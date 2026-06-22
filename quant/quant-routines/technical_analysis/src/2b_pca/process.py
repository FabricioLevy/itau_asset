import numpy as np
from sklearn.decomposition import PCA
import pandas as pd
import statsmodels.api as sm

def rolling_pca(x, x_bar, x_std, window_size):
    x_np = x.to_numpy()
    x_bar_np = x_bar.to_numpy()
    x_std_np = x_std.to_numpy()

    # Declare variables
    components = {}
    for i in range(len(x.columns)):
        components[i] = np.zeros(x_np.shape) * np.nan
    explained_variance = np.zeros(x_np.shape) * np.nan

    # Loop
    for start_index in range( x_np.shape[0]-window_size+1 ):
        x_bar_selection = x_bar_np[ start_index+window_size-1, : ]
        x_std_selection = x_std_np[ start_index+window_size-1, : ]
        x_selection = x_np[ start_index:start_index+window_size, : ]
        x_normalized = (x_selection - x_bar_selection) / x_std_selection
        if (
            (np.isnan(x_normalized).any()) |
            (np.isinf(x_normalized).any())
        ):
            continue

        pca = PCA( n_components=len(x.columns) )
        pca.fit( x_normalized )

        # Store results
        for i in range(len(x.columns)):
            components[i][start_index+window_size-1, :] = - pca.components_[i] / np.sign(pca.components_[i][0])
        explained_variance[start_index+window_size-1, :] = pca.explained_variance_
    
    for i in range(len(x.columns)):
        components[i] = pd.DataFrame(
            components[i], 
            columns=x.columns, 
            index=x.index
        )
    explained_variance = pd.DataFrame(
        explained_variance, 
        columns=x.columns, 
        index=x.index
    )
    return components, explained_variance

def analysis(
    product_log_return, 
    master_log_return,
    pca_component,
    x_mean,
    x_std,
    debug=False,
    window_size=20,
):
    # [ 1, A.diag(sigma).w ][x0; beta]  = b - A.x_bar = b_star
    # a_star.[x0; beta] = b_star
    a_total = product_log_return.to_numpy()
    b_total = master_log_return.to_numpy().reshape(-1,1)

    # Declare variables
    beta_0 = np.zeros(a_total.shape[0]) * np.nan
    beta_1 = np.zeros(a_total.shape[0]) * np.nan
    r2 = np.zeros(a_total.shape[0]) * np.nan
    pca = np.zeros(a_total.shape) * np.nan

    # Loop
    for start_index in range(a_total.shape[0] - window_size):
        if start_index + window_size > x_mean.shape[0]:
            continue
        x_bar_current = x_mean[start_index + window_size-1,:].reshape(-1,1)
        x_std_current = np.diag(x_std[start_index + window_size-1,:])
        pca_current = np.matmul( 
            x_std_current, 
            pca_component[start_index + window_size-1,:] 
        )
        if np.isnan(pca_current).any():
            continue
        pca_current = - pca_current / pca_current[0]
        pca_current = pca_current / np.sqrt((np.power( pca_current, 2 )).sum())

        a_current = a_total[start_index: start_index + window_size, :].copy()
        b_current = b_total[start_index: start_index + window_size].copy()
        
        a_star = sm.add_constant(
            np.matmul(
                a_current,
                pca_current
            ).reshape(-1,1)
        ).copy()
        b_star = (
            b_current - 
            np.matmul( 
                a_current,
                x_bar_current
            )
        ).copy()
        model = sm.OLS( b_star, a_star )
        results = model.fit()
        b_hat = (
            results.predict( a_star ).reshape(-1,1) +
            np.matmul( 
                a_current,
                x_bar_current
            )
        )
        ss_total = (np.power( b_current - b_current.mean(), 2 )).sum()
        ss_res = (np.power( b_current - b_hat.reshape(-1,1), 2 )).sum()

        # Store results
        pca[start_index + window_size-1, :] = pca_current
        beta_0[start_index + window_size - 1] = results.params[0]
        beta_1[start_index + window_size - 1] = results.params[1]
        r2[start_index + window_size - 1] = 1 - (ss_res / ss_total)

    beta_0 = pd.DataFrame(beta_0, index=product_log_return.index)
    beta_1 = pd.DataFrame(beta_1, index=product_log_return.index)
    r2 = pd.DataFrame(r2, index=product_log_return.index)

    return beta_0, beta_1, r2, pca

def analysis_2(
    product_log_return, 
    master_log_return,
    pca_component,
    x_mean,
    x_std,
    debug=False,
    window_size=20,
):
    # [ 1, A.diag(sigma).w ][x0; beta]  = b - A.x_bar = b_star
    # a_star.[x0; beta] = b_star
    a_total = product_log_return.to_numpy()
    b_total = master_log_return.to_numpy().reshape(-1,1)

    # Declare variables
    beta_0 = np.zeros(a_total.shape[0]) * np.nan
    beta_1 = np.zeros(a_total.shape[0]) * np.nan
    beta_2 = np.zeros(a_total.shape[0]) * np.nan
    r2 = np.zeros(a_total.shape[0]) * np.nan
    pca = np.zeros((a_total.shape[0], a_total.shape[1] -1)) * np.nan

    # Loop
    for start_index in range(a_total.shape[0] - window_size):
        if start_index + window_size > x_mean.shape[0]:
            continue
        x_bar_current = x_mean[start_index + window_size-1,:].reshape(-1,1)
        x_std_current = np.diag(x_std[start_index + window_size-1,:])
        pca_current = np.matmul( 
            x_std_current, 
            pca_component[start_index + window_size-1,:] 
        )
        
        if np.isnan(pca_current).any():
            continue
        # pca_current = pca_current / pca_current[0]
        pca_current = pca_current / np.sqrt((np.power( pca_current, 2 )).sum())

        a_current = a_total[start_index: start_index + window_size, :].copy()
        b_current = b_total[start_index: start_index + window_size].copy()
        

        a_star = sm.add_constant(
            np.concatenate(
                (
                    a_current[:, 0].reshape(-1,1),
                    np.matmul(
                        a_current[:, 1:],
                        pca_current
                    ).reshape(-1,1)
                ),
                axis=1
            )
        ).copy()
        b_star = (
            b_current - 
            np.matmul( 
                a_current[:, 1:],
                x_bar_current
            )
        ).copy()
        model = sm.OLS( b_star, a_star )
        results = model.fit()
        b_hat = (
            results.predict( a_star ).reshape(-1,1) +
            np.matmul( 
                a_current[:, 1:],
                x_bar_current
            )
        )
        ss_total = (np.power( b_current - b_current.mean(), 2 )).sum()
        ss_res = (np.power( b_current - b_hat.reshape(-1,1), 2 )).sum()

        # Store results
        pca[start_index + window_size-1, :] = pca_current
        beta_0[start_index + window_size - 1] = results.params[0]
        beta_1[start_index + window_size - 1] = results.params[1]
        beta_2[start_index + window_size - 1] = results.params[2]
        r2[start_index + window_size - 1] = 1 - (ss_res / ss_total)

    beta_0 = pd.DataFrame(beta_0, index=product_log_return.index)
    beta_1 = pd.DataFrame(beta_1, index=product_log_return.index)
    beta_2 = pd.DataFrame(beta_2, index=product_log_return.index)
    r2 = pd.DataFrame(r2, index=product_log_return.index)

    return beta_0, beta_1, beta_2, r2, pca

