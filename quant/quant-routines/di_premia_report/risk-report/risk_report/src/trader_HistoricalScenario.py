import numpy as np
import pandas as pd
import timeit
import datetime
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from scipy.stats import genpareto, norm, probplot
import scipy.optimize
import xlwings as xw
from adjustText import adjust_text
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
    
    dic_share = fu.get_DailyRiskShare(dt, str_fund).loc[dt].to_dict()

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
    df['Trader'] = df['book'].apply(lambda x: dic_trader[x])
    
    dts = []
    qldt = ql.Brazil().adjust(ql.Date(1,1,2007))
    while qldt <= ql.Date.from_date(dt):
        dts.append(qldt.to_date())
        qldt = ql.Brazil().advance(qldt, ql.Period('1d'))


    list_primitive_class = ['Equity', 'BRL Rate Curve', 'FX', 'IPCA Coupon', 'BRD Rate Curve']
    df = df[df['primitive_class'].isin(list_primitive_class)].copy()
    
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
    
    risks = []
    for risk_factor in df['Risk'].unique():
        dfOutput[risk_factor] = dfOutput[df[df['Risk']==risk_factor].index].sum(axis=1)
        risks.append(risk_factor)
    dfOutput['Fund'] = dfOutput[df.index].sum(axis=1)
    
    traders = []
    for t in df['Trader'].unique():
        dfOutput[t] = dfOutput[df[df['Trader']==t].index].sum(axis=1) / dic_share.get(t,1)
        traders.append(t)

 
    
    
    #%%
    fig, axes = plt.subplots(2,3,figsize=(14,7), sharex=True, sharey=False)
    fig.tight_layout()

    ax=axes[-1,-1]
    n, bins, _ = ax.hist(dfOutput['Fund']/nav, bins=50)
    ax.grid(ls='--')
    perc1 = dfOutput['Fund'].quantile(0.01)/nav
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
        SELECT tsv.date_reference, ts.entity_id, tsv.value/100 as ret_pct
        FROM quant.time_series_entity tse JOIN quant.time_series ts ON ts.entity_id = tse.id 
             JOIN quant.time_series_value tsv ON tsv.series_id = ts.id
        WHERE ts.field = 'CHG_PCT_1D' 
            and tsv.date_reference >= '2007-1-1' 
            and ts.entity_id in (SELECT distinct [entity_id]  FROM [middle].[product]
                    where [product_type] in ('Equity', 'Equity Index'))
    """
    df = pd.read_sql(str_sql, connection)
    dfRet = df.pivot(index='date_reference', columns='entity_id', values='ret_pct')
    dfRet = dfRet.rename(columns={'IBOV':'IBVSP'})
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
def calc_evt(dfReturn, col='Fund'):
    #%%
    def invFunc(y, f):
        func = lambda x: abs(f(x) - y)*10000
        fPrime = scipy.optimize.fmin(func=func, x0=0.5, disp=False)
        return fPrime[0]
    
    dfRet = dfReturn[[col]].copy()
    colors = fu.color_palette
    
    std = dfRet[col].ewm(alpha=0.06).vol().iloc[-1] 
    print("\nVaR (BPs) = {:3.1f}".format(10000 * norm.ppf(0.95, loc=0, scale=std)))

    fig, (ax1, ax3) = plt.subplots(1, 2, figsize=(10, 5), sharex=False, sharey=False)
#    plt.tight_layout()
    ax1.hist(dfRet[col] , bins=35, density=True, alpha=1, color="#5BC3F0")
    x = np.linspace(norm.ppf(0.0001, loc=0, scale=std), norm.ppf(0.9999, loc=0, scale=std), 100)
    ax1.plot(x, norm.pdf(x, loc=0, scale=std), 'r-', lw=2,  label='normal pdf')
    ax1.grid()
    (xmin, xmax) = ax1.get_xlim()
    xlim = max(-xmin, xmax)
    ax1.set_xlim(xmin=-xlim, xmax=xlim)
    ax1.set_xticklabels(['{:2.1%}'.format(x) for x in ax1.get_xticks()])
    ax1.set_title('Histogram')
    
    probplot(dfRet[col], dist="norm", plot=ax3)
    ax3.get_lines()[0].set_markerfacecolor("#5BC3F0")
    ax3.get_lines()[0].set_markeredgecolor("#5BC3F0")
    ax3.set_title('PP - Plot')
    ax3.set_yticklabels(['{:2.0%}'.format(x) for x in ax3.get_yticks()])
    ax3.grid()   
    # wb.sheets('EVT').pictures.add(fig, name='Normal_DataFit', update=True)
    plt.show()
    #%%
    threshold_pct = 95
    
    dfRet['Losses'] = abs(dfRet[col][dfRet[col] <= 0])
    u = np.percentile(dfRet['Losses'].fillna(0), threshold_pct)
    dfRet['Exceedances'] = dfRet['Losses'][dfRet['Losses'] > u]    
    
    fig = plt.figure(figsize=(10, 4))
    ax1 = plt.subplot2grid((2, 2), (0, 0), rowspan=2)
    ax2 = plt.subplot2grid((2, 2), (0, 1))
    ax3 = plt.subplot2grid((2, 2), (1, 1))
    plt.tight_layout()
    
    dfRet['Losses'].plot(ax=ax1, kind='area', grid=True, color=colors[1], alpha=0.6)
    ax1.axhline(u, c='k', lw=1.5, label='Threshold (u={:3.2%})'.format(u))
    ax1.set_xlim(xmin=dfRet.index[0], xmax=dfRet.index[-1])
    ax1.set_ylim(ymin=0)
    ax1.set_yticklabels(['{:2.1%}'.format(x) for x in ax1.get_yticks()])
    ax1.xaxis.label.set_visible(False)
    ax1.legend()
    
    _, bins, _ = ax2.hist(dfRet['Losses'][dfRet['Losses']>0].values , bins=30, alpha=0.8, color=colors[1])
    ax2.hist(dfRet['Exceedances'].dropna().values, bins=bins, color='tomato', label='Exceedances')
    
    ax2.axvline(u, c='k', lw=1.5, label='Threshold (u={:3.2%})'.format(u))
    ax2.set_xlim(xmin=0)
    ax2.set_xticklabels(['{:2.1%}'.format(x) for x in ax2.get_xticks()])
    ax2.grid()
    ax2.legend()

    e_u = []
    list_u = []
    for l in dfRet['Losses'].fillna(0).unique():
        list_u.append(l)
        e_u.append(np.mean(dfRet['Losses'][dfRet['Losses'] >= l]))
    
    ax3.plot(list_u, e_u, ls='', marker='.', color=colors[1], alpha=0.4)
    ax3.axvline(u, c='k', lw=1.5, label='Threshold (u={:3.2%})'.format(u))
    ax3.set_xlim(ax2.get_xlim())
    ax3.set_xlim(xmin=0)
    ax3.set_ylim(ymin=0)
    ax3.set_ylabel('Mean Excess')
    ax3.set_xticklabels(['{:2.1%}'.format(x) for x in ax3.get_xticks()])
    ax3.set_yticklabels(['{:2.0%}'.format(x) for x in ax3.get_yticks()])
    ax3.grid()
    ax3.legend()
    # wb.sheets('EVT').pictures.add(fig, name='EVT_Data', update=True)
    plt.show()

    #%%
    (c, loc, scale) = genpareto.fit(dfRet['Exceedances'].dropna().values, loc=u)
    gp = genpareto(c, loc, scale)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 3), sharex=False)
    fig.tight_layout(w_pad=2.5)
    ax1.hist(dfRet['Exceedances'].dropna(), bins=30, density=True, histtype='stepfilled', alpha=1, color=colors[1])
    x = np.linspace(gp.ppf(q=0.01), gp.ppf(q=0.99), 100)
    ax1.plot(x, gp.pdf(x), 'r-', lw=2,  label='Gen.Pareto pdf')
    ax1.set_title('Histogram / PDF')
    ax1.set_xlabel('Loss')
    ax1.set_ylabel('Frequency')
    ax1.legend()
    ax1.grid()
    ax1.set_xlim(xmin=0)
    ax1.set_xticklabels(['{:3.1%}'.format(x) for x in ax1.get_xticks()])
    
    Fu = dfRet.Exceedances.count()/dfRet[col].count()
    F = lambda x:Fu*(1-gp.cdf(x))
#    listProb = [1/21, 1/63, 1/126, 1/252, 1/504, 1/1260, 1/2520, 1/5040]
#    labelProb = ['1M', '3M', '6M', '1Y', '2Y', '5Y', '10Y', '20Y']
    listProb = [1/126, 1/252, 1/504, 1/1260, 1/2520, 1/5040]
    labelProb = ['6M', '1Y', '2Y', '5Y', '10Y', '20Y']
    ret=[]
    for q in listProb:
        ret.append(invFunc(q, F) + u)    
    probplot(dfRet['Exceedances'].dropna().values, dist=gp, plot=ax2, fit=False)
    ax2.get_lines()[0].set_markerfacecolor(colors[1])
    ax2.get_lines()[0].set_markeredgecolor(colors[1])
    ax2.set_yticklabels(['{:2.1%}'.format(x) for x in ax2.get_yticks()])
    ax2.grid()
    
    # wb.sheets('EVT').pictures.add(fig, name='EVT_DataFit', update=True)
    plt.show()
    
    #%%
    fig, ax = plt.subplots(1, 1, figsize=(10, 4), sharex=False)
    ax.semilogy(ret, listProb, marker='o', color=colors[0], zorder=10)
    ax.set_xlim(xmin=u)
    ax.set_ylim(ymin=0.009/100)
    ax.set_xlabel('Loss')
    ax.set_ylabel('Log-Probability')
    texts = []
    for i, q in enumerate(listProb):
        texts.append(ax.text(ret[i], q, \
                     ' {:3.2%}, '. format(ret[i]) + labelProb[i], size=12,\
                    bbox=None if i!=4 else {'facecolor':'none', 'alpha':0.9, \
                                            'boxstyle': 'round', 'pad':1,\
                                            'edgecolor':'red', 'linewidth':3}))
    ax.set_xticklabels(['{:1.0%}'.format(x) for x in ax.get_xticks()])
    ax.set_yticklabels(['{:3.2%}'.format(x) for x in ax.get_yticks()])
    ax.grid()
    ax.legend(['Loss, Frequency'])
    adjust_text(texts)
    # wb.sheets('EVT').pictures.add(fig, name='EVT_VaR', update=True)
    plt.show()

    #%%
    return False

#%%
if __name__ == "__main__":
    
    _ , connection = fu.get_DB_conn('prod')
   
    tic = timeit.default_timer()
    
    dt = datetime.date(2021, 10, 20)
    str_fund = 'A1 Master FIM'
    nav = fu.get_NAV(dt, str_fund)
    report_filename = '../xls/RiskMap_model.xlsm'
    a = main(dt, str_fund, nav, report_filename) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))   
    del tic, tac
    
