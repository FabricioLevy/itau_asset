import pandas as pd
import numpy as np
import datetime
import QuantLib as ql
import xlwings as xw

from a1db.a1sql import SQLConnection

from adjustText import adjust_text
import matplotlib.ticker as mticker
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.ticker import MultipleLocator

import os, sys
path_var = os.path.expanduser('~\\Documents\\Github')
sys.path.insert(1, path_var + '\\VaR_Simulation\\var_calc')
import var_NTNB

import marketdata_config


#%%
def main(dt, report_filename):
#%%
    today = ql.Date.from_date(dt)
    calendar_br = ql.Brazil()
    yesterday = calendar_br.advance(today, ql.Period(-1, ql.Days))
    last_month = calendar_br.advance(today, ql.Period(-1, ql.Months))
    
    connection = SQLConnection().get_connection()
    str_sql = """
                SELECT date_reference,[curve_name],[tenor_date],tenor,[curve_rate],[discount_factor]
                FROM [risk].[interest_rate_curve]
                WHERE date_reference in ('{:%Y-%m-%d}','{:%Y-%m-%d}','{:%Y-%m-%d}') 
                AND curve_name in ('NTNB Zero', 'NTNB BEI', 'DAP Fut', 'DAP BEI') and Tenor is not null
        """
    str_sql = str_sql.format(dt, yesterday.to_date(), last_month.to_date())
    df = pd.read_sql(str_sql, connection)
    
    str_sql = """
                SELECT pp.date_reference, p.date_maturity, pp.rate as rate
                  FROM [middle].[product] p INNER JOIN middle.product_price pp ON p.id = pp.product_id
                  WHERE p.product_type = 'NTN-B' and pp.date_reference in ('{:%Y-%m-%d}','{:%Y-%m-%d}') 
        """
    str_sql = str_sql.format(dt, yesterday.to_date())
    dfBs = pd.read_sql(str_sql, connection)
    dfBs = dfBs.pivot(index='date_maturity', columns='date_reference', values='rate')
     
    #%%
    dfBs['Change (BPs)']=(dfBs[dt]-dfBs[yesterday.to_date()])*10000
    dfBs['VctoLabel'] = [x.strftime('%b-%y') for x in dfBs.index]
    
    [dfNTNB, dfPnl] =var_NTNB.get_data(dt)
    dfNTNB['VctoLabel'] = [x.strftime('%b-%y') for x in dfNTNB['tenor_date']]
    dfNTNB['du'] = [calendar_br.businessDaysBetween(today, ql.Date.from_date(x)) for x in dfNTNB['tenor_date']]
    dfNTNB = dfNTNB[dfNTNB['du'] > 1]
    dfNTNB.set_index('VctoLabel', inplace=True)
    dfNTNB = dfNTNB.join(dfBs[['VctoLabel','Change (BPs)']].set_index('VctoLabel'))
    dfNTNB.sort_values('tenor_date', ascending=False, inplace=True)
    dfNTNB.loc[dfNTNB['1VaRShift'] < dfNTNB['Change (BPs)'].abs(), 'outlier'] =  dfNTNB['Change (BPs)']
    
    
    #%%
    dic_curve = {}
    for c in ['NTNB Zero', 'NTNB BEI', 'DAP Fut', 'DAP BEI']:
        dic_curve[c] = df[df['curve_name']==c].pivot(index='tenor', columns='date_reference', values='curve_rate')
    #%%
    color_palette =['#323E48','#28829B','#C9CBCB', '#748D9E', '#2E9AB2',\
                    'steelblue', 'slategrey', 'silver', 'lightgrey']
    
    #### PLOT ####    
    fig = plt.figure(tight_layout=True, figsize=(11, 7))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1,2])
    gs1 = gridspec.GridSpecFromSubplotSpec(1, 2, subplot_spec=gs[0], width_ratios=[1, 2], wspace=0)
    gs2 = gridspec.GridSpecFromSubplotSpec(2, 2, subplot_spec=gs[1], height_ratios=[1, 1], wspace=0.05)
    plt.tight_layout()
    axNTNBrate = fig.add_subplot(gs1[0])
    axNTNB = fig.add_subplot(gs1[1], sharey=axNTNBrate)
    axCurveDAP= fig.add_subplot(gs2[0,0])
    axCurveNTNB= fig.add_subplot(gs2[0,1], sharey=axCurveDAP)
    axBEIDAP= fig.add_subplot(gs2[1,0])
    axBEINTNB= fig.add_subplot(gs2[1,1], sharey=axBEIDAP)
    
    #### NTN-B level, change and VaR ####
    axNTNBrate.barh(dfNTNB.index, dfNTNB['curve_rate'],zorder=3,\
              alpha=0.2, color=color_palette[1], label='rate(%)')
    axNTNBrate.axvline(0, lw=0.5, color='k')      
    for i, vcto in enumerate(dfNTNB.index):
        axNTNBrate.text(0, i,' {:1.2%}'.format(dfNTNB.loc[vcto, 'curve_rate']), \
                      fontweight='bold', va='center', 
                      color=('tomato' if dfNTNB.loc[vcto, 'curve_rate']<0 else color_palette[0]))   
    axNTNBrate.set_title('NTN-B')
    # axNTNBrate.set_xticklabels(['{:1.0%}'.format(x) for x in axNTNBrate.get_xticks()])
    axNTNBrate.xaxis.set_major_formatter(mticker.PercentFormatter(1))
    
    
    axNTNB.barh(dfNTNB['Change (BPs)'].index, dfNTNB['Change (BPs)'], zorder=2,\
             alpha=0.7, color=(dfNTNB['Change (BPs)'] > 0).map({True: color_palette[1], False: 'tomato'}))
    axNTNB.barh(dfNTNB.index, dfNTNB['outlier'], zorder=3,\
             alpha=1, color='none', edgecolor='black', hatch="//")
    axNTNB.axvline(0, lw=0.75, color='k')    
    for i, vcto in enumerate(dfNTNB.index):
        shift = dfNTNB.loc[vcto, 'Change (BPs)']
        axNTNB.text(max(0, shift), i,' {:+2.0f}'.format(shift) if shift!=0 else ' -', \
                      fontweight='bold', va='center',\
                          color=('tomato' if shift<0 else color_palette[1]))   
    for j in [-1, 1]:
        axNTNB.plot(dfNTNB['1VaRShift'].values*j, range(0,len(dfNTNB)), ls='', marker='|',\
                  markersize=12, c='r', label='VaR', zorder=3)
    axNTNB.set_title('Change (BPs) | VaR')
    if (axNTNB.get_xlim()[1] - axNTNB.get_xlim()[0]) < 95:
        axNTNB.xaxis.set_major_locator(MultipleLocator(20))
        axNTNB.xaxis.set_minor_locator(MultipleLocator(5))
    plt.setp(axNTNB.get_yticklabels(), visible=False)
    
    #### Curva Zeros ####
    for c, ax in zip (['DAP Fut', 'NTNB Zero'],[axCurveDAP, axCurveNTNB]):
        ax.plot(dic_curve[c].index, dic_curve[c][dt], color=color_palette[0], lw=2, label='{:%d-%b-%y}'.format(dt))
        ax.plot(dic_curve[c].index, dic_curve[c][yesterday.to_date()], color=color_palette[1], ls='--', lw=1.25, label='{:%d-%b-%y}'.format(yesterday.to_date()))
        ax.plot(dic_curve[c].index, dic_curve[c][last_month.to_date()], color=color_palette[4], ls=':', lw=1.25, label='{:%d-%b-%y}'.format(last_month.to_date()))
        ax.legend(title='')
        ax.set_xlim(left=1, right=3750)
        ax.set_xticks(np.arange(0, 3601, 360))
        # # axCurve.set_xlabel('days')
        points = [360, 720, 1800, 3600]
        ax.plot(points, [dic_curve[c].loc[i,dt] for i in points], ls='', marker='.',color=color_palette[0])
        texts = []
        for i in points:
            texts.append(ax.text(i, dic_curve[c].loc[i,dt],'{:1.2%}'.format(dic_curve[c].loc[i,dt]),\
                          fontweight='bold', fontsize=9,
                          color=('tomato' if dic_curve[c].loc[i,dt]<0 else color_palette[0])))
        adjust_text(texts, ax=ax, x=list(dic_curve[c].index)*3, y=list(dic_curve[c].T.values.flatten()))
        ax.set_title(c)
        # ax.xaxis.set_minor_locator(MultipleLocator(360))
        ax.set_xticklabels(['{:1.0f}y'.format(x/360) if x in points else '' for x in ax.get_xticks()])
    
    # ax.set_yticklabels(['{:3.1%}'.format(x) for x in ax.get_yticks()])
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1))
    plt.setp(axCurveNTNB.get_yticklabels(), visible=False)
    
    #### BEI ####
    for c, ax in zip (['DAP BEI', 'NTNB BEI'],[axBEIDAP, axBEINTNB]):
        
        ax.plot(dic_curve[c].index, dic_curve[c][dt], color=color_palette[0], lw=2, label='{:%d-%b-%y}'.format(dt))
        ax.plot(dic_curve[c].index, dic_curve[c][yesterday.to_date()], color=color_palette[1], ls='--', lw=1.25, label='{:%d-%b-%y}'.format(yesterday.to_date()))
        ax.plot(dic_curve[c].index, dic_curve[c][last_month.to_date()], color=color_palette[4], ls=':', lw=1.25, label='{:%d-%b-%y}'.format(last_month.to_date()))
        ax.legend(title='')
        ax.set_xlim(left=1, right=3750)
        ax.set_xticks(np.arange(0, 3601, 360))
        points = [360, 720, 1800, 3600]
        ax.plot(points, [dic_curve[c].loc[i,dt] for i in points], ls='', marker='.',color=color_palette[0])
        texts = []
        for i in points:
            texts.append(ax.text(i, dic_curve[c].loc[i,dt],'{:1.2%}'.format(dic_curve[c].loc[i,dt]),\
                          fontweight='bold', color=color_palette[0], fontsize=9))
        adjust_text(texts, ax=ax, x=dic_curve[c].index, y=dic_curve[c][dt].values)
        ax.set_title('Breakeven Inflation')
        # ax.xaxis.set_minor_locator(MultipleLocator(360))
        ax.set_xticklabels(['{:1.0f}y'.format(x/360) if x in points else '' for x in ax.get_xticks()])
    
    
    # ax.set_yticklabels(['{:3.1%}'.format(x) for x in ax.get_yticks()])
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1))
    plt.setp(axBEINTNB.get_yticklabels(), visible=False)
    
    
    for ax in [axNTNBrate, axNTNB, axCurveDAP, axCurveNTNB, axBEIDAP, axBEINTNB]:
        ax.grid(ls='--', which='both')

    fig_file = os.path.expanduser('~\\Documents\\Github\\market_data\\report') + '/temp_figs/{:%Y%m%d}_inflation.svg'.format(dt)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    
    wb = xw.Book(report_filename)
    # wb.sheets('BRL_rates').pictures.add(wb.api.Path + '/../' + fig_file, name='marketdata_inflation', update=True) 
    wb.sheets('BRL_rates').pictures.add(fig_file, name='marketdata_inflation', update=True) 
    
#%%    
if __name__ == "__main__":
    
    dt = marketdata_config.get_config('dt')
    
    report_filename = 'xls/MarketData_model.xlsm'
    main(dt, report_filename) 
        


