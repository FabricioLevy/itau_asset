import pandas as pd
import datetime
import timeit
import xlwings as xw
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import fund_utils as fu

#%%
def main(dt, str_fund, report_filename, print_pdf=False):
    #%%
    _, connection = fu.get_DB_conn('prod')
    
    str_sql = "SELECT [node],risk_measure, [value]/n.NAV as value " +\
                "FROM [risk].[measure] v INNER JOIN middle.NAV n ON v.date_reference = n.date_reference and v.trading_desk = n.trading_desk "+\
                "WHERE v.trading_desk = '{}' and parent_tree in ('Traders', 'Fund') and v.date_reference='{:%Y-%m-%d}' ".format(str_fund, dt) 
                
    df = pd.read_sql(str_sql, connection)
    df = df.pivot(index='node', columns='risk_measure', values='value')
    df['VaR'] *= -10_000
    df.drop('Shared', inplace=True)
    connection.close()
    del str_sql
    #%%
    dfRiskShare = fu.get_DailyRiskShare(dt, str_fund).loc[dt].sort_values(ascending=False)    
    cols = [i for i in dfRiskShare[dfRiskShare>0].index if i not in ['Fund']] + ['Fund']
    
    trader_limit = fu.get_RiskLimits(dt, str_fund)
    for c in cols:
        var_limit, stress_limit, _ = trader_limit[c]
        df.loc[c, 'Var_limit'] = var_limit
        df.loc[c, 'Stress_Limit'] = stress_limit if c != 'Fund' else -0.15

    df = df.reindex(cols).fillna(0)
    #%%
    color1, color2 = fu.color_palette[0], fu.color_palette[1]
    
    fig, (axV, axS) = plt.subplots(nrows=1, ncols=2, figsize=(12, 3.6))
    plt.tight_layout()
    
    df['VaR'].plot.bar(ax=axV, legend=False, zorder=2, color=color2, alpha=0.8)
    df['Var_limit'].plot.bar(ax=axV, legend=False, zorder=2, color='None', \
                             edgecolor='r', linewidth=2, label='limit')
    for i, book in enumerate(df.index):
        y = float(df['VaR'].loc[book])
        axV.text(i, y, '{:2.1f} '.format(y) if y!=0 else '-', va='bottom', color=color2, ha='center', \
                      fontweight='heavy' if book=='Fund' else 'bold', \
                      fontsize=13 if book=='Fund' else 11)
        limit=float(df['Var_limit'].loc[book])
        axV.text(i+0.5, y, '{:2.0%}'.format(y/limit) if limit!=0 else 'Stop' if y!=0 else '', va='bottom', ha='center',\
                     color='k' if limit==0 else 'grey' if y/limit<0.8 else 'k', 
                     backgroundcolor='tomato' if limit==0 else 'None' if y/limit<0.8 else 'gold' if y/limit<1 else 'lightcoral')
            
    axV.axhline(0, lw=1, c='k',zorder=4)
    # axV.set_ylim(bottom=0, top=210)
    axV.set_xlim(right=i+.6)
    axV.set_xlabel('')
    axV.set_ylabel('BPs', fontsize=12)
    axV.tick_params(labelsize=12)           
    axV.grid(axis='y', ls='--',zorder=1)
    axV.legend(loc=2, ncol=2, fontsize=12)
    axV.yaxis.set_major_locator(ticker.MultipleLocator(30))
    ticks_loc = axV.get_yticks().tolist()
    axV.yaxis.set_major_locator(ticker.FixedLocator(ticks_loc))
    axV.set_yticklabels(["{:2.0f}".format(i) for i in ticks_loc])
    axV.get_xticklabels()[-1].set_weight("bold")        
               
    
    
    df['Stress'].plot.bar(ax=axS, legend=False, zorder=2, color=color2, width=0.5, alpha=0.8)
    df['Stress_Limit'].plot.bar(ax=axS, legend=False, zorder=2, color='None', \
                              edgecolor='tomato', linewidth=2, label='warning')
    
    for i, book in enumerate(df.index):
        y = float(df['Stress'].loc[book])
        va, c = ('top', 'r') if y<=0 else ('bottom', 'k')
        axS.text(i, y, '{:2.1f}  '.format(100*y)  if y!=0 else '-', va=va, color=c, ha='center', \
                      fontweight='heavy' if book=='Fund' else 'bold', \
                      fontsize=13 if book=='Fund' else 11)
        limit=float(df['Stress_Limit'].loc[book])
        axS.text(i+0.5, y, '{:2.0%}'.format(abs(y/limit)) if limit!=0 else '-' if y!=0 else '', va='top', ha='center', \
                     color='k' if limit==0 else 'grey' if y/limit<0.8 else 'k',
                     backgroundcolor='tomato' if limit==0 else 'None' if y/limit<0.8 else 'gold' if y/limit<1 else 'lightcoral')
            
    axS.axhline(0, lw=1.5, c='k',zorder=4)
    axS.set_ylim(bottom=-0.26, top=0)
    axS.set_xlim(right=i+.6)
    axS.yaxis.tick_right()
    axS.yaxis.set_major_locator(ticker.MultipleLocator(0.05))
    axS.axhline(-0.25, c='r', lw=1.5, ls='--', label='Policy Limit (-25%)')
    # axS.set_yticks([0, -0.03, -0.06, -0.09, -0.12, -0.15, -0.18])
    axS.set_xlabel('')
    axS.set_ylabel('% NAV', fontsize=12)
    # axS.yaxis.set_label_position("right")
    axS.tick_params(labelsize=12)           
    axS.grid(axis='y', ls='--',zorder=1)
    axS.legend(ncol=1, fontsize=12, loc=8)
    ticks_loc = axS.get_yticks().tolist()
    axS.yaxis.set_major_locator(ticker.FixedLocator(ticks_loc))
    axS.set_yticklabels(["{:2.0%}".format(i) for i in ticks_loc], color='r')
    axS.get_xticklabels()[-1].set_weight("bold") 
    
    if print_pdf:
         fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_{1}_trader_var_stress.pdf'.format(dt, str_fund)
         fig.savefig(fig_file, bbox_inches = "tight")

    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_trader_var_stress.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    
    wb = xw.Book(report_filename)
    wb.sheets('Trader').pictures.add(wb.api.Path + '/' + fig_file, name='trader_var_stress', update=True)
 

#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt, str_fund = fu.get_config(['dt', 'str_fund'])
    report_filename = '../xls/RiskMap_model.xlsm'
    main(dt, str_fund, report_filename, (dt.weekday()==4)) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))
    