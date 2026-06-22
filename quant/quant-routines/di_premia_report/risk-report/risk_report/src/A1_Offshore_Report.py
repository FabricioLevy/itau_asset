# -*- coding: utf-8 -*-
"""
Created on Fri Sep  9 10:19:33 2022

@author: matheus.amaral
"""

import os
import win32com.client as win32
import offshore_jinja_writer
import offshore_savefigs
import fund_utils as fu

def main(dt, str_fund = 'A1 Hedge SP'):
    
    nav = fu.get_NAV(dt,str_fund)
    offshore_savefigs.main(dt,str_fund,nav)
    offshore_jinja_writer.main(dt,str_fund)
    
    path = os.path.expanduser('~\Documents\\GitHub\\risk_report\\tex\\')

    outlook = win32.Dispatch('Outlook.application')
    email = outlook.CreateItem(0)
    
    email.Attachments.Add(Source = os.path.join(path, dt.strftime('%Y%m%d'),dt.strftime('%Y%m%d') + '_A1 Hedge SP.pdf'))
    email.Subject = f"Fund Offshore Report  - {dt:%d-%b-%Y}"
    
    email.To = "risco@asset1.com.br;middle@asset1.com.br"
    email.SentOnBehalfOfName = 'risco@asset1.com.br'
    
    email.Display()
    
#%%

if __name__ == '__main__':
    
    dt, str_fund = fu.get_config(['dt', 'str_fund_offshore'])
    main(dt)