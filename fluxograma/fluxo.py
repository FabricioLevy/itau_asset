


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

CAT_COLOR = dict(zip(CAT_CSS.keys(), [cor for cor, _ in LEGEND_ITEMS]))

TODO_ITEMS_VBA = [
    {"id": "t1",  "text": "Conectar ao banco via ADODB (Call sSQL_Connect -> dbsx337)", "done": False},
    {"id": "t2",  "text": "Executar as 25 queries e escrever resultados no workbook", "done": False},
    {"id": "t3",  "text": "Inserir formulas: PL consolidado, cambio, DU, caixa exterior", "done": False},
    {"id": "t4", "text": "Aplicar AutoFilter no Relatorio (campo 29, >100.1% ou <99.99%)", "done": False},
    {"id": "t5", "text": "Validar queries de moedas com novas fontes BBG FX", "done": False},
    {"id": "t6", "text": "Testar bloco PRV com fundos FICAD_CD adicionados recentemente", "done": False},
    {"id": "t7", "text": "Documentar estrutura das colunas da planilha PRM", "done": False},
]

TODO_ITEMS_PY = [
    {"id": "p1", "text": "Definir estrutura do script Python", "done": False},
    {"id": "p2", "text": "Mapear entradas e saidas do calculo", "done": False},
    {"id": "p3", "text": "Implementar conexao com banco de dados", "done": False},
]

TODO_ITEMS_FE = [
    {"id": "f1", "text": "Definir estrutura do front end", "done": False},
    {"id": "f2", "text": "Mapear paginas e componentes", "done": False},
    {"id": "f3", "text": "Integrar com dados do back end", "done": False},
]

TODO_ITEMS_GRAFICOS = [
    {"id": "gr1", "text": "Definir estrutura de graficos por fundo", "done": False},
    {"id": "gr2", "text": "Mapear series de dados e periodos", "done": False},
    {"id": "gr3", "text": "Implementar visualizacoes interativas", "done": False},
]

TODO_ITEMS_BATIMENTO = [
    {"id": "b1", "text": "Validar triagem macro: fundos indexados com |Delta| >= 0.5 bps", "done": False},
    {"id": "b2", "text": "Testar batimentos paralelos (joblib) para todas as 7 classes", "done": False},
    {"id": "b3", "text": "Confirmar mapeamento de causas: queries diagnostico por (causa, classe)", "done": False},
    {"id": "b4", "text": "Verificar aba Como_Corrigir: scripts RunProject corretos para cada causa", "done": False},
    {"id": "b5", "text": "Validar 10 analises sequenciais (precos, PnL esperado, carrego RF...)", "done": False},
    {"id": "b6", "text": "Testar integracao OC3: patrimonio, RF, RV, futuros, swap, caixa", "done": False},
    {"id": "b7", "text": "Confirmar saida Excel: 19 abas geradas corretamente por fundo", "done": False},
]

TODO_ITEMS_PJ = [
    {"id": "pj1", "text": "Validar gerar_preco_justo_etfRF: cupom + PU careca + taxa ponderada", "done": False},
    {"id": "pj2", "text": "Testar GOAT11: posicao RV + BTC + caixa via Bloomberg", "done": False},
    {"id": "pj3", "text": "Verificar T10R11: yield = CTD + CDI - Fed Funds (vencimento dinamico)", "done": False},
    {"id": "pj4", "text": "Validar etfSelic (CDIB11/LFTI11): accrual CDI diario para LFTI11", "done": False},
    {"id": "pj5", "text": "Confirmar restricao horaria: 10:15 - 18:00", "done": False},
    {"id": "pj6", "text": "Testar saida CSV: delimitador ; decimal , sem NAs", "done": False},
]

TODO_ITEMS_OFFSHORE = [
    {"id": "off1", "text": "Validar lista_fundos offshore: nomes exatos em SISTEMAS_SSC_PED_INTRADAY", "done": False},
    {"id": "off2", "text": "Testar mapeamento de_para_dict: todos os tipos SSC cobertos", "done": False},
    {"id": "off3", "text": "Confirmar threshold arred=1: diferencas < R$1 ignoradas", "done": False},
    {"id": "off4", "text": "Validar distribuicao de PnL por estrategia (est1-est5): proporcional por qtd", "done": False},
    {"id": "off5", "text": "Testar tratamento posicao zerada com multiplas estrategias (divisao igual)", "done": False},
    {"id": "off6", "text": "Verificar aba VerificarPnL: ativos sem estrategia mapeada (VERIFICAR)", "done": False},
    {"id": "off7", "text": "Confirmar saida Excel: 5 abas + frozen panes + path output/batimento_off/", "done": False},
]

TODO_ITEMS_OC3 = [
    {"id": "oc1", "text": "Validar codigos SAC dos fundos: lista_fundos no formato correto (FICFI...)", "done": False},
    {"id": "oc2", "text": "Testar conexao OC3(): nova instancia por fundo (evitar estado acumulado)", "done": False},
    {"id": "oc3", "text": "Verificar as 27 consultas: todas retornando dados ou vazio gracioso", "done": False},
    {"id": "oc4", "text": "Confirmar filtros por fundo: ativo_cotas, pos_fi_patr, cpr filtram por COD_CLI", "done": False},
    {"id": "oc5", "text": "Testar saida Excel: 27 abas por fundo, path output/batimento_oc3/{yyyymmdd}/", "done": False},
    {"id": "oc6", "text": "Validar conversao ADO Recordset -> DataFrame (_recordset_to_df)", "done": False},
]

# ── dados Sub Alerta ──────────────────────────────────────────────────────────

ALERTA_RANGES = [
    ("A8:M34",    "SINGLES"),
    ("A36:M52",   "IBOV"),
    ("A54:M74",   "ETFs"),
    ("A77:M87",   "S&P500"),
    ("A90:M109",  "OFFSHORES & WRAPPERS"),
    ("A113:M116", "MOEDAS"),
    ("A119:M172", "RENDA FIXA"),
    ("A175:M178", "OURO E TREASURY"),
    ("A181:M181", "DEBENTURES"),
    ("A184:M184", "ACWI"),
    ("A186:M192", "CDI"),
]

ALERTA_CHECKS = [
    # (variavel, col_leitura, col_colorir, descricao)
    ("check1", "col 19 (S)", "col 4 (D)",  "Desvio 1"),
    ("check2", "col 22 (V)", "col 7 (G)",  "Desvio 2"),
    ("check3", "col 25 (Y)", "col 8 (H)",  "Desvio 3"),
    ("check4", "col 28 (AB)","col 9 (I)",  "Desvio 4"),
    ("check5", "col 31 (AE)","col 13 (M)", "Desvio 5"),
]

TODO_ITEMS_ALERTA = [
    {"id": "a1", "text": "Validar colunas de check no Design (cols 19,22,25,28,31)", "done": False},
    {"id": "a2", "text": "Confirmar range do loop: linhas 8 a 189", "done": False},
    {"id": "a3", "text": "Testar copia de alertas para aba Alerta", "done": False},
    {"id": "a4", "text": "Verificar logica de agrupamento por categoria (col 14)", "done": False},
]

# ── dados futuros.py ─────────────────────────────────────────────────────────

FUT_QUERIES = [
    ("consulta_futuro_fut", "view_vcrapfut", "Notional / dt_vencto / ativo", "pos", "Futuros: notional e vencimentos"),
    ("consulta_futuro_pl",  "view_vcraplsi", "vl_patrliqtot1 por fundo",     "pos", "PL por fundo"),
]

FUT_COMPUTED_COLS = [
    ("Pos V1 % PL", "not_v1 / PL",        "Posicao vencimento front sobre PL"),
    ("Pos V2 % PL", "not_v2 / PL",        "Posicao vencimento back sobre PL"),
    ("V1 % FUT",    "not_v1 / total_fut", "Percentual front no total do futuro"),
    ("V2 % FUT",    "not_v2 / total_fut", "Percentual back no total do futuro"),
]

FUT_OUTPUTS = [
    ("gerar_imagem",      "matplotlib", "rolagem_{grupo}_{dt}.png", "pos",  "Imagem por grupo com tabela e header Itau"),
    ("gerar_excel_dados", "openpyxl",   "rolagem_{dt}.xlsx",        "fdo",  "Excel com abas por grupo, zebra e formatos"),
]

TODO_ITEMS_FUT = [
    {"id": "u1", "text": "Validar codigos MES_CODIGO (CME: F,G,H,J,K,M,N,Q,U,V,X,Z)", "done": False},
    {"id": "u2", "text": "Confirmar filtro ano_ref: apenas contratos do ano corrente", "done": False},
    {"id": "u3", "text": "Testar processar_grupo para DOL_WDO combinado", "done": False},
    {"id": "u4", "text": "Verificar saida Excel: formatacao verde/vermelho nos percentuais", "done": False},
]

FUT_SQL = {
    "consulta_futuro_fut": """\
SELECT clcli_cd,
       ISNULL(qt,0)*ISNULL(vl_varponto,0)*ISNULL(vl_precomerc,0) AS Notional,
       dt_vencto,
       fuvct_fuatv_cd
FROM   dbsx337.dbo.view_vcrapfut WITH(NOLOCK)
WHERE  dt = '{dt}'
  AND  clcli_cd IN ({fundos})
-- Notional = qt x vl_varponto x vl_precomerc
-- Vencimento formatado: MES_CODIGO[month] + ano[-2:]
--   ex: abril/2025 -> 'J25'""",

    "consulta_futuro_pl": """\
SELECT clcli_cd,
       vl_patrliqtot1 AS PL
FROM   dbsx337.dbo.view_vcraplsi WITH(NOLOCK)
WHERE  dt = '{dt}'
  AND  clcli_cd IN ({fundos})""",
}

# ── dados Python (exposicao.py) ───────────────────────────────────────────────

PY_SHEETS = [
    "SINGLES", "IBOV", "ETFs", "S&P500", "OFFSHORES",
    "MOEDAS", "RENDA FIXA", "OURO e TREASURY", "DEBENTURES", "ACWI", "CDI",
]

PY_QUERIES = [
    # (funcao, fonte, retorno, categoria, descricao)
    ("buscar_fx",           "fundos_dados_moedas / FUNDOS_DADOS_INDICES", "USD / GBP / EUR / CNY",      "moeda", "Taxas de cambio"),
    ("buscar_pl",           "view_vcraplsi",                              "vl_patrliqtot1 por fundo",   "pos",   "Patrimonio Liquido"),
    ("buscar_prv",          "VIEW_vcraprv + VIEW_VCRABTC",               "qty x preco (com FX)",       "rv",    "Acoes RV + Aluguel BTC"),
    ("buscar_futuro",       "view_vcrapfut",                              "qt x varponto x precomerc",  "pos",   "Futuros notional / DU DI1"),
    ("buscar_cotas",        "view_vcrapfdo (vl_liq)",                     "SUM(vl_liq) por fundo",      "fdo",   "Cotas de fundos"),
    ("buscar_proventos",    "view_vcraprdp (mttp 61,62,69,261...)",       "SUM(vl) por fundo",          "prov",  "Proventos RV"),
    ("buscar_pibb11_spxi11","VIEW_vcraprv (PIBB11, SPXI11)",              "SUM(qty x preco) BRL",       "fus",   "ETFs S&P500 (aba especial)"),
    ("buscar_fut_sp_usd",   "view_vcrapfut (ISP/WSP/DOL/WDO/BRI)",       "sp + usd por fundo",         "pos",   "Futuros S&P vs USD hedge"),
]

PY_FORMULAS = [
    ("%ACOES",        "prv_brl / PL",                         "Exposicao acoes com cambio"),
    ("%FUT",          "notional / PL",                        "Exposicao futuros"),
    ("%COTAS",        "SUM(vl_liq) / PL",                     "Exposicao cotas de fundos"),
    ("TOTAL",         "%ACOES + %FUT + %COTAS",               "Exposicao total"),
    ("DESC",          "1 - TOTAL",                            "Descasamento em relacao a 100%"),
    ("Proventos %PL", "SUM(proventos) / PL",                  "Proventos sobre PL"),
    ("EXP S&P",       "(prv - PIBB11 + sp_fut) / PL",         "Logica especial aba S&P500"),
    ("EXP USD",       "SUM(DOL + WDO + BRI) / PL",           "Overlay cambial S&P500"),
    ("PIBB+SPXI",     "(PIBB11 + SPXI11) / PL",              "ETFs S&P500 combinados"),
]

PY_OUTPUTS = [
    ("exportar_excel", "openpyxl",  "exposicao_{dt}.xlsx", "pos",   "Relatorio com cores e formatos numericos"),
    ("gerar_html",     "built-in",  "exposicao_{dt}.html", "fdo",   "Relatorio navegavel com abas e busca"),
    ("gerar_pdf",      "fpdf2",     "exposicao_{dt}.pdf",  "dur",   "PDF com bookmarks por aba (landscape A4)"),
]

VBA_SQL = {
    "sql_VCRAPLSI": """\
SELECT clcli_cd,
       vl_patrliqtot1 AS PL
FROM   dbsx337.dbo.view_vcraplsi WITH (NOLOCK)
WHERE  dt = '{dt_planilha}'
  AND  clcli_cd IN ({string_builder})""",

    "sql_VCRAPRF": """\
SELECT clcli_cd, papct_cd, papct_nm,
       mrc_cd, vl_mercado, vl_mercado_liq,
       dt_vencto, duration_mod, taxa_negocio
FROM   dbsx337.dbo.view_vcraprf WITH (NOLOCK)
WHERE  dt = '{dt_planilha}'
  AND  clcli_cd IN ({string_builder})""",

    "sql_VCRAPRDP": """\
SELECT clcli_cd, mttp_cd, papct_cd,
       vl, vl_bruto
FROM   dbsx337.dbo.view_vcraprdp WITH (NOLOCK)
WHERE  dt = '{dt_planilha}'
  AND  clcli_cd IN ({string_builder})
  AND  mttp_cd NOT IN ('251','986','987')""",

    "sql_SALDO_TESOURARIA": """\
SELECT clcli_cd,
       SUM(vl) AS SALDO_TESOURARIA
FROM   dbsx337.dbo.view_vcraprdp WITH (NOLOCK)
WHERE  dt = '{dt_planilha}'
  AND  clcli_cd IN ({string_builder})
  AND  mttp_cd = '251'
GROUP BY clcli_cd""",

    "sql_COTAS": """\
SELECT clcli_cd,
       SUM(vl_liq) AS COTAS
FROM   dbsx337.dbo.view_vcrapfdo WITH (NOLOCK)
WHERE  dt = '{dt_planilha}'
  AND  clcli_cd IN ({string_builder})
GROUP BY clcli_cd""",

    "sql_FUTURO": """\
SELECT clcli_cd,
       fuvct_fuatv_cd  AS ATIVO,
       qt,
       vl_varponto,
       vl_precomerc,
       dt_vencto
FROM   dbsx337.dbo.view_vcrapfut WITH (NOLOCK)
WHERE  dt = '{dt_planilha}'
  AND  clcli_cd IN ({string_builder})""",

    "sql_BMFXTWO": """\
SELECT TOP 1 preco_limpo AS USD_BRL
FROM   dbsx337.dbo.fundos_dados_moedas WITH (NOLOCK)
WHERE  date = '{dt_planilha}'
  AND  codigo_iam_moeda_base  = 'BRL_B3_2'
  AND  codigo_iam_moeda_quote = 'USD'""",

    "sql_GBP16H": """\
SELECT TOP 1 preco_limpo AS GBP_BRL
FROM   dbsx337.dbo.fundos_dados_moedas WITH (NOLOCK)
WHERE  date = '{dt_planilha}'
  AND  codigo_iam_moeda_base  = 'BRL_B3_2'
  AND  codigo_iam_moeda_quote = 'GBP'""",

    "sql_EURO": """\
SELECT TOP 1 preco_limpo AS EUR_BRL
FROM   dbsx337.dbo.fundos_dados_moedas WITH (NOLOCK)
WHERE  date = '{dt_planilha}'
  AND  codigo_iam_moeda_base  = 'BRL_B3_2'
  AND  codigo_iam_moeda_quote = 'EUR'""",

    "sql_CNY": """\
SELECT TOP 1 preco_limpo AS CNYXBR10
FROM   dbsx337.dbo.FUNDOS_DADOS_INDICES WITH (NOLOCK)
WHERE  date = '{dt_planilha}'
  AND  codigo_iam_indice = 'CNYXBR10'""",

    "sql_CC_EXTERIOR": """\
SELECT clcli_cd,
       SUM(vl_total) AS CAIXA_EXTERIOR
FROM   dbsx337.dbo.view_vcrapfdo WITH (NOLOCK)
WHERE  dt = '{dt_planilha}'
  AND  clcli_cd IN ({string_builder})
GROUP BY clcli_cd""",

    "sql_PRFABERTO": """\
SELECT clcli_cd, papct_cd, papct_nm,
       mrc_cd, vl_mercado, dt_vencto
FROM   dbsx337.dbo.view_vcraprf WITH (NOLOCK)
WHERE  dt = '{dt_planilha}'
  AND  clcli_cd IN ({string_builder})
  AND  papct_cd IN (
         'NTN-B','NTN-F','LTN','DEBIN'
       )""",

    "sql_swap": """\
SELECT clcli_cd,
       papct_cd,
       mrc_cd       AS PONTA,   -- A=ativo / P=passivo
       vl_mercado   AS VL_MERCADO,
       dt_vencto
FROM   dbsx337.dbo.view_vcrapswp WITH (NOLOCK)
WHERE  dt = '{dt_planilha}'
  AND  clcli_cd IN ({string_builder})""",

    "sql_duration": """\
SELECT clcli_cd, papct_cd, papct_nm,
       qt_total, vl_pu,
       duration_mod AS DURATION,
       vl_mercado
FROM   dbsx337.dbo.view_vcraprf WITH (NOLOCK)
WHERE  dt = '{dt_planilha}'
  AND  clcli_cd IN ({string_builder})""",

    "sql_indexduration": """\
SELECT codigo_iam_indice,
       duration
FROM   dbsx337.dbo.tbhh3031_anbima_indices WITH (NOLOCK)
WHERE  date = '{dt_planilha}'""",

    "sql_dolarcupomlimpo": """\
SELECT TOP 1 preco_limpo AS USD_CUPOM_LIMPO
FROM   dbsx337.dbo.fundos_dados_moedas WITH (NOLOCK)
WHERE  date = '{dt_planilha}'
  AND  codigo_iam_moeda_base  = 'BRL_B3_CL'
  AND  codigo_iam_moeda_quote = 'USD'""",

    "sql_cotacoesvsusd": """\
SELECT TOP 1 value AS GBPUSD
FROM   dbsx337.dbo.bbg_fx WITH (NOLOCK)
WHERE  date   = '{dt_planilha}'
  AND  ticker = 'GBPUSD F150'""",

    "sql_eurousd": """\
SELECT TOP 1 value AS EURUSD
FROM   dbsx337.dbo.bbg_fx WITH (NOLOCK)
WHERE  date   = '{dt_planilha}'
  AND  ticker = 'EURUSD F150'""",

    "proventos": """\
SELECT clcli_cd, papct_cd,
       mttp_cd, SUM(vl) AS PROVENTOS
FROM   dbsx337.dbo.view_vcraprdp WITH (NOLOCK)
WHERE  dt = '{dt_planilha}'
  AND  clcli_cd IN ({string_builderrv})
  AND  mttp_cd IN ('61','62','69','261')
GROUP BY clcli_cd, papct_cd, mttp_cd""",

    "moedas": """\
SELECT date, ticker, value
FROM   dbsx337.dbo.bbg_fx WITH (NOLOCK)
WHERE  date   = '{dt_planilha}'
  AND  ticker IN (
         'ADU3','CDU3','ECU3','JYU3'
       )""",

    "sql_COTAS_quebradas": """\
SELECT clcli_cd, FICAD_CD,
       SUM(vl_liq) AS VL_COTAS
FROM   dbsx337.dbo.view_vcrapfdo WITH (NOLOCK)
WHERE  dt = '{dt_planilha}'
  AND  clcli_cd IN ({string_builderCOTAS})
GROUP BY clcli_cd, FICAD_CD""",

    "sql_FUSION": """\
SELECT clcli_cd, ticker_bolsa,
       vl_total AS VL_FUSION
FROM   dbsx337.dbo.VieW_FUNDOS_POSICAO WITH (NOLOCK)
WHERE  date = '{dt_planilha}'
  AND  ticker_bolsa = 'FUSION57691'
  AND  clcli_cd IN ({string_builder})""",

    "consulta_fut": """\
SELECT clcli_cd,
       fuvct_fuatv_cd AS ATIVO,
       fuvct_cd,
       qt,
       dt_vencto
FROM   dbsx337.dbo.view_vcrapfut WITH (NOLOCK)
WHERE  dt = '{dt_planilha}'
  AND  clcli_cd IN ({string_builder})
ORDER BY fuvct_fuatv_cd, dt_vencto""",

    "sql_pfdo": """\
SELECT clcli_cd, FICAD_CD,
       TIPO_CLASSIF,
       SUM(vl_liq) AS VL_LIQ
FROM   dbsx337.dbo.view_vcrapfdo WITH (NOLOCK)
WHERE  dt = '{dt_planilha}'
  AND  clcli_cd IN ({string_builder})
GROUP BY clcli_cd, FICAD_CD, TIPO_CLASSIF""",

    "consulta_teva": """\
SELECT codigo_iam_indice,
       ticker,
       peso
FROM   dbsx337.dbo.FUNDOS_COMPOSICAO_INDICES WITH (NOLOCK)
WHERE  date = '{dt_planilha}'
  AND  codigo_iam_indice = 'ITBR_5_PRE'""",
}

PY_SQL = {
    "buscar_fx": """\
-- USD / GBP / EUR  (fundos_dados_moedas)
SELECT TOP 1 preco_limpo
FROM   dbsx337.dbo.fundos_dados_moedas WITH (NOLOCK)
WHERE  date = '{dt}'
  AND  codigo_iam_moeda_base  = 'BRL_B3_2'
  AND  codigo_iam_moeda_quote = '{quote}'   -- USD | GBP | EUR

-- CNY  (FUNDOS_DADOS_INDICES)
SELECT TOP 1 preco_limpo
FROM   dbsx337.dbo.FUNDOS_DADOS_INDICES WITH (NOLOCK)
WHERE  date = '{dt}'
  AND  codigo_iam_indice = 'CNYXBR10'""",

    "buscar_pl": """\
SELECT clcli_cd, vl_patrliqtot1 AS PL
FROM   dbsx337.dbo.view_vcraplsi WITH (NOLOCK)
WHERE  dt = '{dt}'
  AND  clcli_cd IN ({fundos})""",

    "buscar_prv": """\
-- 1. Quantidades e preco  (VIEW_vcraprv)
SELECT clcli_cd               AS FUNDO,
       acao                   AS ACAO,
       SUM(qtdbloq)           AS QTDBLOQ,
       SUM(qtddisp)           AS QTDDISP,
       MAX(vl_preco_mercmedio) AS PRECO
FROM   DBSX337.dbo.VIEW_vcraprv WITH (NOLOCK)
WHERE  dt = '{dt}'
  AND  clcli_cd IN ({fundos})
GROUP BY clcli_cd, acao

-- 2. Moeda por ticker  (VIEW_FUNDOS_POSICAO)
SELECT ticker_bolsa     AS ACAO,
       MAX(moeda_ativo) AS MOEDA
FROM   DBSX337.dbo.VIEW_FUNDOS_POSICAO WITH (NOLOCK)
WHERE  date = '{dt}'
  AND  tipo = 'Equity'
GROUP BY ticker_bolsa

-- 3. Aluguel BTC  (VIEW_VCRABTC)
SELECT CLCLI_CD AS FUNDO,
       CODPAP   AS ACAO,
       SUM(CASE
             WHEN IC_TIPO_MOVIMENTO = 'Doador'  THEN  QUANTIDADE
             WHEN IC_TIPO_MOVIMENTO = 'Tomador' THEN -QUANTIDADE
             ELSE QUANTIDADE
           END) AS QTD_BTC
FROM   dbsx337.dbo.VIEW_VCRABTC WITH (NOLOCK)
WHERE  dt = '{dt}'
  AND  CLCLI_CD IN ({fundos})
GROUP BY CLCLI_CD, CODPAP""",

    "buscar_futuro": """\
SELECT clcli_cd        AS FUNDO,
       qt,
       vl_varponto,
       vl_precomerc,
       fuvct_fuatv_cd  AS ATIVO,
       dt_vencto
FROM   dbsx337.dbo.view_vcrapfut WITH (NOLOCK)
WHERE  dt = '{dt}'
  AND  clcli_cd IN ({fundos})
-- NOTIONAL = qt * vl_varponto * vl_precomerc
-- FUT DI1  = qt * NETWORKDAYS(dt_ref, dt_vencto)""",

    "buscar_cotas": """\
SELECT clcli_cd AS FUNDO,
       SUM(vl_liq) AS COTAS
FROM   dbsx337.dbo.view_vcrapfdo WITH (NOLOCK)
WHERE  dt = '{dt}'
  AND  clcli_cd IN ({fundos})
GROUP BY clcli_cd""",

    "buscar_proventos": """\
SELECT clcli_cd AS FUNDO,
       SUM(vl)  AS PROVENTOS
FROM   dbsx337.dbo.view_vcraprdp WITH (NOLOCK)
WHERE  dt = '{dt}'
  AND  clcli_cd IN ({fundos})
  AND  mttp_cd IN (
         '61','62','69','261',
         '848','849','971','972','973'
       )
GROUP BY clcli_cd""",

    "buscar_pibb11_spxi11": """\
SELECT clcli_cd AS FUNDO,
       acao      AS TICKER,
       SUM((qtdbloq + qtddisp) * vl_preco_mercmedio) AS VALOR_BRL
FROM   DBSX337.dbo.VIEW_vcraprv WITH (NOLOCK)
WHERE  dt = '{dt}'
  AND  clcli_cd IN ({fundos})
  AND  acao IN ('PIBB11', 'SPXI11')
GROUP BY clcli_cd, acao""",

    "buscar_fut_sp_usd": """\
SELECT clcli_cd       AS FUNDO,
       fuvct_fuatv_cd AS ATIVO,
       SUM(qt * vl_varponto * vl_precomerc) AS NOTIONAL
FROM   dbsx337.dbo.view_vcrapfut WITH (NOLOCK)
WHERE  dt = '{dt}'
  AND  clcli_cd IN ({fundos})
  AND  fuvct_fuatv_cd IN (
         'FUT ISP', 'FUT WSP',          -- S&P futuros
         'FUT DOL', 'FUT WDO', 'FUT BRI' -- USD hedge
       )
GROUP BY clcli_cd, fuvct_fuatv_cd""",
}


# ── dados Batimento Diário ────────────────────────────────────────────────────

BATIMENTO_CLASSES = [
    # (funcao, fonte_vcra, fonte_lake, cat, descricao)
    ("batimento_pnl_acao",      "VCRAPRV",  "VW_FUNDOS_POSICAO (Equity)",       "rv",  "Acoes RV"),
    ("batimento_pnl_rf",        "VCRAPRF",  "VW_FUNDOS_POSICAO (Fixed Income)", "dur", "Renda Fixa"),
    ("batimento_pnl_futuro",    "VCRAPFUT", "VW_FUNDOS_POSICAO (Futures)",      "pos", "Futuros"),
    ("batimento_pnl_fund_fidc", "VCRAPFDO", "VW_FUNDOS_POSICAO (Fund/FIDC)",    "fdo", "Fundos / FIDC"),
    ("batimento_pnl_swap",      "VCRAPSWP", "VW_FUNDOS_POSICAO (Swap)",         "pos", "Swap"),
    ("batimento_pnl_opcao",     "VCRAPOPT", "VW_FUNDOS_POSICAO (Options)",      "fus", "Opcoes"),
    ("batimento_pnl_caixa",     "VCRAPCXD", "VW_FUNDOS_POSICAO (Cash)",         "fdo", "Caixa"),
]

BATIMENTO_CAUSAS = [
    # (causa, condicao, script_correcao)
    ("Apenas no Lake",                "|VW_FUNDOS_POSICAO| ausente no VCRA",              "Cadastro/SAC &rarr; importar_posicao"),
    ("Apenas no VCRA",                "|VCRAPRV| ausente em VW_FUNDOS_POSICAO",           "Posicao/SAC &rarr; importar_posicao"),
    ("Diverg&ecirc;ncia de Pre&ccedil;o",    "|preco_vcra &minus; preco_lake| &gt; 0.1%", "DadosAtivos/Cotas &rarr; carrega_cotas"),
    ("Diverg&ecirc;ncia de Quantidade", "QT_VCRA &ne; QT_LAKE (&gt; 0.01)",              "CRIMS_trades + SAC &rarr; importar_posicao"),
    ("Pre&ccedil;o + Quantidade",       "Ambas as diverg&ecirc;ncias simult&acirc;neas",   "Cotas + SAC em sequ&ecirc;ncia"),
    ("Diverg&ecirc;ncia em Trade",      "Pre&ccedil;o do trade VCRAOPRV &ne; Lake",       "CRIMS + AjustePnlDiff + SAC"),
    ("Diverg&ecirc;ncia de C&acirc;mbio/FX",  "Taxa FX ausente/errada em FUNDOS_DADOS_MOEDAS", "CaixaCPR/FxCRIMS &rarr; carrega_FxCRIMS"),
    ("Diverg&ecirc;ncia de Posi&ccedil;&atilde;o (outros)", "Evento corporativo n&atilde;o aplicado", "Posicao/SAC &rarr; importar_posicao"),
]

BATIMENTO_ANALISES = [
    # (nome, fonte, descricao, cat)
    ("1. Pre&ccedil;os Anomalias",        "&Delta;pre&ccedil;o D-1&rarr;D",       "Congelado (&Delta;&le;0.01%) / Spike (&Delta;&gt;5%)",             "pos"),
    ("2. PnL Esperado",                  "&Delta;pre&ccedil;o &times; qtd_D1",    "PnL esperado vs realizado &mdash; diverg&ecirc;ncia &gt; R$5",      "pos"),
    ("3. Carrego RF",                    "VCRAPRF D e D-1",                       "VL_LIQ_POS accrual esperado vs PnL realizado",                     "dur"),
    ("4. Trades vs Posi&ccedil;&atilde;o","VCRAOPRV + VCRAOPRF",                  "&Delta;qtd trades vs delta_posicao &rarr; pendente liquida&ccedil;&atilde;o", "rv"),
    ("5. Eventos Corporativos",          "FUNDOS_EVENTOS_CORPORATIVOS",           "Ajuste esperado por div/JCP/amortiza&ccedil;&atilde;o",             "rv"),
    ("6. Drift Exposi&ccedil;&atilde;o %PL", "Financeiro / Patrim&ocirc;nio",     "Drift &gt; 0.01% do PL entre D-1 e D",                             "pos"),
    ("7. Vencimentos na Data",           "VW_FUNDOS_POSICAO",                     "Ativos com vencimento = date_ref ainda em posi&ccedil;&atilde;o",   "fdo"),
    ("8. Caixa vs Liquida&ccedil;&otilde;es","VW_FUNDOS_POSICAO (Cash)",          "&Delta;saldo_caixa vs l&iacute;quido de trades do dia",             "fdo"),
    ("9. Tracking Error",                "VW_FUNDOS_BENCHMARKS",                  "TE di&aacute;rio: retorno_fundo &minus; retorno_benchmark",         "pos"),
    ("10. C&acirc;mbio Impl&iacute;cito","FUNDOS_DADOS_MOEDAS",                   "Taxa FX impl&iacute;cita vs taxa oficial &mdash; dif &gt; 0.01%",  "moeda"),
]

BATIMENTO_ABAS = [
    # (nome_aba, descricao, cat)
    ("Triagem",          "Triagem macro + breakdown por ativo",                "pos"),
    ("Explodido_PnL",    "Decomposi&ccedil;&atilde;o bps Cotas vs Posi&ccedil;&atilde;o por classe", "dur"),
    ("Detalhamento_Dif", "Reconcilia&ccedil;&atilde;o da diferen&ccedil;a R$ cotas vs posi&ccedil;&atilde;o", "pos"),
    ("Comparativo_D1",   "Gap macro D e D-1 + posi&ccedil;&atilde;o detalhada D-1",  "fdo"),
    ("Analises_Seq",     "10 an&aacute;lises sequenciais com flags e impactos",       "fus"),
    ("Variacao_Qtd",     "Delta de quantidade por ativo, ordenado por |&Delta;|",     "rv"),
    ("Pivot_Posicao",    "Pivot D-1 vs D por ativo",                               "pos"),
    ("Posicao",          "Carteira: qtd, pre&ccedil;o, financeiro, % PL",             "fdo"),
    ("Resumo_Fundo",     "Vis&atilde;o macro consolidada (PnL bps cotas vs posi&ccedil;&atilde;o)", "pos"),
    ("Proventos",        "Diagn&oacute;stico dividendos FUNDOS_DIVIDENDOS_FUNDOS",    "prov"),
    ("Resumo",           "Por ativo: causa + sugest&atilde;o + script de corre&ccedil;&atilde;o",   "pos"),
    ("Como_Corrigir",    "Scripts RunProject prontos para executar",               "fus"),
    ("Queries_SQL",      "Queries diagn&oacute;sticas prontas para rodar no SSMS",   "dur"),
    ("Diagnostico",      "Vis&atilde;o agregada por classe/causa + impacto R$",       "pos"),
    ("Batimento",        "Batimento completo &mdash; todos os campos VCRA vs Lake",   "rv"),
    ("Macro",            "Diff de retorno SAC vs Lake por fundo",                  "pos"),
    ("Aluguel",          "Batimento de aluguel de a&ccedil;&otilde;es (BTC)",         "fdo"),
    ("Marreta=Aluguel",  "Itens de aluguel com marreta de ajuste",                "fus"),
    ("OC3_Dados",        "Posi&ccedil;&atilde;o/patrim&ocirc;nio OC3 como compara&ccedil;&atilde;o adicional", "dur"),
]

BATIMENTO_SQL = {
    "triagem_macro": """\
SELECT
    CONVERT(VARCHAR(10), DF.date, 23)  AS date,
    DF.codigo_IAM_fundo,
    DF.mesa_gestao,
    ROUND(DF.Diferenca_Bps, 2) AS Diferenca_Bps,
    ROUND(DF.Diferenca_Fin, 2) AS Diferenca_Fin,
    ROUND(DF.fundo_pnl_bps, 4) AS fundo_pnl_bps,
    ROUND(DF.pnl_total_bps, 4) AS pnl_total_bps
FROM (
    SELECT
        A.date, A.codigo_IAM_fundo, A.mesa_gestao,
        A.fundo_pnl_perc * 10000                       AS fundo_pnl_bps,
        B.pnl_total_bps,
        (A.fundo_pnl_perc * 10000 - B.pnl_total_bps)  AS Diferenca_Bps,
        (A.fundo_pnl - B.pnl_total)                    AS Diferenca_Fin
    FROM VW_FUNDOS_COTAS_PL A
    LEFT JOIN (
        SELECT date, codigo_IAM_fundo,
               SUM(pnl_total)              AS pnl_total,
               SUM(pnl_total_perc * 10000) AS pnl_total_bps
        FROM VW_FUNDOS_POSICAO WITH (NOLOCK)
        GROUP BY date, codigo_IAM_fundo
    ) B ON A.date = B.date
       AND A.codigo_IAM_fundo = B.codigo_IAM_fundo
) DF
WHERE DF.date = '{date_ref}'
  AND ABS(DF.Diferenca_Bps) >= {min_bps}
  AND DF.mesa_gestao LIKE '%indexados%'
  AND DF.codigo_IAM_fundo NOT LIKE 'CR[_]%'
ORDER BY ABS(DF.Diferenca_Bps) DESC""",

    "detalhamento_pnl_classe": """\
SELECT
    codigo_IAM_fundo,
    tipo                                         AS classe,
    COUNT(DISTINCT codigo_IAM_ativo)             AS qtd_ativos,
    ROUND(SUM(pnl_total),               2)       AS pnl_posicao_RS,
    ROUND(SUM(pnl_total_perc * 10000),  4)       AS pnl_posicao_bps,
    ROUND(SUM(pnl_moeda_Ativo),         2)       AS pnl_posicao_comp,
    ROUND(SUM(pnl_moeda_ativo_operacao),2)       AS pnl_trade_comp,
    ROUND(SUM(pnl_cambio),              2)       AS pnl_cambio_comp
FROM VW_FUNDOS_POSICAO (NOLOCK)
WHERE date = '{date_ref}'
  AND codigo_IAM_fundo IN ({fundos})
GROUP BY codigo_IAM_fundo, tipo
ORDER BY codigo_IAM_fundo, ABS(SUM(pnl_total)) DESC""",

    "gap_macro_d_d1": """\
SELECT
    CONVERT(VARCHAR(10), A.date, 23)             AS date,
    A.codigo_IAM_fundo,
    A.mesa_gestao,
    ROUND(A.fundo_pnl_perc * 10000,          4) AS pnl_cotas_bps,
    ROUND(ISNULL(B.pnl_total_bps, 0),        4) AS pnl_posicao_bps,
    ROUND(A.fundo_pnl_perc * 10000
          - ISNULL(B.pnl_total_bps, 0),      4) AS diferenca_bps,
    ROUND(A.fundo_pnl
          - ISNULL(B.pnl_total, 0),          2) AS diferenca_RS,
    ROUND(A.last_patrimonio,                  2) AS patrimonio
FROM VW_FUNDOS_COTAS_PL A
LEFT JOIN (
    SELECT date, codigo_IAM_fundo,
           SUM(pnl_total)              AS pnl_total,
           SUM(pnl_total_perc * 10000) AS pnl_total_bps
    FROM VW_FUNDOS_POSICAO WITH (NOLOCK)
    GROUP BY date, codigo_IAM_fundo
) B ON A.date = B.date AND A.codigo_IAM_fundo = B.codigo_IAM_fundo
WHERE A.date IN ('{date_ref}', '{date_d1}')
  AND A.codigo_IAM_fundo IN ({fundos})
ORDER BY A.codigo_IAM_fundo, A.date""",

    "posicao_detalhada": """\
SELECT
    v.codigo_IAM_fundo,
    v.tipo                                            AS classe,
    v.ticker_bolsa, v.codigo_IAM_ativo,
    ROUND(SUM(v.quantidade),                4)        AS quantidade,
    ROUND(AVG(v.preco_limpo),               6)        AS preco,
    ROUND(SUM(v.quantidade)*AVG(v.preco_limpo), 2)    AS financeiro_RS,
    ROUND(SUM(v.pnl_total),                 2)        AS pnl_dia_RS,
    ROUND(SUM(v.pnl_total_perc)*10000,      4)        AS pnl_dia_bps,
    ROUND(SUM(v.pnl_moeda_Ativo),           2)        AS pnl_posicao,
    ROUND(SUM(v.pnl_moeda_ativo_operacao),  2)        AS pnl_trade,
    ROUND(SUM(v.pnl_cambio),                2)        AS pnl_cambio,
    v.moeda_ativo, v.vencimento
FROM VW_FUNDOS_POSICAO (NOLOCK) v
WHERE v.date = '{date_ref}'
  AND v.codigo_IAM_fundo IN ({fundos})
GROUP BY v.codigo_IAM_fundo, v.tipo, v.ticker_bolsa,
         v.codigo_IAM_ativo, v.moeda_ativo, v.vencimento
ORDER BY v.codigo_IAM_fundo, v.tipo,
         ABS(SUM(v.quantidade)*AVG(v.preco_limpo)) DESC""",
}

# ── dados Preço Justo ETF ────────────────────────────────────────────────────

PJ_FUNCOES = [
    # (funcao, etfs, indice, cat, descricao)
    ("gerar_preco_justo_etfRF",     "B5P211, IMAB11, IB5M11, IRFM11, IDKA11, TD3511, TD5011, TD6011, 5PRE11",
     "IMA-B / IRF-M / Pre 5Y", "dur",  "ETFs Renda Fixa &mdash; NTN-B, LTN, NTN-F"),
    ("gerar_preco_justo_etfGOAT11", "GOAT11",
     "80% IMA-B + 20% S&P500",  "rv",   "ETF H&iacute;brido &mdash; RV+RF+Caixa"),
    ("gerar_preco_justo_etfT10R11", "T10R11",
     "T10 futures + CDI &minus; Fed",   "pos",  "ETF Futuro T-Bond 10Y + diferencial BR/EUA"),
    ("gerar_preco_justo_etfSelic",  "CDIB11, LFTI11",
     "IMA-S / Selic",           "fdo",  "ETFs Selic &mdash; LFTs"),
]

PJ_FONTES_DB = [
    # (tabela, descricao, cat)
    ("VCRAPRF",                      "Posi&ccedil;&atilde;o RF: NTN-B, LTN, NTN-F, LFT (qtd, vl_liq_pos, isin, vencto)", "dur"),
    ("VCRAPLSI",                     "Cotas e patrim&ocirc;nio l&iacute;quido do fundo (d1)",                              "pos"),
    ("tbhh3042_anbima_titulo_pub...", "VNA (Valor Nominal Atualizado) de NTN-Bs &mdash; date = d0 (hoje)",               "dur"),
    ("tbhh3031_anbima_indices...",   "Duration dos &iacute;ndices IMA-B, IRF-M, IMA-S &mdash; data_ref = d1",            "dur"),
    ("FUNDOS_DADOS_ATIVOS",          "Duration de NTN-Bs espec&iacute;ficas (BRSTNCNTB*) &mdash; macaulay_duration",     "dur"),
    ("FUNDOS_COMPOSICAO_INDICES",    "Composi&ccedil;&atilde;o e duration do &iacute;ndice Pre 5Y (ITBR_5_PRE)",         "fus"),
    ("vcraprv / vcrabtc / vcraprdp", "GOAT11: posi&ccedil;&atilde;o RV + BTC + caixa parado (mttp_cd=251)",             "rv"),
]

PJ_FONTES_BBG = [
    # (ticker_bbg, campo, cat, descricao)
    ("{ISIN} @ITAM Corp",          "px_last / last_yld",          "dur",  "Pre&ccedil;o e yield NTN-B / LFT via ISIN"),
    ("{ISIN} Corp",                "yas_bond_px / last_trade",    "dur",  "Pre&ccedil;o e yield NTN-F / LTN pre-fixados"),
    ("{TICKER} Equity",            "bid / ask / last_trade",      "rv",   "Bid/Ask/&uacute;ltimo neg&oacute;cio do ETF"),
    ("{ticker} BZ Equity",         "px_last",                     "rv",   "Pre&ccedil;os componentes GOAT11 (RV + BTC)"),
    ("FEDL01 Index",               "PX_LAST (hist&oacute;rico)",  "pos",  "Taxa Fed Funds D-1"),
    ("BZSTSETA Index",             "PX_LAST (hist&oacute;rico)",  "fdo",  "CDI D-1"),
    ("TY{vencto} COMB Comdty",    "CTD_FORWARD_YTM_LAST / dur_adj_mid", "pos", "Yield e duration futuro T10 din&acirc;mico"),
]

PJ_CALCULOS = [
    # (etapa, formula, descricao)
    ("Cupom do dia",        "calc_cupom_ntnb/ntnf/ltn(d0, vencto, taxa, vna)",   "Preco_PnL.assets.* &mdash; acr&uacute;scimo de juros do dia"),
    ("PU careca",           "pu_careca_ntnb/ntnf/ltn(d0, vencto, taxa, vna)",    "Pre&ccedil;o online excluindo cupom acumulado"),
    ("PL online (RF)",      "&sum;(pu_careca &times; qtd) + caixa + cupom + vencto","Valor online da carteira"),
    ("Taxa ponderada",      "&sum;(taxa &times; % composi&ccedil;&atilde;o)",       "Yield m&eacute;dio ponderado por ativo"),
    ("Duration (%PL &times; dur)", "&sum;(% PL &times; duration_ativo)",           "Duration ponderada em dias &uacute;teis / 252 = anos"),
    ("Fair value (cota)",   "(caixa + PL online) / n&ordm; cotas",                "Valor justo estimado da cota do ETF"),
    ("Yield eq. compra",    "taxa_pond &minus; ((bid &minus; fair_value) / dur) / 100", "Yield impl&iacute;cito no pre&ccedil;o de compra"),
    ("Yield eq. venda",     "taxa_pond &minus; ((ask &minus; fair_value) / dur) / 100", "Yield impl&iacute;cito no pre&ccedil;o de venda"),
    ("Spread",              "yield_eq_compra &minus; yield_eq_venda",             "Diferen&ccedil;a de yield bid-ask"),
    ("T10R11 yield",        "CTD_yield + CDI &minus; Fed_Funds",                  "Diferencial de juros Brasil/EUA sobre T10"),
    ("Selic PL online",     "vl_pos_ontem &times; (1 + CDI)^(1/252)",            "LFTI11: atualiza posi&ccedil;&atilde;o pelo CDI do dia"),
]

PJ_SAIDAS = [
    ("Preco_Justo_RF.csv", "\\\\fswcorp\\WMSASSET\\ASSET_COMUM\\ETFs\\",  "pos",  "CSV final (;  ,) com todos os ETFs"),
    ("cotacoes_bs.csv",    "\\\\fswcorp\\WMSASSET\\ASSET_COMUM\\ETFs\\",  "dur",  "Hist&oacute;rico de cota&ccedil;&otilde;es NTN-B"),
    ("log_iam()",          "\\\\fswcorp\\wmsasset\\ASSET_COMUM\\Logs\\",  "fdo",  "Auditoria de execu&ccedil;&atilde;o + status (ok/erro)"),
]

PJ_SQL = {
    "pj_posicao_rf": """\
-- Posição RF (NTN-B, LTN, NTN-F) — data = D-1 útil
SELECT
    dt, clcli_cd,
    TRIM(rftp_cd)                        AS tipo_ativo,
    dt_vencimento,
    CONCAT(rftp_cd, ' ', dt_vencimento)  AS ticker,
    isin,
    SUM(qt_total)                        AS quantidade,
    SUM(vl_liq_pos)                      AS valor_posicao
FROM dbsx337.dbo.VCRAPRF
WHERE dt = '{d1}'
  AND clcli_cd IN ({string_fundos})
  AND rftp_cd NOT IN ('LFT')
GROUP BY dt, clcli_cd, rftp_cd, dt_vencimento, isin
ORDER BY clcli_cd, rftp_cd, dt_vencimento""",

    "pj_pl_ex_bs": """\
-- PL excluindo posições NTN-B/LTN/NTN-F (caixa + outros)
SELECT
    A.dt, A.clcli_cd,
    (A.vl_patrliqtot1 - B.VL_BRUTOPOS_Bs) AS PLexBs
FROM dbsx337.dbo.vcraplsi AS A
JOIN (
    SELECT dt, clcli_cd,
           SUM(vl_brutopos) AS VL_BRUTOPOS_Bs
    FROM dbsx337.dbo.vcraprf
    WHERE dt = '{d1}'
      AND rftp_cd IN ('NTN-B','LTN','NTN-F')
      AND clcli_cd IN ({string_fundos})
    GROUP BY dt, clcli_cd
) AS B ON A.dt = B.dt AND A.clcli_cd = B.clcli_cd
WHERE A.dt = '{d1}'
  AND A.clcli_cd IN ({string_fundos})""",

    "pj_duration": """\
-- Duration índices ANBIMA + NTN-Bs customizadas (UNION)
SELECT DISTINCT
    data_referencia, indice, duration
FROM dbsx337..tbhh3031_anbima_indices_mais_ima_resultados_componentes
WHERE data_referencia = '{d1}'
  AND indice IN ('IMA-B','IMA-B 5','IMA-B 5+','IRF-M',
                 'IRF-M 1','IRF-M 1+','IMA-S')

UNION

SELECT date, 'NTNB 2060', macaulay_duration
FROM FUNDOS_DADOS_ATIVOS (NOLOCK)
WHERE date = '{d1}'
  AND codigo_IAM_ativo = 'BRSTNCNTB690'

UNION

SELECT date, 'NTNB 2050', macaulay_duration
FROM FUNDOS_DADOS_ATIVOS (NOLOCK)
WHERE date = '{d1}'
  AND codigo_IAM_ativo = 'BRSTNCNTB3D4'

UNION

SELECT date, 'NTNB 2040', macaulay_duration
FROM FUNDOS_DADOS_ATIVOS (NOLOCK)
WHERE date = '{d1}'
  AND codigo_IAM_ativo = 'BRSTNCNTB0O7'""",

    "pj_vna_ntnb": """\
-- VNA (Valor Nominal Atualizado) NTN-B — data de hoje (d0)
SELECT tipo, data_referencia, vna
FROM dbsx337.dbo.tbhh3042_anbima_titulo_publico_vna
WHERE data_referencia = '{d0}'
  AND tipo = 'NTN-B'""",

    "pj_posicao_lft": """\
-- Posição LFT (Selic) — para CDIB11 / LFTI11
SELECT
    dt, clcli_cd,
    TRIM(rftp_cd)     AS tipo_ativo,
    dt_vencimento, isin,
    SUM(qt_total)     AS quantidade,
    SUM(vl_liq_pos)   AS valor_posicao
FROM dbsx337.dbo.VCRAPRF
WHERE dt = '{d1}'
  AND clcli_cd IN ({string_fundos})
  AND rftp_cd = 'LFT'
GROUP BY dt, clcli_cd, rftp_cd, dt_vencimento, isin""",
}

# ── dados Batimento Offshore ─────────────────────────────────────────────────

OFF_CLASSES = [
    # (classe_ssc, classe_iam, tipos_ssc, cat, descricao)
    ("Equities",      "Equity",       "EQYLST, EQYNLT",             "rv",  "Acoes offshore"),
    ("Futures",       "Future",       "CMDFUT",                     "pos", "Futuros (excl. NDF)"),
    ("Options",       "Option",       "CMDOPT",                     "fus", "Opcoes (excl. FXO, EQO)"),
    ("Fixed Income",  "Fixed Income", "BNDSVN, BNDCRP, BNDTRS",    "dur", "Bonds (excl. Repo/ReverseRepo)"),
    ("Cash / CPR",    "CaixaCPR",     "CSH &rarr; caixa_{moeda}",   "fdo", "Caixa por moeda"),
]

OFF_DETALHE_COLS = [
    # (coluna, origem, descricao)
    ("DifQtd",          "EndQty &minus; quantidade",                     "Diferenca de quantidade SSC vs IAM"),
    ("DifPnL",          "TotalBookPL &minus; pnl_total",                 "Diferenca de PnL  |Dif| &ge; R$1"),
    ("Dif_preco_D1",    "BegLocalMarketPrice &minus; preco_limpo_d1",    "Divergencia de preco em D-1"),
    ("Dif_preco",       "EndLocalMarketPrice &minus; preco_limpo",       "Divergencia de preco em D"),
]

OFF_ESTRAT_LOGICA = [
    # (caso, regra)
    ("Ativo com estrategia &uacute;nica",     "DifPnLEstrat = DifPnL (100%)"),
    ("M&uacute;ltiplas estrat&eacute;gias",   "DifPnLEstrat = DifPnL &times; (Qtd / Qtd_total)"),
    ("Posi&ccedil;&atilde;o zerada (Qtd=0)",  "DifPnLEstrat = DifPnL / n_estrategias (igual)"),
    ("Sem estrat&eacute;gia mapeada",         "est1 = 'VERIFICAR' &rarr; aba VerificarPnL"),
    ("Cash / CPR",                            "est1 = 'CaixaCPR', est2-est5 = '-'"),
]

OFF_ABAS = [
    ("Resumo",          "Total PnL por fundo e classe (SSnC vs IAM)",        "pos"),
    ("Ativos",          "Detalhe por ativo: qtd, PnL, preco D-1 e D",        "rv"),
    ("PnLEstrategia",   "PnL distribuido por estrategia (est1&ndash;est5)",   "fus"),
    ("VerificarPnL",    "Ativos sem estrategia mapeada &mdash; requer revisao","prov"),
    ("SemVerificarPnL", "Ativos com estrategia mapeada &mdash; OK",           "fdo"),
]

OFF_SQL = {
    "off_resumo_ssc": """\
-- Resumo total P&L por tipo de ativo — SSnC
SELECT date, codigo_IAM_fundo, Tipo,
       SUM(ISNULL(PnL_SSnC, 0)) AS PnL_SSnC
FROM (
    SELECT PeriodEndDate                               AS date,
           Fund                                        AS codigo_IAM_fundo,
           CASE WHEN InvAssetType = 'pseudo'
                 AND InvId LIKE '%INT%' THEN 'CSH'
                ELSE InvAssetType END                  AS Tipo,
           SUM(ISNULL(TotalBookPL, 0))                 AS PnL_SSnC
    FROM SISTEMAS_SSC_PED_INTRADAY (NOLOCK)
    WHERE AccountingPeriod = 'DAILY'
      AND Fund IN ({fundos})
      AND PeriodEndDate = '{data_ref}'
    GROUP BY PeriodEndDate, Fund, InvAssetType, InvId
) AS bla
GROUP BY date, codigo_IAM_fundo, Tipo""",

    "off_resumo_iam": """\
-- Resumo total P&L por tipo de ativo — IAM
SELECT date, codigo_IAM_fundo, Tipo,
       CONVERT(float, SUM(ISNULL(pnl_total, 0))) AS PnL_IAM
FROM VW_FUNDOS_POSICAO (NOLOCK)
WHERE codigo_IAM_fundo IN ({fundos})
  AND date = '{data_ref}'
GROUP BY date, codigo_IAM_fundo, Tipo""",

    "off_equities_ssc": """\
-- Equities SSnC — join com dicionario de ativos
SELECT A.PeriodEndDate        AS date,
       A.InvAssetType         AS Tipo,
       A.Fund                 AS codigo_IAM_fundo,
       A.InvGFSDefined3       AS codigo_IAM_ativo,
       B.valor_str            AS ticker_bolsa,
       AVG(BegLocalMarketPrice) AS BegLocalMarketPrice,
       AVG(EndLocalMarketPrice) AS EndLocalMarketPrice,
       SUM(A.BegQty)          AS BegQty,
       SUM(A.EndQty)          AS EndQty,
       SUM(A.TotalBookPL)     AS TotalBookPL
FROM SISTEMAS_SSC_PED_INTRADAY (NOLOCK) AS A
LEFT JOIN VIEW_FUNDOS_CADASTRO_ATIVOS_LAST_VALUES (NOLOCK) AS B
       ON A.InvGFSDefined3 = B.codigo_IAM_ativo
      AND B.campo = 'ticker_bolsa'
WHERE InvAssetType IN ('EQYLST', 'EQYNLT')
  AND accountingPeriod = 'DAILY'
  AND A.Fund IN ({fundos})
  AND A.PeriodEndDate = '{data_ref}'
GROUP BY A.PeriodEndDate, A.InvAssetType, A.Fund,
         A.InvGFSDefined3, B.valor_str""",

    "off_fixed_income_ssc": """\
-- Fixed Income SSnC (BNDSVN, BNDCRP, BNDTRS — excl. Repo)
SELECT A.PeriodEndDate        AS date,
       A.InvAssetType         AS Tipo,
       A.Fund                 AS codigo_IAM_fundo,
       A.InvGFSDefined2       AS codigo_IAM_ativo,
       AVG(BegLocalMarketPrice) AS BegLocalMarketPrice,
       AVG(EndLocalMarketPrice) AS EndLocalMarketPrice,
       SUM(A.BegQty)          AS BegQty,
       SUM(A.EndQty)          AS EndQty,
       SUM(A.TotalBookPL)     AS TotalBookPL
FROM SISTEMAS_SSC_PED_INTRADAY (NOLOCK) AS A
WHERE InvAssetType IN ('BNDSVN', 'BNDCRP', 'BNDTRS')
  AND AccountingPeriod = 'DAILY'
  AND A.TranType NOT IN ('Repo', 'ReverseRepo')
  AND A.Fund IN ({fundos})
  AND A.PeriodEndDate = '{data_ref}'
GROUP BY A.PeriodEndDate, A.InvAssetType, A.Fund, A.InvGFSDefined2""",

    "off_estrategias": """\
-- Distribuicao por estrategia de negociacao (est1-est5)
SELECT date, codigo_IAM_fundo, codigo_IAM_ativo,
       est1, est2, est3, est4, est5,
       ROUND(SUM(quantidade),          0) AS quantidade,
       ROUND(SUM(quantidade_abertura), 0) AS quantidade_abertura
FROM FUNDOS_POSICAO (NOLOCK)
WHERE codigo_IAM_fundo = '{cod_fund}'
  AND date             = '{data_ref}'
  AND codigo_iam_ativo IN ({codAtivos})
GROUP BY date, codigo_IAM_fundo, codigo_IAM_ativo,
         est1, est2, est3, est4, est5""",

    "off_cash_iam": """\
-- Cash/CPR IAM — agrupa por moeda (caixa_{moeda})
SELECT date, codigo_IAM_fundo, codigo_IAM_ativo,
       AVG(preco_limpo_d1) AS preco_limpo_d1,
       AVG(preco_limpo)    AS preco_limpo,
       SUM(quantidade)     AS quantidade,
       SUM(pnl_total)      AS pnl_total
FROM (
    SELECT date, codigo_IAM_fundo,
           CASE WHEN fator_risco <> 'CaixaCPR'
                THEN CONCAT('caixa_', LOWER(moeda_ativo))
                ELSE codigo_IAM_ativo END AS codigo_IAM_ativo,
           preco_limpo_d1, preco_limpo, quantidade, pnl_total, tipo
    FROM VW_FUNDOS_POSICAO (NOLOCK)
) AS a
WHERE codigo_iam_fundo IN ({fundos})
  AND date = '{data_ref}'
  AND Tipo = 'CaixaCPR'
  AND codigo_IAM_ativo LIKE 'caixa_%'
GROUP BY date, codigo_iam_fundo, codigo_iam_ativo""",
}

# ── dados Batimento OC3 ──────────────────────────────────────────────────────

OC3_POSICOES = [
    # (aba, metodo_oc3, cat, descricao)
    ("patrimonio_cotas", "GetPatRes()",                    "pos", "PL, qtd cotas, valor cota por data"),
    ("pos_rf",           "GetPosRf_Normal()",              "dur", "Posi&ccedil;&atilde;o Renda Fixa (MtM)"),
    ("pos_rv",           "GetPosRvAcoes_Normal()",         "rv",  "Posi&ccedil;&atilde;o A&ccedil;&otilde;es"),
    ("pos_futuro",       "GetFuturo()",                    "pos", "Contratos futuros abertos"),
    ("pos_swap",         "GetPosSwap_Normal()",            "pos", "Posi&ccedil;&atilde;o Swaps"),
    ("pos_caixa",        "GetPosicaoCaixa()",              "fdo", "Saldo caixa por moeda/tipo"),
    ("pos_opcoes_rf",    "GetOpcoes_RF()",                 "dur", "Op&ccedil;&otilde;es de Renda Fixa"),
    ("pos_opcoes_rv",    "GetOpcoes_RV()",                 "rv",  "Op&ccedil;&otilde;es de A&ccedil;&otilde;es"),
    ("pos_aluguel",      "GetPosicaoEmprestimoAcoes()",    "fdo", "Empr&eacute;stimo / aluguel de a&ccedil;&otilde;es"),
    ("fluxo_rf",         "GetRFAtualizacaoPapel()",        "dur", "Fluxo e atualiza&ccedil;&atilde;o de t&iacute;tulos RF"),
    ("cotas_externas",   "GetPosFundosSintetico_Normal()", "fdo", "Cotas de fundos externos/sint&eacute;ticos"),
]

OC3_MOV = [
    ("captacao_liquidez", "GetRVCotas()",            "fdo", "Capta&ccedil;&atilde;o e movimenta&ccedil;&atilde;o de cotas RV"),
    ("mov_fundos",        "GetMovFundos_Normal()",   "pos", "Aplica&ccedil;&otilde;es e resgates de cotas"),
    ("mov_rf",            "GetRFMovimentacao()",     "dur", "Compra/venda de t&iacute;tulos RF"),
    ("mov_rv",            "GetRVMovimentacao()",     "rv",  "Compra/venda de a&ccedil;&otilde;es"),
    ("mov_futuro",        "GetFuturoMovimentacao()", "pos", "Movimenta&ccedil;&atilde;o de futuros"),
    ("cot_futuro",        "GetFuturoConsultaCotacao()", "pos", "Cota&ccedil;&otilde;es de futuros (refer&ecirc;ncia)"),
]

OC3_CADASTROS = [
    ("ativo_cotas",        "GetAtivoCotas()",       "fdo", "Ativos e saldo tesouraria — filtrado por fundo"),
    ("pos_fi_patr",        "GetPosicaoFIPatr()",    "fdo", "Posi&ccedil;&atilde;o patrim&ocirc;nio de FIs — filtrado por fundo"),
    ("cpr",                "GetCPRInterface()",     "dur", "CPR (C&eacute;dula de Produto Rural) — filtrado por fundo"),
    ("cad_fundo_multiplo", "GetCliBasMultiplo()",   "pos", "Cadastro detalhado do fundo"),
]

OC3_PROVENTOS = [
    ("prov_bonificacao",  "GetProventoBonificacao()",  "rv",  "Bonifica&ccedil;&atilde;o de a&ccedil;&otilde;es"),
    ("prov_inplit_split", "GetProventoInplitSplit()",  "rv",  "Inplit / Split de a&ccedil;&otilde;es"),
    ("prov_fusao",        "GetProventoRV()",           "rv",  "Fus&atilde;o / incorpora&ccedil;&atilde;o"),
    ("prov_subscricao",   "GetProventoSubscricao()",   "rv",  "Subscri&ccedil;&atilde;o de a&ccedil;&otilde;es"),
]

OC3_MERCADO = [
    ("tx_cambio",    "GetTaxaCambio()",  "moeda", "Taxa de c&acirc;mbio do per&iacute;odo"),
    ("cot_rv_acoes", "GetRVAcoes()",     "rv",    "Cota&ccedil;&atilde;o de fechamento de a&ccedil;&otilde;es"),
]

# ── dados Dash Mesa RF ────────────────────────────────────────────────────────

DRF_DATAS = [
    ("D0",    "hoje",              "Data de execu&ccedil;&atilde;o &mdash; posi&ccedil;&atilde;o vigente"),
    ("D-1",   "dia &uacute;til anterior", "Posi&ccedil;&atilde;o fechada (base para batimentos)"),
    ("D-2",   "2 dias &uacute;teis atr&aacute;s", "Compara&ccedil;&atilde;o de curto prazo"),
    ("D-M",   "in&iacute;cio do m&ecirc;s corrente", "Base para MTD (month-to-date)"),
    ("YTD",   "31-dez do ano anterior", "Base para retorno no ano"),
    ("D-90",  "~90 dias &uacute;teis atr&aacute;s", "Janela de 3 meses"),
    ("Delta", "data selecionada pelo usu&aacute;rio", "Base para c&aacute;lculo do delta de posi&ccedil;&atilde;o"),
]

DRF_FUNDOS_GRUPOS = [
    # (codigo, grupo)
    ("FLEXPREVRF1644",  "PGBL&atilde;o"),
    ("FLEXPREVRF990",   "PGBL&atilde;o"),
    ("IPCAACTRF272",    "IPCA Action"),
    ("IPCACTRF55320",   "IPCA Action"),
    ("LUMIPRF56086",    "Lumina Plus"),
    ("LUMIRFLP56090",   "Lumina Plus"),
    ("FLEXRFFI56079",   "Lumina Plus"),
    ("INFRA56712",      "Lumina Plus"),
    ("LUMRF56764",      "Discri. Local"),
    ("LUMRF56972",      "Discri. Local"),
    ("FLEXRFAGRESS173", "Discri. Local"),
    ("PORTFOL5RF51009", "Discri. Local"),
    ("PREVIDMM51032",   "Discri. Local"),
    ("IBACTIVEFIXRF74", "Discri. Local"),
    ("FLOOR_RF_194",    "Discri. Local"),
    ("RESERVATPDI1867", "Discri. Local"),
    ("PLUSRF52850",     "Discri. Local"),
    ("ESTRATERF506",    "Discri. Local"),
    ("PER_KEY_RF_020",  "Discri. Local"),
    ("IMASTERF52563",   "Discri. Local"),
    ("WMGERAL53200",    "Discri. Local"),
    ("MIXRF789",        "Discri. Local"),
    ("BRAZNRIRF48888",  "Discri. Local"),
    ("MASTIRFMRF51393", "Discri. Local"),
    ("FRANCES_RF_226",  "100% Sist."),
    ("ITAU_RF_099",     "100% Sist."),
    ("FLEXRFMASTER174", "100% Sist."),
    ("OCEANRF52700",    "100% Sist."),
    ("ALOCDINRF54059",  "Risk budget"),
    ("ITAUFLEXRF848",   "Risk budget"),
    ("FIRF56863",       "PGBL casca"),
    ("ESP_FIASSETCORE", "Fundo off"),
    ("FLXRF57036",      "Sint&eacute;t. BN15XG1"),
    ("TFIMAB53985",     "Sint&eacute;t. BJJMS72"),
]

DRF_QUERIES = [
    # (id, tabela_principal, data, cat, descricao)
    ("drf_pos",       "VW_FUNDOS_POSICAO_EXPLODIDA_DOWN", "D0",  "dur", "Posi&ccedil;&atilde;o D0: % PL, eq_ano, ModDur por fundo/fator/tipo (+ UNION fundos sint&eacute;ticos)"),
    ("drf_pos_d1",    "VW_FUNDOS_POSICAO_EXPLODIDA_DOWN", "D-1", "dur", "Posi&ccedil;&atilde;o D-1: mesma estrutura &mdash; base para alpha e delta"),
    ("drf_pl",        "VW_FUNDOS_COTAS_PL",               "D0",  "pos", "PL, cotas, cota_com_dividendo, benchmark por fundo (tipo_dado=&apos;oficial&apos;)"),
    ("drf_juros_off", "VW_FUNDOS_POSICAO_EXPLODIDA_DOWN + FUNDOS_CADASTRO_ATIVOS", "D0", "fus", "Juros offshore D0: IRS/Fut IR/Opt IR &mdash; eq_ano por pa&iacute;s/tenor (bucket 01M&rarr;50Y)"),
    ("drf_juros_off_d1", "VW_FUNDOS_POSICAO_EXPLODIDA_DOWN + FUNDOS_CADASTRO_ATIVOS", "D-1", "fus", "Juros offshore D-1: mesma estrutura &mdash; base para delta"),
    ("drf_cambio",    "VW_FUNDOS_POSICAO_EXPLODIDA_DOWN", "D0",  "moeda", "C&acirc;mbio D0: NDF, FX fut/opt, Currency Exposure, Bond Swap &mdash; % PL por moeda"),
    ("drf_cambio_d1", "VW_FUNDOS_POSICAO_EXPLODIDA_DOWN", "D-1", "moeda", "C&acirc;mbio D-1: mesma estrutura &mdash; base para delta de moedas"),
]

DRF_TRANSFORMACOES = [
    # (etapa, formula, descricao, cat)
    ("Alpha Dia",          "pnl_cotas_dia &minus; benchmark_dia",                "Retorno relativo ao benchmark no dia",                                "pos"),
    ("Alpha Mtd",          "pnl_cotas_Mtd &minus; benchmark_Mtd",                "Retorno relativo acumulado no m&ecirc;s",                             "pos"),
    ("Alpha YTD",          "pnl_cotas_YTD &minus; benchmark_YTD",                "Retorno relativo acumulado no ano",                                   "pos"),
    ("perc_pl (alpha)",    "ISNULL(perc_pl,0) &minus; ISNULL(benchmark_perc,0)", "Exposi&ccedil;&atilde;o relativa ao benchmark",                       "pos"),
    ("eq_ano (alpha)",     "ISNULL(eq_ano,0) &minus; ISNULL(benchmark_eq_ano,0)","Duration equivalente relativa",                                       "dur"),
    ("ModDur",             "SUM(perc_pl_alpha &times; modified_duration)",        "Duration modificada ponderada pelo % PL relativo",                    "dur"),
    ("Vertex bucket",      "DATEDIFF(date, vencimento) &rarr; 01M/03M/06M/01Y/.../50Y", "Classifica&ccedil;&atilde;o de vencimento por prazo",          "dur"),
    ("Exposure Pr&eacute;","SUM(eq_ano) where fator_risco = &apos;Juros Pre&apos;",  "1Y Equivalent pr&eacute;-fixado total",                           "dur"),
    ("Exposure IPCA",      "SUM(eq_ano) where fator_risco = &apos;Infla&ccedil;&atilde;o&apos;", "1Y Equivalent IPCA total",                            "dur"),
    ("Exposure Offshore",  "SUM(perc_pl) where pais &ne; &apos;Brazil&apos;",    "% PL em ativos offshore",                                             "pos"),
    ("Cr&eacute;dito",     "SUM(perc_pl) where fator_risco = &apos;Cr&eacute;dito&apos;", "% PL em cr&eacute;dito (dupla contagem com outros fatores)", "dur"),
    ("Moedas % PL",        "SUM(perc_pl) by moeda_ativo where fator=C&acirc;mbio", "Exposi&ccedil;&atilde;o cambial por moeda",                        "moeda"),
    ("Delta D vs Delta",   "valor_D0 &minus; valor_Delta",                       "Varia&ccedil;&atilde;o da posi&ccedil;&atilde;o vs data selecionada",  "pos"),
]

DRF_ABAS_SAIDA = [
    # (nome, descricao, cat)
    ("Posi&ccedil;&atilde;o - Resumo",         "Alpha (Dia/Mtd/YTD) + Exposure Pr&eacute;/IPCA/Offshore/Cr&eacute;dito + Prazo M&eacute;dio + Juros OFF + Moedas", "dur"),
    ("Posi&ccedil;&atilde;o Delta",            "Delta D vs data selecionada: mesma estrutura da aba Resumo", "dur"),
    ("Rates BR - por v&eacute;rtice",          "Equiv. anual Pr&eacute; e IPCA por v&eacute;rtice de vencimento (V25 &rarr; F31+)", "pos"),
    ("Rates BR Delta",                         "Delta de posi&ccedil;&atilde;o por v&eacute;rtice vs data selecionada", "pos"),
    ("Estrat&eacute;gias - por v&eacute;rtice","Exposure por estrat&eacute;gia (ARTHUR/YURI/FX/RATES/SIS) &times; v&eacute;rtice &mdash; CAMBIO/OFFSHORE/ONSHORE", "fus"),
    ("Estrat&eacute;gias Delta",               "Delta de exposure por estrat&eacute;gia vs data selecionada", "fus"),
    ("Exposure and P&amp;L - Hist",            "Hist&oacute;rico por fundo: alpha, vol 3M, % cr&eacute;dito/offshore, eq_ano por gestora (PAULO/YURI/HENRIQUE)", "fdo"),
]

DRF_VERTICE_COLS = [
    # (fator, vertice, instrumento)
    ("Juros Pre",  "V25",  "PRE"),  ("Inflacao",  "V25", "IPCA"),
    ("Juros Pre",  "F26",  "PRE"),  ("Juros Pre", "J26", "PRE"),
    ("Juros Pre",  "N26",  "PRE"),  ("Juros Pre", "Q26", "PRE"),
    ("Inflacao",   "V26",  "IPCA"), ("Juros Pre", "F27", "PRE"),
    ("Juros Pre",  "K27",  "PRE"),  ("Inflacao",  "N27", "IPCA"),
    ("Juros Pre",  "F28",  "PRE"),  ("Juros Pre", "N28", "PRE"),
    ("Juros Pre",  "Q28",  "PRE"),  ("Inflacao",  "F29", "IPCA"),
    ("Juros Pre",  "K29",  "PRE"),  ("Inflacao",  "N29", "IPCA"),
    ("Juros Pre",  "F30",  "PRE"),  ("Juros Pre", "Q30", "PRE"),
    ("Inflacao",   "F31",  "IPCA"), ("Juros Pre", "F31", "PRE"),
]

DRF_ESTRATEGIAS = [
    # (bloco, gestora, dim, moeda/etc, instrumento, fator)
    ("CAMBIO",   "ARTHUR", "DM",  "AUD", "CCY", "Juros Pre"),
    ("CAMBIO",   "ARTHUR", "DM",  "EUR", "CCY", "Inflacao"),
    ("OFFSHORE", "FX",     "DM",  "EUR", "-",   "Cambio"),
    ("OFFSHORE", "FX",     "EM",  "BRL", "-",   "Cambio"),
    ("OFFSHORE", "FX",     "EM",  "BRL", "-",   "Cambio"),
    ("OFFSHORE", "OFF",    "HEDGE", "-", "-",   "Cambio"),
    ("OFFSHORE", "YURI",   "FX",  "EM",  "BRL", "Cambio"),
    ("ONSHORE",  "RATES",  "DM",  "GBP", "NOM", "Cambio"),
    ("ONSHORE",  "RATES",  "DM",  "USD", "NOM", "Cambio"),
    ("ONSHORE",  "SIS",    "JUR", "PRE", "DIR", "Juros Pre"),
    ("ONSHORE",  "JUR",    "PRE", "DIR", "-",   "Juros Pre"),
]

DRF_SQL = {
    "drf_pos": """\
-- Posicao D0 — relativa ao benchmark (eq_ano e perc_pl like-for-like)
-- UNION ALL: fundos sinteticos FLXRF57036 (via BN15XG1) e TFIMAB53985 (via BJJMS72)
SELECT *
FROM (
    SELECT
        date, codigo_IAM_fundo, codigo_IAM_fundo_origem,
        mesa_gestao, est1, est2, est3, est4, est5,
        fator_risco, pais, tipo,
        SUM(total)                                                  AS total,
        SUM(ISNULL(perc_pl,0) - ISNULL(benchmark_perc,0))          AS perc_pl,
        SUM(total_nav_moeda_fundo)                                  AS total_nav_moeda_fundo,
        SUM(perc_nav)                                               AS perc_nav,
        SUM(ISNULL(eq_ano,0) - ISNULL(benchmark_eq_ano,0))         AS eq_ano,
        tipo_ativo_exposicao, indexador, divida,
        fator_risco_mercado, vencimento_codigo,
        SUM((ISNULL(perc_pl,0)-ISNULL(benchmark_perc,0))*modified_duration) AS ModDur,
        dias_uteis * perc_pl                                        AS peso,
        ativo
    FROM VW_FUNDOS_POSICAO_EXPLODIDA_DOWN
    WHERE codigo_IAM_ativo NOT IN ('BN15XG1','BJJMS72')
    GROUP BY date, codigo_IAM_fundo, codigo_IAM_fundo_origem,
             mesa_gestao, est1, est2, est3, est4, est5,
             fator_risco, pais, tipo,
             tipo_ativo_exposicao, indexador, divida,
             fator_risco_mercado, vencimento_codigo,
             dias_uteis, ativo, perc_pl

    UNION ALL

    -- Fundo sintetico FLXRF57036 (inclui fundo ITAUIMA5P2070 ponderado por cota BN15XG1)
    SELECT
        a.date, 'FLXRF57036' AS codigo_IAM_fundo,
        codigo_IAM_fundo_origem, mesa_gestao, est1, est2, est3, est4, est5,
        fator_risco, pais, tipo,
        SUM(a.perc_pl * b.perc_pl * b.last_patrimonio) AS total,
        SUM(a.perc_pl * b.perc_pl)                     AS perc_pl,
        SUM(a.perc_pl * b.perc_pl * b.last_patrimonio) AS total_nav_moeda_fundo,
        SUM(perc_nav  * b.perc_pl)                     AS perc_nav,
        SUM(eq_ano    * b.perc_pl)                     AS eq_ano,
        tipo_ativo_exposicao, indexador, divida,
        fator_risco_mercado, vencimento_codigo,
        SUM(a.perc_pl * b.perc_pl * modified_duration) AS ModDur,
        dias_uteis * a.perc_pl                         AS peso, ativo
    FROM VW_FUNDOS_POSICAO_EXPLODIDA_DOWN AS a
    LEFT JOIN (
        SELECT date, perc_pl, last_patrimonio
        FROM VIEW_FUNDOS_POSICAO
        WHERE codigo_IAM_ativo = 'BN15XG1'
          AND codigo_IAM_fundo = 'FLXRF57036'
    ) AS b ON a.date = b.date
    WHERE codigo_IAM_fundo IN ('ITAUIMA5P2070')
    GROUP BY a.date, codigo_IAM_fundo_origem, mesa_gestao,
             est1, est2, est3, est4, est5, fator_risco, pais, tipo,
             tipo_ativo_exposicao, indexador, divida,
             fator_risco_mercado, vencimento_codigo, dias_uteis, ativo, a.perc_pl

    UNION ALL

    -- Fundo sintetico TFIMAB53985 (inclui fundo ITAUIMAB64066 ponderado por cota BJJMS72)
    SELECT
        a.date, 'TFIMAB53985' AS codigo_IAM_fundo,
        codigo_IAM_fundo_origem, mesa_gestao, est1, est2, est3, est4, est5,
        fator_risco, pais, tipo,
        SUM(a.perc_pl * b.perc_pl * b.last_patrimonio) AS total,
        SUM(a.perc_pl * b.perc_pl)                     AS perc_pl,
        SUM(a.perc_pl * b.perc_pl * b.last_patrimonio) AS total_nav_moeda_fundo,
        SUM(perc_nav  * b.perc_pl)                     AS perc_nav,
        SUM(eq_ano    * b.perc_pl)                     AS eq_ano,
        tipo_ativo_exposicao, indexador, divida,
        fator_risco_mercado, vencimento_codigo,
        SUM(a.perc_pl * b.perc_pl * modified_duration) AS ModDur,
        dias_uteis * a.perc_pl                         AS peso, ativo
    FROM VW_FUNDOS_POSICAO_EXPLODIDA_DOWN AS a
    LEFT JOIN (
        SELECT date, perc_pl, last_patrimonio
        FROM VIEW_FUNDOS_POSICAO
        WHERE codigo_IAM_ativo = 'BJJMS72'
          AND codigo_IAM_fundo = 'TFIMAB53985'
    ) AS b ON a.date = b.date
    WHERE codigo_IAM_fundo IN ('ITAUIMAB64066')
    GROUP BY a.date, codigo_IAM_fundo_origem, mesa_gestao,
             est1, est2, est3, est4, est5, fator_risco, pais, tipo,
             tipo_ativo_exposicao, indexador, divida,
             fator_risco_mercado, vencimento_codigo, dias_uteis, ativo, a.perc_pl
) AS bla
WHERE 1=1""",

    "drf_pl": """\
-- PL, cotas e benchmark — tipo_dado = 'oficial'
SELECT
    date, codigo_IAM_fundo,
    qt_cotas, cota_com_dividendo, patrimonio_brl,
    benchmark, cota_benchmark,
    mesa_gestao, calculo_cota, tipo_dado
FROM VW_FUNDOS_COTAS_PL
WHERE tipo_dado = 'oficial'""",

    "drf_juros_off": """\
-- Juros offshore (IRS, Futuro IR, Opcao IR) com bucketing de prazo
-- Fonte: VW_FUNDOS_POSICAO_EXPLODIDA_DOWN + FUNDOS_CADASTRO_ATIVOS (prazo_definido)
SELECT *
FROM (
    SELECT
        date, codigo_IAM_ativo, ativo, ticker_bolsa,
        codigo_IAM_fundo_origem, codigo_IAM_fundo,
        fator_risco, tipo_ativo_exposicao_final,
        SUM(eq_ano) AS eq_ano
    FROM (
        SELECT
            date, a.codigo_IAM_ativo, ticker_bolsa,
            codigo_IAM_fundo_origem, codigo_IAM_fundo,
            fator_risco,
            CASE
                WHEN fator_risco IN ('Juros Pre','Juros Pos','Inflacao') THEN
                    CASE
                        WHEN b.valor_str IS NULL AND DATEDIFF(MONTH, date, vencimento) <= 1  THEN CONCAT(pais,'_01M')
                        WHEN b.valor_str IS NULL AND DATEDIFF(MONTH, date, vencimento) <= 4  THEN CONCAT(pais,'_03M')
                        WHEN b.valor_str IS NULL AND DATEDIFF(MONTH, date, vencimento) <= 8  THEN CONCAT(pais,'_06M')
                        WHEN b.valor_str IS NULL AND DATEDIFF(YEAR,  date, vencimento) <  2  THEN CONCAT(pais,'_01Y')
                        WHEN b.valor_str IS NULL AND DATEDIFF(YEAR,  date, vencimento) <= 3  THEN CONCAT(pais,'_02Y')
                        WHEN b.valor_str IS NULL AND DATEDIFF(YEAR,  date, vencimento) <= 7  THEN CONCAT(pais,'_05Y')
                        WHEN b.valor_str IS NULL AND DATEDIFF(YEAR,  date, vencimento) <= 15 THEN CONCAT(pais,'_10Y')
                        WHEN b.valor_str IS NULL AND DATEDIFF(YEAR,  date, vencimento) <= 20 THEN CONCAT(pais,'_20Y')
                        WHEN b.valor_str IS NULL AND DATEDIFF(YEAR,  date, vencimento) <= 30 THEN CONCAT(pais,'_30Y')
                        WHEN b.valor_str IS NULL AND DATEDIFF(YEAR,  date, vencimento) <= 40 THEN CONCAT(pais,'_40Y')
                        WHEN b.valor_str IS NULL AND DATEDIFF(YEAR,  date, vencimento) <= 50 THEN CONCAT(pais,'_50Y')
                        WHEN b.valor_str IS NOT NULL                                         THEN CONCAT(pais,'_',b.valor_str)
                    END
                ELSE '-'
            END AS tipo_ativo_exposicao_final,
            ativo, eq_ano, perc_pl, quantidade
        FROM VW_FUNDOS_POSICAO_EXPLODIDA_DOWN AS a
        LEFT JOIN FUNDOS_CADASTRO_ATIVOS AS b
            ON a.codigo_IAM_ativo = b.codigo_IAM_ativo
           AND b.campo = 'prazo_definido'
           AND b.date_change = '1900-01-01'
        WHERE tipo NOT IN ('Tx. Adm','Tx. Pfee','Despesa','CaixaCPR')
          AND quantidade <> 0
    ) AS tbFinal
    WHERE fator_risco <> 'CaixaCPR'
    GROUP BY date, codigo_IAM_ativo, ticker_bolsa,
             codigo_IAM_fundo_origem, codigo_IAM_fundo,
             fator_risco, tipo_ativo_exposicao_final, ativo
) AS DF
WHERE ativo IN ('Interest Rate Swap','Future Interest Rate','Option Interest Rate')""",

    "drf_cambio": """\
-- Cambio D0: posicoes FX (NDF, Fut/Opt FX, CurrencyExposure, Bond Swap)
-- Resultado: % PL por moeda e fundo (fator_risco_mercado = 'Cambio')
SELECT *
FROM (
    SELECT
        date, codigo_IAM_ativo, Ativo, Tipo, Ticker_bolsa,
        codigo_IAM_fundo, codigo_IAM_fundo_origem,
        Fator_risco, Moeda_ativo,
        SUM(perc_pl) AS perc_pl
    FROM (
        -- 1. Posicoes FX diretas (long side)
        SELECT
            date, a.codigo_IAM_fundo, a.codigo_IAM_fundo_origem,
            codigo_IAM_ativo2 AS codigo_IAM_ativo,
            Tipo2 AS Tipo, Ticker_bolsa2 AS Ticker_bolsa,
            Ativo2 AS Ativo, Moeda_ativo2 AS Moeda_ativo,
            Fator_risco2 AS Fator_risco, fator_risco_mercado,
            LEFT(Moeda_risco_cambial,3) AS Moeda_risco_cambial,
            SUM(perc_pl) AS perc_pl
        FROM VW_FUNDOS_POSICAO_EXPLODIDA_DOWN (NOLOCK) AS a
        -- [CASE expressions mapeiam tipo/ativo/moeda para classificacao padrao]
        WHERE quantidade <> 0
          AND LEFT(moeda_fundo_origem,3) <> CASE WHEN ativo='NDF' THEN LEFT(moeda_risco_cambial,3) ELSE '' END
        GROUP BY date, a.codigo_IAM_fundo, a.codigo_IAM_fundo_origem,
                 codigo_IAM_ativo2, Tipo2, Ticker_bolsa2, Ativo2,
                 Moeda_ativo2, Fator_risco2, fator_risco_mercado,
                 LEFT(Moeda_risco_cambial,3)

        UNION ALL

        -- 2. FX Futures e Options (short side)
        SELECT date, codigo_IAM_fundo, codigo_IAM_fundo_origem,
               '-', CONCAT('FX ',tipo,' - short side'), CONCAT(ticker_bolsa,' - short side'),
               ativo, moeda_ativo2, 'Cambio', 'Cambio', '-',
               SUM(-perc_pl)
        FROM VW_FUNDOS_POSICAO_EXPLODIDA_DOWN (NOLOCK)
        WHERE fator_risco = 'Cambio'
          AND (tipo IN ('Future','Option') OR codigo_IAM_ativo = 'FX_USD_BRL')
        GROUP BY date, codigo_IAM_fundo, codigo_IAM_fundo_origem,
                 pais2, pais_grupo2, tipo, ticker_bolsa, ativo, moeda_ativo2

        UNION ALL

        -- 3. Currency Exposure (exposure cambial implicita em ativos nao-BRL)
        SELECT date, codigo_IAM_fundo, codigo_IAM_fundo_origem,
               '-', 'CurrencyExposure', 'Currency Exposure',
               '-', Moeda_ativo, 'Cambio', 'Cambio', '-',
               SUM(Perc_pl)
        FROM (
            -- 3a. Exposure do ativo
            SELECT date, codigo_IAM_fundo, codigo_IAM_fundo_origem,
                   ISNULL(Moeda_risco_cambial, Moeda_ativo) AS Moeda_ativo,
                   perc_nav AS Perc_pl
            FROM VW_FUNDOS_POSICAO_EXPLODIDA_DOWN (NOLOCK)
            WHERE LEFT(moeda_fundo,3) <> LEFT(ISNULL(moeda_risco_cambial,moeda_ativo),3)
              AND LEFT(codigo_IAM_ativo,5) <> 'caixa'
            UNION ALL
            -- 3b. Exposure do fundo (lado oposto)
            SELECT date, codigo_IAM_fundo, codigo_IAM_fundo_origem,
                   LEFT(moeda_fundo,3), perc_nav * -1
            FROM VW_FUNDOS_POSICAO_EXPLODIDA_DOWN (NOLOCK)
            WHERE LEFT(moeda_fundo,3) <> LEFT(ISNULL(moeda_risco_cambial,moeda_ativo),3)
            UNION ALL
            -- 3c. Bond Swap leg 1
            SELECT date, codigo_IAM_fundo, codigo_IAM_fundo_origem,
                   Moeda_risco_cambial, isnull(Total_moeda_fundo,0)
            FROM VW_FUNDOS_POSICAO_EXPLODIDA_DOWN (NOLOCK)
            WHERE LEFT(moeda_ativo,3) <> LEFT(moeda_risco_cambial,3) AND Ativo='Bond Swap'
            UNION ALL
            -- 3d. Bond Swap leg 2
            SELECT date, codigo_IAM_fundo, codigo_IAM_fundo_origem,
                   Moeda_ativo, isnull(Total_moeda_fundo,0)*-1
            FROM VW_FUNDOS_POSICAO_EXPLODIDA_DOWN (NOLOCK)
            WHERE LEFT(moeda_ativo,3) <> LEFT(moeda_risco_cambial,3) AND Ativo='Bond Swap'
        ) AS ce
        GROUP BY date, codigo_IAM_fundo, codigo_IAM_fundo_origem, Pais, Pais_grupo, moeda_ativo
    ) AS C
    WHERE fator_risco_mercado = 'Cambio'
    GROUP BY date, codigo_IAM_ativo, Ativo, Tipo, Ticker_bolsa,
             codigo_IAM_fundo, codigo_IAM_fundo_origem, Fator_risco, Moeda_ativo
) AS Bla
WHERE 1=1""",
}

# ── dados SAC_Cota.py ────────────────────────────────────────────────────────

SAC_COTA_SQL = {
    "sac_dic_fundos": """\
SELECT codigo_sistema, codigo_IAM_fundo
FROM SISTEMAS_DICIONARIO_FUNDOS
WHERE sistema = 'SAC'
  AND tipo = 'Carteira'
-- Quando lista_fundos preenchida, adiciona:
-- AND codigo_IAM_fundo IN ({lista_fundos})""",

    "sac_pos_vcrapfdo": """\
-- Contingencia = True  ->  fonte: SAC (vcrapfdo)
SELECT CLCLI_CD        AS clcli_cd,
       dt,
       FICAD_CD        AS ficad_cd,
       TIPO_CLASSIF    AS cd_tipo_classificacao,
       SUM(qt_cotas)   AS qt_cota,
       AVG(vl_cota)    AS vl_cota,
       cd_cliente_sac,
       BAINS_CD        AS cd_emissor
FROM vcrapfdo
WHERE dt IN ('{dateD1}', '{dateD2}')
  AND clcli_cd IN ({lista_fundos_sac})
GROUP BY CLCLI_CD, dt, FICAD_CD,
         TIPO_CLASSIF, cd_cliente_sac, BAINS_CD""",

    "sac_pos_oc3light": """\
-- Contingencia = False  ->  fonte: OC3Light
SELECT b.cd_carteira         AS clcli_cd,
       a.dt_Posicao          AS dt,
       a.cd_Ativo            AS ficad_cd,
       d.cd_TipoClassificacao AS cd_tipo_classificacao,
       SUM(a.QT_COTAS)       AS qt_cota,
       AVG(a.vl_cota)        AS vl_cota,
       d.cd_CarteiraSAC      AS cd_cliente_sac,
       d.cd_emissor
FROM VWOC3_04W_FUNDO_POSICAO_ASSET a (NOLOCK)
JOIN TBOC3_99W_CARTEIRA_CODIGO b (NOLOCK)
  ON a.id_Carteira = b.id_Carteira
JOIN TBOC3_89W_SISTEMA c (NOLOCK)
  ON a.cd_Sistema = c.cd_Sistema
JOIN TBOC3_96W_FUNDO_ATIVO d (NOLOCK)
  ON a.cd_Sistema = d.cd_Sistema
 AND a.cd_Ativo   = d.cd_Ativo
WHERE a.dt_Posicao IN ('{dateD1}', '{dateD2}')
  AND b.cd_carteira IN ({lista_fundos_sac})
GROUP BY b.cd_carteira, a.dt_Posicao, a.cd_Ativo,
         d.cd_TipoClassificacao, d.cd_CarteiraSAC, d.cd_emissor""",

    "sac_dic_ativos": """\
SELECT DISTINCT codigo_IAM_ativo,
       valor_str AS codigo_sistema   -- lista de codigos SAC (eval -> explode)
FROM VIEW_FUNDOS_CADASTRO_ATIVOS_LAST_VALUES
WHERE campo = 'codigo_cota_SAC'
-- Quando lista_ativos preenchida, adiciona:
-- AND codigo_IAM_ativo IN ({lista_ativos})""",

    "sac_fidc_cadastro": """\
-- Consulta antes de inserir: evita duplicatas em FUNDOS_CADASTRO_ATIVOS
SELECT date_change, campo,
       valor_str, valor_num, valor_date,
       codigo_IAM_ativo
FROM FUNDOS_CADASTRO_ATIVOS (NOLOCK)
WHERE codigo_IAM_ativo IN {tup_ativos}""",

    "sac_estrategia": """\
-- Separacao: fundos com controle por estrategia -> FUNDOS_POSICAO_SISTEMAS
SELECT DISTINCT codigo_IAM_fundo
FROM FUNDOS_CADASTRO_FUNDOS
WHERE campo    = 'controle_por_estrategia'
  AND valor_num = 1""",

    "sac_delete_posicao_sistemas": """\
-- DELETE antes do INSERT em FUNDOS_POSICAO_SISTEMAS
DELETE FROM FUNDOS_POSICAO_SISTEMAS
WHERE date              = '{dateD1}'
  AND codigo_IAM_fundo  IN ({codigosFundos})
  AND (
       codigo_IAM_ativo IN ({codigosAtivos})
    OR codigo_IAM_ativo IN (
           SELECT codigo_IAM_ativo
           FROM   fundos_cadastro_ativos
           WHERE  campo     = 'tipo'
             AND  valor_Str = 'fund'
       )
  )""",

    "sac_delete_posicao": """\
-- DELETE antes do INSERT em FUNDOS_POSICAO
DELETE FROM FUNDOS_POSICAO
WHERE date              = '{dateD1}'
  AND codigo_IAM_fundo  IN ({codigosFundos})
  AND (
       codigo_IAM_ativo IN ({codigosAtivos})
    OR codigo_IAM_ativo IN (
           SELECT codigo_IAM_ativo
           FROM   fundos_cadastro_ativos
           WHERE  campo     = 'tipo'
             AND  valor_Str = 'fund'
       )
  )""",
}

# ── helpers HTML ──────────────────────────────────────────────────────────────


def tag(name, source, dest_col, sheet, cat, label):
    css = CAT_CSS.get(cat, "t-pos")
    return (
        '<div class="tag ' + css + '">'
        "<strong>" + name + "</strong>"
        '<span class="src">' + source + "</span>"
        '<span class="dest">' + sheet + " &middot; " + dest_col + "</span>"
        '<span class="lbl">' + label + "</span>"
        "</div>"
    )


def arrow():
    return '<div class="arrow"></div>'


def status_wrap(html, sid):
    badge = (
        '<button class="s-badge s-todo" data-sid="' + sid + '"'
        ' onclick="cycleStatus(event,\'' + sid + '\')" title="Clique para mudar status">'
        '<span class="s-dot"></span><span class="s-lbl">A fazer</span>'
        '</button>'
    )
    pos = html.rfind('</div>')
    if pos >= 0:
        return html[:pos] + badge + html[pos:]
    return html + badge


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
        # '<div class="bloco-header">&#x2699; Inicializacao do Ambiente VBA</div>'
        '<div class="bloco-header">Inicializacao do Ambiente VBA</div>'
        '<div class="bloco-sub">Workbook: <strong>Exposicao Beta</strong>'
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
    return group("Montagem de strings de tickers &mdash; planilha PRM", inner, cols=3, width=620)


def bloco_queries():
    def tag_vba(q):
        css  = CAT_CSS.get(q[4], "t-pos")
        nome = q[0]
        has_sql = nome in VBA_SQL
        click = ' onclick="showSQL(\'' + nome + '\')" title="Clique para ver a query SQL"' if has_sql else ""
        extra = " clickable " if has_sql else " "
        hint  = ' &nbsp;<em style="opacity:.5;font-size:.6rem">ver SQL</em>' if has_sql else ""
        return (
            '<div class="tag' + extra + css + '"' + click + ">"
            "<strong>" + nome + "</strong>"
            '<span class="src">' + q[1] + "</span>"
            '<span class="dest">' + q[3] + " &middot; " + q[2] + "</span>"
            '<span class="lbl">' + q[5] + hint + "</span>"
            "</div>"
        )
    tags = "".join(tag_vba(q) for q in SQL_QUERIES)
    n = len(SQL_QUERIES)
    return group(
        # "&#x1F4DD; Definicao das queries SQL &mdash; banco dbsx337 (" + str(n) + " queries &mdash; clique para ver a query)",
        "Definicao das queries SQL &mdash; banco dbsx337 (" + str(n) + " queries &mdash; clique para ver a query)",
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
        # '<div class="bloco-header">&#x1F5D1; Limpeza de intervalos</div>'
        '<div class="bloco-header">Limpeza de intervalos</div>'
        '<div class="bloco-sub">'
        + str(total) + " intervalos em " + str(len(CLEAR_RANGES)) + " abas"
        + "</div>"
        + rows
    )
    return node(inner, "c-clear", 640)


def bloco_connect():
    inner = (
        # '<div class="bloco-header">&#x1F50C; Conexao com banco de dados</div>'
        '<div class="bloco-header">Conexao com banco de dados</div>'
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
        # "&#x2699; Bloco PRV &mdash; Acoes RV + Aluguel BTC (planilha TEMP intermediaria)"
        "Bloco PRV &mdash; Acoes RV + Aluguel BTC (planilha TEMP intermediaria)"
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
        '<div class="group-title">Execucao das queries e destino no workbook ('
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
        # "&#x1F9EE; Insercao de formulas (" + str(n) + " formulas)</div>"
        "Insercao de formulas (" + str(n) + " formulas)</div>"
        '<table class="ftable"><thead>' + header + "</thead><tbody>" + rows + "</tbody></table>"
        "</div>"
    )


def bloco_autofilter():
    inner = (
        # '<div class="bloco-header">&#x1F50D; AutoFilter &mdash; Aba Relatorio</div>'
        '<div class="bloco-header">AutoFilter &mdash; Aba Relatorio</div>'
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
        # '<div class="bloco-header">&#x267B; Restauracao das configuracoes</div>'
        '<div class="bloco-header">Restauracao das configuracoes</div>'
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

html { color-scheme: dark; }
html[data-theme="light"] { color-scheme: light; }

/* Toda a area de paginas (fluxogramas) vive dentro de #theme-scope.
   A sidebar de To Do e os modais ficam FORA dela de proposito: teriam sua
   posicao fixa quebrada se herdassem um filter do ancestral (regra do CSS
   em que filter cria um novo bloco de conteudo para descendentes fixed). */
#theme-scope { transition: filter .25s ease; }
html[data-theme="light"] #theme-scope { filter: invert(1) hue-rotate(180deg); }

.theme-toggle-btn {
  position: fixed;
  top: 16px;
  left: 16px;
  z-index: 600;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.15rem;
  cursor: pointer;
  background: #13151c;
  border: 1.5px solid #2a2d3e;
  color: #f4d03f;
  transition: transform .15s, border-color .15s, background .15s;
}
.theme-toggle-btn:hover { transform: scale(1.08); border-color: #555; }
html[data-theme="light"] .theme-toggle-btn {
  background: #ffffff;
  border-color: #d7dae0;
  color: #e67e22;
  box-shadow: 0 1px 6px rgba(20,24,32,.15);
}

body {
  font-family: 'Segoe UI', Arial, sans-serif;
  background: #0f1117;
  color: #e0e0e0;
  padding: 28px 16px 64px;
  padding-right: 376px;
  min-width: 960px;
}
html[data-theme="light"] body { background: #eef1f5; color: #20242c; }

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
.todo-sidebar {
  position: fixed;
  top: 16px;
  right: 16px;
  width: 340px;
  max-height: calc(100vh - 32px);
  overflow-y: auto;
  z-index: 200;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.todo-sidebar::-webkit-scrollbar { width: 4px; }
.todo-sidebar::-webkit-scrollbar-thumb { background: #2a2d3e; border-radius: 4px; }
.todo-hidden { display: none !important; }

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

/* Python flow nodes */
.c-py-init  { background:#142a14; border-color:#27ae60; color:#82e0aa; }
.c-py-read  { background:#1a2a1a; border-color:#1e8449; color:#58d68d; }
.c-py-out   { background:#2a2010; border-color:#d4ac0d; color:#f4d03f; }

/* Alerta flow nodes */
.c-al-init  { background:#2a1010; border-color:#c0392b; color:#f1948a; }
.c-al-reset { background:#2a1a10; border-color:#e67e22; color:#f0a868; }
.c-al-loop  { background:#1a1030; border-color:#8e44ad; color:#c39bd3; }

/* Alerta macro box — azul (analogo ao VBA) */
.macro-box-al { border: 2.5px solid #1a5276; }
.macro-box-al.clickable:hover {
  border-color: #5dade2;
  box-shadow: 0 0 40px rgba(41,128,185,.35);
  transform: translateY(-4px);
}
.macro-box-al .macro-box-badge { color: #2980b9; }
.macro-box-al .macro-icon      { color: #5dade2; }
.macro-box-al .macro-stat      { background:#1a2340; border:1px solid #2471a3; color:#74b9ff; }

/* Indexados macro box — slate/indigo */
.macro-box-idx { border: 2.5px solid #5a67d8; }
.macro-box-idx.clickable:hover {
  border-color: #a3aef5;
  box-shadow: 0 0 40px rgba(90,103,216,.35);
  transform: translateY(-4px);
}
.macro-box-idx .macro-box-badge { color: #5a67d8; }
.macro-box-idx .macro-icon      { color: #a3aef5; }
.macro-box-idx .macro-stat      { background:#0e1030; border:1px solid #5a67d8; color:#a3aef5; }

/* Renda Fixa macro box — amber/gold */
.macro-box-rf { border: 2.5px solid #c9850a; }
.macro-box-rf.clickable:hover {
  border-color: #f0c97a;
  box-shadow: 0 0 40px rgba(201,133,10,.35);
  transform: translateY(-4px);
}
.macro-box-rf .macro-box-badge { color: #c9850a; }
.macro-box-rf .macro-icon      { color: #f0c97a; }
.macro-box-rf .macro-stat      { background:#2a1a00; border:1px solid #c9850a; color:#f0c97a; }

/* Base de Dados macro box — steel blue */
.macro-box-db { border: 2.5px solid #2e6da4; }
.macro-box-db.clickable:hover {
  border-color: #7fb3d3;
  box-shadow: 0 0 40px rgba(46,109,164,.35);
  transform: translateY(-4px);
}
.macro-box-db .macro-box-badge { color: #2e6da4; }
.macro-box-db .macro-icon      { color: #7fb3d3; }
.macro-box-db .macro-stat      { background:#0a1828; border:1px solid #2e6da4; color:#7fb3d3; }

/* Visao Tecnica (ER/DFD) macro box — indigo */
.macro-box-tech { border: 2.5px solid #6c5ce7; }
.macro-box-tech.clickable:hover {
  border-color: #a29bfe;
  box-shadow: 0 0 40px rgba(108,92,231,.35);
  transform: translateY(-4px);
}
.macro-box-tech .macro-box-badge { color: #6c5ce7; }
.macro-box-tech .macro-icon      { color: #a29bfe; }
.macro-box-tech .macro-stat      { background:#150f2e; border:1px solid #6c5ce7; color:#a29bfe; }
.macro-subbox-tech { border-color: #6c5ce7; }
.macro-subbox-tech.clickable:hover {
  border-color: #a29bfe;
  box-shadow: 0 0 20px rgba(108,92,231,.3);
  transform: translateY(-2px);
}
.macro-subbox-tech .macro-subbox-name { color: #a29bfe; }

/* Sub-caixas dentro de macro-box */
.macro-subboxes {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  margin-top: 10px;
}
.macro-subbox {
  width: 100%;
  border-radius: 10px;
  padding: 10px 14px;
  background: #0f1117;
  border: 1.5px solid #333;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  transition: border-color .2s, box-shadow .2s, transform .2s;
}
.macro-subbox.clickable { cursor: pointer; }
.macro-subbox-vba { border-color: #2980b9; }
.macro-subbox-vba.clickable:hover {
  border-color: #5dade2;
  box-shadow: 0 0 20px rgba(41,128,185,.3);
  transform: translateY(-2px);
}
.macro-subbox-bat { border-color: #7b1fa2; }
.macro-subbox-bat.clickable:hover {
  border-color: #ce93d8;
  box-shadow: 0 0 20px rgba(123,31,162,.3);
  transform: translateY(-2px);
}
.macro-subbox-bat .macro-subbox-name { color: #ce93d8; }
.macro-subbox-name {
  font-size: .82rem;
  font-weight: 700;
  color: #e0e0e0;
}
.macro-subbox-hint {
  font-size: .65rem;
  color: #555;
}

/* Futuros macro box — teal */
.macro-box-fut { border: 2.5px solid #148f77; }
.macro-box-fut.clickable:hover {
  border-color: #76d7c4;
  box-shadow: 0 0 40px rgba(20,143,119,.35);
  transform: translateY(-4px);
}
.macro-box-fut .macro-box-badge { color: #148f77; }
.macro-box-fut .macro-icon      { color: #76d7c4; }
.macro-box-fut .macro-stat      { background:#0e2420; border:1px solid #148f77; color:#76d7c4; }

/* Batimento OC3 flow nodes */
.c-oc3-init  { background:#001a1a; border-color:#006064; color:#80cbc4; }
.c-oc3-loop  { background:#001520; border-color:#0277bd; color:#81d4fa; }
.c-oc3-grp   { background:#001220; border-color:#01579b; color:#b3e5fc; }
.c-oc3-out   { background:#2a2010; border-color:#d4ac0d; color:#f4d03f; }

/* OC3 sub-caixa */
.macro-subbox-oc3 { border-color: #006064; }
.macro-subbox-oc3.clickable:hover {
  border-color: #80cbc4;
  box-shadow: 0 0 20px rgba(0,96,100,.3);
  transform: translateY(-2px);
}
.macro-subbox-oc3 .macro-subbox-name { color: #80cbc4; }

/* Batimento Offshore flow nodes */
.c-off-init   { background:#1c0900; border-color:#bf360c; color:#ffab91; }
.c-off-query  { background:#1a0a00; border-color:#e64a19; color:#ff8a65; }
.c-off-merge  { background:#1a0c00; border-color:#f4511e; color:#ffccbc; }
.c-off-estrat { background:#1a1000; border-color:#f57f17; color:#ffe082; }
.c-off-out    { background:#2a2010; border-color:#d4ac0d; color:#f4d03f; }

/* Offshore sub-caixa */
.macro-subbox-off { border-color: #bf360c; }
.macro-subbox-off.clickable:hover {
  border-color: #ffab91;
  box-shadow: 0 0 20px rgba(191,54,12,.3);
  transform: translateY(-2px);
}
.macro-subbox-off .macro-subbox-name { color: #ffab91; }
.macro-subbox-db { border-color: #2e6da4; }
.macro-subbox-db.clickable:hover {
  border-color: #7fb3d3;
  box-shadow: 0 0 14px rgba(46,109,164,.4);
}
.macro-subbox-db .macro-subbox-name { color: #7fb3d3; }
.macro-subbox-rf { border-color: #c9850a; }
.macro-subbox-rf.clickable:hover {
  border-color: #f0c97a;
  box-shadow: 0 0 20px rgba(201,133,10,.3);
  transform: translateY(-2px);
}
.macro-subbox-rf .macro-subbox-name { color: #f0c97a; }

/* Preço Justo ETF flow nodes */
.c-pj-init  { background:#00191a; border-color:#00838f; color:#80deea; }
.c-pj-bbg   { background:#001a10; border-color:#2e7d32; color:#a5d6a7; }
.c-pj-calc  { background:#001422; border-color:#0277bd; color:#81d4fa; }
.c-pj-out   { background:#2a2010; border-color:#d4ac0d; color:#f4d03f; }

/* Preço Justo sub-caixa */
.macro-subbox-pj { border-color: #00838f; }
.macro-subbox-pj.clickable:hover {
  border-color: #80deea;
  box-shadow: 0 0 20px rgba(0,131,143,.3);
  transform: translateY(-2px);
}
.macro-subbox-pj .macro-subbox-name { color: #80deea; }

/* Batimento flow nodes */
.c-bat-init    { background:#1a0a2e; border-color:#7b1fa2; color:#ce93d8; }
.c-bat-triage  { background:#1e0b30; border-color:#9c27b0; color:#e1bee7; }
.c-bat-parallel{ background:#160828; border-color:#6a1b9a; color:#ce93d8; }
.c-bat-enrich  { background:#0d1a2a; border-color:#1565c0; color:#90caf9; }
.c-bat-out     { background:#2a2010; border-color:#d4ac0d; color:#f4d03f; }

/* SAC_Cota flow nodes — steel blue */
.c-db-init     { background:#091828; border-color:#2e6da4; color:#7fb3d3; }
.c-db-data     { background:#0a1e30; border-color:#3a82b5; color:#90c4e4; }
.c-db-query    { background:#071a20; border-color:#1a8a7a; color:#5dd6c4; }
.c-db-treat    { background:#0e1428; border-color:#4a5a9a; color:#9aabdc; }
.c-db-fidc     { background:#180e28; border-color:#6a3a9a; color:#c49ada; }
.c-db-meta     { background:#141a10; border-color:#4a7a3a; color:#8acc7a; }
.c-db-split    { background:#201808; border-color:#9a6a1a; color:#daa84a; }
.c-db-insert   { background:#0a2010; border-color:#1a7a3a; color:#5acc8a; }

/* Futuros flow nodes */
.c-fut-init { background:#0d2420; border-color:#17a589; color:#76d7c4; }
.c-fut-proc { background:#162010; border-color:#27ae60; color:#82e0aa; }
.c-fut-out  { background:#2a2010; border-color:#d4ac0d; color:#f4d03f; }

/* Todo Futuros — teal */
.todo-panel-fut { border: 1.5px solid #0e6655; }
.todo-panel-fut .todo-title { color: #76d7c4; }
.todo-panel-fut .todo-progress-fill { background:linear-gradient(90deg,#0e5446,#17a589); }
.todo-panel-fut .todo-check input[type=checkbox] { accent-color:#17a589; }
.todo-panel-fut .todo-edit-input  { border:1px solid #17a589; }
.todo-panel-fut .todo-input:focus { border-color:#17a589; }
.todo-panel-fut .todo-add-btn     { background:#0a2820; border:1px solid #17a589; color:#76d7c4; }
.todo-panel-fut .todo-add-btn:hover { background:#17a589; color:#fff; }
.todo-panel-fut .todo-notes:focus { border-color:#17a589; }

/* Moldura Python group — verde */
.macro-group-py {
  border-color: #1e8449;
  background: rgba(30,132,73,.04);
}
.macro-group-py .macro-group-label { color: #1e8449; }

/* Moldura VBA group */
.macro-group {
  display: flex;
  flex-direction: column;
  gap: 16px;
  border: 2px solid #2471a3;
  border-radius: 22px;
  padding: 26px 16px 18px;
  position: relative;
  background: rgba(36,113,163,.04);
}
.macro-group-label {
  position: absolute;
  top: -12px;
  left: 50%;
  transform: translateX(-50%);
  background: #0c0e14;
  padding: 0 14px;
  font-size: .6rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .1em;
  color: #2471a3;
  white-space: nowrap;
}

/* Todo Alerta — azul variante */
.todo-panel-al { border: 1.5px solid #1b4f72; }
.todo-panel-al .todo-title { color: #aed6f1; }
.todo-panel-al .todo-progress-fill { background:linear-gradient(90deg,#1a4971,#2e86c1); }
.todo-panel-al .todo-check input[type=checkbox] { accent-color:#2e86c1; }
.todo-panel-al .todo-edit-input  { border:1px solid #2e86c1; }
.todo-panel-al .todo-input:focus { border-color:#2e86c1; }
.todo-panel-al .todo-add-btn     { background:#0d2b45; border:1px solid #2e86c1; color:#aed6f1; }
.todo-panel-al .todo-add-btn:hover { background:#2e86c1; color:#fff; }
.todo-panel-al .todo-notes:focus { border-color:#2e86c1; }

/* STATUS BADGE */
.node  { position: relative; }
.group { position: relative; }
.s-badge {
  position: absolute;
  top: -11px;
  right: 10px;
  display: flex;
  align-items: center;
  gap: 4px;
  border-radius: 12px;
  padding: 2px 9px 2px 7px;
  font-size: .6rem;
  font-weight: 700;
  cursor: pointer;
  border: 1.5px solid;
  z-index: 10;
  transition: opacity .15s, transform .15s;
  white-space: nowrap;
  letter-spacing: .04em;
  text-transform: uppercase;
  font-family: 'Segoe UI', Arial, sans-serif;
}
.s-badge:hover { opacity: .8; transform: scale(1.05); }
.s-todo  { background:#111; border-color:#3a3a3a; color:#666; }
.s-doing { background:#2a1e00; border-color:#e67e22; color:#e67e22; }
.s-done  { background:#0a2010; border-color:#27ae60; color:#27ae60; }
.s-dot { width:7px; height:7px; border-radius:50%; flex-shrink:0; }
.s-todo  .s-dot { background:#444; }
.s-doing .s-dot { background:#e67e22; box-shadow:0 0 5px #e67e2280; }
.s-done  .s-dot { background:#27ae60; box-shadow:0 0 5px #27ae6080; }

/* SQL Modal */
.sql-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.78);
  z-index: 2000;
  align-items: center;
  justify-content: center;
}
.sql-overlay.open { display: flex; }
.sql-modal {
  background: #13151c;
  border: 1.5px solid #27ae60;
  border-radius: 12px;
  padding: 22px 24px 20px;
  width: min(760px, 92vw);
  max-height: 82vh;
  display: flex;
  flex-direction: column;
  gap: 12px;
  box-shadow: 0 0 60px rgba(39,174,96,.25);
}
.sql-modal-hdr {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.sql-modal-title {
  font-size: .88rem;
  font-weight: 700;
  color: #82e0aa;
}
.sql-modal-fonte {
  font-size: .7rem;
  color: #555;
  margin-top: 2px;
}
.sql-modal-close {
  background: none;
  border: none;
  color: #444;
  font-size: 1.3rem;
  cursor: pointer;
  line-height: 1;
  padding: 0 4px;
  transition: color .15s;
  flex-shrink: 0;
}
.sql-modal-close:hover { color: #e74c3c; }
.sql-code {
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: .76rem;
  color: #c8d8c8;
  background: rgba(0,0,0,.35);
  border-radius: 6px;
  padding: 14px 16px;
  white-space: pre;
  overflow: auto;
  line-height: 1.75;
  flex: 1;
  min-height: 0;
}
.tag.clickable { cursor: pointer; -webkit-tap-highlight-color: transparent; }
.tag.clickable:hover { opacity: .82; }
.tag.clickable:active, .tag.clickable:focus { opacity: 1; outline: none; }

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

.legend        { display:flex; gap:16px; flex-wrap:wrap; justify-content:center; margin-top:36px; margin-bottom:36px; font-size:.72rem; color:#aaa; }
.legend-item   { display:flex; align-items:center; gap:6px; }
.legend-dot    { width:12px; height:12px; border-radius:3px; flex-shrink:0; }

/* PAGES */
.pg { display:none; }
.pg.active { display:block; }

/* PAGE 1 — macro */
.pg-macro.active {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 40px 16px;
}
.macro-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 36px;
}
.macro-workbook {
  font-size: .85rem;
  color: #666;
  letter-spacing: .06em;
  text-transform: uppercase;
}
.macro-boxes {
  display: flex;
  gap: 28px;
  align-items: stretch;
  flex-wrap: wrap;
  justify-content: center;
}
.macro-box {
  width: 320px;
  border-radius: 18px;
  padding: 40px 32px 32px;
  background: #0c0e14;
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}
.macro-box.clickable {
  cursor: pointer;
  transition: border-color .2s, box-shadow .2s, transform .2s;
}
.macro-box-vba {
  border: 2.5px solid #2980b9;
}
.macro-box-vba.clickable:hover {
  border-color: #5dade2;
  box-shadow: 0 0 40px rgba(41,128,185,.35);
  transform: translateY(-4px);
}
.macro-box-py {
  border: 2.5px solid #27ae60;
}
.macro-box-py.clickable:hover {
  border-color: #58d68d;
  box-shadow: 0 0 40px rgba(39,174,96,.35);
  transform: translateY(-4px);
}
.macro-box-fe { border: 2.5px solid #e67e22; }
.macro-box-fe.clickable:hover {
  border-color: #f0a868;
  box-shadow: 0 0 40px rgba(230,126,34,.35);
  transform: translateY(-4px);
}
.macro-box-badge {
  position: absolute;
  top: -13px;
  left: 50%;
  transform: translateX(-50%);
  background: #0c0e14;
  padding: 0 14px;
  font-size: .65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .12em;
  white-space: nowrap;
}
.macro-box-vba .macro-box-badge { color: #2980b9; }
.macro-box-py  .macro-box-badge { color: #27ae60; }
.macro-box-fe  .macro-box-badge { color: #e67e22; }
.macro-icon {
  font-size: 3.2rem;
  font-weight: 800;
  letter-spacing: .08em;
  line-height: 1;
}
.macro-box-vba .macro-icon { color: #5dade2; }
.macro-box-py  .macro-icon { color: #58d68d; }
.macro-box-fe  .macro-icon { color: #f0a868; }
.macro-sub {
  font-size: .95rem;
  font-weight: 700;
  color: #e0e0e0;
  text-align: center;
}
.macro-hint {
  font-size: .72rem;
  color: #555;
  margin-top: 4px;
}
.macro-stats {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
  justify-content: center;
}
.macro-stat {
  border-radius: 20px;
  padding: 3px 10px;
  font-size: .67rem;
  font-weight: 600;
}
.macro-box-vba .macro-stat { background:#1a2340; border:1px solid #2471a3; color:#74b9ff; }
.macro-box-py  .macro-stat { background:#0f2a1a; border:1px solid #1e8449; color:#82e0aa; }
.macro-box-fe  .macro-stat { background:#2a1500; border:1px solid #a04000; color:#f0a868; }
.macro-arrow-hint {
  font-size: 1.4rem;
  color: #333;
  animation: pulse 1.8s ease-in-out infinite;
}
@keyframes pulse { 0%,100%{opacity:.3} 50%{opacity:1} }

/* PAGE 2 — detail */
.pg-detail.active { display:block; }
.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #13151c;
  border: 1.5px solid #2a2d3e;
  color: #74b9ff;
  border-radius: 8px;
  padding: 7px 16px;
  font-size: .78rem;
  font-weight: 600;
  cursor: pointer;
  margin-bottom: 24px;
  transition: border-color .15s, background .15s;
}
.back-btn:hover { border-color: #2980b9; background: #1a2340; }

/* PAGE BOX */
.page-box {
  border: 2.5px solid #2980b9;
  border-radius: 16px;
  padding: 24px 20px 28px;
  background: #0c0e14;
  max-width: 1640px;
  margin: 0 auto;
  position: relative;
}
.page-box-title {
  position: absolute;
  top: -14px;
  left: 32px;
  background: #0c0e14;
  padding: 0 12px;
  font-size: .78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .1em;
  color: #2980b9;
  white-space: nowrap;
}

/* TO DO PANEL */
.todo-panel {
  background: #13151c;
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.todo-panel-vba { border: 1.5px solid #1f4e79; }
.todo-panel-py  { border: 1.5px solid #1e6b3c; }
.todo-panel-fe  { border: 1.5px solid #7d4200; }
.todo-panel-bat { border: 1.5px solid #4a148c; }
.todo-panel-pj  { border: 1.5px solid #004d52; }
.todo-panel-off { border: 1.5px solid #7f2200; }
.todo-panel-oc3 { border: 1.5px solid #004d40; }

.todo-header { display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; }
.todo-title  { font-size:.9rem; font-weight:700; }
.todo-panel-vba .todo-title { color:#74b9ff; }
.todo-panel-py  .todo-title { color:#82e0aa; }
.todo-panel-fe  .todo-title { color:#f0a868; }
.todo-panel-bat .todo-title { color:#ce93d8; }
.todo-panel-pj  .todo-title { color:#80deea; }
.todo-panel-off .todo-title { color:#ffab91; }
.todo-panel-oc3 .todo-title { color:#80cbc4; }

.todo-counter { font-size:.7rem; color:#888; background:#1e2030; padding:3px 8px; border-radius:12px; }
.todo-progress-wrap { background:#1e2030; border-radius:4px; height:6px; overflow:hidden; }
.todo-progress-fill { height:100%; border-radius:4px; transition:width .35s ease; }
.todo-panel-vba .todo-progress-fill { background:linear-gradient(90deg,#1a5276,#2980b9); }
.todo-panel-py  .todo-progress-fill { background:linear-gradient(90deg,#1e8449,#2ecc71); }
.todo-panel-fe  .todo-progress-fill { background:linear-gradient(90deg,#7d3c00,#e67e22); }
.todo-panel-bat .todo-progress-fill { background:linear-gradient(90deg,#4a148c,#9c27b0); }
.todo-panel-pj  .todo-progress-fill { background:linear-gradient(90deg,#004d52,#00838f); }
.todo-panel-off .todo-progress-fill { background:linear-gradient(90deg,#7f2200,#bf360c); }
.todo-panel-oc3 .todo-progress-fill { background:linear-gradient(90deg,#004d40,#006064); }

.todo-section-title { font-size:.7rem; font-weight:700; text-transform:uppercase; letter-spacing:.06em; color:#555; margin-bottom:6px; }

.todo-list { display:flex; flex-direction:column; gap:4px; max-height:280px; overflow-y:auto; padding-right:2px; }
.todo-list::-webkit-scrollbar { width:4px; }
.todo-list::-webkit-scrollbar-thumb { background:#333; border-radius:4px; }

.todo-item { display:flex; align-items:flex-start; gap:6px; padding:6px 8px; border-radius:6px; background:#1a1d28; border:1px solid #252840; transition:background .15s; }
.todo-item:hover { background:#1e2235; }
.todo-item.todo-done .todo-text { opacity:.45; text-decoration:line-through; }
.todo-check { display:flex; align-items:flex-start; gap:7px; flex:1; cursor:pointer; min-width:0; }
.todo-check input[type=checkbox] { margin-top:2px; flex-shrink:0; width:14px; height:14px; cursor:pointer; }
.todo-panel-vba .todo-check input[type=checkbox] { accent-color:#2980b9; }
.todo-panel-py  .todo-check input[type=checkbox] { accent-color:#27ae60; }
.todo-panel-fe  .todo-check input[type=checkbox] { accent-color:#e67e22; }
.todo-panel-bat .todo-check input[type=checkbox] { accent-color:#9c27b0; }
.todo-panel-pj  .todo-check input[type=checkbox] { accent-color:#00838f; }
.todo-panel-off .todo-check input[type=checkbox] { accent-color:#bf360c; }
.todo-panel-oc3 .todo-check input[type=checkbox] { accent-color:#006064; }
.todo-text  { font-size:.74rem; color:#d0d0d0; line-height:1.45; word-break:break-word; }
.todo-edit-input { font-size:.74rem; color:#e0e0e0; background:#0f1117; border-radius:4px; padding:2px 6px; flex:1; min-width:0; outline:none; }
.todo-panel-vba .todo-edit-input { border:1px solid #2980b9; }
.todo-panel-py  .todo-edit-input { border:1px solid #27ae60; }
.todo-panel-fe  .todo-edit-input { border:1px solid #e67e22; }
.todo-panel-bat .todo-edit-input { border:1px solid #9c27b0; }
.todo-panel-pj  .todo-edit-input { border:1px solid #00838f; }
.todo-panel-off .todo-edit-input { border:1px solid #bf360c; }
.todo-panel-oc3 .todo-edit-input { border:1px solid #006064; }
.todo-del { background:none; border:none; color:#444; cursor:pointer; font-size:.72rem; padding:0 2px; flex-shrink:0; line-height:1; transition:color .15s; }
.todo-del:hover { color:#e74c3c; }

.todo-add { display:flex; gap:6px; }
.todo-input { flex:1; background:#1a1d28; border:1px solid #2a2d3e; border-radius:6px; color:#e0e0e0; padding:6px 10px; font-size:.74rem; outline:none; transition:border-color .15s; }
.todo-input::placeholder { color:#3a3d50; }
.todo-panel-vba .todo-input:focus { border-color:#2980b9; }
.todo-panel-py  .todo-input:focus { border-color:#27ae60; }
.todo-panel-fe  .todo-input:focus { border-color:#e67e22; }
.todo-panel-bat .todo-input:focus { border-color:#9c27b0; }
.todo-panel-pj  .todo-input:focus { border-color:#00838f; }
.todo-panel-off .todo-input:focus { border-color:#bf360c; }
.todo-panel-oc3 .todo-input:focus { border-color:#006064; }
.todo-add-btn { border-radius:6px; width:32px; font-size:1.1rem; cursor:pointer; transition:background .15s; flex-shrink:0; }
.todo-panel-vba .todo-add-btn { background:#1e3a5f; border:1px solid #2980b9; color:#74b9ff; }
.todo-panel-vba .todo-add-btn:hover { background:#2980b9; color:#fff; }
.todo-panel-py  .todo-add-btn { background:#1e4a30; border:1px solid #27ae60; color:#2ecc71; }
.todo-panel-py  .todo-add-btn:hover { background:#27ae60; color:#fff; }
.todo-panel-fe  .todo-add-btn { background:#3d2000; border:1px solid #e67e22; color:#f0a868; }
.todo-panel-fe  .todo-add-btn:hover { background:#e67e22; color:#fff; }
.todo-panel-bat .todo-add-btn { background:#200030; border:1px solid #9c27b0; color:#ce93d8; }
.todo-panel-bat .todo-add-btn:hover { background:#9c27b0; color:#fff; }
.todo-panel-pj  .todo-add-btn { background:#001a1c; border:1px solid #00838f; color:#80deea; }
.todo-panel-pj  .todo-add-btn:hover { background:#00838f; color:#fff; }
.todo-panel-off .todo-add-btn { background:#220800; border:1px solid #bf360c; color:#ffab91; }
.todo-panel-off .todo-add-btn:hover { background:#bf360c; color:#fff; }
.todo-panel-oc3 .todo-add-btn { background:#001a18; border:1px solid #006064; color:#80cbc4; }
.todo-panel-oc3 .todo-add-btn:hover { background:#006064; color:#fff; }

.todo-notes { width:100%; min-height:80px; background:#1a1d28; border:1px solid #2a2d3e; border-radius:6px; color:#d0d0d0; padding:8px 10px; font-size:.74rem; font-family:'Segoe UI',Arial,sans-serif; resize:vertical; outline:none; line-height:1.55; transition:border-color .15s; }
.todo-notes::placeholder { color:#3a3d50; }
.todo-panel-vba .todo-notes:focus { border-color:#2980b9; }
.todo-panel-py  .todo-notes:focus { border-color:#27ae60; }
.todo-panel-fe  .todo-notes:focus { border-color:#e67e22; }
.todo-panel-bat .todo-notes:focus { border-color:#9c27b0; }
.todo-panel-pj  .todo-notes:focus { border-color:#00838f; }
.todo-panel-off .todo-notes:focus { border-color:#bf360c; }
.todo-panel-oc3 .todo-notes:focus { border-color:#006064; }
.todo-reset-btn { background:none; border:1px solid #2a2d3e; color:#555; border-radius:6px; padding:5px 10px; font-size:.68rem; cursor:pointer; transition:color .15s,border-color .15s; align-self:flex-end; }
.todo-reset-btn:hover { color:#aaa; border-color:#555; }

/* ── CALENDARIO DE ENTREGAS ─────────────────────────────────────── */
#cal-section {
  display: none;
  width: 100%;
  max-width: 700px;
  margin: 48px auto 64px;
  padding: 0 16px;
  box-sizing: border-box;
}
#cal-section.cal-visible { display: block; }
.kcal-section-title {
  font-size: .68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .1em;
  color: #444;
  text-align: center;
  margin-bottom: 14px;
}
/* container */
.kcal {
  background: #1a1d2e;
  border-radius: 14px;
  overflow: hidden;
  width: 100%;
  user-select: none;
  box-shadow: 0 4px 32px rgba(0,0,0,.5);
}
/* header */
.kcal-hdr {
  display: flex;
  align-items: center;
  background: #12152a;
  padding: 16px 20px 14px;
  border-bottom: 1px solid #252840;
}
.kcal-hdr-label {
  flex: 1;
  text-align: center;
  font-size: 1rem;
  font-weight: 700;
  color: #e8eaf6;
  letter-spacing: .06em;
}
.kcal-btn {
  background: none;
  border: none;
  color: #888;
  font-size: 1.3rem;
  width: 34px; height: 34px;
  border-radius: 50%;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: background .14s, color .14s;
  flex-shrink: 0;
  line-height: 1;
}
.kcal-btn:hover { background: rgba(255,255,255,.1); color: #fff; }
/* weekday row */
.kcal-dow {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  background: #161928;
  border-bottom: 1px solid #252840;
}
.kcal-dow b {
  display: block;
  text-align: center;
  font-size: .62rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .08em;
  color: #6064a0;
  padding: 9px 0;
  font-style: normal;
}
.kcal-dow b.kfri { color: #d4a017; }
/* grid */
.kcal-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 1px;
  background: #252840;
}
/* day cell */
.kcal-day {
  background: #1e2138;
  min-height: 78px;
  padding: 8px 9px 6px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  transition: background .1s;
  box-sizing: border-box;
}
.kcal-day:hover { background: #252a46; }
.kcal-empty { background: #171a2c !important; cursor: default !important; pointer-events: none !important; }
/* Sexta: mesmo visual das outras datas */
.kcal-today { background: #0e2448; }
.kcal-today:hover { background: #122c56; }
/* day number circle */
.kcal-num {
  width: 28px; height: 28px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: .8rem;
  font-weight: 700;
  color: #b0b4d8;
  flex-shrink: 0;
  line-height: 1;
  transition: background .12s, color .12s;
}
.kcal-day:hover .kcal-num { color: #d8dcff; }
.kcal-today .kcal-num { background: #2980b9; color: #fff; }
.kcal-today.kcal-fri .kcal-num { background: #2980b9; color: #fff; }
.kcal-hasnote:not(.kcal-today) .kcal-num { background: #2471a3; color: #fff; }
.kcal-today.kcal-hasnote .kcal-num { background: #2980b9; color: #fff; }
/* Data de entrega — laranja manual */
.kcal-entrega       { background: #271c00 !important; }
.kcal-entrega:hover { background: #322300 !important; }
.kcal-entrega .kcal-num { background: #e67e22 !important; color: #fff !important; }
.kcal-entrega:hover .kcal-num { background: #f39c12 !important; }
.kcal-entrega.kcal-hasnote .kcal-num { background: #f0b429 !important; color: #111 !important; }
.kcal-entrega.kcal-today .kcal-num { background: #2980b9 !important; box-shadow: 0 0 0 2.5px #e67e22 !important; }
/* Toggle de entrega no modal */
.kcal-delivery-row { margin-bottom: 2px; }
.kcal-delivery-btn {
  width: 100%;
  display: flex; align-items: center; gap: 10px;
  background: #1a1d2e; border: 1.5px solid #2a2d42;
  color: #6064a0; border-radius: 8px;
  padding: 9px 14px; font-size: .78rem; font-weight: 600;
  cursor: pointer; transition: all .15s;
  font-family: 'Segoe UI', Arial, sans-serif;
  text-align: left;
}
.kcal-delivery-btn:hover { border-color: #e67e22; color: #d0843a; }
.kcal-delivery-btn.active {
  background: #2a1600; border-color: #e67e22; color: #f0a050;
}
.kcal-delivery-btn .kdot {
  width: 10px; height: 10px; border-radius: 50%;
  background: #2a2d42; flex-shrink: 0;
  transition: background .15s;
}
.kcal-delivery-btn.active .kdot { background: #e67e22; box-shadow: 0 0 6px #e67e2280; }
/* note preview inside cell */
.kcal-prev {
  margin-top: 5px;
  font-size: .62rem;
  color: #4e5278;
  line-height: 1.45;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-word;
  flex: 1;
}
.kcal-hasnote .kcal-prev { color: #9094c0; }
.kcal-fri.kcal-hasnote .kcal-prev { color: #b08a30; }

/* ── Modal ──────────────────────────────────────────────────────── */
.kcal-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.86);
  z-index: 4000;
  align-items: center;
  justify-content: center;
}
.kcal-overlay.open { display: flex; }
.kcal-modal {
  background: #13151c;
  border: 1.5px solid #252840;
  border-radius: 14px;
  padding: 22px 24px 18px;
  width: min(480px, 92vw);
  display: flex;
  flex-direction: column;
  gap: 14px;
  box-shadow: 0 8px 80px rgba(0,0,0,.9);
}
.kcal-mhdr { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
.kcal-mdate { font-size: .9rem; font-weight: 700; color: #ddd; line-height: 1.35; flex: 1; }
.kcal-mdate.fri { color: #f39c12; }
.kcal-mclose {
  background: none; border: none; color: #444;
  font-size: 1.4rem; cursor: pointer; flex-shrink: 0; line-height: 1; padding: 0;
  transition: color .15s;
}
.kcal-mclose:hover { color: #e74c3c; }
.kcal-mta {
  width: 100%; min-height: 160px;
  background: #1a1d28; border: 1.5px solid #252840; border-radius: 8px;
  color: #d0d0d0; padding: 10px 12px;
  font-size: .83rem; font-family: 'Segoe UI', Arial, sans-serif;
  resize: vertical; outline: none; line-height: 1.65;
  transition: border-color .15s;
}
.kcal-mta::placeholder { color: #2a2d40; }
.kcal-mta:focus { border-color: #3a4262; }
.kcal-mfooter { display: flex; align-items: center; gap: 8px; }
.kcal-mhint { flex: 1; font-size: .6rem; color: #2a2d40; }
.kcal-msave {
  background: #1a3a5c; border: 1.5px solid #2980b9;
  color: #74b9ff; border-radius: 7px; padding: 8px 24px;
  font-size: .78rem; font-weight: 700; cursor: pointer;
  transition: background .14s;
}
.kcal-msave:hover { background: #2980b9; color: #fff; }
.kcal-mclear {
  background: none; border: 1px solid #252840; color: #444;
  border-radius: 7px; padding: 8px 14px;
  font-size: .78rem; cursor: pointer;
  transition: color .14s, border-color .14s;
}
.kcal-mclear:hover { color: #e74c3c; border-color: #7b241c; }

/* ── LIGHT THEME — sidebar de To Do e modais (fora de #theme-scope) ──────── */
html[data-theme="light"] .todo-sidebar::-webkit-scrollbar-thumb { background: #c7cbd3; }
html[data-theme="light"] .todo-panel { background: #ffffff; box-shadow: 0 1px 4px rgba(20,24,32,.08); }
html[data-theme="light"] .todo-counter { background: #eef0f4; color: #666; }
html[data-theme="light"] .todo-progress-wrap { background: #e7e9ee; }
html[data-theme="light"] .todo-section-title { color: #8a8f98; }
html[data-theme="light"] .todo-list::-webkit-scrollbar-thumb { background: #d3d6dc; }
html[data-theme="light"] .todo-item { background: #f6f7f9; border-color: #e3e5ea; }
html[data-theme="light"] .todo-item:hover { background: #eef0f4; }
html[data-theme="light"] .todo-text { color: #2b2f36; }
html[data-theme="light"] .todo-edit-input { background: #fff; color: #1a1a1a; }
html[data-theme="light"] .todo-del { color: #b7bcc4; }
html[data-theme="light"] .todo-input { background: #fff; color: #1a1a1a; border-color: #d7dae0; }
html[data-theme="light"] .todo-input::placeholder { color: #aab0bb; }
html[data-theme="light"] .todo-notes { background: #fff; color: #2b2f36; border-color: #d7dae0; }
html[data-theme="light"] .todo-notes::placeholder { color: #aab0bb; }
html[data-theme="light"] .todo-reset-btn { border-color: #d7dae0; color: #8a8f98; }
html[data-theme="light"] .todo-title { filter: brightness(.7) saturate(1.3); }

html[data-theme="light"] .sql-overlay { background: rgba(30,34,42,.45); }
html[data-theme="light"] .sql-modal { background: #ffffff; box-shadow: 0 20px 60px rgba(20,24,32,.2); }
html[data-theme="light"] .sql-modal-title { filter: brightness(.65) saturate(1.3); }
html[data-theme="light"] .sql-modal-fonte { color: #767b85; }
html[data-theme="light"] .sql-modal-close { color: #9aa0aa; }
html[data-theme="light"] .sql-code { color: #1f2430; background: #f2f4f6; }

html[data-theme="light"] .kcal-overlay { background: rgba(30,34,42,.5); }
html[data-theme="light"] .kcal-modal { background: #ffffff; box-shadow: 0 8px 60px rgba(20,24,32,.25); }
html[data-theme="light"] .kcal-mdate { color: #20242c; }
html[data-theme="light"] .kcal-mclose { color: #9aa0aa; }
html[data-theme="light"] .kcal-mta { background: #f6f7f9; color: #2b2f36; border-color: #d7dae0; }
html[data-theme="light"] .kcal-mta::placeholder { color: #aab0bb; }
html[data-theme="light"] .kcal-msave { filter: brightness(.92); }
html[data-theme="light"] .kcal-mclear { color: #9aa0aa; border-color: #d7dae0; }
html[data-theme="light"] .kcal-mhint { color: #c3c7cf; }

/* ── VISAO TECNICA — ER / DFD (origem -> destino) ─────────────────────────── */
.erd-toolbar { display:flex; justify-content:center; margin-bottom:10px; }
.erd-group { width:100%; max-width:1180px; margin:0 auto 34px; }
.erd-group-title {
  font-size: .78rem; font-weight:700; text-transform:uppercase; letter-spacing:.08em;
  color:#aaa; margin-bottom:14px; padding-bottom:8px; border-bottom:1px solid #252840;
  display:flex; align-items:center; gap:10px;
}
.erd-group-count { font-size:.65rem; font-weight:600; color:#666; text-transform:none; letter-spacing:0; }
.erd-rows { display:flex; flex-direction:column; gap:10px; }
.erd-row {
  display:flex; align-items:stretch; gap:0;
  border-radius: 10px;
  background: rgba(255,255,255,.015);
  border: 1px solid #1c1f2c;
  padding: 10px 14px;
  transition: border-color .15s, background .15s;
}
.erd-row:hover { border-color:#333; background: rgba(255,255,255,.03); }
.erd-node {
  flex: 0 0 250px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1.5px solid #333;
  background: #14161f;
}
.erd-node-tag { font-size:.58rem; font-weight:700; text-transform:uppercase; letter-spacing:.08em; opacity:.65; }
.erd-node-name { font-size:.78rem; font-weight:700; line-height:1.3; word-break:break-word; }
.erd-node-sub  { font-size:.66rem; opacity:.7; line-height:1.3; word-break:break-word; }
.erd-node-origem { border-left-width:4px; }
.erd-node-destino { border-color:#2a2d3e; border-right:4px solid #566; }
.erd-arrow-wrap {
  flex: 1;
  min-width: 130px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  padding: 0 14px;
  position: relative;
}
.erd-arrow-label {
  font-size: .68rem;
  font-weight: 700;
  color: #ccc;
  text-align: center;
  line-height: 1.2;
}
.erd-arrow-label.clickable { cursor: pointer; }
.erd-arrow-label.clickable:hover { color: #fff; }
.erd-arrow-hint { font-size: .58rem; opacity: .45; font-weight: 400; }
.erd-arrow-line {
  position: relative;
  width: 100%;
  height: 2px;
  background: #3a3d50;
  margin: 3px 0;
}
.erd-arrow-line::after {
  content: '';
  position: absolute;
  right: -1px;
  top: 50%;
  transform: translateY(-50%);
  border-top: 5px solid transparent;
  border-bottom: 5px solid transparent;
  border-left: 8px solid #3a3d50;
}
.erd-card {
  font-size: .6rem;
  font-weight: 700;
  padding: 1px 8px;
  border-radius: 10px;
  border: 1px solid #444;
  background: #1e2030;
  color: #ccc;
  letter-spacing: .03em;
  white-space: nowrap;
}
.erd-card-11 { border-color:#2980b9; color:#74b9ff; background:#132436; }
.erd-card-n1 { border-color:#e67e22; color:#f0a868; background:#2a1c0c; }
.erd-card-1n { border-color:#27ae60; color:#82e0aa; background:#0f2419; }
.erd-legend-note { text-align:center; font-size:.68rem; color:#666; margin:-10px auto 30px; max-width:760px; line-height:1.6; }
"""

# ── JavaScript ────────────────────────────────────────────────────────────────

TODO_JS_TEMPLATE = """
<script>
(function() {
  function clone(x) { return JSON.parse(JSON.stringify(x)); }

  function makeTodo(p, storageKey, defaultItems) {
    var state;

    function load() {
      try { var s = localStorage.getItem(storageKey); if (s) return JSON.parse(s); } catch(e) {}
      return { items: clone(defaultItems), notes: '' };
    }
    function save() { localStorage.setItem(storageKey, JSON.stringify(state)); }

    function render() {
      var list    = document.getElementById(p + '-list');
      var notesEl = document.getElementById(p + '-notes');
      var counter = document.getElementById(p + '-counter');
      var fill    = document.getElementById(p + '-progress');
      var done = state.items.filter(function(i) { return i.done; }).length;
      var total = state.items.length;
      if (counter) counter.textContent = done + '/' + total + ' concluidos';
      if (fill)    fill.style.width = (total ? (done / total * 100) : 0) + '%';
      if (notesEl && notesEl !== document.activeElement) notesEl.value = state.notes || '';
      if (!list) return;
      list.innerHTML = '';
      state.items.forEach(function(item, idx) {
        var div = document.createElement('div');
        div.className = 'todo-item' + (item.done ? ' todo-done' : '');
        var label = document.createElement('label');
        label.className = 'todo-check';
        var cb = document.createElement('input');
        cb.type = 'checkbox'; cb.checked = item.done;
        (function(i) { cb.addEventListener('change', function() { toggle(i); }); })(idx);
        var span = document.createElement('span');
        span.className = 'todo-text'; span.textContent = item.text;
        (function(i, sp) { sp.addEventListener('dblclick', function() { edit(i, sp); }); })(idx, span);
        var del = document.createElement('button');
        del.className = 'todo-del'; del.title = 'Remover'; del.textContent = 'x';
        (function(i) { del.addEventListener('click', function() { remove(i); }); })(idx);
        label.appendChild(cb); label.appendChild(span);
        div.appendChild(label); div.appendChild(del); list.appendChild(div);
      });
    }

    function toggle(idx) { state.items[idx].done = !state.items[idx].done; save(); render(); }
    function remove(idx) { state.items.splice(idx, 1); save(); render(); }

    function edit(idx, spanEl) {
      var orig = state.items[idx].text;
      var inp = document.createElement('input');
      inp.type = 'text'; inp.value = orig; inp.className = 'todo-edit-input';
      spanEl.replaceWith(inp); inp.focus(); inp.select();
      var committed = false;
      function commit() {
        if (committed) return; committed = true;
        var v = inp.value.trim(); if (v) state.items[idx].text = v;
        save(); render();
      }
      inp.addEventListener('blur', commit);
      inp.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') commit();
        if (e.key === 'Escape') { inp.value = orig; commit(); }
      });
    }

    state = load();

    document.addEventListener('DOMContentLoaded', function() {
      render();
      var ni = document.getElementById(p + '-input');
      if (ni) ni.addEventListener('keydown', function(e) { if (e.key === 'Enter') addItem(); });
      var tn = document.getElementById(p + '-notes');
      if (tn) tn.addEventListener('input', function() { state.notes = tn.value; save(); });
    });

    function addItem() {
      var inp = document.getElementById(p + '-input'); if (!inp) return;
      var text = inp.value.trim(); if (!text) return;
      state.items.push({ id: 'u' + Date.now(), text: text, done: false });
      inp.value = ''; save(); render();
      var list = document.getElementById(p + '-list');
      if (list) list.scrollTop = list.scrollHeight;
    }
    function resetItems() {
      if (confirm('Restaurar lista padrao? Suas alteracoes serao perdidas.')) {
        state = { items: clone(defaultItems), notes: '' }; save(); render();
      }
    }
    return { addItem: addItem, reset: resetItems };
  }

  var todos = {
    vba:  makeTodo('vba',  'todo_vba_v1',  __VBA_DATA__),
    py:   makeTodo('py',   'todo_py_v1',   __PY_DATA__),
    fe:   makeTodo('fe',   'todo_fe_v1',   __FE_DATA__),
    al:   makeTodo('al',   'todo_al_v1',   __AL_DATA__),
    fut:  makeTodo('fut',  'todo_fut_v1',  __FUT_DATA__),
    graf: makeTodo('graf', 'todo_graf_v1', __GRAF_DATA__),
    bat:  makeTodo('bat',  'todo_bat_v1',  __BAT_DATA__),
    pj:   makeTodo('pj',   'todo_pj_v1',   __PJ_DATA__),
    off:  makeTodo('off',  'todo_off_v1',  __OFF_DATA__),
    oc3:  makeTodo('oc3',  'todo_oc3_v1',  __OC3_DATA__)
  };

  window.addItem   = function(p) { todos[p].addItem(); };
  window.resetTodo = function(p) { todos[p].reset(); };
})();
</script>
"""


# ── montagem HTML ─────────────────────────────────────────────────────────────


def bloco_fut_init():
    inner = (
        # '<div class="bloco-header">&#x1F40D; Inicializacao &mdash; futuros.py</div>'
        '<div class="bloco-header">Inicializacao &mdash; futuros.py</div>'
        '<div class="bloco-sub">Banco: <strong>dbsx337</strong>'
        ' &nbsp;&middot;&nbsp; Saida: <strong>../output/rolagem/{dt}/</strong></div>'
        '<div class="bloco-code">'
        'dt = <span class="kw">ql.Brazil()</span>.advance(..., <span class="kw">ql.Period</span>(<span class="str">\'-1d\'</span>))<br>'
        'fundos = <span class="kw">ler_fundos</span>(<span class="str">"../input/fundos.txt"</span>)<br>'
        '<span class="code-comment"># codigos de vencimento CME</span><br>'
        'MES_CODIGO = {1:<span class="str">\'F\'</span>,2:<span class="str">\'G\'</span>,...,12:<span class="str">\'Z\'</span>}'
        "</div>"
        '<div class="bloco-detail">'
        '<span class="badge badge-teal">QuantLib</span> Brasil -1d util &nbsp;'
        '<span class="badge badge-blue">fundos.txt</span> Lista de clcli_cd'
        "</div>"
    )
    return node(inner, "c-fut-init", 520)


def bloco_fut_queries():
    tags = "".join(
        '<div class="tag clickable ' + CAT_CSS.get(q[3], "t-pos") + '"'
        ' onclick="showSQL(\'' + q[0] + '\')"'
        ' title="Clique para ver a query SQL">'
        "<strong>" + q[0] + "()</strong>"
        '<span class="src">' + q[1] + "</span>"
        '<span class="dest">' + q[2] + "</span>"
        '<span class="lbl">' + q[4] + ' &nbsp;<em style="opacity:.5;font-size:.6rem">ver SQL</em></span>'
        "</div>"
        for q in FUT_QUERIES
    )
    return group(
        # "&#x1F4DD; Consultas SQL &mdash; dbsx337 (" + str(len(FUT_QUERIES)) + " queries &mdash; clique para ver)",
        "Consultas SQL &mdash; dbsx337 (" + str(len(FUT_QUERIES)) + " queries &mdash; clique para ver)",
        tags, cols=2, width=700,
    )


def bloco_fut_preproc():
    inner = (
        # '<div class="bloco-header">&#x1F527; Pre-processamento dos dados</div>'
        '<div class="bloco-header">Pre-processamento dos dados</div>'
        '<div class="bloco-sub">Formatacao de vencimentos e definicao de grupos</div>'
        '<div class="bloco-code">'
        '<span class="code-comment"># formatar vencimento</span><br>'
        'df_fut[<span class="str">"vencimento"</span>] = dt_vencto.apply(<span class="kw">formatar_vencimento</span>)<br>'
        '<span class="code-comment"># filtrar apenas ano corrente</span><br>'
        'ano_ref = dt.strftime(<span class="str">"%y"</span>)<br>'
        'df_fut = df_fut[df_fut[<span class="str">"vencimento"</span>].str.endswith(ano_ref)]<br>'
        '<span class="code-comment"># grupos: DOL_WDO combinado + demais ativos</span><br>'
        'ativos = df_fut[<span class="str">"fuvct_fuatv_cd"</span>].apply(<span class="kw">normalizar_ativo</span>).unique()<br>'
        'grupos = [<span class="str">"DOL_WDO"</span>] + [a <span class="kw">for</span> a <span class="kw">in</span> ativos <span class="kw">if</span> a <span class="kw">not in</span> GRUPO_DOL]'
        "</div>"
    )
    return node(inner, "c-fut-proc", 620)


def bloco_fut_loop():
    col_rows = "".join(
        '<div class="clear-row">'
        '<span class="clear-aba" style="color:#76d7c4;min-width:110px"><code style="font-size:.68rem">' + c[0] + "</code></span>"
        '<span class="clear-cols">' + c[1] + "</span>"
        '<span class="clear-count" style="color:#555">' + c[2] + "</span>"
        "</div>"
        for c in FUT_COMPUTED_COLS
    )
    inner = (
        # '<div class="bloco-header">&#x1F501; Loop por grupo &mdash; processar_grupo()</div>'
        '<div class="bloco-header">Loop por grupo &mdash; processar_grupo()</div>'
        '<div class="bloco-sub">Para cada grupo: identificar V1 (front) e V2 (back)</div>'
        '<div class="bloco-code">'
        '<span class="kw">for</span> grupo <span class="kw">in</span> grupos:<br>'
        '&nbsp;&nbsp;v1 = vencimentos[0] <span class="code-comment"># front month</span><br>'
        '&nbsp;&nbsp;v2 = <span class="kw">next</span>(v <span class="kw">for</span> v <span class="kw">in</span> vcts <span class="kw">if</span> v &gt; v1)<br>'
        '&nbsp;&nbsp;df_grp = groupby([clcli_cd, vencimento]).sum(Notional)<br>'
        '&nbsp;&nbsp;df_tab = merge(df_pl, totais, n1, n2)'
        "</div>"
        + col_rows +
        '<div class="bloco-detail" style="margin-top:6px">'
        '<span class="badge badge-teal">DOL_WDO</span> DOL + WDO agrupados &nbsp;'
        '<span class="badge badge-blue">V1&rarr;V2</span> Rolagem front para back'
        "</div>"
    )
    return node(inner, "c-fut-proc", 680)


def bloco_fut_export():
    tags = "".join(
        '<div class="tag ' + CAT_CSS.get(o[3], "t-pos") + '">'
        "<strong>" + o[0] + "()</strong>"
        '<span class="src">lib: ' + o[1] + "</span>"
        '<span class="dest">' + o[2] + "</span>"
        '<span class="lbl">' + o[4] + "</span>"
        "</div>"
        for o in FUT_OUTPUTS
    )
    return group(
        # "&#x1F4E4; Exportacao (" + str(len(FUT_OUTPUTS)) + " formatos)",
        "Exportacao (" + str(len(FUT_OUTPUTS)) + " formatos)",
        tags, cols=2, width=700, border_color="#d4ac0d",
    )


def bloco_alerta_init():
    inner = (
        # '<div class="bloco-header">&#x2699; Inicializacao do Ambiente VBA</div>'
        '<div class="bloco-header">Inicializacao do Ambiente VBA</div>'
        '<div class="bloco-sub">Workbook: <strong>Exposicao Beta V20.xlsm</strong></div>'
        '<div class="bloco-code">'
        'Application.Calculation = <span class="kw">xlCalculationManual</span><br>'
        'Application.ScreenUpdating = <span class="kw">False</span><br>'
        'Application.DisplayAlerts = <span class="kw">False</span><br>'
        '<span class="code-comment">\'-- variaveis --</span><br>'
        '<span class="kw">Dim</span> teste    <span class="kw">As Variant</span><br>'
        '<span class="kw">Dim</span> valorAnt <span class="kw">As String</span><br>'
        '<span class="kw">Dim</span> valorAtu <span class="kw">As String</span>'
        "</div>"
        '<div class="bloco-detail">'
        '<span class="badge badge-blue">Planilha6</span> Design sheet &nbsp;'
        '<span class="badge badge-purple">alert</span> Aba Alerta'
        "</div>"
    )
    return node(inner, "c-al-init", 500)


def bloco_alerta_autofilter():
    inner = (
        # '<div class="bloco-header">&#x1F6AB; Desativar AutoFilter</div>'
        '<div class="bloco-header">Desativar AutoFilter</div>'
        '<div class="bloco-sub">Aba <strong>Relatorio</strong></div>'
        '<div class="bloco-code">'
        'Sheets(<span class="str">"Relat&oacute;rio"</span>).AutoFilterMode = <span class="kw">False</span>'
        "</div>"
    )
    return node(inner, "c-al-init", 400)


def bloco_alerta_reset():
    rows = "".join(
        '<div class="clear-row">'
        '<span class="clear-aba" style="color:#f1948a;min-width:100px"><code style="font-size:.68rem">' + r[0] + "</code></span>"
        '<span class="clear-cols">' + r[1] + "</span>"
        '<span class="clear-count" style="color:#666">vbWhite</span>'
        "</div>"
        for r in ALERTA_RANGES
    )
    inner = (
        # '<div class="bloco-header">&#x1F5D1; Reset de cores &mdash; Aba Design</div>'
        '<div class="bloco-header">Reset de cores &mdash; Aba Design</div>'
        '<div class="bloco-sub">'
        + str(len(ALERTA_RANGES)) + " categorias &rarr; Interior.Color = vbWhite"
        + "</div>"
        + rows
    )
    return node(inner, "c-al-reset", 560)


def bloco_alerta_loop():
    check_rows = "".join(
        '<div class="clear-row">'
        '<span class="clear-aba" style="color:#c39bd3;min-width:60px">' + c[0] + "</span>"
        '<span class="clear-cols" style="color:#aaa">leitura: <code>' + c[1] + "</code>"
        " &nbsp;&rarr;&nbsp; pinta: <code>" + c[2] + "</code> de <strong style='color:#e74c3c'>vbRed</strong></span>"
        '<span class="clear-count">' + c[3] + "</span>"
        "</div>"
        for c in ALERTA_CHECKS
    )
    inner = (
        # '<div class="bloco-header">&#x1F501; Loop i = 8 To 189 &mdash; Planilha6 (Design)</div>'
        '<div class="bloco-header">Loop i = 8 To 189 &mdash; Planilha6 (Design)</div>'
        '<div class="bloco-sub">Para cada linha: ler 5 checks &rarr; pintar colunas &rarr; copiar para Alerta</div>'
        + check_rows +
        '<div class="bloco-code" style="margin-top:8px">'
        'soma_check = check1 + check2 + check3 + check4 + check5<br>'
        '<span class="kw">If</span> soma_check &lt;&gt; 0 <span class="kw">Then</span><br>'
        '&nbsp;&nbsp;valorAtu = Planilha6.Cells(i, <span class="kw">14</span>).Value <span class="code-comment">\'categoria</span><br>'
        '&nbsp;&nbsp;<span class="kw">If</span> valorAtu &lt;&gt; valorAnt <span class="kw">Then</span> <span class="code-comment">\'nova categoria</span><br>'
        '&nbsp;&nbsp;&nbsp;&nbsp;alert.Cells(99999, 2).End(xlUp).Offset(1,0).PasteSpecial <span class="kw">xlPasteValuesAndNumberFormats</span><br>'
        '&nbsp;&nbsp;<span class="kw">End If</span><br>'
        '&nbsp;&nbsp;Planilha6.Cells(i, <span class="kw">1</span>).Copy &rarr; alert (fundo)'
        "</div>"
        '<div class="bloco-detail">'
        '<span class="badge badge-purple">col 14</span> Agrupador de categoria &nbsp;'
        '<span class="badge badge-blue">col 1</span> Nome do fundo'
        "</div>"
    )
    return node(inner, "c-al-loop", 660)


def bloco_alerta_calc():
    inner = (
        # '<div class="bloco-header">&#x1F4CA; Recalculo + Restauracao</div>'
        '<div class="bloco-header">Recalculo + Restauracao</div>'
        '<div class="bloco-sub">Forca calculo e restaura estado do Excel</div>'
        '<div class="bloco-code">'
        'Calculate<br>'
        'Application.ScreenUpdating = <span class="kw">True</span><br>'
        'Application.DisplayAlerts = <span class="kw">True</span>'
        "</div>"
    )
    return node(inner, "c-al-init", 400)


def bloco_py_init():
    inner = (
        # '<div class="bloco-header">&#x1F40D; Inicializacao do Ambiente Python</div>'
        '<div class="bloco-header">Inicializacao do Ambiente Python</div>'
        '<div class="bloco-sub">Script: <strong>exposicao.py</strong>'
        ' &nbsp;&middot;&nbsp; Banco: <strong>dbsx337</strong></div>'
        '<div class="bloco-code">'
        'date_ref = <span class="kw">ql.Brazil()</span>.advance(<span class="kw">ql.Date.from_date</span>(date.today()), '
        '<span class="kw">ql.Period</span>(<span class="str">\'-1d\'</span>))<br>'
        'dt = date_ref.strftime(<span class="str">\'%Y-%m-%d\'</span>)<br>'
        '<span class="code-comment"># paths</span><br>'
        'INPUT_EXCEL = <span class="str">"../input/fundos_exposicao.xlsx"</span><br>'
        'OUTPUT_BASE = <span class="str">"../output/exposicao"</span>'
        "</div>"
        '<div class="bloco-detail">'
        '<span class="badge badge-teal">QuantLib</span> Calendario Brasil &mdash; -1 dia util'
        "</div>"
    )
    return node(inner, "c-py-init", 540)


def bloco_py_excel():
    sheet_tags = "".join(
        '<span class="macro-stat" style="background:#0f2a1a;border:1px solid #1e8449;color:#82e0aa;border-radius:4px;padding:2px 8px;font-size:.68rem;font-weight:600;margin:2px">'
        + s + "</span>"
        for s in PY_SHEETS
    )
    inner = (
        # '<div class="bloco-header">&#x1F4D1; Leitura do Excel de Parametros</div>'
        '<div class="bloco-header">Leitura do Excel de Parametros</div>'
        '<div class="bloco-sub">Funcao: <strong>ler_exposicao_excel()</strong>'
        ' &nbsp;&middot;&nbsp; ' + str(len(PY_SHEETS)) + ' abas</div>'
        '<div style="display:flex;flex-wrap:wrap;gap:4px;margin:8px 0">'
        + sheet_tags +
        '</div>'
        '<div class="bloco-code">'
        'xls = <span class="kw">pd.ExcelFile</span>(path)<br>'
        'df_out[<span class="str">"FUNDO"</span>], [<span class="str">"BENCH"</span>], '
        '[<span class="str">"MAX"</span>], [<span class="str">"MIN"</span>]<br>'
        '<span class="code-comment"># normaliza benchmark: "IBOV *0,4" &rarr; "IBOV*0,4"</span>'
        "</div>"
    )
    return node(inner, "c-py-read", 620)


def bloco_py_queries():
    tags = "".join(
        '<div class="tag clickable ' + CAT_CSS.get(q[3], "t-pos") + '"'
        ' onclick="showSQL(\'' + q[0] + '\')"'
        ' title="Clique para ver a query SQL">'
        "<strong>" + q[0] + "()</strong>"
        '<span class="src">' + q[1] + "</span>"
        '<span class="dest">' + q[2] + "</span>"
        '<span class="lbl">' + q[4] + ' &nbsp;<em style="opacity:.5;font-size:.6rem">ver SQL</em></span>'
        "</div>"
        for q in PY_QUERIES
    )
    return group(
        # "&#x1F4DD; Consultas SQL &mdash; banco dbsx337 (" + str(len(PY_QUERIES)) + " funcoes &mdash; clique para ver a query)",
        "Consultas SQL &mdash; banco dbsx337 (" + str(len(PY_QUERIES)) + " funcoes &mdash; clique para ver a query)",
        tags, cols=2, width=860,
    )


def bloco_py_montar():
    rows = ""
    for f in PY_FORMULAS:
        rows += (
            '<div class="clear-row">'
            '<span class="clear-aba" style="color:#82e0aa;min-width:120px"><code style="font-size:.7rem">' + f[0] + "</code></span>"
            '<span class="clear-cols">' + f[1] + "</span>"
            '<span class="clear-count" style="color:#555">' + f[2] + "</span>"
            "</div>"
        )
    inner = (
        # '<div class="bloco-header">&#x1F9EE; Montagem das Tabelas &mdash; montar_tabela()</div>'
        '<div class="bloco-header">Montagem das Tabelas &mdash; montar_tabela()</div>'
        '<div class="bloco-sub">' + str(len(PY_SHEETS)) + ' abas &nbsp;&middot;&nbsp; '
        + str(len(PY_FORMULAS)) + ' formulas calculadas</div>'
        + rows +
        '<div class="bloco-detail" style="margin-top:8px">'
        '<span class="badge badge-purple">S&amp;P500</span>'
        " Logica especial: EXP_SP = (PRV &minus; PIBB11 + sp_fut) / PL"
        "</div>"
    )
    return node(inner, "c-py-init", 680)


def bloco_py_export():
    tags = "".join(
        '<div class="tag ' + CAT_CSS.get(o[3], "t-pos") + '">'
        "<strong>" + o[0] + "()</strong>"
        '<span class="src">lib: ' + o[1] + "</span>"
        '<span class="dest">' + o[2] + "</span>"
        '<span class="lbl">' + o[4] + "</span>"
        "</div>"
        for o in PY_OUTPUTS
    )
    return group(
        # "&#x1F4E4; Exportacao de resultados (" + str(len(PY_OUTPUTS)) + " formatos)",
        "Exportacao de resultados (" + str(len(PY_OUTPUTS)) + " formatos)",
        tags, cols=3, width=720, border_color="#d4ac0d",
    )


def build_todo_panel(p, title, css_class, panel_id):
    return (
        '<div id="' + panel_id + '" class="todo-panel ' + css_class + '">'
        '<div class="todo-header">'
        '<span class="todo-title">' + title + '</span>'
        '<span id="' + p + '-counter" class="todo-counter">0/0 concluidos</span>'
        "</div>"
        '<div class="todo-progress-wrap">'
        '<div id="' + p + '-progress" class="todo-progress-fill" style="width:0%"></div>'
        "</div>"
        "<div>"
        '<div class="todo-section-title">Tarefas</div>'
        '<div id="' + p + '-list" class="todo-list"></div>'
        "</div>"
        '<div class="todo-add">'
        '<input id="' + p + '-input" type="text" class="todo-input"'
        ' placeholder="Nova tarefa...">'
        '<button onclick="addItem(\'' + p + '\')" class="todo-add-btn" title="Adicionar">+</button>'
        "</div>"
        "<div>"
        '<div class="todo-section-title">Notas</div>'
        '<textarea id="' + p + '-notes" class="todo-notes"'
        ' placeholder="Observacoes e pendencias..."></textarea>'
        "</div>"
        '<button onclick="resetTodo(\'' + p + '\')" class="todo-reset-btn">&#x21BA; Restaurar</button>'
        "</div>"
    )


CAL_MODAL_HTML = (
    '<div id="kcal-overlay" class="kcal-overlay">'
    '<div class="kcal-modal">'
    '<div class="kcal-mhdr">'
    '<div id="kcal-mdate" class="kcal-mdate"></div>'
    '<button id="kcal-mclose" class="kcal-mclose" title="Fechar">&#215;</button>'
    '</div>'
    '<div class="kcal-delivery-row">'
    '<button id="kcal-delivery-btn" class="kcal-delivery-btn">'
    '<span class="kdot"></span>'
    '<span id="kcal-delivery-lbl">Marcar como entrega</span>'
    '</button>'
    '</div>'
    '<textarea id="kcal-mta" class="kcal-mta" placeholder="Notas para esta data..."></textarea>'
    '<div class="kcal-mfooter">'
    '<span class="kcal-mhint">Ctrl+Enter salva &nbsp;&middot;&nbsp; Esc fecha</span>'
    '<button id="kcal-mclear" class="kcal-mclear">Limpar</button>'
    '<button id="kcal-msave" class="kcal-msave">Salvar</button>'
    '</div>'
    '</div>'
    '</div>'
)


def bloco_calendario():
    return (
        '<div class="kcal">'
        '<div class="kcal-hdr">'
        '<button id="kcal-prev" class="kcal-btn" title="Mes anterior">&#8249;</button>'
        '<span id="kcal-label" class="kcal-hdr-label"></span>'
        '<button id="kcal-next" class="kcal-btn" title="Proximo mes">&#8250;</button>'
        '</div>'
        '<div class="kcal-dow">'
        '<b>Dom</b><b>Seg</b><b>Ter</b><b>Qua</b><b>Qui</b><b class="kfri">Sex</b><b>Sab</b>'
        '</div>'
        '<div id="kcal-grid" class="kcal-grid"></div>'
        '</div>'
    )


CALENDAR_INIT_JS = """
<script>
(function() {
  var KEY      = 'kcal_v1';
  var VER_KEY  = 'kcal_todos_ver';
  var VER      = '2026-06-17-v2';
  if (localStorage.getItem(VER_KEY) === VER) return;
  var existing = {};
  try { existing = JSON.parse(localStorage.getItem(KEY)) || {}; } catch(e) {}
  var notes = {
    '2026-06-08': 'Exposicao Beta - VBA:\\n' +
      '* t1: Conectar banco via ADODB (sSQL_Connect -> dbsx337)\\n' +
      '* t2: Executar 25 queries e escrever resultados no workbook\\n' +
      '* t3: Inserir formulas: PL consolidado, cambio, DU, caixa exterior\\n' +
      '* t4: Aplicar AutoFilter no Relatorio (campo 29, >100.1% ou <99.99%)\\n' +
      '* t5: Validar queries de moedas com novas fontes BBG FX',
    '2026-06-09': 'Exposicao Beta - VBA + Python:\\n' +
      '* t6: Testar bloco PRV com fundos FICAD_CD adicionados recentemente\\n' +
      '* t7: Documentar estrutura das colunas da planilha PRM\\n' +
      '* p1: Definir estrutura do script Python\\n' +
      '* p2: Mapear entradas e saidas do calculo\\n' +
      '* p3: Implementar conexao com banco de dados',
    '2026-06-10': 'Exposicao Beta - Front End + Alerta:\\n' +
      '* f1: Definir estrutura do front end\\n' +
      '* f2: Mapear paginas e componentes\\n' +
      '* f3: Integrar com dados do back end\\n' +
      '* a1: Validar colunas de check no Design (cols 19,22,25,28,31)\\n' +
      '* a2: Confirmar range do loop: linhas 8 a 189',
    '2026-06-11': 'Exposicao Beta - Alerta + Futuros:\\n' +
      '* a3: Testar copia de alertas para aba Alerta\\n' +
      '* a4: Verificar logica de agrupamento por categoria (col 14)\\n' +
      '* u1: Validar codigos MES_CODIGO (CME: F,G,H,J,K,M,N,Q,U,V,X,Z)\\n' +
      '* u2: Confirmar filtro ano_ref: apenas contratos do ano corrente\\n' +
      '* u3: Testar processar_grupo para DOL_WDO combinado',
    '2026-06-12': 'Exposicao Beta - Futuros + Graficos + Batimento Diario:\\n' +
      '* u4: Verificar saida Excel: formatacao verde/vermelho nos percentuais\\n' +
      '* gr1: Definir estrutura de graficos por fundo\\n' +
      '* gr2: Mapear series de dados e periodos\\n' +
      '* gr3: Implementar visualizacoes interativas\\n' +
      '* b1: Validar triagem macro: fundos indexados com |Delta| >= 0.5 bps',
    '2026-06-13': 'Batimento Diario:\\n' +
      '* b2: Testar batimentos paralelos (joblib) para todas as 7 classes\\n' +
      '* b3: Confirmar mapeamento de causas: queries diagnostico por (causa, classe)\\n' +
      '* b4: Verificar aba Como_Corrigir: scripts RunProject corretos para cada causa\\n' +
      '* b5: Validar 10 analises sequenciais (precos, PnL esperado, carrego RF...)\\n' +
      '* b6: Testar integracao OC3: patrimonio, RF, RV, futuros, swap, caixa',
    '2026-06-14': 'Batimento Diario + Preco Justo ETF:\\n' +
      '* b7: Confirmar saida Excel: 19 abas geradas corretamente por fundo\\n' +
      '* pj1: Validar gerar_preco_justo_etfRF: cupom + PU careca + taxa ponderada\\n' +
      '* pj2: Testar GOAT11: posicao RV + BTC + caixa via Bloomberg\\n' +
      '* pj3: Verificar T10R11: yield = CTD + CDI - Fed Funds (vencimento dinamico)\\n' +
      '* pj4: Validar etfSelic (CDIB11/LFTI11): accrual CDI diario para LFTI11',
    '2026-06-15': 'Preco Justo ETF + Batimento dll - OC3:\\n' +
      '* pj5: Confirmar restricao horaria: 10:15 - 18:00\\n' +
      '* pj6: Testar saida CSV: delimitador ; decimal , sem NAs\\n' +
      '* oc1: Validar codigos SAC dos fundos: lista_fundos no formato correto (FICFI...)\\n' +
      '* oc2: Testar conexao OC3(): nova instancia por fundo (evitar estado acumulado)\\n' +
      '* oc3: Verificar as 27 consultas: todas retornando dados ou vazio gracioso',
    '2026-06-16': 'Batimento dll - OC3 + Batimento Offshore (RF):\\n' +
      '* oc4: Confirmar filtros por fundo: ativo_cotas, pos_fi_patr, cpr filtram por COD_CLI\\n' +
      '* oc5: Testar saida Excel: 27 abas por fundo, path output/batimento_oc3/{yyyymmdd}/\\n' +
      '* oc6: Validar conversao ADO Recordset -> DataFrame (_recordset_to_df)\\n' +
      '* off1: Validar lista_fundos offshore: nomes exatos em SISTEMAS_SSC_PED_INTRADAY\\n' +
      '* off2: Testar mapeamento de_para_dict: todos os tipos SSC cobertos',
    '2026-06-17': 'Batimento Offshore (RF) - conclusao:\\n' +
      '* off3: Confirmar threshold arred=1: diferencas < R$1 ignoradas\\n' +
      '* off4: Validar distribuicao de PnL por estrategia (est1-est5): proporcional por qtd\\n' +
      '* off5: Testar tratamento posicao zerada com multiplas estrategias (divisao igual)\\n' +
      '* off6: Verificar aba VerificarPnL: ativos sem estrategia mapeada (VERIFICAR)\\n' +
      '* off7: Confirmar saida Excel: 5 abas + frozen panes + path output/batimento_off/'
  };
  Object.keys(notes).forEach(function(k) { existing[k] = notes[k]; });
  localStorage.setItem(KEY, JSON.stringify(existing));
  localStorage.setItem(VER_KEY, VER);
})();
</script>
"""

CAL_JS = """
<script>
(function() {
  var NOTE_KEY = 'kcal_v1';
  var DEL_KEY  = 'kcal_deliveries_v1';
  var yr, mo, curKey = null;
  var MESES = ['Janeiro','Fevereiro','Marco','Abril','Maio','Junho',
               'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];
  var MSPT  = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'];
  var DIAS  = ['domingo','segunda-feira','terca-feira','quarta-feira',
               'quinta-feira','sexta-feira','sabado'];

  function notes()      { try { return JSON.parse(localStorage.getItem(NOTE_KEY)) || {}; } catch(e) { return {}; } }
  function deliveries() { try { return JSON.parse(localStorage.getItem(DEL_KEY))  || {}; } catch(e) { return {}; } }
  function saveNotes(d) { localStorage.setItem(NOTE_KEY, JSON.stringify(d)); }
  function saveDels(d)  { localStorage.setItem(DEL_KEY,  JSON.stringify(d)); }
  function pad(n) { return n < 10 ? '0'+n : ''+n; }
  function esc(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  function setDeliveryBtn(active) {
    var btn = document.getElementById('kcal-delivery-btn');
    var lbl = document.getElementById('kcal-delivery-lbl');
    if (!btn) return;
    btn.classList.toggle('active', active);
    if (lbl) lbl.textContent = active ? 'Data de entrega marcada' : 'Marcar como entrega';
  }

  function render() {
    var grid  = document.getElementById('kcal-grid');
    var label = document.getElementById('kcal-label');
    if (!grid) return;
    if (label) label.textContent = MESES[mo] + ' ' + yr;
    var nd   = notes();
    var dels = deliveries();
    var first = new Date(yr, mo, 1).getDay();
    var days  = new Date(yr, mo + 1, 0).getDate();
    var now   = new Date();
    var html  = '';
    for (var i = 0; i < first; i++)
      html += '<div class="kcal-day kcal-empty"></div>';
    for (var d = 1; d <= days; d++) {
      var key  = yr + '-' + pad(mo + 1) + '-' + pad(d);
      var dow  = new Date(yr, mo, d).getDay();
      var note = (nd[key] || '').trim();
      var cls  = 'kcal-day';
      if (dow === 5)  cls += ' kcal-fri';
      if (now.getFullYear()===yr && now.getMonth()===mo && now.getDate()===d) cls += ' kcal-today';
      if (note)       cls += ' kcal-hasnote';
      if (dels[key])  cls += ' kcal-entrega';
      html += '<div class="'+cls+'" data-key="'+key+'">'
           +  '<div class="kcal-num">'+d+'</div>'
           +  '<div class="kcal-prev">'+(note ? esc(note) : '')+'</div>'
           +  '</div>';
    }
    grid.innerHTML = html;
  }

  function openModal(key) {
    curKey = key;
    var nd   = notes();
    var dels = deliveries();
    var p = key.split('-');
    var d = +p[2], m = +p[1]-1, y = +p[0];
    var dow   = new Date(y, m, d).getDay();
    var isFri = dow === 5;
    var isDel = !!dels[key];
    var txt   = d + ' de ' + MSPT[m] + ' de ' + y + '  —  ' + DIAS[dow];
    var el = document.getElementById('kcal-mdate');
    el.textContent = txt;
    el.className = 'kcal-mdate' + (isDel ? ' fri' : '');
    setDeliveryBtn(isDel);
    var ta = document.getElementById('kcal-mta');
    ta.value = nd[key] || '';
    document.getElementById('kcal-overlay').classList.add('open');
    setTimeout(function(){ ta.focus(); ta.selectionStart = ta.selectionEnd = ta.value.length; }, 60);
  }

  function closeModal() {
    document.getElementById('kcal-overlay').classList.remove('open');
    curKey = null;
  }

  function saveAll() {
    if (!curKey) return;
    var val  = document.getElementById('kcal-mta').value;
    var nd   = notes();
    var dels = deliveries();
    var btn  = document.getElementById('kcal-delivery-btn');
    if (val.trim()) nd[curKey] = val; else delete nd[curKey];
    if (btn && btn.classList.contains('active')) dels[curKey] = 1; else delete dels[curKey];
    saveNotes(nd); saveDels(dels);
    closeModal(); render();
  }

  function clearAll() {
    if (!curKey) return;
    var nd = notes(); delete nd[curKey]; saveNotes(nd);
    var dels = deliveries(); delete dels[curKey]; saveDels(dels);
    document.getElementById('kcal-mta').value = '';
    setDeliveryBtn(false);
    closeModal(); render();
  }

  document.addEventListener('DOMContentLoaded', function() {
    var now = new Date(); yr = now.getFullYear(); mo = now.getMonth();
    render();

    var prev = document.getElementById('kcal-prev');
    var next = document.getElementById('kcal-next');
    if (prev) prev.addEventListener('click', function(){ if(--mo<0){mo=11;yr--;} render(); });
    if (next) next.addEventListener('click', function(){ if(++mo>11){mo=0;yr++;} render(); });

    var grid = document.getElementById('kcal-grid');
    if (grid) grid.addEventListener('click', function(e) {
      var cell = e.target.closest('.kcal-day:not(.kcal-empty)');
      if (cell && cell.dataset.key) openModal(cell.dataset.key);
    });

    var db_btn = document.getElementById('kcal-delivery-btn');
    if (db_btn) db_btn.addEventListener('click', function(e) {
      e.preventDefault();
      this.classList.toggle('active');
      var lbl = document.getElementById('kcal-delivery-lbl');
      if (lbl) lbl.textContent = this.classList.contains('active')
        ? 'Data de entrega marcada' : 'Marcar como entrega';
    });

    var mc = document.getElementById('kcal-mclose');
    var ms = document.getElementById('kcal-msave');
    var mr = document.getElementById('kcal-mclear');
    var ov = document.getElementById('kcal-overlay');
    if (mc) mc.addEventListener('click', closeModal);
    if (ms) ms.addEventListener('click', saveAll);
    if (mr) mr.addEventListener('click', clearAll);
    if (ov) ov.addEventListener('click', function(e){ if(e.target===this) closeModal(); });

    document.addEventListener('keydown', function(e) {
      var ov2 = document.getElementById('kcal-overlay');
      if (!ov2 || !ov2.classList.contains('open')) return;
      if (e.key==='Escape')              { e.preventDefault(); closeModal(); }
      if (e.key==='Enter' && e.ctrlKey) { e.preventDefault(); saveAll(); }
    });
  });
})();
</script>
"""

STATUS_JS = """
<script>
(function() {
  var STATES = ['todo', 'doing', 'done'];
  var LABELS = { todo: 'A fazer', doing: 'Em andamento', done: 'Concluído' };
  var KEY = 'flowstatus_v1';

  function load() {
    try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch(e) { return {}; }
  }
  function save(s) { localStorage.setItem(KEY, JSON.stringify(s)); }

  function applyBadge(badge, state) {
    badge.className = 's-badge s-' + state;
    badge.querySelector('.s-lbl').textContent = LABELS[state];
  }

  window.cycleStatus = function(e, sid) {
    e.stopPropagation();
    var badge = e.currentTarget;
    var s = load();
    var cur = s[sid] || 'todo';
    var next = STATES[(STATES.indexOf(cur) + 1) % STATES.length];
    s[sid] = next;
    save(s);
    applyBadge(badge, next);
  };

  document.addEventListener('DOMContentLoaded', function() {
    var s = load();
    document.querySelectorAll('.s-badge').forEach(function(b) {
      var sid = b.dataset.sid;
      if (sid && s[sid]) applyBadge(b, s[sid]);
    });
  });
})();
</script>
"""

NAV_JS = """
<script>
function showPage(id, showVba, showPy, showFe, showAl, showFut, showGraf, showCal, showBat, showPj, showOff, showOc3) {
  ['pg0','pg1','pg2','pg3','pg4','pg5','pg6','pg7','pg8','pg9','pg10','pg11','pg12','pg13','pg14','pg15','pg16'].forEach(function(p) {
    var el = document.getElementById(p);
    if (el) el.classList.remove('active');
  });
  document.getElementById(id).classList.add('active');
  var tv   = document.getElementById('todo-vba-panel');
  var tp   = document.getElementById('todo-py-panel');
  var tf   = document.getElementById('todo-fe-panel');
  var ta   = document.getElementById('todo-al-panel');
  var tfu  = document.getElementById('todo-fut-panel');
  var tgr  = document.getElementById('todo-graf-panel');
  var tba  = document.getElementById('todo-bat-panel');
  var tpj  = document.getElementById('todo-pj-panel');
  var toff = document.getElementById('todo-off-panel');
  var cs   = document.getElementById('cal-section');
  if (tv)  tv.classList.toggle('todo-hidden', !showVba);
  if (tp)  tp.classList.toggle('todo-hidden', !showPy);
  if (tf)  tf.classList.toggle('todo-hidden', !showFe);
  if (ta)  ta.classList.toggle('todo-hidden', !showAl);
  if (tfu) tfu.classList.toggle('todo-hidden', !showFut);
  if (tgr) tgr.classList.toggle('todo-hidden', !showGraf);
  if (tba) tba.classList.toggle('todo-hidden', !showBat);
  if (tpj) tpj.classList.toggle('todo-hidden', !showPj);
  if (toff) toff.classList.toggle('todo-hidden', !showOff);
  var toc3 = document.getElementById('todo-oc3-panel');
  if (toc3) toc3.classList.toggle('todo-hidden', !showOc3);
  if (cs)  cs.classList.toggle('cal-visible', !!showCal);
  window.scrollTo(0, 0);
}
function goDetail()           { showPage('pg2',  true,  false, false, false, false, false, true,  false, false, false, false); }
function goDetailPy()         { showPage('pg3',  false, true,  false, false, false, false, true,  false, false, false, false); }
function goDetailFe()         { showPage('pg4',  false, false, true,  false, false, false, true,  false, false, false, false); }
function goDetailAlerta()     { showPage('pg5',  false, false, false, true,  false, false, true,  false, false, false, false); }
function goDetailFut()        { showPage('pg6',  false, false, false, false, true,  false, true,  false, false, false, false); }
function goDetailGraficos()   { showPage('pg7',  false, false, false, false, false, true,  true,  false, false, false, false); }
function goMacro()            { showPage('pg1',  true,  true,  true,  true,  true,  true,  false, false, false, false, false); }
function goIdx()              { showPage('pg0',  false, false, false, false, false, false, false, false, false, false, false); }
function goDetailRF()         { showPage('pg8',  false, false, false, false, false, false, false, false, false, false, false); }
function goDetailRF2()        { showPage('pg8',  false, false, false, false, false, false, false, false, false, false, false); }
function goDetailBatimento()  { showPage('pg9',  false, false, false, false, false, false, true,  true,  false, false, false); }
function goDetailPrecoJusto() { showPage('pg10', false, false, false, false, false, false, true,  false, true,  false, false); }
function goDetailOffshore()   { showPage('pg11', false, false, false, false, false, false, true,  false, false, true,  false); }
function goDetailOC3()        { showPage('pg12', false, false, false, false, false, false, true,  false, false, false, true);  }
function goDetailDashMesaRF() { showPage('pg13', false, false, false, false, false, false, false, false, false, false, false); }
function goDetailBaseDados()  { showPage('pg14', false, false, false, false, false, false, false, false, false, false, false); }
function goDetailContingencia() { showPage('pg15', false, false, false, false, false, false, false, false, false, false, false); }
function goDetailERD()        { showPage('pg16', false, false, false, false, false, false, false, false, false, false, false); }
document.addEventListener('DOMContentLoaded', function() { goIdx(); });
</script>
"""

THEME_JS = """
<script>
(function() {
  var KEY = 'fluxo_theme';

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    var btn = document.getElementById('theme-toggle-btn');
    if (!btn) return;
    if (theme === 'light') {
      btn.textContent = '\\u{1F319}';
      btn.title = 'Mudar para tema escuro';
    } else {
      btn.textContent = '\\u2600\\uFE0F';
      btn.title = 'Mudar para tema claro';
    }
  }

  window.toggleTheme = function() {
    var current = document.documentElement.getAttribute('data-theme') || 'dark';
    var next = current === 'light' ? 'dark' : 'light';
    try { localStorage.setItem(KEY, next); } catch (e) {}
    applyTheme(next);
  };

  var saved = 'dark';
  try { saved = localStorage.getItem(KEY) || 'dark'; } catch (e) {}
  applyTheme(saved);
})();
</script>
"""


def build_macro_page():
    n_queries = len(SQL_QUERIES)
    n_formulas = len(FORMULAS)

    box_vba = (
        '<div class="macro-box macro-box-vba clickable" onclick="goDetail()" title="Ver fluxograma VBA">'
        '<div class="macro-box-badge">M&aacute;cro</div>'
        '<div class="macro-icon">VBA</div>'
        '<div class="macro-sub">Sub Load_DADOS337</div>'
        '<div class="macro-stats">'
        '<span class="macro-stat">' + str(n_queries) + ' queries</span>'
        '<span class="macro-stat">' + str(n_formulas) + ' f&oacute;rmulas</span>'
        '<span class="macro-stat">dbsx337</span>'
        '</div>'
        '<div class="macro-hint">Clique para ver o fluxograma</div>'
        '</div>'
    )

    box_py = (
        '<div class="macro-box macro-box-py clickable" onclick="goDetailPy()" title="Ver fluxograma Python">'
        '<div class="macro-box-badge">Script</div>'
        '<div class="macro-icon">PY</div>'
        '<div class="macro-sub">exposicao.py</div>'
        '<div class="macro-stats">'
        '<span class="macro-stat">' + str(len(PY_QUERIES)) + ' queries</span>'
        '<span class="macro-stat">' + str(len(PY_FORMULAS)) + ' f&oacute;rmulas</span>'
        '<span class="macro-stat">' + str(len(PY_OUTPUTS)) + ' sa&iacute;das</span>'
        '</div>'
        '<div class="macro-hint">Clique para ver o fluxograma</div>'
        '</div>'
    )

    box_fe = (
        '<div class="macro-box macro-box-fe clickable" onclick="goDetailFe()" title="Ver fluxograma Front End">'
        '<div class="macro-box-badge">Interface</div>'
        '<div class="macro-icon">FE</div>'
        '<div class="macro-sub">Front End</div>'
        '<div class="macro-stats">'
        '<span class="macro-stat">em desenvolvimento</span>'
        '</div>'
        '<div class="macro-hint">Clique para ver o fluxograma</div>'
        '</div>'
    )

    box_alerta = (
        '<div class="macro-box macro-box-al clickable" onclick="goDetailAlerta()" title="Ver fluxograma Sub Alerta">'
        '<div class="macro-box-badge">M&aacute;cro</div>'
        '<div class="macro-icon" style="font-size:2.4rem">VBA</div>'
        '<div class="macro-sub">Sub Alerta</div>'
        '<div class="macro-stats">'
        '<span class="macro-stat">' + str(len(ALERTA_RANGES)) + ' categorias</span>'
        '<span class="macro-stat">' + str(len(ALERTA_CHECKS)) + ' checks</span>'
        '<span class="macro-stat">Design &rarr; Alerta</span>'
        '</div>'
        '<div class="macro-hint">Clique para ver o fluxograma</div>'
        '</div>'
    )

    box_fut = (
        '<div class="macro-box macro-box-fut clickable" onclick="goDetailFut()" title="Ver fluxograma futuros.py">'
        '<div class="macro-box-badge">Script</div>'
        '<div class="macro-icon">PY</div>'
        '<div class="macro-sub">futuros.py</div>'
        '<div class="macro-stats">'
        '<span class="macro-stat">' + str(len(FUT_QUERIES)) + ' queries</span>'
        '<span class="macro-stat">' + str(len(FUT_COMPUTED_COLS)) + ' c&aacute;lculos</span>'
        '<span class="macro-stat">' + str(len(FUT_OUTPUTS)) + ' sa&iacute;das</span>'
        '</div>'
        '<div class="macro-hint">Clique para ver o fluxograma</div>'
        '</div>'
    )

    group_vba = (
        '<div class="macro-group">'
        '<span class="macro-group-label">VBA &mdash; Exposicao Beta V20.xlsm</span>'
        + box_vba + box_alerta +
        '</div>'
    )

    box_graficos = (
        '<div class="macro-box macro-box-py clickable" onclick="goDetailGraficos()" title="Ver fluxograma Analise Grafica Fundos">'
        '<div class="macro-box-badge">Script</div>'
        '<div class="macro-icon">PY</div>'
        '<div class="macro-sub">An&aacute;lise Gr&aacute;fica &mdash; Fundos</div>'
        '<div class="macro-stats">'
        '<span class="macro-stat">em desenvolvimento</span>'
        '</div>'
        '<div class="macro-hint">Clique para ver o fluxograma</div>'
        '</div>'
    )

    group_py = (
        '<div class="macro-group macro-group-py">'
        '<span class="macro-group-label" style="background:#0c0e14">Python &mdash; Scripts</span>'
        # '<span class="macro-group-label" style="background:#27ae60">Python &mdash; Scripts</span>'
        + box_py + box_fut + box_graficos +
        '</div>'
    )

    return (
        '<div id="pg1" class="pg pg-macro">'
        '<div class="macro-center">'
        '<button class="back-btn" style="align-self:flex-start" onclick="goIdx()">&#x2190; Voltar</button>'
        '<div class="macro-workbook">Exposicao Beta V20.xlsm</div>'
        '<div class="macro-boxes">'
        + group_vba + group_py + box_fe +
        '</div>'
        '<div class="macro-arrow-hint">&#x25BC;</div>'
        '</div>'
        '</div>'
    )


def _oc3_group(title, items, border_color="#006064", title_color="#80cbc4"):
    tags = "".join(
        '<div class="tag ' + CAT_CSS.get(it[2], "t-pos") + '">'
        '<strong style="font-size:.7rem">' + it[0] + '</strong>'
        '<span class="src" style="font-size:.6rem">' + it[1] + '</span>'
        '<span class="lbl">' + it[3] + '</span>'
        '</div>'
        for it in items
    )
    return (
        '<div class="group" style="border-color:' + border_color + ';margin-bottom:0">'
        '<div class="group-title" style="color:' + title_color + '">'
        + title + ' (' + str(len(items)) + ')'
        + '</div>'
        '<div class="group-grid cols2">' + tags + '</div>'
        '</div>'
    )


def bloco_oc3_init():
    n_total = len(OC3_POSICOES) + len(OC3_MOV) + len(OC3_CADASTROS) + len(OC3_PROVENTOS) + len(OC3_MERCADO)
    inner = (
        '<div class="bloco-header">Inicializa&ccedil;&atilde;o &mdash; Batimento OC3</div>'
        '<div class="bloco-sub">Script: <strong>FLBLIPO_Batimento_PnL_OC3.py</strong>'
        ' &nbsp;&middot;&nbsp; Interface: <strong>OC3 (COM / ADO)</strong></div>'
        '<div class="bloco-code">'
        '<span class="code-comment"># entrada</span><br>'
        'dt_ini, dt_fim = <span class="str">"YYYY-MM-DD"</span>, <span class="str">"YYYY-MM-DD"</span><br>'
        'lista_fundos   = [<span class="str">"FICFI53086"</span>, ...]<br>'
        '<span class="code-comment"># sem escrita em banco — export only</span><br>'
        'oc3 = <span class="kw">OC3()</span> &nbsp;<span class="code-comment"># nova inst&acirc;ncia por fundo</span><br>'
        '_recordset_to_df(dados) &nbsp;<span class="code-comment"># ADO Recordset &rarr; DataFrame</span>'
        "</div>"
        '<div class="bloco-detail">'
        '<span class="badge badge-teal">' + str(n_total) + ' consultas</span> por fundo &nbsp;'
        '<span class="badge badge-blue">openpyxl</span> uma aba por consulta'
        "</div>"
    )
    return node(inner, "c-oc3-init", 560)


def bloco_oc3_posicoes():
    return _oc3_group(
        "Posi&ccedil;&otilde;es &mdash; 11 consultas",
        OC3_POSICOES, "#006064", "#80cbc4"
    )


def bloco_oc3_mov():
    return _oc3_group(
        "Movimenta&ccedil;&otilde;es &mdash; 6 consultas",
        OC3_MOV, "#0277bd", "#81d4fa"
    )


def bloco_oc3_cadastros():
    return _oc3_group(
        "Cadastros / Ativos &mdash; 4 consultas (filtro por fundo)",
        OC3_CADASTROS, "#01579b", "#b3e5fc"
    )


def bloco_oc3_proventos():
    return _oc3_group(
        "Proventos &mdash; 4 consultas",
        OC3_PROVENTOS, "#4a148c", "#ce93d8"
    )


def bloco_oc3_mercado():
    return _oc3_group(
        "Refer&ecirc;ncia de Mercado &mdash; 2 consultas",
        OC3_MERCADO, "#1b5e20", "#a5d6a7"
    )


def bloco_oc3_wrapper():
    inner = (
        bloco_oc3_posicoes() +
        '<div style="height:8px"></div>' +
        bloco_oc3_mov() +
        '<div style="height:8px"></div>' +
        bloco_oc3_cadastros() +
        '<div style="height:8px"></div>' +
        bloco_oc3_proventos() +
        '<div style="height:8px"></div>' +
        bloco_oc3_mercado()
    )
    n_total = len(OC3_POSICOES) + len(OC3_MOV) + len(OC3_CADASTROS) + len(OC3_PROVENTOS) + len(OC3_MERCADO)
    return (
        '<div class="group" style="width:880px;border-color:#006064">'
        '<div class="group-title" style="color:#80cbc4">'
        'Loop por Fundo &mdash; ' + str(n_total) + ' consultas OC3 sequenciais'
        ' &nbsp;&middot;&nbsp; <code style="font-size:.6rem">_consulta(oc3, nome, fn)</code>'
        ' &nbsp;&middot;&nbsp; erro &rarr; DataFrame vazio (n&atilde;o interrompe)'
        '</div>'
        + inner +
        '</div>'
    )


def bloco_oc3_saida():
    n_total = len(OC3_POSICOES) + len(OC3_MOV) + len(OC3_CADASTROS) + len(OC3_PROVENTOS) + len(OC3_MERCADO)
    inner = (
        '<div class="bloco-header">Sa&iacute;da Excel por Fundo &mdash; ' + str(n_total) + ' abas</div>'
        '<div class="bloco-sub">'
        '<code>../../output/batimento_oc3/{yyyymmdd}/{fundo}_{yyyymmdd}.xlsx</code>'
        '</div>'
        '<div class="bloco-code">'
        '<span class="kw">with</span> pd.ExcelWriter(file_path, engine=<span class="str">\'openpyxl\'</span>):<br>'
        '&nbsp;&nbsp;<span class="kw">for</span> nome_aba, df <span class="kw">in</span> abas.items():<br>'
        '&nbsp;&nbsp;&nbsp;&nbsp;df.to_excel(writer, sheet_name=nome_aba, index=<span class="kw">False</span>)'
        "</div>"
        '<div class="bloco-detail">'
        '<span class="badge badge-teal">index=False</span> sem numera&ccedil;&atilde;o de linha &nbsp;'
        '<span class="badge badge-blue">sem dup.</span> <code>dict.fromkeys(lista_fundos)</code>'
        "</div>"
    )
    return node(inner, "c-oc3-out", 680)


def build_oc3_page():
    sections = [
        '<div class="node oval c-start">INICIO</div>',
        arrow(),
        status_wrap(bloco_oc3_init(),    "oc3-init"),
        arrow(),
        status_wrap(bloco_oc3_wrapper(), "oc3-loop"),
        arrow(),
        status_wrap(bloco_oc3_saida(),   "oc3-saida"),
        arrow(),
        '<div class="node oval c-end">FIM</div>',
    ]
    flow = "\n".join(sections)
    return (
        '<div id="pg12" class="pg pg-detail">'
        '<button class="back-btn" style="color:#80cbc4;border-color:#004d40" onclick="goIdx()">&#x2190; Voltar</button>'
        "<h1>Fluxograma &mdash; Batimento dll &mdash; OC3</h1>\n"
        '<div class="subtitle">Python &middot; FLBLIPO_Batimento_PnL_OC3.py &middot; Interface COM (OC3) &middot; 27 consultas por fundo</div>\n'
        '<div class="page-box" style="border-color:#006064">\n'
        '<div class="page-box-title" style="color:#006064">Batimento dll &mdash; OC3</div>\n'
        '<div class="page-layout">\n'
        '  <div class="flow-col">\n'
        "    " + bloco_legend() + "\n"
        '    <div class="flow">\n'
        + flow + "\n"
        "    </div>\n"
        "    " + bloco_legend() + "\n"
        "  </div>\n"
        "</div>\n"
        "</div>\n"
        "</div>"
    )


def bloco_drf_init():
    datas_rows = "".join(
        '<div class="clear-row">'
        '<span class="clear-aba" style="color:#f0c97a;min-width:60px">' + d[0] + '</span>'
        '<span class="clear-cols" style="color:#ffd54f;min-width:180px">' + d[1] + '</span>'
        '<span class="clear-count" style="min-width:280px;color:#aaa;font-size:.62rem">' + d[2] + '</span>'
        '</div>'
        for d in DRF_DATAS
    )
    inner = (
        '<div class="bloco-header">Par&acirc;metros &mdash; Dash Mesa RF</div>'
        '<div class="bloco-sub">Arquivo: <strong>Dash Mesa RF_.xlsb</strong>'
        ' &nbsp;&middot;&nbsp; Banco: <strong>DBSX337</strong>'
        ' &nbsp;&middot;&nbsp; <strong>' + str(len(DRF_FUNDOS_GRUPOS)) + ' fundos</strong>'
        ' &nbsp;&middot;&nbsp; PL total: <strong>~R$ 61.162 MM</strong></div>'
        + datas_rows
    )
    return node(inner, "c-bat-init", 640)


def bloco_drf_fundos():
    grupos = {}
    for cod, grp in DRF_FUNDOS_GRUPOS:
        grupos.setdefault(grp, []).append(cod)
    rows = ""
    for grp, fds in grupos.items():
        rows += (
            '<div class="clear-row">'
            '<span class="clear-aba" style="color:#f0c97a;min-width:150px;font-size:.65rem">' + grp + '</span>'
            '<span class="clear-cols" style="font-size:.6rem;font-family:Consolas,monospace;color:#ccc">'
            + " &middot; ".join(fds)
            + '</span>'
            '</div>'
        )
    inner = (
        '<div class="bloco-header">Lista de Fundos &mdash; ' + str(len(DRF_FUNDOS_GRUPOS)) + ' fundos / 8 grupos</div>'
        '<div class="bloco-sub">SRF &mdash; Mesa Renda Fixa</div>'
        + rows
    )
    return node(inner, "c-bat-init", 820)


def bloco_drf_queries():
    tags = "".join(
        '<div class="tag clickable ' + CAT_CSS.get(q[3], "t-pos") + '"'
        ' onclick="showSQL(\'' + q[0] + '\')" title="ver SQL">'
        '<strong>' + q[0] + '</strong>'
        '<span class="src">' + q[2] + ' &nbsp;&middot;&nbsp; ' + q[1] + '</span>'
        '<span class="lbl">' + q[4] + ' &nbsp;<em style="opacity:.5;font-size:.6rem">ver SQL</em></span>'
        '</div>'
        for q in DRF_QUERIES
    )
    return (
        '<div class="group" style="width:900px;border-color:#c9850a">'
        '<div class="group-title" style="color:#f0c97a">'
        'Queries SQL &mdash; ' + str(len(DRF_QUERIES)) + ' consultas &times; {D0, D-1} &mdash; Fonte: DBSX337'
        '</div>'
        '<div class="group-grid cols2">' + tags + '</div>'
        '</div>'
    )


def bloco_drf_transformacoes():
    rows = "".join(
        '<div class="tag ' + CAT_CSS.get(t[3], "t-dur") + '">'
        '<strong>' + t[0] + '</strong>'
        '<span class="src"><code>' + t[1] + '</code></span>'
        '<span class="lbl">' + t[2] + '</span>'
        '</div>'
        for t in DRF_TRANSFORMACOES
    )
    return group(
        "C&aacute;lculos e Transforma&ccedil;&otilde;es &mdash; Pivot, Alpha, Duration, Vertex",
        rows, cols=2, width=900, border_color="#7b5800",
    )


def bloco_drf_abas():
    tags = "".join(
        '<div class="tag ' + CAT_CSS.get(a[2], "t-pos") + '">'
        '<strong>' + a[0] + '</strong>'
        '<span class="lbl">' + a[1] + '</span>'
        '</div>'
        for a in DRF_ABAS_SAIDA
    )
    return (
        '<div class="group" style="width:900px;border-color:#c9850a">'
        '<div class="group-title" style="color:#f0c97a">'
        'Abas de Sa&iacute;da &mdash; ' + str(len(DRF_ABAS_SAIDA)) + ' vis&otilde;es'
        '</div>'
        '<div class="group-grid cols2">' + tags + '</div>'
        '</div>'
    )


def bloco_drf_vertice():
    pre_vertices  = sorted({v[1] for v in DRF_VERTICE_COLS if v[0] == "Juros Pre"})
    ipca_vertices = sorted({v[1] for v in DRF_VERTICE_COLS if v[0] == "Inflacao"})
    inner = (
        '<div class="bloco-header">Estrutura de V&eacute;rtices &mdash; Rates BR</div>'
        '<div class="bloco-sub">Juros Pr&eacute;-fixados e Infla&ccedil;&atilde;o (IPCA) por vencimento</div>'
        '<div class="bloco-code">'
        '<span style="color:#f0c97a">Pr&eacute; (' + str(len(pre_vertices)) + ' v&eacute;rtices):</span> '
        + " &middot; ".join(pre_vertices) + '<br>'
        '<span style="color:#80cbc4">IPCA (' + str(len(ipca_vertices)) + ' v&eacute;rtices):</span> '
        + " &middot; ".join(ipca_vertices)
        + '</div>'
        '<div class="bloco-detail">'
        '<span class="badge badge-teal">eq_ano</span> 1Y Equivalent &nbsp;'
        '<span class="badge badge-blue">ModDur</span> Duration Modificada'
        '</div>'
    )
    return node(inner, "c-bat-init", 820)


def bloco_drf_estrategias():
    blocos = {}
    for e in DRF_ESTRATEGIAS:
        blocos.setdefault(e[0], []).append(e)
    rows = ""
    for bloco_nome, items in blocos.items():
        gestoras = " &middot; ".join(sorted({i[1] for i in items}))
        moedas   = " &middot; ".join(sorted({i[3] for i in items if i[3] not in ("-", "PRE", "EM", "DM", "HEDGE", "JUR", "FX")}))
        fatores  = " &middot; ".join(sorted({i[5] for i in items}))
        rows += (
            '<div class="clear-row">'
            '<span class="clear-aba" style="color:#f0c97a;min-width:90px">' + bloco_nome + '</span>'
            '<span class="clear-cols" style="min-width:180px;font-size:.65rem">' + gestoras + '</span>'
            '<span class="clear-count" style="font-size:.62rem;color:#aaa">' + (moedas or "-") + ' &nbsp;|&nbsp; ' + fatores + '</span>'
            '</div>'
        )
    inner = (
        '<div class="bloco-header">Estrat&eacute;gias &mdash; CAMBIO / OFFSHORE / ONSHORE</div>'
        '<div class="bloco-sub">Gestoras: ARTHUR &middot; YURI &middot; FX &middot; RATES &middot; SIS &middot; JUR</div>'
        + rows
    )
    return node(inner, "c-bat-init", 700)


def build_dash_mesa_rf_page():
    sections = [
        '<div class="node oval c-start">INICIO</div>',
        arrow(),
        status_wrap(bloco_drf_init(),          "drf-init"),
        arrow(),
        status_wrap(bloco_drf_fundos(),        "drf-fundos"),
        arrow(),
        status_wrap(bloco_drf_queries(),       "drf-queries"),
        arrow(),
        status_wrap(bloco_drf_transformacoes(),"drf-transf"),
        arrow(),
        status_wrap(bloco_drf_vertice(),       "drf-vertice"),
        arrow(),
        status_wrap(bloco_drf_estrategias(),   "drf-estrat"),
        arrow(),
        status_wrap(bloco_drf_abas(),          "drf-abas"),
        arrow(),
        '<div class="node oval c-end">FIM</div>',
    ]
    flow = "\n".join(sections)
    return (
        '<div id="pg13" class="pg pg-detail">'
        '<button class="back-btn" style="color:#f0c97a;border-color:#7d5200" onclick="goIdx()">&#x2190; Voltar</button>'
        "<h1>Fluxograma &mdash; Dash Mesa RF</h1>\n"
        '<div class="subtitle">Excel Power Query &middot; Dash Mesa RF_.xlsb &middot; SRF &middot; DBSX337</div>\n'
        '<div class="page-box" style="border-color:#c9850a">\n'
        '<div class="page-box-title" style="color:#c9850a">Dash Mesa RF &mdash; SRF</div>\n'
        '<div class="page-layout">\n'
        '  <div class="flow-col">\n'
        "    " + bloco_legend() + "\n"
        '    <div class="flow">\n'
        + flow + "\n"
        "    </div>\n"
        "    " + bloco_legend() + "\n"
        "  </div>\n"
        "</div>\n"
        "</div>\n"
        "</div>"
    )


def bloco_off_init():
    inner = (
        '<div class="bloco-header">Inicializa&ccedil;&atilde;o &mdash; Batimento Offshore</div>'
        '<div class="bloco-sub">Script: <strong>FLBLIPO_Batimento_PnL_Offshore.py</strong>'
        ' &nbsp;&middot;&nbsp; Banco: <strong>SQNPRC028 / DBSX337</strong></div>'
        '<div class="bloco-code">'
        'data_ref = <span class="kw">QsDate</span>(today).add_business_days(<span class="str">-1</span>) <span class="code-comment"># T-1</span><br>'
        'arred = <span class="str">1</span> &nbsp;<span class="code-comment"># threshold R$ &mdash; |DifPnL| &lt; 1 ignorado</span><br>'
        'conn = <span class="kw">pyodbc.connect</span>(<span class="str">"SQL Server;SERVER=SQNPRC028"</span>)<br>'
        'lista_fundos = [<span class="str">"ESP_FIASSETCORE"</span>, ...]'
        "</div>"
        '<div class="bloco-detail">'
        '<span class="badge badge-purple">SSnC</span> SISTEMAS_SSC_PED_INTRADAY &nbsp;'
        '<span class="badge badge-teal">IAM</span> VW_FUNDOS_POSICAO'
        "</div>"
    )
    return node(inner, "c-off-init", 560)


def bloco_off_depara():
    items = [
        ("CSH", "CaixaCPR"), ("EQYLST / EQYNLT", "Equity"),
        ("CMDFUT", "Future"), ("CMDOPT", "Option"),
        ("CNTSWP / CNTFRA / CREDITDEFAULTSWAP / EQITYSWP", "Swap"),
        ("BNDSVN / BNDCRP / BNDTRS", "Fixed Income"),
        ("FXF", "Future"), ("COMPAP", "Fixed Income"),
    ]
    rows = "".join(
        '<div class="clear-row">'
        '<span class="clear-aba" style="color:#ffab91;min-width:260px;font-size:.68rem">' + k + '</span>'
        '<span class="clear-cols" style="color:#ff8a65;font-weight:700">&rarr; ' + v + '</span>'
        '</div>'
        for k, v in items
    )
    inner = (
        '<div class="bloco-header">Mapeamento de Tipos &mdash; de_para_dict</div>'
        '<div class="bloco-sub">SSC InvAssetType &rarr; classe IAM</div>'
        + rows
    )
    return node(inner, "c-off-query", 560)


def bloco_off_classes():
    tags = "".join(
        '<div class="tag clickable ' + CAT_CSS.get(c[3], "t-pos") + '"'
        ' onclick="showSQL(\'' + (
            'off_equities_ssc'     if c[0] == 'Equities'     else
            'off_fixed_income_ssc' if c[0] == 'Fixed Income' else
            'off_resumo_ssc'       if c[0] == 'Cash / CPR'   else
            'off_resumo_iam'
        ) + '\')" title="ver SQL">'
        '<strong>' + c[0] + '</strong>'
        '<span class="src">SSnC: <code>' + c[2] + '</code></span>'
        '<span class="dest">IAM: ' + c[1] + '</span>'
        '<span class="lbl">' + c[4] + ' &nbsp;<em style="opacity:.5;font-size:.6rem">ver SQL</em></span>'
        '</div>'
        for c in OFF_CLASSES
    )
    return (
        '<div class="group" style="width:820px;border-color:#e64a19">'
        '<div class="group-title" style="color:#ffab91">'
        'Batimentos por Classe &mdash; OUTER JOIN SSnC &times; IAM &nbsp;&middot;&nbsp; '
        + str(len(OFF_CLASSES)) + ' classes'
        '</div>'
        '<div class="group-grid cols2">' + tags + '</div>'
        '</div>'
    )


def bloco_off_difs():
    rows = "".join(
        '<div class="clear-row">'
        '<span class="clear-aba" style="color:#ff8a65;min-width:130px;font-size:.68rem"><code>' + d[0] + '</code></span>'
        '<span class="clear-cols" style="font-size:.65rem;font-family:Consolas,monospace">' + d[1] + '</span>'
        '<span class="clear-count" style="min-width:200px;font-size:.62rem;color:#888">' + d[2] + '</span>'
        '</div>'
        for d in OFF_DETALHE_COLS
    )
    inner = (
        '<div class="bloco-header">Colunas de Diferen&ccedil;a &mdash; df_Difs</div>'
        '<div class="bloco-sub">'
        'CONCAT [Dif_Opt + Dif_Fut + Dif_Acao + Dif_CPR + Dif_Fixed]'
        ' &nbsp;&middot;&nbsp; filtro |DifPnL| &ge; R$1'
        '</div>'
        + rows
    )
    return node(inner, "c-off-merge", 680)


def bloco_off_estrat():
    rows = "".join(
        '<div class="clear-row">'
        '<span class="clear-aba" style="color:#ffe082;min-width:240px;font-size:.68rem">' + e[0] + '</span>'
        '<span class="clear-cols" style="font-size:.65rem;font-family:Consolas,monospace;color:#ffab91">' + e[1] + '</span>'
        '</div>'
        for e in OFF_ESTRAT_LOGICA
    )
    inner = (
        '<div class="bloco-header">Distribui&ccedil;&atilde;o de PnL por Estrat&eacute;gia</div>'
        '<div class="bloco-sub">'
        'Loop por fundo &rarr; query FUNDOS_POSICAO (est1&ndash;est5) &nbsp;'
        '<span class="badge badge-purple" style="cursor:pointer" onclick="showSQL(\'off_estrategias\')">ver SQL</span>'
        '</div>'
        + rows +
        '<div class="bloco-code" style="margin-top:8px">'
        'Qtd = quantidade <span class="kw">if</span> &gt; 0 <span class="kw">else</span> quantidade_abertura<br>'
        'DifPnLEstrat = DifPnL &times; (Qtd / Qtd_total)<br>'
        'count = SUM por (fundo, ativo) &rarr; indica m&uacute;ltiplas estrat&eacute;gias'
        '</div>'
    )
    return node(inner, "c-off-estrat", 680)


def bloco_off_saidas():
    rows = "".join(
        '<div class="clear-row">'
        '<span class="clear-aba" style="color:#f0c97a;min-width:160px;font-size:.68rem">' + a[0] + '</span>'
        '<span class="clear-cols ' + CAT_CSS.get(a[2], "t-pos") + '" style="font-size:.62rem;background:none;border:none;padding:0">' + a[1] + '</span>'
        '</div>'
        for a in OFF_ABAS
    )
    inner = (
        '<div class="bloco-header">Sa&iacute;da Excel &mdash; ' + str(len(OFF_ABAS)) + ' abas</div>'
        '<div class="bloco-sub">'
        '<code>../../output/batimento_off/renda_fixa/ResumoMartelo_{timestamp}_2.xlsx</code>'
        '</div>'
        + rows +
        '<div class="bloco-detail" style="margin-top:6px">'
        '<span class="badge badge-blue">frozen panes</span> linha 1 (cabe&ccedil;alhos) &nbsp;'
        '<span class="badge badge-teal">auto-open</span> abre ap&oacute;s gera&ccedil;&atilde;o'
        '</div>'
    )
    return node(inner, "c-off-out", 660)


def build_offshore_page():
    sections = [
        '<div class="node oval c-start">INICIO</div>',
        arrow(),
        status_wrap(bloco_off_init(),   "off-init"),
        arrow(),
        status_wrap(bloco_off_depara(), "off-depara"),
        arrow(),
        status_wrap(bloco_off_classes(), "off-classes"),
        arrow(),
        status_wrap(bloco_off_difs(),   "off-difs"),
        arrow(),
        status_wrap(bloco_off_estrat(), "off-estrat"),
        arrow(),
        status_wrap(bloco_off_saidas(), "off-saidas"),
        arrow(),
        '<div class="node oval c-end">FIM</div>',
    ]
    flow = "\n".join(sections)
    return (
        '<div id="pg11" class="pg pg-detail">'
        '<button class="back-btn" style="color:#ffab91;border-color:#7f2200" onclick="goDetailRF2()">&#x2190; Voltar</button>'
        "<h1>Fluxograma &mdash; Batimento Offshore PnL</h1>\n"
        '<div class="subtitle">Python &middot; FLBLIPO_Batimento_PnL_Offshore.py &middot; SSnC vs IAM &middot; SQNPRC028/DBSX337</div>\n'
        '<div class="page-box" style="border-color:#bf360c">\n'
        '<div class="page-box-title" style="color:#bf360c">Batimento Offshore &mdash; SSnC vs IAM</div>\n'
        '<div class="page-layout">\n'
        '  <div class="flow-col">\n'
        "    " + bloco_legend() + "\n"
        '    <div class="flow">\n'
        + flow + "\n"
        "    </div>\n"
        "    " + bloco_legend() + "\n"
        "  </div>\n"
        "</div>\n"
        "</div>\n"
        "</div>"
    )


def bloco_pj_init():
    inner = (
        '<div class="bloco-header">Inicializa&ccedil;&atilde;o &mdash; Pre&ccedil;o Justo ETF</div>'
        '<div class="bloco-sub">Main: <strong>FLBLIPO_MainPrecoJusto.py</strong>'
        ' &nbsp;&middot;&nbsp; M&oacute;dulo: <strong>FLBLIPO_PrecoJustoETF.py</strong></div>'
        '<div class="bloco-code">'
        'd0 = <span class="kw">date.today()</span> &nbsp;<span class="code-comment"># data de execu&ccedil;&atilde;o</span><br>'
        'd1 = <span class="kw">QsDate</span>(d0).add_business_days(<span class="str">-1</span>) &nbsp;<span class="code-comment"># posi&ccedil;&atilde;o D-1</span><br>'
        '<span class="code-comment"># Restri&ccedil;&atilde;o hor&aacute;ria</span><br>'
        '<span class="kw">if</span> <span class="str">10:15</span> &le; agora &le; <span class="str">18:00</span>: executar'
        "</div>"
        '<div class="bloco-detail">'
        '<span class="badge badge-teal">d0</span> VNA + BBG &nbsp;'
        '<span class="badge badge-blue">d1</span> Posi&ccedil;&atilde;o VCRA + duration ANBIMA'
        "</div>"
    )
    return node(inner, "c-pj-init", 540)


def bloco_pj_funcoes():
    tags = "".join(
        '<div class="tag clickable ' + CAT_CSS.get(f[3], "t-pos") + '"'
        ' onclick="showSQL(\'' + (
            'pj_posicao_rf'  if 'RF'    in f[0] else
            'pj_posicao_lft' if 'Selic' in f[0] else
            ''
        ) + '\')" '
        + ('title="ver SQL"' if any(k in f[0] for k in ['RF', 'Selic']) else '') + '>'
        '<strong>' + f[0] + '()</strong>'
        '<span class="src">ETFs: ' + f[1] + '</span>'
        '<span class="dest">' + f[2] + '</span>'
        '<span class="lbl">' + f[4]
        + (' &nbsp;<em style="opacity:.5;font-size:.6rem">ver SQL</em>' if any(k in f[0] for k in ['RF', 'Selic']) else '')
        + '</span>'
        '</div>'
        for f in PJ_FUNCOES
    )
    return group(
        "4 Fun&ccedil;&otilde;es Geradoras &mdash; rodar_precoJusto_main()",
        tags, cols=2, width=860, border_color="#00838f",
    )


def bloco_pj_fontes_db():
    tags = "".join(
        '<div class="tag clickable ' + CAT_CSS.get(f[2], "t-pos") + '"'
        + (' onclick="showSQL(\'' + (
            'pj_posicao_rf'  if 'VCRAPRF' in f[0] and 'lft' not in f[0].lower() and 'prdp' not in f[0] else
            'pj_pl_ex_bs'    if 'VCRAPLSI' in f[0] else
            'pj_duration'    if 'tbhh3031' in f[0] else
            'pj_vna_ntnb'    if 'tbhh3042' in f[0] else
            'pj_posicao_lft' if 'btc' in f[0].lower() else ''
        ) + '\')" title="ver SQL"' if any(k in f[0] for k in ['VCRAPRF','VCRAPLSI','tbhh3031','tbhh3042']) else '')
        + '>'
        '<strong>' + f[0] + '</strong>'
        '<span class="lbl">' + f[1]
        + (' &nbsp;<em style="opacity:.5;font-size:.6rem">ver SQL</em>' if any(k in f[0] for k in ['VCRAPRF','VCRAPLSI','tbhh3031','tbhh3042']) else '')
        + '</span>'
        '</div>'
        for f in PJ_FONTES_DB
    )
    return group(
        "Fontes de Dados &mdash; Banco DBSX337 (d1 = D-1 &uacute;til)",
        tags, cols=2, width=820, border_color="#0277bd",
    )


def bloco_pj_fontes_bbg():
    tags = "".join(
        '<div class="tag ' + CAT_CSS.get(f[2], "t-pos") + '">'
        '<strong>' + f[0] + '</strong>'
        '<span class="src">campo: <code>' + f[1] + '</code></span>'
        '<span class="lbl">' + f[3] + '</span>'
        '</div>'
        for f in PJ_FONTES_BBG
    )
    return (
        '<div class="group" style="width:820px;border-color:#2e7d32">'
        '<div class="group-title" style="color:#a5d6a7">'
        'Bloomberg (BBG) &mdash; Pre&ccedil;os, Yields, Duration, FX em tempo real'
        '</div>'
        '<div class="group-grid cols2">' + tags + '</div>'
        '</div>'
    )


def bloco_pj_calculos():
    rows = "".join(
        '<div class="clear-row">'
        '<span class="clear-aba" style="color:#80deea;min-width:180px;font-size:.68rem">' + c[0] + '</span>'
        '<span class="clear-cols" style="font-size:.65rem;font-family:Consolas,monospace;color:#81d4fa">' + c[1] + '</span>'
        '<span class="clear-count" style="min-width:220px;font-size:.62rem;color:#888">' + c[2] + '</span>'
        '</div>'
        for c in PJ_CALCULOS
    )
    inner = (
        '<div class="bloco-header">L&oacute;gica de C&aacute;lculo &mdash; por fun&ccedil;&atilde;o</div>'
        '<div class="bloco-sub">'
        + str(len(PJ_CALCULOS)) + ' f&oacute;rmulas &mdash; Preco_PnL.assets.* + c&aacute;lculo pr&oacute;prio'
        '</div>'
        + rows
    )
    return node(inner, "c-pj-calc", 760)


def bloco_pj_saidas():
    tags = "".join(
        '<div class="tag ' + CAT_CSS.get(s[2], "t-pos") + '">'
        '<strong>' + s[0] + '</strong>'
        '<span class="src">' + s[1] + '</span>'
        '<span class="lbl">' + s[3] + '</span>'
        '</div>'
        for s in PJ_SAIDAS
    )
    inner = (
        '<div class="bloco-header">Sa&iacute;das &mdash; CSV + Logs</div>'
        '<div class="bloco-sub">Formato: delimitador <code>;</code> &nbsp;|&nbsp; decimal <code>,</code></div>'
        '<div class="bloco-code">'
        '<span class="code-comment"># Colunas do CSV final</span><br>'
        'DATA_HORA_ATUALIZACAO &middot; ETF &middot; INDICE<br>'
        'YIELD_ESTIMADO &middot; YIELD_ULTIMO_NEGOCIO &middot; SPREAD<br>'
        'DURATION &middot; VALOR_ESTIMADO_COTA'
        '</div>'
        '<div class="group-grid cols3" style="margin-top:8px">' + tags + '</div>'
    )
    return node(inner, "c-pj-out", 760)


def build_precojusto_page():
    sections = [
        '<div class="node oval c-start">INICIO</div>',
        arrow(),
        status_wrap(bloco_pj_init(),        "pj-init"),
        arrow(),
        status_wrap(bloco_pj_funcoes(),     "pj-funcoes"),
        arrow(),
        status_wrap(bloco_pj_fontes_db(),   "pj-db"),
        arrow(),
        status_wrap(bloco_pj_fontes_bbg(),  "pj-bbg"),
        arrow(),
        status_wrap(bloco_pj_calculos(),    "pj-calc"),
        arrow(),
        status_wrap(bloco_pj_saidas(),      "pj-saidas"),
        arrow(),
        '<div class="node oval c-end">FIM</div>',
    ]
    flow = "\n".join(sections)
    return (
        '<div id="pg10" class="pg pg-detail">'
        '<button class="back-btn" style="color:#80deea;border-color:#004d52" onclick="goIdx()">&#x2190; Voltar</button>'
        "<h1>Fluxograma &mdash; Pre&ccedil;o Justo ETF</h1>\n"
        '<div class="subtitle">Python &middot; FLBLIPO_MainPrecoJusto.py + FLBLIPO_PrecoJustoETF.py &middot; DBSX337 + Bloomberg</div>\n'
        '<div class="page-box" style="border-color:#00838f">\n'
        '<div class="page-box-title" style="color:#00838f">Pre&ccedil;o Justo ETF &mdash; Fair Value</div>\n'
        '<div class="page-layout">\n'
        '  <div class="flow-col">\n'
        "    " + bloco_legend() + "\n"
        '    <div class="flow">\n'
        + flow + "\n"
        "    </div>\n"
        "    " + bloco_legend() + "\n"
        "  </div>\n"
        "</div>\n"
        "</div>\n"
        "</div>"
    )


def bloco_saccota_init():
    inner = (
        '<div class="bloco-header">Inicializa&ccedil;&atilde;o &mdash; SAC_Cota_posicao()</div>'
        '<div class="bloco-sub">Script: <strong>SAC_Cota.py</strong>'
        ' &nbsp;&middot;&nbsp; Banco: <strong>Lake (Conn) + OC3Light (ConnOC3Light)</strong></div>'
        '<div class="bloco-code">'
        '<span class="code-comment"># par&acirc;metros opcionais</span><br>'
        'date_ref = <span class="kw">None</span> &nbsp;&middot;&nbsp; '
        'lista_fundos = <span class="str">[]</span> &nbsp;&middot;&nbsp; '
        'lista_ativos = <span class="str">[]</span><br>'
        'retorna_df = <span class="kw">False</span> &nbsp;&middot;&nbsp; '
        'contingencia = <span class="kw">True</span><br>'
        '<span class="code-comment"># contingencia global via habilitar_contingencia_oc3()</span><br>'
        'conn = <span class="kw">Conn</span>() &nbsp;&middot;&nbsp; '
        'connoc3light = <span class="kw">ConnOC3Light</span>()'
        '</div>'
        '<div class="bloco-detail">'
        '<span class="badge badge-blue">Lake</span> DBSX337 / Lake &nbsp;'
        '<span class="badge badge-teal">OC3Light</span> fallback quando contingencia=False'
        '</div>'
    )
    return node(inner, "c-db-init", 620)


def bloco_saccota_datas():
    inner = (
        '<div class="bloco-header">C&aacute;lculo de Datas</div>'
        '<div class="bloco-sub"><code>QsDate</code> &mdash; calend&aacute;rio Brasil</div>'
        '<div class="bloco-code">'
        '<span class="kw">if</span> date_ref <span class="kw">is None</span>:<br>'
        '&nbsp;&nbsp;dateQuery = today<br>'
        '&nbsp;&nbsp;dateD1 = QsDate(today).add_business_days(<span class="str">-1</span>)<br>'
        '&nbsp;&nbsp;dateD2 = QsDate(today).add_business_days(<span class="str">-2</span>)<br>'
        '<span class="kw">else</span>:<br>'
        '&nbsp;&nbsp;dateQuery = strptime(date_ref, <span class="str">\'%Y-%m-%d\'</span>)<br>'
        '&nbsp;&nbsp;dateD1 = QsDate(dateQuery) &nbsp;&nbsp;<span class="code-comment"># = date_ref</span><br>'
        '&nbsp;&nbsp;dateD2 = QsDate(dateQuery).add_business_days(<span class="str">-1</span>)'
        '</div>'
        '<div class="bloco-detail">'
        '<span class="badge badge-blue">D-1</span> posi&ccedil;&atilde;o de refer&ecirc;ncia &nbsp;'
        '<span class="badge badge-blue">D-2</span> quantidade_abertura'
        '</div>'
    )
    return node(inner, "c-db-data", 580)


def bloco_saccota_fundos():
    tag = (
        '<div class="tag t-fdo clickable" onclick="showSQL(\'sac_dic_fundos\')">'
        '<strong>SISTEMAS_DICIONARIO_FUNDOS</strong>'
        '<span class="src">sistema = \'SAC\' &middot; tipo = \'Carteira\'</span>'
        '<span class="dest">'
        'lista_fundos vazia &rarr; todos os fundos &nbsp;|&nbsp; preenchida &rarr; filtrado por IAM'
        '</span>'
        '<span class="lbl">Sa&iacute;da: df_fundos &mdash; codigo_sistema, codigo_IAM_fundo</span>'
        '</div>'
    )
    return (
        '<div class="group" style="width:640px;border-color:#3a82b5">'
        '<div class="group-title" style="color:#90c4e4">'
        'Lista de Fundos &mdash; clique para ver SQL'
        '</div>'
        '<div class="group-grid cols1">' + tag + '</div>'
        '</div>'
    )


def bloco_saccota_query():
    branch_sac = (
        '<div class="tag t-pos clickable" onclick="showSQL(\'sac_pos_vcrapfdo\')">'
        '<strong>contingencia = True</strong>'
        '<span class="src">vcrapfdo &middot; Lake / SAC</span>'
        '<span class="dest">WHERE dt IN (D-1, D-2) AND clcli_cd IN ({fundos})</span>'
        '<span class="lbl">GROUP BY CLCLI_CD, dt, FICAD_CD, TIPO_CLASSIF, cd_cliente_sac, BAINS_CD</span>'
        '</div>'
    )
    branch_oc3 = (
        '<div class="tag t-fdo clickable" onclick="showSQL(\'sac_pos_oc3light\')">'
        '<strong>contingencia = False</strong>'
        '<span class="src">VWOC3_04W_FUNDO_POSICAO_ASSET &middot; OC3Light</span>'
        '<span class="dest">JOIN TBOC3_99W_CARTEIRA_CODIGO + TBOC3_96W_FUNDO_ATIVO</span>'
        '<span class="lbl">pd.read_sql(sql, connoc3light)</span>'
        '</div>'
    )
    return (
        '<div class="group" style="width:800px;border-color:#1a8a7a">'
        '<div class="group-title" style="color:#5dd6c4">'
        'Query de Posi&ccedil;&atilde;o de Cotas &mdash; D-1 e D-2 &mdash; clique na branch para ver SQL'
        '</div>'
        '<div class="group-grid cols2">' + branch_sac + branch_oc3 + '</div>'
        '<div class="bloco-detail" style="padding:6px 12px">'
        '<span class="badge badge-teal">Colunas</span> '
        'clcli_cd &middot; dt &middot; ficad_cd &middot; cd_tipo_classificacao &middot; qt_cota &middot; vl_cota &middot; cd_cliente_sac &middot; cd_emissor'
        '</div>'
        '</div>'
    )


def bloco_saccota_tratamento():
    passos = [
        ("dropna",         "cd_tipo_classificacao",                               "Remove linhas sem tipo (nao-cotas)"),
        ("fillna",         "cd_cliente_sac &larr; ficad_cd",                      "Codigo SAC nulo substituido pelo ficad_cd"),
        ("rename",         "dt&rarr;date, clcli_cd&rarr;Fundo, cd_cliente_sac&rarr;Codigo, qt_cota&rarr;quantidade, vl_cota&rarr;preco_sistema_origem", "Renomear e selecionar colunas"),
        ("split D1/D2",    "dfCota_D1 = date==dateD1 &nbsp;|&nbsp; dfCota_D2 = date==dateD2", "Separar D-1 (posicao) de D-2 (abertura)"),
        ("merge outer",    "dfCota = dfCota_D1.merge(dfCota_D2[quantidade_abertura], how=outer)", "Merge D1 + D2 por (Fundo, Codigo)"),
        ("fillna 0",       "quantidade, quantidade_abertura, preco_sistema_origem", "Zerar NaN apos merge outer"),
        ("merge fundos",   "df_fundos &rarr; codigo_IAM_fundo",                   "Join por codigo_sistema (Fundo)"),
        ("query ativos",   "VIEW_FUNDOS_CADASTRO_ATIVOS_LAST_VALUES campo=codigo_cota_SAC", "Dicionario SAC -> IAM (eval + explode)"),
        ("merge ativos",   "df_dic_ativos &rarr; codigo_IAM_ativo",               "Join por Codigo"),
        ("conversao tipos","date, quantidade, quantidade_abertura, preco_sistema_origem", "pd.to_datetime / pd.to_numeric"),
        ("filtro preco",   "preco_sistema_origem > 0",                            "Remove linhas sem preco"),
        ("colunas extra",  "contraparte, pac, est1-5 = '-'",                      "Campos de estrategia inicializados"),
        ("fillna IAM",     "codigo_IAM_ativo nulo &larr; Codigo",                 "Fallback para codigo original"),
    ]
    rows = "".join(
        '<div class="clear-row">'
        '<span class="clear-aba" style="color:#9aabdc;min-width:140px;font-size:.67rem">' + p[0] + '</span>'
        '<span class="clear-cols" style="font-size:.63rem;color:#aaa">' + p[1] + '</span>'
        '<span class="clear-count" style="min-width:220px;font-size:.62rem;color:#666">' + p[2] + '</span>'
        '</div>'
        for p in passos
    )
    tag_ativos = (
        '<div class="tag t-dur clickable" onclick="showSQL(\'sac_dic_ativos\')" style="margin-top:4px">'
        '<strong>VIEW_FUNDOS_CADASTRO_ATIVOS_LAST_VALUES</strong>'
        '<span class="src">campo = \'codigo_cota_SAC\'</span>'
        '<span class="dest">eval(valor_str) &rarr; explode &rarr; df_dic_ativos</span>'
        '<span class="lbl">Merge: dfCota &rarr; codigo_IAM_ativo</span>'
        '</div>'
    )
    inner = (
        '<div class="bloco-header">Tratamento do DataFrame &mdash; '
        + str(len(passos)) + ' etapas</div>'
        '<div class="bloco-sub">dfCota: merge D-1 + D-2 &middot; dicion&aacute;rio de ativos SAC &rarr; IAM</div>'
        + rows
        + tag_ativos
    )
    return node(inner, "c-db-treat", 800)


def bloco_saccota_fidc():
    tag_check = (
        '<div class="tag t-fus clickable" onclick="showSQL(\'sac_fidc_cadastro\')" style="margin-top:4px">'
        '<strong>FUNDOS_CADASTRO_ATIVOS</strong>'
        '<span class="src">Verifica antes de inserir &mdash; evita duplicatas</span>'
        '<span class="dest">WHERE codigo_IAM_ativo IN {tup_ativos}</span>'
        '<span class="lbl">df_ativo = df_ativo[isnull(date_change_origem)] &mdash; apenas registros novos</span>'
        '</div>'
    )
    inner = (
        '<div class="bloco-header">Cadastrar FIDC &mdash; <code>cadastrar_fidc(dfCota)</code></div>'
        '<div class="bloco-sub">'
        'Filtro: <code style="background:#1a0a2e;padding:1px 5px;border-radius:3px">regex ^5[A-Z]</code>'
        ' sobre codigo_IAM_ativo &nbsp;&middot;&nbsp; Destino: <strong>FUNDOS_CADASTRO_ATIVOS</strong>'
        '</div>'
        '<div class="bloco-code">'
        'df_fundos_credito = dfCota[match(<span class="str">r"^5[A-Z]"</span>)]<br>'
        '<span class="kw">if</span> len > 0:<br>'
        '&nbsp;&nbsp;campos str: ativo, divida, fator_risco, moeda*, tipo, pais, emissor, ticker, IAM, codigo_cota_SAC<br>'
        '&nbsp;&nbsp;campos num: multiplicador_contrato=1, risco_cambial=1<br>'
        '&nbsp;&nbsp;pd.melt &rarr; campo/valor_str + campo/valor_num'
        '</div>'
        + tag_check +
        '<div class="bloco-detail">'
        '<span class="badge badge-purple">tipo</span> Fixed Income &nbsp;'
        '<span class="badge badge-purple">fator_risco</span> Credito &nbsp;'
        '<span class="badge badge-purple">INSERT</span> db_insert_frame(\'FUNDOS_CADASTRO_ATIVOS\', df_ativo)'
        '</div>'
    )
    return node(inner, "c-db-fidc", 760)


def bloco_saccota_meta():
    inner = (
        '<div class="bloco-header">Metadata &amp; Auditoria</div>'
        '<div class="bloco-sub">Log de rastreabilidade para todas as linhas</div>'
        '<div class="bloco-code">'
        'dfCota[<span class="str">\'log_script_from\'</span>] = os.path.basename(__file__) &nbsp;<span class="code-comment"># SAC_Cota.py</span><br>'
        'dfCota = <span class="kw">log_last_run</span>(dfCota) &nbsp;<span class="code-comment"># datetime + racf do usuario</span><br>'
        'dfCota[<span class="str">\'tipo_ativo\'</span>] = <span class="str">\'SAC_COTA\'</span>'
        '</div>'
        '<div class="bloco-detail">'
        '<span class="badge badge-blue">CLog</span> log_last_run: log_last_processamento + log_last_user'
        '</div>'
    )
    return node(inner, "c-db-meta", 580)


def bloco_saccota_split():
    tag_estrategia = (
        '<div class="tag t-dur clickable" onclick="showSQL(\'sac_estrategia\')">'
        '<strong>FUNDOS_CADASTRO_FUNDOS</strong>'
        '<span class="src">campo = \'controle_por_estrategia\' &middot; valor_num = 1</span>'
        '<span class="dest">'
        'dfSistema = isin(dfEstrategia) &rarr; FUNDOS_POSICAO_SISTEMAS<br>'
        'df &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;= ~isin(dfEstrategia) &rarr; FUNDOS_POSICAO'
        '</span>'
        '<span class="lbl">clique para ver SQL</span>'
        '</div>'
    )
    return (
        '<div class="group" style="width:660px;border-color:#9a6a1a">'
        '<div class="group-title" style="color:#daa84a">'
        'Separar por Controle de Estrat&eacute;gia &mdash; clique para ver SQL'
        '</div>'
        '<div class="group-grid cols1">' + tag_estrategia + '</div>'
        '</div>'
    )


def bloco_saccota_insert():
    branch_sistema = (
        '<div class="tag t-fus clickable" onclick="showSQL(\'sac_delete_posicao_sistemas\')">'
        '<strong>dfSistema &rarr; FUNDOS_POSICAO_SISTEMAS</strong>'
        '<span class="src">Fundos com controle_por_estrategia = 1</span>'
        '<span class="dest">groupby lista_campos &rarr; agg(sum qt, sum abertura, mean preco)</span>'
        '<span class="lbl">clique: ver DELETE SQL &middot; retorna_df? return : DELETE + INSERT</span>'
        '</div>'
    )
    branch_posicao = (
        '<div class="tag t-fdo clickable" onclick="showSQL(\'sac_delete_posicao\')">'
        '<strong>df &rarr; FUNDOS_POSICAO</strong>'
        '<span class="src">Fundos sem controle_por_estrategia</span>'
        '<span class="dest">groupby lista_campos &rarr; agg(sum qt, sum abertura, mean preco)</span>'
        '<span class="lbl">clique: ver DELETE SQL &middot; retorna_df? return : DELETE + INSERT</span>'
        '</div>'
    )
    colunas_groupby = (
        '<div class="bloco-detail" style="padding:6px 12px;font-size:.62rem">'
        '<strong>lista_campos groupby:</strong> date &middot; codigo_IAM_fundo &middot; codigo_IAM_ativo &middot; '
        'contraparte &middot; pac &middot; est1&ndash;5 &middot; log_last_processamento &middot; log_last_user &middot; '
        'log_script_from &middot; tipo_ativo'
        '</div>'
    )
    return (
        '<div class="group" style="width:860px;border-color:#1a7a3a">'
        '<div class="group-title" style="color:#5acc8a">'
        'DELETE + INSERT &mdash; clique na tabela destino para ver SQL'
        '</div>'
        '<div class="group-grid cols2">' + branch_sistema + branch_posicao + '</div>'
        + colunas_groupby +
        '</div>'
    )


def build_base_dados_page():
    subbox_contingencia = (
        '<div class="macro-subbox macro-subbox-db clickable" onclick="goDetailContingencia()" title="Ver Conting&ecirc;ncia">'
        '<div class="macro-subbox-name">Conting&ecirc;ncia</div>'
        '<div class="macro-subbox-hint">SAC_Cota.py &middot; Clique para abrir</div>'
        '</div>'
    )
    box_contingencia = (
        '<div class="macro-box macro-box-db">'
        '<div class="macro-box-badge">Scripts</div>'
        '<div class="macro-icon" style="font-size:1.6rem">DB</div>'
        '<div class="macro-sub">Conting&ecirc;ncia</div>'
        '<div class="macro-subboxes">'
        + subbox_contingencia +
        '</div>'
        '</div>'
    )
    return (
        '<div id="pg14" class="pg pg-macro">'
        '<button class="back-btn" style="color:#7fb3d3;border-color:#2e6da4" onclick="goIdx()">&#x2190; Voltar</button>'
        '<div class="macro-center">'
        '<div class="macro-workbook">Base de Dados &mdash; dbsx337</div>'
        '<div class="macro-boxes">'
        + box_contingencia +
        '</div>'
        '</div>'
        '</div>'
    )


def build_contingencia_page():
    sections = [
        '<div class="node oval c-start">INICIO</div>',
        arrow(),
        status_wrap(bloco_saccota_init(),       "db-init"),
        arrow(),
        status_wrap(bloco_saccota_datas(),      "db-datas"),
        arrow(),
        status_wrap(bloco_saccota_fundos(),     "db-fundos"),
        arrow(),
        status_wrap(bloco_saccota_query(),      "db-query"),
        arrow(),
        status_wrap(bloco_saccota_tratamento(), "db-treat"),
        arrow(),
        status_wrap(bloco_saccota_fidc(),       "db-fidc"),
        arrow(),
        status_wrap(bloco_saccota_meta(),       "db-meta"),
        arrow(),
        status_wrap(bloco_saccota_split(),      "db-split"),
        arrow(),
        status_wrap(bloco_saccota_insert(),     "db-insert"),
        arrow(),
        '<div class="node oval c-end">FIM</div>',
    ]
    flow = "\n".join(sections)
    return (
        '<div id="pg15" class="pg pg-detail">'
        '<button class="back-btn" style="color:#7fb3d3;border-color:#2e6da4" onclick="goIdx()">&#x2190; Voltar</button>'
        "<h1>Fluxograma &mdash; SAC_Cota.py</h1>\n"
        '<div class="subtitle">Base de Dados &middot; Conting&ecirc;ncia &middot; SAC_Cota.py &middot; Lake + OC3Light</div>\n'
        '<div class="page-box" style="border-color:#2e6da4">\n'
        '<div class="page-box-title" style="color:#2e6da4">Conting&ecirc;ncia &mdash; SAC_Cota_posicao()</div>\n'
        '<div class="page-layout">\n'
        '  <div class="flow-col">\n'
        "    " + bloco_legend() + "\n"
        '    <div class="flow">\n'
        + flow + "\n"
        "    </div>\n"
        "    " + bloco_legend() + "\n"
        "  </div>\n"
        "</div>\n"
        "</div>\n"
        "</div>"
    )


def bloco_bat_init():
    inner = (
        '<div class="bloco-header">Inicializa&ccedil;&atilde;o &mdash; Batimento Di&aacute;rio</div>'
        '<div class="bloco-sub">Script: <strong>FLBLIPO_Batimento_PnL_VCRA_detalhado.py</strong>'
        ' &nbsp;&middot;&nbsp; Banco: <strong>Lake (Conn) + OC3</strong></div>'
        '<div class="bloco-code">'
        'date_ref = <span class="kw">QsDate</span>(today).add_business_days(<span class="str">-1</span>)<br>'
        'mesa_gestao = <span class="str">"indexados"</span><br>'
        'min_bps = <span class="str">0.5</span> &nbsp;<span class="code-comment"># limiar de diferença</span><br>'
        'LIMIAR_PRECO_PERC = <span class="str">0.001</span> &nbsp;<span class="code-comment"># 0.1%</span><br>'
        'LIMIAR_PNL_ABS = <span class="str">5.0</span> &nbsp;<span class="code-comment"># R$5</span>'
        "</div>"
        '<div class="bloco-detail">'
        '<span class="badge badge-purple">joblib</span> Parallel(n_jobs=-1) nas classes &nbsp;'
        '<span class="badge badge-blue">QsDate</span> Calend&aacute;rio Brasil'
        "</div>"
    )
    return node(inner, "c-bat-init", 560)


def bloco_bat_triagem():
    inner = (
        '<div class="bloco-header">Triagem Macro &mdash; Cotas vs Posi&ccedil;&atilde;o</div>'
        '<div class="bloco-sub">'
        '<code>get_fundos_com_diferenca(date_ref, mesa_gestao, min_bps)</code></div>'
        '<div class="bloco-code">'
        '<span class="code-comment">-- VW_FUNDOS_COTAS_PL vs VW_FUNDOS_POSICAO</span><br>'
        'Diferenca_Bps = fundo_pnl_bps &minus; pnl_total_bps<br>'
        'Diferenca_Fin = fundo_pnl &minus; pnl_total<br>'
        '<span class="kw">WHERE</span> ABS(Diferenca_Bps) &ge; min_bps<br>'
        '  <span class="kw">AND</span> mesa_gestao <span class="kw">LIKE</span> <span class="str">\'%indexados%\'</span>'
        "</div>"
        '<div class="bloco-detail">'
        '<span class="badge badge-purple">Filtro</span> Exclui prefixo CR_ &nbsp;'
        '<span class="badge badge-blue">Sa&iacute;da</span> lista_fundos com diferen&ccedil;a relevante'
        "</div>"
    )
    return (
        '<div class="group" style="width:660px;border-color:#7b1fa2">'
        '<div class="group-title" style="color:#ce93d8">'
        'Triagem Macro &mdash; clique para ver SQL'
        ' &nbsp;<em style="opacity:.5;font-size:.6rem;cursor:pointer" onclick="showSQL(\'triagem_macro\')">ver SQL</em>'
        '</div>'
        + inner +
        '</div>'
    )


def bloco_bat_parallel():
    tags = "".join(
        '<div class="tag ' + CAT_CSS.get(c[3], "t-pos") + '">'
        '<strong>' + c[0] + '()</strong>'
        '<span class="src">VCRA: ' + c[1] + '</span>'
        '<span class="dest">Lake: ' + c[2] + '</span>'
        '<span class="lbl">' + c[4] + '</span>'
        '</div>'
        for c in BATIMENTO_CLASSES
    )
    return (
        '<div class="group" style="width:860px;border-color:#6a1b9a">'
        '<div class="group-title" style="color:#e1bee7">'
        'Batimentos por Classe &mdash; Parallel(n_jobs=-1) via joblib'
        ' &nbsp;&middot;&nbsp; ' + str(len(BATIMENTO_CLASSES)) + ' fun&ccedil;&otilde;es'
        '</div>'
        '<div class="group-grid cols3">' + tags + '</div>'
        '</div>'
    )


def bloco_bat_enrich():
    inner = (
        '<div class="bloco-header">Enriquecimento do DataFrame</div>'
        '<div class="bloco-sub">Ap&oacute;s concat de todas as classes</div>'
        '<div class="bloco-code">'
        '<span class="code-comment"># bps por ativo</span><br>'
        'dif_total_bps = dif_pnl_total / last_patrimonio &times; 10000<br>'
        '<span class="code-comment"># classifica causa e script de corre&ccedil;&atilde;o</span><br>'
        '<span class="kw">_adiciona_diagnostico</span>(df_final)<br>'
        '<span class="code-comment"># pre&ccedil;o de refer&ecirc;ncia extra</span><br>'
        '<span class="kw">get_precos_dados_ativos</span>(date_ref, lista_ativos)'
        "</div>"
        '<div class="bloco-detail">'
        '<span class="badge badge-blue">get_pnl_total</span> Patrim&ocirc;nio para bps &nbsp;'
        '<span class="badge badge-teal">FUNDOS_DADOS_ATIVOS</span> Preco_DadosAtivos'
        "</div>"
    )
    return node(inner, "c-bat-enrich", 560)


def bloco_bat_causas():
    rows = "".join(
        '<div class="clear-row">'
        '<span class="clear-aba" style="color:#ce93d8;min-width:220px;font-size:.68rem">' + c[0] + '</span>'
        '<span class="clear-cols" style="font-size:.64rem">' + c[1] + '</span>'
        '<span class="clear-count" style="min-width:240px;font-size:.62rem;color:#888">' + c[2] + '</span>'
        '</div>'
        for c in BATIMENTO_CAUSAS
    )
    inner = (
        '<div class="bloco-header">Classifica&ccedil;&atilde;o de Causa por Ativo</div>'
        '<div class="bloco-sub"><code>_classifica_causa(row)</code> &mdash; '
        + str(len(BATIMENTO_CAUSAS)) + ' causas mapeadas</div>'
        + rows
    )
    return node(inner, "c-bat-triage", 760)


def bloco_bat_complementar():
    items = [
        ("get_diff_return()",               "VW_FUNDOS_RENTABILIDADE",    "pos",  "SAC vs Lake &mdash; diff de retorno macro"),
        ("batimento_pnl_aluguel()",         "VCRABTALUGUEL / Lake",       "fdo",  "Aluguel de a&ccedil;&otilde;es (BTC)"),
        ("aluguel_marreta()",               "df_aluguel",                 "fus",  "Marreta de ajuste sobre aluguel"),
        ("get_diagnostico_proventos()",     "FUNDOS_DIVIDENDOS_FUNDOS",   "prov", "Dividendos / proventos do per&iacute;odo"),
        ("_compara_proventos_com_diferenca()", "df_proventos + df_triagem","prov", "Provento explica &ge;80% da diferen&ccedil;a?"),
    ]
    tags = "".join(
        '<div class="tag ' + CAT_CSS.get(i[2], "t-pos") + '">'
        '<strong>' + i[0] + '</strong>'
        '<span class="src">' + i[1] + '</span>'
        '<span class="lbl">' + i[3] + '</span>'
        '</div>'
        for i in items
    )
    return group(
        "An&aacute;lises Complementares &mdash; Macro / Aluguel / Proventos",
        tags, cols=2, width=760, border_color="#ad1457",
    )


def bloco_bat_dados():
    items = [
        ("get_detalhamento_pnl()",          "VW_FUNDOS_COTAS_PL + VW_FUNDOS_POSICAO", "fdo", "PnL cotas + posi&ccedil;&atilde;o por classe + top ativos"),
        ("get_posicao_fundo()",             "VW_FUNDOS_POSICAO",                      "pos", "Posi&ccedil;&atilde;o detalhada: qtd, pre&ccedil;o, financeiro, % PL"),
        ("get_comparativo_gap()",           "VW_FUNDOS_COTAS_PL + VW_FUNDOS_POSICAO", "pos", "Gap macro D e D-1 + posi&ccedil;&atilde;o D-1"),
        ("get_dados_analises_sequenciais()", "VCRAPRF, VCRAOPRV, FUNDOS_EVENTOS, FX...", "dur", "RF, Trades, Eventos, Caixa, Benchmark, FX"),
        ("get_dados_oc3()",                 "OC3 (ADO Recordset)",                    "fus", "Patrim&ocirc;nio, RF, RV, Futuros, Swap, Caixa, Cotas ext."),
    ]
    tags = "".join(
        '<div class="tag ' + CAT_CSS.get(i[2], "t-pos") + ' clickable" '
        + ('onclick="showSQL(\'' + ('detalhamento_pnl_classe' if 'detalhamento' in i[0] else
                                    'posicao_detalhada'       if 'posicao'       in i[0] else
                                    'gap_macro_d_d1'          if 'gap'           in i[0] else '') + '\')" '
           if any(k in i[0] for k in ['detalhamento', 'posicao', 'gap']) else '')
        + '>'
        '<strong>' + i[0] + '</strong>'
        '<span class="src">' + i[1] + '</span>'
        '<span class="lbl">' + i[3] + ('&nbsp;<em style="opacity:.5;font-size:.6rem">ver SQL</em>' if any(k in i[0] for k in ['detalhamento', 'posicao', 'gap']) else '') + '</span>'
        '</div>'
        for i in items
    )
    return group(
        "Coleta de Dados Adicionais &mdash; D e D-1",
        tags, cols=2, width=860, border_color="#1565c0",
    )


def bloco_bat_analises():
    rows = "".join(
        '<div class="tag ' + CAT_CSS.get(a[3], "t-pos") + '" style="margin-bottom:3px">'
        '<strong style="font-size:.72rem">' + a[0] + '</strong>'
        '<span class="src" style="font-size:.62rem">' + a[1] + '</span>'
        '<span class="lbl">' + a[2] + '</span>'
        '</div>'
        for a in BATIMENTO_ANALISES
    )
    return (
        '<div class="group" style="width:860px;border-color:#283593">'
        '<div class="group-title" style="color:#90caf9">10 An&aacute;lises Sequenciais &mdash; '
        '<code style="font-size:.62rem">_escreve_aba_analises_seq()</code></div>'
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px">' + rows + '</div>'
        '</div>'
    )


def bloco_bat_excel():
    rows = "".join(
        '<div class="clear-row">'
        '<span class="clear-aba" style="color:#f0c97a;min-width:160px;font-size:.68rem">'
        + a[0] + '</span>'
        '<span class="clear-cols ' + CAT_CSS.get(a[2], "t-pos") + '" style="font-size:.62rem;background:none;border:none;padding:0">'
        + a[1] + '</span>'
        '</div>'
        for a in BATIMENTO_ABAS
    )
    n = len(BATIMENTO_ABAS)
    inner = (
        '<div class="bloco-header">Sa&iacute;da Excel por Fundo &mdash; '
        + str(n) + ' abas</div>'
        '<div class="bloco-sub">'
        '<code>../output/batimento/{mesa}/{date_ref}/Detalhado_{fundo}_{date_ref}.xlsx</code>'
        '</div>'
        + rows
    )
    return node(inner, "c-bat-out", 680)


def build_batimento_page():
    sections = [
        '<div class="node oval c-start">INICIO</div>',
        arrow(),
        status_wrap(bloco_bat_init(),        "bat-init"),
        arrow(),
        status_wrap(bloco_bat_triagem(),     "bat-triagem"),
        arrow(),
        status_wrap(bloco_bat_parallel(),    "bat-parallel"),
        arrow(),
        status_wrap(bloco_bat_enrich(),      "bat-enrich"),
        arrow(),
        status_wrap(bloco_bat_causas(),      "bat-causas"),
        arrow(),
        status_wrap(bloco_bat_complementar(), "bat-compl"),
        arrow(),
        status_wrap(bloco_bat_dados(),       "bat-dados"),
        arrow(),
        status_wrap(bloco_bat_analises(),    "bat-analises"),
        arrow(),
        status_wrap(bloco_bat_excel(),       "bat-excel"),
        arrow(),
        '<div class="node oval c-end">FIM</div>',
    ]
    flow = "\n".join(sections)
    return (
        '<div id="pg9" class="pg pg-detail">'
        '<button class="back-btn" style="color:#ce93d8;border-color:#4a148c" onclick="goIdx()">&#x2190; Voltar</button>'
        "<h1>Fluxograma &mdash; Batimento Di&aacute;rio PnL VCRA</h1>\n"
        '<div class="subtitle">Python &middot; FLBLIPO_Batimento_PnL_VCRA_detalhado.py &middot; Lake + OC3</div>\n'
        '<div class="page-box" style="border-color:#7b1fa2">\n'
        '<div class="page-box-title" style="color:#7b1fa2">Batimento Di&aacute;rio &mdash; VCRA vs Lake</div>\n'
        '<div class="page-layout">\n'
        '  <div class="flow-col">\n'
        "    " + bloco_legend() + "\n"
        '    <div class="flow">\n'
        + flow + "\n"
        "    </div>\n"
        "    " + bloco_legend() + "\n"
        "  </div>\n"
        "</div>\n"
        "</div>\n"
        "</div>"
    )


def build_idx_page():
    subbox_exposicao = (
        '<div class="macro-subbox macro-subbox-vba clickable" onclick="goMacro()" title="Ver Exposi&ccedil;&atilde;o Beta">'
        '<div class="macro-subbox-name">Exposi&ccedil;&atilde;o Beta</div>'
        '<div class="macro-subbox-hint">Clique para abrir</div>'
        '</div>'
    )
    subbox_batimento = (
        '<div class="macro-subbox macro-subbox-bat clickable" onclick="goDetailBatimento()" title="Ver Batimento Di&aacute;rio">'
        '<div class="macro-subbox-name">Batimento Di&aacute;rio</div>'
        '<div class="macro-subbox-hint">Clique para abrir</div>'
        '</div>'
    )
    subbox_preco_justo = (
        '<div class="macro-subbox macro-subbox-pj clickable" onclick="goDetailPrecoJusto()" title="Ver Pre&ccedil;o Justo ETF">'
        '<div class="macro-subbox-name">Pre&ccedil;o Justo ETF</div>'
        '<div class="macro-subbox-hint">Clique para abrir</div>'
        '</div>'
    )
    subbox_oc3 = (
        '<div class="macro-subbox macro-subbox-oc3 clickable" onclick="goDetailOC3()" title="Ver Batimento dll - OC3">'
        '<div class="macro-subbox-name">Batimento dll &mdash; OC3</div>'
        '<div class="macro-subbox-hint">Clique para abrir</div>'
        '</div>'
    )
    box_idx = (
        '<div class="macro-box macro-box-idx">'
        '<div class="macro-box-badge">Indexados</div>'
        '<div class="macro-icon">IDX</div>'
        '<div class="macro-sub">Indexados</div>'
        '<div class="macro-subboxes">'
        + subbox_exposicao + subbox_batimento + subbox_preco_justo + subbox_oc3 +
        '</div>'
        '</div>'
    )
    subbox_bat_offshore = (
        '<div class="macro-subbox macro-subbox-off clickable" onclick="goDetailOffshore()" title="Ver Batimento Offshore">'
        '<div class="macro-subbox-name">Batimento Offshore</div>'
        '<div class="macro-subbox-hint">Clique para abrir</div>'
        '</div>'
    )
    subbox_bat_diario_rf = (
        '<div class="macro-subbox">'
        '<div class="macro-subbox-name" style="color:#555">Batimento Di&aacute;rio</div>'
        '<div class="macro-subbox-hint">em branco</div>'
        '</div>'
    )
    subbox_dash_mesa_rf = (
        '<div class="macro-subbox macro-subbox-rf clickable" onclick="goDetailDashMesaRF()" title="Ver Dash Mesa RF">'
        '<div class="macro-subbox-name">Dash Mesa RF</div>'
        '<div class="macro-subbox-hint">Clique para abrir</div>'
        '</div>'
    )
    box_rf = (
        '<div class="macro-box macro-box-rf">'
        '<div class="macro-box-badge">Renda Fixa</div>'
        # '<div class="macro-icon" style="font-size:2rem">RF</div>'
        '<div class="macro-icon">SRF</div>'
        '<div class="macro-sub">Renda Fixa</div>'
        '<div class="macro-subboxes">'
        + subbox_bat_offshore + subbox_bat_diario_rf + subbox_dash_mesa_rf +
        '</div>'
        '</div>'
    )
    subbox_contingencia_db = (
        '<div class="macro-subbox macro-subbox-db clickable" onclick="goDetailContingencia()" title="Ver Conting&ecirc;ncia">'
        '<div class="macro-subbox-name">Conting&ecirc;ncia</div>'
        '<div class="macro-subbox-hint">SAC_Cota.py &middot; Clique para abrir</div>'
        '</div>'
    )
    box_db = (
        '<div class="macro-box macro-box-db">'
        '<div class="macro-box-badge">Dados</div>'
        '<div class="macro-icon">DB</div>'
        '<div class="macro-sub">Base de Dados</div>'
        '<div class="macro-subboxes">'
        + subbox_contingencia_db +
        '</div>'
        '</div>'
    )
    subbox_erd = (
        '<div class="macro-subbox macro-subbox-tech clickable" onclick="goDetailERD()" title="Ver Visao Tecnica ER/DFD">'
        '<div class="macro-subbox-name">ER / DFD &mdash; Origem &rarr; Destino</div>'
        '<div class="macro-subbox-hint">Clique para abrir</div>'
        '</div>'
    )
    box_tech = (
        '<div class="macro-box macro-box-tech">'
        '<div class="macro-box-badge">T&eacute;cnico</div>'
        '<div class="macro-icon">ERD</div>'
        '<div class="macro-sub">Visao Tecnica</div>'
        '<div class="macro-subboxes">'
        + subbox_erd +
        '</div>'
        '</div>'
    )
    return (
        '<div id="pg0" class="pg pg-macro active">'
        '<div class="macro-center">'
        '<div class="macro-workbook">Analytics Projects &mdash; Fabricio Levy</div>'
        '<div class="macro-boxes">'
        + box_idx + box_rf + box_db + box_tech +
        '</div>'
        '</div>'
        '</div>'
    )


# ── Visao Tecnica — ER / DFD (origem -> destino, setas rotuladas, cardinalidade) ──

def _erd_cardinalidade(sql_text):
    """Infere a cardinalidade origem->destino a partir do texto da query."""
    if not sql_text:
        return ("1:1", "erd-card-11")
    up = sql_text.upper()
    if "TOP 1" in up:
        return ("1:1", "erd-card-11")
    if "GROUP BY" in up or "SUM(" in up:
        return ("N:1", "erd-card-n1")
    return ("1:N", "erd-card-1n")


def _erd_row(origem, destino, label, sql_key, sql_map, cat, descricao):
    cor = CAT_COLOR.get(cat, "#2471a3")
    sql_text = sql_map.get(sql_key)
    has_sql = sql_text is not None
    card_label, card_css = _erd_cardinalidade(sql_text)
    click_attr = (' onclick="showSQL(\'' + sql_key + '\')"') if has_sql else ""
    label_css  = "erd-arrow-label" + (" clickable" if has_sql else "")
    hint       = '<div class="erd-arrow-hint">ver SQL</div>' if has_sql else ""
    return (
        '<div class="erd-row">'
        '<div class="erd-node erd-node-origem" style="border-left-color:' + cor + '">'
        '<div class="erd-node-tag" style="color:' + cor + '">Origem</div>'
        '<div class="erd-node-name">' + origem + "</div>"
        "</div>"
        '<div class="erd-arrow-wrap">'
        '<div class="' + label_css + '"' + click_attr + ">" + label + "</div>"
        '<div class="erd-arrow-line"></div>'
        + hint +
        '<div class="erd-card ' + card_css + '">' + card_label + "</div>"
        "</div>"
        '<div class="erd-node erd-node-destino">'
        '<div class="erd-node-tag">Destino</div>'
        '<div class="erd-node-name">' + destino + "</div>"
        '<div class="erd-node-sub">' + descricao + "</div>"
        "</div>"
        "</div>"
    )


def _erd_group(title, rows_html, count):
    return (
        '<div class="erd-group">'
        '<div class="erd-group-title">' + title
        + ' <span class="erd-group-count">(' + str(count) + " fluxos)</span></div>"
        '<div class="erd-rows">' + rows_html + "</div>"
        "</div>"
    )


def build_erd_page():
    vba_rows = "".join(
        _erd_row(q[1], q[3] + " &middot; " + q[2], q[0], q[0], VBA_SQL, q[4], q[5])
        for q in SQL_QUERIES
    )
    py_rows = "".join(
        _erd_row(q[1], q[2], q[0], q[0], PY_SQL, q[3], q[4])
        for q in PY_QUERIES
    )
    fut_rows = "".join(
        _erd_row(q[1], q[2], q[0], q[0], FUT_SQL, q[3], q[4])
        for q in FUT_QUERIES
    )
    legend_note = (
        '<div class="erd-legend-note">Cada linha representa um fluxo de dados: a <strong>origem</strong> '
        "(tabela / view / API no banco) alimenta &mdash; atrav&eacute;s de uma query ou fun&ccedil;&atilde;o "
        "(seta rotulada; clic&aacute;vel quando h&aacute; SQL associado) &mdash; um <strong>destino</strong> "
        "(c&eacute;lula/aba da planilha ou retorno em Python). A pastilha sobre a seta indica a cardinalidade "
        'origem&nbsp;&rarr;&nbsp;destino: <span class="erd-card erd-card-11">1:1</span> um registro por chave '
        '(ex.: TOP 1 cota&ccedil;&atilde;o), <span class="erd-card erd-card-n1">N:1</span> v&aacute;rios registros '
        'agregados em um valor (SUM / GROUP BY), <span class="erd-card erd-card-1n">1:N</span> um recorte fonte '
        "gerando v&aacute;rias linhas de destino.</div>"
    )
    body = (
        legend_note
        + _erd_group("VBA &mdash; Sub Load_DADOS337()", vba_rows, len(SQL_QUERIES))
        + _erd_group("Python &mdash; exposicao.py", py_rows, len(PY_QUERIES))
        + _erd_group("Python &mdash; futuros.py", fut_rows, len(FUT_QUERIES))
    )
    return (
        '<div id="pg16" class="pg pg-detail">'
        '<button class="back-btn" style="color:#a29bfe;border-color:#4834b0" onclick="goIdx()">&#x2190; Voltar</button>'
        "<h1>Visao T&eacute;cnica &mdash; ER / DFD</h1>\n"
        '<div class="subtitle">Origem &rarr; Destino &middot; setas rotuladas &middot; cardinalidade</div>\n'
        '<div class="page-box" style="border-color:#6c5ce7">\n'
        '<div class="page-box-title" style="color:#6c5ce7">Mapa de Fluxo de Dados</div>\n'
        + body +
        "</div>\n"
        "</div>"
    )


def build_html():
    sections = [
        '<div class="node oval c-start">INICIO</div>',
        arrow(),
        status_wrap(bloco_init(),             "vba-init"),
        arrow(),
        status_wrap(bloco_string_builders(),  "vba-strings"),
        arrow(),
        status_wrap(bloco_queries(),          "vba-queries"),
        arrow(),
        status_wrap(bloco_clear(),            "vba-clear"),
        arrow(),
        status_wrap(bloco_connect(),          "vba-connect"),
        arrow(),
        status_wrap(bloco_prv(),              "vba-prv"),
        arrow(),
        status_wrap(bloco_exec_queries(),     "vba-exec"),
        arrow(),
        status_wrap(bloco_formulas(),         "vba-formulas"),
        arrow(),
        status_wrap(bloco_autofilter(),       "vba-filter"),
        arrow(),
        status_wrap(bloco_restore(),          "vba-restore"),
        arrow(),
        '<div class="node oval c-end">FIM</div>',
    ]
    flow = "\n".join(sections)

    detail_page = (
        '<div id="pg2" class="pg pg-detail">'
        '<button class="back-btn" onclick="goMacro()">&#x2190; Voltar</button>'
        "<h1>Fluxograma &mdash; Sub Load_DADOS337()</h1>\n"
        '<div class="subtitle">VBA &middot; Exposicao Beta &middot; dbsx337</div>\n'
        '<div class="page-box">\n'
        # '<div class="page-box-title">&#x1F4CA; C&aacute;lculo VBA &mdash; Sub Load_DADOS337</div>\n'
        '<div class="page-box-title">C&aacute;lculo VBA &mdash; Sub Load_DADOS337</div>\n'
        '<div class="page-layout">\n'
        '  <div class="flow-col">\n'
        "    " + bloco_legend() + "\n"
        '    <div class="flow">\n'
        + flow + "\n"
        "    </div>\n"
        "    " + bloco_legend() + "\n"
        "  </div>\n"
        "</div>\n"
        "</div>\n"
        "</div>"
    )

    py_sections = [
        '<div class="node oval c-start">INICIO</div>',
        arrow(),
        status_wrap(bloco_py_init(),    "py-init"),
        arrow(),
        status_wrap(bloco_py_excel(),   "py-excel"),
        arrow(),
        status_wrap(bloco_py_queries(), "py-queries"),
        arrow(),
        status_wrap(bloco_py_montar(),  "py-montar"),
        arrow(),
        status_wrap(bloco_py_export(),  "py-export"),
        arrow(),
        '<div class="node oval c-end">FIM</div>',
    ]
    py_flow = "\n".join(py_sections)

    py_page = (
        '<div id="pg3" class="pg pg-detail">'
        '<button class="back-btn" onclick="goMacro()">&#x2190; Voltar</button>'
        "<h1>Fluxograma &mdash; C&aacute;lculo Python</h1>\n"
        '<div class="subtitle">exposicao.py &middot; Python 3.x &middot; dbsx337</div>\n'
        '<div class="page-box" style="border-color:#27ae60">\n'
        # '<div class="page-box-title" style="color:#27ae60">&#x1F40D; C&aacute;lculo Python &mdash; exposicao.py</div>\n'
        '<div class="page-box-title" style="color:#27ae60">C&aacute;lculo Python &mdash; exposicao.py</div>\n'
        '<div class="page-layout">\n'
        '  <div class="flow-col">\n'
        "    " + bloco_legend() + "\n"
        '    <div class="flow">\n'
        + py_flow + "\n"
        "    </div>\n"
        "    " + bloco_legend() + "\n"
        "  </div>\n"
        "</div>\n"
        "</div>\n"
        "</div>"
    )

    fe_page = (
        '<div id="pg4" class="pg pg-detail">'
        '<button class="back-btn" onclick="goMacro()">&#x2190; Voltar</button>'
        "<h1>Fluxograma &mdash; Front End</h1>\n"
        '<div class="subtitle">Interface &middot; Exposicao Beta</div>\n'
        '<div class="page-box" style="border-color:#e67e22">\n'
        '<div class="page-box-title" style="color:#e67e22">Front End</div>\n'
        '<div style="display:flex;align-items:center;justify-content:center;min-height:320px;color:#555;font-size:.9rem;">Fluxograma em desenvolvimento...</div>\n'
        "</div>\n"
        "</div>"
    )

    rf_page = (
        '<div id="pg8" class="pg pg-detail">'
        '<button class="back-btn" style="color:#f0c97a;border-color:#7d5200" onclick="goIdx()">&#x2190; Voltar</button>'
        "<h1>Fluxograma &mdash; Renda Fixa</h1>\n"
        '<div class="subtitle">SRF &middot; Renda Fixa</div>\n'
        '<div class="page-box" style="border-color:#c9850a">\n'
        '<div class="page-box-title" style="color:#c9850a">Renda Fixa</div>\n'
        '<div style="display:flex;align-items:center;justify-content:center;min-height:320px;color:#555;font-size:.9rem;">Fluxograma em desenvolvimento...</div>\n'
        "</div>\n"
        "</div>"
    )


    graficos_page = (
        '<div id="pg7" class="pg pg-detail">'
        '<button class="back-btn" onclick="goMacro()">&#x2190; Voltar</button>'
        "<h1>Fluxograma &mdash; An&aacute;lise Gr&aacute;fica &mdash; Fundos</h1>\n"
        '<div class="subtitle">Python &middot; Visualiza&ccedil;&otilde;es por Fundo</div>\n'
        '<div class="page-box" style="border-color:#27ae60">\n'
        '<div class="page-box-title" style="color:#27ae60">An&aacute;lise Gr&aacute;fica &mdash; Fundos</div>\n'
        '<div style="display:flex;align-items:center;justify-content:center;min-height:320px;color:#555;font-size:.9rem;">Fluxograma em desenvolvimento...</div>\n'
        "</div>\n"
        "</div>"
    )

    alerta_sections = [
        '<div class="node oval c-start">INICIO</div>',
        arrow(),
        status_wrap(bloco_alerta_init(),       "al-init"),
        arrow(),
        status_wrap(bloco_alerta_autofilter(), "al-filter"),
        arrow(),
        status_wrap(bloco_alerta_reset(),      "al-reset"),
        arrow(),
        status_wrap(bloco_alerta_loop(),       "al-loop"),
        arrow(),
        status_wrap(bloco_alerta_calc(),       "al-calc"),
        arrow(),
        '<div class="node oval c-end">FIM</div>',
    ]
    alerta_flow = "\n".join(alerta_sections)

    alerta_page = (
        '<div id="pg5" class="pg pg-detail">'
        '<button class="back-btn" style="color:#f1948a;border-color:#922b21" onclick="goMacro()">&#x2190; Voltar</button>'
        "<h1>Fluxograma &mdash; Sub Alerta()</h1>\n"
        '<div class="subtitle">VBA &middot; Exposicao Beta V20.xlsm &middot; Planilha6 (Design) &rarr; Alerta</div>\n'
        '<div class="page-box" style="border-color:#c0392b">\n'
        # '<div class="page-box-title" style="color:#c0392b">&#x1F6A8; Sub Alerta() &mdash; VBA</div>\n'
        '<div class="page-box-title" style="color:#c0392b">Sub Alerta() &mdash; VBA</div>\n'
        '<div class="page-layout">\n'
        '  <div class="flow-col">\n'
        "    " + bloco_legend() + "\n"
        '    <div class="flow">\n'
        + alerta_flow + "\n"
        "    </div>\n"
        "    " + bloco_legend() + "\n"
        "  </div>\n"
        "</div>\n"
        "</div>\n"
        "</div>"
    )

    fut_sections = [
        '<div class="node oval c-start">INICIO</div>',
        arrow(),
        status_wrap(bloco_fut_init(),    "fut-init"),
        arrow(),
        status_wrap(bloco_fut_queries(), "fut-queries"),
        arrow(),
        status_wrap(bloco_fut_preproc(), "fut-preproc"),
        arrow(),
        status_wrap(bloco_fut_loop(),    "fut-loop"),
        arrow(),
        status_wrap(bloco_fut_export(),  "fut-export"),
        arrow(),
        '<div class="node oval c-end">FIM</div>',
    ]
    fut_flow = "\n".join(fut_sections)

    fut_page = (
        '<div id="pg6" class="pg pg-detail">'
        '<button class="back-btn" style="color:#76d7c4;border-color:#0e6655" onclick="goMacro()">&#x2190; Voltar</button>'
        "<h1>Fluxograma &mdash; futuros.py</h1>\n"
        '<div class="subtitle">Python &middot; Rolagem de Futuros &middot; dbsx337 &rarr; ../output/rolagem/</div>\n'
        '<div class="page-box" style="border-color:#148f77">\n'
        # '<div class="page-box-title" style="color:#148f77">&#x1F4C8; futuros.py &mdash; Rolagem</div>\n'
        '<div class="page-box-title" style="color:#148f77">futuros.py &mdash; Rolagem</div>\n'
        '<div class="page-layout">\n'
        '  <div class="flow-col">\n'
        "    " + bloco_legend() + "\n"
        '    <div class="flow">\n'
        + fut_flow + "\n"
        "    </div>\n"
        "    " + bloco_legend() + "\n"
        "  </div>\n"
        "</div>\n"
        "</div>\n"
        "</div>"
    )

    vba_json  = json.dumps(TODO_ITEMS_VBA,      ensure_ascii=False)
    py_json   = json.dumps(TODO_ITEMS_PY,       ensure_ascii=False)
    fe_json   = json.dumps(TODO_ITEMS_FE,       ensure_ascii=False)
    al_json   = json.dumps(TODO_ITEMS_ALERTA,   ensure_ascii=False)
    fut_json  = json.dumps(TODO_ITEMS_FUT,      ensure_ascii=False)
    graf_json = json.dumps(TODO_ITEMS_GRAFICOS,  ensure_ascii=False)
    bat_json  = json.dumps(TODO_ITEMS_BATIMENTO, ensure_ascii=False)
    pj_json   = json.dumps(TODO_ITEMS_PJ,        ensure_ascii=False)
    off_json  = json.dumps(TODO_ITEMS_OFFSHORE,   ensure_ascii=False)
    oc3_json  = json.dumps(TODO_ITEMS_OC3,        ensure_ascii=False)
    todo_js   = (
        TODO_JS_TEMPLATE
        .replace("__VBA_DATA__",  vba_json)
        .replace("__PY_DATA__",   py_json)
        .replace("__FE_DATA__",   fe_json)
        .replace("__AL_DATA__",   al_json)
        .replace("__FUT_DATA__",  fut_json)
        .replace("__GRAF_DATA__", graf_json)
        .replace("__BAT_DATA__",  bat_json)
        .replace("__PJ_DATA__",   pj_json)
        .replace("__OFF_DATA__",  off_json)
        .replace("__OC3_DATA__",  oc3_json)
    )

    panel_vba  = build_todo_panel("vba",  "To Do &mdash; VBA",             "todo-panel-vba", "todo-vba-panel")
    panel_py   = build_todo_panel("py",   "To Do &mdash; Python",          "todo-panel-py",  "todo-py-panel")
    panel_fe   = build_todo_panel("fe",   "To Do &mdash; FE",              "todo-panel-fe",  "todo-fe-panel")
    panel_al   = build_todo_panel("al",   "To Do &mdash; Alerta",          "todo-panel-al",  "todo-al-panel")
    panel_fut  = build_todo_panel("fut",  "To Do &mdash; Futuros",         "todo-panel-fut", "todo-fut-panel")
    panel_graf = build_todo_panel("graf", "To Do &mdash; Graficos Fundos", "todo-panel-py",  "todo-graf-panel")
    panel_bat  = build_todo_panel("bat",  "To Do &mdash; Batimento Di&aacute;rio",   "todo-panel-bat", "todo-bat-panel")
    panel_pj   = build_todo_panel("pj",   "To Do &mdash; Pre&ccedil;o Justo ETF",   "todo-panel-pj",  "todo-pj-panel")
    panel_off  = build_todo_panel("off",  "To Do &mdash; Batimento Offshore",        "todo-panel-off", "todo-off-panel")
    panel_oc3  = build_todo_panel("oc3",  "To Do &mdash; Batimento dll &mdash; OC3", "todo-panel-oc3", "todo-oc3-panel")
    todo_sidebar = '<div class="todo-sidebar">' + panel_vba + panel_py + panel_fe + panel_al + panel_fut + panel_graf + panel_bat + panel_pj + panel_off + panel_oc3 + "</div>"

    # Modal SQL
    all_sql     = {**VBA_SQL, **PY_SQL, **FUT_SQL, **BATIMENTO_SQL, **PJ_SQL, **OFF_SQL, **DRF_SQL, **SAC_COTA_SQL}
    sql_data_js = json.dumps(all_sql, ensure_ascii=False)

    fontes_vba = {q[0]: q[1] for q in SQL_QUERIES}
    fontes_py  = {q[0]: q[1] for q in PY_QUERIES}
    fontes_fut = {q[0]: q[1] for q in FUT_QUERIES}
    all_fontes = {**fontes_vba, **fontes_py, **fontes_fut}
    fontes_js  = json.dumps(all_fontes, ensure_ascii=False)

    cats_vba = {q[0]: q[4] for q in SQL_QUERIES}
    cats_py  = {q[0]: q[3] for q in PY_QUERIES}
    cats_fut = {q[0]: q[3] for q in FUT_QUERIES}
    all_cats = {**cats_vba, **cats_py, **cats_fut}
    cats_js  = json.dumps(all_cats, ensure_ascii=False)

    sql_modal_html = (
        '<div id="sql-overlay" class="sql-overlay" onclick="closeSQLIfOutside(event)">'
        '<div class="sql-modal">'
        '<div class="sql-modal-hdr">'
        '<div style="display:flex;flex-direction:column;gap:4px">'
        '<div id="sql-modal-title" class="sql-modal-title"></div>'
        '<div id="sql-modal-fonte" class="sql-modal-fonte"></div>'
        '</div>'
        '<div style="display:flex;align-items:center;gap:10px">'
        '<span id="sql-modal-cat"></span>'
        '<button class="sql-modal-close" onclick="closeSQL()" title="Fechar">&#x2715;</button>'
        '</div>'
        '</div>'
        '<pre id="sql-code" class="sql-code"></pre>'
        '</div>'
        '</div>'
    )
    legend_js = json.dumps({
        "pos":   {"label": "Posicao",            "color": "#2471a3"},
        "moeda": {"label": "Moeda / FX",         "color": "#1e8449"},
        "dur":   {"label": "Duration / ANBIMA",  "color": "#b7770d"},
        "rv":    {"label": "Renda Variavel / BTC","color": "#7d3c98"},
        "fdo":   {"label": "Fundos / Cotas",     "color": "#148f77"},
        "prov":  {"label": "Proventos",          "color": "#a93226"},
        "fus":   {"label": "Fusion / Teva",      "color": "#6a5acd"},
    }, ensure_ascii=False)

    sql_js = (
        "<script>\n"
        "var ALL_SQL    = " + sql_data_js + ";\n"
        "var ALL_FONTES = " + fontes_js   + ";\n"
        "var ALL_CATS   = " + cats_js     + ";\n"
        "var LEGEND     = " + legend_js   + ";\n"
        "function showSQL(fn) {\n"
        "  var isPy = !" + json.dumps(list(VBA_SQL.keys())) + ".includes(fn);\n"
        "  document.getElementById('sql-modal-title').textContent = fn + (isPy ? '()' : '');\n"
        "  document.getElementById('sql-modal-fonte').textContent = 'Fonte: ' + (ALL_FONTES[fn] || '');\n"
        "  document.getElementById('sql-code').textContent = ALL_SQL[fn] || '(query nao encontrada)';\n"
        "  var catEl = document.getElementById('sql-modal-cat');\n"
        "  var cat = ALL_CATS[fn];\n"
        "  var leg = cat ? LEGEND[cat] : null;\n"
        "  if (catEl) catEl.innerHTML = leg\n"
        "    ? '<span style=\"background:' + leg.color + '22;border:1px solid ' + leg.color + ';color:' + leg.color + ';border-radius:20px;padding:3px 12px 3px 8px;font-size:.68rem;font-weight:700;display:inline-flex;align-items:center;gap:6px\">'\n"
        "      + '<span style=\"width:8px;height:8px;border-radius:50%;background:' + leg.color + ';display:inline-block;flex-shrink:0\"></span>'\n"
        "      + leg.label + '</span>' : '';\n"
        "  document.getElementById('sql-overlay').classList.add('open');\n"
        "}\n"
        "function closeSQL() {\n"
        "  document.getElementById('sql-overlay').classList.remove('open');\n"
        "}\n"
        "function closeSQLIfOutside(e) {\n"
        "  if (e.target.id === 'sql-overlay') closeSQL();\n"
        "}\n"
        "document.addEventListener('keydown', function(e) { if (e.key === 'Escape') closeSQL(); });\n"
        "</script>\n"
    )

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
        '<button id="theme-toggle-btn" class="theme-toggle-btn" onclick="toggleTheme()" '
        'title="Alternar tema claro/escuro">\U0001F319</button>\n'
        '<div id="theme-scope">\n'
        + build_idx_page() + "\n"
        + build_macro_page() + "\n"
        + detail_page + "\n"
        + py_page + "\n"
        + fe_page + "\n"
        + alerta_page + "\n"
        + fut_page + "\n"
        + graficos_page + "\n"
        + rf_page + "\n"
        + build_batimento_page() + "\n"
        + build_precojusto_page() + "\n"
        + build_offshore_page() + "\n"
        + build_oc3_page() + "\n"
        + build_dash_mesa_rf_page() + "\n"
        + build_base_dados_page() + "\n"
        + build_contingencia_page() + "\n"
        + build_erd_page() + "\n"
        + '<div id="cal-section">'
        # + '<div class="kcal-section-title">&#x1F4C5; Calendario de Entregas</div>'
        + '<div class="kcal-section-title">Calendario de Entregas Semanais</div>'
        + bloco_calendario()
        + '</div>' + "\n"
        + "</div>\n"
        + todo_sidebar + "\n"
        + CAL_MODAL_HTML + "\n"
        + sql_modal_html + "\n"
        + STATUS_JS + "\n"
        + NAV_JS + "\n"
        + sql_js
        + todo_js + "\n"
        + THEME_JS + "\n"
        + CALENDAR_INIT_JS + "\n"
        + CAL_JS + "\n"
        "</body>\n"
        "</html>"
    )


# ─────────────────────────────────────────────────────────────────


def main():
    out = Path(__file__).resolve().parent / "../output" / "fluxograma.html"
    
    out.parent.mkdir(parents=True, exist_ok=True)
    
    out.write_text(build_html(), encoding="utf-8")
    print(f"Gerado: {out}")


if __name__ == "__main__":
    main()

