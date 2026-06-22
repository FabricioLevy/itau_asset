import pandas as pd
import datetime

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import adjustText

import sys
sys.path.insert(1, '../../risk_report/src')
import fund_utils as fu
import fund_data


def main(data, str_tree='Risk'):
    #%%
    dfPlot = -10_000 * data._dic_var[str_tree].join(data._dic_var['Fund']).fillna(0)
    dfPlot = dfPlot.drop(datetime.date(2020, 5, 29))
    dfPlot = dfPlot.join(pd.DataFrame(1 - (dfPlot['Fund'] / dfPlot.drop('Fund', axis=1).sum(axis=1)), 
                         columns=['DiversificationRatio']))
    
    color1, color2 = fu.color_palette[0:2]
    fig, ax = plt.subplots(1,1)
    fig.tight_layout(h_pad=0, w_pad=0)
    for y, c in zip([2020, 2021, 2022], fu.color_palette[1:]):
        dfTemp = dfPlot.loc[datetime.date(y,1,1):datetime.date(y,12,31)]
        ax.scatter(dfTemp['DiversificationRatio'], dfTemp['Fund'], marker='.', color=c, label=y)
        
    ax.set_xlim(left=0, right=1)
    ax.grid(ls='--')
    ax.set_ylabel('VaR (BPs)')
    ax.set_xlabel('Diversif. Coef. (%)')
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    ax.legend(loc=5)
    
    txts = []
    for dti in dfPlot.index[-6:]:
        ax.scatter([dfPlot.loc[dti, 'DiversificationRatio']], 
                    [dfPlot.loc[dti, 'Fund']],
                    marker='o',
                    color='tomato',
                    alpha=0.8)
        txts.append(ax.text(dfPlot.loc[dti, 'DiversificationRatio'],
                            dfPlot.loc[dti, 'Fund'],
                            f"{dti:%d%b%y}"))
        
    
    ax.annotate(r'$\delta=1-\frac{VaR_{fundo}}{\sum{VaR_{fator}}}$', xy=(0, 0), xycoords='data',
                  xytext=(0.82, 0.88), ha='center',
                  bbox = dict(boxstyle="round", fc="w", ec="0.5", alpha=0.9),
                  textcoords='axes fraction', 
                  fontweight='bold',
                  fontsize=16)
    
    adjustText.adjust_text(txts, 
                           dfPlot['DiversificationRatio'].values,
                           dfPlot['Fund'].values,
                           ax=ax, arrowprops=dict(arrowstyle="-", color='k', lw=1))
    plt.show()
    #%%
    return fig



#%%
if __name__ == "__main__":

    dt, str_fund = fu.get_config(['dt', 'str_fund'])
    nav = fu.get_NAV(dt, str_fund)
    
    str_path = "../output/temp_figs/"
   
    data = fund_data.db_data(dt, str_fund, verbose=True)    

    f = main(data)
    f.set_size_inches(6, 6)
    fig_file = f"../tex/{dt:%Y_%m_%d}/figuras/{dt:%Y%m%d}_diversification.pdf"
    # f.savefig(fig_file, bbox_inches = 'tight', pad_inches = 0)
    
    f = main(data, 'Traders')
    f.set_size_inches(6, 6)
    fig_file = f"../tex/{dt:%Y_%m_%d}/figuras/{dt:%Y%m%d}_diversification_PM.pdf"
    # f.savefig(fig_file, bbox_inches = 'tight', pad_inches = 0)
    