import pandas as pd
import datetime
import os

from a1db.a1sql import SQLConnection

connection = SQLConnection().get_connection()

today = datetime.date.today()

#%%
# df_USDBRLOptionCall = pd.read_csv('input/USDBRLOptionCall-{:%d%b%Y}.txt'.format(today), sep='\t', parse_dates=[3, 9, 10])
# df_USDBRLOptionCall = pd.read_csv('C:/Users/luis.oliveira/Documents/Github/market_data/input/USDBRLOptionCall-{:%d%b%Y}.txt'.format(today), sep='\t', parse_dates=[3, 9, 10])
df_USDBRLOptionCall = pd.read_csv(os.path.expanduser('~\\Documents\\Github\\market_data') + '/input/USDBRLOptionCall-{:%d%b%Y}.txt'.format(today), sep='\t', parse_dates=[3, 9, 10])
for (prod_id, desc, ccy, dt_exp, _, _, opt_type, opt_style, opt_strike, _, _, _) in df_USDBRLOptionCall.values:
    str_sql = "SELECT * FROM middle.product WHERE id = '{}'".format(prod_id)
    df = pd.read_sql(str_sql, connection)
    if len(df) == 0:
        print(prod_id)
        opt_und = 'USDBRL'
        str_sql = """
            INSERT INTO middle.product (id, product_type, lote45_product, lote45_product_class,
                                        description, product_currency,
                                        product_underlying, date_maturity, 
                                        bloomberg_update, lot_size,
                                        option_type, option_style, option_strike)
              VALUES ('{0:}', 'FX Option', '{0:}', 'USDBRLOptionCall', 
                      '{1:}', '{2:}',
                      '{3:}', '{4:%Y-%m-%d}', 
                      0, 1, 
                      '{5:}', '{6:}', {7:}
                      )
            """
        str_sql = str_sql.format(prod_id, desc, ccy, opt_und, dt_exp, opt_type, opt_style, opt_strike)
        connection.execute(str_sql)
        
        str_sql = "SELECT * FROM middle.product WHERE id = '{}'".format(opt_und)
        df = pd.read_sql(str_sql, connection)
        if len(df) == 0:
            print('Cadastrar ativo: {}'.format(opt_und))
#%%
# df_USDBRLOptionPut = pd.read_csv('input/USDBRLOptionPut-{:%d%b%Y}.txt'.format(today), sep='\t', parse_dates=[3, 9, 10])
# df_USDBRLOptionPut = pd.read_csv('C:/Users/luis.oliveira/Documents/Github/market_data/input/USDBRLOptionPut-{:%d%b%Y}.txt'.format(today), sep='\t', parse_dates=[3, 9, 10])
df_USDBRLOptionPut = pd.read_csv(os.path.expanduser('~\\Documents\\Github\\market_data') + '/input/USDBRLOptionPut-{:%d%b%Y}.txt'.format(today), sep='\t', parse_dates=[3, 9, 10])
for (prod_id, desc, ccy, dt_exp, _, _, opt_type, opt_style, opt_strike, _, _, _) in df_USDBRLOptionPut.values:
    str_sql = "SELECT * FROM middle.product WHERE id = '{}'".format(prod_id)
    df = pd.read_sql(str_sql, connection)
    if len(df) == 0:
        print(prod_id)
        opt_und = 'USDBRL'
        str_sql = """
            INSERT INTO middle.product (id, product_type, lote45_product, lote45_product_class,
                                        description, product_currency,
                                        product_underlying, date_maturity, 
                                        bloomberg_update, lot_size,
                                        option_type, option_style, option_strike)
              VALUES ('{0:}', 'FX Option', '{0:}', 'USDBRLOptionPut', 
                      '{1:}', '{2:}',
                      '{3:}', '{4:%Y-%m-%d}', 
                      0, 1, 
                      '{5:}', '{6:}', {7:}
                      )
            """
        str_sql = str_sql.format(prod_id, desc, ccy, opt_und, dt_exp, opt_type, opt_style, opt_strike)
        connection.execute(str_sql)
        
        str_sql = "SELECT * FROM middle.product WHERE id = '{}'".format(opt_und)
        df = pd.read_sql(str_sql, connection)
        if len(df) == 0:
            print('Cadastrar ativo: {}'.format(opt_und))            
#%%
        
connection.close()
del str_sql