import numpy as np
import pandas as pd
import sys
import matplotlib.pyplot as plt

def regression(asset_data, product_data, window_in_days=15):
    usdbrl = product_data['USDBRL Curncy'].to_numpy()
    predi720 = product_data['PREDI720 Index'].to_numpy() / 100
    spx = product_data['SPX Index'].to_numpy()
    ibov = product_data['IBOV Index'].to_numpy()

    # print(asset_data['Kinea'])
    asset_data = asset_data.replace(0,np.nan)
    # print(asset_data['Kinea'])

    # quit()
    a_matrix = np.zeros((ibov.size-1, 5))
    # A.x = y    ->    x = pinv(A'.A) . (A'.y)
    # A = [{1}, {USDBRL}, {SPX}, {IBOV}]
    # x = {regression coef}
    # y = {fund return}
    a_matrix[:, 0] = int(1)
    a_matrix[:, 1] = np.subtract(np.log(usdbrl[1:usdbrl.size]), np.log(usdbrl[0:usdbrl.size-1]))
    a_matrix[:, 2] = np.subtract(predi720[1:predi720.size], predi720[0:predi720.size-1])
    a_matrix[:, 3] = np.subtract(np.log(spx[1:spx.size]), np.log(spx[0:spx.size-1]))
    a_matrix[:, 4] = np.subtract(np.log(ibov[1:ibov.size]), np.log(ibov[0:ibov.size-1]))
    a_matrix_shape = a_matrix.shape
    funds_r2 = pd.DataFrame()
    funds = {}
    funds_rmse = pd.DataFrame()
    funds_y_hat = pd.DataFrame()
    funds_y_hat_2 = pd.DataFrame()
    for column in asset_data.columns:        
        # print(column)
        y = asset_data[column].values
        y_matrix = np.subtract(np.log(y[1:y.size]), np.log(y[0:y.size-1]))
        y_hat = np.zeros((ibov.size-1,)) * np.nan
        y_hat_2 = np.zeros((ibov.size-1,)) * np.nan
        rmse = np.zeros((ibov.size-1,)) * np.nan
        x_matrix = np.zeros((a_matrix_shape[1], a_matrix_shape[0])) * np.NaN
        r2 = np.zeros((ibov.size-1,)) * np.nan
        for start_index in range(y_matrix.size - window_in_days+1):
            
            a_mse = a_matrix[start_index:(start_index + window_in_days), :]
            if start_index == y_matrix.size - window_in_days:
                a_mse_2 = (a_mse * np.nan).copy()
            else:
                a_mse_2 = (
                    a_matrix[ start_index+1:(start_index + window_in_days+1), : ]
                ).copy()

            y_mse = y_matrix[start_index:(start_index + window_in_days)]
            
            if np.any(np.isnan(a_mse)):
                continue
            if np.any(np.isnan(y_mse)):
                continue
            if np.linalg.cond(np.matmul(np.transpose(a_mse), a_mse)) > 1/sys.float_info.epsilon:
                continue
                
            x_mse = np.linalg.solve(
                np.matmul(a_mse.T, a_mse),
                np.matmul(a_mse.T, y_mse)
            )

            y_bar = y_mse.mean()
            sstot = np.sum( ( y_mse - y_bar ) ** 2 )
            ssreg = np.sum( ( y_mse - np.matmul( a_mse, x_mse ) )**2 )
            current_r2 = 1. - ssreg / sstot
            r2[ start_index + window_in_days-1] = current_r2

            y_hat[(start_index + window_in_days - 1)] = (
                np.exp( np.matmul(a_mse, x_mse) ) - 1
            )[-1]
            if start_index < y_matrix.size - window_in_days :
                y_hat_2[start_index + window_in_days ] = (
                    np.exp( np.matmul(a_mse_2, x_mse) ) - 1
                )[-1]

            rmse[start_index + window_in_days - 1] = ( 
                (
                    np.sum( ( y_mse - np.matmul( a_mse, x_mse ) )**2 )
                ) / len(y_mse)
            ) **  (1/2)
            
            x_matrix[:, start_index + window_in_days - 1] = x_mse
        funds_r2 = pd.concat( 
            [
                funds_r2, 
                pd.DataFrame(r2, columns=[column], index=asset_data.index.values[1:])
            ], 
            axis=1 
        )
        funds[column] = pd.DataFrame(
            np.transpose(x_matrix),
            columns=['Level', 'USDBRL', 'PREDI720', 'SPX', 'IBOV'],
            index=asset_data.index.values[1:]
        )
        funds_y_hat = pd.concat(
            [
                funds_y_hat,
                pd.DataFrame( 
                    y_hat, 
                    columns=[column],
                    index=asset_data.index.values[1:]
                )
            ],
            axis=1
        )
        funds_y_hat_2 = pd.concat(
            [
                funds_y_hat_2,
                pd.DataFrame( 
                    y_hat_2, 
                    columns=[column],
                    index=asset_data.index.values[1:]
                )
            ],
            axis=1
        )
        funds_rmse = pd.concat(
            [
                funds_rmse,
                pd.DataFrame( 
                    rmse, 
                    columns=[column],
                    index=asset_data.index.values[1:]
                )
            ],
            axis=1
        )
        # quit()
    results = {}
    for key in ['Level', 'USDBRL', 'PREDI720', 'SPX', 'IBOV']:
        results[key] = pd.DataFrame()
        for column in funds.keys():
            results[key] = pd.concat( 
                [ 
                    results[key],
                    funds[column][key].rename(column) 
                ], 
                axis=1 
            )
        results[key].index = [pd.Timestamp(x) for x in results[key].index]
    return results, funds_r2, funds_y_hat, funds_y_hat_2, funds_rmse

def calculate_regression_mean(regression_result):
    mean_result = pd.DataFrame()
    for key in regression_result:
        mean_result = pd.concat(
            [
                mean_result,
                regression_result[key].mean(axis=1).rename(key)
            ],
            axis=1
        )
    return mean_result

def get_additional_info(compiled_result):
    # print(compiled_result)
    compiled_result = compiled_result.dropna()    
    info = pd.DataFrame()
    # info.loc['Same sign', 'Fitted'] = (
    #     ( 
    #         ( compiled_result['Return (D-2)'] > 0 ) & 
    #         ( compiled_result['Fitted return (D-2)'] > 0 )
    #     ).value_counts().loc[True] + ( 
    #         ( compiled_result['Return (D-2)'] < 0 ) & 
    #         ( compiled_result['Fitted return (D-2)'] < 0 )
    #     ).value_counts().loc[True]
    # ) / len(compiled_result['Return (D-2)'].index)
    aux_gt = ( 
        ( compiled_result['Return (D-2)'] > 0 ) & 
        ( compiled_result['Projected (D-3)'] > 0 )
    ).value_counts()
    aux2_gt = aux_gt.loc[True] if True in aux_gt else 0
    aux_lt = ( 
        ( compiled_result['Return (D-2)'] < 0 ) & 
        ( compiled_result['Projected (D-3)'] < 0 )
    ).value_counts()
    aux2_lt = aux_lt.loc[True] if True in aux_lt else 0
    info.loc['Same sign', 'Est.'] = (
        aux2_gt + aux2_lt
    ) / len(compiled_result['Return (D-2)'].index)
    # info.loc['Cross corr', 'Fitted'] = compiled_result[['Return (D-2)', 'Fitted return (D-2)']].corr().iloc[-1].iloc[0]
    info.loc['Cross corr', 'Est.'] = compiled_result[['Return (D-2)', 'Projected (D-3)']].corr().iloc[-1].iloc[0]
    
    # a1 = compiled_result['Fitted return (D-2)'].to_numpy().reshape((-1,1))
    a2 = compiled_result['Projected (D-3)'].to_numpy().reshape((-1,1))
    y = compiled_result['Return (D-2)'].to_numpy().reshape((-1,1))
    # info.loc['Beta', 'Fitted'] = np.linalg.solve(
    #     np.matmul( a1.T, a1 ),
    #     np.matmul( a1.T, y )
    # )[0][0]
    info.loc['Beta', 'Est.'] = np.linalg.solve(
        np.matmul( a2.T, a2 ),
        np.matmul( a2.T, y )
    )[0][0]
    # print(info)
    # quit()
    return info