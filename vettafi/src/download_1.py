"""
Baixa os CSVs diários dos últimos DIAS dias de cada índice VettaFi pelo site da
Files.com, navegando como um usuário: faz login, abre a pasta do índice e clica em
"Download" na linha de cada arquivo. Os constituintes (ADJ.VFC) vão para output/INDEX
e as corporate actions (VFA) para output/CORPORATE_ACTIONS.

O navegador é o Edge instalado na máquina (Playwright, channel="msedge"), que já
sai pelo proxy e confia nos certificados do Windows - não há proxy/SSL no código.

Uso: python src/download.py [--visivel]   (a partir da pasta vettafi)
  --visivel  mostra a janela do navegador (para depurar ou digitar o código 2FA)
Credenciais: variáveis de ambiente VETTAFI_USER e VETTAFI_SENHA
Dependência: pip install playwright   (não precisa de "playwright install": usa o Edge)
"""
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import List
from urllib.parse import unquote, urlsplit

from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "output"

SITE = "https://tmxvettafi.files.com"
INDICES = ["RAFSBDRP", "RAFSBRAP"]
# (pasta no site em INDEX_DATA/<INDICE>/, final do nome AAAAMMDD_<INDICE>_<final>, pasta local)
ARQUIVOS = [
    ("ADJ_CLOSE_CONSTITUENTS", "ADJ.VFC.csv", OUTPUT_DIR / "INDEX"),
    ("CORPORATE_ACTIONS", "VFA.csv", OUTPUT_DIR / "CORPORATE_ACTIONS"),
]
# Período: baixa os arquivos com data no nome de hoje até DIAS dias corridos atrás.
# Ex.: DIAS = 7 rodando em 15/10 baixa de 08/10 a 15/10. Fim de semana e feriado não
# têm arquivo, e corporate actions só sai em dia com evento.
DIAS = 7
VETTAFI_USER = os.environ.get("VETTAFI_USER", "fabricio.levy@itau-unibanco.com.br")
VETTAFI_SENHA = os.environ.get("VETTAFI_SENHA", "")

CANAL_NAVEGADOR = "msedge"  # navegador instalado; "chrome" também serve
TIMEOUT_MS = 60_000
TIMEOUT_2FA_MS = 300_000  # tempo para digitar o código 2FA na janela (--visivel)
ROTULO_DOWNLOAD = re.compile(r"^(download|baixar)$", re.IGNORECASE)
ARQUIVO_ERRO = OUTPUT_DIR / "erro_download.png"


def logado(url: str) -> bool:
    return not urlsplit(url).path.startswith(("/login", "/newSession"))


def fazer_login(page, visivel: bool):
    if not VETTAFI_SENHA:
        raise RuntimeError("Defina VETTAFI_SENHA (senha do site da VettaFi) e reabra o VS Code.")

    page.goto(f"{SITE}/login")
    page.fill("#form-username", VETTAFI_USER)
    page.fill("#form-password", VETTAFI_SENHA)
    with page.expect_response(
        lambda r: "/api/rest/v1/sessions" in r.url and r.request.method == "POST"
    ) as resposta_login:
        page.click("button[type=submit]")

    resposta = resposta_login.value
    if not resposta.ok:
        erro = resposta.text()
        if not re.search(r"two.?factor|2fa|partial_session", erro, re.IGNORECASE):
            raise RuntimeError(f"Login recusado pela Files.com (HTTP {resposta.status}): {erro}")
        if not visivel:
            raise RuntimeError("A conta pede 2FA: rode com --visivel e digite o código na janela.")
        print("[login] digite o código 2FA na janela do navegador")

    page.wait_for_url(logado, timeout=TIMEOUT_2FA_MS if visivel else TIMEOUT_MS)
    print(f"[login] ok como {VETTAFI_USER}")


def listar_pasta(page, caminho: str) -> list:
    """Abre a pasta no site e devolve os itens da listagem que a página carrega."""
    # Os nomes saem da listagem que a página carrega: assim dá para saber na hora que
    # não há arquivo, sem esperar o timeout de uma linha que nunca vai aparecer.
    # Cada listagem traz 100 itens: em ordem decrescente os mais recentes vêm primeiro.
    with page.expect_response(
        lambda r: unquote(urlsplit(r.url).path) == f"/api/rest/v1/folders/{caminho}"
    ) as listagem:
        page.goto(f"{SITE}/files/{caminho}?sortColumn=path&sortDirection=desc")
    if listagem.value.status == 404:  # pasta inexistente (ex.: ainda sem ARCHIVE)
        return []
    if not listagem.value.ok:
        raise RuntimeError(f"Não foi possível listar {caminho} (HTTP {listagem.value.status})")
    return listagem.value.json()


def baixar_periodo(
    page, indice: str, pasta: str, final: str, destino: Path, inicio: str, fim: str
) -> List[Path]:
    """Baixa para destino os arquivos AAAAMMDD_<indice>_<final> com AAAAMMDD entre inicio e fim."""
    padrao = re.compile(rf"\d{{8}}_{indice}_{re.escape(final)}")
    caminho = f"INDEX_DATA/{indice}/{pasta}"
    baixados = []
    # a pasta guarda só as últimas semanas; os arquivos mais antigos vão para ARCHIVE
    for subpasta in [caminho, f"{caminho}/ARCHIVE"]:
        nomes = sorted(  # nome começa com AAAAMMDD: ordem alfabética = cronológica
            item["display_name"]
            for item in listar_pasta(page, subpasta)
            if padrao.fullmatch(item["display_name"])
        )
        baixados += [
            baixar_arquivo(page, nome, destino) for nome in nomes if inicio <= nome[:8] <= fim
        ]
        if nomes and nomes[0][:8] < inicio:  # esta pasta já cobre o começo do período
            break
    if not baixados:
        print(f"[aviso] nenhum arquivo *_{indice}_{final} de {inicio} a {fim} em {caminho}")
    return baixados


def baixar_arquivo(page, nome: str, destino: Path) -> Path:
    """Clica em "Download" na linha do arquivo (na pasta aberta no navegador) e salva em destino."""
    linha = page.locator("tr").filter(has_text=nome)
    linha.hover()  # as ações da linha aparecem no hover
    botao = linha.get_by_role("button", name=ROTULO_DOWNLOAD)
    # o site redireciona para um link temporário de download; o Playwright captura o arquivo
    with page.expect_download() as download:
        if botao.count():
            botao.first.click()
        else:  # sem o ícone na linha: usa o menu "..." da linha
            linha.locator(".MoreMenuTrigger").click()
            page.get_by_role("menuitem", name=ROTULO_DOWNLOAD).click()

    arquivo = destino / nome
    download.value.save_as(arquivo)
    print(f"[download] {arquivo.relative_to(OUTPUT_DIR)}")
    return arquivo


def main():
    visivel = "--visivel" in sys.argv[1:]
    fim = date.today()
    inicio = fim - timedelta(days=DIAS)
    print(f"[período] {inicio:%d/%m/%Y} a {fim:%d/%m/%Y} (últimos {DIAS} dias)")
    for _, _, destino in ARQUIVOS:
        destino.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        navegador = p.chromium.launch(channel=CANAL_NAVEGADOR, headless=not visivel)
        page = navegador.new_page(accept_downloads=True, viewport={"width": 1600, "height": 900})
        page.set_default_timeout(TIMEOUT_MS)
        try:
            fazer_login(page, visivel)
            baixados = []
            for indice in INDICES:
                for pasta, final, destino in ARQUIVOS:
                    baixados += baixar_periodo(
                        page, indice, pasta, final, destino, f"{inicio:%Y%m%d}", f"{fim:%Y%m%d}"
                    )
        except Exception:
            page.screenshot(path=str(ARQUIVO_ERRO), full_page=True)
            print(f"[erro] tela no momento do erro: {ARQUIVO_ERRO}")
            raise
        finally:
            navegador.close()

    print(f"[fim] {len(baixados)} arquivo(s) em {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
