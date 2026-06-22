# -*- coding: utf-8 -*-
"""
Created on Mon Aug 15 10:52:36 2022

@author: matheus.amaral
"""

import pandas as pd
import numpy as np
import fund_utils as fu
from datetime import date
from a1db.a1sql import SQLConnection
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import matplotlib.gridspec as gridspec
import adjustText



def main(dt):
    str_fund = 'A1 Master FIM'
    data = 'Traders'
    
    connection = SQLConnection().get_connection()
    
    str_sql = f"""
            SELECT b.date_reference,
                b.lote45_product_class,
                b.lote45_product,
                b.book,
                p.risk_product AS product,
                SUM(b.value / n.NAV_D1) AS pnl
            FROM lote45.book_overview b
            INNER JOIN middle.NAV n
                ON b.date_reference = n.date_reference
                AND b.trading_desk = n.trading_desk
            LEFT JOIN lote45.product_class p
                ON p.lote45_product_class = b.lote45_product_class
            WHERE b.date_reference <= '{dt:%Y-%m-%d}'
                AND b.date_reference LIKE '{dt:%Y}%'
                AND b.trading_desk = '{str_fund}'
                AND b.measure = 'PL'
            GROUP BY b.date_reference, b.book,p.risk_product,b.lote45_product,b.lote45_product_class
            ORDER BY b.date_reference
            """
    df = pd.read_sql(str_sql,connection, parse_dates = 'date_reference')
    
    # list_prod = ['TSM US','SWAP CLP','SWAP COP']
    
    # df[df['product'].str.contains('TSM US')]
    # for prod in list_prod:
    #     df.loc[df['product'].str.contains(prod),'product'] = prod
    
    str_sql =  f"""
            SELECT *
            FROM lote45.book_tree
            WHERE parent_tree = '{data}'
            """
    nd = fu.Node(data, pd.read_sql(str_sql, connection))
    dic_books = nd.to_inv_dict(data)
    
    df[data] = df['book'].apply(lambda x: dic_books[x])
    
    # df = df[df['product'] != 'Cash/Costs']
    
    dt_min = df['date_reference'].min()
    
    str_sql = f"""
            SELECT date_reference,
                rate / 100 AS CDI
            FROM middle.product_price
            WHERE date_reference >= '{dt_min:%Y-%m-%d}'
                AND product_id = 'CDI'
            ORDER BY date_reference
            """
    dfCDI = pd.read_sql(str_sql, connection, index_col = 'date_reference')
    
    dfPnl = df.pivot_table(index = 'date_reference',
                           columns = [data, 'product'],
                           values = 'pnl',
                           aggfunc = np.sum).fillna(0)
    
    temp = dfPnl.sum(level = 1, axis = 1)
    temp = pd.concat([temp], keys = ['Fund'], axis = 1)
    
    dfPnl = dfPnl.join(temp)
    dfCDI['CDI'] = (1 + dfCDI['CDI']) ** (1/252) - 1
    
    dfRiskShare = fu.get_DailyRiskShare(dt, str_fund).loc[dt_min:]
    
    dfPnl.drop('Shared', axis = 1, inplace = True)
   
    for trader in dfPnl.columns.get_level_values(0).unique():
        dfTrader = dfPnl.loc[:,trader]
        
        mindex = pd.MultiIndex(levels= [[],[]],
                               codes=[[],[]],
                                     names=['prod','var'])
        dfOutput = pd.DataFrame(index = dfTrader.index.strftime('%b/%y').unique().tolist() + ['Total'], columns = mindex)
        
        cols = dfTrader.columns

        dfTrader = dfTrader.join(dfRiskShare[trader])
        for c in cols:
            dfTrader[c] /= dfTrader[trader]
            
        dfTrader.drop(trader, axis = 1, inplace = True)
        
        dfTrader = dfTrader.join(dfCDI)        

        dfPnlMonth = (1 + dfTrader).groupby(dfTrader.index.strftime('%b/%y'), sort = False).prod()
        dfPnlMonth['Total'] = (dfPnlMonth - 1).drop('CDI',axis = 1).sum(axis = 1) + 1
        dfPnlMonth.loc['Total'] = dfPnlMonth.prod()
        dfPnlMonth -= 1
        dfPnlMonth *= 10_000
        dfPnlMonth.drop('Cash/Costs', axis = 1, inplace = True)
        
        order = dfPnlMonth.drop(['CDI', 'Total'], axis = 1).sort_values(by = 'Total', axis = 1, ascending = False).columns
        dfTrader.drop('Cash/Costs', axis = 1, inplace = True)
        for c in dfTrader.drop('CDI', axis = 1).columns:
            df = dfTrader[[c,'CDI']][dfTrader[c] != 0]
            
            df['Retorno_acima'] = np.where(df[c] > df['CDI'],
                                           df[c],np.nan)
            
            df['Negativo'] = np.where(df[c] < 0,
                                      df[c], np.nan)
            
            df['Retorno_abaixo'] = np.where((df[c] < df['CDI']) & (df['Negativo'].isna()),
                                            df[c],np.nan)
            
            df = df.drop([c,'CDI'], axis = 1).groupby(df.index.strftime('%b/%y'), sort = False).agg('count')
            df.loc['Total'] = df.sum()
            
            for i in df.columns:
                df[f"{i}%"] = df[i] / df.sum(axis = 1)
            
            df = pd.concat([df], keys=[c], axis = 1)
            
            dfOutput = dfOutput.join(df)
            
        dfOutput.fillna(0, inplace = True)
        
        # temp = dfOutput.sum(level = 1, axis = 1)
        
        # temp.drop(temp.columns[3:], axis = 1,inplace = True)   
        
        # for c in temp.columns:
        #     temp[f"{c}%"] = temp[c] / temp.sum(axis = 1)  
            
        # temp = pd.concat([temp], keys = ['Total'], axis = 1)
        
        dfTrader['Total'] = dfTrader.drop('CDI', axis = 1).sum(axis = 1)
        
        dfTrader = dfTrader[dfTrader['Total'] != 0]
        dfTrader['Retorno_acima'] = np.where(dfTrader['Total'] > dfTrader['CDI'],
                                       dfTrader['Total'],np.nan)
        
        dfTrader['Negativo'] = np.where(dfTrader['Total'] < 0,
                                  dfTrader['Total'], np.nan)
        
        dfTrader['Retorno_abaixo'] = np.where((dfTrader['Total'] < dfTrader['CDI']) & (dfTrader['Negativo'].isna()),
                                        dfTrader['Total'],np.nan)
        
        dfTotal = dfTrader.loc[:,'Retorno_acima':].groupby(dfTrader.index.strftime('%b/%y'), sort = False).count()
        
        dfTotal.loc['Total'] = dfTotal.sum()

        for c in dfTotal.columns:
            dfTotal[f"{c}%"] = dfTotal[c] / dfTotal.sum(axis = 1)
            
        dfTotal = pd.concat([dfTotal], keys = ['Total'], axis = 1)
        dfOutput = dfOutput.join(dfTotal).fillna(0)    
        
            
        fig, axes = plt.subplots(len(dfOutput.columns.get_level_values(0).unique()),
                                 len(dfOutput.index),
                                 figsize=(10,len(dfOutput.columns.get_level_values(0).unique()) * 0.8 if 
                                          len(dfOutput.columns.get_level_values(0).unique()) < 18 else 13.5),
                                 squeeze=False,
                                 sharex=True, sharey=True)
         
        fig.tight_layout(w_pad=0, h_pad=0)
        fig.subplots_adjust(wspace=0.05, hspace=0.05)
        cmap = mpl.cm.get_cmap('bwr', 19).reversed()
        norm = mpl.colors.TwoSlopeNorm(vmin=-100, vcenter=0., vmax=100)
        
        for i,m in enumerate(dfOutput.index):
            ax = axes[0,i]
            ax.set_title(f"{m}",fontsize = 11,fontweight = 'bold', rotation = 0,ha = 'center')
            
            for j,d in enumerate(order.tolist() + ['Total']):
                acima = dfOutput.loc[m, (d, 'Retorno_acima')]
                neg = dfOutput.loc[m, (d,'Negativo')]
                abaixo = dfOutput.loc[m, (d,'Retorno_abaixo')]
                acima_perc = dfOutput.loc[m, (d, 'Retorno_acima%')]
                neg_perc = dfOutput.loc[m, (d,'Negativo%')]
                abaixo_perc = dfOutput.loc[m, (d,'Retorno_abaixo%')]
                cdi = dfPnlMonth.loc[m,'CDI']
                pnl = dfPnlMonth.loc[m,d]
                ax = axes[j,i] 
                ax.set_xticks([])
                ax.set_yticks([])
                if acima + abaixo + neg == 0:
                    ax.spines["top"].set_visible(False)
                    ax.spines["right"].set_visible(False)
                    ax.spines["left"].set_visible(False)
                    ax.spines["bottom"].set_visible(False)
                else:
                    ax.annotate(f"{acima:.0f} - {acima_perc:2.0%}",xy=(0.5, 0.75), xycoords="axes fraction", 
                                va='center', ha='center', fontsize=10, fontweight = 'bold', color = 'b')
                    ax.annotate(f"{abaixo:.0f} - {abaixo_perc:2.0%}",xy=(0.5, 0.5), xycoords="axes fraction",
                            va='center',ha='center', fontweight='bold',fontsize=10)
                    ax.annotate(f"{neg:.0f} - {neg_perc:2.0%}",xy=(0.5, 0.25), xycoords="axes fraction", 
                                va='center',ha='center', color = 'r', fontweight = 'bold')
                    
                    if pnl < 0:
                        facecolor = 'lightsalmon' 
            
                    elif (pnl >= 0) & (pnl <= cdi):
                        facecolor = 'silver' 
                                            
                    else:
                        facecolor = 'lightblue' 
                         
                    ax.set_facecolor(facecolor)
                
        
        for j,m in enumerate(order.tolist() + ['Total']):
            ax = axes[j,0]
            ax.set_ylabel(f"{m}",fontsize = 11,fontweight = 'bold', rotation = 0,ha = 'right')
    
        fig_file = r'C:\Users\matheus.amaral\Documents\GitHub\risk_report\output\temp_figs\{}_performance_cdi.pdf'.format(trader)
        fig.savefig(fig_file,bbox_inches = 'tight', pad_inches = 0)
        
#%%

if __name__ == '__main__':
    dt = date(2022,9,6)
    main(dt)