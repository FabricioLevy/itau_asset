import pandas as pd
import numpy as np
import datetime
import QuantLib as ql
import sqlalchemy as sa
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.gridspec as gridspec

str_fund = 'A1 Master FIM'

dt = datetime.date.today()
dt = datetime.date(2022, 1, 17)
today = ql.Date.from_date(dt)
lastweek = ql.Brazil().advance(today, ql.Period('-1w'))


engine = sa.create_engine('mssql+pyodbc://reader:ax5yYwWd@srvprod1.database.windows.net,1433/dbprod1?driver=SQL+Server+Native+Client+11.0')
connection = engine.connect()
    
str_sql =   """ 
           SELECT [date_reference],[price] as IBOV_RET
  FROM [middle].[product_price]
  where product_id = 'IBOV' and date_reference>'2000-1-1'
  order by 1
        """
dfIBOV = pd.read_sql(str_sql, connection, index_col='date_reference').pct_change().dropna()+1
dfIBOV = dfIBOV.reset_index().sort_values('IBOV_RET')
connection.close()
del str_sql

#%%
str_file = r'C:\Users\mauricio.pereira\Documents\GitHub\risk_report\output\files\{:%Y%m%d}\pics/'.format(dt)
str_file +=  '{:%Y%m%d}_A1 Master FIM_ibov_simulation.xlsx'.format(dt)

df = pd.read_excel(str_file, index_col=0)

dfPlot = pd.merge_asof(dfIBOV, df, right_index=True, left_on='IBOV_RET', direction='nearest')
dfPlot['IBOV_RET'] -= 1




#%%
color1 = '#323E48'
color_palette =['#28829B', 'dodgerblue','royalblue','#C9CBCB', '#748D9E', '#2E9AB2']
    
fig = plt.figure(figsize=(12, 6), tight_layout=True)
gs = gridspec.GridSpec(2, 2, width_ratios=[3,2])

ax1 = fig.add_subplot(gs[:, 0])
ax2= fig.add_subplot(gs[0, 1])
ax3= fig.add_subplot(gs[1, 1])


ax=ax1
ax.plot(dfPlot['IBOV_RET'], dfPlot['PnL Total'], ls='--', lw=3.5, color=color1, label='PnL')
for x in [0.95, 0.99, 1.025]:
    val = df.loc[x,'PnL Total']
    ibov_val = df.loc[x,'IBOV']
    # ax.text(x, val, '{:2.2%}'.format(val))
    
    ax.annotate('{:2.0f}k\n{:4.2%}'.format(ibov_val/1000, val), 
                              xy=(x-1, val), xycoords='data', zorder=3,
                          xytext=(0, 60), textcoords='offset points', fontweight='bold',
                          fontsize=11, color=color1, ha='center',
                          bbox=dict(boxstyle="round", fc='silver' if val>0 else 'tomato', ec="0.5", alpha=0.8),
            arrowprops=dict(facecolor='r', arrowstyle="->", connectionstyle="arc3"))


ax.set_title('Simulated PnL',fontweight='bold')
ax.set_ylabel('PnL (%NAV)',fontweight='bold')
ticks_loc = ax.get_yticks().tolist()
ax.yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
ax.set_yticklabels(['{:2.1%}'.format(i) for i in ticks_loc])
ax.legend()
ax.set_xlabel('Ibovespa change (%) and simulated level (BRL)',fontweight='bold')
ax.axhline(0, color='k', lw=0.75, ls='--')
ax.axvline(1, color='k', lw=0.75, ls='--')
ax.grid(ls='--')
ax.set_xlim(left=-0.15, right=0.15)
ticks_loc = ax.get_xticks().tolist()
ax.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
ax.set_xticklabels(['{:2.1%}\n{:2.1f}k'.format(i, df.loc[round(i,4)+1, 'IBOV']/1000) for i in ticks_loc])


ax=ax2
dfPlot['IBOV_RET'].hist(ax=ax, bins=30, grid=False, color='#28829B')
ax.set_title('Historical IBOV Return Histogram (2000~)',fontweight='bold')
ax.grid(ls='--')
ax.xaxis.set_major_locator(mticker.FixedLocator(ax.get_xticks().tolist()))
ax.set_xticklabels(['{:2.1%}'.format(i) for i in ax.get_xticks()])

ax=ax3
dfPlot['PnL Total'].hist(ax=ax, bins=30, grid=False, color='#28829B')
ax.set_title('Historical PnL Histogram (2000~, {:2.0f} obs)'.format(len(dfPlot)),fontweight='bold')
ax.grid(ls='--')
ax.xaxis.set_major_locator(mticker.FixedLocator(ax.get_xticks().tolist()))
ax.set_xticklabels(['{:2.1%}'.format(i) for i in ax.get_xticks()])

x = dfPlot['PnL Total'].quantile(0.05)

ax.annotate('Perc 5%\n{:4.2%}'.format(x), 
                              xy=(x, val), xycoords='data', zorder=3,
                          xytext=(0, 60), textcoords='offset points', fontweight='bold',
                          fontsize=11, color=color1, ha='center',
                          bbox=dict(boxstyle="round", fc='silver' if x>0 else 'tomato', ec="0.5", alpha=0.8),
            arrowprops=dict(facecolor='r', arrowstyle="->", connectionstyle="arc3"))

x = dfPlot['PnL Total'].quantile(0.001)
ax.annotate('Perc 0.1%\n{:4.2%}'.format(x), 
                              xy=(x, val), xycoords='data', zorder=3,
                          xytext=(0, 80), textcoords='offset points', fontweight='bold',
                          fontsize=11, color=color1, ha='center',
                          bbox=dict(boxstyle="round", fc='silver' if x>0 else 'tomato', ec="0.5", alpha=0.8),
            arrowprops=dict(facecolor='r', arrowstyle="->", connectionstyle="arc3"))

fig_file = 'simu_bolsa.svg'
fig.savefig(fig_file, bbox_inches = "tight")
plt.show()
   