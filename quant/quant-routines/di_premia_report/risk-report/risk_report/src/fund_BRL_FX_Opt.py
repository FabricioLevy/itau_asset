import pandas as pd
import numpy as np
import timeit
import datetime
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import xlwings as xw
import fund_utils as fu
import QuantLib as ql 

import os
import sys
sys.path.insert(1, os.path.expanduser('~\\Documents\\Github\\market_data'))
import curve_db 

sys.path.insert(1, os.path.expanduser('~\\Documents\\Github\\instruments\\B3'))
from B3Option import USDBRLOption
from B3Future import USDBRLFuture

#%%
def main(dt, str_fund, nav, report_filename= '../xls/RiskMap_model.xlsm', print_pdf=False):
    #%%
    today = ql.Date.from_date(dt)
    today_b3 = ql.Brazil(ql.Brazil().Exchange).adjust(today, ql.Preceding)

    _, connection = fu.get_DB_conn('prod')
    
    str_sql = """
    SELECT 'DOL' + [ExpirationCode] as id,[OptionStyle],[OptionType],[ExpirationDate],[ExercisePrice]
          ,[ReferencePrice],[VolatilityValue]/100 as vol,[DeltaValue]
      FROM [up2data].[Currency_ReferencePriceFile]
      where Asset = 'DOL' and ReportDate = '{:%Y-%m-%d}'
    """
    str_sql = str_sql.format(today.to_date())
    dfOpts = pd.read_sql(str_sql, connection, index_col='id')
     
    # str_sql = """
    # SELECT bo.[date_reference],[trading_desk],bt.node,bo.[book],p.product_type,
    # p.id, p.date_maturity, p.option_strike,p.option_style, p.option_type, round(pp.price,4) as price, [value] as qty
    #   FROM [lote45].[book_overview] bo INNER JOIN middle.product p ON p.id = bo.lote45_product
    #       INNER JOIN middle.product_price pp ON bo.date_reference = pp.date_reference and pp.product_id = p.id
    # 	  INNER JOIN lote45.book_tree bt ON bt.book = bo.book
    #   WHERE bo.measure = 'Amount' and bo.date_reference = '{:%Y-%m-%d}' 
    #   and bt.parent_tree = 'Risk' and bt.node = 'FX'
    #   and trading_desk='{}'
    # """
    str_sql =f"""
            SELECT bo.[date_reference],[trading_desk],bt.node,bo.[book],p.product_type,
            p.id, p.date_maturity, p.option_strike,p.option_style, p.option_type, round(pp.price,4) as price, [value] as qty
              FROM [lote45].[book_overview] bo INNER JOIN middle.product p ON p.id = bo.lote45_product
                  INNER JOIN middle.product_price pp ON bo.date_reference = pp.date_reference and pp.product_id = p.id
            	  INNER JOIN lote45.book_tree bt ON bt.book = bo.book
              WHERE bo.measure = 'Amount' 
                  and bo.date_reference = '{today.to_date():%Y-%m-%d}' 
                  and p.date_maturity > '{today.to_date():%Y-%m-%d}' 
                  and bt.parent_tree = 'Risk' 
                  and bt.node = 'FX'
                  and (product_underlying = 'USDBRL' or product_currency= 'BRL')
                  and product_type not in ('DI1Future','Equity Future')
                  and trading_desk='{str_fund}'
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
    str_sql = str_sql.format(today_b3.to_date())
    dfDOL = pd.read_sql(str_sql, connection, index_col='date_maturity')
    
    str_sql = """
                SELECT date_reference, pp.price as CASADO
                FROM  middle.product_price pp 
                WHERE product_id = 'CASADO' and pp.date_reference = '{:%Y-%m-%d}'
                """
    str_sql = str_sql.format(today.to_date())
    casado = pd.read_sql(str_sql, connection, index_col='date_reference').loc[today.to_date(), 'CASADO']
    
    connection.close()
    del connection, str_sql
    #%%
    curve_brl_handle = ql.YieldTermStructureHandle(curve_db.get_curve(today.to_date(), 'DI Fut'))
    curve_usd_handle = ql.YieldTermStructureHandle(curve_db.get_curve(today.to_date(), 'USD BR'))
    
    ql.Settings.instance().evaluationDate = today
    calendar = ql.Brazil()
    dayCounter = ql.Business252(calendar)
    
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
    simu_dates = list(dfPos['date_maturity'].dropna().unique())
    dic_share = fu.get_DailyRiskShare(today.to_date(), str_fund).loc[today.to_date()].sort_values().to_dict()
    
    dfGreeks = pd.DataFrame(data = 0,
                            index = dfQty.index,
                            columns = ['Premium', 'Delta', 'Gamma', 'Vega', 'Theta'])
    
    for asset_id, asset in dic_Asset.items():
        lot_size = asset.lotSize()
        dfGreeks.loc[asset_id, 'Delta'] = asset.delta() * usdbrl_spot.value() * lot_size
        if isinstance(asset, ql.Option):
            dfGreeks.loc[asset_id, 'Premium'] = asset.NPV() * lot_size
            dfGreeks.loc[asset_id, 'Gamma'] = asset.gamma() * (usdbrl_spot.value() ** 2) * lot_size/100
            dfGreeks.loc[asset_id, 'Vega'] = asset.vega() * lot_size
            dfGreeks.loc[asset_id, 'Theta'] = asset.thetaPerDay() * lot_size
            
    dfTraderGreeks = (dfGreeks.T @ dfQty)/nav
    
    for t in dfTraderGreeks.columns:
        dfTraderGreeks[t] = dfTraderGreeks[t] / dic_share[t]
    
    #%%
    spot_0 = usdbrl_spot.value()
    
    rng = (0.90, 1.1001)
    xs = np.round(np.arange(rng[0], rng[1], 0.0005), 4)
    key_value_aux = 100*int(spot_0/100)
    key_values = [np.round(i/spot_0, 6) for i in [key_value_aux-100*i for i in [2,1,0,-1,-2]]]
    xs = sorted(set(np.append(xs,key_values)))
    
    
    dfSimulation = pd.DataFrame(index=xs, 
                                columns=pd.MultiIndex.from_product([[dt] + simu_dates,
                                                                    ['Price','PnL', 'Delta'],
                                                                    ['USDBRL'] + list(dfQty.index)], 
                                                                   names=['simu_date','measure','product_id']))
    for simu_date in [dt] + simu_dates:
        ql.Settings.instance().setEvaluationDate(ql.Date.from_date(simu_date))
        for x in xs:
            usdbrl_spot.setValue(x * spot_0)
            dfSimulation.loc[x, (simu_date, 'Price', 'USDBRL')] = usdbrl_spot.value()
            for asset_id, asset in dic_Asset.items():
                lot_size = asset.lotSize() 
                dfSimulation.loc[x, (simu_date, 'Price', asset_id)] = asset.NPV() 
                dfSimulation.loc[x, (simu_date, 'PnL', asset_id)] = (asset.NPV() - dic_price[asset_id]) * lot_size  
                dfSimulation.loc[x, (simu_date, 'Delta', asset_id)] = asset.delta() * lot_size * usdbrl_spot.value()
                
    usdbrl_spot.setValue(spot_0)
    
    #%%
    product_types = list(dfPos['product_type'].unique())
    
    dfTraderSimulation = pd.DataFrame(columns = pd.MultiIndex.from_product([[dt] + simu_dates,
                                                                            ['PnL', 'Delta'],
                                                                            dfQty.columns,
                                                                            product_types],
                                                                           names = ['simu_date', 'metric', 'trader', 'product']))
    
    for simu_date in [dt] + simu_dates:
        for simu_key in ['PnL', 'Delta']:
            for prod in product_types:
                for t in dfQty.columns:
                    ids = dfPos[dfPos['product_type'] == prod]['id'].unique()
                    dfTraderSimulation.loc[:,(simu_date, simu_key, t, prod)] = (dfSimulation.loc[:, (simu_date, simu_key, ids)] @ dfQty.loc[ids, t].values) / dic_share[t]
    
    dfTraderSimulation /= nav
    
    dfWorstPnL = pd.DataFrame(index=simu_dates, 
                              columns=pd.MultiIndex.from_product([dfQty.columns, 
                                                                          ['PnL', 'SnP']],
                                                                         names=['trader','Value']))
    for t in dfQty.columns:
        for simu_date in  simu_dates:
            temp_pnl = dfTraderSimulation.loc[:,(simu_date, 'PnL', t, product_types)].sum(axis=1)
            dfWorstPnL.loc[simu_date, t] = temp_pnl.min(),  temp_pnl.idxmin()-1
    
    #%%
    color1 = '#323E48'
    color_palette =['#28829B', 'dodgerblue','royalblue','#C9CBCB', '#748D9E', '#2E9AB2']
    
    temp_pos = dfQty.abs().join(dfPos.set_index('id')['product_type']).groupby('product_type').sum()
    
    fig, axes = plt.subplots(len(dfQty.columns), 3, 
                             gridspec_kw={'height_ratios':[3]*(len(dfQty.columns)-1) + [4], 
                                          'width_ratios':[6, 6, 1]},
                             figsize=(13, 8.7), sharex=True)
    plt.tight_layout(w_pad=2.3, h_pad=0.1)
    
    axes[0,0].set_title('Simulated Delta',fontweight='bold')
    axes[0,1].set_title('Simulated PnL',fontweight='bold')
    axes[0,2].set_title('Greeks       ',fontweight='bold')
    for j in [0,1]:
        axes[-1, j].set_facecolor('gainsboro')

    
    for ax_i, t in enumerate(dfQty.columns):        
        ##### DELTA ####
            
        ax=axes[ax_i, 0]
        ax.set_ylabel(f'{t}\n({dic_share[t]:2.1%})',fontweight='bold',fontsize=11)
        for p_i, prod in enumerate(product_types):
            if temp_pos.loc[prod, t] != 0:
                ax.plot(dfTraderSimulation.index,
                        dfTraderSimulation.loc[:,(dt, 'Delta', t, prod)],
                        ls='-', 
                        lw=2, 
                        color=color_palette[p_i], 
                        label=f"{prod.split(' ')[-1]} ({dfTraderSimulation.loc[1,(dt, 'Delta', t, prod)]:+7.1%})")
                
        ax.plot(dfTraderSimulation.index,
                 dfTraderSimulation.loc[:,(dt, 'Delta', t, product_types)].sum(axis=1),
                 ls='--', lw=3.5, color='k', 
                 label=f"TOTAL ({dfTraderSimulation.loc[1,(dt, 'Delta', t, product_types)].sum():+7.1%})")
                
        
        y_min, y_max = ax.get_ylim()
        ax.set_ylim(bottom=min(y_min, -0.001), top=max(y_max, 0.001))
        ax.legend(fontsize=9)

        ##### PNL ####
        ax=axes[ax_i, 1]
        
        for p_i, prod in enumerate(product_types):
            if temp_pos.loc[prod, t] != 0:
                ax.plot(dfTraderSimulation.index,
                        dfTraderSimulation.loc[:,(dt, 'PnL', t, prod)],
                        ls='-', 
                        lw=2, 
                        color=color_palette[p_i], 
                        label=f"{prod.split(' ')[-1]}")
                
        temp_pnl = dfTraderSimulation.loc[:,(dt, 'PnL', t, product_types)].sum(axis=1)
        
        pnl_min = temp_pnl.min()
        x_min = temp_pnl.idxmin()   
        ax.annotate('USDBRL:{:+7.1%}\nPnL:{:+8.2%}'.format(x_min-1, pnl_min), 
                    xytext=(0.5, 0.85), 
                    textcoords="axes fraction",
                    xy=(x_min, pnl_min), 
                    xycoords='data', va="center", ha="center", fontweight='bold',
                    bbox=dict(boxstyle="round", fc='tomato', alpha=0.5),
                    arrowprops=dict(arrowstyle="->", connectionstyle="arc3, rad=-0.2", lw=1.5))
        
        worst_pnl = dfWorstPnL[t]['PnL'].min()
        worst_snp = dfWorstPnL[t]['SnP'].min()
        # ax.annotate('SnP:{:+7.1%}\nPnL:{:+8.2%}'.format(worst_snp, worst_pnl), 
        #             xytext=(0.90, 0.85), 
        #             textcoords="axes fraction",
        #             fontsize=8,
        #             xy=(x_min, pnl_min), 
        #             xycoords='data', va="center", ha="center", fontweight='bold',
        #             bbox=dict(boxstyle="round", fc='red', alpha=0.5))
        
        ax.plot(temp_pnl.index,
                 temp_pnl,
                 ls='--', lw=3.5, color='k', 
                 label="TOTAL")
        
        y_min, y_max = ax.get_ylim()
        ax.set_ylim(bottom=min(y_min, -0.001), top=max(y_max, 0.001))   
        
        ##### Greeks ####
        ax=axes[ax_i, 2]
        ax.axis('off')
        Premium = dfTraderGreeks.loc['Premium', t]
        Delta = dfTraderGreeks.loc['Delta', t]
        Gamma = dfTraderGreeks.loc['Gamma', t]
        Vega = dfTraderGreeks.loc['Vega', t]
        Theta = dfTraderGreeks.loc['Theta', t]
        ax.annotate(f"{Premium=:+8,.2%}\n\n{Delta=:+8,.2%}\n\n{Gamma=:+8,.2%}\n\n{Vega=:+8,.2%}\n\n{Theta=:+8,.2%}", 
                    xytext=(0.98, 0.85), 
                    textcoords="axes fraction",
                    fontsize=9,
                    xy=(1, 1), 
                    xycoords='data', va="top", ha="right", fontweight='bold',
                    bbox=dict(boxstyle="round", fc='blue', alpha=0.2))
            
        for ax in (axes[ax_i, 0], axes[ax_i, 1]):
            ticks_loc = ax.get_yticks().tolist()
            ax.yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
            ax.set_yticklabels(['{:2.1%}'.format(i) for i in ticks_loc])   
            ax.axhline(0, color='k', lw=0.75, ls='--')
            # ax.axvline(1, color='k', lw=0.75, ls='--')
            ax.grid(ls='--')
            ax.set_xlim(left=dfSimulation.index[0], right=dfSimulation.index[-1])
            ticks_loc = ax.get_xticks().tolist()
            ax.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
            ax.set_xticklabels(['{:2.1%}\n{:2,.0f}'.format(i-1, dfSimulation.loc[round(i,4), (dt, 'Price','USDBRL')]) for i in ticks_loc])
            
       
    ##### ####
    axes[ax_i, 0].set_xlabel('USDBRL change (%) and simulated level (USD)',fontweight='bold')
    axes[ax_i, 1].set_xlabel('USDBRL change (%) and simulated level (USD)',fontweight='bold')
    fig.align_ylabels()
       
    if print_pdf:
         fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_{1}_usdbrl_simu_trader.pdf'.format(dt, str_fund)
         fig.savefig(fig_file, bbox_inches = "tight")

    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_usdbrl_simu_trader.svg'.format(today.to_date(), str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    
    wb = xw.Book(report_filename)
    wb.sheets('FX_IR').pictures.add(wb.api.Path + '/' + fig_file, name='usdbrl_fx_opt', update=True)
    # wb.sheets('FX_IR_2').pictures.add(fig, name='usdbrl_fx_opt', update=True)
    plt.show()


#%%

if __name__ == "__main__":
    tic = timeit.default_timer()

    dt, str_fund = fu.get_config(['dt', 'str_fund'])
    nav = fu.get_NAV(dt, str_fund)
    report_filename = '../xls/RiskMap_model.xlsm'
  
    main(dt, str_fund, nav, report_filename, False) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))  