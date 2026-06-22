import pandas as pd
import networkx as nx
import yaml
import datetime
import sqlalchemy as sa
import os 
import urllib.parse
import QuantLib as ql
from matplotlib import font_manager as fm


# last_stops = {'GB':datetime.date(2022,1,17),
#               'TO':datetime.date(2021,8,16),
#               'FK':datetime.date(2021,10,26)}

date_ini = {'A1 Master FIM':datetime.date(2020, 4, 1),
            'A1 Orange FIM':datetime.date(2021, 3, 15),
            'A1 FIFE BEM':datetime.date(2021, 9, 3),
            'A1 FIFE ITAU': datetime.date(2022,3,31)}

color_palette =['#323E48','#28829B','#C9CBCB', 'dodgerblue','royalblue', 'mediumaquamarine', \
                 'slateblue', 'c', 'slategrey',\
                '#748D9E', '#2E9AB2',\
                'silver', 'lightgrey']
#%%
font_prop = fm.FontProperties(fname="FontsFree-Net-AmpleSoftPro.ttf")

#%%
class Node(object):
    def __init__(self, data, dfTree):
        self.data = data
        self.children = []
        dfTemp = dfTree[dfTree['parent_node']==data]['node'].unique()
        # if len(dfTemp) == 0:
        for leaf in dfTree[dfTree['node']==data]['book']:
            if (leaf!=''):
                new_nd = Node(leaf, dfTree)
                self.children.append(new_nd)
        else:
            for nd in dfTemp:
                new_nd = Node(nd, dfTree)
                self.children.append(new_nd)
    
    def get_all_leaves(self):
        leaves = []
        for nd in self.children:
            if len(nd.children) == 0:
                leaves.append(nd.data)
            else:
                leaves += nd.get_all_leaves()
        return leaves
    
    def to_dict(self, str_node):
        dic = {}
        #to implement: search node method
        if self.data == str_node:
            for nd in self.children:
                dic[nd.data] = nd.get_all_leaves()
        return dic
    
    def to_inv_dict(self, str_node):
        dic = {}
        #to implement: search node method
        if self.data == str_node:
            for nd in self.children:
                for i in nd.get_all_leaves():
                    dic[i] = nd.data
        return dic      
    
    def __create_graph(self, nxDG):
        for child in self.children:
            nxDG.add_edge(self.data, child.data)
            child.__create_graph(nxDG)

    def get_graph(self, books=[]):
        DG = nx.DiGraph()
        self.__create_graph(DG)
        if len(books) > 0:
            paths = set([])
            for b in books:
                paths.update(nx.shortest_path(DG, self.data, b))
            for node in list(DG.nodes()):
                if node not in paths:
                    DG.remove_node(node)        
        return DG

    def __str__(self):
        return str(self.data) +  ','.join(['\n' + str(c) for c in self.children])

#%%
def get_last_stop(dt, trader, str_fund='A1 Master FIM'):    
    _, connection = get_DB_conn('DB_USER')
    str_sql =   f""" 
       SELECT max([date_reference]) as last_stop
          FROM [risk].[trader_limit_breach]
          WHERE trader_id = '{trader}'
              AND measure = 'STOP'
              AND date_reference <= '{dt:%Y-%m-%d}'
        """
    last_stop = pd.read_sql(str_sql, connection)['last_stop'].iloc[-1]
    return last_stop if last_stop!=None else date_ini[str_fund]


#%%
def get_PeriodToDate(dt):
    mtd = ql.Brazil().endOfMonth(ql.Brazil().advance(ql.Date(1, dt.month, dt.year), ql.Period('-1d'))).to_date()
    aux_dt = ql.Brazil().advance(ql.Date.from_date(dt), ql.Period('-6m'))
    if ql.Date.from_date(dt).month() in [6,7,8,9,10,11]:
        std = ql.Brazil().endOfMonth(ql.Date(1,5,dt.year)).to_date()
    else:
        std = ql.Brazil().endOfMonth(ql.Date(1,11,aux_dt.year())).to_date()        
    return [mtd, std]

#%%
def get_endOfMonths(dt, dt_start=datetime.date(2020,4,1), flag_price=True):
    schedule = ql.Schedule(ql.Date.from_date(dt_start), 
                           ql.Brazil().endOfMonth(ql.Date.from_date(dt)), 
                           ql.Period('1M'), 
                           ql.Brazil(),
                           ql.ModifiedPreceding, 
                           ql.ModifiedPreceding, 
                           ql.DateGeneration.Backward, 
                           True)
    eom_dates = [dt_start]+[i.to_date() if i.to_date()<dt else dt for i in schedule]
    del schedule
    dic_eom = {}
    for dt1, dt2 in zip(eom_dates, eom_dates[1:]):
        dic_eom[dt2] = (dt1 if flag_price else datetime.date(dt2.year, dt2.month, 1), dt2)
    return dic_eom
#%%
def get_DB_conn(environment='PROD'):
    
    if environment.upper() == 'PROD':
        engine = sa.create_engine('mssql+pyodbc://saprod:nhjmmn&^Yh%%^yhjU&@srvprod1.database.windows.net,1433/dbprod1?driver=SQL+Server+Native+Client+11.0')
        conn = engine.connect()
    elif environment.upper() in ['UAT', 'TEST']:
        engine = sa.create_engine('mssql+pyodbc://sadr:798ujHYu&*uJHy676ytyhgTYU^&&@srvdbteste01.database.windows.net,1433/dbteste01?driver=SQL+Server+Native+Client+11.0')
        conn = engine.connect()
    elif environment.upper() == 'DB_USER':
        server = 'srvprod1.database.windows.net'
        port= 1433
        database = 'dbprod1'
        uid = urllib.parse.quote(os.environ.get('DB_USER'))
        pwd = urllib.parse.quote(os.environ.get('DB_PASS'))        
        engine = sa.create_engine(f"mssql+pyodbc://{uid}:{pwd}@{server},{port}/{database}"
                                  "?driver=ODBC+Driver+17+for+SQL+Server"
                                  "&authentication=ActiveDirectoryPassword")        
        conn = engine.connect()        
        
    else:
        return False
    
    return engine, conn

#%%
def get_DailyRiskShare(dt, str_fund, measure='risk_share', adjShare=False):
    _, connection = get_DB_conn('DB_USER')
    
    str_sql =   """ 
        SELECT [date_reference],[trader_id],[value] as risk_share
        FROM [risk].[trader_risk_share]
        WHERE trading_desk = '{}' AND measure = '{}'
        """
    str_sql = str_sql.format(str_fund, measure)
    df = pd.read_sql(str_sql, connection)
    dfShare = df.pivot(index='date_reference', columns='trader_id', values='risk_share').fillna(method='ffill').fillna(0)
    dt_ini = dfShare.index[0]
    dts = [i.to_pydatetime().date() for i in pd.date_range(dt_ini, dt, freq='d') if not ql.Brazil().isHoliday(ql.Date.from_date(i.to_pydatetime()))]
    dfDailyShare = pd.DataFrame(index=dts)
    dfDailyShare = dfDailyShare.join(dfShare).fillna(method='ffill')
    if adjShare:
        dfDailyShare = dfDailyShare.div(dfDailyShare.drop('Fund', axis=1).sum(axis=1), axis=0)
        dfDailyShare['Fund'] = 1

    return dfDailyShare

#%%
def get_RiskLimits(dt, str_fund):
    _, connection = get_DB_conn('DB_USER')
    
    str_sql =   """ 
        SELECT [date_reference],[trader_id],measure,[value] 
        FROM [risk].[trader_risk_share]
        WHERE measure in ('var_limit', 'stress_limit', 'risk_share')
            and trading_desk = '{}'
        """
    str_sql = str_sql.format(str_fund, dt)
    df = pd.read_sql(str_sql, connection)
    dfShare = df.pivot(index='date_reference', 
                       columns=['trader_id', 'measure'], 
                       values='value').fillna(method='ffill').fillna(0)
    dfShare = dfShare.loc[:dt]
    dic_limit = {}
    
    dfAux = dfShare[dfShare.columns[dfShare.columns.get_level_values(1) == 'risk_share']].iloc[-1]
    
    traders = dfAux[dfAux>0].sort_values(ascending=False).index.get_level_values(0)
    
    for t in traders:
        var = dfShare.iloc[-1].loc[(t,'var_limit')]
        stress = dfShare.iloc[-1].loc[(t,'stress_limit')]
        share = dfShare.iloc[-1].loc[(t,'risk_share')]
        dic_limit[t] = (var, stress, share)
    
    return dic_limit

#%%
def get_traders(dt):
    _, connection = get_DB_conn('DB_USER')
    
    str_sql =  f""" 
        SELECT [trader_id],[trader_name]
        FROM [risk].[trader]
        WHERE ((date_end is null) or (date_end > '{dt:%Y-%m-%d}')) 
            and date_start<'{dt:%Y-%m-%d}'
        ORDER BY ordering
        """
    df = pd.read_sql(str_sql, connection, index_col='trader_id')
    return df['trader_name'].to_dict()
#%%
def get_NAV(dt, str_fund):
    
    _, connection = get_DB_conn('prod')
    
    str_sql = "SELECT n.NAV "+\
              " FROM [middle].[NAV] n "+\
              " WHERE [trading_desk] = '{}'".format(str_fund)+\
              " AND n.date_reference = '{:%Y-%m-%d}'".format(dt)    
    df = pd.read_sql(str_sql, connection)
    connection.close()
    del str_sql
    if len(df) != 1:
        raise Exception("NAV not found for '{}' on date {:%d-%b-%Y}".format(str_fund, dt))
    
    return float(df.values)
#%%
def get_NAV_test(dt, str_fund):
    
    _, connection = get_DB_conn('test')
    
    str_sql = "SELECT n.NAV "+\
              " FROM [lote45].[NAV] n "+\
              " WHERE [TradingDesk] = '{}'".format(str_fund)+\
              " AND n.ValDate = '{:%Y-%m-%d}'".format(dt)    
    df = pd.read_sql(str_sql, connection)
    connection.close()
    del str_sql
    
    return float(df.values)

#%%
def get_config(args=[]):
    
    path_config = os.path.expanduser('~\\Documents\\Github\\risk_report\\config')
    
    with open(path_config + '/report.config', 'r') as f:
        d = yaml.full_load(f)
        
    if args:
        if type(args) == str:
            ret_value = d.get(args, None)
        else:
            ret_value =  [d.get(i, None) for i in args]
    else:
        ret_value =  d
        
    return ret_value


#%%
if __name__ == "__main__":
    
    dt = datetime.date(2022, 8, 5)
    str_fund = 'A1 Master FIM'
    

    
    # d1 = get_endOfMonths(dt)
    # d2 = get_endOfMonths(dt, flag_price=False)
    # dic_limits = get_RiskLimits(dt, str_fund)
    # dfRiskShare = get_DailyRiskShare(dt, str_fund, adjShare=False)
    
    # dfRiskShare = dfRiskShare.loc[datetime.date(2021, 12, 1):]
    
    # print(get_traders(dt))
    
    # try:
    #     nav=get_NAV(dt, str_fund)
    # except Exception as err:
    #     print("ERROR: {}".format(err))
    
    # _, connection = get_DB_conn()
    # str_tree = 'Traders'
    # str_sql = """
    #         SELECT [parent_tree],[parent_node],[node],[book]
    #         FROM [lote45].[book_tree]
    #         WHERE parent_tree = '{}'
    #                 """
    # dfTree = pd.read_sql(str_sql.format(str_tree), connection)
    # nd = Node(str_tree, dfTree)    
    # dic_books = nd.to_inv_dict(str_tree)   
    # dic_book2 = nd.to_dict(str_tree)   
