import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
from networkx.drawing.nx_pydot import graphviz_layout
import pydot

import fund_utils as fu
import fund_data

dt, str_fund = fu.get_config(['dt', 'str_fund'])
nav = fu.get_NAV(dt, str_fund)
data = fund_data.db_data(dt, str_fund, verbose=True)

# _, connection = fu.get_DB_conn()

# for str_tree in ['Traders']:
#     str_sql = f"""
#                      SELECT [parent_tree],[parent_node],[node],[book]
#                      FROM [lote45].[book_tree]
#                      WHERE parent_tree = '{str_tree}'
#               """
# dfTree = pd.read_sql(str_sql, connection)
# nd = fu.Node(str_tree, dfTree)    


#%%
str_tree = 'Traders'
dfPosition = data._dfPosition.copy()
DG = data._dic_nodes[str_tree].get_graph(set(dfPosition['book']))

pos = graphviz_layout(DG, prog="dot")

fig, ax = plt.subplots(1,1, figsize=(14, 5))
fig.tight_layout()

nx.draw(DG, ax=ax, pos=pos, 
        node_shape='s', node_size=600, node_color=fu.color_palette[2], 
        font_size=8, font_weight='bold',
        labels={n: n.replace(' ','\n') for n in DG})

#%%
def format_string(x):
    return x.replace('_','\n').replace(' ','\n') if type(x) == str else x[-1].replace('_','\n').replace(' ','\n')


dic_primitive_class = {'USA Sovereign Yield': 'IR DM', 
                       'BRL Rate Curve': 'IR BR',
                       'Brazil Sovereign Yield' : 'IR BR',
                       'COP Rate Curve': 'IR Latam',
                       'CLP Rate Curve': 'IR Latam',
                       'IPCA Coupon': 'IR BR',
                       'IPCA': 'IR BR', 
                       'MXN Rate Curve': 'IR Latam',
                       'BRD Rate Curve': 'IR BR',
                       'USD Rate Curve': 'IR DM'}

df_primitives = data._dfPrimitive.copy()
dic_primitive = df_primitives[['primitive','primitive_class']].drop_duplicates().set_index('primitive')['primitive_class'].to_dict()

dic_color = {'FX': 'tomato',
             'Equity': 'wheat',
             'IR BR': 'lightsteelblue',
             'IR DM': 'dodgerblue',
             'IR Latam': 'plum',
             'Commodity': 'sienna'}

def format_color(x):
    n = x.replace('_delta', '') if type(x) == str else x[-1].replace('_delta', '')
    return dic_color.get(dic_primitive_class.get(dic_primitive.get(n), dic_primitive.get(n)),'silver') 

df_primitives['node1'] = df_primitives[['book', 'lote45_product']].apply(tuple, axis=1)
df_primitives['node2'] = df_primitives['primitive']
df_primitives['node2_id'] = df_primitives[['book', 'lote45_product', 'primitive']].apply(tuple, axis=1)

trader ='NF'
books = ['NF PRE', 'NF Juro Real']
dg_primitive = nx.DiGraph()
for book in [b for b in df_primitives[df_primitives['Traders'] == trader]['book'].unique() if b in books]:
    dg_primitive.add_edge(trader, book)
    for nd1 in df_primitives[df_primitives['book'] == book]['node1']:
        dg_primitive.add_edge(book, nd1)
        for nd2 in df_primitives[df_primitives['node1'] == nd1]['node2']:
            dg_primitive.add_edge(nd1, nd2 + '_Delta')
            # dg_primitive.add_edge(nd2, (nd2,'Delta'))
            if df_primitives[(df_primitives['node1'] == nd1)&(df_primitives['node2'] == nd2)]['gamma'] !=0:
                dg_primitive.add_edge(nd2, (nd2,'Gamma'))
                

pos = graphviz_layout(dg_primitive, prog="dot")

fig, ax = plt.subplots(1,1, figsize=(14, 5))
fig.tight_layout()
nx.draw(dg_primitive, ax=ax, pos=pos, 
        node_shape='s', node_size=600, 
        node_color=[dic_color.get(dic_primitive_class.get(dic_primitive.get(n), dic_primitive.get(n)),'silver') for n in dg_primitive],
        font_size=8, font_weight='bold',
        labels={n: format_string(n) for n in dg_primitive})