import pandas as pd
import numpy as np
import datetime
import QuantLib as ql

import os, sys
path_instruments = os.path.expanduser('~\\Documents\\Github\\Instruments')
sys.path.insert(1, path_instruments)
from USBond.USTreasury import TBond

from a1db.a1sql import SQLConnection

#%%
def main(dt, show_debug=False):
#%%
    today = ql.Date.from_date(dt)
    str_curvename = 'US Treasury'
    calendar_us = ql.UnitedStates()
 
    connection = SQLConnection().get_connection()
    str_sql = f"""
                SELECT [tenor_maturity],[par_rate] /100 as rate
                FROM [cme].[treasury_par_yield_curve_rate]
                WHERE date_reference = '{dt:%Y-%m-%d}'
              """
    df = pd.read_sql(str_sql, connection)
    
    df['tenor_adj'] = df['tenor_maturity'].apply(lambda x : x.replace(' ', '')[:-1])
    df['maturity_date'] = df['tenor_adj'].apply(lambda x : calendar_us.advance(today, ql.Period(x)).to_date())
    df = df.sort_values('maturity_date')
    
    if len(df) == 0:
        raise Exception(f"No data for date {dt:%d-%b-%Y}!")
    
    del str_sql    
#%%
    ql.Settings.instance().evaluationDate = today  
    bonds = []
    for maturity_date, coupon in df[['maturity_date', 'rate']].values:   
        bonds.append(TBond(maturity_date, coupon, today))
        
    bond_helpers = [ql.BondHelper(ql.QuoteHandle(ql.SimpleQuote(100.0)), b) for b in bonds]
    curve_ust = ql.PiecewiseCubicZero(today, 
                                      bond_helpers, 
                                      ql.ActualActual())
    curve_ust.enableExtrapolation()
    bond_engine = ql.DiscountingBondEngine(ql.YieldTermStructureHandle(curve_ust))
    
    if show_debug:
        for b in bonds:   
            b.setPricingEngine(bond_engine)
            print(f"{b} ; {b.NPV()=:2,.2f}")


#%%
    curve_ust.enableExtrapolation()
 
    buckets = [1, 30, 60, 90, 180, 270, 360, 540, 720, 900] + [i*360 for i in range(3,31)]
        
    data=[(calendar_us.adjust(today+i).to_date(), i, 
               curve_ust.zeroRate(today+i, ql.Actual360(), ql.Compounded, ql.Annual).rate(), 
               curve_ust.discount(today+i), np.nan) for i in buckets]
        

    data+=[(calendar_us.adjust(dt_i).to_date(), np.nan, 
               curve_ust.zeroRate(dt_i, ql.Actual360(), ql.Compounded, ql.Annual).rate(), 
               curve_ust.discount(dt_i), t) 
               for (t, (dt_i, _)) in zip([0]+list(df['tenor_adj']), curve_ust.nodes()) if t!=0]

        
    dfCurve = pd.DataFrame(data, columns=['tenor_date', 'tenor', 'curve_rate', 'discount_factor','code_maturity'])
    dfCurve.insert(0, 'curve_name', str_curvename)
    dfCurve.insert(0, 'date_reference', dt)
        
    dfCurve['business_day'] = dfCurve['tenor_date'].apply(lambda x: ql.UnitedStates().businessDaysBetween(today, ql.Date.from_date(x)))
        
    #%%  
    str_sql = "DELETE FROM [risk].[interest_rate_curve] "+ \
                  "WHERE curve_name = '{}' AND date_reference = '{:%Y-%m-%d}' ".format(str_curvename, dt)
    connection.execute(str_sql)
        
    dfCurve.to_sql("interest_rate_curve", connection, schema='risk', if_exists='append', index=False)
    print('{} - Inserted {} values for date {} : TABLE interest_rate_curve'.format(str_curvename, len(dfCurve), dt))
        
    
#%%    
if __name__ == "__main__":
    
    dt = datetime.date(2022, 10, 19)
    main(dt, True)
    
    # tic = datetime.datetime.now()
    
    # error_date = []
    
    # dtIni = ql.Date(21, 4, 2000)
    # dtIni = ql.UnitedStates().adjust(dtIni)
    # while dtIni<= ql.Date(28, 9, 2022):  
    #     dt = dtIni.to_date()
    #     try:
    #         main(dt, False)
    #     except Exception as err:
    #         print(f"{err=}")
    #         error_date.append(dt)
    #     dtIni = ql.UnitedStates().advance(dtIni, ql.Period(1, ql.Days))
        
    #     tac = datetime.datetime.now()
    #     print(f"{tac-tic}")
    