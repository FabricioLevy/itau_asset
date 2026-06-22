from base_sql import SQLConnection
import pandas as pd

class SqlClass(SQLConnection):
    def __init__(self):
        super().__init__()

    def read_inflation_target(self):
        query = """
            SELECT 
                [date_reference],
                [date_publish],
                [rate_target],
                [rate_tolerance],
                [rate_realized],
                [obs]
            FROM [research].[inflation_target_rate]
            WHERE [country]='BRL'
        """
        conn = self.get_connection()
        df = pd.read_sql(query, conn)
        
        df['date_reference'] = [
            pd.Timestamp(x)
            for x
            in df['date_reference']
        ]
        df['date_publish'] = [
            pd.Timestamp(x)
            for x
            in df['date_publish']
        ]        
        return df

    def read_time_series(self, name):
        query = """
            SELECT [date_reference], [value]
            FROM [quant].[time_series] as a
            JOIN [quant].[time_series_value] as b
            ON a.id=b.series_id
            WHERE a.[name]='%s'
        """ % (name)
        conn = self.get_connection()
        data = pd.read_sql(query, conn)

        data = data.set_index('date_reference')
        data.index = [pd.Timestamp(x) for x in data.index]
        return data