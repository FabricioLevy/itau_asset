import pandas as pd
import numpy as np
import datetime
import QuantLib as ql

from a1db.a1sql import SQLConnection

#%%
def main(dt):
#%%
    today = ql.Date.from_date(dt)
    str_curvename = 'ED Fut'
 
    connection = SQLConnection().get_connection()
    str_sql = f"""
               SELECT [id],[date_maturity],pp.price,pp.rate
               FROM [middle].[product] p 
                   INNER JOIN middle.product_price pp ON p.id = pp.product_id
               WHERE product_type = 'Eurodollar Futures' and
               date_reference = '{dt:%Y-%m-%d}'
               ORDER BY date_maturity
              """
    df = pd.read_sql(str_sql, connection)
     
    del str_sql    
#%%
    ql.Settings.instance().evaluationDate = today
    
    # index = ql.Euribor3M()
    lengthInMonths = 3
    calendar = ql.UnitedStates()
    convention = ql.Following
    endOfMonth = False
    dayCounter = ql.Actual360()
   
    helpers = []
    tenors = []
        
    for code, exp_dt, price, rate in df.values:
        iborStartDate = ql.Date.from_date(exp_dt)
        tenors.append(code)
        h = ql.FuturesRateHelper(price, 
                                 iborStartDate, 
                                 lengthInMonths, 
                                 calendar, 
                                 convention, 
                                 endOfMonth, 
                                 dayCounter, 
                                 0.0,
                                 ql.Futures.IMM)
        helpers.append(h)

#%%
    curve_edfut = ql.PiecewiseCubicZero(today, helpers, ql.Actual360())
    # PiecewiseLinearZero
    #PiecewiseFlatForward
    # PiecewiseLogCubicDiscount
    curve_edfut.enableExtrapolation()
 
    buckets = [1, 30, 60, 90, 180, 270, 360, 540, 720, 900] + [i*360 for i in range(3,11)]
        
    data=[(ql.UnitedStates().adjust(today+i).to_date(), i, 
               curve_edfut.zeroRate(today+i, ql.Actual360(), ql.Compounded, ql.Annual).rate(), 
               curve_edfut.discount(today+i), np.nan) for i in buckets]
        

    data+=[(ql.UnitedStates().adjust(dt_i).to_date(), np.nan, 
               curve_edfut.zeroRate(dt_i, ql.Actual360(), ql.Compounded, ql.Annual).rate(), 
               curve_edfut.discount(dt_i), t) 
               for (t, (dt_i, _)) in zip([0]+tenors, curve_edfut.nodes()) if t!=0]

        
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
    
    dt = datetime.date(2022, 8, 5)
    main(dt)
    
    # dtIni = ql.Date(2,3,2022)
    # dtIni = ql.UnitedStates().adjust(dtIni)
    # while dtIni<= ql.Date(1, 4, 2022):    
    #     main(dtIni.to_date())
    #     dtIni = ql.UnitedStates().advance(dtIni, ql.Period(1, ql.Days))
    
