import pandas as pd
import numpy as np
import timeit
import datetime
import matplotlib.pyplot as plt
import xlwings as xw
import fund_utils as fu
import matplotlib.gridspec as gridspec


#%%
def main(dt, str_fund, nav, report_filename= '../xls/RiskMap_model.xlsm'):
    #%%
    _, connection = fu.get_DB_conn('prod')
    
    str_sql = """
            SELECT book, [lote45_product],[lote45_product_class],[primitive],
            [primitive_class], bucket, [amount],[delta] 
            FROM [lote45].[primitive]
            WHERE date_reference = '{:%Y-%m-%d}' and trading_desk = '{}'
            and bucket <> 0
            """
    str_sql = str_sql.format(dt, str_fund)
    df = pd.read_sql(str_sql, connection)
    df = df[~((df['primitive_class']=='BRL Rate Curve') & (df['lote45_product_class'].isin(['SCS','DDI Future'])))]
    
    str_sql = """
        SELECT [id],[date_maturity]
        FROM [middle].[product]
        WHERE date_maturity >= '{:%Y-%m-%d}'
    """
    str_sql = str_sql.format(dt)
    dfVcto = pd.read_sql(str_sql, connection, index_col='id')
    
    df = df.join(dfVcto, on='lote45_product')
    
    str_sql = """
            SELECT [parent_node],[node],[book]
            FROM [lote45].[book_tree]
            WHERE parent_tree = 'Risk'
            """
    dfTree = pd.read_sql(str_sql, connection)
    tree = fu.Node('Risk', dfTree)
    dic_risk = tree.to_inv_dict('Risk')
    
    str_sql = """
            SELECT [parent_node],[node],[book]
            FROM [lote45].[book_tree]
            WHERE parent_tree = 'Traders'
            """
    dfTree = pd.read_sql(str_sql, connection)
    tree = fu.Node('Traders', dfTree)
    dic_trader = tree.to_inv_dict('Traders')    
    
    dic_share = fu.get_DailyRiskShare(dt, str_fund).iloc[-1].to_dict()
    
    connection.close()
    del str_sql
    #%%   
    df['Trader'] = df['book'].apply(lambda x: dic_trader[x])
    df['Risk'] = df['book'].apply(lambda x: dic_risk[x])     

    dic_product={'USDBRLFuture':'FX',\
                 'USDBRLOptionCall':'FX',\
                 'USDBRLOptionPut':'FX',\
                 'IBOV Options':'Eqty',\
                 'Equity Options':'Eqty',\
                 'Equity Subscription':'Eqty',\
                 'IBOVSPFuture':'Eqty',\
                 'DI1Future':'DI Fut',
                 'IDIOptionPut':'IDI',\
                 'IDIOptionCall':'IDI',\
                 'CPM Options - BMF':'Cpm Opt',\
                 'DAP Future':'DAP',\
                 'DDI Future':'DDI',\
                 'MXN TIIE SWAP':'Swap',\
                 'US Treasury Bond Future':'Trea Fut'}  
    df.replace(dic_product, inplace=True)
    #%%
    dfDIFut = df[df['lote45_product_class']=='DI Fut'].pivot_table(index='date_maturity', 
                                                                    columns=['Trader','Risk'], 
                                                                    values='delta', 
                                                                    aggfunc=np.sum).fillna(0)
    dfDIFut = dfDIFut[[c for c in dfDIFut.columns if c not in [('Shared','ALL')]]]
    dfDIFut = (dfDIFut/nav) / [dic_share[i] for (i,_) in dfDIFut.columns]
    
    # color1, color2 = fu.color_palette[0:2]
    # fig, ax = plt.subplots(1, 1, figsize=(9, 4))
    # # hide axes
    # fig.patch.set_visible(False)
    
    # ax.set_title(t, color=color1, fontsize=16, fontweight='bold')
    # ax.axis('off')
    #     # ax.axis('tight')
    #     # df = dic_trades[t].copy()
    #     # df.update(df[['PnL Stop', 'PnL Target', f"PnL on {dt:%d%b%Y}"]].applymap('{:,.0f}'.format))
    #     # df.update(df[['Date Ini', 'Date End']].applymap(lambda x: '' if x==None else '{:%d-%b-%y}'.format(x)))
    # table = ax.table(cellText=dfDIFut.values, 
    #                      colColours=[color2] * len(dfDIFut.columns),
    #                      rowColours=['gainsboro'] * len(dfDIFut),
    #                      # colWidths = [1/6]*4 + [1/3],
    #                      cellLoc='center',
    #                      colLabels=dfDIFut.columns,
    #                      rowLoc='center',
    #                      rowLabels=dfDIFut.index,
    #                      loc='center',
    #                      bbox=(0, 0, 1, 1))
    #     for (row, col), cell in table.get_celld().items():
    #         if (row == 0):
    #             cell.set_text_props(fontproperties=FontProperties(weight='bold'))
    #         elif col in [2,3,4]:
    #             v = float(cell.get_text().get_text().replace(',',''))
    #             if v<0:
    #                 cell.get_text().set_color('r')
    
    
    
    
    
    
    #%%
    
    df['days_today'] = (df['date_maturity'] - dt).dt.days
    
    df['prod_vcto'] = df.apply(lambda x: ('{:%Y-%m}'.format(x['date_maturity']) \
                               if x['date_maturity'].year in [dt.year, dt.year+1] else '{:%Y}'.format(x['date_maturity']) )\
                          if x['lote45_product_class'] in ['NTN-B','DI Fut','DAP'] \
                              else x['lote45_product_class'], axis=1)
    
    dic_curvename = {'BRL Rate Curve': 'Taxa Pré',\
                     'IPCA Coupon':'Cp IPCA',\
                     'USA Sovereign Yield': 'US', \
                    'BRD Rate Curve':'Cp Cambial',\
                     'MXN Rate Curve': 'MX'}
      
        
    dfPV01Fund = df[df['primitive_class'].isin(dic_curvename.keys())].pivot_table(columns=['Risk','lote45_product_class'], 
                        index=['prod_vcto'], \
                         values='delta', aggfunc='sum')/nav
        
    dfPV01Trader = df[df['primitive_class'].isin(dic_curvename.keys())].pivot_table(columns=['Trader', 'Risk','lote45_product_class'], 
                        index=['prod_vcto'], \
                         values='delta', aggfunc='sum')/nav
        

    #%%                    
    cols = set([i[0] for i in dfPV01Fund.columns if i[0] in ['ARBITRAGE', 'PRE', 'INFLATION']])
    traders = ['Fund'] + [i for i in ['MS', 'BC', 'NF'] if i in dfPV01Trader.columns]

    fig = plt.figure(figsize=(11, 15))
    outer = gridspec.GridSpec(4, len(cols), wspace=0.4, hspace=0.3, height_ratios=[5,3,3,3])
    
    
    axes = []
    for k, trader in enumerate(traders):
        dfPV01Prod = dfPV01Trader[trader] if trader!='Fund' else dfPV01Fund
        fc = 'None' if trader!='Fund' else 'gainsboro'
        for i, c in enumerate(cols):
            if c in dfPV01Prod.columns:
                temp = dfPV01Prod[(c)].dropna(how='all').sort_index(ascending=False) / dic_share[trader]
                
                inner = gridspec.GridSpecFromSubplotSpec(1, len(temp.columns), 
                                                         subplot_spec=outer[k, i],
                                                         wspace=0.1, hspace=0.1)
                
                for j, p in enumerate(temp.columns):
                    if j==0:
                        ax = fig.add_subplot(inner[j])
                        if k==0:
                            ax.set_title(c, ha='left' if len(temp.columns)>1 else 'center', fontweight='bold')
                        if i == 0:
                            ax0=ax
                            axes.append(ax0)
                    else:
                        ax = fig.add_subplot(inner[j], sharey=ax)
                        plt.setp(ax.get_yticklabels(), visible=False)

                    temp.loc['TOTAL', p] = temp[p].sum()
                    ax.set_xlabel(dic_curvename.get(p,p), fontweight='bold')
                    # ax.set_xticklabels([])
                    ax.set_xticks([])
                    ax.grid(ls='--', axis='y')
                    ax.axhline(len(temp[p])-1.5, color='k')                    
                
                    fontsize = (7 if len(temp) > 10 else 9 if len(temp) > 6 else 10) + (1 if trader=='Fund' else 0)
                    ax.barh(temp[p].index, temp[p].values, zorder=3, alpha=0.1, 
                            color=(temp[p] > 0).map({True: fu.color_palette[1], False: 'tomato'}))
                    ax.set_facecolor(fc)
                    ax.tick_params(axis='y', labelsize=fontsize)
                    
                    
                    
                    m = 4#max([abs(z) for z in ax.get_xlim()])
                    # ax.axvline(0, color='k', ls=':', lw=0.5)
                    ax.set_xlim(left=-m, right=m)
                    
                    for x, prod in enumerate(temp.index):
                        pl = temp.loc[prod, p]
                        if not np.isnan(pl):
                            ax.text(0, x,' {:+5.1f}'.format(pl) if pl!=0 else ' -', 
                                   fontweight='bold', fontsize=fontsize,
                                   va='center', ha='center',
                                       color=('r' if pl<0 else fu.color_palette[0]))   

                    fig.add_subplot(ax)

            else:
                inner = gridspec.GridSpecFromSubplotSpec(1, 1, 
                                                         subplot_spec=outer[k, i],
                                                         wspace=0.1, hspace=0.1)
                ax = fig.add_subplot(inner[0])
                ax.set_xticks([])
                ax.set_yticks([])
                for sp in ax.spines:
                    ax.spines[sp].set_visible(False)
                ax0=ax
                axes.append(ax0)
            
        ax0.set_ylabel('{}\n({:2.1%})'.format(trader,dic_share[trader]), fontweight='bold', fontsize=12)

    fig.align_ylabels(axes)
    
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_pv01_by_risk.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    
    wb = xw.Book(report_filename)
    wb.sheets('PV01_ByRisk').pictures.add(wb.api.Path + '/' + fig_file, name='pv01_by_risk', update=True)
    # wb.sheets('FX_IR_2').pictures.add(fig, name='pv01_by_risk', update=True)
    
       

#%%
if __name__ == "__main__":
    tic = timeit.default_timer()

    dt, str_fund = fu.get_config(['dt', 'str_fund'])
    nav = fu.get_NAV(dt, str_fund)
    report_filename = '../xls/RiskMap_model.xlsm'
  
    main(dt, str_fund, nav, report_filename) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))    