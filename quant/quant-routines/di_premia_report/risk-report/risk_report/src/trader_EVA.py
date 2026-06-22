import datetime
import pandas as pd
import numpy as np

import scipy.stats as stats

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from adjustText import adjust_text

import fund_utils as fu
import fund_data

import extreme_value_analysis as eva


#%%%
def main(data, nav):
    #%%
    colors = fu.color_palette
    dfHypoPnL = data._dic_hypoPnL['Traders']
    traders = list(fu.get_traders(data._dt).keys())
    traders = [t for t in traders if t in dfHypoPnL.columns]
    
    dic_figs = {}
    for t in traders:
        risk_share = data._risk_share.loc[data._dt, t]
        var_p, _ = data.calculate_var(data.get_TraderVaRWeights_byCol(t).sum(axis=1))/ risk_share / nav
        var_h = data.calculate_hyb_var('Traders', t)/ risk_share / nav
        
        evt_pot = eva.PeakOverThreshold(dfHypoPnL[t] / risk_share / nav)
        evt_pot.fit()
        dfRet = evt_pot.to_dataframe()
               
        fig, axes = plt.subplots(2, 3, 
                                 figsize=(12, 6), 
                                 constrained_layout=True)
        gs = axes[0, 0].get_gridspec()
        axes[0, 0].remove()
        axes[1, 0].remove()
        ax = fig.add_subplot(gs[0:, 0])
        
        ax.set_title(f"Hypo PnL - since {dfRet.index[0]:%b%Y}")
        dfRet['Losses'].plot(ax=ax, kind='area', color=colors[0], alpha=0.7)
        ax.scatter(dfRet['Exceedances'].index, dfRet['Exceedances'], label='Exceedances', 
                    marker='o', alpha=0.9, color=colors[1])
        
        ax.axhline(evt_pot._u, c='r', ls='--', lw=2, label='Threshold (u={:3.2%})'.format(evt_pot._u))
        ax.grid(ls='--')
        ax.set_xlim(xmin=dfRet.index[0], xmax=dfRet.index[-1])
        ax.set_ylim(ymin=0)
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=2))
        ax.xaxis.label.set_visible(False)
        ax.legend()
        
        ax = axes[0, 1]
        # ax1.hist(dfRet['Exceedances'].dropna(), bins=bins, density=True, histtype='stepfilled', alpha=1, color=colors[1])
        
        # _, bins, _ = ax.hist(dfRet['Losses'].values , bins=30, 
        #                        density=True, histtype='stepfilled',
        #                       alpha=0.8, color=colors[0])
        bins=len(dfRet)//150
        ax.hist(dfRet['Exceedances'].dropna().values, bins=bins, 
                density=True, histtype='stepfilled',
                color=colors[1], label='Exceedances')
        gp = evt_pot._gp
        x = np.linspace(gp.ppf(q=0.01), gp.ppf(q=0.99), 100)
        ax.plot(x, gp.pdf(x), 'b-', lw=2,  label='Gen.Pareto pdf')
        ax.axvline(evt_pot._u, c='r', ls='--', lw=2, label='Threshold (u={:3.2%})'.format(evt_pot._u))
        ax.set_title('Tail Loss Histogram / PDF')
        ax.set_xlabel('Loss')
        ax.set_ylabel('Frequency')
        ax.legend()
        ax.set_xlim(xmin=0)
        ax.grid(ls='--')
        ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=2))
        
        ax = axes[1, 1]    
        stats.probplot(dfRet['Exceedances'].dropna().values, dist=gp, plot=ax, fit=True)
        ax.get_lines()[0].set_markerfacecolor(colors[1])
        ax.get_lines()[0].set_markeredgecolor(colors[1])
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=2))
        ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=2))
        ax.grid(ls='--')

        ax = axes[0, 2]
        ax.hist(dfRet[t], bins=2*bins, color=colors[0], alpha=0.7, zorder=4)
        ax.axvline(var_p, ls='--', lw=2, c=colors[4])
        ax.annotate(f"VaR 95\n{var_p:2.2%}", xytext=(0.2, 0.8), textcoords="axes fraction", 
                         xy=(var_p, 0), xycoords='data',
                         va="center", ha="center",fontweight='bold', fontsize=9,
                          bbox=dict(boxstyle="round", 
                                    fc=colors[4], 
                                    alpha=0.5),
                          arrowprops=dict(arrowstyle="->", 
                                          connectionstyle="arc3, rad=0.2", 
                                          lw=1.5))
        ax.axvline(var_h, ls='--', lw=2, c=colors[5])
        ax.annotate(f"VaR Hyb\n{var_h:2.2%}", xytext=(0.1, 0.5), textcoords="axes fraction", 
                         xy=(var_h, 0), xycoords='data',
                         va="center", ha="center",fontweight='bold', fontsize=9,
                          bbox=dict(boxstyle="round", 
                                    fc=colors[5], 
                                    alpha=0.5),
                          arrowprops=dict(arrowstyle="->", 
                                          connectionstyle="arc3, rad=0.2", 
                                          lw=1.5))
        ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=1))
        ax.grid(ls='--')

        ax = axes[1, 2]
        listProb = [1/252, 1/1_260, 1/2_520, 1/5_040]
        labelProb = ['1Y', '5Y', '10Y', '20Y']
        ret=[evt_pot.func_eva(q) for q in  listProb]        
        ax.semilogy(ret, listProb, marker='.', color='b', lw=0.7, zorder=10)
        # ax.set_xlim(left=evt_pot._u)
        ax.set_ylim(bottom=0.009/100)
        ax.set_xlabel('Loss')
        ax.set_ylabel('Log-Probability')
        texts = []
        for r, q, lbl in zip(ret, listProb, labelProb):
            texts.append(ax.text(r, q, f"{lbl}:{r:3.2%}", size=10, fontweight='bold',
                                 bbox=None if lbl!='10Y' else {'facecolor':'none', 'alpha':0.9,
                                                               'boxstyle': 'round', 'pad':0.5,
                                                               'edgecolor':'red', 'linewidth':2}))
        ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=2))
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=2))
        ax.grid(ls='--')
        ax.legend(['Frequency : Loss(%)'])
        adjust_text(texts, ax=ax)
        
        plt.show()
        dic_figs[t] = fig
        
        
    #%%
    return dic_figs

if __name__ == "__main__":

    dt , str_fund, print_pdf = fu.get_config(['dt', 'str_fund', 'print_pdf'])
    nav = fu.get_NAV(dt, str_fund)
    
    str_path = f"../tex/{dt:%Y%m%d}/figuras"
   
    data = fund_data.db_data(dt, str_fund, verbose=True)      
    
    dic_f = main(data, nav)
    # for t, files in dic_f.items():
    #     for i, f in enumerate(files):
    #         fig_file = f"{str_path}/{dt:%Y%m%d}_{t}_{i:0.0f}.pdf"
    #         f.savefig(fig_file, #facecolor='silver',
    #                   bbox_inches = 'tight')
