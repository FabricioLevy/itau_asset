"""
Gera fluxograma_load_dados337.html descrevendo o fluxo da Sub Load_DADOS337().
"""

import json
from pathlib import Path


# ── dados estruturados ────────────────────────────────────────────────────────

SQL_QUERIES = [
    # (nome, fonte, destino_col, aba, categoria, descricao)
    ("sql_VCRAPLSI",         "view_vcraplsi",                       "Col F",  "Consulta", "pos",   "PL total por fundo"),
    ("sql_VCRAPRF",          "view_vcraprf",                        "Col U",  "Consulta", "pos",   "Posicao Renda Fixa"),
    ("sql_VCRAPRDP",         "view_vcraprdp",                       "Col X",  "Consulta", "pos",   "Posicao DP (excl. 251, 986, 987)"),
    ("sql_SALDO_TESOURARIA", "view_vcraprdp (mttp=251)",            "Col AQ", "Consulta", "pos",   "Saldo Tesouraria"),
    ("sql_COTAS",            "view_vcrapfdo (vl_liq)",              "Col AN", "Consulta", "fdo",   "Cotas de fundos"),
    ("sql_FUTURO",           "view_vcrapfut",                       "Col BD", "Consulta", "pos",   "Futuros notional cotacao"),
    ("sql_BMFXTWO",          "fundos_dados_moedas (BRL_B3_2/USD)",  "Col BZ", "Consulta", "moeda", "USD/BRL"),
    ("sql_GBP16H",           "fundos_dados_moedas (BRL_B3_2/GBP)", "Col CC", "Consulta", "moeda", "GBP/BRL"),
    ("sql_EURO",             "fundos_dados_moedas (BRL_B3_2/EUR)", "Col CG", "Consulta", "moeda", "EUR/BRL"),
    ("sql_CNY",              "FUNDOS_DADOS_INDICES (CNYXBR10)",     "Col EY", "Consulta", "moeda", "CNY/BRL"),
    ("sql_CC_EXTERIOR",      "view_vcrapfdo (vl_total)",            "Col BP", "Consulta", "fdo",   "Caixa exterior"),
    ("sql_PRFABERTO",        "view_vcraprf (NTN-B/F, LTN, DEBIN)", "Col CN", "Consulta", "pos",   "RF Aberto"),
    ("sql_swap",             "view_vcrapswp",                       "Col CS", "Consulta", "pos",   "Swap ativo / passivo"),
    ("sql_duration",         "view_vcraprf",                        "Col A",  "Duration", "dur",   "Duration RF"),
    ("sql_indexduration",    "tbhh3031_anbima_indices",             "Col R",  "Duration", "dur",   "Duration indice ANBIMA"),
    ("sql_dolarcupomlimpo",  "fundos_dados_moedas (BRL_B3_CL/USD)","Col DP", "Consulta", "moeda", "USD cupom limpo"),
    ("sql_cotacoesvsusd",    "bbg_fx (GBPUSD F150)",                "Col DU", "Consulta", "moeda", "GBP vs USD"),
    ("sql_eurousd",          "bbg_fx (EURUSD F150)",                "Col DZ", "Consulta", "moeda", "EUR vs USD"),
    ("proventos",            "view_vcraprdp (mttp 61,62,69,261)",   "Col DX", "Consulta", "prov",  "Proventos RV"),
    ("moedas",               "bbg_fx (ADU3/CDU3/ECU3/JYU3)",        "Col AO", "Moedas",   "moeda", "Moedas futuros"),
    ("sql_COTAS_quebradas",  "view_vcrapfdo (FICAD_CD)",            "Col EE", "Consulta", "fdo",   "Cotas com quebra"),
    ("sql_FUSION",           "VieW_FUNDOS_POSICAO (FUSION57691)",   "Col EI", "Consulta", "fus",   "Fusion Future"),
    ("consulta_fut",         "view_vcrapfut (c/ fuvct_cd)",         "Col A",  "Rolagens", "pos",   "Rolagens de futuros"),
    ("sql_pfdo",             "view_vcrapfdo (TIPO_CLASSIF)",        "Col EQ", "Consulta", "fdo",   "Posicao FDO"),
    ("consulta_teva",        "FUNDOS_COMPOSICAO_INDICES (ITBR_5_PRE)", "Col EW", "Consulta", "dur", "Teva Pre 5"),
]

FORMULAS = [
    ("D3:D",   "Consulta", "=SUMIF(col_H, clcli, col_P)",             "PL consolidado por fundo"),
    ("N3:N",   "Consulta", "conv. USD/GBP/CNY -> BRL",                "Conversao cambial posicoes RV"),
    ("BJ3:BJ", "Consulta", "SE DI1 -> qty x NETWORKDAYS(ref, vencto)", "Exposicao DU futuros DI"),
    ("BK3:BK", "Consulta", "=NETWORKDAYS(ref, vencto, Feriados)",      "Prazo util ate vencimento"),
    ("BS3:BS", "Consulta", "SE 'CAIXA - DOLAR US' -> valor x USD",    "Caixa dolar em BRL"),
    ("BT3:BT", "Consulta", "SE 'CAIXA - LIBRA' -> valor x GBP",       "Caixa libra em BRL"),
    ("BU3:BU", "Consulta", "SE 'C/C-EUR' -> valor x EUR",             "Caixa euro em BRL"),
    ("BV3:BV", "Consulta", "=SUM(BS:BU)",                             "Total caixa exterior em BRL"),
    ("G3:G",   "Duration", "=qt_total x vl_pu x duration",            "Exposicao duration ponderada"),
]

CLEAR_RANGES = {
    "Consulta": [
        "D", "F:G", "I:N", "U:V", "X:Y", "AN:AO", "AQ:AR",
        "BD:BK", "BP:BV", "BY:CI", "CL:CN", "CS:CV", "CX:CZ",
        "DD:DE", "DG:DH", "DJ:DL", "DO:DQ", "DT:DV", "DX:DZ",
        "EE:EG", "EI:EN", "EQ:EU", "EW:EY", "FA:FG",
    ],
    "Duration": ["A:G", "R:T"],
    "Alerta":   ["B"],
    "Moedas":   ["AO:AQ"],
    "Rolagens": ["A:G"],
}

CAT_CSS = {
    "pos":   "t-pos",
    "moeda": "t-moeda",
    "dur":   "t-dur",
    "rv":    "t-rv",
    "fdo":   "t-fdo",
    "prov":  "t-prov",
    "fus":   "t-fus",
}

LEGEND_ITEMS = [
    ("#2471a3", "Posicao"),
    ("#1e8449", "Moeda / FX"),
    ("#b7770d", "Duration / ANBIMA"),
    ("#7d3c98", "Renda Variavel / BTC"),
    ("#148f77", "Fundos / Cotas"),
    ("#a93226", "Proventos"),
    ("#6a5acd", "Fusion / Teva"),
]

TODO_ITEMS = [
    {"id": "t1",  "text": "Inicializar ambiente VBA (DisplayAlerts OFF, ScreenUpdating OFF, Calc Manual)", "done": True},
    {"id": "t2",  "text": "Ler data de referencia da planilha PRM!E2 -> dt_planilha", "done": True},
    {"id": "t3",  "text": "Construir strings de tickers: string_builder, string_builderrv, string_builderCOTAS", "done": True},
    {"id": "t4",  "text": "Definir as 25 queries SQL no banco dbsx337", "done": True},
    {"id": "t5",  "text": "Limpar intervalos das abas: Consulta, Duration, Alerta, Moedas, Rolagens", "done": True},
    {"id": "t6",  "text": "Conectar ao banco via ADODB (Call sSQL_Connect -> dbsx337)", "done": True},
    {"id": "t7",  "text": "Executar bloco PRV: acoes RV + aluguel BTC via planilha TEMP", "done": True},
    {"id": "t8",  "text": "Executar as 25 queries e escrever resultados no workbook", "done": True},
    {"id": "t9",  "text": "Inserir formulas: PL consolidado, cambio, DU, caixa exterior", "done": True},
    {"id": "t10", "text": "Aplicar AutoFilter no Relatorio (campo 29, >100.1% ou <99.99%)", "done": True},
    {"id": "t11", "text": "Restaurar configuracoes Excel (DisplayAlerts ON, ScreenUpdating ON, Calc Auto)", "done": True},
    {"id": "t12", "text": "Validar queries de moedas com novas fontes BBG FX", "done": False},
    {"id": "t13", "text": "Testar bloco PRV com fundos FICAD_CD adicionados recentemente", "done": False},
    {"id": "t14", "text": "Documentar estrutura das colunas da planilha PRM", "done": False},
]


# ── helpers HTML ──────────────────────────────────────────────────────────────


def tag(name, source, dest_col, sheet, cat, label):
    css = CAT_CSS.get(cat, "t-pos")
    return (
        '<div class="tag ' + css + '">'
        "<strong>" + name + "</strong>"
        '<span class="src">&#x1F4E6; ' + source + "</span>"
        '<span class="dest">&#x279C; ' + sheet + " &middot; " + dest_col + "</span>"
        '<span class="lbl">' + label + "</span>"
        "</div>"
    )


def arrow():
    return '<div class="arrow"></div>'


def node(content, extra_css="", width=320):
    return (
        '<div class="node ' + extra_css + '" style="width:' + str(width) + 'px">'
        + content
        + "</div>"
    )


def group(title, inner, cols=3, width=700, border_color="#333"):
    cls = "cols" + str(cols)
    return (
        '<div class="group" style="width:' + str(width) + "px;border-color:" + border_color + '">'
        '<div class="group-title">' + title + "</div>"
        '<div class="group-grid ' + cls + '">'
        + inner
        + "</div></div>"
    )


# ── blocos de conteudo ────────────────────────────────────────────────────────


def bloco_init():
    inner = (
        '<div class="bloco-header">&#x2699; Inicializacao do Ambiente VBA</div>'
        '<div class="bloco-sub">Workbook: <strong>Exposicao Beta V20.xlsm</strong>'
        " &nbsp;&middot;&nbsp; Parametros: <strong>PRM</strong></div>"
        '<div class="bloco-code">'
        'Application.DisplayAlerts = <span class="kw">False</span><br>'
        'Application.ScreenUpdating = <span class="kw">False</span><br>'
        'Application.Calculation = <span class="kw">xlCalculationManual</span><br>'
        '<span class="code-comment">\'-- leitura da data de referencia --</span><br>'
        'dt_planilha = Format(prm.Range(<span class="str">"E2"</span>), <span class="str">"yyyy-mm-dd"</span>)'
        "</div>"
        '<div class="bloco-detail">'
        '<span class="badge badge-blue">PRM!E2</span> Data de referencia do carregamento'
        "</div>"
    )
    return node(inner, "c-init", 520)


def bloco_string_builders():
    inner = (
        tag("string_builder",        "prm col B (linhas 3->N)", "col B",  "PRM", "fdo", "Tickers principais - fundos e cotas")
        + tag("string_builderrv",    "prm col U (linhas 3->N)", "col U",  "PRM", "rv",  "Tickers RV (usados em proventos)")
        + tag("string_builderCOTAS", "prm col AB (linhas 3->N)","col AB", "PRM", "fus", "Fundos com quebra de cotas (FICAD_CD)")
    )
    return group("&#x1F3D7; Montagem de strings de tickers &mdash; planilha PRM", inner, cols=3, width=620)


def bloco_queries():
    tags = "".join(
        tag(q[0], q[1], q[2], q[3], q[4], q[5])
        for q in SQL_QUERIES
    )
    n = len(SQL_QUERIES)
    return group(
        "&#x1F4DD; Definicao das queries SQL &mdash; banco dbsx337 (" + str(n) + " queries)",
        tags, cols=3, width=820,
    )


def bloco_clear():
    rows = ""
    for aba, cols in CLEAR_RANGES.items():
        rows += (
            '<div class="clear-row">'
            '<span class="clear-aba">' + aba + "</span>"
            '<span class="clear-cols">' + " &middot; ".join(cols) + "</span>"
            '<span class="clear-count">' + str(len(cols)) + " int.</span>"
            "</div>"
        )
    total = sum(len(v) for v in CLEAR_RANGES.values())
    inner = (
        '<div class="bloco-header">&#x1F5D1; Limpeza de intervalos</div>'
        '<div class="bloco-sub">'
        + str(total) + " intervalos em " + str(len(CLEAR_RANGES)) + " abas"
        + "</div>"
        + rows
    )
    return node(inner, "c-clear", 640)


def bloco_connect():
    inner = (
        '<div class="bloco-header">&#x1F50C; Conexao com banco de dados</div>'
        '<div class="bloco-sub">Call <strong>sSQL_Connect</strong></div>'
        '<div class="bloco-code">'
        'Provider: <span class="kw">ADODB.Connection</span><br>'
        "Data Source: <strong>dbsx337</strong><br>"
        'Retorno: <span class="str">conn</span> &amp; <span class="str">rst</span> (Recordset)'
        "</div>"
        '<div class="bloco-detail">'
        '<span class="badge badge-teal">ADODB</span> Conexao reutilizada por todas as queries'
        "</div>"
    )
    return node(inner, "c-connect", 390)


def bloco_prv():
    steps = [
        ("1. Cria aba TEMP",                   "Worksheets.Add.Name = &quot;TEMP&quot;"),
        ("2. sql_ALUGUEL &rarr; TEMP!A2",       "VIEW_VCRABTC: CLCLI_CD, CODPAP, tipo_movimento, CASE Doador/Tomador qty"),
        ("3. sql_prv &rarr; TEMP!F2",           "VIEW_vcraprv JOIN VIEW_FUNDOS_POSICAO: acao, qtd, preco, moeda"),
        ("4. sql_join &rarr; TEMP!M2",          "VIEW_vcraprv: lista clcli_cd x acao"),
        ("5. sql_join2 &rarr; TEMP!M (append)", "VIEW_VCRABTC: lista clcli_cd x CODPAP"),
        ("6. Sort + RemoveDuplicates (M:N)",    "Ordena por acao/papel e fundo; remove duplicatas"),
        ("7. Col O &mdash; Qtd liquida",        "=SUMIFS(qtdBTC_Doador) + SUMIFS(qtdBTC_Tomador) + SUMIFS(qtdPRV)"),
        ("8. Col P &mdash; Financeiro",         "=qty x preco (com ajuste EXCS LN x100)"),
        ("9. Col Q &mdash; Moeda",              "=VLOOKUP(acao, tbl_prv, col_moeda)"),
        ("10. Copia TEMP!M:Q &rarr; Consulta!I3 (PasteValues) &middot; Deleta TEMP", ""),
    ]
    rows = "".join(
        '<div class="tag t-rv"><strong>' + s + "</strong>"
        + ('<span class="src">' + d + "</span>" if d else "")
        + "</div>"
        for s, d in steps
    )
    inner = '<div style="display:flex;gap:8px;flex-direction:column">' + rows + "</div>"
    return (
        '<div class="group" style="width:780px;border-color:#6c3483">'
        '<div class="group-title" style="color:#c39bd3">'
        "&#x2699; Bloco PRV &mdash; Acoes RV + Aluguel BTC (planilha TEMP intermediaria)"
        "</div>" + inner + "</div>"
    )


def bloco_exec_queries():
    header = (
        "<tr><th>#</th><th>Query</th><th>Fonte (dbsx337)</th>"
        "<th>Aba</th><th>Destino</th><th>Descricao</th></tr>"
    )
    rows = "".join(
        "<tr><td>" + str(i + 1) + "</td>"
        "<td><code>" + q[0] + "</code></td>"
        "<td>" + q[1] + "</td>"
        "<td>" + q[3] + "</td>"
        "<td><code>" + q[2] + "</code></td>"
        "<td>" + q[5] + "</td></tr>"
        for i, q in enumerate(SQL_QUERIES)
    )
    n = len(SQL_QUERIES)
    return (
        '<div class="group" style="width:920px">'
        '<div class="group-title">&#x25B6; Execucao das queries e destino no workbook ('
        + str(n) + " queries)</div>"
        '<table class="ftable"><thead>' + header + "</thead><tbody>" + rows + "</tbody></table>"
        "</div>"
    )


def bloco_formulas():
    header = (
        "<tr><th>Intervalo</th><th>Aba</th>"
        "<th>Formula / Logica</th><th>Proposito</th></tr>"
    )
    rows = "".join(
        "<tr><td><code>" + f[0] + "</code></td>"
        "<td>" + f[1] + "</td>"
        "<td><code>" + f[2] + "</code></td>"
        "<td>" + f[3] + "</td></tr>"
        for f in FORMULAS
    )
    n = len(FORMULAS)
    return (
        '<div class="group" style="width:820px;border-color:#d4ac0d">'
        '<div class="group-title" style="color:#f4d03f">'
        "&#x1F9EE; Insercao de formulas (" + str(n) + " formulas)</div>"
        '<table class="ftable"><thead>' + header + "</thead><tbody>" + rows + "</tbody></table>"
        "</div>"
    )


def bloco_autofilter():
    inner = (
        '<div class="bloco-header">&#x1F50D; AutoFilter &mdash; Aba Relatorio</div>'
        '<div class="bloco-sub">Filtra fundos com desvio de cotizacao relevante</div>'
        '<div class="bloco-code">'
        'Range: <span class="str">A3:AH</span> &nbsp;&middot;&nbsp; Campo: <span class="kw">29</span><br>'
        'Criteria1: <span class="str">&quot;&gt;100.1%&quot;</span>'
        ' &nbsp; Operator: <span class="kw">xlOr</span><br>'
        'Criteria2: <span class="str">&quot;&lt;99.99%&quot;</span>'
        "</div>"
        '<div class="bloco-detail">'
        '<span class="badge badge-purple">Relatorio</span>'
        " Destaca fundos fora do intervalo <strong>99.99% &ndash; 100.1%</strong>"
        "</div>"
    )
    return node(inner, "c-filter", 510)


def bloco_restore():
    inner = (
        '<div class="bloco-header">&#x267B; Restauracao das configuracoes</div>'
        '<div class="bloco-sub">Reverte estado do Excel para modo normal de uso</div>'
        '<div class="bloco-code">'
        'Application.DisplayAlerts = <span class="kw">True</span><br>'
        'Application.ScreenUpdating = <span class="kw">True</span><br>'
        'Application.Calculation = <span class="kw">xlCalculationAutomatic</span>'
        "</div>"
    )
    return node(inner, "c-init", 440)


def bloco_legend():
    items = "".join(
        '<div class="legend-item">'
        '<div class="legend-dot" style="background:' + cor + '"></div>' + label
        + "</div>"
        for cor, label in LEGEND_ITEMS
    )
    return '<div class="legend">' + items + "</div>"


# ── CSS ───────────────────────────────────────────────────────────────────────

CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Segoe UI', Arial, sans-serif;
  background: #0f1117;
  color: #e0e0e0;
  padding: 28px 16px 64px;
  min-width: 960px;
}

h1 {
  text-align: center;
  font-size: 1.6rem;
  font-weight: 700;
  color: #fff;
  letter-spacing: .04em;
  margin-bottom: 4px;
}
.subtitle {
  text-align: center;
  font-size: .82rem;
  color: #888;
  margin-bottom: 32px;
}

.page-layout {
  display: flex;
  gap: 24px;
  align-items: flex-start;
  max-width: 1600px;
  margin: 0 auto;
}
.flow-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 0;
}
.todo-col {
  width: 340px;
  min-width: 300px;
  flex-shrink: 0;
  align-self: flex-start;
  position: sticky;
  top: 16px;
  max-height: calc(100vh - 32px);
  overflow-y: auto;
}
.todo-col::-webkit-scrollbar { width: 4px; }
.todo-col::-webkit-scrollbar-thumb { background: #2a2d3e; border-radius: 4px; }

.flow {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
  width: 100%;
}

.arrow {
  width: 2px;
  height: 28px;
  background: #444;
  position: relative;
  flex-shrink: 0;
}
.arrow::after {
  content: '';
  position: absolute;
  bottom: -7px;
  left: 50%;
  transform: translateX(-50%);
  border-left: 7px solid transparent;
  border-right: 7px solid transparent;
  border-top: 9px solid #444;
}

.node {
  border-radius: 8px;
  padding: 12px 18px;
  text-align: center;
  font-size: .82rem;
  font-weight: 600;
  line-height: 1.4;
  border: 2px solid transparent;
  transition: transform .15s, box-shadow .15s;
  cursor: default;
}
.node:hover { transform: translateY(-2px); box-shadow: 0 6px 24px rgba(0,0,0,.5); }
.oval { border-radius: 40px; width: 180px !important; }

.c-start   { background:#1a3a2e; border-color:#27ae60; color:#2ecc71; }
.c-end     { background:#2a1a1a; border-color:#c0392b; color:#e74c3c; }
.c-init    { background:#1a2340; border-color:#2980b9; color:#74b9ff; }
.c-clear   { background:#2a1a1a; border-color:#e67e22; color:#f0a868; }
.c-connect { background:#1a2a2a; border-color:#16a085; color:#76d7c4; }
.c-filter  { background:#1a1a2a; border-color:#9b59b6; color:#c39bd3; }

.bloco-header { font-size:.9rem; font-weight:700; margin-bottom:6px; }
.bloco-sub    { font-size:.72rem; font-weight:400; color:#aaa; margin-bottom:8px; }
.bloco-code {
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: .72rem;
  font-weight: 400;
  background: rgba(0,0,0,.3);
  border-radius: 5px;
  padding: 7px 10px;
  text-align: left;
  line-height: 1.7;
  margin-bottom: 8px;
}
.bloco-detail { font-size:.7rem; font-weight:400; color:#bbb; text-align:left; }
.kw           { color:#569cd6; }
.str          { color:#ce9178; }
.code-comment { color:#6a9955; }

.badge {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 4px;
  font-size: .65rem;
  font-weight: 700;
  margin-right: 4px;
  vertical-align: middle;
}
.badge-blue   { background:#1e3a5f; color:#74b9ff;  border:1px solid #2980b9; }
.badge-teal   { background:#0e2a28; color:#76d7c4;  border:1px solid #16a085; }
.badge-purple { background:#1e0e30; color:#c39bd3;  border:1px solid #8e44ad; }

.clear-row    { display:flex; align-items:baseline; gap:8px; padding:4px 0; border-bottom:1px solid rgba(255,255,255,.05); font-size:.72rem; }
.clear-aba    { font-weight:700; color:#f0a868; min-width:80px; }
.clear-cols   { color:#ccc; flex:1; font-family:'Consolas',monospace; font-size:.68rem; }
.clear-count  { color:#666; font-size:.65rem; white-space:nowrap; }

.group {
  border: 1.5px solid #333;
  border-radius: 12px;
  padding: 12px 16px;
  background: #13151c;
}
.group-title {
  font-size: .72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .06em;
  color: #aaa;
  margin-bottom: 10px;
}
.group-grid        { display:grid; gap:6px; }
.group-grid.cols2  { grid-template-columns: 1fr 1fr; }
.group-grid.cols3  { grid-template-columns: 1fr 1fr 1fr; }

.tag          { border-radius:6px; padding:7px 10px; font-size:.74rem; font-weight:600; line-height:1.35; }
.tag strong   { display:block; margin-bottom:3px; }
.tag .src     { font-size:.64rem; font-weight:400; opacity:.8;  display:block; margin-top:1px; }
.tag .dest    { font-size:.62rem; font-weight:400; opacity:.65; display:block; margin-top:1px; color:#7ec8e3; }
.tag .lbl     { font-size:.62rem; font-weight:400; opacity:.7;  display:block; margin-top:3px; font-style:italic; }

.t-pos   { background:#17273f; border:1px solid #2471a3; color:#85c1e9; }
.t-moeda { background:#1f2b17; border:1px solid #1e8449; color:#a9dfbf; }
.t-dur   { background:#2a2015; border:1px solid #b7770d; color:#f0b27a; }
.t-rv    { background:#1f1530; border:1px solid #7d3c98; color:#d2b4de; }
.t-fdo   { background:#1a2a2a; border:1px solid #148f77; color:#76d7c4; }
.t-prov  { background:#2a1515; border:1px solid #a93226; color:#f1948a; }
.t-fus   { background:#1a1a2a; border:1px solid #6a5acd; color:#b0a4e3; }

.ftable { width:100%; border-collapse:collapse; font-size:.72rem; }
.ftable th { background:#1e2030; color:#aaa; padding:5px 8px; text-align:left; font-weight:600; border-bottom:1px solid #333; white-space:nowrap; }
.ftable td { padding:5px 8px; border-bottom:1px solid #1e1e1e; color:#ddd; }
.ftable td code { font-family:'Consolas',monospace; color:#ce9178; font-size:.7rem; }
.ftable tr:hover td { background:#1a1f2e; }

.legend        { display:flex; gap:16px; flex-wrap:wrap; justify-content:center; margin-top:36px; font-size:.72rem; color:#aaa; }
.legend-item   { display:flex; align-items:center; gap:6px; }
.legend-dot    { width:12px; height:12px; border-radius:3px; flex-shrink:0; }

/* TO DO PANEL */
.todo-panel {
  background: #13151c;
  border: 1.5px solid #2a2d3e;
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.todo-header { display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; }
.todo-title  { font-size:1rem; font-weight:700; color:#fff; }
.todo-counter { font-size:.7rem; color:#888; background:#1e2030; padding:3px 8px; border-radius:12px; }
.todo-progress-wrap { background:#1e2030; border-radius:4px; height:6px; overflow:hidden; }
.todo-progress-fill { height:100%; background:linear-gradient(90deg,#27ae60,#2ecc71); border-radius:4px; transition:width .35s ease; }
.todo-section-title { font-size:.7rem; font-weight:700; text-transform:uppercase; letter-spacing:.06em; color:#555; margin-bottom:6px; }

.todo-list { display:flex; flex-direction:column; gap:4px; max-height:340px; overflow-y:auto; padding-right:2px; }
.todo-list::-webkit-scrollbar { width:4px; }
.todo-list::-webkit-scrollbar-thumb { background:#333; border-radius:4px; }

.todo-item { display:flex; align-items:flex-start; gap:6px; padding:6px 8px; border-radius:6px; background:#1a1d28; border:1px solid #252840; transition:background .15s; }
.todo-item:hover { background:#1e2235; }
.todo-item.todo-done .todo-text { opacity:.45; text-decoration:line-through; }
.todo-check { display:flex; align-items:flex-start; gap:7px; flex:1; cursor:pointer; min-width:0; }
.todo-check input[type=checkbox] { margin-top:2px; flex-shrink:0; accent-color:#27ae60; width:14px; height:14px; cursor:pointer; }
.todo-text  { font-size:.74rem; color:#d0d0d0; line-height:1.45; word-break:break-word; }
.todo-edit-input { font-size:.74rem; color:#e0e0e0; background:#0f1117; border:1px solid #2980b9; border-radius:4px; padding:2px 6px; flex:1; min-width:0; outline:none; }
.todo-del { background:none; border:none; color:#444; cursor:pointer; font-size:.72rem; padding:0 2px; flex-shrink:0; line-height:1; transition:color .15s; }
.todo-del:hover { color:#e74c3c; }

.todo-add { display:flex; gap:6px; }
.todo-input { flex:1; background:#1a1d28; border:1px solid #2a2d3e; border-radius:6px; color:#e0e0e0; padding:6px 10px; font-size:.74rem; outline:none; transition:border-color .15s; }
.todo-input:focus { border-color:#2980b9; }
.todo-input::placeholder { color:#3a3d50; }
.todo-add-btn { background:#1e4a30; border:1px solid #27ae60; color:#2ecc71; border-radius:6px; width:32px; font-size:1.1rem; cursor:pointer; transition:background .15s; flex-shrink:0; }
.todo-add-btn:hover { background:#27ae60; color:#fff; }

.todo-notes { width:100%; min-height:110px; background:#1a1d28; border:1px solid #2a2d3e; border-radius:6px; color:#d0d0d0; padding:8px 10px; font-size:.74rem; font-family:'Segoe UI',Arial,sans-serif; resize:vertical; outline:none; line-height:1.55; transition:border-color .15s; }
.todo-notes:focus { border-color:#2980b9; }
.todo-notes::placeholder { color:#3a3d50; }
.todo-reset-btn { background:none; border:1px solid #2a2d3e; color:#555; border-radius:6px; padding:5px 10px; font-size:.68rem; cursor:pointer; transition:color .15s,border-color .15s; align-self:flex-end; }
.todo-reset-btn:hover { color:#aaa; border-color:#555; }
"""


# ── JavaScript ────────────────────────────────────────────────────────────────

TODO_JS_TEMPLATE = """
<script>
(function() {
  var STORAGE_KEY = 'todo_load337_v1';
  var DEFAULT_ITEMS = __DATA__;

  function clone(x) { return JSON.parse(JSON.stringify(x)); }

  function loadState() {
    try {
      var s = localStorage.getItem(STORAGE_KEY);
      if (s) return JSON.parse(s);
    } catch(e) {}
    return { items: clone(DEFAULT_ITEMS), notes: '' };
  }

  function saveState() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  var state = loadState();

  function renderTodo() {
    var list    = document.getElementById('todo-list');
    var notesEl = document.getElementById('todo-notes');
    var counter = document.getElementById('todo-counter');
    var fill    = document.getElementById('todo-progress');

    var done  = state.items.filter(function(i) { return i.done; }).length;
    var total = state.items.length;
    if (counter) counter.textContent = done + '/' + total + ' concluidos';
    if (fill)    fill.style.width = (total ? (done / total * 100) : 0) + '%';
    if (notesEl && notesEl !== document.activeElement) notesEl.value = state.notes || '';

    if (!list) return;
    list.innerHTML = '';

    state.items.forEach(function(item, idx) {
      var div   = document.createElement('div');
      div.className = 'todo-item' + (item.done ? ' todo-done' : '');

      var label = document.createElement('label');
      label.className = 'todo-check';

      var cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = item.done;
      (function(i) { cb.addEventListener('change', function() { toggleItem(i); }); })(idx);

      var span = document.createElement('span');
      span.className = 'todo-text';
      span.textContent = item.text;
      (function(i, sp) { sp.addEventListener('dblclick', function() { editItem(i, sp); }); })(idx, span);

      var del = document.createElement('button');
      del.className = 'todo-del';
      del.title = 'Remover';
      del.textContent = 'x';
      (function(i) { del.addEventListener('click', function() { deleteItem(i); }); })(idx);

      label.appendChild(cb);
      label.appendChild(span);
      div.appendChild(label);
      div.appendChild(del);
      list.appendChild(div);
    });
  }

  function toggleItem(idx) {
    state.items[idx].done = !state.items[idx].done;
    saveState(); renderTodo();
  }

  function deleteItem(idx) {
    state.items.splice(idx, 1);
    saveState(); renderTodo();
  }

  function editItem(idx, spanEl) {
    var orig = state.items[idx].text;
    var inp  = document.createElement('input');
    inp.type = 'text';
    inp.value = orig;
    inp.className = 'todo-edit-input';
    spanEl.replaceWith(inp);
    inp.focus(); inp.select();
    var committed = false;
    function commit() {
      if (committed) return; committed = true;
      var v = inp.value.trim();
      if (v) state.items[idx].text = v;
      saveState(); renderTodo();
    }
    inp.addEventListener('blur', commit);
    inp.addEventListener('keydown', function(e) {
      if (e.key === 'Enter')  commit();
      if (e.key === 'Escape') { inp.value = orig; commit(); }
    });
  }

  window.addItem = function() {
    var inp  = document.getElementById('new-item-input');
    if (!inp) return;
    var text = inp.value.trim();
    if (!text) return;
    state.items.push({ id: 'u' + Date.now(), text: text, done: false });
    inp.value = '';
    saveState(); renderTodo();
    var list = document.getElementById('todo-list');
    if (list) list.scrollTop = list.scrollHeight;
  };

  window.resetTodo = function() {
    if (confirm('Restaurar lista padrao? Suas alteracoes serao perdidas.')) {
      state = { items: clone(DEFAULT_ITEMS), notes: '' };
      saveState(); renderTodo();
    }
  };

  document.addEventListener('DOMContentLoaded', function() {
    renderTodo();
    var ni = document.getElementById('new-item-input');
    if (ni) ni.addEventListener('keydown', function(e) { if (e.key === 'Enter') window.addItem(); });
    var tn = document.getElementById('todo-notes');
    if (tn) tn.addEventListener('input', function() { state.notes = tn.value; saveState(); });
  });
})();
</script>
"""


# ── montagem HTML ─────────────────────────────────────────────────────────────


def build_todo_panel():
    return (
        '<div class="todo-panel">'
        '<div class="todo-header">'
        '<span class="todo-title">&#x1F4CB; To Do</span>'
        '<span id="todo-counter" class="todo-counter">0/0 concluidos</span>'
        "</div>"
        '<div class="todo-progress-wrap">'
        '<div id="todo-progress" class="todo-progress-fill" style="width:0%"></div>'
        "</div>"
        "<div>"
        '<div class="todo-section-title">Tarefas</div>'
        '<div id="todo-list" class="todo-list"></div>'
        "</div>"
        '<div class="todo-add">'
        '<input id="new-item-input" type="text" class="todo-input"'
        ' placeholder="Nova tarefa... (Enter para adicionar)">'
        '<button onclick="addItem()" class="todo-add-btn" title="Adicionar">+</button>'
        "</div>"
        "<div>"
        '<div class="todo-section-title">&#x1F4DD; Detalhes / Notas</div>'
        '<textarea id="todo-notes" class="todo-notes"'
        ' placeholder="Observacoes, contexto ou pendencias detalhadas..."></textarea>'
        "</div>"
        '<button onclick="resetTodo()" class="todo-reset-btn">&#x21BA; Restaurar padrao</button>'
        "</div>"
    )


def build_html():
    sections = [
        '<div class="node oval c-start">&#x25B6; INICIO</div>',
        arrow(),
        bloco_init(),
        arrow(),
        bloco_string_builders(),
        arrow(),
        bloco_queries(),
        arrow(),
        bloco_clear(),
        arrow(),
        bloco_connect(),
        arrow(),
        bloco_prv(),
        arrow(),
        bloco_exec_queries(),
        arrow(),
        bloco_formulas(),
        arrow(),
        bloco_autofilter(),
        arrow(),
        bloco_restore(),
        arrow(),
        '<div class="node oval c-end">&#x25A0; FIM</div>',
    ]
    flow = "\n".join(sections)
    data_json = json.dumps(TODO_ITEMS, ensure_ascii=False)
    todo_js = TODO_JS_TEMPLATE.replace("__DATA__", data_json)

    return (
        "<!DOCTYPE html>\n"
        '<html lang="pt-BR">\n'
        "<head>\n"
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        "<title>Fluxograma - Load_DADOS337</title>\n"
        "<style>" + CSS + "</style>\n"
        "</head>\n"
        "<body>\n"
        "<h1>Fluxograma &mdash; Sub Load_DADOS337()</h1>\n"
        '<div class="subtitle">VBA &middot; Exposicao Beta V20.xlsm &middot; dbsx337</div>\n'
        '<div class="page-layout">\n'
        '  <div class="flow-col">\n'
        '    <div class="flow">\n'
        + flow + "\n"
        "    </div>\n"
        "    " + bloco_legend() + "\n"
        "  </div>\n"
        '  <div class="todo-col">\n'
        "    " + build_todo_panel() + "\n"
        "  </div>\n"
        "</div>\n"
        + todo_js + "\n"
        "</body>\n"
        "</html>"
    )


# ── entry point ───────────────────────────────────────────────────────────────


def main():
    out = Path(__file__).parent / "fluxograma_load_dados337.html"
    out.write_text(build_html(), encoding="utf-8")
    print(f"Gerado: {out}")


if __name__ == "__main__":
    main()
