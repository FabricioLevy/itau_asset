#%% 
import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

import os, sys
path_fund = os.path.expanduser('~\\Documents\\Github\\risk_report\\src')
sys.path.insert(1, path_fund)
import fund_utils as fu 

dt = datetime.date(2021, 5, 7)

#%%
_, connection = fu.get_DB_conn('prod')
   
str_tree = 'Traders'
str_sql = """
          SELECT [parent_tree],[parent_node],[node],[book]
          FROM [lote45].[book_tree]
          WHERE parent_tree = '{}'
   """
dfTree = pd.read_sql(str_sql.format(str_tree), connection)
nd = fu.Node(str_tree, dfTree)    
dic_books = nd.to_dict(str_tree)
inv_books = {}
for k, v in dic_books.items():
   for vi in v:
       inv_books[vi] = k


str_sql = """
         SELECT p.[trading_desk],[book],[primitive],[primitive_class]     
                 ,sum([delta]/n.NAV) as delta_perc
        FROM [lote45].[primitive] p 
            INNER JOIN middle.nav n 
                ON p.date_reference = n.date_reference 
                    and p.trading_desk = n.trading_desk
        WHERE p.date_reference = '{:%Y-%m-%d}' 
        GROUP BY p.[trading_desk] ,[book] ,[primitive] ,[primitive_class]
   """
str_sql = str_sql.format(dt)   
df = pd.read_sql(str_sql, connection)
df['Trader'] = df['book'].apply(lambda x: inv_books[x])
  
connection.close()
del str_sql, connection, nd, dfTree, str_tree, k, v, vi
#%%
list_pv01 = ['BRL Rate Curve', 'BRD Rate Curve', 'IPCA Coupon']
dic_curvename = {'BRL Rate Curve': 'Taxa Pré',\
                     'IPCA Coupon':'Cp IPCA',\
                     'USA Sovereign Yield': 'US', \
                    'BRD Rate Curve':'Cp Cambial',\
                     'MXN Rate Curve': 'MX'}
dfMS = df[df['Trader']=='MS'].copy()
dfMS['risco'] = dfMS.apply(lambda x: x['primitive_class'] if x['primitive_class'] in list_pv01 else x['primitive'],  axis=1 )
dfMS['risco'] = dfMS['risco'].apply(lambda x: dic_curvename.get(x, x))
dfMS['risco'] = dfMS.apply(lambda x: x['primitive'][0:6] if x['primitive_class']=='FX' else x['risco'], axis=1)
dfMS['classe'] = dfMS['primitive_class'].apply(lambda x: 'Juros' if x in list_pv01 else x)
#%%
dfPivot = dfMS.pivot_table(index=['classe','risco'], columns='trading_desk', values='delta_perc', aggfunc=np.sum).fillna(0)
#dfPivot.loc[['Juros','FX','Equity']]
#%%
fig, ax = plt.subplots(1,1, figsize=(6, 2))
ax.axis('off')
ax.set_title("Posição MS: {:%d-%b-%Y}".format(dt), fontsize=11, weight='bold')
dfTable = dfPivot.loc[['Juros','FX','Equity']]
table = ax.table(cellText=dfTable.applymap('{:,.1%}'.format).values,
         rowColours=['silver']*len(dfTable), colColours=['silver']*len(dfTable.columns),
                  rowLabels=['{:>10}: {:15}'.format(a,b) for (a,b) in dfTable.index],
                  colLabels=dfTable.columns,loc='center', cellLoc='center')

for i, ind in enumerate(dfTable.index):
    for j, col in enumerate(dfTable.columns):
        my_cell = table[i+1,j]
        if float(my_cell.get_text().get_text().replace("%",""))<0:
            my_cell.get_text().set_color('r')
        elif float(my_cell.get_text().get_text().replace("%",""))==0:
            my_cell.get_text().set_text('-')
        