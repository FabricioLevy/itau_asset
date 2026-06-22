import pandas as pd
import numpy as np
import datetime

import sys
sys.path.insert(1, '..')
import fund_utils as fu

#%%
def main(dt, str_fund): 
#%%
    _ , connection = fu.get_DB_conn('prod')
    
    str_sql = """
        SELECT [primitive1],[primitive2],[covar_value]
        FROM [lote45].[covar_matrix]
        WHERE date_reference = '{:%Y-%m-%d}' 
        ORDER BY 1, 2
        """
    str_sql = str_sql.format(dt)
    df = pd.read_sql(str_sql, connection)
    dfCovarDB = df.pivot(index='primitive1', columns='primitive2', values='covar_value').fillna(0)
   
    str_sql = """
        SELECT [date_reference],[trading_desk],[book],[primitive],'delta' as greek,[delta] as w
            FROM [lote45].[primitive]
            WHERE date_reference = '{0:%Y-%m-%d}' AND trading_desk = '{1:}'
        UNION
        SELECT [date_reference],[trading_desk],[book],'Vol ' + [primitive],'vega',[vega] as w
            FROM [lote45].[primitive]
            WHERE date_reference = '{0:%Y-%m-%d}' AND trading_desk = '{1:}'
                AND primitive in ('IBVSP','USDBRLSpot') AND vega<>0
      """
    dfPos = pd.read_sql(str_sql.format(dt, str_fund), connection)
    
    trees = ['Risk', 'Traders']
    dic_trees = {}
    for str_tree in trees:
        str_sql = """
           SELECT [parent_tree],[parent_node],[node],[book]
           FROM [lote45].[book_tree]
           WHERE parent_tree = '{}'
                    """
        dfTemp= pd.read_sql(str_sql.format(str_tree), connection)
        nd = fu.Node(str_tree, dfTemp)
        dic_trees[str_tree] = nd.to_dict(str_tree)   

    del str_sql, dfTemp, nd, str_tree

#%%
    ic_var = 1.64485362695147
    
    X = dfCovarDB.values
    X = np.triu(X) + np.tril(X, -1).T
    dfCovar = pd.DataFrame(np.triu(X) + np.tril(X.T, -1), columns=dfCovarDB.index, index=dfCovarDB.index)
    # del X, dfCovarDB

    dfW = dfPos.pivot_table(index='primitive', columns='book', values='w', aggfunc=np.sum).fillna(0)
    if 'BRAZIL ONSHORE SPREAD' in dfW.index:
        dfW=dfW.drop('BRAZIL ONSHORE SPREAD')
    covar = dfCovar[dfW.index].loc[dfW.index].values

    dfW['Fund'] = dfW.sum(axis=1)
    for str_tree, dic_books in dic_trees.items():
        for k, v in dic_books.items():
            dfW[k] = dfW[[i for i in v if i in list(dfW.columns)]].sum(axis=1)
    #%%
    str_sql = """
       UPDATE [risk].[measure]
       SET value = {}
       WHERE date_reference = '{:%Y-%m-%d}' and trading_desk='{}' 
		and risk_measure='VaR' and [node]='{}'
    """
    dfVaR = pd.DataFrame(columns=['VaR_BRL'])
    for b in dfW.columns:
        w = dfW[b].values
        var = -np.sqrt(w.T @ covar @ w) * ic_var
        dfVaR.loc[b, 'VaR_BRL'] = var
        connection.execute(str_sql.format(var, dt, str_fund, b))
    
    connection.close()
    return dfVaR
#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 4, 29)
    str_fund = 'A1 Master FIM'
    # str_fund = 'A1 FIFE ITAU'
    x = main(dt, str_fund) 
