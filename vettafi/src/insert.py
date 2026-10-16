"""
Carrega na DBSX337 os arquivos que o download.py salva em output/<INDICE>/:
  - ADJ_CLOSE_CONSTITUENTS/AAAAMMDD_<INDICE>_ADJ.VFC.csv  -> dbo.rafs_composicao_indices
  - CORPORATE_ACTIONS/AAAAMMDD_<INDICE>_VFA.csv           -> dbo.rafs_corporate_actions

Carga incremental por índice: busca no SQL a última data gravada (EFFECTIVE_DATE na
composição, DATE_REF nas corporate actions) e regrava a partir dela (inclusive),
apagando e reinserindo essas datas na mesma transação. Índice ainda sem dados no SQL é
carregado desde o primeiro arquivo.

Uso: python src/insert.py   (a partir da pasta vettafi)
Credenciais: variáveis de ambiente SQL_LOGIN e SQL_PASSWORD (ver sql_connection.py)
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Context, Decimal
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from sql_connection import disconnect, get_connection

BASE_DIR = Path(__file__).resolve().parents[1]
# mesma pasta do download.py: output/<INDICE>/<SUBPASTA>/AAAAMMDD_<INDICE>_<final>.csv
OUTPUT_DIR = BASE_DIR / "output"

CONTEXTO_DECIMAL = Context(prec=38)  # precisão máxima do DECIMAL no SQL Server


@dataclass(frozen=True)
class Carga:
    """Tabela de destino e como ler os arquivos que a alimentam."""

    tabela: str
    subpasta: str  # pasta dentro de output/<INDICE>/ (a mesma do download.py)
    coluna_data: str  # data da carga incremental: regrava a partir da última do SQL
    margem: timedelta  # folga entre a data do nome do arquivo e a coluna_data
    colunas: List[str]  # colunas do INSERT (a data/hora da carga vem do default da tabela)
    chave: List[str]  # chave primária da tabela
    colunas_decimais: Dict[str, int]  # coluna -> casas decimais (igual ao DECIMAL(p,s))
    colunas_data: List[str]  # datas AAAAMMDD do arquivo
    coluna_nome_arquivo: str  # recebe o nome do arquivo
    colunas_inteiras: List[str] = field(default_factory=list)
    coluna_data_arquivo: Optional[str] = None  # recebe a data do nome do arquivo, se houver
    # as demais colunas do arquivo são texto


COLUNAS_TEXTO_COMPOSICAO = [
    "INDEX", "COMPANY_NAME", "BB_TICKER", "SEDOL", "CUSIP", "ISIN", "ID_BB_GLOBAL",
    "ICE_SECTOR_CODE", "ICE_SECTOR_NAME", "VETTAFI_CATEGORY", "MIC", "COUNTRY",
    "REGION", "SIZE", "CAP", "CURR",
]
COLUNAS_DECIMAIS_COMPOSICAO = {
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
COMPOSICAO = Carga(
    tabela="dbo.rafs_composicao_indices",
    subpasta="ADJ_CLOSE_CONSTITUENTS",
    coluna_data="EFFECTIVE_DATE",
    # o nome do arquivo tem a data do pregão anterior à EFFECTIVE_DATE; a margem cobre feriados
    margem=timedelta(days=7),
    colunas=(
        ["INDEX", "EFFECTIVE_DATE"] + COLUNAS_TEXTO_COMPOSICAO[1:]
        + list(COLUNAS_DECIMAIS_COMPOSICAO) + ["NOME_ARQUIVO"]
    ),
    chave=["INDEX", "EFFECTIVE_DATE", "ID_BB_GLOBAL"],
    colunas_decimais=COLUNAS_DECIMAIS_COMPOSICAO,
    colunas_data=["EFFECTIVE_DATE"],
    coluna_nome_arquivo="NOME_ARQUIVO",
)

# colunas do VFA na ordem do arquivo
COLUNAS_VFA = [
    "INDEX", "EFF_DATE", "EVENT", "SEQUENCE", "CA_DESCRIPTION", "CURRENT_COMPANY_NAME",
    "NEW_COMPANY_NAME", "CURRENT_TICKER", "NEW_TICKER", "CURRENT_SEDOL", "NEW_SEDOL",
    "CURRENT_CUSIP", "NEW_CUSIP", "CURRENT_ISIN", "NEW_ISIN", "ID_BB_GLOBAL", "STK_CURN",
    "DIV_CURN", "DIVIDEND", "NET_DIVIDEND", "TAX_RATE", "FRANKED_PCT", "SHARES_HELD",
    "SHARES_RECEIVED", "SUBSCRIPTION_OFFER_PRICE", "SUBSCRIPTION_OFFER_CURRENCY", "ADJ_FACTOR",
    "CURRENT_SHARES_OUTSTANDING", "NEW_SHARES_OUTSTANDING", "CURRENT_FLOAT", "NEW_FLOAT",
    "CURRENT_WAF", "NEW_WAF", "CURRENT_INDEX_SHARES", "ADJUSTED_INDEX_SHARES", "CURRENT_PRICE",
    "ADJUSTED_PRICE", "SPIN_ACQUIRER_COMPANY_NAME", "SPIN_ACQUIRER_TICKER", "SPIN_ACQUIRER_ISIN",
    "DIVA_EX_DATE_INDEX_SHARES", "DIVA_EX_DATE_FX_RATE", "DIVA_EX_DATE_DIVISOR",
    "ADJUSTMENT_DIVIDEND_POINTS", "ADJUSTMENT_NET_DIVIDEND_POINTS", "CORPORATE_ACTION_NOTES",
]
# todas as colunas numéricas do VFA são DECIMAL(38,16) na tabela
COLUNAS_DECIMAIS_VFA = dict.fromkeys([
    "DIVIDEND", "NET_DIVIDEND", "TAX_RATE", "FRANKED_PCT", "SHARES_HELD", "SHARES_RECEIVED",
    "SUBSCRIPTION_OFFER_PRICE", "ADJ_FACTOR", "CURRENT_SHARES_OUTSTANDING",
    "NEW_SHARES_OUTSTANDING", "CURRENT_FLOAT", "NEW_FLOAT", "CURRENT_WAF", "NEW_WAF",
    "CURRENT_INDEX_SHARES", "ADJUSTED_INDEX_SHARES", "CURRENT_PRICE", "ADJUSTED_PRICE",
    "DIVA_EX_DATE_INDEX_SHARES", "DIVA_EX_DATE_FX_RATE", "DIVA_EX_DATE_DIVISOR",
    "ADJUSTMENT_DIVIDEND_POINTS", "ADJUSTMENT_NET_DIVIDEND_POINTS",
], 16)
CORPORATE_ACTIONS = Carga(
    tabela="dbo.rafs_corporate_actions",
    subpasta="CORPORATE_ACTIONS",
    # cada arquivo é uma foto dos eventos anunciados: a data da foto vem do nome do arquivo
    coluna_data="DATE_REF",
    margem=timedelta(days=0),
    colunas=["INDEX", "DATE_REF"] + COLUNAS_VFA[1:] + ["FILE_NAME"],
    chave=["DATE_REF", "INDEX", "EFF_DATE", "ID_BB_GLOBAL", "EVENT", "SEQUENCE"],
    colunas_decimais=COLUNAS_DECIMAIS_VFA,
    colunas_data=["EFF_DATE"],
    coluna_nome_arquivo="FILE_NAME",
    colunas_inteiras=["SEQUENCE"],
    coluna_data_arquivo="DATE_REF",
)

CARGAS = [COMPOSICAO, CORPORATE_ACTIONS]


def data_do_arquivo(caminho: Path) -> date:
    return datetime.strptime(caminho.name[:8], "%Y%m%d").date()


def ultima_data_por_indice(conn, carga: Carga) -> Dict[str, date]:
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT [INDEX], MAX([{carga.coluna_data}]) FROM {carga.tabela} GROUP BY [INDEX]"
    )
    return {indice: data for indice, data in cursor.fetchall()}


def para_decimal(valor, casas):
    if pd.isna(valor) or valor == "":
        return None
    return Decimal(valor).quantize(Decimal(1).scaleb(-casas), context=CONTEXTO_DECIMAL)


def ler_arquivo(caminho: Path, carga: Carga) -> pd.DataFrame:
    df = pd.read_csv(caminho, dtype=str, keep_default_na=False, na_values=[""])
    # o rodapé "line count = N", quando existe, só preenche a primeira coluna
    df = df.dropna(subset=carga.colunas_data).copy()

    tipadas = carga.colunas_data + carga.colunas_inteiras + list(carga.colunas_decimais)
    for col in df.columns.difference(tipadas):
        df[col] = df[col].str.strip()
    for col in carga.colunas_data:
        df[col] = pd.to_datetime(df[col], format="%Y%m%d").dt.date
    for col in carga.colunas_inteiras:
        df[col] = df[col].map(lambda v: None if pd.isna(v) else int(v))
    for col, casas in carga.colunas_decimais.items():
        df[col] = df[col].map(lambda v, c=casas: para_decimal(v, c))
    if carga.coluna_data_arquivo:
        df[carga.coluna_data_arquivo] = data_do_arquivo(caminho)
    df[carga.coluna_nome_arquivo] = caminho.name
    return df[carga.colunas]


def arquivo_necessario(caminho: Path, ultimas: Dict[str, date], margem: timedelta) -> bool:
    """Evita reler o histórico: arquivos AAAAMMDD_<INDICE>_... ."""
    ultima = ultimas.get(caminho.name.split("_")[1])
    if ultima is None:
        return True
    return data_do_arquivo(caminho) >= ultima - margem


def ler_input(carga: Carga, ultimas: Dict[str, date]) -> pd.DataFrame:
    pasta = OUTPUT_DIR / "<INDICE>" / carga.subpasta  # só para as mensagens
    arquivos = sorted(OUTPUT_DIR.glob(f"*/{carga.subpasta}/*.csv"))
    if not arquivos:
        print(f"[aviso] nenhum CSV em {pasta}")
        return pd.DataFrame(columns=carga.colunas)
    arquivos = [a for a in arquivos if arquivo_necessario(a, ultimas, carga.margem)]
    print(f"Lendo {len(arquivos)} arquivos de {pasta}")
    if not arquivos:
        return pd.DataFrame(columns=carga.colunas)

    df = pd.concat([ler_arquivo(a, carga) for a in arquivos], ignore_index=True)
    limite = df["INDEX"].map(lambda i: ultimas.get(i, date.min))
    df = df[df[carga.coluna_data] >= limite]

    sem_chave = df[carga.chave].isna().any(axis=1)
    if sem_chave.any():
        raise ValueError(f"Linhas sem valor na chave {carga.chave}:\n{df[sem_chave]}")
    duplicados = df.duplicated(carga.chave, keep=False)
    if duplicados.any():
        raise ValueError(f"Linhas duplicadas na chave:\n{df[duplicados]}")
    return df


def salvar(conn, df: pd.DataFrame, carga: Carga, db_name: str):
    inicio_por_indice = df.groupby("INDEX")[carga.coluna_data].min()
    linhas = [
        tuple(None if pd.isna(v) else v for v in linha)
        for linha in df.itertuples(index=False, name=None)
    ]
    colunas_sql = ", ".join(f"[{c}]" for c in carga.colunas)
    placeholders = ", ".join("?" for _ in carga.colunas)

    # DELETE + INSERT na mesma transação (o sql.execute() faz commit por comando)
    try:
        cursor = conn.cursor()
        cursor.fast_executemany = True
        cursor.executemany(
            f"DELETE FROM {carga.tabela} WHERE [INDEX] = ? AND [{carga.coluna_data}] >= ?",
            list(inicio_por_indice.items()),
        )
        cursor.executemany(
            f"INSERT INTO {carga.tabela} ({colunas_sql}) VALUES ({placeholders})",
            linhas,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    print(f"{len(linhas)} linhas gravadas em {db_name}.{carga.tabela}:")
    for indice, datas in df.groupby("INDEX")[carga.coluna_data]:
        print(f"  {indice}: {datas.min()} a {datas.max()} ({datas.nunique()} datas)")


def carregar(conn, carga: Carga, db_name: str):
    ultimas = ultima_data_por_indice(conn, carga)
    for indice, data in sorted(ultimas.items()):
        print(f"Última {carga.coluna_data} em {carga.tabela} - {indice}: {data}")

    df = ler_input(carga, ultimas)
    if df.empty:
        print(f"Nenhuma data nova para {carga.tabela}.")
        return
    salvar(conn, df, carga, db_name)


def main():
    sql = get_connection()
    conn = sql.connection
    if conn is None:
        raise RuntimeError(f"Sem conexão com o banco {sql.db_name}")

    try:
        for carga in CARGAS:
            carregar(conn, carga, sql.db_name)
    finally:
        disconnect()


if __name__ == "__main__":
    main()
