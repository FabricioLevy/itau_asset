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

sys.path.insert(1, os.path.expanduser('~\\Documents\\Github\\market_data'))
import curve_db 

#%%
class EquityFuture(ql.Instrument):
    def __init__(self, quote, dtExpiry, lotSize=1, ccy='USD', openPrice = 0):
        self._bond = ql.ZeroCouponBond(0, 
                                       ql.UnitedStates(), 
                                       1000.0, 
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
            return self._stock.NPV() * (self._bond.notional()/self._bond.NPV()) \
                        - self._openPrice
    
    def delta(self):
        return 1 * self._lotSize
    
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
    def __init__(self, quote, lotSize=1, ccy='USD'):
        self._lotSize = lotSize
        self._ccy = ccy
        return super().__init__(quote)
      
    def delta(self):
        return 1 * self._lotSize
    
    def lotSize(self):
        return self._lotSize
    
    def ccy(self):
        return self._ccy

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


#%%
def main(dt, str_fund, nav_on, nav_off, book=''): 
    #%%
    
    str_benchmark = 'SPX'
    
    _, connection = fu.get_DB_conn('prod')
    
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
    
    dfBeta = pd.DataFrame((dfCovarDB[str_benchmark] + dfCovarDB.loc[str_benchmark]) / dfCovarDB.loc[str_benchmark, str_benchmark])
    
    for index_lote45, index_sql in dic_index_lote45.items():
        if index_lote45 in dfBeta.index:
            dfBeta.loc[index_sql, str_benchmark] = dfBeta.loc[index_lote45, str_benchmark]
    
    dfBeta.loc[str_benchmark]=1 
    dic_beta = dfBeta[str_benchmark].to_dict()
    
    str_book = "" if book == "" else f" AND book='{book}' " 
    
    str_sql = """
    SELECT id,[book],sum([amount])  as amount
    FROM [lote45].[position] pos INNER JOIN middle.product prod
      ON pos.lote45_product = prod.lote45_product
    WHERE  pos.date_reference = '{:%Y-%m-%d}' 
           and pos.trading_desk = '{}' 
           and prod.product_type in ('Equity Option','Equity Future', 'Equity')
           {}
      GROUP BY id, book
    """
    str_sql = str_sql.format(dt, str_fund, str_book)
    dfPosition = pd.read_sql(str_sql, connection).pivot(index='id', columns='book', values='amount').fillna(0)
    dfPosition['TOTAL'] = dfPosition.sum(axis=1)
    dic_position = dfPosition['TOTAL'].to_dict()
            
    str_sql = """
           SELECT [id] as product_id,[product_type],[lote45_product],[lote45_product_class]
          ,[product_currency],[product_underlying],[date_maturity]
          ,[option_type],[option_style],[option_strike], lot_size
      FROM [middle].[product]
      WHERE [id] in ('{}')
            """
    str_sql = str_sql.format("','".join(dic_position.keys()))
    dfAsset = pd.read_sql(str_sql, connection)
    
    ids = "','".join(set(dfAsset[['product_id','product_underlying']].fillna('').values.flatten()))
    
    ids_ccy = "','".join([i+'BRL' for i in dfAsset['product_currency'].unique()])
    
    str_sql = """
                SELECT [product_id],[price] FROM [middle].[product_price]
                WHERE product_id in ('{}','{}') and date_reference = '{:%Y-%m-%d}'
      """
    str_sql = str_sql.format(ids, ids_ccy, dt)
    dfPrice = pd.read_sql(str_sql, connection, index_col='product_id')
    dic_price = dfPrice['price'].to_dict()
    
    nav_off *= dic_price['USDBRL']
    
    dfAsset = dfAsset.join(dfPosition['TOTAL'], on='product_id').join(dfPrice, on='product_id')
    dfAsset = dfAsset[~dfAsset['TOTAL'].isna()]
    dfAsset.loc[dfAsset['product_type']=='Equity', 'product_underlying'] = dfAsset['product_id']
    dfAsset.set_index('product_id', inplace=True)
    
    del str_sql, ids, df, dfPrice, dfBeta, dfCovarDB

    #%%
    today = ql.Date.from_date(dt)
    ql.Settings.instance().evaluationDate = today   
    
    curve_name = 'ED Fut'
    risk_free = curve_db.get_curve(today.to_date(), curve_name)
    risk_free_handle = ql.YieldTermStructureHandle(risk_free)
    
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
        flat_vol_ts = ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, 
                                                                         ql.UnitedStates(), 
                                                                         ql.QuoteHandle(dic_Vol[opt_id]), 
                                                                         ql.Actual365Fixed()))
        bsm_process = ql.BlackScholesProcess(ql.QuoteHandle(dic_Underlying[underlying_id]), 
                                             risk_free_handle,
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
        future.setPricingEngine(ql.DiscountingBondEngine(risk_free_handle))
        dic_Asset[product_id] = future
    # del product_id, underlying_id, dt_exp
#%%
    cols = ['lot_size', 'product_currency']
    for product_id, row in dfAsset[dfAsset['product_type']=='Equity'].iterrows():
        (lot_size, ccy) = row[cols]
        eqty = Equity(ql.QuoteHandle(dic_Underlying[product_id]),
                      lot_size, 
                      ccy)
        dic_Asset[product_id] = eqty
    # del product_id
#%%
    benchmark = dic_Underlying[str_benchmark]
    benchmark_0 = benchmark.value()
    
    rng = (0.85, 1.1501)
    xs = np.round(np.arange(rng[0], rng[1], 0.001), 4)
    # key_value_aux = 50*int(benchmark_0/50)
    # key_values = [np.round(i/benchmark_0, 4) for i in [key_value_aux-50*i for i in [2,1,0]]]
    # xs = sorted(np.append(xs,key_values))
    key_values = []
    
    dic_simu = {}
    
    dic_simu['Price'] = pd.DataFrame(columns=[str_benchmark] + list(dic_Asset.keys()))
    dic_simu['PnL'] = pd.DataFrame(columns=dic_Asset.keys())
    dic_simu['Delta'] = pd.DataFrame(columns=dic_Asset.keys())
    
    
    for x in xs:
        benchmark.setValue(x * benchmark_0)
        for underlying_id in [x for x in dic_Underlying.keys() if x not in [str_benchmark]]:
            dic_Underlying[underlying_id].setValue(dic_price[underlying_id]*(1+((x-1)*dic_beta.get(underlying_id, 1))))
        dic_simu['Price'].loc[x, str_benchmark] = benchmark.value()
        for asset_id, asset in dic_Asset.items():
            lot_size = asset.lotSize() 
            ccy_rate = dic_price[asset.ccy() + 'BRL']
            dic_simu['Price'].loc[x, asset_id] = asset.NPV()  
            dic_simu['PnL'].loc[x, asset_id] = (asset.NPV() - dic_price[asset_id]) * lot_size * dic_position[asset_id] * ccy_rate
            dic_simu['Delta'].loc[x, asset_id] = asset.delta() * dic_Underlying[dfAsset.loc[asset_id, 'product_underlying']].value() * dic_position[asset_id] * ccy_rate
           
    benchmark.setValue(benchmark_0)
    for underlying_id in dic_Underlying.keys():
        dic_Underlying[underlying_id].setValue(dic_price[underlying_id])
        
#%%
    product_types = list(dfAsset['product_type'].unique())
    for simu_key in ['PnL', 'Delta']:
        for prod_type in product_types:
            ids = dfAsset[dfAsset['product_type']==prod_type].index
            dic_simu[simu_key][prod_type] = dic_simu[simu_key][ids].sum(axis=1)
        dic_simu[simu_key]['Total'] = dic_simu[simu_key][dfAsset.index].sum(axis=1)
    del prod_type
#%%
    dfOutput = pd.DataFrame(index=dic_simu['Delta'].index, 
                            columns=[str_benchmark] + product_types + ['Total'])
    dfOutput[str_benchmark] = dic_simu['Price'][str_benchmark]
    dfOutput[product_types+ ['Total']] = dic_simu['Delta'][product_types+ ['Total']]
    dfOutput['PnL Total'] = dic_simu['PnL']['Total']
    dfOutput.to_excel('../output/temp_figs/{:%Y%m%d}_{}_snp_simulation.xlsx'.format(dt, str_fund))
    

   
#%%
    color1 = '#323E48'
    color_palette =['#28829B', 'dodgerblue','royalblue','#C9CBCB', '#748D9E', '#2E9AB2']
    
    for nav, str_nav in zip([nav_on, nav_off], ['on', 'off']):
        fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.75))
        plt.tight_layout(w_pad=2.7)
        
        ##### PNL ####
        ax=axes[0]
        (dic_simu['PnL'][product_types]/nav).plot(ax=ax, ls='-', lw=2, color=color_palette)
        (dic_simu['PnL']['Total']/nav).plot(ax=ax, ls='--', lw=3.5, color='k', label='Total')
        texts = []
        y_min, y_max = ax.get_ylim()
        # for i, x in enumerate(key_values):
        #     val = dic_simu['PnL'].loc[x,'Total']
        #     ibov_val = dic_simu['Price'].loc[x, 'IBOV']
        #     if (val - y_min)/(y_max - y_min) > 0.5:
        #         shift_y = -50
        #     else:
        #         shift_y = 40
        #     # ax.text(x, val, '{:2.2%}'.format(val))
            
        #     texts.append(ax.annotate('{:2.0f}k\n{:4.2%}'.format(ibov_val/1000, val), 
        #                              xy=(x, val), xycoords='data', zorder=3,
        #                           xytext=(0, shift_y), textcoords='offset points', fontweight='bold',
        #                           fontsize=11, color=color1, ha='center',
        #                           bbox=dict(boxstyle="round", fc='silver' if val>0 else 'tomato', ec="0.5", alpha=0.8),
        #             arrowprops=dict(facecolor='r', arrowstyle="->", connectionstyle="arc3")))
        
        # adjust_text(texts, ax=ax)
        ax.set_title('Simulated PnL ' + book,fontweight='bold')
        ax.set_ylabel('PnL (%NAV)',fontweight='bold')
        ticks_loc = ax.get_yticks().tolist()
        ax.yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
        ax.set_yticklabels(['{:2.2%}'.format(i) for i in ticks_loc])
        ax.axhline(0, color='k', lw=0.75, ls='--')
        
        ##### DELTA ####
        ax=axes[1]
        for i, col in enumerate(product_types):
            (dic_simu['Delta'][col]/nav).plot(ax=ax, ls='-', lw=2, color=color_palette[i],
                                              label='{} ({:2.1%})'.format(col.split(' ')[-1], dic_simu['Delta'].loc[1,col]/nav))
        (dic_simu['Delta']['Total']/nav).plot(ax=ax, ls='--', lw=3.5, color='k', label='Total ({:2.1%})'.format(dic_simu['Delta'].loc[1,'Total']/nav))
        texts = []
        y_min, y_max = ax.get_ylim()
        # for i, x in enumerate(key_values):
        #     val = dic_simu['Delta'].loc[x,'Total']
        #     ibov_val = dic_simu['Price'].loc[x, 'IBOV']
        #     if (val - y_min)/(y_max - y_min) > 0.5:
        #         shift_y = -50
        #     else:
        #         shift_y = 40
        #     # ax.text(x, val, '{:2.2%}'.format(val))
            
        #     texts.append(ax.annotate('{:2.0f}k\n{:2.1%}'.format(ibov_val/1000, val), 
        #                              xy=(x, val), xycoords='data', zorder=3,
        #                           xytext=(0, shift_y), textcoords='offset points', fontweight='bold',
        #                           fontsize=11, color=color1, ha='center',
        #                           bbox=dict(boxstyle="round", fc='silver' if val>0 else 'tomato', ec="0.5", alpha=0.8),
        #             arrowprops=dict(facecolor='r', arrowstyle="->", connectionstyle="arc3")))
        
        # adjust_text(texts, ax=ax)
        ax.set_title('Simulated Delta '+book,fontweight='bold')
        ax.set_ylabel('Equity Delta (%NAV)',fontweight='bold')
        ticks_loc = ax.get_yticks().tolist()
        ax.yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
        ax.set_yticklabels(['{:2.1%}'.format(i) for i in ticks_loc])
        
        ##### ####
        for ax in axes:
            ax.legend(fontsize=9.5)
            ax.set_xlabel(f"{str_benchmark} change (%) and simulated level (USD)",fontweight='bold')
            ax.axvline(1, color='k', lw=0.75, ls='--')
            ax.grid(ls='--')
            ax.set_xlim(left=dic_simu['PnL'].index[0], right=dic_simu['PnL'].index[-1])
            ticks_loc = ax.get_xticks().tolist()
            ax.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
            ax.set_xticklabels(['{:2.1%}\n{:2,.0f}'.format(i-1, benchmark_0*i) for i in ax.get_xticks()])
        ##### ####
        
        fig_file = '../output/temp_figs/{:%Y%m%d}_{}_{}_snp_simulation.svg'.format(dt, str_fund, str_nav)
        # fig.savefig(fig_file, bbox_inches = "tight")
        plt.show()
        # wb = xw.Book(report_filename)
        # wb.sheets('Equity_2').pictures.add(wb.api.Path + '/' + fig_file, name='snp_simulation', update=True)
        # wb.sheets('Equity_2').pictures.add(fig, name='ibov_simulation', update=True)
        
        
        
#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt, str_fund_offshore = fu.get_config(['dt', 'str_fund_offshore'])

    str_sql = f"""
                SELECT n.[date_reference],n.[trading_desk],[offshore_vehicle],
                    [position_offshore_brl],n.NAV
                FROM [intrag].[fund_offshore_position] fo INNER JOIN middle.NAV n
                    ON fo.date_reference = n.date_reference 
                      AND fo.trading_desk = n.trading_desk
                WHERE fo. offshore_vehicle = '{str_fund_offshore}'
                     AND fo.date_reference <= '{dt:%Y-%m-%d}'
         """
    _, connection = fu.get_DB_conn('prod')
    df = pd.read_sql(str_sql, connection)
          
    nav_on = df.pivot(index='date_reference',
                       columns='trading_desk',
                       values='NAV').iloc[-1].sum()
    
    nav_off = fu.get_NAV(dt, str_fund_offshore)
    
    main(dt, str_fund_offshore, nav_on, nav_off, 'MS SnP PC') 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))