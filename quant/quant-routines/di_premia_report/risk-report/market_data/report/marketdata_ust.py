# -*- coding: utf-8 -*-
"""
Created on Mon Oct 24 15:14:45 2022

@author: matheus.amaral
"""

import pandas as pd
import numpy as np
import datetime
import QuantLib as ql
from adjustText import adjust_text
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.gridspec as gridspec
from matplotlib.ticker import MultipleLocator
import xlwings as xw

import os, sys
sys.path.insert(1,  '../../')
from market_data import curve_db

from a1db.a1sql import SQLConnection

sys.path.insert(1,  os.path.expanduser('~\\Documents\\Github\\VaR_Simulation\\var_calc'))
import var_USTreasury

sys.path.insert(1,  os.path.expanduser('~\\Documents\\Github\\instruments\\USBond'))
import USTreasury

dt = datetime.date(2022,10,24)

today = ql.Date.from_date(dt)
calendar = ql.UnitedStates()
yesterday = calendar.advance(today, ql.Period(-1, ql.Days))
last_month = calendar.advance(today, ql.Period(-1, ql.Months))

dfUST, dfPnl = var_USTreasury.get_data(dt)

dic_curve = {}
curve_name = 'US Treasury'
for d in [today, yesterday, last_month]:
    dic_curve[d.to_date()] = curve_db.get_curve(d.to_date(), curve_name)
    dic_curve[d.to_date()].enableExtrapolation()
    
#%%

dts = [calendar.advance(today, ql.Period(1,ql.Days))] + [today + (x* 30) for x in range(1,143)]
rts = []
days = []

for dt_i in dts:
    days.append(dt_i - today)
    rts.append((dic_curve[today.to_date()].zeroRateValue(dt_i),
                dic_curve[yesterday.to_date()].forwardRateValue(today, dt_i),
                dic_curve[last_month.to_date()].forwardRateValue(today, dt_i)))

dfCurve = pd.DataFrame(data = rts, 
                       index = days, 
                       columns = [i.to_date() for i in [today, yesterday, last_month]])

dfUST['curve_rate_d-1'] = dfUST['maturity_date'].apply(lambda x: dic_curve[yesterday.to_date()].zeroRateValue(ql.Date.from_date(x)))
dfUST['curve_rate_d0'] = dfUST['maturity_date'].apply(lambda x: dic_curve[today.to_date()].zeroRateValue(ql.Date.from_date(x)))
dfUST['Change (BPs)'] = (dfUST['curve_rate_d0'] - dfUST['curve_rate_d-1']) * 10_000

dfUST['outlier'] = np.where(dfUST['1VaRShift'] < dfUST['Change (BPs)'].abs(), 
                            dfUST['Change (BPs)'], np.nan)

dfUST.set_index(dfUST['shortName'].str.strip('UST '), inplace = True)
dfUST.sort_values(by = 'maturity_date', ascending = False, inplace = True)

#%%

color_palette =['#323E48','#28829B','#C9CBCB', '#748D9E', '#2E9AB2',\
                'steelblue', 'slategrey', 'silver', 'lightgrey']

#### PLOT ####    
fig = plt.figure(tight_layout=True, figsize=(11, 7))
gs = gridspec.GridSpec(1, 2, width_ratios=[1,2])
gs1 = gridspec.GridSpecFromSubplotSpec(1, 2, subplot_spec=gs[0,0], width_ratios=[1, 2], wspace=0)


plt.tight_layout()
axRate = fig.add_subplot(gs1[0])
axUST = fig.add_subplot(gs1[1])
axUSTCurve= fig.add_subplot(gs[0,1])

#### CCY level, change and VaR ####
axRate.barh(dfUST.index, dfUST['rate'],zorder=3,\
          alpha=0.2, color=color_palette[1], label='rate(%)')
for i, vcto in enumerate(dfUST.index):
    axRate.text(0, i,' {:1.2%}'.format(dfUST.loc[vcto, 'rate']), \
                  fontweight='bold', va='center', color=color_palette[0])   
axRate.set_title('Rate')        
axRate.xaxis.set_major_locator(mticker.FixedLocator(axRate.get_xticks()))
axRate.set_xticklabels(['{:1.0%}'.format(x) for x in axRate.get_xticks()])

axRate.yaxis.set_major_locator(mticker.FixedLocator(axRate.get_yticks()))
axRate.set_yticklabels([x.split(' ')[-1] for x in dfUST.index])
axRate.set_ylabel('UST', fontweight='bold')


axUST.barh(dfUST['Change (BPs)'].index, dfUST['Change (BPs)'], zorder=2,\
         alpha=0.5, color=(dfUST['Change (BPs)'] > 0).map({True: color_palette[1], False: 'tomato'}))
axUST.barh(dfUST.index, dfUST['outlier'], zorder=3,\
         alpha=1, color='none', edgecolor='black', hatch="//")
axUST.axvline(0, lw=0.75, color='k')    
for i, vcto in enumerate(dfUST.index):
    shift = dfUST.loc[vcto, 'Change (BPs)']
    axUST.text(max(0, shift), i,' {:+2.0f}'.format(shift) if shift!=0 else ' -', \
                  fontweight='bold', va='center',\
                      color=('tomato' if shift<0 else color_palette[1]))   
for j in [-1, 1]:
    axUST.plot(dfUST['1VaRShift'].values*j, range(0,len(dfUST)), ls='', marker='|',\
              markersize=12, c='r', label='VaR', zorder=4)
axUST.set_title('Change (BPs) | VaR')
axUST.xaxis.set_minor_locator(MultipleLocator(10))
plt.setp(axUST.get_yticklabels(), visible=False)

#### Curva ####
axUSTCurve.plot(dfCurve.index, dfCurve[dt], color=color_palette[0], lw=2, label='{:%d-%b-%y}'.format(dt))
axUSTCurve.plot(dfCurve.index, dfCurve[yesterday.to_date()], color=color_palette[1], ls='--', lw=1.25, label='{:%d-%b-%y}'.format(yesterday.to_date()))
axUSTCurve.plot(dfCurve.index, dfCurve[last_month.to_date()], color=color_palette[4], ls=':', lw=1.25, label='{:%d-%b-%y}'.format(last_month.to_date()))
axUSTCurve.legend(title='')
axUSTCurve.set_xlim(left=0, right=4004)
axUSTCurve.set_xticks(np.arange(0, 4004, 360))
# axCurve.set_xlabel('days')
points = [360, 720, 1800, 3600]
axUSTCurve.set_xticklabels(['{:1.0f}Y'.format(i/360) if i in points else '' for i in axUSTCurve.get_xticks()])
axUSTCurve.plot(points, [dfCurve.loc[i,dt] for i in points], ls='', marker='.',color=color_palette[0])
texts = []
for i in points:
    texts.append(axUSTCurve.text(i, dfCurve.loc[i,dt],'{:1.2%}'.format(dfCurve.loc[i,dt]),\
                 fontweight='bold', color=color_palette[0], fontsize=11))
adjust_text(texts, ax=axUSTCurve, x=list(dfCurve.index)*3, y=list(dfCurve.T.values.flatten()))
axUSTCurve.yaxis.set_major_locator(mticker.FixedLocator(axUSTCurve.get_yticks()))
axUSTCurve.set_yticklabels(['{:3.1%}'.format(x) for x in axUSTCurve.get_yticks()])
axUSTCurve.set_title('UST Curve')
axUSTCurve.grid(ls='--', which='both')
    
fig.align_ylabels()