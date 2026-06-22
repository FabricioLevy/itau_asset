import pandas as pd
import numpy as np
import datetime
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import xlwings as xw
import QuantLib as ql

import fund_utils as fu


#%%
def main(dt, str_fund, report_filename, print_pdf=False): 
#%%
    _, connection = fu.get_DB_conn('prod')
    
    cal_b3 = ql.Brazil(ql.Brazil().Exchange)
    dt = cal_b3.adjust(ql.Date.from_date(dt), ql.Preceding).to_date()
    mtd = cal_b3.adjust(ql.Date(1,dt.month, dt.year))
    dt_rol = cal_b3.endOfMonth(mtd).to_date()
    dt_rol_adj = ql.Brazil().endOfMonth(mtd).to_date()
    last_day = cal_b3.advance(ql.Date.from_date(dt_rol), ql.Period('-3d')).to_date()
    dt_d10 = cal_b3.advance(ql.Date.from_date(dt_rol), ql.Period('-10d')).to_date()
    mtd = mtd.to_date()
    
    list_products = ['DDI Future','USDBRLFuture','USDBRLOptionPut','USDBRLOptionCall','SCS','SCS TERM']
    eom_products = ['USDBRLFuture','USDBRLOptionPut','USDBRLOptionCall']
    str_products = "','".join(list_products)
    
    str_sql = """
        SELECT t.date_reference, p.lote45_product, p.date_maturity as dt_curto, u.date_maturity as dt_longo,
                1/(1+t.tx*datediff(day, p.date_maturity, u.date_maturity)/360) q
                FROM [middle].[product] p 
        	INNER JOIN middle.product u 
        		ON p.product_underlying = u.id
            INNER JOIN	(SELECT pp.date_reference, p.date_maturity, pp.rate/100 as tx
    					FROM [middle].[product_price] pp INNER JOIN middle.product p ON pp.product_id = p.id
    					WHERE p.product_type = 'FRC' AND date_reference >= '{0:%Y-%m-%d}') t
    		    ON t.date_maturity = u.date_maturity
        WHERE p.product_type ='SCS TERM' AND  p.date_maturity > '{0:%Y-%m-%d}'
        AND t.date_reference BETWEEN '{0:%Y-%m-%d}' AND '{1:%Y-%m-%d}'
    """
    str_sql = str_sql.format(mtd, dt)
    dfSCSTerm = pd.read_sql(str_sql, connection)
    dfSCSTerm = dfSCSTerm.pivot(index='date_reference', columns='lote45_product', values='q')
    
    str_sql = """
            SELECT [date_reference],[lote45_product],[lote45_product_class],[book],
                [measure],[value]
            FROM [lote45].[book_overview]
            WHERE date_reference BETWEEN '{:%Y-%m-%d}' AND '{:%Y-%m-%d}' 
                AND trading_desk = '{}'  
                AND lote45_product_class in ('{}') and measure in ('Amount', 'USDBRLSpot')
    """    
       
    str_sql = str_sql.format(mtd, dt, str_fund, str_products)
    dfPos = pd.read_sql(str_sql, connection)
    dfPos = dfPos.pivot(index=['date_reference', 'lote45_product', 'lote45_product_class', 'book'], 
                        columns='measure', 
                        values='value').reset_index().fillna(0)
    dfPos.rename({'Amount':'qty', 'USDBRLSpot':'delta_brl'}, axis=1, inplace=True)
    
    str_sql = """
    SELECT p.lote45_product, p.date_maturity, isnull(u.date_maturity,p.date_maturity) as underlying_maturity
      FROM [middle].[product] p LEFT JOIN middle.product u ON p.product_underlying = u.id
      WHERE p.date_maturity > '{:%Y-%m-%d}'
          AND p.lote45_product_class in ('{}')
    """
    str_sql = str_sql.format(mtd, str_products)
    dfProd = pd.read_sql(str_sql, connection, index_col='lote45_product')
    
    str_sql = """
            SELECT DISTINCT [date_reference],[price]*50 as pu
            FROM [middle].[product_price] pp INNER JOIN middle.product p ON pp.product_id = p.id
            WHERE date_reference >= '{:%Y-%m-%d}' AND  date_reference <= '{:%Y-%m-%d}' 
             AND p.lote45_product_class = 'USDBRLFuture' 
             AND p.date_maturity in ('{:%Y-%m-%d}','{:%Y-%m-%d}')
    """
    str_sql = str_sql.format(mtd, dt, dt_rol, dt_rol_adj)
    dfDOL = pd.read_sql(str_sql, connection, index_col='date_reference')
    
    str_sql = """
        SELECT  [date_reference], sum([value]) as qtde_negociada
            FROM [risk].[product_sensitivity] ps INNER JOIN middle.product p ON p.id = ps.product_id
            WHERE 
		   date_reference BETWEEN DATEADD(month, -9,'{0:%Y-%m-%d}') AND '{0:%Y-%m-%d}' AND
		   (p.date_maturity <= DATEADD(month, 7, ps.date_reference) or p.date_maturity is NULL) AND
		   ps.[sensitivity] = 'qtde_negociada' AND
		   p.product_type in ('FRC', 'DR1')
        GROUP BY [date_reference]
    """
    str_sql = str_sql.format(dt)
    dfLiquidez = pd.read_sql(str_sql, connection, index_col='date_reference').sort_index()
    
    str_sql = """
                SELECT [date_reference], sum([delta]) as delta_brl
                    FROM [lote45].[primitive]
                    WHERE date_reference = '{0:%Y-%m-%d}' 
                      and trading_desk = '{1}' 
                      and primitive = 'USDBRLSpot'
                      and ((product_currency='BRL') OR lote45_product_class in ('SCS', 'SCS TERM', 'DDI Future'))
                GROUP BY date_reference
                """
    str_sql = str_sql.format(dt, str_fund)
    delta_usdbl_d0 = pd.read_sql(str_sql, connection, index_col='date_reference').loc[dt, 'delta_brl']
    
    connection.close()
    del str_sql
    #%%
    dfPos = dfPos.join(dfProd, on='lote45_product')
    dfPos = dfPos[dfPos['date_reference'].apply(lambda x: not cal_b3.isHoliday(ql.Date().from_date(x)))]
    #%%
    dfDeltaAux = dfPos[dfPos['lote45_product_class']=='DDI Future'][['date_reference', 'date_maturity', 'qty', 'delta_brl']]
    dfDeltaAux['delta_aux'] = np.round(dfDeltaAux['delta_brl']/dfDeltaAux['qty'],0)
    dfDeltaAux = dfDeltaAux[['date_reference', 'date_maturity', 'delta_aux']].drop_duplicates()
    dfDeltaAux = dfDeltaAux.pivot(index='date_reference', columns='date_maturity', values='delta_aux')
    #%%
    dfPosAux = pd.DataFrame(columns=dfPos.columns)
    for (dtref, prod, book, qty, delta, vcto) in dfPos[dfPos['lote45_product_class']=='SCS TERM'][['date_reference', 'lote45_product', 'book', 'qty', 'delta_brl','date_maturity']].values:
        if not cal_b3.isHoliday(ql.Date.from_date(dtref)):
            q = dfSCSTerm.loc[dtref, prod]
            delta_aux = dfDeltaAux.loc[dtref, vcto]
            qty_aux = round(-qty*q,0)
            scs_term_curto =[ [dtref, prod+' CURTO', 'SCS TERM', book, qty_aux, delta_aux*qty_aux+delta, vcto, vcto]]
            dfPosAux = dfPosAux.append(pd.DataFrame(scs_term_curto, columns=dfPos.columns))
          
    dfPos = pd.concat([dfPos, dfPosAux])
    dfPos = dfPos[dfPos['delta_brl']!=0]
    dfPos['dt_rolagem'] = np.where(dfPos['lote45_product_class'].isin(eom_products), 
                                   dfPos['underlying_maturity'], 
                                   dfPos['underlying_maturity'].apply(lambda x: cal_b3.advance(ql.Date.from_date(x), ql.Period('-1d')).to_date()))
    dfPos.loc[dfPos['dt_rolagem']  == dt_rol_adj, 'dt_rolagem'] = dt_rol
    #%%
    dts = []
    dt_i = ql.Date.from_date(mtd)
    while dt_i <= ql.Date.from_date(dt_rol):
        dts.append(dt_i.to_date())
        dt_i = cal_b3.advance(dt_i, ql.Period("1d"))
    
    products = dfPos['lote45_product_class'].unique()
    dfRolagem = pd.DataFrame(index=dts, columns=dfPos['lote45_product_class'].unique())
    
    for dt_i in dfPos['date_reference'].unique():
        dfTemp = dfPos[dfPos['date_reference']==dt_i].copy()
        dfTemp = dfTemp.groupby(['lote45_product_class','dt_rolagem']).sum().reset_index()
        dfDelta = dfTemp.pivot(index='dt_rolagem', columns='lote45_product_class', values='delta_brl').fillna(0)
        
        dfRolagem.loc[dt_i, 'AfterRolagem'] = dfDelta.loc[~(dfDelta.index==dt_rol)].sum(axis=0).sum()
            
        for col in products:
            if dt_rol in dfDelta.index:
                dfRolagem.loc[dt_i, col] = dfDelta.loc[dt_rol, col] if col in dfDelta.columns else 0
            else:
                dfRolagem.loc[dt_i, col] = 0
                
                
    
    dfRolagem['Total'] = dfRolagem[products].fillna(0).sum(axis=1)
    dfRolagem = dfRolagem.join(dfDOL)
    dfRolagem['Qty'] = (dfRolagem['Total']/dfRolagem['pu']).abs()
    # liq_limit = dfLiquidez['qtde_negociada'].mean()*.2
    dfRolagem = dfRolagem.join(dfLiquidez['qtde_negociada'].rolling(120, min_periods=100).mean().tail(22) * .2)
    x = 1
    for dt_i in reversed(dfRolagem.index):
        if (dt_i >= dt_d10):# & (dt_i <= last_day):
            dfRolagem.loc[dt_i, 'LiqLimite'] = dfRolagem.loc[dt_i,'qtde_negociada']*x
            if (dt_i < last_day):
                x+=1
    
    dfRolagem['DeltaD0'] = np.nan
    dfRolagem.loc[dt, 'DeltaD0'] = delta_usdbl_d0
    #%%
    color1, color2 = fu.color_palette[0:2]
    color=[color1 if i==dt else color2 for i in dts]
    
    fig, (ax1, axD, axL, ax2) = plt.subplots(4, 1, figsize=(11,6), sharex=False,
                                        gridspec_kw={'height_ratios': [4,1,1,4],
                                                     'hspace':0.1})
    
    # plt.tight_layout()
    
    dfRolagem['Total'].plot(kind='bar',ax=ax1, color=color, zorder=3, label='')
    
    axD.axis('off')
        
    # dfRolagem['DeltaD0'].plot(kind='bar',ax=axD, color=color, zorder=3, label='')
    # ax1.axhline(delta_usdbl_d0, ls=":", color='tomato', label='Current FX Delta', zorder=0, alpha=0.6)
    # ax1.legend()
    
    dfRolagem['Qty'].plot(kind='bar',ax=ax2, color=color, zorder=3)
    dfRolagem['qtde_negociada'].plot(kind='bar', ax=axL, color=color1, zorder=3, alpha=0.1)
    
    
    ax1.set_title('B3 USD/BRL FX Position to expire at Month End', fontweight='normal', fontsize=13)
    ax1.set_ylabel('Financial Value\n(M BRL)')
    ax2.set_ylabel('Dol Fut Eqv\n(#contracts x 1,000)')
    axL.set_ylabel('Liquidity\nx\nLimit', fontsize=9, rotation=0, ha='right', va='center')
    axL.set_xlabel('')
       
    ax1.xaxis.set_tick_params(which='both', labelbottom=True)
    ax1.set_xticklabels(['TODAY\nCurr:{:+5,.0f}M\nAfter:{:+5,.0f}M'.format(delta_usdbl_d0/10**6, dfRolagem.loc[dt, 'AfterRolagem']/10**6) if x==dt else '' for x in dfRolagem.index],  rotation=0, fontweight='bold')
    for ax in [axD, axL]:
        ax.set_xticklabels([])
        ax.set_yticklabels([])
    ax2.set_xticklabels(['{:%d-%b}'.format(x) for x in dfRolagem.index])
    
    ax2.axhline(10_000, color='r', lw=1, ls=':', label='10k contr')
    
    ax1.text(dts.index(dt), max([0,dfRolagem.loc[dt,'Total']]), '{:1,.0f}'.format(dfRolagem.loc[dt,'Total']/10**6), 
             ha='center', va='bottom', fontsize=11, fontweight='bold')
    ax2.text(dts.index(dt), dfRolagem.loc[dt,'Qty'], '{:1.2f}k'.format(dfRolagem.loc[dt,'Qty']/10**3), 
             ha='center', va='bottom', fontsize=12, fontweight='bold')
    
    for ax in (ax1, ax2):
        # ax.set_ylim(top=ax.get_ylim()[1]*1.1)
        ax.grid(ls='--', axis='y')
        ax.axhline(0, c='k', lw=0.5)
        for i in dfRolagem.index[-3:]:
            ax.text(dts.index(i), 10000, "\u2718", zorder=5, color='r', alpha=0.5,
             ha='center', va='bottom', fontsize=25, fontweight='bold')    
        
    for i, v in enumerate(dfRolagem.index):
        if v<=dt:
            qt=dfRolagem.loc[v,'qtde_negociada']
            axL.text(i, qt, '{:1.1f}k'.format(qt/1000), zorder=5, color=color1, alpha=1,
                          ha='center', va='top', fontsize=8, fontweight='bold')
            axL.text(i, 10**4, '{:1.1f}k'.format(dfRolagem.loc[v,'LiqLimite']/1000) if (v >= dt_d10) & (v==dt) else '',
                      ha='center', va='bottom', fontsize=8, fontweight='bold', color='r')
        if v == last_day:
            for x in [-0.4, 0.4]:
                ax1.axvline(i+x, color='tomato', ls='--', lw=1.5)
                ax2.axvline(i+x, color='tomato', ls='--', lw=1.5)
        if (v >= dt_d10) & (v <= last_day):
            l = dfRolagem.loc[v, 'LiqLimite']
            y = ax.get_ylim()[1]
            if dfRolagem.loc[v, 'Qty'] >= l: 
                ax2.text(i, y, "\u26a0", zorder=5, color='r', alpha=0.7,
                          ha='center', va='top', fontsize=25, fontweight='bold')  
            
        # elif (v == dt_d1) & (dt == dt_d1):
        #     if dfRolagem.loc[dt,'Qty'] >=75000:
        #         ax2.set_ylim(top=max(100*10**3, ax2.get_ylim()[1]))
        #         ax2.text(i, 80000, "\u26a0", zorder=5, color='r', alpha=0.7,
        #                  ha='center', va='bottom', fontsize=25, fontweight='bold')                
        # elif  (v == dt_d2) & (dt == dt_d2):
        #     if dfRolagem.loc[dt,'Qty'] >=150000:
        #         ax2.set_ylim(top=max(175*10**3, ax2.get_ylim()[1]))
        #         ax2.text(i, 160000, "\u26a0", zorder=5, color='r', alpha=0.9,
        #                  ha='center', va='center', fontsize=25, fontweight='bold')  
                
    ax1.set_ylim(top=max(ax1.get_ylim()[1],0.2*10**9), bottom=min(ax1.get_ylim()[0],-0.2*10**9))
    ticks_loc = ax1.get_yticks().tolist()
    ax1.yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
    ax1.set_yticklabels(['{:2,.0f}'.format(x/10**6) for x in ticks_loc])

    ax2.set_ylim(top=max(ax2.get_ylim()[1],12000))
    ticks_loc = ax2.get_yticks().tolist()
    ax2.yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))    
    ax2.set_yticklabels(['{:2,.0f}'.format(x/10**3) for x in ticks_loc])    
    fig.align_ylabels(axs=[ax1, ax2])
           
    if print_pdf:
        if print_pdf == 'Risk':
            fig_file = '../../risk_committee/tex/{0:%Y_%m}/figuras/{0:%Y%m}_{1}_rolagem.pdf'.format(dt, str_fund)
            fig.savefig(fig_file, bbox_inches = "tight")
        else:
            fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_{1}_rolagem.pdf'.format(dt, str_fund)
            fig.savefig(fig_file, bbox_inches = "tight")
         
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_rolagem.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    
    wb = xw.Book(report_filename)
    # wb.sheets('B3Rolagem').pictures.add(fig, name='rolagem', update=True)
    wb.sheets('B3Rolagem').pictures.add(wb.api.Path + '/' + fig_file, name='rolagem', update=True)
       
#%%
if __name__ == "__main__":
        
    dt, str_fund, print_pdf = fu.get_config(['dt_eom', 'str_fund', 'print_pdf'])
    report_filename = '../xls/RiskMap_model.xlsm'
    main(dt, str_fund, report_filename, print_pdf)
