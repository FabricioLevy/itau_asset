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

def plot_subsection(
    doc,
    duration,
    short_selector,
    countries,
    images_path_dict,
    title,
    selector_lambda
):
    with doc.create(Subsection(title)):
        doc.append( NoEscape(r"\begin{tabular}{ccc}") )
        for country_index, country in enumerate(countries):
            # For each country, add plot
            selector = selector_lambda(duration, short_selector, country)
            doc.append( NoEscape("\includegraphics[width=230px,height=160px]{%s}" % (images_path_dict[selector]) ) )
            if country_index % 3 == 2:
                doc.append( NoEscape(r"\\") )
            else:
                doc.append( NoEscape(r" & ") )
        doc.append( NoEscape(r"\end{tabular}") )
    doc.append( NoEscape(r'\pagebreak'))

def setup_document():
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
    doc.packages.append(Package('pdflscape'))
    doc.packages.append(Package('graphicx'))

    doc.append( NoEscape( r'''
        \newenvironment{changemargin}[2]{%
        \begin{list}{}{%
        \setlength{\topsep}{0pt}%
        \setlength{\leftmargin}{#1}%
        \setlength{\rightmargin}{#2}%
        \setlength{\listparindent}{\parindent}%
        \setlength{\itemindent}{\parindent}%
        \setlength{\parsep}{\parskip}%
        }%
        \item[]}{\end{list}}
    ''' ) )

    # doc.append( NoEscape(r"\setcounter{section}{3}") )
    return doc

def fill_document(doc):
    input_path = '../output/1_plot'
    countries = [
        'Brasil',
        'Mexico',
        'Colombia',
        'Chile',
        'Africa do Sul',
        'Russia',
        'EUA',
        'Euro',
        'UK',
    ]
    today = pd.Timestamp.now()
    date = today

    # Create a dictionary with file paths
    short_selector = '3M'
    images_path_dict = {}
    for duration in ['6M', '1Y', '2Y']:
        for country in countries:
            selector = '%s-%s_%s' % (duration, short_selector, country)
            images_path_dict['%s' % selector] = '%s/%s.png' % (input_path, selector)
            selector = '%s-%s_%s_hist' % (duration, short_selector, country)
            images_path_dict['%s' % selector] = '%s/%s.png' % (input_path, selector)
    short_selector = '2Y'
    duration = '5Y'
    for country in countries:
        selector = '%s-%s_%s' % (duration, short_selector, country)
        images_path_dict['%s' % selector] = '%s/%s.png' % (input_path, selector)
        selector = '%s-%s_%s_hist' % (duration, short_selector, country)
        images_path_dict['%s' % selector] = '%s/%s.png' % (input_path, selector)
    short_selector = '1Y'
    duration = '2Y'
    for country in countries:
        selector = '%s-%s_%s' % (duration, short_selector, country)
        images_path_dict['%s' % selector] = '%s/%s.png' % (input_path, selector)
        selector = '%s-%s_%s_hist' % (duration, short_selector, country)
        images_path_dict['%s' % selector] = '%s/%s.png' % (input_path, selector)
            
    # Compose document
    doc.append( NoEscape(r"\begin{landscape}") )
    doc.append( NoEscape(r'\begin{changemargin}{0cm}{-1cm}') )
    with doc.create(Section('Relatório de juros cross-country %s' % date.strftime('%Y-%m-%d'))) as section:
        
        section.geometry_options = Command({'margin': '10px'})

        short_selector = '3M'
        for duration in ['6M', '1Y', '2Y']:
            # Add a page with plot and histogram
            plot_subsection(
                doc,
                duration,
                short_selector,
                countries,
                images_path_dict,
                'Curva de juros %s-%s' % (duration, short_selector),
                lambda duration, short_selector, country: '%s-%s_%s' % (duration, short_selector, country)
            )

            plot_subsection(
                doc,
                duration,
                short_selector,
                countries,
                images_path_dict,
                'Histograma da curva de juros %s-%s' % (duration, short_selector),
                lambda duration, short_selector, country: '%s-%s_%s_hist' % (duration, short_selector, country)
            )

        # Add a page with plot and histogram
        short_selector = '1Y' 
        duration = '2Y'
        plot_subsection(
            doc,
            duration,
            short_selector,
            countries,
            images_path_dict,
            'Inclinação %s-%s' % (duration, short_selector),
            lambda duration, short_selector, country: '%s-%s_%s' % (duration, short_selector, country)
        )
        plot_subsection(
            doc,
            duration,
            short_selector,
            countries,
            images_path_dict,
            'Histograma da inclinação %s-%s' % (duration, short_selector),
            lambda duration, short_selector, country: '%s-%s_%s_hist' % (duration, short_selector, country)
        )

        # Add a page with plot and histogram
        short_selector = '2Y' 
        duration = '5Y'
        plot_subsection(
            doc,
            duration,
            short_selector,
            countries,
            images_path_dict,
            'Inclinação %s-%s' % (duration, short_selector),
            lambda duration, short_selector, country: '%s-%s_%s' % (duration, short_selector, country)
        )
        plot_subsection(
            doc,
            duration,
            short_selector,
            countries,
            images_path_dict,
            'Histograma da inclinação %s-%s' % (duration, short_selector),
            lambda duration, short_selector, country: '%s-%s_%s_hist' % (duration, short_selector, country)
        )

    doc.append( NoEscape(r'\end{changemargin}') )
    doc.append( NoEscape(r"\end{landscape}") )

if __name__ == '__main__':
    output_path = '../../output/crosscountry'

    # Create output folder
    for folder in ['../../output', output_path]:
        if not os.path.exists(folder):
            os.makedirs(folder)

    doc = setup_document()
    fill_document(doc)

    doc.generate_pdf( clean_tex=False, compiler ='pdfLaTeX')
    tex = doc.dumps()  # The document as string in LaTeX syntax