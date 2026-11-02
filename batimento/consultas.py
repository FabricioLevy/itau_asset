# ─────────────────────────────────────────────
# batimento/consultas.py
# Leituras do DBSX337 para o batimento (todas WITH (NOLOCK), parâmetros com ?). Cada método devolve um
# DataFrame no formato que o detectores.py espera; a FonteFake dos testes devolve os mesmos formatos sem banco.
# ─────────────────────────────────────────────

import time
from datetime import datetime

import pandas as pd

LOTE = 900                      # itens por lista IN (o SQL Server aceita até 2.100 parâmetros por consulta)
TIPOS_PRECO = ("Fund", "Equity")  # tipos de ativo olhados na tabela de preços (preço zero, salto, duplicado)
LINHA_ATIVO = "ISNULL(p.contraparte, '-') <> 'ajuste_pnl' AND ISNULL(p.tipo, '') NOT LIKE 'Caixa%'"


def _marcadores(n):
    return ", ".join("?" * n)


def _param(x):
    return pd.Timestamp(x).date() if isinstance(x, (pd.Timestamp, datetime)) else x


class FonteSQL:
    def __init__(self, verboso=False):
        self.verboso = verboso
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            import sql_connection
            conn = sql_connection.get_connection()
            if conn.engine is None:
                raise RuntimeError("sem conexão com o DBSX337 (veja a mensagem acima)")
            self._engine = conn.engine
        return self._engine

    def ler(self, sql, params=()):
        params = tuple(_param(p) for p in params)
        t0 = time.perf_counter()
        df = pd.read_sql(sql, self._get_engine(), params=params or None)
        if self.verboso:
            print(f"    [{time.perf_counter() - t0:6.1f}s] {len(df):>8} linhas  {' '.join(sql.split())[:100]}")
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        return df

    def _em_lotes(self, sql_fmt, fixos_antes, lista, fixos_depois=()):
        """Roda sql_fmt (com {lista}) em lotes da lista e junta os resultados."""
        lista = list(dict.fromkeys(lista))
        partes = [self.ler(sql_fmt.format(lista=_marcadores(len(lote))),
                           list(fixos_antes) + list(lote) + list(fixos_depois))
                  for lote in (lista[i:i + LOTE] for i in range(0, len(lista), LOTE))]
        return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()

    # ── calendário e triagem ────────────────────────────────────────────────────────────────────────────────

    def datas_com_cota(self, de, ate):
        """Datas com cota e quantos fundos têm cota em cada uma (para ignorar datas com poucos fundos)."""
        return self.ler("""
            SELECT c.date, COUNT(DISTINCT c.codigo_IAM_fundo) AS fundos
            FROM VW_FUNDOS_COTAS_PL c WITH (NOLOCK)
            WHERE c.date BETWEEN ? AND ?
            GROUP BY c.date
            ORDER BY c.date""", [de, ate])

    def cotas(self, de, ate, mesa=None, fundos=None):
        """Todas as classes de cada fundo e data (detectores.escolhe_classe escolhe uma)."""
        sql = """
            SELECT c.date, c.codigo_IAM_fundo, c.classe, c.mesa_gestao, c.last_patrimonio,
                   c.fundo_pnl, c.fundo_pnl_perc
            FROM VW_FUNDOS_COTAS_PL c WITH (NOLOCK)
            WHERE c.date BETWEEN ? AND ?"""
        params = [de, ate]
        if mesa:
            sql += " AND c.mesa_gestao LIKE ?"
            params.append(f"%{mesa}%")
        if fundos:
            sql += f" AND c.codigo_IAM_fundo IN ({_marcadores(len(fundos))})"
            params += list(fundos)
        return self.ler(sql, params)

    def posicao_resumo(self, de, ate, mesa=None, fundos=None):
        """PnL da posição por fundo e data, com o PnL da OUTRAS_DESPESAS e o dos ajustes manuais à parte."""
        sql = """
            SELECT p.date, p.codigo_IAM_fundo,
                   COUNT(*)                      AS linhas,
                   SUM(p.pnl_total)              AS pnl_total,
                   SUM(p.pnl_total_perc) * 10000 AS pnl_bps,
                   SUM(CASE WHEN p.codigo_IAM_ativo = 'OUTRAS_DESPESAS' THEN p.pnl_total ELSE 0 END) AS pnl_outras_despesas,
                   SUM(CASE WHEN p.contraparte = 'ajuste_pnl' THEN p.pnl_total ELSE 0 END)           AS pnl_ajuste_manual
            FROM VW_FUNDOS_POSICAO p WITH (NOLOCK)
            WHERE p.date BETWEEN ? AND ?"""
        params = [de, ate]
        if mesa:
            sql += """
              AND p.codigo_IAM_fundo IN (SELECT c.codigo_IAM_fundo FROM VW_FUNDOS_COTAS_PL c WITH (NOLOCK)
                                         WHERE c.date BETWEEN ? AND ? AND c.mesa_gestao LIKE ?)"""
            params += [de, ate, f"%{mesa}%"]
        if fundos:
            sql += f" AND p.codigo_IAM_fundo IN ({_marcadores(len(fundos))})"
            params += list(fundos)
        sql += " GROUP BY p.date, p.codigo_IAM_fundo"
        return self.ler(sql, params)

    # ── linhas da posição dos fundos marcados ───────────────────────────────────────────────────────────────

    def posicao_linhas(self, fundos, datas):
        """Uma linha por (data, fundo, ativo, contraparte, tipo), nas datas pedidas."""
        datas = sorted({pd.Timestamp(x).date() for x in datas})
        sql = f"""
            SELECT p.date, p.codigo_IAM_fundo, p.codigo_IAM_ativo, ISNULL(p.contraparte, '-') AS contraparte, p.tipo,
                   MAX(p.ativo) AS ativo, MAX(p.moeda_ativo) AS moeda_ativo,
                   SUM(p.quantidade) AS quantidade, SUM(p.quantidade_abertura) AS quantidade_abertura,
                   MAX(p.preco_limpo) AS preco_limpo, MAX(p.preco_limpo_d1) AS preco_limpo_d1,
                   MAX(p.preco_cambio) AS preco_cambio,
                   SUM(p.total) AS total, SUM(p.total_moeda_fundo) AS total_moeda_fundo,
                   SUM(p.pnl_total) AS pnl_total, SUM(p.pnl_moeda_ativo) AS pnl_moeda_ativo,
                   SUM(p.pnl_moeda_ativo_operacao) AS pnl_operacao, SUM(p.pnl_cambio) AS pnl_cambio,
                   MAX(p.last_patrimonio) AS last_patrimonio,
                   MAX(p.log_last_user) AS log_last_user, MAX(p.log_last_processamento) AS log_last_processamento
            FROM VW_FUNDOS_POSICAO p WITH (NOLOCK)
            WHERE p.date IN ({_marcadores(len(datas))}) AND p.codigo_IAM_fundo IN ({{lista}})
            GROUP BY p.date, p.codigo_IAM_fundo, p.codigo_IAM_ativo, ISNULL(p.contraparte, '-'), p.tipo"""
        return self._em_lotes(sql, datas, fundos)

    def ajustes_manuais(self, de, ate):
        return self.ler("""
            SELECT p.date, p.codigo_IAM_fundo, p.codigo_IAM_ativo, SUM(p.pnl_total) AS pnl_total,
                   MAX(p.log_last_user) AS log_last_user, MAX(p.log_last_processamento) AS log_last_processamento
            FROM VW_FUNDOS_POSICAO p WITH (NOLOCK)
            WHERE p.date BETWEEN ? AND ? AND p.contraparte = 'ajuste_pnl'
            GROUP BY p.date, p.codigo_IAM_fundo, p.codigo_IAM_ativo""", [de, ate])

    # ── tabela de preços ────────────────────────────────────────────────────────────────────────────────────

    COLS_PRECO = """f.date, f.codigo_IAM_ativo, f.preco_limpo, f.preco_limpo_d1, f.pnl_moeda_ativo,
                    f.log_script_from, f.log_last_user, f.log_last_processamento"""

    def precos_entre(self, apos, antes, data_posicao):
        """Linhas com apos < date < antes e variação diferente de zero, de ativos em carteira em data_posicao."""
        return self.ler(f"""
            SELECT {self.COLS_PRECO}
            FROM FUNDOS_DADOS_ATIVOS f WITH (NOLOCK)
            WHERE f.date > ? AND f.date < ?
              AND f.pnl_moeda_ativo <> 0
              AND f.codigo_IAM_ativo IN (SELECT p.codigo_IAM_ativo FROM VW_FUNDOS_POSICAO p WITH (NOLOCK)
                                         WHERE p.date = ?)""", [apos, antes, data_posicao])

    def precos_do_dia(self, data, apos, antes):
        """Linhas de `data` dos ativos que têm linha com variação entre apos e antes."""
        return self.ler(f"""
            SELECT {self.COLS_PRECO}
            FROM FUNDOS_DADOS_ATIVOS f WITH (NOLOCK)
            WHERE f.date = ?
              AND f.codigo_IAM_ativo IN (SELECT g.codigo_IAM_ativo FROM FUNDOS_DADOS_ATIVOS g WITH (NOLOCK)
                                         WHERE g.date > ? AND g.date < ? AND g.pnl_moeda_ativo <> 0)""",
                        [data, apos, antes])

    SQL_POS_ATIVOS = f"""
        SELECT p.date, p.codigo_IAM_fundo, p.codigo_IAM_ativo,
               SUM(CASE WHEN {LINHA_ATIVO} THEN p.quantidade END)          AS quantidade,
               SUM(CASE WHEN {LINHA_ATIVO} THEN p.quantidade_abertura END) AS quantidade_abertura,
               MAX(p.preco_cambio) AS preco_cambio, MAX(p.moeda_ativo) AS moeda_ativo,
               SUM(CASE WHEN {LINHA_ATIVO} THEN p.pnl_moeda_ativo END)     AS pnl_moeda_ativo,
               SUM(CASE WHEN p.contraparte = 'ajuste_pnl' THEN p.pnl_total ELSE 0 END) AS pnl_ajuste_manual
        FROM VW_FUNDOS_POSICAO p WITH (NOLOCK)
        WHERE p.date = ? AND {{filtro}}
        GROUP BY p.date, p.codigo_IAM_fundo, p.codigo_IAM_ativo"""

    def posicao_ativos_entre(self, data, apos, antes):
        """Posição em `data` dos ativos com linha de preço com variação entre apos e antes."""
        filtro = """p.codigo_IAM_ativo IN (SELECT f.codigo_IAM_ativo FROM FUNDOS_DADOS_ATIVOS f WITH (NOLOCK)
                                           WHERE f.date > ? AND f.date < ? AND f.pnl_moeda_ativo <> 0)"""
        return self.ler(self.SQL_POS_ATIVOS.format(filtro=filtro), [data, apos, antes])

    def posicao_ativos_lista(self, data, ativos):
        sql = self.SQL_POS_ATIVOS.format(filtro="p.codigo_IAM_ativo IN ({lista})")
        return self._em_lotes(sql, [data], ativos)

    def precos_anomalos(self, apos, ate, data_posicao, salto):
        """Preço zero ou variação acima de `salto`, de ativos em carteira (fundos e ações) em data_posicao."""
        return self.ler(f"""
            SELECT {self.COLS_PRECO}
            FROM FUNDOS_DADOS_ATIVOS f WITH (NOLOCK)
            WHERE f.date > ? AND f.date <= ?
              AND f.codigo_IAM_ativo IN (SELECT p.codigo_IAM_ativo FROM VW_FUNDOS_POSICAO p WITH (NOLOCK)
                                         WHERE p.date = ? AND p.tipo IN ({_marcadores(len(TIPOS_PRECO))}))
              AND (f.preco_limpo = 0
                   OR (f.preco_limpo_d1 > 0 AND ABS(f.preco_limpo - f.preco_limpo_d1) > ? * f.preco_limpo_d1))""",
                        [apos, ate, data_posicao, *TIPOS_PRECO, salto])

    def precos_duplicados(self, apos, ate, data_posicao):
        """Mais de uma linha no mesmo dia e ativo, com preços diferentes."""
        return self.ler(f"""
            SELECT f.date, f.codigo_IAM_ativo, COUNT(*) AS linhas,
                   MIN(f.preco_limpo) AS preco_min, MAX(f.preco_limpo) AS preco_max,
                   MIN(f.log_script_from) AS script_1, MAX(f.log_script_from) AS script_2
            FROM FUNDOS_DADOS_ATIVOS f WITH (NOLOCK)
            WHERE f.date > ? AND f.date <= ?
              AND f.codigo_IAM_ativo IN (SELECT p.codigo_IAM_ativo FROM VW_FUNDOS_POSICAO p WITH (NOLOCK)
                                         WHERE p.date = ? AND p.tipo IN ({_marcadores(len(TIPOS_PRECO))}))
            GROUP BY f.date, f.codigo_IAM_ativo
            HAVING COUNT(*) > 1 AND MAX(f.preco_limpo) - MIN(f.preco_limpo) > 0.0001 * ABS(MAX(f.preco_limpo))""",
                        [apos, ate, data_posicao, *TIPOS_PRECO])
