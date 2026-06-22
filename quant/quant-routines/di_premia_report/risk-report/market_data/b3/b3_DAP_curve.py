import pandas as pd
import datetime
import QuantLib as ql

from a1db.a1sql import SQLConnection


#%%
def main(dt):
#%%
    str_curvename = 'DAP Fut' 
    
    connection = SQLConnection().get_connection()
            
    str_sql = """
        SELECT pp.date_reference, '{}' as curve_name, pp.product_id as code_maturity,
        p.date_maturity as tenor_date, pp.price/100000 as discount_factor, pp.rate as curve_rate
        FROM [middle].[product] p INNER JOIN middle.product_price pp ON p.id = pp.product_id
        WHERE pp.date_reference = '{:%Y-%m-%d}' and product_type = 'DAP Future'
        ORDER BY date_maturity
    """
    str_sql = str_sql.format(str_curvename, dt)
    df = pd.read_sql(str_sql, connection)
    
    str_sql = """
        SELECT date_reference, price as IPCA_PRT
        FROM [middle].[product_price]
        WHERE product_id = 'IPCA PRT' AND date_reference = '{:%Y-%m-%d}'
    """
    str_sql = str_sql.format(dt)
    ipca_prt = pd.read_sql(str_sql, connection, index_col='date_reference').loc[dt,'IPCA_PRT']
    del str_sql    
    
    #%%
    calendar_br = ql.Brazil()
    today = ql.Date.from_date(dt)
     
    df = df[df['tenor_date']>dt]
    df.sort_values('tenor_date', inplace=True)
    
    #%%
    dfPV01 = df[['date_reference', 'code_maturity', 'tenor_date', 'discount_factor', 'curve_rate']].copy()
    dfPV01['value'] = (dfPV01['tenor_date'].apply(lambda x: calendar_br.businessDaysBetween(today, ql.Date.from_date(x)))/252) *\
                            (1/(1+dfPV01['curve_rate']))*dfPV01['discount_factor'] * ipca_prt * 0.00025 * 10  #(Note: 10 = PU/10000)
    str_sql = "DELETE s FROM [risk].[product_sensitivity] s "+\
                "INNER JOIN [middle].[product] prod "+\
                "ON s.product_id = prod.id "+\
                "WHERE prod.[lote45_product_class]='DAP Future' AND "+\
                "s.date_reference = '{:%Y-%m-%d}'  AND s.sensitivity = 'PV01'".format(dt)
    connection.execute(str_sql)    
    dfPV01.rename(columns={'code_maturity':'product_id'}, inplace=True)
    dfPV01['sensitivity'] = 'PV01'
    dfPV01[['date_reference','product_id','sensitivity','value']].\
        to_sql("product_sensitivity", connection, schema='risk', if_exists='append', index=False)
    print('DAP Future - Inserted {} values for date {} : TABLE product_sensitivity'.format(len(dfPV01), dt))                            
    
    
    #%%
    
    listDatesDAP = [today] + [ql.Date.from_date(i) for i in df['tenor_date']]    
    listDiscountFactor = [1] + [i for i in df['discount_factor']]
        
    curveDAP = ql.DiscountCurve(listDatesDAP, listDiscountFactor,\
                               ql.Business252(calendar_br), \
                               calendar_br, ql.LogLinear())
    
    from types import MethodType
    def zeroRateValue(self, dt):
        return self.zeroRate(dt, ql.Business252(calendar_br), ql.Compounded).rate() 
    
    curveDAP.zeroRateValue = MethodType(zeroRateValue, curveDAP)
    curveDAP.enableExtrapolation()
    
    #%%
    dic_bucket = {1:'1D',30:'1M',60:'2M',90:'3M',180:'6M',\
                      270:'9M',360:'1Y',540:'1.5Y',720:'2Y',900:'2.5Y'} 
    dic_bucket.update({i*360:'{}Y'.format(i) for i in range(3,51)})
    
    data=[((today+i).to_date(), i, curveDAP.zeroRateValue(today+i), curveDAP.discount(calendar_br.adjust(today+i, ql.Following))) for i in dic_bucket.keys()]
    
    dfCurve = pd.DataFrame(data, columns=['tenor_date', 'tenor', 'curve_rate', 'discount_factor'])
    dfCurve.insert(0, 'curve_name', str_curvename)
    dfCurve.insert(0, 'date_reference', dt)
    
    dfDAP = df[['date_reference', 'curve_name', 'tenor_date', 'code_maturity', \
               'curve_rate', 'discount_factor']]
    result = pd.concat([dfCurve, dfDAP])
    result['business_day'] = result['tenor_date'].apply(lambda x: calendar_br.businessDaysBetween(today, ql.Date.from_date(x)))   
   
    #%% 
    str_sql = "DELETE FROM [risk].[interest_rate_curve] "+ \
              "WHERE curve_name = '{}' AND date_reference = '{:%Y-%m-%d}' ".format(str_curvename, dt)
    connection.execute(str_sql)
    
    result.to_sql("interest_rate_curve", connection, schema='risk', if_exists='append', index=False)
    print('{} - Inserted {} values for date {} : TABLE interest_rate_curve'.format(str_curvename, len(result), dt))
    
 
    
#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 3, 9)
    main(dt)
    
    # dtIni = ql.Date(1,1,2007)
    # dtIni = ql.Brazil(ql.Brazil().Exchange).adjust(dtIni)
    # while dtIni<= ql.Date(1, 1, 2010):  
    #     print(dtIni)
    #     main(dtIni.to_date())
    #     dtIni = ql.Brazil(ql.Brazil().Exchange).advance(dtIni, ql.Period(1, ql.Days))


