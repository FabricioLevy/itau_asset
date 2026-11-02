# Testes das verificações com dados reais colados do DBSX337 (out/2026), sem banco:
#   pytest batimento/tests -q
import numpy as np
import pandas as pd
import pytest

import detectores as det
from detectores import Parametros

PRM = Parametros()
T = pd.Timestamp


def L(data, fundo, ativo, tipo, quantidade, valor, pnl, contraparte="-", **extra):
    """Uma linha da posição no formato de consultas.posicao_linhas (valor em reais)."""
    d = {"date": T(data), "codigo_IAM_fundo": fundo, "codigo_IAM_ativo": ativo, "contraparte": contraparte,
         "tipo": tipo, "quantidade": quantidade, "total": valor, "total_moeda_fundo": valor, "pnl_total": pnl}
    d.update(extra)
    return d


def linhas(*rows):
    return det.prepara_linhas(pd.DataFrame(list(rows)))


def cota(data, fundo, pnl, pl, classe="A", mesa="INDEXADOS"):
    perc = pnl / pl if pd.notna(pnl) and pl else np.nan
    return {"date": T(data), "codigo_IAM_fundo": fundo, "classe": classe, "mesa_gestao": mesa,
            "last_patrimonio": pl, "fundo_pnl": pnl, "fundo_pnl_perc": perc}


def pos(data, fundo, pnl, pl, outras=0.0, ajuste=0.0, n=10):
    return {"date": T(data), "codigo_IAM_fundo": fundo, "linhas": n, "pnl_total": pnl, "pnl_bps": pnl / pl * 1e4,
            "pnl_outras_despesas": outras, "pnl_ajuste_manual": ajuste}


def linha_tri(data, fundo, dif, pl, anterior=None, marcado=True):
    return pd.Series({"date": T(data), "codigo_IAM_fundo": fundo, "dif_rs": dif, "pl": pl,
                      "data_anterior": T(anterior) if anterior else pd.NaT, "marcado": marcado})


def so(oc, codigo):
    return [o for o in oc if o["verificacao"] == codigo]


# ── B5P211 (ITAUIMA5P2070) em 15/10: integralização em espécie lançada em OUTRAS_DESPESAS ───────────────────

B5_PL = 4_532_751_592.61
B5_D = [  # (ativo, tipo, qtd_d1, qtd_d, total_d1, total_d, pnl_total) — consulta dia contra dia de 15/10
    ("OUTRAS_DESPESAS", "Despesa", None, 1, None, 0, -11526424.6),
    ("BRSTNCNTB3B8", "Fixed Income", 310024, 310792, 1457399201.41, 1458761105.59, -2242843.5),
    ("BRSTNCNTB682", "Fixed Income", 179608, 180054, 879974468.42, 883139806.95, 977777.74),
    ("BRSTNCNTB4X0", "Fixed Income", 314090, 314868, 1493887245.71, 1496622983.65, -962236.13),
    ("BRSTNCNTB716", "Fixed Income", 114384, 114715, 550239025.24, 551329476.29, -500391.93),
    ("BRSTNCNTB7X3", "Fixed Income", 31793, 31886, 151198912.44, 151466661.66, -174037.22),
    ("TAXA_GESTAO_APROPRIADA", "Despesa", 1, 1, -206940.18, -230323.82, -23383.64),
    ("TAXA_ADMINISTRACAO", "Despesa", 1, 1, -63673.89, -70868.86, -7194.97),
    ("TAXA_CUSTODIA", "Despesa", 1, 1, -47755.42, -53151.64, -5396.22),
    ("TAXA_LICENCA_INFO_MARCA", "Despesa", 1, 1, -237518.21, -241115.69, -3597.48),
    ("AJUSTE_COMPENSACAO_COTAS", "Despesa", 1, 1, 5313.89, 2812.44, -2501.45),
    ("CUSTO_SELIC", "Despesa", 1, 1, -14860.77, -4742.88, -474.29),
    ("TAXA_CVM", "Despesa", 1, 1, 12115.76, 11887.16, -228.6),
    ("BRSTNCLF1RI1", "Fixed Income", 8, 8, 160565.99, 160649.15, 83.16),
    ("IMPOSTOS", "Despesa", 1, 1, 4219.48, 4139.87, -79.61),
    ("BRSTNCLF1RL5", "Fixed Income", 7, 7, 140368.19, 140443.14, 74.95),
    ("BRSTNCLF1RK7", "Fixed Income", 4, 4, 80269.75, 80311.8, 42.05),
    ("DESPESAS_AUDITORIA", "Despesa", 1, 1, -4476.38, -4509.54, -33.16),
    ("DESPESAS_ANBID", "Despesa", 1, 1, -209.7, 699, -23.3),
    ("CARTORIO", "Despesa", 1, 1, -1202.4, -1202.4, 0),
    ("caixa_brl", "CaixaCPR", 1, 1, 301537.77, 290013.96, 0),
    ("CaixaCPROutros", "CaixaCPROutros", 1, 1, 2341.6, 6216.58, 0),
]


def b5_linhas(d="2026-10-15", p="2026-10-14", fundo="ITAUIMA5P2070"):
    ld = linhas(*[L(d, fundo, a, t, qd, vd, pnl) for a, t, _, qd, _, vd, pnl in B5_D])
    lp = linhas(*[L(p, fundo, a, t, qp, vp, 0.0) for a, t, qp, _, vp, _, _ in B5_D if qp is not None])
    return ld, lp


def test_b5p211_outras_despesas_em_especie():
    ld, lp = b5_linhas()
    assert ld["pnl_total"].sum() == pytest.approx(-14_470_868.20, abs=0.01)
    gap = 11_526_787.30
    oc = det.verifica_fundo(linha_tri("2026-10-15", "ITAUIMA5P2070", gap, B5_PL, "2026-10-14"), ld, lp, PRM)
    assert [o["verificacao"] for o in oc] == ["OUTRAS_DESPESAS_ESPECIE"]
    o = oc[0]
    assert o["ativo"] == "OUTRAS_DESPESAS" and o["status"] == "explica"
    assert o["residuo_rs"] == pytest.approx(362.70, abs=0.01)
    assert o["ajuste_rs"] == pytest.approx(11_526_424.60, abs=0.01)
    assert "5 ativo(s) entraram em espécie por R$ 11.522.911,96" in o["detalhe"]
    assert "integralização" in o["detalhe"]


# ── FICFI53254 em 20/10: a diferença é o saldo do CaixaCPROutros, via AJUSTE_COMPENSACAO_COTAS ──────────────

FIC_D = [  # (ativo, tipo, qtd, total_d1, total_d, pnl_total)
    ("IBSCVALUATRV106", "Fund", 8694.05587, 1510246.01, 1563241.93, 52995.92),
    ("AJUSTE_COMPENSACAO_COTAS", "Despesa", 1, 0, 0, 6113.88),
    ("caixa_brl", "CaixaCPR", 1, 1288.76, 1229.76, 0),
    ("CaixaCPROutros", "CaixaCPROutros", 1, -6172.88, -6208.92, 0),
    ("FICFI54694", "Fund", 22.83474953, 348.66, 361.13, 12.47),
    ("TAXA_DISTRIBUICAO", "Despesa", 1, -137.12, -149.14, -12.02),
    ("ZERARF54582", "Fund", 570.80620715, 10923.36, 10928.99, 5.63),
    ("DESPESAS_AUDITORIA", "Despesa", 1, -1898.77, -1898.77, 0),
]


def fic_linhas(d="2026-10-20", p="2026-10-19", fundo="FICFI53254"):
    ld = linhas(*[L(d, fundo, a, t, q, vd, pnl) for a, t, q, _, vd, pnl in FIC_D],
                L(d, fundo, "OUTRAS_DESPESAS", "Despesa", 1, 0, 0))
    lp = linhas(*[L(p, fundo, a, t, q, vp, 0.0) for a, t, q, vp, _, _ in FIC_D])
    return ld, lp


def test_ficfi53254_diferenca_igual_saldo_do_cpr():
    ld, lp = fic_linhas()
    oc = det.verifica_fundo(linha_tri("2026-10-20", "FICFI53254", -6208.92, 1_514_740, "2026-10-19"), ld, lp, PRM)
    cod = [o["verificacao"] for o in oc]
    assert cod == ["LINHA_EXPLICA", "DIFERENCA_IGUAL_SALDO"]          # sem LINHA_SEM_SALDO repetida
    linha, saldo = oc
    assert linha["ativo"] == "AJUSTE_COMPENSACAO_COTAS"
    assert linha["residuo_rs"] == pytest.approx(-95.04, abs=0.01)
    assert saldo["ativo"] == "CaixaCPROutros" and saldo["residuo_rs"] == 0
    assert "AJUSTE_COMPENSACAO_COTAS" in saldo["detalhe"] and "sinal trocado" not in saldo["detalhe"]


# ── ITSCAPFIA53839 em 19/10: BXP3SR7 entrou a 3,0× o valor de mercado ───────────────────────────────────────

ITS_PL = 4_599_431.37 / 0.014669
ITS_D = [  # (ativo, tipo, qtd_d1, qtd_d, total_d1, total_d, pnl_total)
    ("BXP3SR7", "Equity", None, 64177, None, 2239777.3, -4480755.64),
    ("CaixaCPROutros", "CaixaCPROutros", 1, 1, 2278427.01, 150447.59, 0),
    ("BJN6MH8", "Equity", 667000, 667000, 45502740, 46423200, 919273.64),
    ("BMZ9R04", "Equity", 963468, 962912, 12370637.13, 12897770.7, 534101.41),
    ("B4975P9", "Equity", 451419, 452228, 5015847.75, 5350670.58, 326721.95),
    ("BRJPLM3", "Equity", 135373, 135555, 3167659.07, 3593916.51, 422549.94),
    ("APORTE_RESGATE_COTISTAS", "CaixaCPR", 1, 1, -500791.4, -708076.42, 0),
]


def test_itscapfia_fluxo_fora_do_mercado():
    d, p, f = "2026-10-19", "2026-10-16", "ITSCAPFIA53839"
    ld = linhas(*[L(d, f, a, t, qd, vd, pnl) for a, t, _, qd, _, vd, pnl in ITS_D])
    lp = linhas(*[L(p, f, a, t, qp, vp, 0.0) for a, t, qp, _, vp, _, _ in ITS_D if qp is not None])
    oc = det.verifica_fundo(linha_tri(d, f, 4_599_431.37, ITS_PL, p), ld, lp, PRM)
    assert [o["verificacao"] for o in oc] == ["FLUXO_FORA_MERCADO"]   # as compras e vendas normais não entram
    o = oc[0]
    assert o["ativo"] == "BXP3SR7" and o["status"] == "explica"
    assert o["tipo_linha"] == "Equity" and o["contraparte_linha"] == "-"
    # a mercado o resíduo seria R$ 118.675,73; pelo valor que saiu do CaixaCPROutros (150.447,59 − 2.278.427,01),
    # a entrada fecha a diferença em R$ 6.877,85
    assert "a diferença iria para R$ 118.675,73" in o["detalhe"]
    assert "CaixaCPROutros variou R$ -2.127.979,42 sem PnL" in o["detalhe"]
    assert o["ajuste_rs"] == pytest.approx(4_592_553.52, abs=0.01)
    assert o["residuo_rs"] == pytest.approx(6_877.85, abs=0.01)


# ── BITI11 (ITAUBLO66606): linha do CotaExternaD0.py no feriado somada duas vezes ───────────────────────────

def precos(*rows):
    cols = ["date", "codigo_IAM_ativo", "preco_limpo", "preco_limpo_d1", "pnl_moeda_ativo", "log_script_from",
            "log_last_user", "log_last_processamento"]
    return pd.DataFrame([dict(zip(cols, r)) for r in rows])


def pos_ativos(data, fundo, ativo, q, fx, moeda="USD", ajuste=0.0, pnl=np.nan, q_abertura=None):
    return pd.DataFrame([{"date": T(data), "codigo_IAM_fundo": fundo, "codigo_IAM_ativo": ativo, "quantidade": q,
                          "quantidade_abertura": q if q_abertura is None else q_abertura, "preco_cambio": fx,
                          "moeda_ativo": moeda, "pnl_moeda_ativo": pnl, "pnl_ajuste_manual": ajuste}])


H_1210 = (T("2026-10-12"), "3GALABIT", 46.969083, 46.353898, 0.615184999999997, "CotaExternaD0.py", "spquant",
          T("2026-10-12 19:01:14.427"))
D_1310 = (T("2026-10-13"), "3GALABIT", 46.864024, 46.353898, 0.510126, "CotaExternaSAC.py", "spquant",
          T("2026-10-14 06:09:14.563"))
Q_1310 = 1865711.00691692


def tri_um(data, fundo, dif, marcado=True):
    return pd.DataFrame([{"date": T(data), "codigo_IAM_fundo": fundo, "dif_rs": dif, "marcado": marcado}])


def test_biti11_1310_preco_de_feriado_confirmado():
    oc = det.preco_feriado(T("2026-10-13"), pos_ativos("2026-10-13", "ITAUBLO66606", "3GALABIT", Q_1310, 5.0175),
                           precos(H_1210), precos(D_1310), pd.Series({"ITAUBLO66606": T("2026-10-09")}),
                           tri_um("2026-10-13", "ITAUBLO66606", -5_758_503.43), PRM)
    assert len(oc) == 1
    o = oc[0]
    assert o["verificacao"] == "PRECO_FERIADO" and o["status"] == "confirmado"
    assert o["ajuste_rs"] == pytest.approx(-5_758_872.88, abs=0.01)
    assert o["residuo_rs"] == pytest.approx(369.45, abs=0.01)
    assert "CotaExternaD0.py" in o["detalhe"] and "12/10/2026" in o["detalhe"]
    assert "R$ -5.758.872,88" in o["acao"]


def test_biti11_1802_ja_corrigido_com_ajuste_manual():
    h = (T("2026-02-16"), "3GALABIT", 43.210737, 38.884266, 4.32647100000001, "CotaExternaD0.py", "spquant",
         T("2026-02-16 19:31:04.970"))
    d = (T("2026-02-18"), "3GALABIT", 37.545329, 38.884266, -1.33893699999999, "CotaExternaSAC.py", "chinone",
         T("2026-03-02 11:35:51.707"))
    oc = det.preco_feriado(T("2026-02-18"),
                           pos_ativos("2026-02-18", "ITAUBLO66606", "3GALABIT", 2014213.0079969, 5.2424,
                                      ajuste=-45_684_549),
                           precos(h), precos(d), pd.Series({"ITAUBLO66606": T("2026-02-13")}),
                           tri_um("2026-02-18", "ITAUBLO66606", 0.25, marcado=False), PRM)
    assert [o["status"] for o in oc] == ["corrigido"]
    assert oc[0]["ajuste_rs"] == pytest.approx(-45_684_549.68, abs=0.01)


def test_preco_de_feriado_encadeado_ou_fundo_que_bateu_nao_entra():
    # linha do dia partindo do preço do feriado: sem sobreposição
    d_encadeado = D_1310[:3] + (46.969083, -0.105059) + D_1310[5:]
    oc = det.preco_feriado(T("2026-10-13"), pos_ativos("2026-10-13", "X", "3GALABIT", Q_1310, 5.0175),
                           precos(H_1210), precos(d_encadeado), pd.Series({"X": T("2026-10-09")}),
                           tri_um("2026-10-13", "X", -5_758_503.43), PRM)
    assert oc == []
    # sobreposição num fundo que bateu com a cota (duplicidade de scripts): a posição não usou a linha
    oc = det.preco_feriado(T("2026-10-13"), pos_ativos("2026-10-13", "X", "3GALABIT", Q_1310, 5.0175),
                           precos(H_1210), precos(D_1310), pd.Series({"X": T("2026-10-09")}),
                           tri_um("2026-10-13", "X", 10.49, marcado=False), PRM)
    assert oc == []


def test_biti11_pnl_fora_de_preco_so_no_dia_do_feriado():
    f = "ITAUBLO66606"
    galabit = dict(moeda_ativo="USD", preco_cambio=5.0175, preco_limpo=46.864024, preco_limpo_d1=46.353898,
                   quantidade_abertura=Q_1310, pnl_moeda_ativo=10534266.94, pnl_cambio=2536542.64)
    ld = linhas(L("2026-10-13", f, "3GALABIT", "Fund", Q_1310, 438_703_734.65, 13070809.58, **galabit))
    oc = det.pnl_fora_preco(T("2026-10-13"), f, -5_758_503.43, ld, 431_629_931.82, PRM)
    assert len(oc) == 1 and oc[0]["status"] == "explica"
    assert oc[0]["ajuste_rs"] == pytest.approx(-5_758_872.89, abs=0.01)
    assert oc[0]["residuo_rs"] == pytest.approx(369.46, abs=0.01)
    dia_14 = dict(galabit, preco_cambio=5.0317, preco_limpo=46.03386, preco_limpo_d1=46.864024,
                  quantidade_abertura=1863803.00793672, pnl_moeda_ativo=-7785359.01)
    ld = linhas(L("2026-10-14", f, "3GALABIT", "Fund", 1863803.00793672, 1e8, -6543785.91, **dia_14))
    assert det.pnl_fora_preco(T("2026-10-14"), f, 0.0, ld, 438_486_397.41, PRM) == []


# ── alerta: linha do D0 no feriado depois da última posição ─────────────────────────────────────────────────

def test_alerta_de_feriado_so_dia_nao_util_e_script_da_lista():
    fut = precos(
        (T("2026-11-02"), "3GALABIT", 46.2, 45.7, 0.5, "CotaExternaD0.py", "spquant", T("2026-11-02 19:01")),
        (T("2026-11-03"), "3GALABIT", 46.4, 46.2, 0.2, "CotaExternaD0.py", "spquant", T("2026-11-03 19:01")),
        (T("2026-11-01"), "3GALABIT", 45.9, 45.7, 0.2, "Equities_BBG.py", "spquant", T("2026-11-01 08:00")),
    )
    pa = pos_ativos("2026-10-30", "ITAUBLO66606", "3GALABIT", 1862849.0, 5.4544)
    oc = det.alerta_feriado(T("2026-10-30"), T("2026-11-03"), pa, fut, PRM)
    assert len(oc) == 1
    o = oc[0]
    assert o["data"] == T("2026-11-02") and o["status"] == "alerta"
    assert o["ajuste_rs"] == pytest.approx(-1862849.0 * 0.5 * 5.4544)


# ── triagem ─────────────────────────────────────────────────────────────────────────────────────────────────

def test_triagem_sem_posicao_codigo_novo_e_classe():
    cot = pd.DataFrame([
        cota("2026-10-28", "FICFI54649", 215934.09, 62_409_629.93),
        cota("2026-10-28", "FICFI54649S1", np.nan, np.nan),
        cota("2026-10-29", "FICFI54649", 558117.20, 62_732_695.57),
        cota("2026-10-29", "FICFI54649S1", 558114.44, 62_732_689.25),
        # fundo com várias classes: vale a Total, que bate com a posição
        cota("2026-10-29", "ESP_AAAMODERAT", 1_135_177.32 - 10.49 + 30_000, 1e9, classe="A", mesa="SFF_OFF"),
        cota("2026-10-29", "ESP_AAAMODERAT", -609_000.0, 1e9, classe="Total", mesa="SFF_OFF"),
    ])
    p = pd.DataFrame([
        pos("2026-10-28", "FICFI54649", 215934.32, 62_409_629.93),
        pos("2026-10-29", "FICFI54649", 558115.78, 62_732_695.57),
        pos("2026-10-29", "ESP_AAAMODERAT", -609_010.49, 1e9),
    ])
    tri = det.triagem(cot, p, PRM)
    t29 = tri[tri["date"] == T("2026-10-29")].set_index("codigo_IAM_fundo")
    assert t29.loc["FICFI54649S1", "situacao"] == "SEM POSIÇÃO" and t29.loc["FICFI54649S1", "marcado"]
    assert pd.isna(t29.loc["FICFI54649S1", "cota_anterior"])        # 28/10 sem PnL: código novo
    assert not t29.loc["FICFI54649", "marcado"]
    assert t29.loc["ESP_AAAMODERAT", "classe"] == "Total" and t29.loc["ESP_AAAMODERAT", "classes"] == 2
    assert not t29.loc["ESP_AAAMODERAT", "marcado"]
    oc = det.ocorrencias_triagem(tri[tri["date"] == T("2026-10-29")])
    assert [o["verificacao"] for o in oc] == ["SEM_POSICAO"]
    assert "código novo" in oc[0]["detalhe"]
    assert pd.isna(oc[0]["ajuste_rs"])            # o PnL pode estar no código de origem: sem ajuste sugerido


def test_triagem_limiares_e_recorrencia():
    pl = 1_500_000.0
    cot = pd.DataFrame([cota(f"2026-10-{d:02d}", "FICFI53254", 50_000.0, pl) for d in (13, 14, 15, 16)]
                       + [cota("2026-10-16", "FICFI57679", 10.0, 442.74)])
    p = pd.DataFrame([pos(f"2026-10-{d:02d}", "FICFI53254", 56_000.0, pl) for d in (13, 14, 15, 16)]
                     + [pos("2026-10-16", "FICFI57679", 10.23, 442.74)])
    tri = det.triagem(cot, p, PRM).set_index(["date", "codigo_IAM_fundo"])
    assert tri.loc[(T("2026-10-16"), "FICFI53254"), "recorrencia"] == "4 de 4"
    assert tri.loc[(T("2026-10-16"), "FICFI53254"), "data_anterior"] == T("2026-10-15")
    # -5 bps com R$ 0,23: abaixo do limite em reais
    assert not tri.loc[(T("2026-10-16"), "FICFI57679"), "marcado"]


def test_calendario_2026():
    assert {date for date in det.feriados_nacionais(2026)} >= {
        T(x).date() for x in ("2026-02-16", "2026-02-17", "2026-04-03", "2026-06-04", "2026-09-07",
                              "2026-10-12", "2026-11-02", "2026-11-20", "2026-12-25")}
    assert not det.dia_util(T("2026-10-12")) and not det.dia_util(T("2026-11-01")) and det.dia_util(T("2026-11-03"))


# ── tabela de preços ────────────────────────────────────────────────────────────────────────────────────────

def test_anomalias_preco_zero_e_duplicado():
    an = precos((T("2026-10-12"), "EQYNLT_QSLU54604746", 0.0, 1.0, -0.99998996913, "SSC_EquityNonListed.py",
                 "spquant", T("2026-10-13 08:29")))
    du = pd.DataFrame([{"date": T("2026-10-12"), "codigo_IAM_ativo": "BJYGLG9", "linhas": 2, "preco_min": 164.97,
                        "preco_max": 165.04, "script_1": "APX_MutualFund.py", "script_2": "Equities_BBG.py"}])
    pl = pd.concat([pos_ativos("2026-10-13", "ESP_BOURGOGNE", "EQYNLT_QSLU54604746", 2_160_000, 5.0175),
                    pos_ativos("2026-10-13", "ESP_AAAMODERAT", "BJYGLG9", 473148, 5.0175),
                    pos_ativos("2026-10-13", "ESP_AAACONSERV", "BJYGLG9", 202183, 5.0175)])
    t = det.anomalias_preco(an, du, pl, PRM).set_index("verificacao")
    assert t.loc["PRECO_ZERO", "fundos"] == "ESP_BOURGOGNE"
    assert t.loc["PRECO_ZERO", "exposicao_rs"] == pytest.approx(-2_160_000 * 5.0175)
    assert t.loc["PRECO_DUPLICADO", "fundos"] == "2 fundos (maior: ESP_AAAMODERAT)"
    assert t.loc["PRECO_DUPLICADO", "exposicao_rs"] == pytest.approx((473148 + 202183) * 0.07 * 5.0175)


# ── de ponta a ponta, sem banco ─────────────────────────────────────────────────────────────────────────────

class FonteFake:
    """Mesmos métodos e formatos da consultas.FonteSQL, a partir de linhas da posição, cotas e preços."""

    def __init__(self, linhas_pos, cotas, precos_df):
        self.lin = det.prepara_linhas(pd.DataFrame(linhas_pos))
        self.cot = pd.DataFrame(cotas)
        self.pre = precos_df
        pl = self.cot.set_index(["date", "codigo_IAM_fundo"])["last_patrimonio"]
        self.lin["last_patrimonio"] = [pl.get((r.date, r.codigo_IAM_fundo), np.nan) for r in self.lin.itertuples()]
        self.lin["pnl_total_perc"] = self.lin["pnl_total"] / self.lin["last_patrimonio"]
        self.lin["pnl_moeda_ativo_perc"] = self.lin["pnl_moeda_ativo"] / self.lin["last_patrimonio"]

    def linhas_alvo(self, data, fundo, ativo):
        l = self.lin
        return l[(l["date"] == data) & (l["codigo_IAM_fundo"] == fundo) & (l["codigo_IAM_ativo"] == ativo)].copy()

    def conexao_escrita(self):
        return None

    def datas_com_cota(self, de, ate):
        c = self.cot[self.cot["date"].between(de, ate)]
        return c.groupby("date")["codigo_IAM_fundo"].nunique().rename("fundos").reset_index()

    def cotas(self, de, ate, mesa=None, fundos=None):
        return self.cot[self.cot["date"].between(de, ate)].copy()

    def posicao_resumo(self, de, ate, mesa=None, fundos=None):
        l = self.lin[self.lin["date"].between(de, ate)].copy()
        l["outras"] = np.where(l["codigo_IAM_ativo"] == "OUTRAS_DESPESAS", l["pnl_total"], 0.0)
        l["ajuste"] = np.where(l["contraparte"] == "ajuste_pnl", l["pnl_total"], 0.0)
        g = l.groupby(["date", "codigo_IAM_fundo"])
        return pd.DataFrame({"linhas": g.size(), "pnl_total": g["pnl_total"].sum(),
                             "pnl_bps": g["pnl_total_perc"].sum() * 1e4, "pnl_outras_despesas": g["outras"].sum(),
                             "pnl_ajuste_manual": g["ajuste"].sum()}).reset_index()

    def posicao_linhas(self, fundos, datas):
        datas = {T(x) for x in datas}
        return self.lin[self.lin["codigo_IAM_fundo"].isin(fundos) & self.lin["date"].isin(datas)].copy()

    def ajustes_manuais(self, de, ate):
        return self.lin[(self.lin["contraparte"] == "ajuste_pnl") & self.lin["date"].between(de, ate)].copy()

    def _pos_ativos(self, data, ativos):
        l = self.lin[(self.lin["date"] == data) & self.lin["codigo_IAM_ativo"].isin(ativos)]
        ativo = l[(l["contraparte"] != "ajuste_pnl") & ~l["tipo"].str.startswith("Caixa")]
        g = ativo.groupby(["date", "codigo_IAM_fundo", "codigo_IAM_ativo"])
        out = pd.DataFrame({"quantidade": g["quantidade"].sum(), "quantidade_abertura": g["quantidade_abertura"].sum(),
                            "preco_cambio": g["preco_cambio"].max(), "moeda_ativo": g["moeda_ativo"].max(),
                            "pnl_moeda_ativo": g["pnl_moeda_ativo"].sum()}).reset_index()
        aj = (l[l["contraparte"] == "ajuste_pnl"].groupby(["codigo_IAM_fundo", "codigo_IAM_ativo"])["pnl_total"]
              .sum().rename("pnl_ajuste_manual"))
        out = out.join(aj, on=["codigo_IAM_fundo", "codigo_IAM_ativo"])
        out["pnl_ajuste_manual"] = out["pnl_ajuste_manual"].fillna(0.0)
        return out

    def precos_entre(self, apos, antes, data_posicao):
        em_carteira = set(self.lin.loc[self.lin["date"] == data_posicao, "codigo_IAM_ativo"])
        p = self.pre
        return p[(p["date"] > apos) & (p["date"] < antes) & (p["pnl_moeda_ativo"] != 0)
                 & p["codigo_IAM_ativo"].isin(em_carteira)].copy()

    def precos_do_dia(self, data, apos, antes):
        p = self.pre
        com = set(p.loc[(p["date"] > apos) & (p["date"] < antes) & (p["pnl_moeda_ativo"] != 0), "codigo_IAM_ativo"])
        return p[(p["date"] == data) & p["codigo_IAM_ativo"].isin(com)].copy()

    def posicao_ativos_entre(self, data, apos, antes):
        p = self.pre
        com = set(p.loc[(p["date"] > apos) & (p["date"] < antes) & (p["pnl_moeda_ativo"] != 0), "codigo_IAM_ativo"])
        return self._pos_ativos(data, com)

    def posicao_ativos_lista(self, data, ativos):
        return self._pos_ativos(data, set(ativos))

    def precos_anomalos(self, apos, ate, data_posicao, salto):
        return self.pre.iloc[0:0].copy()

    def precos_duplicados(self, apos, ate, data_posicao):
        return pd.DataFrame(columns=["date", "codigo_IAM_ativo", "linhas", "preco_min", "preco_max", "script_1",
                                     "script_2"])


def fonte_outubro():
    """13/10 com os quatro casos (datas trocadas para 09/10 → 13/10) e um fundo que bate."""
    d, p = "2026-10-13", "2026-10-09"
    lin, cot = [], []
    # B5P211 (ITAUIMA5P2070): integralização em OUTRAS_DESPESAS
    for a, t, qp, qd, vp, vd, pnl in B5_D:
        lin.append(L(d, "ITAUIMA5P2070", a, t, qd, vd, pnl))
        if qp is not None:
            lin.append(L(p, "ITAUIMA5P2070", a, t, qp, vp, 0.0))
    cot += [cota(d, "ITAUIMA5P2070", -2_944_080.90, B5_PL), cota(p, "ITAUIMA5P2070", 0.0, B5_PL)]
    # FICFI53254: saldo do CPR virando PnL
    for a, t, q, vp, vd, pnl in FIC_D:
        lin += [L(d, "FICFI53254", a, t, q, vd, pnl), L(p, "FICFI53254", a, t, q, vp, 0.0)]
    cot += [cota(d, "FICFI53254", 52_906.96, 1_514_740), cota(p, "FICFI53254", 0.0, 1_514_740)]
    # BITI11: 3GALABIT com a linha de 12/10 do CotaExternaD0.py
    g = dict(moeda_ativo="USD", preco_cambio=5.0175, preco_limpo=46.864024, preco_limpo_d1=46.353898,
             quantidade_abertura=Q_1310, pnl_moeda_ativo=10534266.94, pnl_cambio=2536542.64, total=87434725.41)
    lin += [L(d, "ITAUBLO66606", "3GALABIT", "Fund", Q_1310, 87434725.41 * 5.0175, 13070809.58, **g),
            L(d, "ITAUBLO66606", "TAXA_GESTAO_APROPRIADA", "Despesa", 1, -39978.71, -7376.56),
            L(p, "ITAUBLO66606", "3GALABIT", "Fund", 1867619.00804028, 86571421 * 4.9882, 836462.32,
              moeda_ativo="USD", preco_cambio=4.9882, total=86571421.0),
            L(p, "ITAUBLO66606", "TAXA_GESTAO_APROPRIADA", "Despesa", 1, -35182.82, 0.0)]
    cot += [cota(d, "ITAUBLO66606", 7_304_929.59, 431_629_931.82),
            cota(p, "ITAUBLO66606", 836_462.32, 431_235_805.15)]
    # um fundo que bate e um código novo sem posição
    lin += [L(d, "FUNDOOK", "ACAO1", "Equity", 100, 10_000.0, 500.0), L(p, "FUNDOOK", "ACAO1", "Equity", 100, 9_500.0, 0.0)]
    cot += [cota(d, "FUNDOOK", 500.0, 10_000.0), cota(p, "FUNDOOK", 0.0, 10_000.0),
            cota(d, "FICFI54649S1", 558_114.44, 62_732_689.25)]
    pre = precos((T(p), "3GALABIT", 46.353898, 46.047437, 0.306460999999999, "CotaExternaSAC.py", "spquant",
                  T("2026-10-13 06:12")), H_1210, D_1310)
    return FonteFake(lin, cot, pre)


def carrega_main():
    """O __main__.py do batimento como módulo (o nome __main__ já é do pytest)."""
    import os
    from importlib import util
    spec = util.spec_from_file_location("batimento_main", os.path.join(os.path.dirname(det.__file__), "__main__.py"))
    bm = util.module_from_spec(spec)
    spec.loader.exec_module(bm)
    return bm


def test_ponta_a_ponta(tmp_path):
    import relatorio
    bm = carrega_main()
    res = bm.roda(fonte_outubro(), [T("2026-10-13")], PRM, hoje=T("2026-10-14"), log=lambda *a: None)
    assert res.avisos == []
    r = res.resumo.set_index("codigo_IAM_fundo")
    assert set(r.index) == {"ITAUIMA5P2070", "FICFI53254", "ITAUBLO66606", "FICFI54649S1"}
    assert r.loc["ITAUBLO66606", "verificacao"] == "PRECO_FERIADO"
    assert r.loc["ITAUBLO66606", "status"] == "confirmado"
    assert r.loc["ITAUBLO66606", "ajuste_rs"] == pytest.approx(-5_758_872.88, abs=0.01)
    assert r.loc["ITAUBLO66606", "outras"] == "PnL fora de quantidade × preço × câmbio"   # sem o fluxo derivado
    assert r.loc["ITAUIMA5P2070", "verificacao"] == "OUTRAS_DESPESAS_ESPECIE"
    assert r.loc["FICFI53254", "verificacao"] == "DIFERENCA_IGUAL_SALDO"
    assert r.loc["FICFI54649S1", "verificacao"] == "SEM_POSICAO"

    caminho = relatorio.grava_excel(res, str(tmp_path), bm.nome_arquivo(res, "INDEXADOS"))
    assert caminho.endswith("batimento_20261013_INDEXADOS.xlsx")
    abas = pd.ExcelFile(caminho).sheet_names
    assert abas == ["Resumo", "Ocorrências", "Triagem", "Preços", "Leia-me"]
    resumo_xlsx = pd.read_excel(caminho, sheet_name="Resumo")
    assert list(resumo_xlsx["Fundo"])[0] == "ITAUIMA5P2070"        # maior diferença primeiro
    linhas_impressas = []
    bm.imprime(res, caminho, log=linhas_impressas.append)
    assert any("ITAUBLO66606" in x and "confirmado" in x for x in linhas_impressas)


# ── caminhos restantes: SEM COTA, datas, ajustes manuais e intervalo de datas ──────────────────────────────

def test_sem_cota_so_para_fundo_que_tinha_cota():
    cot = pd.DataFrame([cota("2026-10-14", "F1", 1000.0, 1e6)])
    p = pd.DataFrame([pos("2026-10-14", "F1", 1000.0, 1e6), pos("2026-10-15", "F1", 5000.0, 1e6),
                      pos("2026-10-15", "SEMCOTA_NUNCA", 9000.0, 1e6)])
    tri = det.triagem(cot, p, PRM)
    t15 = tri[tri["date"] == T("2026-10-15")].set_index("codigo_IAM_fundo")
    assert t15.loc["F1", "situacao"] == "SEM COTA"
    assert not t15.loc["SEMCOTA_NUNCA", "marcado"]          # fundo que nunca tem cota não vira alerta
    oc = det.ocorrencias_triagem(tri[tri["date"] == T("2026-10-15")])
    assert [o["verificacao"] for o in oc] == ["SEM_COTA"] and "14/10/2026" in oc[0]["detalhe"]


def test_datas_ignoram_dia_com_poucos_fundos():
    bm = carrega_main()

    class F:
        def datas_com_cota(self, de, ate):
            return pd.DataFrame({"date": [T("2026-10-09"), T("2026-10-12"), T("2026-10-13")],
                                 "fundos": [1200, 40, 1210]})       # 12/10: só fundos com calendário de fora
    assert bm.escolhe_datas(F(), hoje=T("2026-10-14")) == [T("2026-10-13")]
    assert bm.escolhe_datas(F(), de=T("2026-10-01"), ate=T("2026-10-13")) == [T("2026-10-09"), T("2026-10-13")]
    assert bm.escolhe_datas(F(), data=T("2026-10-12")) == [T("2026-10-12")]


def test_ajuste_manual_vira_registro():
    aj = pd.DataFrame([{"date": T("2026-02-18"), "codigo_IAM_fundo": "ITAUBLO66606", "codigo_IAM_ativo": "3GALABIT",
                        "pnl_total": -45684549.0, "log_last_user": "chinone",
                        "log_last_processamento": T("2026-03-02 11:36:27")}])
    oc = det.ocorrencias_ajustes(aj)
    assert oc[0]["verificacao"] == "AJUSTE_MANUAL" and oc[0]["status"] == "info"
    assert "R$ -45.684.549,00" in oc[0]["detalhe"] and "chinone" in oc[0]["detalhe"]


def test_intervalo_de_datas():
    bm = carrega_main()
    res = bm.roda(fonte_outubro(), [T("2026-10-09"), T("2026-10-13")], PRM, hoje=T("2026-10-14"),
                  log=lambda *a: None)
    assert res.avisos == []
    assert set(res.triagem["date"]) == {T("2026-10-09"), T("2026-10-13")}
    assert len(res.resumo) == 4 and set(res.resumo["date"]) == {T("2026-10-13")}
    assert bm.nome_arquivo(res) == "batimento_20261009_20261013.xlsx"
