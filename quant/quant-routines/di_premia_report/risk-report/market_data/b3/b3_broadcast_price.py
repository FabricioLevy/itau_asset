import pandas as pd
import numpy as np
import datetime
import xlwings as xw

from a1db.a1sql import SQLConnection
    
#%%
def write_excel_file (dt, lote45_products, str_file="b3_broadcast.xlsx"):
    
    connection = SQLConnection().get_connection()
        
    str_sql = """
                 SELECT lote45_product_class as prod_type, [id] as prod_id
                 FROM [middle].[product]
                 WHERE lote45_product_class IN ('{}')
                       AND date_maturity >= '{:%Y-%m-%d}'
                 ORDER BY lote45_product_class, date_maturity
            """
    str_sql = str_sql.format("','".join(lote45_products), dt)
    df = pd.read_sql(str_sql, connection)
    
    #%%
    broadcast_fields = ['DAJ', 'AJUT', 'AJU', 'CAB', 'CNG', 'NEG']
    format_fields = ['dd-mmm-yy', 'General', 'General','General','General','General']
    
    excel_file = xw.Book(str_file)
    excel_file.app.api.RegisterXLL(r"C:\Program Files (x86)\AE Broadcast\Broadcast.AddIn.xll")
    excel_file.app.calculate()
    sheet_names = [i.name for i in excel_file.sheets]    

    for prod_type in lote45_products:
        if prod_type not in sheet_names:
            excel_file.sheets.add(prod_type)
        else:
            excel_file.sheets[prod_type].clear()
        excel_file.sheets[prod_type].cells(1, 1).value = ['Ativo'] + broadcast_fields
        first_row = 2
        for i, (_, prod_id) in enumerate(df[df['prod_type'] == prod_type].values):
            prod_address = excel_file.sheets[prod_type].cells(first_row + i, 1).get_address()
            excel_file.sheets[prod_type].range(prod_address).value = prod_id
            for j, (f, num_format) in enumerate(zip(broadcast_fields, format_fields)):
                excel_file.sheets[prod_type].cells(first_row + i, 2+j).formula = '=BC({},"{}")'.format(prod_address, f)
                excel_file.sheets[prod_type].cells(first_row + i, 2+j).number_format = num_format
        excel_file.app.calculate()
    excel_file.save()
    # excel_file.close()            

#%%
def excel2SQL(dt, lote45_products, str_file="b3_broadcast.xlsx", onlyCNG = True):
    
    connection = SQLConnection().get_connection()
   
    for prod_type in lote45_products:
        dfTemp = pd.read_excel(str_file, sheet_name=prod_type, parse_dates=[1])
        dfTemp = dfTemp[dfTemp['DAJ']==pd.Timestamp(dt)]
        for (prod_id, dtref, rate, price, cab, cng, neg) in dfTemp.values:    
            if not onlyCNG:
                ## settle price #######################
                rate = price if np.isnan(rate) else (rate / 100) if prod_type in ['DDI Future', 'DI1Future', 'DAP Future'] else rate
                str_sql = """
                        SELECT *  FROM [middle].[product_price]
                        WHERE date_reference = '{:%Y-%m-%d}' AND product_id ='{}'
                        """
                str_sql = str_sql.format(dtref, prod_id)
                df = pd.read_sql(str_sql, connection)
                if len(df) == 0:
                    str_sql = """
                        INSERT INTO [middle].[product_price] (date_reference, product_id, rate, price)
                        VALUES ('{:%Y-%m-%d}', '{}', {}, {})
                        """
                    str_sql = str_sql.format(dtref, prod_id, rate, price)
                else:
                    str_sql = """
                        UPDATE [middle].[product_price]
                        SET rate = {}, price={}
                        WHERE date_reference = '{:%Y-%m-%d}' AND product_id ='{}'
                        """
                    str_sql = str_sql.format(rate, price, dtref, prod_id)
                print(str_sql)
                connection.execute(str_sql)
                ########################################
            
            ## contratos negociados ################ 
            cng = 0 if np.isnan(cng) else cng
            neg = 0 if np.isnan(neg) else neg            
            for str_sens, val_sens in zip(['qtde_negociada','num_negocios'],[cng, neg]):
                str_sql = """
                        SELECT *  FROM [risk].[product_sensitivity]
                        WHERE sensitivity = '{}' AND date_reference = '{:%Y-%m-%d}' AND product_id ='{}'
                        """
                str_sql = str_sql.format(str_sens, dtref, prod_id)
                df = pd.read_sql(str_sql, connection)
                if len(df) == 0:
                    str_sql = """
                        INSERT INTO [risk].[product_sensitivity] (date_reference, product_id, sensitivity, [value])
                        VALUES ('{:%Y-%m-%d}', '{}', '{}', {})
                        """
                    str_sql = str_sql.format(dtref, prod_id, str_sens, val_sens)
                else:
                    str_sql = """
                        UPDATE [risk].[product_sensitivity]
                        SET [value] = {}
                        WHERE sensitivity = '{}' AND date_reference = '{:%Y-%m-%d}' AND product_id ='{}'
                        """
                    str_sql = str_sql.format(val_sens, str_sens, dtref, prod_id)
                print(str_sql)
                connection.execute(str_sql)
            ########################################
            
    

#%%
if __name__ == "__main__":
    dt = datetime.date(2022, 3, 9)
    lote45_products = ['DDI Future', 'FRC', 'DI1Future', 'DAP Future', 'IBOVSPFuture', 'USDBRLFuture']
    str_file = "b3_broadcast.xlsx"
    # excel2SQL (dt, lote45_products, str_file, True)
    write_excel_file(dt, lote45_products)
