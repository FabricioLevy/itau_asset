# Fórmulas — `exposicao.py`

## 1. Notional de Futuros

### 1.1 Contratos gerais (B3)

```
NOTIONAL = qt × vl_varponto × vl_precomerc
```

| Variável | Origem (SQL) | Descrição |
|---|---|---|
| `qt` | `view_vcrapfut.qt` | Quantidade de contratos |
| `vl_varponto` | `view_vcrapfut.vl_varponto` | Valor de cada ponto do contrato (R$) |
| `vl_precomerc` | `view_vcrapfut.vl_precomerc` | Preço de mercado do contrato |

Resultado já em BRL, não requer conversão cambial.

### 1.2 FUT DI1 (caso especial)

```
NOTIONAL = qt × NETWORKDAYS(dt_ref, dt_vencto)
```

O FUT DI1 não usa preço × variação de ponto. O notional é proporcional ao número de dias úteis até o vencimento, replicando a col. BJ do relatório VBA original.

`NETWORKDAYS(dt_ref, dt_vencto)` = `len(pd.bdate_range(dt_ref, dt_vencto))` — conta dias úteis, extremos inclusive.

---

## 2. Posição Acionária — Valor em BRL (PRV_BRL)

### 2.1 Quantidade líquida

```
NET_QTY = QTDBLOQ + QTDDISP + QTD_BTC
```

| Variável | Origem | Descrição |
|---|---|---|
| `QTDBLOQ` | `VIEW_vcraprv.qtdbloq` | Quantidade bloqueada |
| `QTDDISP` | `VIEW_vcraprv.qtddisp` | Quantidade disponível |
| `QTD_BTC` | `VIEW_VCRABTC` | Ajuste de empréstimo (BTC): +sinal se Doador, −sinal se Tomador |

### 2.2 Valor em moeda local

```
VALOR_LOCAL = NET_QTY × PRECO
```

**Exceção** — fundo `EMERGFIA54431`, ativo `EXCS LN`:

```
VALOR_LOCAL = NET_QTY × PRECO × 100
```

### 2.3 Conversão cambial para BRL

A moeda efetiva é determinada pela coluna `moeda_ativo` de `VIEW_FUNDOS_POSICAO`. Quando ausente, é inferida pelo sufixo do ticker (`US` → USD, `LN` → GBP).

| Moeda efetiva | Fórmula BRL |
|---|---|
| `USD` | `VALOR_LOCAL × USD_BRL` |
| `IX` (índice USD) | `VALOR_LOCAL × 100 × USD_BRL` |
| `GBP` | `VALOR_LOCAL × GBP_BRL / 100` |
| `CNY` / `CNY_10H` | `VALOR_LOCAL / CNYXBR10` |
| `BRL` ou sem moeda | `VALOR_LOCAL` (sem conversão) |

> **Taxas FX** — buscadas em `fundos_dados_moedas` (USD, GBP, EUR) e em `FUNDOS_DADOS_INDICES` (CNYXBR10).

---

## 3. Colunas principais do Relatório de Exposição

Calculadas em `montar_tabela()`:

```
%AÇÕES         = PRV_BRL / PL
%FUT           = SUM(NOTIONAL) / PL
%COTAS         = SUM(vl_liq de view_vcrapfdo) / PL
TOTAL          = %AÇÕES + %FUT + %COTAS
DESC           = 1 − TOTAL
Proventos % PL = SUM(proventos) / PL
```

| Variável | Origem | Descrição |
|---|---|---|
| `PRV_BRL` | `buscar_prv()` | Valor BRL das ações (com câmbio) |
| `SUM(NOTIONAL)` | `buscar_futuro()` | Soma dos notionais de futuros |
| `SUM(vl_liq)` | `buscar_cotas()` | Valor líquido das cotas de fundos |
| `SUM(proventos)` | `buscar_proventos()` | Proventos de mttp específicos |
| `PL` | `view_vcraplsi.vl_patrliqtot1` | Patrimônio líquido total |

---

## 4. Colunas especiais — Aba S&P 500

Para a aba `S&P500`, as três colunas originais (`%AÇÕES`, `%FUT`, `%COTAS`) são substituídas pelo seguinte cálculo:

### 4.1 EXPOSIÇÃO S&P

```
EXPOSIÇÃO S&P = (PRV − PIBB11 + FUT_SP) / PL
```

- `PRV` — valor BRL de todas as ações (saída de `buscar_prv()`)
- `PIBB11` — valor BRL da posição em `PIBB11` (sempre hedgeado por FUT BRI, portanto excluído da exposição S&P)
- `FUT_SP` — NOTIONAL de `FUT ISP` + `FUT WSP`

### 4.2 EXPOSIÇÃO USD

```
EXPOSIÇÃO USD = FUT_USD / PL
```

- `FUT_USD` — NOTIONAL de `FUT DOL` + `FUT WDO` + `FUT BRI`

### 4.3 PIBB + SPXI

```
PIBB + SPXI = (PIBB11 + SPXI11) / PL
```

Ambos os valores são o produto `(qtdbloq + qtddisp) × vl_preco_mercmedio` buscado em `VIEW_vcraprv`.

### 4.4 TOTAL e DESC (aba S&P500)

```
TOTAL = EXPOSIÇÃO S&P
DESC  = 1 − EXPOSIÇÃO S&P
```

---

## 5. Coluna especial — Aba OFFSHORES

Fundos como `ITAUBLO66606` (BTC) têm cotas parcialmente bloqueadas; `vl_liq` captura só ~20% do valor real.

```
%COTAS = SUM(vl_total de view_vcrapfdo) / PL   ← usa vl_total, não vl_liq
TOTAL  = %AÇÕES + %FUT + %COTAS
DESC   = 1 − TOTAL
```

---

## 6. Coloração da coluna TOTAL

| Condição | Cor | Significado |
|---|---|---|
| `TOTAL > MAX` ou `TOTAL < MIN` | Vermelho (texto + fundo `#fde8e8`) | Fora da banda permitida |
| `TOTAL ≥ 99%` (dentro da banda) | Verde | Exposição plena |
| `TOTAL < 99%` (dentro da banda) | Laranja | Exposição parcial |

`MAX` e `MIN` são lidos do Excel de configuração (arquivo `fundos_exposicao.xlsx`) por fundo e aba.

---

## 7. Relatório de Rolagem

Calcula a proporção da posição de futuros no **vencimento corrente (v1)** e no **vencimento seguinte (v2)**.

```
Pos v1 % PL = Notional(v1) / PL
Pos v2 % PL = Notional(v2) / PL

v1 % FUT    = Notional(v1) / (Notional(v1) + Notional(v2))
v2 % FUT    = Notional(v2) / (Notional(v1) + Notional(v2))
```

- `Notional(v1)` — soma dos notionais (`qt × vl_varponto × vl_precomerc`) dos contratos com vencimento v1, agrupados por fundo
- O próximo vencimento (v2) é obtido por ordenação cronológica dos vencimentos disponíveis. Se só existir um, v2 é derivado adicionando o ciclo-padrão do contrato (tabela `_VENC_CYCLE`):

| Grupo | Ciclo (meses) |
|---|---|
| DOL / WDO | 1 |
| WIN | 2 |
| WEU | 2 |
| ISP | 3 |
| WSP | 3 |
| outros | 3 |

---

## 8. Exposição Beta (INTRAGITAU)

### 8.1 Target com drift de preço (aba Index)

Replica a planilha *Exposição Beta V20 — aba Index*:

```
unidades  = (peso_raw × BASE_PL) / nav_base
valor_d1  = unidades × nav_d1
target_%  = valor_d1 / SUM(valor_d1 do perfil)
```

| Variável | Descrição |
|---|---|
| `peso_raw` | Peso fixo de referência por ativo e perfil (configurado em `BETA_ATIVOS`) |
| `BASE_PL` | PL de referência para as "quantidades teóricas" (R$ 100.000.000) |
| `nav_base` | Cota do sub-fundo na data-base (`BETA_BASE_DATE = 2025-04-30`) |
| `nav_d1` | Cota do sub-fundo na data de referência (`view_fundos_cotas_pl.cota`) |

O denominador normaliza os targets para que somem 100% dentro de cada perfil (Conservador / Moderado / Agressivo), capturando o **drift de preço** de cada ativo desde a data-base.

### 8.2 Posição real (actual%)

Para cada ativo não-CDI:

```
actual% = SUM(vl_liq de view_vcrapfdo para FICAD_CD) / PL
```

### 8.3 CDI como resíduo

O sub-fundo CDI (`FIDELILCMM771`) captura **todo o caixa remanescente** (LFTs, reserva, resíduos):

```
CDI actual% = max(0,  1 − Σ(actual% de todos os outros ativos))
```

### 8.4 Diferença (DIF)

```
DIF = actual% − target%
```

| Condição | Cor da célula |
|---|---|
| `DIF > +0,15%` | Verde (`#e8f5e9`) |
| `DIF < −0,15%` | Vermelho (`#fde8e8`) |
| `−0,15% ≤ DIF ≤ +0,15%` | Amarelo (`#fffde7`) |

O limiar de ±0,15% é configurável em `BETA_DIF_THRESHOLD`.

---

## 9. Calendário de dias úteis

O script usa **QuantLib Brazil** para calcular dias úteis retroativos:

```python
cal.advance(ql.Date.from_date(date.today()), ql.Period(f'-{i}d'))
```

Retrocede `i` dias úteis brasileiros a partir de hoje para determinar as datas de referência a processar.
