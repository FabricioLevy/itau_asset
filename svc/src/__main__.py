# -*- coding: utf-8 -*-
"""
relatorio_svc — baixa o relatório "Consulta Status Validação" do portal
interno https://intracorp9.itau/oc3portalazuread/, junto com a mesa de
gestão de cada fundo.

Uso normal — é só rodar `run.bat` (na pasta relatorio_svc), que já cuida
do --driver e do NO_PROXY. Por baixo dos panos chama:

    python __main__.py --driver "C:\\caminho\\para\\msedgedriver.exe"

Sem argumentos, roda o fluxo automático: abre o Edge, confirma o SSO,
navega até a tela, gera o Excel pra cada sistema (LZ e XZ) e junta tudo
com a mesa de gestão — trazendo todos os fundos do grid, sem filtrar por
data (o run.bat, por sua vez, sempre passa --dias 1, filtrando por D-1).
Use --dias/--data-posicao pra restringir a dias específicos, ou
--explorar pra em vez disso pausar pra navegação manual (só necessário se
for investigar uma tela nova que ainda não foi automatizada).

Com --salvar-sql, além do Excel, atualiza o status dos fundos no SQL
Server (dbo.svc_status_validacao + histórico em dbo.svc_status_validacao_hist,
ver carga_sql.py e sql/). --carregar-sql ARQUIVO grava um relatório final
já gerado, sem abrir o portal.

Requer o driver do Edge (msedgedriver.exe, já incluso em drivers/). O
Selenium tenta baixá-lo sozinho (Selenium Manager) se --driver não for
informado, mas a rede corporativa bloqueia esse download — por isso o
run.bat sempre passa --driver.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import threading
import time

from datetime import date, datetime

from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.support.ui import WebDriverWait

import carga_sql
import status_validacao as sv

URL = "https://intracorp9.itau/oc3portalazuread/default.aspx"
INPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "input")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
DEBUG_HTML_DIR = os.path.join(os.path.dirname(__file__), "..", "debug_html")
AUTO_DEBUG_HTML_DIR = os.path.join(DEBUG_HTML_DIR, "auto")


def _log(msg: str) -> None:
    print(msg, flush=True)


def dump_html(driver: webdriver.Edge, base_dir: str = DEBUG_HTML_DIR) -> str:
    """Salva o HTML da página atual (documento principal + todos os frames
    e iframes, recursivamente) em arquivos .txt dentro de uma subpasta com
    timestamp. Útil quando a navegação usa frames/postbacks e a URL não
    muda — assim dá pra "fotografar" cada tela e ler o conteúdo depois.

    Devolve o caminho da pasta criada.
    """
    out_dir = os.path.join(base_dir, time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(out_dir, exist_ok=True)

    def _dump_current(label: str) -> None:
        html = driver.execute_script("return document.documentElement.outerHTML")
        with open(os.path.join(out_dir, f"{label}.txt"), "w", encoding="utf-8") as f:
            f.write(html)
        frames = driver.find_elements("css selector", "iframe, frame")
        for i, frame in enumerate(frames):
            try:
                driver.switch_to.frame(frame)
            except Exception as exc:
                _log(f"[aviso] não consegui entrar no frame {label}_frame{i}: {exc}")
                continue
            _dump_current(f"{label}_frame{i}")
            driver.switch_to.parent_frame()

    driver.switch_to.default_content()
    _dump_current("main")
    driver.switch_to.default_content()
    return out_dir


def _content_fingerprint(driver: webdriver.Edge) -> str:
    """Hash do HTML atual (documento principal + frames), pra detectar quando
    a tela mudou sem precisar salvar em disco toda hora."""
    htmls = []

    def _collect() -> None:
        htmls.append(driver.execute_script("return document.documentElement.outerHTML"))
        for frame in driver.find_elements("css selector", "iframe, frame"):
            try:
                driver.switch_to.frame(frame)
            except Exception:
                continue
            _collect()
            driver.switch_to.parent_frame()

    driver.switch_to.default_content()
    _collect()
    driver.switch_to.default_content()
    return hashlib.md5("".join(htmls).encode("utf-8", "ignore")).hexdigest()


def auto_dump_loop(driver: webdriver.Edge, stop_event: threading.Event,
                   lock: threading.Lock, interval: float = 1.0) -> None:
    """Roda em background enquanto o usuário navega manualmente: sempre que a
    tela mudar (HTML diferente do último salvo), salva uma cópia em
    debug_html/auto/. Assim capturamos até estados "passageiros" (ex.: popup
    de calendário) sem precisar trocar o foco pro terminal — o que fecharia
    o popup antes de conseguirmos fotografar.
    """
    last_hash = None
    while not stop_event.is_set():
        try:
            with lock:
                h = _content_fingerprint(driver)
                if h and h != last_hash:
                    last_hash = h
                    pasta = dump_html(driver, AUTO_DEBUG_HTML_DIR)
                    _log(f"\n[auto] tela mudou, HTML salvo em: {os.path.abspath(pasta)}")
        except Exception:
            pass
        stop_event.wait(interval)


def abrir_portal(driver_path: str = None, timeout: int = 60,
                 download_dir: str = None) -> webdriver.Edge:
    """Abre o Edge (com o seu perfil/sessão do Windows) e navega até o portal.

    Devolve o `driver` com a sessão aberta — quem chamar é responsável por
    fechar com `driver.quit()` quando terminar.
    """
    options = webdriver.EdgeOptions()
    options.add_argument("--start-maximized")

    if download_dir:
        os.makedirs(download_dir, exist_ok=True)
        options.add_experimental_option("prefs", {
            "download.default_directory": os.path.abspath(download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        })

    service = Service(executable_path=driver_path) if driver_path else Service()
    driver = webdriver.Edge(service=service, options=options)

    _log(f"[info] abrindo {URL}")
    driver.get(URL)

    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    _log(f"[info] página carregada: {driver.title!r}")
    _log(f"[info] URL atual: {driver.current_url}")

    return driver


def _parse_data(texto: str):
    return datetime.strptime(texto, "%d/%m/%Y").date()


def salvar_sql(arquivo_final: str, a: argparse.Namespace) -> int:
    """Grava o relatório final no SQL Server (ver carga_sql.py). Devolve o
    código de saída: 1 se a gravação falhou (o Excel continua salvo)."""
    import pandas as pd

    df_final = pd.read_excel(arquivo_final)
    ok = carga_sql.atualizar_status(df_final, db=a.db, tabela=a.tabela, tabela_hist=a.tabela_hist)
    return 0 if ok else 1


def modo_gerar_excel(a: argparse.Namespace) -> int:
    """Etapa 2+3: navega automaticamente até 'Consulta Status Validação',
    filtra por Sistema e baixa o Excel — uma vez pra cada sistema pedido
    (LZ e/ou XZ). No final, junta tudo com a mesa de gestão (consultada via
    SQL na VW_FUNDOS_COTAS_PL) num único relatório em `--output`.

    Por padrão (sem --dias nem --data-posicao) traz TODOS os fundos do
    grid, sem filtrar por data — a maioria fica "Pendente" até ser
    processada, mas ainda assim entra no relatório. Passe --dias e/ou
    --data-posicao pra restringir só a um ou mais dias específicos.
    """
    sistemas = [s.strip().upper() for s in a.sistemas.split(",") if s.strip()]
    for s in sistemas:
        if s not in sv.SISTEMAS:
            _log(f"[erro] sistema inválido: {s!r} (use LZ e/ou XZ)")
            return 1

    if a.dias is None and a.data_posicao is None:
        datas_posicao = None
        _log("[info] sem filtro de data: trazendo todos os fundos do grid")
    else:
        data_final = _parse_data(a.data_posicao) if a.data_posicao else sv.dia_util_anterior(date.today())
        datas_posicao = sv.gerar_lista_dias_uteis(data_final, a.dias or 1)
        _log(f"[info] dias úteis buscados: {', '.join(d.strftime('%d/%m/%Y') for d in datas_posicao)}")

    driver = abrir_portal(a.driver, download_dir=a.input)
    try:
        arquivos = {}
        for sistema in sistemas:
            arquivo = sv.baixar_status_validacao(
                driver, sistema, datas_posicao, a.input,
                janela_madrugada_horas=a.janela_madrugada,
            )
            arquivos[sistema] = arquivo
            _log(f"[info] {sistema}: {os.path.abspath(arquivo)}")
    finally:
        if a.manter_aberto:
            try:
                input("Pressione Enter para fechar o navegador...")
            except EOFError:
                pass
        driver.quit()

    if datas_posicao is None:
        sufixo = "TODOS_" + date.today().strftime("%Y%m%d")
        data_referencia = date.today()
    else:
        sufixo = (f"{datas_posicao[0].strftime('%Y%m%d')}_a_{datas_posicao[-1].strftime('%Y%m%d')}"
                  if len(datas_posicao) > 1 else datas_posicao[0].strftime("%Y%m%d"))
        data_referencia = datas_posicao[-1]
    destino = os.path.join(a.output, f"StatusValidacao_MesaGestao_{sufixo}.xlsx")
    arquivo_final = sv.gerar_relatorio_mesa_gestao(arquivos, destino, data_referencia=data_referencia)
    _log(f"[info] relatório final: {os.path.abspath(arquivo_final)}")

    if a.salvar_sql:
        return salvar_sql(arquivo_final, a)
    return 0


def modo_exploracao(a: argparse.Namespace) -> int:
    driver = abrir_portal(a.driver)

    driver_lock = threading.Lock()
    stop_event = threading.Event()
    auto_thread = threading.Thread(
        target=auto_dump_loop, args=(driver, stop_event, driver_lock), daemon=True
    )
    auto_thread.start()

    _log("")
    _log("[etapa 1] Confira no Edge que o login por SSO funcionou (sem tela de senha).")
    _log("Navegue manualmente pelo portal. Toda vez que a tela mudar (inclusive "
         "popups como o calendário), o HTML é salvo automaticamente em "
         "relatorio_svc/debug_html/auto/ — não precisa fazer nada, só "
         "continue navegando no Edge sem trocar de janela. Se quiser forçar uma "
         "captura manual da tela atual, digite 'html' e Enter aqui. Quando "
         "terminar, digite apenas Enter (vazio) para encerrar.")
    while True:
        cmd = input("> ").strip().lower()
        if cmd == "":
            break
        if cmd in ("html", "h"):
            with driver_lock:
                pasta = dump_html(driver)
            _log(f"[info] HTML salvo em: {os.path.abspath(pasta)}")
        else:
            _log("Comando não reconhecido. Digite 'html' para salvar ou Enter vazio "
                 "para continuar.")

    stop_event.set()
    _log(f"[info] URL da tela atual: {driver.current_url}")

    input("Pressione Enter para fechar o navegador...")
    driver.quit()
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="relatorio_svc", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--driver", help="caminho do msedgedriver.exe "
                                    "(padrão: Selenium Manager baixa sozinho)")
    p.add_argument("--explorar", action="store_true",
                   help="em vez do fluxo automático, abre o portal e pausa pra "
                        "navegação manual (usado só pra investigar telas novas)")
    p.add_argument("--sistemas", default="LZ,XZ",
                   help="sistemas a gerar, separados por vírgula (padrão: LZ,XZ)")
    p.add_argument("--data-posicao", default=None,
                   help="data mais recente a buscar, formato dd/mm/aaaa "
                        "(padrão: dia útil anterior, D-1). Se nem --dias nem "
                        "--data-posicao forem passados, traz TODOS os fundos "
                        "sem filtrar por data")
    p.add_argument("--dias", type=int, default=None,
                   help="quantos dias úteis buscar, terminando em "
                        "--data-posicao (ex.: --dias 3 pega D-1, D-2 e D-3). "
                        "Se informado sem --data-posicao, termina em D-1")
    p.add_argument("--janela-madrugada", type=int, default=6,
                   help="alguns sistemas (ex.: LZ) fecham o processamento de "
                        "D-1 já na madrugada do dia seguinte, com timestamp "
                        "de 'hoje'; linhas com DataProcessamento no dia "
                        "seguinte e horário antes desse número de horas "
                        "também contam como D-1 (padrão: 6)")
    p.add_argument("--input", default=INPUT_DIR,
                   help=f"pasta onde salvar os .xlsx baixados/filtrados por sistema (padrão: {INPUT_DIR})")
    p.add_argument("--output", default=OUTPUT_DIR,
                   help=f"pasta onde salvar o relatório final consolidado "
                        f"(Data/Fundo/Mesa Gestão/Status) (padrão: {OUTPUT_DIR})")
    p.add_argument("--manter-aberto", action="store_true",
                   help="não fecha o Edge automaticamente ao terminar")
    p.add_argument("--salvar-sql", action="store_true",
                   help="além do Excel, atualiza o status dos fundos no SQL "
                        "Server: dbo.<--tabela> (foto atual, uma linha por Dt "
                        "Posição + Sistema + Fundo) e dbo.<--tabela-hist> "
                        "(cada mudança de Status/Status Banda/Carga Cockpit/"
                        "Valor). Ver carga_sql.py e sql/. Requer SQL_LOGIN/"
                        "SQL_PASSWORD no ambiente")
    p.add_argument("--carregar-sql", metavar="ARQUIVO", default=None,
                   help="não abre o portal: só grava no SQL Server (como o "
                        "--salvar-sql) um relatório final já gerado "
                        "(StatusValidacao_MesaGestao_*.xlsx)")
    p.add_argument("--db", default=carga_sql.DB_PADRAO,
                   help=f"banco de destino do --salvar-sql (padrão: {carga_sql.DB_PADRAO})")
    p.add_argument("--tabela", default=carga_sql.TABELA_PADRAO,
                   help=f"tabela (schema dbo) com a foto atual do status "
                        f"(padrão: {carga_sql.TABELA_PADRAO})")
    p.add_argument("--tabela-hist", default=carga_sql.TABELA_HIST_PADRAO,
                   help=f"tabela (schema dbo) com o histórico de mudanças "
                        f"(padrão: {carga_sql.TABELA_HIST_PADRAO})")
    a = p.parse_args(argv)

    if a.carregar_sql:
        return salvar_sql(a.carregar_sql, a)
    if a.explorar:
        return modo_exploracao(a)
    return modo_gerar_excel(a)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())
