import pandas as pd
import datetime
import QuantLib as ql

from a1db.a1sql import SQLConnection  

#%%
def main(dt):
#%%
    connection = SQLConnection().get_connection()  
    str_path = "R:/Risk/01_DailyReports/01_01_Lote45_extract/Offshore/"
    
    #%%
    file_var_stress = f"BooksOverviewReport_{dt:%d%b%Y}.txt"
    df = pd.read_csv(str_path + file_var_stress, 
                     sep='\t', 
                     parse_dates=[1, 6], 
                     encoding='UTF-8')
    
    cols = ['ValDate', 'TradingDesk', 'Product Class', 'Product', 
             'Book', 'Currency', 'Financial Price', 'Price',
           'Amount', 'Position PL', 'Trades PL', 'PL', 'Position']
    
    df = df[df['ValDate']==f"{dt}"][cols]
    
    df = df.rename({'ValDate': 'date_reference',
                    'TradingDesk':'trading_desk',
                    'Product Class':'lote45_product_class',
                    'Product':'lote45_product',
                    'Book':'book',
                    'Currency':'currency',
                    'Financial Price':'financial_price',
                    'Price':'price',
                    'Amount':'amount',
                    'Position PL': 'position_pnl',
                    'Trades PL': 'trading_pnl',
                    'PL': 'pnl',
                    'Position': 'position'},
                   axis=1)
    
    str_sql = f"""
            DELETE FROM lote45.position
            WHERE date_reference='{dt:%Y-%b-%d}'
            """
    connection.execute(str_sql)
    df.to_sql("position", 
                 connection, 
                 schema='lote45', 
                 if_exists='append', 
                 index=False)
    print(f"Upload Lote45 position - Fund - Inserted {len(df)} row(s) for date {dt}")
        

#%%    
if __name__ == "__main__":
    
    dt = datetime.date(2022, 5, 26)
    main(dt) 
      