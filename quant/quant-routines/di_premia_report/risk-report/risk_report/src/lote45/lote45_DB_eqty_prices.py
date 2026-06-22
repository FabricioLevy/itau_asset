import pandas as pd
import datetime

import sys
sys.path.insert(1, '..')
import fund_utils as fu

    
def main(dt) :
#%%
    engine, connection = fu.get_DB_conn('prod')    
    
    str_sql = """
    SELECT distinct [date_reference],p.id as product_id, round([value],10) as rate, round(value,10) as price
  FROM [lote45].[book_overview] bo INNER JOIN middle.product p ON bo.lote45_product = p.lote45_product
  where measure = 'Price' and date_reference = '{:%Y-%b-%d}'
  and product_type NOT IN ('DI1Future', 'DAP Future', 'FRC', 'DDI Future', 'FX Future', 'Equity Future', 
                           'LFT', 'LTN', 'NTN-F', 'NTN-B', 'Eurodollar Futures', 'FF Futures')
 -- and p.product_type in ('Equity','Equity Option', 'Equity Future', 'FX Option', 'IDI Option', 
 --                        'ETF', 'MXN TIIE SWAP', 'COP Fixed-Float SWAP', 'CLP Fixed-Float SWAP')
 -- and trading_desk='A1 Master FIM'
    """
    str_sql = str_sql.format(dt)    
    df = pd.read_sql(str_sql, connection)
    
    ids = "','".join(df['product_id'].values)
    
    str_sql = """
    DELETE FROM middle.product_price 
    WHERE date_reference='{:%Y-%b-%d}' and product_id in ('{}')
    """
    str_sql = str_sql.format(dt, ids)  
    connection.execute(str_sql)
    
    df.to_sql("product_price", engine, schema='middle', if_exists='append', 
                      index=False, chunksize=100, method='multi')
    print("{:%d-%b-%y} - Lote45 equity prices saved: {} rows".format(dt, len(df)))
    connection.close()

#%%
if __name__ == "__main__":
    dt = datetime.date(2022, 9, 12)
    main(dt)