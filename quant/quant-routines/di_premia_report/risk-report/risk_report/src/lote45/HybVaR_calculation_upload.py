import pandas as pd
import datetime

from a1db.a1sql import SQLConnection

import os, sys
sys.path.insert(1, os.path.expanduser('~\\Documents\\Github') + '\\risk_report\\src')
import fund_data
import fund_utils as fu


def main(dt, str_fund):
#%%
    data = fund_data.db_data(dt, str_fund, verbose=False)
    
    dfOutput=pd.DataFrame(columns=['date_reference','trading_desk','parent_tree',
                                   'node','risk_measure','value'])
    
    trees = ['Risk', 'Traders']
    i = 0
    for str_tree in trees:
        hypo_pnl = data._dic_hypoPnL[str_tree].join(data._ewmaWeight)
        cols = list(hypo_pnl.columns)
        cols.remove('ewma_weight')
        cols.remove('Fund')
        for c in cols:
            var_b = hypo_pnl[(hypo_pnl.sort_values(c)['ewma_weight'].expanding().sum() <= 0.05).sort_index()][c].iloc[-1]
            dfOutput.loc[i, 'date_reference'] = dt
            dfOutput.loc[i, 'trading_desk'] = str_fund
            dfOutput.loc[i, 'parent_tree'] = str_tree
            dfOutput.loc[i, 'node'] = c
            dfOutput.loc[i, 'risk_measure'] = 'Hyb VaR'
            dfOutput.loc[i, 'value'] = var_b
            i += 1
    c = 'Fund'
    var_b = hypo_pnl[(hypo_pnl.sort_values(c)['ewma_weight'].expanding().sum() <= 0.05).sort_index()][c].iloc[-1]
    dfOutput.loc[i, 'date_reference'] = dt
    dfOutput.loc[i, 'trading_desk'] = str_fund
    dfOutput.loc[i, 'parent_tree'] = c
    dfOutput.loc[i, 'node'] = c
    dfOutput.loc[i, 'risk_measure'] = 'Hyb VaR'
    dfOutput.loc[i, 'value'] = var_b
    
    connection = SQLConnection().get_connection()     
    str_sql = f"""
                DELETE FROM risk.measure 
                WHERE risk_measure = 'Hyb VaR'
                    AND date_reference='{dt:%Y-%b-%d}'
                    AND trading_desk='{str_fund}'
               """
    connection.execute(str_sql)
    dfOutput.to_sql("measure",
                    connection,
                    schema='risk',
                    if_exists='append',
                    index=False)
    print(f"Upload Hyb VaR - {str_fund} - Inserted {len(dfOutput)} row(s) for date {dt}")
            
        
#%%    
    
if __name__ == "__main__":

    dt = datetime.date(2022, 9, 14) 
    funds = ['A1 Master FIM', 
             'A1 Orange FIM',
             'A1 FIFE BEM', 
              'A1 FIFE ITAU'
             ] 
    
    for str_fund in funds:
        nav = fu.get_NAV(dt, str_fund)        
        main(dt, str_fund)

#%%
    # import QuantLib as ql
    # dt_ini = ql.Date(30, 3, 2022)    
    # while dt_ini > ql.Date(1,1,2022):
    #     print(f"\n{dt_ini}\n")
    #     dt = dt_ini.to_date()
    #     for str_fund in funds:
    #         nav = fu.get_NAV(dt, str_fund)
    #         data = fund_data.db_data(dt, str_fund, verbose=True)
    #         main(data, dt, str_fund)
    #     dt_ini = ql.Brazil().advance(dt_ini, ql.Period('-1d'))





