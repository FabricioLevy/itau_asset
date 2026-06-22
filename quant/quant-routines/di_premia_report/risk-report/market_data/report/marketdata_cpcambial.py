import pandas as pd
import numpy as np
import datetime
import QuantLib as ql
from adjustText import adjust_text
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import matplotlib.gridspec as gridspec
from matplotlib.ticker import MultipleLocator
import xlwings as xw

from a1db.a1sql import SQLConnection

import os, sys
path_var = os.path.expanduser('~\\Documents\\Github\\market_data')
sys.path.insert(1, path_var)
import curve_db
import marketdata_config

path_var = os.path.expanduser('~\\Documents\\Github\\VaR_Simulation\\var_calc')
sys.path.insert(1, path_var)
import var_FRC


#%%
def main(dt, report_filename):
#%%
    connection = SQLConnection().get_connection()
     
    str_sql = """
                SELECT [date_reference],[product_id],[price]
                FROM [middle].[product_price]
                WHERE product_id in ('CDS BR 1Y','OIS 1Y','CDS BR 2Y','OIS 2Y','CDS BR 5Y','OIS 5Y')
                and date_reference <= '{:%Y-%m-%d}'   
            """
    str_sql = str_sql.format(dt)
    dfRates = pd.read_sql(str_sql, connection).pivot(index='date_reference', columns='product_id', values='price')
    
    for y in ['1Y', '2Y', '5Y']:
        dfRates['CDS BR + OIS {}'.format(y)] = dfRates['CDS BR {}'.format(y)]/10000 + dfRates['OIS {}'.format(y)]/100    
    
    str_sql = """
                SELECT [date_reference],[tenor],[curve_rate]
                FROM [risk].[interest_rate_curve]
                WHERE curve_name = 'USD BR' and tenor in (360, 720, 1800)
                and date_reference <= '{:%Y-%m-%d}'
            """
    str_sql = str_sql.format(dt)
    df2 = pd.read_sql(str_sql, connection).pivot(index='date_reference', columns='tenor', values='curve_rate')
    df2.columns = ['CC 1Y', 'CC 2Y', 'CC 5Y']
    
    dfRates = dfRates.join(df2).dropna()
    
    
#%%
    today = ql.Date.from_date(dt)
    calendar_br = ql.Brazil(ql.Brazil().Settlement)
    yesterday = calendar_br.advance(today, ql.Period(-1, ql.Days))
    last_month = calendar_br.advance(today, ql.Period(-1, ql.Months))
       
    [dfFRC, dfPnl] = var_FRC.get_data(dt)
    
    #%%
    short_index_list = [i for i in dfFRC['tenor_date'] if (i-dt).days<100]
    short_index_list += [i for i in dfFRC['tenor_date'] if (i.month in [1,4,7,10]) & (i.year-dt.year<2)]
    short_index_list += [i for i in dfFRC['tenor_date'] if (i.month in [1,7]) & (i.year-dt.year>=2) & (i.year-dt.year<5)]
    short_index_list += [i for i in dfFRC['tenor_date'] if (i.month == 1) & (i.year-dt.year>=5)]
    short_index_list = sorted(set(short_index_list))
    dfFRC = dfFRC[dfFRC['tenor_date'].isin(short_index_list)]
    dfFRC.sort_values('tenor_date', ascending=False, inplace=True)
    
    #%%
    dic_curve = {}
    for d in [today, yesterday, last_month]:
        dic_curve[d.to_date()] = curve_db.get_curve(d.to_date(), 'USD BR')
        dic_curve[d.to_date()].enableExtrapolation()
    
    dts = []
    rts = []
    dts = [calendar_br.advance(today, ql.Period(1, ql.Days))] +\
            [today + (30*x) for x in range(1, 143)]
    
    days = []
    for dt_i in dts:
        days.append(dt_i-today)
        rts.append((dic_curve[today.to_date()].zeroRateValue(dt_i), 
                    dic_curve[yesterday.to_date()].forwardRateValue(today, dt_i),
                    dic_curve[last_month.to_date()].forwardRateValue(today, dt_i)))
    
    dfCurve = pd.DataFrame(rts, index=days, columns=[i.to_date() for i in [today, yesterday, last_month]])
    
    dfFRC['curve_rate_d-1'] = dfFRC['tenor_date'].apply(lambda x: dic_curve[yesterday.to_date()].zeroRateValue(ql.Date.from_date(x)))
    dfFRC['Change (BPs)'] = (dfFRC['curve_rate']-dfFRC['curve_rate_d-1'])*10000
    
    dfFRC.loc[dfFRC['1VaRShift'] < dfFRC['Change (BPs)'].abs(), 'outlier'] =  dfFRC['Change (BPs)']
    
    dfFRC['id'] = pd.to_datetime(dfFRC['tenor_date']).dt.strftime('%b-%y')
    dfFRC.set_index(dfFRC['id'], inplace=True)
   
    #%%
    color_palette =['#323E48','#28829B','#C9CBCB', '#748D9E', '#2E9AB2',\
                    'steelblue', 'slategrey', 'silver', 'lightgrey']
    
    #### PLOT ####    
    fig = plt.figure(tight_layout=True, figsize=(11, 7))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1,2])
    gs1 = gridspec.GridSpecFromSubplotSpec(1, 2, subplot_spec=gs[0], width_ratios=[1, 2], wspace=0)
    gs2 = gridspec.GridSpecFromSubplotSpec(2, 1, subplot_spec=gs[1], height_ratios=[2, 3])#, hspace=0.25)
    gs3 = gridspec.GridSpecFromSubplotSpec(3, 1, subplot_spec=gs2[1], hspace=0.05)
    plt.tight_layout()
    axFRCrate = fig.add_subplot(gs1[0])
    axFRC= fig.add_subplot(gs1[1], sharey=axFRCrate)
    axCurve= fig.add_subplot(gs2[0])
    axSpread1= fig.add_subplot(gs3[0])
    axSpread2= fig.add_subplot(gs3[1], sharex=axSpread1)
    axSpread5= fig.add_subplot(gs3[2], sharex=axSpread1)
    
    #### FRC level, change and VaR ####
    axFRCrate.barh(dfFRC.index, dfFRC['curve_rate'],zorder=3,\
              alpha=0.2, color=color_palette[1], label='rate(%)')
    for i, vcto in enumerate(dfFRC.index):
        axFRCrate.text(0, i,' {:1.2%}'.format(dfFRC.loc[vcto, 'curve_rate']), \
                      fontweight='bold', va='center', color=color_palette[0])   
    axFRCrate.set_title('Cp Cambial')
    axFRCrate.xaxis.set_major_locator(mticker.FixedLocator(axFRCrate.get_xticks()))
    axFRCrate.set_xticklabels(['{:1.0%}'.format(x) for x in axFRCrate.get_xticks()])
    
    
    axFRC.barh(dfFRC['Change (BPs)'].index, dfFRC['Change (BPs)'], zorder=2,\
             alpha=0.5, color=(dfFRC['Change (BPs)'] > 0).map({True: color_palette[1], False: 'tomato'}))
    axFRC.barh(dfFRC.index, dfFRC['outlier'], zorder=3,\
             alpha=1, color='none', edgecolor='black', hatch="//")
    axFRC.axvline(0, lw=0.75, color='k')    
    for i, vcto in enumerate(dfFRC.index):
        shift = dfFRC.loc[vcto, 'Change (BPs)']
        axFRC.text(max(0, shift), i,' {:+2.0f}'.format(shift) if shift!=0 else ' -', \
                      fontweight='bold', va='center',\
                          color=('tomato' if shift<0 else color_palette[1]))   
    for j in [-1, 1]:
        axFRC.plot(dfFRC['1VaRShift'].values*j, range(0,len(dfFRC)), ls='', marker='|',\
                  markersize=12, c='r', label='VaR', zorder=4)
    axFRC.set_title('Change (BPs) | VaR')
    axFRC.xaxis.set_minor_locator(MultipleLocator(10))
    plt.setp(axFRC.get_yticklabels(), visible=False)
 
    #### Curva Cp Cambial ####
    axCurve.plot(dfCurve.index, dfCurve[dt], color=color_palette[0], lw=2, label='{:%d-%b-%y}'.format(dt))
    axCurve.plot(dfCurve.index, dfCurve[yesterday.to_date()], color=color_palette[1], ls='--', lw=1.25, label='{:%d-%b-%y}'.format(yesterday.to_date()))
    axCurve.plot(dfCurve.index, dfCurve[last_month.to_date()], color=color_palette[4], ls=':', lw=1.25, label='{:%d-%b-%y}'.format(last_month.to_date()))
    axCurve.legend(title='')
    axCurve.set_xlim(left=0, right=4004)
    axCurve.set_xticks(np.arange(0, 4004, 360))
    # axCurve.set_xlabel('days')
    points = [360, 720, 1800, 3600]
    axCurve.set_xticklabels(['{:1.0f}Y'.format(i/360) if i in points else '' for i in axCurve.get_xticks()])
    axCurve.plot(points, [dfCurve.loc[i,dt] for i in points], ls='', marker='.',color=color_palette[0])
    texts = []
    for i in points:
        texts.append(axCurve.text(i, dfCurve.loc[i,dt],'{:1.2%}'.format(dfCurve.loc[i,dt]),\
                     fontweight='bold', color=color_palette[0], fontsize=11))
    adjust_text(texts, ax=axCurve, x=list(dfCurve.index)*3, y=list(dfCurve.T.values.flatten()))
    axCurve.yaxis.set_major_locator(mticker.FixedLocator(axCurve.get_yticks()))
    axCurve.set_yticklabels(['{:3.1%}'.format(x) for x in axCurve.get_yticks()])
    axCurve.set_title('Curva Cupom Cambial')
    
    #### Spreads
    locator = mdates.AutoDateLocator(minticks=3, maxticks=8)
    formatter = mdates.ConciseDateFormatter(locator, formats=['%Y', '%b-%y', '%d', '%H:%M', '%H:%M', '%S.%f'], show_offset=False)
    # axSpread1.xaxis.set_major_locator(locator)
    # axSpread1.xaxis.set_major_formatter(formatter)
    # axSpread1.xaxis.set_minor_locator(mdates.MonthLocator(interval=1))

    axSpread1.set_title('Cupom Cambial x (CDS Brazil + OIS)')
    dfRates = dfRates.loc[datetime.date(2019,1,1):]
    for ax, y in zip([axSpread1, axSpread2, axSpread5],['1Y', '2Y', '5Y']):
        # ax.set_ylabel(y, rotation=0)
        txt_crv1 = 'CDS BR + OIS {}'.format(y)
        txt_crv2 = 'CC {}'.format(y)
        ax.plot(dfRates.index, dfRates[txt_crv1], label=txt_crv1, color=color_palette[0])
        ax.plot(dfRates.index, dfRates[txt_crv2], label=txt_crv2, color=color_palette[1])
        ax.set_xlim(left=dfRates.index[0], right=dfRates.index[-1])
        ax.legend(fontsize=9)
        ax.yaxis.set_major_locator(mticker.FixedLocator(ax.get_yticks()))
        ax.set_yticklabels(['{:1.1%}'.format(x) for x in ax.get_yticks()], fontsize=9)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)
        ax.xaxis.set_minor_locator(mdates.MonthLocator(interval=1))
        texts = []
        spread1 = dfRates[txt_crv1].iloc[-1]
        spread2 = dfRates[txt_crv2].iloc[-1]
        va = ['bottom', 'top'] if spread1>spread2 else ['top', 'bottom']
        texts.append(ax.text(dfRates.index[-1], spread1,
                             ' {:1.2%}'.format(spread1), va=va[0],\
                              fontweight='bold', color=color_palette[0], fontsize=9))
        texts.append(ax.text(dfRates.index[-1], spread2,
                             ' {:1.2%}'.format(spread2), va=va[1],\
                              fontweight='bold', color=color_palette[1], fontsize=9))
        # adjust_text(texts, ax=ax)
        
    for ax in [axFRCrate,axFRC,axCurve, axSpread1, axSpread2, axSpread5]:
        ax.grid(ls='--', which='both')
    
    fig_file = os.path.expanduser('~\\Documents\\Github\\market_data\\report') + '/temp_figs/{:%Y%m%d}_curva_cp_cambial.svg'.format(dt)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    
    wb = xw.Book(report_filename)
    # wb.sheets('US_rates').pictures.add(wb.api.Path + '/../' + fig_file, name='marketdata_cpCambial', update=True) 
    wb.sheets('US_rates').pictures.add(fig_file, name='marketdata_cpCambial', update=True) 
    
#%%    
if __name__ == "__main__":

    dt = marketdata_config.get_config('dt')
    report_filename = 'xls/MarketData_model.xlsm'
    
    main(dt, report_filename) 
    