import pandas as pd
import numpy as np
import datetime
import timeit
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
import xlwings as xw
import fund_utils as fu

#%%
def main(dt, str_fund, nav, report_filename): 
#%%
    _ , connection = fu.get_DB_conn('prod')
    str_sql = """
    SELECT cast (p.[date_reference] as datetime) as date_reference, book, [primitive],sum([delta]/n.NAV) as delta_perc
  FROM [lote45].[primitive] p INNER JOIN middle.NAV n ON p.date_reference = n.date_reference and p.trading_desk = n.trading_desk
  where primitive_class = 'Equity' and p.trading_desk = '{}'
  AND p.date_reference <= '{:%Y-%m-%d}'
  group by p.[date_reference], book, [primitive]
      """
    dfPosition = pd.read_sql(str_sql.format(str_fund, dt), connection)
    connection.close()
    del str_sql

#%%
    dfPos = dfPosition[['date_reference', 'primitive', 'delta_perc']].groupby(['date_reference', 'primitive']).sum().reset_index()
    dfPivot = dfPosition.pivot_table(index='date_reference', columns='primitive', values='delta_perc', aggfunc=np.sum).fillna(0)
    
    dt_ini = dfPivot.index[0]
    lst_idx = list(pd.date_range(datetime.date(dt_ini.year, dt_ini.month, 1), dfPivot.index[0], freq='B', closed='left')) +\
                list(dfPivot.index)
    
    dfPlot = pd.DataFrame(index=lst_idx, columns=['Net', 'Gross', 'Long', 'Short'])
    dfPlot['Long'] = dfPos[dfPos['delta_perc']>0].groupby('date_reference').sum()
    dfPlot['Short'] = dfPos[dfPos['delta_perc']<0].groupby('date_reference').sum()
    dfPlot = dfPlot.fillna(0)
    dfPlot['Net'] = dfPlot['Long'] + dfPlot['Short'] 
    dfPlot['Gross'] = dfPlot['Long'] - dfPlot['Short'] 

#%%
    color1, color2 = fu.color_palette[0:2]   
    locator = mdates.AutoDateLocator(minticks=3, maxticks=7)
    formatter = mdates.ConciseDateFormatter(locator, formats=['%b\n%Y', '%b', '%#d', '%H:%M', '%H:%M', '%S.%f'], show_offset=False)
    
    
    fig, ax1 = plt.subplots(nrows=1, ncols=1, figsize=(10, 3.5))  
                             # gridspec_kw = {'width_ratios':[5, 1]})
    plt.tight_layout()
    # plt.subplots_adjust(hspace=0.05, wspace=0.1)
    
    ax1.fill_between(dfPlot.index, 0, dfPlot['Long'], color=color2, alpha=0.6, 
                     label='Long ({:1.1%})'.format(dfPlot['Long'].iloc[-1]))
    ax1.fill_between(dfPlot.index, 0, dfPlot['Short'], color='tomato', alpha=0.6,
                     label='Short ({:1.1%})'.format(dfPlot['Short'].iloc[-1]))
    ax1.plot(dfPlot['Gross'], ls='--', lw=2, color='k', 
             label='Gross ({:1.1%})'.format(dfPlot['Gross'].iloc[-1]))
    ax1.plot(dfPlot['Net'], color='k', lw=2.5,
             label='Net ({:1.1%})'.format(dfPlot['Net'].iloc[-1]))
    ax1.axhline(0, lw=0.5, color='k')

    ax1.xaxis.set_major_locator(locator)
    ax1.xaxis.set_major_formatter(formatter)
    ax1.xaxis.set_minor_locator(mdates.MonthLocator(interval=1))
    ax1.legend(ncol=2)
    ax1.set_xlim(left=dfPlot.index[0], right=dfPlot.index[-1])
    ax1.grid(ls='--', which='both')
    
    ax1.yaxis.set_major_locator(mticker.FixedLocator(ax1.get_yticks()))
    ax1.set_yticklabels(['{:1.0%}'.format(x) for x in ax1.get_yticks()])

    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_equity_GrossNet.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    wb = xw.Book(report_filename)
    wb.sheets('Equity').pictures.add(wb.api.Path + '/' + fig_file, name='equity_GrossNet', update=True)
    # wb.sheets('Equity').pictures.add(fig, name='equity_GrossNet', update=True)
 
#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt, str_fund = fu.get_config(['dt', 'str_fund'])

    report_filename = '../xls/RiskMap_model.xlsm'
    nav = fu.get_NAV(dt, str_fund)
    main(dt, str_fund, nav, report_filename) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))