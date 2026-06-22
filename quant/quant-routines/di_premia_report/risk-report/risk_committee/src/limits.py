import pandas as pd
import datetime
import calendar
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

from a1db.a1sql import SQLConnection

import os, sys
path_var = os.path.expanduser('~\\Documents\\Github')
sys.path.insert(1, path_var + '\\risk_report\src')
import fund_utils as fu


########################
month, year = 11, 2022
########################

str_fund = 'A1 Master FIM'
dt_ini = datetime.date(year, month, 1)
dt_end = datetime.date(year, month, calendar.monthrange(year, month)[-1])

connection = SQLConnection().get_connection()
    
str_sql =  """
        SELECT v.date_reference, [node],risk_measure, [value]/n.NAV as value 
        FROM [risk].[measure] v INNER JOIN middle.NAV n ON v.date_reference = n.date_reference and v.trading_desk = n.trading_desk
        WHERE v.trading_desk = '{}' 
        and parent_tree in ('Traders', 'Fund') 
        and v.date_reference BETWEEN '{:%Y-%m-%d}' AND '{:%Y-%m-%d}'
           """
           
str_sql = str_sql.format(str_fund, dt_ini, dt_end)

df = pd.read_sql(str_sql, connection)
df['day'] = df['date_reference'].apply(lambda x: x.day)

connection.close()
del str_sql
#%%
dfVaR = df[df['risk_measure']=='VaR'].pivot(index='day', columns='node', values='value') * -10000
dfStress = df[df['risk_measure']=='Stress'].pivot(index='day', columns='node', values='value')

for c in dfVaR.columns:
    if c not in dfStress.columns:
        dfStress[c] = 0

#%%

trader_limit = fu.get_RiskLimits(dt_end, str_fund)

dfVaR_Limit = fu.get_DailyRiskShare(dt_end, str_fund, 'var_limit').loc[dt_ini:dt_end]
dfStress_Limit = fu.get_DailyRiskShare(dt_end, str_fund, 'stress_limit').loc[dt_ini:dt_end]

for dfTemp in [dfVaR_Limit, dfStress_Limit]:
    dfTemp['day'] = [x.day for x in dfTemp.index]
    dfTemp.set_index('day', inplace=True)


#%%
cols = fu.get_traders(dt_end).keys()
cols = sorted(cols, key=trader_limit.get)
dic_ex = {}

color1, color2 = fu.color_palette[0], fu.color_palette[1]

fig, (axV, axS) = plt.subplots(nrows=2, ncols=len(cols),\
                               figsize=(13, 6), sharex=True)
plt.tight_layout()

axS[-1].axhline(-0.25, color='r', lw=2)
for i, c in enumerate(cols):
    dic_ex[c] = [dfVaR[c][dfVaR[c] > dfVaR_Limit[c]+0.001],
                 dfStress[c][dfStress[c] < dfStress_Limit[c]-0.0001]]

    dfVaR[c].plot(ax=axV[i], color=color2, lw=2)
    dfVaR_Limit[c].plot(ax=axV[i], color='r', lw=2, ls='--', drawstyle="steps")
    
    axV[i].set_title(c)
    # axV[i].axhline(trader_limit[c][0], color='r', lw=2)
    axV[i].set_ylim(bottom=0)
    
    
    dfStress[c].plot(ax=axS[i], color=color2, lw=2)
    dfStress_Limit[c].plot(ax=axS[i], color='r', lw=2, ls='--', drawstyle="steps")
    # axS[i].axhline(trader_limit['Fund'][1], color='r', lw=2, ls='--')
    axS[i].set_ylim(top=0)#, bottom=max(-0.25,  axS[i].get_ylim()[0]))
    axS[i].yaxis.set_major_formatter(ticker.PercentFormatter(1.0, decimals=1)) 
    # axS[i].set_yticklabels(['{:2.0%}'.format(i) for i in axS[i].get_yticks()])
    axS[i].set_xlabel('')
    
    for a, v in zip([axV, axS], dic_ex[c]):
        if len(v) > 0:
            a[i].plot(v.index, v, ls='', marker='X', color='red', markersize=8)
    
    for a in [axV, axS]:
        a[i].grid(ls='--')
        

axV[0].set_ylabel('VaR (BPs)')
axV[0].set_xlim(left=dfVaR.index[0], right=dfVaR.index[-1])
axS[0].set_ylabel('Stress (%NAV)')
axS[0].xaxis.set_major_locator(ticker.MultipleLocator(10))
axS[0].xaxis.set_minor_locator(ticker.MultipleLocator(2))

axV[-1].set_facecolor('lightgrey')
axS[-1].set_facecolor('lightgrey')
for file_ext in ['svg', 'pdf']:
    fig_file = '../tex/{0:%Y_%m}/figuras/{0:%Y%m}_trader_var_stress.{1}'.format(dt_ini, file_ext)    
    fig.savefig(fig_file, bbox_inches = "tight")
plt.show()


