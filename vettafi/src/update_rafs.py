"""
Atualiza a dbo.FUNDOS_DADOS_INDICES (DBSX337) com as cotas dos índices VettaFi que o
insert.py grava em dbo.rafs_cotas_indices.

Entra só a versão de preço de cada índice (CODIGOS), com o INDEX_CODE como
codigo_IAM_indice; as versões retorno total (T) e líquido (N) ficam só na
rafs_cotas_indices:
  date        <- PRICE_DATE
  preco_limpo <- INDEX_VALUE   (cota do índice)
  pnl_perc    <- DAILY_RETURN  (retorno do dia em fração: 0.0107 = 1,07%)
  tipo_dado   <- 'oficial'
  log_*       <- data/hora da carga, usuário (racf) e nome deste script
As colunas de duration e de pnl de carrego/mtm ficam nulas (índices de ações).

Carga incremental por código: busca a última date gravada na FUNDOS_DADOS_INDICES e
regrava a partir dela (inclusive), apagando e reinserindo essas datas na mesma transação.
Código ainda sem dados recebe todo o histórico da rafs_cotas_indices.

Uso: python src/update_rafs.py   (a partir da pasta vettafi, depois do insert.py)
Credenciais: variáveis de ambiente SQL_LOGIN e SQL_PASSWORD (ver sql_connection.py)
"""
import getpass
from datetime import date, datetime
from pathlib import Path
from typing import Dict

import pandas as pd

from sql_connection import disconnect, get_connection

ORIGEM = "dbo.rafs_cotas_indices"
DESTINO = "dbo.FUNDOS_DADOS_INDICES"
CODIGOS = ["RAFSBDRP", "RAFSBRAP"]  # INDEX_CODE da versão de preço = codigo_IAM_indice
MARCADORES = ", ".join("?" for _ in CODIGOS)  # IN (...) com os CODIGOS como parâmetros
TIPO_DADO = "oficial"
# colunas do INSERT (as de duration e de pnl de carrego/mtm ficam nulas)
COLUNAS = [
    "date", "codigo_IAM_indice", "preco_limpo", "pnl_perc", "tipo_dado",
    "log_last_processamento", "log_last_user", "log_script_from",
]


def ler_cotas(conn) -> pd.DataFrame:
    """Cotas dos CODIGOS com os nomes e o tipo (FLOAT) das colunas da FUNDOS_DADOS_INDICES."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT PRICE_DATE, INDEX_CODE, CAST(INDEX_VALUE AS FLOAT), CAST(DAILY_RETURN AS FLOAT) "
        f"FROM {ORIGEM} WHERE INDEX_CODE IN ({MARCADORES})",
        CODIGOS,
    )
    return pd.DataFrame(
        [tuple(linha) for linha in cursor.fetchall()],
        columns=["date", "codigo_IAM_indice", "preco_limpo", "pnl_perc"],
    )


def ultima_data_por_codigo(conn) -> Dict[str, date]:
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT codigo_IAM_indice, MAX([date]) FROM {DESTINO} "
        f"WHERE codigo_IAM_indice IN ({MARCADORES}) GROUP BY codigo_IAM_indice",
        CODIGOS,
    )
    return {codigo: data for codigo, data in cursor.fetchall()}


def salvar(conn, df: pd.DataFrame, db_name: str):
    inicio_por_codigo = df.groupby("codigo_IAM_indice")["date"].min()
    # log das tabelas FUNDOS_: data/hora sem microssegundos (a coluna é DATETIME),
    # usuário (racf, até 20 caracteres) e script de origem
    log = (datetime.now().replace(microsecond=0), getpass.getuser()[:20], Path(__file__).name)
    linhas = [
        tuple(None if pd.isna(v) else v for v in linha) + (TIPO_DADO,) + log
        for linha in df.itertuples(index=False, name=None)
    ]
    colunas_sql = ", ".join(f"[{c}]" for c in COLUNAS)
    placeholders = ", ".join("?" for _ in COLUNAS)

    # DELETE + INSERT na mesma transação (o sql.execute() faz commit por comando)
    try:
        cursor = conn.cursor()
        cursor.fast_executemany = True
        cursor.executemany(
            f"DELETE FROM {DESTINO} WHERE [codigo_IAM_indice] = ? AND [date] >= ?",
            list(inicio_por_codigo.items()),
        )
        cursor.executemany(
            f"INSERT INTO {DESTINO} ({colunas_sql}) VALUES ({placeholders})",
            linhas,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    print(f"{len(linhas)} linhas gravadas em {db_name}.{DESTINO}:")
    for codigo, datas in df.groupby("codigo_IAM_indice")["date"]:
        print(f"  {codigo}: {datas.min()} a {datas.max()} ({datas.nunique()} datas)")


def atualizar(conn, db_name: str):
    cotas = ler_cotas(conn)
    if cotas.empty:
        print(f"Nenhuma cota de {', '.join(CODIGOS)} em {ORIGEM}: rode o insert.py antes.")
        return

    ultimas = ultima_data_por_codigo(conn)
    for codigo, data in sorted(ultimas.items()):
        print(f"Última date em {DESTINO} - {codigo}: {data}")

    limite = cotas["codigo_IAM_indice"].map(lambda c: ultimas.get(c, date.min))
    novas = cotas[cotas["date"] >= limite]
    if novas.empty:
        print(f"Nenhuma data nova para {DESTINO}.")
        return
    salvar(conn, novas, db_name)


def main():
    sql = get_connection()
    conn = sql.connection
    if conn is None:
        raise RuntimeError(f"Sem conexão com o banco {sql.db_name}")

    try:
        atualizar(conn, sql.db_name)
    finally:
        disconnect()


if __name__ == "__main__":
    main()
