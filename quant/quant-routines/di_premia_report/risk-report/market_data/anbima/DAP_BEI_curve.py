import pandas as pd
import numpy as np
import datetime
import QuantLib as ql

from a1db.a1sql import SQLConnection


def main(dt):
#%%
    connection = SQLConnection().get_connection()
    str_sql = """
        SELECT [curve_name],[tenor_date],[discount_factor]
      FROM [risk].[interest_rate_curve]
      WHERE curve_name in ('DI Fut', 'DAP Fut') AND tenor is null
      AND date_reference = '{:%Y-%m-%d}' 
      ORDER BY 2
        """
    str_sql = str_sql.format(dt)
    df = pd.read_sql(str_sql, connection)
    
    str_sql = """
        SELECT [date_reference] ,[price]
        FROM [middle].[product_price]
        where product_id = 'IPCA PRT'
        and date_reference between dateadd(YEAR, -1, '{0:%Y-%m-%d}') and '{0:%Y-%m-%d}'
    """
    str_sql = str_sql.format(dt)
    dfIPCA = pd.read_sql(str_sql, connection, index_col='date_reference')
    
    str_sql = """
    SELECT ts.id, ts.name, ts.field
                FROM [quant].[time_series] ts 
            	INNER JOIN [quant].[time_series_entity] tse ON ts.entity_id = tse.id
            	INNER JOIN quant.time_series_grouping tsging on tsging.series_id = ts.id
            	INNER JOIN quant.time_series_group tsg ON tsg.id = tsging.group_id
               WHERE  tsg.[name]='BEI' AND tsg.subtype = 'DAP_BEI'
    """
    dfBEI_ts = pd.read_sql(str_sql, connection)
    del str_sql
    
    #%%
    calendar_br = ql.Brazil()
    today = ql.Date.from_date(dt)
    
    dic_curve={}
    for crv in df['curve_name'].unique():
        dts = [today]
        dfs = [1]
        for (_, dt_i, discf) in df[df['curve_name']==crv].values:
            dts.append(ql.Date.from_date(dt_i))
            dfs.append(discf)
            
        dic_curve[crv] = ql.DiscountCurve(dts, dfs, ql.Business252(calendar_br), \
                                       calendar_br, ql.LogLinear())
        dic_curve[crv].enableExtrapolation()
        
    #%%
    dates = sorted(set([dt_i for (dt_i, _) in dic_curve['DI Fut'].nodes()] + \
                       [calendar_br.adjust(dt_i) for (dt_i, _) in dic_curve['DAP Fut'].nodes()] ))
    dts, dfs = [], []
    
    for dt_i in dates:
        dts.append(dt_i)
        df_pre = dic_curve['DI Fut'].discount(dt_i)
        df_dap = dic_curve['DAP Fut'].discount(dt_i)
        dfs.append(df_pre/df_dap)
        
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
        
    for (dt_i, _) in crv_BEI.nodes()[1:]:
        data.append((dt_i.to_date(),
                     np.nan,
                     crv_BEI.zeroRateValue(dt_i),
                     crv_BEI.discount(dt_i)))
    
    dfCurve = pd.DataFrame(data, columns=['tenor_date', 'tenor', 'curve_rate', 'discount_factor'])
    dfCurve.insert(0, 'curve_name', 'DAP BEI')
    dfCurve.insert(0, 'date_reference', dt)
    dfCurve['code_maturity'] = np.nan
    dfCurve['business_day'] = dfCurve['tenor_date'].apply(lambda x: calendar_br.businessDaysBetween(today, ql.Date.from_date(x)))
    
    #%%
    str_sql = "DELETE FROM [risk].[interest_rate_curve] "+ \
              "WHERE curve_name = 'DAP BEI' AND date_reference = '{:%Y-%m-%d}' ".format(dt)
    connection.execute(str_sql)
    
    dfCurve.to_sql("interest_rate_curve", connection, schema='risk', if_exists='append', index=False)
    print('DAP BEI - Inserted {} values for date {} : TABLE interest_rate_curve'.format(len(dfCurve), dt))
    
    #%%
    df_tsv_output = pd.DataFrame(columns=['series_id','date_reference','value'])
    for (ts_id, _, y) in dfBEI_ts.values:
        y = int(y)
        dt_prt_ini = min(ql.Date(15, 1, y), today)
        dt_ini = max(ql.Date(15, 1, y), today)
        dt_end = ql.Date(15, 1, y+1)
        if y == dt.year:
            prt_ini = dfIPCA.loc[calendar_br.adjust(dt_prt_ini).to_date(), 'price']
            prt_end = dfIPCA.loc[dt, 'price']
            ytd_inflation = prt_end/prt_ini
            bei_eff = crv_BEI.forwardRate(dt_ini, dt_end, ql.Business252(calendar_br), ql.Compounded).compoundFactor(dt_ini, dt_end)
            bei = (ytd_inflation * bei_eff) - 1  
            df_tsv_output = df_tsv_output.append({'series_id':ts_id, 
                                  'date_reference':dt, 
                                  'value': bei}, ignore_index=True)
        elif y > dt.year:
            # r = crv_BEI.forwardRate(dt_ini, dt_end, ql.Business252(calendar_br), ql.Compounded).rate()
            bei = crv_BEI.forwardRate(dt_ini, dt_end, ql.Business252(calendar_br), ql.Compounded).compoundFactor(dt_ini, dt_end)-1
            # print(r, x, r-x)
            df_tsv_output = df_tsv_output.append({'series_id':ts_id, 
                                  'date_reference':dt, 
                                  'value': bei}, ignore_index=True)
    #%%
    str_sql = """
                DELETE FROM [quant].[time_series_value]
                WHERE [series_id] in ({}) AND date_reference = '{:%Y-%m-%d}' 
              """  
    ids = ','.join([str(i) for i in df_tsv_output['series_id'].values])
    connection.execute(str_sql.format(ids, dt))
    
    df_tsv_output.to_sql("time_series_value", connection, schema='quant', if_exists='append', index=False)
    print('DAP BEI - Inserted {} values for date {} : TABLE time_series_value'.format(len(df_tsv_output), dt))
    
    

#%%

if __name__ == "__main__":
    
    dt = datetime.date(2022, 3, 9)
    main(dt)
    
        
