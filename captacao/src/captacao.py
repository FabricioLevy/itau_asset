# ─────────────────────────────────────────────
# captacao.py
# Busca CAPTAÇÃO / RESGATE diários de fundos de investimento no Broadcast+ (AE)
# e salva em .xlsx — via add-in Excel do Broadcast (função BCH).
#
# Por que via Excel (e não direto pelo terminal):
#   Série histórica só sai do terminal pelo add-in Excel (Broadcast.AddIn64.xll), que
#   conversa com o bcsys32.exe em 127.0.0.1:8100 (aesp.cfg). O script abre um Excel
#   OCULTO e separado (DispatchEx — não mexe em nenhum Excel já aberto), carrega o
#   add-in, escreve um =BCH(...) por fundo (uma aba cada, p/ os resultados não se
#   sobreporem) e lê o que o add-in devolve.
#
# Campos BCH usados (Guia de Campos de Dados Históricos do add-in):
#   DRF data de referência | ULT cota | CAPT captação | RESG resgate |
#   PATR patrimônio líquido | QCOT quantidade de cotistas
#   captacao_liquida = CAPT - RESG (calculada aqui).
#
# Código do fundo no Broadcast:
#   O BCH pede o CÓDIGO Broadcast do fundo, não o CNPJ: "FI" + código ANBIMA da classe,
#   só a parte numérica, sem zeros à esquerda (ANBIMA C0001390643 -> FI1390643; é assim
#   que o AE.Funds.Plugin monta o ticker em FundFactory.CreateFund). Para achar o código:
#   no terminal, busca de Fundos pelo CNPJ -> coluna "Código Anbima".
#   Por isso há um mapa CNPJ -> código em ../input/fundos_captacao.csv
#   (colunas cnpj;codigo_broadcast;nome). Na linha de comando, o que for CNPJ é
#   traduzido pelo mapa; código ANBIMA (1390643 ou C0001390643) vira FI1390643; o resto
#   é usado direto como código Broadcast.
#   Aceita também o CNPJ alfanumérico (Receita, jul/2026) na validação dos dígitos.
#
# Requisitos: terminal Broadcast aberto e logado; Excel 64-bit com o add-in instalado;
#   pywin32, pandas, openpyxl (o anaconda do projeto já tem).
#
# Uso:
#   python captacao.py                                  (todos os fundos do mapa, últimos 30 dias)
#   python captacao.py 12.345.678/0001-95 FI123456 --inicio 01/08/2026 --fim 19/09/2026
#   python captacao.py --periodo M --inicio 01/01/2026   (série mensal)
# Saída: ../output/captacao/captacao_<yyyymmdd_HHMM>.xlsx (abas Diario e Resumo)
# ─────────────────────────────────────────────

import argparse
import os
import re
import sys
import time
from datetime import datetime, timedelta

import pandas as pd


AE_BROADCAST_DIR = r"C:\Program Files (x86)\AE Broadcast"
ADDIN_XLL = os.path.join(AE_BROADCAST_DIR, "Broadcast.AddIn64.xll")

AQUI = os.path.dirname(os.path.abspath(__file__))
MAPA_PADRAO = os.path.join(AQUI, "..", "input", "fundos_captacao.csv")
SAIDA_DIR = os.path.join(AQUI, "..", "output", "captacao")

# campo BCH -> coluna de saída (a ordem é a da fórmula)
CAMPOS = [("DRF", "data"), ("ULT", "cota"), ("CAPT", "captacao"), ("RESG", "resgate"),
          ("PATR", "patrimonio"), ("QCOT", "cotistas")]

# códigos de erro do add-in (Broadcast.AddIn.chm, "Problemas Comuns")
ERROS_BC = {
    "#BCONN": "Excel não conectou ao terminal (terminal fechado ou deslogado)",
    "#BCPERM": "código inexistente ou sem permissão no Broadcast",
    "#BCSYMBOL": "código não cadastrado no Broadcast",
    "#BCPROXY": "erro na consulta histórica (parâmetros, período ou permissão)",
    "#BCDATE": "período anterior ao início da base histórica",
    "#BCSYNTAX": "erro de sintaxe na fórmula BCH (ex.: data futura)",
    "#BCLIMIT": "limite de consultas históricas excedido",
}
# textos que a célula mostra enquanto o add-in ainda está buscando/conectando
PENDENTES = {"", "#N/A", "#N/D", "#BCONN", "#GETTING_DATA"}


# ── CNPJ ─────────────────────────────────────────────────────────────────────
_CNPJ_MASCARA = re.compile(r"^[0-9A-Z]{2}\.[0-9A-Z]{3}\.[0-9A-Z]{3}/[0-9A-Z]{4}-\d{2}$")


def normalizar_cnpj(s):
    """'66.198.405/0004-37' -> '66198405000437' (maiúsculas, só alfanuméricos)."""
    return re.sub(r"[^0-9A-Z]", "", (s or "").upper())


def eh_cnpj(s):
    """True p/ CNPJ com máscara (numérico ou alfanumérico) ou 14 dígitos puros."""
    s = (s or "").strip().upper()
    return bool(_CNPJ_MASCARA.match(s) or re.fullmatch(r"\d{14}", s))


def cnpj_valido(cnpj):
    """Confere os 2 dígitos verificadores. Vale p/ o CNPJ alfanumérico: cada caractere
    entra com valor ord(c) - 48 (dígitos continuam 0-9), mesmos pesos do módulo 11."""
    c = normalizar_cnpj(cnpj)
    if len(c) != 14 or not c[12:].isdigit():
        return False
    vals = [ord(ch) - 48 for ch in c[:12]]
    for pesos in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        r = sum(v * p for v, p in zip(vals, pesos)) % 11
        vals.append(0 if r < 2 else 11 - r)
    return "".join(map(str, vals[12:])) == c[12:]


def codigo_broadcast(s):
    """Normaliza o código do fundo: código ANBIMA de classe (1390643 / C0001390643) ->
    'FI1390643'; qualquer outra coisa (ex.: FI1390643, PETR4) volta em maiúsculas."""
    s = (s or "").strip().upper()
    m = re.fullmatch(r"C?(\d{1,10})", s)
    return f"FI{int(m.group(1))}" if m else s


def formatar_cnpj(cnpj):
    c = normalizar_cnpj(cnpj)
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else cnpj


# ── mapa CNPJ -> código Broadcast ─────────────────────────────────────────────
def carregar_mapa(caminho):
    """Lê o CSV (cnpj;codigo_broadcast;nome). Devolve lista de dicts, na ordem do arquivo."""
    if not os.path.exists(caminho):
        return []
    df = pd.read_csv(caminho, sep=";", dtype=str, comment="#", encoding="utf-8-sig").fillna("")
    df.columns = [c.strip().lower() for c in df.columns]
    faltando = {"cnpj", "codigo_broadcast"} - set(df.columns)
    if faltando:
        raise ValueError(f"{caminho}: faltam as colunas {sorted(faltando)} (esperado: cnpj;codigo_broadcast;nome)")
    return [dict(cnpj=normalizar_cnpj(r["cnpj"]), codigo=codigo_broadcast(r["codigo_broadcast"]),
                 nome=r.get("nome", "").strip())
            for _, r in df.iterrows() if r["cnpj"].strip() or r["codigo_broadcast"].strip()]


def resolver_fundos(entradas, mapa):
    """Traduz cada entrada (CNPJ ou código) em {entrada, cnpj, codigo, nome, erro}.
    Sem entradas, usa todos os fundos do mapa."""
    por_cnpj = {m["cnpj"]: m for m in mapa if m["cnpj"]}
    por_codigo = {m["codigo"]: m for m in mapa if m["codigo"]}
    if not entradas:
        entradas = [formatar_cnpj(m["cnpj"]) if m["cnpj"] else m["codigo"] for m in mapa]

    fundos = []
    for ent in entradas:
        f = dict(entrada=ent, cnpj="", codigo="", nome="", erro="")
        if eh_cnpj(ent):
            f["cnpj"] = normalizar_cnpj(ent)
            if not cnpj_valido(ent):
                print(f"[AVISO] CNPJ {ent} tem dígito verificador inválido — confira se foi digitado certo.")
            m = por_cnpj.get(f["cnpj"])
            if m and m["codigo"]:
                f.update(codigo=m["codigo"], nome=m["nome"])
            else:
                f["erro"] = "CNPJ sem codigo_broadcast no mapa (preencha ../input/fundos_captacao.csv)"
        else:
            f["codigo"] = codigo_broadcast(ent)
            m = por_codigo.get(f["codigo"])
            if m:
                f.update(cnpj=m["cnpj"], nome=m["nome"])
        fundos.append(f)
    return fundos


# ── Excel + add-in Broadcast ──────────────────────────────────────────────────
_EXCEL_OCUPADO = (-2147418111, -2147417846)  # RPC_E_CALL_REJECTED, RPC_E_SERVERCALL_RETRYLATER


def _com(fn, tentativas=60, espera=0.5):
    """Chama fn() repetindo enquanto o Excel recusar a chamada por estar ocupado
    (acontece enquanto o add-in está calculando/recebendo dados)."""
    import pywintypes
    for i in range(tentativas):
        try:
            return fn()
        except pywintypes.com_error as e:
            if e.hresult not in _EXCEL_OCUPADO or i == tentativas - 1:
                raise
            time.sleep(espera)


def _formula_bch(codigo, inicio, fim, periodo):
    campos = ";".join(c for c, _ in CAMPOS)
    return (f'=BCH("{codigo}","{campos}","{inicio:%d/%m/%Y}","{fim:%d/%m/%Y}",'
            f'"PERIODO={periodo}","ASC=DRF","TITULO=S")')


def _ler_resultado(ws):
    """Converte o bloco devolvido pelo BCH (título na 1ª linha) em DataFrame."""
    valores = _com(lambda: ws.Range("A1").CurrentRegion.Value)
    if not isinstance(valores, tuple) or len(valores) < 2:
        return pd.DataFrame(columns=[n for _, n in CAMPOS])
    titulos = [str(t).strip().upper() for t in valores[0]]
    nomes = dict(CAMPOS)
    df = pd.DataFrame(list(valores[1:]), columns=[nomes.get(t, t.lower()) for t in titulos])
    # DRF vem como data OLE Automation (nº de dias desde 30/12/1899)
    df["data"] = pd.to_datetime(pd.to_numeric(df["data"], errors="coerce"), unit="D", origin="1899-12-30").dt.normalize()
    for col in df.columns.drop("data"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["data"])


def consultar_bch(codigos, inicio, fim, periodo="D", timeout=120.0):
    """Roda um BCH por código num Excel oculto. Devolve {codigo: DataFrame | 'erro'}."""
    import pythoncom
    import win32com.client

    if not os.path.exists(ADDIN_XLL):
        raise RuntimeError(f"add-in do Broadcast não encontrado em {ADDIN_XLL!r}")

    pythoncom.CoInitialize()
    xl = wb = None
    try:
        xl = win32com.client.DispatchEx("Excel.Application")  # instância própria
        xl.Visible = False
        xl.DisplayAlerts = False
        if not xl.RegisterXLL(ADDIN_XLL):
            raise RuntimeError("Excel não carregou o add-in do Broadcast")
        wb = xl.Workbooks.Add()

        def escrever(cod):
            f = _formula_bch(cod, inicio, fim, periodo)
            _com(lambda: setattr(abas[cod].Range("A1"), "Formula2", f))

        def topo(cod):
            return str(_com(lambda: abas[cod].Range("A1").Text)).strip().upper()

        # uma aba por fundo: o BCH "derrama" linhas e colunas a partir de A1
        abas = {}
        for i, cod in enumerate(codigos):
            abas[cod] = _com(lambda: wb.Worksheets(1) if i == 0
                             else wb.Worksheets.Add(After=wb.Worksheets(wb.Worksheets.Count)))
            escrever(cod)

        # o add-in conecta no terminal de forma assíncrona: nos primeiros segundos
        # a célula mostra #BCONN — reescreve a fórmula até a resposta chegar
        pendentes = set(codigos)
        inicio_espera = ultimo_reenvio = time.time()
        ultimo_print = 0.0
        while pendentes and time.time() - inicio_espera < timeout:
            pythoncom.PumpWaitingMessages()
            time.sleep(1.0)
            for cod in list(pendentes):
                if topo(cod) not in PENDENTES:
                    pendentes.discard(cod)
            if pendentes and time.time() - ultimo_reenvio > 6:
                for cod in pendentes:
                    escrever(cod)
                ultimo_reenvio = time.time()
            if pendentes and time.time() - ultimo_print > 10:
                print(f"[INFO] aguardando Broadcast... {len(codigos) - len(pendentes)}/{len(codigos)} fundo(s) prontos")
                ultimo_print = time.time()

        resultados = {}
        for cod, ws in abas.items():
            t = topo(cod)
            if t == "DRF":
                resultados[cod] = _ler_resultado(ws)
            elif cod in pendentes:
                resultados[cod] = f"sem resposta em {int(timeout)}s ({t or 'vazio'})" + (
                    f" — {ERROS_BC[t]}" if t in ERROS_BC else "")
            else:
                resultados[cod] = f"{t} — {ERROS_BC.get(t, 'erro desconhecido do add-in')}"
        return resultados
    finally:
        try:
            if wb is not None:
                wb.Close(False)
        except Exception:  # noqa
            pass
        if xl is not None:
            xl.Quit()
        pythoncom.CoUninitialize()


# ── montagem da saída ─────────────────────────────────────────────────────────
def montar_tabelas(fundos, resultados):
    """Devolve (diario, resumo) — diario em formato longo, resumo com 1 linha por fundo."""
    partes, resumo = [], []
    for f in fundos:
        res = resultados.get(f["codigo"]) if f["codigo"] else None
        erro = f["erro"] or (res if isinstance(res, str) else "")
        linha = dict(entrada=f["entrada"], cnpj=formatar_cnpj(f["cnpj"]) if f["cnpj"] else "",
                     codigo_broadcast=f["codigo"], nome=f["nome"])
        if not erro and isinstance(res, pd.DataFrame) and not res.empty:
            df = res.copy()
            df["captacao_liquida"] = df["captacao"].fillna(0) - df["resgate"].fillna(0)
            df.loc[df["captacao"].isna() & df["resgate"].isna(), "captacao_liquida"] = float("nan")
            for k in ("nome", "codigo_broadcast", "cnpj"):
                df.insert(0, k, linha[k])
            partes.append(df)
            ini, fim = df.iloc[0], df.iloc[-1]
            linha.update(inicio=ini["data"], fim=fim["data"], dias=len(df),
                         captacao=df["captacao"].sum(min_count=1),
                         resgate=df["resgate"].sum(min_count=1),
                         captacao_liquida=df["captacao_liquida"].sum(min_count=1),
                         patrimonio_inicial=ini["patrimonio"], patrimonio_final=fim["patrimonio"],
                         cotistas_inicial=ini["cotistas"], cotistas_final=fim["cotistas"],
                         status="ok")
        else:
            linha["status"] = erro or "sem dados no período"
        resumo.append(linha)

    colunas = ["cnpj", "codigo_broadcast", "nome", "data", "cota", "captacao", "resgate",
               "captacao_liquida", "patrimonio", "cotistas"]
    diario = pd.concat(partes, ignore_index=True)[colunas] if partes else pd.DataFrame(columns=colunas)
    return diario, pd.DataFrame(resumo)


def salvar_xlsx(diario, resumo, caminho):
    os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
    with pd.ExcelWriter(caminho, engine="openpyxl", datetime_format="DD/MM/YYYY") as xw:
        diario.to_excel(xw, sheet_name="Diario", index=False)
        resumo.to_excel(xw, sheet_name="Resumo", index=False)
        for ws in xw.book.worksheets:
            ws.freeze_panes = "A2"
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = max(
                    12, min(45, max(len(str(c.value or "")) for c in col[:200]) + 2))
    return caminho


# ── CLI ───────────────────────────────────────────────────────────────────────
def _data(s):
    return datetime.strptime(s, "%d/%m/%Y").date()


def main(argv=None):
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa
            pass

    hoje = datetime.now().date()
    ap = argparse.ArgumentParser(description="Captação/resgate de fundos via Broadcast+ (add-in Excel, função BCH).")
    ap.add_argument("fundos", nargs="*",
                    help="CNPJs (com ou sem máscara), códigos ANBIMA (1390643) e/ou códigos Broadcast (FI1390643). "
                         "Sem nenhum, usa todos os fundos do mapa (--mapa).")
    ap.add_argument("--mapa", default=MAPA_PADRAO,
                    help="CSV cnpj;codigo_broadcast;nome que traduz CNPJ -> código Broadcast "
                         "(padrão: ../input/fundos_captacao.csv)")
    ap.add_argument("--inicio", type=_data, default=hoje - timedelta(days=30), help="dd/mm/aaaa (padrão: hoje - 30 dias)")
    ap.add_argument("--fim", type=_data, default=hoje, help="dd/mm/aaaa (padrão: hoje)")
    ap.add_argument("--periodo", choices=["D", "S", "M"], default="D", help="periodicidade do BCH: D(iária), S(emanal), M(ensal)")
    ap.add_argument("--timeout", type=float, default=120.0, help="espera máxima (s) pela resposta do Broadcast (padrão 120)")
    ap.add_argument("--out", help="caminho do .xlsx (padrão: ../output/captacao/captacao_<timestamp>.xlsx)")
    args = ap.parse_args(argv)

    if args.inicio > args.fim:
        ap.error("--inicio depois de --fim")
    if args.fim > hoje:
        ap.error("--fim no futuro (o BCH rejeita data futura)")

    try:
        mapa = carregar_mapa(args.mapa)
    except ValueError as e:
        print(f"[ERRO] {e}")
        return 1
    fundos = resolver_fundos(args.fundos, mapa)
    if not fundos:
        print(f"[ERRO] nenhum fundo para consultar: não foi passado nenhum na linha de comando e o mapa\n"
              f"       {os.path.abspath(args.mapa)}\n"
              f"       está vazio ou não existe. Faça UMA das duas coisas:\n"
              f"         1) passe os códigos Broadcast direto:   python captacao.py FI123456 FI654321\n"
              f"         2) preencha o mapa (uma linha por fundo): 12.345.678/0001-95;FI123456;Nome do fundo\n"
              f"            e rode sem argumentos (ou passando os CNPJs).")
        return 1

    codigos = list(dict.fromkeys(f["codigo"] for f in fundos if f["codigo"] and not f["erro"]))
    resultados = {}
    if codigos:
        print(f"[INFO] consultando {len(codigos)} fundo(s) no Broadcast: "
              f"{args.inicio:%d/%m/%Y} a {args.fim:%d/%m/%Y}, periodicidade {args.periodo}")
        try:
            resultados = consultar_bch(codigos, args.inicio, args.fim, args.periodo, args.timeout)
        except Exception as e:  # noqa
            print(f"[ERRO] falha ao consultar o Broadcast via Excel: {e!r}")
            return 1

    diario, resumo = montar_tabelas(fundos, resultados)
    for _, r in resumo.iterrows():
        rotulo = r["codigo_broadcast"] or r["entrada"]
        if r["status"] == "ok":
            print(f"[OK] {rotulo}: {int(r['dias'])} linha(s), captação líquida no período = {r['captacao_liquida']:,.2f}")
        else:
            print(f"[AVISO] {rotulo}: {r['status']}")

    destino = args.out or os.path.join(SAIDA_DIR, f"captacao_{datetime.now():%Y%m%d_%H%M}.xlsx")
    salvar_xlsx(diario, resumo, destino)
    print(f"[OK] salvo em: {os.path.abspath(destino)}")
    return 0 if (resumo["status"] == "ok").any() else 1


if __name__ == "__main__":
    raise SystemExit(main())
