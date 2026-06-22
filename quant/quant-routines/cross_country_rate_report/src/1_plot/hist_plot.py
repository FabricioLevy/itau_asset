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

    _, ax = plt.subplots(figsize=(7,5))
    ax.bar(
        bin_center, 
        frequency/total_frequency*100, 
        1/70 * ( df[column].max() - df[column].min() ), 
        color=(.5,.6,.5, 0),
        edgecolor=(0,0,0),
    )
    _, top_ylim = plt.ylim()

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
    if (
        (val > (stats['all']['mean'][column] - 4*stats['all']['std'][column])) &
        (val < (stats['all']['mean'][column] + 4*stats['all']['std'][column]))
    ):
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
            xy=( val, top_ylim*.1 ),
            color='w', 
            bbox=dict(
                facecolor=color_annotation, 
                edgecolor='w', 
                boxstyle='square,pad=0.2',
                lw=0
            ),
            ha='center'
        )

    # other plot elements
    if plot_info['title_2'] != None:
        plt.title(plot_info['title_2'])
    plt.ylim((0, top_ylim*1.1))
    plt.xlim((
        stats['all']['mean'][column] - 3*stats['all']['std'][column],
        stats['all']['mean'][column] + 3*stats['all']['std'][column]
    ))
    plt.xlabel('(bps)')
    plt.ylabel('Frequência (%)')
    plt.legend(loc='upper center', ncol=5)
    plt.tight_layout()