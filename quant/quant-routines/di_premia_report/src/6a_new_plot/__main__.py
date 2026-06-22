import pandas as pd
import matplotlib.pyplot as plt
import pickle
from plot import custom_plot
import os

def main():
    INPUT_PATH = '../../output/6_plot'
    OUTPUT_PATH = INPUT_PATH

    # Load data
    with open('%s/stats.pkl' % INPUT_PATH, 'rb') as handle:
        stats = pickle.load(handle)

    print(stats['all']['min'])

    custom_plot(
        stats,
        [
            (6, '6M', '6M'),
            (12,'1Y','1Y'),
            (18,'18M','18M'),
            (24,'2Y','2Y'),        
            (60,'5Y','5Y'),
        ],
        'Prêmio DI'
    )
    plt.savefig('%s/di_cross_section.png' % OUTPUT_PATH)
    plt.close()

    custom_plot(
        stats,
        [
            (6, 'implicit_6m', '6M'),
            (12,'implicit_1y', '1Y'),
            (18,'implicit_18m', '18M'),
            (24,'implicit_2y', '2Y'),
        ],
        'Prêmio de implícita'
    )
    plt.savefig('%s/implicit_cross_section.png' % OUTPUT_PATH)
    plt.close()

if __name__ == "__main__":
    main()