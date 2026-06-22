import pandas as pd
import datetime
import sqlalchemy as sa
import QuantLib as ql

dt = datetime.date(2020, 8, 31)

#%%
def main(dt):
    engine = sa.create_engine('mssql+pyodbc://saprod:nhjmmn&^Yh%%^yhjU&@srvprod1.database.windows.net,1433/dbprod1?driver=SQL+Server+Native+Client+11.0')
    connection = engine.connect()
        
    str_sql = "SELECT date_reference, 'DAP Fut' as curve_name, " +\
            " [vencimento] as code_maturity, [preco_ajuste_atual] as PU "+\
            " FROM [b3].[ajuste_pregao] "+\
            " WHERE mercadoria = 'DAP - Cupom de DI x IPCA' "\
            "   AND date_reference = '{:%Y-%m-%d}'".format(dt)
    df = pd.read_sql(str_sql, connection)
    
    del str_sql
    
    #%%
    calendar_br = ql.Brazil()
    today = ql.Date.from_date(dt)
    # tomorrow = calendar_br.advance(today, ql.Period(1, ql.Days))
    
    df['tenor_date'] = df['code_maturity'].apply(lambda x: \
                             calendar_br.adjust(ql.Date(15, getattr(ql.IMM, x[0]), 2000+int(x[-2:])),\
                                                 ql.Following).to_date())
    df['discount_factor'] = df['PU']/100000 
    df['product_id'] = 'DAP' + df['code_maturity']
    
    df = df[df['tenor_date']>dt]
    df.sort_values('tenor_date', inplace=True)
    
    listDatesDAP = [ql.Date.from_date(i) for i in df['tenor_date']]
    listDatesDAP.insert(0, ql.Date.from_date(dt))
    
    listDiscountFactor = [1] + [i for i in df['discount_factor']]
    
    # if tomorrow != listDatesDAP[1]:
    #     listDiscountFactor.insert(1, (1+cdi)**(-1/252))
    #     listDatesDAP.insert(1, tomorrow)
    
    curveDAP = ql.DiscountCurve(listDatesDAP, listDiscountFactor,\
                               ql.Business252(calendar_br), \
                               calendar_br, ql.LogLinear())
    
    from types import MethodType
    def zeroRateValue(self, dt):
        return self.zeroRate(dt, ql.Business252(calendar_br), ql.Compounded).rate() 
    
    curveDAP.zeroRateValue = MethodType(zeroRateValue, curveDAP)
    curveDAP.enableExtrapolation()
    df['curve_rate'] = df['tenor_date'].apply(lambda x: curveDAP.zeroRateValue(ql.Date.from_date(x)))
    #%%
    dic_bucket = {1:'1D',30:'1M',60:'2M',90:'3M',180:'6M',\
                      270:'9M',360:'1Y',540:'1.5Y',720:'2Y',900:'2.5Y'} 
    dic_bucket.update({i*360:'{}Y'.format(i) for i in range(3,51)})
    
    data=[((today+i).to_date(), i, curveDAP.zeroRateValue(today+i), curveDAP.discount(calendar_br.adjust(today+i, ql.Following))) for i in dic_bucket.keys()]
    
    dfCurve = pd.DataFrame(data, columns=['tenor_date', 'tenor', 'curve_rate', 'discount_factor'])
    dfCurve.insert(0, 'curve_name', 'DAP Fut')
    dfCurve.insert(0, 'date_reference', dt)
    
    dfDAP = df[['date_reference', 'curve_name', 'tenor_date', 'code_maturity', \
               'curve_rate', 'discount_factor']]
    result = pd.concat([dfCurve, dfDAP])
    result['business_day'] = result['tenor_date'].apply(lambda x: calendar_br.businessDaysBetween(today, ql.Date.from_date(x)))
    
    #%%
    str_sql = "DELETE price FROM [middle].[product_price] price "+\
                "INNER JOIN [middle].[product] prod "+\
                "ON price.product_id = prod.id "+\
                "WHERE prod.[lote45_product_class]='DAP Future' AND "+\
                "price.date_reference = '{:%Y-%m-%d}' ".format(dt)
    connection.execute(str_sql)
    
    dfProductPrice = df[['date_reference', 'product_id', 'curve_rate', 'PU']].\
                        rename(columns={'curve_rate': 'rate', 'PU':'price'})
     
    dfProductPrice.to_sql("product_price", engine, schema='middle', if_exists='append', index=False)
    print('DAP Fut - Inserted {} values for date {} : TABLE product_price'.format(len(dfProductPrice), dt))
    
    
    str_sql = "DELETE FROM [risk].[interest_rate_curve] "+ \
              "WHERE curve_name = 'DAP Fut' AND date_reference = '{:%Y-%m-%d}' ".format(dt)
    connection.execute(str_sql)
    
    result.to_sql("interest_rate_curve", engine, schema='risk', if_exists='append', index=False)
    print('DAP Fut - Inserted {} values for date {} : TABLE interest_rate_curve'.format(len(result), dt))
    
    connection.close()
    
#%%
if __name__ == "__main__":
    
    # main(dt)
    
    dtIni = ql.Date(1,4,2020)
    dtIni = ql.Brazil(ql.Brazil().Exchange).adjust(dtIni)
    while dtIni<= ql.Date(15, 9, 2020):    
        main(dtIni.to_date())
        dtIni = ql.Brazil(ql.Brazil().Exchange).advance(dtIni, ql.Period(1, ql.Days))


        
    
    