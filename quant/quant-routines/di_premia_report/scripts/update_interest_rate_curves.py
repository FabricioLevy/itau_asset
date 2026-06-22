"""
Atualiza [risk].[interest_rate_curve] com as curvas DI Fut e DAP BEI.
Fonte: B3 Ajuste do Pregão (público, sem autenticação)

Curvas geradas:
  - 'DI Fut' : tenores 180, 360, 540, 720, 1800 DU
  - 'DAP BEI': tenores 180, 360, 540, 720 DU

Pré-requisitos no banco:
  - [middle].[product_price]             com SELIC TARGET (proxy CDI curto prazo)
  - [research].[monetary_policy_meeting] com datas COPOM
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import warnings
import requests
import pandas as pd
import datetime
import QuantLib as ql
from types import MethodType
from sql import SQLConnection

# Desabilita warning de certificado SSL da B3
try:
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    warnings.filterwarnings('ignore', category=InsecureRequestWarning)
except Exception:
    pass

B3_URL = "http://www2.bmf.com.br/pages/portal/bmfbovespa/lumis/lum-ajustes-do-pregao-ptBR.asp"

DI_TENORS  = [180, 360, 540, 720, 1800]
DAP_TENORS = [180, 360, 540, 720]


# ─────────────────────────────────────────────────────────────
# Download B3
# ─────────────────────────────────────────────────────────────

def download_b3(dt: datetime.date) -> pd.DataFrame:
    """Baixa a tabela de Ajuste do Pregão da B3 para a data dt."""
    resp = requests.post(B3_URL, data={'dData1': dt.strftime('%d/%m/%Y')},
                         verify=False, timeout=30)
    resp.raise_for_status()

    pos = resp.text.find('Atualizado em')
    if pos != -1:
        try:
            dt_html = datetime.datetime.strptime(resp.text[pos:pos + 25][-10:], '%d/%m/%Y').date()
            if dt != dt_html:
                raise ValueError(f'B3 retornou dados para {dt_html}, esperado {dt}.')
        except ValueError as e:
            if 'retornou dados' in str(e):
                raise
            # Formato de data inesperado no HTML — continua sem validação

    import io
    df = pd.read_html(io.StringIO(resp.text), match='.+', thousands='.', decimal=',')[0]
    df.columns = ['mercadoria', 'vencimento', 'preco_anterior', 'preco_atual', 'variacao', 'ajuste_brl']

    # preenche células de mercadoria mescladas no HTML
    ativo = df.iloc[0]['mercadoria']
    for i, row in df.iterrows():
        if row['mercadoria'] == '':
            df.at[i, 'mercadoria'] = ativo
        else:
            ativo = row['mercadoria']

    return df


# ─────────────────────────────────────────────────────────────
# Processamento de preços
# ─────────────────────────────────────────────────────────────

def parse_futures(df_b3: pd.DataFrame, mercadoria: str,
                  maturity_day: int, calendar: ql.Brazil) -> pd.DataFrame:
    """
    Extrai contratos futuros do ajuste pregão.
    maturity_day = 1 para DI1, 15 para DAP.
    """
    df = df_b3[df_b3['mercadoria'] == mercadoria].copy()
    if df.empty:
        raise ValueError(f"Mercadoria '{mercadoria}' não encontrada no Ajuste Pregão.")

    df['maturity_date'] = df['vencimento'].apply(lambda x:
        calendar.adjust(
            ql.Date(maturity_day, getattr(ql.IMM, x[0]), 2000 + int(x[-2:])),
            ql.Following
        ).to_date()
    )
    df['discount_factor'] = 100_000 / df['preco_atual'].astype(float)
    return df


# ─────────────────────────────────────────────────────────────
# Construção de curvas QuantLib
# ─────────────────────────────────────────────────────────────

def _attach_zero_rate(crv, calendar):
    def zero_rate(self, d):
        return self.zeroRate(d, ql.Business252(calendar), ql.Compounded).rate()
    crv.zero_rate = MethodType(zero_rate, crv)
    return crv


def build_discount_curve(dt: datetime.date, df_futures: pd.DataFrame,
                          calendar: ql.Brazil) -> ql.DiscountCurve:
    today = ql.Date.from_date(dt)
    df = df_futures[df_futures['maturity_date'] > dt].sort_values('maturity_date')

    dates = [today] + [ql.Date.from_date(d) for d in df['maturity_date']]
    dfs   = [1.0]   + list(df['discount_factor'])

    crv = ql.DiscountCurve(dates, dfs, ql.Business252(calendar), calendar, ql.LogLinear())
    crv.enableExtrapolation()
    return _attach_zero_rate(crv, calendar)


def anchor_short_end(dt: datetime.date, crv: ql.DiscountCurve,
                      selic_decimal: float, calendar: ql.Brazil) -> ql.DiscountCurve:
    """
    Insere o ponto overnight (SELIC/CDI) antes do primeiro contrato,
    ancorando o trecho curto da curva DI.
    """
    today    = ql.Date.from_date(dt)
    tomorrow = calendar.advance(today, ql.Period(1, ql.Days))
    first    = crv.nodes()[1][0]

    if tomorrow >= first:
        return crv  # primeiro contrato já é amanhã, não precisa inserir

    du_tomorrow = calendar.businessDaysBetween(today, tomorrow)
    df_overnight = (1 + selic_decimal) ** (-du_tomorrow / 252)

    dates = [today, tomorrow] + [d for (d, _) in crv.nodes()[1:]]
    dfs   = [1.0, df_overnight] + [v for (_, v) in crv.nodes()[1:]]

    crv = ql.DiscountCurve(dates, dfs, ql.Business252(calendar), calendar, ql.LogLinear())
    crv.enableExtrapolation()
    return _attach_zero_rate(crv, calendar)


def build_bei_curve(crv_di: ql.DiscountCurve, crv_dap: ql.DiscountCurve,
                     calendar: ql.Brazil) -> ql.DiscountCurve:
    """
    Curva BEI = DI / DAP em espaço de discount factor.
    Usa a união dos nós de ambas as curvas para preservar a estrutura.
    """
    nodes_di  = [d for (d, _) in crv_di.nodes()]
    nodes_dap = [calendar.adjust(d, ql.Following) for (d, _) in crv_dap.nodes()]
    dates_bei = sorted(set(nodes_di + nodes_dap))

    dfs_bei = [crv_di.discount(d) / crv_dap.discount(d) for d in dates_bei]

    crv = ql.DiscountCurve(dates_bei, dfs_bei, ql.Business252(calendar), calendar, ql.LogLinear())
    crv.enableExtrapolation()
    return _attach_zero_rate(crv, calendar)


# ─────────────────────────────────────────────────────────────
# Interpolação nos tenores
# ─────────────────────────────────────────────────────────────

def interpolate_tenors(dt: datetime.date, crv, tenors: list,
                        curve_name: str, calendar: ql.Brazil) -> pd.DataFrame:
    today = ql.Date.from_date(dt)
    rows = []
    for tenor in tenors:
        dt_tenor = calendar.adjust(today + tenor, ql.Following)
        rows.append({
            'date_reference':  dt,
            'curve_name':      curve_name,
            'tenor':           tenor,
            'tenor_date':      dt_tenor.to_date(),
            'curve_rate':      crv.zero_rate(dt_tenor),
            'discount_factor': crv.discount(dt_tenor),
            'business_day':    calendar.businessDaysBetween(today, dt_tenor),
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────
# Leitura do banco
# ─────────────────────────────────────────────────────────────

def get_selic(conn: SQLConnection, dt: datetime.date) -> float:
    """SELIC TARGET mais recente como taxa anual decimal (proxy para CDI)."""
    df = conn.run_query(
        "SELECT TOP 1 [rate] FROM [middle].[product_price] "
        f"WHERE [product_id] = 'SELIC TARGET' "
        f"AND [date_reference] <= '{dt:%Y-%m-%d}' "
        "ORDER BY [date_reference] DESC"
    )
    if df.empty:
        raise ValueError(f'SELIC TARGET não encontrada para {dt}.')
    return float(df.iloc[0, 0]) / 100


# ─────────────────────────────────────────────────────────────
# Escrita no banco
# ─────────────────────────────────────────────────────────────

def write_curve(conn: SQLConnection, df: pd.DataFrame,
                curve_name: str, dt: datetime.date):
    conn.execute(
        "DELETE FROM [risk].[interest_rate_curve] "
        "WHERE [curve_name] = ? AND [date_reference] = ?",
        [curve_name, dt.strftime('%Y-%m-%d')]
    )
    df.to_sql('interest_rate_curve', conn.engine,
              schema='risk', if_exists='append', index=False)
    print(f'  {curve_name}: {len(df)} pontos inseridos para {dt:%Y-%m-%d}.')


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────

def main(dt: datetime.date):
    conn     = SQLConnection()
    calendar = ql.Brazil()

    print(f'\nBaixando B3 Ajuste Pregão — {dt:%d/%m/%Y}...')
    df_b3 = download_b3(dt)

    # ── DI Fut ──────────────────────────────────────────────
    df_di   = parse_futures(df_b3, 'DI1 - DI de 1 dia', 1, calendar)
    crv_di  = build_discount_curve(dt, df_di, calendar)
    selic   = get_selic(conn, dt)
    crv_di  = anchor_short_end(dt, crv_di, selic, calendar)
    df_out  = interpolate_tenors(dt, crv_di, DI_TENORS, 'DI Fut', calendar)
    write_curve(conn, df_out, 'DI Fut', dt)

    # ── DAP Fut → DAP BEI ───────────────────────────────────
    df_dap  = parse_futures(df_b3, 'DAP - Cupom de DI x IPCA', 15, calendar)
    crv_dap = build_discount_curve(dt, df_dap, calendar)
    crv_bei = build_bei_curve(crv_di, crv_dap, calendar)
    df_out  = interpolate_tenors(dt, crv_bei, DAP_TENORS, 'DAP BEI', calendar)
    write_curve(conn, df_out, 'DAP BEI', dt)


if __name__ == '__main__':
    # Roda para o último dia útil
    calendar = ql.Brazil()
    today    = ql.Date.todaysDate()
    dt       = calendar.advance(today, ql.Period(-1, ql.Days)).to_date()

    # Para reprocessar um range histórico, descomente:
    # dt_ini = datetime.date(2020, 1, 1)
    # dt_fim = datetime.date.today()
    # d = ql.Date.from_date(dt_ini)
    # while d.to_date() <= dt_fim:
    #     try:
    #         main(d.to_date())
    #     except Exception as e:
    #         print(f'  Erro em {d}: {e}')
    #     d = calendar.advance(d, ql.Period(1, ql.Days))

    try:
        main(dt)
    except Exception as e:
        print(f'Erro: {e}')
