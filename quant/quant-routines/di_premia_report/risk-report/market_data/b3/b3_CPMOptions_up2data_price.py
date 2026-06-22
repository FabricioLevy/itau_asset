import pandas as pd
import datetime

from a1db.a1sql import SQLConnection

import os, sys
str_onedrive = ''#'\\OneDrive' if os.path.exists(os.path.expanduser('~\\OneDrive')) else ''
path_github = os.path.expanduser('~{}\\Documents\\Github'.format(str_onedrive))
sys.path.insert(1, path_github + '\\market_data')
import checks

#%%
def main(dt):
    #%%
    connection = SQLConnection().get_connection()
        
    str_sql = """
                SELECT [ReportDate] AS 'date_reference'
                      ,('CPM' + [ExpirationCode]) AS 'id'
                      ,LEFT([OptionStyle],1) AS 'option_style'
                      ,LEFT([OptionType],1) AS 'option_type'
                      ,CAST([ExpirationDate] AS datetime) AS 'date_maturity'
                      ,[UnderlyingInstrument] AS 'product_underlying'
                      ,[ExercisePrice] AS 'option_strike'
                      ,[ReferencePrice] AS 'price'
                  FROM [up2data].[Interest_Rate_ReferencePriceFile]
                  WHERE [Asset] = 'CPM'
                  AND [ReportDate] = '{:%Y-%m-%d}'
              """.format(dt)
    df = pd.read_sql(str_sql, connection)
    
    del str_sql
    
    #%%
    df['lote45_product'] = df['id']
    df['lote45_product_class'] = 'CPM Options - BMF'
    df['description'] = 'CPM Option ' + df['option_type']
    df['product_type'] = 'CPM Option'
    df['product_currency'] = 'BRL'
    df['bloomberg_update'] = 0
    df['lot_size'] = 1
    
    #%%
    str_sql = """
                DELETE price FROM [middle].[product_price] price
                    INNER JOIN [middle].[product] prod
                    ON price.product_id = prod.id
                    WHERE prod.[lote45_product_class] IN ('CPM Options - BMF') AND
                    price.date_reference = '{:%Y-%m-%d}'
              """.format(dt)
    connection.execute(str_sql)
    
    dfProductPrice = df[['date_reference','id','price','price']]
    dfProductPrice.columns = ['date_reference','product_id','rate','price']
    
    #%%
    missing_ids = checks.check_missing_product(connection, list(dfProductPrice['product_id'].values), dt)
    
    for id_new in missing_ids:
        df.loc[df['id']==id_new].drop(columns = ['date_reference','price']) \
            .to_sql("product", connection, schema='middle', if_exists='append', index=False)
        print('CPM Options - Inserted New Product: {}'.format(id_new))
    
    #%%
    dfProductPrice.to_sql("product_price", connection, schema='middle', if_exists='append', index=False)
    print('CPM Options - Inserted {} values from UP2DATA for date {} : TABLE product_price'.format(len(dfProductPrice), dt))

    connection.close()
    
#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 3, 9)
    main(dt)
    
    # while dt > datetime.date(2021, 3, 16):
    #     main(dt)
    #     dt = ql.Brazil(ql.Brazil().Exchange).advance(ql.Date.from_date(dt),ql.Period('-1d')).to_date()
