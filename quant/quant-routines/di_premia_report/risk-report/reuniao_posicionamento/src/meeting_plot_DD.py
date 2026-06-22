import numpy as np
import datetime

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker


from scipy.stats import norm

import sys
sys.path.insert(1, '../../risk_report/src')
import fund_utils as fu
import fund_data



def main(data, figsize=(13, 6)):
    #%%
    dfPrice = data.get_adjusted_trader_pnl()
    traders = fu.get_traders(data._dt)
    
    for c in traders.keys():
        dfPrice[c + '_PnL_Acum'] =  (1+dfPrice[c]).cumprod()
        dfPrice['HWM_'+c] = dfPrice[c + '_PnL_Acum'].expanding().max()
        dfPrice['DD_'+c] =  dfPrice[c + '_PnL_Acum'] / dfPrice['HWM_'+c] - 1
        # dt_stop = fu.last_stops.get(c, datetime.date(2020,4,1))
        dt_stop = fu.get_last_stop(data._dt, c)
        dt_stop = max(dt_stop, datetime.date(data._dt.year-1, data._dt.month, data._dt.day))
        # dt_stop = datetime.date(2020,4,1) if dt_stop >= data._dt else dt_stop
        dfPrice['HWMLim_'+c] = dfPrice[c + '_PnL_Acum'].loc[dt_stop:].expanding().max()
        dfPrice['DDLim_'+c] =   dfPrice[c + '_PnL_Acum'] / dfPrice['HWMLim_'+c] - 1  
    
    dfPrice = dfPrice.loc[data._std:]
    dfVaR = data.get_adjusted_trader_var()
    
  #%%
    
    color1, color2 = fu.color_palette[0:2]
    fig, axes = plt.subplots(1, len(traders.keys()), 
                             sharex=True, 
                             sharey='row',
                             figsize=figsize)
    fig.tight_layout(h_pad=0, w_pad=0)
    for i, (ax, t) in enumerate(zip(axes.flatten(), traders.keys())):
        ax.set_title(t, fontweight='bold')
        ax.plot(dfPrice.index, dfPrice['DDLim_'+t], lw=2, c='r')
        ax.fill_between(dfPrice.index, 0,  dfPrice['DDLim_'+t],  color='tomato', alpha=0.5)
        
        dd_t = dfPrice.loc[data._dt,'DDLim_' + t]
        
        for dd in [0.93, 0.90]:
            stop_ret = dd/(1+dd_t)-1
            vol21d = -1 * dfVaR.loc[data._dt, t]/1.645 * np.sqrt(21)
            prob_stop = 0 if vol21d == 0 else 2*norm.cdf(stop_ret, loc=0, scale=vol21d) if stop_ret < 0 else 1
            ax.text(dfPrice.index[0], dd-1, ' P={:3.0%}'.format(prob_stop), 
                          va='bottom', fontweight='bold', fontsize=9, zorder=6)
            ax.axhline(dd-1, ls='--', c='r')
        
        
        # ax.set_xlim(left=dfPlot.index[0], right=dfPlot.index[-1])
        
        # var = dfPlot[t + '_var'].iloc[-1]
        ax.annotate('{:2.1%}'.format(dd_t), xy=(dfPrice.index[-1], dd_t), xycoords='data',
                      xytext=(0.4, 0.68), textcoords='axes fraction', fontweight='bold',
                      fontsize=12, color=color1,
                      arrowprops=dict(facecolor=color2, arrowstyle="->", connectionstyle="arc3"))
       

    locator = mdates.AutoDateLocator(minticks=2, maxticks=4)
    formatter = mdates.ConciseDateFormatter(locator, formats=['%b\n%y', '%b', '%d', '%H:%M', '%H:%M', '%S.%f'], show_offset=False)  
    ax.xaxis.set_minor_locator(mdates.MonthLocator(interval=1))
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    
    axes[0].yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1, decimals=1))
    axes[0].set_xlim(left=data._std, right=data._dt)

    axes[-1].set_facecolor('silver')
    # axes[0,-1].axhline(180, c='r', lw=2)
    # axes[1,-1].set_facecolor('silver')
    # axes[1,-1].axhline(0.06, c='r', lw=2, ls=':')
    # axes[1,-1].axhline(0.08, c='r', lw=2, ls=':')
    # axes[1,-1].fill_between(dfPlot.index, 0.06, 0.08, color='tomato',
    #                       alpha=0.3, label='vol trgt') 
    
    
    for ax in axes.flatten():
        ax.grid(ls='--')
        ax.grid(ls=':', which='minor', axis='x')
        ax.set_ylim(top=0)
    fig.align_ylabels()
    plt.show()
    #%%
    return fig

#%%
if __name__ == "__main__":

    dt , str_fund = fu.get_config(['dt', 'str_fund'])
    nav = fu.get_NAV(dt, str_fund)
    
    str_path = "../output/temp_figs/"
   
    data = fund_data.db_data(dt, str_fund, verbose=True)
    
    f = main(data, figsize=(13, 6))
    fig_file = f"../tex/{dt:%Y_%m_%d}/figuras/{dt:%Y%m%d}_dd_PM.pdf"
    f.savefig(fig_file, bbox_inches = 'tight', pad_inches = 0)
