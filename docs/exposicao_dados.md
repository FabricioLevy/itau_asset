# exposicao_html.py — Consultas SQL (Dados)

**Arquivo:** `src/exposicao_html.py`
Banco: `dbsx337.dbo` (SQL Server)

---

## FX — `buscar_fx(dt)`

| Moeda | View/Tabela | Campo chave |
|---|---|---|
| USD, GBP, EUR | `fundos_dados_moedas` | `codigo_iam_moeda_base = 'BRL_B3_2'` |
| CNY | `FUNDOS_DADOS_INDICES` | `codigo_iam_indice = 'CNYXBR10'` |

Retorna `Dict[str, float]`: `USD_BRL`, `GBP_BRL`, `EUR_BRL`, `CNYXBR10`.

---

## PL — `buscar_pl(dt, fundos)`

- View: `view_vcraplsi`
- Campo: `vl_patrliqtot1`
- Retorna `Dict[fundo → PL_float]`

---

## PRV (Renda Variável) — `buscar_prv(dt, fundos, fx)`

Três queries separadas para evitar produto cartesiano:

| Query | View | Propósito |
|---|---|---|
| `q_prv` | `VIEW_vcraprv` | Qtd bloqueada + disponível + preço médio |
| `q_moeda` | `VIEW_FUNDOS_POSICAO` | Moeda por ticker (type = 'Equity') |
| `q_btc` | `VIEW_VCRABTC` | Ajuste de aluguel (BTC): Doador +QTD / Tomador −QTD |

**Quantidade líquida:** `NET_QTY = QTDBLOQ + QTDDISP + QTD_BTC`

**Conversão cambial:**

| Moeda detectada | Conversão |
|---|---|
| USD, IX | `× USD_BRL` (IX multiplica valor × 100 antes) |
| GBP | `× GBP_BRL` (preço > 100 divide por 100 antes) |
| CNY, CNY_10H | `÷ CNYXBR10` |
| BRL / sem moeda | sem conversão |

Caso especial: `EMERGFIA54431 / EXCS LN` multiplica `VALOR_LOCAL × 100`.

Retorna `Dict[fundo → PRV_BRL_total]`

---

## Futuros — `buscar_futuro(dt, fundos)`

- View: `view_vcrapfut`
- Notional padrão: `qt × vl_varponto × vl_precomerc`
- **DI1:** Notional = `qt × NETWORKDAYS(dt_ref, dt_vencto)` (dias úteis até vencimento)

Retorna `Dict[fundo → NOTIONAL_total]`

---

## Cotas de Fundos — `buscar_cotas` / `buscar_cotas_total`

- View: `view_vcrapfdo`
- `buscar_cotas`: usa `SUM(vl_total)`
- `buscar_cotas_total`: idem — usado para OFFSHORES (captura posições bloqueadas)

---

## PIBB11 / SPXI11 — `buscar_pibb11_spxi11(dt, fundos)`

- Reúne `VIEW_vcraprv` + `VIEW_VCRABTC` filtrando `acao IN ('PIBB11', 'SPXI11')`
- Retorna `Dict[fundo → {"pibb11": float, "spxi11": float}]`

---

## Futuros S&P / USD — `buscar_fut_sp_usd(dt, fundos)`

| Grupo | Ativos |
|---|---|
| S&P | `FUT ISP`, `FUT WSP` |
| USD | `FUT DOL`, `FUT WDO`, `FUT BRI` |

Retorna `Dict[fundo → {"sp": float, "usd": float}]`

---

## Proventos — `buscar_proventos(dt, fundos)`

- View: `view_vcraprdp`
- Filtra `mttp_cd IN ('61','62','69','261','848','849','971','972','973')`
- Retorna `Dict[fundo → PROVENTOS_total]`

---

## Links relacionados

- [[exposicao_html]] — visão geral
- [[exposicao_calculos]] — como esses dados são usados no cálculo
