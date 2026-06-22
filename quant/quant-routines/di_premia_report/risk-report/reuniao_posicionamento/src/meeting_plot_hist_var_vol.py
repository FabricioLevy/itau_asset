import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker

import sys
sys.path.insert(1, '../../risk_report/src')
import fund_utils as fu
import fund_data


def main(data, figsize=(12, 6)):
    #%%
    dfTemp = data._risk_share.iloc[-1].sort_values(ascending=False).drop('Fund')
    traders = list(dfTemp[dfTemp!=0].index)
    
    pnl_data = data.get_adjusted_trader_pnl()
    var_data = data.get_adjusted_trader_var() * -10_000
    
    sorted_cols = traders + ['Fund']
        
    vol_data = pnl_data.rolling(21, min_periods=3).std() * (252**(1/2))
    
    dfPlot = var_data.iloc[-126:]
    dfPlot = dfPlot.join(vol_data, lsuffix='_var', rsuffix='_vol')
    
    color1, color2 = fu.color_palette[0:2]
    fig, axes = plt.subplots(2, len(sorted_cols), 
                             sharex=True, 
                             sharey='row',
                             figsize=figsize)
    fig.tight_layout(h_pad=0, w_pad=0)
    
    for i, t in enumerate(sorted_cols):
        ax = axes[0,i]  
        ax.set_title(t, fontweight='bold')
        ax.plot(dfPlot.index, dfPlot[t + '_var'], lw=2, c=color2)
        ax.set_xlim(left=dfPlot.index[0], right=dfPlot.index[-1])
        
        var = dfPlot[t + '_var'].iloc[-1]
        ax.annotate('{:2.1f}'.format(var), xy=(dfPlot.index[-1], var), xycoords='data',
                      xytext=(0.4, 0.68), textcoords='axes fraction', fontweight='bold',
                      fontsize=12, color=color1,
                      arrowprops=dict(facecolor=color2, arrowstyle="->", connectionstyle="arc3"))
        
        ax = axes[1,i]  
        ax.plot(dfPlot.index, dfPlot[t + '_vol'], lw=2, c=color2)
        ax.set_xlim(left=dfPlot.index[0], right=dfPlot.index[-1])
        
        vol = dfPlot[t + '_vol'].iloc[-1]
        ax.annotate('{:2.1%}'.format(vol), xy=(dfPlot.index[-1], vol), xycoords='data',
                      xytext=(0.4, 0.68), textcoords='axes fraction', fontweight='bold',
                      fontsize=12, color=color1,
                      arrowprops=dict(facecolor=color2, arrowstyle="->", connectionstyle="arc3"))
        

    locator = mdates.AutoDateLocator(minticks=2, maxticks=4)
    formatter = mdates.ConciseDateFormatter(locator, formats=['%b\n%y', '%b', '%d', '%H:%M', '%H:%M', '%S.%f'], show_offset=False)  
    ax.xaxis.set_minor_locator(mdates.MonthLocator(interval=1))
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    
    axes[1,0].yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1, decimals=1))
    axes[0,0].set_ylabel('VaR (BPs)')
    axes[1,0].set_ylabel('Vol 21d(%)')
    
    axes[0,-1].set_facecolor('silver')
    axes[0,-1].axhline(180, c='r', lw=2)
    axes[1,-1].set_facecolor('silver')
    axes[1,-1].axhline(0.06, c='r', lw=2, ls=':')
    axes[1,-1].axhline(0.08, c='r', lw=2, ls=':')
    axes[1,-1].fill_between(dfPlot.index, 0.06, 0.08, color='tomato',
                          alpha=0.3, label='vol trgt') 
    
    
    for ax in axes.flatten():
        ax.grid(ls='--')
        ax.grid(ls=':', which='minor', axis='x')
        ax.set_ylim(bottom=0)
    fig.align_ylabels()
    plt.show()
    #%%
    return fig

#%%#################

#%%
if __name__ == "__main__":

    dt, str_fund = fu.get_config(['dt', 'str_fund'])
    nav = fu.get_NAV(dt, str_fund)
    nav = fu.get_NAV(dt, str_fund)
    
    str_path = "../output/temp_figs/"
   
    data = fund_data.db_data(dt, str_fund, verbose=True)
    
    f = main(data)
    fig_file = f"../tex/{dt:%Y_%m_%d}/figuras/{dt:%Y%m%d}_trader_var_vol.pdf"
    # f.savefig(fig_file, bbox_inches = 'tight', pad_inches = 0)
    
   
