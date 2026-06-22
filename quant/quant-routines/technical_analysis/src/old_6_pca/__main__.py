import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
import pickle
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.patches import FancyArrowPatch
from mpl_toolkits.mplot3d import proj3d
import process
import statsmodels.api as sm
import pca_aux

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

product_log_return = product_data[ ['PREDI720 Index', 'IBOV Index', 'SPX Index', 'USDBRL Curncy'] ].copy()
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

window_size = 60
r2_position_report = pd.read_excel(
    '%s/r2_60du.xlsx' % input_path,
    index_col=0
)

a1_matrix = pd.DataFrame(index= results_2[window_size]['PREDI720'].index)
a1_matrix['PREDI720'] = results_2[window_size]['PREDI720']
a1_matrix['IBOV'] = results_2[window_size]['IBOV']
a1_matrix['SPX'] = results_2[window_size]['SPX']
a1_matrix['USDBRL'] = results_2[window_size]['USDBRL']

print('___________')
print(a1_matrix.mean())
print('___________')
pca_1, pca_1_data = pca_aux.test( 
    a1_matrix, 
    show=False 
)

# pca_2, pca_2_data = pca_aux.test( 
#     a1_matrix[[ 'PREDI720', 'USDBRL']], 
#     show=False 
# )


# _, beta_1_21, _ = process.analysis(
#     product_log_return, 
#     master_log_return,
#     a1_matrix,
#     pca_1.components_[0],
#     r2_position_report,
#     debug=False,
#     title='PCA using PRE, IBOV, SPX, USDBRL',
#     window_size=21
# )
_, beta_1_14, _ = process.analysis(
    product_log_return, 
    master_log_return,
    a1_matrix,
    pca_1.components_[0],
    r2_position_report,
    debug=False,
    title='PCA using PRE, IBOV, SPX, USDBRL',
    window_size=14
)
# _, beta_1_7, _ = process.analysis(
#     product_log_return, 
#     master_log_return,
#     a1_matrix,
#     pca_1.components_[0],
#     r2_position_report,
#     debug=False,
#     title='PCA using PRE, IBOV, SPX, USDBRL',
#     window_size=7
# )
# _, beta_2_21, _ = process.analysis(
#     product_log_return, 
#     master_log_return,
#     a1_matrix,
#     pca_1.components_[1],
#     r2_position_report,
#     debug=False,
#     title='PCA using PRE, IBOV, SPX, USDBRL',
#     window_size=21
# )
_, beta_2_14, _ = process.analysis(
    product_log_return, 
    master_log_return,
    a1_matrix,
    pca_1.components_[1],
    r2_position_report,
    debug=False,
    title='PCA using PRE, IBOV, SPX, USDBRL',
    window_size=14
)
# _, beta_2_7, _ = process.analysis(
#     product_log_return, 
#     master_log_return,
#     a1_matrix,
#     pca_1.components_[1],
#     r2_position_report,
#     debug=False,
#     title='PCA using PRE, IBOV, SPX, USDBRL',
#     window_size=7
# )
_, beta_3_14, _ = process.analysis(
    product_log_return, 
    master_log_return,
    a1_matrix,
    pca_1.components_[2],
    r2_position_report,
    debug=False,
    title='PCA using PRE, IBOV, SPX, USDBRL',
    window_size=14
)


# plt.plot(beta_1_03, label='3DU')
# plt.plot(beta_1_05, label='5DU')
plt.plot(beta_1_14, label='PC1')
plt.plot(beta_2_14, label='PC2')
plt.plot(beta_3_14, label='PC3')
plt.legend()
plt.grid()
plt.show()
# quit()
# _, beta_1_2, _ = process.analysis(
#     product_log_return[[ 'PREDI720', 'USDBRL']], 
#     master_log_return,
#     a1_matrix[[ 'PREDI720', 'USDBRL']],
#     pca_2.components_[0],
#     r2_position_report,
#     debug=True,
#     title='PCA using PREDI720, USDBRL',
#     window_size=60,
# )

quit()

# _______________________________________________________________________________________________
# Preprocessing
product_exp_returns_df, fund_exp_returns_df = process.compose_matrixes( 
    product_data, 
    master_data 
)
a_matrix = product_exp_returns_df.to_numpy()
b_matrix = fund_exp_returns_df.sum(axis=1).to_numpy()

# _______________________________________________________________________________________________
# Run pca
normalization = lambda x: (x - x.mean()) / x.std()
normalization_factor = 1
data = pd.DataFrame()
stds = [
    float(a_matrix[:,1].std()),
    float(a_matrix[:,3].std()),
    float(a_matrix[:,2].std()),
    float(a_matrix[:,0].std()),
    float(b_matrix.std()),
]
means = [
    float(a_matrix[:,1].mean()),
    float(a_matrix[:,3].mean()),
    float(a_matrix[:,2].mean()),
    float(a_matrix[:,0].mean()),
    float(b_matrix.mean()),
]
print(stds)
print(means)
data['PREDI720'] = normalization( a_matrix[:,1] ) # 0
data['IBOV'] = normalization( a_matrix[:,3] ) # 1
data['SPX'] = normalization( a_matrix[:,2] ) # 2
data['USDBRL'] = normalization( a_matrix[:,0] ) # 3
# data['Return'] = normalization( b_matrix ) # 4
# data = data.truncate(
#     before=pd.Timestamp('2020-01-01'),
#     # after=pd.Timestamp('2020-01-01'),
# )

data.dropna(inplace=True)

pca = PCA(n_components=4)
pca.fit( data.to_numpy() )
data_pca = pd.DataFrame( 
    pca.transform( data.to_numpy() ),
    index=data.index
)
print(pca.components_)
print(pca.explained_variance_ratio_)
components = list([x.tolist() for x in pca.components_])
for component_i, component in enumerate(components):
    for index in range(len(component)):
        print(components[component_i][index])
        components[component_i][index] *= stds[index]
# _______________________________________________________________________________________________
# Plot

fig = plt.figure(figsize=(15,15))
ax = fig.add_subplot(111, projection='3d')
index_i = 1
index_j = 2
index_k = 3
ax.scatter( 
    data['PREDI720'] * stds[index_i] + means[index_i], 
    data['IBOV'] * stds[index_j] + means[index_j], 
    data['SPX'] * stds[index_k] + means[index_k], 
    marker='o',
    alpha=.05
)
for component_i, _ in enumerate(components):
    a = plt.plot(
        [
            means[index_i], 
            means[index_i] + pca.singular_values_[component_i] * components[component_i][index_i] / 20
        ], 
        [
            means[index_j], 
            means[index_j] + pca.singular_values_[component_i] * components[component_i][index_j] / 20
        ], 
        [
            means[index_k],
            means[index_k] + pca.singular_values_[component_i] * components[component_i][index_k] / 20
        ],
        lw=3,
        color="r"
    )
ax.set_xlabel('SPX')
ax.set_ylabel('USDBRL')
ax.set_zlabel('Return')
plt.savefig('%s/pre_ibov_spx.png' % output_path)
# plt.show()
plt.close()


y = normalization(b_matrix)
A = data_pca.to_numpy()
model = sm.OLS(y,A)
results = model.fit()
y_hat = results.predict(A)
print(results.params)

plt.plot(y, y_hat, '.')
plt.show()


# print(data_pca)
# plt.plot(data_pca)
# plt.show()

# _______________________________________________________________________________________________
# 


quit()

fig = plt.figure(figsize=(15,15))
ax = fig.add_subplot(111, projection='3d')
ax.scatter( 
    data['PREDI720'], 
    data['IBOV'], 
    data['USDBRL'] 
)
for component_i, component in enumerate(pca.components_):
    a = Arrow3D(
        [
            data['PREDI720'].mean(), 
            pca.singular_values_[component_i]*component[0]/20+data['PREDI720'].mean()
        ], 
        [
            data['IBOV'].mean(), 
            pca.singular_values_[component_i]*component[1]/20+data['IBOV'].mean()
        ], 
        [
            data['USDBRL'].mean(), 
            pca.singular_values_[component_i]*component[3]/20+data['USDBRL'].mean()
        ], 
        mutation_scale=10, 
        lw=3,
        arrowstyle="-|>", 
        color="r"
    )
    ax.add_artist(a)

aux_max = [ data['PREDI720'].max(), data['IBOV'].max(), data['SPX'].max() ]
aux_min = [ data['PREDI720'].min(), data['IBOV'].min(), data['SPX'].min() ]
ax.set_xlim( aux_min-2, aux_max+2 )
ax.set_ylim( aux_min-2, aux_max+2 )
ax.set_zlim( aux_min-2, aux_max+2 )
ax.set_xlabel('PREDI720')
ax.set_ylabel('IBOV')
ax.set_zlabel('USDBRL')
plt.savefig('%s/PRE_IBOV_USDBRL.png' % output_path)
# plt.show()
plt.close()
