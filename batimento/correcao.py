# ─────────────────────────────────────────────
# batimento/correcao.py
# Correção das diferenças diagnosticadas. Monta o plano a partir do Resumo (uma correção por fundo e data), busca
# as linhas da VW_FUNDOS_POSICAO que vão mudar (que também são o backup) e gera:
#   correcao_<...>.sql   script de revisão: BEGIN TRANSACTION, UPDATE com trava no valor atual da linha,
#                        conferência cota × posição dentro da transação e ROLLBACK no fim (troque por COMMIT)
#   reverter_<...>.sql   volta as linhas aos valores de antes (com trava no valor corrigido)
#   backup_<...>.xlsx    as linhas inteiras antes da correção
# Com --aplicar, roda as mesmas atualizações numa transação, confere cota × posição de cada fundo e só grava
# (COMMIT) se todas baterem com o esperado e alguém digitar SIM; senão desfaz tudo (ROLLBACK).
#
# O que vira correção
#   automática  OUTRAS_DESPESAS_ESPECIE (zera o PnL da linha), PRECO_FERIADO confirmado e PNL_FORA_PRECO que
#               explica (tira o excesso da linha do ativo), DIFERENCA_IGUAL_SALDO (tira a diferença da linha que
#               carrega o PnL a mais)
#   revisar     FLUXO_FORA_MERCADO, LINHA_EXPLICA, LINHA_SEM_SALDO e os casos parciais: o UPDATE sai comentado
#               no script e não entra no --aplicar (com --com-revisao, entra)
#   sem SQL     SEM_POSICAO (reprocessar a posição pelo RunProject), SEM_COTA, SEM_CAUSA
#   prevenção   PRECO_FERIADO_ALERTA: DELETE comentado da linha de preço do feriado, antes da próxima posição
# Uma linha da posição (fundo, ativo, contraparte, tipo) pode estar em mais de um registro da VW_FUNDOS_POSICAO
# (estratégias est1..est5, operações): cada registro com PnL vira um UPDATE, separado dos outros pelas colunas
# que o distinguem (IDENTIDADE). Se nada os separa, a correção fica para fazer à mão.
# Colunas alteradas: pnl_total e pnl_total_perc; nos ajustes de preço, também pnl_moeda_ativo(_perc); nos outros,
# a coluna de componente (pnl_moeda_ativo ou pnl_moeda_ativo_operacao) só se ela carrega todo o PnL do registro
# (somar o ajuste numa coluna zerada criaria PnL onde não havia). O percentual muda pelo ajuste ÷ last_patrimonio
# do próprio registro. Alpha e benchmark não mudam (um reprocessamento recalcula; sem corrigir a origem, ele também
# traz o erro de volta).
# ─────────────────────────────────────────────

from dataclasses import dataclass, field, replace
from datetime import datetime

import numpy as np
import pandas as pd

from detectores import AJUSTE_MANUAL, dt, rs

AUTOMATICA, REVISAR, SEM_SQL, PREVENCAO = "automática", "revisar", "sem SQL", "prevenção"
CAMINHO_POSICAO = "Posicao/SAC/importar_posicao"     # caminho do PainelControle verificado no script solução
TOLERANCIA_RS = 1.0                                  # conferência: diferença depois × esperada
ZERA = ("OUTRAS_DESPESAS_ESPECIE", "LINHA_EXPLICA", "LINHA_SEM_SALDO")   # a correção zera o PnL da linha
PRECO = ("PRECO_FERIADO", "PNL_FORA_PRECO")          # ajuste de preço: vai também para o pnl_moeda_ativo
COMPONENTES = ("pnl_moeda_ativo", "pnl_moeda_ativo_operacao")
IDENTIDADE = ("est1", "est2", "est3", "est4", "est5", "codigo_operacao", "pac", "tipo_dado", "origem_ativo",
              "calculo_cota", "quantidade", "quantidade_abertura", "total", "total_moeda_fundo")
_FORA = object()                                     # valor que não serve para separar registros (data, binário)


@dataclass
class Correcao:
    data: pd.Timestamp
    fundo: str
    verificacao: str
    diagnostico: str
    nivel: str
    ativo: str = ""
    tipo: object = None                 # chave da linha (preenchida pela linha encontrada)
    contraparte: object = None
    delta: float = np.nan               # quanto somar ao PnL da linha
    dif_antes: float = np.nan           # diferença cota − posição do fundo no diagnóstico
    classe: object = None               # classe da cota usada na triagem (para a conferência)
    pl_triagem: float = np.nan
    nota: str = ""
    origem: list = field(default_factory=list)   # [(data, ativo, script)] linhas de preço da causa
    runproject: str = ""
    situacao: str = ""                  # pronta, linha não encontrada, ..., aplicada, desfeita
    pnl_total: float = np.nan           # valores do registro antes da correção
    pnl_total_perc: float = np.nan
    componente: str = ""                # pnl_moeda_ativo / pnl_moeda_ativo_operacao, se também recebe o ajuste
    comp_valor: float = np.nan
    comp_perc: float = np.nan
    pl: float = np.nan
    filtro: dict = field(default_factory=dict)   # colunas que separam o registro dos outros da mesma linha
    parte: str = ""                     # "1/2"...: a linha está em mais de um registro
    preparada: bool = False             # o UPDATE ficou pronto (continua valendo depois de aplicada/desfeita)
    dif_depois: float = np.nan          # conferência do --aplicar
    conferencia: str = ""

    @property
    def pronta(self):
        return self.situacao == "pronta"

    @property
    def delta_perc(self):
        return self.delta / self.pl

    def no_script(self, com_revisao):
        return self.preparada and (self.nivel == AUTOMATICA or (com_revisao and self.nivel == REVISAR))

    def entra(self, com_revisao):
        return self.pronta and self.no_script(com_revisao)


# ── plano ───────────────────────────────────────────────────────────────────────────────────────────────────

def _campo(e, col):
    if e is None or col not in e or pd.isna(e[col]):
        return None
    return e[col]


def _runproject(d, fundo):
    return ("from RodarProjeto.Engine_RunProject_V2 import RunProject\n"
            f'RunProject(date_ref="{pd.Timestamp(d):%Y-%m-%d}", funds=["{fundo}"],\n'
            f'           lista_funcoes=[{{"caminho": "{CAMINHO_POSICAO}", "parametro": None}}])')


def monta_plano(res):
    """Uma correção por fundo e data do Resumo, mais a prevenção dos alertas de feriado."""
    oc = res.ocorrencias
    tri = res.triagem.set_index(["date", "codigo_IAM_fundo"]) if len(res.triagem) else None
    plano = []
    for _, r in res.resumo.iterrows():
        d, f, v = r["date"], r["codigo_IAM_fundo"], r["verificacao"]
        ativo = r["ativo"] if isinstance(r["ativo"], str) else ""
        t = tri.loc[(d, f)] if tri is not None and (d, f) in tri.index else None
        base = dict(data=d, fundo=f, verificacao=v, diagnostico=r["diagnostico"], ativo=ativo, dif_antes=r["dif_rs"],
                    classe=None if t is None else t["classe"], pl_triagem=np.nan if t is None else t["pl"])
        do_fundo = oc[(oc["data"] == d) & (oc["fundo"] == f)]
        escolhida = do_fundo[(do_fundo["verificacao"] == v) & (do_fundo["ativo"] == ativo)]
        e = escolhida.iloc[0] if len(escolhida) else None
        linha = dict(tipo=_campo(e, "tipo_linha"), contraparte=_campo(e, "contraparte_linha"))
        origem = [(x.data_origem, ativo, x.script_origem) for x in escolhida.itertuples() if pd.notna(x.data_origem)]

        if v == "PRECO_FERIADO":
            nivel = AUTOMATICA if r["status"] == "confirmado" else REVISAR
            plano.append(Correcao(**base, nivel=nivel, delta=escolhida["ajuste_rs"].sum(), origem=origem,
                                  nota="Tira da linha do ativo a variação da linha de preço do feriado, somada duas "
                                       "vezes. Sem tirar a linha de origem, um reprocessamento traz o erro de volta."))
        elif v == "OUTRAS_DESPESAS_ESPECIE":
            plano.append(Correcao(**base, **linha, nivel=AUTOMATICA, delta=r["ajuste_rs"],
                                  nota="Zera o PnL da linha: a contrapartida da integralização/resgate em espécie é "
                                       "fluxo de cotista. A carga continua lançando isso a cada integralização."))
        elif v == "PNL_FORA_PRECO":
            nivel = AUTOMATICA if r["status"] == "explica" else REVISAR
            plano.append(Correcao(**base, **linha, nivel=nivel, delta=r["ajuste_rs"],
                                  nota="Leva o pnl_moeda_ativo a quantidade × variação do preço × câmbio da linha."))
        elif v == "DIFERENCA_IGUAL_SALDO":
            portadora = do_fundo[do_fundo["verificacao"].isin(["LINHA_EXPLICA", "LINHA_SEM_SALDO"])]
            if len(portadora):
                p = portadora.iloc[0]
                sem_saldo = bool(p["sem_saldo"]) if pd.notna(p["sem_saldo"]) else False
                plano.append(Correcao(**{**base, "ativo": p["ativo"]}, tipo=_campo(p, "tipo_linha"),
                                      contraparte=_campo(p, "contraparte_linha"),
                                      nivel=AUTOMATICA if sem_saldo else REVISAR, delta=r["ajuste_rs"],
                                      nota=f"A diferença é o saldo de {ativo}; sai da linha {p['ativo']}, que carrega o "
                                           "PnL a mais. Volta todo dia até corrigir a carga"
                                           + ("." if sem_saldo else ". A linha tem saldo: conferir antes.")))
            else:
                plano.append(Correcao(**base, nivel=SEM_SQL,
                                      nota="Não achei a linha que carrega o PnL a mais: corrigir à mão."))
        elif v in ("FLUXO_FORA_MERCADO", "LINHA_EXPLICA", "LINHA_SEM_SALDO"):
            plano.append(Correcao(**base, **linha, nivel=REVISAR, delta=r["ajuste_rs"],
                                  nota=f"Conferir antes de aplicar: {r['acao']}"))
        elif v == "SEM_POSICAO":
            plano.append(Correcao(**base, nivel=SEM_SQL, runproject=_runproject(d, f),
                                  nota="Reprocessar a posição só se o código deve ter posição própria; se o PnL está "
                                       "no código de origem, não há o que corrigir na posição."))
        else:
            plano.append(Correcao(**base, nivel=SEM_SQL, nota=r["acao"]))

    vistos = set()
    for _, a in oc[oc["verificacao"] == "PRECO_FERIADO_ALERTA"].iterrows():
        plano.append(Correcao(data=a["data"], fundo=a["fundo"], verificacao=a["verificacao"],
                              diagnostico=a["titulo"], nivel=PREVENCAO, ativo=a["ativo"], delta=a["ajuste_rs"],
                              origem=[] if (a["data_origem"], a["ativo"], a["script_origem"]) in vistos else
                              [(a["data_origem"], a["ativo"], a["script_origem"])], nota=a["acao"]))
        vistos.add((a["data_origem"], a["ativo"], a["script_origem"]))
    return plano


def _num1(v):
    try:
        return np.nan if v is None or pd.isna(v) else float(v)
    except (TypeError, ValueError):
        return np.nan


def _valor(x, col, nome):
    return _num1(x[col[nome]]) if nome in col else np.nan


def _perto(a, b):
    return pd.notna(a) and pd.notna(b) and abs(a - b) < 0.01


def _alvos(c, pnl):
    """Registros que a correção muda e o ajuste de cada um, ou o motivo de não dar para fazer sozinho."""
    if len(pnl) == 1:
        i = pnl.index[0]
        if pd.isna(pnl[i]):
            return [], {}, "linha sem pnl_total"
        return [i], {i: -pnl[i] if c.verificacao in ZERA else c.delta}, ""
    com_pnl = [i for i in pnl.index if pd.notna(pnl[i]) and abs(pnl[i]) >= 0.01]
    if c.verificacao in ZERA and com_pnl:          # zera cada registro com PnL
        return com_pnl, {i: -pnl[i] for i in com_pnl}, ""
    if len(com_pnl) == 1:                           # o ajuste vai para o único registro com PnL
        return com_pnl, {com_pnl[0]: c.delta}, ""
    return [], {}, f"linha em {len(pnl)} registros{' com PnL' if com_pnl else ''}: corrigir à mão"


def _norm(v, nome):
    """Valor comparável de uma coluna de IDENTIDADE: texto, número arredondado, None (NULL) ou _FORA."""
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, (bool, np.bool_)):
        return _FORA
    if isinstance(v, (int, float, np.integer, np.floating)):
        return round(float(v), 2 if nome.lower().startswith("total") else 6)
    return _FORA


def _separa(sel, cp, tp, alvos, antes, depois, col):
    """Colunas de IDENTIDADE que, com contraparte, tipo e o PnL de antes/depois, deixam cada registro alvo único
    entre os registros da linha (o UPDATE e a reversão acertam um só, em qualquer ordem). None se não há."""
    idx = list(sel.index)
    cands = [col[k] for k in IDENTIDADE if k in col]
    vals = {k: {i: _norm(sel.at[i, k], k) for i in idx} for k in cands}
    cands = [k for k in cands if all(v is not _FORA for v in vals[k].values()) and len(set(vals[k].values())) > 1]

    def unicos(cols):
        ch = {i: (cp[i], tp[i]) + tuple(vals[k][i] for k in cols) for i in idx}
        return not any(o != t and ch[o] == ch[t]
                       and (_perto(antes[o], antes[t]) or _perto(depois[o], depois[t])
                            or _perto(depois[o], antes[t]) or _perto(antes[o], depois[t]))
                       for t in alvos for o in idx)

    usadas = []
    for k in [None] + cands:
        if k is not None:
            usadas.append(k)
        if unicos(usadas):
            return {t: {k: vals[k][t] for k in usadas} for t in alvos}
    return None


def _componente(c, x, col):
    """Coluna de componente que também recebe o ajuste: pnl_moeda_ativo nos ajustes de preço; nos outros, a que
    carrega todo o PnL do registro (numa coluna zerada, o ajuste criaria PnL onde não havia)."""
    if c.verificacao in PRECO:
        nomes = ("pnl_moeda_ativo",)
    elif pd.notna(c.pnl_total) and abs(c.pnl_total) >= 0.01:
        nomes = tuple(k for k in COMPONENTES if _perto(_valor(x, col, k), c.pnl_total))
    else:
        nomes = ()
    for k in nomes:
        v = _valor(x, col, k)
        if pd.notna(v):
            return k, v, _valor(x, col, k + "_perc")
    return "", np.nan, np.nan


def _preenche(c, x, col, tipo, contraparte):
    c.tipo, c.contraparte = tipo, contraparte
    c.pnl_total, c.pnl_total_perc = _valor(x, col, "pnl_total"), _valor(x, col, "pnl_total_perc")
    c.componente, c.comp_valor, c.comp_perc = _componente(c, x, col)
    pl = _valor(x, col, "last_patrimonio")
    c.pl = pl if pd.notna(pl) and pl > 0 else c.pl_triagem
    if pd.isna(c.pnl_total):
        c.situacao = "linha sem pnl_total"
    elif not (pd.notna(c.pl) and c.pl > 0):
        c.situacao = "sem PL para recalcular o percentual"
    else:
        c.situacao, c.preparada = "pronta", True


def busca_linhas(fonte, plano):
    """Busca os registros de cada correção na VW_FUNDOS_POSICAO e guarda os valores de antes. Uma linha em vários
    registros vira uma correção por registro com PnL. Troca o plano no lugar (os blocos do SQL seguem a nova
    ordem) e devolve o backup (os registros da linha, com o bloco e se o registro muda)."""
    novo, backup = [], []
    for c in plano:
        if c.nivel not in (AUTOMATICA, REVISAR) or not c.ativo or pd.isna(c.delta):
            novo.append(c)
            continue
        df = fonte.linhas_alvo(c.data, c.fundo, c.ativo)
        if df is None or df.empty:
            c.situacao = "linha não encontrada"
            novo.append(c)
            continue
        col = {str(k).lower(): k for k in df.columns}
        cp = df[col["contraparte"]].fillna("-").astype(str)
        tp = df[col["tipo"]].fillna("").astype(str)
        if c.tipo is not None and c.contraparte is not None:
            m = (cp == str(c.contraparte)) & (tp == str(c.tipo))
        else:                                   # linha do ativo: fora ajuste manual e caixa/CPR do mesmo código
            m = (cp != AJUSTE_MANUAL) & ~tp.str.lower().str.startswith("caixa")
        sel = df[m]
        if sel.empty:
            c.situacao = "linha não encontrada"
            novo.append(c)
            continue
        pnl = sel[col["pnl_total"]].map(_num1)
        alvos, deltas, motivo = _alvos(c, pnl)
        if not motivo and c.verificacao in ZERA and abs(sum(deltas.values()) - c.delta) > 0.01:
            motivo = (f"o PnL da linha mudou desde o diagnóstico ({rs(-c.delta)} → {rs(-sum(deltas.values()))}): "
                      "rode de novo")
        filtros = None
        if not motivo:
            antes = pnl.to_dict()
            depois = {i: antes[i] + deltas.get(i, 0.0) for i in sel.index}
            filtros = _separa(sel, cp, tp, alvos, antes, depois, col)
            if filtros is None:
                motivo = f"linha em {len(sel)} registros que nada separa: corrigir à mão"
        primeiro = len(novo) + 1
        if motivo:
            c.situacao = motivo
            novo.append(c)
            alvos = []
        else:
            for k, i in enumerate(alvos, start=1):
                n = replace(c, delta=deltas[i], filtro=filtros[i], origem=c.origem if k == 1 else [],
                            parte=f"{k}/{len(alvos)}" if len(alvos) > 1 else "")
                _preenche(n, sel.loc[i], col, tp[i], cp[i])
                novo.append(n)
        backup.append(sel.assign(correcao=[primeiro + alvos.index(i) if i in alvos else primeiro for i in sel.index],
                                 alterado=["sim" if i in alvos else "não" for i in sel.index]))
    plano[:] = novo
    return pd.concat(backup, ignore_index=True) if backup else pd.DataFrame()


# ── SQL ─────────────────────────────────────────────────────────────────────────────────────────────────────

def _n(x):
    return repr(float(x))


def _s(x):
    return "'" + str(x).replace("'", "''") + "'"


def _d(x):
    return f"'{pd.Timestamp(x):%Y-%m-%d}'"


def _cond_filtro(nome, v, parametros):
    """Condição de uma coluna que separa o registro: NULL, texto igual ou número com tolerância."""
    if v is None:
        return f"{nome} IS NULL", []
    if isinstance(v, str):
        return f"{nome} = {'?' if parametros else _s(v)}", [v]
    tol = "0.01" if nome.lower().startswith("total") else "0.000001"
    return f"ABS({nome} - ({'?' if parametros else _n(v)})) < {tol}", [float(v)]


def _where(c, guarda_total, guarda_comp, parametros):
    if parametros:
        val, txt, dat = (lambda x: "?"), (lambda x: "?"), (lambda x: "?")
    else:
        val, txt, dat = _n, _s, _d
    cond = [f"date = {dat(c.data)}", f"codigo_IAM_fundo = {txt(c.fundo)}", f"codigo_IAM_ativo = {txt(c.ativo)}",
            f"ISNULL(contraparte, '-') = {txt(c.contraparte)}", f"ISNULL(tipo, '') = {txt(c.tipo)}"]
    params = [pd.Timestamp(c.data).date(), c.fundo, c.ativo, c.contraparte, c.tipo]
    for nome, v in c.filtro.items():
        s, p = _cond_filtro(nome, v, parametros)
        cond.append(s)
        params += p
    cond.append(f"ABS(pnl_total - ({val(guarda_total)})) < 0.01")
    params.append(float(guarda_total))
    if c.componente and pd.notna(guarda_comp):
        cond.append(f"ABS({c.componente} - ({val(guarda_comp)})) < 0.01")
        params.append(float(guarda_comp))
    return "\n   AND ".join(cond), params


def sql_update(c, parametros=False):
    """UPDATE que soma o ajuste ao PnL do registro (só se ele ainda tiver os valores do diagnóstico)."""
    v = (lambda x: "?") if parametros else _n
    sets, params = [f"pnl_total = pnl_total + ({v(c.delta)})"], [float(c.delta)]
    if pd.notna(c.pnl_total_perc):
        sets.append(f"pnl_total_perc = pnl_total_perc + ({v(c.delta_perc)})")
        params.append(float(c.delta_perc))
    if c.componente and pd.notna(c.comp_valor):
        sets.append(f"{c.componente} = {c.componente} + ({v(c.delta)})")
        params.append(float(c.delta))
        if pd.notna(c.comp_perc):
            sets.append(f"{c.componente}_perc = {c.componente}_perc + ({v(c.delta_perc)})")
            params.append(float(c.delta_perc))
    where, wp = _where(c, c.pnl_total, c.comp_valor, parametros)
    return "UPDATE VW_FUNDOS_POSICAO\n   SET " + ",\n       ".join(sets) + "\n WHERE " + where, params + wp


def sql_reverte(c):
    """UPDATE que devolve o registro aos valores de antes (só se ele ainda tiver os valores corrigidos)."""
    sets = [f"pnl_total = {_n(c.pnl_total)}"]
    if pd.notna(c.pnl_total_perc):
        sets.append(f"pnl_total_perc = {_n(c.pnl_total_perc)}")
    guarda_comp = np.nan
    if c.componente and pd.notna(c.comp_valor):
        sets.append(f"{c.componente} = {_n(c.comp_valor)}")
        guarda_comp = c.comp_valor + c.delta
        if pd.notna(c.comp_perc):
            sets.append(f"{c.componente}_perc = {_n(c.comp_perc)}")
    where, _ = _where(c, c.pnl_total + c.delta, guarda_comp, False)
    return "UPDATE VW_FUNDOS_POSICAO\n   SET " + ",\n       ".join(sets) + "\n WHERE " + where


SQL_CONFERENCIA = """
SELECT c.fundo_pnl AS pnl_cota,
       (SELECT SUM(p.pnl_total) FROM VW_FUNDOS_POSICAO p WITH (NOLOCK)
         WHERE p.date = c.date AND p.codigo_IAM_fundo = c.codigo_IAM_fundo) AS pnl_posicao
FROM VW_FUNDOS_COTAS_PL c WITH (NOLOCK)
WHERE c.date = ? AND c.codigo_IAM_fundo = ? AND c.classe = ?"""


def esperadas(plano, com_revisao):
    """Diferença esperada depois, por (data, fundo): a de antes menos os ajustes que entram."""
    out = {}
    for c in plano:
        if c.no_script(com_revisao):
            k = (c.data, c.fundo)
            ant = out.get(k, (c.dif_antes, c.classe))[0]
            out[k] = (ant - c.delta, c.classe)
    return out


def _sql_conferencia_lote(esp, antes):
    linhas = [f"({_d(d)}, {_s(f)}, {_s(classe)}, {antes[(d, f)]:.2f}, {depois:.2f})"
              for (d, f), (depois, classe) in esp.items() if classe is not None and pd.notna(classe)]
    if not linhas:
        return "-- (sem fundo para conferir)"
    return ("SELECT v.data, v.fundo, v.diferenca_antes, v.diferenca_esperada,\n"
            "       c.fundo_pnl - p.pnl_posicao AS diferenca_depois,\n"
            f"       CASE WHEN ABS((c.fundo_pnl - p.pnl_posicao) - v.diferenca_esperada) <= {_n(TOLERANCIA_RS)}\n"
            "            THEN 'ok' ELSE 'CONFERIR' END AS situacao\n"
            "FROM (VALUES\n       " + ",\n       ".join(linhas) + "\n"
            "     ) v (data, fundo, classe, diferenca_antes, diferenca_esperada)\n"
            "JOIN VW_FUNDOS_COTAS_PL c WITH (NOLOCK)\n"
            "  ON c.date = CAST(v.data AS DATE) AND c.codigo_IAM_fundo = v.fundo AND c.classe = v.classe\n"
            "CROSS APPLY (SELECT SUM(x.pnl_total) AS pnl_posicao FROM VW_FUNDOS_POSICAO x WITH (NOLOCK)\n"
            "             WHERE x.date = c.date AND x.codigo_IAM_fundo = c.codigo_IAM_fundo) p\n"
            "ORDER BY v.data, v.fundo;")


def _comenta(txt):
    return "\n".join("-- " + l if l.strip() else "--" for l in txt.splitlines())


def _filtro_txt(c):
    return ", ".join(f"{k} = {'NULL' if v is None else v}" for k, v in c.filtro.items())


def no_script(c, com_revisao):
    """sim: o UPDATE roda; comentado: [revisar] pronto, fora sem --com-revisao; não: sem UPDATE."""
    if c.no_script(com_revisao):
        return "sim"
    return "comentado" if c.preparada and c.nivel == REVISAR else "não"


def fora_do_script(plano, com_revisao):
    """Correções (fora as de prevenção) que o script não aplica, com o motivo."""
    out = []
    for c in plano:
        if c.nivel == PREVENCAO or c.no_script(com_revisao):
            continue
        if c.preparada and c.nivel == REVISAR:
            motivo = "[revisar] UPDATE comentado: confira e use --com-revisao"
        elif c.situacao and not c.pronta:
            motivo = c.situacao
        else:
            motivo = f"[{c.nivel}] " + (c.nota or "").split(". ")[0].rstrip(".")
        out.append((c, motivo))
    return out


def _cabecalho_bloco(i, c):
    linha = f" ({c.tipo})" if c.tipo else ""
    parte = f" | registro {c.parte}" if c.parte else ""
    out = [f"-- {'-' * 100}",
           f"-- {i}) {c.fundo} | {dt(c.data)} | {c.ativo or '-'}{linha}{parte} | {c.diagnostico} [{c.nivel}]"]
    if pd.notna(c.delta):
        depois = c.dif_antes - c.delta if pd.notna(c.dif_antes) else np.nan
        out.append(f"--    diferença antes {rs(c.dif_antes)} | ajuste no PnL {'do registro' if c.parte else 'da linha'} "
                   f"{rs(c.delta)} | diferença esperada depois "
                   + (f"{rs(depois)}" if not c.parte else "(soma dos registros: veja a conferência)"))
    if c.filtro:
        out.append(f"--    registro separado por: {_filtro_txt(c)}")
    if c.pronta and not c.componente and c.verificacao not in PRECO:
        out.append("--    só pnl_total(_perc): nenhum componente (pnl_moeda_ativo...) carrega todo o PnL do registro.")
    if c.situacao and not c.pronta:
        out.append(f"--    !! {c.situacao}: sem UPDATE.")
    for frase in (c.nota or "").split(". "):
        if frase.strip():
            out.append(f"--    {frase.strip().rstrip('.')}.")
    out.append(f"-- {'-' * 100}")
    return out


def _origens(c):
    """DELETE comentado das linhas de preço de feriado que causaram a diferença."""
    out = []
    for data_o, ativo_o, script_o in c.origem:
        if pd.isna(data_o) or not script_o:
            continue
        out.append("-- Origem (opcional; só se ninguém mais usa essa linha de preço):")
        out.append(f"-- DELETE FROM FUNDOS_DADOS_ATIVOS WHERE date = {_d(data_o)} AND codigo_IAM_ativo = "
                   f"{_s(ativo_o)} AND log_script_from = {_s(script_o)};")
    return out


def script_correcao(plano, titulo, com_revisao=False, arquivos=""):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    out = [f"-- {'=' * 100}",
           f"-- Correção do batimento cota × posição — {titulo}",
           f"-- Gerado em {agora} pelo batimento/correcao.py, a partir do diagnóstico do mesmo momento. {arquivos}",
           "--",
           "-- Como usar: rode o script inteiro no SSMS. Ele faz as correções dentro de uma transação, mostra a",
           "-- conferência cota × posição e termina em ROLLBACK. Se a coluna situacao vier 'ok' em todos os fundos e",
           "-- não houver mensagem de ERRO, troque o ROLLBACK do fim por COMMIT e rode de novo.",
           "-- Cada UPDATE só muda a linha se ela ainda tiver os valores do diagnóstico (ABS(...) < 0.01): se alguém",
           "-- reprocessou o fundo depois, a linha não muda, o script conta um erro e o certo é gerar de novo.",
           f"-- Blocos [revisar] saem comentados{' (aqui incluídos: --com-revisao)' if com_revisao else ''}; "
           "[sem SQL] e [prevenção] são só orientação.",
           f"-- {'=' * 100}"]
    dentro = [c for c in plano if c.entra(com_revisao)]
    fora = fora_do_script(plano, com_revisao)
    out.append(f"-- No script: {len(dentro)} UPDATE(s) em {len({(c.data, c.fundo) for c in dentro})} fundo(s)/data(s). "
               + (f"Fora: {len(fora)} (corrigir à mão ou conferir antes):" if fora else "Fora: nenhuma."))
    for c, motivo in fora:
        out.append(f"--   {dt(c.data)} {c.fundo:<16} {c.diagnostico}: {motivo}")
    out += [f"-- {'=' * 100}",
            "SET XACT_ABORT ON;",
            "BEGIN TRANSACTION;",
            "DECLARE @erros INT = 0;",
            ""]
    for i, c in enumerate(plano, start=1):
        out += _cabecalho_bloco(i, c)
        if c.pronta and c.nivel in (AUTOMATICA, REVISAR):
            sql, _ = sql_update(c)
            bloco = (sql + ";\n"
                     f"IF @@ROWCOUNT <> 1 BEGIN SET @erros = @erros + 1; "
                     f"PRINT {_s(f'ERRO no bloco {i}: {c.fundo}/{c.ativo} mudou desde o diagnóstico ou não é única.')};"
                     " END;")
            out.append(bloco if c.entra(com_revisao) else _comenta(bloco))
        if c.runproject:
            out.append("-- Reprocessar a posição (Python, RunProject):")
            out.append(_comenta(c.runproject))
        out += _origens(c)
        out.append("")
    antes = {(c.data, c.fundo): c.dif_antes for c in plano}
    out += [f"-- {'=' * 100}",
            "-- Conferência dentro da transação: a diferença depois tem de ser a esperada (situacao = 'ok').",
            f"-- {'=' * 100}",
            _sql_conferencia_lote(esperadas(plano, com_revisao), antes),
            "",
            "IF @erros > 0 PRINT 'Houve ' + CAST(@erros AS VARCHAR(10)) + ' erro(s): NÃO troque o ROLLBACK por COMMIT.';",
            "ROLLBACK TRANSACTION;   -- <<< depois de conferir, troque por COMMIT TRANSACTION",
            ""]
    return "\n".join(out)


def script_reversao(plano, titulo, com_revisao=False):
    out = [f"-- {'=' * 100}",
           f"-- Reversão da correção do batimento — {titulo}",
           f"-- Gerado em {datetime.now():%d/%m/%Y %H:%M}. Volta cada linha corrigida aos valores de antes, só se ela",
           "-- ainda tiver os valores corrigidos. Termina em ROLLBACK: troque por COMMIT para gravar.",
           f"-- {'=' * 100}",
           "SET XACT_ABORT ON;",
           "BEGIN TRANSACTION;",
           "DECLARE @erros INT = 0;",
           ""]
    n = 0
    for i, c in enumerate(plano, start=1):
        if not c.entra(com_revisao):
            continue
        n += 1
        parte = f" | registro {c.parte}" if c.parte else ""
        out += [f"-- {i}) {c.fundo} | {dt(c.data)} | {c.ativo} ({c.tipo}){parte} | volta o PnL a {rs(c.pnl_total)}",
                sql_reverte(c) + ";",
                f"IF @@ROWCOUNT <> 1 BEGIN SET @erros = @erros + 1; PRINT {_s(f'ERRO no bloco {i}: {c.fundo}/{c.ativo}')};"
                " END;", ""]
    if not n:
        out.append("-- (nenhuma correção para reverter)")
    out += ["IF @erros > 0 PRINT 'Houve ' + CAST(@erros AS VARCHAR(10)) + ' erro(s): NÃO troque o ROLLBACK por COMMIT.';",
            "ROLLBACK TRANSACTION;   -- <<< troque por COMMIT TRANSACTION para gravar", ""]
    return "\n".join(out)


def tabela_plano(plano, com_revisao=False):
    esp = esperadas(plano, com_revisao)
    motivos = {id(c): m for c, m in fora_do_script(plano, com_revisao)}
    linhas = []
    for i, c in enumerate(plano, start=1):
        if (c.data, c.fundo) in esp and c.no_script(com_revisao):
            depois = esp[(c.data, c.fundo)][0]          # do fundo, com todos os registros
        elif c.nivel in (AUTOMATICA, REVISAR) and pd.notna(c.dif_antes) and pd.notna(c.delta):
            depois = c.dif_antes - c.delta
        else:
            depois = np.nan
        como = c.runproject or "; ".join(
            f"DELETE da linha de {dt(o[0])} do {o[1]} ({o[2]}) na FUNDOS_DADOS_ATIVOS (opcional)"
            for o in c.origem if pd.notna(o[0]))
        linhas.append({"bloco": i, "data": c.data, "fundo": c.fundo, "ativo": c.ativo,
                       "linha": f"{c.tipo} / {c.contraparte}" if c.tipo else "", "registro": c.parte,
                       "filtro": _filtro_txt(c), "diagnostico": c.diagnostico, "nivel": c.nivel,
                       "situacao": c.situacao, "no_script": no_script(c, com_revisao),
                       "motivo": motivos.get(id(c), ""), "dif_antes": c.dif_antes, "ajuste": c.delta,
                       "dif_esperada": depois, "dif_depois": c.dif_depois, "conferencia": c.conferencia,
                       "componente": c.componente, "nota": c.nota, "como": como, "pnl_antes": c.pnl_total})
    return pd.DataFrame(linhas)


# ── aplicação ───────────────────────────────────────────────────────────────────────────────────────────────

class TransacaoSQL:
    """As atualizações numa transação pyodbc (autocommit desligado no sql_connection.py)."""

    def __init__(self, conexao):
        self.conn = conexao
        self.cur = conexao.cursor()

    def atualiza(self, c):
        sql, params = sql_update(c, parametros=True)
        self.cur.execute(sql, params)
        return self.cur.rowcount

    def confere(self, data, fundo, classe):
        self.cur.execute(SQL_CONFERENCIA, [pd.Timestamp(data).date(), fundo, classe])
        row = self.cur.fetchone()
        return (float(row[0]), float(row[1])) if row and row[0] is not None and row[1] is not None else (np.nan, np.nan)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()


def aplica(tx, plano, com_revisao=False, confirmar=input, log=print):
    """Aplica as correções prontas, confere cota × posição e grava só se tudo bater e houver confirmação."""
    alvo = [c for c in plano if c.entra(com_revisao)]
    if not alvo:
        log("Nenhuma correção pronta para aplicar.")
        return "nada"
    try:
        erros = 0
        for c in alvo:
            n = tx.atualiza(c)
            if n != 1:
                c.situacao, erros = f"não aplicada: {n} linha(s) com os valores do diagnóstico", erros + 1
        if erros:
            tx.rollback()
            log(f"{erros} correção(ões) não acharam a linha com os valores do diagnóstico: desfeito (ROLLBACK). "
                "Rode o diagnóstico de novo.")
            for c in alvo:
                if c.pronta:
                    c.situacao = "desfeita"
            return "desfeito"
        tudo_ok = True
        for (d, f), (esperada, classe) in esperadas(plano, com_revisao).items():
            cota, posicao = tx.confere(d, f, classe)
            depois = cota - posicao
            ok = pd.notna(depois) and abs(depois - esperada) <= TOLERANCIA_RS
            tudo_ok &= ok
            log(f"  {f:<16} {dt(d)}  diferença depois {rs(depois):>18}  esperada {rs(esperada):>16}  "
                f"{'ok' if ok else 'NÃO BATE'}")
            for c in alvo:
                if (c.data, c.fundo) == (d, f):
                    c.dif_depois, c.conferencia = depois, "ok" if ok else "não bate"
        if not tudo_ok:
            tx.rollback()
            log("A conferência não bateu: desfeito (ROLLBACK).")
            for c in alvo:
                c.situacao = "desfeita"
            return "desfeito"
        try:
            resposta = confirmar(f"{len(alvo)} correção(ões) conferida(s); as linhas ficam travadas até a resposta. "
                                 "Digite SIM para gravar (COMMIT): ")
        except EOFError:
            resposta = ""
        if str(resposta).strip().upper() == "SIM":
            tx.commit()
            for c in alvo:
                c.situacao = "aplicada"
            log("Gravado (COMMIT).")
            return "gravado"
        tx.rollback()
        for c in alvo:
            c.situacao = "desfeita (sem confirmação)"
        log("Sem confirmação: desfeito (ROLLBACK).")
        return "desfeito"
    except Exception:
        tx.rollback()
        for c in alvo:
            c.situacao = "desfeita (erro)"
        raise
