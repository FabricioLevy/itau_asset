import pandas as pd
import numpy as np
import datetime

import xlwings as xw
import QuantLib as ql
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import matplotlib.gridspec as gridspec
import adjustText

import sys
sys.path.insert(1, '../../risk_report/src')
import fund_utils as fu
import fund_data



#%%#################
def plot_x(data, str_key='Fund', figsize=(14, 6)):
#%%
    dfPnL = data._dic_pnl['Traders']
    dfPnL = dfPnL.join(data._dfAcumCDI.pct_change())
    
    dfPnL['day'] = dfPnL.index.map(lambda x: x.day)
    dfPnL['month_year'] = dfPnL.index.map(lambda x: datetime.date(x.year, x.month, 1))
    dfPnL['bus_day'] = dfPnL.index.map(lambda x: ql.Brazil().businessDaysBetween(ql.Date(1, x.month, x.year),
                                                                                 ql.Date.from_date(x))+1)
    
    dfPnL = dfPnL.loc[datetime.date(dfPnL.index[-1].year,1,1):]
    
    col_pivot = 'bus_day'
    dfPlotFund = dfPnL.pivot(index='month_year', columns=col_pivot, values=str_key) 
    dfPlotCDI = dfPnL.pivot(index='month_year', columns=col_pivot, values='CDI') 
    dfPlotDay = dfPnL.pivot(index='month_year', columns=col_pivot, values='day')
    #%%
    cmap = mpl.cm.get_cmap('bwr', 19).reversed()
    norm = mpl.colors.TwoSlopeNorm(vmin=-100, vcenter=0., vmax=100)

    fig, axes = plt.subplots(len(dfPlotFund.index),
                             len(dfPlotFund.columns),
                             figsize=figsize,
                             squeeze=False,
                             sharex=True, sharey=True)
     
    fig.tight_layout(w_pad=0, h_pad=0)
    fig.subplots_adjust(wspace=0.05, hspace=0.05)
    # for j, d in enumerate(dfPlotFund.columns):
    #     ax = axes[0,j] 
    #     ax.set_title(f"{d}", fontsize=11,fontweight='bold')
    dic_count = {}
    for i in ['neg', 'cdi-', 'cdi+']:
        dic_count[i] = 0
        
    for i,m in enumerate(dfPlotFund.index):
        ax = axes[i,0] 
        ax.set_ylabel(f"{m:%b-%y}", fontsize=11,fontweight='bold', rotation=0, ha='right')
        for j,d in enumerate(dfPlotFund.columns):
            ret_fund = dfPlotFund.loc[m, d] * 10_000
            ret_cdi = dfPlotCDI.loc[m, d] * 10_000
            day = dfPlotDay.loc[m, d] 
            ax = axes[i,j] 
            ax.set_xticks([])
            ax.set_yticks([])
            if pd.isna(ret_fund):
                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)
                ax.spines["left"].set_visible(False)
                ax.spines["bottom"].set_visible(False)
            else:
                ax.annotate(f"{day:1.0f}",xy=(0.05, 0.95), xycoords="axes fraction", 
                            va='top', ha='left', fontsize=8)
                ax.annotate(f"{ret_fund:4.2f}",xy=(0.5, 0.6), xycoords="axes fraction",
                        va='center',ha='center', fontweight='bold',fontsize=10,
                        color='k' if ret_fund>=0 else'r' )
                ax.annotate(f"{ret_cdi:4.1f}",xy=(0.5, 0.25), xycoords="axes fraction", 
                            va='center',ha='center')
                if ret_fund<0:
                    facecolor = 'lightsalmon' 
                    dic_count['neg'] += 1
                elif ret_fund<ret_cdi:
                    facecolor = 'silver' 
                    dic_count['cdi-'] += 1                    
                else:
                    facecolor = 'lightblue' 
                    dic_count['cdi+'] += 1 
                ax.set_facecolor(facecolor)
                # ax.set_facecolor(cmap(norm(ret_fund)))     
    plt.show()
    #%%
    fig2, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(4, 1.5),
                             sharex=True, sharey=True)
     
    fig2.tight_layout(w_pad=0, h_pad=0)
    fig2.subplots_adjust(wspace=0.05, hspace=0.05)
    
    ax1.annotate(f"{dic_count['neg']:1.0f} dias\nnegativos\n({dic_count['neg']/len(dfPnL):2.0%})",
                 xy=(0.5, 0.5), xycoords="axes fraction",
                va='center',ha='center', fontweight='bold',fontsize=12,
                color='r')
    ax1.set_facecolor('lightsalmon')
    
    ax2.annotate(f"{dic_count['cdi-']:1.0f} dias\nabaixo\ndo CDI\n({dic_count['cdi-']/len(dfPnL):2.0%})",
                 xy=(0.5, 0.5), xycoords="axes fraction",
                va='center',ha='center', fontweight='bold',fontsize=12,
                color='k')
    ax2.set_facecolor('silver')
    
    ax3.annotate(f"{dic_count['cdi+']:1.0f} dias\nacima\ndo CDI\n({dic_count['cdi+']/len(dfPnL):2.0%})",
                 xy=(0.5, 0.5), xycoords="axes fraction",
                va='center',ha='center', fontweight='bold',fontsize=12,
                color='k')
    ax3.set_facecolor('lightblue')
    
    for ax in [ax1, ax2, ax3]:
        ax.set_xticks([])
        ax.set_yticks([])
    plt.show()
    
    
    #%%
    return fig


#%%#################


#%%
if __name__ == "__main__":

    dt = datetime.date(2022, 9, 30)
    str_fund = 'A1 Master FIM'
    nav = fu.get_NAV(dt, str_fund)
    
    str_path = "../output/temp_figs/"
   
    data = fund_data.db_data(dt, str_fund, verbose=True)
    #%%
    f = plot_x(data)
    # fig_file = f"../tex/{dt:%Y_%m_%d}/figuras/{dt:%Y%m%d}_trader_var_vol.pdf"
    # f.savefig(fig_file, bbox_inches = 'tight', pad_inches = 0)
    
