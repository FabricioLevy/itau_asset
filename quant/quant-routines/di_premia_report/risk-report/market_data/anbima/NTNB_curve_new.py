import datetime
import pandas as pd
import numpy as np
import QuantLib as ql

from a1db.a1sql import SQLConnection

import os, sys
path_github = os.path.expanduser('~\\Documents\\Github')
sys.path.insert(1, path_github + '\\Instruments')
from BRLBond import BrazilianBond as BRLGovBond

sys.path.insert(0, '../')
import curve_db as cdb


def main(dt, debug=False):
    #%%  
    calendar_br = ql.Brazil()
    today = ql.Date.from_date(dt)
    ql.Settings.instance().evaluationDate = today

    connection = SQLConnection().get_connection()
            
    str_sql = f"""
                SELECT pp.product_id, p.date_issue, p.date_maturity, rate, price
                FROM [middle].[product_price] pp INNER JOIN middle.product p 
                        ON pp.product_id = p.id
                WHERE p.product_type = 'NTN-B'
                    AND pp.date_reference = '{dt:%Y-%m-%d}'
                    AND p.date_maturity <> '2023-03-15'
                ORDER BY date_maturity
                """
    df = pd.read_sql(str_sql, connection, index_col='product_id')
    
    str_sql = f"""
                SELECT date_reference, price as vna
                FROM [middle].[product_price]  
                    WHERE product_id = 'VNA NTNB'
                      AND date_reference = '{dt:%Y-%m-%d}'
               """
    
    vna = pd.read_sql(str_sql, connection, index_col='date_reference').loc[dt, 'vna']

    del str_sql
    #%%      
    dic_ntnb = {}
    ntnb_helpers = []
    for prod_id, (dt_issue, dt_exp, rate, price) in df.iterrows():
        b = BRLGovBond.NTNB(dtExpiry=ql.Date.from_date(dt_exp), 
                            dtIssue=ql.Date.from_date(dt_issue), 
                            vnaIndex=vna) 
        dic_ntnb[prod_id] = b    
        cleanPrice = b.cleanPrice(rate, 
                                  ql.Business252(calendar_br), 
                                  ql.Compounded, 
                                  ql.Annual)

        ntnb_helpers.append(ql.BondHelper(ql.QuoteHandle(ql.SimpleQuote(cleanPrice)), b))
       
    #%%            
    curveNTNB = ql.PiecewiseLogLinearDiscount(0, 
                                              calendar_br, 
                                              ntnb_helpers, 
                                              ql.Business252(calendar_br))
    curveNTNB.enableExtrapolation()
    ntnb_curve_handle = ql.YieldTermStructureHandle(curveNTNB)
    
    shift_pv01 = ql.SimpleQuote(0.0)
    ntnb_curve_shifted = ql.ZeroSpreadedTermStructure(ntnb_curve_handle, 
                                                      ql.QuoteHandle(shift_pv01), 
                                                      ql.Compounded, 
                                                      ql.Annual)
    ntnb_curve_shifted_handle = ql.YieldTermStructureHandle(ntnb_curve_shifted)

    bond_engine = ql.DiscountingBondEngine(ntnb_curve_shifted_handle)
    
    for prod_id, b in dic_ntnb.items():
        
        b.setPricingEngine(bond_engine)
        
        pu_anbima = df.loc[prod_id,'price']
        tx_anbima = df.loc[prod_id,'rate']
        
        print(f"\n{b} {b.NPV()=:10.4f} {pu_anbima=:10.4f} {b.NPV()-pu_anbima:10.4f}")
        
        shift_pv01.setValue(0.0001)
        price_1bp_up = b.NPV()
        shift_pv01.setValue(-0.0001)
        price_1bp_down = b.NPV()
        shift_pv01.setValue(0.0)
        
        pv01 = (price_1bp_up - price_1bp_down) / 2
        
        print(f"{b} {pv01:10.4f} {b.PV01():10.4f}")
        
#%%        
    #     pu_zero = b.NPV()*b.VNA()
    #     pu_tir_ql = (b.notional()/100 * b.VNA()) * b.dirtyPrice(b.tx_anbima,
    #                                                             ql.Business252(calendar_br), 
    #                                                             ql.Compounded, 
    #                                                             ql.Annual)
    #     pu_tir_a1 = b.setPU_byRate_Anbima(today)
        
    #     if debug:
    #         print(b)
    #         print(f"> Diff PU Anbima x Zero: {b.pu_anbima-pu_zero:8.6f}")
    #         print(f"Anbima: {b.pu_anbima:8.6f} Zero: {pu_zero:8.6f} TIR QL: {pu_tir_ql:8.6f} TIR A1: {pu_tir_a1:8.6f}")

    #     shift_pv01.setValue(0.0001)
    #     pu_zero_shifted = b.VNA() * b.NPV() 
    #     pu_tir_shifted = (b.notional()/100 * b.VNA()) * b.dirtyPrice(b.tx_anbima+0.0001, 
    #                                                                  ql.Business252(calendar_br), 
    #                                                                  ql.Compounded, 
    #                                                                  ql.Annual)
    #     if debug:
    #         print("pv01 zero={:2.6f}  pv01 Tir={:2.6f}".\
    #               format(pu_zero_shifted-b.pu_anbima, pu_tir_shifted-b.pu_anbima))
        
    #     df.loc[b.maturityDate().to_date(), 'PV01'] = pu_zero_shifted - b.pu_anbima
    #     df.loc[b.maturityDate().to_date(), 'prazo_medio'] = b.prazo_medio(today)
        
    #     if b.maturityDate().to_date() in df_yesterday.index:
    #         vna_d1 = df_yesterday.loc[b.maturityDate().to_date(), 'VNA'] / 1_000
    #         pu_d1 = df_yesterday.loc[b.maturityDate().to_date(), 'price']
    #         tx_d1 = df_yesterday.loc[b.maturityDate().to_date(), 'rate']
        
    #         pu_carregado = pu_d1 * ((1+tx_d1)**(1/252)) * (b.VNA()/vna_d1)
    #         df.loc[b.maturityDate().to_date(), 'carry'] = (pu_carregado - pu_d1 * ((1+CDI)**(1/252))) / (b.pu_anbima - pu_tir_shifted) 
    #     y = ql.InterestRate(b.tx_anbima, ql.Business252(calendar_br), ql.Compounded, ql.Annual)
    #     dur = ql.BondFunctions.duration(b, y, ql.Duration.Macaulay)
    #     df.loc[b.maturityDate().to_date(), 'duration'] = dur 
        
    #     bei_di = (1+curve_di.zeroRateValue(calendar_br.advance(today, ql.Period(int(dur*252), ql.Days)))) / (1+b.tx_anbima) - 1
    #     df.loc[b.maturityDate().to_date(), 'BEI_DI'] = bei_di
        
    #     if abs(b.pu_anbima-pu_zero) > 0.0005:
    #         print(f">> Warning << {b} : Diff PU TIR x Zero: {b.pu_anbima-pu_zero:12.6f}")

    #  #%%
    # str_curve = 'NTNB Zero'
    # dic_bucket = {1:'1D',30:'1M',60:'2M',90:'3M',180:'6M',\
    #                   270:'9M',360:'1Y',540:'1.5Y',720:'2Y',900:'2.5Y'} 
    # dic_bucket.update({i*360:'{}Y'.format(i) for i in range(3,51)})
    
    # data=[(calendar_br.adjust(today+i, ql.Following).to_date(), i, \
    #        curveNTNB.zeroRate(today+i, ql.Business252(calendar_br), ql.Compounded).rate() ,\
    #        curveNTNB.discount(calendar_br.adjust(today+i, ql.Following))) \
    #       for i in dic_bucket.keys()]
        
    # data+=[(b.maturityDate().to_date(), np.nan, \
    #        curveNTNB.zeroRate(b.maturityDate(), ql.Business252(calendar_br), ql.Compounded).rate() ,\
    #        curveNTNB.discount(calendar_br.adjust(b.maturityDate(), ql.Following))) \
    #        for b in ntnbs]    
    
    # dfCurve = pd.DataFrame(data, columns=['tenor_date', 'tenor', 'curve_rate', 'discount_factor'])
    # dfCurve.insert(0, 'curve_name', str_curve)
    # dfCurve.insert(0, 'date_reference', dt)
    # dfCurve['code_maturity'] = np.nan
    # dfCurve['business_day'] = dfCurve['tenor_date'].apply(lambda x: calendar_br.businessDaysBetween(today, ql.Date.from_date(x)))
    
    # #%%
   
        

    
    # #%%
    # str_sql = "DELETE FROM [risk].[interest_rate_curve] "+ \
    #           "WHERE curve_name = '{}' AND date_reference = '{:%Y-%m-%d}' ".format(str_curve, dt)
    # connection.execute(str_sql)
    
    # dfCurve.to_sql("interest_rate_curve", connection, schema='risk', if_exists='append', index=False)
    # print('{}- Inserted {} values for date {}'.format(str_curve, len(dfCurve), dt))
    
    
    # str_sql = "DELETE price FROM [middle].[product_price] price "+\
    #             "INNER JOIN [middle].[product] prod "+\
    #             "ON price.product_id = prod.id "+\
    #             "WHERE prod.[lote45_product_class]='NTN-B' AND "+\
    #             "price.date_reference = '{:%Y-%m-%d}' ".format(dt)
    # connection.execute(str_sql)    
    # df[['date_reference','product_id','rate','price']].\
    #     to_sql("product_price", connection, schema='middle', if_exists='append', index=False)
    # print('NTN-B - Inserted {} values for date {} : TABLE product_price'.format(len(df), dt))
    
    
    # (vna, indice) = df[['VNA','indice']].iloc[0].values
    # str_sql = """
    # DELETE FROM middle.product_price
    # WHERE product_id = 'VNA NTNB' and date_reference = '{:%Y-%m-%d}'
    
    # INSERT INTO middle.product_price (date_reference, product_id, price, rate)
    #     VALUES ('{:%Y-%m-%d}', 'VNA NTNB', {:1.10f}, {:1.10f})
    # """
    # str_sql = str_sql.format(dt, dt, vna, indice)
    # connection.execute(str_sql)    
    # print('NTN-B - Inserted 1 VNA value for date {} : TABLE product_price'.format(dt))
    
    
    # str_sql = "DELETE s FROM [risk].[product_sensitivity] s "+\
    #             "INNER JOIN [middle].[product] prod "+\
    #             "ON s.product_id = prod.id "+\
    #             "WHERE prod.[lote45_product_class]='NTN-B' AND "+\
    #             "s.date_reference = '{:%Y-%m-%d}' ".format(dt)
    # connection.execute(str_sql)    
    
    # for sens in ['PV01','prazo_medio', 'spread_dap', 'carry', 'duration', 'BEI_DI']:
    #     dfTemp =  df[['date_reference','product_id', sens]].copy()
    #     dfTemp.rename({sens:'value'}, axis=1,inplace=True)
    #     dfTemp['sensitivity'] = sens
    #     dfTemp.to_sql("product_sensitivity", connection, schema='risk', if_exists='append', index=False)
    #     print(f'NTN-B - Inserted {len(df)} values for date {dt} : TABLE product_sensitivity - {sens}'.format(len(df), dt))
        

    
#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 11, 16)
    main(dt, True)
    
    