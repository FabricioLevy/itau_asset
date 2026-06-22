import process
import numpy as np
import pandas as pd
import time
import matplotlib.pyplot as plt
import os
import pickle

# _______________________________________________________________________________________________
# Config
input_path = '../../output/0_download_data'
output_path = '../../output/4_further_analysis'
window_in_days = 15

# _______________________________________________________________________________________________
# Create output path
for folder in ['../../output', output_path]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# _______________________________________________________________________________________________
# Read data
master_data = pd.read_excel('%s/master_data.xlsx' % input_path, index_col=0)
product_data = pd.read_excel('%s/product_data.xlsx' % input_path, index_col=0)

# _______________________________________________________________________________________________
# Preprocessing
product_exp_returns_df, fund_exp_returns_df = process.compose_matrixes( 
    product_data, 
    master_data 
)
print(product_exp_returns_df)
print(fund_exp_returns_df)

# _________________________
_, r2_20du, _, _, _, r2_20du_2, beta = process.regression_3(
    product_exp_returns_df, 
    fund_exp_returns_df,
    window_in_days=20
)
r2_20du.to_excel('%s/r2_20du.xlsx' % output_path, 'wb')

_, r2_60du, _, _, _, r2_60du_2, beta = process.regression_3(
    product_exp_returns_df, 
    fund_exp_returns_df,
    window_in_days=60
)
r2_60du.to_excel('%s/r2_60du.xlsx' % output_path, 'wb')

plt.plot(r2_20du, label='Regression R2')
plt.plot(r2_20du.index, r2_20du_2, label='Reduced regression R2')
plt.grid()
plt.legend()
plt.ylabel('R2')
plt.savefig('%s/r2.png' % output_path)
plt.close()

plt.plot(r2_20du.index, r2_20du_2, label='Reduced regression R2')
plt.plot(r2_20du.index, beta, label='Reduced regression beta')
plt.legend()
plt.grid()
plt.savefig('%s/r2_beta.png' % output_path)
plt.close()

plt.plot(r2_20du_2, beta, 'x')
plt.xlabel('Reduced regression R2')
plt.ylabel('Reduced regression beta')
plt.grid()
plt.savefig('%s/r2_beta_scatter.png' % output_path)
plt.close()

# _______________________________________________________________________________________________
# Process 2

print(product_exp_returns_df)
combined_df = pd.DataFrame()
combined_df['Ones'] = product_exp_returns_df['Ones']
combined_df['Combined'] = (
    - 1 * product_exp_returns_df['PREDI720']
    + 0.05 * product_exp_returns_df['IBOV']
    + 0.02 * product_exp_returns_df['SPX']
    - 0.05 * product_exp_returns_df['USDBRL']
)

# _______________________________________________________________________________________________
# Process
results = {}
for window_in_days in [15, 252, 756]:
    print('________________________')
    tic = time.process_time()
    results[window_in_days], _, _, _, _ = process.regression(
        product_exp_returns_df, 
        fund_exp_returns_df,
        window_in_days=window_in_days
    )
    toc = time.process_time()
    print(toc-tic)

# _______________________________________________________________________________________________
# Process
results_2 = {}
for window_in_days in [15, 20, 60, 252, 756]:
    tic = time.process_time()
    results_2[window_in_days], _, _, _, _ = process.regression_2(
        product_exp_returns_df, 
        fund_exp_returns_df,
        window_in_days=window_in_days
    )
    toc = time.process_time()
    print(toc-tic)

# _________________________
output = open('%s/results_1.pkl' % output_path, 'wb')
pickle.dump(results, output)
output.close()

output = open('%s/results_2.pkl' % output_path, 'wb')
pickle.dump(results_2, output)
output.close()

