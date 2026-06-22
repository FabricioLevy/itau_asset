import pandas as pd
import numpy as np
import squarify
import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import fund_utils as fu

def main(dt, str_fund):
    #%%
    _, connection = fu.get_DB_conn('prod')    
    str_sql = f"""
                SELECT n.[date_reference],n.[trading_desk],[offshore_vehicle],
                    [position_offshore_brl],n.NAV
                FROM [intrag].[fund_offshore_position] fo INNER JOIN middle.NAV n
                    ON fo.date_reference = n.date_reference 
                      AND fo.trading_desk = n.trading_desk
                WHERE fo. offshore_vehicle = '{str_fund}'
                     AND fo.date_reference <= '{dt:%Y-%m-%d}'
         """
    df = pd.read_sql(str_sql, connection)
    
    dfOffshoreComposition = df.pivot(index='date_reference',
                                     columns='trading_desk',
                                     values='position_offshore_brl')        
    dfNAVOnshore = df.pivot(index='date_reference',
                            columns='trading_desk',
                            values='NAV')

    str_sql = f"""
                SELECT [date_reference],[NAV],[share]
                    FROM [middle].[NAV]
                    WHERE trading_desk =  '{str_fund}'
                     AND date_reference <= '{dt:%Y-%m-%d}'
         """
    dfNAV = pd.read_sql(str_sql, connection, index_col='date_reference')
    dfNAV['Return'] = dfNAV['share'].pct_change().fillna(0)
    dfNAV['AcumRet'] = (1 + dfNAV['Return']).cumprod() - 1
    dfNAV['DD'] = (1+dfNAV['AcumRet']) / (1+dfNAV['AcumRet'].expanding().max()) - 1
    #%%
    dic_eom = fu.get_endOfMonths(dt, dfNAV.index[0], True)
    dfNAV_Change = pd.DataFrame(index=dic_eom.keys(), columns=['Monthly_Change'])
    for m, (dt1, dt2) in dic_eom.items():
        dfNAV_Change.loc[m, 'Monthly_Change'] = dfNAV.loc[dt2, 'NAV'] / dfNAV.loc[dt1, 'NAV'] - 1
    
    dfNAV_Change['3M_Change'] = (dfNAV_Change['Monthly_Change']+1).rolling(3).agg(lambda x: x.prod())-1
    dfNAV_Change['12M_Change'] = (dfNAV_Change['Monthly_Change']+1).rolling(12).agg(lambda x: x.prod())-1
    
    #%%
    nav_off = dfNAV.loc[dt, 'NAV']
    nav_on = dfNAVOnshore.iloc[-1].sort_values(ascending=False)
    figNAV, (axon, axoff) = plt.subplots(1, 2, 
                             sharex=True, 
                             figsize=(4, 2),
                             constrained_layout=True,
                             gridspec_kw = {'width_ratios':[1, 3]})
    
    text_kwargs = {'fontweight':'bold',
                   'fontsize':'9'}
    
    squarify.plot(sizes=[1], 
                  label=[f"USD {nav_off/(10**6):1,.1f}M"], 
                  color='royalblue',
                  text_kwargs =text_kwargs,
                  ax=axon)
    axon.axis('off')
    axon.set_title(str_fund, 
                   fontweight='bold',
                   fontsize=11)
    
    squarify.plot(sizes = nav_on,
                  label = [f"{i/(10**6):1,.1f}M" for i in nav_on], 
                  color = fu.color_palette[1:], 
                  pad=0.1,
                  text_kwargs = text_kwargs,
                  ax=axoff)
    axoff.axis('off')
    axoff.set_title(f"Total Onshore Funds\nBRL {nav_on.sum()/(10**6):1,.1f}M", 
                    fontweight='bold',
                    fontsize=11)
    plt.show()
    #%%
    color1, color2 = fu.color_palette[0:2]
    locator = mdates.AutoDateLocator(minticks=3, 
                                     maxticks=6)
    formatter = mdates.ConciseDateFormatter(locator, 
                                            formats=['%b%y', '%b%y', '%d%b', '', '', ''], 
                                            show_offset=False)
    
    fig1, axes = plt.subplots(3, 1, 
                             sharex=True, 
                             figsize=(5.5, 5.4),
                             constrained_layout=True,
                             gridspec_kw = {'height_ratios':[5, 3, 3]})
    
    
    ax = axes[0]
    # ax.set_title(str_fund, fontweight='bold')
    ax.plot(dfNAV.index, dfNAV['AcumRet'], lw=2, color=color1)
    ax.axhline(0, lw=0.5, c='k')
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1))
    ax.set_ylabel('Acum Return (%)')
    
    ax = axes[1]
    ax.plot(dfNAV.index, dfNAV['DD'], c='r')
    ax.fill_between(dfNAV.index, 0, dfNAV['DD'], color='r', alpha=0.4)
    ax.set_ylim(top=0)    
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1))
    ax.set_ylabel('Drawdown (%)')
    
    ax = axes[2]
    ax.plot(dfNAV.index, dfNAV['NAV'], c=color2)
    ax.fill_between(dfNAV.index, 0, dfNAV['NAV'], color=color2, alpha=0.6)
    ax.set_ylim(bottom=0)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)   
    ax.set_xlim(left=dfNAV.index[0], right=dfNAV.index[-1])
    ax.set_ylabel('NAV (m USD)')
    ax.yaxis.set_major_locator(mticker.FixedLocator(ax.get_yticks().tolist()))
    ax.set_yticklabels(["{:2,.0f}".format(i/10**6) for i in ax.get_yticks()])
    
    
    for shift, col in zip([-2, -4, -13], ['Monthly_Change', '3M_Change', '12M_Change']):
        dti = dfNAV_Change.index[shift]
        ax.axvline(dti, ls='--', lw=2, c='k')
        ax.text(dti, dfNAV.loc[dti, 'NAV'], f"{shift+1}M:{dfNAV_Change.loc[dt, col]:+2.1%}",
                fontweight='bold', color='r' if dfNAV_Change.loc[dt, col]<0 else 'k',
                va='top', ha='right')
    
    
    for ax in axes.flatten():
        ax.grid(ls='--')
    
    fig1.align_ylabels()
      
    plt.show()
    
    #%%
    fig2, (ax1, ax2) = plt.subplots(2, 1, 
                                    figsize=(3.2, 4.2),
                                    constrained_layout=True,
                                    gridspec_kw = {'height_ratios': [5, 3]})
    # fig2.tight_layout(h_pad=2)
    sizes = dfOffshoreComposition.iloc[-1].sort_values(ascending=False)
    explode = [0.05] * len(sizes)
    ax1.set_title("Actual Composition", fontweight='bold', fontsize='x-large')
    ax1.pie(sizes.values, 
           explode=explode, 
           labels=sizes.index, 
           colors = fu.color_palette[1:],
           autopct='%1.2g%%',
           shadow=False,
           startangle=0,
           textprops={'weight':'bold'})
    ax1.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
    
    sizes = dfNAVOnshore.iloc[-1].sort_values(ascending=False)
    ax2.set_title("Fair Composition", fontweight='bold', fontsize='x-large')
    ax2.pie(sizes.values, 
           explode=explode, 
           labels=sizes.index, 
           colors = fu.color_palette[1:],
           autopct='%1.2g%%',
           shadow=False,
           startangle=0,
           textprops={'weight':'bold'})
    ax2.axis('equal')  
    
    plt.show()
    #%%
    return [fig1, fig2, figNAV]
    
#%%
if __name__ == "__main__":
    
    dt, str_fund = fu.get_config(['dt', 'str_fund_offshore'])
    
    fig1, fig2, figNAV = main(dt, str_fund) 
    #%%
    fig_file = '../output/temp_figs/offshore/{:%Y%m%d}_{}_performance.pdf'.format(dt, str_fund)
    # fig1.set_figwidth(8)
    # fig1.set_figheight(8.4, False)
    fig1.savefig(fig_file,
                bbox_inches = 'tight', #facecolor='silver',
                pad_inches = 0)
    
    
    fig_file = '../output/temp_figs/offshore/{:%Y%m%d}_{}_composition.pdf'.format(dt, str_fund)
    # fig2.set_figwidth(4)
    # fig2.set_figheight(5.0, False)
    fig2.savefig(fig_file,
                bbox_inches = 'tight', #facecolor='silver',
                pad_inches = 0)  
    
    fig_file = '../output/temp_figs/offshore/{:%Y%m%d}_{}_treemap_nav.pdf'.format(dt, str_fund)
    # fig2.set_figwidth(4)
    # fig2.set_figheight(5.0, False)
    figNAV.savefig(fig_file,
                bbox_inches = 'tight',#facecolor='silver',
                pad_inches = 0) 
    
    