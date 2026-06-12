from __future__ import annotations


import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.image as mpimg
from mpl_toolkits.axes_grid1.inset_locator import inset_axes


import sql_connection as sql


INPUT_EXCEL = "../input/fundos_exposicao.xlsx"
LOGO_PATH   = "../input/logo.png"


ITAU_DARK   = "#000D3C"
ITAU_ORANGE = "#EC7000"
ITAU_WHITE  = "#ffffff"
ITAU_GRAY   = "#e0e0e0"
ITAU_GRAY2  = "#aaaaaa"
ROW_PAR     = "#eaf0fb"


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


def output_dir_for_date(dt: str) -> str:
    yyyymmdd = pd.to_datetime(dt).strftime("%Y%m%d")
    return os.path.join("..", "output", "exposicao", yyyymmdd)


def ler_exposicao_excel(path: str) -> dict[str, pd.DataFrame]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Arquivo nao encontrado: {path}")


    xls = pd.ExcelFile(path)
    out: dict[str, pd.DataFrame] = {}


    for sheet in SHEETS:
        if sheet not in xls.sheet_names:
            out[sheet] = pd.DataFrame(columns=["FUNDO", "BENCH", "MAX", "MIN"])
            continue


        df = pd.read_excel(path, sheet_name=sheet)
        cols_lower = {c: str(c).strip().lower() for c in df.columns}


        def find_col(*candidates: str):
            for cand in candidates:
                for orig, low in cols_lower.items():
                    if low == cand:
                        return orig
            return None


        c_fundo = find_col("fundos", "fundo", "fundo(s)", "nome")
        c_bench = find_col("bench", "benchmark", "indice", "índice")
        c_max   = find_col("maximo", "max", "máximo")
        c_min   = find_col("minimo", "min", "mínimo")


        df_out = pd.DataFrame()
        df_out["FUNDO"] = df[c_fundo] if c_fundo and c_fundo in df.columns else pd.Series(dtype="object")
        df_out["BENCH"] = df[c_bench] if c_bench and c_bench in df.columns else pd.Series(dtype="object")
        df_out["MAX"]   = df[c_max]   if c_max and c_max in df.columns     else pd.Series(dtype="float")
        df_out["MIN"]   = df[c_min]   if c_min and c_min in df.columns     else pd.Series(dtype="float")


        df_out["FUNDO"] = df_out["FUNDO"].astype(str).str.strip()
        df_out = df_out[df_out["FUNDO"].notna() & (df_out["FUNDO"] != "")].copy()


        df_out["BENCH"] = df_out["BENCH"].astype(str).str.strip()
        df_out.loc[df_out["BENCH"].isin(["nan", "None", ""]), "BENCH"] = ""


        out[sheet] = df_out.reset_index(drop=True)


    return out


def consulta_pl(dt: str, fundos: list[str]) -> pd.DataFrame:
    if not fundos:
        return pd.DataFrame(columns=["FUNDO", "PL"])


    filtro = f"AND clcli_cd IN ({', '.join([chr(39)+f+chr(39) for f in fundos])})"
    query_pl = f"""
        SELECT clcli_cd, vl_patrliqtot1 AS PL
        FROM   dbsx337.dbo.view_vcraplsi WITH (NOLOCK)
        WHERE  dt = '{dt}' {filtro}
    """
    db = sql.get_connection()
    df_pl = db.run_query(query_pl)
    if df_pl is None or len(df_pl) == 0:
        return pd.DataFrame(columns=["FUNDO", "PL"])
    df_pl = df_pl.rename(columns={"clcli_cd": "FUNDO"})
    return df_pl[["FUNDO", "PL"]].copy()


def consulta_fx(dt: str) -> dict[str, float]:
    """
    Busca as cotações equivalentes às que você tinha em BY:CI.
    Retorna dict com as chaves usadas no cálculo.
    Se não achar, retorna NaN.
    """
    db = sql.get_connection()


    # USD BRL (BMFXTWO no VBA -> fundos_dados_moedas BRL_B3_2 vs USD)
    q_usd = f"""
        SELECT TOP 1 preco_limpo AS v
        FROM dbsx337.dbo.fundos_dados_moedas WITH (NOLOCK)
        WHERE date = '{dt}'
          AND codigo_iam_moeda_base  = 'BRL_B3_2'
          AND codigo_iam_moeda_quote = 'USD'
    """


    # GBP BRL
    q_gbp = f"""
        SELECT TOP 1 preco_limpo AS v
        FROM dbsx337.dbo.fundos_dados_moedas WITH (NOLOCK)
        WHERE date = '{dt}'
          AND codigo_iam_moeda_base  = 'BRL_B3_2'
          AND codigo_iam_moeda_quote = 'GBP'
    """


    # EUR BRL
    q_eur = f"""
        SELECT TOP 1 preco_limpo AS v
        FROM dbsx337.dbo.fundos_dados_moedas WITH (NOLOCK)
        WHERE date = '{dt}'
          AND codigo_iam_moeda_base  = 'BRL_B3_2'
          AND codigo_iam_moeda_quote = 'EUR'
    """


    # CNYXBR10 (no VBA: FUNDOS_DADOS_INDICES / indice CNYXBR10)
    q_cny = f"""
        SELECT TOP 1 preco_limpo AS v
        FROM dbsx337.dbo.FUNDOS_DADOS_INDICES WITH (NOLOCK)
        WHERE date = '{dt}'
          AND codigo_iam_indice = 'CNYXBR10'
    """


    def scalar(q: str) -> float:
        try:
            d = db.run_query(q)
            if d is None or len(d) == 0:
                return float("nan")
            return float(d.iloc[0, 0])
        except Exception:
            return float("nan")


    fx = {
        "USD_BRL": scalar(q_usd),
        "GBP_BRL": scalar(q_gbp),
        "EUR_BRL": scalar(q_eur),
        "CNYXBR10": scalar(q_cny),
    }
    return fx


def consulta_prv_detalhado(dt: str, fundos: list[str]) -> pd.DataFrame:
    """
    Puxa PRV por fundo/ação e moeda_ativo, como no VBA.
    Retorna colunas: FUNDO, ACAO, QTD, PRECO, MOEDA_ATIVO, PRV_LOCAL
    """
    if not fundos:
        return pd.DataFrame(columns=["FUNDO", "ACAO", "QTD", "PRECO", "MOEDA_ATIVO", "PRV_LOCAL"])


    filtro = f"AND A.clcli_cd IN ({', '.join([chr(39)+f+chr(39) for f in fundos])})"


    q = f"""
        SELECT
            A.clcli_cd AS FUNDO,
            A.acao     AS ACAO,
            A.qt_total AS QTD,
            A.vl_preco_mercmedio AS PRECO,
            B.moeda_ativo AS MOEDA_ATIVO
        FROM DBSX337.dbo.VIEW_vcraprv AS A WITH (NOLOCK)
        LEFT JOIN DBSX337.dbo.VIEW_FUNDOS_POSICAO AS B WITH (NOLOCK)
               ON A.acao = B.ticker_bolsa
              AND A.DT   = B.date
              AND B.tipo = 'Equity'
        WHERE A.dt = '{dt}'
          {filtro}
    """


    db = sql.get_connection()
    df = db.run_query(q)
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=["FUNDO", "ACAO", "QTD", "PRECO", "MOEDA_ATIVO", "PRV_LOCAL"])


    # PRV em moeda local do ativo (ou BRL se já vier BRL)
    df["PRV_LOCAL"] = pd.to_numeric(df["QTD"], errors="coerce") * pd.to_numeric(df["PRECO"], errors="coerce")
    df["MOEDA_ATIVO"] = df["MOEDA_ATIVO"].astype(str).str.strip()
    df.loc[df["MOEDA_ATIVO"].isin(["nan", "None", ""]), "MOEDA_ATIVO"] = ""


    return df[["FUNDO", "ACAO", "QTD", "PRECO", "MOEDA_ATIVO", "PRV_LOCAL"]].copy()


def converter_prv_para_brl(df_prv: pd.DataFrame, fx: dict[str, float]) -> pd.DataFrame:
    """
    Aplica a regra do Excel:
      - USD ou IX: (IX -> *100) e * USD_BRL
      - GBP: * (GBP_BRL / 100)
      - CNY / CNY_10H: / CNYXBR10
      - senão: valor sem conversão
    Retorna df com coluna PRV_BRL.
    """
    df = df_prv.copy()


    usd = fx.get("USD_BRL", float("nan"))
    gbp = fx.get("GBP_BRL", float("nan"))
    cny = fx.get("CNYXBR10", float("nan"))


    moeda = df["MOEDA_ATIVO"].fillna("").astype(str).str.strip().str.upper()
    val = pd.to_numeric(df["PRV_LOCAL"], errors="coerce")


    prv_brl = pd.Series(np.nan, index=df.index, dtype="float64")


    # USD / IX
    mask_usd_ix = moeda.isin(["USD", "IX"])
    if not np.isnan(usd):
        adj = val.copy()
        adj.loc[moeda == "IX"] = adj.loc[moeda == "IX"] * 100.0
        prv_brl.loc[mask_usd_ix] = adj.loc[mask_usd_ix] * usd


    # GBP
    mask_gbp = moeda.eq("GBP")
    if not np.isnan(gbp):
        prv_brl.loc[mask_gbp] = val.loc[mask_gbp] * (gbp / 100.0)


    # CNY / CNY_10H
    mask_cny = moeda.isin(["CNY", "CNY_10H"])
    if not np.isnan(cny) and cny != 0:
        prv_brl.loc[mask_cny] = val.loc[mask_cny] / cny


    # Default: sem conversão (BRL ou já convertido)
    mask_default = ~(mask_usd_ix | mask_gbp | mask_cny)
    prv_brl.loc[mask_default] = val.loc[mask_default]


    df["PRV_BRL"] = prv_brl
    return df


def gerar_imagem_tabela(df: pd.DataFrame, aba: str, dt: str, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    if df is None or df.empty:
        print(f"  [{aba}] sem dados - pulando imagem.")
        return


    dt_fmt = pd.to_datetime(dt).strftime("%d/%m/%Y")
    df_disp = df.copy()


    def fmt_money(x):
        try:
            if pd.isna(x): return ""
            return f"R$ {float(x):,.2f}"
        except Exception:
            return ""


    def fmt_pct(x):
        try:
            if pd.isna(x): return ""
            return f"{float(x):.2%}"
        except Exception:
            return ""


    def fmt_text(x):
        try:
            if pd.isna(x): return ""
            s = str(x).strip()
            return "" if s.lower() in ("nan", "none") else s
        except Exception:
            return ""


    df_disp["PL"]        = df_disp["PL"].apply(fmt_money)
    df_disp["PRV (BRL)"] = df_disp["PRV (BRL)"].apply(fmt_money)
    df_disp["PRV % PL"]  = df_disp["PRV % PL"].apply(fmt_pct)
    df_disp["BENCH"]     = df_disp["BENCH"].apply(fmt_text)
    df_disp["MAX"]       = df_disp["MAX"].apply(fmt_pct)
    df_disp["MIN"]       = df_disp["MIN"].apply(fmt_pct)


    colunas = ["FUNDO", "PL", "BENCH", "PRV (BRL)", "PRV % PL", "MAX", "MIN"]
    n_rows = len(df_disp)
    n_cols = len(colunas)


    fig_w = max(18, n_cols * 2.4)
    fig_h = 2.6 + n_rows * 0.60 + 0.7
    fig = plt.figure(figsize=(fig_w, fig_h), facecolor=ITAU_WHITE)


    gs = gridspec.GridSpec(
        4, 1,
        figure=fig,
        height_ratios=[0.85, 1.3, n_rows * 0.60 + 0.4, 0.45],
        hspace=0,
        left=0.0, right=1.0,
    )


    ax_b = fig.add_subplot(gs[0])
    ax_b.set_facecolor(ITAU_DARK)
    ax_b.axis("off")
    ax_b.set_xlim(0, 1)
    ax_b.set_ylim(0, 1)


    ax_b.text(0.015, 0.50, "Itaú Asset Management",
              transform=ax_b.transAxes, fontsize=11, fontweight="bold",
              color=ITAU_GRAY2, va="center", ha="left")


    if os.path.exists(LOGO_PATH):
        try:
            logo_img = mpimg.imread(LOGO_PATH)
            ax_logo = inset_axes(
                ax_b, width="9%", height="75%",
                loc="center right",
                bbox_to_anchor=(0.0, -0.05, 1.0, 1.1),
                bbox_transform=ax_b.transAxes,
                borderpad=0,
            )
            ax_logo.imshow(logo_img)
            ax_logo.axis("off")
        except Exception as e:
            print(f"  Logo nao carregado: {e}")


    ax_b.axhline(y=0.02, xmin=0.0, xmax=1.0, color=ITAU_ORANGE, linewidth=2.0)


    ax_h = fig.add_subplot(gs[1])
    ax_h.set_facecolor(ITAU_WHITE)
    ax_h.axis("off")
    ax_h.set_xlim(0, 1)
    ax_h.set_ylim(0, 1)


    ax_h.text(0.018, 0.68, "RELATÓRIO DE EXPOSIÇÃO",
              transform=ax_h.transAxes, fontsize=15, fontweight="bold",
              color=ITAU_DARK, va="center", ha="left")
    ax_h.text(0.018, 0.30, f"Aba: {aba}",
              transform=ax_h.transAxes, fontsize=11, color=ITAU_ORANGE,
              va="center", ha="left")
    ax_h.text(0.988, 0.68, f"Data Ref:  {dt_fmt}",
              transform=ax_h.transAxes, fontsize=9, color=ITAU_DARK,
              va="center", ha="right")
    ax_h.axhline(y=0.04, xmin=0.0, xmax=1.0, color=ITAU_GRAY, linewidth=1.0)


    ax_t = fig.add_subplot(gs[2])
    ax_t.set_facecolor(ITAU_WHITE)
    ax_t.axis("off")


    col_widths = [0.18, 0.16, 0.16, 0.16, 0.10, 0.12, 0.12]
    tbl = ax_t.table(
        cellText=df_disp[colunas].values,
        colLabels=colunas,
        cellLoc="center",
        loc="center",
        colWidths=col_widths,
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 2.2)


    for col_idx in range(n_cols):
        cell = tbl[0, col_idx]
        cell.set_facecolor(ITAU_DARK)
        cell.set_text_props(color=ITAU_WHITE, fontweight="bold", fontsize=9)
        cell.set_edgecolor(ITAU_WHITE)
        cell.set_linewidth(0.8)


    for row_idx in range(1, n_rows + 1):
        bg = ROW_PAR if row_idx % 2 == 0 else ITAU_WHITE
        for col_idx in range(n_cols):
            cell = tbl[row_idx, col_idx]
            cell.set_facecolor(bg)
            cell.set_edgecolor(ITAU_GRAY)
            cell.set_linewidth(0.5)


    ax_f = fig.add_subplot(gs[3])
    ax_f.set_facecolor(ITAU_WHITE)
    ax_f.axis("off")
    ax_f.set_xlim(0, 1)
    ax_f.set_ylim(0, 1)
    ax_f.axhline(y=0.95, xmin=0.0, xmax=1.0, color=ITAU_DARK, linewidth=1.5)
    ax_f.text(
        0.5, 0.38,
        "* PRV (BRL) convertido por moeda | PRV % PL = PRV(BRL)/PL",
        transform=ax_f.transAxes,
        fontsize=7, color=ITAU_GRAY2,
        ha="center", va="center", style="italic"
    )


    nome = os.path.join(out_dir, f"exposicao_{aba}_{dt}.png")
    plt.savefig(nome, dpi=150, bbox_inches="tight", facecolor=ITAU_WHITE, edgecolor="none")
    plt.close()
    print(f"  [OK] Imagem salva: {nome}")



if __name__ == "__main__":
    dt = "2026-05-27"
    out_dir = output_dir_for_date(dt)


    print(f"Saida em: {out_dir}")
    print(f"Lendo exposicao de: {INPUT_EXCEL}")
    abas = ler_exposicao_excel(INPUT_EXCEL)


    fundos_all: list[str] = []
    for _, df in abas.items():
        if df is not None and not df.empty and "FUNDO" in df.columns:
            fundos_all.extend(df["FUNDO"].dropna().astype(str).tolist())
    fundos_all = sorted(set([f.strip() for f in fundos_all if f and f.strip()]))
    print(f"Total de fundos unicos no Excel: {len(fundos_all)}")


    print("Consultando PL...")
    df_pl = consulta_pl(dt, fundos_all)
    pl_map = dict(zip(df_pl["FUNDO"].astype(str), df_pl["PL"])) if df_pl is not None and not df_pl.empty else {}


    print("Consultando FX...")
    fx = consulta_fx(dt)
    print(f"FX: {fx}")


    print("Consultando PRV detalhado...")
    df_prv_det = consulta_prv_detalhado(dt, fundos_all)
    df_prv_conv = converter_prv_para_brl(df_prv_det, fx)


    # Agrega PRV_BRL por fundo
    df_prv_fundo = (df_prv_conv.groupby("FUNDO", as_index=False)["PRV_BRL"]
                    .sum()
                    .rename(columns={"PRV_BRL": "PRV (BRL)"}))


    prv_map = dict(zip(df_prv_fundo["FUNDO"].astype(str), df_prv_fundo["PRV (BRL)"])) if not df_prv_fundo.empty else {}


    gerados = 0
    for aba, df_exp in abas.items():
        if df_exp is None or df_exp.empty:
            print(f"[{aba}] vazio.")
            continue


        df_out = df_exp.copy()
        df_out["PL"] = df_out["FUNDO"].map(pl_map)
        df_out["PRV (BRL)"] = df_out["FUNDO"].map(prv_map)


        # PRV % PL (se PL ou PRV forem NaN/0, fica em branco)
        df_out["PRV % PL"] = np.nan
        mask = df_out["PL"].notna() & (df_out["PL"] != 0) & df_out["PRV (BRL)"].notna()
        df_out.loc[mask, "PRV % PL"] = df_out.loc[mask, "PRV (BRL)"] / df_out.loc[mask, "PL"]


        for c in ["BENCH", "MAX", "MIN"]:
            if c not in df_out.columns:
                df_out[c] = np.nan


        df_out = df_out[["FUNDO", "PL", "BENCH", "PRV (BRL)", "PRV % PL", "MAX", "MIN"]].copy()


        gerar_imagem_tabela(df_out, aba, dt, out_dir)
        gerados += 1


    print(f"\nConcluido - {gerados} imagem(ns) gerada(s).")




