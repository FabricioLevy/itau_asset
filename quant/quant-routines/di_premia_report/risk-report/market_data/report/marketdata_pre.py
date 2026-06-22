import pandas as pd
import numpy as np
import QuantLib as ql
from adjustText import adjust_text
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.gridspec as gridspec
from matplotlib.ticker import MultipleLocator
import xlwings as xw

from a1db.a1sql import SQLConnection

import os, sys
path_var = os.path.expanduser('~\\Documents\\Github')
sys.path.insert(1, path_var + '\\market_data')
import curve_db
import marketdata_config
 
sys.path.insert(1, path_var)
sys.path.insert(1, path_var + '\\VaR_Simulation\\var_calc')
import var_DIFut


#%%
def main(dt, report_filename):
#%%
    today = ql.Date.from_date(dt)
    calendar_br = ql.Brazil(ql.Brazil().Settlement)
    yesterday = calendar_br.advance(today, ql.Period(-1, ql.Days))
    last_month = calendar_br.advance(today, ql.Period(-1, ql.Months))
    
    first_DI = calendar_br.advance(today, ql.Period('5d')).to_date()    
    
    connection = SQLConnection().get_connection()
    str_sql = "SELECT date_reference, [rate]/100 as cdi FROM [middle].[product_price] "+\
                        "WHERE product_id = 'CDI' AND "+\
                        "date_reference BETWEEN DATEADD(month, -9, '{:%Y-%m-%d}') AND '{:%Y-%m-%d}'".format(dt, dt) +\
                        " ORDER BY 1"
    dfCDI = pd.read_sql(str_sql, connection, index_col='date_reference')  
    
    str_sql = "SELECT [date_effective],[decision],[rate_target],[official_schedule] " +\
                "FROM [research].[monetary_policy_meeting] "+\
                "WHERE country='BRL' and date_effective BETWEEN DATEADD(month, -9, '{:%Y-%m-%d}') AND '{:%Y-%m-%d}'".format(dt, dt) 
    dfpastCOPOM = pd.read_sql(str_sql, connection, index_col='date_effective')          
    
    str_sql = "SELECT [date_effective],[date_reference],[implied_rate]/100 as rate" +\
                " FROM [research].[rate_expectation] "+\
                " WHERE country='BRL' AND date_reference in ('{:%Y-%m-%d}','{:%Y-%m-%d}')".format(dt, yesterday.to_date())
    dfCOPOM = pd.read_sql(str_sql, connection)  
    dfCOPOM = dfCOPOM.pivot(index='date_effective', columns='date_reference', values='rate')
    dfCOPOM = dfCOPOM[dfCOPOM.index>dt]
    
    [dfDI, dfPnl] = var_DIFut.get_data(dt)
    dfDI = dfDI[dfDI['tenor_date']>first_DI]
    
    #%%    
    short_index_list = [i for i in dfDI['tenor_date'] if (i-dt).days<100]
    short_index_list += [i for i in dfDI['tenor_date'] if (i.month in [1,4,7,10]) & (i.year-dt.year<2)]
    short_index_list += [i for i in dfDI['tenor_date'] if (i.month in [1,7]) & (i.year-dt.year>=2) & (i.year-dt.year<5)]
    short_index_list += [i for i in dfDI['tenor_date'] if (i.month == 1) & (i.year-dt.year>=5)]
    short_index_list = sorted(set(short_index_list))
    dfDI = dfDI[dfDI['tenor_date'].isin(short_index_list)].copy()
    dfDI.sort_values('tenor_date', ascending=False, inplace=True)
    
    #%%
    dic_curve = {}
    for d in [today, yesterday, last_month]:
        dic_curve[d.to_date()] = curve_db.get_curve(d.to_date(), 'DI Fut')
        dic_curve[d.to_date()].enableExtrapolation()
    
    dts = []
    rts = []
    # for (i, _) in dic_curve[today.to_date()].nodes():
    #     dts.append(i.to_date())
    #     rts.append((dic_curve[today.to_date()].zeroRateValue(i), 
    #                 dic_curve[yesterday.to_date()].forwardRateValue(today, i),
    #                 dic_curve[last_month.to_date()].forwardRateValue(today, i)))
    
    dts = [calendar_br.advance(today, ql.Period(1, ql.Days))] +\
        [calendar_br.advance(today, ql.Period(x*21, ql.Days)) for x in range(1, 143)]
    
    days = []
    for dt_i in dts:
        days.append(calendar_br.businessDaysBetween(today, dt_i))
        rts.append((dic_curve[today.to_date()].zeroRateValue(dt_i), 
                    dic_curve[yesterday.to_date()].forwardRateValue(today, dt_i),
                    dic_curve[last_month.to_date()].forwardRateValue(today, dt_i)))
    
    dfCurve = pd.DataFrame(rts, index=days, columns=[i.to_date() for i in [today, yesterday, last_month]])
    
    dfDI['curve_rate_d-1'] = dfDI['tenor_date'].apply(lambda x: dic_curve[yesterday.to_date()].zeroRateValue(ql.Date.from_date(x)))
    dfDI['Change (BPs)'] = (dfDI['curve_rate']-dfDI['curve_rate_d-1'])*10000
    
    dfDI.loc[dfDI['1VaRShift'] < dfDI['Change (BPs)'].abs(), 'outlier'] =  dfDI['Change (BPs)']
    
                                                    #%%
    listBusDates = [calendar_br.advance(today, ql.Period(x, ql.Days)).to_date() for x in range(1, 168)]
    dfCDI = dfCDI.join(pd.DataFrame(index=listBusDates, columns=['x']).join(dfCOPOM).fillna(method='ffill'), how='outer').drop('x', axis=1)
    dfCDI.loc[(dfCDI.index>dt) & (dfCDI.index < dfCOPOM.index[0]), dt]=dfCDI.loc[dt, 'cdi']
    dfCDI.loc[(dfCDI.index>dt) & (dfCDI.index < dfCOPOM.index[0]), yesterday.to_date()]=dfCDI.loc[dt, 'cdi']
    
    # dfCDI.loc[dt,[dt,yesterday.to_date()]] = dfCDI.loc[dt,'cdi']
    
    dfCOPOM = dfCOPOM[:dfCDI.index[-1]]
    
    dfChange = dfCDI.diff()*10000
    dfChange = dfChange[(np.abs(dfChange)>0.1).any(axis=1)]
          
    
    #%%
    color_palette =['#323E48','#28829B','#C9CBCB', '#748D9E', '#2E9AB2',\
                    'steelblue', 'slategrey', 'silver', 'lightgrey']
    
    #### PLOT ####    
    fig = plt.figure(tight_layout=True, figsize=(11, 7.5))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1,2])
    gs1 = gridspec.GridSpecFromSubplotSpec(1, 2, subplot_spec=gs[0], width_ratios=[1, 2], wspace=0)
    gs2 = gridspec.GridSpecFromSubplotSpec(2, 1, subplot_spec=gs[1], height_ratios=[2, 3])#, hspace=0.25)
    plt.tight_layout()
    axDIrate = fig.add_subplot(gs1[0])
    axDI = fig.add_subplot(gs1[1], sharey=axDIrate)
    axCurve= fig.add_subplot(gs2[0])
    axCopom= fig.add_subplot(gs2[1])
    
    #### DI level, change and VaR ####
    axDIrate.barh(dfDI.index, dfDI['curve_rate'],zorder=3,\
              alpha=0.2, color=color_palette[1], label='rate(%)')
    for i, vcto in enumerate(dfDI.index):
        axDIrate.text(0, i,' {:1.2%}'.format(dfDI.loc[vcto, 'curve_rate']), \
                      fontweight='bold', va='center', color=color_palette[0])   
    axDIrate.set_title('DI Fut')
    ticks_loc = axDIrate.get_xticks().tolist()
    axDIrate.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
    axDIrate.set_xticklabels(['{:1.0%}'.format(x) for x in ticks_loc])
    
    
    axDI.barh(dfDI['Change (BPs)'].index, dfDI['Change (BPs)'], zorder=2,\
             alpha=0.5, color=(dfDI['Change (BPs)'] > 0).map({True: color_palette[1], False: 'tomato'}))
    axDI.barh(dfDI.index, dfDI['outlier'], zorder=3,\
             alpha=1, color='none', edgecolor='black', hatch="//")
    axDI.axvline(0, lw=0.75, color='k')    
    for i, vcto in enumerate(dfDI.index):
        shift = dfDI.loc[vcto, 'Change (BPs)']
        axDI.text(max(0, shift), i,' {:+2.0f}'.format(shift) if shift!=0 else ' -', \
                      fontweight='bold', va='center',\
                          color=('tomato' if shift<0 else color_palette[1]))   
    for j in [-1, 1]:
        axDI.plot(dfDI['1VaRShift'].values*j, range(0,len(dfDI)), ls='', marker='|',\
                  markersize=12, c='r', label='VaR', zorder=4)
    axDI.set_title('Change (BPs) | VaR')
    axDI.xaxis.set_minor_locator(MultipleLocator(10))
    plt.setp(axDI.get_yticklabels(), visible=False)
    
    #### Curva Pré ####
    axCurve.plot(dfCurve.index, dfCurve[dt], color=color_palette[0], lw=2, label='{:%d-%b-%y}'.format(dt))
    axCurve.plot(dfCurve.index, dfCurve[yesterday.to_date()], color=color_palette[1], ls='--', lw=1.25, label='{:%d-%b-%y}'.format(yesterday.to_date()))
    axCurve.plot(dfCurve.index, dfCurve[last_month.to_date()], color=color_palette[4], ls=':', lw=1.25, label='{:%d-%b-%y}'.format(last_month.to_date()))
    axCurve.legend(title='')
    axCurve.set_xlim(left=0, right=3004)
    axCurve.set_xticks(np.arange(0, 3004, 252))
    # axCurve.set_xlabel('days')
    points = [252, 504, 1260, 2520]
    axCurve.set_xticklabels(['{:1.0f}Y'.format(i/252) if i in points else '' for i in axCurve.get_xticks()])
    axCurve.plot(points, [dfCurve.loc[i,dt] for i in points], ls='', marker='.',color=color_palette[0])
    texts = []
    for i in points:
        texts.append(axCurve.text(i, dfCurve.loc[i,dt],'{:1.2%}'.format(dfCurve.loc[i,dt]),\
                     fontweight='bold', color=color_palette[0], fontsize=11))
    adjust_text(texts, ax=axCurve, x=list(dfCurve.index)*3, y=list(dfCurve.T.values.flatten()))
    ticks_loc = axCurve.get_yticks().tolist()
    axCurve.yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
    axCurve.set_yticklabels(['{:3.1%}'.format(x) for x in ticks_loc])
    axCurve.set_title('Curva Pré')

    
    #### COPOM ####
    axCopom.set_title('COPOM decisions')
    axCopom.plot(dfCDI.index, dfCDI['cdi'], lw=3, color=color_palette[0], label='CDI')
    
    for i in dfChange['cdi'].dropna().index:
        axCopom.text(i, dfCDI.loc[i, 'cdi'], ' {:+2.0f}'.format(dfChange.loc[i, 'cdi']),\
                     va='bottom',color=color_palette[0], fontweight='bold')
    
    for i, dt_i in enumerate([dt, yesterday.to_date()]):
        axCopom.plot(dfCDI.index, dfCDI[dt_i], lw=2, color=color_palette[i], ls='--', alpha=1-i/2, label='{:%d-%b-%y}'.format(dt_i))
    
    texts=[]    
    for j in dfChange[dt].dropna().index:
        axCopom.text(j, dfCDI.loc[j, dt], ' {:+2.0f}'.format(dfChange.loc[j, dt]),\
                     va='bottom',color=color_palette[0], fontweight='bold')
    # for j in dfChange[dt_yesterday].dropna().index:
    #     axCopom.text(j, 1.9/100, ' {:+2.0f}'.format(dfChange.loc[j, dt_yesterday]),\
    #                  va='bottom',color=color_palette[1], fontweight='normal')
    
    axCopom.set_xlim(left=dfCDI.index[0])
    axCopom.set_yticks(np.arange(6.9/100, 15.0/100, 1.0/100), minor=False)
    axCopom.set_yticks(np.arange(6.9/100, 15.0/100, 0.25/100), minor=True)
    axCopom.set_yticklabels(['{:2.2%}'.format(i) for i in axCopom.get_yticks()])
    listCopom = list(dfpastCOPOM.index) + list(dfCOPOM.index)
    axCopom.set_xticks(listCopom)
    axCopom.set_xticklabels(['{:%d\n%b\n%y}'.format(i) for i in listCopom], fontsize=9)
    axCopom.axvline(dt, ls='--', color='tomato')
    axCopom.text(dt, axCopom.get_ylim()[0]+0.001, ' Today', color='tomato', va='bottom', fontweight='bold')
    axCopom.legend()
    
    for ax in [axDIrate,axDI,axCurve, axCopom]:
        ax.grid(ls='--', which='major')
    axCopom.grid(ls=':', which='minor')
    
    fig_file = os.path.expanduser('~\\Documents\\Github\\market_data\\report') + '/temp_figs/{:%Y%m%d}_curva_pre.svg'.format(dt)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    
    wb = xw.Book(report_filename)
    # wb.sheets('BRL_rates').pictures.add(wb.api.Path + '/../' + fig_file, name='marketdata_pre', update=True) 
    wb.sheets('BRL_rates').pictures.add(fig_file, name='marketdata_pre', update=True) 
    
#%%    
if __name__ == "__main__":
    
    dt = marketdata_config.get_config('dt')
    report_filename = 'xls/MarketData_model.xlsm'
    main(dt, report_filename) 
    