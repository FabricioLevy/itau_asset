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
def main(dt, str_fund, nav, report_filename): 
#%%
    dfB3Liq = pd.read_excel('../output/temp_figs/{:%Y%m%d}_liq_b3_fut.xlsx'.format(dt), index_col=0)

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
        SELECT lote45_product,[book],amount as qty,[primitive],'delta' as greek,[delta] as w
            FROM [lote45].[primitive]
            WHERE date_reference = '{0:%Y-%m-%d}' AND trading_desk = '{1:}'
            and primitive_class not in ('Brazil Sovereign Yield')
        UNION
        SELECT lote45_product,[book],amount as qty,'Vol ' + [primitive],'vega',[vega] as w
            FROM [lote45].[primitive]
            WHERE date_reference = '{0:%Y-%m-%d}' AND trading_desk = '{1:}'
                AND primitive in ('IBVSP','USDBRLSpot') AND vega<>0
      """
    dfPrimitive = pd.read_sql(str_sql.format(dt, str_fund), connection)
    dfPrimitive['trader'] = dfPrimitive['book'].apply(lambda x: dic_books[x])
    
    dfQty = dfPrimitive[['trader', 'lote45_product', 'qty']].drop_duplicates().pivot_table(index='lote45_product', columns='trader', values='qty', aggfunc=np.sum).fillna(0)
    dfQty['Fund'] = dfQty.sum(axis=1)
        
    dfPrimitiveTrader = dfPrimitive[['trader','lote45_product', 'primitive', 'w']].pivot_table(index='primitive', columns=['trader','lote45_product'], values='w', aggfunc=np.sum)
    
    dfPrimitive = dfPrimitive.pivot_table(index='primitive', columns='trader', values='w', aggfunc=np.sum).fillna(0)
    dfPrimitive['Fund'] = dfPrimitive.sum(axis=1)
    
    dfPrimitiveTrader = dfPrimitiveTrader.loc[dfPrimitive.index]
    temp_df = dfPrimitiveTrader.groupby(level=1,axis=1).sum()
    for c in temp_df.columns:
        dfPrimitiveTrader[('Fund', c)] = temp_df[c]
  
    str_sql = """
SELECT [id],isnull(product_underlying,[product_type]) as prod_type
  FROM [middle].[product]
  where product_type not in ('Equity','DAP Future','DI1Future')
      """
    dic_prod = pd.read_sql(str_sql, connection, index_col='id')['prod_type'].to_dict()
       
    connection.close()
    del str_sql
    #%%
    dfDaysToLiquidate = pd.DataFrame(index=dfQty.index, columns=dfQty.columns)
    threshold = 0.2
    
    dfPrimitiveAdj = pd.DataFrame(index=dfPrimitive.index, columns=dfDaysToLiquidate.columns)
    
    for trader in dfDaysToLiquidate.columns:
        for prod in dfDaysToLiquidate.index:
            dfDaysToLiquidate.loc[prod, trader] = abs(dfQty.loc[prod, trader]/dfB3Liq['avg1month'].get(prod,np.inf)/threshold)
        
        # if trader == 'Fund':
        #     # temp_trader_delta = dfPos[['lote45_product', 'primitive', 'delta']].pivot_table(index='primitive', columns='lote45_product', values='delta', aggfunc=np.sum).abs()
        #     temp_trader_delta = dfPrimitiveTrader.abs().groupby(level=1,axis=1).sum()
        # else:
        #     # temp_trader_delta = dfPos[dfPos['trader']==trader][['lote45_product', 'primitive', 'delta']].pivot_table(index='primitive', columns='lote45_product', values='delta', aggfunc=np.sum).abs()
        temp_trader_delta = dfPrimitiveTrader[trader].abs()
        for primitive in temp_trader_delta.index:
            tot_primitive = temp_trader_delta.loc[primitive].sum()
            sum_days = 0
            for prod, val in temp_trader_delta.loc[primitive].dropna().iteritems():
                sum_days += val * dfDaysToLiquidate.loc[prod, trader]
            dfPrimitiveAdj.loc[primitive, trader] = 0 if tot_primitive == 0 else sum_days/tot_primitive
            

#%%
    ic_var = 1.64485362695147
    
    X = dfCovarDB.values
    X = np.triu(X) + np.tril(X, -1).T
    dfCovar = pd.DataFrame(np.triu(X) + np.tril(X.T, -1), columns=dfCovarDB.index, index=dfCovarDB.index)
    dfCovar = dfCovar[dfPrimitive.index].loc[dfPrimitive.index]
    covar = dfCovar.values
    D = 1/np.sqrt(np.diag(covar))
    correl = np.diag(D) @ covar @ np.diag(D)
    
    dfRisk = pd.DataFrame(columns=['VaR','LVaR'])
    dfCVaR = pd.DataFrame(index=dfQty.index, columns=dfPrimitive.columns)
    dfCVaRLiq = pd.DataFrame(index=dfQty.index, columns=dfPrimitive.columns)
        
    for trader in dfPrimitive.columns:
        w = dfPrimitive[trader].values   
        var_t = np.sqrt(w.T @ covar @ w) * ic_var
        
        adj_variance = [var*(max(days,2))/2 for var, days in zip(np.diag(covar), dfPrimitiveAdj[trader].fillna(0).values)]
        covar_adj = np.sqrt(np.diag(adj_variance)) @ correl @ np.sqrt(np.diag(adj_variance))
        var_adj = np.sqrt(w.T @ covar_adj @ w) * ic_var
        dfCovarAdj = pd.DataFrame(covar_adj, columns=dfPrimitive.index, index=dfPrimitive.index)
        
        beta_cvar = (covar @ w) / (w.T @ covar @ w)
        beta_cvar_adj = (covar_adj @ w) / (w.T @ covar_adj @ w)
        for prod in dfPrimitiveTrader[trader].columns:
            dfCVaR.loc[prod, trader] = (dfPrimitiveTrader[trader][prod].fillna(0).values @ beta_cvar) * var_t / nav * 10000
            dfCVaRLiq.loc[prod, trader] = (dfPrimitiveTrader[trader][prod].fillna(0).values @ beta_cvar_adj) * var_adj / nav * 10000
        
        dfRisk.loc[trader, 'VaR'] = var_t
        dfRisk.loc[trader, 'LVaR'] = var_adj


    dfCVaR['group'] = [dic_prod.get(i,i) for i in dfCVaR.index.values]
    dfCVaR['group'] = dfCVaR['group'].apply(lambda x: 'CC' if x in ['DDI Future','SCS','SCS TERM'] else x)
    dfCVaR = dfCVaR.groupby(['group']).sum()
        
#%%
    color1, color2 = fu.color_palette[0:2]
    fig, axes = plt.subplots(nrows=4, ncols=4, figsize=(12, 7), #sharex='col', 
                               gridspec_kw = {'width_ratios':[1, 5, 3, 2]})
    plt.tight_layout()
    plt.subplots_adjust(hspace=0.05, wspace=0.1)
    
    dic_share = {'MS':0.48, 'BC':0.285, 'GB':0.04, "Fund":1}
        
    axes[0,0].set_title('Risk', fontweight='bold', fontsize=12)
    axes[0,1].set_title('Top Risk Increment', fontweight='bold', fontsize=12)
    axes[0,2].set_title('Top Risk Hedge', fontweight='bold', fontsize=12)
    axes[0,3].set_title('Liq. Vol Adjustment', fontweight='bold', fontsize=11)
    dic_max_top = {}
    for i, t in enumerate(dic_share.keys()):
        ax = axes[i,0]
        ax.set_yticklabels([])
        temp = dfRisk.loc[t]/nav*10000/dic_share[t]
        temp.plot.bar(ax=ax, zorder=3, color=[color2, color1])
        ax.set_ylabel(t, fontweight='bold', fontsize=14)
        ax.grid(ls='--', axis='y', zorder=0)
        for x, y in enumerate(temp.values):
            ax.text(x,y,'{:2.0f}'.format(y), fontweight='bold', ha='center', va='bottom')
        dic_max_top[0] = max(dic_max_top.get(0,0), ax.get_ylim()[1])
        
        ax = axes[i,1]
        ax.axis('off')
        top10 = dfCVaR[dfCVaR[t]>0][t].sort_values(ascending=False).head(10)
        dic_size = (top10/top10.sum()).to_dict()
        r = squarify.plot(top10.values, 
                      label=['{}\n{:2,.1f}'.format(tick, val/dic_share[t]) for (tick, val) in top10.iteritems()], 
                      color=cm.get_cmap('Blues', 128)(np.linspace(0.75, 0.15, 10)),
                      pad=0.5, 
                      text_kwargs={'weight':'bold',
                                   'size':7},
                      ax=ax)
        for tx in r.texts:
            tick = tx.get_text().split('\n')[0]
            if dic_size[tick]<0.03:
                tx.set_fontsize(5)
            elif dic_size[tick]<0.07:
                tx.set_fontsize(6)           
            
        
        ax = axes[i,2]
        ax.axis('off')
        top10 = dfCVaR[dfCVaR[t]<0][t].sort_values(ascending=True).head(6)
        dic_size = (top10/top10.sum()).to_dict()
        r = squarify.plot(top10.values, 
                      label=['{}\n{:2,.1f}'.format(tick, val/dic_share[t]) for (tick, val) in top10.iteritems()], 
                      color=cm.get_cmap('Reds', 128)(np.linspace(0.65, 0.2, 6)),
                      pad=0.5, 
                      text_kwargs={'weight':'bold',
                                   'size':7},
                      ax=ax)
        for tx in r.texts:
            tick = tx.get_text().split('\n')[0]
            if dic_size[tick]<0.03:
                tx.set_fontsize(5)
            elif dic_size[tick]<0.07:
                tx.set_fontsize(6)
        
        ax = axes[i,3]
        ax.axis('off')
        # top10 = (dic_Pos[t]['vol_adj']-dic_Pos[t]['vol']).sort_values(ascending=False).head(6)
        # top10 = top10[top10>0.001]
        # dic_size = (top10/top10.sum()).to_dict()
        # r = squarify.plot(top10.values, 
        #               label=['{}\n{:+2.0%}'.format(tick, val) for (tick, val) in top10.iteritems()], 
        #               color=cm.get_cmap('Greys', 128)(np.linspace(0.60, 0.15, 6)),
        #               pad=0.5, 
        #               text_kwargs={'weight':'bold',
        #                            'size':7},
        #               ax=ax)
        # for tx in r.texts:
        #     tick = tx.get_text().split('\n')[0]
        #     if dic_size[tick]<0.05:
        #         tx.set_fontsize(4)
        #     elif dic_size[tick]<0.1:
        #         tx.set_fontsize(5)
                
    for i, top in dic_max_top.items():
        for j,_ in enumerate(dic_share.keys()):
            axes[j,i].set_ylim(top=top*1.35)

    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_ir_trader_breakdown.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    # wb = xw.Book(report_filename)
    # wb.sheets('xx').pictures.add(wb.api.Path + '/' + fig_file, name='eqty_trader_liq', update=True)
    # wb.sheets('xx').pictures.add(fig, name='eqty_trader_liq')


#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt = datetime.date(2021, 9, 23)
    str_fund = 'A1 Master FIM'
    report_filename = '../xls/RiskMap_model.xlsm'
    nav = fu.get_NAV(dt, str_fund)
    main(dt, str_fund, nav, report_filename) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))