# -*- coding: utf-8 -*-
"""
Created on Fri Sep 23 08:27:03 2022

@author: matheus.amaral
"""

import pandas as pd
import numpy as np 
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib as mpl
import datetime
import timeit
import xlwings as xw
import fund_utils as fu
import sys
sys.path.insert(1, '../../liquidity_report/src')
import position


def main(dt, str_fund, report_filename, print_pdf = False):
    
    pos = position.positions(dt)
    dfPosition = pos.get_position().query(f"(trading_desk == '{str_fund}') & (type == 'Bond')")
    dfTurnover = pd.DataFrame(index = dfPosition.index)
    for delta in [30,60,90]:
        temp = pos.get_turnover(delta)
        dfTurnover = dfTurnover.join(temp['turnover'])
        dfTurnover.rename({'turnover':str(delta) + 'd'}, axis = 1, inplace = True)
        
    dfBond = dfPosition.join(dfTurnover['90d'])
    
    dfBond['perc_turnover'] = abs(dfBond['position'] / dfBond['90d'])   
    dfBond['90d'] *= 0.15
    dfBond['settle_days'] = np.ceil(abs(dfBond['position'] / dfBond['90d']))
    
    dfBond.sort_values(by = ['product_type', 'date_maturity'], ascending = [True, False], inplace = True)
    
    
    
    #%%
    color1, color2 = '#323E48', '#28829B'
    cmap = mpl.cm.get_cmap('coolwarm', 20)
    fig, (axTO, axLim) = plt.subplots(1, 2, sharey=True, figsize=(11, 16), gridspec_kw={'width_ratios': [3, 2]})
    plt.tight_layout(pad=0)
    plt.subplots_adjust(wspace=0)
    
    threshold = 0.15
    dfBond['position'].abs().plot.barh(ax=axTO, legend=False, zorder=2, alpha=0.05, 
                                  color=(dfBond['position'] > 0).map({True: color2, False: 'tomato'}), 
                                  fontsize = 13.5)
    axTO.set_xlim((0,1))
    axTO.set_xticks([])
    axTO.set_ylabel('')
    dfBond['settle_days'].abs().plot.barh(ax=axLim, legend=False, zorder=2, alpha=0.05,
                                               color=(dfBond['position'] > 0).map({True: color2, False: 'tomato'}))
    axLim.set_xlim((0,1))
    axLim.set_xticks([])
    for i, eqty in enumerate(dfBond.index):
        qty = dfBond.loc[eqty, 'position'] / 10**6
        axTO.text(0.25, i,' {:>4,.2f}M'.format(qty) if qty!=0 else ' -', \
                      fontweight='bold', va='center',ha='right',\
                          color=('tomato' if qty<0 else color1), fontsize = 13.5) 
        for j, d in enumerate([30, 60, 90]):
            qty = dfTurnover.loc[eqty, str(d) + 'd'] / 10**6
            axTO.text(0.5 + j*0.225, i,' {:>4,.0f}M'.format(qty) if qty!=0 else ' -', \
                          fontweight='normal', va='center', ha='right',\
                              color=('tomato' if qty<0 else color1), fontsize = 13.5) 
        qty = abs(dfBond.loc[eqty, 'perc_turnover'])
        axLim.text(0.35, i,' {:>4,.1%}'.format(qty) if qty!=0 else ' -', \
                      fontweight='bold', va='center',ha='right', color=color1, fontsize = 13.5) 
        qty = abs(dfBond.loc[eqty, 'settle_days'])
        axLim.text(0.7, i,' {:>3.0f}'.format(qty) if qty!=0 else ' -', \
                      fontweight='bold', va='center',ha='right', color=color1, fontsize=12.5,
                      backgroundcolor=cmap(min(int(qty),15))) 
        
            
    axTO.set_title('Asset1      |                Avg Turnover\n                           30d             60d              90d')
    axLim.set_title('Pos/90d Avg Turnover | Days to Liquidate*', fontsize=12.5)
    axLim.set_xlabel('*Days to liquidate position\nusing {:2.0%} of last 90d Avg Turnover'.format(threshold), size=9)
    
    if print_pdf:
         fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_{1}_bond_turnover.pdf'.format(dt, str_fund)
         fig.savefig(fig_file, bbox_inches = "tight")
         
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_bond_liq.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    
    wb = xw.Book(report_filename)
    wb.sheets('BondLiq').pictures.add(wb.api.Path + '/' + fig_file, name='bond_liq', update=True)
    
#%%

if __name__ == '__main__':
    
    dt = datetime.date(2022,9,22)
    str_fund = 'A1 Master FIM'
    report_filename = '../xls/RiskMap_model.xlsm'
    
    main(dt,str_fund,report_filename)