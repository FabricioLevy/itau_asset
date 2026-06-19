# exposicao_html.py — Cálculos de Exposição

**Arquivo:** `src/exposicao_html.py`

---

## Tabela padrão — `montar_tabela(...)`

Recebe os mapas de dados e calcula as métricas por fundo:

| Coluna | Fórmula |
|---|---|
| `%AÇÕES` | `PRV_BRL / PL` |
| `%FUT` | `Notional_futuros / PL` |
| `%COTAS` | `vl_total_cotas / PL` |
| `TOTAL` | `%AÇÕES + %FUT + %COTAS` |
| `DESC` | `1 − TOTAL` |
| `Proventos % PL` | `Proventos / PL` |

Infinitos (`inf`, `-inf`) são convertidos para `NaN`.
`MAX` e `MIN` são mantidos internamente para coloração mas não exibidos na tabela.

---

## Aba S&P500 — lógica especial

Renomeia colunas e aplica modelo de buckets:

```
prv_val  = PRV_BRL do fundo
sp_fut   = Notional FUT ISP + FUT WSP
usd_fut  = Notional FUT DOL + FUT WDO + FUT BRI
pibb11   = valor de PIBB11
spxi11   = valor de SPXI11
```

| Bucket | Campo de saída | Cálculo |
|---|---|---|
| S&P | `EXPOSIÇÃO S&P` | `(prv − pibb11 + sp_fut) / PL` |
| USD | `EXPOSIÇÃO USD` | `usd_fut / PL` |
| ETFs | `PIBB + SPXI` | `(pibb11 + spxi11) / PL` |
| IBX | `EXPOSIÇÃO IBX` | 0.002 se `SP500MM*`, senão 0 |
| ISP | `ISP` | `sp_fut / PL` (zero se < 1%) |
| FANG | `FANG` | 0.75 se benchmark contém "FANG" (S&P ×0.2506) |

**Regras de ajuste por prefixo de fundo:**
- `SP500*` ou `USDAFIM*` → `EXPOSIÇÃO USD = EXPOSIÇÃO S&P`
- `ITAUMMSP*` ou `ITAUTRN*` → `EXPOSIÇÃO USD = 0` (hedge)

`TOTAL = EXPOSIÇÃO S&P` (apenas S&P entra no TOTAL desta aba)

---

## Aba OFFSHORES — lógica especial

- `%AÇÕES = 0`, `%FUT = 0`
- `%COTAS` = calculado com `buscar_cotas_total` (usa `vl_total`, não `vl_liq`)
- Motivo: fundos offshore frequentemente têm posições bloqueadas que não aparecem em `vl_liq`

---

## Regra de fora-de-banda

```python
fora_banda = (TOTAL > MAX) or (TOTAL < MIN)
# só avalia se MAX != 0 e MIN != 0 e ambos não-nulos
```

**Efeito visual:**
- Fundo da linha: `#fde8e8` (vermelho claro)
- Cor do texto TOTAL: `ITAU_RED` em negrito
- Aparece na aba **ALERTA** do HTML com link de navegação direta

**Cores do TOTAL (quando dentro da banda):**
- Verde (`ITAU_GREEN`): `TOTAL ≥ 99%`
- Laranja (`ITAU_ORANGE`): `TOTAL < 99%`

---

## Links relacionados

- [[exposicao_dados]] — como os dados são coletados
- [[exposicao_outputs]] — como os resultados são renderizados
