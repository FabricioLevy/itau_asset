import pandas as pd
from datetime import date
import sql
import os
import QuantLib as ql

calendar = ql.Brazil()
# _______________________________________________________________________________________________
# Configuration
date_start = '2013-01-01'
date_end = calendar.advance(
    ql.Date.todaysDate(),
    ql.Period('-2d'),
    ql.Preceding
).ISO()
output_path = '../../output/0_download_data'

# _______________________________________________________________________________________________
# Create output path
for folder in ['../../output', output_path]:
    if not os.path.exists(folder):
        os.makedirs(folder)
# _______________________________________________________________________________________________
# Read data
sql_connection = sql.SQLConnection()
print('Read asset info')
master_info = sql_connection.read_assets(use_fic=False)
fic_info = sql_connection.read_assets(use_fic=True)
master_dict = { 
    x:y 
    for x, y 
    in zip( master_info['cnpj'].values, master_info['plot_name'].values )
}
fic_dict = { 
    x:y 
    for x, y 
    in zip( fic_info['cnpj'].values, fic_info['plot_name'].values )
}
print('Read asset data')
master_data = sql_connection.read_asset_data(
    date_start, 
    date_end, 
    master_dict
)
fic_data = sql_connection.read_asset_data(
    date_start, 
    date_end, 
    fic_dict
)
# Product data
print("Reading product data")
product_data = pd.concat(
    [
        sql_connection.read_predi(date_start, date_end),
        sql_connection.read_other(date_start, date_end),
    ],
    axis=1 
).sort_index()
# Concatenate data
# print(product_data)
# print(master_data)
# print(fic_data)
# quit()
data = pd.concat(
    [
        product_data,
        master_data,
        fic_data
    ],
    axis=1 
).sort_index().dropna(subset=product_data.columns.values)
data = data.loc[:,~data.columns.duplicated()]
# Export data
print('Exporting data')
print(data)
data[master_data.columns].rename(columns=master_dict).to_excel('%s/master_data.xlsx' % output_path)
data[product_data.columns].to_excel('%s/product_data.xlsx' % output_path)
data[fic_data.columns].rename(columns=fic_dict).to_excel('%s/fic_data.xlsx' % output_path)
