import pandas as pd
import numpy as np
import datetime
import timeit
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import QuantLib as ql
import xlwings as xw
import fund_utils as fu

import os
import sys
str_onedrive = '\\OneDrive' if os.path.exists(os.path.expanduser('~\\OneDrive')) else ''

path_curve_db = os.path.expanduser('~{}\\Documents\\Github\\market_data'.format(str_onedrive))
sys.path.insert(1, path_curve_db)
import curve_db 

path_instruments = os.path.expanduser('~{}\\Documents\\Github\\instruments'.format(str_onedrive))
sys.path.insert(1, path_instruments)
from B3 import B3Future
from BRLBond import BrazilianBond

dt = datetime.date(2021,6,15)
str_fund = 'A1 Master FIM'
nav = fu.get_NAV(dt, str_fund)

color1, color2 = fu.color_palette[0:2]

curve_DI = curve_db.get_curve(dt, 'DI Fut')
curve_DI.enableExtrapolation()
curve_DI_handle = ql.RelinkableYieldTermStructureHandle(curve_DI)
curve_DI_t0 = ql.YieldTermStructureHandle(curve_DI)
engine_DI = ql.DiscountingBondEngine(curve_DI_handle)

curve_DAP = curve_db.get_curve(dt, 'DAP Fut')
engine_DAP = ql.DiscountingBondEngine(ql.YieldTermStructureHandle(curve_DAP))
ipca_prt = curve_db.get_price(dt, 'IPCA PRT')

curve_NTNB = curve_db.get_curve(dt, 'NTNB Zero')
engine_NTNB = ql.DiscountingBondEngine(ql.YieldTermStructureHandle(curve_NTNB))
vna = curve_db.get_price(dt, 'VNA NTNB')

curve_NTNF = curve_db.get_curve(dt, 'NTNF Zero')
engine_NTNF = ql.DiscountingBondEngine(ql.YieldTermStructureHandle(curve_NTNF))

# curve_LTN = curve_db.get_curve(dt, 'LTN')
# engine_LTN = ql.DiscountingBondEngine(ql.YieldTermStructureHandle(curve_LTN))

prods = ['DI1Future', 'DAP Future', 'NTN-B', 'NTN-F', 'LTN']

_, connection = fu.get_DB_conn('prod')
    
str_sql = """
            SELECT [product_id],[value] as PV01
            FROM [risk].[product_sensitivity]
            WHERE date_reference = '{:%Y-%m-%d}' and sensitivity = 'PV01'
           """
str_sql = str_sql.format(dt)
dic_pv01 = pd.read_sql(str_sql, connection, index_col='product_id')['PV01'].to_dict()

str_sql = """
    SELECT p.id as product_id, p.product_type, date_maturity, date_issue, sum(bo.value) as amount
      FROM [lote45].[book_overview] bo INNER JOIN middle.product p ON bo.lote45_product = p.lote45_product
      WHERE bo.date_reference = '{:%Y-%m-%d}' and bo.trading_desk = '{}' and bo.measure = 'Amount'
      and p.product_type in ('{}')
      GROUP BY p.id, p.product_type, date_maturity, date_issue
    """
str_sql = str_sql.format(dt, str_fund, "','".join(prods))
dfPosition = pd.read_sql(str_sql, connection, index_col='product_id')
dic_position = dfPosition['amount'].to_dict()

connection.close()
del connection, str_sql, path_curve_db, path_instruments

#%%
dic_asset = {}
for prod_id, row in dfPosition.iterrows():
    prod_type, dt_maturity, dt_issue, _ = row.values

    if prod_type == 'DI1Future':
        dic_asset[prod_id] = B3Future.DI1Future(ql.Date().from_date(dt_maturity))
        dic_asset[prod_id].setPricingEngine(engine_DI)
        
    elif prod_type == 'DAP Future':
        dic_asset[prod_id] = B3Future.DAPFuture(ql.Date().from_date(dt_maturity), ipca_prt)
        dic_asset[prod_id].setPricingEngine(engine_DAP)
        
    elif prod_type == 'NTN-B':
        dic_asset[prod_id] = BrazilianBond.NTNB(ql.Date().from_date(dt_maturity), 
                                                ql.Date().from_date(dt_issue),
                                                vna, True)
        dic_asset[prod_id].setPricingEngine(engine_NTNB)
        
    elif prod_type == 'NTN-F':
        dic_asset[prod_id] = BrazilianBond.NTNF(ql.Date().from_date(dt_maturity))
        dic_asset[prod_id].setPricingEngine(engine_NTNF)
        
    elif prod_type == 'LTN':
        dic_asset[prod_id] = BrazilianBond.LTN(ql.Date().from_date(dt_maturity))
        dic_asset[prod_id].setPricingEngine(engine_DI)

    print(prod_id, dic_asset[prod_id].NPV())
        

#%%
# ql_dt = ql.Date.from_date(dt)
# ql_dt_end = ql.Date.from_date(dfAsset[dfAsset['product_id'].isin(dfPosition.index)]['date_maturity'].max())
# dt_index = [ql.Brazil().advance(ql_dt,ql.Period(i,ql.Days)).to_date() for i in range(ql.Brazil().businessDaysBetween(ql_dt, ql_dt_end))]
# del ql_dt, ql_dt_end
#%%
dic_df = {}
df_ids = ['cashflow', 'pv01']
for i in df_ids:
    dic_df[i] = pd.DataFrame(columns=dic_position.keys())

for prod_id, qty in dic_position.items():
    temp_prod = dic_asset[prod_id] 
    if isinstance(temp_prod, ql.Bond):
        temp_dic = BrazilianBond.BRLBond.cashflow_to_dict(dt, temp_prod, 1)
        for dt_i, cf_i in temp_dic.items():
            dic_df['cashflow'].loc[dt_i, prod_id] = cf_i * temp_prod.NPV() * qty
            dic_df['pv01'].loc[dt_i, prod_id] = cf_i * dic_pv01[prod_id] * qty
    else:
        dic_df['cashflow'].loc[temp_prod.maturityDate().to_date(), prod_id] = temp_prod.NPV() * qty * -1
        dic_df['pv01'].loc[temp_prod.maturityDate().to_date(), prod_id] = dic_pv01[prod_id] * qty 
dic_df['cashflow'] /= nav
dic_df['pv01'] /= (nav/10000)

curves = ['Curva Pré', 'Cupom IPCA']
for (prod_types, curve) in zip ([['DI1Future', 'NTN-F', 'LTN'],['DAP Future', 'NTN-B',]], curves):
    lst_prod = dfPosition[dfPosition['product_type'].isin(prod_types)].index
    for i in df_ids:
        dic_df[i][curve] = dic_df[i][lst_prod].sum(axis=1)

#%%
for curve in curves:
    fig, axes = plt.subplots(1, 2, figsize=(11,4))  
    
    for i, df_id in enumerate(df_ids):
    
        dt_end = dic_df[df_id][dic_df[df_id][curve]!=0].index.max() + datetime.timedelta(days=+30)
        dt_index = [dt + datetime.timedelta(days=+i) for i in range((dt_end - dt).days)]
        dfPlot = pd.DataFrame(index=dt_index)
    
        dfPlot = dfPlot.join(dic_df[df_id][curve]).fillna(0).sort_index(ascending=False)
        dfPlot['expo_acum'] = dfPlot[curve].cumsum()
        dfPlot['pos'] = dfPlot[dfPlot['expo_acum']>0]['expo_acum']
        dfPlot['neg'] = dfPlot[dfPlot['expo_acum']<0]['expo_acum']
           
        ax=axes[i]
        
        ax.set_title('Gap Analysis - {} ({})'.format(curve, df_id))
        ax.fill_between(dfPlot.index, 0, dfPlot['expo_acum'], where=dfPlot['expo_acum']>0, step='pre', color=color2, alpha=0.5,interpolate =False)
        ax.fill_between(dfPlot.index, 0, dfPlot['expo_acum'], where=dfPlot['expo_acum']<0, step='pre', color='tomato', alpha=0.5,interpolate =False)
        
        ax.plot(dfPlot.index, dfPlot['pos'], color=color2)
        ax.plot(dfPlot.index, dfPlot['neg'], color='tomato')
        ax.set_xlim(left=dt)
        ax.axhline(0, color='k', lw=0.5)
        ax.grid(ls='--')
        # ax.xaxis.set_major_locator(mdates.MonthLocator(3))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%y'))
        if df_id == 'pv01':
            ax.set_yticklabels(['{:2.3f}x'.format(x) if x!=0 else '-' for x in ax.get_yticks()])
        else:
            ax.set_yticklabels(['{:2.1%}'.format(x) if x!=0 else '-' for x in ax.get_yticks()])
    
    plt.show()





#%%
# SELECT p.[id],p.[entity_id],ts.field
# ,pp.price, tsv.value/100 as return_1d
#   FROM [middle].[product] p 
#   INNER JOIN middle.product_price pp ON p.id = pp.product_id
#   INNER JOIN quant.time_series ts ON ts.entity_id = p.entity_id
#   INNER JOIN quant.time_series_value tsv ON ts.id = tsv.series_id
#   WHERE ts.field = 'CHG_PCT_1D' 
#     AND pp.date_reference = '2020-11-26' AND
# 		tsv.date_reference = '2017-5-18'
