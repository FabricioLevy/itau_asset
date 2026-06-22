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

def get_equity_returns(connection, date_reference, equities):
    
    str_sql = """
        SELECT tsv.date_reference, p.lote45_product, tsv.value/100 as ret_pct
        FROM [middle].[product] p 
             JOIN quant.time_series_entity tse ON p.entity_id = tse.id
             JOIN quant.time_series ts ON ts.entity_id = tse.id 
             JOIN quant.time_series_value tsv ON tsv.series_id = ts.id
        WHERE ts.field = 'CHG_PCT_1D' 
            and tsv.date_reference >= '2019-1-1' 
            and [product_type] in ('Equity', 'Equity Index', 'Commodity')
    """
    df = pd.read_sql(str_sql, connection)
    dfRet = df.pivot(index='date_reference', columns='lote45_product', values='ret_pct')
    dfRet = dfRet[equities]
    
    str_sql = """
        SELECT [primitive1],[primitive2],[covar_value]
        FROM [lote45].[covar_matrix]
        WHERE date_reference = '{:%Y-%m-%d}' 
        ORDER BY 1, 2
        """
    str_sql = str_sql.format(date_reference)
    dfCovarDB = pd.read_sql(str_sql, connection).pivot(index='primitive1', columns='primitive2', values='covar_value').fillna(0)
    dfBeta = pd.DataFrame((dfCovarDB['IBVSP'] + dfCovarDB.loc['IBVSP']) / dfCovarDB.loc['IBVSP', 'IBVSP'])
    dfBeta = dfBeta.loc[equities]
    dfBeta.loc['IBVSP'] = 1
    
    dfBetaRet = pd.DataFrame(dfRet['IBVSP'].T) @ (dfBeta.T)
    
    dfRet = dfRet.fillna(dfBetaRet)
    
    return dfRet


#%%
def main(dt, str_fund, nav, report_filename=None):
#%%
    _ , connection = fu.get_DB_conn('prod')
    
    dic_share = fu.get_DailyRiskShare(dt, str_fund).loc[dt].to_dict()
    list_trader = ['MS', 'BC', 'FK', 'PC', 'TO', 'PA', 'Fund']

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
    dfPos['Fund'] = dfPos.sum(axis=1)
    for t in dfPos.columns:
        dfPos[t] /= dic_share[t] * nav
        
    to_remove = ['Iron Ore SGX Syn.', 'RIO LN']
    dfPos = dfPos.loc[[i for i in dfPos.index if i not in to_remove]]
    # str_sql = """
    #     SELECT tsv.date_reference, ts.entity_id as product_id, ts.field, tsv.value   
    #     FROM quant.time_series_entity tse JOIN quant.time_series ts ON ts.entity_id = tse.id 
    #          JOIN quant.time_series_value tsv ON tsv.series_id = ts.id
    #     WHERE ts.field = 'CHG_PCT_1D'
    #         and tsv.date_reference >= '2017-1-1' 
    #         and ts.entity_id in (SELECT distinct [entity_id]  FROM [middle].[product]
    #                 where [product_type] in ('Equity', 'Equity Index', 'Commodity'))
    # """
    # df = pd.read_sql(str_sql, connection)
    # df = df.replace({'IBOV':'IBVSP'})
    # dfRet = df[df['field']=='CHG_PCT_1D'].pivot(index='date_reference', columns='product_id', values='value')
    # dfRet = dfRet[[i for i in dfPos.index if i in dfRet.columns]]/100
    
    dfRet = get_equity_returns(connection, dt, [i for i in dfPos.index if i not in to_remove])
    
    # for c in dfRet.columns:
    #     if c in dfPos.index:
    #         ind_x = dfRet[c].first_valid_index()
    #         if ind_x == None:
    #             ind_x = dfRet[c].index[0]
    #         dfRet.loc[ind_x:, c].fillna(0, inplace=True)
    #         dfRet[c].iloc[max(0, list(dfRet.index).index(ind_x)-1)]=0
        
        
    dfRetAcum = (dfRet+1).cumprod() - 1
    
    dfRetAcum.sort_index(inplace=True)

    # connection.close()
    del str_sql
#%%
    t='FK'
    dfPosAdj = pd.DataFrame(0, index=dfPos.index, columns=dfPos.columns)
    dfPosAdj.loc[dfPos[t]>0, t] = dfPos.loc[dfPos[t]>0, t] * (0.7/dfPos.loc[dfPos[t]>0, t].sum())
    dfPosAdj.loc[dfPos[t]<0, t] = dfPos.loc[dfPos[t]<0, t] * (-0.7/dfPos.loc[dfPos[t]<0, t].sum())
    
    dfResult = pd.DataFrame(0, index=dfRet.index, columns=dfPos.columns)
    dfResult[t] = dfRet.fillna(0) @ dfPosAdj[t].T
    
    dfRetAcum = (dfResult[[t]]+1).cumprod()-1

#%%
    fig, (ax1,ax2,ax3) = plt.subplots(3, 1, figsize=(10,8), gridspec_kw = {'height_ratios':[3,2,3]}, sharex=True)
    dfRetAcum[t].plot(ax=ax1)
    ax1.set_xlim(left=dfResult.index[0])
    ax1.set_ylabel('Ret Acum (%)')
    
    dfRetAcum['HWM']=dfRetAcum[t].expanding().max()
    dfRetAcum['DD'] =  (1+dfRetAcum[t]) / (1+dfRetAcum['HWM']) - 1
    dfRetAcum['DD'].plot(ax=ax2, color='tomato')
    ax2.fill_between(dfRetAcum.index, dfRetAcum['DD'], 0, color='r', alpha=0.3)
    ax2.set_ylim(top=0)
    ax2.set_ylabel('DD (%)')
    
    (dfResult[t].rolling(63).std() * np.sqrt(252)).plot(ax=ax3)
    ax3.set_ylim(bottom=0)
    ax3.set_ylabel('VOL 3M(%)')
    
    for ax in (ax1, ax2, ax3):
        ax.grid(ls='--')
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1, 1)) 
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b-%y'))
    
    ax1.set_title(f'Carteira {t} - {dt:%d-%b-%y} - Gross 140% / Net 0%')
    fig.align_ylabels((ax1, ax2, ax3))
    
    fig.savefig(f'R:/Public/Risco/Eqty/simu_{t}_{dt:%Y%m%d}.pdf', bbox_inches = "tight")
    
    plt.show()
    
#%%
if __name__ == "__main__":

   
    dt = datetime.date(2021, 11, 9)
    str_fund = 'A1 Master FIM'
    nav = fu.get_NAV(dt, str_fund)
    main(dt, str_fund, nav) 
    
  