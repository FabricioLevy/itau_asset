/*
    Linhas para o ntnb/input/titulos.csv a partir do DBSX337: ISIN e vencimento das NTN-B em circulação
    (cadastro de ativos, sem a NTN-B Principal) e a cota_acumulada do FUNDOS_DADOS_ATIVOS na data de início.
    Copie o resultado do SSMS com o cabeçalho e cole no titulos.csv (o script aceita tab e "NULL").
    cota_inicio NULL = título sem cota no dia no FUNDOS_DADOS_ATIVOS: a série começa em 1.
*/
DECLARE @data_inicio DATE = '2023-01-02';

SELECT c.codigo_IAM_ativo,
       CONVERT(VARCHAR(10), c.valor_date, 103)   AS vencimento,
       CONVERT(VARCHAR(10), @data_inicio, 103)   AS data_inicio,
       CAST(d.cota_acumulada AS DECIMAL(28,16))  AS cota_inicio
FROM DBSX337.dbo.fundos_cadastro_ativos AS c
LEFT JOIN DBSX337.dbo.fundos_cadastro_ativos AS t
       ON t.codigo_IAM_ativo = c.codigo_IAM_ativo AND t.campo = 'ticker_bolsa'
LEFT JOIN DBSX337.dbo.FUNDOS_DADOS_ATIVOS AS d
       ON d.codigo_IAM_ativo = c.codigo_IAM_ativo AND d.[date] = @data_inicio
WHERE c.campo = 'vencimento'
  AND c.codigo_IAM_ativo LIKE 'BRSTNCNTB%'
  AND LEN(c.codigo_IAM_ativo) <= 12
  AND ISNULL(t.valor_str, '') NOT LIKE 'NTNBP %'
  AND c.valor_date > GETDATE()
GROUP BY c.codigo_IAM_ativo, c.valor_date, d.cota_acumulada
ORDER BY c.valor_date;
