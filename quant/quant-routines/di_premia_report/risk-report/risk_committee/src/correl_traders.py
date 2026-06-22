import pandas as pd
import numpy as np
import datetime
from a1db.a1sql import SQLConnection
import seaborn as sns
import matplotlib.pyplot as plt

import os, sys
sys.path.insert(1, os.path.expanduser('~\\Documents\\Github') + '\\risk_report\\src')
import fund_utils as fu


connection = SQLConnection().get_connection()


str_fund = 'A1 Master FIM'
str_sql =   f""" 
         SELECT b.[date_reference], b.[trading_desk], b.book, [measure], 
         sum([value]/n.NAV_D1) as PnL
         FROM [lote45].[book_overview] b  INNER JOIN middle.NAV n
             ON b.date_reference = n.date_reference 
                 AND b.trading_desk = n.trading_desk
          WHERE [measure] = 'PL'               
               and b.[trading_desk] = '{str_fund}'
        GROUP BY b.[date_reference],b.[trading_desk], b.book,[measure] 
        """
df = pd.read_sql(str_sql, connection)


str_tree = 'Traders'
dic_tree = {}
str_sql = """
           SELECT [parent_tree],[parent_node],[node],[book]
           FROM [lote45].[book_tree]
           WHERE parent_tree = '{}'
                    """
dfTree = pd.read_sql(str_sql.format(str_tree), connection)
nd = fu.Node(str_tree, dfTree)
dic_tree = nd.to_dict(str_tree)    


df['trader'] = df['book'].apply(lambda x: [i for (i, j) in dic_tree.items() if x in j][0])
dfReturn = df.pivot_table(index='date_reference', columns='trader', values='PnL', aggfunc=np.sum)

cols = ['MS', 'BC', 'GB', 'FK', 'PA', 'TO', 'NF', 'PC']

#%%
for shift in [-3, -6, -9, -12]:

    corr = dfReturn.iloc[:shift*21][cols].corr() * 100
    fig, ax = plt.subplots(figsize=(5, 3))
    mask = np.zeros_like(corr, dtype=np.bool)
    mask[np.triu_indices_from(mask)] = True
    cmap = sns.diverging_palette(10, 260, n=15, as_cmap=True)
    sns.heatmap(corr, mask=mask, cmap=cmap, vmax=100, vmin=-100, center=0, fmt='2.0f',\
                square=False, linewidths=.5, annot = True, cbar=False, ax=ax)
    # ax_divider = make_axes_locatable(ax)
    # cax = ax_divider.append_axes('top', size = '3%', pad = '1%')
    # colorbar(ax.get_children()[0], cax = cax, orientation = 'horizontal')
    # cax.xaxis.set_ticks_position('top')
    ax.yaxis.label.set_visible(False)
    ax.xaxis.label.set_visible(False)
    # ax.set_title('')
    # ax.set_title('Since Inception')
    # ax.set_title('Year To Date (2021)')
    # ax.set_title('Outubro 2021')
    ax.set_title(f"Correlation: {dfReturn.index[shift*21]:%d-%b-%Y} -> Today")
    fig.savefig(f"../output/{dfReturn.index[shift*21]:%Y_%m_%d}_correl.svg", bbox_inches = "tight")
    
    plt.show()