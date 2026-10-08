
# ─────────────────────────────────────────────
# Relatório HTML — Performance Attribution
#
# Mesmo padrão visual do relatório exposicao_html (cores Itaú, header/nav em
# abas, tabelas ordenáveis, cascata em SVG com tooltip) — mas
# autocontido: não importa nada de exposicao_html (projetos irmãos aqui não
# se importam entre si), só replica o mesmo estilo.
#
# Autor: Fabricio Levy
# ─────────────────────────────────────────────


import os
import json
import math
import base64
import pandas as pd


# ── Paleta Itaú (igual a exposicao_html/src/config.py) ────────────────────────
ITAU_DARK   = "#000D3C"
ITAU_ORANGE = "#EC7000"
ITAU_GRAY   = "#e0e0e0"
ITAU_GRAY2  = "#aaaaaa"
ITAU_RED    = "#c0392b"
ITAU_GREEN  = "#1e7e34"
ROW_PAR     = "#eaf0fb"


_DIR = os.path.dirname(os.path.abspath(__file__))
# Logo compartilhado com exposicao_html (se não existir, a página fica sem logo).
_LOGO_PATH = os.path.join(_DIR, "..", "..", "exposicao_html", "input", "logo.png")



def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace('"', "&quot;")
            .replace("'", "&#39;").replace("<", "&lt;").replace(">", "&gt;"))



def _fmt_bps(v) -> str:
    try:
        if v is None or pd.isna(v):
            return "—"
        return f"{float(v):+,.2f}"
    except Exception:
        return "—"



def _logo_tag() -> str:
    if not os.path.exists(_LOGO_PATH):
        return ""
    with open(_LOGO_PATH, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f'<img src="data:image/png;base64,{b64}" class="logo-img" alt="Itaú">'



# ─────────────────────────────────────────────────────────────────────────────
# CSS / JS
# ─────────────────────────────────────────────────────────────────────────────


def _build_css() -> str:
    return f"""
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


    .nav-wrapper {{ position: sticky; top: 0; z-index: 100; box-shadow: 0 3px 10px rgba(0,0,0,.09); }}
    .perf-nav {{ background: #fff; display: flex; gap: 6px; flex-wrap: wrap;
                 padding: 12px 40px; border-bottom: 2px solid {ITAU_GRAY}; }}
    .perf-tab-btn {{ padding: 8px 22px; border: 2px solid {ITAU_ORANGE}; border-radius: 20px;
                     background: #fff; color: {ITAU_ORANGE}; font-weight: 700; font-size: .84rem;
                     cursor: pointer; transition: all .17s; white-space: nowrap; letter-spacing: .04em; }}
    .perf-tab-btn:hover {{ background: {ITAU_ORANGE}18; }}
    .perf-tab-btn.active {{ background: {ITAU_ORANGE}; color: #fff; box-shadow: 0 2px 10px {ITAU_ORANGE}55; }}
    .perf-pane {{ display: none; animation: fadeIn .2s; }}
    .perf-pane.active {{ display: block; }}
    @keyframes fadeIn {{ from {{ opacity:0; transform:translateY(4px); }} to {{ opacity:1; transform:none; }} }}


    .content {{ padding: 28px 40px 50px; }}
    .aba-title {{ font-size: 1rem; font-weight: 700; color: {ITAU_ORANGE}; margin-bottom: 14px;
                  text-transform: uppercase; letter-spacing: .08em; }}


    .tbl-wrap {{ overflow-x: auto; border-radius: 10px; box-shadow: 0 2px 16px rgba(0,0,0,.10); }}
    .exp-table {{ border-collapse: collapse; width: 100%; font-size: .83rem; background: #fff; min-width: 500px; }}
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
    .exp-table tr.soma-row {{ background: #D9E1F2 !important; font-weight: 700; }}
    .bold {{ font-weight: 700; }}


    .pnl-chart-box {{ background: #fff; border-radius: 10px; padding: 16px 20px;
                      box-shadow: 0 2px 12px rgba(0,0,0,.08); overflow: hidden; margin-bottom: 20px; }}
    .pnl-chart-title {{ font-size: .82rem; font-weight: 700; color: {ITAU_DARK};
                        text-transform: uppercase; letter-spacing: .05em; margin-bottom: 10px; }}


    .mes-select {{ padding: 6px 14px; border: 1.5px solid {ITAU_GRAY}; border-radius: 8px;
                   font-size: .84rem; font-family: inherit; outline: none; cursor: pointer; }}
    .mes-select:focus {{ border-color: {ITAU_ORANGE}; }}


    .svg-bar {{ cursor: pointer; transition: opacity .12s, filter .12s; }}
    .svg-bar:hover {{ opacity: 1 !important; filter: brightness(1.14) drop-shadow(0 2px 6px rgba(0,0,0,.22)); }}
    #svg-chart-tip {{ position: fixed; background: #1a1a2e; color: #fff; padding: 7px 14px;
                      border-radius: 8px; font-size: .78rem; pointer-events: none; display: none;
                      z-index: 9999; box-shadow: 0 3px 14px rgba(0,0,0,.38); white-space: nowrap;
                      line-height: 1.5; border-left: 3px solid {ITAU_ORANGE}; }}
    #svg-chart-tip .tt-head {{ font-weight: 700; margin-bottom: 3px; }}
    #svg-chart-tip .tt-row {{ display: flex; align-items: center; gap: 8px; }}
    #svg-chart-tip .tt-key {{ width: 14px; height: 3px; border-radius: 2px; flex: none; }}
    #svg-chart-tip .tt-row strong {{ min-width: 62px; text-align: right; font-variant-numeric: tabular-nums; }}
    #svg-chart-tip .tt-name {{ color: #c3c8d6; }}


    .hist-legenda {{ display: flex; flex-wrap: wrap; align-items: center; gap: 6px 22px;
                     margin-bottom: 10px; font-size: .8rem; color: {ITAU_DARK}; }}
    .hist-leg {{ display: inline-flex; align-items: center; gap: 7px; }}
    .hist-leg-toggle {{ cursor: pointer; user-select: none; }}
    .hist-leg-toggle input {{ margin: 0; cursor: pointer; accent-color: {ITAU_DARK}; }}
    .hist-leg-toggle:has(input:not(:checked)) {{ opacity: .45; }}
    .hist-key {{ display: inline-block; width: 18px; height: 3px; border-radius: 2px; }}
    .hist-nota {{ margin-left: auto; color: #7a8194; }}


    .footer {{ background: #fff; border-top: 3px solid {ITAU_DARK}; padding: 16px 40px;
               font-size: .78rem; color: {ITAU_GRAY2}; font-style: italic; text-align: center; }}


    .aviso {{ color: #888; font-style: italic; padding: 20px 0; }}
    """



def _build_js() -> str:
    return r"""
    const tip = document.createElement('div');
    tip.id = 'svg-chart-tip';
    document.body.appendChild(tip);


    function posicionarTip(e) {
      let x = e.clientX + 16, y = e.clientY - 44;
      if (x + tip.offsetWidth > window.innerWidth - 8) x = e.clientX - tip.offsetWidth - 16;
      if (y + tip.offsetHeight > window.innerHeight - 8) y = window.innerHeight - tip.offsetHeight - 8;
      if (y < 8) y = e.clientY + 16;
      tip.style.left = x + 'px'; tip.style.top = y + 'px';
    }


    document.addEventListener('mouseover', function(e){
      const el = e.target.closest && e.target.closest('.svg-bar[data-tip]');
      if (el) { tip.innerHTML = el.dataset.tip; tip.style.display = 'block'; posicionarTip(e); }
    });
    document.addEventListener('mouseout', function(e){
      if (e.target.closest && e.target.closest('.svg-bar[data-tip]')) tip.style.display = 'none';
    });
    document.addEventListener('mousemove', function(e){
      if (tip.style.display === 'block') posicionarTip(e);
    });


    // Gráfico de Histórico: crosshair que "gruda" no mês mais próximo do mouse
    // — linha vertical + ponto em cada série visível + tooltip com todas elas.
    // Os dados de cada gráfico vêm em JSON no data-hist do retângulo
    // .hist-overlay (montado em _build_historico_svg).
    const histCache = new WeakMap();
    function histDados(ov) {
      if (!histCache.has(ov)) histCache.set(ov, JSON.parse(ov.dataset.hist));
      return histCache.get(ov);
    }
    function fmtSinal(v, casas) {
      return (v > 0 ? '+' : '') + v.toLocaleString('en-US',
        {minimumFractionDigits: casas, maximumFractionDigits: casas});
    }
    function linhaTip(cor, valor, nome) {
      const row = document.createElement('div'); row.className = 'tt-row';
      const key = document.createElement('span'); key.className = 'tt-key'; key.style.background = cor;
      const val = document.createElement('strong'); val.textContent = valor;
      const lbl = document.createElement('span'); lbl.className = 'tt-name'; lbl.textContent = nome;
      row.append(key, val, lbl);
      return row;
    }
    document.addEventListener('mousemove', function(e){
      const ov = e.target.closest && e.target.closest('.hist-overlay');
      if (!ov) return;
      const svg = ov.ownerSVGElement, d = histDados(ov), box = ov.closest('.hist-chart');
      const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(svg.getScreenCTM().inverse());
      const i = Math.max(0, Math.min(d.meses.length - 1, Math.floor((p.x - d.x0) / d.slot)));
      const x = d.x0 + (i + 0.5) * d.slot;
      const hv = svg.querySelector('.hist-hover');
      hv.style.display = '';
      const cross = hv.querySelector('.hist-cross');
      cross.setAttribute('x1', x); cross.setAttribute('x2', x);
      tip.replaceChildren();
      const head = document.createElement('div'); head.className = 'tt-head'; head.textContent = d.meses[i];
      tip.appendChild(head);
      d.series.forEach(function(s){
        const dot = hv.querySelector('.hist-dot[data-sid="' + s.sid + '"]');
        if (s.vals[i] === null || (box && box.classList.contains('off-' + s.sid))) {
          dot.style.display = 'none';
          return;
        }
        dot.style.display = '';
        dot.setAttribute('cx', x); dot.setAttribute('cy', s.ys[i]);
        tip.appendChild(linhaTip(s.cor, fmtSinal(s.vals[i], 2) + '%', s.nome));
      });
      if (d.bps && d.bps[i] !== null)
        tip.appendChild(linhaTip('#8a93a6', fmtSinal(d.bps[i], 1) + ' bps', 'atribuição no mês'));
      tip.style.display = 'block';
      posicionarTip(e);
    });
    document.addEventListener('mouseout', function(e){
      const ov = e.target.closest && e.target.closest('.hist-overlay');
      if (!ov) return;
      ov.ownerSVGElement.querySelector('.hist-hover').style.display = 'none';
      tip.style.display = 'none';
    });


    document.querySelectorAll('.perf-tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.perf-tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.perf-pane').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        const pane = document.getElementById(btn.dataset.perfPane);
        if (pane) pane.classList.add('active');
      });
    });


    function showMonth(tipo, mes) {
      document.querySelectorAll('.wf-month-' + tipo).forEach(el => el.style.display = 'none');
      const el = document.getElementById('wf-' + tipo + '-' + mes);
      if (el) el.style.display = 'block';
    }


    function parseNum(text) {
      const n = parseFloat(text.replace(/[^\d,.\-+]/g, '').replace(',', '.'));
      return isNaN(n) ? null : n;
    }


    function sortTable(th) {
      const table = th.closest('table');
      const tbody = table.querySelector('tbody');
      const idx   = Array.from(th.parentNode.children).indexOf(th);
      const goAsc = !th.classList.contains('asc');
      th.parentNode.querySelectorAll('th').forEach(t => t.classList.remove('asc', 'desc'));
      th.classList.add(goAsc ? 'asc' : 'desc');
      const rows = Array.from(tbody.querySelectorAll('tr'));
      rows.sort((a, b) => {
        const av = (a.children[idx]?.textContent || '').trim();
        const bv = (b.children[idx]?.textContent || '').trim();
        const an = parseNum(av), bn = parseNum(bv);
        const cmp = (an !== null && bn !== null) ? an - bn : av.localeCompare(bv, 'pt');
        return goAsc ? cmp : -cmp;
      });
      rows.forEach(r => tbody.appendChild(r));
    }


    // Mostra/esconde a linha de benchmark ou Ibovespa no gráfico de Histórico
    // (checkbox da legenda) sem precisar regerar o SVG — alterna a
    // visibilidade do <g class="hist-serie-{serieId}"> e marca o container
    // com 'off-{serieId}' (o crosshair usa isso pra pular a série no tooltip).
    function toggleHistSerie(checkbox, chartId, serieId) {
      const container = document.getElementById(chartId);
      if (!container) return;
      container.classList.toggle('off-' + serieId, !checkbox.checked);
      container.querySelectorAll('.hist-serie-' + serieId).forEach(el => {
        el.style.display = checkbox.checked ? '' : 'none';
      });
    }
    """



# ─────────────────────────────────────────────────────────────────────────────
# SVG — cascata (waterfall) e histórico (colunas + linha)
# ─────────────────────────────────────────────────────────────────────────────


def _build_waterfall_svg(components, values, total) -> str:
    """SVG de cascata vertical: um incremento por componente + barra TOTAL."""
    bar_data = []
    running = 0.0
    for label, val in zip(components, values):
        bar_data.append((label, running, running + val, ITAU_GREEN if val >= 0 else ITAU_RED, False))
        running += val
    bar_data.append(("TOTAL", 0.0, total, ITAU_DARK, True))
    n = len(bar_data)


    W  = 760
    PB = 68 if n > 10 else 52
    H  = 260 + (PB - 52)
    PLm, PR, PT = 78, 16, 20
    chart_w = W - PLm - PR
    chart_h = H - PT - PB
    bar_slot = chart_w / n
    bar_w = bar_slot * 0.62
    bar_off = bar_slot * 0.19


    all_ys = [s for _, s, e, _, _ in bar_data] + [e for _, s, e, _, _ in bar_data] + [0.0]
    y_min, y_max = min(all_ys), max(all_ys)
    pad = max((y_max - y_min) * 0.15, abs(total) * 0.15, 1.0)
    y_lo, y_hi = y_min - pad, y_max + pad
    y_range = y_hi - y_lo or 1.0


    def _to_y(v: float) -> float:
        return PT + chart_h * (1.0 - (v - y_lo) / y_range)


    els = [f'<rect x="{PLm}" y="{PT}" width="{chart_w}" height="{chart_h}" fill="#f8f9fc" rx="4"/>']
    for k in range(5):
        frac = k / 4
        v_grid = y_lo + frac * y_range
        yg = PT + chart_h * (1 - frac)
        els.append(f'<line x1="{PLm}" y1="{yg:.1f}" x2="{W-PR}" y2="{yg:.1f}" stroke="#e4e8ef" stroke-width="1"/>')
        els.append(f'<text x="{PLm-5}" y="{yg+4:.1f}" text-anchor="end" font-size="9" fill="#999" '
                   f'font-family="Segoe UI,Arial,sans-serif">{v_grid:+,.1f}</text>')


    zero_y = _to_y(0.0)
    if y_lo < 0 < y_hi:
        els.append(f'<line x1="{PLm}" y1="{zero_y:.1f}" x2="{W-PR}" y2="{zero_y:.1f}" '
                   f'stroke="#aaa" stroke-width="1.4" stroke-dasharray="5,3"/>')


    _many = n > 10
    prev_end_y = None
    for i, (label, start, end, color, is_total) in enumerate(bar_data):
        bx = PLm + i * bar_slot + bar_off
        cx = bx + bar_w / 2
        y_top = _to_y(max(start, end))
        y_bot = _to_y(min(start, end))
        bh = max(y_bot - y_top, 2.0)
        val = end - start


        if prev_end_y is not None and not is_total:
            prev_right = PLm + (i - 1) * bar_slot + bar_off + bar_w
            els.append(f'<line x1="{prev_right:.1f}" y1="{prev_end_y:.1f}" x2="{bx:.1f}" y2="{prev_end_y:.1f}" '
                       f'stroke="#c8d0dc" stroke-width="1.2" stroke-dasharray="4,3"/>')


        opacity = "0.88" if is_total else "0.82"
        # _fmt_bps já sai com sinal (+/-) — não prefixar outro "+".
        tip = (f"TOTAL: {_fmt_bps(val)} bps" if is_total
               else f"{_esc(label)}: {_fmt_bps(val)} bps | acum.: {_fmt_bps(end)} bps")
        els.append(f'<rect x="{bx:.1f}" y="{y_top:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
                   f'fill="{color}" opacity="{opacity}" rx="3" class="svg-bar" data-tip="{tip}"/>')


        if is_total or (bh >= 16 and not _many):
            label_y = y_top - 5 if val >= 0 else y_bot + 13
            els.append(f'<text x="{cx:.1f}" y="{label_y:.1f}" text-anchor="middle" font-size="9.5" '
                       f'font-weight="bold" fill="{color}" font-family="Segoe UI,Arial,sans-serif">'
                       f'{_fmt_bps(val)}</text>')


        ly = H - PB + 14
        angle = f'rotate(-45,{cx:.1f},{ly:.1f})'
        show_label = is_total or not _many or i % max(1, n // 10) == 0
        if show_label:
            lbl = _esc(str(label))[:22]
            els.append(f'<text x="{cx:.1f}" y="{ly:.1f}" text-anchor="end" font-size="10" fill="#444" '
                       f'transform="{angle}" font-family="Segoe UI,Arial,sans-serif">{lbl}</text>')
        prev_end_y = _to_y(end)


    return (f'<svg viewBox="0 0 {W} {H}" style="width:100%;display:block;overflow:visible">'
            + "".join(els) + "</svg>")



# Cores das séries — as MESMAS em todo o relatório (Histórico e Resumo), pra
# cor seguir a entidade (fundo/benchmark/Ibovespa). Trio validado para
# daltonismo comparando todos os pares — o roxo antigo do Ibovespa (#9b59b6)
# ficava indistinguível do azul do benchmark.
_COR_FUNDO     = ITAU_ORANGE
_COR_BENCHMARK = "#2A78D6"
_COR_IBOV      = "#4A3AA7"

# Tinta dos gráficos — texto/eixos/grade nunca usam a cor de uma série.
_TINTA       = "#1a1a2e"
_TINTA_FRACA = "#7a8194"
_GRADE       = "#e6e9f0"
_BASE        = "#b9c0cf"

_MESES_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
             "Jul", "Ago", "Set", "Out", "Nov", "Dez"]



def _escala_percentil(vals, p_baixo=0.03, p_alto=0.97, pad_frac=0.2, min_pad=1.0):
    """Faixa [lo, hi] pro eixo bps do gráfico, baseada em percentil em vez de
    min/max puro — um único mês com valor fora da curva (ex.: atribuição de
    RV histórico de um mês de euforia/pânico isolado) não deve esmagar a
    escala e deixar todos os outros meses parecendo "sem barra". Barras fora
    da faixa ficam visualmente cortadas no limite do gráfico — o valor real
    continua certo no tooltip/tabela, só a altura é limitada."""
    validos = sorted(v for v in vals if v is not None)
    if not validos:
        return -1.0, 1.0
    n = len(validos)
    if n >= 10:
        lo = validos[max(0, int(round(p_baixo * (n - 1))))]
        hi = validos[min(n - 1, int(round(p_alto * (n - 1))))]
    else:
        lo, hi = validos[0], validos[-1]
    lo, hi = min(lo, 0.0), max(hi, 0.0)
    pad = max((hi - lo) * pad_frac, min_pad)
    return lo - pad, hi + pad



def _ticks_redondos(lo, hi, n_alvo=5):
    """Ticks "redondos" (passo 1 / 2 / 2,5 / 5 × 10^k) cobrindo [lo, hi].
    Devolve (ticks, passo) — o 1º e o último tick viram os limites do eixo,
    então o gráfico nunca mostra valores quebrados como +12,3% na grade."""
    if hi - lo <= 0:
        lo, hi = lo - 1.0, hi + 1.0
    bruto = (hi - lo) / n_alvo
    mag = 10 ** math.floor(math.log10(bruto))
    passo = next(m * mag for m in (1, 2, 2.5, 5, 10) if bruto <= m * mag * (1 + 1e-9))
    ini = math.floor(lo / passo + 1e-9) * passo
    fim = math.ceil(hi / passo - 1e-9) * passo
    return [ini + k * passo for k in range(int(round((fim - ini) / passo)) + 1)], passo



def _dominio_eixo(lo, hi, n_alvo=5):
    """(y_lo, y_hi, ticks, passo) do eixo Y dos gráficos SVG: ticks redondos
    (_ticks_redondos), mas cada limite só "pula" até o próximo tick quando
    isso desperdiça no máximo meio passo — senão fica rente ao dado (folga
    de 4%). Evita, p.ex., um eixo descendo até -200% por causa de um -6%."""
    ticks, passo = _ticks_redondos(lo, hi, n_alvo)
    folga = 0.04 * ((hi - lo) or 1.0)
    y_lo = ticks[0] if lo - ticks[0] <= passo / 2 else lo - folga
    y_hi = ticks[-1] if ticks[-1] - hi <= passo / 2 else hi + folga
    return y_lo, y_hi, [t for t in ticks if y_lo - 1e-9 <= t <= y_hi + 1e-9], passo



def _fmt_tick(v, passo, sufixo="") -> str:
    """Rótulo de tick com só as casas decimais que o passo pede — sem '+'
    (eixo é referência, não variação); só os negativos levam sinal."""
    if abs(v) < passo * 1e-6:
        return f"0{sufixo}"
    casas = next(c for c in (0, 1, 2) if abs(passo * 10 ** c - round(passo * 10 ** c)) < 1e-6 or c == 2)
    return f"{v:,.{casas}f}{sufixo}"



def _mes_ano(rotulo):
    """'Jul/25' -> (7, 2025); None se o rótulo não estiver nesse formato."""
    try:
        nome, aa = str(rotulo).split("/")
        return _MESES_PT.index(nome) + 1, 2000 + int(aa)
    except ValueError:
        return None



def _rotulos_eixo_x(meses_rotulo, slot):
    """[(índice, texto)] dos meses que ganham rótulo no eixo X. O passo
    (mensal → trimestral → semestral → anual → ...) é o menor que cabe na
    horizontal, sem girar o texto, ancorado no calendário (jan/abr/jul/out);
    a partir do anual o rótulo vira só o ano ('2019')."""
    datas = [_mes_ano(m) for m in meses_rotulo]
    if any(d is None for d in datas):             # rótulo fora do padrão 'Mmm/aa'
        k = max(1, math.ceil(56 / slot))
        return [(i, str(m)) for i, m in enumerate(meses_rotulo) if i % k == 0]

    passo = next((p for p in (1, 3, 6, 12, 24, 60, 120) if p * slot >= (44 if p >= 12 else 56)), 120)
    rotulos = []
    for i, (mes, ano) in enumerate(datas):
        if passo < 12 and (mes - 1) % passo == 0:
            rotulos.append((i, str(meses_rotulo[i])))
        elif passo >= 12 and mes == 1 and ano % (passo // 12) == 0:
            rotulos.append((i, str(ano)))
    return rotulos or [(0, str(meses_rotulo[0]))]



def _path_com_lacunas(pontos) -> str:
    """'M x y L x y ...' que levanta a caneta nos meses sem dado (None), em
    vez de ligar os dois lados da lacuna com uma reta inventada."""
    d, caneta = [], False
    for p in pontos:
        if p is None:
            caneta = False
            continue
        d.append(f"{'L' if caneta else 'M'}{p[0]:.1f} {p[1]:.1f}")
        caneta = True
    return " ".join(d)



def _build_historico_svg(meses_rotulo, bps_vals, series, mostrar_barras=True) -> str:
    """Gráfico de linha do Histórico: retorno acumulado (%) do fundo e das
    séries de comparação (benchmark, Ibovespa...) num ÚNICO eixo Y, com
    ticks redondos, eixo X por calendário (mês/trimestre/ano, sem texto
    girado) e o valor final de cada série rotulado na ponta da linha.

    `series`: lista de (serie_id, nome, valores, cor), com o fundo em 1º —
    ele é a linha principal (mais grossa, desenhada por cima, com área suave
    até o zero). `valores` tem o tamanho de `meses_rotulo`, com None nos
    meses sem dado. Cada série de comparação fica num <g class="hist-serie
    hist-serie-{serie_id}"> (linha + ponto/rótulo final), que o checkbox da
    legenda mostra/esconde via JS sem regerar o gráfico.

    Passando o mouse, um crosshair gruda no mês mais próximo e o tooltip
    lista todas as séries visíveis naquele mês (ver _build_js) — os dados
    vão em JSON no data-hist do retângulo .hist-overlay.

    `mostrar_barras`: acrescenta, ABAIXO, um painel próprio com a atribuição
    mensal (bps) no mesmo eixo X — painel separado em vez de eixo duplo,
    que inventaria correlação entre duas escalas arbitrárias. `bps_vals` tem
    None nos meses sem atribuição.
    """
    n = len(meses_rotulo)
    series = [s for s in series if any(v is not None for v in s[2])]
    if n == 0 or not series:
        return ""


    W, PL, PR, PT = 1000, 64, 96, 16
    H_LINHA, GAP_BARRAS, H_BARRAS, H_EIXO_X = 330, 40, 120, 30
    chart_w = W - PL - PR
    slot = chart_w / n
    base_linha = PT + H_LINHA
    topo_barras = base_linha + GAP_BARRAS
    base_plot = topo_barras + H_BARRAS if mostrar_barras else base_linha
    H = base_plot + H_EIXO_X


    def _x(i): return PL + (i + 0.5) * slot


    todos = [v for _, _, vals, _ in series for v in vals if v is not None] + [0.0]
    y_lo, y_hi, ticks, passo = _dominio_eixo(min(todos), max(todos))


    def _y(v): return PT + H_LINHA * (1 - (v - y_lo) / (y_hi - y_lo))


    # Grade horizontal (hairline sólida, o zero um tom mais forte) + eixo Y;
    # a base do painel ganha uma linha mesmo quando não cai num tick.
    els = [f'<line x1="{PL}" y1="{base_linha}" x2="{W - PR}" y2="{base_linha}" '
           f'stroke="{_GRADE}" stroke-width="1"/>']
    for t in ticks:
        yg = _y(t)
        eh_zero = abs(t) < passo * 1e-6
        els.append(f'<line x1="{PL}" y1="{yg:.1f}" x2="{W - PR}" y2="{yg:.1f}" '
                   f'stroke="{_BASE if eh_zero else _GRADE}" stroke-width="1"/>')
        els.append(f'<text x="{PL - 8}" y="{yg + 4:.1f}" text-anchor="end" font-size="11" '
                   f'fill="{_TINTA_FRACA}">{_fmt_tick(t, passo, "%")}</text>')


    pontos = [[(_x(i), _y(v)) if v is not None else None for i, v in enumerate(vals)]
              for _, _, vals, _ in series]


    # Área suave (~8%) só sob a linha principal, fechando no zero.
    pts_area = [p for p in pontos[0] if p is not None]
    if len(pts_area) > 1:
        y0 = _y(0.0)
        area = (f"M{pts_area[0][0]:.1f} {y0:.1f} "
                + " ".join(f"L{x:.1f} {y:.1f}" for x, y in pts_area)
                + f" L{pts_area[-1][0]:.1f} {y0:.1f} Z")
        els.append(f'<path d="{area}" fill="{series[0][3]}" fill-opacity="0.08"/>')


    # Valor final na ponta de cada linha. Rótulos que colidiriam são
    # afastados na vertical (mín. 15px) e ganham um fio-guia até a ponta da
    # sua linha — assim o número nunca fica "solto" longe da série.
    finais = {}
    for k, (_, _, vals, _) in enumerate(series):
        i_fim = max((i for i, v in enumerate(vals) if v is not None), default=None)
        if i_fim is not None:
            finais[k] = (_x(i_fim), _y(vals[i_fim]), vals[i_fim])
    ordem = sorted(finais, key=lambda k: finais[k][1])
    y_rot = {k: min(max(finais[k][1], PT + 6), base_linha - 6) for k in ordem}
    for a, b in zip(ordem, ordem[1:]):
        y_rot[b] = max(y_rot[b], y_rot[a] + 15)
    if ordem:
        y_rot[ordem[-1]] = min(y_rot[ordem[-1]], base_linha - 6)
        for a, b in zip(reversed(ordem[:-1]), reversed(ordem[1:])):
            y_rot[a] = min(y_rot[a], y_rot[b] - 15)
    x_rotulo = _x(n - 1) + 18


    # Linhas: comparações primeiro, fundo por último (fica por cima).
    for k in range(len(series) - 1, -1, -1):
        sid, _nome, _vals, cor = series[k]
        principal = k == 0
        partes = [f'<path d="{_path_com_lacunas(pontos[k])}" fill="none" stroke="{cor}" '
                  f'stroke-width="{2.5 if principal else 1.8}" stroke-linejoin="round" stroke-linecap="round"/>']
        if k in finais:
            xf, yf, vf = finais[k]
            yr = y_rot[k]
            if abs(yr - yf) > 1.5 or xf < _x(n - 1) - 0.5:
                partes.append(f'<line x1="{xf + 5:.1f}" y1="{yf:.1f}" x2="{x_rotulo - 4:.1f}" y2="{yr:.1f}" '
                              f'stroke="{_BASE}" stroke-width="1"/>')
            partes.append(f'<circle cx="{xf:.1f}" cy="{yf:.1f}" r="4" fill="{cor}" stroke="#fff" stroke-width="2"/>')
            partes.append(f'<text x="{x_rotulo:.1f}" y="{yr + 4:.1f}" font-size="12" '
                          f'font-weight="{700 if principal else 600}" fill="{_TINTA}">{vf:+,.1f}%</text>')
        classe = "hist-serie-principal" if principal else f"hist-serie hist-serie-{sid}"
        els.append(f'<g class="{classe}">{"".join(partes)}</g>')


    if mostrar_barras:
        b_lo, b_hi, ticks_b, passo_b = _dominio_eixo(
            *_escala_percentil([v for v in bps_vals if v is not None]), n_alvo=3)


        def _yb(v): return topo_barras + H_BARRAS * (1 - (v - b_lo) / (b_hi - b_lo))


        els.append(f'<text x="{PL}" y="{topo_barras - 12}" font-size="11.5" font-weight="600" '
                   f'fill="{_TINTA}">Atribuição mensal (bps)</text>')
        els.append(f'<line x1="{PL}" y1="{base_plot}" x2="{W - PR}" y2="{base_plot}" '
                   f'stroke="{_GRADE}" stroke-width="1"/>')
        for t in ticks_b:
            yg = _yb(t)
            eh_zero = abs(t) < passo_b * 1e-6
            els.append(f'<line x1="{PL}" y1="{yg:.1f}" x2="{W - PR}" y2="{yg:.1f}" '
                       f'stroke="{_BASE if eh_zero else _GRADE}" stroke-width="1"/>')
            els.append(f'<text x="{PL - 8}" y="{yg + 4:.1f}" text-anchor="end" font-size="11" '
                       f'fill="{_TINTA_FRACA}">{_fmt_tick(t, passo_b)}</text>')
        bar_w = min(slot * 0.62, 18)
        for i, v in enumerate(bps_vals):
            if v is None or v == 0:
                continue
            # Barra fora da escala (ver _escala_percentil) fica cortada no
            # limite, com uma "quebra" branca perto da ponta; o valor real
            # continua no tooltip e na tabela.
            v_clip = max(min(v, b_hi), b_lo)
            yt, yb = _yb(max(v_clip, 0.0)), _yb(min(v_clip, 0.0))
            bx = _x(i) - bar_w / 2
            els.append(f'<rect x="{bx:.1f}" y="{yt:.1f}" width="{bar_w:.1f}" height="{max(yb - yt, 1.0):.1f}" '
                       f'fill="{ITAU_GREEN if v > 0 else ITAU_RED}" rx="{min(1.5, bar_w / 2):.1f}"/>')
            if v_clip != v:
                yq = yt + 4 if v > 0 else yb - 4
                els.append(f'<line x1="{bx:.1f}" y1="{yq:.1f}" x2="{bx + bar_w:.1f}" y2="{yq:.1f}" '
                           f'stroke="#fff" stroke-width="1.5"/>')


    for i, texto in _rotulos_eixo_x(meses_rotulo, slot):
        x = _x(i)
        els.append(f'<line x1="{x:.1f}" y1="{base_plot}" x2="{x:.1f}" y2="{base_plot + 5}" '
                   f'stroke="{_BASE}" stroke-width="1"/>')
        els.append(f'<text x="{x:.1f}" y="{base_plot + 19}" text-anchor="middle" font-size="11" '
                   f'fill="{_TINTA_FRACA}">{_esc(texto)}</text>')


    # Camada de hover: crosshair + 1 ponto por série (posicionados via JS) e o
    # retângulo transparente que captura o mouse, com os dados em JSON.
    hover = [f'<line class="hist-cross" x1="0" y1="{PT}" x2="0" y2="{base_plot}" '
             f'stroke="{_TINTA_FRACA}" stroke-width="1"/>']
    hover += [f'<circle class="hist-dot" data-sid="{sid}" cx="0" cy="0" r="4.5" fill="{cor}" '
              f'stroke="#fff" stroke-width="2"/>' for sid, _, _, cor in series]
    els.append(f'<g class="hist-hover" style="display:none" pointer-events="none">{"".join(hover)}</g>')
    dados = {
        "x0": PL, "slot": round(slot, 5), "meses": [str(m) for m in meses_rotulo],
        "series": [{"sid": sid, "nome": str(nome), "cor": cor,
                    "vals": [None if v is None else round(v, 4) for v in vals],
                    "ys": [None if v is None else round(_y(v), 1) for v in vals]}
                   for sid, nome, vals, cor in series],
        "bps": [None if v is None else round(v, 2) for v in bps_vals] if mostrar_barras else None,
    }
    els.append(f'<rect class="hist-overlay" x="{PL}" y="{PT}" width="{chart_w:.1f}" '
               f'height="{base_plot - PT:.1f}" fill="transparent" '
               f'data-hist="{_esc(json.dumps(dados, ensure_ascii=False))}"/>')


    aria = f"Retorno acumulado de {meses_rotulo[0]} a {meses_rotulo[-1]}"
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{_esc(aria)}" '
            f'font-family="Segoe UI,Arial,sans-serif" style="width:100%;display:block;overflow:visible">'
            + "".join(els) + "</svg>")



# ─────────────────────────────────────────────────────────────────────────────
# Tabelas
# ─────────────────────────────────────────────────────────────────────────────


def _build_table(df: pd.DataFrame, coluna_texto="mes", destacar_ultima_linha=True, sufixo="",
                 coluna_bold="TOTAL") -> str:
    cols = list(df.columns)
    th = "".join(f'<th onclick="sortTable(this)" title="Clique para ordenar">{_esc(c)}</th>' for c in cols)


    rows_html = []
    n = len(df)
    for i, (_, row) in enumerate(df.iterrows()):
        is_soma = destacar_ultima_linha and (i == n - 1) and str(row.get(coluna_texto, "")) == "Soma"
        cells = []
        for c in cols:
            v = row.get(c, "")
            if c == coluna_texto:
                cells.append(f'<td class="bold">{_esc(v)}</td>')
                continue
            try:
                is_na = pd.isna(v)
            except Exception:
                is_na = False
            if is_na:
                cells.append('<td></td>')
                continue
            vf = float(v)
            color = ITAU_GREEN if vf > 0 else (ITAU_RED if vf < 0 else "#444")
            cls = "bold" if c == coluna_bold else ""
            cells.append(f'<td class="{cls}" style="color:{color}">{vf:+,.2f}{sufixo}</td>')
        tr_cls = ' class="soma-row"' if is_soma else ""
        rows_html.append(f"<tr{tr_cls}>{''.join(cells)}</tr>")


    return (
        '<div class="tbl-wrap"><table class="exp-table">'
        f'<thead><tr>{th}</tr></thead><tbody>{"".join(rows_html)}</tbody></table></div>'
    )



def _build_periodos_svg(periodos, vals_fundo, vals_bench, vals_ibov, nome_benchmark=None) -> str:
    """Barras agrupadas (fundo x benchmark x Ibovespa) por período padrão
    (MTD/QTD/YTD/12M/24M/36M/ITD)."""
    n = len(periodos)
    if n == 0:
        return ""


    series = [
        ("Fundo", vals_fundo, _COR_FUNDO),
        (nome_benchmark or "Benchmark", vals_bench, _COR_BENCHMARK),
        ("Ibovespa", vals_ibov, _COR_IBOV),
    ]
    series = [(nome, vals, cor) for nome, vals, cor in series if any(v is not None for v in vals)]
    if not series:
        return ""


    W, PT, PB = 760, 34, 52
    H = 280
    PLm, PR = 60, 16
    chart_w = W - PLm - PR
    chart_h = H - PT - PB
    slot = chart_w / n
    n_series = len(series)
    bar_w = (slot * 0.78) / n_series
    grp_off = slot * 0.11


    todos = [v for _, vals, _ in series for v in vals if v is not None] + [0.0]
    y_min, y_max = min(todos), max(todos)
    pad = max((y_max - y_min) * 0.2, 1.0)
    y_lo, y_hi = y_min - pad, y_max + pad
    y_rng = y_hi - y_lo or 1.0


    def _y(v): return PT + chart_h * (1 - (v - y_lo) / y_rng)


    els = [f'<rect x="{PLm}" y="{PT}" width="{chart_w}" height="{chart_h}" fill="#f8f9fc" rx="4"/>']
    for k in range(5):
        frac = k / 4
        yg = PT + chart_h * (1 - frac)
        vg = y_lo + frac * y_rng
        els.append(f'<line x1="{PLm}" y1="{yg:.1f}" x2="{W-PR}" y2="{yg:.1f}" stroke="#e4e8ef" stroke-width="1"/>')
        els.append(f'<text x="{PLm-5}" y="{yg+4:.1f}" text-anchor="end" font-size="9" fill="#999" '
                   f'font-family="Segoe UI,Arial,sans-serif">{vg:+.0f}%</text>')


    zero_y = _y(0.0)
    if y_lo < 0 < y_hi:
        els.append(f'<line x1="{PLm}" y1="{zero_y:.1f}" x2="{W-PR}" y2="{zero_y:.1f}" '
                   f'stroke="#aaa" stroke-width="1.2" stroke-dasharray="5,3"/>')


    lx = PLm
    for nome, _vals, cor in series:
        els.append(f'<rect x="{lx}" y="8" width="12" height="12" fill="{cor}" rx="2"/>')
        els.append(f'<text x="{lx+16}" y="19" font-size="10" fill="#444" '
                   f'font-family="Segoe UI,Arial,sans-serif">{_esc(nome)}</text>')
        lx += 30 + 7 * len(nome)


    for i, periodo in enumerate(periodos):
        base_x = PLm + i * slot + grp_off
        for j, (nome, vals, cor) in enumerate(series):
            v = vals[i]
            if v is None:
                continue
            bx = base_x + j * bar_w
            cx = bx + bar_w / 2
            yt, yb = _y(max(v, 0.0)), _y(min(v, 0.0))
            bh = max(yb - yt, 2.0)
            sign = "+" if v > 0 else ""
            tip = f"{_esc(periodo)} — {_esc(nome)}: {sign}{v:.2f}%"
            els.append(f'<rect x="{bx:.1f}" y="{yt:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
                       f'fill="{cor}" opacity="0.85" rx="2" class="svg-bar" data-tip="{tip}"/>')
        cx_grupo = PLm + i * slot + slot / 2
        ly = H - PB + 18
        els.append(f'<text x="{cx_grupo:.1f}" y="{ly:.1f}" text-anchor="middle" font-size="11" '
                   f'font-weight="bold" fill="#444" '
                   f'font-family="Segoe UI,Arial,sans-serif">{_esc(periodo)}</text>')


    return (f'<svg viewBox="0 0 {W} {H}" style="width:100%;display:block;overflow:visible">'
            + "".join(els) + "</svg>")



def _build_resumo_periodos_pane(periodos_por_mes, rotulo_mes_fn, nome_benchmark,
                                tabelas_mensais=None, df_calendario_comparativo=None) -> str:
    """Aba 'Resumo': tabela + gráfico MTD/QTD/YTD/12M/24M/36M/ITD — com
    dropdown de mês de referência (recalcula tudo "como se hoje fosse"
    aquele mês, mesmo padrão das abas de cascata) — seguidos do calendário
    comparativo Fundo x Benchmark x Alpha e de calendários extras mês a mês
    por ano (ex.: Ibovespa).


    `periodos_por_mes`: dict ordenado {mes_label: df_periodos} — 1 entrada
    por mês com cota disponível (de montar_tabela_periodos, uma por mês).
    """
    meses_com_dado = list(periodos_por_mes)
    if not meses_com_dado:
        return '<p class="aviso">Sem cota disponível para montar o resumo de períodos.</p>'


    rotulo_bench_col = f"{nome_benchmark} (%)" if nome_benchmark else "Benchmark (%)"


    opts = "".join(
        f'<option value="{m}"{" selected" if i == len(meses_com_dado) - 1 else ""}>{rotulo_mes_fn(m)}</option>'
        for i, m in enumerate(meses_com_dado)
    )


    paineis = []
    for m in meses_com_dado:
        df_periodos = periodos_por_mes[m]
        periodos = list(df_periodos["periodo"])
        vals_fundo = [None if pd.isna(v) else float(v) for v in df_periodos["retorno_fundo_pct"]]
        vals_bench = [None if pd.isna(v) else float(v) for v in df_periodos["retorno_benchmark_pct"]]
        vals_ibov = [None if pd.isna(v) else float(v) for v in df_periodos["retorno_ibov_pct"]]
        svg = _build_periodos_svg(periodos, vals_fundo, vals_bench, vals_ibov, nome_benchmark)


        df_fmt = df_periodos.rename(columns={
            "periodo": "Período",
            "retorno_fundo_pct": "Fundo (%)",
            "retorno_benchmark_pct": rotulo_bench_col,
            "retorno_ibov_pct": "Ibovespa (%)",
        })
        tabela = _build_table(df_fmt, coluna_texto="Período", destacar_ultima_linha=False)


        display = "block" if m == meses_com_dado[-1] else "none"
        paineis.append(
            f'<div id="wf-periodos-{m}" class="wf-month-pane wf-month-periodos" style="display:{display}">'
            f'{svg}<h2 class="aba-title">Tabela — MTD / QTD / YTD / 12M / 24M / 36M / ITD</h2>'
            f'{tabela}</div>'
        )


    sec_periodos = (
        f'<div class="pnl-chart-box">'
        f'<div class="pnl-chart-title">Performance por período — fundo x benchmark x Ibovespa</div>'
        f'<div style="margin-bottom:12px">'
        f'<label style="font-size:.82rem;font-weight:600;color:{ITAU_DARK};margin-right:8px">'
        f'Mês de referência:</label>'
        f'<select class="mes-select" onchange="showMonth(\'periodos\', this.value)">{opts}</select>'
        f'</div>{"".join(paineis)}</div>'
    )


    sec_comparativo = _build_calendario_comparativo_html(df_calendario_comparativo)
    sec_mensais = "".join(
        _build_tabela_mensal_anual_html(titulo, df_cal) for titulo, df_cal in (tabelas_mensais or [])
    )
    return sec_periodos + sec_comparativo + sec_mensais



def _build_tabela_mensal_anual_html(titulo, df_cal) -> str:
    """Calendário Ano x Jan..Dez + Acum. Ano, pra uma única série (Fundo,
    Benchmark ou Ibovespa)."""
    if df_cal is None or df_cal.empty:
        return ""
    return (
        f'<h2 class="aba-title">{_esc(titulo)}</h2>'
        f'{_build_table(df_cal, coluna_texto="Ano", destacar_ultima_linha=False, coluna_bold="Acum. Ano")}'
    )



def _build_calendario_comparativo_html(df_cal, titulo="Retornos Mensais") -> str:
    """Calendário comparativo Ano x Jan..Dez — 3 linhas por ano (Fundo,
    Benchmark, Alpha), com a coluna 'Year' mesclada (rowspan) a cada bloco
    de 3 linhas. Meses sem dado aparecem como '-', igual ao formato pedido.
    """
    if df_cal is None or df_cal.empty:
        return ""


    meses = [c for c in df_cal.columns if c not in ("Ano", "Série", "Accumulated")]


    def _cel(v, negrito=False):
        if v is None or pd.isna(v):
            return '<td style="text-align:center">-</td>'
        vf = float(v)
        color = ITAU_GREEN if vf > 0 else (ITAU_RED if vf < 0 else "#444")
        cls = ' class="bold"' if negrito else ""
        return f'<td{cls} style="color:{color}">{vf:+.2f}%</td>'


    th = ("<th>Year</th><th></th>" + "".join(f"<th>{_esc(m)}</th>" for m in meses)
          + "<th>Accumulated</th>")


    linhas_html = []
    for ano, bloco in df_cal.groupby("Ano", sort=False):
        n_linhas = len(bloco)
        for i, (_, row) in enumerate(bloco.iterrows()):
            cels = "".join(_cel(row[m]) for m in meses)
            cel_accum = _cel(row["Accumulated"], negrito=True)
            if i == 0:
                linhas_html.append(
                    f'<tr><td rowspan="{n_linhas}" class="bold">{_esc(int(ano))}</td>'
                    f'<td class="bold">{_esc(row["Série"])}</td>{cels}{cel_accum}</tr>'
                )
            else:
                linhas_html.append(f'<tr><td class="bold">{_esc(row["Série"])}</td>{cels}{cel_accum}</tr>')


    return (
        f'<h2 class="aba-title">{_esc(titulo)}</h2>'
        f'<div class="tbl-wrap"><table class="exp-table">'
        f'<thead><tr>{th}</tr></thead><tbody>{"".join(linhas_html)}</tbody></table></div>'
    )



# ─────────────────────────────────────────────────────────────────────────────
# Seções (abas)
# ─────────────────────────────────────────────────────────────────────────────


def _build_breakdown_pane(prefixo, rotulo_componente, meses_dados, rotulo_mes_fn,
                          mensal, df_matriz, categorias) -> str:
    if not categorias:
        return (f'<p class="aviso">Sem dados para compor esta visão ({_esc(rotulo_componente)}) '
                f'no período selecionado.</p>')


    opts = "".join(
        f'<option value="{m}"{" selected" if i == len(meses_dados) - 1 else ""}>{rotulo_mes_fn(m)}</option>'
        for i, m in enumerate(meses_dados)
    )


    paineis = []
    for m in meses_dados:
        d = mensal.get(m, {})
        itens = sorted(((c, d.get(c, 0.0)) for c in categorias if d.get(c, 0.0) != 0),
                       key=lambda kv: -kv[1])
        comps = [c for c, _ in itens]
        vals  = [v for _, v in itens]
        total = sum(d.values())
        svg = _build_waterfall_svg(comps, vals, total)
        display = "block" if m == meses_dados[-1] else "none"
        paineis.append(
            f'<div id="wf-{prefixo}-{m}" class="wf-month-pane wf-month-{prefixo}" '
            f'style="display:{display}">{svg}</div>'
        )


    return (
        f'<div class="pnl-chart-box">'
        f'<div class="pnl-chart-title">Cascata mensal — {_esc(rotulo_componente)}</div>'
        f'<div style="margin-bottom:12px">'
        f'<label style="font-size:.82rem;font-weight:600;color:{ITAU_DARK};margin-right:8px">Mês:</label>'
        f'<select class="mes-select" onchange="showMonth(\'{prefixo}\', this.value)">{opts}</select>'
        f'</div>{"".join(paineis)}</div>'
        f'<h2 class="aba-title">Tabela completa — {_esc(rotulo_componente)}</h2>'
        f'{_build_table(df_matriz)}'
    )



def _sufixo_janela(inicio: str) -> str:
    """'2010-01' -> '2010' (usado em ids de aba)."""
    return inicio.split("-")[0]



def _build_historico_pane(df_historico, nome_benchmark, rotulo_janela="", chart_id="hist",
                          mostrar_coluna_bps=True, mostrar_barras=True) -> str:
    """Monta o conteúdo (legenda + SVG + tabela) de UMA aba de Histórico —
    reutilizado para cada janela em JANELAS_PERFORMANCE (ex.: desde 2010,
    desde 2014).


    `chart_id` identifica o container do gráfico (único por janela) — é nele
    que os checkboxes da legenda (benchmark/Ibovespa) mexem via JS, sem
    precisar regerar o SVG.
    `mostrar_coluna_bps`: inclui a coluna "Atribuição mensal (bps)" na tabela
    (e o total do período ao lado da legenda).
    `mostrar_barras`: acrescenta o painel de atribuição mensal (bps) abaixo
    da linha de retorno acumulado.
    """
    def _col(nome_col):
        if df_historico.empty or nome_col not in df_historico.columns:
            return []
        return [None if pd.isna(v) else float(v) for v in df_historico[nome_col]]


    meses_rotulo = list(df_historico["mes"]) if not df_historico.empty else []
    # bps fica None nos meses sem atribuição (ex.: antes do histórico de
    # posição começar) — o gráfico pula o mês e a tabela mostra em branco.
    bps_vals = _col("total_bps")
    series = [
        ("fundo", "Fundo", _col("retorno_acumulado_pct"), _COR_FUNDO),
        ("bench", nome_benchmark or "Benchmark", _col("retorno_benchmark_pct"), _COR_BENCHMARK),
        ("ibov", "Ibovespa", _col("retorno_ibov_pct"), _COR_IBOV),
    ]
    series = [s for s in series if any(v is not None for v in s[2])]
    historico_svg = _build_historico_svg(meses_rotulo, bps_vals, series, mostrar_barras=mostrar_barras)
    total_periodo = sum(v for v in bps_vals if v is not None)


    nome_bench_disp = nome_benchmark or "benchmark"
    rotulo_bench_col = f"Retorno acumulado — {nome_bench_disp} (%)"
    df_historico_fmt = df_historico.rename(columns={
        "total_bps": "Atribuição mensal (bps)",
        "retorno_acumulado_pct": "Retorno acumulado — fundo (%)",
        "retorno_benchmark_pct": rotulo_bench_col,
        "retorno_ibov_pct": "Retorno acumulado — Ibovespa (%)",
    })
    if not mostrar_coluna_bps:
        df_historico_fmt = df_historico_fmt.drop(columns=["Atribuição mensal (bps)"])


    sufixo_titulo = "retorno acumulado e atribuição mensal" if mostrar_barras else "retorno acumulado"
    titulo = f"Histórico {rotulo_janela} — {sufixo_titulo}" if rotulo_janela \
        else f"Histórico — {sufixo_titulo}"


    # Legenda = controle: o fundo fica sempre visível; benchmark/Ibovespa
    # ganham checkbox — e só aparecem se a série tiver algum dado (não faz
    # sentido oferecer "mostrar benchmark" se o fundo não tem benchmark).
    itens = []
    for sid, nome, _vals, cor in series:
        chave = f'<i class="hist-key" style="background:{cor}"></i>'
        if sid == "fundo":
            itens.append(f'<span class="hist-leg">{chave}{_esc(nome)}</span>')
        else:
            itens.append(
                f'<label class="hist-leg hist-leg-toggle">'
                f'<input type="checkbox" checked onchange="toggleHistSerie(this, \'{chart_id}\', \'{sid}\')">'
                f'{chave}{_esc(nome)}</label>'
            )
    if mostrar_coluna_bps:
        itens.append(f'<span class="hist-nota">Atribuição total no período: {_fmt_bps(total_periodo)} bps</span>')
    legenda = f'<div class="hist-legenda">{"".join(itens)}</div>' if itens else ""


    return (
        f'<div class="pnl-chart-box">'
        f'<div class="pnl-chart-title">{_esc(titulo)}</div>'
        f'{legenda}'
        f'<div id="{chart_id}" class="hist-chart">{historico_svg}</div></div>'
        f'<h2 class="aba-title">Tabela — Histórico</h2>'
        f'{_build_table(df_historico_fmt)}'
    )



_ABAS_VISIVEIS_DEFAULT = {
    "resumo": True, "historico": True, "posicao": True, "empresa": True,
    "setor": True, "categoria": True, "fator_risco": True, "acao": True, "rv_hist": True,
}



def gerar_html(fundo, meses, meses_dados, rotulo_mes_fn,
               mensal_posicao, df_posicao, cats_posicao,
               mensal_empresa, df_empresa, cats_empresa,
               mensal_setor, df_setor, cats_setor,
               mensal_categoria, df_categoria, cats_categoria,
               mensal_fator_risco, df_fator_risco, cats_fator_risco,
               mensal_acao, df_acao, cats_acao,
               historicos, nome_benchmark, out_dir,
               rv_hists=None, periodos_por_mes=None, tabelas_mensais=None,
               df_calendario_comparativo=None, abas_visiveis=None,
               mostrar_coluna_bps_historico=True, mostrar_grafico_barras_historico=True,
               meses_dados_completo=None) -> str:
    """Gera o relatório HTML (mesmo layout do exposicao_html) e devolve o caminho do arquivo.


    `historicos`: lista de (inicio_janela 'YYYY-MM', df_historico).
    `rv_hists`: lista de (inicio_janela, mensal_janela, df_rv, cats_rv, meses_dados_rv, _).
    `periodos_por_mes`: dict ordenado {mes_label: df_periodos} — 1 tabela
    MTD/QTD/YTD/12M/24M/36M/ITD (de perf.montar_tabela_periodos) por mês de
    referência disponível, pro dropdown da aba RESUMO.
    `tabelas_mensais`: lista de (titulo, df_calendario) — de
    perf.montar_tabela_mensal_anual, calendário Ano x Jan..Dez por série.
    `df_calendario_comparativo`: calendário Fundo x Benchmark x Alpha (de
    perf.montar_tabela_calendario_comparativo), mostrado na aba RESUMO.
    `abas_visiveis`: dict {chave: bool} — quais abas entram no relatório
    (chaves: resumo/historico/posicao/empresa/setor/categoria/fator_risco/
    acao/rv_hist). Sem isso (ou chave ausente), a aba aparece normalmente.
    `mostrar_coluna_bps_historico`/`mostrar_grafico_barras_historico`: ver
    perf.MOSTRAR_COLUNA_BPS_HISTORICO / MOSTRAR_GRAFICO_BARRAS_HISTORICO.
    `meses_dados_completo`: meses com dado em Posição/Empresa/Setor DEPOIS de
    preenchidos com RV histórico (pode ir bem mais pro passado que
    `meses_dados`) — usado só no dropdown dessas 3 abas.
    """
    abas_visiveis = {**_ABAS_VISIVEIS_DEFAULT, **(abas_visiveis or {})}
    meses_dados_completo = meses_dados_completo or meses_dados


    os.makedirs(out_dir, exist_ok=True)
    primeiro, ultimo = meses[0][0], meses[-1][0]
    nome = f"performance_attribution_{fundo}_mensal_{primeiro}_a_{ultimo}.html"
    caminho = os.path.join(out_dir, nome)
    rv_hists = rv_hists or []


    tabs = []
    if abas_visiveis["resumo"] and periodos_por_mes:
        sec_resumo = _build_resumo_periodos_pane(periodos_por_mes, rotulo_mes_fn, nome_benchmark,
                                                  tabelas_mensais, df_calendario_comparativo)
        tabs.append(("resumo", "RESUMO", sec_resumo))


    if not abas_visiveis["historico"]:
        historicos = []
    for inicio, df_h in historicos:
        suf = _sufixo_janela(inicio)
        sec_h = _build_historico_pane(df_h, nome_benchmark, rotulo_janela=f"(desde {inicio})",
                                      chart_id=f"hist-chart-{suf}",
                                      mostrar_coluna_bps=mostrar_coluna_bps_historico,
                                      mostrar_barras=mostrar_grafico_barras_historico)
        tabs.append((f"historico_{suf}", f"HISTÓRICO {suf}", sec_h))


    if abas_visiveis["posicao"]:
        sec_posicao = _build_breakdown_pane("posicao", "Posição / Ativo", meses_dados_completo, rotulo_mes_fn,
                                            mensal_posicao, df_posicao, cats_posicao)
        tabs.append(("posicao", "POR POSIÇÃO", sec_posicao))
    if abas_visiveis["empresa"]:
        sec_empresa = _build_breakdown_pane("empresa", "Empresa (Equity)", meses_dados_completo, rotulo_mes_fn,
                                            mensal_empresa, df_empresa, cats_empresa)
        tabs.append(("empresa", "POR EMPRESA", sec_empresa))
    if abas_visiveis["acao"]:
        sec_acao = _build_breakdown_pane("acao", "Ação", meses_dados, rotulo_mes_fn,
                                         mensal_acao, df_acao, cats_acao)
        tabs.append(("acao", "POR AÇÃO", sec_acao))
    if abas_visiveis["setor"]:
        sec_setor = _build_breakdown_pane("setor", "Setor GICS", meses_dados_completo, rotulo_mes_fn,
                                          mensal_setor, df_setor, cats_setor)
        tabs.append(("setor", "POR SETOR", sec_setor))
    if abas_visiveis["fator_risco"]:
        sec_fator_risco = _build_breakdown_pane("fatorrisco", "Fator de Risco", meses_dados, rotulo_mes_fn,
                                                mensal_fator_risco, df_fator_risco, cats_fator_risco)
        tabs.append(("fatorrisco", "POR FATOR DE RISCO", sec_fator_risco))
    if abas_visiveis["categoria"]:
        sec_categoria = _build_breakdown_pane("categoria", "Categoria", meses_dados, rotulo_mes_fn,
                                              mensal_categoria, df_categoria, cats_categoria)
        tabs.append(("categoria", "POR CATEGORIA", sec_categoria))


    if abas_visiveis["rv_hist"]:
        for inicio, mensal_janela, df_rv_j, cats_rv_j, meses_dados_rv_j, _n in rv_hists:
            suf = _sufixo_janela(inicio)
            sec_rv_j = _build_breakdown_pane(
                f"rvhist_{suf}", f"RV — Histórico desde {inicio} (OT0_PERF_ATTRIB_RV_DADOS_GERAL)",
                meses_dados_rv_j, rotulo_mes_fn,
                mensal_janela, df_rv_j, cats_rv_j,
            )
            tabs.append((f"rvhist_{suf}", f"RV HISTÓRICO {suf}", sec_rv_j))


    nav_html = "".join(
        f'<button class="perf-tab-btn{" active" if i == 0 else ""}" '
        f'data-perf-pane="pane-{pid}">{label}</button>'
        for i, (pid, label, _) in enumerate(tabs)
    )
    panes_html = "".join(
        f'<div id="pane-{pid}" class="perf-pane{" active" if i == 0 else ""}">{html}</div>'
        for i, (pid, _, html) in enumerate(tabs)
    )


    dt_ini_fmt = f"{meses[0][0]}"
    dt_fim_fmt = f"{meses[-1][0]}"


    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Performance Attribution — {_esc(fundo)}</title>
  <style>{_build_css()}</style>
</head>
<body>


<div class="hdr">
  <div class="hdr-inner">
    <div>
      <h1>PERFORMANCE ATTRIBUTION</h1>
      <p class="sub">Fundo: <strong>{_esc(fundo)}</strong> &nbsp;|&nbsp;
         Período: <strong>{dt_ini_fmt} a {dt_fim_fmt}</strong></p>
    </div>
    <div class="brand"><span>Itaú Asset Management</span>{_logo_tag()}</div>
  </div>
</div>


<div class="nav-wrapper">
  <nav class="perf-nav">{nav_html}</nav>
</div>


<div class="content">{panes_html}</div>


<div class="footer">
  Atribuição chain-linked pela cota do fundo (bps) &nbsp;|&nbsp;
  TOTAL = soma das contribuições do período &nbsp;|&nbsp;
  Retorno acumulado = encadeamento composto das atribuições mensais
</div>


<script>{_build_js()}</script>
</body>
</html>"""


    with open(caminho, "w", encoding="utf-8") as f:
        f.write(html)


    return caminho

