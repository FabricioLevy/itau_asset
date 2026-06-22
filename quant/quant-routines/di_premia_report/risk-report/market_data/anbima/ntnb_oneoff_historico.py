import datetime
import pandas as pd
import numpy as np
import QuantLib as ql
import sqlalchemy as sa

import os
path_instruments = os.path.expanduser('~\\Documents\\Github\\Instruments')
import sys
sys.path.insert(1, path_instruments)
from BRLBond import BrazilianBond

dt = datetime.date(2012, 12, 3)

def main(dt, debug=False):
    #%%
    engine = sa.create_engine('mssql+pyodbc://saprod:nhjmmn&^Yh%%^yhjU&@srvprod1.database.windows.net,1433/dbprod1?driver=SQL+Server+Native+Client+11.0')
    connection = engine.connect()
            
    str_sql = """
    SELECT pp.[date_reference], p.id as product_id, p.date_maturity, pp.rate, pp.price, p.date_issue, pp_vna.price as VNA
  FROM [middle].[product_price] pp INNER JOIN middle.product p ON pp.product_id = p.id
  INNER JOIN middle.product_price pp_vna ON pp_vna.date_reference = pp.date_reference
  where p.product_type = 'NTN-B' and pp_vna.product_id = 'VNA NTNB'
  and pp.date_reference = '{:%Y-%m-%d}'
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
    
    ntnbs=[]
    ntnb_quotes = []
    ntnb_helpers = []
    for (_, _,  dtExp, rt, pu, dtIssue, vna) in df.values:
        b=BrazilianBond.NTNB(ql.Date.from_date(dtExp), ql.Date.from_date(dtIssue), vna) 
        b.pu_anbima = pu
        b.tx_anbima = rt
        ntnbs.append(b)
        accruedAmount = b.accruedAmount()
        cleanPrice = (pu/vna*100 - accruedAmount)# b.cleanPrice(rt, ql.Business252(calendar_br), ql.Compounded, ql.Annual)
        ntnb_quotes.append(ql.SimpleQuote(cleanPrice))
        ntnb_helpers.append(ql.BondHelper(ql.QuoteHandle(ntnb_quotes[-1]), b))
        if debug:
            print("{} {:3.6f} {:3.6f}".format(b,ntnb_quotes[-1].value(),(pu/vna*100-accruedAmount)))
    del dtExp, rt, pu, dtIssue, vna
    
    #%%
    df['adj_maturity'] = df['date_maturity'].apply(lambda x: calendar_br.adjust(ql.Date.from_date(x)).to_date())
    df.set_index('adj_maturity', inplace=True)
    
    #%%
    
    curveNTNB = ql.PiecewiseLogLinearDiscount(0, calendar_br, ntnb_helpers, day_count)
    curveNTNB.enableExtrapolation()
    ntnb_curve_handle = ql.YieldTermStructureHandle(curveNTNB)
    
    shift_pv01 = ql.SimpleQuote(0.0)
    ntnb_curve_shifted = ql.ZeroSpreadedTermStructure(ntnb_curve_handle, ql.QuoteHandle(shift_pv01), ql.Compounded, ql.Annual)
    ntnb_curve_shifted_handle = ql.YieldTermStructureHandle(ntnb_curve_shifted)

    bond_engine = ql.DiscountingBondEngine(ntnb_curve_shifted_handle)
    for b in ntnbs:
        shift_pv01.setValue(0.0)
        b.setPricingEngine(bond_engine)
        pu_zero = b.NPV()*b.VNA()/100
        pu_tir = b.dirtyPrice(b.tx_anbima, ql.Business252(calendar_br), ql.Compounded, ql.Annual)*b.VNA()/100
        if debug:
            print('');print(b)
            print("Diff={:2.6f}\nPU Anbima: {:2.6f} PU TIR: {:2.6f} PU Zero: {:2.6f}".\
                  format(b.pu_anbima-pu_zero, b.pu_anbima, pu_tir,pu_zero))
        shift_pv01.setValue(0.0001)
        pu_zero_shifted = b.NPV()*b.VNA()/100
        pu_tir_shifted = b.dirtyPrice(b.tx_anbima+0.0001, ql.Business252(calendar_br), ql.Compounded, ql.Annual)*b.VNA()/100
        if debug:
            print("pv01 zero={:2.6f}  pv01 Tir={:2.6f}".\
                  format(pu_zero_shifted-b.pu_anbima, pu_tir_shifted-b.pu_anbima))
        
        df.loc[b.maturityDate().to_date(), 'value'] = pu_zero_shifted - b.pu_anbima
        df.loc[b.maturityDate().to_date(), 'prazo_medio'] = BrazilianBond.BRLBond.prazo_medio(today, b)
                

     #%%
    str_curve = 'NTNB Zero'
    dic_bucket = {1:'1D',30:'1M',60:'2M',90:'3M',180:'6M',\
                      270:'9M',360:'1Y',540:'1.5Y',720:'2Y',900:'2.5Y'} 
    dic_bucket.update({i*360:'{}Y'.format(i) for i in range(3,51)})
    
    data=[(calendar_br.adjust(today+i, ql.Following).to_date(), i, \
           curveNTNB.zeroRate(today+i, ql.Business252(calendar_br), ql.Compounded).rate() ,\
           curveNTNB.discount(calendar_br.adjust(today+i, ql.Following))) \
          for i in dic_bucket.keys()]
        
    data+=[(b.maturityDate().to_date(), np.nan, \
           curveNTNB.zeroRate(b.maturityDate(), ql.Business252(calendar_br), ql.Compounded).rate() ,\
           curveNTNB.discount(calendar_br.adjust(b.maturityDate(), ql.Following))) \
           for b in ntnbs]    
    
    dfCurve = pd.DataFrame(data, columns=['tenor_date', 'tenor', 'curve_rate', 'discount_factor'])
    dfCurve.insert(0, 'curve_name', str_curve)
    dfCurve.insert(0, 'date_reference', dt)
    dfCurve['code_maturity'] = np.nan
    dfCurve['business_day'] = dfCurve['tenor_date'].apply(lambda x: calendar_br.businessDaysBetween(today, ql.Date.from_date(x)))
        
    #%%
    str_sql = "DELETE FROM [risk].[interest_rate_curve] "+ \
              "WHERE curve_name = '{}' AND date_reference = '{:%Y-%m-%d}' ".format(str_curve, dt)
    connection.execute(str_sql)
    
    dfCurve.to_sql("interest_rate_curve", engine, schema='risk', if_exists='append', index=False)
    print('\n{}- Inserted {} values for date {}'.format(str_curve, len(dfCurve), dt))
    
   
    str_sql = "DELETE s FROM [risk].[product_sensitivity] s "+\
                "INNER JOIN [middle].[product] prod "+\
                "ON s.product_id = prod.id "+\
                "WHERE prod.product_type='NTN-B' AND "+\
                "s.date_reference = '{:%Y-%m-%d}' ".format(dt)
    connection.execute(str_sql)    
    df['sensitivity'] = 'PV01'
    df[['date_reference','product_id','sensitivity','value']].\
        to_sql("product_sensitivity", engine, schema='risk', if_exists='append', index=False)
    print('NTN-B - Inserted {} values for date {} : TABLE product_sensitivity'.format(len(df), dt))
    
    dfPrazoMedio =  df[['date_reference','product_id','prazo_medio']].copy()
    dfPrazoMedio.rename({'prazo_medio':'value'}, axis=1,inplace=True)
    dfPrazoMedio['sensitivity'] = 'prazo_medio'
    dfPrazoMedio.to_sql("product_sensitivity", engine, schema='risk', if_exists='append', index=False)
    print('NTN-B - Inserted {} values for date {} : TABLE product_sensitivity - Prazo Médio'.format(len(df), dt))
        
    connection.close()
    
#%%
if __name__ == "__main__":
    
    # main(dt, False)

    dtIni = ql.Date(12,5,2008)    
    dtIni = ql.Brazil().adjust(dtIni)
    while dtIni<= ql.Date(12,5,2008):  
        print(dtIni)
        main(dtIni.to_date(), False)
        dtIni = ql.Brazil().advance(dtIni, ql.Period(1, ql.Days))

