import pandas as pd 
import datetime
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import adjustText
import fund_utils as fu
import os


def main (dt, str_fund = 'A1 Master FIM', print_pdf=False):
    if str_fund != 'A1 Master FIM':
        return False
    
    report_filename = '../xls/mock_trade_ideas.xlsx'
    
    _, dtSInit = pd.to_datetime((fu.get_PeriodToDate(dt)))
    
    dfTrades = pd.read_excel(report_filename, 
                             sheet_name='Trade_Ideas',
                             parse_dates=[0, 1],
                             index_col=3)
    
    dfTrades = dfTrades[(dfTrades['date_end'] > dtSInit) | (dfTrades['date_end'].isna())]
    
    dfPnL = pd.DataFrame(columns = dfTrades.index)
    
    dic_trades = {}
    products = []
    for sheet in dfTrades.index:
        df = pd.read_excel(report_filename, 
                           sheet_name=sheet,
                           parse_dates=[0])
        products += list(df['product_id'])
        dic_trades[sheet] = df
        
    str_products = "'" + "','".join(set(products)) + "'" 
    
    _, connection = fu.get_DB_conn()
      
    str_sql = f"""
            SELECT [date_reference],[value] as 'USD'
                FROM [quant].[time_series_value]
                WHERE series_id = 847
                    and date_reference between '2022-6-1' and '{dt:%Y-%m-%d}'
            """
    dfFX = pd.read_sql(str_sql, 
                       connection, 
                       index_col='date_reference')
    dfFX['BRL'] = 1
    
    str_sql = f"""
            SELECT [date_reference],[product_id],[rate],[price]
            FROM [middle].[product_price]
            WHERE product_id in ({str_products})
              and date_reference between '2022-6-1' and '{dt:%Y-%m-%d}'
            """
    dfPrice = pd.read_sql(str_sql, 
                          connection).pivot(index='date_reference',
                                            columns='product_id',
                                            values='price').fillna(method='ffill')
    
    str_sql = f"""
            SELECT id, product_currency, date_maturity, lot_size
            FROM [middle].[product]
            WHERE  id in ({str_products}) 
            """
    dfProduct = pd.read_sql(str_sql,
                            connection,
                            index_col='id')
    
    #%%
    for trade, df in dic_trades.items():
        dfpnl_temp = pd.DataFrame(columns=df.index)
        for deal_id, (dt_ref, prod_id, amount, price_ini) in df.iterrows():
            price_ant = 0
            ccy = dfProduct.loc[prod_id,'product_currency']
            for dt_i, price in dfPrice[prod_id].iteritems():
                if dt_i == dt_ref.date():
                    dfpnl_temp.loc[dt_i, deal_id] = (price - price_ini) * amount * dfProduct.loc[prod_id,'lot_size'] * dfFX.loc[dt_i, ccy]
                elif dt_i > dt_ref.date():
                    dfpnl_temp.loc[dt_i, deal_id] = (price - price_ant) * amount * dfProduct.loc[prod_id,'lot_size'] * dfFX.loc[dt_i, ccy]
                price_ant = price
    
        dfPnL[trade] = dfpnl_temp.sum(axis=1).cumsum()
    
    #%%
    dic_trades = {}
    for t in dfTrades['trader'].unique():
        dic_trades[t] = dfTrades[dfTrades['trader']==t][['date_start', 'date_end', 
                                                         'pnl_stop', 'pnl_target']]
        dic_trades[t] = dic_trades[t].join(dfPnL.iloc[-1])
        dic_trades[t].columns = ['Date Ini', 'Date End', 'PnL Stop', 'PnL Target', f"PnL on {dt:%d%b%Y}"]
      
      
    #%%
    color1, color2 = fu.color_palette[0:2]
    
    dic_trades_close = {}
    dic_trades_open = {}
    
    for key in dic_trades.keys():
        for dic,df_ in zip([dic_trades_open,dic_trades_close],
                           [dic_trades[key][dic_trades[key]['Date End'].isna()],
                            dic_trades[key][dic_trades[key]['Date End'].notna()]]):
            if not df_.empty:
                dic[key] = df_
    
    names = ['fechado', 'aberto']
    for dic, name in zip([dic_trades_close,dic_trades_open], names):
        if dic:
            fig, axes = plt.subplots(len(dic_trades),
                                     1,
                                     figsize=(9, 1.6 * len(dfTrades)),
                                     squeeze=False,
                                     gridspec_kw = {'height_ratios':[len(d)+1 for _, d in dic_trades.items()]})
            # hide axes
            fig.patch.set_visible(False)
            
            fig.suptitle(f"Não realizado {name}", fontsize = 18, fontweight = 'bold', ha = 'left')
            for ax, t in zip(axes.flatten(), dic.keys()):
                ax.set_title(t, color=color1, fontsize=16, fontweight='bold')
                ax.axis('off')
                # ax.axis('tight')
                df = dic[t].copy()
                df.update(df[['PnL Stop', 'PnL Target', f"PnL on {dt:%d%b%Y}"]].applymap('{:,.0f}'.format))
                df.update(df[['Date Ini', 'Date End']].applymap(lambda x: '' if x is pd.NaT else '{:%d-%b-%y}'.format(x)))
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
            
            fig_file = '../output/temp_figs/{:%Y%m%d}_mock_trade_idea_table_{}.svg'.format(dt,name)
            fig.savefig(fig_file, bbox_inches = "tight")
            
            if print_pdf:
                 fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_mock_trade_idea_table_{1}.pdf'.format(dt, name)
                 fig.savefig(fig_file, bbox_inches = "tight")
            
      
    #%%
    num_subplots={1: (1, 1), 2: (2, 1), 3: (2, 2),
                  4: (2, 2), 5: (2, 3), 6: (2, 3),
                  7: (2, 4), 8: (2, 4), 9: (3, 3),
                  10:(3, 4),11: (3, 4),12: (3, 4)}
    
    if len(dfTrades) == 0:
        print('Sem trade ideas!')
        return False
        
    else:
        n_col, n_row = num_subplots[len(dfTrades)]
    
    fig, axes = plt.subplots(n_row, 
                              n_col, 
                              squeeze=False, 
                              figsize=(9.5, min(3*n_row, 13.5)))
    
    fig.tight_layout(w_pad=3, h_pad=2.5)
    
    for ((c, t), ax) in zip(dfTrades['trader'].iteritems(), axes.flatten()):
    
        (dt_ini, dt_end, pnl_stop, pnl_target, curr_pnl) = dic_trades[t].loc[c].values
    
        dfPlot = dfPnL.loc[dt_ini:, c]
        
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
        if dt_end is not pd.NaT:
            if dt_end.date() <= dt:
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
        if i>=len(dfTrades):
            ax.axis('off')
    
    
    if print_pdf:
        fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_mock_trade_idea_plot.pdf'.format(dt)
        fig.savefig(fig_file, bbox_inches = "tight")
    
    plt.show()

#%%
if __name__ == "__main__":
        
    dt = fu.get_config('dt')
    main(dt) 
    
    
    


