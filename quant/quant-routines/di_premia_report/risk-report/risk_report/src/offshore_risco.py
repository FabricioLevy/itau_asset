import pandas as pd
import numpy as np
import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import fund_utils as fu

def main(dt, str_fund, nav):
    #%%
    _, connection = fu.get_DB_conn('prod')    
    str_sql = f"""
               SELECT  [lote45_product_class],[lote45_product],[primitive_class],
                   [primitive],[book],[product_currency],[bucket],[eq_position],
                   [amount],'delta' as greek, [delta] as w
               FROM [lote45].[primitive]
               WHERE trading_desk = '{str_fund}'
                    and date_reference = '{dt:%Y-%m-%d}'
              UNION
              SELECT [lote45_product_class],[lote45_product],[primitive_class],
                  'Vol ' + [primitive],[book],[product_currency],[bucket],[eq_position],
                  [amount],'vega',[vega] as w
                  FROM [lote45].[primitive]
                  WHERE date_reference = '{dt:%Y-%m-%d}' AND trading_desk = '{str_fund}'
                      AND primitive in ('IBVSP','USDBRLSpot') AND vega<>0
                    
         """
    dfPrimitive = pd.read_sql(str_sql, connection)
    
    dic_class = {'USA Sovereign Yield': 'IR US',
                 'BRL Rate Curve': 'IR BRL',
                 'Brazil Sovereign Yield': 'IR BRL',
                 'COP Rate Curve': 'IR Latam',
                 'Equity': 'Equity',
                 'CLP Rate Curve': 'IR Latam',
                 'IPCA Coupon': 'Inflation BRL',
                 'IPCA': 'Inflation BRL',
                 'MXN Rate Curve': 'IR Latam',
                 'BRD Rate Curve': 'Cp Cambial',
                 'Commodity': 'Commodity',
                 'FX': 'FX',
                 'USD Rate Curve': 'IR US',
                 'Japan Sovereign Yield': 'IR Japan'}
    
    dfPrimitive['primitive_type'] = dfPrimitive['primitive_class'].apply(lambda x: dic_class[x])
    
    str_sql = f"""
    SELECT [primitive1],[primitive2],[covar_value]
      FROM [lote45].[covar_matrix]
      WHERE date_reference = '{dt:%Y-%m-%d}' 
      ORDER BY 1, 2
    """
    dfCovarDB = pd.read_sql(str_sql, connection).pivot(index='primitive1', 
                                                             columns='primitive2', 
                                                             values='covar_value').fillna(0)
    X = dfCovarDB.values
    X = np.triu(X) + np.tril(X, -1).T
    dfCovar = pd.DataFrame(np.triu(X) + np.tril(X.T, -1), 
                           columns=dfCovarDB.index, 
                           index=dfCovarDB.index)

    trees = ['Risk', 'Traders']
    dic_trees = {}
    for str_tree in trees:
        str_sql = """
           SELECT [parent_tree],[parent_node],[node],[book]
           FROM [lote45].[book_tree]
           WHERE parent_tree = '{}'
                    """
        nd = fu.Node(str_tree, 
                     pd.read_sql(str_sql.format(str_tree), 
                                 connection))
        dic_trees[str_tree] = nd.to_inv_dict(str_tree)   
        
        dfPrimitive[str_tree] = dfPrimitive['book'].apply(lambda x: dic_trees[str_tree][x])
    #%%
    dfW = dfPrimitive.pivot_table(index='primitive', 
                                  columns='Traders', 
                                  values='w', 
                                  aggfunc=np.sum).fillna(0)
    dfW['Fund'] = dfW.sum(axis=1)
    dfW = dfW.join(dfPrimitive.pivot_table(index='primitive', 
                                              columns='primitive_type', 
                                              values='w', 
                                              aggfunc=np.sum).fillna(0))
    
    cov = dfCovar.loc[dfW.index, dfW.index].values
    w = dfW['Fund'].values
    beta_cvar =  pd.Series((cov @ w) / (w.T @ cov @ w),
                              index=dfW.index)
    #%%
    ic_var = 1.64485362695147
    dfVaR = pd.DataFrame(columns=dfW.columns,
                         index=['VaR', 'CVaR'])
    
    for c in dfVaR.columns:
        w = dfW[c].values 
        dfVaR.loc['VaR', c] = np.sqrt(w.T @ cov @ w) * ic_var /nav * 10_000
        dfVaR.loc['CVaR', c] = w @ beta_cvar.values 
        
    dfVaR.loc['CVaR'] = dfVaR.loc['CVaR'] * dfVaR.loc['VaR', 'Fund']
    
    #%%
    dfDelta = dfPrimitive[dfPrimitive['greek']=='delta']
    
    color1, color2 = fu.color_palette[0:2]

    #%%
    dic_traders = fu.get_traders(dt)
    
    figPM, (ax1, ax2) = plt.subplots(2, 1, sharex=True,  
                                     figsize=(4, 2.4),
                                     constrained_layout=True,
                                     gridspec_kw = {'height_ratios':[3, 1]})
    # figPM.tight_layout()
    
    dfPlot = dfVaR[[i for i in dic_traders.keys() if i in dfVaR.columns]].T
    
    dfPlot['VaR'].plot(kind='bar', color=color2, zorder=3, ax=ax1)
    dfPlot['CVaR'].plot(kind='bar', color=color1, zorder=3,  ax=ax2)
    
    for i, (v, c) in enumerate(dfPlot.values):
        ax1.text(i, v, f" {v:4,.1f}", ha='center', va='bottom',color='r' if v<0 else 'k', fontweight='bold')
        ax2.text(i, c, f" {c:4,.1f}", ha='center', va='bottom',color='r' if c<0 else 'k', fontweight='bold')
    
    ax1.set_ylabel('VaR (BPs)')
    ax1.grid(ls='--', axis='y')
    ax1.set_ylim(top=1.1 * ax1.get_ylim()[1])
    
    ax2.set_ylabel('Cp VaR (BPs)')
    # ax2.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax2.set_ylim(top=1.5 * ax2.get_ylim()[1])
    ax2.grid(ls='--', axis='y')
    ax2.get_xticklabels()[-1].set_weight("bold")
    
    figPM.align_ylabels()
    plt.show()
    #%%
    figRisk, (ax1, ax2) = plt.subplots(2, 1, sharex=True, 
                                       figsize=(4, 2.4),
                                       constrained_layout=True,
                                       gridspec_kw = {'height_ratios':[3, 1]})
    
    dfPlot = dfVaR[list(dfPrimitive['primitive_type'].unique()) + ['Fund']].T
    
    dfPlot['VaR'].plot(kind='bar', color=color2, zorder=3, ax=ax1)
    dfPlot['CVaR'].plot(kind='bar', color=color1, zorder=3,  ax=ax2)
    
    for i, (v, c) in enumerate(dfPlot.values):
        ax1.text(i, v, f" {v:4,.1f}", ha='center', va='bottom',color='r' if v<0 else 'k', fontweight='bold')
        ax2.text(i, c, f" {c:4,.1f}", ha='center', va='bottom',color='r' if c<0 else 'k', fontweight='bold')
    
    ax1.set_ylabel('VaR (BPs)')
    ax1.grid(ls='--', axis='y')
    ax1.set_ylim(top=1.1 * ax1.get_ylim()[1])
    
    ax2.set_ylabel('Cp VaR (BPs)')
    ax2.set_ylim(top=1.5 * ax2.get_ylim()[1])
    ax2.grid(ls='--', axis='y')
    ax2.set_xticklabels([i.get_text().replace('IR L','IR\nL') for i in ax2.get_xticklabels()])
    ax2.get_xticklabels()[-1].set_weight("bold")
    
    figRisk.align_ylabels()
    plt.show()
    
    #%%
    dfFX = dfDelta[dfDelta['primitive_type']=='FX'][['primitive', 'w']]
    dfFX['long'] = dfFX['primitive'].str[0:3]
    dfFX['short'] = dfFX['primitive'].str[3:6]
    dfFX = (dfFX[['long','w']].groupby(['long']).sum()).join(-dfFX[['short','w']].groupby(['short']).sum(),
                                                             lsuffix='_long',
                                                             rsuffix='_short',
                                                             how='outer')
    dfFX['delta_usd'] = dfFX.sum(axis=1)
    dfFX['delta_%_off'] = dfFX['delta_usd']/nav
    dfFX = dfFX.sort_values(by='delta_%_off')
    
    figFX, ax = plt.subplots(1, 1,
                             figsize=(2, 1.9),
                             constrained_layout=True)
    # figFX.tight_layout()
    dfFX['delta_%_off'].plot(kind='barh', legend=False, alpha=0.5, ax=ax, color=color2)
    ax.axvline(0, lw=0.5, c='k')
    ax.grid(axis='x', ls='--')
    ax.set_ylabel('')
    xlim = max(0.015, max(np.abs(ax.get_xlim())))
    ax.set_xlim(left=-xlim, right=xlim)
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0, 0))
    for i, v in enumerate(dfFX['delta_%_off'].values):
        ax.text(0, i, f" {v:+6,.1%}", va='center', color='r' if v<0 else 'k', fontweight='bold')
    plt.show()
    #%%
    dic_equity = {'NASDAQ-100 E-mini Futures - CME'         : 'Nasdaq',
                  'DJ Euro STOXX 50 Future - EUREX'         : 'EUR Stoxx',
                  'Russell 2000 Index Mini Futures - CME'   : 'Russell',
                  'S&P500 E-mini Futures'                   : 'S&P',
                  'S&P500 E-mini Options'                   : 'S&P'}
    
    dfEquity = dfDelta[dfDelta['primitive_type']=='Equity'][['lote45_product_class', 'w']]
    dfEquity['lote45_product_class'] = dfEquity['lote45_product_class'].apply(lambda x: dic_equity.get(x,x))
    
    dfEquity = dfEquity.groupby(['lote45_product_class']).sum()
    dfEquity['delta_%_off'] = dfEquity['w']/nav
    
    figEqty, ax = plt.subplots(1, 1,
                               figsize=(2, 1.9),
                               constrained_layout=True)
    # figEqty.tight_layout()
    dfEquity['delta_%_off'].plot(kind='barh', legend=False, alpha=0.5, ax=ax, color=color2)
    ax.axvline(0, lw=0.5, c='k')
    ax.grid(axis='x', ls='--')
    ax.set_ylabel('')
    xlim = max(0.015, max(np.abs(ax.get_xlim())))
    ax.set_xlim(left=-xlim, right=xlim)
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0, 0))
    for i, v in enumerate(dfEquity['delta_%_off'].values):
        ax.text(0, i, f" {v:+6,.1%}", va='center', color='r' if v<0 else 'k', fontweight='bold')
    plt.show()
    
    #%%
    dfIR = dfDelta[dfDelta['primitive_type'].isin(['IR US', 'IR Latam', 'IR Japan'])][['primitive_type','primitive_class','primitive', 'w']].groupby(['primitive_type','primitive_class','primitive']).sum() / nav
    
    dfTemp = dfIR.reset_index()
    dic_class = {'USA Sovereign Yield': 'US Tsy',
                 'COP Rate Curve': 'COP',
                 'CLP Rate Curve': 'CLP',
                 'MXN Rate Curve': 'MXN',
                 'USD Rate Curve': 'IR US',
                 'Japan Sovereign Yield': 'JP'} 
    
    dfTemp['primitive_class'] = dfTemp['primitive_class'].apply(lambda x: dic_class.get(x, x))
    
    
    figIR, axes = plt.subplots(1, len(dfTemp['primitive_type'].unique()),
                             figsize=(4, 1.9),
                             squeeze=False,
                             constrained_layout=True)
    
    for ax, pr in zip(axes.flatten(), dfTemp['primitive_type'].unique()):
        dfPlot = dfTemp[dfTemp['primitive_type']==pr][['primitive_class', 'w']].groupby('primitive_class').sum()
        ax.set_title(pr)
        dfPlot['w'].plot(kind='barh', legend=False, alpha=0.5, ax=ax, color=color2)
        ax.axvline(0, lw=0.5, c='k')
        ax.grid(axis='x', ls='--')
        ax.set_ylabel('')
        xlim = max(0.12, max(np.abs(ax.get_xlim())))
        ax.set_xlim(left=-xlim, right=xlim)
        for i, v in enumerate(dfPlot['w'].values):
            ax.text(0, i, f"{v:+5,.1f}x", va='center', color='r' if v<0 else 'k', fontweight='bold')
    
    plt.show()
    
    #%%
    return [figPM, figRisk, figFX, figEqty, figIR]
#%%
if __name__ == "__main__":
    
    dt, str_fund = fu.get_config(['dt', 'str_fund_offshore'])
    nav = fu.get_NAV(dt, str_fund)
    
    figPM, figRisk, figFX, figEqty, figIR = main(dt, str_fund, nav)  
    
    #%%
    fig_file = '../output/temp_figs/offshore/{:%Y%m%d}_{}_varTrader.pdf'.format(dt, str_fund)
    figPM.savefig(fig_file,
                bbox_inches = 'tight', #facecolor='silver',
                pad_inches = 0)
    
    
    fig_file = '../output/temp_figs/offshore/{:%Y%m%d}_{}_varRisk.pdf'.format(dt, str_fund)
    figRisk.savefig(fig_file,
                bbox_inches = 'tight', #facecolor='silver',
                pad_inches = 0) 
    
    fig_file = '../output/temp_figs/offshore/{:%Y%m%d}_{}_deltaFX.pdf'.format(dt, str_fund)
    figFX.savefig(fig_file,
                bbox_inches = 'tight', #facecolor='silver',
                pad_inches = 0) 
    
    fig_file = '../output/temp_figs/offshore/{:%Y%m%d}_{}_deltaEquity.pdf'.format(dt, str_fund)
    figEqty.savefig(fig_file,
                bbox_inches = 'tight', #facecolor='silver',
                pad_inches = 0) 
    
    fig_file = '../output/temp_figs/offshore/{:%Y%m%d}_{}_deltaIR.pdf'.format(dt, str_fund)
    figIR.savefig(fig_file,
                bbox_inches = 'tight', #facecolor='silver',
                pad_inches = 0) 
    