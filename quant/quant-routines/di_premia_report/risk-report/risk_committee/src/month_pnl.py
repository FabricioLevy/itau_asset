import pandas as pd
import numpy as np
import datetime
import calendar
import seaborn as sns
import matplotlib.pyplot as plt

from a1db.a1sql import SQLConnection

########################
month, year = 11, 2022
########################

str_fund = 'A1 Master FIM'
dt_ini = datetime.date(year, month, 1)
dt_end = datetime.date(year, month, calendar.monthrange(year, month)[-1])

connection = SQLConnection().get_connection()
    
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

dfReturn = df[df['measure']=='PL'].pivot_table(index='date_reference', columns='book_risk', values='PnL_Perc', aggfunc=np.sum)\
            .loc[dt_ini:dt_end].sort_index(ascending=True)
dfReturn = dfReturn.fillna(0) 
dt_end = dfReturn.index.max()

corr = dfReturn.drop('Caixa_Outros', axis=1).corr() * 100

dfReturn['Total'] = dfReturn.sum(axis=1)

dfReturn['Day'] = [i.day for i in dfReturn.index]
dfReturn.set_index('Day', inplace=True)
dfReturn.loc['Total']=((1+dfReturn).cumprod().iloc[-1]-1)
dfReturn *= 10000

last_cols = ['Caixa_Outros', 'Total']
sorted_cols = list(dfReturn.loc['Total'].drop(last_cols).sort_values(ascending=False).index) + last_cols
dfReturn = dfReturn[sorted_cols]

del df
#%%
fig, ax = plt.subplots(figsize=(7, 3))
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
ax.set_title('')
for file_ext in ['svg', 'pdf']:
    fig.savefig('../tex/{0:%Y_%m}/figuras/{0:%Y%m}_correl.{1}'.format(dt_ini, file_ext), bbox_inches = "tight")

plt.show()

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
ax1.set_title('Daily Returns (BPs)\n{:%d-%b-%Y}~{:%d-%b-%Y}'.format(dt_ini, dt_end), fontsize=15, fontweight='bold')

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



for file_ext in ['svg', 'pdf']:
    fig.savefig('../tex/{0:%Y_%m}/figuras/{0:%Y%m}_pnl.{1}'.format(dt_ini, file_ext), bbox_inches = "tight")

plt.show()

