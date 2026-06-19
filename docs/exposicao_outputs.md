# exposicao_html.py — Geração de Relatórios

**Arquivo:** `src/exposicao_html.py`

---

## HTML interativo — `gerar_html(...)`

Arquivo único auto-contido (logo embedada em base64).

### Estrutura de navegação

```
Nav principal:  [EXPOSIÇÃO]  [ROLAGEM]*
Nav secundária: [ALERTA] [SINGLES] [IBOV] [ETFs] ... (abas)
```

*Seção ROLAGEM só aparece se houver dados de rolagem.

### Aba ALERTA

- Lista todos os fundos fora-de-banda de todas as abas
- Agrupado por aba, com contador de fundos
- Botão "Ir para aba →" navega diretamente para a aba correta
- Clique no nome do fundo: navega + destaca a linha em amarelo por 1.4s

### Funcionalidades JS

| Função | Comportamento |
|---|---|
| `sortTable(th)` | Ordenação clicável nas colunas (numérica ou alfabética) |
| `filterTable(input)` | Busca em tempo real por texto em qualquer célula |
| `filterAlerta(input)` | Busca no painel de alertas com ocultação por grupo |
| `goToPane(paneId)` | Navegação programática para aba |
| `goToFund(paneId, name)` | Navega para aba + scroll + highlight da linha do fundo |

### Formatação de células

| Coluna | Formato |
|---|---|
| `PL` | `R$ #,##0.00` |
| `TOTAL`, `%AÇÕES`, etc. | `0.00%` |
| `DESC` (só S&P500) | `0.000%` (3 casas) |
| `FUNDO` | texto, alinhado à esquerda |

---

## Excel — `exportar_excel(...)`

Usa `openpyxl`. Uma aba por categoria de fundo.

- Cabeçalho: fundo azul escuro, texto branco, negrito
- Linhas pares: `ROW_PAR` (#eaf0fb)
- Fora de banda: `#fde8e8` + cor da fonte TOTAL em vermelho
- TOTAL verde/laranja/vermelho conforme regra de coloração
- Freeze na linha 1 (`freeze_panes = "A2"`)
- Largura de coluna auto-ajustada (máx 32)

---

## Imagem PNG — `gerar_imagem(...)`

Usa matplotlib com `GridSpec` de 4 linhas:

```
gs[0] → faixa azul escuro (topo) + linha laranja
gs[1] → título + subtítulo (aba) + data de referência
gs[2] → tabela de dados
gs[3] → rodapé com legenda
```

- `dpi=150`, `bbox_inches="tight"`
- Tamanho dinâmico: `fig_h = 3.0 + n_rows × 0.65 + 0.4`
- Tabela renderizada com `ax.table()`

---

## PDF — `gerar_pdf(...)` e `gerar_pdf_rolagem(...)`

Usa **fpdf2**, orientação A4 paisagem.

- Classe `ExposicaoPDF(FPDF)` com `header()` e `footer()` customizados
- Bookmarks navegáveis por aba (`pdf.start_section(aba)`)
- Cabeçalho repetido em quebras de página automáticas
- Coloração de TOTAL idêntica ao HTML/Excel

---

## Índice histórico — `gerar_index(root_dir)`

Arquivo: `../output/relatorios/index.html`

- **Calendário interativo** (JS puro): navega por mês, dias clicáveis com relatório
- Dias com rolagem: destaque em vermelho; sem rolagem: laranja
- Detecção automática de rolagem: verifica presença de `id="sec-rolagem"` nos HTMLs gerados
- Tabela lateral com histórico de todos os relatórios disponíveis

---

## Links relacionados

- [[exposicao_html]] — visão geral e fluxo
- [[exposicao_calculos]] — dados que alimentam os relatórios
- [[exposicao_rolagem]] — seção de rolagem no HTML
