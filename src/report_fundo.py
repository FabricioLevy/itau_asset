"""
report_fundo.py
Gera relatório HTML/PDF detalhado por fundo: posição, preço, PnL e divergências.
"""
import io
import base64
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.backends.backend_pdf import PdfPages

from analise_divergencias import (
    detect_col_groups, _detail_cols_ordered,
    LIMITE_AMARELO, LIMITE_VERMELHO,
    _COR_OK, _COR_ATENCAO, _COR_CRITICO, _COR_AZUL, _COR_CINZA, _STATUS_COLORS,
)


# =============================================================================
# ENTRADA PRINCIPAL
# =============================================================================

def gerar_report_fundo(fundo, df_fundo, df_aluguel_fundo, df_stats_fundo,
                       df_semaforo, date_ref, output_dir, data_hora_atual,
                       gerar_pdf=True):
    """
    Gera relatório HTML (e opcionalmente PDF) detalhado para um único fundo.
    Chamado dentro do loop por fundo em rodar_batimento().
    """
    row_sem = df_semaforo[df_semaforo['fundo'] == fundo]
    status      = row_sem['status'].values[0]      if not row_sem.empty else 'SEM DADO'
    max_bps     = row_sem['max_dif_bps'].values[0]     if not row_sem.empty else np.nan
    soma_dif    = row_sem['soma_dif_pnl($)'].values[0] if not row_sem.empty else np.nan
    n_ativos    = int(row_sem['total_ativos'].values[0])    if not row_sem.empty else 0
    n_ausentes  = int(row_sem['ativos_ausentes'].values[0]) if not row_sem.empty else 0

    meta = dict(fundo=fundo, status=status, max_bps=max_bps,
                soma_dif=soma_dif, n_ativos=n_ativos, n_ausentes=n_ausentes)

    # HTML
    html = _build_html_fundo(df_fundo, df_aluguel_fundo, df_stats_fundo,
                              meta, date_ref, data_hora_atual)
    html_path = output_dir / f"Report_{fundo}_{date_ref.replace('-', '')}_{data_hora_atual}.html"
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  Report fundo: {html_path}")

    # PDF
    if gerar_pdf:
        pdf_path = output_dir / f"Report_{fundo}_{date_ref.replace('-', '')}_{data_hora_atual}.pdf"
        _build_pdf_fundo(df_fundo, df_aluguel_fundo, df_stats_fundo,
                         meta, date_ref, data_hora_atual, pdf_path)
        print(f"  PDF fundo:   {pdf_path}")

    return html_path


# =============================================================================
# HTML
# =============================================================================

def _build_html_fundo(df_fundo, df_aluguel_fundo, df_stats_fundo,
                      meta, date_ref, data_hora_atual):
    secoes = []
    secoes.append(_section_kpis_fundo(meta))

    fig = _make_fig_bps_por_classe(df_fundo, meta['fundo'])
    if fig:
        secoes.append(_wrap_fig(fig, f"Divergência por Classe — {meta['fundo']}"))

    fig = _make_fig_top_ativos(df_fundo, meta['fundo'])
    if fig:
        secoes.append(_wrap_fig(fig, 'Top Ativos por Divergência'))

    secoes.append(_section_tabela_completa(df_fundo))

    if df_aluguel_fundo is not None and not df_aluguel_fundo.empty:
        secoes.append(_section_tabela_generica(df_aluguel_fundo, 'Aluguel'))

    if df_stats_fundo is not None and not df_stats_fundo.empty:
        secoes.append(_section_tabela_generica(df_stats_fundo, 'Stats por Classe'))

    body = '\n'.join(secoes)
    cor_status = _STATUS_COLORS.get(meta['status'], '#ccc')
    badge = (f'<span style="background:{cor_status};color:white;padding:3px 12px;'
             f'border-radius:4px;font-weight:bold">{meta["status"]}</span>')

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Report {meta['fundo']} — {date_ref}</title>
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
  .div-critico {{ border-left:3px solid {_COR_CRITICO} }}
  .div-atencao {{ border-left:3px solid {_COR_ATENCAO} }}
  .kpi-grid {{ display:flex; flex-wrap:wrap; gap:14px }}
  .kpi-card {{ background:#f8f9fb; border-radius:8px; padding:14px 18px; min-width:120px;
               border:1px solid #e2e8f0; flex:1 }}
  .kpi-value {{ font-size:26px; font-weight:800 }}
  .kpi-label {{ font-size:11px; color:#666; margin-top:3px }}
  .tag-grupo  {{ display:inline-block; font-size:10px; padding:1px 6px; border-radius:3px;
                 margin-right:4px; font-weight:600 }}
  footer {{ text-align:center; font-size:10px; color:#aaa; margin-top:28px }}
</style>
</head>
<body>
<header>
  <h1>{meta['fundo']} &nbsp; {badge}</h1>
  <p>Data de referência: <strong>{date_ref}</strong> &nbsp;|&nbsp; Gerado em: {data_hora_atual.replace('_',' ')}</p>
</header>
{body}
<footer>VCRA / IAM — Uso Interno</footer>
</body>
</html>"""


def _section_kpis_fundo(meta):
    def card(label, value, color=_COR_AZUL):
        return (f'<div class="kpi-card">'
                f'<div class="kpi-value" style="color:{color}">{value}</div>'
                f'<div class="kpi-label">{label}</div></div>')

    max_bps_fmt  = f'{meta["max_bps"]:,.4f}' if not pd.isna(meta["max_bps"]) else '-'
    soma_fmt     = f'R$ {meta["soma_dif"]:,.2f}' if not pd.isna(meta["soma_dif"]) else '-'
    cor_bps      = (_COR_CRITICO if not pd.isna(meta["max_bps"]) and meta["max_bps"] >= LIMITE_VERMELHO
                    else _COR_ATENCAO if not pd.isna(meta["max_bps"]) and meta["max_bps"] >= LIMITE_AMARELO
                    else _COR_OK)

    cards = (
        card('Máx Dif (bps)',     max_bps_fmt,         cor_bps)
        + card('Soma Dif PnL',    soma_fmt,             _COR_AZUL)
        + card('Total Ativos',    meta['n_ativos'])
        + card('Ativos Ausentes', meta['n_ausentes'],   _COR_CINZA if meta['n_ausentes'] > 0 else _COR_OK)
    )
    return f'<div class="section"><h2>KPIs do Fundo</h2><div class="kpi-grid">{cards}</div></div>'


def _section_tabela_completa(df_fundo):
    """Tabela com todas as colunas disponíveis, agrupadas por categoria."""
    if df_fundo is None or df_fundo.empty:
        return ''

    grp = detect_col_groups(df_fundo)
    cols_ord = _detail_cols_ordered(df_fundo)
    cols_show = [c for c in cols_ord if c in df_fundo.columns]

    # legenda de grupos
    tags_html = ''
    tag_styles = {
        'posicao':  ('Posição',    '#dbeafe', '#1d4ed8'),
        'preco':    ('Preço',      '#fef9c3', '#854d0e'),
        'pnl':      ('PnL',        '#dcfce7', '#166534'),
        'diferenca':('Diferença',  '#fee2e2', '#991b1b'),
        'sistema':  ('Sistema',    '#ede9fe', '#5b21b6'),
        'vcra':     ('VCRA',       '#e0f2fe', '#0369a1'),
    }
    for grupo, (label, bg, fg) in tag_styles.items():
        n = sum(1 for c in grp[grupo] if c in cols_show)
        if n:
            tags_html += (f'<span class="tag-grupo" style="background:{bg};color:{fg}">'
                          f'{label} ({n})</span>')

    df_sorted = df_fundo[cols_show].sort_values(
        'dif_total_bps', ascending=False, key=abs
    ) if 'dif_total_bps' in cols_show else df_fundo[cols_show]

    rows_html = ''
    for _, row in df_sorted.iterrows():
        bps = row.get('dif_total_bps', 0)
        if pd.isna(bps):
            bps = 0
        if abs(bps) >= LIMITE_VERMELHO:
            row_cls = 'div-critico'
        elif abs(bps) >= LIMITE_AMARELO:
            row_cls = 'div-atencao'
        else:
            row_cls = ''

        cells = ''
        for col in cols_show:
            val = row[col]
            if col == 'dif_total_bps':
                cor = (_COR_CRITICO if abs(bps) >= LIMITE_VERMELHO
                       else _COR_ATENCAO if abs(bps) >= LIMITE_AMARELO else _COR_OK)
                cells += (f'<td style="font-weight:bold;color:{cor}">'
                          f'{val:,.4f}</td>' if not pd.isna(val) else '<td>-</td>')
            elif col == 'Existe':
                cor_ex = _COR_CRITICO if val == False else ''
                cells += f'<td style="color:{cor_ex};font-weight:bold">{val}</td>'
            elif isinstance(val, float) and not pd.isna(val):
                cells += f'<td>{val:,.4f}</td>'
            else:
                cells += f'<td>{"-" if pd.isna(val) else val}</td>'

        rows_html += f'<tr class="{row_cls}">{cells}</tr>'

    headers = ''.join(f'<th>{c}</th>' for c in cols_show)
    table   = f'<table><thead><tr>{headers}</tr></thead><tbody>{rows_html}</tbody></table>'

    return (f'<div class="section"><h2>Tabela Completa de Divergências</h2>'
            f'<p style="margin-bottom:10px">{tags_html}</p>'
            f'<div style="overflow-x:auto">{table}</div></div>')


def _section_tabela_generica(df, titulo):
    """Tabela HTML simples para qualquer DataFrame."""
    if df is None or df.empty:
        return ''

    rows_html = ''
    for _, row in df.iterrows():
        cells = ''.join(
            f'<td>{val:,.4f}</td>' if isinstance(val, float) and not pd.isna(val)
            else f'<td>{"-" if pd.isna(val) else val}</td>'
            for val in row
        )
        rows_html += f'<tr>{cells}</tr>'

    headers = ''.join(f'<th>{c}</th>' for c in df.columns)
    table   = f'<table><thead><tr>{headers}</tr></thead><tbody>{rows_html}</tbody></table>'
    return (f'<div class="section"><h2>{titulo}</h2>'
            f'<div style="overflow-x:auto">{table}</div></div>')


# =============================================================================
# FIGURAS
# =============================================================================

def _make_fig_bps_por_classe(df_fundo, fundo):
    if df_fundo is None or df_fundo.empty:
        return None
    if 'classe' not in df_fundo.columns or 'dif_total_bps' not in df_fundo.columns:
        return None

    stats = (df_fundo.groupby('classe')['dif_total_bps']
             .agg(max_abs=lambda x: x.abs().max(), soma=lambda x: x.sum())
             .sort_values('max_abs', ascending=False)
             .reset_index())

    if stats.empty:
        return None

    colors = [_COR_CRITICO if v >= LIMITE_VERMELHO
              else _COR_ATENCAO if v >= LIMITE_AMARELO
              else _COR_OK for v in stats['max_abs']]

    fig, axes = plt.subplots(1, 2, figsize=(13, max(3.5, len(stats) * 0.55 + 1.5)))
    fig.suptitle(f'Divergência por Classe — {fundo}', fontsize=12,
                 fontweight='bold', color=_COR_AZUL)

    x = np.arange(len(stats))

    axes[0].bar(x, stats['max_abs'], color=colors, edgecolor='white')
    axes[0].axhline(LIMITE_VERMELHO, color=_COR_CRITICO, linestyle='--', linewidth=1)
    axes[0].axhline(LIMITE_AMARELO,  color=_COR_ATENCAO,  linestyle='--', linewidth=1)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(stats['classe'], rotation=35, ha='right', fontsize=9)
    axes[0].set_title('Máx |dif_total_bps|', fontsize=10)
    axes[0].spines[['top', 'right']].set_visible(False)

    bar_colors2 = [_COR_CRITICO if v < 0 else '#4ECDC4' for v in stats['soma']]
    axes[1].bar(x, stats['soma'], color=bar_colors2, edgecolor='white')
    axes[1].axhline(0, color='black', linewidth=0.8)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(stats['classe'], rotation=35, ha='right', fontsize=9)
    axes[1].set_title('Soma dif_total_bps', fontsize=10)
    axes[1].spines[['top', 'right']].set_visible(False)

    plt.tight_layout()
    return fig


def _make_fig_top_ativos(df_fundo, fundo, n=20):
    if df_fundo is None or df_fundo.empty or 'dif_total_bps' not in df_fundo.columns:
        return None

    col_label = 'ticker_bolsa' if 'ticker_bolsa' in df_fundo.columns else 'codigo_IAM_ativo'
    df_plot = (df_fundo[[col_label, 'dif_total_bps', 'classe']]
               .dropna(subset=['dif_total_bps'])
               .assign(abs_bps=lambda d: d['dif_total_bps'].abs())
               .nlargest(n, 'abs_bps'))

    if df_plot.empty:
        return None

    labels  = df_plot[col_label].astype(str)
    values  = df_plot['dif_total_bps'].values
    colors  = [_COR_CRITICO if abs(v) >= LIMITE_VERMELHO
               else _COR_ATENCAO if abs(v) >= LIMITE_AMARELO
               else _COR_OK for v in values]

    fig, ax = plt.subplots(figsize=(10, max(4, len(labels) * 0.45)))
    ax.barh(range(len(labels)), values, color=colors, edgecolor='white')
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.axvline(0, color='black', linewidth=0.8)
    ax.axvline( LIMITE_VERMELHO, color=_COR_CRITICO, linestyle='--', linewidth=1, alpha=0.6)
    ax.axvline(-LIMITE_VERMELHO, color=_COR_CRITICO, linestyle='--', linewidth=1, alpha=0.6)
    ax.axvline( LIMITE_AMARELO,  color=_COR_ATENCAO,  linestyle='--', linewidth=1, alpha=0.6)
    ax.axvline(-LIMITE_AMARELO,  color=_COR_ATENCAO,  linestyle='--', linewidth=1, alpha=0.6)
    ax.invert_yaxis()
    ax.set_xlabel('dif_total_bps', fontsize=9)
    ax.set_title(f'Top {n} Ativos — {fundo}', fontsize=11, fontweight='bold', color=_COR_AZUL)
    ax.spines[['top', 'right']].set_visible(False)
    plt.tight_layout()
    return fig


# =============================================================================
# PDF
# =============================================================================

def _build_pdf_fundo(df_fundo, df_aluguel_fundo, df_stats_fundo,
                     meta, date_ref, data_hora_atual, pdf_path):
    from batimento import _make_fig_table, _STATUS_COLORS as BAT_COLORS

    def _save(pdf, fig):
        if fig:
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)

    with PdfPages(pdf_path) as pdf:

        # Capa do fundo
        _save(pdf, _make_fig_capa_fundo(meta, date_ref, data_hora_atual))

        # Divergência por classe
        _save(pdf, _make_fig_bps_por_classe(df_fundo, meta['fundo']))

        # Top ativos
        _save(pdf, _make_fig_top_ativos(df_fundo, meta['fundo']))

        # Tabela completa (colunas detectadas)
        if df_fundo is not None and not df_fundo.empty:
            cols_ord  = _detail_cols_ordered(df_fundo)
            cols_show = [c for c in cols_ord if c in df_fundo.columns]
            df_sorted = (df_fundo[cols_show]
                         .sort_values('dif_total_bps', ascending=False, key=abs)
                         if 'dif_total_bps' in cols_show else df_fundo[cols_show])
            _save(pdf, _make_fig_table(df_sorted,
                                       f'Divergências Completas — {meta["fundo"]}'))

        # Aluguel
        if df_aluguel_fundo is not None and not df_aluguel_fundo.empty:
            _save(pdf, _make_fig_table(df_aluguel_fundo,
                                       f'Aluguel — {meta["fundo"]}'))

        # Stats
        if df_stats_fundo is not None and not df_stats_fundo.empty:
            _save(pdf, _make_fig_table(df_stats_fundo,
                                       f'Stats por Classe — {meta["fundo"]}'))

        info = pdf.infodict()
        info['Title']   = f'Report {meta["fundo"]} — {date_ref}'
        info['Author']  = 'VCRA / IAM'
        info['Subject'] = 'Batimento PnL por Fundo'


def _make_fig_capa_fundo(meta, date_ref, data_hora_atual):
    cor_status = _STATUS_COLORS.get(meta['status'], '#ccc')
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.axis('off')
    fig.patch.set_facecolor(_COR_AZUL)

    ax.text(0.5, 0.82, meta['fundo'], transform=ax.transAxes,
            fontsize=30, fontweight='bold', color='white', ha='center')
    ax.text(0.5, 0.68, f'Data de Referência: {date_ref}', transform=ax.transAxes,
            fontsize=14, color='#ccddee', ha='center')
    ax.text(0.5, 0.60, f'Gerado em: {data_hora_atual.replace("_", " ")}',
            transform=ax.transAxes, fontsize=10, color='#aabbcc', ha='center')

    # status badge
    ax.text(0.5, 0.48, meta['status'], transform=ax.transAxes,
            fontsize=22, fontweight='bold', color=cor_status, ha='center',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='white', alpha=0.15))

    kpis = [
        ('Máx bps', f'{meta["max_bps"]:.4f}' if not pd.isna(meta["max_bps"]) else '-', cor_status),
        ('Soma Dif', f'R${meta["soma_dif"]:,.0f}' if not pd.isna(meta["soma_dif"]) else '-', 'white'),
        ('Ativos',  str(meta['n_ativos']),   'white'),
        ('Ausentes', str(meta['n_ausentes']), _COR_CRITICO if meta['n_ausentes'] > 0 else _COR_OK),
    ]
    xs = np.linspace(0.12, 0.88, len(kpis))
    for x, (label, value, cor) in zip(xs, kpis):
        ax.text(x, 0.30, value, transform=ax.transAxes,
                fontsize=22, fontweight='bold', color=cor, ha='center')
        ax.text(x, 0.20, label, transform=ax.transAxes,
                fontsize=10, color='#ccddee', ha='center')

    ax.text(0.5, 0.07, 'VCRA / IAM — Uso Interno', transform=ax.transAxes,
            fontsize=8, color='#778899', ha='center')
    plt.tight_layout()
    return fig


# =============================================================================
# HELPER
# =============================================================================

def _wrap_fig(fig, title):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=130, bbox_inches='tight')
    buf.seek(0)
    img = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return (f'<div class="section"><h2>{title}</h2>'
            f'<img src="data:image/png;base64,{img}"/></div>')
