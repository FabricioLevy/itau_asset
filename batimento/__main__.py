# ─────────────────────────────────────────────
# batimento/__main__.py
# Batimento diário cota × posição: compara o PnL da cota (VW_FUNDOS_COTAS_PL) com a soma do PnL da posição
# (VW_FUNDOS_POSICAO) de cada fundo e, nos fundos que não batem, procura a causa linha a linha e na tabela de
# preços (FUNDOS_DADOS_ATIVOS). As verificações saíram das quebras da INDEXADOS em out/2026.
#
# Triagem (todos os fundos do escopo)
#   diferença = PnL da cota − PnL da posição; o fundo entra com |diferença| >= --limiar-bps E >= --limiar-rs, ou
#   se tem cota e nenhuma posição (SEM POSIÇÃO), ou posição sem a cota que tinha antes (SEM COTA). Fundo com
#   várias classes: usa a classe Total, senão A, senão a de maior PL. Recorrência: em quantas das --janela datas
#   anteriores o fundo também entrou.
#
# Verificações nos fundos que entraram (detectores.py; descrição completa na aba Leia-me do Excel)
#   OUTRAS_DESPESAS_ESPECIE  linha sem saldo (uma ou várias) com o PnL da diferença, que é a contrapartida de uma
#                            integralização/resgate em espécie (ETF): confere pelos ativos que entraram/saíram, pelo
#                            fluxo das outras linhas ou, na OUTRAS_DESPESAS, pelo padrão (fecha em até 0,1%)
#   LINHA_EXPLICA            tirando o PnL de uma única linha, a posição bate com a cota
#   DIFERENCA_IGUAL_SALDO    a diferença é igual ao saldo de uma linha de caixa/CPR/despesa (saldo virando PnL)
#   FLUXO_FORA_MERCADO       entrada/saída de ativo registrada por valor muito diferente do de mercado
#   PNL_FORA_PRECO           pnl_moeda_ativo ≠ quantidade × (preço − preço anterior) × câmbio da linha
#   LINHA_SEM_SALDO          linha sem saldo no dia e no anterior com PnL relevante
# Na tabela de preços (todos os fundos do escopo)
#   PRECO_FERIADO            linha de preço num feriado que a linha do dia seguinte ignora: a posição soma as
#                            duas variações (3GALABIT/BITI11 em 18/02, 08/09 e 13/10/2026). Confirma pela
#                            diferença do fundo e reconhece o ajuste manual (contraparte ajuste_pnl) já lançado.
#   PRECO_FERIADO_ALERTA     linha de feriado de um script de --scripts-alerta gravada depois da última posição:
#                            avisa antes de a próxima posição contar duas vezes.
#   PRECO_ZERO / PRECO_SALTO / PRECO_DUPLICADO   linhas suspeitas de ativos em carteira (aba Preços)
#   AJUSTE_MANUAL            ajustes manuais de PnL já lançados no dia
#
# Fontes (DBSX337 pelo sql_connection.py desta pasta, credenciais SQL_LOGIN e SQL_PASSWORD; todas as leituras
#   WITH (NOLOCK)): VW_FUNDOS_COTAS_PL, VW_FUNDOS_POSICAO, FUNDOS_DADOS_ATIVOS.
#
# Saída: output/batimento_<aaaammdd>.xlsx (com --de/--ate, batimento_<de>_<ate>.xlsx) — abas Resumo (um fundo por
#   linha, com a causa mais provável, o ajuste sugerido e o resíduo), Ocorrências, Triagem, Preços, Correções (com
#   --corrigir), Avisos (etapas que falharam) e Leia-me. Erro numa etapa não para as outras: vira aviso.
#
# Correção (correcao.py; nada é gravado no banco sem --aplicar e um SIM digitado)
#   --corrigir      gera output/correcao_<...>.sql (BEGIN TRANSACTION, UPDATE com trava no valor atual da linha,
#                   conferência cota × posição e ROLLBACK no fim), reverter_<...>.sql e backup_<...>.xlsx (as
#                   linhas antes). Automáticas: OUTRAS_DESPESAS_ESPECIE, PRECO_FERIADO confirmado, PNL_FORA_PRECO e
#                   DIFERENCA_IGUAL_SALDO. As outras saem comentadas ([revisar]) ou só como orientação.
#   --aplicar       roda as automáticas numa transação, confere cota × posição de cada fundo e grava (COMMIT) só se
#                   todas baterem e alguém digitar SIM; senão ROLLBACK. Os arquivos acima são gravados antes.
#   --com-revisao   inclui as correções [revisar] no script e no --aplicar.
#
# Requisitos: ODBC Driver 18 for SQL Server, pyodbc, sqlalchemy, pandas, openpyxl. Testes: pytest tests/
#
# Uso (de dentro de batimento/, ou "python batimento" a partir de itau_asset/):
#   python __main__.py                                  (última data com cota, todos os fundos)
#   python __main__.py --data 13/10/2026 --mesa INDEXADOS
#   python __main__.py --de 01/10/2026 --ate 30/10/2026 --mesa INDEXADOS
#   python __main__.py --fundo ITAUBLO66606 ITAUIMA5P2070 --data 13/10/2026
#   python __main__.py --limiar-bps 2 --limiar-rs 500 -v (-v mostra cada consulta e o tempo)
#   python __main__.py --data 13/10/2026 --mesa INDEXADOS --corrigir    (só gera os scripts)
#   python __main__.py --data 13/10/2026 --fundo ITAUBLO66606 --aplicar (aplica, confere e pede SIM)
# ─────────────────────────────────────────────

import argparse
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime

import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)

import detectores as det                                    # noqa: E402
from detectores import Parametros, dt, num_br, rs            # noqa: E402

SAIDA_DIR = os.path.join(AQUI, "output")
JANELA_DIAS = 20       # dias corridos lidos antes da primeira data (posição anterior e recorrência)
DIAS_ULTIMA = 15       # sem --data: procura a última data com cota nos últimos 15 dias
FRACAO_FUNDOS = 0.3    # data com menos de 30% dos fundos da data típica não conta (fundo com outro calendário)


@dataclass
class Resultado:
    datas: list
    triagem: pd.DataFrame
    resumo: pd.DataFrame
    ocorrencias: pd.DataFrame
    precos: pd.DataFrame
    prm: Parametros
    escopo: str = "todos os fundos"
    avisos: list = field(default_factory=list)
    correcoes: pd.DataFrame = None      # plano de correção (--corrigir)


# ── datas ───────────────────────────────────────────────────────────────────────────────────────────────────

def datas_cheias(dc):
    if dc is None or dc.empty:
        return []
    lim = FRACAO_FUNDOS * dc["fundos"].median()
    return sorted(pd.Timestamp(x) for x in dc.loc[dc["fundos"] >= lim, "date"])


def escolhe_datas(fonte, data=None, de=None, ate=None, hoje=None):
    hoje = pd.Timestamp(hoje or date.today()).normalize()
    if data:
        return [pd.Timestamp(data)]
    if de or ate:
        return datas_cheias(fonte.datas_com_cota(pd.Timestamp(de or ate), pd.Timestamp(ate or hoje)))
    return datas_cheias(fonte.datas_com_cota(hoje - pd.Timedelta(days=DIAS_ULTIMA), hoje))[-1:]


# ── execução ────────────────────────────────────────────────────────────────────────────────────────────────

def roda(fonte, datas, prm, mesa=None, fundos=None, hoje=None, com_precos=True, log=print):
    hoje = pd.Timestamp(hoje or date.today()).normalize()
    datas = sorted(pd.Timestamp(d).normalize() for d in datas)
    escopo = ", ".join(x for x in (f"mesa {mesa}" if mesa else "", " ".join(fundos) if fundos else "") if x)
    res = Resultado(datas=datas, triagem=pd.DataFrame(), resumo=pd.DataFrame(), ocorrencias=pd.DataFrame(),
                    precos=pd.DataFrame(), prm=prm, escopo=escopo or "todos os fundos")
    ocorr, precos = [], []

    def etapa(nome, f):
        try:
            return f()
        except Exception as e:                       # uma etapa que falha não para as outras
            res.avisos.append(f"{nome}: {type(e).__name__}: {e}")
            log(f"  [AVISO] {nome}: {type(e).__name__}: {e}")
            return None

    ini = datas[0] - pd.Timedelta(days=JANELA_DIAS)
    log(f"Lendo cotas e posição de {dt(ini)} a {dt(datas[-1])} ({res.escopo})...")
    tri = det.triagem(fonte.cotas(ini, datas[-1], mesa, fundos), fonte.posicao_resumo(ini, datas[-1], mesa, fundos),
                      prm)

    for d in datas:
        tri_d = tri[tri["date"] == d]
        if tri_d.empty:
            res.avisos.append(f"{dt(d)}: sem cota nem posição no escopo.")
            log(f"{dt(d)}: sem cota nem posição no escopo.")
            continue
        marc = tri_d[tri_d["marcado"]]
        log(f"{dt(d)}: {int(tri_d['tem_cota'].sum())} fundos com cota, {len(marc)} acima do limite.")
        ocorr += det.ocorrencias_triagem(tri_d)

        alvo = marc[marc["tem_cota"] & marc["tem_posicao"]]
        if not alvo.empty:
            datas_linhas = [d] + list(alvo["data_anterior"].dropna().unique())
            linhas = etapa(f"{dt(d)} linhas da posição", lambda: det.prepara_linhas(
                fonte.posicao_linhas(alvo["codigo_IAM_fundo"].tolist(), datas_linhas)))
            if linhas is not None:
                for _, t in alvo.iterrows():
                    do_fundo = linhas[linhas["codigo_IAM_fundo"] == t["codigo_IAM_fundo"]]
                    ld = do_fundo[do_fundo["date"] == d]
                    lp = do_fundo[do_fundo["date"] == t["data_anterior"]] if pd.notna(t["data_anterior"]) \
                        else do_fundo.iloc[0:0]
                    ocorr += etapa(f"{dt(d)} {t['codigo_IAM_fundo']}", lambda: det.verifica_fundo(t, ld, lp, prm)) or []

        if (tri_d["pnl_ajuste_manual"].fillna(0) != 0).any():
            aj = etapa(f"{dt(d)} ajustes manuais", lambda: fonte.ajustes_manuais(d, d))
            if aj is not None and not aj.empty:
                ocorr += det.ocorrencias_ajustes(aj[aj["codigo_IAM_fundo"].isin(tri_d["codigo_IAM_fundo"])])

        if com_precos:
            anteriores = tri_d[tri_d["tem_posicao"]].set_index("codigo_IAM_fundo")["data_anterior"].dropna()
            if not anteriores.empty:
                ocorr += etapa(f"{dt(d)} preço de feriado",
                               lambda: _preco_feriado(fonte, d, anteriores, tri_d, prm)) or []
                p = etapa(f"{dt(d)} anomalias de preço",
                          lambda: _anomalias(fonte, d, anteriores.min(), set(tri_d["codigo_IAM_fundo"]), prm))
                if p is not None and not p.empty:
                    precos.append(p)

    ultima = tri[tri["date"] == datas[-1]]
    if com_precos and not ultima.empty:
        ocorr += etapa("alerta de feriado",
                       lambda: _alertas(fonte, datas[-1], hoje, set(ultima["codigo_IAM_fundo"]), prm)) or []

    res.triagem = tri[tri["date"].isin(datas)].reset_index(drop=True)
    res.ocorrencias = det.tabela_ocorrencias(ocorr).sort_values(["data", "fundo", "verificacao"], ignore_index=True)
    res.resumo = det.resumo(res.triagem, ocorr, prm)
    res.precos = pd.concat(precos, ignore_index=True) if precos else pd.DataFrame(columns=det.COLUNAS_PRECOS)
    return res


def _preco_feriado(fonte, d, anteriores, tri_d, prm):
    p_min = anteriores.min()
    h = fonte.precos_entre(p_min, d, d)
    if h.empty:
        return []
    pos = fonte.posicao_ativos_entre(d, p_min, d)
    pos = pos[pos["codigo_IAM_fundo"].isin(tri_d["codigo_IAM_fundo"])]
    return det.preco_feriado(d, pos, h, fonte.precos_do_dia(d, p_min, d), anteriores, tri_d, prm)


def _anomalias(fonte, d, p_min, fundos_escopo, prm):
    an = fonte.precos_anomalos(p_min, d, d, prm.salto_preco)
    du = fonte.precos_duplicados(p_min, d, d)
    ativos = sorted(set(an["codigo_IAM_ativo"]) | set(du["codigo_IAM_ativo"]))
    if not ativos:
        return pd.DataFrame(columns=det.COLUNAS_PRECOS)
    pos = fonte.posicao_ativos_lista(d, ativos)
    return det.anomalias_preco(an, du, pos[pos["codigo_IAM_fundo"].isin(fundos_escopo)], prm)


def _alertas(fonte, d, hoje, fundos_escopo, prm):
    fim = hoje + pd.Timedelta(days=1)
    fut = fonte.precos_entre(d, fim, d)
    if fut.empty or not fut["log_script_from"].isin(prm.scripts_alerta).any():
        return []
    pos = fonte.posicao_ativos_entre(d, d, fim)
    return det.alerta_feriado(d, hoje, pos[pos["codigo_IAM_fundo"].isin(fundos_escopo)], fut, prm)


# ── correção ────────────────────────────────────────────────────────────────────────────────────────────────

def corrige(fonte, res, pasta, base, com_revisao=False, aplicar=False, confirmar=input, log=print):
    """Plano, backup e scripts (sempre); com aplicar, a transação com conferência e confirmação."""
    import correcao as cor
    plano = cor.monta_plano(res)
    backup = cor.busca_linhas(fonte, plano)
    os.makedirs(pasta, exist_ok=True)
    stamp = datetime.now().strftime("%H%M%S")
    arq = {"correcao": os.path.join(pasta, f"correcao_{base}_{stamp}.sql"),
           "reverter": os.path.join(pasta, f"reverter_{base}_{stamp}.sql"),
           "backup": os.path.join(pasta, f"backup_{base}_{stamp}.xlsx")}
    titulo = f"{', '.join(dt(d) for d in res.datas)} ({res.escopo})"
    if not backup.empty:
        backup.to_excel(arq["backup"], index=False)
    else:
        arq.pop("backup")
    with open(arq["correcao"], "w", encoding="utf-8-sig") as f:
        f.write(cor.script_correcao(plano, titulo, com_revisao,
                                    f"Backup: {os.path.basename(arq.get('backup', '-'))}. "
                                    f"Reversão: {os.path.basename(arq['reverter'])}."))
    with open(arq["reverter"], "w", encoding="utf-8-sig") as f:
        f.write(cor.script_reversao(plano, titulo, com_revisao))
    estado = None
    if aplicar:
        log("")
        log("Aplicando as correções (transação; nada é gravado sem conferência e SIM):")
        try:
            estado = cor.aplica(cor.TransacaoSQL(fonte.conexao_escrita()), plano, com_revisao, confirmar, log)
        except Exception as e:                       # aplica já desfez a transação
            estado = "erro"
            msg = f"ao aplicar: {type(e).__name__}: {e}. Nada foi gravado (ROLLBACK)."
            res.avisos.append(msg)
            log(f"[ERRO] {msg}")
    res.correcoes = cor.tabela_plano(plano, com_revisao)
    return {"arquivos": arq, "estado": estado, "plano": plano}


# ── saída ───────────────────────────────────────────────────────────────────────────────────────────────────

def nome_arquivo(res, mesa=None, fundos=None):
    a, b = res.datas[0].strftime("%Y%m%d"), res.datas[-1].strftime("%Y%m%d")
    nome = f"batimento_{a}" if a == b else f"batimento_{a}_{b}"
    if mesa:
        nome += "_" + "".join(ch for ch in mesa if ch.isalnum())
    if fundos and len(fundos) == 1:
        nome += f"_{fundos[0]}"
    return nome + ".xlsx"


def imprime(res, caminho=None, log=print):
    for d in res.datas:
        r = res.resumo[res.resumo["date"] == d] if len(res.resumo) else res.resumo
        tri_d = res.triagem[res.triagem["date"] == d] if len(res.triagem) else res.triagem
        log("")
        log(f"Batimento {dt(d)} ({res.escopo}): {int(tri_d['tem_cota'].sum()) if len(tri_d) else 0} fundos com cota, "
            f"{len(r)} acima de {num_br(res.prm.limiar_bps)} bps e {rs(res.prm.limiar_rs)}")
        for _, x in r.iterrows():
            ajuste = f" | ajuste {rs(x['ajuste_rs'])}, resíduo {rs(x['residuo_rs'])}" if pd.notna(x["ajuste_rs"]) else ""
            ativo = f" {x['ativo']}" if x["ativo"] else ""
            status = f" ({x['status']})" if x["status"] else ""
            log(f"  {x['codigo_IAM_fundo']:<16} {num_br(x['dif_bps']):>10} bps {rs(x['dif_rs']):>20}  "
                f"{x['diagnostico']}{status}{ativo}{ajuste}")
    oc = res.ocorrencias
    alertas = oc[oc["verificacao"] == "PRECO_FERIADO_ALERTA"] if len(oc) else oc
    if len(alertas):
        log("")
        log("Alertas para a próxima posição:")
        for _, a in alertas.iterrows():
            log(f"  {a['fundo']:<16} {a['ativo']} ({dt(a['data'])}): ajuste provável {rs(a['ajuste_rs'])}")
    corrigidos = oc[oc["status"] == "corrigido"] if len(oc) else oc
    if len(corrigidos):
        log(f"Já corrigidos com ajuste manual: {', '.join(sorted(set(corrigidos['fundo'])))}")
    if len(res.precos):
        log(f"Tabela de preços: {len(res.precos)} linha(s) suspeita(s) (aba Preços).")
    if res.avisos:
        log(f"{len(res.avisos)} aviso(s): veja a aba Avisos.")
    if res.correcoes is not None and len(res.correcoes):
        c = res.correcoes
        log("")
        log("Correções (aba Correções):")
        for (nivel, situacao), n in c.groupby(["nivel", c["situacao"].replace("", "-")]).size().items():
            log(f"  {n:>3}  {nivel:<11} {situacao}")
        fora = c[(c["no_script"] != "sim") & (c["nivel"] != "prevenção")]
        if len(fora):
            log("")
            log(f"Fora do script ({len(fora)}): corrigir à mão ou conferir antes")
            for _, x in fora.iterrows():
                log(f"  {dt(x['data'])} {x['fundo']:<16} {x['diagnostico']}: {x['motivo']}")
    if caminho:
        log(f"Relatório: {caminho}")


# ── linha de comando ────────────────────────────────────────────────────────────────────────────────────────

def _data(s):
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(f"{s!r}: use dd/mm/aaaa")


def _numero(s):
    try:
        return float(s.replace(",", "."))
    except ValueError:
        raise argparse.ArgumentTypeError(f"{s!r}: número inválido") from None


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Batimento diário cota × posição dos fundos, com a causa das quebras.")
    ap.add_argument("--data", type=_data, help="data do batimento (dd/mm/aaaa); padrão: a última com cota")
    ap.add_argument("--de", type=_data, help="primeira data de um intervalo (todas as datas com cota)")
    ap.add_argument("--ate", type=_data, help="última data do intervalo (padrão: hoje)")
    ap.add_argument("--mesa", help="filtra a mesa de gestão (contém o texto; ex.: INDEXADOS)")
    ap.add_argument("--fundo", nargs="+", metavar="FUNDO", help="só esses fundos (codigo_IAM_fundo)")
    ap.add_argument("--limiar-bps", type=_numero, default=Parametros.limiar_bps,
                    help="diferença mínima em bps (padrão: %(default)s)")
    ap.add_argument("--limiar-rs", type=_numero, default=Parametros.limiar_rs,
                    help="diferença mínima em reais (padrão: %(default)s)")
    ap.add_argument("--janela", type=int, default=Parametros.janela,
                    help="datas anteriores olhadas na recorrência (padrão: %(default)s)")
    ap.add_argument("--salto-preco", type=_numero, default=Parametros.salto_preco,
                    help="variação de preço suspeita na tabela de preços (padrão: %(default)s = 30%%)")
    ap.add_argument("--tipos-pnl-preco", nargs="+", default=list(Parametros.tipos_pnl_preco), metavar="TIPO",
                    help="tipos da posição em que o PnL deve ser quantidade × variação × câmbio (padrão: Fund)")
    ap.add_argument("--scripts-alerta", nargs="+", default=list(Parametros.scripts_alerta), metavar="SCRIPT",
                    help="scripts cuja linha de preço em feriado vira alerta (padrão: CotaExternaD0.py)")
    ap.add_argument("--sem-precos", action="store_true", help="pula as verificações na FUNDOS_DADOS_ATIVOS")
    ap.add_argument("--corrigir", action="store_true",
                    help="gera o script de correção (termina em ROLLBACK), o de reversão e o backup das linhas")
    ap.add_argument("--aplicar", action="store_true",
                    help="aplica as correções automáticas numa transação, confere e grava só com SIM digitado")
    ap.add_argument("--com-revisao", action="store_true",
                    help="inclui as correções [revisar] (fluxo fora do mercado, linha que explica...)")
    ap.add_argument("--saida", default=SAIDA_DIR, help="pasta do Excel (padrão: batimento/output)")
    ap.add_argument("-v", "--verboso", action="store_true", help="mostra cada consulta, o tempo e as linhas")
    args = ap.parse_args(argv)
    if args.data and (args.de or args.ate):
        ap.error("use --data ou --de/--ate, não os dois")

    from consultas import FonteSQL
    prm = Parametros(limiar_bps=args.limiar_bps, limiar_rs=args.limiar_rs, janela=args.janela,
                     salto_preco=args.salto_preco, tipos_pnl_preco=tuple(args.tipos_pnl_preco),
                     scripts_alerta=tuple(args.scripts_alerta))
    fonte = FonteSQL(verboso=args.verboso)
    try:
        datas = escolhe_datas(fonte, args.data, args.de, args.ate)
        if not datas:
            print("Nenhuma data com cota no período.")
            return 1
        res = roda(fonte, datas, prm, mesa=args.mesa, fundos=args.fundo, com_precos=not args.sem_precos)
        corr = None
        if args.corrigir or args.aplicar:
            base = nome_arquivo(res, args.mesa, args.fundo)[len("batimento_"):-len(".xlsx")]
            corr = corrige(fonte, res, args.saida, base, args.com_revisao, args.aplicar)
    except RuntimeError as e:                        # credenciais ausentes ou sem conexão
        print(f"[ERRO] {e}")
        return 2
    from relatorio import grava_excel
    caminho = grava_excel(res, args.saida, nome_arquivo(res, args.mesa, args.fundo))
    imprime(res, caminho)
    if corr:
        for nome, arq in corr["arquivos"].items():
            print(f"{nome.capitalize():<9}: {arq}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
