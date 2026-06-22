# -*- coding: utf-8 -*-
"""
Created on Mon Oct  3 10:21:09 2022

@author: matheus.amaral
"""

import pandas as pd
import os
from a1db.a1sql import SQLConnection
from datetime import date

def main(dt):
    connection = SQLConnection().get_connection()
    
    path = os.path.expanduser('~\Documents\GitHub\market_data\input')
    file = f'Equity Options-{dt:%d%b%Y}.txt'
    
    try:
        dfLote = pd.read_csv(os.path.join(path,file), sep = '\t')
    
    except:
        print('\nNão foi encontrado o arquivo de opções.')
        
    else:
        dfLote.rename({'Product':'id',
                       'Strike':'option_strike'}, 
                      axis = 1, inplace = 'True')
        
        ids = "','".join(dfLote['id'])
        
        str_sql = f"""
                SELECT id,
                    option_strike
                FROM middle.product
                WHERE id IN ('{ids}')
                """
        dfProd = pd.read_sql(str_sql, connection)
        
        dfProd = dfProd.merge(dfLote[['id', 'option_strike']], on = 'id', suffixes = ['_old', '_new'])
        
        dfProd['dif'] = round(dfProd['option_strike_old'] - dfProd['option_strike_new'],2)
        
        dfUpdate = dfProd[dfProd['dif'] != 0 ][['id', 'option_strike_new']]
        
        if not dfUpdate.empty:
            for prod, strike in dfUpdate.values:
                
                str_sql = f""""
                        UPDATE middle.product
                        SET option_strike = '{strike}'
                        WHERE id = '{prod}'
                        """
                connection.execute(str_sql)
                print(f'\nStrike atualizado: {prod}')
        
        else:
            print("\nSem strikes para serem atualizados")    
            
#%%

if __name__ == '__main__':
    
    dt = date(2022,9,29)
    main(dt)