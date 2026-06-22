# -*- coding: utf-8 -*-
"""
Created on Mon Nov 28 09:45:35 2022

@author: matheus.amaral
"""

import pandas as pd
import numpy as np
import QuantLib as ql
import matplotlib.pyplot as  plt
import matplotlib.ticker as mticker
import os,sys
from datetime import date
from a1db.a1sql import SQLConnection

path_git = os.path.expanduser('~\Documents\GitHub')
sys.path.insert(1,path_git + '\\risk_report\\src')
import fund_utils as fu

sys.path.insert(1, path_git + '\\market_data')
import curve_db

#%%
class EquityFuture(ql.Instrument):
    def __init__(self, underlying_quote, lot_size, ccy_rate, dt_maturity, calendar, *args):
        self._bond = ql.ZeroCouponBond(0,
                                       calendar,
                                       1_000.0,
                                       ql.Date.from_date(dt_maturity),
                                       ql.Following,
                                       100.0,
                                       ql.Date(1,1,2000))
        self._stock = ql.Stock(ql.QuoteHandle(underlying_quote))
        self._lotSize = lot_size
        self._ccyRate = ccy_rate
        
    def setPricingEngine(self, curve):
        curve_handle = ql.YieldTermStructureHandle(curve)
        return self._bond.setPricingEngine(ql.DiscountingBondEngine(curve_handle))
    
    def NPV(self):
        if self._bond.NPV() == 0:
            return 0
        else:
            return self._stock.NPV() * (self._bond.notional() / self._bond.NPV())
        
    def delta(self):
        return self._stock.NPV() * self._lotSize * self._ccyRate
    
    def gamma(self):
        return 0
    
    def vega(self):
        return 0
    
    def theta(self):
        return 0
    
#%%
class EquityOption(ql.VanillaOption):
    def __init__(self, underlying_quote, lot_size, ccy_rate, dt_maturity, calendar, counter, option_type, option_strike, *args):
        self._calendar = calendar
        self._counter = counter
        self._lotSize = lot_size
        self._ccyRate = ccy_rate
        self._undQuote = ql.QuoteHandle(underlying_quote)
        
        payoff = ql.PlainVanillaPayoff(ql.Option.Call if option_type == 'C' else ql.Option.Put, option_strike)
        exercise = ql.EuropeanExercise(ql.Date.from_date(dt_maturity))
        
        super().__init__(payoff, exercise)
        
    def setPricingEngine(self, curve, vol = None, opt_price = None):
        curve_handle = ql.YieldTermStructureHandle(curve)
        
        if vol is None:
            if opt_price is None:
                raise Exception("There must be defined either the vol or the price")
            else:
                vol = ql.SimpleQuote(1.0)
                
                flat_vol = ql.BlackVolTermStructureHandle(ql.BlackConstantVol(0,
                                                                              self._calendar,
                                                                              ql.QuoteHandle(vol),
                                                                              self._counter))
                bsm_process = ql.BlackScholesProcess(self._undQuote, curve_handle, flat_vol)
                
                vol.setValue(super().impliedVolatility(opt_price, bsm_process))
                
                engine = ql.AnalyticEuropeanEngine(bsm_process)
        else:
            flat_vol = ql.BlackVolTermStructureHandle(ql.BlackConstantVol(0,
                                                                          self._calendar,
                                                                          ql.QuoteHandle(vol),
                                                                          self._counter))
            bsm_process = ql.BlackScholesProcess(self._undQuote, curve_handle, flat_vol)
            
            engine = ql.AnalyticEuropeanEngine(bsm_process)
            
        return super().setPricingEngine(engine)    
    
    
    def delta(self):
        return super().delta() * self._undQuote.value() * self._lotSize * self._ccyRate
    
    def gamma(self):
        return super().gamma() * (self._undQuote.value() ** 2) * self._lotSize * self._ccyRate / 100
    
    def vega(self):
        return super().vega() * self._lotSize * self._ccyRate
    
    def theta(self):
        return super().thetaPerDay() * self._lotSize * self._ccyRate
    
    def premium(self):
        return super().NPV() * self._lotSize * self._ccyRate

#%%
class Equity(ql.Stock):
    def __init__(self, underlying_quote, lot_size, ccy_rate, *args):
        self._lotSize = lot_size
        self._ccyRate = ccy_rate
        super().__init__(ql.QuoteHandle(underlying_quote))
        
    def delta(self):
        return super().NPV() * self._lotSize * self._ccyRate
    
    def gamma(self):
        return 0
    
    def vega(self):
        return 0
    
    def theta(self):
        return 0

    
#%%
class EquityPortfolio:
    _dictType = {'onshore':1,
                 'offshore':0}
    
    _dictBenchmark = {'onshore':'IBOV',
                      'offshore':'SPX'}
    
    _dictCalendar = {'onshore':ql.Brazil(),
                     'offshore':ql.UnitedStates()}
    
    _dictCounter = {'onshore':ql.Business252(),
                    'offshore':ql.Actual365Fixed()}
    
    _dictInstruments = {'Equity':Equity,
                        'Equity Future':EquityFuture,
                        'Equity Option':EquityOption}
    
    def __init__(self, dt, str_fund, portfolio_type):
        self._dt = dt
        self._fund = str_fund
        self._type = self._dictType[portfolio_type]
        self._benchmark = self._dictBenchmark[portfolio_type]
        self._calendar = self._dictCalendar[portfolio_type]
        self._counter = self._dictCounter[portfolio_type]
        
        self._connection = SQLConnection().get_connection()
        self._dictRiskShare = fu.get_DailyRiskShare(dt, str_fund).loc[dt].to_dict()
        self._NAV = fu.get_NAV(dt, str_fund)
        
        self.__loadPosition()
        self.__loadAssets()
        self.__loadPrices()
        self.__loadBeta()
        self.__setInstruments()
        
    def __loadPosition(self):
        data = 'Traders'
        
        str_sql = f"""
                SELECT p.id AS product_id,
                    b.book,
                    SUM(b.value) AS amount
                FROM lote45.book_overview b
                INNER JOIN middle.product p
                    ON p.lote45_product = b.lote45_product
                WHERE b.date_reference = '{self._dt:%Y-%m-%d}'
                    AND b.trading_desk = '{self._fund}'
                    AND b.measure = 'Amount'
                    AND p.product_type IN ('Equity', 'Equity Future', 'Equity Option')
                    AND p.lote45_product_class != 'Equity Subscription'
                    AND ((p.date_maturity > '{self._dt:%Y-%m-%d}') OR (p.date_maturity IS NULL))
                    AND p.onshore_risk = {self._type}
                GROUP BY p.id, b.book
                """
        dfTemp = pd.read_sql(str_sql, self._connection)
        
        str_sql = f"""
                SELECT *
                FROM lote45.book_tree
                WHERE parent_tree = '{data}'
                """
        dict_books = (fu.Node(data,
                              pd.read_sql(str_sql, self._connection))
                      .to_inv_dict(data))
        
        dfTemp[data] = dfTemp['book'].apply(lambda x: dict_books[x])
        
        self.dfPosition = (dfTemp.pivot_table(index = 'product_id',
                                             columns = data,
                                             values = 'amount',
                                             aggfunc = np.sum)
                           .fillna(0))
        
        str_sql = """
                SELECT trader_id,
                    ordering
                FROM risk.trader
                WHERE ordering IS NOT NULL
                """
        dictOrder = pd.read_sql(str_sql, self._connection, index_col = 'trader_id')['ordering'].to_dict()
        
        self.dfPosition = self.dfPosition[sorted(self.dfPosition.columns, 
                                                 key = lambda x: dictOrder[x], reverse = True)]
        
        self.dfPosition['Fund'] = self.dfPosition.sum(axis = 1)
        
    
    def __loadAssets(self):
        ids = "','".join(self.dfPosition.index)
        
        str_sql = f"""
                SELECT id AS product_id,
                    product_type,
                    product_currency,
                    product_underlying,
                    date_maturity,
                    lot_size,
                    option_type,
                    option_strike
                FROM middle.product
                WHERE id IN ('{ids}')
                """
        self.dfAssets = pd.read_sql(str_sql, self._connection, index_col = 'product_id')
        
        self.dfPositionByType = (self.dfPosition.join(self.dfAssets['product_type'])
                                 .groupby('product_type').sum())
        
        
    def __loadPrices(self):
        assets = set(self.dfAssets.reset_index()[['product_id', 'product_underlying']].values.flatten().tolist() 
                     + [self._benchmark])
        ids = "','".join(assets)
        
        str_sql = f"""
                SELECT product_id,
                    price
                FROM middle.product_price
                WHERE date_reference = '{self._dt:%Y-%m-%d}'
                    AND product_id in ('{ids}')
                """
        dfTemp = pd.read_sql(str_sql, self._connection, index_col = 'product_id')
        
        if not assets.issubset(set(dfTemp.index)):
            raise Exception("The following products don't have price in the middle.product_price table:"
                            + "\n".join([f"{i}" for i in assets - set(dfTemp.index)]))
        else:
            self.dictPrices = dfTemp['price'].to_dict()
            
        str_sql = f"""
                SELECT price
                FROM middle.product_price
                WHERE date_reference = '{self._dt:%Y-%m-%d}'
                    AND product_id = 'USDBRL'
                """
        ccy_rate = self._connection.execute(str_sql).fetchone()[0]
        
        self.dfAssets['ccy_rate'] = np.where(self.dfAssets['product_currency'] == 'USD',
                                             ccy_rate, 1)
    
    
    def __loadBeta(self):
        dictConv = {'SPX':'SPX',
                    'IBOV':'IBVSP'}
        
        benchm = dictConv[self._benchmark]
        
        str_sql = f"""
                SELECT primitive1,
                    primitive2,
                    covar_value
                FROM lote45.covar_matrix
                WHERE date_reference = '{self._dt:%Y-%m-%d}'
                ORDER BY 1,2
                """
        dfDB = (pd.read_sql(str_sql, self._connection)
                .pivot(index = 'primitive1',
                       columns = 'primitive2',
                       values = 'covar_value')
                .fillna(0))
        
        dfCovar = pd.DataFrame(data = np.triu(dfDB.values) + np.tril(dfDB.T.values, -1),
                               columns = dfDB.index, index = dfDB.index)
        
        try:
            self.dictBeta = (dfCovar.loc[benchm] / dfCovar.loc[benchm, benchm]).to_dict()
            
        except Exception:
            print("There's no covar value for the benchmark in the covar_matrix, the value will be 1")
            self.dictBeta = {prod_id: 1 for prod_id in dfCovar.index}
        
    
    def __setInstruments(self):
        self.dictProducts = {}
        
        self.benchmarkValue = ql.SimpleQuote(self.dictPrices[self._benchmark])
        
        spread = ql.DerivedQuote(ql.QuoteHandle(self.benchmarkValue),
                                 lambda x: (x - self.dictPrices[self._benchmark]) / self.dictPrices[self._benchmark])
        
        dictUnderlying = {und_id: ql.CompositeQuote(
            ql.QuoteHandle(ql.SimpleQuote(self.dictPrices[und_id])),
            ql.QuoteHandle(ql.CompositeQuote(
                ql.QuoteHandle(spread),
                ql.QuoteHandle(ql.SimpleQuote(self.dictBeta.get(und_id,1))),
                lambda x,y: 1 + x*y)),
            lambda x,y: x*y) if und_id != self._benchmark
            else self.benchmarkValue for und_id in self.dfAssets['product_underlying'].unique()}
        
        cols = ['product_type', 'product_underlying', 'date_maturity', 'lot_size', 'option_type', 
                'option_strike', 'ccy_rate']
        
        for prod_id, row in self.dfAssets.iterrows():
            prod_tp, prod_und, dt_mt, lot_size, opt_type, opt_strike, ccy_rate = row[cols]
            
            self.dictProducts[prod_id] = self._dictInstruments[prod_tp](dictUnderlying[prod_und],
                                                                        lot_size, ccy_rate,dt_mt,
                                                                        self._calendar, self._counter,
                                                                        opt_type, opt_strike)
        

    def setPricingEngine(self, curve):
        for fut in self.dfAssets.query("product_type == 'Equity Future'").index:
            self.dictProducts[fut].setPricingEngine(curve)
            
        for opt in self.dfAssets.query("product_type == 'Equity Option'").index:
            opt_price = self.dictPrices[opt]
            self.dictProducts[opt].setPricingEngine(curve, opt_price = opt_price)
            
            
    def resetBenchmarkValue(self):
        self.benchmarkValue.setValue(self.dictPrices[self._benchmark])
        
        
    def greeksByTraders(self):
        temp_dict = {}
        greeks = ['Delta', 'Gamma', 'Vega', 'Theta']
        
        temp_dict['Premium'] = [prod.premium() if isinstance(prod, ql.Option) else 0 for prod in self.dictProducts.values()]
        
        for greek in greeks:
            temp_dict[greek] = [getattr(prod,greek.lower())() for prod in self.dictProducts.values()]
            
        dfTemp = pd.DataFrame(data = temp_dict, index = self.dfAssets.index)
        
        dfGreeks = (dfTemp.T @ self.dfPosition) / self._NAV
        
        for col in dfGreeks.columns:
            dfGreeks[col] /= self._dictRiskShare[col]
        
        return dfGreeks
    
    
    def attributeByTrader(self, attribute, group_by_type = True):
        list_temp = []
        
        if attribute == 'PnL':
            list_temp = [(prod.NPV() - self.dictPrices[prod_id]) * prod._lotSize * prod._ccyRate for prod_id, prod in self.dictProducts.items()]
            
        else:
            list_temp = [getattr(prod, attribute.lower())() for prod in self.dictProducts.values()]
            
        dfTemp = pd.DataFrame(index = self.dfAssets.index)
        
        for col in self.dfPosition.columns:
            dfTemp[col] = self.dfPosition[col] * list_temp / self._dictRiskShare[col]
            
        dfTemp /= self._NAV
        
        if group_by_type:
            dfTemp = (dfTemp.join(self.dfAssets['product_type'])
                      .groupby('product_type').sum())
            
        dfTemp.loc['Total'] = dfTemp.sum()
            
        return dfTemp
#%%
def plot_simulation_greeks(dt, portfolio, simulation, greeks, benchmark_values):
    color1 = '#323E48'
    color_palette =['#28829B', 'dodgerblue','royalblue','#C9CBCB', '#748D9E', '#2E9AB2']
     
    dictBenchName = {'SPX':'SnP',
                  'IBOV':'IBOV'}
     
    dictCcy = {'SPX':'USD',
                'IBOV':'BRL'}
     
    fig, axes = plt.subplots(len(portfolio.dfPosition.columns), 3,
                              gridspec_kw = {'height_ratios':(len(portfolio.dfPosition.columns) - 1) * [3] + [4],
                                             'width_ratios':[6,6,1]},
                              figsize = (13,8.7), sharex = True)
    plt.tight_layout(w_pad = 2.3, h_pad = 0.1)

    axes[0,0].set_title('Simulated Delta', fontweight = 'bold')
    axes[0,1].set_title('Simulated PnL', fontweight = 'bold')
    axes[0,2].set_title('Greeks', fontweight = 'bold') 

    for j in [0,1]:
        axes[-1,j].set_xlabel(f"{dictBenchName[portfolio._benchmark]} change (%) and simulated level ({dictCcy[portfolio._benchmark]})",
                              fontweight = 'bold')
        axes[-1,j].set_facecolor('gainsboro')

    for ax_i, t in enumerate(portfolio.dfPosition.columns):
        for att_j, att in enumerate(['Delta', 'PnL']):
            ax = axes[ax_i, att_j]
            
            for prod_id, prod in enumerate(portfolio.dfAssets['product_type'].unique()):
                if portfolio.dfPositionByType.loc[prod, t] != 0:
                    ax.plot(simulation.index,
                            simulation.loc[:,(dt, att, t, prod)], 
                            ls = '-', lw = 2,
                            color = color_palette[prod_id],
                            label = f"{prod.split(' ')[-1]} ({simulation.loc[1, (dt, att, t, prod)]:+7.1%})")
                
            ax.plot(simulation.index,
                    simulation.loc[:, (dt, att, t, 'Total')],
                    ls = '--', lw = 3, color = 'k',
                    label = f"TOTAL ({simulation.loc[1, (dt, att, t, 'Total')]:+7.1%})")
            
            if att_j == 0:
                ax.legend(fontsize = 9)
                ax.set_ylabel(f"{t}\n{portfolio._dictRiskShare[t]:2.1%}", fontweight = 'bold', fontsize = 11)
            else:
                x_min = simulation.loc[:, (dt, att, t, 'Total')].idxmin()
                pnl_min = simulation.loc[x_min, (dt, att, t, 'Total')]
                
                ax.annotate(f"{dictBenchName[portfolio._benchmark]}:{x_min-1:+7.1%}\nPnL:{pnl_min:+7.2%}",
                            xycoords = 'data', xy = (x_min, pnl_min),
                            textcoords = 'axes fraction', xytext = (0.5,0.85),
                            va = 'center', ha = 'center', fontweight = 'bold',
                            bbox = dict(boxstyle = 'round', fc = 'tomato', alpha = 0.5),
                            arrowprops = dict(arrowstyle = '->', connectionstyle = 'arc3, rad = -0.2', lw = 1.5))
                
            ax.grid(ls = '--')
            ax.axhline(ls = '--', color = 'k', lw = 0.75)
            
            y_min, y_max = ax.get_ylim()
            ax.set_ylim(bottom = min(y_min, -0.001), top = max(y_max, 0.001))
            ax.set_xlim(right = simulation.index[-1], left = simulation.index[0])
            
            tick_loc = ax.get_yticks().tolist()
            ax.yaxis.set_major_locator(mticker.FixedLocator(tick_loc))
            ax.set_yticklabels([f"{i:2.1%}" for i in tick_loc])
            tick_loc = ax.get_xticks().tolist()
            ax.xaxis.set_major_locator(mticker.FixedLocator(tick_loc))
            ax.set_xticklabels([f"{i-1:2.1%}\n{benchmark_values[round(i, 4)]:2,.0f}" for i in tick_loc])
            
        ax = axes[ax_i, 2]
        ax.axis('off')
        ax.annotate("\n\n".join([f"{greek}={val:4.2%}" for greek, val in greeks[t].to_dict().items()]),
                    xycoords = 'data', xy = (1,1),
                    textcoords = 'axes fraction', xytext = (0.98,0.85),
                    va = 'top', ha = 'right', fontweight = 'bold', fontsize = 9,
                    bbox = dict(boxstyle = 'round', fc = 'blue', alpha = 0.2))
        
    fig.align_ylabels()
    plt.show()
    
    return fig
        
    
#%%
if __name__ == '__main__':
    dt = date(2022,10,10)
    str_fund = 'A1 Master FIM'
    portfolio_type = 'onshore'
    
    port = EquityPortfolio(dt, str_fund, portfolio_type)
    
    curve_name = 'ED Fut'
    curve = curve_db.get_curve(dt, curve_name)
    ql.Settings.instance().setEvaluationDate(ql.Date.from_date(dt))
    
    port.setPricingEngine(curve)
    
    dfGreeks = port.greeksByTraders()
    
    dictBench = {}
    simu_dates = [dt] + port.dfAssets['date_maturity'].dropna().unique().tolist()
    xs = np.round(np.arange(0.85, 1.1501, 0.001), 4)
    spx = port.benchmarkValue.value()
    dfSimulation = pd.DataFrame()
    
    for simu_dt in simu_dates:
        ql.Settings.instance().setEvaluationDate(ql.Date.from_date(simu_dt))
        for x in xs:
            port.benchmarkValue.setValue(spx * x)
            dictBench[x] = port.benchmarkValue.value()
            for att in ['Delta', 'PnL']:
                df = (port.attributeByTrader(att)
                      .melt(ignore_index = False, var_name = 'Traders')
                      .reset_index())
                df['simu_date'] = simu_dt
                df['xs'] = x
                df['att'] = att
                
                dfSimulation = pd.concat([dfSimulation, df])
                
    dfSimulation = dfSimulation.pivot(index = 'xs',
                                      columns = ['simu_date', 'att', 'Traders', 'product_type'],
                                      values = 'value')
    
    ql.Settings.instance().setEvaluationDate(ql.Date.from_date(dt))
    port.resetBenchmarkValue()
    
    fig = plot_simulation_greeks(port, dfSimulation, dfGreeks, dictBench)



 