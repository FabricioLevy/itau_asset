import pandas as pd
import numpy as np
import datetime
import scipy.stats as ss
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
import matplotlib.gridspec as gridspec
from matplotlib.ticker import MaxNLocator 
import xlwings as xw
import fund_utils as fu
import var_pnl_breakdown


#%%
def main(dt, str_fund, report_filename, print_pdf=False):
#%%    
    _, connection = fu.get_DB_conn('prod')
            
    str_sql = "SELECT v.[date_reference],[value]/n.NAV*10000 as Var_bps, n.share "+\
              " FROM [risk].[measure] v INNER JOIN middle.NAV n "+\
                  "ON v.date_reference = n.date_reference AND n.trading_desk = v.trading_desk "+\
              " WHERE v.node = 'Fund' and v.parent_tree = 'Fund' and v.risk_measure='VaR' " +\
                  "and v.[date_reference]<='{:%Y-%m-%d}' and v.[trading_desk]='{}'".format(dt, str_fund)
              
    df = pd.read_sql(str_sql, connection, index_col='date_reference')
    df.sort_index(inplace=True)
    
    connection.close()
    #%%
    df['Pnl_bps'] = df['share'].pct_change().fillna(0) * 10000
    df['Var_bps_D1'] = df['Var_bps'].shift(1)
        
    df['outlier'] = np.nan
    df['outlier'][df['Pnl_bps'] < df['Var_bps_D1']] =  df['Pnl_bps']
    
    if (df['outlier'].notna().iloc[-1]) & (str_fund == 'A1 Master FIM'):
        var_pnl_breakdown.main(dt,report_filename)
        
    n, o = df[['Var_bps_D1','outlier']].count().values
    #%%
    # https://www.value-at-risk.net/backtesting-independence-tests/
    # 14.5.1 Christoffersen’s 1998 Exceedance Independence Test

    for c in ['a00', 'a01', 'a10', 'a11']:
        df[c]  = 0
    v = df[['outlier']].values.flatten()
    for i, dt_i in enumerate(df.index[1:], start=1):
        df.loc[dt_i,'a00'] = 1 if np.isnan(v[i-1]) & np.isnan(v[i]) else 0
        df.loc[dt_i,'a01'] = 1 if np.isnan(v[i-1]) & ~np.isnan(v[i]) else 0
        df.loc[dt_i,'a10'] = 1 if ~np.isnan(v[i-1]) & np.isnan(v[i]) else 0
        df.loc[dt_i,'a11'] = 1 if ~np.isnan(v[i-1]) & ~np.isnan(v[i]) else 0
    df.loc[df.index[0],'a00'] = 1
    
    # https://www.financialriskforecasting.com/code/PythonJulia8.html
    V_00 = df['a00'].sum()
    V_01 = df['a01'].sum()
    V_10 = df['a10'].sum()
    V_11 = df['a11'].sum()
    p_00=V_00/(V_00+V_01)
    p_01=V_01/(V_00+V_01)  # = 1 - p_00
    p_10=V_10/(V_10+V_11)
    p_11=V_11/(V_10+V_11)  # = 1 - p_10
    hat_p = (V_01+V_11)/(V_00+V_01+V_10+V_11)
    al = np.log(1-hat_p)*(V_00+V_10) + np.log(hat_p)*(V_01+V_11)
    bl = np.log(p_00)*V_00 + np.log(p_01)*V_01 + (0 if ((V_11==0)|(V_10==0)) else np.log(p_10)*V_10 + np.log(p_11)*V_11)
    LRatioCCI = -2*(al-bl)
    # PValueCCI = round(1 - ss.chi2.cdf(LRatioCCI, 1),3)
    
    
    #%%
    color1, color2 = fu.color_palette[0], fu.color_palette[1]
        
    locator = mdates.AutoDateLocator(minticks=3, maxticks=7)
    formatter = mdates.ConciseDateFormatter(locator, formats=['%b\n%Y', '%b', '%d', '%H:%M', '%H:%M', '%S.%f'], show_offset=False)
    
    fig = plt.figure(figsize=(10, 7), tight_layout=True)
    gs = gridspec.GridSpec(2, 3, height_ratios=[3,2], width_ratios=[4,3,2])
    
    ax = fig.add_subplot(gs[0, :])
    axh= fig.add_subplot(gs[1, 0])
    axk= fig.add_subplot(gs[1, 1])
    axc= fig.add_subplot(gs[1, 2])
      
    for axi in [ax, axh, axk, axc]:
            axi.tick_params(labelsize=11)
    
    # Main Chart (VaR x PnL)
    ax.plot(df['Var_bps_D1'], ls='-', c=color1, label='VaR D-1')
    ax.plot(df['Pnl_bps'], ls='', marker='.', label='PnL D0', color=color2)
    ax.plot(df['outlier'], ls='', c='r', marker='o', alpha=0.5, label='Outlier')
    ax.grid(ls='--', which='both')
    ax.legend(loc=9)
    ax.set_title('{} - VaR Backtesting'.format(str_fund), fontsize=14)
    ax.axhline(0, c='k', lw=1)
    ax.set_xlim(left=df.index[0], right=df.index[-1])
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    if len(df) < 126:
        ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonthday=15))
    else:
        ax.xaxis.set_minor_locator(mdates.MonthLocator(interval=1))
    ax.tick_params(which='both', length=5, width=1.5)
    ticks_loc = ax.get_yticks().tolist()
    ax.yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
    ax.set_yticklabels(['{:2.0f}'.format(i) for i in ticks_loc])
    
    # Histogram
    _,bins,_ = axh.hist(df['Pnl_bps'], bins=12, zorder=3, alpha=0.7, color=color2, label='Daily PnL (n={:1.0f})'.format(n))
    axh.hist(df['outlier'][~df['outlier'].isna()],bins=bins, zorder=4, alpha=0.5, color='r', label='Outliers')
    axh.grid(ls='--')
    axh.axvline(0, ls='--', color='k')
    axh.legend()
    axh.set_title('PnL - Histogram', fontsize=14)
    ticks_loc = axh.get_xticks().tolist()
    axh.yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
    axh.set_yticklabels(['{:2.0f}'.format(i) for i in ticks_loc])
    
    out_values = df.dropna().sort_index(ascending=False)[['Var_bps_D1','Pnl_bps']]
    out_values.to_csv('../output/temp_figs/{:%Y%m%d}_{}_outliers.csv'.format(dt, str_fund))
    
    # Kupiec
    p=0.05  #outlier probability
    q=0.975 #confidence interval     
    [l, u] = ss.binom.isf(q, n, p), ss.binom.isf(1-q, n, p)
    x = np.arange(ss.binom.ppf(0.0001, n, p),
                   ss.binom.ppf(0.9999, n, p)+1)
    
    blue_x = [i for i in x if i >=l and i <=u]
    red_x = [i for i in x if i <l or i >u]
    
    axk.vlines(red_x, 0, ss.binom.pmf(red_x, n, p), colors='r', lw=6, alpha=0.5, label='rejection interval')
    axk.vlines(blue_x, 0, ss.binom.pmf(blue_x, n, p), colors=color2, lw=6, alpha=0.5, label='non-rejection [{:1.0f};{:1.0f}]'.format(blue_x[0], blue_x[-1]))
    
    axk.vlines(o, 0, ss.binom.pmf(o, n, p), colors=color1, ls='--', lw=3, label='#Outliers = {:1.0f} / {:1.0f}'.format(o,n))
    axk.set_title("Kupiec's test", fontsize=14)
    axk.set_ylim(bottom=0)
    axk.xaxis.set_major_locator(MaxNLocator(integer=True))
    axk.set_ylabel('Frequency')
    axk.set_xlabel('Number of Exceptions')
    axk.grid(ls='--')
    axk.set_yticks([])
    axk.legend()
    
    # Christoffersen
    axc.set_title("Christoffersen’s", fontsize=13)
    axc.set_ylim(bottom=0)
    axc.set_xlim(left=0, right=5)
    x = np.arange(0, 6, .01)
    axc.plot(x, ss.chi2.pdf(x, 1), color=color1, lw=2)
    ic = 0.95
    xi = ss.chi2.ppf(ic, 1)
    axc.axvline(xi, lw=1.5, ls='--', c='tomato',label='Acceptance')
    xi_notReject = [i for i in x if i<=xi]
    axc.fill_between(xi_notReject, ss.chi2.pdf(xi_notReject, 1), color=color2, alpha=0.5)
    axc.axvline(LRatioCCI, lw=2, ls='--', color=color1, label='L Ratio CCI')
    axc.legend()
    axc.grid(ls='--')
    axc.set_xlabel(r'Prob. Density Function ($\chi^2_1$)')
    
    fig_file = '../output/temp_figs/{:%Y%m%d}_{}_backtest.svg'.format(dt, str_fund)
    fig.savefig(fig_file, bbox_inches = "tight")
    if print_pdf:
        fig_file = '../output/temp_figs/{:%Y%m%d}_{}_backtest.pdf'.format(dt, str_fund)
        fig.savefig(fig_file, bbox_inches = "tight")
    plt.show()
    
    wb = xw.Book(report_filename)
    wb.sheets('DD_BT').pictures.add(wb.api.Path + '/' + fig_file, name='backtest', update=True)

#%%
if __name__ == "__main__":
    
    dt, str_fund = fu.get_config(['dt', 'str_fund'])
    report_filename = '../xls/RiskMap_model.xlsm'
    
    main(dt, str_fund, report_filename, False) 
    
 