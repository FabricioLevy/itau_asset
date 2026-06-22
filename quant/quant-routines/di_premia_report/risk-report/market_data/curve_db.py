import pandas as pd
import datetime
import QuantLib as ql
from types import MethodType

from a1db.a1sql import SQLConnection


#%%
def get_curve(dt, curve_name):
    
    connection = SQLConnection().get_connection()
    str_sql = """
                SELECT [tenor_date],[curve_rate],[discount_factor]
                FROM [risk].[interest_rate_curve]
                WHERE (tenor is null)
                    AND date_reference = '{:%Y-%m-%d}'
                    AND curve_name = '{}'
                    ORDER BY tenor_date
              """
    str_sql = str_sql.format(dt, curve_name)
    dfCurve = pd.read_sql(str_sql, connection)
    
    str_sql = """
                SELECT [curve_type],[calendar],[day_count],[interpolation],[compounding],[frequency]
                FROM [risk].[curve_setting]
                WHERE curve_name = '{}'
              """
    str_sql = str_sql.format(curve_name)
    dfSettings = pd.read_sql(str_sql, connection)    
    
    del str_sql
    
    if len(dfSettings) == 0:
        raise Exception("Error: there is no settings for curve '{}'".format(curve_name))
    if len(dfCurve) == 0:
        raise Exception("Error: there is no curve '{}' for date {:%Y-%m-%d}".format(curve_name, dt))
    
    today = ql.Date.from_date(dt)
    data = dfCurve.values
    dts = [today] + [ql.Date.from_date(i) for i in data[:,0]]
    rts = [data[0,1]] + list(data[:,1])
    dfs = [1] + list(data[:,2])
    
    dic_Settings = dfSettings.iloc[0].to_dict()
    day_count = getattr(ql, dic_Settings['day_count'])()
    calendar = getattr(ql, dic_Settings['calendar'])()
    interpolation = getattr(ql, dic_Settings['interpolation'])()
        #compounding is an attribute, not a method
    compounding = getattr(ql, dic_Settings['compounding'])

    if dic_Settings['curve_type'] == 'DiscountCurve':
       crv = ql.DiscountCurve(dts, dfs, day_count, calendar)
    elif dic_Settings['curve_type'] == 'ZeroCurve':
        crv = ql.ZeroCurve(dts, rts, day_count, calendar, interpolation, compounding)
    elif dic_Settings['curve_type'] ==  'CubicZeroCurve':
        crv = ql.CubicZeroCurve(dts, rts, day_count, calendar)
    else:
        raise Exception("Error: there is no action for curve type '{}'".format(dic_Settings['curve_type']))

    def zeroRateValue(self, dt):
        if type(dt) in [datetime.date, datetime.datetime]:
            dt=ql.Date.from_date(dt)
        return self.zeroRate(dt, day_count, compounding).rate() 
    def forwardRateValue(self, dt1, dt2):
        if type(dt1) in [datetime.date, datetime.datetime]:
            dt1=ql.Date.from_date(dt1)
        if type(dt2) in [datetime.date, datetime.datetime]:
            dt2=ql.Date.from_date(dt2)   
        return self.forwardRate(dt1, dt2, day_count, compounding).rate()
    
    crv.zeroRateValue = MethodType(zeroRateValue, crv)
    crv.forwardRateValue = MethodType(forwardRateValue, crv)
    
    return crv

#%%
def get_curveShifted(dtShift, curve_name, base_curve):
  
    connection = SQLConnection().get_connection()

    dtRef = ql.Date.from_date(dtShift)
    calendar = base_curve.calendar()
    day_count = base_curve.dayCounter()
    dtRefD1 = calendar.advance(dtRef, ql.Period('-1d'))
    str_sql = """
                SELECT [date_reference],[tenor_date],[tenor],[curve_rate],[discount_factor],[business_day]
                FROM [risk].[interest_rate_curve]
                WHERE date_reference in ('{:%Y-%m-%d}','{:%Y-%m-%d}') 
                AND curve_name = '{}' and tenor is not null
              """
    str_sql = str_sql.format(dtRef.to_date(), dtRefD1.to_date(), curve_name)
    dfCurve = pd.read_sql(str_sql, connection)
    
    del connection, str_sql
    
    dfSpread = dfCurve.pivot(index='tenor', columns='date_reference', values='curve_rate')
    dfSpread['shift'] = dfSpread[dtRef.to_date()] - dfSpread[dtRefD1.to_date()] 
    dfSpread = dfSpread.join(dfCurve[dfCurve['date_reference']==dtRef.to_date()][['tenor','business_day']].set_index('tenor'))
    
    today = base_curve.referenceDate()
    dts = [calendar.advance(today, ql.Period(i,ql.Days)) for i in dfSpread['business_day']]
    shifts = [ql.QuoteHandle(ql.SimpleQuote(i)) for i in dfSpread['shift']]
    
    base_curve_handle = ql.YieldTermStructureHandle(base_curve)
    base_curve_shifted = ql.SpreadedLinearZeroInterpolatedTermStructure(base_curve_handle, shifts, dts)
    
    from types import MethodType
    def zeroRateValue(self, dt):
        if type(dt) in [datetime.date, datetime.datetime]:
            dt=ql.Date.from_date(dt)
        return self.zeroRate(dt, day_count, ql.Compounded).rate() 
    def forwardRateValue(self, dt1, dt2):
        if type(dt1) in [datetime.date, datetime.datetime]:
            dt1=ql.Date.from_date(dt1)
        if type(dt2) in [datetime.date, datetime.datetime]:
            dt2=ql.Date.from_date(dt2)   
        return self.forwardRate(dt1, dt2, day_count, ql.Compounded).rate()
    
    base_curve_shifted.zeroRateValue = MethodType(zeroRateValue, base_curve_shifted)
    base_curve_shifted.forwardRateValue = MethodType(forwardRateValue, base_curve_shifted)
    
    return base_curve_shifted

#%%
def get_price(dt, product_id):
    
    connection = SQLConnection().get_connection() 

    if type(dt) == list:
        str_dt = ','.join(["'{:%Y-%m-%d}'".format(i) for i in dt])
    else:
        str_dt = "'{:%Y-%m-%d}'".format(dt)

    str_sql = """
                SELECT date_reference, price, rate
                FROM [middle].[product_price]
                WHERE product_id = '{}' AND date_reference in ({})
              """
    str_sql = str_sql.format(product_id, str_dt)
    df = pd.read_sql(str_sql, connection, index_col='date_reference')    
    connection.close()
    if len(df) == 0:
        raise Exception("Error: there is no '{}' for date {}".format(product_id, str_dt))
    else:
        return df.loc[dt,'price']
    
#%%
def get_series(dt, product_id):
    
    connection = SQLConnection().get_connection()
    
    str_sql = """
        SELECT [date_reference], [value] as '{0:}'
        FROM [quant].[time_series_value] tsv INNER JOIN quant.time_series ts ON tsv.series_id = ts.id
        WHERE entity_id = '{0:}' and date_reference >= '{1:%Y-%m-%d}'
              """
    str_sql = str_sql.format(product_id, dt)
    df = pd.read_sql(str_sql, connection, index_col='date_reference')    
   
    if len(df) == 0:
        raise Exception("Error: there is no '{}' for date {}".format(product_id, dt))
    else:
        return df
       
    
#%%
if __name__ == "__main__":
    
    dtShift = datetime.date(2021, 6, 9)
    dt = datetime.date(2021, 6, 9)
    curve_name = 'LTN'
    

    base_curve = get_curve(dt, curve_name)    
    curve_shifted = get_curveShifted(dtShift, curve_name, base_curve)
    
    #%%
    for (i, _) in base_curve.nodes():
        tx_1 = base_curve.zeroRateValue(i)
        tx_2 = curve_shifted.zeroRateValue(i)
        print('{:%d-%b-%Y} - Base: {:2.2%}  Shifted: {:2.2%}  Diff: {:2.1f}'.format(i.to_date(), tx_1, tx_2, (tx_2-tx_1)*10000))
    
    #%%
    dt1 = datetime.date(2017, 8, 25)
    dt2 = datetime.date(2017, 8, 28)
    c1 = get_curve(dt1, curve_name) 
    c2 = get_curve(dt2, curve_name) 
    c1.enableExtrapolation()
    c2.enableExtrapolation()
    for (i, _) in c2.nodes():
        tx_1 = c1.zeroRateValue(i)
        tx_2 = c2.zeroRateValue(i)
        print('{:%d-%b-%Y} - c1: {:2.2%}  c2: {:2.2%}  Diff: {:2.1f}'.format(i.to_date(), tx_1, tx_2, (tx_2-tx_1)*10000))
    
    
    
    #%%
    # for y in [2021, 2022, 2023]:
    #     dt_ini = ql.Date(1,1,y)
    #     dt_end = ql.Date(31,12,y)
    #     r=c_d0.forwardRateValue(dt_ini, dt_end)
    #     print('{:1.0f} : {:2.2%}'.format(y, r))
    
    # #%%
    # for (i, _) in c_d0.nodes():
    #     tx_d0 = c_d0.zeroRateValue(i)
    #     tx_d1 = c_d1.forwardRateValue(today, i)
    #     print('{:%d-%b-%Y} - D0: {:2.2%}  D-1: {:2.2%}  Diff: {:2.1f}'.format(i.to_date(), tx_d0, tx_d1, (tx_d0-tx_d1)*10000))