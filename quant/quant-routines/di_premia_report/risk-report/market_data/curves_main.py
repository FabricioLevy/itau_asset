import b3_price as b3_prc
import b3_up2data_price as b3_u2d_prc
import b3_curves as b3_crv
import anbima_price
import anbima_curves as anbima_crv
import swap_curves as swap_crv
import b3.b3_broadcast_price
import cme_price, cme_curve
import datetime
import QuantLib as ql
import timeit
import os
import sys

path_u2d = os.path.expanduser('~\\Documents\\Github\\download_up2data_files\\app\\')
sys.path.insert(1, path_u2d)
import b3_up2data_volume

def main (dt, price_from_b3 = True, up2data_feed = True, n_trades = 'UP2DATA'):
    ql.Brazil(ql.Brazil().Exchange).removeHoliday(ql.Date(25, 1, 2022))
    if not ql.Brazil(ql.Brazil().Exchange).isHoliday(ql.Date.from_date(dt)):
        lote45_products = ['DDI Future', 'FRC', 'DI1Future', 'DAP Future', 'IBOVSPFuture', 'USDBRLFuture']
        
        path_file = os.path.expanduser('~\\Documents\\Github\\market_data\\')
        sys.path.insert(1, path_file)
        str_file = path_file + r"b3\b3_broadcast.xlsx"
        
        if price_from_b3:
            if up2data_feed:
                b3_u2d_prc.main(dt)
            else:
                b3_prc.main(dt)
            if n_trades == 'UP2DATA':
                print('getting number of trades from UP2DATA...')
                b3_up2data_volume.get_volumes(dt)
            elif n_trades == 'Broadcast+':
                print('getting number of trades from Broadcast+...')
                b3.b3_broadcast_price.excel2SQL (dt, lote45_products, str_file, True)
        else:
            print('getting data from Broadcast+...')
            b3.b3_broadcast_price.excel2SQL (dt, lote45_products, str_file, False)
        b3_holiday = False
    else:
        print ("B3 Holiday")
        b3_holiday = True
    
    anbima_price.main(dt)
    cme_price.main(dt)
    
    b3_crv.main(dt, b3_holiday)
    anbima_crv.main(dt)
    swap_crv.main(dt)
    cme_curve.main(dt)
    
#%%    
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt = datetime.date(2022, 7, 21)
    try:
        main(dt, 
             price_from_b3 = False, 
             up2data_feed = False,
             n_trades = 'Broadcast+')    
        
    except Exception as err:
        print(f" !!!  {err=}")

    
    tac = timeit.default_timer()
    print('\n\n******\nProcesso Finalizado! Tempo de Execução: {:1.2f}s'.format(tac-tic))