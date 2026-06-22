import datetime
import pandas as pd
import numpy as np
import QuantLib as ql

from a1db.a1sql import SQLConnection

import os, sys
path_github = os.path.expanduser('~\\Documents\\Github')
sys.path.insert(1, path_github + '\\Instruments')
# from BRLBond import BrazilianBond as BRLGovBond
from BRLBond import BrazilianGovernmentBond as BRLGovBond

sys.path.insert(0, '../')
import curve_db as cdb

def main(dt, debug=False):
    #%%
    connection = SQLConnection().get_connection()
            
    str_sql = "SELECT t.[date_reference], Cast(t.[data_vencimento] as Date) as date_maturity, "+\
                "t.[taxa_indicativa]/100 as rate, t.[PU] as price, t.[data_emissao] as date_issue " +\
                " FROM [anbima].taxa_titulo_publico t " +\
                " WHERE t.titulo = 'NTN-F' AND t.[date_reference] = '{:%Y-%m-%d}'".format(dt)
    df = pd.read_sql(str_sql, connection)
    df.sort_values('date_maturity', inplace=True)
    
    str_sql = "SELECT [id] as product_id,[date_maturity] FROM [middle].[product] " +\
                "WHERE product_type = 'NTN-F' AND date_maturity >= '{:%Y-%m-%d}'".format(dt)
    dfProduct = pd.read_sql(str_sql, connection)
    
    del str_sql
    #%%
    calendar_br = ql.Brazil()
    today = ql.Date.from_date(dt)
    
    ql.Settings.instance().evaluationDate = today
    day_count = ql.Business252(calendar_br)    
    
    ntnfs = []
    ntnf_helpers = []
    for (_, dtExp, rt, pu, dtIssue) in df.values:
        dtIssue = min(dtIssue, datetime.date(2021,1,1))
        f = BRLGovBond.NTNF(ql.Date.from_date(dtExp), 
                            ql.Date.from_date(dtIssue)) 
        if pu == None:
            pu = (f.notional()/100) * (f.dirtyPrice(rt,
                                                    ql.Business252(calendar_br), 
                                                    ql.Compounded, 
                                                    ql.Annual))
            df.loc[df['date_maturity'] == dtExp, 'price'] = pu
        f.pu_anbima = pu
        f.tx_anbima = rt
        ntnfs.append(f)
        cleanPrice = f.cleanPrice(rt, ql.Business252(calendar_br), ql.Compounded, ql.Annual)
        ntnf_helpers.append(ql.BondHelper(ql.QuoteHandle(ql.SimpleQuote(cleanPrice)), f))
        if debug:
            print(f"ANBIMA> PU :{f.pu_anbima:14,.6f}  Tx:{f.tx_anbima:12.4%}")
            dp = (f.notional()/100)* f.dirtyPrice(rt, ql.Business252(calendar_br), ql.Compounded, ql.Annual)
            cp = (f.notional()/100)* f.cleanPrice(rt, ql.Business252(calendar_br), ql.Compounded, ql.Annual)
            print(f"QuantLib> DP: {dp:14,.6f} CP: {cp:14,.6f}")
            print(f"QuantLib> CP+AM: {(f.notional()/100)*f.accruedAmount()+cp:12,.6f} Accr: {f.accruedAmount():12,.6f} ")
               
    
    #%%
    df['adj_maturity'] = df['date_maturity'].apply(lambda x: calendar_br.adjust(ql.Date.from_date(x)).to_date())
    dfProduct['adj_maturity'] = dfProduct['date_maturity'].apply(lambda x: calendar_br.adjust(ql.Date.from_date(x)).to_date())
    dfProduct = dfProduct[['product_id', 'adj_maturity']].set_index('adj_maturity')
    df = df.join(dfProduct, on='adj_maturity', how='left')
    df.set_index('adj_maturity', inplace=True)
    
    #%%    
    curveNTNF = ql.PiecewiseLogLinearDiscount(0, 
                                              calendar_br, 
                                              ntnf_helpers, 
                                              day_count)
    curveNTNF.enableExtrapolation()
    ntnf_curve_handle = ql.YieldTermStructureHandle(curveNTNF)
    
    shift_pv01 = ql.SimpleQuote(0.0)
    ntnf_curve_shifted = ql.ZeroSpreadedTermStructure(ntnf_curve_handle, 
                                                      ql.QuoteHandle(shift_pv01), 
                                                      ql.Compounded, 
                                                      ql.Annual)
    ntnf_curve_shifted_handle = ql.YieldTermStructureHandle(ntnf_curve_shifted)

    bond_engine = ql.DiscountingBondEngine(ntnf_curve_shifted_handle)
    for f in ntnfs:
        shift_pv01.setValue(0.0)
        f.setPricingEngine(bond_engine)
        pu_zero = f.NPV()
        pu_tir = (f.notional()/100) * f.dirtyPrice(f.tx_anbima, 
                                                   ql.Business252(calendar_br), 
                                                   ql.Compounded, 
                                                   ql.Annual)
        if debug:
            print(f)
            print("Diff={:2.6f}\nPU Anbima: {:2.6f} PU TIR: {:2.6f} PU Zero: {:2.6f}".\
                  format(f.pu_anbima-pu_zero, f.pu_anbima, pu_tir, pu_zero))
                
        shift_pv01.setValue(0.0001)
        pu_zero_shifted = f.NPV()
        pu_tir_shifted = (f.notional()/100) * f.dirtyPrice(f.tx_anbima+0.0001, 
                                                           ql.Business252(calendar_br), 
                                                           ql.Compounded, 
                                                           ql.Annual)
        if debug:
            print("pv01 zero={:2.6f}  pv01 Tir={:2.6f}".\
                  format(pu_zero_shifted-f.pu_anbima, pu_tir_shifted-pu_tir))
        
        df.loc[f.maturityDate().to_date(), 'value'] = pu_zero_shifted - f.pu_anbima
        df.loc[f.maturityDate().to_date(), 'prazo_medio'] = f.prazo_medio(today)
        
        if abs(f.pu_anbima-pu_zero) > 0.001:
            print(f">> Warning << {f} : Diff PU TIR x Zero: {f.pu_anbima-pu_zero:12.6f}")
                

     #%%
    str_curve = 'NTNF Zero'
    dic_bucket = {1:'1D',30:'1M',60:'2M',90:'3M',180:'6M',\
                      270:'9M',360:'1Y',540:'1.5Y',720:'2Y',900:'2.5Y'} 
    dic_bucket.update({i*360:'{}Y'.format(i) for i in range(3,51)})
    
    data=[(calendar_br.adjust(today+i, ql.Following).to_date(), i, \
           curveNTNF.zeroRate(today+i, ql.Business252(calendar_br), ql.Compounded).rate() ,\
           curveNTNF.discount(calendar_br.adjust(today+i, ql.Following))) \
          for i in dic_bucket.keys()]
        
    data+=[(b.maturityDate().to_date(), np.nan, \
           curveNTNF.zeroRate(b.maturityDate(), ql.Business252(calendar_br), ql.Compounded).rate() ,\
           curveNTNF.discount(calendar_br.adjust(b.maturityDate(), ql.Following))) \
           for b in ntnfs]    
    
    dfCurve = pd.DataFrame(data, columns=['tenor_date', 'tenor', 'curve_rate', 'discount_factor'])
    dfCurve.insert(0, 'curve_name', str_curve)
    dfCurve.insert(0, 'date_reference', dt)
    dfCurve['code_maturity'] = np.nan
    dfCurve['business_day'] = dfCurve['tenor_date'].apply(lambda x: calendar_br.businessDaysBetween(today, ql.Date.from_date(x)))
        
    #%%
    curve_di = cdb.get_curve(dt, 'DI Fut')
    curve_di.enableExtrapolation()
    curve_di_handle = ql.YieldTermStructureHandle(curve_di)    
    bond_engine_di = ql.DiscountingBondEngine(curve_di_handle)
    for f in ntnfs:
        f.setPricingEngine(bond_engine_di)
        tir_cdi = f.bondYield(ql.Business252(), ql.Compounded, ql.Annual)
        df.loc[f.maturityDate().to_date(), 'spread_cdi'] = (f.tx_anbima - tir_cdi)*10_000
        # print('{:1.5%} {:1.5%}'.format(f.tx_anbima, tir_cdi))
    
    
    #%%
    str_sql = "DELETE FROM [risk].[interest_rate_curve] "+ \
              "WHERE curve_name = '{}' AND date_reference = '{:%Y-%m-%d}' ".format(str_curve, dt)
    connection.execute(str_sql)
    
    dfCurve.to_sql("interest_rate_curve", connection, schema='risk', if_exists='append', index=False)
    print('{} - Inserted {} values for date {}: TABLE interest_rate_curve'.format(str_curve, len(dfCurve), dt))
    
    
    str_sql = "DELETE price FROM [middle].[product_price] price "+\
                "INNER JOIN [middle].[product] prod "+\
                "ON price.product_id = prod.id "+\
                "WHERE prod.[product_type]='NTN-F' AND "+\
                "price.date_reference = '{:%Y-%m-%d}' ".format(dt)
    connection.execute(str_sql)    
    df[['date_reference','product_id','rate','price']].\
        to_sql("product_price", connection, schema='middle', if_exists='append', index=False)
    print('NTN-F - Inserted {} values for date {} : TABLE product_price'.format(len(df), dt))
    
    str_sql = "DELETE s FROM [risk].[product_sensitivity] s "+\
                "INNER JOIN [middle].[product] prod "+\
                "ON s.product_id = prod.id "+\
                "WHERE prod.[product_type]='NTN-F' AND "+\
                "s.date_reference = '{:%Y-%m-%d}' ".format(dt)
    connection.execute(str_sql)    
    df['sensitivity'] = 'PV01'
    df[['date_reference','product_id','sensitivity','value']].\
        to_sql("product_sensitivity", connection, schema='risk', if_exists='append', index=False)
    print('NTN-F - Inserted {} values for date {} : TABLE product_sensitivity'.format(len(df), dt))
    
    dfPrazoMedio =  df[['date_reference','product_id','prazo_medio']].copy()
    dfPrazoMedio.rename({'prazo_medio':'value'}, axis=1,inplace=True)
    dfPrazoMedio['sensitivity'] = 'prazo_medio'
    dfPrazoMedio.to_sql("product_sensitivity", connection, schema='risk', if_exists='append', index=False)
    print('NTN-F - Inserted {} values for date {} : TABLE product_sensitivity - Prazo Médio'.format(len(df), dt))
      
    dfSpreadCDI =  df[['date_reference','product_id','spread_cdi']].copy()
    dfSpreadCDI.rename({'spread_cdi':'value'}, axis=1,inplace=True)
    dfSpreadCDI['sensitivity'] = 'spread_cdi'
    dfSpreadCDI.to_sql("product_sensitivity", connection, schema='risk', if_exists='append', index=False)
    print('NTN-F - Inserted {} values for date {} : TABLE product_sensitivity - Spread CDI'.format(len(df), dt))
       
    
#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 3, 23)
    # main(dt, True)   
        
    main(dt)

