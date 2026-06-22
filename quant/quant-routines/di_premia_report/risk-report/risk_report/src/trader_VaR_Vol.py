import pandas as pd
import numpy as np
import datetime
import timeit
import xlwings as xw
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
import adjustText
import fund_utils as fu

#%%
def main(dt_end, str_fund, report_filename):
    #%%
    _, connection = fu.get_DB_conn('prod')
    
    str_sql = f"""
                SELECT b.[date_reference], b.book, sum([value]/n.NAV_D1) as pnl  
                FROM [lote45].[book_overview] b  
	                INNER JOIN middle.NAV n ON n.date_reference = b.date_reference and n.trading_desk = b.trading_desk  
                WHERE b.[measure] = 'PL' and b.[trading_desk] = '{str_fund}' 
                GROUP BY b.[date_reference], b.book
                """
    df = pd.read_sql(str_sql, connection)    
    
    str_tree = 'Traders'
    str_sql = """
            SELECT [parent_tree],[parent_node],[node],[book]
            FROM [lote45].[book_tree]
            WHERE parent_tree = '{}'
                    """
    dfTree = pd.read_sql(str_sql.format(str_tree), connection)
    nd = fu.Node(str_tree, dfTree)    
    dic_books = nd.to_inv_dict(str_tree)  
    
    df['Trader'] = df['book'].apply(lambda x: dic_books[x])
    
    dfPnl = df.pivot_table(index='date_reference', columns='Trader', values='pnl', aggfunc=np.sum).sort_index()
    dfPnl = dfPnl.loc[:dt_end].fillna(0)    
    
    str_sql = "SELECT v.[date_reference], v.node, -v.[value]/n.NAV*10000 as VaR_BPs "+\
            "FROM [risk].[measure] v INNER JOIN middle.NAV n on v.[date_reference] = n.[date_reference] and v.[trading_desk] = n.[trading_desk]  "+\
            "WHERE v.[risk_measure]='VaR' and v.[parent_tree] ='Traders' and v.[trading_desk]='{}'".format(str_fund)
    df = pd.read_sql(str_sql, connection)
    dfVaR = df.pivot(index='date_reference', columns='node', values='VaR_BPs')
    dfVaR.sort_index(inplace=True)
    dfVaR = dfVaR.loc[:dt_end].fillna(0)
    
    connection.close()
    del str_sql
    #%%
    dfRiskShare = fu.get_DailyRiskShare(dt_end, str_fund).loc[dt_end].sort_values(ascending=False)    
    cols = [i for i in dfRiskShare[dfRiskShare>0].index if i not in ['Fund']]    
    
    for c in cols:
        if c not in dfPnl.columns:
            dfPnl[c]=0
        if c not in dfVaR.columns:
            dfVaR[c]=0
    
    dfVol = (dfPnl.rolling(21, min_periods=2).std()*np.sqrt(252))
    
    dfChart = dfVaR.join(dfVol, lsuffix='_var', rsuffix='_vol')
    
    dfChart = dfChart.loc[datetime.date(dt_end.year-1, dt_end.month, 1):]
    
    #%%
    color1, color2 = fu.color_palette[0], fu.color_palette[1]
    
    fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=len(cols), figsize=(14, 7), \
                                 gridspec_kw = {'height_ratios':[3, 2]},\
                                 sharex=True, 
                                 sharey=False)
    plt.tight_layout(h_pad=3)
    
    # trader_limit = fu.get_RiskLimits(dt_end, str_fund)
    dfVaRLimit = fu.get_DailyRiskShare(dt_end, str_fund, 'var_limit')
    locator = mdates.AutoDateLocator(minticks=3, maxticks=4)
    formatter = mdates.ConciseDateFormatter(locator, formats=['%b\n%y', '%b\n%y', '%d', '', '', ''], show_offset=False)
    for i, c in enumerate(cols):
        var_limit = dfVaRLimit.loc[dt_end, c]
        ax1[i].set_title(c, fontsize=12, fontweight='bold')    
        dfChart[c+'_var'].plot(ax=ax1[i], label='', lw=1.5, c=color2, alpha=0.8)
        
        ax1[i].step(dfVaRLimit.index, dfVaRLimit[c], ls='--', c='r', label='VaR Limit\n({:2.0f} BPs)'.format(var_limit), lw=2)
        
        # dfVaRLimit[dfVaRLimit[c]>0][c].plot(ax=ax1[i], label='VaR Limit\n({:2.0f} BPs)'.format(var_limit), lw=2, c='r')
        
        # ax1[i].axhline(var_limit, ls='-', c='r', label='VaR Limit\n({:2.0f} BPs)'.format(var_limit), lw=2)
        ax1[i].set_xlim(dfChart.index[0], dfChart.index[-1])
        ax1[i].set_ylim(bottom=0)
        texts=[]
        texts.append(ax1[i].text(dfChart[c+'_var'].index[-1], dfChart[c+'_var'][-1],\
                                 '{:2.1f} bps '.format(dfChart[c+'_var'][-1]), \
                              va='top', color='k', ha='right', fontweight='bold', fontsize=13))
        adjustText.adjust_text(texts, ax=ax1[i]) 
        # ax1[i].annotate(' VaR={:2.1f}  '.format(dfChart[c+'_var'][-1]), ha='right',\
        #              size='11', xy=(dfChart[c+'_var'].index[-1], dfChart[c+'_var'][-1]))   
        if dfChart[c+'_var'][-1] > var_limit:
            ax1[i].set_facecolor('lightcoral')
    
        dfChart[c+'_vol'].plot(ax=ax2[i], label='Vol', lw=1.5, c=color2, alpha=0.8)
        
        texts=[]
        # ax2[i].annotate(' Vol={:2.1%} '.format(dfChart[c+'_vol'][-1]), ha='right',\
                         # size='11', xy=(dfChart[c+'_vol'].index[-1], dfChart[c+'_vol'][-1]))
        texts.append(ax2[i].text(dfChart[c+'_vol'].index[-1], dfChart[c+'_vol'][-1],\
                                 '{:2.1%} '.format(dfChart[c+'_vol'][-1]), \
                              va='top', color='k', ha='right', fontweight='bold', fontsize=13))
        adjustText.adjust_text(texts, ax=ax2[i]) 
        ax2[i].set_ylim(bottom=0, top=max(0.005, ax2[i].get_ylim()[1]))
        ticks_loc = ax2[i].get_yticks().tolist()
        ax2[i].yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
        ax2[i].set_yticklabels(['{:3.1%}'.format(x) for x in ticks_loc])
    
        for axi in [ax1, ax2]:
            axi[i].tick_params(labelsize=11) 
            axi[i].grid(ls='--', which='major')
            axi[i].grid(ls=':', which='minor')
            axi[i].set_xlabel('')
        ax1[i].legend(loc='upper center',  prop={'size': 10}, bbox_to_anchor=(0.5, 0))
        # ax2[i].legend(loc=2,  prop={'size': 10})#, bbox_to_anchor=(0.5, -0.2))
    
    ax1[0].set_ylabel('VaR (BPs)')
    ax2[0].set_ylabel('Vol 21d (%)')
    ax2[0].xaxis.set_major_locator(locator)
    ax2[0].xaxis.set_major_formatter(formatter)
    ax2[0].xaxis.set_minor_locator(mdates.MonthLocator())  #bymonth=[4,7,10]       

    fig.align_ylabels()

    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_trader_var_vol.svg'.format(dt_end, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    
    wb = xw.Book(report_filename)
    wb.sheets('Trader').pictures.add(wb.api.Path + '/' + fig_file, name='trader_var_vol', update=True)

#%%
#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt, str_fund = fu.get_config(['dt', 'str_fund'])
    report_filename = '../xls/RiskMap_model.xlsm'
    main(dt, str_fund, report_filename) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))