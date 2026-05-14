import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
from matplotlib.backends.backend_pdf import PdfPages
from pathlib import Path

from indexados import buscar_indexados, buscar_historico_fundo

OUTPUT_DIR = Path("../output")

def carregar_fundos_lista():
    """Carrega lista de fundos de ../input/fundos.txt"""
    caminho = Path("../input/fundos.txt")
    if not caminho.exists():
        print(f"⚠️ Arquivo {caminho} não encontrado. Usando todos os fundos.")
        return None
    
    with open(caminho, 'r') as f:
        fundos = [linha.strip() for linha in f if linha.strip()]
    
    print(f"📋 Carregados {len(fundos)} fundos da lista")
    return fundos

COLORS = {
    'fundo': '#1f77b4',
    'benchmark': '#ff7f0e',
    'diferenca': '#d62728',
    'patrimonio': '#2ca02c',
    'barra_pos': '#2ca02c',
    'barra_neg': '#d62728',
}


# ==============================
# PÁGINA DE RESUMO GERAL
# ==============================
def pagina_resumo(pdf, df):
    fig, axes = plt.subplots(2, 1, figsize=(16, 10))
    fig.suptitle('Resumo Indexados', fontsize=18, fontweight='bold', y=0.98)

    # --- Top: tabela resumo por fundo ---
    resumo = df.groupby('fundo').agg(
        dias=('data', 'nunique'),
        media_bps=('Diferenca_Bps', 'mean'),
        max_bps=('Diferenca_Bps', lambda x: x.abs().max()),
        soma_fin=('Diferenca_Fin', 'sum'),
    ).round(2).sort_values('max_bps', ascending=False)

    ax_tab = axes[0]
    ax_tab.axis('off')
    ax_tab.set_title('Resumo por Fundo', fontsize=13, fontweight='bold', loc='left')

    col_labels = ['Fundo', 'Dias c/ Diff', 'Média Bps', 'Max |Bps|', 'Soma Fin (R$)']
    cell_data = []
    for fundo, row in resumo.iterrows():
        cell_data.append([
            fundo,
            int(row['dias']),
            f"{row['media_bps']:.2f}",
            f"{row['max_bps']:.2f}",
            f"{row['soma_fin']:,.2f}",
        ])

    if cell_data:
        table = ax_tab.table(
            cellText=cell_data,
            colLabels=col_labels,
            loc='center',
            cellLoc='center',
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 1.4)
        for (r, c), cell in table.get_celld().items():
            if r == 0:
                cell.set_facecolor('#4472C4')
                cell.set_text_props(color='white', fontweight='bold')
            else:
                cell.set_facecolor('#f0f4fa' if r % 2 == 0 else 'white')

    # --- Bottom: barras de diferença média por fundo ---
    ax_bar = axes[1]
    ax_bar.set_title('Diferença Média (Bps) por Fundo', fontsize=13, fontweight='bold', loc='left')

    cores = [COLORS['barra_pos'] if v >= 0 else COLORS['barra_neg'] for v in resumo['media_bps']]
    bars = ax_bar.barh(resumo.index, resumo['media_bps'], color=cores, edgecolor='gray', linewidth=0.5)
    ax_bar.axvline(0, color='black', linewidth=0.8)
    ax_bar.set_xlabel('Bps')
    ax_bar.invert_yaxis()

    for bar, val in zip(bars, resumo['media_bps']):
        ax_bar.text(
            bar.get_width() + (0.05 * max(abs(resumo['media_bps'].max()), abs(resumo['media_bps'].min())) if val >= 0 else -0.05),
            bar.get_y() + bar.get_height() / 2,
            f'{val:.2f}', va='center', fontsize=8
        )

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    pdf.savefig(fig)
    plt.close(fig)


# ==============================
# PÁGINA DE DIFERENÇAS NO PERÍODO
# ==============================
def pagina_diferencas_periodo(pdf, df):
    fig, axes = plt.subplots(2, 1, figsize=(16, 10))
    fig.suptitle('Diferenças no Período', fontsize=18, fontweight='bold', y=0.98)

    # Diferença Bps por data (todos os fundos empilhados)
    ax1 = axes[0]
    ax1.set_title('Diferença Bps por Data', fontsize=13, fontweight='bold', loc='left')
    for fundo in sorted(df['fundo'].unique()):
        sub = df[df['fundo'] == fundo].sort_values('data')
        ax1.plot(pd.to_datetime(sub['data']), sub['Diferenca_Bps'], marker='o', markersize=4, label=fundo, linewidth=1.2)
    ax1.axhline(0, color='black', linewidth=0.8, linestyle='--')
    ax1.set_ylabel('Diferença (Bps)')
    ax1.legend(fontsize=7, ncol=3, loc='upper left', framealpha=0.8)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax1.grid(True, alpha=0.3)

    # Diferença Financeira por data
    ax2 = axes[1]
    ax2.set_title('Diferença Financeira (R$) por Data', fontsize=13, fontweight='bold', loc='left')
    for fundo in sorted(df['fundo'].unique()):
        sub = df[df['fundo'] == fundo].sort_values('data')
        ax2.plot(pd.to_datetime(sub['data']), sub['Diferenca_Fin'], marker='s', markersize=4, label=fundo, linewidth=1.2)
    ax2.axhline(0, color='black', linewidth=0.8, linestyle='--')
    ax2.set_ylabel('Diferença (R$)')
    ax2.legend(fontsize=7, ncol=3, loc='upper left', framealpha=0.8)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax2.grid(True, alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    pdf.savefig(fig)
    plt.close(fig)


# ==============================
# PÁGINAS POR FUNDO
# ==============================
def pagina_fundo(pdf, fundo, df_periodo, df_hist):
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle(f'Fundo: {fundo}', fontsize=18, fontweight='bold', y=0.98)

    df_hist = df_hist.copy()
    df_hist['date'] = pd.to_datetime(df_hist['date'])
    df_hist = df_hist.sort_values('date')

    # --- 1. Cota do Fundo vs Benchmark ---
    ax1 = axes[0, 0]
    ax1.set_title('Cota Fundo vs Benchmark', fontsize=11, fontweight='bold')

    if 'cota_com_dividendo' in df_hist.columns and df_hist['cota_com_dividendo'].notna().any():
        cota_col = 'cota_com_dividendo'
    else:
        cota_col = 'cota'

    ax1.plot(df_hist['date'], df_hist[cota_col], label='Fundo', color=COLORS['fundo'], linewidth=1.2)
    if 'cota_benchmark' in df_hist.columns and df_hist['cota_benchmark'].notna().any():
        ax1.plot(df_hist['date'], df_hist['cota_benchmark'], label='Benchmark', color=COLORS['benchmark'], linewidth=1.2, linestyle='--')
    ax1.legend(fontsize=8)
    ax1.set_ylabel('Cota')
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%y'))
    ax1.grid(True, alpha=0.3)

    # --- 2. Patrimônio ---
    ax2 = axes[0, 1]
    ax2.set_title('Patrimônio (R$)', fontsize=11, fontweight='bold')

    pl_col = 'patrimonio_brl' if 'patrimonio_brl' in df_hist.columns and df_hist['patrimonio_brl'].notna().any() else 'patrimonio'
    ax2.fill_between(df_hist['date'], df_hist[pl_col], alpha=0.3, color=COLORS['patrimonio'])
    ax2.plot(df_hist['date'], df_hist[pl_col], color=COLORS['patrimonio'], linewidth=1)
    pl_max = df_hist[pl_col].max()
    if pl_max >= 1e9:
        ax2.set_ylabel('R$ (Bi)')
        ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x/1e9:.2f}'))
    elif pl_max >= 1e6:
        ax2.set_ylabel('R$ (Mi)')
        ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x/1e6:.2f}'))
    else:
        ax2.set_ylabel('R$')
        ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m/%y'))
    ax2.grid(True, alpha=0.3)

    # --- 3. PnL Fundo vs Benchmark (Bps diários) ---
    ax3 = axes[1, 0]
    ax3.set_title('PnL Diário: Fundo vs Benchmark (Bps)', fontsize=11, fontweight='bold')

    ultimos = df_hist.tail(60)
    if 'fundo_pnl_perc' in ultimos.columns and ultimos['fundo_pnl_perc'].notna().any():
        ax3.bar(ultimos['date'] - pd.Timedelta(hours=6), ultimos['fundo_pnl_perc'] * 10000,
                width=0.4, label='Fundo', color=COLORS['fundo'], alpha=0.7)
    if 'benchmark_pnl_perc' in ultimos.columns and ultimos['benchmark_pnl_perc'].notna().any():
        ax3.bar(ultimos['date'] + pd.Timedelta(hours=6), ultimos['benchmark_pnl_perc'] * 10000,
                width=0.4, label='Benchmark', color=COLORS['benchmark'], alpha=0.7)
    ax3.axhline(0, color='black', linewidth=0.5)
    ax3.legend(fontsize=8)
    ax3.set_ylabel('Bps')
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax3.grid(True, alpha=0.3)

    # --- 4. Diferença Bps no período selecionado ---
    ax4 = axes[1, 1]
    ax4.set_title('Diferença Bps (Período)', fontsize=11, fontweight='bold')

    df_per = df_periodo[df_periodo['fundo'] == fundo].sort_values('data')
    if not df_per.empty:
        datas = pd.to_datetime(df_per['data'])
        vals = df_per['Diferenca_Bps'].values
        cores = [COLORS['barra_pos'] if v >= 0 else COLORS['barra_neg'] for v in vals]
        ax4.bar(datas, vals, color=cores, edgecolor='gray', linewidth=0.5, width=0.6)
        ax4.axhline(0, color='black', linewidth=0.5)

        for d, v in zip(datas, vals):
            ax4.text(d, v, f'{v:.1f}', ha='center', va='bottom' if v >= 0 else 'top', fontsize=7)
    else:
        ax4.text(0.5, 0.5, 'Sem dados no período', ha='center', va='center', transform=ax4.transAxes)

    ax4.set_ylabel('Bps')
    ax4.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax4.grid(True, alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    pdf.savefig(fig)
    plt.close(fig)


# ==============================
# PÁGINA RESUMO ESTATÍSTICO
# ==============================
def pagina_stats_fundo(pdf, fundo, df_hist):
    fig, ax = plt.subplots(figsize=(16, 10))
    fig.suptitle(f'Estatísticas: {fundo}', fontsize=18, fontweight='bold', y=0.98)
    ax.axis('off')

    df_hist = df_hist.copy()
    df_hist['date'] = pd.to_datetime(df_hist['date'])

    stats = {}
    stats['Primeiro Registro'] = df_hist['date'].min().strftime('%d/%m/%Y')
    stats['Último Registro'] = df_hist['date'].max().strftime('%d/%m/%Y')
    stats['Total de Dias'] = len(df_hist)

    if 'patrimonio_brl' in df_hist.columns and df_hist['patrimonio_brl'].notna().any():
        pl_col = 'patrimonio_brl'
    else:
        pl_col = 'patrimonio'
    stats['Patrimônio Atual (R$)'] = f"{df_hist[pl_col].iloc[-1]:,.2f}" if df_hist[pl_col].notna().any() else 'N/A'

    if 'cota' in df_hist.columns and df_hist['cota'].notna().any():
        stats['Cota Atual'] = f"{df_hist['cota'].iloc[-1]:.8f}"
        cota_ini = df_hist['cota'].dropna().iloc[0]
        cota_fim = df_hist['cota'].dropna().iloc[-1]
        retorno = (cota_fim / cota_ini - 1) * 100
        stats['Retorno Acumulado (%)'] = f"{retorno:.4f}%"

    if 'benchmark' in df_hist.columns:
        stats['Benchmark'] = str(df_hist['benchmark'].dropna().iloc[-1]) if df_hist['benchmark'].notna().any() else 'N/A'

    if 'fundo_pnl_perc' in df_hist.columns and df_hist['fundo_pnl_perc'].notna().any():
        stats['PnL Diário Médio (Bps)'] = f"{df_hist['fundo_pnl_perc'].mean() * 10000:.2f}"
        stats['PnL Diário Máx (Bps)'] = f"{df_hist['fundo_pnl_perc'].max() * 10000:.2f}"
        stats['PnL Diário Mín (Bps)'] = f"{df_hist['fundo_pnl_perc'].min() * 10000:.2f}"
        stats['Volatilidade Diária (Bps)'] = f"{df_hist['fundo_pnl_perc'].std() * 10000:.2f}"

    if 'mesa_gestao' in df_hist.columns:
        stats['Mesa Gestão'] = str(df_hist['mesa_gestao'].dropna().iloc[-1]) if df_hist['mesa_gestao'].notna().any() else 'N/A'
    if 'calculo_cota' in df_hist.columns:
        stats['Cálculo Cota'] = str(df_hist['calculo_cota'].dropna().iloc[-1]) if df_hist['calculo_cota'].notna().any() else 'N/A'

    col_labels = ['Indicador', 'Valor']
    cell_data = [[k, v] for k, v in stats.items()]

    table = ax.table(
        cellText=cell_data,
        colLabels=col_labels,
        loc='center',
        cellLoc='left',
        colWidths=[0.4, 0.4],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 2)
    for (r, c), cell in table.get_celld().items():
        if r == 0:
            cell.set_facecolor('#4472C4')
            cell.set_text_props(color='white', fontweight='bold')
        else:
            cell.set_facecolor('#f0f4fa' if r % 2 == 0 else 'white')

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    pdf.savefig(fig)
    plt.close(fig)


# ==============================
# GERAR REPORT PDF
# ==============================
def gerar_report(data_ini, data_fim):
    print(f"📅 Buscando indexados: {data_ini} -> {data_fim}")
    
    # Carrega lista de fundos
    fundos_lista = carregar_fundos_lista()
    
    df = buscar_indexados(data_ini, data_fim)

    if df.empty:
        print("❌ Nenhum dado encontrado.")
        return
    
    # Filtra apenas os fundos da lista
    if fundos_lista:
        df_original = df.copy()
        df = df[df['fundo'].isin(fundos_lista)]
        if df.empty:
            print(f"❌ Nenhum dos {len(fundos_lista)} fundos da lista encontrado nos dados.")
            return
        print(f"📊 Dados filtrados: {len(df_original)} registros → {len(df)} registros")

    data_str = pd.to_datetime(df['data'].max()).strftime('%Y%m%d')
    pasta_data = OUTPUT_DIR / data_str
    pasta_data.mkdir(parents=True, exist_ok=True)

    caminho_pdf = pasta_data / f"indexados_report_{data_str}.pdf"
    fundos = sorted(df['fundo'].unique())

    print(f"📊 Gerando report para {len(fundos)} fundos...")

    with PdfPages(str(caminho_pdf)) as pdf:

        # Página 1: Resumo
        print("📄 Página: Resumo Geral")
        pagina_resumo(pdf, df)

        # Página 2: Diferenças no período
        print("📄 Página: Diferenças no Período")
        pagina_diferencas_periodo(pdf, df)

        # Páginas por fundo
        for fundo in fundos:
            print(f"📄 Fundo: {fundo}")

            df_hist = buscar_historico_fundo(fundo)

            if df_hist is None or df_hist.empty:
                print(f"  ⚠️ Sem histórico: {fundo}")
                continue

            pagina_fundo(pdf, fundo, df, df_hist)
            pagina_stats_fundo(pdf, fundo, df_hist)

    print(f"✅ Report salvo: {caminho_pdf}")


# ==============================
# MAIN
# ==============================
def main():
    data_ini = "2026-05-01"
    data_fim = "2026-05-08"

    gerar_report(data_ini, data_fim)
    print("\n✅ Report finalizado")


if __name__ == "__main__":
    main()
