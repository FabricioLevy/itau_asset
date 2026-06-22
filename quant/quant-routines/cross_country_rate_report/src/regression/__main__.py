#%%
import pandas as pd
import matplotlib.pyplot as plt
from sklearn import preprocessing
import seaborn as sns
import numpy as np
import os
from sklearn.decomposition import PCA
from rate_pca import run_rate_pca
from plot import plot_tickers, plot_pca_shape, plot_pca_factor, plot_pairplot
from preprocess import preprocess_country_data, fix_stationarity, normalize_amp
from regression import run_regression, run_regression_2
from adfuller import test_adfuller

input_path = '../../input/update_bloomberg_regression'
input_path_2 = '../../output/update_bloomberg_regression'
output_path = '../../output/regression'

# Create output folder
for folder in ['../../output', output_path]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Load data
print('Reading data')
data = pd.read_excel(
    '%s/data.xlsx' % input_path_2,
    index_col=0
)
print('Reading tickers')
tickers = pd.read_excel(
    '%s/tickers.xlsx' % input_path,
    index_col=0
)
print("Fill na")
filled_data = data.fillna(method='ffill')
print("Preprocess")
country_data = preprocess_country_data(tickers, filled_data)
pc, explained_variance, pc_factor = run_rate_pca(country_data)
# Add pc_factor to country_data
full_data = {}
for country in pc_factor.keys():
    full_data[country] = pd.concat( [ country_data[country], pc_factor[country] ], axis=1).copy()
# Try to fix zero roots
stationary_data = fix_stationarity(full_data)
stationary_normalized_data = normalize_amp( stationary_data )

# Correlation matrix for normalized stationary data
if False:
    country = 'Brasil'
    for shift in range(0, 4):
        for country in stationary_normalized_data.keys():
            print( 'Exporting correlation data with shift', shift, country )
            all_stationary_normalized_data = pd.DataFrame()    
            x = stationary_normalized_data[country].copy()
            index = x.index[1:-(1+shift)]
            curvature = pd.DataFrame( x['curvature'].to_numpy()[1+shift:-1], index=index, columns=['curvature'] )
            dif_slope = pd.DataFrame( x['dif_slope'].to_numpy()[1+shift:-1], index=index, columns=['dif_slope'] )
            dif_level = pd.DataFrame( x['dif_level'].to_numpy()[1+shift:-1], index=index, columns=['dif_level'] )
            x.drop(columns=['dif_slope', 'curvature', 'dif_level'], inplace=True)
            x = pd.concat( [x, curvature, dif_slope, dif_level], axis=1 )
            x.corr().to_excel( '%s/5_corr_s%02d_%s.xlsx' % ( output_path, shift, country ) )
            all_stationary_normalized_data = all_stationary_normalized_data.append( x )
        all_stationary_normalized_data.corr().to_excel( '%s/5_corr_s%02d_all.xlsx' % ( output_path, shift ) )

print('')
#%% Plot
# plot_tickers(data, output_path)
plot_pca_shape( pc, explained_variance, filepath='%s/2_pca.png' % output_path )
plot_pca_factor( country_data, pc_factor, filepath='%s/3_pc_factor_%s.png', output_path=output_path )
# plot_pairplot(country_data, output_path)

#%% Export
# all_data = pd.DataFrame()
# for country in country_data.keys():
#     country_data[country].corr().to_excel('%s/5_corr_%s.xlsx' % (output_path, country))
#     all_data = all_data.append( country_data[country] )
# all_data.corr().to_excel('%s/5_corr_all.xlsx' % (output_path))

# # run regression
if True:
    solution_matrix = {}
    solution_prediction = {}
    for country in stationary_normalized_data.keys():
        # print('________________')
        # print(country)
        solution_matrix_aux, solution_x = run_regression(stationary_normalized_data[country], country)
        solution_matrix[country] = solution_matrix_aux
        solution_prediction[country] = solution_x

        # print( solution_matrix[country] )
        selector = 'slope'
        error = 0
        print(solution_matrix[country])

        x = solution_prediction[country].dropna()
        plt.subplot(2,1,1)
        plt.title('%s - Erro absoluto médio = %.2f' % (country, error) )
        plt.plot( stationary_normalized_data[country][selector], 'k', label=selector)
        plt.plot( solution_prediction[country][selector], 'b--', label='prediction')
        plt.ylabel(selector)
        fig = plt.gcf()
        fig.autofmt_xdate()
        plt.grid()
        plt.legend()
        plt.xlim(( x.index[0], x.index[-1] ))

        plt.subplot(2,1,2)
        plt.plot( stationary_normalized_data[country][selector] - solution_prediction[country][selector], 'b' )
        plt.xlim(( x.index[0], x.index[-1] ))
        plt.ylabel('Error in prediction')
        fig = plt.gcf()
        fig.autofmt_xdate()
        plt.grid()
        plt.savefig( '%s/6_prediction_%s.png' % (output_path, country) )
        plt.close()

# run regression
if False:
    solution_matrix = {}
    solution_prediction = {}
    for country in stationary_normalized_data.keys():
        print('________________')
        print(country)
        solution_matrix_aux, solution_x = run_regression_2(stationary_normalized_data[country], country)
        solution_matrix[country] = solution_matrix_aux
        solution_prediction[country] = solution_x

        print( solution_matrix_aux )

        selector = 'slope'
        x = solution_prediction[country][selector].dropna()
        
        plt.subplot(2,1,1)
        plt.title('%s' % country)
        plt.plot( stationary_normalized_data[country][selector], 'k', label=selector)
        plt.plot( solution_prediction[country][selector], 'b--', label='prediction')
        plt.ylabel(selector)
        fig = plt.gcf()
        fig.autofmt_xdate()
        plt.legend()
        plt.xlim(( x.index[0], x.index[-1] ))

        plt.subplot(2,1,2)
        plt.plot( stationary_normalized_data[country][selector] - solution_prediction[country][selector], 'b' )
        plt.xlim(( x.index[0], x.index[-1] ))
        plt.ylabel('Error in prediction')
        fig = plt.gcf()
        fig.autofmt_xdate()
        plt.savefig( '%s/7_prediction_%s.png' % (output_path, country) )
        # plt.show()
        plt.close()