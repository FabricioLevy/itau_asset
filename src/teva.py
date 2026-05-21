import urllib3
import pandas as pd
import re
import json
from datetime import datetime
import os

for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(var, None)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from curl_cffi import requests as curl_requests


class TevaIndexClient:

    def __init__(self):
        self.session = curl_requests.Session(impersonate="chrome")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;"
                      "q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def _get(self, url: str, referer: str = None, extra_headers: dict = None):
        headers = self.headers.copy()
        if referer:
            headers["Referer"] = referer
        if extra_headers:
            headers.update(extra_headers)
        resp = self.session.get(url, headers=headers, verify=False, timeout=30)
        resp.raise_for_status()
        return resp

    def _extract_series(self, text: str) -> list | None:
        """Extrai array de série histórica em qualquer formato suportado."""

        def _is_series(arr: list) -> bool:
            if not arr:
                return False
            first = arr[0]
            # {"date":"...", "value":...}
            if isinstance(first, dict) and "date" in first:
                return True
            # {"x": timestamp, "y": value}  (Highcharts object)
            if isinstance(first, dict) and "x" in first and "y" in first:
                return True
            # [timestamp, value]  (Highcharts array — > 10 pontos para evitar falsos positivos)
            if isinstance(first, (list, tuple)) and len(first) == 2 and isinstance(first[0], (int, float)) and len(arr) > 10:
                return True
            return False

        def _parse_from(start: int) -> list | None:
            depth = 0
            for i, ch in enumerate(text[start:], start):
                if ch in "[":
                    depth += 1
                elif ch in "]":
                    depth -= 1
                    if depth == 0:
                        try:
                            arr = json.loads(text[start : i + 1])
                            if isinstance(arr, list) and _is_series(arr):
                                return arr
                        except json.JSONDecodeError:
                            pass
                        return None
            return None

        # 1. Busca por chave conhecida (todas as ocorrências)
        for key in ('"chart"', '"data"', '"chartData"', '"historicalData"', '"series"', '"values"'):
            for sep in (f"{key}:[", f"{key}: ["):
                search_from = 0
                while True:
                    idx = text.find(sep, search_from)
                    if idx == -1:
                        break
                    result = _parse_from(text.index("[", idx))
                    if result is not None:
                        return result
                    search_from = idx + 1

        # 2. Busca direta: objeto com "date"
        for marker in ('[{"date":"', '[ {"date":"'):
            idx = text.find(marker)
            while idx != -1:
                result = _parse_from(idx)
                if result is not None:
                    return result
                idx = text.find(marker, idx + 1)

        return None

    def _probe_api_endpoints(self, base_url: str, index_slug: str, referer: str) -> list | None:
        """Testa endpoints de API comuns diretamente."""
        candidates = [
            # Rotas /api/
            f"/api/indices/{index_slug}",
            f"/api/indices/{index_slug}/chart",
            f"/api/indices/{index_slug}/history",
            f"/api/indices/{index_slug}/historico",
            f"/api/chart/{index_slug}",
            f"/api/nossos-indices/{index_slug}",
            f"/api/nossos-indices/{index_slug}/chart",
            f"/api/index/{index_slug}",
            f"/api/v1/indices/{index_slug}",
            f"/api/v1/indices/{index_slug}/chart",
            # Rotas colocalizadas (Next.js App Router route handlers)
            f"/nossos-indices/{index_slug}/chart",
            f"/nossos-indices/{index_slug}/data",
            f"/nossos-indices/{index_slug}/historico",
            f"/nossos-indices/{index_slug}/historical",
            # Com query string
            f"/api/chart?slug={index_slug}",
            f"/api/indices?slug={index_slug}",
        ]
        json_headers = {**self.headers, "Accept": "application/json", "Referer": referer}
        for path in candidates:
            try:
                resp = self.session.get(
                    f"{base_url}{path}", headers=json_headers, verify=False, timeout=10
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                if isinstance(data, list) and data and "date" in data[0]:
                    return data
                series = self._extract_series(json.dumps(data))
                if series:
                    return series
            except Exception:
                pass
        return None

    def _find_api_in_bundles(
        self, bundle_paths: list, base_url: str, index_slug: str
    ) -> str | None:
        """Baixa bundles JS e extrai endpoints de API, incluindo prefixos concatenados."""
        keywords = ["chart", "histor", "serie", "indic", "index", "teva"]

        for js_path in bundle_paths[:20]:
            try:
                resp = self.session.get(
                    f"{base_url}{js_path}", headers=self.headers, verify=False, timeout=15
                )
                text = resp.text
                if len(text) > 800_000:
                    continue

                # Literal completo: "/api/alguma-coisa"
                for m in re.finditer(r'["`](/api/[^"`\s\)]{3,100})["`]', text):
                    c = m.group(1)
                    if any(k in c.lower() for k in keywords):
                        endpoint = re.sub(r'\$\{[^}]+\}|\[[^\]]+\]', index_slug, c)
                        return f"{base_url}{endpoint}"

                # Prefixo concatenado: "/api/alguma-coisa/" + variável
                for m in re.finditer(r'["`](/api/[a-z\-/]+/)["`]', text):
                    prefix = m.group(1)
                    if any(k in prefix for k in keywords):
                        return f"{base_url}{prefix}{index_slug}"

                # fetch("/rota/...") qualquer
                for m in re.finditer(r'fetch\(["\`](/[^"\'`\s\)]{3,80})["\`]', text):
                    url = m.group(1)
                    if any(k in url.lower() for k in keywords):
                        return f"{base_url}{url}".replace("${slug}", index_slug)

            except Exception:
                continue
        return None

    def get_index_history(self, index_slug: str) -> pd.DataFrame:
        base_url = "https://www.tevaindices.com.br"
        page_url = f"{base_url}/nossos-indices/{index_slug}"

        response = self._get(page_url)
        html = response.text
        series = None

        # Estratégia 1: Pages Router — __NEXT_DATA__ + /_next/data/
        next_data_match = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL
        )
        if next_data_match:
            nd = json.loads(next_data_match.group(1))
            json_url = (
                f"{base_url}/_next/data/{nd['buildId']}"
                f"/nossos-indices/{index_slug}.json"
            )
            data = self._get(json_url, referer=page_url).json()
            series = data.get("pageProps", {}).get("index", {}).get("chart")

        # Estratégia 2: RSC payload e busca direta
        rsc_text = ""
        if series is None:
            rsc_resp = self._get(
                page_url,
                extra_headers={
                    "RSC": "1",
                    "Next-Router-State-Tree": "%5B%22%22%2C%7B%7D%2Cnull%2Cnull%2Ctrue%5D",
                    "Next-Url": f"/nossos-indices/{index_slug}",
                    "Accept": "text/x-component",
                },
            )
            rsc_text = rsc_resp.text
            series = self._extract_series(rsc_text) or self._extract_series(html)

        # Estratégia 3: testa endpoints de API comuns
        if series is None:
            print("  Sondando endpoints de API...")
            series = self._probe_api_endpoints(base_url, index_slug, page_url)

        # Estratégia 4: busca nos bundles JS (prioriza os do RSC)
        if series is None:
            rsc_bundles = re.findall(r'"(/_next/static/chunks/[^"]+\.js)"', rsc_text)
            html_bundles = re.findall(r'["\'](/_next/static/chunks/[^"\']+\.js)["\']', html)
            all_bundles = list(dict.fromkeys(rsc_bundles + html_bundles))
            print(f"  Buscando em {len(all_bundles)} bundles JS...")
            api_path = self._find_api_in_bundles(all_bundles, base_url, index_slug)
            if api_path:
                print(f"  Endpoint encontrado: {api_path}")
                data = self._get(api_path, referer=page_url).json()
                series = data if isinstance(data, list) else self._extract_series(json.dumps(data))

        if not series:
            debug_file = "teva_debug4.txt"
            timestamps_in_rsc = re.findall(r'\b1[5-9]\d{11}\b', rsc_text)
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(f"RSC total length : {len(rsc_text):,}\n")
                f.write(f"HTML total length: {len(html):,}\n")
                f.write(f"Unix timestamps in RSC: {len(timestamps_in_rsc)}\n")
                if timestamps_in_rsc:
                    f.write("Sample: " + ", ".join(timestamps_in_rsc[:5]) + "\n")
                f.write("\n=== RSC chars 15000-25000 ===\n")
                f.write(rsc_text[15000:25000])
                f.write("\n\n=== RSC chars 25000-35000 ===\n")
                f.write(rsc_text[25000:35000])
                f.write("\n\n=== RSC last 2000 chars ===\n")
                f.write(rsc_text[-2000:])

            raise ValueError(
                "Não foi possível encontrar os dados do gráfico.\n"
                f"Debug salvo em: {debug_file}"
            )

        first = series[0]
        if isinstance(first, (list, tuple)):
            # Highcharts: [timestamp_ms, value]
            records = [
                {
                    "Data de Referência": pd.to_datetime(int(item[0]), unit="ms"),
                    "Cotação do Índice Retorno Total": float(item[1]),
                }
                for item in series
            ]
        elif isinstance(first, dict) and "x" in first:
            # Highcharts: {"x": timestamp_ms, "y": value}
            records = [
                {
                    "Data de Referência": pd.to_datetime(int(item["x"]), unit="ms"),
                    "Cotação do Índice Retorno Total": float(item["y"]),
                }
                for item in series
            ]
        else:
            # Formato original: {"date": "YYYY-MM-DD", "value": ...}
            records = [
                {
                    "Data de Referência": pd.to_datetime(item["date"]),
                    "Cotação do Índice Retorno Total": float(item["value"]),
                }
                for item in series
            ]
        return pd.DataFrame(records)


def main():
    index_slug = "itbr-selic-indice-teva-tesouro-selic"
    nome_indice = "ITBR SELIC - Índice Teva Tesouro Selic"

    client = TevaIndexClient()

    print("Baixando histórico...")
    try:
        df = client.get_index_history(index_slug)
    except Exception as e:
        print(f"Erro: {e}")
        return

    df["Índice"] = nome_indice

    file_name = f"teva_{datetime.today().strftime('%Y%m%d')}.csv"
    df.to_csv(file_name, index=False, date_format="%Y-%m-%d", encoding="utf-8-sig")

    print(f"Arquivo salvo: {file_name}")
    print(df.head())


if __name__ == "__main__":
    main()
