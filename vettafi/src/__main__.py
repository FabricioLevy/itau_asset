"""
Carrega a composição diária dos índices VettaFi (input/RAFS*/*.csv)
na tabela DBSX337.dbo.rafs_composicao_indices.

A carga é idempotente: as datas (INDEX, EFFECTIVE_DATE) presentes nos arquivos
são apagadas e reinseridas na mesma transação.

Uso: python src   (a partir da pasta vettafi)
Credenciais: variáveis de ambiente SQL_LOGIN e SQL_PASSWORD (ver sql_connection.py)
"""
from decimal import Context, Decimal
from pathlib import Path

import pandas as pd

from sql_connection import disconnect, get_connection

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_DIR = BASE_DIR / "input"

TABELA = "dbo.rafs_composicao_indices"
CONTEXTO_DECIMAL = Context(prec=38)  # precisão máxima do DECIMAL no SQL Server

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


def ler_input() -> pd.DataFrame:
    arquivos = sorted(INPUT_DIR.glob("RAFS*/*.csv"))
    if not arquivos:
        raise FileNotFoundError(f"Nenhum CSV encontrado em {INPUT_DIR}")
    print(f"Lendo {len(arquivos)} arquivos de {INPUT_DIR}")
    df = pd.concat([ler_arquivo(a) for a in arquivos], ignore_index=True)

    duplicados = df.duplicated(["INDEX", "EFFECTIVE_DATE", "ID_BB_GLOBAL"], keep=False)
    if duplicados.any():
        raise ValueError(f"Linhas duplicadas na chave:\n{df[duplicados]}")
    return df


def salvar(df: pd.DataFrame):
    datas = df[["INDEX", "EFFECTIVE_DATE"]].drop_duplicates()
    linhas = [
        tuple(None if pd.isna(v) else v for v in linha)
        for linha in df.itertuples(index=False, name=None)
    ]
    colunas_sql = ", ".join(f"[{c}]" for c in COLUNAS_TABELA)
    placeholders = ", ".join("?" for _ in COLUNAS_TABELA)

    sql = get_connection()
    conn = sql.connection
    if conn is None:
        raise RuntimeError(f"Sem conexão com o banco {sql.db_name}")

    # DELETE + INSERT na mesma transação (o sql.execute() faz commit por comando)
    try:
        cursor = conn.cursor()
        cursor.fast_executemany = True
        cursor.executemany(
            f"DELETE FROM {TABELA} WHERE [INDEX] = ? AND EFFECTIVE_DATE = ?",
            list(datas.itertuples(index=False, name=None)),
        )
        cursor.executemany(
            f"INSERT INTO {TABELA} ({colunas_sql}) VALUES ({placeholders})",
            linhas,
        )
        conn.commit()
        print(f"{len(linhas)} linhas gravadas em {sql.db_name}.{TABELA} ({len(datas)} índice/datas)")
    except Exception:
        conn.rollback()
        raise


def main():
    df = ler_input()
    try:
        salvar(df)
    finally:
        disconnect()


if __name__ == "__main__":
    main()
