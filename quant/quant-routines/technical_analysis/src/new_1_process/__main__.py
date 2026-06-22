import pandas as pd
import numpy as np
import statsmodels.api as sm
import pickle
import os
import matplotlib.pyplot as plt

def preprocess(input_df):
    df = input_df.copy()
    for column in df:
        df[column][df[column] <= 0] = np.nan
    for column in df:
        if column in ('DI2Y',):
            df[column] = df[column].diff() / 100
        else:
            df[column] = np.log(df[column]).diff()
    return df

def regression(input_df, y_variable, window_size = 15):
    df = input_df.dropna()
    x_matrix = df[[x for x in df if x!= y_variable]].copy()
    y_matrix = df[y_variable].copy()
    result_list = []
    for i in range(y_matrix.size - window_size+1):
        current_x = x_matrix.iloc[i:i+window_size]
        current_y = y_matrix.iloc[i:i+window_size]
        # model = sm.OLS(current_y, current_x)
        model = sm.RLM(current_y, current_x, M=sm.robust.norms.HuberT())
        res = model.fit()
        result = res.params.copy()
        result['R2'] = res.rsquared
        result_list.append( 
            [current_y.index[-1].date()] + list(result) 
        )
    result_df = pd.DataFrame(
        result_list,
        columns = ['date']+list(result.index)
    ).set_index('date')
    return result_df

def run_all_regressions(data_df, fund_info_df, regression_variables):
    result_dict = {}
    print("Running regression")
    for cnpj_master in fund_info_df['cnpj_master'].unique():
        print(cnpj_master)
        columns = regression_variables+[cnpj_master]
        current_result = regression(
            data_df[columns], 
            cnpj_master
        )
        for column in current_result:
            if column not in result_dict.keys():
                result_dict[column] = (
                    current_result[column].rename(cnpj_master)
                )
                continue
            result_dict[column] = pd.concat(
                [
                    result_dict[column],
                    current_result[column].rename(cnpj_master),
                ],
                axis=1
            )
    for column in result_dict.keys():
        result_dict[column] = result_dict[column].sort_index()
    return result_dict

def group_result(result_dict):
    for key in result_dict.keys():
        aux = result_dict[key] * 100
        plt.plot(aux.quantile(0.75,axis=1), color=(0,0,0,.1))
        plt.plot(aux.quantile(0.25,axis=1), color=(0,0,0,.1))
        plt.plot(aux.median(axis=1), color=(0,0,1,.2))
        plt.plot(aux.median(axis=1).rolling(21).mean())
        plt.title(key)
        plt.grid()
        plt.show()

def main():
    INPUT_PATH = '../../output/new_0_download_data'
    OUTPUT_PATH = '../../output/new_1_process'
    REGRESSION_VARIABLES = ['USDBRL', 'SPX', 'IBOV', 'DI2Y']
    os.makedirs(OUTPUT_PATH, exist_ok=True)

    fund_info_df = pd.read_pickle('%s/fund_info.pkl' % INPUT_PATH)
    raw_data_df = pd.read_pickle('%s/data.pkl' % INPUT_PATH)
    data_df = preprocess(raw_data_df)

    if 0:
        result_dict = run_all_regressions(
            data_df, 
            fund_info_df, 
            REGRESSION_VARIABLES
        )
        with open('%s/result.pkl' % OUTPUT_PATH, 'wb') as handle:
            pickle.dump(
                result_dict, 
                handle, 
                protocol=pickle.HIGHEST_PROTOCOL
            )
    else:
        with open('%s/result.pkl' % OUTPUT_PATH, 'rb') as handle:
            result_dict = pickle.load(handle)
    group_result(result_dict)

if __name__ == '__main__':
    main()