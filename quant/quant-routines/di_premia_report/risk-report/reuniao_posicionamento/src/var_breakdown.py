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
           SELECT v.[date_reference] as DateRef, v.parent_tree, v.node as Book, -v.[value]/n.NAV*10000 as Var_BPs 
           FROM [risk].[measure] v INNER JOIN middle.NAV n 
               on v.[date_reference] = n.[date_reference] 
               and v.[trading_desk] = n.[trading_desk]  
        WHERE v.[risk_measure]='VaR' 
        and v.[trading_desk]='{}'  
        AND v.date_reference in ('{:%Y-%m-%d}', '{:%Y-%m-%d}')
        ORDER BY parent_tree DESC, v.node
        """
str_sql = str_sql.format(str_fund, lastweek.to_date(), dt)
dfVaR = pd.read_sql(str_sql, connection)
connection.close()
del str_sql

#%%  
color_palette =['#323E48','#28829B', 'teal', '#2F788D', 'royalblue', 'cornflowerblue', 'slategrey', 'silver', 'lightgrey']
color1, color2 = color_palette[0], color_palette[1]

fig, axes = plt.subplots(nrows=1, ncols=1, figsize=(7, 4),  sharey=True)
plt.tight_layout()

dfTemp = dfVaR[dfVaR['parent_tree']=='Risk'].pivot(index='Book', columns='DateRef', values='Var_BPs')
dfTemp = pd.concat([dfTemp, dfVaR[dfVaR['parent_tree']=='Fund'].pivot(index='Book', columns='DateRef', values='Var_BPs')])
if 'TRANSF' in dfTemp.index:
    dfTemp = dfTemp.drop('TRANSF')
x = np.arange(len(dfTemp.index))
for dt_i, w, s, f, c in zip([dt, lastweek.to_date()], [-.25, .125], [.5, .25], [13, 12], [color1,color2]):
    rects = axes.bar(x+w, height=dfTemp[dt_i], width=s, label='{:%d-%b}'.format(dt_i), zorder=3, color=c)
    for rect in rects:
        height = rect.get_height()
        axes.annotate('{:2.0f}'.format(height),
                xy=(rect.get_x() + rect.get_width() / 2, height),
                xytext=(0, 3),  # 3 points vertical offset
                textcoords="offset points",
                ha='center', va='bottom', 
                fontsize=f, zorder=5,
                fontweight=('bold' if dt_i==dt else 'normal'))
        
axes.grid(ls='--', axis='y')
axes.axhline(180, label='Limit', ls='-', lw=2, color='r', zorder=4)
axes.axhline(60, label='Target', ls='--', lw=1.5, color='r', zorder=4)
warning_value = 144
if dfTemp.loc['Fund', dt]>warning_value:
    axes.axhspan(warning_value, 180, facecolor='gold', alpha=0.4)

axes.set_ylim(top=max(200, dfTemp.max().max()*1.05))
axes.set_xlabel('')
axes.set_xticks(x)
axes.tick_params(labelsize=14)   
dfTemp.rename(index={'CUPOM CAMBIAL':'CUPOM\nCAMBIAL'},inplace=True)        
axes.set_xticklabels(dfTemp.index, rotation=90)
axes.get_xticklabels()[-1].set_weight("bold")

axes.set_ylabel('VaR (BPs)', fontsize=13)
# axes.set_title('Breakdown by Risk Factor', fontsize=14)
axes.legend(loc=2, fontsize=12)

fig_file = '..//tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_var_breakdown.pdf'.format(dt)
fig.savefig(fig_file, bbox_inches = "tight")
plt.show()
