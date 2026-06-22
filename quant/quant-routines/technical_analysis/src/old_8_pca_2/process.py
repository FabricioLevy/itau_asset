import numpy as np
from sklearn.linear_model import Ridge, Lasso, LinearRegression
from sklearn.metrics import r2_score
import sys
import pandas as pd
import statsmodels.api as sm
import matplotlib.pyplot as plt

def analysis(
    product_log_return, 
    master_log_return,
    pca_component,
    a_mean,
    a_std,
    debug=False,
    title='',
    window_size=20,
):
    # [ 1, A.diag(sigma).w ][x0; beta]  = b - A.x_bar = b_star
    # a_star.[x0; beta] = b_star

    a_total = product_log_return.to_numpy()
    b_total = master_log_return.to_numpy().reshape(-1,1)

    beta_0 = np.zeros(a_total.shape[0]) * np.nan
    beta_1 = np.zeros(a_total.shape[0]) * np.nan
    r2 = np.zeros(a_total.shape[0]) * np.nan

    res_total = np.zeros(a_total.shape[0]) * np.nan
    res_total_star = np.zeros(a_total.shape[0]) * np.nan
    r2_bar = np.zeros(a_total.shape[0]) * np.nan
    r2_star = np.zeros(a_total.shape[0]) * np.nan
    ax_bar = np.zeros(a_total.shape[0]) * np.nan
    
    pca_hold = None
    for start_index in range(a_total.shape[0] - window_size):
        if start_index + window_size > a_mean.shape[0]:
            continue
        x_bar = a_mean[start_index + window_size-1,:].reshape(-1,1)
        x_std = np.diag(a_std[start_index + window_size-1,:])
        # pca = np.matmul( 
        #     x_std, 
        #     pca_component[start_index + window_size-1,:] 
        # )
        pca = pca_component[start_index + window_size-1,:] 
        
        if np.isnan(pca).any():
            continue
        pca = - pca / np.sign(pca[0])
        pca = pca / np.sqrt((np.power( pca, 2 )).sum())
        pca_hold = pca

        a_current = a_total[start_index: start_index + window_size, :].copy()

        b_current = b_total[start_index: start_index + window_size].copy()
        a_star = sm.add_constant(
            np.matmul(
                a_current,
                pca
            ).reshape(-1,1)
        ).copy()
        b_star = (
            b_current - 
            np.matmul( 
                a_current,
                x_bar
            )
        ).copy()
        model = sm.OLS( b_star, a_star )
        results = model.fit()
        # print(results.params)
        b_hat = (
            results.predict( a_star ).reshape(-1,1) +
            np.matmul( 
                a_current,
                x_bar
            )
        )
        # plt.plot(aux2, label='predict')
        # plt.plot(b_star, label='real')
        # plt.legend()
        # plt.show()

        beta_0[start_index + window_size - 1] = results.params[0]
        beta_1[start_index + window_size - 1] = results.params[1]
        
        ax_bar[start_index + window_size - 1] = np.matmul( 
            a_current,
            x_bar
        )[-1]
        ss_total_star = (np.power( b_star - b_star.mean(), 2 )).sum()
        ss_res_star = ( np.power( 
            b_star - results.predict( a_star ).reshape(-1,1), 
            2 
        )).sum()

        ss_total = (
            np.power( b_current - b_current.mean(), 2 )
        ).sum()


        ss_res = (
            np.power( b_current - b_hat.reshape(-1,1), 2 )
        ).sum()

        res_total[start_index + window_size - 1] = ss_total
        res_total_star[start_index + window_size - 1] = ss_total_star
        r2_bar[start_index + window_size - 1] = 1 - (( np.power(b_star, 2 ) ).sum()/ ss_total)
        # print( 1 - (ss_res / ss_total), ss_res, ss_total )
        r2[start_index + window_size - 1] = 1 - (ss_res / ss_total)
        r2_star[start_index + window_size - 1] = 1 - ( ss_res_star/ ss_total_star)

    beta_0 = pd.DataFrame(beta_0, index=product_log_return.index)
    beta_1 = pd.DataFrame(beta_1, index=product_log_return.index)
    r2 = pd.DataFrame(r2, index=product_log_return.index)
    print(pca_hold)
    # plt.plot(res_total, label='res tot')
    # plt.plot(res_total_star, label='res tot star')
    # plt.plot(r2_bar, label='r2')
    # plt.legend()
    # plt.show()

    # ax_bar = pd.DataFrame(ax_bar, index=b_total.index)
    # plt.plot(ax_bar, label='axbar')
    # plt.plot(b_total, label='b')
    # plt.plot(r2.values, label='r2')
    # plt.plot(r2_star, label='r2 star')
    # plt.legend()
    # plt.show()

    if debug==True:
        
        plt.plot(beta_1, label='Beta 1')
        plt.plot(r2, '--', label='r2')
        plt.title(pca_hold)

        plt.legend()
        plt.grid()
        plt.show()

        aux = (
            np.multiply(
                np.matmul(
                    a_total,
                    pca
                ).reshape(-1,1),
                beta_1
            ) + 
            np.matmul(
                a_total,
                x_bar
            ) +
            beta_0
        )

        plt.plot( aux.to_numpy(), label='predict' )
        plt.plot( b_total, label='real' )
        plt.title('b')
        plt.legend()
        plt.show()

        # plt.plot( aux, b_total, 'x' )
        # plt.plot([-0.03,0.03], [-0.03,0.03])
        # plt.xlabel('predict')
        # plt.ylabel('real')
        # plt.show()
        # plt.plot( beta_0 - beta_0.mean() + beta_1.mean(), label='Beta 0' )
        # plt.plot( beta_1, label='Beta 1' )
        # plt.show()

    return beta_0, beta_1, r2
