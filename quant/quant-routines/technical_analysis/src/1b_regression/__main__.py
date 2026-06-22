import pandas as pd
from datetime import date
import os
import process
import matplotlib.pyplot as plt
import QuantLib as ql
import numpy as np
import pickle
calendar = ql.Brazil()

# _______________________________________________________________________________________________
# Configuration
input_path = '../../output/0_download_data'
output_path = '../../output/1b_regression'

# _______________________________________________________________________________________________
# Create output path
for folder in ['../../output', output_path]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# _______________________________________________________________________________________________
# Read data
print('Read data')
master_data = pd.read_excel('%s/master_data.xlsx' % input_path, index_col=0)
fic_data = pd.read_excel('%s/fic_data.xlsx' % input_path, index_col=0)
product_data = pd.read_excel('%s/product_data.xlsx' % input_path, index_col=0)
# Get dates
date_end = product_data.index[-1]
date_d252 = date_end - pd.DateOffset(days=252)

# _______________________________________________________________________________________________
# Calculate returns
print('Get returns')
master_returns, fic_returns, product_returns = process.get_returns(
    master_data, 
    fic_data, 
    product_data
)

# Calculate log returns (pre is returned with simple differences)
print('Get log returns')
asset_log_return = process.get_log_returns(master_data)
product_log_return = process.get_log_returns(product_data)
a_matrix = product_log_return[['PREDI720 Index', 'IBOV Index', 'SPX Index', 'USDBRL Curncy' ]]
b_matrix = asset_log_return.copy()

# _______________________________________________________________________________________________
# Asset volatility
print('Get volatility')
asset_volatility = fic_returns.truncate(
    before=date_d252
).std().sort_index() * (252 ** .5) * 100

# _______________________________________________________________________________________________
# Regression
regression = {}
for window_in_days in [15]:
    regression[window_in_days] = process.regression( 
        a_matrix, 
        b_matrix, 
        window_in_days=window_in_days
    )

# _______________________________________________________________________________________________
# Export data
product_log_return.to_excel('%s/product_log_return.xlsx' % output_path)
asset_log_return.to_excel('%s/asset_log_return.xlsx' % output_path)

output = open('%s/regression.pkl' % output_path, 'wb')
pickle.dump(regression, output)
output.close()

