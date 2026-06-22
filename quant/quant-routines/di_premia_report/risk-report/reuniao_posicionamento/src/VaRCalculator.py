# -*- coding: utf-8 -*-
"""
Created on Mon Oct 31 09:27:01 2022

@author: matheus.amaral
"""

import pandas as pd
import numpy as np
from a1db.a1sql import SQLConnection
import fund_utils as fu
from datetime import date
import warnings
import scipy.stats as ss

warnings.filterwarnings('ignore')

class VaRCalculator:
    _trees = ['Traders', 'Risk', 'PerformanceAttribution', 'TraderMandate']
    _dictGroup = {'BRD Rate Curve':'Cupom Cambial',
      'BRL Rate Curve':'Pre',
      'Brazil Sovereign Yield':'Pre',
      'IPCA Coupon':'IPCA',
      'USA Sovereign Yield':'US Rate',
      'USD Rate Curve': 'US Rate'}
    
    def __init__(self, dt, str_fund, verbose = True):
        self._dt = dt
        self._fund = str_fund
        
        self._connection = SQLConnection().get_connection()
        self._dictShare = fu.get_DailyRiskShare(dt, str_fund).loc[dt].to_dict()
        self._dictShare['Shared'] = 1
        self._dfLimit = fu.get_DailyRiskShare(dt, str_fund, 'var_limit')
        
        dict_met = {'traders':self.__loadTraders(),
                    'primitives':self.__loadPrimitives(),
                    'covar matrix':self.__loadCovar(),
                    'classes':self.__loadClasses(),
                    'VaR':self.__loadVaRHistory()
                    }
        
        for key, met in dict_met.items():
            if verbose:
                print(f"Loading {key}...")
            met
        print('\nDone')
        
    def __loadTraders(self):
        str_sql = """
                SELECT trader_id
                FROM risk.trader
                WHERE date_end IS NULL
                ORDER BY ordering
                """
        self._traders = pd.read_sql(str_sql, self._connection).values.flatten().tolist()
        
        
    def __loadPrimitives(self):
        str_sql = f"""
                SELECT p.primitive,
                    p.book,
                    p.primitive_class,
                    SUM(p.delta / m.NAV) AS delta,
                    SUM(p.vega / m.NAV) AS vega
                FROM lote45.primitive p
                INNER JOIN middle.NAV m
                    ON p.date_reference = m.date_reference
                    AND p.trading_desk = m.trading_desk
                WHERE p.date_reference = '{self._dt:%Y-%m-%d}'
                    AND p.trading_desk = '{self._fund}'
                GROUP BY p.primitive, p.book, p.primitive_class
                ORDER BY p.primitive
                """
        dfPrim = pd.read_sql(str_sql, self._connection)
        
        dfVega = (dfPrim.query("vega != 0")
                  .drop('delta', axis = 1)
                  .rename({'vega':'delta'}, axis = 1))
        dfVega['primitive'] = 'Vol ' + dfVega['primitive']
        
        self._dfPrim = pd.concat([dfPrim.drop('vega', axis = 1), dfVega])
        
        for data in self._trees:
            str_sql = f"""
                    SELECT *
                    FROM lote45.book_tree
                    WHERE parent_tree = '{data}'
                    """
            dict_books = fu.Node(data, 
                                 pd.read_sql(str_sql, self._connection)).to_inv_dict(data)
            
            self._dfPrim[data] = self._dfPrim['book'].apply(lambda x: dict_books[x])
            
    
    def __loadCovar(self):
        str_sql = f"""
                SELECT primitive1,
                    primitive2,
                    covar_value
                FROM lote45.covar_matrix
                WHERE date_reference = '{self._dt:%Y-%m-%d}'
                ORDER BY 1,2
                """
        dfDB = (pd.read_sql(str_sql, self._connection)
                .pivot(index = 'primitive1',
                       columns = 'primitive2',
                       values = 'covar_value')
                .fillna(0))
        
        self._dfCovar = pd.DataFrame(data = np.triu(dfDB.values) + np.tril(dfDB.values.T, -1),
                               index = dfDB.index,
                               columns = dfDB.index)
    
    def __loadClasses(self):
        str_sql = """
                SELECT DISTINCT primitive_class,
                    primitive
                FROM lote45.primitive
                """
        primitive = pd.read_sql(str_sql, self._connection,index_col = 'primitive')
        
        vega = pd.DataFrame(index = [i for i in self._dfPrim['primitive'].unique() if 'Vol ' in i],
                            columns = ['primitive_class'],
                            data = 'Vega')
        
        self._dfClass = pd.concat([primitive, vega])
        
    def __loadVaRHistory(self):
        str_sql = f"""
                SELECT m.date_reference,
                    m.parent_tree,
                    m.node,
                    m.risk_measure,
                    m.value / n.NAV * 10000 AS VaR
                FROM risk.measure m
                INNER JOIN middle.NAV n
                    ON m.date_reference = n.date_reference
                    AND m.trading_desk = n.trading_desk
                WHERE m.date_reference <= '{self._dt:%Y-%m-%d}'
                    AND m.trading_desk = '{self._fund}'
                    AND m.risk_measure IN ('VaR', 'Hyb VaR')
                """
        self._dfVar = pd.read_sql(str_sql, self._connection)
        
        self._VaRFund = (self._dfVar.query(f"parent_tree == 'Fund'")
                  .pivot(index = 'date_reference',
                         columns = ['node', 'risk_measure'],
                         values = 'VaR')
                  .fillna(0)
                  .copy())
        
        self._dfVar = self._dfVar.query(f"parent_tree != 'Fund'")
        
    def get_Primitives(self, by = ['Traders'], drop = None):
        
        if len(by) >= 3:
            raise Exception('By argument must have 2 factors or less')
        
        dfTemp = (self._dfPrim.pivot_table(index = 'primitive',
                                           columns = by,
                                           values = 'delta',
                                           aggfunc = np.sum)
                  .fillna(0)
                  .copy())
        
        if 'Traders' == by[0]:
            dfTemp = dfTemp[[i for i in self._traders if i in dfTemp.columns] + ['Shared']]
            
        if drop is not None:
            dfTemp = dfTemp[~dfTemp.index.isin(drop)]
        
        if isinstance(dfTemp.columns, pd.MultiIndex):
            dfFund = pd.concat([dfTemp.groupby(axis = 1, level = 1).sum()],
                               keys = ['Fund'], axis = 1)
            dfComp = dfTemp.join(dfFund)
            
            dfTemp = pd.DataFrame(columns = pd.MultiIndex.from_product([[],[]],
                                                                       names = by),
                                  index = dfComp.index)
            
            for factor in dfComp.columns.get_level_values(0).unique():
                df = dfComp[factor]
                df['Total'] = df.sum(axis = 1)
                
                dfTemp = dfTemp.join(pd.concat([df], keys = [factor], axis = 1))
                                     
        else:
            dfTemp['Fund'] = dfTemp.sum(axis = 1)
        
        return dfTemp
    
    
    def get_Covar(self, dfPrimitives = None):
        
        dfTemp = self._dfCovar.copy()
        if dfPrimitives is None:
            return dfTemp
        else:
            missing_products = [i for i in dfPrimitives.index if i not in dfTemp.index]
            for i in missing_products:
                dfTemp[i] = 0
                dfTemp.loc[i] = 0

            return dfTemp.loc[dfPrimitives.index, dfPrimitives.index]


    def calculate_CVaR(self, by = ['Traders'], drop = None, confidence = 0.95, adjust = False, group = True):
        
        dfPrim = self.get_Primitives(by, drop)
        cov = self.get_Covar(dfPrim).values
        ic_var = ss.norm.ppf(confidence)
        
        if (adjust == True) & (by[0] != 'Traders'):
            raise Exception("It's not possible to adjust the size of another factor other than Traders")
          
            
        if isinstance(dfPrim.columns, pd.MultiIndex):
            dfAgg = pd.DataFrame(index = dfPrim.index,
                                 columns = pd.MultiIndex.from_product([[],[]],
                                                                      names = by))
            
            for col in dfPrim.columns.get_level_values(0).unique():
                
                dfTemp = dfPrim[col]
                for c in dfTemp.columns:
                    w = dfTemp[c].values
                    
                    var = np.sqrt(w.T @ cov @ w) * ic_var
                    beta = (cov @ w) / (w.T @ cov @ w)
                    
                    dfTemp[c] = dfTemp[c] * beta * var * 10_000
                    
                if adjust:
                    dfTemp /= self._dictShare[col]
                    
                dfAgg = dfAgg.join(pd.concat([dfTemp], keys = [col], axis = 1))
                
            if group:
                dfAgg = (dfAgg.join(pd.concat([self._dfClass.replace(self._dictGroup)], keys = ['group'], axis = 1))
                         .groupby(('group','primitive_class'))
                         .sum())
        else:
            dfAgg = pd.DataFrame(index = dfPrim.index)
            for col in dfPrim.columns:
                w = dfPrim[col].values
                
                var = np.sqrt(w.T @ cov @ w) * ic_var
                beta = (cov @ w) / (w.T @ cov @ w)
                
                dfAgg[col] = dfPrim[col] * beta * var * 10_000
                
                if adjust:
                    dfAgg[col] /= self._dictShare[col]
                
            if group:
                dfAgg = (dfAgg.join(self._dfClass.replace(self._dictGroup))
                         .groupby('primitive_class')
                         .sum())
        
        dfAgg.loc['VaR'] = dfAgg.sum()
        return dfAgg


    def calculate_CvarByFactors(self, factor1 = 'Traders', factor2 = 'TraderMandate', confidence = 0.95):
        
        ic_var = ss.norm.ppf(0.95)
        dfPrim = self.get_Primitives(by = [factor1,factor2])
        cov = self.get_Covar(dfPrim)
        
        dfFund = dfPrim['Fund']
        
        dict_MargVar = {}
        
        for col in dfFund.columns:
            w = dfFund[col]
            var = np.sqrt(w.T @ cov @ w) * ic_var
            
            beta = (cov @ w) / (w.T @ cov @ w)
            dict_MargVar[col] = beta * var * 10_000
            
        dfTemp = pd.DataFrame(columns = dfFund.columns)
        
        for factor in np.delete(dfPrim.columns.get_level_values(0).unique(),-1):
            df = dfPrim[factor]
            
            for c in df.columns:
                df[c] = df[c] * dict_MargVar[c]
                
            df['Trader'] = factor
            df = df.groupby('Trader').sum()
            
            dfTemp = pd.concat([dfTemp, df])
        
        dfTemp = dfTemp.fillna(0)
        dfTemp.loc['Fund'] = dfTemp.sum()
        
        return dfTemp
                

    def get_HistoricVaR(self, tree = 'Traders'):
        
        
        dfTemp = (self._dfVar.query(f"parent_tree == '{tree}'")
                 .pivot(index = 'date_reference',
                        columns = ['node', 'risk_measure'],
                        values = 'VaR')
                 .fillna(0)
                 .copy())
        
        if tree == 'Traders':
            dfTemp = dfTemp[[i for i in self._traders if i in dfTemp.columns] + ['Shared']]
        
        
        return dfTemp.join(self._VaRFund)

    # def VaRHistoricBreach(self):
        
    #     dfTemp = (self._dfVar.query("(parent_tree == 'Traders) & (risk_measure == 'VaR')")
    #               .pivot(index = 'date_reference',
    #                     columns = 'node',
    #                     value = 'VaR')
    #               .fillna(0)
    #               .copy()
    #               .join(self._VaRFund)
    #               .drop('Shered', axis = 1))
        
    #     dfOut = pd.DataFrame(columns = ['VaR', 'Limit'])
        
    #     for col in dfTemp.columns:
            
    #         df = dfTemp[[col]].join(self._dfLimit[col])
            
        
        

#%%
if __name__ == '__main__':
    
    dt = date(2022,10,31)
    str_fund = 'A1 Master FIM'
    
    vcal = VaRCalculator(dt, str_fund)
    # a = vcal.get_Primitives(by = ['Traders', 'TraderMandate'])
    # cov = vcal.get_Covar(a).values
    # c = vcal.calculate_CVaR(by = ['Traders', 'TraderMandate'], adjust = True)
    # d = vcal.calculate_CvarByFactors()
    # var = vcal.get_HistoricVaR('Risk')
    # limit = vcal._dfLimit
