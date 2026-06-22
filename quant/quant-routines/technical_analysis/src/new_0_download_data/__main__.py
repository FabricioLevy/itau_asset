import pandas as pd
import sql
import os
import QuantLib as ql

def main():
    # Configuration
    CALENDAR = ql.Brazil()
    DATE_START = '2013-01-01'
    DATE_END = CALENDAR.advance(
        ql.Date.todaysDate(),
        ql.Period('-2d'),
        ql.Preceding
    ).ISO()
    OUTPUT_PATH = '../../output/new_0_download_data'

    # Create output path
    os.makedirs(OUTPUT_PATH, exist_ok=True)

    # Read data
    sql_connection = sql.SqlClass()
    print('Read asset info')
    fund_info_df = sql_connection.read_assets(use_fic=True)

    # Product data
    print("Reading product data")
    cpnj_list = fund_info_df['cnpj_master'].values.tolist()
    data_df = pd.concat(
        [
            sql_connection.read_asset_data(
                DATE_START, 
                DATE_END, 
                cpnj_list
            ),
            sql_connection.read_predi(DATE_START, DATE_END),
            sql_connection.read_other(DATE_START, DATE_END),
        ],
        axis=1 
    ).sort_index()
    print(fund_info_df)
    print(data_df)
    fund_info_df.to_excel('%s/fund_info.xlsx' % OUTPUT_PATH)
    fund_info_df.to_pickle('%s/fund_info.pkl' % OUTPUT_PATH)
    data_df.to_excel('%s/data.xlsx' % OUTPUT_PATH)
    data_df.to_pickle('%s/data.pkl' % OUTPUT_PATH)

if __name__ == '__main__':
    main()