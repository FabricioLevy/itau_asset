import pandas as pd
import numpy as np
import datetime
import matplotlib.pyplot as plt
from scipy.stats import genpareto, norm, probplot
import scipy.optimize
import xlwings as xw
from adjustText import adjust_text
import sqlalchemy as sa

#====== UPDATE HERE =========
now = datetime.date(2021, 10, 27)
AuM = 840072603.41
fund = "MACRO"
#============================

#%%
def invFunc(y, f):
    func = lambda x: abs(f(x) - y)*10000
    fPrime = scipy.optimize.fmin(func=func, x0=0.5, disp=False)
    return fPrime[0]

#%%
def main(now, fund, AuM):
#%%
    colors = ["#312C62", "#00D528", "#5BC3F0", "#FF584C"]
    today_file = now.strftime("%Y%m%d")
    str_path = 'V:/04_DEV/Riskmetrics/RiskManagerOutput/' + today_file
    wb = xw.Book(r'V:\04_DEV\Riskmetrics\Results\reportMacro.xlsm')
    wb.sheets('EVT').select()
    str_filename = 'HistoricalPnLByUniqueID_FromJan2006.xlsx'
    str_sheetname = 'Simulated Returns RowSpec Sim'
    dfRet = pd.read_excel(str_path +"/"+ fund +"/"+ str_filename, sheet_name=str_sheetname, \
                          skiprows=17, index_col = [0], usecols=range(2, 4), parse_dates=[0])
    dfRet /= AuM

#%%
    std = dfRet.Total.ewm(alpha=0.06).vol().iloc[-1] 
    print("\nVaR (BPs) = {:3.1f}".format(10000 * norm.ppf(0.95, loc=0, scale=std)))

    fig, (ax1, ax3) = plt.subplots(1, 2, figsize=(10, 5), sharex=False, sharey=False)
#    plt.tight_layout()
    ax1.hist(dfRet.Total , bins=35, density=True, alpha=1, color="#5BC3F0")
    x = np.linspace(norm.ppf(0.0001, loc=0, scale=std), norm.ppf(0.9999, loc=0, scale=std), 100)
    ax1.plot(x, norm.pdf(x, loc=0, scale=std), 'r-', lw=2,  label='normal pdf')
    ax1.grid()
    (xmin, xmax) = ax1.get_xlim()
    xlim = max(-xmin, xmax)
    ax1.set_xlim(xmin=-xlim, xmax=xlim)
    ax1.set_xticklabels(['{:2.1%}'.format(x) for x in ax1.get_xticks()])
    ax1.set_title('Histogram')
    
    probplot(dfRet.Total, dist="norm", plot=ax3)
    ax3.get_lines()[0].set_markerfacecolor("#5BC3F0")
    ax3.get_lines()[0].set_markeredgecolor("#5BC3F0")
    ax3.set_title('PP - Plot')
    ax3.set_yticklabels(['{:2.0%}'.format(x) for x in ax3.get_yticks()])
    ax3.grid()   
    wb.sheets('EVT').pictures.add(fig, name='Normal_DataFit', update=True)
    plt.show()

#%%
    threshold_pct = 95
    
    dfRet['Losses'] = abs(dfRet.Total[dfRet.Total <= 0])
    u = np.percentile(dfRet['Losses'].fillna(0), threshold_pct)
    dfRet['Exceedances'] = dfRet['Losses'][dfRet['Losses'] > u]    
    
    fig = plt.figure(figsize=(10, 4))
    ax1 = plt.subplot2grid((2, 2), (0, 0), rowspan=2)
    ax2 = plt.subplot2grid((2, 2), (0, 1))
    ax3 = plt.subplot2grid((2, 2), (1, 1))
    plt.tight_layout()
    
    dfRet['Losses'].plot(ax=ax1, kind='area', grid=True, color=colors[0], alpha=0.6)
    ax1.axhline(u, c='k', lw=1.5, label='Threshold (u={:3.2%})'.format(u))
    ax1.set_xlim(xmin=dfRet.index[0], xmax=dfRet.index[-1])
    ax1.set_ylim(ymin=0)
    ax1.set_yticklabels(['{:2.1%}'.format(x) for x in ax1.get_yticks()])
    ax1.xaxis.label.set_visible(False)
    ax1.legend()
    
    _, bins, _ = ax2.hist(dfRet['Losses'][dfRet['Losses']>0].values , bins=30, alpha=0.8, color=colors[0])
    ax2.hist(dfRet['Exceedances'].dropna().values, bins=bins, color=colors[2], label='Exceedances')
    
    ax2.axvline(u, c='k', lw=1.5, label='Threshold (u={:3.2%})'.format(u))
    ax2.set_xlim(xmin=0)
    ax2.set_xticklabels(['{:2.1%}'.format(x) for x in ax2.get_xticks()])
    ax2.grid()
    ax2.legend()

    e_u = []
    list_u = []
    for l in dfRet['Losses'].fillna(0).unique():
        list_u.append(l)
        e_u.append(np.mean(dfRet['Losses'][dfRet['Losses'] >= l]))
    
    ax3.plot(list_u, e_u, ls='', marker='.', color=colors[0], alpha=0.4)
    ax3.axvline(u, c='k', lw=1.5, label='Threshold (u={:3.2%})'.format(u))
    ax3.set_xlim(ax2.get_xlim())
    ax3.set_xlim(xmin=0)
    ax3.set_ylim(ymin=0)
    ax3.set_ylabel('Mean Excess')
    ax3.set_xticklabels(['{:2.1%}'.format(x) for x in ax3.get_xticks()])
    ax3.set_yticklabels(['{:2.0%}'.format(x) for x in ax3.get_yticks()])
    ax3.grid()
    ax3.legend()
    wb.sheets('EVT').pictures.add(fig, name='EVT_Data', update=True)
    plt.show()

#%%    
    (c, loc, scale) = genpareto.fit(dfRet['Exceedances'].dropna().values, loc=u)
    gp = genpareto(c, loc, scale)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4), sharex=False)
    ax1.hist(dfRet['Exceedances'].dropna(), bins=bins, density=True, histtype='stepfilled', alpha=1, color=colors[2])
    x = np.linspace(gp.ppf(q=0.01), gp.ppf(q=0.99), 100)
    ax1.plot(x, gp.pdf(x), 'r-', lw=2,  label='Gen.Pareto pdf')
    ax1.set_title('Histogram / PDF')
    ax1.set_xlabel('Loss')
    ax1.set_ylabel('Frequency')
    ax1.legend()
    ax1.grid()
    ax1.set_xlim(xmin=0)
    ax1.set_xticklabels(['{:3.1%}'.format(x) for x in ax1.get_xticks()])
    
    Fu = dfRet.Exceedances.count()/dfRet.Total.count()
    F = lambda x:Fu*(1-gp.cdf(x))
#    listProb = [1/21, 1/63, 1/126, 1/252, 1/504, 1/1260, 1/2520, 1/5040]
#    labelProb = ['1M', '3M', '6M', '1Y', '2Y', '5Y', '10Y', '20Y']
    listProb = [1/126, 1/252, 1/504, 1/1260, 1/2520, 1/5040]
    labelProb = ['6M', '1Y', '2Y', '5Y', '10Y', '20Y']
    ret=[]
    for q in listProb:
        ret.append(invFunc(q, F) + u)    
    probplot(dfRet['Exceedances'].dropna().values, dist=gp, plot=ax2, fit=False)
    ax2.get_lines()[0].set_markerfacecolor("#5BC3F0")
    ax2.get_lines()[0].set_markeredgecolor("#5BC3F0")
    ax2.set_yticklabels(['{:2.1%}'.format(x) for x in ax2.get_yticks()])
    ax2.grid()
    
    wb.sheets('EVT').pictures.add(fig, name='EVT_DataFit', update=True)
    plt.show()
    
#%%    
    fig, ax = plt.subplots(1, 1, figsize=(10, 4), sharex=False)
    ax.semilogy(ret, listProb, marker='o', color=colors[0], zorder=10)
    ax.set_xlim(xmin=u)
    ax.set_ylim(ymin=0.009/100)
    ax.set_xlabel('Loss')
    ax.set_ylabel('Log-Probability')
    texts = []
    for i, q in enumerate(listProb):
        texts.append(ax.text(ret[i], q, \
                     ' {:3.2%}, '. format(ret[i]) + labelProb[i], size=12,\
                    bbox=None if i!=4 else {'facecolor':'none', 'alpha':0.9, \
                                            'boxstyle': 'round', 'pad':1,\
                                            'edgecolor':'red', 'linewidth':3}))
    ax.set_xticklabels(['{:1.0%}'.format(x) for x in ax.get_xticks()])
    ax.set_yticklabels(['{:3.2%}'.format(x) for x in ax.get_yticks()])
    ax.grid()
    ax.legend(['Loss, Frequency'])
    adjust_text(texts)
    wb.sheets('EVT').pictures.add(fig, name='EVT_VaR', update=True)
    plt.show()
    
#%% 
    engine = sa.create_engine('mssql+pyodbc://vin_risk:@vuQawsed84@vinland.database.windows.net,1433/VinlandDB?driver=SQL+Server+Native+Client+11.0')
    connection = engine.connect()
    for i, lbl in enumerate(labelProb):
        connection.execute("DELETE FROM risk.RiskType WHERE RiskType = 'EVT VaR "+ lbl + "' and "+ \
                           " DataRef = '"+ now.strftime("%Y-%m-%d") +"' and Fund='Vinland "+ fund +"'")
        connection.execute("INSERT INTO risk.RiskType ([DataRef],[Fund],[RiskType],[value]) "+\
                           " VALUES ('"+ now.strftime("%Y-%m-%d") +"', 'Vinland "+ fund +"', "\
                           " 'EVT VaR "+ lbl + "', " + str(ret[i]*AuM) + ")")
        
    connection.close()

#%%
if __name__ == "__main__":
    main(now, fund, AuM)  