# pylint: disable=abstract-class-instantiated
import pandas as pd
import os

def main():
    # Configuration
    bloomberg_path = '../../output/0_update_data/bloomberg.xlsx'
    focus_path = '../../output/2_process_focus/focus.xlsx'
    copom_path = '../../output/4_export_hike_corte/hike_corte.xlsx'
    target_cpi_path = '../../output/1_process_target_cpi/brl_cpi_target.xlsx'
    output_path = '../../output/5_export_premia'
   
    # Create output folder
    for folder in ['../../output', output_path]:
        if not os.path.exists(folder):
            os.makedirs(folder)

    # Read bloomberg
    bloomberg_df = pd.read_excel (bloomberg_path, header=0, index_col=0)

    # Read focus
    focus_df = pd.read_excel (focus_path, header=0, index_col=0)

    # Read copom
    # copom_df = pd.read_excel (copom_path, header=0, index_col=0)
    copom_df = pd.read_excel(copom_path, header=0)
    copom_df['date'] = pd.to_datetime(copom_df['date'])
    copom_df = copom_df.set_index('date')
    

    # Read cpi target
    target_cpi_df = pd.read_excel(target_cpi_path, header=0, index_col=0)
    target_cpi_df = target_cpi_df.reindex(bloomberg_df.index).ffill()

    # Extend focus date to match bloomberg date
    def extend_focus(focus, bloomberg_index):
        if len(bloomberg_index) == 0 or len(focus) == 0:
            return focus
        # Find last index where both dateindex match
        match_index = 0
        for index in range(-10,-1):
            bloomberg_date = bloomberg_index[index]
            focus_date = focus.index[-1]
            if bloomberg_date == focus_date: 
                match_index = index
                break

        if match_index > -1:
            # crop exceeding data
            focus = focus.truncate(
                after=bloomberg_index[-1],
                copy=False,
                axis=0,
            )
        else:
            # copy last values
            last_focus_row = focus.iloc[-1]
            for index in range( match_index+1, 0 ):
                focus.loc[bloomberg_index[index]] = last_focus_row
        return focus
    focus_df = extend_focus(focus_df, bloomberg_df.index)

    # Calculate premia
    gap_selic = bloomberg_df['gap selic'].rolling(window=21).mean().bfill()
    premia = pd.DataFrame()
    premia['6M'] = ( bloomberg_df['PREDI180 Index'] - focus_df['6M'] + gap_selic ) * 100
    premia['1Y'] = ( bloomberg_df['PREDI360 Index'] - focus_df['1Y'] + gap_selic ) * 100
    premia['18M'] = ( bloomberg_df['PREDI540 Index'] - focus_df['18M'] + gap_selic ) * 100
    premia['2Y'] = ( bloomberg_df['PREDI720 Index'] - focus_df['2Y'] + gap_selic ) * 100
    premia['5Y'] = ( bloomberg_df['PRDI1800 Index'] - focus_df['5Y'] + gap_selic ) * 100
    premia['2Y-1Y'] = premia['2Y'] - premia['1Y']
    premia['5Y-2Y'] = premia['5Y'] - premia['2Y']
    dap_cols = ['DAPBEI6M', 'DAPBEI1Y', 'DAPBEI18M', 'DAPBEI2Y']
    has_dap = all(c in bloomberg_df.columns for c in dap_cols)
    if has_dap:
        premia['implicit_6m'] = ( bloomberg_df['DAPBEI6M'] - bloomberg_df['IPCA Focus 6m'] ) * 100
        premia['implicit_1y'] = ( bloomberg_df['DAPBEI1Y'] - bloomberg_df['IPCA Focus 1y'] ) * 100
        premia['implicit_18m'] = ( bloomberg_df['DAPBEI18M'] - bloomberg_df['IPCA Focus 18m'] ) * 100
        premia['implicit_2y'] = ( bloomberg_df['DAPBEI2Y'] - bloomberg_df['IPCA Focus 2y'] ) * 100
        premia['target_implicit_1y'] = ( bloomberg_df['DAPBEI1Y'] - target_cpi_df['Target inflation 12m'] ) * 100
        premia['target_implicit_2y'] = ( bloomberg_df['DAPBEI2Y'] - target_cpi_df['Target inflation 24m'] ) * 100
    else:
        print('Aviso: curvas DAP BEI ausentes — premia implícita não calculada.')
    premia['market_vs_realized_6m'] = (bloomberg_df['PREDI180 Index'] - bloomberg_df['CDI180'])*100
    premia['market_vs_realized_1y'] = (bloomberg_df['PREDI360 Index'] - bloomberg_df['CDI360'])*100
    premia['market_vs_realized_2y'] = (bloomberg_df['PREDI720 Index'] - bloomberg_df['CDI720'])*100
    premia['market_vs_realized_5y'] = (bloomberg_df['PRDI1800 Index'] - bloomberg_df['CDI1800'])*100
    premia['flat_6m-selic'] = (bloomberg_df['PREDI180 Index'] - bloomberg_df['BZSTSETA Index'])*100
    premia['flat_1y-selic'] = (bloomberg_df['PREDI360 Index'] - bloomberg_df['BZSTSETA Index'])*100
    premia['flat_2y-selic'] = (bloomberg_df['PREDI720 Index'] - bloomberg_df['BZSTSETA Index'])*100
    premia['flat_2y-1y'] = (bloomberg_df['PREDI720 Index'] - bloomberg_df['PREDI360 Index'])*100
    premia['flat_5y-2y'] = (bloomberg_df['PRDI1800 Index'] - bloomberg_df['PREDI720 Index'])*100
    premia['gap'] = gap_selic

    premia.dropna(inplace=True, how="all")

    # Calculate copom flag
    def add_copom_flag(df, copom):        
        copom_index = 1
        previous_copom = copom.index[0]
        current_copom = copom.index[1]

        while df.index[0] > current_copom:
            if copom_index == len(copom.index) - 1:
                break
            copom_index += 1
            previous_copom = current_copom
            current_copom = copom.index[copom_index]
            
        for date in df.index:
            while date > current_copom:
                if copom_index == len(copom.index) - 1:
                    break
                copom_index += 1
                previous_copom = current_copom
                current_copom = copom.index[copom_index]

            df.loc[date, 'Copom flag'] = copom['Flag'][current_copom]
    add_copom_flag(premia, copom_df)

    # Export data
    print('Exporting premia data to excel')
    with pd.ExcelWriter(
        '%s/premia.xlsx' % output_path,
        engine='xlsxwriter',
        datetime_format='dd/mm/yyyy',
        date_format='dd/mm/yyyy'
    ) as excel_writer:
        premia.to_excel(excel_writer, index=True)

if __name__ == '__main__':
    print('Exporting premia data')
    main()
