import pandas as pd
import QuantLib as ql
from a1db.a1sql import SQLConnection
import curve_db as cdb

cal_b3 = ql.Brazil(ql.Brazil().Exchange)    

connection = SQLConnection().get_connection()
str_sql = """
SELECT [date_meeting],[date_effective]
  FROM [research].[monetary_policy_meeting]
  WHERE date_meeting  between '2021-11-1' and  '2022-3-9'
  order by 1
              """
df = pd.read_sql(str_sql, connection)
dts = list(df.values.flatten())
    
del str_sql
#%%
str_curve = "DI Fut"
len_dts = len(dts)
for i, dt in enumerate(dts):
    dfCurve = pd.DataFrame(columns=['date_reference','curve_name','tenor_date',
                                           'tenor','business_day','curve_rate','discount_factor'])
    qldt = ql.Date.from_date(dt)
    qldt = cal_b3.adjust(qldt)
    dt = qldt.to_date()
    print("{:1.2%}".format(i/len_dts))
    crv = cdb.get_curve(dt, str_curve)
    crv.enableExtrapolation()
    last_tenor = crv.nodes()[-1][0]
    n = cal_b3.businessDaysBetween(qldt, last_tenor)
    for business_day in range(1,n+1):
        tenor_date = cal_b3.advance(qldt, ql.Period(business_day, ql.Days))
        tenor = tenor_date - qldt
        curve_rate = crv.zeroRateValue(tenor_date)
        discount_factor =crv.discount(tenor_date)
        dfCurve.loc[business_day] = [dt, str_curve, tenor_date.to_date(), tenor, business_day, curve_rate, discount_factor]

    str_sql = "DELETE FROM [risk].[interest_rate_curve_full] "+ \
              "WHERE curve_name = '{}' AND date_reference = '{:%Y-%m-%d}' ".format(str_curve, dt)
    connection.execute(str_sql)
    
    dfCurve.to_sql("interest_rate_curve_full", connection, schema='risk', if_exists='append', index=False, chunksize=200)
    print('{} - Inserted {} values for date {} : TABLE interest_rate_curve_full'.format(str_curve, len(dfCurve), dt))
        
connection.close()