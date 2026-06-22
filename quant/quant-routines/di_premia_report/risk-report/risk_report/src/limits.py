# -*- coding: utf-8 -*-
"""
Created on Mon Nov 21 14:56:00 2022

@author: matheus.amaral
"""

import pandas as pd
from a1db.a1sql import SQLConnection
import fund_utils as fu
from datetime import timedelta, date
import var_Equity, var_FX, var_DIFut, var_USTreasury

dt = date(2022,11,18)
connection = SQLConnection().get_connection()
nav = fu.get_NAV(dt, 'A1 Master FIM')

dfVar,_ = var_Equity.get_data(dt)

dictVar = dfVar['VaR'].to_dict()

index = ['IBOV', 'SPX']

dictExp = {}

var_limit = 52.5 / 10_000
for i in index:
    dictExp[i] = var_limit / dictVar[i]
    

dfVar,_ = var_FX.get_data(dt)

for i in ['EURUSD', 'USDBRL']:
    dictExp[i] = var_limit / dfVar.loc[i, 'VaR']

dfVar, _ = var_DIFut.get_data(dt)

for i in ['DI Jan-25','DI Jan-23','DI Jan-27']:
    
    x = dfVar.loc[i, 'VaR'] / dfVar.loc[i, 'PU']

    dictExp[i] = var_limit / x
    
dfVar,_ = var_USTreasury.get_data(dt)
dfVar.set_index('shortName', inplace = True)

for i in ['UST 6M', 'UST 2Y', 'UST 5Y']:
    dictExp[i] = var_limit / dfVar.loc[i,'VaR']
    
dict_share = fu.get_DailyRiskShare(dt, 'A1 Master FIM').loc[dt].to_dict()

dfLimits = pd.DataFrame(columns = ['MS', 'BC', 'PC', 'GB', 'NF', 'MK','Fund'], index = dictExp.keys())

for t in dfLimits.columns:
    for p, exp in dictExp.items():
        dfLimits.loc[p,t] = exp * dict_share[t]