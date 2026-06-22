# -*- coding: utf-8 -*-
"""
Created on Mon Aug  8 15:19:59 2022

@author: matheus.amaral
"""

from datetime import date
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from a1db.a1sql import SQLConnection
import QuantLib as ql
import fund_utils as fu
import xlwings as xw
    
def main(dt,report_filename, str_fund = 'A1 Master FIM'):
    data = 'Risk'
    
    calendar = ql.Brazil()
    dt_1 = calendar.advance(ql.Date.from_date(dt), ql.Period('-1d')).to_date()
    
    connection = SQLConnection().get_connection()
    
    str_sql = f"""
            SELECT b.book,
                SUM(b.value/n.NAV) * 10000 AS pnl_bps
            FROM lote45.book_overview b
            INNER JOIN middle.NAV n
                ON  b.date_reference = n.date_reference
                AND b.trading_desk = n.trading_desk
            WHERE b.date_reference = '{dt:%Y-%m-%d}'
                AND b.trading_desk = '{str_fund}'
                AND b.measure = 'PL'
            GROUP BY b.book
            """
    df = pd.read_sql(str_sql, connection)
    
    str_sql = f"""
            SELECT *
            FROM lote45.book_tree
            WHERE parent_tree = '{data}'
            """
    nd = fu.Node(data, pd.read_sql(str_sql, connection))
    dic_books = nd.to_inv_dict(data)
    
    df[data] = df['book'].apply(lambda x: dic_books[x])
    
    dfPnl = df.pivot_table(index = data,
                           values = 'pnl_bps',
                           aggfunc = np.sum).fillna(0)
    
    str_sql = f"""
            SELECT r.node,
                r.value / n.NAV * 10000 as var_bps
            FROM risk.measure r
            INNER JOIN middle.NAV n
                ON r.date_reference = n.date_reference
                AND r.trading_desk = n.trading_desk
            WHERE r.date_reference = '{dt_1:%Y-%m-%d}'
                AND r.trading_desk = '{str_fund}'
                AND r.risk_measure = 'VaR'
                AND r.parent_tree = '{data}'
            """
    dfVar = pd.read_sql(str_sql, connection, index_col = 'node')
    
    dfOutput = dfPnl.join(dfVar)
    
    color1,color2 = fu.color_palette[0],fu.color_palette[1]
    
    fig, ax = plt.subplots(figsize = (10,7))
    
    ax.step(dfOutput.index, dfOutput['var_bps'],
            color = color1, label = f'VaR (BPs) - {dt_1:%m/%d}',
            where = 'mid')
    ax.bar(dfOutput.index, dfOutput['pnl_bps'],
           color = (dfOutput['pnl_bps'] >= dfOutput['var_bps']).map({True:color2, False:'tomato'}),
            label = f'Pnl (BPs) - {dt:%m/%d}')
    ax.bar_label(ax.containers[0],fmt = '%.2f', label_type = 'center')
    for x,y in zip(dfOutput.index,dfOutput['var_bps']):
        ax.annotate(f'{y:.2f}', (x,y), textcoords = 'offset points',
                    xytext = (0,-12), ha = 'center', fontweight = 'bold')
    ax.axhline(0, color = color1)
    ax.set_ylim(bottom = dfOutput.values.min() * 1.1, top = 1.1*dfOutput.values.max())
    plt.xticks(rotation = 30)
    plt.legend(loc = 'lower left')
    plt.title('Pnl x VaR by Risk', fontsize = 14,fontweight = 'bold')

    fig_file = '../output/temp_figs/{:%Y%m%d}_var_pnl_breakdown_breakdown.svg'.format(dt)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    
    wb = xw.Book(report_filename)
    wb.sheets('Var_breakdown').range('Aviso').value = 'TRUE'
    wb.sheets('Var_breakdown').pictures.add(wb.api.Path + '/' + fig_file, name = 'var_pnl_breakdown', update = True)

#%%
if __name__ == '__main__':
    
    dt = date(2022,7,28)
    str_fund = 'A1 Master FIM'
    report_filename = '../xls/RiskMap_model.xlsm'
    
    main(dt,report_filename)