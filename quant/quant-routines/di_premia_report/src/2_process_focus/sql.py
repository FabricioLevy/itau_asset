import pandas as pd
import pyodbc
from sqlalchemy import create_engine


class SQLConnection:
    def __init__(self):
        self.server_name = "levydb.database.windows.net"
        self.db_name = "db"
        self.username = "adm"
        self.password = "FFLhSgNS375qJRNZA9QR8YUA"

        self.connection = self.criar_conexao()
        self.engine = self.criar_engine()

    def criar_conexao(self):
        try:
            conn = pyodbc.connect(
                "Driver={ODBC Driver 17 for SQL Server};"
                f"Server={self.server_name};"
                f"Database={self.db_name};"
                f"UID={self.username};"
                f"PWD={self.password};"
                "Mars_Connection=Yes;",
                autocommit=False
            )
            print("Conexão (pyodbc) realizada com sucesso!")
            return conn
        except Exception as e:
            print(f"Erro ao conectar via pyodbc: {e}")
            return None

    def criar_engine(self):
        try:
            conn_str = (
                f"mssql+pyodbc://{self.username}:{self.password}"
                f"@{self.server_name}/{self.db_name}"
                "?driver=ODBC+Driver+17+for+SQL+Server"
            )
            engine = create_engine(conn_str, fast_executemany=True)
            print("Engine (SQLAlchemy) criado com sucesso!")
            return engine
        except Exception as e:
            print(f"Erro ao criar engine: {e}")
            return None

    def get_connection(self):
        return self.engine

    def fechar_conexao(self):
        if self.connection:
            self.connection.close()

    def run_query(self, query):
        return pd.read_sql(query, self.engine)

    def execute(self, query, params=None):
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            self.connection.commit()
        except Exception as e:
            print(f"Erro ao executar query: {e}")
            self.connection.rollback()

    def read_focus(self):
        query = """
            SELECT
                q1.[date],
                q1.[value] as '6M',
                q2.[value] as '1Y',
                q2b.[value] as '18M',
                q3.[value] as '2Y',
                q4.[value] as '5Y'
            FROM (
                SELECT
                    [date]
                    ,[value]
                FROM [bcb].[modulo_focus_value] as b
                JOIN [bcb].modulo_focus_series as a
                ON a.id = b.series_id
                WHERE a.indicator = 'SELIC' AND a.[type] = '126DU'
            ) as q1
            FULL JOIN (
                SELECT
                    [date]
                    ,[value]
                FROM [bcb].[modulo_focus_value] as b
                JOIN [bcb].modulo_focus_series as a
                ON a.id = b.series_id
                WHERE a.indicator = 'SELIC' AND a.[type] = '252DU'
            ) as q2
            ON q1.[date] = q2.[date]
            FULL JOIN (
                SELECT
                    [date]
                    ,[value]
                FROM [bcb].[modulo_focus_value] as b
                JOIN [bcb].modulo_focus_series as a
                ON a.id = b.series_id
                WHERE a.indicator = 'SELIC' AND a.[type] = '378DU'
            ) as q2b
            ON q1.[date] = q2b.[date]
            FULL JOIN (
                SELECT
                    [date]
                    ,[value]
                FROM [bcb].[modulo_focus_value] as b
                JOIN [bcb].modulo_focus_series as a
                ON a.id = b.series_id
                WHERE a.indicator = 'SELIC' AND a.[type] = '504DU'
            ) as q3
            ON q1.[date] = q3.[date]
            FULL JOIN (
                SELECT
                    [date]
                    ,[value]
                FROM [bcb].[modulo_focus_value] as b
                JOIN [bcb].modulo_focus_series as a
                ON a.id = b.series_id
                WHERE a.indicator = 'SELIC' AND a.[type] = '1260DU'
            ) as q4
            ON q1.[date] = q4.[date]
        """
        conn = self.get_connection()
        data = pd.read_sql(query, conn)
        data = data.rename(columns={'date': 'from_date'})
        data['from_date'] = [pd.Timestamp(x).date() for x in data['from_date']]
        data = data.set_index('from_date')

        return data
