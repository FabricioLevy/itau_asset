import pandas as pd
import datetime
 
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
                SELECT future_price.[ReportDate] AS 'date_reference'
                      ,future_price.[TickerSymbol] AS 'product_id'
                	  ,future_instrument.[Asset] AS 'product_class'
                      ,future_price.[ExpirationDate] AS 'maturity_date'
                      ,future_price.[AdjustedQuote] AS 'price'
                      ,future_price.[AdjustedQuote] AS 'rate'
                  FROM [up2data].[Currency_EOD_SettlementPriceFile_Futures] future_price
                	INNER JOIN
                	[up2data].[Currency_FutureContractsInstrumentFile] future_instrument
                	ON future_price.[ReportDate] = future_instrument.[ReportDate]
                	AND future_price.[TickerSymbol] = future_instrument.[TickerSymbol]
                		WHERE future_instrument.[Asset] IN ('DOL','WDO')
                		AND future_price.[ReportDate] = '{:%Y-%m-%d}'
				   ORDER BY [maturity_date]
              """
    str_sql = str_sql.format(dt)
    df = pd.read_sql(str_sql, connection)
    
    del str_sql
    #%%
    str_sql = "DELETE price FROM [middle].[product_price] price "+\
                "INNER JOIN [middle].[product] prod "+\
                "ON price.product_id = prod.id "+\
                "WHERE prod.[lote45_product_class]='USDBRLFuture' AND "+\
                "price.date_reference = '{:%Y-%m-%d}' ".format(dt)
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
         VALUES ('{0}', 'FX Future', '{0}',
		'USDBRLFuture', 'DOL {1:%B%Y}', 'BRL',
		'{1:%Y-%m-%d}', 0)
         """
        str_sql = str_sql.format(id_new, df.loc[df['product_id']==id_new,'maturity_date'].item())
        try:
            connection.execute(str_sql)
            print('DOL Fut - Inserted New product: {}'.format(id_new))
        except:
            print('DOL Fut - Product not inserted: {}'.format(id_new))

    #%%
    dfProductPrice.to_sql("product_price", connection, schema='middle', if_exists='append', index=False)
    print('DOL Fut - Inserted {} values from UP2DATA for date {} : TABLE product_price'.format(len(dfProductPrice), dt))
    
    
#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 3, 9)
    main(dt)
    
    # dtIni = ql.Date(1,1,2007)
    # dtIni = ql.Brazil(ql.Brazil().Exchange).adjust(dtIni)
    # while dtIni<= ql.Date(1, 1, 2008):  
    #     print(dtIni)
    #     main(dtIni.to_date())
    #     dtIni = ql.Brazil(ql.Brazil().Exchange).advance(dtIni, ql.Period(1, ql.Days))
   