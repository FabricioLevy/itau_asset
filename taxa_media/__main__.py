# ─────────────────────────────────────────────
# taxa_media/__main__.py
# Taxa média de aquisição dos papéis de crédito atrelados ao CDI (CRI, debênture, CRA...) de uma lista de
# fundos: taxa de cada lote em aberto na custódia, média por ativo (ponderada pela quantidade) e da carteira
# (ponderada pelo financeiro atual).
#
# Entrada: input/fundos.xlsx (colunas S/N aceitam S, Sim, X ou 1)
#   Fundos      fundo (codigo_IAM_fundo) · rodar (S/N, vazio = S) · nome (livre)
#   Tipos       RFTP_CD da VCRAOPRF · incluir (S/N) · descricao. Tipo que aparece na VCRA e não está na aba vira
#               aviso e fica fora. As compromissadas ficam com N: LTN-O, NTN-O e LFT O são over do caixa; CRIOP e
#               CRILA usam o código do CRI de lastro e somariam a compromissada ao CRI comprado em definitivo.
#   Correções   fundo · CD (lote) · taxa · aplicar (S/N, vazio = S) · motivo. Taxa na convenção do grupo do ativo.
#
# Fontes (DBSX337 pelo sql_connection.py desta pasta, credenciais SQL_LOGIN e SQL_PASSWORD; todas as
# leituras WITH (NOLOCK)):
#   VCRAOPRF              custódia de renda fixa, uma linha por movimento de cada lote (CD). Trades = SG_OPERACAO
#                         C/V (M, J e I são eventos).
#   FUNDOS_OPERACOES      boleta do front: exec_taxa = taxa negociada (CDI+: spread % a.a.; %CDI: % do CDI).
#   VW_FUNDOS_POSICAO     quantidade na data (conferência) e PU da última data com preço (total/quantidade).
#   FUNDOS_DADOS_INDICES  CDIAcumulado: CDI do dia, só para converter %CDI em CDI+ equivalente.
#
# Cálculo (por fundo):
#   escopo    tipos com incluir = S e indexador CDI (IDDIR_CD começando com CDI). IPCA, pré e SELIC ficam fora,
#             com aviso: o cálculo só junta CDI+ e %CDI.
#   lote      qtd em aberto = compras - vendas do mesmo CD. Lote com sufixo A (ex.: L10947A) é relançamento
#             da VCRA (venda do original + compra um dia depois no mesmo PU) e já sai certo nessa conta.
#   boleta    cada compra casa com a boleta do mesmo ativo em até 5 dias, pela quantidade ou pelo PU (há
#             boletas com o dobro da quantidade da custódia); prefere a quantidade e a data mais próxima.
#   grupo     CDI+ se o ativo tem spread de emissão (VL_JUROS_EMISSAO > 0); senão %CDI, com a emissão no
#             IDDIR_PC. O indexador da VW_FUNDOS_POSICAO classifica errado alguns papéis.
#   taxa      %CDI: só a boleta — a VCRA grava %CDI como IDDIR_PC + spread, e isso não converte de forma
#             consistente para o % do CDI da boleta. CDI+: a boleta (--fonte boleta, padrão) ou a VCRA, que
#             sai do PU pago (--fonte vcra); sem boleta válida, a VCRA.
#             Boleta válida: %CDI >= 50 (% do CDI), CDI+ < 50 (spread). Lote sem taxa fica fora da média do
#             ativo; a aba Correções corrige a taxa de lotes específicos.
#   ativo     média das taxas dos lotes, ponderada pela quantidade em aberto.
#   carteira  média ponderada pelo financeiro (qtd x último PU), por grupo e no total. O total junta os grupos
#             em CDI+ equivalente, com CDI flat: spread = (1 + %CDI x CDI diário)^252 / (1 + CDI) - 1.
#
# Saída: output/taxa_media_<aaaammdd>.xlsx (com um fundo só, taxa_media_<fundo>_<aaaammdd>.xlsx) — abas
#   Carteira, Ativos, Lotes, Avisos, Fundos e Parâmetros, com a coluna Fundo. Erro num fundo não para os
#   outros: o fundo sai na aba Fundos com o erro.
#
# Requisitos: ODBC Driver 18 for SQL Server, pyodbc, sqlalchemy, pandas, openpyxl.
#
# Uso (de dentro de taxa_media/, ou "python taxa_media" a partir de itau_asset/):
#   python __main__.py                          (fundos da aba Fundos, cada um na última data da posição)
#   python __main__.py --data 23/10/2026
#   python __main__.py --fundo ITAIMOBCDIFII    (só esse fundo; tipos e correções continuam vindo do Excel)
#   python __main__.py --fonte vcra --cdi 13.65
# ─────────────────────────────────────────────

import argparse
import os
import re
import sys
import unicodedata
from datetime import datetime

import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA_DIR = os.path.join(AQUI, "output")
ENTRADA_PADRAO = os.path.join(AQUI, "input", "fundos.xlsx")

# tipos da VCRAOPRF quando o Excel não tem a aba Tipos (True = entra no cálculo)
TIPOS_PADRAO = {"CRI-I": True, "LTN-O": False, "NTN-O": False, "LFT O": False, "CRIOP": False, "CRILA": False}
JANELA_BOLETA = 5       # dias entre a compra na VCRA e a data da boleta
TOLERANCIA_PU = 1e-4    # PU da boleta x PU da VCRA, para casar quando a quantidade não bate
LIMITE_CONVENCAO = 50   # boleta de %CDI vem em % do CDI (>= 50); de CDI+, em spread % a.a. (< 50)
DIAS_PU = 30            # até quantos dias antes da data procurar o último PU com preço na posição
# boleta x VCRA na convenção do grupo acima disso vira aviso: CDI+ em p.p. de spread; %CDI em pontos de % do
# CDI (convertida com CDI flat, a VCRA costuma ficar até ~1,5 ponto abaixo da boleta)
DIVERGENCIA = {"CDI+": 0.25, "%CDI": 3.0}
# ordem dos avisos no console e na aba Avisos ("Correção manual" sai como [INFO])
ORDEM_AVISOS = ["Quantidade", "Sem lote", "Fora do escopo", "Tipo novo", "Fora da média", "Média parcial",
                "Boleta inválida", "Sem boleta", "Correção manual", "Correção não aplicada", "Boleta × VCRA",
                "Venda sem compra", "Lote negativo"]


# ── Entrada (input/fundos.xlsx) ──────────────────────────────────────────────
def _chave(texto):
    """Nome de aba ou de coluna sem acento, sem espaços nas pontas e em minúsculas."""
    return unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().strip().lower()


def _sim(valor, padrao=False):
    if pd.isna(valor) or not str(valor).strip():
        return padrao
    return str(valor).strip().upper() in ("S", "SIM", "X", "1")


def _texto(valor):
    return "" if pd.isna(valor) else str(valor).strip()


def _numero(texto):
    texto = str(texto).strip()
    return float(texto.replace(".", "").replace(",", ".") if "," in texto else texto)


def _aba(abas, nome, colunas, caminho):
    """Aba do Excel com as colunas pedidas (nomes sem acento e minúsculos); None se a aba não existir."""
    df = abas.get(_chave(nome))
    if df is None:
        return None
    df = df.rename(columns=_chave)
    faltam = [c for c in colunas if c not in df.columns]
    if faltam:
        raise ValueError(f"{caminho}, aba {nome}: faltam as colunas {faltam}")
    return df.dropna(how="all")


def carregar_entrada(caminho):
    """input/fundos.xlsx -> (fundos [(fundo, nome)], tipos {RFTP_CD: incluir}, correções {fundo: {CD: (taxa,
    motivo)}}). Sem a aba Tipos vale TIPOS_PADRAO; sem a aba Correções, nenhuma correção."""
    abas = {_chave(nome): df for nome, df in pd.read_excel(caminho, sheet_name=None, dtype=str).items()}

    fundos = []
    df = _aba(abas, "Fundos", ["fundo"], caminho)
    for i, r in ([] if df is None else df.iterrows()):
        fundo = _texto(r["fundo"])
        if not fundo or not _sim(r.get("rodar"), padrao=True) or fundo in dict(fundos):
            continue
        if not re.fullmatch(r"\w+", fundo):
            raise ValueError(f"{caminho}, aba Fundos, linha {i + 2}: código de fundo inválido {fundo!r}")
        fundos.append((fundo, _texto(r.get("nome"))))

    df = _aba(abas, "Tipos", ["rftp_cd", "incluir"], caminho)
    tipos = dict(TIPOS_PADRAO) if df is None else {
        _texto(r["rftp_cd"]).upper(): _sim(r["incluir"]) for _, r in df.iterrows() if _texto(r["rftp_cd"])}

    correcoes = {}
    df = _aba(abas, "Correções", ["fundo", "cd", "taxa"], caminho)
    for i, r in ([] if df is None else df.iterrows()):
        if not _sim(r.get("aplicar"), padrao=True):
            continue
        linha = f"{caminho}, aba Correções, linha {i + 2}"
        if not (_texto(r["fundo"]) and _texto(r["cd"]) and _texto(r["taxa"])):
            raise ValueError(f"{linha}: precisa de fundo, CD e taxa")
        try:
            taxa = _numero(r["taxa"])
        except ValueError:
            raise ValueError(f"{linha}: taxa inválida {r['taxa']!r}") from None
        correcoes.setdefault(_texto(r["fundo"]), {})[_texto(r["cd"])] = (taxa, _texto(r.get("motivo")))
    return fundos, tipos, correcoes


# ── SQL ──────────────────────────────────────────────────────────────────────
SQL_ULTIMA_DATA = """
SELECT MAX(date) AS data
FROM   VW_FUNDOS_POSICAO WITH (NOLOCK)
WHERE  codigo_IAM_fundo = '{fundo}'
"""

SQL_VCRA = """
SELECT  CD, CD_CETIP_SELIC AS codigo, ISIN AS isin, RFTP_CD AS tipo, IDDIR_CD AS indexador, DT AS data,
        SG_OPERACAO AS op, QT AS qt, VL_PU_OPERACAO AS pu, IDDIR_PC AS perc_cdi,
        VL_JUROS_EMISSAO AS taxa_emissao, VL_JUROSOPER AS taxa_vcra
FROM    VCRAOPRF WITH (NOLOCK)
WHERE   CLCLI_CD = '{fundo}' AND DT <= '{data}' AND SG_OPERACAO IN ('C', 'V')
"""

SQL_BOLETAS = """
SELECT  codigo_IAM_ativo AS codigo, date_operacao AS data, exec_qt AS qt, exec_preco AS pu,
        exec_taxa AS taxa
FROM    FUNDOS_OPERACOES WITH (NOLOCK)
WHERE   codigo_IAM_fundo = '{fundo}'
  AND   date_operacao <= DATEADD(day, {janela}, '{data}')
  AND   codigo_IAM_ativo IN ({codigos})
"""

SQL_POSICAO = """
SELECT  codigo_IAM_ativo AS codigo, isin, date AS data, quantidade, total
FROM    VW_FUNDOS_POSICAO WITH (NOLOCK)
WHERE   codigo_IAM_fundo = '{fundo}' AND tipo = 'Fixed Income'
  AND   date BETWEEN DATEADD(day, -{dias}, '{data}') AND '{data}'
"""

SQL_CDI = """
SELECT TOP 1 date AS data, pnl_perc
FROM   FUNDOS_DADOS_INDICES WITH (NOLOCK)
WHERE  codigo_IAM_indice = 'CDIAcumulado' AND date <= '{data}' AND pnl_perc > 0
ORDER BY date DESC
"""


def _consulta(query, sql, nome, obrigatoria=True):
    """SELECT pelo sql_connection.query, que devolve DataFrame vazio também quando a consulta dá erro
    (e imprime a mensagem)."""
    df = query(sql)
    if df.empty and obrigatoria:
        raise RuntimeError(f"{nome}: nenhuma linha (ou erro na consulta: veja a mensagem acima)")
    return df


def _lista_sql(valores):
    return ", ".join("'" + str(v).replace("'", "''") + "'" for v in valores)


def carregar_fundo(query, fundo, data, tipos):
    """VCRA (todos os tipos), boletas dos ativos dos tipos incluídos e posição de um fundo. data None = última
    data da posição do fundo."""
    if data is None:
        ultima = _consulta(query, SQL_ULTIMA_DATA.format(fundo=fundo), "VW_FUNDOS_POSICAO")["data"].iloc[0]
        if pd.isna(ultima):
            raise RuntimeError("sem posição na VW_FUNDOS_POSICAO")
        data = pd.Timestamp(ultima).date()
    p = {"fundo": fundo, "data": f"{data:%Y-%m-%d}", "janela": JANELA_BOLETA, "dias": DIAS_PU}
    vcra = _consulta(query, SQL_VCRA.format(**p), f"VCRAOPRF (até {data:%d/%m/%Y})")
    incluidos = vcra["tipo"].str.strip().str.upper().map(lambda t: tipos.get(t, False)).astype(bool)
    codigos = sorted(vcra.loc[incluidos, "codigo"].dropna().str.strip().unique())
    boletas = pd.DataFrame()
    if codigos:
        boletas = _consulta(query, SQL_BOLETAS.format(codigos=_lista_sql(codigos), **p), "FUNDOS_OPERACOES",
                            obrigatoria=False)
    posicao = _consulta(query, SQL_POSICAO.format(**p), "VW_FUNDOS_POSICAO")
    if not (pd.to_datetime(posicao["data"]).dt.normalize() == pd.Timestamp(data)).any():
        raise RuntimeError(f"sem posição em {data:%d/%m/%Y} na VW_FUNDOS_POSICAO")
    return {"vcra": vcra, "boletas": boletas, "posicao": posicao, "data": data}


def carregar_cdi(query, data):
    """CDI a.a. (fração) do CDIAcumulado no último dia até a data, e de onde ele veio."""
    linha = _consulta(query, SQL_CDI.format(data=f"{data:%Y-%m-%d}"), "FUNDOS_DADOS_INDICES (CDIAcumulado)").iloc[0]
    cdi = (1 + float(linha["pnl_perc"])) ** 252 - 1
    if not 0.01 < cdi < 0.5:
        raise RuntimeError(f"CDI de {cdi:.2%} a.a. no CDIAcumulado fora do esperado: informe com --cdi")
    return cdi, f"CDIAcumulado da FUNDOS_DADOS_INDICES em {pd.Timestamp(linha['data']):%d/%m/%Y}"


# ── Cálculo ──────────────────────────────────────────────────────────────────
def _br(x, casas=2):
    """Número no formato brasileiro (1.234,56)."""
    return f"{x:,.{casas}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _cdi_mais(x):
    return f"CDI{'+' if x >= 0 else '−'}{_br(abs(x))}"


def _aviso(avisos, aviso, ativo, detalhe, lote=""):
    avisos.append({"aviso": aviso, "ativo": ativo, "lote": lote, "detalhe": detalhe})


def _normalizar(df, textos=(), datas=(), numeros=()):
    df = df.copy()
    for c in textos:
        df[c] = df[c].str.strip()
    for c in datas:
        df[c] = pd.to_datetime(df[c]).dt.normalize()
    for c in numeros:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _media_ponderada(df, chave, valor, peso):
    """Média de valor ponderada por peso em cada grupo de chave, só com as linhas que têm valor."""
    ok = df[valor].notna()
    s = df.assign(_v=(df[valor] * df[peso]).where(ok, 0.0), _p=df[peso].where(ok, 0.0)).groupby(chave)[["_v", "_p"]].sum()
    return s["_v"] / s["_p"].replace(0, np.nan)


def filtrar_escopo(vcra, tipos, avisos):
    """Movimentos que entram no cálculo: tipo com incluir = S e indexador CDI. Devolve (VCRA no escopo,
    {codigo: motivo} dos ativos que ficaram fora, para explicar quem está na posição sem lote)."""
    tipo = vcra["tipo"].fillna("").str.upper()
    novos = vcra[~tipo.isin(list(tipos))]
    for t, g in novos.groupby(tipo.loc[novos.index]):
        indexadores = ", ".join(sorted(g["indexador"].dropna().unique())) or "sem indexador"
        _aviso(avisos, "Tipo novo", "", f"RFTP_CD {t or '(vazio)'} ({indexadores}; {len(g)} movimento"
               f"{'s' if len(g) > 1 else ''}) não está na aba Tipos: ficou fora")
    incluido = tipo.map(lambda t: tipos.get(t, False)).astype(bool)
    cdi = vcra["indexador"].fillna("").str.upper().str.startswith("CDI")
    fora = {}
    for r in vcra[~incluido].itertuples():
        fora.setdefault(r.codigo, f"na VCRA como {r.tipo or '(vazio)'}, tipo fora do cálculo")
    for codigo, g in vcra[incluido & ~cdi].groupby("codigo"):
        indexadores = ", ".join(sorted(g["indexador"].dropna().unique())) or "vazio"
        fora[codigo] = f"indexador {indexadores}: só entram papéis atrelados ao CDI"
    return vcra[incluido & cdi], fora


def casar_boletas(compras, boletas):
    """Acrescenta a cada compra da VCRA a boleta do mesmo ativo em até JANELA_BOLETA dias com a mesma
    quantidade ou o mesmo PU; prefere a quantidade e, depois, a data mais próxima."""
    novas = ["data_boleta", "qt_boleta", "taxa_boleta", "casou_por"]
    if boletas.empty:
        return compras.assign(**{c: np.nan for c in novas})
    b = boletas.rename(columns={"data": "data_boleta", "qt": "qt_boleta", "pu": "pu_boleta", "taxa": "taxa_boleta"})
    m = compras[["codigo", "data", "qt", "pu"]].reset_index().merge(b, on="codigo")
    mesma_qt = np.isclose(m["qt_boleta"].abs(), m["qt"], rtol=0, atol=1e-6)
    mesmo_pu = ((m["pu_boleta"] - m["pu"]).abs() < TOLERANCIA_PU).to_numpy()
    m["dias"] = (m["data_boleta"] - m["data"]).dt.days.abs()
    m["prioridade"] = np.where(mesma_qt, 0, 1)
    m["casou_por"] = np.where(mesma_qt, "quantidade", "PU")
    m = m[(m["dias"].to_numpy() <= JANELA_BOLETA) & (mesma_qt | mesmo_pu)]
    m = m.sort_values(["index", "prioridade", "dias"]).drop_duplicates("index").set_index("index")
    return compras.join(m[novas])


def montar_lotes(vcra, boletas, fonte, correcoes, cdi_d, avisos):
    """Lotes em aberto da VCRA (compras - vendas do mesmo CD) com a boleta casada, o grupo e a taxa usada."""
    compras = casar_boletas(vcra[vcra["op"] == "C"].reset_index(drop=True), boletas)
    vendas = vcra[vcra["op"] == "V"].groupby("CD")["qt"].sum()

    chave = ["codigo", "CD"]
    lotes = compras.groupby(chave).agg(
        isin=("isin", "first"), tipo=("tipo", "first"), indexador=("indexador", "first"), dt_compra=("data", "min"),
        perc_cdi=("perc_cdi", "max"), taxa_emissao=("taxa_emissao", "max"), qt_comprada=("qt", "sum"),
        data_boleta=("data_boleta", "min"), casou_por=("casou_por", "first"))
    for coluna, nome in (("pu", "pu_compra"), ("taxa_vcra", "taxa_vcra"), ("taxa_boleta", "taxa_boleta")):
        lotes[nome] = _media_ponderada(compras, chave, coluna, "qt")
    lotes = lotes.reset_index()
    lotes["qt_vendida"] = lotes["CD"].map(vendas).fillna(0.0)
    lotes["qt_aberta"] = lotes["qt_comprada"] - lotes["qt_vendida"]

    for cd in sorted(set(vendas.index) - set(lotes["CD"])):
        v = vcra[(vcra["op"] == "V") & (vcra["CD"] == cd)]
        _aviso(avisos, "Venda sem compra", v["codigo"].iloc[0],
               f"venda de {_br(v['qt'].sum(), 0)} sem a compra do lote no histórico da VCRA", cd)
    for r in lotes[lotes["qt_aberta"] < 0].itertuples():
        _aviso(avisos, "Lote negativo", r.codigo,
               f"vendas ({_br(r.qt_vendida, 0)}) maiores que as compras ({_br(r.qt_comprada, 0)})", r.CD)

    # CDI+ tem spread de emissão; %CDI tem a emissão no IDDIR_PC (o mesmo grupo em todos os lotes do ativo)
    lotes["grupo"] = np.where(lotes.groupby("codigo")["taxa_emissao"].transform("max") > 0, "CDI+", "%CDI")
    cdi_mais = lotes["grupo"] == "CDI+"
    lotes["boleta_ok"] = np.where(cdi_mais, lotes["taxa_boleta"] < LIMITE_CONVENCAO,
                                  lotes["taxa_boleta"] >= LIMITE_CONVENCAO)
    usa_boleta = lotes["boleta_ok"] & (~cdi_mais | (fonte == "boleta"))
    lotes["taxa"] = np.where(usa_boleta, lotes["taxa_boleta"], np.where(cdi_mais, lotes["taxa_vcra"], np.nan))
    lotes["fonte_taxa"] = np.where(usa_boleta, "boleta", np.where(cdi_mais, "VCRA", ""))

    # VCRA na convenção do grupo, para comparar com a boleta: no %CDI, o % do CDI que rende o mesmo que
    # IDDIR_PC% do CDI + o spread da VCRA, com CDI flat
    p, s = lotes["perc_cdi"] / 100, lotes["taxa_vcra"] / 100
    lotes["taxa_vcra_conv"] = np.where(cdi_mais, lotes["taxa_vcra"],
                                       ((1 + p * cdi_d) * (1 + s) ** (1 / 252) - 1) / cdi_d * 100)
    lotes["dif_boleta_vcra"] = (lotes["taxa_boleta"] - lotes["taxa_vcra_conv"]).where(lotes["boleta_ok"])

    for cd, (taxa, motivo) in correcoes.items():
        sel = (lotes["CD"] == cd) & (lotes["qt_aberta"] > 0)
        if not sel.any():
            _aviso(avisos, "Correção não aplicada", "", "o lote não está entre os lotes em aberto do fundo", cd)
            continue
        lotes.loc[sel, "taxa"] = taxa
        lotes.loc[sel, "fonte_taxa"] = "manual"

    abertos = lotes[lotes["qt_aberta"] > 0].reset_index(drop=True)
    consequencia = {"boleta": "", "VCRA": "usada a taxa da VCRA", "manual": "usada a correção manual",
                    "": "lote sem taxa, fora da média do ativo"}
    for r in abertos.itertuples():
        if pd.isna(r.taxa_boleta):
            _aviso(avisos, "Sem boleta", r.codigo, f"nenhuma boleta casada: {consequencia[r.fonte_taxa]}", r.CD)
        elif not r.boleta_ok:
            _aviso(avisos, "Boleta inválida", r.codigo, f"boleta com {_br(r.taxa_boleta, 4)} fora da convenção "
                   f"do {r.grupo}: {consequencia[r.fonte_taxa]}", r.CD)
        elif abs(r.dif_boleta_vcra) > DIVERGENCIA[r.grupo]:
            _aviso(avisos, "Boleta × VCRA", r.codigo, f"boleta {_br(r.taxa_boleta)} × VCRA {_br(r.taxa_vcra_conv)} "
                   f"(PU {_br(r.pu_compra)}); vale a {'correção manual' if r.fonte_taxa == 'manual' else r.fonte_taxa}",
                   r.CD)
        if r.fonte_taxa == "manual":
            _aviso(avisos, "Correção manual", r.codigo, f"taxa {_br(r.taxa, 4)} ({correcoes[r.CD][1]})", r.CD)
    return abertos


def montar_ativos(lotes, posicao, data, cdi, cdi_d, fora, avisos):
    """Taxa média por ativo (lotes ponderados pela quantidade), conferência com a quantidade da posição e
    financeiro pelo último PU com preço. fora: {codigo: motivo} dos ativos fora do escopo."""
    l = lotes.assign(sem_boleta=~lotes["boleta_ok"], manual=lotes["fonte_taxa"] == "manual",
                     sem_taxa=lotes["taxa"].isna())
    a = l.groupby("codigo").agg(
        isin=("isin", "first"), tipo=("tipo", "first"), grupo=("grupo", "first"), perc_cdi=("perc_cdi", "max"),
        taxa_emissao=("taxa_emissao", "max"), n_lotes=("CD", "count"), n_sem_boleta=("sem_boleta", "sum"),
        n_manual=("manual", "sum"), n_sem_taxa=("sem_taxa", "sum"), qt_lotes=("qt_aberta", "sum"))
    a["taxa_vcra"] = _media_ponderada(l, "codigo", "taxa_vcra_conv", "qt_aberta")
    a["taxa_media"] = _media_ponderada(l, "codigo", "taxa", "qt_aberta")

    ref = pd.Timestamp(data)
    na_data = posicao[(posicao["data"] == ref) & posicao["isin"].notna()]
    a = a.join(na_data.groupby("codigo")["quantidade"].sum().rename("qt_posicao"), how="outer")
    a["isin"] = a["isin"].fillna(na_data.groupby("codigo")["isin"].first())
    precos = (posicao[posicao["total"].notna()].groupby(["codigo", "data"])[["quantidade", "total"]].sum()
              .reset_index().sort_values("data").groupby("codigo").tail(1).set_index("codigo"))
    a["pu"] = (precos["total"] / precos["quantidade"].replace(0, np.nan)).reindex(a.index)
    a["dt_pu"] = precos["data"].reindex(a.index)
    a["dif_qt"] = a["qt_lotes"].fillna(0) - a["qt_posicao"].fillna(0)
    a["financeiro"] = a["qt_lotes"] * a["pu"]
    q = a["taxa_media"] / 100
    a["taxa_cdi_mais"] = np.where(a["grupo"] == "CDI+", a["taxa_media"],
                                  ((1 + q * cdi_d) ** 252 / (1 + cdi) - 1) * 100)
    a = a.rename_axis("codigo").reset_index().sort_values(["grupo", "codigo"], na_position="last")

    for r in a.itertuples():
        if pd.isna(r.qt_lotes):
            if r.codigo in fora:
                _aviso(avisos, "Fora do escopo", r.codigo, f"{_br(r.qt_posicao, 0)} na posição; {fora[r.codigo]}")
            else:
                _aviso(avisos, "Sem lote", r.codigo, f"{_br(r.qt_posicao, 0)} na posição sem lote em aberto na VCRA")
            continue
        if abs(r.dif_qt) > 1e-6:
            pos = _br(r.qt_posicao, 0) if pd.notna(r.qt_posicao) else "nada"
            _aviso(avisos, "Quantidade", r.codigo, f"lotes {_br(r.qt_lotes, 0)} × posição {pos} em {ref:%d/%m/%Y}")
        if pd.isna(r.taxa_media):
            _aviso(avisos, "Fora da média", r.codigo, "nenhum lote com taxa")
        elif r.n_sem_taxa:
            _aviso(avisos, "Média parcial", r.codigo,
                   f"{int(r.n_sem_taxa)} de {int(r.n_lotes)} lotes sem taxa: média só dos outros")
        if pd.isna(r.pu):
            _aviso(avisos, "Fora da média", r.codigo, f"sem PU na posição nos {DIAS_PU} dias até {ref:%d/%m/%Y}")
    return a.reset_index(drop=True)


def _resumo(grupo, g):
    fin = g["financeiro"].sum()
    return {"grupo": grupo, "n_ativos": len(g), "financeiro": fin,
            "taxa_media": (g["financeiro"] * g["taxa_media"]).sum() / fin,
            "taxa_cdi_mais": (g["financeiro"] * g["taxa_cdi_mais"]).sum() / fin}


def consolidar(ativos):
    """Média por grupo (na unidade do grupo) e da carteira (em CDI+ equivalente), ponderadas pelo financeiro."""
    ok = ativos[ativos["financeiro"].notna() & ativos["taxa_media"].notna()]
    linhas = [_resumo(grupo, g) for grupo, g in ok.groupby("grupo")]
    if len(ok):
        linhas.append({**_resumo("CARTEIRA", ok), "taxa_media": np.nan})
    return pd.DataFrame(linhas, columns=["grupo", "n_ativos", "financeiro", "taxa_media", "taxa_cdi_mais"])


def calcular(vcra, boletas, posicao, data, cdi, fonte, correcoes, tipos):
    """Um fundo -> (lotes em aberto, ativos, carteira, avisos). cdi = CDI a.a. em fração; fonte = 'boleta' ou
    'vcra'; correcoes = {CD: (taxa, motivo)}; tipos = {RFTP_CD: incluir}."""
    vcra = _normalizar(vcra, textos=("CD", "codigo", "op", "isin", "tipo", "indexador"), datas=("data",),
                       numeros=("qt", "pu", "perc_cdi", "taxa_emissao", "taxa_vcra"))
    vcra["qt"] = vcra["qt"].abs()
    if not boletas.empty:
        boletas = _normalizar(boletas, textos=("codigo",), datas=("data",), numeros=("qt", "pu", "taxa"))
    posicao = _normalizar(posicao, textos=("codigo", "isin"), datas=("data",), numeros=("quantidade", "total"))

    avisos = []
    cdi_d = (1 + cdi) ** (1 / 252) - 1
    vcra, fora = filtrar_escopo(vcra, tipos, avisos)
    lotes = montar_lotes(vcra, boletas, fonte, correcoes, cdi_d, avisos)
    ativos = montar_ativos(lotes, posicao, data, cdi, cdi_d, fora, avisos)
    avisos.sort(key=lambda av: ORDEM_AVISOS.index(av["aviso"]))
    return lotes, ativos, consolidar(ativos), avisos


# ── Saída ────────────────────────────────────────────────────────────────────
TAXA, PU, QTD, VALOR, DATA = "0.0000", "#,##0.000000", "#,##0", "#,##0.00", "dd/mm/yyyy"
FUNDO = ("fundo", "Fundo", None)
COLUNAS = {
    "Carteira": [FUNDO, ("data", "Data", DATA), ("grupo", "Grupo", None), ("n_ativos", "Ativos", "0"),
                 ("financeiro", "Financeiro (R$)", VALOR),
                 ("taxa_media", "Taxa média (CDI+: spread; %CDI: % do CDI)", TAXA),
                 ("taxa_cdi_mais", "Taxa média em CDI+ equivalente", TAXA)],
    "Ativos": [FUNDO, ("codigo", "Ativo", None), ("isin", "ISIN", None), ("tipo", "Tipo (RFTP_CD)", None),
               ("grupo", "Grupo", None), ("perc_cdi", "% do CDI (emissão)", TAXA),
               ("taxa_emissao", "Spread de emissão", TAXA), ("n_lotes", "Lotes", "0"),
               ("n_sem_boleta", "Lotes sem boleta válida", "0"), ("n_manual", "Lotes corrigidos", "0"),
               ("qt_lotes", "Qtd nos lotes", QTD), ("qt_posicao", "Qtd na posição", QTD), ("dif_qt", "Diferença", QTD),
               ("taxa_vcra", "Taxa média VCRA (convenção do grupo)", TAXA), ("taxa_media", "Taxa média", TAXA),
               ("taxa_cdi_mais", "Taxa média em CDI+ equivalente", TAXA), ("pu", "PU", PU),
               ("dt_pu", "Data do PU", DATA), ("financeiro", "Financeiro (R$)", VALOR)],
    "Lotes": [FUNDO, ("codigo", "Ativo", None), ("isin", "ISIN", None), ("tipo", "Tipo (RFTP_CD)", None),
              ("indexador", "Indexador", None), ("grupo", "Grupo", None), ("CD", "Lote", None),
              ("dt_compra", "Compra", DATA), ("qt_comprada", "Qtd comprada", QTD), ("qt_vendida", "Qtd vendida", QTD),
              ("qt_aberta", "Qtd em aberto", QTD), ("pu_compra", "PU de compra", PU),
              ("perc_cdi", "% do CDI (emissão)", TAXA), ("taxa_emissao", "Spread de emissão", TAXA),
              ("taxa_vcra", "Taxa VCRA (bruta)", TAXA), ("taxa_vcra_conv", "Taxa VCRA (convenção do grupo)", TAXA),
              ("data_boleta", "Data da boleta", DATA), ("casou_por", "Boleta casou por", None),
              ("taxa_boleta", "Taxa da boleta", TAXA), ("boleta_ok", "Boleta válida", None),
              ("dif_boleta_vcra", "Boleta − VCRA", TAXA), ("taxa", "Taxa usada", TAXA),
              ("fonte_taxa", "Fonte da taxa", None)],
    "Avisos": [FUNDO, ("aviso", "Aviso", None), ("ativo", "Ativo", None), ("lote", "Lote", None),
               ("detalhe", "Detalhe", None)],
    "Fundos": [FUNDO, ("nome", "Nome", None), ("data", "Data", DATA), ("status", "Status", None),
               ("taxa_carteira", "Carteira em CDI+ equivalente", TAXA), ("financeiro", "Financeiro (R$)", VALOR),
               ("n_lotes", "Lotes em aberto", "0"), ("n_ativos", "Ativos", "0"), ("n_avisos", "Avisos", "0"),
               ("cdi", "CDI (% a.a.)", TAXA), ("cdi_origem", "Origem do CDI", None)],
    "Parâmetros": [("parametro", "Parâmetro", None), ("valor", "Valor", None)],
}


def salvar_xlsx(caminho, tabelas, notas):
    """tabelas: {aba: DataFrame} com as abas de COLUNAS; as notas vão embaixo da aba Carteira."""
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    with pd.ExcelWriter(caminho, engine="openpyxl") as xw:
        for aba, colunas in COLUNAS.items():
            df = tabelas[aba].reindex(columns=[c for c, _, _ in colunas])
            df.rename(columns={c: t for c, t, _ in colunas}).to_excel(xw, sheet_name=aba, index=False)
            ws = xw.book[aba]
            ws.freeze_panes = "B2"
            for j, (c, titulo, fmt) in enumerate(colunas, start=1):
                ws.cell(row=1, column=j).font = Font(bold=True)
                largura = 14 if fmt else max([len(str(v)) for v in df[c].dropna()] + [0])
                ws.column_dimensions[get_column_letter(j)].width = min(max(len(titulo), largura) + 2, 90)
                if fmt:
                    for (cel,) in ws.iter_rows(min_row=2, min_col=j, max_col=j):
                        cel.number_format = fmt
        ws = xw.book["Carteira"]
        ws.append([])
        for nota in notas:
            ws.append([nota])


def imprimir_fundo(lotes, ativos, carteira, avisos, data, cdi):
    print(f"[INFO] {len(lotes)} lotes em aberto em {lotes['codigo'].nunique()} ativos | boleta casada em "
          f"{lotes['taxa_boleta'].notna().sum()} ({(lotes['casou_por'] == 'PU').sum()} pelo PU)")
    if len(lotes) and (ativos["dif_qt"].abs() <= 1e-6).all():
        print(f"[OK] quantidade dos lotes = posição de {data:%d/%m/%Y} nos {len(ativos)} ativos")
    for av in avisos:
        alvo = " ".join(x for x in (av["ativo"], f"({av['lote']})" if av["lote"] else "") if x)
        print(f"[{'INFO' if av['aviso'] == 'Correção manual' else 'AVISO'}] {av['aviso']}"
              f"{f' — {alvo}' if alvo else ''}: {av['detalhe']}")
    for r in carteira.itertuples():
        if r.grupo == "%CDI":
            taxa = f"{_br(r.taxa_media)}% do CDI ({_cdi_mais(r.taxa_cdi_mais)} equivalente)"
        elif r.grupo == "CDI+":
            taxa = _cdi_mais(r.taxa_media)
        else:
            taxa = f"{_cdi_mais(r.taxa_cdi_mais)} (%CDI convertido com CDI de {_br(cdi * 100)}% a.a.)"
        nome = "Carteira" if r.grupo == "CARTEIRA" else r.grupo
        print(f"[OK] {nome}: {r.n_ativos} ativos, R$ {_br(r.financeiro, 0)} — {taxa}")


def _data(s):
    return datetime.strptime(s, "%d/%m/%Y").date()


def main(argv=None):
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa
            pass

    ap = argparse.ArgumentParser(description="Taxa média de aquisição dos papéis de crédito atrelados ao CDI de uma "
                                             "lista de fundos: lotes da VCRAOPRF, taxa da boleta (FUNDOS_OPERACOES) "
                                             "e financeiro pela VW_FUNDOS_POSICAO.")
    ap.add_argument("--entrada", default=ENTRADA_PADRAO,
                    help="Excel com as abas Fundos, Tipos e Correções (padrão: input/fundos.xlsx)")
    ap.add_argument("--fundo", nargs="+", metavar="FUNDO",
                    help="só estes fundos, no lugar da aba Fundos (tipos e correções continuam vindo do Excel)")
    ap.add_argument("--data", type=_data,
                    help="data de referência dd/mm/aaaa (padrão: última data da posição de cada fundo)")
    ap.add_argument("--fonte", choices=("boleta", "vcra"), default="boleta",
                    help="taxa dos CDI+: boleta (negociada, padrão) ou vcra (pelo PU pago); %%CDI usa sempre a boleta")
    ap.add_argument("--cdi", type=float, help="CDI em %% a.a. para converter %%CDI em CDI+ equivalente "
                                               "(padrão: CDIAcumulado da FUNDOS_DADOS_INDICES na data de cada fundo)")
    args = ap.parse_args(argv)
    if args.cdi is not None and not 1 < args.cdi < 50:
        ap.error("--cdi em % a.a. (ex.: 13.65)")
    for fundo in args.fundo or []:
        if not re.fullmatch(r"\w+", fundo):
            ap.error(f"--fundo inválido: {fundo!r}")

    if os.path.exists(args.entrada):
        try:
            fundos, tipos, correcoes = carregar_entrada(args.entrada)
        except (OSError, ValueError) as e:
            ap.error(str(e))
    elif args.fundo:
        fundos, tipos, correcoes = [], dict(TIPOS_PADRAO), {}
    else:
        ap.error(f"não achei {args.entrada}: crie a lista de fundos ou use --fundo")
    if args.fundo:
        nomes = dict(fundos)
        fundos = [(f, nomes.get(f, "")) for f in dict.fromkeys(args.fundo)]
    if not fundos:
        ap.error(f"nenhum fundo para rodar na aba Fundos de {args.entrada}")
    print(f"[INFO] {len(fundos)} fundo(s) | tipos incluídos: {', '.join(t for t, s in tipos.items() if s)} | "
          f"taxa dos CDI+: {args.fonte}")

    sys.path.insert(0, AQUI)
    from sql_connection import disconnect, get_connection, query
    try:
        get_connection()
    except Exception as e:  # noqa — credenciais ou driver
        sys.exit(f"[ERRO] conexão com o banco: {e}")

    partes = {aba: [] for aba in ("Carteira", "Ativos", "Lotes", "Avisos")}
    resumo, cdis = [], {}
    try:
        for fundo, nome in fundos:
            print(f"\n── {fundo}{f' ({nome})' if nome else ''} {'─' * 40}")
            info = {"fundo": fundo, "nome": nome}
            resumo.append(info)
            try:
                d = carregar_fundo(query, fundo, args.data, tipos)
                if args.cdi is not None:
                    cdi, origem = args.cdi / 100, "informado em --cdi"
                else:
                    if d["data"] not in cdis:
                        cdis[d["data"]] = carregar_cdi(query, d["data"])
                    cdi, origem = cdis[d["data"]]
                print(f"[INFO] {d['data']:%d/%m/%Y} | CDI {_br(cdi * 100)}% a.a. ({origem}) | "
                      f"{len(correcoes.get(fundo, {}))} correção(ões) manual(is)")
                if d["boletas"].empty:
                    print("[AVISO] nenhuma boleta na FUNDOS_OPERACOES: CDI+ pela VCRA e %CDI sem taxa")
                lotes, ativos, carteira, avisos = calcular(d["vcra"], d["boletas"], d["posicao"], d["data"], cdi,
                                                           args.fonte, correcoes.get(fundo, {}), tipos)
                imprimir_fundo(lotes, ativos, carteira, avisos, d["data"], cdi)
            except Exception as e:  # noqa — erro num fundo (dado faltando, consulta) não para os outros
                print(f"[ERRO] {fundo}: {e}")
                info["status"] = f"erro: {e}"
                continue
            total = carteira[carteira["grupo"] == "CARTEIRA"]
            info.update(data=d["data"], cdi=cdi * 100, cdi_origem=origem, n_lotes=len(lotes),
                        n_ativos=int(ativos["qt_lotes"].notna().sum()), n_avisos=len(avisos),
                        status="OK" if len(total) else "sem ativo com taxa e PU",
                        taxa_carteira=total["taxa_cdi_mais"].iloc[0] if len(total) else np.nan,
                        financeiro=total["financeiro"].iloc[0] if len(total) else np.nan)
            partes["Carteira"].append(carteira.assign(fundo=fundo, data=pd.Timestamp(d["data"])))
            partes["Ativos"].append(ativos.assign(fundo=fundo))
            partes["Lotes"].append(lotes.assign(fundo=fundo))
            partes["Avisos"].append(pd.DataFrame(avisos, columns=["aviso", "ativo", "lote", "detalhe"]).assign(fundo=fundo))
    finally:
        disconnect()

    tabelas = {aba: pd.concat([p for p in lista if len(p)], ignore_index=True) if any(len(p) for p in lista)
               else pd.DataFrame() for aba, lista in partes.items()}
    if len(tabelas["Lotes"]):
        tabelas["Lotes"] = tabelas["Lotes"].sort_values(["fundo", "grupo", "codigo", "dt_compra"]).assign(
            boleta_ok=lambda x: x["boleta_ok"].map({True: "sim", False: "não"}))
    tabelas["Fundos"] = pd.DataFrame(resumo)
    datas = [r["data"] for r in resumo if "data" in r]
    ref = args.data or (max(datas) if datas else datetime.now().date())
    tabelas["Parâmetros"] = pd.DataFrame([
        ("Entrada", args.entrada if os.path.exists(args.entrada) else "(sem arquivo: --fundo e tipos padrão)"),
        ("Fundos", ", ".join(f for f, _ in fundos)),
        ("Data de referência", f"{args.data:%d/%m/%Y}" if args.data else "última data da posição de cada fundo"),
        ("Taxa dos CDI+", "boleta (negociada)" if args.fonte == "boleta" else "VCRA (pelo PU pago)"),
        ("Taxa dos %CDI", "boleta (% do CDI)"),
        ("CDI para %CDI → CDI+", f"{_br(args.cdi, 4)}% a.a. (--cdi)" if args.cdi is not None
         else "CDIAcumulado na data de cada fundo (aba Fundos)"),
        ("Tipos incluídos", ", ".join(t for t, s in tipos.items() if s)),
        ("Tipos excluídos", ", ".join(t for t, s in tipos.items() if not s)),
        ("Indexador", "só CDI (IDDIR_CD começando com CDI)"),
        ("Casamento com a boleta", f"mesmo ativo, até {JANELA_BOLETA} dias, mesma quantidade ou PU "
                                   f"(tolerância {TOLERANCIA_PU})"),
        ("Boleta válida", f"%CDI >= {LIMITE_CONVENCAO} (% do CDI); CDI+ < {LIMITE_CONVENCAO} (spread)"),
        ("Correções manuais", f"{sum(map(len, correcoes.values()))} lote(s) com aplicar = S na aba Correções"),
        ("Gerado em", f"{datetime.now():%d/%m/%Y %H:%M}"),
    ], columns=["parametro", "valor"])
    notas = ["CDI+: spread sobre 100% do CDI (% a.a.). %CDI: % do CDI.",
             "CDI+ equivalente: %CDI convertido com CDI flat; o CDI usado em cada fundo está na aba Fundos.",
             "Médias ponderadas pelo financeiro (qtd em aberto x último PU da posição); ativo sem taxa ou sem PU "
             "fica de fora (aba Avisos)."]

    os.makedirs(SAIDA_DIR, exist_ok=True)
    arquivo = f"taxa_media_{fundos[0][0]}_{ref:%Y%m%d}.xlsx" if len(fundos) == 1 else f"taxa_media_{ref:%Y%m%d}.xlsx"
    xlsx = os.path.join(SAIDA_DIR, arquivo)
    try:
        salvar_xlsx(xlsx, tabelas, notas)
    except PermissionError:
        sys.exit(f"[ERRO] não deu para gravar {xlsx}: o arquivo está aberto no Excel?")

    print(f"\n── Resumo {'─' * 40}")
    for r in resumo:
        if r["status"] == "OK":
            print(f"[OK] {r['fundo']} em {r['data']:%d/%m/%Y}: carteira {_cdi_mais(r['taxa_carteira'])} "
                  f"({r['n_ativos']} ativos, R$ {_br(r['financeiro'], 0)}; {r['n_avisos']} avisos)")
        elif r["status"].startswith("erro: "):
            print(f"[ERRO] {r['fundo']}: {r['status'][len('erro: '):]}")
        else:
            print(f"[AVISO] {r['fundo']}: {r['status']}")
    print(f"[OK] {xlsx}")
    if any(r["status"].startswith("erro") for r in resumo):
        sys.exit(1)


if __name__ == "__main__":
    main()
