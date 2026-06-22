import pandas as pd
import numpy as np
import datetime
import QuantLib as ql

from a1db.a1sql import SQLConnection

#%%
def main(dt):
#%%
    today = ql.Date.from_date(dt)
    str_curvename = 'FF Fut'
 
    connection = SQLConnection().get_connection()
    str_sql = f"""
               SELECT [id], [date_maturity], pp.price, pp.rate
               FROM [middle].[product] p 
                   INNER JOIN middle.product_price pp ON p.id = pp.product_id
               WHERE product_type = 'FF Futures' and
                   date_reference = '{dt:%Y-%m-%d}'
               ORDER BY date_maturity
              """
    df = pd.read_sql(str_sql, 
                     connection,
                     index_col='id')
    
    str_sql = f"""
                SELECT [date_reference],[value] as FF
                    FROM [quant].[time_series_value] tsv
                      INNER JOIN [quant].[time_series] ts ON tsv.series_id = ts.id
                    WHERE ts.entity_id = 'FedFundRate'
                        AND date_reference BETWEEN '{datetime.date(dt.year, dt.month, 1):%Y-%m-%d}'
                                           AND '{dt:%Y-%m-%d}'
                    ORDER BY date_reference
                """
    dfFF_fixing = pd.read_sql(str_sql,
                              connection,
                              index_col='date_reference')
    
    str_sql = f"""
                SELECT date_effective
                FROM [research].[monetary_policy_meeting]
                WHERE country = 'USD'
                    and date_effective >= '{datetime.date(dt.year, dt.month, 1):%Y-%m-%d}'
                ORDER BY date_effective
                """
    dates_FOMC = list(pd.read_sql(str_sql, connection)['date_effective'])
    
    del str_sql    
#%%
    ql.Settings.instance().evaluationDate = today
    index = ql.FedFunds() 
    index.clearFixings()
    index.addFixings([ql.Date.from_date(i) for i in dfFF_fixing.index], 
                     dfFF_fixing['FF'].values/100)
    
    calendar = index.fixingCalendar()
    df['date_start'] = df['date_maturity'].apply(lambda x: calendar.adjust(ql.Date(1, x.month, x.year)).to_date())
        
    next_fomc = dates_FOMC[0]
    
    current_month = []    
    d = calendar.adjust(ql.Date(1, dt.month, dt.year))
    while d <= calendar.endOfMonth(ql.Date(1, dt.month, dt.year)):
        current_month.append(d.to_date())
        d = calendar.advance(d, ql.Period("1d"))

    q1 = dfFF_fixing['FF'].count()
    m1 = dfFF_fixing['FF'].mean()
    q2 = len([i for i in current_month if i<next_fomc]) - q1
    m2 = dfFF_fixing['FF'].iloc[-1]
    q3 = len([i for i in current_month if i>=next_fomc])  
    m3 = (((q1+q2+q3) *df['rate'].iloc[0]*100 - q1*m1 - q2*m2) / q3) / 100
    
    curr_future = df.index[0]   
    if next_fomc < df.loc[curr_future, 'date_maturity']:
        #FOMC meets in the current month
        df.loc[curr_future, 'date_start'] = next_fomc
        df.loc[curr_future, 'rate'] = m3
        df.loc['FF_ON', 'date_start'] = dt
        df.loc['FF_ON', 'date_maturity'] = next_fomc
        df.loc['FF_ON', 'rate'] = m2 / 100
    else:
        df.loc[curr_future, 'date_start'] = dt
    
    df.sort_values(by='date_maturity', inplace=True)
#%%  
    helpers = []
    tenors = []
    
    tenors.append(curr_future)
    d = calendar.businessDaysBetween(today,
                                     ql.Date.from_date(df.loc[curr_future, 'date_start']))
    h = ql.DepositRateHelper(df.loc[curr_future, 'rate'],
                             ql.Period(d, ql.Days),
                             0,
                             calendar,
                             ql.ModifiedFollowing,
                             False,
                             ql.Actual360())
    helpers.append(h)
    
        
    for code, (exp_dt, price, rate, start_dt) in df.iloc[1:].iterrows():
        tenors.append(code)
        h = ql.DatedOISRateHelper(ql.Date.from_date(start_dt),
                                  ql.Date.from_date(exp_dt),
                                  ql.QuoteHandle(ql.SimpleQuote(rate)),
                                  index)
        helpers.append(h)

#%%
    curve_fffut = ql.PiecewiseCubicZero(today, helpers, ql.Actual360())
    curve_fffut.enableExtrapolation()
 
    buckets = [1, 30, 60, 90, 180, 270, 360, 540, 720, 900] + [i*360 for i in range(3,21)]
    
        
    data=[(ql.UnitedStates().adjust(today+i).to_date(), i, 
               curve_fffut.zeroRate(today+i, ql.Actual360(), ql.Compounded, ql.Annual).rate(), 
               curve_fffut.discount(today+i), np.nan) for i in buckets]
        

    data+=[(ql.UnitedStates().adjust(dt_i).to_date(), np.nan, 
               curve_fffut.zeroRate(dt_i, ql.Actual360(), ql.Compounded, ql.Annual).rate(), 
               curve_fffut.discount(dt_i), t) 
               for (t, (dt_i, _)) in zip([0]+tenors, curve_fffut.nodes()) if t!=0]

        
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
    
    dt = datetime.date(2022, 3, 17)
    main(dt)
    