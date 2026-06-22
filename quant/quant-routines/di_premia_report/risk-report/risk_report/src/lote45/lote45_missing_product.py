import pandas as pd
import datetime

from a1db.a1sql import SQLConnection

def main(dt) :
#%%
    connection = SQLConnection().get_connection()
    
    str_sql = """
            SELECT distinct [lote45_product_class], [lote45_product]
            FROM [lote45].[book_overview]
            WHERE date_reference = '{:%Y-%b-%d}'
                AND measure = 'Amount'
                AND lote45_product_class not in ('Cash', 'EquityLoan', 'Provisions and Costs')
    """
    str_sql = str_sql.format(dt)    
    dfLote45 = pd.read_sql(str_sql, connection, index_col='lote45_product')
    
    str_sql = """
    SELECT [id] as product_id,[lote45_product]
        FROM [middle].[product]
    """
    str_sql = str_sql.format(dt)    
    dfProd = pd.read_sql(str_sql, connection, index_col='lote45_product')
    
    dfLote45 = dfLote45.join(dfProd)
        
    prod_not_to_check = [
                          'Currencies Forward', 
                          'Currencies NDF', 
                          'TBILL',
                          # 'Currencies NDO', 
                          # 'Currencies Options'
                         ]
    
    
    dfCheck = dfLote45[dfLote45['product_id'].isna() & ~dfLote45['lote45_product_class'].isin(prod_not_to_check)]
    
    dic_prods = {}
    for key, value in dfCheck['lote45_product_class'].to_dict().items():
        dic_prods.setdefault(value, [])
        dic_prods[value].append(key)
    
    
    str_sql = """
    INSERT INTO [middle].[product] ([id],[product_type],[lote45_product],[lote45_product_class],[description],[date_maturity])
    SELECT distinct [lote45_product],'Compromissada' as product_type,[lote45_product],[lote45_product_class],
		[lote45_product],cast([value] as datetime) as date_maturity
        FROM [lote45].[book_overview]
        WHERE date_reference = '{:%Y-%b-%d}' 
        and lote45_product_class = 'Compromissada CDI' 
        and measure='ExpiryDate'
        and [lote45_product] in ('{}')
    """
    str_sql = str_sql.format(dt, "','".join([i for i in dfCheck.index]))
    
    
    
    if len(dfCheck) > 0:
        print("------")
        print("Faltam cadatrar os seguintes produtos na tabela middle.product:")
        print("\n".join([f"{dfCheck.loc[i,'lote45_product_class']:35}: {i}" for i in dfCheck.index]))
        print("------")
        ret = connection.execute(str_sql)
        print("Inserted {:2.0f} new 'Compromissada CDI'!".format(ret.rowcount))
    else:
        print("Sem produtos para cadastrar!\n")

    return dic_prods

#%%
if __name__ == "__main__":
    dt = datetime.date(2022, 6, 8)
    main(dt)