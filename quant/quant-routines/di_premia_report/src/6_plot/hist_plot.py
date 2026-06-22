import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches

pd.plotting.register_matplotlib_converters()

def plot(df, stats, copom, plot_dict, column):
    plot_info = plot_dict[column]
    x = df[column].dropna()

    frequency, bins, _= plt.hist(x, bins=70)
    total_frequency = np.sum(frequency)
    bin_center = ( bins[0:-1] + bins[1:] )/2

    _, ax = plt.subplots(figsize=(10,5))
    ax.bar(
        bin_center, 
        frequency/total_frequency*100, 
        1/70 * ( df[column].max() - df[column].min() ), 
        color=(.5,.6,.5, 0),
        edgecolor=(0,0,0),
    )
    _, top_ylim = plt.ylim()

    # draw mean and std devs
    for j in range(-2, 3):
        color = (.1,.1,.1,.5)
        color_annotation = (0.4,0.4,0.4)
        linewidth = 3
        label = None
        if j == 0:
            color = (0.1,0.1,1,0.5)
            color_annotation = (0.4,0.4,1)
            linewidth = 4
            label = "Média"
        elif j == 1:
            label = "+- 1 ou 2 desv."
        val = stats['all']['mean'][column] + j*stats['all']['std'][column]
        ax.plot(
            [val, val], 
            [0, 100], 
            color=color,
            lw = linewidth,
            label=label
        )
        ax.annotate( 
            "%.1f" % val, 
            xy=( val, plot_info['ylim'][1]/100 ),
            color='w', 
            bbox=dict(
                facecolor=color_annotation, 
                edgecolor='w', 
                boxstyle='square,pad=0.2',
                lw=0
            ),
            ha='center'
        )
    # draw last value
    val = stats['all']['last_x'][column]
    ax.plot(
        [val, val], 
        [0, 100], 
        '-',
        color=(.1,1,.1,.5),
        lw=11,
        label="Último valor"
    )
    ax.annotate( 
        "%.1f" % val, 
        xy=( val, top_ylim*0.75 ),
        color='w', 
        bbox=dict(
            edgecolor='None', 
            facecolor=(.1,0.8,.1),
            boxstyle='square,pad=0.2',
            lw=0
        ),
        # ha='center'
    )

    # other plot elements
    if plot_info['title_2'] != None:
        plt.title(plot_info['title_2'])
    plt.ylim((0, top_ylim*1.1))
    lower_limit = stats['all']['mean'][column] - 3*stats['all']['std'][column]
    upper_limit = stats['all']['mean'][column] + 3*stats['all']['std'][column]
    if val < lower_limit:
        lower_limit = val - .1 * (upper_limit - lower_limit)
    elif val > upper_limit:
        upper_limit = val + .1 * (upper_limit - lower_limit)
    plt.xlim((lower_limit, upper_limit))
    plt.xlabel('Prêmio (bps)')
    plt.ylabel('Frequência (%)')
    plt.legend(loc='upper center', ncol=5)
    plt.tight_layout()


def plot_2(df, stats, copom, plot_dict, column):
    plot_info = plot_dict[column]
    data = {
        'Hike': df[ df['Copom flag'] == 1 ][column].dropna(),
        'Manut': df[ df['Copom flag'] == 0 ][column].dropna(),
        'Corte': df[ df['Copom flag'] == -1 ][column].dropna(),
    }
    color_dict = {
        'Hike': (1,.5,.3),
        'Manut': (.8,.8,.8),
        'Corte': (.1,.5,1),
    }
    data_max = max(
        [ data[key].max() for key in data.keys()]
    )
    data_min = min(
        [ data[key].min() for key in data.keys()]
    )
    bin_list = np.linspace( data_min-0.1, data_max+0.1, num=50)
    amplitude = ( data_max - data_min + 0.1*2 ) * .9
    bin_center = ( bin_list[0:-1] + bin_list[1:] )/2
    freq_data = {
        key: plt.hist( data[key], bin_list )[0]
        for key 
        in data.keys()
    }
    total_frequency = sum([
        np.sum( freq_data[key] )
        for key
        in data.keys()
    ])
    normalized_freq_data = {
        key : freq_data[key] / total_frequency
        for key
        in data.keys()
    }
    
    bottom = [0 for x in bin_center]
    _, ax = plt.subplots(figsize=(10,5))
    for key in data.keys():
        plt.bar(
            bin_center, 
            normalized_freq_data[key], 
            bottom=bottom,
            width= amplitude / 50,
            color=color_dict[key]
        )
        bottom += normalized_freq_data[key]

    _, top_ylim = plt.ylim()

    # draw mean and std devs
    for j in range(-3, 4):
        color = (.1,.1,.1,.5)
        color_annotation = (0.4,0.4,0.4)
        linewidth = 3
        label = None
        if j == 0:
            color = (0.1,0.1,1,0.5)
            color_annotation = (0.4,0.4,1)
            linewidth = 4
            label = "Média"
        elif j == 1:
            label = "+- 1 ou 2 desv."
        val = stats['all']['mean'][column] + j*stats['all']['std'][column]
        ax.plot(
            [val, val], 
            [0, 100], 
            color=color,
            lw = linewidth,
            label='_nolegend_'
        )
        ax.annotate( 
            "%.1f" % val, 
            xy=( val, top_ylim * .1 ),
            color='w', 
            bbox=dict(
                facecolor=color_annotation, 
                edgecolor='w', 
                boxstyle='square,pad=0.2',
                lw=0
            ),
            ha='center'
        )
    # draw last value
    val = stats['all']['last_x'][column]
    ax.plot(
        [val, val], 
        [0, 100], 
        '-',
        color=(.1,1,.1,.5),
        lw=11,
        label="Último valor"
    )
    ax.annotate( 
        "%.1f" % val, 
        xy=( val, top_ylim*0.75 ),
        color='w', 
        bbox=dict(
            edgecolor='None', 
            facecolor=(.1,0.8,.1),
            boxstyle='square,pad=0.2',
            lw=0
        ),
        # ha='center'
    )

    # other plot elements
    if plot_info['title_2'] != None:
        plt.title(plot_info['title_2'])
    plt.ylim((0, top_ylim*1.1))
    lower_limit = stats['all']['mean'][column] - 3*stats['all']['std'][column]
    upper_limit = stats['all']['mean'][column] + 3*stats['all']['std'][column]
    if val < lower_limit:
        lower_limit = val - .1 * (upper_limit - lower_limit)
    elif val > upper_limit:
        upper_limit = val + .1 * (upper_limit - lower_limit)
    plt.xlim((lower_limit, upper_limit))
    plt.xlabel('Prêmio (bps)')
    plt.ylabel('Frequência (%)')
    plt.legend(loc='upper center', ncol=5)
    flatten = lambda t: [item for sublist in t for item in sublist]
    plt.legend( flatten( 
        [
            ['Último valor'], 
            data.keys()
        ] 
    ) )
    plt.grid()
    plt.tight_layout()