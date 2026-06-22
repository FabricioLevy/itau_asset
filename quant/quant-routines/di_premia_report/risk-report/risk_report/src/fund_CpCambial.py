import pandas as pd
import numpy as np
import datetime
import timeit
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import xlwings as xw
import QuantLib as ql
import fund_utils as fu

#%%
def main(dt, str_fund, nav, report_filename): 
    #%%
    cal_b3 = ql.Brazil(ql.Brazil().Exchange)
    dt = cal_b3.adjust(ql.Date.from_date(dt), ql.Preceding).to_date()
    dt_y = cal_b3.advance(ql.Date.from_date(dt), ql.Period('-1d')).to_date()
    color1, color2 = fu.color_palette[0:2]

    _, connection = fu.get_DB_conn('prod')
    
    str_sql = """
    SELECT p.date_maturity, [value] as pv01, pp.price as PU
  FROM [risk].[product_sensitivity] ps INNER JOIN middle.product p ON p.id = ps.product_id
	INNER JOIN middle.product_price pp ON pp.date_reference = ps.date_reference and pp.product_id = p.id
  WHERE ps.date_reference = '{:%Y-%m-%d}' and p.product_type = 'DDI Future' and ps.sensitivity = 'PV01'
  ORDER BY 1
    """
    str_sql = str_sql.format(dt)    
    dfPV01 = pd.read_sql(str_sql, connection, index_col='date_maturity')
    
    str_sql = """
    SELECT [tenor_date],[curve_rate] as rate
  FROM [risk].[interest_rate_curve]
  WHERE date_reference = '{:%Y-%m-%d}' and curve_name = 'USD BR' and tenor is null
  ORDER by tenor_date
    """
    str_sql = str_sql.format(dt)    
    dfRate = pd.read_sql(str_sql, connection, index_col='tenor_date')
    
    dfPV01 = dfPV01.join(dfRate).fillna(0)
    
    str_sql = """
        SELECT p.date_maturity ,  AVG([value]) avg1month, COUNT([value]) numdata
        FROM [risk].[product_sensitivity] ps INNER JOIN middle.product p ON ps.product_id = p.id
        WHERE ps.sensitivity = 'qtde_negociada' 
        	AND ps.date_reference >= DATEADD(MONTH, -1, '{:%Y-%m-%d}')
    		AND p.product_type = 'FRC'
        GROUP BY p.lote45_product_class, p.lote45_product, p.date_maturity
    """
    dfCNG = pd.read_sql(str_sql.format(dt), connection, index_col='date_maturity')
    dfCNG = dfCNG.join(dfPV01)
    dfCNG['avg1month_pv01'] = dfCNG['avg1month'] * dfCNG['pv01']
    dfCNG['avg1month_pv01_pl'] = dfCNG['avg1month_pv01'] / nav * 10000
    
    str_sql = """
    SELECT date_reference, bo.lote45_product_class, bo.[lote45_product], p.date_maturity, sum([value]) as qty
    FROM [lote45].[book_overview] bo LEFT JOIN middle.product p ON bo.lote45_product = p.lote45_product
    WHERE date_reference in ('{:%Y-%m-%d}','{:%Y-%m-%d}') and trading_desk = '{}'  and measure = 'amount'
    and bo.lote45_product_class in ('DDI Future', 'SCS', 'USDBRLFuture')
   GROUP BY date_reference, bo.lote45_product_class, bo.[lote45_product], p.date_maturity
             """
    str_sql = str_sql.format(dt, dt_y, str_fund)    
    dfTemp = pd.read_sql(str_sql, connection)
    
    dic_DDI = {}
    for dt_i in [dt_y, dt]:
        df = dfTemp[dfTemp['date_reference']==dt_i][['date_reference',
                                                     'lote45_product_class',
                                                     'lote45_product',
                                                     'date_maturity', 
                                                     'qty']].copy()
        dfDDI = df[df['lote45_product_class']=='DDI Future'].set_index('date_maturity')
        dfSCS = df[df['lote45_product_class']=='SCS'].set_index('date_maturity')
        dfDDI = dfDDI.join(dfSCS['qty'], lsuffix='_ddi', rsuffix='_scs', how='outer').fillna(0)
        dfDDI['date_reference'] = dt_i
        dfDOL = df[df['lote45_product_class']=='USDBRLFuture'].copy()
        dfDOL['date_maturity'] = dfDOL['date_maturity'].apply(lambda x: cal_b3.advance(ql.Date.from_date(x), ql.Period('1d')).to_date())
        dfDOL['qty_dol'] = - dfDOL['qty'] * dfDOL['lote45_product'].apply(lambda x: 1 if x[0:3]=='DOL' else 0.2)
        dfDDI = dfDDI.join(dfDOL[['date_maturity','qty_dol']].groupby(['date_maturity']).sum()).fillna(0)
        dic_DDI[dt_i] = dfDDI.copy()
    
    str_sql = """
SELECT date_reference, bo.[lote45_product],p.date_maturity as dt1, pu.date_maturity as dt2,
     -sum([value]) as scs_term_curto, sum([value]) as scs_term_longo
  FROM [lote45].[book_overview] bo LEFT JOIN middle.product p ON bo.lote45_product = p.lote45_product
  LEFT JOIN middle.product pu ON p.product_underlying = pu.id
   WHERE date_reference in ('{:%Y-%m-%d}','{:%Y-%m-%d}') and trading_desk = '{}' and measure = 'amount'
   and bo.lote45_product_class ='SCS TERM'
   GROUP BY date_reference, bo.[lote45_product],p.date_maturity,pu.date_maturity
             """
  
    str_sql = """
 SELECT t.date_reference, p.lote45_product, p.date_maturity as dt1, u.date_maturity as dt2,
            round(sum(-1/(1+t.tx*datediff(day, p.date_maturity, u.date_maturity)/360)*bo.[value]),0) as scs_term_curto, 
            sum(bo.[value]) as scs_term_longo
    FROM [middle].[product] p 
    				INNER JOIN middle.product u 
						ON p.product_underlying = u.id
					INNER JOIN	(SELECT pp.date_reference, p.date_maturity, pp.rate/100 as tx
									FROM [middle].[product_price] pp INNER JOIN middle.product p ON pp.product_id = p.id
									WHERE p.product_type = 'FRC' AND date_reference >= '{1:%Y-%m-%d}') t
						 ON t.date_maturity = u.date_maturity
					INNER JOIN [lote45].[book_overview] bo
						ON bo.lote45_product = p.lote45_product and bo.date_reference = t.date_reference
    WHERE p.product_type ='SCS TERM' 
		AND bo. measure = 'amount'
		and bo.trading_desk = '{2:}'
		AND  p.date_maturity > '{1:%Y-%m-%d}'
		AND t.date_reference BETWEEN '{1:%Y-%m-%d}' AND '{0:%Y-%m-%d}'
	GROUP BY t.date_reference, p.lote45_product, p.date_maturity, u.date_maturity
"""
             
    str_sql = str_sql.format(dt, dt_y, str_fund)    
    dfTemp = pd.read_sql(str_sql, connection)  
    for dt_i in [dt_y, dt]:
        df = dfTemp[dfTemp['date_reference']==dt_i][['lote45_product','dt1','dt2','scs_term_curto','scs_term_longo']].copy()
        dic_DDI[dt_i] = dic_DDI[dt_i].join(df[['dt1','scs_term_curto']].set_index('dt1').groupby('dt1').sum()).fillna(0)
        dic_DDI[dt_i] = dic_DDI[dt_i].join(df[['dt2','scs_term_longo']].set_index('dt2').groupby('dt2').sum()).fillna(0)    
        dic_DDI[dt_i] = dic_DDI[dt_i].join(dfPV01).sort_index(ascending=False)
        
    connection.close()
    
    del str_sql, connection, dfSCS, dfDDI, dfTemp, dt_i
    
    #%%
    cols_qty = ['qty_ddi', 'qty_scs', 'qty_scs_term', 'qty_dol']
    for dt_i in [dt_y, dt]:
        dfDDI = dic_DDI[dt_i].copy()
        if 'scs_term_curto' in dfDDI.columns:
            dfDDI['qty_scs_term'] = dfDDI[['scs_term_curto', 'scs_term_longo']].sum(axis=1)
        else:
            dfDDI['qty_scs_term'] = 0
        for col in cols_qty:
            dfDDI['pv01_' + col] = dfDDI['pv01'] * dfDDI[col] / nav * 10000
        dfDDI['pv01_total'] = dfDDI[['pv01_' + col for col in cols_qty]].sum(axis=1)
        dfDDI['qty_total'] = dfDDI[cols_qty].sum(axis=1)
        dic_DDI[dt_i] = dfDDI.copy()
    dfDDI = dic_DDI[dt].copy()
    if len(dfDDI) == 0:
        return False
    else:
        dfDDI.sort_index().to_excel('../../cupom_cambial/output/{:%Y%m%d}_{}_position.xlsx'.format(dt, str_fund))
        dfCompara = pd.concat([dic_DDI[dt_y].reset_index(), dic_DDI[dt].reset_index()])
        dfCompara = pd.melt(dfCompara, value_vars=['qty_ddi', 'qty_scs', 'qty_scs_term', 'qty_total'], id_vars=['date_reference','date_maturity'], var_name='qty')
        dfCompara = dfCompara.pivot(index='date_maturity', columns=['date_reference', 'qty'], values='value').fillna(0)
        if (dt_y,'qty_total') in dfCompara.columns:
            dfCompara[(dt,'Abs Diff')] = dfCompara[(dt,'qty_total')].abs() - dfCompara[(dt_y,'qty_total')].abs()
            dfCompara[(dt,'PV01 Change')] = dfCompara[(dt,'Abs Diff')] * dfPV01['pv01'] 
        
        fig, ax = plt.subplots(1,1, figsize=(16, 8))
        ax.axis('off')
        ax.set_title("Variação Diária de Contratos", fontsize=11, weight='bold')
        dfTable = dfCompara.copy()
        plt_table = ax.table(cellText=dfTable.applymap('{:.0f}'.format).values,
                 rowColours=['silver']*len(dfTable), colColours=['silver']*len(dfTable.columns),
                          rowLabels=['{:%b-%y}'.format(i) for i in dfTable.index],
                          colLabels=['{:%d-%b}\n{}'.format(i,j) for (i,j) in dfTable.columns],loc='center', cellLoc='center')
        
        for i, ind in enumerate(dfTable.index):
            for j, col in enumerate(dfTable.columns):
                my_cell = plt_table[i+1,j]
                if float(my_cell.get_text().get_text())<0:
                    my_cell.get_text().set_color('r')
                elif float(my_cell.get_text().get_text())==0:
                    my_cell.get_text().set_text('-')
        cellDict = plt_table.get_celld()
        for i in range(0,len(dfTable.columns)):
            cellDict[(0,i)].set_height(.08)

        plt.show()
        file3 = '../../cupom_cambial/output/{:%Y%m%d}_{}_reducao_cupom_cambial_3.pdf'.format(dt, str_fund)
        fig.savefig(file3, bbox_inches = "tight")

    #%%
    dt_end = dfDDI.index.max() + datetime.timedelta(days=+30)
    dt_index = [dt + datetime.timedelta(days=+i) for i in range((dt_end - dt).days)]
    dfPlot = pd.DataFrame(index=dt_index)

    dfPlot = dfPlot.join(dfDDI['pv01_total']).fillna(0).sort_index(ascending=False)
    dfPlot = dfPlot.join(dic_DDI[dt_y]['pv01_total'], rsuffix='_yesterday').fillna(0).sort_index(ascending=False)
    
    perc = 0.2
    dfPlotY = dfDDI[['pv01_total']].join(dfCNG['avg1month_pv01_pl']).reset_index()
    dfPlotY = dfPlotY.groupby(dfPlotY['date_maturity'].apply(lambda x: x.year)).sum()
    dfPlotY['days_to_liq'] = np.trunc(dfPlotY['pv01_total'].abs() / (dfPlotY['avg1month_pv01_pl'] * perc))+1
    dfPlotY['avg1month_pv01_pl'] *= dfPlotY['pv01_total'].apply(lambda x: 1 if x>0 else -1)
    
    dfPlot['pv01_acum'] = dfPlot['pv01_total'].cumsum()
    dfPlot['pv01_acum_yesterday'] = dfPlot['pv01_total_yesterday'].cumsum()
    dfPlot['pos'] = dfPlot[dfPlot['pv01_acum']>0]['pv01_acum']
    dfPlot['neg'] = dfPlot[dfPlot['pv01_acum']<0]['pv01_acum']

    dfPlot.sort_index(inplace=True)
    #%%
    locator = mdates.AutoDateLocator(minticks=4, maxticks=10)
    # formatter = mdates.ConciseDateFormatter(locator)
    fig, ax = plt.subplots(1,1,figsize=(11.2, 4.5))  
    ax.set_title('Gap Analysis - Pv01 Cupom Cambial')
    ax.fill_between(dfPlot.index, 0, dfPlot['pv01_acum'], where=dfPlot['pv01_acum']>0, color=color2, alpha=0.5,interpolate =False)
    ax.fill_between(dfPlot.index, 0, dfPlot['pv01_acum'], where=dfPlot['pv01_acum']<0, color='tomato', alpha=0.5,interpolate =False)
    
    ax.plot(dfPlot.index, dfPlot['pos'], color=color2)
    ax.plot(dfPlot.index, dfPlot['neg'], color='tomato')
    
    ax.plot(dfPlot.index, dfPlot['pv01_acum_yesterday'], color='k', ls='--', label='Previous Day')
    ax.legend()
    
    texts = []
    xs, ys = [], []
    for dt_i in dfPV01.index:
        if (dt_i.month==1) & (dt_i in dfPlot.index):
            val = dfPlot.loc[dt_i, 'pv01_acum']
            xs.append(dt_i)
            ys.append(val)
            eq_qty = val / (dfPV01.loc[dt_i,'pv01']/nav*10000)
            # texts.append(ax.text(dt_i, dfPlot.loc[dt_i, 'pv01_acum'], '{:2,.0f}'.format(eq_qty),fontweight='bold'))
    # ax.scatter(xs, ys, marker='o', color='k', zorder=3, label='Qty Eqv DDI')
    # ax.legend()
    # adjust_text(texts)
    ax.set_ylabel('Cumulative PV01 Exposure (x NAV)', fontsize=12)
    ax.set_xlim(left=dt)
    y_min, y_max = ax.get_ylim()
    ax.set_ylim(bottom=min(-0.25, y_min), top=max(0.25, y_max))
    ax.axhline(0, color='k', lw=0.5)
    ax.grid(ls='--', which='major', color='gray')
    ax.grid(ls=':', which='minor')
    ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=None if len(dfPlot)<1825 else [1,4,7,10]))
    ax.xaxis.set_major_locator(locator if len(dfPlot)<400 else mdates.MonthLocator(1) )
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%y'))
    ticks_loc = ax.get_yticks().tolist()
    ax.yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
    ax.set_yticklabels(['{:2.2f}x'.format(x) if x!=0 else '-' for x in ticks_loc])
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_gap_cp_cambial.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    wb = xw.Book(report_filename)
    # wb.sheets('FX_IR').pictures.add(wb.api.Path + '/' + fig_file, name='gap_cpCambial', update=True)
    # wb.sheets('FX_IR').pictures.add(fig, name='gap_cpCambial', update=True)  
    
    #%%
    # del dfPlot
    # ptax = 5.60
    # dfDDI['pu_total'] = dfDDI['qty_total'] * dfDDI['PU'] / (1+dfDDI['rate']) / nav * ptax / 2
    # dfPlot2 = pd.DataFrame(index=dt_index)
    # dfPlot2 = dfPlot2.join(dfDDI['pu_total']).fillna(0).sort_index(ascending=False)
    # dfPlot2['pu_acum'] = dfPlot2['pu_total'].cumsum()
    # dfPlot2['pos'] = dfPlot2[dfPlot2['pu_acum']>0]['pu_acum']
    # dfPlot2['neg'] = dfPlot2[dfPlot2['pu_acum']<0]['pu_acum']
    # dfPlot2.sort_index(inplace=True)
    
    # day_fraction = 1/365
    # dfPlot2['pos_area'] = dfPlot2['pos'].fillna(0).cumsum() * day_fraction 
    # dfPlot2['neg_area'] = dfPlot2['neg'].fillna(0).cumsum() * day_fraction

    #%%
    # fig, ax = plt.subplots(1,1,figsize=(12, 6))  #figsize=(11.2, 4.5)
    # ax.set_title('Gap Analysis - PU Eqv Cupom Cambial - {:%d-%b-%Y}'.format(dt))
    # ax.fill_between(dfPlot2.index, 0, dfPlot2['pu_acum'], where=dfPlot2['pu_acum']>0, color=color2, alpha=0.5,interpolate =False)
    # ax.fill_between(dfPlot2.index, 0, dfPlot2['pu_acum'], where=dfPlot2['pu_acum']<0, color='tomato', alpha=0.5,interpolate =False)
    
    # ax.plot(dfPlot2.index, dfPlot2['pos'], color=color2)
    # ax.plot(dfPlot2.index, dfPlot2['neg'], color='tomato')
    
    # texts = []
    # xs, ys = [], []
    # dt_ant = dfPlot2.index[0]
    # for dt_i in dfPV01.index:
    #     if (dt_i.month==1) & (dt_i in dfPlot2.index):
    #         val = dfPlot2.loc[dt_i, 'pu_acum']
    #         xs.append(dt_i)
    #         ys.append(val)
    #         # texts.append(ax.text(dt_i, dfPlot2.loc[dt_i, 'pu_acum'], '{:2,.3f}x'.format(val),fontweight='bold', color='r' if val<0 else 'k'))
    #         pv01_diff_p = dfPlot2.loc[dt_i, 'pos_area'] - dfPlot2.loc[dt_ant, 'pos_area']
    #         pv01_diff_n = dfPlot2.loc[dt_i, 'neg_area'] - dfPlot2.loc[dt_ant, 'neg_area']
    #         # ax.text(datetime.date(dt_ant.year,6,30), -1, '{:2,.2f}'.format(pv01_diff))
    #         if pv01_diff_p > 0:
    #             ax.annotate('{:2,.2f}'.format(pv01_diff_p), 
    #                         xytext=(datetime.date(dt_ant.year,6,30), +1), textcoords="data",
    #                         xy=(datetime.date(dt_ant.year,6,30), -1), xycoords="data", 
    #                      va="center", ha="center",fontweight='bold',
    #                       bbox=dict(boxstyle="round", fc=color2, alpha=0.4))
    #         if pv01_diff_n < 0:
    #             ax.annotate('{:2,.2f}'.format(pv01_diff_n), 
    #                         xytext=(datetime.date(dt_ant.year,6,30), -1), textcoords="data",
    #                         xy=(datetime.date(dt_ant.year,6,30), -1), xycoords="data", 
    #                      va="center", ha="center",fontweight='bold',
    #                       bbox=dict(boxstyle="round", fc='tomato', alpha=0.4))
                
                
    #         dt_ant = dt_i
    # # ax.scatter(xs, ys, marker='.', color='k', zorder=3, label='PU Eqv DDI')
    # ax.legend([])
    # # adjust_text(texts)
    # ax.set_ylabel('Cumulative PU Exposure (x NAV)', fontsize=12)
    # ax.set_xlim(left=dt)
    # ax.axhline(0, color='k', lw=0.5)
    # ax.grid(ls='--', which='major', color='gray')
    # ax.grid(ls=':', which='minor')
    # ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=None if len(dfPlot)<1825 else [1,4,7,10]))
    # ax.xaxis.set_major_locator(locator)
    # ax.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%y'))
    # ax.yaxis.set_minor_locator(mticker.MultipleLocator(base=0.5))
    # ax.yaxis.set_major_locator(mticker.MultipleLocator(base=1.0))
    # ax.yaxis.set_major_formatter('{x:2.1f}x')

    # fig_file = '../output/temp_figs/{:%Y%m%d}_{}_gap_cp_cambial.pdf'.format(dt, str_fund)
    # fig.savefig(fig_file, bbox_inches = "tight")
    # plt.show()
    
    #%%
    # fig, ax = plt.subplots(1,1,figsize=(11.2, 4.5))  
    # dic_color={}
    # min_i = 0
    # for max_i, c in zip([5,10,15,20],['royalblue', 'cornflowerblue', 'tomato', 'red']):
    #     for j in range(min_i, max_i):
    #         dic_color[j] = c
    #     min_i = j

    # dfPlotY['pv01_total'].plot.bar(ax=ax, zorder=3, color=color2, label='Asset1 PV01 Position')
    # dfPlotY['avg1month_pv01_pl'].plot.bar(ax=ax, zorder=3,  color='None', \
    #                              edgecolor=color1, linewidth=2, label='Avg 1-Month Market PV01')
    # ax.axhline(0, color='k', lw=1)
    # ax.grid(ls='--', axis='y')
    # ax.yaxis.set_major_locator(mticker.MultipleLocator(1))
    # ax.legend()
    
    # ticks_loc = ax.get_yticks().tolist()
    # ax.yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
    # ax.set_yticklabels(['{:2.1f}x'.format(x) if x!=0 else '-' for x in ticks_loc])
    
    # for i, (val, d) in enumerate(dfPlotY[['pv01_total', 'days_to_liq']].values):
    #     ax.text(i, val, "{:1.0f}".format(d), fontweight='bold',
    #             ha='center', va='top' if val<0 else 'bottom',
    #             backgroundcolor=dic_color.get(d,'red'))
        
    
    
    
    #%%
    fig, (axes, axesT) = plt.subplots(2,6,figsize=(10, 2), sharey='row', sharex=True, 
                             gridspec_kw={'width_ratios': [0.75,2,1,1,1,1],
                                          'height_ratios':[len(dfDDI),1]})
    plt.tight_layout(pad=0)
    plt.subplots_adjust(wspace=0.1)
    
    
    for j, c in enumerate(['total'] + cols_qty):
        col = 'pv01_' + c
        ax = axes[j+1]        
        dfDDI[col].plot.barh(ax=ax, legend=False, zorder=3, alpha=0.5,
                                       color=(dfDDI[col] > 0).map({True: color2, False: 'tomato'}))
        ax.axvline(0, color='k', lw=1.5, ls=':')
        
        ax = axesT[j+1]
        val = dfDDI[col].sum()
        ax.barh(['Total'],[val],  zorder=3, alpha=0.5,color=color2 if val>0 else 'tomato')
        ax.text(0, 0, ' {:5.2f}'.format(val) if val !=0 else '  -',
                            va='center', color='r' if val<0 else 'k', fontweight='bold',fontsize=11)
        ax.axvline(0, color='k', lw=1.5, ls=':')
        ax.grid(ls='--')
        
    for i, v in enumerate(dfDDI.index):
        ax = axes[0]
        val = dfDDI.loc[v, 'qty_total']
        ax.text(0, i, ' {:8,.0f}'.format(val) if val !=0 else '  -',
                           va='center', ha='center', color='r' if val<0 else 'k', fontweight='bold')

    
    for i, v in enumerate(dfDDI.index):
        for j, c in enumerate(['total'] + cols_qty):
            col = 'pv01_' + c
            ax = axes[j+1]
            val = dfDDI.loc[v, col]
            ax.text(0, i, ' {:5.2f}'.format(val) if val !=0 else '  -',
                           va='center', color='r' if val<0 else 'k', fontweight='bold',fontsize=11)
      
    axes[0].set_ylabel('')
    axes[0].set_yticklabels(['{:%b-%y}'.format(y) for y in dfDDI.index], fontsize=11, fontweight='bold')
    axes[0].set_facecolor('lightgrey')
    axes[1].set_facecolor('lightgrey')
    axesT[1].set_facecolor('lightgrey')
    
    axesT[1].get_shared_x_axes().remove(axesT[1])
    axesT[0].xaxis.set_visible(False)
    axesT[0].yaxis.set_ticks_position('none') 
    plt.setp(axesT[0].spines.values(), visible=False)
    axesT[0].yaxis.set_major_locator(mticker.FixedLocator(axesT[0].get_yticks()))
    axesT[0].set_yticklabels(['TOTAL'], fontsize=12, fontweight='bold')

    
    for ax, t in zip(axes, ['Contracts','TOTAL', 'DDI', 'SCS', 'SCS TERM', 'DOL']):
        ax.set_title(t, fontweight='bold' if t=='TOTAL' else 'normal')
        ax.grid(ls='--')
        ax.xaxis.set_major_locator(mticker.FixedLocator(ax.get_xticks()))
        ax.set_xticklabels(['{:1.0f}x'.format(x) if x!=0 else '-' for x in ax.get_xticks()])
    
    plt.setp(axes[0].get_xticklabels(), visible=False)
    plt.setp(axesT[0].get_xticklabels(), visible=False)
    
    
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_cp_cambial.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
        
    wb.sheets('FX_IR').pictures.add(wb.api.Path + '/' + fig_file, name='ir_cpCambial', update=True)
    # wb.sheets('FX_IR').pictures.add(fig, name='ir_cpCambial', update=True)   
   
#%%
    
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt, str_fund = fu.get_config(['dt', 'str_fund'])
    
    report_filename = '../xls/RiskMap_model.xlsm'
    nav = fu.get_NAV(dt, str_fund)

    main(dt, str_fund, nav, report_filename) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))