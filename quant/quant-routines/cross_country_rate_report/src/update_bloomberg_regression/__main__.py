import pdblp
import os
import pandas as pd
import numpy as np

def main():
    input_path = '../../input/update_bloomberg_regression'
    output_path = '../../output/update_bloomberg_regression'
    date_d1 = pd.Timestamp.today() - pd.DateOffset(years=10)
    date_start =  pd.Timestamp( date_d1.strftime('%Y-%m-%d') )
    date_d2 = pd.Timestamp.today() - pd.DateOffset(days=1)
    date_end = pd.Timestamp( date_d2.strftime('%Y-%m-%d') )

    # Create output folder
    for folder in ['../../output', output_path]:
        if not os.path.exists(folder):
            os.makedirs(folder)

    # Create bloomberg connection
    bloomberg_connection = pdblp.BCon(
        debug=False, 
        port=8194, 
        timeout=30000
    )
    bloomberg_connection.start()

    # Read list of tickers
    ticker_table = pd.read_excel( 
        '%s/tickers.xlsx' % (input_path),
        index_col=0,
        sheet_name='bloomberg'
    )
    melted_ticker_table = pd.melt(
        ticker_table.drop(['Obs', 'Description', 'Bloomberg description'], axis=1),
    )
    tickers = melted_ticker_table['value'].dropna().unique()

    # Request data from bloomberg
    df = pd.DataFrame()
    for ticker_id, ticker in enumerate(tickers):
        print("%3d / %3d - %s" % (ticker_id, len(tickers), ticker), end=' ')
        data = bloomberg_connection.bdh(
            ticker, 
            'PX_LAST',
            date_start.strftime('%Y%m%d'), 
            date_end.strftime('%Y%m%d')
        )
        if len(data.index) == 0:
            print('[EMPTY]', end='')
            data = pd.DataFrame(columns=[ticker])
        data.columns = [ticker]    
        df = pd.concat([df, data], axis=1)
        print('')
    df.sort_index(inplace=True)
    
    # Request and update
    df.to_excel( '%s/data.xlsx' % (output_path) )


if __name__ == "__main__":
    main()
    