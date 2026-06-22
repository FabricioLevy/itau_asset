import pandas as pd
import numpy as np
import datetime
import matplotlib.pyplot as plt
import networkx as nx
from networkx.drawing.nx_pydot import graphviz_layout

import fund_utils as fu
import fund_data

dt, str_fund = fu.get_config(['dt', 'str_fund'])
nav = fu.get_NAV(dt, str_fund)
data = fund_data.db_data(dt, str_fund, verbose=True)

#%%
_, connection = fu.get_DB_conn('prod')
str_sql = "SELECT [lote45_product_class],[risk_product]  FROM [lote45].[product_class] "
dic_product = pd.read_sql(str_sql, 
                          connection, 
                          index_col='lote45_product_class')['risk_product'].to_dict()

connection.close()

#%%
df_pnl = data._dfPnL.copy()

df_pnl['prod'] = df_pnl['lote45_product_class'].apply(lambda x: dic_product.get(x,x))
df_pnl = df_pnl.replace({'Caixa_Outros':'Caixa'})
df_pnl.loc[df_pnl['PerformanceAttribution']=='Caixa','prod'] = 'Outros'

tree_levels = ['Traders','PerformanceAttribution', 'prod']
dic_filters = {k:df_pnl[k].unique() for k in tree_levels}

dic_filters['Traders'] = ['MS', 'BC', 'PC', 'GB', 'NF', 'MK']


date_ini = dt #datetime.date(2022,9,1)
date_end = dt #datetime.date(2022,9,30)


df_pnl = df_pnl.pivot_table(index='date_reference',
                        columns=tree_levels,
                        values = 'PnL_Perc',
                        aggfunc=np.sum).loc[date_ini:date_end].dropna(how='all', axis=1).fillna(0)

total_pnl = ((df_pnl.sum(axis=1)+1).prod()-1) * 10_000

dic_total_pnl = {}
list_level = []
for lvl in tree_levels:
    list_level.append(lvl)
    dic_total_pnl[lvl] = ((df_pnl.groupby(level=list_level, axis=1).sum()+1).prod()-1) * 10_000


dg_pnl = nx.DiGraph()
dg_pnl.add_node((str_fund,), 
                label=f"{str_fund}\n{total_pnl:+2,.1f}",
                color='salmon' if total_pnl<0 else 'lightblue')

def add_nodes(dic_total_pnl, levels, lvl_parent, dg):
    if levels:
        current_level = levels[0]
        temp_total_pnl = dic_total_pnl[current_level].loc[lvl_parent[1:]]
        for lvl_item in temp_total_pnl.index:
            if lvl_item in dic_filters[current_level]:
                new_tuple = (*lvl_parent, lvl_item)
                str_lvl_item = lvl_item.replace(' ', '\n').replace('/','\n')
                dg.add_node(new_tuple,
                            label=f"{str_lvl_item}\n{temp_total_pnl.loc[lvl_item]:+2.1f}",
                            color='salmon' if temp_total_pnl.loc[lvl_item]<0 else 'lightblue')
                dg.add_edge(lvl_parent, new_tuple)
                add_nodes(dic_total_pnl, levels[1:] , new_tuple, dg)


add_nodes(dic_total_pnl, tree_levels, (str_fund,), dg_pnl)


pos = graphviz_layout(dg_pnl, prog="dot", root=str_fund)

fig, ax = plt.subplots(1,1, figsize=(32, 8))
fig.tight_layout()

nx.draw(dg_pnl, 
        ax=ax, 
        pos=pos, 
        node_shape='s', 
        node_size=500, 
        node_color=[n[1].get('color', 'silver') for n in dg_pnl.nodes(data=True)], 
        font_size=8, 
        font_weight='bold',
        labels={n[0]:n[1].get('label', n) for n in dg_pnl.nodes(data=True)}
        )

ax.set_title(f"{str_fund}\n({date_ini:%d%b%Y} ~ {date_end:%d%b%Y})", fontweight='bold')
plt.show()

# fig.savefig(f"../../reuniao_posicionamento/tex/2022_09_16/figuras/risk_mapping_{str_tree}.pdf",
#                 bbox_inches = "tight")

#%%

