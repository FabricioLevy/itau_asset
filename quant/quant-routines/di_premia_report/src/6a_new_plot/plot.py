import pandas as pd
import matplotlib.pyplot as plt

def custom_plot(stats, info_list, title_prefix):
    copom_dict = {
       -1: 'cut',
       0: 'manut',
       1: 'hike',
    }
    last_copom_type = copom_dict[ stats['all']['last_x']['Copom flag'] ]

    df_dict = {}
    for selector in [
        'all',
        last_copom_type
    ]:
        df = pd.DataFrame()
        for n_month, key, name in info_list:
            df.loc[n_month, 'name'] = name
            df.loc[n_month, '+3s'] = stats[selector]['mean'][key] + 3 * stats[selector]['std'][key]
            df.loc[n_month, '+2s'] = stats[selector]['mean'][key] + 2 * stats[selector]['std'][key]
            df.loc[n_month, '+1s'] = stats[selector]['mean'][key] + 1 * stats[selector]['std'][key]
            df.loc[n_month, 'median'] = stats[selector]['median'][key]
            df.loc[n_month, 'mean'] = stats[selector]['mean'][key]
            df.loc[n_month, '-1s'] = stats[selector]['mean'][key] - 1 * stats[selector]['std'][key]
            df.loc[n_month, '-2s'] = stats[selector]['mean'][key] - 2 * stats[selector]['std'][key]
            df.loc[n_month, '-3s'] = stats[selector]['mean'][key] - 3 * stats[selector]['std'][key]
            df.loc[n_month, 'last'] = stats[selector]['last_x'][key]
            df.loc[n_month, 'max'] = stats[selector]['max'][key]
            df.loc[n_month, 'min'] = stats[selector]['min'][key]
        df_dict[selector] = df

    df = df_dict['all']
    px = 1/plt.rcParams['figure.dpi']
    _, (ax1, ax2) = plt.subplots(2,1, figsize=(800*px,800*px))
    subplot_1(
        df, 
        ax1, 
        title='%s vs todos períodos' % title_prefix,
        legend=False
    )

    df = df_dict[ last_copom_type ]
    copom_dict_2 = {
        'hike': 'hike',
        'cut': 'corte',
        'manut': 'manutenção'
    }
    subplot_1(
        df, 
        ax2, 
        title='%s vs períodos de %s' % (
            title_prefix,
            copom_dict_2[last_copom_type]
        )
    )

def subplot_1(df, ax, title='', legend=True):
    ax.fill_between(df.index, df['+3s'], df['+2s'], alpha=0.1, facecolor='b', label='< 3std')
    ax.fill_between(df.index, df['-3s'], df['-2s'], alpha=0.1, facecolor='b')    
    ax.fill_between(df.index, df['+2s'], df['+1s'], alpha=0.25, facecolor='b', label='< 2std')
    ax.fill_between(df.index, df['-2s'], df['-1s'], alpha=0.25, facecolor='b')    
    ax.fill_between(df.index, df['-1s'], df['+1s'], alpha=0.35, facecolor='b', label='< 1std')
    ax.plot(df['median'], ':b', label='Mediana')
    ax.plot(df['mean'], '-.b', label='Média')
    ax.plot(df['last'], 'o-r', label='Último')
    ax.set_xlim([df.index[0], df.index[-1]])
    ax.set_ylabel('Prêmio (bps)')
    ax.set_title(title)
    ax.set_xticks(df.index) 
    ax.set_xticklabels(df['name'], fontsize=10)
    ax.grid()
    if legend:
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.1), ncol=3)