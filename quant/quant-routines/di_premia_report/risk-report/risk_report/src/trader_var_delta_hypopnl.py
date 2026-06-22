import datetime
import pandas as pd
import numpy as np
import math

import networkx as nx
from networkx.drawing.nx_pydot import graphviz_layout

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import adjustText

import fund_utils as fu
import fund_data


#%%#################
def get_graph(df_w, t, data, nav):
    ##### sub fuction #########
    def add_nodes(temp_df, parent, parent_tuple, dg):
        nds = set(temp_df[parent_tuple].columns.get_level_values(0))
        for nd in nds:
            new_tuple = (*parent_tuple, nd)
            df_var = temp_df[new_tuple].sum(axis=1) if len(new_tuple) < temp_df.columns.nlevels else temp_df[new_tuple]
            var, bull_bear = data.calculate_var(df_var) 
            dg.add_node(new_tuple,
                        label=nd,
                        var=-var/nav*10_000,
                        bull_bear=bull_bear
                        ) 
            dg.add_edge(parent_tuple, new_tuple)
            if type(temp_df[new_tuple])!= pd.Series:
                add_nodes(temp_df, nd, new_tuple, dg)     
    ##########################    
    dg_var = nx.DiGraph()
    parent_tuple = (t,)    
    var, bull_bear = data.calculate_var(df_w[parent_tuple].sum(axis=1))    
    dg_var.add_node(parent_tuple, 
                    label=t,                    
                    var=-var/nav*10_000,
                    bull_bear=bull_bear
                    )
    add_nodes(df_w, t, parent_tuple, dg_var)
    return dg_var

#%%%
def main(data, nav):
    #%%
    _, connection = fu.get_DB_conn('prod')    
    str_sql = f"""
                SELECT [lote45_product],[date_maturity]
                    FROM [middle].[product]
                    WHERE date_maturity >= '{data._dt:%Y-%m-%d}'
            """
    dic_maturity = pd.read_sql(str_sql, connection, index_col='lote45_product')['date_maturity'].to_dict()
    #%%
    cols = ['Traders', 'Risk', 'book']
    fixedincome_risks = ['PRE', 'ARBITRAGE', 'INFLATION']
    fixedincome_primitives = [
                              # 'Brazil Sovereign Yield',
                              'BRD Rate Curve',
                              'BRL Rate Curve',
                              'CLP Rate Curve',
                              'COP Rate Curve',
                              'IPCA Coupon',
                              'MXN Rate Curve',
                              'USA Sovereign Yield',
                              'USD Rate Curve']
    
    
    dfHypoPnL = data._dfHypoPnL.groupby(level=cols, 
                                        axis=1).sum()
    
    df_w = data._w.pivot_table(index='primitive',
                               columns=cols, 
                               values='w',
                               aggfunc=np.sum).fillna(0)
    
    temp_primitive = data._dfPrimitive.copy()
    temp_primitive['geo'].replace({True:'Brazil', False:'Off'}, inplace=True)
    def mapPrimitive(primitive_class, primitive, geo):
        if primitive_class=='Equity':
            return 'Eqty ' +geo
        elif primitive_class=='FX':
            return 'FX ' + primitive[0:6]
        else:
            return primitive_class
    
    temp_primitive['primitive_'] = temp_primitive[['primitive_class', 'primitive', 'geo']].apply(lambda x: mapPrimitive(x[0], x[1], x[2]), axis=1)

    
    df_primitive = temp_primitive.pivot_table(index=['primitive_', 'lote45_product'],
                                                 columns=cols,
                                                 values='delta',
                                                 aggfunc=np.sum)
    
    #%%
    traders = list(fu.get_traders(data._dt).keys())
    traders = [t for t in traders if t in set(df_w.columns.get_level_values(0))]
    dic_figs = {}
    for t in traders:
        risk_share = data._risk_share.loc[data._dt, t]
        dg_var = get_graph(df_w, t, data, nav)  
        pos = graphviz_layout(dg_var, 
                              prog="dot", 
                              root=t)
    
        temp_hypopnl = dfHypoPnL[t].loc[datetime.date(2000,1,1):] / risk_share / nav * 10_000
        temp_primitive = df_primitive[t]    
    
        fig1, ax = plt.subplots(1,1, figsize=(12,3), constrained_layout=True)        
        nx.draw(dg_var, 
                ax=ax, 
                pos=pos,
                labels={n[0]:f"{n[1].get('label', n)}\n{n[1].get('var', 0)/risk_share:2.1f}" \
                        for n in dg_var.nodes(data=True)},
                node_shape='s', 
                node_size=800, 
                node_color='silver', 
                font_size=9, 
                font_weight='bold'                
                )
        plt.show()
        
        #%%
        nrows = math.ceil(len(temp_primitive.columns)/4)
        fig2, axes = plt.subplots(nrows, 4, 
                                 figsize=(12, min([6.775, 3*nrows])), constrained_layout=True) 
        
        sorted_cols = sorted(temp_primitive.columns, key=lambda x: "a" if x[0] in fixedincome_risks else "b")
        temp_primitive = temp_primitive[sorted_cols]
        
        for ax, (col_risk, col_book) in zip(axes.flatten(), sorted_cols):
            ax.set_title(f"{col_risk}\n{col_book}", fontweight='bold')
            temp_pos = temp_primitive[(col_risk, col_book)].dropna()/nav/risk_share
            if col_risk in fixedincome_risks:
                temp_pos = temp_pos.loc[[i for i in set(temp_pos.index.get_level_values(0)) if i in fixedincome_primitives]]
                temp_pos.index = temp_pos.index.droplevel()
                temp_pos = temp_pos.loc[sorted(temp_pos.index, 
                                               key=lambda x:dic_maturity.get(x),
                                               reverse=True)]
            else:
                temp_pos = temp_pos.groupby('primitive_').sum()            
            temp_pos.plot.barh(ax=ax, alpha=0.1)
            for i, (_, v) in enumerate(temp_pos.iteritems()):
                ax.text(0, i, f"{v:+0,.0%}", ha='center', va='center',
                            fontweight='bold', c='k' if v>=0 else 'r')    
            ax.set_ylabel('')
            ax.set_xlim(left=-50, right=50)
            ax.set_xticks([])
            
        for ax in axes.flatten()[len(sorted_cols):]:
            ax.set_axis_off()
    
        plt.show()    
       
        #%%   
        ncol=5
        trader_hypopnl = temp_hypopnl.sum(axis=1)
        df_top5 = trader_hypopnl.sort_values().head(ncol).sort_index()
        
        fig3 = plt.figure(figsize=(12, 4.22), constrained_layout=True)
        axRet = plt.subplot(2, ncol, (1,5))
        axes = []
        for i in range(0, ncol):
            axes.append(plt.subplot(2, ncol, i+6))
         
        ax = axRet
        # ax.set_title("Simulação Histórica - 15 anos", fontsize=12, fontweight='bold')
        ax.plot(trader_hypopnl.index, trader_hypopnl, color=fu.color_palette[1], ls='', marker='.', alpha=0.5)
        ax.set_ylabel("Simulated PnL (BPs)")
        ax.grid(ls='--', which='major')
        ax.grid(ls=':', which='minor')
        ax.set_xlim(left=trader_hypopnl.index[0], right=trader_hypopnl.index[-1])
         
        txts = []
        for i, axi in enumerate(axes):
            ax.scatter([df_top5.index[i]],[df_top5.iloc[i]],color='tomato')
            txts.append(ax.text(df_top5.index[i],
                                df_top5.iloc[i],
                                f"{df_top5.index[i]:%d%b%y}"))
            axi.set_title(f"{df_top5.index[i]:%d%b%y}", fontsize=11, fontweight='bold')
            temp_plot = temp_hypopnl.loc[df_top5.index[i]].loc[sorted_cols].droplevel(0)
            temp_plot['TOTAL'] = temp_plot.sum()
            temp_plot.plot.bar(ax=axi, 
                               grid=False, 
                               color=[fu.color_palette[1]] * (len(temp_plot)-1) + ['tomato'], 
                               zorder=3)
            for j, v in enumerate(temp_plot.values):
                axi.text(j, max([0,v]), f" {v:+2,.0f}", ha='center', va='bottom', 
                         rotation=90, fontsize=8,
                         fontweight='bold', c='r' if v<0 else 'k')
            axi.get_xticklabels()[-1].set_fontweight('bold')
            axi.set_xticklabels([i[:14] for i in temp_plot.index])
            axi.grid(ls='--', axis='y')
            axi.set_xlabel('')
            ymin, ymax = axi.get_ylim()
            axi.set_ylim(top=max([150, ymax*1.75]), bottom=ymin*1.2)
             
        adjustText.adjust_text(txts, ax=ax)
        axes[0].set_ylabel("Simulated PnL (BPs)")
        fig3.align_ylabels()
        plt.show()
    
        dic_figs[t] = [fig1, fig2, fig3]
    #%%
    return dic_figs

if __name__ == "__main__":

    dt , str_fund, print_pdf = fu.get_config(['dt', 'str_fund', 'print_pdf'])
    nav = fu.get_NAV(dt, str_fund)
    
    str_path = f"../tex/{dt:%Y%m%d}/figuras"
   
    data = fund_data.db_data(dt, str_fund, verbose=True)      
    
    dic_f = main(data, nav)
    for t, files in dic_f.items():
        for i, f in enumerate(files):
            fig_file = f"{str_path}/{dt:%Y%m%d}_{t}_{i:0.0f}.pdf"
            f.savefig(fig_file, #facecolor='silver',
                      bbox_inches = 'tight')
    