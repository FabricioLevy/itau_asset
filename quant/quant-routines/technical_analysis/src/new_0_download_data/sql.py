import pyodbc 
import pandas as pd
import os
class SqlClass():
    def __init__(self):
        server = 'srvprod1.database.windows.net'
        database = 'dbprod1'
        username = os.environ.get('DB_USER')
        password = os.environ.get('DB_PASS')
        authentication='ActiveDirectoryPassword'        
        if os.name == 'nt':
            driver = 'SQL+Server'
        else:
            driver = 'ODBC Driver 17 for SQL Server'
        driver = 'ODBC Driver 17 for SQL Server'
        self.conn = pyodbc.connect(
            f"Driver={driver};"
            f"Server={server};"
            f"Database={database};"
            f"UID={username};"
            f"PWD={password};"
            f"AUTHENTICATIONS={authentication};"
            f"Trusted_Connection=Yes;"
        )
    
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
                AND date_reference >= ?
                AND date_reference <= ?
            ORDER BY date_reference
        '''
        cursor = self.conn.cursor()
        cursor.execute( query, [start_date, end_date] )
        data = pd.DataFrame(
            [ [ pd.Timestamp(x[0]), x[1], x[2] ] for x in cursor.fetchall()],
            columns=['date', 'tenor', 'value']
        ).pivot(
            index='date', 
            columns='tenor', 
            values='value'
        ).rename(
            columns={
                360.:'DI1Y', 
                720.:'DI2Y'
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
                AND date_reference >= ?
                AND date_reference <= ?
            ORDER BY b.[date_reference] DESC
        '''
        cursor = self.conn.cursor()
        cursor.execute( query, [start_date, end_date] )
        data = pd.DataFrame(
            [ [ x[0], pd.Timestamp(x[1]), x[2] ] for x in cursor.fetchall()],
            columns=['name', 'date_reference', 'value']
        ).pivot(
            index='date_reference', 
            columns='name', 
            values='value'
        ).rename(
            columns={
                'IDIX9 Index':'IDIX9', 
                'IBOVESPA':'IBOV',
                'S&P 500':'SPX',
                'BRL':'USDBRL',
            }
        )
        return data

    def read_assets(self, use_fic=False):
        str_filter_peers = 'DailyComparison'
        str_filter = 'cnpj_fundo_fic' if use_fic else 'cnpj_fundo_master'
        query = """
            SELECT g.gestor_short_name, fp.plot_name, fp.{0}, c.denom_social, fp.cnpj_fundo_master as cnpj_master
            FROM cvm.fundo_investimento_cadastro c 
                INNER JOIN cvm.gestor g ON g.cnpj_cpf_gestor = c.cnpj_cpf_gestor
                INNER JOIN cvm.fund_peers fp ON fp.{0} = c.cnpj_fundo
            WHERE fp.[peer_group] = '{1}' and g.gestor_short_name is not null
        """.format(str_filter, str_filter_peers)
        cursor = self.conn.cursor()
        cursor.execute( query, [] )
        data = pd.DataFrame(
            [list(x) for x in cursor.fetchall()],
            columns=['gestor_short_name', 'plot_name', 'cnpj_fic', 'social_name', 'cnpj_master']
        )
        return data

    def read_asset_data(self, start_date, end_date, cpnj_list):
        query = """
            SELECT [cnpj_fundo],[date_reference],[quota_value] 
            FROM [cvm].[fundo_investimento_informe_diario]
            WHERE  date_reference BETWEEN '{}' AND '{}'
            and [cnpj_fundo] in ({})
        """.format(start_date, end_date, ','.join([str(x) for x in cpnj_list]))
        
        cursor = self.conn.cursor()
        cursor.execute( query, [] )
        data = pd.DataFrame(
            [ [ x[0], pd.Timestamp(x[1]), x[2] ] for x in cursor.fetchall()],
            columns=['cnpj', 'date', 'quota_value']
        ).pivot(
            index='date', 
            columns='cnpj', 
            values='quota_value'
        )
        return data