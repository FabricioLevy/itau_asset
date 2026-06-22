import numpy as np
import pandas as pd
import time
import matplotlib.pyplot as plt
import os
import plot
import pickle

# _______________________________________________________________________________________________
# Configuration
input_path = '../../output/4_further_analysis'
output_path = '../../output/5_further_analysis_plot'

# _______________________________________________________________________________________________
# Create output path
for folder in ['../../output', output_path]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# _______________________________________________________________________________________________
# Load data
pkl_file = open('%s/results_1.pkl' % input_path, 'rb')
results = pickle.load(pkl_file)
pkl_file = open('%s/results_2.pkl' % input_path, 'rb')
results_2 = pickle.load(pkl_file)

# _______________________________________________________________________________________________
# PLOTS
for window_in_days in [15, 252, 756]:
    for key in results_2[window_in_days].keys():
        print('________________________')
        print(key)
        mean_1 = results[window_in_days][key].mean(axis=1)
        mean_2 = results_2[window_in_days][key].mean(axis=1)
        plt.plot(
            mean_1,
            mean_2,
            '.',
        )
        plt.plot(
            [mean_1.min(), mean_1.max()],
            [mean_1.min(), mean_1.max()],
            '-'
        )
        plt.xlabel('Mean of regression')
        plt.ylabel('Regression of mean')
        plt.grid()
        plt.title('Mean of regression vs regression of mean %s- %d' % (key, window_in_days) )
        plt.savefig('%s/mean_vs_mean_%s_%03d.png' % (output_path, key, window_in_days))
        plt.close()

for key in results_2[252].keys():
    print('________________________')
    print(key)
    mean_1 = results_2[252][key].mean(axis=1)
    mean_2 = results_2[756][key].mean(axis=1)
    plt.plot(
        mean_1,
        mean_2,
        '.',
    )
    plt.plot(
        [mean_1.min(), mean_1.max()],
        [mean_1.min(), mean_1.max()],
        '-'
    )
    plt.xlabel('252 DU')
    plt.ylabel('756 DU')
    plt.grid()
    plt.title('Scatter plot of funds regression result of the mean %s- 252 vs 756' % key) 
    plt.savefig('%s/regression_of_mean_%s.png' % (output_path, key))
    plt.close()

for key_i, key in enumerate(results[window_in_days].keys()):
    for window_in_days in [15, 252, 756]:
        plt.plot(
            results[window_in_days][key].mean(axis=1), 
            '+',
            label='Mean of regression %d DU' % window_in_days,
        )
    for window_in_days in [15, 252, 756]:
        plt.plot(
            results_2[window_in_days][key].mean(axis=1), 
            '-',
            label='Regression of mean %d DU' % window_in_days,
        )
    plt.ylabel(key)
    plt.grid()
    plt.title('Regression results - %s' % key ) 
    plt.legend()
    plt.tight_layout()
    plt.savefig('%s/result_%s.png' % (output_path, key))
    plt.close()

for key in results[252].keys():
    print('________________________')
    print(key)
    mean_1 = results[252][key].mean(axis=1)
    mean_2 = results[756][key].mean(axis=1)
    plt.plot(
        mean_1,
        mean_2,
        '.',
    )
    plt.plot(
        [mean_1.min(), mean_1.max()],
        [mean_1.min(), mean_1.max()],
        '-'
    )
    plt.xlabel('252 DU')
    plt.ylabel('756 DU')
    plt.grid()
    plt.title('Scatter plot of mean of funds regression results %s- 252 vs 756' % key) 
    plt.savefig('%s/scatter_%s.png' % (output_path, key))
    plt.close()

# plt.plot( results_2[252]['IBOV'].mean(axis=1),results_2[252]['USDBRL'].mean(axis=1), 'x' )
# plt.grid()
# plt.xlabel('IBOV')
# plt.ylabel('USDBRL')
# plt.show()

# plt.plot( results_2[252]['PREDI720'].mean(axis=1),results_2[252]['USDBRL'].mean(axis=1), 'x' )
# plt.grid()
# plt.xlabel('PREDI720')
# plt.ylabel('USDBRL')
# plt.show()

# plt.plot( results_2[252]['SPX'].mean(axis=1),results_2[252]['IBOV'].mean(axis=1), 'x' )
# plt.grid()
# plt.xlabel('SPX')
# plt.ylabel('IBOV')
# plt.show()

# plt.plot( results_2[252]['SPX'].mean(axis=1),results_2[252]['USDBRL'].mean(axis=1), 'x' )
# plt.grid()
# plt.xlabel('SPX')
# plt.ylabel('USDBRL')
# plt.show()