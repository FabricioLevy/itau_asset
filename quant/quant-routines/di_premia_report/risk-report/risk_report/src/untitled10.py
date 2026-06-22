import pandas as pd
import numpy as np
import datetime
import timeit
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import QuantLib as ql
import xlwings as xw
import fund_utils as fu
import fund_data

import os
import sys 
sys.path.insert(1, os.path.expanduser('~\\Documents\\Github\\market_data'))
import curve_db 

path_instruments = os.path.expanduser('~\\Documents\\Github\\instruments\\B3')
sys.path.insert(1, path_instruments)
import B3Option, B3Future


#%%
dt = datetime.date(2022, 1, 18)
str_fund = 'A1 Master FIM'
nav = fu.get_NAV(dt, str_fund)

my_db = fund_data.db_data(dt, str_fund)

#%%
def delta(self):
        return 1
ql.Stock.delta = delta
#%%
ids = "','".join(set(my_db._dfPosition[['id','product_underlying']].fillna('x').values.flatten()))
    
str_sql = """
            SELECT [product_id],[price] FROM [middle].[product_price]
            WHERE product_id in ('{}') and date_reference = '{:%Y-%m-%d}'
      """
dic_price = pd.read_sql(str_sql.format(ids, dt), my_db._connection, index_col='product_id')['price'].to_dict()
dic_Underlying = {underlying_id: ql.SimpleQuote(dic_price[underlying_id]) for underlying_id in set(my_db._dfPosition[my_db._dfPosition['product_type']=='Equity Option']['product_underlying'].dropna())}

str_sql = f"""
            SELECT [TickerSymbol], [VolatilityValue]/100 as vol
            FROM [up2data].[Equities_OptionOnEquitiesReferencePriceFile]
            WHERE [ReportDate] = '{dt:%Y-%m-%d}'
            """
dic_vol = pd.read_sql(str_sql, my_db._connection, index_col='TickerSymbol')['vol'].to_dict()

calendar_br = ql.Brazil()
today = ql.Date.from_date(dt)
ql.Settings.instance().evaluationDate = today
day_count = ql.Business252(calendar_br)
    
curve_name = 'DI Fut'
risk_free = curve_db.get_curve(today.to_date(), curve_name)
risk_free_handle = ql.YieldTermStructureHandle(risk_free)
    
dic_Asset = {}

dfPos = my_db._dfPosition.pivot_table(index='lote45_product', columns='product_underlying', values='Amount', aggfunc=np.sum)[dic_Underlying.keys()].dropna(how='all')
   
cols = ['id', 'product_type', 'date_maturity', 'product_underlying', 'lot_size',
        'option_type','option_style','option_strike','price']
dfAsset = my_db._dfPosition[cols].drop_duplicates()
dfAsset.set_index('id', inplace=True)
for opt_id, (product_type, dt_exp, underlying_id, _, opt_type, opt_style, opt_strike, price) in dfAsset[dfAsset['product_type']=='Equity Option'].iterrows():
 
    ql_opt_type = ql.Option.Call if opt_type.upper() == 'C' else ql.Option.Put
    option = B3Option.EquityOption(ql_opt_type, opt_strike, ql.Date.from_date(dt_exp), 
                                   dic_Underlying[underlying_id], ql.SimpleQuote(dic_vol[opt_id[:-3]]), risk_free_handle)
    dic_Asset[opt_id] = option
    print(f"{opt_id:15} Price:  {price:8.2f} {option.NPV():8.2f}")
    

cols = ['product_underlying', 'date_maturity', 'lot_size']
for product_id, row in dfAsset[dfAsset['product_type']=='Equity Future'].iterrows():
    (underlying_id, dt_exp, lot_size)= row[cols]
    print(lot_size)
    future = B3Future.IbovespaFuture(ql.QuoteHandle(dic_Underlying[underlying_id]), ql.Date.from_date(dt_exp), lot_size)
    future.setPricingEngine(ql.DiscountingBondEngine(risk_free_handle))
    dic_Asset[product_id] = future

for product_id in dic_Underlying.keys():
    dic_Asset[product_id] = ql.Stock(ql.QuoteHandle(dic_Underlying[product_id]))

#%%
rng = (0.60, 1.401)
xs = np.round(np.arange(rng[0], rng[1], 0.005), 4)

dic_simu = {}

for underlying_id in dic_Underlying.keys():
    spot = dic_Underlying[underlying_id]
    spot_0 = dic_price[underlying_id]
    products = set([underlying_id] + list(dfPos[underlying_id].dropna().index))
    temp_df = pd.DataFrame(index=xs, columns=pd.MultiIndex.from_product([products, ['Price','PnL', 'Delta']], names=['product_id','measure']))
    for x in xs:
        spot.setValue(x * spot_0)
        # dic_Underlying[underlying_id].setValue(spot_0*x)
        
        for product_id in products:
            asset = dic_Asset[product_id]
            lot_size = asset.lotSize() if type(asset)==B3Future.IbovespaFuture else 1
            qty = dfPos[underlying_id].get(product_id, 0)
            temp_df.loc[x, (product_id, 'Price')] = asset.NPV()
            temp_df.loc[x, (product_id, 'PnL')] = (asset.NPV() - dic_price[product_id]) * qty /nav * lot_size
            temp_df.loc[x, (product_id, 'Delta')] = (asset.delta() * dic_Underlying[underlying_id].value()) * qty / nav
        
    spot.setValue(spot_0)
    df_total = temp_df.groupby(level=1, axis=1).sum()
    temp_df[('Total','Delta')] = df_total['Delta']
    temp_df[('Total','PnL')] = df_total['PnL']
    
    dic_simu[underlying_id] = temp_df


#%%
num_subplots={1: (1, 1),
              2: (2, 1),
              3: (2, 2),
              4: (2, 2),
              5: (3, 2),
              6: (3, 2),
              7: (4, 2),
              8: (4, 2),
              9: (3, 3)}
n_col, n_row = num_subplots[len(dic_Underlying)]
color1, color2 = fu.color_palette[0:2]
fig, axes = plt.subplots(n_row, n_col, squeeze=False, figsize=(12, 3*n_row))
fig.tight_layout(w_pad=1, h_pad=3)

for underlying_id, ax in zip(dic_Underlying.keys(), axes.flatten()):
    
    dfPlot = dic_simu[underlying_id]

    ax.set_title(underlying_id, fontweight='bold')
    ax.grid(ls='--')
    ax.axhline(0, lw=0.5, c='k')
    
    ax.plot(dfPlot.index, dfPlot[('Total','PnL')]*10_000, lw=2.5, c='k', ls='--')
    
    for k in dfPos[underlying_id].dropna().index:
        ax.plot(dfPlot.index, dfPlot[(k,'PnL')]*10_000, lw=2, ls=":", label=k)
    
    ax.legend(fontsize=8)
    
    ticks_loc = [0.6, 0.8, 1, 1.2, 1.4]
    ax.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))    
    if underlying_id == 'IBOV':
        ax.set_xticklabels([f"{i-1:+2.0%}\n{dfPlot.loc[round(i,2), (underlying_id, 'Price')]/1_000:2.0f}K" for i in ax.get_xticks()])
    else:
        ax.set_xticklabels([f"{i-1:+2.0%}\n{dfPlot.loc[round(i,2), (underlying_id, 'Price')]:2.1f}" for i in ax.get_xticks()])
    
    

    
# fig.subplots_adjust(bottom=0.15/n_row)
# legend_elements = [l_plot, l_stop, l_target, l_price]
# plt.figlegend(legend_elements, [l.get_label() for l in legend_elements], loc = 'lower center', 
#               borderaxespad=0.1, ncol=4, labelspacing=0.,  prop={'size': 11, 'weight':'normal'},) 
fig.savefig('t.svg', bbox_inches = "tight")
plt.show()
