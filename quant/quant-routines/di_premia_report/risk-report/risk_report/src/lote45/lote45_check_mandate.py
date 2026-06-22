# -*- coding: utf-8 -*-
"""
Created on Tue Sep 20 08:54:38 2022

@author: matheus.amaral
"""

import pandas as pd
from a1db.a1sql import SQLConnection
from datetime import date
import fund_utils as fu

def main(dt):
    connection = SQLConnection().get_connection()
    data = 'Traders'
    list_out = ['Provisions and CostS', 'Cash', 'EquityLoan', 'Compromissada CDI', 'Overnight']
    
    
    str_sql = """
            SELECT *
            FROM risk.trader_mandate
            """
    dfMandate = pd.read_sql(str_sql, connection)
    
    str_sql = """
            SELECT DISTINCT lote45_product,
                lote45_product_class,
                primitive_class,
                primitive
            FROM lote45.primitive
            """
    dfP = pd.read_sql(str_sql, connection)
    
    str_sql = f"""
            SELECT DISTINCT book,
                lote45_product,
                lote45_product_class
            FROM lote45.book_overview
            WHERE date_reference = '{dt:%Y-%m-%d}'
                AND lote45_product_class NOT IN ('{"','".join(list_out)}')
                AND measure = 'Amount'
            """
    dfProd = pd.read_sql(str_sql, connection)
    
    str_sql = f"""
            SELECT *
            FROM lote45.book_tree
            WHERE parent_tree = '{data}'
            """
    nd = fu.Node(data, pd.read_sql(str_sql, connection))
    dict_books = nd.to_inv_dict(data)
    
    dfProd['trader_id'] = dfProd['book'].apply(lambda x: dict_books[x])
    
    dfProd = dfProd[dfProd['trader_id'] != 'Shared'].drop('book', axis = 1).drop_duplicates()
    
    dfClass = dfMandate[dfMandate['primitive_class'] == '*'][['trader_id', 'lote45_product_class']]
    dfPrimitive = dfMandate[dfMandate['primitive_class'] != '*']
    
    dfFilter = dfProd.merge(dfClass, on = ['trader_id', 'lote45_product_class'], indicator = True, how = 'left').\
        query('_merge == "left_only"').drop(['_merge'], axis = 1)
        
    dfCheck_1 = dfFilter[~dfFilter['lote45_product_class'].isin(dfPrimitive['lote45_product_class'].unique())].\
        drop('lote45_product', axis = 1).drop_duplicates()
    
    dfFilter = dfFilter[dfFilter['lote45_product_class'].isin(dfPrimitive['lote45_product_class'].unique())]
    
    dfCheck_2 = dfFilter.merge(dfPrimitive[['trader_id','lote45_product_class','primitive_class']].drop_duplicates(),\
                               on = ['trader_id', 'lote45_product_class'], how = 'left')
    
    dfCheck_2 =dfCheck_2.merge(dfP, on = ['lote45_product_class', 'lote45_product', 'primitive_class'],how = 'left')
    
    dfCheck_2 = dfCheck_2.merge(dfPrimitive, on = ['trader_id', 'lote45_product_class', 'primitive_class', 'primitive'],\
                                how = 'left', indicator = True).query("_merge == 'left_only'")
    
    dfCheck_3 = dfCheck_2[dfCheck_2['primitive_class'].isna()]
    dfCheck_2 = dfCheck_2.dropna(subset = 'primitive_class')    
    
    if (dfCheck_1.empty) & (dfCheck_2.empty) & (dfCheck_3.empty):
        print('\n')
        print('Nenhuma relação trader - produto nova.')
    else:
        print('\n')
        print('As sguintes relações trader - produto não foram encontradas na tabela de mandato:')
        print('\n'.join([f"{dfCheck_1.loc[i,'trader_id']} - {dfCheck_1.loc[i,'lote45_product_class']}" for i \
                         in dfCheck_1.index]))
        print('\n'.join([f"{dfCheck_2.loc[i,'trader_id']} - {dfCheck_2.loc[i,'lote45_product_class']} - {dfCheck_2.loc[i,'primitive']}"\
                         for i in dfCheck_2.index]))
        print('\n'.join([f"{dfCheck_3.loc[i,'trader_id']} - {dfCheck_3.loc[i,'lote45_product_class']} - {dfCheck_3.loc[i,'lote45_product']}"\
                         for i in dfCheck_3.index]))
 
#%%
if __name__ == '__main__':
    
    dt = date(2022,10,7)
    main(dt)