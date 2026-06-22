import pandas as pd
import numpy as np
import datetime
import dateutil
import timeit
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.gridspec as gridspec
import matplotlib as mpl
import xlwings as xw
import fund_utils as fu
import QuantLib as ql

#%%
def main(dt, str_fund, report_filename, print_pdf=False): 
    #%%
    _, connection = fu.get_DB_conn('prod')
    
    
    str_sql = """
       SELECT p.lote45_product_class, p.lote45_product, cast (p.date_maturity as datetime) as vcto ,[contratos_em_aberto]
       FROM [b3].[contrato_aberto] c 
           INNER JOIN middle.product p ON p.id = (c.[mercadoria] + [vencimento])
           WHERE c.date_reference = '{:%Y-%m-%d}'
           order by 1,3 desc
    """
    dfB3 = pd.read_sql( str_sql.format(dt), connection, index_col='lote45_product')
    
    # use D-1 if data is not available
    if len(dfB3) == 0:
        str_sql = str_sql.format(ql.Brazil().advance(ql.Date.from_date(dt), ql.Period('-1d')).to_date())    
        dfB3 = pd.read_sql( str_sql, connection, index_col='lote45_product')
    
    str_sql = """
    SELECT max([date_reference]) as dt, p.lote45_product_class, p.lote45_product , cast (p.date_maturity as datetime) as vcto , 
            AVG([value]) avg1month, COUNT([value]) numdata
    FROM [risk].[product_sensitivity] ps INNER JOIN middle.product p ON ps.product_id = p.id
    WHERE ps.sensitivity = 'qtde_negociada' 
        AND p.date_maturity >= '{0:%Y-%m-%d}'
    	AND ps.date_reference BETWEEN DATEADD(DAY, -42, '{0:%Y-%m-%d}') AND '{0:%Y-%m-%d}'
    GROUP BY p.lote45_product_class, p.lote45_product, p.date_maturity
    """
    dfB3Avg = pd.read_sql( str_sql.format(dt), connection, index_col='lote45_product')
    dfAuxFRCAvg = dfB3Avg[dfB3Avg['lote45_product_class']=='FRC'][['vcto','avg1month']].set_index('vcto').copy()
    dfB3Avg = dfB3Avg.join(dfAuxFRCAvg, on='vcto', rsuffix='_frc')
    dfB3Avg.loc[dfB3Avg['lote45_product_class']=='DDI Future', 'avg1month'] = dfB3Avg['avg1month_frc']
    del dfAuxFRCAvg
    
    
    str_sql = """
                SELECT [lote45_product],sum([value]) as qty
                FROM [lote45].[book_overview]
                WHERE date_reference = '{:%Y-%m-%d}' and trading_desk = '{}' and measure = 'amount'
                GROUP BY [lote45_product]
             """
    str_sql = str_sql.format(dt, str_fund)    
    dfPosition = pd.read_sql(str_sql, connection, index_col='lote45_product')
    
    str_sql = """
    SELECT bo.lote45_product_class, bo.[lote45_product], p.date_maturity, sum([value]) as qty
    FROM [lote45].[book_overview] bo LEFT JOIN middle.product p ON bo.lote45_product = p.lote45_product
    WHERE date_reference = '{:%Y-%m-%d}' and trading_desk = '{}'  and measure = 'amount'
    and bo.lote45_product_class in ('DDI Future', 'SCS')
   GROUP BY bo.lote45_product_class, bo.[lote45_product], p.date_maturity
             """
    str_sql = str_sql.format(dt, str_fund)    
    df = pd.read_sql(str_sql, connection)
    dfDDI = df[df['lote45_product_class']=='DDI Future'].set_index('date_maturity')
    dfSCS = df[df['lote45_product_class']=='SCS'].set_index('date_maturity')
    dfDDI = dfDDI.join(dfSCS['qty'], lsuffix='_ddi', rsuffix='_scs').fillna(0)
    
    str_sql = """
SELECT bo.[lote45_product], sum([value]) as qty
  FROM [lote45].[book_overview] bo 
   WHERE date_reference = '{:%Y-%m-%d}' and trading_desk = '{}' and measure = 'amount'
   and bo.lote45_product_class ='SCS TERM'
   GROUP BY bo.[lote45_product]
             """
    str_sql = str_sql.format(dt, str_fund)    
    df = pd.read_sql(str_sql, connection, index_col='lote45_product')
             
    str_sql = """
        SELECT p.lote45_product, p.date_maturity as dt2, u.date_maturity as dt1, 1 as qty1,
                -1/(1+t.tx*datediff(day, p.date_maturity, u.date_maturity)/360) qty2
                FROM [middle].[product] p 
        	INNER JOIN middle.product u 
        		ON p.product_underlying = u.id
            INNER JOIN	(SELECT pp.date_reference, p.date_maturity, pp.rate/100 as tx
    					FROM [middle].[product_price] pp INNER JOIN middle.product p ON pp.product_id = p.id
    					WHERE p.product_type = 'FRC' AND date_reference >= '{0:%Y-%m-%d}') t
    		    ON t.date_maturity = u.date_maturity
        WHERE p.product_type ='SCS TERM' AND  p.date_maturity > '{0:%Y-%m-%d}'
        AND t.date_reference = '{0:%Y-%m-%d}'
    """
    str_sql = str_sql.format(dt)
    dfSCSTerm = pd.read_sql(str_sql, connection, index_col='lote45_product')
    df = df.join(dfSCSTerm)
    df['qty1'] *= df['qty']
    df['qty2'] *= df['qty']
    df = df.reset_index()
             
    dfDDI = dfDDI.join(df[['dt1','qty1']].set_index('dt1').groupby('dt1').sum()).fillna(0)
    dfDDI = dfDDI.join(df[['dt2','qty2']].set_index('dt2').groupby('dt2').sum()).fillna(0)
    
    if 'qty1' in dfDDI.columns:
        dfDDI = dfDDI.set_index('lote45_product')[['qty_ddi', 'qty_scs', 'qty1', 'qty2']].sum(axis=1)
    else:
        dfDDI = dfDDI.set_index('lote45_product')[['qty_ddi', 'qty_scs']].sum(axis=1)

    
    connection.close()
    del str_sql, connection
    
    #%%
    color1, color2 = '#323E48', '#28829B'
    cmap = mpl.cm.get_cmap('coolwarm', 20)

    perc = 0.2
    min_open = 10_000.0
    # replace DDI for sum of DDI, SCS and SCS TERM
    dfPosition.loc[dfDDI.index, 'qty'] = dfDDI    
   
    dfOutput = dfB3.join(dfPosition, on='lote45_product').fillna(0)
    dfOutput['limite'] = np.maximum(dfOutput['contratos_em_aberto'] * perc, min_open)
    dfOutput['usage'] = dfOutput['qty'].abs() / dfOutput['contratos_em_aberto'] 
    
    dfOutput = dfOutput.join(dfB3Avg['avg1month'])
    threshold = 0.20
    dfOutput['%'] = dfOutput['qty']/(dfOutput['avg1month'])
    dfOutput['days_to_liquidate'] = (dfOutput['%'].fillna(0) / threshold).apply(lambda x: int(abs(x))+1)
    dfOutput.to_excel('../output/temp_figs/{:%Y%m%d}_liq_b3_fut.xlsx'.format(dt))
    
    #%%
    dfOutput['date_delta']= dfOutput['vcto'].apply(lambda x: dateutil.relativedelta.relativedelta(x, dt))
    dfOutput['semester'] = dfOutput['date_delta'].apply(lambda x: ((x.years*12+x.months)//6)/2)
    dfOutputSemester = dfOutput.groupby(['lote45_product_class','semester'])[['contratos_em_aberto','qty']].apply(lambda x: np.sum(np.abs(x))).reset_index()
    dfOutputSemester['usage'] = dfOutputSemester['qty'].abs()/dfOutputSemester['contratos_em_aberto']
    dfOutputSemester['max'] = 1/3
    dfOutputSemester['str_semester']= dfOutputSemester['semester'].apply(lambda x: '<6M' if x==0 else '6M' if x==0.5 else '{:1.1f}y'.format(x))
    #%%
    
    for p in dfOutput['lote45_product_class'].unique():
        if p in ['IBOVSPFuture', 'USDBRLFuture']:
            h = 4
            tail = 5
            bbox_y = -0.2
        elif p in ['S&P500 Futures - BMF', 'US T-Note 10 BMF']:
            h=1.5
            tail=2
            bbox_y= -0.5
        else:
            h = 10
            tail = 15
            bbox_y = -0.06
        fig, (ax, ax2, ax3) = plt.subplots(1,3, sharey=True, figsize=(4, h),
                                           gridspec_kw={'width_ratios': [2, 6, 1]})
        plt.tight_layout(pad=0)
        plt.subplots_adjust(wspace=0)
        top10 = list(dfOutput[(dfOutput['lote45_product_class']==p)].sort_values(by='contratos_em_aberto').tail(tail).index)
        dfTemp = dfOutput[(dfOutput['lote45_product_class']==p)&((dfOutput['qty']!=0)|(dfOutput.index.isin(top10)))]
        
        dfTemp['limite'].plot.barh(ax=ax, legend=False, zorder=3, color='None', \
                                 edgecolor=color1, linewidth=2, label='{:1.0%} Open Contracts/ Min. {:1,.0f}'.format(perc, min_open))
        dfTemp['qty'].abs().plot.barh(ax=ax, legend=False, zorder=2, color=color2, alpha=0.8, label='Asset1')
        dfTemp['usage'].plot.barh(ax=ax2, legend=False, zorder=2, color=color2, alpha=0.1)
        ax.legend(loc='lower center', bbox_to_anchor=(1.9, bbox_y),
                          ncol=2, fancybox=True, shadow=True)
        ax.set_ylabel('', fontsize=14)
        
        ticks_loc = ax.get_xticks().tolist()
        ax.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
        ax.set_xticklabels(['{:2,.0f}k'.format(i/10**3) for i in ticks_loc])
        
        ax.grid(ls='--', axis='x')
        
        ax2.set_xlim((0,1))
        ax2.set_xticks([])
        ax2.tick_params(axis = "y", which = "both", left = False, right = False)
        ax2.set_title('Asset1  /  B3  /  Usage(%)')
        for i, vcto in enumerate(dfTemp.index):
            qty = dfTemp.loc[vcto, 'qty']
            ax2.text(0.30, i,' {:>9,.0f}'.format(qty) if qty!=0 else ' -', \
                          fontweight='bold', va='center',ha='right',\
                              color=('tomato' if qty<0 else color1)) 
            ax2.text(0.67, i,' {:>12,.0f}'.format(dfTemp.loc[vcto, 'contratos_em_aberto']), \
                          fontweight='bold', va='center',ha='right',\
                              color=color1)
            usg = dfTemp.loc[vcto, 'usage']
            ax2.text(0.98, i,' {:2.1%}'.format(usg), \
                          fontweight='bold', va='center',ha='right',\
                              color=color1 if usg<0.2 else 'grey' , zorder=0,
                              backgroundcolor='None' if (usg<0.2) else 'lightcyan' if (abs(qty)<=min_open) else 'gold' if usg<0.5 else 'lightcoral')
            del usg
            dtl = dfTemp.loc[vcto, 'days_to_liquidate']
            ax3.text(0.5, i,' {:3.0f}'.format(dtl), \
                          fontweight='bold', va='center',ha='center',zorder=0,
                              backgroundcolor=cmap(min(dtl,15)))
        ax3.set_xticks([])
        ax3.tick_params(axis = "y", which = "both", left = False, right = False)
        ax3.set_title('*', fontweight='bold')
        
        if print_pdf:
             fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_b3_{1}_{2}.pdf'.format(dt, str_fund, p)
             fig.savefig(fig_file, bbox_inches = "tight")
                
    
        fig_file = '../output/temp_figs/{:%Y%m%d}_b3_{}_{}.svg'.format(dt, str_fund, p)
        fig.savefig(fig_file, bbox_inches = "tight")
        plt.show()
        wb = xw.Book(report_filename)
        wb.sheets('B3Fut').pictures.add(wb.api.Path + '/' + fig_file, name=p, update=True)
        # wb.sheets('B3Fut').pictures.add(fig, name=p, update=True)
#%%
    fig = plt.figure(figsize=(11, 7), tight_layout=True)
    gs = gridspec.GridSpec(2, 4)#, height_ratios=[3,2], width_ratios=[4,3,2])
    
    axDI = fig.add_subplot(gs[:, 0])
    axDAP= fig.add_subplot(gs[:, 1])
    axDDI= fig.add_subplot(gs[:, 2])
    axDOL= fig.add_subplot(gs[0, 3])
    axIND= fig.add_subplot(gs[1, 3])
    
    for ax, prod in zip([axDI, axDAP, axDDI, axDOL, axIND],
                        ['DI1Future','DAP Future','DDI Future','USDBRLFuture','IBOVSPFuture']):
        dfTemp = dfOutputSemester[dfOutputSemester['lote45_product_class']==prod].set_index('str_semester').sort_values('semester',ascending=False)
        ax.set_title('{}\nUsage | Asset1* | Open Interest*'.format(prod), fontsize=10)
        dfTemp['usage'].plot.barh(ax=ax, color=color2, alpha=0.4)
        dfTemp['max'].plot.barh(ax=ax, color='None', edgecolor=color1,  zorder=3)
        for i, (cont, qty, v) in enumerate(dfTemp[['contratos_em_aberto', 'qty', 'usage']].values):
            color='red' if (v>1/3) else color1 if (v<0.3) else 'gold'
            ax.text(1/3, i, ' {:1.1%}'.format(v) if v!=0 else ' -', ha='left', va='center',
                    color=color, fontweight='bold')
            ax.text(0.88, i, ' {:1,.1f}'.format(qty/1000) if qty!=0 else ' -', ha='right', va='center',
                    color=color, fontweight='normal')
            ax.text(1.2, i, '{:1,.0f} '.format(cont/1000) if cont!=0 else ' -', ha='right', va='center',
                    color=color, fontweight='normal')
        
        # dfTemp['contratos_em_aberto'].plot.barh(ax=ax,logx=True, color='None', edgecolor=color1)
        ax.grid(ls='--', axis='x')
        ax.set_xlim(right=1.2)
        ax.set_xticks([0, 1/3])
        ax.set_xticklabels(['{:1.0%}'.format(x) if x!=0 else '-' for x in ax.get_xticks()])
        ax.set_ylabel('')
        
    fig_file = '../output/temp_figs/{:%Y%m%d}_b3_concentration_limit.svg'.format(dt)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    wb = xw.Book(report_filename)
    wb.sheets('B3Rolagem').pictures.add(wb.api.Path + '/' + fig_file, name='B3_concent_limit', update=True)
    # wb.sheets('B3Rolagem').pictures.add(fig, name='B3_concent_limit', update=True)
    dfOutput[dfOutput['lote45_product_class']=='DDI Future'].sort_values('vcto')[['contratos_em_aberto','avg1month']].to_excel('../../cupom_cambial/output/{:%Y%m%d}_contratos_abertos.xlsx'.format(dt))
#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt, str_fund = fu.get_config(['dt', 'str_fund'])
    report_filename = '../xls/RiskMap_model.xlsm'
    
    main(dt, str_fund, report_filename, (dt.weekday()==4)) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))
    
