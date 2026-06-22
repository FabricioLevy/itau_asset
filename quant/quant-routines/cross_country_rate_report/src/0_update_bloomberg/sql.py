import os
import urllib.parse
import sqlalchemy as sa
import pandas as pd

class SQLConnection:

    __instance = {}

    @staticmethod 
    def getInstance(database='dbprod1'):
        """ Static access method. """
        if database not in SQLConnection.__instance:
            SQLConnection(database)
        return SQLConnection.__instance[database]

    def __new__(cls, 
                database='dbprod1',
                server = 'srvprod1.database.windows.net'):
        if database not in SQLConnection.__instance:
            print('... creating SQLConnection!')
            cls._server = server
            cls._port = 1433
            cls._database = database
            cls._uid = urllib.parse.quote(os.environ.get('DB_USER'))
            cls._pwd = urllib.parse.quote(os.environ.get('DB_PASS'))  
            cls._driver= "ODBC+Driver+17+for+SQL+Server"
            cls._authentication='ActiveDirectoryPassword'
            cls._engine = sa.create_engine(f"mssql+pyodbc://{cls._uid}:{cls._pwd}@{cls._server},{cls._port}/{cls._database}"
                                            f"?driver={cls._driver}"
                                            f"&authentication={cls._authentication}")   
            cls._conn = cls._engine.connect()
            cls.__instance[database] = super().__new__(cls)
        return cls.__instance[database]
    def get_connection(self):
        if self._conn.closed:
            self._conn = self._engine.connect()            
        return self._conn
        
    def get_engine(self):
        return self._engine
    
    def __repr__(self):
        return "SQLConnection: " + self._engine.__repr__()
    
    def __del__(self):
        print ("... SQLConnection deleted!")
    
    def read_predi(self, tenor):
        query = '''
            SELECT
                [date_reference]
                ,[curve_rate]*100 as 'value'
            FROM [risk].[interest_rate_curve]
            where
                tenor='%s'
                AND curve_name = 'DI Fut'
                AND date_reference >= '2005-06-10'
            ORDER BY date_reference
        ''' % (tenor)        

        conn = self.get_connection()
        data = pd.read_sql( query, conn )
        data['date_reference'] = pd.to_datetime(data['date_reference'])
        
        return data.values

    def read_products(self, product_ids, date_start):
        query = '''
            SELECT 
                [date_reference],
                [product_id],
                [rate]
            FROM [middle].[product_price]
            WHERE
                date_reference >= '%s' AND
                product_id in (\'%s\')
        ''' % (date_start, '\',\''.join(product_ids) )

        conn = self.get_connection()
        data = pd.read_sql(query, conn)
        data = data.pivot(columns='product_id', values='rate', index='date_reference')
        data['date'] = [pd.Timestamp(x) for x in data.index]

        # data = data.rename(columns={'date_reference':'date','value':entity_id})
        data = data.set_index('date')        

        return data


    def read_series(self, entity_id, date):
        query = '''
            SELECT 
                b.date_reference,
                b.[value]
            FROM [quant].[time_series] as a
            JOIN [quant].[time_series_value] as b
            ON a.[id]=b.[series_id]
            WHERE
                [entity_id] = '%s'
                AND [field]='PX_LAST'
                AND date_reference > '%s'
            ORDER BY date_reference
        ''' % (entity_id,date)

        conn = self.get_connection()
        data = pd.read_sql( query, conn )
        data = data.rename(columns={'date_reference':'date','value':entity_id})
        data['date'] = pd.to_datetime(data['date'])
        data = data.set_index('date')

        data.index = [pd.Timestamp(x) for x in data.index]
        
        return data