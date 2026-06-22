import datetime
import pandas as pd

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import adjustText

import sys
sys.path.insert(1, '../../risk_report/src')
import fund_utils as fu
import fund_data


#%%#################
def main(data, figsize=(12, 6)):
#%%
    _, connection = fu.get_DB_conn('prod')    
    str_sql = """
                SELECT [cnpj_fundo_master],[plot_name]
                FROM [cvm].[fund_peers]
                WHERE peer_group = 'WeeklyComparison'
            """
    dfFundos = pd.read_sql(str_sql, connection, index_col='cnpj_fundo_master')

    str_sql =f"""
                SELECT [cnpj_fundo],[date_reference],[quota_value]
                FROM [cvm].[fundo_investimento_informe_diario]
                where cnpj_fundo in ({",".join([str(i) for i in dfFundos.index])}) 
                and date_reference>='2020-4-1'
            """
    dfPrice = pd.read_sql(str_sql, 
                          connection).pivot(index='date_reference',
                                            columns='cnpj_fundo',
                                            values='quota_value')

    dfPrice = dfPrice.loc[datetime.date(2022,5,31):]
    # dfPrice = dfPrice.iloc[-64:]
    dfPrice.rename(columns=dfFundos['plot_name'].to_dict(), inplace=True)
    dfPrice = dfPrice.join(data._dfAcumCDI)
    
    dfReturn = dfPrice.pct_change()
    
    dfPnLTrader = data.get_adjusted_trader_pnl() 
    dfTemp = data._risk_share.iloc[-1].sort_values(ascending=False).drop('Fund')
    traders = list(dfTemp[dfTemp!=0].index)
    dfPnLTrader = dfPnLTrader.join(dfReturn['CDI'])
    for t in traders:
        dfPnLTrader[t] += dfReturn['CDI']
    
    dfReturn = dfReturn.join(dfPnLTrader[traders]).fillna(0)
    dfAcumRet = (dfReturn+1).cumprod() - 1
    sorted_cols = dfAcumRet.iloc[-1].sort_values(ascending=False).index
    dfAcumRet = dfAcumRet[sorted_cols]
    ret = dfAcumRet.iloc[-1].to_dict()
    vol = (dfReturn.std() * (252**.5)).to_dict()
    
#%%
    color1, color2 = fu.color_palette[0:2]
    locator = mdates.AutoDateLocator(minticks=2, 
                                     maxticks=6)
    formatter = mdates.ConciseDateFormatter(locator, 
                                            formats=['%b\n%Y', '%b', '%d%b', '%H:%M', '%H:%M', '%S.%f'], 
                                            show_offset=False)
    fig, (ax1, ax2) = plt.subplots(nrows=1, ncols=2, figsize=figsize, \
                                 gridspec_kw = {'width_ratios':[3, 2]},\
                                 sharex=False, sharey=True)
    fig.tight_layout()
    fig.subplots_adjust(wspace=0.02, hspace=0)

    dicColor = {}
    txts = []
    j=0
    for i, c in enumerate(dfAcumRet.columns):
        if c == 'CDI':
            p = ax1.plot(dfAcumRet.index, dfAcumRet[c], lw=2, ls=':', c='k', label=f"{c} ({ret[c]:2.1%})", zorder=4)
            txts.append(ax2.text(vol[c], ret[c], c, color=p[0].get_color(), fontweight='bold', fontsize=10))
        elif c == 'Asset1':
            p = ax1.plot(dfAcumRet.index, dfAcumRet[c], lw=2.5, ls='-.', c=fu.color_palette[0], label=f"{c} ({ret[c]:2.1%})", zorder=4)
            txts.append(ax2.text(vol[c], ret[c], c, color=p[0].get_color(), backgroundcolor='whitesmoke', fontweight='bold', fontsize=11))
        elif c in traders:
            j+=1
            p = ax1.plot(dfAcumRet.index, dfAcumRet[c], color=fu.color_palette[j], lw=2.25, ls='--',
                         label=f"{c} ({ret[c]:2.1%})", zorder=2)  
            txts.append(ax2.text(vol[c], ret[c], c, color=fu.color_palette[j],
                                 fontweight='bold', fontsize=10))
        else:
            p = ax1.plot(dfAcumRet.index, dfAcumRet[c], lw=1.75, label=f"{c} ({ret[c]:2.1%})")
            txts.append(ax2.text(vol[c], ret[c], c, color=p[0].get_color(), fontweight='bold', fontsize=9))
        dicColor[c] = p[0].get_color()
        ax2.scatter([vol[c]], [ret[c]], marker='.', c=[dicColor[c]])

    ax1.set_xlim(left=dfAcumRet.index[0], right=dfAcumRet.index[-1])
    ax1.legend(fontsize=8, loc=2, ncol=2)
    ax1.xaxis.set_major_locator(locator)
    ax1.xaxis.set_minor_locator(mdates.MonthLocator(interval=1))
    ax1.xaxis.set_major_formatter(formatter)  
    ax1.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    ax1.set_title(f"Acum. Return  ({dfPrice.index[0]:%e-%b-%y} ~ {dfPrice.index[-1]:%e-%b-%y})")


    adjustText.adjust_text(txts,ax=ax2, arrowprops=dict(arrowstyle="-", color='k', lw=0.5))
    ax2.xaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    ax2.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    ax2.set_title('Acum. Return x Volatility')
    for ax in (ax1, ax2):
        ax.grid(ls='--', which='both')

    fig.subplots_adjust(bottom=0.05)    
    plt.show()
    #%%
    return fig

if __name__ == "__main__":

    dt , str_fund = fu.get_config(['dt', 'str_fund'])
    nav = fu.get_NAV(dt, str_fund)
    
    str_path = "../output/temp_figs/"
   
    data = fund_data.db_data(dt, str_fund, verbose=True)      
    
    f = main(data)
    fig_file = f"../tex/{dt:%Y_%m_%d}/figuras/{dt:%Y%m%d}_peers_vol.pdf"
    # f.savefig(fig_file, bbox_inches = 'tight', pad_inches = 0)
    
  
