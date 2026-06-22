import pandas as pd
import datetime
import os

from a1db.a1sql import SQLConnection

def main(str_lote45_product_class, list_prod):

    connection = SQLConnection().get_connection()
    
    dic_underlying = {'S&P500 E-mini Futures': 'SPX',
                      'S&P500 Futures - BMF': 'SPX',
                      'S&P500 E-mini Options':'SPX',
                      'NASDAQ-100 E-mini Futures - CME': 'NDX',
                      'Russell 2000 Index Mini Futures - CME': 'RTY',
                      'DJ Euro STOXX 50 Future - EUREX': 'SX5E',
                      'Gold Future  - CMX':'Gold Syn.'}
   
    str_path = os.path.expanduser("~/Documents/Github/market_data/input/")   
    
    dt_file=datetime.datetime(2000,1,1)
    for f in os.listdir(str_path):
        if f.startswith(str_lote45_product_class+"-") and f.endswith(".txt"):
            dt_file = max(dt_file, datetime.datetime.strptime(f[-13:-4], '%d%b%Y'))
    
    f = str_path + f"{str_lote45_product_class}-{dt_file:%d%b%Y}.txt"
    print(f">> reading file: {f}")
    
    if str_lote45_product_class in ['Equity', 'ETF BR']: 
        dfProd = pd.read_csv(f, sep='\t')
        add_product_Equity(list_prod, dfProd, str_lote45_product_class, connection)
        
    elif str_lote45_product_class in ['S&P500 E-mini Futures',
                                    'S&P500 Futures - BMF',
                                    'NASDAQ-100 E-mini Futures - CME',
                                    'Russell 2000 Index Mini Futures - CME']:
        dfProd = pd.read_csv(f, sep='\t', parse_dates=[3, 4])
        und = dic_underlying[str_lote45_product_class]
        add_product_IndexFuture(list_prod, dfProd, str_lote45_product_class, und, connection)
        
    elif str_lote45_product_class == 'CPM Options - BMF':
        dfProd = pd.read_csv(f, sep = '\t', parse_dates = [3])
        add_product_cpm_option(list_prod, dfProd, str_lote45_product_class, connection)
        
    elif str_lote45_product_class in ['Gold Future  - CMX']:
        dfProd = pd.read_csv(f, sep='\t', parse_dates=[3, 4])
        und = dic_underlying[str_lote45_product_class]
        add_commodity_future(list_prod, dfProd, str_lote45_product_class, und, connection)
        
    elif str_lote45_product_class == 'S&P500 E-mini Options':
        dfProd = pd.read_csv(f,sep = '\t', parse_dates=[3])
        und = dic_underlying[str_lote45_product_class]
        add_product_snp_options(list_prod,dfProd, str_lote45_product_class,und,connection)
        
    elif str_lote45_product_class in ['DJ Euro STOXX 50 Future - EUREX']:
         dfProd = pd.read_csv(f, sep='\t', parse_dates=[4])
         und = dic_underlying[str_lote45_product_class]
         add_product_IndexFuture(list_prod, dfProd, str_lote45_product_class, und, connection)

    elif str_lote45_product_class == 'BDR Unsponsored': 
        dfProd = pd.read_csv(f, sep='\t')
        add_product_BDR(list_prod, dfProd, str_lote45_product_class, connection)
        
    elif str_lote45_product_class == "Equity Receipts":
        print(f"XXX To be developed: '{str_lote45_product_class}' XXX")
        
    elif str_lote45_product_class in ['Equity Options',
                                      'Equity Subscription']:
        dfProd = pd.read_csv(f, sep='\t', parse_dates=[3, 9, 10, 12])
        add_product_EquityOption(list_prod, dfProd, connection, str_lote45_product_class)
        
    elif str_lote45_product_class == 'IBOV Options':
        dfProd = pd.read_csv(f, sep='\t', parse_dates=[3, 9, 10])
        add_product_IBOVOption(list_prod, dfProd, connection)
        
    elif str_lote45_product_class in ['WTI Crude Oil Future Options']:
        dfProd = pd.read_csv(f, sep='\t', parse_dates=[3])
        add_product_CmtdyOpt(list_prod, dfProd, connection, str_lote45_product_class)
        
    elif str_lote45_product_class in ['USDBRLOptionCall', 
                                      'USDBRLOptionPut']:
        dfProd = pd.read_csv(f, sep='\t', parse_dates=[3, 9, 10])
        add_product_USDBRLOption(list_prod, dfProd, str_lote45_product_class, connection)
        
    elif str_lote45_product_class in ['Currencies Options']:
        dfProd = pd.read_csv(f, sep='\t', parse_dates=[3])
        add_currencyOptions(list_prod, dfProd, connection, str_lote45_product_class)
        
    elif str_lote45_product_class in ['ETF', 
                                      'US Equity']:
        dfProd = pd.read_csv(f, sep='\t')
        add_product_USEquity(list_prod, dfProd, connection)    
        
    elif str_lote45_product_class in ['US Treasury Bond Future',
                                      'US T-Note 10 BMF']:
        dfProd = pd.read_csv(f, sep='\t', parse_dates=[4])
        add_product_USTBondFuture(list_prod, dfProd, str_lote45_product_class, connection)
        
    elif str_lote45_product_class == 'MXN TIIE SWAP':
        dfProd = pd.read_csv(f, sep='\t', parse_dates=[3,4,5,6,9])
        dfProd = dfProd[dfProd['Dt_Expiry']==dfProd['Dt_CashFlow']]
        add_product_SwapTIIE(list_prod, dfProd, str_lote45_product_class, connection)
        
    elif str_lote45_product_class == 'CLP Fixed-Float SWAP':
        dfProd = pd.read_csv(f, sep='\t', parse_dates=[3,4,5,6,9])
        dfProd = dfProd[dfProd['Dt_Expiry']==dfProd['Dt_CashFlow']]
        add_product_SwapCLP(list_prod, dfProd, str_lote45_product_class, connection)
        
    elif str_lote45_product_class == 'COP Fixed-Float SWAP':
        dfProd = pd.read_csv(f, sep='\t', parse_dates=[3,4,5,6,9, 12, 13])
        dfProd = dfProd[(dfProd['Dt_Expiry']==dfProd['Dt_CashFlow']) & (dfProd['Is Fixed Payment']==True)]
        add_product_SwapCOP(list_prod, dfProd, str_lote45_product_class, connection)
           
    

#%% ##############################################
def add_product_Equity(list_prod, dfProd, lote45_product_class, connection):
    
    dfProd = dfProd[dfProd['Product'].isin(list_prod)]
    for (prod_id, desc, ccy, _, _, isin) in dfProd.values:
        
        ### middle.product
        str_sql = f"SELECT * FROM middle.product WHERE id = '{prod_id}'"
        df = pd.read_sql(str_sql, connection)
        if len(df) == 0:
            print(f"middle.product: {prod_id}")
            str_sql = f"""
                INSERT INTO middle.product (id, product_type, lote45_product, lote45_product_class,
                                            description, isin, bloomberg_ticker, product_currency,
                                            product_underlying, bloomberg_update, lot_size,
                                            entity_id, onshore_risk)
                  VALUES ('{prod_id}', 'Equity', '{prod_id}', '{lote45_product_class}', 
                          '{desc}', '{isin}', '{prod_id} BZ EQUITY', '{ccy}',
                          '{prod_id}', 0, 1, 
                          '{prod_id}', 1 )
                """
            connection.execute(str_sql)
            
        ### quant.time_series_entity
        str_sql = f"SELECT * FROM quant.time_series_entity WHERE id = '{prod_id}'"
        df = pd.read_sql(str_sql, connection)
        if len(df) == 0:
            print(f"quant.time_series_entity: {prod_id}")
            str_sql = f"""
                INSERT INTO quant.time_series_entity (id, bloomberg_symbol)
                  VALUES ('{prod_id}', '{prod_id} BZ EQUITY')
                """
            connection.execute(str_sql)
            
            for field in ['CHG_PCT_1D', 'TURNOVER']:
                str_sql = f"""
                    INSERT INTO quant.time_series (entity_id, name, source, field, update_frequency)
                    VALUES ('{prod_id}', '{prod_id} {field}', 'bloomberg', '{field}', '1d*')
                    """
                print('quant.time_series: {} - {}'.format(prod_id, field))
                connection.execute(str_sql)
                
#%% ##############################################
def add_product_snp_options(list_prod, dfProd, lote45_product_class,und, connection):
    
    dfProd = dfProd[dfProd['Product'].isin(list_prod)][['Product','Description','ProductCurrency','Dt_Expiry',
                                                    'NegotiationLot', 'Option Type', 'Option Style', 'Strike']]
    
    for prod_id, description, ccy, date_mat, lot_size, opt_type, opt_style, strike in dfProd.values:
        str_sql = f"SELECT * FROM middle.product WHERE id = '{prod_id}'"
        df = pd.read_sql(str_sql, connection)
        if len(df) == 0:
            print(f"middle.product: {prod_id}")
            str_sql = f"""
                    INSERT INTO middle.product (id,product_type,lote45_product,lote45_product_class,
                                                description, product_currency, product_underlying,date_maturity,bloomberg_update,
                                                lot_size,entity_id, option_type,option_style,option_strike,onshore_risk)
                    VALUES ('{prod_id}','Equity Option','{prod_id}','{lote45_product_class}','{description}',
                            '{ccy}','{und}','{date_mat:%Y-%m-%d}',0,'{lot_size}','{und}','{opt_type}','{opt_style}',
                            '{strike}',0)
                    """
            
            connection.execute(str_sql)
            
def add_product_cpm_option(list_prod, dfProd, lote45_product_class, connection):
    
    dfProd = dfProd[dfProd['Product'].isin(list_prod)][['Product', 'Description', 'ProductCurrency','Dt_Expiry', 'PriceLot', 
                                                        'Option Type', 'Option Style', 'Strike']]
    
    for prod_id, desc, ccy, dt_mt, lot_size, opt_type, opt_style, strike in dfProd.values:
        
        str_sql = f"SELECT * FROM middle.product WHERE id = '{prod_id}'"
        df = pd.read_sql(str_sql, connection)
        if len(df) == 0:
            print(f"middle.product: {prod_id}")
            str_sql = f"""
                    INSERT INTO middle.product (id,product_type,lote45_product,lote45_product_class,
                                                description, product_currency, product_underlying,date_maturity,bloomberg_update,
                                                lot_size, option_type,option_style,option_strike,onshore_risk)
                    VALUES ('{prod_id}','CPM Option','{prod_id}','{lote45_product_class}','{desc}',
                            '{ccy}','ISETA','{dt_mt:%Y-%m-%d}',0,'{lot_size}','{opt_type}','{opt_style}',
                            '{strike}',1)
                    """
            
            connection.execute(str_sql)
    
#%% #############################################
def add_product_BDR(list_prod, dfProd, lote45_product_class, connection):
    
    dfProd = dfProd[dfProd['Product'].isin(list_prod)]
    for (prod_id, desc, ccy, _, _, _, pricelot) in dfProd.values:
        
        ### middle.product
        str_sql = f"SELECT * FROM middle.product WHERE id = '{prod_id}'"
        df = pd.read_sql(str_sql, connection)
        if len(df) == 0:
            print(f"middle.product: {prod_id}")
            str_sql = f"""
                INSERT INTO middle.product (id, product_type, lote45_product, lote45_product_class,
                                            description, bloomberg_ticker, product_currency,
                                            product_underlying, bloomberg_update, lot_size,
                                            entity_id)
                  VALUES ('{prod_id}', 'Equity', '{prod_id}', '{lote45_product_class}', 
                          '{desc}',  '{prod_id} BZ EQUITY', '{ccy}',
                          '{prod_id}', 0, {pricelot}, 
                          '{prod_id}' )
                """
            connection.execute(str_sql)
            
        ### quant.time_series_entity
        str_sql = f"SELECT * FROM quant.time_series_entity WHERE id = '{prod_id}'"
        df = pd.read_sql(str_sql, connection)
        if len(df) == 0:
            print(f"quant.time_series_entity: {prod_id}")
            str_sql = f"""
                INSERT INTO quant.time_series_entity (id, bloomberg_symbol)
                  VALUES ('{prod_id}', '{prod_id} BZ EQUITY')
                """
            connection.execute(str_sql)
            
            for field in ['CHG_PCT_1D', 'TURNOVER']:
                str_sql = f"""
                    INSERT INTO quant.time_series (entity_id, name, source, field, update_frequency)
                    VALUES ('{prod_id}', '{prod_id} {field}', 'bloomberg', '{field}', '1d*')
                    """
                print('quant.time_series: {} - {}'.format(prod_id, field))
                connection.execute(str_sql)
                
#%% ##############################################
def add_product_EquityOption(list_prod, dfProd, connection, str_lote45_product_class):

    dfProd = dfProd[dfProd['Product'].isin(list_prod)]
    for (prod_id, desc, ccy, dt_exp, _, _, opt_type, opt_style, opt_strike, _, _, opt_und, _) in dfProd.values:
        str_sql = "SELECT * FROM middle.product WHERE id = '{}'".format(prod_id)
        df = pd.read_sql(str_sql, connection)
        if len(df) == 0:
            print(f"Added new product: {prod_id}")
            str_sql = f"""
                INSERT INTO middle.product (id, product_type, lote45_product, lote45_product_class,
                                            description, product_currency,
                                            product_underlying, date_maturity, 
                                            bloomberg_update, lot_size,
                                            option_type, option_style, option_strike, onshore_risk)
                  VALUES ('{prod_id}', 'Equity Option', '{prod_id}', '{str_lote45_product_class}', 
                          '{desc}', '{ccy}',
                          '{opt_und}', '{dt_exp:%Y-%m-%d}', 
                          0, 1, 
                          '{opt_type:}', '{opt_style:}', {opt_strike:}, 1
                          )
                """
            connection.execute(str_sql)
            
            str_sql = "SELECT * FROM middle.product WHERE id = '{}'".format(opt_und)
            df = pd.read_sql(str_sql, connection)
            if len(df) == 0:
                print('Cadastrar ativo: {}'.format(opt_und))
        else:
            str_sql = f"UPDATE middle.product SET option_strike = {opt_strike:} WHERE id = '{prod_id:}' "
            print(str_sql)
            connection.execute(str_sql)

#%% ##############################################
def add_product_IBOVOption(list_prod, dfProd, connection):    

    dfProd = dfProd[dfProd['Product'].isin(list_prod)]
    for (prod_id, desc, ccy, dt_exp, _, _, opt_type, opt_style, opt_strike, _, _, _) in dfProd.values:
        str_sql = "SELECT * FROM middle.product WHERE id = '{}'".format(prod_id)
        df = pd.read_sql(str_sql, connection)
        if len(df) == 0:
            print(f"Added new product: {prod_id}")
            opt_und = 'IBOV'
            str_sql = f"""
                INSERT INTO middle.product (id, product_type, lote45_product, lote45_product_class,
                                            description, product_currency,
                                            product_underlying, date_maturity, 
                                            bloomberg_update, lot_size,
                                            option_type, option_style, option_strike, onshore_risk)
                  VALUES ('{prod_id}', 'Equity Option', '{prod_id}', 'Equity Options', 
                          '{desc}', '{ccy}',
                          '{opt_und}', '{dt_exp:%Y-%m-%d}', 
                          0, 1, 
                          '{opt_type}', '{opt_style}', {opt_strike}, 1
                          )
                """
            connection.execute(str_sql)
            
#%% ##############################################

def add_product_CmtdyOpt(list_prod, dfProd, connection, str_lote45_product_class):    

    dfProd = dfProd[dfProd['Product'].isin(list_prod)]
    for (prod_id, desc, ccy, dt_exp, lot_size, _, opt_type, opt_style, opt_strike, _, _, opt_und,_) in dfProd.values:
        str_sql = "SELECT * FROM middle.product WHERE id = '{}'".format(prod_id)
        df = pd.read_sql(str_sql, connection)
        if len(df) == 0:
            print(f"Added new product: {prod_id}")
            str_sql = f"""
                INSERT INTO middle.product (id, product_type, lote45_product, lote45_product_class,
                                            description, product_currency,
                                            product_underlying, date_maturity, 
                                            bloomberg_update, lot_size,
                                            option_type, option_style, option_strike, onshore_risk)
                  VALUES ('{prod_id}', 'Commodity Option', '{prod_id}', '{str_lote45_product_class}', 
                          '{desc}', '{ccy}',
                          '{opt_und}', '{dt_exp:%Y-%m-%d}', 
                          0, '{lot_size}', 
                          '{opt_type}', '{opt_style}', {opt_strike}, 0
                          )
                """
            connection.execute(str_sql)
        
#%% ##############################################
def add_product_USDBRLOption(list_prod, dfProd, str_lote45_product_class, connection):
    
    dfProd = dfProd[dfProd['Product'].isin(list_prod)]
    for (prod_id, desc, ccy, dt_exp, _, _, opt_type, opt_style, opt_strike, _, _, _) in dfProd.values:
        str_sql = "SELECT * FROM middle.product WHERE id = '{}'".format(prod_id)
        df = pd.read_sql(str_sql, connection)
        if len(df) == 0:
            print(f"Added new product: {prod_id}")
            opt_und = 'USDBRL'
            str_sql = f"""
                INSERT INTO middle.product (id, product_type, lote45_product, lote45_product_class,
                                            description, product_currency,
                                            product_underlying, date_maturity, 
                                            bloomberg_update, lot_size,
                                            option_type, option_style, option_strike, onshore_risk)
                  VALUES ('{prod_id}', 'FX Option', '{prod_id}', '{str_lote45_product_class}', 
                          '{desc}', '{ccy}',
                          '{opt_und}', '{dt_exp:%Y-%m-%d}', 
                          0, 1, 
                          '{opt_type}', '{opt_style}', {opt_strike}, 1
                          )
                """
            str_sql = str_sql.format(prod_id, desc, ccy, opt_und, dt_exp, opt_type, opt_style, opt_strike)
            connection.execute(str_sql)
            
#%% ##############################################
def add_product_USEquity(list_prod, dfProd, connection):
    
    dfProd = dfProd[dfProd['Product'].isin(list_prod)]
    for (prod_id, desc, ccy, _, pricelot, isin) in dfProd.values:
        
        ### middle.product
        str_sql = f"SELECT * FROM middle.product WHERE id = '{prod_id}'"
        df = pd.read_sql(str_sql, connection)
        if len(df) == 0:
            print(f"middle.product: {prod_id}")
            str_sql = f"""
                INSERT INTO middle.product (id, product_type, lote45_product, lote45_product_class,
                                            description, isin, bloomberg_ticker, product_currency,
                                            product_underlying, bloomberg_update, lot_size,
                                            entity_id, onshore_risk)
                  VALUES ('{prod_id}', 'Equity', '{prod_id}', 'US Equity', 
                          '{desc}', '{isin}', '{prod_id} US EQUITY', '{ccy}',
                          '{prod_id}', 0, {pricelot}, 
                          '{prod_id}', 0 )
                """
            connection.execute(str_sql)
            
        ### quant.time_series_entity
        str_sql = f"SELECT * FROM quant.time_series_entity WHERE id = '{prod_id}'"
        df = pd.read_sql(str_sql, connection)
        if len(df) == 0:
            print(f"quant.time_series_entity: {prod_id}")
            str_sql = f"""
                INSERT INTO quant.time_series_entity (id, bloomberg_symbol)
                  VALUES ('{prod_id}', '{prod_id} US EQUITY')
                """
            connection.execute(str_sql)
            
            for field in ['CHG_PCT_1D', 'TURNOVER']:
                str_sql = f"""
                    INSERT INTO quant.time_series (entity_id, name, source, field, update_frequency)
                    VALUES ('{prod_id}', '{prod_id} {field}', 'bloomberg', '{field}', '1d*')
                    """
                print('quant.time_series: {} - {}'.format(prod_id, field))
                connection.execute(str_sql)           
#%% ##############################################
def add_currencyOptions(list_prod, dfProd, connection, product_class):
    
    dfProd = dfProd[dfProd['Product'].isin(list_prod)]
    for (prod_id, desc, ccy, dt_exp, lot_size, _, ccy2,_, strike,_,_,_) in dfProd.values:
        
        str_sql = f"SELECT * FROM middle.product WHERE id = '{prod_id}'"
        df = pd.read_sql(str_sql, connection)
        
        if len(df) == 0:
            print(f"middle.product: {prod_id}")
            str_sql = f"""
                INSERT INTO middle.product (id, product_type, lote45_product, lote45_product_class,
                                            description, product_currency,
                                            product_underlying, date_maturity, lot_size,
                                            option_type,option_style, option_strike, onshore_risk)
                  VALUES ('{prod_id}', 'FX Option', '{prod_id}', '{product_class}', 
                          '{prod_id}', '{ccy}',
                          '{ccy + ccy2}','{dt_exp:%Y-%m-%d}', {lot_size}, 
                          '{prod_id[3]}', 'E', {strike}, 0)
                """
            connection.execute(str_sql)

#%% ##############################################
def add_product_USTBondFuture(list_prod, dfProd, str_lote45_product_class, connection):
    
    dfProd = dfProd[dfProd['Product'].isin(list_prod)]    
    for (prod_id, desc, ccy, _, dt_exp, lotsize, _) in dfProd.values:        
        ### middle.product
        str_sql = f"SELECT * FROM middle.product WHERE id = '{prod_id}'"
        df = pd.read_sql(str_sql, connection)
        if len(df) == 0:
            if str_lote45_product_class == 'US T-Note 10 BMF':
                bbg_code = 'OI' + prod_id[-3] + prod_id[-1]
            else:
                bbg_code = prod_id
                
            print(f"middle.product: {prod_id}")
            str_sql = f"""
                INSERT INTO middle.product (id, product_type, 
                                            lote45_product, lote45_product_class,
                                            date_maturity,
                                            description, bloomberg_ticker, product_currency,
                                            product_underlying, bloomberg_update, lot_size,
                                            entity_id, onshore_risk)
                  VALUES ('{prod_id}', '{str_lote45_product_class}',
                          '{prod_id}', '{str_lote45_product_class}', 
                          '{dt_exp:%Y-%m-%d}',
                          '{desc}', '{bbg_code} COMDTY', '{ccy}',
                          NULL, 1, {lotsize}, 
                          NULL, 0 )
                """
            connection.execute(str_sql)
            
#%% ##############################################
def add_product_IndexFuture(list_prod, dfProd, str_lote45_product_class, und, connection):
    
    dfProd = dfProd[dfProd['Product'].isin(list_prod)][['Product', 'Description', 
                                                       'ProductCurrency', 'Dt_Expiry',
                                                       'NegotiationLot', 'PriceLot']]
    for (prod_id, desc, ccy, dt_exp, lotsize, _) in dfProd.values:
        
        ### middle.product
        str_sql = f"SELECT * FROM middle.product WHERE id = '{prod_id}'"
        df = pd.read_sql(str_sql, connection)
        if len(df) == 0:
            if str_lote45_product_class == 'S&P500 Futures - BMF':
                bbg_code = prod_id[:-2] + prod_id[-1]
            else:
                bbg_code = prod_id
            print(f"middle.product: {prod_id}")
            str_sql = f"""
                INSERT INTO middle.product (id, product_type, lote45_product, lote45_product_class,
                                            description, bloomberg_ticker, product_currency,
                                            date_maturity,
                                            product_underlying, bloomberg_update, lot_size,
                                            entity_id, onshore_risk)
                  VALUES ('{prod_id}', 'Equity Future', '{prod_id}', '{str_lote45_product_class}', 
                          '{desc}', '{bbg_code} Index', '{ccy}',
                          '{dt_exp:%Y-%m-%d}',
                          '{und}', 1, {lotsize}, 
                          '{und}', 0 )
                """
            connection.execute(str_sql)          
#%%
def add_commodity_future(list_prod, dfProd, str_lote45_product_class, und, connection):
    dfProd = dfProd[dfProd['Product'].isin(list_prod)][['Product', 'Description', 
                                                       'ProductCurrency', 'Dt_Expiry',
                                                       'NegotiationLot', 'PriceLot']]
    for (prod_id, desc, ccy, dt_exp, lotsize, _) in dfProd.values:
        
        ### middle.product
        str_sql = f"SELECT * FROM middle.product WHERE id = '{prod_id}'"
        df = pd.read_sql(str_sql, connection)
        if len(df) == 0:
            bbg_code = prod_id
            print(f"middle.product: {prod_id}")
            str_sql = f"""
                INSERT INTO middle.product (id, product_type, lote45_product, lote45_product_class,
                                            description, bloomberg_ticker, product_currency,
                                            date_maturity,
                                            product_underlying, bloomberg_update, lot_size,
                                            entity_id, onshore_risk)
                  VALUES ('{prod_id}', 'Commodity Future', '{prod_id}', '{str_lote45_product_class}', 
                          '{desc}', '{bbg_code}', '{ccy}',
                          '{dt_exp:%Y-%m-%d}',
                          '{und}', 0, {lotsize}, 
                          '{und}', 0 )
                """
            connection.execute(str_sql) 

#%% ##############################################
def add_product_SwapTIIE(list_prod, dfProd, str_lote45_product_class, connection):
    
    dfProd = dfProd[dfProd['Product'].isin(list_prod)]    
    for (prod_id, desc, ccy, dt_issue, dt_exp, _,_,_,_,_, _,_,_,_,_, _,fixed_rate,_,_,_,_,_) in dfProd.values:        
        ### middle.product
        str_sql = f"SELECT * FROM middle.product WHERE id = '{prod_id}'"
        df = pd.read_sql(str_sql, connection)
        if len(df) == 0:                
            print(f"middle.product: {prod_id}")
            str_sql = f"""
                INSERT INTO middle.product (id, product_type, 
                                            lote45_product, lote45_product_class,
                                            description, product_currency,
                                            date_issue, date_maturity, swap_fixed_rate,
                                            product_underlying, bloomberg_update, lot_size,
                                            entity_id, onshore_risk)
                  VALUES ('{prod_id}', '{str_lote45_product_class}',
                          '{prod_id}', '{str_lote45_product_class}', 
                          '{desc}', '{ccy}',
                          '{dt_issue:%Y-%m-%d}','{dt_exp:%Y-%m-%d}', {fixed_rate:0.8f},
                          'TIIE 28', 0, 1, 
                          NULL, 0 )
                """
            connection.execute(str_sql)
            
#%% ##############################################
def add_product_SwapCLP(list_prod, dfProd, str_lote45_product_class, connection):
    
    dfProd = dfProd[dfProd['Product'].isin(list_prod)]    
    for (prod_id, desc, ccy, dt_issue, dt_exp, _,_,_,_,_, _,_,_,_,_, _,_,_,_,_, _,fixed_rate) in dfProd.values:        
        ### middle.product
        str_sql = f"SELECT * FROM middle.product WHERE id = '{prod_id}'"
        df = pd.read_sql(str_sql, connection)
        if len(df) == 0:                
            print(f"middle.product: {prod_id}")
            str_sql = f"""
                INSERT INTO middle.product (id, product_type, 
                                            lote45_product, lote45_product_class,
                                            description, product_currency,
                                            date_issue, date_maturity, swap_fixed_rate,
                                            product_underlying, bloomberg_update, lot_size,
                                            entity_id, onshore_risk)
                  VALUES ('{prod_id}', '{str_lote45_product_class}',
                          '{prod_id}', '{str_lote45_product_class}', 
                          '{desc}', '{ccy}',
                          '{dt_issue:%Y-%m-%d}','{dt_exp:%Y-%m-%d}', {fixed_rate:0.8f},
                          'ICP', 0, 1, 
                          NULL, 0 )
                """
            connection.execute(str_sql)
 
#%% ##############################################
def add_product_SwapCOP(list_prod, dfProd, str_lote45_product_class, connection):
    
    dfProd = dfProd[dfProd['Product'].isin(list_prod)]    
    for (prod_id, desc, ccy, dt_issue, dt_exp, _,_,_,_,_, _,_,_,_,_, _,_,_,_,_, _,fixed_rate) in dfProd.values:        
        ### middle.product
        str_sql = f"SELECT * FROM middle.product WHERE id = '{prod_id}'"
        df = pd.read_sql(str_sql, connection)
        if len(df) == 0:                
            print(f"middle.product: {prod_id}")
            str_sql = f"""
                INSERT INTO middle.product (id, product_type, 
                                            lote45_product, lote45_product_class,
                                            description, product_currency,
                                            date_issue, date_maturity, swap_fixed_rate,
                                            product_underlying, bloomberg_update, lot_size,
                                            entity_id, onshore_risk)
                  VALUES ('{prod_id}', '{str_lote45_product_class}',
                          '{prod_id}', '{str_lote45_product_class}', 
                          '{desc}', '{ccy}',
                          '{dt_issue:%Y-%m-%d}','{dt_exp:%Y-%m-%d}', {fixed_rate:0.8f},
                          'ICP', 0, 1, 
                          NULL, 0 )
                """
            connection.execute(str_sql)
                        
                                   
            
#%%
if __name__ == "__main__":
    str_lote45_product_class = 'CPM Options - BMF'
    list_prod = ['CPMZQ80']
    main(str_lote45_product_class, list_prod)
    
 
