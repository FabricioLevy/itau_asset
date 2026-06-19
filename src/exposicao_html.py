
# ═══════════════════════════════════════════════════════════════════════════════
# Relatório de Exposição, Rolagem e Rentabilidade
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations
from typing import Dict, List, Optional

import os
import sys
import numpy as np
import pandas as pd
from datetime import date
import QuantLib as ql
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.image as mpimg
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

import sql_connection as sql

INPUT_EXCEL    = "../input/fundos_exposicao.xlsx"
INPUT_FUNDOS_ROL = "../input/fundos.txt"
LOGO_PATH      = "../input/logo.png"
OUTPUT_BASE    = "../output/relatorios"

SHEETS = [
    "SINGLES", 
    "IBOV", 
    "ETFs", 
    "S&P500", 
    "OFFSHORES",
    "MOEDAS", 
    "RENDA FIXA",
    "OURO e TREASURY",
    "DEBENTURES", 
    "ACWI", 
    "CDI",
]

ITAU_DARK   = "#000D3C"
ITAU_ORANGE = "#EC7000"
ITAU_WHITE  = "#ffffff"
ITAU_GRAY   = "#e0e0e0"
ITAU_GRAY2  = "#aaaaaa"
ITAU_RED    = "#c0392b"
ITAU_GREEN  = "#1e7e34"
ROW_PAR     = "#eaf0fb"

_MES_COD  = {1:"F",2:"G",3:"H",4:"J",5:"K",6:"M",7:"N",8:"Q",9:"U",10:"V",11:"X",12:"Z"}
_GRUP_DOL = {"DOL", "WDO"}
# ciclo em meses entre vencimentos consecutivos por família de contrato
_VENC_CYCLE = {"DOL_WDO": 1, "WIN": 2, "WEU": 2, "ISP": 3, "WSP": 3}

# None = exibe todos os grupos encontrados no banco
# Lista = exibe APENAS os grupos especificados
# Exemplos: "DOL_WDO", "ISP", "IND", "DI1", "BGI", "CCM"
GRUPOS_ROLAGEM: Optional[List[str]] = None

# Grupos a EXCLUIR do relatório (tem prioridade sobre GRUPOS_ROLAGEM)
# Exemplo para remover DI: GRUPOS_ROLAGEM_EXCLUIR = ["DI1"]
# 0 = apenas o mês de referência; N = inclui os N meses seguintes também
# Exemplo: 2 → mostra v1 no mês atual, mês+1 e mês+2
ROLAGEM_MESES_ADICIONAIS: int = 0
GRUPOS_ROLAGEM_EXCLUIR: List[str] = ["DI1", "DAP"]


def ler_fundos_rol() -> List[str]:
    if not os.path.exists(INPUT_FUNDOS_ROL):
        print(f"  [AVISO] {INPUT_FUNDOS_ROL} não encontrado — rolagem ignorada.")
        return []
    with open(INPUT_FUNDOS_ROL) as f:
        return [l.strip() for l in f if l.strip()]


def _ids(fundos: List[str]) -> str:
    return ", ".join(f"'{f}'" for f in fundos)

def _scalar(db, q: str) -> float:
    try:
        d = db.run_query(q)
        return float("nan") if (d is None or len(d) == 0) else float(d.iloc[0, 0])
    except Exception:
        return float("nan")

def _to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0)

def _fmt_money(x) -> str:
    try:
        return "" if pd.isna(x) else f"R$ {float(x):,.2f}"
    except Exception:
        return ""

def _fmt_pct(x) -> str:
    try:
        return "" if pd.isna(x) else f"{float(x):.2%}"
    except Exception:
        return ""

def _fmt_pct3(x) -> str:
    try:
        return "" if pd.isna(x) else f"{float(x):.3%}"
    except Exception:
        return ""

def _fmt_text(x) -> str:
    try:
        if pd.isna(x): return ""
        s = str(x).strip()
        return "" if s.lower() in ("nan", "none") else s
    except Exception:
        return ""

def _networkdays(dt_ref: pd.Timestamp, dt_venc: pd.Timestamp) -> int:
    if pd.isna(dt_venc):
        return 0
    return len(pd.bdate_range(dt_ref, dt_venc))

def output_dir_for_date(dt: str) -> str:
    return os.path.join(OUTPUT_BASE, pd.to_datetime(dt).strftime("%Y%m%d"))

# ─────────────────────────────────────────────────────────────────────────────
# LEITURA DO EXCEL
# ─────────────────────────────────────────────────────────────────────────────

def ler_exposicao_excel(path: str) -> Dict[str, pd.DataFrame]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Arquivo nao encontrado: {path}")

    xls = pd.ExcelFile(path)
    out: Dict[str, pd.DataFrame] = {}

    for sheet in SHEETS:
        if sheet not in xls.sheet_names:
            out[sheet] = pd.DataFrame(columns=["FUNDO", "BENCH", "MAX", "MIN"])
            continue

        df = pd.read_excel(path, sheet_name=sheet)
        cl = {c: str(c).strip().lower() for c in df.columns}

        def fc(*cands):
            for c in cands:
                for orig, low in cl.items():
                    if low == c:
                        return orig
            return None

        df_out = pd.DataFrame()
        df_out["FUNDO"] = df[fc("fundos","fundo","fundo(s)","nome")] \
            if fc("fundos","fundo","fundo(s)","nome") else pd.Series(dtype="object")
        df_out["BENCH"] = df[fc("bench","benchmark","indice","índice")] \
            if fc("bench","benchmark","indice","índice") else pd.Series(dtype="object")
        df_out["MAX"]   = df[fc("maximo","max","máximo")] \
            if fc("maximo","max","máximo") else pd.Series(dtype="float")
        df_out["MIN"]   = df[fc("minimo","min","mínimo")] \
            if fc("minimo","min","mínimo") else pd.Series(dtype="float")

        df_out["FUNDO"] = df_out["FUNDO"].astype(str).str.strip()
        df_out = df_out[df_out["FUNDO"].notna() & (df_out["FUNDO"] != "")].copy()
        df_out["BENCH"] = df_out["BENCH"].astype(str).str.strip()
        df_out.loc[df_out["BENCH"].isin(["nan","None",""]), "BENCH"] = ""
        # normaliza espaços ao redor do asterisco: "IBOV *0,4" → "IBOV*0,4"
        df_out["BENCH"] = df_out["BENCH"].str.replace(r'\s*\*\s*', '*', regex=True)
        out[sheet] = df_out.reset_index(drop=True)

    return out


def buscar_fx(dt: str) -> Dict[str, float]:
    db = sql.get_connection()

    def q_moeda(quote: str) -> str:
        return f"""
            SELECT TOP 1 preco_limpo
            FROM dbsx337.dbo.fundos_dados_moedas WITH (NOLOCK)
            WHERE date = '{dt}'
              AND codigo_iam_moeda_base  = 'BRL_B3_2'
              AND codigo_iam_moeda_quote = '{quote}'
        """

    q_cny = f"""
        SELECT TOP 1 preco_limpo
        FROM dbsx337.dbo.FUNDOS_DADOS_INDICES WITH (NOLOCK)
        WHERE date = '{dt}' AND codigo_iam_indice = 'CNYXBR10'
    """

    fx = {
        "USD_BRL" : _scalar(db, q_moeda("USD")),
        "GBP_BRL" : _scalar(db, q_moeda("GBP")),
        "EUR_BRL" : _scalar(db, q_moeda("EUR")),
        "CNYXBR10": _scalar(db, q_cny),
    }
    print(f"  FX: USD={fx['USD_BRL']:.4f} | GBP={fx['GBP_BRL']:.4f} | "
          f"EUR={fx['EUR_BRL']:.4f} | CNY={fx['CNYXBR10']:.6f}")
    return fx

# ─────────────────────────────────────────────────────────────────────────────
# PL — view_vcraplsi
# ─────────────────────────────────────────────────────────────────────────────

def buscar_pl(dt: str, fundos: List[str]) -> Dict[str, float]:
    if not fundos:
        return {}
    q = f"""
        SELECT clcli_cd, vl_patrliqtot1 AS PL
        FROM   dbsx337.dbo.view_vcraplsi WITH (NOLOCK)
        WHERE  dt = '{dt}' AND clcli_cd IN ({_ids(fundos)})
    """
    db = sql.get_connection()
    df = db.run_query(q)
    if df is None or len(df) == 0:
        return {}
    return dict(zip(df["clcli_cd"].astype(str),
                    pd.to_numeric(df["PL"], errors="coerce")))


def buscar_prv(dt: str, fundos: List[str], fx: Dict[str, float]) -> Dict[str, float]:
    if not fundos:
        return {}

    db = sql.get_connection()

    # 1. Quantidades e preço — VIEW_vcraprv SOMENTE (sem JOIN para evitar produto cartesiano)
    q_prv = f"""
        SELECT clcli_cd                AS FUNDO,
               acao                    AS ACAO,
               SUM(qtdbloq)            AS QTDBLOQ,
               SUM(qtddisp)            AS QTDDISP,
               MAX(vl_preco_mercmedio) AS PRECO
        FROM   DBSX337.dbo.VIEW_vcraprv WITH (NOLOCK)
        WHERE  dt = '{dt}'
          AND  clcli_cd IN ({_ids(fundos)})
        GROUP BY clcli_cd, acao
    """

    # 2. Moeda por ticker — VIEW_FUNDOS_POSICAO separado (um registro por ativo)
    q_moeda = f"""
        SELECT ticker_bolsa     AS ACAO,
               MAX(moeda_ativo) AS MOEDA
        FROM   DBSX337.dbo.VIEW_FUNDOS_POSICAO WITH (NOLOCK)
        WHERE  date = '{dt}' AND tipo = 'Equity'
        GROUP BY ticker_bolsa
    """

    # 3. Ajuste de aluguel BTC (replica sql_ALUGUEL do VBA)
    q_btc = f"""
        SELECT CLCLI_CD AS FUNDO,
               CODPAP   AS ACAO,
               SUM(CASE
                     WHEN IC_TIPO_MOVIMENTO = 'Doador'  THEN  QUANTIDADE
                     WHEN IC_TIPO_MOVIMENTO = 'Tomador' THEN -QUANTIDADE
                     ELSE QUANTIDADE
                   END) AS QTD_BTC
        FROM   dbsx337.dbo.VIEW_VCRABTC WITH (NOLOCK)
        WHERE  dt = '{dt}'
          AND  CLCLI_CD IN ({_ids(fundos)})
        GROUP BY CLCLI_CD, CODPAP
    """

    df_prv   = db.run_query(q_prv)
    df_moeda = db.run_query(q_moeda)
    df_btc   = db.run_query(q_btc)

    empty_prv = df_prv is None or df_prv.empty
    empty_btc = df_btc is None or df_btc.empty
    if empty_prv and empty_btc:
        return {}

    if empty_prv:
        df_prv = pd.DataFrame(columns=["FUNDO","ACAO","QTDBLOQ","QTDDISP","PRECO"])
    if df_moeda is None or df_moeda.empty:
        df_moeda = pd.DataFrame(columns=["ACAO","MOEDA"])
    if empty_btc:
        df_btc = pd.DataFrame(columns=["FUNDO","ACAO","QTD_BTC"])

    for col in ["QTDBLOQ","QTDDISP","PRECO"]:
        df_prv[col] = pd.to_numeric(df_prv[col], errors="coerce").fillna(0)
    df_btc["QTD_BTC"] = pd.to_numeric(df_btc["QTD_BTC"], errors="coerce").fillna(0)

    # União de pares (FUNDO, ACAO) — replica sql_join + sql_join2 do VBA
    keys = pd.concat([
        df_prv[["FUNDO","ACAO"]],
        df_btc[["FUNDO","ACAO"]],
    ]).drop_duplicates().reset_index(drop=True)

    df = keys.merge(df_prv, on=["FUNDO","ACAO"], how="left")
    df = df.merge(df_moeda, on="ACAO",           how="left")   # moeda por ticker
    df = df.merge(df_btc,   on=["FUNDO","ACAO"], how="left")

    df[["QTDBLOQ","QTDDISP","PRECO","QTD_BTC"]] = \
        df[["QTDBLOQ","QTDDISP","PRECO","QTD_BTC"]].fillna(0)

    # Quantidade líquida — col O da aba TEMP
    # df["NET_QTY"] = df["QTDBLOQ"] + df["QTDDISP"] + df["QTD_BTC"]

    df["NET_QTY"] = (df["QTDBLOQ"] + df["QTDDISP"] + df["QTD_BTC"]).fillna(0)

    # Valor em moeda local — col P da aba TEMP
    df["VALOR_LOCAL"] = df["NET_QTY"] * df["PRECO"]
    mask_special = (df["FUNDO"] == "EMERGFIA54431") & (df["ACAO"] == "EXCS LN")
    df.loc[mask_special, "VALOR_LOCAL"] *= 100.0

    # Câmbio — replica col N de Consulta do VBA
    usd = fx.get("USD_BRL",  float("nan"))
    gbp = fx.get("GBP_BRL",  float("nan"))
    cny = fx.get("CNYXBR10", float("nan"))

    moeda  = df["MOEDA"].fillna("").astype(str).str.strip().str.upper()
    sufixo = df["ACAO"].fillna("").astype(str).str[-2:].str.upper()

    moeda_efe = moeda.copy()
    sem_moeda = moeda_efe.isin(["", "BRL", "NAN", "NONE"])
    moeda_efe.loc[sem_moeda & (sufixo == "US")] = "USD"
    moeda_efe.loc[sem_moeda & (sufixo == "LN")] = "GBP"

    val = df["VALOR_LOCAL"].copy()
    brl = pd.Series(0.0, index=df.index, dtype="float64")

    mask = moeda_efe.isin(["USD", "IX"])
    if not np.isnan(usd):
        adj = val.copy()
        adj.loc[moeda_efe == "IX"] *= 100.0
        brl.loc[mask] = adj.loc[mask] * usd

    # mask = moeda_efe.eq("GBP")
    # if not np.isnan(gbp):
    #     brl.loc[mask] = val.loc[mask] * gbp / 100.0

    mask_gbp = moeda_efe.eq("GBP")
    if not np.isnan(gbp):
        adj = val.copy()
        adj.loc[mask_gbp & (df["PRECO"] > 100)] /= 100.0
        brl.loc[mask_gbp] = adj.loc[mask_gbp] * gbp


    mask = moeda_efe.isin(["CNY", "CNY_10H"])
    if not np.isnan(cny) and cny != 0:
        brl.loc[mask] = val.loc[mask] / cny

    convertido = moeda_efe.isin(["USD", "IX", "GBP", "CNY", "CNY_10H"])
    brl.loc[~convertido] = val.loc[~convertido]

    df["PRV_BRL"] = brl
    return df.groupby("FUNDO")["PRV_BRL"].sum().to_dict()

# ─────────────────────────────────────────────────────────────────────────────
# FUTUROS — view_vcrapfut
# Notional : qt × vl_varponto × vl_precomerc  (B3, já em BRL)
# FUT DI1  : qt × NETWORKDAYS(dt_ref, dt_vencto)  [col BJ do VBA]
# ─────────────────────────────────────────────────────────────────────────────

def buscar_futuro(dt: str, fundos: List[str]) -> Dict[str, float]:
    if not fundos:
        return {}

    q = f"""
        SELECT clcli_cd AS FUNDO,
               qt,
               vl_varponto,
               vl_precomerc,
               fuvct_fuatv_cd AS ATIVO,
               dt_vencto
        FROM   dbsx337.dbo.view_vcrapfut WITH (NOLOCK)
        WHERE  dt = '{dt}'
        AND  clcli_cd IN ({_ids(fundos)})
    """
    db = sql.get_connection()
    df = db.run_query(q)
    # print(df.columns)
    # quit()
    if df is None or len(df) == 0:
        return {}

    df["qt"]           = _to_num(df["qt"])
    df["vl_varponto"]  = _to_num(df["vl_varponto"])
    df["vl_precomerc"] = _to_num(df["vl_precomerc"])
    df["ATIVO"]        = df["ATIVO"].astype(str).str.strip().str.upper()
    df["dt_vencto"]    = pd.to_datetime(df["dt_vencto"], errors="coerce")

    dt_ref = pd.Timestamp(dt)
    df["NOTIONAL"] = df["qt"] * df["vl_varponto"] * df["vl_precomerc"]

    # mask_di1 = df["ATIVO"] == "FUT DI1"
    # if mask_di1.any():
    #     df.loc[mask_di1, "NOTIONAL"] = df.loc[mask_di1].apply(
    #         # lambda r: r["qt"] * _networkdays(dt_ref, r["dt_vencto"]), axis=1
    #         lambda r: r["qt"] * max(_networkdays(dt_ref, r["dt_vencto"]), 0)
    #     )

    mask_di1 = df["ATIVO"] == "FUT DI1"
    if mask_di1.any():
        dias = df.loc[mask_di1, "dt_vencto"].apply(
            lambda d: max(_networkdays(dt_ref, d), 0)
        )

        df.loc[mask_di1, "NOTIONAL"] = df.loc[mask_di1, "qt"] * dias


    return df.groupby("FUNDO")["NOTIONAL"].sum().to_dict()

# ─────────────────────────────────────────────────────────────────────────────
# COTAS — view_vcrapfdo  SUM(vl_liq)
# ─────────────────────────────────────────────────────────────────────────────

# def buscar_cotas(dt: str, fundos: List[str]) -> Dict[str, float]:
#     if not fundos:
#         return {}

#     q = f"""
#         SELECT clcli_cd AS FUNDO, SUM(vl_liq) AS COTAS
#         FROM   dbsx337.dbo.view_vcrapfdo WITH (NOLOCK)
#         WHERE  dt = '{dt}' AND clcli_cd IN ({_ids(fundos)})
#         GROUP BY clcli_cd
#     """
#     db = sql.get_connection()
#     df = db.run_query(q)
#     if df is None or len(df) == 0:
#         return {}
#     return dict(zip(df["FUNDO"].astype(str), _to_num(df["COTAS"])))

def buscar_cotas(dt: str, fundos: List[str]) -> Dict[str, float]:
    if not fundos:
        return {}

    q = f"""
        SELECT clcli_cd AS FUNDO, SUM(vl_total) AS COTAS
        FROM   dbsx337.dbo.view_vcrapfdo WITH (NOLOCK)
        WHERE  dt = '{dt}' AND clcli_cd IN ({_ids(fundos)})
        GROUP BY clcli_cd
    """
    db = sql.get_connection()
    df = db.run_query(q)
    if df is None or len(df) == 0:
        return {}
    return dict(zip(df["FUNDO"].astype(str), _to_num(df["COTAS"])))


def buscar_cotas_total(dt: str, fundos: List[str]) -> Dict[str, float]:
    """SUM(vl_total) de view_vcrapfdo — captura posições bloqueadas (vl_liq
    cobre apenas a parcela líquida; fundos 'bloqueados' têm o grosso em vl_total)."""
    if not fundos:
        return {}

    q = f"""
        SELECT clcli_cd AS FUNDO, SUM(vl_total) AS COTAS
        FROM   dbsx337.dbo.view_vcrapfdo WITH (NOLOCK)
        WHERE  dt = '{dt}' AND clcli_cd IN ({_ids(fundos)})
        GROUP BY clcli_cd
    """
    db = sql.get_connection()
    df = db.run_query(q)
    if df is None or len(df) == 0:
        return {}
    return dict(zip(df["FUNDO"].astype(str), _to_num(df["COTAS"])))

# ─────────────────────────────────────────────────────────────────────────────
# ROLAGEM — posição por vencimento (v1 → v2) para cada grupo de futuro
# ─────────────────────────────────────────────────────────────────────────────

######################################################################################################
######################################################################################################
######################################################################################################


def buscar_rolagem(dt: str, fundos: List[str]) -> List[tuple]:
    if not fundos:
        return []

    q_fut = f"""
        SELECT clcli_cd AS FUNDO,
               ISNULL(qt,0)*ISNULL(vl_varponto,0)*ISNULL(vl_precomerc,0) AS Notional,
               dt_vencto,
               fuvct_fuatv_cd AS ATIVO
        FROM   dbsx337.dbo.view_vcrapfut WITH(NOLOCK)
        WHERE  dt = '{dt}' AND clcli_cd IN ({_ids(fundos)})
    """
    db     = sql.get_connection()
    df_fut = db.run_query(q_fut)
    pl_map = buscar_pl(dt, fundos)

    if df_fut is None or df_fut.empty or not pl_map:
        return []

    df_pl = pd.DataFrame(list(pl_map.items()), columns=["FUNDO", "PL"])

    df_fut["Notional"]  = pd.to_numeric(df_fut["Notional"], errors="coerce").fillna(0)
    df_fut["dt_vencto"] = pd.to_datetime(df_fut["dt_vencto"], errors="coerce")
    df_fut = df_fut.dropna(subset=["dt_vencto"])
    df_fut["vencimento"] = df_fut["dt_vencto"].apply(
        lambda d: f"{_MES_COD[d.month]}{str(d.year)[-2:]}"
    )

    dt_ref_ts = pd.Timestamp(dt)
    df_fut    = df_fut[df_fut["dt_vencto"] >= dt_ref_ts]

    def _norm(a: str) -> str:
        return str(a).replace("FUT ", "").strip()

    ativos_norm = df_fut["ATIVO"].apply(_norm).unique()
    grupos      = ["DOL_WDO"] + [a for a in ativos_norm if a not in _GRUP_DOL]
    if GRUPOS_ROLAGEM is not None:
        grupos = [g for g in grupos if g in GRUPOS_ROLAGEM]
    if GRUPOS_ROLAGEM_EXCLUIR:
        grupos = [g for g in grupos if g not in GRUPOS_ROLAGEM_EXCLUIR]

    dt_ref_pd  = pd.to_datetime(dt)
    valid_venc = {
        f"{_MES_COD[(dt_ref_pd + pd.DateOffset(months=i)).month]}"
        f"{(dt_ref_pd + pd.DateOffset(months=i)).strftime('%y')}"
        for i in range(ROLAGEM_MESES_ADICIONAIS + 1)
    }

    resultado = []
    for grupo in grupos:
        if grupo == "DOL_WDO":
            mask  = df_fut["ATIVO"].apply(lambda a: _norm(a) in _GRUP_DOL)
            label = "FUT DOL + WDO"
        else:
            mask  = df_fut["ATIVO"].apply(lambda a: _norm(a) == grupo)
            label = f"FUT {grupo}"

        df_g = df_fut[mask].copy()
        if df_g.empty:
            continue

        # ordena por data real para cruzamentos de ano ficarem corretos
        vct_dates = df_g.groupby("vencimento")["dt_vencto"].min().sort_values()
        vcts = vct_dates.index.tolist()
        if not vcts:
            continue

        v1 = vcts[0]
        if v1 not in valid_venc:
            continue

        if len(vcts) >= 2:
            v2 = vcts[1]
        else:
            cycle = _VENC_CYCLE.get(grupo, 3)
            dt_next = vct_dates.iloc[0] + pd.DateOffset(months=cycle)
            v2 = f"{_MES_COD[dt_next.month]}{str(dt_next.year)[-2:]}"

        df_g  = df_g[df_g["vencimento"].isin([v1, v2])]
        df_grp = df_g.groupby(["FUNDO","vencimento"])["Notional"].sum().reset_index()

        total = df_grp.groupby("FUNDO")["Notional"].sum().reset_index()
        total.rename(columns={"Notional":"total_fut"}, inplace=True)

        df_tab = df_pl.merge(total, on="FUNDO", how="inner")
        n1 = df_grp[df_grp.vencimento==v1].groupby("FUNDO")["Notional"].sum().reset_index()
        n2 = df_grp[df_grp.vencimento==v2].groupby("FUNDO")["Notional"].sum().reset_index()
        n1.rename(columns={"Notional":"not_v1"}, inplace=True)
        n2.rename(columns={"Notional":"not_v2"}, inplace=True)

        df_tab = (df_tab.merge(n1, on="FUNDO", how="left")
                        .merge(n2, on="FUNDO", how="left")
                        .fillna(0))
        df_tab = df_tab[(df_tab["not_v1"] != 0) | (df_tab["not_v2"] != 0)]
        if df_tab.empty:
            continue

        # pl_s  = pd.to_numeric(df_tab["PL"], errors="coerce").replace(0, np.nan)
        # fut_s = df_tab["total_fut"]

        # df_tab["FUTURO"]              = label
        # df_tab[f"Pos {v1} % PL"]     = df_tab["not_v1"] / pl_s
        # df_tab[f"Pos {v2} % PL"]     = df_tab["not_v2"] / pl_s
        # df_tab[f"{v1} % FUT"]        = df_tab["not_v1"].abs() / fut_s.abs()
        # df_tab[f"{v2} % FUT"]        = df_tab["not_v2"].abs() / fut_s.abs()

        pl_s = pd.to_numeric(df_tab["PL"], errors="coerce").replace(0, np.nan)

        # denominador correto = soma dos absolutos
        fut_s = df_tab["not_v1"].abs() + df_tab["not_v2"].abs()
        fut_s = fut_s.replace(0, np.nan)

        df_tab["FUTURO"]          = label
        df_tab[f"Pos {v1} % PL"] = df_tab["not_v1"] / pl_s
        df_tab[f"Pos {v2} % PL"] = df_tab["not_v2"] / pl_s

        # distribuição correta da rolagem
        df_tab[f"{v1} % FUT"] = df_tab["not_v1"].abs() / fut_s
        df_tab[f"{v2} % FUT"] = df_tab["not_v2"].abs() / fut_s

        cols = ["FUNDO","PL","FUTURO",
                f"Pos {v1} % PL", f"Pos {v2} % PL",
                f"{v1} % FUT",    f"{v2} % FUT"]
        resultado.append((label, df_tab[cols].copy(), v1, v2))
        print(f"    [ROLAGEM] {label}: {v1} >> {v2}")

    return resultado



######################################################################################################
######################################################################################################
######################################################################################################



# ─────────────────────────────────────────────────────────────────────────────
# PIBB11 / SPXI11 — valores BRL das posições nesses tickers específicos
# ─────────────────────────────────────────────────────────────────────────────

def buscar_pibb11_spxi11(dt: str, fundos: List[str]) -> Dict[str, Dict[str, float]]:
    if not fundos:
        return {}

    db = sql.get_connection()

    # quantidade + preço — mesma lógica de buscar_prv
    q_prv = f"""
        SELECT clcli_cd             AS FUNDO,
               acao                 AS TICKER,
               SUM(qtdbloq + qtddisp) AS QTD,
               MAX(vl_preco_mercmedio) AS PRECO
        FROM   DBSX337.dbo.VIEW_vcraprv WITH (NOLOCK)
        WHERE  dt = '{dt}'
          AND  clcli_cd IN ({_ids(fundos)})
          AND  acao IN ('PIBB11', 'SPXI11')
        GROUP BY clcli_cd, acao
    """

    # ajuste de aluguel BTC — mesma lógica de buscar_prv
    q_btc = f"""
        SELECT CLCLI_CD AS FUNDO,
               CODPAP   AS TICKER,
               SUM(CASE
                     WHEN IC_TIPO_MOVIMENTO = 'Doador'  THEN  QUANTIDADE
                     WHEN IC_TIPO_MOVIMENTO = 'Tomador' THEN -QUANTIDADE
                     ELSE QUANTIDADE
                   END) AS QTD_BTC
        FROM   dbsx337.dbo.VIEW_VCRABTC WITH (NOLOCK)
        WHERE  dt = '{dt}'
          AND  CLCLI_CD IN ({_ids(fundos)})
          AND  CODPAP IN ('PIBB11', 'SPXI11')
        GROUP BY CLCLI_CD, CODPAP
    """

    df_prv = db.run_query(q_prv)
    df_btc = db.run_query(q_btc)

    empty_prv = df_prv is None or df_prv.empty
    empty_btc = df_btc is None or df_btc.empty
    if empty_prv and empty_btc:
        return {}

    if empty_prv:
        df_prv = pd.DataFrame(columns=["FUNDO", "TICKER", "QTD", "PRECO"])
    if empty_btc:
        df_btc = pd.DataFrame(columns=["FUNDO", "TICKER", "QTD_BTC"])

    df_prv["QTD"]   = pd.to_numeric(df_prv["QTD"],   errors="coerce").fillna(0)
    df_prv["PRECO"] = pd.to_numeric(df_prv["PRECO"], errors="coerce").fillna(0)
    df_btc["QTD_BTC"] = pd.to_numeric(df_btc["QTD_BTC"], errors="coerce").fillna(0)

    df = df_prv.merge(df_btc, on=["FUNDO", "TICKER"], how="outer")
    df[["QTD", "PRECO", "QTD_BTC"]] = df[["QTD", "PRECO", "QTD_BTC"]].fillna(0)
    df["VALOR_BRL"] = (df["QTD"] + df["QTD_BTC"]) * df["PRECO"]

    result: Dict[str, Dict[str, float]] = {}
    for _, row in df.iterrows():
        fundo  = str(row["FUNDO"])
        ticker = str(row["TICKER"]).upper().strip()
        val    = float(row["VALOR_BRL"])
        if fundo not in result:
            result[fundo] = {"pibb11": 0.0, "spxi11": 0.0}
        if ticker == "PIBB11":
            result[fundo]["pibb11"] = val
        elif ticker == "SPXI11":
            result[fundo]["spxi11"] = val
    return result


# ─────────────────────────────────────────────────────────────────────────────
# FUTUROS S&P vs USD — split por tipo de contrato
# S&P  : FUT ISP, FUT WSP
# USD  : FUT DOL, FUT WDO, FUT BRI
# ─────────────────────────────────────────────────────────────────────────────

def buscar_fut_sp_usd(dt: str, fundos: List[str]) -> Dict[str, Dict[str, float]]:
    if not fundos:
        return {}

    SP_ATIVOS  = ("'FUT ISP'", "'FUT WSP'")
    USD_ATIVOS = ("'FUT DOL'", "'FUT WDO'", "'FUT BRI'")
    todos      = SP_ATIVOS + USD_ATIVOS

    q = f"""
        SELECT clcli_cd           AS FUNDO,
               fuvct_fuatv_cd     AS ATIVO,
               SUM(qt * vl_varponto * vl_precomerc) AS NOTIONAL
        FROM   dbsx337.dbo.view_vcrapfut WITH (NOLOCK)
        WHERE  dt = '{dt}'
          AND  clcli_cd IN ({_ids(fundos)})
          AND  fuvct_fuatv_cd IN ({', '.join(todos)})
        GROUP BY clcli_cd, fuvct_fuatv_cd
    """
    db = sql.get_connection()
    df = db.run_query(q)
    if df is None or df.empty:
        return {}

    df["NOTIONAL"] = pd.to_numeric(df["NOTIONAL"], errors="coerce").fillna(0)
    sp_set  = {"FUT ISP", "FUT WSP"}
    result: Dict[str, Dict[str, float]] = {}
    for _, row in df.iterrows():
        fundo = str(row["FUNDO"])
        ativo = str(row["ATIVO"]).upper().strip()
        val   = float(row["NOTIONAL"])
        if fundo not in result:
            result[fundo] = {"sp": 0.0, "usd": 0.0}
        if ativo in sp_set:
            result[fundo]["sp"] += val
        else:
            result[fundo]["usd"] += val
    return result


# ─────────────────────────────────────────────────────────────────────────────
# PROVENTOS — view_vcraprdp  mttp do VBA
# ─────────────────────────────────────────────────────────────────────────────

def buscar_proventos(dt: str, fundos: List[str]) -> Dict[str, float]:
    if not fundos:
        return {}

    mttp = "('61','62','69','261','848','849','971','972','973')"
    q = f"""
        SELECT clcli_cd AS FUNDO, SUM(vl) AS PROVENTOS
        FROM   dbsx337.dbo.view_vcraprdp WITH (NOLOCK)
        WHERE  dt = '{dt}'
          AND  clcli_cd IN ({_ids(fundos)})
          AND  mttp_cd IN {mttp}
        GROUP BY clcli_cd
    """
    db = sql.get_connection()
    df = db.run_query(q)
    if df is None or len(df) == 0:
        return {}
    return dict(zip(df["FUNDO"].astype(str), _to_num(df["PROVENTOS"])))

# ─────────────────────────────────────────────────────────────────────────────
# MONTAGEM DA TABELA
#
# Replica o relatório VBA:
#   PRV_BRL  = SUM(VL_MERCADOLIQUIDO com câmbio)     ← coluna nova
#   %AÇÕES   = PRV_BRL / PL
#   %FUT     = SUM(Notional) / PL
#   %COTAS   = SUM(vl_liq) / PL
#   TOTAL    = %AÇÕES + %FUT + %COTAS
#   DESC     = 1 − TOTAL
#   Proventos % PL = SUM(proventos) / PL
# ─────────────────────────────────────────────────────────────────────────────

def montar_tabela(df_exp:        pd.DataFrame,
                  pl_map:        Dict[str, float],
                  prv_map:       Dict[str, float],
                  fut_map:       Dict[str, float],
                  cotas_map:     Dict[str, float],
                  proventos_map: Dict[str, float]) -> pd.DataFrame:

    df = df_exp.copy()
    f  = df["FUNDO"].astype(str)

    pl    = pd.to_numeric(f.map(pl_map),    errors="coerce").replace(0, np.nan)
    prv   = _to_num(f.map(prv_map))
    fut   = _to_num(f.map(fut_map))
    cotas = _to_num(f.map(cotas_map))
    prov  = _to_num(f.map(proventos_map))

    df["PL"]             = pl
    df["PRV"]            = prv
    df["%AÇÕES"]         = prv   / pl
    df["%FUT"]           = fut   / pl
    df["%COTAS"]         = cotas / pl

    for col in ["%AÇÕES", "%FUT", "%COTAS"]:
        df[col] = df[col].replace([np.inf, -np.inf], np.nan)

    # df["TOTAL"]          = df["%AÇÕES"].fillna(0) + df["%FUT"].fillna(0) + df["%COTAS"].fillna(0)
    df["TOTAL"] = df["%AÇÕES"] + df["%FUT"] + df["%COTAS"]
    df["TOTAL"] = df["TOTAL"].replace([np.inf, -np.inf], np.nan)
    df["DESC"]           = 1.0 - df["TOTAL"]
    df["Proventos % PL"] = prov  / pl

    # MAX/MIN ficam no df interno (usados para coloração) mas não exibidos
    return df[[
        "FUNDO", "PL", "BENCH",
        "TOTAL", "DESC",
        "%AÇÕES", "%FUT", "%COTAS",
        "Proventos % PL",
        "MAX", "MIN",
    ]].copy()

    df = df.round(6)

# ─────────────────────────────────────────────────────────────────────────────
# GERAÇÃO DE IMAGEM
# ─────────────────────────────────────────────────────────────────────────────

def gerar_imagem(df: pd.DataFrame, aba: str, dt: str, out_dir: str,
                 mostrar_logo: bool = False) -> None:
    os.makedirs(out_dir, exist_ok=True)
    if df is None or df.empty:
        print(f"  [{aba}] sem dados — pulando.")
        return

    dt_fmt  = pd.to_datetime(dt).strftime("%d/%m/%Y")
    df_disp = df.copy()

    # Colunas exibidas (PRV, MAX, MIN removidos)
    SP500_COLS = ["EXPOSIÇÃO S&P","EXPOSIÇÃO IBX","EXPOSIÇÃO USD","PIBB + SPXI","FANG","ISP"]
    is_sp500   = "EXPOSIÇÃO S&P" in df_disp.columns

    if is_sp500:
        colunas     = ["FUNDO","PL","BENCH","TOTAL","DESC",
                       "EXPOSIÇÃO S&P","EXPOSIÇÃO IBX","EXPOSIÇÃO USD",
                       "PIBB + SPXI","FANG","Proventos % PL","ISP"]
        col_widths  = [0.12, 0.11, 0.07, 0.07, 0.06,
                       0.08, 0.08, 0.08, 0.08, 0.07, 0.08, 0.06]
    else:
        colunas    = ["FUNDO","PL","BENCH","TOTAL","DESC",
                      "%AÇÕES","%FUT","%COTAS","Proventos % PL"]
        col_widths = [0.16, 0.14, 0.09, 0.09, 0.08, 0.10, 0.08, 0.10, 0.12]

    # formatação para exibição
    df_disp["PL"]    = df_disp["PL"].apply(_fmt_money)
    df_disp["BENCH"] = df_disp["BENCH"].apply(_fmt_text)
    pct_fmt_cols = ["TOTAL","DESC","%AÇÕES","%FUT","%COTAS","Proventos % PL","MAX","MIN"] + SP500_COLS
    for c in pct_fmt_cols:
        if c in df_disp.columns:
            fmt = _fmt_pct3 if (c == "DESC" and is_sp500) else _fmt_pct
            df_disp[c] = df_disp[c].apply(fmt)

    n_rows = len(df_disp)
    n_cols = len(colunas)

    fig_w = max(24, n_cols * 2.4)
    fig_h = 3.0 + n_rows * 0.65 + 0.4
    fig   = plt.figure(figsize=(fig_w, fig_h), facecolor=ITAU_WHITE)

    gs = gridspec.GridSpec(4, 1, figure=fig,
                           height_ratios=[1.10, 1.60, n_rows * 0.65 + 0.4, 0.40],
                           hspace=0, left=0.0, right=1.0)

    # ── faixa topo ───────────────────────────────────────────────────────────
    ax_b = fig.add_subplot(gs[0])
    ax_b.set_facecolor(ITAU_DARK); ax_b.axis("off")
    ax_b.set_xlim(0, 1); ax_b.set_ylim(0, 1)
    if mostrar_logo:
        ax_b.text(0.77, 1.0, "Itaú Asset",
                  transform=ax_b.transAxes, fontsize=34, fontweight="bold",
                  color=ITAU_GRAY2, va="center", ha="left")
    if mostrar_logo and os.path.exists(LOGO_PATH):
        try:
            ax_logo = inset_axes(ax_b, width="12%", height="210%",
                                 loc="center right",
                                 bbox_to_anchor=(0.0, 0.8, 1.0, 0.82),
                                 bbox_transform=ax_b.transAxes, borderpad=0)
            ax_logo.imshow(mpimg.imread(LOGO_PATH))
            ax_logo.axis("off")
        except Exception as e:
            print(f"  Logo: {e}")
    ax_b.axhline(y=0.06, color=ITAU_ORANGE, linewidth=2.5)



    # # ── faixa topo ───────────────────────────────────────────────────────────
    # ax_b = fig.add_subplot(gs[0])
    # ax_b.set_facecolor(ITAU_DARK); ax_b.axis("off")
    # ax_b.set_xlim(0, 1); ax_b.set_ylim(0, 1)
    # ax_b.text(1.015, 0.50, "Itaú Asset Management",
    #           transform=ax_b.transAxes, fontsize=14, fontweight="bold",
    #           color=ITAU_GRAY2, va="center", ha="left")
    # if os.path.exists(LOGO_PATH):
    #     try:
    #         ax_logo = inset_axes(ax_b, width="12%", height="250%",
    #                              loc="center right",
    #                              bbox_to_anchor=(0.0, 1.0, 1.0, 0.82),
    #                              bbox_transform=ax_b.transAxes, borderpad=0)
    #         ax_logo.imshow(mpimg.imread(LOGO_PATH))
    #         ax_logo.axis("off")
    #     except Exception as e:
    #         print(f"  Logo: {e}")
    # ax_b.axhline(y=0.06, color=ITAU_ORANGE, linewidth=2.5)


    # ── título ───────────────────────────────────────────────────────────────
    # ax_h = fig.add_subplot(gs[1])
    # ax_h.set_facecolor(ITAU_WHITE); ax_h.axis("off")
    # ax_h.set_xlim(0, 1); ax_h.set_ylim(0, 1)
    # ax_h.text(0.018, 0.82, "RELATÓRIO DE EXPOSIÇÃO",
    #           transform=ax_h.transAxes, fontsize=20, fontweight="bold",
    #           color=ITAU_DARK, va="center", ha="left")
    # ax_h.text(0.018, 0.50, f"{aba}",
    #           transform=ax_h.transAxes, fontsize=14, color=ITAU_ORANGE,
    #           va="center", ha="left")
    # ax_h.text(0.988, 0.82, f"Data Referência:  {dt_fmt}",
    #           transform=ax_h.transAxes, fontsize=12, color=ITAU_DARK,
    #           va="center", ha="right")
    # ax_h.axhline(y=0.14, color=ITAU_GRAY, linewidth=1.2)

    ax_h = fig.add_subplot(gs[1])
    ax_h.set_facecolor(ITAU_WHITE); ax_h.axis("off")
    ax_h.set_xlim(0, 1); ax_h.set_ylim(0, 1)
    ax_h.text(0.018, 0.82, "RELATÓRIO DE EXPOSIÇÃO",
              transform=ax_h.transAxes, fontsize=32, fontweight="bold",
              color=ITAU_DARK, va="center", ha="left")
    ax_h.text(0.018, 0.30, f"{aba}",
              transform=ax_h.transAxes, fontsize=20, color=ITAU_ORANGE,
              va="center", ha="left")
    ax_h.text(0.988, 0.82, f"Data Referência:  {dt_fmt}",
              transform=ax_h.transAxes, fontsize=18, color=ITAU_DARK,
              va="center", ha="right")
    ax_h.axhline(y=0.14, color=ITAU_GRAY, linewidth=1.2)

    # ── tabela ───────────────────────────────────────────────────────────────
    ax_t = fig.add_subplot(gs[2])
    ax_t.set_facecolor(ITAU_WHITE); ax_t.axis("off")

    tbl = ax_t.table(cellText=df_disp[colunas].values,
                     colLabels=colunas, cellLoc="center",
                     loc="center", colWidths=col_widths)
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(12)
    tbl.scale(1, 2.2)

    idx_total = colunas.index("TOTAL")
    FONT_SIZE = 14 ####################################### 12

    # cabeçalho
    for ci in range(n_cols):
        cell = tbl[0, ci]
        cell.set_facecolor(ITAU_DARK)
        cell.set_text_props(color=ITAU_WHITE, fontweight="bold", fontsize=FONT_SIZE)
        cell.set_edgecolor(ITAU_WHITE)
        cell.set_linewidth(0.8)

    # linhas de dados
    for ri in range(1, n_rows + 1):
        row_data = df_disp.iloc[ri - 1]
        row_num  = df.iloc[ri - 1]
        bg_base  = ROW_PAR if ri % 2 == 0 else ITAU_WHITE

        # verifica se TOTAL está fora da banda MAX/MIN (usa floats originais, igual ao Excel)
        fora_banda = False
        try:
            v_tot = float(row_num["TOTAL"])
            v_max = row_num["MAX"]
            v_min = row_num["MIN"]
            if (not pd.isna(v_max) and not pd.isna(v_min)
                    and float(v_max) != 0 and float(v_min) != 0):
                fora_banda = (v_tot > float(v_max) or v_tot < float(v_min))
        except Exception:
            pass

        # background: vermelho claro se fora da banda, normal caso contrário
        bg = "#fde8e8" if fora_banda else bg_base

        for ci in range(n_cols):
            cell = tbl[ri, ci]
            cell.set_facecolor(bg)
            cell.set_edgecolor(ITAU_GRAY)
            cell.set_linewidth(0.5)

        # cor do texto na coluna TOTAL
        try:
            v_tot_pct = float(row_num["TOTAL"]) * 100
            if fora_banda:
                tbl[ri, idx_total].set_text_props(color=ITAU_RED, fontweight="bold",
                                                   fontsize=FONT_SIZE)
            elif v_tot_pct >= 99.0:
                tbl[ri, idx_total].set_text_props(color=ITAU_GREEN, fontweight="bold",
                                                   fontsize=FONT_SIZE)
            else:
                tbl[ri, idx_total].set_text_props(color=ITAU_ORANGE, fontweight="bold",
                                                   fontsize=FONT_SIZE)
        except Exception:
            pass

    # ── rodapé ───────────────────────────────────────────────────────────────
    ax_f = fig.add_subplot(gs[3])
    ax_f.set_facecolor(ITAU_WHITE); ax_f.axis("off")
    ax_f.set_xlim(0, 1); ax_f.set_ylim(0, 1)
    ax_f.axhline(y=0.95, color=ITAU_DARK, linewidth=1.5)
    ax_f.text(
        0.5, 0.38,
        "TOTAL = %AÇÕES + %FUT + %COTAS  |  DESC = 1−TOTAL  |  "
        "Linha vermelha = TOTAL fora da banda MAX/MIN",
        transform=ax_f.transAxes, fontsize=10, color=ITAU_GRAY2,
        ha="center", va="center", style="italic"
    )

    nome = os.path.join(out_dir, f"exposicao_{aba}_{dt}.png")
    plt.savefig(nome, dpi=150, bbox_inches="tight",
                facecolor=ITAU_WHITE, edgecolor="none")
    plt.close()
    print(f"  [OK] {nome}")

# ─────────────────────────────────────────────────────────────────────────────
# EXPORTAÇÃO EXCEL
# ─────────────────────────────────────────────────────────────────────────────

def exportar_excel(abas_data: Dict[str, pd.DataFrame], dt: str, out_dir: str) -> None:
    from openpyxl.styles import PatternFill, Font, Alignment
    from openpyxl.utils import get_column_letter

    os.makedirs(out_dir, exist_ok=True)
    nome = os.path.join(out_dir, f"exposicao_{dt}.xlsx")

    def to_argb(h: str) -> str:
        return "FF" + h.lstrip("#").upper()

    pct_cols   = {"TOTAL", "DESC", "%AÇÕES", "%FUT", "%COTAS", "Proventos % PL", "MAX", "MIN",
                  "EXPOSIÇÃO S&P", "EXPOSIÇÃO IBX", "EXPOSIÇÃO USD", "PIBB + SPXI", "FANG", "ISP"}
    money_cols = {"PL"}

    with pd.ExcelWriter(nome, engine="openpyxl") as writer:
        for aba, df in abas_data.items():
            if df is None or df.empty:
                continue

            df.to_excel(writer, sheet_name=aba[:31], index=False)
            ws = writer.sheets[aba[:31]]

            col_names = list(df.columns)
            col_idx   = {name: i + 1 for i, name in enumerate(col_names)}

            # cabeçalho
            hdr_fill = PatternFill("solid", fgColor=to_argb(ITAU_DARK))
            hdr_font = Font(bold=True, color=to_argb(ITAU_WHITE), size=11)
            for cell in ws[1]:
                cell.fill      = hdr_fill
                cell.font      = hdr_font
                cell.alignment = Alignment(horizontal="center", vertical="center")

            # linhas de dados: background + formato numérico
            for ri in range(2, ws.max_row + 1):
                row_idx  = ri - 2
                bg_color = ROW_PAR if (ri % 2 == 0) else ITAU_WHITE

                # fundo vermelho se TOTAL fora da banda
                if {"TOTAL", "MAX", "MIN"} <= col_idx.keys():
                    try:
                        v_tot = float(df.iloc[row_idx]["TOTAL"])
                        v_max = df.iloc[row_idx]["MAX"]
                        v_min = df.iloc[row_idx]["MIN"]
                        if (not pd.isna(v_max) and not pd.isna(v_min)
                                and float(v_max) != 0 and float(v_min) != 0
                                and (v_tot > float(v_max) or v_tot < float(v_min))):
                            bg_color = "#fde8e8"
                    except Exception:
                        pass

                row_fill = PatternFill("solid", fgColor=to_argb(bg_color))
                for ci, col_name in enumerate(col_names, start=1):
                    cell = ws.cell(row=ri, column=ci)
                    cell.fill = row_fill
                    if col_name in pct_cols:
                        is_sp500_aba = "EXPOSIÇÃO S&P" in col_names
                        cell.number_format = "0.000%" if (col_name == "DESC" and is_sp500_aba) else "0.00%"
                        cell.alignment     = Alignment(horizontal="center")
                    elif col_name in money_cols:
                        cell.number_format = '"R$ "#,##0.00'
                        cell.alignment     = Alignment(horizontal="right")
                    else:
                        cell.alignment = Alignment(horizontal="left")

            # cor da fonte na coluna TOTAL (igual às imagens)
            if {"TOTAL", "MAX", "MIN"} <= col_idx.keys():
                ci_total = col_idx["TOTAL"]
                for ri in range(2, ws.max_row + 1):
                    try:
                        row_idx = ri - 2
                        v_tot   = float(df.iloc[row_idx]["TOTAL"])
                        v_max   = df.iloc[row_idx]["MAX"]
                        v_min   = df.iloc[row_idx]["MIN"]
                        fora    = (not pd.isna(v_max) and not pd.isna(v_min)
                                   and float(v_max) != 0
                                   and (v_tot > float(v_max) or v_tot < float(v_min)))
                        color   = ITAU_RED if fora else (ITAU_GREEN if v_tot >= 0.99 else ITAU_ORANGE)
                        ws.cell(ri, ci_total).font = Font(bold=True, color=to_argb(color))
                    except Exception:
                        pass

            # largura das colunas
            for ci, col_name in enumerate(col_names, start=1):
                try:
                    data_len = int(df[col_name].astype(str).str.len().max())
                except Exception:
                    data_len = 0
                ws.column_dimensions[get_column_letter(ci)].width = min(
                    max(len(col_name), data_len) + 2, 32
                )

            ws.freeze_panes = "A2"

    print(f"  [OK] Excel: {nome}")


# ─────────────────────────────────────────────────────────────────────────────
# GERAÇÃO DE HTML
# ─────────────────────────────────────────────────────────────────────────────

def gerar_html(abas_data: Dict[str, pd.DataFrame], dt: str, out_dir: str,
               rolagem_data: Optional[List[tuple]] = None) -> None:
    import base64
    os.makedirs(out_dir, exist_ok=True)
    dt_fmt = pd.to_datetime(dt).strftime("%d/%m/%Y")

    logo_tag = ""
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as _f:
            _b64 = base64.b64encode(_f.read()).decode()
        _ext = os.path.splitext(LOGO_PATH)[1].lstrip(".").lower()
        _mime = "image/png" if _ext == "png" else f"image/{_ext}"
        logo_tag = f'<img src="data:{_mime};base64,{_b64}" class="logo-img" alt="Itaú">'

    SP500_COLS = ["FUNDO","PL","BENCH","TOTAL","DESC",
                  "EXPOSIÇÃO S&P","EXPOSIÇÃO IBX","EXPOSIÇÃO USD",
                  "PIBB + SPXI","FANG","Proventos % PL","ISP"]
    STD_COLS   = ["FUNDO","PL","BENCH","TOTAL","DESC",
                  "%AÇÕES","%FUT","%COTAS","Proventos % PL"]
    PCT_COLS   = {"TOTAL","DESC","%AÇÕES","%FUT","%COTAS","Proventos % PL",
                  "EXPOSIÇÃO S&P","EXPOSIÇÃO IBX","EXPOSIÇÃO USD",
                  "PIBB + SPXI","FANG","ISP"}

    def fmt_cell(col: str, val) -> str:
        if col == "PL":      return _fmt_money(val)
        if col in PCT_COLS:  return _fmt_pct(val)
        return _fmt_text(val)

    def build_table(df: pd.DataFrame) -> str:
        is_sp500 = "EXPOSIÇÃO S&P" in df.columns
        cols = [c for c in (SP500_COLS if is_sp500 else STD_COLS) if c in df.columns]

        th_cells = "".join(
            f'<th onclick="sortTable(this)" title="Clique para ordenar">{c}</th>'
            for c in cols
        )

        rows_html = []
        for _, row in df.iterrows():
            fora = False
            try:
                v_tot = float(row["TOTAL"])
                v_max = row.get("MAX", float("nan"))
                v_min = row.get("MIN", float("nan"))
                if (not pd.isna(v_max) and not pd.isna(v_min)
                        and float(v_max) != 0 and float(v_min) != 0):
                    fora = v_tot > float(v_max) or v_tot < float(v_min)
            except Exception:
                pass

            cells = []
            for c in cols:
                if c == "DESC" and is_sp500:
                    text = _fmt_pct3(row.get(c, ""))
                else:
                    text = fmt_cell(c, row.get(c, ""))
                if c == "TOTAL":
                    try:
                        v = float(row["TOTAL"])
                        cls = "tot-red" if fora else ("tot-green" if v >= 0.99 else "tot-orange")
                    except Exception:
                        cls = ""
                    cells.append(f'<td class="bold {cls}">{text}</td>')
                else:
                    cells.append(f'<td>{text}</td>')

            tr_cls = ' class="fora-banda"' if fora else ""
            rows_html.append(f"<tr{tr_cls}>{''.join(cells)}</tr>")

        return (
            '<div class="search-wrap">'
            '<input class="search-box" placeholder="&#128269; Buscar fundo..." oninput="filterTable(this)">'
            '</div>'
            '<div class="tbl-wrap">'
            '<table class="exp-table">'
            f'<thead><tr>{th_cells}</tr></thead>'
            f'<tbody>{"".join(rows_html)}</tbody>'
            '</table></div>'
        )

    # ── ALERTA: coleta todos os fundos fora-banda em todas as abas ──────────────
    alerta_rows = []
    for aba, df in abas_data.items():
        if df is None or df.empty:
            continue
        for _, row in df.iterrows():
            try:
                v_tot = float(row["TOTAL"])
                v_max = row.get("MAX", float("nan"))
                v_min = row.get("MIN", float("nan"))
                if (not pd.isna(v_max) and not pd.isna(v_min)
                        and float(v_max) != 0 and float(v_min) != 0
                        and (v_tot > float(v_max) or v_tot < float(v_min))):
                    alerta_rows.append({
                        "ABA":   aba,
                        "FUNDO": str(row.get("FUNDO", "")),
                        "PL":    row.get("PL",    float("nan")),
                        "BENCH": str(row.get("BENCH", "")),
                        "TOTAL": v_tot,
                        "MAX":   float(v_max),
                        "MIN":   float(v_min),
                        "DESC":  row.get("DESC",  float("nan")),
                    })
            except Exception:
                pass

    def build_alerta_table(rows):
        if not rows:
            return '<p style="padding:20px;color:#888;">Nenhum fundo fora da banda.</p>'

        # agrupa preservando a ordem de aparição das abas
        groups: Dict[str, list] = {}
        for r in rows:
            groups.setdefault(r["ABA"], []).append(r)

        cols = ["FUNDO", "PL", "BENCH", "TOTAL", "DESC"]
        th_cells = "".join(
            f'<th onclick="sortTable(this)" title="Clique para ordenar">{c}</th>'
            for c in cols
        )

        sections = []
        for aba, grp in groups.items():
            pid      = "pane-" + aba.replace("&", "e").replace(" ", "_")
            n        = len(grp)
            plural   = "s" if n != 1 else ""
            rows_html = []
            for r in grp:
                fund_esc = r["FUNDO"].replace("'", "\\'")
                cells = []
                for c in cols:
                    val = r.get(c, "")
                    if c == "PL":
                        text = _fmt_money(val)
                    elif c in ("TOTAL", "DESC"):
                        text = _fmt_pct(val)
                    else:
                        text = _fmt_text(val) if not isinstance(val, float) else _fmt_pct(val)
                    if c == "TOTAL":
                        cells.append(f'<td class="bold tot-red">{text}</td>')
                    elif c == "FUNDO":
                        cells.append(
                            f'<td><a class="fund-link" href="javascript:void(0)" '
                            f'onclick="goToFund(\'{pid}\',\'{fund_esc}\')">{text}</a></td>'
                        )
                    else:
                        cells.append(f'<td>{text}</td>')
                rows_html.append(f'<tr class="fora-banda">{"".join(cells)}</tr>')

            sections.append(
                f'<div class="alerta-section">'
                f'<div class="alerta-sec-header">'
                f'<span class="alerta-sec-name">{aba}</span>'
                f'<span class="alerta-count">{n} fundo{plural}</span>'
                f'<button class="alerta-goto" onclick="goToPane(\'{pid}\')">'
                f'Ir para aba &#8594;</button>'
                f'</div>'
                f'<div class="tbl-wrap">'
                f'<table class="exp-table">'
                f'<thead><tr>{th_cells}</tr></thead>'
                f'<tbody>{"".join(rows_html)}</tbody>'
                f'</table></div></div>'
            )

        return (
            '<div class="search-wrap">'
            '<input class="search-box" placeholder="&#128269; Buscar fundo..." '
            'oninput="filterAlerta(this)">'
            '</div>'
            + "".join(sections)
        )

    n_alerta = len(alerta_rows)
    badge = (f' <span class="alerta-badge">{n_alerta}</span>') if n_alerta else ""
    alerta_pane = (
        f'<div id="pane-ALERTA" class="pane active">'
        f'<h2 class="aba-title">ALERTA — Fundos fora da banda</h2>'
        f'{build_alerta_table(alerta_rows)}</div>'
    )
    alerta_btn = (
        f'<button class="nav-btn nav-btn-alerta active" data-pane="pane-ALERTA">'
        f'ALERTA{badge}</button>'
    )

    panes   = [alerta_pane]
    buttons = [alerta_btn]
    for aba, df in abas_data.items():
        if df is None or df.empty:
            continue
        sid = aba.replace("&", "e").replace(" ", "_")
        panes.append(
            f'<div id="pane-{sid}" class="pane">'
            f'<h2 class="aba-title">{aba}</h2>'
            f'{build_table(df)}</div>'
        )
        buttons.append(
            f'<button class="nav-btn" data-pane="pane-{sid}">{aba}</button>'
        )

    def _build_rol_table(label, df, v1, v2):
        cols = df.columns.tolist()
        th   = "".join(
            f'<th onclick="sortTable(this)" title="Clique para ordenar">{c}</th>'
            for c in cols
        )
        rows = []
        for _, row in df.iterrows():
            cells = []
            for c in cols:
                val = row[c]
                if c == "PL":
                    cells.append(f'<td>{_fmt_money(val)}</td>')
                elif "%" in c:
                    text = _fmt_pct(val)
                    try:
                        v = float(val)
                        cls = "tot-green" if v > 0 else ("tot-red" if v < 0 else "")
                    except Exception:
                        cls = ""
                    cells.append(f'<td class="bold {cls}">{text}</td>')
                else:
                    cells.append(f'<td>{_fmt_text(val)}</td>')
            rows.append(f"<tr>{''.join(cells)}</tr>")
        return (
            f'<div class="rol-group">'
            f'<div class="rol-subtitle">{label}'
            f'<span class="rol-vct">{v1} &#8594; {v2}</span></div>'
            f'<div class="search-wrap">'
            f'<input class="search-box" placeholder="&#128269; Buscar fundo..." oninput="filterTable(this)">'
            f'</div>'
            f'<div class="tbl-wrap"><table class="exp-table">'
            f'<thead><tr>{th}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody>'
            f'</table></div></div>'
        )

    rol_html = "".join(
        _build_rol_table(label, df, v1, v2)
        for label, df, v1, v2 in (rolagem_data or [])
    )
    has_rolagem = bool(rol_html)

    css = f"""
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f0f3fa; color: #1a1a2e; }}

    .hdr {{ background: {ITAU_DARK}; padding: 24px 40px 0; }}
    .hdr::after {{ content: ''; display: block; height: 4px; background: {ITAU_ORANGE}; margin-top: 20px; }}
    .hdr-inner {{ display: flex; align-items: center; justify-content: space-between; }}
    .hdr h1 {{ color: #fff; font-size: 1.7rem; font-weight: 700; letter-spacing: .06em; }}
    .hdr .sub {{ color: {ITAU_GRAY2}; font-size: .88rem; margin-top: 5px; }}
    .hdr .sub strong {{ color: #fff; }}
    .brand {{ display: flex; align-items: center; gap: 12px; }}
    .brand span {{ color: {ITAU_GRAY2}; font-size: 2.1rem; font-weight: 700; letter-spacing: .04em; }}
    .logo-img {{ height: 52px; width: auto; object-fit: contain; }}

    .nav-wrapper {{ position: sticky; top: 0; z-index: 100;
                    box-shadow: 0 3px 10px rgba(0,0,0,.09); }}
    .nav-main {{ background: {ITAU_DARK}; padding: 0 40px;
                 display: flex; align-items: center; gap: 0; }}
    .main-btn {{ padding: 13px 28px; background: none; border: none;
                 border-bottom: 3px solid transparent;
                 color: {ITAU_GRAY2}; font-weight: 700; font-size: .88rem;
                 letter-spacing: .06em; cursor: pointer; transition: all .18s;
                 white-space: nowrap; }}
    .main-btn:hover {{ color: #fff; }}
    .main-btn.active {{ color: #fff; border-bottom-color: {ITAU_ORANGE}; }}
    .btn-voltar {{ padding: 10px 18px; background: none; border: none;
                   border-right: 1px solid rgba(255,255,255,.15);
                   color: {ITAU_GRAY2}; font-weight: 600; font-size: .82rem;
                   cursor: pointer; text-decoration: none; white-space: nowrap;
                   transition: color .17s; margin-right: 8px; }}
    .btn-voltar:hover {{ color: #fff; }}
    .nav-sub {{ background: #fff; padding: 10px 40px; display: flex; flex-wrap: wrap; gap: 8px;
                align-items: center; border-bottom: 2px solid {ITAU_GRAY}; }}
    .nav-btn {{ padding: 7px 18px; border: 2px solid {ITAU_ORANGE}; border-radius: 20px;
                background: #fff; color: {ITAU_ORANGE}; font-weight: 600; font-size: .82rem;
                cursor: pointer; transition: all .17s; white-space: nowrap; }}
    .nav-btn:hover {{ background: {ITAU_ORANGE}18; }}
    .nav-btn.active {{ background: {ITAU_ORANGE}; color: #fff; box-shadow: 0 2px 8px {ITAU_ORANGE}55; }}
    .nav-btn-alerta {{ border-color: {ITAU_RED}; color: {ITAU_RED}; font-weight: 700;
                       letter-spacing: .04em; }}
    .nav-btn-alerta:hover {{ background: {ITAU_RED}18; border-color: {ITAU_RED}; color: {ITAU_RED}; }}
    .nav-btn-alerta.active {{ background: {ITAU_RED}; border-color: {ITAU_RED}; color: #fff;
                               box-shadow: 0 2px 8px {ITAU_RED}55; }}
    .sec {{ display: none; }}
    .sec.active {{ display: block; }}

    .content {{ padding: 28px 40px 50px; }}
    .pane {{ display: none; animation: fadeIn .2s; }}
    .pane.active {{ display: block; }}
    @keyframes fadeIn {{ from {{ opacity:0; transform:translateY(4px); }} to {{ opacity:1; transform:none; }} }}

    .aba-title {{ font-size: 1rem; font-weight: 700; color: {ITAU_ORANGE}; margin-bottom: 14px;
                  text-transform: uppercase; letter-spacing: .08em; }}

    .search-wrap {{ margin-bottom: 12px; }}
    .search-box {{ padding: 8px 16px; border: 1.5px solid {ITAU_GRAY}; border-radius: 8px;
                   font-size: .85rem; width: 300px; outline: none; transition: border .2s; }}
    .search-box:focus {{ border-color: {ITAU_ORANGE}; box-shadow: 0 0 0 3px {ITAU_ORANGE}22; }}

    .tbl-wrap {{ overflow-x: auto; border-radius: 10px;
                 box-shadow: 0 2px 16px rgba(0,0,0,.10); }}
    .exp-table {{ border-collapse: collapse; width: 100%; font-size: .83rem;
                  background: #fff; min-width: 700px; }}
    .exp-table thead tr {{ background: {ITAU_DARK}; }}
    .exp-table th {{ color: #fff; font-weight: 600; padding: 11px 14px; white-space: nowrap;
                     text-align: center; cursor: pointer; user-select: none;
                     border-right: 1px solid #ffffff1a; position: sticky; top: 0; }}
    .exp-table th:hover {{ background: #112070; }}
    .exp-table th.asc::after  {{ content: ' ▲'; font-size: .6em; opacity: .8; }}
    .exp-table th.desc::after {{ content: ' ▼'; font-size: .6em; opacity: .8; }}
    .exp-table td {{ padding: 9px 14px; text-align: center; border-bottom: 1px solid {ITAU_GRAY};
                     border-right: 1px solid {ITAU_GRAY}; white-space: nowrap; }}
    .exp-table td:first-child {{ text-align: left; font-weight: 600; }}
    .exp-table td:last-child, .exp-table th:last-child {{ border-right: none; }}
    .exp-table tbody tr:nth-child(even) {{ background: {ROW_PAR}; }}
    .exp-table tbody tr:hover {{ background: #d6e4ff !important; transition: background .12s; }}
    .fora-banda {{ background: #fde8e8 !important; }}
    .fora-banda:hover {{ background: #f9c6c6 !important; }}
    .fund-link {{ color: {ITAU_DARK}; text-decoration: underline dotted; cursor: pointer; font-weight: 600; }}
    .fund-link:hover {{ color: {ITAU_ORANGE}; text-decoration: underline; }}
    .alerta-section {{ margin-bottom: 32px; }}
    .alerta-sec-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }}
    .alerta-sec-name {{ font-size: 1rem; font-weight: 700; color: {ITAU_DARK};
                        text-transform: uppercase; letter-spacing: .06em; }}
    .alerta-count {{ background: {ITAU_RED}22; color: {ITAU_RED}; border-radius: 12px;
                     font-size: .78rem; font-weight: 700; padding: 2px 10px; }}
    .alerta-goto {{ margin-left: auto; padding: 4px 14px; border: 1.5px solid {ITAU_ORANGE};
                    border-radius: 14px; background: #fff; color: {ITAU_ORANGE};
                    font-size: .78rem; font-weight: 600; cursor: pointer; transition: all .15s; }}
    .alerta-goto:hover {{ background: {ITAU_ORANGE}; color: #fff; }}
    .alerta-badge {{ display: inline-block; background: {ITAU_RED}; color: #fff;
                     border-radius: 50%; font-size: .7rem; font-weight: 700;
                     min-width: 18px; height: 18px; line-height: 18px;
                     text-align: center; padding: 0 4px; margin-left: 5px;
                     vertical-align: middle; }}
    .bold {{ font-weight: 700; }}
    .tot-green  {{ color: {ITAU_GREEN}; }}
    .tot-orange {{ color: {ITAU_ORANGE}; }}
    .tot-red    {{ color: {ITAU_RED}; }}

    .footer {{ background: #fff; border-top: 3px solid {ITAU_DARK}; padding: 16px 40px;
               font-size: .78rem; color: {ITAU_GRAY2}; font-style: italic; text-align: center; }}
    .leg-dot {{ display: inline-block; width: 12px; height: 12px; border-radius: 50%;
                background: #fde8e8; border: 2px solid {ITAU_RED}; vertical-align: middle; margin-right: 4px; }}
    .rol-group {{ margin-bottom: 32px; }}
    .rol-subtitle {{ font-size: .95rem; font-weight: 700; color: {ITAU_DARK};
                     margin-bottom: 10px; display: flex; align-items: center; gap: 10px; }}
    .rol-vct {{ color: {ITAU_ORANGE}; font-size: .82rem; font-weight: 600;
                background: {ITAU_ORANGE}18; padding: 2px 10px; border-radius: 10px; }}
    """

    js = r"""
    const TITLES = { exposicao: 'RELATÓRIO DE EXPOSIÇÃO', rolagem: 'RELATÓRIO DE ROLAGEM' };

    function switchMain(name) {
      document.querySelectorAll('.main-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.main-btn').forEach(b => {
        if (b.getAttribute('onclick') === "switchMain('" + name + "')")
          b.classList.add('active');
      });
      document.querySelectorAll('.sec').forEach(s => s.classList.remove('active'));
      const sec = document.getElementById('sec-' + name);
      if (sec) sec.classList.add('active');
      const sub = document.getElementById('nav-sub');
      if (sub) sub.style.display = name === 'exposicao' ? '' : 'none';
      const title = document.getElementById('page-title');
      if (title && TITLES[name]) title.textContent = TITLES[name];
    }

    document.querySelectorAll('.nav-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.pane').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(btn.dataset.pane).classList.add('active');
      });
    });

    function parseNum(text) {
      const s = text.replace(/R\$\s*/g, '').replace(/%/g, '').replace(/,/g, '').trim();
      const n = parseFloat(s);
      return isNaN(n) ? null : n;
    }

    function sortTable(th) {
      const table  = th.closest('table');
      const tbody  = table.querySelector('tbody');
      const idx    = Array.from(th.parentNode.children).indexOf(th);
      const goAsc  = !th.classList.contains('asc');
      th.parentNode.querySelectorAll('th').forEach(t => t.classList.remove('asc','desc'));
      th.classList.add(goAsc ? 'asc' : 'desc');
      const rows = Array.from(tbody.querySelectorAll('tr'));
      rows.sort((a, b) => {
        const av = (a.children[idx]?.textContent || '').trim();
        const bv = (b.children[idx]?.textContent || '').trim();
        const an = parseNum(av), bn = parseNum(bv);
        const cmp = (an !== null && bn !== null)
          ? an - bn
          : av.localeCompare(bv, 'pt');
        return goAsc ? cmp : -cmp;
      });
      rows.forEach(r => tbody.appendChild(r));
    }

    function filterTable(input) {
      const q         = input.value.toLowerCase();
      const container = input.closest('.pane') || input.closest('.rol-group');
      container.querySelectorAll('tbody tr').forEach(row => {
        const text = Array.from(row.cells).map(c => c.textContent).join(' ').toLowerCase();
        row.style.display = text.includes(q) ? '' : 'none';
      });
    }

    function filterAlerta(input) {
      const q    = input.value.toLowerCase();
      const pane = input.closest('.pane');
      pane.querySelectorAll('.alerta-section').forEach(sec => {
        let visible = 0;
        sec.querySelectorAll('tbody tr').forEach(row => {
          const text = Array.from(row.cells).map(c => c.textContent).join(' ').toLowerCase();
          const show = text.includes(q);
          row.style.display = show ? '' : 'none';
          if (show) visible++;
        });
        sec.style.display = (visible === 0 && q) ? 'none' : '';
      });
    }

    function goToPane(paneId) {
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.pane').forEach(p => p.classList.remove('active'));
      const btn = document.querySelector('.nav-btn[data-pane="' + paneId + '"]');
      if (btn) btn.classList.add('active');
      const pane = document.getElementById(paneId);
      if (pane) pane.classList.add('active');
    }

    function goToFund(paneId, fundName) {
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.pane').forEach(p => p.classList.remove('active'));
      const btn = document.querySelector('.nav-btn[data-pane="' + paneId + '"]');
      if (btn) btn.classList.add('active');
      const pane = document.getElementById(paneId);
      if (!pane) return;
      pane.classList.add('active');
      for (const row of pane.querySelectorAll('tbody tr')) {
        if ((row.cells[0]?.textContent || '').trim() === fundName) {
          row.scrollIntoView({ behavior: 'smooth', block: 'center' });
          row.style.transition = 'background 0.15s';
          const prev = row.classList.contains('fora-banda') ? '#fde8e8' : '';
          row.style.background = '#ffe066';
          setTimeout(() => { row.style.background = prev; }, 1400);
          break;
        }
      }
    }
    """

    _btn_rolagem = ('<button class="main-btn" onclick="switchMain(\'rolagem\')">'
                    'ROLAGEM</button>') if has_rolagem else ''
    _sec_rolagem = (f'<div id="sec-rolagem" class="sec"><div class="content">'
                    f'{rol_html}</div></div>') if has_rolagem else ''

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Relatório de Exposição — {dt_fmt}</title>
  <style>{css}</style>
</head>
<body>

<div class="hdr">
  <div class="hdr-inner">
    <div>
      <h1 id="page-title">RELATÓRIO DE EXPOSIÇÃO</h1>
      <p class="sub">Data Referência: &nbsp;<strong>{dt_fmt}</strong></p>
    </div>
    <div class="brand"><span>Itaú Asset Management</span>{logo_tag}</div>
  </div>
</div>

<div class="nav-wrapper">
  <nav class="nav-main">
    <a href="../index.html" class="btn-voltar">&#8592; Voltar</a>
    <button class="main-btn active" onclick="switchMain('exposicao')">EXPOSIÇÃO</button>
    {_btn_rolagem}
  </nav>
  <nav class="nav-sub" id="nav-sub">
    {''.join(buttons)}
  </nav>
</div>

<div id="sec-exposicao" class="sec active">
  <div class="content">{''.join(panes)}</div>
</div>

{_sec_rolagem}

<div class="footer">
  TOTAL = %AÇÕES + %FUT + %COTAS &nbsp;|&nbsp; DESC = 1 − TOTAL &nbsp;|&nbsp;
  <span class="leg-dot"></span> Linha = TOTAL fora da banda MAX/MIN
</div>

<script>{js}</script>
</body>
</html>"""

    nome = os.path.join(out_dir, f"exposicao_{dt}.html")
    with open(nome, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  [OK] HTML: {nome}")


# ─────────────────────────────────────────────────────────────────────────────
# ÍNDICE DE HISTÓRICO
# ─────────────────────────────────────────────────────────────────────────────

def gerar_index(root_dir: str) -> None:
    import glob, re, base64, json
    os.makedirs(root_dir, exist_ok=True)

    arquivos = sorted(
        glob.glob(os.path.join(root_dir, "????????", "exposicao_????-??-??.html")),
        reverse=True
    )

    def _parse_dt(path: str):
        m = re.search(r"exposicao_(\d{4}-\d{2}-\d{2})\.html$", os.path.basename(path))
        if m:
            try:
                return pd.to_datetime(m.group(1))
            except Exception:
                pass
        return None

    items = []
    for p in arquivos:
        ts = _parse_dt(p)
        if ts is None:
            continue
        subfolder = os.path.basename(os.path.dirname(p))
        nome_arq  = os.path.basename(p)
        items.append((ts, ts.strftime("%d/%m/%Y"), f"{subfolder}/{nome_arq}"))

    if not items:
        return

    # Detecta quais datas têm rolagem (presença de sec-rolagem no HTML gerado)
    rolagem_dates: set = set()
    for ts, _, href in items:
        full_path = os.path.join(root_dir, href)
        try:
            with open(full_path, "r", encoding="utf-8") as _fh:
                if 'id="sec-rolagem"' in _fh.read():
                    rolagem_dates.add(ts.strftime("%Y-%m-%d"))
        except Exception:
            pass
    rolagem_js = json.dumps(sorted(rolagem_dates), ensure_ascii=False)

    logo_tag = ""
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as _f:
            _b64 = base64.b64encode(_f.read()).decode()
        _ext  = os.path.splitext(LOGO_PATH)[1].lstrip(".").lower()
        _mime = "image/png" if _ext == "png" else f"image/{_ext}"
        logo_tag = f'<img src="data:{_mime};base64,{_b64}" class="logo-img" alt="Itaú">'

    # mapa JS: {"YYYY-MM-DD": "subpasta/arquivo.html"}
    reports_js = json.dumps(
        {ts.strftime("%Y-%m-%d"): href for ts, _, href in items},
        ensure_ascii=False
    )

    # mês inicial = mês do relatório mais recente
    init_year  = items[0][0].year
    init_month = items[0][0].month

    rows_html = []
    for i, (_, dt_fmt, href) in enumerate(items):
        badge = '<span class="badge">Mais recente</span>' if i == 0 else ""
        bg    = f' style="background:{ROW_PAR}"' if i % 2 == 1 else ""
        rows_html.append(
            f'<tr{bg}>'
            f'<td>{dt_fmt}{badge}</td>'
            f'<td><a href="{href}" class="link">{os.path.basename(href)}</a></td>'
            f'</tr>'
        )

    css = f"""
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f0f3fa; color: #1a1a2e; }}

    .hdr {{ background: {ITAU_DARK}; padding: 24px 40px 0; }}
    .hdr::after {{ content: ''; display: block; height: 4px; background: {ITAU_ORANGE}; margin-top: 20px; }}
    .hdr-inner {{ display: flex; align-items: center; justify-content: space-between; }}
    .hdr h1 {{ color: #fff; font-size: 1.7rem; font-weight: 700; letter-spacing: .06em; }}
    .hdr .sub {{ color: {ITAU_GRAY2}; font-size: .88rem; margin-top: 5px; }}
    .brand {{ display: flex; align-items: center; gap: 12px; }}
    .brand span {{ color: {ITAU_GRAY2}; font-size: 2.1rem; font-weight: 700; letter-spacing: .04em; }}
    .logo-img {{ height: 52px; width: auto; object-fit: contain; }}

    .content {{ padding: 40px; max-width: 960px; margin: 0 auto;
                display: grid; grid-template-columns: 320px 1fr; gap: 32px; align-items: start; }}

    /* ── Calendário ── */
    .cal-card {{ background: #fff; border-radius: 12px;
                 box-shadow: 0 2px 16px rgba(0,0,0,.10); overflow: hidden; }}
    .cal-nav {{ background: {ITAU_DARK}; display: flex; align-items: center;
                justify-content: space-between; padding: 14px 18px; }}
    .cal-nav button {{ background: none; border: none; color: #fff; font-size: 1.3rem;
                       cursor: pointer; padding: 0 6px; border-radius: 4px; }}
    .cal-nav button:hover {{ background: rgba(255,255,255,.15); }}
    .cal-nav span {{ color: #fff; font-weight: 700; font-size: 1rem; letter-spacing: .04em; }}
    .cal-grid {{ display: grid; grid-template-columns: repeat(7, 1fr); gap: 0; padding: 12px; }}
    .cal-dow {{ text-align: center; font-size: .72rem; font-weight: 700;
                color: {ITAU_GRAY2}; padding: 6px 0; text-transform: uppercase; }}
    .cal-day {{ text-align: center; padding: 8px 4px; font-size: .85rem;
                border-radius: 6px; cursor: default; color: #555; }}
    .cal-day.empty {{ background: none; }}
    .cal-day.has-report {{ background: {ITAU_ORANGE}; color: #fff; font-weight: 700;
                           cursor: pointer; transition: background .15s; }}
    .cal-day.has-report:hover {{ background: #c85e00; }}
    .cal-day.has-rolagem {{ background: {ITAU_RED}; color: #fff; font-weight: 700;
                            cursor: pointer; transition: background .15s; }}
    .cal-day.has-rolagem:hover {{ background: #96281b; }}
    .cal-day.today {{ outline: 2px solid {ITAU_DARK}; outline-offset: -2px; }}

    /* ── Legenda do calendário ── */
    .cal-legend {{ padding: 10px 14px 14px; display: flex; gap: 18px; flex-wrap: wrap;
                   border-top: 1px solid {ITAU_GRAY}; }}
    .leg-item {{ display: flex; align-items: center; gap: 7px;
                 font-size: .74rem; color: #555; }}
    .leg-swatch {{ display: inline-block; width: 13px; height: 13px;
                   border-radius: 3px; flex-shrink: 0; }}

    /* ── Tabela histórico ── */
    .tbl-card {{ background: #fff; border-radius: 12px;
                 box-shadow: 0 2px 16px rgba(0,0,0,.10); overflow: hidden; }}
    .tbl-title {{ background: {ITAU_DARK}; color: #fff; font-weight: 700;
                  font-size: .88rem; padding: 14px 20px; letter-spacing: .04em; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th {{ color: {ITAU_GRAY2}; font-weight: 600; padding: 10px 20px;
          text-align: left; font-size: .78rem; text-transform: uppercase;
          border-bottom: 2px solid {ITAU_GRAY}; }}
    td {{ padding: 11px 20px; border-bottom: 1px solid {ITAU_GRAY}; font-size: .85rem; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #eef3ff; transition: background .12s; }}
    .link {{ color: {ITAU_ORANGE}; text-decoration: none; font-weight: 600; }}
    .link:hover {{ text-decoration: underline; }}
    .badge {{ background: {ITAU_ORANGE}; color: #fff; font-size: .65rem; font-weight: 700;
              padding: 2px 8px; border-radius: 10px; margin-left: 8px; vertical-align: middle; }}

    .footer {{ border-top: 3px solid {ITAU_DARK}; padding: 16px 40px; margin-top: 40px;
               font-size: .78rem; color: {ITAU_GRAY2}; font-style: italic;
               text-align: center; background: #fff; }}
    """

    js = f"""
    const REPORTS      = {reports_js};
    const ROLAGEM_SET  = new Set({rolagem_js});
    const MONTHS  = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
                     'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];
    let curYear  = {init_year};
    let curMonth = {init_month - 1};   // 0-based

    function renderCal() {{
      const title = document.getElementById('cal-title');
      const grid  = document.getElementById('cal-grid');
      title.textContent = MONTHS[curMonth] + ' ' + curYear;
      grid.innerHTML = '';

      const today = new Date();
      const first = new Date(curYear, curMonth, 1).getDay(); // 0=Dom
      const days  = new Date(curYear, curMonth + 1, 0).getDate();

      for (let i = 0; i < first; i++) {{
        const el = document.createElement('div');
        el.className = 'cal-day empty';
        grid.appendChild(el);
      }}

      for (let d = 1; d <= days; d++) {{
        const el   = document.createElement('div');
        const key  = curYear + '-'
                   + String(curMonth + 1).padStart(2,'0') + '-'
                   + String(d).padStart(2,'0');
        const isToday = (d === today.getDate() &&
                         curMonth === today.getMonth() &&
                         curYear  === today.getFullYear());

        const hasRol  = ROLAGEM_SET.has(key);
        el.className = 'cal-day'
                     + (REPORTS[key] ? (hasRol ? ' has-rolagem' : ' has-report') : '')
                     + (isToday      ? ' today' : '');
        el.textContent = d;
        if (REPORTS[key]) {{
          el.title = (hasRol ? 'Com rolagem — ' : '') + 'Abrir relatório ' + key;
          el.onclick = () => window.location.href = REPORTS[key];
        }}
        grid.appendChild(el);
      }}
    }}

    function prevMonth() {{
      curMonth--;
      if (curMonth < 0) {{ curMonth = 11; curYear--; }}
      renderCal();
    }}
    function nextMonth() {{
      curMonth++;
      if (curMonth > 11) {{ curMonth = 0; curYear++; }}
      renderCal();
    }}

    renderCal();
    """

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Relatórios de Exposição — Histórico</title>
  <style>{css}</style>
</head>
<body>

<div class="hdr">
  <div class="hdr-inner">
    <div>
      <h1>RELATÓRIO DE INDEXADOS</h1>
      <p class="sub">Histórico — {len(items)} relatório(s) disponível(is)</p>
    </div>
    <div class="brand"><span>Itaú Asset Management</span>{logo_tag}</div>
  </div>
</div>

<div class="content">

  <div class="cal-card">
    <div class="cal-nav">
      <button onclick="prevMonth()">&#8249;</button>
      <span id="cal-title"></span>
      <button onclick="nextMonth()">&#8250;</button>
    </div>
    <div class="cal-grid">
      <div class="cal-dow">Dom</div><div class="cal-dow">Seg</div>
      <div class="cal-dow">Ter</div><div class="cal-dow">Qua</div>
      <div class="cal-dow">Qui</div><div class="cal-dow">Sex</div>
      <div class="cal-dow">Sáb</div>
    </div>
    <div id="cal-grid" class="cal-grid"></div>
    <div class="cal-legend">
      <span class="leg-item">
        <span class="leg-swatch" style="background:{ITAU_ORANGE}"></span>
        Relatório disponível
      </span>
      <span class="leg-item">
        <span class="leg-swatch" style="background:{ITAU_RED}"></span>
        Relatório com rolagem
      </span>
    </div>
  </div>

  <div class="tbl-card">
    <div class="tbl-title">HISTÓRICO DE RELATÓRIOS</div>
    <table>
      <thead><tr><th>Data de Referência</th><th>Arquivo</th></tr></thead>
      <tbody>{''.join(rows_html)}</tbody>
    </table>
  </div>

</div>

<div class="footer">Itaú Asset Management — Relatório de Exposição</div>

<script>{js}</script>
</body>
</html>"""

    nome = os.path.join(root_dir, "index.html")
    with open(nome, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  [OK] Index: {nome}")


# ─────────────────────────────────────────────────────────────────────────────
# GERAÇÃO DE PDF NAVEGÁVEL  (fpdf2 — compatível com Python 3.8)
# ─────────────────────────────────────────────────────────────────────────────

def gerar_pdf(abas_data: Dict[str, pd.DataFrame], dt: str, out_dir: str) -> None:
    try:
        from fpdf import FPDF, XPos, YPos
    except ImportError:
        print("  [AVISO] fpdf2 não encontrado — execute: pip install fpdf2")
        return

    os.makedirs(out_dir, exist_ok=True)
    dt_fmt = pd.to_datetime(dt).strftime("%d/%m/%Y")

    # ── Paleta (R, G, B 0-255) ───────────────────────────────────────────────
    def _hex(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    CD  = _hex(ITAU_DARK)    # azul escuro
    CO  = _hex(ITAU_ORANGE)  # laranja
    CW  = (255, 255, 255)    # branco
    CG2 = _hex(ITAU_GRAY2)  # cinza texto
    CR  = _hex(ROW_PAR)      # linha par
    CB  = (253, 232, 232)    # fora de banda
    CGR = _hex(ITAU_GREEN)   # verde
    CRD = _hex(ITAU_RED)     # vermelho

    # ── Configuração de colunas ───────────────────────────────────────────────
    SP500_COLS = ["FUNDO","PL","BENCH","TOTAL","DESC",
                  "EXPOSIÇÃO S&P","EXPOSIÇÃO IBX","EXPOSIÇÃO USD",
                  "PIBB + SPXI","FANG","Proventos % PL","ISP"]
    STD_COLS   = ["FUNDO","PL","BENCH","TOTAL","DESC",
                  "%AÇÕES","%FUT","%COTAS","Proventos % PL"]
    PCT_COLS   = {"TOTAL","DESC","%AÇÕES","%FUT","%COTAS","Proventos % PL",
                  "EXPOSIÇÃO S&P","EXPOSIÇÃO IBX","EXPOSIÇÃO USD",
                  "PIBB + SPXI","FANG","ISP"}

    def _fmt(col, val):
        if col == "PL":      return _fmt_money(val)
        if col in PCT_COLS:  return _fmt_pct(val)
        return _fmt_text(val)

    # largura relativa de cada coluna (soma = 1.0)
    COL_RATIOS = {"FUNDO": 0.14, "PL": 0.14, "BENCH": 0.07}

    # ── Classe PDF ───────────────────────────────────────────────────────────
    class ExposicaoPDF(FPDF):
        def __init__(self, dt_fmt, logo_path):
            super().__init__(orientation="L", unit="mm", format="A4")
            self._dt_fmt   = dt_fmt
            self._logo     = logo_path if os.path.exists(logo_path) else None
            self.set_margins(12, 22, 12)
            self.set_auto_page_break(auto=True, margin=12)

        def header(self):
            # barra azul escuro
            self.set_fill_color(*CD)
            self.rect(0, 0, self.w, 14, "F")
            # linha laranja
            self.set_fill_color(*CO)
            self.rect(0, 13.5, self.w, 1.5, "F")
            # texto esquerda
            self.set_font("Helvetica", "B", 11)
            self.set_text_color(*CW)
            self.set_xy(12, 3.5)
            self.cell(120, 7, "RELATÓRIO DE EXPOSIÇÃO", align="L")
            # data direita
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*CG2)
            txt = f"Data Referência: {self._dt_fmt}"
            if self._logo:
                self.set_xy(self.w - 12 - 60, 3.5)
                self.cell(42, 7, txt, align="R")
                try:
                    self.image(self._logo, x=self.w - 12 - 15, y=1, h=12)
                except Exception:
                    pass
            else:
                self.set_xy(self.w - 12 - 60, 3.5)
                self.cell(60, 7, txt, align="R")
            self.set_text_color(0, 0, 0)
            self.ln(2)

        def footer(self):
            self.set_y(-10)
            self.set_draw_color(*CD)
            self.set_line_width(0.4)
            self.line(12, self.h - 10, self.w - 12, self.h - 10)
            self.set_font("Helvetica", "", 7)
            self.set_text_color(*CG2)
            self.cell(0, 5,
                      f"Itau Asset Management  |  {self._dt_fmt}  |  pag. {self.page_no()}",
                      align="C")
            self.set_text_color(0, 0, 0)

        def section_title(self, title: str):
            self.set_font("Helvetica", "B", 11)
            self.set_text_color(*CO)
            self.cell(0, 7, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_draw_color(*CO)
            self.set_line_width(0.5)
            self.line(self.l_margin, self.get_y(),
                      self.w - self.r_margin, self.get_y())
            self.ln(3)
            self.set_text_color(0, 0, 0)

        def data_table(self, df: pd.DataFrame, cols: list):
            usable = self.w - self.l_margin - self.r_margin
            n      = len(cols)

            # larguras em mm
            widths = []
            for c in cols:
                r = COL_RATIOS.get(c, (1 - sum(COL_RATIOS.get(x, 0) for x in cols
                                               if x in COL_RATIOS)) /
                                   max(1, sum(1 for x in cols if x not in COL_RATIOS)))
                widths.append(usable * r)

            row_h  = 6.5
            hdr_h  = 7

            # ── Cabeçalho ────────────────────────────────────────────────────
            self.set_fill_color(*CD)
            self.set_text_color(*CW)
            self.set_font("Helvetica", "B", 7)
            self.set_draw_color(200, 200, 200)
            self.set_line_width(0.2)
            for i, c in enumerate(cols):
                align = "L" if i == 0 else "C"
                self.cell(widths[i], hdr_h, c, border=1, align=align, fill=True)
            # linha laranja sob cabeçalho
            y_after = self.get_y() + hdr_h
            self.ln(hdr_h)
            self.set_draw_color(*CO)
            self.set_line_width(0.6)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
            self.set_line_width(0.2)
            self.set_draw_color(200, 200, 200)

            idx_tot = cols.index("TOTAL") if "TOTAL" in cols else -1

            # ── Linhas de dados ───────────────────────────────────────────────
            for ri, (_, row) in enumerate(df.iterrows()):
                # verifica banda
                fora = False
                try:
                    v_tot = float(row["TOTAL"])
                    v_max = row.get("MAX", float("nan"))
                    v_min = row.get("MIN", float("nan"))
                    if (not pd.isna(v_max) and not pd.isna(v_min)
                            and float(v_max) != 0 and float(v_min) != 0):
                        fora = v_tot > float(v_max) or v_tot < float(v_min)
                except Exception:
                    pass

                bg = CB if fora else (CR if ri % 2 == 1 else CW)
                self.set_fill_color(*bg)

                # quebra de página automática com cabeçalho repetido
                if self.get_y() + row_h > self.h - self.b_margin:
                    self.add_page()
                    self.set_fill_color(*CD)
                    self.set_text_color(*CW)
                    self.set_font("Helvetica", "B", 7)
                    for i, c in enumerate(cols):
                        align = "L" if i == 0 else "C"
                        self.cell(widths[i], hdr_h, c, border=1,
                                  align=align, fill=True)
                    self.ln(hdr_h)
                    self.set_draw_color(*CO)
                    self.set_line_width(0.6)
                    self.line(self.l_margin, self.get_y(),
                              self.w - self.r_margin, self.get_y())
                    self.set_line_width(0.2)
                    self.set_draw_color(200, 200, 200)
                    self.set_fill_color(*bg)

                for i, c in enumerate(cols):
                    is_sp500_row = "EXPOSIÇÃO S&P" in df.columns
                    if c == "DESC" and is_sp500_row:
                        text = _fmt_pct3(row.get(c, ""))
                    else:
                        text = _fmt(c, row.get(c, ""))
                    align = "L" if i == 0 else "C"

                    if i == idx_tot:
                        try:
                            v = float(row["TOTAL"])
                            tc = CRD if fora else (CGR if v >= 0.99 else CO)
                        except Exception:
                            tc = (0, 0, 0)
                        self.set_text_color(*tc)
                        self.set_font("Helvetica", "B", 7)
                        self.cell(widths[i], row_h, text, border=1,
                                  align=align, fill=True)
                        self.set_font("Helvetica", "", 7)
                        self.set_text_color(0, 0, 0)
                    else:
                        self.set_text_color(0, 0, 0)
                        self.set_font("Helvetica", "", 7)
                        self.cell(widths[i], row_h, text, border=1,
                                  align=align, fill=True)
                self.ln(row_h)

    # ── Gera PDF ─────────────────────────────────────────────────────────────
    pdf = ExposicaoPDF(dt_fmt, LOGO_PATH)
    pdf.set_title(f"Relatório de Exposição — {dt_fmt}")
    pdf.set_author("Itaú Asset Management")

    first = True
    for aba, df in abas_data.items():
        if df is None or df.empty:
            continue

        pdf.add_page()
        pdf.start_section(aba)          # bookmark navegável

        pdf.section_title(aba)

        is_sp500 = "EXPOSIÇÃO S&P" in df.columns
        cols = [c for c in (SP500_COLS if is_sp500 else STD_COLS)
                if c in df.columns]
        pdf.data_table(df, cols)

    nome = os.path.join(out_dir, f"exposicao_{dt}.pdf")
    pdf.output(nome)
    print(f"  [OK] PDF: {nome}")


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO BETA  (Exposição Beta V20 — aba "Index")
# ─────────────────────────────────────────────────────────────────────────────

BETA_BASE_DATE = "2025-04-30"
BETA_BASE_PL   = 100_000_000.0   # PL de referência para as "quantidades teóricas"

# Mapeamento: FICAD_CD → (ticker_display, w_cons, w_mod, w_agr, nav_base)
# nav_base = cota do FICAD_CD na data base (col L da aba Index)
BETA_ATIVOS: Dict[str, tuple] = {
    "ITAUIMAB64215":  ("IB5M11",       0.050, 0.035, 0.035, 113.383611),
    "ITAUIBOV62154":  ("BOVV11",        0.000, 0.030, 0.030, 140.397291),
    "ITAUIRFMP24216": ("IRFM11",        0.000, 0.075, 0.150,  89.276339),
    "ITAUTRN61201":   ("SPXI11",        0.000, 0.065, 0.140, 367.950276),
    "FTSERARV52631":  ("FTSERARV52631", 0.000, 0.050, 0.100,  35.770297),
    "TESAM10A54529":  ("TESAM10A54529", 0.000, 0.080, 0.130,  10.518801),
    "ITAUIMA5P2070":  ("B5P211",        0.250, 0.115, 0.215,  96.229888),
    "ITAUIMAB64066":  ("IMAB11",        0.000, 0.000, 0.000, 102.986080),
    "ITAUBLO66606":   ("BITI11",        0.000, 0.000, 0.000, 162.806697),
    "FIDELILCMM771":  ("FIDELILCMM771", 0.700, 0.550, 0.200,  37.626401),
}

# Fundos INTRA → perfil benchmark
BETA_FUNDS: Dict[str, str] = {
    "INTRAGITAU362": "Conservador",
    "INTRAGITAU363": "Moderado",
    "INTRAGITAU364": "Agressivo",
}

BETA_DIF_THRESHOLD = 0.0015   # ±0.15% — limiar para verde/vermelho
BETA_COLOR_GREEN   = "#e8f5e9"
BETA_COLOR_YELLOW  = "#fffde7"
BETA_COLOR_RED     = "#fde8e8"


def buscar_nav_beta(dt: str) -> Dict[str, float]:
    ficad_cds = list(BETA_ATIVOS.keys())
    q = f"""
        SELECT codigo_iam_fundo, cota
        FROM   dbsx337.dbo.view_fundos_cotas_pl WITH (NOLOCK)
        WHERE  date = '{dt}'
          AND  codigo_iam_fundo IN ({_ids(ficad_cds)})
    """
    db  = sql.get_connection()
    df  = db.run_query(q)
    if df is None or df.empty:
        return {}
    return dict(zip(df["codigo_iam_fundo"].astype(str),
                    pd.to_numeric(df["cota"], errors="coerce")))


# def calcular_targets_beta(nav_map: Dict[str, float]) -> Dict[str, Dict[str, float]]:
#     """
#     Targets com drift de preço desde a data-base.
#     Formula: unidades = (peso_raw * BASE_PL) / nav_base
#              valor_d1 = unidades * nav_d1
#              target_% = valor_d1 / SUM(valores_d1)
#     """
#     perfs = ("Conservador", "Moderado", "Agressivo")
#     brl: Dict[str, Dict[str, float]] = {p: {} for p in perfs}

#     for ficad, (ticker, w_c, w_m, w_a, nav_b) in BETA_ATIVOS.items():
#         nav_d1  = nav_map.get(ficad, 0.0) or 0.0
#         weights = (w_c, w_m, w_a)
#         for perf, w in zip(perfs, weights):
#             if nav_b > 0 and nav_d1 > 0:
#                 units = (w * BETA_BASE_PL) / nav_b
#                 brl[perf][ficad] = units * nav_d1
#             else:
#                 brl[perf][ficad] = w * BETA_BASE_PL

#     targets: Dict[str, Dict[str, float]] = {}
#     for perf in perfs:
#         total = sum(brl[perf].values())
#         if total > 0:
#             targets[perf] = {f: v / total for f, v in brl[perf].items()}
#         else:
#             targets[perf] = {f: 0.0 for f in BETA_ATIVOS}

#     return targets

def calcular_targets_beta(nav_map: Dict[str, float]) -> Dict[str, Dict[str, float]]:
    perfs = ("Conservador", "Moderado", "Agressivo")
    brl = {p: {} for p in perfs}

    for ficad, (_, w_c, w_m, w_a, nav_base) in BETA_ATIVOS.items():
        nav_d1 = float(nav_map.get(ficad) or 0.0)

        for perf, peso in zip(perfs, (w_c, w_m, w_a)):
            if nav_base > 0 and nav_d1 > 0:
                unidades = (peso * BETA_BASE_PL) / nav_base
                valor = unidades * nav_d1
            else:
                valor = peso * BETA_BASE_PL

            brl[perf][ficad] = valor

    targets = {}
    for perf in perfs:
        total = sum(brl[perf].values())

        targets[perf] = {
            ficad: (valor / total if total > 0 else 0.0)
            for ficad, valor in brl[perf].items()
        }

    return targets


def buscar_cotas_quebradas(dt: str) -> pd.DataFrame:
    fundos_beta = list(BETA_FUNDS.keys())
    q = f"""
        SELECT clcli_cd, FICAD_CD, SUM(vl_liq) AS SOMA_VL_COTAS
        FROM   dbsx337.dbo.view_vcrapfdo WITH (NOLOCK)
        WHERE  dt = '{dt}'
          AND  clcli_cd IN ({_ids(fundos_beta)})
        GROUP  BY clcli_cd, FICAD_CD
    """
    db = sql.get_connection()
    df = db.run_query(q)
    return df if (df is not None and not df.empty) else pd.DataFrame(
        columns=["clcli_cd", "FICAD_CD", "SOMA_VL_COTAS"])


# def montar_tabela_beta(cotas_df: pd.DataFrame,
#                        pl_map:   Dict[str, float],
#                        targets:  Dict[str, Dict[str, float]]) -> pd.DataFrame:
#     rows = []
#     for ficad, (ticker, *_) in BETA_ATIVOS.items():
#         row: Dict = {"ATIVO": ticker, "FICAD_CD": ficad}
#         for fund, profile in BETA_FUNDS.items():
#             pl = pl_map.get(fund, np.nan)
#             soma = 0.0
#             if not cotas_df.empty:
#                 mask = ((cotas_df["clcli_cd"].astype(str) == fund) &
#                         (cotas_df["FICAD_CD"].astype(str) == ficad))
#                 vals = cotas_df.loc[mask, "SOMA_VL_COTAS"]
#                 if not vals.empty:
#                     soma = float(pd.to_numeric(vals.iloc[0], errors="coerce") or 0)

#             actual = soma / pl if (pl and not np.isnan(pl) and pl > 0) else 0.0
#             target = targets.get(profile, {}).get(ficad, 0.0)
#             row[fund]              = actual
#             row[profile]           = target
#             row[f"DIF_{profile}"]  = actual - target
#         rows.append(row)
#     return pd.DataFrame(rows)


# def montar_tabela_beta(cotas_df, pl_map, targets):

#     rows = []

#     for ficad, (ticker, *_ ) in BETA_ATIVOS.items():
#         if ficad == "FIDELILCMM771":
#             continue

#         row = {"ATIVO": ticker}

#         for fund, profile in BETA_FUNDS.items():
#             pl = pl_map.get(fund, np.nan)

#             mask = (
#                 (cotas_df["clcli_cd"].astype(str) == fund) &
#                 (cotas_df["FICAD_CD"].astype(str) == ficad)
#             )

#             soma = cotas_df.loc[mask, "SOMA_VL_COTAS"].sum()
#             soma = float(soma) if soma else 0

#             actual = soma / pl if pl and not np.isnan(pl) else 0
#             target = targets[profile].get(ficad, 0)

#             row[fund] = actual
#             row[profile] = target
#             row[f"DIF_{profile}"] = actual - target

#         rows.append(row)

#     # CDI = residual
#     row_cdi = {"ATIVO": "CDI"}
#     for fund, profile in BETA_FUNDS.items():
#         pl = pl_map.get(fund, 0)

#         soma_outros = sum(
#             r[fund] for r in rows if fund in r
#         )

#         cdi = max(0, 1 - soma_outros)

#         target = targets[profile].get("FIDELILCMM771", 0)

#         row_cdi[fund] = cdi
#         row_cdi[profile] = target
#         row_cdi[f"DIF_{profile}"] = cdi - target

#     rows.append(row_cdi)

#     return pd.DataFrame(rows)

def montar_tabela_beta(cotas_df, pl_map, targets):

    rows = []
    soma_nao_cdi = {f: 0.0 for f in BETA_FUNDS.keys()}

    for ficad, (ticker, *_ ) in BETA_ATIVOS.items():

        if ficad == "FIDELILCMM771":
            continue

        row = {"ATIVO": ticker}

        for fund, profile in BETA_FUNDS.items():

            pl = pl_map.get(fund, np.nan)

            mask = (
                (cotas_df["clcli_cd"].astype(str) == fund) &
                (cotas_df["FICAD_CD"].astype(str) == ficad)
            )

            soma = cotas_df.loc[mask, "SOMA_VL_COTAS"].sum()
            soma = float(soma) if not pd.isna(soma) else 0.0

            actual = soma / pl if (pl and not np.isnan(pl) and pl > 0) else 0.0

            soma_nao_cdi[fund] += actual

            target = targets[profile].get(ficad, 0.0)

            row[fund] = actual
            row[profile] = target
            row[f"DIF_{profile}"] = actual - target

        rows.append(row)

    # CDI residual
    row_cdi = {"ATIVO": "CDI"}

    for fund, profile in BETA_FUNDS.items():

        actual_cdi = max(0.0, 1.0 - soma_nao_cdi[fund])
        target = targets[profile].get("FIDELILCMM771", 0.0)

        row_cdi[fund] = actual_cdi
        row_cdi[profile] = target
        row_cdi[f"DIF_{profile}"] = actual_cdi - target

    rows.append(row_cdi)

    return pd.DataFrame(rows)



def gerar_imagem_beta(df: pd.DataFrame, dt: str, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    if df is None or df.empty:
        print("  [BETA] sem dados — pulando.")
        return

    dt_fmt = pd.to_datetime(dt).strftime("%d/%m/%Y")
    funds  = list(BETA_FUNDS.keys())
    profs  = list(BETA_FUNDS.values())

    # Ordem das colunas para exibição
    disp_cols = ["ATIVO"]
    disp_hdrs = [""]
    for fund, prof in BETA_FUNDS.items():
        disp_cols += [fund, prof, f"DIF_{prof}"]
        disp_hdrs += [fund, prof, "Dif"]

    n_rows = len(df)
    n_cols = len(disp_cols)

    # Build cell text matrix and color matrix
    cell_text   = []
    cell_colors = []

    for _, row in df.iterrows():
        txt_row = []
        clr_row = []
        for col in disp_cols:
            val = row[col]
            if col == "ATIVO":
                txt_row.append(str(val))
                clr_row.append(ITAU_WHITE)
            elif col.startswith("DIF_"):
                pct = float(val) if pd.notna(val) else 0.0
                txt_row.append(f"{pct:.2%}")
                if pct > BETA_DIF_THRESHOLD:
                    clr_row.append(BETA_COLOR_GREEN)
                elif pct < -BETA_DIF_THRESHOLD:
                    clr_row.append(BETA_COLOR_RED)
                else:
                    clr_row.append(BETA_COLOR_YELLOW)
            else:
                pct = float(val) if pd.notna(val) else 0.0
                txt_row.append(f"{pct:.2%}")
                clr_row.append(ITAU_WHITE)
        cell_text.append(txt_row)
        cell_colors.append(clr_row)

    # Apply alternating row background to non-Dif columns
    for ri in range(n_rows):
        bg = ROW_PAR if ri % 2 == 0 else ITAU_WHITE
        for ci, col in enumerate(disp_cols):
            if not col.startswith("DIF_") and col != "ATIVO":
                cell_colors[ri][ci] = bg
            elif col == "ATIVO":
                cell_colors[ri][ci] = bg

    fig_w = max(28, n_cols * 2.5)
    fig_h = 3.0 + n_rows * 0.65 + 0.4
    fig   = plt.figure(figsize=(fig_w, fig_h), facecolor=ITAU_WHITE)

    gs = gridspec.GridSpec(4, 1, figure=fig,
                           height_ratios=[1.10, 1.60, n_rows * 0.65 + 0.4, 0.40],
                           hspace=0, left=0.0, right=1.0)

    # ── faixa topo ──────────────────────────────────────────────────────────
    ax_b = fig.add_subplot(gs[0])
    ax_b.set_facecolor(ITAU_DARK); ax_b.axis("off")
    ax_b.axhline(y=0.06, color=ITAU_ORANGE, linewidth=2.5)

    # ── título ──────────────────────────────────────────────────────────────
    ax_h = fig.add_subplot(gs[1])
    ax_h.set_facecolor(ITAU_WHITE); ax_h.axis("off")
    ax_h.set_xlim(0, 1); ax_h.set_ylim(0, 1)
    ax_h.text(0.018, 0.82, "RELATÓRIO DE EXPOSIÇÃO BETA",
              transform=ax_h.transAxes, fontsize=32, fontweight="bold",
              color=ITAU_DARK, va="center", ha="left")
    ax_h.text(0.018, 0.30, "INTRAGITAU — Posição vs Benchmark",
              transform=ax_h.transAxes, fontsize=20, color=ITAU_ORANGE,
              va="center", ha="left")
    ax_h.text(0.988, 0.82, f"Data Referência:  {dt_fmt}",
              transform=ax_h.transAxes, fontsize=18, color=ITAU_DARK,
              va="center", ha="right")
    ax_h.axhline(y=0.14, color=ITAU_GRAY, linewidth=1.2)

    # ── tabela ──────────────────────────────────────────────────────────────
    ax_t = fig.add_subplot(gs[2])
    ax_t.set_facecolor(ITAU_WHITE); ax_t.axis("off")

    col_widths = [0.10] + [0.09, 0.09, 0.06] * 3
    tbl = ax_t.table(cellText=cell_text,
                     colLabels=disp_hdrs,
                     cellLoc="center",
                     loc="center",
                     colWidths=col_widths)
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(11)
    tbl.scale(1, 2.2)

    FONT_SIZE = 13

    # Cabeçalho
    for ci in range(n_cols):
        cell = tbl[0, ci]
        cell.set_facecolor(ITAU_DARK)
        cell.set_text_props(color=ITAU_WHITE, fontweight="bold", fontsize=FONT_SIZE)
        cell.set_edgecolor(ITAU_WHITE)
        cell.set_linewidth(0.8)

    # Linhas de dados
    dif_indices = [i for i, c in enumerate(disp_cols) if c.startswith("DIF_")]
    for ri in range(n_rows):
        for ci in range(n_cols):
            cell = tbl[ri + 1, ci]
            cell.set_facecolor(cell_colors[ri][ci])
            cell.set_edgecolor(ITAU_GRAY)
            cell.set_linewidth(0.5)
            if ci in dif_indices:
                dif_val = df.iloc[ri][disp_cols[ci]]
                try:
                    dif_f = float(dif_val)
                    if dif_f > BETA_DIF_THRESHOLD:
                        cell.set_text_props(color=ITAU_GREEN, fontweight="bold",
                                            fontsize=FONT_SIZE)
                    elif dif_f < -BETA_DIF_THRESHOLD:
                        cell.set_text_props(color=ITAU_RED, fontweight="bold",
                                            fontsize=FONT_SIZE)
                    else:
                        cell.set_text_props(color="#7d6608", fontsize=FONT_SIZE)
                except Exception:
                    pass

    # ── rodapé ──────────────────────────────────────────────────────────────
    ax_f = fig.add_subplot(gs[3])
    ax_f.set_facecolor(ITAU_WHITE); ax_f.axis("off")
    ax_f.set_xlim(0, 1); ax_f.set_ylim(0, 1)
    ax_f.axhline(y=0.95, color=ITAU_DARK, linewidth=1.5)
    ax_f.text(
        0.5, 0.38,
        f"Dif = Fundo − Benchmark  |  Verde > +{BETA_DIF_THRESHOLD:.2%}  |  "
        f"Vermelho < −{BETA_DIF_THRESHOLD:.2%}  |  "
        f"Targets com drift de preço desde {BETA_BASE_DATE}",
        transform=ax_f.transAxes, fontsize=10, color=ITAU_GRAY2,
        ha="center", va="center", style="italic"
    )

    nome = os.path.join(out_dir, f"exposicao_beta_{dt}.png")
    plt.savefig(nome, dpi=150, bbox_inches="tight",
                facecolor=ITAU_WHITE, edgecolor="none")
    plt.close()
    print(f"  [OK] {nome}")


# ─────────────────────────────────────────────────────────────────────────────
# BETA 2 — cálculo direto da aba "Posição" (Exposição Beta V20)
# actual% = SUM(vl_liq) de view_vcrapfdo  /  vl_patrliqtot1 de view_vcraplsi
# target% = peso_raw × (nav_d1 / nav_base), normalizado por perfil
# ─────────────────────────────────────────────────────────────────────────────

def _buscar_cotas_quebradas_b2(dt: str) -> pd.DataFrame:
    """
    Retorna o valor BRL de cada sub-fundo (FICAD_CD) dentro de cada fundo INTRA.
    Equivale à coluna de valores BRL na aba Posição do Excel.
    """
    fundos = list(BETA_FUNDS.keys())
    ficads = list(BETA_ATIVOS.keys())
    q = f"""
        SELECT clcli_cd      AS FUNDO,
               FICAD_CD,
               SUM(vl_liq)  AS VL_BRL
        FROM   dbsx337.dbo.view_vcrapfdo WITH (NOLOCK)
        WHERE  dt = '{dt}'
          AND  clcli_cd IN ({_ids(fundos)})
          AND  FICAD_CD  IN ({_ids(ficads)})
        GROUP  BY clcli_cd, FICAD_CD
    """
    db = sql.get_connection()
    df = db.run_query(q)
    return df if (df is not None and not df.empty) else pd.DataFrame(
        columns=["FUNDO", "FICAD_CD", "VL_BRL"])


def _calcular_targets_b2(nav_map: Dict[str, float]) -> Dict[str, Dict[str, float]]:
    """
    Replica a fórmula da aba Index do Excel:
      unidades  = peso_raw × BASE_PL / nav_base
      valor_d1  = unidades × nav_d1
      target_%  = valor_d1 / SUM(valor_d1 do perfil)
    """
    perfs = ("Conservador", "Moderado", "Agressivo")
    brl: Dict[str, Dict[str, float]] = {p: {} for p in perfs}

    for ficad, (_, w_c, w_m, w_a, nav_b) in BETA_ATIVOS.items():
        nav_d1  = float(nav_map.get(ficad) or 0.0)
        for perf, w in zip(perfs, (w_c, w_m, w_a)):
            if nav_b > 0 and nav_d1 > 0:
                brl[perf][ficad] = (w * BETA_BASE_PL / nav_b) * nav_d1
            else:
                brl[perf][ficad] = w * BETA_BASE_PL

    targets: Dict[str, Dict[str, float]] = {}
    for perf in perfs:
        total = sum(brl[perf].values())
        targets[perf] = (
            {f: v / total for f, v in brl[perf].items()} if total > 0
            else {f: 0.0 for f in BETA_ATIVOS}
        )
    return targets


_CDI_FICAD = "FIDELILCMM771"  # linha CDI é residual: PL − Σ(outros ativos)


def _soma_brl(cotas_df: pd.DataFrame, fund: str, ficad: str) -> float:
    if cotas_df.empty:
        return 0.0
    mask = (cotas_df["FUNDO"].astype(str) == fund) & \
           (cotas_df["FICAD_CD"].astype(str) == ficad)
    vl = cotas_df.loc[mask, "VL_BRL"]
    return float(pd.to_numeric(vl.iloc[0], errors="coerce") or 0) if not vl.empty else 0.0


def _montar_df_beta_2(cotas_df: pd.DataFrame,
                      pl_map:   Dict[str, float],
                      targets:  Dict[str, Dict[str, float]]) -> pd.DataFrame:
    """
    Replica a aba Posição de Exposição Beta V20.

    Para cada ativo não-CDI:
        actual% = SUM(vl_liq de view_vcrapfdo para FICAD_CD) / PL

    Para FIDELILCMM771 (CDI):
        actual% = 1 − Σ(actual% de todos os outros ativos)
        ≡ (PL − Σ BRL dos outros ativos) / PL
    Isso captura todo o caixa remanescente: FIDELILCMM771 + LFTs + Reserva − CPR.
    """
    rows: list = []
    # acumulador de actual% não-CDI por fundo
    soma_nao_cdi: Dict[str, float] = {f: 0.0 for f in BETA_FUNDS}

    for ficad, (ticker, *_) in BETA_ATIVOS.items():
        if ficad == _CDI_FICAD:
            continue  # calculado após o loop como resíduo

        row: Dict = {"ATIVO": ticker}
        for fund, profile in BETA_FUNDS.items():
            pl     = pl_map.get(fund, np.nan)
            soma   = _soma_brl(cotas_df, fund, ficad)
            actual = soma / pl if (pl and not np.isnan(pl) and pl > 0) else 0.0
            soma_nao_cdi[fund] += actual
            target = targets.get(profile, {}).get(ficad, 0.0)
            row[fund]             = actual
            row[profile]          = target
            row[f"DIF_{profile}"] = actual - target
        rows.append(row)

    # linha CDI: resíduo = 1 − Σ(actual% não-CDI)
    cdi_ticker = BETA_ATIVOS[_CDI_FICAD][0]
    row_cdi: Dict = {"ATIVO": cdi_ticker}
    for fund, profile in BETA_FUNDS.items():
        cdi_actual = max(0.0, 1.0 - soma_nao_cdi[fund])
        target = targets.get(profile, {}).get(_CDI_FICAD, 0.0)
        row_cdi[fund]             = cdi_actual
        row_cdi[profile]          = target
        row_cdi[f"DIF_{profile}"] = cdi_actual - target
    rows.append(row_cdi)

    return pd.DataFrame(rows)


def gerar_imagem_beta_2(dt: str, out_dir: str) -> None:
    """
    Gera exposicao_beta_2_{dt}.png — tabela de comparação actual vs target
    baseada na aba Posição de Exposição Beta V20.
    """
    os.makedirs(out_dir, exist_ok=True)

    cotas_df = _buscar_cotas_quebradas_b2(dt)
    nav_map  = buscar_nav_beta(dt)
    pl_intra = buscar_pl(dt, list(BETA_FUNDS.keys()))
    targets  = _calcular_targets_b2(nav_map)
    df       = _montar_df_beta_2(cotas_df, pl_intra, targets)

    if df is None or df.empty:
        print("  [BETA2] sem dados — pulando.")
        return

    dt_fmt    = pd.to_datetime(dt).strftime("%d/%m/%Y")
    disp_cols = ["ATIVO"]
    disp_hdrs = [""]
    for fund, prof in BETA_FUNDS.items():
        disp_cols += [fund, prof, f"DIF_{prof}"]
        disp_hdrs += [fund, prof, "Dif"]

    n_rows = len(df)
    n_cols = len(disp_cols)

    cell_text:   list = []
    cell_colors: list = []

    for _, row in df.iterrows():
        txt_row, clr_row = [], []
        for col in disp_cols:
            val = row[col]
            if col == "ATIVO":
                txt_row.append(str(val))
                clr_row.append(ITAU_WHITE)
            elif col.startswith("DIF_"):
                pct = float(val) if pd.notna(val) else 0.0
                txt_row.append(f"{pct:+.2%}")
                if pct > BETA_DIF_THRESHOLD:
                    clr_row.append(BETA_COLOR_GREEN)
                elif pct < -BETA_DIF_THRESHOLD:
                    clr_row.append(BETA_COLOR_RED)
                else:
                    clr_row.append(BETA_COLOR_YELLOW)
            else:
                pct = float(val) if pd.notna(val) else 0.0
                txt_row.append(f"{pct:.2%}")
                clr_row.append(ITAU_WHITE)
        cell_text.append(txt_row)
        cell_colors.append(clr_row)

    for ri in range(n_rows):
        bg = ROW_PAR if ri % 2 == 0 else ITAU_WHITE
        for ci, col in enumerate(disp_cols):
            if not col.startswith("DIF_"):
                cell_colors[ri][ci] = bg

    fig_w = max(28, n_cols * 2.5)
    fig_h = 3.0 + n_rows * 0.65 + 0.4
    fig   = plt.figure(figsize=(fig_w, fig_h), facecolor=ITAU_WHITE)
    gs    = gridspec.GridSpec(4, 1, figure=fig,
                              height_ratios=[1.10, 1.60, n_rows * 0.65 + 0.4, 0.40],
                              hspace=0, left=0.0, right=1.0)

    # faixa topo
    ax_b = fig.add_subplot(gs[0])
    ax_b.set_facecolor(ITAU_DARK); ax_b.axis("off")
    ax_b.axhline(y=0.06, color=ITAU_ORANGE, linewidth=2.5)

    # título
    ax_h = fig.add_subplot(gs[1])
    ax_h.set_facecolor(ITAU_WHITE); ax_h.axis("off")
    ax_h.set_xlim(0, 1); ax_h.set_ylim(0, 1)
    ax_h.text(0.018, 0.82, "RELATÓRIO DE EXPOSIÇÃO BETA",
              transform=ax_h.transAxes, fontsize=32, fontweight="bold",
              color=ITAU_DARK, va="center", ha="left")
    ax_h.text(0.018, 0.30, "INTRAGITAU — Posição vs Benchmark",
              transform=ax_h.transAxes, fontsize=20, color=ITAU_ORANGE,
              va="center", ha="left")
    ax_h.text(0.988, 0.82, f"Data Referência:  {dt_fmt}",
              transform=ax_h.transAxes, fontsize=18, color=ITAU_DARK,
              va="center", ha="right")
    ax_h.axhline(y=0.14, color=ITAU_GRAY, linewidth=1.2)

    # tabela
    ax_t = fig.add_subplot(gs[2])
    ax_t.set_facecolor(ITAU_WHITE); ax_t.axis("off")
    col_widths = [0.10] + [0.09, 0.09, 0.06] * 3
    tbl = ax_t.table(cellText=cell_text, colLabels=disp_hdrs,
                     cellLoc="center", loc="center", colWidths=col_widths)
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(11)
    tbl.scale(1, 2.2)

    FONT_SIZE = 13
    for ci in range(n_cols):
        cell = tbl[0, ci]
        cell.set_facecolor(ITAU_DARK)
        cell.set_text_props(color=ITAU_WHITE, fontweight="bold", fontsize=FONT_SIZE)
        cell.set_edgecolor(ITAU_WHITE)
        cell.set_linewidth(0.8)

    dif_indices = [i for i, c in enumerate(disp_cols) if c.startswith("DIF_")]
    for ri in range(n_rows):
        for ci in range(n_cols):
            cell = tbl[ri + 1, ci]
            cell.set_facecolor(cell_colors[ri][ci])
            cell.set_edgecolor(ITAU_GRAY)
            cell.set_linewidth(0.5)
            if ci in dif_indices:
                try:
                    dif_f = float(df.iloc[ri][disp_cols[ci]])
                    if dif_f > BETA_DIF_THRESHOLD:
                        cell.set_text_props(color=ITAU_GREEN, fontweight="bold",
                                            fontsize=FONT_SIZE)
                    elif dif_f < -BETA_DIF_THRESHOLD:
                        cell.set_text_props(color=ITAU_RED, fontweight="bold",
                                            fontsize=FONT_SIZE)
                    else:
                        cell.set_text_props(color="#7d6608", fontsize=FONT_SIZE)
                except Exception:
                    pass
            else:
                cell.set_text_props(fontsize=FONT_SIZE)

    # rodapé
    ax_f = fig.add_subplot(gs[3])
    ax_f.set_facecolor(ITAU_WHITE); ax_f.axis("off")
    ax_f.set_xlim(0, 1); ax_f.set_ylim(0, 1)
    ax_f.axhline(y=0.95, color=ITAU_DARK, linewidth=1.5)
    ax_f.text(
        0.5, 0.38,
        f"Dif = Fundo − Benchmark  |  Verde > +{BETA_DIF_THRESHOLD:.2%}  |  "
        f"Vermelho < −{BETA_DIF_THRESHOLD:.2%}  |  "
        f"Targets com drift de preço desde {BETA_BASE_DATE}",
        transform=ax_f.transAxes, fontsize=10, color=ITAU_GRAY2,
        ha="center", va="center", style="italic"
    )

    nome = os.path.join(out_dir, f"exposicao_beta_2_{dt}.png")
    plt.savefig(nome, dpi=150, bbox_inches="tight",
                facecolor=ITAU_WHITE, edgecolor="none")
    plt.close()
    print(f"  [OK] {nome}")


# ─────────────────────────────────────────────────────────────────────────────
# EXCEL E PDF DE ROLAGEM
# ─────────────────────────────────────────────────────────────────────────────

def exportar_excel_rolagem(rolagem_data: List[tuple], dt: str, out_dir: str) -> None:
    from openpyxl.styles import PatternFill, Font, Alignment
    from openpyxl.utils import get_column_letter

    if not rolagem_data:
        return

    os.makedirs(out_dir, exist_ok=True)
    nome = os.path.join(out_dir, f"rolagem_{dt}.xlsx")

    def to_argb(h: str) -> str:
        return "FF" + h.lstrip("#").upper()

    with pd.ExcelWriter(nome, engine="openpyxl") as writer:
        for label, df, v1, v2 in rolagem_data:
            sheet_name = label[:31]
            df_copy = df.copy().sort_values("FUNDO")
            df_copy.to_excel(writer, sheet_name=sheet_name, index=False)
            ws = writer.sheets[sheet_name]
            col_names = list(df_copy.columns)

            hdr_fill = PatternFill("solid", fgColor=to_argb(ITAU_DARK))
            hdr_font = Font(bold=True, color=to_argb(ITAU_WHITE), size=11)
            for cell in ws[1]:
                cell.fill      = hdr_fill
                cell.font      = hdr_font
                cell.alignment = Alignment(horizontal="center", vertical="center")

            for ri in range(2, ws.max_row + 1):
                bg      = ROW_PAR if ri % 2 == 0 else ITAU_WHITE
                row_fill = PatternFill("solid", fgColor=to_argb(bg))
                for ci, col_name in enumerate(col_names, start=1):
                    cell = ws.cell(row=ri, column=ci)
                    cell.fill = row_fill
                    if col_name == "PL":
                        cell.number_format = '"R$ "#,##0.00'
                        cell.alignment     = Alignment(horizontal="right")
                    elif "%" in col_name:
                        cell.number_format = "0.00%"
                        cell.alignment     = Alignment(horizontal="center")
                        try:
                            v = float(cell.value) if cell.value is not None else 0
                            color = ITAU_GREEN if v > 0 else (ITAU_RED if v < 0 else ITAU_DARK)
                            cell.font = Font(bold=(v != 0), color=to_argb(color))
                        except Exception:
                            pass
                    else:
                        cell.alignment = Alignment(horizontal="left")

            for ci, col_name in enumerate(col_names, start=1):
                try:
                    data_len = int(df_copy[col_name].astype(str).str.len().max())
                except Exception:
                    data_len = 0
                ws.column_dimensions[get_column_letter(ci)].width = min(
                    max(len(col_name), data_len) + 2, 32
                )
            ws.freeze_panes = "A2"

    print(f"  [OK] Excel Rolagem: {nome}")


def gerar_pdf_rolagem(rolagem_data: List[tuple], dt: str, out_dir: str) -> None:
    try:
        from fpdf import FPDF, XPos, YPos
    except ImportError:
        print("  [AVISO] fpdf2 não encontrado — execute: pip install fpdf2")
        return

    if not rolagem_data:
        return

    os.makedirs(out_dir, exist_ok=True)
    dt_fmt = pd.to_datetime(dt).strftime("%d/%m/%Y")

    def _hex(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    CD  = _hex(ITAU_DARK)
    CO  = _hex(ITAU_ORANGE)
    CW  = (255, 255, 255)
    CG2 = _hex(ITAU_GRAY2)
    CR  = _hex(ROW_PAR)
    CGR = _hex(ITAU_GREEN)
    CRD = _hex(ITAU_RED)

    class RolagemPDF(FPDF):
        def __init__(self, dt_fmt, logo_path):
            super().__init__(orientation="L", unit="mm", format="A4")
            self._dt_fmt = dt_fmt
            self._logo   = logo_path if os.path.exists(logo_path) else None
            self.set_margins(12, 22, 12)
            self.set_auto_page_break(auto=True, margin=12)

        def header(self):
            self.set_fill_color(*CD); self.rect(0, 0, self.w, 14, "F")
            self.set_fill_color(*CO); self.rect(0, 13.5, self.w, 1.5, "F")
            self.set_font("Helvetica", "B", 11)
            self.set_text_color(*CW)
            self.set_xy(12, 3.5); self.cell(120, 7, "RELATÓRIO DE ROLAGEM", align="L")
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*CG2)
            txt = f"Data Referência: {self._dt_fmt}"
            if self._logo:
                self.set_xy(self.w - 12 - 60, 3.5); self.cell(42, 7, txt, align="R")
                try: self.image(self._logo, x=self.w - 12 - 15, y=1, h=12)
                except Exception: pass
            else:
                self.set_xy(self.w - 12 - 60, 3.5); self.cell(60, 7, txt, align="R")
            self.set_text_color(0, 0, 0)
            self.set_xy(self.l_margin, self.t_margin)

        def footer(self):
            self.set_y(-10)
            self.set_draw_color(*CD); self.set_line_width(0.4)
            self.line(12, self.h - 10, self.w - 12, self.h - 10)
            self.set_font("Helvetica", "", 7)
            self.set_text_color(*CG2)
            self.cell(0, 5, f"Itau Asset Management  |  {self._dt_fmt}  |  pag. {self.page_no()}", align="C")
            self.set_text_color(0, 0, 0)

        def section_title(self, label, v1, v2):
            self.set_font("Helvetica", "B", 11)
            self.set_text_color(*CO)
            self.cell(0, 7, f"{label}  -  {v1} >> {v2}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_draw_color(*CO); self.set_line_width(0.5)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
            self.ln(3); self.set_text_color(0, 0, 0)

        def data_table(self, df, cols):
            usable   = self.w - self.l_margin - self.r_margin
            fundo_r  = 0.18
            pl_r     = 0.14
            other_r  = (1 - fundo_r - pl_r) / max(1, len(cols) - 2)
            widths   = [usable * (fundo_r if c == "FUNDO" else pl_r if c == "PL" else other_r)
                        for c in cols]
            widths[-1] += usable - sum(widths)

            xs, cx = [], self.l_margin
            for w in widths:
                xs.append(cx); cx += w

            ROW_H, HDR_H = 6.5, 7.0

            def _draw_header():
                y = self.get_y()
                self.set_font("Helvetica", "B", 7)
                self.set_draw_color(200, 200, 200); self.set_line_width(0.2)
                for i, (c, w, x) in enumerate(zip(cols, widths, xs)):
                    self.set_xy(x, y)
                    self.set_fill_color(*CD); self.set_text_color(*CW)
                    self.cell(w, HDR_H, c, border=1, align="L" if i == 0 else "C", fill=True)
                self.set_xy(self.l_margin, y + HDR_H)
                self.set_draw_color(*CO); self.set_line_width(0.6)
                self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
                self.set_line_width(0.2); self.set_draw_color(200, 200, 200)

            _draw_header()
            for ri, (_, row) in enumerate(df.sort_values("FUNDO").iterrows()):
                if self.get_y() + ROW_H > self.h - self.b_margin:
                    self.add_page(); _draw_header()
                bg = CR if ri % 2 == 1 else CW
                y  = self.get_y()
                for i, (c, w, x) in enumerate(zip(cols, widths, xs)):
                    val = row.get(c, "")
                    text = _fmt_money(val) if c == "PL" else (_fmt_pct(val) if "%" in c else _fmt_text(val))
                    self.set_xy(x, y); self.set_fill_color(*bg)
                    if "%" in c:
                        try:
                            v  = float(val)
                            tc = CGR if v > 0 else (CRD if v < 0 else (0, 0, 0))
                        except Exception:
                            tc = (0, 0, 0)
                        self.set_text_color(*tc); self.set_font("Helvetica", "B", 7)
                    else:
                        self.set_text_color(0, 0, 0); self.set_font("Helvetica", "", 7)
                    self.cell(w, ROW_H, text, border=1, align="L" if i == 0 else "C", fill=True)
                self.set_xy(self.l_margin, y + ROW_H)

    pdf = RolagemPDF(dt_fmt, LOGO_PATH)
    pdf.set_title(f"Relatório de Rolagem — {dt_fmt}")
    pdf.set_author("Itaú Asset Management")
    for label, df, v1, v2 in rolagem_data:
        pdf.add_page()
        pdf.start_section(f"{label} {v1}>>{v2}")
        pdf.section_title(label, v1, v2)
        pdf.data_table(df, df.columns.tolist())

    nome = os.path.join(out_dir, f"rolagem_{dt}.pdf")
    pdf.output(nome)
    print(f"  [OK] PDF Rolagem: {nome}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    n_dias = int(sys.argv[1]) if len(sys.argv) > 1 else 1 ######### else 1 sao qtd de dias para gerar o relatorio

    cal   = ql.Brazil()
    datas = [
        cal.advance(ql.Date.from_date(date.today()), ql.Period(f'-{i}d'))
           .to_date().strftime('%Y-%m-%d')
        for i in range(1, n_dias + 1)
    ]

    print(f"\n{'='*62}")
    print(f"  RELATÓRIO DE EXPOSIÇÃO  v18")
    print(f"  Dias      : {n_dias}  ({datas[0]} → {datas[-1]})")
    print(f"  Excel     : {INPUT_EXCEL}")
    print(f"{'='*62}\n")

    # ── carrega Excel e listas de fundos UMA vez ──────────────────────────────
    print("Lendo Excel...")
    abas = ler_exposicao_excel(INPUT_EXCEL)

    fundos_all: List[str] = []
    for _, df in abas.items():
        if df is not None and not df.empty and "FUNDO" in df.columns:
            fundos_all.extend(df["FUNDO"].dropna().astype(str).tolist())
    fundos_all = sorted(set(f.strip() for f in fundos_all if f.strip()))
    print(f"  Fundos únicos: {len(fundos_all)}")

    if not fundos_all:
        print("ERRO: Nenhum fundo encontrado no Excel.")
        return

    sp500_fundos: List[str] = []
    if "S&P500" in abas and abas["S&P500"] is not None and not abas["S&P500"].empty:
        sp500_fundos = abas["S&P500"]["FUNDO"].dropna().astype(str).tolist()

    fundos_rol = ler_fundos_rol()

    # ── loop por data ─────────────────────────────────────────────────────────
    for i, dt in enumerate(datas, 1):
        dt_fmt  = pd.to_datetime(dt).strftime('%d/%m/%Y')
        out_dir = os.path.join(OUTPUT_BASE, pd.to_datetime(dt).strftime("%Y%m%d"))

        print(f"\n{'='*62}")
        print(f"  [{i}/{n_dias}]  Data ref: {dt_fmt}  →  {out_dir}")
        print(f"{'='*62}")

        print("\nConsultando banco...")
        print("  FX...");        fx            = buscar_fx(dt)
        print("  PL...");        pl_map        = buscar_pl(dt, fundos_all)
        print("  PRV + FX...");  prv_map       = buscar_prv(dt, fundos_all, fx)
        print("  Futuros...");   fut_map       = buscar_futuro(dt, fundos_all)
        print("  Cotas...");     cotas_map     = buscar_cotas(dt, fundos_all)
        print("  Proventos..."); proventos_map = buscar_proventos(dt, fundos_all)
        print("  PIBB11/SPXI11...");
        pibb_spxi_map  = buscar_pibb11_spxi11(dt, sp500_fundos)
        print("  Futuros S&P/USD...");
        fut_sp_usd_map = buscar_fut_sp_usd(dt, sp500_fundos)
        print("  Rolagem...")
        rolagem_data   = buscar_rolagem(dt, fundos_rol) if fundos_rol else []

        sem_pl = [f for f in fundos_all if f not in pl_map]
        if sem_pl:
            print(f"\n  [AVISO] {len(sem_pl)} fundo(s) sem PL: "
                  f"{sem_pl[:5]}{'...' if len(sem_pl) > 5 else ''}")

        print(f"\nMontando tabelas...")
        abas_resultado: Dict[str, pd.DataFrame] = {}
        for aba, df_exp in abas.items():
            if df_exp is None or df_exp.empty:
                continue

            df_out = montar_tabela(
                df_exp, pl_map, prv_map, fut_map, cotas_map, proventos_map
            )

            # if aba == "S&P500":
            #     df_out = df_out.rename(columns={
            #         "%AÇÕES": "EXPOSIÇÃO S&P",
            #         "%FUT":   "EXPOSIÇÃO USD",
            #         "%COTAS": "PIBB + SPXI",
            #     })
            #     for col in ["EXPOSIÇÃO IBX", "FANG", "ISP"]:
            #         df_out[col] = 0.0

            #     for idx, row in df_out.iterrows():
            #         fundo  = str(row["FUNDO"])
            #         pl_val = row["PL"]
            #         if pd.isna(pl_val) or pl_val == 0:
            #             continue
            #         prv_val = _to_num(pd.Series([prv_map.get(fundo, 0)]))[0]
            #         pibb11  = pibb_spxi_map.get(fundo, {}).get("pibb11", 0.0)
            #         spxi11  = pibb_spxi_map.get(fundo, {}).get("spxi11", 0.0)
            #         sp_fut  = fut_sp_usd_map.get(fundo, {}).get("sp",  0.0)
            #         usd_fut = fut_sp_usd_map.get(fundo, {}).get("usd", 0.0)
            #         exp_sp  = (prv_val - pibb11 + sp_fut) / pl_val
            #         exp_usd = usd_fut / pl_val
            #         exp_ps  = (pibb11 + spxi11) / pl_val
            #         df_out.at[idx, "EXPOSIÇÃO S&P"] = exp_sp
            #         df_out.at[idx, "EXPOSIÇÃO USD"]  = exp_usd
            #         df_out.at[idx, "PIBB + SPXI"]    = exp_ps
                    
            #         # df_out.at[idx, "TOTAL"]           = exp_sp
            #         # df_out.at[idx, "DESC"]            = 1.0 - exp_sp
                    
            #         total_sp = exp_sp + exp_usd + exp_ps
            #         df_out.at[idx, "TOTAL"] = total_sp
            #         df_out.at[idx, "DESC"]  = 1.0 - total_sp


            # if aba == "S&P500":
            #     df_out = df_out.rename(columns={
            #         "%AÇÕES": "EXPOSIÇÃO S&P",
            #         "%FUT":   "EXPOSIÇÃO USD",
            #         "%COTAS": "PIBB + SPXI",
            #     })

            #     # inicializa colunas extras
            #     for col in ["EXPOSIÇÃO IBX", "FANG", "ISP"]:
            #         df_out[col] = 0.0

            #     for idx, row in df_out.iterrows():
            #         fundo  = str(row["FUNDO"])
            #         pl_val = row["PL"]

            #         if pd.isna(pl_val) or pl_val == 0:
            #             continue

            #         prv_val = prv_map.get(fundo, 0.0)

            #         pibb11  = pibb_spxi_map.get(fundo, {}).get("pibb11", 0.0)
            #         spxi11  = pibb_spxi_map.get(fundo, {}).get("spxi11", 0.0)

            #         sp_fut  = fut_sp_usd_map.get(fundo, {}).get("sp",  0.0)
            #         usd_fut = fut_sp_usd_map.get(fundo, {}).get("usd", 0.0)

            #         # EXPOSIÇÃO CORE (igual Excel)
            #         exp_sp = (prv_val - pibb11 + sp_fut) / pl_val

            #         # limpeza numérica
            #         if abs(exp_sp) < 1e-6:
            #             exp_sp = 0.0

            #         # COMPONENTES (informativos, não entram no TOTAL)
            #         exp_usd = usd_fut / pl_val
            #         exp_ps  = (pibb11 + spxi11) / pl_val

            #         # grava
            #         df_out.at[idx, "EXPOSIÇÃO S&P"] = exp_sp
            #         df_out.at[idx, "EXPOSIÇÃO USD"]  = exp_usd
            #         df_out.at[idx, "PIBB + SPXI"]    = exp_ps

            #         # TOTAL = SOMENTE S&P
            #         df_out.at[idx, "TOTAL"] = exp_sp
            #         df_out.at[idx, "DESC"]  = 1.0 - exp_sp

            #         # FANG (caso especial)
            #         if "FANG" in str(row.get("BENCH", "")).upper():
            #             fang = max(0.0, 1.0 - exp_sp)
            #             df_out.at[idx, "FANG"] = fang
            #         else:
            #             df_out.at[idx, "FANG"] = 0.0

            if aba == "S&P500":
                df_out = df_out.rename(columns={
                    "%AÇÕES": "EXPOSIÇÃO S&P",
                    "%FUT":   "EXPOSIÇÃO USD",
                    "%COTAS": "PIBB + SPXI",
                })

                for col in ["EXPOSIÇÃO IBX", "FANG", "ISP"]:
                    df_out[col] = 0.0

                for idx, row in df_out.iterrows():

                    fundo  = str(row["FUNDO"])
                    pl_val = row["PL"]

                    if pd.isna(pl_val) or pl_val == 0:
                        continue

                    # ===============================
                    # 1. COMPONENTES BRUTOS
                    # ===============================
                    prv_val = prv_map.get(fundo, 0.0)
                    sp_fut  = fut_sp_usd_map.get(fundo, {}).get("sp",  0.0)
                    usd_fut = fut_sp_usd_map.get(fundo, {}).get("usd", 0.0)
                    pibb11  = pibb_spxi_map.get(fundo, {}).get("pibb11", 0.0)
                    spxi11  = pibb_spxi_map.get(fundo, {}).get("spxi11", 0.0)

                    prv_pct = prv_val / pl_val
                    fut_sp  = sp_fut / pl_val
                    fut_usd = usd_fut / pl_val
                    etf_pct = (pibb11 + spxi11) / pl_val

                    # ===============================
                    # 2. INICIALIZA BUCKETS
                    # ===============================
                    bucket_sp   = 0.0
                    bucket_usd  = 0.0
                    bucket_isp  = 0.0
                    bucket_pibb = 0.0
                    bucket_ibx  = 0.0

                    # ===============================
                    # 3. CLASSIFICAÇÃO (ESSÊNCIA)
                    # ===============================

                    # ETF → PIBB
                    bucket_pibb = etf_pct

                    # FUT S&P → ISP
                    if abs(fut_sp) > 0:
                        bucket_isp = fut_sp

                    # FUT USD → USD
                    if abs(fut_usd) > 0:
                        bucket_usd = fut_usd

                    # PRV → S&P base
                    bucket_sp = prv_pct - (pibb11 / pl_val)

                    # ===============================
                    # 4. AJUSTES DO MODELO EXCEL
                    # ===============================

                    # S&P final inclui futuro SP
                    bucket_sp = bucket_sp + bucket_isp

                    # fundos que carregam USD estrutural
                    if fundo.startswith("SP500") or fundo.startswith("USDAFIM"):
                        bucket_usd = bucket_sp

                    # fundos hedgeados
                    if fundo.startswith("ITAUMMSP") or fundo.startswith("ITAUTRN"):
                        bucket_usd = 0.0

                    # IBX = ajuste pequeno residual
                    if fundo.startswith("SP500MM"):
                        bucket_ibx = 0.002
                    else:
                        bucket_ibx = 0.0

                    # FANG
                    if "FANG" in str(row.get("BENCH","")).upper():
                        bucket_sp = bucket_sp * 0.2506
                        bucket_fang = 0.75
                    else:
                        bucket_fang = 0.0

                    # ISP regra final (Excel só mostra quando relevante)
                    if abs(bucket_isp) < 0.01:
                        bucket_isp = 0.0

                    # ===============================
                    # 5. OUTPUT FINAL
                    # ===============================
                    exp_sp  = bucket_sp
                    exp_usd = bucket_usd
                    exp_ibx = bucket_ibx
                    exp_ps  = bucket_pibb
                    isp     = bucket_isp

                    df_out.at[idx, "EXPOSIÇÃO S&P"] = exp_sp
                    df_out.at[idx, "EXPOSIÇÃO USD"] = exp_usd
                    df_out.at[idx, "EXPOSIÇÃO IBX"] = exp_ibx
                    df_out.at[idx, "PIBB + SPXI"]   = exp_ps
                    df_out.at[idx, "FANG"]          = bucket_fang
                    df_out.at[idx, "ISP"]           = isp

                    df_out.at[idx, "TOTAL"] = exp_sp
                    df_out.at[idx, "DESC"]  = 1.0 - exp_sp



            if aba == "OFFSHORES":

                df_out["%AÇÕES"] = 0.0
                df_out["%FUT"]   = 0.0

                offshore_fundos = df_out["FUNDO"].astype(str).tolist()
                cotas_total_map = buscar_cotas_total(dt, offshore_fundos)
                for idx, row in df_out.iterrows():
                    fundo  = str(row["FUNDO"])
                    pl_val = row["PL"]
                    if pd.isna(pl_val) or pl_val == 0:
                        continue
                    cotas_vl = cotas_total_map.get(fundo, 0.0)
                    if cotas_vl > 0:
                        df_out.at[idx, "%COTAS"] = cotas_vl / pl_val
                df_out["TOTAL"] = (df_out["%AÇÕES"].fillna(0)
                                   + df_out["%FUT"].fillna(0)
                                   + df_out["%COTAS"].fillna(0))
                df_out["DESC"]  = 1.0 - df_out["TOTAL"]

            n_ok  = int((df_out["TOTAL"].notna() & (df_out["TOTAL"] > 0)).sum())
            n_nok = len(df_out) - n_ok
            print(f"  [{aba}] {len(df_out)} fundo(s) | {n_ok} OK"
                  + (f" | {n_nok} sem dados" if n_nok else ""))
            abas_resultado[aba] = df_out

        print(f"\nExportando Excel...")
        exportar_excel(abas_resultado, dt, out_dir)
        print(f"\nGerando HTML...")
        gerar_html(abas_resultado, dt, out_dir, rolagem_data=rolagem_data)
        print(f"\nGerando PDF...")
        gerar_pdf(abas_resultado, dt, out_dir)
        print(f"\nGerando Excel Rolagem...")
        exportar_excel_rolagem(rolagem_data, dt, out_dir)
        print(f"\nGerando PDF Rolagem...")
        gerar_pdf_rolagem(rolagem_data, dt, out_dir)

    # ── índice único ao final ─────────────────────────────────────────────────
    gerar_index(OUTPUT_BASE)

    print(f"\n{'='*62}")
    print(f"  Concluído — {n_dias} data(s) processada(s).")
    print(f"  Index: {os.path.join(OUTPUT_BASE, 'index.html')}")
    print(f"{'='*62}\n")


if __name__ == "__main__":
    main()