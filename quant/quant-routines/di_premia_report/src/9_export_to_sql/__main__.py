import pandas as pd
import sql
import numpy as np

bloomberg_path = '../../output/0_update_data/bloomberg.xlsx'
premia_path = '../../output/5_export_premia/premia.xlsx'
target_cpi_path = '../../output/1_process_target_cpi/brl_cpi_target.xlsx'
sql_connection = sql.SqlClass()

# Read data
def get_data():
    bloomberg_df = pd.read_excel (bloomberg_path, header=0, index_col=0)
    wanted = ['DAPBEI1Y','DAPBEI2Y','IPCA Focus 1y','IPCA Focus 2y','IPCA Focus 18m']
    available = [c for c in wanted if c in bloomberg_df.columns]
    if not available:
        print('Aviso: nenhuma coluna esperada encontrada em bloomberg.xlsx — Stage 9 sem dados para exportar.')
        return pd.DataFrame()
    bloomberg_df = bloomberg_df[available]
    premia_df = pd.read_excel (premia_path, header=0, index_col=0)
    premia_df = premia_df[['implicit_1y', 'implicit_2y']]
    premia_df.columns = ['Implicit inflation premium 1y', 'Implicit inflation premium 2y']
    target_cpi_df = pd.read_excel(target_cpi_path, header=0, index_col=0)
    target_cpi_df = target_cpi_df[['Target inflation 12m', 'Target inflation 24m', 'Target inflation 18m']]
    target_cpi_df.columns = ['BRL target inflation 1y', 'BRL target inflation 2y', 'BRL target inflation 18m']
    return pd.concat([ bloomberg_df, premia_df, target_cpi_df ], axis=1 )
df = get_data()

if df.empty:
    print('Nenhum dado para exportar.')
    exit(0)

for column in df:
    # get or create time series
    series_id = sql_connection.get_or_create_time_series({
        'entity_id': column
    })

    # insert data
    for index, value in df[column].items():
        if np.isnan(value):
            continue
        print('\r', column, index.strftime('%Y-%m-%d'), value, end='')
        
        item = {
            '[series_id]': series_id,
            '[date_reference]': index.strftime('%Y-%m-%d'),
            '[value]': value,
        }
        sql_connection.batch_insert(
            item,
            '[quant].[time_series_value]',
            ['[series_id]', '[date_reference]'],
            ['[value]'],
        )
    sql_connection.batch_send()
    print('')
