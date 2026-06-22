import pandas as pd
import datetime
import QuantLib as ql

import sys
sys.path.insert(1, '..')
import fund_utils as fu


#%%
def main(dt): 
    #%%
    
    today = ql.Date.from_date(dt)
    if ql.Brazil(ql.Brazil.Exchange).endOfMonth(today) == today:
        print('!!!!!!\n{}\nEnd of Month: Attention on DDI and DOLFUT expiring!\n!!!!!!'.format(__file__))
    
        _, connection = fu.get_DB_conn('prod')    
    
        str_sql = """
        SELECT bo_ptax.[date_reference], bo_ptax.trading_desk, bo_ptax.lote45_product,bo_ptax.book, ISNULL(deltaSpot,0)-deltaPtax as deltaTotal
        FROM
	       (SELECT [date_reference],[trading_desk],[lote45_product],[book], [value] as deltaPtax
        	FROM [lote45].[book_overview] 
	        WHERE date_reference = '{0:%Y-%m-%d}' AND measure='USDBRLPtax') as bo_ptax
        LEFT JOIN
	       (SELECT [date_reference],[trading_desk],[lote45_product],[book], [value] as deltaSpot
	       FROM [lote45].[book_overview] 
	       WHERE date_reference = '{0:%Y-%m-%d}' AND measure='USDBRLSpot') as bo_spot
       ON bo_spot.trading_desk = bo_ptax.trading_desk 
          and bo_spot.book = bo_ptax.book 
          and bo_spot.[lote45_product] = bo_ptax.[lote45_product]
        """
        str_sql = str_sql.format(dt)
        df = pd.read_sql(str_sql, connection)
        
        str_sql = """
            UPDATE [lote45].[primitive] 
                SET [delta] = {}, eq_position = {}
            WHERE date_reference = '{:%Y-%m-%d}' AND 
            trading_desk='{}' and 
            lote45_product='{}' and 
            book='{}' and 
            primitive = 'USDBRLSpot'        
        """
        str_sql_insert = """
            INSERT INTO [lote45].[primitive] ([date_reference],[trading_desk]
                                              ,[lote45_product],[primitive]
                                              ,[primitive_class],[book]
                                              ,[bucket],[eq_position],[delta])
            VALUES ('{:%Y-%m-%d}', '{}', '{}', 'USDBRLSpot'
                    ,'FX', '{}', 0, {}, {}) 
        """
        count_insert = 0
        for (dt_ref, fund, prod, book, delta) in df[['date_reference', 'trading_desk', 'lote45_product', 'book', 'deltaTotal']].values:
            str_sql_update = str_sql.format(delta, delta, dt, fund, prod, book)
            ret = connection.execute(str_sql_update)
            if ret.rowcount == 0:
                s = str_sql_insert.format(dt, fund, prod, book, delta, delta)
                count_insert += 1
                ret = connection.execute(s)

        print("{:%d-%b-%y} - Update {} rows ({} were insertions) in table Primitives due to expiring PTAX products".format(dt, len(df), count_insert))
        connection.close()
        del str_sql, connection

#%%        
if __name__ == "__main__":
    
    dt = datetime.date(2021, 6, 10)
    main(dt)        