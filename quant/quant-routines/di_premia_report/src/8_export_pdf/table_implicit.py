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

def add_multirow_implicit(doc, df):
    doc.append(NoEscape(r'\definecolor{LightCyan}{rgb}{0.88,.88,.88}'))
    doc.append(NoEscape(r'\definecolor{HeaderColor}{rgb}{.93,.93,.93}'))
    
    print(df)
    highlight_color = NoEscape(r'c')

    header_color = r'c'

    table1 = Tabular(NoEscape(r'c c c c c ') )
    
    table1.add_hline(start=2)
    table1.add_row((
        '', 
        MultiColumn(1, align=NoEscape( r'|'+ header_color ), data='Todos'),
        MultiColumn(1, align=NoEscape( header_color ), data='Corte'),
        MultiColumn(1, align=NoEscape( header_color ), data='Manut.'),
        MultiColumn(1, align=NoEscape( header_color + r'|' ), data='Hike'),
    ))
    table1.add_hline()
    row_index = 0
    table1.add_row((
        MultiColumn(1, align=NoEscape( r'|' ) + header_color + NoEscape( r'|' ), data=NoEscape(r'Max\footnote{calculado pela média dos valores maiores que p95}')), 
        MultiColumn(1, align=highlight_color, data= '%.0f' % df[ df.columns[0] ][ df.index[row_index] ] ),
        MultiColumn(1, align=highlight_color, data= '%.0f' % df[ df.columns[1] ][ df.index[row_index] ] ),
        MultiColumn(1, align=highlight_color, data= '%.0f' % df[ df.columns[2] ][ df.index[row_index] ] ),
        MultiColumn(1, align=highlight_color + r'|', data= '%.0f' % df[ df.columns[3] ][ df.index[row_index] ] ),
    ))
    table1.add_hline()
    row_index = 1
    table1.add_row((
        MultiColumn(1, align=NoEscape( r'|' ) + header_color + NoEscape( r'|' ), data=NoEscape(r'Min\footnote{calculado pela média dos valores menores que p05}')), 
        MultiColumn(1, align=highlight_color, data= '%.0f' % df[ df.columns[0] ][ df.index[row_index] ] ),
        MultiColumn(1, align=highlight_color, data= '%.0f' % df[ df.columns[1] ][ df.index[row_index] ] ),
        MultiColumn(1, align=highlight_color, data= '%.0f' % df[ df.columns[2] ][ df.index[row_index] ] ),
        MultiColumn(1, align=highlight_color + r'|', data= '%.0f' % df[ df.columns[3] ][ df.index[row_index] ] ),
    ))
    table1.add_hline()
    row_index = 2
    table1.add_row((
        MultiColumn(1, align=NoEscape( r'|' ) + header_color + NoEscape( r'|' ), data='Média'), 
        MultiColumn(1, align=highlight_color, data= '%.0f' % df[ df.columns[0] ][ df.index[row_index] ] ),
        MultiColumn(1, align=highlight_color, data= '%.0f' % df[ df.columns[1] ][ df.index[row_index] ] ),
        MultiColumn(1, align=highlight_color, data= '%.0f' % df[ df.columns[2] ][ df.index[row_index] ] ),
        MultiColumn(1, align=highlight_color + r'|', data= '%.0f' % df[ df.columns[3] ][ df.index[row_index] ] ),
    ))
    table1.add_hline()
    row_index = 3
    table1.add_row((
        MultiColumn(1, align=NoEscape( r'|' ) + header_color + NoEscape( r'|' ), data='Mediana'), 
        MultiColumn(1, align=highlight_color, data= '%.0f' % df[ df.columns[0] ][ df.index[row_index] ] ),
        MultiColumn(1, align=highlight_color, data= '%.0f' % df[ df.columns[1] ][ df.index[row_index] ] ),
        MultiColumn(1, align=highlight_color, data= '%.0f' % df[ df.columns[2] ][ df.index[row_index] ] ),
        MultiColumn(1, align=highlight_color + r'|', data= '%.0f' % df[ df.columns[3] ][ df.index[row_index] ] ),
    ))
    table1.add_hline()
    row_index = 4
    table1.add_row((
        MultiColumn(1, align=NoEscape( r'|' ) + header_color + NoEscape( r'|' ), data='Desv. Padrão'), 
        MultiColumn(1, align=highlight_color, data= '%.0f' % df[ df.columns[0] ][ df.index[row_index] ] ),
        MultiColumn(1, align=highlight_color, data= '%.0f' % df[ df.columns[1] ][ df.index[row_index] ] ),
        MultiColumn(1, align=highlight_color, data= '%.0f' % df[ df.columns[2] ][ df.index[row_index] ] ),
        MultiColumn(1, align=highlight_color + r'|', data= '%.0f' % df[ df.columns[3] ][ df.index[row_index] ] ),
    ))
    table1.add_hline()
    row_index = 5
    table1.add_row((
        MultiColumn(1, align=NoEscape( r'|' ) + header_color + NoEscape( r'|' ), data='Último prêmio'), 
        MultiColumn(1, align=highlight_color, data= '%.0f' % df[ df.columns[0] ][ df.index[row_index] ] ),
        MultiColumn(1, align=highlight_color, data= '%.0f' % df[ df.columns[1] ][ df.index[row_index] ] ),
        MultiColumn(1, align=highlight_color, data= '%.0f' % df[ df.columns[2] ][ df.index[row_index] ] ),
        MultiColumn(1, align=highlight_color+ r'|', data= '%.0f' % df[ df.columns[3] ][ df.index[row_index] ] ),
    ))
    table1.add_hline()
    row_index = 6
    table1.add_row((
        MultiColumn(1, align=NoEscape( r'|' ) + header_color + NoEscape( r'|' ), data='Última data'), 
        MultiColumn(1, align=highlight_color, data=df[ df.columns[0] ][ df.index[row_index] ].strftime('%Y-%m-%d') ),
        MultiColumn(1, align=highlight_color, data=df[ df.columns[1] ][ df.index[row_index] ].strftime('%Y-%m-%d') ),
        MultiColumn(1, align=highlight_color, data=df[ df.columns[2] ][ df.index[row_index] ].strftime('%Y-%m-%d') ),
        MultiColumn(1, align=highlight_color+ r'|', data=df[ df.columns[3] ][ df.index[row_index] ].strftime('%Y-%m-%d') ),
    ))
    table1.add_hline()
    doc.append(table1)
    return doc