import pandas as pd
import numpy as np
from date_utils import business_days

def generate_copom_trajectory(current_dates, current_data, month_map, date_dict):
    aux = pd.DataFrame()
    aux['month'] = current_dates
    aux['date_effective'] = [ 
        (
            month_map.loc[x, 'date_effective'] 
            if (x in month_map.index) 
            else pd.NA
        )
        for x 
        in current_dates 
    ]
    aux['copom'] = current_data
    aux['missing_copom'] = False
    for index in aux.index[1:]:
        if (
            ( aux.loc[index, 'date_effective'] is pd.NA ) &
            ( aux.loc[index-1, 'copom'] == aux.loc[index, 'copom'] )
        ):
            aux.loc[index, 'missing_copom'] = True
    aux.sort_values('month', inplace=True)
    aux.ffill(inplace=True)

    # Count the number of days in each focus level
    for selector in ['6M', '1Y', '2Y', '5Y']:
        aux.loc[aux.index[0], selector] =  business_days(
            aux.loc[aux.index[0], 'month'],
            aux.loc[aux.index[1], 'date_effective']
        )
        for i in range( 1, len(aux.index)-1 ):
            if (aux.loc[aux.index[i+1], 'date_effective'] > date_dict.loc[selector, 0]):
                break
            aux.loc[aux.index[i], selector] =  business_days(
                aux.loc[aux.index[i], 'date_effective'],
                aux.loc[aux.index[i+1], 'date_effective']
            )
        aux.loc[ aux.index[i], selector] =  business_days(
            aux.loc[ aux.index[i], 'date_effective' ],
            date_dict.loc[selector, 0]
        )
    aux.fillna(0, inplace=True)
    return aux

def get_current_focus(copom_trajectory):
    current_focus = []
    for selector in ['6M', '1Y', '2Y', '5Y']:
        current_focus.append(
            (
                np.exp(
                    copom_trajectory[selector].multiply( 
                        np.log( 1 + copom_trajectory['copom'] / 100 )
                    ).sum() / copom_trajectory[selector].sum()
                ) - 1
            ) * 100
        )
    return current_focus