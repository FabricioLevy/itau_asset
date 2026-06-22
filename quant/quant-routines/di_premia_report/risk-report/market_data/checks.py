import pandas as pd
import datetime

def check_missing_product(connection, ids, dt=None):
    if dt is None:
        dt = datetime.datetime.today()
    str_sql = """
        SELECT [id]
          FROM [middle].[product] 
        WHERE date_maturity>='{:%Y-%m-%d}' 
             AND id in ('{}')
        """
    str_sql = str_sql.format(dt, "','".join(ids))
    df = pd.read_sql(str_sql, connection)
    return set(ids) - set(df['id'].values)