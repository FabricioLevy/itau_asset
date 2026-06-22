import pandas as pd
import numpy as np
import datetime
import sqlalchemy as sa
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import adjustText

import os, sys
str_onedrive = '\\OneDrive' if os.path.exists(os.path.expanduser('~\\OneDrive')) else ''
path_github = os.path.expanduser('~{}\\Documents\\Github'.format(str_onedrive))
sys.path.insert(1, path_github + '\\risk_report\\src')
import fund_utils as fu
del str_onedrive, path_github

funds = {'A1 Master FIM': [fu.color_palette[1], (0.8, 0.8)],
         'A1 FIFE BEM': ['tomato', (0.8, 0.4)]}

dt_ini = datetime.date(2021, 9, 3)
dt = datetime.date.today()
dt = datetime.date(2022, 4, 5)

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

str_sql = """
SELECT [date_reference],[trading_desk],[share]
  FROM [middle].[NAV]
  WHERE date_reference BETWEEN '{0:%Y-%m-%d}' AND '{1:%Y-%m-%d}' and trading_desk in ('{2}')
  UNION
 SELECT [date_reference],[product_id],[rate]  
  FROM [middle].[product_price]
 WHERE [product_id]='CDI' AND date_reference BETWEEN '{0:%Y-%m-%d}' AND '{1:%Y-%m-%d}'
"""
dfCota = pd.read_sql(str_sql.format(dt_ini, dt, "','".join(funds.keys())) , connection).pivot(index='date_reference', columns='trading_desk', values='share').sort_index(ascending=True)
dfCota['CDI'] = ((1+dfCota['CDI']/100)**(1/252)).cumprod().shift(1).fillna(1)  
dfRet = dfCota.pct_change()
vol = dfRet.std() * np.sqrt(252)

dfRetAcum = (dfRet.fillna(0)+1).cumprod()-1


l = list(funds.keys())
te = (dfRet[l[0]] - dfRet[l[1]]).std() * np.sqrt(252)


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
fig, axes = plt.subplots(1,2, figsize=(10,4), sharex=False, sharey=False)
fig.tight_layout(w_pad=2)

ax = axes[0]
for f in dfRetAcum.iloc[-1][l].sort_values(ascending=False).index:
    ax.plot(dfRetAcum[f].index, dfRetAcum[f], label=f"{f} ({dfRetAcum.iloc[-1][f]:2.2%})", zorder=3, lw=3, alpha=0.9, c=funds[f][0])
f='CDI'
ax.plot(dfRetAcum[f].index, dfRetAcum[f], label=f"{f} ({dfRetAcum.iloc[-1][f]:2.2%})", c='k', ls='--', lw=2)
ax.grid(ls='--')
ax.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1))
ax.xaxis.set_major_locator(mdates.DayLocator(bymonthday=[1]))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%Y'))
ax.set_xlim(left=dfRetAcum.index[0])
ax.legend()

ax = axes[1]
ax.plot(dfRet[l[0]].values, dfRet[l[1]].values, ls='', marker='.', zorder=3, alpha=0.7)
# for y in set([i.year for i in dfRet.index]):
#     temp_df = dfRet.loc[datetime.date(y,1,1):datetime.date(y,12,31)]
#     ax.plot(temp_df[l[0]].values, temp_df[l[1]].values, ls='', marker='.', zorder=3, label=y, alpha=0.7)
# temp_df = dfRet.iloc[-10:]
# ax.plot(temp_df[l[0]].values, temp_df[l[1]].values, ls='', marker='s', zorder=3, label='last 2 weeks')

dfRet['diff'] = abs(dfRet[l[0]] - dfRet[l[1]])
txts=[]
# for i in dfRet['diff'].sort_values(ascending=False).head(3).index:
#     txts.append(ax.text(dfRet.loc[i, l[0]], dfRet.loc[i, l[1]], f"{i:%d%b%y}"))
# adjustText.adjust_text(txts, 
#                        dfRet[l[0]].values, 
#                        dfRet[l[1]].values, 
#                        ax=ax, 
#                        arrowprops=dict(arrowstyle="-", color='k', lw=0.5))

ax.plot([-.005,.005],[-.005,.005], c='silver', label='y=x', ls='--')
ax.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1))
ax.xaxis.set_major_formatter(ticker.PercentFormatter(xmax=1))
ax.axvline(0, lw=0.5, c='k')
ax.axhline(0, lw=0.5, c='k')
ax.grid(ls='--')
ax.yaxis.set_label_position("right")
ax.set_xlabel(f"Retorno (%)\n{l[0]}")
ax.set_ylabel(f"Retorno (%)\n{l[1]}")
ax.legend()

file3 = '../output/temp_figs/{:%Y%m%d}_pnl_3.pdf'.format(dt)
fig.savefig(file3, bbox_inches = "tight")
fig.savefig('../output/temp_figs/{:%Y%m%d}_pnl_3.svg'.format(dt), bbox_inches = "tight")
plt.show()
#%%
from PyPDF2 import PdfFileMerger

merger = PdfFileMerger()
for f in [file1, file2, file3]:
    merger.append(f)

merger.write('../output/temp_figs/{:%Y%m%d}_{}_pnl_diff.pdf'.format(dt, l[1]))
merger.close()
