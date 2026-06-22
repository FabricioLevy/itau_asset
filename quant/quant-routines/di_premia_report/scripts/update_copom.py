"""
Atualiza [research].[monetary_policy_meeting] com as decisões do COPOM.
Fonte: BCB SGS série 4189 via python-bcb (pagina automaticamente o limite de 10 anos da API)

A 'decision' é calculada como a variação em relação à reunião anterior.
Apenas datas novas são inseridas (decisões históricas não mudam).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from bcb import sgs
from sql import SQLConnection

SERIE = 4189
COUNTRY = 'BRL'
DATE_START = '2004-01-01'


def fetch_copom() -> pd.DataFrame:
    df = sgs.get({'rate_target': SERIE}, start=DATE_START)
    df = df.reset_index().rename(columns={'Date': 'date_effective'})
    df['date_effective'] = pd.to_datetime(df['date_effective'])
    df = df.dropna().sort_values('date_effective').reset_index(drop=True)
    df = df.sort_values('date_effective').reset_index(drop=True)

    # decision = variação em relação à reunião anterior
    df['decision'] = df['rate_target'].diff().round(4)

    df['country'] = COUNTRY
    df['official_schedule'] = 1
    return df


def insert_new_rows(conn, df):
    existing = conn.run_query(
        f"SELECT [date_effective] FROM [research].[monetary_policy_meeting] "
        f"WHERE [country] = '{COUNTRY}'"
    )
    existing_dates = set(pd.to_datetime(existing['date_effective']))
    new = df[~df['date_effective'].isin(existing_dates)].copy()

    if new.empty:
        print("COPOM: nenhum dado novo para inserir.")
        return

    new = new[['country', 'date_effective', 'decision', 'rate_target', 'official_schedule']]
    new.to_sql(
        'monetary_policy_meeting', conn.engine,
        schema='research', if_exists='append', index=False
    )
    print(f"COPOM: {len(new)} novas reuniões inseridas.")


if __name__ == '__main__':
    conn = SQLConnection()
    df = fetch_copom()
    insert_new_rows(conn, df)
