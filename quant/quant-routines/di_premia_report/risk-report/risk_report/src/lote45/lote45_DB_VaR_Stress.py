import pandas as pd
import datetime
import QuantLib as ql

from a1db.a1sql import SQLConnection  

#%%
def main(dt):
#%%
    connection = SQLConnection().get_connection()  
    str_path = "R:/Risk/01_DailyReports/01_01_Lote45_extract/"
    
    #%%
    file_var_stress = f"FundVaRStress_{dt:%d%b%Y}.txt"
    str_tree = 'Fund'
    df = pd.read_csv(str_path + str_tree + '/' + file_var_stress, 
                     sep='\t', 
                     parse_dates=[], 
                     encoding='UTF-8')
    
    dfVaR = df.groupby(['TradingDesk'])['PVaR 1 Day'].sum().reset_index()
    dfVaR['risk_measure'] = 'VaR'
    dfVaR = dfVaR.rename({'TradingDesk':'trading_desk',
                          'PVaR 1 Day': 'value'}, 
                         axis=1)
    
    dfStress = df[['TradingDesk','Stress Macro', 'Stress Specific']].groupby(['TradingDesk']).sum().reset_index()
    dfStress['value'] = dfStress[['Stress Macro', 'Stress Specific']].sum(axis=1)
    dfStress['risk_measure'] = 'Stress'
    dfStress = dfStress.rename({'TradingDesk':'trading_desk'},
                               axis=1)
    
    dfSQL = pd.concat([dfVaR[['trading_desk', 'value', 'risk_measure']],
                       dfStress[['trading_desk', 'value', 'risk_measure']]])
    del dfVaR, dfStress, df
    dfSQL['date_reference'] = dt
    dfSQL['parent_tree'] = 'Fund'
    dfSQL['node'] = 'Fund'
    
    dfSQL = dfSQL[['date_reference', 'trading_desk','parent_tree', 'node', 'risk_measure', 'value']]
    
    str_sql = f"""
            DELETE FROM risk.measure 
            WHERE risk_measure in ('VaR', 'Stress')
                and date_reference='{dt:%Y-%b-%d}'
                and parent_tree='Fund'
            """
    connection.execute(str_sql)
    dfSQL.to_sql("measure", 
                 connection, 
                 schema='risk', 
                 if_exists='append', 
                 index=False)
    print(f"Upload VaR/Stress Lote45 - Fund - Inserted {len(dfSQL)} row(s) for date {dt}")
        
    #%%
    file_var = f"BooksPrimitivesVaR_{dt:%d%b%Y}.txt"
    file_stress = f"BookPrimitivesStressReport_{dt:%d%b%Y}.txt"

    tree_list = ['Risk', 'Traders']
    if ql.Brazil().isEndOfMonth(ql.Date.from_date(dt)):
        print("\n !! Reminder: It's month end, export the files for Itau DDQ form !!\n")
        tree_list.append('Itau')
        
    for str_tree in tree_list:        
        dfVaR = pd.read_csv(str_path + str_tree + '/' + file_var, sep='\t', parse_dates=[], encoding='UTF-8')
        
        dfVaR = dfVaR.groupby(['TradingDesk', 'Book'])['Relative VaR 1D'].sum().reset_index()
        dfVaR['risk_measure'] = 'VaR'
        dfVaR = dfVaR.rename({'TradingDesk':'trading_desk',
                              'Book':'node',
                              'Relative VaR 1D':'value'}, 
                              axis=1)
        
        dfStress = pd.read_csv(str_path + str_tree + '/' + file_stress, sep='\t', parse_dates=[], encoding='UTF-8')
        
        dfStress = dfStress[['TradingDesk', 'Book','Stress']].groupby(['TradingDesk', 'Book']).sum().reset_index()
        dfStress['risk_measure'] = 'Stress'
        dfStress = dfStress.rename({'TradingDesk':'trading_desk',
                                    'Stress':'value',
                                    'Book':'node'},
                                   axis=1)
        
        dfSQL = pd.concat([dfVaR[['trading_desk', 'node', 'value', 'risk_measure']],
                           dfStress[['trading_desk', 'node', 'value', 'risk_measure']]])
        del dfVaR, dfStress
        dfSQL['date_reference'] = dt
        dfSQL['parent_tree'] = str_tree
        
        dfSQL = dfSQL[['date_reference', 'trading_desk','parent_tree', 'node', 'risk_measure', 'value']]
        
        str_sql = f"""
            DELETE FROM risk.measure 
            WHERE risk_measure in ('VaR', 'Stress')
                and date_reference='{dt:%Y-%b-%d}'
                and parent_tree='{str_tree}'
            """
        connection.execute(str_sql)
        dfSQL.to_sql("measure",
                     connection,
                     schema='risk',
                     if_exists='append',
                     index=False)
        print(f"Upload VaR/Stress Lote45 - {str_tree} - Inserted {len(dfSQL)} row(s) for date {dt}")
    

#%%    
if __name__ == "__main__":
    
    dt = datetime.date(2022, 7, 14)
    main(dt) 
      