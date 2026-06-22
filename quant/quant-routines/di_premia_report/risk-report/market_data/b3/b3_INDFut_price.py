import pandas as pd
import datetime
import QuantLib as ql

from a1db.a1sql import SQLConnection

import os, sys
path_github = os.path.expanduser('~\\Documents\\Github')
sys.path.insert(1, path_github + '\\market_data')
import checks


#%%
def closest_wednesday(dt, calendar=ql.Brazil()):
    day_15 = ql.Date(15, dt.month(), dt.year())
    wed_2 = ql.Date.nthWeekday(2, ql.Wednesday, dt.month(), dt.year())
    wed_3 = ql.Date.nthWeekday(3, ql.Wednesday, dt.month(), dt.year())
    return calendar.adjust(wed_2) if (day_15 - wed_2 < 4) else calendar.adjust(wed_3)

#%%
def main(dt):
    #%%
    connection = SQLConnection().get_connection()
        
    str_sql = "SELECT date_reference,left([mercadoria],3) as product_id, [vencimento] as code_maturity, [preco_ajuste_atual] as price "+\
            " FROM [b3].[ajuste_pregao] "+\
            " WHERE mercadoria in ('IND - Ibovespa', 'WIN - Ibovespa Mini') "\
            "   AND date_reference = '{:%Y-%m-%d}'".format(dt)
    df = pd.read_sql(str_sql, connection)
    
    del str_sql
    #%%
    df['maturity_date'] = df['code_maturity'].apply(lambda x: \
                             closest_wednesday(ql.Date(15, getattr(ql.IMM, x[0]), 2000+int(x[-2:]))).to_date())
    
    df['product_id'] +=  df['code_maturity']
    df['rate'] = df['price']

     #%%
    str_sql = "DELETE price FROM [middle].[product_price] price "+\
                "INNER JOIN [middle].[product] prod "+\
                "ON price.product_id = prod.id "+\
                "WHERE prod.[lote45_product_class]='IBOVSPFuture' AND "+\
                "price.date_reference = '{:%Y-%m-%d}' ".format(dt)
    connection.execute(str_sql)
    
    dfProductPrice = df[['date_reference', 'product_id', 'rate' ,'price']]
    #%%
    missing_ids = checks.check_missing_product(connection, list(dfProductPrice['product_id'].values), dt)
    for id_new in missing_ids:
        str_sql = """
         INSERT INTO [middle].[product] 
	        ([id],[product_type],[lote45_product],
            [lote45_product_class],[description],[product_currency],[product_underlying],
           [date_maturity],[bloomberg_update], lot_size)
         VALUES ('{0}', 'Equity Future', '{0}',
		'IBOVSPFuture', 'IND {1:%b%Y}', 'BRL', 'IBOV',
		'{1:%Y-%m-%d}', 0, {2:1.1f})
         """
        str_sql = str_sql.format(id_new, 
                                 df.loc[df['product_id']==id_new,'maturity_date'].item(),
                                 0.2 if id_new[0]=='W' else 1.0)
        connection.execute(str_sql)
        print('IND Fut - Inserted New product: {}'.format(id_new))

    #%%
    dfProductPrice.to_sql("product_price", connection, schema='middle', if_exists='append', index=False)
    print('IND Fut - Inserted {} values for date {} : TABLE product_price'.format(len(dfProductPrice), dt))

    
#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 3, 9)
    main(dt)
    

    # dtIni = ql.Date(1,4,2020)
    # dtIni = ql.Brazil(ql.Brazil().Exchange).adjust(dtIni)
    # while dtIni<= ql.Date(15, 11, 2020):    
    #     main(dtIni.to_date())
    #     dtIni = ql.Brazil(ql.Brazil().Exchange).advance(dtIni, ql.Period(1, ql.Days))



    