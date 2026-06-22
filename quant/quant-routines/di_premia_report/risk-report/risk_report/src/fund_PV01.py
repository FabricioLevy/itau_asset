import pandas as pd
import timeit
import datetime
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import xlwings as xw
from matplotlib.colors import ListedColormap
import seaborn as sns
import fund_utils as fu


#%%
def main(dt, str_fund, nav, report_filename):
    #%%
    _, connection = fu.get_DB_conn('prod')
    
    str_sql = f"""SELECT [lote45_product],[lote45_product_class],
                [primitive],[primitive_class], trim(str([bucket])) as bucket, 
                [amount],[delta] 
                FROM [lote45].[primitive] 
                WHERE date_reference = '{dt:%Y-%m-%d}' 
                    --and lote45_product_class <> 'CPM Options - BMF'
                    and trading_desk = '{str_fund}'"""
    df = pd.read_sql(str_sql, connection)
    connection.close()
    del str_sql
    
    #%%
    columns = ['primitive_class','lote45_product_class']#, 'Product']
    dfPV01 = df.pivot_table(index=columns, 
                            columns='bucket',
                            values='delta', 
                            aggfunc='sum', 
                            fill_value=0).reset_index()
        
    dic_bucket = {'1':'1D','5':'1W','30':'1M','60':'2M','90':'3M','180':'6M',\
                  '270':'9M','360':'1Y','540':'1.5Y','720':'2Y','900':'2.5Y'} 
    dic_bucket.update({str(i*360):'{}Y'.format(i) for i in range(3,51)})
    
    
    dfPV01.loc[dfPV01['lote45_product_class']=='CPM Options - BMF',[i for i in dic_bucket.keys() if i in dfPV01.columns]] = 0
    
    
    dic_tenor = {}
    dic_tenor['<1M'] = [v for k,v in dic_bucket.items() if int(k)<=30]
    dic_tenor['1Y'] = [v for k,v in dic_bucket.items() if int(k)>30 and int(k)<=360]
    dic_tenor['1Y-5Y'] = [v for k,v in dic_bucket.items() if int(k)>360 and int(k)<=1800]
    dic_tenor['5Y-10Y'] = [v for k,v in dic_bucket.items() if int(k)>1800 and int(k)<=3600]
    dic_tenor['>10Y'] = [v for k,v in dic_bucket.items() if int(k)>3600]
    dic_tenor['Total'] = list(dic_bucket.values())
    
    dic_product={
                 'USDBRLFuture':'FX',
                 'Currencies Forward': 'FX',
                 'Currencies NDF': 'FX',
                 'USDBRLOptionCall':'FX',
                 'USDBRLOptionPut':'FX',
                 'IBOV Options':'Eqty',
                 'Equity Options':'Eqty',
                 'Equity Subscription':'Eqty',
                 'IBOVSPFuture':'Eqty',
                 'DI1Future':'DI Fut',
                 'IDIOptionPut':'IDI',
                 'IDIOptionCall':'IDI',
                 'CPM Options - BMF':'*Cpm Opt',
                 'DAP Future':'DAP',
                 'DDI Future':'DDI',
                 'SCS TERM': 'SCS Term',
                 'CLP Fixed-Float SWAP':'Swap',
                 'COP Fixed-Float SWAP':'Swap',
                 'MXN TIIE SWAP':'Swap',
                 'US Treasury Bond Future':'Trea Fut',
                 'TBILL':'T-Bill',
                 'Eurodollar Futures':'ED Fut',
                 '30-Day Fed Funds Futures':'FF',
                 'JGB 10-year Futures - TSE': 'JGB Fut'
                 }
    dfPV01.replace(dic_product, inplace=True)
    
    dic_curve_rename = {'USA Sovereign Yield': 'US', 
                        'USD Rate Curve':'US'}
    dfPV01.replace(dic_curve_rename, inplace=True)
    
    
    dfPV01 = dfPV01.groupby(by=['primitive_class','lote45_product_class']).sum().reset_index()
    
    sorted_buckets = sorted([int(i) for i in dfPV01.columns if i not in columns])    
    dfPV01 = dfPV01[columns + [str(i) for i in sorted_buckets]]
    dfPV01.rename(columns=dic_bucket, inplace=True)
    col_buckets = [dic_bucket[str(i)] for i in sorted_buckets if i>0]
    dfPV01['Total']=dfPV01[col_buckets].sum(axis=1)
    col_buckets += ['Total']
    
    dfPV01 = dfPV01[~((dfPV01['primitive_class']=='BRL Rate Curve') & (dfPV01['lote45_product_class'].isin(['SCS','DDI'])))]
    
    dfIPCA = dfPV01[dfPV01['primitive_class']=='IPCA']
    if len(dfIPCA)>0:
        dfIPCA = dfIPCA[['lote45_product_class', '0']].groupby('lote45_product_class').sum()/nav
        dfIPCA.columns = ['DeltaIPCA']

    # dfPV01 = dfPV01.loc[~(dfPV01[col_buckets]==0).all(axis=1)]
    #%%
    ### IPCA
    if len(dfIPCA)>0:
        fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(5, 1))
        plt.tight_layout()
        dfIPCA.plot.barh(ax=ax, legend=False, color=fu.color_palette[2])
        
        for i, prod in enumerate(dfIPCA.index):
            x = float(dfIPCA.loc[prod, 'DeltaIPCA'])
            c = 'r' if x<0 else 'k'
            ax.text(max(0, x), i, '{:2.0%}'.format(x), va='center',\
                         color=c, ha='left', fontweight='bold', fontsize=8) 
            
        ax.grid(ls='--', axis='x')
        ax.set_xlim(right=ax.get_xlim()[1]*1.25)
        ticks_loc = ax.get_xticks().tolist()
        ax.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
        ax.set_xticklabels(['{:2.0%}'.format(x) for x in ticks_loc], fontsize=9)
        ax.set_ylabel('')
        
        fig_file = '../output/temp_figs/{:%Y%m%d}_{}_dashboard_ipca.svg'.format(dt, str_fund)
        fig.savefig(fig_file, bbox_inches = "tight")
        plt.show()
        
        wb = xw.Book(report_filename)
        wb.sheets('Cover').pictures.add(wb.api.Path + '/' + fig_file, name='dashboard_ipca', update=True)
    
    #%%
    dic_curvename = {'BRL Rate Curve': 'Taxa\nPré',
                     'IPCA Coupon':'Cp\nIPCA',
                     'US': 'US', 
                     'BRD Rate Curve':'Cp\nCambial',
                     'Japan Sovereign Yield' : 'JP',
                     'MXN Rate Curve': 'MX',
                     'COP Rate Curve': 'CO',
                     'CLP Rate Curve': 'CL'}
          
    dic_PV01={}
    dfPV01_resumo=pd.DataFrame(columns=dic_tenor.keys())
    height_ratios=[]
    for k, v in dic_curvename.items():
        if len(dfPV01[dfPV01['primitive_class']==k]) > 0:
            dic_PV01[v] = dfPV01[dfPV01['primitive_class']==k].set_index('lote45_product_class')[col_buckets]
            for tenor, buckets in dic_tenor.items():
                dfPV01_resumo.loc[v.replace('\n', ' '), tenor] = float(dic_PV01[v][[b for b in buckets if b in dic_PV01[v].columns]].sum().sum()/nav)
            x=len(dic_PV01[v])
            height_ratios.append(x if x==1 else x+1)
        
    fig, axes = plt.subplots(len(dic_PV01), 
                             1, 
                             figsize=(11.5, 4.85), 
                             sharex='col', 
                             gridspec_kw = {'height_ratios':height_ratios})
    plt.tight_layout()
    plt.subplots_adjust(wspace=0.05, hspace=0.1)
    
    for i, (curve, dfTemp) in enumerate(dic_PV01.items()):
        if len(dic_PV01) == 1:
            ax = axes
        else:
            ax = axes[i]
        if len(dfTemp) > 1:
            dfTemp.loc['Total'] = dfTemp.sum(axis=0)
            
        sns.heatmap(dfTemp[col_buckets], cmap=ListedColormap(['#E0F0F4']), fmt='2.1f',\
                    xticklabels=True,\
                        square=False, linewidths=1.0, annot=False, cbar=False, ax=ax)
        for xi, c in enumerate(col_buckets):
            for yi in range(len(dfTemp)):
                v = dfTemp[c].iloc[yi]/nav
                ax.text(xi+.5, yi+.5, '{:2.1f}'.format(v) if v!= 0 else '-',\
                               ha="center", va="center", color="k" if v>=0 else 'r',\
                               fontweight='bold' if c in col_buckets else 'normal')
                    
        ax.axvline(len(col_buckets)-1, color='k', lw=1)
                
        if len(dfTemp) != 1:
            ax.axhline(len(dfTemp)-1, color='k', lw=1) 
        if i!=0:
            ax.xaxis.set_ticks_position('none') 
    
        ax.set_ylabel(curve, fontsize=12)
        ax.set_xlabel('')
        if len(dfTemp) == 1:
            ax.set_yticklabels(dfTemp.index, rotation=0)
        else:
            ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
    
    if len(dic_PV01) > 1:
        axes[0].xaxis.set_ticks_position('top')
        axes[0].get_xticklabels()[-1].set_weight("bold")
    ax.get_xticklabels()[-1].set_weight("bold")
    
    fig.align_ylabels(axes)
    
       
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_dashboard_pv01.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    
    wb = xw.Book(report_filename)
    wb.sheets('Cover').pictures.add(wb.api.Path + '/' + fig_file, name='dashboard_pv01', update=True)

#%%
    plt.close()
    fig, ax = plt.subplots(1, 1, figsize=(10, 4))
    sns.heatmap(dfPV01_resumo.fillna(0), cmap=ListedColormap(['#E0F0F4']), fmt='2.2f',\
                       square=False, linewidths=1.0, annot=False, cbar=False, ax=ax)
        
    for xi, c in enumerate(dfPV01_resumo.columns):
       for yi, i in enumerate(dfPV01_resumo.index):
           v = dfPV01_resumo.loc[i, c]
           ax.text(xi+.5, yi+.5, '{:2.2f}'.format(v) if v!= 0 else '-',\
                           ha="center", va="center", color="k" if v>=0 else 'r',\
                           fontweight='bold' if c in ['Total'] else 'normal',\
                               fontsize=14)
    ax.xaxis.set_ticks_position('both')
    ax.axvline(xi, color='k', lw=2) 
    ax.tick_params(labelsize=14)
    ax.get_xticklabels()[-1].set_weight("bold")
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
   

#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt, str_fund = fu.get_config(['dt', 'str_fund'])
    nav = fu.get_NAV(dt, str_fund)
    report_filename = '../xls/RiskMap_model.xlsm'
    main(dt, str_fund, nav, report_filename) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))