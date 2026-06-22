from scipy.optimize import minimize
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import statsmodels.api as sm
# _______________________________________________________________________________________________
# Configuration
input_path = '../../output/0_download_data'
input_path_2 = '../../output/4_further_analysis'
# _______________________________________________________________________________________________
# Import data
product_data = pd.read_excel('%s/product_data.xlsx' % input_path, index_col=0)
master_data = pd.read_excel('%s/master_data.xlsx' % input_path, index_col=0)
# product_data = product_data.truncate(
#     before = pd.Timestamp('2020-05-30'),
#     after = pd.Timestamp('2020-07-31'),
# )
# master_data = master_data.truncate(
#     before = pd.Timestamp('2020-05-30'),
#     after = pd.Timestamp('2020-07-31'),
# )

# A matrix
a_matrix = pd.DataFrame()
a_matrix["Ones"]  = product_data['PREDI720 Index'].to_numpy()[1:] * 0 + 1
key = 'PREDI720 Index'
aux = product_data[key].to_numpy()
a_matrix[key] = ( aux[1:] - aux[:-1] ) / 100
for key in [ 
    'USDBRL Curncy', 
    'IBOV Index', 
    'SPX Index'
]:
    aux = product_data[key].to_numpy()
    a_matrix[key] = np.log(aux[1:]) - np.log(aux[:-1])
a_matrix = a_matrix.to_numpy()

# Initial condition
x0 = np.ones((1, a_matrix.shape[1])) 

# B matrix
all_b_matrix = pd.DataFrame()
for column in master_data:
    aux = master_data[column].to_numpy()
    all_b_matrix[column] = np.log(aux[1:]) - np.log(aux[:-1])
b_matrix = all_b_matrix.mean(axis=1).to_numpy()
all_b_matrix = all_b_matrix.to_numpy()

x_test = np.matmul(
    np.linalg.pinv(
        a_matrix 
    ),
    b_matrix
)

# C matrix
window_size = 20
c_matrix_n_rows = len(product_data.index) - window_size - 1
c_matrix = np.zeros( (c_matrix_n_rows, a_matrix.shape[1]) )
for i in range( c_matrix_n_rows ):
    start_i = i
    aux_c = np.matmul(
        np.linalg.pinv(
            a_matrix[ start_i:start_i+window_size, : ] 
        ),
        b_matrix[ start_i:start_i+window_size ]
    )
    c_matrix[i,:] = np.reshape( aux_c, (1, a_matrix.shape[1]) )

# Regression 
imported_r2 = pd.read_excel('%s/r2_20du.xlsx' % input_path_2, index_col=0)
c_matrix_n_rows = len(product_data.index) - window_size - 1
beta = np.zeros( (len(product_data.index), 1) ) * np.nan
r2 = np.zeros( (len(product_data.index), 1) ) * np.nan
w_vector = np.array([-1,-.05,.1,0.05]).reshape(-1,1)
for i in range( c_matrix_n_rows ):
    y_mse = b_matrix[ i:i+window_size ].reshape(-1,1)
    x = np.matmul(
        a_matrix[ i:i+window_size, 1: ],
        w_vector
    )

    model = sm.OLS(y_mse,x)
    results = model.fit()

    beta[i] = results.params

    r2[i] = results.rsquared

plt.plot(master_data.index[0:len(product_data.index)], r2, 'k', label='r2')
plt.plot(imported_r2, 'r', label='r2 (fund position analysis)')
# plt.plot(master_data.index[0:len(product_data.index)], beta, 'b', label='beta')
plt.legend()
plt.grid()
plt.show()

print(imported_r2)
quit()
# _______________________________________________________________________________________________
# Process

def cost_function(x):
    x1 = np.matmul( x, c_matrix.transpose() ).reshape(1,-1)
    x2 = np.matmul( c_matrix, x ).reshape(-1,1)
    x3 = np.matmul( x1, x2 ).item()
    return -x3

def cost_function_deriv(x):
    y = 2 * np.matmul(
        np.matmul( c_matrix.transpose(), c_matrix ),
        x
    )
    y = np.asarray( y )
    return -y

def eq(x):
    y = np.matmul( x.transpose(), x ) - 1
    y = y.flatten()[0]
    return y*2

eq_constraint = {
    'type': 'eq',
    'fun': eq,
    'jac': lambda x: 2 * x
}

res = minimize(
    cost_function,
    x0,
    jac=cost_function_deriv,
    method='SLSQP',
    constraints=[ eq_constraint ],
    options={
        'maxiter': 50000
    }
)

print( res )
alignment = np.matmul(
    a_matrix,
    -res.x
)
a = (
    (
        (alignment > 0) & (b_matrix > 0)
    ) |
    (
        (alignment < 0) & (b_matrix < 0)
    )
)

print( np.unique(a, return_counts=True) )

plt.plot( b_matrix, alignment, 'x' )
plt.xlabel('b')
plt.ylabel('alignment')
plt.grid()
plt.show()

plt.plot( b_matrix )
plt.plot( -alignment )
plt.show()

