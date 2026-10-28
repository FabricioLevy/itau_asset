# ─────────────────────────────────────────────
# taxa_media/html_report.py
# Relatório HTML da taxa média: o mesmo layout do attribution/html_report.py (cores Itaú, header com abas,
# tabelas ordenáveis, gráficos em SVG com tooltip) e, como ele, autocontido: não importa nada do attribution nem
# do __main__ (projetos irmãos aqui não se importam entre si). Recebe as mesmas tabelas que vão para o Excel.
#
# Abas: FUNDOS (só com mais de um fundo), RESUMO, HISTÓRICO (com --desde), ATIVOS, LOTES, TRADES, AVISOS e
# METODOLOGIA. Com mais de um fundo, o seletor da barra de abas troca o fundo em todas elas. Clicar num ativo
# (tabela ou gráfico) abre a ficha dele, com os lotes, os trades e os avisos.
# ─────────────────────────────────────────────

import base64
import json
import math
import os
import re
from datetime import date, datetime

import numpy as np
import pandas as pd

# ── Paleta Itaú (igual a attribution/html_report.py) ──────────────────────────
ITAU_DARK = "#000D3C"
ITAU_ORANGE = "#EC7000"
ITAU_GRAY = "#e0e0e0"
ITAU_GRAY2 = "#aaaaaa"
ITAU_RED = "#c0392b"
ITAU_GREEN = "#1e7e34"
ROW_PAR = "#eaf0fb"

# Cores das séries, as mesmas em todo o relatório (a cor segue a entidade): carteira, CDI+ e %CDI usam o trio do
# attribution (fundo, benchmark, Ibovespa); compras e vendas, um par próprio. Os dois trios (com a carteira)
# passam no validador de daltonismo comparando todos os pares.
COR_CARTEIRA = ITAU_ORANGE
COR_GRUPO = {"CDI+": "#2A78D6", "%CDI": "#4A3AA7"}
COR_OPERACAO = {"Compra": "#00A37A", "Venda": "#B0306A"}
COR_PESO = "#9AA5B8"     # peso no financeiro: neutro, não é série
COR_DESTAQUE = "#D03B3B"  # lote com aviso Boleta × VCRA

# Tinta dos gráficos: texto, eixos e grade nunca usam a cor de uma série.
_TINTA = "#1a1a2e"
_TINTA_FRACA = "#7a8194"
_GRADE = "#e6e9f0"
_BASE = "#b9c0cf"
_MESES_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

_DIR = os.path.dirname(os.path.abspath(__file__))
# Logo compartilhado com exposicao_html, como no attribution (se não existir, a página fica sem logo).
_LOGO_PATH = os.path.join(_DIR, "..", "..", "exposicao_html", "input", "logo.png")

# O que cada aviso do __main__ quer dizer (aba AVISOS); "Correção manual" é informativo.
SIGNIFICADO_AVISOS = {
    "Quantidade": "a quantidade dos lotes em aberto na VCRA não bate com a da posição na data",
    "Sem lote": "o ativo está na posição sem lote em aberto na VCRA: fica fora da média",
    "Fora do escopo": "o ativo está na posição, mas o tipo (RFTP_CD) ou o indexador está fora do cálculo",
    "Tipo novo": "RFTP_CD da VCRA que não está na aba Tipos do Excel de entrada: ficou fora",
    "Fora da média": "ativo sem nenhum lote com taxa ou sem PU na posição: não entra na média",
    "Média parcial": "parte dos lotes do ativo está sem taxa: a média do ativo usa só os outros",
    "Boleta inválida": "a taxa da boleta está fora da convenção do grupo (ex.: 9,33 num papel de % do CDI)",
    "Sem boleta": "nenhuma boleta casou com a compra (mesmo ativo, perto da data, mesma quantidade ou PU)",
    "Correção manual": "taxa do lote trocada pela aba Correções do Excel de entrada",
    "Correção não aplicada": "lote da aba Correções que não está em aberto no fundo",
    "Boleta × VCRA": "a taxa da boleta e a da VCRA (pelo PU pago) divergem acima do limite",
    "Venda sem compra": "venda de um lote cuja compra não está no histórico da VCRA",
    "Lote negativo": "o lote tem mais vendas que compras na VCRA",
}


# ── Formatação ───────────────────────────────────────────────────────────────
def _esc(s):
    return (str(s).replace("&", "&amp;").replace('"', "&quot;").replace("'", "&#39;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def _vazio(v):
    """None, NaN, NaT ou texto em branco (o Excel relido traz NaN onde a memória tinha "")."""
    if isinstance(v, str):
        return not v.strip()
    try:
        return v is None or bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def _br(x, casas=2):
    """Número no formato brasileiro (1.234,56)."""
    return f"{x:,.{casas}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _cdi_mais(x, casas=2):
    return "" if _vazio(x) else f"CDI{'+' if x >= 0 else '−'}{_br(abs(x), casas)}"


def _taxa(grupo, v, casas=2):
    """Taxa na convenção do grupo: CDI+2,46 ou 105,51% do CDI."""
    if _vazio(v):
        return ""
    return f"{_br(v, casas)}% do CDI" if grupo == "%CDI" else _cdi_mais(v, casas)


def _rs(v):
    """R$ compacto (R$ 548,3 mi), para cartões, rótulos e tooltips; as tabelas mostram o valor cheio."""
    if _vazio(v):
        return "—"
    for limite, sufixo in ((1e9, "bi"), (1e6, "mi"), (1e3, "mil")):
        if abs(v) >= limite:
            return f"R$ {_br(v / limite, 1)} {sufixo}"
    return f"R$ {_br(v, 0)}"


def _dt(v):
    return "" if _vazio(v) else f"{pd.Timestamp(v):%d/%m/%Y}"


def _iso(v):
    return "" if _vazio(v) else f"{pd.Timestamp(v):%Y-%m-%d}"


def _int(v):
    return 0 if _vazio(v) else int(v)


def _plural(n, palavra, plural=None):
    return f"{_br(n, 0)} {palavra if n == 1 else plural or palavra + 's'}"


def _logo_tag():
    if not os.path.exists(_LOGO_PATH):
        return ""
    with open(_LOGO_PATH, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f'<img src="data:image/png;base64,{b64}" class="logo-img" alt="Itaú">'


def _tag(texto, classe):
    return f'<span class="tag {classe}">{_esc(texto)}</span>'


def _chave(texto, cor):
    """Rótulo com a marca da cor da série ao lado (o texto fica na cor da tinta)."""
    return f'<span class="tag t-serie"><i style="background:{cor}"></i>{_esc(texto)}</span>'


_CLASSE_FONTE = {"boleta": "t-boleta", "VCRA": "t-vcra", "manual": "t-manual"}

# formato de cada coluna das tabelas: valor (não vazio) e a linha inteira -> HTML da célula
_FMT = {
    "texto": lambda v, r: _esc(v),
    "longo": lambda v, r: _esc(v),  # texto corrido: alinhado à esquerda e quebrando linha
    "data": lambda v, r: _dt(v),
    "int": lambda v, r: _br(v, 0),
    "pu": lambda v, r: _br(v, 6),
    "t2": lambda v, r: _br(v, 2),
    "t4": lambda v, r: _br(v, 4),
    "dif": lambda v, r: ("+" if v > 0 else "") + _br(v, 2),
    "pct": lambda v, r: _br(v, 2) + "%",
    "eq": lambda v, r: _cdi_mais(v),
    "conv": lambda v, r: _taxa(r.get("grupo"), v),
    "conv4": lambda v, r: _taxa(r.get("grupo"), v, 4),
    "ativo": lambda v, r: f'<a class="lk-ativo" data-ativo="{_esc(v)}">{_esc(v)}</a>',
    "fundo": lambda v, r: f'<a class="lk-fundo" data-fundo="{_esc(v)}">{_esc(v)}</a>',
    "grupo": lambda v, r: _chave(v, COR_GRUPO.get(v, _BASE)) if v in COR_GRUPO else _tag(v, "t-total"),
    "op": lambda v, r: _chave(v, COR_OPERACAO.get(v, _BASE)),
    "fonte": lambda v, r: _tag(v, _CLASSE_FONTE.get(v, "t-sem")),
    "simnao": lambda v, r: _tag("sim", "t-ok") if v in (True, "sim") else _tag("não", "t-sem"),
    "aviso": lambda v, r: _tag(v, "t-info" if v == "Correção manual" else "t-aviso"),
    "status": lambda v, r: _tag(v, "t-ok" if v == "OK" else "t-erro" if str(v).startswith("erro") else "t-aviso"),
}
_FMT_TEXTO = {"texto", "ativo", "fundo", "grupo", "op", "fonte", "simnao", "aviso", "status"}


def _attr(v):
    if _vazio(v):
        return ""
    return _iso(v) if isinstance(v, (pd.Timestamp, datetime, date)) else str(v)


def _celula(v, fmt, r):
    """<td> com data-v (número cru ou data ISO) para a ordenação; vazio fica com data-v vazio e vai para o fim."""
    if _vazio(v):
        return '<td data-v=""></td>'
    html = _FMT[fmt](v, r)
    if fmt == "longo":
        return f'<td class="txt">{html}</td>'
    if fmt in _FMT_TEXTO:
        return f"<td>{html}</td>"
    if isinstance(v, (pd.Timestamp, datetime, date)):
        return f'<td data-v="{_iso(v)}">{html}</td>'
    return f'<td class="num" data-v="{float(v):.12g}">{html}</td>'


def _tabela(df, colunas, tid=None, attrs=(), rodape=(), alta=False, extra=""):
    """Tabela ordenável (clique no título da coluna). colunas: [(coluna, título, formato, dica)], formato = chave de
    _FMT e dica = tooltip do título; attrs: [(nome, coluna)] que viram data-<nome> de cada linha (filtros e ficha do
    ativo); rodape: linhas de total ({coluna: valor}) no tfoot, fora da ordenação; alta: rolagem própria com o
    título fixo; extra: atributos a mais do <table>."""
    cab = "".join(f'<th onclick="sortTable(this)" title="{_esc(dica)} (clique para ordenar)">{_esc(titulo)}</th>'
                  for _, titulo, _, dica in colunas)
    linhas = []
    for r in df.to_dict("records"):
        dados = "".join(f' data-{nome}="{_esc(_attr(r.get(c)))}"' for nome, c in attrs)
        linhas.append(f"<tr{dados}>" + "".join(_celula(r.get(c), fmt, r) for c, _, fmt, _ in colunas) + "</tr>")
    pe = "".join("<tr>" + "".join(_celula(t.get(c), fmt, t) for c, _, fmt, _ in colunas) + "</tr>" for t in rodape)
    ident = f' id="{tid}"' if tid else ""
    return (f'<div class="tbl-wrap{" alta" if alta else ""}"><table class="exp-table"{ident}{extra}>'
            f'<thead><tr>{cab}</tr></thead><tbody>{"".join(linhas)}</tbody>'
            f'{f"<tfoot>{pe}</tfoot>" if pe else ""}</table></div>')


def _filtros(tid, selects=(), dia=False, dica="Filtrar"):
    """Barra acima da tabela: busca por texto, um select por atributo da linha (selects: [(campo, rótulo,
    opções)]), o filtro de dia (vem do clique num dia de trade) e a contagem de linhas."""
    partes = [f'<input class="filtro-busca" data-alvo="{tid}" type="search" placeholder="{_esc(dica)}">']
    for campo, rotulo, opcoes in selects:
        ops = "".join(f'<option value="{_esc(o)}">{_esc(o)}</option>' for o in opcoes)
        partes.append(f'<label class="filtro-rot">{_esc(rotulo)} <select class="filtro-sel" data-alvo="{tid}" '
                      f'data-campo="{campo}"><option value="">Todos</option>{ops}</select></label>')
    if dia:
        partes.append(f'<button class="chip-dia" data-alvo="{tid}" hidden title="Voltar a todos os dias">'
                      f'Dia <b></b> ✕</button>')
    partes.append(f'<span class="filtro-cont" data-alvo="{tid}"></span>')
    return f'<div class="toolbar">{"".join(partes)}</div>'


def _kpi(rotulo, valor, sub="", cor=ITAU_DARK, extra="", grafico=""):
    """Cartão de número (rótulo, valor e uma linha de contexto); extra = atributos do cartão (clique)."""
    return (f'<div class="kpi" style="border-top-color:{cor}"{extra}><div class="kpi-rot">{_esc(rotulo)}</div>'
            f'<div class="kpi-val">{_esc(valor)}</div>{grafico}'
            f'{f"<div class=kpi-sub>{_esc(sub)}</div>" if sub else ""}</div>')


def _secao(titulo, conteudo, explica=""):
    """Bloco branco com título (o pnl-chart-box do attribution) e, opcionalmente, uma linha de como ler."""
    return (f'<div class="pnl-chart-box"><div class="pnl-chart-title">{_esc(titulo)}</div>'
            f'{f"<p class=explica>{explica}</p>" if explica else ""}{conteudo}</div>')


# ── SVG: eixos ───────────────────────────────────────────────────────────────
def _ticks_redondos(lo, hi, n_alvo=5):
    """Ticks "redondos" (passo 1 / 2 / 2,5 / 5 × 10^k) cobrindo [lo, hi]; devolve (ticks, passo)."""
    if hi - lo <= 0:
        folga = abs(hi) * 0.05 or 1.0
        lo, hi = lo - folga, hi + folga
    bruto = (hi - lo) / n_alvo
    mag = 10 ** math.floor(math.log10(bruto))
    passo = next(m * mag for m in (1, 2, 2.5, 5, 10) if bruto <= m * mag * (1 + 1e-9))
    ini = math.floor(lo / passo + 1e-9) * passo
    fim = math.ceil(hi / passo - 1e-9) * passo
    return [ini + k * passo for k in range(int(round((fim - ini) / passo)) + 1)], passo


def _dominio_eixo(lo, hi, n_alvo=5):
    """(y_lo, y_hi, ticks, passo): ticks redondos, mas cada limite só vai até o próximo tick quando isso desperdiça no
    máximo meio passo; senão fica rente ao dado, com 4% de folga."""
    ticks, passo = _ticks_redondos(lo, hi, n_alvo)
    folga = 0.04 * ((hi - lo) or passo)
    y_lo = ticks[0] if lo - ticks[0] <= passo / 2 else lo - folga
    y_hi = ticks[-1] if ticks[-1] - hi <= passo / 2 else hi + folga
    return y_lo, y_hi, [t for t in ticks if y_lo - 1e-9 <= t <= y_hi + 1e-9], passo


def _fmt_tick(v, passo, sufixo="", escala=1.0):
    """Rótulo de tick com só as casas que o passo pede; escala divide o valor (ex.: 1e6 para R$ mi)."""
    v, passo = v / escala, passo / escala
    if abs(v) < passo * 1e-6:
        return f"0{sufixo}"
    casas = next(c for c in (0, 1, 2, 3) if abs(passo * 10 ** c - round(passo * 10 ** c)) < 1e-6 or c == 3)
    return f"{_br(v, casas)}{sufixo}"


def _rotulos_datas(datas, xs, temporal, x_de):
    """[(x, texto)] do eixo X: o 1º dia de cada mês (Mmm/aa), com o maior espaçamento de meses (1, 3, 6, 12) que
    cabe na horizontal; com menos de três meses no período, os dias (dd/mm)."""
    if temporal:
        meses = pd.date_range(datas[0] + pd.offsets.MonthBegin(0), datas[-1], freq="MS")
        cand = [(x_de(m), m) for m in meses]
    else:
        cand = [(x, d) for i, (x, d) in enumerate(zip(xs, datas)) if i == 0 or d.month != datas[i - 1].month]
    if len(cand) >= 3:
        for passo in (1, 3, 6, 12, 24):
            sel = [(x, d) for x, d in cand if (d.month - 1) % passo == 0]
            if len(sel) >= 2 and min(b[0] - a[0] for a, b in zip(sel, sel[1:])) >= 52:
                return [(x, f"{_MESES_PT[d.month - 1]}/{d:%y}") for x, d in sel]
        return [(x, f"{_MESES_PT[d.month - 1]}/{d:%y}") for x, d in cand[:1]]
    rotulos, ultimo = [], -1e9
    for x, d in zip(xs, datas):
        if x - ultimo >= 46:
            rotulos.append((x, f"{d:%d/%m}"))
            ultimo = x
    return rotulos


def _path_com_lacunas(pontos, liga=False):
    """'M x y L x y ...' que levanta a caneta nos pontos vazios (None), a não ser com liga = True."""
    d, caneta = [], False
    for p in pontos:
        if p is None:
            caneta = caneta and liga
            continue
        d.append(f"{'L' if caneta else 'M'}{p[0]:.1f} {p[1]:.1f}")
        caneta = True
    return " ".join(d)


def _marcador(x, y, forma, cor, r=4.5):
    """Ponto de série com o anel de 2px na cor do fundo (fica legível sobre linhas e outros pontos)."""
    if forma == "losango":
        k = r * 1.3
        return (f'<path d="M{x:.1f} {y - k:.1f} L{x + k:.1f} {y:.1f} L{x:.1f} {y + k:.1f} L{x - k:.1f} {y:.1f} Z" '
                f'fill="{cor}" stroke="#fff" stroke-width="2"/>')
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{cor}" stroke="#fff" stroke-width="2"/>'


def _faixa_robusta(vals, corte=0.03):
    """[lo, hi] dos valores sem os extremos (percentis 3% e 97%, com folga) quando há valores suficientes: um dia fora
    da curva (ex.: o começo do fundo, com um ou dois ativos) não achata o resto do gráfico."""
    v = sorted(vals)
    if len(v) < 20:
        return v[0], v[-1]
    lo, hi = v[int(round(corte * (len(v) - 1)))], v[int(round((1 - corte) * (len(v) - 1)))]
    folga = (hi - lo) * 0.15 or abs(hi) * 0.02 or 1.0
    return max(v[0], lo - folga), min(v[-1], hi + folga)


# ── SVG: série no tempo (painéis com o mesmo eixo X e crosshair) ─────────────────
def _grafico_serie(cid, datas, paineis, temporal=False, rodape=None, clique=None, dias_clique=None):
    """Séries no tempo em painéis empilhados com o mesmo eixo X: um painel por unidade, nunca dois eixos Y no mesmo
    painel. paineis: [{"titulo", "altura", "fmt" (valor -> texto do tooltip e do rótulo final), "sufixo" e "escala"
    (ticks), "zero" (inclui o zero no eixo), "robusto" (escala sem os extremos, que ficam recortados na borda),
    "series": [{"sid", "nome", "vals", "cor", "tipo" (linha, pontos ou barras), "forma" (circulo ou losango),
    "principal", "liga" (a linha passa por cima dos vazios)}]}]; os vals têm o tamanho de datas, com None onde não
    há valor. Eixo X por posição (uma vaga por data) ou, com temporal, proporcional ao tempo. O tooltip lista todas
    as séries visíveis na data mais próxima do mouse (dados no data-serie do .serie-overlay); rodape[i] fecha o
    tooltip; clique = id da tabela de trades que o clique numa data filtra (só nas datas com rodape) ou "#dia:<aba>",
    que no index.html abre o relatório do dia nessa aba; dias_clique = o dia aberto em cada data (padrão: a própria
    data). cid = id do gráfico (prefixo dos recortes)."""
    datas = [pd.Timestamp(d) for d in datas]
    n = len(datas)
    if not n:
        return ""
    W, PL, PR, PT, TIT, GAP, EIXO = 1000, 72, 118, 6, 22, 30, 30
    largura = W - PL - PR
    dias = max((datas[-1] - datas[0]).days, 1)
    borda = 14 if n > 1 else largura / 2

    def x_de(d):  # eixo proporcional ao tempo
        return PL + borda + (pd.Timestamp(d) - datas[0]).days / dias * (largura - 2 * borda)

    if temporal:
        xs = [x_de(d) for d in datas]
        menor = min((b - a for a, b in zip(xs, xs[1:])), default=40)
        bar_w = max(2.0, min(12.0, menor * 0.6))
    else:
        vaga = largura / n
        xs = [PL + (i + 0.5) * vaga for i in range(n)]
        bar_w = min(vaga * 0.62, 18)

    els, ys_json, y = [], {}, PT
    topo_plot = PT + TIT
    for k, p in enumerate(paineis):
        if k:
            y += GAP
        topo, base = y + TIT, y + TIT + p["altura"]
        barras = [s for s in p["series"] if s["tipo"] == "barras"]
        vals = [v for s in p["series"] if s["tipo"] != "barras" for v in s["vals"] if v is not None]
        lo, hi = _faixa_robusta(vals) if p.get("robusto") and vals else (min(vals or [0.0]), max(vals or [0.0]))
        for i in range(n if barras else 0):  # barras empilhadas: a soma de cada lado do zero
            v_i = [s["vals"][i] for s in barras if s["vals"][i] is not None]
            lo = min(lo, 0.0, sum(v for v in v_i if v < 0))
            hi = max(hi, 0.0, sum(v for v in v_i if v > 0))
        if p.get("zero"):
            lo, hi = min(lo, 0.0), max(hi, 0.0)
        y_lo, y_hi, ticks, passo = _dominio_eixo(lo, hi, n_alvo=4 if p["altura"] < 200 else 5)
        fora = sum(not y_lo <= v <= y_hi for v in vals)

        def _y(v, topo=topo, altura=p["altura"], y_lo=y_lo, y_hi=y_hi):
            return topo + altura * (1 - (v - y_lo) / ((y_hi - y_lo) or 1.0))

        def _y_dentro(v, topo=topo, base=base):  # ponto e rótulo de valor fora da escala ficam na borda
            return min(max(_y(v), topo), base)

        recorte = f"{cid}-p{k}"
        els.append(f'<clipPath id="{recorte}"><rect x="{PL}" y="{topo - 3}" width="{largura}" '
                   f'height="{p["altura"] + 6}"/></clipPath>')
        els.append(f'<text x="{PL}" y="{y + 13}" font-size="11.5" font-weight="600" fill="{_TINTA}">'
                   f'{_esc(p["titulo"])}</text>')
        if fora:
            els.append(f'<text x="{W - PR}" y="{y + 13}" text-anchor="end" font-size="10.5" fill="{_TINTA_FRACA}">'
                       f'{_plural(fora, "valor", "valores")} fora da escala (os extremos estão no tooltip e na '
                       f'tabela)</text>')
        els.append(f'<line x1="{PL}" y1="{base}" x2="{W - PR}" y2="{base}" stroke="{_GRADE}" stroke-width="1"/>')
        for t in ticks:
            yg = _y(t)
            zero = abs(t) < passo * 1e-6
            els.append(f'<line x1="{PL}" y1="{yg:.1f}" x2="{W - PR}" y2="{yg:.1f}" stroke="{_BASE if zero else _GRADE}" '
                       f'stroke-width="1"/>')
            els.append(f'<text x="{PL - 8}" y="{yg + 4:.1f}" text-anchor="end" font-size="11" fill="{_TINTA_FRACA}">'
                       f'{_fmt_tick(t, passo, p.get("sufixo", ""), p.get("escala", 1.0))}</text>')

        pos, neg = [0.0] * n, [0.0] * n
        for s in barras:
            partes = []
            for i, v in enumerate(s["vals"]):
                if v is None or v == 0:
                    continue
                acum = pos if v > 0 else neg
                ini, fim = acum[i], acum[i] + v
                acum[i] = fim
                yt, yb = _y(max(ini, fim)), _y(min(ini, fim))
                if ini != 0:  # 2px de fundo entre os segmentos empilhados
                    yt, yb = (yt, yb - 2) if v > 0 else (yt + 2, yb)
                partes.append(f'<rect x="{xs[i] - bar_w / 2:.1f}" y="{yt:.1f}" width="{bar_w:.1f}" '
                              f'height="{max(yb - yt, 1.0):.1f}" fill="{s["cor"]}" rx="{min(1.5, bar_w / 2):.1f}"/>')
            els.append(f'<g class="serie-{s["sid"]}">{"".join(partes)}</g>')

        finais = {}
        for s in p["series"]:
            if s["tipo"] == "barras":
                continue
            pontos = [(xs[i], _y(v)) if v is not None else None for i, v in enumerate(s["vals"])]
            dentro = [(xs[i], _y_dentro(v)) if v is not None else None for i, v in enumerate(s["vals"])]
            ys_json[s["sid"]] = [None if q is None else round(q[1], 1) for q in dentro]
            if s["tipo"] == "linha":  # a linha é recortada na borda do painel; o valor fica no tooltip
                els.append(f'<g class="serie-{s["sid"]}"><path d="{_path_com_lacunas(pontos, s.get("liga"))}" '
                           f'fill="none" stroke="{s["cor"]}" stroke-width="{2.5 if s.get("principal") else 2}" '
                           f'stroke-linejoin="round" stroke-linecap="round" clip-path="url(#{recorte})"/></g>')
                i_fim = max((i for i, q in enumerate(dentro) if q is not None), default=None)
                if i_fim is not None:
                    finais[s["sid"]] = (dentro[i_fim][0], dentro[i_fim][1], p["fmt"](s["vals"][i_fim]), s)
            else:
                els.append(f'<g class="serie-{s["sid"]}">' + "".join(
                    _marcador(q[0], q[1], s.get("forma", "circulo"), s["cor"]) for q in dentro if q is not None)
                    + "</g>")

        # valor final de cada linha na ponta direita; rótulos que colidiriam são afastados (mín. 15px) e ganham
        # um fio-guia até a ponta da linha
        ordem = sorted(finais, key=lambda sid: finais[sid][1])
        y_rot = {sid: min(max(finais[sid][1], topo + 6), base - 6) for sid in ordem}
        for a, b in zip(ordem, ordem[1:]):
            y_rot[b] = max(y_rot[b], y_rot[a] + 15)
        if ordem:
            y_rot[ordem[-1]] = min(y_rot[ordem[-1]], base - 6)
            for a, b in zip(reversed(ordem[:-1]), reversed(ordem[1:])):
                y_rot[a] = min(y_rot[a], y_rot[b] - 15)
        x_rot = W - PR + 14
        for sid in ordem:
            xf, yf, texto, s = finais[sid]
            yr = y_rot[sid]
            fio = (f'<line x1="{xf + 5:.1f}" y1="{yf:.1f}" x2="{x_rot - 4:.1f}" y2="{yr:.1f}" stroke="{_BASE}" '
                   f'stroke-width="1"/>' if abs(yr - yf) > 1.5 or xf < xs[-1] - 0.5 else "")
            peso = 700 if s.get("principal") else 600
            els.append(f'<g class="serie-{sid}">{fio}{_marcador(xf, yf, "circulo", s["cor"], r=4)}'
                       f'<text x="{x_rot:.1f}" y="{yr + 4:.1f}" font-size="12" font-weight="{peso}" '
                       f'fill="{_TINTA}">{_esc(texto)}</text></g>')
        y = base

    base_plot = y
    for x, texto in _rotulos_datas(datas, xs, temporal, x_de):
        els.append(f'<line x1="{x:.1f}" y1="{base_plot}" x2="{x:.1f}" y2="{base_plot + 5}" stroke="{_BASE}" '
                   f'stroke-width="1"/>')
        els.append(f'<text x="{x:.1f}" y="{base_plot + 19}" text-anchor="middle" font-size="11" fill="{_TINTA_FRACA}">'
                   f'{_esc(texto)}</text>')

    # camada do mouse: crosshair + um ponto por série de linha ou de pontos (posicionados no JS) e o retângulo que
    # captura o mouse, com os dados em JSON
    linhas = [[[s["sid"], s["cor"], p["fmt"](s["vals"][i]), s["nome"]]
               for p in paineis for s in p["series"] if s["vals"][i] is not None] for i in range(n)]
    hover = [f'<line class="serie-cross" x1="0" y1="{topo_plot}" x2="0" y2="{base_plot}" stroke="{_TINTA_FRACA}" '
             f'stroke-width="1"/>']
    hover += [f'<circle class="serie-dot" data-sid="{s["sid"]}" cx="0" cy="0" r="5" fill="{s["cor"]}" stroke="#fff" '
              f'stroke-width="2"/>' for p in paineis for s in p["series"] if s["tipo"] != "barras"]
    els.append(f'<g class="serie-hover" style="display:none" pointer-events="none">{"".join(hover)}</g>')
    dados = {"xs": [round(x, 1) for x in xs], "titulos": [_dt(d) for d in datas], "ys": ys_json, "linhas": linhas,
             "rodape": rodape, "clique": clique}
    if clique:
        dados["dias"] = dias_clique or [_iso(d) if rodape and rodape[i] else None for i, d in enumerate(datas)]
    els.append(f'<rect class="serie-overlay{" clicavel" if clique else ""}" x="{PL}" y="{topo_plot}" '
               f'width="{largura:.1f}" height="{base_plot - topo_plot:.1f}" fill="transparent" '
               f'data-serie="{_esc(json.dumps(dados, ensure_ascii=False))}"/>')
    return (f'<svg viewBox="0 0 {W} {base_plot + EIXO}" role="img" font-family="Segoe UI,Arial,sans-serif" '
            f'style="width:100%;display:block;overflow:visible">' + "".join(els) + "</svg>")


def _legenda(cid, paineis, nota=""):
    """Legenda acima do gráfico: a marca de cada série (linha, ponto ou barra) e, nas linhas e pontos que não são a
    série principal, a caixa que mostra ou esconde a série."""
    itens = []
    for p in paineis:
        for s in p["series"]:
            if s["tipo"] == "linha":
                marca = f'<i class="hist-key" style="background:{s["cor"]}"></i>'
            elif s["tipo"] == "pontos":
                forma = "border-radius:50%" if s.get("forma", "circulo") == "circulo" else "transform:rotate(45deg)"
                marca = f'<i class="hist-key-ponto" style="background:{s["cor"]};{forma}"></i>'
            else:
                marca = f'<i class="hist-key-barra" style="background:{s["cor"]}"></i>'
            if s["tipo"] == "barras" or s.get("principal"):
                itens.append(f'<span class="hist-leg">{marca}{_esc(s["nome"])}</span>')
            else:
                acao = f"toggleSerie(this, '{cid}', '{s['sid']}')"
                itens.append(f'<label class="hist-leg hist-leg-toggle"><input type="checkbox" checked '
                             f'onchange="{acao}">{marca}{_esc(s["nome"])}</label>')
    if nota:
        itens.append(f'<span class="hist-nota">{nota}</span>')
    return f'<div class="hist-legenda">{"".join(itens)}</div>'


# ── SVG: barras horizontais, cascata, dispersão ───────────────────────────────
def _barras_h(linhas, titulo_valor, ref=None, titulo_extra=None):
    """Barras horizontais, uma linha por item (ativo ou fundo) já na ordem: a barra sai do zero e o texto vai na
    ponta. linhas: [{"rotulo", "valor", "texto", "cor", "tip", "ativo" ou "fundo" (o clique abre a ficha do ativo
    ou troca o fundo), "extra" e "extra_texto" (a 2ª coluna, com titulo_extra)}]; ref = (valor, texto) da linha
    vertical de referência (a taxa da carteira)."""
    n = len(linhas)
    if not n:
        return ""
    W, TOPO, ALT, ROT = 1000, (46 if ref else 28), 24, 150
    x0, x1 = ROT + 12, (730 if titulo_extra else W - 10)
    vals = [li["valor"] for li in linhas] + [0.0] + ([ref[0]] if ref else [])
    lo, hi = min(vals), max(vals)
    esq, dir_ = x0 + (130 if lo < 0 else 0), x1 - 170   # espaço do texto nas pontas

    def _x(v):
        return esq + (v - lo) / ((hi - lo) or 1.0) * (dir_ - esq)

    base = TOPO + n * ALT
    zero = _x(0.0)
    els = [f'<text x="{x0}" y="14" font-size="11.5" font-weight="600" fill="{_TINTA}">{_esc(titulo_valor)}</text>',
           f'<line x1="{zero:.1f}" y1="{TOPO - 4}" x2="{zero:.1f}" y2="{base}" stroke="{_BASE}" stroke-width="1"/>']
    if titulo_extra:
        els.append(f'<text x="770" y="14" font-size="11.5" font-weight="600" fill="{_TINTA}">{_esc(titulo_extra)}</text>')
    maior_extra = max((li.get("extra") or 0) for li in linhas) or 1.0
    # rótulos de valor por cima da linha de referência, com um contorno da cor do fundo para não sumirem nela
    rotulos, linhas_hover = [], []
    halo = 'stroke="#fff" stroke-width="3" paint-order="stroke"'
    for i, li in enumerate(linhas):
        yc = TOPO + i * ALT + ALT / 2
        xv = _x(li["valor"])
        classe = "lk-ativo" if li.get("ativo") else "lk-fundo" if li.get("fundo") else ""
        alvo = (f' data-ativo="{_esc(li["ativo"])}"' if li.get("ativo") else
                f' data-fundo="{_esc(li["fundo"])}"' if li.get("fundo") else "")
        els.append(f'<text x="{ROT}" y="{yc + 4:.1f}" text-anchor="end" font-size="12" font-weight="600" '
                   f'fill="{ITAU_DARK}">{_esc(li["rotulo"])}</text>')
        els.append(f'<rect x="{min(zero, xv):.1f}" y="{yc - 7:.1f}" width="{max(abs(xv - zero), 1.5):.1f}" height="14" '
                   f'fill="{li["cor"]}" rx="3"/>')
        ancora = ("start", xv + 6) if li["valor"] >= 0 else ("end", xv - 6)
        rotulos.append(f'<text x="{ancora[1]:.1f}" y="{yc + 4:.1f}" text-anchor="{ancora[0]}" font-size="11.5" '
                       f'fill="{_TINTA}" {halo}>{_esc(li["texto"])}</text>')
        if titulo_extra and li.get("extra") is not None:
            we = max(li["extra"] / maior_extra * 150, 1.5)
            els.append(f'<rect x="770" y="{yc - 5:.1f}" width="{we:.1f}" height="10" fill="{COR_PESO}" rx="2"/>')
            els.append(f'<text x="{776 + we:.1f}" y="{yc + 4:.1f}" font-size="11" fill="{_TINTA_FRACA}">'
                       f'{_esc(li.get("extra_texto", ""))}</text>')
        # a linha inteira é a área do mouse (bem maior que a barra) e fica por cima de tudo
        linhas_hover.append(f'<rect class="svg-linha {classe}"{alvo} x="0" y="{yc - ALT / 2:.1f}" width="{W}" '
                            f'height="{ALT}" data-tip="{_esc(li["tip"])}"/>')
    if ref:
        xr = _x(ref[0])
        els.append(f'<line x1="{xr:.1f}" y1="{TOPO - 10}" x2="{xr:.1f}" y2="{base + 4}" stroke="{COR_CARTEIRA}" '
                   f'stroke-width="2"/>')
        els.append(f'<text x="{xr:.1f}" y="{TOPO - 15}" text-anchor="middle" font-size="11.5" font-weight="700" '
                   f'fill="{_TINTA}">{_esc(ref[1])}</text>')
    return (f'<svg viewBox="0 0 {W} {base + 8}" font-family="Segoe UI,Arial,sans-serif" '
            f'style="width:100%;display:block;overflow:visible">' + "".join(els + rotulos + linhas_hover) + "</svg>")


def _cascata(itens, total, tip_total, rotulo_total="CARTEIRA"):
    """Cascata vertical (a do attribution): cada item sobe ou desce a partir do acumulado e a última barra é o total.
    itens: [(rótulo, valor, tip)]."""
    barras, acum = [], 0.0
    for rotulo, v, tip in itens:
        barras.append((rotulo, acum, acum + v, ITAU_GREEN if v >= 0 else ITAU_RED, False, tip))
        acum += v
    barras.append((rotulo_total, 0.0, total, COR_CARTEIRA, True, tip_total))
    n = len(barras)
    muitos = n > 10
    W, PL, PR, PT = 1000, 70, 16, 22
    PB = 92 if muitos else 40
    H = 300 + PB
    largura, altura = W - PL - PR, H - PT - PB
    vaga = largura / n
    bar_w = min(vaga * 0.62, 44)
    ys = [b[1] for b in barras] + [b[2] for b in barras] + [0.0]
    y_lo, y_hi, ticks, passo = _dominio_eixo(min(ys), max(ys))

    def _y(v):
        return PT + altura * (1 - (v - y_lo) / ((y_hi - y_lo) or 1.0))

    els = []
    for t in ticks:
        yg = _y(t)
        zero = abs(t) < passo * 1e-6
        els.append(f'<line x1="{PL}" y1="{yg:.1f}" x2="{W - PR}" y2="{yg:.1f}" stroke="{_BASE if zero else _GRADE}" '
                   f'stroke-width="1"/>')
        els.append(f'<text x="{PL - 8}" y="{yg + 4:.1f}" text-anchor="end" font-size="11" fill="{_TINTA_FRACA}">'
                   f'{_fmt_tick(t, passo)}</text>')
    fim_anterior = None
    for i, (rotulo, ini, fim, cor, eh_total, tip) in enumerate(barras):
        bx = PL + i * vaga + (vaga - bar_w) / 2
        cx = bx + bar_w / 2
        y_top, y_bot = _y(max(ini, fim)), _y(min(ini, fim))
        bh = max(y_bot - y_top, 2.0)
        v = fim - ini
        if fim_anterior is not None and not eh_total:
            els.append(f'<line x1="{bx - (vaga - bar_w):.1f}" y1="{fim_anterior:.1f}" x2="{bx:.1f}" '
                       f'y2="{fim_anterior:.1f}" stroke="#c8d0dc" stroke-width="1.2" stroke-dasharray="4,3"/>')
        els.append(f'<rect x="{bx:.1f}" y="{y_top:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{cor}" '
                   f'opacity="{0.9 if eh_total else 0.84}" rx="3" class="svg-bar" data-tip="{_esc(tip)}"/>')
        if eh_total or (bh >= 16 and not muitos) or (muitos and bh >= 26):
            texto = _cdi_mais(v) if eh_total else ("+" if v > 0 else "") + _br(v, 2)
            ly = y_top - 5 if v >= 0 else y_bot + 13
            els.append(f'<text x="{cx:.1f}" y="{ly:.1f}" text-anchor="middle" font-size="10.5" font-weight="700" '
                       f'fill="{_TINTA}">{_esc(texto)}</text>')
        ly = H - PB + 14
        if muitos:
            els.append(f'<text x="{cx:.1f}" y="{ly:.1f}" text-anchor="end" font-size="10.5" fill="#444" '
                       f'transform="rotate(-45,{cx:.1f},{ly:.1f})">{_esc(str(rotulo)[:22])}</text>')
        else:
            els.append(f'<text x="{cx:.1f}" y="{ly + 4:.1f}" text-anchor="middle" font-size="10.5" fill="#444">'
                       f'{_esc(str(rotulo)[:16])}</text>')
        fim_anterior = _y(fim)
    return (f'<svg viewBox="0 0 {W} {H}" font-family="Segoe UI,Arial,sans-serif" '
            f'style="width:100%;display:block;overflow:visible">' + "".join(els) + "</svg>")


def _dispersao(pontos, titulo_x, titulo_y):
    """Dispersão de um grupo: x = taxa da VCRA (pelo PU pago), y = taxa da boleta, a diagonal onde as duas são iguais
    e os pontos em destaque (aviso Boleta × VCRA) com o lote ao lado. pontos: [{"x", "y", "cor", "destaque",
    "rotulo", "tip", "ativo"}]; os dois eixos têm a mesma escala, para a diagonal ficar a 45°."""
    if not pontos:
        return ""
    W, H, PL, PR, PT, PB = 480, 410, 62, 20, 14, 52
    vals = [p["x"] for p in pontos] + [p["y"] for p in pontos]
    lo, hi, ticks, passo = _dominio_eixo(min(vals), max(vals))
    w, h = W - PL - PR, H - PT - PB

    def _x(v):
        return PL + (v - lo) / ((hi - lo) or 1.0) * w

    def _y(v):
        return PT + h * (1 - (v - lo) / ((hi - lo) or 1.0))

    els = [f'<rect x="{PL}" y="{PT}" width="{w}" height="{h}" fill="none" stroke="{_GRADE}"/>']
    for t in ticks:
        els.append(f'<line x1="{_x(t):.1f}" y1="{PT}" x2="{_x(t):.1f}" y2="{PT + h}" stroke="{_GRADE}" stroke-width="1"/>')
        els.append(f'<line x1="{PL}" y1="{_y(t):.1f}" x2="{PL + w}" y2="{_y(t):.1f}" stroke="{_GRADE}" stroke-width="1"/>')
        els.append(f'<text x="{_x(t):.1f}" y="{PT + h + 16}" text-anchor="middle" font-size="11" fill="{_TINTA_FRACA}">'
                   f'{_fmt_tick(t, passo)}</text>')
        els.append(f'<text x="{PL - 8}" y="{_y(t) + 4:.1f}" text-anchor="end" font-size="11" fill="{_TINTA_FRACA}">'
                   f'{_fmt_tick(t, passo)}</text>')
    els.append(f'<line x1="{_x(lo):.1f}" y1="{_y(lo):.1f}" x2="{_x(hi):.1f}" y2="{_y(hi):.1f}" stroke="{_TINTA_FRACA}" '
               f'stroke-width="1.2"/>')
    els.append(f'<text x="{PL + w / 2:.1f}" y="{H - 8}" text-anchor="middle" font-size="11.5" font-weight="600" '
               f'fill="{_TINTA}">{_esc(titulo_x)}</text>')
    els.append(f'<text x="14" y="{PT + h / 2:.1f}" text-anchor="middle" font-size="11.5" font-weight="600" '
               f'fill="{_TINTA}" transform="rotate(-90,14,{PT + h / 2:.1f})">{_esc(titulo_y)}</text>')
    alvos, ocupados = [], []
    for p in sorted(pontos, key=lambda q: q["destaque"]):
        x, y = _x(p["x"]), _y(p["y"])
        els.append(_marcador(x, y, "circulo", COR_DESTAQUE if p["destaque"] else p["cor"]))
        if p["destaque"]:
            # rótulo do lote: o 1º canto livre em volta do ponto (sem cobrir outro rótulo nem sair do gráfico)
            larg = 6.3 * len(str(p["rotulo"]))
            for dx, dy in ((8, -7), (8, 15), (-8 - larg, -7), (-8 - larg, 15), (8, -20), (-8 - larg, 28)):
                caixa = (x + dx, y + dy - 10, x + dx + larg, y + dy + 2)
                if (PL <= caixa[0] and caixa[2] <= PL + w and PT <= caixa[1] and caixa[3] <= PT + h
                        and not any(a[0] < caixa[2] and caixa[0] < a[2] and a[1] < caixa[3] and caixa[1] < a[3]
                                    for a in ocupados)):
                    break
            ocupados.append(caixa)
            els.append(f'<text x="{caixa[0]:.1f}" y="{caixa[3] - 2:.1f}" font-size="10.5" font-weight="600" '
                       f'fill="{_TINTA}" stroke="#fff" stroke-width="3" paint-order="stroke">{_esc(p["rotulo"])}</text>')
        alvos.append(f'<circle class="svg-ponto lk-ativo" data-ativo="{_esc(p["ativo"])}" cx="{x:.1f}" cy="{y:.1f}" '
                     f'r="11" data-tip="{_esc(p["tip"])}"/>')
    return (f'<svg viewBox="0 0 {W} {H}" font-family="Segoe UI,Arial,sans-serif" '
            f'style="width:100%;max-width:560px;display:block;overflow:visible">' + "".join(els + alvos) + "</svg>")


def _barra_composicao(partes):
    """Barra 100% (parte do todo), com o rótulo dentro do segmento só quando cabe. partes: [(nome, valor, cor)]."""
    partes = [(nome, v, cor) for nome, v, cor in partes if not _vazio(v) and v > 0]
    total = sum(v for _, v, _ in partes)
    if not total:
        return ""
    segs, itens = [], []
    for nome, v, cor in partes:
        pct = v / total * 100
        rotulo = f"{nome} {_br(pct, 1)}%" if pct >= 14 else ""
        segs.append(f'<div class="comp-seg" style="flex:{pct:.4f};background:{cor}" '
                    f'data-tip="{_esc(f"{nome}{chr(10)}{_br(pct, 1)}% do financeiro{chr(10)}{_rs(v)}")}">'
                    f'{_esc(rotulo)}</div>')
        itens.append(f'<span class="hist-leg"><i class="hist-key-barra" style="background:{cor}"></i>'
                     f'{_esc(nome)}: {_br(pct, 1)}% ({_esc(_rs(v))})</span>')
    return f'<div class="comp-barra">{"".join(segs)}</div><div class="hist-legenda comp-leg">{"".join(itens)}</div>'


def _sparkline(vals, cor):
    """Linha pequena da série (no cartão da carteira), com o último ponto marcado."""
    v = [x for x in vals if x is not None]
    if len(v) < 2:
        return ""
    W, H = 170, 36
    lo, hi = min(v), max(v)
    pts = [(3 + i / (len(v) - 1) * (W - 8), H - 5 - (x - lo) / ((hi - lo) or 1.0) * (H - 10)) for i, x in enumerate(v)]
    path = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    return (f'<svg class="spark" viewBox="0 0 {W} {H}" width="{W}" height="{H}" aria-hidden="true">'
            f'<path d="{path}" fill="none" stroke="{cor}" stroke-width="1.8" stroke-linejoin="round"/>'
            f'<circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="3" fill="{cor}"/></svg>')


# ── Cadastro do ativo (FUNDOS_CADASTRO_ATIVOS) ────────────────────────────────
# campos da ficha, por seção; os outros ficam só em "Todos os campos"
_CADASTRO_SECOES = [
    ("Emissão", [("issuer", "Emissor"), ("emissor", "Código do emissor"), ("issuer_cnpj", "CNPJ do emissor"),
                 ("data_emissao", "Emissão"), ("vencimento", "Vencimento"), ("taxa_emissao", "Taxa de emissão"),
                 ("indexador", "Indexador"), ("tipo_indexador", "Tipo de indexador")]),
    ("Crédito e risco", [("rating_itau", "Rating Itaú"), ("grupo_economico_ce", "Grupo econômico"),
                         ("setor_iam_ce", "Setor"), ("subsetor_iam_ce", "Subsetor"),
                         ("gics_sector_name", "Setor GICS"), ("estruturado_ce", "Estruturado"),
                         ("watchlist_ce", "Watchlist"), ("exotico", "Exótico"), ("divida", "Dívida"),
                         ("fator_risco", "Fator de risco")]),
    ("Identificação", [("ativo", "Ativo"), ("isin", "ISIN"), ("ticker_bolsa", "Ticker"), ("bolsa", "Bolsa"),
                       ("secID_CRIMS", "secID CRIMS"), ("issuer_cd", "Issuer (CRIMS)"), ("tipo", "Tipo"),
                       ("tipo_marcacao", "Marcação"), ("pais", "País"), ("moeda_exposicao", "Moeda")]),
]
_CADASTRO_SIM_NAO = {"estruturado_ce", "watchlist_ce", "exotico", "risco_cambial"}


def _cadastro_vigente(cad, data_ref):
    """Cadastro na data: ({ativo: {campo: (valor, desde, fonte)}} com a versão mais recente de cada campo até a
    data, {ativo: {campo: [(desde, valor), ...]}} dos campos que mudaram de valor)."""
    atual, versoes = {}, {}
    if cad is None or cad.empty:
        return atual, versoes
    cad = cad[cad["desde"] <= data_ref] if data_ref is not None else cad
    for (codigo, campo), g in cad.sort_values("desde", kind="stable").groupby(["codigo", "campo"], sort=False):
        u = g.iloc[-1]
        atual.setdefault(str(codigo), {})[campo] = (u["valor"], u["desde"], u.get("fonte"))
        if len(g) > 1:
            versoes.setdefault(str(codigo), {})[campo] = list(zip(g["desde"], g["valor"]))
    return atual, versoes


def _desde_texto(d):
    """Data da versão do campo; 01/01/1900 é a carga inicial do cadastro."""
    return "" if _vazio(d) else "carga inicial" if pd.Timestamp(d).year == 1900 else _dt(d)


def _valor_cadastro(campo, v, campos, data_ref):
    """Valor de um campo do cadastro como texto: datas dd/mm/aaaa (o vencimento com o prazo que falta), flags 0/1 como
    Sim/Não, CNPJ formatado e a taxa de emissão na convenção do indexador do ativo."""
    if _vazio(v):
        return ""
    if isinstance(v, (pd.Timestamp, datetime, date)):
        texto = _dt(v)
        if campo == "vencimento" and data_ref is not None:
            anos = (pd.Timestamp(v) - data_ref).days / 365.25
            texto += f" (faltam {_br(anos, 1)} anos)" if anos > 0 else " (vencido)"
        return texto
    if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
        if campo in _CADASTRO_SIM_NAO:
            return "Sim" if v else "Não"
        if campo == "taxa_emissao":
            indexador = str(campos.get("indexador", ("",))[0] or "").upper().replace(" ", "")
            if indexador.startswith("CDI+"):
                return _cdi_mais(float(v))
            return f"{_br(v)}% do CDI" if "%" in indexador or indexador in ("CDI", "DI") else _br(v)
        return _br(v, 0) if float(v).is_integer() else f"{float(v):.6g}".replace(".", ",")
    if campo == "issuer_cnpj":
        digitos = re.sub(r"\D", "", str(v))
        if 0 < len(digitos) <= 14:
            d = digitos.zfill(14)
            return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return str(v)


def _ficha_cadastro(campos, versoes, data_ref):
    """Cadastro de um ativo para a ficha: nome, descrição, as seções de _CADASTRO_SECOES, todos os campos (valor,
    desde quando e fonte) e as alterações de valor."""
    def valor(campo):
        return _valor_cadastro(campo, campos[campo][0], campos, data_ref) if campo in campos else ""

    secoes = [[titulo, [[rotulo, valor(c)] for c, rotulo in itens if valor(c)]] for titulo, itens in _CADASTRO_SECOES]
    fonte = {c: "" if _vazio(campos[c][2]) else str(campos[c][2]) for c in campos}
    return {"nome": valor("security_name"), "descricao": valor("flyer_descricao_ativo"),
            "secoes": [s for s in secoes if s[1]],
            "campos": [[c, valor(c), _desde_texto(campos[c][1]), fonte[c]] for c in sorted(campos, key=str.lower)],
            "mudancas": [[c, [[_desde_texto(d), _valor_cadastro(c, v, campos, None)] for d, v in vs]]
                         for c, vs in sorted(versoes.items())]}


# ── Dados de cada fundo ───────────────────────────────────────────────────────
_COLUNAS_DATA = ("data", "dt_compra", "data_boleta", "dt_pu", "desde")


def _com_datas(df):
    """Datas como Timestamp (no Excel relido já vêm assim; na memória, a série tem datetime.date)."""
    df = df.copy()
    for c in _COLUNAS_DATA:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def _do_fundo(df, fundo):
    if df is None or df.empty or "fundo" not in df.columns:
        return pd.DataFrame()
    return df[df["fundo"] == fundo].reset_index(drop=True)


def _emissao(df):
    """Taxa de emissão na convenção do grupo: o spread no CDI+ e o % do CDI no %CDI."""
    return np.where(df["grupo"] == "CDI+", df["taxa_emissao"], df["perc_cdi"])


def _preparar_fundo(t, info, cadastro=None):
    """Tabelas de um fundo, com as colunas que o relatório acrescenta: peso e contribuição de cada ativo para a taxa
    da carteira, avisos por ativo, nome, grupo econômico e rating do cadastro (cadastro = o atual do
    _cadastro_vigente), emissão na convenção do grupo e a fonte da taxa com "sem taxa" no lugar do vazio."""
    fundo = info["fundo"]
    f = {"fundo": fundo, "info": info, "slug": re.sub(r"\W", "_", str(fundo)),
         "nome": "" if _vazio(info.get("nome")) else str(info["nome"]),
         "data": None if _vazio(info.get("data")) else pd.Timestamp(info["data"]),
         "cdi": None if _vazio(info.get("cdi")) else float(info["cdi"]),
         "erro": str(info["status"]) if str(info.get("status", "")).startswith("erro") else None}
    for chave, aba in (("carteira", "Carteira"), ("ativos", "Ativos"), ("lotes", "Lotes"), ("trades", "Trades"),
                       ("por_dia", "Trades por dia"), ("avisos", "Avisos"), ("historico", "Histórico")):
        f[chave] = _do_fundo(t.get(aba), fundo)
    avisos_por_ativo = f["avisos"]["ativo"].value_counts() if len(f["avisos"]) else pd.Series(dtype=float)
    a = f["ativos"]
    if len(a):
        a["emissao"] = _emissao(a)
        ok = a["financeiro"].notna() & a["taxa_media"].notna()  # os que entram na média (consolidar no __main__)
        total = a.loc[ok, "financeiro"].sum()
        a["peso"] = (a["financeiro"] / total * 100).where(ok) if total else np.nan
        a["contrib"] = a["peso"] / 100 * a["taxa_cdi_mais"]
        a["n_avisos"] = a["codigo"].map(avisos_por_ativo).fillna(0)
        cad = [(cadastro or {}).get(str(c), {}) for c in a["codigo"]]
        for coluna, campo in (("nome_ativo", "security_name"), ("grupo_eco", "grupo_economico_ce"),
                              ("rating", "rating_itau")):
            a[coluna] = [x.get(campo, (None,))[0] for x in cad]
        f["ativos"] = a.sort_values(["grupo", "codigo"], na_position="last").reset_index(drop=True)
    for chave in ("lotes", "trades"):
        df = f[chave]
        if len(df):
            df["emissao"] = _emissao(df)
            df["fonte_rot"] = df["fonte_taxa"].fillna("").replace("", "sem taxa")
    if len(f["trades"]):
        f["trades"] = f["trades"].sort_values(["data", "operacao", "codigo", "CD"], ascending=[False, True, True, True])
    if len(f["por_dia"]):
        f["por_dia"] = f["por_dia"].sort_values(["data", "operacao"], ascending=[False, True])
    if len(f["historico"]):
        f["historico"] = f["historico"].sort_values("data").reset_index(drop=True)
    return f


def _media_trades(df):
    """(trades, financeiro, taxa média em CDI+ equivalente ponderada pelo financeiro dos trades com taxa)."""
    ok = df[df["taxa_cdi_mais"].notna()]
    taxa = (ok["financeiro"] * ok["taxa_cdi_mais"]).sum() / ok["financeiro"].sum() if len(ok) else np.nan
    return len(df), df["financeiro"].sum(), taxa


def _vals(serie, validos=None):
    """Lista para os gráficos: None no vazio (e onde validos for False)."""
    validos = [True] * len(serie) if validos is None else validos
    return [None if _vazio(v) or not ok else float(v) for v, ok in zip(serie, validos)]


# ── Abas de cada fundo ────────────────────────────────────────────────────────
def _aba_resumo(f):
    c = f["carteira"].set_index("grupo") if len(f["carteira"]) else pd.DataFrame(columns=["financeiro"])

    def g(grupo, coluna):
        return c.at[grupo, coluna] if grupo in c.index and coluna in c.columns else np.nan

    taxa, fin = g("CARTEIRA", "taxa_cdi_mais"), g("CARTEIRA", "financeiro")
    h = f["historico"]
    spark = _sparkline(_vals(h["taxa_carteira"], list(h["status"] == "OK")), COR_CARTEIRA) if len(h) else ""
    cdi = f" · CDI de {_br(f['cdi'])}% a.a." if f["cdi"] else ""
    info, av = f["info"], f["avisos"]
    tipos = av["aviso"].value_counts(sort=False) if len(av) else pd.Series(dtype=int)
    cartoes = [
        _kpi("Taxa média da carteira", _cdi_mais(taxa) or "sem taxa", f"em CDI+ equivalente{cdi}", COR_CARTEIRA,
             grafico=spark),
        _kpi("%CDI", _taxa("%CDI", g("%CDI", "taxa_media")) or "—",
             f"{_rs(g('%CDI', 'financeiro'))} · {_plural(_int(g('%CDI', 'n_ativos')), 'ativo')}", COR_GRUPO["%CDI"]),
        _kpi("CDI+", _taxa("CDI+", g("CDI+", "taxa_media")) or "—",
             f"{_rs(g('CDI+', 'financeiro'))} · {_plural(_int(g('CDI+', 'n_ativos')), 'ativo')}", COR_GRUPO["CDI+"]),
        _kpi("Financeiro na média", _rs(fin), f"{_plural(_int(info.get('n_ativos')), 'ativo')} · "
             f"{_plural(_int(info.get('n_lotes')), 'lote')} em aberto"),
        _kpi("Avisos", _br(len(av), 0), " · ".join(f"{t} {n}" for t, n in list(tipos.items())[:3]) or "nenhum",
             extra=' data-ir="avisos" role="button" tabindex="0" title="Abrir a aba AVISOS"'),
    ]
    html = f'<div class="kpis">{"".join(cartoes)}</div>'

    comp = _barra_composicao([("CDI+", g("CDI+", "financeiro"), COR_GRUPO["CDI+"]),
                              ("%CDI", g("%CDI", "financeiro"), COR_GRUPO["%CDI"])])
    if comp:
        html += _secao("Composição do financeiro na média", comp)

    a = f["ativos"]
    a = a[a["contrib"].notna()] if len(a) else a
    if len(a) and not _vazio(taxa):
        top = a.reindex(a["contrib"].abs().sort_values(ascending=False).index)
        principais, resto = top.head(12).sort_values("contrib", ascending=False), top.iloc[12:]
        itens, acum = [], 0.0
        for r in principais.itertuples():
            acum += r.contrib
            itens.append((r.codigo, r.contrib, f"{r.codigo} · {r.grupo}\nContribuição: {_br(r.contrib, 4)} p.p.\n"
                          f"Taxa: {_taxa(r.grupo, r.taxa_media)} · peso {_br(r.peso, 2)}%\nAcumulado: {_cdi_mais(acum)}"))
        if len(resto):
            acum += resto["contrib"].sum()
            itens.append((f"Demais ({len(resto)})", resto["contrib"].sum(),
                          f"Demais {_plural(len(resto), 'ativo')}\nContribuição: {_br(resto['contrib'].sum(), 4)} p.p.\n"
                          f"Peso somado: {_br(resto['peso'].sum(), 2)}%\nAcumulado: {_cdi_mais(acum)}"))
        html += _secao("De onde vem a taxa da carteira: contribuição de cada ativo (p.p. de CDI+)",
                       _cascata(itens, taxa, f"Carteira\n{_cdi_mais(taxa)} (CDI+ equivalente)\n{_rs(fin)}"),
                       "Contribuição = peso do ativo no financeiro × taxa dele em CDI+ equivalente; a soma das barras é a "
                       "taxa da carteira. Os maiores em valor absoluto; o resto vai em Demais. Todos os ativos estão na "
                       "aba ATIVOS.")

    if len(f["carteira"]):
        cart = f["carteira"].copy()
        cart["peso"] = cart["financeiro"] / fin * 100 if fin else np.nan
        linhas = cart[cart["grupo"] != "CARTEIRA"]
        total = cart[cart["grupo"] == "CARTEIRA"].assign(grupo="Carteira").to_dict("records")
        colunas = [("grupo", "Grupo", "grupo", "Grupo dos ativos"), ("n_ativos", "Ativos", "int", "Ativos com taxa e PU"),
                   ("financeiro", "Financeiro (R$)", "int", "Quantidade em aberto × último PU da posição"),
                   ("peso", "Peso", "pct", "Parte do financeiro na média"),
                   ("taxa_media", "Taxa média", "conv", "Média ponderada pelo financeiro, na convenção do grupo"),
                   ("taxa_cdi_mais", "Em CDI+ equivalente", "eq", "Média em CDI+ equivalente (junta os grupos)")]
        html += f'<h2 class="aba-title">Carteira por grupo</h2>{_tabela(linhas, colunas, rodape=total)}'

    tr = f["trades"]
    if len(tr):
        cartoes, dias = [], tr["data"]
        quando = f"de {_dt(dias.min())} a {_dt(dias.max())}" if dias.nunique() > 1 else f"em {_dt(dias.min())}"
        ir = ' data-ir="trades" role="button" tabindex="0" title="Abrir a aba TRADES"'
        for op in ("Compra", "Venda"):
            n, fin_op, taxa_op = _media_trades(tr[tr["operacao"] == op])
            if n:
                cartoes.append(_kpi(f"{op}s: taxa média", _cdi_mais(taxa_op) or "sem taxa",
                                    f"{_plural(n, op.lower())} · {_rs(fin_op)} · {quando}", COR_OPERACAO[op], extra=ir))
        if dias.nunique() > 1:
            cartoes.append(_kpi("Dias com trade", _br(dias.nunique(), 0), quando, extra=ir))
        html += f'<h2 class="aba-title">Trades</h2><div class="kpis">{"".join(cartoes)}</div>'
    return html


def _aba_historico(f, abre_dia=False):
    """Gráfico e tabela da série; com abre_dia (index.html), clicar numa data abre o relatório do dia."""
    h = f["historico"]
    if h.empty:
        return '<p class="aviso">Sem série para este fundo.</p>'
    ok = list(h["status"] == "OK")
    datas = list(h["data"])
    paineis = [
        {"titulo": "Taxa em CDI+ equivalente (spread, % a.a.)", "altura": 250, "robusto": True, "fmt": _cdi_mais,
         "series": [{"sid": "carteira", "nome": "Carteira (CDI+ equivalente)", "vals": _vals(h["taxa_carteira"], ok),
                     "cor": COR_CARTEIRA, "tipo": "linha", "principal": True},
                    {"sid": "cdimais", "nome": "CDI+ (spread médio)", "vals": _vals(h["taxa_mais"], ok),
                     "cor": COR_GRUPO["CDI+"], "tipo": "linha"}]},
        {"titulo": "%CDI: taxa média (% do CDI)", "altura": 140, "robusto": True, "sufixo": "%",
         "fmt": lambda v: f"{_br(v)}% do CDI",
         "series": [{"sid": "pct", "nome": "%CDI (taxa média)", "vals": _vals(h["taxa_pct"], ok),
                     "cor": COR_GRUPO["%CDI"], "tipo": "linha"}]},
        {"titulo": "Financeiro na média (R$ mi)", "altura": 120, "fmt": _rs, "escala": 1e6, "series": [
            {"sid": "fin-mais", "nome": "Financeiro CDI+", "vals": _vals(h["fin_mais"], ok), "cor": COR_GRUPO["CDI+"],
             "tipo": "barras"},
            {"sid": "fin-pct", "nome": "Financeiro %CDI", "vals": _vals(h["fin_pct"], ok), "cor": COR_GRUPO["%CDI"],
             "tipo": "barras"}]},
    ]
    for p in paineis:
        p["series"] = [s for s in p["series"] if any(v is not None for v in s["vals"])]
    paineis = [p for p in paineis if p["series"]]
    rodape = [f"{_plural(r.n_ativos, 'ativo')} · {_plural(r.n_lotes, 'lote')} · {_plural(r.n_avisos, 'aviso')} · CDI "
              f"{_br(r.cdi)}%" if r.status == "OK" else str(r.status) for r in h.itertuples()]
    if abre_dia:
        rodape = [r + " — clique para abrir o dia" for r in rodape]

    validos = h[h["status"] == "OK"]
    resumo = ""
    if len(validos):
        i, u = validos.iloc[0], validos.iloc[-1]
        mn, mx = validos.loc[validos["taxa_carteira"].idxmin()], validos.loc[validos["taxa_carteira"].idxmax()]
        var = u["taxa_carteira"] - i["taxa_carteira"]
        resumo = (f"Carteira de <b>{_cdi_mais(i['taxa_carteira'])}</b> em {_dt(i['data'])} para "
                  f"<b>{_cdi_mais(u['taxa_carteira'])}</b> em {_dt(u['data'])} ({'+' if var > 0 else ''}{_br(var)} p.p.); "
                  f"mínima {_cdi_mais(mn['taxa_carteira'])} em {_dt(mn['data'])}, máxima "
                  f"{_cdi_mais(mx['taxa_carteira'])} em {_dt(mx['data'])}. {_plural(len(h), 'data')}"
                  f"{f', {len(h) - len(validos)} sem taxa' if len(h) > len(validos) else ''}.")
    cid = f"serie-{f['slug']}-hist"
    clique = "#dia:resumo" if abre_dia else None
    grafico = (_legenda(cid, paineis) + f'<div id="{cid}" class="serie-chart">'
               f'{_grafico_serie(cid, datas, paineis, rodape=rodape, clique=clique)}</div>'
               if paineis else '<p class="aviso">Nenhuma data com taxa na série.</p>')
    html = _secao("Histórico da taxa média", grafico,
                  resumo + " Cada data é recalculada só com o que existia nela (VCRA e boletas até a data, PU dos dias "
                  "anteriores, CDI do dia). Passe o mouse para ver os valores; as caixas da legenda mostram ou "
                  "escondem as linhas." + (" Clique numa data, no gráfico ou na tabela, para abrir o relatório do "
                                           "dia." if abre_dia else ""))
    colunas = [("data", "Data", "data", "Data da carteira"), ("status", "Status", "status", "OK ou o motivo da falha"),
               ("taxa_carteira", "Carteira", "eq", "Taxa da carteira em CDI+ equivalente"),
               ("financeiro", "Financeiro (R$)", "int", "Financeiro dos ativos na média"),
               ("taxa_pct", "%CDI: taxa", "pct", "Taxa média dos %CDI, em % do CDI"),
               ("fin_pct", "%CDI: financeiro (R$)", "int", "Financeiro dos %CDI"),
               ("taxa_mais", "CDI+: spread", "eq", "Spread médio dos CDI+"),
               ("fin_mais", "CDI+: financeiro (R$)", "int", "Financeiro dos CDI+"),
               ("n_ativos", "Ativos", "int", "Ativos com lote em aberto"), ("n_lotes", "Lotes", "int", "Lotes em aberto"),
               ("cdi", "CDI (% a.a.)", "t2", "CDI usado para converter %CDI em CDI+ equivalente"),
               ("n_avisos", "Avisos", "int", "Avisos na data"),
               ("avisos", "Avisos por tipo", "longo", "Quantos de cada tipo")]
    tid = f"tbl-{f['slug']}-historico"
    tabela = _tabela(h.sort_values("data", ascending=False), colunas, tid, alta=True,
                     attrs=[("dia", "data")] if abre_dia else (), extra=' data-abre-dia="resumo"' if abre_dia else "")
    return (html + f'<h2 class="aba-title">Tabela: uma linha por data (mais recente primeiro)</h2>'
            f'{_filtros(tid, dica="Filtrar (data, status, aviso...)")}{tabela}')


def _fora_da_media(r):
    if _vazio(r["qt_lotes"]):
        return "sem lote na VCRA"
    return "sem taxa" if _vazio(r["taxa_media"]) else "sem PU" if _vazio(r["pu"]) else ""


def _aba_ativos(f):
    a = f["ativos"]
    if a.empty:
        return '<p class="aviso">Nenhum ativo na data.</p>'
    taxa = f["carteira"].set_index("grupo")["taxa_cdi_mais"].get("CARTEIRA", np.nan) if len(f["carteira"]) else np.nan
    na_media = a[a["peso"].notna() & a["taxa_cdi_mais"].notna()].sort_values("taxa_cdi_mais", ascending=False)
    linhas = []
    for r in na_media.itertuples():
        proprio = f" ({_br(r.taxa_media)}% do CDI)" if r.grupo == "%CDI" else ""
        nome = "" if _vazio(r.nome_ativo) else f"\n{r.nome_ativo}"
        linhas.append({
            "rotulo": r.codigo, "valor": r.taxa_cdi_mais, "texto": _cdi_mais(r.taxa_cdi_mais) + proprio,
            "cor": COR_GRUPO.get(r.grupo, _BASE), "ativo": r.codigo, "extra": r.peso, "extra_texto": f"{_br(r.peso, 1)}%",
            "tip": f"{r.codigo} · {r.grupo}{nome}\nTaxa média: {_taxa(r.grupo, r.taxa_media)}\nCDI+ equivalente: "
                   f"{_cdi_mais(r.taxa_cdi_mais)}\nFinanceiro: {_rs(r.financeiro)} · peso {_br(r.peso, 2)}%\n"
                   f"Contribuição: {_br(r.contrib, 4)} p.p.\nClique para abrir a ficha"})
    fora = [f"{r['codigo']} ({_fora_da_media(r)})" for r in a.to_dict("records") if _fora_da_media(r)]
    legenda = "".join(f'<span class="hist-leg"><i class="hist-key-barra" style="background:{cor}"></i>{g}</span>'
                      for g, cor in COR_GRUPO.items() if g in set(na_media["grupo"]))
    legenda += f'<span class="hist-leg"><i class="hist-key" style="background:{COR_CARTEIRA}"></i>Carteira</span>'
    grafico = (f'<div class="hist-legenda">{legenda}</div>' + _barras_h(
        linhas, "Taxa em CDI+ equivalente", None if _vazio(taxa) else (taxa, f"Carteira {_cdi_mais(taxa)}"),
        "Peso no financeiro")) if linhas else '<p class="aviso">Nenhum ativo com taxa e PU.</p>'
    explica = ("Barras ordenadas pela taxa em CDI+ equivalente (os %CDI convertidos com o CDI da data, com o % do CDI "
               "entre parênteses); a linha laranja é a taxa da carteira. À direita, o peso de cada ativo no "
               "financeiro da média. Clique num ativo para abrir a ficha com os lotes, os trades e os avisos.")
    if fora:
        explica += f" <b>Fora da média:</b> {_esc(', '.join(fora))}."
    html = _secao("Taxa e peso de cada ativo", grafico, explica)

    colunas = [("codigo", "Ativo", "ativo", "Clique para abrir a ficha do ativo"),
               ("grupo", "Grupo", "grupo", "CDI+ (tem spread de emissão) ou %CDI"),
               ("tipo", "Tipo", "texto", "RFTP_CD da VCRAOPRF"),
               ("grupo_eco", "Grupo econômico", "texto", "Grupo econômico de risco (FUNDOS_CADASTRO_ATIVOS)"),
               ("rating", "Rating", "texto", "Rating Itaú (FUNDOS_CADASTRO_ATIVOS)"),
               ("emissao", "Emissão", "conv", "Taxa de emissão: spread (CDI+) ou % do CDI"),
               ("n_lotes", "Lotes", "int", "Lotes em aberto na VCRA"),
               ("n_sem_boleta", "Sem boleta válida", "int", "Lotes sem boleta válida"),
               ("n_manual", "Corrigidos", "int", "Lotes com a taxa da aba Correções"),
               ("qt_lotes", "Qtd lotes", "int", "Quantidade em aberto nos lotes da VCRA"),
               ("qt_posicao", "Qtd posição", "int", "Quantidade na VW_FUNDOS_POSICAO na data"),
               ("dif_qt", "Diferença", "int", "Lotes − posição (diferente de zero vira aviso)"),
               ("taxa_vcra", "Taxa VCRA", "conv", "Média da taxa da VCRA (pelo PU pago), na convenção do grupo"),
               ("taxa_media", "Taxa média", "conv", "Média das taxas usadas nos lotes, ponderada pela quantidade"),
               ("taxa_cdi_mais", "CDI+ equivalente", "eq", "Taxa média em CDI+ equivalente"),
               ("pu", "PU", "pu", "Último PU com preço na posição"), ("dt_pu", "Data do PU", "data", "Data desse PU"),
               ("financeiro", "Financeiro (R$)", "int", "Quantidade nos lotes × PU"),
               ("peso", "Peso", "pct", "Parte do financeiro da média (vazio: fora da média)"),
               ("contrib", "Contribuição (p.p.)", "t4", "Peso × CDI+ equivalente; a soma é a taxa da carteira"),
               ("n_avisos", "Avisos", "int", "Avisos do ativo (veja a ficha ou a aba AVISOS)")]
    sem_cadastro = {c for c in ("grupo_eco", "rating") if a[c].map(_vazio).all()}
    colunas = [c for c in colunas if c[0] not in sem_cadastro]
    ok = a["peso"].notna()
    total = [{"codigo": "Carteira", "n_lotes": a["n_lotes"].sum(), "financeiro": a.loc[ok, "financeiro"].sum(),
              "peso": a["peso"].sum(), "taxa_cdi_mais": taxa, "contrib": a["contrib"].sum(),
              "n_avisos": a["n_avisos"].sum()}]
    tid = f"tbl-{f['slug']}-ativos"
    grupos = [g for g in COR_GRUPO if g in set(a["grupo"].dropna())]
    return (html + f'<h2 class="aba-title">Tabela de ativos</h2>'
            f'{_filtros(tid, [("grupo", "Grupo", grupos)], dica="Filtrar (ativo, ISIN, tipo...)")}'
            f'{_tabela(a, colunas, tid, attrs=[("ativo", "codigo"), ("grupo", "grupo")], rodape=total)}')


def _aba_lotes(f):
    lt = f["lotes"]
    if lt.empty:
        return '<p class="aviso">Nenhum lote em aberto na data.</p>'
    tid = f"tbl-{f['slug']}-lotes"
    divergentes = set(f["avisos"].loc[f["avisos"]["aviso"] == "Boleta × VCRA", "lote"]) if len(f["avisos"]) else set()
    cont = lt["fonte_rot"].value_counts()
    dicas = {"boleta": "taxa negociada na boleta", "VCRA": "sem boleta válida (ou --fonte vcra): pelo PU pago",
             "manual": "taxa da aba Correções", "sem taxa": "%CDI sem boleta válida: fora da média do ativo"}
    cores = {"boleta": ITAU_GREEN, "VCRA": COR_GRUPO["CDI+"], "manual": ITAU_ORANGE, "sem taxa": ITAU_RED}
    cartoes = [_kpi("Lotes em aberto", _br(len(lt), 0), f"em {_plural(lt['codigo'].nunique(), 'ativo')}")]
    for fonte, dica in dicas.items():
        if cont.get(fonte):
            cartoes.append(_kpi(f"Taxa: {fonte}", _br(cont[fonte], 0), dica, cores[fonte],
                                extra=f' data-filtra="{tid}" data-campo="fonte" data-valor="{fonte}" role="button" '
                                      f'tabindex="0" title="Filtrar a tabela"'))
    html = f'<div class="kpis">{"".join(cartoes)}</div>'

    paineis = []
    for grupo, unidade in (("CDI+", "spread, % a.a."), ("%CDI", "% do CDI")):
        g = lt[(lt["grupo"] == grupo) & (lt["boleta_ok"].isin([True, "sim"])) & lt["taxa_boleta"].notna()
               & lt["taxa_vcra_conv"].notna()]
        pontos = [{"x": r.taxa_vcra_conv, "y": r.taxa_boleta, "cor": COR_GRUPO[grupo], "destaque": r.CD in divergentes,
                   "rotulo": r.CD, "ativo": r.codigo,
                   "tip": f"{r.codigo} · lote {r.CD}\nBoleta: {_taxa(grupo, r.taxa_boleta, 4)}\nVCRA: "
                          f"{_taxa(grupo, r.taxa_vcra_conv, 4)}\nBoleta − VCRA: {_br(r.dif_boleta_vcra, 4)}\n"
                          f"PU de compra: {_br(r.pu_compra, 6)}\nTaxa usada: {_taxa(grupo, r.taxa, 4)} ({r.fonte_rot})"}
                  for r in g.itertuples()]
        if pontos:
            n_div = sum(p["destaque"] for p in pontos)
            paineis.append(_secao(f"{grupo}: boleta × VCRA ({unidade})",
                                  _dispersao(pontos, f"Taxa da VCRA ({unidade})", f"Taxa da boleta ({unidade})"),
                                  f"{_plural(len(pontos), 'lote')} com boleta válida"
                                  f"{f'; <b>{n_div}</b> com o aviso Boleta × VCRA (em vermelho)' if n_div else ''}."))
    if paineis:
        html += f'<div class="grid2">{"".join(paineis)}</div>'
        html += ('<p class="explica">Cada ponto é um lote com boleta válida: no eixo X, a taxa da VCRA (pelo PU pago, na '
                 'convenção do grupo); no Y, a da boleta. Na diagonal as duas são iguais. Ponto longe da diagonal é '
                 'boleta que repete a taxa de emissão, PU fora do mercado ou erro de digitação: confira na ficha.</p>')

    colunas = [("codigo", "Ativo", "ativo", "Clique para abrir a ficha do ativo"),
               ("CD", "Lote", "texto", "CD da VCRAOPRF (sufixo A = relançamento)"),
               ("grupo", "Grupo", "grupo", "CDI+ ou %CDI"), ("dt_compra", "Compra", "data", "Data da compra do lote"),
               ("qt_comprada", "Qtd comprada", "int", "Soma das compras do lote"),
               ("qt_vendida", "Qtd vendida", "int", "Soma das vendas do lote"),
               ("qt_aberta", "Qtd em aberto", "int", "Comprada − vendida"),
               ("pu_compra", "PU de compra", "pu", "PU da compra (média ponderada)"),
               ("data_boleta", "Boleta", "data", "Data da boleta casada"),
               ("casou_por", "Casou por", "texto", "A boleta casou pela quantidade ou pelo PU"),
               ("taxa_boleta", "Taxa da boleta", "conv4", "exec_taxa da FUNDOS_OPERACOES"),
               ("boleta_ok", "Boleta válida", "simnao", "Na convenção do grupo (veja METODOLOGIA)"),
               ("taxa_vcra_conv", "Taxa VCRA", "conv4", "Taxa da VCRA (pelo PU pago) na convenção do grupo"),
               ("dif_boleta_vcra", "Boleta − VCRA", "dif", "Diferença na convenção do grupo"),
               ("taxa", "Taxa usada", "conv4", "A taxa que entra na média"),
               ("fonte_rot", "Fonte", "fonte", "De onde veio a taxa usada")]
    ordem = lt.sort_values(["grupo", "codigo", "dt_compra"])
    selects = [("grupo", "Grupo", [g for g in COR_GRUPO if g in set(lt["grupo"])]),
               ("fonte", "Fonte", [x for x in dicas if cont.get(x)]), ("valida", "Boleta válida", ["sim", "não"])]
    ordem = ordem.assign(valida=ordem["boleta_ok"].map(lambda v: "sim" if v in (True, "sim") else "não"))
    tabela = _tabela(ordem, colunas, tid, alta=True,
                     attrs=[("ativo", "codigo"), ("grupo", "grupo"), ("fonte", "fonte_rot"), ("valida", "valida")])
    return (html + f'<h2 class="aba-title">Lotes em aberto</h2>{_filtros(tid, selects, dica="Filtrar (ativo, lote...)")}'
            f'{tabela}')


def _sem_trades(f):
    """Aviso de nenhum trade: no relatório de um dia, com o período dos trades dele."""
    janela = f.get("janela")
    if not janela:
        return '<p class="aviso">Nenhum trade no período.</p>'
    ini, fim = janela
    quando = f"em {_dt(fim)}" if ini == fim else f"de {_dt(ini)} a {_dt(fim)}"
    return f'<p class="aviso">Nenhum trade {quando}.</p>'


def _grafico_trades(f, clique, arquivo_do_dia=None):
    """Seção com a taxa média de cada dia com trade (compras e vendas e, com a série, a taxa da carteira como
    referência) e o financeiro do dia; vazio com menos de duas datas. clique: como no _grafico_serie;
    arquivo_do_dia = {dia do trade: dia do relatório que tem o trade} (index.html)."""
    dia, h = f["por_dia"], f["historico"]
    h = h[h["status"] == "OK"] if len(h) else h
    datas = sorted(set(dia["data"]) | set(h["data"] if len(h) else []))
    if len(datas) < 2:
        return ""
    por = {(r.data, r.operacao): r for r in dia.itertuples()}
    cart = dict(zip(h["data"], h["taxa_carteira"])) if len(h) else {}

    def serie(op, campo, sinal=1):
        return [None if (d, op) not in por or _vazio(getattr(por[(d, op)], campo))
                else sinal * float(getattr(por[(d, op)], campo)) for d in datas]

    taxas = [{"sid": "carteira", "nome": "Carteira (CDI+ equivalente)", "vals": [cart.get(d) for d in datas],
              "cor": COR_CARTEIRA, "tipo": "linha", "liga": True}] if cart else []
    taxas += [{"sid": op.lower(), "nome": f"{op}s (média do dia)", "vals": serie(op, "taxa_total"),
               "cor": COR_OPERACAO[op], "tipo": "pontos", "forma": "circulo" if op == "Compra" else "losango"}
              for op in ("Compra", "Venda")]
    volumes = [{"sid": f"fin-{op.lower()}", "nome": f"Financeiro de {op.lower()}s", "vals": serie(op, "financeiro", s),
                "cor": COR_OPERACAO[op], "tipo": "barras"} for op, s in (("Compra", 1), ("Venda", -1))]
    paineis = [{"titulo": "Taxa média do dia em CDI+ equivalente", "altura": 230, "fmt": _cdi_mais, "series": taxas},
               {"titulo": "Financeiro do dia (R$ mi): compras para cima, vendas para baixo", "altura": 130,
                "fmt": lambda v: _rs(abs(v)), "escala": 1e6, "series": volumes}]
    for p in paineis:
        p["series"] = [s for s in p["series"] if any(v is not None for v in s["vals"])]
    rodape = []
    for d in datas:
        partes = [f"{op}s: {_plural(por[(d, op)].n_trades, 'trade')}, {_plural(por[(d, op)].n_ativos, 'ativo')}"
                  for op in ("Compra", "Venda") if (d, op) in por]
        rodape.append(" · ".join(partes) + " — clique para ver os trades do dia" if partes else None)
    dias_clique = None
    if arquivo_do_dia is not None:
        dias_clique = [_iso(arquivo_do_dia[d]) if r and d in arquivo_do_dia else None for d, r in zip(datas, rodape)]
    cid = f"serie-{f['slug']}-trades"
    svg = _grafico_serie(cid, datas, paineis, temporal=True, rodape=rodape, clique=clique, dias_clique=dias_clique)
    grafico = _legenda(cid, paineis) + f'<div id="{cid}" class="serie-chart">{svg}</div>'
    destino = "abrir o relatório do dia" if str(clique).startswith("#dia") else "ver os trades dele na tabela de baixo"
    return _secao("Trades por dia", grafico,
                  "Cada ponto é a taxa média dos trades do dia, ponderada pelo financeiro de cada trade (os %CDI "
                  "convertidos com o CDI do dia)" + ("; a linha laranja é a taxa da carteira na data" if cart else "")
                  + f". Clique num dia para {destino}.")


_COLUNAS_POR_DIA = [("data", "Data", "data", "Clique na linha para ver os trades do dia"),
                    ("operacao", "Operação", "op", "Compra ou venda"), ("n_trades", "Trades", "int", "Trades no dia"),
                    ("n_ativos", "Ativos", "int", "Ativos negociados"),
                    ("financeiro", "Financeiro (R$)", "int", "Soma de qtd × PU dos trades"),
                    ("taxa_total", "Taxa média", "eq", "Média ponderada pelo financeiro, em CDI+ equivalente"),
                    ("taxa_pct", "%CDI: taxa", "pct", "Média dos %CDI, em % do CDI"),
                    ("fin_pct", "%CDI: financeiro (R$)", "int", "Financeiro dos %CDI com taxa"),
                    ("taxa_mais", "CDI+: spread", "eq", "Spread médio dos CDI+"),
                    ("fin_mais", "CDI+: financeiro (R$)", "int", "Financeiro dos CDI+ com taxa"),
                    ("n_sem_taxa", "Sem taxa", "int", "Trades sem taxa (fora das médias)"),
                    ("fin_sem_taxa", "Sem taxa (R$)", "int", "Financeiro dos trades sem taxa"),
                    ("cdi", "CDI (% a.a.)", "t2", "CDI do dia, para o CDI+ equivalente")]


def _aba_trades(f):
    tr, dia = f["trades"], f["por_dia"]
    if tr.empty:
        return _sem_trades(f)
    tid, tid_dia = f"tbl-{f['slug']}-trades", f"tbl-{f['slug']}-pordia"
    cartoes = []
    for op in ("Compra", "Venda"):
        n, fin, taxa = _media_trades(tr[tr["operacao"] == op])
        if n:
            cartoes.append(_kpi(f"{op}s: taxa média", _cdi_mais(taxa) or "sem taxa",
                                f"{_plural(n, op.lower())} · {_rs(fin)} · em CDI+ equivalente", COR_OPERACAO[op],
                                extra=f' data-filtra="{tid}" data-campo="op" data-valor="{op}" role="button" '
                                      f'tabindex="0" title="Filtrar a tabela de trades"'))
    dias = tr["data"]
    cartoes.append(_kpi("Dias com trade", _br(dias.nunique(), 0), f"de {_dt(dias.min())} a {_dt(dias.max())}")
                   if dias.nunique() > 1 else _kpi("Dia dos trades", _dt(dias.min()), _plural(len(tr), "trade")))
    sem = tr[tr["taxa"].isna()]
    if len(sem):
        cartoes.append(_kpi("Trades sem taxa", _br(len(sem), 0), f"{_rs(sem['financeiro'].sum())} fora das médias",
                            ITAU_RED, extra=f' data-filtra="{tid}" data-campo="fonte" data-valor="sem taxa" '
                                            f'role="button" tabindex="0" title="Filtrar a tabela de trades"'))
    html = f'<div class="kpis">{"".join(cartoes)}</div>' + _grafico_trades(f, tid)
    colunas = [("data", "Data", "data", "Data do trade"), ("operacao", "Operação", "op", "Compra ou venda"),
               ("codigo", "Ativo", "ativo", "Clique para abrir a ficha do ativo"),
               ("CD", "Lote", "texto", "CD da VCRAOPRF"),
               ("grupo", "Grupo", "grupo", "CDI+ ou %CDI"), ("qt", "Quantidade", "int", "Quantidade negociada"),
               ("pu", "PU", "pu", "PU da operação"), ("financeiro", "Financeiro (R$)", "int", "Quantidade × PU"),
               ("data_boleta", "Boleta", "data", "Data da boleta casada"),
               ("casou_por", "Casou por", "texto", "Quantidade ou PU"),
               ("taxa_boleta", "Taxa da boleta", "conv4", "exec_taxa da FUNDOS_OPERACOES"),
               ("taxa_vcra_conv", "Taxa VCRA", "conv4", "VL_JUROSOPER na convenção do grupo"),
               ("taxa", "Taxa usada", "conv4", "Pelas mesmas regras dos lotes"),
               ("fonte_rot", "Fonte", "fonte", "De onde veio a taxa usada"),
               ("taxa_cdi_mais", "CDI+ equivalente", "eq", "Taxa usada em CDI+ equivalente, com o CDI do dia")]
    ops = [o for o in ("Compra", "Venda") if o in set(tr["operacao"])]
    fontes = [x for x in ("boleta", "VCRA", "manual", "sem taxa") if x in set(tr["fonte_rot"])]
    grupos = [g for g in COR_GRUPO if g in set(tr["grupo"])]
    filtros_dia = _filtros(tid_dia, [("op", "Operação", ops)], dica="Filtrar (data...)")
    tabela_dia = _tabela(dia, _COLUNAS_POR_DIA, tid_dia, attrs=[("dia", "data"), ("op", "operacao")],
                         extra=f' data-filtra="{tid}"')
    filtros = _filtros(tid, [("op", "Operação", ops), ("grupo", "Grupo", grupos), ("fonte", "Fonte", fontes)],
                       dia=True, dica="Filtrar (ativo, lote...)")
    tabela = _tabela(tr, colunas, tid, alta=True, attrs=[("ativo", "codigo"), ("dia", "data"), ("op", "operacao"),
                                                         ("grupo", "grupo"), ("fonte", "fonte_rot")])
    return (html + f'<h2 class="aba-title">Trades por dia</h2>{filtros_dia}{tabela_dia}'
            f'<h2 class="aba-title tbl-bloco" id="{tid}-titulo">Trades (mais recentes primeiro)</h2>{filtros}{tabela}')


def _media_por_dia(g):
    """(trades, financeiro, taxa média em CDI+ equivalente) de linhas da tabela Trades por dia: a média de cada dia
    pesa o financeiro dos trades com taxa."""
    peso = (g["financeiro"] - g["fin_sem_taxa"].fillna(0)).where(g["taxa_total"].notna(), 0.0)
    taxa = (peso * g["taxa_total"].fillna(0)).sum() / peso.sum() if peso.sum() else np.nan
    return _int(g["n_trades"].sum()), g["financeiro"].sum(), taxa


def _aba_trades_periodo(f):
    """TRADES do index.html: os trades por dia de todos os relatórios diários; o detalhe de cada trade fica no
    relatório do dia, que abre no clique."""
    dia = f["por_dia"]
    if dia.empty:
        return '<p class="aviso">Nenhum trade nos relatórios diários.</p>'
    cartoes = []
    for op in ("Compra", "Venda"):
        g = dia[dia["operacao"] == op]
        if g.empty:
            continue
        n, fin, taxa = _media_por_dia(g)
        cartoes.append(_kpi(f"{op}s: taxa média", _cdi_mais(taxa) or "sem taxa",
                            f"{_plural(n, op.lower())} · {_rs(fin)} · em CDI+ equivalente", COR_OPERACAO[op]))
    datas = dia["data"]
    cartoes.append(_kpi("Dias com trade", _br(datas.nunique(), 0), f"de {_dt(datas.min())} a {_dt(datas.max())}"))
    n_sem = _int(dia["n_sem_taxa"].fillna(0).sum())
    if n_sem:
        cartoes.append(_kpi("Trades sem taxa", _br(n_sem, 0), f"{_rs(dia['fin_sem_taxa'].sum())} fora das médias",
                            ITAU_RED))
    html = (f'<div class="kpis">{"".join(cartoes)}</div>'
            + _grafico_trades(f, "#dia:trades", dict(zip(dia["data"], dia["arquivo"]))))
    tid = f"tbl-{f['slug']}-pordia"
    ops = [o for o in ("Compra", "Venda") if o in set(dia["operacao"])]
    tabela = _tabela(dia, _COLUNAS_POR_DIA, tid, alta=True, attrs=[("dia", "arquivo"), ("op", "operacao")],
                     extra=' data-abre-dia="trades"')
    return (html + '<h2 class="aba-title">Trades por dia (mais recentes primeiro)</h2>'
            f'{_filtros(tid, [("op", "Operação", ops)], dica="Filtrar (data...)")}{tabela}')


def _aba_avisos(f):
    av = f["avisos"]
    if av.empty:
        return '<p class="aviso">Nenhum aviso na data.</p>'
    tid = f"tbl-{f['slug']}-avisos"
    cartoes = "".join(
        f'<div class="card-filtro{" info" if tipo == "Correção manual" else ""}" data-filtra="{tid}" data-campo="aviso" '
        f'data-valor="{_esc(tipo)}" role="button" tabindex="0"><div class="card-n">{n}</div><div><b>{_esc(tipo)}</b>'
        f'<p>{_esc(SIGNIFICADO_AVISOS.get(tipo, ""))}</p></div></div>'
        for tipo, n in av["aviso"].value_counts(sort=False).items())
    colunas = [("aviso", "Aviso", "aviso", "Tipo do aviso"), ("ativo", "Ativo", "ativo", "Clique para abrir a ficha"),
               ("lote", "Lote", "texto", "CD do lote, quando o aviso é de um lote"),
               ("detalhe", "Detalhe", "longo", "O que foi encontrado e o que o cálculo fez")]
    tipos = list(dict.fromkeys(av["aviso"]))
    return (f'<p class="explica">Clique num tipo para filtrar a tabela (de novo para voltar a todos).</p>'
            f'<div class="cards">{cartoes}</div>'
            f'{_filtros(tid, [("aviso", "Aviso", tipos)], dica="Filtrar (ativo, lote, detalhe...)")}'
            f'{_tabela(av, colunas, tid, attrs=[("ativo", "ativo"), ("aviso", "aviso")])}')


# ── Abas gerais ──────────────────────────────────────────────────────────────
GLOSSARIO = [
    ("CDI+ (spread)", "taxa acima de 100% do CDI, em % a.a. Ex.: CDI+2,46."),
    ("%CDI", "percentual do CDI. Ex.: 105,51% do CDI. O grupo do ativo vem da VCRA: CDI+ se tem spread de emissão, "
             "senão %CDI."),
    ("CDI+ equivalente", "o %CDI convertido no spread que rende o mesmo em um ano, com o CDI flat: (1 + %CDI × CDI "
                         "diário)^252 / (1 + CDI) − 1. É o que permite juntar os dois grupos numa taxa só."),
    ("Lote", "cada compra na custódia (CD da VCRAOPRF). Quantidade em aberto = compras − vendas do lote. Lote com "
             "sufixo A é relançamento da VCRA."),
    ("Taxa usada", "%CDI: a da boleta. CDI+: a da boleta ou a da VCRA (veja Taxa dos CDI+ nos parâmetros); sem boleta "
                   "válida, a da VCRA. A aba Correções do Excel de entrada vale por cima de tudo."),
    ("Boleta válida", "boleta casada com a taxa na convenção do grupo (limites nos parâmetros)."),
    ("Taxa VCRA", "a taxa da custódia pelo PU pago (VL_JUROSOPER), na convenção do grupo, para comparar com a boleta."),
    ("Taxa média do ativo", "média das taxas usadas nos lotes em aberto, ponderada pela quantidade."),
    ("Taxa da carteira", "média dos ativos ponderada pelo financeiro (quantidade × último PU), por grupo e no total "
                         "em CDI+ equivalente."),
    ("Peso e contribuição", "peso = financeiro do ativo ÷ financeiro na média; contribuição = peso × taxa em CDI+ "
                            "equivalente. A soma das contribuições é a taxa da carteira."),
    ("Trades", "compras e vendas da VCRA, com a taxa pelas regras dos lotes; relançamento (lote X → XA) não é "
               "trade. A média do dia é ponderada pelo financeiro de cada trade."),
]

NAVEGACAO = [
    "As abas de cima trocam a visão; com mais de um fundo, o seletor à direita troca o fundo em todas elas.",
    "Clique no título de uma coluna para ordenar; a caixa de busca e os seletores acima de cada tabela filtram as "
    "linhas.",
    "Clique num ativo (tabela ou gráfico) para abrir a ficha dele: lotes em aberto, trades e avisos.",
    "Nos gráficos, passe o mouse para ver os valores; as caixas da legenda mostram ou escondem as linhas.",
    "Na aba TRADES, clique num dia (gráfico ou tabela Trades por dia) para filtrar os trades dele.",
    "Os cartões com contagem (fonte da taxa, tipos de aviso) também filtram a tabela da aba.",
]


def _aba_metodologia(param, notas):
    gl = "".join(f"<dt>{_esc(t)}</dt><dd>{_esc(d)}</dd>" for t, d in GLOSSARIO)
    nav = "".join(f"<li>{_esc(x)}</li>" for x in NAVEGACAO)
    html = _secao("Como navegar", f'<ul class="lista">{nav}</ul>') + _secao("Como ler", f'<dl class="glossario">{gl}</dl>')
    if len(param):
        colunas = [("parametro", "Parâmetro", "texto", "Parâmetro da execução"),
                   ("valor", "Valor", "longo", "Valor usado")]
        html += f'<h2 class="aba-title">Parâmetros da execução</h2>{_tabela(param, colunas)}'
    if notas:
        itens = "".join(f"<li>{_esc(n)}</li>" for n in notas)
        html += f'<h2 class="aba-title">Notas</h2><ul class="lista notas">{itens}</ul>'
    return html


def _aba_fundos(fundos):
    ok = fundos[fundos["taxa_carteira"].notna()].sort_values("taxa_carteira", ascending=False) \
        if "taxa_carteira" in fundos.columns else fundos.iloc[0:0]
    linhas = []
    for r in ok.to_dict("records"):
        nome = "" if _vazio(r.get("nome")) else f" · {r['nome']}"
        linhas.append({"rotulo": r["fundo"], "valor": r["taxa_carteira"], "texto": _cdi_mais(r["taxa_carteira"]),
                       "cor": COR_CARTEIRA, "fundo": r["fundo"],
                       "tip": f"{r['fundo']}{nome}\nCarteira: {_cdi_mais(r['taxa_carteira'])} em {_dt(r.get('data'))}\n"
                              f"Financeiro: {_rs(r.get('financeiro'))}\nClique para abrir o fundo"})
    html = _secao("Taxa média da carteira de cada fundo (CDI+ equivalente)", _barras_h(linhas, "Carteira em CDI+ "
                  "equivalente"), "Clique num fundo para abrir o resumo dele.") if linhas else ""
    colunas = [("fundo", "Fundo", "fundo", "Clique para abrir o fundo"), ("nome", "Nome", "texto", "Nome na aba Fundos"),
               ("data", "Data", "data", "Data de referência do fundo"), ("status", "Status", "status", "OK ou o erro"),
               ("taxa_carteira", "Carteira", "eq", "Taxa da carteira em CDI+ equivalente"),
               ("financeiro", "Financeiro (R$)", "int", "Financeiro na média"),
               ("n_ativos", "Ativos", "int", "Ativos com lote em aberto"), ("n_lotes", "Lotes", "int", "Lotes em aberto"),
               ("n_avisos", "Avisos", "int", "Avisos na data"), ("cdi", "CDI (% a.a.)", "t2", "CDI da conversão"),
               ("cdi_origem", "Origem do CDI", "longo", "De onde veio o CDI")]
    return html + f'<h2 class="aba-title">Fundos</h2>{_tabela(fundos, [c for c in colunas if c[0] in fundos.columns])}'


def _fichas(f):
    """Dados da ficha de cada ativo (cabeçalho e cartões); as tabelas da ficha são as linhas das abas LOTES, TRADES e
    AVISOS do ativo, copiadas no JS."""
    ativos = {}
    for r in f["ativos"].to_dict("records"):
        g = None if _vazio(r.get("grupo")) else r["grupo"]
        emissao = f"emissão {_taxa(g, r.get('emissao'))}" if not _vazio(r.get("emissao")) else ""
        sub = " · ".join(str(x) for x in (r.get("isin"), r.get("tipo"), g, emissao) if x and not _vazio(x))
        pu, peso = r.get("pu"), r.get("peso")
        ativos[r["codigo"]] = {"sub": sub, "kpis": [
            ["Taxa média", _taxa(g, r.get("taxa_media")) or "sem taxa", "lotes ponderados pela quantidade"],
            ["CDI+ equivalente", _cdi_mais(r.get("taxa_cdi_mais")) or "—",
             "com o CDI da data" if g == "%CDI" else "a própria taxa"],
            ["Financeiro", _rs(r.get("financeiro")),
             f"PU {_br(pu, 6)} em {_dt(r.get('dt_pu'))}" if not _vazio(pu) else "sem PU na posição"],
            ["Peso na média", f"{_br(peso, 2)}%" if not _vazio(peso) else "fora da média",
             f"contribuição {_br(r.get('contrib'), 4)} p.p." if not _vazio(peso) else ""],
            ["Lotes em aberto", _br(_int(r.get("n_lotes")), 0),
             f"{_br(_int(r.get('qt_lotes')), 0)} na VCRA × {_br(_int(r.get('qt_posicao')), 0)} na posição"],
            ["Taxa VCRA", _taxa(g, r.get("taxa_vcra")) or "—", "média pelo PU pago, na convenção do grupo"]]}
    return {"slug": f["slug"], "data": _dt(f["data"]), "ativos": ativos}


# ── CSS / JS ─────────────────────────────────────────────────────────────────
def _css():
    return f"""
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f0f3fa; color: #1a1a2e; }}
    body.modal-aberto {{ overflow: hidden; }}
    [hidden] {{ display: none !important; }}

    .hdr {{ background: {ITAU_DARK}; padding: 24px 40px 0; }}
    .hdr::after {{ content: ''; display: block; height: 4px; background: {ITAU_ORANGE}; margin-top: 20px; }}
    .hdr-inner {{ display: flex; align-items: center; justify-content: space-between; gap: 24px; }}
    .hdr h1 {{ color: #fff; font-size: 1.7rem; font-weight: 700; letter-spacing: .06em; }}
    .hdr .sub {{ color: {ITAU_GRAY2}; font-size: .88rem; margin-top: 5px; line-height: 1.6; }}
    .hdr .sub strong {{ color: #fff; }}
    .brand {{ display: flex; align-items: center; gap: 12px; }}
    .brand span {{ color: {ITAU_GRAY2}; font-size: 2.1rem; font-weight: 700; letter-spacing: .04em; white-space: nowrap; }}
    .logo-img {{ height: 52px; width: auto; object-fit: contain; }}

    .nav-wrapper {{ position: sticky; top: 0; z-index: 100; box-shadow: 0 3px 10px rgba(0,0,0,.09); }}
    .perf-nav {{ background: #fff; display: flex; gap: 6px; flex-wrap: wrap; align-items: center;
                 padding: 12px 40px; border-bottom: 2px solid {ITAU_GRAY}; }}
    .perf-tab-btn {{ padding: 8px 22px; border: 2px solid {ITAU_ORANGE}; border-radius: 20px;
                     background: #fff; color: {ITAU_ORANGE}; font-weight: 700; font-size: .84rem;
                     cursor: pointer; transition: all .17s; white-space: nowrap; letter-spacing: .04em; }}
    .perf-tab-btn:hover {{ background: {ITAU_ORANGE}18; }}
    .perf-tab-btn.active {{ background: {ITAU_ORANGE}; color: #fff; box-shadow: 0 2px 10px {ITAU_ORANGE}55; }}
    .nav-fundo {{ margin-left: auto; display: flex; align-items: center; gap: 8px; font-size: .82rem;
                  font-weight: 600; color: {ITAU_DARK}; }}
    .perf-pane {{ display: none; animation: fadeIn .2s; }}
    .perf-pane.active {{ display: block; }}
    @keyframes fadeIn {{ from {{ opacity:0; transform:translateY(4px); }} to {{ opacity:1; transform:none; }} }}

    .content {{ padding: 28px 40px 50px; }}
    .aba-title {{ font-size: 1rem; font-weight: 700; color: {ITAU_ORANGE}; margin: 26px 0 14px;
                  text-transform: uppercase; letter-spacing: .08em; scroll-margin-top: 90px; }}
    .explica {{ font-size: .8rem; color: #5a6275; margin: 0 0 12px; line-height: 1.55; }}
    .grid2 + .explica {{ margin-top: 12px; }}

    .tbl-wrap {{ overflow-x: auto; border-radius: 10px; box-shadow: 0 2px 16px rgba(0,0,0,.10); }}
    .tbl-wrap.alta {{ max-height: 70vh; overflow: auto; }}
    .exp-table {{ border-collapse: collapse; width: 100%; font-size: .83rem; background: #fff; min-width: 500px; }}
    .exp-table thead tr {{ background: {ITAU_DARK}; }}
    .exp-table th {{ color: #fff; background: {ITAU_DARK}; font-weight: 600; padding: 11px 14px; white-space: nowrap;
                     text-align: center; cursor: pointer; user-select: none; z-index: 2;
                     border-right: 1px solid #ffffff1a; position: sticky; top: 0; }}
    .exp-table th:hover {{ background: #112070; }}
    .exp-table th.asc::after  {{ content: ' ▲'; font-size: .6em; opacity: .8; }}
    .exp-table th.desc::after {{ content: ' ▼'; font-size: .6em; opacity: .8; }}
    .exp-table td {{ padding: 8px 14px; text-align: center; border-bottom: 1px solid {ITAU_GRAY};
                     border-right: 1px solid {ITAU_GRAY}; white-space: nowrap; }}
    .exp-table td.num {{ font-variant-numeric: tabular-nums; }}
    .exp-table td:first-child {{ text-align: left; font-weight: 600; }}
    .exp-table td.txt {{ text-align: left; white-space: normal; min-width: 260px; }}
    /* 1ª coluna fixa na rolagem horizontal das tabelas largas */
    .exp-table tbody tr {{ background: #fff; }}
    .exp-table td:first-child {{ position: sticky; left: 0; z-index: 1; background: inherit; }}
    .exp-table th:first-child {{ left: 0; z-index: 3; }}
    .exp-table td:last-child, .exp-table th:last-child {{ border-right: none; }}
    .exp-table tbody tr:nth-child(even) {{ background: {ROW_PAR}; }}
    .exp-table tbody tr:hover {{ background: #d6e4ff !important; transition: background .12s; }}
    .exp-table tfoot td, .exp-table tfoot td:first-child {{ background: #D9E1F2; font-weight: 700;
                                                             border-top: 2px solid {ITAU_DARK}; }}
    table[data-filtra] tbody tr {{ cursor: pointer; }}

    .pnl-chart-box {{ background: #fff; border-radius: 10px; padding: 16px 20px;
                      box-shadow: 0 2px 12px rgba(0,0,0,.08); overflow: hidden; margin-bottom: 20px; }}
    .pnl-chart-title {{ font-size: .82rem; font-weight: 700; color: {ITAU_DARK};
                        text-transform: uppercase; letter-spacing: .05em; margin-bottom: 10px; }}
    .grid2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(440px, 1fr)); gap: 20px; }}
    .grid2 .pnl-chart-box {{ margin-bottom: 0; }}
    .mes-select {{ padding: 6px 14px; border: 1.5px solid {ITAU_GRAY}; border-radius: 8px;
                   font-size: .84rem; font-family: inherit; outline: none; cursor: pointer; }}
    .mes-select:focus {{ border-color: {ITAU_ORANGE}; }}

    .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 20px; }}
    .kpi {{ background: #fff; border-radius: 10px; padding: 14px 18px; box-shadow: 0 2px 12px rgba(0,0,0,.08);
            border-top: 4px solid {ITAU_DARK}; }}
    .kpi-rot {{ font-size: .72rem; font-weight: 700; color: {_TINTA_FRACA}; text-transform: uppercase; letter-spacing: .06em; }}
    .kpi-val {{ font-size: 1.6rem; font-weight: 700; color: {ITAU_DARK}; margin-top: 6px; }}
    .kpi-sub {{ font-size: .78rem; color: {_TINTA_FRACA}; margin-top: 4px; line-height: 1.4; }}
    .kpi[data-ir], .kpi[data-filtra] {{ cursor: pointer; transition: box-shadow .15s, transform .15s; }}
    .kpi[data-ir]:hover, .kpi[data-filtra]:hover {{ box-shadow: 0 4px 18px rgba(0,0,0,.16); transform: translateY(-1px); }}
    .kpi.ativo, .card-filtro.ativo {{ outline: 2px solid {ITAU_ORANGE}; }}
    .spark {{ display: block; margin-top: 6px; }}

    .tag {{ display: inline-flex; align-items: center; gap: 6px; padding: 2px 9px; border-radius: 10px;
            font-size: .74rem; font-weight: 600; white-space: nowrap; }}
    .tag i {{ display: inline-block; width: 9px; height: 9px; border-radius: 50%; flex: none; }}
    .t-serie {{ background: #f1f3f8; color: {_TINTA}; }}
    .t-total {{ background: {ITAU_DARK}; color: #fff; }}
    .t-boleta, .t-ok {{ background: #e3f3e8; color: #1e5e34; }}
    .t-vcra {{ background: #e5eefb; color: #1d4f91; }}
    .t-manual, .t-aviso {{ background: #fff0e0; color: #8a4200; }}
    .t-sem, .t-erro {{ background: #fdeceb; color: #a42a1e; }}
    .t-info {{ background: #eef1f6; color: #4a5468; }}

    .toolbar {{ display: flex; flex-wrap: wrap; align-items: center; gap: 10px 16px; margin-bottom: 10px; }}
    .filtro-busca {{ padding: 7px 12px; border: 1.5px solid {ITAU_GRAY}; border-radius: 8px; font: inherit;
                     font-size: .84rem; min-width: 260px; outline: none; background: #fff; }}
    .filtro-busca:focus, .filtro-sel:focus {{ border-color: {ITAU_ORANGE}; }}
    .filtro-rot {{ font-size: .8rem; font-weight: 600; color: {ITAU_DARK}; display: inline-flex; align-items: center; gap: 6px; }}
    .filtro-sel {{ padding: 6px 10px; border: 1.5px solid {ITAU_GRAY}; border-radius: 8px; font: inherit;
                   font-size: .82rem; cursor: pointer; background: #fff; outline: none; }}
    .filtro-cont {{ margin-left: auto; color: {_TINTA_FRACA}; font-size: .8rem; }}
    .chip-dia {{ border: 1.5px solid {ITAU_ORANGE}; background: #fff4e8; color: {ITAU_DARK}; border-radius: 16px;
                 padding: 4px 12px; font: inherit; font-size: .8rem; cursor: pointer; }}

    .cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; margin-bottom: 18px; }}
    .card-filtro {{ display: flex; gap: 14px; align-items: flex-start; background: #fff; border-radius: 10px;
                    padding: 12px 16px; box-shadow: 0 2px 10px rgba(0,0,0,.07); border-left: 4px solid {ITAU_ORANGE};
                    cursor: pointer; }}
    .card-filtro.info {{ border-left-color: {_BASE}; }}
    .card-filtro:hover {{ box-shadow: 0 4px 16px rgba(0,0,0,.14); }}
    .card-n {{ font-size: 1.5rem; font-weight: 700; color: {ITAU_DARK}; min-width: 30px; }}
    .card-filtro b {{ color: {ITAU_DARK}; font-size: .88rem; }}
    .card-filtro p {{ color: #5a6275; font-size: .78rem; margin-top: 3px; line-height: 1.4; }}

    .comp-barra {{ display: flex; gap: 2px; height: 32px; border-radius: 6px; overflow: hidden; }}
    .comp-seg {{ display: flex; align-items: center; justify-content: center; color: #fff; font-size: .8rem;
                 font-weight: 700; white-space: nowrap; min-width: 2px; cursor: default; }}
    .comp-leg {{ margin: 10px 0 0; }}

    .svg-bar {{ cursor: pointer; transition: opacity .12s, filter .12s; }}
    .svg-bar:hover {{ opacity: 1 !important; filter: brightness(1.14) drop-shadow(0 2px 6px rgba(0,0,0,.22)); }}
    .svg-linha, .svg-ponto {{ fill: transparent; cursor: pointer; }}
    .svg-linha:hover {{ fill: {ITAU_DARK}; fill-opacity: .05; }}
    .svg-ponto:hover {{ fill: {ITAU_DARK}; fill-opacity: .10; }}
    .serie-overlay.clicavel {{ cursor: pointer; }}
    #svg-chart-tip {{ position: fixed; background: #1a1a2e; color: #fff; padding: 7px 14px;
                      border-radius: 8px; font-size: .78rem; pointer-events: none; display: none;
                      z-index: 9999; box-shadow: 0 3px 14px rgba(0,0,0,.38); white-space: nowrap;
                      line-height: 1.5; border-left: 3px solid {ITAU_ORANGE}; }}
    #svg-chart-tip .tt-head {{ font-weight: 700; margin-bottom: 3px; }}
    #svg-chart-tip .tt-row {{ display: flex; align-items: center; gap: 8px; }}
    #svg-chart-tip .tt-key {{ width: 14px; height: 3px; border-radius: 2px; flex: none; }}
    #svg-chart-tip .tt-row strong {{ min-width: 62px; text-align: right; font-variant-numeric: tabular-nums; }}
    #svg-chart-tip .tt-name {{ color: #c3c8d6; }}
    #svg-chart-tip .tt-foot {{ color: #c3c8d6; margin-top: 4px; font-size: .74rem; }}

    .hist-legenda {{ display: flex; flex-wrap: wrap; align-items: center; gap: 6px 22px;
                     margin-bottom: 10px; font-size: .8rem; color: {ITAU_DARK}; }}
    .hist-leg {{ display: inline-flex; align-items: center; gap: 7px; }}
    .hist-leg-toggle {{ cursor: pointer; user-select: none; }}
    .hist-leg-toggle input {{ margin: 0; cursor: pointer; accent-color: {ITAU_DARK}; }}
    .hist-leg-toggle:has(input:not(:checked)) {{ opacity: .45; }}
    .hist-key {{ display: inline-block; width: 18px; height: 3px; border-radius: 2px; }}
    .hist-key-ponto {{ display: inline-block; width: 9px; height: 9px; }}
    .hist-key-barra {{ display: inline-block; width: 11px; height: 11px; border-radius: 2px; }}
    .hist-nota {{ margin-left: auto; color: #7a8194; }}

    .lk-ativo, .lk-fundo {{ color: {ITAU_DARK}; text-decoration: underline dotted {ITAU_GRAY2};
                            text-underline-offset: 3px; cursor: pointer; font-weight: 600; }}
    .lk-ativo:hover, .lk-fundo:hover {{ color: {ITAU_ORANGE}; }}

    .ficha-fundo {{ position: fixed; inset: 0; background: rgba(0,13,60,.45); display: none; z-index: 200;
                    justify-content: center; align-items: flex-start; padding: 40px 20px; overflow-y: auto; }}
    .ficha-fundo.aberta {{ display: flex; }}
    .ficha {{ background: #f0f3fa; border-radius: 12px; width: min(1200px, 100%); padding: 24px 28px 30px;
              position: relative; box-shadow: 0 12px 40px rgba(0,0,0,.35); border-top: 4px solid {ITAU_ORANGE}; }}
    .ficha h2 {{ color: {ITAU_DARK}; font-size: 1.35rem; padding-right: 40px; }}
    .ficha-sub {{ color: #5a6275; font-size: .86rem; margin: 4px 0 16px; }}
    .ficha-fechar {{ position: absolute; top: 12px; right: 14px; border: none; background: none; font-size: 1.3rem;
                     line-height: 1; cursor: pointer; color: {ITAU_DARK}; padding: 6px 10px; border-radius: 6px; }}
    .ficha-fechar:hover {{ background: #e3e8f3; }}
    .ficha .kpis {{ grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); }}
    .ficha .kpi-val {{ font-size: 1.2rem; }}
    .ficha-nome {{ font-size: 1rem; font-weight: 600; color: #3a4052; margin-top: 2px; }}
    .ficha-desc {{ background: #fff; border-left: 4px solid {ITAU_ORANGE}; border-radius: 6px; padding: 10px 14px;
                   font-size: .84rem; color: #3a4052; line-height: 1.55; margin: 0 0 16px; max-width: 980px; }}
    .cad-grade {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(270px, 1fr)); gap: 14px; }}
    .cad-secao {{ background: #fff; border-radius: 10px; padding: 12px 16px; box-shadow: 0 2px 10px rgba(0,0,0,.07); }}
    .cad-secao h4 {{ font-size: .72rem; font-weight: 700; color: {_TINTA_FRACA}; text-transform: uppercase;
                     letter-spacing: .06em; margin-bottom: 8px; }}
    .cad-secao dl {{ display: grid; grid-template-columns: auto 1fr; gap: 5px 14px; font-size: .82rem; }}
    .cad-secao dt {{ color: {_TINTA_FRACA}; }}
    .cad-secao dd {{ color: {_TINTA}; font-weight: 600; text-align: right; overflow-wrap: anywhere; }}
    .cad-mudancas {{ margin-top: 12px; font-size: .8rem; color: #3a4052; }}
    .cad-mudancas ul {{ margin: 4px 0 0 18px; line-height: 1.6; }}
    .cad-todos {{ margin-top: 12px; }}
    .cad-todos summary {{ cursor: pointer; font-size: .82rem; font-weight: 700; color: {ITAU_DARK}; margin-bottom: 8px; }}

    .glossario dt {{ font-weight: 700; color: {ITAU_DARK}; font-size: .88rem; margin-top: 10px; }}
    .glossario dd {{ color: #3a4052; font-size: .85rem; line-height: 1.55; }}
    .lista {{ padding-left: 20px; }}
    .lista li {{ font-size: .85rem; color: #3a4052; line-height: 1.6; margin: 3px 0; }}
    .notas {{ background: #fff; border-radius: 10px; padding: 14px 18px 14px 36px; box-shadow: 0 2px 12px rgba(0,0,0,.08); }}

    .footer {{ background: #fff; border-top: 3px solid {ITAU_DARK}; padding: 16px 40px;
               font-size: .78rem; color: {ITAU_GRAY2}; font-style: italic; text-align: center; line-height: 1.6; }}
    .aviso {{ color: #888; font-style: italic; padding: 20px 0; }}

    /* relatório do dia: link para o calendário; dentro do index.html (iframe), sem cabeçalho nem rodapé */
    .nav-direita {{ margin-left: auto; display: flex; align-items: center; gap: 14px; }}
    .nav-cal {{ color: {ITAU_DARK}; font-weight: 700; font-size: .8rem; text-decoration: none; letter-spacing: .04em;
                border: 2px solid {ITAU_DARK}; border-radius: 20px; padding: 6px 16px; white-space: nowrap; }}
    .nav-cal:hover {{ background: {ITAU_DARK}; color: #fff; }}
    /* o fundo é escolhido no índice, que avisa o relatório */
    body.embutido .hdr, body.embutido .footer, body.embutido .nav-direita {{ display: none; }}
    body.embutido .perf-nav {{ padding: 10px 24px; }}
    body.embutido .content {{ padding: 20px 24px 40px; }}
    table[data-abre-dia] tbody tr {{ cursor: pointer; }}

    /* index.html: calendário dos dias e o relatório do dia ao lado */
    .cal-layout {{ display: grid; grid-template-columns: 330px minmax(0, 1fr); gap: 20px;
                   height: calc(100vh - 96px); min-height: 560px; }}
    .cal-lateral {{ display: flex; flex-direction: column; gap: 14px; overflow-y: auto; padding: 2px 4px 2px 2px; }}
    .cal-box {{ background: #fff; border-radius: 10px; padding: 14px 16px; box-shadow: 0 2px 12px rgba(0,0,0,.08); }}
    .cal-topo {{ display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }}
    .cal-topo select {{ flex: 1; text-align: center; font-weight: 700; color: {ITAU_DARK}; }}
    .cal-nav {{ border: 1.5px solid {ITAU_GRAY}; background: #fff; border-radius: 8px; width: 34px; height: 34px;
                font-size: 1.15rem; line-height: 1; cursor: pointer; color: {ITAU_DARK}; flex: none; }}
    .cal-nav:hover:not(:disabled) {{ border-color: {ITAU_ORANGE}; color: {ITAU_ORANGE}; }}
    .cal-nav:disabled {{ opacity: .35; cursor: default; }}
    .cal-grade {{ display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }}
    .cal-sem {{ font-size: .66rem; font-weight: 700; color: {_TINTA_FRACA}; text-align: center;
                text-transform: uppercase; letter-spacing: .04em; padding-bottom: 4px; }}
    .cal-dia {{ position: relative; height: 46px; border: 1px solid #e3e7f0; background: #fff; border-radius: 7px;
                display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 1px;
                font: inherit; color: {ITAU_DARK}; cursor: pointer; padding: 0; }}
    .cal-dia:hover:not(:disabled) {{ border-color: {ITAU_ORANGE}; background: #fff4e8; }}
    .cal-dia:disabled {{ background: transparent; border-color: transparent; color: #c3c8d6; cursor: default; }}
    .cal-dia.sel {{ background: {ITAU_ORANGE}; border-color: {ITAU_ORANGE}; color: #fff; }}
    .cal-num {{ font-size: .82rem; font-weight: 700; }}
    .cal-tx {{ font-size: .64rem; color: {_TINTA_FRACA}; font-variant-numeric: tabular-nums; }}
    .cal-dia.sel .cal-tx {{ color: #fff; }}
    .cal-trade {{ position: absolute; top: 5px; right: 5px; width: 6px; height: 6px; border-radius: 50%;
                  background: {COR_OPERACAO["Compra"]}; }}
    .cal-dia.sel .cal-trade {{ background: #fff; }}
    .cal-legenda {{ font-size: .72rem; color: {_TINTA_FRACA}; margin-top: 12px; line-height: 1.55; }}
    .cal-legenda i {{ display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin-right: 5px;
                      background: {COR_OPERACAO["Compra"]}; vertical-align: middle; }}
    .cal-titulo {{ font-size: .95rem; font-weight: 700; color: {ITAU_DARK}; }}
    .cal-fundo {{ font-size: .76rem; color: {_TINTA_FRACA}; margin: 2px 0 10px; }}
    .cal-resumo {{ display: grid; grid-template-columns: auto 1fr; gap: 5px 12px; font-size: .8rem; }}
    .cal-resumo dt {{ color: {_TINTA_FRACA}; }}
    .cal-resumo dd {{ color: {_TINTA}; font-weight: 600; text-align: right; }}
    .cal-acoes {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }}
    .cal-abrir {{ display: block; margin-top: 12px; font-size: .78rem; font-weight: 700; color: {ITAU_ORANGE};
                  text-decoration: none; }}
    .cal-abrir:hover {{ text-decoration: underline; }}
    .cal-acoes button, .cal-acoes a {{ flex: 1; padding: 7px 10px; border: 2px solid {ITAU_ORANGE}; border-radius: 18px;
                                       background: #fff; color: {ITAU_ORANGE}; font: inherit; font-size: .78rem;
                                       font-weight: 700; cursor: pointer; text-align: center; text-decoration: none;
                                       white-space: nowrap; }}
    .cal-acoes button:hover:not(:disabled), .cal-acoes a:hover {{ background: {ITAU_ORANGE}; color: #fff; }}
    .cal-acoes button:disabled {{ opacity: .35; cursor: default; }}
    .cal-relatorio {{ background: #fff; border-radius: 10px; box-shadow: 0 2px 16px rgba(0,0,0,.10); overflow: hidden; }}
    .cal-relatorio iframe {{ display: block; width: 100%; height: 100%; border: 0; }}

    @media (max-width: 760px) {{
      .hdr, .perf-nav, .content, .footer {{ padding-left: 16px; padding-right: 16px; }}
      .brand span {{ display: none; }}
      .grid2 {{ grid-template-columns: 1fr; }}
      .filtro-busca {{ min-width: 0; width: 100%; }}
      .nav-fundo {{ margin-left: 0; }}
    }}
    @media (max-width: 980px) {{
      .cal-layout {{ grid-template-columns: 1fr; height: auto; }}
      .cal-relatorio {{ height: 85vh; }}
    }}
    @media print {{
      .nav-wrapper, .toolbar, .ficha-fundo {{ display: none !important; }}
      .perf-pane {{ display: block !important; break-before: page; }}
      .tbl-wrap.alta {{ max-height: none; overflow: visible; }}
      body {{ background: #fff; }}
    }}
    """


def _js():
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

    // Tooltip das marcas (barras, linhas de ativo, pontos): data-tip em texto, uma linha por \n, a 1ª em negrito.
    // Montado com textContent: códigos e nomes vêm do banco.
    document.addEventListener('mouseover', function(e){
      const el = e.target.closest && e.target.closest('[data-tip]');
      if (!el) return;
      tip.replaceChildren();
      el.dataset.tip.split('\n').forEach(function(texto, i){
        const d = document.createElement('div');
        if (i === 0) d.className = 'tt-head';
        d.textContent = texto;
        tip.appendChild(d);
      });
      tip.style.display = 'block';
      posicionarTip(e);
    });
    document.addEventListener('mouseout', function(e){
      if (e.target.closest && e.target.closest('[data-tip]')) tip.style.display = 'none';
    });
    document.addEventListener('mousemove', function(e){
      if (tip.style.display === 'block') posicionarTip(e);
    });

    // Gráficos de série: crosshair que gruda na data mais próxima do mouse, um ponto em cada série visível e o
    // tooltip com todas elas. Os dados vêm em JSON no data-serie do .serie-overlay (_grafico_serie).
    const serieCache = new WeakMap();
    function dadosSerie(ov) {
      if (!serieCache.has(ov)) serieCache.set(ov, JSON.parse(ov.dataset.serie));
      return serieCache.get(ov);
    }
    function indiceSerie(ov, e) {
      const d = dadosSerie(ov);
      const x = new DOMPoint(e.clientX, e.clientY).matrixTransform(ov.ownerSVGElement.getScreenCTM().inverse()).x;
      let melhor = 0;
      for (let i = 1; i < d.xs.length; i++) if (Math.abs(d.xs[i] - x) < Math.abs(d.xs[melhor] - x)) melhor = i;
      return melhor;
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
      const ov = e.target.closest && e.target.closest('.serie-overlay');
      if (!ov) return;
      const svg = ov.ownerSVGElement, d = dadosSerie(ov), box = ov.closest('.serie-chart');
      const i = indiceSerie(ov, e), x = d.xs[i];
      const oculta = function(sid){ return box && box.classList.contains('off-' + sid); };
      const hv = svg.querySelector('.serie-hover');
      hv.style.display = '';
      const cross = hv.querySelector('.serie-cross');
      cross.setAttribute('x1', x); cross.setAttribute('x2', x);
      hv.querySelectorAll('.serie-dot').forEach(function(dot){
        const ys = d.ys[dot.dataset.sid], y = ys ? ys[i] : null;
        if (y === null || y === undefined || oculta(dot.dataset.sid)) { dot.style.display = 'none'; return; }
        dot.style.display = ''; dot.setAttribute('cx', x); dot.setAttribute('cy', y);
      });
      tip.replaceChildren();
      const head = document.createElement('div'); head.className = 'tt-head'; head.textContent = d.titulos[i];
      tip.appendChild(head);
      d.linhas[i].forEach(function(l){ if (!oculta(l[0])) tip.appendChild(linhaTip(l[1], l[2], l[3])); });
      if (d.rodape && d.rodape[i]) {
        const p = document.createElement('div'); p.className = 'tt-foot'; p.textContent = d.rodape[i];
        tip.appendChild(p);
      }
      tip.style.display = 'block';
      posicionarTip(e);
    });
    document.addEventListener('mouseout', function(e){
      const ov = e.target.closest && e.target.closest('.serie-overlay');
      if (!ov) return;
      ov.ownerSVGElement.querySelector('.serie-hover').style.display = 'none';
      tip.style.display = 'none';
    });

    // Mostra/esconde uma série (caixa da legenda) sem regerar o SVG; o container ganha 'off-<série>', que o
    // crosshair usa para pular a série no tooltip.
    function toggleSerie(caixa, chartId, sid) {
      const c = document.getElementById(chartId);
      if (!c) return;
      c.classList.toggle('off-' + sid, !caixa.checked);
      c.querySelectorAll('.serie-' + sid).forEach(function(el){ el.style.display = caixa.checked ? '' : 'none'; });
    }

    // Abas e fundo: as abas são as mesmas para todos os fundos; cada aba tem um .fundo-bloco por fundo. Cada troca
    // dispara o evento 'taxa-media' (o index.html e o relatório dentro dele se avisam por ele).
    function mostrarAba(aba) {
      if (!document.querySelector('.perf-tab-btn[data-aba="' + CSS.escape(aba) + '"]')) return;
      document.querySelectorAll('.perf-tab-btn').forEach(function(b){ b.classList.toggle('active', b.dataset.aba === aba); });
      document.querySelectorAll('.perf-pane').forEach(function(p){ p.classList.toggle('active', p.dataset.aba === aba); });
      document.dispatchEvent(new CustomEvent('taxa-media', {detail: {aba: aba}}));
    }
    function mostrarFundo(fundo) {
      document.querySelectorAll('.fundo-bloco').forEach(function(b){ b.hidden = b.dataset.fundo !== fundo; });
      const sel = document.getElementById('fundo-sel');
      if (sel) sel.value = fundo;
      document.dispatchEvent(new CustomEvent('taxa-media', {detail: {fundo: fundo}}));
    }
    function fundoAtual() {
      const b = document.querySelector('.perf-pane .fundo-bloco:not([hidden])');
      return b ? b.dataset.fundo : '';
    }
    function abaAtual() {
      const b = document.querySelector('.perf-tab-btn.active');
      return b ? b.dataset.aba : '';
    }
    function temFundo(fundo) {
      return !!fundo && !!document.querySelector('.fundo-bloco[data-fundo="' + CSS.escape(fundo) + '"]');
    }
    document.querySelectorAll('.perf-tab-btn').forEach(function(btn){
      btn.addEventListener('click', function(){ mostrarAba(btn.dataset.aba); });
    });
    const seletor = document.getElementById('fundo-sel');
    if (seletor) seletor.addEventListener('change', function(){ mostrarFundo(seletor.value); });

    // Relatório de um dia aberto no index.html (num iframe): sem o cabeçalho, e o fundo e a aba escolhidos aqui vão
    // para o index, que abre o próximo dia no mesmo ponto. O endereço aceita #fundo=...&aba=...
    const embutido = window.parent !== window;
    if (embutido) document.body.classList.add('embutido');
    function avisarIndice() {
      if (embutido) window.parent.postMessage({taxaMedia: 'estado', fundo: fundoAtual(), aba: abaAtual()}, '*');
    }
    document.addEventListener('taxa-media', avisarIndice);
    window.addEventListener('message', function(e){
      const m = e.data;
      if (m && m.taxaMedia === 'fundo' && m.fundo !== fundoAtual() && temFundo(m.fundo)) mostrarFundo(m.fundo);
    });
    function aplicarEndereco() {
      const p = new URLSearchParams(location.hash.slice(1));
      if (temFundo(p.get('fundo')) && p.get('fundo') !== fundoAtual()) mostrarFundo(p.get('fundo'));
      if (p.get('aba')) mostrarAba(p.get('aba'));
      avisarIndice();
    }
    window.addEventListener('hashchange', aplicarEndereco);
    aplicarEndereco();

    // Ordenação: data-v da célula (número cru ou data ISO) ou o texto; vazios sempre no fim.
    function sortTable(th) {
      const table = th.closest('table'), tbody = table.querySelector('tbody');
      const idx = Array.from(th.parentNode.children).indexOf(th);
      const goAsc = !th.classList.contains('asc');
      th.parentNode.querySelectorAll('th').forEach(function(t){ t.classList.remove('asc', 'desc'); });
      th.classList.add(goAsc ? 'asc' : 'desc');
      const chave = function(tr){
        const td = tr.children[idx];
        return !td ? '' : td.dataset.v !== undefined ? td.dataset.v : td.textContent.trim();
      };
      const rows = Array.from(tbody.querySelectorAll('tr'));
      rows.sort(function(a, b){
        const av = chave(a), bv = chave(b);
        if (av === '' || bv === '') return (av === '') - (bv === '');
        const an = Number(av), bn = Number(bv);
        const cmp = (!isNaN(an) && !isNaN(bn)) ? an - bn : av.localeCompare(bv, 'pt');
        return goAsc ? cmp : -cmp;
      });
      rows.forEach(function(r){ tbody.appendChild(r); });
    }

    // Filtros das tabelas: busca (sem acento, sem caixa), selects por atributo data-* da linha e o dia.
    function normalizar(s) { return (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
    const textoCache = new WeakMap();
    function textoLinha(tr) {
      if (!textoCache.has(tr)) textoCache.set(tr, normalizar(tr.textContent));
      return textoCache.get(tr);
    }
    function aplicarFiltros(tid) {
      const t = document.getElementById(tid);
      if (!t) return;
      const busca = document.querySelector('.filtro-busca[data-alvo="' + tid + '"]');
      const termo = busca ? normalizar(busca.value.trim()) : '';
      const sels = Array.from(document.querySelectorAll('.filtro-sel[data-alvo="' + tid + '"]')).filter(function(s){ return s.value; });
      const dia = t.dataset.dia || '';
      let n = 0, total = 0;
      t.querySelectorAll('tbody tr').forEach(function(tr){
        total++;
        const ok = (!dia || tr.dataset.dia === dia)
          && sels.every(function(s){ return tr.dataset[s.dataset.campo] === s.value; })
          && (!termo || textoLinha(tr).includes(termo));
        tr.hidden = !ok;
        if (ok) n++;
      });
      const cont = document.querySelector('.filtro-cont[data-alvo="' + tid + '"]');
      if (cont) cont.textContent = n === total ? total + (total === 1 ? ' linha' : ' linhas') : n + ' de ' + total + ' linhas';
      document.querySelectorAll('[data-filtra="' + tid + '"][data-campo]').forEach(function(c){
        const s = document.querySelector('.filtro-sel[data-alvo="' + tid + '"][data-campo="' + c.dataset.campo + '"]');
        c.classList.toggle('ativo', !!s && s.value === c.dataset.valor);
      });
    }
    function filtrarDia(tid, dia, rotulo) {
      const t = document.getElementById(tid);
      if (!t) return;
      t.dataset.dia = dia || '';
      const chip = document.querySelector('.chip-dia[data-alvo="' + tid + '"]');
      if (chip) { chip.hidden = !dia; chip.querySelector('b').textContent = rotulo || ''; }
      aplicarFiltros(tid);
      if (dia) (document.getElementById(tid + '-titulo') || t).scrollIntoView({behavior: 'smooth', block: 'start'});
    }
    document.addEventListener('input', function(e){
      if (e.target.matches('.filtro-busca')) aplicarFiltros(e.target.dataset.alvo);
    });
    document.addEventListener('change', function(e){
      if (e.target.matches('.filtro-sel')) aplicarFiltros(e.target.dataset.alvo);
    });
    document.querySelectorAll('.filtro-cont').forEach(function(c){ aplicarFiltros(c.dataset.alvo); });

    // Ficha do ativo: cabeçalho e cartões do JSON fichas-dados; as tabelas são cópias das linhas do ativo nas
    // abas LOTES, TRADES e AVISOS do mesmo fundo.
    const elFichas = document.getElementById('fichas-dados');
    const dadosFichas = elFichas ? JSON.parse(elFichas.textContent) : {};
    const fichas = dadosFichas.fundos || {}, cadastro = dadosFichas.cadastro || {};
    function cartao(rotulo, valor, sub) {
      const k = document.createElement('div'); k.className = 'kpi';
      const r = document.createElement('div'); r.className = 'kpi-rot'; r.textContent = rotulo;
      const v = document.createElement('div'); v.className = 'kpi-val'; v.textContent = valor;
      k.append(r, v);
      if (sub) { const s = document.createElement('div'); s.className = 'kpi-sub'; s.textContent = sub; k.appendChild(s); }
      return k;
    }
    // Cadastro do ativo (FUNDOS_CADASTRO_ATIVOS, vigente na data): seções, alterações de valor e todos os campos.
    function blocoCadastro(cad) {
      const caixa = document.createElement('div'); caixa.className = 'cad';
      const grade = document.createElement('div'); grade.className = 'cad-grade';
      cad.secoes.forEach(function(s){
        const sec = document.createElement('div'); sec.className = 'cad-secao';
        const h = document.createElement('h4'); h.textContent = s[0];
        const dl = document.createElement('dl');
        s[1].forEach(function(l){
          const dt = document.createElement('dt'); dt.textContent = l[0];
          const dd = document.createElement('dd'); dd.textContent = l[1];
          dl.append(dt, dd);
        });
        sec.append(h, dl);
        grade.appendChild(sec);
      });
      caixa.appendChild(grade);
      if (cad.mudancas.length) {
        const m = document.createElement('div'); m.className = 'cad-mudancas';
        const t = document.createElement('b'); t.textContent = 'Alterações no cadastro';
        const ul = document.createElement('ul');
        cad.mudancas.forEach(function(x){
          const li = document.createElement('li');
          li.textContent = x[0] + ': ' + x[1].map(function(v){ return v[1] + ' (' + v[0] + ')'; }).join(' → ');
          ul.appendChild(li);
        });
        m.append(t, ul);
        caixa.appendChild(m);
      }
      const det = document.createElement('details'); det.className = 'cad-todos';
      const resumo = document.createElement('summary');
      resumo.textContent = 'Todos os campos do cadastro (' + cad.campos.length + ')';
      const wrap = document.createElement('div'); wrap.className = 'tbl-wrap';
      const tab = document.createElement('table'); tab.className = 'exp-table';
      const cab = document.createElement('tr');
      ['Campo', 'Valor', 'Desde', 'Fonte'].forEach(function(c){
        const th = document.createElement('th'); th.textContent = c; th.title = 'Clique para ordenar';
        th.addEventListener('click', function(){ sortTable(th); });
        cab.appendChild(th);
      });
      const thead = document.createElement('thead'); thead.appendChild(cab);
      const tb = document.createElement('tbody');
      cad.campos.forEach(function(l){
        const tr = document.createElement('tr');
        l.forEach(function(v, j){
          const td = document.createElement('td'); td.textContent = v;
          if (j === 1) td.className = 'txt';
          tr.appendChild(td);
        });
        tb.appendChild(tr);
      });
      tab.append(thead, tb);
      wrap.appendChild(tab);
      det.append(resumo, wrap);
      caixa.appendChild(det);
      return caixa;
    }
    function abrirAtivo(fundo, ativo) {
      const dados = fichas[fundo] || {ativos: {}, slug: '', data: ''};
      const info = dados.ativos[ativo];
      const m = document.getElementById('ficha'), corpo = m.querySelector('.ficha-corpo');
      m.dataset.fundo = fundo;
      corpo.replaceChildren();
      const cad = cadastro[ativo];
      const h = document.createElement('h2'); h.id = 'ficha-titulo'; h.textContent = ativo;
      corpo.appendChild(h);
      if (cad && cad.nome) { const n = document.createElement('p'); n.className = 'ficha-nome'; n.textContent = cad.nome; corpo.appendChild(n); }
      const sub = document.createElement('p'); sub.className = 'ficha-sub';
      sub.textContent = info ? info.sub : 'Fora da carteira em ' + dados.data + ': só aparece nos trades.';
      corpo.appendChild(sub);
      if (cad && cad.descricao) { const d = document.createElement('p'); d.className = 'ficha-desc'; d.textContent = cad.descricao; corpo.appendChild(d); }
      if (info) {
        const k = document.createElement('div'); k.className = 'kpis';
        info.kpis.forEach(function(p){ k.appendChild(cartao(p[0], p[1], p[2])); });
        corpo.appendChild(k);
      }
      if (cad) {
        const t = document.createElement('h3'); t.className = 'aba-title'; t.textContent = 'Cadastro';
        corpo.append(t, blocoCadastro(cad));
      }
      [['Lotes em aberto', 'lotes'], ['Trades', 'trades'], ['Avisos', 'avisos']].forEach(function(s){
        const t = document.getElementById('tbl-' + dados.slug + '-' + s[1]);
        const linhas = t ? Array.from(t.querySelectorAll('tbody tr')).filter(function(tr){ return tr.dataset.ativo === ativo; }) : [];
        const tit = document.createElement('h3'); tit.className = 'aba-title'; tit.textContent = s[0] + ' (' + linhas.length + ')';
        corpo.appendChild(tit);
        if (!linhas.length) {
          const p = document.createElement('p'); p.className = 'aviso'; p.textContent = 'Nenhum.';
          corpo.appendChild(p);
          return;
        }
        const wrap = document.createElement('div'); wrap.className = 'tbl-wrap';
        const tab = document.createElement('table'); tab.className = 'exp-table';
        const tb = document.createElement('tbody');
        linhas.forEach(function(tr){ const c = tr.cloneNode(true); c.hidden = false; tb.appendChild(c); });
        tab.append(t.querySelector('thead').cloneNode(true), tb);
        wrap.appendChild(tab);
        corpo.appendChild(wrap);
      });
      m.classList.add('aberta');
      document.body.classList.add('modal-aberto');
      m.querySelector('.ficha-fechar').focus();
    }
    function fecharFicha() {
      const m = document.getElementById('ficha');
      if (m) m.classList.remove('aberta');
      document.body.classList.remove('modal-aberto');
    }
    function abrirDiaEm(dia, aba) {
      if (dia) document.dispatchEvent(new CustomEvent('abrir-dia', {detail: {dia: dia, aba: aba}}));
    }

    document.addEventListener('click', function(e){
      const t = e.target;
      tip.style.display = 'none';
      if (!t.closest) return;
      const ativo = t.closest('.lk-ativo');
      if (ativo) { const b = ativo.closest('[data-fundo]'); abrirAtivo(b ? b.dataset.fundo : '', ativo.dataset.ativo); return; }
      const fundo = t.closest('.lk-fundo');
      if (fundo) { mostrarFundo(fundo.dataset.fundo); mostrarAba('resumo'); window.scrollTo(0, 0); return; }
      const ir = t.closest('[data-ir]');
      if (ir) { mostrarAba(ir.dataset.ir); window.scrollTo(0, 0); return; }
      const filtro = t.closest('[data-filtra][data-campo]');
      if (filtro) {
        const s = document.querySelector('.filtro-sel[data-alvo="' + filtro.dataset.filtra + '"][data-campo="' + filtro.dataset.campo + '"]');
        if (s) { s.value = s.value === filtro.dataset.valor ? '' : filtro.dataset.valor; aplicarFiltros(filtro.dataset.filtra); }
        return;
      }
      const chip = t.closest('.chip-dia');
      if (chip) { filtrarDia(chip.dataset.alvo, ''); return; }
      const linha = t.closest('table[data-filtra] tbody tr');
      if (linha) { filtrarDia(linha.closest('table').dataset.filtra, linha.dataset.dia, linha.children[0].textContent); return; }
      // no index.html: linha de tabela ou data de gráfico que abre o relatório do dia
      const abre = t.closest('table[data-abre-dia] tbody tr');
      if (abre) { abrirDiaEm(abre.dataset.dia, abre.closest('table').dataset.abreDia); return; }
      const ov = t.closest('.serie-overlay.clicavel');
      if (ov) {
        const d = dadosSerie(ov), i = indiceSerie(ov, e);
        if (d.dias && d.dias[i] && String(d.clique).startsWith('#dia')) abrirDiaEm(d.dias[i], d.clique.split(':')[1]);
        else if (d.dias && d.dias[i]) filtrarDia(d.clique, d.dias[i], d.titulos[i]);
        return;
      }
      if (t.closest('.ficha-fechar') || t.id === 'ficha') fecharFicha();
    });
    document.addEventListener('keydown', function(e){
      if (e.key === 'Escape') fecharFicha();
      if ((e.key === 'Enter' || e.key === ' ') && e.target.matches && e.target.matches('[role="button"]')) {
        e.preventDefault();
        e.target.click();
      }
    });
    """


# ── Página ───────────────────────────────────────────────────────────────────
_ABAS_FUNDO = [("resumo", "RESUMO", _aba_resumo), ("historico", "HISTÓRICO", _aba_historico),
               ("ativos", "ATIVOS", _aba_ativos), ("lotes", "LOTES", _aba_lotes), ("trades", "TRADES", _aba_trades),
               ("avisos", "AVISOS", _aba_avisos)]


def _seletor_fundo(fundos):
    """Seletor de fundo da barra de abas; fundos: [(fundo, nome)]."""
    opcoes = "".join(f'<option value="{_esc(fundo)}">{_esc(fundo)}{" — " + _esc(nome) if nome else ""}</option>'
                     for fundo, nome in fundos)
    return f'<label class="nav-fundo">Fundo <select id="fundo-sel" class="mes-select">{opcoes}</select></label>'


def _json_valor(v):
    if _vazio(v):
        return None
    if isinstance(v, (pd.Timestamp, datetime, date)):
        return _iso(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return float(v)
    return v if isinstance(v, (int, str)) else str(v)


# o que cada relatório diário guarda para o index.html: a linha de cada fundo (aba Fundos) e os trades por dia
_RESUMO_FUNDO = ("fundo", "nome", "status", "taxa_carteira", "financeiro", "taxa_pct", "fin_pct", "taxa_mais",
                 "fin_mais", "n_ativos", "n_lotes", "cdi", "n_avisos", "avisos")
_RESUMO_TRADES = ("fundo",) + tuple(c for c, *_ in _COLUNAS_POR_DIA)


def _resumo_dia(dia, t):
    """<script> com o resumo do dia, que o gerar_indice lê sem abrir o resto do arquivo."""
    def linhas(aba, campos):
        df = t.get(aba, pd.DataFrame())
        return [{c: _json_valor(r.get(c)) for c in campos} for r in df.to_dict("records")]
    dados = {"dia": _iso(dia), "fundos": linhas("Fundos", _RESUMO_FUNDO),
             "trades": linhas("Trades por dia", _RESUMO_TRADES)}
    texto = json.dumps(dados, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/json" id="resumo-dia">{texto}</script>'


def _cabecalho_fundo(f):
    nome = f" ({_esc(f['nome'])})" if f["nome"] else ""
    partes = [f"Fundo: <strong>{_esc(f['fundo'])}</strong>{nome}"]
    if f["data"] is not None:
        partes.append(f"Data: <strong>{_dt(f['data'])}</strong>")
    if f["cdi"]:
        partes.append(f"CDI: <strong>{_br(f['cdi'])}% a.a.</strong>")
    return " &nbsp;|&nbsp; ".join(partes)


def gerar_html(caminho, tabelas, notas=(), dia=None, trades_desde=None):
    """Grava o relatório HTML a partir das tabelas do Excel ({aba: DataFrame} com os nomes internos das colunas, as
    mesmas do salvar_xlsx do __main__; a que faltar fica de fora) e devolve o caminho. Com dia, é o relatório de um
    dia da pasta diario/: o título leva a data, a barra de abas ganha o link para o ../index.html e o <head> guarda
    o resumo do dia que o gerar_indice lê; trades_desde = 1º dia dos trades do relatório (padrão: o próprio dia)."""
    t = {aba: _com_datas(df) for aba, df in tabelas.items() if isinstance(df, pd.DataFrame)}
    fundos_df = t.get("Fundos", pd.DataFrame(columns=["fundo", "status"]))
    param_df = t.get("Parâmetros", pd.DataFrame(columns=["parametro", "valor"]))
    param = dict(zip(param_df["parametro"], param_df["valor"])) if len(param_df) else {}
    # cadastro vigente na data do relatório (a mais recente entre os fundos ou o dia do relatório diário)
    datas = fundos_df["data"].dropna() if "data" in fundos_df.columns else pd.Series(dtype=object)
    data_ref = pd.Timestamp(dia) if dia is not None else pd.Timestamp(datas.max()) if len(datas) else None
    cad_atual, cad_versoes = _cadastro_vigente(t.get("Cadastro"), data_ref)
    fundos = [_preparar_fundo(t, r, cad_atual) for r in fundos_df.to_dict("records")]
    for f in fundos if dia is not None else []:
        f["janela"] = (pd.Timestamp(trades_desde or dia), pd.Timestamp(dia))
    tem_historico = len(t.get("Histórico", ())) > 0

    abas = []
    if len(fundos) > 1:
        abas.append(("fundos", "FUNDOS", _aba_fundos(fundos_df)))
    for aba, rotulo, montar in _ABAS_FUNDO:
        if aba == "historico" and not tem_historico:
            continue
        blocos = []
        for i, f in enumerate(fundos):
            conteudo = f'<p class="aviso">{_esc(f["fundo"])}: {_esc(f["erro"])}</p>' if f["erro"] else montar(f)
            blocos.append(f'<div class="fundo-bloco" data-fundo="{_esc(f["fundo"])}"{" hidden" if i else ""}>'
                          f'{conteudo}</div>')
        abas.append((aba, rotulo, "".join(blocos)))
    abas.append(("metodologia", "METODOLOGIA", _aba_metodologia(param_df, list(notas))))

    nav = "".join(f'<button class="perf-tab-btn{" active" if i == 0 else ""}" data-aba="{aba}">{rotulo}</button>'
                  for i, (aba, rotulo, _) in enumerate(abas))
    direita = [_seletor_fundo([(f["fundo"], f["nome"]) for f in fundos])] if len(fundos) > 1 else []
    if dia is not None:
        direita.append('<a class="nav-cal" href="../index.html" title="Calendário com todos os dias">CALENDÁRIO</a>')
    if direita:
        nav += f'<div class="nav-direita">{"".join(direita)}</div>'
    paineis = "".join(f'<div class="perf-pane{" active" if i == 0 else ""}" data-aba="{aba}">{html}</div>'
                      for i, (aba, _, html) in enumerate(abas))

    sub = "".join(f'<span class="fundo-bloco" data-fundo="{_esc(f["fundo"])}"{" hidden" if i else ""}>'
                  f'{_cabecalho_fundo(f)}</span>' for i, f in enumerate(fundos))
    serie = str(param.get("Série (aba Histórico)", ""))
    if serie and not serie.startswith("não"):
        sub += f" &nbsp;|&nbsp; Série: <strong>{_esc(serie)}</strong>"
    if param.get("Taxa dos CDI+"):
        sub += f" &nbsp;|&nbsp; Taxa dos CDI+: <strong>{_esc(param['Taxa dos CDI+'])}</strong>"
    titulo = _dt(dia) if dia is not None else fundos[0]["fundo"] if len(fundos) == 1 else f"{len(fundos)} fundos"
    resumo_dia = _resumo_dia(dia, t) if dia is not None else ""
    rodape = list(notas)[:1] + ["Método, parâmetros e notas na aba METODOLOGIA"] + (
        [f"Gerado em {param['Gerado em']}"] if param.get("Gerado em") else [])
    rodape = " &nbsp;|&nbsp; ".join(_esc(n) for n in rodape)
    # "</" escapado para o JSON não fechar o <script>
    # cadastro só dos ativos que aparecem no relatório (ativos, lotes, trades e avisos de algum fundo)
    codigos = set()
    for f in fundos:
        for chave, coluna in (("ativos", "codigo"), ("lotes", "codigo"), ("trades", "codigo"), ("avisos", "ativo")):
            codigos |= {str(c) for c in f[chave][coluna].dropna()} if len(f[chave]) else set()
    cadastro = {c: _ficha_cadastro(cad_atual[c], cad_versoes.get(c, {}), data_ref) for c in sorted(codigos)
                if c in cad_atual}
    fichas = json.dumps({"fundos": {f["fundo"]: _fichas(f) for f in fundos if not f["erro"]}, "cadastro": cadastro},
                        ensure_ascii=False)
    fichas = fichas.replace("</", "<\\/")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Taxa média — {_esc(titulo)}</title>
  {resumo_dia}
  <style>{_css()}</style>
</head>
<body>

<div class="hdr">
  <div class="hdr-inner">
    <div>
      <h1>TAXA MÉDIA DE AQUISIÇÃO</h1>
      <p class="sub">Crédito atrelado ao CDI &nbsp;|&nbsp; {sub}</p>
    </div>
    <div class="brand"><span>Itaú Asset Management</span>{_logo_tag()}</div>
  </div>
</div>

<div class="nav-wrapper">
  <nav class="perf-nav">{nav}</nav>
</div>

<div class="content">{paineis}</div>

<div class="footer">{rodape}</div>

<div id="ficha" class="ficha-fundo">
  <div class="ficha" role="dialog" aria-modal="true" aria-labelledby="ficha-titulo">
    <button class="ficha-fechar" title="Fechar (Esc)" aria-label="Fechar">✕</button>
    <div class="ficha-corpo"></div>
  </div>
</div>
<script type="application/json" id="fichas-dados">{fichas}</script>

<script>{_js()}</script>
</body>
</html>"""

    with open(caminho, "w", encoding="utf-8") as arq:
        arq.write(html)
    return caminho


# ── index.html: calendário dos relatórios diários ─────────────────────────────
_PADRAO_DIA = re.compile(r"\d{8}\.html")
_PADRAO_RESUMO = re.compile(r'<script type="application/json" id="resumo-dia">(.*?)</script>', re.S)


def _ler_resumos(pasta):
    """{dia (Timestamp): resumo} de cada pasta/aaaammdd.html; arquivo sem o resumo (de outra versão ou que não é
    relatório) ou com data inválida no nome fica de fora."""
    resumos = {}
    for nome in sorted(os.listdir(pasta)) if os.path.isdir(pasta) else []:
        if not _PADRAO_DIA.fullmatch(nome):
            continue
        with open(os.path.join(pasta, nome), encoding="utf-8", errors="replace") as arq:
            texto = arq.read(200_000)  # o resumo fica no <head>
            m = _PADRAO_RESUMO.search(texto) or _PADRAO_RESUMO.search(texto + arq.read())
        try:
            resumos[pd.Timestamp(nome[:8])] = json.loads(m.group(1))
        except (AttributeError, ValueError):
            continue
    return resumos


def _dados_calendario(fundos, nomes, historico, por_dia, pasta):
    """JSON do calendário: os dias com relatório e, por fundo e dia, a taxa da carteira (embaixo do número do dia),
    se teve trade e as linhas do quadro do dia escolhido."""
    fundos_cal = {}
    for fundo in fundos:
        trades = {}
        g_fundo = por_dia[por_dia["fundo"] == fundo] if len(por_dia) else por_dia
        for (arquivo, op), g in (g_fundo.groupby(["arquivo", "operacao"]) if len(g_fundo) else []):
            n, fin, taxa = _media_por_dia(g)
            texto = f"{_plural(n, op.lower())} · {_rs(fin)}" + (f" · {_cdi_mais(taxa)}" if not _vazio(taxa) else "")
            trades.setdefault(_iso(arquivo), {})[op] = (n, texto)
        dias = {}
        for r in historico[historico["fundo"] == fundo].to_dict("records"):
            iso, ok = _iso(r["data"]), r.get("status") == "OK"
            ops = trades.get(iso, {})
            resumo = [["Carteira", f"{_cdi_mais(r['taxa_carteira'])} (CDI+ eq.)" if ok else str(r.get("status"))]]
            if ok:
                resumo += [["%CDI", _taxa("%CDI", r.get("taxa_pct")) or "—"],
                           ["CDI+", _cdi_mais(r.get("taxa_mais")) or "—"], ["Financeiro", _rs(r.get("financeiro"))],
                           ["Ativos · lotes", f"{_br(_int(r.get('n_ativos')), 0)} · {_br(_int(r.get('n_lotes')), 0)}"],
                           ["Avisos", _br(_int(r.get("n_avisos")), 0)],
                           ["CDI", f"{_br(r['cdi'])}% a.a." if not _vazio(r.get("cdi")) else "—"]]
            resumo += [[f"{op}s", ops[op][1]] for op in ("Compra", "Venda") if op in ops] or [["Trades", "nenhum"]]
            dias[iso] = {"taxa": _br(r["taxa_carteira"]) if ok else "—",
                         "carteira": _cdi_mais(r["taxa_carteira"]) if ok else str(r.get("status")),
                         "trades": sum(n for n, _ in ops.values()), "resumo": resumo}
        fundos_cal[fundo] = dias
    return {"pasta": pasta, "dias": sorted({_iso(d) for d in historico["data"]}), "fundos": fundos_cal,
            "nomes": nomes, "fundoInicial": fundos[0] if fundos else ""}


def gerar_indice(pasta_saida, subpasta="diario"):
    """Grava pasta_saida/index.html a partir dos relatórios em pasta_saida/subpasta/aaaammdd.html: o calendário dos
    dias, o relatório do dia escolhido ao lado e o histórico e os trades de todos os dias. Dias de rodadas
    diferentes entram todos (o índice é refeito do zero a cada rodada). Devolve o caminho, ou None sem relatório."""
    resumos = _ler_resumos(os.path.join(pasta_saida, subpasta))
    if not resumos:
        return None
    linhas_hist, linhas_trades, nomes = [], [], {}
    for dia, r in resumos.items():
        for linha in r.get("fundos", []):
            linhas_hist.append({**linha, "data": dia})
            if linha.get("nome"):
                nomes[linha["fundo"]] = linha["nome"]
        linhas_trades += [{**linha, "arquivo": dia} for linha in r.get("trades", [])]
    historico = _com_datas(pd.DataFrame(linhas_hist)).sort_values("data").reset_index(drop=True)
    por_dia = _com_datas(pd.DataFrame(linhas_trades))
    for df, textos in ((historico, _RESUMO_FUNDO[:3] + ("avisos",)), (por_dia, ("fundo", "operacao"))):
        for c in df.columns.difference(textos + ("data", "arquivo")):  # o JSON traz vazio como None
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if len(por_dia):
        # o mesmo dia de trade em dois relatórios (rodadas com períodos diferentes): vale o relatório mais próximo
        por_dia = (por_dia.sort_values("arquivo").drop_duplicates(["fundo", "data", "operacao"])
                   .sort_values(["data", "operacao"], ascending=[False, True]).reset_index(drop=True))
    fundos = list(dict.fromkeys(historico["fundo"]))

    blocos_hist, blocos_trades = [], []
    for i, fundo in enumerate(fundos):
        f = {"fundo": fundo, "slug": re.sub(r"\W", "_", str(fundo)),
             "historico": historico[historico["fundo"] == fundo].reset_index(drop=True),
             "por_dia": por_dia[por_dia["fundo"] == fundo] if len(por_dia) else pd.DataFrame()}
        abre = f'<div class="fundo-bloco" data-fundo="{_esc(fundo)}"{" hidden" if i else ""}>'
        blocos_hist.append(f"{abre}{_aba_historico(f, abre_dia=True)}</div>")
        blocos_trades.append(f"{abre}{_aba_trades_periodo(f)}</div>")

    calendario = """
<div class="cal-layout">
  <aside class="cal-lateral">
    <div class="cal-box">
      <div class="cal-topo">
        <button type="button" class="cal-nav" id="cal-ant" title="Mês anterior" aria-label="Mês anterior">‹</button>
        <select id="cal-mes" class="mes-select" aria-label="Mês"></select>
        <button type="button" class="cal-nav" id="cal-prox" title="Próximo mês" aria-label="Próximo mês">›</button>
      </div>
      <div class="cal-grade" id="cal-grade"></div>
      <div class="cal-acoes">
        <button type="button" id="dia-ant">‹ Dia anterior</button>
        <button type="button" id="dia-prox">Próximo dia ›</button>
      </div>
      <p class="cal-legenda">Embaixo do dia, a taxa da carteira em CDI+ equivalente; <i></i>dia com trade. As setas ← e →
        trocam o dia, e a aba aberta no relatório continua aberta no dia seguinte.</p>
    </div>
    <div class="cal-box" id="cal-dia"></div>
  </aside>
  <section class="cal-relatorio"><iframe id="dia-frame" title="Relatório do dia"></iframe></section>
</div>"""
    abas = [("calendario", "CALENDÁRIO", calendario), ("historico", "HISTÓRICO", "".join(blocos_hist)),
            ("trades", "TRADES", "".join(blocos_trades))]
    nav = "".join(f'<button class="perf-tab-btn{" active" if i == 0 else ""}" data-aba="{aba}">{rotulo}</button>'
                  for i, (aba, rotulo, _) in enumerate(abas))
    if len(fundos) > 1:
        nav += f'<div class="nav-direita">{_seletor_fundo([(f, nomes.get(f, "")) for f in fundos])}</div>'
    paineis = "".join(f'<div class="perf-pane{" active" if i == 0 else ""}" data-aba="{aba}">{html}</div>'
                      for i, (aba, _, html) in enumerate(abas))
    dias = sorted(resumos)
    lista = ", ".join(f"{_esc(f)}{f' ({_esc(nomes[f])})' if nomes.get(f) else ''}" for f in fundos)
    sub = (f"Calendário diário &nbsp;|&nbsp; {'Fundos' if len(fundos) > 1 else 'Fundo'}: <strong>{lista}</strong> "
           f"&nbsp;|&nbsp; <strong>{_plural(len(dias), 'dia')}</strong>, de <strong>{_dt(dias[0])}</strong> a "
           f"<strong>{_dt(dias[-1])}</strong>")
    dados = json.dumps(_dados_calendario(fundos, nomes, historico, por_dia, subpasta), ensure_ascii=False)
    dados = dados.replace("</", "<\\/")
    rodape = (f"Cada dia é o relatório {_esc(subpasta)}/aaaammdd.html, com a carteira, os ativos, os lotes, os trades "
              f"e os avisos da data &nbsp;|&nbsp; Índice gerado em {datetime.now():%d/%m/%Y %H:%M}")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Taxa média — calendário</title>
  <style>{_css()}</style>
</head>
<body>

<div class="hdr">
  <div class="hdr-inner">
    <div>
      <h1>TAXA MÉDIA DE AQUISIÇÃO</h1>
      <p class="sub">{sub}</p>
    </div>
    <div class="brand"><span>Itaú Asset Management</span>{_logo_tag()}</div>
  </div>
</div>

<div class="nav-wrapper">
  <nav class="perf-nav">{nav}</nav>
</div>

<div class="content">{paineis}</div>

<div class="footer">{rodape}</div>

<script type="application/json" id="calendario-dados">{dados}</script>
<script>{_js()}</script>
<script>{_js_indice()}</script>
</body>
</html>"""

    caminho = os.path.join(pasta_saida, "index.html")
    with open(caminho, "w", encoding="utf-8") as arq:
        arq.write(html)
    return caminho


def _js_indice():
    return r"""
    // Calendário dos dias com relatório, o relatório do dia escolhido no iframe e o estado (fundo e aba) que passa
    // de um dia para o outro. Os dados vêm do JSON calendario-dados (gerar_indice).
    const cal = JSON.parse(document.getElementById('calendario-dados').textContent);
    const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro',
                   'outubro', 'novembro', 'dezembro'];
    const SEMANA = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
    const temDia = new Set(cal.dias);
    const meses = Array.from(new Set(cal.dias.map(function(d){ return d.slice(0, 7); })));
    const estado = {fundo: cal.fundoInicial, aba: 'resumo', dia: cal.dias[cal.dias.length - 1], mes: ''};
    const grade = document.getElementById('cal-grade'), selMes = document.getElementById('cal-mes');
    const frame = document.getElementById('dia-frame');

    meses.forEach(function(m){
      const o = document.createElement('option');
      o.value = m;
      o.textContent = MESES[Number(m.slice(5)) - 1] + ' de ' + m.slice(0, 4);
      selMes.appendChild(o);
    });
    function infoDia(dia) { return (cal.fundos[estado.fundo] || {})[dia]; }
    function arquivo(dia) { return cal.pasta + '/' + dia.replace(/-/g, '') + '.html'; }
    function dataLonga(dia) {
      const p = dia.split('-').map(Number);
      const s = new Date(p[0], p[1] - 1, p[2]).toLocaleDateString('pt-BR',
        {weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric'});
      return s.charAt(0).toUpperCase() + s.slice(1);
    }

    function desenharMes(mes) {
      estado.mes = mes;
      selMes.value = mes;
      grade.replaceChildren();
      SEMANA.forEach(function(s){
        const h = document.createElement('div'); h.className = 'cal-sem'; h.textContent = s;
        grade.appendChild(h);
      });
      const ano = Number(mes.slice(0, 4)), m = Number(mes.slice(5));
      const vazios = new Date(ano, m - 1, 1).getDay(), n = new Date(ano, m, 0).getDate();
      for (let i = 0; i < vazios; i++) grade.appendChild(document.createElement('span'));
      for (let d = 1; d <= n; d++) {
        const dia = mes + '-' + String(d).padStart(2, '0');
        const b = document.createElement('button');
        b.type = 'button'; b.className = 'cal-dia';
        const num = document.createElement('span'); num.className = 'cal-num'; num.textContent = d;
        b.appendChild(num);
        if (temDia.has(dia)) {
          const info = infoDia(dia);
          b.dataset.dia = dia;
          const tx = document.createElement('span'); tx.className = 'cal-tx'; tx.textContent = info ? info.taxa : '—';
          b.appendChild(tx);
          if (info && info.trades) { const p = document.createElement('i'); p.className = 'cal-trade'; b.appendChild(p); }
          b.title = dataLonga(dia) + (info ? ' · carteira ' + info.carteira
            + (info.trades ? ' · ' + info.trades + (info.trades === 1 ? ' trade' : ' trades') : '')
            : ' · o fundo não está no relatório do dia');
          b.classList.toggle('sel', dia === estado.dia);
          if (dia === estado.dia) b.setAttribute('aria-current', 'date');
        } else {
          b.disabled = true;
        }
        grade.appendChild(b);
      }
      const i = meses.indexOf(mes);
      document.getElementById('cal-ant').disabled = i <= 0;
      document.getElementById('cal-prox').disabled = i >= meses.length - 1;
    }

    function preencherDia() {
      const box = document.getElementById('cal-dia');
      box.replaceChildren();
      const t = document.createElement('div'); t.className = 'cal-titulo'; t.textContent = dataLonga(estado.dia);
      const f = document.createElement('div'); f.className = 'cal-fundo';
      f.textContent = estado.fundo + (cal.nomes && cal.nomes[estado.fundo] ? ' — ' + cal.nomes[estado.fundo] : '');
      box.append(t, f);
      const info = infoDia(estado.dia);
      if (info) {
        const dl = document.createElement('dl'); dl.className = 'cal-resumo';
        info.resumo.forEach(function(r){
          const dt = document.createElement('dt'); dt.textContent = r[0];
          const dd = document.createElement('dd'); dd.textContent = r[1];
          dl.append(dt, dd);
        });
        box.appendChild(dl);
      } else {
        const p = document.createElement('p'); p.className = 'cal-legenda';
        p.textContent = 'O fundo não está no relatório deste dia.';
        box.appendChild(p);
      }
      const i = cal.dias.indexOf(estado.dia);
      document.getElementById('dia-ant').disabled = i <= 0;
      document.getElementById('dia-prox').disabled = i >= cal.dias.length - 1;
      const a = document.createElement('a');
      a.className = 'cal-abrir'; a.href = arquivo(estado.dia); a.target = '_blank'; a.rel = 'noopener';
      a.textContent = 'Abrir este dia em nova aba ↗';
      box.appendChild(a);
    }

    function abrirDia(dia, aba) {
      if (!temDia.has(dia)) return;
      if (aba) estado.aba = aba;
      estado.dia = dia;
      desenharMes(dia.slice(0, 7));
      preencherDia();
      frame.src = arquivo(dia) + '#fundo=' + encodeURIComponent(estado.fundo) + '&aba=' + encodeURIComponent(estado.aba);
      mostrarAba('calendario');
    }
    function passarDia(passo) {
      const i = cal.dias.indexOf(estado.dia) + passo;
      if (i >= 0 && i < cal.dias.length) abrirDia(cal.dias[i]);
    }

    document.getElementById('cal-ant').addEventListener('click', function(){
      const i = meses.indexOf(estado.mes);
      if (i > 0) desenharMes(meses[i - 1]);
    });
    document.getElementById('cal-prox').addEventListener('click', function(){
      const i = meses.indexOf(estado.mes);
      if (i < meses.length - 1) desenharMes(meses[i + 1]);
    });
    selMes.addEventListener('change', function(){ desenharMes(selMes.value); });
    grade.addEventListener('click', function(e){
      const b = e.target.closest('.cal-dia[data-dia]');
      if (b) abrirDia(b.dataset.dia);
    });
    document.getElementById('dia-ant').addEventListener('click', function(){ passarDia(-1); });
    document.getElementById('dia-prox').addEventListener('click', function(){ passarDia(1); });
    document.addEventListener('keydown', function(e){
      if (abaAtual() !== 'calendario' || (e.target.matches && e.target.matches('input, select, textarea'))) return;
      if (e.key === 'ArrowLeft') { e.preventDefault(); passarDia(-1); }
      if (e.key === 'ArrowRight') { e.preventDefault(); passarDia(1); }
    });
    // linha de tabela ou data de gráfico das abas HISTÓRICO e TRADES
    document.addEventListener('abrir-dia', function(e){ abrirDia(e.detail.dia, e.detail.aba); });

    // O relatório do dia avisa a aba e o fundo escolhidos nele (o fundo só vale se o relatório tem o fundo do
    // índice: senão ele mostra outro sem a pessoa ter pedido); o seletor de fundo do índice avisa o relatório.
    window.addEventListener('message', function(e){
      const m = e.data;
      if (!m || m.taxaMedia !== 'estado' || e.source !== frame.contentWindow) return;
      if (m.aba) estado.aba = m.aba;
      if (m.fundo && m.fundo !== estado.fundo && cal.fundos[m.fundo] && infoDia(estado.dia)) mostrarFundo(m.fundo);
    });
    document.addEventListener('taxa-media', function(e){
      const fundo = e.detail.fundo;
      if (!fundo || fundo === estado.fundo) return;
      estado.fundo = fundo;
      desenharMes(estado.mes);
      preencherDia();
      if (frame.contentWindow) frame.contentWindow.postMessage({taxaMedia: 'fundo', fundo: fundo}, '*');
    });

    abrirDia(estado.dia);
    """
