import datetime
import pandas as pd
import numpy as np
import QuantLib as ql

from a1db.a1sql import SQLConnection

import os, sys
path_github = os.path.expanduser('~\\Documents\\Github')
sys.path.insert(1, path_github + '\\Instruments')

# from BRLBond import BrazilianBond
from BRLBond import BrazilianGovernmentBond as BRLGovBond


def main(dt, debug=False):
    #%%
    connection = SQLConnection().get_connection()
            
    str_sql = "SELECT t.[date_reference], Cast(t.[data_vencimento] as Date) as date_maturity, "+\
                "t.[taxa_indicativa]/100 as rate, t.[PU] as price, t.[data_emissao] as date_issue " +\
                " FROM [anbima].taxa_titulo_publico t " +\
                " WHERE t.titulo = 'LTN' AND t.[date_reference] = '{:%Y-%m-%d}'".format(dt)
    df = pd.read_sql(str_sql, connection)
    df.sort_values('date_maturity', inplace=True)
    
    str_sql = "SELECT [id] as product_id,[date_maturity] FROM [middle].[product] " +\
                "WHERE product_type = 'LTN' AND date_maturity >= '{:%Y-%m-%d}'".format(dt)
    dfProduct = pd.read_sql(str_sql, connection)
    
    del str_sql
    #%%
    calendar_br = ql.Brazil()
    today = ql.Date.from_date(dt)
    ql.Settings.instance().evaluationDate = today
         
    ltns = []
    dates = [today]
    discfactors = [1]
    for (_, dt_i, rt, pu, dtIssue) in df.values:
        dtExp = ql.Date.from_date(dt_i)
        if (pu == None):
            du = calendar_br.businessDaysBetween(today, 
                                                 dtExp)
            pu = 1_000 / (1+rt)**(du/252)
            df.loc[df['date_maturity'] == dt_i, 'price'] = pu
        l=BRLGovBond.LTN(dtExp, 
                         ql.Date.from_date(dtIssue)) 
        l.pu_anbima = pu
        l.tx_anbima = rt
        ltns.append(l)
        dates.append(dtExp)
        discfactors.append(pu/1_000)   
    
    #%%
    df['adj_maturity'] = df['date_maturity'].apply(lambda x: calendar_br.adjust(ql.Date.from_date(x)).to_date())
    dfProduct['adj_maturity'] = dfProduct['date_maturity'].apply(lambda x: calendar_br.adjust(ql.Date.from_date(x)).to_date())
    dfProduct = dfProduct[['product_id', 'adj_maturity']].set_index('adj_maturity')
    df = df.join(dfProduct, on='adj_maturity', how='left')
    df.set_index('date_maturity', inplace=True)
    
    #%%
    curveLTN = ql.DiscountCurve(dates, 
                                discfactors,
                                ql.Business252(calendar_br),
                                calendar_br, 
                                ql.LogLinear())   
    curveLTN.enableExtrapolation()
    ltn_curve_handle = ql.YieldTermStructureHandle(curveLTN)
    
    shift_pv01 = ql.SimpleQuote(0.0001)
    ltn_curve_shifted = ql.ZeroSpreadedTermStructure(ltn_curve_handle, 
                                                     ql.QuoteHandle(shift_pv01), 
                                                     ql.Compounded, 
                                                     ql.Annual)
    ltn_curve_shifted_handle = ql.YieldTermStructureHandle(ltn_curve_shifted)

    bond_engine = ql.DiscountingBondEngine(ltn_curve_shifted_handle)
    for l in ltns:
        l.setPricingEngine(bond_engine)
        df.loc[l.maturityDate().to_date(), 'value'] = l.NPV() - l.pu_anbima
        df.loc[l.maturityDate().to_date(), 'prazo_medio'] = l.prazo_medio(today)
    #%%
    str_curve = 'LTN'
    dic_bucket = {1:'1D',30:'1M',60:'2M',90:'3M',180:'6M',\
                      270:'9M',360:'1Y',540:'1.5Y',720:'2Y',900:'2.5Y'} 
    dic_bucket.update({i*360:'{}Y'.format(i) for i in range(3,21)})
    
    data=[(calendar_br.adjust(today+i, ql.Following).to_date(), i, \
           curveLTN.zeroRate(today+i, ql.Business252(calendar_br), ql.Compounded).rate() ,\
           curveLTN.discount(calendar_br.adjust(today+i, ql.Following))) \
          for i in dic_bucket.keys()]
        
    data+=[(b.maturityDate().to_date(), np.nan, \
           curveLTN.zeroRate(b.maturityDate(), ql.Business252(calendar_br), ql.Compounded).rate() ,\
           curveLTN.discount(calendar_br.adjust(b.maturityDate(), ql.Following))) \
           for b in ltns]    
    
    dfCurve = pd.DataFrame(data, columns=['tenor_date', 'tenor', 'curve_rate', 'discount_factor'])
    dfCurve.insert(0, 'curve_name', str_curve)
    dfCurve.insert(0, 'date_reference', dt)
    dfCurve['code_maturity'] = np.nan
    dfCurve['business_day'] = dfCurve['tenor_date'].apply(lambda x: calendar_br.businessDaysBetween(today, ql.Date.from_date(x)))
        
    #%%
    str_sql = f"""
                DELETE 
                FROM [risk].[interest_rate_curve]
                WHERE curve_name = '{str_curve}' 
                   AND date_reference = '{dt:%Y-%m-%d}'
            """
    connection.execute(str_sql)    
    dfCurve.to_sql("interest_rate_curve", 
                   connection, 
                   schema='risk', 
                   if_exists='append', 
                   index=False)
    print(f"{str_curve} - Inserted {len(dfCurve)} values for date {dt} : TABLE interest_rate_curve")
    
    str_sql = f"""
                DELETE price FROM [middle].[product_price] price 
                     INNER JOIN [middle].[product] prod 
                           ON price.product_id = prod.id 
                WHERE prod.product_type='LTN' 
                   AND price.date_reference = '{dt:%Y-%m-%d}'
                """
    connection.execute(str_sql)    
    df[['date_reference','product_id','rate','price']].to_sql("product_price", 
                                                              connection, 
                                                              schema='middle', 
                                                              if_exists='append', 
                                                              index=False)
    print(f"LTN - Inserted {len(df)} values for date {dt} : TABLE product_price")
    
    str_sql = "DELETE s FROM [risk].[product_sensitivity] s "+\
                "INNER JOIN [middle].[product] prod "+\
                "ON s.product_id = prod.id "+\
                "WHERE prod.[product_type]='LTN' AND "+\
                "s.date_reference = '{:%Y-%m-%d}' ".format(dt)
    connection.execute(str_sql)    
    df['sensitivity'] = 'PV01'
    df[['date_reference','product_id','sensitivity','value']].\
        to_sql("product_sensitivity", connection, schema='risk', if_exists='append', index=False)
    print('LTN - Inserted {} values for date {} : TABLE product_sensitivity - PV01'.format(len(df), dt))
    
    dfPrazoMedio =  df[['date_reference','product_id','prazo_medio']].copy()
    dfPrazoMedio.rename({'prazo_medio':'value'}, axis=1,inplace=True)
    dfPrazoMedio['sensitivity'] = 'prazo_medio'
    dfPrazoMedio.to_sql("product_sensitivity", connection, schema='risk', if_exists='append', index=False)
    print('LTN - Inserted {} values for date {} : TABLE product_sensitivity - Prazo Médio'.format(len(df), dt))
    
 
#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 3, 23)
    main(dt)
    
