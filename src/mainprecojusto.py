# main preco justo

import sys
import os
import pathlib
import pandas as pd
import argparse
from datetime import date, datetime


folder = pathlib.Path().resolve().parent.name

if folder == 'bases-fundos-iam':
    sys.path.append("../")
else:
    filePath = os.environ.get('BASES_FUNDOS_IAM_FILE_PATH')
    sys.path.append(filePath)


from CLog.log import log_iam, log_iam_flow_status
from AnalyticsETF.PrecoJustoETF import (
    gerar_preco_justo_etfRF,
    gerar_preco_justo_etfGOAT11,
    gerar_preco_justo_etfT10R11,
    gerar_preco_justo_etfSelic,
)
from AnalyticsETF.BBGValores import gerar_valor_bbg
from AnalyticsETF.spreadETF_Intraday import spread_ETF_toTable
from Datalake.Common.CLog import CLog


def rodar_precoJusto_main(id_iamflow=None, date_ref=None):
    dt_01      = datetime.now()
    d0         = date.today()
    hora_atual = datetime.now().time()

    inicio = datetime.strptime("10:15", "%H:%M").time()
    fim    = datetime.strptime("18:00", "%H:%M").time()

    if not (inicio <= hora_atual <= fim):
        c_log.bInfo("Fora do horário válido de cálculo (sem cotações)")
        exit()

    try:

        if id_iamflow is not None:
            log_iam_flow_status(id=id_iamflow, dt_ref=d0, status_execucao='running')

        #############################################################################
        ##########################  INPUT MANUAL  ###################################
        #############################################################################

        arquivo_destino = r"\\fswcorp\WMSASSET\ASSET_COMUM\ETFs\Preco_Justo_RF.csv"

        fundos_control = {
            'ITAUIMA5P2070': {
                'ticker':           'B5P211',
                'bench':            'IMA-B 5',
                'funcao_execucao':  'gerar_preco_justo_etfRF',
                'indice_formatado': 'IMA-B 5 P2',
            },
            'ITAUIMAB64066': {
                'ticker':           'IMAB11',
                'bench':            'IMA-B',
                'funcao_execucao':  'gerar_preco_justo_etfRF',
                'indice_formatado': 'IMA-B',
            },
            'ITAUIMAB64215': {
                'ticker':           'IB5M11',
                'bench':            'IMA-B 5+',
                'funcao_execucao':  'gerar_preco_justo_etfRF',
                'indice_formatado': 'IMA-B 5+',
            },
            'ITAUIRFMP24216': {
                'ticker':           'IRFM11',
                'bench':            'IRF-M P2',
                'funcao_execucao':  'gerar_preco_justo_etfRF',
                'indice_formatado': 'IRF-M P2',
            },
            'ITAUIRFM67811': {
                'ticker':           'IDKA11',
                'bench':            'IRF-M P3',
                'funcao_execucao':  'gerar_preco_justo_etfRF',
                'indice_formatado': 'IRF-M P3',
            },
            'ITAUSPI68168': {
                'ticker':           'GOAT11',
                'bench':            'IRF-M P3',
                'funcao_execucao':  'gerar_preco_justo_etfGOAT11',
                'indice_formatado': '80% IMA-B + 20% S&P500',
            },
            'ITAUTSA68443': {
                'ticker':           'T10R11',
                'funcao_execucao':  'gerar_preco_justo_etfT10R11',
                'indice_formatado': 'T10 + Diferencial de Juros BR vs EUA',
            },
            # 20260227  Novos ETFs
            'ITAUNTN68777': {
                'ticker':           'TD3511',
                'bench':            'NTNB 2035',
                'funcao_execucao':  'gerar_preco_justo_etfRF',
                'indice_formatado': 'NTN-B ago/35',
            },
            'ITAUNTN68778': {
                'ticker':           'TD5011',
                'bench':            'NTNB 2050',
                'funcao_execucao':  'gerar_preco_justo_etfRF',
                'indice_formatado': 'NTN-B ago/50',
            },
            'ITAUNTN68779': {
                'ticker':           'TD6011',
                'bench':            'NTNB 2060',
                'funcao_execucao':  'gerar_preco_justo_etfRF',
                'indice_formatado': 'NTN-B ago/60',
            },
            'ITAUTEV68755': {
                'ticker':           '5PRE11',
                'bench':            'ITBR_5_PRE',
                'funcao_execucao':  'gerar_preco_justo_etfRF',
                'indice_formatado': 'Pre 5 anos',
            },
            # TODO: substituir pelos códigos internos reais dos fundos
            'TODO_CDIB11_FUND_CODE': {
                'ticker':           'CDIB11',
                'bench':            'IMA-S',
                'funcao_execucao':  'gerar_preco_justo_etfSelic',
                'indice_formatado': 'Selic Target 800',
            },
            'TODO_LFTI11_FUND_CODE': {
                'ticker':           'LFTI11',
                'bench':            'IMA-S',
                'funcao_execucao':  'gerar_preco_justo_etfSelic',
                'indice_formatado': 'IMA-S',
            },
        }

        #############################################################################
        #############################################################################
        #############################################################################

        lista_fundos = list(fundos_control.keys())

        fundos_filtrados = {k: v for k, v in fundos_control.items()
                            if v['funcao_execucao'] == 'gerar_preco_justo_etfRF'}
        dfRF = gerar_preco_justo_etfRF(fundos_filtrados)

        fundos_filtrados_GOAT11 = {k: v for k, v in fundos_control.items()
                                   if v['funcao_execucao'] == 'gerar_preco_justo_etfGOAT11'}
        dfGOAT = gerar_preco_justo_etfGOAT11(fundos_filtrados_GOAT11)

        fundos_filtrados_T10 = {k: v for k, v in fundos_control.items()
                                if v['funcao_execucao'] == 'gerar_preco_justo_etfT10R11'}
        dfT10 = gerar_preco_justo_etfT10R11(fundos_filtrados_T10)
        dfT10['yield_estimado'] = dfT10['yield_estimado'] / 100
        dfT10['yield_estimado'] = dfT10['yield_estimado'].apply(lambda x: f"{x:.2%}")
        dfT10['yield_estimado'] = dfT10['yield_estimado'].astype(str).str.replace('.', ',', regex=False)
        dfT10['duration']       = dfT10['duration'].round(2)

        fundos_filtrados_Selic = {k: v for k, v in fundos_control.items()
                                  if v['funcao_execucao'] == 'gerar_preco_justo_etfSelic'}
        dfSelic = gerar_preco_justo_etfSelic(fundos_filtrados_Selic)
        dfSelic['yield_estimado']        = dfSelic['yield_estimado'].apply(lambda x: f"{x:.2%}")
        dfSelic['yield_ultimo_negocio']  = dfSelic['yield_ultimo_negocio'].apply(lambda x: f"{x:.2%}")
        dfSelic['spread']                = dfSelic['spread'].apply(lambda x: f"{x:.2%}")
        dfSelic['duration']              = dfSelic['duration'].round(2)
        dfSelic['yield_estimado']        = dfSelic['yield_estimado'].astype(str).str.replace('.', ',', regex=False)
        dfSelic['yield_ultimo_negocio']  = dfSelic['yield_ultimo_negocio'].astype(str).str.replace('.', ',', regex=False)

        # FORMATACAO DO CSV
        df = dfRF
        df['yield_estimado']       = df['yield_estimado'].apply(lambda x: f"{x:.2%}")
        df['yield_ultimo_negocio'] = df['yield_ultimo_negocio'].apply(lambda x: f"{x:.2%}")
        df['spread']               = df['spread'].apply(lambda x: f"{x:.2%}")
        df['duration']             = df['duration'].round(2)

        df['yield_estimado']       = df['yield_estimado'].astype(str).str.replace('.', ',', regex=False)
        df['yield_ultimo_negocio'] = df['yield_ultimo_negocio'].astype(str).str.replace('.', ',', regex=False)

        mask = df['indice'].str.contains('IMA-B')
        df.loc[mask, 'yield_estimado']       = 'IPCA+ ' + df['yield_estimado']
        df.loc[mask, 'yield_ultimo_negocio'] = 'IPCA+ ' + df['yield_ultimo_negocio']

        # 20260406  Pediram para incluir IPCA+ para os índices das NTN-Bs também.
        mask = df['indice'].str.contains('NTN-B')
        df.loc[mask, 'yield_estimado']       = 'IPCA+ ' + df['yield_estimado']
        df.loc[mask, 'yield_ultimo_negocio'] = 'IPCA+ ' + df['yield_ultimo_negocio']

        df = pd.concat([df, dfGOAT])
        df = pd.concat([df, dfSelic])
        df['valor_estimado_cota'] = df['valor_estimado_cota'].round(2)

        df = pd.concat([df, dfT10])
        df['data_hora_atualizacao'] = pd.to_datetime(df['data_hora_atualizacao'])
        df['data_hora_atualizacao'] = df['data_hora_atualizacao'].dt.strftime('%d/%m/%Y às %H:%M:%S')
        df['yield_ultimo_negocio']  = df['yield_ultimo_negocio'].astype(str).str.replace('.', ',', regex=False)
        df['yield_estimado']        = df['yield_estimado'].astype(str).str.replace('.', ',', regex=False)
        df['spread']                = df['spread'].astype(str).str.replace('.', ',', regex=False)
        df['duration']              = df['duration'].astype(str).str.replace('.', ',', regex=False)
        df['valor_estimado_cota']   = df['valor_estimado_cota'].astype(str).str.replace('.', ',', regex=False)

        df.columns = df.columns.str.upper()

        if df.isnull().values.any():
            raise ValueError("Erro: Existem valores NA no DataFrame df.")

        if df.empty:
            raise ValueError("Erro: O DataFrame df está vazio.")

        if len(df['ETF']) != len(lista_fundos):
            raise ValueError("Erro: Faltam fundos.")

        df.to_csv(arquivo_destino, sep=';', decimal=',', index=False)

        spread_ETF_toTable(df)
        #gerar_valor_bbg(df)

        if id_iamflow is not None:
            log_iam_flow_status(id=id_iamflow, dt_ref=d0, status_execucao='ok',
                                status_final='ok', status_qualidade='ok')

        log_iam(data_ref_inicio=d0, data_ref_final=d0, tabela=arquivo_destino,
                data_hora_inicio=dt_01, rows_inserted=len(df),
                script=os.path.basename(__file__))

    except Exception as msg:
        c_log.bErro(f"Não foi possível atualizar o arquivo com os índices\n  Mensagem de Erro\n  {msg}")

        if id_iamflow is not None:
            log_iam_flow_status(id=id_iamflow, dt_ref=d0, status_execucao='erro', status_final='erro')

        log_iam(data_ref_inicio=d0, data_ref_final=d0, tabela=arquivo_destino,
                data_hora_inicio=dt_01, script=os.path.basename(__file__))


if __name__ == "__main__":
    str_pasta_log = r"\\fswcorp\wmsasset\ASSET_COMUM\Logs" + '\\'
    c_log = CLog("DL_MainPrecoJusto", bDebug=True, strPasta=str_pasta_log, bPrintLog=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--date_ref",    help="Date referência")
    parser.add_argument("-i", "--id_iamflow",  help="Id do script no IAM Flow para controle de log")
    args = parser.parse_args()

    rodar_precoJusto_main(id_iamflow=args.id_iamflow, date_ref=args.date_ref)
    c_log.bOK("Concluído")
