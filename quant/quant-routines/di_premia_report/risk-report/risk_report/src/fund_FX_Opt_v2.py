import QuantLib as ql 
import pandas as pd
import numpy as np
import datetime
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import sqlalchemy as sa
import fund_utils as fu

import os
path_curve_db = os.path.expanduser('~\\Documents\\Github\\market_data')
import sys
sys.path.insert(1, path_curve_db)
import curve_db 

path_curve_db = os.path.expanduser('~\\Documents\\Github\\instruments\\B3')
sys.path.insert(1, path_curve_db)
from B3Option import USDBRLOption
from B3Future import USDBRLFuture

del path_curve_db
#%%
today = ql.Date(27, 7, 2021)
str_fund = 'A1 Master FIM'
nav = fu.get_NAV(today.to_date(), str_fund)


engine = sa.create_engine('mssql+pyodbc://saprod:nhjmmn&^Yh%%^yhjU&@srvprod1.database.windows.net,1433/dbprod1?driver=SQL+Server+Native+Client+11.0')
connection = engine.connect()

str_sql = """
SELECT 'DOL' + [ExpirationCode] as id,[OptionStyle],[OptionType],[ExpirationDate],[ExercisePrice]
      ,[ReferencePrice],[VolatilityValue]/100 as vol,[DeltaValue]
  FROM [up2data].[Currency_ReferencePriceFile]
  where Asset = 'DOL' and ReportDate = '{:%Y-%m-%d}'
"""
str_sql = str_sql.format(today.to_date())
dfOpts = pd.read_sql(str_sql, connection, index_col='id')
 
str_sql = """
SELECT bo.[date_reference],[trading_desk],bt.node,bo.[book],p.product_type,
p.id, p.date_maturity, p.option_strike,p.option_style, p.option_type, round(pp.price,4) as price, [value] as qty
  FROM [lote45].[book_overview] bo INNER JOIN middle.product p ON p.id = bo.lote45_product
      INNER JOIN middle.product_price pp ON bo.date_reference = pp.date_reference and pp.product_id = p.id
	  INNER JOIN lote45.book_tree bt ON bt.book = bo.book
  WHERE bo.measure = 'Amount' and bo.date_reference = '{:%Y-%m-%d}' 
  and bt.parent_tree = 'Risk' and bt.node = 'FX'
  and trading_desk='{}'
"""
str_sql = str_sql.format(today.to_date(), str_fund)
dfPos = pd.read_sql(str_sql, connection)

str_tree = 'Traders'
str_sql = """
       SELECT [parent_tree],[parent_node],[node],[book]
       FROM [lote45].[book_tree]
       WHERE parent_tree = '{}'
                """
dfTree = pd.read_sql(str_sql.format(str_tree), connection)
nd = fu.Node(str_tree, dfTree)    
dic_books = nd.to_dict(str_tree)
inv_books = {}
for k, v in dic_books.items():
    for vi in v:
        inv_books[vi] = k
dfPos['trader'] = dfPos['book'].apply(lambda x: inv_books[x])


str_sql = """
            SELECT DISTINCT p.[date_maturity], pp.price as DOLFUT
            FROM [middle].[product] p INNER JOIN middle.product_price pp ON p.id = pp.product_id
            WHERE lote45_product_class in ('USDBRLFuture') and pp.date_reference = '{:%Y-%m-%d}'
            """
str_sql = str_sql.format(today.to_date())
dfDOL = pd.read_sql(str_sql, connection, index_col='date_maturity')

str_sql = """
            SELECT date_reference, pp.price as CASADO
            FROM  middle.product_price pp 
            WHERE product_id = 'CASADO' and pp.date_reference = '{:%Y-%m-%d}'
            """
str_sql = str_sql.format(today.to_date())
casado = pd.read_sql(str_sql, connection, index_col='date_reference').loc[today.to_date(), 'CASADO']

connection.close()
del connection, engine, str_sql
#%%
curve_brl_handle = ql.YieldTermStructureHandle(curve_db.get_curve(today.to_date(), 'DI Fut'))
curve_usd_handle = ql.YieldTermStructureHandle(curve_db.get_curve(today.to_date(), 'USD BR'))

#%%
ql.Settings.instance().evaluationDate = today
calendar = ql.Brazil()
dayCounter = ql.Business252(calendar)

#%%
# dic_opts = {'DOLUPDH':0, #-727, 
#             'DOLUPDL':367,
#             'DOLQPDL':-1640}

# ['date_reference', 'trading_desk', 'node', 'book', 'product_type', 'id',
#        'date_maturity', 'option_strike', 'option_style', 'option_type',
#        'price', 'qty', 'trader']


# for k, v in dic_opts.items():
#     dfOpts.loc[k]
#     temp = [today.to_date(), 'A1 Master FIM', 'FX', 'MS BRL', 'FX Option', 
#          k, calendar.advance(ql.Date.from_date(dfOpts.loc[k, 'ExpirationDate']), ql.Period('-1d')).to_date(), 
#          dfOpts.loc[k, 'ExercisePrice'],         
#          dfOpts.loc[k, 'OptionStyle'][0],
#         dfOpts.loc[k, 'OptionType'][0], dfOpts.loc[k, 'ReferencePrice'], v, 'MS']
#     dfPos.loc[len(dfPos)] = temp


#%%
usdbrl_spot = ql.SimpleQuote(dfDOL['DOLFUT'].iloc[0]-casado)
usdbrl_spot_handle = ql.QuoteHandle(usdbrl_spot)

dic_Asset = {}
dic_price = {}
dic_vol = {}

dfQty = dfPos.pivot_table(index='id', columns='trader', values='qty', aggfunc=np.sum).fillna(0)
pos_temp = dfPos.fillna(0).groupby(['product_type', 'id', 'date_maturity', 'option_strike', 'option_style', 'option_type',  'price']).sum().reset_index()

for (prod_type, prod_id, maturity, strike_price, style, opt_type, price, qty) in pos_temp.values:
    if prod_type == 'FX Option':
        price = dfOpts.loc[prod_id,'ReferencePrice']
        vol = dfOpts.loc[prod_id,'vol']
        dic_Asset[prod_id] = USDBRLOption(ql.Option.Put if opt_type=='P' else ql.Option.Call, strike_price, maturity)
        dic_vol[prod_id] = ql.SimpleQuote(vol)
        flat_vol_ts = ql.BlackVolTermStructureHandle(ql.BlackConstantVol(0, calendar, ql.QuoteHandle(dic_vol[prod_id]), dayCounter))
        bsm_process = ql.BlackScholesMertonProcess(usdbrl_spot_handle, curve_usd_handle, curve_brl_handle, flat_vol_ts)
        dic_Asset[prod_id].setPricingEngine(ql.AnalyticEuropeanEngine(bsm_process))
    elif prod_type == 'FX Future':
        lotSize = 10 if prod_id[0:3] == 'WDO' else 50
        dic_Asset[prod_id] = USDBRLFuture(usdbrl_spot_handle, maturity, price/usdbrl_spot.value(), lotSize)
    dfQty.loc[prod_id,'Fund'] = qty
    dic_price[prod_id] = price

#%%
spot_0 = usdbrl_spot.value()

rng = (0.90, 1.1001)
xs = np.round(np.arange(rng[0], rng[1], 0.0005), 4)
key_value_aux = 100*int(spot_0/100)
key_values = [np.round(i/spot_0, 6) for i in [key_value_aux-100*i for i in [2,1,0,-1,-2]]]
xs = sorted(np.append(xs,key_values))

cols = ['Price', 'PnL_BRL', 'Delta_BRL', 'Delta_USD']
dfSimu = pd.DataFrame(index=xs, columns=pd.MultiIndex.from_product([cols, dic_Asset.keys()], names=['measure','product_id']))

for x in xs:
    usdbrl_spot.setValue(x * spot_0)
    dfSimu.loc[x, ('Price', 'USDBRL')] = usdbrl_spot.value()
    for asset_id, asset in dic_Asset.items():
        lot_size = asset.lotSize() 
        dfSimu.loc[x, ('Price', asset_id)] = asset.NPV() 
        dfSimu.loc[x, ('PnL_BRL', asset_id)] = (asset.NPV() - dic_price[asset_id]) * lot_size  
        dfSimu.loc[x, ('Delta_USD', asset_id)] = asset.delta() * lot_size * 1000
        dfSimu.loc[x, ('Delta_BRL', asset_id)] = dfSimu.loc[x, ('Delta_USD', asset_id)] * usdbrl_spot.value()/1000
usdbrl_spot.setValue(spot_0)

#%%
cols = ['PnL_BRL', 'Delta_BRL', 'Delta_USD']  #remove PRICE
dfSimuBook = pd.DataFrame(index=dfSimu.index, columns=pd.MultiIndex.from_product([dfQty.columns, cols], names=['book','measure']))
for c in dfQty.columns:
    for m in cols:        
        dfSimuBook.loc[:,(c, m)] = dfSimu.loc[:,(m, dfQty[c].index)] @ dfQty[c].values
#%%
# dic_share = {'BC': 1, 'FK': 1, 'Fund': 1, 'GB': 1, 'MS': 1, 'NF': 1, 'PA': 1, 'TO': 1}
dic_share = fu.get_DailyRiskShare(today.to_date(), str_fund).loc[today.to_date()].sort_values().to_dict()

#%%
color1 = '#323E48'
color_palette =['#28829B', 'dodgerblue','royalblue','#C9CBCB', '#748D9E', '#2E9AB2']
fig, axes = plt.subplots(len(dfQty.columns), 2, figsize=(12, 8),sharex=True)
fig.tight_layout(h_pad=0, w_pad=0.3)

axes[0,0].set_title('Simulated Delta (%NAV)', fontweight='bold')
axes[0,1].set_title('Simulated PnL (%NAV)', fontweight='bold')
for i, c in enumerate([b for b in dic_share.keys() if b in dfQty.columns]):
    ax = axes[i, 0]
    m = 'Delta_BRL'
    ax.set_ylabel('{}\n({:2.1%})'.format(c, dic_share[c]), fontweight='bold', fontsize=12)
    ax.axhline(0, color='k', lw=0.5)
    val = dfSimuBook.loc[1, (c, m)]/nav/dic_share[c]
    ax.plot(dfSimuBook.index, dfSimuBook[c][m]/nav/dic_share[c], color=color1, ls='--', lw=3, label='Delta ({:2.1%})'.format(val))    
    ax.legend(loc=2)

    y_min, y_max = ax.get_ylim()
    for x in key_values:
        val = dfSimuBook.loc[x, (c, m)]/nav/dic_share[c]
        usdbrl_val = dfSimu.loc[x, ('Price','USDBRL')]
        if (val - y_min)/(y_max - y_min) > 0.5:
            shift_y = -50
        else:
            shift_y = 40
        
        ax.annotate('{:2.2f}\n{:2.1%}'.format(usdbrl_val/1000, val), 
                                  xy=(x, val), xycoords='data', zorder=3,
                              xytext=(0, shift_y), textcoords='offset points', fontweight='bold',
                              fontsize=8, color=color1, ha='center',
                              bbox=dict(boxstyle="round", fc='silver' if val>0 else 'tomato', ec="0.5", alpha=0.8),
                              arrowprops=dict(facecolor='r', arrowstyle="->", connectionstyle="arc3"))
   
    ax = axes[i, 1]
    ax.axhline(0, color='k', lw=0.5)
    ax.plot(dfSimuBook.index, dfSimuBook[c]['PnL_BRL']/nav/dic_share[c], color=color1, ls='--', lw=3, label='Total')
    
    y_min, y_max = ax.get_ylim()
    for x in key_values:
        val = dfSimuBook.loc[x, (c, 'PnL_BRL')]/nav/dic_share[c]
        usdbrl_val = dfSimu.loc[x, ('Price','USDBRL')]
        if (val - y_min)/(y_max - y_min) > 0.5:
            shift_y = -50
        else:
            shift_y = 40
        
        ax.annotate('{:2.2f}\n{:2.2%}'.format(usdbrl_val/1000, val), 
                                  xy=(x, val), xycoords='data', zorder=3,
                              xytext=(0, shift_y), textcoords='offset points', fontweight='bold',
                              fontsize=8, color=color1, ha='center',
                              bbox=dict(boxstyle="round", fc='silver' if val>0 else 'tomato', ec="0.5", alpha=0.8),
                              arrowprops=dict(facecolor='r', arrowstyle="->", connectionstyle="arc3"))

ax.set_xlim(left=dfSimuBook.index[0], right=dfSimuBook.index[-1])
for ax in axes.flatten():
    ax.grid(ls='--')
    ax.yaxis.set_major_locator(mticker.FixedLocator(ax.get_yticks().tolist()))
    ax.set_yticklabels(['{:2.1%}'.format(i) for i in ax.get_yticks()])
for ax in axes[-1,:]:
    ax.set_xticklabels(['{:2.3f}\n{:2.1%}'.format(dfSimu.loc[round(i,4), ('Price','USDBRL')]/1000,i-1) for i in ax.get_xticks()])
    ax.set_facecolor('gainsboro')

fig_file = '../output/temp_figs/{:%Y%m%d}_{}_usdbrl_simu_trader.svg'.format(today.to_date(), str_fund)
fig.savefig(fig_file, bbox_inches = "tight")
plt.show()
#%%

dic_vol_0 = {k:v.value() for (k,v) in dic_vol.items()}

rng = (-0.1, 0.101)
xs = np.round(np.arange(rng[0], rng[1], 0.01), 3)

dic_simu_vol = {}

dic_simu_vol['vol_PnL'] = pd.DataFrame(columns=dic_Asset.keys())
dic_simu_vol['vol_Delta'] = pd.DataFrame(columns=dic_Asset.keys())

for x in xs:
    for k, v in dic_vol_0.items():
        dic_vol[k].setValue(dic_vol_0[k]+v)
    for asset_id, asset in dic_Asset.items():
        lot_size = asset.lotSize() 
        dic_simu_vol['vol_PnL'].loc[x, asset_id] = (asset.NPV() - dic_price[asset_id]) * lot_size * dfQty.loc[asset_id, 'Fund'] / nav
        dic_simu_vol['vol_Delta'].loc[x, asset_id] = asset.delta() * usdbrl_spot.value() * lot_size * dfQty.loc[asset_id, 'Fund'] / nav

for k, v in dic_vol_0.items():
    dic_vol[k].setValue(dic_vol_0[k])




#%%

ql.Settings.instance().evaluationDate = today
#%%
for k, v in dic_Asset.items():
    print(k, v.NPV(), v.theta(), v.thetaPerDay())

#%%
dts = [calendar.advance(today, ql.Period(t, ql.Days)) for t in range(0, 10)]

dfTheta = pd.DataFrame(columns=dic_Asset.keys())

ql.Settings.instance().includeReferenceDateEvents = True
for qlDate in dts:
    ql.Settings.instance().setEvaluationDate(qlDate)
    for k, v in dic_Asset.items():
        dfTheta.loc[qlDate.to_date(), k] = v.NPV() * dfQty.loc[asset_id, 'Fund'] * v.lotSize()

dfTheta['Total'] = dfTheta.sum(axis=1)

print(dfTheta)
