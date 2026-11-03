# ─────────────────────────────────────────────
# batimento/relatorio.py
# Excel do batimento: Resumo, Ocorrências, Triagem, Preços, Avisos e Leia-me.
# ─────────────────────────────────────────────

import os
from datetime import datetime

import pandas as pd

from detectores import VERIFICACOES, num_br

# (coluna, título, formato): data, txt, rs (R$), bps, num, pct, longo (texto com quebra)
ABAS = {
    "Resumo": [
        ("date", "Data", "data"), ("codigo_IAM_fundo", "Fundo", "txt"), ("mesa_gestao", "Mesa", "txt"),
        ("cota_bps", "Cota (bps)", "bps"), ("posicao_bps", "Posição (bps)", "bps"),
        ("dif_bps", "Diferença (bps)", "bps"), ("dif_rs", "Diferença (R$)", "rs"),
        ("recorrencia", "Recorrência", "txt"), ("diagnostico", "Diagnóstico", "txt"), ("status", "Status", "txt"),
        ("ativo", "Ativo", "txt"), ("ajuste_rs", "Ajuste sugerido (R$)", "rs"), ("residuo_rs", "Resíduo (R$)", "rs"),
        ("detalhe", "Detalhe", "longo"), ("outras", "Outras verificações", "txt"), ("acao", "Ação", "longo")],
    "Ocorrências": [
        ("data", "Data", "data"), ("fundo", "Fundo", "txt"), ("titulo", "Verificação", "txt"),
        ("status", "Status", "txt"), ("ativo", "Ativo", "txt"), ("ajuste_rs", "Ajuste sugerido (R$)", "rs"),
        ("residuo_rs", "Resíduo (R$)", "rs"), ("detalhe", "Detalhe", "longo"), ("acao", "Ação", "longo"),
        ("verificacao", "Código", "txt")],
    "Triagem": [
        ("date", "Data", "data"), ("codigo_IAM_fundo", "Fundo", "txt"), ("mesa_gestao", "Mesa", "txt"),
        ("classe", "Classe", "txt"), ("classes", "Classes", "num0"), ("pl", "PL (R$)", "rs"),
        ("cota_rs", "Cota (R$)", "rs"), ("cota_bps", "Cota (bps)", "bps"), ("posicao_rs", "Posição (R$)", "rs"),
        ("posicao_bps", "Posição (bps)", "bps"), ("dif_rs", "Diferença (R$)", "rs"),
        ("dif_bps", "Diferença (bps)", "bps"), ("pnl_outras_despesas", "OUTRAS_DESPESAS (R$)", "rs"),
        ("pnl_ajuste_manual", "Ajuste manual (R$)", "rs"), ("linhas", "Linhas", "num0"),
        ("situacao", "Situação", "txt"), ("recorrencia", "Recorrência", "txt"),
        ("data_anterior", "Posição anterior", "data")],
    "Preços": [
        ("data", "Data", "data"), ("ativo", "Ativo", "txt"), ("titulo", "Verificação", "txt"),
        ("preco_anterior", "Preço anterior", "num"), ("preco", "Preço", "num"), ("variacao", "Variação", "pct"),
        ("script", "Script", "txt"), ("gravado_em", "Gravado em", "datahora"), ("usuario", "Usuário", "txt"),
        ("fundos", "Fundos", "txt"), ("exposicao_rs", "Exposição (R$)", "rs"), ("detalhe", "Detalhe", "longo")],
    "Correções": [
        ("bloco", "Bloco no SQL", "num0"), ("data", "Data", "data"), ("fundo", "Fundo", "txt"),
        ("ativo", "Ativo", "txt"), ("linha", "Linha (tipo / contraparte)", "txt"), ("registro", "Registro", "txt"),
        ("diagnostico", "Diagnóstico", "txt"), ("nivel", "Nível", "txt"), ("situacao", "Situação", "txt"),
        ("no_script", "No script", "txt"), ("motivo", "Por que ficou fora", "longo"),
        ("dif_antes", "Diferença antes (R$)", "rs"), ("ajuste", "Ajuste no PnL (R$)", "rs"),
        ("dif_esperada", "Diferença esperada depois (R$)", "rs"), ("dif_depois", "Diferença depois (R$)", "rs"),
        ("conferencia", "Conferência", "txt"), ("pnl_antes", "PnL do registro antes (R$)", "rs"),
        ("componente", "Componente também ajustado", "txt"), ("filtro", "Registro separado por", "txt"),
        ("nota", "Nota", "longo"), ("como", "Como corrigir na origem", "longo")],
}
FORMATOS = {"rs": "#,##0.00", "bps": "0.00", "num": "#,##0.000000", "num0": "0", "pct": "0.00%",
            "data": "dd/mm/yyyy", "datahora": "dd/mm/yyyy hh:mm"}
LARGURA = {"longo": 80, "data": 11, "datahora": 16, "rs": 18, "bps": 11, "num": 14, "num0": 8, "pct": 10}


def _grava_aba(xw, nome, df, colunas):
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    df = df if df is not None else pd.DataFrame()
    saida = pd.DataFrame({titulo: (df[col] if col in df.columns else pd.Series(dtype=object))
                          for col, titulo, _ in colunas})
    for col, titulo, fmt in colunas:
        if fmt in ("data", "datahora"):
            saida[titulo] = pd.to_datetime(saida[titulo], errors="coerce")
    saida.to_excel(xw, sheet_name=nome, index=False)
    ws = xw.sheets[nome]
    cab = PatternFill("solid", fgColor="1F3864")
    for j, (col, titulo, fmt) in enumerate(colunas, start=1):
        c = ws.cell(row=1, column=j)
        c.font, c.fill = Font(bold=True, color="FFFFFF"), cab
        c.alignment = Alignment(vertical="center", wrap_text=True)
        letra = get_column_letter(j)
        if fmt == "txt":
            largura = max([len(str(titulo))] + [len(str(v)) for v in saida[titulo].head(500) if pd.notna(v)])
            ws.column_dimensions[letra].width = min(max(largura + 2, 8), 45)
        else:
            ws.column_dimensions[letra].width = max(LARGURA[fmt], len(titulo) + 2)
        for i in range(2, len(saida) + 2):
            cel = ws.cell(row=i, column=j)
            if fmt in FORMATOS:
                cel.number_format = FORMATOS[fmt]
            if fmt == "longo":
                cel.alignment = Alignment(wrap_text=True, vertical="top")
            else:
                cel.alignment = Alignment(vertical="top")
    ws.freeze_panes = "C2"
    if len(saida):
        ws.auto_filter.ref = ws.dimensions


def _leia_me(xw, resultado):
    from openpyxl.styles import Alignment, Font

    p = resultado.prm
    linhas = [
        ("Batimento cota × posição", ""),
        ("Gerado em", datetime.now().strftime("%d/%m/%Y %H:%M")),
        ("Datas", ", ".join(d.strftime("%d/%m/%Y") for d in resultado.datas)),
        ("Escopo", resultado.escopo),
        ("", ""),
        ("Como ler", "Resumo: um fundo por linha, com a causa mais provável. Ocorrências: tudo o que cada verificação "
                     "encontrou. Triagem: cota × posição de todos os fundos que entraram. Preços: linhas suspeitas da "
                     "FUNDOS_DADOS_ATIVOS para ativos em carteira. Correções (com --corrigir): o que o script de "
                     "correção muda em cada fundo; o número do bloco é o do arquivo correcao_*.sql."),
        ("Sinais", "Diferença = PnL da cota − PnL da posição. Ajuste sugerido = quanto somar ao PnL da posição para "
                   "desfazer a causa. Resíduo = o que sobra da diferença depois desse ajuste."),
        ("Status", "explica / confirmado: a causa fecha a diferença. parcial: explica só uma parte. corrigido: já tem "
                   "ajuste manual. não confirmado: a diferença do fundo não bate com a causa. candidato: sem cota "
                   "para confirmar. alerta: deve acontecer na próxima posição."),
        ("", ""),
        ("Parâmetros", f"diferença a partir de {num_br(p.limiar_bps)} bps e {num_br(p.limiar_rs)} reais (as duas); "
                       f"linha relevante a partir de {num_br(p.limiar_rs)} reais ou {num_br(p.limiar_linha_bps)} bps "
                       f"do PL; uma causa explica se o resíduo fica em até {num_br(p.tol_explica * 100, 0)}% da "
                       f"diferença ou {num_br(p.tol_minima_rs)} reais; fluxo aceito entre "
                       f"{num_br(p.faixa_preco[0])}× e {num_br(p.faixa_preco[1])}× o valor de mercado; salto de preço "
                       f"acima de {num_br(p.salto_preco * 100, 0)}%; PnL de preço nos tipos "
                       f"{', '.join(p.tipos_pnl_preco)}; scripts de alerta: {', '.join(p.scripts_alerta)}; "
                       f"contrapartida em espécie pelo padrão em {', '.join(p.linhas_especie)} (resíduo até "
                       f"{num_br(p.tol_padrao * 100, 1)}% da diferença); recorrência nas {p.janela} datas anteriores."),
        ("Fontes", "VW_FUNDOS_COTAS_PL, VW_FUNDOS_POSICAO, FUNDOS_DADOS_ATIVOS (DBSX337, leituras WITH (NOLOCK))."),
        ("", ""),
        ("Verificação", "O que procura"),
    ] + [(titulo, texto) for titulo, texto in VERIFICACOES.values()]
    pd.DataFrame(linhas, columns=["Item", "Descrição"]).to_excel(xw, sheet_name="Leia-me", index=False, header=False)
    ws = xw.sheets["Leia-me"]
    ws.column_dimensions["A"].width = 46
    ws.column_dimensions["B"].width = 120
    for row in ws.iter_rows():
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    for i, (a, _) in enumerate(linhas, start=1):
        if a in ("Batimento cota × posição", "Verificação"):
            ws.cell(row=i, column=1).font = Font(bold=True, size=12 if i == 1 else 11)
            ws.cell(row=i, column=2).font = Font(bold=True)


def grava_excel(resultado, pasta, nome):
    """Grava o relatório e devolve o caminho (com hora no nome se o arquivo estiver aberto)."""
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, nome)
    try:
        return _grava(resultado, caminho)
    except PermissionError:
        raiz, ext = os.path.splitext(caminho)
        return _grava(resultado, f"{raiz}_{datetime.now():%H%M%S}{ext}")


def _grava(resultado, caminho):
    with pd.ExcelWriter(caminho, engine="openpyxl") as xw:
        _grava_aba(xw, "Resumo", resultado.resumo, ABAS["Resumo"])
        _grava_aba(xw, "Ocorrências", resultado.ocorrencias, ABAS["Ocorrências"])
        _grava_aba(xw, "Triagem", resultado.triagem[resultado.triagem["marcado"]]
                   if len(resultado.triagem) else resultado.triagem, ABAS["Triagem"])
        _grava_aba(xw, "Preços", resultado.precos, ABAS["Preços"])
        if getattr(resultado, "correcoes", None) is not None and len(resultado.correcoes):
            _grava_aba(xw, "Correções", resultado.correcoes, ABAS["Correções"])
        if resultado.avisos:
            pd.DataFrame({"Aviso": resultado.avisos}).to_excel(xw, sheet_name="Avisos", index=False)
            xw.sheets["Avisos"].column_dimensions["A"].width = 160
        _leia_me(xw, resultado)
    return caminho
