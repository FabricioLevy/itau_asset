-- ─────────────────────────────────────────────
-- taxa_media/sql/taxa_media.sql
-- Taxa média de aquisição dos papéis de crédito atrelados ao CDI de UM fundo, com os avisos e as pendências.
-- Mesma lógica do taxa_media/__main__.py (doc/taxa_media.md) para os grupos CDI+ e %CDI, para conferir no SSMS.
-- Só CDI: SELIC+, pré, IPCA+ e as cotas de FIDC estão só no Python (aqui ficam fora, com o aviso de indexador).
--
-- Antes de rodar: preencha os parâmetros, @tipos (= aba Tipos do input/fundos.xlsx) e @correcoes (= linhas
-- da aba Correções deste fundo com aplicar = S). Todas as leituras são WITH (NOLOCK).
--
-- Resultados, nesta ordem:
--   1 Parâmetros   fundo, data, fonte, CDI usado e contagens
--   2 Carteira     média por grupo (%CDI em % do CDI, CDI+ em spread) e da carteira (CDI+ equivalente)
--   3 Ativos       taxa média, conferência com a posição, PU e financeiro de cada ativo
--   4 Lotes        cada lote em aberto: boleta casada, taxa da VCRA, taxa usada e de onde ela veio
--   5 Avisos       tudo o que merece conferência, na mesma ordem do script em Python
--   6 Pendências   lotes com boleta inválida ou sem boleta, no formato da aba Correções: preencha a taxa,
--                  troque aplicar para S e cole as linhas na aba
-- ─────────────────────────────────────────────
SET NOCOUNT ON;

DECLARE @fundo   varchar(20) = 'ITAIMOBCDIFII';
DECLARE @data    date        = NULL;      -- NULL = última data da posição do fundo
DECLARE @fonte   varchar(6)  = 'LAKE';    -- taxa dos CDI+: 'LAKE' (boleta do Lake, negociada) ou 'VCRA' (pelo PU pago)
DECLARE @cdi     float       = NULL;      -- CDI % a.a. para converter %CDI em CDI+; NULL = CDIAcumulado
DECLARE @janela  int         = 5;         -- dias entre a compra na VCRA e a data da boleta
DECLARE @tol_pu  float       = 0.0001;    -- PU da boleta x PU da VCRA, para casar sem a mesma quantidade
DECLARE @limite  float       = 50;        -- boleta válida: %CDI >= 50 (% do CDI); CDI+ < 50 (spread)
DECLARE @dias_pu int         = 30;        -- até quantos dias antes da data procurar o último PU com preço
DECLARE @div_cdi float       = 0.25;      -- aviso Boleta x VCRA no CDI+ (p.p. de spread)
DECLARE @div_pct float       = 3;         -- aviso Boleta x VCRA no %CDI (pontos de % do CDI)

-- aba Tipos: RFTP_CD da VCRAOPRF e se entra no cálculo (1 = S)
DECLARE @tipos TABLE (RFTP_CD varchar(10) PRIMARY KEY, incluir bit NOT NULL);
INSERT @tipos VALUES ('CRI-I', 1), ('LTN-O', 0), ('NTN-O', 0), ('LFT O', 0), ('CRIOP', 0), ('CRILA', 0);

-- aba Correções, só as linhas deste fundo com aplicar = S: CD, taxa na convenção do grupo do ativo, motivo
DECLARE @correcoes TABLE (CD varchar(10) PRIMARY KEY, taxa float NOT NULL, motivo varchar(300) NULL);
-- INSERT @correcoes VALUES ('L79492', 109.33, '26A1798621: boleta gravou 9,33 num papel de 101% do CDI');

-- ── data e CDI ──
IF @data IS NULL
    SELECT @data = MAX(date) FROM VW_FUNDOS_POSICAO WITH (NOLOCK) WHERE codigo_IAM_fundo = @fundo;
IF @data IS NULL
BEGIN
    RAISERROR('Fundo sem posição na VW_FUNDOS_POSICAO.', 16, 1);
    RETURN;
END;

DECLARE @cdi_origem varchar(100) = 'informado em @cdi';
IF @cdi IS NULL
    SELECT TOP 1 @cdi = (POWER(1 + pnl_perc, 252E0) - 1) * 100,
                 @cdi_origem = CONCAT('CDIAcumulado da FUNDOS_DADOS_INDICES em ', FORMAT(date, 'dd/MM/yyyy'))
    FROM   FUNDOS_DADOS_INDICES WITH (NOLOCK)
    WHERE  codigo_IAM_indice = 'CDIAcumulado' AND date <= @data AND pnl_perc > 0
    ORDER BY date DESC;
IF @cdi IS NULL OR @cdi NOT BETWEEN 1 AND 50
BEGIN
    RAISERROR('CDI ausente ou fora de 1%% a 50%% a.a.: informe @cdi.', 16, 1);
    RETURN;
END;
DECLARE @c   float = @cdi / 100;
DECLARE @c_d float = POWER(1 + @c, 1E0 / 252) - 1;

DROP TABLE IF EXISTS #vcra, #compras, #lotes, #ativos, #carteira, #avisos;

-- ── 1) movimentos C/V do fundo até a data; escopo = tipo da lista com incluir = 1 e indexador CDI ──
SELECT  v.CD, v.CD_CETIP_SELIC AS codigo, v.ISIN AS isin, v.RFTP_CD AS tipo, v.IDDIR_CD AS indexador,
        v.DT AS data, v.SG_OPERACAO AS op, ABS(v.QT) AS qt, v.VL_PU_OPERACAO AS pu, v.IDDIR_PC AS perc_cdi,
        v.VL_JUROS_EMISSAO AS taxa_emissao, v.VL_JUROSOPER AS taxa_vcra,
        CASE WHEN t.RFTP_CD IS NULL THEN 0 ELSE 1 END AS na_lista,
        CASE WHEN t.incluir = 1 THEN 1 ELSE 0 END AS incluido,
        CASE WHEN LTRIM(v.IDDIR_CD) LIKE 'CDI%' THEN 1 ELSE 0 END AS cdi
INTO    #vcra
FROM    VCRAOPRF v WITH (NOLOCK)
LEFT JOIN @tipos t ON t.RFTP_CD = UPPER(LTRIM(RTRIM(v.RFTP_CD))) COLLATE DATABASE_DEFAULT
WHERE   v.CLCLI_CD = @fundo AND v.DT <= @data AND v.SG_OPERACAO IN ('C', 'V');

-- ── 2) compras no escopo, cada uma com a boleta do mesmo ativo em até @janela dias, pela quantidade ou pelo PU
--       (há boletas com o dobro da quantidade da custódia); prefere a quantidade e a data mais próxima ──
SELECT  c.*, b.data_boleta, b.qt_boleta, b.taxa_boleta, b.casou_por
INTO    #compras
FROM    #vcra c
OUTER APPLY (SELECT TOP 1 o.date_operacao AS data_boleta, o.exec_qt AS qt_boleta, o.exec_taxa AS taxa_boleta,
                    CASE WHEN ABS(o.exec_qt) = c.qt THEN 'quantidade' ELSE 'PU' END AS casou_por
             FROM   FUNDOS_OPERACOES o WITH (NOLOCK)
             WHERE  o.codigo_IAM_fundo = @fundo
               AND  o.codigo_IAM_ativo = c.codigo
               AND  o.date_operacao BETWEEN DATEADD(day, -@janela, c.data) AND DATEADD(day, @janela, c.data)
               AND  (ABS(o.exec_qt) = c.qt OR ABS(o.exec_preco - c.pu) < @tol_pu)
             ORDER BY CASE WHEN ABS(o.exec_qt) = c.qt THEN 0 ELSE 1 END,
                      ABS(DATEDIFF(day, o.date_operacao, c.data))) b
WHERE   c.op = 'C' AND c.incluido = 1 AND c.cdi = 1;

-- ── 3) lotes: compras − vendas do mesmo CD; grupo, boleta válida, taxa usada, correções e VCRA na convenção ──
WITH agg AS (
    SELECT  codigo, CD, MAX(isin) AS isin, MAX(tipo) AS tipo, MAX(indexador) AS indexador, MIN(data) AS dt_compra,
            MAX(perc_cdi) AS perc_cdi, MAX(taxa_emissao) AS taxa_emissao, SUM(qt) AS qt_comprada,
            SUM(qt * pu) / NULLIF(SUM(qt), 0) AS pu_compra,
            SUM(qt * taxa_vcra) / NULLIF(SUM(CASE WHEN taxa_vcra IS NOT NULL THEN qt END), 0) AS taxa_vcra,
            SUM(qt * taxa_boleta) / NULLIF(SUM(CASE WHEN taxa_boleta IS NOT NULL THEN qt END), 0) AS taxa_boleta,
            MIN(data_boleta) AS data_boleta, MIN(casou_por) AS casou_por
    FROM    #compras
    GROUP BY codigo, CD
),
vendas AS (
    SELECT CD, SUM(qt) AS qt_vendida FROM #vcra WHERE op = 'V' AND incluido = 1 AND cdi = 1 GROUP BY CD
),
base AS (
    SELECT  a.*, ISNULL(v.qt_vendida, 0) AS qt_vendida, a.qt_comprada - ISNULL(v.qt_vendida, 0) AS qt_aberta,
            -- CDI+ tem spread de emissão; %CDI tem a emissão no IDDIR_PC (o mesmo grupo em todos os lotes do ativo)
            CASE WHEN MAX(a.taxa_emissao) OVER (PARTITION BY a.codigo) > 0 THEN 'CDI+' ELSE '%CDI' END AS grupo
    FROM    agg a
    LEFT JOIN vendas v ON v.CD = a.CD
),
validada AS (
    SELECT  b.*, x.boleta_ok, x.taxa_vcra_conv,
            CASE WHEN x.boleta_ok = 1 THEN b.taxa_boleta - x.taxa_vcra_conv END AS dif_boleta_vcra
    FROM    base b
    CROSS APPLY (SELECT
        CASE WHEN (b.grupo = '%CDI' AND b.taxa_boleta >= @limite) OR (b.grupo = 'CDI+' AND b.taxa_boleta < @limite)
             THEN 1 ELSE 0 END AS boleta_ok,
        -- no %CDI, o % do CDI que rende o mesmo que IDDIR_PC% do CDI + o spread da VCRA, com CDI flat
        CASE WHEN b.grupo = 'CDI+' THEN b.taxa_vcra
             ELSE ((1 + b.perc_cdi / 100 * @c_d) * POWER(1 + b.taxa_vcra / 100, 1E0 / 252) - 1) / @c_d * 100
        END AS taxa_vcra_conv) x
)
SELECT  v.*,
        CASE WHEN k.CD IS NOT NULL THEN k.taxa
             WHEN v.boleta_ok = 1 AND (v.grupo = '%CDI' OR @fonte <> 'VCRA') THEN v.taxa_boleta
             WHEN v.grupo = 'CDI+' THEN v.taxa_vcra END AS taxa,
        CASE WHEN k.CD IS NOT NULL THEN 'manual'
             WHEN v.boleta_ok = 1 AND (v.grupo = '%CDI' OR @fonte <> 'VCRA') THEN 'Lake'
             WHEN v.grupo = 'CDI+' THEN 'VCRA' ELSE '' END AS fonte_taxa,
        k.motivo AS motivo_correcao
INTO    #lotes
FROM    validada v
LEFT JOIN @correcoes k ON k.CD = v.CD COLLATE DATABASE_DEFAULT AND v.qt_aberta > 0;

-- ── 4) ativos: média dos lotes em aberto ponderada pela quantidade; conferência com a posição; PU e financeiro ──
WITH por_ativo AS (
    SELECT  codigo, MAX(isin) AS isin, MAX(tipo) AS tipo, MAX(grupo) AS grupo, MAX(perc_cdi) AS perc_cdi,
            MAX(taxa_emissao) AS taxa_emissao, COUNT(*) AS n_lotes, SUM(1 - boleta_ok) AS n_sem_boleta,
            SUM(CASE WHEN fonte_taxa = 'manual' THEN 1 ELSE 0 END) AS n_manual,
            SUM(CASE WHEN taxa IS NULL THEN 1 ELSE 0 END) AS n_sem_taxa,
            SUM(qt_aberta) AS qt_lotes,
            SUM(qt_aberta * taxa_vcra_conv)
              / NULLIF(SUM(CASE WHEN taxa_vcra_conv IS NOT NULL THEN qt_aberta END), 0) AS taxa_vcra,
            SUM(qt_aberta * taxa) / NULLIF(SUM(CASE WHEN taxa IS NOT NULL THEN qt_aberta END), 0) AS taxa_media
    FROM    #lotes
    WHERE   qt_aberta > 0
    GROUP BY codigo
),
pos AS (              -- quantidade na data, só linhas com ISIN (tira compromissadas e caixa)
    SELECT  codigo_IAM_ativo AS codigo, MAX(isin) AS isin, SUM(quantidade) AS qt_posicao
    FROM    VW_FUNDOS_POSICAO WITH (NOLOCK)
    WHERE   codigo_IAM_fundo = @fundo AND date = @data AND tipo = 'Fixed Income' AND isin IS NOT NULL
    GROUP BY codigo_IAM_ativo
),
pu AS (               -- PU do último dia com preço (total) até a data
    SELECT  codigo, dt_pu, total / NULLIF(quantidade, 0) AS pu
    FROM   (SELECT codigo_IAM_ativo AS codigo, date AS dt_pu, SUM(total) AS total, SUM(quantidade) AS quantidade,
                   ROW_NUMBER() OVER (PARTITION BY codigo_IAM_ativo ORDER BY date DESC) AS rn
            FROM   VW_FUNDOS_POSICAO WITH (NOLOCK)
            WHERE  codigo_IAM_fundo = @fundo AND tipo = 'Fixed Income' AND total IS NOT NULL
              AND  date BETWEEN DATEADD(day, -@dias_pu, @data) AND @data
            GROUP BY codigo_IAM_ativo, date) x
    WHERE   rn = 1
)
SELECT  COALESCE(a.codigo, p.codigo) AS codigo, COALESCE(a.isin, p.isin) AS isin, a.tipo, a.grupo, a.perc_cdi,
        a.taxa_emissao, a.n_lotes, a.n_sem_boleta, a.n_manual, a.n_sem_taxa, a.qt_lotes, p.qt_posicao,
        ISNULL(a.qt_lotes, 0) - ISNULL(p.qt_posicao, 0) AS dif_qt, a.taxa_vcra, a.taxa_media,
        CASE a.grupo WHEN 'CDI+' THEN a.taxa_media
                     WHEN '%CDI' THEN (POWER(1 + a.taxa_media / 100 * @c_d, 252) / (1 + @c) - 1) * 100
        END AS taxa_cdi_mais,
        u.pu, u.dt_pu, a.qt_lotes * u.pu AS financeiro
INTO    #ativos
FROM    por_ativo a
FULL JOIN pos p ON p.codigo = a.codigo
LEFT JOIN pu u ON u.codigo = COALESCE(a.codigo, p.codigo);

-- ── 5) carteira: ponderada pelo financeiro; taxa_media na unidade do grupo, total em CDI+ equivalente ──
SELECT  CASE WHEN GROUPING(grupo) = 1 THEN 'CARTEIRA' ELSE grupo END AS grupo,
        COUNT(*) AS n_ativos, SUM(financeiro) AS financeiro,
        CASE WHEN GROUPING(grupo) = 0 THEN SUM(financeiro * taxa_media) / SUM(financeiro) END AS taxa_media,
        SUM(financeiro * taxa_cdi_mais) / SUM(financeiro) AS taxa_cdi_mais
INTO    #carteira
FROM    #ativos
WHERE   financeiro IS NOT NULL AND taxa_media IS NOT NULL
GROUP BY ROLLUP (grupo);

-- ── 6) avisos ──
CREATE TABLE #avisos (ordem int, aviso varchar(30), ativo varchar(250), lote varchar(10), detalhe varchar(500));

INSERT #avisos                                   -- soma dos lotes ≠ posição
SELECT  1, 'Quantidade', codigo, '',
        CONCAT('lotes ', FORMAT(qt_lotes, 'N0', 'pt-BR'), ' × posição ', ISNULL(FORMAT(qt_posicao, 'N0', 'pt-BR'), 'nada'),
               ' em ', FORMAT(@data, 'dd/MM/yyyy'))
FROM    #ativos
WHERE   qt_lotes IS NOT NULL AND ABS(dif_qt) > 1e-6;

INSERT #avisos                                   -- na posição sem lote: fora do escopo (tipo ou indexador) ou sem lote
SELECT  CASE WHEN f.motivo IS NULL THEN 2 ELSE 3 END, CASE WHEN f.motivo IS NULL THEN 'Sem lote' ELSE 'Fora do escopo' END,
        a.codigo, '',
        CONCAT(FORMAT(a.qt_posicao, 'N0', 'pt-BR'), ' na posição', ISNULL('; ' + f.motivo, ' sem lote em aberto na VCRA'))
FROM    #ativos a
OUTER APPLY (SELECT TOP 1
                CASE WHEN v.incluido = 0 THEN CONCAT('na VCRA como ', v.tipo, ', tipo fora do cálculo')
                     ELSE CONCAT('indexador ', v.indexador, ': só entram papéis atrelados ao CDI') END AS motivo
             FROM   #vcra v
             WHERE  v.codigo = a.codigo AND (v.incluido = 0 OR v.cdi = 0)
             ORDER BY v.incluido DESC) f
WHERE   a.qt_lotes IS NULL;

INSERT #avisos                                   -- tipo da VCRA que não está em @tipos
SELECT  4, 'Tipo novo', '', '',
        CONCAT('RFTP_CD ', ISNULL(tipo, '(vazio)'), ' (indexador ', ISNULL(MIN(indexador), 'vazio'),
               CASE WHEN MIN(indexador) <> MAX(indexador) THEN CONCAT(' a ', MAX(indexador)) ELSE '' END, '; ', COUNT(*),
               CASE WHEN COUNT(*) > 1 THEN ' movimentos' ELSE ' movimento' END, ') não está em @tipos: ficou fora')
FROM    #vcra
WHERE   na_lista = 0
GROUP BY tipo;

INSERT #avisos                                   -- ativo fora das médias de grupo e carteira
SELECT 5, 'Fora da média', codigo, '', 'nenhum lote com taxa' FROM #ativos WHERE qt_lotes IS NOT NULL AND taxa_media IS NULL
UNION ALL
SELECT 5, 'Fora da média', codigo, '', CONCAT('sem PU na posição nos ', @dias_pu, ' dias até ', FORMAT(@data, 'dd/MM/yyyy'))
FROM   #ativos WHERE qt_lotes IS NOT NULL AND pu IS NULL;

INSERT #avisos
SELECT  6, 'Média parcial', codigo, '', CONCAT(n_sem_taxa, ' de ', n_lotes, ' lotes sem taxa: média só dos outros')
FROM    #ativos
WHERE   taxa_media IS NOT NULL AND n_sem_taxa > 0;

INSERT #avisos                                   -- boleta inválida ou sem boleta
SELECT  CASE WHEN taxa_boleta IS NULL THEN 8 ELSE 7 END,
        CASE WHEN taxa_boleta IS NULL THEN 'Sem boleta' ELSE 'Boleta inválida' END, codigo, CD,
        CONCAT(CASE WHEN taxa_boleta IS NULL THEN 'nenhuma boleta casada'
                    ELSE CONCAT('boleta com ', FORMAT(taxa_boleta, 'N4', 'pt-BR'), ' fora da convenção do ', grupo) END,
               ': ', CASE fonte_taxa WHEN 'VCRA' THEN 'usada a taxa da VCRA' WHEN 'manual' THEN 'usada a correção manual'
                                     ELSE 'lote sem taxa, fora da média do ativo' END)
FROM    #lotes
WHERE   qt_aberta > 0 AND boleta_ok = 0;

INSERT #avisos
SELECT  9, 'Correção manual', codigo, CD, CONCAT('taxa ', FORMAT(taxa, 'N4', 'pt-BR'), ' (', motivo_correcao, ')')
FROM    #lotes
WHERE   qt_aberta > 0 AND fonte_taxa = 'manual';

INSERT #avisos
SELECT  10, 'Correção não aplicada', '', k.CD, 'o lote não está entre os lotes em aberto do fundo'
FROM    @correcoes k
WHERE   NOT EXISTS (SELECT 1 FROM #lotes l WHERE l.CD = k.CD COLLATE DATABASE_DEFAULT AND l.qt_aberta > 0);

INSERT #avisos                                   -- boleta x VCRA acima do limite (só conferência)
SELECT  11, 'Boleta × VCRA', codigo, CD,
        CONCAT('boleta ', FORMAT(taxa_boleta, 'N2', 'pt-BR'), ' × VCRA ', FORMAT(taxa_vcra_conv, 'N2', 'pt-BR'),
               ' (PU ', FORMAT(pu_compra, 'N2', 'pt-BR'), '); ',
               CASE fonte_taxa WHEN 'manual' THEN 'vale a correção manual' WHEN 'Lake' THEN 'vale a taxa do Lake'
                               ELSE 'vale a taxa da VCRA' END)
FROM    #lotes
WHERE   qt_aberta > 0 AND boleta_ok = 1
  AND   ABS(dif_boleta_vcra) > CASE grupo WHEN 'CDI+' THEN @div_cdi ELSE @div_pct END;

INSERT #avisos
SELECT  12, 'Venda sem compra', MAX(codigo), CD,
        CONCAT('venda de ', FORMAT(SUM(qt), 'N0', 'pt-BR'), ' sem a compra do lote no histórico da VCRA')
FROM    #vcra v
WHERE   op = 'V' AND incluido = 1 AND cdi = 1 AND NOT EXISTS (SELECT 1 FROM #compras c WHERE c.CD = v.CD)
GROUP BY CD;

INSERT #avisos
SELECT  13, 'Lote negativo', codigo, CD,
        CONCAT('vendas (', FORMAT(qt_vendida, 'N0', 'pt-BR'), ') maiores que as compras (',
               FORMAT(qt_comprada, 'N0', 'pt-BR'), ')')
FROM    #lotes
WHERE   qt_aberta < 0;

-- ── resultados ──
SELECT  @fundo AS fundo, @data AS data, @fonte AS taxa_dos_cdi_mais, @cdi AS cdi_aa, @cdi_origem AS origem_do_cdi,
        (SELECT COUNT(*) FROM #lotes WHERE qt_aberta > 0) AS lotes_em_aberto,
        (SELECT COUNT(*) FROM #ativos WHERE qt_lotes IS NOT NULL) AS ativos,
        (SELECT COUNT(*) FROM #avisos) AS avisos;

SELECT * FROM #carteira ORDER BY CASE grupo WHEN 'CARTEIRA' THEN 2 ELSE 1 END, grupo;

SELECT  codigo, isin, tipo, grupo, perc_cdi, taxa_emissao, n_lotes, n_sem_boleta, n_manual, qt_lotes, qt_posicao,
        dif_qt, taxa_vcra, taxa_media, taxa_cdi_mais, pu, dt_pu, financeiro
FROM    #ativos
ORDER BY CASE WHEN grupo IS NULL THEN 1 ELSE 0 END, grupo, codigo;

SELECT  codigo, isin, tipo, indexador, grupo, CD AS lote, dt_compra, qt_comprada, qt_vendida, qt_aberta, pu_compra,
        perc_cdi, taxa_emissao, taxa_vcra, taxa_vcra_conv, data_boleta, casou_por, taxa_boleta,
        CASE boleta_ok WHEN 1 THEN 'sim' ELSE 'não' END AS boleta_valida, dif_boleta_vcra, taxa, fonte_taxa
FROM    #lotes
WHERE   qt_aberta > 0
ORDER BY grupo, codigo, dt_compra;

SELECT aviso, ativo, lote, detalhe FROM #avisos ORDER BY ordem, ativo, lote;

-- pendências no formato da aba Correções (fundo, CD, taxa, aplicar, motivo)
SELECT  @fundo AS fundo, CD, '' AS taxa, 'N' AS aplicar,
        CONCAT(codigo, ': ',
               CASE WHEN taxa_boleta IS NULL THEN 'sem boleta casada'
                    ELSE CONCAT('boleta ', FORMAT(taxa_boleta, 'N4', 'pt-BR'), ' fora da convenção do ', grupo) END,
               '; VCRA ', ISNULL(FORMAT(taxa_vcra_conv, 'N4', 'pt-BR'), '-'),
               CASE grupo WHEN '%CDI' THEN '% do CDI' ELSE ' de spread' END,
               '; PU ', FORMAT(pu_compra, 'N6', 'pt-BR'), '; compra em ', FORMAT(dt_compra, 'dd/MM/yyyy')) AS motivo
FROM    #lotes
WHERE   qt_aberta > 0 AND boleta_ok = 0 AND fonte_taxa <> 'manual'
ORDER BY codigo, CD;
