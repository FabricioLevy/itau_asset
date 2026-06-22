from datetime import date
import sql 
import pandas as pd
from encapsulation import (
    get_target_inflation,
    get_12m_target_inflation,
    get_24m_target_inflation
)
import matplotlib.pyplot as plt
import os

output_path = '../../output/1_process_target_cpi' 
input_path = '../../output/0_update_data'

# Create output folder
for folder in ['../../output', output_path]:
    if not os.path.exists(folder):
        os.makedirs(folder)
other_data = pd.read_excel('%s/bloomberg.xlsx' % input_path, index_col=0)
other_data.index = [pd.Timestamp(x) for x in other_data.index]

# Process
sql_connection = sql.SqlClass()
expectation_data = sql_connection.read_inflation_target()

# Tenta ler DAPBEI1Y do banco (populado pelo Stage 9 em runs anteriores).
# No primeiro run, usa o dado do bloomberg.xlsx como fallback.
try:
    dap_bei_1y = sql_connection.read_time_series('DAPBEI1Y')
    if dap_bei_1y.empty:
        raise ValueError('Série vazia')
except Exception:
    print('DAPBEI1Y não encontrado no banco — usando bloomberg.xlsx como fallback.')
    dap_bei_1y = other_data[['DAPBEI1Y']].rename(columns={'DAPBEI1Y': 'value'})

result_list = []
print('Processing target inflation:')
for current_date in dap_bei_1y.index:
    # if current_date <= pd.Timestamp('2021-05-20'):
        # continue
    # if current_date >= pd.Timestamp('2019-01-01'):
    #     continue
    print('\r %s' % current_date.strftime('%Y-%m-%d'), end='')
    pi_12m, pi_upper_12m, pi_lower_12m = get_target_inflation(current_date, expectation_data, 252)
    pi_18m, pi_upper_18m, pi_lower_18m = get_target_inflation(current_date, expectation_data, 378)
    pi_24m, pi_upper_24m, pi_lower_24m = get_target_inflation(current_date, expectation_data, 504)
    result_list.append([current_date, pi_12m, pi_24m, pi_upper_12m, pi_upper_24m, pi_lower_12m, pi_lower_24m, pi_18m])
result = pd.DataFrame(
    result_list, 
    columns=[
        'date', 
        'Target inflation 12m', 
        'Target inflation 24m', 
        'Target inflation upper limit 12m', 
        'Target inflation upper limit 24m',
        'Target inflation lower limit 12m', 
        'Target inflation lower limit 24m',
        'Target inflation 18m',
    ]
).set_index('date')
print('')
result.to_excel('%s/brl_cpi_target.xlsx' % output_path)
# try:
#     result.to_excel('%s/brl_cpi_target.xlsx' % output_path)
# except:
#     pass
# print('')

# plt.plot(result['Target Inflation 12m'])
# plt.show()
