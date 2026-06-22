#%%
import pandas as pd
import matplotlib.pyplot as plt
from sklearn import preprocessing
import seaborn as sns
import numpy as np
import os
from sklearn.decomposition import PCA
from statsmodels.tsa.stattools import adfuller


def test_adfuller(data, plot=False):
    for country in data.keys():
        for column in data[country]:
            passed_test = test_series( data[country][column] )
            if not passed_test:
                print(country, column, 'not passed adfuller')
                if passed_test:
                    plt.plot( data[country][column] )
                    plt.title('%s %s %s' % (country, column, 'not Passed'))
                    plt.show()

def test_series(series):
    # Return None if series is constant
    # Return True if passed augmented dicker fuller test
    # Return False if not passed
    x = series.dropna().values
    if min(x) != max(x): # this is necessary to avoid error in adfuller
        adf, _, _, _, critical_values, _ = adfuller( x )
        pass_test = ( not np.isnan(adf) ) & ( adf < critical_values['5%'] )
    else:
        pass_test = None
    return pass_test
