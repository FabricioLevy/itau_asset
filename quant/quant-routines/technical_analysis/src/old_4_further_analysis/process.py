import numpy as np
from sklearn.linear_model import Ridge, Lasso, LinearRegression
from sklearn.metrics import r2_score
import sys
import pandas as pd
import statsmodels.api as sm

def compose_matrixes(product_data, master_data):
    usdbrl = product_data['USDBRL Curncy'].to_numpy()
    predi720 = product_data['PREDI720 Index'].to_numpy() / 100
    spx = product_data['SPX Index'].to_numpy()
    ibov = product_data['IBOV Index'].to_numpy()

    a_matrix = np.zeros((ibov.shape[0]-1, 5))
    # A.x = y    ->    x = pinv(A'.A) . (A'.y)
    # A = [{1}, {USDBRL}, {PREDI720}, {SPX}, {IBOV}]
    # x = {regression coef}
    # y = {fund return}
    a_matrix[:, 0] = int(1)
    a_matrix[:, 1] = np.subtract(np.log(usdbrl[1:usdbrl.shape[0]]), np.log(usdbrl[0:usdbrl.shape[0]-1]))
    a_matrix[:, 2] = np.subtract(predi720[1:predi720.shape[0]], predi720[0:predi720.shape[0]-1])
    a_matrix[:, 3] = np.subtract(np.log(spx[1:spx.shape[0]]), np.log(spx[0:spx.shape[0]-1]))
    a_matrix[:, 4] = np.subtract(np.log(ibov[1:ibov.shape[0]]), np.log(ibov[0:ibov.shape[0]-1]))
    a_matrix = pd.DataFrame(
        a_matrix,
        index=product_data.index[1:],
        columns=['Ones', 'USDBRL', 'PREDI720', 'SPX', 'IBOV']
    )

    y_matrix = pd.DataFrame(index=master_data.index[1:])
    for column in master_data.columns:
        aux = master_data[column].to_numpy()
        y_matrix[column] = np.subtract(np.log(aux[1:aux.shape[0]]), np.log(aux[0:aux.shape[0]-1]))
    y_matrix = y_matrix
    return a_matrix, y_matrix

def regression(product_df, fund_df, window_in_days=15, **kwarg):
    # 
    a_matrix = product_df.to_numpy()
    a_matrix_shape = a_matrix.shape
    funds = {}
    aux_index = range(fund_df.shape[0]-1)
    funds_rmse = pd.DataFrame(columns=fund_df.columns, index=aux_index)
    funds_y_hat = pd.DataFrame(columns=fund_df.columns, index=aux_index)
    funds_y_hat_2 = pd.DataFrame(columns=fund_df.columns, index=aux_index)
    funds_r2 = pd.DataFrame(columns=fund_df.columns, index=aux_index)
    nan_array = np.zeros((a_matrix_shape[0]-1,)) * np.nan
    nan_matrix = np.zeros((a_matrix_shape[1], a_matrix_shape[0])) * np.NaN
    for column in fund_df.columns:
        print(column)
        # Selection fund value
        y = fund_df[column].values

        # Declare variables
        y_hat = nan_array.copy()
        y_hat_2 = nan_array.copy()
        rmse = nan_array.copy()
        x_matrix = nan_matrix.copy()
        r2 = nan_array.copy()

        # Run regression for moving window
        for start_index in range(a_matrix_shape[0] - window_in_days - 1):
            # Select current section of data
            a_mse = a_matrix[ start_index:(start_index + window_in_days), : ]
            y_mse = y[start_index:(start_index + window_in_days)]
            if start_index == y.shape[0] - window_in_days:
                a_mse_2 = (a_mse * np.nan).copy()
            else:
                a_mse_2 = (
                    a_matrix[ start_index+1:(start_index + window_in_days+1), : ]
                ).copy()
            
            # Verify data
            if np.any(np.isnan(a_mse)):
                continue
            if np.any(np.isnan(y_mse)):
                continue
            if np.linalg.cond(
                np.matmul(np.transpose(a_mse), a_mse)
            ) > 1/sys.float_info.epsilon:
                continue
            
            # Process
            x_mse = np.linalg.solve(
                np.matmul(a_mse.T, a_mse),
                np.matmul(a_mse.T, y_mse)
            )
            sstot = np.sum( ( y_mse - y_mse.mean() ) ** 2 )
            ssreg = np.sum( ( y_mse - np.matmul( a_mse, x_mse ) )**2 )
            r2[ start_index + window_in_days ] = 1. - ssreg / sstot
            y_hat[(start_index + window_in_days)] = (
                np.exp( np.matmul(a_mse, x_mse) ) - 1
            )[-1]
            if start_index + window_in_days + 1 < y.shape[0] - 1:
                y_hat_2[start_index + window_in_days + 1] = (
                    np.exp( np.matmul(a_mse_2, x_mse) ) - 1
                )[-1]

            rmse[start_index + window_in_days] = ( 
                (
                    np.sum( ( y_mse - np.matmul( a_mse, x_mse ) )**2 )
                ) / len(y_mse)
            ) **  (1/2)
            
            x_matrix[:, start_index + window_in_days] = x_mse
        funds[column] = pd.DataFrame(
            np.transpose(x_matrix),
            columns=['Level', 'USDBRL', 'PREDI720', 'SPX', 'IBOV'],
            index=fund_df.index.values
        )
        funds_r2[column] = r2
        funds_y_hat[column] = y_hat
        funds_y_hat_2[column] = y_hat_2
        funds_rmse[column] = rmse
    funds_r2.index = product_df.index[1:]
    funds_y_hat.index = product_df.index[1:]
    funds_y_hat_2.index = product_df.index[1:]
    funds_rmse.index = product_df.index[1:]

    results = {}
    for key in ['Level', 'USDBRL', 'PREDI720', 'SPX', 'IBOV']:
        results[key] = pd.DataFrame()
        for column in funds.keys():
            results[key][column] = funds[column][key]
        results[key].index = [pd.Timestamp(x) for x in results[key].index]
    return results, funds_r2, funds_y_hat, funds_y_hat_2, funds_rmse

def regression_2(product_df, fund_df, window_in_days=15, **kwarg):
    # 
    a_matrix = product_df.to_numpy()
    a_matrix_shape = a_matrix.shape
    funds = {}
    aux_index = range(fund_df.shape[0]-1)
    funds_rmse = pd.DataFrame(columns=['All'], index=aux_index)
    funds_y_hat = pd.DataFrame(columns=['All'], index=aux_index)
    funds_y_hat_2 = pd.DataFrame(columns=['All'], index=aux_index)
    funds_r2 = pd.DataFrame(columns=['All'], index=aux_index)
    nan_array = np.zeros((a_matrix_shape[0]-1,)) * np.nan
    nan_matrix = np.zeros((a_matrix_shape[1], a_matrix_shape[0])) * np.NaN
    
    column = 'All'

    # Selection fund value
    y = fund_df.mean(axis=1)

    # Declare variables
    y_hat = nan_array.copy()
    y_hat_2 = nan_array.copy()
    rmse = nan_array.copy()
    x_matrix = nan_matrix.copy()
    r2 = nan_array.copy()

    # Run regression for moving window
    for start_index in range(a_matrix_shape[0] - window_in_days - 1):
        # Select current section of data
        a_mse = a_matrix[ start_index:(start_index + window_in_days), : ]
        y_mse = y[start_index:(start_index + window_in_days)]

        
        if start_index == y.shape[0] - window_in_days:
            a_mse_2 = (a_mse * np.nan).copy()
        else:
            a_mse_2 = (
                a_matrix[ start_index+1:(start_index + window_in_days+1), : ]
            ).copy()
        
        # Verify data
        if np.any(np.isnan(a_mse)):
            continue
        if np.any(np.isnan(y_mse)):
            continue
        if np.linalg.cond(
            np.matmul(np.transpose(a_mse), a_mse)
        ) > 1/sys.float_info.epsilon:
            continue
        
        # Process
        x_mse = np.linalg.solve(
            np.matmul(a_mse.T, a_mse),
            np.matmul(a_mse.T, y_mse)
        )
        sstot = np.sum( ( y_mse - y_mse.mean() ) ** 2 )
        ssreg = np.sum( ( y_mse - np.matmul( a_mse, x_mse ) )**2 )
        r2[ start_index + window_in_days ] = 1. - ssreg / sstot
        y_hat[(start_index + window_in_days)] = (
            np.exp( np.matmul(a_mse, x_mse) ) - 1
        )[-1]
        if start_index + window_in_days + 1 < y.shape[0] - 1:
            y_hat_2[start_index + window_in_days + 1] = (
                np.exp( np.matmul(a_mse_2, x_mse) ) - 1
            )[-1]

        rmse[start_index + window_in_days] = ( 
            (
                np.sum( ( y_mse - np.matmul( a_mse, x_mse ) )**2 )
            ) / len(y_mse)
        ) **  (1/2)
        
        x_matrix[:, start_index + window_in_days] = x_mse
    funds[column] = pd.DataFrame(
        np.transpose(x_matrix),
        columns=['Level', 'USDBRL', 'PREDI720', 'SPX', 'IBOV'],
        index=fund_df.index.values
    )
    funds_r2[column] = r2
    funds_y_hat[column] = y_hat
    funds_y_hat_2[column] = y_hat_2
    funds_rmse[column] = rmse

    funds_r2.index = product_df.index[1:]
    funds_y_hat.index = product_df.index[1:]
    funds_y_hat_2.index = product_df.index[1:]
    funds_rmse.index = product_df.index[1:]

    results = {}
    for key in ['Level', 'USDBRL', 'PREDI720', 'SPX', 'IBOV']:
        results[key] = pd.DataFrame()
        for column in funds.keys():
            results[key][column] = funds[column][key]
        results[key].index = [pd.Timestamp(x) for x in results[key].index]
    return results, funds_r2, funds_y_hat, funds_y_hat_2, funds_rmse


def regression_3(product_df, fund_df, window_in_days=15, **kwarg):
    w_vector = np.array([-1, -.05, .1, 0.05]).reshape(-1,1)
    a_matrix = product_df.to_numpy()
    a_matrix_shape = a_matrix.shape
    funds = {}
    aux_index = range(fund_df.shape[0]-1)
    funds_rmse = pd.DataFrame(columns=['All'], index=aux_index)
    funds_y_hat = pd.DataFrame(columns=['All'], index=aux_index)
    funds_y_hat_2 = pd.DataFrame(columns=['All'], index=aux_index)
    funds_r2 = pd.DataFrame(columns=['All'], index=aux_index)
    nan_array = np.zeros((a_matrix_shape[0]-1,)) * np.nan
    nan_matrix = np.zeros((a_matrix_shape[1], a_matrix_shape[0])) * np.NaN
    
    test_beta = np.zeros( (a_matrix_shape[0]-1, 1) ) * np.nan
    test_r2 = np.zeros( (a_matrix_shape[0]-1, 1) ) * np.nan

    column = 'All'

    # Selection fund value
    y = fund_df.mean(axis=1)

    # Declare variables
    y_hat = nan_array.copy()
    y_hat_2 = nan_array.copy()
    rmse = nan_array.copy()
    x_matrix = nan_matrix.copy()
    r2 = nan_array.copy()

    # Run regression for moving window
    for start_index in range(a_matrix_shape[0] - window_in_days - 1):
        # Select current section of data
        a_mse = a_matrix[ start_index:(start_index + window_in_days), : ]
        y_mse = y[start_index:(start_index + window_in_days)]

        
        if start_index == y.shape[0] - window_in_days:
            a_mse_2 = (a_mse * np.nan).copy()
        else:
            a_mse_2 = (
                a_matrix[ start_index+1:(start_index + window_in_days+1), : ]
            ).copy()
        
        # Verify data
        if np.any(np.isnan(a_mse)):
            continue
        if np.any(np.isnan(y_mse)):
            continue
        if np.linalg.cond(
            np.matmul(np.transpose(a_mse), a_mse)
        ) > 1/sys.float_info.epsilon:
            continue
        
        # Process
        # x_mse = np.linalg.solve(
        #     np.matmul(a_mse.T, a_mse),
        #     np.matmul(a_mse.T, y_mse)
        # )
        model = sm.OLS( y_mse, a_mse )
        model_fit = model.fit()
        x_mse = model_fit.params
        r2[ start_index + window_in_days ] = model_fit.rsquared

        y_hat[(start_index + window_in_days)] = (
            np.exp( model_fit.predict(a_mse) ) - 1
        )[-1]
        if start_index + window_in_days + 1 < y.shape[0] - 1:
            y_hat_2[start_index + window_in_days + 1] = (
                np.exp( model_fit.predict(a_mse_2) ) - 1
            )[-1]

        rmse[start_index + window_in_days] = ( 
            (
                np.sum( ( y_mse - model_fit.predict(a_mse) )**2 )
            ) / len(y_mse)
        ) **  (1/2)
        
        x_matrix[:, start_index + window_in_days] = x_mse

        test_x = sm.add_constant(
            np.matmul(
                a_mse[:, 1:],
                w_vector
            )
        )
        test_model = sm.OLS( y_mse, test_x )
        test_results = test_model.fit()
        test_beta[start_index + window_in_days] = test_results.params[-1]
        test_r2[start_index + window_in_days] = test_results.rsquared

    funds[column] = pd.DataFrame(
        np.transpose(x_matrix),
        columns=['Level', 'USDBRL', 'PREDI720', 'SPX', 'IBOV'],
        index=fund_df.index.values
    )
    funds_r2[column] = r2
    funds_y_hat[column] = y_hat
    funds_y_hat_2[column] = y_hat_2
    funds_rmse[column] = rmse

    funds_r2.index = product_df.index[1:]
    funds_y_hat.index = product_df.index[1:]
    funds_y_hat_2.index = product_df.index[1:]
    funds_rmse.index = product_df.index[1:]

    results = {}
    for key in ['Level', 'USDBRL', 'PREDI720', 'SPX', 'IBOV']:
        results[key] = pd.DataFrame()
        for column in funds.keys():
            results[key][column] = funds[column][key]
        results[key].index = [pd.Timestamp(x) for x in results[key].index]
    return results, funds_r2, funds_y_hat, funds_y_hat_2, funds_rmse, test_r2, test_beta