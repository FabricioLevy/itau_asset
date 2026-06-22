import pandas as pd
import numpy as np
import datetime
import QuantLib as ql

import sys
sys.path.insert(1, '..')
import fund_utils as fu

#%%
def main(dt, str_fund): 
#%%
    _ , connection = fu.get_DB_conn('prod')
    
    dt1 = ql.Brazil(ql.Brazil().Exchange).advance(ql.Date.from_date(dt), ql.Period("1d")).to_date()
    
    str_sql = f"""
                SELECT (abs([delta])) as gross_delta
                FROM [lote45].[primitive]
                WHERE date_reference = '{dt:%Y-%m-%d}'
                    AND trading_desk = '{str_fund}'
                    AND lote45_product in (SELECT [lote45_product]
                                           FROM [middle].[product]
                                           WHERE lote45_product_class = 'CPM Options - BMF'
                                               AND date_maturity = '{dt1:%Y-%m-%d}' )
    """
    dfCheck = pd.read_sql(str_sql, connection)
    if len(dfCheck) != 0:
        
        str_sql = """
            SELECT [primitive1],[primitive2],[covar_value]
            FROM [lote45].[covar_matrix]
            WHERE date_reference = '{:%Y-%m-%d}' 
            ORDER BY 1, 2
            """
        str_sql = str_sql.format(dt)
        df = pd.read_sql(str_sql, connection)
        dfCovarDB = df.pivot(index='primitive1', columns='primitive2', values='covar_value').fillna(0)
       
        str_sql = f"""
            SELECT [date_reference],[trading_desk],[book],[primitive],'delta' as greek,[delta] as w
                FROM [lote45].[primitive]
                WHERE date_reference = '{dt:%Y-%m-%d}' 
                   AND trading_desk = '{str_fund}'
                   AND lote45_product not in (SELECT [lote45_product]
                                              FROM [middle].[product]
                                              WHERE lote45_product_class = 'CPM Options - BMF'
                                                  AND date_maturity = '{dt1:%Y-%m-%d}' )
                   UNION
            SELECT [date_reference],[trading_desk],[book],'Vol ' + [primitive],'vega',[vega] as w
                FROM [lote45].[primitive]
                WHERE date_reference = '{dt:%Y-%m-%d}' AND trading_desk = '{str_fund}'
                    AND primitive in ('IBVSP','USDBRLSpot') AND vega<>0
          """
        dfPos = pd.read_sql(str_sql, connection)
        
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
        print(f"Updated VaR of {len(dfVaR):2.0f} books of fund '{str_fund}' due to CPM Opt")
    else:
        print("No CPM Option expiring today!")
    
    connection.close()
    
#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 3, 16)
    for str_fund in ['A1 Master FIM', 'A1 FIFE BEM', 'A1 Orange FIM']:
        main(dt, str_fund)
        