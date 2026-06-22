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
        SELECT date_reference,left([mercadoria],3) as product_id,  [vencimento] as code_maturity, [preco_ajuste_atual] as price 
        FROM [b3].[ajuste_pregao] 
        WHERE mercadoria in ('DOL - Dólar comercial', 'WDO - Dólar Mini - WDO') 
            AND date_reference = '{:%Y-%m-%d}'
    """
    str_sql = str_sql.format(dt)
    df = pd.read_sql(str_sql, connection)
    
    del str_sql
    #%%
    calendar_br = ql.Brazil()
    df['settle_date'] = df['code_maturity'].apply(lambda x: \
                             calendar_br.adjust(ql.Date(1, getattr(ql.IMM, x[0]), 2000+int(x[-2:])),\
                                                 ql.Following).to_date())
    df['maturity_date'] = df['settle_date'].apply(lambda x: \
                             calendar_br.advance(ql.Date.from_date(x), ql.Period(-1, ql.Days)).to_date())        
    
    df['product_id'] +=  df['code_maturity']
    df['rate'] = df['price']
    
    df = df[df['settle_date']>dt]
    df.sort_values('settle_date', inplace=True)
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
        connection.execute(str_sql)
        print('DOL Fut - Inserted New product: {}'.format(id_new))

    #%%
    dfProductPrice.to_sql("product_price", connection, schema='middle', if_exists='append', index=False)
    print('DOL Fut - Inserted {} values for date {} : TABLE product_price'.format(len(dfProductPrice), dt))

    
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
   