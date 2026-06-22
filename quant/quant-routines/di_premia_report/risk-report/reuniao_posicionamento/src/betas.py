import pandas as pd
import numpy as np
import datetime
import QuantLib as ql
import sqlalchemy as sa
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.dates as mdates

import sys
sys.path.insert(1, '../../risk_report/src')
import fund_utils as fu

str_fund = 'A1 Master FIM'

dt = datetime.date(2021, 3, 9)
today = ql.Date.from_date(dt)
lastweek = ql.Brazil().advance(today, ql.Period('-1w'))
lastmonth = ql.Brazil().advance(today, ql.Period('-1m'))
last6month = ql.Brazil().advance(today, ql.Period('-6m'))


engine = sa.create_engine('mssql+pyodbc://reader:ax5yYwWd@srvprod1.database.windows.net,1433/dbprod1?driver=SQL+Server+Native+Client+11.0')
connection = engine.connect()    
    
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
    SELECT [date_reference],[trading_desk],book, [lote45_product_class],[lote45_product],
        [primitive],'delta' as greek,[delta] as w
        FROM [lote45].[primitive]
        WHERE date_reference = '{0:%Y-%m-%d}' AND trading_desk = '{1:}'
    UNION
    SELECT [date_reference],[trading_desk],book,[lote45_product_class],[lote45_product],'Vol ' + [primitive],'vega',[vega] as w
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
connection.close()


#%%
ic_var = 1.64485362695147

X = dfCovarDB.values
X = np.triu(X) + np.tril(X, -1).T
dfCovar = pd.DataFrame(np.triu(X) + np.tril(X.T, -1), columns=dfCovarDB.index, index=dfCovarDB.index)
# del X, dfCovarDB

dfW = dfPos.pivot_table(index='primitive', columns='book', values='w', aggfunc=np.sum).fillna(0)
dfW=dfW.drop('BRAZIL ONSHORE SPREAD')
covar = dfCovar[dfW.index].loc[dfW.index].values
dfW['TOTAL'] = dfW.sum(axis=1).values
w = dfW['TOTAL'].values
dfW['beta_cvar'] = (covar @ w) / (w.T @ covar @ w)

for rf in ['IBVSP', 'DI_01800', 'USDBRLSpot']:
    for i in dfW.index:
        dfW.loc[i, 'beta_' + rf] = dfCovar.loc[i, rf]/dfCovar.loc[rf, rf]

#%%
var = np.sqrt(w.T @ covar @ w) * ic_var

for str_tree, dic_books in dic_trees.items():
    for k, v in dic_books.items():
        dfW[k] = dfW[[i for i in v if i in list(dfW.columns)]].sum(axis=1)

#%%



