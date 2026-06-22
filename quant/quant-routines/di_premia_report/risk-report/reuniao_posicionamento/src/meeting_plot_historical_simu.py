import datetime
import pandas as pd
import numpy as np

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import adjustText

import sys
sys.path.insert(1, '../../risk_report/src')
import fund_utils as fu
import fund_data


#%%#################
def main(data, nav, figsize=(12, 6), print_pdf=False):
    #%%
    # dfHypoPnL = data._dfHypoPnL.groupby(level=['Traders','Risk'], axis=1).sum()
    # traders = ['MS']
    
    # for t in traders:
    #     temp_df = dfHypoPnL[t].copy() / nav
    #     temp_df[t] = temp_df.sum(axis=1)
    
    #%%
    dic_var = data._dic_var['Risk'].loc[dt] * 10_000
    dic_var['Fund'] = data._dic_var['Fund'].loc[dt,'Fund'] * 10_000
    dfHypoPnL = data._dfHypoPnL.groupby(level=['Risk'], axis=1).sum() / nav * 10_000
    dfHypoPnL['Fund'] = dfHypoPnL.sum(axis=1)
    bins = np.linspace(dfHypoPnL['Fund'].min(), dfHypoPnL['Fund'].max(), 80)
    
    fig, axes = plt.subplots(2, 5, figsize=figsize, sharex=True)
    fig.tight_layout(w_pad=1.5, h_pad=2)
    
    for c, ax in zip(dfHypoPnL.columns, axes.flatten()):
        var = dic_var[c]
        es = dfHypoPnL[dfHypoPnL[c]<var][c].mean()
        qtl_99_9 = dfHypoPnL[c].quantile(0.001)
        ax.set_title(f"{c}", fontsize=11, fontweight='bold')
        dfHypoPnL[c].hist(ax=ax, bins=bins, grid=False, zorder=3, color=fu.color_palette[1])
        y_pos = np.mean(ax.get_ylim())
        x_pos = (ax.get_xlim()[0] + es) / 2
        
        ax.annotate(f"{qtl_99_9:2,.1f}", xytext=(0.2, 0.3), textcoords="axes fraction", 
                    xy=(qtl_99_9, 0), xycoords='data',
                    va="center", ha="center",fontweight='bold',
                    bbox=dict(boxstyle="round", fc='tomato', alpha=0.5),
                    arrowprops=dict(arrowstyle="->", connectionstyle="arc3, rad=+0.2", lw=1.5))
        
        # ax.text(x_pos, y_pos/2, f"{qtl_99_9:2,.1f}", ha='center')
        ax.text(x_pos, y_pos, f"CVaR\n{es:2,.1f}bps", ha='center')
        
        ax.axvline(var, c='r', ls=':', lw=2, zorder=5, label=f" VaR ({-var:2.1f} bps)")
        # ax.axvspan(-2500, var, alpha=0.5, color='red')
        # ax.fill_between(ax.get_xlim()[0], var, color='tomato')
        
        ax.grid(ls='--')
        ax.legend(fontsize=8, loc=2)
    
    fig.suptitle('VaR e Quantile 99.9% - Simulação Histórica de 15 anos', y=1.05, fontweight='bold')
    
    plt.show()
    fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_fund_var_simu_histogram.pdf'.format(dt)
    if print_pdf:
        fig.savefig(fig_file, bbox_inches = "tight")
    #%%
    # dfHypoPnL = data._dfHypoPnL.groupby(level=['geo'], axis=1).sum() / nav * 10_000
    
    
    ncol=5
    temp_df = dfHypoPnL.sort_values('Fund').head(ncol).sort_index()
    fig = plt.figure(figsize=(12, 6), tight_layout=True)
    fig.tight_layout(h_pad=0, w_pad=0)
    gs = gridspec.GridSpec(2, ncol, height_ratios=[2,1])
    
    axRet = fig.add_subplot(gs[0, :])
    axes = []
    for i in range(0, ncol):    
        axes.append(fig.add_subplot(gs[1, i]))
    
    ax = axRet
    ax.set_title(f"Simulação Histórica - 15 anos", fontsize=12, fontweight='bold')
    ax.plot(dfHypoPnL.index, dfHypoPnL['Fund'], color=fu.color_palette[1], ls='', marker='.', alpha=0.5)
    ax.set_ylabel("Simulated PnL (BPs)")
    ax.grid(ls='--', which='major')
    ax.grid(ls=':', which='minor')
    ax.set_xlim(left=dfHypoPnL.index[0], right=dfHypoPnL.index[-1])
    
    txts = []
    for i, axi in enumerate(axes):
        ax.scatter([temp_df.index[i]],[temp_df['Fund'].iloc[i]],color='tomato')
        txts.append(ax.text(temp_df.index[i],
                            temp_df['Fund'].iloc[i],
                            f"{temp_df.index[i]:%d%b%y}"))
        adjustText.adjust_text(txts, ax=ax)
        axi.set_ylim(top=200, bottom=-300)
        axi.set_title(f"{temp_df.index[i]:%d%b%y}", fontsize=11, fontweight='bold')
        temp_df.iloc[i].plot.bar(ax=axi, grid=False, color=fu.color_palette[1], zorder=3)
        for j, v in enumerate(temp_df.iloc[i].values):
            axi.text(j, 0, f" {v:+2.0f}", ha='center', va='bottom', rotation=90, fontsize=8, 
                     fontweight='bold', c='r' if v<0 else 'k')
        
        
        axi.grid(ls='--', axis='y')
        axi.set_xlabel('')
    
    axes[0].set_ylabel("Simulated PnL (BPs)")
    fig.align_ylabels()
    fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_fund_var_simu_top5.pdf'.format(dt)
    if print_pdf:
        fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    #%%
    
    
    
    
    
   
    #%%
    return fig

if __name__ == "__main__":

    dt , str_fund, print_pdf = fu.get_config(['dt', 'str_fund', 'print_pdf'])
    nav = fu.get_NAV(dt, str_fund)
    
    str_path = "../output/temp_figs/"
   
    data = fund_data.db_data(dt, str_fund, verbose=True)      
    
    f = main(data, nav, print_pdf=print_pdf)
    # fig_file = f"../tex/{dt:%Y_%m_%d}/figuras/{dt:%Y%m%d}_peers_vol.pdf"
    # f.savefig(fig_file, bbox_inches = 'tight', pad_inches = 0)
    
  