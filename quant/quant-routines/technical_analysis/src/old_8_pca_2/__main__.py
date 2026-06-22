import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
import pickle
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.patches import FancyArrowPatch
from mpl_toolkits.mplot3d import proj3d
import statsmodels.api as sm
from sklearn.decomposition import PCA
import process

class Arrow3D(FancyArrowPatch):
    def __init__(self, xs, ys, zs, *args, **kwargs):
        FancyArrowPatch.__init__(self, (0,0), (0,0), *args, **kwargs)
        self._verts3d = xs, ys, zs

    def draw(self, renderer):
        xs3d, ys3d, zs3d = self._verts3d
        xs, ys, zs = proj3d.proj_transform(xs3d, ys3d, zs3d, renderer.M)
        self.set_positions((xs[0],ys[0]),(xs[1],ys[1]))
        FancyArrowPatch.draw(self, renderer)

# _______________________________________________________________________________________________
# Configuration
input_path = '../../output/4_further_analysis'
output_path = '../../output/6_pca'
input_path_2 = '../../output/0_download_data'

# _______________________________________________________________________________________________
# Create output path
for folder in ['../../output', output_path]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# _______________________________________________________________________________________________
# Load data
master_data = pd.read_excel('%s/master_data.xlsx' % input_path_2, index_col=0)
product_data = pd.read_excel('%s/product_data.xlsx' % input_path_2, index_col=0)

master_log_return = np.log( master_data.to_numpy() )
master_log_return = master_log_return[1:, :] - master_log_return[:-1, :]
master_log_return = pd.DataFrame( master_log_return, index=master_data.index[1:] )
master_log_return = master_log_return.mean(axis=1)

master_rolling_mean = master_log_return.rolling(window=126).mean()
master_rolling_std = master_log_return.rolling(window=126).std()
product_rolling_mean = product_data.rolling(window=126).mean()
product_rolling_std = product_data.rolling(window=126).std()

product_selector = ['PREDI720 Index', 'IBOV Index', 'SPX Index', 'USDBRL Curncy']
product_log_return = product_data[ product_selector ].copy()
product_log_return['IBOV Index'] = np.log( product_log_return['IBOV Index'].to_numpy() )
product_log_return['SPX Index'] = np.log( product_log_return['SPX Index'].to_numpy() )
product_log_return['USDBRL Curncy'] = np.log( product_log_return['USDBRL Curncy'].to_numpy() )
product_log_return['PREDI720 Index'] = product_log_return['PREDI720 Index'] / 100
product_log_return = product_log_return.to_numpy()
product_log_return = product_log_return[1:, :] - product_log_return[:-1, :]
product_log_return = pd.DataFrame( 
    product_log_return, 
    index=product_data.index[1:],
    columns=['PREDI720', 'IBOV', 'SPX', 'USDBRL']
)

pickle_file = open('%s/results_1.pkl' % input_path, "rb")
results_1 = pickle.load(pickle_file)
pickle_file.close()

pickle_file = open('%s/results_2.pkl' % input_path, "rb")
results_2 = pickle.load(pickle_file)
pickle_file.close()

window_size = 15
r2_position_report = pd.read_excel(
    '%s/r2_60du.xlsx' % input_path,
    index_col=0
)

a1_matrix = pd.DataFrame(index= results_2[window_size]['PREDI720'].index)
a1_matrix['PREDI720'] = results_2[window_size]['PREDI720']
a1_matrix['IBOV'] = results_2[window_size]['IBOV']
a1_matrix['SPX'] = results_2[window_size]['SPX']
a1_matrix['USDBRL'] = results_2[window_size]['USDBRL']
# a1_matrix.dropna(inplace=True)


window_size = 252 * 5
a_matrix_mean = a1_matrix.rolling(window=window_size).mean()
a_matrix_std = a1_matrix.rolling(window=window_size).std()
a_matrix = a1_matrix.to_numpy()
pc_components = {
    0 : np.zeros(a_matrix.shape) * np.nan,
    1 : np.zeros(a_matrix.shape) * np.nan,
    2 : np.zeros(a_matrix.shape) * np.nan,
}
a_mean = np.zeros(a_matrix.shape) * np.nan
a_std = np.zeros(a_matrix.shape) * np.nan

for start_index in range( a_matrix.shape[0]-window_size+1 ):
    a_sub_matrix = a_matrix[ start_index:start_index+window_size, : ]

    a_mean[start_index+window_size-1, :] = a_matrix_mean.iloc[start_index+window_size-1].to_numpy()
    a_std[start_index+window_size-1, :] = a_matrix_std.iloc[start_index+window_size-1].to_numpy()

    a_sub_matrix_2 = (
        a_sub_matrix - a_mean[start_index+window_size-1, :]
    ) #/ a_std[start_index+window_size-1, :]
    if np.isnan(a_sub_matrix).any():
        continue
    pca = PCA( n_components=len(a1_matrix.columns) )
    pca.fit( a_sub_matrix_2 )
    for component_i in range(3):
        # pc_components[component_i][start_index,:] = -(
        #     pca.components_[component_i]
        # ) / pca.components_[component_i][0]
        pc_components[component_i][start_index+window_size-1,:] = (
            pca.components_[component_i] * np.sign( pca.components_[component_i][0] )
        )

# pc_components[0] = pd.DataFrame( pc_components[0], columns=['pre', 'ibov', 'spx', 'usd'], index=a1_matrix.index)
# pc_components[1] = pd.DataFrame( pc_components[1], columns=['pre', 'ibov', 'spx', 'usd'], index=a1_matrix.index)
# pc_components[2] = pd.DataFrame( pc_components[2], columns=['pre', 'ibov', 'spx', 'usd'], index=a1_matrix.index)

# a_mean = pd.DataFrame( a_mean, index=a1_matrix.index, columns=['pre', 'ibov', 'spx', 'usd'])
# a_std = pd.DataFrame( a_std, index=a1_matrix.index, columns=['pre', 'ibov', 'spx', 'usd'])

# a_mean.plot()
# plt.show()

# aux.plot()
# plt.show()

# a1_matrix.plot()
# plt.show()
_, beta_1, r2_1 = process.analysis(
    product_log_return, 
    master_log_return,
    pc_components[0],
    a_mean,
    a_std,
    debug=False,
    window_size=15,
)
_, beta_2, r2_2 = process.analysis(
    product_log_return, 
    master_log_return,
    pc_components[1],
    a_mean,
    a_std,
    debug=False,
    window_size=15,
)

plt.plot(r2_1, '--', label='R2 PC 1', linewidth=1)
plt.plot(r2_2, '--', label='R2 PC 2', linewidth=1)
plt.plot(beta_1, label='Beta PC 1')
plt.plot(beta_2, label='Beta PC 2')
plt.legend()
plt.grid()
plt.show()