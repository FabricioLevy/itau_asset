from sklearn.decomposition import PCA
import pandas as pd
import matplotlib.pyplot as plt

def test(a_matrix, show=False):
    normalization = lambda x: (x - x.mean()) / x.std()
    a1_normalized = a_matrix.copy()
    for key in a1_normalized.columns:
        a1_normalized[key] = normalization( a1_normalized[key] ) 
    a1_normalized.dropna(inplace=True)

    pca = PCA(n_components=len( a_matrix.columns ))
    pca.fit( a1_normalized.to_numpy() )
    data_pca = pd.DataFrame( 
        pca.transform( a1_normalized.to_numpy() ),
        index=a1_normalized.index
    )
    if show==True:
        print(a_matrix.mean())
        print(a_matrix.std())
        print(pca.components_)
        print(pca.explained_variance_ratio_)
        plt.plot(data_pca)
        plt.legend([
            ('X.w (pc %d)' % (x+1))
            for x
            in range( len( a_matrix.columns ) )
        ])
        plt.show()
        plt.close()
        
        # fig = plt.figure(figsize=(15,15))
        # ax = fig.add_subplot(111, projection='3d')
        # index_i = 0
        # index_j = 1
        # index_k = 2
        # ax.scatter( 
        #     a1_normalized[a1_normalized.columns[index_i]], 
        #     a1_normalized[a1_normalized.columns[index_j]], 
        #     a1_normalized[a1_normalized.columns[index_k]], 
        #     marker='o',
        #     alpha=.05
        # )
        # for component_i, _ in enumerate(pca.components_):
        #     a = plt.plot(
        #         [
        #             0, 
        #             pca.singular_values_[component_i] * pca.components_[component_i][index_i] / 20
        #         ], 
        #         [
        #             0, 
        #             pca.singular_values_[component_i] * pca.components_[component_i][index_j] / 20
        #         ], 
        #         [
        #             0,
        #             pca.singular_values_[component_i] * pca.components_[component_i][index_k] / 20
        #         ],
        #         lw=3,
        #         color="r"
        #     )
        # ax.set_xlabel(a_matrix.columns[index_i])
        # ax.set_ylabel(a_matrix.columns[index_j])
        # ax.set_zlabel(a_matrix.columns[index_k])
        # plt.show()
        # plt.close()

    return pca, data_pca
