import pandas as pd
import numpy as np
import datetime
import QuantLib as ql

from a1db.a1sql import SQLConnection

import os, sys
sys.path.insert(1, os.path.expanduser('~\\Documents\\Github\\Instruments'))
from LatamSwap import CopSwap, SwapUtils

#%%
def main(dt, debug=False):
#%%
    str_curvename = 'Swap COP Zero'
    calendar_co = CopSwap.COPHolidays()
    today = ql.Date.from_date(dt)
    spot_d2 = calendar_co.advance(today, ql.Period("2d"))
    ql.Settings.instance().evaluationDate = today
        
    connection = SQLConnection().get_connection()
        
    str_sql = """
                SELECT ts.entity_id, ts.name, tsv.value as rate
                FROM [quant].[time_series] ts 
            	INNER JOIN [quant].[time_series_entity] tse ON ts.entity_id = tse.id
            	INNER JOIN quant.time_series_value tsv ON tsv.series_id = ts.id
            	INNER JOIN quant.time_series_grouping tsging on tsging.series_id = ts.id
            	INNER JOIN quant.time_series_group tsg ON tsg.id = tsging.group_id
                WHERE tsg.[name] = 'IR SWAP COP' AND tsv.date_reference = '{:%Y-%m-%d}'
    
              """
    str_sql = str_sql.format(dt)
    df = pd.read_sql(str_sql, connection, index_col='name')
    holiday = False
    if len(df) < 12:
        print("!!!!!!!!!!!!!\n\u26a0 \u26a0 \u26a0 \n " + \
              "Warning: only {:2.0f} of 12 vertices to interpolate the {} curve!".format(len(df),str_curvename) +\
                  "\n!!!!!!!!!!!!!\n")
        holiday = ql.UnitedStates().isHoliday(today)  
    
    del str_sql    
#%%
    if (not calendar_co.isHoliday(today)) and (not holiday):
        
        cop_ois_yts = ql.RelinkableYieldTermStructureHandle()
        IBR = ql.OvernightIndex("IBR", 
                                0, 
                                ql.CLPCurrency(), 
                                calendar_co, 
                                ql.Actual360(),
                                cop_ois_yts)    
        
        rt = df.loc['Colombia IBR Overnight', 'rate'] / 100
        h = ql.DepositRateHelper(ql.QuoteHandle(ql.SimpleQuote(rt)), 
                                 ql.Period('1D'), 
                                 0,
                                 calendar_co, 
                                 ql.Following, 
                                 False, 
                                 ql.Actual360())
        helpers = [h]
        str_index = 'Colombia swap fixed-floating {}'
        tenors = ['3M','6M','9M','1Y', '18M', '2Y','3Y','4Y','5Y','10Y','20Y']
        for t in tenors:
            if str_index.format(t) in df.index:
                rt = df.loc[str_index.format(t), 'rate'] / 100
                freq = ql.Once if ql.Period(t)<=ql.Period('18M') else ql.Quarterly         # M is zero-coupon, Y is semmi-annual
                h = ql.OISRateHelper(2, 
                                     ql.Period(t), 
                                     ql.QuoteHandle(ql.SimpleQuote(rt)),
                                     IBR,
                                     paymentFrequency=freq)
                helpers.append(h)
        
    #%%
        curveCOP = ql.PiecewiseLogLinearDiscount(today, helpers, ql.Actual360())
        curveCOP.enableExtrapolation()
        cop_ois_yts.linkTo(curveCOP)
        
        buckets = [1, 30, 60, 90, 180, 270, 360, 540, 720, 900] + [i*360 for i in range(3,22)]
        
        data=[(calendar_co.adjust(today+i).to_date(), i, 
               curveCOP.zeroRate(today+i, ql.Actual360(), ql.Compounded, ql.Annual).rate(), 
               curveCOP.discount(today+i), np.nan) for i in buckets]
        
        data+=[(calendar_co.adjust(dt_i).to_date(), np.nan, 
               curveCOP.zeroRate(dt_i, ql.Actual360(), ql.Compounded, ql.Annual).rate(), 
               curveCOP.discount(dt_i), t) 
               for (t, (dt_i, _)) in zip([0,'1D']+tenors, curveCOP.nodes()) if t!=0]
        
        dfCurve = pd.DataFrame(data, columns=['tenor_date', 'tenor', 'curve_rate', 'discount_factor','code_maturity'])
        dfCurve.insert(0, 'curve_name', str_curvename)
        dfCurve.insert(0, 'date_reference', dt)
        
        dfCurve['business_day'] = dfCurve['tenor_date'].apply(lambda x: calendar_co.businessDaysBetween(today, ql.Date.from_date(x)))
        
        #%%  
        str_sql = "DELETE FROM [risk].[interest_rate_curve] "+ \
                  "WHERE curve_name = '{}' AND date_reference = '{:%Y-%m-%d}' ".format(str_curvename, dt)
        connection.execute(str_sql)
        
        dfCurve.to_sql("interest_rate_curve", connection, schema='risk', if_exists='append', index=False)
        print('{} - Inserted {} values for date {} : TABLE interest_rate_curve'.format(str_curvename, len(dfCurve), dt))
        
        #%%
        if debug:
            for t in tenors:
                rt = df.loc[str_index.format(t), 'rate'] / 100
                ois_swap = CopSwap.CopSwap(100, 
                                           spot_d2,
                                           calendar_co.advance(spot_d2, ql.Period(t)), 
                                           rt, 
                                           IBR)
                print(ois_swap)
                # print(SwapUtils.SwapUtils.cashflow_to_pandas(ois_swap, clp_ois_yts))
                ois_swap.setPricingEngine(ql.DiscountingSwapEngine(cop_ois_yts))
                print(f"{t}: {ois_swap.fairRate()*100:.4f}, {rt*100:.4f}\n")
         
    else:
        print('Feriado na Colombia!')
        
   
    
#%%    
if __name__ == "__main__":
    
    # dt = datetime.date(2022, 7, 18)
    # main(dt, True)
    
    calendar_co = CopSwap.COPHolidays()
    dtIni = ql.Date(31, 12, 2021)
    dtIni = calendar_co.adjust(dtIni)
    while dtIni<= ql.Date(18, 7, 2022):    
        main(dtIni.to_date())
        dtIni = calendar_co.advance(dtIni, ql.Period(1, ql.Days))
