import pandas as pd
import matplotlib as mpl
import datetime
import timeit
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import xlwings as xw
import fund_utils as fu

def main(dt, str_fund, report_filename, print_pdf=False):
    #%%
    dt_ini = fu.date_ini[str_fund]
    mtd, std = [max(dt_ini, i) for i in fu.get_PeriodToDate(dt)]

    _, connection = fu.get_DB_conn('prod')
    
    str_sql = "SELECT  [date_reference] as dtRef, [trading_desk] as asset, [share] as price "+\
              " FROM middle.[NAV] "+\
              " WHERE [trading_desk] = '{}'".format(str_fund)+\
              "UNION "+\
              "SELECT [date_reference],[product_id],[rate] "+\
                  "FROM [middle].[product_price] "+\
                  "WHERE [product_id]='CDI' AND [date_reference]>='{:%Y-%m-%d}'".format(dt_ini)
    
    df = pd.read_sql(str_sql, connection)
    connection.close()
    del str_sql
    
    
    dfPrice = df.pivot(index='dtRef', columns='asset', values='price')\
                .loc[dt_ini:dt].sort_index(ascending=True)
                
    dfPrice['CDI'] = ((1+dfPrice['CDI']/100)**(1/252)).cumprod().shift(1).fillna(1)    
                     
    dfPrice = dfPrice.fillna(method='bfill')
    dfPrice = dfPrice / dfPrice.iloc[0]
    
    dfReturn = dfPrice.pct_change().dropna()
    dfReturn.sort_index(inplace=True)
    
    benchmark = 'CDI'
    dfPrice['Alpha'] = (dfPrice[str_fund] / dfPrice[benchmark])
    dfPrice['RetAplic'] = dfPrice['Alpha'].iloc[-1]/dfPrice['Alpha']
    
    ret_mtd = dfPrice[str_fund][-1]/dfPrice.loc[mtd, str_fund] - 1
    ret_std = dfPrice[str_fund][-1]/dfPrice.loc[std, str_fund] - 1
    dfPrice -= 1
    dfPrice['std'] = dfPrice[str_fund].loc[std:]
    
    #%%

    color1, color2 = fu.color_palette[0], fu.color_palette[1]

    fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(6, 4.25),  sharex=True, gridspec_kw = {'height_ratios':[5, 2]})
    plt.tight_layout()
    axes[0].plot(dfPrice.index, dfPrice[str_fund], lw=2.5, ls='-', c=color1 , zorder=2, label='{} ({:1.2%})'.format(str_fund, dfPrice[str_fund].iloc[-1]))
    axes[0].plot(dfPrice.index, dfPrice[benchmark], lw=2.5, ls=':', c=color1 , zorder=2, label='{} ({:1.2%})'.format(benchmark, dfPrice[benchmark].iloc[-1]))
    axes[0].plot(dfPrice.index, dfPrice['std'], lw=5, ls='-', c=color2 , zorder=1, alpha=0.75)
    axes[0].axvline(std, ls=':', lw=1, color=color2)
    axes[1].axvline(std, ls=':', lw=1, color=color2)
    axes[0].axhline(0, lw=0.75, c='k')
    axes[0].grid(ls='--', which='both')
    axes[0].tick_params(labelsize=12)           
    axes[0].set_xlim(dfPrice.index[0], dfPrice.index[-1])
    axes[0].legend(loc=2,  prop={'size': 12})
    ticks_loc = axes[0].get_yticks().tolist()
    axes[0].yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
    axis_len = axes[0].get_ylim()[1]-axes[1].get_ylim()[0]
    axes[0].set_yticklabels(['{:.1%}'.format(x) if axis_len < 0.02 else '{:.0%}'.format(x) for x in ticks_loc])
   
    
    
    axes[0].annotate('STD\n{:+1.2%}'.format(ret_std), xytext=(0.8, 0.45), textcoords="axes fraction", 
                     xy=(std, dfPrice.loc[std, str_fund]), xycoords='data',
                     va="center", ha="center",fontweight='bold',
                      bbox=dict(boxstyle="round", fc='#28829B' if ret_std>0 else 'tomato', alpha=0.5),
                      arrowprops=dict(arrowstyle="->", connectionstyle="arc3, rad=-0.2", lw=1.5))
    axes[0].annotate('STD\n{:+1.2%}'.format(ret_std), xytext=(0.8, 0.45), textcoords="axes fraction", 
                     xy=(dfPrice.index[-1], dfPrice[str_fund].iloc[-1]), xycoords='data',
                     va="center", ha="center",fontweight='bold',
                      bbox=dict(boxstyle="round", fc='#28829B' if ret_std>0 else 'tomato', alpha=0.5),
                      arrowprops=dict(arrowstyle="->", connectionstyle="arc3, rad=0.2", lw=1.5))
    
    axes[0].annotate('Daily\n{:+1.2%}'.format(dfReturn[str_fund].iloc[-1]), xytext=(0.9, 0.85), textcoords="axes fraction",
                     xy=(dfPrice.index[-1], dfPrice[str_fund].iloc[-1]), xycoords="data", 
                     va="center", ha="center",fontweight='bold',
                      bbox=dict(boxstyle="round", fc=color2 if dfReturn[str_fund].iloc[-1]>0 else 'tomato'))
    if std != mtd:
        axes[0].annotate('MTD\n{:+1.2%}'.format(ret_mtd), xytext=(0.95, 0.45), textcoords="axes fraction",
                     xy=(dfPrice.index[-1], dfPrice[str_fund].iloc[-1]), xycoords="data", 
                     va="center", ha="center",fontweight='bold',
                     bbox=dict(boxstyle="round", fc=color2 if ret_mtd>0 else 'tomato'))
       
    
    
    dfPrice['RetAplic'].plot(ax=axes[1], title='Alpha by Investment Date',  color="k", lw=0.75, zorder=3)
    axes[1].axhline(0, lw=1, c='k')
    axes[1].fill_between(dfPrice['RetAplic'].index, 0, dfPrice['RetAplic'], where=dfPrice['RetAplic']>0 ,\
                        interpolate=True, alpha=0.8, color=color2, zorder=2)
    axes[1].fill_between(dfPrice['RetAplic'].index, 0, dfPrice['RetAplic'], where=dfPrice['RetAplic']<0 ,\
                        interpolate=True, alpha=.8, color='tomato', zorder=2)
    axes[1].grid(ls='--', which='both')
    axes[1].tick_params(labelsize=12)
    axes[1].set_xlim(dfPrice.index[0], dfPrice.index[-1])
    ticks_loc = axes[1].get_yticks().tolist()
    axes[1].yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))   
    axis_len = axes[1].get_ylim()[1]-axes[1].get_ylim()[0]
    axes[1].set_yticklabels(['{:.1%}'.format(x) if axis_len < 0.02 else '{:.0%}'.format(x) for x in ticks_loc])
    
    locator = mdates.AutoDateLocator(minticks=2, maxticks=7)
    formatter = mdates.ConciseDateFormatter(locator, formats=['%b\n%Y', '%b', '%d', '%H:%M', '%H:%M', '%S.%f'], show_offset=False)
    
    axes[1].xaxis.set_major_locator(locator)
    axes[1].xaxis.set_major_formatter(formatter)
    if len(dfPrice) <= 126:
        axes[1].xaxis.set_minor_locator(mdates.DayLocator(bymonthday=15))
    else:
        axes[1].xaxis.set_minor_locator(mdates.MonthLocator(interval=1))

    plt.gcf().autofmt_xdate(rotation=0, ha="center")
    axes[1].xaxis.label.set_visible(False)
    
    #%%    
    
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_dashboard_performance.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    
    wb = xw.Book(report_filename)
    wb.sheets('Cover').pictures.add(wb.api.Path + '/' + fig_file, name='dashboard_performance', update=True)
    #%%
    dic_eoms = fu.get_endOfMonths(dt, dt_ini)
    # effectiveDate = ql.Date.from_date(dt_ini)
    # terminationDate = ql.Brazil().endOfMonth(ql.Date.from_date(dt))
    # frequency = ql.Period('1M')
    # calendar = ql.Brazil()
    # convention = ql.ModifiedPreceding
    # terminationDateConvention = ql.ModifiedPreceding
    # rule = ql.DateGeneration.Backward
    # endOfMonth = False
    # schedule = ql.Schedule(effectiveDate, terminationDate, frequency, calendar,
    #                        convention, terminationDateConvention, rule, endOfMonth)
    # eom_dates = [i.to_date() if i!=terminationDate else dt for i in schedule]
    # del effectiveDate, terminationDate, frequency, calendar, convention, terminationDateConvention, rule, endOfMonth
    
    dfMonthRet = pd.DataFrame(index=dic_eoms.keys(), columns=dfPrice.columns)
    for dt_key, (dt1, dt2) in dic_eoms.items():
        dfMonthRet.loc[dt_key] = (1+dfPrice.loc[dt2])/(1+dfPrice.loc[dt1])-1
    
    dfMonthRet['dt'] = dfMonthRet.index
    dfMonthRet['year'] = dfMonthRet['dt'].apply(lambda x:x.year)
    dfMonthRet['month'] = dfMonthRet['dt'].apply(lambda x:x.month)
    
    dfRetFund = dfMonthRet.pivot(index='year', columns='month', values=str_fund)
    dfRetCDI = dfMonthRet.pivot(index='year', columns='month', values='CDI')
    #%%
    cmap = mpl.cm.get_cmap('bwr', 19).reversed()
    # norm = mpl.colors.Normalize(vmin=-0.06, vmax=0.06)
    norm = mpl.colors.TwoSlopeNorm(vmin=-0.06, vcenter=0., vmax=0.10)
    
    fig, axes = plt.subplots(len(dfRetFund.index), len(dfRetFund.columns), 
                             figsize=(10, len(dfRetFund.index)),
                             sharex=True, sharey=True)  
    fig.tight_layout(w_pad=0, h_pad=0)
    fig.subplots_adjust(wspace=0.05, hspace=0.05)
    for j,m in enumerate(dfRetFund.columns):
        ax = axes[0,j] if len(dfRetFund.index) >1 else axes[j]
        ax.set_title(f"{datetime.date(2000,m,1):%b}", fontsize=14,fontweight='bold')
    for i,y in enumerate(dfRetFund.index):
        ax = axes[i,0] if len(dfRetFund.index) >1 else axes[i]
        ax.set_ylabel(y, fontsize=14,fontweight='bold')
        for j,m in enumerate(dfRetFund.columns):
            ret_fund = dfRetFund.loc[y,m]
            ret_cdi = dfRetCDI.loc[y,m]
            ax = axes[i,j] if len(dfRetFund.index) >1 else axes[j]
            ax.set_xticks([])
            ax.set_yticks([])
            if pd.isna(ret_fund):
                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)
                ax.spines["left"].set_visible(False)
                ax.spines["bottom"].set_visible(False)
            else:
                ax.annotate(f"{ret_fund:6.2%}",xy=(0.5, 0.7), xycoords="axes fraction",
                        va='center',ha='center', fontweight='bold',fontsize=12,
                        color='k' if ret_fund>=0 else'r' )
                ax.annotate(f"{ret_cdi:6.2%}",xy=(0.5, 0.3), xycoords="axes fraction", 
                            va='center',ha='center')
                ax.set_facecolor(cmap(norm(ret_fund)))
                
    if print_pdf == 'Risk':
        fig_file = '../../risk_committee/tex/{0:%Y_%m}/figuras/{0:%Y%m}_{1}_monthBymonth_performance.pdf'.format(dt, str_fund)
        fig.savefig(fig_file, bbox_inches = "tight")       
    plt.show()
#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt, str_fund = fu.get_config(['dt_eom', 'str_fund'])
    
    report_filename = '../xls/RiskMap_model.xlsm'
    main(dt, str_fund, report_filename, 'Risk') 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))