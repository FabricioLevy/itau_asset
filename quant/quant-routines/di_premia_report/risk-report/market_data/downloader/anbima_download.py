import pandas as pd
import datetime
import urllib

from a1db.a1sql import SQLConnection

import win32com.client as win32


#%%
def main (dt, notification = False):
    #%%
    
    today_file = dt.strftime("%y%m%d")
    
    anbima_url = "https://www.anbima.com.br/informacoes/merc-sec/arqs/"
    anbima_local = "R:/Risk/02_MarketData/Anbima/files/"
    anbima_tit_file = 'ms' + today_file + ".txt"
    
    try:
        urllib.request.urlretrieve(anbima_url + anbima_tit_file, 
                                   anbima_local + anbima_tit_file)    
    except urllib.request.HTTPError as exception:
        print(f"!! Error in file: {__file__}")
        raise exception
        # return False
    
    dfAnbima = pd.read_csv(anbima_local+anbima_tit_file, skiprows=2, sep='@', na_values='--',\
                           parse_dates=[1, 3, 4], decimal=",", encoding='cp1252')

    dfAnbima.columns = ['titulo', 'date_reference', 'codigo_selic','data_emissao',\
                        'data_vencimento','taxa_compra','taxa_venda','taxa_indicativa',\
                        'pu' ,'desvio_padrao' ,'interv_ind_inf_D0' ,'interv_ind_sup_D0',\
                        'interv_ind_inf_D1','interv_ind_sup_D1','criterio']
        
    connection = SQLConnection().get_connection()
    connection.execute("DELETE FROM anbima.[taxa_titulo_publico] WHERE date_reference = '{:%Y-%m-%d}'".format(dt))
    dfAnbima.to_sql("taxa_titulo_publico", connection, schema='anbima', if_exists='append', index=False)
    print('Download Anbima - Inserted {} values for date {}'.format(len(dfAnbima), dt))
    
    #%%
    anbima_url = "http://www.anbima.com.br/vna/vna-down.asp" 
    anbima_url = "https://www.anbima.com.br/informacoes/vna/vna-down.asp"
    data = urllib.parse.urlencode({'Idioma': 'PT', 'saida': 'txt', 'Data': dt.strftime("%d%m%Y")}).encode()
    req =  urllib.request.Request(anbima_url, data=data)
    resp = urllib.request.urlopen(req)
    
    anbima_tit_file = 'vna_'+ today_file +'.txt'
    with open(anbima_local + anbima_tit_file, 'wb') as file:
        file.write(resp.read())
    
    dfVNA = pd.read_csv(anbima_local+anbima_tit_file, skiprows=7, sep=';', decimal=',',\
                        thousands='.', encoding='cp1252', parse_dates=[5], dayfirst=True)
    
    dfVNA.columns = ['titulo','codigo_selic','VNA','indice','ref','valido_a_partir_de']        
    dfVNA.insert(0, 'date_reference', dt)    
    
    connection.execute("DELETE FROM anbima.VNA WHERE date_reference = '{:%Y-%m-%d}'".format(dt))
    
    dfVNA.to_sql("VNA", connection, schema='anbima', if_exists='append', index=False)
    print('Download Anbima VNA - Inserted {} values for date {}'.format(len(dfVNA), dt))
   
    #%%    
    if notification:
        outlook = win32.Dispatch('outlook.application')
        mail = outlook.CreateItem(0)
        mail.To = "luis.oliveira@asset1.com.br"
        mail.Subject = 'ANBIMA OK - ' + datetime.date.today().strftime("%d/%m/%Y")
        mail.Body = ''
        
        mail.HTMLBody = """
                            <html>
                                <body>
                                Dados do site salvos no Banco de Dados.
                                </body>
                            </html>
                        """
        mail.Send()
        
        print('\nANBIMA OK sent.\n')

#%%    
if __name__ == "__main__":
    
    dt = datetime.date(2022, 7, 19)
    try:
        main(dt)
    except Exception as err:
        print(f"Did not work! {err=}")