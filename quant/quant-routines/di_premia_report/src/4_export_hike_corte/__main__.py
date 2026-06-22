import sql
import pandas as pd
import os 

output_path = '../../output/4_export_hike_corte'

# Create output folder
for folder in ['../../output', output_path]:
    if not os.path.exists(folder):
        os.makedirs(folder)


sql_connection = sql.SQLConnection()
data = sql_connection.read_copom()
hike_corte = pd.DataFrame( data['decision'] )
hike_corte.loc[hike_corte['decision'] > 0, 'decision'] = 1
hike_corte.loc[hike_corte['decision'] < 0, 'decision'] = -1
hike_corte.rename(columns={'decision': 'Flag'}, inplace=True)

print(hike_corte)

with pd.ExcelWriter(
    '%s/hike_corte.xlsx' % output_path,
    engine='xlsxwriter',
    datetime_format='dd/mm/yyyy',
    date_format='dd/mm/yyyy'
) as excel_writer:
    hike_corte.to_excel(excel_writer, index=True)