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


#%%
def main(dt, str_fund, nav, report_filename, print_pdf=False): 
#%%
    _, connection = fu.get_DB_conn()
    
    str_sql = """
    SELECT p.id as product_id, qtsv.date_reference, qtsv.value as turnover     
      FROM [quant].[time_series] as qts 
    	INNER JOIN middle.product as p ON qts.entity_id = p.entity_id
    	INNER JOIN [quant].[time_series_value] as qtsv ON qtsv.series_id = qts.id
      WHERE qtsv.date_reference >= '{:%Y-%m-%d}' 
           and qts.field = 'TURNOVER' 
           and qts.source = 'bloomberg'
    """ 
    str_sql = str_sql.format(dt-datetime.timedelta(93))
    df = pd.read_sql(str_sql, connection)
    dfTO = df.pivot(index='date_reference', columns='product_id', values='turnover')
    ipo = []
    for col in dfTO.columns:
        dfTO.loc[dfTO[col].first_valid_index(), col] = np.nan
        if dfTO[col].count()<=21:
            ipo.append(col)
    
    str_sql = """
    SELECT  id,[measure],sum([value]) as val
      FROM [lote45].[book_overview] bo LEFT JOIN middle.product p ON bo.lote45_product = p.lote45_product
      WHERE bo.trading_desk = '{}' and bo.date_reference = '{:%Y-%m-%d}' and p.product_type = 'Equity'
      AND measure in ('Amount', 'Position')
      GROUP BY id,[measure]
    """ 
    str_sql = str_sql.format(str_fund, dt)
    df = pd.read_sql(str_sql, connection)
    dfPos = df.pivot(index='id', columns='measure', values='val')
    if 'Amount' not in dfPos.columns:
        dfPos['Amount'] = 0
    
    str_sql = """
    SELECT [code] FROM [b3].[ibovespa_composition] WHERE [date_reference] = '{}' ORDER BY 1
    """ 
    str_sql = str_sql.format(dt)
    df = pd.read_sql(str_sql, connection)
    dfIBOV_list = df['code'].tolist()
    
    connection.close()
    del str_sql
    #%%
    dfAvgVol = pd.DataFrame (columns=dfTO.columns)
    dts = [30, 60, 90]
    for dti in dts:
        dfAvgVol.loc[dti] = dfTO.loc[(dt - datetime.timedelta(dti)):].mean()
    
    dfPos['%NAV'] = dfPos['Position']/nav
    dfPos = dfPos.join(dfAvgVol.T, how='left')
    dfPos['%'] = dfPos['Position']/dfPos[90]
    threshold = 0.15
    dfPos['days_to_liquidate'] = (dfPos['%'].fillna(0) / threshold).apply(lambda x: int(abs(x))+1)
    dfPos.sort_index(ascending=False, inplace=True)
    dfPos.to_excel('../output/temp_figs/{:%Y%m%d}_{}_liq_b3_eqty.xlsx'.format(dt, str_fund))
    
    dfPos['inIBOV'] = list(dfPos.index)
    dfPos['inIBOV'] = dfPos['inIBOV'].apply(lambda x: 1 if x in dfIBOV_list else 0)
    
    #
    ##### O DataFrame dfPos contém os papéis pertencentes ao índice na última coluna.
    # return dfPos
    #
    
    dic_names_liq = {}
    list_name = []
    for t in [10*10**6, 20*10**6]:
        dic_names_liq[t] = set(dfPos[dfPos[30] < t].index) - set(list_name)
        list_name += list(dfPos[dfPos[30] < t].index)
    
    #%%
    max_liq_days = dfPos['days_to_liquidate'].max()
    dfLiquidation = pd.DataFrame(index=range(max_liq_days+ 1), columns=dfPos.index)
    dfLiquidation.loc[0] = dfPos.loc[dfLiquidation.columns, 'Position']    
    for index in dfLiquidation.index[1:]:
        for c in dfLiquidation.columns:
            val_ant = dfLiquidation.loc[index-1, c]
            if val_ant > 0:
                dfLiquidation.loc[index, c] = max([val_ant - dfPos.loc[c,90] * threshold, 0])
            else:
                dfLiquidation.loc[index, c] = min([val_ant + dfPos.loc[c,90] * threshold, 0])
    
    
    #%%
    longs = list(dfPos[dfPos['Amount']>0].index)
    shorts = list(dfPos[dfPos['Amount']<0].index)
    in_ibov = list(dfPos[dfPos['inIBOV']==1].index)
    not_ibov = list(dfPos[dfPos['inIBOV']!=1].index)
    
    dfLiquidation['Long_Ibovespa'] = dfLiquidation[set(longs) & set(in_ibov)].sum(axis=1)
    dfLiquidation['Short_Ibovespa'] = dfLiquidation[set(shorts) & set(in_ibov)].sum(axis=1)
    dfLiquidation['Long_not_Ibovespa'] = dfLiquidation[set(longs) & set(not_ibov)].sum(axis=1)
    dfLiquidation['Short_not_Ibovespa'] = dfLiquidation[set(shorts) & set(not_ibov)].sum(axis=1)
    
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True, gridspec_kw={'width_ratios': [2, 3]})
    plt.tight_layout(pad=0)
    dfPlot = (dfLiquidation[['Long_Ibovespa', 'Short_Ibovespa','Long_not_Ibovespa','Short_not_Ibovespa']]/nav)
    ax=axes[0]
    dfPlot.loc[:5].plot.area(ax=ax, color=['#28829B','red', 'lightblue','tomato'], legend=False)
    ax.set_xlim(left=0, right=5)    
    ax.grid(ls='--')
    ax.yaxis.set_major_locator(mticker.MultipleLocator(0.01))
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax.set_title('Liquidity Profile - 5 days')
    for i, ha in zip([1, min([5, max_liq_days])],['left', 'right']):
        val_long = dfPlot.loc[i, ['Long_Ibovespa', 'Long_not_Ibovespa']].sum()
        vol_short = dfPlot.loc[i, ['Short_Ibovespa', 'Short_not_Ibovespa']].sum()
        ax.text(i, val_long, '{:2.1%}'.format(val_long), va='bottom', ha=ha, color='#323E48', fontweight='bold')
        ax.text(i, vol_short, '\n{:2.1%}'.format(vol_short), va='top', ha=ha, color='red', fontweight='bold')
       
        
    ax=axes[1]
    ax.set_title('Liquidity Profile - {:1.0f} days'.format(len(dfPlot)))
    dfPlot.plot.area(ax=ax, color=['#28829B','red', 'lightblue','tomato'])
    ax.set_xlim(left=0)    
    ax.grid(ls='--')
    ax.legend(ncol=2)
    ax_texts = [10, 20] if max_liq_days>=20 else [5,10] if max_liq_days>=10 else [1, min([5, max_liq_days])]
    for i, ha in zip(ax_texts,['center', 'center']):
        val_long = dfPlot.loc[i, ['Long_Ibovespa', 'Long_not_Ibovespa']].sum()
        vol_short = dfPlot.loc[i, ['Short_Ibovespa', 'Short_not_Ibovespa']].sum()
        ax.text(i, val_long, '{:2.2%}'.format(val_long), va='bottom', ha=ha, color='#323E48', fontweight='bold')
        ax.text(i, vol_short, '\n{:2.2%}'.format(vol_short), va='top', ha=ha, color='red', fontweight='bold')
       
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_b3_eqty_liquidity.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    #%%
    color1, color2 = '#323E48', '#28829B'
    cmap = mpl.cm.get_cmap('coolwarm', 20)
    fig, (axPos, axTO, axLim) = plt.subplots(1, 3, sharey=True, figsize=(11, 16), gridspec_kw={'width_ratios': [2, 3, 2]})
    plt.tight_layout(pad=0)
    plt.subplots_adjust(wspace=0)
    
    dfPos['%NAV'].abs().plot.barh(ax=axPos, legend=False, zorder=2, 
                                  color=(dfPos['%NAV'] > 0).map({True: color2, False: 'tomato'}), 
                                  alpha=0.8, label='Asset1')
    axPos.set_title('Position (% NAV)')
    axPos.set_ylabel('')
    axPos.grid(ls='--', axis='x')
    axPos.axvline(0, color='k', lw=0.5)
    axPos.set_xlim(left=-axPos.get_xlim()[1]*.4)
    
    ticks_loc = axPos.get_xticks().tolist()
    axPos.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
    axPos.set_xticklabels(['{:2.1%}'.format(i) if i>=0 else '' for i in ticks_loc])
    
    dfPos['Position'].abs().plot.barh(ax=axTO, legend=False, zorder=2, alpha=0.05, 
                                  color=(dfPos['Position'] > 0).map({True: color2, False: 'tomato'}))
    axTO.set_xlim((0,1))
    axTO.set_xticks([])
    dfPos['days_to_liquidate'].abs().plot.barh(ax=axLim, legend=False, zorder=2, alpha=0.05,
                                               color=(dfPos['Position'] > 0).map({True: color2, False: 'tomato'}))
    axLim.set_xlim((0,1))
    axLim.set_xticks([])
    for i, eqty in enumerate(dfPos.index):
        axPos.text(0, i, '{:5.2f} '.format(dfPos.loc[eqty,'%NAV']*100), ha='right', va='center',
                   fontweight='bold', color=color2 if dfPos.loc[eqty,'%NAV']>0 else 'tomato')
        qty = dfPos.loc[eqty, 'Position'] / 10**6
        axTO.text(0.25, i,' {:>4,.2f}M'.format(qty) if qty!=0 else ' -', \
                      fontweight='bold', va='center',ha='right',\
                          color=('tomato' if qty<0 else color1)) 
        for j, d in enumerate([30, 60, 90]):
            qty = dfPos.loc[eqty, d] / 10**6
            axTO.text(0.5 + j*0.225, i,' {:>4,.0f}M'.format(qty) if qty!=0 else ' -', \
                          fontweight='normal', va='center', ha='right',\
                              color=('tomato' if qty<0 else color1)) 
        qty = abs(dfPos.loc[eqty, '%'])
        axLim.text(0.35, i,' {:>4,.1%}'.format(qty) if qty!=0 else ' -', \
                      fontweight='bold', va='center',ha='right', color=color1) 
        qty = abs(dfPos.loc[eqty, 'days_to_liquidate'])
        axLim.text(0.7, i,' {:>3.0f}'.format(qty) if qty!=0 else ' -', \
                      fontweight='bold', va='center',ha='right', color=color1, fontsize=8,
                      backgroundcolor=cmap(min(qty,15))) 
        if eqty in ipo:
            axLim.text(0.8, i, ' IPO', \
                      fontweight='bold', va='center',ha='right', color=color1, fontsize=7)
            
    axTO.set_title('Asset1      |                Avg Turnover\n                           30d             60d              90d')
    axLim.set_title('Pos/90d Avg Turnover | Days to Liquidate*', fontsize=10)
    axLim.set_xlabel('*Days to liquidate position\nusing {:2.0%} of last 90d Avg Turnover'.format(threshold), size=9)
    axTO.set_xlabel('\n# Least liquid names: #\n10M: ' + ', '.join(dic_names_liq[10*10**6]) +'\n20M: ' + ', '.join(dic_names_liq[20*10**6]), fontsize=9)
    
    for t in axPos.get_yticklabels():
        if t.get_text() in ipo:
            t.set_fontweight('bold')
            t.set_color('gold')
            t.set_backgroundcolor('grey')
            t.set_fontsize(9)
    
    #%%
    if print_pdf:
         fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_{1}_b3_turnover.pdf'.format(dt, str_fund)
         fig.savefig(fig_file, bbox_inches = "tight")
    
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_b3_turnover.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    
    wb = xw.Book(report_filename)
    wb.sheets('B3Eqty').pictures.add(wb.api.Path + '/' + fig_file, name='b3_eqty', update=True)
    
    
#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    str_fund = 'A1 Master FIM'
    dt, str_fund = fu.get_config(['dt', 'str_fund'])
    report_filename = '../xls/RiskMap_model.xlsm'
    nav = fu.get_NAV(dt, str_fund)
    
    main(dt, str_fund, nav, report_filename, False) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))