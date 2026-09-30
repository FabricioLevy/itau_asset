# Esse script vai montar o ATT
import argparse
from datetime import date, datetime, timedelta
import urllib
import pandas as pd
import sqlalchemy as sa
import re
import numpy as np
import sys
import os
import pathlib
import unicodedata
import glob
from openpyxl import load_workbook
import win32com.client as win32
import xlwings as xw

folder = pathlib.Path().resolve().parent.name

if (folder == 'bases-fundos-iam'):
    sys.path.append("../")
    filePathRunJson = '..'
    filePath = '..'  # [FIX] filePath ficava indefinido nesse ramo
else:
    filePath = os.environ.get('BASES_FUNDOS_IAM_FILE_PATH')
    sys.path.append(filePath)
    filePathRunJson = os.environ.get('BASES_FUNDOS_IAM_FILE_PATH')

from Funcoes.LakeConn import Conn, ConnEngine, db_insert_frame
from config.Config import get_global_config
from qs_utils.qsdate import QsDate

import json
from CLog.log import log_iam

from ScriptsPersonalizados.Relatorios_estruturados.get_cota_mercado import get_cota_mercado

conn = Conn()

dict_fundos_nomes = {'INTITAUFIIAGRO': 'RURA11',
                     'ITAUFICFIDCINF': 'IFRA11',
                     'ITAUINFCDIRF': 'IFRI11',
                     'INTITAUCRIFII': 'ICRI11',
                     'ITISENTOMAR29': 'ISEN11',
                     'ITISENTOSET29': 'ISTT11',
                     'ITISENTOSET28': 'ISET11',
                     'ITISENTOMAR28': 'ISNT11',
                     'ITISENTOMAR30': 'ISNN11'}

LISTA_FUNDOS_ISENTOS = ['ITISENTOMAR29', 'ITISENTOSET28', 'ITISENTOSET29',
                        'ITISENTOMAR28', 'ITISENTOMAR30']

# ITAUBAs FIP: só geram a tabela de saída (consolidador_infos_isen_dif).
# Fundos com a mesma data e cota inicial têm a mesma tabela, então saem juntos num PDF só
LISTA_FUNDOS_ITAUBA_FIP = ['ITAUBAFIPSEN1_3', 'ITAUBAFIPSEN2', 'ITAUBAFIPSEN4_6_7',
                           'ITAUBAFIPSEN5', 'ITAUBAFIPSEN8_9']

# fundos da comparação de histórico (fim da rotina diária e padrão do comando historico)
LISTA_FUNDOS_HISTORICO = ['ITAUFICFIDCINF', 'ITAUINFCDIRF', 'INTITAUCRIFII', 'ITISENTOSET28',
                          'ITISENTOMAR29', 'ITISENTOSET29', 'INTITAUFIIAGRO', 'ITISENTOMAR28',
                          'ITISENTOMAR30']

# [FIX] caminho da planilha compartilhada de yields dos ITAUBAs
PATH_ITAUBAS_YIELD = r"\\fswcorp\ceic\WMS\DCIGI\SISTEMAS\GRUP\PESQUANT\_Publico\ITAUBA\ITAUBAs_yield.xlsx"


def get_cota_mercado_b3(nome, date_ref):
    if date_ref == '2025-12-31':
        date_ref = '2025-12-30'
    sql = f"""
        select reportdate as date, a.tickersymbol as ticker_ativo, lastprice as preco_limpo, financialinstrumentquantity as volume
        from rt2_ai6_imm9820_tif_001 (nolock) as a

        where 1=1--a.lastprice is not null
        and reportdate = '{date_ref}'
        and a.tickersymbol in ('{nome}')
    """
    df = pd.read_sql(sql, conn)

    # retornar a cota
    return df['preco_limpo'].values[0]


def truncate(valor, casas_decimais):
    fator = 10 ** casas_decimais
    return int(valor * fator) / fator


def get_posicao_rf(date_ref, lista_fundos):
    query_fundos = "('" + "','".join(lista_fundos) + "')"

    sql = f"""
        select a.codigo_IAM_fundo, codigo_IAM_fundo_origem,codigo_IAM_ativo, ativo, indexador, taxa, taxa_emissao, quantidade, preco_limpo, total,
        spread_cdi, spread_ipca, spread_equivalente, perc_pl, macaulay_duration, d.valor as spread_ntnb_equivalente, ntnb_referencia,spread_ntnb
        from vw_fundos_posicao_explodida_down (nolock) as a
        LEFT JOIN FUNDOS_DADOS_FUNDOS (nolock) AS d ON a.date = d.date AND a.codigo_IAM_fundo = d.codigo_IAM_fundo AND d.metrica = 'SPREAD_NTNB_EQUIVALENTE'
        where a.date = '{date_ref}' and a.codigo_IAM_fundo in {query_fundos}
        and codigo_IAM_fundo_origem NOT LIKE '%PIR%' and codigo_IAM_ativo not in ('INITAUPIRIIMEZ')
        and (tipo = 'Fixed Income' or codigo_IAM_ativo='caixa_brl' or (tipo='Fund'))
    """
    df = pd.read_sql(sql, conn)

    if df.empty:  # [FIX] evita quebrar nas operacoes de string abaixo
        return df, pd.DataFrame(columns=df.columns)

    df_caixa = df[(df['codigo_IAM_ativo'] == 'caixa_brl')
                  | df['ativo'].str.contains('LFT', case=False)
                  | (df['ativo'].str.contains('Over', case=False))
                  | df['codigo_IAM_ativo'].isin(['ZERARF54582', 'FIDELILCMM771'])]

    # pegando o benchmark dos fundos
    sql = f"""
        select codigo_IAM_fundo, cota,benchmark, patrimonio, qt_cotas from vw_fundos_cotas_pl (nolock)
        where codigo_IAM_fundo in {query_fundos}
        and date = '{date_ref}'
    """

    df_benchmark = pd.read_sql(sql, conn)

    df = df.merge(df_benchmark, on='codigo_IAM_fundo', how='left')

    # Tratando casos em PDD
    sql_pdd = f"""select cad.date_change, cad.codigo_IAM_ativo, 'PDD' as marcado from FUNDOS_CADASTRO_ATIVOS AS CAD
            left join FUNDOS_CADASTRO_ATIVOS as cad_tipo on cad_tipo.codigo_IAM_ativo = cad.codigo_IAM_ativo and cad_tipo.campo = 'TIPO_PDD'
            where CAD.campo = 'PDD' and cad.date_change <= '{date_ref}' order by cad.codigo_IAM_ativo, cad.date_change
            """
    df_pdd = pd.read_sql(sql_pdd, conn)
    # Pegando o mais atualizado
    df_pdd = df_pdd.groupby(["codigo_IAM_ativo"]).tail(1)
    df_pdd.drop(columns=['date_change'], inplace=True)

    df = df.merge(df_pdd, on='codigo_IAM_ativo', how='left')
    df = df[df['marcado'] != 'PDD']
    df.drop(columns=['marcado'], inplace=True)
    df.reset_index(drop=True, inplace=True)

    df['spread'] = np.nan
    if len(df_caixa.loc[(df_caixa['ativo'].str.contains('Over', case=False) & (df_caixa['total'] > 0))]) > 0:
        taxa_over = df.loc[(df['ativo'].str.contains('Over', case=False) & (df['total'] > 0)), 'spread_ipca'].values[0]
        df.loc[df['codigo_IAM_ativo'].isin(df_caixa.loc[df_caixa['codigo_IAM_ativo'] != 'caixa_brl', 'codigo_IAM_ativo']), 'spread_ipca'] = taxa_over

    # se benchmark for cdi, pega o spread_cdi
    df['spread'] = np.where(df['benchmark'] == 'CDI', df['spread_cdi'], df['spread_equivalente'])
    # se benchmark ipca, pega o spread ipca
    df['spread'] = np.where(df['benchmark'] == 'IMA_B', df['spread_ipca'], df['spread'])
    # se benchmark ipca_ajustado, pega o spread ipca
    df['spread'] = np.where(df['benchmark'] == 'IPCA_Ajustado', df['spread_ipca'], df['spread'])

    df['spread_pond'] = df['spread'] * df['perc_pl'] / 100
    df['duration_pond'] = df['macaulay_duration'] * df['perc_pl']
    df['spread_ntnb_pond'] = df['spread_ntnb'] * df['perc_pl'] / 100

    return df, df_caixa


def get_infos_complementares(date_ref, lista_fundos):
    lista_fundos = ",".join(f"'{fundo}'" for fundo in lista_fundos)
    sql = f"""
        select codigo_IAM_fundo, valor_num/100 as taxa_adm from view_fundos_cadastro_fundos_last_values
        where campo = 'TaxaAdmCobrada' and codigo_IAM_fundo in ({lista_fundos})
    """
    df = pd.read_sql(sql, conn)

    return df


def get_rentabilidade_dia(date_ref, lista_fundos):
    lista_fundos = ",".join(f"'{fundo}'" for fundo in lista_fundos)
    sql = f"""
        select codigo_IAM_fundo, 10000*fundo_pnl_perc rentabilidade_dia from VW_FUNDOS_COTAS_PL
        where date = '{date_ref}' and codigo_IAM_fundo in ({lista_fundos})
    """
    df = pd.read_sql(sql, conn)

    return df


def get_ntnb_ref(date_ref, duration):
    sql = f"""
        select d.date, d.macaulay_duration, cad.valor_date as data_ntnb , taxa/100 as taxa_ntnb
        from fundos_dados_ativos as d
        left join fundos_cadastro_ativos as cad on d.codigo_iam_ativo = cad.codigo_iam_ativo and cad.campo = 'vencimento'
        left join fundos_cadastro_ativos as cad2 on d.codigo_iam_ativo = cad2.codigo_iam_ativo and cad2.campo = 'ticker_bolsa'
        where d.codigo_IAM_ativo like '%BRSTNCNTB%' AND LEN(d.codigo_IAM_ativo) <=12  and cad2.valor_str not like 'NTNBP %'
        and date = '{date_ref}'
        and d.macaulay_duration is not null
    """
    df = pd.read_sql(sql, conn)

    def find_closest_value(arr, value):
        idx = (np.abs(arr - value)).argmin()
        return arr[idx]

    df['closest_value'] = find_closest_value(df['macaulay_duration'].values, duration)

    df = df[df['macaulay_duration'] == df['closest_value'].values[0]]
    df.reset_index(drop=True, inplace=True)
    taxa = df.taxa_ntnb.values[0]

    return taxa


def calcula_infos(date_ref=None, lista_fundos=[]):
    nomes = [dict_fundos_nomes.get(fundo, fundo) for fundo in lista_fundos]

    dict_cota_mercado = {}
    for nome in nomes:
        print(nome)
        cota_mercado = get_cota_mercado_b3(nome, date_ref)
        dict_cota_mercado[nome] = cota_mercado

    df, df_caixa = get_posicao_rf(date_ref, lista_fundos)

    if df.empty:
        print(f"\n⚠️  AVISO: Nenhuma posição encontrada para a data {date_ref}")
        print(f"Fundos afetados: {lista_fundos}")
        return pd.DataFrame(), pd.DataFrame()

    # somar perc pl por fundo
    df_caixa = df_caixa.groupby(['codigo_IAM_fundo']).agg({'perc_pl': 'sum'}).reset_index()

    df_spread = df.groupby(['codigo_IAM_fundo', 'patrimonio', 'qt_cotas', 'cota']).agg(
        {'spread_pond': 'sum', 'spread_ntnb_pond': 'sum'}).reset_index()
    df_duration = df.groupby(['codigo_IAM_fundo', 'patrimonio', 'qt_cotas', 'cota']).agg(
        {'duration_pond': 'sum'}).reset_index()
    durations_afetadas = df.loc[df['macaulay_duration'].isna(),
                                ['codigo_IAM_fundo', 'codigo_IAM_ativo', 'ativo']].drop_duplicates()

    # get_ntnb ref
    if len(df_duration) > 0:
        taxa_ntnb = get_ntnb_ref(date_ref, df_duration['duration_pond'].values[0])
    else:
        print(f"\n⚠️  AVISO: Nenhum dado de duration encontrado para a data {date_ref}")
        if durations_afetadas.empty:
            print(f"Fundos sem posições para cálculo: {lista_fundos}")
        else:
            print("Ativos com duration ausente:")
            print(durations_afetadas.to_string(index=False))
        resposta = input("Deseja continuar com taxa_ntnb = 0? (s/n): ").strip().lower()
        if resposta == 's':
            print("Continuando com taxa_ntnb = 0")
            taxa_ntnb = 0
        else:
            print("Operação cancelada pelo usuário.")
            return pd.DataFrame(), pd.DataFrame()

    df_duration['duration_pond'] = df_duration['duration_pond'] / 252
    df_infos = get_infos_complementares(date_ref, lista_fundos)

    df_fim = df_caixa.merge(df_spread, on='codigo_IAM_fundo', how='left')
    df_fim = df_fim.merge(df_duration, on=['codigo_IAM_fundo', 'patrimonio', 'qt_cotas', 'cota'], how='left')
    df_fim = df_fim.merge(df_infos, left_on='codigo_IAM_fundo', right_on='codigo_IAM_fundo', how='left')

    df_fim['nome_mercado'] = df_fim['codigo_IAM_fundo'].map(dict_fundos_nomes)
    df_fim['cota_mercado'] = df_fim['nome_mercado'].map(dict_cota_mercado)

    df_fim['agio_patrimonial'] = df_fim['cota_mercado'] / df_fim['cota'] - 1

    df_cotas_ficticias = pd.DataFrame()
    df_cotas_ficticias_json = pd.DataFrame()

    for fundo in df.codigo_IAM_fundo.unique().tolist():
        df_fundo = df_fim[df_fim['codigo_IAM_fundo'] == fundo].copy()
        df_fundo = df_fundo[['codigo_IAM_fundo', 'cota_mercado']]
        df_fundo_json = df_fundo.copy()

        for i in range(-6, 9):
            passo = 0.25 if fundo in ['INTITAUFIIAGRO', 'ITAUINFCDIRF'] else 0.50
            df_fundo1 = pd.DataFrame({'codigo_IAM_fundo': [fundo],
                                      'cota_mercado': [df_fundo['cota_mercado'].values[0] + i * passo]})
            df_fundo = pd.concat([df_fundo, df_fundo1], ignore_index=True)

        for i in range(-30, 45):
            passo = 0.05 if fundo in ['INTITAUFIIAGRO', 'ITAUINFCDIRF'] else 0.10
            df_fundo1 = pd.DataFrame({'codigo_IAM_fundo': [fundo],
                                      'cota_mercado': [df_fundo_json['cota_mercado'].values[0] + i * passo]})
            df_fundo_json = pd.concat([df_fundo_json, df_fundo1], ignore_index=True)

        df_fundo.drop_duplicates(inplace=True)
        df_fundo_json.drop_duplicates(inplace=True)
        df_cotas_ficticias = pd.concat([df_cotas_ficticias, df_fundo])
        df_cotas_ficticias_json = pd.concat([df_cotas_ficticias_json, df_fundo_json])

    df_fim_json = df_fim.copy()
    df_fim = df_cotas_ficticias.merge(df_fim, on='codigo_IAM_fundo', how='left')
    df_fim_json = df_cotas_ficticias_json.merge(df_fim_json, on='codigo_IAM_fundo', how='left')

    df_fim['taxa_ntnb'] = taxa_ntnb
    df_fim_json['taxa_ntnb'] = taxa_ntnb

    # cobranca pfee para o agro
    df_fim['pfee'] = np.where(df_fim['codigo_IAM_fundo'] == 'INTITAUFIIAGRO',
                              (df_fim['spread_pond'] - 0.01 - df_fim['taxa_adm']) * 0.2, 0)
    df_fim_json['pfee'] = np.where(df_fim_json['codigo_IAM_fundo'] == 'INTITAUFIIAGRO',
                                   (df_fim_json['spread_pond'] - 0.01 - df_fim_json['taxa_adm']) * 0.2, 0)

    # calcular spread liquido
    df_fim['spread_liquido'] = df_fim['spread_pond'] - df_fim['pfee'] - df_fim['taxa_adm']
    df_fim['spread_ntnb_liquido'] = df_fim['spread_ntnb_pond'] - df_fim['pfee'] - df_fim['taxa_adm']
    df_fim_json['spread_liquido'] = df_fim_json['spread_pond'] - df_fim_json['pfee'] - df_fim_json['taxa_adm']
    df_fim_json['spread_ntnb_liquido'] = df_fim_json['spread_ntnb_pond'] - df_fim_json['pfee'] - df_fim_json['taxa_adm']

    # taxa ate vencimento
    df_fim['spread_vencimento'] = (1 + df_fim['spread_liquido']) ** df_fim['duration_pond'] - 1
    df_fim['cota_vencimento'] = df_fim['cota'] * (1 + df_fim['spread_vencimento'])
    df_fim_json['spread_vencimento'] = (1 + df_fim_json['spread_liquido']) ** df_fim_json['duration_pond'] - 1
    df_fim_json['cota_vencimento'] = df_fim_json['cota'] * (1 + df_fim_json['spread_vencimento'])

    df_fim['agio_desagio'] = (df_fim['cota_vencimento'] / df_fim['cota_mercado_x']) - 1
    df_fim['spread_mercado'] = (1 + df_fim['agio_desagio']) ** (1 / df_fim['duration_pond']) - 1
    df_fim_json['agio_desagio'] = (df_fim_json['cota_vencimento'] / df_fim_json['cota_mercado_x']) - 1
    df_fim_json['spread_mercado'] = (1 + df_fim_json['agio_desagio']) ** (1 / df_fim_json['duration_pond']) - 1

    df_fim['cota_vencimento_ntnb'] = df_fim['cota'] * (1 + df_fim['spread_ntnb_liquido'])
    df_fim['spread_mercado_ntnb'] = ((df_fim['cota_vencimento_ntnb'] / df_fim['cota_mercado_x'])) ** (1 / df_fim['duration_pond']) - 1

    df_fim_json['cota_vencimento_ntnb'] = df_fim_json['cota'] * (1 + df_fim_json['spread_ntnb_liquido'])
    df_fim_json['spread_mercado_ntnb'] = ((df_fim_json['cota_vencimento_ntnb'] / df_fim_json['cota_mercado_x'])) ** (1 / df_fim_json['duration_pond']) - 1

    df_fim.drop(columns=['cota_vencimento_ntnb'], inplace=True)
    df_fim_json.drop(columns=['cota_vencimento_ntnb'], inplace=True)
    df_fim.sort_values(by=['codigo_IAM_fundo', 'cota_mercado_x'], inplace=True)
    df_fim_json.sort_values(by=['codigo_IAM_fundo', 'cota_mercado_x'], inplace=True)

    df_fim = df_fim[['codigo_IAM_fundo', 'cota_mercado_x', 'perc_pl', 'patrimonio', 'qt_cotas', 'cota',
                     'spread_pond', 'duration_pond', 'taxa_adm', 'nome_mercado', 'cota_mercado_y',
                     'agio_patrimonial', 'taxa_ntnb', 'pfee', 'spread_liquido', 'spread_vencimento',
                     'cota_vencimento', 'agio_desagio', 'spread_mercado', 'spread_ntnb_liquido',
                     'spread_mercado_ntnb']]

    return df_fim, df_fim_json


def calcula_info_isentos(date_ref=None, lista_fundos=[]):
    nomes = [dict_fundos_nomes.get(fundo, fundo) for fundo in lista_fundos]

    dict_cota_mercado = {}
    for nome in nomes:
        print(nome)
        cota_mercado = get_cota_mercado_b3(nome, date_ref)
        dict_cota_mercado[nome] = cota_mercado

    df, df_caixa = get_posicao_rf(date_ref, lista_fundos)

    if df.empty:  # [FIX] retorna vazio de forma consistente (3 objetos)
        print(f"\n AVISO: Nenhuma posição encontrada para a data {date_ref}")
        print(f"Fundos afetados: {lista_fundos}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df_caixa = df_caixa.groupby(['codigo_IAM_fundo']).agg({'perc_pl': 'sum'}).reset_index()

    df = df[['codigo_IAM_fundo', 'patrimonio', 'qt_cotas', 'cota']].copy()
    df.drop_duplicates(inplace=True)

    # [FIX] parametros por fundo em dicionario, evita variaveis vazando do loop
    params_isentos = {
        'ITISENTOMAR29': ('2029-03-29', 'ODJ29 Comdty', 0.96),
        'ITISENTOSET28': ('2028-09-18', 'ODV28 Comdty', 0.95),
        'ITISENTOSET29': ('2029-09-20', 'ODV29 Comdty', 0.955),
        'ITISENTOMAR28': ('2028-03-31', 'ODJ28 Comdty', 0.95),
        'ITISENTOMAR30': ('2028-03-31', 'ODJ28 Comdty', 0.95),
    }

    data_consulta = '2025-12-30' if date_ref == '2025-12-31' else date_ref

    duration = None
    spread = None
    spread_marcado_carteira = None

    for fundo in lista_fundos:
        if fundo not in params_isentos:
            raise ValueError(f"Fundo isento sem parametrizacao: {fundo}")

        venc, ticker, fator = params_isentos[fundo]
        duration = QsDate(date_ref).business_days_diff(venc) - 2

        sql = f"select DATE,TICKER,valor_num from BBG_INTEREST_RATE where TICKER='{ticker}' and CAMPO='PX_LAST' and date='{data_consulta}' order by DATE"
        spread_df = pd.read_sql(sql, conn)
        spread = spread_df['valor_num'].values[0] / 100
        spread_marcado_carteira = fator * spread

    df_fim = df_caixa.merge(df, on='codigo_IAM_fundo', how='left')
    df_fim['duration_pond'] = duration / 252
    df_fim['spread_liquido'] = spread_marcado_carteira

    df_fim['nome_mercado'] = df_fim['codigo_IAM_fundo'].map(dict_fundos_nomes)
    df_fim['cota_mercado'] = df_fim['nome_mercado'].map(dict_cota_mercado)
    df_fim['cota_mercado'] = df_fim['cota']

    df_fim['agio_patrimonial'] = df_fim['cota_mercado'] / df_fim['cota'] - 1

    df_cotas_ficticias = pd.DataFrame()
    df_cotas_ficticias_json = pd.DataFrame()

    for fundo in df.codigo_IAM_fundo.unique().tolist():
        df_fundo = df_fim[df_fim['codigo_IAM_fundo'] == fundo].copy()
        df_fundo = df_fundo[['codigo_IAM_fundo', 'cota_mercado']]
        df_fundo_json = df_fundo.copy()

        for i in range(-3, 18):
            if fundo in ['ITISENTOMAR29']:
                passo = 0.3
            elif fundo in ['ITISENTOSET28']:
                passo = 0.2
            else:
                passo = 1.5
            df_fundo1 = pd.DataFrame({'codigo_IAM_fundo': [fundo],
                                      'cota_mercado': [df_fundo['cota_mercado'].values[0] + i * passo]})
            df_fundo = pd.concat([df_fundo, df_fundo1], ignore_index=True)

        for i in range(-20, 80):
            if fundo in ['ITISENTOMAR29']:
                passo = 0.04
            elif fundo in ['ITISENTOSET28']:
                passo = 0.03
            else:
                passo = 0.30
            df_fundo1 = pd.DataFrame({'codigo_IAM_fundo': [fundo],
                                      'cota_mercado': [df_fundo_json['cota_mercado'].values[0] + i * passo]})
            df_fundo_json = pd.concat([df_fundo_json, df_fundo1], ignore_index=True)

        df_fundo.drop_duplicates(inplace=True)
        df_fundo_json.drop_duplicates(inplace=True)
        df_cotas_ficticias = pd.concat([df_cotas_ficticias, df_fundo])
        df_cotas_ficticias_json = pd.concat([df_cotas_ficticias_json, df_fundo_json])

    df_fim_json = df_fim.copy()
    df_fim = df_cotas_ficticias.merge(df_fim, on='codigo_IAM_fundo', how='left')
    df_fim_json = df_cotas_ficticias_json.merge(df_fim_json, on='codigo_IAM_fundo', how='left')

    # taxa ate vencimento
    df_fim['spread_patrimonial'] = spread_marcado_carteira / spread
    df_fim['spread_vencimento'] = (1 + df_fim['spread_liquido']) ** df_fim['duration_pond'] - 1
    df_fim['cota_vencimento'] = df_fim['cota'] * (1 + df_fim['spread_vencimento'])
    df_fim_json['spread_vencimento'] = (1 + df_fim_json['spread_liquido']) ** df_fim_json['duration_pond'] - 1
    df_fim_json['cota_vencimento'] = df_fim_json['cota'] * (1 + df_fim_json['spread_vencimento'])

    df_fim['agio_desagio'] = (df_fim['cota_vencimento'] / df_fim['cota_mercado_x']) - 1
    df_fim['spread_mercado'] = (1 + df_fim['agio_desagio']) ** (1 / df_fim['duration_pond']) - 1
    df_fim['spread_mercado_gross'] = ((1 + df_fim['agio_desagio'] / 0.85)) ** (1 / df_fim['duration_pond']) - 1
    df_fim_json['agio_desagio'] = (df_fim_json['cota_vencimento'] / df_fim_json['cota_mercado_x']) - 1
    df_fim_json['spread_mercado'] = (1 + df_fim_json['agio_desagio']) ** (1 / df_fim_json['duration_pond']) - 1
    df_fim_json['spread_mercado_gross'] = ((1 + df_fim_json['agio_desagio'] / 0.85)) ** (1 / df_fim_json['duration_pond']) - 1

    df_fim['spread_mercado'] = df_fim['spread_mercado'] / spread
    df_fim['spread_mercado_gross'] = df_fim['spread_mercado_gross'] / spread
    df_fim_json['spread_mercado'] = round(df_fim_json['spread_mercado'] / spread, 4)
    df_fim_json['spread_mercado_gross'] = round(df_fim_json['spread_mercado_gross'] / spread, 4)

    df_fim.sort_values(by=['codigo_IAM_fundo', 'cota_mercado_x'], inplace=True)
    df_fim_json.sort_values(by=['codigo_IAM_fundo', 'cota_mercado_x'], inplace=True)

    df_conta_excel = df_fim[df_fim['cota_mercado_x'] == df_fim['cota']]
    df_conta_excel = df_conta_excel[['codigo_IAM_fundo', 'cota_mercado_x', 'cota', 'spread_liquido',
                                     'spread_patrimonial', 'duration_pond', 'cota_vencimento']]
    return df_fim, df_fim_json, df_conta_excel


def calcula_saida_isentos(date_ref=None, lista_fundos=[]):
    df_fim = pd.DataFrame()

    # [FIX] parametros por fundo em dicionario
    params_saida = {
        'ITISENTOMAR29': ('2025-06-05', 100),
        'ITISENTOSET28': ('2025-06-11', 100),
        'ITISENTOSET29': ('2025-08-27', 1000),
        'ITISENTOMAR28': ('2025-11-17', 1035.16),
        'ITISENTOMAR30': ('2025-12-23', 1012.12),
        'ITAUBAFIPSEN1_3': ('2026-05-08', 1006.54),
        'ITAUBAFIPSEN2': ('2026-04-29', 1003.538),
        'ITAUBAFIPSEN4_6_7': ('2026-06-26', 1009.327),
        'ITAUBAFIPSEN5': ('2026-06-19', 1006.892),
        'ITAUBAFIPSEN8_9': ('2026-07-17', 1002.419),
    }

    for fundo in lista_fundos:
        if fundo not in params_saida:
            raise ValueError(f"Fundo isento sem parametrizacao de saida: {fundo}")

        ini_date, cota_ini = params_saida[fundo]

        # liquidação em D+1 para os ITAUBAs FIP e D+2 para os demais, com D = data da tabela (date_ref + 1)
        prazo_liq = 1 if fundo in LISTA_FUNDOS_ITAUBA_FIP else 2
        dias_ate_liq = 1 + prazo_liq  # dias úteis de date_ref até a liquidação

        date_liq = QsDate(date_ref).add_business_days(dias_ate_liq)
        dif = abs(date_liq.business_days_diff(ini_date))

        sql = f"""
                SELECT date, codigo_IAM_indice, preco_limpo, pnl_perc
                from FUNDOS_DADOS_INDICES (nolock)
                where 1=1 and (date='{ini_date}' or date='{date_ref}')
                and codigo_IAM_indice = 'CDIAcumulado'
                order by date
            """
        df_cdi = pd.read_sql(sql, conn)

        rentabilidade_100 = truncate(df_cdi['preco_limpo'].values[-1] / df_cdi['preco_limpo'].values[0], 8)
        rentab_liq_100 = (1 + df_cdi['pnl_perc'].values[-1]) ** dias_ate_liq
        rent_100cdi = (rentabilidade_100) * (rentab_liq_100) - 1

        # diarizar rentab 100
        rent_100_cdi_dia = (1 + rent_100cdi) ** (1 / dif) - 1
        rent_93cdi = (1 + rent_100_cdi_dia * 0.93) ** (dif) - 1

        # ITAUBAs FIP não pagam emolumentos
        emol = 1.0 if fundo in LISTA_FUNDOS_ITAUBA_FIP else 1.0003

        # cota hoje
        cota = truncate(cota_ini * (1 + rent_93cdi) * emol, 2) + 0.01

        df = pd.DataFrame()

        faixa = range(-10, 11) if fundo in ['ITISENTOMAR29', 'ITISENTOSET28'] else range(-15, 15)
        for i in faixa:
            cota_mercado = truncate(cota + i * 0.01, 2)
            rentab = cota_mercado / emol / cota_ini - 1

            df1 = pd.DataFrame({
                'codigo_IAM_fundo': [fundo],
                'cota_mercado': [cota_mercado],
                'rentabilidade': [rentab],
            })
            df = pd.concat([df, df1], ignore_index=True)

        df.reset_index(drop=True, inplace=True)
        df.drop_duplicates(inplace=True)

        df['cdi_perc'] = ((1 + df['rentabilidade']) ** (1 / dif) - 1) / ((1 + rent_100cdi) ** (1 / dif) - 1)
        df['cdi_perc_gross'] = df['cdi_perc'] / 0.85

        df_fim = pd.concat([df_fim, df], ignore_index=True)

    return df_fim


def append_to_excel(df, file_name):
    """[FIX] Apaga a aba antes de regravar.

    O `if_sheet_exists='overlay'` anterior escrevia por cima sem limpar,
    deixando linhas de execucoes antigas (ex.: fevereiro) abaixo do bloco
    novo. As abas PDF liam esse residuo.
    """
    df = df.reset_index(drop=True)

    fundo = df.codigo_IAM_fundo.iloc[0]
    sheet = 'Auxiliar_' + fundo

    book = load_workbook(file_name)
    if sheet in book.sheetnames:
        del book[sheet]
        book.save(file_name)
    book.close()

    with pd.ExcelWriter(
        file_name,
        engine='openpyxl',
        mode='a',
        if_sheet_exists='replace'
    ) as writer:
        df.to_excel(writer, sheet_name=sheet, index=False)


def calculate_formulas_excel(file_name):
    """[FIX] Usa uma instancia isolada e fecha sempre, mesmo em erro.

    Antes, `xw.Book()` podia anexar a uma instancia do Excel ja aberta com
    o arquivo em cache de uma rodada anterior.
    """
    app = xw.App(visible=False, add_book=False)
    app.display_alerts = False
    try:
        wb = app.books.open(os.path.abspath(file_name))
        app.calculate()
        wb.save()
        wb.close()
    finally:
        app.quit()


def export_PDF(wb_carteira, sheet_name, pdf_file_name):
    print('Exporta PDF - {}'.format(pdf_file_name))

    excel = win32.gencache.EnsureDispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    wb = excel.Workbooks.Open(os.path.abspath(wb_carteira))

    try:
        sheet = wb.Sheets[sheet_name]

        sheet.PageSetup.Zoom = False
        sheet.PageSetup.FitToPagesWide = 1
        sheet.PageSetup.Orientation = 1  # retrato (xlPortrait)

        sheet.ExportAsFixedFormat(0, os.path.abspath(pdf_file_name))
    finally:
        wb.Close(SaveChanges=False)  # [FIX] garante fechamento mesmo em erro
    return


def create_json(df, ticker, tipo='CDI', path=''):
    dict_json = {}

    dict_json['ticker'] = ticker
    if tipo == 'CDI':
        dict_json['nome_primeira_coluna'] = '(CDI+)'
    elif tipo == 'CDI_perc':
        dict_json['nome_primeira_coluna'] = '(CDI%)'
        dict_json['nome_segunda_coluna'] = '(CDI% - Gross-up)'
    else:
        dict_json['nome_primeira_coluna'] = 'Yield (IPCA+)'
        dict_json['nome_segunda_coluna'] = 'Spread (NTNB+)'

    dict_json['cota_patrimonial'] = df['cota'].values[0]
    dict_json['data_criacao'] = df['date'].values[0]
    dict_json['valores_colunas'] = []
    for index, row in df.iterrows():
        if tipo == 'CDI':
            dict_json['valores_colunas'].append(
                {'preco_mercado': row['cota_mercado_x'], 'primeira_coluna': row['spread_mercado']})
        elif tipo == 'CDI_perc':
            dict_json['valores_colunas'].append(
                {'preco_mercado': row['cota_mercado_x'], 'primeira_coluna': row['spread_mercado'],
                 'segunda_coluna': row['spread_mercado_gross']})
        else:
            dict_json['valores_colunas'].append(
                {'preco_mercado': row['cota_mercado_x'], 'primeira_coluna': row['spread_mercado'],
                 'segunda_coluna': row['spread_mercado_ntnb']})

    json_data = json.dumps(dict_json, indent=4)

    with open(path + f'dados_{ticker}.json', 'w') as json_file:
        json_file.write(json_data)


def union_all_json(date_ref=None):
    if date_ref is None:
        date_ref = str(QsDate(date.today()).add_business_days(-1))

    path = filePath + r'\ScriptsPersonalizados\Relatorios_estruturados\PDFs' + '\\'
    path_salvar = path
    json_files = glob.glob(path + 'dados_*.json')  # [FIX] nao reprocessa dados_combinados

    lista_dicionarios = []
    for json_file in json_files:
        if os.path.basename(json_file) == 'dados_combinados.json':
            continue
        with open(json_file, 'r') as f:
            try:
                data = json.load(f)
                lista_dicionarios.append(data)
            except json.JSONDecodeError as e:
                print(f"Erro ao processar o arquivo {json_file}: {e}")

    output_dir = path_salvar + date_ref + '\\'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(output_dir + 'dados_combinados.json', 'w') as output_file:
        json.dump(lista_dicionarios, output_file, indent=4)


def consolidador_infos(date_ref=None, lista_fundos=[], file_name=None, path=None):

    dict_nome_pdf = {'RURA11': 'Sensibilidade-RURA',
                     'IFRA11': 'cota-IFRA',
                     'IFRI11': 'Sensibilidade-IFRI',
                     'ICRI11': 'Sensibilidade ICRI',
                     'ISEN11': 'Sensibilidade-ISEN',
                     'ISNT11': 'Sensibilidade-ISNT',
                     'ISET11': 'Sensibilidade-ISET',
                     'ISNN11': 'Sensibilidade-ISNN',
                     'ISTT11': 'Sensibilidade-ISTT'}

    for fundo in lista_fundos:
        # [FIX] variavel local: date_ref nao e mais mutado.
        # entre fundos nem entre chamadas da funcao
        data_fundo = date_ref if date_ref is not None else str(QsDate(date.today()).add_business_days(-1))

        if fundo in LISTA_FUNDOS_ISENTOS:
            df, df_json, df_excel = calcula_info_isentos(data_fundo, [fundo])
            if df.empty or df_json.empty:
                print(f"Fundo {fundo} ignorado por falta de dados em {data_fundo}")
                continue
            df['date'] = data_fundo
            df_json['date'] = data_fundo
            df_excel['date'] = data_fundo

            # [FIX] grava o resumo na planilha compartilhada de yields dos ITAUBAs.
            # Isolado em try/except para que uma indisponibilidade do fileshare
            # nao derrube a geracao dos PDFs e dos JSONs.
            if not df_excel.empty:
                try:
                    append_to_excel(df_excel, PATH_ITAUBAS_YIELD)
                    print(f"ITAUBAs_yield atualizado para {fundo} ({data_fundo})")
                except Exception as e:
                    print(f"⚠️  Falha ao gravar em ITAUBAs_yield.xlsx para {fundo}: {e}")
            else:
                print(f"⚠️  df_excel vazio para {fundo}, nada gravado em ITAUBAs_yield.xlsx")
        else:
            df, df_json = calcula_infos(data_fundo, [fundo])
            if df.empty or df_json.empty:
                print(f"Fundo {fundo} ignorado por falta de dados em {data_fundo}")
                continue
            df['date'] = data_fundo
            df_json['date'] = data_fundo

        df_fundo = df[df['codigo_IAM_fundo'] == fundo].copy()
        df_fundo_json = df_json[df_json['codigo_IAM_fundo'] == fundo].copy()

        append_to_excel(df_fundo, file_name)

        nome_bonito = dict_fundos_nomes.get(fundo, fundo)

        output_path = path + data_fundo + '\\'
        if not os.path.exists(output_path):
            os.makedirs(output_path)

        calculate_formulas_excel(file_name)
        export_PDF(file_name, 'PDF_' + nome_bonito, output_path + dict_nome_pdf[nome_bonito] + '.pdf')

        # criar json
        if nome_bonito in ['RURA11', 'IFRI11']:
            create_json(df_fundo_json, nome_bonito, tipo='CDI', path=path)
        elif nome_bonito in ['ISEN11', 'ISET11', 'ISTT11', 'ISNT11', 'ISNN11']:
            create_json(df_fundo_json, nome_bonito, tipo='CDI_perc', path=path)
        else:
            create_json(df_fundo_json, nome_bonito, tipo='IPCA', path=path)


def consolidador_infos_isen_dif(date_ref=None, lista_fundos=[], file_name=None, path=None):

    dict_nome_pdf = {'ISEN11': 'Tabela de Sensibilidade Indicativa do Mercado Secundario-ISEN11',
                     'ISET11': 'Tabela de Sensibilidade Indicativa do Mercado Secundario-ISET11',
                     'ISTT11': 'Tabela de Sensibilidade Indicativa do Mercado Secundario-ISTT11',
                     'ISNT11': 'Tabela de Sensibilidade Indicativa do Mercado Secundario-ISNT11',
                     'ISNN11': 'Tabela de Sensibilidade Indicativa do Mercado Secundario-ISNN11',
                     'ITAUBAFIPSEN1_3': 'Tabela de Sensibilidade Indicativa do Mercado Secundario-ITAUBAFIPSEN1_3',
                     'ITAUBAFIPSEN2': 'Tabela de Sensibilidade Indicativa do Mercado Secundario-ITAUBAFIPSEN2',
                     'ITAUBAFIPSEN4_6_7': 'Tabela de Sensibilidade Indicativa do Mercado Secundario-ITAUBAFIPSEN4_6_7',
                     'ITAUBAFIPSEN5': 'Tabela de Sensibilidade Indicativa do Mercado Secundario-ITAUBAFIPSEN5',
                     'ITAUBAFIPSEN8_9': 'Tabela de Sensibilidade Indicativa do Mercado Secundario-ITAUBAFIPSEN8_9'}

    for fundo in lista_fundos:
        # [FIX] variavel local, mesmo motivo do consolidador_infos
        data_fundo = date_ref if date_ref is not None else str(QsDate(date.today()).add_business_days(-1))

        if fundo not in LISTA_FUNDOS_ISENTOS + LISTA_FUNDOS_ITAUBA_FIP:
            continue

        df = calcula_saida_isentos(data_fundo, [fundo])
        if df.empty:
            print(f"Fundo {fundo} ignorado por falta de dados em {data_fundo}")
            continue

        df['date'] = str(QsDate(data_fundo).add_business_days(1))

        df_fundo = df[df['codigo_IAM_fundo'] == fundo].copy()
        append_to_excel(df_fundo, file_name)

        nome_bonito = dict_fundos_nomes.get(fundo, fundo)

        output_path = path + data_fundo + '\\'
        if not os.path.exists(output_path):
            os.makedirs(output_path)

        calculate_formulas_excel(file_name)
        export_PDF(file_name, 'PDF_' + nome_bonito, output_path + dict_nome_pdf[nome_bonito] + '.pdf')


def compara_historico(date_ref=None, lista_fundos=[]):
    if date_ref is None:
        date_ref = str(QsDate(date.today()).add_business_days(-1))

    date_d3 = str(QsDate(date_ref).add_business_days(-5))

    caixa = pd.DataFrame({'codigo_IAM_fundo': []})
    spread = pd.DataFrame({'codigo_IAM_fundo': []})
    duration = pd.DataFrame({'codigo_IAM_fundo': []})
    rentabilidade = pd.DataFrame({'codigo_IAM_fundo': []})

    data = date_d3
    while data <= date_ref:
        df, df_caixa = get_posicao_rf(data, lista_fundos)

        if df.empty:
            data = str(QsDate(data).add_business_days(1))
            continue

        df_caixa = df_caixa.groupby(['codigo_IAM_fundo']).agg({'perc_pl': 'sum'}).reset_index()
        df_spread = df.groupby(['codigo_IAM_fundo', 'patrimonio', 'qt_cotas', 'cota']).agg({'spread_pond': 'sum'}).reset_index()
        df_spread['spread_pond'] = df_spread['spread_pond'].round(6)
        df_duration = df.groupby(['codigo_IAM_fundo', 'patrimonio', 'qt_cotas', 'cota']).agg({'duration_pond': 'sum'}).reset_index()
        df_duration['duration_pond'] = df_duration['duration_pond'] / 252

        df_rentab = get_rentabilidade_dia(data, lista_fundos)

        df_caixa.rename(columns={'perc_pl': data}, inplace=True)
        df_spread.rename(columns={'spread_pond': data}, inplace=True)
        df_spread = df_spread[['codigo_IAM_fundo', data]]
        df_duration.rename(columns={'duration_pond': data}, inplace=True)
        df_duration = df_duration[['codigo_IAM_fundo', data]]
        df_rentab.rename(columns={'rentabilidade_dia': data}, inplace=True)
        df_rentab = df_rentab[['codigo_IAM_fundo', data]]

        caixa = pd.merge(caixa, df_caixa, on='codigo_IAM_fundo', how='outer')
        spread = pd.merge(spread, df_spread, on=['codigo_IAM_fundo'], how='outer')
        duration = pd.merge(duration, df_duration, on=['codigo_IAM_fundo'], how='outer')
        rentabilidade = pd.merge(rentabilidade, df_rentab, on=['codigo_IAM_fundo'], how='outer')
        data = str(QsDate(data).add_business_days(1))

    print('Caixa')
    print(caixa)
    print('Spread')
    print(spread)
    print('Duration')
    print(duration)
    print('Rentabilidade')
    print(rentabilidade)

    spread.to_clipboard(decimal=',')


def rotina_diaria(file_name, file_name1, path):
    """Rotina completa do dia, na ordem de sempre (o que o main rodava antes)."""
    ## Rodar antes das 10h pois está em oferta
    consolidador_infos(date_ref=None, lista_fundos=['ITAUFICFIDCINF', 'ITAUINFCDIRF'],
                       file_name=file_name, path=path)

    # rodar junto porque não depende de base
    consolidador_infos_isen_dif(date_ref=None,
                                lista_fundos=['ITISENTOSET28', 'ITISENTOMAR29', 'ITISENTOSET29',
                                              'ITISENTOMAR28', 'ITISENTOMAR30'],
                                file_name=file_name1, path=path)

    # ITAUBAs FIP - mesma tabela de saída dos isentos, também não depende de base
    consolidador_infos_isen_dif(date_ref=None, lista_fundos=LISTA_FUNDOS_ITAUBA_FIP,
                                file_name=file_name1, path=path)

    ########################## RODAR DEPOIS ##########################################
    # PODE RODAR CEDO ELES TEM QUE SAIR CEDOOOOOOOOO - 10h30
    consolidador_infos(date_ref=None,
                       lista_fundos=['ITISENTOSET28', 'ITISENTOMAR29', 'ITISENTOMAR28',
                                     'ITISENTOSET29', 'ITISENTOMAR30'],
                       file_name=file_name, path=path)

    # PODE RODAR PARA ESSES DOIS - 11h geralmente d2
    date_d2 = str(QsDate(date.today()).add_business_days(-2))
    date_d4 = str(QsDate(date.today()).add_business_days(-4))
    # consolidador_infos(date_ref=date_d4, lista_fundos=['INTITAUFIIAGRO'], file_name=file_name, path=path)
    consolidador_infos(date_ref=date_d2, lista_fundos=['INTITAUCRIFII'], file_name=file_name, path=path)

    # criar json
    union_all_json()

    compara_historico(date_ref=None, lista_fundos=LISTA_FUNDOS_HISTORICO)


# atalhos aceitos no lugar dos fundos na linha de comando
GRUPOS_FUNDOS = {'isentos': LISTA_FUNDOS_ISENTOS, 'fip': LISTA_FUNDOS_ITAUBA_FIP}


def ler_data(texto):
    """Aceita AAAA-MM-DD, DD/MM/AAAA ou D-N (N dias úteis antes de hoje)."""
    m = re.fullmatch(r'[dD]-(\d+)', texto)
    if m:
        return str(QsDate(date.today()).add_business_days(-int(m.group(1))))
    for formato in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(texto, formato).strftime('%Y-%m-%d')
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(f"data inválida: '{texto}' (use AAAA-MM-DD, DD/MM/AAAA ou D-N)")


def ler_fundos(parser, comando, nomes, validos=None):
    """Troca atalhos e tickers pelo codigo_IAM_fundo e confere se o comando aceita cada fundo."""
    codigo_do_ticker = {ticker: codigo for codigo, ticker in dict_fundos_nomes.items()}
    fundos = []
    for nome in nomes:
        if nome.lower() in GRUPOS_FUNDOS:
            fundos += GRUPOS_FUNDOS[nome.lower()]
        else:
            fundos.append(codigo_do_ticker.get(nome.upper(), nome.upper()))
    fundos = list(dict.fromkeys(fundos))  # tira repetidos mantendo a ordem

    if validos is not None:
        invalidos = [f for f in fundos if f not in validos]
        if invalidos:
            def rotulo(f):
                return f"{f} ({dict_fundos_nomes[f]})" if f in dict_fundos_nomes else f
            parser.error(f"'{comando}' não aceita {', '.join(map(rotulo, invalidos))}. "
                         f"Opções: {', '.join(map(rotulo, validos))}")
    return fundos


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv

    tabela_fundos = '\n'.join(f'  {codigo:16s} {ticker}' for codigo, ticker in dict_fundos_nomes.items())
    parser = argparse.ArgumentParser(
        description='Gera as tabelas de sensibilidade dos fundos estruturados (PDF, JSON e histórico).',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""exemplos:
  python __main__.py diario
  python __main__.py sensibilidade IFRA11 IFRI11
  python __main__.py sensibilidade ICRI11 --data D-2
  python __main__.py saida isentos fip
  python __main__.py saida ITAUBAFIPSEN4_6_7 --data 2026-09-28
  python __main__.py json
  python __main__.py historico

fundos (código ou ticker):
{tabela_fundos}

atalhos:
  isentos = {' '.join(LISTA_FUNDOS_ISENTOS)}
  fip     = {' '.join(LISTA_FUNDOS_ITAUBA_FIP)}""")

    comum = argparse.ArgumentParser(add_help=False)
    comum.add_argument('--data', type=ler_data,
                       help='AAAA-MM-DD, DD/MM/AAAA ou D-N (N dias úteis atrás). Padrão: D-1')

    sub = parser.add_subparsers(dest='comando', metavar='comando')
    sub.add_parser('diario', help='rotina completa do dia, na ordem de sempre')
    p = sub.add_parser('sensibilidade', parents=[comum], help='PDF de sensibilidade + JSON (consolidador_infos)')
    p.add_argument('fundos', nargs='+', help='códigos, tickers ou atalho (isentos)')
    p = sub.add_parser('saida', parents=[comum],
                       help='tabela de saída dos isentos e FIPs (consolidador_infos_isen_dif)')
    p.add_argument('fundos', nargs='+', help='códigos, tickers ou atalhos (isentos, fip)')
    sub.add_parser('json', parents=[comum], help='junta os dados_*.json em dados_combinados.json (union_all_json)')
    p = sub.add_parser('historico', parents=[comum],
                       help='caixa, spread, duration e rentabilidade dos últimos dias (compara_historico)')
    p.add_argument('fundos', nargs='*', help='padrão: fundos da rotina diária')

    args = parser.parse_args(argv)
    if args.comando is None:
        parser.print_help()
        sys.exit(2)

    path_base = filePath + r'\ScriptsPersonalizados\Relatorios_estruturados' + '\\'

    file_name = path_base + 'modelo.xlsx'
    file_name1 = path_base + 'modelo1.xlsx'

    path = filePath + r'\ScriptsPersonalizados\Relatorios_estruturados\PDFs' + '\\'

    if args.comando == 'diario':
        rotina_diaria(file_name, file_name1, path)
    elif args.comando == 'sensibilidade':
        fundos = ler_fundos(parser, args.comando, args.fundos, validos=list(dict_fundos_nomes))
        consolidador_infos(date_ref=args.data, lista_fundos=fundos, file_name=file_name, path=path)
    elif args.comando == 'saida':
        fundos = ler_fundos(parser, args.comando, args.fundos,
                            validos=LISTA_FUNDOS_ISENTOS + LISTA_FUNDOS_ITAUBA_FIP)
        consolidador_infos_isen_dif(date_ref=args.data, lista_fundos=fundos, file_name=file_name1, path=path)
    elif args.comando == 'json':
        union_all_json(date_ref=args.data)
    elif args.comando == 'historico':
        fundos = ler_fundos(parser, args.comando, args.fundos) or LISTA_FUNDOS_HISTORICO
        compara_historico(date_ref=args.data, lista_fundos=fundos)


if __name__ == '__main__':
    main()
