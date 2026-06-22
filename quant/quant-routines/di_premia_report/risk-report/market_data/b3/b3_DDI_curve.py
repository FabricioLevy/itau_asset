import pandas as pd
import datetime
import QuantLib as ql

from a1db.a1sql import SQLConnection


#%%
def main(dt):
    #%%# getting data from DB - Ajuste Pregão
    str_curvename = 'USD BR' 
    
    today = ql.Date.from_date(dt)
    tomorrow = ql.Brazil(ql.Brazil().Exchange).advance(today, ql.Period(1, ql.Days))
    codes = ['F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z']
    if ql.Brazil(ql.Brazil().Exchange).isEndOfMonth(today):
        nextMonth = ql.Brazil(ql.Brazil().Exchange).advance(today, ql.Period(2,ql.Months), ql.ModifiedFollowing)
        code = "{}{:%y}".format(codes[nextMonth.month()-1], nextMonth.to_date())
    else:
        nextMonth = ql.Brazil(ql.Brazil().Exchange).advance(today, ql.Period(1,ql.Months), ql.ModifiedFollowing)
        code = "{}{:%y}".format(codes[nextMonth.month()-1], nextMonth.to_date())
    dt1 = ql.Brazil(ql.Brazil().Exchange).adjust(ql.Date(1,nextMonth.month(), nextMonth.year()))
    
    nextMonth = ql.Brazil(ql.Brazil().Exchange).advance(nextMonth, ql.Period(1,ql.Months), ql.ModifiedFollowing)
    code2 = "{}{:%y}".format(codes[nextMonth.month()-1], nextMonth.to_date())
    dt2 = ql.Brazil(ql.Brazil().Exchange).adjust(ql.Date(1,nextMonth.month(), nextMonth.year()))
    
    dolfut1_code = 'DOL' + code
    dolfut2_code = 'DOL' + code2
    di1_code = 'DI1' + code
    di2_code = 'DI1' + code2
    
    connection = SQLConnection().get_connection()
    
    str_sql = """
    SELECT [date_reference], '{}' as curve_name, p.[product_type], pp.product_id,
    [rate],[price], p.date_maturity as tenor_date
  FROM [middle].[product_price] pp inner join middle.product p
  ON pp.product_id = p.id
  where date_reference = '{:%Y-%m-%d}' and p.product_type in ('DDI Future', 'FRC')
order by p.[product_type], p.date_maturity
    """
    str_sql = str_sql.format(str_curvename, dt)
    df = pd.read_sql(str_sql, connection)
    
    str_sql="SELECT [product_id],[price] FROM [middle].[product_price] " +\
            "WHERE date_reference = '{0:%Y-%m-%d}' and product_id in ('DOL{1}', 'DI1{1}', 'CASADO', 'DOL{2}', 'DI1{2}') ".format(dt, code, code2)
    dfFut = pd.read_sql(str_sql, connection, index_col='product_id')  

    del str_sql
    
    #%%
    calendar_br = ql.Brazil()
    
    dfFRC = df[df['product_type'] == 'FRC'].copy()
    dfFRC['code_maturity'] = dfFRC['product_id'].str[3:]
    dfFRC = dfFRC[dfFRC['tenor_date']>dt]
    dfFRC['rate'] /= 100
    dfDDI = df[df['product_type'] == 'DDI Future'].copy()  
    del df

    
    casado = dfFut.loc['CASADO', 'price']
    dolfut1 = dfFut.loc[dolfut1_code, 'price']
    
    # fct_Pre = 100000/dfFut.loc[di1_code,'price']    
    fct_Pre1 = 100_000/dfFut.loc[di1_code,'price']
    fct_CupomCambial1=(1-casado/dolfut1)*fct_Pre1
    
    if ql.Brazil(ql.Brazil().Exchange).isEndOfMonth(tomorrow):     
        dolfut2 = dfFut.loc[dolfut2_code, 'price']
        rolagem = dolfut2 - dolfut1
        fct_Pre12 = 100_000/dfFut.loc[di2_code,'price'] / fct_Pre1
        fct_CupomCambial12=(1-rolagem/dolfut2)*fct_Pre12
        fct_CupomCambial = fct_CupomCambial1 * fct_CupomCambial12
        dt_term = dt2        
    else:       
        fct_CupomCambial = (1-casado/dolfut1)*fct_Pre1
        dt_term = dt1
    rt_CupomCambial = (fct_CupomCambial-1)*(360/(dt_term-today))    
    
    dfFRC['discount_factor'] = 1/(1+dfFRC['rate']*((dfFRC['tenor_date']-dt_term.to_date()).dt.days/360))/fct_CupomCambial
    dfFRC['zero_rate'] = (1/dfFRC['discount_factor']-1)*(360/((dfFRC['tenor_date']-dt).dt.days))
    
    # insert the 1st node
    dfFRC = dfFRC.append({'date_reference':dt,
                    'curve_name':'USD BR',
                    'code_maturity':code,
                    'rate':0, 
                    'tenor_date':dt_term.to_date(),
                    'product_id':'DOLFUT1', 
                    'discount_factor':1/fct_CupomCambial,
                    'zero_rate':rt_CupomCambial}, ignore_index=True)
    dfFRC.sort_values('tenor_date', inplace=True)
    
    dates_CC = [today] + [ql.Date.from_date(i) for i in dfFRC['tenor_date']]
    rates_CC = [dfFRC['zero_rate'].iloc[0]] + [i for i in dfFRC['zero_rate']]
    
    curve_CC = ql.ZeroCurve(dates_CC, rates_CC, ql.Actual360(), calendar_br)
    curve_CC.enableExtrapolation()
    
    from types import MethodType
    def zeroRateValue(self, dt):
        return self.zeroRate(dt, ql.Actual360(), ql.Compounded).rate() 
    
    curve_CC.zeroRateValue = MethodType(zeroRateValue, curve_CC)
    curve_CC.enableExtrapolation()
    
    #%%
    #PV01 calculation
    spot = (dolfut1 - casado)/1000
    dfDDI['value'] = spot * 0.5 / 10000 * (dfDDI['tenor_date']-dt).dt.days/360 * \
                        dfDDI['price'] / (1+dfDDI['tenor_date'].apply(lambda x: curve_CC.zeroRateValue(ql.Date.from_date(x))))


    #%%
    dic_bucket = {1:'1D',30:'1M',60:'2M',90:'3M',180:'6M',\
                      270:'9M',360:'1Y',540:'1.5Y',720:'2Y',900:'2.5Y'} 
    dic_bucket.update({i*360:'{}Y'.format(i) for i in range(3,51)})
    
    data=[((today+i).to_date(), i, curve_CC.zeroRateValue(today+i), curve_CC.discount(calendar_br.adjust(today+i, ql.Following))) for i in dic_bucket.keys()]
    
    dfCurve = pd.DataFrame(data, columns=['tenor_date', 'tenor', 'curve_rate', 'discount_factor'])
    dfCurve.insert(0, 'curve_name', 'USD BR')
    dfCurve.insert(0, 'date_reference', dt)
    
    dfCC = dfFRC[['date_reference', 'curve_name', 'tenor_date', 'code_maturity', \
               'zero_rate', 'discount_factor']].rename({'zero_rate':'curve_rate'}, axis=1)
    result = pd.concat([dfCurve, dfCC])
    result['business_day'] = result['tenor_date'].apply(lambda x: calendar_br.businessDaysBetween(today, ql.Date.from_date(x)))
    
    #%%   
    str_sql = "DELETE FROM [risk].[interest_rate_curve] "+ \
              "WHERE curve_name = 'USD BR' AND date_reference = '{:%Y-%m-%d}' ".format(dt)
    connection.execute(str_sql)
    
    result.to_sql("interest_rate_curve", connection, schema='risk', if_exists='append', index=False)
    print('USD BR - Inserted {} values for date {} : TABLE interest_rate_curve'.format(len(result), dt))
    
    #%%
    str_sql = "DELETE s FROM [risk].[product_sensitivity] s "+\
                "INNER JOIN [middle].[product] prod "+\
                "ON s.product_id = prod.id "+\
                "WHERE prod.[lote45_product_class]='DDI Future' AND "+\
                "s.date_reference = '{:%Y-%m-%d}'  AND s.sensitivity = 'PV01'".format(dt)
    connection.execute(str_sql)    
    dfDDI['sensitivity'] = 'PV01'
    dfDDI[['date_reference','product_id','sensitivity','value']].\
        to_sql("product_sensitivity", connection, schema='risk', if_exists='append', index=False)
    print('DDI Future - Inserted {} values for date {} : TABLE product_sensitivity'.format(len(dfDDI), dt))
 
    
#%%
if __name__ == "__main__":
    
    dt = datetime.date(2011, 11, 29)
    main(dt)
    
    # dtIni = ql.Date(30, 10, 2008)
    # dtIni = ql.Brazil(ql.Brazil().Exchange).adjust(dtIni)
    # while dtIni<= ql.Date(1, 1, 2009):  
    #     print(dtIni)
    #     main(dtIni.to_date())
    #     dtIni = ql.Brazil(ql.Brazil().Exchange).advance(dtIni, ql.Period(1, ql.Days))

