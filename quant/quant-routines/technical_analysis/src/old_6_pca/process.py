import numpy as np
from sklearn.linear_model import Ridge, Lasso, LinearRegression
from sklearn.metrics import r2_score
import sys
import pandas as pd
import statsmodels.api as sm
import matplotlib.pyplot as plt

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
    return a_matrix[['USDBRL', 'PREDI720', 'SPX', 'IBOV']], y_matrix

def analysis(
    product_log_return, 
    master_log_return,
    a1_matrix,
    pca_component,
    r2_,
    debug=False,
    title='',
    window_size=20,
):
    # [ 1, A.diag(sigma).w ][x0; beta]  = b - A.x_bar = b_star

    # a_star.[x0; beta] = b_star


    a_total = product_log_return.to_numpy()
    b_total = master_log_return.to_numpy().reshape(-1,1)
    x_bar = a1_matrix.mean().to_numpy().reshape(-1,1)
    x_std = np.diag(a1_matrix.std())
    beta_0 = np.zeros(a_total.shape[0]) * np.nan
    beta_1 = np.zeros(a_total.shape[0]) * np.nan
    r2 = np.zeros(a_total.shape[0]) * np.nan
    pca = np.matmul( x_std, pca_component )
    pca = -pca / pca[0]
    for start_index in range(a_total.shape[0] - window_size):
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
        # aux2 = results.predict( a_star ).copy()
        # plt.plot(aux2, label='predict')
        # plt.plot(b_star, label='real')
        # plt.legend()
        # plt.show()

        beta_0[start_index + window_size - 1] = results.params[0]
        beta_1[start_index + window_size - 1] = results.params[1]
        r2[start_index + window_size - 1] = results.rsquared
    beta_0 = pd.DataFrame(beta_0, index=product_log_return.index)
    beta_1 = pd.DataFrame(beta_1, index=product_log_return.index)
    r2 = pd.DataFrame(r2, index=product_log_return.index)
    if debug==True:
        print(pca)
        plt.plot(beta_1)
        plt.grid()
        plt.title(title)
        plt.show()

        plt.plot(r2)
        plt.plot(r2_)
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
        plt.legend()
        plt.show()

        plt.plot( aux, b_total, 'x' )
        plt.plot([-0.03,0.03], [-0.03,0.03])
        plt.show()

        plt.plot( beta_0 - beta_0.mean() + beta_1.mean(), label='Beta 0' )
        plt.plot( beta_1, label='Beta 1' )
        plt.show()

    return beta_0, beta_1, r2
