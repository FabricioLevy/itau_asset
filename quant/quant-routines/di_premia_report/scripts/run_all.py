"""
Executa todos os scripts de atualização do banco na ordem correta.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import datetime
import update_cdi
import update_selic
import update_focus
import update_copom
import seed_inflation_target
import update_interest_rate_curves

steps = [
    ("CDI",                    update_cdi),
    ("SELIC TARGET",           update_selic),
    ("Focus IPCA/SELIC",       update_focus),
    ("COPOM",                  update_copom),
    ("Inflation Target",       seed_inflation_target),
    ("Interest Rate Curves",   update_interest_rate_curves),
]

from sql import SQLConnection
import QuantLib as ql

conn = SQLConnection()

for name, module in steps:
    print(f"\n{'='*50}")
    print(f"  {name}")
    print(f"{'='*50}")
    try:
        if module == update_cdi:
            df = module.fetch_cdi()
            module.ensure_entity(conn)
            sid = module.get_series_id(conn)
            module.insert_new_rows(conn, sid, df)

        elif module == update_selic:
            df = module.fetch_selic()
            module.insert_new_rows(conn, df)

        elif module == update_focus:
            for indicador in module.INDICADORES:
                print(f"  Buscando {indicador}...")
                df = module.fetch_focus(indicador)
                for tenor in module.TENORS:
                    df_t = df[df['type'] == tenor]
                    if df_t.empty:
                        continue
                    sid = module.get_or_create_series(conn, indicador, tenor)
                    n = module.upsert_values(conn, sid, df_t)
                    print(f"    {indicador} {tenor}: {n} registros.")

        elif module == update_copom:
            df = module.fetch_copom()
            module.insert_new_rows(conn, df)

        elif module == seed_inflation_target:
            df = module.load_csv()
            module.upsert_rows(conn, df)

        elif module == update_interest_rate_curves:
            calendar = ql.Brazil()
            today = ql.Date.todaysDate()
            dt = calendar.advance(today, ql.Period(-1, ql.Days)).to_date()
            module.main(dt)

    except Exception as e:
        print(f"  ERRO em {name}: {e}")

print("\nConcluído.")
