import pandas as pd
import datetime
import timeit
import xlwings as xw
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
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
    
    dfPnl = df.pivot_table(index='date_reference', columns='Trader', values='pnl', aggfunc='sum').sort_index()
    dfPnl = dfPnl.loc[:dt_end].fillna(0)    
    dfPnl=dfPnl.drop('Shared', axis=1)


    del str_sql
    #%%
    dfRiskShare = fu.get_DailyRiskShare(dt_end, str_fund).loc[dt_end].sort_values(ascending=False)    
    cols = [i for i in dfRiskShare[dfRiskShare>0].index if i not in ['Fund']] 
    for c in cols:
        if c not in dfPnl.columns:
            dfPnl[c]=0
    
    dfPrice = (dfPnl+1).cumprod()-1
    for c in cols:
        dfPrice['HWM_'+c] = dfPrice[c].expanding().max()
        dfPrice['DD_'+c] =  (1+dfPrice[c]) / (1+dfPrice['HWM_'+c]) -1
    
    #%%
    color1, color2 = fu.color_palette[0], fu.color_palette[1]
    
    locator = mdates.AutoDateLocator(minticks=1, maxticks=4)
    formatter = mdates.ConciseDateFormatter(locator, formats=['%b\n%y', '%b', '%d', '', '%', ''], show_offset=False)
    
    fig, (axR, axD) = plt.subplots(nrows=2, ncols=len(cols), figsize=(12, 4.8), \
                                 gridspec_kw = {'height_ratios':[2, 1]},\
                                 sharex=True)
    plt.tight_layout()
    plt.subplots_adjust(hspace=0.10, wspace=0.3)
    
    for i, c in enumerate(cols):
        axR[i].set_title(c, fontsize=12, fontweight='bold')  
        axR[i].plot(dfPrice['HWM_'+c], lw=4, alpha=0.3, ls='-', c=color2, label='High Watermark')
        axR[i].plot(dfPrice[c], lw=2, label='{}'.format(c), c=color1)
        axR[i].set_xlim(left=dfPrice.index[0], right=dfPrice.index[-1])
        axR[i].set_ylim(top=max(0.004, axR[i].get_ylim()[1]))
        axR[i].axhline(0, c='k',lw=1)
        texts=[]
        texts.append(axR[i].text(dfPrice[c].index[-1], dfPrice[c][-1],\
                                 '{:2.2%}'.format(dfPrice[c][-1]), \
                              va='top', color='k', ha='right', fontweight='bold', fontsize=12))
        adjustText.adjust_text(texts, ax=axR[i]) 
        
        axD[i].plot(dfPrice['DD_'+c], c='r', lw=0.25, ls='-', label='Drawdown (%)')
        axD[i].fill_between(dfPrice.index, dfPrice['DD_'+c], 0, color='r', alpha=0.3)    
        # axD[i].xaxis.set_minor_locator(mdates.MonthLocator(bymonthday=15))
        axD[i].xaxis.label.set_visible(False)
        axD[i].set_xticks(list(axD[i].get_xticks()))
        texts=[]
        texts.append(axD[i].text(dfPrice.index[-1], dfPrice['DD_'+c][-1],\
                                 '{:2.2%}'.format(dfPrice['DD_'+c][-1]), \
                              va='top', color='r', ha='right', fontweight='bold', fontsize=12))
        if  dfPrice['DD_'+c][-1] < -0.01:
            adjustText.adjust_text(texts, ax=axD[i]) 
        
        axD[i].set_ylim(top=0, bottom=min(-0.008, dfPrice['DD_'+c].min()*1.1))
        for ax in [axR, axD]:
            ax[i].grid(ls='--', which='both')
            ax[i].tick_params(labelsize=11)  
            ticks_loc = ax[i].get_yticks().tolist()
            ax[i].yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
            ax[i].set_yticklabels(['{:2.1f}'.format(100*j) for j in ticks_loc], fontsize=10)
            
    
    # axD[0].set_ylim(top=0)
    # axD[0].set_yticklabels(['{:2.1%}'.format(j) for j in axD[0].get_yticks()])
    # axR[0].set_yticklabels(['{:2.1%}'.format(j) for j in axR[0].get_yticks()])
    
    axR[0].set_ylabel('Return (%)', fontsize=13)
    axD[0].set_ylabel('Drawdown (%)', fontsize=13)
    
    axD[0].xaxis.set_major_locator(locator)
    axD[0].xaxis.set_major_formatter(formatter)
    axD[0].xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[4,7,10])) 
    
    fig.align_ylabels()

    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_trader_dd.svg'.format(dt_end, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    
    wb = xw.Book(report_filename)
    wb.sheets('Trader').pictures.add(wb.api.Path + '/' + fig_file, name='trader_dd', update=True)
 
#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt, str_fund = fu.get_config(['dt', 'str_fund'])
    report_filename = '../xls/RiskMap_model.xlsm'
    main(dt, str_fund, report_filename) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))