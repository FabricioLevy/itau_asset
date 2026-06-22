# -*- coding: utf-8 -*-
"""
Created on Tue Nov 29 14:56:18 2022

@author: matheus.amaral
"""

import pandas as pd
import numpy as np
import EquityPortfolio as eq
import os, sys
path_curve = os.path.expanduser('~\Documents\GitHube\market_data')
sys.path.insert(1, path_curve)
import curve_db
import QuantLib as ql
from datetime import date
import xlwings as xw

def generateSimulation(dt, str_fund, portfolio_type, curve_name):
    report_filename = '../xls/RiskMap_model.xlsm'
    curve = curve_db.get_curve(dt, curve_name)
    ql.Settings.instance().setEvaluationDate(ql.Date.from_date(dt))
    
    port = eq.EquityPortfolio(dt, str_fund, portfolio_type)
    port.setPricingEngine(curve)
    
    dfGreeks = port.greeksByTraders()
    
    simu_dates = [dt] + port.dfAssets['date_maturity'].dropna().unique().tolist()
    xs = np.round(np.arange(0.85, 1.1501, 0.001), 4)
    benchmark = port.benchmarkValue.value()
    
    dfSimulation = pd.DataFrame()
    dictBench = {}
    
    for simu_dt in simu_dates:
        ql.Settings.instance().setEvaluationDate(ql.Date.from_date(simu_dt))
        for x  in xs:
            port.benchmarkValue.setValue(benchmark * x)
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
    
    fig = eq.plot_simulation_greeks(dt, port, dfSimulation, dfGreeks, dictBench)
    
    wb = xw.Book(report_filename)
    
    if portfolio_type == 'offshore':
        fig_file = '../output/temp_figs/{:%Y%m%d}_{}_trader_SnP_simulation.svg'.format(dt, str_fund)
        fig.savefig(fig_file, bbox_inches = "tight")
        wb.sheets('Equity_3').pictures.add(wb.api.Path + '/' + fig_file, name='snp_simulation', update=True)
        
    else:
        fig_file = '../output/temp_figs/{:%Y%m%d}_{}_trader_ibov_simulation.svg'.format(dt, str_fund)
        fig.savefig(fig_file, bbox_inches = "tight")
        wb.sheets('Equity_3').pictures.add(wb.api.Path + '/' + fig_file, name='ibov_simulation', update=True)
    
    
    
    
#%%
if __name__ == '__main__':
    dt = date(2022,10,10)
    str_fund = 'A1 Master FIM'
    portfolio_type = 'offshore'
    curve_name = 'ED Fut'
    
    generateSimulation(dt, str_fund, portfolio_type, curve_name)
