from pylatex import (
    Document, 
    Section,
    Subsection, 
    Tabular, 
    LineBreak,
    Math, 
    TikZ, 
    Axis,
    Plot, 
    Figure, 
    SubFigure,
    Matrix, 
    Alignat,
    Command,
    Package,
    Math,
    MultiRow,
    MultiColumn,
)
from pylatex.utils import italic, NoEscape
import pandas as pd
import os 
import shutil

# _______________________________________________________________________________________________
# Configuration

input_path = '../../output/0_download_data'
input_path_2 = '../../output/1_process'
input_path_3 = '../../output/1_process/funds'
output_path = '../../output/2_generate_pdf'
output_path_2 = r'R:\Public\fund_position_analysis'
today = pd.Timestamp.today().strftime('%Y_%m_%d')

# _______________________________________________________________________________________________
# Create output path

for folder in ['../../output', output_path]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# _______________________________________________________________________________________________
# Process

def setup_document(output_path):
    # Document with `\maketitle` command activated
    geometry_options = {
        "head": "0pt",
        "margin": "0.5in",
        "bottom": "0.5in",
        "includeheadfoot": True
    }
    doc = Document(
        default_filepath=output_path,
        geometry_options=geometry_options
    )
    # Add package
    doc.packages.append(Package('placeins', options='section'))
    doc.packages.append(Package('float'))
    doc.packages.append(Package('xcolor'))
    doc.packages.append(Package('colortbl'))

    # doc.append( NoEscape(r"\setcounter{section}{3}") )
    # doc.append( NoEscape(r"\setcounter{page}{10}") )
    return doc

def fill_document(doc, input_path, fund):
    # Compose document
    # _________________________________________________________________
    with doc.create(Subsection('%s' % fund)):
        for key in [('PREDI720', 'IBOV'), ('USDBRL', 'SPX'), ('R2', 'RETURN')]:
            with doc.create(Figure(position='H')) as images:
                with doc.create(
                    SubFigure(
                        position='b',
                        width=NoEscape(r'0.50\linewidth')
                    )
                ) as image:
                    image.add_image( '%s/%s_%s.png' % (input_path, key[0], fund))
                with doc.create(
                    SubFigure(
                        position='b',
                        width=NoEscape(r'0.50\linewidth')
                    )
                ) as image:
                    image.add_image( '%s/%s_%s.png' % (input_path, key[1],  fund))
            doc.append( NoEscape(r"\vspace*{-.50in}") )
    doc.append( NoEscape(r"\pagebreak") )

def fill_document_3(doc, input_path):
    doc.append( NoEscape(r"\vspace*{-.2in}") )
    with doc.create(Figure(position='H')) as image:
        doc.append(Command('centering'))
        with doc.create(
            SubFigure(
                position='b',
                width=NoEscape(r'0.45\linewidth')
            )
        ) as image:
            image.add_image( '%s/005du.png' % input_path)
        with doc.create(
            SubFigure(
                position='b',
                width=NoEscape(r'0.45\linewidth')
            )
        ) as image:
            image.add_image( '%s/021du.png' % input_path)
    doc.append( NoEscape(r"\vspace*{-.2in}") )
    with doc.create(Figure(position='H')) as image:
        doc.append(Command('centering'))
        with doc.create(
            SubFigure(
                position='b',
                width=NoEscape(r'0.45\linewidth')
            )
        ) as image:
            image.add_image( '%s/126du.png' % input_path)
        with doc.create(
            SubFigure(
                position='b',
                width=NoEscape(r'0.45\linewidth')
            )
        ) as image:
            image.add_image( '%s/252du.png' % input_path)

def fill_document_2(doc, input_path):
    with doc.create( Section('Análise técnica') ):
        with doc.create( Subsection('Posição técnica média') ):
            with doc.create(Figure(position='H')) as images:
                doc.append(Command('centering'))
                images.add_image( 
                    '%s/compiled_result.png' % input_path,
                    width=NoEscape(r'0.70\linewidth')
                )
            doc.append( NoEscape(r"\vspace*{-.10in}") )
            with doc.create(Figure(position='H')) as images:
                doc.append(Command('centering'))
                with doc.create(
                    SubFigure(
                        position='b',
                        width=NoEscape(r'0.20\linewidth')
                    )
                ) as image:
                    image.add_image( '%s/compiled_result_3.png' % input_path)
                doc.append( NoEscape(r"\hspace{0.05\textwidth}") )
                with doc.create(
                    SubFigure(
                        position='b',
                        width=NoEscape(r'0.18\linewidth')
                    )
                ) as image:
                    image.add_image( '%s/compiled_result_2.png' % input_path)

            doc.append( "*: Projected with regression for 15 days up to D-3\n" )
            doc.append( "**: Regression for 15 days up to D-2\n" ) 
            doc.append( "Obs: Returns calculated with master\n" ) 
            
        with doc.create( Subsection('Posição técnica média') ):
            for key, key_label in [
                ('PREDI720', 'PREDI720'), 
                ('IBOV', 'IBOVESPA'), 
                ('USDBRL', 'USDBRL'), 
                ('SPX', 'S&P'), 
            ]:
                with doc.create(Figure(position='H')) as images:
                    with doc.create(
                        SubFigure(
                            position='b',
                            width=NoEscape(r'0.50\linewidth')
                        )
                    ) as image:
                        image.add_image( '%s/%s_1.png' % (input_path, key))
                    with doc.create(
                        SubFigure(
                            position='b',
                            width=NoEscape(r'0.50\linewidth')
                        )
                    ) as image:
                        image.add_image( '%s/%s_1b.png' % (input_path, key))
                doc.append( NoEscape(r"\vspace*{-.50in}") )
        doc.append( NoEscape(r"\vspace*{.70in}") )
        with doc.create( Subsection('Posição técnica média - Volatilidade ajustada 5%') ): 
            for key, key_label in [
                ('PREDI720', 'PREDI720'), 
                ('IBOV', 'IBOVESPA'), 
                ('USDBRL', 'USDBRL'), 
                ('SPX', 'S&P'), 
            ]:
                with doc.create(Figure(position='H')) as images:
                    with doc.create(
                        SubFigure(
                            position='b',
                            width=NoEscape(r'0.50\linewidth')
                        )
                    ) as image:
                        image.add_image( '%s/%s_1.png' % (input_path, key))
                    with doc.create(
                        SubFigure(
                            position='b',
                            width=NoEscape(r'0.50\linewidth')
                        )
                    ) as image:
                        image.add_image( '%s/%s_1b.png' % (input_path, key))
                doc.append( NoEscape(r"\vspace*{-.50in}") )
        # doc.append( NoEscape(r"\pagebreak") )

def read_data(input_path):
    print('Read data')
    master_data = pd.read_excel('%s/master_data.xlsx' % input_path, index_col=0)
    return master_data

data = read_data(input_path)
data_columns = list(data.columns)
data_columns.sort()

doc = setup_document("%s/funds_technical" % output_path)
with doc.create( Section('Análise técnica - Fundos') ):
    for fund in data_columns:
        fill_document(doc, input_path_3, fund.strip())
doc.generate_pdf( 
    "%s/funds_technical" % output_path, 
    clean_tex=False ,
    compiler = 'pdfLaTeX'
)

doc2 = setup_document("%s/technical" % output_path)
fill_document_2(doc2, input_path_2)
doc2.generate_pdf( 
    "%s/technical" % output_path, 
    clean_tex=False,
    compiler = 'pdfLaTeX'
)

doc3 = setup_document("%s/funds_performance" % output_path)
with doc.create( Section('Performance dos fundos') ):
    fill_document_3(doc3, input_path_2)
doc3.generate_pdf( 
    "%s/funds_performance" % output_path, 
    clean_tex=False,
    compiler = 'pdfLaTeX'
)

# Copy to public folder
shutil.copyfile(
    "%s/funds_technical.pdf" % output_path,
    "%s/funds_technical.pdf" % ( output_path_2 ), 
)
shutil.copyfile(
    "%s/technical.pdf" % output_path,
    "%s/technical_%s.pdf" % ( output_path_2, today ), 
)
shutil.copyfile(
    "%s/funds_performance.pdf" % output_path,
    "%s/funds_performance_%s.pdf" % ( output_path_2, today ), 
)
