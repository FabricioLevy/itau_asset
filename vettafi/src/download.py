"""
Carrega a composição diária dos índices VettaFi (input/RAFS*/*.csv)
na tabela DBSX337.dbo.rafs_composicao_indices.

Carga incremental por índice: busca no SQL a última EFFECTIVE_DATE gravada e
regrava a partir dela (inclusive), apagando e reinserindo essas datas na mesma
transação. Índice ainda sem dados no SQL é carregado desde o primeiro arquivo.

Uso: python src   (a partir da pasta vettafi)
Credenciais: variáveis de ambiente SQL_LOGIN e SQL_PASSWORD (ver sql_connection.py)
"""
from datetime import date, datetime, timedelta
from decimal import Context, Decimal
from pathlib import Path
from typing import Dict

import pandas as pd

from sql_connection import disconnect, get_connection

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_DIR = BASE_DIR / "input"

TABELA = "dbo.rafs_composicao_indices"
CONTEXTO_DECIMAL = Context(prec=38)  # precisão máxima do DECIMAL no SQL Server
# o nome do arquivo tem a data do pregão anterior à EFFECTIVE_DATE; a margem cobre feriados
MARGEM_DATA_ARQUIVO = timedelta(days=7)

COLUNAS_TEXTO = [
    "INDEX", "COMPANY_NAME", "BB_TICKER", "SEDOL", "CUSIP", "ISIN", "ID_BB_GLOBAL",
    "ICE_SECTOR_CODE", "ICE_SECTOR_NAME", "VETTAFI_CATEGORY", "MIC", "COUNTRY",
    "REGION", "SIZE", "CAP", "CURR",
]
# coluna -> casas decimais (igual ao DECIMAL(p,s) da tabela)
COLUNAS_DECIMAIS = {
    "LOCAL_PRICE": 8,
    "FX_RATE": 16,
    "INDEX_PRICE": 16,
    "SHARES_OUTSTANDING": 4,
    "MARKET_CAP": 16,
    "FLOAT": 16,
    "WAF": 16,
    "INDEX_SHARES": 16,
    "INDEX_MARKET_CAP": 16,
    "INDEX_WEIGHT": 16,
    "DAILY_PRICE_RETURN": 16,
    "DAILY_TOTAL_RETURN": 16,
    "DIVIDEND": 8,
    "NET_DIVIDEND": 8,
}
COLUNAS_TABELA = (
    ["INDEX", "EFFECTIVE_DATE"] + COLUNAS_TEXTO[1:] + list(COLUNAS_DECIMAIS) + ["NOME_ARQUIVO"]
)


def ultima_data_por_indice(conn) -> Dict[str, date]:
    cursor = conn.cursor()
    cursor.execute(f"SELECT [INDEX], MAX(EFFECTIVE_DATE) FROM {TABELA} GROUP BY [INDEX]")
    return {indice: data for indice, data in cursor.fetchall()}


def para_decimal(valor, casas):
    if pd.isna(valor) or valor == "":
        return None
    return Decimal(valor).quantize(Decimal(1).scaleb(-casas), context=CONTEXTO_DECIMAL)


def ler_arquivo(caminho: Path) -> pd.DataFrame:
    df = pd.read_csv(caminho, dtype=str, keep_default_na=False, na_values=[""])
    # a última linha do arquivo é o rodapé "line count = N"
    df = df[df["EFFECTIVE_DATE"].notna()].copy()

    for col in COLUNAS_TEXTO:
        df[col] = df[col].str.strip()
    df["EFFECTIVE_DATE"] = pd.to_datetime(df["EFFECTIVE_DATE"], format="%Y%m%d").dt.date
    for col, casas in COLUNAS_DECIMAIS.items():
        df[col] = df[col].map(lambda v, c=casas: para_decimal(v, c))
    df["NOME_ARQUIVO"] = caminho.name
    return df[COLUNAS_TABELA]


def arquivo_necessario(caminho: Path, ultimas: Dict[str, date]) -> bool:
    """Evita reler o histórico: arquivos de pasta/índice YYYYMMDD_<INDICE>_... ."""
    ultima = ultimas.get(caminho.parent.name)
    if ultima is None:
        return True
    data_arquivo = datetime.strptime(caminho.name[:8], "%Y%m%d").date()
    return data_arquivo >= ultima - MARGEM_DATA_ARQUIVO


def ler_input(ultimas: Dict[str, date]) -> pd.DataFrame:
    arquivos = sorted(INPUT_DIR.glob("RAFS*/*.csv"))
    if not arquivos:
        raise FileNotFoundError(f"Nenhum CSV encontrado em {INPUT_DIR}")
    arquivos = [a for a in arquivos if arquivo_necessario(a, ultimas)]
    print(f"Lendo {len(arquivos)} arquivos de {INPUT_DIR}")
    if not arquivos:
        return pd.DataFrame(columns=COLUNAS_TABELA)

    df = pd.concat([ler_arquivo(a) for a in arquivos], ignore_index=True)
    limite = df["INDEX"].map(lambda i: ultimas.get(i, date.min))
    df = df[df["EFFECTIVE_DATE"] >= limite]

    duplicados = df.duplicated(["INDEX", "EFFECTIVE_DATE", "ID_BB_GLOBAL"], keep=False)
    if duplicados.any():
        raise ValueError(f"Linhas duplicadas na chave:\n{df[duplicados]}")
    return df


def salvar(conn, df: pd.DataFrame, db_name: str):
    inicio_por_indice = df.groupby("INDEX")["EFFECTIVE_DATE"].min()
    linhas = [
        tuple(None if pd.isna(v) else v for v in linha)
        for linha in df.itertuples(index=False, name=None)
    ]
    colunas_sql = ", ".join(f"[{c}]" for c in COLUNAS_TABELA)
    placeholders = ", ".join("?" for _ in COLUNAS_TABELA)

    # DELETE + INSERT na mesma transação (o sql.execute() faz commit por comando)
    try:
        cursor = conn.cursor()
        cursor.fast_executemany = True
        cursor.executemany(
            f"DELETE FROM {TABELA} WHERE [INDEX] = ? AND EFFECTIVE_DATE >= ?",
            list(inicio_por_indice.items()),
        )
        cursor.executemany(
            f"INSERT INTO {TABELA} ({colunas_sql}) VALUES ({placeholders})",
            linhas,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    print(f"{len(linhas)} linhas gravadas em {db_name}.{TABELA}:")
    for indice, datas in df.groupby("INDEX")["EFFECTIVE_DATE"]:
        print(f"  {indice}: {datas.min()} a {datas.max()} ({datas.nunique()} datas)")


def main():
    sql = get_connection()
    conn = sql.connection
    if conn is None:
        raise RuntimeError(f"Sem conexão com o banco {sql.db_name}")

    try:
        ultimas = ultima_data_por_indice(conn)
        for indice, data in sorted(ultimas.items()):
            print(f"Última data no SQL - {indice}: {data}")

        df = ler_input(ultimas)
        if df.empty:
            print("Nenhuma data nova para carregar.")
            return
        salvar(conn, df, sql.db_name)
    finally:
        disconnect()


if __name__ == "__main__":
    main()
