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
import var_SwapClp
import var_SwapCop
import var_SwapTiie

sys.path.insert(1,  os.path.expanduser('~\\Documents\\Github\\instruments\\LatamSwap'))
import ClpSwap
import CopSwap


#%%
def main(dt, report_filename):
#%%
    calendar_cl = ClpSwap.CLPHolidays()
    calendar_co = CopSwap.COPHolidays()
    
    today = ql.Date.from_date(dt)
    calendar_br = ql.Brazil()
    latam_calendar = ql.JointCalendar(calendar_br, ql.Mexico(), ql.UnitedStates())
    latam_calendar = ql.JointCalendar(latam_calendar, calendar_cl, calendar_co)
    yesterday = latam_calendar.advance(today, ql.Period(-1, ql.Days), ql.Preceding)
    last_month = latam_calendar.advance(today, ql.Period(-1, ql.Months), ql.Preceding)
    
    connection = SQLConnection().get_connection()
    str_sql = """
                SELECT tsv.date_reference, ts.name as [id], tsv.value/100 as rate --,ts.entity_id
                FROM [quant].[time_series] ts 
            	INNER JOIN [quant].[time_series_entity] tse ON ts.entity_id = tse.id
            	INNER JOIN quant.time_series_value tsv ON tsv.series_id = ts.id
            	INNER JOIN quant.time_series_grouping tsging on tsging.series_id = ts.id
            	INNER JOIN quant.time_series_group tsg ON tsg.id = tsging.group_id
                WHERE tsg.[name] in ('IR SWAP MXN', 'IR SWAP CLP', 'IR SWAP COP') 
                AND tsv.date_reference in ('{:%Y-%m-%d}','{:%Y-%m-%d}') 
    
        """
    str_sql = str_sql.format(dt, yesterday.to_date())
    dfLatam = pd.read_sql(str_sql, connection)
    dfLatam = dfLatam.pivot(index='id', columns='date_reference', values='rate')
 
    #%%
    dfLatam['Change (BPs)']=(dfLatam[dt]-dfLatam[yesterday.to_date()]).fillna(0)*10000
           
    [dfCLP, _] = var_SwapClp.get_data(dt)
    [dfCOP, _] = var_SwapCop.get_data(dt)
    [dfMXN, _] = var_SwapTiie.get_data(dt)
    
    #%%
    curves_id = ['MXN TIIE Zero', 'Swap CLP Zero', 'Swap COP Zero']
    dic_dfCurve = {}
    for id_crv, df, cal in zip(curves_id, [dfMXN, dfCLP, dfCOP], [ql.Mexico(), calendar_cl, calendar_co]):
        dic_curve = {}
        for d in [today, yesterday, last_month]:
            d_adj = latam_calendar.adjust(d, ql.Preceding)
            dic_curve[d.to_date()] = curve_db.get_curve(d_adj.to_date(), id_crv)
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
        
        dic_dfCurve[id_crv] = pd.DataFrame(rts, index=days, columns=[i.to_date() for i in [today, yesterday, last_month]])
        
        # df['curve_rate_d-1'] = df['tenor_date'].apply(lambda x: dic_curve[yesterday.to_date()].zeroRateValue(ql.Date.from_date(x)))
        df['Change (BPs)'] = dfLatam['Change (BPs)'] #(df['curve_rate']-df['curve_rate_d-1'])*10000
        
        df.loc[df['1VaRShift'] < df['Change (BPs)'].abs(), 'outlier'] =  df['Change (BPs)']
        df.sort_values('tenor_date', ascending=False, inplace=True)
       
    #%%
    color_palette =['#323E48','#28829B','#C9CBCB', '#748D9E', '#2E9AB2',\
                    'steelblue', 'slategrey', 'silver', 'lightgrey']
    
    #### PLOT ####    
    fig = plt.figure(tight_layout=True, figsize=(11, 7))
    gs = gridspec.GridSpec(3, 2, width_ratios=[1,2])
    gs1 = gridspec.GridSpecFromSubplotSpec(1, 2, subplot_spec=gs[0,0], width_ratios=[1, 2], wspace=0)
    gs2 = gridspec.GridSpecFromSubplotSpec(1, 2, subplot_spec=gs[1,0], width_ratios=[1, 2], wspace=0)
    gs3 = gridspec.GridSpecFromSubplotSpec(1, 2, subplot_spec=gs[2,0], width_ratios=[1, 2], wspace=0)
   
    plt.tight_layout()
    axMXNrate = fig.add_subplot(gs1[0])
    axMXN = fig.add_subplot(gs1[1], sharey=axMXNrate)
    axMXNCurve= fig.add_subplot(gs[0,1])
    axCLPrate = fig.add_subplot(gs2[0])
    axCLP = fig.add_subplot(gs2[1], sharey=axCLPrate)
    axCLPCurve= fig.add_subplot(gs[1,1])
    axCOPrate = fig.add_subplot(gs3[0])
    axCOP = fig.add_subplot(gs3[1], sharey=axCOPrate)
    axCOPCurve= fig.add_subplot(gs[2,1])
    

    for axCCYrate, axCCY, axCurve, dfCCY, curve_id in [(axMXNrate, axMXN, axMXNCurve, dfMXN, 'MXN TIIE Zero'),
                                                      (axCLPrate, axCLP, axCLPCurve, dfCLP, 'Swap CLP Zero'),
                                                      (axCOPrate, axCOP, axCOPCurve, dfCOP, 'Swap COP Zero')]:
        dfCurve = dic_dfCurve[curve_id]
        #### CCY level, change and VaR ####
        axCCYrate.barh(dfCCY.index, dfCCY['curve_rate'],zorder=3,\
                  alpha=0.2, color=color_palette[1], label='rate(%)')
        for i, vcto in enumerate(dfCCY.index):
            axCCYrate.text(0, i,' {:1.2%}'.format(dfCCY.loc[vcto, 'curve_rate']), \
                          fontweight='bold', va='center', color=color_palette[0])   
        axCCYrate.set_title('Rate')        
        axCCYrate.xaxis.set_major_locator(mticker.FixedLocator(axCCYrate.get_xticks()))
        axCCYrate.set_xticklabels(['{:1.0%}'.format(x) for x in axCCYrate.get_xticks()])
        
        axCCYrate.yaxis.set_major_locator(mticker.FixedLocator(axCCYrate.get_yticks()))
        axCCYrate.set_yticklabels([x.split(' ')[-1] for x in dfCCY.index])
        axCCYrate.set_ylabel(curve_id.replace(' Zero', ''), fontweight='bold')
    
    
        axCCY.barh(dfCCY['Change (BPs)'].index, dfCCY['Change (BPs)'], zorder=2,\
                 alpha=0.5, color=(dfCCY['Change (BPs)'] > 0).map({True: color_palette[1], False: 'tomato'}))
        axCCY.barh(dfCCY.index, dfCCY['outlier'], zorder=3,\
                 alpha=1, color='none', edgecolor='black', hatch="//")
        axCCY.axvline(0, lw=0.75, color='k')    
        for i, vcto in enumerate(dfCCY.index):
            shift = dfCCY.loc[vcto, 'Change (BPs)']
            axCCY.text(max(0, shift), i,' {:+2.0f}'.format(shift) if shift!=0 else ' -', \
                          fontweight='bold', va='center',\
                              color=('tomato' if shift<0 else color_palette[1]))   
        for j in [-1, 1]:
            axCCY.plot(dfCCY['1VaRShift'].values*j, range(0,len(dfCCY)), ls='', marker='|',\
                      markersize=12, c='r', label='VaR', zorder=4)
        axCCY.set_title('Change (BPs) | VaR')
        axCCY.xaxis.set_minor_locator(MultipleLocator(10))
        plt.setp(axCCY.get_yticklabels(), visible=False)
    
        #### Curva ####
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
        axCurve.set_title('Zero Curve')
        
            
        for ax in [axCCYrate, axCCY, axCurve]:
            ax.grid(ls='--', which='both')
    
    fig.align_ylabels()
    fig_file = os.path.expanduser('~\\Documents\\Github\\market_data\\report') + '/temp_figs/{:%Y%m%d}_curva_latam.svg'.format(dt)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    
    wb = xw.Book(report_filename)
    # wb.sheets('US_rates').pictures.add(wb.api.Path + '/../' + fig_file, name='marketdata_latam', update=True) 
    wb.sheets('US_rates').pictures.add(fig_file, name='marketdata_latam', update=True) 
    
#%%    
if __name__ == "__main__":
    
    dt = datetime.date(2022, 6, 6)
    report_filename = 'xls/MarketData_model.xlsm'
    main(dt, report_filename) 
    