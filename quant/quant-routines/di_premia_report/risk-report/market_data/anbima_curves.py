import datetime

import anbima.LFT_curve
import anbima.LTN_curve
import anbima.NTNB_curve
import anbima.NTNF_curve
import anbima.NTNB_BEI_curve
import anbima.DAP_BEI_curve

def main(dt):
    anbima.LFT_curve.main(dt)
    anbima.LTN_curve.main(dt)
    anbima.NTNF_curve.main(dt)
    anbima.NTNB_curve.main(dt)
    anbima.NTNB_BEI_curve.main(dt)
    anbima.DAP_BEI_curve.main(dt)

#%%    
if __name__ == "__main__":
    dt = datetime.date(2022, 3, 23)
    main(dt)