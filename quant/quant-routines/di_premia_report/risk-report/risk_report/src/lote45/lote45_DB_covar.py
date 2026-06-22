import pandas as pd
import numpy as np
import datetime

from a1db.a1sql import SQLConnection
    
def main(dt, funds) :
#%%
    connection = SQLConnection().get_connection() 
    
    str_path = "R:/Risk/01_DailyReports/01_01_Lote45_extract/Fund/"
    
    dic_covar = {}
    for str_fund in funds:
        str_file = "Fund1DayCovarianceTable_{}_{:%d%b%Y}.txt".format(str_fund, dt)    
        dic_covar[str_fund] = pd.read_csv(str_path + str_file, 
                                          sep='\t',
                                          encoding='UTF-8', 
                                          index_col=0)
    
    cols = set([x for df in dic_covar.values() for x in df])
    dfCovar = pd.DataFrame(index=cols, columns=cols)
    for str_fund in funds:
        dfCovar = dfCovar.fillna(dic_covar[str_fund])
    dfCovar = dfCovar.fillna(0)
    
    dfCovar = dfCovar.reindex(sorted(dfCovar.columns), axis=1).sort_index()
    dfCovar_db = dfCovar.where(np.triu(np.ones(dfCovar.shape)).astype(bool))
    dfCovar_db = dfCovar_db.stack().reset_index()
    dfCovar_db.columns = ['primitive1', 'primitive2', 'covar_value']
    dfCovar_db.insert(0,'date_reference', dt)
    
    connection.execute("DELETE FROM lote45.covar_matrix WHERE date_reference='{:%Y-%b-%d}'".format(dt))
    dfCovar_db.to_sql("covar_matrix", 
                      connection,
                      schema='lote45', 
                      if_exists='append', 
                      index=False, 
                      chunksize=100,
                      method='multi')
    print("{:%d-%b-%y} - Primitives Covariances inserted: {} rows".format(dt, len(dfCovar_db)))

#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 4, 29)
    funds = ['A1 Master FIM', 
             'A1 Orange FIM',
             'A1 FIFE BEM', 
             'A1 FIFE ITAU']
    main(dt, funds)