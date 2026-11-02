# Testes da correção (correcao.py) com os casos de out/2026, sem banco: uma transação falsa aplica os mesmos UPDATEs
# nas linhas da FonteFake.
import os

import numpy as np
import pandas as pd
import pytest

import correcao as cor
from test_detectores import PRM, T, carrega_main, fonte_outubro


class TransacaoFake:
    """Mesma interface da correcao.TransacaoSQL, sobre as linhas da FonteFake."""

    def __init__(self, fonte):
        self.f = fonte
        self.antes = fonte.lin.copy()
        self.commits = 0

    def atualiza(self, c):
        l = self.f.lin
        m = ((l["date"] == c.data) & (l["codigo_IAM_fundo"] == c.fundo) & (l["codigo_IAM_ativo"] == c.ativo)
             & (l["contraparte"].fillna("-") == c.contraparte) & (l["tipo"].fillna("") == c.tipo)
             & ((l["pnl_total"] - c.pnl_total).abs() < 0.01))
        if pd.notna(c.pnl_moeda_ativo):
            m &= (l["pnl_moeda_ativo"] - c.pnl_moeda_ativo).abs() < 0.01
        l.loc[m, "pnl_total"] += c.delta
        l.loc[m, "pnl_total_perc"] += c.delta_perc
        if pd.notna(c.pnl_moeda_ativo):
            l.loc[m, "pnl_moeda_ativo"] += c.delta
            l.loc[m, "pnl_moeda_ativo_perc"] += c.delta_perc
        return int(m.sum())

    def confere(self, data, fundo, classe):
        c = self.f.cot
        c = c[(c["date"] == data) & (c["codigo_IAM_fundo"] == fundo) & (c["classe"] == classe)]
        l = self.f.lin
        pos = l.loc[(l["date"] == data) & (l["codigo_IAM_fundo"] == fundo), "pnl_total"].sum()
        return float(c["fundo_pnl"].iloc[0]), float(pos)

    def commit(self):
        self.commits += 1
        self.antes = self.f.lin.copy()

    def rollback(self):
        self.f.lin = self.antes.copy()


def plano_outubro():
    fonte = fonte_outubro()
    res = carrega_main().roda(fonte, [T("2026-10-13")], PRM, hoje=T("2026-10-14"), log=lambda *a: None)
    plano = cor.monta_plano(res)
    backup = cor.busca_linhas(fonte, plano)
    return fonte, res, {c.fundo: c for c in plano}, plano, backup


def test_plano_outubro():
    _, _, p, plano, backup = plano_outubro()
    biti = p["ITAUBLO66606"]
    assert (biti.nivel, biti.situacao, biti.tipo, biti.contraparte) == (cor.AUTOMATICA, "pronta", "Fund", "-")
    assert biti.delta == pytest.approx(-5_758_872.88, abs=0.01)
    assert biti.pnl_moeda_ativo == pytest.approx(10_534_266.94)
    assert biti.origem == [(T("2026-10-12"), "3GALABIT", "CotaExternaD0.py")]
    b5 = p["ITAUIMA5P2070"]
    assert (b5.nivel, b5.situacao, b5.ativo, b5.tipo) == (cor.AUTOMATICA, "pronta", "OUTRAS_DESPESAS", "Despesa")
    assert b5.delta == pytest.approx(11_526_424.60) and pd.isna(b5.pnl_moeda_ativo)
    fic = p["FICFI53254"]                       # a diferença sai da linha que carrega o PnL, não do CaixaCPROutros
    assert (fic.nivel, fic.situacao, fic.ativo) == (cor.AUTOMATICA, "pronta", "AJUSTE_COMPENSACAO_COTAS")
    assert fic.delta == pytest.approx(-6_208.92)
    novo = p["FICFI54649S1"]
    assert novo.nivel == cor.SEM_SQL and 'date_ref="2026-10-13"' in novo.runproject
    assert "Posicao/SAC/importar_posicao" in novo.runproject
    assert len(backup) == 3 and set(backup["correcao"]) == {1, 2, 4}


def test_script_correcao_e_reversao():
    _, _, p, plano, _ = plano_outubro()
    sql = cor.script_correcao(plano, "13/10/2026")
    ativos = [l for l in sql.splitlines() if l.startswith("UPDATE VW_FUNDOS_POSICAO")]
    assert len(ativos) == 3                                                   # as três automáticas
    assert "AND ABS(pnl_moeda_ativo - (10534266.94)) < 0.01" in sql            # trava no valor do diagnóstico
    assert "-- DELETE FROM FUNDOS_DADOS_ATIVOS WHERE date = '2026-10-12' AND codigo_IAM_ativo = '3GALABIT'" in sql
    assert sql.rstrip().splitlines()[-1].startswith("ROLLBACK TRANSACTION;")
    assert sql.count("('2026-10-13', ") == 3                                   # conferência dos três fundos
    rev = cor.script_reversao(plano, "13/10/2026")
    assert "SET pnl_total = 13070809.58" in rev
    assert f"ABS(pnl_total - ({cor._n(13070809.58 + p['ITAUBLO66606'].delta)})) < 0.01" in rev


def test_revisar_sai_comentado():
    _, _, p, plano, _ = plano_outubro()
    p["ITAUBLO66606"].nivel = cor.REVISAR
    sql = cor.script_correcao(plano, "13/10/2026")
    assert sum(l.startswith("UPDATE VW_FUNDOS_POSICAO") for l in sql.splitlines()) == 2
    assert "-- UPDATE VW_FUNDOS_POSICAO" in sql
    assert sum(l.startswith("UPDATE VW_FUNDOS_POSICAO")
               for l in cor.script_correcao(plano, "x", com_revisao=True).splitlines()) == 3


def test_aplica_confere_e_grava_com_sim():
    fonte, _, p, plano, _ = plano_outubro()
    tx = TransacaoFake(fonte)
    log = []
    assert cor.aplica(tx, plano, confirmar=lambda msg: "sim", log=log.append) == "gravado"
    assert tx.commits == 1
    assert p["ITAUBLO66606"].dif_depois == pytest.approx(369.45, abs=0.01)
    assert p["ITAUIMA5P2070"].dif_depois == pytest.approx(362.70, abs=0.01)
    assert p["FICFI53254"].dif_depois == pytest.approx(0.0, abs=0.01)
    assert all(p[f].situacao == "aplicada" for f in ("ITAUBLO66606", "ITAUIMA5P2070", "FICFI53254"))
    # diagnóstico de novo: só sobra o código novo sem posição
    res = carrega_main().roda(fonte, [T("2026-10-13")], PRM, hoje=T("2026-10-14"), log=lambda *a: None)
    assert list(res.resumo["codigo_IAM_fundo"]) == ["FICFI54649S1"]


def test_aplica_sem_confirmacao_desfaz():
    fonte, _, p, plano, _ = plano_outubro()
    antes = fonte.lin.copy()
    tx = TransacaoFake(fonte)
    assert cor.aplica(tx, plano, confirmar=lambda msg: "não", log=lambda *a: None) == "desfeito"
    assert tx.commits == 0
    pd.testing.assert_frame_equal(fonte.lin, antes)
    assert p["ITAUBLO66606"].situacao == "desfeita (sem confirmação)"


def test_aplica_desfaz_se_a_linha_mudou_depois_do_diagnostico():
    fonte, _, p, plano, _ = plano_outubro()
    l = fonte.lin
    l.loc[(l["codigo_IAM_fundo"] == "ITAUBLO66606") & (l["codigo_IAM_ativo"] == "3GALABIT")
          & (l["date"] == T("2026-10-13")), "pnl_total"] += 100.0           # alguém reprocessou
    antes = fonte.lin.copy()
    tx = TransacaoFake(fonte)
    perguntou = []
    assert cor.aplica(tx, plano, confirmar=perguntou.append, log=lambda *a: None) == "desfeito"
    assert perguntou == [] and tx.commits == 0
    pd.testing.assert_frame_equal(fonte.lin, antes)
    assert p["ITAUBLO66606"].situacao.startswith("não aplicada: 0 linha(s)")


def test_corrige_grava_os_arquivos_e_a_aba(tmp_path, monkeypatch):
    bm = carrega_main()
    fonte = fonte_outubro()
    res = bm.roda(fonte, [T("2026-10-13")], PRM, hoje=T("2026-10-14"), log=lambda *a: None)
    monkeypatch.setattr(cor, "TransacaoSQL", lambda conn: TransacaoFake(fonte))
    out = bm.corrige(fonte, res, str(tmp_path), "20261013_INDEXADOS", aplicar=True,
                     confirmar=lambda msg: "SIM", log=lambda *a: None)
    assert out["estado"] == "gravado"
    assert set(out["arquivos"]) == {"correcao", "reverter", "backup"}
    assert all(os.path.exists(a) for a in out["arquivos"].values())
    assert open(out["arquivos"]["correcao"], encoding="utf-8-sig").read().count("UPDATE VW_FUNDOS_POSICAO") == 3
    import relatorio
    caminho = relatorio.grava_excel(res, str(tmp_path), "batimento_20261013_INDEXADOS.xlsx")
    corr = pd.read_excel(caminho, sheet_name="Correções")
    assert list(corr["Situação"].value_counts().items()) == [("aplicada", 3)]
    assert corr.loc[corr["Fundo"] == "ITAUBLO66606", "Diferença depois (R$)"].iloc[0] == pytest.approx(369.45, abs=0.01)


def test_saldo_em_linha_com_saldo_vai_para_revisao():
    from types import SimpleNamespace
    import detectores as det
    d, f = T("2026-10-20"), "FUNDOX"
    oc = det.tabela_ocorrencias([
        det.ocorrencia(d, f, "LINHA_EXPLICA", "explica", "ACAO_X", -5000.0, -10.0, linha=("Equity", "-"),
                       sem_saldo=False),
        det.ocorrencia(d, f, "DIFERENCA_IGUAL_SALDO", "explica", "CaixaCPROutros", -5010.0, 0.0,
                       linha=("CaixaCPROutros", "-"))])
    resumo = pd.DataFrame([{"date": d, "codigo_IAM_fundo": f, "verificacao": "DIFERENCA_IGUAL_SALDO",
                            "diagnostico": "Diferença igual a um saldo", "status": "explica",
                            "ativo": "CaixaCPROutros", "ajuste_rs": -5010.0, "residuo_rs": 0.0, "dif_rs": -5010.0,
                            "acao": ""}])
    tri = pd.DataFrame([{"date": d, "codigo_IAM_fundo": f, "classe": "A", "pl": 1e6}])
    plano = cor.monta_plano(SimpleNamespace(resumo=resumo, ocorrencias=oc, triagem=tri))
    assert len(plano) == 1
    assert (plano[0].ativo, plano[0].nivel) == ("ACAO_X", cor.REVISAR)
    assert "A linha tem saldo" in plano[0].nota
