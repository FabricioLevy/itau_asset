import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches

pd.plotting.register_matplotlib_converters()

def plot(df, stats, copom, plot_dict, column):
    plot_info = plot_dict[column]
    x = df[column].dropna()

    # Define used colors
    color_data = (0.2, 0.2, 0.2)

    def draw_copom_highlight(hike_color = (1,0.8,0.8), cut_color = (0.8,0.85,1)):
        for date_index, date in enumerate(copom.index):
            color = cut_color # corte

            if copom['Flag'][date] == 0:
                continue
            elif copom['Flag'][date] == 1: # hike
                color = hike_color

            if date_index != len(copom.index) - 1:
                ax.axvspan(copom.index[date_index], copom.index[date_index+1], facecolor=color)
            else:
                ax.axvspan(copom.index[date_index], df.index.iloc[-1], facecolor=color)

    def set_legend(hike_color = (1,0.8,0.8), cut_color = (0.8,0.85,1)):
        handles, _ = ax.get_legend_handles_labels()
        # manually define a new patch 
        red_patch = mpatches.Patch(facecolor=hike_color, label='Hike')
        blue_patch = mpatches.Patch(facecolor=cut_color, label='Corte')
        # handles is a list, so append manual patch
        handles.append(red_patch) 
        handles.append(blue_patch) 
        # plot the legend
        plt.legend(handles=handles, loc='upper center', ncol=6)

    def draw_median(df, stats, color_median = (0.1,0.1,0.1,0.5)): 
        val = stats['all']['median'][column]
        plt.annotate( 
            "  %.1f" % val, 
            xy=( x.index.iloc[-1], val - 0.5 ) 
        )
        plt.plot( 
            x.index, np.ones(len(x.index)) * val, 
            '--', label='Mediana', color=color_median,
            linewidth=3,
        )

    def draw_dev(df, stats, color_median = (0.1,0.1,0.1,0.5), max_y = 300):
        for j in range(-2, 3):
            linewidth = 2
            label = None
            color = (0.1,0.1,0.1,0.5)
            color_annotation = (0.5, 0.5, 0.5)
            if j == 0:
                linewidth = 3
                label = 'Média'
                color = (0.1,0.1,1,0.5)
                color_annotation = (0.5,0.5,1)
            if j == 1:
                label = '+- 1 ou 2 desv.'
            val = stats['all']['mean'][column] + j*stats['all']['std'][column]

            if val < max_y:
                plt.annotate( 
                    "%.1f" % val, 
                    xy=( x.index[15], val ),
                    color='w', 
                    bbox=dict(
                        facecolor=color_annotation, 
                        edgecolor='w', 
                        boxstyle='square,pad=0.2',
                        lw=0
                    )
                )
            plt.plot( 
                x.index, np.ones(len(x.index)) * val, 
                '-', 
                color=color,
                linewidth=linewidth,
                label=label
            )

    def draw_last_value():
        ax.annotate(
            "%s\n%.1f" % ( pd.to_datetime(x.index[-1]).strftime("%d/%m/%Y"), x.iloc[-1] ) ,
            xy=( x.index[-1], x.iloc[-1] ),
            xytext=(x.index[-1] + np.timedelta64(300,'D'), x.iloc[-1]-1),
            color='w', 
            arrowprops={
                'arrowstyle': '-'
            },
            bbox=dict(facecolor=(0.5, 0.5, 0.5), edgecolor='none', boxstyle='square,pad=0.4')
        )

    #plot
    _, ax = plt.subplots(figsize=(11,5))

    #draw copom highlight
    draw_copom_highlight()
    #draw last value
    draw_last_value()
    #draw median
    draw_median(df, stats)
    #draw mean and standard devs
    draw_dev(df, stats, max_y = plot_info['ylim'][1])

    #draw data
    ax.plot( x, color=color_data, label="Prêmio", lw=1)
    set_legend()

    if plot_info['title_1'] != None:
        plt.title(plot_info['title_1'])
    plt.xlabel('Data')
    plt.ylabel('Prêmio (bps)')
    plt.xlim(( x.index[0], x.index.iloc[-1] ))
    plt.ylim((plot_info['ylim']))
    plt.tight_layout()