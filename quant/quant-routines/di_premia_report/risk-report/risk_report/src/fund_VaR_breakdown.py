import pandas as pd
import numpy as np
import datetime
import timeit
import matplotlib.pyplot as plt
import QuantLib as ql
import xlwings as xw
import fund_utils as fu


#%%
def main(dt_d0, str_fund, report_filename, day_target=-1):
#%%    
    _, connection = fu.get_DB_conn('prod')
    
    calendarBrazil = ql.Brazil()
    dt_d1 = calendarBrazil.advance(ql.Date.from_date(dt_d0), ql.Period(day_target, ql.Days)).to_date()
    
    str_sql = "SELECT v.[date_reference] as DateRef, v.parent_tree, v.node as Book, -v.[value]/n.NAV*10000 as Var_BPs " +\
                "FROM [risk].[measure] v INNER JOIN middle.NAV n on v.[date_reference] = n.[date_reference] and v.[trading_desk] = n.[trading_desk]  "+\
                "WHERE v.[risk_measure]='VaR' and v.[trading_desk]='{}' ".format(str_fund) +\
              " AND v.date_reference in ('{:%Y-%b-%d}', '{:%Y-%b-%d}')".format(dt_d0, dt_d1) +\
            "ORDER BY parent_tree DESC, v.node"
    dfVaR = pd.read_sql(str_sql, connection)
    str_dt = 'D{:2.0f}'.format(day_target)
    dfVaR.replace({dt_d0:'Today', dt_d1:str_dt}, inplace=True)
    
    connection.close()
    del str_sql

    #%%  
    color1, color2 = fu.color_palette[0], fu.color_palette[1]
    
    fig, axes = plt.subplots(nrows=1, ncols=1, figsize=(7, 3.6),  sharey=True)
    plt.tight_layout()
    
    dfTemp = dfVaR[dfVaR['parent_tree']=='Risk'].pivot(index='Book', columns='DateRef', values='Var_BPs')
    dfTemp = pd.concat([dfTemp, dfVaR[dfVaR['parent_tree']=='Fund'].pivot(index='Book', columns='DateRef', values='Var_BPs')])
    x = np.arange(len(dfTemp.index))
    for dt, w, s, f, c in zip(['Today', str_dt], [-.25, .125], [.5, .25], [13, 12], [color1,color2]):
        rects = axes.bar(x+w, height=dfTemp[dt], width=s, label=dt, zorder=3, color=c)
        for rect in rects:
            height = rect.get_height()
            axes.annotate('{:2.0f}'.format(height),
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', 
                    fontsize=f, zorder=5,
                    fontweight=('bold' if dt=='Today' else 'normal'))
            
    axes.grid(ls='--', axis='y')
    axes.axhline(180, label='Limit', ls='-', lw=2, color='r', zorder=4)
    axes.axhline(60, label='Target', ls='--', lw=1.5, color='r', zorder=4)
    warning_value = 144
    if dfTemp.loc['Fund', 'Today']>warning_value:
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
    
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_dashboard_var_breakdown.svg'.format(dt_d0, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    
    wb = xw.Book(report_filename)
    wb.sheets('Cover').pictures.add(wb.api.Path + '/' + fig_file, name='dashboard_var_breakdown', update=True)

#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt, str_fund = fu.get_config(['dt', 'str_fund'])
    report_filename = '../xls/RiskMap_model.xlsm'
    main(dt, str_fund, report_filename) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))