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
def main(str_fund, today):
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
    DECLARE @date_query AS DATETIME = '{:%Y-%m-%d}'
    SELECT bo.[date_reference],[trading_desk],bt.node,bo.[book],p.product_type,
    p.id, p.date_maturity, p.option_strike,p.option_style, p.option_type,pp.price, [value] as qty
      FROM [lote45].[book_overview] bo INNER JOIN middle.product p ON p.id = bo.lote45_product
          INNER JOIN middle.product_price pp ON bo.date_reference = pp.date_reference and pp.product_id = p.id
    	  INNER JOIN lote45.book_tree bt ON bt.book = bo.book
      WHERE bo.measure = 'Amount' and bo.date_reference =  @date_query AND p.[date_maturity] > @date_query
      
      --!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
      AND bo.[book] = 'MS BRL'
      --!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
      
      and bt.parent_tree = 'Risk' and bt.node = 'FX'
      and trading_desk='{}'
    """
    str_sql = str_sql.format(today.to_date(), str_fund)
    dfPos = pd.read_sql(str_sql, connection)
    
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
    usdbrl_spot = ql.SimpleQuote(dfDOL['DOLFUT'].iloc[0]-casado)
    usdbrl_spot_handle = ql.QuoteHandle(usdbrl_spot)
    
    dic_Asset = {}
    dic_position = {}
    dic_price = {}
    dic_vol = {}
    
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
        dic_position[prod_id] = qty
        dic_price[prod_id] = price
    
    #%%
    spot_0 = usdbrl_spot.value()
    
    rng = (0.90, 1.1001)
    xs = np.round(np.arange(rng[0], rng[1], 0.0005), 4)
    key_value_aux = 100*int(spot_0/100)
    key_values = [np.round(i/spot_0, 6) for i in [key_value_aux-100*i for i in [2,1,0,-1,-2]]]
    xs = sorted(np.append(xs,key_values))
    
    dic_simu = {}
    
    dic_simu['Price'] = pd.DataFrame(columns=['USDBRL'] + list(dic_Asset.keys()))
    dic_simu['PnL'] = pd.DataFrame(columns=dic_Asset.keys())
    dic_simu['PnL_BRL'] = pd.DataFrame(columns=dic_Asset.keys())
    dic_simu['Delta'] = pd.DataFrame(columns=dic_Asset.keys())
    dic_simu['Delta_USD'] = pd.DataFrame(columns=dic_Asset.keys())
    dic_simu['Theta_USD'] = pd.DataFrame(columns=dic_Asset.keys())
    
    for x in xs:
        usdbrl_spot.setValue(x * spot_0)
        dic_simu['Price'].loc[x, 'USDBRL'] = usdbrl_spot.value()
        for asset_id, asset in dic_Asset.items():
            lot_size = asset.lotSize() 
            dic_simu['Price'].loc[x, asset_id] = asset.NPV()
            dic_simu['PnL'].loc[x, asset_id] = (asset.NPV() - dic_price[asset_id]) * lot_size * dic_position[asset_id] / nav
            dic_simu['PnL_BRL'].loc[x, asset_id] = (asset.NPV() - dic_price[asset_id]) * lot_size * dic_position[asset_id] 
            dic_simu['Delta'].loc[x, asset_id] = asset.delta() * usdbrl_spot.value() * lot_size * dic_position[asset_id] / nav
            dic_simu['Delta_USD'].loc[x, asset_id] = asset.delta() * lot_size * dic_position[asset_id] * 1000
    usdbrl_spot.setValue(spot_0)
    
    #%%
    product_types = list(dfPos['product_type'].unique())
    for simu_key in ['PnL', 'Delta', 'Delta_USD', 'PnL_BRL']:
        dic_simu[simu_key]['Total'] = dic_simu[simu_key][dfPos['id'].unique()].sum(axis=1)
        for prod_type in product_types:
            ids = dfPos[dfPos['product_type']==prod_type]['id'].values
            dic_simu[simu_key][prod_type] = dic_simu[simu_key][ids].sum(axis=1)
    # del prod_type
    
    #%%
    color1 = '#323E48'
    color_palette =['#28829B', 'dodgerblue','royalblue','#C9CBCB', '#748D9E', '#2E9AB2']
    fig, axes = plt.subplots(2,2,figsize=(12, 6),sharex=True)
    fig.tight_layout(h_pad=2)
    
    ax=axes[0,0]
    ax.set_title('Simulated Delta (%NAV)')
    for j, prod in enumerate(product_types):
        ax.plot(dic_simu['Delta'].index, dic_simu['Delta'][prod], color=color_palette[j], label=prod)
    ax.plot(dic_simu['Delta'].index, dic_simu['Delta']['Total'], color='k', ls='--', lw=3, label='Total')
    y_min, y_max = ax.get_ylim()
    for i, x in enumerate(key_values):
        val = dic_simu['Delta'].loc[x,'Total']
        usdbrl_val = dic_simu['Price'].loc[x, 'USDBRL']
        if (val - y_min)/(y_max - y_min) > 0.5:
            shift_y = -50
        else:
            shift_y = 40
        
        ax.annotate('{:2.2f}\n{:2.1%}'.format(usdbrl_val/1000, val), 
                                 xy=(x, val), xycoords='data', zorder=3,
                              xytext=(0, shift_y), textcoords='offset points', fontweight='bold',
                              fontsize=11, color=color1, ha='center',
                              bbox=dict(boxstyle="round", fc='silver' if val>0 else 'tomato', ec="0.5", alpha=0.8),
                arrowprops=dict(facecolor='r', arrowstyle="->", connectionstyle="arc3"))
    
    val = dic_simu['Delta'].loc[1,'Total']
    ax.annotate('{:2.1%}'.format(val), 
                                 xy=(1, val), xycoords='data', zorder=2,
                              xytext=(0.5, 0.05), textcoords='axes fraction', fontweight='bold',
                              fontsize=12, color=color1, ha='center',
                              bbox=dict(boxstyle="round", fc='silver' if val>0 else 'r', ec="0.5", alpha=0.8),
                arrowprops=dict(facecolor='r', arrowstyle="->", connectionstyle="arc3"))
    
    
    
    ax=axes[1,0]
    ax.set_title('Simulated Delta (USD)')
    for j, prod in enumerate(product_types):
        ax.plot(dic_simu['Delta_USD'].index, dic_simu['Delta_USD'][prod], color=color_palette[j],label=prod)
    ax.plot(dic_simu['Delta_USD'].index, dic_simu['Delta_USD']['Total'], color='k', ls='--', lw=3, label='Total')
    
    ax=axes[0,1]
    ax.set_title('Simulated PnL (%NAV)')
    for j, prod in enumerate(product_types):
        ax.plot(dic_simu['PnL'].index, dic_simu['PnL'][prod], color=color_palette[j],label=prod)
    ax.plot(dic_simu['PnL'].index, dic_simu['PnL']['Total'], color='k', ls='--', lw=3, label='Total')
    
    ax=axes[1,1]
    ax.set_title('Simulated PnL (BRL)')
    for j, prod in enumerate(product_types):
        ax.plot(dic_simu['PnL_BRL'].index, dic_simu['PnL_BRL'][prod], color=color_palette[j],label=prod)
    ax.plot(dic_simu['PnL_BRL'].index, dic_simu['PnL_BRL']['Total'], color='k', ls='--', lw=3, label='Total')
    
    ax.set_xlim(left=dic_simu['Price'].index[0], right=dic_simu['Price'].index[-1])
    for ax in axes.flatten():
        ax.grid(ls='--')
        ax.axhline(0, color='k', lw=0.5)
        ax.legend()
        ax.yaxis.set_major_locator(mticker.FixedLocator(ax.get_yticks().tolist()))
    for ax in axes[0,:]:
        ax.set_yticklabels(['{:2.1%}'.format(i) for i in ax.get_yticks()])
    for ax in axes[1,:]:
        ax.set_xticklabels(['{:2.3f}\n{:2.1%}'.format(dic_simu['Price'].loc[round(i,4), 'USDBRL']/1000,i-1) for i in ax.get_xticks()])
        ax.set_yticklabels(['{:2,.0f}M'.format(i/10**6) for i in ax.get_yticks()])
    
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_usdbrl_simu.svg'.format(today.to_date(), str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()

#%%
if __name__ == '__main__':
    today = ql.Date(23, 9, 2021)
    main('A1 Master FIM', today)
    main('A1 Orange FIM', today)