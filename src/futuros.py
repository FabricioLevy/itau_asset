
# ─────────────────────────────────────────────
# consulta_futuro.py
# ─────────────────────────────────────────────


from __future__ import annotations


import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.image as mpimg
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
import sql_connection as sql



OUTPUT_DIR   = "../output/rolagem"
INPUT_FUNDOS = "../input/fundos.txt"
LOGO_PATH    = "../input/logo.png"


# ── Cores Itaú Asset ──────────────────────────────────────────────────────────
ITAU_DARK   = "#000D3C"
ITAU_ORANGE = "#EC7000"
ITAU_WHITE  = "#ffffff"
ITAU_LIGHT  = "#f5f5f5"
ITAU_GRAY   = "#e0e0e0"
ITAU_GRAY2  = "#aaaaaa"
ITAU_RED    = "#c0392b"
ITAU_GREEN  = "#1e7e34"
ROW_PAR     = "#eaf0fb"


MES_CODIGO = {
    1:  "F",  2:  "G",  3:  "H",  4:  "J",
    5:  "K",  6:  "M",  7:  "N",  8:  "Q",
    9:  "U",  10: "V",  11: "X",  12: "Z",
}


GRUPO_DOL       = {"DOL", "WDO"}
GRUPO_DOL_LABEL = "FUT DOL + FUT WDO"



def formatar_vencimento(dt_vencto, ativo: str) -> str:
    try:
        dt     = pd.to_datetime(dt_vencto)
        codigo = MES_CODIGO[dt.month]
        ano    = str(dt.year)[-2:]
        return f"{codigo}{ano}"
    except Exception:
        return ""



def normalizar_ativo(ativo: str) -> str:
    return ativo.replace("FUT ", "").strip()



def eh_grupo_dol(ativo: str) -> bool:
    return normalizar_ativo(ativo) in GRUPO_DOL



def ler_fundos() -> list:
    if not os.path.exists(INPUT_FUNDOS):
        print(f"Aviso: {INPUT_FUNDOS} nao encontrado - sem filtro.")
        return []
    with open(INPUT_FUNDOS, "r", encoding="utf-8") as f:
        fundos = [l.strip() for l in f
                  if l.strip() and not l.strip().startswith("#")]
    print(f"  {len(fundos)} fundo(s) carregado(s) de {INPUT_FUNDOS}")
    return fundos



def consulta_futuro(dt: str, fundos: list):
    filtro = (f"AND clcli_cd IN ({', '.join([chr(39)+f+chr(39) for f in fundos])})"
              if fundos else "")
    query_fut = f"""
        SELECT clcli_cd, qt,
               qt * vl_varponto * vl_precomerc AS Notional,
               dt_vencto, fuvct_fuatv_cd,
               vl_precomerc * vl_varponto AS Cotacao
        FROM   dbsx337.dbo.view_vcrapfut WITH (NOLOCK)
        WHERE  dt = '{dt}' {filtro}
        ORDER  BY clcli_cd, fuvct_fuatv_cd, fuvct_cd
    """
    query_pl = f"""
        SELECT clcli_cd, vl_patrliqtot1 AS PL
        FROM   dbsx337.dbo.view_vcraplsi WITH (NOLOCK)
        WHERE  dt = '{dt}' {filtro}
    """
    db     = sql.get_connection()
    df_fut = db.run_query(query_fut)
    df_pl  = db.run_query(query_pl)
    return df_fut, df_pl



def processar_grupo(df_fut: pd.DataFrame, df_pl: pd.DataFrame,
                    dt: str, grupo: str) -> tuple:

    hoje       = pd.to_datetime(dt)
    inicio_mes = hoje.replace(day=1)

    df = df_fut[df_fut["dt_vencto"] >= inicio_mes].copy()

    if grupo == "DOL_WDO":
        df = df[df["fuvct_fuatv_cd"].apply(eh_grupo_dol)].copy()
        label_futuro = GRUPO_DOL_LABEL
    else:
        df = df[df["fuvct_fuatv_cd"].apply(normalizar_ativo) == grupo].copy()
        label_futuro = f"FUT {grupo}"

    df = df[(df["Notional"] != 0) & df["Notional"].notna()].copy()

    if df.empty:
        return pd.DataFrame(), [], label_futuro

    proximos = sorted(df["vencimento"].unique())[:2]
    if len(proximos) < 2:
        print(f"  [{grupo}] Menos de 2 vencimentos encontrados.")
        return pd.DataFrame(), [], label_futuro

    v1, v2 = proximos[0], proximos[1]
    print(f"  [{grupo}] Vencimentos: {v1} | {v2}")

    df_grp = (df.groupby(["clcli_cd", "vencimento"])["Notional"]
              .sum().reset_index())
    df_grp = df_grp[df_grp["Notional"] != 0].copy()

    tot_fundo = (df_grp.groupby("clcli_cd")["Notional"]
                 .sum().reset_index()
                 .rename(columns={"Notional": "total_fut"}))

    not_v1 = (df_grp[df_grp["vencimento"] == v1]
              .groupby("clcli_cd")["Notional"].sum()
              .reset_index().rename(columns={"Notional": f"not_{v1}"}))

    not_v2 = (df_grp[df_grp["vencimento"] == v2]
              .groupby("clcli_cd")["Notional"].sum()
              .reset_index().rename(columns={"Notional": f"not_{v2}"}))

    df_tab = (df_pl
              .merge(tot_fundo, on="clcli_cd", how="inner")
              .merge(not_v1,    on="clcli_cd", how="left")
              .merge(not_v2,    on="clcli_cd", how="left"))

    df_tab[f"not_{v1}"] = df_tab[f"not_{v1}"].fillna(0)
    df_tab[f"not_{v2}"] = df_tab[f"not_{v2}"].fillna(0)

    df_tab = df_tab[
        (df_tab[f"not_{v1}"] != 0) | (df_tab[f"not_{v2}"] != 0)
    ].copy()

    if df_tab.empty:
        return pd.DataFrame(), [], label_futuro

    df_tab["FUTURO"] = label_futuro

    df_tab[f"Posicao {v1} % PL"]      = df_tab[f"not_{v1}"] / df_tab["PL"]
    df_tab[f"Posicao {v2} % PL"]      = df_tab[f"not_{v2}"] / df_tab["PL"]
    df_tab[f"{v1} % do total de FUT"] = df_tab[f"not_{v1}"] / df_tab["total_fut"]
    df_tab[f"{v2} % do total de FUT"] = df_tab[f"not_{v2}"] / df_tab["total_fut"]

    df_out = df_tab[[
        "clcli_cd", "PL", "FUTURO",
        f"Posicao {v1} % PL",
        f"Posicao {v2} % PL",
        f"{v1} % do total de FUT",
        f"{v2} % do total de FUT",
    ]].rename(columns={"clcli_cd": "FUNDO"})

    return df_out, [v1, v2], label_futuro



def gerar_imagem(df: pd.DataFrame, grupo: str, label_futuro: str,
                 vencimentos: list, dt: str) -> None:

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if df.empty:
        print(f"  Nenhum dado para {label_futuro}")
        return

    v1, v2 = vencimentos[0], vencimentos[1]
    dt_fmt  = pd.to_datetime(dt).strftime("%d/%m/%Y")

    df_disp = df.copy()
    df_disp["PL"] = df_disp["PL"].apply(lambda x: f"R$ {x:,.2f}")
    for c in [c for c in df_disp.columns if "%" in c]:
        df_disp[c] = df_disp[c].apply(lambda x: f"{x:.2%}")

    colunas = [
        "FUNDO", "PL", "FUTURO",
        f"Posicao {v1} % PL",
        f"Posicao {v2} % PL",
        f"{v1} % do total de FUT",
        f"{v2} % do total de FUT",
    ]

    n_rows = len(df_disp)
    n_cols = len(colunas)

    fig_w  = max(20, n_cols * 2.8)
    fig_h  = 2.6 + n_rows * 0.60 + 0.7
    fig    = plt.figure(figsize=(fig_w, fig_h), facecolor=ITAU_WHITE)

    # GridSpec largura total — sem barra lateral
    gs = gridspec.GridSpec(
        4, 1,
        figure        = fig,
        height_ratios = [0.85, 1.3, n_rows * 0.60 + 0.4, 0.45],
        hspace        = 0,
        left=0.0, right=1.0,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # BARRA DO TOPO — azul, espessa, largura total; logo a direita alinhado
    # ─────────────────────────────────────────────────────────────────────────
    ax_b = fig.add_subplot(gs[0])
    ax_b.set_facecolor(ITAU_DARK)
    ax_b.axis("off")
    ax_b.set_xlim(0, 1)
    ax_b.set_ylim(0, 1)

    ax_b.text(0.018, 0.55,
              "Itau Asset Management",
              transform  = ax_b.transAxes,
              fontsize   = 12, fontweight="bold",
              color      = ITAU_WHITE,
              va="center", ha="left",
              fontfamily = "DejaVu Sans")

    # Logo a direita da barra azul, alinhado com a borda direita da tabela
    if os.path.exists(LOGO_PATH):
        try:
            logo_img = mpimg.imread(LOGO_PATH)
            ax_logo  = inset_axes(
                ax_b,
                width          = "9%",
                height         = "78%",
                loc            = "center right",
                bbox_to_anchor = (0.0, 0.0, 0.988, 1.0),
                bbox_transform = ax_b.transAxes,
                borderpad      = 0,
            )
            ax_logo.imshow(logo_img)
            ax_logo.axis("off")
        except Exception as e:
            print(f"  Logo nao carregado: {e}")

    # Linha laranja na base da barra azul
    ax_b.axhline(y=0.07, xmin=0.0, xmax=1.0,
                 color=ITAU_ORANGE, linewidth=3.0)

    # ─────────────────────────────────────────────────────────────────────────
    # FAIXA DE TITULO — fundo branco
    # ─────────────────────────────────────────────────────────────────────────
    ax_h = fig.add_subplot(gs[1])
    ax_h.set_facecolor(ITAU_WHITE)
    ax_h.axis("off")
    ax_h.set_xlim(0, 1)
    ax_h.set_ylim(0, 1)

    ax_h.text(0.018, 0.68,
              "RELATORIO DE ROLAGEM",
              transform  = ax_h.transAxes,
              fontsize   = 15, fontweight="bold",
              color      = ITAU_DARK,
              va="center", ha="left")

    ax_h.text(0.018, 0.30,
              label_futuro,
              transform = ax_h.transAxes,
              fontsize  = 11, color=ITAU_ORANGE,
              va="center", ha="left")

    ax_h.text(0.988, 0.68,
              f"Data Ref:  {dt_fmt}",
              transform = ax_h.transAxes,
              fontsize  = 9, color=ITAU_DARK,
              va="center", ha="right")

    ax_h.text(0.988, 0.30,
              f"Vencimentos:  {v1}  ->  {v2}",
              transform = ax_h.transAxes,
              fontsize  = 9, color=ITAU_GRAY2,
              va="center", ha="right")

    # Separador azul entre cabecalho e tabela
    ax_h.axhline(y=0.05, xmin=0.0, xmax=1.0,
                 color=ITAU_DARK, linewidth=2.5)

    # ─────────────────────────────────────────────────────────────────────────
    # TABELA
    # ─────────────────────────────────────────────────────────────────────────
    ax_t = fig.add_subplot(gs[2])
    ax_t.set_facecolor(ITAU_WHITE)
    ax_t.axis("off")

    col_widths = [0.17, 0.16, 0.17, 0.125, 0.125, 0.115, 0.115]

    tbl = ax_t.table(
        cellText  = df_disp[colunas].values,
        colLabels = colunas,
        cellLoc   = "center",
        loc       = "center",
        colWidths = col_widths,
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 2.2)

    for col_idx in range(n_cols):
        cell = tbl[0, col_idx]
        cell.set_facecolor(ITAU_DARK)
        cell.set_text_props(color=ITAU_WHITE, fontweight="bold", fontsize=8.5)
        cell.set_edgecolor(ITAU_WHITE)
        cell.set_linewidth(0.8)

    for row_idx in range(1, n_rows + 1):
        bg = ROW_PAR if row_idx % 2 == 0 else ITAU_WHITE
        for col_idx in range(n_cols):
            cell = tbl[row_idx, col_idx]
            cell.set_facecolor(bg)
            cell.set_edgecolor(ITAU_GRAY)
            cell.set_linewidth(0.5)

            if "% PL" in colunas[col_idx]:
                val_str = df_disp[colunas].values[row_idx - 1][col_idx]
                try:
                    val = float(val_str.replace("%", "").replace(",", "."))
                    if val < 0:
                        cell.set_facecolor("#fde8e8")
                        cell.set_text_props(color=ITAU_RED, fontweight="bold")
                    elif val > 0:
                        cell.set_facecolor("#e8f5e9")
                        cell.set_text_props(color=ITAU_GREEN, fontweight="bold")
                except Exception:
                    pass

    # ─────────────────────────────────────────────────────────────────────────
    # RODAPE
    # ─────────────────────────────────────────────────────────────────────────
    ax_f = fig.add_subplot(gs[3])
    ax_f.set_facecolor(ITAU_WHITE)
    ax_f.axis("off")
    ax_f.set_xlim(0, 1)
    ax_f.set_ylim(0, 1)

    ax_f.axhline(y=0.95, xmin=0.0, xmax=1.0,
                 color=ITAU_DARK, linewidth=1.5)

    ax_f.text(0.5, 0.38,
              "* Posicao % PL = Notional do vencimento / PL do fundo   |   "
              "% do total de FUT = Notional do vencimento / Notional total de futuros",
              transform = ax_f.transAxes,
              fontsize  = 7, color=ITAU_GRAY2,
              ha="center", va="center", style="italic")

    # ── Salva ─────────────────────────────────────────────────────────────────
    nome = f"{OUTPUT_DIR}/rolagem_{grupo}_{dt}.png"
    plt.savefig(nome, dpi=150, bbox_inches="tight",
                facecolor=ITAU_WHITE, edgecolor="none")
    plt.close()
    print(f"  [OK] Imagem salva: {nome}")



# ── Entry point ───────────────────────────────────────────────────────────────


if __name__ == "__main__":
    dt = "2026-05-27"

    fundos = ler_fundos()

    print("Conectando ao banco...")
    df_fut, df_pl = consulta_futuro(dt, fundos)

    df_fut["dt_vencto"]  = pd.to_datetime(df_fut["dt_vencto"])
    df_fut["vencimento"] = df_fut.apply(
        lambda r: formatar_vencimento(r["dt_vencto"], r["fuvct_fuatv_cd"]), axis=1
    )

    ativos_norm = df_fut["fuvct_fuatv_cd"].apply(normalizar_ativo).unique().tolist()
    grupos      = ["DOL_WDO"] + [a for a in ativos_norm if a not in GRUPO_DOL]
    grupos      = list(dict.fromkeys(grupos))

    print(f"\nGrupos: {grupos}\n")

    gerados = 0
    for grupo in grupos:
        df_result, vencimentos, label_futuro = processar_grupo(
            df_fut, df_pl, dt, grupo
        )
        if df_result.empty:
            print(f"  [SKIP] {grupo} - sem dados\n")
            continue
        gerar_imagem(df_result, grupo, label_futuro, vencimentos, dt)
        gerados += 1

    print(f"\nConcluido - {gerados} imagem(ns) gerada(s).")
