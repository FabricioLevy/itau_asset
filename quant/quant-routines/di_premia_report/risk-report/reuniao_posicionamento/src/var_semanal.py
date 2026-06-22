import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

import sys
sys.path.insert(1, '../../risk_report/src')
import fund_data
import fund_utils as fu

def main(data, dt_1w):
#%%    
    dt = data._dt
    figs = []
    for tree in ['Geography', 'Risk']:
    
        dfVaR = data._dic_var[tree].loc[dt_1w:dt].join(data._dic_var['Fund']).fillna(0) * -10_000
        
    
        for del_col in ['ALL', 'TRANSF']:
            if del_col in dfVaR.columns:
                dfVaR = dfVaR.drop(del_col, axis=1)
            
        dfFund = pd.DataFrame(dfVaR['Fund'])
        sorted_cols = list(dfVaR.mean().sort_values(ascending=False).index)
        sorted_cols.remove('Fund')
          
        data_perc = dfVaR[sorted_cols].divide(dfVaR[sorted_cols].sum(axis=1), axis=0)
        data_perc['Day'] = ['{:%d-%b}'.format(i) for i in data_perc.index]
        data_perc.set_index('Day', inplace=True)
        
        dfFund['Day'] = ['{:%d-%b}'.format(i) for i in dfFund.index]
        dfFund.set_index('Day', inplace=True)
    
        color_palette =['teal', '#2F788D', 'royalblue', 'cornflowerblue', 'slategrey', 'silver', 'lightgrey']
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4), gridspec_kw = {'width_ratios':[3,  2]})
        fig.tight_layout()
        fig.subplots_adjust(wspace=0.1, hspace=0.05)
        
        # data_perc.plot.area(ax=ax1, color=color_palette, legend=False)
        ax1.stackplot(data_perc.index, [data_perc[i].values for i in data_perc.columns],\
                      edgecolor='w',colors=color_palette)
        
        axV = ax1.twinx()    
        axV.plot(dfFund.index, dfFund['Fund'], ls='--',marker='s', lw=3,color='darkred', label='VaR Total') 
        axV.set_ylim(bottom=0)
        axV.set_ylabel('VaR (BPs)')
        axV.legend(loc='lower right')
        for i, ha in zip([0, -1],['left','right']):
            axV.text(dfFund.index[i], dfFund['Fund'].iloc[i], 
                     '\n{:2.1f}'.format(dfFund['Fund'].iloc[i]), color='darkred',
                     ha=ha, va='top', fontweight='bold', fontsize=12 )
        
        
        ax1.set_title('Composição do VaR')
        ax1.set_xlim(left=data_perc.index[0], right=data_perc.index[-1])
        
        ax1.set_ylim((0,1))
        ax1.legend(ncol=2, labels=data_perc.columns, loc='lower left')
        ax1.grid(ls='--', alpha=0.5)
        ax1.set_yticklabels(['{:2.0%}'.format(x) for x in ax1.get_yticks()])
        
        
        def absolute_value(val):
            return np.round(val/100.*dfVaR[sorted_cols].mean().sum(), 1)
        
        axT = dfVaR[sorted_cols].mean().plot.pie(ax=ax2,  shadow=False, fontsize=15, autopct=absolute_value, \
                              colors=color_palette, labels=None, \
                              wedgeprops={"edgecolor":"white",'linewidth': 1,
                            'linestyle': 'solid', 'antialiased': True})
        
        for t in ax2.texts:
            if t.get_text() != '' :
                if float(t.get_text())/dfVaR[sorted_cols].mean().sum() < 0.02:
                    t.set_text('')    
        
        ax2.set_title('Média Semanal do VaR (BPs)')
        ax2.set_ylabel('')
        ax2.legend(loc='lower center', ncol=2, fontsize=9, bbox_to_anchor=(0.5, -0.1),
                   labels=['{} ({:2.1f})'.format(i, dfVaR[sorted_cols].mean().loc[i]) for i in sorted_cols if i!='Fund']) 
        
        plt.show()
        figs.append(fig)
    
#%%    
    color1, color2 = fu.color_palette[0:2]
    fig, axes = plt.subplots(nrows=1, ncols=1, figsize=(7, 4),  sharey=True)
    fig.tight_layout()
 
    dfTemp = dfVaR.loc[[dt, dt_1w]].T
    if 'TRANSF' in dfTemp.index:
        dfTemp = dfTemp.drop('TRANSF')
    x = np.arange(len(dfTemp.index))
    for dt_i, w, s, f, c in zip([dt, dt_1w], [-.25, .125], [.5, .25], [13, 12], [color1, color2]):
        rects = axes.bar(x+w, height=dfTemp[dt_i], width=s, label='{:%d-%b}'.format(dt_i), zorder=3, color=c)
        for rect in rects:
            height = rect.get_height()
            axes.annotate('{:2.0f}'.format(height),
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', 
                    fontsize=f, zorder=5,
                    fontweight=('bold' if dt_i==dt else 'normal'))
            
    axes.grid(ls='--', axis='y')
    axes.axhline(180, label='Limit', ls='-', lw=2, color='r', zorder=4)
    axes.axhline(60, label='Target', ls='--', lw=1.5, color='r', zorder=4)
    warning_value = 144
    if dfTemp.loc['Fund', dt]>warning_value:
        axes.axhspan(warning_value, 180, facecolor='gold', alpha=0.4)
 
    axes.set_ylim(top=max(200, dfTemp.max().max()*1.05))
    axes.set_xlabel('')
    axes.set_xticks(x)
    axes.tick_params(labelsize=14)   
    dfTemp.rename(index={'CUPOM CAMBIAL':'CUPOM\nCAMBIAL'},inplace=True)        
    axes.set_xticklabels(dfTemp.index, rotation=90)
    axes.get_xticklabels()[-1].set_weight("bold")
    axes.set_ylabel('VaR (BPs)', fontsize=13)
    axes.legend(loc=2, fontsize=12)

    plt.show() 
    figs.append(fig)
#%%    
    return figs
    
#%%
if __name__ == "__main__":

    dt, str_fund, dt_1w = fu.get_config(['dt', 'str_fund', 'dt_1w'])
        
    str_path = "../output/temp_figs/"
    data = fund_data.db_data(dt, str_fund, verbose=True)
    
    f1, f2, f3 = main(data, dt_1w)
    fig_file = f"../tex/{dt:%Y_%m_%d}/figuras/{dt:%Y%m%d}_hist_var.pdf"
    f1.savefig(fig_file, bbox_inches = "tight", pad_inches = 0)
    
    fig_file = f"../tex/{dt:%Y_%m_%d}/figuras/{dt:%Y%m%d}_hist_var_geo.pdf"
    f2.savefig(fig_file, bbox_inches = "tight", pad_inches = 0)
    
    fig_file = f"../tex/{dt:%Y_%m_%d}/figuras/{dt:%Y%m%d}_var_breakdown.pdf"
    f3.savefig(fig_file, bbox_inches = "tight", pad_inches = 0)
    
    