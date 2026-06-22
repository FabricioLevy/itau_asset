import pandas as pd
import numpy as np
import datetime
import sqlalchemy as sa
import QuantLib as ql
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
from adjustText import adjust_text
import xlwings as xw
import os


dt = datetime.date(2021, 9, 29)

calendar_br = ql.Brazil()
today = ql.Date.from_date(dt)
dt1m = calendar_br.advance(today, ql.Period('-1M')).to_date()
dt1w = calendar_br.advance(today, ql.Period('-1W')).to_date()

engine = sa.create_engine('mssql+pyodbc://saprod:nhjmmn&^Yh%%^yhjU&@srvprod1.database.windows.net,1433/dbprod1?driver=SQL+Server+Native+Client+11.0')
connection = engine.connect()

str_sql = """
    SELECT date_reference, s.product_id, s.a1_sector as sector, [pct]/100 as perc
        FROM [b3].[ibovespa_composition] c inner join b3.sector_classification s on c.code = s.product_id
        WHERE date_reference = (SELECT max([date_reference]) FROM [b3].[ibovespa_composition] WHERE date_reference <= '{:%Y-%m-%d}')
          """
dfIbovComp = pd.read_sql(str_sql.format(dt), connection, index_col='product_id')

str_sql = """
SELECT p.product_underlying as product_id, qtsv.date_reference, qts.field, qtsv.value   
  FROM [quant].[time_series] as qts 
	INNER JOIN middle.product as p ON qts.entity_id = p.entity_id
	INNER JOIN [quant].[time_series_value] as qtsv ON qtsv.series_id = qts.id
  WHERE qtsv.date_reference > '{:%Y-%m-%d}' and qts.field = 'CHG_PCT_1D' and qts.source = 'bloomberg'
""" 
str_sql = str_sql.format(dt-datetime.timedelta(90))
df = pd.read_sql(str_sql, connection)
dfRet = df[df['field']=='CHG_PCT_1D'].pivot(index='date_reference', columns='product_id', values='value').loc[:dt] / 100
dfRetEqty = dfRet[['SPX', 'IBVSP']+[i for i in dfIbovComp.index if i in dfRet]].fillna(0)

str_sql = """
SELECT qts.entity_id , qtsv.date_reference, qts.field, qtsv.value   
  FROM [quant].[time_series] as qts 
	INNER JOIN [quant].[time_series_value] as qtsv ON qtsv.series_id = qts.id
  WHERE qtsv.date_reference >= '{:%Y-%m-%d}' and qts.field = 'PX_LAST' and qts.source = 'bloomberg'
  and qts.entity_id  in ('USDBRL', 'USDMXN', 'USDCLP')
""" 
str_sql = str_sql.format(dt-datetime.timedelta(90))
df = pd.read_sql(str_sql, connection)
dfPrice = df[df['field']=='PX_LAST'].pivot(index='date_reference', columns='entity_id', values='value').loc[:dt]
dfPrice.fillna(method='ffill', inplace=True)
dfReturn = dfRetEqty.join(dfPrice.pct_change())

str_sql = """
            SELECT [date_reference],[curve_name],[tenor],[discount_factor],curve_rate,business_day
              FROM [risk].[interest_rate_curve]
            WHERE (
                  (curve_name='DI Fut' and tenor in (360, 720, 1800)) OR
                  (curve_name='NTNB Zero' and tenor in (720, 1800)) OR
                  (curve_name='DAP BEI' and tenor in (720, 1800)) OR
                  (curve_name='MXN TIIE Zero' and tenor in (720, 1800)) OR
                  (curve_name='Swap CLP Zero' and tenor in (720, 1800)) OR
                  (curve_name='Swap COP Zero' and tenor in (720, 1800))                       
                  )
        		AND [date_reference] >= '{:%Y-%m-%d}'
         """
str_sql = str_sql.format(dt-datetime.timedelta(90))         
df = pd.read_sql(str_sql, connection)

dic_curve = {'DI Fut'   : 'PRE',
             'NTNB Zero': 'NTNB',
             'DAP BEI'  : 'BEI',
             'MXN TIIE Zero' : 'MXN',
             'Swap CLP Zero' : 'CLP',
             'Swap COP Zero' : 'COP'}

dic_tenor = {360:'1Y', 720:'2Y', 1800:'5Y'}

df['curve_id'] = df[['curve_name', 'tenor']].apply(lambda x: dic_curve[x['curve_name']] + '_' + dic_tenor[x['tenor']], axis=1)
dfCurve = df.pivot(index='date_reference', columns='curve_id', values='discount_factor').fillna(method='ffill')
curvas = list(dfCurve.columns)
dfReturn = dfReturn.join(dfCurve.pct_change())

connection.close()
del str_sql, connection, engine
#%%
txts=[]
cm = plt.cm.get_cmap('tab10')
fig, ax = plt.subplots(1,1, figsize=(12,8))
dfVol = dfReturn.ewm(alpha=0.06).std() * np.sqrt(252)
x0, y0 = 0, 0
for c, asset in enumerate(['IBVSP', 'SPX', 'USDBRL', 'USDMXN', 'PRE_2Y']):
    for d, str_p in zip([dt1m, dt1w, dt],[' 1m',' 1w','']):
        y = ((dfReturn.loc[:d].iloc[-21:]+1).cumprod()-1).loc[d, asset]
        x = dfVol.loc[d, asset]
        # x = vol.loc[asset]
        # y = ret.loc[asset]
        ax.scatter([x], [y], zorder=5, s=80 if d==dt else 40, color=cm.colors[c])
        dx = x - x0
        dy = y - y0
        if d != dt1m:
            ax.arrow(x0, y0, dx, dy, width=0.00005, head_width=0.003, color='k', length_includes_head=True)
        if d == dt:
            txts.append(ax.text(x, y, asset+str_p, zorder=6, color=cm.colors[c], fontweight='bold'))
        x0=x
        y0=y
adjust_text(txts,ax=ax)
ax.axhline(0, color='k', lw=0.5, ls='--')
ax.set_xlim(left=0)
ax.grid(ls='--')
plt.show()
#%%