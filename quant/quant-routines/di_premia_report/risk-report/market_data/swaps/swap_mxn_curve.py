import pandas as pd
import numpy as np
import datetime
import QuantLib as ql

from a1db.a1sql import SQLConnection

import os, sys
sys.path.insert(1, os.path.expanduser('~\\Documents\\Github\\Instruments'))
from LatamSwap import MxnSwap, SwapUtils

sys.path.insert(0,'..')
import curve_db as cdb

#%%
def main(dt, debug=False):
#%%
    today = ql.Date.from_date(dt)
    settle_date = ql.Mexico().advance(today, 1, ql.Days)
    str_curvename = 'MXN TIIE Zero'
    connection = SQLConnection().get_connection()
    str_sql = """
                SELECT ts.name, tsv.value as rate --,ts.entity_id
                FROM [quant].[time_series] ts 
            	INNER JOIN [quant].[time_series_entity] tse ON ts.entity_id = tse.id
            	INNER JOIN quant.time_series_value tsv ON tsv.series_id = ts.id
            	INNER JOIN quant.time_series_grouping tsging on tsging.series_id = ts.id
            	INNER JOIN quant.time_series_group tsg ON tsg.id = tsging.group_id
                WHERE tsg.[name] = 'IR SWAP MXN' AND tsv.date_reference = '{:%Y-%m-%d}'
              """
    str_sql = str_sql.format(dt)
    df = pd.read_sql(str_sql, connection, index_col='name')
    # df = df.loc[sorted(list(df.index), key=lambda x: int(''.join([i for i in x if i.isnumeric()])))]
    holiday = False
    if len(df) < 11:
        print("!!!!!!!!!!!!!\n\u26a0 \u26a0 \u26a0 \nWarning: only {:2.0f} of 11 vertices to interpolate the curve!\n!!!!!!!!!!!!!\n".format(len(df)))
        holiday = ql.UnitedStates().isHoliday(today)
    del str_sql    
#%%
    if (not ql.Mexico().isHoliday(today)) and (not holiday):
        ql.Settings.instance().evaluationDate = today
        
        mxn_swp_yts = ql.RelinkableYieldTermStructureHandle()
        tiie_index =  ql.IborIndex('TIIE', 
                                   ql.Period('4W'), 
                                   1, 
                                   ql.MXNCurrency(),
                                   ql.Mexico(), 
                                   ql.Following, 
                                   False, 
                                   ql.Actual360(),
                                   mxn_swp_yts)
    
        index_rate = df.loc['MXN TIIE 28D', 'rate'] / 100 
        helpers = [ql.DepositRateHelper(ql.QuoteHandle(ql.SimpleQuote(index_rate)),
                                        ql.Period('4W'), 
                                        1, 
                                        ql.Mexico(), 
                                        ql.Following, 
                                        False, 
                                        ql.Actual360())]
        
        tenors = [3, 6, 9, 13, 26, 39, 52, 65, 130, 260]
        for t in tenors:
            tenor_period = ql.Period('{}W'.format(t*4))
            ind = 'MXN TIIE {:1.0f}x1'.format(t)
            if ind in df.index:
                rt = df.loc[ind, 'rate'] / 100
                df.loc[ind,'tenor'] = t
                h = ql.SwapRateHelper(ql.QuoteHandle(ql.SimpleQuote(rt)), 
                                      tenor_period, 
                                      ql.Mexico(),
                                      ql.EveryFourthWeek, 
                                      ql.Following,  
                                      ql.Actual360(), 
                                      tiie_index)
                helpers.append(h)
    #%%
        curveTIIE = ql.PiecewiseLinearZero(today, helpers, ql.Actual360())
        # curveTIIE = ql.PiecewiseCubicZero(today, helpers, ql.Actual360())
        curveTIIE.enableExtrapolation()
        mxn_swp_yts.linkTo(curveTIIE)
        
        buckets = [1, 30, 60, 90, 180, 270, 360, 540, 720, 900] + [i*360 for i in range(3,21)]
        
        data=[(ql.Mexico().adjust(today+i).to_date(), i, 
               curveTIIE.zeroRate(today+i, ql.Actual360(), ql.Compounded).rate(), 
               curveTIIE.discount(today+i), np.nan) for i in buckets]
        
        data+=[(ql.Mexico().adjust(dt_i).to_date(), np.nan, 
               curveTIIE.zeroRate(dt_i, ql.Actual360(), ql.Compounded).rate(), 
               curveTIIE.discount(dt_i), '{:1.0f}x1'.format(t)) 
               for (t, (dt_i, _)) in zip([0,1]+tenors, curveTIIE.nodes()) if t!=0]
        
        dfCurve = pd.DataFrame(data, columns=['tenor_date', 'tenor', 'curve_rate', 'discount_factor','code_maturity'])
        dfCurve.insert(0, 'curve_name', str_curvename)
        dfCurve.insert(0, 'date_reference', dt)
        
        dfCurve['business_day'] = dfCurve['tenor_date'].apply(lambda x: ql.Mexico().businessDaysBetween(today, ql.Date.from_date(x)))
        
        #%%  
        str_sql = "DELETE FROM [risk].[interest_rate_curve] "+ \
                  "WHERE curve_name = '{}' AND date_reference = '{:%Y-%m-%d}' ".format(str_curvename, dt)
        connection.execute(str_sql)
        
        dfCurve.to_sql("interest_rate_curve", connection, schema='risk', if_exists='append', index=False)
        print('{} - Inserted {} values for date {} : TABLE interest_rate_curve'.format(str_curvename, len(dfCurve), dt))
        #%%
        if debug:
            db_yts = ql.RelinkableYieldTermStructureHandle()
            db_yts.linkTo(cdb.get_curve(dt, str_curvename))
            
            for t in tenors:
                tenor_period = ql.Period('{}W'.format(t*4))
                ind = 'MXN TIIE {:1.0f}x1'.format(t)
                rt = df.loc[ind, 'rate'] / 100
                mxn_swap = MxnSwap.MxnTiieSwap(ql.Swap.Payer,
                                               100,
                                               settle_date,
                                               ql.Mexico().advance(settle_date, tenor_period), 
                                               rt, 
                                               tiie_index)
                
                mxn_swap.setPricingEngine(ql.DiscountingSwapEngine(db_yts))
                print(f"{t:4}:\t{mxn_swap.fairRate()*100:.4f}\t{rt*100:.4f}")               
            
        
        #%%        
    else:
        print('Feriado no México!')
    
#%%    
if __name__ == "__main__":
    
    dt = datetime.date(2022, 5, 30)
    main(dt, True)
    
    # dtIni = ql.Date(1,5,2022)
    # dtIni = ql.Mexico().adjust(dtIni)
    # while dtIni<= ql.Date(24, 5, 2022):    
    #     main(dtIni.to_date())
    #     dtIni = ql.Mexico().advance(dtIni, ql.Period(1, ql.Days))

