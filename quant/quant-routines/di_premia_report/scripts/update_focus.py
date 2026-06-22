"""
Atualiza [bcb].[modulo_focus_series] e [bcb].[modulo_focus_value]
com as expectativas suavizadas de IPCA e SELIC (formato XxxDU).
Fonte: BCB Olinda API - ExpectativasMercadoSuavizadas

Os últimos 30 dias são sempre re-inseridos para capturar revisões.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import time
import requests
import pandas as pd
from sql import SQLConnection

BASE_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
    "ExpectativasMercadoSuavizadas"
)
INDICADORES = ['IPCA', 'SELIC']
TENORS = ['126DU', '252DU', '378DU', '504DU', '1260DU']
PAGE_SIZE = 10000
REVISION_WINDOW_DAYS = 30


def _bcb_get(url, params=None, timeout=90, retries=5, wait=30):
    """GET com retry para erros 5xx da BCB."""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.HTTPError as e:
            if attempt == retries or (resp.status_code < 500):
                raise
            print(f"  BCB {resp.status_code} — tentativa {attempt}/{retries}. Aguardando {wait}s...")
            time.sleep(wait)


def fetch_focus(indicador):
    rows = []
    skip = 0
    tenor_filter = ' or '.join([f"SuavizadoTipoPrazo eq '{t}'" for t in TENORS])
    filter_str = (
        f"Indicador eq '{indicador}' and Suavizado eq 'S' and ({tenor_filter})"
    )

    while True:
        params = {
            '$filter': filter_str,
            '$select': 'Indicador,SuavizadoTipoPrazo,Data,Media',
            '$format': 'json',
            '$top': PAGE_SIZE,
            '$skip': skip,
        }
        resp = _bcb_get(BASE_URL, params=params)
        batch = resp.json().get('value', [])
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        skip += PAGE_SIZE
        print(f"  {indicador}: {len(rows)} registros buscados...")

    df = pd.DataFrame(rows)
    df = df.rename(columns={
        'Indicador': 'indicator',
        'SuavizadoTipoPrazo': 'type',
        'Data': 'date',
        'Media': 'value',
    })
    df['date'] = pd.to_datetime(df['date'])
    df['value'] = df['value'].astype(float)
    return df


def get_or_create_series(conn, indicator, tenor):
    row = conn.run_query(
        f"SELECT [id] FROM [bcb].[modulo_focus_series] "
        f"WHERE [indicator] = '{indicator}' AND [type] = '{tenor}'"
    )
    if not row.empty:
        return int(row.iloc[0, 0])

    conn.execute(
        "INSERT INTO [bcb].[modulo_focus_series] ([indicator], [type]) VALUES (?, ?)",
        [indicator, tenor]
    )
    row = conn.run_query(
        f"SELECT [id] FROM [bcb].[modulo_focus_series] "
        f"WHERE [indicator] = '{indicator}' AND [type] = '{tenor}'"
    )
    return int(row.iloc[0, 0])


def upsert_values(conn, series_id, df_series):
    cutoff = df_series['date'].max() - pd.Timedelta(days=REVISION_WINDOW_DAYS)

    # Remove a janela de revisão para re-inserir
    conn.execute(
        f"DELETE FROM [bcb].[modulo_focus_value] "
        f"WHERE [series_id] = ? AND [date] >= ?",
        [series_id, cutoff.strftime('%Y-%m-%d')]
    )

    # Datas mais antigas: só insere o que não existe
    existing = conn.run_query(
        f"SELECT [date] FROM [bcb].[modulo_focus_value] WHERE [series_id] = {series_id}"
    )
    existing_dates = set(pd.to_datetime(existing['date']))

    to_insert = df_series[~df_series['date'].isin(existing_dates)].copy()
    to_insert['series_id'] = series_id
    to_insert = to_insert[['series_id', 'date', 'value']]

    if not to_insert.empty:
        to_insert.to_sql(
            'modulo_focus_value', conn.engine,
            schema='bcb', if_exists='append', index=False
        )

    return len(to_insert)


if __name__ == '__main__':
    conn = SQLConnection()

    total = 0
    for indicador in INDICADORES:
        print(f"\nBuscando Focus {indicador}...")
        df = fetch_focus(indicador)

        for tenor in TENORS:
            df_tenor = df[df['type'] == tenor]
            if df_tenor.empty:
                continue
            series_id = get_or_create_series(conn, indicador, tenor)
            n = upsert_values(conn, series_id, df_tenor)
            total += n
            print(f"  {indicador} {tenor}: {n} registros inseridos/atualizados.")

    print(f"\nFocus: {total} registros no total.")
