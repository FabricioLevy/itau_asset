# ─────────────────────────────────────────────
# batimento/detectores.py
# Verificações do batimento cota × posição. Só pandas: cada função recebe os DataFrames das consultas
# (consultas.py) e devolve ocorrências, sem tocar no banco — os testes (tests/) usam dados colados do banco.
#
# Sinais
#   dif_rs      PnL da cota − PnL da posição (a Diferenca_Fin da triagem).
#   ajuste_rs   quanto somar ao PnL da posição para desfazer a causa encontrada.
#   residuo_rs  dif_rs − ajuste_rs: o que sobra da diferença depois desse ajuste.
#   valor       total_moeda_fundo da linha (em reais); total quando ele vem vazio.
# ─────────────────────────────────────────────

from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

AJUSTE_MANUAL = "ajuste_pnl"                        # contraparte das linhas de ajuste manual de PnL
CHAVE_LINHA = ["codigo_IAM_ativo", "contraparte", "tipo"]
FORTES = ("explica", "confirmado")                  # status em que a causa fecha a diferença

VERIFICACOES = {
    "SEM_POSICAO": (
        "Sem posição",
        "O fundo tem cota no dia e nenhuma linha na VW_FUNDOS_POSICAO. Se é a primeira cota do código, é código "
        "novo (classe ou subclasse) — a posição costuma estar no código de origem (ex.: FICFI54649S1 em 29/10/2026)."),
    "SEM_COTA": (
        "Sem cota",
        "O fundo tem posição no dia, teve cota antes e não tem cota no dia."),
    "PRECO_FERIADO": (
        "Preço de feriado contado duas vezes",
        "Há uma linha de preço na FUNDOS_DADOS_ATIVOS numa data sem posição (feriado), e a linha do dia parte do "
        "mesmo preço anterior que ela. A posição soma as duas variações (3GALABIT no BITI11 em 18/02, 08/09 e "
        "13/10/2026, linha do CotaExternaD0.py). Só reprocessar repete o erro: é preciso tirar a linha do feriado "
        "ou lançar um ajuste de PnL."),
    "PRECO_FERIADO_ALERTA": (
        "Linha de preço em feriado (alerta)",
        "Linha de preço de um script da lista de alerta (--scripts-alerta) gravada em feriado ou fim de semana "
        "depois da última posição: a próxima posição deve somar essa variação duas vezes."),
    "OUTRAS_DESPESAS_ESPECIE": (
        "Integralização/resgate em espécie como despesa",
        "Uma linha sem saldo (em geral OUTRAS_DESPESAS) tem PnL igual ao valor dos ativos que entraram ou saíram "
        "do fundo no dia: a contrapartida da integralização/resgate em espécie virou despesa (ETFs da INDEXADOS em "
        "out/2026)."),
    "LINHA_EXPLICA": (
        "Uma linha explica a diferença",
        "Tirando o PnL de uma única linha, a posição bate com a cota."),
    "DIFERENCA_IGUAL_SALDO": (
        "Diferença igual a um saldo",
        "A diferença do dia é igual ao saldo de uma linha de caixa, CPR ou despesa: o saldo inteiro está entrando "
        "no PnL, e não só a variação do dia (FICFI53254 e o CaixaCPROutros em out/2026)."),
    "LINHA_SEM_SALDO": (
        "Linha sem saldo com PnL",
        "Linha sem saldo no dia nem no dia anterior, com PnL relevante (fora as linhas ajuste_pnl)."),
    "FLUXO_FORA_MERCADO": (
        "Fluxo fora do valor de mercado",
        "A entrada ou saída de um ativo foi registrada por um valor muito diferente do de mercado, e a diferença "
        "virou PnL (BXP3SR7 no ITSCAPFIA53839 em 19/10/2026: entrada a 3,0× o valor)."),
    "PNL_FORA_PRECO": (
        "PnL fora de quantidade × preço × câmbio",
        "O pnl_moeda_ativo da linha não bate com quantidade × (preço − preço anterior) × câmbio da própria linha. "
        "Vale só para os tipos de --tipos-pnl-preco (padrão: cotas de fundo)."),
    "PRECO_ZERO": (
        "Preço zero",
        "Linha com preço zero na FUNDOS_DADOS_ATIVOS para ativo em carteira (aba Preços)."),
    "PRECO_SALTO": (
        "Salto de preço",
        "Variação de preço acima de --salto-preco na FUNDOS_DADOS_ATIVOS para ativo em carteira (aba Preços)."),
    "PRECO_DUPLICADO": (
        "Preço duplicado",
        "Mais de uma linha de preço no mesmo dia, com valores diferentes, para ativo em carteira (aba Preços)."),
    "AJUSTE_MANUAL": (
        "Ajuste manual de PnL",
        "Linha com contraparte ajuste_pnl na posição: correção manual já lançada."),
    "SEM_CAUSA": (
        "Sem causa automática",
        "Nenhuma verificação explicou a diferença: rodar o batimento por ativo (script solução) para o fundo."),
}

# ordem em que as causas entram no Resumo (dentro das que fecham a diferença e depois das parciais)
PRIORIDADE = ["SEM_POSICAO", "SEM_COTA", "PRECO_FERIADO", "OUTRAS_DESPESAS_ESPECIE", "DIFERENCA_IGUAL_SALDO",
              "LINHA_EXPLICA", "FLUXO_FORA_MERCADO", "PNL_FORA_PRECO", "LINHA_SEM_SALDO"]

COLUNAS_OCORRENCIA = ["data", "fundo", "verificacao", "titulo", "status", "ativo", "ajuste_rs", "residuo_rs",
                      "detalhe", "acao", "tipo_linha", "contraparte_linha", "data_origem", "script_origem", "sem_saldo"]
COLUNAS_PRECOS = ["data", "ativo", "verificacao", "titulo", "preco_anterior", "preco", "variacao", "script",
                  "gravado_em", "usuario", "fundos", "exposicao_rs", "detalhe"]
COLUNAS_RESUMO = ["date", "codigo_IAM_fundo", "mesa_gestao", "cota_bps", "posicao_bps", "dif_bps", "dif_rs",
                  "recorrencia", "verificacao", "diagnostico", "status", "ativo", "ajuste_rs", "residuo_rs",
                  "detalhe", "outras", "acao"]


@dataclass
class Parametros:
    limiar_bps: float = 5.0             # diferença cota × posição a partir da qual o fundo entra (bps)...
    limiar_rs: float = 1_000.0          # ... e em R$: as duas condições juntas
    limiar_linha_bps: float = 0.5       # linha relevante: |PnL| >= limiar_rs ou isso do PL (o maior)
    tol_explica: float = 0.02           # uma causa explica a diferença se o resíduo fica em até 2% dela...
    tol_minima_rs: float = 50.0         # ... ou em até R$ 50
    faixa_preco: tuple = (0.8, 1.25)    # valor do fluxo / valor de mercado aceito (FLUXO_FORA_MERCADO)
    salto_preco: float = 0.30           # variação de preço suspeita (PRECO_SALTO)
    tipos_pnl_preco: tuple = ("Fund",)  # tipos em que o PnL é quantidade × variação do preço × câmbio
    scripts_alerta: tuple = ("CotaExternaD0.py",)   # scripts cuja linha de feriado já foi contada duas vezes
    janela: int = 5                     # datas anteriores olhadas na recorrência

    def limiar_linha(self, pl):
        if pl is None or pd.isna(pl) or pl <= 0:
            return self.limiar_rs
        return max(self.limiar_rs, self.limiar_linha_bps * pl / 1e4)

    def tolerancia(self, dif):
        return max(self.tol_minima_rs, self.tol_explica * abs(dif))


# ── calendário (feriados nacionais da ANBIMA; o mesmo do captacao/src/captacao.py) ─────────────────────────

def _pascoa(ano):
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    g = (b - (b + 8) // 25 + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    return date(ano, (h + l - 7 * m + 114) // 31, (h + l - 7 * m + 114) % 31 + 1)


@lru_cache(maxsize=None)
def feriados_nacionais(ano):
    """Fixos + Carnaval (2ª e 3ª), Sexta-feira Santa e Corpus Christi; Consciência Negra a partir de 2024."""
    p = _pascoa(ano)
    fixos = [(1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (12, 25)] + (
        [(11, 20)] if ano >= 2024 else [])
    return frozenset({date(ano, m, d) for m, d in fixos} | {p - timedelta(days=48), p - timedelta(days=47),
                                                             p - timedelta(days=2), p + timedelta(days=60)})


def dia_util(d):
    d = pd.Timestamp(d).date()
    return d.weekday() < 5 and d not in feriados_nacionais(d.year)


# ── formatação dos textos ───────────────────────────────────────────────────────────────────────────────────

def num_br(x, casas=2):
    if x is None or pd.isna(x):
        return "-"
    return f"{x:,.{casas}f}".replace(",", "\0").replace(".", ",").replace("\0", ".")


def rs(x):
    return "-" if x is None or pd.isna(x) else "R$ " + num_br(x)


def preco(x):
    if x is None or pd.isna(x):
        return "-"
    return f"{x:.6f}".rstrip("0").rstrip(".").replace(".", ",")


def dt(x):
    return "-" if x is None or pd.isna(x) else pd.Timestamp(x).strftime("%d/%m/%Y")


def dt_hora(x):
    return "-" if x is None or pd.isna(x) else pd.Timestamp(x).strftime("%d/%m/%Y %H:%M")


# ── utilitários ─────────────────────────────────────────────────────────────────────────────────────────────

def _num(s):
    return pd.to_numeric(s, errors="coerce")


def _datas(df, colunas=("date",)):
    for c in colunas:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c]).dt.normalize()
    return df


def _caixa_ou_despesa(tipo):
    s = tipo.fillna("").astype(str).str.lower()
    return s.str.contains("caixa") | s.str.contains("despesa") | s.str.contains("cpr")


def _cambio(df):
    """Câmbio da linha: 1 para ativo em reais; senão o preco_cambio da posição."""
    moeda = df["moeda_ativo"].fillna("BRL").astype(str).str.upper()
    return pd.Series(np.where(moeda.str.startswith("BRL"), 1.0, _num(df["preco_cambio"])), index=df.index)


def _quantidade(df):
    """Quantidade usada no PnL de preço: a de abertura, ou a do dia quando ela vem vazia."""
    q = _num(df["quantidade_abertura"])
    return q.where(q.notna() & (q != 0), _num(df["quantidade"]))


def ocorrencia(data, fundo, codigo, status, ativo="", ajuste=np.nan, residuo=np.nan, detalhe="", acao="",
               linha=None, origem=None, sem_saldo=None):
    """linha: (tipo, contraparte) da linha da posição; origem: (data, script) da linha de preço que causou;
    sem_saldo: a linha não tem saldo no dia nem no anterior (só nas verificações por linha)."""
    tipo, contraparte = linha if linha is not None else (None, None)
    data_origem, script_origem = origem if origem is not None else (pd.NaT, None)
    return {"data": pd.Timestamp(data), "fundo": fundo, "verificacao": codigo, "titulo": VERIFICACOES[codigo][0],
            "status": status, "ativo": ativo, "ajuste_rs": ajuste, "residuo_rs": residuo, "detalhe": detalhe,
            "acao": acao, "tipo_linha": tipo, "contraparte_linha": contraparte, "data_origem": data_origem,
            "script_origem": script_origem, "sem_saldo": sem_saldo}


def tabela_ocorrencias(ocorrencias):
    return pd.DataFrame(list(ocorrencias), columns=COLUNAS_OCORRENCIA)


# ── triagem ─────────────────────────────────────────────────────────────────────────────────────────────────

def escolhe_classe(cotas):
    """Uma linha de cota por (data, fundo): classe 'Total', senão 'A', senão a de maior PL (como o script solução)."""
    c = cotas.copy()
    if c.empty:
        return c.assign(classes=pd.Series(dtype=int))
    cl = c["classe"].astype(str).str.strip().str.upper()
    c["_ordem"] = np.select([cl.eq("TOTAL"), cl.eq("A")], [0, 1], 2)
    c["_pl"] = _num(c["last_patrimonio"]).fillna(-np.inf)
    c["classes"] = c.groupby(["date", "codigo_IAM_fundo"])["codigo_IAM_fundo"].transform("size")
    c = c.sort_values(["date", "codigo_IAM_fundo", "_ordem", "_pl"], ascending=[True, True, True, False])
    return c.drop_duplicates(["date", "codigo_IAM_fundo"]).drop(columns=["_ordem", "_pl"])


def _anterior(t, mascara):
    """Para cada linha de t, a última data anterior do mesmo fundo em que `mascara` vale."""
    base = t.loc[mascara, ["codigo_IAM_fundo", "date"]].drop_duplicates()
    if base.empty:
        return pd.Series(pd.NaT, index=t.index, dtype="datetime64[ns]")
    base = base.rename(columns={"date": "_ant"}).sort_values("_ant")
    esq = t[["codigo_IAM_fundo", "date"]].reset_index().sort_values("date")
    m = pd.merge_asof(esq, base, left_on="date", right_on="_ant", by="codigo_IAM_fundo",
                      allow_exact_matches=False, direction="backward")
    return m.set_index("index")["_ant"].reindex(t.index)


def triagem(cotas, posicao, prm):
    """Uma linha por (data, fundo) com cota e/ou posição: PnL dos dois lados, diferença e se o fundo entra."""
    c = escolhe_classe(_datas(cotas.copy()))
    p = _datas(posicao.copy())
    t = c.merge(p, on=["date", "codigo_IAM_fundo"], how="outer", indicator=True)
    t["tem_cota"] = t["_merge"] != "right_only"
    t["tem_posicao"] = t["_merge"] != "left_only"
    t = t.drop(columns="_merge")
    t["cota_rs"] = _num(t["fundo_pnl"])
    t["cota_bps"] = _num(t["fundo_pnl_perc"]) * 1e4
    t["posicao_rs"] = _num(t["pnl_total"])
    t["posicao_bps"] = _num(t["pnl_bps"])
    t["dif_rs"] = (t["cota_rs"] - t["posicao_rs"].fillna(0)).where(t["tem_cota"])
    t["dif_bps"] = (t["cota_bps"] - t["posicao_bps"].fillna(0)).where(t["tem_cota"])
    t["pl"] = _num(t["last_patrimonio"])
    for col in ("pnl_outras_despesas", "pnl_ajuste_manual", "linhas"):
        t[col] = _num(t[col]) if col in t.columns else np.nan
    t["data_anterior"] = _anterior(t, t["tem_posicao"])
    t["cota_anterior"] = _anterior(t, t["tem_cota"] & t["cota_rs"].notna())

    sem_pos = t["tem_cota"] & ~t["tem_posicao"] & (t["cota_rs"].abs() >= prm.limiar_rs)
    sem_cota = (~t["tem_cota"] & t["tem_posicao"] & t["cota_anterior"].notna()
                & (t["posicao_rs"].abs() >= prm.limiar_rs))
    dif = (t["tem_cota"] & t["tem_posicao"] & (t["dif_bps"].abs() >= prm.limiar_bps)
           & (t["dif_rs"].abs() >= prm.limiar_rs))
    t["situacao"] = np.select([sem_pos, sem_cota, dif], ["SEM POSIÇÃO", "SEM COTA", "DIFERENÇA"], "")
    t["marcado"] = sem_pos | sem_cota | dif

    t = t.sort_values(["codigo_IAM_fundo", "date"]).reset_index(drop=True)
    g = t.groupby("codigo_IAM_fundo")["marcado"]
    t["dias_marcados"] = g.transform(lambda s: s.astype(int).rolling(prm.janela + 1, min_periods=1).sum())
    t["dias_olhados"] = g.transform(lambda s: s.astype(int).rolling(prm.janela + 1, min_periods=1).count())
    t["recorrencia"] = (t["dias_marcados"].astype(int).astype(str) + " de "
                        + t["dias_olhados"].astype(int).astype(str))
    return t


def ocorrencias_triagem(tri_d):
    """SEM POSIÇÃO e SEM COTA, direto da triagem."""
    oc = []
    for _, t in tri_d[tri_d["marcado"]].iterrows():
        if t["situacao"] == "SEM POSIÇÃO":
            novo = pd.isna(t["cota_anterior"])
            detalhe = (f"Cota com PnL de {rs(t['cota_rs'])} ({num_br(t['cota_bps'])} bps) e nenhuma linha na "
                       "VW_FUNDOS_POSICAO.")
            acao = "Conferir a carga da posição do fundo no dia."
            if novo:
                detalhe += " É a primeira cota do código na janela olhada: código novo (classe ou subclasse?)."
                acao = ("Conferir a carga da posição do código novo e se o PnL está no código de origem "
                        "(nesse caso, o código novo não deve ser somado de novo).")
            # sem ajuste sugerido: o PnL pode estar em outro código, e somá-lo aqui contaria duas vezes
            oc.append(ocorrencia(t["date"], t["codigo_IAM_fundo"], "SEM_POSICAO", "confirmado", detalhe=detalhe,
                                 acao=acao))
        elif t["situacao"] == "SEM COTA":
            detalhe = (f"Posição com PnL de {rs(t['posicao_rs'])} e nenhuma cota no dia; a última cota é de "
                       f"{dt(t['cota_anterior'])}.")
            oc.append(ocorrencia(t["date"], t["codigo_IAM_fundo"], "SEM_COTA", "confirmado", detalhe=detalhe,
                                 acao="Conferir a carga da cota do fundo no dia."))
    return oc


# ── verificações por linha (fundos marcados) ───────────────────────────────────────────────────────────────

COLS_NUM_LINHAS = ["quantidade", "quantidade_abertura", "preco_limpo", "preco_limpo_d1", "preco_cambio", "total",
                   "total_moeda_fundo", "pnl_total", "pnl_moeda_ativo", "pnl_operacao", "pnl_cambio",
                   "last_patrimonio"]


def prepara_linhas(linhas):
    """Normaliza as linhas da posição (consultas.FonteSQL.posicao_linhas) e calcula o `valor` em reais."""
    l = _datas(linhas.copy())
    for c in COLS_NUM_LINHAS:
        l[c] = _num(l[c]) if c in l.columns else np.nan
    for c in ("codigo_IAM_fundo", "codigo_IAM_ativo", "moeda_ativo", "ativo"):
        if c not in l.columns:
            l[c] = None
    l["contraparte"] = l["contraparte"].fillna("-").astype(str) if "contraparte" in l.columns else "-"
    l["tipo"] = l["tipo"].fillna("").astype(str) if "tipo" in l.columns else ""
    l["valor"] = l["total_moeda_fundo"].where(l["total_moeda_fundo"].notna(), l["total"])
    return l


def _mesma_linha(df, r):
    m = pd.Series(True, index=df.index)
    for c in CHAVE_LINHA:
        m &= df[c] == r[c]
    return m


def fluxos(ld, lp):
    """Por linha: variação de quantidade, fluxo implícito (Δvalor − PnL) e o valor de mercado dessa variação."""
    a = ld[CHAVE_LINHA + ["quantidade", "valor", "pnl_total"]]
    b = lp[CHAVE_LINHA + ["quantidade", "valor"]].rename(columns={"quantidade": "q_ant", "valor": "valor_ant"})
    f = a.merge(b, on=CHAVE_LINHA, how="outer")
    for c in ("quantidade", "q_ant", "valor", "valor_ant", "pnl_total"):
        f[c] = _num(f[c]).fillna(0.0)
    f["delta_q"] = f["quantidade"] - f["q_ant"]
    f["implicito"] = (f["valor"] - f["valor_ant"]) - f["pnl_total"]
    unit = np.where(f["quantidade"] != 0, f["valor"] / f["quantidade"].replace(0, np.nan),
                    f["valor_ant"] / f["q_ant"].replace(0, np.nan))
    f["mercado"] = f["delta_q"] * unit
    return f


def linha_que_explica(d, fundo, gap, ld, lp, fl, prm, explicadas):
    """A linha cujo PnL, tirado da posição, fecha a diferença (OUTRAS_DESPESAS dos ETFs, AJUSTE_... etc.)."""
    cand = ld[ld["pnl_total"].abs() >= prm.limiar_rs]
    if cand.empty:
        return []
    residuo = gap + cand["pnl_total"]
    i = residuo.abs().idxmin()
    r, res = cand.loc[i], residuo.loc[i]
    if abs(res) > prm.tolerancia(gap):
        return []
    explicadas.add(tuple(r[c] for c in CHAVE_LINHA))
    ant = lp.loc[_mesma_linha(lp, r), "valor"] if not lp.empty else pd.Series(dtype=float)
    valor_ant = ant.iloc[0] if len(ant) else np.nan
    sem_saldo = abs(np.nan_to_num(r["valor"])) < 0.01 and abs(np.nan_to_num(valor_ant)) < 0.01
    nome = r["codigo_IAM_ativo"]
    saldo = ("sem saldo no dia nem no anterior" if sem_saldo
             else f"saldo de {rs(r['valor'])}, anterior {rs(valor_ant)}")
    detalhe = (f"A linha {nome} ({r['tipo']}, {saldo}) tem PnL de {rs(r['pnl_total'])}. Sem ela, a diferença cai "
               f"de {rs(gap)} para {rs(res)}.")

    ativos = fl[(fl["delta_q"] != 0) & ~_caixa_ou_despesa(fl["tipo"]) & (fl["contraparte"] != AJUSTE_MANUAL)]
    especie = ativos["implicito"].sum()
    if (sem_saldo and abs(especie) >= prm.limiar_rs
            and abs(especie + r["pnl_total"]) <= max(prm.limiar_rs, 0.01 * abs(r["pnl_total"]))):
        fluxo = "integralização" if especie > 0 else "resgate"
        detalhe += (f" No mesmo dia, {len(ativos)} ativo(s) {'entraram' if especie > 0 else 'saíram'} em espécie "
                    f"por {rs(abs(especie))}: a linha é a contrapartida da {fluxo}, lançada como despesa.")
        acao = ("Corrigir na carga: a contrapartida da integralização/resgate em espécie é fluxo de cotista, não "
                f"despesa. No dia, zerar o PnL da {nome} (seção A-T do script solução).")
        return [ocorrencia(d, fundo, "OUTRAS_DESPESAS_ESPECIE", "explica", nome, -r["pnl_total"], res, detalhe,
                           acao, linha=(r["tipo"], r["contraparte"]), sem_saldo=True)]
    acao = f"Conferir a origem do PnL da linha {nome}: sem ela, o fundo bate com a cota."
    return [ocorrencia(d, fundo, "LINHA_EXPLICA", "explica", nome, -r["pnl_total"], res, detalhe, acao,
                       linha=(r["tipo"], r["contraparte"]), sem_saldo=sem_saldo)]


def diferenca_igual_saldo(d, fundo, gap, ld, prm, explicadas, tol=1.0):
    """A diferença é igual (em módulo) ao saldo de uma linha de caixa/CPR/despesa: saldo virando PnL."""
    if abs(gap) < prm.limiar_rs:
        return []
    c = ld[_caixa_ou_despesa(ld["tipo"]) & ld["valor"].notna()]
    if c.empty:
        return []
    dist = (c["valor"].abs() - abs(gap)).abs()
    if dist.min() > tol:
        return []
    r = c.loc[dist.idxmin()]
    nome = r["codigo_IAM_ativo"]
    carrega = [k[0] for k in explicadas if k[0] != nome]
    sinal = "" if abs(r["valor"] - gap) <= tol else ", com o sinal trocado"
    detalhe = (f"A diferença do dia ({rs(gap)}) é igual ao saldo da linha {nome} ({rs(r['valor'])}){sinal}: o "
               "saldo inteiro está entrando no PnL, e não só a variação do dia.")
    if carrega:
        detalhe += f" O PnL a mais aparece na linha {', '.join(carrega)}."
    acao = (f"Conferir como a carga da posição trata o saldo de {nome}"
            + (f" e a linha {', '.join(carrega)}" if carrega else "")
            + ". Enquanto não corrigir, a diferença acompanha esse saldo todo dia.")
    return [ocorrencia(d, fundo, "DIFERENCA_IGUAL_SALDO", "explica", nome, gap, 0.0, detalhe, acao,
                       linha=(r["tipo"], r["contraparte"]))]


def fluxo_fora_mercado(d, fundo, gap, fl, pl, prm):
    """Entrada/saída de ativo registrada por um valor muito diferente do de mercado (a diferença vira PnL)."""
    x = fl[(fl["delta_q"].abs() > 1e-9) & ~_caixa_ou_despesa(fl["tipo"]) & (fl["contraparte"] != AJUSTE_MANUAL)
           & fl["mercado"].notna() & (fl["mercado"].abs() > 0)].copy()
    if x.empty:
        return []
    x["razao"] = x["implicito"] / x["mercado"]
    lo, hi = prm.faixa_preco
    x = x[~x["razao"].between(lo, hi) & ((x["implicito"] - x["mercado"]).abs() >= prm.limiar_linha(pl))]
    if x.empty:
        return []
    caixa = fl[_caixa_ou_despesa(fl["tipo"])].assign(var=lambda f: f["valor"] - f["valor_ant"])
    maior = caixa.loc[caixa["var"].abs().idxmax()] if not caixa.empty and caixa["var"].abs().max() > 0 else None
    oc = []
    for _, r in x.iterrows():
        ajuste = r["implicito"] - r["mercado"]
        residuo = gap - ajuste
        if r["q_ant"] == 0:
            mov = "Entrada"
        elif r["quantidade"] == 0:
            mov = "Saída"
        else:
            mov = "Compra" if r["delta_q"] > 0 else "Venda"
        detalhe = (f"{mov} de {num_br(abs(r['delta_q']), 0)} de {r['codigo_IAM_ativo']} registrada por "
                   f"{rs(r['implicito'])}, {num_br(r['razao'])}× o valor de mercado ({rs(r['mercado'])}). Isso põe "
                   f"{rs(-ajuste)} no PnL da linha (PnL do dia: {rs(r['pnl_total'])}); com o fluxo a mercado, a "
                   f"diferença iria para {rs(residuo)}.")
        # contrapartida no caixa/CPR do dia, sem PnL e perto do valor de mercado (ex.: o direito que virou ação):
        # se fecha melhor a diferença, o fluxo certo é esse valor
        cont = caixa[(caixa["pnl_total"].abs() < 0.01) & (np.sign(-caixa["var"]) == np.sign(r["mercado"]))
                     & ((-caixa["var"] - r["mercado"]).abs() <= 0.2 * abs(r["mercado"]))]
        usou = False
        if not cont.empty:
            c = cont.loc[(-cont["var"] - r["mercado"]).abs().idxmin()]
            ajuste_c = r["implicito"] + c["var"]
            if abs(gap - ajuste_c) < abs(residuo):
                ajuste, residuo, usou = ajuste_c, gap - ajuste_c, True
                detalhe += (f" No mesmo dia, {c['codigo_IAM_ativo']} variou {rs(c['var'])} sem PnL: com o fluxo por "
                            f"esse valor, a diferença vai para {rs(residuo)} (é o ajuste sugerido).")
        if not usou and maior is not None:
            detalhe += (f" No mesmo dia, {maior['codigo_IAM_ativo']} variou {rs(maior['var'])}"
                        + (" sem PnL." if abs(maior["pnl_total"]) < 0.01 else "."))
        acao = (f"Conferir o evento ou a boleta de {r['codigo_IAM_ativo']} (desdobramento, grupamento, troca de "
                "ações, direito de subscrição) e o valor de entrada.")
        status = "explica" if abs(residuo) <= prm.tolerancia(gap) else "parcial"
        oc.append(ocorrencia(d, fundo, "FLUXO_FORA_MERCADO", status, r["codigo_IAM_ativo"], ajuste, residuo,
                             detalhe, acao, linha=(r["tipo"], r["contraparte"])))
    return oc


def pnl_fora_preco(d, fundo, gap, ld, pl, prm):
    """pnl_moeda_ativo diferente de quantidade × (preço − preço anterior) × câmbio da própria linha."""
    x = ld[ld["tipo"].isin(prm.tipos_pnl_preco) & (ld["contraparte"] != AJUSTE_MANUAL)
           & ld["preco_limpo"].notna() & ld["preco_limpo_d1"].notna() & ld["pnl_moeda_ativo"].notna()].copy()
    if x.empty:
        return []
    x["fx"] = _cambio(x)
    x = x[x["fx"].notna()]
    dp = x["preco_limpo"] - x["preco_limpo_d1"]
    e1, e2 = x["quantidade_abertura"] * dp * x["fx"], x["quantidade"] * dp * x["fx"]
    d1, d2 = x["pnl_moeda_ativo"] - e1, x["pnl_moeda_ativo"] - e2
    usa1 = d1.notna() & (d2.isna() | (d1.abs() <= d2.abs()))
    x["esperado"] = np.where(usa1, e1, e2)
    x["dif"] = np.where(usa1, d1, d2)
    x = x[x["dif"].abs() >= prm.limiar_linha(pl)]
    oc = []
    for _, r in x.iterrows():
        residuo = gap + r["dif"]
        cambio = "" if r["fx"] == 1 else f" × câmbio {num_br(r['fx'], 4)}"
        detalhe = (f"pnl_moeda_ativo de {rs(r['pnl_moeda_ativo'])}; quantidade × (preço {preco(r['preco_limpo'])} − "
                   f"anterior {preco(r['preco_limpo_d1'])}){cambio} dá {rs(r['esperado'])}. Diferença de "
                   f"{rs(r['dif'])}.")
        if r["fx"] != 1 and r["pnl_cambio"] == 0:
            detalhe += " O pnl_cambio está zerado: parece PnL forçado (UPDATE \"força Lake = VCRA\")."
        acao = (f"O PnL não sai dos preços da própria linha: conferir as linhas de preço de {r['codigo_IAM_ativo']} "
                f"na FUNDOS_DADOS_ATIVOS entre a posição anterior e {dt(d)} (linha em feriado?).")
        status = "explica" if abs(residuo) <= prm.tolerancia(gap) else "parcial"
        oc.append(ocorrencia(d, fundo, "PNL_FORA_PRECO", status, r["codigo_IAM_ativo"], -r["dif"], residuo,
                             detalhe, acao, linha=(r["tipo"], r["contraparte"])))
    return oc


def linhas_sem_saldo(d, fundo, gap, ld, lp, pl, prm, explicadas):
    """Linhas sem saldo no dia e no anterior com PnL relevante (fora as já explicadas e os ajustes manuais)."""
    m = ld.merge(lp[CHAVE_LINHA + ["valor"]].rename(columns={"valor": "valor_ant"}), on=CHAVE_LINHA, how="left")
    sem = ((m["valor"].fillna(0).abs() < 0.01) & (m["valor_ant"].fillna(0).abs() < 0.01)
           & (m["pnl_total"].abs() >= prm.limiar_linha(pl)) & (m["contraparte"] != AJUSTE_MANUAL))
    oc = []
    for _, r in m[sem].iterrows():
        if tuple(r[c] for c in CHAVE_LINHA) in explicadas:
            continue
        residuo = gap + r["pnl_total"]
        detalhe = (f"A linha {r['codigo_IAM_ativo']} ({r['tipo']}) não tem saldo no dia nem no anterior e tem PnL "
                   f"de {rs(r['pnl_total'])}.")
        status = "explica" if abs(residuo) <= prm.tolerancia(gap) else "parcial"
        oc.append(ocorrencia(d, fundo, "LINHA_SEM_SALDO", status, r["codigo_IAM_ativo"], -r["pnl_total"], residuo,
                             detalhe, f"Conferir a origem do PnL da {r['codigo_IAM_ativo']}.",
                             linha=(r["tipo"], r["contraparte"]), sem_saldo=True))
    return oc


def verifica_fundo(t, ld, lp, prm):
    """Verificações por linha de um fundo marcado. t: linha da triagem; ld/lp: linhas no dia e na data anterior."""
    d, fundo, gap, pl = t["date"], t["codigo_IAM_fundo"], t["dif_rs"], t["pl"]
    if ld.empty or pd.isna(gap):
        return []
    ld, lp = ld.reset_index(drop=True), lp.reset_index(drop=True)
    fl = fluxos(ld, lp)
    explicadas = set()
    oc = linha_que_explica(d, fundo, gap, ld, lp, fl, prm, explicadas)
    oc += diferenca_igual_saldo(d, fundo, gap, ld, prm, explicadas)
    preco_errado = pnl_fora_preco(d, fundo, gap, ld, pl, prm)
    # o fluxo implícito sai do PnL: numa linha cujo PnL já não bate com os preços, ele não diz nada novo
    sem_fluxo = {o["ativo"] for o in preco_errado}
    oc += fluxo_fora_mercado(d, fundo, gap, fl[~fl["codigo_IAM_ativo"].isin(sem_fluxo)], pl, prm)
    oc += preco_errado
    oc += linhas_sem_saldo(d, fundo, gap, ld, lp, pl, prm, explicadas)
    return oc


# ── tabela de preços (FUNDOS_DADOS_ATIVOS) ─────────────────────────────────────────────────────────────────

def _renomeia_preco(df, sufixo):
    return df.rename(columns={"date": f"data_{sufixo}", "preco_limpo": f"preco_{sufixo}",
                              "preco_limpo_d1": f"base_{sufixo}", "pnl_moeda_ativo": f"var_{sufixo}",
                              "log_script_from": f"script_{sufixo}", "log_last_user": f"usuario_{sufixo}",
                              "log_last_processamento": f"gravado_{sufixo}"})


def preco_feriado(d, pos_ativos, precos_h, precos_d, anteriores, tri_d, prm):
    """
    Linha de preço numa data entre a posição anterior e d (feriado) que a linha de d ignora: as duas partem do
    mesmo preço anterior, e a posição de d soma as duas variações.

    pos_ativos  posição em d dos ativos com linha de preço entre as posições (consultas.posicao_ativos_entre)
    precos_h    linhas da FUNDOS_DADOS_ATIVOS entre as posições, com variação (consultas.precos_entre)
    precos_d    linhas de d desses ativos (consultas.precos_do_dia)
    anteriores  Series fundo → data da posição anterior
    tri_d       triagem em d: confirma pela diferença do fundo
    """
    d = pd.Timestamp(d)
    if pos_ativos.empty or precos_h.empty or precos_d.empty:
        return []
    h = _renomeia_preco(_datas(precos_h.copy()), "h")
    h = h[_num(h["var_h"]).fillna(0) != 0]
    dd = _renomeia_preco(_datas(precos_d.copy()), "d")
    linhas_d = dd.groupby("codigo_IAM_ativo").size().rename("linhas_d")
    linhas_h = h.groupby(["data_h", "codigo_IAM_ativo"]).size().rename("linhas_h")
    m = h.merge(dd[["codigo_IAM_ativo", "preco_d", "base_d", "script_d"]], on="codigo_IAM_ativo")
    base_h, base_d = _num(m["base_h"]), _num(m["base_d"])
    m = m[(base_h.abs() > 0) & ((base_d - base_h).abs() <= 1e-9 * base_h.abs().clip(lower=1))]
    if m.empty:
        return []
    m = m.drop_duplicates(["codigo_IAM_ativo", "data_h", "var_h", "script_h"])
    m = m.join(linhas_d, on="codigo_IAM_ativo").join(linhas_h, on=["data_h", "codigo_IAM_ativo"])

    pa = _datas(pos_ativos.copy()).reset_index(drop=True)
    x = pa.merge(m, on="codigo_IAM_ativo")
    x["data_anterior"] = x["codigo_IAM_fundo"].map(anteriores)
    x = x[x["data_anterior"].notna() & (x["data_h"] > x["data_anterior"]) & (x["data_h"] < d)].copy()
    if x.empty:
        return []
    x["q"] = _quantidade(x)
    x["fx"] = _cambio(x)
    x["excesso"] = x["q"] * _num(x["var_h"]) * x["fx"]

    ajuste_manual = (pa[pa["codigo_IAM_ativo"].isin(x["codigo_IAM_ativo"])]
                     .groupby("codigo_IAM_fundo")["pnl_ajuste_manual"].sum())
    marcados = set(tri_d.loc[tri_d["marcado"], "codigo_IAM_fundo"])
    gap = tri_d.set_index("codigo_IAM_fundo")["dif_rs"]
    oc = []
    for fundo, g in x.groupby("codigo_IAM_fundo"):
        exc = g["excesso"].sum()
        if pd.isna(exc) or abs(exc) < prm.limiar_rs:
            continue
        aj = ajuste_manual.get(fundo, 0.0)
        aj = 0.0 if pd.isna(aj) else float(aj)
        dif = gap.get(fundo, np.nan)
        if aj != 0 and abs(aj + exc) <= max(prm.limiar_rs, 0.01 * abs(exc)):
            status, residuo = "corrigido", dif
        elif pd.notna(dif) and abs(dif + exc) <= max(prm.limiar_rs, 0.02 * abs(exc)):
            status, residuo = "confirmado", dif + exc
        elif pd.notna(dif):
            if fundo not in marcados:
                continue                    # o fundo bateu com a cota: a posição não usou essa linha
            status, residuo = "não confirmado", dif + exc
        else:
            status, residuo = "candidato", np.nan
        for _, r in g.iterrows():
            detalhe = (f"Linha de preço de {dt(r['data_h'])} ({r['script_h']}, gravada em {dt_hora(r['gravado_h'])}) "
                       f"com variação de {preco(r['var_h'])} por unidade, de {preco(r['base_h'])} para "
                       f"{preco(r['preco_h'])}. A linha de {dt(d)} ({r['script_d']}) também parte de "
                       f"{preco(r['base_d'])}: a posição soma as duas. Excesso: quantidade {num_br(r['q'], 2)} × "
                       f"{preco(r['var_h'])}" + ("" if r["fx"] == 1 else f" × câmbio {num_br(r['fx'], 4)}")
                       + f" = {rs(r['excesso'])}.")
            if np.nan_to_num(r["linhas_d"]) > 1 or np.nan_to_num(r["linhas_h"]) > 1:
                detalhe += " Atenção: o ativo tem mais de uma linha de preço no dia (scripts diferentes)."
            if status == "corrigido":
                detalhe += f" Já corrigido com ajuste_pnl de {rs(aj)}."
                acao = "Nenhuma: já corrigido com ajuste manual."
            elif status == "confirmado":
                acao = (f"Lançar ajuste de PnL de {rs(-exc)} no {fundo}/{r['codigo_IAM_ativo']}, ou tirar a linha de "
                        f"{dt(r['data_h'])} da FUNDOS_DADOS_ATIVOS e reprocessar. Só reprocessar repete o erro.")
            elif status == "não confirmado":
                acao = "A diferença do fundo não bate com essa linha: provavelmente é outra causa."
            else:
                acao = "Sem cota para confirmar: conferir o PnL do ativo no fundo."
            oc.append(ocorrencia(d, fundo, "PRECO_FERIADO", status, r["codigo_IAM_ativo"], -r["excesso"], residuo,
                                 detalhe, acao, origem=(r["data_h"], r["script_h"])))
    return oc


def alerta_feriado(d, hoje, pos_ativos, precos_fut, prm):
    """Linhas de preço de scripts da lista de alerta gravadas em dia não útil depois de d (a próxima posição)."""
    d, hoje = pd.Timestamp(d), pd.Timestamp(hoje)
    if pos_ativos.empty or precos_fut.empty:
        return []
    f = _renomeia_preco(_datas(precos_fut.copy()), "h")
    f = f[(f["data_h"] > d) & (f["data_h"] <= hoje) & ~f["data_h"].map(dia_util)
          & f["script_h"].isin(prm.scripts_alerta) & (_num(f["var_h"]).fillna(0) != 0)]
    if f.empty:
        return []
    x = _datas(pos_ativos.copy()).merge(f, on="codigo_IAM_ativo")
    x["q"] = _quantidade(x)
    x["fx"] = _cambio(x)
    x["excesso"] = x["q"] * _num(x["var_h"]) * x["fx"]
    oc = []
    for _, r in x[x["excesso"].abs() >= prm.limiar_rs].iterrows():
        detalhe = (f"Linha de preço de {dt(r['data_h'])} ({r['script_h']}, gravada em {dt_hora(r['gravado_h'])}), "
                   f"variação de {preco(r['var_h'])} por unidade, de {preco(r['base_h'])} para {preco(r['preco_h'])}. "
                   f"Se a linha do próximo dia útil partir de novo de {preco(r['base_h'])}, a posição conta essa "
                   f"variação duas vezes: cerca de {rs(r['excesso'])} com a quantidade de {dt(d)}.")
        acao = (f"Tirar a linha de {dt(r['data_h'])} antes da posição do próximo dia útil, ou corrigir depois com "
                f"ajuste de PnL de {rs(-r['excesso'])}.")
        oc.append(ocorrencia(r["data_h"], r["codigo_IAM_fundo"], "PRECO_FERIADO_ALERTA", "alerta",
                             r["codigo_IAM_ativo"], -r["excesso"], np.nan, detalhe, acao,
                             origem=(r["data_h"], r["script_h"])))
    return oc


def anomalias_preco(anomalos, duplicados, pos_lista, prm):
    """Preço zero, salto de preço e preço duplicado de ativos em carteira (aba Preços), com a exposição."""
    if pos_lista.empty or (anomalos.empty and duplicados.empty):
        return pd.DataFrame(columns=COLUNAS_PRECOS)
    pos = _datas(pos_lista.copy()).reset_index(drop=True)
    pos["q"] = _quantidade(pos)
    pos["fx"] = _cambio(pos)

    def carteira(ativo, delta):
        p = pos[pos["codigo_IAM_ativo"] == ativo]
        if p.empty:
            return None
        exp = p["q"] * delta * p["fx"]
        maior = p.loc[exp.abs().idxmax(), "codigo_IAM_fundo"] if exp.notna().any() else p["codigo_IAM_fundo"].iloc[0]
        nome = maior if len(p) == 1 else f"{len(p)} fundos (maior: {maior})"
        return nome, exp.sum()

    linhas = []
    for _, r in _datas(anomalos.copy()).iterrows():
        base, atual = _num(pd.Series([r["preco_limpo_d1"], r["preco_limpo"]]))
        cart = carteira(r["codigo_IAM_ativo"], atual - base if pd.notna(base) else np.nan)
        if cart is None:
            continue
        codigo = "PRECO_ZERO" if atual == 0 else "PRECO_SALTO"
        var = atual / base - 1 if pd.notna(base) and base else np.nan
        detalhe = (f"Preço {preco(atual)} contra {preco(base)} no dia anterior"
                   + (f" ({num_br(var * 100, 1)}%)" if pd.notna(var) else "") + ".")
        linhas.append({"data": r["date"], "ativo": r["codigo_IAM_ativo"], "verificacao": codigo,
                       "titulo": VERIFICACOES[codigo][0], "preco_anterior": base, "preco": atual, "variacao": var,
                       "script": r.get("log_script_from"), "gravado_em": r.get("log_last_processamento"),
                       "usuario": r.get("log_last_user"), "fundos": cart[0], "exposicao_rs": cart[1],
                       "detalhe": detalhe})
    for _, r in _datas(duplicados.copy()).iterrows():
        pmin, pmax = _num(pd.Series([r["preco_min"], r["preco_max"]]))
        cart = carteira(r["codigo_IAM_ativo"], pmax - pmin)
        if cart is None:
            continue
        scripts = r["script_1"] if r["script_1"] == r["script_2"] else f"{r['script_1']}, {r['script_2']}"
        detalhe = (f"{int(r['linhas'])} linhas no dia, com preços de {preco(pmin)} a {preco(pmax)} ({scripts}). A "
                   "exposição é a diferença entre o maior e o menor preço na carteira.")
        linhas.append({"data": r["date"], "ativo": r["codigo_IAM_ativo"], "verificacao": "PRECO_DUPLICADO",
                       "titulo": VERIFICACOES["PRECO_DUPLICADO"][0], "preco_anterior": pmin, "preco": pmax,
                       "variacao": pmax / pmin - 1 if pmin else np.nan, "script": scripts, "gravado_em": None,
                       "usuario": None, "fundos": cart[0], "exposicao_rs": cart[1], "detalhe": detalhe})
    return pd.DataFrame(linhas, columns=COLUNAS_PRECOS)


def ocorrencias_ajustes(ajustes):
    oc = []
    for _, r in _datas(ajustes.copy()).iterrows():
        detalhe = (f"Linha ajuste_pnl de {rs(_num(pd.Series([r['pnl_total']])).iloc[0])} lançada por "
                   f"{r.get('log_last_user') or '-'} em {dt_hora(r.get('log_last_processamento'))}.")
        oc.append(ocorrencia(r["date"], r["codigo_IAM_fundo"], "AJUSTE_MANUAL", "info", r["codigo_IAM_ativo"],
                             detalhe=detalhe, acao="Nenhuma: só registro."))
    return oc


# ── resumo ──────────────────────────────────────────────────────────────────────────────────────────────────

def resumo(tri, ocorrencias, prm):
    """Uma linha por fundo marcado, com a causa mais provável (as que fecham a diferença primeiro)."""
    marc = tri[tri["marcado"]].copy()
    if marc.empty:
        return pd.DataFrame(columns=COLUNAS_RESUMO)
    oc = tabela_ocorrencias(ocorrencias)
    oc = oc[oc["verificacao"].isin(PRIORIDADE) & (oc["status"] != "corrigido")]
    marc["_ordem"] = marc["dif_rs"].abs().fillna(marc["cota_rs"].abs())
    linhas = []
    for _, t in marc.sort_values(["date", "_ordem"], ascending=[True, False]).iterrows():
        o = oc[(oc["data"] == t["date"]) & (oc["fundo"] == t["codigo_IAM_fundo"])]
        base = {c: t.get(c) for c in ("date", "codigo_IAM_fundo", "mesa_gestao", "cota_bps", "posicao_bps",
                                      "dif_bps", "dif_rs", "recorrencia")}
        if o.empty:
            base.update({"verificacao": "SEM_CAUSA", "diagnostico": VERIFICACOES["SEM_CAUSA"][0], "status": "",
                         "ativo": "", "ajuste_rs": np.nan, "residuo_rs": np.nan, "detalhe": "", "outras": "",
                         "acao": "Rodar o batimento por ativo (script solução) para o fundo e a data."})
        else:
            o = o.assign(_fraca=~o["status"].isin(FORTES), _p=o["verificacao"].map(PRIORIDADE.index),
                         _r=o["residuo_rs"].abs().fillna(np.inf)).sort_values(["_fraca", "_p", "_r"])
            e = o.iloc[0]
            outras = [x for x in dict.fromkeys(o["titulo"].iloc[1:]) if x != e["titulo"]]
            base.update({"verificacao": e["verificacao"], "diagnostico": e["titulo"], "status": e["status"],
                         "ativo": e["ativo"], "ajuste_rs": e["ajuste_rs"], "residuo_rs": e["residuo_rs"],
                         "detalhe": e["detalhe"], "outras": "; ".join(outras), "acao": e["acao"]})
        linhas.append(base)
    return pd.DataFrame(linhas, columns=COLUNAS_RESUMO)
