import pandas as pd
import QuantLib as ql
import numpy as np
import os
import sql

input_path = '../../output/1_export_focus_raw'
output_path = '../../output/2_process_focus'

# Create output folder
for folder in ['../../output', output_path]:
    if not os.path.exists(folder):
        os.makedirs(folder)

print('Getting focus 6M 1Y 18M 2Y 5Y')
sql_connection = sql.SQLConnection()
focus = sql_connection.read_focus()
print(focus)
focus.to_excel('%s/focus.xlsx' % output_path)
