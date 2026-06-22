import pandas as pd
import matplotlib.pyplot as plt
import os
import time_plot
import hist_plot
import stats as stat_utils
import pickle
pd.plotting.register_matplotlib_converters()

def main():
    input_path = '../../output/5_export_premia/premia.xlsx'
    input_copom_path = '../../output/4_export_hike_corte/hike_corte.xlsx'
    output_folder = '../../output/6_plot'

    # Create output folder
    for folder in ['../../output', output_folder]:
        if not os.path.exists(folder):
            os.makedirs(folder)

    print("Reading input files")
    # Import premia data
    premia = pd.read_excel(input_path, index_col=0)    

    # Import copom data
    copom = pd.read_excel(input_copom_path)
    copom['date'] = pd.to_datetime(copom['date'])
    copom = copom.set_index('date')

    # Calculate mean, median, std, etc
    stats = stat_utils.calculate_all(premia)
    with open('%s/stats.pkl' % output_folder, 'wb') as handle:
        pickle.dump(stats, handle, protocol=pickle.HIGHEST_PROTOCOL)

    # Plot time series
    plot_dict = {
        '6M': {
            'output_prefix': '1_',
            'ylim': (-50, 150),
            'title_1': 'Prêmio DI (6M)',
            'title_2': 'Histograma do prêmio DI (6M)',
        }, 
        '1Y': { 
            'output_prefix': '2_',
            'ylim': (-50, 200),
            'title_1': 'Prêmio DI (1Y)',
            'title_2': 'Histograma do prêmio DI (1Y)',
        }, 
        '18M': { 
            'output_prefix': '2a_',
            'ylim': (-50, 250),
            'title_1': 'Prêmio DI (18M)',
            'title_2': 'Histograma do prêmio DI (18M)',
        }, 
        '2Y': { 
            'output_prefix': '3_',
            'ylim': (-50,350),
            'title_1': 'Prêmio DI (2Y)',
            'title_2': 'Histograma do prêmio DI (2Y)',
        }, 
        '2Y-1Y': { 
            'output_prefix': '4_',
            'ylim': (-50, 150),
            'title_1': 'Prêmio de inclinação (2Y - 1Y)',
            'title_2': 'Histograma do prêmio de inclinação (2Y - 1Y)',
        }, 
        '5Y-2Y': { 
            'output_prefix': '5_',
            'ylim': (-50, 200),
            'title_1': 'Prêmio de inclinação (5Y - 2Y)',
            'title_2': 'Histograma do prêmio de inclinação (5Y - 2Y)',
        },
        'implicit_6m': { 
            'output_prefix': '6a_',
            'ylim': (-200, 300),
            'title_1': 'Prêmio de inflação implícita (6M)',
            'title_2': 'Histograma do prêmio de inflação implícita (6M)',
        }, 
        'implicit_1y': { 
            'output_prefix': '6_',
            'ylim': (-200, 300),
            'title_1': 'Prêmio de inflação implícita (1Y)',
            'title_2': 'Histograma do prêmio de inflação implícita (1Y)',
        },
        'implicit_18m': { 
            'output_prefix': '6aa_',
            'ylim': (-150, 300),
            'title_1': 'Prêmio de inflação implícita (18M)',
            'title_2': 'Histograma do prêmio de inflação implícita (18M)',
        }, 
        'implicit_2y': { 
            'output_prefix': '6b_',
            'ylim': (-150, 350),
            'title_1': 'Prêmio de inflação implícita (2Y)',
            'title_2': 'Histograma do prêmio de inflação implícita (2Y)',
        },
        'target_implicit_1y': { 
            'output_prefix': '6c_',
            'ylim': (-300, 500),
            'title_1': 'Prêmio de inflação mercado vs meta (1Y)',
            'title_2': 'Histograma do prêmio de inflação mercado vs meta (1Y)',
        },
        'target_implicit_2y': { 
            'output_prefix': '6d_',
            'ylim': (-300, 500),
            'title_1': 'Prêmio de inflação mercado vs meta (2Y)',
            'title_2': 'Histograma do prêmio de inflação mercado vs meta (2Y)',
        },
        'flat_6m-selic': { 
            'output_prefix': '7_',
            'ylim': (-200, 200),
            'title_1': 'Inclinação SEM subtração focus (6M-Selic)',
            'title_2': 'Histograma da inclinação SEM subtração focus (6M-Selic)',
        },
        'flat_1y-selic': { 
            'output_prefix': '8_',
            'ylim': (-200, 300),
            'title_1': 'Inclinação SEM subtração focus (1Y-Selic)',
            'title_2': 'Histograma da inclinação SEM subtração focus (1Y-Selic)',
        },
        'flat_2y-selic': { 
            'output_prefix': '9_',
            'ylim': (-300, 450),
            'title_1': 'Inclinação SEM subtração focus (2Y-Selic)',
            'title_2': 'Histograma da inclinação SEM subtração focus (2Y-Selic)',
        },
        'flat_2y-1y': { 
            'output_prefix': '10_',
            'ylim': (-150, 300),
            'title_1': 'Inclinação SEM subtração focus (2Y-1Y)',
            'title_2': 'Histograma da inclinação SEM subtração focus (2Y-1Y)',
        },
        'flat_5y-2y': { 
            'output_prefix': '11_',
            'ylim': (-150, 300),
            'title_1': 'Inclinação SEM subtração focus (5Y-2Y)',
            'title_2': 'Histograma da inclinação SEM subtração focus (5Y-2Y)',
        },
        'market_vs_realized_6m': { 
            'output_prefix': '12_',
            'ylim': (-100, 300),
            'title_1': 'Prêmio mercado vs realizado (6M)',
            'title_2': 'Histograma da prêmio mercado vs realizado (6M)',
        },
        'market_vs_realized_1y': { 
            'output_prefix': '13_',
            'ylim': (-150, 500),
            'title_1': 'Prêmio mercado vs realizado (1Y)',
            'title_2': 'Histograma da prêmio mercado vs realizado (1Y)',
        },
        'market_vs_realized_2y': { 
            'output_prefix': '14_',
            'ylim': (-250,650),
            'title_1': 'Prêmio mercado vs realizado (2Y)',
            'title_2': 'Histograma da prêmio mercado vs realizado (2Y)',
        },
        'market_vs_realized_5y': { 
            'output_prefix': '15_',
            'ylim': (-300, 900),
            'title_1': 'Prêmio mercado vs realizado (5Y)',
            'title_2': 'Histograma da prêmio mercado vs realizado (5Y)',
        },
    }

    for column in plot_dict.keys():
        print("Plotting results for %s" % column)
        time_plot.plot(premia, stats, copom, plot_dict, column)
        plt.savefig("%s/%sa_%s.png" % ( output_folder, plot_dict[column]['output_prefix'], column))
        plt.close()

        hist_plot.plot_2(premia, stats, copom, plot_dict, column)
        plt.savefig("%s/%sb_%s.png" % ( output_folder, plot_dict[column]['output_prefix'], column))
        plt.close()

        hist_plot.plot(premia, stats, copom, plot_dict, column)
        plt.savefig("%s/%sb2_%s.png" % ( output_folder, plot_dict[column]['output_prefix'], column))
        plt.close()

    print("Exporting results tables")
    stat_row_dict = {
        'Max (> p95 média)': 'max', 
        'Mín (< p5 média)': 'min',  
        'Média': 'mean', 
        'Mediana': 'median', 
        'Desv. Padrão': 'std', 
        'Último prêmio': 'last_x', 
        'Última data': 'last_t',
    }
    stat_utils.export_stat( 
        stats,
        "%s/di.xlsx" % ( output_folder ),
        stat_row_dict,
        {
            '6M \n Todos': ('all', '6M'), 
            '6M \n Corte': ('cut', '6M'),
            '6M \n Manut': ('manut', '6M'),
            '6M \n Hike': ('hike', '6M'),
            '1Y \n Todos': ('all', '1Y'),
            '1Y \n Corte': ('cut', '1Y'),
            '1Y \n Manut': ('manut', '1Y'),
            '1Y \n Hike': ('hike', '1Y'),
            '18M \n Todos': ('all', '18M'),
            '18M \n Corte': ('cut', '18M'),
            '18M \n Manut': ('manut', '18M'),
            '18M \n Hike': ('hike', '18M'),
            '2Y \n Todos': ('all', '2Y'),
            '2Y \n Corte': ('cut', '2Y'),
            '2Y \n Manut': ('manut', '2Y'),
            '2Y \n Hike': ('hike', '2Y'),
        }
    )
    stat_utils.export_stat( 
        stats,
        "%s/steepness.xlsx" % ( output_folder ),
        stat_row_dict,
        {
            '2-1 \n Todos': ('all', '2Y-1Y'), 
            '2-1 \n Corte': ('cut', '2Y-1Y'),
            '2-1 \n Manut': ('manut', '2Y-1Y'),
            '2-1 \n Hike': ('hike', '2Y-1Y'),

            '5-2 \n Todos': ('all', '5Y-2Y'),
            '5-2 \n Corte': ('cut', '5Y-2Y'),
            '5-2 \n Manut': ('manut', '5Y-2Y'),
            '5-2 \n Hike': ('hike', '5Y-2Y'),
        }
    )
    stat_utils.export_stat( 
        stats,
        "%s/implicit_6m.xlsx" % ( output_folder ),
        stat_row_dict,
        {
            'Todos': ('all', 'implicit_6m'), 
            'Corte': ('cut', 'implicit_6m'),
            'Manut': ('manut', 'implicit_6m'),
            'Hike': ('hike', 'implicit_6m'),
        }
    )
    stat_utils.export_stat( 
        stats,
        "%s/implicit_1y.xlsx" % ( output_folder ),
        stat_row_dict,
        {
            'Todos': ('all', 'implicit_1y'), 
            'Corte': ('cut', 'implicit_1y'),
            'Manut': ('manut', 'implicit_1y'),
            'Hike': ('hike', 'implicit_1y'),
        }
    )
    stat_utils.export_stat( 
        stats,
        "%s/implicit_18m.xlsx" % ( output_folder ),
        stat_row_dict,
        {
            'Todos': ('all', 'implicit_18m'), 
            'Corte': ('cut', 'implicit_18m'),
            'Manut': ('manut', 'implicit_18m'),
            'Hike': ('hike', 'implicit_18m'),
        }
    )
    stat_utils.export_stat( 
        stats,
        "%s/implicit_2y.xlsx" % ( output_folder ),
        stat_row_dict,
        {
            'Todos': ('all', 'implicit_2y'), 
            'Corte': ('cut', 'implicit_2y'),
            'Manut': ('manut', 'implicit_2y'),
            'Hike': ('hike', 'implicit_2y'),
        }
    )
    stat_utils.export_stat( 
        stats,
        "%s/target_implicit_1y.xlsx" % ( output_folder ),
        stat_row_dict,
        {
            'Todos': ('all', 'target_implicit_1y'), 
            'Corte': ('cut', 'target_implicit_1y'),
            'Manut': ('manut', 'target_implicit_1y'),
            'Hike': ('hike', 'target_implicit_1y'),
        }
    )
    stat_utils.export_stat( 
        stats,
        "%s/target_implicit_2y.xlsx" % ( output_folder ),
        stat_row_dict,
        {
            'Todos': ('all', 'target_implicit_2y'), 
            'Corte': ('cut', 'target_implicit_2y'),
            'Manut': ('manut', 'target_implicit_2y'),
            'Hike': ('hike', 'target_implicit_2y'),
        }
    )
    stat_utils.export_stat( 
        stats,
        "%s/flat_vs_selic.xlsx" % ( output_folder ),
        stat_row_dict,
        {
            '6M \n Todos': ('all', 'flat_6m-selic'), 
            '6M \n Corte': ('cut', 'flat_6m-selic'),
            '6M \n Manut': ('manut', 'flat_6m-selic'),
            '6M \n Hike': ('hike', 'flat_6m-selic'),

            '1Y \n Todos': ('all', 'flat_1y-selic'), 
            '1Y \n Corte': ('cut', 'flat_1y-selic'),
            '1Y \n Manut': ('manut', 'flat_1y-selic'),
            '1Y \n Hike': ('hike', 'flat_1y-selic'),

            '2Y \n Todos': ('all', 'flat_2y-selic'), 
            '2Y \n Corte': ('cut', 'flat_2y-selic'),
            '2Y \n Manut': ('manut', 'flat_2y-selic'),
            '2Y \n Hike': ('hike', 'flat_2y-selic'),
        }
    )

    stat_utils.export_stat( 
        stats,
        "%s/flat_steepness.xlsx" % ( output_folder ),
        stat_row_dict,
        {
            '2-1 \n Todos': ('all', 'flat_2y-1y'), 
            '2-1 \n Corte': ('cut', 'flat_2y-1y'),
            '2-1 \n Manut': ('manut', 'flat_2y-1y'),
            '2-1 \n Hike': ('hike', 'flat_2y-1y'),
            
            '5-2 \n Todos': ('all', 'flat_5y-2y'), 
            '5-2 \n Corte': ('cut', 'flat_5y-2y'),
            '5-2 \n Manut': ('manut', 'flat_5y-2y'),
            '5-2 \n Hike': ('hike', 'flat_5y-2y'),
        }
    )

    stat_utils.export_stat( 
        stats,
        "%s/market_vs_realized.xlsx" % ( output_folder ),
        stat_row_dict,
        {
            '6M \n Todos': ('all',   'market_vs_realized_6m'), 
            '6M \n Corte': ('cut',   'market_vs_realized_6m'),
            '6M \n Manut': ('manut', 'market_vs_realized_6m'),
            '6M \n Hike': ('hike',   'market_vs_realized_6m'),

            '1y \n Todos': ('all',   'market_vs_realized_1y'), 
            '1y \n Corte': ('cut',   'market_vs_realized_1y'),
            '1y \n Manut': ('manut', 'market_vs_realized_1y'),
            '1y \n Hike': ('hike',   'market_vs_realized_1y'),

            '2y \n Todos': ('all',   'market_vs_realized_2y'), 
            '2y \n Corte': ('cut',   'market_vs_realized_2y'),
            '2y \n Manut': ('manut', 'market_vs_realized_2y'),
            '2y \n Hike': ('hike',   'market_vs_realized_2y'),

            '5y \n Todos': ('all',   'market_vs_realized_5y'), 
            '5y \n Corte': ('cut',   'market_vs_realized_5y'),
            '5y \n Manut': ('manut', 'market_vs_realized_5y'),
            '5y \n Hike': ('hike',   'market_vs_realized_5y'),
        }
    )

if __name__ == '__main__':
    main()