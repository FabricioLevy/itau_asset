"""
Baixa os CSVs diários mais recentes de cada índice VettaFi (constituintes e
corporate actions) pelo site da Files.com, navegando como um usuário: faz login,
abre a pasta do índice e clica em "Download" na linha do arquivo.

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
from datetime import date
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlsplit

from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "output"

SITE = "https://tmxvettafi.files.com"
INDICES = ["RAFSBDRP", "RAFSBRAP"]
# pasta em INDEX_DATA/<INDICE>/ -> final do nome do arquivo (AAAAMMDD_<INDICE>_<final>)
ARQUIVOS = {
    "ADJ_CLOSE_CONSTITUENTS": "ADJ.VFC.csv",
    "CORPORATE_ACTIONS": "VFA.csv",
}
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


def baixar_mais_recente(page, indice: str, pasta: str, final: str) -> Optional[Path]:
    caminho = f"INDEX_DATA/{indice}/{pasta}"
    # a listagem vem em páginas de 100: em ordem decrescente o mais recente fica no topo.
    # Os nomes saem da listagem que a página carrega: assim dá para saber na hora que
    # não há arquivo, sem esperar o timeout de uma linha que nunca vai aparecer.
    with page.expect_response(
        lambda r: unquote(urlsplit(r.url).path) == f"/api/rest/v1/folders/{caminho}"
    ) as listagem:
        page.goto(f"{SITE}/files/{caminho}?sortColumn=path&sortDirection=desc")
    if not listagem.value.ok:
        raise RuntimeError(f"Não foi possível listar {caminho} (HTTP {listagem.value.status})")

    # Nem todo dia tem arquivo (fim de semana, feriado, dia sem corporate action):
    # pega o mais recente até hoje
    padrao = re.compile(rf"\d{{8}}_{indice}_{re.escape(final)}")
    hoje = date.today().strftime("%Y%m%d")
    nomes = [
        item["display_name"]
        for item in listagem.value.json()
        if padrao.fullmatch(item["display_name"]) and item["display_name"][:8] <= hoje
    ]
    if not nomes:
        print(f"[aviso] nenhum arquivo *_{indice}_{final} até {hoje} em {caminho}")
        return None
    nome = max(nomes)  # nome começa com AAAAMMDD: ordem alfabética = cronológica

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

    destino = OUTPUT_DIR / nome
    download.value.save_as(destino)
    print(f"[download] {nome}")
    return destino


def main():
    visivel = "--visivel" in sys.argv[1:]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        navegador = p.chromium.launch(channel=CANAL_NAVEGADOR, headless=not visivel)
        page = navegador.new_page(accept_downloads=True, viewport={"width": 1600, "height": 900})
        page.set_default_timeout(TIMEOUT_MS)
        try:
            fazer_login(page, visivel)
            baixados = [
                baixar_mais_recente(page, indice, pasta, final)
                for indice in INDICES
                for pasta, final in ARQUIVOS.items()
            ]
        except Exception:
            page.screenshot(path=str(ARQUIVO_ERRO), full_page=True)
            print(f"[erro] tela no momento do erro: {ARQUIVO_ERRO}")
            raise
        finally:
            navegador.close()

    baixados = [arquivo for arquivo in baixados if arquivo]
    print(f"[fim] {len(baixados)} arquivo(s) em {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
