import pandas as pd
import numpy as np
import datetime
import QuantLib as ql

from a1db.a1sql import SQLConnection

#%%
def main(dt):
#%%
    today = ql.Date.from_date(dt)
    str_curvename = 'SOFR Fut'
 
    connection = SQLConnection().get_connection()
    str_sql = f"""
               SELECT p.lote45_product, p.lote45_product_class, [date_maturity],pp.price,pp.rate
               FROM [middle].[product] p 
                   INNER JOIN middle.product_price pp ON p.id = pp.product_id
               WHERE product_type = 'SOFR Future' and
               date_reference = '{dt:%Y-%m-%d}'
               ORDER BY p.lote45_product_class, date_maturity
              """
    dfProd = pd.read_sql(str_sql, connection)
    
    
    str_sql = f"""
            SELECT [date_reference], [value]/100 as Sofr
            FROM [quant].[time_series_value] tsv 
                INNER JOIN quant.time_series ts
                    ON tsv.series_id = ts.id
            WHERE ts.entity_id = 'SOFRRATE' 
                AND field = 'PX_LAST'
                AND date_reference BETWEEN DATEADD(MONTH, -4, '{dt:%Y-%m-%d}') AND '{dt:%Y-%m-%d}'
            ORDER BY date_reference
    """
    dfIndex = pd.read_sql(str_sql, connection)
    
    del str_sql    
#%%
    ql.Settings.instance().evaluationDate = today
    
    index = ql.Sofr()
    calendar = index.fixingCalendar()
    index.clearFixings()
    index.addFixings([ql.Date.from_date(i) for i in dfIndex['date_reference'].to_list()], 
                      dfIndex['Sofr'].to_list())
   
    dic_helpers = {}         
    for code, _, exp_dt, price, rate in dfProd[dfProd['lote45_product_class']=='One-Month SOFR Futures - CME'].values:
        contract_date = ql.Date.from_date(exp_dt)  
        dic_helpers[code] = ql.SofrFutureRateHelper(ql.QuoteHandle(ql.SimpleQuote(price)), 
                                                    contract_date.month(),
                                                    contract_date.year(),
                                                    ql.Monthly,
                                                    index)
            
    for code, _, exp_dt, price, rate in dfProd[dfProd['lote45_product_class']=='Three-Month SOFR Futures - CME'].values:
        contract_date = ql.IMM.date(code[-2:], today)        
        if contract_date.month() in [3, 6, 9, 12]:
            dic_helpers[code] = ql.SofrFutureRateHelper(ql.QuoteHandle(ql.SimpleQuote(price)), 
                                                        contract_date.month(),
                                                        contract_date.year(),
                                                        ql.Quarterly,
                                                        index)
 
#%%
    curve_sofr = ql.PiecewiseCubicZero(today, 
                                       [i for i in dic_helpers.values()], 
                                       ql.Actual360())
    curve_sofr.enableExtrapolation()
 
    buckets = [1, 30, 60, 90, 180, 270, 360, 540, 720, 900] + [i*360 for i in range(3,11)]
        
    data=[(ql.UnitedStates().adjust(today+i).to_date(), i, 
               curve_sofr.zeroRate(today+i, ql.Actual360(), ql.Compounded, ql.Annual).rate(), 
               curve_sofr.discount(today+i), np.nan) for i in buckets]
        

    data+=[(ql.UnitedStates().adjust(dt_i).to_date(), np.nan, 
               curve_sofr.zeroRate(dt_i, ql.Actual360(), ql.Compounded, ql.Annual).rate(), 
               curve_sofr.discount(dt_i), t) 
               for (t, (dt_i, _)) in zip([0]+list(dic_helpers.keys()), curve_sofr.nodes()) if t!=0]

        
    dfCurve = pd.DataFrame(data, columns=['tenor_date', 'tenor', 'curve_rate', 'discount_factor','code_maturity'])
    dfCurve.insert(0, 'curve_name', str_curvename)
    dfCurve.insert(0, 'date_reference', dt)
        
    dfCurve['business_day'] = dfCurve['tenor_date'].apply(lambda x: ql.UnitedStates().businessDaysBetween(today, ql.Date.from_date(x)))
        
    #%%  
    str_sql = "DELETE FROM [risk].[interest_rate_curve] "+ \
                  "WHERE curve_name = '{}' AND date_reference = '{:%Y-%m-%d}' ".format(str_curvename, dt)
    connection.execute(str_sql)
        
    dfCurve.to_sql("interest_rate_curve", connection, schema='risk', if_exists='append', index=False)
    print('{} - Inserted {} values for date {} : TABLE interest_rate_curve'.format(str_curvename, len(dfCurve), dt))
        
    
#%%    
if __name__ == "__main__":
    
    dt = datetime.date(2022, 12, 12)
    main(dt)
    
    # dtIni = ql.Date(2,3,2022)
    # dtIni = ql.UnitedStates().adjust(dtIni)
    # while dtIni<= ql.Date(1, 4, 2022):    
    #     main(dtIni.to_date())
    #     dtIni = ql.UnitedStates().advance(dtIni, ql.Period(1, ql.Days))
    
