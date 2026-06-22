import pandas as pd
import numpy as np
import datetime
import timeit
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import QuantLib as ql
import xlwings as xw
import fund_utils as fu

import os
import sys
path_curve_db = os.path.expanduser('~\\Documents\\Github\\market_data')
sys.path.insert(1, path_curve_db)
import curve_db 

path_instruments = os.path.expanduser('~\\Documents\\Github\\instruments')
sys.path.insert(1, path_instruments)
from B3 import B3Future

#%%

class EquityOption(ql.VanillaOption):
    def __init__(self, payoff, exercise, lot_size = 1):
        self._lotSize = lot_size
        return super().__init__(payoff, exercise)
    
    def delta(self):
        return super().delta() * self._lotSize
    
    def lotSize(self):
        return self._lotSize
    
    
#%%

class Equity(ql.Stock):
    def __init__(self,quote, lot_size = 1):
        self._lotSize = lot_size
        return super().__init__(quote)
    
    def delta(self):
        return 1 * self._lotSize
    
    def lotSize(self):
        return self._lotSize
        
        
def main(dt, str_fund, nav, report_filename, print_pdf=False): 
    #%%
    dt = ql.Brazil(ql.Brazil().Exchange).adjust(ql.Date.from_date(dt), ql.Preceding).to_date()
    _, connection = fu.get_DB_conn('prod')
    
    dic_share = fu.get_DailyRiskShare(dt, str_fund).loc[dt].to_dict()
    
    str_tree = 'Traders'
    str_sql = """
       SELECT [parent_tree],[parent_node],[node],[book]
       FROM [lote45].[book_tree]
       WHERE parent_tree = '{}'
                """
    dfTree = pd.read_sql(str_sql.format(str_tree), connection)
    nd = fu.Node(str_tree, dfTree)    
    dic_books = nd.to_inv_dict(str_tree)   
    
    str_sql = """
        SELECT [primitive1],[primitive2],[covar_value]
        FROM [lote45].[covar_matrix]
        WHERE date_reference = '{:%Y-%m-%d}' 
        ORDER BY 1, 2
        """
    str_sql = str_sql.format(dt)
    df = pd.read_sql(str_sql, connection)
    dfCovarDB = df.pivot(index='primitive1', columns='primitive2', values='covar_value').fillna(0)
    dfBeta = pd.DataFrame((dfCovarDB['IBVSP'] + dfCovarDB.loc['IBVSP']) / dfCovarDB.loc['IBVSP', 'IBVSP'])
    dfBeta.loc['IBVSP']=1
    dfBeta.loc['IBOV']=1
    dic_beta = dfBeta['IBVSP'].to_dict()
            
    str_sql = """
           SELECT [id] as product_id,[product_type],[lote45_product],[lote45_product_class]
          ,[product_currency],[product_underlying],[date_maturity]
          ,[option_type],[option_style],[option_strike], lot_size
      FROM [middle].[product]
      WHERE ((product_type in ('Equity Option', 'Equity Future') and date_maturity > '{:%Y-%m-%d}')
             or product_type = 'Equity')
          and onshore_risk = 1
            """
    str_sql = str_sql.format(dt)
    dfAsset = pd.read_sql(str_sql, connection)
    dfAsset = dfAsset[dfAsset['lote45_product_class'] != 'Equity Subscription']
    
    ids = "','".join(set(dfAsset[['product_id','product_underlying']].fillna('x').values.flatten()))
    
    str_sql = """
                SELECT [product_id],[price] FROM [middle].[product_price]
                WHERE product_id in ('{}') and date_reference = '{:%Y-%m-%d}'
      """
    str_sql = str_sql.format(ids, dt)
    dfPrice = pd.read_sql(str_sql, connection, index_col='product_id')
    dic_price = dfPrice['price'].to_dict()
    
    str_sql = """
    SELECT p.id as product_id, bo.book, sum(bo.value) as amount
      FROM [lote45].[book_overview] bo INNER JOIN middle.product p ON bo.lote45_product = p.lote45_product
      WHERE bo.date_reference = '{0:%Y-%m-%d}' and bo.trading_desk = '{1}' and bo.measure = 'Amount'
      and p.product_type in ('Equity Option','Equity Future', 'Equity')
      and p.lote45_product_class != 'Equity Subscription'
      and ( (p.date_maturity>'{0:%Y-%m-%d}') or (p.date_maturity is null))
      --and book='MS Bolsa'
      and onshore_risk = 1
      GROUP BY p.id, bo.book
    """
    str_sql = str_sql.format(dt, str_fund)
    dfPosition = pd.read_sql(str_sql, connection)
    dfPosition['trader'] = dfPosition['book'].apply(lambda x: dic_books[x])
    dfPosition = dfPosition.pivot_table(index='product_id', 
                                        columns='trader', 
                                        values='amount',
                                        aggfunc=np.sum).fillna(0)    
    dfPosition['Fund'] = dfPosition.sum(axis=1)
    dfPosition = dfPosition[sorted(dfPosition.columns, key=dic_share.get)]
    
    dfCheck = dfPosition[~dfPosition.index.isin(dfPrice.index)]
    
    if not dfCheck.empty:
        raise Exception("Os seguintes produtos não tem preço na tabela middle.product_price:" + 
                        "\n".join([f"{i}" for i in dfCheck.index]))
        
    # traders = ['MS','BC','GB','PA','FK','TO','NF','Shared','Fund']
    # for t, b in dic_books.items():
    #     books = [i for i in dfPosition.columns if i in b]
    #     if len(books) > 0:
    #         dfPosition[t] = dfPosition[[i for i in dfPosition.columns if i in b]].sum(axis=1)
    #     else:
    #         traders.remove(t)
    
    
    dfAsset = dfAsset.join(dfPosition['Fund'], on='product_id').join(dfPrice, on='product_id')
    dfAsset = dfAsset[~dfAsset['Fund'].isna()]
    dfAsset.loc[dfAsset['product_type']=='Equity', 'product_underlying'] = dfAsset['product_id']
    dfAsset.set_index('product_id', inplace=True)

    simu_dates = set(dfAsset['date_maturity'].dropna())
    # del str_sql, ids, connection, df, dfPrice, dfBeta, dfCovarDB
    del str_sql, ids, df, dfPrice, dfBeta, dfCovarDB

    #%%
    # def delta(self):
    #     return 1
    # ql.Stock.delta = delta

    #%%
    today = ql.Date.from_date(dt)
    ql.Settings.instance().setEvaluationDate(today)
    ql.Settings.instance().includeReferenceDateEvents = True
    calendar_br = ql.Brazil()
    day_count = ql.Business252(calendar_br)
    
    curve_name = 'DI Fut'
    risk_free = curve_db.get_curve(today.to_date(), curve_name)
    risk_free_handle = ql.YieldTermStructureHandle(risk_free)
    
    # Add Underlyings to dictionary
    dic_Underlying = {underlying_id: ql.SimpleQuote(dic_price[underlying_id]) for underlying_id in set(dfAsset['product_underlying'].dropna())}

#%%
    if 'IBOV' not in dic_Underlying.keys():
        dic_Underlying['IBOV'] = ql.SimpleQuote(dic_price['IBOV'])

    dic_Asset = {}
    dic_Vol = {}
    
    cols = ['product_underlying', 'date_maturity', 'option_type', 'option_style', 'option_strike','lot_size']
    for opt_id, row in dfAsset[dfAsset['product_type']=='Equity Option'].iterrows():
        (underlying_id, dt_exp, opt_type, opt_style, opt_strike, lot_size) = row[cols]
        ql_opt_type = ql.Option.Call if opt_type.upper() == 'C' else ql.Option.Put
        ql_dt_exp = ql.Date.from_date(dt_exp)
        # set_SimuDates.add(calendar_br.advance(ql_dt_exp, ql.Period('-1d')))
        exercise = ql.EuropeanExercise(ql_dt_exp) #if opt_style.upper() == 'E' else ql.AmericanExercise(calculation_date, ql_dt_exp)
        payoff = ql.PlainVanillaPayoff(ql_opt_type, opt_strike)
        option = EquityOption(payoff, exercise, lot_size)
           
        # volatility = ql.SimpleQuote(1.0)
        dic_Vol[opt_id] = ql.SimpleQuote(1.0)
        flat_vol_ts = ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, calendar_br, ql.QuoteHandle(dic_Vol[opt_id]), day_count))
        bsm_process = ql.BlackScholesProcess(ql.QuoteHandle(dic_Underlying[underlying_id]), risk_free_handle, flat_vol_ts)
        try:
            str_sql = """
                        SELECT [ReportDate], [VolatilityValue]/100 as vol
                        FROM [up2data].[Equities_OptionOnEquitiesReferencePriceFile]
                        WHERE [ReportDate] = '{:%Y-%m-%d}'
                        AND [TickerSymbol] = '{}'
                      """
            str_sql = str_sql.format(dt,opt_id[:-3])
            dic_Vol[opt_id].setValue(pd.read_sql(str_sql, connection, index_col='ReportDate').loc[dt, 'vol'])
        except:
            dic_Vol[opt_id].setValue(option.impliedVolatility(dic_price[opt_id], bsm_process))
            
        option.setPricingEngine(ql.AnalyticEuropeanEngine(bsm_process))
        dic_Asset[opt_id] = option    
   
#%%
    connection.close()
#%%
    cols = ['product_underlying', 'date_maturity', 'lot_size']
    for product_id, row in dfAsset[dfAsset['product_type']=='Equity Future'].iterrows():
        (underlying_id, dt_exp, lot_size) = row[cols]
        future = B3Future.IbovespaFuture(ql.QuoteHandle(dic_Underlying[underlying_id]), ql.Date.from_date(dt_exp), lot_size)
        future.setPricingEngine(ql.DiscountingBondEngine(risk_free_handle))
        dic_Asset[product_id] = future
    # del product_id, underlying_id, dt_exp
#%%
    cols = ['lot_size']    
    for product_id, row in dfAsset[dfAsset['product_type']=='Equity'].iterrows():
        lot_size = dfAsset.loc[product_id, 'lot_size']
        eqty = Equity(ql.QuoteHandle(dic_Underlying[product_id]), lot_size)
        dic_Asset[product_id] = eqty
    # del product_id
    
#%%
    dfGreeks = pd.DataFrame(0,
                            index = dfPosition.index,
                            columns = ['Premium','Delta', 'Gamma', 'Vega', 'Theta'])
    
    for asset_id, asset in dic_Asset.items():
        lotSize = asset.lotSize()
        dfGreeks.loc[asset_id, 'Delta'] = asset.delta() * dic_Underlying[dfAsset.loc[asset_id, 'product_underlying']].value()
        if isinstance(asset, ql.Option):
            dfGreeks.loc[asset_id, 'Premium'] = asset.NPV() * lotSize
            dfGreeks.loc[asset_id, 'Gamma'] = (asset.gamma() * lotSize *  dic_Underlying[dfAsset.loc[asset_id, 'product_underlying']].value() ** 2)/100
            dfGreeks.loc[asset_id, 'Vega'] = asset.vega() * lotSize
            dfGreeks.loc[asset_id, 'Theta'] = asset.thetaPerDay() * lotSize
            
    dfTraderGreeks = (dfGreeks.T @ dfPosition) / nav
    for t in dfTraderGreeks.columns:
        dfTraderGreeks[t] = dfTraderGreeks[t] / dic_share[t]
    
#%%
    ibov = dic_Underlying['IBOV']
    ibov_0 = ibov.value()
    
    rng = (0.85, 1.1501)
    xs = np.round(np.arange(rng[0], rng[1], 0.0005), 4)
    key_value_aux = 5*int(ibov_0/5000)
    key_values = [np.round(1000*i/ibov_0, 6) for i in [key_value_aux-5*i for i in [2,1,0]]]
    xs = sorted(np.append(xs,key_values))
    
    dfSimulation = pd.DataFrame(columns=pd.MultiIndex.from_product([[dt] + list(simu_dates),
                                                                    ['Price','PnL', 'Delta'], 
                                                                    ['IBOV'] + list(dic_Asset.keys())], 
                                                                   names=['simu_date','metric', 'asset']))
    
    for simu_date in [dt] + list(simu_dates):
        ql.Settings.instance().setEvaluationDate(ql.Date.from_date(simu_date))
        for x in xs:
            ibov.setValue(x * ibov_0)
            for underlying_id in [x for x in dic_Underlying.keys() if x not in ['IBOV']]:
                dic_Underlying[underlying_id].setValue(dic_price[underlying_id]*(1+((x-1)*dic_beta.get(underlying_id, 1))))
            dfSimulation.loc[x, (simu_date,'Price', 'IBOV')] = ibov.value()
            for asset_id, asset in dic_Asset.items():
                lot_size = asset.lotSize()
                dfSimulation.loc[x, (simu_date, 'Price', asset_id)] = asset.NPV()
                dfSimulation.loc[x, (simu_date, 'PnL', asset_id)] = (asset.NPV() - dic_price[asset_id]) * lot_size
                dfSimulation.loc[x, (simu_date, 'Delta', asset_id)] = asset.delta() * dic_Underlying[dfAsset.loc[asset_id, 'product_underlying']].value()
                
            
    ibov.setValue(ibov_0)
    for underlying_id in dic_Underlying.keys():
        dic_Underlying[underlying_id].setValue(dic_price[underlying_id])
        
    ql.Settings.instance().setEvaluationDate(today)
        
#%%
    product_types = list(dfAsset['product_type'].unique())
    dfTraderSimulation = pd.DataFrame(columns=pd.MultiIndex.from_product([[dt] + list(simu_dates),
                                                                            ['PnL', 'Delta'], 
                                                                          dfPosition.columns, 
                                                                          product_types],
                                                                         names=['simu_date','metric', 'trader', 'product']))
    for simu_date in [dt] + list(simu_dates):
        for simu_key in ['PnL', 'Delta']:
            for prod_type in product_types:
                for t in dfPosition.columns:
                    ids = dfAsset[dfAsset['product_type']==prod_type].index
                    dfTraderSimulation.loc[:, (simu_date,simu_key, t, prod_type)] = (dfSimulation.loc[:,(simu_date, simu_key,ids)] @ dfPosition.loc[ids, t].values) / dic_share[t]
                    
    dfTraderSimulation /= nav
    
    dfWorstPnL = pd.DataFrame(index=simu_dates, 
                              columns=pd.MultiIndex.from_product([dfPosition.columns, 
                                                                          ['PnL', 'SnP']],
                                                                         names=['trader','Value']))
    for t in dfPosition.columns:
        for simu_date in  simu_dates:
            temp_pnl = dfTraderSimulation.loc[:,(simu_date, 'PnL', t, product_types)].sum(axis=1)
            dfWorstPnL.loc[simu_date, t] = temp_pnl.min(),  temp_pnl.idxmin()-1
            
            
    
#%%
    color1 = '#323E48'
    color_palette =['#28829B', 'dodgerblue','royalblue','#C9CBCB', '#748D9E', '#2E9AB2']
    
    temp_pos = dfPosition.abs().join(dfAsset['product_type']).groupby('product_type').sum()
    
    fig, axes = plt.subplots(len(dfPosition.columns), 3, 
                             gridspec_kw={'height_ratios':[3]*(len(dfPosition.columns)-1) + [4], 
                                          'width_ratios':[6, 6, 1]},
                             figsize=(13, 8.7), sharex=True)
    plt.tight_layout(w_pad=2.3, h_pad=0.1)
    
    axes[0,0].set_title('Simulated Delta',fontweight='bold')
    axes[0,1].set_title('Simulated PnL',fontweight='bold')
    axes[0,2].set_title('Greeks       ',fontweight='bold')
    for j in [0,1]:
        axes[-1, j].set_facecolor('gainsboro')

    
    for ax_i, t in enumerate(dfPosition.columns):        
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
        ax.annotate('Ibov:{:+7.1%}\nPnL:{:+8.2%}'.format(x_min-1, pnl_min), 
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
            ax.set_xticklabels(['{:2.1%}\n{:2,.0f}'.format(i-1, dfSimulation.loc[round(i,4), (dt, 'Price','IBOV')]) for i in ticks_loc])
            
       
    ##### ####
    axes[ax_i, 0].set_xlabel('Ibov change (%) and simulated level (BRL)',fontweight='bold')
    axes[ax_i, 1].set_xlabel('Ibov change (%) and simulated level (BRL)',fontweight='bold')
    fig.align_ylabels()
    
    if print_pdf:
         fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_{1}_trader_IBOV_simulation.pdf'.format(dt, str_fund)
         fig.savefig(fig_file, bbox_inches = "tight")
    
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_trader_ibov_simulation.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    wb = xw.Book(report_filename)
    wb.sheets('Equity_3').pictures.add(wb.api.Path + '/' + fig_file, name='ibov_simulation', update=True)
    # wb.sheets('Equity_3').pictures.add(fig, name='x', update=True)
#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt, str_fund, print_pdf = fu.get_config(['dt', 'str_fund', 'print_pdf'])
    report_filename = '../xls/RiskMap_model.xlsm'
    nav = fu.get_NAV(dt, str_fund)
    main(dt, str_fund, nav, report_filename, print_pdf) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))