import pandas as pd
import timeit
import datetime
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import QuantLib as ql
import fund_utils as fu


#%%
def main(dt, str_fund, nav, report_filename):
    #%%
    _, connection = fu.get_DB_conn('prod')
    
    str_sql = """
        SELECT *
        --[lote45_product],[lote45_product_class]
          --      [primitive],[primitive_class], bucket
           --     [amount],[delta], gamma, vega
                FROM [lote45].[primitive]
                WHERE date_reference = '{:%Y-%m-%d}' and trading_desk = '{}'
                """
    str_sql = str_sql.format(dt, str_fund)
    df = pd.read_sql(str_sql, connection)
    
    str_tree = 'Risk'
    str_sql = """
       SELECT [parent_tree],[parent_node],[node],[book]
       FROM [lote45].[book_tree]
       WHERE parent_tree = '{}'
                """
    dfTree = pd.read_sql(str_sql.format(str_tree), connection)
    del str_sql

    #%%
    nd = fu.Node(str_tree, dfTree)    
    dic_books = nd.to_dict(str_tree)    

    book_map = {}
    for k, v in dic_books.items():
        for book in v:
            book_map[book] = k
    #%%
    currencies = [i[:6] for i in df[(df['primitive_class']=='FX')]['primitive'].unique()]
    equities = list(df[(df['primitive_class']=='Equity')]['primitive'].unique())

    scenario_keys = ['IBVSP', 'USDBRLSpot', 'BRD_00360', 'DI_00360', 'DI_01800', 'IPCA_COUPON_01800']
    scenario_key_names = ['IBOV', 'USD/BRL', 'CC 1Y', 'PRE 1Y', 'PRE 5Y', 'IPCA 5Y']
    
    scenario_dates = [datetime.date(2017, 5, 18), datetime.date(2020, 3, 12), datetime.date(2018, 5, 28),
                      datetime.date(2018, 10, 8), datetime.date(2008, 9, 15), datetime.date(2011, 9, 1)]
    scenario_desc = ['Joesley Scandal', 'Pandemia', "Brazil truck drivers' strike",
                     'Bolsonaro Election', 'Lehman Brothers', "COPOM 'Cavalo de Pau'"]
    
    dic_returns = {}
    dic_scenario_keys = {}
    
    for i_scenario, date_scenario in enumerate(scenario_dates):   
        dfReturn = pd.DataFrame(columns=['ret_pct'])
        dfReturn = pd.concat([dfReturn, get_equity_scenario(connection, dt, date_scenario, equities)])
        dfReturn = pd.concat([dfReturn, get_curve_scenario(connection, date_scenario)])
        dfReturn = pd.concat([dfReturn, get_fx_scenario(connection, date_scenario, currencies)])        
        
        dic_scenario_keys[date_scenario] = dfReturn.loc[scenario_keys]
        
        df[str_tree] = df['book'].apply(lambda x: book_map[x])
        dfTemp = df.join(dfReturn, on='primitive')
        dfTemp['PnL'] = (dfTemp['eq_position']*dfTemp['ret_pct'] + 0.5 * dfTemp['gamma'] * (dfTemp['ret_pct']**2)) / nav
        
        dic_returns[date_scenario] = pd.DataFrame(dfTemp[[str_tree, 'PnL']].groupby([str_tree]).sum())
    
    
    
    
    
    #%%
    
    color1, color2 = fu.color_palette[0:2]
        
    fig = plt.figure(figsize=(10, 14.5))
    outer = gridspec.GridSpec(3, 2, wspace=0.2, hspace=0.5)

    for i_scenario, date_scenario in enumerate(scenario_dates):
      
        inner = gridspec.GridSpecFromSubplotSpec(2, 1, subplot_spec=outer[i_scenario], wspace=0.1, hspace=0.5, height_ratios=[2, 5])

        ax = plt.Subplot(fig, inner[0])
        ax.set_title('{:%d-%b-%y}\n{}'.format(date_scenario, scenario_desc[i_scenario]), fontweight='bold')
        dic_scenario_keys[date_scenario]['ret_pct'].plot(kind='bar', ax=ax, 
                                   color=(dic_scenario_keys[date_scenario]['ret_pct'] > 0).map({True: color2, False: 'tomato'}),
                        legend=False, zorder=2, alpha=0.55)
        ax.set_xticklabels(scenario_key_names, rotation=0, fontweight='bold', fontsize=8)
        for i, (ind, row) in enumerate(dic_scenario_keys[date_scenario].iterrows()):
            v = row['ret_pct']
            ax.text(i, 0, '{:+2.1%}'.format(v), ha='center', va='bottom', 
                    color='k' if v>=0 else 'r', fontweight='bold')
        ax.axhline(0, lw=0.5, color='k')
        ax.grid(axis='y')
        ax.set_ylim(top=max(0.05, ax.get_ylim()[1]), bottom=min(-0.05, ax.get_ylim()[0]))
        ax.set_yticklabels(['{:1.1%}'.format(i) for i in ax.get_yticks()])

        fig.add_subplot(ax)
        
        ax = plt.Subplot(fig, inner[1])
        ax.set_title('SImulated PnL')
        dic_returns[date_scenario]['PnL'].plot(kind='bar', ax=ax,
                                   color=(dic_returns[date_scenario]['PnL'] > 0).map({True: color2, False: 'tomato'}),
                        legend=False, zorder=2, alpha=0.7)
        for i, (ind, row) in enumerate(dic_returns[date_scenario].iterrows()):
            v = row['PnL']
            ax.text(i, 0, '{:+2.1f}'.format(v*100), ha='center', va='bottom', 
                    color='k' if v>=0 else 'r', fontweight='bold')
        ax.set_xticklabels(dic_returns[date_scenario].index.str.replace(' ','\n'), rotation=90)
        ax.set_xlabel('')
        val = dic_returns[date_scenario]['PnL'].sum()
        ax.annotate('Total\n{:+2.2%}'.format(val), zorder=3, xy=(0,0),
                                  xytext=(0.5, 0.1), textcoords='axes fraction', fontweight='bold',
                                  fontsize=12, color='k', ha='center',
                                  bbox=dict(boxstyle="round", fc=color2 if val>0 else 'tomato', ec="0.5", alpha=1))
        ax.axhline(0, lw=0.5, color='k')
        ax.grid(axis='y')
        ax.set_ylim(bottom=min(-0.005, ax.get_ylim()[0]))
        ax.set_yticklabels(['{:1.1%}'.format(i) for i in ax.get_yticks()])
        fig.add_subplot(ax)
        fig_file = '../output/temp_figs/{:%Y%m%d}_scenario_simulatio.svg'.format(dt)
        fig_file = '../output/temp_figs/{:%Y%m%d}_scenario_simulatio.pdf'.format(dt)
        fig.savefig(fig_file, bbox_inches = "tight")

    
    
    #%%
    connection.close()
    return 0
    
#%%
def get_fx_scenario(connection, date_scenario, currencies):
    
    prev_day =  ql.Brazil().advance(ql.Date.from_date(date_scenario), ql.Period("-1d")).to_date()
       
    str_sql = """
        SELECT ts.entity_id + 'Spot' as primitive, tsv.date_reference, tsv.value
        FROM quant.time_series_entity tse 
    		INNER JOIN quant.time_series ts ON ts.entity_id = tse.id 
            JOIN quant.time_series_value tsv ON tsv.series_id = ts.id
        WHERE ts.field = 'PX_LAST' 
        AND tsv.date_reference in ('{:%Y-%m-%d}', '{:%Y-%m-%d}')
        AND tse.id in ('{}')
    """
    str_sql = str_sql.format(date_scenario, prev_day, "','".join(currencies))
    df = pd.read_sql(str_sql, connection)
    df = df.pivot(index='primitive', columns='date_reference', values='value')
    df['ret_pct'] = df[date_scenario]/df[prev_day] - 1
    
    return pd.DataFrame(df['ret_pct'])
#%%
def get_equity_scenario(connection, date_reference, date_scenario, equities):
    
    str_sql = """
        SELECT lote45_product, tsv.value/100 as ret_pct
        FROM [middle].[product] p 
    		INNER JOIN middle.product_price pp ON p.id = pp.product_id
             JOIN quant.time_series_entity tse ON p.entity_id = tse.id
             JOIN quant.time_series ts ON ts.entity_id = tse.id 
             JOIN quant.time_series_value tsv ON tsv.series_id = ts.id
        WHERE ts.field = 'CHG_PCT_1D' 
            and pp.date_reference = '{:%Y-%m-%d}'
            and tsv.date_reference = '{:%Y-%m-%d}' 
            and [product_type] in ('Equity', 'Equity Index')
    """
    
    str_sql = str_sql.format(date_reference, date_scenario)
    df = pd.read_sql(str_sql, connection, index_col='lote45_product')

    str_sql = """
        SELECT [primitive1],[primitive2],[covar_value]
        FROM [lote45].[covar_matrix]
        WHERE date_reference = '{:%Y-%m-%d}' 
        ORDER BY 1, 2
        """
    str_sql = str_sql.format(date_reference)
    dfCovarDB = pd.read_sql(str_sql, connection).pivot(index='primitive1', columns='primitive2', values='covar_value').fillna(0)
    dfBeta = pd.DataFrame((dfCovarDB['IBVSP'] + dfCovarDB.loc['IBVSP']) / dfCovarDB.loc['IBVSP', 'IBVSP'])
    dfBeta = dfBeta.loc[equities]
    dfBeta.loc['IBVSP'] = 1
    df = (dfBeta * df.loc['IBVSP','ret_pct']).join(df)
    df.loc[df['ret_pct'].isna(), 'ret_pct'] = df['IBVSP']
    
    return pd.DataFrame(df['ret_pct'])

#%%
def get_curve_scenario(connection, date_scenario):
    prev_day =  ql.Brazil().advance(ql.Date.from_date(date_scenario), ql.Period("-1d")).to_date()
    
    curves = ['DI Fut', 'NTNB Zero', 'USD BR']
    lote45_curves = ['DI_', 'IPCA_COUPON_', 'BRD_']
    dic_curve = dict(zip(curves, lote45_curves))
    
    str_sql = """
       SELECT [date_reference],[curve_name],[tenor_date],[tenor],[curve_rate],[discount_factor]
           FROM [risk].[interest_rate_curve]
           WHERE date_reference in ('{:%Y-%m-%d}', '{:%Y-%m-%d}')
               and curve_name in ('{}') 
               and tenor is not null
            ORDER BY tenor
    """
    str_sql = str_sql.format(date_scenario, prev_day, "','".join(curves))
    df = pd.read_sql(str_sql, connection)
    df['primitive'] = df['curve_name'].apply(lambda x: dic_curve[x]) + df['tenor'].apply(lambda x: '{:05.0f}'.format(x))
    dfReturn = pd.DataFrame(columns=['ret_pct'])
    for c, lote45_c in zip(curves, lote45_curves):
        dfTemp = df[df['curve_name']==c].pivot(index='primitive',  columns='date_reference', values='discount_factor')
        dfAux = pd.DataFrame(columns=['ret_pct'])
        dfAux['ret_pct'] = dfTemp[date_scenario]/dfTemp[prev_day] - 1
        dfReturn = pd.concat([dfReturn,  dfAux])
    return dfReturn
#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt = datetime.date(2021, 6, 29)
    str_fund = 'A1 Master FIM'
    nav = fu.get_NAV(dt, str_fund)
    report_filename = '../xls/RiskMap_model.xlsm'
    main(dt, str_fund, nav, report_filename) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))    