"""
analise_divergencias.py
Funções de análise detalhada de divergências para o Report Batimento PnL.
Detecta automaticamente colunas de posição, preço e PnL disponíveis no df_final.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.colors as mcolors

# ── constantes (replicadas do batimento.py para uso standalone) ──────────────
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

# Colunas que são sempre identificadores (não entram nos grupos de detalhe)
_ID_COLS = {
    'classe', 'codigo_IAM_fundo', 'codigo_IAM_ativo', 'ticker_bolsa',
    'Existe', 'dif_total_bps', 'dif_pnl_total($)', 'pnl_total_VCRA',
    'last_patrimonio'
}

# Palavras-chave para cada grupo de colunas
_KW_POSICAO = ['qtd', 'quantidade', 'posicao', 'pos_', 'notional', 'nominal',
               'exposicao', 'saldo']
_KW_PRECO   = ['preco', 'price', 'pu', 'cota', 'taxa', 'spread', 'yield',
               'px', 'vna', 'fator']
_KW_PNL     = ['pnl', 'mtm', 'resultado', 'ganho', 'perda', 'carry',
               'receita', 'custo', 'accrual']
_KW_DIF     = ['dif_', '_dif', 'diff_', '_diff', 'erro_', 'diverge']


# =============================================================================
# DETECÇÃO AUTOMÁTICA DE COLUNAS
# =============================================================================

def detect_col_groups(df):
    """
    Retorna dict com grupos de colunas detectadas no df_final:
      posicao, preco, pnl, diferenca, sistema, vcra, outros_numericos
    """
    groups = {g: [] for g in ('posicao', 'preco', 'pnl', 'diferenca',
                               'sistema', 'vcra', 'outros_numericos')}

    for col in df.columns:
        if col in _ID_COLS:
            continue
        cl = col.lower()

        if any(k in cl for k in _KW_DIF):
            groups['diferenca'].append(col)
        elif any(k in cl for k in _KW_POSICAO):
            groups['posicao'].append(col)
        elif any(k in cl for k in _KW_PRECO):
            groups['preco'].append(col)
        elif any(k in cl for k in _KW_PNL):
            groups['pnl'].append(col)
        elif cl.endswith('_iam') or cl.endswith('_sistema') or cl.endswith('_sys'):
            groups['sistema'].append(col)
        elif cl.endswith('_vcra'):
            groups['vcra'].append(col)
        elif df[col].dtype in (np.float64, np.int64, float, int):
            groups['outros_numericos'].append(col)

    return groups


def _detail_cols_ordered(df):
    """
    Retorna lista ordenada de colunas para a tabela de detalhe:
    identificadores + posição + preço + PnL + diferenças + resto.
    """
    grp = detect_col_groups(df)

    id_present = [c for c in
                  ['classe', 'codigo_IAM_ativo', 'ticker_bolsa',
                   'Existe', 'dif_total_bps', 'dif_pnl_total($)']
                  if c in df.columns]

    ordered = (id_present
               + grp['posicao']
               + grp['preco']
               + grp['pnl']
               + grp['diferenca']
               + grp['sistema']
               + grp['vcra']
               + grp['outros_numericos'])

    seen = set()
    return [c for c in ordered if not (c in seen or seen.add(c))]


# =============================================================================
# FIGURAS
# =============================================================================

def make_fig_heatmap(df_final):
    """Heatmap fundo × classe — máx |dif_total_bps|."""
    if df_final.empty or 'dif_total_bps' not in df_final.columns:
        return None
    if 'classe' not in df_final.columns or 'codigo_IAM_fundo' not in df_final.columns:
        return None

    pivot = df_final.pivot_table(
        values='dif_total_bps',
        index='codigo_IAM_fundo',
        columns='classe',
        aggfunc=lambda x: x.abs().max()
    ).fillna(0)

    if pivot.empty:
        return None

    n_fundos, n_classes = pivot.shape
    fig_h = max(4, n_fundos * 0.55 + 1.5)
    fig_w = max(8, n_classes * 1.4 + 2)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    # colormap: branco → amarelo → vermelho
    cmap = mcolors.LinearSegmentedColormap.from_list(
        'semaforo', ['#f7fff7', _COR_ATENCAO, _COR_CRITICO]
    )

    im = ax.imshow(pivot.values, cmap=cmap, aspect='auto',
                   vmin=0, vmax=max(LIMITE_VERMELHO * 1.5, pivot.values.max()))

    ax.set_xticks(range(n_classes))
    ax.set_xticklabels(pivot.columns, rotation=35, ha='right', fontsize=9)
    ax.set_yticks(range(n_fundos))
    ax.set_yticklabels(pivot.index, fontsize=9)

    # anotações com valor
    for i in range(n_fundos):
        for j in range(n_classes):
            val = pivot.values[i, j]
            if val > 0:
                txt_color = 'white' if val >= LIMITE_VERMELHO else 'black'
                ax.text(j, i, f'{val:.2f}', ha='center', va='center',
                        fontsize=7.5, color=txt_color, fontweight='bold')

    plt.colorbar(im, ax=ax, label='bps', shrink=0.7)
    ax.set_title('Heatmap: Máx Divergência por Fundo × Classe (bps)',
                 fontsize=12, fontweight='bold', color=_COR_AZUL, pad=10)
    plt.tight_layout()
    return fig


def make_fig_waterfall(df_stats):
    """Waterfall da contribuição de cada classe à soma total de dif_pnl."""
    if df_stats.empty or 'soma_dif_pnl' not in df_stats.columns:
        return None

    df_plot = df_stats[['classe', 'soma_dif_pnl']].copy()
    df_plot = df_plot.sort_values('soma_dif_pnl', ascending=False).reset_index(drop=True)
    total   = df_plot['soma_dif_pnl'].sum()

    # acumulado para o waterfall
    running = 0
    bottoms, tops, colors, labels = [], [], [], []
    for _, row in df_plot.iterrows():
        v = row['soma_dif_pnl']
        bottoms.append(running if v >= 0 else running + v)
        tops.append(abs(v))
        colors.append(_COR_CRITICO if v < 0 else '#4ECDC4')
        labels.append(row['classe'])
        running += v

    # barra total
    labels.append('TOTAL')
    bottoms.append(min(0, total))
    tops.append(abs(total))
    colors.append(_COR_AZUL)

    fig, ax = plt.subplots(figsize=(max(9, len(labels) * 1.1), 5))
    x = np.arange(len(labels))
    bars = ax.bar(x, tops, bottom=bottoms, color=colors, edgecolor='white', linewidth=0.5)

    # linha zero
    ax.axhline(0, color='black', linewidth=0.8, linestyle='-')

    # rótulos de valor
    for bar, b, t, v_orig in zip(bars, bottoms, tops,
                                  df_plot['soma_dif_pnl'].tolist() + [total]):
        ypos = b + t / 2
        ax.text(bar.get_x() + bar.get_width() / 2, ypos,
                f'R${v_orig:,.0f}', ha='center', va='center',
                fontsize=8, fontweight='bold',
                color='white' if abs(v_orig) > 0 else 'black')

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha='right', fontsize=9)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'R${v:,.0f}'))
    ax.set_title('Waterfall: Contribuição ao Dif PnL Total por Classe (R$)',
                 fontsize=12, fontweight='bold', color=_COR_AZUL)
    ax.spines[['top', 'right']].set_visible(False)
    plt.tight_layout()
    return fig


def make_fig_scatter(df_final):
    """Scatter: valor absoluto da posição financeira vs divergência em bps, por classe."""
    if df_final.empty or 'dif_total_bps' not in df_final.columns:
        return None

    grp = detect_col_groups(df_final)

    # tenta encontrar coluna de posição financeira
    pos_col = None
    for c in grp['posicao'] + grp['pnl'] + grp['vcra'] + grp['sistema']:
        if df_final[c].notna().sum() > 0:
            pos_col = c
            break

    if pos_col is None or 'dif_pnl_total($)' not in df_final.columns:
        return None

    df_plot = df_final[['classe', 'dif_total_bps', 'dif_pnl_total($)', pos_col]].dropna()
    if df_plot.empty:
        return None

    classes   = df_plot['classe'].unique()
    cmap_list = plt.get_cmap('tab10')
    class_colors = {c: mcolors.to_hex(cmap_list(i % 10)) for i, c in enumerate(classes)}

    fig, ax = plt.subplots(figsize=(10, 6))

    for cls in classes:
        sub = df_plot[df_plot['classe'] == cls]
        ax.scatter(sub[pos_col].abs(), sub['dif_total_bps'].abs(),
                   c=class_colors[cls], label=cls, alpha=0.7,
                   s=sub['dif_pnl_total($)'].abs().clip(upper=5000) / 20 + 20,
                   edgecolors='white', linewidth=0.4)

    ax.axhline(LIMITE_VERMELHO, color=_COR_CRITICO, linestyle='--', linewidth=1, alpha=0.7)
    ax.axhline(LIMITE_AMARELO, color=_COR_ATENCAO,  linestyle='--', linewidth=1, alpha=0.7)
    ax.set_xlabel(f'|{pos_col}|', fontsize=10)
    ax.set_ylabel('|dif_total_bps|', fontsize=10)
    ax.set_title('Posição Financeira vs Divergência (bps)\n(tamanho = |dif PnL R$|)',
                 fontsize=12, fontweight='bold', color=_COR_AZUL)
    ax.legend(fontsize=8, bbox_to_anchor=(1.01, 1), loc='upper left')
    ax.spines[['top', 'right']].set_visible(False)
    plt.tight_layout()
    return fig


def make_fig_top_ativos_barh(df_final, n=15):
    """Gráfico de barras horizontal com os N ativos de maior divergência absoluta."""
    if df_final.empty or 'dif_total_bps' not in df_final.columns:
        return None

    col_label = 'ticker_bolsa' if 'ticker_bolsa' in df_final.columns else 'codigo_IAM_ativo'
    cols_need = ['codigo_IAM_fundo', col_label, 'dif_total_bps', 'dif_pnl_total($)']
    cols_exist = [c for c in cols_need if c in df_final.columns]

    df_plot = (df_final[cols_exist]
               .dropna(subset=['dif_total_bps'])
               .assign(abs_bps=lambda d: d['dif_total_bps'].abs())
               .nlargest(n, 'abs_bps'))

    if df_plot.empty:
        return None

    label_col = col_label if col_label in df_plot.columns else cols_exist[0]
    labels = (df_plot[label_col].astype(str)
              + ' (' + df_plot['codigo_IAM_fundo'].astype(str) + ')')
    values = df_plot['dif_total_bps'].values
    colors = [_COR_CRITICO if abs(v) >= LIMITE_VERMELHO
              else _COR_ATENCAO if abs(v) >= LIMITE_AMARELO
              else _COR_OK for v in values]

    fig, ax = plt.subplots(figsize=(11, max(4, n * 0.45)))
    ax.barh(range(len(labels)), values, color=colors, edgecolor='white')
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.axvline(0, color='black', linewidth=0.8)
    ax.axvline( LIMITE_VERMELHO, color=_COR_CRITICO, linestyle='--', linewidth=1, alpha=0.6)
    ax.axvline(-LIMITE_VERMELHO, color=_COR_CRITICO, linestyle='--', linewidth=1, alpha=0.6)
    ax.axvline( LIMITE_AMARELO, color=_COR_ATENCAO,  linestyle='--', linewidth=1, alpha=0.6)
    ax.axvline(-LIMITE_AMARELO, color=_COR_ATENCAO,  linestyle='--', linewidth=1, alpha=0.6)
    ax.invert_yaxis()
    ax.set_xlabel('dif_total_bps', fontsize=10)
    ax.set_title(f'Top {n} Ativos com Maior Divergência (bps)',
                 fontsize=12, fontweight='bold', color=_COR_AZUL)
    ax.spines[['top', 'right']].set_visible(False)
    plt.tight_layout()
    return fig


# =============================================================================
# SEÇÕES HTML
# =============================================================================

def section_detalhes_por_fundo(df_final, df_semaforo):
    """
    Tabela detalhada (posição, preço, PnL) para cada fundo com status
    ATENÇÃO ou CRÍTICO, mostrando só as colunas disponíveis.
    """
    if df_final.empty or df_semaforo.empty:
        return ''

    fundos_criticos = df_semaforo[
        df_semaforo['status'].isin(['ATENCAO', 'CRITICO'])
    ]['fundo'].tolist()

    if not fundos_criticos:
        return ('<div class="section"><h2>Detalhamento por Fundo</h2>'
                '<p style="color:green">Nenhum fundo com divergência relevante.</p></div>')

    cols_ord = _detail_cols_ordered(df_final)
    grp = detect_col_groups(df_final)

    blocos = []
    for fundo in fundos_criticos:
        df_f = (df_final[df_final['codigo_IAM_fundo'] == fundo]
                .sort_values('dif_total_bps', ascending=False, key=abs))
        if df_f.empty:
            continue

        status = df_semaforo.loc[df_semaforo['fundo'] == fundo, 'status'].values[0]
        cor    = _STATUS_COLORS.get(status, '#ccc')
        badge  = (f'<span style="background:{cor};color:white;'
                  f'padding:2px 10px;border-radius:4px;font-weight:bold">{status}</span>')

        cols_show = [c for c in cols_ord if c in df_f.columns]
        rows_html = ''
        for _, row in df_f[cols_show].iterrows():
            bps = row.get('dif_total_bps', 0)
            if pd.isna(bps):
                bps = 0
            row_cor = (_COR_CRITICO if abs(bps) >= LIMITE_VERMELHO
                       else _COR_ATENCAO if abs(bps) >= LIMITE_AMARELO else '')
            style = f'border-left:4px solid {row_cor}' if row_cor else ''

            cells = ''
            for col in cols_show:
                val = row[col]
                if col == 'dif_total_bps':
                    cells += (f'<td style="font-weight:bold;color:{row_cor}">'
                              f'{val:,.4f}</td>' if not pd.isna(val) else '<td>-</td>')
                elif col == 'Existe':
                    cor_ex = _COR_CRITICO if val == False else _COR_OK
                    cells += f'<td style="color:{cor_ex};font-weight:bold">{val}</td>'
                elif isinstance(val, float) and not pd.isna(val):
                    cells += f'<td>{val:,.2f}</td>'
                else:
                    cells += f'<td>{"-" if pd.isna(val) else val}</td>'

            rows_html += f'<tr style="{style}">{cells}</tr>'

        headers  = ''.join(f'<th>{c}</th>' for c in cols_show)
        col_info = _col_group_legend(cols_show, grp)
        table    = (f'<table><thead><tr>{headers}</tr></thead>'
                    f'<tbody>{rows_html}</tbody></table>')

        blocos.append(
            f'<div class="sub-section">'
            f'<h3>{fundo} &nbsp;{badge}</h3>'
            f'<p class="col-info">{col_info}</p>'
            f'{table}</div>'
        )

    if not blocos:
        return ''

    inner = '\n'.join(blocos)
    return f'<div class="section"><h2>Detalhamento por Fundo (Atenção / Crítico)</h2>{inner}</div>'


def section_aluguel_detail(df_aluguel):
    """Seção HTML com detalhamento do aluguel."""
    if df_aluguel is None or df_aluguel.empty:
        return ''

    cols_ord = _detail_cols_ordered(df_aluguel)
    cols_show = [c for c in cols_ord if c in df_aluguel.columns]

    rows_html = ''
    for _, row in df_aluguel.sort_values(
            'dif_total_bps', ascending=False, key=abs
    ).iterrows() if 'dif_total_bps' in df_aluguel.columns else df_aluguel.iterrows():
        cells = ''
        for col in cols_show:
            val = row[col]
            if isinstance(val, float) and not pd.isna(val):
                cells += f'<td>{val:,.4f}</td>'
            else:
                cells += f'<td>{"-" if pd.isna(val) else val}</td>'
        rows_html += f'<tr>{cells}</tr>'

    headers = ''.join(f'<th>{c}</th>' for c in cols_show)
    table   = f'<table><thead><tr>{headers}</tr></thead><tbody>{rows_html}</tbody></table>'
    return f'<div class="section"><h2>Detalhamento Aluguel ({len(df_aluguel)} linhas)</h2>{table}</div>'


def section_macro_detail(df_macro):
    """Seção HTML com detalhamento dos erros macro."""
    if df_macro is None or df_macro.empty:
        return ''

    cols_show = df_macro.columns.tolist()
    rows_html = ''
    for _, row in df_macro.iterrows():
        cells = ''.join(
            f'<td>{val:,.4f}</td>' if isinstance(val, float) and not pd.isna(val)
            else f'<td>{"-" if pd.isna(val) else val}</td>'
            for col, val in row.items()
        )
        rows_html += f'<tr>{cells}</tr>'

    headers = ''.join(f'<th>{c}</th>' for c in cols_show)
    table   = f'<table><thead><tr>{headers}</tr></thead><tbody>{rows_html}</tbody></table>'
    return f'<div class="section"><h2>Macro Erros ({len(df_macro)} linhas)</h2>{table}</div>'


def section_resumo_colunas(df_final):
    """
    Seção informativa mostrando quais colunas de detalhe foram detectadas
    (útil para validar o que o sistema está enviando).
    """
    if df_final.empty:
        return ''

    grp = detect_col_groups(df_final)
    rows = ''
    for grupo, cols in grp.items():
        if cols:
            cols_txt = ', '.join(f'<code>{c}</code>' for c in cols)
            rows += f'<tr><td><strong>{grupo}</strong></td><td>{cols_txt}</td></tr>'

    if not rows:
        return ''

    table = f'<table><thead><tr><th>Grupo</th><th>Colunas detectadas</th></tr></thead><tbody>{rows}</tbody></table>'
    return f'<div class="section"><h2>Colunas Detectadas no df_final</h2>{table}</div>'


# =============================================================================
# HELPERS INTERNOS
# =============================================================================

def _col_group_legend(cols_show, grp):
    """Texto informativo: quantas colunas de cada grupo foram incluídas."""
    partes = []
    for nome, lista in [('posição', grp['posicao']), ('preço', grp['preco']),
                         ('PnL', grp['pnl']), ('diferença', grp['diferenca'])]:
        n = sum(1 for c in lista if c in cols_show)
        if n:
            partes.append(f'{n} col. de {nome}')
    return ' | '.join(partes) if partes else ''
