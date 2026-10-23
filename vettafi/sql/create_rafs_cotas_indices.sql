/*
    Cotas diárias dos índices VettaFi (RAFSBDRP, RAFSBRAP): arquivos
    AAAAMMDD_<INDICE>_VFL.csv que o download.py salva em output/<INDICE>/LEVELS.

    Cada arquivo traz a cota do dia (PRICE_DATE) de três versões do índice, em INDEX_CODE:
    preço (final P, ex.: RAFSBDRP), retorno total (final T) e retorno total líquido (final N).
    [INDEX] é o índice do nome do arquivo, o mesmo das tabelas de composição e corporate actions.
    As colunas numéricas não inteiras do arquivo são todas DECIMAL(38,16).

    Renomeia os objetos reservados (os renames mantêm os grants de cada objeto):
        dbo.TabelaReserva_GrantsApenasParaPrivado_20  ->  dbo.rafs_cotas_indices
        dbo.ViewReserva_Publica_20                    ->  dbo.vw_rafs_cotas_indices

    Ordem: tabela recebe as colunas novas -> view passa a ler as colunas novas
    -> coluna placeholder [n] é removida (evita erro se a view reserva depender dela).
    O script pode ser executado mais de uma vez.
*/
USE [DBSX337];
GO

/* 1. Rename da tabela */
IF OBJECT_ID('dbo.TabelaReserva_GrantsApenasParaPrivado_20', 'U') IS NOT NULL
   AND OBJECT_ID('dbo.rafs_cotas_indices', 'U') IS NULL
    EXEC sp_rename 'dbo.TabelaReserva_GrantsApenasParaPrivado_20', 'rafs_cotas_indices';
GO

/* 2. Colunas da tabela (a tabela reserva é esvaziada para permitir colunas NOT NULL) */
IF COL_LENGTH('dbo.rafs_cotas_indices', 'PRICE_DATE') IS NULL
BEGIN
    TRUNCATE TABLE dbo.rafs_cotas_indices;

    ALTER TABLE dbo.rafs_cotas_indices ADD
        [INDEX]             VARCHAR(20)    NOT NULL,
        PRICE_DATE          DATE           NOT NULL,
        INDEX_CODE          VARCHAR(20)    NOT NULL,
        INDEX_NAME          VARCHAR(200)   NULL,
        CURRENCY            VARCHAR(3)     NULL,
        INDEX_VALUE         DECIMAL(38,16) NULL,
        CLOSE_MARKET_CAP    DECIMAL(38,16) NULL,
        CLOSE_DIVISOR       DECIMAL(38,16) NULL,
        CLOSE_COUNT         INT            NULL,
        ADJ_MARKET_CAP      DECIMAL(38,16) NULL,
        ADJ_DIVISOR         DECIMAL(38,16) NULL,
        ADJ_COUNT           INT            NULL,
        INDEX_DIVIDEND      DECIMAL(38,16) NULL,
        DAILY_RETURN        DECIMAL(38,16) NULL,
        CHANGE              VARCHAR(100)   NULL,  -- vazia em todos os arquivos vistos até agora
        FILE_NAME           VARCHAR(100)   NULL,
        DATE_LOAD           DATETIME2(0)   NOT NULL
            CONSTRAINT DF_rafs_cotas_indices_DATE_LOAD DEFAULT SYSDATETIME();
END
GO

/* 3. Rename da view */
IF OBJECT_ID('dbo.ViewReserva_Publica_20', 'V') IS NOT NULL
   AND OBJECT_ID('dbo.vw_rafs_cotas_indices', 'V') IS NULL
    EXEC sp_rename 'dbo.ViewReserva_Publica_20', 'vw_rafs_cotas_indices';
GO

/* 4. Definição da view (ALTER VIEW mantém os grants e atualiza o nome na definição) */
ALTER VIEW dbo.vw_rafs_cotas_indices
AS
SELECT
    [INDEX],
    PRICE_DATE,
    INDEX_CODE,
    INDEX_NAME,
    CURRENCY,
    INDEX_VALUE,
    CLOSE_MARKET_CAP,
    CLOSE_DIVISOR,
    CLOSE_COUNT,
    ADJ_MARKET_CAP,
    ADJ_DIVISOR,
    ADJ_COUNT,
    INDEX_DIVIDEND,
    DAILY_RETURN,
    CHANGE,
    FILE_NAME,
    DATE_LOAD
FROM dbo.rafs_cotas_indices;
GO

/* 5. Remove a coluna placeholder da tabela reserva */
IF COL_LENGTH('dbo.rafs_cotas_indices', 'n') IS NOT NULL
    ALTER TABLE dbo.rafs_cotas_indices DROP COLUMN n;
GO

/* 6. Chave primária: uma cota por versão do índice (INDEX_CODE) e data */
IF OBJECT_ID('dbo.PK_rafs_cotas_indices', 'PK') IS NULL
    ALTER TABLE dbo.rafs_cotas_indices
        ADD CONSTRAINT PK_rafs_cotas_indices
        PRIMARY KEY CLUSTERED (PRICE_DATE, INDEX_CODE);
GO
