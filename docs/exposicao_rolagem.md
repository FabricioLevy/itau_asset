# exposicao_html.py — Rolagem de Futuros e Beta

**Arquivo:** `src/exposicao_html.py`

---

## Rolagem de Futuros — `buscar_rolagem(dt, fundos)`

Analisa a distribuição de posição entre o vencimento atual (v1) e o próximo (v2).

### Fonte de dados

- View: `view_vcrapfut`
- `Notional = ISNULL(qt,0) × ISNULL(vl_varponto,0) × ISNULL(vl_precomerc,0)`

### Agrupamento por família de contrato

| Grupo | Ativos | Ciclo (meses) |
|---|---|---|
| `DOL_WDO` | `DOL`, `WDO` | 1 |
| `WIN` | `WIN` | 2 |
| `WEU` | `WEU` | 2 |
| `ISP` / `WSP` | `ISP`, `WSP` | 3 |
| Outros | conforme banco | 3 (default) |

**Exclusões por padrão:** `DI1`, `DAP` (configurável via `GRUPOS_ROLAGEM_EXCLUIR`)

### Cálculo das métricas

```
Pos v1 % PL  = Notional_v1 / PL
Pos v2 % PL  = Notional_v2 / PL
v1 % FUT     = |Notional_v1| / (|Notional_v1| + |Notional_v2|)
v2 % FUT     = |Notional_v2| / (|Notional_v1| + |Notional_v2|)
```

O denominador usa soma dos **absolutos** (posição comprada + vendida).

### Configurações

```python
GRUPOS_ROLAGEM: Optional[List[str]] = None   # None = todos
GRUPOS_ROLAGEM_EXCLUIR = ["DI1", "DAP"]
ROLAGEM_MESES_ADICIONAIS: int = 0            # 0 = só mês atual como v1
```

---

## Relatório Beta — `BETA_ATIVOS` / `BETA_FUNDS`

Monitora a exposição dos fundos INTRA (Conservador, Moderado, Agressivo) em relação a targets dinâmicos ajustados por drift de preço desde uma data-base.

### Fundos monitorados (`BETA_FUNDS`)

| Código | Perfil |
|---|---|
| `INTRAGITAU362` | Conservador |
| `INTRAGITAU363` | Moderado |
| `INTRAGITAU364` | Agressivo |

### Ativos monitorados (`BETA_ATIVOS`)

Mapeamento `FICAD_CD → (ticker, w_cons, w_mod, w_agr, nav_base)`

| Ticker | FICAD_CD |
|---|---|
| IB5M11 | ITAUIMAB64215 |
| BOVV11 | ITAUIBOV62154 |
| IRFM11 | ITAUIRFMP24216 |
| SPXI11 | ITAUTRN61201 |
| B5P211 | ITAUIMA5P2070 |
| BITI11 | ITAUBLO66606 |
| CDI (residual) | FIDELILCMM771 |

Data-base: `2025-04-30` | PL de referência: `R$ 100.000.000`

### Cálculo de target com drift (`calcular_targets_beta`)

```
unidades = (peso × PL_base) / nav_base
valor_d1 = unidades × nav_d1
target_% = valor_d1 / SUM(todos os valores_d1)
```

CDI = residual: `max(0, 1 − soma_demais_exposições)`

### Limiar de alerta (`BETA_DIF_THRESHOLD`)

```python
BETA_DIF_THRESHOLD = 0.0015   # ±0.15%
# verde: dentro; amarelo: próximo; vermelho: fora
```

---

## Links relacionados

- [[exposicao_html]] — visão geral
- [[exposicao_dados]] — consultas SQL usadas na rolagem
- [[exposicao_outputs]] — como a rolagem aparece no HTML e PDF
