/*
    Linhas para o ntnb/input/titulos.csv a partir do DBSX337: ISIN e vencimento das NTN-B em circulação
    (cadastro de ativos, sem a NTN-B Principal) e a 1ª cota_acumulada do FUNDOS_DADOS_ATIVOS a partir da
    data de início (cota + data_cota: o script escala a série para bater com o banco nesse dia).
    Copie o resultado do SSMS com o cabeçalho e cole no titulos.csv (o script aceita tab e "NULL").
    cota NULL = título sem cota no FUNDOS_DADOS_ATIVOS no período: a série começa em 1.
    Só títulos vivos: o Broadcast não tem NTN-B vencida.
*/
DECLARE @data_inicio DATE = '2021-01-04';

WITH titulos AS (
    SELECT c.codigo_IAM_ativo, MAX(c.valor_date) AS vencimento
    FROM DBSX337.dbo.fundos_cadastro_ativos AS c
    LEFT JOIN DBSX337.dbo.fundos_cadastro_ativos AS t
           ON t.codigo_IAM_ativo = c.codigo_IAM_ativo AND t.campo = 'ticker_bolsa'
    WHERE c.campo = 'vencimento'
      AND c.codigo_IAM_ativo LIKE 'BRSTNCNTB%'
      AND LEN(c.codigo_IAM_ativo) <= 12
      AND ISNULL(t.valor_str, '') NOT LIKE 'NTNBP %'
    GROUP BY c.codigo_IAM_ativo
    HAVING MAX(c.valor_date) > GETDATE()
),
primeira AS (
    SELECT d.codigo_IAM_ativo, MIN(d.[date]) AS data_cota
    FROM DBSX337.dbo.FUNDOS_DADOS_ATIVOS AS d
    JOIN titulos AS x ON x.codigo_IAM_ativo = d.codigo_IAM_ativo
    WHERE d.[date] >= @data_inicio AND d.cota_acumulada IS NOT NULL
    GROUP BY d.codigo_IAM_ativo
)
SELECT x.codigo_IAM_ativo,
       CONVERT(VARCHAR(10), x.vencimento, 103)   AS vencimento,
       CONVERT(VARCHAR(10), @data_inicio, 103)   AS data_inicio,
       CAST(d.cota_acumulada AS DECIMAL(28,16))  AS cota,
       CONVERT(VARCHAR(10), p.data_cota, 103)    AS data_cota
FROM titulos AS x
LEFT JOIN primeira AS p
       ON p.codigo_IAM_ativo = x.codigo_IAM_ativo
LEFT JOIN DBSX337.dbo.FUNDOS_DADOS_ATIVOS AS d
       ON d.codigo_IAM_ativo = x.codigo_IAM_ativo AND d.[date] = p.data_cota
ORDER BY x.vencimento;
