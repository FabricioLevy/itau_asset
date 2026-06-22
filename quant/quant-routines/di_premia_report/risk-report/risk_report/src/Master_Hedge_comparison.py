import pandas as pd
import numpy as np
import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import xlwings as xw
import QuantLib as ql

import os, sys
path_risk = os.path.expanduser('~\\Documents\\Github\\risk_report\\src')
sys.path.insert(1, path_risk)
import fund_utils as fu

def main(dt, str_fund_compared):
    #%%
    color1, color2 = fu.color_palette[0:2]
    
    str_fund = 'A1 Master FIM'
    
    _, connection = fu.get_DB_conn('prod')
    
    str_sql = """
            SELECT [product_ticker]
            FROM [middle].[allocation_positive_list]
            WHERE trading_desk_permitted = '{}'
    """.format(str_fund_compared)
    lista_positiva = ['IBVS'] + list(pd.read_sql(str_sql, connection)['product_ticker'].values)
    
    str_sql = """
    SELECT p.[date_reference],p.[trading_desk],[lote45_product],[lote45_product_class]
          ,[primitive],[primitive_class],[book],[product_currency],[bucket]
          ,[eq_position],[amount],[delta]/n.NAV as delta_perc,[gamma],[vega]
          FROM [lote45].[primitive] p INNER JOIN middle.NAV n
              ON p.date_reference = n.date_reference AND p.trading_desk = n.trading_desk
      WHERE p.trading_desk in ('{}', 'A1 Master FIM') 
      and p.date_reference = '{:%Y-%m-%d}'
                """
    dfPrimitive = pd.read_sql(str_sql.format(str_fund_compared,dt), connection)
    
    str_sql = """
        SELECT m.[date_reference],m.[trading_desk],[parent_tree],[node]
          ,[risk_measure],-[value]/n.NAV as val_perc
      FROM [risk].[measure] m INNER JOIN middle.NAV n
              ON m.date_reference = n.date_reference AND m.trading_desk = n.trading_desk
      WHERE m.trading_desk in ('{}', 'A1 Master FIM') 
      and m.date_reference = '{:%Y-%m-%d}'
      and parent_tree <> 'Itau'
    """
    dfRisk = pd.read_sql(str_sql.format(str_fund_compared,dt), connection)
    
    str_tree = 'Traders'
    str_sql = """
           SELECT [parent_tree],[parent_node],[node],[book]
           FROM [lote45].[book_tree]
           WHERE parent_tree = '{}'
                    """
    dfTree = pd.read_sql(str_sql.format(str_tree), connection)
    
    connection.close()
    del str_sql, connection
    
    #%%
    nd = fu.Node(str_tree, dfTree)    
    dic_books = nd.to_inv_dict(str_tree)    
    del nd, dfTree, str_tree
    
    #%%
    dfPrimitive['trader'] = dfPrimitive['book'].apply(lambda x: dic_books[x])
    
    #%%
    dfEquity = dfPrimitive[(dfPrimitive['primitive_class'] == 'Equity') & (dfPrimitive['product_currency'] == 'BRL')].pivot_table(index=['trader','primitive'], columns='trading_desk', values='delta_perc', aggfunc=np.sum).fillna(0)
    dfEquity['Diff'] = dfEquity['A1 Master FIM']- dfEquity[str_fund_compared]
    index_positivo = dfEquity.index.get_level_values('primitive').str[0:4].isin(lista_positiva)
    dfEquity.loc[index_positivo, 'ListaPositiva'] = dfEquity.loc[index_positivo, str_fund_compared]
    dfEquity['Diff2'] = dfEquity['A1 Master FIM']- dfEquity['ListaPositiva']
    #%%
    dfFX = dfPrimitive[dfPrimitive['primitive_class'] == 'FX'].copy()
    dfFX['primitive'] = dfFX['primitive'].str.replace('Spot','')
    dfFX = dfFX.pivot_table(index=['trader','primitive'], columns='trading_desk', values='delta_perc', aggfunc=np.sum).fillna(0)
    dfFX['Diff'] = dfFX['A1 Master FIM']- dfFX[str_fund_compared]
    
    #%%
    dic_risk={}
    for tree in dfRisk['parent_tree'].unique():
        if tree != 'Geography':
            dic_risk[tree] = dfRisk[dfRisk['parent_tree']==tree].pivot(index='node', columns=['risk_measure','trading_desk'], values='val_perc').fillna(0)
            for r in ['VaR', 'Stress']:
                dic_risk[tree][(r, 'Diff')] = dic_risk[tree][(r)]['A1 Master FIM']- dic_risk[tree][(r)][str_fund_compared]
            dic_risk[tree] = dic_risk[tree][sorted(dic_risk[tree].columns)]
        
    #%%
    excel_file = xw.Book()
    for k, df_v in dic_risk.items():
        str_sheet = "VaR_Stress_" + k
        excel_file.sheets.add(str_sheet)
        sht = excel_file.sheets[str_sheet]
        sht.cells(1, 1).value = df_v
        sht.range('A1:Z2').api.Font.Bold = True
        sht.range('A1:A500').api.Font.Bold = True
        sht.range('B3:Z500').number_format = "0.00%;[Red]-0.00%;-"
        sht.autofit(axis='c')
    
    str_sheet = "Equity Delta"
    excel_file.sheets.add(str_sheet)
    sht = excel_file.sheets[str_sheet]
    sht.cells(1, 1).value = dfEquity
    sht.range('A1:Z1').api.Font.Bold = True
    sht.range('A1:B500').api.Font.Bold = True
    sht.range('B2:Z500').number_format = "0.00%;[Red]-0.00%;-"
    sht.autofit(axis='c')
    
    str_sheet = "FX Delta"
    excel_file.sheets.add(str_sheet)
    sht = excel_file.sheets[str_sheet]
    sht.cells(1, 1).value = dfFX
    sht.range('A1:Z1').api.Font.Bold = True
    sht.range('A1:B500').api.Font.Bold = True
    sht.range('B2:Z500').number_format = "0.00%;[Red]-0.00%;-"
    sht.autofit(axis='c')
    
    str_path = 'R:\\Risk\\01_DailyReports\\Master Hedge Comparison\\'
    str_newfile = str_path + "{:%Y%m%d}_".format(dt) + "Master_{}_comparacao.xlsx".format(str_fund_compared)
    excel_file.save(path = str_newfile)
    
        #     first_row = 2
        #     for i, (_, prod_id) in enumerate(df[df['prod_type'] == prod_type].values):
        #         prod_address = excel_file.sheets[prod_type].cells(first_row + i, 1).get_address()
        #         excel_file.sheets[prod_type].range(prod_address).value = prod_id
        #         for j, (f, num_format) in enumerate(zip(broadcast_fields, format_fields)):
        #             excel_file.sheets[prod_type].cells(first_row + i, 2+j).formula = '=BC({},"{}")'.format(prod_address, f)
        #             excel_file.sheets[prod_type].cells(first_row + i, 2+j).number_format = num_format
        #     excel_file.app.calculate()
        # excel_file.save()

if __name__ == '__main__':
    
    dt = datetime.date(2022, 6, 29)
    main(dt,'A1 Orange FIM')
    main(dt,'A1 FIFE BEM')