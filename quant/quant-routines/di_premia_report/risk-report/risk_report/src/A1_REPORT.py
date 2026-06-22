import datetime
import timeit
import xlwings as xw
import QuantLib as ql
import pathlib
import os

import fund_utils as fu
import fund_performance, fund_VaR_Vol, fund_VaR_breakdown, fund_Stress, \
        fund_FX, fund_Equity, fund_equity_breakdown_on_off, fund_Equity_GrossNet, \
        fund_PV01, fund_CpCambial, fund_Backtest, fund_Drawdown, fund_PV01_byRisk, \
        fund_BRL_FX_Opt, fund_trade_ideas, fund_mock_trade_ideas, trader_ideas_email, fund_exposure,\
        trader_Ibov_simulation,trader_SnP_simulation, bond_turnover

import trader_VaR_Stress, trader_VaR_Vol, trader_Drawdown, trader_analysis, \
        trader_exposure, trader_eqty_liquidity

import b3_concentration, b3_eqty_turnover, fund_rolagem

#%%
def main(dt, str_fund, nav, report_filename='../xls/RiskMap_model.xlsm', print_pdf=False):
    
    wb = xw.Book(report_filename)
    wb.sheets('Cover').range('NAV').value = nav
    wb.sheets('Cover').range('DataRef').value = dt
    wb.sheets('Cover').range('DataD1').value = ql.Brazil().advance(ql.Date.from_date(dt), ql.Period('-1d')).to_date()
    wb.sheets('Cover').range('fund').value = str_fund
    
    str_path = "../output/files/{:%Y%m%d}/".format(dt)
    pathlib.Path(str_path).mkdir(exist_ok=True)
    pathlib.Path(str_path + 'pics/').mkdir(exist_ok=True)
    
    cal_B3 = ql.Brazil(ql.Brazil().Exchange)
    
    
    fund_performance.main(dt, str_fund, report_filename)
    fund_VaR_Vol.main(dt, str_fund, report_filename, print_pdf)
    fund_VaR_breakdown.main(dt, str_fund, report_filename)
    fund_Stress.main(dt, str_fund, report_filename)
    fund_FX.main(dt, str_fund, nav, report_filename)
    fund_CpCambial.main(dt, str_fund, nav, report_filename)
    fund_Equity.main(dt, str_fund, nav, report_filename)
    fund_equity_breakdown_on_off.main(dt, str_fund, nav, report_filename, print_pdf)
    fund_Equity_GrossNet.main(dt, str_fund, nav, report_filename)
    fund_PV01.main(dt, str_fund, nav, report_filename)
    fund_PV01_byRisk.main(dt, str_fund, nav, report_filename)
    fund_BRL_FX_Opt.main(dt, str_fund, nav, report_filename, print_pdf)
    fund_Backtest.main(dt, str_fund, report_filename)
    fund_Drawdown.main(dt, str_fund, report_filename)
    fund_trade_ideas.main(dt, str_fund, report_filename, print_pdf)
    fund_mock_trade_ideas.main(dt, str_fund, print_pdf)
    
    trader_Ibov_simulation.main(dt,str_fund,nav,report_filename, print_pdf)
    trader_SnP_simulation.main(dt,str_fund,nav,report_filename, print_pdf)
    trader_eqty_liquidity.main(dt, str_fund, nav, report_filename, False, True, print_pdf)
    trader_VaR_Vol.main(dt, str_fund, report_filename)
    trader_VaR_Stress.main(dt, str_fund, report_filename, print_pdf)
    trader_Drawdown.main(dt, str_fund, report_filename)
    trader_analysis.main(dt, str_fund, report_filename, print_pdf)
    trader_exposure.main(dt, str_fund, report_filename)
    
    b3_concentration.main(dt, str_fund, report_filename, print_pdf)
    b3_eqty_turnover.main(dt, str_fund, nav, report_filename, print_pdf)
    bond_turnover.main(dt,str_fund, report_filename,print_pdf)
    fund_rolagem.main(dt, str_fund, report_filename, print_pdf)
    
    if str_fund == 'A1 Master FIM':
        fund_exposure.main(dt)
    
    if dt == cal_B3.advance(cal_B3.endOfMonth(ql.Date.from_date(dt)), ql.Period('-1d')).to_date():
        print(u"\u26a0 \u26a0 \u26a0 \n\n *** CHECAR ROLAGEM *** \n\n\u26a0 \u26a0 \u26a0")
        
    trader_ideas_email.main(dt, str_fund)
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
    
    tic = timeit.default_timer()
    
    dt = datetime.date(2022, 11, 24)
    report_filename = '../xls/RiskMap_model.xlsm'
    
    # If next business day is in the next week, we print the figures in PDF format
    #  to be used in the weekly 'Reuniao de Posicionamento'
    bl_print_pdf = False
        
    fundos = [
                'A1 FIFE ITAU',
                'A1 FIFE BEM',
                'A1 Orange FIM',
                'A1 Master FIM'
             ]
    
    
    for str_fund, print_pdf in zip(fundos,
                                   [False]*(len(fundos)-1) + [bl_print_pdf]):
                     
        try:
            nav = fu.get_NAV(dt, str_fund)
        except Exception as err:
            print(u"\u2620 \u2620 \u2620")
            print("ERROR: {}".format(err))
            print(u"\u2620 \u2620 \u2620")
        main(dt, str_fund, nav, report_filename, print_pdf)
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))