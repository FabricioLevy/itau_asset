import pandas as pd
import numpy as np
import datetime
import QuantLib as ql
import matplotlib.pyplot as plt

from a1db.a1sql import SQLConnection

import sys
sys.path.insert(1, '../../risk_report/src')
import fund_utils as fu

dt, str_fund, dt_1w = fu.get_config(['dt', 'str_fund', 'dt_1w'])

today = ql.Date.from_date(dt)
lastweek = ql.Date.from_date(dt_1w)

connection = SQLConnection().get_connection()
    
str_sql =   """ 
        SELECT v.[date_reference], v.node as Book, -v.[value]/n.NAV*10000 as VaR_BPs  
            FROM [risk].[measure] v  
            INNER JOIN middle.NAV n on v.[date_reference] = n.[date_reference] 
            and v.[trading_desk] = n.[trading_desk]   
            WHERE v.[risk_measure]='VaR'  
            	and v.parent_tree in ('Geography','Fund') 
            	and v.[trading_desk]='{}'
                and v.date_reference BETWEEN '{:%Y-%m-%d}' AND '{:%Y-%m-%d}'
 """
str_sql = str_sql.format(str_fund, lastweek.to_date(), dt)
df = pd.read_sql(str_sql, connection)
df['Book'].replace({'Onshore':'Brazil','Offshore':'International'}, inplace=True)
connection.close()
del str_sql
#%%
color_palette = ['#28829B', '#C9CBCB', 'dodgerblue']
    
dfVaR = df.pivot(index='date_reference', columns='Book', values='VaR_BPs').fillna(0)

dfFund = pd.DataFrame(dfVaR['Fund'])
sorted_cols = list(dfVaR.mean().sort_values(ascending=False).index)
dfVaR = dfVaR[sorted_cols].drop('Fund', axis=1)

data_perc = dfVaR.divide(dfVaR.sum(axis=1), axis=0)
data_perc['Day'] = ['{:%d-%b}'.format(i) for i in data_perc.index]
data_perc.set_index('Day', inplace=True)

dfFund['Day'] = ['{:%d-%b}'.format(i) for i in dfFund.index]
dfFund.set_index('Day', inplace=True)
#%%
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4), gridspec_kw = {'width_ratios':[3,  2]})
plt.tight_layout()
plt.subplots_adjust(wspace=0.1, hspace=0.05)

# data_perc.plot.area(ax=ax1, color=color_palette, legend=False)
ax1.stackplot(data_perc.index, [data_perc[i].values for i in data_perc.columns],\
              edgecolor='w',colors=color_palette)

axV = ax1.twinx()    
axV.plot(dfFund.index, dfFund['Fund'], ls='--',marker='s', lw=3,color='darkred', label='VaR Total') 
axV.set_ylim(bottom=0)
axV.set_ylabel('VaR (BPs)')
axV.legend(loc='lower right')
for i, ha in zip([0, -1],['left','right']):
    axV.text(dfFund.index[i], dfFund['Fund'].iloc[i], 
             '\n{:2.1f}'.format(dfFund['Fund'].iloc[i]), color='darkred',
             ha=ha, va='top', fontweight='bold', fontsize=12 )


ax1.set_title('Composição do VaR')
ax1.set_xlim(left=data_perc.index[0], right=data_perc.index[-1])

ax1.set_ylim((0,1))
ax1.legend(ncol=2, labels=data_perc.columns, loc='lower left')
ax1.grid(ls='--', alpha=0.5)
ax1.set_yticklabels(['{:2.0%}'.format(x) for x in ax1.get_yticks()])


def absolute_value(val):
    return np.round(val/100.*dfVaR.mean().sum(), 1)

axT = dfVaR.mean().plot.pie(ax=ax2,  shadow=False, fontsize=15, autopct=absolute_value, \
                      colors=color_palette, labels=None, \
                      wedgeprops={"edgecolor":"white",'linewidth': 1,
                    'linestyle': 'solid', 'antialiased': True})

for t in ax2.texts:
    if t.get_text() != '' :
        if float(t.get_text())/dfVaR.mean().sum() < 0.02:
            t.set_text('')    

ax2.set_title('Média Semanal do VaR (BPs)')
ax2.set_ylabel('')
ax2.legend(loc='lower center', ncol=2, fontsize=9, bbox_to_anchor=(0.5, -0.1),
           labels=['{} ({:2.1f})'.format(i, dfVaR.mean().loc[i]) for i in sorted_cols if i!='Fund'])

fig_file = '..//tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_hist_var_geo.pdf'.format(dt)
fig.savefig(fig_file, bbox_inches = "tight")
plt.show()