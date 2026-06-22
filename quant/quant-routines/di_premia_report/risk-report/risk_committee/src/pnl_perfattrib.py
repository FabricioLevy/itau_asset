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

str_sql =   """ 
       SELECT b.[date_reference], b.book, b.[lote45_product_class],
              b.[lote45_product], sum([value]/n.NAV_D1) as PnL_Perc  
         FROM [lote45].[book_overview] b  
           		INNER JOIN middle.NAV n 
                   ON n.date_reference = b.date_reference 
                      and n.trading_desk = b.trading_desk
        WHERE [measure] = 'PL'  and b.date_reference <='{:%Y-%m-%d}' and b.[trading_desk] = '{}'
        GROUP BY b.[date_reference], b.book, b.[lote45_product_class], b.[lote45_product]
        """
df = pd.read_sql(str_sql.format(dt_end, str_fund) , connection)

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
dfRiskShare['Shared'] = 1

df['Trader'] = df['book'].apply(lambda x: dic_books[x])
df['Risk'] = df['book'].apply(lambda x: dic_books2[x])

df['product'] = df['lote45_product_class'].apply(lambda x: dfProduct['risk_product'].get(x, x))

df.loc[(df['Risk']=='Cupom Cambial') & (df['product']=='FX'), 'product'] = 'Cp Cambial'
df.loc[(df['Risk']=='Caixa_Outros') & (df['product']=='Cp Cambial'), 'product'] = 'Cash/Costs'

#%%
dfPnL = pd.DataFrame(0, index=df['Trader'].unique(), columns=df['Risk'].unique())

dfTraderPnL = df.pivot_table(index='date_reference', columns='Trader', values='PnL_Perc', aggfunc=np.sum).fillna(0)
dfTraderPnL['Fund'] = dfTraderPnL.sum(axis=1)

dfTraderPnLAdj = (dfTraderPnL/dfRiskShare).fillna(0)

dfRiskPnL = df.pivot_table(index='date_reference', columns='Risk', values='PnL_Perc', aggfunc=np.sum).fillna(0)
dfRiskPnL['Fund'] = dfRiskPnL.sum(axis=1)

dfRiskTraderPnL = df.pivot_table(index='date_reference', columns=['Risk','Trader'], values='PnL_Perc', aggfunc=np.sum).fillna(0)

dfTraderProductPnL = df.pivot_table(index='date_reference', columns=['Trader', 'product'], values='PnL_Perc', aggfunc=np.sum).fillna(0)

temp = dfTraderProductPnL.sum(level=1,axis=1)

for c in temp.columns:
    dfTraderProductPnL[('Fund', c)] = temp[c]

#%%
calendarBrazil = ql.Brazil()
dt = min(dt_end, dfRiskShare.index[-1])
dtEnd = calendarBrazil.advance(ql.Date(1, dt.month, dt.year), ql.Period('-1d'))
dtEnd = ql.Date.from_date(dt)
dtIni = ql.Date(1, ql.April, 2020)

list_EoM = [dtIni]
dtEoM = calendarBrazil.endOfMonth(ql.Date(1, dtIni.month(), dtIni.year()))
while dtEoM < dtEnd:
    list_EoM.append(dtEoM)
    dtEoM = calendarBrazil.endOfMonth(dtEoM + ql.Period(1, ql.Months))
list_EoM.append(dtEnd)

dicDates = {value2.to_date(): (value1, value2) for (value1, value2) in list(zip(list_EoM[:-1], list_EoM[1:]))}
del list_EoM


#%%
dic_pnl = {}
for dfTemp, perf_id in zip([dfTraderPnLAdj, dfTraderPnL, dfRiskPnL, dfRiskTraderPnL, dfTraderProductPnL],
                           ['TraderAdj', 'Trader', 'Risk', 'RiskTrader', 'TraderProduct']):
    dfCota = (dfTemp+1).cumprod()
    dfOutput = pd.DataFrame(columns=dfCota.columns, index=dicDates.keys())
    for (key, (dtPrevEoM, dtEoM)) in dicDates.items():
        dfOutput.loc[key] = dfCota.loc[dtEoM.to_date()]/dfCota.loc[dtPrevEoM.to_date()] - 1
    dic_pnl[perf_id] = dfOutput.copy()


#%%
trader_cols = list(fu.get_traders(dt_end).keys())
dfPlot = dic_pnl['TraderAdj'][trader_cols]
dfVol = pd.DataFrame(dfPlot.replace(0, np.nan).iloc[-12:].std()*np.sqrt(12), columns=['Vol\n(%aa)'])

fig, (ax, ax2) = plt.subplots(1, 2, figsize=(len(dfPlot)*0.55, 5), 
                              gridspec_kw = {'width_ratios':[len(dfPlot), 1.3]})
fig.tight_layout(w_pad=0.01)
fig.subplots_adjust(wspace=0.025)
cmap = sns.diverging_palette(10, 240, n=15, as_cmap=True)
sns.heatmap(dfPlot.T.astype(dtype=np.float64)*10000, annot_kws={"size": 10}, \
                cmap=cmap, vmax=100, vmin=-100, center=0, fmt='2,.0f', \
                    square=False, linewidths=.5, annot = True, cbar=False,  ax=ax)
ax.set_xticklabels([x for x in dicDates.keys()])
ax.yaxis.set_ticks_position('none') 
ax.xaxis.set_ticks_position('none') 
ax.set_xticklabels(['{:%b\n%Y}'.format(i) for i in dfPlot.index])
ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontweight='bold')

cmap = sns.light_palette((260, 75, 60), input="husl", as_cmap=True)
sns.heatmap(dfVol.astype(dtype=np.float64),  alpha=1,\
            cmap=cmap, vmax=0.1, vmin=0,annot = True, annot_kws={"weight": "bold"},
            linewidths=2, cbar=False, fmt='2.1%', ax=ax2)
ax2.set_yticks([])

ax.axvline(len(dfPlot)-12, color='k', ls='--')    
for axis in [ax, ax2]:
    axis.xaxis.set_ticks_position('top')
    axis.axhline(len(dfPlot.columns)-1, lw=2.5, color='k')
    
for file_ext in ['svg', 'pdf']:
    fig_file = '../output/{:%Y%m%d}_{}_monthly_vol.{}'.format(dt, str_fund, file_ext)
    fig.savefig(fig_file, bbox_inches = "tight")
    
plt.show()

#%%
dt_target = dt #datetime.date(2021, 9, 30)
month_pnl = dic_pnl['TraderProduct'].loc[dt_target].reset_index().pivot(columns='Trader', index='product', values=dt_target).fillna(0)
trader_cols.insert(-1,  'Shared')
month_pnl = np.round(month_pnl[trader_cols], 10)
month_pnl = month_pnl.loc[(month_pnl!=0).any(1)] #remove all zero rows

dic_prod = (dfProduct[['risk_product', 'perf_att_class']].drop_duplicates().set_index('risk_product')).sort_values(by='perf_att_class')['perf_att_class'].to_dict()

month_pnl.loc['Total'] = dic_pnl['Trader'].loc[dt_target, trader_cols]

sorted_index = sorted(month_pnl.index, key=lambda x:dic_prod.get(x,x))

month_pnl = month_pnl.loc[sorted_index]

fig, ax, = plt.subplots(1, 1, figsize=(11, 5))
fig.tight_layout()
cmap = sns.diverging_palette(10, 240, n=15, as_cmap=True)
sns.heatmap(month_pnl.astype(dtype=np.float64)*10000, annot_kws={"size": 12}, \
                cmap=cmap, vmax=50, vmin=-50, center=0, fmt='2,.1f', \
                    square=False, linewidths=.5, annot = True, cbar=False,  ax=ax)
    
ax.xaxis.set_ticks_position('top')
ax.set_xticklabels(ax.get_xticklabels(), rotation=0, fontweight='bold', fontsize=13)    
ax.set_xlabel('')

ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontweight='bold')    
ax.set_ylabel('')

ax.axvline(len(month_pnl.columns)-1, lw=2, color='k')
ax.axhline(len(month_pnl)-1, lw=2, color='k')
ax.axhline(0, lw=2, color='k')

ax.set_title('PnL Attribution by Product  -  {:%B.%Y}'.format(dt_target), fontweight='bold', fontsize=14)

for t in ax.texts:
    if (float(t.get_text())==0):
        t.set_text('-')
for file_ext in ['svg', 'pdf']:        
    fig_file = '../tex/{0:%Y_%m}/figuras/{0:%Y%m}_{1}_pnl_product.{2}'.format(mtd, str_fund, file_ext)
    fig.savefig(fig_file, bbox_inches = "tight")
plt.show()