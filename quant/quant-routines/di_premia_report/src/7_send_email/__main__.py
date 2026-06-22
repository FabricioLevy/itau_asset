import win32com.client as win32
import datetime
import pandas as pd
import os

outlook = win32.Dispatch('outlook.application')
mail = outlook.CreateItem(0)
mail.To = "premiodi@asset1.com.br"
# mail.To = "marlon.koga@asset1.com.br"
# mail.To = "carlos.viana@asset1.com.br"
# mail.To = "bruno.carvalho@asset1.capital"
mail.Subject = 'Relatório de prêmio'
mail.Body = ' '
input_path = os.path.abspath(os.getcwd()) + '/../../output/6_plot'
content_files = [
    'di.xlsx',
    {
        'file': 'di_cross_section.png',
        'html_tag':  "<img src=cid:%s height=\"90%%\">",
    },
    "1_a_6M.png", 
    "1_b_6M.png",
    "2_a_1Y.png",
    "2_b_1Y.png",
    "2a_a_18M.png",
    "2a_b_18M.png",
    "3_a_2Y.png",
    "3_b_2Y.png",

    'steepness.xlsx',
    "4_a_2Y-1Y.png",
    "4_b_2Y-1Y.png",
    "5_a_5Y-2Y.png",
    "5_b_5Y-2Y.png",

    {
        'file': 'implicit_cross_section.png',
        'html_tag':  "<img src=cid:%s height=\"90%%\">",
    },
    'implicit_6m.xlsx',
    "6a_a_implicit_6m.png",
    "6a_b_implicit_6m.png",

    'implicit_1y.xlsx',
    "6_a_implicit_1y.png",
    "6_b_implicit_1y.png",

    'implicit_18m.xlsx',
    "6aa_a_implicit_18m.png",
    "6aa_b_implicit_18m.png",

    'implicit_2y.xlsx',
    "6b_a_implicit_2y.png",
    "6b_b_implicit_2y.png",

    'target_implicit_1y.xlsx',
    "6c_a_target_implicit_1y.png",
    "6c_b_target_implicit_1y.png",

    'target_implicit_2y.xlsx',
    "6d_a_target_implicit_2y.png",
    "6d_b_target_implicit_2y.png",

    'flat_vs_selic.xlsx',
    '7_a_flat_6m-selic.png',
    '7_b_flat_6m-selic.png',
    '8_a_flat_1y-selic.png',
    '8_b_flat_1y-selic.png',
    '9_a_flat_2y-selic.png',
    '9_b_flat_2y-selic.png',

    'flat_steepness.xlsx',
    '10_a_flat_2y-1y.png',
    '10_b_flat_2y-1y.png',
    '11_a_flat_5y-2y.png',
    '11_b_flat_5y-2y.png',
]

contents = []
for content_id, content_file in enumerate(content_files):
    if isinstance(content_file, dict):
        filename = content_file['file']
        html_tag = content_file['html_tag']
    else:
        filename = content_file
        html_tag = "<img src=cid:%s height=\"55%%\">"
    file_extension = filename.split('.')[-1]

    if file_extension == 'png':
        print(filename)
        # Add inline images
        image_tag = "myimg%02d" % content_id
        attachment = mail.Attachments.Add('%s/%s' % (input_path, filename))
        attachment.PropertyAccessor.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x3712001F", image_tag)
        contents.append( html_tag % image_tag)

    elif file_extension == 'xlsx':
        # Add inline tables
        excel_data = pd.read_excel('%s/%s' % (input_path, filename), index_col=0)
        for column in excel_data:
            for index in excel_data.index:
                if type(excel_data[column][index]) == datetime.datetime:
                    excel_data[column][index] = excel_data[column][index].date()
        contents.append(
            excel_data.to_html(
                float_format=lambda x: "%.0f" % x,
                justify='center'
            )
        )

mail.HTMLBody = """
<html>
    <style>
        table {text-align: center;}
        table thead th {text-align: center;}
    </style>
    <body>
        Prezados, bom dia! <br>
        <br>
        Segue o relatório de prêmio <br>
        <br>
        _____________________________________________________________________________________________________________________________________________________________<br>
        <br>
        <b>     
        &nbsp;&nbsp;&nbsp;&nbsp;PRÊMIO DE DI
        </b><br>
        <br>
        %s<br>
        %s<br>
        %s<br>
        %s<br>
        %s<br>
        %s<br>
        %s<br>
        %s<br>
        %s<br>
        %s<br>
        <br>
        _____________________________________________________________________________________________________________________________________________________________<br>
        <br>
        <b>     
        &nbsp;&nbsp;&nbsp;&nbsp;PRÊMIO DE INCLINAÇÂO
        </b><br>
        <br>
        %s<br>
        %s<br>
        %s<br>
        %s<br>
        %s<br>
        <br>
        _____________________________________________________________________________________________________________________________________________________________<br>
        <br>
        <b>
        &nbsp;&nbsp;&nbsp;&nbsp;PRÊMIO DE IMPLÍCITA (MERCADO VS FOCUS)
        </b><br>
        %s<br>
        <br>
        _____________________________________________________________________________________________________________________________________________________________<br>
        <br>
        <b>
        &nbsp;&nbsp;&nbsp;&nbsp;PRÊMIO DE IMPLÍCITA 6M (MERCADO VS FOCUS)
        </b><br>
        <br>
        %s<br>
        %s<br>
        %s<br>
        <br>
        _____________________________________________________________________________________________________________________________________________________________<br>
        <br>
        <b>
        &nbsp;&nbsp;&nbsp;&nbsp;PRÊMIO DE IMPLÍCITA 1Y (MERCADO VS FOCUS)
        </b><br>
        <br>
        %s<br>
        %s<br>
        %s<br>
        <br>
        _____________________________________________________________________________________________________________________________________________________________<br>
        <br>
        <b>
        &nbsp;&nbsp;&nbsp;&nbsp;PRÊMIO DE IMPLÍCITA 18M (MERCADO VS FOCUS)
        </b><br>
        <br>
        %s<br>
        %s<br>
        %s<br>
        <br>
        _____________________________________________________________________________________________________________________________________________________________<br>
        <br>
        <b>
        &nbsp;&nbsp;&nbsp;&nbsp;PRÊMIO DE IMPLÍCITA 2Y (MERCADO VS FOCUS)
        </b><br>
        <br>
        %s<br>
        %s<br>
        %s<br>
        <br>
        _____________________________________________________________________________________________________________________________________________________________<br>
        <br>
        <b>
        &nbsp;&nbsp;&nbsp;&nbsp;PRÊMIO DE IMPLÍCITA 1Y (MERCADO VS META INFLAÇÃO)
        </b><br>
        <br>
        %s<br>
        %s<br>
        %s<br>
        <br>
        _____________________________________________________________________________________________________________________________________________________________<br>
        <br>
        <b>
        &nbsp;&nbsp;&nbsp;&nbsp;PRÊMIO DE IMPLÍCITA 2Y (MERCADO VS META INFLAÇÃO)
        </b><br>
        <br>
        %s<br>
        %s<br>
        %s<br>
        <br>
        _____________________________________________________________________________________________________________________________________________________________<br>
        <br>
        <b>
        &nbsp;&nbsp;&nbsp;&nbsp;INCLINAÇÂO SEM SUBTRAÇÃO FOCUS (vs SELIC)
        </b><br>
        <br>
        %s<br>
        %s<br>
        %s<br>
        %s<br>
        %s<br>
        %s<br>
        %s<br>
        <br>
        _____________________________________________________________________________________________________________________________________________________________<br>
        <br>
        <b>     
        &nbsp;&nbsp;&nbsp;&nbsp;INCLINAÇÂO SEM SUBTRAÇÃO FOCUS
        </b><br>
        <br>
        %s<br>
        %s<br>
        %s<br>
        %s<br>
        %s<br>
        <br>
        <br>
        Atenciosamente, <br>
        Quant
    </body>
</html>
""" % tuple(contents)

mail.Send()