import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

def plot(y, y2, stats={}, title='', ylabel='Exposição PL (%)', quantiles=None):
    if quantiles is not None:
        aux = quantiles.copy()
        aux['date'] = aux.index
        x = aux['date'].values
        plt.fill_between( x, aux[.25]*100, aux[.75]*100, alpha=.2, color='k', label='Q25-Q75')
        # plt.fill_between( x, aux[.10]*100, aux[.90]*100, alpha=.1, color='k', label='Q10-Q90')
    plt.plot(y*100, color='cyan', linewidth=1, label='Exposição')
    plt.plot(y2*100, 'b', label='Moving avg.', linewidth=2)
    plt.legend()
    if 'mean' in stats:
        min_x = y.index.min()
        max_x = y.index.max()
        text_box_config = {
            'color': 'k',  
            'verticalalignment': 'bottom', 
            'size': 10,
            'fontweight': 'bold',
        }
        for line_info in [
            ( stats['mean'], {'linewidth': 2} ),
            ( stats['mean'] + 1 * stats['std'], {'linestyle': 'dashed'}),
            ( stats['mean'] - 1 * stats['std'], {'linestyle': 'dashed'}),
            ( stats['mean'] + 2 * stats['std'], {'linestyle': 'dashed'}),
            ( stats['mean'] - 2 * stats['std'], {'linestyle': 'dashed'}),  
        ]:
            plt.hlines( line_info[0]*100, min_x, max_x, colors='r', **line_info[1])
            plt.text( min_x, line_info[0]*100, '%.1f%%' % (line_info[0]*100), **text_box_config)
    plt.grid()
    plt.title(title)
    plt.ylabel(ylabel)
    plt.gcf().autofmt_xdate()
    # plt.show()
    # plt.close()

def plot_r2(y, y2, stats={}, title='', ylabel=''):
    plt.figure()
    plt.plot(y, color=(.8,.8,.8))
    plt.plot(y2)
    if 'mean' in stats:
        min_x = y.index.min()
        max_x = y.index.max()
        text_box_config = {
            'color': 'k', 
            'verticalalignment': 'bottom', 
            'size': 10,
            'fontweight': 'bold',
        }
        for line_info in [
            ( stats['mean'], {'linewidth': 2} ),
            ( stats['mean'] + 1 * stats['std'], {'linestyle': 'dashed'}),
            ( stats['mean'] - 1 * stats['std'], {'linestyle': 'dashed'}),
            ( stats['mean'] + 2 * stats['std'], {'linestyle': 'dashed'}),
            ( stats['mean'] - 2 * stats['std'], {'linestyle': 'dashed'}),  
        ]:
            plt.hlines( line_info[0], min_x, max_x, colors='r', **line_info[1])
            plt.text( min_x, line_info[0], '%.2f' % (line_info[0]), **text_box_config)
    # plt.grid()
    plt.title(title)
    plt.ylabel(ylabel)
    plt.gcf().autofmt_xdate()
    # plt.show()
    # plt.close()

def plot_return_horizontal_bar(returns, product_returns, title):
    # selection_data = product_returns.iloc[-1] * 100
    # selection_data.loc['CDI'] = .1
    data_2 = pd.DataFrame( product_returns.iloc[-1] ) * 100
    data_2.columns = ['Return']
    data_2.index.name = 'Product'

    selection_data = returns.iloc[-1] * 100
    selection_data.loc['CDI'] = .1
    data = pd.DataFrame( selection_data.sort_values(ascending=False) )
    data.columns = ['Return']
    data.index.name = 'Fund'

    plt.figure( figsize=(6,7.5) )
    plt.barh(data.index.to_list(), data['Return'].to_list(), color='gray', alpha=0.30)
    plt.barh(['CDI'], [.1], color='black', alpha=0.60)
    plt.barh(['Asset1'], [data.loc['Asset1', 'Return']], color='darkblue', alpha=0.30)
    plt.barh([''], [0])
    aux = data_2.index.to_list()
    plt.barh(aux, [0 for x in aux], color='darkblue', alpha=0.30)
    for _, row in data.iterrows():
        x_pos = 0 if np.isnan(row['Return']) else row['Return']
        text_value = 'Não existente' if np.isnan(row['Return']) else '%.1f%%' % row['Return']
        plt.text(
            x_pos, 
            row.name, 
            text_value, 
            color='darkred' if row['Return'] < 0 else 'darkblue',
            verticalalignment='center',
        )
    for _, row in data_2.iterrows():
        plt.text(
            0, 
            row.name, 
            '%.1f%%' % row['Return'] if 'PREDI' not in row.name else '%.1fbps' % row['Return'], 
            color='darkred' if row['Return'] < 0 else 'darkblue',
            verticalalignment='center',
        )
    plt.margins(y=0.005)
    plt.xticks([])
    plt.gca().invert_yaxis()
    plt.title(title)
    plt.tight_layout()