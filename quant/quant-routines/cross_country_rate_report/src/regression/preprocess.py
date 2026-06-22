from adfuller import test_series
import pandas as pd 
import matplotlib.pyplot as plt

def preprocess_country_data(tickers, df):
    exclude_columns = ['Description', 'Bloomberg description', 'Obs', 'Turquia']
    ticker_index = tickers.index
    country_data = {}
    for country in tickers.columns.drop(exclude_columns):
        selection_index = {
            tickers[country][x]: tickers.index[x_index]
            for x_index, x
            in enumerate( ticker_index )
            if type(tickers[country][x]) == str
        }
        
        # select data from country
        country_data[country] = df[ selection_index.keys() ].copy()
        country_data[country].rename(
            columns=selection_index,
            copy=False,
            inplace=True
        )
    return country_data

def calculate_delta(series):
    x = series.values
    return pd.Series(
        x[1:] - x[0:-1],
        index=series.index[1:],
        name='dif_%s' % series.name
    )

def fix_stationarity(df):
    exclude_columns = [
        'metainfl',
        'resint',
        'cambio',
        'indutil',
        'cc',
        'tradebalance',
    ]
    dif_columns = [
        # 'jurobc', 
        # 'expjuros', 
        # 'cpiforecast', 
        # 'cpi', 
        # 'cds5y', 
        # 'cds10y', 
        # 'defnom%', 
        # 'pardivnresid', 
        # 'fdi%', 
        # 'txdes', 
        # 'txpre03m', 
        # 'txpre06m', 
        # 'txpre12m', 
        # 'txpre24m',
        # 'txpre60m', 
        # 'divpub%', 
        # 'divbruta%', 
        # 'cc%',
        # 'level',
        # 'slope'
    ]
    fixed_df = {}
    for country in df.keys():
        fixed_df[country] = pd.DataFrame()
        for column in reversed(df[country].columns): 
            # the reversed is to fix a bug with indexes.  
            # curvature index is complete - differently than the diff columns
            # if diff columns are added first, the first index is dropped and not added later

            x = df[country][column]

            if False: # Automatic
                pass_dicker_fuller = test_series( x )
                if pass_dicker_fuller == None:
                    continue
                elif pass_dicker_fuller:
                    print(country, column, 'passed ADF')
                    fixed_df[country] = fixed_df[country].append( pd.DataFrame(x) )
                else:
                    dif_x = calculate_delta(x)
                    pass_dicker_fuller = test_series( dif_x )
                    if pass_dicker_fuller:
                        print(country, column, 'ADF test passed after dif')
                        fixed_df[country] = fixed_df[country].append( pd.DataFrame(dif_x) )
                    else:
                        print(country, column, 'discarted, dif did not pass ADF test')
                        continue
            else:
                if column in exclude_columns:
                    continue
                elif column in dif_columns:
                    dif_x = calculate_delta(x)
                    fixed_df[country][dif_x.name] = dif_x.copy()
                else:
                    fixed_df[country][x.name] = x.copy()

    return fixed_df

def normalize_amp(data):
    result = {}
    normalization_dict = {
        'jurobc': 1, 
        'expjuros': 1, 
        'cpiforecast': 1, 
        'cpi': 1, 
        'cds5y': 100, 
        'cds10y': 100, 
        'defnom%': 10, 
        'pardivnresid': 1, 
        'cc': 100000, 
        'fdi%': 1, 
        'resint': 1, 
        'txdes': 1, 
        'txpre03m': 1, 
        'txpre06m': 1, 
        'txpre12m': 1, 
        'txpre24m': 1, 
        'txpre60m': 1, 
        'metainfl': 1,
        'divpub%': 1, 
        'divbruta%': 1, 
        'cambio': 1, 
        'cc%': 1, 
        'tradebalance': 1, 
        'indutil': 1,
        'slope': 1,

        'dif_jurobc': 1, 
        'dif_expjuros': 1, 
        'dif_cpiforecast': 1, 
        'dif_cpi': 1, 
        'dif_cds5y': 100, 
        'dif_cds10y': 100, 
        'dif_defnom%': 10, 
        'dif_pardivnresid': 1, 
        'dif_cc': 100000, 
        'dif_fdi%': 1, 
        'dif_resint': 1, 
        'dif_txdes': 1, 
        'dif_txpre03m': 1, 
        'dif_txpre06m': 1, 
        'dif_txpre12m': 1, 
        'dif_txpre24m': 1, 
        'dif_txpre60m': 1, 
        'dif_metainfl': 1,
        'dif_divpub%': 1, 
        'dif_divbruta%': 1, 
        'dif_cambio': 1, 
        'dif_cc%': 1, 
        'dif_tradebalance': 1, 
        'dif_indutil': 1,
        'dif_slope': 1,
    }
    for country in data.keys():
        result[country] = data[country].copy()
        for column in data[country]:
            if column in normalization_dict.keys():
                result[country][column] = result[country][column] / normalization_dict[column]
        # print(result[country].max()-result[country].min())
        # print(country)
        # print('_______________________')
    return result