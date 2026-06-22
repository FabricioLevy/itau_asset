# -*- coding: utf-8 -*-
"""
Created on Mon Oct 17 14:38:55 2022

@author: matheus.amaral
"""

import pandas as pd
import numpy as np
from a1db.a1sql import SQLConnection
from datetime import date
import sys
sys.path.insert(1, '../../risk_report/src')
import fund_utils as fu
import matplotlib.pyplot as plt
import warnings 
import VaRCalculator

def main(dfPlot):
    
    n = len(dfPlot.index)
    
    if n>1:
        fig, ax = plt.subplots(nrows=n, ncols=1, figsize=(9, 9.5), gridspec_kw={'height_ratios': (n-1)*[1]+[1]},\
                                sharey=True, sharex=True)
        plt.tight_layout()
        fig.subplots_adjust(hspace=0.13)
        
        for j, b in enumerate(dfPlot.index):
            hbars = (dfPlot.loc[b]
              .reset_index()
              .pivot(index = 'Traders', columns = 'TraderMandate', values = b)
              .loc[dfPlot.columns.get_level_values(0).unique()]
              .plot.bar(ax=ax[j], legend=True if j == 0 else False, zorder=2, stacked=False, \
                                  rot=0, width = 0.85, color = {'Core':fu.color_palette[3],
                                                                'NonCore':fu.color_palette[5],
                                                                'Total':fu.color_palette[1]}))
            if j == 0:
                hbars.legend(loc = 'best')
            for c in hbars.containers:
                labels = [f'{w:2.0f}' if (w := v.get_height()) != 0 else '-' for v in c]
                
                ax[j].bar_label(c, labels = labels, fontweight = 'bold', size = 10)
                
            ax[j].set_xticks([], minor=True)
            ax[j].set_yticks([])
            ax[j].grid(ls='--', axis='y')
            ax[j].axhline(0, lw=0.5, c='grey')
            ax[j].set_xlabel('')
            ax[j].set_ylabel(b.replace(' ','\n') if b =='CUPOM CAMBIAL' else b, rotation=0, fontsize=10, ha='right', va='center')
            ax[j].set_title('')
            ax[j].tick_params(labelsize=11)
        ax[0].set_ylim(top=max(0.1, 2*float(dfPlot.max().max())), bottom=min(-.1, 1.1*float(dfPlot.min().min())))
        ax[0].set_yticklabels([])
        ax[j].set_ylabel(b.replace(' ','\n'), rotation=0, fontweight='bold', fontsize=11, ha='right', va='center')
        ax[j].set_facecolor('lightgrey')
        
                
        # fig_file = fig_file = f"../tex/{dt:%Y_%m_%d}/figuras/{dt:%Y%m%d}_CVaR_Braekdown.pdf"
        # fig.savefig(fig_file, bbox_inches = "tight")
        # plt.show()
        
#%%

if __name__ == '__main__':
    dt = date(2022,10,24)
    str_fund = 'A1 Master FIM'
    vcal = VaRCalculator.VaRCalculator(dt, str_fund)
    
    dfPlot = vcal.calculate_CVaR(by = ['Traders', 'TraderMandate'], adjust = True)      
    
    main(dfPlot)
