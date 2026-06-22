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
from table_di import add_multirow_di
from table_inclination import add_multirow_inclination
from table_implicit import add_multirow_implicit

def setup_document(output_path):
    # Document with `\maketitle` command activated
    geometry_options = {
        "head": "0pt",
        "margin": "0.5in",
        "bottom": "0.5in",
        "includeheadfoot": True
    }
    doc = Document(
        default_filepath="%s/di_premia_report" % output_path,
        geometry_options=geometry_options
    )
    # Add package
    doc.packages.append(Package('placeins', options='section'))
    doc.packages.append(Package('float'))
    doc.packages.append(Package('xcolor'))
    doc.packages.append(Package('colortbl'))

    doc.append( NoEscape(r"\setcounter{section}{3}") )
    doc.append( NoEscape(r"\setcounter{page}{10}") )
    return doc

def fill_document(doc, input_path):
    images_path_dict = {
        'di_series_6m': '%s/%s' % ( input_path, '1_a_6M.png' ),
        'di_hist_6m': '%s/%s' % ( input_path, '1_b_6M.png' ),
        'di_series_1y': '%s/%s' % ( input_path, '2_a_1Y.png' ),
        'di_hist_1y': '%s/%s' % ( input_path, '2_b_1Y.png' ),
        'di_series_2y': '%s/%s' % ( input_path, '3_a_2Y.png' ),
        'di_hist_2y': '%s/%s' % ( input_path, '3_b_2Y.png' ),
        '2_1_series': '%s/%s' % ( input_path, '4_a_2Y-1Y.png' ),
        '2_1_hist': '%s/%s' % ( input_path, '4_b_2Y-1Y.png' ),
        '5_2_series': '%s/%s' % ( input_path, '5_a_5Y-2Y.png' ),
        '5_2_hist': '%s/%s' % ( input_path, '5_b_5Y-2Y.png' ),
        'implicit_series': '%s/%s' % ( input_path, '6_a_implicit_1y.png' ),
        'implicit_hist': '%s/%s' % ( input_path, '6_b_implicit_1y.png' ),
        'implicit_2y_series': '%s/%s' % ( input_path, '6b_a_implicit_2y.png' ),
        'implicit_2y_hist': '%s/%s' % ( input_path, '6b_b_implicit_2y.png' ),
        'target_implicit_1y_series': '%s/%s' % ( input_path, '6c_a_target_implicit_1y.png' ),
        'target_implicit_1y_hist': '%s/%s' % ( input_path, '6c_b_target_implicit_1y.png' ),
        'target_implicit_2y_series': '%s/%s' % ( input_path, '6d_a_target_implicit_2y.png' ),
        'target_implicit_2y_hist': '%s/%s' % ( input_path, '6d_b_target_implicit_2y.png' ),        
        'flat_6m-selic_series': '%s/%s' % ( input_path, '7_a_flat_6m-selic.png' ),
        'flat_6m-selic_hist': '%s/%s' % ( input_path, '7_b_flat_6m-selic.png' ),
        'flat_1y-selic_series': '%s/%s' % ( input_path, '8_a_flat_1y-selic.png' ),
        'flat_1y-selic_hist': '%s/%s' % ( input_path, '8_b_flat_1y-selic.png' ),
        'flat_2y-selic_series': '%s/%s' % ( input_path, '9_a_flat_2y-selic.png' ),
        'flat_2y-selic_hist': '%s/%s' % ( input_path, '9_b_flat_2y-selic.png' ),
        'flat_2y-1y_series': '%s/%s' % ( input_path, '10_a_flat_2y-1y.png' ),
        'flat_2y-1y_hist': '%s/%s' % ( input_path, '10_b_flat_2y-1y.png' ),
        'flat_5y-2y_series': '%s/%s' % ( input_path, '11_a_flat_5y-2y.png' ),
        'flat_5y-2y_hist': '%s/%s' % ( input_path, '11_b_flat_5y-2y.png' ),
    }

    # Import data
    dataframe_di = pd.read_excel( '%s/%s' % (input_path, 'di.xlsx'), index_col=0)
    dataframe_steepness = pd.read_excel( '%s/%s' % (input_path, 'steepness.xlsx'), index_col=0)
    dataframe_implicit_1y = pd.read_excel( '%s/%s' % (input_path, 'implicit_1y.xlsx'), index_col=0)
    dataframe_implicit_2y = pd.read_excel( '%s/%s' % (input_path, 'implicit_2y.xlsx'), index_col=0)    
    dataframe_target_implicit_1y = pd.read_excel( '%s/%s' % (input_path, 'target_implicit_1y.xlsx'), index_col=0)
    dataframe_target_implicit_2y = pd.read_excel( '%s/%s' % (input_path, 'target_implicit_2y.xlsx'), index_col=0)    
    dataframe_flat_vs_selic = pd.read_excel( '%s/%s' % (input_path, 'flat_vs_selic.xlsx'), index_col=0)
    dataframe_flat_steepness = pd.read_excel( '%s/%s' % (input_path, 'flat_steepness.xlsx'), index_col=0)
    
    # Compose document
    with doc.create(Section('Relatório de prêmio')):
        # _________________________________________________________________
        with doc.create(Subsection('Prêmio 6M')):
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\begin{minipage}{\textwidth}") )

            # Add DI 6M table
            doc.append( NoEscape(r"\centering") )
            doc.append( NoEscape(r"\hspace*{-0.3in}") )
            doc = add_multirow_di(doc, dataframe_di, selector='6m')
            
            # Add DI 6M graphs
            with doc.create(Figure(position='H')) as image:
                image.add_image( images_path_dict['di_series_6m'], width='500px')
            with doc.create(Figure(position='H')) as image:
                doc.append( NoEscape(r"\hspace*{-0.7in}") )
                image.add_image( images_path_dict['di_hist_6m'], width='435px')
            
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\end{minipage}") )
            doc.append( NoEscape(r"\pagebreak") )
        # _________________________________________________________________
        with doc.create(Subsection('Prêmio 1Y')):
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\begin{minipage}{\textwidth}") )

            # Add DI 1Y table
            doc.append( NoEscape(r"\vspace*{0.4in}") )
            doc.append( NoEscape(r"\centering") )
            doc.append( NoEscape(r"\hspace*{-0.3in}") )
            doc = add_multirow_di(doc, dataframe_di, selector='1y')

            # Add DI 1Y graph
            with doc.create(Figure(position='H')) as image:
                image.add_image( images_path_dict['di_series_1y'], width='500px')
            with doc.create(Figure(position='H')) as image:
                doc.append( NoEscape(r"\hspace*{-0.7in}") )
                image.add_image( images_path_dict['di_hist_1y'], width='435px')
            
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\end{minipage}") )
            doc.append( NoEscape(r"\pagebreak") )
        # _________________________________________________________________
        with doc.create(Subsection('Prêmio 2Y')):
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\begin{minipage}{\textwidth}") )

            # Add DI 2Y table
            doc.append( NoEscape(r"\vspace*{0.4in}") )
            doc.append( NoEscape(r"\centering") )
            doc.append( NoEscape(r"\hspace*{-0.3in}") )
            doc = add_multirow_di(doc, dataframe_di, selector='2y')

            # Add DI 2Y graph
            with doc.create(Figure(position='H')) as image:
                image.add_image( images_path_dict['di_series_2y'], width='500px')
            with doc.create(Figure(position='H')) as image:
                doc.append( NoEscape(r"\hspace*{-0.7in}") )
                image.add_image( images_path_dict['di_hist_2y'], width='435px')

            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\end{minipage}") )
            doc.append( NoEscape(r"\pagebreak") )
        # _________________________________________________________________
        with doc.create(Subsection('Prêmio 2Y - 1Y')):
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\begin{minipage}{\textwidth}") )

            # Add 2Y - 1Y table
            doc.append( NoEscape(r"\vspace*{0.4in}") )
            doc.append( NoEscape(r"\centering") )
            doc.append( NoEscape(r"\hspace*{-0in}") )
            doc = add_multirow_inclination(doc, dataframe_steepness, selector='2_1')
            
            # Add 2Y - 1Y graphs
            with doc.create(Figure(position='H')) as image:
                image.add_image( images_path_dict['2_1_series'], width='500px')
            with doc.create(Figure(position='H')) as image:
                doc.append( NoEscape(r"\hspace*{-0.7in}") )
                image.add_image( images_path_dict['2_1_hist'], width='435px')
            
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\end{minipage}") )
            doc.append( NoEscape(r"\pagebreak") )
        # _________________________________________________________________
        with doc.create(Subsection('Prêmio 5Y - 2Y')):
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\begin{minipage}{\textwidth}") )

            # Add 5Y - 2Y table
            doc.append( NoEscape(r"\vspace*{0.4in}") )
            doc.append( NoEscape(r"\centering") )
            doc.append( NoEscape(r"\hspace*{-0.3in}") )
            doc = add_multirow_inclination(doc, dataframe_steepness, selector='5_2')
            
            # Add 5Y - 2Y graphs
            with doc.create(Figure(position='H')) as image:
                image.add_image( images_path_dict['5_2_series'], width='500px')
            with doc.create(Figure(position='H')) as image:
                doc.append( NoEscape(r"\hspace*{-0.7in}") )
                image.add_image( images_path_dict['5_2_hist'], width='435px')
            
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\end{minipage}") )
            doc.append( NoEscape(r"\pagebreak") )
        # _________________________________________________________________
        with doc.create(Subsection('Relatório de implícita 1Y (Mercado vs Focus)')):
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\begin{minipage}{\textwidth}") )

            # Add implicit table
            doc.append( NoEscape(r"\vspace*{0.4in}") )
            doc.append( NoEscape(r"\centering") )
            doc.append( NoEscape(r"\hspace*{-0.3in}") )
            doc = add_multirow_implicit(doc, dataframe_implicit_1y)
            
            # Add implicit graphs
            with doc.create(Figure(position='H')) as image:
                image.add_image( images_path_dict['implicit_series'], width='500px')
            with doc.create(Figure(position='H')) as image:
                doc.append( NoEscape(r"\hspace*{-0.7in}") )
                image.add_image( images_path_dict['implicit_hist'], width='435px')
            
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\end{minipage}") )
            doc.append( NoEscape(r"\pagebreak") )
        # _________________________________________________________________
        with doc.create(Subsection('Relatório de implícita 2Y (Mercado vs Focus)')):
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\begin{minipage}{\textwidth}") )

            # Add implicit table
            doc.append( NoEscape(r"\vspace*{0.4in}") )
            doc.append( NoEscape(r"\centering") )
            doc.append( NoEscape(r"\hspace*{-0.3in}") )
            doc = add_multirow_implicit(doc, dataframe_implicit_2y)
            
            # Add implicit graphs
            with doc.create(Figure(position='H')) as image:
                image.add_image( images_path_dict['implicit_2y_series'], width='500px')
            with doc.create(Figure(position='H')) as image:
                doc.append( NoEscape(r"\hspace*{-0.7in}") )
                image.add_image( images_path_dict['implicit_2y_hist'], width='435px')
            
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\end{minipage}") )
            doc.append( NoEscape(r"\pagebreak") )
        # _________________________________________________________________
        with doc.create(Subsection('Relatório de implícita 1Y (Mercado vs Meta)')):
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\begin{minipage}{\textwidth}") )

            # Add implicit table
            doc.append( NoEscape(r"\vspace*{0.4in}") )
            doc.append( NoEscape(r"\centering") )
            doc.append( NoEscape(r"\hspace*{-0.3in}") )
            doc = add_multirow_implicit(doc, dataframe_target_implicit_2y)
            
            # Add implicit graphs
            with doc.create(Figure(position='H')) as image:
                image.add_image( images_path_dict['target_implicit_1y_series'], width='500px')
            with doc.create(Figure(position='H')) as image:
                doc.append( NoEscape(r"\hspace*{-0.7in}") )
                image.add_image( images_path_dict['target_implicit_1y_hist'], width='435px')
            
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\end{minipage}") )
            doc.append( NoEscape(r"\pagebreak") )
        # _________________________________________________________________
        with doc.create(Subsection('Relatório de implícita 2Y (Mercado vs Meta)')):
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\begin{minipage}{\textwidth}") )

            # Add implicit table
            doc.append( NoEscape(r"\vspace*{0.4in}") )
            doc.append( NoEscape(r"\centering") )
            doc.append( NoEscape(r"\hspace*{-0.3in}") )
            doc = add_multirow_implicit(doc, dataframe_target_implicit_2y)
            
            # Add implicit graphs
            with doc.create(Figure(position='H')) as image:
                image.add_image( images_path_dict['target_implicit_2y_series'], width='500px')
            with doc.create(Figure(position='H')) as image:
                doc.append( NoEscape(r"\hspace*{-0.7in}") )
                image.add_image( images_path_dict['target_implicit_2y_hist'], width='435px')
            
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\end{minipage}") )
            doc.append( NoEscape(r"\pagebreak") )
        # _________________________________________________________________
        with doc.create(Subsection('Inclinação 6M-SELIC (SEM SUBTRAÇÃO FOCUS)')):
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\begin{minipage}{\textwidth}") )

            # Add implicit table
            doc.append( NoEscape(r"\vspace*{0.4in}") )
            doc.append( NoEscape(r"\centering") )
            doc.append( NoEscape(r"\hspace*{-0.3in}") )
            doc = add_multirow_di(doc, dataframe_flat_vs_selic)
            
            # Add implicit graphs
            with doc.create(Figure(position='H')) as image:
                image.add_image( images_path_dict['flat_6m-selic_series'], width='500px')
            with doc.create(Figure(position='H')) as image:
                doc.append( NoEscape(r"\hspace*{-0.7in}") )
                image.add_image( images_path_dict['flat_6m-selic_hist'], width='435px')
            
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\end{minipage}") )
            doc.append( NoEscape(r"\pagebreak") )
        # _________________________________________________________________
        with doc.create(Subsection('Inclinação 1Y-SELIC (SEM SUBTRAÇÃO FOCUS)')):
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\begin{minipage}{\textwidth}") )

            # Add implicit table
            doc.append( NoEscape(r"\vspace*{0.4in}") )
            doc.append( NoEscape(r"\centering") )
            doc.append( NoEscape(r"\hspace*{-0.3in}") )
            doc = add_multirow_di(doc, dataframe_flat_vs_selic)
            
            # Add implicit graphs
            with doc.create(Figure(position='H')) as image:
                image.add_image( images_path_dict['flat_1y-selic_series'], width='500px')
            with doc.create(Figure(position='H')) as image:
                doc.append( NoEscape(r"\hspace*{-0.7in}") )
                image.add_image( images_path_dict['flat_1y-selic_hist'], width='435px')
            
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\end{minipage}") )
            doc.append( NoEscape(r"\pagebreak") )
        # _________________________________________________________________
        with doc.create(Subsection('Inclinação 2Y-SELIC (SEM SUBTRAÇÃO FOCUS)')):
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\begin{minipage}{\textwidth}") )

            # Add implicit table
            doc.append( NoEscape(r"\vspace*{0.4in}") )
            doc.append( NoEscape(r"\centering") )
            doc.append( NoEscape(r"\hspace*{-0.3in}") )
            doc = add_multirow_di(doc, dataframe_flat_vs_selic)
            
            # Add implicit graphs
            with doc.create(Figure(position='H')) as image:
                image.add_image( images_path_dict['flat_2y-selic_series'], width='500px')
            with doc.create(Figure(position='H')) as image:
                doc.append( NoEscape(r"\hspace*{-0.7in}") )
                image.add_image( images_path_dict['flat_2y-selic_hist'], width='435px')
            
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\end{minipage}") )
            doc.append( NoEscape(r"\pagebreak") )
        # _________________________________________________________________
        with doc.create(Subsection('Inclinação 2Y-1Y (SEM SUBTRAÇÃO FOCUS)')):
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\begin{minipage}{\textwidth}") )

            # Add implicit table
            doc.append( NoEscape(r"\vspace*{0.4in}") )
            doc.append( NoEscape(r"\centering") )
            doc.append( NoEscape(r"\hspace*{-0.3in}") )
            doc = add_multirow_inclination(doc, dataframe_flat_steepness)
            
            # Add implicit graphs
            with doc.create(Figure(position='H')) as image:
                image.add_image( images_path_dict['flat_2y-1y_series'], width='500px')
            with doc.create(Figure(position='H')) as image:
                doc.append( NoEscape(r"\hspace*{-0.7in}") )
                image.add_image( images_path_dict['flat_2y-1y_hist'], width='435px')
            
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\end{minipage}") )
            doc.append( NoEscape(r"\pagebreak") )
        # _________________________________________________________________
        with doc.create(Subsection('Inclinação 5Y-2Y (SEM SUBTRAÇÃO FOCUS)')):
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\begin{minipage}{\textwidth}") )

            # Add implicit table
            doc.append( NoEscape(r"\vspace*{0.4in}") )
            doc.append( NoEscape(r"\centering") )
            doc.append( NoEscape(r"\hspace*{-0.3in}") )
            doc = add_multirow_inclination(doc, dataframe_flat_steepness)
            
            # Add implicit graphs
            with doc.create(Figure(position='H')) as image:
                image.add_image( images_path_dict['flat_5y-2y_series'], width='500px')
            with doc.create(Figure(position='H')) as image:
                doc.append( NoEscape(r"\hspace*{-0.7in}") )
                image.add_image( images_path_dict['flat_5y-2y_hist'], width='435px')
            
            # This is to fix usage of footnote on table
            doc.append( NoEscape(r"\end{minipage}") )
            doc.append( NoEscape(r"\pagebreak") )
     
if __name__ == '__main__':
    output_path = '../../output/8_export_pdf'
    input_path = '../../output/6_plot'

    # Create output folder
    for folder in ['../../output', output_path]:
        if not os.path.exists(folder):
            os.makedirs(folder)

    doc = setup_document(output_path)
    fill_document(doc, input_path)

    doc.generate_pdf( "%s/di_premia_report" % output_path, clean_tex=False, compiler = 'pdfLaTeX' )
    tex = doc.dumps()  # The document as string in LaTeX syntax