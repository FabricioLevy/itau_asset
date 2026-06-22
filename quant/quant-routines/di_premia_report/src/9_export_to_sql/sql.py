import pyodbc 
import math
import os
from base_sql import SQLConnection
import pandas as pd

class SqlClass(SQLConnection):
    def __init__(self):
        super().__init__()
        self.n_batch = 20

    def get_or_create_time_series(self, info):
        query = '''
            SET NOCOUNT ON
            DECLARE @entity_id int
            DECLARE @date_start DATE
            IF NOT EXISTS (
                SELECT id
                FROM [quant].[time_series_entity]
                WHERE id='%s'
            ) BEGIN
                INSERT INTO [quant].[time_series_entity] 
                ([id],[refinitiv_symbol],[bloomberg_symbol])
                VALUES ('%s', NULL, '%s');
            END
            IF NOT EXISTS (
                SELECT id
                FROM [quant].[time_series]
                WHERE entity_id='%s' AND source='di premia'
            ) BEGIN
                INSERT INTO [quant].[time_series]
                ([entity_id],[name],[source],[field],[update_frequency])
                VALUES (
                    '%s', '%s', 'di premia', '-', 'manual'
                )
            END
            SELECT id
            FROM [quant].[time_series]
            WHERE entity_id='%s' AND source='di premia';
            COMMIT
        ''' % (
            info['entity_id'],
            info['entity_id'],
            '?'+info['entity_id'],
            info['entity_id'],
            info['entity_id'],
            info['entity_id'],
            info['entity_id']
        )
        # cursor = self.get_cursor('prod')
        # cursor.execute( 
        #     query,
        #     [ 
        #         info['entity_id'],
        #         info['entity_id'],
        #         '?'+info['entity_id'],
        #         info['entity_id'],
        #         info['entity_id'],
        #         info['entity_id'],
        #         info['entity_id']
        #     ]
        # )
        # series_id = cursor.fetchall()[0][0]

        conn = self.get_connection()
        data = pd.read_sql(query, conn)
        series_id = data.values[0][0]        
        return series_id

