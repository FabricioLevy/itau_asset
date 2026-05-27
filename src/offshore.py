import pandas as pd
import pyodbc
import os
import numpy as np
import datetime
import pathlib
from openpyxl import load_workbook
from pandas import ExcelWriter
import xlsxwriter


usernameSQL = os.environ.get('SQL_LOGIN')
passwordSQL = os.environ.get('SQL_PASSWORD')


def select_from_db(sSQL, usario, senha, base):
    conn = pyodbc.connect("DRIVER={SQL Server Native Client 11.0};"
                          "SERVER=SQNPRC028;"
                          "DATABASE=" + base + ";"
                          "UID=" + usario + ";"
                          "PWD=" + senha + "")
    sql_select = pd.read_sql_query(sSQL, conn)
    return sql_select


# Insert list of funds and date ref
# lista_fundos = ['ESP_INDIAGDFI','ESP_INDIAGD','ESP_OPPITUB','ESP_INDIAGDULT','ESP_PREVGDFIINDIA','ESP_GDFISIERRA','ESP_OSCARGDULT','ESP_GDFITANGO_B','ESP_TANGOGD_B','ESP_PREVGDFITANGO_B','ESP_SIERRAGD','ESP_PAPAGDULT','ESP_SIERRAGDULT','ESP_PREVGDFIPAPA','ESP_GDFIPAPA']
# lista_fundos = ['ESP_SIERRAGD','ESP_OSCARGDULT','ESP_PAPAGDULT']
# lista_fundos = ['ITAUGLMACROHE','ESP_MOPPGD','ESP_PREVGDFIMOPPHF','ESP_GDFIMOPP'] # YIELD PLUS
# lista_fundos = ['ESP_GDFITANGO_B','ESP_TANGOGD_B','ESP_PREVGDFITANGO_B'] # FUNDAMENTA
# lista_fundos = ['ESP_VICTORGD','ESP_PREVGDFIVICT'] # VICTOR
lista_fundos = ['ESP_INDIAGDFI','ESP_INDIAGD','ESP_OPPITUB','ESP_INDIAGDULT','ESP_PREVGDFIINDIA'] # INDIA
# lista_fundos = ['ESP_GDFIMOPP','ESP_MOPPGD','ESP_PREVGDFIMOPPHF','ITAUGLMACROHE','ESP_GDFISIERRA','ESP_PREVGDFIVICT','ESP_OSCARGDULT','ESP_VICTORGD','ESP_PREVGDFIVICT','ESP_GDFITANGO_B','ESP_TANGOGD_B','ESP_SIERRAGD']
lista_fundos = ['ESP_LIMAGD','ESP_FIOPTIMUS','ESP_ALVORADAFI','ESP_PREVGDFILIMA','ESP_OPTIMUSLB','ESP_OPTIMUS','ESP_BLUEGD','ESP_PREVGDFIBLUE','ESP_GDFIBLUE','ESP_ALLSEASONS','ESP_QUANT']
# lista_fundos = ['ESP_ALVORADAFI','ESP_PREVGDFIBLUE','ESP_BLUEGD','ESP_GDFIBLUE','ESP_ALLSEASONS','ESP_QUANT']
# lista_fundos = ['ESP_PREVGDFILIMA','ESP_LIMAGD','ESP_FIOPTIMUS','ESP_OPTIMUS']
# lista_fundos = ['ESP_GDFIPAPA','ESP_PAPAGD']
# lista_fundos = ['ESP_FIOPTIMUS']

base_table = 'SISTEMAS_SSC_PED_INTRADAY'

data_ref = '2025-08-11'
arred = 1

batimento_preco = True

ta_string = data_ref.replace('-', '')
fundo = [f"'{x}'" for x in lista_fundos]
fundo = ','.join(map(str, fundo))

de_para_dict = {
    'CSH': 'CaixaCPR',
    'PSEUDO': 'Despesa',
    'CASHEQ': 'Despesa',
    'EQYLST': 'Equity',
    'FXF': 'Future',
    'CMDFUT': 'Future',
    'CMDOPT': 'Option',
    'CNTOPT': 'Option',
    'CNTSWP': 'Swap',
    'CNTFRA': 'Swap',
    'CREDITDEFAULTSWAP': 'Swap',
    'EQITYSWP': 'Swap',
    'BNDSVN': 'Fixed Income',
    'BNDCRP': 'Fixed Income',
    'BNDTRS': 'Fixed Income',
    'EQYNLT': 'Equity',
    'BNDSWP': 'Swap',
    'COMPAP': 'Fixed Income',
}


# Total dif for each type
sSQL = f"""select date, codigo_IAM_fundo, Tipo, SUM(ISNULL(PnL_SSnC,0)) As PnL_SSnC
           from (
               SELECT PeriodEndDate As date, Fund As codigo_IAM_fundo,
                      case when InvAssetType = 'pseudo' and InvId like '%INT%' then 'CSH' else InvAssetType end As Tipo,
                      SUM(ISNULL(TotalBookPL,0)) As PnL_SSnC
               FROM {base_table} (NOLOCK)
               WHERE AccountingPeriod = 'DAILY' and Fund in ({fundo}) and PeriodEndDate = '{data_ref}'
               GROUP BY PeriodEndDate, Fund, InvAssetType, InvId
           ) as bla
           GROUP BY date, codigo_IAM_fundo, Tipo"""
Total_SSnC = select_from_db(sSQL, usernameSQL, passwordSQL, 'DBSX337')
Total_SSnC['Tipo'] = Total_SSnC['Tipo'].map(de_para_dict)
colunas = ['date', 'codigo_IAM_fundo', 'Tipo']
Total_SSnC = Total_SSnC.groupby(by=colunas, as_index=False, sort=False).agg({'PnL_SSnC': 'sum'})


sSQL = f"""SELECT date, codigo_IAM_fundo, Tipo, CONVERT(float,SUM(ISNULL(pnl_total,0))) As PnL_IAM
           FROM VW_FUNDOS_POSICAO (NOLOCK)
           WHERE codigo_IAM_fundo in ({fundo}) and date = '{data_ref}'
           GROUP BY date, codigo_IAM_fundo, Tipo"""
Total_IAM = select_from_db(sSQL, usernameSQL, passwordSQL, 'DBSX337')


# Get Equities dif
sSQL = f"""SELECT A.PeriodEndDate as date, A.InvAssetType As Tipo, A.Fund as codigo_IAM_fundo,
                  A.InvGFSDefined3 as codigo_IAM_ativo, B.valor_str As ticker_bolsa,
                  AVG(BegLocalMarketPrice) AS BegLocalMarketPrice, AVG(EndLocalMarketPrice) as EndLocalMarketPrice,
                  SUM(A.BegQty) As BegQty, SUM(A.EndQty) As EndQty, SUM(A.TotalBookPL) As TotalBookPL
           FROM {base_table} (NOLOCK) As A
           LEFT JOIN VIEW_FUNDOS_CADASTRO_ATIVOS_LAST_VALUES (NOLOCK) As B
               ON A.InvGFSDefined3 = B.codigo_IAM_ativo and B.campo = 'ticker_bolsa'
           WHERE InvAssetType in ('EQYLST','EQYNLT') and accountingPeriod = 'DAILY'
             and A.Fund in ({fundo}) and A.PeriodEndDate = '{data_ref}'
           GROUP BY A.accountingPeriod, A.PeriodEndDate, A.InvAssetType, A.Fund, A.InvGFSDefined3, B.valor_str"""
Acoes_SSnC = select_from_db(sSQL, usernameSQL, passwordSQL, 'DBSX337')
Acoes_SSnC['Tipo'] = Acoes_SSnC['Tipo'].map(de_para_dict)


sSQL = f"""SELECT date, codigo_IAM_fundo, codigo_IAM_ativo, ticker_bolsa,
                  avg(preco_limpo_d1) as preco_limpo_d1, avg(preco_limpo) as preco_limpo,
                  SUM(quantidade) As quantidade, SUM(pnl_total) As pnl_total
           FROM VW_FUNDOS_POSICAO (NOLOCK) As D
           WHERE tipo = 'Equity' and codigo_IAM_fundo in ({fundo}) and date = '{data_ref}'
           GROUP BY date, codigo_IAM_fundo, codigo_IAM_ativo, ticker_bolsa"""
Acoes_IAM = select_from_db(sSQL, usernameSQL, passwordSQL, 'DBSX337')


Dif_Acao = pd.merge(Acoes_SSnC, Acoes_IAM, how='outer',
                    on=['date', 'codigo_IAM_fundo', 'codigo_IAM_ativo'])
Dif_Acao['Tipo'] = 'Equity'
Dif_Acao['Ticker'] = Dif_Acao['ticker_bolsa_y']
Dif_Acao.loc[Dif_Acao['ticker_bolsa_y'].isnull(), 'Ticker'] = Dif_Acao['ticker_bolsa_x']
Dif_Acao = Dif_Acao.drop(['ticker_bolsa_x', 'ticker_bolsa_y'], axis=1)
Dif_Acao.fillna(0, inplace=True)

Dif_Acao['DifQtd'] = Dif_Acao['EndQty'] - Dif_Acao['quantidade']
Dif_Acao['DifPnL'] = Dif_Acao['TotalBookPL'] - Dif_Acao['pnl_total']
Dif_Acao = Dif_Acao.drop(Dif_Acao[(Dif_Acao['DifPnL'].abs() < arred)].index)
Dif_Acao['DifPnL'] = Dif_Acao['DifPnL'].round(0)


# Get Futures dif
sSQL = f"""SELECT date, Tipo, codigo_IAM_fundo, codigo_IAM_ativo, ticker_bolsa,
                  AVG(BegLocalMarketPrice) AS BegLocalMarketPrice, AVG(EndLocalMarketPrice) as EndLocalMarketPrice,
                  SUM(BegQty) As BegQty, SUM(EndQty) As EndQty, SUM(TotalBookPL) As TotalBookPL
           FROM (
               SELECT A.PeriodEndDate as date, A.InvAssetType As Tipo, A.Fund as codigo_IAM_fundo,
                      ISNULL(B.codigo_IAM_ativo, a.InvTicker) as codigo_IAM_ativo, B.valor_str as ticker_bolsa,
                      BegLocalMarketPrice, EndLocalMarketPrice, BegQty, EndQty, TotalBookPL
               FROM {base_table} (NOLOCK) as A
               LEFT JOIN VIEW_FUNDOS_CADASTRO_ATIVOS_LAST_VALUES (NOLOCK) as B
                   ON a.InvTicker = B.codigo_IAM_ativo and B.campo = 'ticker_bolsa'
               WHERE InvAssetType = 'CMDFUT' and accountingPeriod = 'DAILY'
                 and A.Fund in ({fundo}) and A.PeriodEndDate = '{data_ref}'
           ) As DF
           GROUP BY date, Tipo, codigo_IAM_fundo, codigo_IAM_ativo, ticker_bolsa"""
Fut_SSnC = select_from_db(sSQL, usernameSQL, passwordSQL, 'DBSX337')
Fut_SSnC['Tipo'] = Fut_SSnC['Tipo'].map(de_para_dict)


sSQL = f"""SELECT date, codigo_IAM_fundo, codigo_IAM_ativo, ticker_bolsa,
                  avg(preco_limpo_d1) as preco_limpo_d1, avg(preco_limpo) as preco_limpo,
                  SUM(quantidade) As quantidade, SUM(pnl_total) As pnl_total
           FROM VW_FUNDOS_POSICAO (NOLOCK) As D
           WHERE tipo = 'Future' and ativo <> 'NDF' and codigo_IAM_fundo in ({fundo}) and date = '{data_ref}'
           GROUP BY date, codigo_IAM_fundo, codigo_IAM_ativo, ticker_bolsa"""
Fut_IAM = select_from_db(sSQL, usernameSQL, passwordSQL, 'DBSX337')


Dif_Fut = pd.merge(Fut_SSnC, Fut_IAM, how='outer',
                   on=['date', 'codigo_IAM_fundo', 'codigo_IAM_ativo'])
Dif_Fut['Tipo'] = 'Future'
Dif_Fut['Ticker'] = Dif_Fut['ticker_bolsa_y']
Dif_Fut.loc[Dif_Fut['ticker_bolsa_y'].isnull(), 'Ticker'] = Dif_Fut['ticker_bolsa_x']
Dif_Fut = Dif_Fut.drop(['ticker_bolsa_x', 'ticker_bolsa_y'], axis=1)
Dif_Fut.fillna(0, inplace=True)

Dif_Fut['DifQtd'] = Dif_Fut['EndQty'] - Dif_Fut['quantidade']
Dif_Fut['DifPnL'] = Dif_Fut['TotalBookPL'] - Dif_Fut['pnl_total']
Dif_Fut = Dif_Fut.drop(Dif_Fut[(Dif_Fut['DifPnL'].abs() < arred)].index)
Dif_Fut['DifPnL'] = Dif_Fut['DifPnL'].round(0)


# Get Options dif
sSQL = f"""select a.PeriodEndDate as date, a.InvAssetType As Tipo, a.Fund as codigo_IAM_fundo,
                  isnull(a.InvTicker, c.codigo_IAM_ativo) as codigo_IAM_ativo,
                  isnull(b.valor_str, d.valor_str) as ticker_bolsa,
                  AVG(BegLocalMarketPrice) AS BegLocalMarketPrice, AVG(EndLocalMarketPrice) as EndLocalMarketPrice,
                  SUM(a.BegQty) As BegQty, SUM(a.EndQty) As EndQty, Sum(a.TotalBookPL) As TotalBookPL
           from {base_table} (NOLOCK) as a
           LEFT JOIN VIEW_FUNDOS_CADASTRO_ATIVOS_LAST_VALUES (NOLOCK) as b
               ON a.InvTicker = b.codigo_IAM_ativo and b.campo = 'ticker_bolsa'
           LEFT JOIN VIEW_FUNDOS_CADASTRO_ATIVOS_LAST_VALUES (NOLOCK) as c
               ON CONCAT(a.ExternalID2,'_',a.LongShortIndicator,'_',a.CounterPartyCode) = c.valor_str and c.campo = 'codigo_sistema'
           LEFT JOIN VIEW_FUNDOS_CADASTRO_ATIVOS_LAST_VALUES (NOLOCK) as d
               ON c.codigo_IAM_ativo = d.codigo_IAM_ativo and d.campo = 'ticker_bolsa'
           LEFT JOIN VIEW_FUNDOS_CADASTRO_ATIVOS_LAST_VALUES (NOLOCK) as e
               ON b.codigo_IAM_ativo = e.codigo_IAM_ativo and e.campo = 'ativo'
           LEFT JOIN VIEW_FUNDOS_CADASTRO_ATIVOS_LAST_VALUES (NOLOCK) as f
               ON c.codigo_IAM_ativo = f.codigo_IAM_ativo and f.campo = 'ativo'
           WHERE InvAssetType in ('CMDOPT') and AccountingPeriod = 'DAILY'
             and A.Fund in ({fundo}) and A.PeriodEndDate = '{data_ref}'
           GROUP BY a.PeriodEndDate, a.InvAssetType, a.Fund,
                    isnull(a.InvTicker, c.codigo_IAM_ativo), isnull(b.valor_str, d.valor_str)"""
Opt_SSnC = select_from_db(sSQL, usernameSQL, passwordSQL, 'DBSX337')
Opt_SSnC['Tipo'] = Opt_SSnC['Tipo'].map(de_para_dict)


sSQL = f"""SELECT date, codigo_IAM_fundo, codigo_IAM_ativo, ticker_bolsa,
                  avg(preco_limpo_d1) as preco_limpo_d1, avg(preco_limpo) as preco_limpo,
                  SUM(quantidade) As quantidade, SUM(pnl_total) As pnl_total
           FROM VW_FUNDOS_POSICAO (NOLOCK)
           WHERE tipo = 'Option' and codigo_IAM_fundo in ({fundo}) and date = '{data_ref}'
             and codigo_IAM_ativo not like 'FXO[_]%' AND codigo_IAM_ativo not like 'EQO[_]%'
           GROUP BY date, codigo_IAM_fundo, codigo_IAM_ativo, ticker_bolsa"""
Opt_IAM = select_from_db(sSQL, usernameSQL, passwordSQL, 'DBSX337')


Dif_Opt = pd.merge(Opt_SSnC, Opt_IAM, how='outer',
                   on=['date', 'codigo_IAM_fundo', 'codigo_IAM_ativo'])
Dif_Opt['Tipo'] = 'Options'
Dif_Opt['Ticker'] = Dif_Opt['ticker_bolsa_y']
Dif_Opt.loc[Dif_Opt['ticker_bolsa_y'].isnull(), 'Ticker'] = Dif_Opt['ticker_bolsa_x']
Dif_Opt = Dif_Opt.drop(['ticker_bolsa_x', 'ticker_bolsa_y'], axis=1)
Dif_Opt.fillna(0, inplace=True)

Dif_Opt['DifQtd'] = Dif_Opt['EndQty'] - Dif_Opt['quantidade']
Dif_Opt['DifPnL'] = Dif_Opt['TotalBookPL'] - Dif_Opt['pnl_total']
Dif_Opt = Dif_Opt.drop(Dif_Opt[(Dif_Opt['DifPnL'].abs() < arred)].index)
Dif_Opt['DifPnL'] = Dif_Opt['DifPnL'].round(0)


# Get Fixed Income dif
sSQL = f"""SELECT a.PeriodEndDate as date, a.InvAssetType As Tipo, a.Fund as codigo_IAM_fundo,
                  AVG(BegLocalMarketPrice) AS BegLocalMarketPrice, AVG(EndLocalMarketPrice) as EndLocalMarketPrice,
                  SUM(a.BegQty) As BegQty, SUM(a.EndQty) As EndQty, SUM(a.TotalBookPL) As TotalBookPL,
                  a.InvGFSDefined2 As codigo_IAM_ativo
           from {base_table} (NOLOCK) as a
           LEFT JOIN VIEW_FUNDOS_CADASTRO_ATIVOS_LAST_VALUES (NOLOCK) As b
               ON CONCAT(a.ExternalID2,'_',a.LongShortIndicator,'_',a.CounterPartyCode) = b.valor_str and b.campo = 'codigo_sistema'
           LEFT JOIN VIEW_FUNDOS_CADASTRO_ATIVOS_LAST_VALUES (NOLOCK) as c
               ON b.codigo_IAM_ativo = c.codigo_IAM_ativo and c.campo = 'ativo'
           LEFT JOIN VIEW_FUNDOS_CADASTRO_ATIVOS_LAST_VALUES (NOLOCK) as d
               ON a.InvGFSDefined2 = d.codigo_IAM_ativo and d.campo = 'ativo'
           WHERE InvAssetType IN ('BNDSVN','BNDCRP','BNDTRS') and AccountingPeriod = 'DAILY'
             and A.TranType not in ('Repo','ReverseRepo')
             and A.Fund in ({fundo}) and A.PeriodEndDate = '{data_ref}'
           GROUP BY a.PeriodEndDate, a.InvAssetType, a.Fund, a.InvGFSDefined2"""
Fixed_SSnC = select_from_db(sSQL, usernameSQL, passwordSQL, 'DBSX337')
Fixed_SSnC['Tipo'] = Fixed_SSnC['Tipo'].map(de_para_dict)


sSQL = f"""SELECT date, codigo_IAM_fundo, codigo_IAM_ativo, ticker_bolsa,
                  avg(preco_limpo_d1) as preco_limpo_d1, avg(preco_limpo) as preco_limpo,
                  SUM(quantidade) As quantidade, SUM(pnl_total) As pnl_total
           FROM VW_FUNDOS_POSICAO (NOLOCK)
           WHERE tipo = 'Fixed Income' and ativo = 'Bonds' and codigo_IAM_fundo in ({fundo}) and date = '{data_ref}'
           GROUP BY date, codigo_IAM_fundo, codigo_IAM_ativo, ticker_bolsa"""
Fixed_IAM = select_from_db(sSQL, usernameSQL, passwordSQL, 'DBSX337')


Dif_Fixed = pd.merge(Fixed_SSnC, Fixed_IAM, how='outer',
                     on=['date', 'codigo_IAM_fundo', 'codigo_IAM_ativo'])
Dif_Fixed['Tipo'] = 'Fixed Income'
Dif_Fixed['Ticker'] = Dif_Fixed['ticker_bolsa']
Dif_Fixed = Dif_Fixed.drop(['ticker_bolsa'], axis=1)
Dif_Fixed.fillna(0, inplace=True)

Dif_Fixed['DifQtd'] = Dif_Fixed['EndQty'] - Dif_Fixed['quantidade']
Dif_Fixed['DifPnL'] = Dif_Fixed['TotalBookPL'] - Dif_Fixed['pnl_total']
Dif_Fixed = Dif_Fixed.drop(Dif_Fixed[(Dif_Fixed['DifPnL'].abs() < arred)].index)
Dif_Fixed['DifPnL'] = Dif_Fixed['DifPnL'].round(0)


# Get CaixaCPR dif
sSQL = f"""SELECT a.PeriodEndDate as date, a.Fund as codigo_IAM_fundo, a.InvAssetType As Tipo,
                  LOWER(CONCAT('caixa_', a.InvLocalCcy)) as codigo_IAM_ativo,
                  AVG(BegLocalMarketPrice) AS BegLocalMarketPrice, AVG(EndLocalMarketPrice) as EndLocalMarketPrice,
                  sum(a.endlocalnav) as EndQty, sum(a.TotalBookPL) As TotalBookPL
           FROM {base_table} (NOLOCK) as a
           WHERE a.AccountingPeriod = 'DAILY' and a.InvAssetType IN ('CSH')
             and fund in ({fundo}) and periodenddate = '{data_ref}'
           GROUP BY a.PeriodEndDate, a.Fund, a.InvLocalCcy, a.InvAssetType"""
CPR_SSnC = select_from_db(sSQL, usernameSQL, passwordSQL, 'DBSX337')
CPR_SSnC['Tipo'] = CPR_SSnC['Tipo'].map(de_para_dict)


sSQL = f"""SELECT date, codigo_IAM_fundo, codigo_IAM_ativo,
                  avg(preco_limpo_d1) as preco_limpo_d1, avg(preco_limpo) as preco_limpo,
                  SUM(quantidade) As quantidade, SUM(pnl_total) As pnl_total
           FROM (
               SELECT date, codigo_IAM_fundo,
                      CASE
                          WHEN fator_risco <> 'CaixaCPR' then CONCAT('caixa_', LOWER(moeda_ativo))
                          else codigo_IAM_ativo
                      end as codigo_IAM_ativo,
                      preco_limpo_d1, preco_limpo, quantidade, pnl_total, tipo
               FROM VW_FUNDOS_POSICAO (NOLOCK)
           ) as a
           WHERE codigo_iam_fundo in ({fundo}) and date = '{data_ref}'
             and Tipo = 'CaixaCPR' and codigo_IAM_ativo like 'caixa_%'
           GROUP BY date, codigo_iam_fundo, codigo_iam_ativo"""
CPR_IAM = select_from_db(sSQL, usernameSQL, passwordSQL, 'DBSX337')


Dif_CPR = pd.merge(CPR_SSnC, CPR_IAM, how='outer',
                   on=['date', 'codigo_IAM_fundo', 'codigo_IAM_ativo'])
Dif_CPR.fillna(0, inplace=True)

Dif_CPR['DifQtd'] = Dif_CPR['EndQty'] - Dif_CPR['quantidade']
Dif_CPR['DifPnL'] = Dif_CPR['TotalBookPL'] - Dif_CPR['pnl_total']
Dif_CPR = Dif_CPR.drop(Dif_CPR[(Dif_CPR['DifPnL'].abs() < arred)].index)
Dif_CPR['DifPnL'] = Dif_CPR['DifPnL'].round(0)


# Total fund's difference
df_resumo = pd.merge(Total_IAM, Total_SSnC, how='outer',
                     on=['date', 'codigo_IAM_fundo', 'Tipo'])
df_resumo.fillna(0, inplace=True)
df_resumo['Dif'] = df_resumo['PnL_SSnC'] - df_resumo['PnL_IAM']
df_resumo.sort_values(by=['Tipo', 'codigo_IAM_fundo'], inplace=True, ascending=True)


# joins all difs
df_Difs = pd.concat([Dif_Opt, Dif_Fut, Dif_Acao, Dif_CPR, Dif_Fixed])
df_Difs['Dif_preco_D1'] = df_Difs['BegLocalMarketPrice'] - df_Difs['preco_limpo_d1']
df_Difs['Dif_preco'] = df_Difs['EndLocalMarketPrice'] - df_Difs['preco_limpo']
df_Difs.sort_values(by=['Tipo', 'codigo_IAM_ativo', 'codigo_IAM_fundo'], inplace=True, ascending=True)
df_Difs = df_Difs.reindex(columns=[
    'date', 'codigo_IAM_fundo', 'codigo_IAM_ativo', 'Tipo',
    'BegQty', 'EndQty', 'TotalBookPL', 'quantidade', 'pnl_total',
    'Ticker', 'DifQtd', 'DifPnL', 'Dif_preco', 'Dif_preco_D1',
    'BegLocalMarketPrice', 'preco_limpo_d1', 'EndLocalMarketPrice', 'preco_limpo',
])


# Calculate PnL Dif for each strategy
df_fundos = df_Difs['codigo_IAM_fundo'].drop_duplicates()
df_estrat_fim = pd.DataFrame()

for cod_fund in df_fundos:
    df_ativos = df_Difs[df_Difs['codigo_IAM_fundo'] == f'{cod_fund}']
    codAtivos = df_ativos['codigo_IAM_ativo'].to_list()
    codAtivos = [f"'{x}'" for x in codAtivos]
    codAtivos = ','.join(map(str, codAtivos))

    df_temp = df_ativos[(df_ativos['Tipo'] != 'CaixaCPR')]
    df_temp = df_temp.drop(['BegQty', 'EndQty', 'TotalBookPL', 'quantidade', 'pnl_total', 'Ticker', 'DifQtd'], axis=1)

    sSQL = f"""SELECT date, codigo_IAM_fundo, codigo_IAM_ativo, est1, est2, est3, est4, est5,
                      round(SUM(quantidade),0) As quantidade, round(SUM(quantidade_abertura),0) As quantidade_abertura
               FROM FUNDOS_POSICAO (NOLOCK)
               WHERE codigo_IAM_fundo = '{cod_fund}' and date = '{data_ref}' and codigo_iam_ativo in ({codAtivos})
               GROUP BY date, codigo_IAM_fundo, codigo_IAM_ativo, est1, est2, est3, est4, est5"""
    pos_estrat = select_from_db(sSQL, usernameSQL, passwordSQL, 'DBSX337')

    pos_estrat['Qtd'] = pos_estrat['quantidade']
    pos_estrat.loc[pos_estrat['quantidade'] == 0, 'Qtd'] = pos_estrat['quantidade_abertura']
    pos_estrat = pos_estrat.drop(
        pos_estrat[(pos_estrat['quantidade'] == 0) & (pos_estrat['quantidade_abertura'] == 0)].index
    )

    total_qtd = pos_estrat.groupby(
        by=['date', 'codigo_IAM_fundo', 'codigo_IAM_ativo'], as_index=False, sort=False
    ).agg(Qtd_total=("Qtd", "sum"))
    pos_estrat = pd.merge(pos_estrat, total_qtd, how='left',
                          on=['date', 'codigo_IAM_fundo', 'codigo_IAM_ativo'])
    pos_estrat = pd.merge(pos_estrat, df_temp, how='outer',
                          on=['date', 'codigo_IAM_fundo', 'codigo_IAM_ativo'])
    pos_estrat['DifPnLEstrat'] = pos_estrat['DifPnL'] * pos_estrat['Qtd'] / pos_estrat['Qtd_total']

    # Ajustando ativos que nao estao na posicao (vao ficar sem estrategia)
    pos_estrat.loc[pos_estrat['DifPnLEstrat'].isnull(), 'DifPnLEstrat'] = pos_estrat['DifPnL']
    pos_estrat[['est1', 'est2', 'est3', 'est4', 'est5']] = (
        pos_estrat[['est1', 'est2', 'est3', 'est4', 'est5']].fillna('VERIFICAR')
    )

    # Tratando Inf
    df_temp3 = pos_estrat[(pos_estrat['Qtd_total'] != 0)]
    df_temp2 = pos_estrat[(pos_estrat['Qtd_total'] == 0)]
    df_temp2['Trades'] = np.where((df_temp2['quantidade'] != df_temp2['quantidade_abertura']), 'Sim', 'Nao')
    df_temp2.loc[df_temp2['Trades'] == 'Sim', 'DifPnLEstrat'] = df_temp2['DifPnL']
    df_temp2 = df_temp2.drop(df_temp2[(df_temp2['Trades'] == 'Nao')].index)

    # Tratando quando as duas estrategias possuem trade que zera as quantidades,
    # dessa forma distribuimos igualmente nas estrategias a diferenca de pnl
    df_temp4 = df_temp2.groupby(['codigo_IAM_ativo'])[['codigo_IAM_ativo']].count()
    df_temp4 = df_temp4.rename(columns={'codigo_IAM_ativo': 'count'})
    df_temp4 = df_temp4.reset_index()
    df_temp2 = pd.merge(df_temp2, df_temp4, how='left', on=['codigo_IAM_ativo'])
    df_temp2['DifPnLEstrat'] = df_temp2['DifPnLEstrat'] / df_temp2['count']
    df_temp2 = df_temp2.drop(['Trades', 'count'], axis=1)

    pos_estrat = pd.concat([df_temp3, df_temp2])
    pos_estrat = pos_estrat.drop(
        ['quantidade', 'quantidade_abertura', 'Qtd', 'Qtd_total', 'DifPnL',
         'Dif_preco', 'BegLocalMarketPrice', 'preco_limpo_d1', 'EndLocalMarketPrice', 'preco_limpo'],
        axis=1,
    )
    pos_estrat = pos_estrat.reindex(columns=[
        'date', 'codigo_IAM_fundo', 'codigo_IAM_ativo', 'Tipo',
        'est1', 'est2', 'est3', 'est4', 'est5', 'DifPnLEstrat',
    ])

    df_estrat_fim = pd.concat([df_estrat_fim, pos_estrat])

df_estrat_fim['DifPnLEstrat'] = df_estrat_fim['DifPnLEstrat'].astype('int').round(0)


# Join CPR with df strategy
df_tempcpr = Dif_CPR.drop(
    ['EndQty', 'TotalBookPL', 'quantidade', 'pnl_total', 'DifQtd',
     'BegLocalMarketPrice', 'preco_limpo_d1', 'EndLocalMarketPrice', 'preco_limpo'],
    axis=1,
)
df_tempcpr = df_tempcpr.rename(columns={'DifPnL': 'DifPnLEstrat'})
df_tempcpr['est1'] = 'CaixaCPR'
df_tempcpr.loc[:, ['est2', 'est3', 'est4', 'est5']] = ['-', '-', '-', '-']

df_estrat_fim = pd.concat([df_estrat_fim, df_tempcpr])
df_estrat_fim.sort_values(
    by=['Tipo', 'codigo_IAM_ativo', 'est1', 'est2', 'est3', 'est4', 'est5', 'codigo_IAM_fundo'],
    inplace=True, ascending=True,
)

# Count codigo_IAM_fundo and codigo_IAM_ativo total in dataframe
df_estrat_fim['count'] = 1
df_estrat_fim['count'] = df_estrat_fim.groupby(['codigo_IAM_fundo', 'codigo_IAM_ativo'])['count'].transform('sum')


# Retirar colunas de batimento
if not batimento_preco:
    df_Difs.drop(
        columns=['Dif_preco_D1', 'Dif_preco', 'BegLocalMarketPrice', 'preco_limpo_d1', 'EndLocalMarketPrice', 'preco_limpo'],
        inplace=True,
    )


# Create a Pandas Excel writer using XlsxWriter as the engine.
agora = datetime.datetime.now()
data_hora_atual = agora.strftime("%Y-%m-%d_%H-%M-%S")

file_path = pathlib.Path(f"../output/batimento/renda_fixa/ResumoMartelo_{data_hora_atual}_2.xlsx")
file_path.parent.mkdir(parents=True, exist_ok=True)
writer = pd.ExcelWriter(file_path, engine='xlsxwriter')

# Write each dataframe to a different worksheet.
df_resumo.to_excel(writer, sheet_name='Resumo', index=False, freeze_panes=(1, 0))
df_Difs.to_excel(writer, sheet_name='Ativos', index=False, freeze_panes=(1, 0))
df_estrat_fim.to_excel(writer, sheet_name='PnLEstrategia', index=False, freeze_panes=(1, 0))

# Aba com ativos de VERIFICAR
if len(df_estrat_fim) > 0:
    mask_verificar = df_estrat_fim['est1'] == 'VERIFICAR'
    df_verificar = df_estrat_fim.loc[mask_verificar, :]
    df_verificar.to_excel(writer, sheet_name='VerificarPnL', index=False, freeze_panes=(1, 0))
    df_sem_verificar = df_estrat_fim.loc[~mask_verificar, :]
    df_sem_verificar.to_excel(writer, sheet_name='SemVerificarPnL', index=False, freeze_panes=(1, 0))

writer.close()

print(rf"Arquivo Salvo: {file_path}")

os.startfile(file_path)
