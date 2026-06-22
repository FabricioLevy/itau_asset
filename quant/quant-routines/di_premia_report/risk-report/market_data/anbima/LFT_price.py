import datetime
import pandas as pd

from a1db.a1sql import SQLConnection

import os, sys
path_github = os.path.expanduser('~\\Documents\\Github')
sys.path.insert(1, path_github + '\\market_data')
import checks

#%%
def main(dt):
    #%%
    connection = SQLConnection().get_connection()
            
    str_sql = "SELECT t.[date_reference], Cast(t.[data_vencimento] as datetime) as date_maturity, "+\
                "t.[taxa_indicativa]/100 as rate, t.[PU] as price, t.[data_emissao] as date_issue " +\
                " FROM [anbima].taxa_titulo_publico t " +\
                " WHERE t.titulo = 'LFT' AND t.[date_reference] = '{:%Y-%m-%d}'".format(dt)
    df = pd.read_sql(str_sql, connection)
    df.sort_values('date_maturity', inplace=True)
    
    str_sql = "SELECT [id] as product_id, Cast([date_maturity] as datetime) as date_maturity FROM [middle].[product] " +\
                "WHERE product_type = 'LFT' AND date_maturity >= '{:%Y-%m-%d}'".format(dt)
    dfProduct = pd.read_sql(str_sql, connection, index_col='date_maturity')
    
    del str_sql    
    #%%
    df = df.join(dfProduct, on='date_maturity')
    df['prazo_medio'] = (df['date_maturity'].dt.date - dt).dt.days
    df['product_id'] = df['product_id'].fillna('LFT ' + df['date_maturity'].dt.strftime('%d/%m/%Y'))
    df['lote45_product'] = 'LFT' + df['date_maturity'].dt.strftime('%d%m%Y')
    
    #%%
    missing_ids = checks.check_missing_product(connection, list(df['product_id'].values), dt)
    for id_new in missing_ids:
        str_sql = """
                     INSERT INTO [middle].[product] 
                	        ([id],[product_type],[lote45_product],
                            [lote45_product_class],[description],[product_currency],
                            [date_maturity],[bloomberg_update], product_category, onshore_risk)
                         VALUES ('{0}', 'LFT', '{1}',
                		'LFT', 'LFT {2:%B%Y}', 'BRL',
                		'{2:%Y-%m-%d}', 0, 'LFT', 1)
                 """
        str_sql = str_sql.format(
                                 id_new,
                                 df.loc[df['product_id']==id_new,'lote45_product'].item(),
                                 df.loc[df['product_id']==id_new,'date_maturity'].dt.date.item()
                                )
        connection.execute(str_sql)
        print('LFT - Inserted New product: {}'.format(id_new))
    
    #%%    
    str_sql = "DELETE price FROM [middle].[product_price] price "+\
                "INNER JOIN [middle].[product] prod "+\
                "ON price.product_id = prod.id "+\
                "WHERE prod.product_type='LFT' AND "+\
                "price.date_reference = '{:%Y-%m-%d}' ".format(dt)
    connection.execute(str_sql)    
    df[['date_reference','product_id','rate','price']].\
        to_sql("product_price", connection, schema='middle', if_exists='append', index=False)
    print('LFT - Inserted {} values for date {} : TABLE product_price'.format(len(df), dt))
    
    str_sql = "DELETE s FROM [risk].[product_sensitivity] s "+\
                "INNER JOIN [middle].[product] prod "+\
                "ON s.product_id = prod.id "+\
                "WHERE prod.[product_type]='LFT' AND "+\
                "s.date_reference = '{:%Y-%m-%d}' ".format(dt)
    connection.execute(str_sql)    
    
    dfPrazoMedio =  df[['date_reference','product_id','prazo_medio']].copy()
    dfPrazoMedio.rename({'prazo_medio':'value'}, axis=1,inplace=True)
    dfPrazoMedio['sensitivity'] = 'prazo_medio'
    dfPrazoMedio.to_sql("product_sensitivity", connection, schema='risk', if_exists='append', index=False)
    print('LFT - Inserted {} values for date {} : TABLE product_sensitivity - Prazo Médio'.format(len(df), dt))
    
    
#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 11, 17)
    main(dt)
