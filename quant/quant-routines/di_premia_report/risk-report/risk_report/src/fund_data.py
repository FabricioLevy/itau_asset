import fund_utils as fu
import pandas as pd
import numpy as np
import datetime


class db_data():
    
    HypoPnLProducts = ['Equity Option', 'IDI Option', 'CPM Option', 
                       'FX Option']
    
    def __init__(self, 
                 dt, 
                 str_fund, 
                 parent_tree=['Risk', 'Traders', 'PerformanceAttribution', 'TraderMandate'],
                 verbose=False,
                 loadHist=True):
        self._dt = dt
        self._fund = str_fund
        _, self._connection = fu.get_DB_conn('prod')
        self._mtd, self._std = [max(fu.date_ini[str_fund], i) for i in fu.get_PeriodToDate(dt)]
        self._itd = fu.date_ini[str_fund]
        self._risk_limits = fu.get_RiskLimits(dt, str_fund)
        self._risk_share = fu.get_DailyRiskShare(dt, str_fund)
        if type(parent_tree)==str:
            parent_tree = [parent_tree]
        self._parent_tree = parent_tree
        if verbose: print("__load_book_trees...")
        self.__load_book_trees()
        if verbose: print("__load_pnl...")
        self.__load_pnl()
        if verbose: print("__pnl_by_month...")
        self.__pnl_by_month()
        if verbose: print("__load_primitives...")        
        self.__load_primitives()
        if verbose: print("__load_risk...")  
        self.__load_risk()
        if verbose: print("__load_position...")  
        self.__load_position()
        if verbose: print("__load_covar_matrix...")  
        self.__load_covar_matrix()
        if verbose: print("__set_parametricVaR_weights...")  
        self.__set_parametricVaR_weights()
        if verbose: print("__calculate_cvar_weights...")  
        self.__calculate_cvar_weights()
        if verbose: print("__load_CDI...")
        self.__load_CDI()
        if loadHist:
            if verbose: print("__load_hist_var...")
            self.__load_hist_var()
        self.__set_BearBull()
        
        
    def __repr__(self):
        return f"database object: '{self._fund}' {self._dt:%d%b%Y}"
        
    
    def __load_book_trees(self):
        self._dic_books = {}
        self._dic_nodes = {}
        for str_tree in self._parent_tree:
            str_sql = f"""
                       SELECT [parent_tree],[parent_node],[node],[book]
                       FROM [lote45].[book_tree]
                       WHERE parent_tree = '{str_tree}'
                """
            dfTree = pd.read_sql(str_sql, 
                                 self._connection)
            nd = fu.Node(str_tree, dfTree)    
            self._dic_books[str_tree] = nd.to_inv_dict(str_tree) 
            self._dic_nodes[str_tree] = nd
        

    def __load_pnl(self):
        str_sql = f"""
                 SELECT b.[date_reference], b.book,b.lote45_product_class,b.lote45_product, 
                     sum([value]/n.NAV_D1) as PnL_Perc  
                 FROM [lote45].[book_overview] b  
                   	INNER JOIN middle.NAV n 
                       ON n.date_reference = b.date_reference and n.trading_desk = b.trading_desk
                 WHERE [measure] = 'PL'  and b.date_reference <='{self._dt:%Y-%m-%d}'
                        and b.[trading_desk] = '{self._fund}'
                 GROUP BY b.[date_reference], b.book,b.lote45_product_class,b.lote45_product
                 """
        self._dfPnL = pd.read_sql(str_sql, 
                                  self._connection)
        self._dic_pnl = {}
        for key in ['lote45_product_class', 'lote45_product']:
            self._dic_pnl[key] = self._dfPnL.pivot_table(index='date_reference', 
                                                         columns=key, 
                                                         values='PnL_Perc', 
                                                         aggfunc=np.sum).sort_index()
        for str_tree in self._parent_tree:
            self._dfPnL[str_tree] = self._dfPnL['book'].apply(lambda x: self._dic_books[str_tree][x])
            self._dic_pnl[str_tree] = self._dfPnL.pivot_table(index='date_reference', 
                                                              columns=str_tree, 
                                                              values='PnL_Perc', 
                                                              aggfunc=np.sum).sort_index()
            self._dic_pnl[str_tree]['Fund'] = self._dic_pnl[str_tree].fillna(0).sum(axis=1) 
        
        for t in self._risk_share.columns:
            if t not in self._dic_pnl['Traders'].columns:
                self._dic_pnl['Traders'][t] = pd.NA 
                
    
    
    def __pnl_by_month(self):
        self._dic_pnl_month = {}
        dic_months = fu.get_endOfMonths(self._dt, 
                                        fu.date_ini[self._fund])
        for str_tree in self._parent_tree:
            self._dic_pnl_month[str_tree] = pd.DataFrame(index=dic_months.keys(), 
                                                         columns=self._dic_pnl[str_tree].columns)
            temp_df = (self._dic_pnl[str_tree].fillna(0)+1).cumprod()
            for m, (d1, d2) in dic_months.items():
                self._dic_pnl_month[str_tree].loc[m] = temp_df.loc[d2] / temp_df.loc[d1] - 1
            self._dic_pnl_month[str_tree].replace(0, np.nan, inplace=True)
        
        self._dic_pnl_month['Traders_Adj'] = pd.DataFrame(index=dic_months.keys(),
                                                     columns=self._dic_pnl['Traders'].columns)
        temp_df = ((self._dic_pnl['Traders'][[c for c in self._risk_share.columns if c in self._dic_pnl['Traders'].columns]]/self._risk_share).fillna(0)+1).cumprod()
        for m, (d1, d2) in dic_months.items():
            self._dic_pnl_month['Traders_Adj'].loc[m] = temp_df.loc[d2] / temp_df.loc[d1] - 1
        self._dic_pnl_month['Traders_Adj'].replace(0, np.nan, inplace=True)

    
    def __load_risk(self):
        str_sql = f"""
                SELECT r.[date_reference],[parent_tree],[node],[risk_measure],[value]/n.NAV as value_perc
                    FROM [risk].[measure] r 
                         INNER JOIN middle.NAV n
		                        ON r.date_reference = n.date_reference and r.trading_desk = n.trading_desk
                    WHERE r.date_reference <='{self._dt:%Y-%m-%d}'
                        and r.[trading_desk] = '{self._fund}' 
            """
        self._dfRisk = pd.read_sql(str_sql, 
                                   self._connection)
        self._dic_var = {}
        self._dic_stress = {}
        for str_tree in self._parent_tree + ['Geography', 'Fund']:
            temp_df = self._dfRisk[self._dfRisk['parent_tree']==str_tree]
            self._dic_var[str_tree] = temp_df[temp_df['risk_measure']=='VaR'].pivot(index='date_reference', 
                                                                                    columns='node', 
                                                                                    values='value_perc').sort_index()
            self._dic_stress[str_tree] = temp_df[temp_df['risk_measure']=='Stress'].pivot(index='date_reference', 
                                                                                          columns='node', 
                                                                                          values='value_perc').sort_index()
      
    def __load_primitives(self):
        str_sql = f"""
               SELECT lp.[lote45_product], lp.[lote45_product_class], [primitive],
                    [primitive_class], [book],lp.[product_currency],
                    isnull(mp.onshore_risk, 0) as geo, [bucket], [eq_position], 
                    [amount], [delta], [gamma], [vega]
               FROM [lote45].[primitive] lp LEFT JOIN middle.product mp
			     ON lp.lote45_product = mp.lote45_product
               WHERE date_reference = '{self._dt:%Y-%m-%d}'
                        AND [trading_desk] = '{self._fund}' 
            """
        self._dfPrimitive = pd.read_sql(str_sql, 
                                        self._connection)
        #change caixa off risk to 'onshore'
        self._dfPrimitive.loc[self._dfPrimitive['book']=='Caixa Off', 'geo'] = True
        
        for str_tree in self._parent_tree:
            self._dfPrimitive[str_tree] = self._dfPrimitive['book'].apply(lambda x: self._dic_books[str_tree][x])
    
    
    def __load_covar_matrix(self):
        str_sql = f"""
        SELECT [primitive1],[primitive2],[covar_value]
          FROM [lote45].[covar_matrix]
          WHERE date_reference = '{self._dt:%Y-%m-%d}' 
          ORDER BY 1, 2
        """
        dfCovarDB = pd.read_sql(str_sql, self._connection).pivot(index='primitive1', 
                                                                 columns='primitive2', 
                                                                 values='covar_value').fillna(0)
        X = dfCovarDB.values
        X = np.triu(X) + np.tril(X, -1).T
        self._dfCovar = pd.DataFrame(np.triu(X) + np.tril(X.T, -1), 
                                     columns=dfCovarDB.index, 
                                     index=dfCovarDB.index)
        
        
    def __load_position_old(self):
        str_sql = f"""
                     SELECT bo.book, bo.lote45_product, p.id, p.product_type, 
                         [value] as Amount, pp.price, pp.rate, p.date_maturity, 
                         p.lot_size, p.option_style, p.option_type, p.option_strike,
                         p.product_underlying, p.product_currency
                    FROM [lote45].[book_overview] bo 
	                   INNER JOIN middle.product p 
                                        ON bo.lote45_product = p.lote45_product
	                   INNER JOIN middle.product_price pp 
                                       ON p.id = pp.product_id 
                                       AND bo.date_reference = pp.date_reference
                    WHERE bo.measure = 'Amount'  
                       AND round([value], 6) <> 0
                       AND  bo.date_reference = '{self._dt:%Y-%m-%d}' 
                       AND bo.trading_desk = '{self._fund}'
                   """
        self._dfPosition = pd.read_sql(str_sql, 
                                       self._connection)
        for str_tree in self._parent_tree:
            self._dfPosition[str_tree] = self._dfPosition['book'].apply(lambda x: self._dic_books[str_tree][x])

    def __load_position(self):
        str_sql = f"""
                     SELECT bo.book, bo.lote45_product, bo.measure, [value] 
                     FROM [lote45].[book_overview] bo 
                     WHERE bo.measure in ('Amount','Position')
                         AND round([value], 6) <> 0
                         AND  bo.date_reference = '{self._dt:%Y-%m-%d}' 
                         AND bo.trading_desk = '{self._fund}'
                   """
        self._dfPosition = pd.read_sql(str_sql, 
                                       self._connection).pivot(index=['book', 'lote45_product'],
                                                               columns=['measure'],
                                                               values='value').fillna(0)
                                        
        str_sql = f"""
                      SELECT p.lote45_product, p.product_type, pp.price, pp.rate, 
                          p.date_maturity, p.lot_size, p.option_style, p.option_type, 
                          p.option_strike, p.product_underlying, p.product_currency,
                          p.onshore_risk
                      FROM middle.product p 
                           INNER JOIN middle.product_price pp ON p.id = pp.product_id 
                      WHERE pp.date_reference = '{self._dt:%Y-%m-%d}' 
                        AND p.lote45_product IS NOT NULL
                  """                                                      
                  
        self._dfProduct = pd.read_sql(str_sql, self._connection, index_col='lote45_product')
        self._dfPosition = self._dfPosition.join(self._dfProduct, how='left', on='lote45_product')
                                                               
        for str_tree in self._parent_tree:
            self._dfPosition[str_tree] = self._dfPosition.index.map(lambda x: self._dic_books[str_tree][x[0]])
    
    
    
    def __set_parametricVaR_weights(self):
        w_cols = ['lote45_product', 'lote45_product_class', 'primitive',
                  'primitive_class', 'book', 'geo'] + self._parent_tree
        self._w = pd.DataFrame(self._dfPrimitive[w_cols+['delta']].values, 
                               columns=w_cols+['w'])
       
        mask_vega_rows = (self._dfPrimitive['vega']!=0)
        temp_df_vega = pd.DataFrame(self._dfPrimitive[mask_vega_rows][w_cols+['vega']].values, 
                                    columns=w_cols+['w'])
        temp_df_vega['primitive'] = temp_df_vega['primitive'].apply(lambda x: 'Vol ' + x)
       
        self._w = pd.concat([self._w, temp_df_vega])
        
        
    def __set_BearBull(self):   
        index = pd.MultiIndex.from_frame(self._w[['primitive_class','primitive']].drop_duplicates())
        self._dfBullBearPrimitive = pd.DataFrame(0,
                                                 index=index,
                                                 columns=['return'])
        
        self._dfBullBearPrimitive.loc['Equity', 'return'] = 0.02
        
        for c in ['BRL Rate Curve', 'IPCA Coupon', 'BRD Rate Curve', 'USD Rate Curve',
                 'Brazil Sovereign Yield', 'USA Sovereign Yield']:
            self._dfBullBearPrimitive.loc[c, 'return'] = - 0.01
            
        for ccy in self._dfBullBearPrimitive.loc['FX'].index:
            if ccy[:3] == 'USD':
                self._dfBullBearPrimitive.loc[('FX', ccy), 'return'] = -0.015
            else:
                self._dfBullBearPrimitive.loc[('FX', ccy), 'return'] = +0.015
        
        self._dfBullBearPrimitive = self._dfBullBearPrimitive.droplevel(0)         
                
    
    
    def get_TraderVaRWeights_byCol(self, trader='Fund', col='primitive_class'):
        if trader.upper() in ['FUND', 'FUNDO']:
            temp_w = self._w.pivot_table(index='primitive', 
                                         columns=col, 
                                         values='w', 
                                         aggfunc=np.sum)
        else:
            temp_w = self._w[self._w['Traders']==trader].pivot_table(index='primitive', 
                                                                     columns=col, 
                                                                     values='w', 
                                                                     aggfunc=np.sum)
        return pd.DataFrame(temp_w, index=self._dfCovar.index).fillna(0)
    
    
    def __calculate_cvar_weights(self):
        
        df_w = self.get_TraderVaRWeights_byCol('fund').sum(axis=1)
        cov = self._dfCovar.loc[df_w.index, df_w.index].values
        w = df_w.values
        beta_cvar = (cov @ w) / (w.T @ cov @ w)
        
        self._beta_cvar =  pd.DataFrame(beta_cvar,
                                        index=df_w.index,
                                        columns=['beta_cvar'])
    
    
    def calculate_var(self, df_w=None):
        ic_var = 1.64485362695147
        if df_w is None:
            df_w = self.get_TraderVaRWeights_byCol().sum(axis=1)
        df_w = df_w[df_w!=0]
        cov_index = [i for i in df_w.index if i in self._dfCovar.index]
        cov = self._dfCovar.loc[cov_index, cov_index].values
        w = df_w.loc[cov_index].values
        bear_bull = float(self._dfBullBearPrimitive.loc[df_w.index].T.values @ df_w)
        return [-np.sqrt(w.T @ cov @ w) * ic_var, bear_bull]
    
    
    def calculate_hyb_var(self, str_tree, c):
        if str_tree in self._dic_hypoPnL.keys():
            hypo_pnl = self._dic_hypoPnL[str_tree].join(self._ewmaWeight)
            var_b = hypo_pnl[(hypo_pnl.sort_values(c)['ewma_weight'].expanding().sum() <= 0.05).sort_index()][c].iloc[-1]
        else:
            var_b = 0
        return var_b        
    
    
    def get_adjusted_trader_pnl(self):
        temp_df = self._dic_pnl['Traders'].copy()
        temp_df = temp_df[[c for c in self._risk_share.columns]] / self._risk_share
        temp_df.replace([np.inf, -np.inf], np.nan, inplace=True)
        return temp_df
    
    
    def get_adjusted_trader_var(self):
        temp_df = self._dic_var['Traders'].copy()
        temp_df = temp_df.join(self._dic_var['Fund']) 
        return temp_df[[c for c in self._risk_share.columns]] / self._risk_share
    
    
    def __load_CDI(self):
        str_sql = """
                    SELECT [date_reference],[rate]/100 as CDI
                      FROM [middle].[product_price]
                      WHERE [product_id]='CDI' AND [date_reference]>='2020-3-21'
                      ORDER BY 1
                    """
        temp_df = pd.read_sql(str_sql, self._connection, index_col='date_reference')
        self._dfAcumCDI = ((1+temp_df[['CDI']])**(1/252)).cumprod().shift(1).fillna(1)        
        dic_months = fu.get_endOfMonths(self._dt)
        self._dic_pnl_month['CDI'] = pd.DataFrame(index=dic_months.keys(),
                                                  columns=['CDI'])
        for m, (d1, d2) in dic_months.items():
            self._dic_pnl_month['CDI'].loc[m] = self._dfAcumCDI.loc[d2] / self._dfAcumCDI.loc[d1] - 1
            self._dic_pnl_month['CDI'].replace(0, np.nan, inplace=True)
        
        return self._dfAcumCDI.copy()
    
    
    def __load_hist_var(self):
        str_path = "R:/Risk/01_DailyReports/01_01_Lote45_extract/Fund/"
        str_file = "Fund1DayHistReturnTable_{}_{:%d%b%Y}.txt".format(self._fund, self._dt)    
        try:
            dfHistVaR = pd.read_csv(str_path + str_file, 
                                    sep='\t', 
                                    parse_dates=[0], 
                                    encoding='UTF-8', 
                                    index_col=0).sort_index()
        except FileNotFoundError as err:
            raise
        dfHistVaR = dfHistVaR.fillna(0)
        
        ### calculate max and min PnL for each option position ###
        temp_df_position = self._dfPosition[self._dfPosition['product_type'].isin(self.HypoPnLProducts)].sort_values(by=['book', 'lote45_product'])
        temp_df_position = temp_df_position[temp_df_position['Amount'] != 0]
        self._df_MinMax_pnl = pd.DataFrame(columns=['max', 'min'],
                                           index=temp_df_position.index)
        for index, row in temp_df_position.iterrows():
            (book, prod) = index
            prod_type, position, qty, price, lot_size = row[['product_type', 'Position', 'Amount', 'price', 'lot_size']].values
            # position = qty * price * lot_size
            if position >= 0:
                self._df_MinMax_pnl.loc[(book, prod), 'min'] = - position
                if prod_type == 'CPM Option':
                    self._df_MinMax_pnl.loc[(book, prod), 'max'] = (qty * 100 * lot_size) - position
            else:
                self._df_MinMax_pnl.loc[(book, prod), 'max'] = - position
                if prod_type == 'CPM Option':
                    self._df_MinMax_pnl.loc[(book, prod), 'min'] = -(qty * 100 * lot_size) + position
        
        ### generate the weights for hybrid VaR ###
        alpha = 0.97        
        self._ewmaWeight = pd.DataFrame(reversed(alpha**np.arange(0,len(dfHistVaR))),
                                        index=dfHistVaR.index,
                                        columns=['ewma_weight']) * (1-alpha)
        
        ### calculate the hypo PnL using Taylor expansion for each primitive ###
        temp_df_primitive = self._dfPrimitive[~ self._dfPrimitive['primitive'].isin(['BRAZIL ONSHORE SPREAD'])]        
        dfOutput = pd.DataFrame(index=dfHistVaR.index,
                                columns=temp_df_primitive.index)
        for i in temp_df_primitive.index:
            primitive = self._dfPrimitive.loc[i, 'primitive']
            delta = self._dfPrimitive.loc[i, 'delta']
            gamma = self._dfPrimitive.loc[i, 'gamma'] 
            vega = self._dfPrimitive.loc[i, 'vega']        
            vol_shift = dfHistVaR['Vol ' + primitive] if 'Vol '+primitive in dfHistVaR.columns else 0      
            dfOutput[i] = delta*dfHistVaR[primitive] + (0.5*gamma*dfHistVaR[primitive]**2) + (vega * vol_shift)
            
        ### create dataframe with historical returns of primitives
        self._dfHistPrimitiveReturn = dfHistVaR[temp_df_primitive['primitive'].sort_values().unique()].copy()
        
        ### create dictionary of dictionaries linking each primitive to its products and books ###
        dics = {}
        for c in ['geo','lote45_product', 'book']:
            temp_dict = temp_df_primitive[c].to_dict()
            dics[c] = {}
            for k, v in temp_dict.items():
                if v not in dics[c]:
                    dics[c][v]=[k]
                else:
                    dics[c][v].append(k)
        
        ### create hypoPnL dataframe with multiindex columns ###
        temp_tuples = temp_df_primitive[['book', 'lote45_product', 'geo']].drop_duplicates()
        self._dic_geo = temp_tuples.set_index('lote45_product')['geo'].to_dict()
        tuples = [temp_tuples['geo'],
                  temp_tuples['book'],
                  temp_tuples['lote45_product']] +\
                  [temp_tuples['book'].apply(lambda x: self._dic_books[y][x]) for y in self._dic_books.keys()]  
                  # temp_tuples['book'].apply(lambda x: self._dic_books['Risk'][x]),
                  # temp_tuples['book'].apply(lambda x: self._dic_books['Traders'][x])]
        self._dfHypoPnL = pd.DataFrame(columns=pd.MultiIndex.from_arrays(tuples,
                                                                          names=['geo','book','lote45_product']+list(self._dic_books.keys())),
                                        index=dfOutput.index)
        
        for (geo, book, prod, risk, trader, perfatt, core) in self._dfHypoPnL.columns:
            cols = list(set(dics['lote45_product'].get(prod, -1)).intersection(dics['book'].get(book, -1)).intersection(dics['geo'].get(geo, -1)))
            self._dfHypoPnL[(geo, book, prod, risk, trader, perfatt, core)] = dfOutput[cols].sum(axis=1)
                
        ### for each option position, floor and ceil the hypo PnL accordingly ###    
        for book, prod in self._df_MinMax_pnl.index:
            min_val, max_val = self._df_MinMax_pnl.loc[book, prod].values
            geo = self._dic_geo[prod]
            risk = self._dic_books['Risk'][book]
            trader = self._dic_books['Traders'][book]
            perfatt = self._dic_books['PerformanceAttribution'][book]
            core = self._dic_books['TraderMandate'][book]
            self._dfHypoPnL[(geo, book, prod, risk, trader, perfatt, core)] = self._dfHypoPnL[(geo, book, prod, risk, trader, perfatt, core)].apply(lambda x: max(x, max_val))
            self._dfHypoPnL[(geo, book, prod, risk, trader, perfatt, core)] = self._dfHypoPnL[(geo, book, prod, risk, trader, perfatt, core)].apply(lambda x: min(x, min_val))        
        
        ### creating dict with grouped columns ### 
        self._dic_hypoPnL = {}
        for col in self._dfHypoPnL.columns.names:
            self._dic_hypoPnL[col] = self._dfHypoPnL.groupby(level=col, axis=1).sum()
            self._dic_hypoPnL[col]['Fund'] = self._dic_hypoPnL[col].sum(axis=1)


    
#%%
if __name__ == "__main__":

    dt, str_fund = fu.get_config(['dt', 'str_fund'])
    nav = fu.get_NAV(dt, str_fund)
    try:
        data = db_data(dt, str_fund, verbose=True)
    except Exception as err:
        print(err)
    
    # df = my_db._df_MinMax_pnl
#%%    
#     print(my_db._w)
#     df_w = my_db.get_TraderVaRWeights_byCol(trader='GB', col='book')
#     cov = my_db._dfCovar.values
 
#     for b in df_w.columns:
#         w_total = df_w[b].values
#         var = np.sqrt(w_total.T @ cov @ w_total) * 1.645 #/ nav * 10_000
        
#         hypo_pnl = my_db._dic_hypoPnL['book'][[b]].join(my_db._ewmaWeight)
#         var_b = - hypo_pnl[(hypo_pnl.sort_values(b)['ewma_weight'].expanding().sum() <= 0.05).sort_index()][b].iloc[-1]
        
#         print(f"{b:15}:{var:12,.1f}  {var_b:12,.1f}")
 
# #%%
#     _, connection = fu.get_DB_conn('prod')
#     str_sql = f"""
#            SELECT [date_reference],[product_id],[price]
#            FROM [middle].[product_price]
#            WHERE product_id in ('SPX')
#            """
#     df = pd.read_sql(str_sql, connection)
#     dfPrice = df.pivot(index='date_reference', columns='product_id', values='price').fillna(method='ffill')
#     dfRet = dfPrice.pct_change()
    
#     books = ['GB SnP', 'MS SnP']
#     hypo_pnl = (my_db._dic_hypoPnL['book'][books]/nav).join(dfRet)

# #%%
#     import statsmodels.api as sm
#     import matplotlib.pyplot as plt
#     import matplotlib.ticker as mticker

#     fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharex=True)
#     fig.tight_layout()
     
#     for ax, b, rs   in zip(axes.flatten(), books, [0.036, 0.661]):
    
#         ax.set_title(b)
#         ax.scatter(hypo_pnl['SPX'], hypo_pnl[b]/rs, c='royalblue', marker='.')
#         ax.grid(ls='--')
        
#         ax.axhline(0, lw=0.5, color='k')
#         ax.axvline(0, lw=0.5, color='k')
        
#         ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
#         ax.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
        
#         ax.set_xlabel('$\Delta SnP_i$ (%)')
        
#     axes[0].set_ylabel('PnL (%)')
    
#     # fig_file = '../../reuniao_posicionamento/tex/{0:%Y_%m_%d}/figuras/{0:%Y%m%d}_snp_hypo_pnl.pdf'.format(dt)
#     # fig.savefig(fig_file, bbox_inches = "tight")
  
#     plt.show()
    
