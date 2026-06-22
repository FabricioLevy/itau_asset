import datetime
import pandas as pd
import numpy as np
import QuantLib as ql

from a1db.a1sql import SQLConnection

def main(dt):
    #%%
    connection = SQLConnection().get_connection()
            
    str_sql = """
        SELECT [product_id],p.[date_maturity],rate,[price], date_reference
        FROM [middle].[product_price] pp  INNER JOIN middle.product p 
        ON pp.product_id = p.id  
        WHERE p.product_type = 'LFT' 
         AND p.date_maturity >= '{0:%Y-%m-%d}' 
         AND date_reference = '{0:%Y-%m-%d}'
        ORDER BY p.[date_maturity] 
        """
    str_sql = str_sql.format(dt)
    dfProduct = pd.read_sql(str_sql, connection, index_col='product_id')    
    
    del str_sql    
    #%%
    calendar_br = ql.Brazil()
    today = ql.Date.from_date(dt)
    ql.Settings.instance().evaluationDate = today
         
    dates = [today]
    discfactors = [1]
    dfProduct['value'] = 0  # CS01
    for index, row in dfProduct.iterrows():
        (dt_i, spread, pu, _, _) = row.values
        dtExp = ql.Date.from_date(dt_i)
        du = calendar_br.businessDaysBetween(today, dtExp)
        disc_factor = 1 / (1+spread)**(du/252)
        dates.append(dtExp)
        discfactors.append(disc_factor)
        dfProduct.loc[index, 'value'] = -(du/252) * pu / (1+spread) / 10000
    
    #%%
    curveLFT = ql.DiscountCurve(dates, discfactors,\
                               ql.Business252(calendar_br), \
                               calendar_br, ql.LogLinear())   
    curveLFT.enableExtrapolation()
    lft_curve_handle = ql.YieldTermStructureHandle(curveLFT)
    
    str_curve = 'LFT Spread'
    dic_bucket = {1:'1D',30:'1M',60:'2M',90:'3M',180:'6M',\
                      270:'9M',360:'1Y',540:'1.5Y',720:'2Y',900:'2.5Y'} 
    dic_bucket.update({i*360:'{}Y'.format(i) for i in range(3, 16)})
    
    data=[(calendar_br.adjust(today+i, ql.Following).to_date(), i, \
           curveLFT.zeroRate(today+i, ql.Business252(calendar_br), ql.Compounded).rate() ,\
           curveLFT.discount(calendar_br.adjust(today+i, ql.Following))) \
          for i in dic_bucket.keys()]
        
    data+=[(lft_dt, np.nan, \
           curveLFT.zeroRate(ql.Date.from_date(lft_dt), ql.Business252(calendar_br), ql.Compounded).rate() ,\
           curveLFT.discount(calendar_br.adjust(ql.Date.from_date(lft_dt), ql.Following))) \
           for lft_dt in dfProduct['date_maturity'].values]    
    
    dfCurve = pd.DataFrame(data, columns=['tenor_date', 'tenor', 'curve_rate', 'discount_factor'])
    dfCurve.insert(0, 'curve_name', str_curve)
    dfCurve.insert(0, 'date_reference', dt)
    dfCurve['code_maturity'] = np.nan
    dfCurve['business_day'] = dfCurve['tenor_date'].apply(lambda x: calendar_br.businessDaysBetween(today, ql.Date.from_date(x)))
        
    #%%
    str_sql = "DELETE FROM [risk].[interest_rate_curve] "+ \
              "WHERE curve_name = '{}' AND date_reference = '{:%Y-%m-%d}' ".format(str_curve, dt)
    connection.execute(str_sql)
    
    dfCurve.to_sql("interest_rate_curve", connection, schema='risk', if_exists='append', index=False)
    print('{}- Inserted {} values for date {}: TABLE interest_rate_curve'.format(str_curve, len(dfCurve), dt))
        
    str_sql = "DELETE s FROM [risk].[product_sensitivity] s "+\
                "INNER JOIN [middle].[product] prod "+\
                "ON s.product_id = prod.id "+\
                "WHERE prod.[product_type]='LFT' AND s.sensitivity='CS01' AND "+\
                "s.date_reference = '{:%Y-%m-%d}' ".format(dt)
    connection.execute(str_sql)    
    dfProduct['sensitivity'] = 'CS01'
    dfProduct.reset_index()[['date_reference','product_id','sensitivity','value']].\
        to_sql("product_sensitivity", connection, schema='risk', if_exists='append', index=False)
    print('LFT - Inserted {} values for date {} : TABLE product_sensitivity - CS01'.format(len(dfProduct), dt))
    
 
#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 3, 9)
    main(dt)
    
    # dtIni = ql.Date(1,1,2016)
    # dtIni = ql.Brazil(ql.Brazil().Exchange).adjust(dtIni)
    # while dtIni<= ql.Date(1,1,2018):  
    #     main(dtIni.to_date())
    #     dtIni = ql.Brazil(ql.Brazil().Exchange).advance(dtIni, ql.Period(1, ql.Days))
    