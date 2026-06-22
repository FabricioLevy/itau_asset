import pandas as pd
from datetime import date
import os
import process
import matplotlib.pyplot as plt
import QuantLib as ql
import plot
import math
from excel_utils import inject_df_to_excel, excel_export_img
import shutil
import numpy as np

calendar = ql.Brazil()
# _______________________________________________________________________________________________
# Configuration

input_path = '../../output/0_download_data'
input_path_2 = '../../input/1_process'
output_path = '../../output/1_process'
output_path_2 = '../../output/1_process/funds'

# _______________________________________________________________________________________________
# Create output path

for folder in ['../../output', output_path, output_path_2]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# _______________________________________________________________________________________________
# Read data

print('Read data')
master_data = pd.read_excel('%s/master_data.xlsx' % input_path, index_col=0)
fic_data = pd.read_excel('%s/fic_data.xlsx' % input_path, index_col=0)
product_data = pd.read_excel('%s/product_data.xlsx' % input_path, index_col=0)
print(master_data)
print(product_data)

# Get dates
date_end = product_data.index[-1]
date_truncate = date_end + pd.tseries.offsets.YearBegin(-3)
date_d252 = date_end - pd.DateOffset(days=252)
date_truncate_2 = date_end - pd.DateOffset(days=252)

# _______________________________________________________________________________________________
# Asset returns and volatility

print('Get assets returns and volatility')
master_returns = master_data.pct_change()
fic_returns = fic_data.pct_change()
product_returns = product_data.pct_change()
product_returns['PREDI360 Index'] = product_data['PREDI360 Index'].diff()
product_returns['PREDI720 Index'] = product_data['PREDI720 Index'].diff()
asset_volatility = fic_returns.truncate(
    before=date_d252
).std().sort_index() * (252 ** .5) * 100

# _______________________________________________________________________________________________
# Return plot - Horizontal bar plot
for period, title_string, figure_name in [
    (5,'Última "semana"', '005du.png'),
    (21,'Último "mês"', '021du.png'),
    (126,'Últimos "6 meses"', '126du.png'),
    (252,'Últimos "12 meses"', '252du.png'),
]:
    aux_product_returns = product_data.pct_change(periods=period)
    aux_product_returns['PREDI360 Index'] = product_data['PREDI360 Index'].diff(periods=period)
    aux_product_returns['PREDI720 Index'] = product_data['PREDI720 Index'].diff(periods=period)
    plot.plot_return_horizontal_bar(
        master_data.pct_change(periods=period), 
        aux_product_returns, 
        title='%s - %d du\n(%s-%s)'% ( 
            title_string, 
            period,
            aux_product_returns.index[-period-1].strftime('%Y-%m-%d'), 
            aux_product_returns.index[-1].strftime('%Y-%m-%d')
        )
    )
    plt.savefig('%s/%s' % (output_path, figure_name))
    plt.close()

# _______________________________________________________________________________________________
# Calculate regression weights
print('Calculate regression weights')

def fill_and_rolling_mean(x):
    filler = pd.DataFrame()
    for column in x.columns:
        filler[column] = pd.Series([
            x[ column ].iloc[-1]
            for y 
            in range(15)
        ])
    x2 = pd.concat([ x, filler ]).rolling(30, center=True).mean()
    x2.drop( x2.tail(15).index, inplace=True )
    return x2
regression_result, regression_r2, regression_y, regression_y_2, regression_rmse = process.regression( master_data, product_data )

regression_result_rolling_mean = {}
for key in regression_result.keys():
    regression_result_rolling_mean[key] = fill_and_rolling_mean( regression_result[key] )
vol_adjusted_regression_result = {}

for key in regression_result:
    vol_adjusted_regression_result[key] = regression_result[key].copy()
    for column in vol_adjusted_regression_result[key]:
        # column = 'Kinea'
        # print(column)
        if asset_volatility[column] == 0:
            vol_adjusted_regression_result[key][column] = np.nan
        else:
            vol_adjusted_regression_result[key][column] *= 5 / asset_volatility[column]
        
mean_result = process.calculate_regression_mean( regression_result )
vol_adjusted_mean_result = process.calculate_regression_mean( vol_adjusted_regression_result )
rolling_mean_result = fill_and_rolling_mean( mean_result )
vol_adjusted_rolling_mean_result = fill_and_rolling_mean( vol_adjusted_mean_result )
regression_result_quantiles = {}
for key in regression_result.keys():
    regression_result_quantiles[key] = regression_result_rolling_mean[key].quantile(
        [.1, .25, .5, .75, .9], 
        axis=1
    ).transpose()

aux = regression_y_2.copy()
for column in aux.columns:
    aux[column] *= master_returns[column]
aux[ aux >= 0 ] = True
aux[ aux < 0 ] = False
aux = aux.apply(pd.value_counts, normalize=True, axis=1)

r2_aux = regression_r2.mean(axis=1, numeric_only=True).copy()
r2_aux.index = aux.index

plt.plot( r2_aux, color='cyan', label='Raw', linewidth=1)
plt.plot( r2_aux.rolling(15).mean(), color='blue', label='Moving average 15d')
plt.gca().set_facecolor((.8, .8, .8))
plt.ylabel('R2')
plt.grid()
plt.title('R2')
plt.legend()
plt.gcf().autofmt_xdate()
plt.savefig('%s/rolling_r2.png' % output_path)
plt.close()

plt.plot( r2_aux.truncate(date_truncate), color='cyan', label='Raw', linewidth=1)
plt.plot( r2_aux.rolling(15).mean().truncate(date_truncate), color='blue', label='Moving average 15d')
plt.gca().set_facecolor((.8, .8, .8))
plt.ylabel('R2')
plt.grid()
plt.title('R2')
plt.legend()
plt.gcf().autofmt_xdate()
plt.savefig('%s/rolling_r2_b.png' % output_path)
plt.close()

plt.plot( 100*aux[True], color='cyan', label='Raw', linewidth=1)
plt.plot( 100*aux.rolling(15).mean()[True], color='blue', label='Moving average 15d')
plt.gca().set_facecolor((.8, .8, .8))
plt.grid()
plt.legend()
plt.ylabel('%')
plt.title('Same sign %')
plt.gcf().autofmt_xdate()
plt.savefig('%s/same_sign.png' % output_path)
plt.close()

plt.plot( 100*aux[True].truncate(date_truncate), color='cyan', label='Raw', linewidth=1)
plt.plot( 100*aux.rolling(15).mean()[True].truncate(date_truncate), color='blue', label='Moving average 15d')
plt.gca().set_facecolor((.8, .8, .8))
plt.grid()
plt.legend()
plt.ylabel('%')
plt.title('Same sign %')
plt.gcf().autofmt_xdate()
plt.savefig('%s/same_sign_b.png' % output_path)
plt.close()

# _______________________________________________________________________________________________
# Compile results into a table
compiled_result = pd.DataFrame()
compiled_result['Return (D-2)'] = master_returns.iloc[-1].sort_index()
compiled_result['Projected (D-3)'] = regression_y_2.iloc[-1]
compiled_result['Regression R2'] = regression_r2.iloc[-1]
compiled_result['Regression R2'] = [(round(x * 100) / 100 if not math.isnan(x) else math.nan)for x in compiled_result['Regression R2']]
compiled_result['PRE 2Y'] = regression_result['PREDI720'].iloc[-1]
compiled_result['USDBRL'] = regression_result['USDBRL'].iloc[-1]
compiled_result['IBOV'] = regression_result['IBOV'].iloc[-1]
compiled_result['S&P'] = regression_result['SPX'].iloc[-1]
compiled_result.index.name = regression_result['PREDI720'].iloc[-1].name.strftime('%Y-%m-%d')
product_return_table = pd.DataFrame()
product_return_table['Pre 2Y (bps)'] = pd.Series( (product_data['PREDI720 Index'].iloc[-1] - product_data['PREDI720 Index'].iloc[-2]) * 100 )
product_return_table['USDBRL'] = pd.Series( product_returns.iloc[-1]['USDBRL Curncy'] )
product_return_table['IBovespa'] = pd.Series( product_returns.iloc[-1]['IBOV Index'] )
product_return_table['S&P'] = pd.Series( product_returns.iloc[-1]['SPX Index'] )
product_return_table = product_return_table.transpose()

# Export table images
shutil.copyfile(
    '%s/template.xlsx' % input_path_2,
    '%s/compiled_result.xlsx' % output_path, 
)
inject_df_to_excel(
    compiled_result, 
    '%s/compiled_result.xlsx' % output_path, 
    position=(2,1), 
    sheet_name='Sheet1',
    include_index=True
)
inject_df_to_excel(
    pd.DataFrame([[date_end.strftime('%Y-%m-%d')]], columns=['Date']), 
    '%s/compiled_result.xlsx' % output_path, 
    position=(1,1), 
    sheet_name='Sheet1',
    include_index=False
)

len_end = len(compiled_result['USDBRL'].index) + 2

excel_export_img(
    '%s/compiled_result.xlsx' % output_path, 
    '%s/compiled_result.png' % output_path, 
    'Sheet1',
    [2,2], #initial row, col
    [len_end,9] #final row, col

)



shutil.copyfile(
    '%s/template_2.xlsx' % input_path_2,
    '%s/compiled_result_2.xlsx' % output_path, 
)
inject_df_to_excel(
    product_return_table, 
    '%s/compiled_result_2.xlsx' % output_path, 
    position=(2,1), 
    sheet_name='Sheet1',
    include_index=True
)

excel_export_img(
    '%s/compiled_result_2.xlsx' % output_path, 
    '%s/compiled_result_2.png' % output_path, 
    'Sheet1', 
    [2,2], #initial row, col
    [6,3]  #final row, col
)

additional_info = process.get_additional_info(compiled_result)
shutil.copyfile(
    '%s/template_3.xlsx' % input_path_2,
    '%s/compiled_result_3.xlsx' % output_path, 
)
inject_df_to_excel(
    additional_info, 
    '%s/compiled_result_3.xlsx' % output_path, 
    position=(2,1), 
    sheet_name='Sheet1',
    include_index=True
)
excel_export_img(
    '%s/compiled_result_3.xlsx' % output_path, 
    '%s/compiled_result_3.png' % output_path, 
    'Sheet1', 
    [2,2], #initial row, col
    [5,3]  #final row, col
)
# _______________________________________________________________________________________________
# Mean Plots

for plot_config in [
    ('PREDI720', 'PRE 2Y (Aplicado < 0)'),
    ('USDBRL', 'USDBRL (Vendido em USD < 0)'),
    ('IBOV', 'IBOV'),
    ('SPX', 'S&P'),
]:
    plot_selector = plot_config[0]
    print('Plotting %s' % plot_selector)
    plot.plot( 
        mean_result[plot_selector], 
        rolling_mean_result[plot_selector],
        stats={
            'mean': mean_result[plot_selector].mean(),
            'std': mean_result[plot_selector].std(),
        },
        title='Exposição média - %s' % plot_config[1],
        quantiles=regression_result_quantiles[plot_selector]
    )
    plt.savefig('%s/%s_1.png' % (output_path, plot_selector))
    plt.close()
    plot.plot( 
        mean_result[plot_selector].truncate(before=date_truncate), 
        rolling_mean_result[plot_selector].truncate(before=date_truncate),
        stats={
            'mean': mean_result[plot_selector].truncate(before=date_truncate).mean(),
            'std': mean_result[plot_selector].truncate(before=date_truncate).std(),
        },
        title='Exposição média - %s' % plot_config[1],
        quantiles=regression_result_quantiles[plot_selector].truncate(before=date_truncate),
    )
    plt.savefig('%s/%s_1b.png' % (output_path, plot_selector))
    plt.close()
    plot.plot( 
        vol_adjusted_mean_result[plot_selector], 
        vol_adjusted_rolling_mean_result[plot_selector],
        stats={
            'mean': vol_adjusted_mean_result[plot_selector].mean(),
            'std': vol_adjusted_mean_result[plot_selector].std(),
        },
        title='Exposição média (vol adjusted) - %s' % plot_config[1],
        quantiles=regression_result_quantiles[plot_selector]
    )
    plt.savefig('%s/%s_2.png' % (output_path, plot_selector))
    plt.close()
    plot.plot( 
        vol_adjusted_mean_result[plot_selector].truncate(before=date_truncate), 
        vol_adjusted_rolling_mean_result[plot_selector].truncate(before=date_truncate),
        stats={
            'mean': vol_adjusted_mean_result[plot_selector].truncate(before=date_truncate).mean(),
            'std': vol_adjusted_mean_result[plot_selector].truncate(before=date_truncate).std(),
        },
        title='Exposição média (vol adjusted) - %s' % plot_config[1],
        quantiles=regression_result_quantiles[plot_selector].truncate(before=date_truncate),
    )
    plt.savefig('%s/%s_2b.png' % (output_path, plot_selector))
    plt.close()

# Fund plots
for fund in regression_result[plot_selector]:
    for plot_config in [
        ('PREDI720', 'PRE 2Y (Aplicado < 0)'),
        ('USDBRL', 'USDBRL (Vendido em USD < 0)'),
        ('IBOV', 'IBOV'),
        ('SPX', 'S&P'),
    ]:
        plot_selector = plot_config[0]
        print('Plotting %s %s' % (plot_selector, fund))
        plot.plot( 
            regression_result[plot_selector][fund], 
            fill_and_rolling_mean( 
                pd.DataFrame( regression_result[plot_selector][fund] ) 
            ),
            stats={
                'mean': regression_result[plot_selector][fund].mean(),
                'std': regression_result[plot_selector][fund].std(),
            },
            title='Exposição - %s' % plot_config[1]
        )
        plt.savefig('%s/%s_%s.png' % (output_path_2, plot_selector, fund.strip()))
        plt.close()
        
    print('Plotting %s %s' % ('R2', fund))
    aux_y1 = pd.DataFrame( regression_r2[fund].values, index=regression_result['PREDI720'][fund].index )
    plot.plot_r2( 
        aux_y1, 
        fill_and_rolling_mean( aux_y1 ),
        stats={
            'mean': aux_y1.mean(),
            'std': aux_y1.std(),
        },
        title='R2',
        ylabel='R2'
    )
    plt.savefig('%s/R2_%s.png' % (output_path_2, fund.strip()))
    plt.close()

    print('Plotting %s %s' % ('Return', fund))
    aux_y1 = pd.DataFrame( regression_y_2[fund]*100, index=regression_result['PREDI720'][fund].index )
    aux_y2 = pd.DataFrame( master_returns[fund]*100, index=regression_result['PREDI720'][fund].index )
    
    plt.figure()
    plt.subplots_adjust(wspace=0,hspace=.05)
    ax1 = plt.subplot(211)
    plt.plot( aux_y1.truncate(before=date_truncate_2), '--', label='Projetado**' )
    plt.plot( aux_y2.truncate(before=date_truncate_2), '-', label='Realizado' )
    plt.legend()
    plt.grid()
    plt.title('Retorno realizado vs projetado um dia a frente')
    plt.ylabel('Retorno (%)')
    plt.setp( ax1.get_xticklabels(), visible=False )

    ax2= plt.subplot(212, sharex=ax1)
    plt.plot( regression_rmse[fund].truncate(before=date_truncate_2)*100 )
    plt.grid()
    plt.ylabel('RMSE (%)')
    plt.gcf().autofmt_xdate()

    plt.savefig('%s/RETURN_%s.png' % (output_path_2, fund.strip()))
    plt.close()
    
print('')