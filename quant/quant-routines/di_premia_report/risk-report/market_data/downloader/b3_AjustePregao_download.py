import pandas as pd
import datetime
import requests

from a1db.a1sql import SQLConnection

#%%
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

#%%
def main(dt):
#%%
    
    today = dt.strftime("%d/%m/%Y")
    form_param = {'dData1':today}
    bmf_url = "http://www2.bmf.com.br/pages/portal/bmfbovespa/lumis/lum-ajustes-do-pregao-ptBR.asp"
    
    r = requests.post(bmf_url, form_param, verify = False)
    
    pos_a = r.text.find('Atualizado em')
    dt_html = datetime.datetime.strptime(r.text[pos_a:pos_a+25][-10:], '%d/%m/%Y')
    if dt != dt_html.date():
        print(f"!! Error in file: {__file__}")
        raise ValueError('Arquivo não disponivel para data!')
    
    try:
        listHTML = pd.read_html(r.text, match='.+', flavor=None, header=None, index_col=None,\
                            skiprows=None, attrs=None, parse_dates=False, \
                            thousands='.', encoding=None, decimal=',', converters=None,\
                            na_values=None, keep_default_na=False)
    except ValueError:
        print(f"!! Error in file: {__file__}")
        raise ValueError('Dados não disponiveis em para a data {:%d-%b-%y} em:\n'.format(dt) + bmf_url)
    
    dfBMF = listHTML[0]
    del r, listHTML
    
    ativo_prev = dfBMF.head(1)['Mercadoria']
    for i, row in dfBMF.iterrows():
        ativo_id = row['Mercadoria']
        if ativo_id == '':
            dfBMF.at[i, 'Mercadoria'] = ativo_prev
        else:
            ativo_prev = ativo_id
    
    dfBMF.columns = ['mercadoria','vencimento','preco_ajuste_anterior','preco_ajuste_atual',\
                     'variacao','valor_ajuste_contrato_brl']
    dfBMF.insert(0, 'date_reference', dt)
    
    # dfBMF = dfBMF[~(dfBMF['mercadoria'] =='IND - Ibovespa')]
    dfBMF = dfBMF[~(dfBMF['mercadoria'] =='IS2 - Açúcar')]
    
            
    #save to .CSV
    dfBMF.to_csv("R:/Risk/02_MarketData/B3/AjustePregao/AjustePregao_"+dt.strftime("%Y%m%d")+".csv",\
                 sep=',', index=False, encoding='UTF16')
    
    #save to DB
    connection = SQLConnection().get_connection()
    str_sql = "DELETE FROM [b3].[ajuste_pregao] "+ \
              "WHERE date_reference = '{:%Y-%m-%d}' ".format(dt)
    connection.execute(str_sql)
    
    dfBMF.to_sql("ajuste_pregao", connection, schema='b3', if_exists='append', index=False)
    print('Download B3 - Inserted {} values for date {}'.format(len(dfBMF), dt))

    
#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 7, 19)
    try:
        main(dt)
    except Exception as err:
        print(f"Did not work! {err=}")
    
