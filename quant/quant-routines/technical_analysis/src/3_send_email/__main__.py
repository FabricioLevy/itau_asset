import win32com.client as win32
import datetime
import pandas as pd
import os

outlook = win32.Dispatch('outlook.application')
mail = outlook.CreateItem(0)
mail.To = "analise_tecnica@asset1.com.br"
# mail.To = "marlon.koga@asset1.com.br"
# mail.To = "guilherme.santos@asset1.com.br"
# mail.To = "carlos.viana@asset1.com.br"
# mail.To = "bruno.carvalho@asset1.com.br"
mail.Subject = 'Relatório de posição técnica'
mail.Body = ' '

input_path = os.path.abspath('../../output/1_process')
input_path_2 = os.path.abspath('../../output/2_generate_pdf')
content_files = [
    "PREDI720_1.png", 
    "PREDI720_1b.png",
    "USDBRL_1.png", 
    "USDBRL_1b.png",
    "IBOV_1.png", 
    "IBOV_1b.png",
    "SPX_1.png", 
    "SPX_1b.png",
    ("compiled_result.png", "<img src=cid:%s height=\"120%%\">"),
    ("compiled_result_3.png", "<img src=cid:%s height=\"13%%\">"),
    ("compiled_result_2.png", "<img src=cid:%s height=\"15%%\">"),
    "same_sign.png",
    "same_sign_b.png",
    'rolling_r2.png',
    'rolling_r2_b.png',

    "PREDI720_2.png", 
    "PREDI720_2b.png",
    "USDBRL_2.png", 
    "USDBRL_2b.png",
    "IBOV_2.png", 
    "IBOV_2b.png",
    "SPX_2.png", 
    "SPX_2b.png",

    "../2b_pca/indicador_otimismo.png", 
    "../2b_pca/indicador_otimismo_b.png", 
    "../2b_pca/indicador_otimismo_pre.png", 
    "../2b_pca/indicador_otimismo_pre_b.png", 
]
mail.Attachments.Add('%s/%s' % (input_path_2, 'funds_performance.pdf'))

contents = []
for content_id, content_file in enumerate(content_files):
    if type(content_file) == tuple:
        file_extension = content_file[0].split('.')[-1]
    else:
        file_extension = content_file.split('.')[-1]

    if file_extension == 'png':
        print(content_file)
        # Add inline images
        image_tag = "myimg%02d" % content_id
        
        if type(content_file) == tuple:
            content_file_name = '%s/%s' % (input_path, content_file[0])
            content_tag = content_file[1] % image_tag
        else:
            content_file_name = '%s/%s' % (input_path, content_file)
            content_tag = "<img src=cid:%s height=\"55%%\">" % image_tag

        attachment = mail.Attachments.Add(content_file_name)
        attachment.PropertyAccessor.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x3712001F", image_tag)
        contents.append(content_tag)
    elif file_extension == 'xlsx':
        # Add inline tables
        excel_data = pd.read_excel('%s/%s' % (input_path, content_file), index_col=0)
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
        Segue análise técnica de posicionamento com cotas até D-2; relatório detalhado anexo.<br>
        A posição técnica de fundo a fundo pode ser encontrada em "R:\\Public\\fund_position_analysis"<br>
        <br>
        Atenciosamente,<br>
        LG e Marlon<br>

        _____________________________________________________________________________________________________________________________________________________________<br>
        <br>
        <b> 
        <font color="Red" size=-1 face="Arial">    
        &nbsp;&nbsp;&nbsp;&nbsp; ESTIMATIVA DE POSIÇÕES MÉDIAS:
        </font>
        </b><br>
        <br>
        %s
        %s<br>
        %s
        %s<br>
        %s
        %s<br>
        %s
        %s<br>
        %s<br><br> 
        *: Projected with regression for 15 days up to D-3 <br>
        **: Regression for 15 days up to D-2 <br>
        Obs: Returns calculated with master <br>
        <br>
        %s&nbsp;&nbsp;&nbsp;%s<br>
        <br>
        %s
        %s <br>
        %s
        %s <br>
        <br>
        <br>
        _____________________________________________________________________________________________________________________________________________________________<br>
        <br>
        <b>     
        <font color="Red" size=-1 face="Arial">    
        &nbsp;&nbsp;&nbsp;&nbsp; ESTIMATIVA DE POSIÇÕES MÉDIAS COM VOLATILIDADE NORMALIZADA: <br>
        </font>
        (ajusta-se a volatilidade de cada fundo para 5%%) <br>
        </b><br>
        <br>
        %s
        %s<br>
        %s
        %s<br>
        %s
        %s<br>
        %s
        %s<br>
        <br>
        _____________________________________________________________________________________________________________________________________________________________<br>
        <br><b>
        <font color="Red" size=-1 face="Arial">    
        &nbsp;&nbsp;&nbsp;&nbsp; ESTIMATIVA DE OTIMISMO/PESSIMISMO: <br>
        </font>
        </b><br>
        Os resultados abaixo são obtidos a partir de uma análise de PCA que <br>
        agrupa os dados de Ibov, SPX e USDBRL em um índice <br>
        <br>
        %s
        %s<br>
        %s
        %s<br>
        <br>
    </body>
</html>
""" % tuple( contents )

mail.Send()