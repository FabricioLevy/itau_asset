# -*- coding: utf-8 -*-
"""
Grava o relatório final do relatorio_svc (StatusValidacao_MesaGestao_*.xlsx)
no SQL Server (DBSX337), em duas tabelas (DDL em sql/):

  dbo.svc_status_validacao       foto atual: uma linha por Dt Posição +
                                 Sistema + Fundo. Fundo/dia novo é inserido,
                                 o que mudou é atualizado, o que não veio no
                                 grid fica como estava.
  dbo.svc_status_validacao_hist  histórico: uma linha na primeira vez que o
                                 fundo/dia aparece e a cada mudança de
                                 Status, Status Banda, Carga Cockpit ou
                                 Valor (com o valor anterior e o novo).

Tudo numa transação só: as linhas vão para a temporária #svc_status, um
MERGE atualiza a foto atual e devolve (OUTPUT) o que mudou, e isso vira o
histórico. Se algo falhar, nada é gravado.

A chave é a Dt Posição (data filtrada no portal com --dias/--data-posicao).
Rodando sem filtro de data, usa a Data efetiva (calculada a partir da Data
Processamento); linhas sem nenhuma das duas ("Pendente" sem processamento)
ficam de fora da carga, porque não dá para saber de que dia são.

Credenciais: variáveis de ambiente SQL_LOGIN e SQL_PASSWORD (ver sql_connection.py).
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

import pandas as pd

from status_validacao import MESA_NAO_ENCONTRADA

DB_PADRAO = "DBSX337"
TABELA_PADRAO = "svc_status_validacao"
TABELA_HIST_PADRAO = "svc_status_validacao_hist"

FORMATO_DATA = "%d/%m/%Y"
FORMATO_DATA_HORA = "%d/%m/%Y %H:%M:%S"

# colunas da #svc_status / svc_status_validacao, na ordem das tuplas de montar_linhas
COLUNAS = ["DATE_REF", "SYSTEM_CODE", "FUND", "FUND_IAM_CODE", "QUOTE_TYPE",
           "LIABILITY_CODE", "QUOTE_VALUE", "QUOTE_STATUS", "BAND_STATUS",
           "COCKPIT_LOAD", "DESK", "QUOTE_ID", "PORTFOLIO_ID", "PROCESSING_DATE"]
CHAVE = ["DATE_REF", "SYSTEM_CODE", "FUND"]

# COLLATE DATABASE_DEFAULT: a temporária nasce com a collation do tempdb, que
# pode ser diferente da DBSX337 (o MERGE compararia textos de collations diferentes)
SQL_STAGING = """
IF OBJECT_ID('tempdb..#svc_status') IS NOT NULL DROP TABLE #svc_status;
CREATE TABLE #svc_status (
    DATE_REF        DATE           NOT NULL,
    SYSTEM_CODE     VARCHAR(10)    COLLATE DATABASE_DEFAULT NOT NULL,
    FUND            VARCHAR(100)   COLLATE DATABASE_DEFAULT NOT NULL,
    FUND_IAM_CODE   VARCHAR(100)   COLLATE DATABASE_DEFAULT NULL,
    QUOTE_TYPE      VARCHAR(50)    COLLATE DATABASE_DEFAULT NULL,
    LIABILITY_CODE  VARCHAR(20)    COLLATE DATABASE_DEFAULT NULL,
    QUOTE_VALUE     DECIMAL(38,16) NULL,
    QUOTE_STATUS    VARCHAR(100)   COLLATE DATABASE_DEFAULT NULL,
    BAND_STATUS     VARCHAR(100)   COLLATE DATABASE_DEFAULT NULL,
    COCKPIT_LOAD    VARCHAR(20)    COLLATE DATABASE_DEFAULT NULL,
    DESK            VARCHAR(100)   COLLATE DATABASE_DEFAULT NULL,
    QUOTE_ID        BIGINT         NULL,
    PORTFOLIO_ID    BIGINT         NULL,
    PROCESSING_DATE DATETIME2(0)   NULL,
    PRIMARY KEY (DATE_REF, SYSTEM_CODE, FUND)
);
"""

# {tabela} e {tabela_hist} são validados em atualizar_status (só letras, números e _)
SQL_MERGE = """
SET NOCOUNT ON;
SET XACT_ABORT ON;

DECLARE @agora DATETIME2(0) = SYSDATETIME();
DECLARE @historico INT;
DECLARE @mudancas TABLE (
    CHANGE_TYPE      VARCHAR(10)    COLLATE DATABASE_DEFAULT NOT NULL,
    DATE_REF         DATE           NOT NULL,
    SYSTEM_CODE      VARCHAR(10)    COLLATE DATABASE_DEFAULT NOT NULL,
    FUND             VARCHAR(100)   COLLATE DATABASE_DEFAULT NOT NULL,
    OLD_QUOTE_STATUS VARCHAR(100)   COLLATE DATABASE_DEFAULT NULL,
    NEW_QUOTE_STATUS VARCHAR(100)   COLLATE DATABASE_DEFAULT NULL,
    OLD_BAND_STATUS  VARCHAR(100)   COLLATE DATABASE_DEFAULT NULL,
    NEW_BAND_STATUS  VARCHAR(100)   COLLATE DATABASE_DEFAULT NULL,
    OLD_COCKPIT_LOAD VARCHAR(20)    COLLATE DATABASE_DEFAULT NULL,
    NEW_COCKPIT_LOAD VARCHAR(20)    COLLATE DATABASE_DEFAULT NULL,
    OLD_QUOTE_VALUE  DECIMAL(38,16) NULL,
    NEW_QUOTE_VALUE  DECIMAL(38,16) NULL,
    QUOTE_ID         BIGINT         NULL,
    PROCESSING_DATE  DATETIME2(0)   NULL
);

-- foto atual: só atualiza a linha se alguma coluna mudou (EXCEPT compara NULL como valor)
MERGE dbo.[{tabela}] WITH (HOLDLOCK) AS t
USING #svc_status AS s
   ON  t.DATE_REF    = s.DATE_REF
   AND t.SYSTEM_CODE = s.SYSTEM_CODE
   AND t.FUND        = s.FUND
WHEN MATCHED AND EXISTS (
        SELECT s.FUND_IAM_CODE, s.QUOTE_TYPE, s.LIABILITY_CODE, s.QUOTE_VALUE, s.QUOTE_STATUS,
               s.BAND_STATUS, s.COCKPIT_LOAD, s.DESK, s.QUOTE_ID, s.PORTFOLIO_ID, s.PROCESSING_DATE
        EXCEPT
        SELECT t.FUND_IAM_CODE, t.QUOTE_TYPE, t.LIABILITY_CODE, t.QUOTE_VALUE, t.QUOTE_STATUS,
               t.BAND_STATUS, t.COCKPIT_LOAD, t.DESK, t.QUOTE_ID, t.PORTFOLIO_ID, t.PROCESSING_DATE
    ) THEN UPDATE SET
        FUND_IAM_CODE   = s.FUND_IAM_CODE,
        QUOTE_TYPE      = s.QUOTE_TYPE,
        LIABILITY_CODE  = s.LIABILITY_CODE,
        QUOTE_VALUE     = s.QUOTE_VALUE,
        QUOTE_STATUS    = s.QUOTE_STATUS,
        BAND_STATUS     = s.BAND_STATUS,
        COCKPIT_LOAD    = s.COCKPIT_LOAD,
        DESK            = s.DESK,
        QUOTE_ID        = s.QUOTE_ID,
        PORTFOLIO_ID    = s.PORTFOLIO_ID,
        PROCESSING_DATE = s.PROCESSING_DATE,
        DATE_UPDATE     = @agora
WHEN NOT MATCHED BY TARGET THEN
    INSERT (DATE_REF, SYSTEM_CODE, FUND, FUND_IAM_CODE, QUOTE_TYPE, LIABILITY_CODE,
            QUOTE_VALUE, QUOTE_STATUS, BAND_STATUS, COCKPIT_LOAD, DESK, QUOTE_ID,
            PORTFOLIO_ID, PROCESSING_DATE, DATE_LOAD, DATE_UPDATE)
    VALUES (s.DATE_REF, s.SYSTEM_CODE, s.FUND, s.FUND_IAM_CODE, s.QUOTE_TYPE, s.LIABILITY_CODE,
            s.QUOTE_VALUE, s.QUOTE_STATUS, s.BAND_STATUS, s.COCKPIT_LOAD, s.DESK, s.QUOTE_ID,
            s.PORTFOLIO_ID, s.PROCESSING_DATE, @agora, @agora)
OUTPUT $action,
       inserted.DATE_REF, inserted.SYSTEM_CODE, inserted.FUND,
       deleted.QUOTE_STATUS, inserted.QUOTE_STATUS,
       deleted.BAND_STATUS,  inserted.BAND_STATUS,
       deleted.COCKPIT_LOAD, inserted.COCKPIT_LOAD,
       deleted.QUOTE_VALUE,  inserted.QUOTE_VALUE,
       inserted.QUOTE_ID, inserted.PROCESSING_DATE
  INTO @mudancas;

-- histórico: fundo/dia novo, ou mudança em alguma das colunas acompanhadas
INSERT INTO dbo.[{tabela_hist}] (
    DATE_REF, SYSTEM_CODE, FUND, CHANGE_TYPE,
    OLD_QUOTE_STATUS, NEW_QUOTE_STATUS, OLD_BAND_STATUS, NEW_BAND_STATUS,
    OLD_COCKPIT_LOAD, NEW_COCKPIT_LOAD, OLD_QUOTE_VALUE, NEW_QUOTE_VALUE,
    QUOTE_ID, PROCESSING_DATE, DATE_LOAD)
SELECT m.DATE_REF, m.SYSTEM_CODE, m.FUND, m.CHANGE_TYPE,
       m.OLD_QUOTE_STATUS, m.NEW_QUOTE_STATUS, m.OLD_BAND_STATUS, m.NEW_BAND_STATUS,
       m.OLD_COCKPIT_LOAD, m.NEW_COCKPIT_LOAD, m.OLD_QUOTE_VALUE, m.NEW_QUOTE_VALUE,
       m.QUOTE_ID, m.PROCESSING_DATE, @agora
FROM @mudancas AS m
WHERE m.CHANGE_TYPE = 'INSERT'
   OR EXISTS (
        SELECT m.OLD_QUOTE_STATUS, m.OLD_BAND_STATUS, m.OLD_COCKPIT_LOAD, m.OLD_QUOTE_VALUE
        EXCEPT
        SELECT m.NEW_QUOTE_STATUS, m.NEW_BAND_STATUS, m.NEW_COCKPIT_LOAD, m.NEW_QUOTE_VALUE
   );
SET @historico = @@ROWCOUNT;

DROP TABLE #svc_status;

SELECT COUNT(CASE WHEN CHANGE_TYPE = 'INSERT' THEN 1 END) AS INSERTED,
       COUNT(CASE WHEN CHANGE_TYPE = 'UPDATE' THEN 1 END) AS UPDATED,
       @historico AS HISTORY
FROM @mudancas;
"""


def _log(msg: str) -> None:
    print(msg, flush=True)


def _texto(valor):
    """Texto sem espaços sobrando; vazio/NaN -> None. Número inteiro lido do
    Excel como float (57574.0) volta a ser "57574"."""
    if valor is None or pd.isna(valor):
        return None
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    texto = " ".join(str(valor).split())
    return texto or None


def _inteiro(valor):
    if valor is None or pd.isna(valor):
        return None
    try:
        return int(valor.strip()) if isinstance(valor, str) else int(valor)
    except (TypeError, ValueError):
        return None


def _decimal(valor):
    """Cota -> Decimal pelo repr do float (54557.74446 não vira 54557.744459999...)."""
    if valor is None or pd.isna(valor):
        return None
    try:
        if isinstance(valor, str):  # texto no formato BR, ex.: "1.234,5678"
            valor = valor.strip().replace(".", "").replace(",", ".")
            return Decimal(valor) if valor else None
        return Decimal(repr(float(valor)))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _datas(serie: pd.Series, formato: str) -> pd.Series:
    """Texto do Excel (dd/mm/aaaa ou dd/mm/aaaa hh:mm:ss) -> datetime; vazio/inválido -> NaT."""
    if pd.api.types.is_datetime64_any_dtype(serie):
        return serie
    return pd.to_datetime(serie.astype("string").str.strip(), format=formato, errors="coerce")


def montar_linhas(df_final: pd.DataFrame) -> list:
    """Relatório final (colunas do Excel) -> tuplas na ordem de COLUNAS, uma
    por Dt Posição + Sistema + Fundo, com tipos que o pyodbc aceita (date,
    datetime, Decimal, int, str, None)."""
    def coluna(nome):
        if nome in df_final.columns:
            return df_final[nome]
        return pd.Series(None, index=df_final.index, dtype=object)

    base = pd.DataFrame({
        "date_ref": _datas(coluna("Dt Posição"), FORMATO_DATA).fillna(
            _datas(coluna("Data"), FORMATO_DATA)),
        "sistema": coluna("Sistema").map(_texto),
        "fundo": coluna("Fundo").map(_texto),
        "processamento": _datas(coluna("Data Processamento"), FORMATO_DATA_HORA),
        "id_cota": pd.to_numeric(coluna("Id Cota"), errors="coerce"),
    }, index=df_final.index)

    sem_chave = base["date_ref"].isna() | base["sistema"].isna() | base["fundo"].isna()
    if sem_chave.any():
        _log(f"[carga_sql] aviso: {int(sem_chave.sum())} linha(s) sem Dt Posição/Data, "
             f"Sistema ou Fundo ficaram fora da carga (rode com --dias para gravar "
             f"também os 'Pendente' sem Data Processamento)")
    base = base[~sem_chave]

    # mesma chave duas vezes no grid (ex.: cota reprocessada): fica a mais recente.
    # Maiúsculas porque a collation da base não diferencia maiúsculas/minúsculas.
    base = base.assign(_sistema=base["sistema"].str.upper(), _fundo=base["fundo"].str.upper())
    base = base.sort_values(["processamento", "id_cota"], na_position="first")
    repetidas = base.duplicated(subset=["date_ref", "_sistema", "_fundo"], keep="last")
    if repetidas.any():
        _log(f"[carga_sql] aviso: {int(repetidas.sum())} linha(s) repetidas (mesma Dt Posição, "
             f"Sistema e Fundo) — gravada só a de Data Processamento mais recente")
    base = base[~repetidas]

    linhas = []
    for i, chave in base.iterrows():
        r = df_final.loc[i]
        mesa = _texto(r.get("Mesa Gestão"))
        processamento = chave["processamento"]
        linhas.append((
            chave["date_ref"].date(),
            chave["sistema"],
            chave["fundo"],
            _texto(r.get("Código IAM")),
            _texto(r.get("Tipo")),
            _texto(r.get("Passivo")),
            _decimal(r.get("Valor")),
            _texto(r.get("Status")),
            _texto(r.get("Status Banda")),
            _texto(r.get("Carga Cockpit")),
            None if mesa == MESA_NAO_ENCONTRADA else mesa,
            _inteiro(r.get("Id Cota")),
            _inteiro(r.get("Id Carteira")),
            None if pd.isna(processamento) else processamento.to_pydatetime(),
        ))
    return linhas


def atualizar_status(df_final: pd.DataFrame, db: str = DB_PADRAO,
                     tabela: str = TABELA_PADRAO,
                     tabela_hist: str = TABELA_HIST_PADRAO) -> bool:
    """Atualiza dbo.<tabela> (foto atual) e dbo.<tabela_hist> (histórico) com
    o relatório final, numa transação só (ver docstring do módulo).

    Não levanta exceção por erro de banco: só avisa e devolve False (o Excel
    já foi salvo antes de chegar aqui). Devolve True se gravou ou se não
    havia nada para gravar.
    """
    import sql_connection as sc

    for nome in (tabela, tabela_hist):
        if not re.fullmatch(r"\w+", nome):
            raise ValueError(f"nome de tabela inválido: {nome!r}")

    linhas = montar_linhas(df_final)
    if not linhas:
        _log("[carga_sql] nenhuma linha para gravar")
        return True

    colunas_sql = ", ".join(COLUNAS)
    placeholders = ", ".join("?" for _ in COLUNAS)
    conn = None
    try:
        conn = sc.get_connection(db).connection
        if conn is None:
            raise RuntimeError(f"sem conexão com o banco {db}")
        cursor = conn.cursor()
        cursor.execute(SQL_STAGING)
        # executemany sem fast_executemany: são poucas centenas de linhas, e o
        # fast_executemany não descreve parâmetros de tabela temporária
        cursor.executemany(f"INSERT INTO #svc_status ({colunas_sql}) VALUES ({placeholders})", linhas)
        cursor.execute(SQL_MERGE.format(tabela=tabela, tabela_hist=tabela_hist))
        inseridos, atualizados, historico = cursor.fetchone()
        conn.commit()
    except Exception as e:                # noqa: BLE001 — banco fora do ar não pode quebrar o relatório
        if conn is not None:
            try:
                conn.rollback()
            except Exception:             # noqa: BLE001
                pass
        _log(f"[carga_sql][AVISO] falha ao gravar em {db}.dbo.{tabela} / "
             f"{tabela_hist} (nada foi gravado): {e}")
        return False

    datas = sorted({linha[0] for linha in linhas})
    _log(f"[carga_sql] {len(linhas)} fundo(s) lidos (Dt Posição: "
         f"{', '.join(d.strftime('%d/%m/%Y') for d in datas)}) -> {db}.dbo.{tabela}: "
         f"{inseridos} novo(s), {atualizados} atualizado(s), "
         f"{len(linhas) - inseridos - atualizados} sem mudança; "
         f"{historico} linha(s) em dbo.{tabela_hist}")
    return True
