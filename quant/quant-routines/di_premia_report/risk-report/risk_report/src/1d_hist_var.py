import pandas as pd
import numpy as np
import datetime
import timeit
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
import fund_utils as fu 
from adjustText import adjust_text

#%%
def main(dt, str_fund, nav, report_filename):
    #%%
    _, connection = fu.get_DB_conn('prod')
    
    str_path = "R:/Risk/01_DailyReports/01_01_Lote45_extract/Fund/"
    str_file = "Fund1DayHistReturnTable_{}_{:%d%b%Y}.txt".format(str_fund, dt)    
    dfHistVaR = pd.read_csv(str_path + str_file, sep='\t', parse_dates=[0], encoding='UTF-8', index_col=0).sort_index()
    dfHistVaR = dfHistVaR.fillna(0)
        
    str_sql = """
            SELECT [date_reference],[lote45_product],[lote45_product_class],
                [primitive],[primitive_class],[book],[delta],[gamma],[vega]
            FROM [lote45].[primitive]
            WHERE date_reference = '{:%Y-%m-%d}' and trading_desk = '{}'
            AND primitive NOT IN ('BRAZIL ONSHORE SPREAD')
                """
    str_sql = str_sql.format(dt, str_fund)
    dfPrimitive = pd.read_sql(str_sql, connection)

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
    dfPrimitive['Risk'] = dfPrimitive['book'].apply(lambda x: dic_book[x])
    dfPrimitive['Trader'] = dfPrimitive['book'].apply(lambda x: dic_trader[x])
    #%%
    dics = {}
    for c in ['lote45_product', 'lote45_product_class', 'primitive', 'primitive_class', 'book', 'Risk', 'Trader']:
        temp_dict = dfPrimitive[c].to_dict()
        dics[c] = {}
        for k, v in temp_dict.items():
            if v not in dics[c]:
                dics[c][v]=[k]
            else:
                dics[c][v].append(k)
    #%%
    dfOutput = pd.DataFrame(index=dfHistVaR.index, columns=dfPrimitive.index)
    for i in dfPrimitive.index:
        primitive = dfPrimitive.loc[i, 'primitive']
        delta = dfPrimitive.loc[i, 'delta']
        gamma = dfPrimitive.loc[i, 'gamma'] 
        vega = dfPrimitive.loc[i, 'vega']        
        vol_shift = dfHistVaR['Vol '+primitive] if 'Vol '+primitive in dfHistVaR.columns else 0      
        dfOutput[i] = delta*dfHistVaR[primitive] + (0.5*gamma*dfHistVaR[primitive]**2) + (vega * vol_shift)
    
    #%%    
    # tuples = list(dfPrimitive[['book', 'lote45_product']].drop_duplicates().itertuples(index=False))
    # dfHypoPnL =  pd.DataFrame(columns=pd.MultiIndex.from_tuples(tuples),
    #              index=dfOutput.index)

    # for (book, prod) in dfHypoPnL.columns:
    #     cols = set(dics['lote45_product'].get(prod, -1)).intersection(dics['book'].get(book, -1))
    #     dfHypoPnL[(book, prod)] = dfOutput[cols].sum(axis=1)

    
    # %%
    # dfOutput = pd.DataFrame(index=dfHistVaR.index, columns=dfPrimitive.index)
    # for i in dfPrimitive.index:
    #     primitive = dfPrimitive.loc[i, 'primitive']
    #     delta = dfPrimitive.loc[i, 'delta']
    #     gamma = dfPrimitive.loc[i, 'gamma'] 
    #     vega = dfPrimitive.loc[i, 'vega']
    #     for dt_i in dfHistVaR.index:
    #         dfOutput.loc[dt_i, i] = dfHistVaR.loc[dt_i, primitive] * delta +\
    #             (0.5 * gamma * (dfHistVaR.loc[dt_i, primitive]**2)) +\
    #               (100 * dfHistVaR.loc[dt_i].get('Vol '+primitive, 0) * vega)
    #%%
    dic_dfs = {}
    for k1, dic_ids in dics.items():
        temp_df = dfOutput.copy()
        for k2, list_ids in dic_ids.items():
            temp_df[k2] = temp_df[list_ids].sum(axis=1)
        dic_dfs[k1] = temp_df[dic_ids.keys()].copy() / nav
        dic_dfs[k1]['Fund'] = dic_dfs[k1].sum(axis=1)
       
        
    #%%
    temp_ret = dic_dfs['Trader'][[i for i in ['MS','BC','GB','PC','NF', 'MK','Fund'] if i in dic_dfs['Trader'].columns]]
    cmap = sns.diverging_palette(10, 260, n=15, as_cmap=True)
    fig, axes = plt.subplots(2, 2, figsize=(12, 6))
    fig.tight_layout(h_pad=4)
    for shift, ax in zip([-21, -63, -126, -252], 
                          axes.flatten()):

        corr = temp_ret.iloc[shift:].corr() * 100
        mask = np.zeros_like(corr)
        mask[np.triu_indices_from(mask)] = True
        sns.heatmap(corr, mask=mask, cmap=cmap, vmax=100, vmin=-100, center=0, fmt='2.0f',\
                    square=False, linewidths=.5, annot = True, cbar=False, ax=ax)
        ax.yaxis.label.set_visible(False)
        ax.xaxis.label.set_visible(False)
        ax.set_xticklabels(ax.get_xticklabels(), rotation=0, fontweight='bold', fontsize=11)  
        ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontweight='bold', fontsize=11)  
        ax.set_title(f"Janela de {-shift:2.0f} dias", fontweight='bold')
    
    fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_simu_correl.pdf'.format(dt)
    fig.savefig(fig_file, bbox_inches = "tight")
   
    plt.show()
    
    #%%
    limits = fu.get_RiskLimits(dt, str_fund)
    
    locator = mdates.AutoDateLocator(minticks=4, maxticks=7)
    formatter = mdates.ConciseDateFormatter(locator, formats=['%b\n%Y', '%b', '%d', '%H:%M', '%H:%M', '%S.%f'], show_offset=False)
   

    fig, axes = plt.subplots(2, 2, figsize=(12, 6))
    fig.tight_layout(h_pad=4)
    for shift, ax in zip([-21, -63, -126, -252], 
                          axes.flatten()):
        ax.set_title(f"Janela de {-shift:2.0f} dias", fontweight='bold')
        for trader, (_,_,risk_share) in limits.items():
            if trader in temp_ret.columns:
                df_plot = (temp_ret[trader].iloc[shift:]/risk_share+1).cumprod() - 1
                df_plot.loc[temp_ret.index[shift-1]]=0
                df_plot = df_plot.sort_index()
                ax.plot(df_plot.index, df_plot, label=trader, 
                        lw=3 if trader=='Fund' else 1.5,
                        ls='--' if trader=='Fund' else '-')
        ax.set_xlim(left = temp_ret.index[shift-1])
        ax.grid(ls='--')
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1,0)) 
        # ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)
    axes[0,0].legend(ncol=3)
    fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_simu_correl_retacum.pdf'.format(dt)
    fig.savefig(fig_file, bbox_inches = "tight")
   
    plt.show()  
    
    
    
    #%%
    color1, color2 = fu.color_palette[0:2]
    
    temp_df = dic_dfs[k1].copy()
    for trader, (_,_,risk_share) in limits.items():
        if trader in temp_df.columns:
            temp_df[trader] /= risk_share
    df_var = temp_df.ewm(alpha=0.06, adjust=False, min_periods=10).std() * 1.645 * 10_000
    df_vol = temp_df.ewm(alpha=0.06, min_periods=10).std() * np.sqrt(252)
    df_vol21d = temp_df.rolling(21, min_periods=10).std() * np.sqrt(252)
    vol5y = temp_df.std() * np.sqrt(252)
        
    temp_df *= 10_000
    bins = np.linspace(round(temp_df.min().min()*1.05,4), round(temp_df.max().max()*1.05,4), 50)

    fig, axes = plt.subplots(3,3, figsize=(10,6), sharey=True)
    fig.tight_layout(w_pad=0)
    for ax, trader in zip(axes.flatten(), limits.keys()):
        ax.set_title(trader, fontweight='bold', fontsize=13 if trader=='Fund' else 10)
        if trader in temp_df.columns:
            _ , bins, _ = ax.hist(temp_df[trader], 26, color=color2, zorder=3, alpha=0.9)
    
            var_hist95 = temp_df[trader].quantile(0.05)
            ax.axvline(var_hist95, ymax=0.9, color='darkorange', ls='--', lw=2.5, zorder=4)
            ax.hist(temp_df[temp_df[trader]<var_hist95][trader], bins, color='darkorange', zorder=4, alpha=0.8)       
            ax.annotate(f"VaR95\n{var_hist95:2.1f}", xytext=(0.7, 0.6), textcoords="axes fraction",
                         xy=(var_hist95, 0), xycoords="data", fontsize=9,
                         va="center", ha="center",fontweight='bold', zorder=3,
                          bbox=dict(boxstyle="round", fc='darkorange', alpha=0.8),
                          arrowprops=dict(arrowstyle="->", connectionstyle="arc3, rad=-0.2", lw=1.5)) 
            
                   
            var_hist99 = temp_df[trader].quantile(0.01)
            ax.axvline(var_hist99, ymax=0.45, color='tomato', ls='--', lw=2.5, zorder=4)
            
            ax.annotate(f"VaR99\n{var_hist99:2.1f}", xytext=(0.5, 0.85), textcoords="axes fraction", 
                         xy=(var_hist99, 0), xycoords="data", fontsize=9,
                         va="center", ha="center",fontweight='bold', zorder=4,
                          bbox=dict(boxstyle="round",alpha=0.8, fc='tomato'),
                          arrowprops=dict(arrowstyle="->", connectionstyle="arc3, rad=-0.2", lw=1.5)) 
            ax.hist(temp_df[temp_df[trader]<var_hist99][trader], bins, color='tomato', zorder=4, alpha=0.8)
            
            es99 = temp_df[temp_df[trader]<var_hist99][trader].mean()
            es95 = temp_df[temp_df[trader]<var_hist95][trader].mean()
            
            # xleft = ax.get_xlim()[0]
            # ax.arrow(var_hist95, 80, xleft-var_hist95, 0,  
            #             width=1.5,  linewidth=1, alpha=0.6, color='darkorange',
            #            length_includes_head=True, zorder=6)
            ax.text(var_hist95, 500, f"{es95:2.1f} ", va='bottom', ha='right', fontweight='bold', color='darkorange')
            
            # ax.arrow(var_hist99, 30, xleft-var_hist99, 0,  
            #             width=1.5,  linewidth=1, alpha=0.6, color='tomato',
            #            length_includes_head=True, zorder=6)
            ax.text(var_hist99, 200, f"{es99:2.1f} ", va='bottom', ha='right', fontweight='bold', color='tomato')
            # ax.annotate(f"{es99:2.1f}",
            #     xy=(0, 0), xycoords='data',fontweight='bold',fontsize=9,
            #      xytext=((bins[0]-var_hist99)/2 + var_hist99, 30), textcoords='data', ha='center', zorder=4,
            #      bbox=dict(boxstyle="darrow,pad=0.3", fc="tomato", ec='tomato', lw=2),
            #     )   
            
            
            # ax.text(es, 10, f"{es:2.1f}  ", ha='right', va='bottom', fontweight='bold', fontsize=11, color='tomato')
            ax.grid(ls='--')
        
        # ax.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax.set_facecolor('silver')
    
    plt.show()
    #%%
    fig, axes = plt.subplots(2, 3, figsize=(12,6), sharex=True)
    fig.tight_layout()
    for ax, trader in zip(axes.flatten(), [t for t in limits.keys() if t!='Fund']):
        ax.set_title(trader, fontweight='bold', fontsize=13 if trader=='Fund' else 10)
        if trader in temp_df.columns:
            ax.plot(df_var.index, df_var[trader], ls='-', color=color2, zorder=3, lw=1.5, label=f"VaR ({df_var.iloc[-1][trader]:2.0f})")
            ax.axhline(df_var[trader].mean(), ls='--', color='tomato', zorder=2, lw=2, label=f"Avg VaR ({df_var[trader].mean():2.0f})")
            # ax.axhline(vol5y[trader], color='tomato', ls=':',lw=2, label=f"Vol 5y ({vol5y[trader]:2.1%})")
            ax.grid(ls='--', which='major')
            ax.grid(ls=':', which='minor')
            ax.set_ylim(bottom=0)
            ax.legend(loc=3,ncol=2, fontsize=8)
            ax.xaxis.set_minor_locator(mdates.YearLocator(1))
            ax.xaxis.set_major_locator(mdates.YearLocator(3))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
            ax.yaxis.set_major_formatter(mticker.StrMethodFormatter('{x:,.0f}'))
            ax.set_xlim(left=df_var.index[0])
            ax.set_ylim(top=max(ax.get_ylim()[1], 5))
            txts = []
            ym=[]
            count=0
            for i in temp_df[trader].abs().sort_values(ascending=False).head(10).index:
                if (i.month, i.year) not in ym:
                    ym.append((i.month, i.year))
                    count+=1
                    if count<=3:
                        txts.append(ax.text(i, df_var.loc[i, trader], f"{i:%d%b%y}", fontsize=8))
            adjust_text(txts, ax=ax, arrowprops=dict(arrowstyle='-', color='k'))
    # ax.set_facecolor('silver')
    
    fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_trader_var_level.pdf'.format(dt)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    
    #%%
    fig, (axVar, axRet) = plt.subplots(2, 1, 
                                       figsize=(10, 5), sharex=True,
                                       gridspec_kw={'height_ratios':[3, 2]})
    fig.tight_layout(h_pad=0)
    
    trader = 'Fund'
    ax = axVar
    ax.plot(df_var.index, df_var[trader], ls='-', color=color2, zorder=3, lw=1.5, label=f"VaR ({df_var.iloc[-1][trader]:2.0f})")
    ax.axhline(df_var[trader].mean(), ls='--', color='tomato', zorder=2, lw=2, label=f"Avg VaR ({df_var[trader].mean():2.0f})")
    
    ax.set_title(trader, fontweight='bold', fontsize=13 if trader=='Fund' else 10)
    ax.set_ylim(bottom=0)
    ax.legend(loc=3,ncol=2, fontsize=8)
    ax.xaxis.set_minor_locator(mdates.YearLocator(1))
    ax.xaxis.set_major_locator(mdates.YearLocator(3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%y'))
    # ax.yaxis.set_major_formatter(mticker.PercentFormatter(1,1))
    ax.set_xlim(left=df_var.index[0])
    
    ax.set_ylabel("Hypothetical VaR (BPs)")
    txts = []
    ym=[]
    count=0
    for i in temp_df[trader].abs().sort_values(ascending=False).head(10).index:
        if (i.month, i.year) not in ym:
            ym.append((i.month, i.year))
            count+=1
            if count<=3:
                txts.append(ax.text(i, df_var.loc[i, trader], f"{i:%d%b%y}", fontsize=8))
                axRet.scatter([i], [temp_df.loc[i, trader]], marker='o', color='tomato')
    adjust_text(txts, ax=ax, arrowprops=dict(arrowstyle='-', color='k'))

    ax = axRet    
    std = temp_df[trader].std()
    ax.plot(temp_df.index, temp_df[trader], color=color1, ls='', marker='.', alpha=0.5)
    
    ax.axhline(std*-2, ls='--', color='tomato', zorder=4, label=r"$+2\sigma$")
    ax.axhline(std*2, ls='--', color='tomato', zorder=4, label=r"$-2\sigma$")
    ax.legend()
    ax.set_ylabel("Simulated Returns (BPs)")
        
    
    for ax in (axVar, axRet):
        ax.grid(ls='--', which='major')
        ax.grid(ls=':', which='minor')
    
    fig.align_ylabels()
    fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_fund_var_level.pdf'.format(dt)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    #%%
    fig, ax = plt.subplots(1, 1, figsize=(8, 4) )
    fig.tight_layout(h_pad=0)
    
    trader = 'Fund'
    ax.plot(df_vol21d.index, df_vol21d[trader], ls='-', color=color2, zorder=3, lw=1.5, label=f"Vol {trader}")
    ax.axhline(df_vol21d[trader].mean(), ls='--', color='tomato', zorder=2, lw=2, label=f"Avg Vol ({df_vol21d[trader].mean():2.1%})")
    
    ax.set_title(trader, fontweight='bold', fontsize=13)
    ax.set_ylim(bottom=0)
    ax.legend(loc=3,ncol=2, fontsize=8)
    ax.xaxis.set_minor_locator(mdates.MonthLocator([7]))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%y'))
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1,1))
    ax.set_xlim(left=df_vol21d.index[0])
    
    # ax.set_ylabel("Hypothetical VaR (BPs)")
    ax.grid(ls='--', which='major')
    ax.grid(ls=':', which='minor')
    
    fig.align_ylabels()
    plt.show()
    
    
    
    #%%
    
    
    fig, axes = plt.subplots(3,3, figsize=(10,6), sharex=True)
    fig.tight_layout()
    for ax, trader in zip(axes.flatten(), limits.keys()):
        ax.set_title(trader, fontweight='bold', fontsize=13 if trader=='Fund' else 10)
        if trader in temp_df.columns:
            ax.plot(df_vol.index, df_vol[trader], ls='-', color=color2, zorder=3, lw=1.5, label=f"Vol ({df_vol.iloc[-1][trader]:2.1%})")
            ax.axhline(vol5y[trader], color='tomato', ls=':',lw=2, label=f"Vol 5y ({vol5y[trader]:2.1%})")
            ax.grid(ls='--', which='major')
            ax.grid(ls=':', which='minor')
            ax.set_ylim(bottom=0)
            ax.legend(loc=3,ncol=2, fontsize=8)
            ax.xaxis.set_minor_locator(mdates.MonthLocator([7]))
            ax.xaxis.set_major_locator(mdates.YearLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%y'))
            ax.yaxis.set_major_formatter(mticker.PercentFormatter(1,1))
            ax.set_xlim(left=df_vol.index[0])
            txts = []
            ym=[]
            count=0
            for i in temp_df[trader].abs().sort_values(ascending=False).head(10).index:
                if (i.month, i.year) not in ym:
                    ym.append((i.month, i.year))
                    count+=1
                    if count<=3:
                        txts.append(ax.text(i, df_vol.loc[i, trader], f"{i:%d%b%y}", fontsize=8))
            adjust_text(txts, ax=ax, arrowprops=dict(arrowstyle='-', color='k'))
    ax.set_facecolor('silver')
    plt.show()
#%%
    dfVolIndex = df_vol / df_vol.loc['2016-7-1'] * 100
    
    fig, axes = plt.subplots(3,3, figsize=(10,6), sharex=True)
    fig.tight_layout()
    for ax, trader in zip(axes.flatten(), limits.keys()):
        ax.set_title(trader, fontweight='bold', fontsize=13 if trader=='Fund' else 10)
        if trader in temp_df.columns:
            ax.plot(dfVolIndex.index, dfVolIndex[trader], ls='-', 
                    color=color2, zorder=3, lw=1.5, label=f"Vol ({dfVolIndex.iloc[-1][trader]:2.1f})")
            # ax.axhline(vol5y[trader], color='tomato', ls=':',lw=2, label=f"Vol 5y ({vol5y[trader]:2.1%})")
            ax.grid(ls='--', which='major')
            ax.grid(ls=':', which='minor')
            # ax.set_ylim(bottom=0)
            ax.legend(loc=3,ncol=2, fontsize=8)
            ax.xaxis.set_minor_locator(mdates.MonthLocator([7]))
            ax.xaxis.set_major_locator(mdates.YearLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%y'))
            # ax.yaxis.set_major_formatter(mticker.PercentFormatter(1,1))
            ax.set_xlim(left=dfVolIndex.index[0])
            txts = []
            ym=[]
            count=0
            for i in temp_df[trader].abs().sort_values(ascending=False).head(10).index:
                if (i.month, i.year) not in ym:
                    ym.append((i.month, i.year))
                    count+=1
                    if count<=3:
                        txts.append(ax.text(i, dfVolIndex.loc[i, trader], f"{i:%d%b%y}", fontsize=8))
            adjust_text(txts, ax=ax, arrowprops=dict(arrowstyle='-', color='k'))
    ax.set_facecolor('silver')
    plt.show()  
    #%%
    # dfOutput2 = pd.DataFrame(index=dfHistVaR.index, columns=dfPrimitive['primitive'].unique())
    
    # for primitive in dfOutput2.columns:
    #     print(primitive)
    #     delta = dfPrimitive[dfPrimitive['primitive']==primitive]['delta'].sum()
    #     gamma = dfPrimitive[dfPrimitive['primitive']==primitive]['gamma'].sum()
    #     vega = dfPrimitive[dfPrimitive['primitive']==primitive]['vega'].sum()
    #     for dt_i in dfHistVaR.index:
            
    #         dfOutput2.loc[dt_i, 'Delta ' + primitive] = dfHistVaR.loc[dt_i, primitive] * delta 
            
    #         if gamma != 0:
    #             dfOutput2.loc[dt_i, 'Gamma ' + primitive] =  (0.5 * gamma * (dfHistVaR.loc[dt_i, primitive]**2))
                  
    #         if vega != 0:
    #             dfOutput2.loc[dt_i, 'Vega ' + primitive] =  (dfHistVaR.loc[dt_i].get('Vol '+primitive, 0) * vega)
            
    #         dfOutput2.loc[dt_i, primitive] = dfHistVaR.loc[dt_i, primitive] * delta +\
    #            (0.5 * gamma * (dfHistVaR.loc[dt_i, primitive]**2)) +\
    #               (100 * dfHistVaR.loc[dt_i].get('Vol '+primitive, 0) * vega)

#%%                  
if __name__ == "__main__":
        
    tic = timeit.default_timer()
    dt = datetime.date(2022, 11, 18)
    str_fund = 'A1 Master FIM'
    report_filename = '../xls/RiskMap_model.xlsm'
    nav = fu.get_NAV(dt, str_fund)
    main(dt, str_fund, nav, report_filename)              

    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))     
