# -*- coding: utf-8 -*-
"""
Created on Thu Aug 11 11:58:58 2022

@author: matheus.amaral
"""

import pandas as pd
import timeit
import datetime
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import xlwings as xw
import fund_utils as fu
import QuantLib as ql


def main(dt):
    dt_d1 = ql.Brazil().advance(ql.Date.from_date(dt), ql.Period('-1d')).to_date()
    
    _, connection = fu.get_DB_conn('prod')
    
    str_sql = f"""SELECT risk_measure, [value]/n.NAV as value,
                    v.trading_desk  
                  FROM [risk].[measure] v 
                    INNER JOIN middle.NAV n ON v.date_reference = n.date_reference 
                                           and v.trading_desk = n.trading_desk  
                  WHERE parent_tree = 'Fund' 
                       and v.date_reference='{dt:%Y-%m-%d}'
                """
                
    df = pd.read_sql(str_sql, connection)
    dfRisk = df.pivot(index='risk_measure', columns='trading_desk', values='value')
    dfRisk.loc['VaR'] *= -10000
    
    str_sql = """ SELECT p.date_reference,p.book, p.trading_desk, primitive_class, primitive, bucket, 
                        SUM(delta/n.nav) as delta
                FROM [lote45].[primitive] p INNER JOIN middle.NAV n ON p.date_reference=n.date_reference
                        AND n.trading_desk = p.trading_desk
                WHERE p.date_reference in ('{:%Y-%m-%d}','{:%Y-%m-%d}') 
                    AND lote45_product_class <> 'CPM Options - BMF'
                    AND p.trading_desk != 'A1 Hedge SP'
                GROUP BY p.date_reference,p.book, p.trading_desk, primitive_class, primitive,bucket
    """    
    str_sql = str_sql.format(dt, dt_d1)
    df = pd.read_sql(str_sql, connection)
    
    str_tree = 'Risk'
    str_sql = f"""
            SELECT *
            FROM [lote45].[book_tree]
            WHERE parent_tree = '{str_tree}'
            """    
    tree = fu.Node(str_tree, pd.read_sql(str_sql, connection))
    dic_books = tree.to_inv_dict(str_tree)
    df[str_tree] = df['book'].apply(lambda x: dic_books[x])
    df.drop('book', axis=1, inplace=True)
    
    connection.close()
    del str_sql
    
    #%%
    
    df['primitive_class'] = df.apply(lambda x: 'BRL Rate Curve INFL' if (x['primitive_class']=='BRL Rate Curve' and x['Risk']=='INFLATION') else x['primitive_class'], axis=1)
    
    for primitive in ['USA Sovereign Yield', 'USD Rate Curve']:
        
        df.loc[df['primitive_class'] == primitive, 'primitive_class'] = 'USD Yield/Rate Curve'
        
    for primitive in ['Japan Sovereign Yield']:
        df.loc[df['primitive_class'] == primitive, 'primitive_class'] = 'JPY Yield/Rate Curve'
        
    lote45_primitives = ['BRL Rate Curve', 'BRL Rate Curve INFL', 'IPCA Coupon', 'BRD Rate Curve', 
                         'MXN Rate Curve','USD Yield/Rate Curve', 'JPY Yield/Rate Curve']
    dic_buckets = {}
    dic_buckets_groups = {}
    
    f = lambda x, l: [n for n,i in enumerate(l) if i>=x][0]
    for (group_name, bucket_group, bucket_time) in zip(['default', 'BRD Rate Curve', 'USD Yield/Rate Curve', 'MXN Rate Curve', 'JPY Yield/Rate Curve'],
                                                             [['<6M', 'UpTo2Y','>2Y'], ['<6M', 'UpTo3Y','3Y~6Y','>6Y'], ['<1.5Y','<5Y','5Y~10Y','>10Y'], ['<2Y','2Y~5Y','5Y~10Y', '>10Y'], ['<2Y','2Y~5Y','5Y~10Y', '>10Y']],
                                                             [[180, 720, 99999], [180, 1080, 2160, 99999], [1800, 3600, 99999],[720, 1800, 3600, 99999],[720, 1800, 3600, 99999], [540, 99999]]):
        dic_buckets[group_name] = {}
        dic_buckets_groups[group_name] = bucket_group
        for i in sorted(df['bucket'].unique()):
            if i != 0:
                dic_buckets[group_name][i] = bucket_group[f(i,bucket_time)]   
    
    for p in lote45_primitives:
        df.loc[df['primitive_class']==p, 'bucket'] = df.loc[df['primitive_class']==p, 'bucket'].map(dic_buckets.get(p,dic_buckets['default']))
    
    #%%
    dfToday = df[df['date_reference']==dt]
    dfYesterday = df[df['date_reference']==dt_d1]
    
    #%%
    
    list_ccy=[]
    for c in dfToday[dfToday['primitive_class']=='FX']['primitive'].unique():
        list_ccy.append([c, c[0:3], 1])
        list_ccy.append([c, c[3:6], -1])
    
    dfFXHelp = pd.DataFrame(data=list_ccy, columns=['primitive', 'ccy', 'factor'])
    dfFX = dfToday.merge(dfFXHelp, left_on='primitive', right_on='primitive')
    dfFX['delta'] *= dfFX['factor']
    
    dfFX = dfFX[['trading_desk', 'ccy', 'delta']]
    
    dfFXTotal = dfFX[['ccy','delta']].groupby('ccy').sum()
    
    del dfFXHelp, list_ccy
    
    #%%
    
    color1, color2 = '#323E48', '#28829B'
    funds = ['A1 Master FIM', 'A1 Orange FIM','A1 FIFE BEM', 'A1 FIFE ITAU']
    
    fund_limit = {}
    for f in funds:
        limit = fu.get_RiskLimits(dt, f)
        fund_limit[f] = limit['Fund']
        
    
    fig, axes = plt.subplots(14, len(funds), 
                             figsize=(10, 15), 
                             sharey='row',# sharex='row',
                             gridspec_kw = {'height_ratios':[1, 2, 2, 2, 2, 2, 2, 2.5,2.5, 1, 5,1.2, 1, 1]})
    plt.tight_layout(h_pad=0)
    plt.subplots_adjust(wspace=0.1, 
                        hspace=0.2)
    
    for j, t in reversed(list(enumerate(funds))):
        dfTemp = dfToday[dfToday['trading_desk']==t][['primitive_class', 'primitive', 'bucket', 'delta']].groupby(['primitive_class', 'primitive', 'bucket']).sum().reset_index()
        ##
        row = 0
        ax = axes[row, j]
        ax.set_title('{}'.format(t), fontsize=15, fontweight='bold')
        ## Risk share
        risk_share = fund_limit[t][-1]
        # ax.barh([0],[risk_share], tick_label=['(%)'], color=color1, zorder=3, alpha=0.3)
        # ax.axvline(0, color='k', lw=0.75)
        # ax.axvline(1, color='k', lw=0.75, ls='--')
        # ax.grid(ls='--', axis='x')
        # # ticks_loc = ax.get_xticks().tolist()
        # # ax.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
        # # ax.set_xticklabels(['{:2.0%}'.format(x) if x!=0 else '-' for x in ticks_loc])
        # ax.set_xticklabels([])
        # ax.text(0, 0, '  ' + '{:2.1%}'.format(risk_share), color=color2,
        #                 fontsize=13, va='center', ha='left', fontweight='bold')
        # dfExcel.loc['Share of Risk (%)', t] = risk_share
        
        ############################################################### 
        ## S&P
        # row = 0
        ax = axes[row, j]
        dfEqty_SPX = dfTemp[(dfTemp['primitive_class']=='Equity')&(dfTemp['primitive'].isin(['SPX','NASDAQ 100 INDEX']))]
        if len(dfEqty_SPX['delta'].dropna())>0:
            val = dfEqty_SPX['delta'].sum() / risk_share 
            ax.barh([0],[val],tick_label=['S&P/\nNDX'], zorder=3, alpha=0.3, color=color2)
            ax.axvline(0, color='k', lw=0.75)            
            ax.grid(ls='--')
            ax.set_xlim(left=-0.5, right=1.5)
            # ticks_loc = ax.get_xticks().tolist()
            # ax.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
            # ax.set_xticklabels(['{:1.1%}'.format(x) if x!=0 else '-' for x in ticks_loc])
            ax.set_xticklabels([])
            ax.text(0, 0, ' {:3.2%}'.format(val) if val !=0 else '  -', va='center', fontsize=11,
                        ha='left', color='r' if val<0 else color1, fontweight='bold')
        else:
            ax.set_xticks([])
            ax.set_yticklabels(['S&P/\nNDX'])#, fontdict = {'fontsize': 4})
            val = 0
        # dfExcel.loc['S&P/NASDAQ', t] = val
        
        ## Equity
        row = 1        
        dfEqty_ex_SPX = dfTemp[(dfTemp['primitive_class']=='Equity')&(~dfTemp['primitive'].isin(['SPX','NASDAQ 100 INDEX']))]        
        num_eqty = dfEqty_ex_SPX['delta'].count()
        if risk_share !=0:
            net = dfEqty_ex_SPX['delta'].sum() / risk_share
            gross = dfEqty_ex_SPX['delta'].abs().sum() / risk_share
        else:
            net, gross = 0, 0 
        ax = axes[row, j]
        if (net!=0) & (gross!=0):
            ax.barh([0,1],[net, gross], tick_label=['Net', 'Gross'], color=color2, zorder=3, alpha=0.3)
            ax.axvline(0, color='k', lw=0.75)
            ax.grid(ls='--', axis='x')
            ax.set_xlim(left=-0.5, right=1.5)
            # ticks_loc = ax.get_xticks().tolist()
            # ax.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
            # ax.set_xticklabels(['{:1.0%}'.format(x) if x!=0 else '-' for x in ticks_loc])
            ax.set_xticklabels([])
            ax.text(0, 0,' {:4.1%}'.format(net) if net!=0 else ' -', \
                              fontweight='bold', va='center',ha='left',\
                                  color=('tomato' if net<0 else color1)) 
            ax.text(0, 1,' {:4.1%}'.format(gross) if gross!=0 else ' -', \
                              fontweight='bold', va='center',ha='left',\
                                  color=('tomato' if gross<0 else color1)) 
        else:
            ax.set_xticks([])
            ax.set_yticklabels(['Net', 'Gross'])
        # dfExcel.loc['Equity Net (ex-S&P/NDX)', t] = net
        # dfExcel.loc['Equity Gross (ex-S&P/NDX)', t] = gross
        ############################################################### 
        
        ## Juros 
        # lote45_primitives = ['BRL Rate Curve', 'IPCA Coupon', 'BRD Rate Curve', 'MXN Rate Curve']
        list_axes = [1,2,3,4,5,6,7]
        juros_ids = ['Taxa Pré', 'Tx Pré Infl', 'Cupom IPCA', 'Cupom Cambial', 'MX TIIE', 'UST/ED', 'JPT']
        
        for str_juros, i_axes, juros_id in zip(lote45_primitives, list_axes, juros_ids):
            bucket_group = dic_buckets_groups.get(str_juros, dic_buckets_groups['default'])
            dfPlot = dfTemp[dfTemp['primitive_class']==str_juros][['bucket','delta']].groupby('bucket').sum() / risk_share
            ax = axes[row+i_axes, j]
            if len(dfPlot)>0:
                for str_prazo in bucket_group:
                    if str_prazo not in dfPlot.index:
                        dfPlot.loc[str_prazo] = 0
                    # dfExcel.loc['{} ({:^6})'.format(juros_id, str_prazo), t] = dfPlot.loc[str_prazo, 'delta']
                # dfPlot.sort_index(inplace=True)
                dfPlot = dfPlot.reindex([i for i in reversed(bucket_group)])
                dfPlot.plot.barh(ax=ax, legend=False, color=color2, zorder=3, alpha=0.3)
                ax.axvline(0, color='k', lw=0.75)
                ax.grid(ls='--', axis='x')
                ax.set_xlim(left=min(-1.8, ax.get_xlim()[0]), right=max(1.8, ax.get_xlim()[1]))
                # ticks_loc = ax.get_xticks().tolist()
                # ax.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
                # ax.set_xticklabels(['{:1.0f}x'.format(x) if x!=0 else '-' for x in ax.get_xticks()])
                ax.set_xticklabels([])
                for i, v in enumerate(dfPlot.index):
                    val = dfPlot.loc[v, 'delta']
                    ax.text(0, i, ' {:3.2f}'.format(val) if val !=0 else '  -',
                               va='center', ha='left', color='r' if val<0 else color1, fontweight='bold')
            else:
                ax.set_xticks([])
                if j==0:
                    ax.yaxis.set_major_locator(mticker.FixedLocator([i for i, _ in enumerate(bucket_group)]))
                    ax.set_yticklabels([i for i in reversed(bucket_group)])
                # for str_prazo in bucket_group:
                #     dfExcel.loc['{} ({:^6})'.format(juros_id, str_prazo), t] = 0
        ############################################################### 
        
        ## IPCA
        row=9
        dfPlot = dfTemp[dfTemp['primitive_class']=='IPCA']
        ax = axes[row, j]
        if len(dfPlot['delta'].dropna())>0:
            val = dfPlot['delta'].sum() / risk_share * (0.1/100)
            ax.barh([0],[val],tick_label=['Delta \n(0.1%)'], zorder=3, alpha=0.3, color=color2)
            ax.axvline(0, color='k', lw=0.75)            
            ax.grid(ls='--')
            ax.set_xlim(left=min(-0.0013, val), right=max(0.0013, val))
            # ticks_loc = ax.get_xticks().tolist()
            # ax.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
            # ax.set_xticklabels(['{:1.1%}'.format(x) if x!=0 else '-' for x in ticks_loc])
            ax.set_xticklabels([])
            ax.text(0, 0, ' {:3.2%}'.format(val) if val !=0 else '  -', va='center', fontsize=11,
                        ha='left', color='r' if val<0 else color1, fontweight='bold')
        else:
            ax.set_xticks([])
            val = 0
        # dfExcel.loc['IPCA (Delta 0.1%)', t] = val
        
        ############################################################### 
        
        ## FX
        row+=1
        fx_axis = row
        ax = axes[row, j]
        dfPlot = dfFX[dfFX['trading_desk']==t][['ccy','delta']].groupby('ccy').sum()
        if len(dfFXTotal) > 0:
            dfPlot = dfPlot.join(dfFXTotal, how='right', rsuffix='x').sort_values('deltax') / risk_share
            if len(dfPlot['delta'].dropna())>0:
                dfPlot['delta'].plot.barh(ax=ax, legend=False, zorder=3, alpha=0.3,
                                 color=[color1 if i in ['BRL','USD'] else color2 for i in dfPlot.index])
                ax.axvline(0, color='k', lw=0.75)
                ax.set_xlim(left=-0.18, right=0.18)
                ax.grid(ls='--')
                # ticks_loc = ax.get_xticks().tolist()
                # ax.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
                # ax.set_xticklabels(['{:1.0%}'.format(x) if x!=0 else '-' for x in ticks_loc])
                ax.set_xticklabels([])
                for i, v in enumerate(dfPlot.index):
                    val = dfPlot.fillna(0).loc[v, 'delta']
                    ax.text(0, i, '{:6.1%}'.format(val) if val !=0 else '  -', 
                            fontsize=11 if v in ['USD', 'BRL'] else 10,
                               va='center', ha='left', color='r' if val<0 else color1, fontweight='bold')
            else:
                ax.set_xticks([])
        else:
            ax.set_xticks([])
            dfPlot['delta'] = 0
            if j==0:
                ax.yaxis.set_major_locator(mticker.FixedLocator([0.25, .75]))
                ax.set_yticklabels(['BRL','USD'])
                    
        
        ccy_cols = ['BRL', 'USD', 'EUR', 'MXN', 'CLP', 'COP', 'CAD', 'CNH', 'AUD', 'NZD', 'ZAR']
        # for ccy in ccy_cols:
        #     dfExcel.loc[ccy, t] = dfPlot['delta'].get(ccy, 0)
        fx_gross, fx_net = 0, 0
        for ccy in dfPlot['delta'].index:
            if ccy not in ccy_cols:
                fx_net += dfPlot.loc[ccy,'delta']
                fx_gross += abs(dfPlot.loc[ccy,'delta'])
        # dfExcel.loc['Others (Net)', t] = fx_net
        # dfExcel.loc['Others (Gross)', t] = fx_gross
        ############################################################### 
        #Commodity
        row+=1
        fx_axis = row
        ax = axes[row, j]
        dfPlot = dfTemp[dfTemp['primitive_class']=='Commodity']
        dict_cmdty = {'Gold Syn.':'Gold',
                      'WTI Crude Oil Syn. 2M':'Oil'}
        if len(dfPlot['delta'].dropna())>0:
            dfPlot['primitive'] = dfPlot['primitive'].map(dict_cmdty)
            dfPlot = dfPlot.set_index('primitive')
            dfPlot['delta'] /= risk_share
            dfPlot['delta'].plot.barh(ax=ax, legend=False, zorder=3, alpha=0.3,
                                color=color2)
            ax.axvline(0, color='k', lw=0.75)
            ax.set_xlim(left=-0.18, right=0.18)
            ax.grid(ls='--')
            # ticks_loc = ax.get_xticks().tolist()
            # ax.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
            # ax.set_xticklabels(['{:1.0%}'.format(x) if x!=0 else '-' for x in ticks_loc])
            ax.set_xticklabels([])
            
            for i, v in enumerate(dfPlot.index):
                val = dfPlot.fillna(0).loc[v, 'delta']
                ax.text(0, i, '{:6.1%}'.format(val) if val !=0 else '  -', 
                        fontsize= 10,
                        va='center', ha='left', color='r' if val<0 else color1, fontweight='bold')
        else:
            ax.set_xticks([])
            ax.set_yticklabels(dict_cmdty.values())
            val = 0
        
        row+=1
        for str_risk, i_axes, fmt, lim_max in zip (['VaR', 'Stress'], [0, 1], 
                                                   ['{:1.1f}', '{:2.1%}'], [190, 0.35]):
            ax = axes[row+i_axes, j]
            if t in t in dfRisk.columns:
                val = abs(dfRisk.loc[str_risk,t]) / risk_share
            else:
                val = 0
            ax.barh([0],[val], tick_label=['(BPs)' if str_risk=='VaR' else '(%)'], color=color2, zorder=3, alpha=0.3)
            ax.axvline(0, color='k', lw=0.75)
            ax.set_xlim(left=0, right=lim_max)
            # if t=='Fund':
            #     ax.axvline(abs(trader_limit[t][i_axes]), color='r', lw=1.5)
    
            ax.grid(ls='--', axis='x')
            # ticks_loc = ax.get_xticks().tolist()
            # ax.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
            # ax.set_xticklabels([fmt.format(x) if x!=0 else '-' for x in ticks_loc])
            ax.set_xticklabels([])
            ax.text(0, 0, '  ' + fmt.format(val) if val !=0 else '  -', fontweight='bold',
                        fontsize=13, va='center', ha='left', color=color1)
            
            # dfExcel.loc[str_risk, t] = val
        ############################################################### 
        
    for i, str_labels in enumerate(['Index','Equity','Taxa Pré','Pré Infl', 'Cp IPCA',
                                    'Cp Cambial','MX TIIE', 'UST/ED', 'JPT', 'IPCA',
                                    'FX','Cmdty', 'VaR','Stress']):
        axes[i,0].set_ylabel(str_labels, fontweight='bold', size=13)
    
    for i, tx in enumerate(axes[fx_axis,0].get_yticklabels()):
        if tx.get_text() in ['USD', 'BRL']:     
            tx.set_color(color2)
            tx.set_fontweight('bold') 
    for i in range(len(axes)):
        axes[i,0].set_yticklabels(axes[i,0].get_yticklabels(), fontsize=12)
        # axes[i,-1].set_facecolor('lightgray')
    
    fig.align_ylabels(axes[:, 0])
    fig_file = r'R:\Risk\01_DailyReports\Risk\{:%Y%m%d}_Fund_exposure.pdf'.format(dt)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    
#%%

if __name__ == '__main__':
    
    dt = datetime.date(2023, 1, 16)
    main(dt)