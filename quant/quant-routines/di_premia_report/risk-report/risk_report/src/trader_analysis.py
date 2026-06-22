import pandas as pd
import numpy as np
import datetime
import timeit
import xlwings as xw
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import matplotlib.gridspec as gridspec
import adjustText
import fund_utils as fu
from scipy.stats import norm
import squarify # pip install squarify (algorithm for treemap)


#%%
def main(dt, str_fund, report_filename, print_pdf=False):
    #%%
    _, connection = fu.get_DB_conn('prod')
    mtd, std = [max(fu.date_ini[str_fund], i) for i in fu.get_PeriodToDate(dt)]
    # std = datetime.date(2021, 11, 30)
    
    str_tree = 'Traders'
    str_sql = """
       SELECT [parent_tree],[parent_node],[node],[book]
       FROM [lote45].[book_tree]
       WHERE parent_tree = '{}'
                """
    dfTree = pd.read_sql(str_sql.format(str_tree), connection)
    nd = fu.Node(str_tree, dfTree)    
    dic_books = nd.to_dict(str_tree)
    inv_books = {}
    for k, v in dic_books.items():
        for vi in v:
            inv_books[vi] = k

    str_sql =   """ 
         SELECT b.[date_reference], b.book, [measure], sum([value]/n.NAV_D1) as PnL_Perc  
         FROM [lote45].[book_overview] b  
           		INNER JOIN middle.NAV n ON n.date_reference = b.date_reference and n.trading_desk = b.trading_desk
        WHERE [measure] = 'PL'  and b.date_reference <='{:%Y-%m-%d}'
            and b.[trading_desk] = '{}'
--            and not (book in ('GB Cupom Cambial', 'MS Cupom Cambial', 'MS Cupom Cambial 2'))
--            and not (book in ('GB Cupom Cambial', 'MS Cupom Cambial', 'MS Cupom Cambial 2') and b.[date_reference]='{:%Y-%m-%d}')
        GROUP BY b.[date_reference], b.book,[measure] 
        """
    str_sql = str_sql.format(dt, str_fund, dt)
    df = pd.read_sql(str_sql, connection)
    df['book'].replace(inv_books, inplace=True)
    dfPnl = df.pivot_table(index='date_reference', columns='book', values='PnL_Perc', aggfunc=np.sum).fillna(0).sort_index()
    dfPnl['Fund'] = dfPnl.sum(axis=1)
    dfPnl.drop('Shared', axis=1, inplace=True)
    
    str_sql = """
        SELECT v.[date_reference], v.node, -v.[value]/n.NAV*10000 as VaR_BPs 
        FROM [risk].[measure] v INNER JOIN middle.NAV n on v.[date_reference] = n.[date_reference] and v.[trading_desk] = n.[trading_desk]
        WHERE v.[risk_measure]='VaR' and v.[trading_desk]='{}'
            AND (v.[parent_tree] ='Traders' or (v.[parent_tree] = 'Fund' and v.[node]='Fund'))
            """
    str_sql = str_sql.format(str_fund) 
    df = pd.read_sql(str_sql, connection)
    dfVaR = df.pivot(index='date_reference', columns='node', values='VaR_BPs')
    dfVaR.sort_index(inplace=True)
    dfVaR = dfVaR.loc[:dt].fillna(0)   
   
    connection.close()
    del str_sql, connection, nd, dfTree, str_tree, k, v, vi
    #%%
    dfRiskShare = fu.get_DailyRiskShare(dt, str_fund)

    #Put 'Fund' at end and list traders sorted by risk_share and remove traders with zero share
    dic_riskshare = dfRiskShare.loc[dt].sort_values(ascending=False).to_dict()   
    cols = [i for i,v in dic_riskshare.items() if (i not in ['Fund']) and (v>0)] + ['Fund']
    
    
    for c in cols:
        if c not in dfPnl.columns:
            dfPnl[c]=0
        if c not in dfVaR.columns:
            dfVaR[c]=0
        dfPnl[c + "_adj"] =dfPnl[c] / dfRiskShare[c]
        dfVaR[c + "_adj"] =dfVaR[c] / dfRiskShare[c]
    
    diversification = dfVaR[cols].drop('Fund', axis=1).sum(axis=1) / dfVaR['Fund']
    
    vol = dfPnl.std() * np.sqrt(252)
    dfVol = dfPnl.rolling(21, min_periods=5).std()*np.sqrt(252)
    
    wb = xw.Book(report_filename)
    sht = 'Trader_2'
    dfPrice = plot_ITD(cols, dfPnl.copy(), wb, dt, str_fund, print_pdf)
    dfPrice.iloc[-1, :] = dfPrice.iloc[-1, :].fillna(0)
    dfDD = dfPrice[[col for col in dfPrice.columns if 'DDLim' in col]]
    dfDD.columns = ['DD_' + col for col in cols]
    str_fig = 'trader_dd'
    plot_charts(cols, dfVol, dfVaR, dfPrice, wb, sht, str_fig, dt, str_fund, print_pdf)
    
    sht = 'Trader_STD'
    dfPrice = plot_STD(std, cols, dfPnl.copy(), wb, dt, str_fund, print_pdf)
    str_fig = 'trader_dd_std'
    plot_charts_2(cols, dfVol.loc[std:], dfVaR.loc[std:], dfPrice,  wb, sht, str_fig, dt, str_fund, dfDD.loc[std:],print_pdf)
    
    # dfPrice = (dfPnl[[c + "_adj" for c in cols]]+1).cumprod()-1
    # for c in cols:
    #     dfPrice['HWM_'+c] = dfPrice[c + "_adj"].expanding().max()
    #     dfPrice['DD_'+c] =  (1+dfPrice[c + "_adj"]) / (1+dfPrice['HWM_'+c]) -1
    #     dt_stop = fu.last_stops.get(c, datetime.date(2020,4,1))
    #     dfPrice['HWMLim_'+c] = dfPrice[c + "_adj"].loc[dt_stop:].expanding().max()
    #     dfPrice['DDLim_'+c] =  (1+dfPrice[c + "_adj"]) / (1+dfPrice['HWMLim_'+c]) -1
    
 #%%
def plot_charts(cols, dfVol, dfVaR, dfPrice, wb, sht, str_fig, dt, str_fund, print_pdf=False):
    #%%
    color1, color2 = fu.color_palette[0], fu.color_palette[1]
    locator = mdates.AutoDateLocator(minticks=1, maxticks=3)
    formatter = mdates.ConciseDateFormatter(locator, formats=['%b\n%y', '%b', '%d', '%H:%M', '%H:%M', '%S.%f'], show_offset=False)
    
    fig, (axVaR, axVol, axDD, axDDLimit) = plt.subplots(nrows=4, ncols=len(cols), figsize=(10, 10), \
                                  gridspec_kw = {'height_ratios':[1,1,1,1.5]},\
                                  sharex=True, sharey='row')
    plt.tight_layout()
    plt.subplots_adjust(hspace=0.10, wspace=0.22)
    
    for i, c in enumerate(cols):
        
        for dd in [0.93, 0.90]:
            stop_ret = dd/(1+dfPrice.loc[dt,'DDLim_'+c])-1
            vol21d = dfVaR.loc[dt,c+'_adj']/10_000/1.645 * np.sqrt(21)
            prob_stop = 2*norm.cdf(stop_ret, loc=0, scale=vol21d) if stop_ret < 0 else 1
            axDDLimit[i].text(dfPrice.index[0], dd-1, ' P={:3.0%}'.format(prob_stop), 
                          va='bottom', fontweight='bold', fontsize=9, zorder=6)
    
    
    
        multiplier = 1 if c == 'Fund' else 1.166666
        axVaR[i].set_title(c, fontsize=12, fontweight='bold')  
        axVaR[i].plot(dfVaR[c + "_adj"], lw=2, ls='-', c=color2)
        axVaR[i].axhline(180*multiplier, lw=1.5, color='r', ls="-")
        if c=='Fund':        
            axVaR[i].axhline(60*multiplier, lw=2, color='r', ls=":")
        v = dfVaR.iloc[-1][c + "_adj"]
        bbox_props = dict(boxstyle="round", fc="w", ec="0.5", alpha=0.3)
        if not np.isnan(v):
            axVaR[i].annotate('{:2.1f}'.format(v), xy=(dfVaR.index[-1], v), xycoords='data', 
                          xytext=(0.3, 0.5), textcoords='axes fraction', fontweight='bold',
                          fontsize=12, color=color1, bbox=bbox_props,
                          arrowprops=dict(facecolor=color2, arrowstyle="->", connectionstyle="arc3"))

        axVol[i].plot(dfVol[c + "_adj"], lw=2, ls='-', c=color2)
        if c=='Fund':
            axVol[i].axhline(0.08*multiplier, lw=2, color='r', ls=":")
            axVol[i].axhline(0.06*multiplier, lw=2, color='r', ls=":")
            axVol[i].fill_between(dfVol.index, 0.06*multiplier, 0.08*multiplier, color='tomato',
                                  alpha=0.3, label='vol trgt') 
        v = dfVol.iloc[-1][c + "_adj"]
        if not np.isnan(v):
            axVol[i].annotate('{:2.1%}'.format(v), xy=(dfVol.index[-1], v), xycoords='data',
                          xytext=(0.4, 0.68), textcoords='axes fraction', fontweight='bold',
                          fontsize=12, color=color1,
                          arrowprops=dict(facecolor=color2, arrowstyle="->", connectionstyle="arc3"))
       
        axDD[i].plot(dfPrice['DD_'+c], c='r', lw=0.25, ls='-', label='Drawdown (%)')
        axDD[i].fill_between(dfPrice.index, dfPrice['DD_'+c], 0, color='r', alpha=0.3) 
        v = dfPrice['DD_'+c].iloc[-1]
        if not np.isnan(v):
            axDD[i].annotate('{:2.2%}'.format(v), xy=(dfPrice.index[-1], v), xycoords='data',
                          xytext=(0.2, 0.5), textcoords='axes fraction', fontweight='bold',
                          fontsize=11, color='r' if v<0 else color1, bbox=bbox_props,
                          arrowprops=dict(facecolor='r', arrowstyle="->", connectionstyle="arc3"),
                          )
            axDD[i].annotate('{:2.2%}'.format(dfPrice['DD_'+c].iloc[-2]), xy=(dfPrice.index[-1], v), xycoords='data',
                          xytext=(0.1, 0.35), textcoords='axes fraction', fontweight='normal',
                          fontsize=10, color='r', bbox=bbox_props                          
                          )
        
        
        bbox_props = dict(boxstyle="round", fc="tomato", ec="0.5", alpha=0.3)
        axDDLimit[i].plot(dfPrice['DDLim_'+c], c='r', lw=0.25, ls='-')
        axDDLimit[i].axhline(-0.07, c='r', lw=2, ls=':', label='Warning')
        axDDLimit[i].axhline(-0.1, c='r', lw=1.5, ls='-', label='Limit')
        axDDLimit[i].fill_between(dfPrice.index, dfPrice['DDLim_'+c], 0, color='r', alpha=0.3) 
        v = dfPrice['DDLim_'+c].iloc[-1]
        if not np.isnan(v):
             axDDLimit[i].annotate('{:2.1%}'.format(v), xy=(dfPrice.index[-1], v), xycoords='data',
                          xytext=(0.25, 0.5), textcoords='axes fraction', fontweight='bold',
                          fontsize=12, color='r' if v<0 else color1, bbox=bbox_props,
                          arrowprops=dict(facecolor='r', arrowstyle="->", connectionstyle="arc3"),
                          )
        if v < -0.07:
            axDDLimit[i].fill_between(dfPrice.index, -0.07, -0.10, color='gold', alpha=0.5) 

        
        dt_stop = dfPrice['DDLim_'+c].first_valid_index()
        dt_stop = dt if dt_stop is None else dt_stop
        if (dt_stop > fu.date_ini[str_fund]):
            axDD[i].axvline(dt_stop, lw=1.5, color='b', ls=':')
            axDDLimit[i].annotate('{:%d%b%y}'.format(dt_stop), xy=(dt_stop, 0), xycoords='data',
                          xytext=(0.15, 0.85), textcoords='axes fraction', fontweight='bold',
                          fontsize=9, color='b', 
                          bbox=dict(boxstyle="round", fc="b", ec="0.5", alpha=0.3),
            arrowprops=dict(facecolor='r', arrowstyle="->", connectionstyle="arc3"),
            )
                
        for ax in [axVaR, axVol, axDD, axDDLimit]:
            ax[i].grid(ls='--', which='both')
    
    axVaR[0].set_ylabel('VaR (BPs)', fontsize=13)
    axVaR[0].set_ylim(bottom=0)
    axVaR[0].set_xlim(left=dfVaR.index[0], right=dfVaR.index[-1])
    axVaR[0].xaxis.set_major_locator(locator)
    axVaR[0].xaxis.set_major_formatter(formatter)
    axVaR[0].xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[4,7,10]))
        
    axVol[0].set_ylabel('Vol 21d (%)', fontsize=13)
    axVol[-1].legend(fontsize=9)
    axVol[0].set_ylim(bottom=0)
    # ticks_loc = axVol[0].get_yticks().tolist()
    axVol[0].yaxis.set_major_locator(ticker.FixedLocator(axVol[0].get_yticks().tolist()))
    axVol[0].set_yticklabels(['{:2.0%}'.format(j) if j!=0 else '-' for j in axVol[0].get_yticks()])
    
    axDD[0].set_ylabel('Drawdown STD (%)' if  str_fig == 'trader_dd_std' else 'Drawdown ITD (%)', fontsize=13)
    axDD[0].set_ylim(top=0)
    axDD[0].yaxis.set_major_locator(ticker.FixedLocator(axDD[0].get_yticks().tolist()))
    axDD[0].set_yticklabels(['{:2.0%}'.format(j) if j!=0 else '-' for j in axDD[0].get_yticks()], color='r')
    
    axDDLimit[0].set_ylabel('Drawdown since Last Stop (%)', fontsize=13, fontweight='bold')
    axDDLimit[0].set_ylim(top=0)
    axDDLimit[0].yaxis.set_major_locator(ticker.FixedLocator(axDDLimit[0].get_yticks().tolist()))
    axDDLimit[0].set_yticklabels(['{:2.0%}'.format(j) if j!=0 else '-' for j in axDDLimit[0].get_yticks()], color='r')
    axDDLimit[-1].legend(loc=(0.01, 0.12), fontsize=9)
    
    for ax in [axVaR, axVol, axDD, axDDLimit]:
        ax[-1].set_facecolor('lightgrey')
    
    fig.align_ylabels()
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_trader_1.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    wb.sheets(sht).pictures.add(wb.api.Path + '/' + fig_file, name=str_fig, update=True)
    # wb.sheets(sht).pictures.add(fig, name=str_fig, update=True)

#%%

def plot_charts_2(cols, dfVol, dfVaR, dfPrice, wb, sht, str_fig, dt, str_fund,dfDD, print_pdf=False):
    color1, color2 = fu.color_palette[0], fu.color_palette[1]
    
    locator = mdates.AutoDateLocator(minticks=1, maxticks=3)
    formatter = mdates.ConciseDateFormatter(locator, formats=['%b\n%y', '%b', '%d', '%H:%M', '%H:%M', '%S.%f'], show_offset=False)
    
    fig, (axVaR, axVol, axDD) = plt.subplots(nrows=3, ncols=len(cols), figsize=(10, 10), \
                                  gridspec_kw = {'height_ratios':[1,1,1]},\
                                  sharex=True, sharey='row')
    plt.tight_layout()
    plt.subplots_adjust(hspace=0.10, wspace=0.22)
    
    for i, c in enumerate(cols):
    
        multiplier = 1 if c == 'Fund' else 1.166666
        axVaR[i].set_title(c, fontsize=12, fontweight='bold')  
        axVaR[i].plot(dfVaR[c + "_adj"], lw=2, ls='-', c=color2)
        axVaR[i].axhline(180*multiplier, lw=1.5, color='r', ls="-")
        if c=='Fund':
            axVaR[i].axhline(60*multiplier, lw=2, color='r', ls=":")
        v = dfVaR.iloc[-1][c + "_adj"]
        bbox_props = dict(boxstyle="round", fc="w", ec="0.5", alpha=0.3)
        if not np.isnan(v):
            axVaR[i].annotate('{:2.1f}'.format(v), xy=(dfVaR.index[-1], v), xycoords='data', 
                          xytext=(0.35, 0.5), textcoords='axes fraction', fontweight='bold',
                          fontsize=12, color=color1, bbox=bbox_props,
                          arrowprops=dict(facecolor=color2, arrowstyle="->", connectionstyle="arc3"))

        axVol[i].plot(dfVol[c + "_adj"], lw=2, ls='-', c=color2)
        if c=='Fund':
            axVol[i].axhline(0.08*multiplier, lw=2, color='r', ls=":")
            axVol[i].axhline(0.06*multiplier, lw=2, color='r', ls=":")
            axVol[i].fill_between(dfVol.index, 0.06*multiplier, 0.08*multiplier, color='tomato',
                              alpha=0.3, label='vol trgt') 
        v = dfVol.iloc[-1][c + "_adj"]
        if not np.isnan(v):
            axVol[i].annotate('{:2.1%}'.format(v), xy=(dfVol.index[-1], v), xycoords='data',
                          xytext=(0.4, 0.68), textcoords='axes fraction', fontweight='bold',
                          fontsize=12, color=color1,
                          arrowprops=dict(facecolor=color2, arrowstyle="->", connectionstyle="arc3"))
       
        axDD[i].plot(dfDD['DD_'+c], c='r', lw=0.25, ls='-', label='Drawdown (%)')
        axDD[i].fill_between(dfDD.index, dfDD['DD_'+c], 0, color='r', alpha=0.3) 
        v = dfDD['DD_'+c].iloc[-1]
        if not np.isnan(v):
            axDD[i].annotate('{:2.2%}'.format(v), xy=(dfDD.index[-1], v), xycoords='data',
                          xytext=(0.2, 0.5), textcoords='axes fraction', fontweight='bold',
                          fontsize=11, color='r' if v<0 else color1, bbox=bbox_props,
                          arrowprops=dict(facecolor='r', arrowstyle="->", connectionstyle="arc3"),
                          )
            axDD[i].annotate('{:2.2%}'.format(dfDD['DD_'+c].iloc[-2]), xy=(dfDD.index[-1], v), xycoords='data',
                          xytext=(0.1, 0.35), textcoords='axes fraction', fontweight='normal',
                          fontsize=10, color='r', bbox=bbox_props                          
                          )
        
        
        bbox_props = dict(boxstyle="round", fc="tomato", ec="0.5", alpha=0.3)
        # v = dfDD['DDLim_'+c].iloc[-1]
                
        for ax in [axVaR, axVol, axDD]:
            ax[i].grid(ls='--', which='both')
    
    axVaR[0].set_ylabel('VaR (BPs)', fontsize=13)
    axVaR[0].set_ylim(bottom=0)
    axVaR[0].set_xlim(left=dfVaR.index[0], right=dfVaR.index[-1])
    axVaR[0].xaxis.set_major_locator(locator)
    axVaR[0].xaxis.set_major_formatter(formatter)
        
    axVol[0].set_ylabel('Vol 21d (%)', fontsize=13)
    axVol[0].legend(fontsize=9)
    axVol[0].set_ylim(bottom=0)
    axVol[0].yaxis.set_major_locator(ticker.FixedLocator(axVol[0].get_yticks().tolist()))
    axVol[0].set_yticklabels(['{:2.0%}'.format(j) if j!=0 else '-' for j in axVol[0].get_yticks()])
    
    axDD[0].set_ylabel('Drawdown STD (%)' if  str_fig == 'trader_dd_std' else 'Drawdown ITD (%)', fontsize=13)
    axDD[0].set_ylim(top=0)
    axDD[0].yaxis.set_major_locator(ticker.FixedLocator(axDD[0].get_yticks().tolist()))
    axDD[0].set_yticklabels(['{:2.0%}'.format(j) if j!=0 else '-' for j in axDD[0].get_yticks()], color='r')
    
    for ax in [axVaR, axVol, axDD]:
        ax[-1].set_facecolor('lightgrey')
    
    fig.align_ylabels()
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_trader_2.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    wb.sheets(sht).pictures.add(wb.api.Path + '/' + fig_file, name=str_fig, update=True)

#%%
def plot_ITD(cols, dfPnl, wb, dt, str_fund, print_pdf=False):
#%%    
    trader_limit = fu.get_RiskLimits(dt, str_fund)    
    dfPrice = (dfPnl[[c + "_adj" for c in cols]]+1).cumprod()
    vol = dfPrice.pct_change().std() * np.sqrt(252)
    # dfVol = dfPrice.pct_change().rolling(21, min_periods=5).std()*np.sqrt(252)
    dfPrice -= 1
    for c in cols:
        dfPrice['HWM_'+c] = dfPrice[c + "_adj"].expanding().max()
        dfPrice['DD_'+c] =  (1+dfPrice[c + "_adj"]) / (1+dfPrice['HWM_'+c]) -1
        dt_stop = fu.get_last_stop(dt, c, str_fund)
        dt_stop = max(dt_stop, datetime.date(dt.year-1, dt.month, dt.day))
        # dt_stop = fu.last_stops.get(c, max(datetime.date(2020,4,1), datetime.date(dt.year-1, dt.month, dt.day)))
        dt_stop = datetime.date(2020,4,1) if dt_stop > dt else dt_stop
        dfPrice['HWMLim_'+c] = dfPrice[c + "_adj"].loc[dt_stop:].expanding().max()
        dfPrice['DDLim_'+c] =  (1+dfPrice[c + "_adj"]) / (1+dfPrice['HWMLim_'+c]) -1

    locator = mdates.AutoDateLocator(minticks=3, maxticks=6)
    formatter = mdates.ConciseDateFormatter(locator, formats=['%b\n%y', '%b', '%d', '%H:%M', '%H:%M', '%S.%f'], show_offset=False)
    
    fig = plt.figure(tight_layout=True, figsize=(10, 4))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1, 2])
    gs1 = gridspec.GridSpecFromSubplotSpec(1, 2, subplot_spec=gs[1], width_ratios=[2, 1], wspace=0.02)
    plt.tight_layout()
    axTree = fig.add_subplot(gs[0])
    axRet= fig.add_subplot(gs1[0])
    axVol = fig.add_subplot(gs1[1], sharey=axRet)
    
    r = squarify.plot(sizes=[v for k, (_,_,v) in trader_limit.items() if (k != 'Fund') & (v!=0)], 
                  label=["{}\n{:2.1%}".format(k,v) for k, (_,_,v) in trader_limit.items() if (k != 'Fund') & (v!=0)],
                  color=fu.color_palette, alpha=.8, text_kwargs={'fontsize':11, 'fontweight': 'bold'},
                  edgecolor='k', lw=1,
                  ax=axTree)
    for t in r.texts:
        if 'MK' in t.get_text():
            t.set_fontsize(7)
        elif 'NF' in t.get_text():
            t.set_fontsize(8)
    axTree.axis('off')
    axTree.set_title('Share of Risk')
    texts = []
    for i, c in enumerate([f for f in trader_limit if f!='Fund']):
        axRet.plot(dfPrice[c + "_adj"], color=fu.color_palette[i], label='{} ({:5.1%})'.format(c, dfPrice[c + "_adj"].iloc[-1]))
        axVol.scatter(vol[c + "_adj"], dfPrice[c + "_adj"].iloc[-1], color=fu.color_palette[i])
        texts.append(axVol.text(vol[c + "_adj"], dfPrice[c + "_adj"].iloc[-1], c, 
                                color=fu.color_palette[i], fontweight='bold'))
    c = 'Fund'
    axRet.plot(dfPrice[c + "_adj"], color='k', lw=3, ls='--', label='{} ({:5.1%})'.format(c, dfPrice[c + "_adj"].iloc[-1]))
    axVol.scatter(vol[c + "_adj"], dfPrice[c + "_adj"].iloc[-1], color='k')
    texts.append(axVol.text(vol[c + "_adj"], dfPrice[c + "_adj"].iloc[-1], c, 
                                color='k', fontweight='bold', fontsize=13))  
    
    axRet.xaxis.set_major_locator(locator)
    axRet.xaxis.set_major_formatter(formatter)
    axRet.set_title('Risk Adjusted Accum Return')
    axRet.axhline(0, color='k', lw=0.5)
    axRet.grid(ls='--')
    axRet.legend(ncol=2)
    axRet.set_xlim(left=dfPrice.index[0])#, right=dfPrice.index[-1])
    tick_locs = axRet.get_yticks().tolist()
    axRet.yaxis.set_major_locator(ticker.FixedLocator(tick_locs))
    if abs(tick_locs[0]-tick_locs[-1]) > 0.05:
        axRet.set_yticklabels(['{:2.0%}'.format(i) for i in axRet.get_yticks()])
    else:
        axRet.set_yticklabels(['{:2.1%}'.format(i) for i in axRet.get_yticks()])
    
    axVol.set_title('Volatility')
    axVol.set_xlim(left=0)
    axVol.axhline(0, color='k', lw=0.5)
    axVol.grid(ls='--')
    axVol.xaxis.set_major_locator(ticker.MultipleLocator(0.02))
    plt.setp(axVol.get_yticklabels(), visible=False)
    axVol.xaxis.set_major_locator(ticker.FixedLocator(axVol.get_xticks().tolist()))
    axVol.set_xticklabels(['{:2.0%}'.format(i) if i!=0 else '-' for i in axVol.get_xticks()])
    adjustText.adjust_text(texts, ax=axVol) 
    
    if print_pdf:
         fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_{1}_trader_2_maptree.pdf'.format(dt, str_fund)
         fig.savefig(fig_file, bbox_inches = "tight")
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_trader_2_maptree.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    wb.sheets('Trader_2').pictures.add(wb.api.Path + '/' + fig_file, name='trader_maptree', update=True)
    #%%
    return dfPrice
    #%%

#%%
def plot_STD(std, cols, dfPnl, wb, dt, str_fund, print_pdf=False):
    #%%
    trader_limit = fu.get_RiskLimits(dt, str_fund)
    dfPrice = (dfPnl[[c + "_adj" for c in cols]]+1).cumprod().fillna(1)
    dfPrice['Fund ex-Caixa'] = (dfPnl[[c for c in cols if c != 'Fund']].sum(axis=1)+1).cumprod().fillna(1)
    dfPrice = dfPrice.loc[std:]/dfPrice.loc[std]
    vol = dfPrice.pct_change().std() * np.sqrt(252)
    dfVol = dfPrice.pct_change().rolling(21, min_periods=5).std()*np.sqrt(252)
    dfPrice -= 1
    for c in cols:
        dfPrice['HWM_'+c] = dfPrice[c + "_adj"].expanding().max() #High Water Mark
        dfPrice['DD_'+c] =  (1+dfPrice[c + "_adj"]) / (1+dfPrice['HWM_'+c]) -1 # Drawdown
        # dt_stop = fu.last_stops.get(c, datetime.date(2020,4,1))
        dt_stop = fu.get_last_stop(dt, c, str_fund)
        dt_stop = datetime.date(2020,4,1) if dt_stop > dt else dt_stop
        dfPrice['HWMLim_'+c] = dfPrice[c + "_adj"].loc[dt_stop:].expanding().max()
        dfPrice['DDLim_'+c] =  (1+dfPrice[c + "_adj"]) / (1+dfPrice['HWMLim_'+c]) -1
    
    locator = mdates.AutoDateLocator(minticks=3, maxticks=6)
    formatter = mdates.ConciseDateFormatter(locator, formats=['%b\n%Y', '%b', '%d', '%H:%M', '%H:%M', '%S.%f'], show_offset=False)
    
    fig, (axRet, axVol) = plt.subplots(1,2, figsize=(10.5, 4), sharey=True, \
                                       gridspec_kw = {'width_ratios':[5, 3]})
    plt.subplots_adjust(wspace=0.02)
    texts = []
    for i, c in enumerate([f for f in trader_limit if f!='Fund']):
        axRet.plot(dfPrice[c + "_adj"], color=fu.color_palette[i], label='{} ({:5.1%})'.format(c, dfPrice[c + "_adj"].iloc[-1]))
        axVol.scatter(vol[c + "_adj"], dfPrice[c + "_adj"].iloc[-1], color=fu.color_palette[i], marker='.')
        texts.append(axVol.text(vol[c + "_adj"], dfPrice[c + "_adj"].iloc[-1], c, fontsize=10, 
                                color=fu.color_palette[i], fontweight='bold'))
    c = 'Fund'
    axRet.plot(dfPrice[c + "_adj"], color='k', lw=3, ls='--', label='{} ({:5.1%})'.format(c, dfPrice[c + "_adj"].iloc[-1]))
    axVol.scatter(vol[c + "_adj"], dfPrice[c + "_adj"].iloc[-1], color='k', marker='.')
    texts.append(axVol.text(vol[c + "_adj"], dfPrice[c + "_adj"].iloc[-1], c, 
                                color='k', fontweight='bold', fontsize=12))  
    
    c = 'Fund ex-Caixa'
    axRet.plot(dfPrice[c], color='tomato', lw=3, ls='--', label='{} ({:5.1%})'.format(c, dfPrice[c].iloc[-1]))
    axVol.scatter(vol[c], dfPrice[c].iloc[-1], color='tomato', marker='.')
    texts.append(axVol.text(vol[c], dfPrice[c].iloc[-1], c, 
                                color='tomato', fontweight='bold', fontsize=10))  
    
    
    axRet.xaxis.set_major_locator(locator)
    axRet.xaxis.set_major_formatter(formatter)
    axRet.set_title('Risk Adjusted Accum Return')
    axRet.axhline(0, color='k', lw=0.5)
    axRet.grid(ls='--')
    axRet.grid(ls=':', which='minor')
    axRet.legend(ncol=2)
    axRet.set_xlim(left=dfPrice.index[0])#, right=dfPrice.index[-1]) 
    axRet.yaxis.set_minor_locator(ticker.MultipleLocator(0.01))
    axRet.yaxis.set_major_locator(ticker.MultipleLocator(0.02))
    axRet.yaxis.set_major_formatter(ticker.PercentFormatter(1, 0))
    
    
    axVol.set_title('Volatility')
    axVol.set_xlim(left=0)
    axVol.axhline(0, color='k', lw=0.5)
    axVol.grid(ls='--')
    axVol.grid(ls=':', which='minor')
    # axVol.yaxis.set_tick_params(labelbottom=True)
    # axVol.yaxis.tick_right()
    axVol.yaxis.set_minor_locator(ticker.MultipleLocator(0.01))
    axVol.yaxis.set_major_locator(ticker.MultipleLocator(0.02))
    axVol.yaxis.set_major_formatter(ticker.PercentFormatter(1, 0))
    axVol.xaxis.set_major_locator(ticker.MultipleLocator(0.02))
    axVol.xaxis.set_major_formatter(ticker.PercentFormatter(1, 0))

    adjustText.adjust_text(texts, ax=axVol, arrowprops=dict(arrowstyle="-", color='k', lw=0.5)) 
    
    if print_pdf:
         fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_{1}_trader_retvol_std.pdf'.format(dt, str_fund)
         fig.savefig(fig_file, bbox_inches = "tight")
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_trader_retvol_std.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    wb.sheets('Trader_STD').pictures.add(wb.api.Path + '/' + fig_file, name='trader_retvol_std', update=True)
    # wb.sheets('Trader_STD').pictures.add(fig, name='trader_retvol_std', update=True)
#%%
    return dfPrice
    #%%
    
#%%
if __name__ == "__main__":

    tic = timeit.default_timer()
    
    dt, str_fund, print_pdf = fu.get_config(['dt', 'str_fund', 'print_pdf'])
    report_filename = '../xls/RiskMap_model.xlsm'
    
    main(dt, str_fund, report_filename, print_pdf) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))
 
