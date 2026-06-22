import pandas as pd
import numpy as np
import datetime
import timeit
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import QuantLib as ql
import xlwings as xw
import fund_utils as fu

import os
import sys 
sys.path.insert(1, os.path.expanduser('~\\Documents\\Github\\market_data'))
import curve_db 

path_instruments = os.path.expanduser('~\\Documents\\Github\\instruments\\B3')
sys.path.insert(1, path_instruments)
import B3Option

str_fund = 'A1 Master FIM'
dt = datetime.date(2022,2,3)
dt1 = datetime.date(2022,2,3)
calendar_br = ql.Brazil()
today = ql.Date.from_date(dt)
_, connection = fu.get_DB_conn('prod')
 
str_sql = f"""
    SELECT ReportDate, [PriceValue]
  FROM [up2data].[Economic_Indicator_EconomicIndicatorFile]
  WHERE ReportDate = '{dt:%Y-%m-%d}' and TickerSymbol = 'IDI-09' 
    """ 
idix9 = pd.read_sql(str_sql, connection, index_col='ReportDate').loc[dt, 'PriceValue']

str_sql = f"""
    SELECT distinct book, [lote45_product],[amount]
  FROM [lote45].[primitive]
  where date_reference = '{dt1:%Y-%m-%d}' and trading_desk='{str_fund}' 
  and lote45_product_class in ('IDIOptionCall','IDIOptionPut')
"""
dfPos = pd.read_sql(str_sql, connection).pivot(index='lote45_product', columns='book', values='amount').fillna(0)
ids = "','".join(dfPos.index)

str_sql = f"""
SELECT [id],[lote45_product],[date_maturity],[option_type]
      ,[option_style],[option_strike], pp.price
  FROM [middle].[product] p INNER JOIN middle.product_price pp
	ON p.id = pp.product_id
  WHERE id in ('{ids}') and pp.date_reference='{dt1:%Y-%m-%d}'
"""
dfOpt = pd.read_sql(str_sql, connection, index_col='id') 


opt_ids = "','".join(dfOpt.index)
str_sql = f"""
        SELECT [Asset],[ExpirationCode],[OptionStyle],[OptionType],[ExpirationDate] 
      ,[ExercisePrice],[ReferencePrice],[VolatilityValue],[DeltaValue] 
  FROM [up2data].[Interest_Rate_ReferencePriceFile]
  where ReportDate='{dt1:%Y-%m-%d}' 
  and Asset+ExpirationCode in ('{opt_ids}')
"""
dfUp2Data = pd.read_sql(str_sql, connection) 
dfUp2Data['id'] = dfUp2Data['Asset'] + dfUp2Data['ExpirationCode']
dfUp2Data.set_index('id', inplace=True)
 
#%%
ql.Settings.instance().evaluationDate = today
day_count = ql.Business252(calendar_br)
    
curve_name = 'DI Fut'
risk_free = curve_db.get_curve(today.to_date(), curve_name)
risk_free_handle = ql.YieldTermStructureHandle(risk_free)
    
dic_Asset = {}
dic_Vol = {}

for opt_id, (_, dt_exp, opt_type, opt_style, opt_strike, price) in dfOpt.iterrows():
 
    ql_opt_type = ql.Option.Call if opt_type.upper() == 'C' else ql.Option.Put
    ql_dt_exp = ql.Date.from_date(dt_exp)
    dic_Vol[opt_id] = ql.SimpleQuote(dfUp2Data.loc[opt_id,'VolatilityValue']/100)
    
    opt = B3Option.IDIOption(ql_opt_type, opt_strike, dt_exp, float(idix9), dic_Vol[opt_id], risk_free_handle, price)
    dic_Asset[opt_id] = opt
    
    # black = ql.BlackCalculator(ql.PlainVanillaPayoff(ql_opt_type, opt._strike_rate),
    #                            opt._fwd_rate.value(),
    #                             dic_Vol[opt_id].value()*(ql.Business252(ql.Brazil()).yearFraction(ql.Settings.instance().evaluationDate, ql_dt_exp))**(1/2), 
    #                            risk_free.discount(ql_dt_exp))
    

    
    # print(f"{opt}")
    # print(f"fwd rate linear:{opt._fwd_rate.value():8.3%}  DI rate:{risk_free.zeroRateValue(ql_dt_exp):8.3%}  fator:{opt.factor():12,.4f}")
    # print(f"strike rate linear:{opt._strike_rate:8.2%} ")
    # print(f"Vol Model: {opt._vol.blackVol(ql_dt_exp, opt_strike):8.4%}  Vol B3:{dfUp2Data.loc[opt_id,'VolatilityValue']/100:8.4%}")
    
    # print(f"{opt_id} Price B3:{dfUp2Data.loc[opt_id,'ReferencePrice']:8.2f}  Model:{opt.NPV():8.2f}")
    # print(f"{opt_id} Delta B3:{dfUp2Data.loc[opt_id,'DeltaValue']:8.4f} Model:{opt.delta():8.4f} Model FWD:{opt.deltaForward():8.4f}")
    # print(f"{opt.DI1_numberOfContracts():8.2f}")
    
    
    # # print(f"{black.value()*opt.factor():8.2f}")
    
    # print("\n")
#%%
    
dfOPtSimu = pd.read_excel("C:/Users/mauricio.pereira/Documents/simu_IDI.xlsx", index_col=0)
dfRes = pd.DataFrame(index=dfPos.index, columns=['desc','Amount','Strike Rate', 'vol', 'price','MtM', 'Delta', 'DI1'])

for opt_id, (dt_exp, opt_type, opt_strike, vol, amount) in dfOPtSimu.iterrows():
 
    ql_opt_type = ql.Option.Call if opt_type.upper() == 'C' else ql.Option.Put
    ql_dt_exp = ql.Date.from_date(dt_exp)
    dic_Vol[opt_id] = ql.SimpleQuote(vol)
    
    opt = B3Option.IDIOption(ql_opt_type, opt_strike, dt_exp, float(idix9), dic_Vol[opt_id], 0.11695)
    dic_Asset[opt_id] = opt
    
    dfRes.loc[opt_id, 'Amount'] = amount
    dfRes.loc[opt_id, 'desc'] = str(opt)
    dfRes.loc[opt_id, 'Strike Rate'] = opt._strike_rate
    dfRes.loc[opt_id, 'vol'] = vol
    dfRes.loc[opt_id, 'price'] = opt.NPV()
    dfRes.loc[opt_id, 'MtM'] = opt.NPV() * amount
    dfRes.loc[opt_id, 'Delta'] = opt.delta() * amount
    dfRes.loc[opt_id, 'DI1'] = opt.DI1_numberOfContracts() * amount
    
    
    
#%%
dic_output = {}
for b in dfPos.columns:
    dic_output[b] = pd.DataFrame(index=dfPos.index, columns=['Amount', 'Maturity','MtM', 'Delta', 'DI1'])
    tempPos = dfPos[b].to_dict()
    for opt_id, amount in tempPos.items():
        dic_output[b].loc[opt_id, 'Amount'] = amount
        dic_output[b].loc[opt_id, 'Maturity'] = dic_Asset[opt_id].exercise().lastDate().to_date()
        dic_output[b].loc[opt_id, 'MtM'] = dic_Asset[opt_id].NPV() * amount
        dic_output[b].loc[opt_id, 'Delta'] = dic_Asset[opt_id].delta() * amount
        dic_output[b].loc[opt_id, 'DI1'] = dic_Asset[opt_id].DI1_numberOfContracts() * amount
 
