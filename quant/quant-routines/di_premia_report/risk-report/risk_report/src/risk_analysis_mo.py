import os
import sys
import timeit
import QuantLib as ql

#%%     Input: Data

numbers_of_days_delayed = 0

#%%     Setup de Datas dos Processos

dt = ql.Brazil().advance(ql.Date.todaysDate(),ql.Period('-' + str(numbers_of_days_delayed) + 'd')).to_date()
# dt = datetime.date(2021, 8, 30) # Editar data manualmente.
print('d0 = ' + str(dt))
dt_yesterday = ql.Brazil().advance(ql.Date.from_date(dt),ql.Period('-1d')).to_date()
print('d-1 = ' + str(dt_yesterday))

#%%     Download dos Dados ANBIMA e B3 

def download_anbima_b3():
    path_market_data_downloader = os.path.expanduser('~\\Documents\\Github\\market_data\\downloader')
    sys.path.insert(1, path_market_data_downloader)
    import download_main
    try:
        download_main.main(dt)
    except ValueError:
        print('\n!!! ERRO no download dos dados ANBIMA & B3 !!!')
download_anbima_b3()

# import time
# for x in range (600):
#     download_anbima_b3()
#     time.sleep(10)

#%%     Rotina de Curvas

path_market_data = os.path.expanduser('~\\Documents\\Github\\market_data')
sys.path.insert(1, path_market_data)
import curves_main
tic = timeit.default_timer()
curves_main.main(dt, True, up2data_feed = True, n_trades = 'UP2DATA')
tac = timeit.default_timer()
print('\n\n******\nProcesso Finalizado! Tempo de Execução: {:1.2f}s'.format(tac-tic))

#%%     Gerar Planilha do Relatório Market Data

path_market_data_report = os.path.expanduser('~\\Documents\\Github\\market_data\\report')
sys.path.insert(1, path_market_data_report)
import marketdata_main
marketdata_report_filename = 'xls/MarketData_model.xlsm'
tic = timeit.default_timer()
marketdata_main.main(dt, marketdata_report_filename)
tac = timeit.default_timer()
print("Execution time: {:3.1f}s".format(tac - tic))

#%%     Salvar na Rede a Planilha para Simulação de VaR

path_var_simulation = os.path.expanduser('~\\Documents\\Github\\VaR_Simulation')
sys.path.insert(1, path_var_simulation)
import var_main
var_main.main(dt)

#%%     Rodar o Relatório de Liquidez

path_liquidity_report_src = os.path.expanduser('~\\Documents\\Github\\liquidity_report\\src')
sys.path.insert(1, path_liquidity_report_src)
import liquidity_report
report_filename = '/xls/LiquidityRisk_Model.xlsm'
liquidity_report.main(dt_yesterday, 'A1 Master FIM', report_filename)
liquidity_report.main(dt_yesterday, 'A1 Orange FIM', report_filename)
liquidity_report.main(dt_yesterday, 'A1 FIFE BEM', report_filename)

#%%     Cadastra Novas Ações, Opções de Ações e Atualiza os Strikes

try:
    path_market_data = os.path.expanduser('~\\Documents\\Github\\market_data')
    sys.path.insert(1, path_market_data)
    import load_equity_time_series
except:
    None

#%%     Carrega Opções de USDBRL Exportadas do LOTE45 no Banco de Dados

try:
    path_market_data = os.path.expanduser('~\\Documents\\Github\\market_data')
    sys.path.insert(1, path_market_data)
    import load_fx_opt_time_series
except:
    None

#%%     Consolida no Banco de Dados as Análises de Risco do LOTE45

path_risk_report_lote45 = os.path.expanduser('~\\Documents\\Github\\risk_report\\src\\lote45')
sys.path.insert(1, path_risk_report_lote45)
import lote45_DB
lote45_DB.main(dt, 'A1 Master FIM')

#%%     Adiciona à Rede Planilha de Comparação Master vs Orange

path_risk_report_src = os.path.expanduser('~\\Documents\\Github\\risk_report\\src')
sys.path.insert(1, path_risk_report_src)
import Master_Hedge_comparison
Master_Hedge_comparison.main(dt, 'A1 Orange FIM')
Master_Hedge_comparison.main(dt, 'A1 FIFE BEM')

#%%     Salvar na Rede as Planilhas de PnL, Gross e VaR p/ Gestores de Equities

path_save_eqty_var_pnl = os.path.expanduser('~\\Documents\\Github\\save_eqty_var_pnl')
sys.path.insert(1, path_save_eqty_var_pnl)
import save_var_pnl
save_var_pnl.main('A1 Master FIM', dt)
save_var_pnl.main('A1 Orange FIM', dt)
save_var_pnl.main('A1 FIFE BEM', dt)