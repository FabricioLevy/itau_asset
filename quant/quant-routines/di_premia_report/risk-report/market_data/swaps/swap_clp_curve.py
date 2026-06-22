import pandas as pd
import numpy as np
import datetime
import QuantLib as ql

from a1db.a1sql import SQLConnection

import os, sys
sys.path.insert(1, os.path.expanduser('~\\Documents\\Github\\Instruments'))
from LatamSwap import ClpSwap, SwapUtils


#%%
def main(dt, debug=False):
#%%
    today = ql.Date.from_date(dt)
    str_curvename = 'Swap CLP Zero'
    connection = SQLConnection().get_connection()       
    str_sql = f"""
                SELECT ts.entity_id, ts.name, tsv.value as rate
                FROM [quant].[time_series] ts 
            	  INNER JOIN [quant].[time_series_entity] tse ON ts.entity_id = tse.id
            	  INNER JOIN quant.time_series_value tsv ON tsv.series_id = ts.id
            	  INNER JOIN quant.time_series_grouping tsging on tsging.series_id = ts.id
            	  INNER JOIN quant.time_series_group tsg ON tsg.id = tsging.group_id
                WHERE tsg.[name] = 'IR SWAP CLP' 
                  AND tsv.date_reference = '{dt:%Y-%m-%d}'
    """
    df = pd.read_sql(str_sql, connection, index_col='entity_id')
    
    holiday = False
    if len(df) < 12:
        print("!!!!!!!!!!!!!\n\u26a0 \u26a0 \u26a0 \n " + \
              "Warning: only {:2.0f} of 12 vertices to interpolate the {} curve!".format(len(df),str_curvename) +\
                  "\n!!!!!!!!!!!!!\n")
        holiday = ql.UnitedStates().isHoliday(today)

    
    str_sql = f"""
                SELECT top 1 [date_effective]
                FROM [research].[monetary_policy_meeting]
                WHERE country = 'CLP'
                    AND date_effective >= '{dt:%Y-%m-%d}'
                ORDER BY date_effective
             """
    next_meeting = pd.read_sql(str_sql, connection)['date_effective'].iloc[0]
    del str_sql    
#%%
    calendar_cl = ClpSwap.CLPHolidays()
    spot_d2 = calendar_cl.advance(today, ql.Period("2d"))
    ql.Settings.instance().evaluationDate = today
    if (not calendar_cl.isHoliday(today)) and (not holiday):
    
        clp_ois_yts = ql.RelinkableYieldTermStructureHandle()
        ICP = ql.OvernightIndex("ICP", 
                                0, 
                                ql.CLPCurrency(), 
                                calendar_cl, 
                                ql.Actual360(),
                                clp_ois_yts)
        
        helpers=[]
        # 1-day rate
        rt = df.loc['CLP IR Swap 1D', 'rate'] / 100 
        helpers = [ql.DepositRateHelper(ql.QuoteHandle(ql.SimpleQuote(rt)), 
                                        ql.Period('1D'), 
                                        0,
                                        calendar_cl, 
                                        ql.Following, 
                                        False, 
                                        ql.Actual360())]
        
        tenors = ['3M','6M','9M','12M','18M','2Y','3Y','4Y','5Y','10Y','20Y']
        for t in tenors:
            rt = df.loc['CLP IR Swap {}'.format(t), 'rate'] / 100    
            freq = ql.Once if ql.Period(t).units() == 2 else ql.Semiannual         # M is zero-coupon, Y is semmi-annual
            
            helper = ql.OISRateHelper(2, 
                                      ql.Period(t), 
                                      ql.QuoteHandle(ql.SimpleQuote(rt)), 
                                      ICP, 
                                      paymentFrequency=freq)
            helpers.append(helper)
    #%%
        # curveCLP = ql.PiecewiseLinearZero(spot_d2, helpers, ql.Actual360())
        curveCLP = ql.PiecewiseLogLinearDiscount(today, helpers, ql.Actual360())
        curveCLP.enableExtrapolation()
        clp_ois_yts.linkTo(curveCLP)
        
        buckets = [1, 30, 60, 90, 180, 270, 360, 540, 720, 900] + [i*360 for i in range(3,22)]
        
        data=[(calendar_cl.adjust(today + i).to_date(), i, 
               curveCLP.zeroRate(today + i, ql.Actual360(), ql.Compounded, ql.Annual).rate(), 
               curveCLP.discount(today + i), np.nan) for i in buckets]
        
        data+=[(calendar_cl.adjust(dt_i).to_date(), np.nan, 
               curveCLP.zeroRate(dt_i, ql.Actual360(), ql.Compounded, ql.Annual).rate(), 
               curveCLP.discount(dt_i), t) 
               for (t, (dt_i, _)) in zip([0, '1D']+tenors, curveCLP.nodes()) if t!=0]
        
        dfCurve = pd.DataFrame(data, columns=['tenor_date', 'tenor', 'curve_rate', 'discount_factor','code_maturity'])
        dfCurve.insert(0, 'curve_name', str_curvename)
        dfCurve.insert(0, 'date_reference', dt)
        
        dfCurve['business_day'] = dfCurve['tenor_date'].apply(lambda x: calendar_cl.businessDaysBetween(today, ql.Date.from_date(x)))
        
        #%%  
        str_sql = "DELETE FROM [risk].[interest_rate_curve] "+ \
                  "WHERE curve_name = '{}' AND date_reference = '{:%Y-%m-%d}' ".format(str_curvename, dt)
        connection.execute(str_sql)
        
        dfCurve.to_sql("interest_rate_curve", connection, schema='risk', if_exists='append', index=False)
        print('{} - Inserted {} values for date {} : TABLE interest_rate_curve'.format(str_curvename, len(dfCurve), dt))
        
        #%%
        if debug:
            for t in tenors:
                rt = df.loc['CLP IR Swap {}'.format(t), 'rate'] / 100  
                ois_swap = ClpSwap.ClpSwap(100, 
                                           spot_d2,
                                           calendar_cl.advance(spot_d2, ql.Period(t)), 
                                           rt, 
                                           ICP)
                print(ois_swap)
                # print(SwapUtils.SwapUtils.cashflow_to_pandas(ois_swap, clp_ois_yts))
                ois_swap.setPricingEngine(ql.DiscountingSwapEngine(clp_ois_yts))
                print(f"{t}: {ois_swap.fairRate()*100:.4f}, {rt*100:.4f}\n")
         
                
    
    else:
        print('Feriado no Chile!')
        
    
#%%    
if __name__ == "__main__":
    
    dt = datetime.date(2022, 7, 18)
    main(dt, True)
    
    # dtIni = ql.Date(1,1,2022)
    # dtIni = ClpSwap.CLPHolidays().adjust(dtIni)
    # while dtIni<= ql.Date(18, 7, 2022):    
    #     main(dtIni.to_date(), False)
    #     dtIni = ClpSwap.CLPHolidays().advance(dtIni, ql.Period(1, ql.Days))
