# -*- coding: utf-8 -*-
"""
Created on Fri Jul  1 14:46:22 2022

@author: matheus.amaral
"""

import pandas as pd 
import datetime
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import adjustText
import fund_utils as fu
import os
import win32com.client as win32


#%%
def main(dt, str_fund = 'A1 Master FIM'):
    if str_fund != 'A1 Master FIM':
        return False
    
    path = os.path.expanduser('~\Documents\\GitHub\\risk_report\output\\temp_figs')
    
    folder_files = [file for file in os.listdir(path) if 'trade_idea_table' in file]
    names = ['trade_idea_table_aberto.svg', 'mock_trade_idea_table_aberto.svg', 
             'trade_idea_table_fechado.svg', 'mock_trade_idea_table_fechado.svg']
    
    names_dt = [f"{dt:%Y%m%d}_" + name for name in names]
    outlook = win32.Dispatch('outlook.application')
    email = outlook.CreateItem(0)
    
    text = "<html>"
    for file in names_dt:
        if file in folder_files:
            print(file)
            
            path_fig = '//'.join(os.path.join(path,file).split('\\'))
            email.Attachments.Add(Source = path_fig)
            text += f"""
                <img src = "{file}"><br><br/>
            """
            
    email.htmlBody = text
    email.Subject = f"Trade Ideas - MtM {dt:%d-%b-%Y}"
    email.To = """
        risco@asset1.com.br;Marcello.Siniscalchi@asset1.com.br;
        Bruno.Carvalho@asset1.com.br;Marlon.Koga@asset1.com.br>; Gabriel.Blum@asset1.com.br; 
        Norberto.Alves@asset1.com.br; pedro.carneiro@asset1.com.br; felipe.husein@asset1.com.br; 
        anthony.maalouf@asset1.com.br; luis.cezario@asset1.com.br'
        """
    email.SentOnBehalfOfName = 'risco@asset1.com.br'
    email.Display()
    
#%%
if __name__ == '__main__':
    dt = datetime.date(2022,7,14)
    main(dt)

   