import datetime
import pandas as pd
import QuantLib as ql

from a1db.a1sql import SQLConnection

import os, sys
path_github = os.path.expanduser('~\\Documents\\Github')
sys.path.insert(1, path_github + '\\market_data')
import checks


def main(dt):
    #%%
    connection = SQLConnection().get_connection()
            
    str_sql = "SELECT t.[date_reference], Cast(t.[data_vencimento] as datetime) as date_maturity, "+\
                "t.[taxa_indicativa]/100 as rate, t.[PU] as price, t.[data_emissao] as date_issue " +\
                " FROM [anbima].taxa_titulo_publico t " +\
                " WHERE t.titulo = 'LTN' AND t.[date_reference] = '{:%Y-%m-%d}'".format(dt)
    df = pd.read_sql(str_sql, connection)
    df.sort_values('date_maturity', inplace=True)
    
    str_sql = "SELECT [id] as product_id,[date_maturity] FROM [middle].[product] " +\
                "WHERE product_type = 'LTN' AND date_maturity >= '{:%Y-%m-%d}'".format(dt)
    dfProduct = pd.read_sql(str_sql, connection)
    
    del str_sql
    
    #%%
    calendar_br = ql.Brazil()
    df['adj_maturity'] = df['date_maturity'].apply(lambda x: calendar_br.adjust(ql.Date.from_date(x)).to_date())
    dfProduct['adj_maturity'] = dfProduct['date_maturity'].apply(lambda x: calendar_br.adjust(ql.Date.from_date(x)).to_date())
    dfProduct = dfProduct[['product_id', 'adj_maturity']].set_index('adj_maturity')
    df = df.join(dfProduct, on='adj_maturity', how='left')
    
    #%%
    df['product_id'] = df['product_id'].fillna('LTN ' + df['date_maturity'].dt.strftime('%d/%m/%Y'))
    df['lote45_product'] = 'LTN ' + df['date_maturity'].dt.strftime('%d/%m/%Y')
    
    #%%
    missing_ids = checks.check_missing_product(connection, list(df['product_id'].values), dt)
    for id_new in missing_ids:
        str_sql = """
                     INSERT INTO [middle].[product] 
                	        ([id],[product_type],[lote45_product],
                            [lote45_product_class],[description],[product_currency],
                            [date_maturity],[bloomberg_update])
                         VALUES ('{0}', 'LTN', '{1}',
                		'LTN', 'LTN {2:%B%Y}', 'BRL',
                		'{2:%Y-%m-%d}', 0)
                 """
        str_sql = str_sql.format(
                                 id_new,
                                 df.loc[df['product_id']==id_new,'lote45_product'].item(),
                                 df.loc[df['product_id']==id_new,'adj_maturity'].item()
                                )
        connection.execute(str_sql)
        print('LTN - Inserted New product: {}'.format(id_new))
    
    #%%
    str_sql = "DELETE price FROM [middle].[product_price] price "+\
                "INNER JOIN [middle].[product] prod "+\
                "ON price.product_id = prod.id "+\
                "WHERE prod.product_type='LTN' AND "+\
                "price.date_reference = '{:%Y-%m-%d}' ".format(dt)
    connection.execute(str_sql)    
    df[['date_reference','product_id','rate','price']].\
        to_sql("product_price", connection, schema='middle', if_exists='append', index=False)
    print('LTN - Inserted {} values for date {} : TABLE product_price'.format(len(df), dt))
    
 
#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 7, 21)
    main(dt)
    
    
    # dtIni = ql.Date(1,1,2017)
    # dtIni = ql.Brazil().adjust(dtIni)
    # while dtIni<= ql.Date(1,1,2019):  
    #     main(dtIni.to_date())
    #     dtIni = ql.Brazil().advance(dtIni, ql.Period(1, ql.Days))