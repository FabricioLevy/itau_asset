import os
import pandas as pd
import sql

# Configuration
folder_name = '0_update_bloomberg'
input_path = '../../input/%s' % folder_name
output_path = '../../output/%s' % folder_name
date_start = pd.Timestamp('2005-06-01')
date_d1 = pd.Timestamp.today() - pd.DateOffset(days=1)
date_end = pd.Timestamp(date_d1.strftime('%Y-%m-%d'))
sql_connection = sql.SQLConnection()

# Create output folder
for folder in ['../../output', output_path]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Read list of tickers
ticker_table = pd.read_excel( 
    '%s/tickers.xlsx' % (input_path),
    index_col=0
)

# Request data from bloomberg
tickers = []
for country in ticker_table.index:
    if country == "Brasil":
        continue
    if country in ('Turquia', 'China'):
        continue
    for column in ticker_table:
        ticker = ticker_table[column][country]
        if ticker not in tickers:
            tickers.append( ticker )

data = sql_connection.read_products( tickers, date_start.strftime('%Y-%m-%d') )

for country in ['Euro', 'UK']:
    for column in ticker_table:
        data = pd.concat(
            [
                data,
                sql_connection.read_series( 
                    ticker_table.loc[country, column], 
                    date_start.strftime('%Y-%m-%d')
                )
            ],
            axis = 1
        )

# Substitute PREDI data for sql data
for tenor, ticker in [
    (90,   'PREDI90 Index'), 
    (180,  'PREDI180 Index'), 
    (360,  'PREDI360 Index'), 
    (720,  'PREDI720 Index'), 
    (1800, 'PRDI1800 Index')
]:
    print('Adding for PREDI data:', ticker)
    # Request data
    sql_data = sql_connection.read_predi(tenor)        

    sql_data = pd.DataFrame( [list(x) for x in sql_data], columns=['ticker', ticker])
    sql_data.set_index(keys='ticker', inplace=True)    
    # Substitute    
    for index_item in sql_data.index:
        if index_item in data.index:
            data.loc[index_item, ticker] = sql_data.loc[index_item, ticker]

# Request and update
data.to_excel( '%s/data.xlsx' % (output_path) )