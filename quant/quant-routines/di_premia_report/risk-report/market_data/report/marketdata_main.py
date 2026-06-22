import datetime
import timeit
import xlwings as xw
import pathlib
import os

import marketdata_pre, marketdata_inflation, marketdata_cpcambial, \
        marketdata_latam, marketdata_vol

#%%
def main(dt, report_filename):
#%%
    report_filename = os.path.expanduser('~\\Documents\\Github\\market_data\\report\\') + report_filename
    wb = xw.Book(report_filename)
    str_cover = 'BRL_rates'
    wb.sheets(str_cover).range('DataRef').value = dt
    
    # str_path = os.path.dirname(report_filename) + "/../output/{:%Y%m%d}/".format(dt)
    str_path = os.path.expanduser('~\\Documents\\Github\\market_data\\report\\') + "output/{:%Y%m%d}/".format(dt)
    pathlib.Path(str_path).mkdir(exist_ok=True)
    pathlib.Path(str_path + 'pics/').mkdir(exist_ok=True)
        
    for m in [
            marketdata_pre, 
            marketdata_inflation, 
            marketdata_cpcambial,
            marketdata_latam, 
            marketdata_vol
              ]:
        m.main(dt, report_filename)
    
    for pic in os.listdir(os.path.expanduser('~\\Documents\\Github\\market_data\\report\\') + 'temp_figs'):
        if pic[0:8] == "{:%Y%m%d}".format(dt):
            os.replace(os.path.expanduser('~\\Documents\\Github\\market_data\\report\\') + 'temp_figs/' + pic, str_path + 'pics/' + pic)
        elif pic.split('.')[-1] == 'svg':
            os.remove(os.path.expanduser('~\\Documents\\Github\\market_data\\report\\') + 'temp_figs/' + pic)
    
    str_newfile = str_path + "{:%Y%m%d}_MarketData.xlsm".format(dt)
    wb.save(path=str_newfile)
    # wb.close()
    
    
#%%    
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    ################################
    ### ------ UPDATE HERE ----- ###
    dt = datetime.date(2022, 4, 13)
    ################################
    report_filename = 'xls/MarketData_model.xlsm'
    
    main(dt, report_filename) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))   