import datetime

import swaps.swap_mxn_curve
import swaps.swap_clp_curve
import swaps.swap_cop_curve

def main(dt):
    swaps.swap_mxn_curve.main(dt)
    swaps.swap_clp_curve.main(dt)
    swaps.swap_cop_curve.main(dt)
    
#%%    
if __name__ == "__main__":
    
    dt = datetime.date(2021, 6, 22)
    main(dt) 
    
