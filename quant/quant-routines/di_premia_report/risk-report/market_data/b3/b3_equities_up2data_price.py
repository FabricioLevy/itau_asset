import pandas as pd
import datetime

from a1db.a1sql import SQLConnection

#%%
def main(dt):
#%%
    connection = SQLConnection().get_connection()
    
    str_sql = """
                SELECT [ReportDate] AS 'date_reference'
                      ,[TickerSymbol] AS 'product_id'
                      ,[LastPrice] AS 'rate'
                      ,[LastPrice] AS 'price'
                  FROM [up2data].[Equities_EODPriceFile] AS up2_price
                  INNER JOIN
                  [middle].[product] AS prod
                  ON [TickerSymbol] = [id]
                WHERE [ReportDate] = '{:%Y-%m-%d}'
              """.format(dt)
    df = pd.read_sql(str_sql, connection)
    
    del str_sql    
    #%%
    str_sql = "DELETE price FROM [middle].[product_price] price "+\
                "INNER JOIN [middle].[product] prod "+\
                "ON price.product_id = prod.id "+\
                "WHERE prod.[lote45_product_class]='Equity' AND "+\
                "price.date_reference = '{:%Y-%m-%d}' ".format(dt)
    connection.execute(str_sql)
    
    dfProductPrice = df[['date_reference', 'product_id', 'rate', 'price']]
    #%%
#     missing_ids = checks.check_missing_product(connection, list(dfProductPrice['product_id'].values), dt)
#     for id_new in missing_ids:
#         str_sql = """
#          INSERT INTO [middle].[product] 
# 	        ([id],[product_type],[lote45_product],
#             [lote45_product_class],[description],[product_currency],
#            [date_maturity],[bloomberg_update])
#          VALUES ('{0}', 'DI1Future', '{0}',
# 		'DI1Future', 'DI1 {1:%b%Y}', 'BRL',
# 		'{1:%Y-%m-%d}', 0)
#          """
#         str_sql = str_sql.format(id_new, df.loc[df['product_id']==id_new,'maturity_date'].item())
#         connection.execute(str_sql)
#         print('DI1Future - Inserted New product: {}'.format(id_new))
    #%%
    dfProductPrice.to_sql("product_price", connection, schema='middle', if_exists='append', index=False)
    print('Equities - Inserted {} values from UP2DATA for date {} : TABLE product_price'.format(len(dfProductPrice), dt))
 

#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 3, 9)
    main(dt)