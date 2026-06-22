import pandas as pd
import datetime
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
import adjustText
import xlwings as xw
import fund_utils as fu

#%%
def main(dt, str_fund, report_filename, print_pdf=False):
    #%%
    _, connection = fu.get_DB_conn('prod')
        
    str_sql = "SELECT n.[date_reference], n.share as ValorCota "+\
              " FROM middle.NAV n "+\
              " WHERE n.[date_reference]<='{:%Y-%m-%d}' and n.[trading_desk]='{}'".format(dt, str_fund)
              
    dfFund = pd.read_sql(str_sql, connection, index_col='date_reference')
    dfFund.sort_index(inplace=True)
    
    benchmark = 'CDI'
    str_sql = "SELECT date_reference,rate/100 as CDI " +\
                "FROM [middle].[product_price] "+\
                " where product_id = 'CDI'"
    dfBM = pd.read_sql(str_sql, connection, index_col='date_reference')
    dfBM.sort_index(inplace=True)
    
    dfBM['BM'] = ((1+dfBM['CDI'].shift(1))**(1/252)).cumprod()
    
    connection.close()
    del str_sql
    #%%
    dfFund = dfFund.join(dfBM['BM']).sort_index()
    dfRet = dfFund / dfFund.iloc[0] - 1
    
    dfRet['HWM']=dfRet['ValorCota'].expanding().max()
    dfRet['DD'] =  (1+dfRet['ValorCota']) / (1+dfRet['HWM']) - 1
    
    #%%
    dfDD = pd.DataFrame(columns=['Date_Ini', 'Date_End', 'DD', 'DD_days', 'DD_days_recovery'])
    dic_DD = {}
    auxList = list(dfRet['DD'][dfRet['DD']==0].index)
    if  dfRet.index[-1] not in auxList:
        auxList.append(dfRet.index[-1])
    for (idx1, idx2) in zip(auxList, auxList[1:]):
        mdd = dfRet['DD'][idx1:idx2].min()
        if mdd != 0:
            idx = dfRet['DD'][idx1:idx2].idxmin()
            mdd = (1+dfRet.loc[idx, 'ValorCota']) / (1+dfRet.loc[idx, 'HWM']) - 1
            dic_DD[idx] = [mdd, idx1, idx2, len(dfRet.loc[idx1:idx]), len(dfRet.loc[idx:idx2])]
            dfDD.loc[idx] = [idx1, idx2, mdd, len(dfRet.loc[idx1:idx]), len(dfRet.loc[idx:idx2])-1]
    
    dic_top3dd = {}
    i = 1        
    for w in sorted(dic_DD, key=dic_DD.get)[:3]:
        dic_top3dd[w] = dic_DD[w]
        dfRet['DD' + str(i)] = dfRet['ValorCota'][dic_DD[w][1]:w]
        i+=1
    del i
    
    dfDD.sort_values('DD').to_excel('../output/temp_figs/{:%Y%m%d}_{}_dd.xlsx'.format(dt, str_fund))
    
    #%%
    color1, color2 = fu.color_palette[0], fu.color_palette[1]
        
    locator = mdates.AutoDateLocator(minticks=4, maxticks=7)
    formatter = mdates.ConciseDateFormatter(locator, formats=['%b\n%Y', '%b', '%d', '%H:%M', '%H:%M', '%S.%f'], show_offset=False)
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True,\
                                      gridspec_kw ={'height_ratios':[5, 2]})
    plt.tight_layout()
    
    ax1.plot(dfRet['HWM'], lw=6, alpha=0.3, ls='-', c=color2, label='High Water Mark')
    ax1.plot(dfRet['ValorCota'], lw=2, label='{}'.format(str_fund), c=color1)
    ax1.plot(dfRet['DD1'], lw=6, label='Top 3 Drawdowns', c='r', alpha=0.3)
    for i in range(len(dic_top3dd)-1):
        # print(i+1)
        ax1.plot(dfRet['DD'+str(i+2)], lw=6, label='', c='r', alpha=0.3)
        # ax1.plot(dfRet['DD'+str(i)], lw=6, label='', c='r', alpha=0.3)
    ax1.plot(dfRet['BM'], lw=1.5, ls='--', label=benchmark, c='grey')
    ax1.set_xlim(left=dfRet.index[0], right=dfRet.index[-1])
    ax1.axhline(0, lw=1, c='k')
    
    ax1.text(dfRet.index[-1], dfRet['HWM'].iloc[-1], " {:2.2%}".format(dfRet['HWM'].iloc[-1]),\
             alpha=0.5, c=color2, fontweight='bold', va='bottom', fontsize=14)
    ax1.text(dfRet.index[-1], dfRet['ValorCota'].iloc[-1], " {:2.2%}".format(dfRet['ValorCota'].iloc[-1]),\
             alpha=1, c=color1, fontweight='bold', va='top', fontsize=14)
    ax1.text(dfRet.index[-1], dfRet['BM'].iloc[-1], " {:2.2%}".format(dfRet['BM'].iloc[-1]),\
             alpha=1, c='grey', fontweight='bold', fontsize=13)
    ax1.legend(fontsize=14)
        
    ax2.plot(dfRet['DD'], c='r', lw=0.25, ls='-', label='Drawdown (%)')
    ax2.fill_between(dfRet.index, dfRet['DD'], 0, color='r', alpha=0.3)
    ax2.set_ylim(top=0, bottom=min(-.005, 1.2*ax2.get_ylim()[0]))
    
    ax2.xaxis.set_major_locator(locator)
    ax2.xaxis.set_major_formatter(formatter)
    if len(dfRet)<=126:
        ax2.xaxis.set_minor_locator(mdates.DayLocator(bymonthday=15))
    else:
        ax2.xaxis.set_minor_locator(mdates.MonthLocator(interval=1))
    ax2.xaxis.label.set_visible(False)
    # ax2.set_xticks(list(ax2.get_xticks()))
    ax2.legend(loc=3, fontsize=14)
    
    for ax in [ax1, ax2]:
        ax.grid(ls='--', which='both')
        ax.tick_params(labelsize=13)  
        ticks_loc = ax.get_yticks().tolist()
        ax.yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
        ax.set_yticklabels(['{:2.1%}'.format(i) for i in ticks_loc])
    
    texts = []
    for i, (k, v) in enumerate (dic_top3dd.items()):
        ax2.fill_between(dfRet.index, dfRet['DD'], 0, alpha=0.5, where=~dfRet['DD'+str(i+1)].isna(), color='r')
        texts.append(ax2.text(k, v[0], '{}={:2.2%}'.format('Max DD' if i==0 else 'DD#'+str(i+1), v[0]),\
                              va='top',  ha='right', fontweight='normal', fontsize=13))

    adjustText.adjust_text(texts)             
    ax2.text(dfRet['DD'].index[-1], dfRet['DD'].iloc[-1], ' Current\n DD={:2.2%}'.format(dfRet['DD'].iloc[-1]),\
             va='top', ha='left', fontweight='bold', fontsize=12)
        
        
    #%%    
    if print_pdf=='Risk':
        fig_file = '../../risk_committee/tex/{0:%Y_%m}/figuras/{0:%Y%m}_{1}_drawdown.pdf'.format(dt, str_fund)
        fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_drawdown.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    
    wb = xw.Book(report_filename)
    wb.sheets('DD_BT').pictures.add(wb.api.Path + '/' + fig_file, name='drawdown', update=True)


#%%
if __name__ == "__main__":
    
    dt, str_fund, print_pdf = fu.get_config(['dt', 'str_fund', 'print_pdf'])
    report_filename = '../xls/RiskMap_model.xlsm'
    
    main(dt, str_fund, report_filename, 'Risk') 
    

 

    