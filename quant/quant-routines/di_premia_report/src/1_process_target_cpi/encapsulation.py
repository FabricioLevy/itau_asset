import pandas as pd
import QuantLib as ql

def get_inflation(data, date):
    aux = data[ data['date_publish'] < date ]
    date_dict = {}
    for _, row in aux.iterrows():
        if row['date_reference'] in date_dict:
            if date_dict[ row['date_reference'] ] < row['date_publish'] :
                date_dict[ row['date_reference'] ] = row['date_publish']
        else:
            date_dict[ row['date_reference'] ] = row['date_publish']
    date_index_list = [
        (key, date_dict[key]) for key in date_dict
    ]
    aux = aux.set_index(['date_reference', 'date_publish'])
    aux = aux.loc[date_index_list].reset_index()
    aux = aux[['date_reference', 'rate_target', 'rate_tolerance', 'rate_realized']]
    return aux

def advance_business_days(d1, offset):
    calendar = ql.Brazil()
    return pd.Timestamp(
        calendar.advance(
            ql.Date(d1.day, d1.month, d1.year),
            ql.Period(offset, ql.Days), 
            ql.Following,
            False
        ).ISO()
    )

def get_business_days(d1, d2):
    calendar = ql.Brazil()
    return calendar.businessDaysBetween(
        ql.Date(d1.day, d1.month, d1.year), 
        ql.Date(d2.day, d2.month, d2.year),
        True, 
        False
    )

def get_12m_target_inflation(current_date, expectation_data):
    df = get_inflation(expectation_data, current_date)
    year_begin = (
        (current_date + pd.DateOffset(days=1)) 
        + pd.offsets.YearBegin(-1) 
    )
    df = df[ df['date_reference'] >= year_begin ]
    if len(df.index) == 1:
        return (
            df.iloc[0]['rate_target'], 
            df.iloc[0]['rate_target']+df.iloc[0]['rate_tolerance'],
            df.iloc[0]['rate_target']-df.iloc[0]['rate_tolerance']
        )
    current_year = (
        ( current_date + pd.DateOffset(days=-1) )
        + pd.offsets.YearEnd(1)
    )
    du1 = get_business_days( current_date, current_year )
    du2 = 252 - du1
    if du2 < 0:
        return (
            df.iloc[0]['rate_target'], 
            df.iloc[0]['rate_target']+df.iloc[0]['rate_tolerance'],
            df.iloc[0]['rate_target']-df.iloc[0]['rate_tolerance'],
        )
    r1 = ( 1 + df.iloc[0]['rate_target']/100 ) ** (du1/(du1+du2))
    r2 = ( 1 + df.iloc[1]['rate_target']/100 ) ** (du2/(du1+du2))
    t1_upper = ( 
        1  
        + df.iloc[0]['rate_target']/100
        + df.iloc[0]['rate_tolerance']/100 
    ) ** (du1/(du1+du2))
    t2_upper = ( 
        1 
        + df.iloc[1]['rate_target']/100
        + df.iloc[1]['rate_tolerance']/100 
    ) ** (du2/(du1+du2))
    t1_lower = ( 
        1  
        + df.iloc[0]['rate_target']/100
        - df.iloc[0]['rate_tolerance']/100 
    ) ** (du1/(du1+du2))
    t2_lower = ( 
        1 
        + df.iloc[1]['rate_target']/100
        - df.iloc[1]['rate_tolerance']/100 
    ) ** (du2/(du1+du2))
    return (
        round( ( (r1*r2) - 1 )*100, 2 ),
        round( ( (t1_upper*t2_upper) - 1 )*100, 2 ),
        round( ( (t1_lower*t2_lower) - 1 )*100, 2 ),
    )

def get_24m_target_inflation(current_date, expectation_data):
    df = get_inflation(expectation_data, current_date)
    year_begin = (
        (current_date + pd.DateOffset(days=1)) 
        + pd.offsets.YearBegin(-1) 
    )
    df = df[ df['date_reference'] >= year_begin ]
    if len(df.index) == 1:
        return (
            df.iloc[0]['rate_target'], 
            df.iloc[0]['rate_target'] + df.iloc[0]['rate_tolerance'],
            df.iloc[0]['rate_target'] - df.iloc[0]['rate_tolerance']
        )
    current_year = (
        ( current_date + pd.DateOffset(days=-1) )
        + pd.offsets.YearEnd(1)
    )
    du1 = get_business_days( current_date, current_year )
    if len(df.index) == 2: # only 2 years available
        r1 = ( 1 + df.iloc[0]['rate_target']/100 ) ** (du1/504)
        r2 = ( 1 + df.iloc[1]['rate_target']/100 ) ** ((504-du1)/504)        
        t1_upper = ( 
            1 
            + df.iloc[0]['rate_target']/100 
            + df.iloc[0]['rate_tolerance']/100 
        ) ** (du1/504)
        t2_upper = (
            1 
            + df.iloc[1]['rate_target']/100 
            + df.iloc[1]['rate_tolerance']/100 
        ) ** ((504-du1)/504)
        t1_lower = ( 
            1 
            + df.iloc[0]['rate_target']/100 
            - df.iloc[0]['rate_tolerance']/100 
        ) ** (du1/504)
        t2_lower = (
            1 
            + df.iloc[1]['rate_target']/100 
            - df.iloc[1]['rate_tolerance']/100 
        ) ** ((504-du1)/504)
        return (
            round( ( (r1*r2) - 1 )*100, 2 ),
            round( ( (t1_upper*t2_upper) - 1 )*100, 2 ),
            round( ( (t1_lower*t2_lower) - 1 )*100, 2 ),
        )
    else:
        du2 = 252
        du3 = 504 - du2 - du1
        r1 = ( 1 + df.iloc[0]['rate_target']/100 ) ** (du1/504)
        r2 = ( 1 + df.iloc[1]['rate_target']/100 ) ** (du2/504)        
        r3 = ( 1 + df.iloc[2]['rate_target']/100 ) ** (du3/504)        
        t1_upper = ( 
            1 
            + df.iloc[0]['rate_target']/100 
            + df.iloc[0]['rate_tolerance']/100 
        ) ** (du1/504)
        t2_upper = ( 
            1 
            + df.iloc[1]['rate_target']/100 
            + df.iloc[1]['rate_tolerance']/100 
        ) ** (du2/504)
        t3_upper = ( 
            1 
            + df.iloc[2]['rate_target']/100 
            + df.iloc[2]['rate_tolerance']/100 
        ) ** (du3/504)
        t1_lower = ( 
            1 
            + df.iloc[0]['rate_target']/100 
            - df.iloc[0]['rate_tolerance']/100 
        ) ** (du1/504)
        t2_lower = ( 
            1 
            + df.iloc[1]['rate_target']/100 
            - df.iloc[1]['rate_tolerance']/100 
        ) ** (du2/504)
        t3_lower = ( 
            1 
            + df.iloc[2]['rate_target']/100 
            - df.iloc[2]['rate_tolerance']/100 
        ) ** (du3/504)
        return (
            round( ( (r1*r2*r3) - 1 )*100, 2 ),
            round( ( (t1_upper*t2_upper*t3_upper) - 1 )*100, 2 ),
            round( ( (t1_lower*t2_lower*t3_lower) - 1 )*100, 2 )
        )

def get_target_inflation(current_date, expectation_data, n_days):
    df = get_inflation(expectation_data, current_date)
    year_begin = (
        (current_date + pd.DateOffset(days=1)) 
        + pd.offsets.YearBegin(-1) 
    )
    df = df[ df['date_reference'] >= year_begin ]
    if len(df.index) == 1:
        return (
            df.iloc[0]['rate_target'], 
            df.iloc[0]['rate_target'] + df.iloc[0]['rate_tolerance'],
            df.iloc[0]['rate_target'] - df.iloc[0]['rate_tolerance']
        )
    current_year = (
        ( current_date + pd.DateOffset(days=-1) )
        + pd.offsets.YearEnd(1)
    )
    cummulative_r = 1
    cummulative_du = 0

    du = get_business_days( current_date, current_year )
    i = 0
    while True:
        if (
            (i != -1) &
            (cummulative_du + du < n_days)
        ):
            cummulative_du += du
            cummulative_r *= (1+df.iloc[i]['rate_target']/100) ** (du/n_days)
            # print(current_date, i, du, df.iloc[i]['rate_target'], cummulative_r)
            # input() 
        else:
            du = n_days - cummulative_du
            cummulative_du += du
            cummulative_r *= (1+df.iloc[i]['rate_target']/100) ** (du/n_days)
            # print(current_date, i, du, df.iloc[i]['rate_target'], cummulative_r)
            # input()  
            break
        i += 1
        if i >= len(df.index):
            i = -1
        du = 252
    result = round( ( cummulative_r - 1 )*100, 2 )
    return result, result, result