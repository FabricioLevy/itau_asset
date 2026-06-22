# -*- coding: utf-8 -*-
"""
Created on Wed Sep 14 10:24:16 2022

@author: matheus.amaral
"""

import pandas as pd
import numpy as np

from datetime import date
from a1db.a1sql import SQLConnection

import scipy.stats as ss
import matplotlib.pyplot as plt
import sys
sys.path.insert(1, '../../risk_report/src')
import fund_utils as fu
import fund_data as fd

def main(dt,str_fund = 'A1 Master FIM'):
    
    data = 'Traders'
    connection = SQLConnection().get_connection()
    nav = fu.get_NAV(dt, str_fund)
    traders = fu.get_traders(dt)
    
    db = fd.db_data(dt,str_fund)
    
    ic_var = ss.norm.ppf(0.95) 
    
    dfCvar = pd.DataFrame(index = db.get_TraderVaRWeights_byCol().index)       
    
    dfShare = fu.get_DailyRiskShare(dt,str_fund).loc[dt]
    
    
    for trader in traders.keys():
    
        dfPrimitives = db.get_TraderVaRWeights_byCol(trader = trader) / nav
    
        dfCovar = db._dfCovar
        
        cov = dfCovar.values
        
        dfPrimitives[trader] = dfPrimitives.sum(axis = 1)
    
        w = dfPrimitives[trader]
        var = np.sqrt(w.T @ cov @ w) * ic_var * 10_000
        
        beta_cvar = (cov @ w) / (w.T @ cov @ w)
        
        dfCvar[trader] = beta_cvar * var * dfPrimitives[trader] / dfShare.loc[trader]
        
    
    
    str_sql = f"""
            SELECT DISTINCT primitive,
                primitive_class
            FROM lote45.primitive
            """
    primitives = pd.read_sql(str_sql, connection)
    
    # primitives = db._dfPrimitive[['primitive', 'primitive_class']].drop_duplicates()
    
    vega = pd.DataFrame(data = dfCvar[dfCvar.index.str.contains('Vol ')].index.to_list(), columns = ['primitive'])
    
    primitives = primitives.append(vega).fillna('Vega').set_index('primitive')
    
    dfCvar = dfCvar.join(primitives).dropna(subset = 'primitive_class')
    dfPlot = dfCvar.replace({'BRD Rate Curve':'Cupom Cambial',
                    'BRL Rate Curve':'Pre',
                    'Brazil Sovereign Yield':'Pre',
                    'IPCA Coupon':'IPCA',
                    'USA Sovereign Yield':'US Rate',
                    'USD Rate Curve': 'US Rate'}).groupby('primitive_class').sum().sort_index()
    
    
    dfPlot.loc['VaR'] = dfPlot.sum()
    
    n = len(dfPlot.index)
    
    if n>1:
        fig, ax = plt.subplots(nrows=n, ncols=1, figsize=(6, 7), gridspec_kw={'height_ratios': (n-1)*[1]+[1]},\
                               sharey=True, sharex=True)
        plt.tight_layout()
        fig.subplots_adjust(hspace=0.05)
        
        for j, b in enumerate(dfPlot.index):
            dfPlot.loc[b].plot.bar(ax=ax[j], legend=False, zorder=2, stacked=False, \
                               color=fu.color_palette[1], rot=0, subplots=True)
            for i, ccy in enumerate(dfPlot.columns):
                y = float(dfPlot.loc[b,ccy])
                c = 'r' if y<0 else 'k'
                ax[j].text(i, max(0, y), '{:2.1f}'.format(y) if y!=0 else '-', va='bottom',\
                         color=c, ha='center', fontweight='bold', fontsize=11) 
            
            ax[j].set_xticks([], minor=True)
            ax[j].set_yticks([])
            ax[j].grid(ls='--', axis='y')
            ax[j].axhline(0, lw=0.5, c='grey')
            ax[j].set_xlabel('')
            ax[j].set_ylabel(b.replace(' ','\n') if b =='CUPOM CAMBIAL' else b, rotation=0, fontsize=10, ha='right', va='center')
            ax[j].set_title('')
            ax[j].tick_params(labelsize=11)
        ax[0].set_ylim(top=max(0.1, 2*float(dfPlot.max().max())), bottom=min(-.1, 1.1*float(dfPlot.min().min())))
        ax[0].set_yticklabels([])
        ax[j].set_ylabel(b.replace(' ','\n'), rotation=0, fontweight='bold', fontsize=11, ha='right', va='center')
        ax[j].set_facecolor('lightgrey')
        
        for i, t in enumerate(ax[j].get_xticklabels()):
            if t.get_text() in ['USD', 'BRL']:
                # t.set_color(color1)
                t.set_fontweight('bold') 
                
        fig_file = fig_file = f"../tex/{dt:%Y_%m_%d}/figuras/{dt:%Y%m%d}_CVaR_Braekdown.pdf"
        fig.savefig(fig_file, bbox_inches = "tight")
        plt.show()
        
    
#%%

if __name__ == '__main__':
    
   dt = date(2022,9,16)
   
   main(dt)
