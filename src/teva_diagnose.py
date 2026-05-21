"""
Script de diagnóstico: baixa os bundles JS do site e extrai contexto
em volta de palavras-chave para encontrar o endpoint da API.
Execute: python teva_diagnose.py
"""
import re
import os
import urllib3

for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(var, None)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from curl_cffi import requests as curl_requests

BASE_URL = "https://www.tevaindices.com.br"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

KEY_BUNDLES = [
    "/_next/static/chunks/0umzb-9gu2id8.js",
    "/_next/static/chunks/0_p0avxbrijbp.js",
    "/_next/static/chunks/0wu8nx4d_wsey.js",
    "/_next/static/chunks/0x.73w57rn4ou.js",
    "/_next/static/chunks/0i.l9589uvx0j.js",
    "/_next/static/chunks/0~mk~haosq91n.js",
]

KEYWORDS = [
    "chart", "teva", "indic", "selic", "histor",
    "/api/", "nossos-indice", "fetch(", "axios",
    "XMLHttpRequest", ".get(", "useQuery", "useSWR",
]

CONTEXT = 200  # chars antes e depois do match


def main():
    session = curl_requests.Session(impersonate="chrome")
    output_lines = []

    for bundle_path in KEY_BUNDLES:
        url = f"{BASE_URL}{bundle_path}"
        print(f"Baixando {bundle_path}...")
        try:
            resp = session.get(url, headers=HEADERS, verify=False, timeout=20)
            text = resp.text
        except Exception as e:
            output_lines.append(f"\n=== {bundle_path} — ERRO: {e} ===\n")
            continue

        output_lines.append(f"\n{'='*80}")
        output_lines.append(f"BUNDLE: {bundle_path}  ({len(text):,} chars)")
        output_lines.append(f"{'='*80}\n")

        found_any = False
        for kw in KEYWORDS:
            positions = [m.start() for m in re.finditer(re.escape(kw), text, re.IGNORECASE)]
            if not positions:
                continue
            found_any = True
            output_lines.append(f"  [{kw}] — {len(positions)} ocorrência(s)")
            for pos in positions[:6]:
                start = max(0, pos - CONTEXT)
                end = min(len(text), pos + CONTEXT)
                snippet = text[start:end].replace("\n", " ")
                output_lines.append(f"    ...{snippet}...")
            output_lines.append("")

        # Todos os strings que parecem URLs (/algo ou https://...)
        url_matches = re.findall(
            r'["\`]((?:https?://[^"\`\s]{8,}|/[a-zA-Z][a-zA-Z0-9\-/_]{4,80}))["\`]',
            text,
        )
        unique_urls = list(dict.fromkeys(url_matches))
        if unique_urls:
            output_lines.append(f"  [URLs encontradas — {len(unique_urls)} únicas]")
            for u in unique_urls[:60]:
                output_lines.append(f"    {u}")
            output_lines.append("")

        if not found_any and not unique_urls:
            output_lines.append("  (nenhuma keyword ou URL encontrada)")

    out_file = "teva_bundle_analysis.txt"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))

    print(f"\nAnálise salva em: {out_file}")
    print("Cole o conteúdo desse arquivo para identificar o endpoint correto.")


if __name__ == "__main__":
    main()
