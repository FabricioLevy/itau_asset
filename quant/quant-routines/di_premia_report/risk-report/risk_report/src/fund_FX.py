import pandas as pd
import numpy as np
import datetime
import timeit
import matplotlib.pyplot as plt
import xlwings as xw
import QuantLib as ql
import fund_utils as fu
import cartopy.crs as ccrs
import cartopy.feature as cfeature



#%%
def plot_fx_map (delta):
    #%%
    dic_ccy = { "USD": ( -99,  40)
               ,"BRL": ( -50, -15)
               ,"MXN": (-103,  24)
               ,"CLP": ( -70, -30)
               ,"CNH": ( 100,  33)
               ,"COP": ( -74,   4)
               ,"AUD": ( 133, -25)
               ,"ZAR": (  22, -33)
               ,"CHF": (   9,  49)
               ,"EUR": (   7,  50)
               ,"CAD": (-110,  55)
               ,"JPY": ( 140,  35)
               ,"NZD": ( 172, -36)
               ,"TRY": (  29,  41)
               ,"GBP": (  -6,  58)
               }
    
    dic_ccy_alt = { "CHF": (   5,  20)
                   ,"EUR": ( -22,  40)
                   }

    data = pd.DataFrame.from_dict(dic_ccy, orient='index', columns=['lat','lon'])
    data = data.join(delta).fillna(0)
     
    fig = plt.figure(figsize=(12, 5.25))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
    ax.set_extent([-140, 180, -63, 77], crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.LAND, color='#323E48', alpha=0.7)
    ax.add_feature(cfeature.OCEAN, color='lightcyan')
    ax.add_feature(cfeature.COASTLINE)
    
    # fig, ax = plt.subplots(1,1,figsize=(12,12))
    # m=Basemap(llcrnrlon=-140, llcrnrlat=-63,urcrnrlon=180,urcrnrlat=77, ax=ax)
    # m.drawmapboundary(fill_color='lightcyan', linewidth=0)
    # m.fillcontinents(color='#323E48', alpha=0.7, lake_color='#323E48')
    # m.drawcoastlines(linewidth=0.1, color="white")
    
    texts = []
    for k, v in dic_ccy.items():
        d = data.loc[k,'Fund']
        if k in ['CHF', 'EUR']:
            texts.append(ax.annotate('{}\n{:+0.1%}'.format(k, d) if d!=0 else '{}\n-'.format(k),
                            xy=v, xycoords="data", va="center", ha="center", fontweight='bold',
                            xytext=dic_ccy_alt[k],
                          bbox=dict(boxstyle="round", fc='#28829B' if d>0 else 'tomato' if d<0 else 'silver'),
                         arrowprops=dict(arrowstyle="->", connectionstyle="arc3, rad=0.2", lw=1.5)))
        else:
            texts.append(ax.annotate('{}\n{:+0.1%}'.format(k, d) if d!=0 else '{}\n-'.format(k),
                            xy=v, xycoords="data", va="center", ha="center", fontweight='bold',
                          bbox=dict(boxstyle="round", fc='#28829B' if d>0 else 'tomato' if d<0 else 'silver')))
        
        
    # adjust_text(texts)
    #%%
    return fig
#%%


#%%
def main(dt, str_fund, nav, report_filename): 
    #%%
    _, connection = fu.get_DB_conn('prod')    
    
    str_sql = "SELECT br.[node] as 'book_risk', p.book, p.primitive, p.delta "+\
                    "FROM [lote45].[primitive] p INNER JOIN [lote45].[book_tree] br ON p.book = br.book "+\
                    "WHERE primitive_class = 'FX' and br.parent_tree = 'Risk' "+\
                    "and p.date_reference = '{:%Y-%m-%d}' and p. trading_desk = '{}'".format(dt, str_fund)
    df = pd.read_sql(str_sql, connection)
    
    
    # today = ql.Date.from_date(dt)
    # if ql.Brazil(ql.Brazil.Exchange).isEndOfMonth(today):
    #     print('!!!!!!\n{}\nEnd of Month: Attention on DDI and DOLFUT expiring!\n!!!!!!'.format(__file__))
    #     str_sql = """
    #                     SELECT br.node, sum([value]) as delta
    #               FROM [lote45].[book_overview] p INNER JOIN [lote45].[book_tree] br ON p.book = br.book
    #               where measure = 'USDBRLPTAX' and br.parent_tree = 'risk'
    #               and date_reference = '{:%Y-%m-%d}' and trading_desk = '{}'
    #               GROUP BY br.node
    #               """      
    #     str_sql = str_sql.format(dt, str_fund)
    #     df2 = pd.read_sql(str_sql, connection, index_col='node')
    #     df2['USD'] = df2['delta']
    #     df2['BRL'] = -df2['delta']
    #     dfPtax = df2[['USD', 'BRL']].T /nav
    #     del df2
    # else:    
    #     cols = list(df['book_risk'].unique())
    #     dfPtax = pd.DataFrame(index=['USD', 'BRL'], columns=cols, data=np.zeros((2,len(cols))))
        
        
    connection.close()
    del str_sql, connection
    
    #%%
    list_ccy=[]
    for c in df['primitive'].unique():
        list_ccy.append([c, c[0:3], 1])
        list_ccy.append([c, c[3:6], -1])

    dfFXHelp = pd.DataFrame(data=list_ccy, columns=['primitive', 'ccy', 'factor'])
    dfFX = df.merge(dfFXHelp, left_on='primitive', right_on='primitive')
    dfFX['delta'] *= dfFX['factor']
    dfFX = dfFX[['book_risk', 'book', 'ccy', 'delta']]
    
    del dfFXHelp, list_ccy
    #%%

    dfPlot = dfFX.pivot_table(index='ccy', columns='book_risk', values='delta', aggfunc=np.sum)/nav
    # dfPlot = dfPlot.sub(dfPtax, fill_value=0).fillna(0)
    dfPlot.fillna(0, inplace=True)
    ir_books = ['IR DM', 'IR LATAM']
    if all(x in dfPlot.columns for x in ir_books):
        dfPlot['RATES'] = dfPlot[['IR DM', 'IR LATAM']].sum(axis=1)
        dfPlot.drop(ir_books, axis=1, inplace=True)
    dfPlot['Fund'] = dfPlot.sum(axis=1)
    dfPlot.sort_values('Fund', ascending=False, inplace=True)
    dfPlot.rename({'ALL':'HEDGE\nOFF'}, axis=1, inplace=True)
    n = len(dfPlot.columns)
    
    if n>1:
        fig, ax = plt.subplots(nrows=n, ncols=1, figsize=(5, 3), gridspec_kw={'height_ratios': (n-1)*[1]+[1]},\
                               sharey=True, sharex=True)
        plt.tight_layout()
        fig.subplots_adjust(hspace=0.05)
        
        for j, b in enumerate(dfPlot.columns):
            dfPlot[b].plot.bar(ax=ax[j], legend=False, zorder=2, stacked=False, \
                               color=fu.color_palette[1], rot=0, subplots=True)
            for i, ccy in enumerate(dfPlot.index):
                y = float(dfPlot.loc[ccy, b])
                c = 'r' if y<0 else 'k'
                ax[j].text(i, max(0, y), '{:2.1f}'.format(100*y) if y!=0 else '-', va='bottom',\
                         color=c, ha='center', fontweight='bold', fontsize=9) 
            
            ax[j].set_xticks([], minor=True)
            ax[j].set_yticks([])
            ax[j].grid(ls='--', axis='y')
            ax[j].axhline(0, lw=0.5, c='grey')
            ax[j].set_xlabel('')
            ax[j].set_ylabel(b.replace(' ','\n') if b =='CUPOM CAMBIAL' else b, rotation=0, fontsize=8, ha='right', va='center')
            ax[j].set_title('')
            ax[j].tick_params(labelsize=11)
        ax[0].set_ylim(top=max(0.1, 2*float(dfPlot.max().max())), bottom=min(-.1, 1.1*float(dfPlot.min().min())))
        ax[0].set_yticklabels([])
        ax[j].set_ylabel(b.replace(' ','\n'), rotation=0, fontweight='bold', fontsize=10, ha='right', va='center')
        ax[j].set_facecolor('lightgrey')
        
        for i, t in enumerate(ax[j].get_xticklabels()):
            if t.get_text() in ['USD', 'BRL']:
                # t.set_color(color1)
                t.set_fontweight('bold') 
                
            
        fig_file = '../output/temp_figs/{:%Y%m%d}_{}_dashboard_fx.svg'.format(dt, str_fund)
        fig.savefig(fig_file, bbox_inches = "tight")
        plt.show()
        
        wb = xw.Book(report_filename)
        wb.sheets('Cover').pictures.add(wb.api.Path + '/' + fig_file, name='dashboard_fx', update=True)
        
        fig2 = plot_fx_map(dfPlot['Fund'].round(8))
        fig_file = '../output/temp_figs/{:%Y%m%d}_{}_map_fx.svg'.format(dt, str_fund)
        fig2.savefig(fig_file, bbox_inches = "tight")#, transparent = True, pad_inches = 0)
        
        # wb.sheets('FX_IR').pictures.add(fig2, name='map_fx', update=True)
        wb.sheets('FX_IR').pictures.add(wb.api.Path + '/' + fig_file, name='map_fx', update=True)
 
#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt, str_fund = fu.get_config(['dt', 'str_fund'])
    report_filename = '../xls/RiskMap_model.xlsm'
    nav = fu.get_NAV(dt, str_fund)
    main(dt, str_fund, nav, report_filename) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))