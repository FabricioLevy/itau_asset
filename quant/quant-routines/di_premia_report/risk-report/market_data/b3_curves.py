import datetime
import b3_curves_holiday
import b3.IPCA_pro_rata_temp
import b3.b3_DI_curve 
import b3.b3_DAP_curve
import b3.b3_DDI_curve


def main (dt, b3_holiday=False):    
    
    b3.IPCA_pro_rata_temp.save_IPCA_prt(dt)
    if b3_holiday:
        b3_curves_holiday.main(dt)
    else:
        b3.b3_DI_curve.main(dt)
        b3.b3_DAP_curve.main(dt)
        b3.b3_DDI_curve.main(dt)

    
#%%    
if __name__ == "__main__":
    dt = datetime.date(2021, 9, 15)
    main(dt, False) 
    