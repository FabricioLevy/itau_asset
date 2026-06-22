import pandas as pd
import numpy as np
import scipy.optimize
import scipy.stats as stats

class PeakOverThreshold:
    
    def __init__(self, series, series_id=None, threshold_pct=95):
        if isinstance(series, pd.DataFrame):
            self.series_id = series.columns[0] if series_id==None else series_id
            series = series[self.series_id]
        elif isinstance(series, pd.Series):
            self.series_id = series.name if series_id==None else series_id          
        elif isinstance(series, np.ndarray):
            self.series_id = 'unamed' if series_id==None else series_id  
        else:
            raise Exception('series must be of types np.array, pd.Series or pd.DataFrame!')
        self.dfRet = pd.DataFrame(series, columns=[self.series_id])
        self.threshold = threshold_pct
        
        self.dfRet['Losses'] = abs(self.dfRet[self.series_id][self.dfRet[self.series_id] <= 0])
        self._u = np.percentile(self.dfRet['Losses'].fillna(0), self.threshold)
        self.dfRet['Exceedances'] = self.dfRet['Losses'][self.dfRet['Losses'] > self._u]
        self._Fu = self.dfRet['Exceedances'].count() / self.dfRet[self.series_id].count()
    
    def __invFunc(self, y, f):
        func_inv = scipy.optimize.fmin(func=lambda x: abs(f(x) - y),
                                       x0=0.5, 
                                       xtol=0.000001,
                                       ftol=0.000001,
                                       disp=False)
        return func_inv[0]
    
    def fit(self):
        (c, loc, scale) = stats.genpareto.fit(self.dfRet['Exceedances'].dropna().values, 
                                              loc=self._u)
        self._gp = stats.genpareto(c, loc, scale)     
     
    def func_eva(self, q):
        F = lambda x: self._Fu * (1 - self._gp.cdf(x))
        return self.__invFunc(q, F) + self._u
    
    def to_dataframe(self):
        return self.dfRet.copy()
    
    def __repr__(self):
        return f"EVA: {len(self.dfRet):1,.0f} data points "
    

#%%
if __name__ == "__main__":
    
    pass
    
    