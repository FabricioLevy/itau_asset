# -*- coding: utf-8 -*-
"""
Created on Tue Aug 16 12:03:33 2022

@author: matheus.amaral
"""

import pandas as pd
import numpy as np
import fund_utils as fu
import datetime
from a1db.a1sql import SQLConnection
import scipy.stats as ss

class db_data():
    
    def __init__(self,
                 dt,
                 str_fund,
                 parent_tree = ['Risk', 'Traders', 'PerformanceAttribution'],
                 verbose = True):
        
        self._dt = dt
        self._fund = str_fund
        self._itd = fu.date_ini[str_fund]
        self._connection = SQLConnection().get_connection()
        self._mtd, self._std = [max(fu.date_ini[str_fund], i) for i in fu.get_PeriodToDate(dt)]
        self._risk_limits = fu.get_RiskLimits(dt, str_fund)
        self._risk_share = fu.get_DailyRiskShare(dt, str_fund)
        
        if type(parent_tree) == str:
            parent_tree = [parent_tree]
        self._parent_tree = parent_tree
        if verbose == True: print('__load_book_trees...')
        self.__load_book_trees()
        if verbose == True: print('__load_pnl...')
        self.__load_pnl()
        if verbose == True: print('__pnl_by_month...')
        self.__pnl_by_month()
        if verbose == True: print('__pnl_by_year...')
        self.__pnl_by_year()
        if verbose == True: print('__load_cdi...')
        self.__load_cdi()
        if verbose == True: print('__load_primitives...')
        self.__load_primitives()
        if verbose == True: print('__load_risk...')
        self.__load_risk()
        if verbose == True: print('__load_covar_matrix...')
        self.__load_covar_matrix()
        if verbose: print("__set_parametricVaR_weights...")  
        self.__set_parametricVaR_weights()
        
        
    def __load_book_trees(self):
        self._dict_books = {}
        
        for str_tree in self._parent_tree:
            str_sql = f"""
                        SELECT *
                        FROM lote45.book_tree
                        WHERE parent_tree = '{str_tree}'
                        """
            nd = fu.Node(str_tree, pd.read_sql(str_sql, self._connection))
            self._dict_books[str_tree] = nd.to_inv_dict(str_tree)
    
    def __load_pnl(self):
        
        str_sql = f"""
                    SELECT b.date_reference,
                        b.book,
                        b.lote45_product,
                        b.lote45_product_class,
                        p.risk_product,
                        p.perf_att_class,
                        SUM(b.value / n.NAV_D1) AS pnl_perc
                    FROM lote45.book_overview b
                    INNER JOIN middle.NAV n
                        ON b.date_reference = n.date_reference
                        AND b.trading_desk = n.trading_desk
                    LEFT JOIN lote45.product_class p
                        ON b.lote45_product_class = p.lote45_product_class
                    WHERE b.date_reference <= '{self._dt:%Y-%m-%d}'
                        AND b.trading_desk = '{self._fund}'
                        AND b.measure = 'Position PL'
                    GROUP BY b.date_reference, b.book, b.lote45_product, b.lote45_product_class, p.risk_product, p.perf_att_class
                    ORDER BY b.date_reference
                """
                
        self._dfpnl = pd.read_sql(str_sql, self._connection)
        
        self._dict_pnl = {}
        for str_tree in self._parent_tree:
            self._dfpnl[str_tree] = self._dfpnl['book'].apply(lambda x: self._dict_books[str_tree][x])
            self._dict_pnl[str_tree] = self._dfpnl.pivot_table(index = 'date_reference',
                                                               columns = str_tree,
                                                               values = 'pnl_perc',
                                                               aggfunc = np.sum).fillna(0)
            self._dict_pnl[str_tree]['Fund'] = self._dict_pnl[str_tree].sum(axis = 1)
            
        self._dict_pnl['Traders_Adj'] = pd.DataFrame()
        for c in self._dict_pnl['Traders'].drop('Shared', axis = 1).columns:
            self._dict_pnl['Traders_Adj'][c] = self._dict_pnl['Traders'][c] / self._risk_share[c]
        self._dict_pnl['Traders_Adj'].replace([np.inf, -np.inf], 0,inplace = True)
        
     
        
    def __pnl_by_month(self):
        self._dict_month_pnl = {}
        dict_months = fu.get_endOfMonths(self._dt)
        for str_tree in self._parent_tree + ['Traders_Adj']:
            self._dict_month_pnl[str_tree] = pd.DataFrame(index = dict_months.keys(),
                                                          columns = self._dict_pnl[str_tree].columns)
            
            if list(dict_months.values())[0][0] not in self._dict_pnl[str_tree].index:
                self._dict_pnl[str_tree].loc[list(dict_months.values())[0][0]] = np.nan
                
            temp_df = (1 + self._dict_pnl[str_tree].fillna(0)).cumprod()
            
            for m, (dt1,dt2) in dict_months.items():
                self._dict_month_pnl[str_tree].loc[m] = temp_df.loc[dt2] / temp_df.loc[dt1] - 1
            self._dict_month_pnl[str_tree].fillna(0, inplace = True)
            

    def __pnl_by_year(self):
        self._dict_year_pnl = {}
        for str_tree in self._parent_tree + ['Traders_Adj']:
            df = self._dict_pnl[str_tree].copy()
            df.index = pd.to_datetime(df.index)
            
            years = df.index.year.unique()
            
            dict_year = {}
            for y in years:
                if y == self._itd.year:
                    dt1 = pd.to_datetime(self._itd)
                else:
                    dt1 = max(df[df.index.year == y-1].index)
                dt2 = max(df[df.index.year == y].index)
                dict_year[dt2] = (dt1,dt2)
                
            self._dict_year_pnl[str_tree] = pd.DataFrame(index = dict_year.keys(),
                                                         columns = df.columns)
            df = (1 + df).cumprod()
            for y,(dt1,dt2) in dict_year.items():
                self._dict_year_pnl[str_tree].loc[y] = df.loc[dt2] / df.loc[dt1] - 1
                
    
    def __load_cdi(self):
        str_sql = f"""
                SELECT date_reference,
                    rate / 100 as CDI
                FROM middle.product_price
                WHERE product_id = 'CDI'
                    AND date_reference >= '{self._itd:%Y-%m-%d}'
                ORDER BY date_reference
                """
        self._daily_cdi = pd.read_sql(str_sql,self._connection, index_col='date_reference')
        self._daily_cdi['CDI'] = (1 + self._daily_cdi) ** (1/252) - 1
        
        
        dict_months = fu.get_endOfMonths(self._dt)
        self._monthly_cdi = pd.DataFrame(index = dict_months.keys(), columns = ['CDI'])
        
        temp_df = (1 + self._daily_cdi).cumprod()
        for m, (dt1, dt2) in dict_months.items():
            self._monthly_cdi.loc[m] = temp_df.loc[dt2] / temp_df.loc[dt1] - 1
            
        temp_df.index = pd.to_datetime(temp_df.index)
        
        years = temp_df.index.year.unique()
        dict_year = {}
        
        for y in years:
            if y == self._itd.year:
                dt1 = pd.to_datetime(self._itd)
            else:
                dt1 = max(temp_df[temp_df.index.year == y-1].index)
            dt2 = max(temp_df[temp_df.index.year == y].index)
            dict_year[dt2] = (dt1, dt2)
            
        self._annualy_cdi = pd.DataFrame(index = dict_year.keys(), columns = ['CDI'])
        
        for m, (dt1, dt2) in dict_year.items():
            self._annualy_cdi.loc[m] = temp_df.loc[dt2] / temp_df.loc[dt1] - 1
        
        
    def __load_primitives(self):
        str_sql = f"""
                SELECT p.lote45_product,
                    p.lote45_product_class,
                    r.risk_product,
                    r.perf_att_class,
                    p.primitive,
                    p.primitive_class,
                    p.book,
                    p.product_currency,
                    p.bucket,
                    p.eq_position,
                    mp.onshore_risk,
                    p.amount,
                    p.delta / n.NAV AS delta,
                    p.gamma,
                    p.vega / n.NAV AS vega
                FROM lote45.primitive p
                INNER JOIN middle.NAV n
                    ON p.date_reference = n.date_reference
                    AND p.trading_desk = n.trading_desk
                LEFT JOIN lote45.product_class r
                    ON p.lote45_product_class = r.lote45_product_class
                LEFT JOIN middle.product mp
                    ON mp.lote45_product = p.lote45_product
                WHERE p.date_reference = '{self._dt:%Y-%m-%d}'
                    AND p.trading_desk = '{self._fund}'
                """
        
        self._dfPrimitive = pd.read_sql(str_sql, self._connection)
        
        for tree in self._parent_tree:
            self._dfPrimitive[tree] = self._dfPrimitive['book'].apply(lambda x: self._dict_books[tree][x])
            
        
    def __load_risk(self):
        str_sql = f"""
                SELECT r.date_reference,
                    r.parent_tree,
                    r.node,
                    r.risk_measure,
                    r.value / n.NAV AS value_perc
                FROM risk.measure r
                INNER JOIN middle.NAV n
                    ON r.date_reference = n.date_reference
                    AND r.trading_desk = n.trading_desk
                WHERE r.date_reference <= '{self._dt:%Y-%m-%d}'
                    AND r.trading_desk = '{self._fund}'
                ORDER BY r.date_reference
                """
        self._dfRisk = pd.read_sql(str_sql, self._connection)
        self._dict_var = {}
        self._dict_stress = {}
        
        for tree in self._parent_tree + ['Fund']:
            temp = self._dfRisk[self._dfRisk['parent_tree'] == tree]
            self._dict_var[tree] = temp[temp['risk_measure'] == 'VaR'].pivot(index = 'date_reference',
                                                                            columns = 'node',
                                                                            values = 'value_perc').fillna(0)
            
            self._dict_stress[tree] = temp[temp['risk_measure'] == 'Stress'].pivot(index = 'date_reference',
                                                                                  columns = 'node',
                                                                                  values = 'value_perc').fillna(0)
            
    def __load_covar_matrix(self):
        str_sql = f"""
                SELECT primitive1,
                    primitive2,
                    covar_value
                FROM lote45.covar_matrix
                WHERE date_reference = '{self._dt:%Y-%m-%d}'
                ORDER BY 1,2
            """
        dfCovarDB = pd.read_sql(str_sql, self._connection).pivot(index = 'primitive1',
                                                                 columns = 'primitive2',
                                                                 values = 'covar_value').fillna(0)
        X = dfCovarDB.values
        self._dfCovar = pd.DataFrame(data = np.triu(X) + np.tril(X.T,-1), 
                                     index = dfCovarDB.index, columns = dfCovarDB.index)
        
    def __set_parametricVaR_weights(self):
         w_cols = ['lote45_product', 'lote45_product_class', 'primitive',
                   'primitive_class', 'book', 'Risk', 'Traders','onshore_risk',
                   'PerformanceAttribution']
         self._w = pd.DataFrame(self._dfPrimitive[w_cols+['delta']].values, 
                                columns=w_cols+['w'])
        
         mask_vega_rows = (self._dfPrimitive['vega']!=0)
         temp_df_vega = pd.DataFrame(self._dfPrimitive[mask_vega_rows][w_cols+['vega']].values, 
                                     columns=w_cols+['w'])
         temp_df_vega['primitive'] = temp_df_vega['primitive'].apply(lambda x: 'Vol ' + x)
        
         self._w = pd.concat([self._w, temp_df_vega])
        
        
      
        
    def get_PnL(self, by = 'PerformanceAttribution', period = 'Daily', append_cdi = True):
        """ 
        Get the Pnl divided by the NAV, using different attributes.
        
        Parameters:
        -----------
            by: {'PerformanceAttribution','Traders','Traders_Adj','Risk'}, default 'PerformanceAttribution' 
                Set of attributes that will be displayed in each column
                
            period: {'Daily', 'Monthly', 'Annualy'}, default 'Daily'
                The period by wich the Pnl will be grouped in each line
                
            append_cdi: bool, default True
                Append the return of CDI to the Pnl DataFrame (default = True)
                
        Returns
        -------
            dfPnl: DataFrame
                DataFrame containing the Pnl
        """
        dict_period = {'Daily': (self._dict_pnl, self._daily_cdi),
                       'Monthly': (self._dict_month_pnl, self._monthly_cdi),
                       'Annualy':(self._dict_year_pnl, self._annualy_cdi)}
        
        
        dfPnl = dict_period[period][0][by].copy()
        
        if append_cdi:
            dfPnl = dfPnl.join(dict_period[period][1])
        return dfPnl.fillna(0)
        
        
    def get_DailyPnLbyAttribute(self, by = 'Traders', attribute = 'PerformanceAttribution'):
        """
        Get the daily Pnl divided by the NAV by 2 attributes in a MultiIndex DataFrame with 2 columns indexes.

        Parameters
        ----------
        by : {'Traders','PerformanceAttribution','Risk',lote45_product_class,lote45_product,risk_product}, default 'Traders'
            First level of the MultiIndex columns.
        
        attribute : {'Traders','PerformanceAttribution','Risk',lote45_product_class,lote45_product,risk_product}, default 'PerformanceAttribution'
            Second level of the MultiIndex columns.

        Returns
        -------
        dfPnl : DataFrame
            DataFrame conating the Pnl.

        """
        dfPnl = self._dfpnl.pivot_table(index = 'date_reference',
                                  columns = [by,attribute],
                                  values = 'pnl_perc',
                                  aggfunc = np.sum).fillna(0)
            
        temp = dfPnl.sum(axis = 1, level = 1)
        temp = pd.concat([temp], keys = ['Fund'], axis = 1)
        
        dfPnl = dfPnl.join(temp)
        
        return dfPnl
        
    
    def get_MonthlyPnLbyAttribute(self, by = 'Traders', attribute = 'PerformanceAttribution'):
        df = self.get_DailyPnLbyAttribute(by, attribute)
        
        dict_months = fu.get_endOfMonths(self._dt)
        
        mindex = pd.MultiIndex(levels= [[],[]],
                               codes=[[],[]],
                                     names=['prod','var'])
        
        df = (1 + df).cumprod()
        dfPnl = pd.DataFrame(index = dict_months.keys(), columns = mindex)
        
        for c in df.columns.get_level_values(0).unique():
            temp = pd.DataFrame(index = dict_months.keys(), columns = df[c].columns)            
            for m,(dt1,dt2) in dict_months.items():
                temp.loc[m] = df.loc[dt2,c] / df.loc[dt1,c] - 1   
            
            temp = pd.concat([temp], keys = [c], axis = 1)
            dfPnl = dfPnl.join(temp)
            
        
        return dfPnl

        
    
    def get_Risk(self, risk = 'VaR', tree = 'Fund'):
        if risk == 'VaR':
            dfRisk = self._dict_var[tree].copy()
        else:
            dfRisk = self._dict_stress[tree].copy()
        return dfRisk
    
    
    def get_TraderAdjustedVaR(self):
        df = self.get_Risk('VaR', 'Traders').copy()
        
        for col in df.columns:
            df[col] = df[col] / self._risk_share[col]
        return df
        
        
        
    def get_AdjustedVaR(self, risk = 'VaR'):
        
        dfRisk = self.get_Risk(risk, tree = 'Traders')
        
        for col in dfRisk.drop('Shared', axis = 1).columns:
            dfRisk[col] /= self._risk_share[col]
            
        dfRisk = dfRisk.replace([np.inf, -np.inf], 0).fillna(0)
        return dfRisk
      

      
    def get_Delta_byAttribute(self, trader='Fund', col='primitive_class', onshore_risk = 'all'):
        if onshore_risk != 'all':
            df = self._w[self._w['onshore_risk'] == onshore_risk].copy()
        else:
            df = self._w.copy()
        if trader.upper() in ['FUND', 'FUNDO']:
            temp_w = df.pivot_table(index='primitive', 
                                         columns=col, 
                                         values='w', 
                                         aggfunc=np.sum)
        else:
            temp_w = df[df['Traders']==trader].pivot_table(index='primitive', 
                                                                     columns=col, 
                                                                     values='w', 
                                                                     aggfunc=np.sum)
        return temp_w.fillna(0)
    
    def get_Covar(self):
        
        dfCovar = self._dfCovar
        
        missing_primitives = [i for i in self._w['primitive'].unique() if i not in dfCovar.index]
        
        for i in missing_primitives:
            dfCovar[i] = 0
            dfCovar.loc[i] = 0
        return dfCovar
    
    
    
    
    def get_TraderCVaR_byAttribute(self, trader='Fund', col='primitive_class', 
                                   onshore_risk = 'all',conf_level = 0.95, drop_primitives = None):
        
        temp_w = self.get_Delta_byAttribute(trader, col, onshore_risk)
            
        dfCov = self.get_Covar()
        
        df_w = pd.DataFrame(temp_w, index =dfCov.index).fillna(0)
        df_w[trader] = df_w.sum(axis = 1)
        
        if drop_primitives != None:
            df_w.drop(drop_primitives, inplace = True)
        
        ic_var = ss.norm.ppf(conf_level)
        dfCVar = pd.DataFrame(index = df_w.index)
        
        cov = dfCov.loc[df_w.index,df_w.index].values
        
        
        for col in df_w.columns:
            w = df_w[col].values
            var = np.sqrt(w.T @ cov @ w) * ic_var * 10_000
            
            beta_cvar = (cov @ w) / (w.T @ cov @ w)
            
            dfCVar[col] = beta_cvar * var * df_w[col]
            
        return dfCVar
    
        
    
    def get_BenchmarkBeta(self, onshore_risk = True):
        
        benchmarks = {True:'IBVSP',
                        False:'SPX'}
        
        bench = benchmarks[onshore_risk]
        equities = self.get_Delta_byAttribute(onshore_risk = onshore_risk)[['Equity']]
        equities = equities[equities['Equity'] != 0]
        
        if benchmarks[onshore_risk] not in equities.index:
            equities.loc[bench, 'Equity'] = 0
            
        dfCov = self._dfCovar.copy()
        missing_primitives = [i for i in equities.index if i not in dfCov.index]
        
        for i in missing_primitives:
            dfCov[i] = 0
            dfCov.loc[i] = 0
        
        dfCov = dfCov.loc[equities.index, equities.index]
        dfBeta = pd.DataFrame(index = equities.index)
        
        dfBeta[f'Beta_{bench}'] = dfCov.loc[bench] / dfCov.loc[bench, bench]
        
        return dfBeta
      
        
        
#%%

if __name__ == '__main__':
    
    dt = datetime.date(2022,8,24)
    str_fund = 'A1 Master FIM'
    
    db = db_data(dt,str_fund)
        
    
    dfvar = db.get_TraderCVaR_byAttribute(col = 'Traders')
    fund_var = dfvar.sum().loc['Fund']
    delta = db.get_Delta_byAttribute(col = 'Traders')
    
    import scipy.stats as ss
    
    dfCovar = db.get_Covar()
    ic_var = ss.norm.ppf(0.95)
    dict_trader = {}
    
    
    for col in delta.columns:
        
        temp = delta.drop(col, axis = 1)
        temp['Fund'] = temp.sum(axis = 1)
        
        
        cov = dfCovar.loc[temp.index, temp.index].values
        w = temp['Fund'].values
            
        var = np.sqrt(w.T @ cov @ w) * ic_var * 10_000
        dict_trader[col] = var    
        
    dict_marginalVar = {}
    for i, v in dict_trader.items():
        dict_marginalVar[i] = fund_var - v
