# ─────────────────────────────────────────────
# clp/__main__.py
# Cotação BRL_B3_2/CLP (reais por peso chileno) que falta na dbsx337.dbo.FUNDOS_DADOS_MOEDAS. A série
# do BBG.py começa em 28/09/2021; antes disso o patrimonio_brl dos fundos em CLP (ETFIPSASD, desde
# 02/09/2013) ficou em pesos na VW_FUNDOS_COTAS_PL.
#
# Cálculo (o mesmo da série do BBG.py — 22/10/2026: 5,0355 / 986,01 = 0,0051069):
#   preco_limpo = BRL_B3_2/USD (no banco desde 08/04/2013) / USD/CLP do Broadcast+
#   pnl = preco_limpo - o do dia anterior da série; pnl_perc = pnl / o do dia anterior.
#   Grava só as datas com os dois preços (dia útil na B3), de --inicio até a véspera da 1ª cotação do
#   BBG.py; data que já tem BRL_B3_2/CLP não é tocada. As linhas saem com log_script_from = LOG_SCRIPT.
#   Antes de gravar, confere o mesmo cálculo contra a série do BBG.py nos dias em comum: diferença
#   média acima de TOLERANCIA_MEDIA (código errado, cotação invertida) não grava nada.
#
# Fonte: Broadcast+, código USDCLP (CLP por USD; grupo das moedas à vista, o mesmo do USDBRL), campo
#   ULT, pela consultar_bch do ntnb/__main__.py (Excel oculto com o add-in). O feed tem fim de semana
#   (repete a sexta); essas datas caem fora por não terem BRL_B3_2/USD.
#
# Saída (./output/):
#   usdclp_<aaaammdd>.csv: date;usdclp — levar para a máquina com acesso ao banco (--carregar).
#   brl_clp_<aaaammdd>.csv (--carregar): as linhas gravadas (ou que seriam, com --simular).
#
# Requisitos: os do ntnb/__main__.py — Broadcast: terminal Broadcast+ aberto e logado + Excel 64-bit
#   com o add-in, pywin32; SQL: ODBC Driver 18 for SQL Server, pyodbc, sqlalchemy e SQL_LOGIN/
#   SQL_PASSWORD (vettafi/src/sql_connection.py).
#
# Uso (de dentro de clp/, ou "python clp" a partir de itau_asset/):
#   python __main__.py                        (máquina com Broadcast: USD/CLP de --inicio até hoje -> CSV)
#   python __main__.py --carregar --simular   (máquina com o banco: confere e mostra o que entraria)
#   python __main__.py --carregar             (confere e grava; sem arquivo = o usdclp_*.csv mais recente)
# ─────────────────────────────────────────────

import argparse
import getpass
import glob
import importlib.util
import os
import sys
from datetime import date, datetime, timedelta

import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA_DIR = os.path.join(AQUI, "output")
NTNB_MAIN = os.path.join(AQUI, "..", "ntnb", "__main__.py")      # consultar_bch (Broadcast via Excel)
SQL_CONNECTION_DIR = os.path.join(AQUI, "..", "vettafi", "src")  # sql_connection.py (SQNPRC028/DBSX337)

CODIGO_BROADCAST = "USDCLP"
INICIO_PADRAO = date(2013, 9, 2)  # 1º dia do ETFIPSASD
FOLGA_DIAS = 15                   # baixa antes do --inicio para o 1º dia gravado ter pnl
FAIXA_USDCLP = (300, 2000)        # CLP por USD ficou entre ~490 e ~1.050 desde 2013: fora disso é lixo
SALTO_DIARIO = 0.05               # variação diária que sai como aviso (15/07/2022: 7%, intervenção do BCCh)

TABELA_SQL = "dbo.FUNDOS_DADOS_MOEDAS"
BASE, QUOTE = "BRL_B3_2", "CLP"
LOG_SCRIPT = "clp/__main__.py"
TOLERANCIA_MEDIA = 0.01           # o USD/CLP de Londres 16h (USDLOND16H) fica a 0,3% da série do BBG.py


# ── Broadcast ────────────────────────────────────────────────────────────────
def baixar_broadcast(inicio, fim, timeout):
    """USD/CLP do Broadcast -> Series(data -> CLP por USD), sem os valores fora de FAIXA_USDCLP."""
    spec = importlib.util.spec_from_file_location("ntnb_main", NTNB_MAIN)
    ntnb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ntnb)
    serie = ntnb.consultar_bch([CODIGO_BROADCAST], inicio, fim, timeout)[CODIGO_BROADCAST]
    if isinstance(serie, str):
        raise RuntimeError(f"{CODIGO_BROADCAST}: {serie}")

    fora = serie[(serie < FAIXA_USDCLP[0]) | (serie > FAIXA_USDCLP[1])]
    if len(fora):
        print(f"[AVISO] {len(fora)} valor(es) fora de {FAIXA_USDCLP} descartado(s): "
              f"{', '.join(f'{d:%d/%m/%Y} ({v})' for d, v in fora.items())}")
        serie = serie.drop(fora.index)
    if serie.empty:
        raise RuntimeError(f"{CODIGO_BROADCAST}: sem dados de {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}")

    saltos = serie.pct_change().abs()
    saltos = saltos[saltos > SALTO_DIARIO]
    if len(saltos):
        print(f"[AVISO] variação diária acima de {SALTO_DIARIO:.0%} (confira se é mercado ou erro do feed): "
              f"{', '.join(f'{d:%d/%m/%Y} ({v:.1%})' for d, v in saltos.items())}")
    return serie


def ler_csv(caminho):
    tab = pd.read_csv(caminho, sep=";")
    if list(tab.columns) != ["date", "usdclp"]:
        raise ValueError(f"{caminho}: esperava as colunas date;usdclp (não é um usdclp_*.csv?)")
    return pd.Series(tab["usdclp"].to_numpy(dtype=float),
                     index=pd.DatetimeIndex(pd.to_datetime(tab["date"], format="%Y-%m-%d")))


# ── Cálculo ──────────────────────────────────────────────────────────────────
def montar(usdclp, usd, oficial, existentes, inicio):
    """usdclp: CLP por USD (Broadcast); usd: BRL_B3_2/USD; oficial: BRL_B3_2/CLP do BBG.py (Series por
    data, não vazia); existentes: datas que já têm BRL_B3_2/CLP.
    Devolve (linhas a gravar, diferença diária em módulo contra a série do BBG.py)."""
    preco = (usd / usdclp).dropna()
    tab = pd.DataFrame({"preco_limpo": preco, "pnl": preco.diff(), "pnl_perc": preco.pct_change()})
    comum = preco.index.intersection(oficial.index)
    dif = (preco[comum] / oficial[comum] - 1).abs()
    novas = tab[(tab.index >= pd.Timestamp(inicio)) & (tab.index < oficial.index.min())
                & ~tab.index.isin(existentes)]
    return novas, dif


# ── SQL ──────────────────────────────────────────────────────────────────────
def _serie(linhas):
    """[(data, valor)] do pyodbc -> Series por dia (a última linha, se o dia vier repetido)."""
    if not linhas:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    s = pd.Series([float(v) for _, v in linhas], index=pd.to_datetime([d for d, _ in linhas]).normalize())
    return s.groupby(level=0).last().sort_index()


def _num(v):
    return None if pd.isna(v) else float(v)


def carregar(usdclp, inicio, simular):
    """Confere o cálculo contra a série do BBG.py e grava as datas que faltam (INSERT numa transação)."""
    sys.path.insert(0, SQL_CONNECTION_DIR)
    from sql_connection import disconnect, get_connection

    sql = get_connection()
    try:
        conn = sql.connection
        if conn is None:
            raise RuntimeError(f"sem conexão com o banco {sql.db_name}")
        cur = conn.cursor()

        # textos de log no tamanho das colunas
        cur.execute("SELECT COLUMN_NAME, CHARACTER_MAXIMUM_LENGTH FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_NAME = 'FUNDOS_DADOS_MOEDAS' AND COLUMN_NAME IN ('log_last_user', 'log_script_from')")
        limite = {c.lower(): n for c, n in cur.fetchall()}

        def cortar(texto, coluna):
            n = limite.get(coluna) or -1  # -1 = (max)
            return texto[:n] if n > 0 else texto

        log_script, usuario = cortar(LOG_SCRIPT, "log_script_from"), cortar(getpass.getuser(), "log_last_user")

        cur.execute(f"SELECT [date], codigo_IAM_moeda_quote, preco_limpo, ISNULL(log_script_from, '') "
                    f"FROM {TABELA_SQL} (nolock) WHERE codigo_IAM_moeda_base = ? "
                    f"AND codigo_IAM_moeda_quote IN ('USD', ?) ORDER BY [date]", BASE, QUOTE)
        linhas = [(d, q.strip(), p, s.strip()) for d, q, p, s in cur.fetchall()]
        usd = _serie([(d, p) for d, q, p, _ in linhas if q == "USD" and p is not None])
        oficial = _serie([(d, p) for d, q, p, s in linhas if q == QUOTE and p is not None and s != log_script])
        existentes = pd.to_datetime([d for d, q, _, _ in linhas if q == QUOTE]).normalize()
        if usd.empty or oficial.empty:
            raise RuntimeError(f"sem {BASE}/USD ou sem a série {BASE}/{QUOTE} do BBG.py em {TABELA_SQL}")

        novas, dif = montar(usdclp, usd, oficial, existentes, inicio)
        if dif.empty:
            raise RuntimeError("nenhum dia em comum com a série do BBG.py: sem como conferir o cálculo")
        print(f"[INFO] conferência com a série do BBG.py: {len(dif)} dias em comum, diferença média "
              f"{dif.mean():.3%}, máxima {dif.max():.3%} ({dif.idxmax():%d/%m/%Y})")
        if dif.mean() > TOLERANCIA_MEDIA:
            raise RuntimeError(f"diferença média acima de {TOLERANCIA_MEDIA:.1%}: nada gravado "
                               f"(o {CODIGO_BROADCAST} do Broadcast não é a mesma cotação?)")

        primeira = oficial.index.min()
        if novas.empty:
            print(f"[OK] nada a gravar: de {inicio:%d/%m/%Y} até a 1ª cotação do BBG.py ({primeira:%d/%m/%Y}) "
                  f"todas as datas já têm {BASE}/{QUOTE} ou não têm os dois preços")
            return
        os.makedirs(SAIDA_DIR, exist_ok=True)
        csv = os.path.join(SAIDA_DIR, f"brl_clp_{novas.index[-1]:%Y%m%d}.csv")
        novas.rename_axis("date").to_csv(csv, sep=";", date_format="%Y-%m-%d")
        resumo = (f"{len(novas)} dias de {novas.index[0]:%d/%m/%Y} a {novas.index[-1]:%d/%m/%Y} "
                  f"(1ª cotação do BBG.py: {primeira:%d/%m/%Y})")
        if simular:
            print(f"[OK] --simular: entrariam {resumo}; nada gravado. Linhas em {csv}")
            return

        agora = datetime.now().replace(microsecond=0)
        valores = [(d.to_pydatetime(), BASE, QUOTE, float(r.preco_limpo), _num(r.pnl), _num(r.pnl_perc),
                    agora, usuario, log_script, "-")
                   for d, r in zip(novas.index, novas.itertuples(index=False))]
        try:
            cur.fast_executemany = True
            cur.executemany(f"INSERT INTO {TABELA_SQL} ([date], codigo_IAM_moeda_base, codigo_IAM_moeda_quote, "
                            "preco_limpo, pnl, pnl_perc, log_last_processamento, log_last_user, log_script_from, "
                            "fixing) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", valores)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        print(f"[OK] {resumo} gravados em {sql.db_name}.{TABELA_SQL} ({BASE}/{QUOTE}, "
              f"log_script_from = '{log_script}'). Linhas em {csv}")
        print("[INFO] próximo passo: rodar de novo o UPDATE do patrimonio_brl na VW_FUNDOS_COTAS_PL")
    finally:
        disconnect()


def _data(s):
    return datetime.strptime(s, "%d/%m/%Y").date()


def main(argv=None):
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa
            pass

    hoje = datetime.now().date()
    ap = argparse.ArgumentParser(description=f"{BASE}/{QUOTE} que falta na {TABELA_SQL}: {BASE}/USD do banco / "
                                             f"{CODIGO_BROADCAST} do Broadcast+.")
    ap.add_argument("--inicio", type=_data, default=INICIO_PADRAO,
                    help=f"1º dia a gravar dd/mm/aaaa (padrão: {INICIO_PADRAO:%d/%m/%Y}, início do ETFIPSASD)")
    ap.add_argument("--timeout", type=float, default=180.0,
                    help="espera máxima (s) pela resposta do Broadcast (padrão 180)")
    ap.add_argument("--carregar", nargs="?", const="", metavar="CSV",
                    help="confere e grava no SQL um usdclp_*.csv (sem arquivo: o mais recente de output/); "
                         "não usa o Broadcast")
    ap.add_argument("--simular", action="store_true", help="com --carregar: só confere e mostra o que entraria")
    args = ap.parse_args(argv)
    if args.simular and args.carregar is None:
        ap.error("--simular só vale com --carregar")
    if args.inicio >= hoje:
        ap.error("--inicio precisa ser antes de hoje")

    if args.carregar is not None:
        caminho = args.carregar or max(glob.glob(os.path.join(SAIDA_DIR, "usdclp_*.csv")), default=None)
        if not caminho:
            ap.error(f"nenhum usdclp_*.csv em {SAIDA_DIR}: rode antes na máquina com o Broadcast")
        print(f"[INFO] carregando {caminho}")
        try:
            usdclp = ler_csv(caminho)
        except (OSError, ValueError) as e:
            ap.error(str(e))
        try:
            carregar(usdclp, args.inicio, args.simular)
        except Exception as e:  # noqa — banco (credenciais, permissão) ou conferência que não bateu
            sys.exit(f"[ERRO] {e}")
        return

    inicio = args.inicio - timedelta(days=FOLGA_DIAS)
    print(f"[INFO] {CODIGO_BROADCAST} no Broadcast de {inicio:%d/%m/%Y} a {hoje:%d/%m/%Y}")
    try:
        usdclp = baixar_broadcast(inicio, hoje, args.timeout)
    except RuntimeError as e:
        sys.exit(f"[ERRO] {e}")
    if usdclp.index[0] > pd.Timestamp(args.inicio):
        print(f"[AVISO] o Broadcast só tem {CODIGO_BROADCAST} desde {usdclp.index[0]:%d/%m/%Y}")
    os.makedirs(SAIDA_DIR, exist_ok=True)
    csv = os.path.join(SAIDA_DIR, f"usdclp_{usdclp.index[-1]:%Y%m%d}.csv")
    usdclp.rename("usdclp").rename_axis("date").to_csv(csv, sep=";", date_format="%Y-%m-%d")
    print(f"[OK] {csv}: {len(usdclp)} dias, {usdclp.index[0]:%d/%m/%Y} a {usdclp.index[-1]:%d/%m/%Y}")
    print("[INFO] próximo passo, na máquina com acesso ao banco: python __main__.py --carregar --simular")


if __name__ == "__main__":
    main()
