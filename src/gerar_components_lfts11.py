"""
Gera arquivo de componentes do LFTS11 análogo a components-download-file/1.3.4 Teva Tesouro 5 Pre.csv
Fontes:
  - teva-itau-public: preços exatos dos LFT com vencimentos 2031-2032
  - teva-downloads: composição da carteira LFTS11 (ISINs + pesos no rebalanceamento)
  - teva-indices-public: pesos teóricos de abertura (D)
  - teva_<data>.csv: cotações históricas do índice (D-1 e D-2)
"""

import os, re, urllib.request, urllib.parse, json
from datetime import datetime, date
from io import StringIO

import pandas as pd
import numpy as np

# ── helpers ─────────────────────────────────────────────────────────────────

def gcs_csv(bucket, path):
    url = f"https://storage.googleapis.com/{bucket}/{urllib.parse.quote(path)}"
    return pd.read_csv(StringIO(urllib.request.urlopen(url).read().decode("utf-8-sig")))

def gcs_xlsx(url):
    import openpyxl, tempfile, urllib.request
    tmp = tempfile.mktemp(suffix=".xlsx")
    urllib.request.urlretrieve(url, tmp)
    wb = openpyxl.load_workbook(tmp)
    ws = wb.active
    rows = list(ws.rows)
    headers = [c.value for c in rows[0]]
    data = [[c.value for c in row] for row in rows[1:] if any(c.value for c in row)]
    return pd.DataFrame(data, columns=headers)

# ── 1. Composição da carteira LFTS11 ────────────────────────────────────────

portfolio = gcs_xlsx(
    "https://storage.googleapis.com/teva-downloads/rebalanced_portfolios/"
    "carteira-indice-teva-tesouro-selic.xlsx"
)
portfolio.columns = ["DataRebal", "ISIN", "Vencimento", "Emissor", "PesoRebal"]
portfolio = portfolio.dropna(subset=["ISIN"]).copy()
portfolio["Vencimento"] = pd.to_datetime(portfolio["Vencimento"]).dt.strftime("%Y-%m-%d")

# ISIN → vencimento map
isin_to_venc = dict(zip(portfolio["ISIN"], portfolio["Vencimento"]))
venc_to_isin = dict(zip(portfolio["Vencimento"], portfolio["ISIN"]))

# ── 2. Preços de LFT de ficheiros teva-itau-public ──────────────────────────

lft_ntnb = gcs_csv("teva-itau-public", "components-download-file/1.4.5 Teva LFT NTNB 800.csv")
lft_curto = gcs_csv("teva-itau-public", "components-download-file/1.1.6 Teva LFT Curto.csv")

cols_preco = [
    "Ativo", "Preço de Fechamento (D-1)", "Preço Teórico de Abertura (D)",
    "Sigla", "Data de emissão", "Taxa de emissão", "Data de vencimento",
    "Prazo até o vencimento (dias)", "Yield to maturity", "Duration (anos)", "Taxa"
]
lft_ref = pd.concat([
    lft_ntnb[lft_ntnb["Sigla"] == "LFT"][cols_preco],
    lft_curto[lft_curto["Sigla"] == "LFT"][cols_preco],
], ignore_index=True)

# Normaliza a data de vencimento para "YYYY-MM-DD" e converte numéricos
lft_ref["Data de vencimento"] = pd.to_datetime(lft_ref["Data de vencimento"]).dt.strftime("%Y-%m-%d")
for c in ["Preço de Fechamento (D-1)", "Preço Teórico de Abertura (D)",
          "Yield to maturity", "Duration (anos)", "Taxa",
          "Prazo até o vencimento (dias)"]:
    lft_ref[c] = pd.to_numeric(lft_ref[c], errors="coerce")

# Mapa vencimento → dados de preço (match exato de ISIN ou de vencimento)
venc_to_price_row = {row["Data de vencimento"]: row for _, row in lft_ref.iterrows()}
isin_to_price_row = {row["Ativo"]: row for _, row in lft_ref.iterrows()}

# ── 3. Pesos teóricos (Peso na Carteira de Abertura D) ─────────────────────

metrics_url = (
    "https://storage.googleapis.com/teva-indices-public/"
    + urllib.parse.quote("metrics/Ativos com maior relevância/1.1.4B4 Índice Teva Tesouro Selic v0.92.csv")
)
met = pd.read_csv(StringIO(urllib.request.urlopen(metrics_url).read().decode("utf-8-sig")))
met.columns = met.columns.str.strip()
met["Data de referência"] = pd.to_datetime(met["Data de referência"]).dt.strftime("%Y-%m-%d")
met["Data de vencimento"] = pd.to_datetime(met["Data de vencimento"]).dt.strftime("%Y-%m-%d")

# Pega o dia mais recente disponível
latest_date = met["Data de referência"].max()
met_today = met[met["Data de referência"] == latest_date].copy()

# Mapa vencimento → peso teórico
venc_to_peso_teorico = {}
for _, row in met_today.iterrows():
    venc = row["Data de vencimento"]
    peso_col = [c for c in met.columns if "te" in c.lower() and "rico" in c.lower()]
    if peso_col:
        venc_to_peso_teorico[venc] = float(row[peso_col[0]])

# ── 4. Cotação do índice D-1 e D-2 ──────────────────────────────────────────

csv_files = sorted([f for f in os.listdir(".") if f.startswith("teva_") and f.endswith(".csv")])
if not csv_files:
    raise FileNotFoundError("Arquivo teva_*.csv não encontrado. Execute teva.py primeiro.")
quotes = pd.read_csv(csv_files[-1])
idx_d1 = float(quotes.iloc[-1]["Cotação do Índice Retorno Total"])
idx_d2 = float(quotes.iloc[-2]["Cotação do Índice Retorno Total"])
ref_date = latest_date  # usa a data mais recente dos metrics

# ── 5. Modelo de interpolação de preços (para bonds sem dado exato) ──────────

today_dt = datetime.strptime(ref_date, "%Y-%m-%d").date()
lft_ref["days_calc"] = (
    pd.to_datetime(lft_ref["Data de vencimento"]).dt.date.apply(lambda d: (d - today_dt).days)
)
lft_valid = lft_ref.dropna(subset=["Preço de Fechamento (D-1)", "days_calc"])

# Ajusta polinômio grau 2 a preço vs dias
coef_preco = np.polyfit(lft_valid["days_calc"], lft_valid["Preço de Fechamento (D-1)"], 2)
coef_ytm   = np.polyfit(lft_valid["days_calc"], lft_valid["Yield to maturity"], 1)
coef_taxa  = np.polyfit(lft_valid["days_calc"], lft_valid["Taxa"], 1)

def itp_preco(d): return float(np.polyval(coef_preco, d))
def itp_ytm(d):   return float(np.polyval(coef_ytm, d))
def itp_taxa(d):  return float(np.polyval(coef_taxa, d))

DURATION = 1 / 252  # constante para todos os LFT (floating rate bond)
INDEX_NAME = "1.1.4B4 Índice Teva Tesouro Selic v0.92"

# ── 6. Monta o DataFrame de saída ────────────────────────────────────────────

records = []
for _, bond in portfolio.iterrows():
    isin = bond["ISIN"]
    venc = bond["Vencimento"]
    venc_dt = datetime.strptime(venc, "%Y-%m-%d").date()
    days = (venc_dt - today_dt).days
    peso_rebal = float(bond["PesoRebal"])
    peso_teorico = venc_to_peso_teorico.get(venc, peso_rebal)  # fallback para rebal

    # Procura preço exato por ISIN, depois por vencimento, senão interpola
    if isin in isin_to_price_row:
        pr = isin_to_price_row[isin]
        preco_d1   = float(pr["Preço de Fechamento (D-1)"])
        preco_d    = float(pr["Preço Teórico de Abertura (D)"])
        em_date    = pr["Data de emissão"]
        em_rate    = pr["Taxa de emissão"]
        ytm        = float(pr["Yield to maturity"])
        taxa       = float(pr["Taxa"])
    elif venc in venc_to_price_row:
        pr = venc_to_price_row[venc]
        preco_d1   = float(pr["Preço de Fechamento (D-1)"])
        preco_d    = float(pr["Preço Teórico de Abertura (D)"])
        em_date    = pr["Data de emissão"]
        em_rate    = pr["Taxa de emissão"]
        ytm        = float(pr["Yield to maturity"])
        taxa       = float(pr["Taxa"])
    else:
        preco_d1   = itp_preco(days)
        preco_d    = preco_d1
        em_date    = ""
        em_rate    = ""
        ytm        = itp_ytm(days)
        taxa       = itp_taxa(days)

    records.append({
        "Ativo":                            isin,
        "Preço de Fechamento (D-1)":        preco_d1,
        "Preço Teórico de Abertura (D)":    preco_d,
        "Peso na Carteira de Abertura (D)": peso_teorico,
        "Proventos Ex (D)":                 0.0,
        "Cotação do Índice (D-1)":          idx_d1,
        "Cotação do Índice (D-2)":          idx_d2,
        "Data de referência":               ref_date,
        "Sigla":                            "LFT",
        "Data de emissão":                  em_date,
        "Taxa de emissão":                  em_rate,
        "Data de vencimento":               venc,
        "Prazo até o vencimento (dias)":    float(days),
        "Yield to maturity":                ytm,
        "Duration (anos)":                  DURATION,
        "Índice":                           INDEX_NAME,
        "Taxa":                             taxa,
    })

# Linha Caixa
records.append({
    "Ativo":                            "Caixa",
    "Preço de Fechamento (D-1)":        0.0,
    "Preço Teórico de Abertura (D)":    0.0,
    "Peso na Carteira de Abertura (D)": "0E-15",
    "Proventos Ex (D)":                 0.0,
    "Cotação do Índice (D-1)":          idx_d1,
    "Cotação do Índice (D-2)":          idx_d2,
    "Data de referência":               ref_date,
    "Sigla":                            "",
    "Data de emissão":                  "",
    "Taxa de emissão":                  "",
    "Data de vencimento":               "",
    "Prazo até o vencimento (dias)":    "",
    "Yield to maturity":                "",
    "Duration (anos)":                  "",
    "Índice":                           INDEX_NAME,
    "Taxa":                             "",
})

df = pd.DataFrame(records)

out = f"components_lfts11_{ref_date.replace('-','')}.csv"
df.to_csv(out, index=False, encoding="utf-8-sig")
print(f"Arquivo salvo: {out}")
print(f"  Data de referência: {ref_date}")
print(f"  Cotação D-1: {idx_d1:.4f} | D-2: {idx_d2:.4f}")
print(f"\n{df[['Ativo','Preço de Fechamento (D-1)','Peso na Carteira de Abertura (D)','Data de vencimento']].to_string()}")
