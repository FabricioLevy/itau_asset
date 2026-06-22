import pandas as pd
import datetime
import QuantLib as ql

from a1db.a1sql import SQLConnection

import os, sys
path_github = os.path.expanduser('~\\Documents\\Github')
sys.path.insert(1, path_github + '\\market_data')
import checks

#%%
def main(dt):
    #%%
    connection = SQLConnection().get_connection()
        
    str_sql = """
                SELECT [date_reference]
                      ,REPLACE(LOWER([month_strike]),'jly','jul') as 'month_strike'
                      ,[sett_price] as 'price'
                  FROM [cme].[daily_settlement]
                  WHERE [product] = 'ED'
                  AND [date_reference] = '{:%Y-%m-%d}'
              """.format(dt)
    df = pd.read_sql(str_sql, connection)
    if len(df) == 0:
        raise RuntimeError
    del str_sql
    
    #%%
    month_code = ['F','G','H','J','K','M','N','Q','U','V','X','Z']
    df['temp_datetime'] = df['month_strike'].apply(lambda x: datetime.datetime.strptime(x,'%b%y'))
    df = df.loc[df['temp_datetime'].dt.year<dt.year+10]
    df['temp_code'] = df['temp_datetime'].apply(lambda x: f"{month_code[x.month-1]}{x.year%10:1d}")
    
    df['product_id'] = df['temp_datetime'].apply(lambda x: f"ED{month_code[x.month-1]}{x.year%100:1d}")
    df['lote45_product'] = 'ED' + df['temp_code']
    df['maturity_date'] = df['temp_code'].apply(lambda x: ql.IMM.date(x, ql.Date.from_date(dt)).to_date())
    df['rate'] = (100 - df['price']) / 100 
  
    df.sort_values('maturity_date', inplace=True)
    
    #%%
    str_sql = """
                DELETE price FROM [middle].[product_price] price
                    INNER JOIN [middle].[product] prod
                    ON price.product_id = prod.id
                    WHERE prod.[lote45_product_class] = 'Eurodollar Futures' AND
                    price.date_reference = '{:%Y-%m-%d}'
              """.format(dt)
    connection.execute(str_sql)
    
    dfProductPrice = df[['date_reference', 'product_id', 'rate' ,'price']]
    
    #%%
    missing_ids = checks.check_missing_product(connection, list(dfProductPrice['product_id'].values), dt)
    
    for id_new in missing_ids:
        str_sql = """
                     INSERT INTO [middle].[product] 
                	        ([id],[product_type],[lote45_product],
                            [lote45_product_class],[description],[product_currency],
                            [date_maturity],[bloomberg_update])
                         VALUES ('{0}', 'Eurodollar Futures', '{1}',
                		'Eurodollar Futures', 'ED {2:%B%Y}', 'USD',
                		'{2:%Y-%m-%d}', 0)
                 """
        str_sql = str_sql.format(
                                 id_new,
                                 df.loc[df['product_id']==id_new,'lote45_product'].item(),
                                 df.loc[df['product_id']==id_new,'maturity_date'].item()
                                )
        connection.execute(str_sql)
        
        print('Eurodollar Futures - Inserted New product: {}'.format(id_new))
    #%%
    dfProductPrice.to_sql("product_price", connection, schema='middle', if_exists='append', index=False)
    print('CME ED Futures - Inserted {} values for date {} : TABLE product_price'.format(len(dfProductPrice), dt))

#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 4, 5)
    main(dt)
    
