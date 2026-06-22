import pandas as pd
import datetime

from a1db.a1sql import SQLConnection


#%%
def main(dt):
#%%
    connection = SQLConnection().get_connection()
    
    str_sql = """
                SELECT [ReportDate] AS 'date_reference'
                      ,[PriceValue] AS 'price'
                      ,[PriceValue] AS 'rate'
                  FROM [up2data].[Economic_Indicator_EconomicIndicatorFile]
                  WHERE [TickerSymbol] = 'IDI-09'
                  AND [ReportDate] = '{:%Y-%m-%d}'
              """.format(dt)
    df = pd.read_sql(str_sql, connection)
    
    del str_sql
    
    #%%
    df['product_id'] = 'IDIX9'
    
    #%%
    str_sql = """
                DELETE FROM [middle].[product_price]
                    WHERE [product_id] = 'IDIX9'
                    AND [date_reference] = '{:%Y-%m-%d}'
              """.format(dt)
    connection.execute(str_sql)

    #%%
    df.to_sql("product_price", connection, schema='middle', if_exists='append', index=False)
    print('IDI-09 - Inserted {} value from UP2DATA for date {} : TABLE product_price'.format(len(df), dt))
    

#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 3, 9)
    main(dt)
    
    # while dt > datetime.date(2021, 3, 16):
    #     main(dt)
    #     dt = ql.Brazil(ql.Brazil().Exchange).advance(ql.Date.from_date(dt),ql.Period('-1d')).to_date()