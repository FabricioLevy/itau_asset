import pandas as pd
import QuantLib as ql
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
from adjustText import adjust_text
import xlwings as xw

from a1db.a1sql import SQLConnection

import os, sys
path_var = os.path.expanduser('~\\Documents\\Github')
sys.path.insert(1, path_var + '\\market_data')
import marketdata_config

#%%
def main(dt, report_filename):
#%%    
    calendar_br = ql.Brazil()
    today = ql.Date.from_date(dt)
    # dtIni = datetime.date(2020, 6, 1)
    dtIni = calendar_br.advance(today, ql.Period('-1M')).to_date()
    
    connection = SQLConnection().get_connection()
    
    str_sql = """
                SELECT [date_reference],[curve_name],[tenor],[discount_factor],curve_rate,business_day
                  FROM [risk].[interest_rate_curve]
                WHERE ((curve_name='DI Fut' and tenor in (360, 720, 1800)) OR
                      (curve_name='NTNB Zero' and tenor in (720, 1800)))
            		AND [date_reference] > '2020-1-1'
             """
    df = pd.read_sql(str_sql, connection)
    
    str_sql = """
                SELECT [date_reference],[product_id],[price]
                  FROM [middle].[product_price]
                 where product_id in ('SPX', 'USDBRL', 'IBOV')
            		AND [date_reference] > '2020-1-1'
              """
    df2 = pd.read_sql(str_sql, connection)
    

    #%%
    dfDI_today = df[(df['date_reference']==dt) & (df['curve_name']=='DI Fut')].copy()
    dfDI_today['pv01'] = (dfDI_today['business_day']/252)/(1+dfDI_today['curve_rate'])
    alpha12 = float(dfDI_today.loc[dfDI_today['tenor']==360,'pv01'].values/dfDI_today.loc[dfDI_today['tenor']==720,'pv01'].values)
    alpha15 = float(dfDI_today.loc[dfDI_today['tenor']==360,'pv01'].values/dfDI_today.loc[dfDI_today['tenor']==1800,'pv01'].values)
    alpha25 = float(dfDI_today.loc[dfDI_today['tenor']==720,'pv01'].values/dfDI_today.loc[dfDI_today['tenor']==1800,'pv01'].values)
    del dfDI_today
    #%%
    df['bucket'] = df['curve_name'].apply(lambda x: x.split(' ')[0]) + df['tenor'].apply(lambda x: '_{:1.0f}Y'.format(x/360))
    dfRet = df.pivot(index='date_reference', columns='bucket', values='discount_factor').pct_change()
    dfRet['DI_1Yx2Y'] = dfRet['DI_1Y'] / alpha12 - dfRet['DI_2Y'] 
    dfRet['DI_1Yx5Y'] = dfRet['DI_1Y'] / alpha15 - dfRet['DI_5Y']
    dfRet['DI_2Yx5Y'] = dfRet['DI_2Y'] / alpha25 - dfRet['DI_5Y'] 
    #%%
    dfRet = dfRet.join(df2.pivot(index='date_reference', columns='product_id', values='price').pct_change())
    
    vol = dfRet.ewm(alpha=0.06).std().iloc[-1] * ((252)**(1/2))
    
    dic_risk = {'Curva Pré' : ['DI_1Y', 'DI_2Y', 'DI_5Y'],
                'Juro Real' : ['NTNB_2Y','NTNB_5Y'],
                'Inclinação': ['DI_1Yx2Y', 'DI_1Yx5Y','DI_2Yx5Y'],
                'Equity'    : ['IBOV', 'SPX'],
                'FX'        : ['USDBRL']}
    #%%
    dfRetAcum = (dfRet.fillna(0)+1).cumprod()
    dfRetAcum = dfRetAcum.loc[dtIni:dt]/dfRetAcum.loc[dtIni]-1
    #%%
    colors = list(plt.cm.get_cmap('tab20c').colors )
    
    locator = mdates.AutoDateLocator(maxticks=6)
    formatter = mdates.ConciseDateFormatter(locator, formats=['%b-%y', '%b-%y', '%d', '%H:%M', '%H:%M', '%S.%f'], show_offset=False)
       
    fig, ax = plt.subplots(2,3,figsize=(12, 8))
    plt.tight_layout()
    plt.subplots_adjust(hspace=0.15, wspace=0.20)
    
    ls=['-','--','-.',':']
    dicColor = {}
    for i, (k, v) in enumerate(dic_risk.items()):
        row = i // 3
        col = i % 3
        for j, risk in enumerate(v):
            p = ax[row, col].plot(dfRetAcum[risk], ls=ls[j], label='{} ({:5.1%})'.format(risk, dfRetAcum[risk].iloc[-1]), color=colors[4*i+j])
            dicColor[risk] = p[0].get_color()
        ax[row, col].set_xlim(left=dfRetAcum.index[0])
        ax[row, col].grid(ls='--')
        ax[row, col].axhline(0,color='k',lw=0.5)
        ax[row, col].xaxis.set_major_locator(locator)
        ax[row, col].xaxis.set_major_formatter(formatter)
        ax[row, col].xaxis.set_minor_locator(mdates.MonthLocator(interval=1))
        ax[row, col].xaxis.label.set_visible(False)
        ax[row, col].legend(title='Return (%)')
        ax[row, col].set_title(k)
        ax[row, col].yaxis.set_major_locator(mticker.FixedLocator(ax[row, col].get_yticks().tolist()))
        ax[row, col].set_yticklabels(['{:1.1%}'.format(x) for x in ax[row, col].get_yticks()])
        ax[-1,-1].scatter([], [], c=[colors[4*i+1]], label=k)
        [ax[row, col].get_yticklabels()[i].set_color('red')  if (ax[row, col].get_yticks()[i] < 0 ) else ax[row,col].get_yticklabels()[i].set_color('black') for i in range(len(ax[row,col].get_yticklabels()))]
                                                                                                                                                      
    ax[-1,-1].scatter(vol, dfRetAcum.iloc[-1], s=10, c=[dicColor[k] for k in dfRetAcum], zorder=3)
    ax[-1,-1].set_title('Vol x Return')
    ax[-1,-1].grid(ls='--')
    ax[-1,-1].set_xlabel('Vol (%)')
    ax[-1,-1].set_ylabel('Return (%)')
    row, col = -1, -1
    ax[row, col].yaxis.set_major_locator(mticker.FixedLocator(ax[row, col].get_yticks().tolist()))
    ax[row, col].xaxis.set_major_locator(mticker.FixedLocator(ax[row, col].get_xticks().tolist()))
    ax[row, col].set_xticklabels(['{:1.0%}'.format(x) for x in ax[row, col].get_xticks()])
    ax[row, col].set_yticklabels(['{:1.0%}'.format(x) for x in ax[row, col].get_yticks()])
    [ax[row, col].get_yticklabels()[i].set_color('red')  if (ax[row, col].get_yticks()[i] < 0 ) else ax[row,col].get_yticklabels()[i].set_color('black') for i in range(len(ax[row,col].get_yticklabels()))]
    texts = []
    for risk in dfRetAcum.columns:
        texts.append(ax[-1,-1].text(vol[risk], dfRetAcum[risk].iloc[-1], risk, \
                             fontdict={"size":7, "color":dicColor[risk], "weight":"bold"}))
    adjust_text(texts, ax=ax[-1,-1])
    ax[-1,-1].legend(scatterpoints=1, labelspacing=0.5, title='', fontsize=9)
    
    fig_file = os.path.expanduser('~\\Documents\\Github\\market_data\\report') + '/temp_figs/{:%Y%m%d}_vol.svg'.format(dt)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    
    wb = xw.Book(report_filename)
    # wb.sheets('vol').pictures.add(wb.api.Path + '/../' + fig_file, name='marketdata_vol', update=True) 
    wb.sheets('vol').pictures.add(fig_file, name='marketdata_vol', update=True) 
    
#%%    
if __name__ == "__main__":
    
    dt = marketdata_config.get_config('dt')
    report_filename = 'xls/MarketData_model.xlsm'
    main(dt, report_filename) 
    