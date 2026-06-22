import pandas as pd
import datetime
import urllib

from a1db.a1sql import SQLConnection

#%%
def main (dt):
    #%%
    
    us_treasury_url = f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{dt:%Y}/all?type=daily_treasury_yield_curve&field_tdr_date_value={dt:%Y%m}&page&_format=csv"
    tsy_local = "R:/Risk/02_MarketData/USTreasury/"
    tsy_tit_file = f"{dt:%Y%m%d}.csv"
    
    try:
        urllib.request.urlretrieve(us_treasury_url, 
                                   tsy_local + tsy_tit_file)    
    except urllib.request.HTTPError as exception:
        print(f"!! Error in file: {__file__}")
        raise exception
        # return False
    
    dfUST = pd.read_csv(tsy_local + tsy_tit_file,
                        parse_dates=[0], 
                        index_col=0,
                        decimal=".")
    
    dfUST = dfUST.loc[dt.strftime('%Y-%m-%d')].melt(value_name='par_rate', 
                                                    var_name='tenor_maturity')
    dfUST['date_reference'] = dt
    
    dfUST = dfUST[['date_reference', 'tenor_maturity', 'par_rate']]
    
    connection = SQLConnection().get_connection()
    connection.execute(f"DELETE FROM  cme.treasury_par_yield_curve_rate WHERE date_reference = '{dt:%Y-%m-%d}'")
    dfUST.to_sql("treasury_par_yield_curve_rate", connection, schema='cme', if_exists='append', index=False)
    print('Download US Treasury - Inserted {} values for date {}'.format(len(dfUST), dt))
    

#%%    
if __name__ == "__main__":
    
    dt = datetime.date(2022, 9, 29)
    try:
        main(dt)
    except Exception as err:
        print(f"Did not work! {err=}")