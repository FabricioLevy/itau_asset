import pandas as pd
import datetime
import QuantLib as ql
import sqlalchemy as sa

def main (dt, engine, connection):
    #%%
    str_sql = """
                SELECT DISTINCT DATEADD(day, dias_corridos, date_reference) as dt_maturity
          ,[taxa_valor]/100 as rate
      FROM [b3].[taxa_referencial]
      WHERE date_reference = '{:%Y-%m-%d}'
      and taxa_nome = 'Cupom limpo'
      order by dt_maturity
              """
    str_sql = str_sql.format(dt)
    df = pd.read_sql(str_sql, connection)
    
    #%%
    today = ql.Date.from_date(dt)
    data = df.values
    dts = [today] + [ql.Date.from_date(i) for i in data[:,0]]
    rts = [data[0,1]] + list(data[:,1])
        
    calendar_br = ql.Brazil()
    day_count = ql.Actual360()
    
    curve_CC = ql.ZeroCurve(dts, rts, day_count, calendar_br)
    curve_CC.enableExtrapolation()
    
    from types import MethodType
    def zeroRateValue(self, dt):
        return self.zeroRate(dt, ql.Actual360(), ql.Compounded).rate() 
    
    curve_CC.zeroRateValue = MethodType(zeroRateValue, curve_CC)
    
    #%%    
    dic_bucket = {1:'1D',5:'1W',30:'1M',60:'2M',90:'3M',180:'6M',\
                      270:'9M',360:'1Y',540:'1.5Y',720:'2Y',900:'2.5Y'} 
    dic_bucket.update({i*360:'{}Y'.format(i) for i in range(3,51)})
    
    data=[((today+i).to_date(), i, curve_CC.zeroRateValue(today+i), curve_CC.discount(calendar_br.adjust(today+i, ql.Following))) for i in dic_bucket.keys()]
    
    dfCurve = pd.DataFrame(data, columns=['tenor_date', 'tenor', 'curve_rate', 'discount_factor'])
    dfCurve.insert(0, 'curve_name', 'USD BR')
    dfCurve.insert(0, 'date_reference', dt)
    
    dfCurve['business_day'] = dfCurve['tenor_date'].apply(lambda x: calendar_br.businessDaysBetween(today, ql.Date.from_date(x)))
    
    #%%   
    str_sql = "DELETE FROM [risk].[interest_rate_curve] "+ \
              "WHERE curve_name = 'USD BR' AND date_reference = '{:%Y-%m-%d}' ".format(dt)
    connection.execute(str_sql)
    
    dfCurve.to_sql("interest_rate_curve", engine, schema='risk', if_exists='append', index=False)
    print('USD BR - Inserted {} values for date {} : TABLE interest_rate_curve'.format(len(dfCurve), dt))
    
        
#%%
if __name__ == "__main__":
    
    # dt = datetime.date(2020, 11, 26)
    # main(dt, True)
    engine = sa.create_engine('mssql+pyodbc://saprod:nhjmmn&^Yh%%^yhjU&@srvprod1.database.windows.net,1433/dbprod1?driver=SQL+Server+Native+Client+11.0')
    connection = engine.connect() 
    


        
    dtIni = ql.Date(8, 8, 2003)
    dtIni = ql.Brazil().adjust(dtIni)
    while dtIni<= ql.Date(8,8,2003):  
        print(dtIni)
        main(dtIni.to_date(), engine, connection)
        dtIni = ql.Brazil(ql.Brazil().Exchange).advance(dtIni, ql.Period(1, ql.Days))

