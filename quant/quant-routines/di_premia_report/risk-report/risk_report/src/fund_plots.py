import pandas as pd
import numpy as np
import math
import datetime

import timeit
import xlwings as xw
import QuantLib as ql
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import matplotlib.gridspec as gridspec
import adjustText
import fund_data
import fund_utils as fu
import squarify # pip install squarify (algorithm for treemap)

#######################################################
def plot_piechart_riskshare(data, trader):
    #%%
    limit_data = data._risk_limits
    color1, color2 = fu.color_palette[0:2]
    fig, ax = plt.subplots(1,1)
    fig.tight_layout(pad=0)
    labels = [f"{k}\n{i[2]:2.1%}" if k==trader else '' for k, i in limit_data.items() if k!= 'Fund']
    sizes = [i[2] for k, i in limit_data.items() if k!= 'Fund']
    explode = [0.1 if k==trader else 0 for k, i in limit_data.items() if k!= 'Fund']
    colors = [color2 if k==trader else 'silver' for k, i in limit_data.items() if k!= 'Fund']

    ax.pie(sizes, explode=explode, labels=labels, 
           labeldistance=0.55,
           wedgeprops = { 'linewidth' : 2, 'edgecolor' : 'w' },
           textprops = {'fontweight':'bold', 'fontsize':14, 'ha':'center'},
        shadow=False, startangle=90, colors=colors)
    ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
    ax.margins(0,0)
    plt.show()
    #%%
    return fig

#######################################################
def plot_performance_dd(data, trader):
    #%%
    pnl_data = data.get_adjusted_trader_pnl()

    dfPlot = pd.DataFrame(index=pnl_data.index, columns=['AcumPerf', 'HWM', 'DD'])
    dfPlot['AcumPerf'] = (1+pnl_data[trader]).cumprod()-1
    dfPlot = dfPlot.dropna(how='all')
    dfPlot['HWM'] = dfPlot['AcumPerf'].expanding().max()
    dfPlot['DD'] = (1+dfPlot['AcumPerf'])/(1+dfPlot['HWM'])-1
    
    std = max(data._std, dfPlot['AcumPerf'].first_valid_index())
    dfPlot_STD = pd.DataFrame(columns=['AcumPerf', 'HWM', 'DD'])
    dfPlot_STD['AcumPerf'] = (1+dfPlot.loc[std:,'AcumPerf'])/(1+dfPlot.loc[std,'AcumPerf'])-1
    dfPlot_STD['HWM'] = dfPlot_STD['AcumPerf'].expanding().max()
    dfPlot_STD['DD'] = (1+dfPlot_STD['AcumPerf'])/(1+dfPlot_STD['HWM'])-1
    
    color1, color2 = fu.color_palette[0:2]
    fig, axes = plt.subplots(2, 2, sharex='col', 
                             gridspec_kw={'width_ratios':[3,2], 
                                          'height_ratios':[3,2]})
    fig.tight_layout(h_pad=0, w_pad=5)
    
    axP, axD = axes[:,0]
    axP.set_title('ITD')
    axP.set_ylabel('Accum. Performance')
    axD.set_ylabel('Drawdown')
    axP.plot(dfPlot.index, dfPlot['AcumPerf'], lw=2, c=color1)
    axP.plot(dfPlot.index, dfPlot['HWM'], lw=3, c=color2, alpha=0.3)
    itd_val = dfPlot['AcumPerf'].iloc[-1]
    axP.text(dfPlot.index[-1], itd_val, f" {itd_val:2.1%}", ha='left', va='center',
             fontweight='bold', c=color1)
    axD.plot(dfPlot.index, dfPlot['DD'], color='r')
    dd_val = dfPlot['DD'].iloc[-1]
    axD.text(dfPlot.index[-1], dd_val, f" {dd_val:2.1%}", ha='left', va='center',
             fontweight='bold', c='r')
    axD.fill_between(dfPlot.index, 0, dfPlot['DD'], color='r', alpha=0.5)
    axD.set_ylim(top=0)
    axD.set_xlim(left=dfPlot.index[0], right=dfPlot.index[-1])
    locator = mdates.AutoDateLocator(minticks=2, maxticks=6)
    formatter = mdates.ConciseDateFormatter(locator, formats=['%b\n%Y', '%b', '%d', '%H:%M', '%H:%M', '%S.%f'], show_offset=False)  
    axD.xaxis.set_minor_locator(mdates.MonthLocator(interval=1))
    axD.xaxis.set_major_locator(locator)
    axD.xaxis.set_major_formatter(formatter)
    
    axP, axD = axes[:,1]
    axP.set_title('STD')
    axP.plot(dfPlot_STD.index, dfPlot_STD['AcumPerf'], lw=2, c=color1)
    axP.plot(dfPlot_STD.index, dfPlot_STD['HWM'], lw=3, c=color2, alpha=0.3)    
    axP.set_xlim(left=std, right=dfPlot.index[-1])
    std_val = dfPlot_STD['AcumPerf'].iloc[-1]
    axP.text(dfPlot_STD.index[-1], std_val, f" {std_val:2.1%}", ha='left', va='center',
             fontweight='bold', c=color1)
    axP.xaxis.set_minor_locator(mdates.MonthLocator(interval=1))    
    axD.plot(dfPlot_STD.index, dfPlot_STD['DD'], color='r')
    dd_val = dfPlot_STD['DD'].iloc[-1]
    axD.text(dfPlot_STD.index[-1], dd_val, f" {dd_val:2.1%}", ha='left', va='center',
             fontweight='bold', c='r')
    axD.fill_between(dfPlot_STD.index, 0, dfPlot_STD['DD'], color='r', alpha=0.5)
    axD.set_ylim(top=0)
    locator = mdates.AutoDateLocator(minticks=2, maxticks=6)
    formatter = mdates.ConciseDateFormatter(locator, formats=['%b\n%Y', '%b', '%d', '', '%H:%M', '%S.%f'], show_offset=False)  
    axD.xaxis.set_major_locator(locator)
    axD.xaxis.set_major_formatter(formatter)
    
    for ax in axes.flatten():
        ax.grid(ls='--')
        ax.grid(ls=':', which='minor', axis='x')
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1, decimals=1))
    fig.align_ylabels(axes[:, 0])
    plt.show()
    #%%
    return fig

#######################################################
def plot_hist_var_vol(data, trader, figsize=(4,4)):
    #%%
    pnl_data = data.get_adjusted_trader_pnl()
    var_data = data.get_adjusted_trader_var()
    dfPlot = pd.DataFrame(columns=['VaR', 'Vol'])
    dfPlot['VaR'] = -10_000 * var_data[trader]
    dfPlot['Vol'] = pnl_data[trader].rolling(21, min_periods=3).std() * (252**(1/2))
    dfPlot = dfPlot.dropna(how='all').fillna(0)
    
    color1, color2 = fu.color_palette[0:2]
    fig, (axVar, axVol) = plt.subplots(2, 1, sharex=True, figsize=figsize)
    fig.tight_layout(h_pad=0)
    axVar.plot(dfPlot.index, dfPlot['VaR'], lw=2, c=color1)
    axVar.set_xlim(left=dfPlot.index[0], right=dfPlot.index[-1])
    axVar.axhline(180, c='r', ls='--', label='Limit (180bps)')
    axVar.set_ylabel('VaR (BPs)')
    var = dfPlot['VaR'].iloc[-1]
    axVar.text(dfPlot.index[-1], var, f" {var:2.1f}", ha='left', va='center',
             fontweight='bold', c=color1)
    
    axVol.plot(dfPlot.index, dfPlot['Vol'], lw=2, c=color2)
    axVol.set_ylabel('Vol 21d (%aa)')
    vol = dfPlot['Vol'].iloc[-1]
    axVol.text(dfPlot.index[-1], vol, f" {vol:2.1%}", ha='left', va='center',
             fontweight='bold', c=color2)
    locator = mdates.AutoDateLocator(minticks=2, maxticks=6)
    formatter = mdates.ConciseDateFormatter(locator, formats=['%b\n%Y', '%b', '%d', '%H:%M', '%H:%M', '%S.%f'], show_offset=False)  
    axVol.xaxis.set_minor_locator(mdates.MonthLocator(interval=1))
    axVol.xaxis.set_major_locator(locator)
    axVol.xaxis.set_major_formatter(formatter)
    axVol.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1, decimals=1))
    
    for ax in [axVar, axVol]:
        ax.grid(ls='--')
        ax.grid(ls=':', which='minor', axis='x')
        ax.set_ylim(bottom=0)
    fig.align_ylabels()
    plt.show()
    #%%
    return fig

#%%#######################################################
def plot_month_pnl(data, trader, show_cdi=False):
    dfMonthRet = data._dic_pnl_month['Traders_Adj'][[trader]].copy()
    dfMonthRet['dt'] = dfMonthRet.index
    dfMonthRet['year'] = dfMonthRet['dt'].apply(lambda x:x.year)
    dfMonthRet['month'] = dfMonthRet['dt'].apply(lambda x:x.month)   
    dic_date = {(m, y):dt for (_,dt,y,m) in dfMonthRet.values}
    dfRet = dfMonthRet.pivot(index='year', 
                             columns='month', 
                             values=trader)
 
    cmap = mpl.cm.get_cmap('bwr', 15).reversed()
    norm = mpl.colors.TwoSlopeNorm(vmin=-0.06, 
                                   vcenter=0., 
                                   vmax=0.06)
    
    fig, axes = plt.subplots(len(dfRet.index), 
                             len(dfRet.columns), 
                             figsize=(10, len(dfRet.index)*0.8),
                             sharex=True, 
                             sharey=True)  
    fig.tight_layout(w_pad=0, 
                     h_pad=0)
    fig.subplots_adjust(wspace=0.05, 
                        hspace=0.05)
    for j,m in enumerate(dfRet.columns):
        ax = axes[0,j] if len(dfRet.index) >1 else axes[j]
        ax.set_title(f"{datetime.date(2000,m,1):%b}", 
                     fontsize=14,
                     fontweight='bold')
    for i,y in enumerate(dfRet.index):
        ax = axes[i,0] if len(dfRet.index)>1 else axes[i]
        ax.set_ylabel(y, 
                      fontsize=14,
                      fontweight='bold')
        for j,m in enumerate(dfRet.columns):
            ret_fund = dfRet.loc[y,m]
            ax = axes[i,j] if len(dfRet.index)>1 else axes[j]
            ax.set_xticks([])
            ax.set_yticks([])
            if pd.isna(ret_fund):
                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)
                ax.spines["left"].set_visible(False)
                ax.spines["bottom"].set_visible(False)
            else:
                ax.annotate(f"{ret_fund:6.2%}",
                            xy=(0.5, 0.5), 
                            xycoords="axes fraction",
                            va='center',
                            ha='center', 
                            fontweight='bold',
                            fontsize=12,
                            color='k')# if ret_fund>=0 else'r' )
                ax.set_facecolor(cmap(norm(ret_fund)))   
                if show_cdi:
                    ret_cdi = data._dic_pnl_month['CDI'].loc[dic_date[(m, y)], 'CDI']
                    ax.annotate(f"{ret_cdi:6.2%}",
                            xy=(0.5, 0.15), 
                            xycoords="axes fraction",
                            va='center',
                            ha='center', 
                            fontweight='normal',
                            fontsize=9,
                            color='k' )
                    
    plt.show()
    return fig

#%%####
def plot_hist_month_pnl(data, trader, figsize=(8,3)):
    dfMonthRet = data._dic_pnl_month['Traders_Adj'][[trader]].dropna().copy()
    x = math.ceil(abs(dfMonthRet).max().loc[trader]*100)/100
    bins=np.linspace(-x, x, 21)
    l=[]
    for a, b in zip(bins, bins[1:]):
        l.append((a+b)/2)
    dfMonthRet['hist'] = pd.cut(dfMonthRet[trader], 
                                bins, 
                                labels=l)
    dfHist=dfMonthRet.groupby(['hist']).count().reset_index()
    dfHist['abs_hist'] = dfHist['hist'].apply(lambda x: abs(round(x,4)))
    dfHist['qty_pos'] = dfHist[[trader, 'hist']].apply(lambda x: x[trader] * (1 if x['hist']>=0 else 0), axis=1)
    dfHist['qty_neg'] = dfHist[[trader, 'hist']].apply(lambda x: x[trader] * (-1 if x['hist']<0 else 0), axis=1)
    dfPlot  = dfHist[['abs_hist', 'qty_pos', 'qty_neg']].groupby(['abs_hist']).sum()

    fig, ax = plt.subplots(1,1, figsize=figsize)
    dfPlot['qty_pos'].plot.barh(ax=ax,  
                                color=fu.color_palette[1],
                                zorder=3, 
                                label='{:2.0f} Meses Positivos'.format(dfPlot['qty_pos'].sum()))
    dfPlot['qty_neg'].plot.barh(ax=ax, 
                                color='tomato', 
                                zorder=3, 
                                label='{:2.0f} Meses Negativos'.format(-dfPlot['qty_neg'].sum()))
    ax.axvline(0, c='k', lw=0.75)
    ax.grid(ls='--', zorder=0)
    ax.set_xlabel('Frequência', 
                  fontweight='bold')
    ax.set_ylabel('Retorno Mensal', 
                  fontweight='bold')
    ax.set_yticklabels(['{:2.1f}~{:2.1%}'.format(a*100, b) for (a,b) in zip(bins, bins[1:]) if a>=0])
    max_qty = dfPlot.abs().max().max()
    ax.set_xticks(np.arange(-max_qty, max_qty+1, 1))
    ax.set_xticklabels(['{:1.0f}'.format(abs(i)) for i in ax.get_xticks()])
    ax.legend(loc='upper center', 
              fontsize=9,
              bbox_to_anchor=(0.5, 1.18), 
              fancybox=True, 
              shadow=True)
    plt.show()        
    return fig

#%%#################




#%%
if __name__ == "__main__":

    dt = datetime.date(2022, 8, 15)
    str_fund = 'A1 Master FIM'
    nav = fu.get_NAV(dt, str_fund)
    
    str_path = "../output/temp_figs/"
   
    my_db = fund_data.db_data(dt, str_fund, verbose=True)
    #%%
    
    fig_names = ['piechart', 'trader_hist_var_vol']
    figsizes = [(4, 4), (10, 4)]
    
    
    dic_figs = {}
    for trader, t_name in fu.get_traders(dt).items():
        fig_name = 'piechart'
        fig = plot_piechart_riskshare(my_db, trader)
        fig.set_size_inches(5, 5)
        fig_file = f"{str_path}/{dt:%Y%m%d}_{trader}_{fig_name}.pdf" 
        fig.savefig(fig_file,
                    bbox_inches = 'tight', #facecolor='silver',
                    pad_inches = -0.4)
        
        fig_name = 'hist_var_vol'
        fig = plot_hist_var_vol(my_db, trader)
        fig.set_size_inches(9, 5)
        fig_file = f"{str_path}/{dt:%Y%m%d}_{trader}_{fig_name}.pdf" 
        fig.savefig(fig_file,
                    bbox_inches = 'tight', #facecolor='silver',
                    pad_inches = 0)
        
        fig_name = 'perf_dd'
        fig = plot_performance_dd(my_db, trader)
        fig.set_size_inches(6, 4.85)
        fig_file = f"{str_path}/{dt:%Y%m%d}_{trader}_{fig_name}.pdf" 
        fig.savefig(fig_file,
                    bbox_inches = 'tight',# facecolor='silver',
                    pad_inches = 0)
        
        fig_name = 'month_ret'
        fig = plot_month_pnl(my_db, trader)
        fig.set_figwidth(12)
        h = fig.get_figheight()
        fig.set_figheight(min (h, 6))
        # fig.set_size_inches(12, 6)
        fig_file = f"{str_path}/{dt:%Y%m%d}_{trader}_{fig_name}.pdf" 
        fig.savefig(fig_file,
                    bbox_inches = 'tight',# facecolor='silver',
                    pad_inches = 0)
        
        fig_name = 'perf_histogram'
        fig = plot_hist_month_pnl(my_db, trader)
        fig.set_size_inches(5, 5.75)
        fig_file = f"{str_path}/{dt:%Y%m%d}_{trader}_{fig_name}.pdf" 
        fig.savefig(fig_file,
                    bbox_inches = 'tight', #facecolor='silver',
                    pad_inches = 0)
        
        # dic_figs['pie_riskshare'] = fig
    #     dic_figs['trader_perf_dd'] = plot_performance_dd(my_db, trader, figsize=(8,4))
    #     dic_figs['trader_hist_var_vol'] = plot_hist_var_vol(my_db, trader, figsize=(9,4))
    #     dic_figs['trader_month_ret'] = plot_month_pnl(my_db, trader, show_cdi=True)
    #     dic_figs['trader_perf_histogram'] = plot_hist_month_pnl(my_db, trader, figsize=(3,4))
    
    
    
    
  #%%  
    # report_filename='../xls/trader_RiskReport.xlsm'
    # wb = xw.Book(report_filename)
    # sheet_name = 'Cover'
    # wb.sheets(sheet_name).range('NAV').value = nav
    # wb.sheets(sheet_name).range('DataRef').value = dt
    # wb.sheets(sheet_name).range('DataD1').value = ql.Brazil().advance(ql.Date.from_date(dt), ql.Period('-1d')).to_date()
    # wb.sheets(sheet_name).range('fund').value = str_fund
    
    # sheet_name = '_model_'
    # sheet_model = wb.sheets[sheet_name]
    
    # for trader, t_name in zip(fu.traders, fu.trader_names):
    #     sheet_model.copy(after=wb.sheets[sheet_name], name=trader)   
    #     sheet_name = trader
    #     wb.sheets(trader).range('trader_name').value = t_name
    #     dic_figs = {}
    #     dic_figs['pie_riskshare'] = plot_piechart_riskshare(my_db, trader)
    #     dic_figs['trader_perf_dd'] = plot_performance_dd(my_db, trader, figsize=(8,4))
    #     dic_figs['trader_hist_var_vol'] = plot_hist_var_vol(my_db, trader, figsize=(9,4))
    #     dic_figs['trader_month_ret'] = plot_month_pnl(my_db, trader, show_cdi=True)
    #     dic_figs['trader_perf_histogram'] = plot_hist_month_pnl(my_db, trader, figsize=(3,4))
    #     for i, (n, f) in enumerate(dic_figs.items(), 1):
    #         fig_file = f"{str_path}/{trader}_{i}.svg" 
    #         f.savefig(fig_file, 
    #                   bbox_inches = 'tight', 
    #                   pad_inches = 0)

    #         wb.sheets(trader).pictures.add(wb.api.Path + '/' + fig_file, 
    #                                   name=n, 
    #                                   update=True)
#%%

#     str_tree = 'Traders'
#     my_db._dfPnL[str_tree] = my_db._dfPnL['book'].apply(lambda x: my_db._dic_books[str_tree][x] + ('_CC' if my_db._dic_books['Risk'][x]=='CUPOM CAMBIAL' else ''))
#     my_db._dic_pnl[str_tree] = my_db._dfPnL.pivot_table(index='date_reference', 
#                                                        columns=str_tree, 
#                                                        values='PnL_Perc', 
#                                                        aggfunc=np.sum).sort_index()
#     my_db._dic_pnl[str_tree]['Fund'] = my_db._dic_pnl[str_tree].fillna(0).sum(axis=1)
#     my_db.x()
# #%%
#     for trader, t_name in zip(['MS', 'GB'],['Marcello Siniscalchi', 'Gabriel Blum']):
#         sheet_model.copy(after=wb.sheets[sheet_name], name=trader)   
#         sheet_name = trader
#         wb.sheets(trader).range('trader_name').value = t_name
#         dic_figs = {}
#         dic_figs['pie_riskshare'] = plot_piechart_riskshare(my_db, trader)
#         dic_figs['trader_perf_dd'] = plot_performance_dd(my_db, trader, figsize=(8,4))
#         dic_figs['trader_hist_var_vol'] = plot_hist_var_vol(my_db, trader, figsize=(9,4))
#         dic_figs['trader_month_ret'] = plot_month_pnl(my_db, trader)
#         dic_figs['trader_perf_histogram'] = plot_hist_month_pnl(my_db, trader, figsize=(3,4))
#         for i, (n, f) in enumerate(dic_figs.items(), 1):
#             fig_file = f"{str_path}/{trader}_{i}.svg" 
#             f.savefig(fig_file, 
#                       bbox_inches = 'tight', 
#                       pad_inches = 0)

#             wb.sheets(trader).pictures.add(wb.api.Path + '/' + fig_file, 
#                                       name=n, 
#                                       update=True)