import pandas as pd
import numpy as np

def get_stats(df):
    p05 = df.quantile(q=0.05, axis = 0)
    p95 = df.quantile(q=0.95, axis = 0)
    stat = {}
    time = pd.Series(df.iloc[-1].name, index=df.columns)
    stat['min'] = df[ df <= p05 ].mean()
    stat['max'] = df[ df >= p95 ].mean()
    stat['median'] = df.median()
    stat['mean'] = df.mean()
    stat['std'] = df.std()
    stat['last_t'] = time
    stat['last_x'] = df.iloc[-1]
    return stat

def calculate_all(df):
    # for column in df:
    stat = {}
    stat['all'] = get_stats( df )
    stat['hike'] = get_stats( df[ df['Copom flag'] == 1 ] )
    stat['manut'] = get_stats( df[ df['Copom flag'] == 0 ] )
    stat['cut'] = get_stats( df[ df['Copom flag'] == -1 ] )
    return stat

    
def export_stat(stats, output, index_dict, column_dict):
    df = pd.DataFrame(
        columns = list(column_dict.keys()),
        index = list(index_dict.keys()),
        dtype='object'
    )

    
    for column in df.columns:
        for index in df.index:
            selector_0 = column_dict[column][0]
            selector_1 = column_dict[column][1]
            df.loc[index, column] = stats[selector_0][index_dict[index]][selector_1]

    # Create a Pandas Excel writer using XlsxWriter as the engine.
    with pd.ExcelWriter(
        output,
        engine='xlsxwriter',
        datetime_format='dd/mm/yyyy',
        date_format='dd/mm/yyyy',
    ) as writer:
        df.to_excel(writer, sheet_name='Sheet1', index = True, header=True)

        workbook  = writer.book
        worksheet = writer.sheets['Sheet1']

        general_format = workbook.add_format({
            'num_format': '0'
        })

        worksheet.set_column('A:A', 15, general_format)
        worksheet.set_column('B:M', 10, general_format)