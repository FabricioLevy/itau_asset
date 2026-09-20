
from __future__ import annotations
from typing import Dict, List, Optional
import os
import pandas as pd

from config import (
    LOGO_PATH, OUTPUT_BASE, ROW_PAR,
    ITAU_DARK, ITAU_ORANGE, ITAU_GRAY, ITAU_GRAY2,
    ITAU_RED, ITAU_GREEN,
    INPUT_IT_NOW, BETA_FUNDS,
    BETA_DIF_THRESHOLD, BETA_COLOR_GREEN, BETA_COLOR_RED,
    MOSTRAR_ITNOW, MOSTRAR_PERFORMANCE, MOSTRAR_BATIMENTO,
    ALERTA_DIAS_ROLAGEM,
)
from utils import _fmt_money, _fmt_pct, _fmt_pct3, _fmt_du, _fmt_text
from html_styles import (
    SP500_COLS, MOEDAS_COLS, RF_COLS, OURO_COLS, DEB_COLS, ACWI_COLS, CDI_COLS, STD_COLS, PCT_COLS, DU_COLS,
    build_css, build_js,
)


# ─────────────────────────────────────────────────────────────────────────────
# GERAÇÃO DO RELATÓRIO HTML
# ─────────────────────────────────────────────────────────────────────────────

def gerar_html(abas_data: Dict[str, pd.DataFrame], dt: str, out_dir: str,
               rolagem_data: Optional[List[tuple]] = None,
               beta_df: Optional[pd.DataFrame] = None,
               it_now_df: Optional[pd.DataFrame] = None,
               pnl_df: Optional[pd.DataFrame] = None,
               posicoes_df: Optional[pd.DataFrame] = None,
               despesas_df: Optional[pd.DataFrame] = None,
               pa_df: Optional[pd.DataFrame] = None,
               historico_df: Optional[pd.DataFrame] = None,
               batimento_df: Optional[pd.DataFrame] = None,
               pa_sem_df: Optional[pd.DataFrame] = None,
               pa_mes_df: Optional[pd.DataFrame] = None,
               pa_ano_df: Optional[pd.DataFrame] = None) -> None:
    import base64
    os.makedirs(out_dir, exist_ok=True)
    dt_fmt = pd.to_datetime(dt).strftime("%d/%m/%Y")

    logo_tag = ""
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as _f:
            _b64 = base64.b64encode(_f.read()).decode()
        _ext  = os.path.splitext(LOGO_PATH)[1].lstrip(".").lower()
        _mime = "image/png" if _ext == "png" else f"image/{_ext}"
        logo_tag = f'<img src="data:{_mime};base64,{_b64}" class="logo-img" alt="Itaú">'

    def fmt_cell(col: str, val) -> str:
        if col == "PL":       return _fmt_money(val)
        if col in PCT_COLS:   return _fmt_pct(val)
        if col in DU_COLS:    return _fmt_du(val)
        return _fmt_text(val)

    def build_table(df: pd.DataFrame) -> str:
        is_sp500  = "EXPOSIÇÃO S&P" in df.columns
        is_moedas = "EXPOSIÇÃO AUS" in df.columns
        is_rf     = "EXPOSIÇÃO NTN-B" in df.columns
        is_ouro   = "EXPOSIÇÃO TREASURY" in df.columns
        is_deb    = "Exposição Debêntures" in df.columns
        is_acwi   = "EXPOSIÇÃO NÃO HEDGEADA" in df.columns
        is_cdi    = "Verso A" in df.columns
        if is_sp500:
            col_list = SP500_COLS
        elif is_moedas:
            col_list = MOEDAS_COLS
        elif is_rf:
            col_list = RF_COLS
        elif is_ouro:
            col_list = OURO_COLS
        elif is_deb:
            col_list = DEB_COLS
        elif is_acwi:
            col_list = ACWI_COLS
        elif is_cdi:
            col_list = CDI_COLS
        else:
            col_list = STD_COLS
        cols = [c for c in col_list if c in df.columns]

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
                    cls = "tot-red" if fora else "tot-green"
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

    # ── Mapa fundo → categoria (planilha fundos_exposicao.xlsx) ─────────────────
    _fund_cats: Dict[str, str] = {}
    _cats_ordered: List[str] = []
    for _aba, _df_aba in abas_data.items():
        if _df_aba is not None and not _df_aba.empty and "FUNDO" in _df_aba.columns:
            for _f in _df_aba["FUNDO"].dropna().astype(str).str.strip().unique():
                if _f and _f not in _fund_cats:
                    _fund_cats[_f] = _aba
            if _aba not in _cats_ordered:
                _cats_ordered.append(_aba)

    # ── Coleta fundos fora-banda em todas as abas ─────────────────────────────
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
            pid    = "pane-" + aba.replace("&", "e").replace(" ", "_")
            n      = len(grp)
            plural = "s" if n != 1 else ""
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

    def build_beta_perfil_table(df: pd.DataFrame) -> str:
        funds = list(BETA_FUNDS.keys())
        profs = list(BETA_FUNDS.values())

        th_top = '<th rowspan="2">Ativo</th>'
        for fund, prof in zip(funds, profs):
            th_top += f'<th colspan="3" style="text-align:center">{prof}</th>'

        th_bot = ""
        for fund, prof in zip(funds, profs):
            th_bot += (f'<th onclick="sortTable(this)" title="Clique para ordenar">{fund}</th>'
                       f'<th onclick="sortTable(this)" title="Clique para ordenar">Target</th>'
                       f'<th onclick="sortTable(this)" title="Clique para ordenar">Dif</th>')

        pct_rows_html = []
        for _, row in df.iterrows():
            ativo = str(row.get("ATIVO", ""))
            cells = [f'<td><strong>{ativo}</strong></td>']
            for fund, prof in zip(funds, profs):
                act = float(row.get(fund,          0) or 0)
                tgt = float(row.get(prof,          0) or 0)
                dif = float(row.get(f"DIF_{prof}", 0) or 0)
                clr = BETA_COLOR_RED if dif < -BETA_DIF_THRESHOLD else BETA_COLOR_GREEN
                sign = "+" if dif >= 0 else ""
                cells.append(f'<td style="text-align:right">{act:.2%}</td>')
                cells.append(f'<td style="text-align:right">{tgt:.2%}</td>')
                cells.append(
                    f'<td class="bold" style="background:{clr};text-align:right">'
                    f'{sign}{dif:.2%}</td>'
                )
            pct_rows_html.append(f"<tr>{''.join(cells)}</tr>")

        pct_table = (
            '<div class="tbl-wrap">'
            '<h3 style="margin:8px 0 4px;color:#0277BD">Exposição vs Target (%)</h3>'
            '<table class="exp-table">'
            f'<thead><tr>{th_top}</tr><tr>{th_bot}</tr></thead>'
            f'<tbody>{"".join(pct_rows_html)}</tbody>'
            '</table></div>'
        )

        return pct_table

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

    if beta_df is not None and not beta_df.empty:
        panes.append(
            '<div id="pane-PERFIL" class="pane">'
            '<h2 class="aba-title">PERFIL — Exposição Beta INTRAGITAU</h2>'
            f'{build_beta_perfil_table(beta_df)}</div>'
        )
        buttons.append(
            '<button class="nav-btn nav-btn-perfil" data-pane="pane-PERFIL">PERFIL</button>'
        )

    def _pnl_svg_bars(df: pd.DataFrame, col: str, fmt_fn, max_n: int = 20) -> str:
        """SVG horizontal diverging bar chart for a PnL column."""
        df2 = df[["FUNDO", col]].copy()
        df2[col] = pd.to_numeric(df2[col], errors="coerce")
        df2 = df2.dropna(subset=[col]).sort_values(col, ascending=True)
        if df2.empty:
            return ""
        if len(df2) > max_n:
            half = max_n // 2
            df2 = pd.concat([df2.head(half), df2.tail(half)]).drop_duplicates()
        df2 = df2.sort_values(col, ascending=True).reset_index(drop=True)

        BAR_H   = 26
        NAME_W  = 175
        GAP_R   = 110   # right label space
        W       = 760
        P_TOP   = 8
        P_BOT   = 8
        usable  = W - NAME_W - GAP_R
        total_h = P_TOP + len(df2) * BAR_H + P_BOT

        vals     = df2[col].tolist()
        max_abs  = max(abs(v) for v in vals) or 1
        has_neg  = any(v < 0 for v in vals)
        has_pos  = any(v > 0 for v in vals)

        if has_neg and has_pos:
            zero_x = NAME_W + usable / 2
            scale  = (usable / 2) / max_abs
        elif has_pos:
            zero_x = NAME_W
            scale  = usable / max_abs
        else:
            zero_x = NAME_W + usable
            scale  = usable / max_abs

        els = []
        for i, (_, row) in enumerate(df2.iterrows()):
            val  = float(row[col])
            yc   = P_TOP + i * BAR_H + BAR_H / 2
            ytop = P_TOP + i * BAR_H + 3
            bh   = BAR_H - 6
            clr  = "#1e7e34" if val >= 0 else "#c0392b"
            bw   = abs(val) * scale
            bx   = zero_x if val >= 0 else zero_x - bw
            name = str(row["FUNDO"])[:24]

            if i % 2 == 0:
                els.append(f'<rect x="0" y="{P_TOP + i * BAR_H}" width="{W}" height="{BAR_H}" fill="#f5f7fc"/>')

            els.append(
                f'<text x="{NAME_W - 7}" y="{yc + 4}" text-anchor="end" '
                f'font-size="11" fill="#1a1a2e" font-family="Segoe UI,Arial,sans-serif">{name}</text>'
            )
            if bw > 0:
                tip = f"{name}: {fmt_fn(val)}"
                els.append(
                    f'<rect x="{bx:.1f}" y="{ytop}" width="{bw:.1f}" height="{bh}" '
                    f'fill="{clr}" opacity="0.82" rx="2" class="svg-bar" data-tip="{tip}"/>'
                )
            # Posicionamento do label: evita sobreposição com área de nomes
            if val >= 0:
                lx, anchor, lfill = bx + bw + 5, "start", clr
            else:
                if bx > NAME_W + 44:          # espaço suficiente à esquerda
                    lx, anchor, lfill = bx - 5, "end", clr
                elif bw >= 70:                # barra larga → label dentro, branco
                    lx, anchor, lfill = bx + bw - 5, "end", "#fff"
                else:                          # barra pequena → label à direita da barra
                    lx, anchor, lfill = bx + bw + 5, "start", clr
            els.append(
                f'<text x="{lx:.1f}" y="{yc + 4}" text-anchor="{anchor}" font-size="10" '
                f'fill="{lfill}" font-weight="bold" font-family="Segoe UI,Arial,sans-serif">'
                f'{fmt_fn(val)}</text>'
            )

        els.append(
            f'<line x1="{zero_x:.1f}" y1="{P_TOP - 4}" x2="{zero_x:.1f}" '
            f'y2="{total_h - P_BOT + 4}" stroke="#aaa" stroke-width="1.2" stroke-dasharray="4,3"/>'
        )
        return (
            f'<svg viewBox="0 0 {W} {total_h}" '
            f'style="width:100%;display:block;overflow:visible">'
            + "".join(els) + "</svg>"
        )

    def build_posicoes_section(pos: pd.DataFrame) -> str:
        if pos is None or pos.empty:
            return ""
        pos = pos.copy()

        fundos_uniq = sorted(pos["FUNDO"].dropna().unique().tolist())

        # Seletor colapsável por fundo
        fund_items = (
            '<button class="fund-drop-item active" data-fundo="ALL" '
            'onclick="posSelectFund(\'ALL\',this)">Todos os Fundos</button>'
        )
        for f in fundos_uniq:
            fe = f.replace("'", "\\'")
            fund_items += (
                f'<button class="fund-drop-item" data-fundo="{f}" '
                f'onclick="posSelectFund(\'{fe}\',this)">{f}</button>'
            )

        fund_selector = (
            f'<div class="fund-collapse-wrap">'
            f'<button class="fund-collapse-btn" onclick="posToggleFundList()">'
            f'<span id="pos-fund-label">Todos os Fundos</span>'
            f'<span class="drop-arrow" id="pos-fund-arrow">&#9660;</span>'
            f'</button>'
            f'<div class="fund-collapse-panel" id="pos-fund-panel">'
            f'{fund_items}'
            f'</div></div>'
        )

        col_map = {
            "FUNDO":          "FUNDO",
            "ATIVO":          "ATIVO",
            "TICKER":         "TICKER",
            "TIPO":           "TIPO",
            "MOEDA":          "MOEDA",
            "VALOR":          "VALOR (R$)",
            "PERC_PL":        "% PL",
            "PNL_TOTAL":      "PnL Total",
            "PNL_TOTAL_PERC": "PnL %",
            "PNL_MTM":        "PnL MTM",
            "PNL_CARREGO":    "PnL Carrego",
            "PNL_CAMBIO":     "PnL Câmbio",
            "SETOR":          "SETOR",
        }
        cols    = [c for c in col_map if c in pos.columns]
        headers = [col_map[c] for c in cols]

        th_cells = "".join(
            f'<th onclick="sortTable(this)" title="Clique para ordenar">{h}</th>'
            for h in headers
        )

        rows_html = []
        for _, row in pos.iterrows():
            fundo = str(row.get("FUNDO", "")).replace('"', '&quot;')
            cells = []
            for c in cols:
                val = row.get(c, "")
                if c in ("VALOR", "PNL_TOTAL", "PNL_MTM", "PNL_CARREGO", "PNL_CAMBIO"):
                    text = _fmt_money(val)
                    try:
                        v = float(val)
                        cls = ' class="bold tot-green"' if (c != "VALOR" and v >= 0) else (
                              ' class="bold tot-red"'  if (c != "VALOR" and v <  0) else "")
                    except Exception:
                        cls = ""
                    cells.append(f'<td{cls}>{text}</td>')
                elif c in ("PERC_PL", "PNL_TOTAL_PERC"):
                    text = _fmt_pct(val)
                    try:
                        cls = ' class="bold tot-green"' if float(val) >= 0 else ' class="bold tot-red"'
                    except Exception:
                        cls = ""
                    cells.append(f'<td{cls}>{text}</td>')
                else:
                    cells.append(f'<td>{_fmt_text(val)}</td>')
            rows_html.append(f'<tr data-fundo="{fundo}">{"".join(cells)}</tr>')

        js = (
            '<script>'
            'function posToggleFundList(){'
            '  const p=document.getElementById("pos-fund-panel");'
            '  const a=document.getElementById("pos-fund-arrow");'
            '  const open=p.classList.toggle("open");'
            '  a.innerHTML=open?"&#9650;":"&#9660;";'
            '}'
            'function posSelectFund(fundo,btn){'
            '  document.querySelectorAll("#pos-fund-panel .fund-drop-item").forEach(b=>b.classList.remove("active"));'
            '  btn.classList.add("active");'
            '  document.getElementById("pos-fund-label").textContent='
            '    fundo==="ALL"?"Todos os Fundos":fundo;'
            '  document.getElementById("pos-fund-panel").classList.remove("open");'
            '  document.getElementById("pos-fund-arrow").innerHTML="&#9660;";'
            '  _posFilter(fundo);'
            '}'
            'function posFilterSearch(inp){'
            '  const ab=document.querySelector("#pos-fund-panel .fund-drop-item.active");'
            '  const fundo=ab?ab.dataset.fundo:"ALL";'
            '  _posFilter(fundo,inp.value);'
            '}'
            'function _posFilter(fundo,q){'
            '  q=(q||document.querySelector("#pos-search-box")?.value||"").toLowerCase();'
            '  document.querySelectorAll("#pos-tbody tr").forEach(row=>{'
            '    const fOk=fundo==="ALL"||row.dataset.fundo===fundo;'
            '    const tOk=!q||Array.from(row.cells).map(c=>c.textContent).join(" ").toLowerCase().includes(q);'
            '    row.style.display=(fOk&&tOk)?"":"none";'
            '  });'
            '}'
            '</script>'
        )

        return (
            f'<div class="pnl-chart-title" style="margin-top:14px">Posições por Fundo</div>'
            f'{fund_selector}'
            f'<div class="search-wrap" style="margin-top:10px">'
            f'<input id="pos-search-box" class="search-box" '
            f'placeholder="&#128269; Buscar ativo, setor, tipo..." oninput="posFilterSearch(this)">'
            f'</div>'
            f'<div class="tbl-wrap"><table class="exp-table" id="pos-table">'
            f'<thead><tr>{th_cells}</tr></thead>'
            f'<tbody id="pos-tbody">{"".join(rows_html)}</tbody>'
            f'</table></div>'
            f'{js}'
        )

    def build_despesas_section(desp: pd.DataFrame) -> str:
        if desp is None or desp.empty:
            return ""

        col_map = {
            "FUNDO":    "FUNDO",
            "DESPESA":  "DESPESA",
            "DESCRICAO":"DESCRIÇÃO",
            "VALOR":    "VALOR (R$)",
            "VALOR_CPR":"VALOR CPR (R$)",
        }
        cols    = [c for c in col_map if c in desp.columns]
        headers = [col_map[c] for c in cols]

        th_cells = "".join(
            f'<th onclick="sortTable(this)" title="Clique para ordenar">{h}</th>'
            for h in headers
        )
        rows_html = []
        for _, row in desp.iterrows():
            cells = []
            for c in cols:
                val = row.get(c, "")
                if c in ("VALOR", "VALOR_CPR"):
                    cells.append(f'<td>{_fmt_money(val)}</td>')
                else:
                    cells.append(f'<td>{_fmt_text(val)}</td>')
            rows_html.append(f"<tr>{''.join(cells)}</tr>")

        total = pd.to_numeric(desp["VALOR"], errors="coerce").sum()
        total_html = (
            f'<div style="text-align:right;margin-top:6px;font-size:.82rem;color:#555;">'
            f'Total despesas: <strong style="color:{ITAU_RED}">{_fmt_money(total)}</strong></div>'
        )

        return (
            f'<div class="pnl-chart-title" style="margin-top:36px">Despesas do Dia</div>'
            f'<div class="search-wrap" style="margin-top:10px">'
            f'<input class="search-box" placeholder="&#128269; Buscar despesa..." oninput="filterTable(this)">'
            f'</div>'
            f'<div class="tbl-wrap"><table class="exp-table">'
            f'<thead><tr>{th_cells}</tr></thead>'
            f'<tbody>{"".join(rows_html)}</tbody>'
            f'</table></div>'
            f'{total_html}'
        )

    def _build_ret_histogram(ret_vals: pd.Series) -> str:
        """SVG histograma vertical de distribuição de retornos."""
        buckets = [
            (-float("inf"), -0.02,  "< −2%",      "#7b0000"),
            (-0.02,  -0.01,         "−2% a −1%",  "#c0392b"),
            (-0.01,  -0.005,        "−1% a −0.5%","#e74c3c"),
            (-0.005,  0,            "−0.5% a 0%", "#f39c12"),
            ( 0,      0.005,        "0% a 0.5%",  "#27ae60"),
            ( 0.005,  0.01,         "0.5% a 1%",  "#1e7e34"),
            ( 0.01,   0.02,         "1% a 2%",    "#145a24"),
            ( 0.02,   float("inf"), "> 2%",        "#0a3d15"),
        ]
        clean = ret_vals.dropna()
        counts = []
        for lo, hi, label, color in buckets:
            if lo == -float("inf"):
                n = int((clean < hi).sum())
            elif hi == float("inf"):
                n = int((clean >= lo).sum())
            else:
                n = int(((clean >= lo) & (clean < hi)).sum())
            counts.append((label, n, color))

        if not any(n > 0 for _, n, _ in counts):
            return ""

        W, H     = 560, 200
        PL, PR, PT, PB = 30, 20, 24, 52
        cw       = W - PL - PR
        ch       = H - PT - PB
        nb       = len(counts)
        bw_slot  = cw / nb
        max_n    = max(n for _, n, _ in counts) or 1

        els = []
        # faixa de fundo
        els.append(f'<rect x="{PL}" y="{PT}" width="{cw}" height="{ch}" fill="#f8f9fc" rx="4"/>')
        # grade horizontal
        for k in range(1, 5):
            yg = PT + ch - (k / 4) * ch
            els.append(f'<line x1="{PL}" y1="{yg:.1f}" x2="{W-PR}" y2="{yg:.1f}" stroke="#e0e0e0" stroke-width="1"/>')

        for i, (label, n, color) in enumerate(counts):
            bh   = (n / max_n) * ch if n > 0 else 0
            bx   = PL + i * bw_slot + bw_slot * 0.12
            by   = PT + ch - bh
            bww  = bw_slot * 0.76
            cx   = PL + i * bw_slot + bw_slot / 2
            if bh > 0:
                _plural = "fundo" if n == 1 else "fundos"
                els.append(
                    f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bww:.1f}" height="{bh:.1f}" '
                    f'fill="{color}" opacity=".87" rx="3" class="svg-bar" '
                    f'data-tip="{label}: {n} {_plural}"/>'
                )
            if n > 0:
                els.append(
                    f'<text x="{cx:.1f}" y="{by - 5:.1f}" text-anchor="middle" '
                    f'font-size="11" font-weight="bold" fill="{color}" '
                    f'font-family="Segoe UI,Arial,sans-serif">{n}</text>'
                )
            angle = f"rotate(-35,{cx:.1f},{PT + ch + 14:.1f})"
            els.append(
                f'<text x="{cx:.1f}" y="{PT + ch + 14:.1f}" text-anchor="end" '
                f'font-size="9.5" fill="#555" transform="{angle}" '
                f'font-family="Segoe UI,Arial,sans-serif">{label}</text>'
            )
        els.append(
            f'<line x1="{PL}" y1="{PT+ch}" x2="{W-PR}" y2="{PT+ch}" stroke="#ccc" stroke-width="1.2"/>'
        )
        return (
            f'<div class="pnl-chart-box">'
            f'<div class="pnl-chart-title">Distribuição de Retornos</div>'
            f'<svg viewBox="0 0 {W} {H}" style="width:100%;display:block">'
            + "".join(els) + "</svg></div>"
        )

    def _build_group_bars(pos: pd.DataFrame, group_col: str,
                          val_col: str, title: str) -> str:
        """Barra horizontal de PnL agrupado por coluna (setor, tipo…)."""
        if pos is None or pos.empty:
            return ""
        if group_col not in pos.columns or val_col not in pos.columns:
            return ""
        grp = (pos.groupby(group_col, dropna=True)[val_col]
                  .sum()
                  .reset_index()
                  .rename(columns={group_col: "FUNDO"}))
        grp = grp[grp["FUNDO"].astype(str).str.strip() != ""]
        if grp.empty:
            return ""
        svg = _pnl_svg_bars(grp, val_col, _fmt_money, max_n=30)
        return (
            f'<div class="pnl-chart-box">'
            f'<div class="pnl-chart-title">{title}</div>'
            f'{svg}</div>'
        )

    def _build_waterfall_svg(components: list, values: list, total: float, show_pct: bool = False, pl: float = 0.0) -> str:
        """SVG waterfall vertical para atribuição de PnL por componente."""
        all_labels = list(components) + ["TOTAL"]
        n = len(all_labels)

        # Margem inferior maior quando há muitas barras (labels rotacionados -45°)
        W  = 760
        PB = 68 if n > 10 else 52
        H  = 260 + (PB - 52)
        PL, PR, PT = 78, 16, 20
        chart_w = W - PL - PR
        chart_h = H - PT - PB
        bar_slot = chart_w / n
        bar_w = bar_slot * 0.62
        bar_off = bar_slot * 0.19

        running = 0.0
        bar_data = []
        for label, val in zip(components, values):
            bar_data.append((label, running, running + val,
                             "#1e7e34" if val >= 0 else "#c0392b", False))
            running += val
        bar_data.append(("TOTAL", 0.0, total, ITAU_DARK, True))

        all_ys = ([s for _, s, e, _, _ in bar_data]
                  + [e for _, s, e, _, _ in bar_data]
                  + [0.0])
        y_min = min(all_ys)
        y_max = max(all_ys)
        pad = max((y_max - y_min) * 0.15, abs(total) * 0.15, 1.0)
        y_lo = y_min - pad
        y_hi = y_max + pad
        y_range = y_hi - y_lo or 1.0

        def _to_y(v: float) -> float:
            return PT + chart_h * (1.0 - (v - y_lo) / y_range)

        els = []
        els.append(
            f'<rect x="{PL}" y="{PT}" width="{chart_w}" height="{chart_h}" fill="#f8f9fc" rx="4"/>'
        )
        for k in range(5):
            frac = k / 4
            v_grid = y_lo + frac * y_range
            yg = PT + chart_h * (1 - frac)
            els.append(
                f'<line x1="{PL}" y1="{yg:.1f}" x2="{W-PR}" y2="{yg:.1f}" '
                f'stroke="#e4e8ef" stroke-width="1"/>'
            )
            els.append(
                f'<text x="{PL-5}" y="{yg+4:.1f}" text-anchor="end" font-size="9" fill="#999" '
                f'font-family="Segoe UI,Arial,sans-serif">{_fmt_money(v_grid)}</text>'
            )

        zero_y = _to_y(0.0)
        if y_lo < 0 < y_hi:
            els.append(
                f'<line x1="{PL}" y1="{zero_y:.1f}" x2="{W-PR}" y2="{zero_y:.1f}" '
                f'stroke="#aaa" stroke-width="1.4" stroke-dasharray="5,3"/>'
            )

        prev_end_y: Optional[float] = None
        for i, (label, start, end, color, is_total) in enumerate(bar_data):
            bx = PL + i * bar_slot + bar_off
            cx = bx + bar_w / 2
            y_top = _to_y(max(start, end))
            y_bot = _to_y(min(start, end))
            bh = max(y_bot - y_top, 2.0)
            val = end - start

            if prev_end_y is not None and not is_total:
                prev_right = PL + (i - 1) * bar_slot + bar_off + bar_w
                els.append(
                    f'<line x1="{prev_right:.1f}" y1="{prev_end_y:.1f}" '
                    f'x2="{bx:.1f}" y2="{prev_end_y:.1f}" '
                    f'stroke="#c8d0dc" stroke-width="1.2" stroke-dasharray="4,3"/>'
                )

            opacity = "0.88" if is_total else "0.82"
            _sign = "+" if val > 0 and not is_total else ""
            _pct_tip = ""
            if show_pct and not is_total and total != 0:
                _pv = val / abs(total) * 100
                _pct_tip = f" | {'+' if _pv > 0 else ''}{_pv:.1f}%"
            if is_total and show_pct and pl:
                _total_pct_str = f"{('+' if val > 0 else '')}{_fmt_pct(val / pl)}"
                _tip = f"TOTAL: {_total_pct_str} ({_fmt_money(val)})"
            else:
                _tip = (f"TOTAL: {_fmt_money(val)}" if is_total
                        else f"{label}: {_sign}{_fmt_money(val)}{_pct_tip} | acum.: {_fmt_money(end)}")
            els.append(
                f'<rect x="{bx:.1f}" y="{y_top:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
                f'fill="{color}" opacity="{opacity}" rx="3" class="svg-bar" data-tip="{_tip}"/>'
            )

            _many = len(bar_data) > 10
            sign = "+" if val > 0 and not is_total else ""

            if show_pct and not is_total and total != 0:
                _pv = val / abs(total) * 100
                _pct_str = f"{'+' if _pv > 0 else ''}{_pv:.1f}%"
                _fsz = "8" if _many else "9"
                label_y = y_top - 4 if val >= 0 else y_bot + 11
                els.append(
                    f'<text x="{cx:.1f}" y="{label_y:.1f}" text-anchor="middle" '
                    f'font-size="{_fsz}" font-weight="bold" fill="{color}" '
                    f'font-family="Segoe UI,Arial,sans-serif">{_pct_str}</text>'
                )
            elif is_total or (bh >= 16 and not _many):
                label_y = y_top - 5 if val >= 0 else y_bot + 13
                _total_label = (f"{('+' if val > 0 else '')}{_fmt_pct(val / pl)}"
                                if is_total and show_pct and pl
                                else f"{sign}{_fmt_money(val)}")
                els.append(
                    f'<text x="{cx:.1f}" y="{label_y:.1f}" text-anchor="middle" '
                    f'font-size="9.5" font-weight="bold" fill="{color}" '
                    f'font-family="Segoe UI,Arial,sans-serif">{_total_label}</text>'
                )

            ly = H - PB + 14
            angle = f'rotate(-45,{cx:.1f},{ly:.1f})'
            _show_xlabel = (show_pct or is_total or not _many
                            or i % max(1, len(bar_data) // 8) == 0)
            if _show_xlabel:
                els.append(
                    f'<text x="{cx:.1f}" y="{ly:.1f}" text-anchor="end" font-size="10" fill="#444" '
                    f'transform="{angle}" font-family="Segoe UI,Arial,sans-serif">{label}</text>'
                )
            prev_end_y = _to_y(end)

        return (
            f'<svg viewBox="0 0 {W} {H}" style="width:100%;display:block;overflow:visible">'
            + "".join(els) + "</svg>"
        )

    def _build_grouped_bar_svg(labels: list, vals_a: list, vals_b: list,
                               label_a: str = "PnL", label_b: str = "Benchmark",
                               fmt=None) -> str:
        """Barras agrupadas lado a lado: série A (PnL) e série B (Benchmark) por rótulo."""
        n = len(labels)
        if n == 0:
            return ""
        fmt = fmt if fmt is not None else _fmt_money

        COLOR_A_POS = "#1e7e34"
        COLOR_A_NEG = "#c0392b"
        COLOR_B     = "#4472c4"

        W  = 760
        PT = 42          # espaço para a legenda no topo
        PB = 68 if n > 10 else 52
        H  = 270 + (PB - 52)
        PL, PR = 78, 16
        chart_w = W - PL - PR
        chart_h = H - PT - PB

        slot    = chart_w / n
        bar_w   = slot * 0.36
        gap     = slot * 0.04
        grp_off = slot * 0.12   # deslocamento do grupo dentro do slot

        all_ys = list(vals_a) + list(vals_b) + [0.0]
        y_min, y_max = min(all_ys), max(all_ys)
        pad   = max((y_max - y_min) * 0.18, 1.0)
        y_lo  = y_min - pad
        y_hi  = y_max + pad
        y_rng = y_hi - y_lo or 1.0

        def _y(v): return PT + chart_h * (1.0 - (v - y_lo) / y_rng)

        els = []
        # fundo e grid
        els.append(f'<rect x="{PL}" y="{PT}" width="{chart_w}" height="{chart_h}" fill="#f8f9fc" rx="4"/>')
        for k in range(5):
            frac = k / 4
            vg   = y_lo + frac * y_rng
            yg   = PT + chart_h * (1 - frac)
            els.append(f'<line x1="{PL}" y1="{yg:.1f}" x2="{W-PR}" y2="{yg:.1f}" stroke="#e4e8ef" stroke-width="1"/>')
            els.append(f'<text x="{PL-5}" y="{yg+4:.1f}" text-anchor="end" font-size="9" fill="#999" '
                       f'font-family="Segoe UI,Arial,sans-serif">{fmt(vg)}</text>')
        zero_y = _y(0.0)
        if y_lo < 0 < y_hi:
            els.append(f'<line x1="{PL}" y1="{zero_y:.1f}" x2="{W-PR}" y2="{zero_y:.1f}" '
                       f'stroke="#aaa" stroke-width="1.4" stroke-dasharray="5,3"/>')

        # legenda
        lx = PL
        els.append(f'<rect x="{lx}" y="8" width="12" height="12" fill="{COLOR_A_POS}" rx="2"/>')
        els.append(f'<text x="{lx+15}" y="19" font-size="10" fill="#444" font-family="Segoe UI,Arial,sans-serif">{label_a} (+)</text>')
        lx2 = lx + 90
        els.append(f'<rect x="{lx2}" y="8" width="12" height="12" fill="{COLOR_A_NEG}" rx="2"/>')
        els.append(f'<text x="{lx2+15}" y="19" font-size="10" fill="#444" font-family="Segoe UI,Arial,sans-serif">{label_a} (−)</text>')
        lx3 = lx2 + 90
        els.append(f'<rect x="{lx3}" y="8" width="12" height="12" fill="{COLOR_B}" rx="2" opacity="0.75"/>')
        els.append(f'<text x="{lx3+15}" y="19" font-size="10" fill="#444" font-family="Segoe UI,Arial,sans-serif">{label_b}</text>')

        _many = n > 10
        _fsz  = "8" if _many else "9"

        for i, (lbl, va, vb) in enumerate(zip(labels, vals_a, vals_b)):
            bx_a = PL + i * slot + grp_off
            bx_b = bx_a + bar_w + gap
            cx_a = bx_a + bar_w / 2
            cx_b = bx_b + bar_w / 2
            cx_m = (bx_a + bx_b + bar_w) / 2   # centro do grupo para label X

            col_a = COLOR_A_POS if va >= 0 else COLOR_A_NEG

            # barra A (PnL)
            ya_top = _y(max(va, 0.0))
            ya_bot = _y(min(va, 0.0))
            bh_a   = max(ya_bot - ya_top, 2.0)
            sign_a = "+" if va > 0 else ""
            tip_a  = f"{lbl} PnL: {sign_a}{fmt(va)}"
            els.append(f'<rect x="{bx_a:.1f}" y="{ya_top:.1f}" width="{bar_w:.1f}" height="{bh_a:.1f}" '
                       f'fill="{col_a}" opacity="0.85" rx="2" class="svg-bar" data-tip="{tip_a}"/>')
            ly_a = ya_top - 4 if va >= 0 else ya_bot + 11
            els.append(f'<text x="{cx_a:.1f}" y="{ly_a:.1f}" text-anchor="middle" '
                       f'font-size="{_fsz}" font-weight="bold" fill="{col_a}" '
                       f'font-family="Segoe UI,Arial,sans-serif">{sign_a}{fmt(va)}</text>')

            # barra B (Benchmark)
            yb_top = _y(max(vb, 0.0))
            yb_bot = _y(min(vb, 0.0))
            bh_b   = max(yb_bot - yb_top, 2.0)
            sign_b = "+" if vb > 0 else ""
            tip_b  = f"{lbl} Benchmark: {sign_b}{fmt(vb)}"
            els.append(f'<rect x="{bx_b:.1f}" y="{yb_top:.1f}" width="{bar_w:.1f}" height="{bh_b:.1f}" '
                       f'fill="{COLOR_B}" opacity="0.75" rx="2" class="svg-bar" data-tip="{tip_b}"/>')
            ly_b = yb_top - 4 if vb >= 0 else yb_bot + 11
            els.append(f'<text x="{cx_b:.1f}" y="{ly_b:.1f}" text-anchor="middle" '
                       f'font-size="{_fsz}" fill="{COLOR_B}" '
                       f'font-family="Segoe UI,Arial,sans-serif">{sign_b}{fmt(vb)}</text>')

            # label eixo X centralizado no grupo
            ly_x  = H - PB + 14
            angle = f'rotate(-45,{cx_m:.1f},{ly_x:.1f})'
            els.append(f'<text x="{cx_m:.1f}" y="{ly_x:.1f}" text-anchor="end" font-size="10" fill="#444" '
                       f'transform="{angle}" font-family="Segoe UI,Arial,sans-serif">{lbl}</text>')

        return (f'<svg viewBox="0 0 {W} {H}" style="width:100%;display:block;overflow:visible">'
                + "".join(els) + "</svg>")

    def _build_setor_fator_list(fund_df: pd.DataFrame, group_col: str,
                                 title: str, uid_prefix: str) -> str:
        """Lista colapsável de PnL agrupado por setor ou fator, com top posições."""
        pnl_col = "PNL_TOTAL"
        if group_col not in fund_df.columns or pnl_col not in fund_df.columns:
            return ""

        fdf = fund_df.copy()
        fdf["_grp"] = fdf[group_col].fillna("—").astype(str).str.strip()
        fdf["_grp"] = fdf["_grp"].replace("", "—")
        fdf["_pnl"] = pd.to_numeric(fdf[pnl_col], errors="coerce").fillna(0.0)

        agg = fdf.groupby("_grp", dropna=False)["_pnl"].sum().reset_index()
        agg = agg.sort_values("_pnl", ascending=True)
        if agg.empty:
            return ""

        rows = []
        for idx, grow in agg.iterrows():
            group_name = str(grow["_grp"])
            group_total = float(grow["_pnl"])
            color = "#1e7e34" if group_total >= 0 else "#c0392b"
            sign = "+" if group_total >= 0 else ""

            sub = fdf[fdf["_grp"] == group_name].copy()
            sub = sub.reindex(sub["_pnl"].abs().sort_values(ascending=False).index).head(6)

            pos_rows = []
            for _, prow in sub.iterrows():
                ativo = str(prow.get("ATIVO", prow.get("TICKER", ""))).strip()[:24]
                pnl_v = float(prow["_pnl"])
                pc = "#1e7e34" if pnl_v >= 0 else "#c0392b"
                ps = "+" if pnl_v >= 0 else ""
                pos_rows.append(
                    f'<div class="wf-pos-row">'
                    f'<span class="wf-pos-name">{ativo}</span>'
                    f'<span class="wf-pos-val" style="color:{pc}">{ps}{_fmt_money(pnl_v)}</span>'
                    f'</div>'
                )

            grp_id = f"{uid_prefix}-{idx}"
            rows.append(
                f'<div class="wf-group-item">'
                f'<div class="wf-group-header" onclick="wfToggleGroup(\'{grp_id}\')">'
                f'<span class="wf-group-name">{group_name}</span>'
                f'<span class="wf-group-total" style="color:{color}">{sign}{_fmt_money(group_total)}</span>'
                f'</div>'
                f'<div class="wf-group-body" id="{grp_id}">{"".join(pos_rows)}</div>'
                f'</div>'
            )

        return (
            f'<div class="wf-breakdown-col">'
            f'<div class="wf-breakdown-title">{title}</div>'
            f'{"".join(rows)}'
            f'</div>'
        )

    def _build_waterfall_per_fund_section(pa: pd.DataFrame) -> str:
        """Seção de waterfall por fundo + listas setor/fator para a aba ATRIBUIÇÃO."""
        if pa is None or pa.empty:
            return ""

        comp_map = [
            ("MTM",          "PNL_MTM"),
            ("Carrego",      "PNL_CARREGO"),
            ("Spread",       "PNL_SPREAD"),
            ("FX (Câmbio)",  "PNL_CAMBIO"),
            ("Aluguel",      "PNL_ALUGUEL"),
            ("Operações",    "PNL_OPERACAO"),
        ]

        fundos_uniq = sorted(pa["FUNDO"].dropna().unique().tolist())
        if not fundos_uniq:
            return ""

        def _safe_id(s: str) -> str:
            import re
            return re.sub(r"[^a-zA-Z0-9]", "_", s)

        btns = (
            '<button class="wf-fund-btn active" data-wffund="ALL" '
            'onclick="wfSelectFund(\'ALL\',this)">Todos os Fundos</button>'
        )
        for f in fundos_uniq:
            fe = f.replace("'", "\\'")
            fid = _safe_id(f)
            btns += (
                f'<button class="wf-fund-btn" data-wffund="{fid}" '
                f'onclick="wfSelectFund(\'{fe}\',this)">{f}</button>'
            )

        fund_sections = []
        for f in fundos_uniq:
            fdf = pa[pa["FUNDO"] == f]
            fid = _safe_id(f)

            components, values = [], []
            for label, col in comp_map:
                if col in fdf.columns:
                    v = pd.to_numeric(fdf[col], errors="coerce").sum()
                    if not pd.isna(v) and v != 0:
                        components.append(label)
                        values.append(float(v))

            total = float(pd.to_numeric(fdf["PNL_TOTAL"], errors="coerce").sum())

            wf_html = ""
            if components:
                svg = _build_waterfall_svg(components, values, total)
                wf_html = (
                    f'<div class="pnl-chart-box" style="margin-bottom:18px">'
                    f'<div class="pnl-chart-title">Waterfall de Atribuição — {f}</div>'
                    f'{svg}</div>'
                )

            setor_html = _build_setor_fator_list(fdf, "SETOR",       "PnL por Setor",           f"wfs-{fid}")
            fator_html = _build_setor_fator_list(fdf, "FATOR_RISCO", "PnL por Fator de Risco",  f"wff-{fid}")
            breakdown_html = ""
            if setor_html or fator_html:
                breakdown_html = f'<div class="wf-breakdown-row">{setor_html}{fator_html}</div>'

            fund_sections.append(
                f'<div class="wf-fund-section" id="wf-section-{fid}" data-wffund="{fid}">'
                f'{wf_html}'
                f'{breakdown_html}'
                f'</div>'
            )

        js = (
            '<script>'
            'function wfSelectFund(fund,btn){'
            '  document.querySelectorAll(".wf-fund-btn").forEach(b=>b.classList.remove("active"));'
            '  btn.classList.add("active");'
            '  const secs=document.querySelectorAll(".wf-fund-section");'
            '  if(fund==="ALL"){secs.forEach(s=>s.style.display="");}'
            '  else{'
            '    const fid=fund.replace(/[^a-zA-Z0-9]/g,"_");'
            '    secs.forEach(s=>s.style.display=s.dataset.wffund===fid?"":"none");'
            '  }'
            '}'
            'function wfToggleGroup(id){'
            '  const el=document.getElementById(id);'
            '  if(el)el.classList.toggle("open");'
            '}'
            '</script>'
        )

        return (
            f'<div class="wf-section-title">Atribuição por Fundo — Waterfall</div>'
            f'<div class="wf-fund-selector">{btns}</div>'
            f'{"".join(fund_sections)}'
            f'{js}'
        )

    def build_attribution_pane(pa: pd.DataFrame) -> str:
        if pa is None or pa.empty:
            return '<p style="padding:20px;color:#888;">Sem dados de atribuição para esta data.</p>'

        import re as _re

        def _safe_id(s: str) -> str:
            return _re.sub(r"[^a-zA-Z0-9]", "_", s)

        # Data de referência
        data_ref = ""
        if "DATA_REF" in pa.columns and not pa["DATA_REF"].dropna().empty:
            raw = str(pa["DATA_REF"].dropna().iloc[0])[:10]
            try:
                data_ref = pd.to_datetime(raw).strftime("%d/%m/%Y")
            except Exception:
                data_ref = raw
        data_ref_html = (
            f'<div style="margin-bottom:16px;font-size:.82rem;color:{ITAU_GRAY2};'
            f'font-style:italic;">Dados de atribuição referentes a: '
            f'<strong style="color:{ITAU_DARK}">{data_ref}</strong></div>'
        ) if data_ref else ""

        def _c(v):
            return "#1e7e34" if (not pd.isna(v) and float(v) >= 0) else "#c0392b"

        def _card(title: str, value: str, color: str, sub: str = "") -> str:
            sub_html = f'<div class="pnl-card-sub">{sub}</div>' if sub else ""
            return (
                f'<div class="pnl-card">'
                f'<div class="pnl-card-title">{title}</div>'
                f'<div class="pnl-card-value" style="color:{color}">{value}</div>'
                f'{sub_html}</div>'
            )

        comp_cols = [
            ("MTM",         "PNL_MTM"),
            ("Carrego",     "PNL_CARREGO"),
            ("Spread",      "PNL_SPREAD"),
            ("FX (Câmbio)", "PNL_CAMBIO"),
            ("Aluguel",     "PNL_ALUGUEL"),
            ("Operações",   "PNL_OPERACAO"),
        ]

        def _build_grouped_table(vdf: pd.DataFrame, vid: str) -> str:
            """Tabela de resumo agrupado por TIPO / SETOR / GRUPO / FATOR."""
            money_map = [
                ("PNL_TOTAL",    "PnL Total"),
                ("PNL_MTM",      "MTM"),
                ("PNL_CARREGO",  "Carrego"),
                ("PNL_SPREAD",   "Spread"),
                ("PNL_CAMBIO",   "FX"),
                ("PNL_ALUGUEL",  "Aluguel"),
                ("PNL_OPERACAO", "Operações"),
                ("BENCH_PNL",    "Benchmark"),
            ]
            agg_cols  = [c for c, _ in money_map if c in vdf.columns]
            agg_lbls  = [l for c, l in money_map if c in vdf.columns]

            dims = [
                ("TIPO",  "Tipo",           "TIPO"),
                ("SETOR", "Setor",          "SETOR"),
                ("GRUPO", "Grupo",          "GRUPO_PNL"),
                ("FATOR", "Fator de Risco", "FATOR_RISCO"),
            ]

            def _make_table(dim_col: str, dim_label: str) -> str:
                if dim_col not in vdf.columns or not agg_cols:
                    return '<p style="padding:12px;color:#888;font-size:.82rem;">Sem dados.</p>'

                tmp = vdf.copy()
                tmp[dim_col] = (tmp[dim_col].fillna("—").astype(str)
                                            .str.strip().replace("", "—"))
                grp = (tmp.groupby(dim_col, dropna=False)[agg_cols]
                          .sum()
                          .reset_index()
                          .sort_values("PNL_TOTAL", ascending=True))

                th = (
                    f'<th onclick="sortTable(this)">{dim_label}</th>'
                    + "".join(
                        f'<th onclick="sortTable(this)" title="Clique para ordenar">{lbl}</th>'
                        for lbl in agg_lbls
                    )
                )

                def _tr(row, is_total=False):
                    name = str(row[dim_col])
                    bd = ' class="bold"' if is_total else ""
                    cells = [f'<td{bd}>{name}</td>']
                    for c in agg_cols:
                        v = float(row.get(c, 0) or 0)
                        clr = "tot-green" if v >= 0 else "tot-red"
                        cls = f' class="bold {clr}"' if is_total else (
                              f' class="{clr}"' if v != 0 else "")
                        cells.append(f'<td{cls}>{_fmt_money(v)}</td>')
                    bg = ' style="background:#e8eaf6"' if is_total else ""
                    return f'<tr{bg}>{"".join(cells)}</tr>'

                rows = [_tr(r) for _, r in grp.iterrows()]
                total_s = pd.Series({dim_col: "TOTAL",
                                     **{c: pd.to_numeric(grp[c], errors="coerce").sum()
                                        for c in agg_cols}})
                rows.append(_tr(total_s, is_total=True))

                return (
                    '<div class="tbl-wrap">'
                    '<table class="exp-table">'
                    f'<thead><tr>{th}</tr></thead>'
                    f'<tbody>{"".join(rows)}</tbody>'
                    '</table></div>'
                )

            tabs_html  = ""
            panes_html = ""
            for i, (key, label, col) in enumerate(dims):
                active = " active" if i == 0 else ""
                tabs_html += (
                    f'<button class="grp-tab-btn{active}" '
                    f'onclick="grpTab(\'{key}\',\'{vid}\',this)">{label}</button>'
                )
                display = "" if i == 0 else ' style="display:none"'
                panes_html += (
                    f'<div id="grp-pane-{key}-{vid}" class="grp-pane"{display}>'
                    f'{_make_table(col, label)}'
                    f'</div>'
                )

            return (
                f'<div class="wf-section-title" style="margin-top:28px">Resumo Agrupado</div>'
                f'<div class="grp-tab-nav" id="grp-nav-{vid}">{tabs_html}</div>'
                f'{panes_html}'
            )

        def _build_view(vdf: pd.DataFrame, vid: str) -> str:
            """Cards + gráficos + waterfall + setor/fator para um subconjunto de fundos."""
            total     = pd.to_numeric(vdf["PNL_TOTAL"],    errors="coerce").sum()
            t_mtm     = pd.to_numeric(vdf["PNL_MTM"],      errors="coerce").sum() if "PNL_MTM"      in vdf.columns else float("nan")
            t_carr    = pd.to_numeric(vdf["PNL_CARREGO"],  errors="coerce").sum() if "PNL_CARREGO"  in vdf.columns else float("nan")
            t_sprd    = pd.to_numeric(vdf["PNL_SPREAD"],   errors="coerce").sum() if "PNL_SPREAD"   in vdf.columns else float("nan")
            t_fx      = pd.to_numeric(vdf["PNL_CAMBIO"],   errors="coerce").sum() if "PNL_CAMBIO"   in vdf.columns else float("nan")
            t_alug    = pd.to_numeric(vdf["PNL_ALUGUEL"],  errors="coerce").sum() if "PNL_ALUGUEL"  in vdf.columns else float("nan")
            t_op      = pd.to_numeric(vdf["PNL_OPERACAO"], errors="coerce").sum() if "PNL_OPERACAO" in vdf.columns else float("nan")
            bench_tot = pd.to_numeric(vdf["BENCH_PNL"],    errors="coerce").sum() if "BENCH_PNL"    in vdf.columns else float("nan")
            alpha_tot = float(total) - (float(bench_tot) if not pd.isna(bench_tot) else 0.0)

            cards = f'<div class="pnl-cards">' + "".join([
                _card("PnL Total",   _fmt_money(total),      _c(total)),
                _card("Benchmark",   _fmt_money(bench_tot),  _c(bench_tot)),
                _card("Alpha",       _fmt_money(alpha_tot),  _c(alpha_tot)),
                _card("MTM",         _fmt_money(t_mtm),      _c(t_mtm)),
                _card("Carrego",     _fmt_money(t_carr),     _c(t_carr)),
                _card("Spread",      _fmt_money(t_sprd),     _c(t_sprd)),
                _card("FX (Câmbio)", _fmt_money(t_fx),       _c(t_fx)),
                _card("Aluguel",     _fmt_money(t_alug),     _c(t_alug)),
                _card("Operações",   _fmt_money(t_op),       _c(t_op)),
            ]) + "</div>"

            # Waterfall 1: decomposição por componente
            comp_comps, comp_vals = [], []
            for label, val in [
                ("MTM",         t_mtm),
                ("Carrego",     t_carr),
                ("Spread",      t_sprd),
                ("FX (Câmbio)", t_fx),
                ("Aluguel",     t_alug),
                ("Operações",   t_op),
            ]:
                if not pd.isna(val) and val != 0:
                    comp_comps.append(label)
                    comp_vals.append(float(val))
            comp_svg = (
                _build_waterfall_svg(comp_comps, comp_vals, float(total))
                if comp_comps else ""
            )

            # Waterfall 2: alpha por fundo (ordem ascendente → barra total)
            if "BENCH_PNL" in vdf.columns:
                alpha_df = (
                    vdf.groupby("FUNDO", dropna=True)[["PNL_TOTAL", "BENCH_PNL"]]
                    .sum().reset_index()
                )
                alpha_df["ALPHA"] = alpha_df["PNL_TOTAL"] - alpha_df["BENCH_PNL"].fillna(0)
            else:
                alpha_df = vdf.groupby("FUNDO", dropna=True)[["PNL_TOTAL"]].sum().reset_index()
                alpha_df["ALPHA"] = alpha_df["PNL_TOTAL"]
            alpha_df = alpha_df.sort_values("ALPHA", ascending=True).reset_index(drop=True)
            alpha_comps = alpha_df["FUNDO"].tolist()
            alpha_vals  = [float(v) for v in alpha_df["ALPHA"].tolist()]
            alpha_total = float(sum(alpha_vals))
            alpha_svg = (
                _build_waterfall_svg(alpha_comps, alpha_vals, alpha_total)
                if alpha_comps else ""
            )

            row1 = (
                '<div class="pnl-charts-row">'
                f'<div class="pnl-chart-box"><div class="pnl-chart-title">Decomposição PnL por Componente</div>{comp_svg}</div>'
                f'<div class="pnl-chart-box"><div class="pnl-chart-title">Alpha vs Benchmark por Fundo</div>{alpha_svg}</div>'
                '</div>'
            )

            g_grupo = _build_group_bars(vdf, "GRUPO_PNL",   "PNL_TOTAL", "PnL por Grupo")
            g_setor = _build_group_bars(vdf, "SETOR",       "PNL_TOTAL", "PnL por Setor")
            g_fator = _build_group_bars(vdf, "FATOR_RISCO", "PNL_TOTAL", "PnL por Fator de Risco")
            g_mesa  = _build_group_bars(vdf, "MESA",        "PNL_TOTAL", "PnL por Mesa de Gestão")
            row2 = (
                '<div class="pnl-charts-row">'
                + (g_grupo or "") + (g_setor or "")
                + '</div>'
                + '<div class="pnl-charts-row">'
                + (g_fator or "") + (g_mesa or "")
                + '</div>'
            )

            # Listas setor/fator colapsáveis
            setor_html = _build_setor_fator_list(vdf, "SETOR",       "PnL por Setor",          f"wfs-{vid}")
            fator_html = _build_setor_fator_list(vdf, "FATOR_RISCO", "PnL por Fator de Risco", f"wff-{vid}")
            breakdown_html = ""
            if setor_html or fator_html:
                breakdown_html = f'<div class="wf-breakdown-row">{setor_html}{fator_html}</div>'

            grouped_tbl = _build_grouped_table(vdf, vid)
            return cards + row1 + row2 + breakdown_html + grouped_tbl

        # Seletor hierárquico: ALL + categoria + fundo
        fundos_uniq = sorted(pa["FUNDO"].dropna().unique().tolist())

        # Agrupa os fundos presentes em pa por categoria
        cats_in_pa: Dict[str, List[str]] = {}
        for f in fundos_uniq:
            cat = _fund_cats.get(f, "Outros")
            cats_in_pa.setdefault(cat, []).append(f)

        # Vistas: ALL + uma por categoria + uma por fundo individual
        views = [("ALL", pa)]
        for cat in _cats_ordered:
            if cat not in cats_in_pa:
                continue
            cat_vid = "CAT_" + _safe_id(cat)
            cat_df  = pa[pa["FUNDO"].isin(cats_in_pa[cat])]
            views.append((cat_vid, cat_df))
        for f in fundos_uniq:
            views.append((_safe_id(f), pa[pa["FUNDO"] == f]))
        # Categoria "Outros" se houver fundos sem mapeamento
        if "Outros" in cats_in_pa:
            outros_df = pa[pa["FUNDO"].isin(cats_in_pa["Outros"])]
            views.append(("CAT_Outros", outros_df))

        # ── Estilos inline para pills de categoria (igual ao BATIMENTO) ─────────
        _B  = ('display:inline-block;margin:3px 4px;padding:5px 14px;border-radius:20px;'
               'border:1.5px solid #ccc;background:#fff;font-size:.8rem;cursor:pointer;'
               'font-family:inherit;font-weight:600;transition:all .12s;')
        _BA = f'background:{ITAU_ORANGE};color:#fff;border-color:{ITAU_ORANGE};'
        _BI = f'color:{ITAU_DARK};'

        # Nível 1 — pills de categoria
        ordered_cats_pa = [c for c in _cats_ordered if c in cats_in_pa]
        if "Outros" in cats_in_pa:
            ordered_cats_pa.append("Outros")

        cat_bar = f'<div id="atrib-cat-bar" style="margin:10px 0 6px">'
        cat_bar += (
            f'<button data-atribcat="" data-atribfund="ALL" data-atriblabel="Todos os Fundos"'
            f' style="{_B}{_BA}" onclick="atribCatSel(this)">TODOS</button>'
        )
        for cat in ordered_cats_pa:
            cat_vid = "CAT_" + _safe_id(cat)
            n_funds = len(cats_in_pa[cat])
            cat_bar += (
                f'<button data-atribcat="{cat}" data-atribfund="{cat_vid}"'
                f' data-atriblabel="{cat}" style="{_B}{_BI}"'
                f' onclick="atribCatSel(this)">{cat} ({n_funds})</button>'
            )
        cat_bar += '</div>'

        # Nível 2 — dropdown de fundo por categoria
        fund_bar = '<div id="atrib-fund-bar" style="margin:4px 0 14px">'
        fund_bar += '<div data-atribcatfunds="" style="display:block"></div>'
        for cat in ordered_cats_pa:
            fund_bar += f'<div data-atribcatfunds="{cat}" style="display:none">'
            fund_bar += (
                f'<div class="fund-collapse-wrap" style="margin:0">'
                f'<button class="fund-collapse-btn" onclick="atribFundDropToggle(this)">'
                f'<span data-atrib-lbl>Selecionar Fundo</span>'
                f'<span class="drop-arrow">&#9660;</span>'
                f'</button>'
                f'<div class="fund-collapse-panel">'
            )
            for f in cats_in_pa[cat]:
                fid = _safe_id(f)
                fund_bar += (
                    f'<button class="fund-drop-item" data-atribfund="{fid}"'
                    f' data-atriblabel="{f}" onclick="atribSelectFund(this)">{f}</button>'
                )
            fund_bar += '</div></div></div>'
        fund_bar += '</div>'

        fund_selector = cat_bar + fund_bar

        # Seções pré-renderizadas por fundo (show/hide via JS)
        view_sections = ""
        for i, (vid, vdf) in enumerate(views):
            display = "" if i == 0 else ' style="display:none"'
            view_sections += (
                f'<div id="atrib-view-{vid}" class="atrib-view"{display}>'
                f'{_build_view(vdf, vid)}'
                f'</div>'
            )

        # ── Tabela detalhada por ativo ───────────────────────────────────────
        col_map = {
            "FUNDO":        "FUNDO",
            "ATIVO":        "ATIVO",
            "TICKER":       "TICKER",
            "TIPO":         "TIPO",
            "SETOR":        "SETOR",
            "GRUPO_PNL":    "GRUPO",
            "FATOR_RISCO":  "FATOR",
            "MOEDA":        "MOEDA",
            "PERC_PL":      "% PL",
            "PNL_TOTAL":    "PnL Total",
            "PNL_MTM":      "MTM",
            "PNL_CARREGO":  "Carrego",
            "PNL_SPREAD":   "Spread",
            "PNL_CAMBIO":   "FX",
            "PNL_ALUGUEL":  "Aluguel",
            "PNL_OPERACAO": "Operações",
            "BENCH_PNL":    "Benchmark",
        }
        cols    = [c for c in col_map if c in pa.columns]
        headers = [col_map[c] for c in cols]
        th_cells = "".join(
            f'<th onclick="sortTable(this)" title="Clique para ordenar">{h}</th>'
            for h in headers
        )

        # Mapeamento de colunas monetárias → chave data-*
        money_dattr = [
            ("PNL_TOTAL",    "pnl"),
            ("PNL_MTM",      "mtm"),
            ("PNL_CARREGO",  "carrego"),
            ("PNL_SPREAD",   "sprd"),
            ("PNL_CAMBIO",   "fx"),
            ("PNL_ALUGUEL",  "alug"),
            ("PNL_OPERACAO", "op"),
            ("BENCH_PNL",    "bench"),
        ]
        money_cols    = {c for c, _ in money_dattr}
        present_flags = [c in pa.columns for c, _ in money_dattr]
        present_js    = str(present_flags).lower()          # [true,false,...] para JS
        agg_headers   = [lbl for c, lbl in [               # cabeçalhos da tabela agregada
            ("PNL_TOTAL","PnL Total"),("PNL_MTM","MTM"),
            ("PNL_CARREGO","Carrego"),("PNL_SPREAD","Spread"),
            ("PNL_CAMBIO","FX"),("PNL_ALUGUEL","Aluguel"),
            ("PNL_OPERACAO","Operações"),("BENCH_PNL","Benchmark"),
        ] if c in pa.columns]
        agg_th = (
            '<th id="atrib-agg-dim-hdr" onclick="sortTable(this)">—</th>'
            + "".join(f'<th onclick="sortTable(this)">{h}</th>' for h in agg_headers)
        )

        def _da(v):
            return str(v).replace('"', '').replace("'", '').strip()[:50]

        def _dn(v):
            try:
                return str(float(pd.to_numeric(v, errors="coerce") or 0))
            except Exception:
                return "0"

        rows_html = []
        for _, row in pa.iterrows():
            fundo_raw  = str(row.get("FUNDO", ""))
            fundo_attr = fundo_raw.replace('"', '&quot;')
            row_cat    = _fund_cats.get(fundo_raw.strip(), "")
            dattrs = (
                f'data-fundo="{fundo_attr}" '
                f'data-cat="{row_cat}" '
                f'data-ativo="{_da(row.get("ATIVO",""))}" '
                f'data-ticker="{_da(row.get("TICKER",""))}" '
                f'data-tipo="{_da(row.get("TIPO",""))}" '
                f'data-setor="{_da(row.get("SETOR",""))}" '
                f'data-grupo="{_da(row.get("GRUPO_PNL",""))}" '
                f'data-fator="{_da(row.get("FATOR_RISCO",""))}" '
                + " ".join(
                    f'data-{key}="{_dn(row.get(col,0))}"'
                    for col, key in money_dattr
                )
            )
            cells = []
            for c in cols:
                val = row.get(c, "")
                if c in money_cols:
                    text = _fmt_money(val)
                    try:
                        cls = ' class="bold tot-green"' if float(val) >= 0 else ' class="bold tot-red"'
                    except Exception:
                        cls = ""
                    cells.append(f'<td{cls}>{text}</td>')
                elif c == "PERC_PL":
                    cells.append(f'<td>{_fmt_pct(val)}</td>')
                else:
                    cells.append(f'<td>{_fmt_text(val)}</td>')
            rows_html.append(f'<tr {dattrs}>{"".join(cells)}</tr>')

        grpby_btns = (
            '<button class="grp-by-btn active" onclick="atribGroupBy(\'NONE\',this)">Nenhum</button>'
            '<button class="grp-by-btn" onclick="atribGroupBy(\'ativo\',this)">Ativo</button>'
            '<button class="grp-by-btn" onclick="atribGroupBy(\'ticker\',this)">Ticker</button>'
            '<button class="grp-by-btn" onclick="atribGroupBy(\'tipo\',this)">Tipo</button>'
            '<button class="grp-by-btn" onclick="atribGroupBy(\'setor\',this)">Setor</button>'
            '<button class="grp-by-btn" onclick="atribGroupBy(\'grupo\',this)">Grupo</button>'
            '<button class="grp-by-btn" onclick="atribGroupBy(\'fator\',this)">Fator</button>'
        )

        table_html = (
            f'<div class="pnl-chart-title" style="margin-top:24px">Detalhe por Ativo</div>'
            f'<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:8px;margin-bottom:6px">'
            f'<div class="search-wrap" style="margin:0;flex:1;min-width:180px">'
            f'<input id="atrib-search" class="search-box" '
            f'placeholder="&#128269; Buscar ativo, setor, grupo, fator..." '
            f'oninput="atribSearch(this)">'
            f'</div>'
            f'<div class="grp-by-row" style="margin:0">'
            f'<span class="grp-by-label">Agrupar por:</span>'
            f'{grpby_btns}'
            f'</div>'
            f'</div>'
            # Tabela raw
            f'<div id="atrib-raw-wrap">'
            f'<div class="tbl-wrap"><table class="exp-table">'
            f'<thead><tr>{th_cells}</tr></thead>'
            f'<tbody id="atrib-tbody">{"".join(rows_html)}</tbody>'
            f'</table></div></div>'
            # Tabela agregada (JS popula o tbody)
            f'<div id="atrib-agg-wrap" style="display:none">'
            f'<div class="tbl-wrap"><table class="exp-table" id="atrib-agg-table">'
            f'<thead><tr>{agg_th}</tr></thead>'
            f'<tbody id="atrib-agg-tbody"></tbody>'
            f'</table></div></div>'
        )

        js = (
            '<script>'
            'function grpTab(dim,vid,btn){'
            '  const nav=document.getElementById("grp-nav-"+vid);'
            '  if(nav)nav.querySelectorAll(".grp-tab-btn").forEach(b=>b.classList.remove("active"));'
            '  btn.classList.add("active");'
            '  ["TIPO","SETOR","GRUPO","FATOR"].forEach(d=>{'
            '    const p=document.getElementById("grp-pane-"+d+"-"+vid);'
            '    if(p)p.style.display=d===dim?"":"none";'
            '  });'
            '}'
            f'var _atribMoneyKeys=["pnl","mtm","carrego","sprd","fx","alug","op","bench"];'
            f'var _atribMoneyPresent={present_js};'
            f'var _atribMoneyLabels={str(agg_headers)};'
            'var _atribFund="ALL";'   # vid atual
            'var _atribCat="";'       # categoria atual ("" = filtro por fundo individual)
            'var _atribGroupBy="NONE";'
            'function _fmtBRL(v){'
            '  const s=Math.abs(v)>=1e6'
            '    ?(v/1e6).toLocaleString("pt-BR",{minimumFractionDigits:2,maximumFractionDigits:2})+" M"'
            '    :v.toLocaleString("pt-BR",{minimumFractionDigits:2,maximumFractionDigits:2});'
            '  return "R$ "+s;'
            '}'
            # Seleciona categoria (pill)
            f'var _atribB="{_B}",_atribBA="{_BA}",_atribBI="{_BI}";'
            'function atribCatSel(btn){'
            '  const cat=btn.dataset.atribcat;'
            '  const vid=btn.dataset.atribfund;'
            '  _atribFund=vid; _atribCat=cat;'
            # atualiza estilos dos pills
            '  document.querySelectorAll("#atrib-cat-bar button").forEach(b=>{'
            '    b.style.cssText=_atribB+(b===btn?_atribBA:_atribBI);'
            '  });'
            # mostra/oculta grupo de fundos da categoria
            '  document.querySelectorAll("#atrib-fund-bar [data-atribcatfunds]").forEach(d=>{'
            '    d.style.display=d.dataset.atribcatfunds===cat?"block":"none";'
            '  });'
            # fecha qualquer dropdown de fundo aberto e reseta labels
            '  document.querySelectorAll("#atrib-fund-bar .fund-collapse-panel.open").forEach(p=>{'
            '    p.classList.remove("open");'
            '    const a=p.previousElementSibling&&p.previousElementSibling.querySelector(".drop-arrow");'
            '    if(a)a.innerHTML="&#9660;";'
            '  });'
            '  document.querySelectorAll("#atrib-fund-bar [data-atrib-lbl]").forEach(s=>{'
            '    s.textContent="Selecionar Fundo";'
            '  });'
            '  document.querySelectorAll("#atrib-fund-bar .fund-drop-item.active").forEach(b=>{'
            '    b.classList.remove("active");'
            '  });'
            # mostra view da categoria (ALL ou CAT_xxx)
            '  document.querySelectorAll(".atrib-view").forEach(v=>v.style.display="none");'
            '  const el=document.getElementById("atrib-view-"+vid);'
            '  if(el)el.style.display="";'
            '  if(_atribGroupBy==="NONE"){'
            '    const q=(document.getElementById("atrib-search")||{}).value||"";'
            '    _atribFilter(vid,cat,q.toLowerCase());'
            '  } else {'
            '    _renderAtribAgg();'
            '  }'
            '}'
            # Abre/fecha dropdown de fundo
            'function atribFundDropToggle(btn){'
            '  const panel=btn.nextElementSibling;'
            '  if(!panel)return;'
            '  const open=panel.classList.toggle("open");'
            '  const arrow=btn.querySelector(".drop-arrow");'
            '  if(arrow)arrow.innerHTML=open?"&#9650;":"&#9660;";'
            '}'
            # Seleciona fundo individual dentro do dropdown
            'function atribSelectFund(btn){'
            '  const vid=btn.dataset.atribfund;'
            '  const label=btn.dataset.atriblabel||btn.textContent.trim();'
            '  _atribFund=vid; _atribCat="";'
            # marca ativo no dropdown e fecha
            '  const panel=btn.closest(".fund-collapse-panel");'
            '  if(panel){'
            '    panel.querySelectorAll(".fund-drop-item").forEach(b=>{'
            '      b.classList.toggle("active",b===btn);'
            '    });'
            '    panel.classList.remove("open");'
            '    const colBtn=panel.previousElementSibling;'
            '    if(colBtn){'
            '      const lbl=colBtn.querySelector("[data-atrib-lbl]");'
            '      if(lbl)lbl.textContent=label;'
            '      const arrow=colBtn.querySelector(".drop-arrow");'
            '      if(arrow)arrow.innerHTML="&#9660;";'
            '    }'
            '  }'
            '  document.querySelectorAll(".atrib-view").forEach(v=>v.style.display="none");'
            '  const el=document.getElementById("atrib-view-"+vid);'
            '  if(el)el.style.display="";'
            '  if(_atribGroupBy==="NONE"){'
            '    const q=(document.getElementById("atrib-search")||{}).value||"";'
            '    _atribFilter(vid,"",q.toLowerCase());'
            '  } else {'
            '    _renderAtribAgg();'
            '  }'
            '}'
            'function atribGroupBy(dim,btn){'
            '  _atribGroupBy=dim;'
            '  document.querySelectorAll(".grp-by-btn").forEach(b=>b.classList.remove("active"));'
            '  btn.classList.add("active");'
            '  if(dim==="NONE"){'
            '    document.getElementById("atrib-raw-wrap").style.display="";'
            '    document.getElementById("atrib-agg-wrap").style.display="none";'
            '    const q=(document.getElementById("atrib-search")||{}).value||"";'
            '    _atribFilter(_atribFund,_atribCat,q.toLowerCase());'
            '  } else {'
            '    document.getElementById("atrib-raw-wrap").style.display="none";'
            '    document.getElementById("atrib-agg-wrap").style.display="";'
            '    _renderAtribAgg();'
            '  }'
            '}'
            'function _renderAtribAgg(){'
            '  const dimLabels={ativo:"Ativo",ticker:"Ticker",tipo:"Tipo",'
            '    setor:"Setor",grupo:"Grupo",fator:"Fator"};'
            '  const hdr=document.getElementById("atrib-agg-dim-hdr");'
            '  if(hdr)hdr.textContent=dimLabels[_atribGroupBy]||_atribGroupBy;'
            '  const rows=Array.from(document.querySelectorAll("#atrib-tbody tr"));'
            '  const matching=rows.filter(r=>_rowMatch(r,_atribFund,_atribCat));'
            '  const map=new Map();'
            '  matching.forEach(r=>{'
            '    const key=r.dataset[_atribGroupBy]||"—";'
            '    if(!map.has(key)){const o={key};_atribMoneyKeys.forEach(k=>o[k]=0);map.set(key,o);}'
            '    const g=map.get(key);'
            '    _atribMoneyKeys.forEach(k=>g[k]+=parseFloat(r.dataset[k]||0));'
            '  });'
            '  const sorted=[...map.values()].sort((a,b)=>a.pnl-b.pnl);'
            '  const tot={key:"TOTAL"};_atribMoneyKeys.forEach(k=>tot[k]=sorted.reduce((s,r)=>s+r[k],0));'
            '  sorted.push(tot);'
            '  const tbody=document.getElementById("atrib-agg-tbody");'
            '  tbody.innerHTML=sorted.map((g,i)=>{'
            '    const isT=i===sorted.length-1;'
            '    const bold=isT?" class=\\"bold\\"":" ";'
            '    const bg=isT?" style=\\"background:#e8eaf6\\"":" ";'
            '    const cells=_atribMoneyKeys'
            '      .filter((_,idx)=>_atribMoneyPresent[idx])'
            '      .map(k=>{'
            '        const v=g[k];'
            '        const clr=v>=0?"tot-green":"tot-red";'
            '        const cls=isT?` class="bold ${clr}"`:v!==0?` class="${clr}"`:"";'
            '        return `<td${cls}>${_fmtBRL(v)}</td>`;'
            '      }).join("");'
            '    return `<tr${bg}><td${bold}>${g.key}</td>${cells}</tr>`;'
            '  }).join("");'
            '}'
            'function _rowMatch(row,vid,cat){'
            '  if(vid==="ALL")return true;'
            '  if(cat)return row.dataset.cat===cat;'
            '  return row.dataset.fundo.replace(/[^a-zA-Z0-9]/g,"_")===vid;'
            '}'
            'function atribSearch(inp){'
            '  if(_atribGroupBy!=="NONE")return;'
            '  _atribFilter(_atribFund,_atribCat,inp.value.toLowerCase());'
            '}'
            'function _atribFilter(vid,cat,q){'
            '  document.querySelectorAll("#atrib-tbody tr").forEach(row=>{'
            '    const fOk=_rowMatch(row,vid,cat);'
            '    const tOk=!q||Array.from(row.cells).map(c=>c.textContent).join(" ").toLowerCase().includes(q);'
            '    row.style.display=(fOk&&tOk)?"":"none";'
            '  });'
            '}'
            '</script>'
        )

        return data_ref_html + fund_selector + view_sections + table_html + js

    # ── Paleta de cores para gráficos de linha ────────────────────────────────
    _LINE_COLORS = [
        "#E6821E","#1565C0","#2E7D32","#C62828","#6A1B9A",
        "#00695C","#F9A825","#37474F","#AD1457","#558B2F",
        "#0277BD","#4E342E","#1a237e","#bf360c","#006064",
    ]

    def _build_svg_line_chart(chart_id: str, title: str, dates: list,
                               series: list, fmt_y, zero_line: bool = True,
                               area_fill: bool = True, chart_type: str = "generic",
                               W: int = 760, H: int = 300) -> str:
        """
        Gráfico de linha SVG interativo — curvas suaves, área gradiente, crosshair.
        series: list de dict {name, values:[float|None], color, ret_dia:[float|None]}
        """
        import json, math

        def _safe(v):
            if v is None: return None
            try:
                f = float(v)
                return None if math.isnan(f) or math.isinf(f) else f
            except Exception:
                return None

        series = [{"name": s["name"],
                   "values": [_safe(v) for v in s["values"]],
                   "ret_dia": [_safe(v) for v in s.get("ret_dia", [])],
                   "color": s["color"]} for s in series]
        series = [s for s in series if any(v is not None for v in s["values"])]
        if not dates or not series:
            return ""

        PL, PR, PT, PB = 78, 60, 22, 46
        cw = W - PL - PR
        ch = H - PT - PB
        n  = len(dates)

        all_vals = [v for s in series for v in s["values"] if v is not None]
        if not all_vals:
            return ""
        y_min, y_max = min(all_vals), max(all_vals)
        pad  = (y_max - y_min) * 0.12 or abs(y_max) * 0.12 or 0.001
        y_lo = y_min - pad
        y_hi = y_max + pad
        y_rng = y_hi - y_lo or 1.0

        # Nice ticks
        def _nice_ticks(lo, hi, n_t=6):
            rng = hi - lo or 1
            raw = rng / (n_t - 1)
            mag = 10 ** math.floor(math.log10(abs(raw))) if raw != 0 else 1
            for m in [1, 2, 2.5, 5, 10]:
                step = m * mag
                if rng / step <= n_t + 1:
                    break
            start = math.ceil(lo / step) * step
            ticks = []
            t = start
            while t <= hi + step * 0.01:
                ticks.append(round(t, 10))
                t += step
            return ticks

        ticks = _nice_ticks(y_lo, y_hi)
        y_lo  = min(y_lo, ticks[0]  if ticks else y_lo)
        y_hi  = max(y_hi, ticks[-1] if ticks else y_hi)
        y_rng = y_hi - y_lo or 1.0

        def _tx(i):  return PL + i * cw / max(n - 1, 1)
        def _ty(v):  return PT + ch * (1.0 - (v - y_lo) / y_rng)

        def _spline_path(xy_pts):
            """Catmull-Rom spline → SVG cubic bezier path."""
            if len(xy_pts) < 2:
                return ""
            parts = [f"M {xy_pts[0][0]:.1f},{xy_pts[0][1]:.1f}"]
            for i in range(1, len(xy_pts)):
                p0 = xy_pts[max(0, i - 2)]
                p1 = xy_pts[i - 1]
                p2 = xy_pts[i]
                p3 = xy_pts[min(len(xy_pts) - 1, i + 1)]
                cp1x = p1[0] + (p2[0] - p0[0]) / 6
                cp1y = p1[1] + (p2[1] - p0[1]) / 6
                cp2x = p2[0] - (p3[0] - p1[0]) / 6
                cp2y = p2[1] - (p3[1] - p1[1]) / 6
                parts.append(
                    f"C {cp1x:.1f},{cp1y:.1f} {cp2x:.1f},{cp2y:.1f} {p2[0]:.1f},{p2[1]:.1f}"
                )
            return " ".join(parts)

        els   = []
        defs  = []
        y0    = max(PT, min(PT + ch, _ty(0)))  # clamp zero line

        # Fundo e grade
        els.append(f'<rect x="{PL}" y="{PT}" width="{cw}" height="{ch}" fill="#f5f7fd" rx="5"/>')
        for t in ticks:
            yg = _ty(t)
            if PT - 2 <= yg <= PT + ch + 2:
                els.append(
                    f'<line x1="{PL}" y1="{yg:.1f}" x2="{W-PR}" y2="{yg:.1f}" '
                    f'stroke="#e2e6f0" stroke-width="1"/>'
                )
                els.append(
                    f'<text x="{PL-7}" y="{yg+4:.1f}" text-anchor="end" font-size="9" '
                    f'fill="#aaa" font-family="Segoe UI,Arial,sans-serif">{fmt_y(t)}</text>'
                )

        # Linha zero destacada
        if zero_line and y_lo < 0 < y_hi:
            els.append(
                f'<line x1="{PL}" y1="{y0:.1f}" x2="{W-PR}" y2="{y0:.1f}" '
                f'stroke="#bbb" stroke-width="1.4" stroke-dasharray="6,3"/>'
            )

        # Labels X
        show_every = max(1, n // 9)
        for i, d in enumerate(dates):
            if i % show_every == 0 or i == n - 1:
                lbl = d[5:].replace("-", "/")
                els.append(
                    f'<text x="{_tx(i):.1f}" y="{PT+ch+16}" text-anchor="middle" font-size="9" '
                    f'fill="#aaa" font-family="Segoe UI,Arial,sans-serif">{lbl}</text>'
                )

        # Gradientes SVG para área fill
        if area_fill:
            for si, s in enumerate(series):
                gid = f"{chart_id}-g{si}"
                defs.append(
                    f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
                    f'<stop offset="0%" stop-color="{s["color"]}" stop-opacity="0.22"/>'
                    f'<stop offset="85%" stop-color="{s["color"]}" stop-opacity="0.01"/>'
                    f'</linearGradient>'
                )

        # Segmentos contínuos de cada série
        for si, s in enumerate(series):
            segments: list = []
            seg: list = []
            for i, v in enumerate(s["values"]):
                if v is not None:
                    seg.append((_tx(i), _ty(v)))
                else:
                    if len(seg) > 1:
                        segments.append(seg)
                    seg = []
            if len(seg) > 1:
                segments.append(seg)

            for seg_i, seg in enumerate(segments):
                lp = _spline_path(seg)
                # Área fill (só no primeiro segmento para evitar sobreposição)
                if area_fill and lp and seg_i == 0:
                    gid = f"{chart_id}-g{si}"
                    ap  = (lp
                           + f" L {seg[-1][0]:.1f},{y0:.1f}"
                           + f" L {seg[0][0]:.1f},{y0:.1f} Z")
                    els.append(f'<path data-series-area="{si}" d="{ap}" fill="url(#{gid})" stroke="none"/>')
                # Linha suave
                if lp:
                    line_attr = f'data-series-line="{si}"' if seg_i == 0 else ""
                    els.append(
                        f'<path {line_attr} d="{lp}" fill="none" stroke="{s["color"]}" '
                        f'stroke-width="2.2" stroke-linejoin="round" opacity="0.9"/>'
                    )

            # Label do último valor (right edge)
            last_val = next((v for v in reversed(s["values"]) if v is not None), None)
            last_idx = next((len(s["values"]) - 1 - i
                             for i, v in enumerate(reversed(s["values"])) if v is not None), None)
            if last_val is not None and last_idx is not None:
                lx = _tx(last_idx) + 5
                ly = _ty(last_val)
                ly = max(PT + 8, min(PT + ch - 4, ly))
                els.append(
                    f'<text data-series-label="{si}" x="{lx:.1f}" y="{ly:.1f}" '
                    f'font-size="9.5" font-weight="bold" '
                    f'fill="{s["color"]}" font-family="Segoe UI,Arial,sans-serif" '
                    f'dominant-baseline="middle">{fmt_y(last_val)}</text>'
                )

        # Eixos
        els.append(f'<line x1="{PL}" y1="{PT}" x2="{PL}" y2="{PT+ch}" stroke="#d0d5e8" stroke-width="1.2"/>')
        els.append(f'<line x1="{PL}" y1="{PT+ch}" x2="{W-PR}" y2="{PT+ch}" stroke="#d0d5e8" stroke-width="1.2"/>')

        # Crosshair
        els.append(
            f'<line id="{chart_id}-vl" x1="0" y1="{PT}" x2="0" y2="{PT+ch}" '
            f'stroke="#666" stroke-width="1" stroke-dasharray="4,2" display="none"/>'
        )
        for i, s in enumerate(series):
            els.append(
                f'<circle id="{chart_id}-d{i}" cx="0" cy="0" r="5" '
                f'fill="{s["color"]}" stroke="#fff" stroke-width="2" display="none"/>'
            )

        # Overlay para mouse
        els.append(
            f'<rect x="{PL}" y="{PT}" width="{cw}" height="{ch}" fill="transparent" '
            f'style="cursor:crosshair" '
            f'onmousemove="lcMove(event,\'{chart_id}\')" onmouseleave="lcLeave(\'{chart_id}\')"/>'
        )

        # Legenda (abaixo do gráfico)
        leg_y = PT + ch + 28
        max_per_row = min(5, len(series))
        col_w = cw // max(max_per_row, 1)
        n_rows_leg = (len(series) + max_per_row - 1) // max_per_row
        for i, s in enumerate(series):
            lx = PL + (i % max_per_row) * col_w
            ly = leg_y + (i // max_per_row) * 15
            name_short = s["name"][:22]
            els.append(f'<rect x="{lx}" y="{ly-4}" width="14" height="3" fill="{s["color"]}" rx="2"/>')
            els.append(
                f'<text x="{lx+18}" y="{ly:.0f}" font-size="9.5" fill="#555" '
                f'font-family="Segoe UI,Arial,sans-serif">{name_short}</text>'
            )

        total_h = leg_y + n_rows_leg * 15 + 6

        fmt_type = "pct" if fmt_y == _fmt_pct else "money"
        lc_data = {
            "dates": dates, "series": series,
            "x0": PL, "cw": cw, "pt": PT, "ch": ch,
            "ylo": y_lo, "yrng": y_rng, "n": n,
            "fmt": fmt_type, "chart_type": chart_type,
        }
        import json as _json
        data_script = (
            f'<script>window["_lc_{chart_id}"]='
            + _json.dumps(lc_data, ensure_ascii=False, default=lambda x: None)
            + ';</script>'
        )

        defs_str = f'<defs>{"".join(defs)}</defs>' if defs else ""
        return (
            data_script
            + f'<svg id="{chart_id}" viewBox="0 0 {W} {total_h}" '
            f'style="width:100%;display:block;overflow:visible">'
            + defs_str + "".join(els) + "</svg>"
        )

    def _build_analise_tab(hist: Optional[pd.DataFrame]) -> str:
        """Tab ANÁLISE — gráficos de linha: retorno acumulado, evolução PL, drawdown."""
        if hist is None or hist.empty:
            return '<p style="padding:20px;color:#888;">Sem dados históricos para análise.</p>'

        import re as _re, math

        def _sid(s):
            return _re.sub(r"[^a-zA-Z0-9]", "_", s)

        hist = hist.copy()
        hist["DATA_REF"]  = pd.to_datetime(hist["DATA_REF"])
        hist["CATEGORIA"] = hist["FUNDO"].map(_fund_cats).fillna("Outros")

        all_dates = sorted(hist["DATA_REF"].dt.strftime("%Y-%m-%d").unique().tolist())
        if not all_dates:
            return '<p style="padding:20px;color:#888;">Sem datas disponíveis.</p>'

        fundos_uniq = sorted(hist["FUNDO"].dropna().unique().tolist())

        # Agregação por categoria (vista ALL)
        cat_hist = (hist.groupby(["CATEGORIA", "DATA_REF"], as_index=False)
                       .agg(PL=("PL", "sum"), RET_DIA=("RET_DIA", "mean")))
        cat_hist = cat_hist.sort_values(["CATEGORIA", "DATA_REF"])
        cat_hist["RET_ACUM"] = cat_hist.groupby("CATEGORIA")["RET_DIA"].transform(
            lambda x: (1 + x.fillna(0)).cumprod() - 1
        )
        def _dd(s):
            peak = s.cummax()
            return (s - peak) / peak.replace(0, float("nan"))
        cat_hist["DRAWDOWN"] = cat_hist.groupby("CATEGORIA")["PL"].transform(_dd)
        cats_in_hist = sorted(cat_hist["CATEGORIA"].unique().tolist())

        def _make_series(df, name_col, val_col, max_n=12):
            """Constrói lista de series alinhadas em all_dates."""
            names = df[name_col].dropna().unique().tolist()[:max_n]
            result = []
            for j, nm in enumerate(names):
                sub = df[df[name_col] == nm].sort_values("DATA_REF")
                val_map = dict(zip(
                    sub["DATA_REF"].dt.strftime("%Y-%m-%d"),
                    sub[val_col].tolist()
                ))
                result.append({
                    "name":   nm,
                    "values": [val_map.get(d) for d in all_dates],
                    "color":  _LINE_COLORS[j % len(_LINE_COLORS)],
                })
            return result

        def _trio(series_acum, series_pl, series_dd, vid):
            c1 = _build_svg_line_chart(f"ra-{vid}", "Retorno Acumulado (%)",
                                        all_dates, series_acum, _fmt_pct)
            c2 = _build_svg_line_chart(f"pl-{vid}", "Evolução do PL (R$)",
                                        all_dates, series_pl, _fmt_money, zero_line=False)
            c3 = _build_svg_line_chart(f"dd-{vid}", "Drawdown (%)",
                                        all_dates, series_dd, _fmt_pct)
            boxes = ""
            for lbl, svg in [("Retorno Acumulado (%)", c1),
                              ("Evolução do PL (R$)", c2),
                              ("Drawdown (%)", c3)]:
                if svg:
                    boxes += (f'<div class="pnl-chart-box" style="margin-bottom:20px">'
                              f'<div class="pnl-chart-title">{lbl}</div>{svg}</div>')
            return boxes

        # Vista ALL (por categoria)
        views: Dict[str, str] = {}
        s_acum = _make_series(cat_hist, "CATEGORIA", "RET_ACUM")
        s_pl   = _make_series(cat_hist, "CATEGORIA", "PL")
        s_dd   = _make_series(cat_hist, "CATEGORIA", "DRAWDOWN")
        views["ALL"] = _trio(s_acum, s_pl, s_dd, "ALL")

        # Vistas por categoria (fundos individuais)
        cats_in_pa: Dict[str, List[str]] = {}
        for f in fundos_uniq:
            cat = _fund_cats.get(f, "Outros")
            cats_in_pa.setdefault(cat, []).append(f)

        for cat in _cats_ordered + (["Outros"] if "Outros" in cats_in_pa else []):
            if cat not in cats_in_pa:
                continue
            sub = hist[hist["CATEGORIA"] == cat]
            vid = "CAT_" + _sid(cat)
            s_a = _make_series(sub, "FUNDO", "RET_ACUM")
            s_p = _make_series(sub, "FUNDO", "PL")
            s_d = _make_series(sub, "FUNDO", "DRAWDOWN")
            views[vid] = _trio(s_a, s_p, s_d, vid)

        # Vistas individuais por fundo
        for f in fundos_uniq:
            sub = hist[hist["FUNDO"] == f]
            vid = _sid(f)
            s_a = _make_series(sub, "FUNDO", "RET_ACUM", max_n=1)
            s_p = _make_series(sub, "FUNDO", "PL",       max_n=1)
            s_d = _make_series(sub, "FUNDO", "DRAWDOWN", max_n=1)
            views[vid] = _trio(s_a, s_p, s_d, vid)

        # Dropdown hierárquico (igual ao da ATRIBUIÇÃO)
        drop_items = (
            '<button class="fund-drop-item active"'
            ' data-anlfund="ALL" data-anllabel="Todos os Fundos (por categoria)"'
            ' onclick="anlSelect(this)">&#9776; Todos os Fundos</button>'
        )
        for cat in _cats_ordered + (["Outros"] if "Outros" in cats_in_pa else []):
            if cat not in cats_in_pa:
                continue
            cvid    = "CAT_" + _sid(cat)
            csafeid = _sid(cat)
            drop_items += (
                f'<div class="atrib-cat-hdr"'
                f' data-anlfund="{cvid}" data-anllabel="{cat}"'
                f' onclick="anlSelect(this)">{cat}'
                f'<button class="cat-toggle" onclick="anlToggleCat(\'{csafeid}\',event)">&#9654;</button>'
                f'</div>'
                f'<div class="atrib-cat-body" id="anl-cat-body-{csafeid}" style="display:none">'
            )
            for f in cats_in_pa[cat]:
                fid = _sid(f)
                drop_items += (
                    f'<button class="fund-drop-item atrib-sub-item"'
                    f' data-anlfund="{fid}" data-anllabel="{f}"'
                    f' onclick="anlSelect(this)">{f}</button>'
                )
            drop_items += '</div>'

        dropdown = (
            '<div class="fund-collapse-wrap" style="margin-bottom:20px">'
            '<button class="fund-collapse-btn" onclick="anlTogglePanel()">'
            '<span id="anl-fund-label">Todos os Fundos (por categoria)</span>'
            '<span class="drop-arrow" id="anl-fund-arrow">&#9660;</span>'
            '</button>'
            f'<div class="fund-collapse-panel" id="anl-fund-panel">{drop_items}</div>'
            '</div>'
        )

        # Vistas HTML
        views_html = ""
        for vid, content in views.items():
            display = "" if vid == "ALL" else ' style="display:none"'
            views_html += f'<div id="anl-view-{vid}" class="anl-view"{display}>{content}</div>'

        # Nota de período
        if all_dates:
            d0 = pd.to_datetime(all_dates[0]).strftime("%d/%m/%Y")
            d1 = pd.to_datetime(all_dates[-1]).strftime("%d/%m/%Y")
            period_note = (
                f'<div style="font-size:.75rem;color:{ITAU_GRAY2};margin-bottom:14px">'
                f'Período: <strong>{d0}</strong> → <strong>{d1}</strong>'
                f' ({len(all_dates)} datas disponíveis)</div>'
            )
        else:
            period_note = ""

        js = (
            '<script>'
            'function anlTogglePanel(){'
            '  const p=document.getElementById("anl-fund-panel");'
            '  const a=document.getElementById("anl-fund-arrow");'
            '  const open=p.classList.toggle("open");'
            '  a.innerHTML=open?"&#9650;":"&#9660;";'
            '}'
            'function anlToggleCat(sid,e){'
            '  e.stopPropagation();'
            '  const b=document.getElementById("anl-cat-body-"+sid);'
            '  if(!b)return;'
            '  const open=b.style.display==="none";'
            '  b.style.display=open?"":"none";'
            '  e.target.innerHTML=open?"&#9660;":"&#9654;";'
            '}'
            'function anlSelect(btn){'
            '  const vid=btn.dataset.anlfund;'
            '  const lbl=btn.dataset.anllabel||btn.textContent.trim();'
            '  document.querySelectorAll("#anl-fund-panel .fund-drop-item,'
            '    #anl-fund-panel .atrib-cat-hdr").forEach(b=>b.classList.remove("active"));'
            '  btn.classList.add("active");'
            '  document.getElementById("anl-fund-label").textContent=lbl;'
            '  document.getElementById("anl-fund-panel").classList.remove("open");'
            '  document.getElementById("anl-fund-arrow").innerHTML="&#9660;";'
            '  document.querySelectorAll(".anl-view").forEach(v=>v.style.display="none");'
            '  const el=document.getElementById("anl-view-"+vid);'
            '  if(el)el.style.display="";'
            '}'
            '</script>'
        )

        return period_note + dropdown + views_html + js

    def build_pnl_content(df: pd.DataFrame,
                          posicoes: Optional[pd.DataFrame] = None,
                          despesas: Optional[pd.DataFrame] = None,
                          pa: Optional[pd.DataFrame] = None,
                          historico: Optional[pd.DataFrame] = None,
                          pa_sem: Optional[pd.DataFrame] = None,
                          pa_mes: Optional[pd.DataFrame] = None,
                          pa_ano: Optional[pd.DataFrame] = None) -> str:

        df = df.copy()
        pnl_vals    = pd.to_numeric(df["PNL"],    errors="coerce")
        ret_vals    = pd.to_numeric(df["RET_%"],  errors="coerce")
        pl_vals     = pd.to_numeric(df["PL"],     errors="coerce")
        pl_ant_vals = pd.to_numeric(df["PL_ANT"], errors="coerce")

        total_pnl    = pnl_vals.sum(skipna=True)
        total_pl     = pl_vals.sum(skipna=True)
        total_pl_ant = pl_ant_vals.sum(skipna=True)
        retorno_cart = (total_pnl / total_pl_ant) if total_pl_ant else float("nan")
        mediana_ret  = float(ret_vals.median()) if not ret_vals.dropna().empty else float("nan")
        n_pos  = int((pnl_vals > 0).sum())
        n_neg  = int((pnl_vals < 0).sum())
        n_zero = int((pnl_vals == 0).sum())

        best_idx  = ret_vals.idxmax() if not ret_vals.dropna().empty else None
        worst_idx = ret_vals.idxmin() if not ret_vals.dropna().empty else None
        best_fund  = str(df.loc[best_idx,  "FUNDO"]) if best_idx is not None else "—"
        worst_fund = str(df.loc[worst_idx, "FUNDO"]) if worst_idx is not None else "—"
        best_ret   = float(ret_vals.max()) if best_idx is not None else float("nan")
        worst_ret  = float(ret_vals.min()) if worst_idx is not None else float("nan")

        df["PESO_%"]    = pl_ant_vals / total_pl_ant if total_pl_ant else float("nan")
        df["CONTRIB_%"] = pnl_vals    / total_pl_ant if total_pl_ant else float("nan")

        tc = "#1e7e34" if total_pnl >= 0 else "#c0392b"
        rc = "#1e7e34" if (not pd.isna(retorno_cart) and retorno_cart >= 0) else "#c0392b"

        def _card(title: str, value: str, color: str, sub: str = "") -> str:
            sub_html = f'<div class="pnl-card-sub">{sub}</div>' if sub else ""
            return (
                f'<div class="pnl-card">'
                f'<div class="pnl-card-title">{title}</div>'
                f'<div class="pnl-card-value" style="color:{color}">{value}</div>'
                f'{sub_html}</div>'
            )

        # ── ABA 1: RESUMO ────────────────────────────────────────────────────
        cards_html = f'<div class="pnl-cards">' + "".join([
            _card("PnL Total do Dia",  _fmt_money(total_pnl),  tc),
            _card("Retorno Carteira",  _fmt_pct(retorno_cart), rc),
            _card("PL Total",          _fmt_money(total_pl),   ITAU_DARK),
            _card("Fundos c/ Ganho",   str(n_pos),              "#1e7e34"),
            _card("Fundos c/ Perda",   str(n_neg),              "#c0392b"),
            _card("Neutros",           str(n_zero),             "#888"),
            _card("Mediana Retorno",   _fmt_pct(mediana_ret),   "#555"),
            _card("Melhor Retorno",    _fmt_pct(best_ret),      "#1e7e34", best_fund),
            _card("Pior Retorno",      _fmt_pct(worst_ret),     "#c0392b", worst_fund),
        ]) + "</div>"

        chart_pnl  = _pnl_svg_bars(df, "PNL",      _fmt_money)
        chart_ret  = _pnl_svg_bars(df, "RET_%",    _fmt_pct)
        chart_cont = _pnl_svg_bars(df, "CONTRIB_%", _fmt_pct)
        hist_html  = _build_ret_histogram(ret_vals)

        resumo_pane = (
            cards_html
            + '<div class="pnl-charts-row">'
            + f'<div class="pnl-chart-box"><div class="pnl-chart-title">PnL por Fundo (R$)</div>{chart_pnl}</div>'
            + f'<div class="pnl-chart-box"><div class="pnl-chart-title">Retorno (%) por Fundo</div>{chart_ret}</div>'
            + '</div>'
            + '<div class="pnl-charts-row">'
            + f'<div class="pnl-chart-box"><div class="pnl-chart-title">Contribuição ao Retorno da Carteira</div>{chart_cont}</div>'
            + hist_html
            + '</div>'
        )

        # ── ABA 2: PnL FUNDOS ────────────────────────────────────────────────
        col_map = {
            "FUNDO":     "FUNDO",
            "PL":        "PL Atual",
            "PL_ANT":    "PL D-1",
            "PESO_%":    "Peso %",
            "PNL":       "PnL (R$)",
            "RET_%":     "Retorno (%)",
            "CONTRIB_%": "Contribuição %",
        }
        cols    = [c for c in col_map if c in df.columns]
        headers = [col_map[c] for c in cols]
        th_cells = "".join(
            f'<th onclick="sortTable(this)" title="Clique para ordenar">{h}</th>'
            for h in headers
        )
        rows_html = []
        for _, row in df.iterrows():
            fund_name = str(row.get("FUNDO", ""))
            row_cat   = _fund_cats.get(fund_name.strip(), "")
            cells = []
            for c in cols:
                val = row.get(c, "")
                if c == "FUNDO":
                    cells.append(f'<td>{_fmt_text(val)}</td>')
                elif c in ("PL", "PL_ANT"):
                    cells.append(f'<td>{_fmt_money(val)}</td>')
                elif c == "PNL":
                    text = _fmt_money(val)
                    try:
                        cls = "bold tot-green" if float(val) >= 0 else "bold tot-red"
                    except Exception:
                        cls = ""
                    cells.append(f'<td class="{cls}">{text}</td>')
                elif c in ("RET_%", "CONTRIB_%"):
                    text = _fmt_pct(val)
                    try:
                        cls = "bold tot-green" if float(val) >= 0 else "bold tot-red"
                    except Exception:
                        cls = ""
                    cells.append(f'<td class="{cls}">{text}</td>')
                elif c == "PESO_%":
                    cells.append(f'<td>{_fmt_pct(val)}</td>')
            rows_html.append(f'<tr data-categoria="{row_cat}">{"".join(cells)}</tr>')

        # Pills de categoria para o PnL FUNDOS
        pnl_cats_present = []
        for _cat in _cats_ordered:
            if any(_fund_cats.get(str(r.get("FUNDO", "")).strip(), "") == _cat
                   for _, r in df.iterrows()):
                pnl_cats_present.append(_cat)
        cat_pills_html = (
            '<div class="cat-pill-row">'
            '<button class="cat-pill active" onclick="pnlCatFilter(\'ALL\',this)">Todos</button>'
            + "".join(
                f'<button class="cat-pill" onclick="pnlCatFilter(\'{c.replace(chr(39),chr(92)+chr(39))}\',this)">{c}</button>'
                for c in pnl_cats_present
            )
            + '</div>'
            '<script>'
            'function pnlCatFilter(cat,btn){'
            '  document.querySelectorAll(".cat-pill").forEach(b=>b.classList.remove("active"));'
            '  btn.classList.add("active");'
            '  document.querySelectorAll("#pnl-fundos-tbody tr").forEach(row=>{'
            '    row.style.display=(cat==="ALL"||row.dataset.categoria===cat)?"":"none";'
            '  });'
            '}'
            '</script>'
        ) if pnl_cats_present else ""

        fundos_pane = (
            cat_pills_html
            + '<div class="search-wrap" style="margin-bottom:12px">'
            '<input class="search-box" placeholder="&#128269; Buscar fundo..." oninput="filterTable(this)">'
            '</div>'
            '<div class="tbl-wrap"><table class="exp-table">'
            f'<thead><tr>{th_cells}</tr></thead>'
            f'<tbody id="pnl-fundos-tbody">{"".join(rows_html)}</tbody>'
            '</table></div>'
        )

        # ── ABA 3: POSIÇÕES ──────────────────────────────────────────────────
        if posicoes is not None and not posicoes.empty:
            setor_chart = _build_group_bars(posicoes, "SETOR",    "PNL_TOTAL", "PnL Total por Setor (R$)")
            tipo_chart  = _build_group_bars(posicoes, "TIPO",     "PNL_TOTAL", "PnL Total por Tipo de Ativo (R$)")
            charts_pos  = (
                '<div class="pnl-charts-row">'
                + (f'{setor_chart}' if setor_chart else '')
                + (f'{tipo_chart}'  if tipo_chart  else '')
                + '</div>'
            )
            posicoes_pane = charts_pos + build_posicoes_section(posicoes)
        else:
            posicoes_pane = '<p style="padding:20px;color:#888;">Sem dados de posições para esta data.</p>'

        # ── ABA 4: ANÁLISE (gráficos de linha históricos) ────────────────────
        analise_pane = _build_analise_tab(historico)

        # ── ABA 5: ATRIBUIÇÃO ────────────────────────────────────────────────
        atrib_pane = build_attribution_pane(pa)

        # ── ABA 6: ATRIBUIÇÃO POR ATIVO ──────────────────────────────────────
        def _build_atrib_ativo_pane(pa_dfs: Dict[str, Optional[pd.DataFrame]]) -> str:
            """
            pa_dfs: {"D": pa_diario, "W": pa_semana, "M": pa_mes, "A": pa_ano}
            """
            import re as _re

            # PL por fundo (do df de resumo do dia) para normalizar PnL em % do patrimônio
            _pl_per_fund: dict = {}
            if "FUNDO" in df.columns and "PL" in df.columns:
                _pl_per_fund = dict(zip(
                    df["FUNDO"].astype(str),
                    pd.to_numeric(df["PL"], errors="coerce").fillna(0)
                ))

            _PERIOD_LABELS = {"D": "DIÁRIO", "W": "SEMANAL", "M": "MENSAL", "A": "ANUAL"}
            # Filtra períodos com dados
            periods = [(k, _PERIOD_LABELS[k], v)
                       for k, v in pa_dfs.items()
                       if v is not None and not v.empty]

            if not periods:
                return '<p style="padding:20px;color:#888;">Sem dados de atribuição por ativo.</p>'

            # Usa o primeiro período disponível como referência para o seletor de fundos
            first_key, _, first_df = periods[0]
            ref_df = first_df.copy()
            ref_df["CATEGORIA"] = ref_df["FUNDO"].map(_fund_cats).fillna("Outros")

            def _sid(s): return _re.sub(r"[^a-zA-Z0-9]", "_", str(s))

            _B  = ('display:inline-block;margin:3px 4px;padding:5px 14px;border-radius:20px;'
                   'border:1.5px solid #ccc;background:#fff;font-size:.8rem;cursor:pointer;'
                   'font-family:inherit;font-weight:600;transition:all .12s;')
            _BA = f'background:{ITAU_ORANGE};color:#fff;border-color:{ITAU_ORANGE};'
            _BI = f'color:{ITAU_DARK};'

            # ── Mapa categoria → fundos (baseado em ref_df) ──────────────────
            cats_in: Dict[str, List[str]] = {}
            for f in sorted(ref_df["FUNDO"].dropna().unique().tolist()):
                cats_in.setdefault(_fund_cats.get(f, "Outros"), []).append(f)
            ordered = [c for c in _cats_ordered if c in cats_in]
            if "Outros" in cats_in:
                ordered.append("Outros")

            # ── Seletor de período ────────────────────────────────────────────
            period_bar = '<div id="pav-period-bar" style="margin:8px 0 10px">'
            for i, (key, label, _) in enumerate(periods):
                act = _BA if i == 0 else _BI
                period_bar += (f'<button data-pavperiod="{key}" style="{_B}{act}"'
                               f' onclick="pavPeriodSel(this)">{label}</button>')
            period_bar += '</div>'

            # ── Nível 1: pills de categoria ───────────────────────────────────
            cat_bar = '<div id="pav-cat-bar" style="margin:6px 0 6px">'
            cat_bar += f'<button data-pavcat="" style="{_B}{_BA}" onclick="pavCatSel(this)">TODOS</button>'
            for cat in ordered:
                n = len(cats_in[cat])
                cat_bar += (f'<button data-pavcat="{cat}" style="{_B}{_BI}"'
                            f' onclick="pavCatSel(this)">{cat} ({n})</button>')
            cat_bar += '</div>'

            # ── Nível 2: dropdown de fundo por categoria ──────────────────────
            fund_bar = '<div id="pav-fund-bar" style="margin:4px 0 12px">'
            fund_bar += '<div data-pavcatfunds="" style="display:block"></div>'
            for cat in ordered:
                fund_bar += f'<div data-pavcatfunds="{cat}" style="display:none">'
                fund_bar += ('<div class="fund-collapse-wrap" style="margin:0">'
                             '<button class="fund-collapse-btn" onclick="pavFundDropToggle(this)">'
                             '<span data-pav-lbl>Selecionar Fundo</span>'
                             '<span class="drop-arrow">&#9660;</span>'
                             '</button><div class="fund-collapse-panel">')
                for f in cats_in[cat]:
                    fid = _sid(f)
                    fund_bar += (f'<button class="fund-drop-item" data-pavfundo="{fid}"'
                                 f' data-pavfnome="{f}" onclick="pavFundSel(this)">{f}</button>')
                fund_bar += '</div></div></div>'
            fund_bar += '</div>'

            # ── Busca ─────────────────────────────────────────────────────────
            search_box = (
                '<div class="search-wrap" style="margin-bottom:10px">'
                '<input id="pav-search" class="search-box"'
                ' placeholder="&#128269; Buscar ativo, ticker, setor, tipo..."'
                ' oninput="pavFilter()">'
                '</div>'
            )

            # ── Colunas comuns ────────────────────────────────────────────────
            col_map = [
                ("FUNDO",        "Fundo",      "txt"),
                ("TIPO",         "Tipo",       "txt"),
                ("ATIVO",        "Ativo",      "txt"),
                ("TICKER",       "Ticker",     "txt"),
                ("SETOR",        "Setor",      "txt"),
                ("MOEDA",        "Moeda",      "txt"),
                ("PNL_TOTAL",    "PnL Total",  "money"),
                ("PNL_MTM",      "MTM",        "money"),
                ("PNL_CARREGO",  "Carrego",    "money"),
                ("PNL_SPREAD",   "Spread",     "money"),
                ("PNL_CAMBIO",   "Câmbio",     "money"),
                ("PNL_ALUGUEL",  "Aluguel",    "money"),
                ("PNL_OPERACAO", "Operação",   "money"),
                ("BENCH_PNL",    "Benchmark",  "money"),
            ]

            MAX_ATIVOS = 20

            def _build_wf_for_fund(key, f, pf):
                """Waterfall SVG para um fundo dentro de uma janela temporal.
                   O ID inclui a chave do período para evitar colisão entre janelas."""
                fid  = _sid(f)
                pf   = pf.copy()
                pf["_pnl_v"] = pd.to_numeric(pf["PNL_TOTAL"], errors="coerce")
                _pl_f = float(_pl_per_fund.get(f, 0) or 0)

                # ── Gráfico por Ativo ─────────────────────────────────────────
                _akey = "TICKER" if "TICKER" in pf.columns else "ATIVO"
                _fagg = (pf.groupby(_akey, dropna=False)
                           .agg(_pnl_v=("_pnl_v", "sum")).reset_index())
                n_tot = len(_fagg)
                _top  = _fagg.assign(_abs=lambda d: d["_pnl_v"].abs()).nlargest(MAX_ATIVOS, "_abs")
                _pos  = _top[_top["_pnl_v"] >= 0].sort_values("_pnl_v", ascending=False)
                _neg  = _top[_top["_pnl_v"] <  0].sort_values("_pnl_v", ascending=False)
                _srt  = pd.concat([_pos, _neg])
                lbls, vals = [], []
                for _, row in _srt.iterrows():
                    v = row["_pnl_v"]
                    if pd.isna(v) or v == 0:
                        continue
                    lbls.append(str(row.get(_akey) or "")[:16])
                    vals.append(float(v))
                total = float(pf["_pnl_v"].sum())
                svg   = _build_waterfall_svg(lbls, vals, total, show_pct=True, pl=_pl_f) if lbls else ""
                note  = (f'<p style="font-size:.78rem;color:#888;margin:2px 0 8px">'
                         f'Exibindo os {len(lbls)} ativos de maior |PnL| ({n_tot} no total)</p>'
                         if len(lbls) < n_tot else "")

                # ── Gráfico por Setor ─────────────────────────────────────────
                setor_html = ""
                if "SETOR" in pf.columns:
                    _sagg = (pf.assign(_setor=pf["SETOR"].fillna("—").astype(str).str.strip()
                                       .replace("", "—"))
                               .groupby("_setor", dropna=False)
                               .agg(_pnl_v=("_pnl_v", "sum")).reset_index())
                    _sagg = _sagg[_sagg["_pnl_v"].notna() & (_sagg["_pnl_v"] != 0)]
                    _sp = _sagg[_sagg["_pnl_v"] >= 0].sort_values("_pnl_v", ascending=False)
                    _sn = _sagg[_sagg["_pnl_v"] <  0].sort_values("_pnl_v", ascending=False)
                    _ss = pd.concat([_sp, _sn])
                    slbls = [str(r["_setor"])[:20] for _, r in _ss.iterrows()]
                    svals = [float(r["_pnl_v"]) for _, r in _ss.iterrows()]
                    if slbls:
                        ssvg = _build_waterfall_svg(slbls, svals, total, show_pct=True, pl=_pl_f)
                        setor_html = (
                            f'<div class="pnl-chart-box" style="margin-bottom:10px">'
                            f'<div class="pnl-chart-title">Atribuição por Setor — {f}</div>'
                            f'{ssvg}</div>'
                        )

                # ── Gráfico PnL vs Benchmark por Ativo (barras agrupadas) ────
                alpha_html = ""
                if "BENCH_PNL" in pf.columns:
                    _akey2 = "TICKER" if "TICKER" in pf.columns else "ATIVO"
                    _aagg = (pf.groupby(_akey2, dropna=False)
                               .agg(_pnl=("_pnl_v", "sum"),
                                    _bench=("BENCH_PNL", "sum")).reset_index())
                    _aagg["_bench"] = pd.to_numeric(_aagg["_bench"], errors="coerce").fillna(0)
                    # ordena pelo maior |PnL| para mostrar os mais relevantes
                    _aagg = (_aagg.assign(_abs=lambda d: d["_pnl"].abs())
                                  .nlargest(MAX_ATIVOS, "_abs"))
                    _ap = _aagg[_aagg["_pnl"] >= 0].sort_values("_pnl", ascending=False)
                    _an = _aagg[_aagg["_pnl"] <  0].sort_values("_pnl", ascending=False)
                    _as = pd.concat([_ap, _an])
                    albls = [str(r[_akey2])[:16] for _, r in _as.iterrows()]
                    avals_pnl   = [float(r["_pnl"])   for _, r in _as.iterrows()]
                    avals_bench = [float(r["_bench"])  for _, r in _as.iterrows()]
                    if albls:
                        if _pl_f:
                            _pnl_pct   = [v / _pl_f for v in avals_pnl]
                            _bench_pct = [v / _pl_f for v in avals_bench]
                            asvg = _build_grouped_bar_svg(albls, _pnl_pct, _bench_pct,
                                                          label_a="PnL", label_b="Benchmark",
                                                          fmt=_fmt_pct)
                            _tot_pnl_pct   = total / _pl_f
                            _tot_bench_pct = float(pd.to_numeric(pf["BENCH_PNL"], errors="coerce").fillna(0).sum()) / _pl_f
                            _tot_alpha_pct = _tot_pnl_pct - _tot_bench_pct
                            _subtitle = (
                                f'<div style="font-size:.78rem;color:#555;margin:-2px 0 6px;padding-left:2px">'
                                f'Total — PnL: <strong style="color:{"#1e7e34" if _tot_pnl_pct>=0 else "#c0392b"}">'
                                f'{("+" if _tot_pnl_pct>0 else "")}{_fmt_pct(_tot_pnl_pct)}</strong>'
                                f'&nbsp;|&nbsp;Benchmark: <strong style="color:{"#1e7e34" if _tot_bench_pct>=0 else "#c0392b"}">'
                                f'{("+" if _tot_bench_pct>0 else "")}{_fmt_pct(_tot_bench_pct)}</strong>'
                                f'&nbsp;|&nbsp;Alpha: <strong style="color:{"#1e7e34" if _tot_alpha_pct>=0 else "#c0392b"}">'
                                f'{("+" if _tot_alpha_pct>0 else "")}{_fmt_pct(_tot_alpha_pct)}</strong>'
                                f'</div>'
                            )
                        else:
                            asvg = _build_grouped_bar_svg(albls, avals_pnl, avals_bench,
                                                          label_a="PnL", label_b="Benchmark")
                            _subtitle = ""
                        alpha_html = (
                            f'<div class="pnl-chart-box" style="margin-bottom:10px">'
                            f'<div class="pnl-chart-title">PnL vs Benchmark por Ativo — {f}</div>'
                            f'{_subtitle}{asvg}</div>'
                        )

                # ID com período: pav-wf-D-FUND1, pav-wf-W-FUND1, etc.
                return (f'<div id="pav-wf-{key}-{fid}" class="pav-wf" style="display:none">'
                        f'<div class="pnl-chart-box" style="margin-bottom:10px">'
                        f'<div class="pnl-chart-title">Atribuição por Ativo — {f}</div>'
                        f'{note}{svg}</div>'
                        f'{setor_html}'
                        f'{alpha_html}</div>')

            def _build_table_for_period(key, pf):
                """Tabela de ativos para uma janela temporal."""
                pf = pf.copy()
                pf["CATEGORIA"] = pf["FUNDO"].map(_fund_cats).fillna("Outros")
                cols = [(c, lbl, fmt) for c, lbl, fmt in col_map if c in pf.columns]
                th   = "".join(f'<th onclick="sortTable(this)">{lbl}</th>' for _, lbl, _ in cols)
                rows = []
                for i, (_, row) in enumerate(pf.iterrows()):
                    bg   = f'style="background:{ROW_PAR}"' if i % 2 == 1 else ""
                    cat  = str(row.get("CATEGORIA", ""))
                    fund = _sid(str(row.get("FUNDO", "")))
                    cells = []
                    for c, _, fmt in cols:
                        val = row.get(c, "")
                        if fmt == "money":
                            text = _fmt_money(val)
                            try:
                                v = float(val)
                                cls = ' class="bold tot-green"' if v >= 0 else ' class="bold tot-red"'
                            except Exception:
                                cls = ""
                            cells.append(f'<td{cls}>{text}</td>')
                        else:
                            bold = ' class="bold"' if c == "FUNDO" else ""
                            cells.append(f'<td{bold}>{_fmt_text(val)}</td>')
                    rows.append(f'<tr {bg} data-pavcat="{cat}" data-pavfund="{fund}">{"".join(cells)}</tr>')
                return (f'<div class="tbl-wrap"><table class="exp-table">'
                        f'<thead><tr>{th}</tr></thead>'
                        f'<tbody id="pav-tbody-{key}">{"".join(rows)}</tbody>'
                        f'</table></div>')

            # ── Seções por período ────────────────────────────────────────────
            period_sections = []
            for i, (key, label, pf) in enumerate(periods):
                fundos_p = sorted(pf["FUNDO"].dropna().unique().tolist())
                wf_parts = "".join(_build_wf_for_fund(key, f, pf[pf["FUNDO"] == f]) for f in fundos_p)
                tbl_part = _build_table_for_period(key, pf)
                vis = "" if i == 0 else ' style="display:none"'
                period_sections.append(
                    f'<div id="pav-sec-{key}" class="pav-period-sec"{vis}>'
                    f'{wf_parts}{tbl_part}'
                    f'</div>'
                )
            period_html = "".join(period_sections)

            # ── JS inline ─────────────────────────────────────────────────────
            first_key = periods[0][0]
            js = (
                '<script>'
                f'var _pavB="{_B}",_pavBA="{_BA}",_pavBI="{_BI}";'
                f'var _pavCat="",_pavFund="",_pavPeriod="{first_key}";'

                # Seletor de período
                'function pavPeriodSel(btn){'
                '  _pavPeriod=btn.dataset.pavperiod;'
                '  document.querySelectorAll("#pav-period-bar button").forEach(b=>{'
                '    b.style.cssText=_pavB+(b===btn?_pavBA:_pavBI);'
                '  });'
                '  document.querySelectorAll(".pav-period-sec").forEach(s=>s.style.display="none");'
                '  const sec=document.getElementById("pav-sec-"+_pavPeriod);'
                '  if(sec)sec.style.display="";'
                '  _pavShowWf(_pavFund);'
                '  pavFilter();'
                '}'

                # Mostra waterfall do fundo selecionado no período ativo
                # ID = pav-wf-{período}-{fid}
                'function _pavShowWf(fid){'
                '  document.querySelectorAll(".pav-wf").forEach(d=>d.style.display="none");'
                '  if(fid){'
                '    const el=document.getElementById("pav-wf-"+_pavPeriod+"-"+fid);'
                '    if(el)el.style.display="";'
                '  }'
                '}'

                'function pavCatSel(btn){'
                '  _pavCat=btn.dataset.pavcat;_pavFund="";'
                '  document.querySelectorAll("#pav-cat-bar button").forEach(b=>{'
                '    b.style.cssText=_pavB+(b===btn?_pavBA:_pavBI);'
                '  });'
                '  document.querySelectorAll("#pav-fund-bar [data-pavcatfunds]").forEach(d=>{'
                '    d.style.display=d.dataset.pavcatfunds===_pavCat?"block":"none";'
                '  });'
                '  document.querySelectorAll("#pav-fund-bar .fund-collapse-panel.open").forEach(p=>{'
                '    p.classList.remove("open");'
                '    const a=p.previousElementSibling&&p.previousElementSibling.querySelector(".drop-arrow");'
                '    if(a)a.innerHTML="&#9660;";'
                '  });'
                '  document.querySelectorAll("#pav-fund-bar [data-pav-lbl]").forEach(s=>{'
                '    s.textContent="Selecionar Fundo";'
                '  });'
                '  document.querySelectorAll("#pav-fund-bar .fund-drop-item.active").forEach(b=>{'
                '    b.classList.remove("active");'
                '  });'
                '  _pavShowWf(null);'
                '  pavFilter();'
                '}'

                'function pavFundDropToggle(btn){'
                '  const panel=btn.nextElementSibling;'
                '  if(!panel)return;'
                '  const open=panel.classList.toggle("open");'
                '  const arrow=btn.querySelector(".drop-arrow");'
                '  if(arrow)arrow.innerHTML=open?"&#9650;":"&#9660;";'
                '}'

                'function pavFundSel(btn){'
                '  _pavFund=btn.dataset.pavfundo;'
                '  const panel=btn.closest(".fund-collapse-panel");'
                '  if(panel){'
                '    panel.querySelectorAll(".fund-drop-item").forEach(b=>{'
                '      b.classList.toggle("active",b===btn);'
                '    });'
                '    panel.classList.remove("open");'
                '    const colBtn=panel.previousElementSibling;'
                '    if(colBtn){'
                '      const lbl=colBtn.querySelector("[data-pav-lbl]");'
                '      if(lbl)lbl.textContent=btn.dataset.pavfnome||btn.textContent;'
                '      const arrow=colBtn.querySelector(".drop-arrow");'
                '      if(arrow)arrow.innerHTML="&#9660;";'
                '    }'
                '  }'
                '  _pavShowWf(_pavFund);'
                '  pavFilter();'
                '}'

                # Filtra a tabela do período ativo
                'function pavFilter(){'
                '  const q=(document.getElementById("pav-search")||{}).value||"";'
                '  const ql=q.toLowerCase();'
                '  const tbody=document.getElementById("pav-tbody-"+_pavPeriod);'
                '  if(!tbody)return;'
                '  tbody.querySelectorAll("tr").forEach(row=>{'
                '    const catOk=!_pavCat||row.dataset.pavcat===_pavCat;'
                '    const fundOk=!_pavFund||row.dataset.pavfund===_pavFund;'
                '    const txtOk=!ql||Array.from(row.cells).map(c=>c.textContent).join(" ").toLowerCase().includes(ql);'
                '    row.style.display=(catOk&&fundOk&&txtOk)?"":"none";'
                '  });'
                '}'
                '</script>'
            )

            return period_bar + cat_bar + fund_bar + search_box + period_html + js

        atrib_ativo_pane = _build_atrib_ativo_pane({
            "D": pa,
            "W": pa_sem,
            "M": pa_mes,
            "A": pa_ano,
        })

        # ── ABA 7: DESPESAS ──────────────────────────────────────────────────
        if despesas is not None and not despesas.empty:
            desp_chart   = _build_group_bars(despesas, "FUNDO", "VALOR", "Despesas por Fundo (R$)")
            despesas_pane = (
                (f'<div class="pnl-charts-row">{desp_chart}</div>' if desp_chart else "")
                + build_despesas_section(despesas)
            )
        else:
            despesas_pane = '<p style="padding:20px;color:#888;">Sem despesas para esta data.</p>'

        # ── Montagem das sub-abas ────────────────────────────────────────────
        tabs = [
            ("perf-resumo",      "RESUMO",         resumo_pane),
            ("perf-fundos",      "PnL FUNDOS",     fundos_pane),
            ("perf-posicoes",    "POSIÇÕES",        posicoes_pane),
            ("perf-analise",     "ANÁLISE",         analise_pane),
            ("perf-atrib",       "ATRIBUIÇÃO",      atrib_pane),
            ("perf-atrib-ativo", "ATRIB. POR ATIVO", atrib_ativo_pane),
            ("perf-despesas",    "DESPESAS",        despesas_pane),
        ]
        nav_btns = "".join(
            f'<button class="perf-tab-btn{" active" if i == 0 else ""}" data-perf-pane="{tid}">{label}</button>'
            for i, (tid, label, _) in enumerate(tabs)
        )
        panes_html = "".join(
            f'<div id="{tid}" class="perf-pane{" active" if i == 0 else ""}">{content}</div>'
            for i, (tid, _, content) in enumerate(tabs)
        )
        return (
            f'<div class="perf-nav">{nav_btns}</div>'
            + panes_html
        )

    def _build_rol_alertas(rol_data):
        """Tabela-resumo de alertas de rolagem.

        Lista, por produto, os dias úteis até o vencimento do futuro (v1) e o
        status de rolagem — destacando quando faltam <= ALERTA_DIAS_ROLAGEM
        dias úteis para o vencimento.
        """
        alertas = [
            df.attrs["alerta"]
            for _, df, _, _ in (rol_data or [])
            if df.attrs.get("alerta")
        ]
        if not alertas:
            return ""

        alertas = sorted(alertas, key=lambda a: a.get("dias", 10 ** 9))  # + urgente 1º
        n_urg   = sum(1 for a in alertas if a.get("urgente"))

        heads = ["PRODUTO", "ROLAGEM", "VENCIMENTO", "DIAS P/ VENC.",
                 "DATA MÁX. ROLAGEM", "DIAS P/ ROLAGEM", "STATUS"]
        th = "".join(
            f'<th onclick="sortTable(this)" title="Clique para ordenar">{h}</th>'
            for h in heads
        )

        rows = []
        for a in alertas:
            urg      = bool(a.get("urgente"))
            venc_fmt = pd.to_datetime(a["vencimento"]).strftime("%d/%m/%Y")
            dmax_fmt = pd.to_datetime(a["data_max"]).strftime("%d/%m/%Y")
            row_cls  = ' class="rol-alert-urgent"' if urg else ""
            status   = ('<span class="rol-badge-alert">&#9888; ALERTA</span>'
                        if urg else '<span class="rol-badge-ok">OK</span>')
            rows.append(
                f'<tr{row_cls}>'
                f'<td>{_fmt_text(a["produto"])}</td>'
                f'<td>{_fmt_text(a["rolagem"])}</td>'
                f'<td>{venc_fmt}</td>'
                f'<td class="bold">{a["dias"]}</td>'
                f'<td>{dmax_fmt}</td>'
                f'<td class="bold">{a["dias_rolagem"]}</td>'
                f'<td>{status}</td>'
                f'</tr>'
            )

        aviso = (f'<span class="rol-alert-count">{n_urg} em alerta</span>'
                 if n_urg else
                 '<span class="rol-alert-count ok">nenhum em alerta</span>')

        return (
            f'<div class="rol-alert-wrap">'
            f'<div class="rol-alert-head">'
            f'<span class="rol-alert-title">&#9888; ALERTA DE ROLAGENS</span>'
            f'<span class="rol-alert-sub">destaque quando faltam '
            f'&#8804; {ALERTA_DIAS_ROLAGEM} dias úteis para o vencimento do futuro'
            f'</span>{aviso}</div>'
            f'<div class="tbl-wrap"><table class="exp-table rol-alert-table">'
            f'<thead><tr>{th}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody>'
            f'</table></div></div>'
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

        # badge com os dias úteis até o vencimento do futuro (v1)
        alerta     = df.attrs.get("alerta") or {}
        dias_v     = alerta.get("dias")
        venc_v     = alerta.get("vencimento")
        dias_badge = ""
        if dias_v is not None and venc_v is not None:
            venc_fmt   = pd.to_datetime(venc_v).strftime("%d/%m/%Y")
            urg_cls    = " urgent" if alerta.get("urgente") else ""
            dias_badge = (
                f'<span class="rol-dias{urg_cls}" '
                f'title="Dias úteis até o vencimento do futuro">'
                f'&#9201; {dias_v} du p/ venc. {venc_fmt}</span>'
            )

        return (
            f'<div class="rol-group">'
            f'<div class="rol-subtitle">{label}'
            f'<span class="rol-vct">{v1} &#8594; {v2}</span>{dias_badge}</div>'
            f'<div class="tbl-wrap"><table class="exp-table">'
            f'<thead><tr>{th}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody>'
            f'</table></div></div>'
        )

    rol_html = ""
    if rolagem_data:
        rol_html = _build_rol_alertas(rolagem_data) + "".join(
            _build_rol_table(label, df, v1, v2)
            for label, df, v1, v2 in rolagem_data
        )
    has_rolagem = bool(rol_html)

    has_it_now = MOSTRAR_ITNOW and it_now_df is not None and not it_now_df.empty
    _csv_abs   = os.path.abspath(INPUT_IT_NOW)
    _html_dir  = os.path.abspath(out_dir)
    _csv_rel   = os.path.relpath(_csv_abs, _html_dir).replace("\\", "/")

    css = build_css()
    js  = build_js(_csv_rel if has_it_now else "")

    _btn_rolagem = ('<button class="main-btn" onclick="switchMain(\'rolagem\')">'
                    'ROLAGEM</button>') if has_rolagem else ''
    _sec_rolagem = (f'<div id="sec-rolagem" class="sec"><div class="content">'
                    f'{rol_html}</div></div>') if has_rolagem else ''

    def build_it_now_html(df: pd.DataFrame) -> str:
        ts_col    = "DATA_HORA_ATUALIZACAO"
        timestamp = ""
        if ts_col in df.columns and not df[ts_col].dropna().empty:
            timestamp = df[ts_col].dropna().iloc[0]

        col_map = {
            "ETF":                  "ETF",
            "INDICE":               "ÍNDICE",
            "YIELD_ESTIMADO":       "YIELD ESTIMADO",
            "YIELD_ULTIMO_NEGOCIO": "YIELD ÚLTIMO NEGÓCIO",
            "SPREAD":               "SPREAD",
            "DURATION":             "DURATION",
            "VALOR_ESTIMADO_COTA":  "VALOR EST. COTA",
        }
        data_cols = [c for c in col_map if c in df.columns]

        th_cells = "".join(
            f'<th onclick="sortTable(this)" title="Clique para ordenar">{col_map[c]}</th>'
            for c in data_cols
        )

        rows_html = []
        for i, (_, row) in enumerate(df.iterrows()):
            bg = f'style="background:{ROW_PAR}"' if i % 2 == 1 else ""
            cells = []
            for c in data_cols:
                val = str(row.get(c, "") or "").strip()
                cls = ' class="bold"' if c == "ETF" else ""
                cells.append(f'<td{cls}>{val}</td>')
            rows_html.append(f'<tr {bg}>{"".join(cells)}</tr>')

        ts_html = (f'<p class="it-now-ts">Última atualização do arquivo: '
                   f'<strong>{timestamp}</strong></p>') if timestamp else ""
        return (
            f'<div class="it-now-toolbar">'
            f'  <div class="it-now-meta">'
            f'    {ts_html}'
            f'    <span class="it-now-refreshed" id="it-now-refreshed"></span>'
            f'  </div>'
            f'  <button class="btn-refresh" id="btn-refresh-itnow" onclick="refreshItNow()">'
            f'    <span class="spin">&#8635;</span> Atualizar'
            f'  </button>'
            f'</div>'
            f'<div class="tbl-wrap">'
            f'<table class="exp-table" id="it-now-table">'
            f'<thead><tr>{th_cells}</tr></thead>'
            f'<tbody id="it-now-tbody">{"".join(rows_html)}</tbody>'
            f'</table></div>'
        )

    _btn_itnow = ('<button class="main-btn" onclick="switchMain(\'itnow\')">'
                  'IT NOW</button>') if has_it_now else ''
    _sec_itnow = (
        f'<div id="sec-itnow" class="sec"><div class="content">'
        f'<h2 class="aba-title">IT NOW — ETFs em Tempo Real</h2>'
        f'{build_it_now_html(it_now_df)}'
        f'</div></div>'
    ) if has_it_now else ''

    has_performance = MOSTRAR_PERFORMANCE and pnl_df is not None and not pnl_df.empty
    _btn_performance = ('<button class="main-btn" onclick="switchMain(\'performance\')">'
                        'PERFORMANCE</button>') if has_performance else ''
    _sec_performance = (
        f'<div id="sec-performance" class="sec"><div class="content">'
        f'<h2 class="aba-title">PERFORMANCE — PnL Diário por Fundo</h2>'
        f'{build_pnl_content(pnl_df, posicoes_df, despesas_df, pa_df, historico_df, pa_sem_df, pa_mes_df, pa_ano_df)}'
        f'</div></div>'
    ) if has_performance else ''

    has_batimento = MOSTRAR_BATIMENTO and batimento_df is not None and not batimento_df.empty
    _btn_batimento = (
        f'<a href="batimento_{dt}.html" class="main-btn" style="text-decoration:none">'
        f'BATIMENTO</a>'
    ) if has_batimento else ''

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
    {_btn_itnow}
    {_btn_performance}
    {_btn_batimento}
  </nav>
  <nav class="nav-sub" id="nav-sub">
    {''.join(buttons)}
  </nav>
</div>

<div id="sec-exposicao" class="sec active">
  <div class="content">{''.join(panes)}</div>
</div>

{_sec_rolagem}

{_sec_itnow}

{_sec_performance}

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
# BATIMENTO — arquivo HTML separado
# ─────────────────────────────────────────────────────────────────────────────

def gerar_batimento_html(batimento_df: Optional[pd.DataFrame], dt: str, out_dir: str,
                         abas_data: Dict[str, pd.DataFrame],
                         posicoes_df: Optional[pd.DataFrame] = None) -> None:
    """Gera batimento_{dt}.html separado do relatório principal."""
    import re as _re, json as _json
    from html_styles import build_css, build_js

    os.makedirs(out_dir, exist_ok=True)
    dt_fmt = pd.to_datetime(dt).strftime("%d/%m/%Y")
    css    = build_css()
    js_base = build_js("")

    # Mapa fundo → categoria (mesmo padrão do gerar_html)
    _fund_cats: Dict[str, str] = {}
    _cats_ordered: List[str] = []
    for _aba, _df_aba in abas_data.items():
        if _df_aba is not None and not _df_aba.empty and "FUNDO" in _df_aba.columns:
            for _f in _df_aba["FUNDO"].dropna().astype(str).str.strip().unique():
                if _f and _f not in _fund_cats:
                    _fund_cats[_f] = _aba
            if _aba not in _cats_ordered:
                _cats_ordered.append(_aba)

    # ── Escrita em streaming — nunca monta a string inteira em memória ────────
    nome = os.path.join(out_dir, f"batimento_{dt}.html")
    _CHUNK = 512 * 1024  # 512 KB por write

    def _write(fh, s: str) -> None:
        for off in range(0, max(len(s), 1), _CHUNK):
            fh.write(s[off:off + _CHUNK])

    def _esc(s: str) -> str:
        return str(s).replace('&', '&amp;').replace('"', '&quot;').replace("'", "&#39;").replace('<', '&lt;').replace('>', '&gt;')

    def _fmt_qty(v) -> str:
        if pd.isna(v):
            return ""
        return f"{v:,.6f}".rstrip("0").rstrip(".")

    # Estilo compartilhado para os botões de categoria e fundo
    _btn_base  = ('display:inline-block;margin:3px 4px;padding:5px 14px;border-radius:20px;'
                  'border:1.5px solid #ccc;background:#fff;font-size:.8rem;cursor:pointer;'
                  'font-family:inherit;font-weight:600;transition:all .12s;')
    _btn_act   = f'background:{ITAU_ORANGE};color:#fff;border-color:{ITAU_ORANGE};'
    _btn_inact = f'color:{ITAU_DARK};'

    with open(nome, "w", encoding="utf-8") as fh:
        _write(fh, '<!DOCTYPE html><html lang="pt-BR"><head>'
                   '<meta charset="UTF-8">'
                   '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
                   f'<title>Batimento — {dt_fmt}</title>'
                   '<style>')
        _write(fh, css)
        _write(fh, '</style></head><body>')

        fh.write(
            f'<div class="hdr"><div class="hdr-inner">'
            f'<div><h1>BATIMENTO — Verificação de Posição</h1>'
            f'<p class="sub">Data Referência: &nbsp;<strong>{dt_fmt}</strong></p></div>'
            f'<div class="brand"><span>Itaú Asset Management</span></div>'
            f'</div></div>'
            f'<div class="nav-wrapper"><nav class="nav-main">'
            f'<a href="exposicao_{dt}.html" class="btn-voltar">&#8592; Voltar</a>'
            f'</nav></div>'
            f'<div class="sec active"><div class="content">'
        )

        if batimento_df is None or batimento_df.empty:
            _write(fh, '<p style="padding:2rem;color:#888">Sem dados de batimento disponíveis.</p>')
        else:
            df = batimento_df.copy()
            df["CATEGORIA"] = df["FUNDO"].map(_fund_cats).fillna("Outros")

            n_qbr_total = len(df)
            qbr_by_cat  = df.groupby("CATEGORIA").size().to_dict()
            qbr_by_fund = df.groupby("FUNDO").size().to_dict()

            # ── Card ─────────────────────────────────────────────────────────
            fh.write(
                f'<div class="pnl-cards">'
                f'<div class="pnl-card" style="border-top:4px solid {ITAU_RED}">'
                f'<p class="pnl-card-lbl">A Verificar</p>'
                f'<p class="pnl-card-val" style="color:{ITAU_RED}" id="bat-card-n">'
                f'{n_qbr_total:,}</p>'
                f'</div></div>'
            )

            # ── Mapa categoria → fundos ───────────────────────────────────────
            cats_in_bat: Dict[str, List[str]] = {}
            for f in sorted(df["FUNDO"].dropna().unique().tolist()):
                cats_in_bat.setdefault(_fund_cats.get(f, "Outros"), []).append(f)

            ordered_cats = [c for c in _cats_ordered if c in cats_in_bat]
            if "Outros" in cats_in_bat:
                ordered_cats.append("Outros")

            # ── Nível 1: botões de categoria (data-batcat para lookup) ──────
            fh.write('<div id="bat-cat-bar" style="margin:14px 0 6px">')
            fh.write(
                f'<button data-batcat="" style="{_btn_base}{_btn_act}" '
                f'onclick="batCatSel(this)">TODOS ({n_qbr_total})</button>'
            )
            for cat in ordered_cats:
                n = qbr_by_cat.get(cat, 0)
                fh.write(
                    f'<button data-batcat="{_esc(cat)}" style="{_btn_base}{_btn_inact}" '
                    f'onclick="batCatSel(this)">{_esc(cat)} ({n})</button>'
                )
            fh.write('</div>')

            # ── Nível 2: grupos de fundos por categoria (data-batcatfunds) ───
            fh.write('<div id="bat-fund-bar" style="margin:2px 0 14px;min-height:32px">')
            # TODOS: sem dropdown de fundo
            fh.write('<div data-batcatfunds="" style="display:block"></div>')
            # Por categoria: dropdown collapsível com a lista de fundos
            for cat in ordered_cats:
                fh.write(f'<div data-batcatfunds="{_esc(cat)}" style="display:none">')
                fh.write(
                    f'<div class="fund-collapse-wrap" style="margin:6px 0 10px">'
                    f'<button class="fund-collapse-btn" onclick="batFundDropToggle(this)">'
                    f'<span data-bat-lbl>Selecionar Fundo</span>'
                    f'<span class="drop-arrow">&#9660;</span>'
                    f'</button>'
                    f'<div class="fund-collapse-panel">'
                )
                for f in cats_in_bat[cat]:
                    n = qbr_by_fund.get(f, 0)
                    fh.write(
                        f'<button class="fund-drop-item" data-batfundo="{_esc(f)}" '
                        f'onclick="batFundSel(this)">{_esc(f)} ({n})</button>'
                    )
                fh.write('</div></div></div>')
            fh.write('</div>')

            if df.empty:
                fh.write(
                    f'<p style="padding:1rem;color:{ITAU_GREEN};font-weight:600">'
                    f'&#10003; Nenhuma discrepância encontrada.</p>'
                )
            else:
                def _fmt_qty(v):
                    if pd.isna(v): return ""
                    return f"{float(v):,.6f}".rstrip("0").rstrip(".")

                fh.write(
                    f'<div class="tbl-wrap"><table class="exp-table">'
                    f'<thead><tr>'
                    f'<th onclick="sortTable(this)">Fundo</th>'
                    f'<th onclick="sortTable(this)">Tipo</th>'
                    f'<th onclick="sortTable(this)">Ativo (ISIN)</th>'
                    f'<th onclick="sortTable(this)">Ticker</th>'
                    f'<th onclick="sortTable(this)">Pos D-1</th>'
                    f'<th onclick="sortTable(this)">Operado</th>'
                    f'<th onclick="sortTable(this)">Pos Esperada</th>'
                    f'<th onclick="sortTable(this)">Pos D</th>'
                    f'<th onclick="sortTable(this)">Diferença</th>'
                    f'<th>Status</th>'
                    f'</tr></thead>'
                    f'<tbody id="bat-tbody">'
                )
                for i, (_, row) in enumerate(df.iterrows()):
                    bg   = f'style="background:{ROW_PAR}"' if i % 2 == 1 else ""
                    cat  = _esc(str(row.get("CATEGORIA", "")))
                    fund = _esc(str(row.get("FUNDO", "")))
                    dif  = row.get("DIFERENCA", 0)
                    fh.write(
                        f'<tr {bg} data-batcat="{cat}" data-batfundo="{fund}">'
                        f'<td class="bold">{row.get("FUNDO","")}</td>'
                        f'<td style="text-align:center">{row.get("TIPO","")}</td>'
                        f'<td>{row.get("ATIVO","")}</td>'
                        f'<td>{row.get("TICKER","")}</td>'
                        f'<td style="text-align:right">{_fmt_qty(row.get("POS_D1"))}</td>'
                        f'<td style="text-align:right">{_fmt_qty(row.get("OPERADO"))}</td>'
                        f'<td style="text-align:right">{_fmt_qty(row.get("POS_ESPERADA"))}</td>'
                        f'<td style="text-align:right">{_fmt_qty(row.get("POS_D"))}</td>'
                        f'<td style="text-align:right;color:{ITAU_RED};font-weight:600">'
                        f'{_fmt_qty(dif)}</td>'
                        f'<td style="text-align:center">'
                        f'<span style="display:inline-block;padding:1px 8px;border-radius:9px;'
                        f'background:{ITAU_RED};color:#fff;font-size:.75rem;font-weight:700">'
                        f'VERIFICAR</span></td>'
                        f'</tr>'
                    )
                fh.write('</tbody></table></div>')

            # ── JS inline ─────────────────────────────────────────────────────────
            fh.write(
                f'<script>'
                f'var _B="{_btn_base}",_BA="{_btn_act}",_BI="{_btn_inact}";'
                'var _bcat="",_bfund="";'

                # Abre/fecha dropdown de fundo de uma categoria
                'function batFundDropToggle(btn){'
                '  var panel=btn.nextElementSibling;'
                '  if(!panel)return;'
                '  var open=panel.classList.toggle("open");'
                '  var arrow=btn.querySelector(".drop-arrow");'
                '  if(arrow)arrow.innerHTML=open?"&#9650;":"&#9660;";'
                '}'

                # Seleciona categoria
                'function batCatSel(btn){'
                '  _bcat=btn.dataset.batcat;_bfund="";'
                # atualiza estilo dos botões de categoria
                '  document.querySelectorAll("#bat-cat-bar button").forEach(function(b){'
                '    b.style.cssText=_B+(b===btn?_BA:_BI);'
                '  });'
                # mostra/oculta grupo de fundo da categoria
                '  document.querySelectorAll("#bat-fund-bar [data-batcatfunds]").forEach(function(d){'
                '    d.style.display=d.dataset.batcatfunds===_bcat?"block":"none";'
                '  });'
                # fecha qualquer dropdown de fundo aberto e reseta labels
                '  document.querySelectorAll("#bat-fund-bar .fund-collapse-panel.open").forEach(function(p){'
                '    p.classList.remove("open");'
                '    var a=p.previousElementSibling&&p.previousElementSibling.querySelector(".drop-arrow");'
                '    if(a)a.innerHTML="&#9660;";'
                '  });'
                '  document.querySelectorAll("#bat-fund-bar [data-bat-lbl]").forEach(function(s){'
                '    s.textContent="Selecionar Fundo";'
                '  });'
                '  document.querySelectorAll("#bat-fund-bar .fund-drop-item.active").forEach(function(b){'
                '    b.classList.remove("active");'
                '  });'
                '  var sec=document.getElementById("bat-pos-sec");'
                '  if(sec)sec.style.display="none";'
                '  _batFilter();'
                '}'

                # Seleciona fundo dentro do dropdown
                'function batFundSel(btn){'
                '  _bfund=btn.dataset.batfundo;'
                # marca ativo no dropdown
                '  var panel=btn.closest(".fund-collapse-panel");'
                '  if(panel){'
                '    panel.querySelectorAll(".fund-drop-item").forEach(function(b){'
                '      b.classList.toggle("active",b===btn);'
                '    });'
                # fecha dropdown e atualiza label do botão
                '    panel.classList.remove("open");'
                '    var colBtn=panel.previousElementSibling;'
                '    if(colBtn){'
                '      var lbl=colBtn.querySelector("[data-bat-lbl]");'
                '      if(lbl)lbl.textContent=btn.textContent;'
                '      var arrow=colBtn.querySelector(".drop-arrow");'
                '      if(arrow)arrow.innerHTML="&#9660;";'
                '    }'
                '  }'
                '  _batFilter();'
                # mostra posições do fundo
                '  var sec=document.getElementById("bat-pos-sec");'
                '  var ttl=document.getElementById("bat-pos-ttl");'
                '  if(_bfund&&sec){'
                '    sec.style.display="";'
                '    var nm=btn.textContent.replace(/\\s*\\(\\d+\\)\\s*$/,"");'
                '    if(ttl)ttl.textContent="Posições — "+nm;'
                '    document.querySelectorAll("#bat-pos-tbody tr").forEach(function(r){'
                '      r.style.display=r.dataset.batfundo===_bfund?"":"none";'
                '    });'
                '  } else if(sec){sec.style.display="none";}'
                '}'

                'function _batFilter(){'
                '  var n=0;'
                '  document.querySelectorAll("#bat-tbody tr").forEach(function(r){'
                '    var ok=_bfund?r.dataset.batfundo===_bfund:(!_bcat||r.dataset.batcat===_bcat);'
                '    r.style.display=ok?"":"none";'
                '    if(ok)n++;'
                '  });'
                '  var el=document.getElementById("bat-card-n");'
                '  if(el)el.textContent=n.toLocaleString("pt-BR");'
                '}'
                '</script>'
            )

            # ── Seção de posições por ativo (aparece ao selecionar um fundo) ──
            bat_fundos = set(df["FUNDO"].dropna().unique()) if not df.empty else set()
            pos_bat = (posicoes_df[posicoes_df["FUNDO"].isin(bat_fundos)].copy()
                       if posicoes_df is not None and not posicoes_df.empty
                       else pd.DataFrame())

            fh.write(
                f'<div id="bat-pos-sec" style="display:none;margin-top:24px">'
                f'<h3 id="bat-pos-ttl" style="margin:0 0 8px;color:{ITAU_DARK};font-size:1rem">'
                f'Posições</h3>'
            )

            if pos_bat.empty:
                fh.write(
                    f'<p style="color:#888;font-size:.85rem">'
                    f'Sem dados de posição disponíveis (VW_FUNDOS_POSICAO).</p>'
                )
            else:
                fh.write(
                    f'<div class="tbl-wrap"><table class="exp-table">'
                    f'<thead><tr>'
                    f'<th onclick="sortTable(this)">Tipo</th>'
                    f'<th onclick="sortTable(this)">Ticker</th>'
                    f'<th onclick="sortTable(this)">Ativo</th>'
                    f'<th onclick="sortTable(this)">Moeda</th>'
                    f'<th onclick="sortTable(this)">Valor (R$)</th>'
                    f'<th onclick="sortTable(this)">% PL</th>'
                    f'<th onclick="sortTable(this)">PnL Total</th>'
                    f'<th onclick="sortTable(this)">PnL MTM</th>'
                    f'<th onclick="sortTable(this)">PnL Carrego</th>'
                    f'<th onclick="sortTable(this)">PnL Câmbio</th>'
                    f'<th onclick="sortTable(this)">Setor</th>'
                    f'</tr></thead>'
                    f'<tbody id="bat-pos-tbody">'
                )
                for i, (_, row) in enumerate(pos_bat.iterrows()):
                    bg   = f'style="background:{ROW_PAR}"' if i % 2 == 1 else ""
                    fund = _esc(str(row.get("FUNDO", "")))
                    pnl  = row.get("PNL_TOTAL", 0)
                    pnl_c = (f'color:{ITAU_GREEN}' if (not pd.isna(pnl) and float(pnl) >= 0)
                             else f'color:{ITAU_RED}')
                    perc = row.get("PERC_PL", None)
                    perc_s = _fmt_pct(perc) if perc is not None else ""
                    fh.write(
                        f'<tr {bg} data-batfundo="{fund}" style="display:none">'
                        f'<td>{row.get("TIPO","")}</td>'
                        f'<td class="bold">{row.get("TICKER","")}</td>'
                        f'<td>{row.get("ATIVO","")}</td>'
                        f'<td>{row.get("MOEDA","")}</td>'
                        f'<td style="text-align:right">{_fmt_money(row.get("VALOR"))}</td>'
                        f'<td style="text-align:right">{perc_s}</td>'
                        f'<td style="text-align:right;{pnl_c};font-weight:600">'
                        f'{_fmt_money(pnl)}</td>'
                        f'<td style="text-align:right">{_fmt_money(row.get("PNL_MTM"))}</td>'
                        f'<td style="text-align:right">{_fmt_money(row.get("PNL_CARREGO"))}</td>'
                        f'<td style="text-align:right">{_fmt_money(row.get("PNL_CAMBIO"))}</td>'
                        f'<td>{row.get("SETOR","")}</td>'
                        f'</tr>'
                    )
                fh.write('</tbody></table></div>')

            fh.write('</div>')  # fecha bat-pos-sec

        _write(fh, '</div></div><script>')
        _write(fh, js_base)
        _write(fh, '</script></body></html>')

    print(f"  [OK] Batimento HTML: {nome}")


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

    reports_js = json.dumps(
        {ts.strftime("%Y-%m-%d"): href for ts, _, href in items},
        ensure_ascii=False
    )

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

    .cal-legend {{ padding: 10px 14px 14px; display: flex; gap: 18px; flex-wrap: wrap;
                   border-top: 1px solid {ITAU_GRAY}; }}
    .leg-item {{ display: flex; align-items: center; gap: 7px;
                 font-size: .74rem; color: #555; }}
    .leg-swatch {{ display: inline-block; width: 13px; height: 13px;
                   border-radius: 3px; flex-shrink: 0; }}

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
    let curMonth = {init_month - 1};

    function renderCal() {{
      const title = document.getElementById('cal-title');
      const grid  = document.getElementById('cal-grid');
      title.textContent = MONTHS[curMonth] + ' ' + curYear;
      grid.innerHTML = '';

      const today = new Date();
      const first = new Date(curYear, curMonth, 1).getDay();
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
