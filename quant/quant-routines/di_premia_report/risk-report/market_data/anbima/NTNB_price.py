import datetime
import pandas as pd
import QuantLib as ql
import os, sys

from a1db.a1sql import SQLConnection

path_github = os.path.expanduser('~\Documents\\Github')
sys.path.insert(1, path_github + '\\market_data')
import checks



def main(dt):
    #%%
    
    calendar_br = ql.Brazil()
    today = ql.Date.from_date(dt)
    yesterday = calendar_br.advance(today, ql.Period('-1d'))

    connection = SQLConnection().get_connection()
            
    str_sql = f"""
        SELECT v.[date_reference], Cast(t.[data_vencimento] as datetime) as date_maturity, t.[taxa_indicativa]/100 as rate, 
              t.[PU] as price, t.[data_emissao] as date_issue, v.VNA, v.indice 
                FROM [anbima].taxa_titulo_publico t INNER JOIN [anbima].VNA v 
                     ON t.[date_reference] = v.[date_reference] AND t.titulo=v.titulo 
                     AND t.[codigo_selic] = v.[codigo_selic]
                 WHERE t.titulo = 'NTN-B' AND t.[data_vencimento] <> '2023-03-15'
                 AND t.[date_reference] between  '{yesterday.to_date():%Y-%m-%d}' AND '{today.to_date():%Y-%m-%d}'
                 order by data_vencimento
                """
    df_last2d = pd.read_sql(str_sql, connection)
    df_last2d['adj_maturity'] = df_last2d['date_maturity'].apply(lambda x: calendar_br.adjust(ql.Date.from_date(x)).to_date())
    df = (df_last2d[df_last2d['date_reference']==dt].sort_values('date_maturity')).copy()
    df_yesterday = (df_last2d[df_last2d['date_reference']==yesterday.to_date()].sort_values('date_maturity')).copy()
    df_yesterday['adj_maturity'] = df_yesterday['date_maturity'].apply(lambda x: calendar_br.adjust(ql.Date.from_date(x)).to_date())
    df_yesterday.set_index('adj_maturity', inplace=True) 
    
    str_sql = "SELECT [id] as product_id,[date_maturity] FROM [middle].[product] " +\
                "WHERE product_type = 'NTN-B' AND date_maturity >= '{:%Y-%m-%d}'".format(dt)
    dfProduct = pd.read_sql(str_sql, connection, index_col='date_maturity')
    
    # str_sql = f"""SELECT date_reference, rate FROM [middle].[product_price]  
    #               WHERE product_id = 'CDI' AND date_reference = '{dt:%Y-%m-%d}'
    #               """
    # CDI = pd.read_sql(str_sql, connection, index_col='date_reference').loc[dt, 'rate'] / 100
    
    del str_sql
    
    #%%
    df = df.join(dfProduct, on='adj_maturity', how='left')

    #%%
    df['product_id'] = df['product_id'].fillna('NTNB ' + df['date_maturity'].dt.strftime('%d/%m/%Y'))
    df['lote45_product'] = 'NTNB ' + df['date_maturity'].dt.strftime('%d/%m/%Y')
    
    #%%
    missing_ids = checks.check_missing_product(connection, list(df['product_id'].values), dt)
    for id_new in missing_ids:
        str_sql = """
                     INSERT INTO [middle].[product] 
                	        ([id],[product_type],[lote45_product],
                            [lote45_product_class],[description],[product_currency],
                            [date_maturity],[bloomberg_update])
                         VALUES ('{0}', 'NTN-B', '{1}',
                		'NTN-B', 'NTNB {2:%B%Y}', 'BRL',
                		'{2:%Y-%m-%d}', 0)
                 """
        str_sql = str_sql.format(
                                 id_new,
                                 df.loc[df['product_id']==id_new,'lote45_product'].item(),
                                 df.loc[df['product_id']==id_new,'adj_maturity'].item()
                                )
        connection.execute(str_sql)
        print('NTN-B - Inserted New product: {}'.format(id_new))
    
    #%%
    str_sql = "DELETE price FROM [middle].[product_price] price "+\
                "INNER JOIN [middle].[product] prod "+\
                "ON price.product_id = prod.id "+\
                "WHERE prod.[lote45_product_class]='NTN-B' AND "+\
                "price.date_reference = '{:%Y-%m-%d}' ".format(dt)
    connection.execute(str_sql)    
    df[['date_reference','product_id','rate','price']].\
        to_sql("product_price", connection, schema='middle', if_exists='append', index=False)
    print('NTN-B - Inserted {} values for date {} : TABLE product_price'.format(len(df), dt))
    
    
    (vna, indice) = df[['VNA','indice']].iloc[0].values
    str_sql = """
    DELETE FROM middle.product_price
    WHERE product_id = 'VNA NTNB' and date_reference = '{:%Y-%m-%d}'
    
    INSERT INTO middle.product_price (date_reference, product_id, price, rate)
        VALUES ('{:%Y-%m-%d}', 'VNA NTNB', {:1.10f}, {:1.10f})
    """
    str_sql = str_sql.format(dt, dt, vna, indice)
    connection.execute(str_sql)    
    print('NTN-B - Inserted 1 VNA value for date {} : TABLE product_price'.format(dt))
    
    
#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 3, 22)
    main(dt)
    
    
    # dtIni = ql.Date(1,1,2021)
    # dtIni = ql.Brazil(ql.Brazil().Exchange).adjust(dtIni)
    # while dtIni<= ql.Date(9,4,2021):  
    #     print(dtIni)
    #     main(dtIni.to_date(), False)
    #     dtIni = ql.Brazil(ql.Brazil().Exchange).advance(dtIni, ql.Period(1, ql.Days))


