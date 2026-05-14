"""
batimento_range.py
Roda o batimento para um range de datas (dia a dia) e gera relatório de tendência.

Uso:
    from batimento_range import rodar_batimento_range

    rodar_batimento_range(
        date_start  = '2026-04-01',
        date_end    = '2026-05-06',
        lista_fundos = ['FUND1', 'FUND2', ...],
    )
"""
import datetime
import pathlib
import io
import base64

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.colors as mcolors
from matplotlib.backends.backend_pdf import PdfPages

from analise_divergencias import (
    LIMITE_AMARELO, LIMITE_VERMELHO,
    _COR_OK, _COR_ATENCAO, _COR_CRITICO, _COR_AZUL, _COR_CINZA, _STATUS_COLORS,
)

agora_range   = datetime.datetime.now()
_DH_RANGE     = agora_range.strftime("%Y-%m-%d_%H-%M-%S")


# =============================================================================
# ENTRADA PRINCIPAL
# =============================================================================

def rodar_batimento_range(date_start, date_end, lista_fundos, lista_mesa=None,
                           lista_funcoes=None, previa=False, updateVCRA=False):
    """
    Roda o batimento para cada dia útil entre date_start e date_end (inclusive).
    Gera relatório HTML + PDF de tendência na pasta output/batimento/range/.

    Parâmetros
    ----------
    date_start : str   'YYYY-MM-DD'
    date_end   : str   'YYYY-MM-DD'
    lista_fundos : list[str]
    """
    if lista_mesa is None:
        lista_mesa = []

    datas = pd.bdate_range(start=date_start, end=date_end)
    datas_str = [d.strftime('%Y-%m-%d') for d in datas]

    if not datas_str:
        print("Nenhum dia útil no range informado.")
        return

    print(f"Range: {date_start} → {date_end}  ({len(datas_str)} dias úteis)")

    # importa lazy para evitar circular
    from batimento import _coletar_batimento, _build_semaforo, _build_stats_por_classe

    rows_sem   = []
    rows_stats = []

    for date_ref in datas_str:
        print(f"  Coletando {date_ref}...", end=' ')
        try:
            df_final, _, _ = _coletar_batimento(
                date_ref, lista_fundos, lista_mesa, lista_funcoes, previa, updateVCRA
            )
            df_sem   = _build_semaforo(df_final, lista_fundos)
            df_stats = _build_stats_por_classe(df_final)

            df_sem['date_ref']   = date_ref
            df_stats['date_ref'] = date_ref

            rows_sem.append(df_sem)
            rows_stats.append(df_stats)
            print("OK")
        except Exception as e:
            print(f"ERRO: {e}")

    if not rows_sem:
        print("Nenhum dado coletado.")
        return

    df_range       = pd.concat(rows_sem,   ignore_index=True)
    df_stats_range = pd.concat(rows_stats, ignore_index=True)

    output_dir = pathlib.Path(f"../output/batimento/range")
    output_dir.mkdir(parents=True, exist_ok=True)

    gerar_report_range(df_range, df_stats_range, date_start, date_end,
                       lista_fundos, output_dir)


# =============================================================================
# RELATÓRIO DE RANGE
# =============================================================================

def gerar_report_range(df_range, df_stats_range, date_start, date_end,
                        lista_fundos, output_dir):
    """
    Gera HTML + PDF com análise temporal dia a dia.
    Pode ser chamado standalone se você já tiver df_range e df_stats_range.
    """
    secoes = []
    secoes.append(_section_kpis_range(df_range, date_start, date_end))
    secoes.append(_section_evolucao_table(df_range))

    fig = _make_fig_timeseries(df_range)
    if fig:
        secoes.append(_wrap_fig(fig, 'Evolução do Máx dif_total_bps por Fundo'))

    fig = _make_fig_heatmap_data_fundo(df_range)
    if fig:
        secoes.append(_wrap_fig(fig, 'Heatmap Data × Fundo (bps)'))

    fig = _make_fig_heatmap_data_classe(df_stats_range)
    if fig:
        secoes.append(_wrap_fig(fig, 'Heatmap Data × Classe (bps)'))

    fig = _make_fig_dias_criticos(df_range)
    if fig:
        secoes.append(_wrap_fig(fig, 'Dias com Status CRÍTICO por Fundo'))

    fig = _make_fig_trend_bps(df_range)
    if fig:
        secoes.append(_wrap_fig(fig, 'Tendência: Média Móvel 3d do Máx bps'))

    secoes.append(_section_tabela_tendencia(df_range))
    secoes.append(_section_piores_dias(df_range))

    # HTML
    html = _render_html_range(date_start, date_end, secoes)
    slug = f"{date_start.replace('-','')}_{date_end.replace('-','')}"
    html_path = output_dir / f"Report_Range_{slug}_{_DH_RANGE}.html"
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Report range HTML: {html_path}")

    # PDF
    pdf_path = output_dir / f"Report_Range_{slug}_{_DH_RANGE}.pdf"
    _build_pdf_range(df_range, df_stats_range, date_start, date_end, pdf_path)
    print(f"Report range PDF:  {pdf_path}")

    return html_path, pdf_path


# =============================================================================
# FIGURAS
# =============================================================================

def _make_fig_timeseries(df_range):
    """Série temporal de max_dif_bps por fundo."""
    if df_range.empty or 'max_dif_bps' not in df_range.columns:
        return None

    fundos = df_range['fundo'].unique()
    fig, ax = plt.subplots(figsize=(14, 5))

    cmap = plt.get_cmap('tab10')
    for i, fundo in enumerate(fundos):
        sub = (df_range[df_range['fundo'] == fundo]
               .sort_values('date_ref'))
        ax.plot(sub['date_ref'], sub['max_dif_bps'],
                marker='o', markersize=4, linewidth=1.5,
                color=mcolors.to_hex(cmap(i % 10)), label=fundo)

    ax.axhline(LIMITE_VERMELHO, color=_COR_CRITICO, linestyle='--',
               linewidth=1.2, label=f'Crítico ({LIMITE_VERMELHO} bps)')
    ax.axhline(LIMITE_AMARELO,  color=_COR_ATENCAO,  linestyle='--',
               linewidth=1.2, label=f'Atenção ({LIMITE_AMARELO} bps)')

    ax.set_title('Evolução Máx dif_total_bps por Fundo', fontsize=13,
                 fontweight='bold', color=_COR_AZUL)
    ax.set_ylabel('bps')
    ax.set_xlabel('Data')
    _rotate_xaxis(ax)
    ax.legend(fontsize=7, bbox_to_anchor=(1.01, 1), loc='upper left')
    ax.spines[['top', 'right']].set_visible(False)
    plt.tight_layout()
    return fig


def _make_fig_heatmap_data_fundo(df_range):
    """Heatmap: linhas = datas, colunas = fundos, valores = max_dif_bps."""
    if df_range.empty or 'max_dif_bps' not in df_range.columns:
        return None

    pivot = (df_range.pivot_table(
        values='max_dif_bps', index='date_ref', columns='fundo', aggfunc='max'
    ).fillna(0))

    if pivot.empty:
        return None

    n_datas, n_fundos = pivot.shape
    fig_w = max(8, n_fundos * 1.2 + 2)
    fig_h = max(4, n_datas * 0.45 + 1.5)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    cmap = mcolors.LinearSegmentedColormap.from_list(
        'semaforo', ['#f7fff7', _COR_ATENCAO, _COR_CRITICO]
    )
    vmax = max(LIMITE_VERMELHO * 1.5, float(pivot.values.max()))
    im = ax.imshow(pivot.values, cmap=cmap, aspect='auto', vmin=0, vmax=vmax)

    ax.set_xticks(range(n_fundos))
    ax.set_xticklabels(pivot.columns, rotation=35, ha='right', fontsize=8)
    ax.set_yticks(range(n_datas))
    ax.set_yticklabels(pivot.index, fontsize=8)

    for i in range(n_datas):
        for j in range(n_fundos):
            val = pivot.values[i, j]
            if val > 0:
                txt_color = 'white' if val >= LIMITE_VERMELHO else 'black'
                ax.text(j, i, f'{val:.1f}', ha='center', va='center',
                        fontsize=7, color=txt_color, fontweight='bold')

    plt.colorbar(im, ax=ax, label='bps', shrink=0.7)
    ax.set_title('Heatmap: Data × Fundo (Máx bps)',
                 fontsize=12, fontweight='bold', color=_COR_AZUL, pad=10)
    plt.tight_layout()
    return fig


def _make_fig_heatmap_data_classe(df_stats_range):
    """Heatmap: linhas = datas, colunas = classes, valores = max_abs_bps."""
    if df_stats_range.empty or 'max_abs_bps' not in df_stats_range.columns:
        return None

    pivot = (df_stats_range.pivot_table(
        values='max_abs_bps', index='date_ref', columns='classe', aggfunc='max'
    ).fillna(0))

    if pivot.empty:
        return None

    n_datas, n_classes = pivot.shape
    fig_w = max(8, n_classes * 1.4 + 2)
    fig_h = max(4, n_datas * 0.45 + 1.5)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    cmap = mcolors.LinearSegmentedColormap.from_list(
        'semaforo2', ['#f0f9ff', _COR_ATENCAO, _COR_CRITICO]
    )
    vmax = max(LIMITE_VERMELHO * 1.5, float(pivot.values.max()))
    im = ax.imshow(pivot.values, cmap=cmap, aspect='auto', vmin=0, vmax=vmax)

    ax.set_xticks(range(n_classes))
    ax.set_xticklabels(pivot.columns, rotation=35, ha='right', fontsize=8)
    ax.set_yticks(range(n_datas))
    ax.set_yticklabels(pivot.index, fontsize=8)

    for i in range(n_datas):
        for j in range(n_classes):
            val = pivot.values[i, j]
            if val > 0:
                txt_color = 'white' if val >= LIMITE_VERMELHO else 'black'
                ax.text(j, i, f'{val:.1f}', ha='center', va='center',
                        fontsize=7, color=txt_color, fontweight='bold')

    plt.colorbar(im, ax=ax, label='bps', shrink=0.7)
    ax.set_title('Heatmap: Data × Classe (Máx bps)',
                 fontsize=12, fontweight='bold', color=_COR_AZUL, pad=10)
    plt.tight_layout()
    return fig


def _make_fig_dias_criticos(df_range):
    """Barras: quantos dias cada fundo ficou com status CRÍTICO/ATENÇÃO."""
    if df_range.empty or 'status' not in df_range.columns:
        return None

    contagem = (df_range.groupby(['fundo', 'status'])
                .size().reset_index(name='dias')
                .pivot_table(index='fundo', columns='status', values='dias', fill_value=0))

    fig, ax = plt.subplots(figsize=(max(8, len(contagem) * 0.9), 5))
    x      = np.arange(len(contagem))
    width  = 0.25
    status_cols = [s for s in ['OK', 'ATENCAO', 'CRITICO'] if s in contagem.columns]
    cores  = {'OK': _COR_OK, 'ATENCAO': _COR_ATENCAO, 'CRITICO': _COR_CRITICO}

    for i, st in enumerate(status_cols):
        offset = (i - len(status_cols) / 2) * width + width / 2
        ax.bar(x + offset, contagem[st], width, label=st,
               color=cores[st], edgecolor='white')

    ax.set_xticks(x)
    ax.set_xticklabels(contagem.index, rotation=35, ha='right', fontsize=9)
    ax.set_ylabel('Nº de dias')
    ax.set_title('Dias por Status no Range', fontsize=12, fontweight='bold', color=_COR_AZUL)
    ax.legend()
    ax.spines[['top', 'right']].set_visible(False)
    plt.tight_layout()
    return fig


def _make_fig_trend_bps(df_range, window=3):
    """Linha com média móvel do max_dif_bps por fundo."""
    if df_range.empty or 'max_dif_bps' not in df_range.columns:
        return None

    fundos = df_range['fundo'].unique()
    fig, ax = plt.subplots(figsize=(14, 5))
    cmap = plt.get_cmap('tab10')

    for i, fundo in enumerate(fundos):
        sub = (df_range[df_range['fundo'] == fundo]
               .sort_values('date_ref')
               .copy())
        sub['mm'] = sub['max_dif_bps'].rolling(window, min_periods=1).mean()
        color = mcolors.to_hex(cmap(i % 10))
        ax.plot(sub['date_ref'], sub['mm'],
                linewidth=2, color=color, label=fundo)
        ax.fill_between(sub['date_ref'], 0, sub['mm'],
                        alpha=0.08, color=color)

    ax.axhline(LIMITE_VERMELHO, color=_COR_CRITICO, linestyle='--', linewidth=1)
    ax.axhline(LIMITE_AMARELO,  color=_COR_ATENCAO,  linestyle='--', linewidth=1)
    ax.set_title(f'Tendência: Média Móvel {window}d do Máx bps',
                 fontsize=12, fontweight='bold', color=_COR_AZUL)
    ax.set_ylabel('bps (MM3)')
    _rotate_xaxis(ax)
    ax.legend(fontsize=7, bbox_to_anchor=(1.01, 1), loc='upper left')
    ax.spines[['top', 'right']].set_visible(False)
    plt.tight_layout()
    return fig


# =============================================================================
# SEÇÕES HTML
# =============================================================================

def _section_kpis_range(df_range, date_start, date_end):
    n_dias    = df_range['date_ref'].nunique() if not df_range.empty else 0
    n_fundos  = df_range['fundo'].nunique()    if not df_range.empty else 0
    pct_cr    = 0
    if not df_range.empty and 'status' in df_range.columns:
        pct_cr = (df_range['status'] == 'CRITICO').mean() * 100
    media_bps = df_range['max_dif_bps'].mean() if not df_range.empty else 0

    def card(label, value, color=_COR_AZUL):
        return (f'<div class="kpi-card">'
                f'<div class="kpi-value" style="color:{color}">{value}</div>'
                f'<div class="kpi-label">{label}</div></div>')

    cards = (
        card('Dias Úteis Analisados', n_dias)
        + card('Fundos', n_fundos)
        + card('% Observações CRÍTICO', f'{pct_cr:.1f}%', _COR_CRITICO)
        + card('Média Máx bps (geral)', f'{media_bps:.4f}',
               _COR_CRITICO if media_bps >= LIMITE_VERMELHO
               else _COR_ATENCAO if media_bps >= LIMITE_AMARELO else _COR_OK)
    )
    return f'<div class="section"><h2>Resumo do Range {date_start} → {date_end}</h2><div class="kpi-grid">{cards}</div></div>'


def _section_evolucao_table(df_range):
    """Pivot: linhas = datas, colunas = fundos, valor = max_dif_bps formatado com badge."""
    if df_range.empty or 'max_dif_bps' not in df_range.columns:
        return ''

    pivot = (df_range.pivot_table(
        values='max_dif_bps', index='date_ref', columns='fundo', aggfunc='max'
    ))

    rows_html = ''
    for data, row in pivot.iterrows():
        cells = f'<td><strong>{data}</strong></td>'
        for fundo in pivot.columns:
            val = row[fundo]
            if pd.isna(val):
                cells += '<td style="color:#ccc">-</td>'
            else:
                cor = (_COR_CRITICO if val >= LIMITE_VERMELHO
                       else _COR_ATENCAO if val >= LIMITE_AMARELO else _COR_OK)
                cells += (f'<td style="font-weight:bold;color:{cor}">{val:.4f}</td>')
        rows_html += f'<tr>{cells}</tr>'

    headers = '<th>Data</th>' + ''.join(f'<th>{c}</th>' for c in pivot.columns)
    table   = f'<table><thead><tr>{headers}</tr></thead><tbody>{rows_html}</tbody></table>'
    return (f'<div class="section"><h2>Evolução Dia a Dia (Máx bps por Fundo)</h2>'
            f'<div style="overflow-x:auto">{table}</div></div>')


def _section_tabela_tendencia(df_range):
    """Tabela: por fundo, média, máx histórico, % dias crítico, tendência."""
    if df_range.empty:
        return ''

    rows = []
    for fundo in df_range['fundo'].unique():
        sub = df_range[df_range['fundo'] == fundo].sort_values('date_ref')
        bps = sub['max_dif_bps'].dropna()
        if bps.empty:
            continue

        media    = bps.mean()
        maximo   = bps.max()
        pct_cr   = (sub['status'] == 'CRITICO').mean() * 100
        pct_at   = (sub['status'] == 'ATENCAO').mean() * 100

        # tendência: regressão linear simples nos últimos pontos
        if len(bps) >= 3:
            x  = np.arange(len(bps))
            coef = np.polyfit(x, bps.values, 1)[0]
            if coef > 0.1:
                trend = '↑ piorando'
                trend_cor = _COR_CRITICO
            elif coef < -0.1:
                trend = '↓ melhorando'
                trend_cor = _COR_OK
            else:
                trend = '→ estável'
                trend_cor = _COR_ATENCAO
        else:
            trend, trend_cor = '—', _COR_CINZA

        rows.append(dict(
            fundo=fundo, media_bps=f'{media:.4f}', max_bps=f'{maximo:.4f}',
            pct_critico=f'{pct_cr:.1f}%', pct_atencao=f'{pct_at:.1f}%',
            _trend=trend, _trend_cor=trend_cor
        ))

    if not rows:
        return ''

    cols = ['fundo', 'media_bps', 'max_bps', 'pct_critico', 'pct_atencao', '_trend']
    headers = ''.join(f'<th>{c.lstrip("_")}</th>' for c in cols)
    rows_html = ''
    for r in rows:
        cells = ''
        for col in cols:
            val = r[col]
            if col == '_trend':
                cor = r['_trend_cor']
                cells += f'<td style="font-weight:bold;color:{cor}">{val}</td>'
            else:
                cells += f'<td>{val}</td>'
        rows_html += f'<tr>{cells}</tr>'

    table = f'<table><thead><tr>{headers}</tr></thead><tbody>{rows_html}</tbody></table>'
    return f'<div class="section"><h2>Análise de Tendência por Fundo</h2>{table}</div>'


def _section_piores_dias(df_range):
    """Top 10 piores observações (data + fundo) por max_dif_bps."""
    if df_range.empty or 'max_dif_bps' not in df_range.columns:
        return ''

    cols = ['date_ref', 'fundo', 'status', 'max_dif_bps', 'soma_dif_pnl($)', 'ativos_ausentes']
    cols_exist = [c for c in cols if c in df_range.columns]
    top = df_range.nlargest(10, 'max_dif_bps')[cols_exist]

    rows_html = ''
    for _, row in top.iterrows():
        cells = ''
        for col in cols_exist:
            val = row[col]
            if col == 'status':
                cor = _STATUS_COLORS.get(str(val), '#ccc')
                cells += (f'<td><span style="background:{cor};color:white;'
                          f'padding:1px 8px;border-radius:3px">{val}</span></td>')
            elif col == 'max_dif_bps':
                cor = (_COR_CRITICO if val >= LIMITE_VERMELHO
                       else _COR_ATENCAO if val >= LIMITE_AMARELO else _COR_OK)
                cells += f'<td style="font-weight:bold;color:{cor}">{val:.4f}</td>'
            elif isinstance(val, float):
                cells += f'<td>{val:,.2f}</td>'
            else:
                cells += f'<td>{val}</td>'
        rows_html += f'<tr>{cells}</tr>'

    headers = ''.join(f'<th>{c}</th>' for c in cols_exist)
    table   = f'<table><thead><tr>{headers}</tr></thead><tbody>{rows_html}</tbody></table>'
    return f'<div class="section"><h2>Top 10 Piores Observações do Range</h2>{table}</div>'


# =============================================================================
# PDF DO RANGE
# =============================================================================

def _build_pdf_range(df_range, df_stats_range, date_start, date_end, pdf_path):
    from batimento import _make_fig_table

    def _save(pdf, fig):
        if fig:
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)

    with PdfPages(pdf_path) as pdf:
        _save(pdf, _make_fig_capa_range(date_start, date_end, df_range))
        _save(pdf, _make_fig_timeseries(df_range))
        _save(pdf, _make_fig_heatmap_data_fundo(df_range))
        _save(pdf, _make_fig_heatmap_data_classe(df_stats_range))
        _save(pdf, _make_fig_dias_criticos(df_range))
        _save(pdf, _make_fig_trend_bps(df_range))

        # Tabela pivot resumo
        if not df_range.empty and 'max_dif_bps' in df_range.columns:
            pivot = (df_range.pivot_table(
                values='max_dif_bps', index='date_ref', columns='fundo', aggfunc='max'
            ).reset_index().round(4))
            _save(pdf, _make_fig_table(pivot, f'Evolução Dia a Dia ({date_start} → {date_end})'))

        # Tabela stats por classe no range
        if not df_stats_range.empty:
            stats_agg = (df_stats_range.groupby(['date_ref', 'classe'])
                         .agg(max_abs_bps=('max_abs_bps', 'max'),
                              soma_dif_pnl=('soma_dif_pnl', 'sum'))
                         .reset_index().round(4))
            _save(pdf, _make_fig_table(stats_agg, 'Stats por Classe no Range'))

        info = pdf.infodict()
        info['Title']   = f'Report Range {date_start} → {date_end}'
        info['Author']  = 'VCRA / IAM'
        info['Subject'] = 'Batimento PnL — Análise Temporal'


def _make_fig_capa_range(date_start, date_end, df_range):
    n_dias   = df_range['date_ref'].nunique() if not df_range.empty else 0
    n_fundos = df_range['fundo'].nunique()    if not df_range.empty else 0

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.axis('off')
    fig.patch.set_facecolor(_COR_AZUL)

    ax.text(0.5, 0.82, 'Report Batimento PnL — Análise Temporal',
            transform=ax.transAxes, fontsize=22, fontweight='bold',
            color='white', ha='center')
    ax.text(0.5, 0.68, f'{date_start}  →  {date_end}',
            transform=ax.transAxes, fontsize=16, color='#ccddee', ha='center')
    ax.text(0.5, 0.60, f'Gerado em: {_DH_RANGE.replace("_", " ")}',
            transform=ax.transAxes, fontsize=10, color='#aabbcc', ha='center')

    kpis = [('Dias Úteis', str(n_dias), 'white'),
            ('Fundos', str(n_fundos), 'white')]
    if not df_range.empty and 'status' in df_range.columns:
        n_cr = int((df_range['status'] == 'CRITICO').sum())
        kpis.append(('Obs. CRÍTICO', str(n_cr), _COR_CRITICO))

    xs = np.linspace(0.2, 0.8, len(kpis))
    for x, (label, value, cor) in zip(xs, kpis):
        ax.text(x, 0.38, value, transform=ax.transAxes,
                fontsize=32, fontweight='bold', color=cor, ha='center')
        ax.text(x, 0.28, label, transform=ax.transAxes,
                fontsize=11, color='#ccddee', ha='center')

    ax.text(0.5, 0.08, 'VCRA / IAM — Uso Interno',
            transform=ax.transAxes, fontsize=8, color='#778899', ha='center')
    plt.tight_layout()
    return fig


# =============================================================================
# HTML TEMPLATE
# =============================================================================

def _render_html_range(date_start, date_end, secoes):
    body = '\n'.join(secoes)
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Report Range {date_start} → {date_end}</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0 }}
  body {{ font-family:'Segoe UI',Arial,sans-serif; background:#f0f2f5; color:#333; padding:24px }}
  header {{ background:{_COR_AZUL}; color:white; border-radius:8px; padding:18px 26px; margin-bottom:22px }}
  header h1 {{ font-size:20px; font-weight:700 }}
  header p  {{ font-size:12px; opacity:.8; margin-top:4px }}
  .section  {{ background:white; border-radius:8px; padding:20px 22px; margin-bottom:18px;
               box-shadow:0 1px 4px rgba(0,0,0,.08) }}
  .section h2 {{ font-size:14px; font-weight:700; color:{_COR_AZUL}; margin-bottom:14px;
                 border-left:4px solid {_COR_AZUL}; padding-left:9px }}
  .section img {{ max-width:100%; border-radius:4px }}
  table {{ border-collapse:collapse; width:100%; font-size:12px }}
  thead tr {{ background:{_COR_AZUL}; color:white }}
  th {{ padding:8px 10px; text-align:left; font-weight:600; white-space:nowrap }}
  td {{ padding:6px 10px; border-bottom:1px solid #eee; white-space:nowrap }}
  tr:hover td {{ background:#f5f8ff }}
  .kpi-grid {{ display:flex; flex-wrap:wrap; gap:14px }}
  .kpi-card {{ background:#f8f9fb; border-radius:8px; padding:14px 18px; min-width:120px;
               border:1px solid #e2e8f0; flex:1 }}
  .kpi-value {{ font-size:26px; font-weight:800 }}
  .kpi-label {{ font-size:11px; color:#666; margin-top:3px }}
  footer {{ text-align:center; font-size:10px; color:#aaa; margin-top:28px }}
</style>
</head>
<body>
<header>
  <h1>Report Batimento PnL — Análise Temporal</h1>
  <p>Range: <strong>{date_start}</strong> → <strong>{date_end}</strong>
     &nbsp;|&nbsp; Gerado em: {_DH_RANGE.replace('_',' ')}</p>
</header>
{body}
<footer>VCRA / IAM — Uso Interno</footer>
</body>
</html>"""


# =============================================================================
# HELPERS
# =============================================================================

def _wrap_fig(fig, title):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=130, bbox_inches='tight')
    buf.seek(0)
    img = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return (f'<div class="section"><h2>{title}</h2>'
            f'<img src="data:image/png;base64,{img}"/></div>')


def _rotate_xaxis(ax, rotation=35):
    for label in ax.get_xticklabels():
        label.set_rotation(rotation)
        label.set_ha('right')
        label.set_fontsize(8)
