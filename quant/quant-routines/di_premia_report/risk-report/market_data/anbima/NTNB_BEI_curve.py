import pandas as pd
import numpy as np
import datetime

from a1db.a1sql import SQLConnection

import QuantLib as ql

def main(dt):
#%%
    connection = SQLConnection().get_connection()
    
    curves = ['NTNF Zero', 'NTNB Zero']    
    str_sql = f"""
        SELECT [curve_name],[tenor_date],[discount_factor]
      FROM [risk].[interest_rate_curve]
      WHERE curve_name in ('{"','".join(curves)}') AND tenor is null
      AND date_reference = '{dt:%Y-%m-%d}' 
      ORDER BY 2
        """
    df = pd.read_sql(str_sql, connection)
    del str_sql
    
    #%%
    calendar_br = ql.Brazil()
    today = ql.Date.from_date(dt)
    
    dic_curve={}
    for crv in curves:
        dts = [today]
        dfs = [1]
        for (_, dt_i, discf) in df[df['curve_name']==crv].values:
            dts.append(ql.Date.from_date(dt_i))
            dfs.append(discf)
            
        dic_curve[crv] = ql.DiscountCurve(dts, dfs, ql.Business252(calendar_br), \
                                       calendar_br, ql.LogLinear())
        dic_curve[crv].enableExtrapolation()
        
    #%%
    dts, dfs = [], []
    for (dt_i, df_i) in dic_curve['NTNB Zero'].nodes():
        dts.append(dt_i)
        df_pre = dic_curve['NTNF Zero'].discount(dt_i)
        dfs.append(df_pre/df_i)
        
    crv_BEI = ql.DiscountCurve(dts, dfs, ql.Business252(calendar_br), \
                                       calendar_br, ql.LogLinear())
    crv_BEI.enableExtrapolation()
    
    from types import MethodType
    def zeroRateValue(self, dt):
        return self.zeroRate(dt, ql.Business252(calendar_br), ql.Compounded).rate() 
    crv_BEI.zeroRateValue = MethodType(zeroRateValue, crv_BEI)
    #%%
    dic_bucket = {1:'1D',30:'1M',60:'2M',90:'3M',180:'6M',\
                      270:'9M',360:'1Y',540:'1.5Y',720:'2Y',900:'2.5Y'} 
    dic_bucket.update({i*360:'{}Y'.format(i) for i in range(3,51)})
    
    data = []
    for i in dic_bucket.keys():
        dt_i = calendar_br.adjust(today+i, ql.Following)
        data.append((dt_i.to_date(),
                     i,
                     crv_BEI.zeroRateValue(dt_i),
                     crv_BEI.discount(dt_i)))
        
    for (dt_i, _) in dic_curve['NTNB Zero'].nodes()[1:]:
        data.append((dt_i.to_date(),
                     np.nan,
                     crv_BEI.zeroRateValue(dt_i),
                     crv_BEI.discount(dt_i)))
    
    dfCurve = pd.DataFrame(data, columns=['tenor_date', 'tenor', 'curve_rate', 'discount_factor'])
    dfCurve.insert(0, 'curve_name', 'NTNB BEI')
    dfCurve.insert(0, 'date_reference', dt)
    dfCurve['code_maturity'] = np.nan
    dfCurve['business_day'] = dfCurve['tenor_date'].apply(lambda x: calendar_br.businessDaysBetween(today, ql.Date.from_date(x)))
    
    #%%
    
    str_sql = "DELETE FROM [risk].[interest_rate_curve] "+ \
              "WHERE curve_name = 'NTNB BEI' AND date_reference = '{:%Y-%m-%d}' ".format(dt)
    connection.execute(str_sql)
    
    dfCurve.to_sql("interest_rate_curve", connection, schema='risk', if_exists='append', index=False)
    print('NTNB BEI - Inserted {} values for date {} : TABLE interest_rate_curve'.format(len(dfCurve), dt))
    

#%%

if __name__ == "__main__":
    
    dt = datetime.date(2022, 3, 9)
    main(dt)
    
    # for dtIni in dtTemp:
    #     print(dtIni)
    #     main(dtIni.to_date())
    
    
    # dts = []
    # dtIni = ql.Date(20, 5, 2016)
    # dtIni = ql.Brazil().adjust(dtIni)
    # while dtIni<= ql.Date(1,1,2017):  
    #     print(dtIni)
    #     try:
    #         main(dtIni.to_date())
    #     except KeyError:
    #         dts += [dtIni]
    #     dtIni = ql.Brazil().advance(dtIni, ql.Period(1, ql.Days))
