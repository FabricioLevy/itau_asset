
import datetime
import os
import pathlib

import numpy as np
import pandas as pd
import pyodbc
import QuantLib as ql
from datetime import date


# ── Configuration ──────────────────────────────────────────────────────────────

_DB_SERVER  = 'SQNPRC028'
_DB_NAME    = 'DBSX337'
_BASE_TABLE = 'SISTEMAS_SSC_PED_INTRADAY'

_USERNAME_SQL = os.environ.get('SQL_LOGIN')
_PASSWORD_SQL = os.environ.get('SQL_PASSWORD')

_ARRED           = 0
_BATIMENTO_PRECO = True

# lista_fundos = ['ESP_INDIAGDFI','ESP_INDIAGD','ESP_OPPITUB','ESP_INDIAGDULT','ESP_PREVGDFIINDIA','ESP_GDFISIERRA','ESP_OSCARGDULT','ESP_GDFITANGO_B','ESP_TANGOGD_B','ESP_PREVGDFITANGO_B','ESP_SIERRAGD','ESP_PAPAGDULT','ESP_SIERRAGDULT','ESP_PREVGDFIPAPA','ESP_GDFIPAPA']
# lista_fundos = ['ESP_SIERRAGD','ESP_OSCARGDULT','ESP_PAPAGDULT']
# lista_fundos = ['ITAUGLMACROHE','ESP_MOPPGD','ESP_PREVGDFIMOPPHF','ESP_GDFIMOPP'] # YIELD PLUS
# lista_fundos = ['ESP_GDFITANGO_B','ESP_TANGOGD_B','ESP_PREVGDFITANGO_B'] # FUNDAMENTA
# lista_fundos = ['ESP_VICTORGD','ESP_PREVGDFIVICT'] # VICTOR
#### lista_fundos = ['ESP_INDIAGDFI','ESP_INDIAGD','ESP_OPPITUB','ESP_INDIAGDULT','ESP_PREVGDFIINDIA'] # INDIA
# lista_fundos = ['ESP_GDFIMOPP','ESP_MOPPGD','ESP_PREVGDFIMOPPHF','ITAUGLMACROHE','ESP_GDFISIERRA','ESP_PREVGDFIVICT','ESP_OSCARGDULT','ESP_VICTORGD','ESP_PREVGDFIVICT','ESP_GDFITANGO_B','ESP_TANGOGD_B','ESP_SIERRAGD']
#### lista_fundos = ['ESP_LIMAGD','ESP_FIOPTIMUS','ESP_ALVORADAFI','ESP_PREVGDFILIMA','ESP_OPTIMUSLB','ESP_OPTIMUS','ESP_BLUEGD','ESP_PREVGDFIBLUE','ESP_GDFIBLUE','ESP_ALLSEASONS','ESP_QUANT']
# lista_fundos = ['ESP_ALVORADAFI','ESP_PREVGDFIBLUE','ESP_BLUEGD','ESP_GDFIBLUE','ESP_ALLSEASONS','ESP_QUANT']
# lista_fundos = ['ESP_PREVGDFILIMA','ESP_LIMAGD','ESP_FIOPTIMUS','ESP_OPTIMUS']
# lista_fundos = ['ESP_GDFIPAPA','ESP_PAPAGD']
# lista_fundos = ['ESP_FIOPTIMUS']
_LISTA_FUNDOS = ['ESP_FIASSETCORE']

_DE_PARA_TIPO = {
    'CSH':               'CaixaCPR',
    'PSEUDO':            'Despesa',
    'CASHEQ':            'Despesa',
    'EQYLST':            'Equity',
    'FXF':               'Future',
    'CMDFUT':            'Future',
    'CMDOPT':            'Option',
    'CNTOPT':            'Option',
    'CNTSWP':            'Swap',
    'CNTFRA':            'Swap',
    'CREDITDEFAULTSWAP': 'Swap',
    'EQITYSWP':          'Swap',
    'BNDSVN':            'Fixed Income',
    'BNDCRP':            'Fixed Income',
    'BNDTRS':            'Fixed Income',
    'EQYNLT':            'Equity',
    'BNDSWP':            'Swap',
    'COMPAP':            'Fixed Income',
}


# ── Database helpers ───────────────────────────────────────────────────────────

def select_from_db(query, usuario, senha, base):
    conn = pyodbc.connect(
        "DRIVER={SQL Server Native Client 11.0};"
        f"SERVER={_DB_SERVER};"
        f"DATABASE={base};"
        f"UID={usuario};"
        f"PWD={senha}"
    )
    return pd.read_sql_query(query, conn)


def _to_sql_list(items):
    return ','.join(f"'{x}'" for x in items)


def _merge_and_calc_dif(df_ssnc, df_iam, tipo=None, ticker_mode=None):
    """
    ticker_mode: 'xy' -> merge produces ticker_bolsa_x/y; 'single' -> only ticker_bolsa; None -> no ticker
    """
    join_keys = ['date', 'codigo_IAM_fundo', 'codigo_IAM_ativo']
    dif = pd.merge(df_ssnc, df_iam, how='outer', on=join_keys)

    if tipo is not None:
        dif['Tipo'] = tipo

    if ticker_mode == 'xy':
        dif['Ticker'] = dif['ticker_bolsa_y']
        dif.loc[dif['ticker_bolsa_y'].isnull(), 'Ticker'] = dif['ticker_bolsa_x']
        dif = dif.drop(['ticker_bolsa_x', 'ticker_bolsa_y'], axis=1)
    elif ticker_mode == 'single':
        dif['Ticker'] = dif['ticker_bolsa']
        dif = dif.drop(['ticker_bolsa'], axis=1)

    dif.fillna(0, inplace=True)
    dif['DifQtd'] = dif['EndQty'] - dif['quantidade']
    dif['DifPnL'] = dif['TotalBookPL'] - dif['pnl_total']
    dif = dif.drop(dif[dif['DifPnL'].abs() < _ARRED].index)
    dif['DifPnL'] = dif['DifPnL'].round(0)
    return dif


# ── Query functions ────────────────────────────────────────────────────────────

def _fetch_batimento(data_ref):
    sSQL = f"""select a.*, ABS(a.diferenca) as abs_dif,
    case when diferenca<0 then 'V' else 'C' end as compra_venda,
    b.valor_str, c.valor_str as tipo, d.valor_str as ticker_bolsa
from FUNDOS_POSICAO_BATIMENTO (nolock) as a
left join VIEW_FUNDOS_CADASTRO_FUNDOS_LAST_VALUES as b
    on a.codigo_IAM_fundo=b.codigo_IAM_fundo and b.campo='mesagestao'
left join VIEW_FUNDOS_CADASTRO_ATIVOS_LAST_VALUES as c
    on a.codigo_IAM_ativo=c.codigo_IAM_ativo and c.campo='Tipo'
left join VIEW_FUNDOS_CADASTRO_ATIVOS_LAST_VALUES as d
    on a.codigo_IAM_ativo=d.codigo_IAM_ativo and d.campo='ticker_bolsa'
where 1=1
    and (b.valor_str like '%srf%')
    and abs(a.diferenca)>={_ARRED}
    and a.date='{data_ref}'
order by a.date, b.valor_str, a.codigo_IAM_fundo, a.codigo_IAM_ativo"""
    return select_from_db(sSQL, _USERNAME_SQL, _PASSWORD_SQL, _DB_NAME)


def _fetch_outros(data_ref):
    sSQL = f"""select a.date,
    a.codigo_IAM_fundo,
    a.mesa_gestao,
    sum(a.pnl_total)-b.fundo_pnl as outros_financeiro,
    (sum(a.pnl_total_perc)-b.fundo_pnl_perc)*10000 as outros_bps
from VW_FUNDOS_POSICAO (nolock) a
    left join VW_FUNDOS_COTAS_PL (nolock) b
        on a.codigo_IAM_fundo=b.codigo_IAM_fundo and a.date=b.date
where 1=1
    and a.mesa_gestao like '%SRF%'
    and a.date='{data_ref}'
group by a.date, a.codigo_IAM_fundo, b.fundo_pnl, b.fundo_pnl_perc, a.mesa_gestao
having abs((sum(a.pnl_total_perc)-b.fundo_pnl_perc)*10000)>0.3
order by a.date asc, abs(sum(a.pnl_total_perc)-b.fundo_pnl_perc) desc"""
    return select_from_db(sSQL, _USERNAME_SQL, _PASSWORD_SQL, _DB_NAME)


def _fetch_total_ssnc(data_ref, fundo_sql):
    sSQL = f"""select date, codigo_IAM_fundo, Tipo, SUM(ISNULL(PnL_SSnC,0)) As PnL_SSnC
           from (
               SELECT PeriodEndDate As date, Fund As codigo_IAM_fundo,
                      case when InvAssetType = 'pseudo' and InvId like '%INT%' then 'CSH' else InvAssetType end As Tipo,
                      SUM(ISNULL(TotalBookPL,0)) As PnL_SSnC
               FROM {_BASE_TABLE} (NOLOCK)
               WHERE AccountingPeriod = 'DAILY' and Fund in ({fundo_sql}) and PeriodEndDate = '{data_ref}'
               GROUP BY PeriodEndDate, Fund, InvAssetType, InvId
           ) as bla
           GROUP BY date, codigo_IAM_fundo, Tipo"""
    df = select_from_db(sSQL, _USERNAME_SQL, _PASSWORD_SQL, _DB_NAME)
    df['Tipo'] = df['Tipo'].map(_DE_PARA_TIPO)
    colunas = ['date', 'codigo_IAM_fundo', 'Tipo']
    return df.groupby(by=colunas, as_index=False, sort=False).agg({'PnL_SSnC': 'sum'})


def _fetch_total_iam(data_ref, fundo_sql):
    sSQL = f"""SELECT date, codigo_IAM_fundo, Tipo, CONVERT(float,SUM(ISNULL(pnl_total,0))) As PnL_IAM
           FROM VW_FUNDOS_POSICAO (NOLOCK)
           WHERE codigo_IAM_fundo in ({fundo_sql}) and date = '{data_ref}'
           GROUP BY date, codigo_IAM_fundo, Tipo"""
    return select_from_db(sSQL, _USERNAME_SQL, _PASSWORD_SQL, _DB_NAME)


def _fetch_dif_acoes(data_ref, fundo_sql):
    sSQL_ssnc = f"""SELECT A.PeriodEndDate as date, A.InvAssetType As Tipo, A.Fund as codigo_IAM_fundo,
                  A.InvGFSDefined3 as codigo_IAM_ativo, B.valor_str As ticker_bolsa,
                  AVG(BegLocalMarketPrice) AS BegLocalMarketPrice, AVG(EndLocalMarketPrice) as EndLocalMarketPrice,
                  SUM(A.BegQty) As BegQty, SUM(A.EndQty) As EndQty, SUM(A.TotalBookPL) As TotalBookPL
           FROM {_BASE_TABLE} (NOLOCK) As A
           LEFT JOIN VIEW_FUNDOS_CADASTRO_ATIVOS_LAST_VALUES (NOLOCK) As B
               ON A.InvGFSDefined3 = B.codigo_IAM_ativo and B.campo = 'ticker_bolsa'
           WHERE InvAssetType in ('EQYLST','EQYNLT') and accountingPeriod = 'DAILY'
             and A.Fund in ({fundo_sql}) and A.PeriodEndDate = '{data_ref}'
           GROUP BY A.accountingPeriod, A.PeriodEndDate, A.InvAssetType, A.Fund, A.InvGFSDefined3, B.valor_str"""
    df_ssnc = select_from_db(sSQL_ssnc, _USERNAME_SQL, _PASSWORD_SQL, _DB_NAME)
    df_ssnc['Tipo'] = df_ssnc['Tipo'].map(_DE_PARA_TIPO)

    sSQL_iam = f"""SELECT date, codigo_IAM_fundo, codigo_IAM_ativo, ticker_bolsa,
                  avg(preco_limpo_d1) as preco_limpo_d1, avg(preco_limpo) as preco_limpo,
                  SUM(quantidade) As quantidade, SUM(pnl_total) As pnl_total
           FROM VW_FUNDOS_POSICAO (NOLOCK) As D
           WHERE tipo = 'Equity' and codigo_IAM_fundo in ({fundo_sql}) and date = '{data_ref}'
           GROUP BY date, codigo_IAM_fundo, codigo_IAM_ativo, ticker_bolsa"""
    df_iam = select_from_db(sSQL_iam, _USERNAME_SQL, _PASSWORD_SQL, _DB_NAME)

    return _merge_and_calc_dif(df_ssnc, df_iam, tipo='Equity', ticker_mode='xy')


def _fetch_dif_futuros(data_ref, fundo_sql):
    sSQL_ssnc = f"""SELECT date, Tipo, codigo_IAM_fundo, codigo_IAM_ativo, ticker_bolsa,
                  AVG(BegLocalMarketPrice) AS BegLocalMarketPrice, AVG(EndLocalMarketPrice) as EndLocalMarketPrice,
                  SUM(BegQty) As BegQty, SUM(EndQty) As EndQty, SUM(TotalBookPL) As TotalBookPL
           FROM (
               SELECT A.PeriodEndDate as date, A.InvAssetType As Tipo, A.Fund as codigo_IAM_fundo,
                      ISNULL(B.codigo_IAM_ativo, a.InvTicker) as codigo_IAM_ativo, B.valor_str as ticker_bolsa,
                      BegLocalMarketPrice, EndLocalMarketPrice, BegQty, EndQty, TotalBookPL
               FROM {_BASE_TABLE} (NOLOCK) as A
               LEFT JOIN VIEW_FUNDOS_CADASTRO_ATIVOS_LAST_VALUES (NOLOCK) as B
                   ON a.InvTicker = B.codigo_IAM_ativo and B.campo = 'ticker_bolsa'
               WHERE InvAssetType = 'CMDFUT' and accountingPeriod = 'DAILY'
                 and A.Fund in ({fundo_sql}) and A.PeriodEndDate = '{data_ref}'
           ) As DF
           GROUP BY date, Tipo, codigo_IAM_fundo, codigo_IAM_ativo, ticker_bolsa"""
    df_ssnc = select_from_db(sSQL_ssnc, _USERNAME_SQL, _PASSWORD_SQL, _DB_NAME)
    df_ssnc['Tipo'] = df_ssnc['Tipo'].map(_DE_PARA_TIPO)

    sSQL_iam = f"""SELECT date, codigo_IAM_fundo, codigo_IAM_ativo, ticker_bolsa,
                  avg(preco_limpo_d1) as preco_limpo_d1, avg(preco_limpo) as preco_limpo,
                  SUM(quantidade) As quantidade, SUM(pnl_total) As pnl_total
           FROM VW_FUNDOS_POSICAO (NOLOCK) As D
           WHERE tipo = 'Future' and ativo <> 'NDF' and codigo_IAM_fundo in ({fundo_sql}) and date = '{data_ref}'
           GROUP BY date, codigo_IAM_fundo, codigo_IAM_ativo, ticker_bolsa"""
    df_iam = select_from_db(sSQL_iam, _USERNAME_SQL, _PASSWORD_SQL, _DB_NAME)

    return _merge_and_calc_dif(df_ssnc, df_iam, tipo='Future', ticker_mode='xy')


def _fetch_dif_opcoes(data_ref, fundo_sql):
    sSQL_ssnc = f"""select a.PeriodEndDate as date, a.InvAssetType As Tipo, a.Fund as codigo_IAM_fundo,
                  isnull(a.InvTicker, c.codigo_IAM_ativo) as codigo_IAM_ativo,
                  isnull(b.valor_str, d.valor_str) as ticker_bolsa,
                  AVG(BegLocalMarketPrice) AS BegLocalMarketPrice, AVG(EndLocalMarketPrice) as EndLocalMarketPrice,
                  SUM(a.BegQty) As BegQty, SUM(a.EndQty) As EndQty, Sum(a.TotalBookPL) As TotalBookPL
           from {_BASE_TABLE} (NOLOCK) as a
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
             and A.Fund in ({fundo_sql}) and A.PeriodEndDate = '{data_ref}'
           GROUP BY a.PeriodEndDate, a.InvAssetType, a.Fund,
                    isnull(a.InvTicker, c.codigo_IAM_ativo), isnull(b.valor_str, d.valor_str)"""
    df_ssnc = select_from_db(sSQL_ssnc, _USERNAME_SQL, _PASSWORD_SQL, _DB_NAME)
    df_ssnc['Tipo'] = df_ssnc['Tipo'].map(_DE_PARA_TIPO)

    sSQL_iam = f"""SELECT date, codigo_IAM_fundo, codigo_IAM_ativo, ticker_bolsa,
                  avg(preco_limpo_d1) as preco_limpo_d1, avg(preco_limpo) as preco_limpo,
                  SUM(quantidade) As quantidade, SUM(pnl_total) As pnl_total
           FROM VW_FUNDOS_POSICAO (NOLOCK)
           WHERE tipo = 'Option' and codigo_IAM_fundo in ({fundo_sql}) and date = '{data_ref}'
             and codigo_IAM_ativo not like 'FXO[_]%' AND codigo_IAM_ativo not like 'EQO[_]%'
           GROUP BY date, codigo_IAM_fundo, codigo_IAM_ativo, ticker_bolsa"""
    df_iam = select_from_db(sSQL_iam, _USERNAME_SQL, _PASSWORD_SQL, _DB_NAME)

    return _merge_and_calc_dif(df_ssnc, df_iam, tipo='Options', ticker_mode='xy')


def _fetch_dif_fixed(data_ref, fundo_sql):
    sSQL_ssnc = f"""SELECT a.PeriodEndDate as date, a.InvAssetType As Tipo, a.Fund as codigo_IAM_fundo,
                  AVG(BegLocalMarketPrice) AS BegLocalMarketPrice, AVG(EndLocalMarketPrice) as EndLocalMarketPrice,
                  SUM(a.BegQty) As BegQty, SUM(a.EndQty) As EndQty, SUM(a.TotalBookPL) As TotalBookPL,
                  a.InvGFSDefined2 As codigo_IAM_ativo
           from {_BASE_TABLE} (NOLOCK) as a
           LEFT JOIN VIEW_FUNDOS_CADASTRO_ATIVOS_LAST_VALUES (NOLOCK) As b
               ON CONCAT(a.ExternalID2,'_',a.LongShortIndicator,'_',a.CounterPartyCode) = b.valor_str and b.campo = 'codigo_sistema'
           LEFT JOIN VIEW_FUNDOS_CADASTRO_ATIVOS_LAST_VALUES (NOLOCK) as c
               ON b.codigo_IAM_ativo = c.codigo_IAM_ativo and c.campo = 'ativo'
           LEFT JOIN VIEW_FUNDOS_CADASTRO_ATIVOS_LAST_VALUES (NOLOCK) as d
               ON a.InvGFSDefined2 = d.codigo_IAM_ativo and d.campo = 'ativo'
           WHERE InvAssetType IN ('BNDSVN','BNDCRP','BNDTRS') and AccountingPeriod = 'DAILY'
             and A.TranType not in ('Repo','ReverseRepo')
             and A.Fund in ({fundo_sql}) and A.PeriodEndDate = '{data_ref}'
           GROUP BY a.PeriodEndDate, a.InvAssetType, a.Fund, a.InvGFSDefined2"""
    df_ssnc = select_from_db(sSQL_ssnc, _USERNAME_SQL, _PASSWORD_SQL, _DB_NAME)
    df_ssnc['Tipo'] = df_ssnc['Tipo'].map(_DE_PARA_TIPO)

    sSQL_iam = f"""SELECT date, codigo_IAM_fundo, codigo_IAM_ativo, ticker_bolsa,
                  avg(preco_limpo_d1) as preco_limpo_d1, avg(preco_limpo) as preco_limpo,
                  SUM(quantidade) As quantidade, SUM(pnl_total) As pnl_total
           FROM VW_FUNDOS_POSICAO (NOLOCK)
           WHERE tipo = 'Fixed Income' and ativo = 'Bonds' and codigo_IAM_fundo in ({fundo_sql}) and date = '{data_ref}'
           GROUP BY date, codigo_IAM_fundo, codigo_IAM_ativo, ticker_bolsa"""
    df_iam = select_from_db(sSQL_iam, _USERNAME_SQL, _PASSWORD_SQL, _DB_NAME)

    return _merge_and_calc_dif(df_ssnc, df_iam, tipo='Fixed Income', ticker_mode='single')


def _fetch_dif_cpr(data_ref, fundo_sql):
    sSQL_ssnc = f"""SELECT a.PeriodEndDate as date, a.Fund as codigo_IAM_fundo, a.InvAssetType As Tipo,
                  LOWER(CONCAT('caixa_', a.InvLocalCcy)) as codigo_IAM_ativo,
                  AVG(BegLocalMarketPrice) AS BegLocalMarketPrice, AVG(EndLocalMarketPrice) as EndLocalMarketPrice,
                  sum(a.endlocalnav) as EndQty, sum(a.TotalBookPL) As TotalBookPL
           FROM {_BASE_TABLE} (NOLOCK) as a
           WHERE a.AccountingPeriod = 'DAILY' and a.InvAssetType IN ('CSH')
             and fund in ({fundo_sql}) and periodenddate = '{data_ref}'
           GROUP BY a.PeriodEndDate, a.Fund, a.InvLocalCcy, a.InvAssetType"""
    df_ssnc = select_from_db(sSQL_ssnc, _USERNAME_SQL, _PASSWORD_SQL, _DB_NAME)
    df_ssnc['Tipo'] = df_ssnc['Tipo'].map(_DE_PARA_TIPO)

    sSQL_iam = f"""SELECT date, codigo_IAM_fundo, codigo_IAM_ativo,
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
           WHERE codigo_iam_fundo in ({fundo_sql}) and date = '{data_ref}'
             and Tipo = 'CaixaCPR' and codigo_IAM_ativo like 'caixa_%'
           GROUP BY date, codigo_iam_fundo, codigo_iam_ativo"""
    df_iam = select_from_db(sSQL_iam, _USERNAME_SQL, _PASSWORD_SQL, _DB_NAME)

    return _merge_and_calc_dif(df_ssnc, df_iam)


# ── Strategy calculation ───────────────────────────────────────────────────────

def _calc_estrategia_fundo(cod_fund, df_difs, data_ref):
    df_ativos      = df_difs[df_difs['codigo_IAM_fundo'] == cod_fund]
    cod_ativos_sql = _to_sql_list(df_ativos['codigo_IAM_ativo'].to_list())

    df_temp = df_ativos[df_ativos['Tipo'] != 'CaixaCPR'].drop(
        ['BegQty', 'EndQty', 'TotalBookPL', 'quantidade', 'pnl_total', 'Ticker', 'DifQtd'], axis=1
    )

    sSQL = f"""SELECT date, codigo_IAM_fundo, codigo_IAM_ativo, est1, est2, est3, est4, est5,
                      round(SUM(quantidade),0) As quantidade, round(SUM(quantidade_abertura),0) As quantidade_abertura
               FROM FUNDOS_POSICAO (NOLOCK)
               WHERE codigo_IAM_fundo = '{cod_fund}' and date = '{data_ref}' and codigo_iam_ativo in ({cod_ativos_sql})
               GROUP BY date, codigo_IAM_fundo, codigo_IAM_ativo, est1, est2, est3, est4, est5"""
    pos_estrat = select_from_db(sSQL, _USERNAME_SQL, _PASSWORD_SQL, _DB_NAME)

    pos_estrat['Qtd'] = pos_estrat['quantidade']
    pos_estrat.loc[pos_estrat['quantidade'] == 0, 'Qtd'] = pos_estrat['quantidade_abertura']
    pos_estrat = pos_estrat.drop(
        pos_estrat[(pos_estrat['quantidade'] == 0) & (pos_estrat['quantidade_abertura'] == 0)].index
    )

    total_qtd = pos_estrat.groupby(
        by=['date', 'codigo_IAM_fundo', 'codigo_IAM_ativo'], as_index=False, sort=False
    ).agg(Qtd_total=('Qtd', 'sum'))
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
    df_temp3 = pos_estrat[pos_estrat['Qtd_total'] != 0]
    df_temp2 = pos_estrat[pos_estrat['Qtd_total'] == 0]
    df_temp2['Trades'] = np.where(
        (df_temp2['quantidade'] != df_temp2['quantidade_abertura']), 'Sim', 'Nao'
    )
    df_temp2.loc[df_temp2['Trades'] == 'Sim', 'DifPnLEstrat'] = df_temp2['DifPnL']
    df_temp2 = df_temp2.drop(df_temp2[df_temp2['Trades'] == 'Nao'].index)

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
    return pos_estrat.reindex(columns=[
        'date', 'codigo_IAM_fundo', 'codigo_IAM_ativo', 'Tipo',
        'est1', 'est2', 'est3', 'est4', 'est5', 'DifPnLEstrat',
    ])


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # data_ref = '2026-06-18'
    data_ref = ql.Brazil().advance(ql.Date.from_date(date.today()), ql.Period('-1d')).to_date().strftime('%Y-%m-%d')
    print('Data Referencia:', data_ref)
    print(data_ref)
    # quit()

    ta_string = data_ref.replace('-', '')
    fundo_sql = _to_sql_list(_LISTA_FUNDOS)

    # Batimento check
    df_batimento = _fetch_batimento(data_ref)
    if df_batimento.empty:
        print('Sem diferenças no batimento para a data e critérios informados. Encerrando.')
        quit()
    print(f'Diferenças encontradas no batimento: {len(df_batimento)} registros')

    # Outros financeiro
    df_outros = _fetch_outros(data_ref)
    print(f'Outros financeiro/bps: {len(df_outros)} registros')

    # PnL totais por tipo
    Total_SSnC = _fetch_total_ssnc(data_ref, fundo_sql)
    Total_IAM  = _fetch_total_iam(data_ref, fundo_sql)

    # Diferenças por tipo de ativo
    Dif_Acao  = _fetch_dif_acoes(data_ref, fundo_sql)
    Dif_Fut   = _fetch_dif_futuros(data_ref, fundo_sql)
    Dif_Opt   = _fetch_dif_opcoes(data_ref, fundo_sql)
    Dif_Fixed = _fetch_dif_fixed(data_ref, fundo_sql)
    Dif_CPR   = _fetch_dif_cpr(data_ref, fundo_sql)

    # Resumo total do fundo
    df_resumo = pd.merge(Total_IAM, Total_SSnC, how='outer', on=['date', 'codigo_IAM_fundo', 'Tipo'])
    df_resumo.fillna(0, inplace=True)
    df_resumo['Dif'] = df_resumo['PnL_SSnC'] - df_resumo['PnL_IAM']
    df_resumo.sort_values(by=['Tipo', 'codigo_IAM_fundo'], inplace=True, ascending=True)

    # Consolidado de diferenças
    df_Difs = pd.concat([Dif_Opt, Dif_Fut, Dif_Acao, Dif_CPR, Dif_Fixed])
    df_Difs['Dif_preco_D1'] = df_Difs['BegLocalMarketPrice'] - df_Difs['preco_limpo_d1']
    df_Difs['Dif_preco']    = df_Difs['EndLocalMarketPrice'] - df_Difs['preco_limpo']
    df_Difs.sort_values(by=['Tipo', 'codigo_IAM_ativo', 'codigo_IAM_fundo'], inplace=True, ascending=True)
    df_Difs = df_Difs.reindex(columns=[
        'date', 'codigo_IAM_fundo', 'codigo_IAM_ativo', 'Tipo',
        'BegQty', 'EndQty', 'TotalBookPL', 'quantidade', 'pnl_total',
        'Ticker', 'DifQtd', 'DifPnL', 'Dif_preco', 'Dif_preco_D1',
        'BegLocalMarketPrice', 'preco_limpo_d1', 'EndLocalMarketPrice', 'preco_limpo',
    ])

    # PnL por estratégia
    df_estrat_fim = pd.concat([
        _calc_estrategia_fundo(cod_fund, df_Difs, data_ref)
        for cod_fund in df_Difs['codigo_IAM_fundo'].drop_duplicates()
    ])
    df_estrat_fim['DifPnLEstrat'] = df_estrat_fim['DifPnLEstrat'].astype('int').round(0)

    # Join CPR com estratégia
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

    df_estrat_fim['count'] = 1
    df_estrat_fim['count'] = df_estrat_fim.groupby(
        ['codigo_IAM_fundo', 'codigo_IAM_ativo']
    )['count'].transform('sum')

    if not _BATIMENTO_PRECO:
        df_Difs.drop(
            columns=['Dif_preco_D1', 'Dif_preco', 'BegLocalMarketPrice', 'preco_limpo_d1',
                     'EndLocalMarketPrice', 'preco_limpo'],
            inplace=True,
        )

    # Exportar para Excel
    agora = datetime.datetime.now()
    data_hora_atual = agora.strftime("%Y-%m-%d_%H-%M-%S")

    pasta_data = pathlib.Path(f"../output/batimento_off/renda_fixa/{ta_string}")
    pasta_data.mkdir(parents=True, exist_ok=True)

    file_path = pasta_data / f"ResumoMartelo_{data_hora_atual}_2.xlsx"
    with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
        df_resumo.to_excel(writer, sheet_name='Resumo', index=False, freeze_panes=(1, 0))
        df_Difs.to_excel(writer, sheet_name='Ativos', index=False, freeze_panes=(1, 0))
        df_estrat_fim.to_excel(writer, sheet_name='PnLEstrategia', index=False, freeze_panes=(1, 0))

        if len(df_estrat_fim) > 0:
            mask_verificar   = df_estrat_fim['est1'] == 'VERIFICAR'
            df_verificar     = df_estrat_fim.loc[mask_verificar, :]
            df_sem_verificar = df_estrat_fim.loc[~mask_verificar, :]
            df_verificar.to_excel(writer, sheet_name='VerificarPnL', index=False, freeze_panes=(1, 0))
            df_sem_verificar.to_excel(writer, sheet_name='SemVerificarPnL', index=False, freeze_panes=(1, 0))

    print(rf"Arquivo Salvo: {file_path}")
    os.startfile(file_path)

    file_path_outros = pasta_data / f"OutrosFinanceiro_{data_hora_atual}.xlsx"
    with pd.ExcelWriter(file_path_outros, engine='xlsxwriter') as writer:
        df_outros.to_excel(writer, sheet_name='OutrosFinanceiro', index=False, freeze_panes=(1, 0))
    print(rf"Arquivo Salvo: {file_path_outros}")
    os.startfile(file_path_outros)


if __name__ == '__main__':
    main()
