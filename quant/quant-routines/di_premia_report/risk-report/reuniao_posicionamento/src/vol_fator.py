import pandas as pd
import numpy as np
import datetime
import QuantLib as ql
from a1db.a1sql import SQLConnection
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.dates as mdates

import sys
sys.path.insert(1, '../../risk_report/src')
import fund_utils as fu

dt, str_fund = fu.get_config(['dt', 'str_fund'])

today = ql.Date.from_date(dt)
lastweek = ql.Brazil().advance(today, ql.Period('-1w'))
lastmonth = ql.Brazil().advance(today, ql.Period('-1m'))
last6month = ql.Brazil().advance(today, ql.Period('-6m'))

connection = SQLConnection().get_connection()  

str_sql = """
          SELECT tsv.date_reference, ts.entity_id, tsv.value
          FROM [quant].[time_series] ts 
         	INNER JOIN [quant].[time_series_entity] tse ON ts.entity_id = tse.id
         	INNER JOIN quant.time_series_value tsv ON tsv.series_id = ts.id
         	INNER JOIN quant.time_series_grouping tsging on tsging.series_id = ts.id
         	INNER JOIN quant.time_series_group tsg ON tsg.id = tsging.group_id
         WHERE tsg.[name] = 'VaR Simulation' 
               AND tsg.[subtype] = 'US Bonds'
               AND tsv.date_reference > '2020-1-1'
             order by 1
         """
dfUSBond = pd.read_sql(str_sql, connection).pivot(index='date_reference', columns='entity_id', values='value').diff()/100


    
str_sql = """
            SELECT [date_reference],[curve_name],[tenor],[discount_factor],curve_rate,business_day
              FROM [risk].[interest_rate_curve]
            WHERE ((curve_name in ('DI Fut','DAP Fut','NTNB Zero', 'ED Fut') and tenor in (360, 720, 1800, 3600)) OR
                  (curve_name in ('MXN TIIE Zero','Swap CLP Zero','Swap COP Zero') and tenor=1800))   
        		AND [date_reference] > '2020-1-1'
         """
df = pd.read_sql(str_sql, connection)

str_sql = """
            SELECT [date_reference],[product_id],[price]
              FROM [middle].[product_price]
             where product_id in ('SPX', 'USDBRL', 'IBOV', 'USDMXN', 'USDCOP', 'USDCLP')
        		AND [date_reference] > '2020-1-1'
          """
df2 = pd.read_sql(str_sql, connection)
connection.close()

dic_curve = {'DI Fut'   : 'DI',
             'ED Fut'   : 'US',
             'NTNB Zero': 'NTNB',
             'DAP Fut' : 'DAP',
             'DAP BEI'  : 'BEI',
             'MXN TIIE Zero' : 'MXN',
             'Swap CLP Zero' : 'CLP',
             'Swap COP Zero' : 'COP'}


del str_sql
#%%
df['bucket'] = df['curve_name'].apply(lambda x: dic_curve[x]) + df['tenor'].apply(lambda x: '_{:1.0f}Y'.format(x/360))
df = df.pivot(index='date_reference', columns='bucket', values='discount_factor')
df = df.loc[:dt]
df['BEI 2Y'] = df['DAP_2Y']/df['DI_2Y']
df['BEI 5Y'] = df['DAP_5Y']/df['DI_5Y']

dfRet = df.pct_change()

dfRet = dfRet.join(df2.pivot(index='date_reference', columns='product_id', values='price').pct_change()).join(dfUSBond)
#%%

dfVol = dfRet.ewm(alpha=0.06).std() * np.sqrt(252)
dfRetAcum = (1+dfRet).cumprod()

#%%
# 'DI_2Y', 'DI_5Y', 'NTNB_2Y', 'NTNB_5Y'
locator = mdates.AutoDateLocator(minticks=2, maxticks=7)
formatter = mdates.ConciseDateFormatter(locator, formats=['%b\n%Y', '%b', '%d', '%H:%M', '%H:%M', '%S.%f'], show_offset=False)
color_palette =['teal', '#2F788D', 'royalblue', 'cornflowerblue', 'slategrey', 'silver', 'lightgrey']    

dfPlot = dfVol.loc[last6month.to_date():]
fig, axes = plt.subplots(2, 3, figsize=(12, 5), sharex=True, 
                                             gridspec_kw = {'width_ratios':[1,1,1]})
plt.tight_layout()
# plt.subplots_adjust(wspace=0.1, hspace=0.05)

ax = axes[0,0]
ax.set_title('Juro Nominal - BR')
ax.plot(dfPlot.index, dfPlot['DI_2Y'], label='Pre 2Y', color=color_palette[0], lw=2.5)
ax.plot(dfPlot.index, dfPlot['DI_5Y'], label='Pre 5Y', color=color_palette[2], lw=2.5)

ax = axes[0,1]
ax.set_title('Juro Real - BR')
ax.plot(dfPlot.index, dfPlot['NTNB_2Y'], label='Cp IPCA 2Y', color=color_palette[0], lw=2.5)
ax.plot(dfPlot.index, dfPlot['NTNB_5Y'], label='Cp IPCA 5Y', color=color_palette[2], lw=2.5)

ax = axes[0,2]
# ax.set_title('Breakeven Inflation - BR')
# ax.plot(dfPlot.index, dfPlot['BEI 2Y'], label='BEI 2Y', color=color_palette[0], lw=2.5)
# ax.plot(dfPlot.index, dfPlot['BEI 5Y'], label='BEI 5Y', color=color_palette[2], lw=2.5)
ax.set_title('Juros Nominal - US (ED Fut)')
ax.plot(dfPlot.index, dfPlot['US_2Y'], label='US 2Y', color=color_palette[0], lw=2.5)
ax.plot(dfPlot.index, dfPlot['US_5Y'], label='US 5Y', color=color_palette[3], lw=2.5)
ax.plot(dfPlot.index, dfPlot['US_10Y'], label='US 10Y', color=color_palette[2], lw=2.5)


ax = axes[1,0]
ax.set_title('Juros Latam')
# ax.plot(dfPlot.index, dfPlot['DI_5Y'], label='DI_5Y', color=color_palette[0], lw=2.5, ls='--')
ax.plot(dfPlot.index, dfPlot['MXN_5Y'], label='MXN_5Y', color=color_palette[4], lw=2.5)
ax.plot(dfPlot.index, dfPlot['COP_5Y'], label='COP_5Y', color=color_palette[2], lw=2.5)
ax.plot(dfPlot.index, dfPlot['CLP_5Y'], label='CLP_5Y', color=color_palette[3], lw=2.5)

ax = axes[1,1]
ax.set_title('Moeda')
ax.plot(dfPlot.index, dfPlot['USDBRL'], label='BRL', color=color_palette[0], lw=2.5, ls='--')
ax.plot(dfPlot.index, dfPlot['USDMXN'], label='MXN', color=color_palette[4], lw=2.5)
ax.plot(dfPlot.index, dfPlot['USDCOP'], label='COP', color=color_palette[2], lw=2.5)
ax.plot(dfPlot.index, dfPlot['USDCLP'], label='CLP', color=color_palette[3], lw=2.5)

ax = axes[1,2]
ax.set_title('Bolsa')
ax.plot(dfPlot.index, dfPlot['SPX'], label='S&P', color=color_palette[2], lw=2.5)
ax.plot(dfPlot.index, dfPlot['IBOV'], label='Ibov', color=color_palette[0], lw=2.5, ls='--')

for ax in axes.flatten():
    ax.axhline(0, color='k', lw=0.5)
    ax.legend(ncol=2)
    ax.grid(ls='--', which='both')
    ax.set_xlim(left=dfPlot.index[0])
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1))
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    # ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=4, interval=1))

fig.suptitle(r'Volatilidade Fatores de Risco (EWMA, $\lambda$=0.94)', y=1.05, fontsize=13, fontweight='bold')
fig_file = '..//tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_vol_fator.pdf'.format(dt)
fig.savefig(fig_file, bbox_inches = "tight")
plt.show()

#%%
dfPlot = dfRetAcum.loc[last6month.to_date():]
dfPlot = (dfPlot / dfPlot.iloc[0]) - 1
fig, axes = plt.subplots(2, 3, figsize=(12, 5), sharex=True, 
                                             gridspec_kw = {'width_ratios':[1,1,1]})
plt.tight_layout(w_pad=2)
ax = axes[0,0]
ax.set_title('Juro Nominal - BR')
ax.plot(dfPlot.index, dfPlot['DI_2Y'], label='Pre 2Y', color=color_palette[0], lw=2.5)
ax.plot(dfPlot.index, dfPlot['DI_5Y'], label='Pre 5Y', color=color_palette[2], lw=2.5)

ax = axes[0,1]
ax.set_title('Juro Real - BR')
ax.plot(dfPlot.index, dfPlot['NTNB_2Y'], label='Cp IPCA 2Y', color=color_palette[0], lw=2.5)
ax.plot(dfPlot.index, dfPlot['NTNB_5Y'], label='Cp IPCA 5Y', color=color_palette[2], lw=2.5)

ax = axes[0,2]
ax.set_title('Juros Nominal - US (ED Fut)')
ax.plot(dfPlot.index, dfPlot['US_2Y'], label='US 2Y', color=color_palette[0], lw=2.5)
ax.plot(dfPlot.index, dfPlot['US_5Y'], label='US 5Y', color=color_palette[3], lw=2.5)
ax.plot(dfPlot.index, dfPlot['US_10Y'], label='US 10Y', color=color_palette[2], lw=2.5)


ax = axes[1,0]
ax.set_title('Juros Latam')
ax.plot(dfPlot.index, dfPlot['MXN_5Y'], label='MXN_5Y', color=color_palette[4], lw=2.5)
ax.plot(dfPlot.index, dfPlot['COP_5Y'], label='COP_5Y', color=color_palette[2], lw=2.5)
ax.plot(dfPlot.index, dfPlot['CLP_5Y'], label='CLP_5Y', color=color_palette[3], lw=2.5)

ax = axes[1,1]
ax.set_title('Moeda')
ax.plot(dfPlot.index, dfPlot['USDBRL'], label='BRL', color=color_palette[0], lw=2.5, ls='--')
ax.plot(dfPlot.index, dfPlot['USDMXN'], label='MXN', color=color_palette[4], lw=2.5)
ax.plot(dfPlot.index, dfPlot['USDCOP'], label='COP', color=color_palette[2], lw=2.5)
ax.plot(dfPlot.index, dfPlot['USDCLP'], label='CLP', color=color_palette[3], lw=2.5)

ax = axes[1,2]
ax.set_title('Bolsa')
ax.plot(dfPlot.index, dfPlot['SPX'], label='S&P', color=color_palette[2], lw=2.5)
ax.plot(dfPlot.index, dfPlot['IBOV'], label='Ibov', color=color_palette[0], lw=2.5, ls='--')

for ax in axes.flatten():
    ax.axhline(0, color='k', lw=0.5)
    ax.legend(ncol=2)
    ax.grid(ls='--', which='both')
    ax.set_xlim(left=dfPlot.index[0])
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1))
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    # ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=4, interval=1))

fig.suptitle(r'Retorno Acumulado - Fatores de Risco', y=1.05, fontsize=13, fontweight='bold')
fig_file = '..//tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_retacum_fator.pdf'.format(dt)
fig.savefig(fig_file, bbox_inches = "tight")
plt.show()