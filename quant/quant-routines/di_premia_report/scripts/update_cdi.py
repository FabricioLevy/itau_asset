"""
Atualiza [quant].[time_series_value] com a taxa CDI diária.
Fonte: BCB SGS série 12 via python-bcb (pagina automaticamente o limite de 10 anos da API)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from bcb import sgs
from sql import SQLConnection

SERIE = 12
ENTITY_ID = 'CDI'
SOURCE = 'bcb'
DATE_START = '2005-01-01'


def fetch_cdi() -> pd.DataFrame:
    df = sgs.get({'value': SERIE}, start=DATE_START)
    df = df.reset_index().rename(columns={'Date': 'date_reference'})
    df['date_reference'] = pd.to_datetime(df['date_reference'])
    return df[['date_reference', 'value']].dropna()


def ensure_entity(conn):
    conn.execute("""
        IF NOT EXISTS (SELECT 1 FROM [quant].[time_series_entity] WHERE [id] = ?)
            INSERT INTO [quant].[time_series_entity] ([id], [refinitiv_symbol], [bloomberg_symbol])
            VALUES (?, NULL, NULL)
    """, [ENTITY_ID, ENTITY_ID])

    conn.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM [quant].[time_series]
            WHERE [entity_id] = ? AND [source] = ?
        )
            INSERT INTO [quant].[time_series]
                ([entity_id], [name], [source], [field], [update_frequency])
            VALUES (?, ?, ?, '-', 'daily')
    """, [ENTITY_ID, SOURCE, ENTITY_ID, ENTITY_ID, SOURCE])


def get_series_id(conn):
    df = conn.run_query(
        f"SELECT [id] FROM [quant].[time_series] "
        f"WHERE [entity_id] = '{ENTITY_ID}' AND [source] = '{SOURCE}'"
    )
    return int(df.iloc[0, 0])


def insert_new_rows(conn, series_id, df):
    existing = conn.run_query(
        f"SELECT [date_reference] FROM [quant].[time_series_value] "
        f"WHERE [series_id] = {series_id}"
    )
    existing_dates = set(pd.to_datetime(existing['date_reference']))
    new = df[~df['date_reference'].isin(existing_dates)].copy()

    if new.empty:
        print("CDI: nenhum dado novo para inserir.")
        return

    new['series_id'] = series_id
    new = new[['series_id', 'date_reference', 'value']]
    new.to_sql(
        'time_series_value', conn.engine,
        schema='quant', if_exists='append', index=False
    )
    print(f"CDI: {len(new)} novos registros inseridos.")


if __name__ == '__main__':
    conn = SQLConnection()
    df = fetch_cdi()
    ensure_entity(conn)
    series_id = get_series_id(conn)
    insert_new_rows(conn, series_id, df)
