import pandas as pd
import numpy as np
import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
from matplotlib.lines import Line2D
import QuantLib as ql
import adjustText

import os, sys
sys.path.insert(1, os.path.expanduser('~\\Documents\\Github\\instruments\\LatamSwap'))
import MxnSwap
import ClpSwap 
import CopSwap 
from SwapUtils import SwapUtils

sys.path.insert(1, os.path.expanduser('~\\Documents\\Github\\market_data'))
import curve_db as cdb
    
from a1db.a1sql import SQLConnection

def main(dt, str_fund):
    #%%
    connection = SQLConnection().get_connection()
    
    ## Position
    str_sql = f"""
            SELECT [date_reference],[lote45_product],[book],[currency],[financial_price],
           [price],[amount],[position_pnl],[trading_pnl],[pnl],[position]
            FROM [lote45].position
            WHERE lote45_product_class in ('MXN TIIE SWAP', 
                                           'CLP Fixed-Float SWAP',
                                           'COP Fixed-Float SWAP')
                and trading_desk = '{str_fund}'
                and date_reference BETWEEN '2022-5-11' and '{dt:%Y-%m-%d}'
    """
    dfPos = pd.read_sql(str_sql,
                        connection)
    prods = set(dfPos[dfPos['date_reference']==dt]['lote45_product'].unique())         
    books = set(dfPos[dfPos['date_reference']==dt]['book'].unique())    
    dates = sorted(set(dfPos[dfPos['book'].isin(books)]['date_reference'].unique()))
    prod_books = dfPos[dfPos['lote45_product'].isin(prods) & dfPos['book'].isin(books)][['lote45_product', 'book']].drop_duplicates()
    dfPos = dfPos.set_index(['date_reference', 'lote45_product', 'book'])
    
    ## Swap details    
    str_sql =  f"""
                SELECT lote45_product_class,[lote45_product],[product_currency],[product_underlying],
                    [date_issue],[date_maturity],[swap_fixed_rate]
                FROM [middle].[product]
                WHERE lote45_product_class in ('MXN TIIE SWAP', 
                                               'CLP Fixed-Float SWAP',
                                               'COP Fixed-Float SWAP')
                and date_issue <= '{dt:%Y-%m-%d}'
                """
    df = pd.read_sql(str_sql, 
                     connection)
    
    ## Index and Currencies    
    str_sql = f"""
    SELECT ts.entity_id,[date_reference],[value]
      FROM [quant].[time_series_value] tsv 
    	INNER JOIN quant.time_series ts ON tsv.series_id =ts.id
      WHERE ts.id in (77, 82, 44, 11933, 19, 79, 853, 81) 
      and date_reference between '2022-5-1' and '{dt:%Y-%m-%d}'
      """
    dfIndex = pd.read_sql(str_sql, 
                          connection).pivot(index='date_reference', 
                                            columns='entity_id',
                                            values='value').sort_index().fillna(method='ffill')
    
    ##### currencies ######
    ql.Money.setConversionType(ql.Money.AutomatedConversion)
    usd = ql.USDCurrency()
    clp = ql.CLPCurrency()
    cop = ql.COPCurrency()
    mxn = ql.MXNCurrency()
    brl = ql.BRLCurrency()
    dic_currencies = {str_ccy:ccy for (ccy, str_ccy) in zip([cop, clp, mxn, brl], ['USDCOP','USDCLP', 'USDMXN', 'USDBRL'])}
    for dti in dfIndex.index:
        ql_dt = ql.Date.from_date(dti)
        for str_ccy, ccy in dic_currencies.items():
            ql.ExchangeRateManager.instance().add(ql.ExchangeRate(usd, 
                                                                  ccy, 
                                                                  dfIndex.loc[dti, str_ccy]), 
                                                  ql_dt, 
                                                  ql_dt)
    #######################
    
    
    dfIndex = dfIndex.rename({'MXN TIIE 28D':'MXN TIIE SWAP',
                              'CLP IR Swap 1D':'CLP Fixed-Float SWAP',
                              'COOVIBR':'COP Fixed-Float SWAP'}, axis=1)
                  
    dic_str_curve_zero = {'MXN TIIE SWAP': 'MXN TIIE Zero',
                          'CLP Fixed-Float SWAP': 'Swap CLP Zero',
                          'COP Fixed-Float SWAP': 'Swap COP Zero'}                          
    dic_index, dic_curve = {}, {}
    
    dic_curve['MXN TIIE SWAP'] = ql.RelinkableYieldTermStructureHandle()
    dic_index['MXN TIIE SWAP'] =  ql.IborIndex('TIIE',
                                               ql.Period(ql.EveryFourthWeek), 
                                               1, 
                                               ql.MXNCurrency(), 
                                               ql.Mexico(), 
                                               ql.Following, 
                                               False, 
                                               ql.Actual360(),
                                               dic_curve['MXN TIIE SWAP'])
    ql.IndexManager.instance().clearHistory(dic_index['MXN TIIE SWAP'].name())
    
    
    dic_curve['CLP Fixed-Float SWAP'] = ql.RelinkableYieldTermStructureHandle()
    dic_index['CLP Fixed-Float SWAP'] = ql.OvernightIndex('ICP',
                                                           0,
                                                           ql.CLPCurrency(), 
                                                           ClpSwap.CLPHolidays(), 
                                                           ql.Actual360(),
                                                           dic_curve['CLP Fixed-Float SWAP'])
    ql.IndexManager.instance().clearHistory(dic_index['CLP Fixed-Float SWAP'].name())
    
    dic_curve['COP Fixed-Float SWAP'] = ql.RelinkableYieldTermStructureHandle()
    dic_index['COP Fixed-Float SWAP'] = ql.OvernightIndex('IBR',
                                                           0,
                                                           ql.COPCurrency(), 
                                                           CopSwap.COPHolidays(), 
                                                           ql.Actual360(),
                                                           dic_curve['COP Fixed-Float SWAP'])
    ql.IndexManager.instance().clearHistory(dic_index['COP Fixed-Float SWAP'].name())
    
    #%%
    dic_swaps = {}
    dic_cashflows = {}
    for (prod_class, prod, ccy, p_und, dt_issue, dt_exp, swap_rate) in df.values:
        dt_issue = ql.Date.from_date(dt_issue)
        dt_exp = ql.Date.from_date(dt_exp)
        if prod_class == 'MXN TIIE SWAP':
            dt_settle = ql.Mexico().advance(dt_issue, ql.Period("1d"))
            dic_swaps[prod] = MxnSwap.MxnTiieSwap(ql.VanillaSwap.Payer, 
                                                  1, 
                                                  dt_settle, 
                                                  dt_exp, 
                                                  swap_rate, 
                                                  dic_index['MXN TIIE SWAP'])
            dic_swaps[prod].setPricingEngine(ql.DiscountingSwapEngine(dic_curve['MXN TIIE SWAP']))
        elif prod_class == 'CLP Fixed-Float SWAP':
            dt_settle = ClpSwap.CLPHolidays().advance(dt_issue, ql.Period("2d"))
            dic_swaps[prod] = ClpSwap.ClpSwap(1,
                                             dt_settle, 
                                             dt_exp, 
                                             swap_rate,
                                             dic_index['CLP Fixed-Float SWAP'])
            dic_swaps[prod].setPricingEngine(ql.DiscountingSwapEngine(dic_curve['CLP Fixed-Float SWAP']))
        elif prod_class == 'COP Fixed-Float SWAP':
            dt_settle = CopSwap.COPHolidays().advance(dt_issue, ql.Period("2d"))
            dic_swaps[prod] = CopSwap.CopSwap(1,
                                             dt_settle, 
                                             dt_exp, 
                                             swap_rate,
                                             dic_index['COP Fixed-Float SWAP'])
            dic_swaps[prod].setPricingEngine(ql.DiscountingSwapEngine(dic_curve['COP Fixed-Float SWAP'] ))
        # dic_cashflows[prod] = SwapUtils.cashflow_to_pandas(dic_swaps[prod])
    
    #%%    
    cols = [(i,j,s) for i,j in prod_books.values for s in ['Lote45', 'Asset1']]
    dfMtM = pd.DataFrame(index=dates, 
                         columns=pd.MultiIndex.from_tuples(cols, 
                                                           names=['lote45_product', 
                                                                  'book', 
                                                                  'source']))
    sorted_cols, _ = dfMtM.columns.sortlevel()
    
    dfMtM = dfMtM[sorted_cols]
    dfPrice = pd.DataFrame(index=dates, 
                         columns=sorted_cols)
    
    for dti  in dates:
        print("\n", dti)
        reaval_date = ql.Date.from_date(dti)
        ql.Settings.instance().evaluationDate = reaval_date
        
        for index_id in dic_index.keys():
            if not dic_index[index_id].fixingCalendar().isHoliday(ql.Date.from_date(dti)):
                dic_index[index_id].addFixing(ql.Date.from_date(dti),
                                             dfIndex.loc[dti, index_id]/100)
                dic_curve[index_id].linkTo(cdb.get_curve(reaval_date.to_date(), dic_str_curve_zero[index_id]))
        
        # usdmxn = dfIndex.loc[dti, 'USDMXN']
        # usdclp = dfIndex.loc[dti, 'USDCLP']
        
        for prod, book in prod_books.values: 
            if (dti, prod, book) in dfPos.index:
                amount = dfPos.loc[(dti, prod, book), 'amount']
                lote45_price = dfPos.loc[(dti, prod, book), 'financial_price']
                lote45_rate = dfPos.loc[(dti, prod, book), 'price']
                lote45_mtm = dfPos.loc[(dti, prod, book), 'position']
                print(book, prod, sep="  -  ")
                
                if prod in dic_swaps.keys():
                    if  dic_swaps[prod].mtmStartDate().to_date() <= dti:
                        price = dic_swaps[prod].NPV()
                        usdccy_value = ql.ExchangeRateManager.instance().lookup(dic_currencies[dic_swaps[prod].currency()], 
                                                                                usd, 
                                                                                ql.Settings.instance().evaluationDate).rate()
                        usdccy_value = dfIndex.loc[dti, dic_swaps[prod].currency()]
                        mtm = price * amount / usdccy_value
                        
                        print(dfIndex.loc[dti, dic_swaps[prod].currency()], usdccy_value)
                        
                        print(f"Lote45 Price: {lote45_price:11,.8f}  Rate: {lote45_rate:8.4%}")
                        print(f"Asset1 Price: {price:11,.8f}  Rate: {dic_swaps[prod].fairRate():8.4%}")
                        
                        dfMtM.loc[dti, (prod, book, 'Lote45')] = lote45_mtm  
                        dfMtM.loc[dti, (prod, book, 'Asset1')] = mtm  
                        
                        dfPrice.loc[dti, (prod, book, 'Lote45')] = lote45_rate
                        dfPrice.loc[dti, (prod, book, 'Asset1')] = dic_swaps[prod].fairRate()
                        
                        dic_cashflows[(prod, dti)] = SwapUtils.cashflow_to_pandas(dic_swaps[prod], dic_curve['MXN TIIE SWAP'])
    
    dfMtM /= 1_000
    #%%
    dic_color = {'USDMXN': 'darkgreen',
                 'USDCOP': 'gold',
                 'USDCLP': 'darkred'}
    
    num_subplots={0: (1, 1),
                  1: (1, 1), 2: (2, 1), 3: (2, 2),
                  4: (2, 2), 5: (2, 3), 6: (2, 3),
                  7: (2, 4), 8: (2, 4), 9: (3, 3),
                  10:(3, 4),11: (3, 4),12: (3, 4)}
    
    n_col, n_row = num_subplots[len(prod_books)]
    
    fig, axes = plt.subplots(n_row, 
                             n_col, 
                             squeeze=False, 
                             figsize=(9.5, min(3*n_row, 11.6)))
    fig.tight_layout(h_pad=3)
    
    for ax, (prod, book) in zip(axes.flatten(), prod_books.values):
        dfPlot = dfMtM[(prod, book)].dropna()
        ax.set_title(f"{book}\n{prod}", 
                     fontsize=10 if len(prod_books)<9 else 8, 
                     fontweight='bold')
        txts=[]
        for m, c in zip(['Lote45', 'Asset1'], ['grey','#28829B']):
            ax.plot(dfPlot.index, dfPlot[m], marker='s', 
                    label=f"{m} ({dfPlot[m].iloc[-1]:2,.3g}k)", c=c, lw=2.5)
            
            for dti in dfPlot.index[-1:]:
                txts.append(ax.text(dti, dfPlot.loc[dti, m], 
                        "{:6.3%}".format(dfPrice.loc[dti, (prod, book, m)]),
                        color=c, fontweight='bold', ha='left', va='center'))
        
        ax.yaxis.set_major_locator(plt.MaxNLocator(6))
        locator = mdates.AutoDateLocator(minticks=2, 
                                         maxticks=5)
        formatter = mdates.ConciseDateFormatter(locator, 
                                                formats=['%b%y', '%b%y', '%d%b', '', '', ''], 
                                                show_offset=False)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)   
        ax.axhline(0, c='k', lw=0.5)
        ax.grid(ls='--')
        ax.set_xlim(dfPlot.index[0])
        adjustText.adjust_text(txts, ax=ax)
        ax.legend(fontsize=9)
        ax.patch.set_alpha(0.2)
        # ax1.patch.set_facecolor(color)
        ax.set_facecolor(dic_color[dic_swaps[prod].currency()])
        
        [ax.get_yticklabels()[i].set_color('red') if (ax.get_yticks()[i] < 0 ) \
         else ax.get_yticklabels()[i].set_color('black') for i in range(len(ax.get_yticklabels()))]
    
    for i in range(axes.shape[0]):
        axes[i,0].set_ylabel("MtM (k USD)", fontweight='bold')
    
    for i, ax in enumerate(axes.flatten()):
        if i>=len(prod_books):
             ax.axis('off')
    
    fig.align_ylabels()
    
    legend_elements = [Line2D([0], [0], color=c, lw=5, ls='-', alpha=0.4) for c in dic_color.values()]
    
    plt.figlegend(legend_elements, [k[3:] for k in dic_color.keys()], loc = 'lower center', 
                  borderaxespad=0.2, ncol=4, labelspacing=0.,  prop={'size': 10, 'weight':'bold'}, 
                  bbox_to_anchor=(0.5, -0.02)) 
    
    
    plt.show()
    #%%
    return fig

#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 7, 19)
    str_fund = 'A1 Hedge SP'
    
    fig1 = main(dt, str_fund) 
    #%%
    fig_file = '../output/temp_figs/offshore/{:%Y%m%d}_{}_swaplatam.pdf'.format(dt, str_fund)
    # fig1.set_figwidth(9)
    # fig1.set_figheight(8.4, False)
    fig1.savefig(fig_file,
                bbox_inches = 'tight', #facecolor='silver',
                pad_inches = 0)
    
    