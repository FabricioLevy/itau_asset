"""
Performance Attribution — Fundos Indexados
Fonte: [DBSX337].[dbo].[VW_FUNDOS_PERFORMANCE_ATTRIBUTION]
"""


import sys
import json
import base64
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker


sys.path.insert(0, r"c:\Users\FLBLIPO\Videos\fabricio_levy\exposicao\src")
from sql_connection import query


INPUT_DIR  = Path(__file__).parent.parent / "input"
OUTPUT_DIR = Path(__file__).parent.parent / "output" / "performance"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# CONFIGURAÇÃO
# ---------------------------------------------------------------------------


DATA_FIM    = "2026-06-11"
_ytd_start  = f"{DATA_FIM[:4]}-01-01"
_win_start  = (datetime.strptime(DATA_FIM, "%Y-%m-%d") - timedelta(days=400)).strftime("%Y-%m-%d")
DATA_INICIO = min(_ytd_start, _win_start)   # cobre YTD + 60D + 21D + 1D


SALVAR_PNG  = 0   # 1 = gera gráficos PNG por fundo  |  0 = pula (apenas HTML)


def _ler_fundos_excel() -> Optional[list]:
    """Lê todos os fundos de ../input/fundos_exposicao.xlsx (coluna 'fundos' de todas as abas)."""
    path = INPUT_DIR / "fundos_exposicao.xlsx"
    if not path.exists():
        print(f"  [AVISO] {path} não encontrado — carregando todos os fundos.")
        return None
    xl     = pd.ExcelFile(str(path))
    fundos = []
    for sheet in xl.sheet_names:
        df  = pd.read_excel(xl, sheet_name=sheet)
        col = next((c for c in df.columns if str(c).strip().lower() == "fundos"), None)
        if col:
            fundos += [str(v).strip() for v in df[col].dropna() if str(v).strip()]
    fundos = list(dict.fromkeys(fundos))   # remove duplicatas mantendo ordem
    print(f"  {len(fundos)} fundo(s) lidos de {path.name}")
    return fundos or None


FUNDOS_FILTRO = _ler_fundos_excel()


def _logo_base64() -> str:
    path = INPUT_DIR / "logo.png"
    if not path.exists():
        return ""
    return base64.b64encode(path.read_bytes()).decode("utf-8")



def _ler_classificacao() -> dict:
    """
    Lê ../input/fundos_exposicao.xlsx.
    Retorna {fundo: classificacao} onde classificacao = nome da aba.
    """
    path = INPUT_DIR / "fundos_exposicao.xlsx"
    if not path.exists():
        return {}
    xl  = pd.ExcelFile(str(path))
    out = {}
    for sheet in xl.sheet_names:
        df = pd.read_excel(xl, sheet_name=sheet)
        col = next((c for c in df.columns if str(c).strip().lower() == "fundos"), None)
        if col is None:
            continue
        for v in df[col].dropna():
            out[str(v).strip()] = sheet
    print(f"  Classificação carregada: {len(out)} fundos em {len(xl.sheet_names)} categorias")
    return out


CLASSIFICACAO = _ler_classificacao()



def _fundos_por_grupo(fundos: list) -> "dict[str, list]":
    """Agrupa uma lista de fundos pela classificação do Excel. Sem classificação → 'Outros'."""
    grupos: dict = {}
    for f in fundos:
        grp = CLASSIFICACAO.get(f, "Outros")
        grupos.setdefault(grp, []).append(f)
    return grupos



# ---------------------------------------------------------------------------
# 1. QUERY
# ---------------------------------------------------------------------------


def build_query(data_inicio: str, data_fim: str, fundos: Optional[list]) -> str:
    filtro_fundo = ""
    if fundos:
        lista = ", ".join(f"'{f}'" for f in fundos)
        filtro_fundo = f"AND codigo_IAM_fundo IN ({lista})"


    return f"""
        SELECT
            [date],
            [codigo_IAM_fundo]                  AS fundo,
            [ativo],
            [ticker_bolsa],
            [tipo],
            [gics_sector_name]                  AS setor,
            [setor_iam],
            [subsetor_iam],
            [perc_pl],
            [pnl_total],
            [pnl_total_perc],
            [benchmark_ativos_pnl_total],
            [benchmark_ativos_pnl_total_perc],
            [benchmark_pnl_total],
            [benchmark_pnl_total_perc]
        FROM [DBSX337].[dbo].[VW_FUNDOS_PERFORMANCE_ATTRIBUTION]
        WHERE [date] BETWEEN '{data_inicio}' AND '{data_fim}'
          AND [tipo_pnl] IS NOT NULL
          AND [pnl_total] <> 0
          {filtro_fundo}
    """



def load_data() -> pd.DataFrame:
    sql = build_query(DATA_INICIO, DATA_FIM, FUNDOS_FILTRO)
    df  = query(sql)
    if df.empty:
        raise ValueError("Query não retornou dados. Verifique os filtros de data/fundo.")


    num_cols = [
        "perc_pl", "pnl_total", "pnl_total_perc",
        "benchmark_ativos_pnl_total", "benchmark_ativos_pnl_total_perc",
        "benchmark_pnl_total", "benchmark_pnl_total_perc",
    ]
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)


    df["contribuicao_pp"] = df["pnl_total_perc"]


    for col in ["ativo", "ticker_bolsa", "tipo", "setor_iam", "subsetor_iam"]:
        df[col] = df[col].fillna("N/A")


    return df



# ---------------------------------------------------------------------------
# 2. AGREGAÇÕES
# ---------------------------------------------------------------------------


def _agg(df: pd.DataFrame, group_cols: list) -> pd.DataFrame:
    """Agregação genérica: soma contribuição e benchmark por grupo."""
    grp = (
        df.groupby(group_cols, dropna=False)
        .agg(
            contribuicao_pp                 = ("contribuicao_pp",                 "sum"),
            pnl_total                       = ("pnl_total",                       "sum"),
            benchmark_ativos_pnl_total      = ("benchmark_ativos_pnl_total",      "sum"),
            benchmark_ativos_pnl_total_perc = ("benchmark_ativos_pnl_total_perc", "sum"),
        )
        .reset_index()
    )
    grp["alpha"] = grp["contribuicao_pp"] - grp["benchmark_ativos_pnl_total_perc"]
    return grp



def summary_by_fund(df: pd.DataFrame) -> pd.DataFrame:
    grp = df.groupby("fundo").agg(
        rentabilidade_pp    = ("contribuicao_pp",                 "sum"),
        benchmark_ativos_pp = ("benchmark_ativos_pnl_total_perc", "sum"),
        benchmark_fundo_pp  = ("benchmark_pnl_total_perc",        "mean"),
    ).reset_index()
    grp["alpha_vs_bm_fundo"]  = grp["rentabilidade_pp"] - grp["benchmark_fundo_pp"]
    grp["alpha_vs_bm_ativos"] = grp["rentabilidade_pp"] - grp["benchmark_ativos_pp"]
    return grp.sort_values("rentabilidade_pp", ascending=False)



def attribution_by_tipo(df: pd.DataFrame) -> pd.DataFrame:
    return _agg(df, ["fundo", "tipo"]).sort_values(
        ["fundo", "contribuicao_pp"], ascending=[True, False]
    )



def attribution_by_ticker(df: pd.DataFrame) -> pd.DataFrame:
    return _agg(df, ["fundo", "ticker_bolsa", "tipo"]).sort_values(
        ["fundo", "contribuicao_pp"], ascending=[True, False]
    )



def attribution_by_ativo(df: pd.DataFrame) -> pd.DataFrame:
    return _agg(df, ["fundo", "ativo", "tipo"]).sort_values(
        ["fundo", "contribuicao_pp"], ascending=[True, False]
    )




# ---------------------------------------------------------------------------
# 2b. PRE-COMPUTO DE JANELAS
# ---------------------------------------------------------------------------


def compute_windows(df_raw: pd.DataFrame, data_fim: str) -> dict:
    """Agrega fund/tipo/ticker/ativo/day para cada janela de retorno."""
    df = df_raw.copy()
    df["_date"] = df["date"].astype(str).str[:10]
    all_dates   = sorted(df["_date"].unique())
    year        = data_fim[:4]

    ytd_dates = [d for d in all_dates if d >= f"{year}-01-01"]
    defs: dict = {
        "1D":  all_dates[-1:],
        "21D": all_dates[-21:],
        "60D": all_dates[-60:],
        "YTD": ytd_dates,
    }

    result: dict = {}
    for label, dates in defs.items():
        if not dates:
            continue
        mask = df["_date"].isin(set(dates))
        sub  = df[mask].drop(columns=["_date"])

        def _rec(frame):
            return frame.fillna(0).to_dict(orient="records")

        result[label] = {
            "dates":  [dates[0], dates[-1]],
            "fund":   _rec(summary_by_fund(sub)),
            "tipo":   _rec(attribution_by_tipo(sub)),
            "ticker": _rec(attribution_by_ticker(sub)),
            "ativo":  _rec(attribution_by_ativo(sub)),
            "day":    _rec(attribution_by_day(sub)),
        }
    return result


def attribution_by_day(df: pd.DataFrame) -> pd.DataFrame:
    """Retorno diário do fundo — soma de todas as contribuições no dia."""
    grp = (
        df.groupby(["fundo", "date"], dropna=False)
        .agg(
            contribuicao_pp                 = ("contribuicao_pp",                 "sum"),
            benchmark_ativos_pnl_total_perc = ("benchmark_ativos_pnl_total_perc", "sum"),
            benchmark_pnl_total_perc        = ("benchmark_pnl_total_perc",        "mean"),
        )
        .reset_index()
    )
    grp["date"]  = grp["date"].astype(str).str[:10]
    grp["alpha"] = grp["contribuicao_pp"] - grp["benchmark_ativos_pnl_total_perc"]
    grp["benchmark_ativos_pnl_total"] = 0.0  # não usado no dia
    grp["pnl_total"] = 0.0
    return grp.sort_values(["fundo", "date"])



# ---------------------------------------------------------------------------
# 3. RELATÓRIO NO TERMINAL
# ---------------------------------------------------------------------------


def fmt(val: float, decimals: int = 6) -> str:
    sinal = "+" if val > 0 else ""
    return f"{sinal}{val:.{decimals}f}"



def _print_table(df_view: pd.DataFrame, fundo: str, label_col: str, title: str) -> None:
    subset = df_view[df_view["fundo"] == fundo].sort_values("contribuicao_pp", ascending=False)
    print(f"\n  [{title}]")
    print(f"  {'─'*70}")
    print(f"  {label_col.upper():<25} {'Contrib.':>14} {'BM Ativo':>14} {'Alpha':>12}")
    print(f"  {'─'*65}")
    for _, row in subset.iterrows():
        print(
            f"  {str(row[label_col])[:25]:<25} "
            f"{fmt(row['contribuicao_pp'], 6):>14} "
            f"{fmt(row['benchmark_ativos_pnl_total_perc'], 6):>14} "
            f"{fmt(row['alpha'], 6):>12}"
        )


    top_pos = subset.head(3)
    top_neg = subset.tail(3).iloc[::-1]
    print(f"\n  Top 3 GANHOS:")
    for _, r in top_pos.iterrows():
        print(f"    {str(r[label_col]):<25} {fmt(r['contribuicao_pp'], 6):>14}")
    print(f"  Top 3 PERDAS:")
    for _, r in top_neg.iterrows():
        print(f"    {str(r[label_col]):<25} {fmt(r['contribuicao_pp'], 6):>14}")



def print_report(
    df_fund: pd.DataFrame,
    df_tipo: pd.DataFrame,
    df_ticker: pd.DataFrame,
    df_ativo: pd.DataFrame,
) -> None:
    print("\n" + "=" * 75)
    print("  PERFORMANCE ATTRIBUTION — FUNDOS INDEXADOS")
    print(f"  Período: {DATA_INICIO}  →  {DATA_FIM}")
    print("=" * 75)


    for _, frow in df_fund.iterrows():
        fundo = frow["fundo"]
        print(f"\n{'═'*75}")
        print(f"  FUNDO: {fundo}")
        print(f"  Rentabilidade        : {fmt(frow['rentabilidade_pp'], 6)}")
        print(f"  BM Ativos            : {fmt(frow['benchmark_ativos_pp'], 6)}"
              f"   Alpha: {fmt(frow['alpha_vs_bm_ativos'], 6)}")
        print(f"  BM Fundo             : {fmt(frow['benchmark_fundo_pp'], 6)}"
              f"   Alpha: {fmt(frow['alpha_vs_bm_fundo'], 6)}")


        _print_table(df_tipo,   fundo, "tipo",         "POR TIPO")
        _print_table(df_ticker, fundo, "ticker_bolsa", "POR TICKER")
        _print_table(df_ativo,  fundo, "ativo",        "POR ATIVO")


    print("\n" + "=" * 75)



# ---------------------------------------------------------------------------
# 4. GRÁFICOS
# ---------------------------------------------------------------------------


def _plot_bars(
    df_view: pd.DataFrame,
    df_fund: pd.DataFrame,
    label_col: str,
    titulo: str,
    filename_prefix: str,
    max_items: int = 30,
    out_dir: Path = OUTPUT_DIR,
) -> None:
    """Um PNG por fundo — evita imagens de largura ilimitada."""
    for fundo in df_fund["fundo"].tolist():
        subset = (
            df_view[df_view["fundo"] == fundo]
            .sort_values("contribuicao_pp")
            .tail(max_items)
        )
        if subset.empty:
            continue


        total   = df_fund.loc[df_fund["fundo"] == fundo, "rentabilidade_pp"].values[0]
        bm_fund = df_fund.loc[df_fund["fundo"] == fundo, "benchmark_fundo_pp"].values[0]


        labels  = [str(v)[:25] for v in subset[label_col].values]
        contrib = subset["contribuicao_pp"].values
        bm_atv  = subset["benchmark_ativos_pnl_total_perc"].values
        y       = list(range(len(labels)))


        fig, ax = plt.subplots(figsize=(10, max(5, len(labels) * 0.35)),
                               constrained_layout=True)


        ax.barh(y, contrib,
                color=["#2ecc71" if v >= 0 else "#e74c3c" for v in contrib],
                edgecolor="white", linewidth=0.4, label="Contribuição")
        ax.scatter(bm_atv, y, color="#2c3e50", zorder=5, s=25, label="BM Ativo")
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=8)
        ax.axvline(0, color="black", linewidth=0.8)
        ax.legend(fontsize=8, loc="lower right")
        ax.set_title(
            f"{fundo} — {titulo}\n"
            f"Rent: {'+' if total >= 0 else ''}{total:.6f}"
            f"  |  BM Fundo: {'+' if bm_fund >= 0 else ''}{bm_fund:.6f}",
            fontsize=9.5, fontweight="bold",
        )
        ax.set_xlabel("Contribuição")
        ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.5f"))
        ax.tick_params(axis="y", labelsize=8)


        slug = fundo.replace(" ", "_").replace("/", "_")
        path = out_dir / f"{filename_prefix}_{slug}.png"
        plt.savefig(path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        print(f"  Gráfico salvo: {path}")



def plot_all(
    df_fund: pd.DataFrame,
    df_tipo: pd.DataFrame,
    df_ticker: pd.DataFrame,
    df_ativo: pd.DataFrame,
    out_dir: Path = OUTPUT_DIR,
) -> None:
    _plot_bars(df_tipo,   df_fund, "tipo",         "Por Tipo",   "perf_tipo",   max_items=15,  out_dir=out_dir)
    _plot_bars(df_ticker, df_fund, "ticker_bolsa", "Por Ticker", "perf_ticker", max_items=35,  out_dir=out_dir)
    _plot_bars(df_ativo,  df_fund, "ativo",        "Por Ativo",  "perf_ativo",  max_items=35,  out_dir=out_dir)



# ---------------------------------------------------------------------------
# 5. EXPORTAR
# ---------------------------------------------------------------------------


def export_results(
    df_fund: pd.DataFrame,
    df_tipo: pd.DataFrame,
    df_ticker: pd.DataFrame,
    df_ativo: pd.DataFrame,
) -> None:
    exports = [
        (df_fund,   "attribution_por_fundo.csv"),
        (df_tipo,   "attribution_por_tipo.csv"),
        (df_ticker, "attribution_por_ticker.csv"),
        (df_ativo,  "attribution_por_ativo.csv"),
    ]
    for df, nome in exports:
        path = OUTPUT_DIR / nome
        df.to_csv(path, index=False, sep=";", decimal=",")
        print(f"  Exportado: {path}")



# ---------------------------------------------------------------------------
# 6. HTML (waterfall Chart.js + estilo exposição)
# ---------------------------------------------------------------------------


def _waterfall_chartjs_data(
    df_view: pd.DataFrame,
    fundo: str,
    label_col: str,
    sort_col: Optional[str] = None,   # None = ordena por contribuicao_pp desc
    sort_asc: bool = True,
):
    """
    Retorna (labels, bases, values, colors) para o waterfall via Chart.js floating bars.
    Cada barra = [base, base+contribution]. Barra final = total (azul).
    sort_col: coluna a usar para ordenação (ex: "date" para ordem cronológica).
    """
    if sort_col:
        subset = (
            df_view[df_view["fundo"] == fundo]
            .sort_values(sort_col, ascending=sort_asc)
            .reset_index(drop=True)
        )
    else:
        subset = (
            df_view[df_view["fundo"] == fundo]
            .sort_values("contribuicao_pp", ascending=False)
            .reset_index(drop=True)
        )


    labels, bases, values, colors = [], [], [], []
    running = 0.0
    for _, row in subset.iterrows():
        v = float(row["contribuicao_pp"])
        labels.append(str(row[label_col]))
        bases.append(round(running, 10))
        values.append(round(v, 10))
        colors.append("#2ecc71" if v >= 0 else "#e74c3c")
        running += v


    labels.append("TOTAL")
    bases.append(0.0)
    values.append(round(running, 10))
    colors.append("#000D3C")


    return labels, bases, values, colors



def _kpi_cards_html(frow: pd.Series) -> str:
    def card(titulo, valor, cor):
        sinal = "+" if valor > 0 else ""
        return (
            f'<div class="kpi-card">'
            f'<div class="kpi-label">{titulo}</div>'
            f'<div class="kpi-value" style="color:{cor}">{sinal}{valor:.6f}</div>'
            f'</div>'
        )


    rent   = frow["rentabilidade_pp"]
    bm_f   = frow["benchmark_fundo_pp"]
    bm_a   = frow["benchmark_ativos_pp"]
    alp_f  = frow["alpha_vs_bm_fundo"]
    alp_a  = frow["alpha_vs_bm_ativos"]


    def cor(v):  return "#1e7e34" if v > 0 else ("#c0392b" if v < 0 else "#555")


    return (
        '<div class="kpi-row">'
        + card("Rentabilidade", rent, cor(rent))
        + card("BM Fundo",      bm_f,  cor(bm_f))
        + card("Alpha vs BM Fundo", alp_f, cor(alp_f))
        + card("BM Ativos",    bm_a,  cor(bm_a))
        + card("Alpha vs BM Ativos", alp_a, cor(alp_a))
        + '</div>'
    )



def _waterfall_section_html(
    df_view: pd.DataFrame,
    df_fund: pd.DataFrame,
    fundo: str,
    label_col: str,
    chart_id: str,
) -> str:
    frow = df_fund[df_fund["fundo"] == fundo].iloc[0]
    labels, bases, values, colors = _waterfall_chartjs_data(df_view, fundo, label_col, sort_col=None)


    # tabela de dados
    subset = (
        df_view[df_view["fundo"] == fundo]
        .sort_values("contribuicao_pp", ascending=False)
        .reset_index(drop=True)
    )
    rows_html = ""
    for _, row in subset.iterrows():
        contrib = float(row["contribuicao_pp"])
        bm      = float(row["benchmark_ativos_pnl_total_perc"])
        alpha   = float(row["alpha"])
        sinal_c = "+" if contrib > 0 else ""
        sinal_b = "+" if bm > 0 else ""
        sinal_a = "+" if alpha > 0 else ""
        cor_c   = "tot-green" if contrib > 0 else ("tot-red" if contrib < 0 else "")
        cor_a   = "tot-green" if alpha  > 0 else ("tot-red" if alpha  < 0 else "")
        rows_html += (
            f'<tr>'
            f'<td>{row[label_col]}</td>'
            f'<td class="{cor_c} bold">{sinal_c}{contrib:.6f}</td>'
            f'<td>{sinal_b}{bm:.6f}</td>'
            f'<td class="{cor_a} bold">{sinal_a}{alpha:.6f}</td>'
            f'</tr>'
        )


    # Chart.js JSON
    chart_labels = json.dumps(labels)
    chart_bases  = json.dumps(bases)
    chart_values = json.dumps(values)
    chart_colors = json.dumps(colors)


    bar_height = 420


    return f"""
<div class="kpi-section" id="kpi_{{chart_id}}">{_kpi_cards_html(frow)}</div>


<div class="chart-wrap">
  <canvas id="{chart_id}" style="height:{bar_height}px;"></canvas>
</div>
<script>
(function(){{
  var labels  = {chart_labels};
  var bases   = {chart_bases};
  var vals    = {chart_values};
  var colors  = {chart_colors};
  var floats  = vals.map(function(v,i){{ return [bases[i], bases[i]+v]; }});
  window.__CHARTS__ = window.__CHARTS__ || {{}};
  window.__CHARTS__['{chart_id}'] = new Chart(document.getElementById('{chart_id}'), {{
    type: 'bar',
    data: {{
      labels: labels,
      datasets: [{{
        label: 'Contribuição',
        data: floats,
        backgroundColor: colors,
        borderColor: colors,
        borderWidth: 1,
        borderRadius: 3,
      }}]
    }},
    options: {{
      indexAxis: 'x',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          callbacks: {{
            label: function(ctx) {{
              var v = vals[ctx.dataIndex];
              return (v >= 0 ? '+' : '') + v.toFixed(6);
            }}
          }}
        }}
      }},
      scales: {{
        y: {{
          grid: {{ color: '#e0e0e0' }},
          ticks: {{ callback: function(v){{ return v.toFixed(5); }} }}
        }},
        x: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 11 }}, maxRotation: 45, minRotation: 30 }} }}
      }}
    }}
  }});
}})();
</script>


<div class="tbl-wrap" style="margin-top:20px;">
<table class="exp-table" id="tbl_{chart_id}">
<thead><tr>
  <th onclick="sortTable('tbl_{chart_id}',0)">{label_col.replace('_',' ').title()}</th>
  <th onclick="sortTable('tbl_{chart_id}',1)">Contribuição</th>
  <th onclick="sortTable('tbl_{chart_id}',2)">BM Ativo</th>
  <th onclick="sortTable('tbl_{chart_id}',3)">Alpha</th>
</tr></thead>
<tbody>{rows_html}</tbody>
</table>
</div>
"""



def _waterfall_day_section_html(
    df_day: pd.DataFrame,
    df_fund: pd.DataFrame,
    fundo: str,
    chart_id: str,
) -> str:
    """Waterfall horizontal por dia (ordem cronológica)."""
    frow   = df_fund[df_fund["fundo"] == fundo].iloc[0]
    labels, bases, values, colors = _waterfall_chartjs_data(
        df_day, fundo, "date", sort_col="date", sort_asc=True
    )


    subset = (
        df_day[df_day["fundo"] == fundo]
        .sort_values("date")
        .reset_index(drop=True)
    )


    rows_html = ""
    for _, row in subset.iterrows():
        contrib = float(row["contribuicao_pp"])
        bm      = float(row["benchmark_ativos_pnl_total_perc"])
        alpha   = float(row["alpha"])
        cor_c   = "tot-green" if contrib > 0 else ("tot-red" if contrib < 0 else "")
        cor_a   = "tot-green" if alpha  > 0 else ("tot-red" if alpha  < 0 else "")
        s = lambda v: ("+" if v > 0 else "") + f"{v:.6f}"
        rows_html += (
            f'<tr>'
            f'<td>{row["date"]}</td>'
            f'<td class="{cor_c} bold">{s(contrib)}</td>'
            f'<td>{s(bm)}</td>'
            f'<td class="{cor_a} bold">{s(alpha)}</td>'
            f'</tr>'
        )


    bar_height = 420


    return f"""
<div class="kpi-section" id="kpi_{{chart_id}}">{_kpi_cards_html(frow)}</div>
<div class="chart-wrap">
  <canvas id="{chart_id}" style="height:{bar_height}px;"></canvas>
</div>
<script>
(function(){{
  var labels  = {json.dumps(labels)};
  var bases   = {json.dumps(bases)};
  var vals    = {json.dumps(values)};
  var colors  = {json.dumps(colors)};
  var floats  = vals.map(function(v,i){{ return [bases[i], bases[i]+v]; }});
  window.__CHARTS__ = window.__CHARTS__ || {{}};
  window.__CHARTS__['{chart_id}'] = new Chart(document.getElementById('{chart_id}'), {{
    type: 'bar',
    data: {{
      labels: labels,
      datasets: [{{
        label: 'Retorno Diário',
        data: floats,
        backgroundColor: colors,
        borderColor: colors,
        borderWidth: 1,
        borderRadius: 3,
      }}]
    }},
    options: {{
      indexAxis: 'x',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          callbacks: {{
            label: function(ctx) {{
              var v = vals[ctx.dataIndex];
              return (v >= 0 ? '+' : '') + v.toFixed(6);
            }},
            title: function(ctx) {{
              return 'Data: ' + labels[ctx[0].dataIndex];
            }}
          }}
        }}
      }},
      scales: {{
        y: {{
          grid: {{ color: '#e0e0e0' }},
          ticks: {{ callback: function(v){{ return v.toFixed(5); }} }}
        }},
        x: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 11 }}, maxRotation: 45, minRotation: 30 }} }}
      }}
    }}
  }});
}})();
</script>


<div class="tbl-wrap" style="margin-top:20px;">
<table class="exp-table" id="tbl_{chart_id}">
<thead><tr>
  <th onclick="sortTable('tbl_{chart_id}',0)">Data</th>
  <th onclick="sortTable('tbl_{chart_id}',1)">Retorno Diário</th>
  <th onclick="sortTable('tbl_{chart_id}',2)">BM Ativos</th>
  <th onclick="sortTable('tbl_{chart_id}',3)">Alpha</th>
</tr></thead>
<tbody>{rows_html}</tbody>
</table>
</div>
"""



def _comparativo_html(df_fund: pd.DataFrame) -> str:
    """Barras de rentabilidade por fundo, agrupadas por classificação do Excel."""
    xl_path = INPUT_DIR / "fundos_exposicao.xlsx"
    sheet_order = pd.ExcelFile(str(xl_path)).sheet_names if xl_path.exists() else []


    grupos: dict = {}
    for _, row in df_fund.iterrows():
        grp = CLASSIFICACAO.get(row["fundo"], "Outros")
        grupos.setdefault(grp, []).append(row)


    def _grp_ord(g):
        try:    return sheet_order.index(g)
        except: return len(sheet_order)


    content = ""
    for grp in sorted(grupos, key=_grp_ord):
        rows   = sorted(grupos[grp], key=lambda r: float(r["rentabilidade_pp"]), reverse=True)
        labels = [r["fundo"] for r in rows]
        rents  = [round(float(r["rentabilidade_pp"]), 6) for r in rows]
        bms    = [round(float(r["benchmark_fundo_pp"]), 6) for r in rows]
        colors = ["#2ecc71" if v >= 0 else "#e74c3c" for v in rents]
        cid    = f"comp_{grp.replace(' ','_').replace('&','_').replace('/','_')}"


        tbl_rows = ""
        for rank, r in enumerate(rows, 1):
            rent  = float(r["rentabilidade_pp"])
            bm    = float(r["benchmark_fundo_pp"])
            alpha = float(r["alpha_vs_bm_fundo"])
            s     = lambda v: ("+" if v > 0 else "") + f"{v:.6f}"
            cr    = "tot-green" if rent  > 0 else ("tot-red" if rent  < 0 else "")
            ca    = "tot-green" if alpha > 0 else ("tot-red" if alpha < 0 else "")
            tbl_rows += (
                f'<tr>'
                f'<td style="color:#aaa;width:28px;text-align:center">{rank}°</td>'
                f'<td style="text-align:left;font-weight:600">{r["fundo"]}</td>'
                f'<td class="{cr} bold">{s(rent)}</td>'
                f'<td>{s(bm)}</td>'
                f'<td class="{ca} bold">{s(alpha)}</td>'
                f'</tr>'
            )


        chart_h = max(280, len(labels) * 36)
        content += f"""
<div class="comp-group">
  <div class="comp-group-title">
    {grp}
    <span class="comp-count">{len(rows)} fundo(s)</span>
  </div>
  <div class="chart-wrap" style="margin-bottom:12px;">
    <canvas id="{cid}" style="height:{chart_h}px;"></canvas>
  </div>
  <div class="tbl-wrap" style="margin-bottom:32px;">
    <table class="exp-table" id="tbl_{cid}">
      <thead><tr>
        <th>#</th>
        <th onclick="sortTable('tbl_{cid}',1)" style="text-align:left">Fundo</th>
        <th onclick="sortTable('tbl_{cid}',2)">Rentabilidade</th>
        <th onclick="sortTable('tbl_{cid}',3)">BM Fundo</th>
        <th onclick="sortTable('tbl_{cid}',4)">Alpha</th>
      </tr></thead>
      <tbody>{tbl_rows}</tbody>
    </table>
  </div>
</div>
<script>
(function(){{
  var labels = {json.dumps(labels)};
  var rents  = {json.dumps(rents)};
  var bms    = {json.dumps(bms)};
  var colors = {json.dumps(colors)};
  window.__CHARTS__ = window.__CHARTS__ || {{}};
  window.__CHARTS__['{cid}'] = new Chart(document.getElementById('{cid}'), {{
    type: 'bar',
    data: {{
      labels: labels,
      datasets: [
        {{
          label: 'Rentabilidade',
          data: rents,
          backgroundColor: colors,
          borderColor: colors,
          borderWidth: 1,
          borderRadius: 3,
          order: 1,
        }},
        {{
          label: 'BM Fundo',
          data: bms,
          type: 'line',
          borderColor: '#000D3C',
          backgroundColor: 'transparent',
          borderWidth: 1.5,
          borderDash: [5,3],
          pointRadius: 4,
          pointBackgroundColor: '#000D3C',
          order: 0,
        }}
      ]
    }},
    options: {{
      indexAxis: 'x',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{ display: true, position: 'top', labels: {{ font: {{ size: 11 }} }} }},
        tooltip: {{
          callbacks: {{
            label: function(ctx) {{
              var v = ctx.raw;
              return ctx.dataset.label + ': ' + (v >= 0 ? '+' : '') + v.toFixed(6);
            }}
          }}
        }}
      }},
      scales: {{
        y: {{ grid: {{ color: '#e0e0e0' }},
               ticks: {{ callback: function(v){{ return v.toFixed(4); }} }} }},
        x: {{ grid: {{ display: false }},
               ticks: {{ font: {{ size: 10 }}, maxRotation: 45, minRotation: 30 }} }}
      }}
    }}
  }});
}})();
</script>
"""
    return content



def generate_html(windows_data: dict) -> None:
    w1d       = windows_data.get("1D", next(iter(windows_data.values())))
    df_fund   = pd.DataFrame(w1d["fund"]).fillna(0)
    df_tipo   = pd.DataFrame(w1d["tipo"]).fillna(0)
    df_ticker = pd.DataFrame(w1d["ticker"]).fillna(0)
    df_ativo  = pd.DataFrame(w1d["ativo"]).fillna(0)
    df_day    = pd.DataFrame(w1d["day"]).fillna(0)
    d0, d1    = w1d["dates"]
    ini_br    = f"{d0[8:10]}/{d0[5:7]}/{d0[:4]}"
    data_br   = f"{d1[8:10]}/{d1[5:7]}/{d1[:4]}"
    # JSON for client-side window switching
    _def = lambda o: 0.0 if isinstance(o, float) and (o != o) else o
    windows_json     = json.dumps(windows_data, ensure_ascii=False, default=_def)
    fundos_all       = sorted({r["fundo"] for w in windows_data.values() for r in w["fund"]})
    fundo_safe_json  = json.dumps(
        {f: f.replace(" ", "_").replace("/", "_") for f in fundos_all},
        ensure_ascii=False)
    fundo_grupo_json = json.dumps(
        {f: CLASSIFICACAO.get(f, "Outros") for f in fundos_all},
        ensure_ascii=False)
    fundos  = df_fund["fundo"].tolist()


    first_fundo   = fundos[0] if fundos else ""
    comparativo_h = _comparativo_html(df_fund)
    grupos = _fundos_por_grupo(fundos)
    fund_menu_items = ""
    first = True
    for grp, gfundos in grupos.items():
        fund_menu_items += f'<div class="fund-group-label">{grp}</div>'
        for f in gfundos:
            active = "active" if first else ""
            fund_menu_items += f'<button class="{active}" onclick="showFundo(\'{f}\')">{f}</button>'
            first = False


    fundo_sections = ""
    for fi, fundo in enumerate(fundos):
        fundo_safe  = fundo.replace(" ", "_").replace("/", "_")
        dia_html    = _waterfall_day_section_html(df_day,   df_fund, fundo, f"wf_dia_{fundo_safe}")
        tipo_html   = _waterfall_section_html(df_tipo,   df_fund, fundo, "tipo",         f"wf_tipo_{fundo_safe}")
        ticker_html = _waterfall_section_html(df_ticker, df_fund, fundo, "ticker_bolsa", f"wf_ticker_{fundo_safe}")
        ativo_html  = _waterfall_section_html(df_ativo,  df_fund, fundo, "ativo",        f"wf_ativo_{fundo_safe}")


        fundo_sections += f"""
<div class="fundo-sec{'  active' if fi == 0 else ''}" data-fundo="{fundo}">
  <div class="nav-sub">
    <button class="nav-btn active" onclick="showAba(this, 'dia_{fundo_safe}')">Por Dia</button>
    <button class="nav-btn"        onclick="showAba(this, 'tipo_{fundo_safe}')">Por Tipo</button>
    <button class="nav-btn"        onclick="showAba(this, 'ticker_{fundo_safe}')">Por Ticker</button>
    <button class="nav-btn"        onclick="showAba(this, 'ativo_{fundo_safe}')">Por Ativo</button>
  </div>
  <div class="content">
    <div class="pane active" id="dia_{fundo_safe}">
      <div class="aba-title" data-aba="Por Dia" id="title_dia_{{fundo_safe}}">Por Dia — {ini_br} → {data_br}</div>{dia_html}
    </div>
    <div class="pane" id="tipo_{fundo_safe}">
      <div class="aba-title" data-aba="Por Tipo" id="title_tipo_{{fundo_safe}}">Por Tipo — {ini_br} → {data_br}</div>{tipo_html}
    </div>
    <div class="pane" id="ticker_{fundo_safe}">
      <div class="aba-title" data-aba="Por Ticker" id="title_ticker_{{fundo_safe}}">Por Ticker — {ini_br} → {data_br}</div>{ticker_html}
    </div>
    <div class="pane" id="ativo_{fundo_safe}">
      <div class="aba-title" data-aba="Por Ativo" id="title_ativo_{{fundo_safe}}">Por Ativo — {ini_br} → {data_br}</div>{ativo_html}
    </div>
  </div>
</div>
"""


    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Performance Attribution — {data_br}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f0f3fa; color: #1a1a2e; }}


    .hdr {{ background: #000D3C; padding: 24px 40px 0; }}
    .hdr::after {{ content: ''; display: block; height: 4px; background: #EC7000; margin-top: 20px; }}
    .hdr-inner {{ display: flex; align-items: center; justify-content: space-between; }}
    .hdr h1 {{ color: #fff; font-size: 1.7rem; font-weight: 700; letter-spacing: .06em; }}
    .hdr .sub {{ color: #aaa; font-size: .88rem; margin-top: 5px; }}
    .hdr .sub strong {{ color: #fff; }}
    .brand span {{ color: #aaa; font-size: 1.8rem; font-weight: 700; }}


    .nav-wrapper {{ position: sticky; top: 0; z-index: 100; box-shadow: 0 3px 10px rgba(0,0,0,.09); }}
    .nav-main {{ background: #000D3C; padding: 0 20px; display: flex; align-items: center; gap: 0; }}


    .btn-voltar {{ padding: 10px 16px; background: none; border: none;
                   border-right: 1px solid rgba(255,255,255,.15);
                   color: #aaa; font-weight: 600; font-size: .82rem;
                   cursor: pointer; text-decoration: none; white-space: nowrap;
                   transition: color .17s; margin-right: 10px; display: flex; align-items: center; gap: 6px; }}
    .btn-voltar:hover {{ color: #fff; }}


    .fund-dropdown {{ position: relative; }}
    .fund-btn {{ padding: 13px 20px; background: none; border: none;
                  border-bottom: 3px solid #EC7000;
                  color: #fff; font-weight: 700; font-size: .88rem;
                  letter-spacing: .06em; cursor: pointer; white-space: nowrap;
                  display: flex; align-items: center; gap: 8px; }}
    .fund-btn .arrow {{ font-size: .7rem; transition: transform .2s; }}
    .fund-btn.open .arrow {{ transform: rotate(180deg); }}
    .fund-menu {{ display: none; position: absolute; top: 100%; left: 0;
                   background: #000D3C; border-top: 2px solid #EC7000;
                   min-width: 240px; max-height: 400px; overflow-y: auto;
                   box-shadow: 0 8px 24px rgba(0,0,0,.35); z-index: 200; }}
    .fund-menu.open {{ display: block; }}
    .fund-menu button {{ display: block; width: 100%; padding: 8px 18px 8px 26px;
                          background: none; border: none; border-bottom: 1px solid rgba(255,255,255,.05);
                          color: #ccc; font-size: .83rem; text-align: left;
                          cursor: pointer; transition: all .15s; }}
    .fund-menu button:hover {{ background: rgba(236,112,0,.2); color: #fff; }}
    .fund-menu button.active {{ color: #EC7000; font-weight: 700; }}
    .fund-group-label {{ padding: 8px 18px 4px; font-size: .68rem; font-weight: 700;
                          color: #EC7000; text-transform: uppercase; letter-spacing: .08em;
                          border-top: 1px solid rgba(255,255,255,.12); margin-top: 2px; }}


    .nav-sub {{ background: #fff; padding: 10px 40px; display: flex; flex-wrap: wrap; gap: 8px;
                 align-items: center; border-bottom: 2px solid #e0e0e0; }}
    .nav-btn {{ padding: 7px 18px; border: 2px solid #EC7000; border-radius: 20px;
                 background: #fff; color: #EC7000; font-weight: 600; font-size: .82rem;
                 cursor: pointer; transition: all .17s; white-space: nowrap; }}
    .nav-btn:hover {{ background: #EC700018; }}
    .nav-btn.active {{ background: #EC7000; color: #fff; box-shadow: 0 2px 8px #EC700055; }}


    .fundo-sec {{ display: none; }}
    .fundo-sec.active {{ display: block; }}
    .content {{ padding: 28px 40px 50px; }}
    .pane {{ display: none; animation: fadeIn .2s; }}
    .pane.active {{ display: block; }}
    @keyframes fadeIn {{ from {{ opacity:0; transform:translateY(4px); }} to {{ opacity:1; }} }}
    .aba-title {{ font-size: 1rem; font-weight: 700; color: #EC7000; margin-bottom: 14px;
                   text-transform: uppercase; letter-spacing: .08em; }}


    .kpi-section {{ margin-bottom: 22px; }}
    .kpi-row {{ display: flex; flex-wrap: wrap; gap: 14px; }}
    .kpi-card {{ background: #fff; border-radius: 10px; padding: 14px 22px;
                  box-shadow: 0 2px 10px rgba(0,0,0,.08); min-width: 160px; }}
    .kpi-label {{ font-size: .75rem; font-weight: 600; color: #aaa;
                   text-transform: uppercase; letter-spacing: .06em; margin-bottom: 6px; }}
    .kpi-value {{ font-size: 1.15rem; font-weight: 700; }}


    .chart-wrap {{ background: #fff; border-radius: 10px; padding: 20px;
                    box-shadow: 0 2px 16px rgba(0,0,0,.10); margin-bottom: 20px; overflow-x: auto; }}


    .tbl-wrap {{ overflow-x: auto; border-radius: 10px; box-shadow: 0 2px 16px rgba(0,0,0,.10); }}
    .exp-table {{ border-collapse: collapse; width: 100%; font-size: .83rem;
                   background: #fff; min-width: 600px; }}
    .exp-table thead tr {{ background: #000D3C; }}
    .exp-table th {{ color: #fff; font-weight: 600; padding: 11px 14px; white-space: nowrap;
                      text-align: center; cursor: pointer; user-select: none;
                      border-right: 1px solid #ffffff1a; }}
    .exp-table th:hover {{ background: #112070; }}
    .exp-table th.asc::after  {{ content: ' ▲'; font-size: .6em; opacity: .8; }}
    .exp-table th.desc::after {{ content: ' ▼'; font-size: .6em; opacity: .8; }}
    .exp-table td {{ padding: 9px 14px; text-align: center; border-bottom: 1px solid #e0e0e0;
                      border-right: 1px solid #e0e0e0; white-space: nowrap; }}
    .exp-table td:first-child {{ text-align: left; font-weight: 600; }}
    .exp-table tbody tr:nth-child(even) {{ background: #eaf0fb; }}
    .exp-table tbody tr:hover {{ background: #d6e4ff !important; }}
    .bold {{ font-weight: 700; }}
    .tot-green {{ color: #1e7e34; }}
    .tot-red   {{ color: #c0392b; }}


    .comp-btn {{ padding: 13px 22px; background: none; border: none;
                  border-bottom: 3px solid transparent;
                  color: #aaa; font-weight: 700; font-size: .88rem;
                  letter-spacing: .06em; cursor: pointer; transition: all .18s;
                  white-space: nowrap; margin-left: 8px; }}
    .comp-btn:hover {{ color: #fff; }}
    .comp-btn.active {{ color: #fff; border-bottom-color: #EC7000; }}


    .comp-sec {{ display: none; }}
    .comp-sec.active {{ display: block; }}
    .comp-group {{ margin-bottom: 8px; }}
    .comp-group-title {{ font-size: 1rem; font-weight: 700; color: #EC7000;
                          text-transform: uppercase; letter-spacing: .08em;
                          padding: 28px 40px 12px; display: flex; align-items: center; gap: 10px; }}
    .comp-count {{ font-size: .75rem; font-weight: 400; color: #aaa;
                    background: #f0f3fa; padding: 2px 10px; border-radius: 10px; }}
    .comp-group .chart-wrap,
    .comp-group .tbl-wrap {{ margin: 0 40px; }}


    .win-bar {{ background: #f0f3fa; padding: 8px 40px; display: flex;
                 align-items: center; gap: 8px; border-bottom: 2px solid #e0e0e0; }}
    .win-label {{ font-size: .75rem; font-weight: 700; color: #555;
                  text-transform: uppercase; margin-right: 4px; }}
    .win-btn {{ padding: 5px 15px; border: 2px solid #000D3C; border-radius: 16px;
                background: #fff; color: #000D3C; font-weight: 700; font-size: .82rem;
                cursor: pointer; transition: all .15s; }}
    .win-btn:hover {{ background: #000D3C18; }}
    .win-btn.active {{ background: #000D3C; color: #fff; }}
    .win-period {{ font-size: .78rem; color: #888; margin-left: 12px; }}

    .footer {{ background: #fff; border-top: 3px solid #000D3C; padding: 16px 40px;
                font-size: .78rem; color: #aaa; font-style: italic; text-align: center; }}
  </style>
</head>
<body>


<div class="hdr">
  <div class="hdr-inner">
    <div>
      <h1>PERFORMANCE ATTRIBUTION</h1>
      <p class="sub">Período: &nbsp;<strong>{DATA_INICIO} → {DATA_FIM}</strong></p>
    </div>
    <div class="brand">
      <span>Itaú Asset Management</span>
      {{logo_tag}}
    </div>
  </div>
</div>


<div class="nav-wrapper">
  <div class="win-bar">
    <span class="win-label">Janela:</span>
    <button class="win-btn active" onclick="setWindow('1D')">1D</button>
    <button class="win-btn" onclick="setWindow('21D')">21D</button>
    <button class="win-btn" onclick="setWindow('60D')">60D</button>
    <button class="win-btn" onclick="setWindow('YTD')">YTD</button>
    <span class="win-period" id="win-period"></span>
  </div>
  <nav class="nav-main">
    <a href="../index.html" class="btn-voltar">&#8592; Voltar</a>
    <div class="fund-dropdown">
      <button class="fund-btn" id="fund-btn" onclick="toggleFundMenu()">
        <span id="fund-label">{first_fundo}</span>
        <span class="arrow">&#9660;</span>
      </button>
      <div class="fund-menu" id="fund-menu">{fund_menu_items}</div>
    </div>
    <button class="comp-btn" id="comp-btn" onclick="showComparativo()">&#9654; Comparativo</button>
  </nav>
</div>


{fundo_sections}


<div class="comp-sec" id="comp-sec">
  {comparativo_h}
</div>


<div class="footer">
  Gerado em {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')} &nbsp;|&nbsp;
  Fonte: DBSX337.dbo.VW_FUNDOS_PERFORMANCE_ATTRIBUTION
</div>


<script>
function toggleFundMenu() {{
  var menu = document.getElementById('fund-menu');
  var btn  = document.getElementById('fund-btn');
  menu.classList.toggle('open');
  btn.classList.toggle('open');
}}


function showComparativo() {{
  document.querySelectorAll('.fundo-sec').forEach(function(el){{ el.classList.remove('active'); }});
  document.getElementById('comp-sec').classList.add('active');
  document.getElementById('comp-btn').classList.add('active');
  document.getElementById('fund-menu').classList.remove('open');
  document.getElementById('fund-btn').classList.remove('open');
}}


function showFundo(fundo) {{
  document.getElementById('comp-sec').classList.remove('active');
  document.getElementById('comp-btn').classList.remove('active');
  document.querySelectorAll('.fundo-sec').forEach(function(el){{
    el.classList.toggle('active', el.dataset.fundo === fundo);
  }});
  document.querySelectorAll('#fund-menu button').forEach(function(btn){{
    btn.classList.toggle('active', btn.textContent.trim() === fundo);
  }});
  document.getElementById('fund-label').textContent = fundo;
  document.getElementById('fund-menu').classList.remove('open');
  document.getElementById('fund-btn').classList.remove('open');
}}


document.addEventListener('click', function(e) {{
  var dd = document.querySelector('.fund-dropdown');
  if (dd && !dd.contains(e.target)) {{
    document.getElementById('fund-menu').classList.remove('open');
    document.getElementById('fund-btn').classList.remove('open');
  }}
}});


function showAba(btn, paneId) {{
  var sec = btn.closest('.fundo-sec');
  sec.querySelectorAll('.pane').forEach(function(p){{ p.classList.remove('active'); }});
  sec.querySelectorAll('.nav-btn').forEach(function(b){{ b.classList.remove('active'); }});
  document.getElementById(paneId).classList.add('active');
  btn.classList.add('active');
}}


function sortTable(tableId, col) {{
  var tbl = document.getElementById(tableId);
  var th  = tbl.querySelectorAll('th')[col];
  var asc = !th.classList.contains('asc');
  tbl.querySelectorAll('th').forEach(function(h){{ h.classList.remove('asc','desc'); }});
  th.classList.add(asc ? 'asc' : 'desc');
  var tbody = tbl.querySelector('tbody');
  var rows  = Array.from(tbody.querySelectorAll('tr'));
  rows.sort(function(a,b){{
    var av = a.cells[col].textContent.replace('+','').trim();
    var bv = b.cells[col].textContent.replace('+','').trim();
    var an = parseFloat(av), bn = parseFloat(bv);
    if (!isNaN(an) && !isNaN(bn)) return asc ? an-bn : bn-an;
    return asc ? av.localeCompare(bv) : bv.localeCompare(av);
  }});
  rows.forEach(function(r){{ tbody.appendChild(r); }});
}}
</script>
</body>
</html>"""


    logo_b64 = _logo_base64()
    logo_tag = (
        f'<img src="data:image/png;base64,{logo_b64}" '
        f'style="height:48px;width:auto;object-fit:contain;margin-left:16px;" alt="Logo">'
        if logo_b64 else ""
    )
    html = html.replace("{logo_tag}", logo_tag)
    html = html.replace('__WINDOWS_JSON__',     windows_json)
    html = html.replace('__FUNDO_SAFE_JSON__',  fundo_safe_json)
    html = html.replace('__FUNDO_GRUPO_JSON__', fundo_grupo_json)


    date_slug = DATA_FIM.replace("-", "")
    sub_dir   = OUTPUT_DIR / date_slug
    sub_dir.mkdir(parents=True, exist_ok=True)


    # salva o relatório
    fname = f"perf_att_{date_slug}.html"
    path  = sub_dir / fname
    path.write_text(html, encoding="utf-8")
    print(f"  HTML salvo: {path}")


    # salva manifest para o index
    manifest = {
        "date":   DATA_FIM,
        "fundos": fundos,
        "file":   f"{date_slug}/{fname}",
    }
    (sub_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )



# ---------------------------------------------------------------------------
# 7. INDEX HTML (calendário + seletor de fundo)
# ---------------------------------------------------------------------------


def generate_index() -> None:
    """Varre os manifests e gera output/performance/index.html."""
    # coleta todos os manifests
    reports: list = []
    for m in sorted(OUTPUT_DIR.glob("*/manifest.json"), reverse=True):
        try:
            data = json.loads(m.read_text(encoding="utf-8"))
            reports.append(data)
        except Exception:
            pass


    if not reports:
        print("  Nenhum manifest encontrado — index não gerado.")
        return


    # todos os fundos disponíveis nos relatórios
    all_fundos: set = {f for r in reports for f in r.get("fundos", [])}


    # objeto JS: { "2026-06-11": { file: "...", fundos: [...] }, ... }
    reports_js = {
        r["date"]: {"file": r["file"], "fundos": r.get("fundos", [])}
        for r in reports
    }


    # tabela histórico
    rows_html = ""
    for i, r in enumerate(reports):
        bg    = ' style="background:#eaf0fb"' if i % 2 else ""
        badge = '<span class="badge">Mais recente</span>' if i == 0 else ""
        d     = r["date"]
        d_br  = f"{d[8:10]}/{d[5:7]}/{d[:4]}"
        flist  = r.get("fundos", [])
        grupos = _fundos_por_grupo(flist)
        cat_tags = "".join(
            f'<span class="fund-tag">{grp} <span class="cat-count">({len(gfundos)})</span></span>'
            for grp, gfundos in grupos.items()
        )
        fund_cell = f'<div class="fund-tags">{cat_tags}</div>'


        rows_html += (
            f'<tr{bg}><td>{d_br}{badge}</td>'
            f'<td><a href="{r["file"]}" class="link">{r["file"].split("/")[-1]}</a></td>'
            f'<td>{fund_cell}</td></tr>'
        )


    logo_b64  = _logo_base64()
    logo_tag  = (
        f'<img src="data:image/png;base64,{logo_b64}" class="logo-img" alt="Logo">'
        if logo_b64 else ""
    )
    n_reports = len(reports)
    last_date = reports[0]["date"] if reports else ""
    last_d_br = f"{last_date[8:10]}/{last_date[5:7]}/{last_date[:4]}" if last_date else ""


    # mês inicial = mês do relatório mais recente
    init_year  = int(last_date[:4])  if last_date else datetime.now().year
    init_month = int(last_date[5:7]) - 1 if last_date else datetime.now().month - 1


    # dropdown agrupado por classificação do Excel
    # percorre abas na ordem original do Excel para manter a hierarquia
    xl_path = INPUT_DIR / "fundos_exposicao.xlsx"
    sheet_order = pd.ExcelFile(str(xl_path)).sheet_names if xl_path.exists() else []
    grupos_idx: dict = {}
    for f in CLASSIFICACAO:
        if f in all_fundos:
            grp = CLASSIFICACAO[f]
            grupos_idx.setdefault(grp, []).append(f)
    # fundos sem classificação
    outros = sorted(f for f in all_fundos if f not in CLASSIFICACAO)
    if outros:
        grupos_idx["Outros"] = outros


    # ordena grupos pela ordem das abas do Excel
    def _grp_order(g):
        try:    return sheet_order.index(g)
        except: return len(sheet_order)


    fundos_options = ""
    for grp in sorted(grupos_idx, key=_grp_order):
        fundos_options += f'<optgroup label="{grp}">'
        for f in grupos_idx[grp]:
            fundos_options += f'<option value="{f}">{f}</option>'
        fundos_options += '</optgroup>'


    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Performance Attribution — Histórico</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f0f3fa; color: #1a1a2e; }}


    .hdr {{ background: #000D3C; padding: 24px 40px 0; }}
    .hdr::after {{ content: ''; display: block; height: 4px; background: #EC7000; margin-top: 20px; }}
    .hdr-inner {{ display: flex; align-items: center; justify-content: space-between; }}
    .hdr h1 {{ color: #fff; font-size: 1.7rem; font-weight: 700; letter-spacing: .06em; }}
    .hdr .sub {{ color: #aaa; font-size: .88rem; margin-top: 5px; }}
    .brand {{ display: flex; align-items: center; gap: 12px; }}
    .brand span {{ color: #aaa; font-size: 2.1rem; font-weight: 700; letter-spacing: .04em; }}
    .logo-img {{ height: 52px; width: auto; object-fit: contain; }}


    .content {{ padding: 40px; max-width: 1100px; margin: 0 auto;
                 display: grid; grid-template-columns: 320px 1fr; gap: 32px; align-items: start; }}


    /* ── Painel esquerdo ── */
    .left-panel {{ display: flex; flex-direction: column; gap: 20px; }}


    /* ── Seletor de fundo ── */
    .filter-card {{ background: #fff; border-radius: 12px;
                    box-shadow: 0 2px 16px rgba(0,0,0,.10); overflow: hidden; }}
    .filter-header {{ background: #000D3C; color: #fff; font-weight: 700;
                       font-size: .88rem; padding: 14px 18px; letter-spacing: .04em; }}
    .filter-body {{ padding: 16px 18px; display: flex; flex-direction: column; gap: 10px; }}
    .filter-body label {{ font-size: .8rem; font-weight: 600; color: #555;
                           text-transform: uppercase; letter-spacing: .05em; }}
    .filter-body select {{ padding: 8px 12px; border: 1.5px solid #e0e0e0; border-radius: 8px;
                            font-size: .85rem; outline: none; transition: border .2s; width: 100%; }}
    .filter-body select:focus {{ border-color: #EC7000; box-shadow: 0 0 0 3px #EC700022; }}
    .btn-clear {{ padding: 8px 16px; background: none; border: 2px solid #EC7000;
                  border-radius: 8px; color: #EC7000; font-weight: 600; font-size: .82rem;
                  cursor: pointer; transition: all .17s; width: 100%; }}
    .btn-clear:hover {{ background: #EC700018; }}


    /* ── Calendário ── */
    .cal-card {{ background: #fff; border-radius: 12px;
                  box-shadow: 0 2px 16px rgba(0,0,0,.10); overflow: hidden; }}
    .cal-nav {{ background: #000D3C; display: flex; align-items: center;
                 justify-content: space-between; padding: 14px 18px; }}
    .cal-nav button {{ background: none; border: none; color: #fff; font-size: 1.3rem;
                        cursor: pointer; padding: 0 6px; border-radius: 4px; }}
    .cal-nav button:hover {{ background: rgba(255,255,255,.15); }}
    .cal-nav span {{ color: #fff; font-weight: 700; font-size: 1rem; letter-spacing: .04em; }}
    .cal-grid {{ display: grid; grid-template-columns: repeat(7, 1fr); gap: 0; padding: 12px; }}
    .cal-dow {{ text-align: center; font-size: .72rem; font-weight: 700;
                 color: #aaa; padding: 6px 0; text-transform: uppercase; }}
    .cal-day {{ text-align: center; padding: 8px 4px; font-size: .85rem;
                 border-radius: 6px; cursor: default; color: #555; }}
    .cal-day.empty {{ background: none; }}
    .cal-day.has-report {{ background: #EC7000; color: #fff; font-weight: 700;
                            cursor: pointer; transition: background .15s; }}
    .cal-day.has-report:hover {{ background: #c85e00; }}
    .cal-day.today {{ outline: 2px solid #000D3C; outline-offset: -2px; }}
    .cal-day.dimmed {{ opacity: .35; cursor: default !important; }}


    /* ── Tabela histórico ── */
    .tbl-card {{ background: #fff; border-radius: 12px;
                  box-shadow: 0 2px 16px rgba(0,0,0,.10); overflow: hidden; }}
    .tbl-title {{ background: #000D3C; color: #fff; font-weight: 700;
                   font-size: .88rem; padding: 14px 20px; letter-spacing: .04em; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th {{ color: #aaa; font-weight: 600; padding: 10px 20px;
           text-align: left; font-size: .78rem; text-transform: uppercase;
           border-bottom: 2px solid #e0e0e0; }}
    td {{ padding: 11px 20px; border-bottom: 1px solid #e0e0e0; font-size: .85rem; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #eef3ff; transition: background .12s; }}
    tr.hidden {{ display: none; }}
    .link {{ color: #EC7000; text-decoration: none; font-weight: 600; }}
    .link:hover {{ text-decoration: underline; }}
    .badge {{ background: #EC7000; color: #fff; font-size: .65rem; font-weight: 700;
               padding: 2px 8px; border-radius: 10px; margin-left: 8px; vertical-align: middle; }}
    .fund-tags {{ display: flex; flex-wrap: wrap; gap: 4px; max-width: 380px; }}
    .fund-tag {{ background: #eaf0fb; color: #000D3C; font-size: .75rem; font-weight: 700;
                  padding: 3px 10px; border-radius: 10px; white-space: nowrap;
                  border: 1px solid #c5d5f0; text-transform: uppercase; letter-spacing: .04em; }}
    .cat-count {{ font-weight: 400; color: #7a90b8; font-size: .68rem; }}


    .footer {{ border-top: 3px solid #000D3C; padding: 16px 40px; margin-top: 40px;
                font-size: .78rem; color: #aaa; font-style: italic;
                text-align: center; background: #fff; }}
  </style>
</head>
<body>


<div class="hdr">
  <div class="hdr-inner">
    <div>
      <h1>PERFORMANCE ATTRIBUTION</h1>
      <p class="sub">Histórico — {n_reports} relatório(s) | Último: <strong style="color:#fff">{last_d_br}</strong></p>
    </div>
    <div class="brand"><span>Itaú Asset Management</span>{logo_tag}</div>
  </div>
</div>


<div class="content">


  <div class="left-panel">


    <!-- Seletor de fundo -->
    <div class="filter-card">
      <div class="filter-header">FILTRAR POR FUNDO</div>
      <div class="filter-body">
        <label for="sel-fundo">Fundo</label>
        <select id="sel-fundo" onchange="applyFilter()">
          <option value="">— Todos os fundos —</option>
          {fundos_options}
        </select>
        <button class="btn-clear" onclick="clearFilter()">Limpar filtro</button>
      </div>
    </div>


    <!-- Calendário -->
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
    </div>


  </div>


  <!-- Tabela histórico -->
  <div class="tbl-card">
    <div class="tbl-title" id="tbl-title">HISTÓRICO DE RELATÓRIOS — {n_reports} disponível(is)</div>
    <table>
      <thead><tr>
        <th>Data de Referência</th>
        <th>Arquivo</th>
        <th>Fundos</th>
      </tr></thead>
      <tbody id="tbl-body">{rows_html}</tbody>
    </table>
  </div>


</div>


<div class="footer">Itaú Asset Management — Performance Attribution &nbsp;|&nbsp;
  Gerado em {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}</div>


<script>
  const REPORTS = {json.dumps(reports_js, ensure_ascii=False)};
  const MONTHS  = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
                   'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];
  let curYear  = {init_year};
  let curMonth = {init_month};
  let selFundo = '';


  function visibleDates() {{
    if (!selFundo) return Object.keys(REPORTS);
    return Object.keys(REPORTS).filter(d => REPORTS[d].fundos.includes(selFundo));
  }}


  function renderCal() {{
    const title = document.getElementById('cal-title');
    const grid  = document.getElementById('cal-grid');
    title.textContent = MONTHS[curMonth] + ' ' + curYear;
    grid.innerHTML = '';
    const today  = new Date();
    const first  = new Date(curYear, curMonth, 1).getDay();
    const days   = new Date(curYear, curMonth + 1, 0).getDate();
    const visible = visibleDates();


    for (let i = 0; i < first; i++) {{
      const el = document.createElement('div');
      el.className = 'cal-day empty';
      grid.appendChild(el);
    }}
    for (let d = 1; d <= days; d++) {{
      const el  = document.createElement('div');
      const key = curYear + '-'
                + String(curMonth + 1).padStart(2,'0') + '-'
                + String(d).padStart(2,'0');
      const hasReport = REPORTS[key] !== undefined;
      const inFilter  = visible.includes(key);
      const isToday   = (d === today.getDate() &&
                         curMonth === today.getMonth() &&
                         curYear  === today.getFullYear());


      el.className = 'cal-day'
        + (hasReport && inFilter ? ' has-report' : '')
        + (hasReport && !inFilter ? ' dimmed'     : '')
        + (isToday ? ' today' : '');
      el.textContent = d;
      if (hasReport && inFilter) {{
        el.title   = 'Abrir ' + key;
        el.onclick = () => window.open(REPORTS[key].file, '_blank');
      }}
      grid.appendChild(el);
    }}
  }}


  function applyFilter() {{
    selFundo = document.getElementById('sel-fundo').value;
    const visible = visibleDates();
    const rows    = document.getElementById('tbl-body').querySelectorAll('tr');
    let count = 0;
    rows.forEach(function(row) {{
      const link  = row.querySelector('a');
      if (!link) return;
      const file  = link.getAttribute('href');
      const match = Object.entries(REPORTS).find(([,v]) => v.file === file);
      const show  = !selFundo || (match && match[1].fundos.includes(selFundo));
      row.classList.toggle('hidden', !show);
      if (show) count++;
    }});
    document.getElementById('tbl-title').textContent =
      'HISTÓRICO DE RELATÓRIOS — ' + count + ' disponível(is)' +
      (selFundo ? ' · ' + selFundo : '');
    renderCal();
  }}


  function clearFilter() {{
    document.getElementById('sel-fundo').value = '';
    applyFilter();
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
// ── JANELAS FLEXÍVEIS ────────────────────────────────────────────────────
var __WINDOWS__     = __WINDOWS_JSON__;
var __FUNDO_SAFE__  = __FUNDO_SAFE_JSON__;
var __FUNDO_GRUPO__ = __FUNDO_GRUPO_JSON__;
var __ACTIVE_WIN__  = '1D';

function fmtDate(s) {{
  return s ? s.slice(8)+'/'+s.slice(5,7)+'/'+s.slice(0,4) : '';
}}

function setWindow(label) {{
  __ACTIVE_WIN__ = label;
  document.querySelectorAll('.win-btn').forEach(function(b) {{
    b.classList.toggle('active', b.textContent === label);
  }});
  var w = __WINDOWS__[label];
  if (!w) return;
  var d0 = fmtDate(w.dates[0]), d1 = fmtDate(w.dates[1]);
  var el = document.getElementById('win-period');
  if (el) el.textContent = d0 + ' → ' + d1;
  document.querySelectorAll('.aba-title').forEach(function(t) {{
    if (t.dataset.aba) t.textContent = t.dataset.aba + ' — ' + d0 + ' → ' + d1;
  }});
  var sec = document.querySelector('.fundo-sec.active');
  if (sec) _updFundo(sec.dataset.fundo, w);
  _updComp(w);
}}

function _kpiHtml(r) {{
  function card(t, v, c) {{
    var s = v > 0 ? '+' : '';
    return '<div class="kpi-card"><div class="kpi-label">' + t + '</div>'
         + '<div class="kpi-value" style="color:' + c + '">' + s + v.toFixed(6) + '</div></div>';
  }}
  function cor(v) {{ return v > 0 ? '#1e7e34' : (v < 0 ? '#c0392b' : '#555'); }}
  return '<div class="kpi-row">'
    + card('Rentabilidade',       r.rentabilidade_pp,    cor(r.rentabilidade_pp))
    + card('BM Fundo',            r.benchmark_fundo_pp,  cor(r.benchmark_fundo_pp))
    + card('Alpha vs BM Fundo',   r.alpha_vs_bm_fundo,   cor(r.alpha_vs_bm_fundo))
    + card('BM Ativos',           r.benchmark_ativos_pp, cor(r.benchmark_ativos_pp))
    + card('Alpha vs BM Ativos',  r.alpha_vs_bm_ativos,  cor(r.alpha_vs_bm_ativos))
    + '</div>';
}}

function _wf(rows, labelKey, byDate) {{
  var sorted = byDate
    ? rows.slice().sort(function(a, b) {{ return a[labelKey] < b[labelKey] ? -1 : 1; }})
    : rows.slice().sort(function(a, b) {{ return b.contribuicao_pp - a.contribuicao_pp; }});
  var labels = [], bases = [], values = [], colors = [], run = 0;
  sorted.forEach(function(r) {{
    var v = r.contribuicao_pp;
    labels.push(r[labelKey]); bases.push(run);
    values.push(v); colors.push(v >= 0 ? '#2ecc71' : '#e74c3c'); run += v;
  }});
  labels.push('TOTAL'); bases.push(0); values.push(run); colors.push('#000D3C');
  return {{ labels: labels, bases: bases, values: values, colors: colors }};
}}

function _updChart(cid, rows, labelKey, byDate) {{
  var ch = (window.__CHARTS__ || {{}})[cid];
  if (!ch || !rows.length) return;
  var wf = _wf(rows, labelKey, byDate);
  var floats = wf.values.map(function(v, i) {{ return [wf.bases[i], wf.bases[i] + v]; }});
  ch.data.labels = wf.labels;
  ch.data.datasets[0].data = floats;
  ch.data.datasets[0].backgroundColor = wf.colors;
  ch.data.datasets[0].borderColor = wf.colors;
  ch.update('none');
}}

function _updTbl(tblId, rows, labelKey, byDate) {{
  var tbody = document.querySelector('#' + tblId + ' tbody');
  if (!tbody) return;
  var sorted = byDate
    ? rows.slice().sort(function(a, b) {{ return a[labelKey] < b[labelKey] ? -1 : 1; }})
    : rows.slice().sort(function(a, b) {{ return b.contribuicao_pp - a.contribuicao_pp; }});
  var html = '';
  sorted.forEach(function(r) {{
    var c = r.contribuicao_pp, b = r.benchmark_ativos_pnl_total_perc, a = r.alpha;
    function s(v) {{ return (v > 0 ? '+' : '') + v.toFixed(6); }}
    var cc = c > 0 ? 'tot-green bold' : (c < 0 ? 'tot-red bold' : 'bold');
    var ca = a > 0 ? 'tot-green bold' : (a < 0 ? 'tot-red bold' : 'bold');
    html += '<tr><td>' + r[labelKey] + '</td>'
          + '<td class="' + cc + '">' + s(c) + '</td>'
          + '<td>' + s(b) + '</td>'
          + '<td class="' + ca + '">' + s(a) + '</td></tr>';
  }});
  tbody.innerHTML = html;
}}

function _updFundo(fundo, w) {{
  var fr = w.fund.find(function(r) {{ return r.fundo === fundo; }});
  if (!fr) return;
  var safe = (__FUNDO_SAFE__[fundo] || fundo.replace(/[ \\/]/g, '_'));
  var tipoR = w.tipo.filter(function(r) {{ return r.fundo === fundo; }});
  var tckR  = w.ticker.filter(function(r) {{ return r.fundo === fundo; }});
  var atvR  = w.ativo.filter(function(r) {{ return r.fundo === fundo; }});
  var dayR  = w.day.filter(function(r) {{ return r.fundo === fundo; }});

  ['wf_dia_', 'wf_tipo_', 'wf_ticker_', 'wf_ativo_'].forEach(function(p) {{
    var el = document.getElementById('kpi_' + p + safe);
    if (el) el.innerHTML = _kpiHtml(fr);
  }});

  _updChart('wf_dia_' + safe,    dayR,  'date',         true);
  _updChart('wf_tipo_' + safe,   tipoR, 'tipo',         false);
  _updChart('wf_ticker_' + safe, tckR,  'ticker_bolsa', false);
  _updChart('wf_ativo_' + safe,  atvR,  'ativo',        false);

  _updTbl('tbl_wf_dia_' + safe,    dayR,  'date',         true);
  _updTbl('tbl_wf_tipo_' + safe,   tipoR, 'tipo',         false);
  _updTbl('tbl_wf_ticker_' + safe, tckR,  'ticker_bolsa', false);
  _updTbl('tbl_wf_ativo_' + safe,  atvR,  'ativo',        false);
}}

function _updComp(w) {{
  var grpFunds = {{}};
  w.fund.forEach(function(r) {{
    var grp = (__FUNDO_GRUPO__[r.fundo] || 'Outros');
    if (!grpFunds[grp]) grpFunds[grp] = [];
    grpFunds[grp].push(r);
  }});
  Object.keys(grpFunds).forEach(function(grp) {{
    var rows = grpFunds[grp].slice().sort(function(a, b) {{ return b.rentabilidade_pp - a.rentabilidade_pp; }});
    var cid  = 'comp_' + grp.replace(/[\\s&\\/]/g, '_');
    var ch   = (window.__CHARTS__ || {{}})[cid];
    if (ch) {{
      var labels = rows.map(function(r) {{ return r.fundo; }});
      var rents  = rows.map(function(r) {{ return r.rentabilidade_pp; }});
      var bms    = rows.map(function(r) {{ return r.benchmark_fundo_pp; }});
      var colors = rents.map(function(v) {{ return v >= 0 ? '#2ecc71' : '#e74c3c'; }});
      ch.data.labels = labels;
      ch.data.datasets[0].data = rents;
      ch.data.datasets[0].backgroundColor = colors;
      ch.data.datasets[0].borderColor = colors;
      ch.data.datasets[1].data = bms;
      ch.update('none');
    }}
    var tbody = document.querySelector('#tbl_' + cid + ' tbody');
    if (tbody) {{
      var html = '';
      rows.forEach(function(r, i) {{
        var rent = r.rentabilidade_pp, bm = r.benchmark_fundo_pp, alpha = r.alpha_vs_bm_fundo;
        function s(v) {{ return (v > 0 ? '+' : '') + v.toFixed(6); }}
        var cr = rent  > 0 ? 'tot-green bold' : (rent  < 0 ? 'tot-red bold' : 'bold');
        var ca = alpha > 0 ? 'tot-green bold' : (alpha < 0 ? 'tot-red bold' : 'bold');
        html += '<tr>'
          + '<td style="color:#aaa;width:28px;text-align:center">' + (i+1) + '°</td>'
          + '<td style="text-align:left;font-weight:600">' + r.fundo + '</td>'
          + '<td class="' + cr + '">' + s(rent) + '</td>'
          + '<td>' + s(bm) + '</td>'
          + '<td class="' + ca + '">' + s(alpha) + '</td></tr>';
      }});
      tbody.innerHTML = html;
    }}
  }});
}}

// Initialise period label on load
(function() {{
  var w = __WINDOWS__['1D'];
  if (w) {{
    var el = document.getElementById('win-period');
    if (el) el.textContent = fmtDate(w.dates[0]) + ' → ' + fmtDate(w.dates[1]);
  }}
}})();

</script>
</body>
</html>"""


    idx_path = OUTPUT_DIR / "index.html"
    idx_path.write_text(html, encoding="utf-8")
    print(f"  Index salvo: {idx_path}")



# ---------------------------------------------------------------------------
# 8. MAIN
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    print(f"\nCarregando dados de {DATA_INICIO} a {DATA_FIM}...")
    df_raw = load_data()
    print(f"  {len(df_raw):,} linhas | {df_raw['fundo'].nunique()} fundo(s)")


    df_fund   = summary_by_fund(df_raw)
    df_tipo   = attribution_by_tipo(df_raw)
    df_ticker = attribution_by_ticker(df_raw)
    df_ativo  = attribution_by_ativo(df_raw)
    df_day    = attribution_by_day(df_raw)


    date_slug = DATA_FIM.replace("-", "")
    sub_dir   = OUTPUT_DIR / date_slug
    sub_dir.mkdir(parents=True, exist_ok=True)


    print_report(df_fund, df_tipo, df_ticker, df_ativo)
    export_results(df_fund, df_tipo, df_ticker, df_ativo)
    if SALVAR_PNG:
        plot_all(df_fund, df_tipo, df_ticker, df_ativo, out_dir=sub_dir)
    else:
        print("  PNGs desativados (SALVAR_PNG = 0)")
    windows_data = compute_windows(df_raw, DATA_FIM)
    generate_html(windows_data)
    generate_index()
    export_results(df_fund, df_tipo, df_ticker, df_ativo)
    #plot_all(df_fund, df_tipo, df_ticker, df_ativo)

