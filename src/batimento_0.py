from datetime import date
import datetime
import pandas as pd
import sys
import os
import pathlib
import numpy as np

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
agora = datetime.datetime.now()
data_hora_atual = agora.strftime("%Y-%m-%d_%H-%M-%S")

# Limites para classificação de divergência (em bps)
LIMITE_AMARELO = 1.0
LIMITE_VERMELHO = 5.0


def rodar_batimento(date_ref=None, lista_fundos=None, lista_mesa=None,
                    only_diff=False, lista_funcoes=None,
                    todos_fundos=False, margem_erro=0,
                    previa=False, updateVCRA=False):

    if lista_fundos is None:
        lista_fundos = []
    if lista_mesa is None:
        lista_mesa = []

    if date_ref is None or date_ref == '':
        d0 = date.today()
        dateQuery = QsDate(d0).add_business_days(-1)
        date_ref = str(dateQuery)

    conn = Conn()

    if lista_funcoes is None:
        lista_funcoes = [
            batimento_pnl_acao, batimento_pnl_caixa,
            batimento_pnl_fund_fidc, batimento_pnl_futuro,
            batimento_pnl_opcao, batimento_pnl_rf,
            batimento_pnl_swap
        ]

    if updateVCRA:
        run_VCRA(date_ref=date_ref, lista_fundos=lista_fundos, respeitar_horario=False)

    tabela = "VW_FUNDOS_POSICAO_PREVIA" if previa else "VW_FUNDOS_POSICAO"

    functions = [
        delayed(funcao)(date_ref=date_ref, lista_fundos=lista_fundos,
                        lista_mesa=lista_mesa, test=True, only_diff=only_diff, tabela=tabela)
        for funcao in lista_funcoes
    ]

    lista_df = Parallel(n_jobs=-1, verbose=10)(functions)
    lista_df = [df for df in lista_df if df is not None]

    df_final = pd.concat(lista_df, ignore_index=True) if lista_df else pd.DataFrame()

    df_macro = get_diff_return(date_ref=date_ref)
    df_pnl_total = get_pnl_total(date_ref=date_ref)

    if not df_final.empty:
        df_final = df_final.merge(df_pnl_total, on=['codigo_IAM_fundo'], how='left')
        df_final['dif_total_bps'] = (
            df_final['dif_pnl_total($)'] / df_final['last_patrimonio']
        ) * 10000
        df_final.drop(columns=['last_patrimonio'], inplace=True)

    df_aluguel = batimento_pnl_aluguel(date_ref=date_ref, lista_fundos=lista_fundos,
                                       lista_mesa=lista_mesa, test=True, only_diff=only_diff)

    df_marreta = aluguel_marreta(df_aluguel)

    output_dir = pathlib.Path(f"../output/batimento/{date_ref.replace('-', '')}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # ===== ARQUIVO CONSOLIDADO =====
    consolidated_path = output_dir / f"Consolidado_{date_ref.replace('-', '')}_{data_hora_atual}.xlsx"
    writer_cons = pd.ExcelWriter(consolidated_path, engine='xlsxwriter')

    df_semaforo = _build_semaforo(df_final, lista_fundos)
    df_stats_global = _build_stats_por_classe(df_final)

    df_pnl_excel(df_semaforo, 'Semaforo', writer_cons, semaforo=True)
    df_pnl_excel(df_stats_global, 'Stats por Classe', writer_cons)

    # ===== LOOP POR FUNDO =====
    for fundo in lista_fundos:

        file_path = output_dir / f"Pnl_{fundo}_{data_hora_atual}.xlsx"
        writer = pd.ExcelWriter(file_path, engine='xlsxwriter')

        df_final_fundo = df_final[df_final['codigo_IAM_fundo'] == fundo]
        df_macro_fundo = df_macro[df_macro['codigo_IAM_fundo'] == fundo]

        df_aluguel_fundo = df_aluguel[df_aluguel['codigo_IAM_fundo'] == fundo] \
            if not df_aluguel.empty else pd.DataFrame()
        df_marreta_fundo = df_marreta[df_marreta['codigo_IAM_fundo'] == fundo] \
            if not df_marreta.empty else pd.DataFrame()

        if not df_final_fundo.empty:
            df_resumo = df_final_fundo[[
                'classe', 'codigo_IAM_fundo', 'codigo_IAM_ativo',
                'ticker_bolsa', 'Existe', 'dif_total_bps', 'dif_pnl_total($)'
            ]]
            df_stats_fundo = _build_stats_por_classe(df_final_fundo)

            df_pnl_excel(df_resumo, 'Resumo', writer)
            df_pnl_excel(df_final_fundo, 'Batimento', writer)
            df_pnl_excel(df_macro_fundo, 'Macro erro', writer)
            df_pnl_excel(df_stats_fundo, 'Stats por Classe', writer)

            # aba do fundo no consolidado (max 31 chars no nome da aba)
            df_pnl_excel(df_final_fundo, fundo[:31], writer_cons)

            if not df_aluguel_fundo.empty:
                df_pnl_excel(df_aluguel_fundo, 'Aluguel', writer)
                df_pnl_excel(df_marreta_fundo, 'Marreta=Aluguel', writer)

        writer.close()
        print(f"Arquivo gerado: {file_path}")

    writer_cons.close()
    print(f"Arquivo consolidado gerado: {consolidated_path}")


def _build_semaforo(df_final, lista_fundos):
    """Resumo por fundo com classificação OK / ATENCAO / CRITICO baseado em dif_total_bps."""
    if df_final.empty:
        return pd.DataFrame()

    rows = []
    for fundo in lista_fundos:
        df_f = df_final[df_final['codigo_IAM_fundo'] == fundo]
        if df_f.empty:
            continue

        max_bps = df_f['dif_total_bps'].abs().max() if 'dif_total_bps' in df_f.columns else np.nan
        soma_dif = df_f['dif_pnl_total($)'].sum() if 'dif_pnl_total($)' in df_f.columns else np.nan
        total_ativos = len(df_f)
        ativos_ausentes = int((df_f['Existe'] == False).sum()) if 'Existe' in df_f.columns else 0

        if pd.isna(max_bps):
            status = 'SEM DADO'
        elif max_bps <= LIMITE_AMARELO:
            status = 'OK'
        elif max_bps <= LIMITE_VERMELHO:
            status = 'ATENCAO'
        else:
            status = 'CRITICO'

        rows.append({
            'fundo': fundo,
            'status': status,
            'max_dif_bps': round(max_bps, 4) if not pd.isna(max_bps) else np.nan,
            'soma_dif_pnl($)': round(soma_dif, 2) if not pd.isna(soma_dif) else np.nan,
            'total_ativos': total_ativos,
            'ativos_ausentes': ativos_ausentes,
        })

    return pd.DataFrame(rows)


def _build_stats_por_classe(df_final):
    """Estatísticas de divergência agrupadas por classe de ativo."""
    if df_final.empty or 'classe' not in df_final.columns:
        return pd.DataFrame()

    grp = df_final.groupby('classe').agg(
        qtd_ativos=('codigo_IAM_ativo', 'count'),
        soma_dif_pnl=('dif_pnl_total($)', 'sum'),
        media_dif_pnl=('dif_pnl_total($)', 'mean'),
        max_abs_bps=('dif_total_bps', lambda x: x.abs().max()),
        media_abs_bps=('dif_total_bps', lambda x: x.abs().mean()),
    ).reset_index()

    return grp


def df_pnl_excel(df, name, writer, semaforo=False):
    if df is None or df.empty:
        return

    df.to_excel(writer, sheet_name=name, index=False, na_rep='-', freeze_panes=(1, 1))
    ws = writer.sheets[name]
    book = writer.book

    # cria formatos uma única vez fora do loop
    fmt_bps = book.add_format({'bg_color': '#86e39f', 'num_format': '0.00'})
    fmt_highlight = book.add_format({'bg_color': '#86e39f', 'num_format': '#,##0.00'})
    fmt_vcra = book.add_format({'bg_color': '#B8CAD4', 'num_format': '#,##0.00'})
    fmt_num = book.add_format({'bg_color': '#DCDCDC', 'num_format': '#,##0.00'})
    fmt_text = book.add_format({'bg_color': '#DCDCDC'})

    for col in df.columns:
        col_idx = df.columns.get_loc(col)
        col_width = max(df[col].astype(str).map(len).max(), len(col)) + 2

        if col == 'dif_total_bps':
            fmt = fmt_bps
        elif col == 'pnl_total_VCRA':
            fmt = fmt_vcra
        elif col == 'dif_pnl_total($)':
            fmt = fmt_highlight
        elif df[col].dtype in (np.float64, np.int64, float, int):
            fmt = fmt_num
        else:
            fmt = fmt_text

        ws.set_column(col_idx, col_idx, col_width, fmt)

    n_rows = len(df)

    # formatação condicional na coluna dif_total_bps
    if 'dif_total_bps' in df.columns:
        bps_idx = df.columns.get_loc('dif_total_bps')
        fmt_bps_red = book.add_format({'bg_color': '#FFC7CE', 'num_format': '0.00'})
        fmt_bps_yellow = book.add_format({'bg_color': '#FFEB9C', 'num_format': '0.00'})
        ws.conditional_format(1, bps_idx, n_rows, bps_idx, {
            'type': 'cell', 'criteria': '>=', 'value': LIMITE_VERMELHO, 'format': fmt_bps_red
        })
        ws.conditional_format(1, bps_idx, n_rows, bps_idx, {
            'type': 'cell', 'criteria': '>=', 'value': LIMITE_AMARELO, 'format': fmt_bps_yellow
        })

    # formatação condicional na coluna status (semáforo)
    if semaforo and 'status' in df.columns:
        st_idx = df.columns.get_loc('status')
        fmt_ok = book.add_format({'bg_color': '#00B050', 'font_color': '#FFFFFF', 'bold': True})
        fmt_atencao = book.add_format({'bg_color': '#FFBF00', 'bold': True})
        fmt_critico = book.add_format({'bg_color': '#FF0000', 'font_color': '#FFFFFF', 'bold': True})
        ws.conditional_format(1, st_idx, n_rows, st_idx, {
            'type': 'text', 'criteria': 'containing', 'value': 'OK', 'format': fmt_ok
        })
        ws.conditional_format(1, st_idx, n_rows, st_idx, {
            'type': 'text', 'criteria': 'containing', 'value': 'ATENCAO', 'format': fmt_atencao
        })
        ws.conditional_format(1, st_idx, n_rows, st_idx, {
            'type': 'text', 'criteria': 'containing', 'value': 'CRITICO', 'format': fmt_critico
        })


if __name__ == "__main__":
    date_ref = '2026-05-06'
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
        'FICFI57693',
    ]

    lista_mesa = []

    rodar_batimento(
        date_ref,
        lista_fundos,
        lista_mesa,
        only_diff=False,
        lista_funcoes=None,
        todos_fundos=False,
        margem_erro=margem_erro,
        previa=False,
        updateVCRA=False
    )
