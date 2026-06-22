import pyodbc 
import pandas as pd
from base_sql import SQLConnection

class SqlClass(SQLConnection):
    def __init__(self):
        super().__init__()
    
    def read_predi(self, tenor, start_date, end_date):
        query = '''
            SELECT
                [date_reference]
                ,[curve_rate]*100 as 'value'
            FROM [risk].[interest_rate_curve]
            where
                tenor='%s'
                AND curve_name = 'DI Fut'
                AND date_reference >= '%s'
                AND date_reference <= '%s'
            ORDER BY date_reference
        ''' % (tenor, start_date, end_date)

        conn = self.get_connection()
        data = pd.read_sql(query, conn)

        
        return data.values

    def read_dap_bei(self, start_date, end_date):
        query = '''
            SELECT
                [date_reference],
                [tenor],
                [curve_rate]
            FROM [risk].[interest_rate_curve]
            WHERE
                curve_name='DAP BEI' AND
                tenor in (180, 360, 540, 720) AND
                date_reference >= '%s' AND
                date_reference <= '%s'
            ORDER BY date_reference
        ''' % (start_date, end_date)
        # cursor = self.get_cursor()
        # cursor.execute( query, [start_date, end_date] )
        # raw_data = cursor.fetchall()
        # df = pd.DataFrame(
        #     [ list(x) for x in raw_data ],
        #     columns=['date', 'tenor', 'curve_rate']
        # )
        # df = df.pivot(
        #     index='date',
        #     columns='tenor',
        #     values='curve_rate'
        # ).rename(columns={
        #     180: 'DAPBEI6M',
        #     360: 'DAPBEI1Y',
        #     540: 'DAPBEI18M',
        #     720: 'DAPBEI2Y'
        # }) * 100

        conn = self.get_connection()
        data = pd.read_sql(query, conn)
        data = data.rename(columns={'date_reference':'date'})
        data = data.pivot(
             index='date',
             columns='tenor',
             values='curve_rate'
        )
        data = data.rename(columns={
             180: 'DAPBEI6M',
             360: 'DAPBEI1Y',
             540: 'DAPBEI18M',
             720: 'DAPBEI2Y'
         }) * 100

        return data

    def read_selic_expectation(self, start_date, end_date):
        query = '''
            SELECT
                [date_reference],
                [product_id],
                [rate]
            FROM [middle].[product_price]
            WHERE
                product_id = 'SELIC TARGET' AND
                date_reference >= '%s' AND
                date_reference <= '%s'
            order by date_reference
        ''' % (start_date, end_date)
        # cursor = self.get_cursor()
        # cursor.execute( query, [start_date, end_date] )
        # raw_data = cursor.fetchall()
        # df = pd.DataFrame(
        #     [ list(x) for x in raw_data ],
        #     columns=['date', 'variable', 'value']
        # ).pivot(
        #     index='date',
        #     columns='variable',
        #     values='value'
        # ).rename(
        #     columns={
        #         'SELIC TARGET': 'BZSTSETA Index'
        #     }
        # )
        conn = self.get_connection()
        data = pd.read_sql(query, conn)
        data = data.rename(columns={'date_reference':'date','product_id':'variable', 'rate':'value'})
        data = data.pivot(
             index='date',
             columns='variable',
             values='value'
        )

        data = data.rename(
             columns={
                 'SELIC TARGET': 'BZSTSETA Index'
             }
        )

        return data

    def read_cdi(self, start_date, end_date):
        query = '''
            SELECT
                b.[date_reference],
                b.[value]
            FROM [quant].[time_series] as a
            JOIN [quant].[time_series_value] as b
            ON a.[id] = b.[series_id]
            WHERE
                a.[entity_id] = 'CDI' AND
                b.date_reference >= '%s' AND
                b.date_reference <= '%s'
            order by b.date_reference
        ''' % (start_date, end_date)
        
        conn = self.get_connection()
        data = pd.read_sql(query, conn)
        data = data.rename(columns={'date_reference':'date','value':'CDI'})
        data = data.set_index('date')

        return data

    def read_ipca_focus_expectation(self, start_date, end_date):
        query = '''
            SELECT [type], [date], [value]
            FROM [bcb].[modulo_focus_series] as a
            JOIN [bcb].[modulo_focus_value] as b
            ON a.[id]=b.[series_id]
            WHERE indicator='IPCA' AND 
                [date]>= '%s' AND
                [date]<= '%s' AND                
        ''' % (start_date, end_date)
        query = query +"""
                        [type] like '%DU'"""
        
        # raw_data = pd.DataFrame(
        #     [list(x) for x in cursor.fetchall()],
        #     columns=['type', 'date', 'value']
        # )
        # raw_data['date'] = [pd.Timestamp(x) for x in raw_data['date']]
        # raw_data['type'] = [int(x.replace('DU', '')) for x in raw_data['type']]
        # if len(raw_data.index) == 0:
        #     raise Exception("Something went wrong in the db. Empty data for ipca focus from 'modulo focus'")
        #     return pd.DataFrame()
        # df = raw_data.pivot(
        #     index='date',
        #     columns='type',
        #     values='value'
        # ).rename(
        #     columns={
        #         126: 'IPCA Focus 6m',
        #         252: 'IPCA Focus 1y',
        #         378: 'IPCA Focus 18m',
        #         504: 'IPCA Focus 2y',
        #     }
        # )

        conn = self.get_connection()
        data = pd.read_sql(query, conn)
        data['date'] = [pd.Timestamp(x) for x in data['date']]
        data['type'] = [int(x.replace('DU', '')) for x in data['type']]
        
        df = data.pivot(
            index='date',
            columns='type',
            values='value'
        ).rename(
            columns={
                126: 'IPCA Focus 6m',
                252: 'IPCA Focus 1y',
                378: 'IPCA Focus 18m',
                504: 'IPCA Focus 2y',
            }
        )

        return df