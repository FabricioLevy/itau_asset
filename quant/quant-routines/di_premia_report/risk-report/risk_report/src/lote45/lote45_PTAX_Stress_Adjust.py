import pandas as pd
import numpy as np
import datetime

import sys
sys.path.insert(1, '..')
import fund_utils as fu

#%%
def main(dt, str_fund): 
#%%
    engine, connection = fu.get_DB_conn('prod')    
    
    tree_list = ['Risk', 'Main', 'Traders']
    str_path = "R:/Risk/01_DailyReports/01_01_Lote45_extract/"
    
    for str_tree in tree_list:
        str_file = "BooksVaRStress_{:%d%b%Y}.txt".format(dt)
        dfLote45 = pd.read_csv(str_path + str_tree + '/' + str_file, sep='\t', parse_dates=[1,5], encoding='UTF-8')
        
        # dfLote45 = dfLote45[dfLote45.USDBRLPTAX == 0]
        
        dfLote45 = dfLote45[['TradingDesk', 'ValDate', 'Book', 'Stress Macro', 'Stress Specific']]
        dfStress = dfLote45.groupby(['TradingDesk', 'ValDate', 'Book']).sum().reset_index()
        dfStress['value'] = dfStress.sum(axis=1)
    
        dfStress = dfStress[['ValDate','TradingDesk', 'Book', 'value']]
        dfStress = dfStress.rename({'ValDate': 'date_reference',\
                                    'TradingDesk':'trading_desk',\
                                    'Book':'node'}, axis=1)
        dfStress.insert(2, 'parent_tree', str_tree)
        dfStress.insert(4, 'risk_measure', 'Stress')
        dfStress = dfStress[dfStress['value']!=0]

        connection.execute("DELETE FROM risk.measure WHERE risk_measure='Stress' "+\
                           "and date_reference='{:%Y-%b-%d}' and parent_tree='{}'".format(dt, str_tree))
        dfStress.to_sql("measure", engine, schema='risk', if_exists='append', index=False)
        print('Upload Stress Lote45 - Tree: {} - Inserted {} row(s) for date {}'.format(str_tree, len(dfStress), dt))
     
    #%%  
    str_file = "Main/FundVaRStress_{:%d%b%Y}.txt".format(dt)
    dfLote45Fund= pd.read_csv(str_path + str_file, sep='\t', parse_dates=[5],encoding='UTF-8')
    
    dfLote45Fund = dfLote45Fund[['TradingDesk', 'ValDate', 'Stress Macro', 'Stress Specific']]
    dfStress = dfLote45Fund.groupby(['TradingDesk', 'ValDate']).sum().reset_index()
    dfStress['value'] = dfStress.sum(axis=1)
    
    dfStress = dfStress[['ValDate','TradingDesk', 'value']]
    dfStress = dfStress.rename({'ValDate': 'date_reference',\
                                    'TradingDesk':'trading_desk'}, axis=1)
    dfStress.insert(2, 'parent_tree', 'Fund')
    dfStress.insert(3, 'node', 'Fund')
    dfStress.insert(4, 'risk_measure', 'Stress')
    dfStress = dfStress[dfStress['value']!=0]
    
    connection.execute("DELETE FROM risk.measure WHERE risk_measure='Stress' "+\
                           "and date_reference='{:%Y-%b-%d}' and parent_tree='Fund'".format(dt))
    dfStress.to_sql("measure", engine, schema='risk', if_exists='append', index=False)
    print('Upload Stress Lote45 - Fund - Inserted {} row(s) for date {}'.format(len(dfStress), dt))

#%%
if __name__ == "__main__":
    
    dt = datetime.date(2021, 8, 31)
    str_fund = 'A1 Master FIM'
    x = main(dt, str_fund) 
