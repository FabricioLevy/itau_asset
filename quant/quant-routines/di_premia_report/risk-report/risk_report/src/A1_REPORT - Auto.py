import datetime
import timeit
import xlwings as xw
import QuantLib as ql
import pathlib
import os

import fund_utils as fu
import fund_performance, fund_VaR_Vol, fund_VaR_breakdown, fund_Stress, \
        fund_FX, fund_Equity, fund_equity_breakdown, fund_Equity_GrossNet, \
        fund_PV01, fund_CpCambial, fund_Backtest, fund_Drawdown, fund_Ibov_simulation, \
        fund_PV01_byRisk, fund_BRL_FX_Opt

import trader_VaR_Stress, trader_VaR_Vol, trader_Drawdown, trader_analysis, \
        trader_exposure, trader_eqty_liquidity

import b3_concentration, b3_eqty_turnover, fund_rolagem

#%%
def main(dt, str_fund, nav, report_filename='../xls/RiskMap_model.xlsm'):
    
    wb = xw.Book(report_filename)
    wb.sheets('Cover').range('NAV').value = nav
    wb.sheets('Cover').range('DataRef').value = dt
    wb.sheets('Cover').range('DataD1').value = ql.Brazil().advance(ql.Date.from_date(dt), ql.Period('-1d')).to_date()
    wb.sheets('Cover').range('fund').value = str_fund
    
    str_path = "../output/files/{:%Y%m%d}/".format(dt)
    pathlib.Path(str_path).mkdir(exist_ok=True)
    pathlib.Path(str_path + 'pics/').mkdir(exist_ok=True)
    
    fund_performance.main(dt, str_fund, report_filename)
    fund_VaR_Vol.main(dt, str_fund, report_filename)
    fund_VaR_breakdown.main(dt, str_fund, report_filename)
    fund_Stress.main(dt, str_fund, report_filename)
    fund_FX.main(dt, str_fund, nav, report_filename)
    fund_CpCambial.main(dt, str_fund, nav, report_filename)
    fund_Equity.main(dt, str_fund, nav, report_filename)
    fund_equity_breakdown.main(dt, str_fund, nav, report_filename)
    fund_Ibov_simulation.main(dt, str_fund, nav, report_filename)
    fund_Equity_GrossNet.main(dt, str_fund, nav, report_filename)
    fund_PV01.main(dt, str_fund, nav, report_filename)
    fund_PV01_byRisk.main(dt, str_fund, nav, report_filename)
    fund_BRL_FX_Opt.main(dt, str_fund, nav, report_filename)
    fund_Backtest.main(dt, str_fund, report_filename)
    fund_Drawdown.main(dt, str_fund, report_filename)
    
    trader_eqty_liquidity.main(dt, str_fund, nav, report_filename)
    trader_VaR_Vol.main(dt, str_fund, report_filename)
    trader_VaR_Stress.main(dt, str_fund, report_filename)
    trader_Drawdown.main(dt, str_fund, report_filename)
    trader_analysis.main(dt, str_fund, report_filename)
    trader_exposure.main(dt, str_fund, report_filename)
    
    b3_concentration.main(dt, str_fund, report_filename)
    b3_eqty_turnover.main(dt, str_fund, nav, report_filename)
    fund_rolagem.main(dt, str_fund, report_filename)
    
    str_temp_figs = '../output/temp_figs'
    for pic in os.listdir(str_temp_figs):
        if pic[0:8] == "{:%Y%m%d}".format(dt):
            os.replace(str_temp_figs + '/' + pic, str_path + 'pics/' + pic)
        elif pic.split('.')[-1] == 'svg':
            os.remove(str_temp_figs + '/' + pic)
    
    str_newfile = str_path + "{:%Y%m%d}_{}_RiskMap.xlsm".format(dt, str_fund)
    wb.save(path=str_newfile)
    # wb.close()
    return True
    
    
#%%    
if __name__ == "__main__":
    
# =============================================================================
#     tic = timeit.default_timer()
#     dt = datetime.date(2021, 9, 17)
#     # dt = ql.Brazil().advance(ql.Date.from_date(datetime.datetime.today()),ql.Period('-0d')).to_date()
#     str_fund = 'A1 Master FIM'
#     # str_fund = 'A1 Orange FIM'
#     # str_fund = 'A1 FIFE BEM'
#     report_filename = '../xls/RiskMap_model.xlsm'
#     
#     try:
#         nav = fu.get_NAV(dt, str_fund)
#     except Exception as err:
#         print(u"\u2620 \u2620 \u2620")
#         print("ERROR: {}".format(err))
#         print(u"\u2620 \u2620 \u2620")
# 
#     main(dt, str_fund, nav) 
#  
#     tac = timeit.default_timer()
#     print("Execution time: {:3.1f}s".format(tac - tic))  
#     
#     # import QuantLib as ql
#     # dtIni = ql.Date(31,10,2020)
#     # dtIni = ql.Brazil().adjust(dtIni)
#     # while dtIni >= ql.Date(1, 10, 2020):   
#     #     nav = fu.get_NAV(dtIni.to_date(), str_fund)
#     #     main(dtIni.to_date(), str_fund, nav)
#     #     dtIni = ql.Brazil().advance(dtIni, ql.Period(-1, ql.Days))
# =============================================================================
    
    #%%
    tic = timeit.default_timer()
    
    # dt = datetime.date(2021, 8, 31)
    dt = ql.Brazil().advance(ql.Date.todaysDate(),ql.Period('-0d')).to_date()
    
    report_filename = '../xls/RiskMap_model.xlsm'
    
    str_fund = 'A1 FIFE BEM'
    try:
        nav = fu.get_NAV(dt, str_fund)
    except Exception as err:
        print(u"\u2620 \u2620 \u2620")
        print("ERROR: {}".format(err))
        print(u"\u2620 \u2620 \u2620")
    main(dt, str_fund, nav)
    
    str_fund = 'A1 Orange FIM'
    try:
        nav = fu.get_NAV(dt, str_fund)
    except Exception as err:
        print(u"\u2620 \u2620 \u2620")
        print("ERROR: {}".format(err))
        print(u"\u2620 \u2620 \u2620")
    main(dt, str_fund, nav)
    
    str_fund = 'A1 Master FIM'
    try:
        nav = fu.get_NAV(dt, str_fund)
    except Exception as err:
        print(u"\u2620 \u2620 \u2620")
        print("ERROR: {}".format(err))
        print(u"\u2620 \u2620 \u2620")
    main(dt, str_fund, nav)
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))