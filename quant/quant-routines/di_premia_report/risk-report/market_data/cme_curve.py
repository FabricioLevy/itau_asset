import datetime

import cme.ed_fut_curve
import cme.ff_fut_curve
import cme.sofr_fut_curve
import cme.ust_curve


def main(dt):
    cme.ed_fut_curve.main(dt)
    cme.ff_fut_curve.main(dt)
    cme.sofr_fut_curve.main(dt)
    cme.ust_curve.main(dt)

#%%    
if __name__ == "__main__":
    dt = datetime.date(2022, 12, 12)
    main(dt)