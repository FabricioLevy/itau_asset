import time_plot
import pandas as pd
import matplotlib.pyplot as plt
import os
import hist_plot


def get_data(data_file, ticker_file):
    # Read bloomberg data
    data = pd.read_excel( 
        data_file,
        index_col=0
    )
    # data.drop( 'field', axis=0, inplace=True )
    # data.drop( 'date_reference', axis=0, inplace=True )

    # Read tickers
    tickers = pd.read_excel( 
        ticker_file,
        index_col=0
    )
    print( tickers )

    # Parse data
    results = {}
    for country in tickers.index:
        if country not in results:
            results[ country ] = pd.DataFrame( columns = [] )
        
        print(country, end=' - ')

        for selector in ['3M Ticker', '6M Ticker', '1Y Ticker', '2Y Ticker', '5Y Ticker']:
            ticker = tickers[ selector ][country]
            
            print(ticker, end=' ')
            results[ country ][ selector ] = data[ticker]
        print('\n')

    return tickers, results

def get_processed_data(df, tickers):

    results = {}
    for country in tickers.index:
        results[ country ] = pd.DataFrame(columns=[
            '6M-3M', '1Y-3M', '2Y-3M', '5Y-3M',
            '2Y-1Y', '5Y-2Y'
        ])

        results[ country ][ '6M-3M' ] = ( df[ country ]['6M Ticker'] - df[ country ]['3M Ticker'] ) * 100
        results[ country ][ '1Y-3M' ] = ( df[ country ]['1Y Ticker'] - df[ country ]['3M Ticker'] ) * 100
        results[ country ][ '2Y-3M' ] = ( df[ country ]['2Y Ticker'] - df[ country ]['3M Ticker'] ) * 100
        results[ country ][ '5Y-3M' ] = ( df[ country ]['5Y Ticker'] - df[ country ]['3M Ticker'] ) * 100

        results[ country ][ '2Y-1Y' ] = ( df[ country ]['2Y Ticker'] - df[ country ]['1Y Ticker'] ) * 100
        results[ country ][ '5Y-2Y' ] = ( df[ country ]['5Y Ticker'] - df[ country ]['2Y Ticker'] ) * 100
    return results

def calculate_stats(df):
    stats = {
        'all': {
            'median': {},
            'mean': {},
            'std': {},
            'last_x': {},
            'max': {},
            'min': {},
        }
    }
    for item in df.columns:
        last_value = df[item][ df[item].notnull() ].values[-1]
        stats['all']['median'][item] = df[item].median(skipna=True)
        stats['all']['mean'][item] = df[item].mean(skipna=True)
        stats['all']['std'][item] = df[item].std(skipna=True)
        stats['all']['max'][item] = df[item].max(skipna=True)
        stats['all']['min'][item] = df[item].min(skipna=True)
        stats['all']['last_x'][item] = last_value
    return stats

def main():

    folder_name = '1_plot'
    input_path2 = '../../output/0_update_bloomberg'
    input_path = '../../input/0_update_bloomberg'
    output_path = '../../output/%s' % folder_name

    # Create output folder
    for folder in ['../../output', output_path]:
        if not os.path.exists(folder):
            os.makedirs(folder)

    # Get data and process
    tickers, data = get_data(
        '%s/data.xlsx' % (input_path2),
        '%s/tickers.xlsx' % (input_path)
    )

    data_2 =  get_processed_data(data, tickers)

    data_3 = {}
    for curve in ['6M-3M', '1Y-3M', '2Y-3M', '5Y-3M', '2Y-1Y', '5Y-2Y']:
        data_3[curve] = pd.DataFrame()
        for country in data_2.keys():
            data_3[curve][country] = data_2[country][curve]

    plot_dict = {
        '6M-3M': {
            'title_1': 'Curva 6M - 3M',
            'title_2': 'Histogram 6M - 3M',
        },
        '1Y-3M': {
            'title_1': 'Curva 1Y - 3M',
            'title_2': 'Histogram 1Y - 3M',
        },
        '2Y-3M': {
            'title_1': 'Curva 2Y - 3M',
            'title_2': 'Histogram 2Y - 3M',
        },
        '5Y-3M': {
            'title_1': 'Curva 5Y - 3M',
            'title_2': 'Histogram 5Y - 3M',
        },
        '2Y-1Y': {
            'title_1': 'Curva 2Y - 1Y',
            'title_2': 'Histogram 2Y - 1Y',
        },
        '5Y-2Y': {
            'title_1': 'Curva 5Y - 2Y',
            'title_2': 'Histogram 5Y - 2Y',
        }
    }

    print(tickers)
    for country in tickers.index:
        print('%16s' % country, end='   ')
        stats = calculate_stats( data_2[country] )
        
        for key in plot_dict.keys():
            print(key, end='   ')
            plot_dict_item = plot_dict[key].copy()
            plot_dict_item['title_1'] += ' (%s)' % (country)
            plot_dict_item['title_2'] += ' (%s)' % (country)
            plot_dict_item['ylim'] = [
                stats['all']['mean'][key] - 3*stats['all']['std'][key],
                stats['all']['mean'][key] + 3*stats['all']['std'][key]
            ]
            time_plot.plot( 
                data_2[ country ], 
                stats, 
                None, 
                {key: plot_dict_item}, 
                key
            )
            plt.savefig( '%s/%s_%s.png' % (output_path, key, country) )
            plt.close()

            hist_plot.plot(
                data_2[ country ],
                stats,
                None,
                {key: plot_dict_item}, 
                key
            )
            plt.savefig( '%s/%s_%s_hist.png' % (output_path, key, country) )
            plt.close()
        print('')
    
if __name__ == '__main__':
    main()