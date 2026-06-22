import pandas as pd
import numpy as np
import datetime
import sqlalchemy as sa
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


import os, sys
str_onedrive = '\\OneDrive' if os.path.exists(os.path.expanduser('~\\OneDrive')) else ''
path_github = os.path.expanduser('~{}\\Documents\\Github'.format(str_onedrive))
sys.path.insert(1, path_github + '\\risk_report\\src')
import fund_utils as fu
del str_onedrive, path_github

funds = {'A1 Master FIM': [fu.color_palette[1], (0.8, 0.8)],
         'A1 Orange FIM': ['darkorange', (0.8, 0.4)]}

dt_ini = datetime.date(2021, 3, 15)
dt = datetime.date.today()
dt = datetime.date(2021, 11, 30)

engine = sa.create_engine('mssql+pyodbc://reader:ax5yYwWd@srvprod1.database.windows.net,1433/dbprod1?driver=SQL+Server+Native+Client+11.0')
connection = engine.connect()

str_sql =   """ 
         SELECT b.[date_reference], b.[trading_desk], b.book, [measure], sum([value]/n.NAV_D1) as PnL_Perc  
         FROM [lote45].[book_overview] b  
           		INNER JOIN middle.NAV n ON n.date_reference = b.date_reference and n.trading_desk = b.trading_desk
        WHERE [measure] = 'PL' and b.date_reference BETWEEN '{:%Y-%m-%d}' AND '{:%Y-%m-%d}'
            and b.[trading_desk] in ('{}')
        GROUP BY b.[date_reference],b.[trading_desk], b.book,[measure] 
        """
df = pd.read_sql(str_sql.format(dt_ini, dt, "','".join(funds.keys())) , connection)

trees = ['Traders', 'Risk']
dic_tree = {}
for str_tree in trees:
    str_sql = """
           SELECT [parent_tree],[parent_node],[node],[book]
           FROM [lote45].[book_tree]
           WHERE parent_tree = '{}'
                    """
    dfTree = pd.read_sql(str_sql.format(str_tree), connection)
    nd = fu.Node(str_tree, dfTree)    
    dic_tree[str_tree] = nd.to_dict(str_tree)    



connection.close()
del str_sql, connection, engine, nd, dfTree, str_tree

#%%
df['risk'] = df['book'].apply(lambda x: [i for (i, j) in dic_tree['Risk'].items() if x in j][0])
df['trader'] = df['book'].apply(lambda x: [i for (i, j) in dic_tree['Traders'].items() if x in j][0])

#%%
dic_ret={}
dic_price={}
for i in ['risk', 'trader']:
    dic_ret[i] = df.pivot_table(index='date_reference', columns=['trading_desk',i], values='PnL_Perc', aggfunc=np.sum).fillna(0)
    dic_price[i] = (1+dic_ret[i]).cumprod()
    dic_price[i] = dic_price[i] / dic_price[i].iloc[0] - 1
#%%
fig, axes = plt.subplots(3,3, figsize=(12,8), sharex=True, sharey=False)
fig.tight_layout()

for ax, risk in zip(axes.flatten(), dic_tree['Risk'].keys()):
    for f, v in funds.items():
        if (f, risk) in dic_price['risk'].columns:
            ax.plot(dic_price['risk'].index, dic_price['risk'][(f, risk)], label=f, color=v[0], lw=2.3)
            
            ax.annotate('{:5.0f}'.format(dic_price['risk'][(f, risk)].iloc[-1]*10000),
                  xy=(dic_price['risk'].index[-1], dic_price['risk'][(f, risk)].iloc[-1]), xycoords='data',
                  xytext=v[1], textcoords='axes fraction', fontweight='bold',
                  size=11, va="center", ha="center", color='k', zorder=5,
                  bbox=dict(boxstyle="round", fc=v[0], ec='None', alpha=0.4),
                  arrowprops=dict(arrowstyle="->",
                                  connectionstyle="arc3,rad=-0.2",
                                  fc="w"),
                  )
            
            
            
           
    ax.grid(ls='--')
    ax.axhline(0, lw=0.5, color='k')
    ax.set_title(risk)
    ax.set_yticks(ax.get_yticks().tolist())
    ax.set_yticklabels(['{:2.0f}'.format(10000*x) for x in ax.get_yticks()])
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d\n%b'))

axes[0,0].set_xlim(left=dic_price['risk'].index[0])
axes[0,0].legend()
axes[1,0].set_ylabel('PnL Acumulado (BPs)')
file1 = '../output/temp_figs/{:%Y%m%d}_pnl_1.pdf'.format(dt)
fig.savefig(file1, bbox_inches = "tight")

plt.show()
del risk        
#%%
fig, axes = plt.subplots(3,3, figsize=(12,8), sharex=True, sharey=False)
fig.tight_layout()

for ax, trader in zip(axes.flatten(), dic_tree['Traders'].keys()):
    for f in funds.keys():
        if (f, trader) in dic_price['trader'].columns:
            ax.plot(dic_price['trader'].index, dic_price['trader'][(f, trader)], label=f)
    ax.grid(ls='--')
    ax.axhline(0, lw=0.5, color='k')
    ax.set_title(trader)
    ax.set_yticks(ax.get_yticks().tolist())
    ax.set_yticklabels(['{:2.1f}'.format(10000*x) for x in ax.get_yticks()])
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d\n%b'))
    
axes[0,0].legend()
axes[1,0].set_ylabel('PnL Acumulado (BPs)')
file2 = '../output/temp_figs/{:%Y%m%d}_pnl_2.pdf'.format(dt)
fig.savefig(file2, bbox_inches = "tight")

plt.show()
del trader

#%%
from PyPDF2 import PdfFileMerger

merger = PdfFileMerger()
for f in [file1, file2]:
    merger.append(f)

merger.write('../output/temp_figs/{:%Y%m%d}_pnl_diff.pdf'.format(dt))
merger.close()
