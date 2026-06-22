import datetime
import pandas as pd
import numpy as np
import QuantLib as ql
import sqlalchemy as sa

import os, sys
str_onedrive = '\\OneDrive' if os.path.exists(os.path.expanduser('~\\OneDrive')) else ''
path_github = os.path.expanduser('~{}\\Documents\\Github'.format(str_onedrive))
sys.path.insert(1, path_github + '\\Instruments')
from BRLBond import BrazilianBond

sys.path.insert(0, '../')
import curve_db as cdb

def main(dt, debug=False):
    #%%
    engine = sa.create_engine('mssql+pyodbc://saprod:nhjmmn&^Yh%%^yhjU&@srvprod1.database.windows.net,1433/dbprod1?driver=SQL+Server+Native+Client+11.0')
    connection = engine.connect()
            
    str_sql = """
        SELECT pp.[date_reference], p.id as product_id, p.date_maturity, pp.rate, pp.price
            FROM [middle].[product_price] pp INNER JOIN middle.product p ON pp.product_id = p.id
            WHERE p.product_type = 'NTN-F' and pp.date_reference = '{:%Y-%m-%d}'
    """
    str_sql = str_sql.format(dt)
    df = pd.read_sql(str_sql, connection)
    df.sort_values('date_maturity', inplace=True)
    
    del str_sql
    #%%
    calendar_br = ql.Brazil()
    today = ql.Date.from_date(dt)
    
    ql.Settings.instance().evaluationDate = today
    day_count = ql.Business252(calendar_br)
        
    ntnfs=[]
    ntnf_quotes = []
    ntnf_helpers = []
    for (_, _, dtExp, rt, pu) in df.values:
        f=BrazilianBond.NTNF(ql.Date.from_date(dtExp)) 
        if pu == None:
            pu = 10*(f.cleanPrice(rt, ql.Business252(calendar_br), ql.Compounded, ql.Annual) + f.accruedAmount())
            df.loc[df['date_maturity'] == dtExp, 'price'] = pu
        f.pu_anbima = pu
        f.tx_anbima = rt
        ntnfs.append(f)
        accruedAmount = f.accruedAmount()
        cleanPrice = (pu/10 - accruedAmount)# f.cleanPrice(rt, ql.Business252(calendar_br), ql.Compounded, ql.Annual)
        ntnf_quotes.append(ql.SimpleQuote(cleanPrice))
        ntnf_helpers.append(ql.BondHelper(ql.QuoteHandle(ntnf_quotes[-1]), f))
        if debug:
            print("{} {:3.6f} {:3.6f}".format(f,ntnf_quotes[-1].value(),(pu-accruedAmount)))
    del dtExp, rt, pu
    
    #%%
    df['adj_maturity'] = df['date_maturity'].apply(lambda x: calendar_br.adjust(ql.Date.from_date(x)).to_date())
    df.set_index('adj_maturity', inplace=True)
    
    
    #%%
    
    curveNTNF = ql.PiecewiseLogLinearDiscount(0, calendar_br, ntnf_helpers, day_count)
    curveNTNF.enableExtrapolation()
    ntnf_curve_handle = ql.YieldTermStructureHandle(curveNTNF)
    
    shift_pv01 = ql.SimpleQuote(0.0)
    ntnf_curve_shifted = ql.ZeroSpreadedTermStructure(ntnf_curve_handle, ql.QuoteHandle(shift_pv01), ql.Compounded, ql.Annual)
    ntnf_curve_shifted_handle = ql.YieldTermStructureHandle(ntnf_curve_shifted)

    bond_engine = ql.DiscountingBondEngine(ntnf_curve_shifted_handle)
    for f in ntnfs:
        shift_pv01.setValue(0.0)
        f.setPricingEngine(bond_engine)
        pu_zero = f.NPV()
        pu_tir = (f.notional())/100 * f.dirtyPrice(f.tx_anbima, ql.Business252(calendar_br), ql.Compounded, ql.Annual)
        if debug:
            print('');print(f)
            print("Diff={:2.6f}\nPU Anbima: {:2.6f} PU TIR: {:2.6f} PU Zero: {:2.6f}".\
                  format(f.pu_anbima-pu_zero, f.pu_anbima, pu_tir, pu_zero))
        shift_pv01.setValue(0.0001)
        pu_zero_shifted = f.NPV()
        pu_tir_shifted = (f.notional())/100 * f.dirtyPrice(f.tx_anbima+0.0001, ql.Business252(calendar_br), ql.Compounded, ql.Annual)
        if debug:
            print("pv01 zero={:2.6f}  pv01 Tir={:2.6f}".\
                  format(pu_zero_shifted-f.pu_anbima, pu_tir_shifted-pu_tir))
        
        df.loc[f.maturityDate().to_date(), 'value'] = pu_zero_shifted - f.pu_anbima
        df.loc[f.maturityDate().to_date(), 'prazo_medio'] = BrazilianBond.BRLBond.prazo_medio(today, f)
                

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
        df.loc[f.maturityDate().to_date(), 'spread_cdi'] = (f.tx_anbima - tir_cdi)*10000
        # print('{:1.5%} {:1.5%}'.format(f.tx_anbima, tir_cdi))
    
    
    #%%
    str_sql = "DELETE FROM [risk].[interest_rate_curve] "+ \
              "WHERE curve_name = '{}' AND date_reference = '{:%Y-%m-%d}' ".format(str_curve, dt)
    connection.execute(str_sql)
    
    dfCurve.to_sql("interest_rate_curve", engine, schema='risk', if_exists='append', index=False)
    print('\n{}- Inserted {} values for date {}: TABLE interest_rate_curve'.format(str_curve, len(dfCurve), dt))
    
    
    str_sql = "DELETE price FROM [middle].[product_price] price "+\
                "INNER JOIN [middle].[product] prod "+\
                "ON price.product_id = prod.id "+\
                "WHERE prod.[product_type]='NTN-F' AND "+\
                "price.date_reference = '{:%Y-%m-%d}' ".format(dt)
    connection.execute(str_sql)    
    df[['date_reference','product_id','rate','price']].\
        to_sql("product_price", engine, schema='middle', if_exists='append', index=False)
    print('NTN-F - Inserted {} values for date {} : TABLE product_price'.format(len(df), dt))
    
    str_sql = "DELETE s FROM [risk].[product_sensitivity] s "+\
                "INNER JOIN [middle].[product] prod "+\
                "ON s.product_id = prod.id "+\
                "WHERE prod.[product_type]='NTN-F' AND "+\
                "s.date_reference = '{:%Y-%m-%d}' ".format(dt)
    connection.execute(str_sql)    
    df['sensitivity'] = 'PV01'
    df[['date_reference','product_id','sensitivity','value']].\
        to_sql("product_sensitivity", engine, schema='risk', if_exists='append', index=False)
    print('NTN-F - Inserted {} values for date {} : TABLE product_sensitivity'.format(len(df), dt))
    
    dfPrazoMedio =  df[['date_reference','product_id','prazo_medio']].copy()
    dfPrazoMedio.rename({'prazo_medio':'value'}, axis=1,inplace=True)
    dfPrazoMedio['sensitivity'] = 'prazo_medio'
    dfPrazoMedio.to_sql("product_sensitivity", engine, schema='risk', if_exists='append', index=False)
    print('NTN-F - Inserted {} values for date {} : TABLE product_sensitivity - Prazo Médio'.format(len(df), dt))
      
    dfSpreadCDI =  df[['date_reference','product_id','spread_cdi']].copy()
    dfSpreadCDI.rename({'spread_cdi':'value'}, axis=1,inplace=True)
    dfSpreadCDI['sensitivity'] = 'spread_cdi'
    dfSpreadCDI.to_sql("product_sensitivity", engine, schema='risk', if_exists='append', index=False)
    print('NTN-F - Inserted {} values for date {} : TABLE product_sensitivity - Spread CDI'.format(len(df), dt))
       
    
    connection.close()
    
#%%
if __name__ == "__main__":
       
    dtIni = ql.Date(1,1,2005)
    dtIni = ql.Brazil(ql.Brazil().Exchange).adjust(dtIni)
    while dtIni<= ql.Date(1,1,2010):  
        print(dtIni)
        main(dtIni.to_date(), False)
        dtIni = ql.Brazil(ql.Brazil().Exchange).advance(dtIni, ql.Period(1, ql.Days))
