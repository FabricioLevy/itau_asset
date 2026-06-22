import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches

pd.plotting.register_matplotlib_converters()

def plot(df, stats, copom, plot_dict, column):
    plot_info = plot_dict[column]
    x = df[column].copy()
    # x = x.dropna()

    # Define used colors
    color_data = (0.2, 0.2, 0.2)

    def set_legend(hike_color = (1,0.8,0.8), cut_color = (0.8,0.85,1)):
        handles, _ = ax.get_legend_handles_labels()
        # # manually define a new patch 
        # red_patch = mpatches.Patch(facecolor=hike_color, label='Hike')
        # blue_patch = mpatches.Patch(facecolor=cut_color, label='Corte')
        # # handles is a list, so append manual patch
        # handles.append(red_patch) 
        # handles.append(blue_patch) 
        # plot the legend
        plt.legend(handles=handles, loc='upper center', ncol=6)

    def draw_median(df, stats, color_median = (0.1,0.1,0.1,0.5)): 
        val = stats['all']['median'][column]
        x_space = int(len(x.index)/14)
        amp = (stats['all']['std'][column]) * 0.1
        plt.annotate( 
            "  %.1f" % val, 
            xy=( x.index[x_space], val+amp ),
            bbox=dict(facecolor=(.9, .9, .9), edgecolor='none', boxstyle='square,pad=0.3') 
        )
        plt.plot(
            x.index, np.ones(len(x.index)) * val, 
            '--', label='Mediana', color=color_median,
            linewidth=3,
        )

    def draw_dev(df, stats, color_median = (0.1,0.1,0.1,0.5), max_y = None):
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

            
            if max_y == None or val < max_y:
                aux = 15 if len(x.index) > 15 else len(x.index)-1
                plt.annotate( 
                    "%.1f" % val, 
                    xy=( x.index[aux], val ),
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

    def draw_last_value(df):
        n_days = round(int((df.index[-1] - df.index[0]).days))
        last_value = x[ x.notnull() ].values[-1]
        last_index = x[ x.notnull() ].index[-1]
        # print(df.index[-1], last_value)
        ax.annotate(
            "%s\n%.1f" % ( pd.to_datetime(last_index).strftime("%d/%m/%y"), last_value ) ,
            xy=( df.index[-1], last_value ),
            xytext=( df.index[-1] + np.timedelta64(int(n_days/30),'D' ), last_value),
            color='w', 
            arrowprops={
                'arrowstyle': '-'
            },
            bbox=dict(facecolor=(0.5, 0.5, 0.5), edgecolor='none', boxstyle='square,pad=0.4')
        )

    #plot
    _, ax = plt.subplots(figsize=(7,5))

    #draw mean and standard devs
    draw_dev(df, stats, max_y = plot_info['ylim'][1])
    #draw data
    ax.plot( x, color=color_data, label="Curva", lw=1)
    #draw last value
    draw_last_value(df)
    #draw median
    draw_median(df, stats)

    set_legend()
    # print(x.index[0], x.index[-1])
    if plot_info['title_1'] != None:
        plt.title(plot_info['title_1'])
    plt.xlabel('Data')
    plt.ylabel('Valor (bps)')
    plt.xlim(( x.index[0], x.index[-1] ))
    if plot_info['ylim'][0] != None:
        n_days = round(int((df.index[-1] - df.index[0]).days))
        last_value = x[ x.notnull() ].values[-1]
        if (
            (last_value < plot_info['ylim'][0]) | 
            (last_value > plot_info['ylim'][1])
        ):
            pass
        else:
            plt.ylim((plot_info['ylim']))
    else:
        plt.ylim([
            stats['all']['mean'][column] - 3*stats['all']['std'][column],
            stats['all']['mean'][column] + 3*stats['all']['std'][column]
        ])
    plt.tight_layout()
