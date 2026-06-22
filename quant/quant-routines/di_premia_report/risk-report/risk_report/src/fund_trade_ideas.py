import pandas as pd 
import datetime
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import adjustText
import xlwings as xw
import fund_utils as fu
import win32com.client as win32
import os


def main(dt, str_fund, report_filename, print_pdf=False):
    
    if str_fund != 'A1 Master FIM':
        return False

#%%    
    _, connection = fu.get_DB_conn()
    
    _, dtSInit = fu.get_PeriodToDate(dt)
    str_sql = f"""
            SELECT *
            FROM [risk].[trade_idea]
            WHERE date_start <='{dt:%Y-%m-%d}'
                AND ((date_end > '{dtSInit:%Y-%m-%d}') OR (date_end IS NULL))
            order by isnull([date_end],GETDATE()) desc, trader, date_start asc
            """
    dfTrade = pd.read_sql(str_sql.format(dt), connection)
    books = set(dfTrade[['book', 'book_off']].values.flatten())
    books.remove(None)
    
    str_sql = f""" 
               SELECT b.[date_reference], b.book, sum([value]/n.NAV_D1) as PnL_Perc, sum([value]) as PnL_BRL
               FROM [lote45].[book_overview] b  
               		INNER JOIN middle.NAV n ON n.date_reference = b.date_reference and n.trading_desk = b.trading_desk
               WHERE [measure] = 'PL'  
                   and b.date_reference <='{dt:%Y-%m-%d}' 
                    -- and b.[trading_desk] = '{str_fund}'
                   and book in ('{"','".join(books)}')
            GROUP BY b.[date_reference], b.book
            """
    df = pd.read_sql(str_sql, connection)
    del books
    #%%
    dfDailyPnL_perc = df.pivot(index='date_reference', columns='book', values='PnL_Perc').fillna(0)
    dfDailyPnL_brl = df.pivot(index='date_reference', columns='book', values='PnL_BRL').fillna(0)
    
    dic_books = {b:[b] for b in dfTrade['book']}
    for b_on, b_off in dfTrade[~dfTrade['book_off'].isnull()][['book', 'book_off']].values:
        dic_books[b_on].append(b_off)
    
    for k, v in dic_books.items():
        dfDailyPnL_perc[k] = dfDailyPnL_perc[v].sum(axis=1)
        dfDailyPnL_brl[k] = dfDailyPnL_brl[v].sum(axis=1)
        
    dfAcumPnL_perc = (dfDailyPnL_perc[dic_books.keys()] + 1).cumprod() - 1
    dfAcumPnL_brl = dfDailyPnL_brl[dic_books.keys()].cumsum()
    del dic_books
    #%%
    dic_trades = {}
    for t in dfTrade['trader'].unique():    
        dic_trades[t] = dfTrade[dfTrade['trader']==t][['date_start', 'date_end', 'book',
                                                       'pnl_stop', 'pnl_target']].set_index('book')
        dic_trades[t] = dic_trades[t].join(dfAcumPnL_brl.iloc[-1])
        dic_trades[t].columns = ['Date Ini', 'Date End', 'PnL Stop', 'PnL Target', f"PnL on {dt:%d%b%Y}"]
    
    
    #%%
    wb = xw.Book(report_filename)
    
    color1, color2 = fu.color_palette[0:2]
    
    dic_trades_close = {}
    dic_trades_open = {}
    df = dic_trades['BC']
    df1 = df[df['Date End'].notna()]
    for key in dic_trades.keys():
        for dic,df_ in zip([dic_trades_open,dic_trades_close],
                           [dic_trades[key][dic_trades[key]['Date End'].isna()],
                            dic_trades[key][dic_trades[key]['Date End'].notna()]]):
            if not df_.empty:
                dic[key] = df_
            
    names = ['fechado', 'aberto']
    for dic, name in zip([dic_trades_close,dic_trades_open], names):
        
        if dic:
            fig, axes = plt.subplots(len(dic),
                                     1,
                                     figsize=(9, 1.7 * len(dic)),
                                     squeeze=False,
                                     gridspec_kw = {'height_ratios':[len(d)+1 for _, d in dic.items()]})
            # hide axes
            fig.patch.set_visible(False)
            
            fig.suptitle(f"Realizado {name}", fontweight = 'bold', fontsize = 18,ha = 'left')
            for ax, t in zip(axes.flatten(), dic.keys()):
                ax.set_title(t, color=color1, fontsize=16, fontweight='bold')
                ax.axis('off')
                # ax.axis('tight')
                df = dic[t].copy()
                df.update(df[['PnL Stop', 'PnL Target', f"PnL on {dt:%d%b%Y}"]].applymap('{:,.0f}'.format))
                df.update(df[['Date Ini', 'Date End']].applymap(lambda x: '' if x==None else '{:%d-%b-%y}'.format(x)))
                table = ax.table(cellText=df.values, 
                                 colColours=[color2] * len(df.columns),
                                 rowColours=['gainsboro'] * len(df),
                                 colWidths = [1/6]*4 + [1/3],
                                 cellLoc='center',
                                 colLabels=df.columns,
                                 rowLoc='center',
                                 rowLabels=df.index,
                                 loc='center',
                                 bbox=(0, 0, 1, 1))
                for (row, col), cell in table.get_celld().items():
                    if (row == 0):
                        cell.set_text_props(fontproperties=FontProperties(weight='bold'))
                    elif col in [2,3,4]:
                        v = float(cell.get_text().get_text().replace(',',''))
                        if v<0:
                            cell.get_text().set_color('r')
            
            fig.tight_layout()
            plt.show()
          
            if print_pdf:
                 fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_trade_idea_table_{1}.pdf'.format(dt, name)
                 fig.savefig(fig_file, bbox_inches = "tight")
            
            fig_file = '../output/temp_figs/{:%Y%m%d}_trade_idea_table_{}.svg'.format(dt, name)
            fig.savefig(fig_file, bbox_inches = "tight")  
            
            try:
                wb.sheets('Trade_Idea').pictures('trade_idea_table').delete()
            except KeyError:
                pass
            wb.sheets('Trade_Idea').pictures.add(wb.api.Path + '/' + fig_file, 
                                                 name='trade_idea_table', 
                                                 update=True, 
                                                 left=wb.sheets('Trade_Idea').range("O5").left)

    
    #%%
    num_subplots={1: (1, 1), 2: (2, 1), 3: (2, 2),
                  4: (2, 2), 5: (2, 3), 6: (2, 3),
                  7: (2, 4), 8: (2, 4), 9: (3, 3),
                  10:(3, 4),11: (3, 4),12: (3, 4)}
    
    if len(dfTrade) == 0:
        print('Sem trade ideas!')
        
    else:
        n_col, n_row = num_subplots[len(dfTrade)]
    
    fig, axes = plt.subplots(n_row, 
                             n_col, 
                             squeeze=False, 
                             figsize=(9.5, min(3*n_row, 13.5)))
    
    fig.tight_layout(w_pad=3, h_pad=2.5)
    
    for ((t, c), ax) in zip(dfTrade[['trader', 'book']].values, axes.flatten()):
    
        (dt_ini, dt_end, pnl_stop, pnl_target, curr_pnl) = dic_trades[t].loc[c].values
    
        dfPlot = dfAcumPnL_brl.loc[dt_ini:, c]
        
        ax.plot(dfPlot.index, dfPlot, lw=2.5, c=color2, label='PnL')
        ax.set_title(c, fontsize=13, fontweight='bold')
        
        ax.annotate(f" BRL {curr_pnl:8,.0f}",
                      xy=(dfPlot.index[-1], curr_pnl), xycoords='data',
                      xytext=(0.75, 0.65), textcoords='axes fraction',
                      size=11, va="center", ha="center", fontweight='bold',
                      bbox=dict(boxstyle="round4", fc=color2 if curr_pnl>0 else "tomato", alpha=0.5),
                      arrowprops=dict(arrowstyle="->",
                                      connectionstyle="arc3,rad=0.2",
                                      relpos=(0., 0.),
                                      fc="w")
                      )
        
        ax.axhline(0, c='k', lw=1)
        ax.axhline(pnl_stop, c='r', label='PnL Stop')
        ax.text(dt_ini, pnl_stop, f" BRL {pnl_stop:8,.0f}", va='bottom', c='r', fontweight='bold')
        ax.axhline(pnl_target, c='g', label='PnL Target')
        ax.text(dt_ini, pnl_target, f" BRL {pnl_target:8,.0f}", va='top', c='g', fontweight='bold')
        if dt_end != None:
            if dt_end<=dt:
                ax.axvline(dt_end, c='grey', lw=3, ls=":")
                txts = [ax.text(dt_end, 0, f" End: {dt_end:%d%b%y}", c='grey', fontweight='bold', va='bottom')]
                adjustText.adjust_text(txts, ax=ax)
                ax.set_facecolor('gainsboro')
        
        ax.set_xlim(left=dt_ini)
        # ax.legend()
        ax.grid(ls='--')
        # ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}')) 
        # values_list= ax.get_yticks()
        ax.yaxis.set_major_locator(plt.MaxNLocator(5))
        ax.yaxis.set_ticks(ax.get_yticks())
        ax.set_yticklabels(["{:3.1f}M".format(i/10**6) for i in ax.get_yticks()])
        locator = mdates.AutoDateLocator(minticks=3, 
                                         maxticks=6)
        formatter = mdates.ConciseDateFormatter(locator, 
                                                formats=['%b%y', '%b%y', '%d%b', '%H:%M', '%H:%M', '%S.%f'], 
                                                show_offset=False)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)   
    
    for i, ax in enumerate(axes.flatten()):
        if i>=len(dfTrade):
            ax.axis('off')
    
    plt.show()

    if print_pdf:
         fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_trade_idea_plot.pdf'.format(dt)
         fig.savefig(fig_file, bbox_inches = "tight")

    fig_file = '../output/temp_figs/{:%Y%m%d}_trade_idea_plot.svg'.format(dt)
    fig.savefig(fig_file, bbox_inches = "tight")    
    
    try:
        wb.sheets('Trade_Idea').pictures('trade_idea').delete()
    except KeyError:
        pass
    wb.sheets('Trade_Idea').pictures.add(wb.api.Path + '/' + fig_file, 
                                          name='trade_idea', 
                                          update=True, 
                                          top=wb.sheets('Trade_Idea').range("A5").top)
#%%
if __name__ == "__main__":
        
    dt, str_fund = fu.get_config(['dt', 'str_fund'])
    report_filename = '../xls/RiskMap_model.xlsm'
    main(dt, str_fund, report_filename, (dt.weekday()==4)) 
    
    
    
    