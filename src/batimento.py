from datetime import date
import datetime
import pandas as pd
import sys
import os
import pathlib
import numpy as np
import base64
import io

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.backends.backend_pdf import PdfPages

from joblib import Parallel, delayed

from analise_divergencias import (
    make_fig_heatmap, make_fig_waterfall, make_fig_scatter,
    make_fig_top_ativos_barh,
    section_detalhes_por_fundo, section_aluguel_detail,
    section_macro_detail, section_resumo_colunas,
)
from report_fundo import gerar_report_fundo

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

LIMITE_AMARELO = 1.0
LIMITE_VERMELHO = 5.0

_COR_OK      = '#00B050'
_COR_ATENCAO = '#FFBF00'
_COR_CRITICO = '#E63946'
_COR_AZUL    = '#003366'
_COR_CINZA   = '#6c757d'

_STATUS_COLORS = {
    'OK': _COR_OK, 'ATENCAO': _COR_ATENCAO,
    'CRITICO': _COR_CRITICO, 'SEM DADO': _COR_CINZA
}


# =============================================================================
# BATIMENTO PRINCIPAL
# =============================================================================

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

    df_macro   = get_diff_return(date_ref=date_ref)
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

    df_semaforo     = _build_semaforo(df_final, lista_fundos)
    df_stats_global = _build_stats_por_classe(df_final)

    # ===== ARQUIVO CONSOLIDADO =====
    consolidated_path = output_dir / f"Consolidado_{date_ref.replace('-', '')}_{data_hora_atual}.xlsx"
    writer_cons = pd.ExcelWriter(consolidated_path, engine='xlsxwriter')

    df_pnl_excel(df_semaforo, 'Semaforo', writer_cons, semaforo=True)
    df_pnl_excel(df_stats_global, 'Stats por Classe', writer_cons)

    # ===== LOOP POR FUNDO =====
    for fundo in lista_fundos:

        file_path = output_dir / f"Pnl_{fundo}_{data_hora_atual}.xlsx"
        writer = pd.ExcelWriter(file_path, engine='xlsxwriter')

        df_final_fundo  = df_final[df_final['codigo_IAM_fundo'] == fundo]
        df_macro_fundo  = df_macro[df_macro['codigo_IAM_fundo'] == fundo]

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

            df_pnl_excel(df_final_fundo, fundo[:31], writer_cons)

            if not df_aluguel_fundo.empty:
                df_pnl_excel(df_aluguel_fundo, 'Aluguel', writer)
                df_pnl_excel(df_marreta_fundo, 'Marreta=Aluguel', writer)

        writer.close()
        print(f"Arquivo gerado: {file_path}")

        gerar_report_fundo(
            fundo         = fundo,
            df_fundo      = df_final_fundo,
            df_aluguel_fundo = df_aluguel_fundo,
            df_stats_fundo   = _build_stats_por_classe(df_final_fundo),
            df_semaforo   = df_semaforo,
            date_ref      = date_ref,
            output_dir    = output_dir,
            data_hora_atual = data_hora_atual,
        )

    writer_cons.close()
    print(f"Arquivo consolidado gerado: {consolidated_path}")

    # ===== RELATÓRIOS HTML + PDF =====
    gerar_report(df_final, df_semaforo, df_stats_global, date_ref, output_dir,
                 df_aluguel=df_aluguel, df_macro=df_macro)
    gerar_pdf(df_final, df_semaforo, df_stats_global, date_ref, output_dir,
              df_aluguel=df_aluguel, df_macro=df_macro)


# =============================================================================
# COLETA DE DADOS (reutilizada pelo batimento_range)
# =============================================================================

def _coletar_batimento(date_ref, lista_fundos, lista_mesa, lista_funcoes,
                       previa=False, updateVCRA=False):
    """
    Executa as funções de batimento e retorna (df_final, df_aluguel, df_macro)
    sem gerar arquivos. Reutilizada por batimento_range.py.
    """
    if lista_mesa is None:
        lista_mesa = []

    conn = Conn()  # noqa: F841

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
                        lista_mesa=lista_mesa, test=True, only_diff=False, tabela=tabela)
        for funcao in lista_funcoes
    ]

    lista_df = Parallel(n_jobs=-1, verbose=0)(functions)
    lista_df = [df for df in lista_df if df is not None]

    df_final = pd.concat(lista_df, ignore_index=True) if lista_df else pd.DataFrame()

    df_macro     = get_diff_return(date_ref=date_ref)
    df_pnl_total = get_pnl_total(date_ref=date_ref)

    if not df_final.empty:
        df_final = df_final.merge(df_pnl_total, on=['codigo_IAM_fundo'], how='left')
        df_final['dif_total_bps'] = (
            df_final['dif_pnl_total($)'] / df_final['last_patrimonio']
        ) * 10000
        df_final.drop(columns=['last_patrimonio'], inplace=True)

    df_aluguel = batimento_pnl_aluguel(date_ref=date_ref, lista_fundos=lista_fundos,
                                       lista_mesa=lista_mesa, test=True, only_diff=False)

    return df_final, df_aluguel, df_macro


# =============================================================================
# FIGURAS (compartilhadas entre HTML e PDF)
# =============================================================================

def _make_fig_bps_por_fundo(df_semaforo):
    df_plot = df_semaforo.dropna(subset=['max_dif_bps']).sort_values('max_dif_bps', ascending=False)
    if df_plot.empty:
        return None

    colors = [
        _COR_CRITICO if v >= LIMITE_VERMELHO
        else _COR_ATENCAO if v >= LIMITE_AMARELO
        else _COR_OK
        for v in df_plot['max_dif_bps']
    ]

    fig, ax = plt.subplots(figsize=(max(10, len(df_plot) * 0.9), 5))
    ax.bar(df_plot['fundo'], df_plot['max_dif_bps'], color=colors, edgecolor='white', linewidth=0.5)
    ax.axhline(LIMITE_VERMELHO, color=_COR_CRITICO, linestyle='--', linewidth=1.2,
               label=f'Crítico ({LIMITE_VERMELHO} bps)')
    ax.axhline(LIMITE_AMARELO, color=_COR_ATENCAO,  linestyle='--', linewidth=1.2,
               label=f'Atenção ({LIMITE_AMARELO} bps)')
    ax.set_title('Máxima Divergência por Fundo (bps)', fontsize=13, fontweight='bold', color=_COR_AZUL)
    ax.set_ylabel('bps')
    ax.tick_params(axis='x', rotation=40, labelsize=9)
    ax.legend(fontsize=9)
    ax.spines[['top', 'right']].set_visible(False)
    plt.tight_layout()
    return fig


def _make_fig_stats_por_classe(df_stats):
    if df_stats.empty:
        return None

    df_plot = df_stats.sort_values('max_abs_bps', ascending=False)
    classes = df_plot['classe'].tolist()
    x = np.arange(len(classes))

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle('Análise por Classe de Ativo', fontsize=13, fontweight='bold', color=_COR_AZUL)

    ax0 = axes[0]
    bar_colors = [_COR_CRITICO if v < 0 else '#4ECDC4' for v in df_plot['soma_dif_pnl']]
    ax0.bar(x, df_plot['soma_dif_pnl'], color=bar_colors, edgecolor='white')
    ax0.set_title('Soma Dif PnL (R$)', fontsize=11)
    ax0.set_xticks(x)
    ax0.set_xticklabels(classes, rotation=35, ha='right', fontsize=9)
    ax0.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'R${v:,.0f}'))
    ax0.spines[['top', 'right']].set_visible(False)

    ax1 = axes[1]
    ax1.bar(x, df_plot['max_abs_bps'], color='#5B8DB8', edgecolor='white')
    ax1.axhline(LIMITE_VERMELHO, color=_COR_CRITICO, linestyle='--', linewidth=1.2)
    ax1.axhline(LIMITE_AMARELO, color=_COR_ATENCAO,  linestyle='--', linewidth=1.2)
    ax1.set_title('Máx Divergência (bps)', fontsize=11)
    ax1.set_xticks(x)
    ax1.set_xticklabels(classes, rotation=35, ha='right', fontsize=9)
    ax1.spines[['top', 'right']].set_visible(False)

    plt.tight_layout()
    return fig


def _make_fig_pizza_status(df_semaforo):
    if df_semaforo.empty:
        return None

    contagem = df_semaforo['status'].value_counts()
    if contagem.empty:
        return None

    labels = contagem.index.tolist()
    values = contagem.values.tolist()
    colors = [_STATUS_COLORS.get(l, '#aaa') for l in labels]

    fig, ax = plt.subplots(figsize=(5, 5))
    _, _, autotexts = ax.pie(
        values, labels=labels, colors=colors,
        autopct='%1.0f%%', startangle=140,
        wedgeprops={'edgecolor': 'white', 'linewidth': 1.5}
    )
    for t in autotexts:
        t.set_fontsize(11)
        t.set_color('white')
        t.set_fontweight('bold')
    ax.set_title('Distribuição de Status', fontsize=12, fontweight='bold', color=_COR_AZUL)
    plt.tight_layout()
    return fig


def _make_fig_table(df, title, col_formats=None, status_col=None):
    """Renderiza um DataFrame como figura matplotlib (para uso no PDF)."""
    if df is None or df.empty:
        return None

    col_formats = col_formats or {}
    n_rows, n_cols = df.shape

    # formata células
    cell_text = []
    for _, row in df.iterrows():
        fmt_row = []
        for col in df.columns:
            val = row[col]
            if pd.isna(val):
                fmt_row.append('-')
            elif col in col_formats:
                fmt_row.append(col_formats[col].format(val))
            elif isinstance(val, float):
                fmt_row.append(f'{val:,.2f}')
            else:
                fmt_row.append(str(val))
        cell_text.append(fmt_row)

    row_height = 0.5
    fig_h = max(3.5, n_rows * row_height + 2.0)
    fig, ax = plt.subplots(figsize=(16, fig_h))
    ax.axis('off')

    tbl = ax.table(
        cellText=cell_text,
        colLabels=df.columns.tolist(),
        cellLoc='center',
        loc='center',
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8.5)
    tbl.auto_set_column_width(col=list(range(n_cols)))

    # cabeçalho
    for col_idx in range(n_cols):
        cell = tbl[0, col_idx]
        cell.set_facecolor(_COR_AZUL)
        cell.set_text_props(color='white', fontweight='bold')
        cell.set_height(0.10)

    # linhas de dados
    for row_idx in range(1, n_rows + 1):
        row_data = df.iloc[row_idx - 1]
        bg = '#f0f4ff' if row_idx % 2 == 0 else 'white'

        for col_idx, col in enumerate(df.columns):
            cell = tbl[row_idx, col_idx]
            cell.set_height(0.08)

            # colorir coluna status
            if col == status_col:
                val = str(row_data[col])
                cor = _STATUS_COLORS.get(val, '#ccc')
                cell.set_facecolor(cor)
                cell.set_text_props(color='white', fontweight='bold')
            else:
                cell.set_facecolor(bg)

    ax.set_title(title, fontsize=12, fontweight='bold', color=_COR_AZUL, pad=14)
    plt.tight_layout()
    return fig


def _make_fig_titulo(date_ref, df_semaforo):
    """Página de capa do PDF."""
    total  = len(df_semaforo) if not df_semaforo.empty else 0
    n_ok   = int((df_semaforo['status'] == 'OK').sum())     if not df_semaforo.empty else 0
    n_at   = int((df_semaforo['status'] == 'ATENCAO').sum()) if not df_semaforo.empty else 0
    n_cr   = int((df_semaforo['status'] == 'CRITICO').sum()) if not df_semaforo.empty else 0

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.axis('off')
    fig.patch.set_facecolor(_COR_AZUL)

    ax.text(0.5, 0.80, 'Report Batimento PnL', transform=ax.transAxes,
            fontsize=28, fontweight='bold', color='white', ha='center', va='center')
    ax.text(0.5, 0.68, f'Data de Referência: {date_ref}', transform=ax.transAxes,
            fontsize=16, color='#ccddee', ha='center', va='center')
    ax.text(0.5, 0.60, f'Gerado em: {data_hora_atual.replace("_", " ")}', transform=ax.transAxes,
            fontsize=11, color='#aabbcc', ha='center', va='center')

    # KPI boxes
    kpis = [
        ('Total Fundos', str(total),  'white'),
        ('OK',           str(n_ok),   _COR_OK),
        ('Atenção',      str(n_at),   _COR_ATENCAO),
        ('Crítico',      str(n_cr),   _COR_CRITICO),
    ]
    xs = np.linspace(0.15, 0.85, len(kpis))
    for x, (label, value, cor) in zip(xs, kpis):
        ax.text(x, 0.38, value, transform=ax.transAxes,
                fontsize=36, fontweight='bold', color=cor, ha='center', va='center')
        ax.text(x, 0.28, label, transform=ax.transAxes,
                fontsize=11, color='#ccddee', ha='center', va='center')

    ax.text(0.5, 0.08, 'VCRA / IAM — Uso Interno', transform=ax.transAxes,
            fontsize=9, color='#778899', ha='center', va='center')

    plt.tight_layout()
    return fig


# =============================================================================
# PDF
# =============================================================================

def gerar_pdf(df_final, df_semaforo, df_stats, date_ref, output_dir,
              df_aluguel=None, df_macro=None):
    """Gera relatório PDF multi-página com as principais análises do batimento."""

    pdf_path = output_dir / f"Report_Batimento_{date_ref.replace('-', '')}_{data_hora_atual}.pdf"

    col_formats_semaforo = {
        'max_dif_bps':     '{:.4f}',
        'soma_dif_pnl($)': 'R$ {:,.2f}',
    }
    cols_top10 = ['codigo_IAM_fundo', 'classe', 'codigo_IAM_ativo',
                  'ticker_bolsa', 'dif_total_bps', 'dif_pnl_total($)']

    def _save(fig):
        if fig:
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)

    with PdfPages(pdf_path) as pdf:

        _save(_make_fig_titulo(date_ref, df_semaforo))

        # Semáforo
        if not df_semaforo.empty:
            _save(_make_fig_table(df_semaforo, 'Semáforo por Fundo',
                                  col_formats=col_formats_semaforo, status_col='status'))

        # Gráficos de overview
        _save(_make_fig_bps_por_fundo(df_semaforo))
        _save(_make_fig_stats_por_classe(df_stats))
        _save(_make_fig_pizza_status(df_semaforo))

        # Novas visualizações detalhadas
        _save(make_fig_heatmap(df_final))
        _save(make_fig_waterfall(df_stats))
        _save(make_fig_top_ativos_barh(df_final))
        _save(make_fig_scatter(df_final))

        # Tabela stats por classe
        if not df_stats.empty:
            _save(_make_fig_table(df_stats, 'Estatísticas por Classe de Ativo'))

        # Top 10 tabela
        if not df_final.empty and 'dif_total_bps' in df_final.columns:
            cols_exist = [c for c in cols_top10 if c in df_final.columns]
            top10 = df_final.nlargest(10, 'dif_total_bps')[cols_exist].copy()
            _save(_make_fig_table(top10, 'Top 10 Maiores Divergências (por Ativo)'))

        # Detalhes por fundo (ATENÇÃO/CRÍTICO) — uma página por fundo
        if not df_final.empty and not df_semaforo.empty:
            fundos_criticos = df_semaforo[
                df_semaforo['status'].isin(['ATENCAO', 'CRITICO'])
            ]['fundo'].tolist()
            from analise_divergencias import _detail_cols_ordered
            for fundo in fundos_criticos:
                df_f = (df_final[df_final['codigo_IAM_fundo'] == fundo]
                        .sort_values('dif_total_bps', ascending=False, key=abs))
                if df_f.empty:
                    continue
                cols_show = [c for c in _detail_cols_ordered(df_f) if c in df_f.columns]
                status = df_semaforo.loc[df_semaforo['fundo'] == fundo, 'status'].values[0]
                _save(_make_fig_table(df_f[cols_show],
                                      f'Detalhes: {fundo}  [{status}]',
                                      status_col=None))

        # Aluguel
        if df_aluguel is not None and not df_aluguel.empty:
            _save(_make_fig_table(df_aluguel, f'Aluguel ({len(df_aluguel)} linhas)'))

        # Macro
        if df_macro is not None and not df_macro.empty:
            _save(_make_fig_table(df_macro, f'Macro Erros ({len(df_macro)} linhas)'))

        # Ativos ausentes
        if not df_final.empty and 'Existe' in df_final.columns:
            df_aus = df_final[df_final['Existe'] == False]
            if not df_aus.empty:
                cols_aus = ['codigo_IAM_fundo', 'classe', 'codigo_IAM_ativo', 'ticker_bolsa']
                cols_aus_exist = [c for c in cols_aus if c in df_aus.columns]
                _save(_make_fig_table(df_aus[cols_aus_exist],
                                      f'Ativos Ausentes ({len(df_aus)})'))

        meta = pdf.infodict()
        meta['Title']   = f'Report Batimento PnL — {date_ref}'
        meta['Author']  = 'VCRA / IAM'
        meta['Subject'] = 'Batimento PnL'

    print(f"PDF gerado: {pdf_path}")
    return pdf_path


# =============================================================================
# HTML
# =============================================================================

def gerar_report(df_final, df_semaforo, df_stats, date_ref, output_dir,
                 df_aluguel=None, df_macro=None):
    """Gera relatório HTML auto-contido com as principais análises do batimento."""

    secoes = []

    # ── Overview ──────────────────────────────────────────────────────────────
    secoes.append(_section_kpis(df_semaforo))
    secoes.append(_section_semaforo_table(df_semaforo))

    if not df_semaforo.empty and 'max_dif_bps' in df_semaforo.columns:
        fig = _make_fig_bps_por_fundo(df_semaforo)
        if fig:
            secoes.append(_wrap_fig_html(fig, 'Divergência por Fundo'))

    if not df_stats.empty:
        fig = _make_fig_stats_por_classe(df_stats)
        if fig:
            secoes.append(_wrap_fig_html(fig, 'Análise por Classe de Ativo'))

    if not df_semaforo.empty:
        fig = _make_fig_pizza_status(df_semaforo)
        if fig:
            secoes.append(_wrap_fig_html(fig, 'Distribuição de Status',
                                         extra_style='text-align:center',
                                         img_style='max-width:380px'))

    # ── Novas análises detalhadas ──────────────────────────────────────────────
    fig = make_fig_heatmap(df_final)
    if fig:
        secoes.append(_wrap_fig_html(fig, 'Heatmap Fundo × Classe (bps)'))

    fig = make_fig_waterfall(df_stats)
    if fig:
        secoes.append(_wrap_fig_html(fig, 'Waterfall Dif PnL por Classe'))

    fig = make_fig_top_ativos_barh(df_final)
    if fig:
        secoes.append(_wrap_fig_html(fig, 'Top 15 Ativos com Maior Divergência'))

    fig = make_fig_scatter(df_final)
    if fig:
        secoes.append(_wrap_fig_html(fig, 'Posição Financeira vs Divergência (bps)'))

    # ── Tabelas de detalhe ─────────────────────────────────────────────────────
    if not df_final.empty and 'dif_total_bps' in df_final.columns:
        secoes.append(_section_top10(df_final))

    secoes.append(section_detalhes_por_fundo(df_final, df_semaforo))

    if df_aluguel is not None:
        secoes.append(section_aluguel_detail(df_aluguel))

    if df_macro is not None:
        secoes.append(section_macro_detail(df_macro))

    if not df_final.empty and 'Existe' in df_final.columns:
        secoes.append(_section_ausentes(df_final))

    secoes.append(section_resumo_colunas(df_final))

    html = _render_html(date_ref, secoes)

    report_path = output_dir / f"Report_Batimento_{date_ref.replace('-', '')}_{data_hora_atual}.html"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Report HTML gerado: {report_path}")
    return report_path


def _wrap_fig_html(fig, title, extra_style='', img_style='max-width:100%'):
    img = _fig_to_b64(fig)
    plt.close(fig)
    inner = f'<div style="{extra_style}"><img src="data:image/png;base64,{img}" style="{img_style}"/></div>'
    return f'<div class="section"><h2>{title}</h2>{inner}</div>'


def _fig_to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=130, bbox_inches='tight')
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


def _section_kpis(df_semaforo):
    if df_semaforo.empty:
        return ''

    total  = len(df_semaforo)
    n_ok   = int((df_semaforo['status'] == 'OK').sum())
    n_at   = int((df_semaforo['status'] == 'ATENCAO').sum())
    n_cr   = int((df_semaforo['status'] == 'CRITICO').sum())
    total_ausentes = int(df_semaforo['ativos_ausentes'].sum()) if 'ativos_ausentes' in df_semaforo.columns else 0
    soma_col = 'soma_dif_pnl($)'
    soma_dif = df_semaforo[soma_col].sum() if soma_col in df_semaforo.columns else 0

    def card(label, value, color='#003366'):
        return (f'<div class="kpi-card">'
                f'<div class="kpi-value" style="color:{color}">{value}</div>'
                f'<div class="kpi-label">{label}</div>'
                f'</div>')

    cards = (
        card('Total de Fundos', total)
        + card('OK',            n_ok,           _COR_OK)
        + card('Atenção',       n_at,           _COR_ATENCAO)
        + card('Crítico',       n_cr,           _COR_CRITICO)
        + card('Ativos Ausentes', total_ausentes, _COR_CINZA)
        + card('Soma Dif PnL',  f'R$ {soma_dif:,.0f}', _COR_AZUL)
    )
    return f'<div class="section"><h2>Resumo Geral</h2><div class="kpi-grid">{cards}</div></div>'


def _section_semaforo_table(df_semaforo):
    if df_semaforo.empty:
        return ''

    rows_html = ''
    for _, row in df_semaforo.iterrows():
        status = row.get('status', '')
        cor    = _STATUS_COLORS.get(status, '#ccc')
        badge  = (f'<span style="background:{cor};color:white;'
                  f'padding:2px 10px;border-radius:4px;font-weight:bold">{status}</span>')
        cells = ''
        for col in df_semaforo.columns:
            val = row[col]
            if col == 'status':
                cells += f'<td>{badge}</td>'
            elif isinstance(val, float):
                cells += f'<td>{val:,.4f}</td>'
            else:
                cells += f'<td>{val}</td>'
        rows_html += f'<tr>{cells}</tr>'

    headers = ''.join(f'<th>{c}</th>' for c in df_semaforo.columns)
    table = f'<table><thead><tr>{headers}</tr></thead><tbody>{rows_html}</tbody></table>'
    return f'<div class="section"><h2>Semáforo por Fundo</h2>{table}</div>'


def _section_top10(df_final):
    cols = ['codigo_IAM_fundo', 'classe', 'codigo_IAM_ativo',
            'ticker_bolsa', 'dif_total_bps', 'dif_pnl_total($)']
    cols_exist = [c for c in cols if c in df_final.columns]
    top10 = df_final.nlargest(10, 'dif_total_bps')[cols_exist].copy()

    rows_html = ''
    for _, row in top10.iterrows():
        bps = row.get('dif_total_bps', 0)
        cor = _COR_CRITICO if bps >= LIMITE_VERMELHO else _COR_ATENCAO if bps >= LIMITE_AMARELO else _COR_OK
        cells = ''
        for col in cols_exist:
            val = row[col]
            if col == 'dif_total_bps':
                cells += f'<td style="color:{cor};font-weight:bold">{val:,.4f}</td>'
            elif isinstance(val, float):
                cells += f'<td>{val:,.2f}</td>'
            else:
                cells += f'<td>{val}</td>'
        rows_html += f'<tr>{cells}</tr>'

    headers = ''.join(f'<th>{c}</th>' for c in cols_exist)
    table = f'<table><thead><tr>{headers}</tr></thead><tbody>{rows_html}</tbody></table>'
    return f'<div class="section"><h2>Top 10 Maiores Divergências (por Ativo)</h2>{table}</div>'


def _section_ausentes(df_final):
    df_aus = df_final[df_final['Existe'] == False]
    if df_aus.empty:
        return ('<div class="section"><h2>Ativos Ausentes</h2>'
                '<p style="color:green">Nenhum ativo ausente encontrado.</p></div>')

    cols = ['codigo_IAM_fundo', 'classe', 'codigo_IAM_ativo', 'ticker_bolsa']
    cols_exist = [c for c in cols if c in df_aus.columns]
    rows_html  = ''
    for _, row in df_aus[cols_exist].iterrows():
        cells = ''.join(f'<td>{row[c]}</td>' for c in cols_exist)
        rows_html += f'<tr>{cells}</tr>'

    headers = ''.join(f'<th>{c}</th>' for c in cols_exist)
    table = f'<table><thead><tr>{headers}</tr></thead><tbody>{rows_html}</tbody></table>'
    return f'<div class="section"><h2>Ativos Ausentes ({len(df_aus)})</h2>{table}</div>'


def _render_html(date_ref, secoes):
    body = '\n'.join(secoes)
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Report Batimento PnL — {date_ref}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; color: #333; padding: 24px; }}
  header {{ background: {_COR_AZUL}; color: white; border-radius: 8px; padding: 20px 28px; margin-bottom: 24px; }}
  header h1 {{ font-size: 22px; font-weight: 700; }}
  header p  {{ font-size: 13px; opacity: .8; margin-top: 4px; }}
  .section  {{ background: white; border-radius: 8px; padding: 22px 24px; margin-bottom: 20px;
               box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
  .section h2 {{ font-size: 15px; font-weight: 700; color: {_COR_AZUL}; margin-bottom: 16px;
                 border-left: 4px solid {_COR_AZUL}; padding-left: 10px; }}
  .section img {{ max-width: 100%; border-radius: 4px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  thead tr {{ background: {_COR_AZUL}; color: white; }}
  th {{ padding: 9px 12px; text-align: left; font-weight: 600; }}
  td {{ padding: 7px 12px; border-bottom: 1px solid #eee; }}
  tr:hover td {{ background: #f5f8ff; }}
  .kpi-grid  {{ display: flex; flex-wrap: wrap; gap: 16px; }}
  .kpi-card  {{ background: #f8f9fb; border-radius: 8px; padding: 16px 20px; min-width: 130px;
                border: 1px solid #e2e8f0; flex: 1; }}
  .kpi-value {{ font-size: 28px; font-weight: 800; }}
  .kpi-label {{ font-size: 12px; color: #666; margin-top: 4px; }}
  .sub-section {{ border: 1px solid #e2e8f0; border-radius: 6px; padding: 14px 16px; margin-bottom: 16px; }}
  .sub-section h3 {{ font-size: 13px; color: {_COR_AZUL}; margin-bottom: 10px; }}
  .col-info {{ font-size: 11px; color: #888; margin-bottom: 8px; font-style: italic; }}
  code {{ background: #f0f4ff; padding: 1px 5px; border-radius: 3px; font-size: 11px; }}
  footer {{ text-align: center; font-size: 11px; color: #aaa; margin-top: 32px; padding-bottom: 16px; }}
</style>
</head>
<body>
<header>
  <h1>Report Batimento PnL</h1>
  <p>Data de referência: <strong>{date_ref}</strong> &nbsp;|&nbsp; Gerado em: {data_hora_atual.replace('_', ' ')}</p>
</header>
{body}
<footer>Gerado automaticamente pelo sistema de Batimento PnL — VCRA / IAM</footer>
</body>
</html>"""


# =============================================================================
# EXCEL
# =============================================================================

def _build_semaforo(df_final, lista_fundos):
    if df_final.empty:
        return pd.DataFrame()

    rows = []
    for fundo in lista_fundos:
        df_f = df_final[df_final['codigo_IAM_fundo'] == fundo]
        if df_f.empty:
            continue

        max_bps  = df_f['dif_total_bps'].abs().max() if 'dif_total_bps' in df_f.columns else np.nan
        soma_dif = df_f['dif_pnl_total($)'].sum()    if 'dif_pnl_total($)' in df_f.columns else np.nan
        total_ativos    = len(df_f)
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
            'fundo':            fundo,
            'status':           status,
            'max_dif_bps':      round(max_bps,  4) if not pd.isna(max_bps)  else np.nan,
            'soma_dif_pnl($)':  round(soma_dif, 2) if not pd.isna(soma_dif) else np.nan,
            'total_ativos':     total_ativos,
            'ativos_ausentes':  ativos_ausentes,
        })

    return pd.DataFrame(rows)


def _build_stats_por_classe(df_final):
    if df_final.empty or 'classe' not in df_final.columns:
        return pd.DataFrame()

    return df_final.groupby('classe').agg(
        qtd_ativos=('codigo_IAM_ativo',  'count'),
        soma_dif_pnl=('dif_pnl_total($)', 'sum'),
        media_dif_pnl=('dif_pnl_total($)', 'mean'),
        max_abs_bps=('dif_total_bps', lambda x: x.abs().max()),
        media_abs_bps=('dif_total_bps', lambda x: x.abs().mean()),
    ).reset_index()


def df_pnl_excel(df, name, writer, semaforo=False):
    if df is None or df.empty:
        return

    df.to_excel(writer, sheet_name=name, index=False, na_rep='-', freeze_panes=(1, 1))
    ws   = writer.sheets[name]
    book = writer.book

    fmt_bps       = book.add_format({'bg_color': '#86e39f', 'num_format': '0.00'})
    fmt_highlight = book.add_format({'bg_color': '#86e39f', 'num_format': '#,##0.00'})
    fmt_vcra      = book.add_format({'bg_color': '#B8CAD4', 'num_format': '#,##0.00'})
    fmt_num       = book.add_format({'bg_color': '#DCDCDC', 'num_format': '#,##0.00'})
    fmt_text      = book.add_format({'bg_color': '#DCDCDC'})

    for col in df.columns:
        col_idx   = df.columns.get_loc(col)
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

    if 'dif_total_bps' in df.columns:
        bps_idx        = df.columns.get_loc('dif_total_bps')
        fmt_bps_red    = book.add_format({'bg_color': '#FFC7CE', 'num_format': '0.00'})
        fmt_bps_yellow = book.add_format({'bg_color': '#FFEB9C', 'num_format': '0.00'})
        ws.conditional_format(1, bps_idx, n_rows, bps_idx, {
            'type': 'cell', 'criteria': '>=', 'value': LIMITE_VERMELHO, 'format': fmt_bps_red
        })
        ws.conditional_format(1, bps_idx, n_rows, bps_idx, {
            'type': 'cell', 'criteria': '>=', 'value': LIMITE_AMARELO, 'format': fmt_bps_yellow
        })

    if semaforo and 'status' in df.columns:
        st_idx      = df.columns.get_loc('status')
        fmt_ok      = book.add_format({'bg_color': '#00B050', 'font_color': '#FFFFFF', 'bold': True})
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


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    date_ref    = '2026-05-06'
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
