import pandas as pd
import datetime

from a1db.a1sql import SQLConnection

#%%
def get_volumes(dt):
    #%%
    connection = SQLConnection().get_connection()
    
    str_sql = """
                DECLARE @date_query AS DATETIME = '{:%Y-%m-%d}'
                SELECT [date_reference]
                        ,[product_id]
                        ,[sensitivity]
                        ,[value]
                FROM (SELECT [ReportDate] AS 'date_reference'
                        ,[TickerSymbol] AS 'product_id'
                        ,'ctos_aberto' AS 'sensitivity'
                        ,[OpenInterest] AS 'value'
                    FROM [up2data].[Currency_OpenPositionFile]
                    WHERE [ReportDate] = @date_query
                UNION
                SELECT [ReportDate] AS 'date_reference'
                        ,[TickerSymbol] AS 'product_id'
                        ,'ctos_aberto' AS 'sensitivity'
                        ,[OpenInterest] AS 'value'
                    FROM [up2data].[Equities_Indexes_OpenPositionFile]
                    WHERE [ReportDate] = @date_query
                UNION
                SELECT [ReportDate] AS 'date_reference'
                        ,[TickerSymbol] AS 'product_id'
                        ,'ctos_aberto' AS 'sensitivity'
                        ,[OpenInterest] AS 'value'
                    FROM [up2data].[Interest_Rate_OpenPositionFile]
                    WHERE [ReportDate] = @date_query) AS prod_open
                INNER JOIN [middle].[product] AS prod
                ON prod_open.[product_id] = prod.[id]
                ORDER BY 2
              """.format(dt)
    df = pd.read_sql(str_sql, connection)
    
    del str_sql
    #%%
    str_sql = """
                DELETE prod_sens
                	FROM [risk].[product_sensitivity] prod_sens
                	INNER JOIN [middle].[product] prod
                	ON prod_sens.[product_id] = prod.[id]
                	WHERE prod.[lote45_product_class] IN ('SCS','DI1Future','DDI Future','DAP Future','USDBRLFuture','IBOVSPFuture')
                	AND prod_sens.[sensitivity] = ('ctos_aberto')
                	AND prod_sens.[date_reference] = '{:%Y-%m-%d}'
              """.format(dt)
    connection.execute(str_sql)
    
    #%%
    df.to_sql("product_sensitivity", connection, schema='risk', if_exists='append', index=False)
    print("\nOpen Contracts' numbers of SCS, DI1Future, DDI Future, DAP Future, USDBRLFuture, IBOVSPFuture - Inserted {} values from UP2DATA for date {} : TABLE product_sensitivity\n".format(len(df), dt))

    
#%%
if __name__ == "__main__":

    dt = datetime.date(2022, 3, 9)
    get_volumes(dt)

    # import time
    # while int(datetime.datetime.now().strftime('%H')) < 999:
    #     time.sleep(600)

    #     for x in range(1,32):
    #         dt = datetime.date(2021, 5, x)
    #         get_volumes(dt)

#%%