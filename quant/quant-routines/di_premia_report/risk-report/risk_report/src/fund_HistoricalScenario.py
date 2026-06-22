import pandas as pd
import timeit
import datetime
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import QuantLib as ql
import fund_utils as fu


#%%
def main(dt, str_fund, nav, report_filename):
    #%%
    _, connection = fu.get_DB_conn('prod')
    
    str_sql = """
        SELECT *
        --[lote45_product],[lote45_product_class]
          --      [primitive],[primitive_class], bucket
           --     [amount],[delta], gamma, vega
                FROM [lote45].[primitive]
                WHERE date_reference = '{:%Y-%m-%d}' and trading_desk = '{}'
                """
    str_sql = str_sql.format(dt, str_fund)
    df = pd.read_sql(str_sql, connection)

    dic_book, dic_trader = {}, {}
    
    for d, str_tree in zip([dic_book, dic_trader] ,['Risk', 'Traders']):
        str_sql = """
           SELECT [parent_tree],[parent_node],[node],[book]
           FROM [lote45].[book_tree]
           WHERE parent_tree = '{}'
                    """
        dfTree = pd.read_sql(str_sql.format(str_tree), connection)
        nd = fu.Node(str_tree, dfTree)    
        d = d.update(nd.to_inv_dict(str_tree))    
   
    del str_sql, d, str_tree, nd

    #%%
    currencies = [i[:6] for i in df[(df['primitive_class']=='FX')]['primitive'].unique()]
    equities = sorted(df[(df['primitive_class']=='Equity')]['primitive'].unique())
    lote45_rates = ['BRL Rate Curve','IPCA Coupon','BRD Rate Curve']
    rates = sorted(df[(df['primitive_class'].isin(lote45_rates))]['primitive'].unique())
    

    df['Risk'] = df['book'].apply(lambda x: dic_book[x])
    df['Trader'] = df['book'].apply(lambda x: dic_book[x])
    
    dts = []
    qldt = ql.Brazil().adjust(ql.Date(1,1,2007))
    while qldt <= ql.Date.from_date(dt):
        dts.append(qldt.to_date())
        qldt = ql.Brazil().advance(qldt, ql.Period('1d'))

        
    # dfPosCpCambial = df[df['primitive_class']=='BRD Rate Curve'][['lote45_product','primitive','eq_position']].copy()
    # dfPosCpCambial['maturity'] = dfPosCpCambial['lote45_product'].apply(lambda x: dic_prod.get(x,'dolfut'))
    # rates_cpcambial = list(dfPosCpCambial['primitive'].unique())
    # dfRetCpCambial = pd.DataFrame(index=dts).join(get_curve_returns(connection, rates_cpcambial)).fillna(0)
    # dfScenarios = pd.DataFrame(index=dts, columns=list(dfPosCpCambial['maturity'].unique()))
    # for i_scenario, date_scenario in enumerate(dts):
    #     dfTemp = dfPosCpCambial.join(dfRetCpCambial.loc[date_scenario], on='primitive')
    #     dfTemp['PnL'] = dfTemp['eq_position']*dfTemp[date_scenario]
    #     dfAux = pd.DataFrame(dfTemp[['maturity', 'PnL']].groupby(['maturity']).sum())
    #     dfScenarios.loc[date_scenario, dfAux.index] = dfAux.T[dfAux.index].values
    # dfScenarios = dfScenarios[[dfScenarios.columns[-1]] + sorted(dfScenarios.columns[:-1])]
    # (dfScenarios/nav).to_excel('5fev_scenarios.xlsx')
    
    list_eqty = ['SCCO']
    for eq in list_eqty:
        equities.remove(eq)
    df = df[~df['primitive'].isin(list_eqty)]
        
    list_primitive_class = ['Equity', 'BRL Rate Curve', 'FX', 'IPCA Coupon', 'BRD Rate Curve']
    df = df[df['primitive_class'].isin(list_primitive_class)]
    


    dfRet = pd.DataFrame(index=dts)
    dfRet = dfRet.join(get_curve_returns(connection, rates))
    dfRet = dfRet.join(get_equity_returns(connection, dt, equities))
    dfRet = dfRet.join(get_fx_returns(connection, currencies))
    
    dfOutput = pd.DataFrame(index=dfRet.index, columns=df.index)
    
    for i in df.index:
        for dt_i in dfRet.index:
            primitive = df.loc[i, 'primitive']
            dfOutput.loc[dt_i, i] = dfRet.loc[dt_i, primitive] * df.loc[i, 'eq_position'] +\
                0.5 * df.loc[i, 'gamma'] * (dfRet.loc[dt_i, primitive]**2)
    
    
    for risk_factor in df['Risk'].unique():
        dfOutput[risk_factor] = dfOutput[df[df['Risk']==risk_factor].index].sum(axis=1)
    dfOutput['TOTAL'] = dfOutput[df.index].sum(axis=1)

    # dfPosPRE = df[df[str_tree]=='INFLATION'][['lote45_product','primitive','eq_position']].copy()
    # dfScenarios = pd.DataFrame(index=dts, columns=list(dfPosPRE['lote45_product'].unique()))
    # for i_scenario, date_scenario in enumerate(dts):
    #     dfTemp = dfPosPRE.join(dfRet.loc[date_scenario], on='primitive')
    #     dfTemp['PnL'] = dfTemp['eq_position']*dfTemp[date_scenario]
    #     dfAux = pd.DataFrame(dfTemp[['lote45_product', 'PnL']].groupby(['lote45_product']).sum())
    #     dfScenarios.loc[date_scenario, dfAux.index] = dfAux.T[dfAux.index].values
    # dfScenarios['TOTAL'] = dfScenarios.sum(axis=1)
    


    # dic_returns = {}
    # dfScenarios = pd.DataFrame(index=dts, columns=['PnL'])
    # for i_scenario, date_scenario in enumerate(dts):
    #     dfTemp = df.join(dfRet.loc[date_scenario], on='primitive')
    #     dfTemp['PnL'] = (dfTemp['eq_position']*dfTemp[date_scenario] + 0.5 * dfTemp['gamma'] * (dfTemp[date_scenario]**2)) / nav
    #     dic_returns[date_scenario] = pd.DataFrame(dfTemp[[str_tree, 'PnL']].groupby([str_tree]).sum())
    #     dfScenarios.loc[date_scenario, 'PnL'] = dfTemp['PnL'].sum()

    
    
    #%%

    fig, axes = plt.subplots(2,3,figsize=(14,7), sharex=True, sharey=False)
    fig.tight_layout()

    ax=axes[-1,-1]
    n, bins, _ = ax.hist(dfOutput['TOTAL']/nav, bins=50)
    ax.grid(ls='--')
    perc1 = dfOutput['TOTAL'].quantile(0.01)/nav
    ax.annotate('Perc 1%\n{:4.2%}'.format(perc1), 
                              xy=(0, 0), xycoords='data', zorder=3,
                          xytext=(0.85, 0.85), textcoords='axes fraction', fontweight='bold',
                          fontsize=12, color='k', ha='center',
                          bbox=dict(boxstyle="round", fc='r', ec="0.5", alpha=0.8))
    ax.set_title('TOTAL', fontweight='bold')
    ax.xaxis.set_major_formatter(ticker.PercentFormatter(xmax=1, decimals=1))
    ax.set_facecolor('lightgrey')    
    for i, (dt_j, j) in enumerate(dfOutput['TOTAL'].sort_values().reset_index().head(3).values):
            ax.annotate('{:%d%b%y}: {:4.2%}'.format(dt_j, j/nav), 
                              xy=(j/nav, 0), xycoords='data', zorder=3,
                          xytext=(0.25, 0.85-i/8), textcoords='axes fraction', fontweight='bold',
                          fontsize=11, color='k', ha='center',
                          bbox=dict(boxstyle="round", fc='tomato', ec="0.5", alpha=0.8),
            arrowprops=dict(facecolor='r', arrowstyle="->", connectionstyle="arc3"))

    for ax, risk_factor in zip(axes.flatten(), ['BOLSA', 'FX', 'INFLATION', 'CUPOM CAMBIAL', 'PRE']):
        ax.set_title(risk_factor, fontweight='bold')
        ax.hist(dfOutput[risk_factor]/nav, bins=bins, zorder=3, alpha=0.7)
        ax.grid(ls='--')
        
        perc1 = dfOutput[risk_factor].quantile(0.01)/nav
        ax.annotate('Perc 1%\n{:4.2%}'.format(perc1), 
                              xy=(0, 0), xycoords='data', zorder=3,
                          xytext=(0.85, 0.85), textcoords='axes fraction', fontweight='bold',
                          fontsize=12, color='k', ha='center',
                          bbox=dict(boxstyle="round", fc='r', ec="0.5", alpha=0.8))
        
        for i, (dt_j, j) in enumerate(dfOutput[risk_factor].sort_values().reset_index().head(3).values):
            ax.annotate('{:%d%b%y}\n{:4.2%}'.format(dt_j, j/nav), 
                              xy=(j/nav, 0), xycoords='data', zorder=3,
                          xytext=(0.38 if i==1 else 0.125, 0.85-i/8), textcoords='axes fraction', fontweight='bold',
                          fontsize=10, color='k', ha='center',
                          bbox=dict(boxstyle="round", fc='tomato', ec="0.5", alpha=0.8),
            arrowprops=dict(facecolor='r', arrowstyle="->", connectionstyle="arc3"))
    
    fig.suptitle('Simulações Históricas - {:1.0f} dias ({:%b%Y}~{:%b%Y})'.format(len(dfOutput), dfOutput.index[0], dfOutput.index[-1]), 
                 fontsize=16, y=1.06, fontweight='bold')
    plt.show()
    fig_file = '../output/temp_figs/{:%Y%m%d}_historical_simulation.svg'.format(dt)
    fig.savefig(fig_file, bbox_inches = "tight")
    
    #%%
    connection.close()
    return [dfOutput.copy(), df.copy()]
    
#%%
def get_fx_returns(connection, currencies):
    
    str_sql = """
        SELECT ts.entity_id + 'Spot' as primitive, tsv.date_reference, tsv.value
        FROM quant.time_series_entity tse 
    		INNER JOIN quant.time_series ts ON ts.entity_id = tse.id 
            JOIN quant.time_series_value tsv ON tsv.series_id = ts.id
        WHERE ts.field = 'PX_LAST' 
        AND tsv.date_reference > '2007-1-1' 
        AND tse.id in ('{}')
    """
    str_sql = str_sql.format("','".join(currencies))
    df = pd.read_sql(str_sql, connection)
    dfRet = df.pivot(index='date_reference', columns='primitive', values='value').pct_change().fillna(0)
    
    
    return dfRet
#%%
def get_equity_returns(connection, date_reference, equities):
    
    str_sql = """
        SELECT tsv.date_reference, p.lote45_product, tsv.value/100 as ret_pct
        FROM [middle].[product] p 
             JOIN quant.time_series_entity tse ON p.entity_id = tse.id
             JOIN quant.time_series ts ON ts.entity_id = tse.id 
             JOIN quant.time_series_value tsv ON tsv.series_id = ts.id
        WHERE ts.field = 'CHG_PCT_1D' 
            and tsv.date_reference >= '2007-1-1' 
            and [product_type] in ('Equity', 'Equity Index')
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
def get_curve_returns(connection, rates):
    
    curves = ['DI Fut', 'NTNB Zero', 'USD BR']
    lote45_curves = ['DI_', 'IPCA_COUPON_', 'BRD_']
    dic_curve = dict(zip(curves, lote45_curves))
    
    str_sql = """
       SELECT [date_reference],[curve_name],[tenor],[discount_factor]
       FROM [risk].[interest_rate_curve]
       WHERE tenor is not null and date_reference >= '2007-1-1' 
           AND curve_name in ('{}') 
    """
    str_sql = str_sql.format("','".join(curves))
    df = pd.read_sql(str_sql, connection)
    df['primitive'] = df['curve_name'].apply(lambda x: dic_curve[x]) + df['tenor'].apply(lambda x: '{:05.0f}'.format(x))
    df = df[df['primitive'].isin(rates)]
    dfRet = df.pivot(index='date_reference',  columns='primitive', values='discount_factor').fillna(method='ffill')
    dfRet = dfRet.pct_change().fillna(0)
    return dfRet
#%%
if __name__ == "__main__":
    
    _ , connection = fu.get_DB_conn('prod')
   
    tic = timeit.default_timer()
    
    dt = datetime.date(2021, 8, 13)
    str_fund = 'A1 Master FIM'
    nav = fu.get_NAV(dt, str_fund)
    report_filename = '../xls/RiskMap_model.xlsm'
    a = main(dt, str_fund, nav, report_filename) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))   
    del tic, tac
