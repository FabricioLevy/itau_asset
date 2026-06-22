import datetime
import pandas as pd
import QuantLib as ql

from a1db.a1sql import SQLConnection

import curve_db

#%%    
def date2code(dt):
    codes = ['F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z']
    return "{}{:%y}".format(codes[dt.month-1], dt) 


def main(dt):
#%%    
    if ql.Brazil(ql.Brazil().Exchange).isHoliday(ql.Date.from_date(dt)):
        connection = SQLConnection().get_connection()
    
        today = ql.Date.from_date(dt)
        dt_adj = ql.Brazil(ql.Brazil().Exchange).adjust(today, ql.Preceding).to_date()
        
        for curve_name, code_prod in zip(['DI Fut', 'DAP Fut', 'USD BR'], ['DI1', 'DAP', 'FRC']):
                
            crv = curve_db.get_curve(dt_adj, curve_name)
            crv.enableExtrapolation()
            cal = crv.calendar()
            
            dic_bucket = {1:'1D',5:'5W',30:'1M',60:'2M',90:'3M',180:'6M',\
                              270:'9M',360:'1Y',540:'1.5Y',720:'2Y',900:'2.5Y'} 
            dic_bucket.update({i*360:'{}Y'.format(i) for i in range(3,51)})
            
            discfactor_1d = crv.discount(today)
            data=[((today+i).to_date(), 
                   i,
                   crv.forwardRateValue(today,today+i), 
                   crv.discount(cal.adjust(today+i, ql.Following))/discfactor_1d) 
                  for i in dic_bucket.keys()]
            ##################################
            if code_prod == 'FRC':
                data=[((today+i).to_date(), 
                       i,
                       crv.zeroRateValue(ql.Date.from_date(dt_adj)+i), 
                       crv.discount(cal.adjust(ql.Date.from_date(dt_adj)+i, ql.Following)))
                      for i in dic_bucket.keys()]
            ##################################
            
            dfCurve = pd.DataFrame(data, columns=['tenor_date', 'tenor', 'curve_rate', 'discount_factor'])
            dfCurve.insert(0, 'curve_name', curve_name)
            dfCurve.insert(0, 'date_reference', dt)
            
            
            data_nodes=[(dt, 
                         curve_name, 
                         dt_i.to_date(),
                         '{}{}'.format(code_prod, date2code(dt_i.to_date())), 
                         crv.forwardRateValue(today, dt_i), 
                         crv.discount(dt_i)/discfactor_1d) 
                        for (dt_i, _) in crv.nodes() if dt_i>today]
            
            ##################################
            if code_prod == 'FRC':
                data_nodes=[(dt, 
                         curve_name, 
                         dt_i.to_date(),
                         '{}{}'.format(code_prod, date2code(dt_i.to_date())), 
                         crv.zeroRateValue(dt_i), 
                         crv.discount(dt_i)) 
                        for (dt_i, _) in crv.nodes() if dt_i>today]
            ##################################
            
            dfNodes= pd.DataFrame(data_nodes, columns=['date_reference', 'curve_name', 'tenor_date', 'code_maturity', 'curve_rate', 'discount_factor'])
            result = pd.concat([dfCurve, dfNodes])
            result['business_day'] = result['tenor_date'].apply(lambda x: cal.businessDaysBetween(today, ql.Date.from_date(x)))   
               
            str_sql = "DELETE FROM [risk].[interest_rate_curve] "+ \
                      "WHERE curve_name = '{}' AND date_reference = '{:%Y-%m-%d}' ".format(curve_name, dt)
            connection.execute(str_sql)
            
            result.to_sql("interest_rate_curve", connection, schema='risk', if_exists='append', index=False)
            print('{} - Inserted {} values for date {} : TABLE interest_rate_curve'.format(curve_name, len(result), dt))
            
        
    else:
        print('{:%d-%b-%Y} is not a B3 holiday!'.format(dt))
        
#%%
if __name__ == "__main__":
        
    dt=datetime.date(2022, 3, 9)
    main(dt)
        
                
    # cal_b3 = ql.Brazil(ql.Brazil().Exchange)
    # dtIni = ql.Date(1, 1, 2009)
    # dtIni = ql.Brazil().adjust(dtIni)
    # while dtIni<= ql.Date(1,2,2021):
    #     if cal_b3.isHoliday(dtIni):
    #         if not ql.Brazil().isHoliday(dtIni):
    #             print(dtIni)
    #             main(dtIni.to_date())
    #     dtIni = ql.Brazil().advance(dtIni, ql.Period(1, ql.Days))

