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
        """Cria conexão pyodbc para uso com cursor (MERGE, INSERT, UPDATE)"""
        try:
            conn = pyodbc.connect(
                "Driver={ODBC Driver 17 for SQL Server};"
                f"Server={self.server_name};"
                f"Database={self.db_name};"
                f"UID={self.username};"
                f"PWD={self.password};"
                "Mars_Connection=Yes;",
                autocommit=False  # deixa sob seu controle o commit
            )
            print("✅ Conexão (pyodbc) realizada com sucesso!")
            return conn
        except Exception as e:
            print(f"❌ Erro ao conectar via pyodbc: {e}")
            return None

    def criar_engine(self):
        """Cria engine SQLAlchemy (para to_sql e consultas via pandas)"""
        try:
            conn_str = (
                f"mssql+pyodbc://{self.username}:{self.password}"
                f"@{self.server_name}/{self.db_name}"
                "?driver=ODBC+Driver+17+for+SQL+Server"
            )
            engine = create_engine(conn_str, fast_executemany=True)
            print("✅ Engine (SQLAlchemy) criado com sucesso!")
            return engine
        except Exception as e:
            print(f"❌ Erro ao criar engine: {e}")
            return None

    def fechar_conexao(self):
        """Fecha conexão pyodbc"""
        if self.connection:
            self.connection.close()
            print("🔒 Conexão pyodbc fechada com sucesso!")

    def run_query(self, query):
        """Executa uma query SELECT e retorna DataFrame"""
        return pd.read_sql(query, self.engine)

    def execute(self, query, params=None):
        """Executa queries DML (INSERT, UPDATE, DELETE, MERGE) com pyodbc"""
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            self.connection.commit()
        except Exception as e:
            print(f"❌ Erro ao executar query: {e}")
            self.connection.rollback()
