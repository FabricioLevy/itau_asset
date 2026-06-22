import pandas as pd
import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import fund_utils as fu


str_fund = 'A1 Master FIM'
dt = datetime.date(2022, 3, 30)

#%%
class trade_idea:    
    def __init__(self, date_start, date_end, book, book_off, product_id_long, product_id_short,
                 price_start, price_target, price_stop, pnl_stop, pnl_target, amount_brl, trade_idea_type):
        self.date_start = date_start
        self.date_end = date_end
        self.book = book
        self.book_off = book_off
        self.product_id_long = [] if product_id_long==None else product_id_long.split(',')
        self.product_id_short = [] if product_id_short==None else product_id_short.split(',')
        self.price_start = price_start
        self.price_target = price_target
        self.price_stop = price_stop
        self.amount_brl = amount_brl
        self.trade_idea_type = trade_idea_type
        if pnl_target == None:
            self.amount_target = (price_target/price_start-1) * amount_brl
        else:
            self.amount_target = pnl_target
        if pnl_stop == None:   
            self.amount_stop = (price_stop/price_start-1) * amount_brl
        else:
            self.amount_stop = pnl_stop
        
    def historical_price(self, dfPrice):
        if self.trade_idea_type.upper() == 'LO':
            temp = dfPrice.loc[self.date_start:, self.product_id_long].copy()
            temp.columns = ['Price']
        elif self.trade_idea_type.upper() == 'LS':
            temp = dfPrice.loc[self.date_start:,  self.product_id_long + self.product_id_short].copy()
            temp['Price'] = temp[self.product_id_long[0]]/temp[self.product_id_short[0]]
        else:
            pass
        return temp
    
    def __repr__(self):
        return "trade_idea:Long:{}/Short:{}".format(','.join(self.product_id_long), ','.join(self.product_id_short))


#%%
_, connection = fu.get_DB_conn()

str_sql = """
        SELECT [date_start],[date_end],[book],book_off,[product_id_long],[product_id_short],
      [price_start],[price_target],[price_stop],[pnl_stop],[pnl_target],[amount_brl],[trade_idea_type]
  FROM [risk].[trade_idea]
  WHERE ((date_end is null) or (date_end>='{0:%Y-%m-%d}')) and date_start<='{0:%Y-%m-%d}'
"""
dfTrade = pd.read_sql(str_sql.format(dt), connection)
books = {}
products = []
for id_t, (date_start, date_end, book, book_off, product_id_long, product_id_short, \
                 price_start, price_target, price_stop, pnl_stop, pnl_target, \
                     amount_brl, trade_idea_type) in dfTrade.iterrows():
    books[book] = trade_idea(date_start, 
                             date_end, 
                             book, 
                             book_off,
                             product_id_long, 
                             product_id_short,
                             price_start, 
                             price_target,
                             price_stop, 
                             pnl_stop, 
                             pnl_target,
                             amount_brl, 
                             trade_idea_type)
    
    products += books[book].product_id_long + books[book].product_id_short
    
products = set(products)

str_sql = """
        SELECT date_reference, product_id, price, rate
        FROM middle.product_price
        WHERE product_id in ('{}') and date_reference <='{:%Y-%m-%d}'
        """
df = pd.read_sql(str_sql.format("','".join(products), dt), connection)
dfPrice = df.pivot(index='date_reference', columns='product_id', values='price')

str_sql =   """ 
       SELECT b.[date_reference], b.book, sum([value]/n.NAV_D1) as PnL_Perc, sum([value]) as PnL_BRL
         FROM [lote45].[book_overview] b  
           		INNER JOIN middle.NAV n ON n.date_reference = b.date_reference and n.trading_desk = b.trading_desk
        WHERE [measure] = 'PL'  and b.date_reference <='{:%Y-%m-%d}' and b.[trading_desk] = '{}'
            and book in ('{}')
        GROUP BY b.[date_reference], b.book
        """
df = pd.read_sql(str_sql.format(dt, str_fund, "','".join(books.keys())) , connection)

connection.close()
del str_sql, connection

#%%
dfPnL_perc = (df.pivot(index='date_reference', columns='book', values='PnL_Perc').fillna(0)+1).cumprod()-1
dfDaily_brl = df.pivot(index='date_reference', columns='book', values='PnL_BRL') 
dfPnL_brl = dfDaily_brl.fillna(0).cumsum()

#%%
num_subplots={1: (1, 1),
              2: (2, 1),
              3: (2, 2),
              4: (2, 2),
              5: (3, 2),
              6: (3, 2),
              7: (4, 2),
              8: (4, 2),
              9: (3, 3)}

if len(books) == 0:
    print('Sem trade ideas!')
    
else:
    n_col, n_row = num_subplots[len(books)]
    
    color1, color2 = fu.color_palette[0:2]
    
    fig, axes = plt.subplots(n_row, n_col, squeeze=False, figsize=(10, 4*n_row))
    fig.tight_layout(w_pad=4)
    
    locator = mdates.AutoDateLocator(minticks=2, maxticks=6)
    formatter = mdates.ConciseDateFormatter(locator, formats=['%b\n%Y', '%b\n%Y', '%d%b', '%H:%M', '%H:%M', '%S.%f'], show_offset=False)
    
    for b, ax in zip(books, axes.flatten()):
    
        ax2 = ax.twinx()
        ax2.set_zorder(1)
        ax.set_zorder(2)
        ax.patch.set_visible(False)
        ax2.patch.set_visible(False)
        ax.grid(ls='--', axis='x', zorder=1)
        ax2.grid(ls='--', zorder=1)
        
         
        # nticks = 7
        # ax2.yaxis.set_major_locator(ticker.LinearLocator(nticks))
        # ax.yaxis.set_major_locator(ticker.LinearLocator(nticks))
        # ax2.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.02f'))
        
        
        temp_price = books[b].historical_price(dfPrice)
        l_price, = ax2.plot(dfPnL_brl[b].index, temp_price['Price'], c=color2, lw=3, ls=':', zorder=5, label='Price')
        # ax2.axhline(books[b].price_start, color=color2, lw=0.75)
        ax2.tick_params(axis="y", labelcolor=color2)
        curr_price = temp_price.iloc[-1]['Price']
        ax2.text(temp_price.index[0], books[b].price_start, f" {books[b].price_start:2.2f}", va='bottom', c=color2, fontweight='bold')
        ax2.annotate(f"Price: {curr_price:2.4g}", xytext=(0.5, 0.5), textcoords="axes fraction",
                         xy=(temp_price.index[-1], curr_price), xycoords="data", 
                         va="center", ha="center",fontweight='bold', zorder=4,
                          bbox=dict(boxstyle="round", fc='tomato' if curr_price<books[b].price_start else color2),
                          arrowprops=dict(arrowstyle="->", connectionstyle="arc3, rad=0.2", lw=1.5)) 
        
           
        pnl = dfPnL_brl[b].iloc[-1]/10**6
        l_plot, = ax.plot(dfPnL_brl[b].index, dfPnL_brl[b]/10**6, c=color1, lw=3, zorder=5, label='PnL (BRL)')
        ax.set_ylim(top=books[b].amount_target*1.01/10**6, bottom=min(books[b].amount_stop, dfPnL_brl[b].iloc[-1])*1.01/10**6)
        ax.set_title(b, fontweight='bold')
        # ax.plot(dfDaily_brl[dfDaily_brl[b]>=0][b].index, dfDaily_brl[dfDaily_brl[b]>=0][b]/10**6, ls='', c='b', marker='.', zorder=5)
        # ax.plot(dfDaily_brl[dfDaily_brl[b]<0][b].index, dfDaily_brl[dfDaily_brl[b]<0][b]/10**6, ls='', c='r', marker='.', zorder=5)
        
    
        stop = books[b].price_stop
        l_stop = ax2.axhline(stop, color='r', lw=2, ls='--', zorder=3, label='Stop')
        ax2.text(temp_price.index[0], stop, f" {stop:2.2f}", va='bottom', c='r', fontweight='bold')
        target = books[b].price_target
        l_target = ax2.axhline(target, color='g', lw=2, ls='--', zorder=3, label='Target')
        ax2.text(temp_price.index[0], target, f"\n {target:2.2f}", va='center', c='g', fontweight='bold')
        ax.axhline(0, lw=0.7, c='k')
    
        for axi in [ax, ax2]:
            axi.set_xlim(left=dfPnL_brl[b].dropna().index[0])
            axi.yaxis.set_major_formatter(ticker.ScalarFormatter( )) 
            axi.xaxis.set_major_locator(locator)
            axi.xaxis.set_major_formatter(formatter)      
            
        perc_target = max(0, (curr_price-books[b].price_start)/(target-books[b].price_start))
        perc_stop = max(0, (curr_price-stop)/(stop-books[b].price_start))
        
        ax.annotate(f"Acum PnL\nBRL {pnl:+2.2f}M", xytext=(0.65, 0.7), textcoords="axes fraction",
                         xy=(dfPnL_brl[b].index[-1], pnl), xycoords="data", 
                         va="center", ha="center",fontweight='bold', zorder=6,
                          bbox=dict(boxstyle="round", fc=color2 if pnl>0 else 'tomato'),
                          arrowprops=dict(arrowstyle="->", connectionstyle="arc3, rad=0.2", lw=1.5))   
        
        ax2_len = ax2.get_ylim()[1]-ax2.get_ylim()[0]
        arrow_size = ax2_len/25
        if curr_price > books[b].price_start:
            ax2.arrow(temp_price.index[-1], curr_price, 0, target-curr_price,  
                  head_width=0.15, head_length=arrow_size, linewidth=2, alpha=0.6,color='silver',
                  length_includes_head=True, zorder=4)
            ax2.text(temp_price.index[-1], curr_price+(target-curr_price)/2,f"{1-perc_target:2.1%} ", va='center',
                     ha='right', color='silver', fontweight='bold')
            ax2.arrow(temp_price.index[-1], price_start, 0, curr_price-price_start,  
                  head_width=0.15, head_length=arrow_size, linewidth=2, alpha=0.6,color='g',
                  length_includes_head=True, zorder=4)
            ax2.text(temp_price.index[-1], price_start+(curr_price-price_start)/2,f" {perc_target:2.1%}", va='center',
                     ha='left', color='g', fontweight='bold')
        else:
            # ax2.arrow(temp_price.index[-1], curr_price, 0, stop-curr_price,  
            #            head_width=0.15, head_length=arrow_size, linewidth=2, alpha=0.6,color='r',
            #           length_includes_head=True, zorder=4)
            ax2.text(temp_price.index[-1], curr_price+(stop-curr_price)/2,f"{perc_stop:2.1%} ",  va='center',
                    ha='right', color='r', fontweight='bold')
        
    for c in range(0,n_row):
        axes[c,0].set_ylabel('PnL (M BRL)')
        
        
        
    fig.subplots_adjust(bottom=0.15/n_row)
    legend_elements = [l_plot, l_stop, l_target, l_price]
    plt.figlegend(legend_elements, [l.get_label() for l in legend_elements], loc = 'lower center', 
                  borderaxespad=0.1, ncol=4, labelspacing=0.,  prop={'size': 11, 'weight':'normal'},) 
    
    fig.savefig('t.svg', bbox_inches = "tight")  
    plt.show()