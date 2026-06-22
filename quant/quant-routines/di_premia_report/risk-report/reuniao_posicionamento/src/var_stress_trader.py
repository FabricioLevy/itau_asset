import pandas as pd
import datetime
import timeit
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

import os
import sys
str_onedrive = '\\OneDrive' if os.path.exists(os.path.expanduser('~\\OneDrive')) else ''
path_util = os.path.expanduser('~{}\\Documents\\Github\\risk_report\\src'.format(str_onedrive))
sys.path.insert(1, path_util)
import fund_utils as fu

#%%
def main(dt, str_fund, report_filename):
    #%%
    _, connection = fu.get_DB_conn('prod')
    
    str_sql = "SELECT [node],risk_measure, [value]/n.NAV as value " +\
                "FROM [risk].[measure] v INNER JOIN middle.NAV n ON v.date_reference = n.date_reference and v.trading_desk = n.trading_desk "+\
                "WHERE v.trading_desk = '{}' and parent_tree in ('Traders', 'Fund') and v.date_reference='{:%Y-%m-%d}' ".format(str_fund, dt) 
                
    df = pd.read_sql(str_sql, connection)
    df = df.pivot(index='node', columns='risk_measure', values='value')
    df['VaR'] *= -10000
    df.drop('Shared', inplace=True)
    connection.close()
    del str_sql
    #%%
    dic_riskshare = fu.get_DailyRiskShare(dt, str_fund).loc[dt].to_dict()
    cols = ['MS','BC', 'GB', 'PA', 'FK', 'TO', 'Fund']
    trader_limit = fu.get_RiskLimits(dt, str_fund)
    for c in cols:
        var_limit, stress_limit, _ = [i/dic_riskshare[c] for i in trader_limit[c]]
        df.loc[c, 'VaR'] /= dic_riskshare[c]
        df.loc[c, 'Stress'] /= dic_riskshare[c]
    df.loc['Fund', 'Var_limit'] = 180
    df.loc['Fund', 'Stress_Limit'] =  -0.15

    df = df.reindex(cols)
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
                      fontsize=13 if book=='Fund' else 12)
        # limit=float(df['Var_limit'].loc[book])
        # axV.text(i+0.425, y, '{:2.0%}'.format(y/limit) if limit!=0 else 'Stop', va='bottom', ha='center',\
        #              color='k' if limit==0 else 'grey' if y/limit<0.8 else 'k', 
        #              backgroundcolor='tomato' if limit==0 else 'None' if y/limit<0.8 else 'gold' if y/limit<1 else 'lightcoral')
            
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
                      fontsize=13 if book=='Fund' else 12)
        # limit=float(df['Stress_Limit'].loc[book])
        # axS.text(i+0.470, y, '{:2.0%}'.format(abs(y/limit)), va='top', ha='center', \
        #               color='grey' if y/limit<0.8 else 'k', 
        #               backgroundcolor='None' if y/limit<0.8 else 'gold' if y/limit<1 else 'lightcoral')

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
    

    fig_file = '../output/{:%Y%m%d}_{}_trader_var_stress.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    
    # wb = xw.Book(report_filename)
    # wb.sheets('Trader').pictures.add(wb.api.Path + '/' + fig_file, name='trader_var_stress', update=True)
 

#%%
#%%
if __name__ == "__main__":
    tic = timeit.default_timer()
    
    dt = datetime.date(2021, 4, 27)
    str_fund = 'A1 Master FIM'
    report_filename = '../xls/RiskMap_model.xlsm'
    main(dt, str_fund, report_filename) 
    
    tac = timeit.default_timer()
    print("Execution time: {:3.1f}s".format(tac - tic))
    