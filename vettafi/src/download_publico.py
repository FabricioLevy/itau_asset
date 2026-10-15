"""
Alternativa ao download.py que não usa o portal da Files.com: lê a página pública
de cada índice no site da VettaFi (www.vettafi.com/indexing/index/<indice>), sem login.

A página pública NÃO tem a composição completa (ADJ.VFC) nem corporate actions (VFA):
só o top 10 ("Showing 1 to 10 of 10 entries"). Esses arquivos só existem no portal da
VettaFi, que o download.py baixa. A página traz, e o script salva em output/:
  - top 10 constituintes com ISIN e peso, posição de D-1   -> AAAAMMDD_<INDICE>_TOP10.csv
  - histórico diário do nível do índice (price, total return e net total return;
    antes do lançamento é backtest)                         -> AAAAMMDD_<INDICE>_NIVEIS.csv

O navegador é o Edge instalado na máquina (Playwright, channel="msedge"), como no
download.py.

Uso: python src/download_publico.py [--visivel]   (a partir da pasta vettafi)
"""
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List

import pandas as pd
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "output"

SITE = "https://www.vettafi.com/indexing/index"
INDICES = ["RAFSBDRP", "RAFSBRAP"]

CANAL_NAVEGADOR = "msedge"  # navegador instalado; "chrome" também serve
TIMEOUT_MS = 60_000
ARQUIVO_ERRO = OUTPUT_DIR / "erro_download_publico.png"

# coluna do CSV -> atributo data-element da célula na tabela "Top constituents"
CAMPOS_CONSTITUINTE = {
    "TICKER": "ticker",
    "COMPANY_NAME": "name",
    "ISIN": "isin",  # coluna escondida por CSS, mas presente no HTML
    "WEIGHT": "weight",
}
# coluna do CSV -> série no JSON de performance que a página carrega
SERIES_NIVEL = {
    "PRICE_RETURN": "Price Return",
    "TOTAL_RETURN": "Total Return",
    "NET_TOTAL_RETURN": "Net Total Return",
}


def baixar_indice(page, indice: str) -> List[Path]:
    # o nível diário vem de um JSON que a própria página carrega; o CDN recusa (403)
    # quem pede o arquivo direto, fora da página
    with page.expect_response(
        lambda r: r.url.endswith(f"/{indice.lower()}_performance.json")
    ) as performance:
        page.goto(f"{SITE}/{indice.lower()}")
    if not performance.value.ok:
        raise RuntimeError(f"Histórico de {indice} indisponível (HTTP {performance.value.status})")

    linhas = page.locator(".data-table__row.w-dyn-item")
    linhas.first.wait_for()
    texto_data = page.get_by_text("As of", exact=True).locator("xpath=following-sibling::*[1]")
    data_posicao = datetime.strptime(texto_data.inner_text().strip(), "%B %d, %Y")

    constituintes = pd.DataFrame(
        {coluna: linha.locator(f"[data-element={campo}]").text_content().strip()
         for coluna, campo in CAMPOS_CONSTITUINTE.items()}
        for linha in linhas.all()
    )
    constituintes["WEIGHT"] = constituintes["WEIGHT"].map(lambda p: Decimal(p.rstrip("%")) / 100)
    constituintes.insert(0, "INDEX", indice)
    constituintes.insert(1, "AS_OF_DATE", data_posicao.strftime("%Y%m%d"))
    destino_top = OUTPUT_DIR / f"{data_posicao:%Y%m%d}_{indice}_TOP10.csv"
    constituintes.to_csv(destino_top, index=False)
    print(f"[top10] {destino_top.name} ({len(constituintes)} constituintes)")

    series = performance.value.json()  # {"Price Return": [{"d": "2026-10-14", "l": 1069.67}, ...]}
    niveis = pd.DataFrame({
        coluna: pd.Series({ponto["d"]: ponto["l"] for ponto in series.get(nome, [])}, dtype=float)
        for coluna, nome in SERIES_NIVEL.items()
    }).sort_index()
    niveis.index.name = "DATE"
    niveis.insert(0, "INDEX", indice)
    destino_niveis = OUTPUT_DIR / f"{niveis.index[-1].replace('-', '')}_{indice}_NIVEIS.csv"
    niveis.to_csv(destino_niveis)
    print(f"[niveis] {destino_niveis.name} ({niveis.index[0]} a {niveis.index[-1]})")

    return [destino_top, destino_niveis]


def main():
    visivel = "--visivel" in sys.argv[1:]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        navegador = p.chromium.launch(channel=CANAL_NAVEGADOR, headless=not visivel)
        page = navegador.new_page(viewport={"width": 1600, "height": 900})
        page.set_default_timeout(TIMEOUT_MS)
        try:
            gerados = [arquivo for indice in INDICES for arquivo in baixar_indice(page, indice)]
        except Exception:
            page.screenshot(path=str(ARQUIVO_ERRO), full_page=True)
            print(f"[erro] tela no momento do erro: {ARQUIVO_ERRO}")
            raise
        finally:
            navegador.close()

    print(f"[fim] {len(gerados)} arquivo(s) em {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
