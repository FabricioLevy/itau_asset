"""
Atualiza na DBSX337, para os índices VettaFi em CODIGOS, as tabelas FUNDOS_ a partir das
tabelas rafs_ que o insert.py grava.

dbo.rafs_cotas_indices -> dbo.FUNDOS_DADOS_INDICES (só a versão de preço do índice; as
versões retorno total T e líquido N ficam só na rafs_cotas_indices):
  date        <- PRICE_DATE
  preco_limpo <- INDEX_VALUE   (cota do índice)
  pnl_perc    <- DAILY_RETURN  (retorno do dia em fração: 0.0107 = 1,07%)
  tipo_dado   <- 'oficial'
  log_*       <- data/hora da carga, usuário (racf) e nome deste script
As colunas de duration e de pnl de carrego/mtm ficam nulas (índices de ações).

dbo.rafs_composicao_indices -> dbo.FUNDOS_COMPOSICAO_INDICES:
  date              <- EFFECTIVE_DATE  (dia em que a composição vale, como no IBOV)
  codigo_IAM_ativo  <- SEDOL
  quantidade        <- INDEX_SHARES arredondado (quantidade teórica)
  perc              <- INDEX_WEIGHT    (peso em fração no início do dia)
  ticker_bolsa      <- BB_TICKER sem o código da bolsa ('BBDC4 BS' -> 'BBDC4')
  security_name     <- COMPANY_NAME
  gics_sector_name  <- ICE_SECTOR_NAME (setor ICE da VettaFi)
  tipo_dado, tipo, fator_risco, ativo, multiplicador_contrato <- 'oficial', 'Equity',
      'Renda Variavel', 'Common Stock', 1
Preço, total e retornos do dia ficam nulos: o ADJ_CLOSE não traz o fechamento do dia.

Carga incremental por tabela e código: busca a última date gravada e regrava a partir dela
(inclusive), apagando e reinserindo essas datas na mesma transação. Código ainda sem dados
recebe todo o histórico da tabela rafs_.

Uso: python src/update_rafs.py   (a partir da pasta vettafi, depois do insert.py)
Credenciais: variáveis de ambiente SQL_LOGIN e SQL_PASSWORD (ver sql_connection.py)
"""
import getpass
from datetime import date, datetime
from pathlib import Path
from typing import Dict

import pandas as pd

from sql_connection import disconnect, get_connection

DADOS = "dbo.FUNDOS_DADOS_INDICES"
COMPOSICAO = "dbo.FUNDOS_COMPOSICAO_INDICES"
CODIGOS = ["RAFSBDRP", "RAFSBRAP"]  # INDEX_CODE da versão de preço = [INDEX] = codigo_IAM_indice
MARCADORES = ", ".join("?" for _ in CODIGOS)  # IN (...) com os CODIGOS como parâmetros
TIPO_DADO = "oficial"
# colunas com o mesmo valor em todas as linhas da composição (ações e BDRs)
CONSTANTES_COMPOSICAO = {
    "tipo_dado": TIPO_DADO, "tipo": "Equity", "fator_risco": "Renda Variavel",
    "ativo": "Common Stock", "multiplicador_contrato": 1.0,
}


def consultar(conn, sql: str) -> pd.DataFrame:
    """SELECT com os CODIGOS como parâmetros -> DataFrame com os nomes das colunas do SELECT."""
    cursor = conn.cursor()
    cursor.execute(sql, CODIGOS)
    colunas = [coluna[0] for coluna in cursor.description]
    # object: mantém os tipos do pyodbc (int do BIGINT não vira float e NULL continua None)
    return pd.DataFrame(
        [tuple(linha) for linha in cursor.fetchall()], columns=colunas, dtype=object
    )


def ler_cotas(conn) -> pd.DataFrame:
    """Cotas dos CODIGOS com os nomes e o tipo (FLOAT) das colunas da FUNDOS_DADOS_INDICES."""
    return consultar(
        conn,
        "SELECT PRICE_DATE AS [date], INDEX_CODE AS codigo_IAM_indice, "
        "CAST(INDEX_VALUE AS FLOAT) AS preco_limpo, CAST(DAILY_RETURN AS FLOAT) AS pnl_perc "
        f"FROM dbo.rafs_cotas_indices WITH (NOLOCK) WHERE INDEX_CODE IN ({MARCADORES})",
    )


def ler_composicao(conn) -> pd.DataFrame:
    """Composição dos CODIGOS com os nomes e tipos das colunas da FUNDOS_COMPOSICAO_INDICES."""
    df = consultar(
        conn,
        "SELECT EFFECTIVE_DATE AS [date], [INDEX] AS codigo_IAM_indice, "
        "SEDOL AS codigo_IAM_ativo, CAST(ROUND(INDEX_SHARES, 0) AS BIGINT) AS quantidade, "
        "CAST(INDEX_WEIGHT AS FLOAT) AS perc, BB_TICKER AS ticker_bolsa, "
        "COMPANY_NAME AS security_name, ICE_SECTOR_NAME AS gics_sector_name "
        f"FROM dbo.rafs_composicao_indices WITH (NOLOCK) WHERE [INDEX] IN ({MARCADORES})",
    )
    # BB_TICKER é '<ticker> <bolsa>' (ex.: 'BBDC4 BS'): fica só o ticker
    df["ticker_bolsa"] = df["ticker_bolsa"].str.rsplit(" ", n=1).str[0]
    return df


def ultima_data_por_codigo(conn, tabela: str) -> Dict[str, date]:
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT codigo_IAM_indice, MAX([date]) FROM {tabela} WITH (NOLOCK) "
        f"WHERE codigo_IAM_indice IN ({MARCADORES}) GROUP BY codigo_IAM_indice",
        CODIGOS,
    )
    return {codigo: data for codigo, data in cursor.fetchall()}


def salvar(conn, tabela: str, df: pd.DataFrame, constantes: Dict[str, object], db_name: str):
    inicio_por_codigo = df.groupby("codigo_IAM_indice")["date"].min()
    colunas = list(df.columns) + list(constantes)
    linhas = [
        tuple(None if pd.isna(v) else v for v in linha) + tuple(constantes.values())
        for linha in df.itertuples(index=False, name=None)
    ]
    colunas_sql = ", ".join(f"[{c}]" for c in colunas)
    placeholders = ", ".join("?" for _ in colunas)

    # DELETE + INSERT na mesma transação (o sql.execute() faz commit por comando)
    try:
        cursor = conn.cursor()
        cursor.fast_executemany = True
        cursor.executemany(
            f"DELETE FROM {tabela} WHERE [codigo_IAM_indice] = ? AND [date] >= ?",
            list(inicio_por_codigo.items()),
        )
        cursor.executemany(
            f"INSERT INTO {tabela} ({colunas_sql}) VALUES ({placeholders})",
            linhas,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    print(f"{len(linhas)} linhas gravadas em {db_name}.{tabela}:")
    for codigo, datas in df.groupby("codigo_IAM_indice")["date"]:
        print(f"  {codigo}: {datas.min()} a {datas.max()} ({datas.nunique()} datas)")


def carregar(conn, tabela: str, df: pd.DataFrame, constantes: Dict[str, object], db_name: str):
    """Grava em tabela as datas de df a partir da última já gravada de cada código (inclusive)."""
    if df.empty:
        print(f"Nada de {', '.join(CODIGOS)} para {tabela}: rode o insert.py antes.")
        return

    ultimas = ultima_data_por_codigo(conn, tabela)
    for codigo, data in sorted(ultimas.items()):
        print(f"Última date em {tabela} - {codigo}: {data}")

    limite = df["codigo_IAM_indice"].map(lambda c: ultimas.get(c, date.min))
    novas = df[df["date"] >= limite]
    if novas.empty:
        print(f"Nenhuma data nova para {tabela}.")
        return
    salvar(conn, tabela, novas, constantes, db_name)


def atualizar(conn, db_name: str):
    # log da FUNDOS_DADOS_INDICES: data/hora sem microssegundos (a coluna é DATETIME),
    # usuário (racf, até 20 caracteres) e script de origem
    log = {
        "log_last_processamento": datetime.now().replace(microsecond=0),
        "log_last_user": getpass.getuser()[:20],
        "log_script_from": Path(__file__).name,
    }
    carregar(conn, DADOS, ler_cotas(conn), {"tipo_dado": TIPO_DADO, **log}, db_name)
    carregar(conn, COMPOSICAO, ler_composicao(conn), CONSTANTES_COMPOSICAO, db_name)


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
