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

        self.n_batch = 20
        self.batch_count = 0
        self.batch_query = ''
        self.batch_parameters = []

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

    def batch_send(self):
        if self.batch_count == 0:
            return True
        query = """
            SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
            BEGIN TRAN
                %s
            COMMIT
        """ % (self.batch_query)
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, self.batch_parameters)
            self.connection.commit()
        except Exception as e:
            print(f"Erro ao executar batch: {e}")
            self.connection.rollback()
        self.clear_batch()
        return 1

    def clear_batch(self):
        self.batch_count = 0
        self.batch_query = ''
        self.batch_parameters = []

    def batch_insert(
        self,
        data,
        table_name,
        identifier_keys,
        parameters_keys,
    ):
        identifier_data = [str(data[key]) for key in identifier_keys]
        identifier_string = ' AND '.join([
            (key + '=?') for key in identifier_keys
        ])
        identifier_query_snippet = ','.join([
            key for key in identifier_keys
        ])

        fields = []
        keys = data.keys()
        for item in parameters_keys:
            if item in keys:
                fields.append(item)

        data_block = [str(data[field]) for field in fields]

        update_query_snippet = ','.join([(field + '=?') for field in fields])
        insert_query_snippet = ','.join([field for field in fields])

        query_unit = """
            IF EXISTS (
                SELECT TOP 1 %s FROM %s WITH (UPDLOCK)
                WHERE %s
            )
                UPDATE %s SET %s
                WHERE %s;
            ELSE
                INSERT %s (%s,%s)
                VALUES (%s,%s);
        """ % (
            parameters_keys[0],
            table_name,
            identifier_string,
            table_name,
            update_query_snippet,
            identifier_string,
            table_name,
            insert_query_snippet,
            identifier_query_snippet,
            ','.join(['?' for field in fields]),
            ','.join(['?' for field in identifier_keys]),
        )

        current_parameters = []
        current_parameters.extend(identifier_data)
        current_parameters.extend(data_block)
        current_parameters.extend(identifier_data)
        current_parameters.extend(data_block)
        current_parameters.extend(identifier_data)

        self.batch_query += query_unit
        self.batch_parameters.extend(current_parameters)
        self.batch_count += 1

        if self.batch_count >= self.n_batch:
            return self.batch_send()
        return True
