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
FILTRO_FUNDOS = " AND p.codigo_IAM_fundo IN ({lista})"   # entra no {fundos} das consultas que aceitam lista de fundos


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

    def ler(self, sql, params=(), nome=""):
        params = tuple(_param(p) for p in params)
        if self.verboso:                             # o nome antes: se travar, já se sabe em qual consulta
            print(f"    {nome or ' '.join(sql.split())[:100]} ...", end="", flush=True)
        t0 = time.perf_counter()
        try:
            df = pd.read_sql(sql, self._get_engine(), params=params or None)
        except Exception:
            if self.verboso:
                print(" erro", flush=True)
            raise
        if self.verboso:
            print(f" {time.perf_counter() - t0:.1f} s, {len(df)} linhas", flush=True)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        return df

    def _em_lotes(self, sql_fmt, fixos_antes, lista, fixos_depois=(), nome="", unicas=False):
        """Roda sql_fmt (com {lista}) em lotes da lista e junta os resultados. unicas: tira as linhas repetidas
        entre lotes (consultas em que a lista só filtra uma subconsulta)."""
        lista = list(dict.fromkeys(lista))
        lotes = [lista[i:i + LOTE] for i in range(0, len(lista), LOTE)]
        partes = [self.ler(sql_fmt.format(lista=_marcadores(len(lote))),
                           list(fixos_antes) + list(lote) + list(fixos_depois),
                           nome + (f" (lote {k}/{len(lotes)})" if len(lotes) > 1 else ""))
                  for k, lote in enumerate(lotes, start=1)]
        if not partes:
            return pd.DataFrame()
        df = pd.concat(partes, ignore_index=True)
        return df.drop_duplicates(ignore_index=True) if unicas and len(partes) > 1 else df

    def _por_fundos(self, sql_fmt, fixos, fundos, nome):
        """sql_fmt com {fundos} no fim da subconsulta da posição: sem lista, todos os fundos; com lista, só os
        ativos desses fundos (em lotes)."""
        if fundos is None:
            return self.ler(sql_fmt.format(fundos=""), fixos, nome)
        return self._em_lotes(sql_fmt.format(fundos=FILTRO_FUNDOS), fixos, fundos, nome=nome, unicas=True)

    # ── calendário e triagem ────────────────────────────────────────────────────────────────────────────────

    def datas_com_cota(self, de, ate):
        """Datas com cota e quantos fundos têm cota em cada uma (para ignorar datas com poucos fundos)."""
        return self.ler("""
            SELECT c.date, COUNT(DISTINCT c.codigo_IAM_fundo) AS fundos
            FROM VW_FUNDOS_COTAS_PL c WITH (NOLOCK)
            WHERE c.date BETWEEN ? AND ?
            GROUP BY c.date
            ORDER BY c.date""", [de, ate], "datas com cota")

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
        return self.ler(sql, params, "cotas")

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
        return self.ler(sql, params, "posição por fundo")

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
        return self._em_lotes(sql, datas, fundos, nome=f"linhas da posição ({len(fundos)} fundo(s))")

    def linhas_alvo(self, data, fundo, ativo):
        """Todas as colunas das linhas de um ativo num fundo e data (as que a correção vai mudar e o backup)."""
        return self.ler("""
            SELECT p.*
            FROM VW_FUNDOS_POSICAO p WITH (NOLOCK)
            WHERE p.date = ? AND p.codigo_IAM_fundo = ? AND p.codigo_IAM_ativo = ?""", [data, fundo, ativo],
                        f"registros de {fundo}/{ativo}")

    def conexao_escrita(self):
        """Conexão pyodbc (autocommit desligado) para o --aplicar."""
        import sql_connection
        conn = sql_connection.get_connection()
        if conn.connection is None:
            raise RuntimeError("sem conexão pyodbc com o DBSX337 (veja a mensagem acima)")
        return conn.connection

    def ajustes_manuais(self, de, ate, fundos=None):
        return self._por_fundos("""
            SELECT p.date, p.codigo_IAM_fundo, p.codigo_IAM_ativo, SUM(p.pnl_total) AS pnl_total,
                   MAX(p.log_last_user) AS log_last_user, MAX(p.log_last_processamento) AS log_last_processamento
            FROM VW_FUNDOS_POSICAO p WITH (NOLOCK)
            WHERE p.date BETWEEN ? AND ? AND p.contraparte = 'ajuste_pnl'{fundos}
            GROUP BY p.date, p.codigo_IAM_fundo, p.codigo_IAM_ativo""", [de, ate], fundos, "ajustes manuais")

    # ── tabela de preços ────────────────────────────────────────────────────────────────────────────────────
    # As consultas com `fundos` olham só os ativos da posição desses fundos (None: de todos os fundos). As que
    # recebem `ativos` leem a lista pronta, sem subconsulta.

    COLS_PRECO = """f.date, f.codigo_IAM_ativo, f.preco_limpo, f.preco_limpo_d1, f.pnl_moeda_ativo,
                    f.log_script_from, f.log_last_user, f.log_last_processamento"""

    def precos_entre(self, apos, antes, data_posicao, fundos=None, scripts=None):
        """Linhas com apos < date < antes e variação diferente de zero, de ativos na posição de data_posicao; com
        `scripts`, só as linhas desses scripts."""
        so_scripts = f" AND f.log_script_from IN ({_marcadores(len(scripts))})" if scripts else ""
        return self._por_fundos(f"""
            SELECT {self.COLS_PRECO}
            FROM FUNDOS_DADOS_ATIVOS f WITH (NOLOCK)
            WHERE f.date > ? AND f.date < ?
              AND f.pnl_moeda_ativo <> 0{so_scripts}
              AND f.codigo_IAM_ativo IN (SELECT p.codigo_IAM_ativo FROM VW_FUNDOS_POSICAO p WITH (NOLOCK)
                                         WHERE p.date = ?{{fundos}})""",
                                [apos, antes, *(scripts or ()), data_posicao], fundos,
                                f"preços de {_param(apos):%d/%m} a {_param(antes):%d/%m} (exclusive)")

    def precos_do_dia(self, data, ativos):
        """Linhas de `data` dos ativos da lista."""
        return self._em_lotes(f"""
            SELECT {self.COLS_PRECO}
            FROM FUNDOS_DADOS_ATIVOS f WITH (NOLOCK)
            WHERE f.date = ? AND f.codigo_IAM_ativo IN ({{lista}})""", [data], ativos,
                              nome=f"preços do dia ({len(ativos)} ativo(s))")

    SQL_POS_ATIVOS = f"""
        SELECT p.date, p.codigo_IAM_fundo, p.codigo_IAM_ativo,
               SUM(CASE WHEN {LINHA_ATIVO} THEN p.quantidade END)          AS quantidade,
               SUM(CASE WHEN {LINHA_ATIVO} THEN p.quantidade_abertura END) AS quantidade_abertura,
               MAX(p.preco_cambio) AS preco_cambio, MAX(p.moeda_ativo) AS moeda_ativo,
               SUM(CASE WHEN {LINHA_ATIVO} THEN p.pnl_moeda_ativo END)     AS pnl_moeda_ativo,
               SUM(CASE WHEN p.contraparte = 'ajuste_pnl' THEN p.pnl_total ELSE 0 END) AS pnl_ajuste_manual
        FROM VW_FUNDOS_POSICAO p WITH (NOLOCK)
        WHERE p.date = ? AND p.codigo_IAM_ativo IN ({{lista}})
        GROUP BY p.date, p.codigo_IAM_fundo, p.codigo_IAM_ativo"""

    def posicao_ativos_lista(self, data, ativos):
        """Posição em `data` dos ativos da lista, em todos os fundos (quem chama filtra o escopo)."""
        return self._em_lotes(self.SQL_POS_ATIVOS, [data], ativos, nome=f"posição de {len(ativos)} ativo(s)")

    def precos_anomalos(self, apos, ate, data_posicao, salto, fundos=None):
        """Preço zero ou variação acima de `salto`, de ativos em carteira (fundos e ações) em data_posicao."""
        return self._por_fundos(f"""
            SELECT {self.COLS_PRECO}
            FROM FUNDOS_DADOS_ATIVOS f WITH (NOLOCK)
            WHERE f.date > ? AND f.date <= ?
              AND (f.preco_limpo = 0
                   OR (f.preco_limpo_d1 > 0 AND ABS(f.preco_limpo - f.preco_limpo_d1) > ? * f.preco_limpo_d1))
              AND f.codigo_IAM_ativo IN (SELECT p.codigo_IAM_ativo FROM VW_FUNDOS_POSICAO p WITH (NOLOCK)
                                         WHERE p.date = ? AND p.tipo IN ({_marcadores(len(TIPOS_PRECO))}){{fundos}})""",
                                [apos, ate, salto, data_posicao, *TIPOS_PRECO], fundos, "preços zero ou com salto")

    def precos_duplicados(self, apos, ate, data_posicao, fundos=None):
        """Mais de uma linha no mesmo dia e ativo, com preços diferentes."""
        return self._por_fundos(f"""
            SELECT f.date, f.codigo_IAM_ativo, COUNT(*) AS linhas,
                   MIN(f.preco_limpo) AS preco_min, MAX(f.preco_limpo) AS preco_max,
                   MIN(f.log_script_from) AS script_1, MAX(f.log_script_from) AS script_2
            FROM FUNDOS_DADOS_ATIVOS f WITH (NOLOCK)
            WHERE f.date > ? AND f.date <= ?
              AND f.codigo_IAM_ativo IN (SELECT p.codigo_IAM_ativo FROM VW_FUNDOS_POSICAO p WITH (NOLOCK)
                                         WHERE p.date = ? AND p.tipo IN ({_marcadores(len(TIPOS_PRECO))}){{fundos}})
            GROUP BY f.date, f.codigo_IAM_ativo
            HAVING COUNT(*) > 1 AND MAX(f.preco_limpo) - MIN(f.preco_limpo) > 0.0001 * ABS(MAX(f.preco_limpo))""",
                                [apos, ate, data_posicao, *TIPOS_PRECO], fundos, "preços duplicados")
