import pandas as pd
import numpy as np
import datetime
import sqlalchemy as sa
import seaborn as sns
import matplotlib.pyplot as plt


str_fund = 'A1 Master FIM'

dt_ini = datetime.date(2020, 12, 1)
dt_end = datetime.date(2020, 12, 31)


engine = sa.create_engine('mssql+pyodbc://reader:ax5yYwWd@srvprod1.database.windows.net,1433/dbprod1?driver=SQL+Server+Native+Client+11.0')
connection = engine.connect()
    
str_sql =   "  SELECT b.[date_reference], t.node as book_trader, r.node as book_risk, [measure], sum([value]/n.NAV_D1) as PnL_Perc  " +\
            "  FROM [lote45].[book_overview] b  " +\
            "		INNER JOIN [lote45].[book_tree] t ON b.book = t.book  " +\
            "		INNER JOIN [lote45].[book_tree] r ON b.book = r.book  " +\
            "		INNER JOIN middle.NAV n ON n.date_reference = b.date_reference and n.trading_desk = b.trading_desk  " +\
            "  WHERE t.parent_tree = 'Traders' and r.parent_node = 'PerformanceAttribution' " +\
            "	and [measure] in ('PL','Position PL','Trades PL') " +\
            "	and b.[trading_desk] = '{}'  ".format(str_fund) +\
            "  GROUP BY b.[date_reference], t.node, r.node,[measure] " +\
            "  ORDER BY 1 " 

df = pd.read_sql(str_sql, connection)
connection.close()
del str_sql

dfReturn = df[df['measure']=='PL'].pivot_table(index='date_reference', columns='book_trader', values='PnL_Perc', aggfunc=np.sum)\
            .loc[dt_ini:dt_end].sort_index(ascending=True)
dfReturn = dfReturn.fillna(0) 
dfReturn.rename(columns={'FK Bolsa':'FK'}, inplace=True)
dfReturn['Total'] = dfReturn.sum(axis=1)


dfReturn['Day'] = [i.day for i in dfReturn.index]
dfReturn.set_index('Day', inplace=True)
dfReturn.loc['Total']=((1+dfReturn).cumprod().iloc[-1]-1)
dfReturn *= 10000

last_cols = ['Shared', 'Total']
sorted_cols = list(dfReturn.loc['Total'].drop(last_cols).sort_values(ascending=False).index) + last_cols
dfReturn = dfReturn[sorted_cols]

dfReturn.to_excel('../output/{:%y%m%d}_{:%y%m%d}_pnl.xlsx'.format(dt_ini, dt_end))

del df
#%%
color1, color2 = '#344147','#2F788D'

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 6), gridspec_kw = {'height_ratios':[3,  4]})
plt.tight_layout()
plt.subplots_adjust(wspace=0.02, hspace=0.05)
cmap = sns.diverging_palette(10, 205, n=15, as_cmap=True)
sns.heatmap(dfReturn.T.astype(dtype=np.float64), annot_kws={"size": 12}, \
            cmap=cmap, vmax=40, vmin=-40, center=0, fmt='2.0f', \
                square=False, linewidths=.5, annot = True, cbar=False,  ax=ax1)
ax1.xaxis.set_ticks_position('top')
ax1.xaxis.set_tick_params(labelsize=12)
ax1.yaxis.set_tick_params(labelsize=12)
ax1.set_ylabel('Book', fontsize=12)
ax1.xaxis.label.set_visible(False)


plt.yticks(rotation='horizontal')
ax1.set_title('Daily Returns (BPs)\n{:%B-%Y}'.format(dt_end), fontsize=15, fontweight='bold')

tickTotal = ax1.get_yticklabels()[-1]
tickTotal.set_fontsize(13)
tickTotal.set_fontweight('bold')

pos_Bold = [t.get_position()[0] for t in ax1.get_xticklabels() if t.get_text() == 'Total']
for text in ax1.texts:
    if text.get_position()[-1] == tickTotal.get_position()[-1]:
        text.set_fontweight('bold')
    if text.get_position()[0] in pos_Bold:
        text.set_fontweight('bold')

for t in ax1.get_xticklabels() + ax2.get_xticklabels():
    if t.get_text() == 'Total':
        t.set_fontsize(13)
        t.set_fontweight('bold')        
        
ax1.axhline(len(dfReturn.columns)-1, c='k', lw=3)
ax1.axhline(len(dfReturn.columns), c='k', lw=1.5)
for x in pos_Bold:
    ax1.axvline(x-0.5, c='k', lw=1.5)
    ax1.axvline(x+0.5, c='k', lw=1.5)

trans = pd.DataFrame(dfReturn.loc['Total'])
blank=trans.drop('Total').Total.cumsum().shift(1).fillna(0)
blank.loc['Total'] = float(trans.loc['Total'])

step = blank.reset_index(drop=True).repeat(3).shift(-1)
step[1::3] = np.nan

blank.loc['Total'] = 0

c = [color2 if i>0 else 'tomato' for i in trans['Total'].values]
c[-1] = color1 if c[-1]==color2 else 'r'

ax2.bar(range(len(trans.index)), trans['Total'],bottom=blank, color=c, zorder=3,\
        tick_label=[x.replace(' ','\n') for x in trans.index])

ax2.plot([x+.37 if i % 3 == 0 else x-.37 for i, x in enumerate(step.index)],\
         step.values, 'k', lw=1.25, ls='--', zorder=4)

h = ax2.get_ylim()[1] - ax2.get_ylim()[0]
ax2.set_ylim(top=ax2.get_ylim()[1]+h/8, bottom=ax2.get_ylim()[0]-h/8)

for j, value in enumerate(trans['Total'].values):
    if value > 0:
        va, shift, c = 'bottom', 1, 'k'
    else:
        va, shift, c ='top', -1, 'r'
    y = value + blank.iloc[j] + shift*(h/50)
    ax2.annotate("{:,.1f}".format(value),(j, y), ha="center", va=va,\
           fontsize=11, fontweight='bold',color=c)


ax2.grid(axis='y', ls='--', zorder=1)
ax2.tick_params(labelsize=12)
ax2.axhline(0, c='k', lw=1, zorder=2)

for file_ext in ['svg', 'jpg']:
    fig.savefig('../output/{:%y%m%d}_{:%y%m%d}_pnl.{}'.format(dt_ini, dt_end, file_ext), bbox_inches = "tight")

plt.show()
#%%
