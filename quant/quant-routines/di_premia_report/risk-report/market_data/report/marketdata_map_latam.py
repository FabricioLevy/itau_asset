import pandas as pd
import numpy as np
import datetime
import timeit
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as shpreader

from a1db.a1sql import SQLConnection

 



#%%
def plot_map (dt):
    #%%
    connection = SQLConnection().get_connection()
    
    dic_country = {'MEX': ['MEXBOL', 'USDMXN', 'darkgreen', (-60, 25), (0.54 ,0.71)],
                   'COL': ['COLCAP', 'USDCOP', 'gold', (-42, 5), (0.58 ,0.52)],
                   'CHL': ['IPSA', 'USDCLP', 'darkred', (-100, -30), (0.41 ,0.283)]}

    ## Index and Currencies    
    str_sql = f"""
    SELECT ts.entity_id,[date_reference],[value]
      FROM [quant].[time_series_value] tsv 
    	INNER JOIN quant.time_series ts ON tsv.series_id =ts.id
      WHERE ts.id in (899, 82, 902, 81, 901, 79) 
      and date_reference between '{datetime.date(dt.year-1, 1, 1):%Y-%m-%d}' and '{dt:%Y-%m-%d}'
      """
    dfIndex = pd.read_sql(str_sql, 
                          connection).pivot(index='date_reference', 
                                            columns='entity_id',
                                            values='value').sort_index().fillna(method='ffill')
    
    dfIndex[[i[1] for i in dic_country.values()]] = 1 / (dfIndex[[i[1] for i in dic_country.values()]])

    fig = plt.figure(figsize=(12, 5.25))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
    ax.set_extent([-130, -17.5, -60, 35], crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.LAND, color='#323E48', alpha=0.7)
    ax.add_feature(cfeature.OCEAN, color='lightcyan')
    ax.add_feature(cfeature.COASTLINE)
    
    shpfilename = shpreader.natural_earth(resolution='110m',
                                          category='cultural',
                                          name='admin_0_countries')
    reader = shpreader.Reader(shpfilename)
    countries = reader.records()    
    for country in countries:       
        ADM0_A3 = country.attributes['ADM0_A3']
        if ADM0_A3 in dic_country.keys():
            color = dic_country[ADM0_A3][2]
            ax.add_geometries([country.geometry], 
                              ccrs.PlateCarree(),
                              facecolor=color,
                              edgecolor='#000000',
                              linewidth=1.5)    

    dfRet = (dfIndex/dfIndex.iloc[-22]-1).iloc[-22:]
    ret1d = dfIndex.iloc[-1]/dfIndex.iloc[-2]-1
    ret1m = dfIndex.iloc[-1]/dfIndex.iloc[-22]-1
    for k, (stock, fx, color, xy1, xy2) in dic_country.items():
        dfPlot = pd.DataFrame(ret1d[[stock, fx]].values, index=[stock, fx[3:]], columns=['1D'])
        ax1 = fig.add_axes([xy2[0], xy2[1], 0.1, 0.1])
        ax1.set_title(k, fontweight='bold')
        ax1.patch.set_alpha(0.4)
        ax1.patch.set_facecolor(color)
        # dfPlot.plot.barh(ax=ax1, legend=False, color=(dfPlot['1D'] > 0).map({True:'#28829B', False: 'tomato'}))
        ax1.barh(dfPlot['1D'].index, dfPlot['1D'], color=(dfPlot['1D'] > 0).map({True: 'royalblue', False: 'tomato'}))
        
        ax1.set_xticks([])
        ax1.axvline(0, c='k', ls='--', lw=0.5)
        for i, v in enumerate(ret1d[[stock, fx]].values):
            ax1.text(0, i, f'{v:+7.2%}', va='center', color='r' if v<0 else 'k', fontweight='bold')
        ax1.set_xlim((-0.04, 0.05))
        # ax1.set_yticklabels(ax1.get_yticklabels(), fontweight='bold', fontsize='small')
        # table = f"{k}\n{'ret(%)':12}{'1D':7}{'1M':>7}\n{'FX=':>6}{ret1d[fx]:>+8.2%}{ret1m[fx]:>+8.1%}\nStock={ret1d[stock]:>+8.2%}{ret1m[stock]:>+8.1%}"
        # ax.annotate(table,
        #                 xy=xy, xycoords="data", va="center", ha="center", fontweight='bold',
        #               bbox=dict(boxstyle="round", fc=color)
    plt.show()
        #%%
    # adjust_text(texts)    #%%
    return fig

#%%
if __name__=="__main__":
    dt = datetime.date(2022, 6, 8)
    plot_map(dt)