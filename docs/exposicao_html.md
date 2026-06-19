# exposicao_html.py — Visão Geral

**Arquivo:** `src/exposicao_html.py`
**Propósito:** Gera o Relatório de Exposição diário dos fundos da Itaú Asset — PNG, Excel, HTML interativo, PDF e índice histórico.

---

## Fluxo principal (`main`)

```
python exposicao_html.py [n_dias]
```

1. Calcula as datas úteis (QuantLib Brasil) retroativas a partir de hoje
2. Lê o Excel de configuração (`../input/fundos_exposicao.xlsx`)
3. Para cada data:
   - Consulta SQL: FX → PL → PRV → Futuros → Cotas → Proventos → PIBB/SPXI → Fut S&P/USD → Rolagem
   - Monta tabelas por aba
   - Exporta: Excel → HTML → PDF → PDF Rolagem → Excel Rolagem
4. Gera o `index.html` com calendário histórico

---

## Diagrama de fluxo

```mermaid
flowchart TD
    A([python exposicao_html.py n_dias]) --> B[QuantLib: calcular datas úteis]
    B --> C[ler_exposicao_excel\nfundos_exposicao.xlsx]
    C --> LOOP

    subgraph LOOP["Loop por data"]
        direction TB

        subgraph SQL["Consultas SQL — dbsx337"]
            direction LR
            FX[buscar_fx\nUSD · GBP · EUR · CNY]
            PL[buscar_pl\nview_vcraplsi]
            PRV[buscar_prv\nVIEW_vcraprv\n+ BTC + moeda]
            FUT[buscar_futuro\nview_vcrapfut\nDI1 = dias úteis]
            COT[buscar_cotas\nview_vcrapfdo]
            PROV[buscar_proventos\nview_vcraprdp]
            PIBB[buscar_pibb11_spxi11]
            FSPUSD[buscar_fut_sp_usd\nISP/WSP vs DOL/WDO]
            ROL[buscar_rolagem\nv1 → v2 por família]
        end

        SQL --> MT

        subgraph MT["montar_tabela — por aba"]
            direction TB
            CALC["%AÇÕES = PRV/PL\n%FUT = Notional/PL\n%COTAS = Cotas/PL\nTOTAL = soma\nDESC = 1−TOTAL"]
            SP500["Aba S&P500\nbuckets: S&P · USD · IBX · PIBB · FANG · ISP"]
            OFF["Aba OFFSHORES\n%AÇÕES=0 · %FUT=0\nCotas via vl_total"]
            BANDA{TOTAL fora\nde banda?}
            CALC --> SP500 & OFF
            CALC --> BANDA
        end

        MT --> OUT

        subgraph OUT["Exportação"]
            direction LR
            HTML[gerar_html\nHTML interativo\nAbas · Alertas · Busca · Sort]
            XLSX[exportar_excel\nopenpyxl\nformatação condicional]
            PDF[gerar_pdf\nfpdf2 A4 paisagem\nbookmarks]
            PNG[gerar_imagem\nmatplotlib PNG\npor aba]
            RPDF[gerar_pdf_rolagem]
            RXLSX[exportar_excel_rolagem]
        end
    end

    LOOP --> IDX[gerar_index\nindex.html\ncalendário histórico]

    style SQL fill:#e8f0fe,stroke:#4a6fa5
    style MT fill:#fff8e1,stroke:#f0a500
    style OUT fill:#e8f5e9,stroke:#2e7d32
    style BANDA fill:#fde8e8,stroke:#c0392b
```

---

## Arquivos de entrada

| Variável | Caminho padrão | Descrição |
|---|---|---|
| `INPUT_EXCEL` | `../input/fundos_exposicao.xlsx` | Configuração de fundos por aba (FUNDO, BENCH, MAX, MIN) |
| `INPUT_FUNDOS_ROL` | `../input/fundos.txt` | Lista de fundos incluídos no relatório de rolagem |
| `LOGO_PATH` | `../input/logo.png` | Logo para cabeçalho nos relatórios |

---

## Abas processadas (`SHEETS`)

```
SINGLES, IBOV, ETFs, S&P500, OFFSHORES, MOEDAS,
RENDA FIXA, OURO e TREASURY, DEBENTURES, ACWI, CDI
```

Cada aba do Excel deve ter colunas: `FUNDO`, `BENCH`, `MAX`, `MIN`.
A leitura é tolerante a variações de capitalização e nomes próximos.

---

## Saídas por data (`../output/relatorios/YYYYMMDD/`)

| Arquivo | Função |
|---|---|
| `exposicao_{aba}_{dt}.png` | Imagem matplotlib por aba |
| `exposicao_{dt}.xlsx` | Excel com formatação condicional |
| `exposicao_{dt}.html` | HTML interativo com abas, busca e alertas |
| `exposicao_{dt}.pdf` | PDF A4 paisagem navegável (fpdf2) |
| `rolagem_{dt}.pdf` | PDF separado de rolagem de futuros |
| `rolagem_{dt}.xlsx` | Excel de rolagem |

Índice histórico: `../output/relatorios/index.html`

---

## Paleta de cores Itaú

```python
ITAU_DARK   = "#000D3C"   # azul escuro — fundo de cabeçalhos
ITAU_ORANGE = "#EC7000"   # laranja — destaques, TOTAL na faixa
ITAU_RED    = "#c0392b"   # vermelho — fora de banda
ITAU_GREEN  = "#1e7e34"   # verde — TOTAL ≥ 99%
ROW_PAR     = "#eaf0fb"   # azul claro — linhas pares
```

---

## Dependências

```python
pandas, numpy, QuantLib, matplotlib, openpyxl, fpdf2
sql_connection  # módulo interno de conexão com dbsx337
```

---

## Links relacionados

- [[exposicao_dados]] — consultas SQL
- [[exposicao_calculos]] — cálculo de exposição
- [[exposicao_outputs]] — geração de relatórios
- [[exposicao_rolagem]] — rolagem e Beta
