import pandas as pd
import numpy as np
import datetime
import timeit
import xlwings as xw
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import fund_utils as fu

#%%
def main(dt_end, str_fund, report_filename, print_pdf=False):
    
    _, connection = fu.get_DB_conn('prod')
    
    str_sql = "SELECT  cast([date_reference] as Date) as dtRef,[share] as price "+\
               " FROM [middle].[NAV] " +\
               " WHERE trading_desk='{}'".format(str_fund)
    dfPrice = pd.read_sql(str_sql, connection, index_col='dtRef')
    dfPrice.sort_index(inplace=True)
    dfPrice = dfPrice.loc[:dt_end]
    
    str_sql = "SELECT v.[date_reference] as dtRef, -v.[value]/n.NAV*10000 as VaR_BPs "+\
            "FROM [risk].[measure] v INNER JOIN middle.NAV n on v.[date_reference] = n.[date_reference] and v.[trading_desk] = n.[trading_desk]  "+\
            "WHERE v.[risk_measure]='VaR' and v.[parent_tree] = 'Fund' and v.[node]='Fund' and v.[trading_desk]='{}'".format(str_fund)
    dfVaR = pd.read_sql(str_sql, connection, index_col='dtRef')
    dfVaR.sort_index(inplace=True)
    dfVaR = dfVaR.loc[:dt_end]
    
    connection.close()
    del str_sql
    #%%
    color1, color2 = fu.color_palette[0], fu.color_palette[1]
        
    dfReturn = dfPrice.pct_change().dropna()
    dfVol = dfReturn.rolling(21, min_periods=2).std()*np.sqrt(252)
    dfAvgVol = dfReturn.expanding().std()*np.sqrt(252)
    
    fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(6, 4.5), \
                                 gridspec_kw = {'height_ratios':[1, 1]},\
                                 sharex=True, sharey=False)
    plt.tight_layout()
    
    # axes[0].set_title('Historical VaR and Vol(21d)', fontsize=15, fontweight='bold')
    
    dfVaR['VaR_BPs'].plot(ax=axes[0], label='VaR (BPs)', lw=3, c=color1)
    axes[0].axhline(60, ls='--', c='r', label='VaR Target (60 BPs)', lw=1.5)
    axes[0].axhline(180, ls='-', c='r', label='VaR Limit (180 BPs)', lw=2)
    axes[0].tick_params(labelsize=14)           
    axes[0].set_xlim(dfVaR.index[0], dfVaR.index[-1])
    axes[0].annotate(' VaR={:2.1f}  '.format(dfVaR['VaR_BPs'][-1]), ha='left',\
                     size='12', xy=(dfVaR.index[-1], dfVaR['VaR_BPs'][-1]))
    
    
    dfVol['price'].plot(ax=axes[1], label='Vol 21d (%)', lw=3, c=color1)
    axes[1].plot(dfAvgVol['price'], lw=2, ls='-', c=color2, alpha=0.3)
    axes[1].tick_params(labelsize=14)   
    axes[1].axhline(0.06, ls='--', c='r', label='Vol Target (6.0%)', lw=1.5)
    axes[1].set_ylim(top=max(0.08, dfVol['price'].max()))
    ticks_loc = axes[1].get_yticks().tolist()
    axes[1].yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
    axes[1].set_yticklabels(['{:2.0%}'.format(x) for x in ticks_loc])
    
    locator = mdates.AutoDateLocator(minticks=3, maxticks=7)
    formatter = mdates.ConciseDateFormatter(locator, formats=['%b\n%Y', '%b', '%d', '%H:%M', '%H:%M', '%S.%f'], show_offset=False)
    
    axes[1].xaxis.set_major_locator(locator)
    axes[1].xaxis.set_major_formatter(formatter)
    if len (dfVaR) < 126:
        axes[1].xaxis.set_minor_locator(mdates.MonthLocator(bymonthday=15))
    else:
        axes[1].xaxis.set_minor_locator(mdates.MonthLocator(interval=1))
    axes[1].annotate(' Vol={:2.1%}  '.format(dfVol['price'][-1]), ha='left',\
                     size='12', xy=(dfVol.index[-1], dfVol['price'][-1]))
    
    for i in [0, 1]:
        axes[i].legend( prop={'size': 12})
        axes[i].grid(ls='--', which='both')
        axes[i].set_xlabel('')
    
    if print_pdf:
         fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_{1}_var_vol.pdf'.format(dt_end, str_fund)
         fig.savefig(fig_file, bbox_inches = "tight")

    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_dashboard_var_vol.svg'.format(dt_end, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")

    wb = xw.Book(report_filename)
    wb.sheets('Cover').pictures.add(wb.api.Path + '/' + fig_file, name='dashboard_var_vol', update=True)
        
    plt.show()  
      

#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt, str_fund = fu.get_config(['dt', 'str_fund'])

    report_filename = '../xls/RiskMap_model.xlsm'
    main(dt, str_fund, report_filename, False) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))