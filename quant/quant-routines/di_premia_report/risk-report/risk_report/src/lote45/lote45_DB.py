import datetime
import QuantLib as ql
import lote45_DB_VaR_Stress
import lote45_DB_Position
import lote45_insert_missing_product
import lote45_DB_Primitives
import lote45_DB_Primitives_Offshore
import lote45_DB_Primitives_Ptax
import lote45_DB_covar
import lote45_DB_eqty_prices
import lote45_missing_product
import lote45_PTAX_VaR_Adjust
import lote45_CPMOpt_VaR_Adjust
import lote45_DB_VaR_NotInTree
import lote45_update_option_strike
import HybVaR_calculation_upload
import lote45_check_mandate
import warnings

import sys
sys.path.insert(1, '../')
import fund_data

def main(dt, funds):
    
    warnings.filterwarnings('ignore', category=DeprecationWarning)
    dic_prods = lote45_missing_product.main(dt)
    if dic_prods:
        print('... inserting new products:')
        for prod_class, prods in dic_prods.items():
            print(prod_class)
            lote45_insert_missing_product.main(prod_class, prods)
    
    lote45_update_option_strike.main(dt)
    lote45_check_mandate.main(dt)        
    lote45_DB_VaR_Stress.main(dt)
    lote45_DB_Position.main(dt)
    lote45_DB_Primitives.main(dt)
    lote45_DB_Primitives_Offshore.main(dt)
    lote45_DB_Primitives_Ptax.main(dt)
    lote45_DB_covar.main(dt, funds)
    lote45_DB_eqty_prices.main(dt)
    for str_fund in funds:
        lote45_CPMOpt_VaR_Adjust.main(dt, str_fund)
        data = fund_data.db_data(dt, str_fund, verbose=False)
        lote45_DB_VaR_NotInTree.main(data)
    if ql.Brazil(ql.Brazil().Exchange).endOfMonth(ql.Date.from_date(dt)) == ql.Date.from_date(dt):
        for str_fund in funds:
            print('B3 EoM - {:%d-%b-%Y} - {} - Adjusting Delta FX in VaR...'.format(dt, str_fund))
            lote45_PTAX_VaR_Adjust.main(dt, str_fund)
    for str_fund in funds:
        HybVaR_calculation_upload.main(dt, str_fund)

#%%
if __name__ == "__main__":

    dt = datetime.date(2022, 10, 24) 
    funds = ['A1 Master FIM', 
             'A1 Orange FIM',
             'A1 FIFE BEM', 
              'A1 FIFE ITAU'
             ]
    main(dt, funds)