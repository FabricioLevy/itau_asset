# -*- coding: utf-8 -*-
"""
Created on Thu Aug 25 14:26:36 2022

@author: matheus.amaral
"""

import data_test as dtest
import pandas as pd
import scipy.stats as ss
import numpy as np
from datetime import date
import fund_utils as fu
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
import matplotlib.gridspec as gridspec
from matplotlib.ticker import MaxNLocator 

import QuantLib as ql

calendar = ql.Brazil()

d = calendar.businessDaysBetween(ql.Date.from_date(date(2022,8,25)), ql.Date.from_date(date(2023,1,1)))



dt = date(2022,9,30)
str_fund = 'A1 Master FIM'


db = dtest.db_data(dt,str_fund)

dfPnl = db.get_PnL(by = 'Traders_Adj',append_cdi = False) * 10_000

dfVar = db.get_AdjustedVaR().join(db.get_Risk()) * 10_000

traders = fu.get_traders(dt)

q = 0.975
p = 0.05

for t in traders.keys():
    
    df = dfPnl[[t]].join(dfVar[[t]], rsuffix = '_VaR', lsuffix = '_Pnl')
    
    df = df[df[f'{t}_Pnl'] != 0]
    df['Var_D1'] = df[f'{t}_VaR'].shift(1)
    df['outlier'] = np.where(df[f'{t}_Pnl'] < df['Var_D1'],
                             df[f'{t}_Pnl'], np.nan)
    
    
    for c in ['a00', 'a01', 'a10', 'a11']:
        df[c] = np.nan
    v = df[['outlier']].values.flatten()
    
    for i,dt_i in enumerate(df.index[1:], start = 1):
        df.loc[dt_i,'a00'] = 1 if np.isnan(v[i-1]) & np.isnan(v[i]) else 0
        df.loc[dt_i,'a01'] = 1 if np.isnan(v[i-1]) & ~np.isnan(v[i]) else 0
        df.loc[dt_i,'a10'] = 1 if ~np.isnan(v[i-1]) & np.isnan(v[i]) else 0
        df.loc[dt_i,'a11'] = 1 if ~np.isnan(v[i-1]) & ~np.isnan(v[i]) else 0
    df.loc[df.index[0],'a00'] = 1
    
    V_00 = df['a00'].sum()
    V_01 = df['a01'].sum()
    V_10 = df['a10'].sum()
    V_11 = df['a11'].sum()
    
    p_00=V_00/(V_00+V_01)
    p_01=V_01/(V_00+V_01)  
    p_10=V_10/(V_10+V_11)
    p_11=V_11/(V_10+V_11)  
    hat_p = (V_01+V_11)/(V_00+V_01+V_10+V_11)
    al = np.log(1-hat_p)*(V_00+V_10) + np.log(hat_p)*(V_01+V_11)
    bl = np.log(p_00)*V_00 + np.log(p_01)*V_01 + (0 if ((V_11==0)|(V_10==0)) else np.log(p_10)*V_10 + np.log(p_11)*V_11)
    LRatioCCI = -2*(al-bl)
    
    n,o = df[[f'{t}_Pnl', 'outlier']].count().values
    [u,l] = ss.binom.ppf(q,n,p), ss.binom.ppf(1-q,n,p)

    x = np.arange(ss.binom.ppf(0.0001,n,p),ss.binom.ppf(0.9999,n,p) + 1)        
    
    blue_x = [i for i in x if i >= l and i <= u]
    red_x = [i for i in x if i < l or i > u]


    color1, color2 = fu.color_palette[0], fu.color_palette[1]
        
    locator = mdates.AutoDateLocator(minticks=3, maxticks=7)
    formatter = mdates.ConciseDateFormatter(locator, formats=['%b\n%Y', '%b', '%d', '%H:%M', '%H:%M', '%S.%f'], show_offset=False)
    
    fig = plt.figure(figsize=(10, 7), tight_layout=True)
    gs = gridspec.GridSpec(2, 3, height_ratios=[3,2], width_ratios=[4,3,2])
    
    ax = fig.add_subplot(gs[0, :])
    axh= fig.add_subplot(gs[1, 0])
    axk= fig.add_subplot(gs[1, 1])
    axc= fig.add_subplot(gs[1, 2])
      
    for axi in [ax, axh, axk, axc]:
            axi.tick_params(labelsize=11)
            
    ax.plot(df['Var_D1'], ls='-', c=color1, label='VaR D-1')
    ax.plot(df[f'{t}_Pnl'], ls='', marker='.', label='PnL D0', color=color2)
    ax.plot(df['outlier'], ls='', c='r', marker='o', alpha=0.5, label='Outlier')
    ax.grid(ls='--', which='both')
    ax.legend(loc=9)
    ax.set_title('{} - VaR Backtesting'.format(t), fontsize=14)
    ax.axhline(0, c='k', lw=1)
    ax.set_xlim(left=df.index[0], right=df.index[-1])
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    if len(df) < 126:
        ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonthday=15))
    else:
        ax.xaxis.set_minor_locator(mdates.MonthLocator(interval=1))
    ax.tick_params(which='both', length=5, width=1.5)
    ticks_loc = ax.get_yticks().tolist()
    ax.yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
    ax.set_yticklabels(['{:2.0f}'.format(i) for i in ticks_loc])
    
    # Histogram
    _,bins,_ = axh.hist(df[f'{t}_Pnl'], bins=12, zorder=3, alpha=0.7, color=color2, label='Daily PnL (n={:1.0f})'.format(n))
    axh.hist(df['outlier'][~df['outlier'].isna()],bins=bins, zorder=4, alpha=0.5, color='r', label='Outliers')
    axh.grid(ls='--')
    axh.axvline(0, ls='--', color='k')
    axh.legend()
    axh.set_title('PnL - Histogram', fontsize=14)
    ticks_loc = axh.get_xticks().tolist()
    axh.yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
    axh.set_yticklabels(['{:2.0f}'.format(i) for i in ticks_loc])
    
    out_values = df.dropna().sort_index(ascending=False)[['Var_D1',f'{t}_Pnl']]
    # out_values.to_csv('../output/temp_figs/{:%Y%m%d}_{}_outliers.csv'.format(dt, str_fund))
    
    axk.vlines(red_x, 0, ss.binom.pmf(red_x, n, p), colors='r', lw=6, alpha=0.5, label='rejection interval')
    axk.vlines(blue_x, 0, ss.binom.pmf(blue_x, n, p), colors=color2, lw=6, alpha=0.5, label='non-rejection [{:1.0f};{:1.0f}]'.format(blue_x[0], blue_x[-1]))
    
    axk.vlines(o, 0, ss.binom.pmf(o, n, p), colors=color1, ls='--', lw=3, label='#Outliers = {:1.0f} / {:1.0f}'.format(o,n))
    axk.set_title("Kupiec's test", fontsize=14)
    axk.set_ylim(bottom=0)
    axk.xaxis.set_major_locator(MaxNLocator(integer=True))
    axk.set_ylabel('Frequency')
    axk.set_xlabel('Number of Exceptions')
    axk.grid(ls='--')
    axk.set_yticks([])
    axk.legend()
    
    # Christoffersen
    axc.set_title("Christoffersen’s", fontsize=13)
    axc.set_ylim(bottom=0)
    axc.set_xlim(left=0, right=5)
    x = np.arange(0, 6, .01)
    axc.plot(x, ss.chi2.pdf(x, 1), color=color1, lw=2)
    ic = 0.95
    xi = ss.chi2.ppf(ic, 1)
    axc.axvline(xi, lw=1.5, ls='--', c='tomato',label='Acceptance')
    xi_notReject = [i for i in x if i<=xi]
    axc.fill_between(xi_notReject, ss.chi2.pdf(xi_notReject, 1), color=color2, alpha=0.5)
    axc.axvline(LRatioCCI, lw=2, ls='--', color=color1, label='L Ratio CCI')
    axc.legend()
    axc.grid(ls='--')
    axc.set_xlabel(r'Prob. Density Function ($\chi^2_1$)')