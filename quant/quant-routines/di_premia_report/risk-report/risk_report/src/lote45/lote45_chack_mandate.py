# -*- coding: utf-8 -*-
"""
Created on Tue Aug  9 19:55:23 2022

@author: matheus.amaral
"""

import pandas as pd
import numpy as np
from datetime import date
from a1db.a1sql import SQLConnection 
import fund_utils as fu


def main(dt):
    
    data = 'Traders'
    connection = SQLConnection().get_connection()
    exclude = ('cash', 'Provisions and Costs', 'Compromissada CDI','EquityLoan')
    
    str_sql = f"""
            SELECT *
            FROM risk.trader_mandate
            """
    dfMandate = pd.read_sql(str_sql, connection)
    
    str_sql = f"""
            SELECT *
            FROM lote45.book_tree
            WHERE parent_tree = '{data}'
            """
    nd = fu.Node(data, pd.read_sql(str_sql, connection))
    dic_books = nd.to_inv_dict(data)
    
    str_sql = f"""
            SELECT DISTINCT lote45_product_class,
                lote45_product,
                book
            FROM lote45.book_overview
            WHERE date_reference = '{dt:%Y-%m-%d}'
                AND measure = 'Position'
                AND lote45_product_class NOT IN {exclude}
            """
    df = pd.read_sql(str_sql, connection)
    
    df['trader_id'] = df['book'].apply(lambda x: dic_books[x])
    
    dfProds = df[df['trader_id'] != 'Shared'][['lote45_product', 'lote45_product_class', 'trader_id']].\
        drop_duplicates()
        
    list_keys = ['trader_id', 'lote45_product_class']
    dfCheck1 = dfProds.merge(dfMandate[list_keys + ['primitive_class']].drop_duplicates(), how = 'left', on = list_keys)
    
    list_warning_prod = list(dfCheck1[dfCheck1['primitive_class'].isna()][['trader_id','lote45_product_class']].\
        drop_duplicates().to_records(index = False))
    
    if list_warning_prod:
        print('\nRelação trader produto não encontrada na base:')
        print('\n'.join([f"{i[0]} - {i[1]}" for i in list_warning_prod]))
    
    #%%    
    dfCheck2 = dfCheck1[(dfCheck1['primitive_class'].notna()) & (dfCheck1['primitive_class'] != '*')]
    
    products = tuple(dfCheck2['lote45_product'].unique())
    
    str_sql = f"""
            SELECT DISTINCT book,
                lote45_product,
                primitive,
                primitive_class
            FROM lote45.primitive
            WHERE lote45_product IN {products}
            """
    dfPrimitive = pd.read_sql(str_sql,connection)
    dfPrimitive['trader_id'] = dfPrimitive['book'].apply(lambda x: dic_books[x])
    dfPrimitive = dfPrimitive.drop('book', axis = 1).drop_duplicates()
    
    dfCheck2 = dfCheck2.merge(dfPrimitive, on =  ['lote45_product','trader_id', 'primitive_class'], 
                              how = 'left')
    dfCheck2 = dfCheck2.drop('lote45_product', axis = 1).drop_duplicates()
    
    dfCheck2 = dfCheck2.merge(dfMandate, on = list_keys + ['primitive'], how = 'left', indicator = True).query('_merge == "left_only"')
    
    list_warning_primitive = list(dfCheck2[['trader_id','lote45_product_class','primitive']].to_records(index = False))
    
    if list_warning_primitive:
        print('\nRelação trader-produto-primitiva não encontrada na base:')
        print('\n'.join([f"{i[0]} -  {i[1]} - {i[2]}" for i in list_warning_primitive]))


#%%
if __name__ == '__main__':
    
    dt = date(2022,8,19)
    main(dt)