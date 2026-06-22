import datetime

import anbima.LFT_price
import anbima.LTN_price
import anbima.NTNF_price
import anbima.NTNB_price

def main (dt):
    anbima.LFT_price.main(dt)
    anbima.LTN_price.main(dt)
    anbima.NTNF_price.main(dt)
    anbima.NTNB_price.main(dt)

#%%    
if __name__ == "__main__":
    dt = datetime.date(2022, 1, 7)
    main(dt) 