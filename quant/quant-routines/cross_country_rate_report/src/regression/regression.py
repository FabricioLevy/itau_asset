
import pandas as pd
import matplotlib.pyplot as plt
from sklearn import preprocessing, linear_model
import seaborn as sns
import numpy as np
import os
from sklearn.decomposition import PCA

def run_regression(data, country):
    clean_data = data.dropna().truncate(after=pd.Timestamp('2020-02-01'))
    # clean_data = data.dropna()

    # Select x data
    a_columns = [    
        # 'dif_cc%',
        # 'dif_divbruta%',
        # 'dif_divpub%',
        # # 'dif_txpre60m',
        # # 'dif_txpre24m',
        # 'dif_txpre12m',
        # # 'dif_txpre06m',
        # # 'dif_txpre03m',
        # 'dif_txdes',
        # 'dif_fdi%',
        # 'dif_defnom%',
        # 'dif_cpi',
        # 'dif_cpiforecast',
        # 'dif_jurobc',

        'cc%',
        'divbruta%',
        'divpub%',
        # # 'txpre60m',
        # 'txpre24m',
        'txpre12m',
        # # # 'txpre06m',
        # # # 'txpre03m',
        'txdes',
        'fdi%',
        'defnom%',
        'cpi',
        'cds5y',
        # 'cds10y',
        # 'pardivnresid',
        # 'cpiforecast',
        'jurobc',
        # 'expjuros',
        # 'curvature',
        # 'level',
    ]
    a_columns = [column for column in a_columns if column in clean_data]
    a_data = clean_data[a_columns].to_numpy()  # dimension (t, n)
    a2_data = data[a_columns].dropna()  # dimension (t2, n)
    
    # Select y data
    y_columns = ['dif_slope', 'slope']
    y_columns = [column for column in y_columns if column in clean_data]
    y_data = clean_data[y_columns].to_numpy() # dimension (t, m)
    
    # Auxiliar c matrix
    regression = linear_model.LinearRegression()

    regression.fit( a_data, y_data )

    solution = regression
    index = a_columns.copy()
    index.append('constant')

    solution_matrix = pd.DataFrame(
        np.transpose(
            np.concatenate( (solution.coef_, solution.intercept_.reshape((1,-1))), axis=1 ) 
        ), 
        index=index, 
        columns=y_columns 
    )

    a_hat = pd.DataFrame(
        regression.predict(a2_data),
        columns=y_columns,
        index=a2_data.index
    )
    return solution_matrix, a_hat

def run_regression_2(data, country):
    # Select x data
    a_columns = [    
        # 'dif_cc%',
        # 'dif_divbruta%',
        # 'dif_divpub%',
        # # 'dif_txpre60m',
        # # 'dif_txpre24m',
        # 'dif_txpre12m',
        # # 'dif_txpre06m',
        # # 'dif_txpre03m',
        # 'dif_txdes',
        # 'dif_fdi%',
        # 'dif_defnom%',
        # 'dif_cpi',
        # 'dif_cpiforecast',
        # 'dif_jurobc',
        # 'dif_slope',
        'cc%',
        'divbruta%',
        'divpub%',
        # 'txpre60m',
        # 'txpre24m',
        'txpre12m',
        # 'txpre06m',
        # 'txpre03m',
        'txdes',
        'fdi%',
        'defnom%',
        'cpi',
        'cpiforecast',
        'jurobc',
        'slope'
    ]
    a_columns = [column for column in a_columns if column in data]
    a_data = data[a_columns].to_numpy()  # dimension (t, n)
    
    # Auxiliar c matrix
    aux0 = pd.DataFrame( a_data[0:-1, :], index=data.index[1:], columns=['0_%s' % x for x in a_columns])
    aux1 = pd.DataFrame( a_data[1:, :], index=data.index[1:], columns=['1_%s' % x for x in a_columns])
    
    joined_data = pd.concat( 
        [aux0, aux1],
        axis=1
    ).dropna()
    a_d0 = joined_data[ joined_data.columns[0:(len(a_columns))] ].to_numpy()
    a_d1 = joined_data[ joined_data.columns[len(a_columns):(2*len(a_columns))] ].to_numpy()

    solution = np.matmul( np.linalg.pinv( a_d0 ), a_d1 )
    
    solution_matrix = pd.DataFrame( 
        solution, 
        index=a_columns, 
        columns=a_columns 
    )

    a_hat = pd.DataFrame(
        np.matmul( a_data[0:-1, :], solution ),
        columns=a_columns,
        index=data.index[1:]
    )
    return solution_matrix, a_hat