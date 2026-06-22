import pandas as pd
import datetime

from a1db.a1sql import SQLConnection

def main(dt) :
#%%
    connection = SQLConnection().get_connection()  
    
    str_path = "R:/Risk/01_DailyReports/01_01_Lote45_extract/Offshore/"
    str_file = "BookLevelProductsGreeksRiskBucketsReport_{:%d%b%Y}.txt".format(dt)
    dfLote45= pd.read_csv(str_path + str_file, sep='\t', encoding='UTF-8')
    
    dfLote45 =  dfLote45[ dfLote45.columns[0:13]]
    dfLote45.columns = ['trading_desk', 'lote45_product', 'lote45_product_class',\
                        'primitive', 'primitive_class', 'book', 'product_currency',\
                        'bucket', 'eq_position', 'amount', 'delta', 'gamma', 'vega']
    dfLote45.insert(0, 'date_reference', dt)
    
    str_funds = "','".join(set(dfLote45['trading_desk']))
    
    connection.execute("DELETE FROM lote45.primitive WHERE date_reference='{:%Y-%b-%d}' and trading_desk in ('{}')".format(dt, str_funds))
    dfLote45.to_sql("primitive", connection, schema='lote45', if_exists='append', index=False)
    print("{:%d-%b-%y} - Offshore Primitives inserted: {} rows".format(dt, len(dfLote45)))
    

#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 5, 26)
    main(dt)
    