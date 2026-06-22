import pandas as pd
import numpy as np
import datetime
import timeit
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import QuantLib as ql
import xlwings as xw
import fund_utils as fu
import adjustText

import os
import sys

sys.path.insert(1, os.path.expanduser('~\\Documents\\Github\\market_data'))
import curve_db 

#%%
class EquityFuture(ql.Instrument):
    def __init__(self, quote, dtExpiry, lotSize=1, ccy='USD', openPrice = 0):
        self._bond = ql.ZeroCouponBond(0, 
                                       ql.UnitedStates(), 
                                       1_000.0, 
                                       dtExpiry, 
                                       ql.Following, 
                                       100.0, 
                                       ql.Date(1,1,2000))
        self._stock = ql.Stock(quote)
        self._lotSize = lotSize
        self._ccy = ccy
        self._openPrice = openPrice
        return None
    
    def NPV(self):
        if self._bond.NPV() == 0:
            return 0
        else:
            return self._stock.NPV() * (1_000/self._bond.NPV()) - self._openPrice
    
    def delta(self):
        return 1 * self._lotSize
    
    def gamma(self):
        return 0
    
    def vega(self):
        return 0
    
    def lotSize(self):
        return self._lotSize
    
    def ccy(self):
        return self._ccy
    
    def setPricingEngine(self, engine):
        return self._bond.setPricingEngine(engine)
    
    def maturityDate(self):
        return self._bond.maturityDate()
         
    def __str__(self):
        return "EquityFuture {:%d-%b-%y}".format(self._bond.maturityDate().to_date())
    
    def __repr__(self):
        return self.__str__()
    
#%%
class Equity(ql.Stock):
    def __init__(self, quote, desc, lotSize=1, ccy='USD'):
        self._desc = desc
        self._lotSize = lotSize
        self._ccy = ccy
        return super().__init__(quote)
      
    def delta(self):
        return 1 * self._lotSize
    
    def gamma(self):
        return 0
    
    def vega(self):
        return 0
    
    def lotSize(self):
        return self._lotSize
    
    def ccy(self):
        return self._ccy
    
    def __str__(self):
        return "Equity {}".format(self._desc)
    
    def __repr__(self):
        return self.__str__()

#%%
class EquityOption(ql.VanillaOption):
    def __init__(self, payoff, exercise, lotSize=1, ccy='USD'):
        self._lotSize = lotSize
        self._ccy = ccy
        return super().__init__(payoff, exercise)
      
    def delta(self):
        return super().delta() * self._lotSize
    
    def lotSize(self):
        return self._lotSize
    
    def ccy(self):
        return self._ccy
    
    def __str__(self):
        return "EquityOption {:%d-%b-%y}".format(self.exercise().lastDate().to_date())
    
    def __repr__(self):
        return self.__str__()


#%%
def main(dt, str_fund, nav, report_filename, print_pdf=False): 
    #%%
    
    str_benchmark = 'SPX'
    
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
    
    str_sql = """
                SELECT [id],[product_underlying]
                FROM [middle].[product]
                WHERE product_type = 'Equity Index'
                   and [onshore_risk] = 0
               """
    dic_index_lote45 = pd.read_sql(str_sql, connection, index_col='product_underlying')['id'].to_dict()
    
    if str_benchmark in dfCovarDB.columns:
        dfBeta = pd.DataFrame((dfCovarDB[str_benchmark] + dfCovarDB.loc[str_benchmark]) / dfCovarDB.loc[str_benchmark, str_benchmark])
    else:
        dfBeta = pd.DataFrame(1, index=dfCovarDB.index, columns=[str_benchmark])
    
    for index_lote45, index_sql in dic_index_lote45.items():
        if index_lote45 in dfBeta.index:
            dfBeta.loc[index_sql, str_benchmark] = dfBeta.loc[index_lote45, str_benchmark]
    
    dfBeta.loc[str_benchmark]=1 
    dic_beta = dfBeta[str_benchmark].to_dict()
    
    str_sql = """
    SELECT p.id as product_id, bo.book, sum(bo.value) as amount
      FROM [lote45].[book_overview] bo INNER JOIN middle.product p ON bo.lote45_product = p.lote45_product
      WHERE bo.date_reference = '{0:%Y-%m-%d}' and bo.trading_desk = '{1}' and bo.measure = 'Amount'
      and p.product_type in ('Equity Option','Equity Future', 'Equity')
      and ((p.date_maturity>'{0:%Y-%m-%d}') or p.date_maturity is null)
      and onshore_risk = 0
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
            
    str_sql = """
           SELECT [id] as product_id,[product_type],[lote45_product],[lote45_product_class]
          ,[product_currency],[product_underlying],[date_maturity]
          ,[option_type],[option_style],[option_strike], lot_size
      FROM [middle].[product]
      WHERE [id] in ('{}')
            """
    str_sql = str_sql.format("','".join(dfPosition.index))
    dfAsset = pd.read_sql(str_sql, connection)
    
    ids = "','".join(set(dfAsset[['product_id','product_underlying']].fillna('').values.flatten()))
    
    ids_ccy = "','".join([i+'BRL' for i in dfAsset['product_currency'].unique()])
    
    str_sql = f"""
                SELECT [product_id],[price] FROM [middle].[product_price]
                WHERE product_id in ('{ids}','{ids_ccy}', '{str_benchmark}') 
                   and date_reference = '{dt:%Y-%m-%d}'
      """
    dfPrice = pd.read_sql(str_sql, connection, index_col='product_id')
    dic_price = dfPrice['price'].to_dict()
    
    dfAsset = dfAsset.join(dfPosition['Fund'], on='product_id').join(dfPrice, on='product_id')
    dfAsset = dfAsset[~dfAsset['Fund'].isna()]
    dfAsset.loc[dfAsset['product_type']=='Equity', 'product_underlying'] = dfAsset['product_id']
    dfAsset.set_index('product_id', inplace=True)
    
    simu_dates = set(dfAsset['date_maturity'].dropna())
    
    # del str_sql, ids, df, dfPrice, dfBeta, dfCovarDB

    #%%
    today = ql.Date.from_date(dt)
    ql.Settings.instance().setEvaluationDate(today)
    ql.Settings.instance().includeReferenceDateEvents = True
    # ql.Settings.instance().includeReferenceDateCashFlows = True
    # ql.Settings.instance().includeTodaysCashFlows = True
    
    curve_name = 'ED Fut'
    risk_free = curve_db.get_curve(today.to_date(), curve_name)
    # risk_free_handle = ql.YieldTermStructureHandle(risk_free)
    
    # risk_free_handle = ql.YieldTermStructureHandle(ql.FlatForward(0, ql.TARGET(), 0, ql.Actual365Fixed()))
    
    
    dic_crv_handle = {}
    for simu_date in simu_dates:
        risk_free.zeroRateValue(simu_date)
        dic_crv_handle[simu_date] = ql.YieldTermStructureHandle(ql.FlatForward(0,
                                                                            ql.TARGET(), 
                                                                            risk_free.zeroRateValue(simu_date),
                                                                            ql.Actual365Fixed()))
    
    # Add Underlyings to dictionary
    dic_Underlying = {underlying_id: ql.SimpleQuote(dic_price[underlying_id])
                      for underlying_id in set(dfAsset['product_underlying'].dropna())}
    
    if str_benchmark not in dic_Underlying.keys():
        dic_Underlying[str_benchmark] = ql.SimpleQuote(dic_price[str_benchmark])

#%%
    dic_Asset = {}
    dic_Vol = {}
    
    cols = ['product_underlying', 'date_maturity', 'option_type', 'option_style', 
            'option_strike', 'lot_size', 'product_currency']
    for opt_id, row in dfAsset[dfAsset['product_type']=='Equity Option'].iterrows():
        (underlying_id, dt_exp, opt_type, opt_style, opt_strike, lot_size, ccy) = row[cols]
        ql_opt_type = ql.Option.Call if opt_type.upper() == 'C' else ql.Option.Put
        ql_dt_exp = ql.Date.from_date(dt_exp)
        
        exercise = ql.EuropeanExercise(ql_dt_exp) #if opt_style.upper() == 'E' else ql.AmericanExercise(calculation_date, ql_dt_exp)
        payoff = ql.PlainVanillaPayoff(ql_opt_type, opt_strike)
        option = EquityOption(payoff, exercise, lot_size, ccy)
           
        # volatility = ql.SimpleQuote(1.0)
        dic_Vol[opt_id] = ql.SimpleQuote(1.0)
        flat_vol_ts = ql.BlackVolTermStructureHandle(ql.BlackConstantVol(0, 
                                                                         ql.UnitedStates(), 
                                                                         ql.QuoteHandle(dic_Vol[opt_id]), 
                                                                         ql.Actual365Fixed()))
        bsm_process = ql.BlackScholesProcess(ql.QuoteHandle(dic_Underlying[underlying_id]), 
                                             # risk_free_handle,
                                             dic_crv_handle[dt_exp],
                                             flat_vol_ts)
        
        dic_Vol[opt_id].setValue(option.impliedVolatility(dic_price[opt_id], 
                                                          bsm_process))
            
        option.setPricingEngine(ql.AnalyticEuropeanEngine(bsm_process))
    
        dic_Asset[opt_id] = option
        
    # del opt_id, underlying_id, dt_exp, opt_type, opt_style, opt_strike, ql_opt_type, ql_dt_exp, exercise, option, cols
   
#%%
    cols = ['product_underlying', 'date_maturity', 'lot_size', 'product_currency']
    for product_id, row in dfAsset[dfAsset['product_type']=='Equity Future'].iterrows():
        (underlying_id, dt_exp, lot_size, ccy) = row[cols]
        future = EquityFuture(ql.QuoteHandle(dic_Underlying[underlying_id]), 
                              ql.Date.from_date(dt_exp), 
                              lot_size,
                              ccy)
        # future.setPricingEngine(ql.DiscountingBondEngine(risk_free_handle))
        future.setPricingEngine(ql.DiscountingBondEngine(dic_crv_handle[dt_exp]))
        dic_Asset[product_id] = future
    # del product_id, underlying_id, dt_exp
#%%
    cols = ['lot_size', 'product_currency']
    for product_id, row in dfAsset[dfAsset['product_type']=='Equity'].iterrows():
        (lot_size, ccy) = row[cols]
        eqty = Equity(ql.QuoteHandle(dic_Underlying[product_id]),
                      product_id,
                      lot_size, 
                      ccy)
        dic_Asset[product_id] = eqty
    # del product_id
#%%
    dfGreeks = pd.DataFrame(0,
                            columns=['Premium', 'Delta', 'Gamma', 'Vega', 'Theta'],
                            index=dfPosition.index)
    for asset_id, asset in dic_Asset.items():
        lot_size = asset.lotSize() 
        ccy_rate = dic_price[asset.ccy() + 'BRL']
        dfGreeks.loc[asset_id, 'Delta'] = asset.delta() * dic_Underlying[dfAsset.loc[asset_id, 'product_underlying']].value() * ccy_rate
        if isinstance(asset, ql.Option):
            dfGreeks.loc[asset_id, 'Premium'] = asset.NPV() * lot_size * ccy_rate
            dfGreeks.loc[asset_id, 'Gamma'] = asset.gamma() * lot_size * (dic_Underlying[dfAsset.loc[asset_id, 'product_underlying']].value()**2) * ccy_rate / 100
            dfGreeks.loc[asset_id, 'Vega'] = asset.vega() * lot_size * ccy_rate
            dfGreeks.loc[asset_id, 'Theta'] = asset.thetaPerDay() * lot_size * ccy_rate
        
    dfTraderGreeks = (dfGreeks.T @ dfPosition).copy() / nav
    for t in dfTraderGreeks.columns:
        dfTraderGreeks[t] /= dic_share[t]
    
#%%        
    benchmark = dic_Underlying[str_benchmark]
    benchmark_0 = benchmark.value()
    
    rng = (0.85, 1.1501)
    xs = np.round(np.arange(rng[0], rng[1], 0.001), 4)
    
    dfSimulation = pd.DataFrame(columns=pd.MultiIndex.from_product([[dt] + list(simu_dates),
                                                                    ['Price','PnL', 'Delta'], 
                                                                    [str_benchmark] + list(dic_Asset.keys())], 
                                                                   names=['simu_date','metric', 'asset']))
    for simu_date in [dt] + list(simu_dates):
        ql.Settings.instance().setEvaluationDate(ql.Date.from_date(simu_date))
        for x in xs:
            benchmark.setValue(x * benchmark_0)
            for underlying_id in [x for x in dic_Underlying.keys() if x not in [str_benchmark]]:
                dic_Underlying[underlying_id].setValue(dic_price[underlying_id]*(1+((x-1)*dic_beta.get(underlying_id, 1))))
            dfSimulation.loc[x, (simu_date, 'Price', str_benchmark)] = benchmark.value()
            for asset_id, asset in dic_Asset.items():
                lot_size = asset.lotSize() 
                ccy_rate = dic_price[asset.ccy() + 'BRL']
                dfSimulation.loc[x, (simu_date, 'Price', asset_id)] = asset.NPV()
                dfSimulation.loc[x, (simu_date, 'PnL', asset_id)] = (asset.NPV() - dic_price[asset_id]) * lot_size * ccy_rate
                
                dfSimulation.loc[x, (simu_date, 'Delta', asset_id)] = asset.delta() * dic_Underlying[dfAsset.loc[asset_id, 'product_underlying']].value() * ccy_rate
                
        benchmark.setValue(benchmark_0)
        for underlying_id in dic_Underlying.keys():
            dic_Underlying[underlying_id].setValue(dic_price[underlying_id])
    
    ql.Settings.instance().setEvaluationDate(today)
 #%%       
    product_types = list(dfAsset['product_type'].unique())
    dfTraderSimulation = pd.DataFrame(columns=pd.MultiIndex.from_product([[dt] + list(simu_dates),
                                                                          ['PnL', 'Delta'], 
                                                                          dfPosition.columns, 
                                                                          product_types],
                                                                         names=['simu_date', 'metric', 'trader', 'product']))

    for simu_date in [dt] + list(simu_dates):
        for simu_key in ['PnL', 'Delta']:
            for prod_type in product_types:
                for t in dfPosition.columns:
                    ids = dfAsset[dfAsset['product_type']==prod_type].index
                    dfTraderSimulation.loc[:, (simu_date, simu_key, t, prod_type)] = (dfSimulation.loc[:,(simu_date, simu_key, ids)] @ dfPosition.loc[ids, t].values) / dic_share[t]
  
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
        ax.annotate('SnP:{:+7.1%}\nPnL:{:+8.2%}'.format(x_min-1, pnl_min), 
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
            ax.set_xticklabels(['{:2.1%}\n{:2,.0f}'.format(i-1, dfSimulation.loc[round(i,4), (dt, 'Price',str_benchmark)]) for i in ticks_loc])
            
       
    ##### ####
    axes[ax_i, 0].set_xlabel('SnP change (%) and simulated level (USD)',fontweight='bold')
    axes[ax_i, 1].set_xlabel('SnP change (%) and simulated level (USD)',fontweight='bold')
    fig.align_ylabels()
   
    if print_pdf:
         fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_{1}_trader_SnP_simulation.pdf'.format(dt, str_fund)
         fig.savefig(fig_file, bbox_inches = "tight")
    
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_trader_SnP_simulation.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    wb = xw.Book(report_filename)
    wb.sheets('Equity_3').pictures.add(wb.api.Path + '/' + fig_file, name='snp_simulation', update=True)

    #%%
    return dfSimulation, dfPosition, dfTraderSimulation
                
#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt, str_fund, print_pdf = fu.get_config(['dt', 'str_fund', 'print_pdf'])
    nav = fu.get_NAV(dt, str_fund) 
    report_filename = '../xls/RiskMap_model.xlsm'
    
    main(dt, str_fund, nav, report_filename, print_pdf)
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))