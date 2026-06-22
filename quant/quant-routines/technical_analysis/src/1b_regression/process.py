import numpy as np
import pandas as pd
import sys
import statsmodels.api as sm
from statsmodels.tools.eval_measures import rmse

def get_returns(master_data, fic_data, product_data):
    master_returns = master_data.pct_change()
    fic_returns = fic_data.pct_change()
    product_returns = product_data.pct_change()    
    product_returns['PREDI360 Index'] = product_data['PREDI360 Index'].diff()
    product_returns['PREDI720 Index'] = product_data['PREDI720 Index'].diff()
    return master_returns, fic_returns, product_returns

def get_log_returns(data):    
    data = data.replace(0,np.nan)    
    log_returns = np.log(data) - np.log(data.shift(1))
    for key in log_returns:
        if (('PREDI360' in key) or ('PREDI720' in key)):
            log_returns[key] = ( data[key] - data[key].shift(1) ) / 100
    log_returns.drop(log_returns.index[0], inplace=True)    
    return log_returns

def regression(a_full_matrix, b_full_matrix, window_in_days=15):
    # Convert from pandas to numpy
    a_np = sm.add_constant( 
        a_full_matrix.to_numpy()
    )
    b_np = b_full_matrix.to_numpy()

    # Declare variables
    regression = {}
    regression['rmse'] = np.zeros(b_np.shape) * np.nan
    regression['r2'] = np.zeros(b_np.shape) * np.nan
    regression['b_fit'] = np.zeros(b_np.shape) * np.nan
    regression['b_pred'] = np.zeros(b_np.shape) * np.nan
    regression['x'] = {}
    for i in range(a_np.shape[1]):
        regression['x'][i] = np.zeros(b_np.shape) * np.nan

    for start_index in range(b_np.shape[0] - window_in_days + 1):
        print(start_index, b_np.shape[0] - window_in_days,end='\r')
        # Select 'a' data
        a = a_np[start_index:(start_index + window_in_days), :] 
        
        if start_index == b_np.shape[0] - window_in_days:
            a2 = (a * np.nan).copy()
        else:
            a2 = (
                a_np[ (start_index+1):(start_index + window_in_days+1), : ]
            ).copy()

        # Validate 'a' matrix condition value
        if np.linalg.cond(np.matmul(np.transpose(a), a)) > 1/sys.float_info.epsilon:
            continue

        for column_i, column in enumerate(b_full_matrix.columns):
            # Select 'b' data
            b = b_np[start_index:(start_index + window_in_days), column_i]
            
            # Fit
            model = sm.OLS( b, a )
            results = model.fit()
            b_fitted = results.predict( a )
            
            # Store results
            regression['rmse'][(start_index + window_in_days - 1), column_i] = (
                rmse(b, b_fitted)
            )
            regression['r2'][ start_index + window_in_days-1, column_i ] = results.rsquared
            regression['b_fit'][(start_index + window_in_days - 1), column_i] = (
                np.exp( b_fitted ) - 1
            )[-1]
            if start_index < b_np.shape[0] - window_in_days :
                regression['b_pred'][(start_index + window_in_days), column_i] = (
                    np.exp( results.predict( a2 ) ) - 1
                )[-1]

            for i in range(a_np.shape[1]):
                regression['x'][i][ 
                    start_index + window_in_days - 1, column_i 
                ] = results.params[i]
    # Convert results from numpy to pandas
    regression['rmse'] = pd.DataFrame( 
        regression['rmse'],
        columns=b_full_matrix.columns,
        index=b_full_matrix.index
    )
    regression['r2'] = pd.DataFrame(
        regression['r2'],
        columns=b_full_matrix.columns,
        index=b_full_matrix.index
    ) 
    regression['b_fit'] = pd.DataFrame(
        regression['b_fit'],
        columns=b_full_matrix.columns,
        index=b_full_matrix.index
    )
    regression['b_pred'] = pd.DataFrame(
        regression['b_pred'],
        columns=b_full_matrix.columns,
        index=b_full_matrix.index
    )
    for i in range(a_np.shape[1]):
        regression['x'][i] = pd.DataFrame(
            regression['x'][i],
            columns=b_full_matrix.columns,
            index=b_full_matrix.index
        ) 
    return regression
            
