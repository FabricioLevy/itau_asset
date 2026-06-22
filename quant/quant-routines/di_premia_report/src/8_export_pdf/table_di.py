from pylatex import (
    Document, 
    Section,
    Subsection, 
    Tabular, 
    Math, 
    TikZ, 
    Axis,
    Plot, 
    Figure, 
    Matrix, 
    Alignat,
    Command,
    Package,
    Math,
    MultiRow,
    MultiColumn,
)
from pylatex.utils import italic, NoEscape
import os
import pandas as pd

def add_multirow_di(doc, df, selector='6m'):
    doc.append(NoEscape(r'\definecolor{LightCyan}{rgb}{0.97,.97,.97}'))
    doc.append(NoEscape(r'\definecolor{HeaderColor}{rgb}{.97,.97,.97}'))
    
    highlight_color = NoEscape(r'>{\columncolor{LightCyan}}c')
    highlight_color = NoEscape(r'c')
    column_color_6m = NoEscape( r'c' )
    column_color_1y = NoEscape( r'c' )
    column_color_2y = NoEscape( r'c' )
    if selector == '6m':
        column_color_6m = highlight_color
    elif selector == '1y':
        column_color_1y = highlight_color
    elif selector == '2y':
        column_color_2y = highlight_color
    header_color = r'c'

    print(df)
    print(df.columns)
    table1 = Tabular(NoEscape(r'c c c c c c c c c c c c c ') )
    
    table1.add_hline(start=2)
    table1.add_row((
        '', 
        MultiColumn(4, align=NoEscape( r'|' + header_color + r'|' ), data='6M'),
        MultiColumn(4, align=NoEscape( header_color + r'|' ), data='1Y'),
        MultiColumn(4, align=NoEscape( header_color + r'|' ), data='2Y'),
    ))

    table1.add_row((
        '', 
        MultiColumn(1, align=NoEscape( r'|' + header_color ), data='Todos'),
        MultiColumn(1, align=NoEscape( header_color ), data='Cut'),
        MultiColumn(1, align=NoEscape( header_color ), data='Manut'),
        MultiColumn(1, align=NoEscape( header_color + r'|' ), data='Hike'),

        MultiColumn(1, align=NoEscape( header_color ), data='Todos'),
        MultiColumn(1, align=NoEscape( header_color ), data='Cut'),
        MultiColumn(1, align=NoEscape( header_color ), data='Manut'),
        MultiColumn(1, align=NoEscape( header_color + r'|' ), data='Hike'),

        MultiColumn(1, align=NoEscape( header_color ), data='Todos'),
        MultiColumn(1, align=NoEscape( header_color ), data='Cut'),
        MultiColumn(1, align=NoEscape( header_color ), data='Manut'),
        MultiColumn(1, align=NoEscape( header_color + r'|' ), data='Hike'),
    ))
    table1.add_hline()
    row_index = 0
    table1.add_row((
        MultiColumn(1, align=NoEscape( r'|' ) + header_color + NoEscape( r'|' ), data=NoEscape(r'Max\footnote{calculado pela média dos valores maiores que p95}')), 

        MultiColumn(1, align=column_color_6m, data= '%.0f' % df[ df.columns[0] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_6m, data= '%.0f' % df[ df.columns[1] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_6m, data= '%.0f' % df[ df.columns[2] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_6m + NoEscape( r'|' ), data= '%.0f' % df[ df.columns[3] ][ df.index[row_index] ] ),

        MultiColumn(1, align=column_color_1y, data= '%.0f' % df[ df.columns[4] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_1y, data= '%.0f' % df[ df.columns[5] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_1y, data= '%.0f' % df[ df.columns[6] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_1y + NoEscape( r'|' ), data= '%.0f' % df[ df.columns[7] ][ df.index[row_index] ] ),

        MultiColumn(1, align=column_color_2y, data= '%.0f' % df[ df.columns[8] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_2y, data= '%.0f' % df[ df.columns[9] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_2y, data= '%.0f' % df[ df.columns[10] ][ df.index[row_index] ] ),        
        MultiColumn(1, align=column_color_2y + NoEscape( r'|' ), data= '%.0f' % df[ df.columns[11] ][ df.index[row_index] ] ),
    ))
    table1.add_hline()
    row_index = 1
    table1.add_row((
        MultiColumn(1, align=NoEscape( r'|' ) + header_color + NoEscape( r'|' ), data=NoEscape(r'Min\footnote{calculado pela média dos valores menores que p05}')), 

        MultiColumn(1, align=column_color_6m, data= '%.0f' % df[ df.columns[0] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_6m, data= '%.0f' % df[ df.columns[1] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_6m, data= '%.0f' % df[ df.columns[2] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_6m + NoEscape( r'|' ), data= '%.0f' % df[ df.columns[3] ][ df.index[row_index] ] ),

        MultiColumn(1, align=column_color_1y, data= '%.0f' % df[ df.columns[4] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_1y, data= '%.0f' % df[ df.columns[5] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_1y, data= '%.0f' % df[ df.columns[6] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_1y + NoEscape( r'|' ), data= '%.0f' % df[ df.columns[7] ][ df.index[row_index] ] ),

        MultiColumn(1, align=column_color_2y, data= '%.0f' % df[ df.columns[8] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_2y, data= '%.0f' % df[ df.columns[9] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_2y, data= '%.0f' % df[ df.columns[10] ][ df.index[row_index] ] ),        
        MultiColumn(1, align=column_color_2y + NoEscape( r'|' ), data= '%.0f' % df[ df.columns[11] ][ df.index[row_index] ] ),
    ))
    table1.add_hline()
    row_index = 2
    table1.add_row((
        MultiColumn(1, align=NoEscape( r'|' ) + header_color + NoEscape( r'|' ), data='Média'), 

        MultiColumn(1, align=column_color_6m, data= '%.0f' % df[ df.columns[0] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_6m, data= '%.0f' % df[ df.columns[1] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_6m, data= '%.0f' % df[ df.columns[2] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_6m + NoEscape( r'|' ), data= '%.0f' % df[ df.columns[3] ][ df.index[row_index] ] ),
        
        MultiColumn(1, align=column_color_1y, data= '%.0f' % df[ df.columns[4] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_1y, data= '%.0f' % df[ df.columns[5] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_1y, data= '%.0f' % df[ df.columns[6] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_1y + NoEscape( r'|' ), data= '%.0f' % df[ df.columns[7] ][ df.index[row_index] ] ),
        
        MultiColumn(1, align=column_color_2y, data= '%.0f' % df[ df.columns[8] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_2y, data= '%.0f' % df[ df.columns[9] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_2y, data= '%.0f' % df[ df.columns[10] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_2y + NoEscape( r'|' ), data= '%.0f' % df[ df.columns[11] ][ df.index[row_index] ] ),
    ))
    table1.add_hline()
    row_index = 3
    table1.add_row((
        MultiColumn(1, align=NoEscape( r'|' ) + header_color + NoEscape( r'|' ), data='Mediana'), 

        MultiColumn(1, align=column_color_6m, data= '%.0f' % df[ df.columns[0] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_6m, data= '%.0f' % df[ df.columns[1] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_6m, data= '%.0f' % df[ df.columns[2] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_6m + NoEscape( r'|' ), data= '%.0f' % df[ df.columns[3] ][ df.index[row_index] ] ),
        
        MultiColumn(1, align=column_color_1y, data= '%.0f' % df[ df.columns[4] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_1y, data= '%.0f' % df[ df.columns[5] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_1y, data= '%.0f' % df[ df.columns[6] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_1y + NoEscape( r'|' ), data= '%.0f' % df[ df.columns[7] ][ df.index[row_index] ] ),

        MultiColumn(1, align=column_color_2y, data= '%.0f' % df[ df.columns[8] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_2y, data= '%.0f' % df[ df.columns[9] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_2y, data= '%.0f' % df[ df.columns[10] ][ df.index[row_index] ] ),        
        MultiColumn(1, align=column_color_2y + NoEscape( r'|' ), data= '%.0f' % df[ df.columns[11] ][ df.index[row_index] ] ),
    ))
    table1.add_hline()
    row_index = 4
    table1.add_row((
        MultiColumn(1, align=NoEscape( r'|' ) + header_color + NoEscape( r'|' ), data='Desv. Padrão'), 

        MultiColumn(1, align=column_color_6m, data= '%.0f' % df[ df.columns[0] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_6m, data= '%.0f' % df[ df.columns[1] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_6m, data= '%.0f' % df[ df.columns[2] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_6m + NoEscape( r'|' ), data= '%.0f' % df[ df.columns[3] ][ df.index[row_index] ] ),
        
        MultiColumn(1, align=column_color_1y, data= '%.0f' % df[ df.columns[4] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_1y, data= '%.0f' % df[ df.columns[5] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_1y, data= '%.0f' % df[ df.columns[6] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_1y + NoEscape( r'|' ), data= '%.0f' % df[ df.columns[7] ][ df.index[row_index] ] ),

        MultiColumn(1, align=column_color_2y, data= '%.0f' % df[ df.columns[8] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_2y, data= '%.0f' % df[ df.columns[9] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_2y, data= '%.0f' % df[ df.columns[10] ][ df.index[row_index] ] ),        
        MultiColumn(1, align=column_color_2y + NoEscape( r'|' ), data= '%.0f' % df[ df.columns[11] ][ df.index[row_index] ] ),
    ))
    table1.add_hline()
    row_index = 5
    table1.add_row((
        MultiColumn(1, align=NoEscape( r'|' ) + header_color + NoEscape( r'|' ), data='Último prêmio'), 

        MultiColumn(1, align=column_color_6m, data= '%.0f' % df[ df.columns[0] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_6m, data= '%.0f' % df[ df.columns[1] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_6m, data= '%.0f' % df[ df.columns[2] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_6m + NoEscape( r'|' ), data= '%.0f' % df[ df.columns[3] ][ df.index[row_index] ] ),
        
        MultiColumn(1, align=column_color_1y, data= '%.0f' % df[ df.columns[4] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_1y, data= '%.0f' % df[ df.columns[5] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_1y, data= '%.0f' % df[ df.columns[6] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_1y + NoEscape( r'|' ), data= '%.0f' % df[ df.columns[7] ][ df.index[row_index] ] ),
        
        MultiColumn(1, align=column_color_2y, data= '%.0f' % df[ df.columns[8] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_2y, data= '%.0f' % df[ df.columns[9] ][ df.index[row_index] ] ),
        MultiColumn(1, align=column_color_2y, data= '%.0f' % df[ df.columns[10] ][ df.index[row_index] ] ),        
        MultiColumn(1, align=column_color_2y + NoEscape( r'|' ), data= '%.0f' % df[ df.columns[11] ][ df.index[row_index] ] ),
    ))
    table1.add_hline()
    # row_index = 6
    # table1.add_row((
    #     MultiColumn(1, align=NoEscape( r'|' ) + header_color + NoEscape( r'|' ), data='Última data'), 

    #     MultiColumn(4, align=highlight_color + NoEscape( r'|' ), data=df[ df.columns[0] ][ df.index[row_index] ].strftime('%Y-%m-%d') ),
    #     MultiColumn(4, align=highlight_color + NoEscape( r'|' ), data=df[ df.columns[4] ][ df.index[row_index] ].strftime('%Y-%m-%d') ),
    #     MultiColumn(4, align=highlight_color + NoEscape( r'|' ), data=df[ df.columns[8] ][ df.index[row_index] ].strftime('%Y-%m-%d') ),
    # ))
    # table1.add_hline()
    doc.append(table1)
    return doc