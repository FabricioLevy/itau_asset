import datetime

import b3.b3_DI_up2data_price
import b3.b3_DAP_up2data_price
import b3.b3_FRC_up2data_price
import b3.b3_DDI_up2data_price
import b3.b3_DOLFUT_up2data_price
import b3.b3_INDFut_up2data_price
import b3.b3_equities_up2data_price
import b3.b3_IDIOptions_up2data_price
import b3.b3_CPMOptions_up2data_price
import b3.b3_economic_indicators_up2data_price

def main (dt):

    b3.b3_DI_up2data_price.main(dt)
    b3.b3_DAP_up2data_price.main(dt)
    b3.b3_FRC_up2data_price.main(dt)
    b3.b3_DDI_up2data_price.main(dt)
    b3.b3_DOLFUT_up2data_price.main(dt)
    b3.b3_INDFut_up2data_price.main(dt)
    b3.b3_equities_up2data_price.main(dt)
    b3.b3_IDIOptions_up2data_price.main(dt)
    b3.b3_CPMOptions_up2data_price.main(dt)
    b3.b3_economic_indicators_up2data_price.main(dt)

#%%    
if __name__ == "__main__":
    dt = datetime.date(2022, 1, 26)
    main(dt) 