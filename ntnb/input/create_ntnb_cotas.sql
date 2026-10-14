/*
    Série diária de NTN-B com e sem reinvestimento do cupom — PU, VNA e taxa ANBIMA via Broadcast+.
    Carga: ntnb/__main__.py (--sql ou --carregar). Todas as NTN-B na mesma tabela: 1 linha por título e dia.
    Cada carga substitui a série inteira de cada título carregado.

    date / codigo_IAM_ativo / cota_acumulada têm os mesmos nomes do FUNDOS_DADOS_ATIVOS:
        cota_acumulada       reinvestindo o cupom (mesma conta da cota_acumulada do FUNDOS_DADOS_ATIVOS)
        cota_sem_reinvestir  cupom fica em caixa, sem render
        cota_preco           só o PU (o cupom sai e não volta)
    As três partem da cota_inicio do título (ntnb/input/titulos.csv) na data_inicio dele.

    As casas decimais precisam acompanhar COLUNAS_SQL do ntnb/__main__.py.
    O script pode ser executado mais de uma vez.
*/
USE [DBSX337];
GO

IF OBJECT_ID('dbo.ntnb_cotas', 'U') IS NULL
    CREATE TABLE dbo.ntnb_cotas (
        codigo_IAM_ativo     VARCHAR(20)    NOT NULL,  -- ISIN (ex.: BRSTNCNTB690 = NTN-B 15/08/2060)
        [date]               DATE           NOT NULL,
        vencimento           DATE           NOT NULL,
        taxa_indicativa      DECIMAL(10,4)  NULL,      -- % a.a.
        pu                   DECIMAL(18,6)  NOT NULL,
        vna                  DECIMAL(18,6)  NULL,
        cupom                DECIMAL(18,8)  NOT NULL,  -- R$ por título no dia do pagamento; 0 nos demais
        cota_acumulada       DECIMAL(28,16) NOT NULL,
        cota_sem_reinvestir  DECIMAL(28,16) NOT NULL,
        cota_preco           DECIMAL(28,16) NOT NULL,
        dt_carga             DATETIME2(0)   NOT NULL
            CONSTRAINT DF_ntnb_cotas_dt_carga DEFAULT SYSDATETIME(),
        CONSTRAINT PK_ntnb_cotas PRIMARY KEY CLUSTERED (codigo_IAM_ativo, [date])
    );
GO

/* Exemplo — a mesma consulta do FUNDOS_DADOS_ATIVOS, trocando a tabela:
SELECT [date], cota_acumulada, cota_sem_reinvestir, cota_preco
FROM DBSX337.dbo.ntnb_cotas
WHERE [date] > '2023-01-01' AND codigo_IAM_ativo = 'BRSTNCNTB690'
ORDER BY [date];
*/
