# ─────────────────────────────────────────────
# sql_connection.py
# ─────────────────────────────────────────────

import os
import urllib.parse
from typing import Dict, Optional

import pandas as pd
import pyodbc
from sqlalchemy import create_engine


class SQLConnection:
    def __init__(
        self,
        db_name: str = "DBSX337",
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.server_name = "SQNPRC028"
        self.db_name = db_name

        # SQL user e password (variáveis de ambiente)
        if username is None:
            username = os.environ.get("SQL_LOGIN")
        if password is None:
            password = os.environ.get("SQL_PASSWORD")

        if not username or not password:
            raise RuntimeError(
                "Credenciais ausentes: defina as variáveis de ambiente "
                "SQL_LOGIN e SQL_PASSWORD."
            )

        self.username = username
        self.password = password
        self.connection = self._criar_conexao()
        self.engine = self._criar_engine()

    def _criar_conexao(self) -> Optional[pyodbc.Connection]:
        """Conexão pyodbc para DML (INSERT, UPDATE, MERGE)."""
        try:
            conn = pyodbc.connect(
                "Driver={ODBC Driver 18 for SQL Server};"
                f"Server={self.server_name};"
                f"Database={self.db_name};"
                f"UID={self.username};"
                f"PWD={self.password};"
                "TrustServerCertificate=yes;"
                "Mars_Connection=Yes;",
                autocommit=False,
            )
            print(f"[OK] Conexão (pyodbc) com {self.db_name} realizada com sucesso!")
            return conn
        except Exception as e:
            print(f"[ERRO] Erro ao conectar via pyodbc: {e}")
            return None

    def _criar_engine(self):
        """Engine SQLAlchemy para pd.read_sql e to_sql."""
        try:
            params = urllib.parse.quote_plus(
                "Driver={ODBC Driver 18 for SQL Server};"
                f"Server={self.server_name};"
                f"Database={self.db_name};"
                f"Uid={self.username};"
                f"Pwd={self.password};"
                "TrustServerCertificate=yes;"
            )
            engine = create_engine(
                f"mssql+pyodbc:///?odbc_connect={params}",
                fast_executemany=True,
            )
            print(f"[OK] Engine (SQLAlchemy) para {self.db_name} criado com sucesso!")
            return engine
        except Exception as e:
            print(f"[ERRO] Erro ao criar engine: {e}")
            return None

    def run_query(self, query: str) -> pd.DataFrame:
        """SELECT → DataFrame."""
        try:
            return pd.read_sql(query, self.engine)
        except Exception as e:
            print(f"[ERRO] Erro ao executar query: {e}")
            return pd.DataFrame()

    def execute(self, query: str, params=None) -> bool:
        """DML: INSERT / UPDATE / DELETE / MERGE."""
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params) if params else cursor.execute(query)
            self.connection.commit()
            return True
        except Exception as e:
            print(f"[ERRO] Erro ao executar DML: {e}")
            self.connection.rollback()
            return False

    def fechar_conexao(self) -> None:
        """Fecha a conexão pyodbc."""
        if self.connection:
            self.connection.close()
            print("[FECHADO] Conexão pyodbc fechada.")


# ── Singletons por banco ──────────────────────────────────────────────────────

DB_DEFAULT = "DBSX337"

_instances: Dict[str, SQLConnection] = {}


def get_connection(db_name: str = DB_DEFAULT) -> SQLConnection:
    """Retorna (ou cria) a instância única de SQLConnection para o banco informado."""
    conn = _instances.get(db_name)
    if conn is None:
        conn = SQLConnection(db_name=db_name)
        _instances[db_name] = conn
    return conn


def query(sql_str: str, db_name: str = DB_DEFAULT) -> pd.DataFrame:
    """Atalho global para SELECT."""
    return get_connection(db_name).run_query(sql_str)


def execute(sql_str: str, params=None, db_name: str = DB_DEFAULT) -> bool:
    """Atalho global para DML."""
    return get_connection(db_name).execute(sql_str, params)


def disconnect(db_name: Optional[str] = None) -> None:
    """Fecha a conexão de um banco (ou de todos, se db_name for None) e reseta o singleton."""
    global _instances
    if db_name is None:
        for conn in _instances.values():
            conn.fechar_conexao()
        _instances = {}
    else:
        conn = _instances.pop(db_name, None)
        if conn:
            conn.fechar_conexao()
