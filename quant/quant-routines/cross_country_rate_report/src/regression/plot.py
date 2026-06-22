import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

def plot_tickers(data, output_path):
    print('Exporting data graphs')
    for column in data.columns:
        print('Plot ticker', column)
    
        plt.figure()
        plt.plot(data[column], '.-')
        plt.title(column)
        plt.xlabel('Time')
        plt.grid()
        plt.savefig( '%s/1_%s.png' % (output_path, column) )
        plt.close()

def plot_pca_shape(pc, explained_variance, filepath):
    plt.figure(figsize=(14,8))
    plt.subplot(3, 1, 1)
    for country in pc.keys():
        plt.plot( 
            [3, 6, 12, 24, 60],
            pc[country][0], 
            label='%s (%.1f%%)' % (country, explained_variance[country][0])
        )
    plt.title('PC')
    plt.ylabel('First PC vector')
    plt.xlabel('Months')
    plt.legend()
    plt.subplot(3, 1, 2)
    for country in pc.keys():
        plt.plot( 
            [3, 6, 12, 24, 60],
            pc[country][1], 
            label='%s (%.1f%%)' % (country, explained_variance[country][1])
        )
    plt.title('PC')
    plt.ylabel('Second PC vector')
    plt.xlabel('Months')
    plt.legend()
    plt.subplot(3, 1, 3)
    for country in pc.keys():
        plt.plot( 
            [3, 6, 12, 24, 60],
            pc[country][2], 
            label='%s (%.1f%%)' % (country, explained_variance[country][2])
        )
    plt.title('PC')
    plt.ylabel('Third PC vector')
    plt.xlabel('Months')
    plt.legend()
    if filepath != None:
        plt.savefig(filepath)
    else:
        plt.show()
    plt.close()

def plot_pca_factor(country_data, pc_factor, filepath, output_path):
    for country in pc_factor.keys():
        plt.subplot(2,1,1)
        plt.plot( pc_factor[country] )
        plt.title('PC factor %s' % country)
        plt.legend(['Level', 'Slope', 'Curvature'])
        plt.ylabel('PC factor')
        plt.xlabel('Time')
        plt.grid()
        plt.subplot(2,1,2)
        plt.plot( country_data[country]['txpre06m'], label='6M')
        plt.plot( country_data[country]['txpre12m'], label='1Y')
        plt.plot( country_data[country]['txpre24m'], label='2Y')
        plt.plot( country_data[country]['txpre60m'], label='5Y')
        plt.legend()
        plt.ylabel('PC factor')
        plt.xlabel('Time')
        plt.grid()
        if filepath != None:
            plt.savefig( filepath % ( output_path, country ) )
        else:
            plt.show()
        plt.close()

def plot_pairplot(country_data, output_path):
    column_filters = [
        ['txpre12m', 'exp_juros', 'jurosbc'],
        ['txpre12m', 'cpiforecast', 'indutil'],
        ['txpre12m', 'cds5y', 'cds10y',],
        ['txpre12m', 'defnom%', 'pardivnresid' ],
        ['txpre12m', 'cc', 'fdi' ],
        ['txpre12m', 'resint', 'txdes' ],
        ['txpre12m', 'metainfl', 'divpub' ],
        ['txpre12m', 'divbruta', 'cambio' ],
        ['txpre12m', 'cc%', 'tradebalance' ],
    ]
    for country in country_data.keys():
        for column_filter_index, column_filter in enumerate(column_filters):
            print( 'Pairplot', country, column_filter_index )
            column_filter = [ x for x in column_filter if x in country_data[country] ]
            sns.pairplot(country_data[country][column_filter])
            plt.savefig('%s/4_pairplot_%s_%02d.png' % (output_path, country, column_filter_index))
            plt.close()