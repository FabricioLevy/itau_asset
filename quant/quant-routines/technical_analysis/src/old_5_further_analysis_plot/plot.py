import matplotlib.pyplot as plt

def plot(results, window_size = 756):
    ax1 = None
    for key_i, key in enumerate(results.keys()):
        ax1 = plt.subplot( len(results.keys()), 1, key_i + 1, sharex=ax1)
        plt.plot(results[key].mean(axis=1))
        plt.ylabel(key)
        plt.grid()
        if key_i == 0:
            plt.title('Regression mean with window size = %d' % window_size) 
    plt.subplots_adjust(wspace=0, hspace=0.2)
    plt.tight_layout()