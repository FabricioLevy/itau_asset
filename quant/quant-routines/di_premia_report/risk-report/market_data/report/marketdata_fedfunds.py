import pandas as pd
import numpy as np
import datetime
import QuantLib as ql
from adjustText import adjust_text
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.gridspec as gridspec
from matplotlib.ticker import MultipleLocator

import os, sys
sys.path.insert(1,  '../../')
from market_data import curve_db

from a1db.a1sql import SQLConnection

#%%
def main(dt, figsize=(11, 5)):
#%%
    today = ql.Date.from_date(dt)
    str_curvename = 'FF Fut'
 
    connection = SQLConnection().get_connection()
    str_sql = f"""
               SELECT [id], [date_maturity], pp.price, pp.rate
               FROM [middle].[product] p 
                   INNER JOIN middle.product_price pp ON p.id = pp.product_id
               WHERE product_type = 'FF Futures' and
                   date_reference = '{dt:%Y-%m-%d}'
               ORDER BY date_maturity
              """
    df = pd.read_sql(str_sql, 
                     connection,
                     index_col='id')
    
    str_sql = f"""
                SELECT [date_reference],[value]/100 as FF
                    FROM [quant].[time_series_value] tsv
                      INNER JOIN [quant].[time_series] ts ON tsv.series_id = ts.id
                    WHERE ts.entity_id = 'FedFundRate'
                        AND date_reference BETWEEN DATEADD(MONTH, -6, '{dt:%Y-%m-%d}')
                                           AND '{dt:%Y-%m-%d}'
                    ORDER BY date_reference
                """
    dfFF_fixing = pd.read_sql(str_sql,
                              connection,
                              index_col='date_reference')
    
    str_sql = f"""
                SELECT date_effective
                FROM [research].[monetary_policy_meeting]
                WHERE country = 'USD'
                    and date_effective >= DATEADD(MONTH, -6, '{dt:%Y-%m-%d}')
                ORDER BY date_effective
                """
    dates_FOMC = list(pd.read_sql(str_sql, connection)['date_effective'])
    
    del str_sql    
#%%
    dts = list(dfFF_fixing.index) + \
        [ql.UnitedStates().advance(today, ql.Period(i, ql.Days)).to_date() for i in range(550)]
        
    dfPlot = pd.DataFrame(index=dts).join(df.set_index('date_maturity')['rate'])
    dfPlot = dfPlot.join(dfFF_fixing['FF'])
    dfPlot.loc[dt:,'rate'].fillna(method='bfill', inplace=True)
    # dfPlot.loc[:dt, 'rate'] = pd.NA

    fig, ax = plt.subplots(1,1, figsize=figsize)
    
    ax.plot(dfPlot.index, dfPlot['FF'], lw=2, label='Fed Funds')  
    ax.plot(dfPlot.index, dfPlot['rate'], lw=2, ls='--', label=dt) 
    
    ax.set_ylim(bottom=0)
    ax.axvline(dt, ls='--', lw=2, c='tomato')
    ax.text(dt, 0, ' Today', color='tomato', va='bottom', ha='left', fontweight='bold')
    
    ax.grid(ls='--')
    ax.legend()
    plt.show()

#%%
    return fig
   
#%%    
if __name__ == "__main__":
    
    dt = datetime.date(2023, 1, 10)
    main(dt)
    