import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import networkx as nx
from networkx.drawing.nx_pydot import graphviz_layout

import sys
sys.path.insert(1, '../../risk_report/src')
import fund_utils as fu
import fund_data


def main(data, nav):
#%%                          
    dt = data._dt
    str_fund = data._fund
                             
    _, connection = fu.get_DB_conn('prod')
    str_sql = "SELECT [lote45_product_class],[risk_product] FROM [lote45].[product_class] "
    dic_product = pd.read_sql(str_sql, 
                              connection, 
                              index_col='lote45_product_class')['risk_product'].to_dict()
    connection.close() 
#%%
    def add_nodes(dic_var, levels, lvl_parent, dg):
        if levels:
            current_level = levels[0]
            temp_var = dic_var[current_level].loc[lvl_parent]
            for lvl_item in temp_var.index:
                if lvl_item in dic_filters[current_level]:
                    new_tuple = (*lvl_parent, lvl_item)
                    str_lvl_item = lvl_item.replace(' ', '\n').replace('/','\n')
                    color=color_off if 'Offshore' in new_tuple else color_on if 'Onshore' in new_tuple else 'silver'
                    dg.add_node(new_tuple,
                                label=f"{str_lvl_item}\n{temp_var.loc[lvl_item]:4.1f}",
                                color=color,
                                var=temp_var.loc[lvl_item],
                                edgecolor='red' if ((lvl_item  in dic_risk_share.keys()) and (temp_var.loc[lvl_item])>210) else color,
                                bull = dic_bull[new_tuple],
                                cvar=0) 
                    dg.add_edge(lvl_parent, new_tuple)
                    add_nodes(dic_var, levels[1:] , new_tuple, dg)
#%%
    temp_df_w = data._w.copy()
    temp_df_w.loc[:,'geo'].replace({True:'Onshore',
                                    False:'Offshore'}, inplace=True)
    
    temp_df_w['prod'] = temp_df_w['lote45_product_class'].apply(lambda x: dic_product.get(x, x))
    temp_df_w['Fund'] = data._fund
    
    trees = [['Fund', 'Traders', 'geo', 'Risk'],
             ['Fund', 'geo', 'Risk', 'prod']]
    trader_adj = True

    dic_figs = {}

    for tree_levels in trees:

        df_w = temp_df_w.pivot_table(index='primitive',
                                     columns=tree_levels, 
                                     values='w', 
                                     aggfunc=np.sum).fillna(0)

        if trader_adj and ('Traders' in tree_levels):
            trader_index = tree_levels.index('Traders')
        else:
            trader_adj = False
           
        dic_risk_share = data._risk_share.loc[dt].to_dict()
        dic_filters = {k:list(temp_df_w[k].unique()) for k in tree_levels}
        
        dic_filters['Traders'] = ['MS', 'BC', 'PC', 'GB', 'NF', 'MK']
        dic_filters['geo'] = ['Onshore', 'Offshore']
        if 'Risk' in dic_filters.keys():
            dic_filters['Risk'].remove('ALL') 
        
        dic_var = {}
        dic_bull = {}
        
        list_level = []
        for i_lvl, lvl in enumerate(tree_levels):
            list_level.append(lvl)
            temp_df = df_w.groupby(level=list_level, axis=1).sum()
            dic_var[lvl] = pd.Series(index=temp_df.columns, dtype=float)
            for c in temp_df.columns:
                if trader_adj:
                    t = c[trader_index] if type(c) == tuple else c 
                    adj_risk = dic_risk_share.get(t, 1) if i_lvl>=trader_index else 1
                    if adj_risk==0:
                        adj_risk = 1
                else:
                    adj_risk = 1
                var_brl, bullbear = data.calculate_var(temp_df[c])
                dic_var[lvl].loc[c] = - var_brl / nav * 10_000 / adj_risk
                dic_bull[c] = (bullbear > 0)
                
        
        if 'Traders' in dic_var.keys():
            dic_var['Traders'].sort_index(key=np.vectorize(lambda x: -dic_risk_share.get(x,0)),
                                          inplace=True)
            
        dg_var = nx.DiGraph()
        dg_var.add_node((str_fund,), 
                        label=f"{str_fund}\n{dic_var['Fund'].loc[str_fund]:2,.1f}",
                        color=fu.color_palette[3],
                        edgecolor=fu.color_palette[3],
                        var=dic_var['Fund'].loc[str_fund],
                        bull = dic_bull[str_fund],
                        cvar=0)
        
        color_off, color_on = fu.color_palette[1], fu.color_palette[5]      
        
        add_nodes(dic_var, tree_levels[1:], (str_fund,), dg_var)        
        
        pos = graphviz_layout(dg_var, prog="dot", root=str_fund)
        
        fig, ax = plt.subplots(1,1, figsize=(4*len(tree_levels),
                                             1.25*len(tree_levels)))
        fig.tight_layout()
        for is_bull, node_shape in zip([True, False], ['^', 'v']):
            node_list = [n[0] for n in dg_var.nodes(data=True) if n[1].get('bull') == is_bull ]    
            nx.draw_networkx_nodes(dg_var,
                                   ax=ax, 
                                   pos=pos, 
                                   node_shape=node_shape, 
                                   nodelist=node_list,
                                   node_size=[n[1].get('var', n)*(10 if trader_adj else 30) for n in dg_var.nodes(data=True) if n[0] in node_list], 
                                   node_color=[n[1].get('color', 'silver') for n in dg_var.nodes(data=True) if n[0] in node_list], 
                                   edgecolors=[n[1].get('edgecolor', 'silver') for n in dg_var.nodes(data=True) if n[0] in node_list],
                                   )
        
        nx.draw_networkx_labels(dg_var,
                                ax=ax,
                                pos=pos,
                                font_size=8,
                                font_weight='bold',
                                labels={n[0]:n[1].get('label', n) for n in dg_var.nodes(data=True)})
        
        nx.draw_networkx_edges(dg_var,
                               ax=ax,
                               width=1.25,
                               pos=pos)
        
        legend_elements1 = [Line2D([0], [0], marker='s', color=fu.color_palette[3], label='Fund', lw=0,
                                  markerfacecolor=fu.color_palette[3], markersize=12),
                           Line2D([0], [0], marker='s', color='silver', label='Traders', lw=0,
                                  markerfacecolor='silver', markersize=12),
                           Line2D([0], [0], marker='s', color=color_on, label='Brazil', lw=0,
                                  markerfacecolor=color_on, markersize=12),
                           Line2D([0], [0], marker='s', color=color_off, label='International', lw=0,
                                  markerfacecolor=color_off, markersize=12),
                           ]
        
        ax.legend(handles=legend_elements1, 
                  bbox_to_anchor=(0.2, 0.95),
                  prop={'weight':'bold',
                        'size':9})        
        
        legend_elements2 = [Line2D([0], [0], marker='s', color='red', label='Limit Breach', lw=0,
                                   markerfacecolor='silver', markersize=12),
                           Line2D([0], [0], marker='v', color='silver', label='Bearish', lw=0,
                                  markerfacecolor='silver', markersize=12),
                           Line2D([0], [0], marker='^', color='silver', label='Bullish', lw=0,
                                  markerfacecolor='silver', markersize=12),
                           ]
        ax2 = ax.twinx()
        ax2.legend(handles=legend_elements2, 
                  bbox_to_anchor=(0.85, 0.95),
                  prop={'weight':'bold',
                        'size':9})
        
        ax.axis('off')
        ax2.axis('off')
        ax.set_title(f"{str_fund} - VaR (Bps)\n{dt:%d-%b-%Y}", fontweight='bold')
        plt.show()
        dic_figs['_'.join(tree_levels)] = fig
        
    return dic_figs


#%%
if __name__ == "__main__":

    dt, str_fund, dt_1w = fu.get_config(['dt', 'str_fund', 'dt_1w'])
    data = fund_data.db_data(dt, str_fund, verbose=True)
    nav = fu.get_NAV(dt, str_fund)
    
    dic_figs = main(data, nav)
    
    for str_fig, fig in dic_figs.items():
        fig_file = f"../../reuniao_posicionamento/tex/{dt:%Y_%m_%d}/figuras/{dt:%Y%m%d}_{str_fund}_riskTree_{str_fig}.pdf"
        fig.savefig(fig_file, bbox_inches = "tight")

    