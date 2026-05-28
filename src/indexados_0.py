from datetime import date
import datetime
import pandas as pd
import sys
import os
import pathlib
import numpy as np
from datetime import datetime, timedelta


from joblib import Parallel, delayed


folder = pathlib.Path().resolve().parent.name


if (folder == 'bases-fundos-iam'):
    sys.path.append("../")
else:
    filePath = os.environ.get('BASES_FUNDOS_IAM_FILE_PATH')
    sys.path.append(filePath)


from qs_utils.qsdate import QsDate
from Funcoes.LakeConn import Conn
from BatimentoBases.VCRA_Funcoes_batimento_PnL.Batimento_PnL_Acao import batimento_pnl_acao
from BatimentoBases.VCRA_Funcoes_batimento_PnL.Batimento_PnL_Opcao import batimento_pnl_opcao
from BatimentoBases.VCRA_Funcoes_batimento_PnL.Batimento_PnL_Caixa import batimento_pnl_caixa
from BatimentoBases.VCRA_Funcoes_batimento_PnL.Batimento_PnL_Futuros import batimento_pnl_futuro
from BatimentoBases.VCRA_Funcoes_batimento_PnL.Batimento_PnL_Fund import batimento_pnl_fund_fidc
from BatimentoBases.VCRA_Funcoes_batimento_PnL.Batimento_PnL_Swap import batimento_pnl_swap
from BatimentoBases.VCRA_Funcoes_batimento_PnL.Batimento_PnL_RF import batimento_pnl_rf
from BatimentoBases.VCRA_Funcoes_batimento_PnL.Batimento_PnL_Aluguel import batimento_pnl_aluguel
from VCRA.VCRAs import run_VCRA
from BatimentoBases.VCRA_Funcoes_batimento_PnL.Funcoes_Batimento_Pnl_VCRA import (
    get_pnl_total, get_diff_return, aluguel_marreta
)


usernameSQL = os.environ.get('SQL_LOGIN')
agora = datetime.now()
data_hora_atual = agora.strftime("%Y-%m-%d_%H-%M-%S")


# ===== CONFIG =====
data_ini = datetime.strptime('2026-04-21', "%Y-%m-%d")
data_fim = datetime.strptime('2026-04-22', "%Y-%m-%d")

margem_erro = 0

lista_fundos = [
    'ETFIPSASD',
    'ESPCRETARF',
    'FICFI53254',
    'AGLOBAISHED',
    'ESPFACHESF',
    'ITAURUSS65632',
    'ESPBRASILFIA',
    'TESAM10A54529',
    'ITAUCARD49298',
    'SMINDEXFIA672',
    'ITAUSPI68168',
    'DIVINDEXRV52025',
    'INDEXIBRXRV467',
    'INTRAGITAU117',
    'FICFI57693'
]

lista_mesa = ['']

only_diff = False
previa = False
updateVCRA = False

lista_funcoes = [
    batimento_pnl_acao, batimento_pnl_caixa,
    batimento_pnl_fund_fidc, batimento_pnl_futuro,
    batimento_pnl_opcao, batimento_pnl_rf,
    batimento_pnl_swap
]


def df_pnl_excel(df, name, writer):

    df.to_excel(writer, sheet_name=name, index=False, na_rep='-', freeze_panes=(1, 1))

    colunas_formato1 = ['dif_total_bps', 'dif_pnl_total($)']
    colunas_formato2 = ['pnl_total_VCRA']

    for col in df:
        col_index = df.columns.get_loc(col)

        if col in colunas_formato2:
            fmt = writer.book.add_format({'bg_color': '#B8CAD4', 'num_format': '#,##0.00'})
        elif col in colunas_formato1:
            fmt = writer.book.add_format({'bg_color': '#86e39f', 'num_format': '#,##0.00'})
        else:
            fmt = writer.book.add_format({'bg_color': '#DCDCDC', 'num_format': '#,##0.00'})

        writer.sheets[name].set_column(col_index, col_index, 18, fmt)

        if col == 'dif_total_bps':
            fmt = writer.book.add_format({'bg_color': '#86e39f', 'num_format': '0.00'})
            writer.sheets[name].set_column(col_index, col_index, 18, fmt)

    # auto width
    for column in df:
        column_width = max(df[column].astype(str).map(len).max(), len(column))
        col_idx = df.columns.get_loc(column)
        writer.sheets[name].set_column(col_idx, col_idx, column_width)


# ===== LOOP POR DATA =====
data_atual = data_ini

while data_atual <= data_fim:

    date_ref = data_atual.strftime('%Y-%m-%d')

    print(f"\n📅 Rodando batimento para: {date_ref}")

    try:

        conn = Conn()

        if updateVCRA:
            run_VCRA(date_ref=date_ref, lista_fundos=lista_fundos, respeitar_horario=False)

        tabela = "VW_FUNDOS_POSICAO_PREVIA" if previa else "VW_FUNDOS_POSICAO"

        functions = [
            delayed(funcao)(date_ref=date_ref, lista_fundos=lista_fundos,
                            lista_mesa=[], test=True, only_diff=only_diff, tabela=tabela)
            for funcao in lista_funcoes
        ]

        lista_df = Parallel(n_jobs=-1, verbose=10)(functions)
        lista_df = [df for df in lista_df if df is not None]

        df_final = pd.concat(lista_df, ignore_index=True) if lista_df else pd.DataFrame()

        try:
            df_macro = get_diff_return(date_ref=date_ref)
        except Exception as e:
            print(f"⚠️  get_diff_return falhou para {date_ref}: {e}")
            df_macro = pd.DataFrame()

        try:
            df_pnl_total = get_pnl_total(date_ref=date_ref)
        except Exception as e:
            print(f"⚠️  get_pnl_total falhou para {date_ref}: {e}")
            df_pnl_total = pd.DataFrame()

        if not df_final.empty and not df_pnl_total.empty:
            df_final = df_final.merge(df_pnl_total, on=['codigo_IAM_fundo'], how='left')
            df_final['dif_total_bps'] = (
                df_final['dif_pnl_total($)'] / df_final['last_patrimonio']
            ) * 10000
            df_final.drop(columns={'last_patrimonio'}, inplace=True)

        try:
            df_aluguel = batimento_pnl_aluguel(date_ref=date_ref, lista_fundos=lista_fundos,
                                               lista_mesa=[], test=True, only_diff=only_diff)
        except Exception as e:
            print(f"⚠️  batimento_pnl_aluguel falhou para {date_ref}: {e}")
            df_aluguel = pd.DataFrame()

        try:
            df_marreta = aluguel_marreta(df_aluguel)
        except Exception as e:
            print(f"⚠️  aluguel_marreta falhou para {date_ref}: {e}")
            df_marreta = pd.DataFrame()

        # ===== CRIA PASTA =====
        output_dir = pathlib.Path(f"../output/batimento/indexados/{date_ref.replace('-', '')}")
        output_dir.mkdir(parents=True, exist_ok=True)

        # ===== LOOP POR FUNDO =====
        for fundo in lista_fundos:

            file_path = output_dir / f"Pnl_{fundo}_{date_ref}.xlsx"
            writer = pd.ExcelWriter(file_path, engine='xlsxwriter')

            df_final_fundo = df_final[df_final['codigo_IAM_fundo'] == fundo] \
                if not df_final.empty else pd.DataFrame()

            df_macro_fundo = df_macro[df_macro['codigo_IAM_fundo'] == fundo] \
                if not df_macro.empty else pd.DataFrame()

            df_aluguel_fundo = df_aluguel[df_aluguel['codigo_IAM_fundo'] == fundo] \
                if not df_aluguel.empty else pd.DataFrame()

            df_marreta_fundo = df_marreta[df_marreta['codigo_IAM_fundo'] == fundo] \
                if not df_marreta.empty else pd.DataFrame()

            if not df_final_fundo.empty:

                df_resumo = df_final_fundo[[
                    'classe', 'codigo_IAM_fundo', 'codigo_IAM_ativo',
                    'ticker_bolsa', 'Existe', 'dif_total_bps', 'dif_pnl_total($)'
                ]]

                df_pnl_excel(df_resumo, 'Resumo', writer)
                df_pnl_excel(df_final_fundo, 'Batimento', writer)

                if not df_macro_fundo.empty:
                    df_pnl_excel(df_macro_fundo, "Macro erro", writer)

                if not df_aluguel_fundo.empty:
                    df_pnl_excel(df_aluguel_fundo, "Aluguel", writer)
                    df_pnl_excel(df_marreta_fundo, "Marreta=Aluguel", writer)

            writer.close()
            print(f"Arquivo gerado: {file_path}")

    except Exception as e:
        print(f"❌ Erro ao rodar batimento para {date_ref}: {e}")

    data_atual += timedelta(days=1)


print("\n✅ Loop finalizado")
