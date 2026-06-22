import pandas as pd
import datetime
import os

from a1db.a1sql import SQLConnection

connection = SQLConnection().get_connection()

today = datetime.date.today()

#%%
# dfEquity = pd.read_csv('input/Equity-{:%d%b%Y}.txt'.format(today), sep='\t')
# dfEquity = pd.read_csv(r'C:\Users\luis.oliveira\Documents\Github\market_data\input\Equity-{:%d%b%Y}.txt'.format(today), sep='\t')
dfEquity = pd.read_csv(os.path.expanduser('~\\Documents\\Github\\market_data') + r'\input\Equity-{:%d%b%Y}.txt'.format(today), sep='\t')
for (prod_id, desc, ccy, _, _, isin) in dfEquity.values:
    ### middle.product
    str_sql = "SELECT * FROM middle.product WHERE id = '{}'".format(prod_id)
    df = pd.read_sql(str_sql, connection)
    if len(df) == 0:
        print('middle.product: {}'.format(prod_id))
        str_sql = """
            INSERT INTO middle.product (id, product_type, lote45_product, lote45_product_class,
                                        description, isin, bloomberg_ticker, product_currency,
                                        product_underlying, bloomberg_update, lot_size,
                                        entity_id)
              VALUES ('{0:}', 'Equity', '{0:}', 'Equity', 
                      '{1:}', '{2:}', '{0:} BZ EQUITY', '{3:}',
                      '{0:}', 0, 1, 
                      '{0:}' )
            """
        str_sql = str_sql.format(prod_id, desc, isin, ccy)
        connection.execute(str_sql)  
        
    ### quant.time_series_entity
    str_sql = "SELECT * FROM quant.time_series_entity WHERE id = '{}'".format(prod_id)
    df = pd.read_sql(str_sql, connection)
    if len(df) == 0:
        print('quant.time_series_entity: {}'.format(prod_id))
        str_sql = """
            INSERT INTO quant.time_series_entity (id, bloomberg_symbol)
              VALUES ('{0:}', '{0:} BZ EQUITY')
            """
        str_sql = str_sql.format(prod_id, desc, isin, ccy)
        connection.execute(str_sql)
        
        for field in ['CHG_PCT_1D', 'TURNOVER']:
            str_sql = """
                INSERT INTO quant.time_series (entity_id, name, source, field, update_frequency)
                VALUES ('{0:}', '{0:} {1:}', 'bloomberg', '{1:}', '1d*')
                """
            str_sql = str_sql.format(prod_id, field)
            print('quant.time_series: {} - {}'.format(prod_id, field))
            connection.execute(str_sql)
    
#%%
# dfEquityOpt = pd.read_csv('input/Equity Options-{:%d%b%Y}.txt'.format(today), sep='\t', parse_dates=[3, 9, 10, 12])
# dfEquityOpt = pd.read_csv(r'C:\Users\luis.oliveira\Documents\Github\market_data\input\Equity Options-{:%d%b%Y}.txt'.format(today), sep='\t', parse_dates=[3, 9, 10, 12])
dfEquityOpt = pd.read_csv(os.path.expanduser('~\\Documents\\Github\\market_data') + r'\input\Equity Options-{:%d%b%Y}.txt'.format(today), sep='\t', parse_dates=[3, 9, 10, 12])
for (prod_id, desc, ccy, dt_exp, _, _, opt_type, opt_style, opt_strike, _, _, opt_und, _) in dfEquityOpt.values:
    str_sql = "SELECT * FROM middle.product WHERE id = '{}'".format(prod_id)
    df = pd.read_sql(str_sql, connection)
    if len(df) == 0:
        print(prod_id)
        str_sql = """
            INSERT INTO middle.product (id, product_type, lote45_product, lote45_product_class,
                                        description, product_currency,
                                        product_underlying, date_maturity, 
                                        bloomberg_update, lot_size,
                                        option_type, option_style, option_strike)
              VALUES ('{0:}', 'Equity Option', '{0:}', 'Equity Options', 
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
    else:
        str_sql = " UPDATE middle.product SET option_strike = {1:} WHERE id = '{0:}' "
        str_sql = str_sql.format(prod_id, opt_strike)
        print(str_sql)
        connection.execute(str_sql)
        
#%%
# dfIbovOpt = pd.read_csv('input/IBOV Options-{:%d%b%Y}.txt'.format(today), sep='\t', parse_dates=[3, 9, 10])
# dfIbovOpt = pd.read_csv('C:/Users/luis.oliveira/Documents/Github/market_data/input/IBOV Options-{:%d%b%Y}.txt'.format(today), sep='\t', parse_dates=[3, 9, 10])
dfIbovOpt = pd.read_csv(os.path.expanduser('~\\Documents\\Github\\market_data') + '/input/IBOV Options-{:%d%b%Y}.txt'.format(today), sep='\t', parse_dates=[3, 9, 10])
for (prod_id, desc, ccy, dt_exp, _, _, opt_type, opt_style, opt_strike, _, _, _) in dfIbovOpt.values:
    str_sql = "SELECT * FROM middle.product WHERE id = '{}'".format(prod_id)
    df = pd.read_sql(str_sql, connection)
    if len(df) == 0:
        print(prod_id)
        opt_und = 'IBOV'
        str_sql = """
            INSERT INTO middle.product (id, product_type, lote45_product, lote45_product_class,
                                        description, product_currency,
                                        product_underlying, date_maturity, 
                                        bloomberg_update, lot_size,
                                        option_type, option_style, option_strike)
              VALUES ('{0:}', 'Equity Option', '{0:}', 'Equity Options', 
                      '{1:}', '{2:}',
                      '{3:}', '{4:%Y-%m-%d}', 
                      0, 1, 
                      '{5:}', '{6:}', {7:}
                      )
            """
        str_sql = str_sql.format(prod_id, desc, ccy, opt_und, dt_exp, opt_type, opt_style, opt_strike)
        connection.execute(str_sql)
        

#%%
 
del str_sql