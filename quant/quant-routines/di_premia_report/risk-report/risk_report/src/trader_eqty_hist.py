import pandas as pd
import numpy as np
import datetime
import timeit
from scipy.cluster.hierarchy import dendrogram, linkage, distance, fcluster
import matplotlib.pyplot as plt
from matplotlib import cm
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
import xlwings as xw
import fund_utils as fu
import seaborn as sns


#%%
def main(dt, str_fund, nav, report_filename):
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
    dfPos = dfPos.pivot_table(index='primitive', columns=['trader', 'book'], values='delta', aggfunc=np.sum).fillna(0)
    dfPos['Fund'] = dfPos.sum(axis=1)
   
        
    str_sql = """
        SELECT [product_id],[b3_sector],[b3_subsector],[b3_segment],[a1_sector] as sector
            FROM [b3].[sector_classification]    
    """    
    dfClassif = pd.read_sql(str_sql, connection, index_col='product_id')
    dfClassif['sector'].replace({'Transportation/Travel':'Transp./Travel'}, inplace=True)
    
      
    str_sql = """
        SELECT tsv.date_reference, ts.entity_id as product_id, ts.field, tsv.value   
        FROM quant.time_series_entity tse JOIN quant.time_series ts ON ts.entity_id = tse.id 
             JOIN quant.time_series_value tsv ON tsv.series_id = ts.id
        WHERE ts.field in ('CHG_PCT_1D','TURNOVER') 
            and tsv.date_reference >= '{:%Y-%m-%d}' 
            and ts.entity_id in (SELECT distinct [entity_id]  FROM [middle].[product]
                    where [product_type] in ('Equity', 'Equity Index', 'Commodity'))
    """
    str_sql = str_sql.format(datetime.date(2007,1,1))
    df = pd.read_sql(str_sql, connection)
    df = df.replace({'IBOV':'IBVSP'})
    
    dfRet = df[df['field']=='CHG_PCT_1D'].pivot(index='date_reference', columns='product_id', values='value').loc[:dt]
    dfRet = dfRet[[i for i in dfPos.index if i in dfRet.columns]]/100

    for c in dfRet.columns:
        if c in dfPos.index:
            ind_x = dfRet[c].first_valid_index()
            if ind_x == None:
                ind_x = dfRet[c].index[0]
            dfRet.loc[ind_x:, c].fillna(0, inplace=True)
            dfRet[c].iloc[max(0, list(dfRet.index).index(ind_x)-1)]=0
        
        
    dfRetAcum = (dfRet+1).cumprod() - 1
    dfRetAcum.sort_index(inplace=True)
    

    dic_share = fu.get_DailyRiskShare(dt, str_fund).loc[dt].to_dict()
    list_trader = ['MS', 'BC', 'FK', 'TO', 'PA', 'Fund']

    connection.close()
    del str_sql

#%%
    ic_var = 1.64485362695147
    str_benchmark = 'IBVSP'
    
    X = dfCovarDB.values
    X = np.triu(X) + np.tril(X, -1).T
    dfCovar = pd.DataFrame(np.triu(X) + np.tril(X.T, -1), columns=dfCovarDB.index, index=dfCovarDB.index)
    dfCovar = pd.DataFrame(columns=dfPos.index, index=dfPos.index).fillna(dfCovar).fillna(0.001)
    dfCovar = dfCovar[dfPos.index].loc[dfPos.index]
    covar = dfCovar.values
    var_bechmark = dfCovar.loc[str_benchmark,str_benchmark]
    dfBetas = dfCovar.loc[str_benchmark]/var_bechmark
    D = 1/np.sqrt(np.diag(covar))
    correl = np.diag(D) @ covar @ np.diag(D)
    dfCorrel = pd.DataFrame(correl, index=dfPos.index, columns=dfPos.index)
    
    dfRetAdj = dfRet[[str_benchmark for b in dfBetas.index]] * dfBetas.T.values
    dfRetAdj.columns = dfBetas.index
    
    dfRet = dfRet.fillna(dfRetAdj)
    
#%%
    t = 'TO'
    risk_share = dic_share[t]
    
    tempPos = dfPos[dfPos[t] != 0.0][[t]].dropna(how='all').fillna(0).sum(axis=1)
    tempCorrel = dfCorrel.loc[tempPos.index, tempPos.index]
    tempCovar = dfCovar.loc[tempPos.index, tempPos.index]
    tempRet = dfRet[tempPos.index]
    tempEWMA = tempRet.ewm(alpha=0.06).cov()
    tempvol12m= tempRet.rolling(252).cov()
    


#%%
    # xx = ['BEEF3', 'GGBR4', 'JBSS3', 'USIM5', 'VALE3']
    # corr = tempCorrel.loc[xx,xx] * 100    
    corr = tempCorrel * 100    
    fig, ax = plt.subplots(figsize=(12, 8))
    plt.tight_layout()
    mask = np.zeros_like(corr, dtype=np.bool)
    mask[np.triu_indices_from(mask)] = False
    cmap = sns.diverging_palette(10, 260, n=15, as_cmap=True)
    sns.heatmap(corr, mask=mask, cmap=cmap, vmax=80, vmin=-80, center=0, fmt='2.0f',\
                square=False, linewidths=.5, annot = True, cbar=False, ax=ax)
    ax.yaxis.label.set_visible(False)
    ax.xaxis.label.set_visible(False)
    # fig.savefig('corr.svg', bbox_inches = "tight")    
#%%
    temp_color = list(plt.cm.get_cmap('tab20').colors)
    dic_color = {a:b for a,b in zip(list(dfClassif['sector'].dropna().unique()), temp_color)}
    dfClassif['color'] = dfClassif['sector'].apply(lambda x: dic_color.get(x, 'k'))

    corr_condensed = distance.squareform((np.round(1-tempCorrel,6))) # convert to condensed
    z = linkage(corr_condensed, method='average')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12,6), gridspec_kw={'height_ratios': [2, 1]}, sharex=True)
    fig.tight_layout(h_pad=3.5)
    
    dd = dendrogram(z, labels=tempCorrel.index, ax=ax1)
    dic_cluster = {i:[x] for i, x in enumerate(tempPos.index)}
    
    for i, (a, b, _, _) in enumerate(z, len(z)+1):
        dic_cluster[i] = dic_cluster[a] + dic_cluster[b]
    
    l_risks = dd['ivl']
    # tempPos = tempPos.loc[l_risks]
    # tempCovar = tempCovar.loc[l_risks, l_risks]
    for j, w, x in zip(tempPos.loc[l_risks].index, tempPos.loc[l_risks].values, ax1.get_xticks()):
        var = np.sqrt(dfCovar.loc[j, j]) * abs(w) * ic_var/nav/risk_share*10_000
        ax1.annotate("{:1.0f}".format(var), (x, 0), xytext=(0, 0), fontweight='bold',
                     textcoords='offset points', fontsize=8,
                     va='bottom', ha='center')
    
    sorted_index = [dd['dcoord'].index(x) for x in sorted(dd['dcoord'], key=lambda x:x[1])]
    for j, idx in enumerate(sorted_index, len(z)+1):
        (i, d) = dd['icoord'][idx], dd['dcoord'][idx]
        x = 0.5 * sum(i[1:3])
        y = d[1]
        
        w = tempPos.loc[dic_cluster[j]].values
        cov = dfCovar.loc[dic_cluster[j], dic_cluster[j]].values
        var =  np.sqrt(w.T @ cov @ w) * ic_var/nav/risk_share*10_000
        
        # ax1.plot(x, y, 'ro')
        ax1.annotate("{:1.0f}".format(var), (x, y), xytext=(0, 0),
                     textcoords='offset points', fontweight='bold',
                     va='bottom', ha='center')
    
    ax1.set_yticklabels([])
    ax1.axes.get_xaxis().set_visible(False)
    ax1.grid(ls='--')

    ax2.axhline(0, lw=0.5, c='k')
    ax2.grid(ls='--')
    ax2.xaxis.set_ticks_position('top') 
    for j, x in zip(tempPos.loc[l_risks].values/nav/risk_share, ax1.get_xticks()):
        ax2.bar([x], [j], width=5, color='tomato' if j<0 else 'royalblue', zorder=5)
        ax2.text(x, max(0,j), '{:1.1f}'.format(100*j), ha='center', va='bottom', fontsize=8,
                 color='k' if j>0 else 'r', fontweight='bold', zorder=5)
        
        # ax2.scatter(x, j, color='tomato' if j<0 else 'royalblue', zorder=5)
    ax2.set_xticklabels([i[:6] for i in l_risks], rotation=90, fontsize=8, fontweight='bold')

    ax2.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1, decimals=0))
    ax2.set_ylim(top=ax2.get_ylim()[1]*1.2)
    
    vols = np.diag(tempCovar)
    fig.savefig('hc.svg', bbox_inches = "tight")    
    plt.show()
    
    corr = tempCorrel.loc[l_risks,l_risks] * 100    
    fig, ax = plt.subplots(figsize=(12, 10))
    plt.tight_layout()
    mask = np.zeros_like(corr, dtype=np.bool)
    mask[np.triu_indices_from(mask)] = False
    cmap = sns.diverging_palette(10, 260, n=15, as_cmap=True)
    sns.heatmap(corr, mask=mask, cmap=cmap, vmax=80, vmin=-80, center=0, fmt='2.0f',\
                square=False, linewidths=.5, annot = False, cbar=False, ax=ax)
    ax.yaxis.label.set_visible(False)
    ax.xaxis.label.set_visible(False)    
#%%

    w = tempPos.values
    dfOutput = pd.DataFrame(index=tempRet.index, columns=['VaR_EWMA', 'VaR_VOL1Y', 'HypoPnL'])
    for dti in dfOutput.index:
        cov = tempEWMA.loc[dti].fillna(0)
        var =  np.sqrt(w.T @ cov @ w) * 1.645/nav/risk_share*10_000
        dfOutput.loc[dti, 'VaR_EWMA'] = var
        
        cov = tempvol12m.loc[dti].fillna(0)
        var =  np.sqrt(w.T @ cov @ w) * 1.645/nav/risk_share*10_000
        dfOutput.loc[dti, 'VaR_VOL1Y'] = var
    dfOutput['HypoPnL'] = tempRet.shift(-1).values @ tempPos.values /nav/risk_share*10_000
    
    dfOutput['Backtest_EWMA'] = 0
    dfOutput['Backtest_Vol1Y'] = 0    
    dfOutput.loc[dfOutput['HypoPnL']<-dfOutput['VaR_EWMA'],'Backtest_EWMA']= 1
    dfOutput.loc[dfOutput['HypoPnL']<-dfOutput['VaR_VOL1Y'],'Backtest_Vol1Y']= 1
    
    dfOutput = dfOutput.loc[datetime.date(2008,1,1):]
    
    
    dfOutput[['Backtest_Vol1Y', 'Backtest_EWMA']].sum() / len(dfOutput)
    
#%%
    fig, ax = plt.subplots(1,1,figsize=(12,6))
    ax.plot(dfOutput.index, dfOutput['VaR_EWMA'], lw=3, label='VaR Vol EWMA (BPs)', color='tomato')
    ax.plot(dfOutput.index, dfOutput['VaR_VOL1Y'], lw=3, label='VaR Vol 1Y (BPs)', color='royalblue', ls='--')
    # ax.scatter(dfOutput.index, -dfOutput['HypoPnL'], marker='.', label='PnL', color='k')
    ax.grid(ls='--')
    ax.legend()
    ax.axhline(0, c='k', lw=0.5)
    ax.set_title('VaR - {} - Carteira de {:%d-%b-%y} e vols/correls passadas'.format(t, dt))
    plt.show()
   
    
#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
  
    dt = datetime.date(2022, 1, 4)
    str_fund = 'A1 Master FIM'
    # str_fund = 'A1 FIFE BEM'
    report_filename = '../xls/RiskMap_model.xlsm'
    nav = fu.get_NAV(dt, str_fund)
    main(dt, str_fund, nav, report_filename) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))
    del tic, tac
