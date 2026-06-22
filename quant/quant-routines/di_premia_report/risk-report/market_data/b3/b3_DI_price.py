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
    ## getting data from DB - Ajuste Pregão
    connection = SQLConnection().get_connection()
        
    str_sql = "SELECT date_reference, [vencimento] as code_maturity, [preco_ajuste_atual] as price "+\
            " FROM [b3].[ajuste_pregao] "+\
            " WHERE mercadoria = 'DI1 - DI de 1 dia' "\
            "   AND date_reference = '{:%Y-%m-%d}'".format(dt)
    df = pd.read_sql(str_sql, connection)
    
    del str_sql    
    #%%
    calendar_br = ql.Brazil()
    today = ql.Date.from_date(dt)
    
    df['maturity_date'] = df['code_maturity'].apply(lambda x: \
                             calendar_br.adjust(ql.Date(1, getattr(ql.IMM, x[0]), 2000+int(x[-2:])),\
                                                 ql.Following).to_date())
    df['factor'] = 100000/df['price']
    df['product_id'] = 'DI1' + df['code_maturity']
    
    df = df[df['maturity_date']>dt].copy()
    df['busday'] = df['maturity_date'].apply(lambda x: calendar_br.businessDaysBetween(today, ql.Date.from_date(x)))
    df['rate'] = df['factor'] ** (252/df['busday']) - 1
    ## pv01
    df['value'] = (df['busday']/252) * (1/(1+df['rate']))*df['price'] / 10000
    
    #%%
    str_sql = "DELETE price FROM [middle].[product_price] price "+\
                "INNER JOIN [middle].[product] prod "+\
                "ON price.product_id = prod.id "+\
                "WHERE prod.[lote45_product_class]='DI1Future' AND "+\
                "price.date_reference = '{:%Y-%m-%d}' ".format(dt)
    connection.execute(str_sql)
    
    dfProductPrice = df[['date_reference', 'product_id', 'rate', 'price']]
    #%%
    missing_ids = checks.check_missing_product(connection, list(dfProductPrice['product_id'].values), dt)
    for id_new in missing_ids:
        str_sql = """
         INSERT INTO [middle].[product] 
	        ([id],[product_type],[lote45_product],
            [lote45_product_class],[description],[product_currency],
           [date_maturity],[bloomberg_update])
         VALUES ('{0}', 'DI1Future', '{0}',
		'DI1Future', 'DI1 {1:%b%Y}', 'BRL',
		'{1:%Y-%m-%d}', 0)
         """
        str_sql = str_sql.format(id_new, df.loc[df['product_id']==id_new,'maturity_date'].item())
        connection.execute(str_sql)
        print('DI1Future - Inserted New product: {}'.format(id_new))
    #%%
    dfProductPrice.to_sql("product_price", connection, schema='middle', if_exists='append', index=False)
    print('DI1Future - Inserted {} values for date {} : TABLE product_price'.format(len(dfProductPrice), dt))
    

    
#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 3, 9)
    main(dt)
    
    # dtIni = ql.Date(1,1,2007)
    # dtIni = ql.Brazil(ql.Brazil().Exchange).adjust(dtIni)
    # while dtIni<= ql.Date(1, 1, 2010):    
    #     main(dtIni.to_date())
    #     dtIni = ql.Brazil(ql.Brazil().Exchange).advance(dtIni, ql.Period(1, ql.Days))

