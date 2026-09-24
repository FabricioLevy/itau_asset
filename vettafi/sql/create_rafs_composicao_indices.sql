/*
    Composição diária dos índices VettaFi (RAFSBDRP, RAFSBRAP).

    Renomeia os objetos reservados (os renames mantêm os grants de cada objeto):
        dbo.TabelaReserva_GrantsApenasParaPrivado_16  ->  dbo.rafs_composicao_indices
        dbo.ViewReserva_Publica_17                    ->  dbo.vw_rafs_composicao_indices

    Ordem: tabela recebe as colunas novas -> view passa a ler as colunas novas
    -> coluna placeholder [n] é removida (evita erro se a view reserva depender dela).
    O script pode ser executado mais de uma vez.
*/
USE [DBSX337];
GO

/* 1. Rename da tabela */
IF OBJECT_ID('dbo.TabelaReserva_GrantsApenasParaPrivado_16', 'U') IS NOT NULL
   AND OBJECT_ID('dbo.rafs_composicao_indices', 'U') IS NULL
    EXEC sp_rename 'dbo.TabelaReserva_GrantsApenasParaPrivado_16', 'rafs_composicao_indices';
GO

/* 2. Colunas da tabela (a tabela reserva é esvaziada para permitir colunas NOT NULL) */
IF COL_LENGTH('dbo.rafs_composicao_indices', 'EFFECTIVE_DATE') IS NULL
BEGIN
    TRUNCATE TABLE dbo.rafs_composicao_indices;

    ALTER TABLE dbo.rafs_composicao_indices ADD
        [INDEX]              VARCHAR(20)    NOT NULL,
        EFFECTIVE_DATE       DATE           NOT NULL,
        COMPANY_NAME         VARCHAR(200)   NULL,
        BB_TICKER            VARCHAR(30)    NULL,
        SEDOL                VARCHAR(10)    NULL,
        CUSIP                VARCHAR(12)    NULL,
        ISIN                 VARCHAR(12)    NULL,
        ID_BB_GLOBAL         VARCHAR(12)    NOT NULL,
        ICE_SECTOR_CODE      VARCHAR(20)    NULL,
        ICE_SECTOR_NAME      VARCHAR(100)   NULL,
        VETTAFI_CATEGORY     VARCHAR(100)   NULL,
        MIC                  VARCHAR(10)    NULL,
        COUNTRY              VARCHAR(5)     NULL,
        REGION               VARCHAR(50)    NULL,
        SIZE                 VARCHAR(50)    NULL,
        CAP                  VARCHAR(50)    NULL,
        CURR                 VARCHAR(3)     NULL,
        LOCAL_PRICE          DECIMAL(28,8)  NULL,
        FX_RATE              DECIMAL(28,16) NULL,
        INDEX_PRICE          DECIMAL(28,16) NULL,
        SHARES_OUTSTANDING   DECIMAL(38,4)  NULL,
        MARKET_CAP           DECIMAL(38,16) NULL,
        [FLOAT]              DECIMAL(28,16) NULL,
        WAF                  DECIMAL(28,16) NULL,
        INDEX_SHARES         DECIMAL(38,16) NULL,
        INDEX_MARKET_CAP     DECIMAL(38,16) NULL,
        INDEX_WEIGHT         DECIMAL(28,16) NULL,
        DAILY_PRICE_RETURN   DECIMAL(28,16) NULL,
        DAILY_TOTAL_RETURN   DECIMAL(28,16) NULL,
        DIVIDEND             DECIMAL(28,8)  NULL,
        NET_DIVIDEND         DECIMAL(28,8)  NULL,
        NOME_ARQUIVO         VARCHAR(100)   NULL,
        DT_CARGA             DATETIME2(0)   NOT NULL
            CONSTRAINT DF_rafs_composicao_indices_DT_CARGA DEFAULT SYSDATETIME();
END
GO

/* 3. Rename da view */
IF OBJECT_ID('dbo.ViewReserva_Publica_17', 'V') IS NOT NULL
   AND OBJECT_ID('dbo.vw_rafs_composicao_indices', 'V') IS NULL
    EXEC sp_rename 'dbo.ViewReserva_Publica_17', 'vw_rafs_composicao_indices';
GO

/* 4. Definição da view (ALTER VIEW mantém os grants e atualiza o nome na definição) */
ALTER VIEW dbo.vw_rafs_composicao_indices
AS
SELECT
    [INDEX],
    EFFECTIVE_DATE,
    COMPANY_NAME,
    BB_TICKER,
    SEDOL,
    CUSIP,
    ISIN,
    ID_BB_GLOBAL,
    ICE_SECTOR_CODE,
    ICE_SECTOR_NAME,
    VETTAFI_CATEGORY,
    MIC,
    COUNTRY,
    REGION,
    SIZE,
    CAP,
    CURR,
    LOCAL_PRICE,
    FX_RATE,
    INDEX_PRICE,
    SHARES_OUTSTANDING,
    MARKET_CAP,
    [FLOAT],
    WAF,
    INDEX_SHARES,
    INDEX_MARKET_CAP,
    INDEX_WEIGHT,
    DAILY_PRICE_RETURN,
    DAILY_TOTAL_RETURN,
    DIVIDEND,
    NET_DIVIDEND,
    NOME_ARQUIVO,
    DT_CARGA
FROM dbo.rafs_composicao_indices;
GO

/* 5. Remove a coluna placeholder da tabela reserva */
IF COL_LENGTH('dbo.rafs_composicao_indices', 'n') IS NOT NULL
    ALTER TABLE dbo.rafs_composicao_indices DROP COLUMN n;
GO

/* 6. Chave primária */
IF OBJECT_ID('dbo.PK_rafs_composicao_indices', 'PK') IS NULL
    ALTER TABLE dbo.rafs_composicao_indices
        ADD CONSTRAINT PK_rafs_composicao_indices
        PRIMARY KEY CLUSTERED (EFFECTIVE_DATE, [INDEX], ID_BB_GLOBAL);
GO
