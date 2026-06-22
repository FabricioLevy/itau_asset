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
    str_sql = f"""
                SELECT p.[date_reference],[primitive],[book]
                  ,[product_currency], ([delta]/n.NAV) as delta_perc
              FROM [lote45].[primitive] p INNER JOIN middle.NAV n
                  ON p.date_reference = n.date_reference and p.trading_desk = n.trading_desk
              WHERE primitive_class = 'Equity' and p.trading_desk = '{str_fund}'
              AND p.date_reference <= '{dt:%Y-%m-%d}'
      """
    dfPosition = pd.read_sql(str_sql, connection)
    
    str_tree = 'Traders'
    
    str_sql = f"""
            SELECT r.[date_reference],[parent_tree],[node],[risk_measure],[value]/n.NAV*(-10000) as value_bps
                FROM [risk].[measure] r 
                     INNER JOIN middle.NAV n
                      ON r.date_reference = n.date_reference and r.trading_desk = n.trading_desk
                WHERE r.date_reference <='{dt:%Y-%m-%d}'
                    and r.[trading_desk] = '{str_fund}'
                    and parent_tree='{str_tree}'
                """
    df = pd.read_sql(str_sql, connection)
    dfVaR = df[df['risk_measure']=='VaR'].pivot(index='date_reference', columns='node', values='value_bps')
    
    str_sql = f"""
       SELECT [parent_tree],[parent_node],[node],[book]
       FROM [lote45].[book_tree]
       WHERE parent_tree = '{str_tree}'
                """
    dfTree = pd.read_sql(str_sql, connection)    
    connection.close()
  
    nd = fu.Node(str_tree, dfTree)    
    dic_books = nd.to_inv_dict(str_tree)

    del str_sql

    dfPosition['trader'] = dfPosition['book'].apply(lambda x: dic_books[x])
    
    dfPos = dfPosition.pivot_table(index='date_reference', 
                                   columns=['trader', 'primitive'], 
                                   values='delta_perc', 
                                   aggfunc=np.sum).fillna(0)
    
    dfPosFundo = dfPosition.pivot_table(index='date_reference', 
                                   columns='primitive', 
                                   values='delta_perc', 
                                   aggfunc=np.sum)
    
    
    dfNet = dfPos.groupby(level = 0, axis = 1).sum()
    dfGross = dfPos.abs().groupby(level = 0, axis = 1).sum()
    dfRiskShare = fu.get_DailyRiskShare(dt, str_fund)
    
    for t in set(dfPos.columns.get_level_values(0)):
        dfNet[t] /= dfRiskShare[t]
        dfGross[t] /= dfRiskShare[t]
        dfVaR[t] /= dfRiskShare[t]  
        

#%%
    color1, color2 = fu.color_palette[0:2]   
    locator = mdates.AutoDateLocator(minticks=3, maxticks=7)
    formatter = mdates.ConciseDateFormatter(locator, 
                                            formats=['%b\n%Y', '%b', '%#d', '%H:%M', '%H:%M', '%S.%f'], 
                                            show_offset=False)
    
    t='FK'
    dfPlot = dfVaR[[t]].loc[datetime.date(2022,1,15):]
    dfPlot = dfPlot.join(dfNet[t], rsuffix='_NET').join(dfGross[t], rsuffix='_GROSS')
    
    fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(10, 6), sharex=True)  
                             # gridspec_kw = {'width_ratios':[5, 1]})
    plt.tight_layout()
    
    ax = axes[0]
    ax.set_title(f"{t}  -  VaR / Equity Gross and Net", fontweight='bold')
    ax.plot(dfPlot.index, dfPlot[t], lw=2, color=color2)
    ax.axhline(0, c='k', lw=0.5)
    ax.set_xlim(left=dfPlot.index[0])
    ax.set_ylabel('VaR (BPs)')

    ax = axes[1]
    ax.plot(dfPlot.index, dfPlot[t+'_NET'], ls='--', lw=2, c=color1, label='Net (%)')    
    ax.plot(dfPlot.index, dfPlot[t+'_GROSS'], ls='-', lw=2, c=color2, label='Gross (%)') 
    ax.set_ylabel('% NAV')
    ax.legend()
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    ax.xaxis.set_minor_locator(mdates.MonthLocator(interval=1))
    
    fig.align_ylabels()
    
    for ax in axes.flatten():
        ax.grid(ls='--')
    
    # # plt.subplots_adjust(hspace=0.05, wspace=0.1)
    
    # ax1.fill_between(dfPlot.index, 0, dfPlot['Long'], color=color2, alpha=0.6, 
    #                  label='Long ({:1.1%})'.format(dfPlot['Long'].iloc[-1]))
    # ax1.fill_between(dfPlot.index, 0, dfPlot['Short'], color='tomato', alpha=0.6,
    #                  label='Short ({:1.1%})'.format(dfPlot['Short'].iloc[-1]))
    # ax1.plot(dfPlot['Gross'], ls='--', lw=2, color='k', 
    #          label='Gross ({:1.1%})'.format(dfPlot['Gross'].iloc[-1]))
    # ax1.plot(dfPlot['Net'], color='k', lw=2.5,
    #          label='Net ({:1.1%})'.format(dfPlot['Net'].iloc[-1]))
    # ax1.axhline(0, lw=0.5, color='k')

    # ax1.legend(ncol=2)
    # ax1.set_xlim(left=dfPlot.index[0], right=dfPlot.index[-1])
    # ax1.grid(ls='--', which='both')
    
    # ax1.yaxis.set_major_locator(mticker.FixedLocator(ax1.get_yticks()))
    # ax1.set_yticklabels(['{:1.0%}'.format(x) for x in ax1.get_yticks()])

    # fig_file = '../output/temp_figs/{:%Y%m%d}_{}_equity_GrossNet.svg'.format(dt, str_fund)
    # fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    # wb = xw.Book(report_filename)
    # wb.sheets('Equity').pictures.add(wb.api.Path + '/' + fig_file, name='equity_GrossNet', update=True)
    # wb.sheets('Equity').pictures.add(fig, name='equity_GrossNet', update=True)
 
#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt = datetime.date(2022, 5, 27)
    str_fund = 'A1 Master FIM'

    report_filename = '../xls/RiskMap_model.xlsm'
    nav = fu.get_NAV(dt, str_fund)
    main(dt, str_fund, nav, report_filename) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))