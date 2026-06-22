"""
Popula [research].[inflation_target_rate] a partir do CSV de referência.
Fonte: doc/brl_target_inflation.csv (atualização manual, uma vez por ano em junho)

O CSV original usa nomes de coluna antigos (target, tolerance, realized).
Este script faz o mapeamento para os nomes usados nas queries do pipeline
(rate_target, rate_tolerance, rate_realized).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from sql import SQLConnection

CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'doc', 'brl_target_inflation.csv')


def load_csv():
    df = pd.read_csv(CSV_PATH)
    df = df.rename(columns={
        'target':    'rate_target',
        'tolerance': 'rate_tolerance',
        'realized':  'rate_realized',
    })
    df['date_reference'] = pd.to_datetime(df['date_reference'], dayfirst=True)
    df['date_publish']   = pd.to_datetime(df['date_publish'],   dayfirst=True)
    df['rate_target']    = df['rate_target'].astype(float)
    df['rate_tolerance'] = df['rate_tolerance'].astype(float)
    df['rate_realized']  = pd.to_numeric(df['rate_realized'], errors='coerce')
    return df


def upsert_rows(conn, df):
    for _, row in df.iterrows():
        conn.execute("""
            MERGE [research].[inflation_target_rate] AS t
            USING (
                SELECT ? AS country, ? AS date_reference, ? AS date_publish
            ) AS s
            ON t.[country] = s.country
               AND t.[date_reference] = s.date_reference
               AND t.[date_publish]   = s.date_publish
            WHEN MATCHED THEN
                UPDATE SET
                    [rate_target]    = ?,
                    [rate_tolerance] = ?,
                    [rate_realized]  = ?,
                    [obs]            = ?
            WHEN NOT MATCHED THEN
                INSERT ([country],[date_reference],[date_publish],
                        [rate_target],[rate_tolerance],[rate_realized],[obs])
                VALUES (?,?,?,?,?,?,?);
        """, [
            # USING clause
            row['country'],
            row['date_reference'].strftime('%Y-%m-%d'),
            row['date_publish'].strftime('%Y-%m-%d'),
            # UPDATE
            row['rate_target'],
            row['rate_tolerance'],
            None if pd.isna(row['rate_realized']) else row['rate_realized'],
            row.get('obs'),
            # INSERT
            row['country'],
            row['date_reference'].strftime('%Y-%m-%d'),
            row['date_publish'].strftime('%Y-%m-%d'),
            row['rate_target'],
            row['rate_tolerance'],
            None if pd.isna(row['rate_realized']) else row['rate_realized'],
            row.get('obs'),
        ])

    print(f"Inflation Target: {len(df)} registros inseridos/atualizados.")


if __name__ == '__main__':
    conn = SQLConnection()
    df = load_csv()
    upsert_rows(conn, df)
