import pandas as pd
from datetime import date
import os
import matplotlib.pyplot as plt
import QuantLib as ql
import shutil
import numpy as np
import pickle as pkl
import process
import math

calendar = ql.Brazil()
# _______________________________________________________________________________________________
# Configuration
input_path = '../../output/0_download_data'
input_path_2 = '../../output/1b_regression'
output_path = '../../output/2b_pca'

# _______________________________________________________________________________________________
# Create output path
for folder in ['../../output', output_path]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# _______________________________________________________________________________________________
# Load data
with open("%s/regression.pkl" % input_path_2, "rb") as f:
    regression = pkl.load(f)
product_log_return = pd.read_excel(
    '%s/product_log_return.xlsx' % input_path_2,
    index_col=0
)
asset_log_return = pd.read_excel(
    '%s/asset_log_return.xlsx' % input_path_2,
    index_col=0
)
asset_volatility = asset_log_return.truncate(before=pd.Timestamp('2020-04-01')).std().sort_index() * (252 ** .5) * 100
asset_log_return_normalized = asset_log_return.copy()
for column in asset_log_return.columns:
    asset_log_return_normalized[column] /= asset_volatility[column] / 5
asset_log_return = asset_log_return_normalized.copy()

date_end = product_log_return.index[-1]
date_truncate = date_end + pd.tseries.offsets.YearBegin(-3)

# _______________________________________________________________________________________________
# Preprocess
window_size = 15
rolling_window_size = 252 * 4
pca_window_size = 252 * 4
min_window_size = 252
x_without_pre = pd.DataFrame()
for key in regression[window_size]['x'].keys():
    if key in [0,1]: 
        continue
    x_without_pre[key] = regression[window_size]['x'][key].mean(axis=1)
x = pd.DataFrame()
for key in regression[window_size]['x'].keys():
    if key in [0]: 
        continue
    x[key] = regression[window_size]['x'][key].mean(axis=1)

product_selector = [
    'PREDI720 Index', 
    'IBOV Index', 
    'SPX Index', 
    'USDBRL Curncy'
]
a_matrix = product_log_return[product_selector].copy()
b_matrix = asset_log_return.mean(axis=1).copy()
x_mean_without_pre = x_without_pre.rolling(rolling_window_size, min_periods=min_window_size).mean() 
x_std_without_pre = x_without_pre.rolling(rolling_window_size, min_periods=min_window_size).std()
x_mean = x.rolling(rolling_window_size, min_periods=min_window_size).mean() 
x_std = x.rolling(rolling_window_size, min_periods=min_window_size).std()

# _______________________________________________________________________________________________
# PCA
components_without_pre, _ = process.rolling_pca(
    x_without_pre,
    x_mean_without_pre,
    x_std_without_pre,
    pca_window_size
)
for key in components_without_pre.keys():
    components_without_pre[key].fillna( 
        method='bfill', 
        inplace=True, 
        axis=0 
    )

components, _ = process.rolling_pca(
    x,
    x_mean,
    x_std,
    pca_window_size
)
for key in components.keys():
    components[key].fillna( 
        method='bfill', 
        inplace=True, 
        axis=0 
    )

# x_mean_without_pre = 0
# print(x_mean_without_pre)
x_mean_without_pre[2] = .038
x_mean_without_pre[3] = .035
x_mean_without_pre[4] = 0
# quit()
components_without_pre[0][2] = 1 #* 329 /251
components_without_pre[0][3] = 1
components_without_pre[0][4] = -1
# components_without_pre[0][2] = .6
# components_without_pre[0][2] = .6

# plt.plot(components_without_pre[0])
# plt.legend([
#     'IBOV Index', 
#     'SPX Index', 
#     'USDBRL Curncy'
# ])
# plt.show()
# quit()
# from mpl_toolkits import mplot3d
# ax = plt.axes(projection='3d')
# ax.scatter3D(
#     components[0][2],
#     components[0][3],
#     components[0][4],
#     cmap='Greens'
# )
# ax.set_xlabel('IBOV')
# ax.set_ylabel('SPX')
# ax.set_zlabel('USDBRL')
# plt.show()

beta_0_without_pre, beta_pre, beta_pc_without_pre, r2_without_pre, pca_without_pre = process.analysis_2(
    a_matrix, 
    b_matrix,
    components_without_pre[0].to_numpy(),
    x_mean_without_pre.to_numpy(),
    x_std_without_pre.to_numpy(),
    debug=False,
    window_size=window_size,
)
beta_pc_without_pre = ( beta_pc_without_pre - beta_pc_without_pre.mean() )/ beta_pc_without_pre.std()
# beta_0, beta_pc, r2, pca = process.analysis(
#     a_matrix, 
#     b_matrix,
#     components[0].to_numpy(),
#     x_mean.to_numpy(),
#     x_std.to_numpy(),
#     debug=False,
#     window_size=window_size,
# )

def plot_1(df, stats, show_as_percent=True):
    rolling_window = 30
    aux = df.copy()
    aux_2 = np.nan * df.iloc[-math.floor(rolling_window/2)-1:]
    aux_2.index = [aux.index[-1] for x in aux_2.index]
    aux = pd.concat([df, aux_2])
    aux.fillna(method='ffill', inplace=True)
    plt.plot(df, 'cyan', linewidth=1, label='Exposição')
    plt.gca().set_facecolor((.8, .8, .8))
    plt.plot(aux.rolling(rolling_window, center=True).mean(), 'b', linewidth=2, label='Moving avg. 30d')
    plt.ylabel('Exposição (%)')
    if 'mean' in stats:
        min_x = df.index.min()
        max_x = df.index.max()
        text_box_config = {
            'color': 'k',  
            'verticalalignment': 'bottom', 
            'size': 10,
            'weight': 'bold',
            #'fontweight': 'bold',
        }
        for line_info in [
            ( stats['mean'], {'linewidth': 2} ),
            ( stats['mean'] + 1 * stats['std'], {'linestyle': 'dashed'}),
            ( stats['mean'] - 1 * stats['std'], {'linestyle': 'dashed'}),
            ( stats['mean'] + 2 * stats['std'], {'linestyle': 'dashed'}),
            ( stats['mean'] - 2 * stats['std'], {'linestyle': 'dashed'}),  
        ]:
            plt.hlines( line_info[0], min_x, max_x, colors='r', **line_info[1])
            if show_as_percent:
                plt.text( min_x, line_info[0], '%.1f%%' % (line_info[0]), **text_box_config)
            else:
                plt.text( min_x, line_info[0], '%.1f std' % (line_info[0]), **text_box_config)
    plt.grid()
    plt.legend()
    plt.gcf().autofmt_xdate()

plot_1( 
    beta_pc_without_pre, 
    {
        'mean': beta_pc_without_pre.mean(),
        'std': beta_pc_without_pre.std()
    },
    show_as_percent=False
)
plt.title('Indicador de otimismo (+) e pessimismo (-): Ibov, SPX, USDBRL')
plt.ylabel('Indicador de otimimismo e pessimismo')
plt.savefig('%s/indicador_otimismo.png' % output_path)
plt.close()

plot_1(
    beta_pre * 100,
    {
        'mean': beta_pre.mean()*100,
        'std': beta_pre.std()*100
    },
)
plt.title('Posicionamento PRE ajustado com indicador de otimismo')
plt.savefig('%s/indicador_otimismo_pre.png' % output_path)
plt.close()

aux = beta_pc_without_pre.truncate(before=date_truncate)
plot_1( 
    aux,
    {
        'mean': aux.mean(),
        'std': aux.std()
    },
    show_as_percent=False
)
plt.title('Indicador de otimismo (+) e pessimismo (-): Ibov, SPX, USDBRL')
plt.ylabel('Indicador de otimimismo e pessimismo')
plt.savefig('%s/indicador_otimismo_b.png' % output_path)
plt.close()

aux = beta_pre.truncate(before=date_truncate)
plot_1( 
    aux*100, 
    {
        'mean': aux.mean()*100,
        'std': aux.std()*100
    }
)
plt.title('Posicionamento PRE ajustado com indicador de otimismo')
plt.savefig('%s/indicador_otimismo_pre_b.png' % output_path)
plt.close()
