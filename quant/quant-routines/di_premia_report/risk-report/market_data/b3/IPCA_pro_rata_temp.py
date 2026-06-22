import pandas as pd
import datetime
import QuantLib as ql

from a1db.a1sql import SQLConnection


def IPCA_dates(qlDt):
    
    lastIPCA = ql.Date(15, qlDt.month(), qlDt.year())
    if qlDt.dayOfMonth() < 15:
        nextIPCA = ql.Brazil().adjust(lastIPCA)
        lastIPCA = ql.Brazil().advance(lastIPCA, ql.Period(-1, ql.Months))
    else:
        nextIPCA = ql.Brazil().advance(lastIPCA, ql.Period(1, ql.Months))
        lastIPCA = ql.Brazil().adjust(lastIPCA)
    return (lastIPCA, nextIPCA)
    

def save_IPCA_prt(dt):
    #%%
    today = ql.Date.from_date(dt)
    calendar_br = ql.Brazil()
    dt_last_IPCA, dt_next_IPCA = IPCA_dates(today)
    
    connection = SQLConnection().get_connection()
    
    str_sql = "SELECT [date_reference],[price] "+\
                " FROM [middle].[product_price] " +\
                " WHERE product_id = 'IPCA' " +\
                " AND date_reference = '{:%Y-%m-%d}' ".format(dt_last_IPCA.to_date()) +\
                "ORDER BY date_reference DESC"
    dfTemp = pd.read_sql(str_sql, connection, index_col='date_reference')
    if len (dfTemp) == 1:
        last_IPCA = dfTemp.loc[dt_last_IPCA.to_date(), 'price']
    else:
        raise Exception("Error: there is no IPCA for date '{:%Y-%m-%d}' ".format(dt_last_IPCA.to_date()))
    
    # str_sql = "SELECT TOP 1 [date_reference],[rate] "+\
    #             " FROM [middle].[product_price] " +\
    #             " WHERE product_id = 'IPCA PROJ' " +\
    #             " AND date_reference BETWEEN '{:%Y-%m-%d}' AND'{:%Y-%m-%d}' ".format(dt_last_IPCA.to_date(), dt) +\
    #             "ORDER BY date_reference DESC"
                
    if dt_last_IPCA.to_date() == dt:
        proj_IPCA = 0
    else:
        str_sql = """
        SELECT [date_reference],[indice] /100 as ipca_proj
        FROM [anbima].[VNA]
        WHERE date_reference = '{:%Y-%m-%d}' AND codigo_selic = 760199
        """  
        str_sql = str_sql.format(dt)
        dfTemp = pd.read_sql(str_sql, connection, index_col='date_reference')
        if len (dfTemp) == 1:
            proj_IPCA = dfTemp.loc[dt,'ipca_proj']
        else:
            raise Exception("Error: there is no IPCA PROJ for date '{:%Y-%m-%d}' ".format(dt_last_IPCA.to_date()))

    du_dts_IPCA = calendar_br.businessDaysBetween(dt_last_IPCA, dt_next_IPCA)
    du = calendar_br.businessDaysBetween(dt_last_IPCA, today)
    pro_rata =  round(last_IPCA * (1+proj_IPCA)**(du/du_dts_IPCA), 6)
    
    connection.execute("DELETE FROM middle.product_price " +\
                      "WHERE product_price.product_id='IPCA PRT' AND date_reference='{:%Y-%m-%d}'".format(dt))
    
    connection.execute("INSERT INTO middle.product_price (date_reference, product_id, rate, price) " +\
                      "VALUES ('{:%Y-%m-%d}', 'IPCA PRT', {}, {})".format(dt, pro_rata, pro_rata))
    
    print('IPCA PRT: {:%Y-%m-%d} {:2.6f}'.format(dt, pro_rata))

    
#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 3, 9)
    save_IPCA_prt(dt)
    
