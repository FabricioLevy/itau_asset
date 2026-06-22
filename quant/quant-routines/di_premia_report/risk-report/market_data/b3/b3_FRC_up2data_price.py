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
                SELECT interest_reate_price.[ReportDate] AS 'date_reference'
                      ,interest_reate_price.[TickerSymbol] AS 'product_id'
                	  ,interest_reate_instrument.[Asset] AS 'product_class'
                      ,interest_reate_price.[ExpirationDate] AS 'maturity_date'
                      ,interest_reate_price.[AdjustedQuoteTax] AS 'price'
                      ,interest_reate_price.[AdjustedQuoteTax] AS 'rate'
                  FROM [up2data].[Interest_Rate_EOD_SettlementPriceFile_StructuredOperations] interest_reate_price
                	INNER JOIN
                	[up2data].[Interest_Rate_StructuredOperationInstrumentFile] interest_reate_instrument
                	ON interest_reate_price.[ReportDate] = interest_reate_instrument.[ReportDate]
                	AND interest_reate_price.[TickerSymbol] = interest_reate_instrument.[TickerSymbol]
                		WHERE interest_reate_instrument.[Asset] = 'FRC'
                		AND interest_reate_price.[ReportDate] = '{:%Y-%m-%d}'
					ORDER BY [maturity_date]
              """.format(dt)
    df = pd.read_sql(str_sql, connection)
    
    del str_sql
    #%%
    str_sql = "DELETE price FROM [middle].[product_price] price "+\
                "INNER JOIN [middle].[product] prod "+\
                "ON price.product_id = prod.id "+\
                "WHERE prod.[lote45_product_class]='FRC' AND "+\
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
         VALUES ('{0}', 'FRC', '{0}',
		'FRC', 'FRC {1:%B%Y}', 'USD',
		'{1:%Y-%m-%d}', 0)
         """
        str_sql = str_sql.format(id_new, df.loc[df['product_id']==id_new,'maturity_date'].item())
        connection.execute(str_sql)
        print('FRC - Inserted New product: {}'.format(id_new))
    #%%
    dfProductPrice.to_sql("product_price", connection, schema='middle', if_exists='append', index=False)
    print('FRC - Inserted {} values from UP2DATA for date {} : TABLE product_price'.format(len(dfProductPrice), dt))

    
#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 3, 9)
    main(dt)
        
    # dtIni = ql.Date(1,1,2020)
    # dtIni = ql.Brazil(ql.Brazil().Exchange).adjust(dtIni)
    # while dtIni<= ql.Date(8, 12, 2020):  
    #     print(dtIni)
    #     main(dtIni.to_date())
    #     dtIni = ql.Brazil(ql.Brazil().Exchange).advance(dtIni, ql.Period(1, ql.Days))
