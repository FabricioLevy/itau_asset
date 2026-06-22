import pandas as pd
import numpy as np
import datetime
import timeit
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import xlwings as xw
import fund_utils as fu


#%%
def main(dt, str_fund, nav, report_filename): 
    #%%
    _, connection = fu.get_DB_conn('prod')
    
    str_sql = """
            SELECT [lote45_product_class],[primitive],sum([delta]) as delta
          FROM [lote45].[primitive]
          where date_reference = '{}' and primitive_class = 'Equity' and trading_desk = '{}'
          group by [lote45_product_class],[primitive]
            """
    
    str_sql = str_sql.format(dt, str_fund)
                    
    df = pd.read_sql(str_sql, connection)
    connection.close()
    del str_sql, connection
    
    df.replace({'Equity Receipts':'Equity', 
                'US Equity':'Equity',
                'ADR':'Equity',
                'Equity Options':'Eqty Opt',
                'Equity Subscription':'Equity',
                'S&P500 E-mini Futures':'S&P',
                'S&P500 E-mini Options':'S&P',
                'IBOV Options':'IBOV Opt',
                'IBOVSPFuture':'IBOV/EWZ',
                'BDR Unsponsored':'BDR',
                'NASDAQ-100 E-mini Futures - CME': 'NASDAQ',
                'DJ Euro STOXX 50 Future - EUREX': 'Eur Stoxx',
                'Russell 2000 Index Mini Futures - CME':'Russell 2k'}, inplace=True)
    
    df.loc[df['primitive']=='EWZ','lote45_product_class'] = 'IBOV/EWZ'
    
    #%%
    dfEqty = df.pivot_table(index='lote45_product_class', values='delta', aggfunc=np.sum)/nav
    dfEqty = dfEqty.join(df[df['delta']>0].groupby('lote45_product_class').sum()/nav, rsuffix='_long')
    dfEqty = dfEqty.join(df[df['delta']<0].groupby('lote45_product_class').sum()/nav, rsuffix='_short')
    dfEqty.sort_values(by='delta', inplace=True)
    
    #%%

    if len(dfEqty) > 0:
        fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(5, 1.7))
        plt.tight_layout()
         
        ax.barh(dfEqty.index, dfEqty['delta'], color=fu.color_palette[1], zorder=3, label='Net')
        ax.barh(dfEqty.index, dfEqty['delta_long'], color=fu.color_palette[1], zorder=4, alpha=0.3, label='Gross')
        ax.barh(dfEqty.index, dfEqty['delta_short'], color=fu.color_palette[1], zorder=4, alpha=0.3)
        
        ax.barh('Net Total', dfEqty['delta'].sum(), color=fu.color_palette[0], zorder=3)
        ax.legend()
        for i, c in enumerate(dfEqty.index):
            x = float(dfEqty.loc[c, 'delta'])
            c = 'r' if x<0 else 'k'
            ax.text(max(0, x), i, ' {:2.1%}'.format(x), va='center',\
                             color=c, ha='left', fontweight='bold', fontsize=9) 
        
        x = dfEqty['delta'].sum()
        c = 'r' if x<0 else 'k'
        ax.text(max(0, x), i+1, ' {:2.1%}'.format(x), va='center',\
                             color=c, ha='left', fontweight='bold', fontsize=11) 
        ax.axhline(i+0.5, color=fu.color_palette[0], lw=1)
        ax.get_yticklabels()[-1].set_fontweight('bold')
            
        ax.grid(ls='--', axis='x', which='both')
        ax.axvline(0, lw=0.75, c='k')
        ax.set_ylabel('')
        ax.tick_params(labelsize=11)
        ax.set_xlim(right=max(0.06, 1.25*float(dfEqty.max().max()), 1.25*dfEqty['delta'].sum()), 
                    left=min(-.06, 1.2*float(dfEqty.min().min()),1.2*dfEqty['delta'].sum()))
        if ax.get_xlim()[1]-ax.get_xlim()[0] < 0.3:
            ax.xaxis.set_minor_locator(mticker.MultipleLocator(0.01))
        ax.xaxis.set_major_locator(mticker.MultipleLocator(0.05))
        ticks_loc = ax.get_xticks().tolist()
        ax.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
        ax.set_xticklabels(['{:1.0%}'.format(i) for i in ticks_loc])
    
        fig_file = '../output/temp_figs/{:%Y%m%d}_{}_dashboard_equity.svg'.format(dt, str_fund)
        fig.savefig(fig_file, bbox_inches = "tight")
        plt.show()
        wb = xw.Book(report_filename)
        wb.sheets('Cover').pictures.add(wb.api.Path + '/' + fig_file, name='dashboard_equity', update=True)
 
#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt, str_fund = fu.get_config(['dt', 'str_fund'])
    report_filename = '../xls/RiskMap_model.xlsm'
    nav = fu.get_NAV(dt, str_fund)
    main(dt, str_fund, nav, report_filename) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))
    
