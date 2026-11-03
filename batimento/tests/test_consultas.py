# As consultas do consultas.FonteSQL sem banco: cada marcador ? tem o seu parâmetro, nenhum {} sobra no SQL e as
# listas grandes vão em lotes. A sintaxe foi conferida à parte com o parser do SSMS (ScriptDom).
import pandas as pd
import pytest

import consultas

T = pd.Timestamp


class Captura(consultas.FonteSQL):
    def __init__(self):
        super().__init__()
        self.lidas = []

    def ler(self, sql, params=(), nome=""):
        self.lidas.append((sql, list(params), nome))
        return pd.DataFrame({"codigo_IAM_ativo": ["X"]})


def todas(f):
    d, p = T("2026-10-13"), T("2026-10-09")
    f.datas_com_cota(p, d)
    f.cotas(p, d, mesa="INDEXADOS", fundos=["A", "B"])
    f.posicao_resumo(p, d, mesa="INDEXADOS", fundos=["A"])
    f.posicao_linhas(["A", "B", "C"], [d, p])
    f.linhas_alvo(d, "A", "X")
    for fundos in (None, ["A", "B"]):
        f.ajustes_manuais(d, d, fundos)
        f.precos_entre(p, d, d, fundos=fundos)
        f.precos_entre(p, d, d, fundos=fundos, scripts=("CotaExternaD0.py",))
        f.precos_anomalos(p, d, d, 0.3, fundos=fundos)
        f.precos_duplicados(p, d, d, fundos=fundos)
    f.precos_do_dia(d, ["X", "Y"])
    f.posicao_ativos_lista(d, ["X", "Y"])


def test_marcadores_e_parametros():
    f = Captura()
    todas(f)
    assert len(f.lidas) == 17
    for sql, params, nome in f.lidas:
        assert sql.count("?") == len(params), nome
        assert "{" not in sql and "}" not in sql, nome
        assert nome
    # com lista de fundos, o filtro entra na subconsulta da posição; sem lista, não
    entre = [sql for sql, _, nome in f.lidas if nome.startswith("preços de ")]
    assert ["codigo_IAM_fundo IN" in s for s in entre] == [False, False, True, True]
    assert "log_script_from IN (?)" in entre[1] and "log_script_from IN (?)" in entre[3]


def test_listas_grandes_em_lotes_sem_repetir_linhas():
    f = Captura()
    fundos = [f"F{i}" for i in range(consultas.LOTE + 10)]
    df = f.precos_anomalos(T("2026-10-09"), T("2026-10-13"), T("2026-10-13"), 0.3, fundos=fundos)
    assert [n for _, _, n in f.lidas] == ["preços zero ou com salto (lote 1/2)", "preços zero ou com salto (lote 2/2)"]
    assert [len(p) for _, p, _ in f.lidas] == [4 + 2 + consultas.LOTE, 4 + 2 + 10]
    assert len(df) == 1                       # o mesmo ativo nos dois lotes vira uma linha


@pytest.mark.parametrize("fundos", [None, ["A"]])
def test_ajustes_manuais_com_e_sem_fundos(fundos):
    f = Captura()
    f.ajustes_manuais(T("2026-10-13"), T("2026-10-13"), fundos)
    sql, params, _ = f.lidas[0]
    assert ("codigo_IAM_fundo IN (?)" in sql) == bool(fundos) and len(params) == 2 + len(fundos or [])
