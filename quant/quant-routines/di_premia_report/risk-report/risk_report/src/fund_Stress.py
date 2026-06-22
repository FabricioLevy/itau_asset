import pandas as pd
import datetime
import timeit
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import xlwings as xw
import fund_utils as fu
import QuantLib as ql

def main(dt, str_fund, report_filename) :
#%%
    _, connection = fu.get_DB_conn('prod')

    dt_d1 = ql.Brazil().advance(ql.Date.from_date(dt), ql.Period(-1, ql.Days)).to_date()
    
    str_sql="SELECT v.[date_reference], v.node, v.[value]/n.NAV as Stress " +\
            "FROM [risk].[measure] v INNER JOIN middle.NAV n on v.[date_reference] = n.[date_reference] and v.[trading_desk] = n.[trading_desk]  "+\
            "WHERE v.[risk_measure]='Stress' and parent_tree in ('Risk', 'Fund') " +\
                "and v.[date_reference] in ('{:%Y-%m-%d}', '{:%Y-%m-%d}') and v.[trading_desk]='{}' ".format(dt, dt_d1, str_fund) +\
            "ORDER BY parent_tree DESC, node "
    dfStress = pd.read_sql(str_sql, connection)
    dfStress.replace({dt:'Today', dt_d1:'D-1'}, inplace=True)
    dfStress = dfStress.pivot(index='node', values='Stress', columns = 'date_reference').fillna(0)
    dfStress = dfStress.reindex( [i for i in dfStress.index if i != 'Fund'] + ['Fund'])
    connection.close()
    del str_sql

    #%%    
    color1, color2 = fu.color_palette[0], fu.color_palette[1]
    limit_value = -0.25 #fu.trader_limit['Fund'][1]
    warning_value = limit_value * 0.6
    
    fig, axes = plt.subplots(nrows=1, ncols=1, figsize=(7, 3.6))
    plt.tight_layout()
    dfStress['Today'].plot.bar(ax=axes, legend=False, zorder=3, color=color1, width=0.50, position=0.50)
    dfStress['D-1'].plot.bar(ax=axes, legend=False, zorder=2, color=color2, width=0.25, position=-0.75, alpha=1)
    for i, book in enumerate(dfStress.index):
        y = float(dfStress.loc[book, 'Today'])
        axes.text(i-0.1, y-0.005, '{:2.1f}'.format(y*100), va='top', color='r', ha='center', \
                      fontweight='heavy' if book=='Fund' else 'bold', \
                      fontsize=15 if book=='Fund' else 12)
    axes.axhline(0, lw=1, c='k')
    axes.set_xlabel('')
    axes.set_ylabel('% NAV', fontsize=13)
    axes.tick_params(labelsize=14)           
    axes.grid(axis='y', ls='--')
    axes.axhline(-0.15, c='r', lw=2, ls='--',label='Warning (-15%)')
    axes.axhline(-0.25, c='r', lw=2, ls='-', label='Policy Limit (-25%)')
    axes.legend(loc=3, fontsize=11, ncol=2)
    axes.set_ylim(top=0, bottom=-.26)
    axes.set_xlim(left=-0.5)
    dfStress.rename(index={'CUPOM CAMBIAL':'CUPOM\nCAMBIAL'},inplace=True)
    axes.set_xticklabels(dfStress.index, rotation=90)
    axes.get_xticklabels()[-1].set_weight("bold")
    axes.get_xticklabels()[-1].set_fontsize(16)
    axes.yaxis.set_major_locator(plt.MultipleLocator(0.05))
    if dfStress.loc['Fund', 'Today']<limit_value:
        axes.axhspan(limit_value, -0.30, facecolor='tomato', alpha=0.4)
    elif dfStress.loc['Fund', 'Today']<warning_value:
        axes.axhspan(warning_value, limit_value, facecolor='gold', alpha=0.2)
    ticks_loc = axes.get_yticks().tolist()
    axes.yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
    axes.set_yticklabels(["{:1.0%}".format(i) for i in ticks_loc], color='r')
  
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_dashboard_stress.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    
    wb = xw.Book(report_filename)
    wb.sheets('Cover').pictures.add(wb.api.Path + '/' + fig_file, name='dashboard_stress', update=True)

#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt, str_fund = fu.get_config(['dt', 'str_fund'])
    report_filename = '../xls/RiskMap_model.xlsm'
    main(dt, str_fund, report_filename) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))