"""
Atualiza [middle].[product_price] com a Meta SELIC diária.
Fonte: BCB SGS série 432 via python-bcb (pagina automaticamente o limite de 10 anos da API)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from bcb import sgs
from sql import SQLConnection

SERIE = 432
PRODUCT_ID = 'SELIC TARGET'
DATE_START = '2005-01-01'


def fetch_selic() -> pd.DataFrame:
    df = sgs.get({'rate': SERIE}, start=DATE_START)
    df = df.reset_index().rename(columns={'Date': 'date_reference'})
    df['date_reference'] = pd.to_datetime(df['date_reference'])
    return df[['date_reference', 'rate']].dropna()


def insert_new_rows(conn, df):
    existing = conn.run_query(
        f"SELECT [date_reference] FROM [middle].[product_price] "
        f"WHERE [product_id] = '{PRODUCT_ID}'"
    )
    existing_dates = set(pd.to_datetime(existing['date_reference']))
    new = df[~df['date_reference'].isin(existing_dates)].copy()

    if new.empty:
        print("SELIC TARGET: nenhum dado novo para inserir.")
        return

    new['product_id'] = PRODUCT_ID
    new = new[['date_reference', 'product_id', 'rate']]
    new.to_sql(
        'product_price', conn.engine,
        schema='middle', if_exists='append', index=False
    )
    print(f"SELIC TARGET: {len(new)} novos registros inseridos.")


if __name__ == '__main__':
    conn = SQLConnection()
    df = fetch_selic()
    insert_new_rows(conn, df)
