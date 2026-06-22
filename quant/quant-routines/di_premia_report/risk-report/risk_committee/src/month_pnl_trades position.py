import pandas as pd
import numpy as np
import datetime
import calendar
import QuantLib as ql
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import seaborn as sns

color1, color2 ='#28829B', '#323E48'

import os, sys
path_github = os.path.expanduser('~\\Documents\\Github')
sys.path.insert(1, path_github + '\\risk_report\\src')
import fund_utils as fu

########################
month, year = 11, 2022
########################

str_fund = 'A1 Master FIM'
mtd = datetime.date(year, month, 1)
dt_end = datetime.date(year, month, calendar.monthrange(year, month)[-1])

itd = datetime.date(2020, 4, 1)

_, connection = fu.get_DB_conn('prod')

str_sql =   f""" 
       SELECT b.[date_reference], b.book, b.[lote45_product_class],
              b.[lote45_product], measure, sum([value]/n.NAV_D1) as PnL_Perc  
         FROM [lote45].[book_overview] b  
           		INNER JOIN middle.NAV n 
                   ON n.date_reference = b.date_reference 
                      and n.trading_desk = b.trading_desk
        WHERE [measure] in ('PL', 'Trades PL', 'Position PL' )
            and b.date_reference between '{mtd:%Y-%m-%d}' and '{dt_end:%Y-%m-%d}' 
            and b.[trading_desk] = '{str_fund}'
        GROUP BY b.[date_reference], b.book, b.[lote45_product_class], b.[lote45_product], measure
        """
df = pd.read_sql(str_sql.format(dt_end, str_fund) , connection)
dt_end = df['date_reference'].max()

str_tree = 'Traders'
str_sql = """
       SELECT [parent_tree],[parent_node],[node],[book]
       FROM [lote45].[book_tree]
       WHERE parent_tree = '{}'
                """
dfTree = pd.read_sql(str_sql.format(str_tree), connection)

str_tree2 = 'PerformanceAttribution'
str_sql = """
       SELECT [parent_tree],[parent_node],[node],[book]
       FROM [lote45].[book_tree]
       WHERE parent_tree = '{}'
                """
dfTree2 = pd.read_sql(str_sql.format(str_tree2), connection)

str_sql="""
    SELECT  [lote45_product_class] ,[risk_product],[perf_att_class]
  FROM [lote45].[product_class]
"""
dfProduct = pd.read_sql(str_sql, connection, index_col='lote45_product_class')

connection.close()
del str_sql, connection

#%%
nd = fu.Node(str_tree, dfTree)    
dic_books = nd.to_inv_dict(str_tree)    
del nd, dfTree, str_tree

nd = fu.Node(str_tree2, dfTree2)    
dic_books2 = nd.to_inv_dict(str_tree2)    
del nd, dfTree2, str_tree2

dfRiskShare = fu.get_DailyRiskShare(dt_end, str_fund)

df['Trader'] = df['book'].apply(lambda x: dic_books[x])
df['Risk'] = df['book'].apply(lambda x: dic_books2[x])

df['product'] = df['lote45_product_class'].apply(lambda x: dfProduct['risk_product'].get(x, x))

df.loc[(df['Risk']=='Cupom Cambial') & (df['product']=='FX'), 'product'] = 'Cp Cambial'
df.loc[(df['Risk']=='Caixa_Outros') & (df['product']=='Cp Cambial'), 'product'] = 'Cash/Costs'

#%%
dfTraderPnL = df.pivot_table(index='date_reference', 
                             columns=['Trader', 'measure'], 
                             values='PnL_Perc', 
                             aggfunc=np.sum).fillna(0)

traders = dfRiskShare.loc[dt_end].to_dict()
cols = [c for c in sorted(traders.keys(), key=traders.get) if (traders[c] > 0) and c!='Fund']

for c in cols:
    for j in dfTraderPnL[c].columns:
        dfTraderPnL[(c, j)] /= dfRiskShare.loc[dfTraderPnL.index, c]
    

dfTraderPnL = ((dfTraderPnL+1).prod()-1)*10_000


#%%
fig, axes = plt.subplots(1, 
                         len(cols), 
                         figsize=(14, 4),
                         sharey=True)

for c, ax in zip(cols, axes.flatten()):
    dfPlot = dfTraderPnL.loc[c]
    dfPlot.plot.bar(ax=ax, zorder=3, color=[color2, color1, color1])
    ax.set_title(c, fontweight='bold')
    ax.axhline(0, ls='-', c='k', lw=0.7)
    ax.grid(ls='--', axis='y')
    ax.set_xlabel('')
    for j, v in enumerate(dfPlot.values):
        ax.text(j, max(v,0), f"{v:+2.0f}", ha='center', va='bottom',
                fontweight='bold', c='r' if v<0 else 'k')


#%%
fig_file = '../tex/{0:%Y_%m}/figuras/{0:%Y%m}_{1}_pnl_trade_position.pdf'.format(mtd, str_fund)
fig.savefig(fig_file, bbox_inches = "tight")
plt.show()