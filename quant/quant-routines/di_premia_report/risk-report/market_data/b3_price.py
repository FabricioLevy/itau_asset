import datetime

import b3.b3_DI_price
import b3.b3_DAP_price
import b3.b3_FRC_price
import b3.b3_DDI_price
import b3.b3_DOLFUT_price
import b3.b3_INDFut_price


def main (dt):
    
    b3.b3_DI_price.main(dt)
    b3.b3_DAP_price.main(dt)
    b3.b3_FRC_price.main(dt)
    b3.b3_DDI_price.main(dt)
    b3.b3_DOLFUT_price.main(dt)
    b3.b3_INDFut_price.main(dt)

#%%    
if __name__ == "__main__":
    dt = datetime.date(2022, 1, 3)
    main(dt) 