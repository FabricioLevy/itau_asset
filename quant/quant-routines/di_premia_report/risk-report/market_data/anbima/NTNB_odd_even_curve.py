import datetime
import pandas as pd
import numpy as np
import QuantLib as ql

from a1db.a1sql import SQLConnection

import os, sys
sys.path.insert(1, os.path.expanduser('~\\Documents\\Github\\Instruments'))
from BRLBond import BrazilianGovernmentBond as BRLGovBond


def main(dt, debug=False):
    #%%    
    calendar_br = ql.Brazil()
    today = ql.Date.from_date(dt)
    connection = SQLConnection().get_connection()
            
    str_sql = f"""
        SELECT t.[data_vencimento] as date_maturity, 
              t.[taxa_indicativa]/100 as rate, 
              t.[PU] as price, 
              t.[data_emissao] as date_issue, 
              v.VNA
                FROM [anbima].taxa_titulo_publico t INNER JOIN [anbima].VNA v 
                     ON t.[date_reference] = v.[date_reference] AND t.titulo=v.titulo 
                     AND t.[codigo_selic] = v.[codigo_selic]
                 WHERE t.titulo = 'NTN-B' AND t.[data_vencimento] <> '2023-03-15'
                 AND t.[date_reference] = '{dt:%Y-%m-%d}'
                 order by data_vencimento
                """
    df = pd.read_sql(str_sql, connection)
    del str_sql
    #%%    
    ql.Settings.instance().evaluationDate = today
    day_count = ql.Business252(calendar_br)   
    curve_zero_link = ql.RelinkableYieldTermStructureHandle()
    ntnbs = []
    for (dtExp, rt, pu, dtIssue, vna) in df.values:
        b = BRLGovBond.NTNB(ql.Date.from_date(dtExp), 
                            ql.Date.from_date(dtIssue), 
                            vna) 
        b.pu_anbima = pu
        b.tx_anbima = rt
        b.setPricingEngine(ql.DiscountingBondEngine(curve_zero_link))
        ntnbs.append(b)
        
    ntnb_helpers = {'odd':[],
                    'even':[]}
    for b in ntnbs:
        cleanPrice = b.cleanPrice(b.tx_anbima,
                                  ql.Business252(calendar_br), 
                                  ql.Compounded, 
                                  ql.Annual)
        if b.maturityDate().year() % 2 == 0:
            ntnb_helpers['even'].append(ql.BondHelper(ql.QuoteHandle(ql.SimpleQuote(cleanPrice)), b))
        else:
            ntnb_helpers['odd'].append(ql.BondHelper(ql.QuoteHandle(ql.SimpleQuote(cleanPrice)), b))

    #%%    
    curves_NTNB = {}
    for k, helpers in ntnb_helpers.items():
        curves_NTNB[k] = ql.PiecewiseLogLinearDiscount(0,
                                                       calendar_br, 
                                                       helpers, 
                                                       day_count)
        curves_NTNB[k].enableExtrapolation()

    #%%
    for k, curve in curves_NTNB.items():
        curve_zero_link.linkTo(curve)
        # bond_engine = ql.DiscountingBondEngine(ql.YieldTermStructureHandle(curve))
        print(f"\n\n==> curve with {k.upper()} years<==")
        for b in ntnbs:
            # b.setPricingEngine(ql.DiscountingBondEngine(ql.YieldTermStructureHandle(curve)))
            b.recalculate()
            pu_zero = b.NPV()*b.VNA()
            tir_zero = b.bondYield(ql.Business252(), ql.Compounded, ql.Annual)
            
            print(f"{b} {b.pu_anbima=:10,.4f}  {pu_zero=:10,.4f}  Diff:{b.pu_anbima-pu_zero:>10,.4f}")
            print(f"{b} {b.tx_anbima=:10,.4%}  {tir_zero=:10,.4%}  Diff:{b.tx_anbima-tir_zero:>10,.4%}\n")
    
#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 6, 2)
    main(dt, True)
    