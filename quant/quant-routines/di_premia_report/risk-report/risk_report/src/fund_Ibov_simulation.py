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

sys.path.insert(1, os.path.expanduser('~\\Documents\\Github\\instruments'))
from B3 import B3Future

#%%
def main(dt, str_fund, nav, report_filename): 
    #%%
    dt = ql.Brazil(ql.Brazil().Exchange).adjust(ql.Date.from_date(dt), ql.Preceding).to_date()
    _, connection = fu.get_DB_conn('prod')
    
    str_sql = """
        SELECT [primitive1],[primitive2],[covar_value]
        FROM [lote45].[covar_matrix]
        WHERE date_reference = '{:%Y-%m-%d}' 
        ORDER BY 1, 2
        """
    str_sql = str_sql.format(dt)
    df = pd.read_sql(str_sql, connection)
    dfCovarDB = df.pivot(index='primitive1', columns='primitive2', values='covar_value').fillna(0)
    dfBeta = pd.DataFrame((dfCovarDB['IBVSP'] + dfCovarDB.loc['IBVSP']) / dfCovarDB.loc['IBVSP', 'IBVSP'])
    dfBeta.loc['IBVSP']=1
    dfBeta.loc['IBOV']=1
    dic_beta = dfBeta['IBVSP'].to_dict()
            
    str_sql = """
           SELECT [id] as product_id,[product_type],[lote45_product],[lote45_product_class]
          ,[product_currency],[product_underlying],[date_maturity]
          ,[option_type],[option_style],[option_strike], lot_size
      FROM [middle].[product]
      WHERE ((product_type in ('Equity Option', 'Equity Future') and date_maturity > '{:%Y-%m-%d}')
             or product_type = 'Equity')
             and onshore_risk = 1
            """
    str_sql = str_sql.format(dt)
    dfAsset = pd.read_sql(str_sql, connection)
    
    ids = "','".join(set(dfAsset[['product_id','product_underlying']].fillna('x').values.flatten()))
    
    str_sql = """
                SELECT [product_id],[price] FROM [middle].[product_price]
                WHERE product_id in ('{}') and date_reference = '{:%Y-%m-%d}'
      """
    str_sql = str_sql.format(ids, dt)
    dfPrice = pd.read_sql(str_sql, connection, index_col='product_id')
    dic_price = dfPrice['price'].to_dict()
    
    str_sql = """
    SELECT p.id as product_id, bo.book, sum(bo.value) as amount
      FROM [lote45].[book_overview] bo INNER JOIN middle.product p ON bo.lote45_product = p.lote45_product
      WHERE bo.date_reference = '{:%Y-%m-%d}' and bo.trading_desk = '{}' and bo.measure = 'Amount'
      and p.product_type in ('Equity Option','Equity Future', 'Equity')
      --and book='MS Bolsa'
      and onshore_risk = 1
      GROUP BY p.id, bo.book
    """
    str_sql = str_sql.format(dt, str_fund)
    dfPosition = pd.read_sql(str_sql, connection).pivot(index='product_id', columns='book', values='amount').fillna(0)
    dfPosition['TOTAL'] = dfPosition.sum(axis=1)
    dic_position = dfPosition['TOTAL'].to_dict()
    dic_position_ms = dfPosition['MS Bolsa'].to_dict() if 'MS Bolsa' in dfPosition.columns else {}
    
    dfAsset = dfAsset.join(dfPosition['TOTAL'], on='product_id').join(dfPrice, on='product_id')
    dfAsset = dfAsset[~dfAsset['TOTAL'].isna()]
    dfAsset.loc[dfAsset['product_type']=='Equity', 'product_underlying'] = dfAsset['product_id']
    dfAsset.set_index('product_id', inplace=True)
    
    # connection.close()
    # del str_sql, ids, connection, df, dfPrice, dfBeta, dfCovarDB
    del str_sql, ids, df, dfPrice, dfBeta, dfCovarDB

    #%%
    def delta(self):
        return 1
    ql.Stock.delta = delta

    #%%
    today = ql.Date.from_date(dt)
    ql.Settings.instance().evaluationDate = today
    calendar_br = ql.Brazil()
    day_count = ql.Business252(calendar_br)
    
    curve_name = 'DI Fut'
    risk_free = curve_db.get_curve(today.to_date(), curve_name)
    risk_free_handle = ql.YieldTermStructureHandle(risk_free)
    
    # Add Underlyings to dictionary
    dic_Underlying = {underlying_id: ql.SimpleQuote(dic_price[underlying_id])
                      for underlying_id in set(dfAsset['product_underlying'].dropna())}
    
    if 'IBOV' not in dic_Underlying.keys():
        dic_Underlying['IBOV'] = ql.SimpleQuote(dic_price['IBOV'])

#%%
    dic_Asset = {}
    dic_Vol = {}
    
    cols = ['product_underlying', 'date_maturity', 'option_type', 'option_style', 'option_strike']
    for opt_id, row in dfAsset[dfAsset['product_type']=='Equity Option'].iterrows():
        (underlying_id, dt_exp, opt_type, opt_style, opt_strike) = row[cols]
        ql_opt_type = ql.Option.Call if opt_type.upper() == 'C' else ql.Option.Put
        ql_dt_exp = ql.Date.from_date(dt_exp)
        # set_SimuDates.add(calendar_br.advance(ql_dt_exp, ql.Period('-1d')))
        exercise = ql.EuropeanExercise(ql_dt_exp) #if opt_style.upper() == 'E' else ql.AmericanExercise(calculation_date, ql_dt_exp)
        payoff = ql.PlainVanillaPayoff(ql_opt_type, opt_strike)
        option = ql.VanillaOption(payoff, exercise)
           
        # volatility = ql.SimpleQuote(1.0)
        dic_Vol[opt_id] = ql.SimpleQuote(1.0)
        flat_vol_ts = ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, calendar_br, ql.QuoteHandle(dic_Vol[opt_id]), day_count))
        bsm_process = ql.BlackScholesProcess(ql.QuoteHandle(dic_Underlying[underlying_id]), risk_free_handle, flat_vol_ts)
        try:
            str_sql = """
                        SELECT [ReportDate], [VolatilityValue]/100 as vol
                        FROM [up2data].[Equities_OptionOnEquitiesReferencePriceFile]
                        WHERE [ReportDate] = '{:%Y-%m-%d}'
                        AND [TickerSymbol] = '{}'
                      """
            str_sql = str_sql.format(dt,opt_id[:-3])
            dic_Vol[opt_id].setValue(pd.read_sql(str_sql, connection, index_col='ReportDate').loc[dt, 'vol'])
        except:
            dic_Vol[opt_id].setValue(option.impliedVolatility(dic_price[opt_id], bsm_process))
            
        option.setPricingEngine(ql.AnalyticEuropeanEngine(bsm_process))
    
        dic_Asset[opt_id] = option
        
    # del opt_id, underlying_id, dt_exp, opt_type, opt_style, opt_strike, ql_opt_type, ql_dt_exp, exercise, option, cols
   

#%%
    cols = ['product_underlying', 'date_maturity', 'lot_size']
    for product_id, row in dfAsset[dfAsset['product_type']=='Equity Future'].iterrows():
        (underlying_id, dt_exp, lot_size) = row[cols]
        future = B3Future.IbovespaFuture(ql.QuoteHandle(dic_Underlying[underlying_id]), ql.Date.from_date(dt_exp), lot_size)
        future.setPricingEngine(ql.DiscountingBondEngine(risk_free_handle))
        dic_Asset[product_id] = future
    # del product_id, underlying_id, dt_exp
#%%
    for product_id in dfAsset[dfAsset['product_type']=='Equity'].index:
        eqty = ql.Stock(ql.QuoteHandle(dic_Underlying[product_id]))
        dic_Asset[product_id] = eqty
    # del product_id
#%%
    ibov = dic_Underlying['IBOV']
    ibov_0 = ibov.value()
    
    rng = (0.85, 1.1501)
    xs = np.round(np.arange(rng[0], rng[1], 0.0005), 4)
    key_value_aux = 5*int(ibov_0/5000)
    key_values = [np.round(1000*i/ibov_0, 6) for i in [key_value_aux-5*i for i in [2,1,0]]]
    xs = sorted(np.append(xs,key_values))
    
    dic_simu = {}
    
    dic_simu['Price'] = pd.DataFrame(columns=['IBOV'] + list(dic_Asset.keys()))
    dic_simu['PnL'] = pd.DataFrame(columns=dic_Asset.keys())
    dic_simu['Delta'] = pd.DataFrame(columns=dic_Asset.keys())
    dic_simu['Delta_MS'] = pd.DataFrame(columns=dic_Asset.keys())
    
    for x in xs:
        ibov.setValue(x * ibov_0)
        for underlying_id in [x for x in dic_Underlying.keys() if x not in ['IBOV']]:
            dic_Underlying[underlying_id].setValue(dic_price[underlying_id]*(1+((x-1)*dic_beta.get(underlying_id, 1))))
        dic_simu['Price'].loc[x, 'IBOV'] = ibov.value()
        for asset_id, asset in dic_Asset.items():
            lot_size = asset.lotSize() if type(asset)==B3Future.IbovespaFuture else 1
            dic_simu['Price'].loc[x, asset_id] = asset.NPV()
            dic_simu['PnL'].loc[x, asset_id] = (asset.NPV() - dic_price[asset_id]) * lot_size * dic_position[asset_id] / nav
            dic_simu['Delta'].loc[x, asset_id] = asset.delta() * dic_Underlying[dfAsset.loc[asset_id, 'product_underlying']].value() * dic_position[asset_id] / nav
            dic_simu['Delta_MS'].loc[x, asset_id] = asset.delta() * dic_Underlying[dfAsset.loc[asset_id, 'product_underlying']].value() * dic_position_ms.get(asset_id,0) / nav
    ibov.setValue(ibov_0)
    for underlying_id in dic_Underlying.keys():
        dic_Underlying[underlying_id].setValue(dic_price[underlying_id])
        
#%%
    product_types = list(dfAsset['product_type'].unique())
    for simu_key in ['PnL', 'Delta', 'Delta_MS']:
        for prod_type in product_types:
            ids = dfAsset[dfAsset['product_type']==prod_type].index
            dic_simu[simu_key][prod_type] = dic_simu[simu_key][ids].sum(axis=1)
        dic_simu[simu_key]['Total'] = dic_simu[simu_key][dfAsset.index].sum(axis=1)
    del prod_type
#%%
    dfOutput = pd.DataFrame(index=dic_simu['Delta'].index, columns=['IBOV'] + product_types + ['Total'])
    dfOutput['IBOV'] = dic_simu['Price']['IBOV']
    dfOutput[product_types+ ['Total']] = dic_simu['Delta'][product_types+ ['Total']]
    dfOutput['PnL Total'] = dic_simu['PnL']['Total']
    dfOutput.to_excel('../output/temp_figs/{:%Y%m%d}_{}_ibov_simulation.xlsx'.format(dt, str_fund))
    
    dfOutput = pd.DataFrame(index=dic_simu['Delta_MS'].index, columns=['IBOV'] + product_types + ['Total'])
    dfOutput['IBOV'] = dic_simu['Price']['IBOV'].apply(lambda x: float(x))
    dfOutput[product_types+ ['Total']] = dic_simu['Delta_MS'][product_types+ ['Total']]
    dfOutput.to_excel('../output/temp_figs/{:%Y%m%d}_{}_ibov_simulation_MS.xlsx'.format(dt, str_fund))
    #%%
    dfTable = pd.merge_asof(pd.DataFrame(index=np.linspace(round(ibov_0/1000,0)-10, round(ibov_0/1000,0)+10, 21)*1000.0),
                  dfOutput, right_on='IBOV', left_index=True, direction='nearest').set_index('IBOV')
    fig, ax = plt.subplots(figsize=(6,5.2))
    ax.axis('off')
    ax.set_title("Delta (%NAV) - {} - MS Bolsa".format(str_fund), fontsize=11, weight='bold')
    ax.table(cellText=dfTable.applymap('{:,.1%}'.format).values,
             rowColours=['silver']*21, colColours=['silver']*4,
                      rowLabels=['{:2,.0f}k'.format(round(i/1000)) for i in dfTable.index],
                      colLabels=dfTable.columns,loc='center', cellLoc='center')
    plt.show()
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_ibov_simulation_MS_table.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
#%%
    color1 = '#323E48'
    color_palette =['#28829B', 'dodgerblue','royalblue','#C9CBCB', '#748D9E', '#2E9AB2']
    
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.75))
    plt.tight_layout(w_pad=2.3)
    
    ##### PNL ####
    ax=axes[0]
    dic_simu['PnL'][product_types].plot(ax=ax, ls='-', lw=2, color=color_palette)
    dic_simu['PnL']['Total'].plot(ax=ax, ls='--', lw=3.5, color='k', label='Total')
    texts = []
    y_min, y_max = ax.get_ylim()
    for i, x in enumerate(key_values):
        val = dic_simu['PnL'].loc[x,'Total']
        ibov_val = dic_simu['Price'].loc[x, 'IBOV']
        if (val - y_min)/(y_max - y_min) > 0.5:
            shift_y = -50
        else:
            shift_y = 40
        # ax.text(x, val, '{:2.2%}'.format(val))
        
        texts.append(ax.annotate('{:2.0f}k\n{:4.2%}'.format(ibov_val/1000, val), 
                                 xy=(x, val), xycoords='data', zorder=3,
                              xytext=(0, shift_y), textcoords='offset points', fontweight='bold',
                              fontsize=11, color=color1, ha='center',
                              bbox=dict(boxstyle="round", fc='silver' if val>0 else 'tomato', ec="0.5", alpha=0.8),
                arrowprops=dict(facecolor='r', arrowstyle="->", connectionstyle="arc3")))
    
    # adjust_text(texts, ax=ax)
    ax.set_title('Simulated PnL',fontweight='bold')
    ax.set_ylabel('PnL (%NAV)',fontweight='bold')
    ticks_loc = ax.get_yticks().tolist()
    ax.yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
    ax.set_yticklabels(['{:2.2%}'.format(i) for i in ticks_loc])
    ax.axhline(0, color='k', lw=0.75, ls='--')
    
    ##### DELTA ####
    ax=axes[1]
    for i, col in enumerate(product_types):
        dic_simu['Delta'][col].plot(ax=ax, ls='-', lw=2, color=color_palette[i],
                                          label='{} ({:2.1%})'.format(col.split(' ')[-1], dic_simu['Delta'].loc[1,col]))
    dic_simu['Delta']['Total'].plot(ax=ax, ls='--', lw=3.5, color='k', label='Total ({:2.1%})'.format(dic_simu['Delta'].loc[1,'Total']))
    texts = []
    y_min, y_max = ax.get_ylim()
    for i, x in enumerate(key_values):
        val = dic_simu['Delta'].loc[x,'Total']
        ibov_val = dic_simu['Price'].loc[x, 'IBOV']
        if (val - y_min)/(y_max - y_min) > 0.5:
            shift_y = -50
        else:
            shift_y = 40
        # ax.text(x, val, '{:2.2%}'.format(val))
        
        texts.append(ax.annotate('{:2.0f}k\n{:2.1%}'.format(ibov_val/1000, val), 
                                 xy=(x, val), xycoords='data', zorder=3,
                              xytext=(0, shift_y), textcoords='offset points', fontweight='bold',
                              fontsize=11, color=color1, ha='center',
                              bbox=dict(boxstyle="round", fc='silver' if val>0 else 'tomato', ec="0.5", alpha=0.8),
                arrowprops=dict(facecolor='r', arrowstyle="->", connectionstyle="arc3")))
    
    # adjust_text(texts, ax=ax)
    ax.set_title('Simulated Delta',fontweight='bold')
    ax.set_ylabel('Equity Delta (%NAV)',fontweight='bold')
    ticks_loc = ax.get_yticks().tolist()
    ax.yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
    ax.set_yticklabels(['{:2.1%}'.format(i) for i in ticks_loc])
    
    ##### ####
    for ax in axes:
        ax.legend(fontsize=9.5)
        ax.set_xlabel('Ibovespa change (%) and simulated level (BRL)',fontweight='bold')
        ax.axvline(1, color='k', lw=0.75, ls='--')
        ax.grid(ls='--')
        ax.set_xlim(left=dic_simu['PnL'].index[0], right=dic_simu['PnL'].index[-1])
        ticks_loc = ax.get_xticks().tolist()
        ax.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
        ax.set_xticklabels(['{:2.1%}\n{:2.1f}k'.format(i-1, dic_simu['Price'].loc[round(i,4), 'IBOV']/1000) for i in ticks_loc])
    ##### ####
    
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_ibov_simulation.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    wb = xw.Book(report_filename)
    wb.sheets('Equity_2').pictures.add(wb.api.Path + '/' + fig_file, name='ibov_simulation', update=True)
    # wb.sheets('Equity_2').pictures.add(fig, name='ibov_simulation', update=True)
#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt, str_fund = fu.get_config(['dt', 'str_fund'])
    report_filename = '../xls/RiskMap_model.xlsm'
    nav = fu.get_NAV(dt, str_fund)
    main(dt, str_fund, nav, report_filename) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))
    