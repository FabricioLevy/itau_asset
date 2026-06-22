import pandas as pd
import numpy as np
import datetime
import sqlalchemy as sa
import matplotlib.pyplot as plt


str_fund = 'A1 Master FIM'

dt_ini = datetime.date(2020, 4, 1)
dt_end = datetime.date(2022, 1, 31)


engine = sa.create_engine('mssql+pyodbc://saprod:nhjmmn&^Yh%%^yhjU&@srvprod1.database.windows.net,1433/dbprod1?driver=SQL+Server+Native+Client+11.0')
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

dfReturn = df[df['measure']=='PL'].pivot_table(index='date_reference', columns='book_risk', values='PnL_Perc', aggfunc=np.sum)\
            .loc[dt_ini:dt_end].sort_index(ascending=True)
dfReturn = dfReturn.fillna(0) 


# dfReturn['Moedas'] += dfReturn[['Moedas']].join(dfReturn.loc[datetime.date(2021,2,1):datetime.date(2021,4,30), ['Cupom Cambial']]).fillna(0)['Cupom Cambial']
# dfReturn['Cp Cambial\nFev,Mar,Abr-2021'] = dfReturn.loc[datetime.date(2021,2,1):datetime.date(2021,4,30), 'Cupom Cambial']
# dfReturn.loc[datetime.date(2021,2,1):datetime.date(2021,4,30), 'Cupom Cambial'] = 0
dfReturn = dfReturn.fillna(0) 

dfReturn['Total'] = dfReturn.sum(axis=1)
dfReturn.sort_index(inplace=True)

dfReturn.rename(columns={'Caixa_Outros':'Outros', 'Moedas':'USDBRL'}, inplace=True)
last_cols = ['Outros', 'Total']
cols = [c for c in dfReturn.columns if c not in last_cols] + last_cols

dfReturn = dfReturn[cols]
del last_cols, cols

dfReturn['Day'] = [i.day for i in dfReturn.index]
dfReturn.set_index('Day', inplace=True)
dfReturn.loc['Total']=((1+dfReturn).cumprod().iloc[-1]-1)
dfReturn *= 10000
last_cols = ['Outros', 'Total']
sorted_cols = list(dfReturn.loc['Total'].drop(last_cols).sort_values(ascending=False).index) + last_cols
dfReturn = dfReturn[sorted_cols]

for x in dfReturn.columns:
    if dfReturn.loc['Total', x] == 0:
        dfReturn.drop(x, axis=1, inplace=True)


#%%
color1, color2 = '#344147','#2F788D'

fig, ax2 = plt.subplots(1, 1, figsize=(8, 4))
ax2.set_title('Atribuição de Resultado (BPs)\n(entre {:%d-%b-%y} e {:%d-%b-%y})'.format(dt_ini, dt_end), fontsize=15, fontweight='bold')
plt.tight_layout()

trans = pd.DataFrame(dfReturn.loc['Total'])
blank=trans.drop('Total').Total.cumsum().shift(1).fillna(0)
blank.loc['Total'] = float(trans.loc['Total'])

step = blank.reset_index(drop=True).repeat(3).shift(-1)
step[1::3] = np.nan

blank.loc['Total'] = 0

c = [color2 if i>0 else 'tomato' for i in trans['Total'].values]
c[-1] = color1 if c[-1]==color2 else 'r'

ax2.bar(range(len(trans.index)), trans['Total'],bottom=blank, color=c, zorder=3,\
        tick_label=[x.replace(' ',' ') for x in trans.index])

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
    ax2.annotate("{:,.0f}".format(value),(j, y), ha="center", va=va,\
           fontsize=11, fontweight='bold',color=c)


ax2.grid(axis='y', ls='--')
ax2.tick_params(labelsize=12)
plt.xticks(rotation=90)
ax2.axhline(0, c='k', lw=1, zorder=4)

# watermark2(ax2)
fig.savefig('{:%Y%m%d}_{:%Y%m%d}_pnl_barplot_2.svg'.format(dt_ini, dt_end), bbox_inches = "tight")

plt.show()