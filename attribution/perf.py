
# ─────────────────────────────────────────────
# Performance Attribution mensal
#
# Para os últimos N meses, calcula a atribuição de performance do fundo em
# 3 recortes (por posição/ativo, por empresa/Equity e por setor GICS) e
# monta, para cada um, uma aba com dropdown de mês + gráfico Waterfall
# nativo do Excel daquele mês. Também gera uma aba de histórico (atribuição
# mensal + retorno acumulado).
#
# Autor: Fabricio Levy
# ─────────────────────────────────────────────

import os
import sys
import time
import calendar
from datetime import date

import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.chart.label import DataLabel, DataLabelList
from openpyxl.chart.marker import DataPoint
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.drawing.line import LineProperties
import pandas as pd

XL_WATERFALL = 119

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sql_connection  # noqa: E402
import html_report     # noqa: E402


_DIR       = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_DIR, "..", "output")

# FUNDO_DEFAULT  = "ITAUCARD49295"
# FUNDO_DEFAULT  = "DIVOFIA58154"
FUNDO_DEFAULT   = 'ITAUTEV68965'
N_MESES_DEFAULT = 180   # ~2012-01 em diante (ITAUCARD49295 existe desde 2012)

# Liga/desliga as linhas de comparação no Histórico. Editar aqui e rodar de
# novo — não precisa de argumento de linha de comando.
INCLUIR_BENCHMARK = True   # benchmark cadastrado do próprio fundo (cota_benchmark)
INCLUIR_IBOV      = True   # Ibovespa (FUNDOS_DADOS_INDICES, codigo_IAM_indice='IBOV')
INCLUIR_RV_HIST   = True   # aba separada com OT0_PERF_ATTRIB_RV_DADOS_GERAL (histórico de RV)

# Janelas de performance: cada início ('YYYY-MM') gera a SUA PRÓPRIA aba
# Histórico + RV (Histórico), rebasada do zero naquele mês (cota/benchmark/
# Ibovespa/RV alcançam bem mais pro passado que a posição) — todas terminam
# no último mês fechado. As abas de posição (Posição/Empresa/Setor/etc.)
# NÃO duplicam por janela: ficam limitadas ao que o expurgo cobre, como já é.
JANELAS_PERFORMANCE = ["2012-08", "2014-01"]   # 2012-01 = início do fundo ITAUCARD49295

# JANELAS_PERFORMANCE = ["2012-08", "2014-01"]

# Mostra ou oculta cada aba do relatório (Excel e HTML) — False pula a aba
# por completo (nem calcula). Editar aqui e rodar de novo, sem precisar de
# argumento de linha de comando.
MOSTRAR_RESUMO      = True   # Resumo_Periodos / aba RESUMO (MTD/QTD/YTD/.../ITD + calendário mês a mês)
MOSTRAR_HISTORICO   = True   # Historico_<ano> / aba HISTÓRICO <ano> (1 por item em JANELAS_PERFORMANCE)
MOSTRAR_POSICAO     = True   # Attribution_Posicao / aba POR POSIÇÃO
MOSTRAR_EMPRESA     = False   # Attribution_Empresa / aba POR EMPRESA
MOSTRAR_SETOR       = True   # Attribution_Setor / aba POR SETOR
MOSTRAR_CATEGORIA   = False   # Attribution_Categoria / aba POR CATEGORIA
MOSTRAR_FATOR_RISCO = False   # Attribution_FatorRisco / aba POR FATOR DE RISCO
MOSTRAR_ACAO        = False   # Attribution_Acao / aba POR AÇÃO
MOSTRAR_RV_HIST     = True   # Attribution_RV_Hist_<ano> / aba RV HISTÓRICO <ano> (precisa também de INCLUIR_RV_HIST=True)

# Ajustes finos de exibição (não afetam o cálculo, só o que aparece).
MOSTRAR_COLUNA_BPS_HISTORICO     = False  # coluna "Atribuição mensal (bps)" nas abas Historico_<ano>
MOSTRAR_GRAFICO_BARRAS_HISTORICO = False  # barras de atribuição mensal no gráfico das abas Historico_<ano>
                                           # (False = fica só a linha de retorno acumulado)
MOSTRAR_LINHA_SOMA = False   # linha final "Soma" nas tabelas de atribuição
                             # (Posição/Empresa/Setor/Categoria/Fator de Risco/Ação/RV Histórico)

_MESES_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
             "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
_MESES_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Set", "Oct", "Nov", "Dec"]

# Classificação macro por palavra-chave no nome do ativo (case-insensitive).
# Ajustada ao universo de ativos observado no ITAUTEV68965 (fundo de RF
# pós-fixado/inflação); qualquer ativo não reconhecido cai em "Other" — nada
# desaparece silenciosamente, só não tem regra dedicada ainda.
_REGRAS_CATEGORIA = [
    ("Juros Pós", ("LFT", "OVERNIGHT", "CUSTO_SELIC")),
    ("Inflação", ("NTN-B", "NTNB")),
    ("Despesas Tx. Adm", (
        "TAXA_ADMINISTRACAO", "TAXA_GESTAO_APROPRIADA", "TAXA_LICENCA_INFO_MARCA",
        "TAXA_CUSTODIA", "DESPESAS_CETIP", "DESPESAS_AUDITORIA", "DESPESAS_ANBID",
        "OUTRAS_DESPESAS", "IMPOSTOS", "AJUSTE_COMPENSACAO_COTAS", "CORRESPONDENCIA",
    )),
]


def classificar_categoria(ativo: str) -> str:
    """Classifica o nome do ativo numa categoria macro (Juros Pós / Inflação /
    Despesas Tx. Adm / Other) a partir de `_REGRAS_CATEGORIA`."""
    nome = (ativo or "").upper()
    for categoria, chaves in _REGRAS_CATEGORIA:
        if any(chave in nome for chave in chaves):
            return categoria
    return "Other"


def montar_query(fundo: str, data_inicio: str, data_fim: str) -> str:
    """Attribution por posição (contribuição em bps, chain-linked pela cota),
    já trazendo os atributos (tipo, setor GICS, fator de risco, código do
    ativo) usados pelos outros recortes (empresa/Equity, setor, fator de
    risco e ação) — assim 1 query por mês basta para alimentar todas as
    visões, em vez de repetir a consulta pesada várias vezes.

    Base do chain-link = primeira cota disponível DENTRO do período (primeiro
    dia útil), e não @DataInicio fixo — assim meses cujo dia 1º cai em
    feriado/fim de semana não são perdidos.

    A VIEW_FUNDOS_POSICAO corrente não alcança datas mais antigas: esse
    histórico foi expurgado para a tabela VW_FUNDOS_POSICAO_EXPURGO, que a
    view corrente não vê. Por isso a posição vem de um UNION ALL das duas
    fontes — uma data nunca aparece nas duas ao mesmo tempo (foi "expurgada"
    da corrente), então não há risco de contar em dobro.
    """
    return f"""
        DECLARE @DataInicio date = '{data_inicio}';
        DECLARE @DataFim    date = '{data_fim}';
        DECLARE @Fundo      varchar(60) = '{fundo}';

        WITH posicao AS (
            SELECT codigo_IAM_fundo, ativo, codigo_IAM_ativo, ticker_bolsa, tipo,
                   gics_sector_name, fator_risco, pnl_total_perc, last_cota_com_dividendo
            FROM VIEW_FUNDOS_POSICAO
            WHERE codigo_IAM_fundo = @Fundo
              AND date >= @DataInicio AND date <= @DataFim

            UNION ALL

            SELECT codigo_IAM_fundo, ativo, codigo_IAM_ativo, ticker_bolsa, tipo,
                   gics_sector_name, fator_risco, pnl_total_perc, last_cota_com_dividendo
            FROM VW_FUNDOS_POSICAO_EXPURGO
            WHERE codigo_IAM_fundo = @Fundo
              AND date >= @DataInicio AND date <= @DataFim
        )
        SELECT
            a.codigo_IAM_fundo                                                     AS fundo,
            ISNULL(a.ativo, a.codigo_IAM_ativo)                                    AS ativo,
            a.codigo_IAM_ativo                                                     AS codigo_ativo,
            ISNULL(a.ticker_bolsa, a.codigo_IAM_ativo)                             AS ticker,
            a.tipo                                                                 AS tipo,
            ISNULL(a.gics_sector_name, '(Sem setor)')                              AS setor,
            ISNULL(a.fator_risco, '(Sem fator)')                                   AS fator_risco,
            (SUM(a.pnl_total_perc * (a.last_cota_com_dividendo /
                                     b.last_cota_com_dividendo))) * 10000          AS attribution_bps
        FROM posicao a
        LEFT JOIN VIEW_FUNDOS_COTAS_PL b
            ON b.codigo_IAM_fundo = a.codigo_IAM_fundo
           AND b.date = (SELECT MIN(c.date) FROM VIEW_FUNDOS_COTAS_PL c
                         WHERE c.codigo_IAM_fundo = a.codigo_IAM_fundo
                           AND c.date >= @DataInicio AND c.date <= @DataFim)
        GROUP BY a.codigo_IAM_fundo, ISNULL(a.ativo, a.codigo_IAM_ativo), a.codigo_IAM_ativo,
                 ISNULL(a.ticker_bolsa, a.codigo_IAM_ativo),
                 a.tipo, ISNULL(a.gics_sector_name, '(Sem setor)'), ISNULL(a.fator_risco, '(Sem fator)')
    """


def ultimos_meses(n: int, ref: date = None):
    """Últimos n meses COMPLETOS (mais antigo → mais recente).

    Retorna lista de (label 'YYYY-MM', inicio 'YYYY-MM-01', fim 'YYYY-MM-DD').
    O mês corrente (incompleto) é ignorado.
    """
    if ref is None:
        ref = date.today()

    ano, mes = ref.year, ref.month
    mes -= 1                       # começa no último mês completo
    if mes == 0:
        ano, mes = ano - 1, 12

    meses = []
    for _ in range(n):
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        meses.append((
            f"{ano:04d}-{mes:02d}",
            f"{ano:04d}-{mes:02d}-01",
            f"{ano:04d}-{mes:02d}-{ultimo_dia:02d}",
        ))
        mes -= 1
        if mes == 0:
            ano, mes = ano - 1, 12

    return list(reversed(meses))


def meses_desde(inicio_label: str, ref: date = None) -> int:
    """Quantos meses `ultimos_meses(n)` precisa pra alcançar `inicio_label`
    ('YYYY-MM') a partir do último mês completo antes de `ref` (hoje, por
    padrão). Usado pra garantir que a busca cubra a mais antiga das
    JANELAS_PERFORMANCE sem precisar calcular o N na mão.
    """
    if ref is None:
        ref = date.today()
    ano_ini, mes_ini = (int(x) for x in inicio_label.split("-"))
    ano_fim, mes_fim = ref.year, ref.month - 1
    if mes_fim == 0:
        ano_fim, mes_fim = ano_fim - 1, 12
    return max((ano_fim - ano_ini) * 12 + (mes_fim - mes_ini) + 1, 1)


def rotulo_mes(label: str) -> str:
    """'2025-07' -> 'Jul/25'."""
    ano, mes = label.split("-")
    return f"{_MESES_PT[int(mes) - 1]}/{ano[2:]}"


_COLS_POSICAO = ["ativo", "codigo_ativo", "ticker", "tipo", "setor", "fator_risco", "bps"]


def coletar_mensal(fundo: str, meses):
    """Roda a query para cada mês; devolve {label: DataFrame(ativo, codigo_ativo,
    ticker, tipo, setor, fator_risco, bps)}."""
    resultado = {}
    for label, inicio, fim in meses:
        df = sql_connection.query(montar_query(fundo, inicio, fim))
        if df.empty:
            resultado[label] = pd.DataFrame(columns=_COLS_POSICAO)
            print(f"  {label}:    sem dados  (fundo sem posições no mês)")
            continue
        df = df.dropna(subset=["attribution_bps"]).copy()
        df["ativo"] = df["ativo"].fillna("(Sem identificação)")
        df["codigo_ativo"] = df["codigo_ativo"].fillna("(Sem identificação)")
        df["ticker"] = df["ticker"].fillna("(Sem ticker)")
        df["setor"] = df["setor"].fillna("(Sem setor)")
        df["fator_risco"] = df["fator_risco"].fillna("(Sem fator)")
        df = df.rename(columns={"attribution_bps": "bps"})[_COLS_POSICAO]
        resultado[label] = df
        print(f"  {label}: {df['bps'].sum():+9.2f} bps  ({len(df)} posições)")
    return resultado


def agregar_por(dados_mensais, coluna, filtro=None):
    """A partir de {label: DataFrame(ativo, tipo, setor, bps)}, agrega por
    `coluna` (ex.: 'ativo' ou 'setor'), aplicando um filtro opcional (ex.:
    só Equity p/ a visão por empresa). Devolve {label: {chave: bps}}.
    """
    resultado = {}
    for label, df in dados_mensais.items():
        if df.empty:
            resultado[label] = {}
            continue
        d = df if filtro is None else df[filtro(df)]
        resultado[label] = {} if d.empty else d.groupby(coluna)["bps"].sum().to_dict()
    return resultado


def agregar_por_categoria(dados_mensais, classificador):
    """Como `agregar_por`, mas agrega por uma categoria DERIVADA do ativo
    (via `classificador(ativo) -> str`), não por uma coluna já existente.
    Usada na visão 'por categoria' (Juros Pós / Inflação / Despesas / Other).
    """
    resultado = {}
    for label, df in dados_mensais.items():
        if df.empty:
            resultado[label] = {}
            continue
        categoria = df["ativo"].map(classificador)
        resultado[label] = df.assign(categoria=categoria).groupby("categoria")["bps"].sum().to_dict()
    return resultado


def montar_matriz(mensal, meses_validos, ordem=None, incluir_soma=None):
    """Pivota {label: {chave: bps}} numa matriz mês × chave + coluna TOTAL.

    `meses_validos` é o conjunto de meses em que o FUNDO tinha posição (não
    necessariamente a chave deste recorte específico) — um mês fora desse
    conjunto vira NA (sem dado); um mês válido sem nenhuma chave (ex.: fundo
    sem Equity naquele mês) vira 0, não NA.

    `ordem`, se passado, fixa a ordem das colunas (ex.: categorias macro);
    qualquer chave fora dessa lista entra no final, ordenada por magnitude.

    `incluir_soma`: se None (padrão), usa MOSTRAR_LINHA_SOMA; passe True/False
    pra forçar independente da constante.
    """
    if incluir_soma is None:
        incluir_soma = MOSTRAR_LINHA_SOMA
    chaves = {s for d in mensal.values() for s in d}
    totais = {s: sum(d.get(s, 0.0) for d in mensal.values()) for s in chaves}
    if ordem:
        resto = sorted(chaves - set(ordem), key=lambda s: abs(totais[s]), reverse=True)
        chaves = [c for c in ordem if c in chaves] + resto
    else:
        chaves = sorted(chaves, key=lambda s: totais[s], reverse=True)  # mais relevante 1º

    linhas = []
    for label, d in mensal.items():                     # já em ordem cronológica
        row = {"mes": label}
        if label in meses_validos:
            row.update({s: d.get(s, 0.0) for s in chaves})
            row["TOTAL"] = sum(d.values())
        else:                                            # mês sem posição → células em branco
            row.update({s: pd.NA for s in chaves})
            row["TOTAL"] = pd.NA
        linhas.append(row)

    df = pd.DataFrame(linhas, columns=["mes"] + chaves + ["TOTAL"])
    if not incluir_soma:
        return df, chaves

    soma = {"mes": "Soma"}
    soma.update({c: df[c].sum() for c in chaves + ["TOTAL"]})
    return pd.concat([df, pd.DataFrame([soma])], ignore_index=True), chaves


def montar_query_cotas(fundo: str, data_inicio: str, data_fim: str) -> str:
    """Série diária de cota do fundo e do benchmark — 1 query para todo o
    período (não por mês), usada só para montar o Histórico com comparação
    contra o benchmark.
    """
    return f"""
        SELECT date, cota_com_dividendo, cota_benchmark, benchmark
        FROM VIEW_FUNDOS_COTAS_PL
        WHERE codigo_IAM_fundo = '{fundo}'
          AND tipo_dado = 'oficial'
          AND date >= '{data_inicio}' AND date <= '{data_fim}'
        ORDER BY date
    """


def buscar_cotas_periodo(fundo: str, data_inicio: str, data_fim: str) -> pd.DataFrame:
    """Cotas diárias (fundo + benchmark) do período, com coluna 'mes' (YYYY-MM)."""
    df = sql_connection.query(montar_query_cotas(fundo, data_inicio, data_fim))
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df["mes"] = df["date"].dt.strftime("%Y-%m")
    for c in ("cota_com_dividendo", "cota_benchmark"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.sort_values("date")


def montar_query_ibov(data_inicio: str, data_fim: str) -> str:
    """Série diária do nível do Ibovespa (FUNDOS_DADOS_INDICES)."""
    return f"""
        SELECT date, preco_limpo
        FROM FUNDOS_DADOS_INDICES
        WHERE codigo_IAM_indice = 'IBOV'
          AND date >= '{data_inicio}' AND date <= '{data_fim}'
        ORDER BY date
    """


def buscar_ibov_periodo(data_inicio: str, data_fim: str) -> pd.DataFrame:
    """Nível diário do Ibovespa do período, com coluna 'mes' (YYYY-MM)."""
    df = sql_connection.query(montar_query_ibov(data_inicio, data_fim))
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df["mes"] = df["date"].dt.strftime("%Y-%m")
    df["preco_limpo"] = pd.to_numeric(df["preco_limpo"], errors="coerce")
    return df.sort_values("date")


def montar_query_rv_hist(fundo: str, data_inicio: str, data_fim: str) -> str:
    """Performance attribution por ativo de renda variável (RV) já pronta —
    Retorno_perc é a contribuição diária do ativo para o retorno do fundo
    (não precisa de chain-link como a atribuição montada a partir da
    VIEW_FUNDOS_POSICAO). Fonte com histórico bem mais longo que a posição
    (ex.: ITAUCARD49295 existe desde 2012). 1 query para todo o período.
    """
    return f"""
        SELECT [Data] AS data, [Descricao] AS ativo, [Retorno_perc] AS retorno_perc
        FROM [DBSX337].[dbo].[OT0_PERF_ATTRIB_RV_DADOS_GERAL]
        WHERE Fundo = '{fundo}'
          AND [Data] >= '{data_inicio}' AND [Data] <= '{data_fim}'
        ORDER BY [Data]
    """


LIMITE_RETORNO_PERC_RV = 2.0   # 200% de contribuição num dia já é um exagero generoso;
                               # acima disso é erro/sentinela de dado na fonte, não retorno real


def buscar_rv_hist_periodo(fundo: str, data_inicio: str, data_fim: str) -> pd.DataFrame:
    """Série diária de atribuição por ativo RV do período, com 'mes' (YYYY-MM)
    e 'bps' (Retorno_perc convertido de fração para pontos-base).

    OT0_PERF_ATTRIB_RV_DADOS_GERAL tem linhas com Retorno_perc absurdo (na
    casa de bilhões/trilhões de %, ex.: Retorno_perc = 42700000001.22) —
    claramente erro/valor sentinela na fonte, não um retorno de verdade.
    Essas linhas são descartadas aqui (com aviso) antes de qualquer soma,
    pra não contaminar nem a aba RV (Histórico) nem o fallback do Histórico.
    """
    df = sql_connection.query(montar_query_rv_hist(fundo, data_inicio, data_fim))
    if df.empty:
        return df
    df = df.dropna(subset=["retorno_perc"]).copy()
    df["retorno_perc"] = pd.to_numeric(df["retorno_perc"], errors="coerce")
    df = df.dropna(subset=["retorno_perc"])

    outliers = df["retorno_perc"].abs() > LIMITE_RETORNO_PERC_RV
    if outliers.any():
        print(f"[AVISO] {outliers.sum()} linha(s) de OT0_PERF_ATTRIB_RV_DADOS_GERAL "
              f"descartada(s) por Retorno_perc fora do razoável "
              f"(|valor| > {LIMITE_RETORNO_PERC_RV:.0%}) — provável erro de dado na fonte.")
        df = df[~outliers]
    if df.empty:
        return df

    df["data"] = pd.to_datetime(df["data"])
    df["mes"] = df["data"].dt.strftime("%Y-%m")
    df["ativo"] = df["ativo"].fillna("(Sem identificação)")
    df["bps"] = df["retorno_perc"] * 10000
    return df.sort_values("data")


def agregar_rv_hist_mensal(rv_df, todos_meses_labels):
    """{mes: {ativo: bps}} a partir da série diária de
    OT0_PERF_ATTRIB_RV_DADOS_GERAL — soma simples do Retorno_perc (já pronto,
    sem chain-link) por ativo dentro de cada mês."""
    resultado = {label: {} for label in todos_meses_labels}
    if rv_df is None or rv_df.empty:
        return resultado
    for mes, grupo in rv_df.groupby("mes"):
        if mes in resultado:
            resultado[mes] = grupo.groupby("ativo")["bps"].sum().to_dict()
    return resultado


def mesclar_fallback_mensal(mensal_principal, mensal_fallback, todos_meses_labels):
    """{label: {chave: bps}} (na ordem de `todos_meses_labels`) — usa
    `mensal_principal` nos meses em que ele tem dado; cai para
    `mensal_fallback` só nos meses em que o principal está vazio/ausente.

    Usado pra preencher os "buracos" entre fontes complementares: posição
    (VIEW_FUNDOS_POSICAO/EXPURGO, forte a partir de ~2021) e RV histórico
    (OT0_PERF_ATTRIB_RV_DADOS_GERAL, forte até ~2021/2023) — cada uma cobre
    o período em que a outra não tem dado.
    """
    resultado = {}
    for label in todos_meses_labels:
        principal = mensal_principal.get(label)
        resultado[label] = principal if principal else mensal_fallback.get(label, {})
    return resultado


def montar_lookup_setor(dados, mais_recente=False):
    """{ativo_ou_ticker: setor} a partir de QUALQUER mês com posição
    disponível (não só o mais recente) — usado pra classificar por setor os
    ativos que só aparecem via RV histórico (que não tem campo de setor).
    Assume que o setor GICS de um ativo não muda ao longo do tempo; a
    primeira classificação encontrada (cronologicamente) é a que vale.

    `mais_recente=True` inverte a varredura: vale a classificação do mês
    mais recente em que o ativo teve setor — usado na coluna "Setor GICS"
    da aba Waterfall_Posicao (reflete reclassificações do GICS).
    """
    lookup = {}
    meses = list(dados.values())
    for df in (reversed(meses) if mais_recente else meses):
        if df is None or df.empty:
            continue
        cols = [c for c in ("ativo", "codigo_ativo", "ticker", "setor") if c in df.columns]
        if "setor" not in cols:
            continue
        for _, row in df[cols].drop_duplicates().iterrows():
            setor = row.get("setor")
            if pd.isna(setor) or setor in (None, "(Sem setor)"):
                continue
            for chave_col in ("ativo", "codigo_ativo", "ticker"):
                chave = row.get(chave_col)
                if pd.notna(chave) and chave not in lookup:
                    lookup[chave] = setor
    return lookup


def agregar_rv_por_setor(mensal_rv_hist, lookup_setor):
    """{label: {setor: bps}} a partir de {label: {ativo: bps}} do RV
    histórico, usando `lookup_setor` (de montar_lookup_setor) pra classificar
    cada ativo. Ativo sem classificação conhecida cai em '(Sem setor)'."""
    resultado = {}
    for label, d in mensal_rv_hist.items():
        agregado = {}
        for ativo, bps in d.items():
            setor = lookup_setor.get(ativo, "(Sem setor)")
            agregado[setor] = agregado.get(setor, 0.0) + bps
        resultado[label] = agregado
    return resultado


def _retornos_mensais_encadeados(sub, col_valor, cols_chave=("ano", "mes_num")):
    """A partir de `sub` (DataFrame com as colunas em `cols_chave` +
    `col_valor`, já ordenado por data, sem NaN em `col_valor`), devolve
    {chave: retorno_pct} na convenção PADRÃO de retorno mensal: último dia
    do mês contra o último dia do mês ANTERIOR — não o primeiro dia do
    próprio mês (que sub-conta o retorno do 1º dia útil do mês, pulando o
    "gap" entre o fechamento anterior e a 1ª cota do mês atual). É assim que
    relatórios oficiais de performance calculam rentabilidade mensal.

    `cols_chave` pode ser `("ano", "mes_num")` (chave = tupla) ou uma única
    coluna como `["mes"]` (chave = o próprio label 'YYYY-MM', usado pelo
    Histórico). O primeiro mês da série inteira (sem mês anterior
    disponível) usa o primeiro valor DENTRO dele mesmo como base — única
    exceção, inevitável por não haver dado anterior.
    """
    cols_chave = list(cols_chave)
    fechamentos = sub.groupby(cols_chave, sort=False)[col_valor].last()
    primeiros = sub.groupby(cols_chave, sort=False)[col_valor].first()
    retornos = {}
    base_anterior = None
    for chave in fechamentos.index:          # já em ordem cronológica (sub ordenado por data)
        ultimo = fechamentos[chave]
        base = base_anterior if base_anterior is not None else primeiros[chave]
        if pd.notna(base) and base and pd.notna(ultimo):
            retornos[chave] = (ultimo / base - 1) * 100
        base_anterior = ultimo
    return retornos


PERIODOS_PADRAO = ["MTD", "QTD", "YTD", "12M", "24M", "36M", "ITD"]


def montar_tabela_periodos(cotas_df, ibov_df=None):
    """Tabela-resumo de performance por período padrão (MTD/QTD/YTD/12M/24M/
    36M/ITD — fundo vs benchmark vs Ibovespa).

    Calculada a partir da série DIÁRIA de cota (não dos agregados mensais —
    mais precisa, principalmente pro MTD), com a data mais recente
    disponível em `cotas_df` como referência. Base de cada período = último
    valor disponível ANTES do início do período (ex.: MTD usa o fechamento
    do mês anterior, não a 1ª cota deste mês) — mesma convenção padrão de
    retorno usada no resto do módulo. Só quando não há nenhum dado anterior
    (ex.: ITD, ou o fundo começou exatamente dentro do período) cai para o
    1º valor disponível dentro do próprio período.

    Períodos mais longos que o histórico disponível (ex.: 36M pedido mas o
    fundo só tem 20 meses de cota) ficam de fora da tabela — ITD cobre esse
    caso (é sempre "desde o que a gente tem").
    """
    cols = ["periodo", "retorno_fundo_pct", "retorno_benchmark_pct", "retorno_ibov_pct"]
    if cotas_df is None or cotas_df.empty:
        return pd.DataFrame(columns=cols)

    cotas_df = cotas_df.sort_values("date")
    data_ref = cotas_df["date"].max()
    data_ini_fundo = cotas_df["date"].min()

    def _retorno(df, col, data_ini):
        if df is None or df.empty or col not in df.columns:
            return None
        fim = df[df["date"] <= data_ref]
        if fim.empty:
            return None
        anterior = df[df["date"] < data_ini]
        if not anterior.empty:
            v0 = anterior[col].iloc[-1]          # fechamento ANTES do período — convenção padrão
        else:
            primeiro = df[df["date"] >= data_ini]
            if primeiro.empty:
                return None
            v0 = primeiro[col].iloc[0]           # sem dado anterior (ex.: ITD) — único fallback
        v1 = fim[col].iloc[-1]
        if pd.isna(v0) or pd.isna(v1) or not v0:
            return None
        return (v1 / v0 - 1) * 100

    trimestre_mes_ini = ((data_ref.month - 1) // 3) * 3 + 1
    periodos_inicio = [
        ("MTD", data_ref.replace(day=1)),
        ("QTD", data_ref.replace(month=trimestre_mes_ini, day=1)),
        ("YTD", data_ref.replace(month=1, day=1)),
        ("12M", data_ref - pd.DateOffset(years=1)),
        ("24M", data_ref - pd.DateOffset(years=2)),
        ("36M", data_ref - pd.DateOffset(years=3)),
        ("ITD", data_ini_fundo),
    ]

    linhas = []
    for nome, ini in periodos_inicio:
        if nome != "ITD" and ini < data_ini_fundo:
            continue   # fundo não existia há tempo suficiente pra esse período
        linhas.append({
            "periodo": nome,
            "retorno_fundo_pct": _retorno(cotas_df, "cota_com_dividendo", ini),
            "retorno_benchmark_pct": _retorno(cotas_df, "cota_benchmark", ini),
            "retorno_ibov_pct": _retorno(ibov_df, "preco_limpo", ini),
        })
    return pd.DataFrame(linhas, columns=cols)


def montar_tabela_mensal_anual(df, col_valor, col_data="date", data_minima=None):
    """Calendário clássico de lâmina: retorno mensal (%) em colunas Jan..Dez,
    uma linha por ano, + coluna 'Acum. Ano' (retorno composto do ano).

    Calculado a partir da série DIÁRIA (`df[col_valor]`), mês a mês, com a
    convenção PADRÃO de retorno mensal — último dia do mês contra o último
    dia do mês ANTERIOR (ver `_retornos_mensais_encadeados`) — cobre TODOS
    os meses presentes em `df`, não só a janela de uma JANELA_PERFORMANCE
    específica.

    `data_minima`: descarta qualquer dado anterior a essa data antes de
    montar o calendário. Útil pro Ibovespa, que tem histórico bem mais longo
    que o fundo — sem isso, se a busca geral (`n_meses`) extrapolar um pouco
    o início real do fundo, sobra um "ano" inicial incompleto só nessa
    tabela (ex.: 3 meses de 2011 isolados, com o resto do ano em branco).
    """
    cols = ["Ano"] + _MESES_PT + ["Acum. Ano"]
    if df is None or df.empty or col_valor not in df.columns:
        return pd.DataFrame(columns=cols)

    sub = df[[col_data, col_valor]].dropna().sort_values(col_data)
    if data_minima is not None:
        sub = sub[sub[col_data] >= data_minima]
    if sub.empty:
        return pd.DataFrame(columns=cols)

    sub = sub.assign(ano=sub[col_data].dt.year, mes_num=sub[col_data].dt.month)
    retornos_mes = _retornos_mensais_encadeados(sub, col_valor)   # {(ano, mes_num): retorno_pct}

    anos = sorted({ano for ano, _ in retornos_mes})
    linhas = []
    for ano in anos:
        row = {"Ano": ano}
        cum = 1.0
        tem_mes = False
        for m in range(1, 13):
            v = retornos_mes.get((ano, m))
            row[_MESES_PT[m - 1]] = v
            if v is not None:
                cum *= (1 + v / 100)
                tem_mes = True
        row["Acum. Ano"] = (cum - 1) * 100 if tem_mes else None
        linhas.append(row)
    return pd.DataFrame(linhas, columns=cols)


def montar_tabela_calendario_comparativo(rotulo_fundo, cotas_df, nome_benchmark=None, data_minima=None):
    """Calendário comparativo Ano x Jan..Dez (meses em inglês), formato
    clássico de lâmina comparativa — 3 linhas por ano: Fundo, Benchmark e
    Alpha (= Fundo menos Benchmark, em pontos percentuais), + coluna
    'Accumulated' (retorno composto do ano; o Alpha acumulado é a diferença
    entre os dois acumulados, não o composto dos alphas mensais).

    Retorno mensal na convenção PADRÃO — último dia do mês contra o último
    dia do mês ANTERIOR (ver `_retornos_mensais_encadeados`), fundo e
    benchmark calculados separadamente (cada um só com suas próprias datas
    válidas, já que podem ter padrões de NA diferentes).

    `rotulo_fundo`: texto da linha do fundo (normalmente o código do fundo).
    Meses sem dado (ainda não aconteceram, ou faltando) ficam como None —
    quem renderiza decide o símbolo ('-', em branco, etc.).
    """
    cols = ["Ano", "Série"] + _MESES_EN + ["Accumulated"]
    if cotas_df is None or cotas_df.empty or "cota_com_dividendo" not in cotas_df.columns:
        return pd.DataFrame(columns=cols)

    def _prep(col):
        if col not in cotas_df.columns:
            return None
        sub = cotas_df[["date", col]].dropna().sort_values("date").copy()
        if data_minima is not None:
            sub = sub[sub["date"] >= data_minima]
        if sub.empty:
            return None
        sub["ano"] = sub["date"].dt.year
        sub["mes_num"] = sub["date"].dt.month
        return sub

    sub_f = _prep("cota_com_dividendo")
    sub_b = _prep("cota_benchmark")
    ret_fundo = _retornos_mensais_encadeados(sub_f, "cota_com_dividendo") if sub_f is not None else {}
    ret_bench = _retornos_mensais_encadeados(sub_b, "cota_benchmark") if sub_b is not None else {}
    if not ret_fundo and not ret_bench:
        return pd.DataFrame(columns=cols)

    anos = sorted({ano for ano, _ in ret_fundo} | {ano for ano, _ in ret_bench}, reverse=True)
    rotulo_bench = nome_benchmark or "Benchmark"
    linhas = []
    for ano in anos:
        row_f = {"Ano": ano, "Série": rotulo_fundo}
        row_b = {"Ano": ano, "Série": rotulo_bench}
        row_a = {"Ano": ano, "Série": "Alpha"}
        cum_f, cum_b = 1.0, 1.0
        tem_f, tem_b = False, False
        for m in range(1, 13):
            vf, vb = ret_fundo.get((ano, m)), ret_bench.get((ano, m))
            row_f[_MESES_EN[m - 1]] = vf
            row_b[_MESES_EN[m - 1]] = vb
            row_a[_MESES_EN[m - 1]] = (vf - vb) if (vf is not None and vb is not None) else None
            if vf is not None:
                cum_f *= (1 + vf / 100)
                tem_f = True
            if vb is not None:
                cum_b *= (1 + vb / 100)
                tem_b = True
        acum_f = (cum_f - 1) * 100 if tem_f else None
        acum_b = (cum_b - 1) * 100 if tem_b else None
        row_f["Accumulated"] = acum_f
        row_b["Accumulated"] = acum_b
        row_a["Accumulated"] = (acum_f - acum_b) if (acum_f is not None and acum_b is not None) else None
        linhas += [row_f, row_b, row_a]
    return pd.DataFrame(linhas, columns=cols)


def montar_historico(mensal_posicao, meses_historico, cotas_df=None, ibov_df=None,
                     incluir_benchmark=True, incluir_ibov=True, mensal_rv_hist=None):
    """Série (mês, atribuição do mês em bps, retorno acumulado do fundo, do
    benchmark cadastrado e do Ibovespa — todos compostos mês a mês pela cota).

    `meses_historico` é a lista COMPLETA de meses pedidos (não só os que têm
    posição) — o histórico de cota costuma alcançar muito mais para trás do
    que o histórico de posição (ex.: VIEW_FUNDOS_COTAS_PL cobre desde 2012,
    mas VW_FUNDOS_POSICAO_EXPURGO só desde 2021). Assim, mesmo sem detalhe de
    posição/atribuição num mês antigo, a curva de retorno (fundo/benchmark/
    Ibovespa) ainda aparece a partir da cota.

    A barra de atribuição em bps usa `mensal_posicao` quando há; nos meses
    sem posição, cai para `mensal_rv_hist` (OT0_PERF_ATTRIB_RV_DADOS_GERAL,
    que cobre um período bem maior) se disponível; só fica em branco (NA)
    quando nenhuma das duas fontes tem dado pro mês.

    Retorno do fundo/benchmark/Ibovespa em cada mês = último valor
    disponível no mês contra o último valor disponível no mês ANTERIOR —
    convenção PADRÃO de retorno mensal (ver `_retornos_mensais_encadeados`),
    igual à usada na aba RESUMO. Se não houver cota do fundo pro mês, usa a
    soma da atribuição em bps daquele mês (posição ou RV) como aproximação;
    se não houver nem cota nem atribuição, o mês fica com retorno 0 (sem
    informação) e não distorce o acumulado.

    `incluir_benchmark`/`incluir_ibov` controlam se as respectivas colunas
    são calculadas — ainda que `cotas_df`/`ibov_df` tenham os dados, ficam
    como NA se a flag estiver desligada (ex.: INCLUIR_BENCHMARK = False).
    """
    cotas_df = cotas_df if cotas_df is not None else pd.DataFrame()
    ibov_df = ibov_df if ibov_df is not None else pd.DataFrame()
    mensal_rv_hist = mensal_rv_hist or {}

    def _chain_por_mes(df, col):
        if df is None or df.empty or col not in df.columns:
            return {}
        sub = df[["date", "mes", col]].dropna(subset=[col]).sort_values("date")
        if sub.empty:
            return {}
        return _retornos_mensais_encadeados(sub, col, cols_chave=["mes"])

    ret_fundo_mensal = _chain_por_mes(cotas_df, "cota_com_dividendo")
    ret_bench_mensal = _chain_por_mes(cotas_df, "cota_benchmark") if incluir_benchmark else {}
    ret_ibov_mensal = _chain_por_mes(ibov_df, "preco_limpo") if incluir_ibov else {}
    bench_disponivel = bool(ret_bench_mensal)
    ibov_disponivel = bool(ret_ibov_mensal)

    nome_benchmark = None
    if incluir_benchmark and not cotas_df.empty and "benchmark" in cotas_df.columns:
        nomes = cotas_df["benchmark"].dropna()
        if not nomes.empty:
            nome_benchmark = nomes.iloc[-1]

    linhas = []
    cum_fundo = 1.0
    cum_bench = 1.0
    cum_ibov = 1.0
    for label in meses_historico:
        pos_mes = mensal_posicao.get(label)
        rv_mes = mensal_rv_hist.get(label)
        if pos_mes:
            total_bps = sum(pos_mes.values())
        elif rv_mes:
            total_bps = sum(rv_mes.values())
        else:
            total_bps = pd.NA
        tem_bps = pd.notna(total_bps)

        r_fundo_cota = ret_fundo_mensal.get(label)
        if r_fundo_cota is not None:
            r_fundo = r_fundo_cota / 100.0
        else:
            r_fundo = (total_bps / 10000.0) if tem_bps else 0.0

        r_bench_pct = ret_bench_mensal.get(label)
        r_bench = (r_bench_pct / 100.0) if r_bench_pct is not None else None

        r_ibov_pct = ret_ibov_mensal.get(label)
        r_ibov = (r_ibov_pct / 100.0) if r_ibov_pct is not None else None

        cum_fundo *= (1 + r_fundo)
        cum_bench *= (1 + r_bench) if r_bench is not None else 1.0
        cum_ibov *= (1 + r_ibov) if r_ibov is not None else 1.0

        linhas.append({
            "mes": rotulo_mes(label),
            "total_bps": total_bps,
            "retorno_acumulado_pct": (cum_fundo - 1) * 100,
            "retorno_benchmark_pct": (cum_bench - 1) * 100 if bench_disponivel else None,
            "retorno_ibov_pct": (cum_ibov - 1) * 100 if ibov_disponivel else None,
        })

    df = pd.DataFrame(linhas, columns=["mes", "total_bps", "retorno_acumulado_pct",
                                       "retorno_benchmark_pct", "retorno_ibov_pct"])
    if not bench_disponivel:
        df["retorno_benchmark_pct"] = pd.NA
    if not ibov_disponivel:
        df["retorno_ibov_pct"] = pd.NA
    return df, nome_benchmark


def _escrever_calendario_comparativo(ws, df_cal, linha_inicio):
    """Escreve o calendário comparativo (Ano, mesclado em 3 linhas | Série |
    Jan..Dez | Accumulated) a partir de `linha_inicio`. 3 linhas por ano:
    Fundo, Benchmark, Alpha (de montar_tabela_calendario_comparativo).
    Meses sem dado aparecem como '-', igual ao formato pedido. Devolve a
    próxima linha livre."""
    if df_cal is None or df_cal.empty:
        return linha_inicio

    pct_fmt = '#,##0.00"%";[Red]-#,##0.00"%"'
    meses = _MESES_EN
    col_accum = 3 + len(meses)   # A=Ano, B=Série, C..N=meses, O=Accumulated

    header_row = linha_inicio
    ws.cell(row=header_row, column=1, value="Year")
    for j, mes in enumerate(meses, start=3):
        ws.cell(row=header_row, column=j, value=mes)
    ws.cell(row=header_row, column=col_accum, value="Accumulated")
    for j in range(1, col_accum + 1):
        cell = ws.cell(row=header_row, column=j)
        cell.fill = openpyxl.styles.PatternFill("solid", fgColor="000D3C")
        cell.font = openpyxl.styles.Font(color="FFFFFF", bold=True)

    def _valor_ou_traco(cell, v, negrito=False):
        if v is None or pd.isna(v):
            cell.value = "-"
            cell.alignment = openpyxl.styles.Alignment(horizontal="center")
            return
        cell.value = v
        cell.number_format = pct_fmt
        cell.font = openpyxl.styles.Font(
            bold=negrito, color="1E7E34" if v > 0 else ("C0392B" if v < 0 else "444444"))

    linha = header_row + 1
    linhas_por_ano = df_cal.groupby("Ano", sort=False)
    for ano, bloco in linhas_por_ano:
        linha_ano_ini = linha
        for _, row in bloco.iterrows():
            ws.cell(row=linha, column=2, value=row["Série"])
            for j, mes in enumerate(meses, start=3):
                _valor_ou_traco(ws.cell(row=linha, column=j), row[mes])
            _valor_ou_traco(ws.cell(row=linha, column=col_accum), row["Accumulated"], negrito=True)
            linha += 1
        ws.cell(row=linha_ano_ini, column=1, value=int(ano))
        ws.cell(row=linha_ano_ini, column=1).font = openpyxl.styles.Font(bold=True)
        if linha - linha_ano_ini > 1:
            ws.merge_cells(start_row=linha_ano_ini, start_column=1, end_row=linha - 1, end_column=1)
            ws.cell(row=linha_ano_ini, column=1).alignment = openpyxl.styles.Alignment(
                vertical="center", horizontal="center")

    ws.column_dimensions["A"].width = 9
    ws.column_dimensions["B"].width = 16
    for col_letter in "CDEFGHIJKLMN":
        ws.column_dimensions[col_letter].width = 9
    ws.column_dimensions[get_column_letter(col_accum)].width = 13
    return linha + 1


def _escrever_aba_periodos(writer, df_periodos, nome_benchmark=None, tabelas_mensais=None,
                           df_calendario_comparativo=None):
    """Aba 'Resumo_Periodos': tudo que é resumo de performance, numa só aba —
    tabela MTD/QTD/YTD/12M/24M/36M/ITD (fundo vs benchmark vs Ibovespa) +
    gráfico de barras agrupadas, seguidos do calendário comparativo Fundo x
    Benchmark x Alpha (`df_calendario_comparativo`, de
    montar_tabela_calendario_comparativo) e de calendários extras mês a mês
    por ano em `tabelas_mensais` (ex.: Ibovespa, de montar_tabela_mensal_anual).
    """
    tabelas_mensais = [(t, df) for t, df in (tabelas_mensais or []) if df is not None and not df.empty]

    wb = writer.book
    ws = wb.create_sheet("Resumo_Periodos")

    rotulo_bench = f"{nome_benchmark} (%)" if nome_benchmark else "Benchmark (%)"
    ws.append(["Período", "Fundo (%)", rotulo_bench, "Ibovespa (%)"])
    for cell in ws[1]:
        cell.fill = openpyxl.styles.PatternFill("solid", fgColor="000D3C")
        cell.font = openpyxl.styles.Font(color="FFFFFF", bold=True)

    def _ou_none(v):
        return None if pd.isna(v) else v

    for _, row in df_periodos.iterrows():
        ws.append([row["periodo"], _ou_none(row["retorno_fundo_pct"]),
                  _ou_none(row["retorno_benchmark_pct"]), _ou_none(row["retorno_ibov_pct"])])

    n = ws.max_row
    for row in ws.iter_rows(min_row=2, max_row=n, min_col=2, max_col=4):
        for cell in row:
            cell.number_format = '#,##0.00;[Red]-#,##0.00'
            if cell.value is not None:
                cell.font = openpyxl.styles.Font(
                    color="1E7E34" if cell.value > 0 else ("C0392B" if cell.value < 0 else "444444"))

    for col, width in zip("ABCD", (10, 16, 20, 16)):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"

    # Altura do gráfico (cm) convertida em nº de linhas aproximado (linha
    # padrão ~0.53cm) — pra saber a partir de qual linha a planilha fica
    # livre de novo e os calendários mensais podem começar sem se sobrepor.
    altura_grafico_cm = 11
    linha_livre_grafico = 2 + int(altura_grafico_cm / 0.53) + 2

    if n >= 2:
        grafico = BarChart()
        grafico.type = "col"
        grafico.grouping = "clustered"
        grafico.title = "Performance por período — fundo x benchmark x Ibovespa"
        grafico.y_axis.title = "Retorno (%)"
        grafico.x_axis.title = "Período"
        grafico.height, grafico.width = altura_grafico_cm, 20
        grafico.x_axis.delete = False   # openpyxl 3.1: sem isso o Excel esconde os eixos
        grafico.y_axis.delete = False
        grafico.x_axis.tickLblPos = "low"
        _sem_sobreposicao(grafico)

        dados = Reference(ws, min_col=2, max_col=4, min_row=1, max_row=n)
        categorias = Reference(ws, min_col=1, min_row=2, max_row=n)
        grafico.add_data(dados, titles_from_data=True)
        grafico.set_categories(categorias)

        ws.add_chart(grafico, "F2")

    if df_calendario_comparativo is None and not tabelas_mensais:
        return

    linha = max(n + 3, linha_livre_grafico)
    if df_calendario_comparativo is not None and not df_calendario_comparativo.empty:
        linha = _escrever_calendario_comparativo(ws, df_calendario_comparativo, linha) + 1

    num_fmt = '#,##0.00;[Red]-#,##0.00'
    for titulo, df_cal in tabelas_mensais:
        ws.cell(row=linha, column=1, value=titulo).font = openpyxl.styles.Font(bold=True, size=12, color="000D3C")
        linha += 1

        header_row = linha
        for j, col in enumerate(df_cal.columns, start=1):
            cell = ws.cell(row=header_row, column=j, value=col)
            cell.fill = openpyxl.styles.PatternFill("solid", fgColor="000D3C")
            cell.font = openpyxl.styles.Font(color="FFFFFF", bold=True)
        linha += 1

        for _, row in df_cal.iterrows():
            for j, col in enumerate(df_cal.columns, start=1):
                v = row[col]
                v = None if pd.isna(v) else v
                cell = ws.cell(row=linha, column=j, value=v)
                if col != "Ano" and v is not None:
                    cell.number_format = num_fmt
                    cell.font = openpyxl.styles.Font(
                        bold=(col == "Acum. Ano"),
                        color="1E7E34" if v > 0 else ("C0392B" if v < 0 else "444444"))
            linha += 1
        linha += 2   # espaço entre tabelas

    for col_letter in "EFGHIJKLM":
        ws.column_dimensions[col_letter].width = 9
    ws.column_dimensions["N"].width = 12


def _escrever_aba_matriz(writer, df, nome_aba):

    num_fmt = '#,##0.00;[Red]-#,##0.00'   # negativos em vermelho
    df.to_excel(writer, sheet_name=nome_aba, index=False)
    ws = writer.sheets[nome_aba]

    for cell in ws[1]:
        cell.fill = openpyxl.styles.PatternFill("solid", fgColor="000D3C")
        cell.font = openpyxl.styles.Font(color="FFFFFF", bold=True)

    n_linhas = ws.max_row
    for row in ws.iter_rows(min_row=2):
        eh_soma = row[0].row == n_linhas and row[0].value == "Soma"
        for cell in row:
            col_name = ws.cell(row=1, column=cell.column).value
            if eh_soma:
                cell.fill = openpyxl.styles.PatternFill("solid", fgColor="D9E1F2")
                cell.font = openpyxl.styles.Font(bold=True)
            elif cell.row % 2 == 0:
                cell.fill = openpyxl.styles.PatternFill("solid", fgColor="EAF0FB")
            if col_name != "mes":
                cell.number_format = num_fmt
            if col_name == "TOTAL":
                cell.font = openpyxl.styles.Font(bold=True, color=cell.font.color)

    for col in ws.columns:
        max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in col)
        ws.column_dimensions[col[0].column_letter].width = max_len + 3
    ws.freeze_panes = "B2"


def _escrever_aba_waterfall(writer, aba_matriz, aba_grafico, categorias, meses_dados,
                             n_meses, rotulo_linha="Componente", setor_por_categoria=None):
    """Aba com dropdown de mês + tabela auxiliar (INDEX/MATCH na matriz
    `aba_matriz`) que alimenta o gráfico Waterfall nativo de UM mês por vez.

    `setor_por_categoria`: {categoria: setor GICS} — se passado, a tabela
    auxiliar ganha a coluna C "Setor GICS" (fora da faixa do gráfico, que
    continua só Ativo × Contribuição).

    Devolve (faixa_dados, ref_titulo) para o passo de inserção do gráfico via
    COM, ou (None, None) se não houver nenhuma categoria (ex.: fundo sem
    Equity no período, para a visão "por empresa").
    """
    wb = writer.book
    ws = wb.create_sheet(aba_grafico)

    if not categorias:
        ws["A1"] = (f"Sem dados para compor esta visão ({rotulo_linha}) "
                    f"no período selecionado.")
        ws["A1"].font = openpyxl.styles.Font(italic=True, color="7F7F7F")
        ws.column_dimensions["A"].width = 60
        return None, None

    # Faixas da aba de matriz referenciadas pelo INDEX/MATCH
    ultima_lin = 1 + n_meses                               # última linha de mês (antes de 'Soma')
    col_ini    = "B"
    col_fim    = get_column_letter(1 + len(categorias))    # última coluna de categoria
    col_total  = get_column_letter(2 + len(categorias))    # coluna TOTAL
    A = aba_matriz
    rng_meses = f"{A}!$A$2:$A${ultima_lin}"
    rng_hdr   = f"{A}!${col_ini}$1:${col_fim}$1"
    rng_mat   = f"{A}!${col_ini}$2:${col_fim}${ultima_lin}"
    rng_total = f"{A}!${col_total}$2:${col_total}${ultima_lin}"

    # Seletor de mês
    ws["A1"] = "Mês:"
    ws["A1"].font = openpyxl.styles.Font(bold=True)
    ws["B1"] = meses_dados[-1]                             # default = mês mais recente
    ws["B1"].font = openpyxl.styles.Font(bold=True, color="1F4E78")
    ws["B1"].fill = openpyxl.styles.PatternFill("solid", fgColor="FFF2CC")

    dv = DataValidation(type="list",
                        formula1='"' + ",".join(meses_dados) + '"',
                        allow_blank=False, showDropDown=False)
    ws.add_data_validation(dv)
    dv.add(ws["B1"])

    # Título dinâmico (o gráfico linka nesta célula)
    ws["D1"] = (f'="Performance Attribution  |  "&$B$1&"  |  Total do mês: "'
                f'&TEXT(IFERROR(INDEX({rng_total},MATCH($B$1,{rng_meses},0)),0),'
                f'" +#,##0.0;-#,##0.0")&" bps"')

    # Tabela auxiliar: categorias (ordem fixa) × contribuição do mês selecionado
    ws["A3"] = rotulo_linha
    ws["B3"] = "Contribuição (bps)"
    cabecalhos = ["A3", "B3"]
    if setor_por_categoria is not None:
        ws["C3"] = "Setor GICS"
        cabecalhos.append("C3")
    for c in cabecalhos:
        ws[c].fill = openpyxl.styles.PatternFill("solid", fgColor="000D3C")
        ws[c].font = openpyxl.styles.Font(color="FFFFFF", bold=True)

    for i, cat in enumerate(categorias):
        r = 4 + i
        ws[f"A{r}"] = cat
        ws[f"B{r}"] = (f'=IFERROR(INDEX({rng_mat},MATCH($B$1,{rng_meses},0),'
                       f'MATCH($A{r},{rng_hdr},0)),0)')
        ws[f"B{r}"].number_format = '#,##0.00;[Red]-#,##0.00'
        if setor_por_categoria is not None:
            ws[f"C{r}"] = setor_por_categoria.get(cat, "(Sem setor)")

    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 18
    if setor_por_categoria is not None:
        ws.column_dimensions["C"].width = max(
            [12] + [len(str(s)) + 3 for s in setor_por_categoria.values()])

    faixa_dados = f"A3:B{3 + len(categorias)}"
    return faixa_dados, f"={aba_grafico}!$D$1"


def _escala_percentil(vals, p_baixo=0.03, p_alto=0.97, pad_frac=0.2, min_pad=1.0):
    """Faixa [lo, hi] pro eixo de um gráfico, baseada em percentil em vez de
    min/max puro — um único mês com valor fora da curva (ex.: atribuição de
    RV histórico de um mês de euforia/pânico isolado) não deve esmagar a
    escala e deixar todos os outros meses parecendo "sem barra". Os pontos
    fora da faixa simplesmente ficam cortados no limite do gráfico (o valor
    real continua certo na célula/tooltip, só a altura visual é limitada).
    """
    validos = sorted(v for v in vals if v is not None and not pd.isna(v))
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


# Mesma paleta do HTML (html_report._COR_*): fundo, benchmark, Ibovespa.
_CORES_HISTORICO_XL = ("EC7000", "2A78D6", "4A3AA7")


def _passo_rotulos_meses(n_meses, max_rotulos=16):
    """Passo de calendário (1, 3, 6, 12, 24... meses) entre os rótulos do
    eixo X pra caber ~`max_rotulos` na horizontal, sem o Excel girar o texto."""
    return next((p for p in (1, 3, 6, 12, 24, 36, 60) if n_meses / p <= max_rotulos), 60)


def _formatar_eixos_historico(grafico, passo_x):
    """Eixos visíveis — o openpyxl 3.1 não grava `<c:delete val="0"/>` se
    `delete` não for explicitamente False, e aí o Excel desenha o gráfico
    sem NENHUM rótulo de eixo —, grade horizontal clara, rótulos do eixo X
    sempre embaixo (mesmo com valores negativos) e 1 a cada `passo_x` meses."""
    grafico.x_axis.delete = False
    grafico.y_axis.delete = False
    grafico.x_axis.tickLblPos = "low"
    grafico.x_axis.tickLblSkip = passo_x
    grafico.x_axis.tickMarkSkip = passo_x
    grafico.x_axis.noMultiLvlLbl = True
    grafico.y_axis.majorGridlines.spPr = GraphicalProperties(ln=LineProperties(solidFill="E4E8EF"))


def _sem_sobreposicao(grafico):
    """Título, legenda e títulos de eixo FORA da área de plotagem — o
    openpyxl 3.1 não grava `overlay=0` e o Excel os desenha por cima das
    séries/rótulos."""
    for titulo in (grafico.title, grafico.x_axis.title, grafico.y_axis.title):
        if titulo is not None:
            titulo.overlay = False
    if grafico.legend is not None:
        grafico.legend.overlay = False


def _rotulo_so_no_ultimo_ponto(serie, idx):
    """Mostra o valor só no último ponto da série (ponta direita da linha),
    no formato da própria célula."""
    sem_nada = dict(showVal=False, showSerName=False, showCatName=False,
                    showLegendKey=False, showPercent=False, showBubbleSize=False)
    serie.dLbls = DataLabelList(
        dLbl=[DataLabel(idx=idx, dLblPos="r", **{**sem_nada, "showVal": True})],
        **sem_nada)


def _escrever_aba_historico(writer, df_historico, nome_benchmark=None, nome_aba="Historico", inicio=None):
    """Aba 'Historico': tabela + gráfico de linha do retorno acumulado
    (fundo/benchmark/Ibovespa) — cor fixa por série (a mesma do HTML), fundo
    em destaque (linha mais grossa), eixo X com rótulos por ano/semestre/
    trimestre conforme o tamanho da janela. Série sem nenhum dado (ex.:
    fundo sem benchmark) fica fora do gráfico e da legenda.

    A coluna de atribuição mensal (bps) e o gráfico de barras (separado,
    abaixo da linha — não num eixo secundário, que distorce a leitura) são
    opcionais — ver MOSTRAR_COLUNA_BPS_HISTORICO e
    MOSTRAR_GRAFICO_BARRAS_HISTORICO."""
    wb = writer.book
    ws = wb.create_sheet(nome_aba)

    rotulo_bench = f"Retorno acumulado — {nome_benchmark} (%)" if nome_benchmark else "Retorno acumulado — benchmark (%)"
    cabecalho = ["Mês"]
    if MOSTRAR_COLUNA_BPS_HISTORICO:
        cabecalho.append("Atribuição mensal (bps)")
    cabecalho += ["Retorno acumulado — fundo (%)", rotulo_bench, "Retorno acumulado — Ibovespa (%)"]
    ws.append(cabecalho)
    for cell in ws[1]:
        cell.fill = openpyxl.styles.PatternFill("solid", fgColor="000D3C")
        cell.font = openpyxl.styles.Font(color="FFFFFF", bold=True)

    def _ou_none(v):
        return None if pd.isna(v) else v

    for _, row in df_historico.iterrows():
        linha_dados = [row["mes"]]
        if MOSTRAR_COLUNA_BPS_HISTORICO:
            linha_dados.append(_ou_none(row["total_bps"]))
        linha_dados += [_ou_none(row["retorno_acumulado_pct"]), _ou_none(row["retorno_benchmark_pct"]),
                        _ou_none(row["retorno_ibov_pct"])]
        ws.append(linha_dados)

    n = ws.max_row
    n_cols = len(cabecalho)
    for row in ws.iter_rows(min_row=2, max_row=n, min_col=2, max_col=n_cols):
        for cell in row:
            cell.number_format = '#,##0.00;[Red]-#,##0.00'

    larguras = [10] + ([24] if MOSTRAR_COLUNA_BPS_HISTORICO else []) + [24, 24, 24]
    for col, width in zip("ABCDE", larguras):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"

    if n < 2:
        return

    col_pct_ini = 3 if MOSTRAR_COLUNA_BPS_HISTORICO else 2
    categorias = Reference(ws, min_col=1, min_row=2, max_row=n)
    passo_x = _passo_rotulos_meses(n - 1)

    linha = LineChart()
    for k, cor in enumerate(_CORES_HISTORICO_XL):
        col = col_pct_ini + k
        linhas_com_dado = [r for r in range(2, n + 1) if ws.cell(row=r, column=col).value is not None]
        if not linhas_com_dado:
            continue                       # série sem dado não entra (nem na legenda)
        linha.add_data(Reference(ws, min_col=col, min_row=1, max_row=n), titles_from_data=True)
        serie = linha.series[-1]
        serie.graphicalProperties.line.solidFill = cor
        serie.graphicalProperties.line.width = 31750 if k == 0 else 19050   # EMU: 2,5pt fundo / 1,5pt demais
        serie.marker.symbol = "none"       # sem marcador por ponto — com muitos
        serie.smooth = False               # meses (janelas de 10+ anos) vira bolha
        _rotulo_so_no_ultimo_ponto(serie, linhas_com_dado[-1] - 2)
    linha.set_categories(categorias)
    linha.varyColors = False               # 1 série só: sem isso o Excel pinta cada mês de uma cor
    linha.title = f"Retorno acumulado desde {inicio}" if inicio else "Retorno acumulado"
    _formatar_eixos_historico(linha, passo_x)
    linha.y_axis.number_format = '#,##0"%"'
    linha.legend.position = "b"
    _sem_sobreposicao(linha)
    linha.height, linha.width = 12, 26
    ws.add_chart(linha, "G2")

    if MOSTRAR_GRAFICO_BARRAS_HISTORICO and MOSTRAR_COLUNA_BPS_HISTORICO:
        colunas = BarChart()
        colunas.type = "col"
        colunas.title = "Atribuição mensal (bps)"
        colunas.add_data(Reference(ws, min_col=2, min_row=1, max_row=n), titles_from_data=True)
        colunas.set_categories(categorias)
        # Verde/vermelho pelo sinal, como no HTML — sem invertIfNegative o
        # Excel pinta as barras negativas de branco.
        barras = colunas.series[0]
        barras.invertIfNegative = False
        barras.graphicalProperties.solidFill = "1E7E34"
        barras.graphicalProperties.line.noFill = True
        for r in range(2, n + 1):
            v = ws.cell(row=r, column=2).value
            if v is not None and v < 0:
                ponto = DataPoint(idx=r - 2, invertIfNegative=False)
                ponto.graphicalProperties.solidFill = "C0392B"
                ponto.graphicalProperties.line.noFill = True
                barras.dPt.append(ponto)
        colunas.varyColors = False
        colunas.gapWidth = 50

        # Eixo robusto a outliers — ver _escala_percentil. Sem isso, um único
        # mês com atribuição fora da curva faz os demais parecerem "sem barra".
        # Limites arredondados pra grade não cair em valores quebrados.
        ticks_b, passo_b = html_report._ticks_redondos(*_escala_percentil(df_historico["total_bps"]), n_alvo=4)
        colunas.y_axis.scaling.min = ticks_b[0]
        colunas.y_axis.scaling.max = ticks_b[-1]
        colunas.y_axis.majorUnit = passo_b
        _formatar_eixos_historico(colunas, passo_x)
        colunas.y_axis.number_format = '#,##0'
        colunas.legend = None
        _sem_sobreposicao(colunas)
        colunas.height, colunas.width = 8, 26
        ws.add_chart(colunas, "G27")       # logo abaixo da linha (12cm ≈ 23 linhas a partir de G2)


def _sufixo_janela(inicio: str) -> str:
    """'2010-01' -> '2010' (usado em nomes de aba/sheet)."""
    return inicio.split("-")[0]


def gerar_excel(fundo, meses, meses_dados,
                df_posicao, cats_posicao,
                df_empresa, cats_empresa,
                df_setor, cats_setor,
                df_categoria, cats_categoria,
                df_fator_risco, cats_fator_risco,
                df_acao, cats_acao,
                historicos, nome_benchmark=None,
                rv_hists=None, df_periodos=None, tabelas_mensais=None,
                df_calendario_comparativo=None, meses_dados_completo=None,
                setor_posicao=None):
    """
    `historicos`: lista de (inicio_janela 'YYYY-MM', df_historico) — 1 aba
    'Historico_<ano>' por janela em JANELAS_PERFORMANCE.
    `rv_hists`: lista de (inicio_janela, df_rv, cats_rv, meses_dados_rv,
    n_meses_janela) — 1 par de abas 'Attribution_RV_Hist_<ano>' /
    'Waterfall_RV_Hist_<ano>' por janela.
    `df_periodos`: tabela MTD/QTD/YTD/12M/24M/36M/ITD (de montar_tabela_periodos).
    `tabelas_mensais`: lista de (titulo, df_calendario) — de
    montar_tabela_mensal_anual, 1 calendário Ano x Jan..Dez por título
    (ex.: Ibovespa).
    `df_calendario_comparativo`: calendário Fundo x Benchmark x Alpha (de
    montar_tabela_calendario_comparativo).
    `meses_dados_completo`: meses com dado em Posição/Empresa/Setor DEPOIS
    de preenchidos com RV histórico (pode ir bem mais pro passado que
    `meses_dados`) — usado só no dropdown dessas 3 abas; as demais
    (Categoria/Fator de Risco/Ação) continuam usando `meses_dados`.
    `setor_posicao`: {ativo: setor GICS} — vira a coluna "Setor GICS" da
    aba Waterfall_Posicao.

    Cada aba respeita o MOSTRAR_* correspondente (constantes no topo do
    arquivo) — se desligado, a aba nem é criada.
    """
    rv_hists = rv_hists or []
    tabelas_mensais = tabelas_mensais or []
    meses_dados_completo = meses_dados_completo or meses_dados

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    primeiro, ultimo = meses[0][0], meses[-1][0]
    nome = f"performance_attribution_{fundo}_mensal_{primeiro}_a_{ultimo}.xlsx"
    caminho = os.path.join(OUTPUT_DIR, nome)

    specs = []   # (aba_grafico, faixa, ref_titulo) p/ inserir o waterfall nativo via COM
    with pd.ExcelWriter(caminho, engine="openpyxl") as writer:
        if MOSTRAR_RESUMO:
            tem_periodos = df_periodos is not None and not df_periodos.empty
            tem_mensais = any(df is not None and not df.empty for _, df in tabelas_mensais)
            tem_comparativo = df_calendario_comparativo is not None and not df_calendario_comparativo.empty
            if tem_periodos or tem_mensais or tem_comparativo:
                _escrever_aba_periodos(writer, df_periodos if tem_periodos else pd.DataFrame(columns=[
                    "periodo", "retorno_fundo_pct", "retorno_benchmark_pct", "retorno_ibov_pct"]),
                    nome_benchmark, tabelas_mensais, df_calendario_comparativo)

        if MOSTRAR_HISTORICO:
            for inicio, df_h in historicos:
                _escrever_aba_historico(writer, df_h, nome_benchmark,
                                        nome_aba=f"Historico_{_sufixo_janela(inicio)}", inicio=inicio)

        if MOSTRAR_POSICAO:
            _escrever_aba_matriz(writer, df_posicao, "Attribution_Posicao")
            faixa, ref = _escrever_aba_waterfall(writer, "Attribution_Posicao", "Waterfall_Posicao",
                                                 cats_posicao, meses_dados_completo, len(meses), "Ativo",
                                                 setor_por_categoria=setor_posicao)
            if faixa:
                specs.append(("Waterfall_Posicao", faixa, ref))

        if MOSTRAR_EMPRESA:
            _escrever_aba_matriz(writer, df_empresa, "Attribution_Empresa")
            faixa, ref = _escrever_aba_waterfall(writer, "Attribution_Empresa", "Waterfall_Empresa",
                                                 cats_empresa, meses_dados_completo, len(meses), "Empresa")
            if faixa:
                specs.append(("Waterfall_Empresa", faixa, ref))

        if MOSTRAR_SETOR:
            _escrever_aba_matriz(writer, df_setor, "Attribution_Setor")
            faixa, ref = _escrever_aba_waterfall(writer, "Attribution_Setor", "Waterfall_Setor",
                                                 cats_setor, meses_dados_completo, len(meses), "Setor GICS")
            if faixa:
                specs.append(("Waterfall_Setor", faixa, ref))

        if MOSTRAR_CATEGORIA:
            _escrever_aba_matriz(writer, df_categoria, "Attribution_Categoria")
            faixa, ref = _escrever_aba_waterfall(writer, "Attribution_Categoria", "Waterfall_Categoria",
                                                 cats_categoria, meses_dados, len(meses), "Categoria")
            if faixa:
                specs.append(("Waterfall_Categoria", faixa, ref))

        if MOSTRAR_FATOR_RISCO:
            _escrever_aba_matriz(writer, df_fator_risco, "Attribution_FatorRisco")
            faixa, ref = _escrever_aba_waterfall(writer, "Attribution_FatorRisco", "Waterfall_FatorRisco",
                                                 cats_fator_risco, meses_dados, len(meses), "Fator de Risco")
            if faixa:
                specs.append(("Waterfall_FatorRisco", faixa, ref))

        if MOSTRAR_ACAO:
            _escrever_aba_matriz(writer, df_acao, "Attribution_Acao")
            faixa, ref = _escrever_aba_waterfall(writer, "Attribution_Acao", "Waterfall_Acao",
                                                 cats_acao, meses_dados, len(meses), "Ação")
            if faixa:
                specs.append(("Waterfall_Acao", faixa, ref))

        if MOSTRAR_RV_HIST:
            for inicio, _mensal_janela, df_rv_j, cats_rv_j, meses_dados_rv_j, n_meses_janela in rv_hists:
                suf = _sufixo_janela(inicio)
                aba_dados, aba_graf = f"Attribution_RV_Hist_{suf}", f"Waterfall_RV_Hist_{suf}"
                _escrever_aba_matriz(writer, df_rv_j, aba_dados)
                faixa, ref = _escrever_aba_waterfall(writer, aba_dados, aba_graf, cats_rv_j,
                                                     meses_dados_rv_j, n_meses_janela,
                                                     f"Ativo RV (desde {inicio})")
                if faixa:
                    specs.append((aba_graf, faixa, ref))

    print(f"[OK] Excel (dados + dropdowns) gerado: {caminho}")
    return caminho, specs


def _set_soft(obj, attr, val):
    try:
        setattr(obj, attr, val)
    except Exception:
        pass


def adicionar_waterfalls_nativos(caminho, specs):
    """Insere, numa única sessão do Excel, o gráfico Waterfall nativo de
    cada aba listada em `specs` (gerada por `_escrever_aba_waterfall`)."""
    if not specs:
        print("[AVISO] Nenhuma cascata para inserir (sem categorias em nenhuma aba).")
        return

    import pythoncom
    import win32com.client as win32

    pythoncom.CoInitialize()
    xl = None
    try:
        xl = win32.DispatchEx("Excel.Application")        # instância nova e isolada
        _set_soft(xl, "Visible", False)
        _set_soft(xl, "DisplayAlerts", False)

        wb = xl.Workbooks.Open(os.path.abspath(caminho))
        for aba, faixa, ref_titulo in specs:
            ws = wb.Worksheets(aba)
            ws.Activate()
            # Gráfico começa logo à direita da tabela auxiliar inteira (que
            # pode ter colunas extras fora da faixa, ex.: "Setor GICS").
            tabela = ws.Range(faixa).CurrentRegion
            esquerda = tabela.Left + tabela.Width + 12
            ws.Range(faixa).Select()                       # seleção prévia → auto-bind dos dados
            sh = ws.Shapes.AddChart2(-1, XL_WATERFALL, esquerda, 15, 640, 380)
            ch = sh.Chart
            ch.HasTitle = True
            ch.ChartTitle.Formula = ref_titulo             # título linkado à célula dinâmica
            ws.Range("B1").Select()

        wb.Save()
        wb.Close(SaveChanges=True)
        print(f"[OK] {len(specs)} waterfall(s) nativo(s) inserido(s).")
    except Exception as e:
        print(f"[AVISO] Não foi possível inserir os waterfalls nativos via Excel COM: {e}")
        print("        O arquivo com dados + dropdowns foi mantido (sem os gráficos).")
    finally:
        if xl is not None:
            try:
                xl.Quit()
            except Exception:
                pass


def main():
    fundo   = sys.argv[1] if len(sys.argv) > 1 else FUNDO_DEFAULT
    n_meses = int(sys.argv[2]) if len(sys.argv) > 2 else N_MESES_DEFAULT

    # A busca cobre, no mínimo, a mais antiga das JANELAS_PERFORMANCE — senão
    # a aba Historico_<ano>/RV_Hist_<ano> mais longa ficaria cortada mesmo
    # tendo dado de cota/RV disponível.
    if JANELAS_PERFORMANCE:
        n_meses = max(n_meses, meses_desde(min(JANELAS_PERFORMANCE)))

    meses = ultimos_meses(n_meses)
    todos_meses_labels = [m[0] for m in meses]     # inclui meses sem posição (ex.: antes de 2021)
    print(f"Fundo={fundo} | {n_meses} meses: {meses[0][0]} a {meses[-1][0]}")

    # Cota (fundo/benchmark) e Ibovespa costumam cobrir um histórico BEM maior
    # que a posição (ex.: VIEW_FUNDOS_COTAS_PL desde 2012, mas
    # VW_FUNDOS_POSICAO_EXPURGO só desde ~2021) — por isso são buscados numa
    # janela própria, independente de o fundo ter posição detalhada ou não.
    cotas_df = buscar_cotas_periodo(fundo, meses[0][1], meses[-1][2]) if INCLUIR_BENCHMARK else None
    ibov_df = buscar_ibov_periodo(meses[0][1], meses[-1][2]) if INCLUIR_IBOV else None
    rv_hist_df = buscar_rv_hist_periodo(fundo, meses[0][1], meses[-1][2]) if INCLUIR_RV_HIST else None

    dados = coletar_mensal(fundo, meses)
    meses_dados = [label for label, df in dados.items() if not df.empty]   # só meses com posição
    meses_validos = set(meses_dados)

    tem_cotas = cotas_df is not None and not cotas_df.empty
    tem_rv_hist = rv_hist_df is not None and not rv_hist_df.empty
    if not meses_dados and not tem_cotas and not tem_rv_hist:
        print("Nenhum mês retornou dados (nem posição, nem cota, nem RV histórico) — nada a exportar.")
        return
    if not meses_dados:
        print("[AVISO] Fundo sem posições no período pedido — Posição/Empresa/Setor tentarão "
              "se preencher via RV histórico (só cobre equity); Categoria/Fator de Risco/Ação "
              "dependem só de posição e ficarão vazias. O Histórico e/ou a aba RV (Histórico) "
              "ainda são montados a partir de fontes com período mais longo "
              "(cota / OT0_PERF_ATTRIB_RV_DADOS_GERAL).")

    mensal_posicao    = agregar_por(dados, "ativo")
    mensal_empresa    = agregar_por(dados, "ativo", filtro=lambda df: df["tipo"] == "Equity")
    mensal_setor      = agregar_por(dados, "setor")
    mensal_categoria  = agregar_por_categoria(dados, classificar_categoria)
    mensal_fator_risco = agregar_por(dados, "fator_risco")
    mensal_acao        = agregar_por(dados, "ticker", filtro=lambda df: df["tipo"] == "Equity")

    # RV (Histórico): fonte própria (OT0_PERF_ATTRIB_RV_DADOS_GERAL), por
    # ativo e por mês — usada abaixo tanto pra preencher Posição/Empresa/
    # Setor (buraco pré-posição) quanto, na direção oposta, preenchida pela
    # própria posição onde ELA tiver buraco (pós-2021/2023).
    mensal_rv_hist_full = agregar_rv_hist_mensal(rv_hist_df, todos_meses_labels)

    # Posição/Empresa/Setor "completos": preenchem o período sem posição
    # detalhada (ex.: 2012-2021) com o RV histórico — só cobre a parte de
    # equity do fundo (RV não tem renda fixa/outros ativos), mas é melhor
    # que ficar em branco. Setor precisa de uma classificação ticker->setor
    # pra reaproveitar o RV (que não traz setor) — ver montar_lookup_setor.
    lookup_setor = montar_lookup_setor(dados)
    mensal_rv_por_setor = agregar_rv_por_setor(mensal_rv_hist_full, lookup_setor)
    mensal_posicao_completo = mesclar_fallback_mensal(mensal_posicao, mensal_rv_hist_full, todos_meses_labels)
    mensal_empresa_completo = mesclar_fallback_mensal(mensal_empresa, mensal_rv_hist_full, todos_meses_labels)
    mensal_setor_completo   = mesclar_fallback_mensal(mensal_setor, mensal_rv_por_setor, todos_meses_labels)
    meses_dados_rv_qualquer = [l for l in todos_meses_labels if mensal_rv_hist_full.get(l)]
    meses_validos_completo = meses_validos | set(meses_dados_rv_qualquer)
    meses_dados_completo = [l for l in todos_meses_labels if l in meses_validos_completo]
    if len(meses_dados_completo) > len(meses_dados):
        print(f"[INFO] Posição/Empresa/Setor preenchidos com RV histórico onde não há posição "
              f"detalhada: {len(meses_dados_completo)} meses no total "
              f"(eram {len(meses_dados)} só com posição).")

    ordem_categoria = [nome for nome, _ in _REGRAS_CATEGORIA] + ["Other"]

    df_posicao,     cats_posicao     = montar_matriz(mensal_posicao_completo, meses_validos_completo)
    # Setor GICS de cada ativo da aba Waterfall_Posicao — classificação do
    # mês mais recente em que ele teve setor; sem nenhuma, "(Sem setor)".
    lookup_setor_atual = montar_lookup_setor(dados, mais_recente=True)
    setor_posicao = {ativo: lookup_setor_atual.get(ativo, "(Sem setor)") for ativo in cats_posicao}
    df_empresa,     cats_empresa     = montar_matriz(mensal_empresa_completo, meses_validos_completo)
    df_setor,       cats_setor       = montar_matriz(mensal_setor_completo, meses_validos_completo)
    df_categoria,   cats_categoria   = montar_matriz(mensal_categoria, meses_validos, ordem=ordem_categoria)
    df_fator_risco, cats_fator_risco = montar_matriz(mensal_fator_risco, meses_validos)
    df_acao,        cats_acao        = montar_matriz(mensal_acao, meses_validos)

    # RV (Histórico): preenche o buraco OPOSTO — meses pós-2021/2023 em que
    # o OT0_PERF_ATTRIB_RV_DADOS_GERAL já não é mais atualizado — com a
    # posição em Equity (mensal_empresa, não a versão "completa" acima, pra
    # não reintroduzir o próprio RV nele mesmo). 1 par de abas por
    # JANELA_PERFORMANCE, cada uma rebasada do zero no seu início.
    mensal_rv_hist_completo = mesclar_fallback_mensal(mensal_rv_hist_full, mensal_empresa, todos_meses_labels)
    rv_hists = []          # [(inicio, mensal_janela, df_rv, cats_rv, meses_dados_rv, n_meses_janela)]
    for inicio in JANELAS_PERFORMANCE:
        labels_janela = [l for l in todos_meses_labels if l >= inicio]
        mensal_janela = {k: v for k, v in mensal_rv_hist_completo.items() if k in labels_janela}
        meses_dados_rv_j = [l for l in labels_janela if mensal_janela.get(l)]
        df_rv_j, cats_rv_j = montar_matriz(mensal_janela, set(meses_dados_rv_j))
        rv_hists.append((inicio, mensal_janela, df_rv_j, cats_rv_j, meses_dados_rv_j, len(labels_janela)))
        if INCLUIR_RV_HIST and not meses_dados_rv_j:
            print(f"[INFO] Sem dados em OT0_PERF_ATTRIB_RV_DADOS_GERAL nem em posição (Equity) "
                  f"para este fundo desde {inicio} — aba 'Waterfall_RV_Hist_{_sufixo_janela(inicio)}' "
                  f"ficará só com um aviso.")
        elif INCLUIR_RV_HIST:
            print(f"[INFO] RV (Histórico) desde {inicio}: {meses_dados_rv_j[0]} a "
                  f"{meses_dados_rv_j[-1]} ({len(meses_dados_rv_j)} meses com dado, "
                  f"RV + posição Equity combinados).")

    # Histórico: idem, 1 aba por JANELA_PERFORMANCE, cada uma rebasada do zero.
    historicos = []        # [(inicio, df_historico)]
    nome_benchmark = None
    for inicio in JANELAS_PERFORMANCE:
        labels_janela = [l for l in todos_meses_labels if l >= inicio]
        df_h, nb = montar_historico(
            mensal_posicao, labels_janela, cotas_df, ibov_df,
            incluir_benchmark=INCLUIR_BENCHMARK, incluir_ibov=INCLUIR_IBOV,
            mensal_rv_hist=mensal_rv_hist_full,
        )
        historicos.append((inicio, df_h))
        nome_benchmark = nome_benchmark or nb
        if not INCLUIR_BENCHMARK:
            pass
        elif nb:
            print(f"[INFO] Benchmark do fundo (janela {inicio}): {nb}")
        elif df_h["retorno_benchmark_pct"].isna().all():
            print(f"[INFO] Sem cota de benchmark disponível desde {inicio} "
                  f"— Historico_{_sufixo_janela(inicio)} ficará sem essa linha.")
        if INCLUIR_IBOV and df_h["retorno_ibov_pct"].isna().all():
            print(f"[INFO] Sem cotação de Ibovespa disponível desde {inicio} "
                  f"— Historico_{_sufixo_janela(inicio)} ficará sem essa linha.")
    if not INCLUIR_BENCHMARK:
        print("[INFO] INCLUIR_BENCHMARK = False — histórico sem a linha do benchmark do fundo.")
    if not INCLUIR_IBOV:
        print("[INFO] INCLUIR_IBOV = False — histórico sem a linha do Ibovespa.")

    if not cats_empresa:
        print("[INFO] Fundo sem posições de Equity (renda variável) no período "
              "— aba 'Waterfall_Empresa' ficará só com um aviso.")
    if not cats_acao:
        print("[INFO] Fundo sem posições de Equity (renda variável) no período "
              "— aba 'Waterfall_Acao' ficará só com um aviso.")

    # Resumo MTD/QTD/YTD/12M/24M/36M/ITD — calculado direto da cota diária
    # (mais precisa que os agregados mensais), cobrindo desde que o fundo tem
    # cota disponível (não limitado pela posição). Uma tabela por mês de
    # referência disponível (recalculando tudo "como se hoje fosse" aquele
    # mês) — vira o dropdown de mês no HTML; o Excel usa só a última.
    cotas_df_ok = cotas_df if cotas_df is not None else pd.DataFrame()
    periodos_por_mes = {}   # {mes_label: df_periodos}
    if not cotas_df_ok.empty:
        for label, _, fim in meses:
            data_fim_mes = pd.Timestamp(fim)
            cotas_ate_mes = cotas_df_ok[cotas_df_ok["date"] <= data_fim_mes]
            if cotas_ate_mes.empty:
                continue
            ibov_ate_mes = (ibov_df[ibov_df["date"] <= data_fim_mes]
                            if ibov_df is not None and not ibov_df.empty else None)
            periodos_por_mes[label] = montar_tabela_periodos(cotas_ate_mes, ibov_ate_mes)

    df_periodos = list(periodos_por_mes.values())[-1] if periodos_por_mes else pd.DataFrame()
    if not df_periodos.empty:
        print(f"[INFO] Resumo de períodos ({len(periodos_por_mes)} meses de referência disponíveis "
              f"no dropdown do HTML): {', '.join(df_periodos['periodo'])}")

    # Calendário comparativo Fundo x Benchmark x Alpha (formato pedido, 3
    # linhas por ano) + calendário extra do Ibovespa (formato antigo, Ano x
    # Jan-Dez) isolado — o Ibovespa é travado pra não começar antes do fundo
    # (tem histórico bem mais longo — sem isso sobra um "ano" inicial
    # incompleto só nessa tabela).
    data_ini_fundo = cotas_df_ok["date"].min() if not cotas_df_ok.empty else None
    df_calendario_comparativo = montar_tabela_calendario_comparativo(fundo, cotas_df_ok, nome_benchmark)
    if not df_calendario_comparativo.empty:
        print(f"[INFO] Calendário comparativo Fundo x Benchmark x Alpha: "
              f"{df_calendario_comparativo['Ano'].nunique()} ano(s).")

    tabelas_mensais = [
        ("Retornos Mensais — Ibovespa",
         montar_tabela_mensal_anual(ibov_df, "preco_limpo", data_minima=data_ini_fundo)),
    ]
    tabelas_mensais = [(t, df) for t, df in tabelas_mensais if not df.empty]
    if tabelas_mensais:
        print(f"[INFO] Retornos mensais por ano (extra): {', '.join(t for t, _ in tabelas_mensais)}")

    caminho, specs = gerar_excel(fundo, meses, meses_dados,
                                 df_posicao, cats_posicao,
                                 df_empresa, cats_empresa,
                                 df_setor, cats_setor,
                                 df_categoria, cats_categoria,
                                 df_fator_risco, cats_fator_risco,
                                 df_acao, cats_acao,
                                 historicos, nome_benchmark,
                                 rv_hists, df_periodos, tabelas_mensais,
                                 df_calendario_comparativo, meses_dados_completo,
                                 setor_posicao=setor_posicao)
    sql_connection.disconnect()

    adicionar_waterfalls_nativos(caminho, specs)

    abas_visiveis = {
        "resumo": MOSTRAR_RESUMO, "historico": MOSTRAR_HISTORICO,
        "posicao": MOSTRAR_POSICAO, "empresa": MOSTRAR_EMPRESA, "setor": MOSTRAR_SETOR,
        "categoria": MOSTRAR_CATEGORIA, "fator_risco": MOSTRAR_FATOR_RISCO,
        "acao": MOSTRAR_ACAO, "rv_hist": MOSTRAR_RV_HIST,
    }
    caminho_html = html_report.gerar_html(
        fundo, meses, meses_dados, rotulo_mes,
        mensal_posicao_completo, df_posicao, cats_posicao,
        mensal_empresa_completo, df_empresa, cats_empresa,
        mensal_setor_completo, df_setor, cats_setor,
        mensal_categoria, df_categoria, cats_categoria,
        mensal_fator_risco, df_fator_risco, cats_fator_risco,
        mensal_acao, df_acao, cats_acao,
        historicos, nome_benchmark, OUTPUT_DIR,
        rv_hists=rv_hists, periodos_por_mes=periodos_por_mes, tabelas_mensais=tabelas_mensais,
        df_calendario_comparativo=df_calendario_comparativo, abas_visiveis=abas_visiveis,
        mostrar_coluna_bps_historico=MOSTRAR_COLUNA_BPS_HISTORICO,
        mostrar_grafico_barras_historico=MOSTRAR_GRAFICO_BARRAS_HISTORICO,
        meses_dados_completo=meses_dados_completo,
    )
    print(f"[OK] HTML gerado: {caminho_html}")


if __name__ == "__main__":
    main()