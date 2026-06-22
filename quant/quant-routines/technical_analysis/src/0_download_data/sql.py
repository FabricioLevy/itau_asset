import pandas as pd
import urllib.parse
import sqlalchemy as sa
import os
class SQLConnection:    
    __instance = {}
    @staticmethod 
    def getInstance(database='dbprod1',server='srvprod1.database.windows.net'):
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
    
    def read_predi(self, start_date, end_date):
        query = '''
            SELECT
                [date_reference],
                tenor,
                [curve_rate]*100 as 'value'
            FROM [risk].[interest_rate_curve]
            where
                tenor in (360, 720)
                AND curve_name = 'DI Fut'
                AND date_reference >= '%s'
                AND date_reference <= '%s'
            ORDER BY date_reference
        ''' % (start_date, end_date)
        # cursor = self.conn.cursor()
        # cursor.execute( query, [start_date, end_date] )
        # data = pd.DataFrame(
        #     [ [ pd.Timestamp(x[0]), x[1], x[2] ] for x in cursor.fetchall()],
        #     columns=['date', 'tenor', 'value']
        # )        
        conn = self.get_connection()
        data = pd.read_sql(query, conn)
        data = data.rename(columns={'date_reference':'date'})
        data['date'] = pd.to_datetime(data['date'])
        
        data = data.pivot(
            index='date', 
            columns='tenor', 
            values='value'
        )
        
        data = data.rename(
            columns={
                360.:'PREDI360 Index', 
                720.:'PREDI720 Index'
            }
        )
        data.index.name = None
        data.columns.name = None
        return data 

    def read_other(self, start_date, end_date):
        query = '''
            SELECT
                a.[name],
                b.[date_reference],
                b.[value]
            FROM [quant].[time_series_value] as b
            JOIN [quant].[time_series] as a
            ON a.[id]=b.[series_id]
            WHERE a.[name] in ('IDIX9 Index', 'IBOVESPA', 'S&P 500', 'BRL')
                AND date_reference >= '%s'
                AND date_reference <= '%s'
            ORDER BY b.[date_reference] DESC
        ''' % (start_date, end_date)
        
        # cursor = self.conn.cursor()
        conn = self.get_connection()
        data = pd.read_sql(query, conn)
        data['date_reference'] = pd.to_datetime(data['date_reference'])
        data = data.pivot(
            index='date_reference', 
            columns='name', 
            values='value'
            )
        data = data.rename(
            columns={
                'IDIX9 Index':'BZACCETP Index', 
                'IBOVESPA':'IBOV Index',
                'S&P 500':'SPX Index',
                'BRL':'USDBRL Curncy',
            }
        )
        
        # # cursor.execute( query, [start_date, end_date] )
        # data = pd.DataFrame(
        #     [ [ x[0], pd.Timestamp(x[1]), x[2] ] for x in cursor.fetchall()],
        #     columns=['name', 'date_reference', 'value']
        # ).pivot(
        #     index='date_reference', 
        #     columns='name', 
        #     values='value'
        # ).rename(
        #     columns={
        #         'IDIX9 Index':'BZACCETP Index', 
        #         'IBOVESPA':'IBOV Index',
        #         'S&P 500':'SPX Index',
        #         'BRL':'USDBRL Curncy',
        #     }
        # )
        return data

    def read_assets(self, use_fic=False):
        str_filter_peers = 'DailyComparison'
        str_filter = 'cnpj_fundo_fic' if use_fic else 'cnpj_fundo_master'
        query = """
            SELECT g.gestor_short_name, fp.plot_name, fp.{0}, c.denom_social, c.fundo_quotas, fp.cnpj_fundo_master as cnpj_master
            FROM cvm.fundo_investimento_cadastro c 
                INNER JOIN cvm.gestor g ON g.cnpj_cpf_gestor = c.cnpj_cpf_gestor
                INNER JOIN cvm.fund_peers fp ON fp.{0} = c.cnpj_fundo
            WHERE fp.[peer_group] = '{1}' and g.gestor_short_name is not null
        """.format(str_filter, str_filter_peers)
        
        conn = self.get_connection()
        data = pd.read_sql(query, conn)
        data = data.rename(columns={
            str_filter:'cnpj',
            'denom_social':'social_name',
            })
        
        # cursor = self.conn.cursor()
        # cursor.execute( query, [] )
        # data = pd.DataFrame(
        #     [list(x) for x in cursor.fetchall()],
        #     columns=['gestor_short_name', 'plot_name', 'cnpj', 'social_name', 'fundo_quotas', 'cnpj_master']
        # )
        return data

    def read_asset_data(self, start_date, end_date, cnpj_dict):
        query = """
            SELECT [cnpj_fundo],[date_reference],[quota_value] 
            FROM [cvm].[fundo_investimento_informe_diario]
            WHERE  date_reference BETWEEN '{}' AND '{}'
            and [cnpj_fundo] in ({})
        """.format(start_date, end_date, ','.join([str(x) for x in cnpj_dict.keys()]))
        

        conn = self.get_connection()
        data = pd.read_sql(query, conn)
        data = data.rename(columns={
            'cnpj_fundo':'cnpj',
            'date_reference':'date',            
            })
        data['date'] = pd.to_datetime(data['date'])
        data = data.pivot(
            index='date', 
            columns='cnpj', 
            values='quota_value'
        )
        # cursor = self.conn.cursor()
        # cursor.execute( query, [] )
        # data = pd.DataFrame(
        #     [ [ x[0], pd.Timestamp(x[1]), x[2] ] for x in cursor.fetchall()],
        #     columns=['cnpj', 'date', 'quota_value']
        # )
        return data