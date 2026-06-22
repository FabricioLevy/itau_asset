import pandas as pd
import os
import sql
import QuantLib as ql
import numpy as np
calendar = ql.Brazil()

# Configuration
folder_name = '0_update_data'
output_path = '../../output/%s' % folder_name
date_start = pd.Timestamp('2005-01-01')
date_end = pd.Timestamp(
    calendar.adjust(
        ql.Date.todaysDate() - 1,
        ql.Preceding
    ).ISO()
)

# Create output folder
for folder in ['../../output', output_path]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Request data from sql and format it
tenor_dict = {
    180:'PREDI180 Index',
    360: 'PREDI360 Index',
    540: 'PREDI540 Index',
    720: 'PREDI720 Index',
    1800: 'PRDI1800 Index',
}
sql_data = pd.DataFrame()
sql_connection = sql.SqlClass()

focus_ipca = sql_connection.read_ipca_focus_expectation(
    date_start.strftime('%Y-%m-%d'), 
    date_end.strftime('%Y-%m-%d') 
)
other_data = pd.concat(
    [
        sql_connection.read_dap_bei(
            date_start.strftime('%Y-%m-%d'), 
            date_end.strftime('%Y-%m-%d') 
        ),
        sql_connection.read_selic_expectation(
            date_start.strftime('%Y-%m-%d'), 
            date_end.strftime('%Y-%m-%d') 
        ),
        sql_connection.read_cdi(
            date_start.strftime('%Y-%m-%d'), 
            date_end.strftime('%Y-%m-%d') 
        )
    ],
    axis=1
).sort_index().ffill()
if 'BZSTSETA Index' not in other_data.columns:
    print('Aviso: SELIC TARGET não encontrada no banco — coluna BZSTSETA Index ausente.')
    other_data['BZSTSETA Index'] = float('nan')
other_data['BZSTSETA Index'] = other_data['BZSTSETA Index'].shift(1)
other_data['gap selic'] = other_data['BZSTSETA Index'] - other_data['CDI']
other_data['gap selic'] = other_data['gap selic'].ffill()
other_data['gap selic'] = other_data['gap selic'].bfill()
other_data['date'] = [pd.Timestamp(x) for x in other_data.index]
other_data.set_index('date', inplace=True)

for tenor in [180, 360, 540, 720, 1800]:
    di_future = sql_connection.read_predi( 
        tenor, 
        date_start.strftime('%Y-%m-%d'), 
        date_end.strftime('%Y-%m-%d') 
    )
    di_future = pd.DataFrame(
        [x[1] for x in di_future],
        columns = [ tenor_dict[tenor] ],
        index = [x[0] for x in di_future],
    )    
    sql_data = pd.concat([ sql_data, di_future ], axis=1)
sql_data.rename_axis(None, inplace=True)
sql_data['date'] = [pd.Timestamp(x) for x in sql_data.index]
sql_data.set_index('date', inplace=True)

# Processing
data = pd.concat([ other_data, sql_data, focus_ipca ], axis=1)
data.ffill(inplace=True)
data['date2'] = [x.date() for x in data.index]
data.set_index('date2', inplace=True)
data.rename_axis('Dates', inplace=True)

# Compute CDI
aux = (data['CDI']/100 + 1)
for duration in tenor_dict.keys():
    duration_aux = int(duration * 252 / 360)
    data["CDI%d" % duration] = (
        aux[::-1].rolling(duration_aux).apply(np.prod, raw=True)[::-1] ** (1/duration_aux)- 1
    ) * 100

# Export
# pylint: disable=abstract-class-instantiated
with pd.ExcelWriter('%s/bloomberg.xlsx' % output_path) as writer:
    print('Writing data')
    data.to_excel( writer )
# pylint: enable=abstract-class-instantiated