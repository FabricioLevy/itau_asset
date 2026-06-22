import pandas as pd
import numpy as np
from sklearn.decomposition import PCA

def rate_pca(country_df):
    filter_columns = [
        #'cpiforecast',
        #'cpi',
        #'fdi',        
        #'txdes',
        'txpre03m',
        'txpre06m',
        'txpre12m',
        'txpre24m',
        'txpre60m',
        #'divbruta',
        #'cc%',
    ]
    df = country_df[filter_columns].dropna().copy()
    pca = PCA(n_components=3)
    # plt.plot(df)
    # plt.show()

    pca.fit( df - df.mean() )
    explained_variance = [
        float( '%.1f' % (x*100) )
        for x 
        in pca.explained_variance_ratio_
    ]

    # Store results
    pc = pca.components_ 
    if pc[0][0] < 0:
        pc[0] = -pc[0]
    if pc[1][0] > 0:
        pc[1] = -pc[1]
    if pc[2][0] < 0:
        pc[2] = -pc[2]
    
    pc_factor = pd.DataFrame(
        np.matmul( df.to_numpy(), np.transpose(pc) ),
        index = df.index,
        columns=['level', 'slope', 'curvature']
    )

    return pca.components_, explained_variance, pc_factor

def run_rate_pca(country_data):
    # Per country
    pc = {}
    explained_variance = {}
    pc_factor = {}
    for country in country_data.keys():
        print('Rate PCA', country)
        
        # Analysis
        current_pc, current_explained_variance, current_pc_factor = rate_pca(country_data[country])
        
        # Store results
        pc[country] = current_pc
        explained_variance[country] = current_explained_variance
        pc_factor[country] = current_pc_factor
    return pc, explained_variance, pc_factor