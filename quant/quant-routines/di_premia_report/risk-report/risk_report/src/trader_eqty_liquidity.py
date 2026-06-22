import pandas as pd
import numpy as np
import datetime
import timeit
import matplotlib.pyplot as plt
from matplotlib import cm
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
import xlwings as xw
import fund_utils as fu
import squarify
import adjustText


#%%
def main(dt, str_fund, nav, report_filename, plot_vol=False, save_to_db=True, print_pdf=False):
#%%
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
    
    str_tree = 'Traders'
    str_sql = """
       SELECT [parent_tree],[parent_node],[node],[book]
       FROM [lote45].[book_tree]
       WHERE parent_tree = '{}'
                """
    dfTree = pd.read_sql(str_sql.format(str_tree), connection)
    nd = fu.Node(str_tree, dfTree)    
    dic_books = nd.to_inv_dict(str_tree)    

    str_sql = """
    SELECT book,[primitive],sum([delta]) as delta
      FROM [lote45].[primitive]
      where date_reference = '{:%Y-%m-%d}' and primitive_class in ('Equity','Commodity') and trading_desk = '{}'
      GROUP BY [primitive], book
      """
    dfPos = pd.read_sql(str_sql.format(dt, str_fund), connection)
    dfPos['trader'] = dfPos['book'].apply(lambda x: dic_books[x])
    dfPos = dfPos.pivot_table(index='primitive', columns='trader', values='delta', aggfunc=np.sum).fillna(0)
    if 'IBVSP' not in dfPos.index:
        dfPos.loc['IBVSP'] = len(dfPos.columns) * [0]
    
    dfPos['Fund'] = dfPos.sum(axis=1)
    dic_Pos = {}
    for t in dfPos.columns:
        dic_Pos[t] = dfPos[[t]].copy()
        
    str_sql = """
        SELECT [product_id],[b3_sector],[b3_subsector],[b3_segment],[a1_sector] as sector
            FROM [b3].[sector_classification]    
    """    
    dfClassif = pd.read_sql(str_sql, connection, index_col='product_id')
    dfClassif['sector'].replace({'Transportation/Travel':'Transp./Travel'}, inplace=True)
    
    str_sql = """
        SELECT date_reference, s.product_id, s.a1_sector as sector, [pct]/100 as perc
            FROM [b3].[ibovespa_composition] c inner join b3.sector_classification s on c.code = s.product_id
            WHERE date_reference = (SELECT max([date_reference]) FROM [b3].[ibovespa_composition] WHERE date_reference <= '{:%Y-%m-%d}')
              """
    dfIbovComp = pd.read_sql(str_sql.format(dt), connection, index_col='product_id')
    
    
    str_sql = """
        SELECT tsv.date_reference, ts.entity_id as product_id, ts.field, tsv.value   
        FROM quant.time_series_entity tse JOIN quant.time_series ts ON ts.entity_id = tse.id 
             JOIN quant.time_series_value tsv ON tsv.series_id = ts.id
        WHERE ts.field in ('CHG_PCT_1D','TURNOVER') 
            and tsv.date_reference >= '{:%Y-%m-%d}' 
            and ts.entity_id in (SELECT distinct [entity_id]  FROM [middle].[product]
                    where [product_type] in ('Equity', 'Equity Index', 'Commodity'))
    """
    str_sql = str_sql.format(dt-datetime.timedelta(90))
    df = pd.read_sql(str_sql, connection)
    df = df.replace({'IBOV':'IBVSP'})
   
    # str_sql = """
    # SELECT p.product_underlying as product_id, qtsv.date_reference, qts.field, qtsv.value   
    #   FROM [quant].[time_series] as qts 
    # 	INNER JOIN middle.product as p ON qts.entity_id = p.entity_id
    # 	INNER JOIN [quant].[time_series_value] as qtsv ON qtsv.series_id = qts.id
    #   WHERE qtsv.date_reference >= '{:%Y-%m-%d}' and qts.field in ('CHG_PCT_1D','TURNOVER') and qts.source = 'bloomberg'
    # """ 
    # str_sql = str_sql.format(dt-datetime.timedelta(90))
    # df = pd.read_sql(str_sql, connection)
    # df['product_id'].replace({'IBOV':'IBVSP'}, inplace=True)
    dfTO = df[df['field']=='TURNOVER'].pivot(index='date_reference', columns='product_id', values='value')
    for col in dfTO.columns:
        dfTO.loc[dfTO[col].first_valid_index(), col] = np.nan
    dfTO = dfTO.loc[:dt]
    dfTO = dfTO[[i for i in dfTO.columns if i not in ['MATB11', 'SMAL11']]]
    
    dfRet = df[df['field']=='CHG_PCT_1D'].pivot(index='date_reference', columns='product_id', values='value').loc[:dt]
    ipo_list = list(dfRet.count()[(dfRet.count()<21)].index)
    for c in dfRet.columns:
        if c in dfPos.index:
            ind_x = dfRet[c].first_valid_index()
            if ind_x == None:
                ind_x = dfRet[c].index[0]
            dfRet.loc[ind_x:, c].fillna(0, inplace=True)
            dfRet[c].iloc[max(0, list(dfRet.index).index(ind_x)-1)]=0
        
        
    dfRet = dfRet[[i for i in dfPos.index if i in dfRet.columns]]/100
    dfRetAcum = (dfRet+1).cumprod() - 1
    # dfRetAcum.loc[dfRetAcum.index[0]+datetime.timedelta(days=-1)] = 0
    dfRetAcum.sort_index(inplace=True)
    
    dfPos = dfPos.join(pd.DataFrame(dfTO.mean(), columns=['AvgTO']))

    dic_share = fu.get_DailyRiskShare(dt, str_fund).loc[dt].to_dict()
    
    list_trader = sorted(dic_share, key=dic_share.get)
    
    # list_trader = fu.traders

    # connection.close()
    del str_sql

#%%
    ic_var = 1.64485362695147
    threshold = 0.15
    str_benchmark = 'IBVSP'

    X = dfCovarDB.values
    X = np.triu(X) + np.tril(X, -1).T
    dfCovar = pd.DataFrame(np.triu(X) + np.tril(X.T, -1), 
                           columns=dfCovarDB.index, 
                           index=dfCovarDB.index)
    dfCovar = pd.DataFrame(columns=dfPos.index,
                           index=dfPos.index).fillna(dfCovar).fillna(0.001)
    dfCovar = dfCovar[dfPos.index].loc[dfPos.index]
    covar = dfCovar.values
    var_bechmark = dfCovar.loc[str_benchmark,str_benchmark]
    D = 1/np.sqrt(np.diag(covar))
    correl = np.diag(D) @ covar @ np.diag(D)
    
    dfRisk = pd.DataFrame(columns=['VaR','LVaR'])
    
    for t in dic_Pos.keys():
        dic_Pos[t]['%'] = dic_Pos[t][t]/dfPos['AvgTO']   
        dic_Pos[t]['days_to_liquidate'] = (dic_Pos[t]['%'].fillna(0)/threshold).apply(lambda x: int(abs(x))+1)
        
        w = dic_Pos[t][t].values   
        var_t = np.sqrt(w.T @ covar @ w) * ic_var
        
        adj_variance = [var*(max(days,2))/2 for var, days in zip(np.diag(covar), dic_Pos[t]['days_to_liquidate'].values)]
        covar_adj = np.sqrt(np.diag(adj_variance)) @ correl @ np.sqrt(np.diag(adj_variance))
        var_adj = np.sqrt(w.T @ covar_adj @ w) * ic_var
        dfCovarAdj = pd.DataFrame(covar_adj, columns=dfPos.index, index=dfPos.index)
    
        dic_Pos[t]['delta_%'] = dic_Pos[t][t] / nav
        dic_Pos[t]['beta_cvar'] = (covar @ w) / (w.T @ covar @ w)
        dic_Pos[t]['cvar'] = dic_Pos[t]['beta_cvar'] * dic_Pos[t][t] * var_t / nav * 10000
        for c in dfPos.index:
            # dic_Pos[t].loc[c,'beta'] = dfCovar.loc[c, str_benchmark] / var_bechmark
            dic_Pos[t].loc[c,'vol'] = np.sqrt(dfCovar.loc[c, c]) * np.sqrt(252)
            dic_Pos[t].loc[c,'vol_adj'] = np.sqrt(dfCovarAdj.loc[c, c]) * np.sqrt(252)
            
            w_prime = dic_Pos[t][t].copy()
            w_prime.loc[c] = 0
            w_prime = w_prime.values
            var_marginal = var_t - np.sqrt(w_prime.T @ covar @ w_prime) * ic_var
            dic_Pos[t].loc[c,'var_marginal'] = var_marginal / nav * 10000
            var_marginal_adj = var_adj - np.sqrt(w_prime.T @ covar_adj @ w_prime) * ic_var
            dic_Pos[t].loc[c,'var_marginal_adj'] = var_marginal_adj / nav * 10000

        dic_Pos[t]['beta_cvar_adj'] = (covar @ w) / (w.T @ covar @ w)
        dic_Pos[t]['cvar_adj'] = dic_Pos[t]['beta_cvar_adj'] * dic_Pos[t][t] * var_adj / nav * 10000
        
        
        dfRisk.loc[t, 'VaR'] = var_t
        dfRisk.loc[t, 'LVaR'] = var_adj

        # print('{}: {:2.2f} {:2.2f}'.format(t, var_t/ nav * 10000, var_adj/ nav * 10000))

#%%
    color1, color2 = fu.color_palette[0:2]
    fig, axes = plt.subplots(nrows=len(dfRisk.index), ncols=7, figsize=(12, 7), sharex='col', 
                               gridspec_kw = {'width_ratios':[1, 1, 1, 4, 4, 2.5, 2]})
    plt.tight_layout()
    plt.subplots_adjust(hspace=0.05, wspace=0.1)
    
    cols = sorted(list(dfClassif['sector'].dropna().unique())) + ['IBOVESPA']
    
    axes[0,0].set_title('Risk', fontweight='bold', fontsize=12)
    axes[0,1].set_title('In Ibov?', fontweight='bold', fontsize=12)
    axes[0,2].set_title('IPO?', fontweight='bold', fontsize=12)
    axes[0,3].set_title('Delta by Sector', fontweight='bold', fontsize=12)
    axes[0,4].set_title('Top Risk Increment', fontweight='bold', fontsize=12)
    axes[0,5].set_title('Top Risk Hedge', fontweight='bold', fontsize=12)
    axes[0,6].set_title('Liq. Vol Adjustment', fontweight='bold', fontsize=11)
    dic_max_top = {}
    for i, t in enumerate([tt for tt in list_trader if tt in dfRisk.index]):
        col=0
        ax = axes[i,col]
        ax.set_yticklabels([])
        temp = dfRisk.loc[t]/nav*10000/dic_share[t]
        temp.plot.bar(ax=ax, zorder=3, color=[color2, color1])
        ax.set_ylabel('{}\n({:2.1%})'.format(t,dic_share[t]), fontweight='bold', fontsize=11)
        ax.grid(ls='--', axis='y', zorder=0)
        for x, y in enumerate(temp.values):
            ax.text(x,y,'{:2.0f}'.format(y), fontweight='bold', ha='center', va='bottom')
        dic_max_top[col] = max(dic_max_top.get(col,0), ax.get_ylim()[1])
        
        col+=1
        ax = axes[i,col]
        ax.set_yticklabels([])
        temp = dic_Pos[t][['delta_%']].join(dfIbovComp[['sector']])
        temp['ibov'] = temp['sector'].apply(lambda x: 'No' if pd.isna(x) else 'Yes')
        temp.loc['IBVSP', 'ibov'] = 'Yes'
        temp = temp.groupby(['ibov']).sum().reindex(['Yes','No'])/dic_share[t]
        temp['delta_%'].plot.bar(ax=ax, legend=False, zorder=3, color=(temp['delta_%'] > 0).map({True: color2, False: 'tomato'}))
        ax.axhline(0, c='k', lw=0.5)
        ax.grid(ls='--', axis='y', zorder=0)
        ax.set_xlabel('')
        for x, y in enumerate(temp['delta_%'].values):
            ax.text(x,max(y,0),'{:2.0%}'.format(y) if y!=0 else '-', fontweight='bold', ha='center', 
                    va='bottom', color='r' if y<0 else 'k')
        dic_max_top[col] = max(dic_max_top.get(col,0), ax.get_ylim()[1])

        col+=1
        ax = axes[i,col]
        ax.set_yticklabels([])
        temp = dic_Pos[t][['delta_%']].copy()
        temp['ipo'] = 'No'
        temp.loc[[x for x in ipo_list if x in dic_Pos[t].index], 'ipo'] = 'Yes'
        temp = temp.groupby(['ipo']).sum().reindex(['Yes','No'])/dic_share[t]
        temp['delta_%'].plot.bar(ax=ax, legend=False, zorder=3, color=['orange', color2])
        ax.axhline(0, c='k', lw=0.5)
        ax.grid(ls='--', axis='y', zorder=0)
        ax.set_xlabel('')
        for x, y in enumerate(temp['delta_%'].fillna(0).values):
            ax.text(x,max(y,0),'{:2.0%}'.format(y) if y!=0 else '-', fontweight='bold', ha='center', 
                    va='bottom', color='r' if y<0 else 'k')
        dic_max_top[col] = max(dic_max_top.get(col,0), ax.get_ylim()[1])
        
        
        col+=1
        ax = axes[i,col]
        ax.set_yticklabels([])
        temp = dic_Pos[t][['delta_%']].join(dfClassif[['sector']])
        temp.loc['IBVSP', 'sector'] = 'IBOVESPA'
        temp = temp.groupby(['sector']).sum().reindex(cols).fillna(0)/dic_share[t]
        temp['delta_%'].plot.bar(ax=ax, legend=False, zorder=3, color=(temp['delta_%'] > 0).map({True: color2, False: 'tomato'}))
        ax.axhline(0, c='k', lw=0.5)
        ax.grid(ls='--', axis='y', zorder=0)
        ax.grid(ls=':', axis='x', zorder=0)
        ax.set_xlabel('')
        for x, y in enumerate(temp['delta_%'].fillna(0).values):
            ax.text(x,max(y,0),' {:1.1f}'.format(y*100) if y!=0 else ' ', fontweight='bold', ha='center', fontsize=9,
                    va='bottom', color='r' if y<0 else 'k', rotation=90)
        dic_max_top[col] = max(dic_max_top.get(col,0), ax.get_ylim()[1])
        
        col+=1
        ax = axes[i,col]
        ax.axis('off')
        top10 = dic_Pos[t][dic_Pos[t]['cvar']>0]['cvar'].sort_values(ascending=False).head(10)
        dic_size = (top10/top10.sum()).to_dict()
        r = squarify.plot(top10.values, 
                      label=['{}\n{:2.1f}'.format(tick, val/dic_share[t]) for (tick, val) in top10.iteritems()], 
                      color=cm.get_cmap('Blues', 128)(np.linspace(0.75, 0.15, 10)),
                      pad=0.5, 
                      text_kwargs={'weight':'bold',
                                   'size':7},
                      ax=ax)
        for tx in r.texts:
            tick = tx.get_text().split('\n')[0]
            if tick in ipo_list:
                tx.set_color('orange')
            if dic_size[tick]<0.03:
                tx.set_fontsize(5)
            elif dic_size[tick]<0.07:
                tx.set_fontsize(6)           
            
        col+=1
        ax = axes[i,col]
        ax.axis('off')
        top10 = dic_Pos[t][dic_Pos[t]['cvar']<0]['cvar'].sort_values(ascending=True).head(6)
        dic_size = (top10/top10.sum()).to_dict()
        r = squarify.plot(top10.values, 
                      label=['{}\n{:2.1f}'.format(tick, val/dic_share[t]) for (tick, val) in top10.iteritems()], 
                      color=cm.get_cmap('Reds', 128)(np.linspace(0.65, 0.2, 6)),
                      pad=0.5, 
                      text_kwargs={'weight':'bold',
                                   'size':7},
                      ax=ax)
        for tx in r.texts:
            tick = tx.get_text().split('\n')[0]
            if tick in ipo_list:
                tx.set_color('orange')
            if dic_size[tick]<0.03:
                tx.set_fontsize(5)
            elif dic_size[tick]<0.07:
                tx.set_fontsize(6)
        
        col+=1
        ax = axes[i,col]
        ax.axis('off')
        top10 = (dic_Pos[t]['vol_adj']-dic_Pos[t]['vol']).sort_values(ascending=False).head(6)
        top10 = top10[top10>0.001]
        dic_size = (top10/top10.sum()).to_dict()
        r = squarify.plot(top10.values, 
                      label=['{}\n{:+2.0%}'.format(tick, val) for (tick, val) in top10.iteritems()], 
                      color=cm.get_cmap('Greys', 128)(np.linspace(0.60, 0.15, 6)),
                      pad=0.5, 
                      text_kwargs={'weight':'bold',
                                   'size':7},
                      ax=ax)
        for tx in r.texts:
            tick = tx.get_text().split('\n')[0]
            if tick in ipo_list:
                tx.set_color('orange')
            if dic_size[tick]<0.05:
                tx.set_fontsize(4)
            elif dic_size[tick]<0.1:
                tx.set_fontsize(5)
    
    for col in [0,1,2,3]:
        axes[-1, col].set_facecolor('gainsboro')
    
    for i, top in dic_max_top.items():
        for j in range(len(dfRisk)):
            axes[j,i].set_ylim(top=(top+0.01)*1.4)

    if print_pdf:
         fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_{1}_equity_trader_breakdown.pdf'.format(dt, str_fund)
         fig.savefig(fig_file, bbox_inches = "tight")

    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_equity_trader_breakdown.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    wb = xw.Book(report_filename)
    wb.sheets('Eqty_Trader_Liq').pictures.add(wb.api.Path + '/' + fig_file, name='eqty_trader_liq', update=True)
    # wb.sheets('Eqty_Trader_Liq').pictures.add(fig, name='eqty_trader_liq')
    #%%
    if plot_vol:
        fig, axes = plt.subplots(2,2, figsize=(12, 6), 
                                                  gridspec_kw = {'height_ratios':[3,2]},
                                                  sharey='row', sharex='col')
        fig.tight_layout(w_pad=0, h_pad=0)
        
        top20 = list(dic_Pos['Fund'][dic_Pos['Fund']['cvar']<0]['cvar'].sort_values().head(10).index)
        top20 += list(dic_Pos['Fund'][dic_Pos['Fund']['cvar']>0]['cvar'].sort_values().tail(10).index)
        
        vols = dfRet.ewm(alpha=0.06).std().iloc[-1] * np.sqrt(252)
        texts1, texts2 = [], []
        missing_ids = []
        for ind in dfPos.index:
            if ind in dfRetAcum.columns:
                if ind in top20:
                    color='orange' if ind in ipo_list else 'blue' if dfPos.loc[ind, 'Fund'] > 0 else 'r' 
                    ls='-'
                    s=np.abs(dfPos.loc[ind,'Fund']/nav*(0.5*10**5))
                    fw='bold'
                    marker='o'
                    fc=color
                    fs=9
                else:
                    color = 'orange' if ind in ipo_list else 'royalblue' if dfPos.loc[ind, 'Fund'] > 0 else 'tomato'
                    ls=':'
                    s=5
                    fw='normal'
                    marker='s'
                    fc='k'
                    fs=7
                    
                if dfPos.loc[ind, 'Fund'] > 0:
                    ax1 = axes[0,0]
                    ax2 = axes[0,1]
                    texts = texts1
                else:
                    ax1 = axes[1,0]
                    ax2 = axes[1,1]
                    texts = texts2
                    
                        
                ax1.plot(dfRetAcum.index, dfRetAcum[ind], color=color, ls=ls, zorder=3)   
                ax2.scatter([vols[ind]],[dfRetAcum.iloc[-1][ind]], color=color, zorder=3,
                            s=s, marker=marker, 
                            alpha=0.4)
                texts.append(ax2.text(vols[ind],dfRetAcum.iloc[-1][ind], ind, fontweight=fw,
                                       color=fc, fontsize=fs, zorder=4))
            else:
                missing_ids.append(ind)
        
        if len(missing_ids)>0:
            print('======\u26A0\u26A0\u26A0======\nMissing Returns for:\n{}\n===================='.format('\n'.join(missing_ids)))
    
        axes[0,0].set_xlim(left=dfRetAcum.index[0], right=dfRetAcum.index[-1])
        # axes[0,1].set_xlim(left=0)
        axes[1,0].xaxis.set_major_formatter(mdates.DateFormatter('%d-%b\n%Y'))
        for ax in axes.flatten():
            ax.grid(ls='--', which='both')
            ax.axhline(0, c='k', lw=0.5)
            ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
            
        axes[0,0].set_title('Accum. Performance (3M)')
        axes[0,1].set_title('Return x Vol')
        axes[1,1].set_xlabel('vol (%aa)')
        
        vol_ibov = np.sqrt(var_bechmark)*np.sqrt(252)
        w = dic_Pos['Fund']['Fund'].values   
        vol_fundo_eqty = np.sqrt(w.T @ covar @ w)/nav * np.sqrt(252) 
        
        axes[1,1].axvline(vol_ibov, ls='--', c='k')
        axes[0,1].axvline(vol_ibov, ls='--', c='k')
        axes[0,1].text(vol_ibov, axes[0,1].get_ylim()[1]*.9, ' Vol IBVSP ({:2.1%})'.format(vol_ibov), fontweight='bold')
        
        axes[0,1].set_xscale('log')
        axes[1,1].xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
        axes[1,1].xaxis.set_minor_formatter(mticker.PercentFormatter(xmax=1))
        axes[1,1].tick_params(axis='x', which='minor', labelsize=8)
        adjustText.adjust_text(texts1,ax=axes[0,1])
        adjustText.adjust_text(texts2,ax=axes[1,1])
          
        fig_file = '../output/temp_figs/{:%Y%m%d}_{}_equity_ret_vol.svg'.format(dt, str_fund)
        fig.savefig(fig_file, bbox_inches = "tight")    
        plt.show()
        # dfCVarSector.plot.bar(color=(dfCVarSector > 0).map({True: color2, False: 'tomato'}))
    
#%%
    if 'FK' in dic_Pos.keys():
        dic_Pos['FK'][['FK', 'days_to_liquidate', 'delta_%', 'cvar', 'vol',
                   'vol_adj', 'cvar_adj']].to_excel('R:/Public/Kops/Liquidity/{:%Y%m%d}_liquidity.xlsx'.format(dt))

#%%
    if save_to_db:
        str_sql = """
            DELETE FROM [risk].[measure] 
            WHERE date_reference = '{:%Y-%m-%d}' 
                AND trading_desk = '{}' 
                AND [risk_measure] = 'LVaR'
                  """ 
        str_sql = str_sql.format(dt,str_fund)
        connection.execute(str_sql)
        for id_var, value_var in dfRisk['LVaR'].iteritems():
            str_parent_tree = 'Fund' if id_var == 'Fund' else 'Traders'
            str_sql = """
            INSERT INTO [risk].[measure]
                ([date_reference],[trading_desk],[parent_tree],[node],[risk_measure],[value])
                VALUES ('{:%Y-%m-%d}','{}','{}','{}','LVaR',{})
            """
            str_sql = str_sql.format(dt, str_fund, str_parent_tree, id_var, value_var)
            connection.execute(str_sql)
        del str_sql
    
#%%
    connection.close()
    
#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt, str_fund = fu.get_config(['dt', 'str_fund'])
    report_filename = '../xls/RiskMap_model.xlsm'
    nav = fu.get_NAV(dt, str_fund)
    main(dt, 
         str_fund, 
         nav, 
         report_filename,
         plot_vol=True,
         save_to_db=True,
         print_pdf=False) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))