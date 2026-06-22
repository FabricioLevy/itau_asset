import pandas as pd
import datetime
import requests

import urllib.parse 

from a1db.a1sql import SQLConnection

#%%
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

#%%
def main(dt):
#%%
    
    today = dt.strftime("%d/%m/%Y")
    form_param = {'dData1': urllib.parse.quote(today)}

    bmf_url = "https://www2.bmf.com.br/pages/portal/bmfbovespa/lumis/lum-posicoes-em-aberto-futuro-ptBR.asp"
    
    r = requests.post(bmf_url, 
                      data=form_param, 
                      verify = False)
    try:
        listHTML = pd.read_html(r.text, match='.+', 
                                flavor=None, 
                                header=None, 
                                index_col=None,
                                skiprows=None, 
                                attrs=None, 
                                parse_dates=False,
                                thousands='.', 
                                encoding=None, 
                                decimal=',', 
                                converters=None,
                                na_values=None,
                                keep_default_na=False)
    except Exception as err:
        print(f"!! Error in file: {__file__}")
        raise err
        
    dfBMF = listHTML[0]
    del r, listHTML
    
    ativo_prev = dfBMF.head(1)['Mercadoria']
    for i, row in dfBMF.iterrows():
        ativo_id = row['Mercadoria']
        if ativo_id == '':
            dfBMF.at[i, 'Mercadoria'] = ativo_prev
        else:
            ativo_prev = ativo_id
    
    dfBMF.columns = ['mercadoria','vencimento','contratos_em_aberto', 'variacao']
    dfBMF=dfBMF[dfBMF['contratos_em_aberto'].str.isnumeric()]
    dfBMF=dfBMF[dfBMF['mercadoria']!='Total']
    dfBMF.insert(0, 'date_reference', dt)
    dfBMF.insert(1, 'tipo_contrato', 'Futuro')
            
    #save to .CSV
    dfBMF.to_csv("R:/Risk/02_MarketData/B3/ContratosAbertos/ContratosAbertosFuturos_"+dt.strftime("%Y%m%d")+".csv",\
                 sep=',', index=False, encoding='UTF16')
    
    #save to DB
    connection = SQLConnection().get_connection()
    str_sql = "DELETE FROM [b3].[contrato_aberto] "+ \
              "WHERE date_reference = '{:%Y-%m-%d}' and tipo_contrato='Futuro'".format(dt)
    connection.execute(str_sql)
    
    dfBMF.to_sql("contrato_aberto", connection, schema='b3', if_exists='append', index=False)
    print('Download B3 - Contrato Aberto Futuros - Inserted {} values for date {}'.format(len(dfBMF), dt))


    
#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 7, 19)
    try:
        main(dt)
    except Exception as err:
        print(f"Did not work! {err=}")
    
 