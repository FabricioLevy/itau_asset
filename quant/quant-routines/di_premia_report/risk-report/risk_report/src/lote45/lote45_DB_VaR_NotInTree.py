import pandas as pd
import datetime
import numpy as np

from a1db.a1sql import SQLConnection

import os, sys
sys.path.insert(1, os.path.expanduser('~\\Documents\\Github') + '\\risk_report\\src')
import fund_data

def main(data):
#%%
    str_fund = data._fund
    dt = data._dt

    dfOutput=pd.DataFrame(columns=['date_reference','trading_desk','parent_tree',
                                   'node','risk_measure','value'])
    
    trees = [['geo'], ['Traders', 'TraderMandate'], ['TraderMandate']]
    parents = ['Geography', 'Trader Mandate', 'Fund Mandate']
    
    ic_var = 1.64485362695147
    
    temp_df_w = data._w.replace({True:'Onshore',
                                 False:'Offshore'}).copy()
    
    i = 0
    for tree, parent_tree in zip(trees, parents):
        df_w = temp_df_w.pivot_table(index='primitive',
                                     columns=tree,
                                     values='w',
                                     aggfunc=np.sum).fillna(0)
        covar_index = [i for i in df_w.index if i in data._dfCovar.index]
        for c in df_w.columns:
            w = df_w.loc[covar_index, c].values
            covar = data._dfCovar.loc[covar_index, covar_index].values
            var = -np.sqrt(w.T @ covar @ w) * ic_var
            dfOutput.loc[i, 'date_reference'] = dt
            dfOutput.loc[i, 'trading_desk'] = str_fund
            dfOutput.loc[i, 'parent_tree'] = parent_tree
            dfOutput.loc[i, 'node'] = c if len(tree) == 1 else " ".join(c)
            dfOutput.loc[i, 'risk_measure'] = 'VaR'
            dfOutput.loc[i, 'value'] = var
            i += 1
            
   
    connection = SQLConnection().get_connection()     
    str_sql = f"""
                DELETE FROM risk.measure 
                WHERE risk_measure = 'VaR'
                    AND date_reference='{dt:%Y-%b-%d}'
                    AND trading_desk='{str_fund}'
                    and parent_tree in ('{"','".join(parents)}')
                """
    connection.execute(str_sql)
    dfOutput.to_sql("measure",
                    connection,
                    schema='risk',
                    if_exists='append',
                    index=False)
    print(f"Upload VaR in ({', '.join(parents)}) - {str_fund} - Inserted {len(dfOutput)} row(s) for date {dt}")
            
        
#%%    
    
if __name__ == "__main__":

    dt = datetime.date(2022, 10, 24) 
    funds = [
            'A1 Master FIM', 
            'A1 Orange FIM',
            'A1 FIFE BEM', 
            'A1 FIFE ITAU'
              ] 
    
    for str_fund in funds:
        data = fund_data.db_data(dt, str_fund, verbose=False)
        main(data)

    # tic = datetime.datetime.now()
    # err_dates = []
    # import QuantLib as ql
    # dt_ini = ql.Date(19,10, 2022)
    # dt_ini = ql.Brazil().adjust(dt_ini)
    # while dt_ini <= ql.Date(24, 10, 2022):
    #     tac = datetime.datetime.now()
    #     print(dt_ini.ISO(), tac-tic)
    #     for f in funds:
    #         try:
    #             data = fund_data.db_data(dt_ini.to_date(), f, verbose=False, loadHist=False)
    #             main(data) 
    #         except Exception as err:
    #             err_dates.append(dt_ini.to_date())
    #             print('==> ', dt_ini.ISO(), err)
            
    #     dt_ini = ql.Brazil().advance(dt_ini, ql.Period('1d'))




