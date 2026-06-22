import pandas as pd
import numpy as np
import datetime
import timeit
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import xlwings as xw
import fund_utils as fu


#%%
def main(dt, str_fund, nav, report_filename, print_pdf=False): 
#%%
    benchmark_list = ['SPX','IBVSP']    
    _ , connection = fu.get_DB_conn('prod')
    
    str_sql = """
        SELECT [primitive1],[primitive2],[covar_value]
        FROM [lote45].[covar_matrix]
        WHERE date_reference = '{:%Y-%m-%d}' 
        ORDER BY 1, 2
        """
    str_sql = str_sql.format(dt)
    df = pd.read_sql(str_sql, connection)
    dfCovarDB = df.pivot(index='primitive1', columns='primitive2', values='covar_value').fillna(0)
   
    str_sql = """
    SELECT p.[primitive],sum(p.[delta]) as delta, m.[onshore_risk]
      FROM [lote45].[primitive] p LEFT JOIN [middle].[product] m
      ON p.lote45_product = m.lote45_product
      WHERE date_reference = '{:%Y-%m-%d}' AND primitive_class='Equity' and trading_desk = '{}'
      GROUP BY [primitive], [onshore_risk]
      """
    dfPos_tot = pd.read_sql(str_sql.format(dt, str_fund), connection, index_col='primitive')
    for b, on_off in zip(benchmark_list, [False, True]):
        if b not in dfPos_tot.index:
            dfPos_tot.loc[b, 'delta'] = 0
            dfPos_tot.loc[b, 'onshore_risk'] = on_off
            
    dfPos_tot.rename({'DJ EURO STOXX 50 INDEX':'EURO STOXX'},
                 axis = 0, inplace = True)
    
    str_sql = """
        SELECT [product_id],[b3_sector],[b3_subsector],[b3_segment],[a1_sector] as sector
            FROM [b3].[sector_classification]    
    """    
    dfClassif = pd.read_sql(str_sql, connection, index_col='product_id')
    
    str_sql = """
        SELECT date_reference, s.product_id, s.a1_sector as sector, [pct]/100 as perc
            FROM [b3].[ibovespa_composition] c inner join b3.sector_classification s on c.code = s.product_id
            WHERE date_reference = (SELECT max([date_reference]) FROM [b3].[ibovespa_composition] WHERE date_reference <= '{:%Y-%m-%d}')
              """
    dfIbovComp = pd.read_sql(str_sql.format(dt), connection, index_col='product_id')

    connection.close()
    del str_sql

#%%
    ic_var = 1.64485362695147
    
    # dfSector = dfPos_tot[dfPos_tot['onshore_risk'] == False].merge(dfClassif[['sector']], 
    #                                                               left_index = True, right_index = True).drop('onshore_risk', axis = 1)
    
    dfOff = dfPos_tot[(dfPos_tot['onshore_risk'] == False) & (dfPos_tot.index != 'SPX')].drop('onshore_risk', axis = 1)
    X = dfCovarDB.values
    dfCovar = pd.DataFrame(np.triu(X) + np.tril(X.T, -1), 
                           columns=dfCovarDB.index,
                           index=dfCovarDB.index)
    del X
    
    missing_primitives = [i for i in dfPos_tot.index if i not in dfCovar.index]
    for i in missing_primitives:
        dfCovar[i] = 0
        dfCovar.loc[i] = 0
    w = dfPos_tot['delta'].values
    
    covar = dfCovar[dfPos_tot.index].loc[dfPos_tot.index].values
    var_total = np.sqrt(w.T @ covar @ w) * ic_var
    
    dfPos_tot['beta_cvar'] = (covar @ w) / (w.T @ covar @ w)
    dfPos_tot['cvar'] = dfPos_tot['beta_cvar'] * dfPos_tot['delta'] * var_total / nav * 10_000
    
    dfPos_tot['Equity'] = np.where(dfPos_tot['onshore_risk'] == 1,
                                   'Onshore', 'Offshore')
    
    dfGroup = dfPos_tot.groupby('Equity').sum()[['cvar']]
    
    for equity in dfPos_tot['Equity']:
        dfTemp = dfPos_tot[dfPos_tot['Equity'] == equity]
        w_temp = dfTemp['delta'].values
        covar_temp = dfCovar[dfTemp.index].loc[dfTemp.index].values
        dfGroup.loc[equity, 'VaR'] = np.sqrt(w_temp.T @ covar_temp @ w_temp) * ic_var / nav * 10_000
        
    
    
    #%%
    fig, (ax1, ax2) = plt.subplots(nrows = 2, 
                                   ncols= 1, 
                                   figsize=(4.5, 5),
                                   gridspec_kw = {'height_ratios':[4, 1]})
    plt.tight_layout()
    # plt.subplots_adjust(hspace=0.1, wspace=0.5)
    ax1.pie(dfGroup['VaR'], 
            labels = ['{}\n({:,.1f})'.format(i, a) for i, a in zip(dfGroup.index, dfGroup['VaR'])], 
            shadow = True,
            startangle =30, 
            explode = [0.2,0], 
            colors = fu.color_palette[1:3], 
            textprops = {'weight':'bold', 'size':12, 'ha':'center'},
            labeldistance = 1.1,
            wedgeprops = dict(width = 0.4))
    # ax1.text(0, 0, 'Equity VaR\n{:,.2f}'.format(var_total/nav * 10_000),
    #          ha='center', fontweight = 'bold', fontsize = 11)
    
    
    dfGroup[['cvar']].T.plot.barh(ax=ax2, 
                                  stacked=True, 
                                  legend=False,
                                  alpha=0.9,
                                  color=fu.color_palette[1:3],
                                  zorder=3)
    
    ax2.axvline(0, color='k', ls='-', lw=0.7)
    ax2.grid(ls='--', axis='x')
    ax2.set_yticks([])
    ax2.set_xlim(right=1.1*ax2.get_xlim()[1])
    
    cvar_value_off = dfGroup.loc['Offshore','cvar']
    ax2.text(cvar_value_off,
             0,
             '{:+2.1f} '.format(cvar_value_off),
             color='k' if cvar_value_off>=0 else 'r',
             ha='right',
             va='center',
             fontweight='bold',
             fontsize = 12)
    
    cvar_value_on = dfGroup.loc['Onshore','cvar']
    ax2.text(cvar_value_on + (cvar_value_off if cvar_value_on>0 else 0),
             0,
             '{:+2.1f}'.format(cvar_value_on),
             color='k' if cvar_value_on>=0 else 'r',
             ha='left' if cvar_value_on>0 else 'right',
             va='center',
             fontweight='bold',
             fontsize = 12)

    
    ax1.set_title('Equity VaR ({:,.1f}bps)'.format(var_total/nav * 10_000), 
                  fontweight = 'bold',
                  fontsize = 16)
    ax2.set_title('Component Var (Bps)', 
                  fontweight = 'bold', 
                  fontsize = 15)
    plt.show()
    
    if print_pdf:
        fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_{1}_donut_on_off_equity.pdf'.format(dt, str_fund)
        fig.savefig(fig_file, bbox_inches = "tight")
        
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_donut_on_off_equity.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    
    wb = xw.Book(report_filename)
    wb.sheets('Equity_offshore').pictures.add(wb.api.Path + '/' + fig_file, name='Var_breakdown_equity', update=True)
    
    
    
    # del dfTemp

#%%
    dfOff['delta%'] = dfOff['delta'] / nav
    
    
    fig,ax = plt.subplots(figsize = (6,2.5))
    
    ax.bar(dfOff.index, dfOff['delta%'],
           alpha=0.9,
           color=(dfOff['delta%'] > 0).map({True:fu.color_palette[1],False:'tomato'}),
           zorder=3, 
           width = 0.5)
    if len(dfOff) == 1:
         ax.set_xlim(5,-5)
    ax.grid(ls = '--', axis = 'y')
    plt.xticks(rotation = 90, fontweight = 'bold')
    ax.bar_label(ax.containers[0],labels = [f"{100*n:.2f}%" for n in dfOff['delta%']], fontweight = 'bold')
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1))
    plt.xlabel('')
    
    ax.set_title('Equity Offshore Delta({:.3f}%)'.format(dfOff['delta%'].sum()), 
                  fontweight = 'bold',
                  fontsize = 11)
    ax.set_ylim(top = 1.1*max(ax.get_ylim()), bottom = 1.1*min(ax.get_ylim()))
    plt.show()
    
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_sector_var.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    
    wb = xw.Book(report_filename)
    wb.sheets('Equity_offshore').pictures.add(wb.api.Path + '/' + fig_file, name='Var_sector', update=True)
    
#%%
    dic_image = {0:['equity_breakdown_offshore', 'Equity_offshore'],
                 1:['equity_breakdown', 'Equity']}    
    
    for n in [0,1]:
        
        dfPos = dfPos_tot[dfPos_tot['onshore_risk'] == n]\
            .drop(['onshore_risk', 'cvar','Equity'], axis = 1).copy()
        
    
        w = dfPos['delta'].values
    
        covar = dfCovar[dfPos.index].loc[dfPos.index].values
        var_total = np.sqrt(w.T @ covar @ w) * ic_var
        
        dfPos = dfPos.join(dfClassif)
        dfPos['delta_%'] = dfPos['delta'] / nav
        dfPos['beta_cvar'] = (covar @ w) / (w.T @ covar @ w)
        dfPos['cvar'] = dfPos['beta_cvar'] * dfPos['delta'] * var_total / nav * 10_000
        str_benchmark = benchmark_list[n]
        var_bechmark = dfCovar.loc[str_benchmark,str_benchmark]
        for c in dfPos.index:
            dfPos.loc[c,'beta'] = dfCovar.loc[c, str_benchmark] / var_bechmark
            dfPos.loc[c,'var'] = abs(np.sqrt(dfCovar.loc[c, c]) * ic_var * dfPos.loc[c, 'delta_%'] * 10_000)
    
        dfFundo = pd.DataFrame(columns=['delta_%', 'cvar', 'beta'])
        dfFundo.loc['FUND'] = dfPos[['delta_%', 'cvar']].sum()
        dfFundo.loc['FUND','beta'] = (dfPos['beta'] * dfPos['delta_%']).sum()/dfPos['delta_%'].sum()

#%%
        color1, color2 = fu.color_palette[0:2]
        idx_long = dfPos[dfPos['delta']>=0].drop(str_benchmark, errors='ignore').index
        dfPosLong = dfPos.loc[idx_long].sort_values('delta').copy()
        dfPosLong.loc['TOTAL', 'beta'] = (dfPosLong['beta'] * dfPosLong['delta_%']).sum()/dfPosLong['delta_%'].sum()
        for col in ['delta_%', 'cvar']:
            dfPosLong.loc['TOTAL', col] = dfPosLong[col].sum()
        
        idx_short = dfPos[dfPos['delta']<0].drop(str_benchmark, errors='ignore').index
        dfPosShort = dfPos.loc[idx_short].sort_values('delta', ascending=False).copy()
        dfPosShort.loc['TOTAL', 'beta'] = (dfPosShort['beta'] * dfPosShort['delta_%']).sum()/dfPosShort['delta_%'].sum()
        for col in ['delta_%', 'cvar']:
            dfPosShort.loc['TOTAL', col] = dfPosShort[col].sum()
        
        num_long = len(dfPos.loc[idx_long])
        num_short = len(dfPos.loc[idx_short])
        
        fs = 7 if len(dfPos)>100 else 8 if len(dfPos)>60 else 9
        
        fig, (axL, axS, axI, axF) = plt.subplots(nrows=4, ncols=3, figsize=(10, 10),  sharey='row', sharex='col',
                                 gridspec_kw = {'height_ratios':[num_long+1, num_short+1, 2, 2],
                                                'width_ratios':[3, 1, 1]})
        plt.tight_layout()
        plt.subplots_adjust(hspace=0.05, wspace=0.1)
        
        for ax, dfPlot in zip((axL, axS, axI, axF), (dfPosLong, dfPosShort, dfPos.loc[[str_benchmark]], dfFundo)):
            if len(dfPlot) > 0:
                dfPlot['delta_%'].plot(kind='barh', ax=ax[0], zorder=3,
                                       color=(dfPlot['delta_%'] > 0).map({True: color2, False: 'tomato'}))
                dfPlot['beta'].plot(kind='barh', ax=ax[1], color=color2, zorder=3, alpha=0.25)
                dfPlot['cvar'].plot(kind='barh', ax=ax[2], zorder=3,
                                    color=(dfPlot['cvar'] > 0).map({True: color2, False: 'tomato'}))
                for t in ax[0].get_yticklabels():
                    if t.get_text() in [str_benchmark, 'TOTAL', 'FUND']:
                        t.set_fontsize(12)
                        t.set_weight("bold")   
                    else:
                        t.set_fontsize(fs)
               
                for i, v in enumerate(dfPlot.index):
                    val = dfPlot.loc[v,'delta_%']
                    ax[0].text(max(0, val), i, ' {:5.2f}'.format(val*100) if val !=0 else '  -',
                               va='center', color='r' if val<0 else 'k', fontweight='bold', fontsize=fs)
                    
                    val = dfPlot.fillna(0).loc[v,'beta']
                    ax[1].text(0.8, i, ' {:5.2f}'.format(val) if val !=0 else '  -',
                               va='center', color='r' if val<0 else 'k', fontweight='bold', fontsize=fs)
                    
                    val = dfPlot.fillna(0).loc[v,'cvar']
                    ax[2].text(max(0, val), i, ' {:4.1f}'.format(val) if val !=0 else '  -',
                               va='center', color='r' if val<0 else 'k', fontweight='bold', fontsize=fs)
                    
            for ax_i in ax:
                ax_i.grid(ls='--')
                ax_i.axvline(0, color='k', lw=1, zorder=2)
                ax_i.axhline(len(ax_i.get_yticks())-1.5, color='k', lw=1)
        
        axL[0].set_ylabel('Eqty Long', fontsize=13)
        axL[0].set_title('Delta (% NAV)', fontweight='bold')
        axL[0].set_xlim(right=max(0.15, axL[0].get_xlim()[1]*1.1))
        axL[1].set_title('Beta {}'.format(str_benchmark), fontweight='bold')
        axL[1].set_xlim(right=2)
        axL[2].set_title('CVaR (BPs)', fontweight='bold')
        axL[2].set_xlim(right=max(20, axL[2].get_xlim()[1]*1.25))
        axS[0].set_ylabel('Eqty Short', fontsize=13)
        axI[0].set_ylabel('')
        ticks_loc = axI[0].get_xticks().tolist()
        axI[0].xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
        axI[0].set_xticklabels(['{:1.0%}'.format(x) for x in ticks_loc])
        for ax_i in axF:
            ax_i.set_facecolor('lightgrey')
            
        if print_pdf:
            fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_{1}_{2}.pdf'.format(dt, str_fund, dic_image[n][0])
            fig.savefig(fig_file, bbox_inches = "tight")
        
        fig_file = '../output/temp_figs/{:%Y%m%d}_{}_{}.svg'.format(dt, str_fund, dic_image[n][0])
        fig.savefig(fig_file, bbox_inches = "tight")
        plt.show()
        wb = xw.Book(report_filename)
        wb.sheets(dic_image[n][1]).pictures.add(wb.api.Path + '/' + fig_file, name=dic_image[n][0], update=True)
#%%
        if n == 1:
            delta_ibov = dfPos.loc['IBVSP','delta_%']
            dfIbovComp['delta_%'] = dfIbovComp['perc'] * delta_ibov
            dfIbovComp['col'] = 'delta_ibov_%'
            dfIbovComp[['sector', 'col', 'delta_%']].reset_index()
            
            dfPos['col'] = 'delta_%'
            # dfPos[['sector', 'col', 'delta_%']].reset_index()
            
            dfTempPos = pd.concat([dfPos[['sector', 'col', 'delta_%']].drop('IBVSP').reset_index(),
                       dfIbovComp[['sector', 'col', 'delta_%']].reset_index().rename(columns={dfIbovComp.index.name:'primitive'})])
            
            dfTempPos = dfTempPos.pivot_table(index='primitive', columns='col', values='delta_%').\
                fillna(0).join(dfTempPos[['primitive','sector']].drop_duplicates().set_index('primitive'))
           
            dfPos.loc['IBVSP','sector'] = 'IBVSP'
            try:
                dfTempPos = dfTempPos.iloc[(-dfTempPos['delta_%'].abs()).argsort()]
            except Exception:
                dfTempPos['delta_%'] = 0
                dfTempPos = dfTempPos.iloc[(-dfTempPos['delta_%'].abs()).argsort()]
            
            # if len(dfTempPos[dfTempPos['sector'].isna()]) > 0:
            dfTempPos_filter_index = dfTempPos.copy()
            
        # =============================================================================
            dfTempPos_filter_index = dfTempPos_filter_index.copy().loc[dfTempPos_filter_index.index != 'BOVA11']
        # =============================================================================
            dfTempPos_filter_index = dfTempPos_filter_index.copy().loc[dfTempPos_filter_index.index != 'SPX']
            dfTempPos_filter_index = dfTempPos_filter_index.copy().loc[dfTempPos_filter_index.index != 'NASDAQ 100 INDEX']
            if len(dfTempPos_filter_index[dfTempPos_filter_index['sector'].isna()]) > 0:
                print('!!!!!!!!!!!!!!\n\nFaltam classificar os seguintes ativos:\n')
                print(dfTempPos_filter_index[dfTempPos_filter_index['sector'].isna()])
            else:
                dfTempPos.loc[dfTempPos['sector'].isna(), 'sector'] = 'Others'
            
            # dfCVarSector = dfPos.groupby('sector')['cvar'].sum().reindex(list(dfTempPos['sector'].unique()) + ['IBVSP'])
            num_cols = 4
            fig, axes = plt.subplots(nrows=4, ncols=num_cols, figsize=(10, 14),  sharey=True)
            plt.tight_layout()
            plt.xticks(fontsize=9, rotation=90)
            plt.subplots_adjust(hspace=0.75, wspace=0.05)
            max_y, min_y = 0, 0
            sorted_sectors = dfTempPos.groupby('sector').sum().sum(axis=1).sort_values(ascending=False).index
            for i, sector in enumerate(sorted_sectors):
                col = i % num_cols
                row = i // num_cols
                ax = axes[row, col]
                dfTemp = dfTempPos[(dfTempPos['sector'] == sector) & (dfTempPos['delta_%'] != 0)]['delta_%'].copy()
                dfTemp.loc['Fund'] = dfTempPos[(dfTempPos['sector'] == sector)]['delta_%'].sum()
                dfTemp.loc['BVSP'] = dfTempPos[(dfTempPos['sector'] == sector)]['delta_ibov_%'].sum()
                dfTemp.plot(kind='bar',ax=ax, color=(dfTemp > 0).map({True: color2, False: 'tomato'}), zorder=3)
                for j, v in enumerate(dfTemp.index):
                    val = dfTemp.loc[v]
                    ax.text(j, max(0, val), '{:2.1f}'.format(abs(val)*100) if val !=0 else '-', fontsize=8, zorder=4,
                                   va='bottom', ha='center', color='r' if val<0 else 'k', fontweight='bold',
                                   rotation=90 if len(dfTemp)>9 else 0)
                total_sector = dfTemp.drop('Fund').sum()
                ax.set_title('{} ({:1.1%})'.format(sector, total_sector).replace(' e ','\ne '), size=11, weight='bold', color='r' if total_sector<0 else 'k')
                ax.axhline(0, color='k', lw=0.5)
                ax.grid(ls='--', axis='y', zorder=0)
                max_y = max(max_y, ax.get_ylim()[1])
                min_y = min(min_y, ax.get_ylim()[0])
                # ticks_loc = ax.get_yticks().tolist()
                # ax.yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
                # ax.set_yticklabels(['{:1.1%}'.format(a) for a in ticks_loc], fontsize=10)
                for t in ax.get_xticklabels()[-2:]:
                    t.set_weight('bold')
                ax.set_xlabel('')
                ax.axvline(len(dfTemp)-2.5, ls='-', lw=1, color='k')
        
            ax.set_ylim(top=max_y*1.15)
            ax.set_ylim(bottom=min_y*1.05)
            ax.yaxis.set_major_formatter(mticker.PercentFormatter(1,1)) 
            for j in (range(i+1,12)):
                col = j % num_cols
                row = j // num_cols
                axes[row, col].set_visible(False)
            fig_file = '../output/temp_figs/{:%Y%m%d}_{}_equity_sector_breakdown.svg'.format(dt, str_fund)
            fig.savefig(fig_file, bbox_inches = "tight")
            plt.show()
            wb.sheets('Equity_2').pictures.add(wb.api.Path + '/' + fig_file, name='equity_sector', update=True)
    #%%
    # dfCVarSector.plot.bar(color=(dfCVarSector > 0).map({True: color2, False: 'tomato'}))
#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt, str_fund = fu.get_config(['dt', 'str_fund'])
    report_filename = '../xls/RiskMap_model.xlsm'
    nav = fu.get_NAV(dt, str_fund)
    main(dt, str_fund, nav, report_filename, print_pdf=False) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))