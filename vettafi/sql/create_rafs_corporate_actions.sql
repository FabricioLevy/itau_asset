/*
    Corporate actions dos índices VettaFi (RAFSBDRP, RAFSBRAP): arquivos
    AAAAMMDD_<INDICE>_VFA.csv que o download.py salva em output/<INDICE>/CORPORATE_ACTIONS.

    Cada arquivo diário é uma foto dos eventos anunciados (EFF_DATE, em geral futura).
    A tabela guarda todas as fotos, identificadas pela data do nome do arquivo (DATE_REF).
    As colunas numéricas do arquivo são todas DECIMAL(38,16).

    Renomeia os objetos reservados (os renames mantêm os grants de cada objeto):
        dbo.TabelaReserva_GrantsApenasParaPrivado_NN  ->  dbo.rafs_corporate_actions
        dbo.ViewReserva_Publica_NN                    ->  dbo.vw_rafs_corporate_actions

    >>> ANTES DE RODAR: troque os NN pelos números dos objetos reservados para esta tabela
        (aparecem nos passos 1 e 3). Para listar os objetos reservados:
            SELECT name, type_desc FROM sys.objects WHERE name LIKE '%Reserva%' ORDER BY name;

    Ordem: tabela recebe as colunas novas -> view passa a ler as colunas novas
    -> coluna placeholder [n] é removida (evita erro se a view reserva depender dela).
    O script pode ser executado mais de uma vez.
*/
USE [DBSX337];
GO

/* 1. Rename da tabela */
IF OBJECT_ID('dbo.TabelaReserva_GrantsApenasParaPrivado_NN', 'U') IS NOT NULL
   AND OBJECT_ID('dbo.rafs_corporate_actions', 'U') IS NULL
    EXEC sp_rename 'dbo.TabelaReserva_GrantsApenasParaPrivado_NN', 'rafs_corporate_actions';
GO

/* 2. Colunas da tabela (a tabela reserva é esvaziada para permitir colunas NOT NULL) */
IF COL_LENGTH('dbo.rafs_corporate_actions', 'EFF_DATE') IS NULL
BEGIN
    TRUNCATE TABLE dbo.rafs_corporate_actions;

    ALTER TABLE dbo.rafs_corporate_actions ADD
        [INDEX]                         VARCHAR(20)    NOT NULL,
        DATE_REF                        DATE           NOT NULL,
        EFF_DATE                        DATE           NOT NULL,
        EVENT                           VARCHAR(30)    NOT NULL,
        [SEQUENCE]                      INT            NOT NULL,
        CA_DESCRIPTION                  VARCHAR(200)   NULL,
        CURRENT_COMPANY_NAME            VARCHAR(200)   NULL,
        NEW_COMPANY_NAME                VARCHAR(200)   NULL,
        CURRENT_TICKER                  VARCHAR(30)    NULL,
        NEW_TICKER                      VARCHAR(30)    NULL,
        CURRENT_SEDOL                   VARCHAR(10)    NULL,
        NEW_SEDOL                       VARCHAR(10)    NULL,
        CURRENT_CUSIP                   VARCHAR(12)    NULL,
        NEW_CUSIP                       VARCHAR(12)    NULL,
        CURRENT_ISIN                    VARCHAR(12)    NULL,
        NEW_ISIN                        VARCHAR(12)    NULL,
        ID_BB_GLOBAL                    VARCHAR(12)    NOT NULL,
        STK_CURN                        VARCHAR(3)     NULL,
        DIV_CURN                        VARCHAR(3)     NULL,
        DIVIDEND                        DECIMAL(38,16) NULL,
        NET_DIVIDEND                    DECIMAL(38,16) NULL,
        TAX_RATE                        DECIMAL(38,16) NULL,
        FRANKED_PCT                     DECIMAL(38,16) NULL,
        SHARES_HELD                     DECIMAL(38,16) NULL,
        SHARES_RECEIVED                 DECIMAL(38,16) NULL,
        SUBSCRIPTION_OFFER_PRICE        DECIMAL(38,16) NULL,
        SUBSCRIPTION_OFFER_CURRENCY     VARCHAR(3)     NULL,
        ADJ_FACTOR                      DECIMAL(38,16) NULL,
        CURRENT_SHARES_OUTSTANDING      DECIMAL(38,16) NULL,
        NEW_SHARES_OUTSTANDING          DECIMAL(38,16) NULL,
        CURRENT_FLOAT                   DECIMAL(38,16) NULL,
        NEW_FLOAT                       DECIMAL(38,16) NULL,
        CURRENT_WAF                     DECIMAL(38,16) NULL,
        NEW_WAF                         DECIMAL(38,16) NULL,
        CURRENT_INDEX_SHARES            DECIMAL(38,16) NULL,
        ADJUSTED_INDEX_SHARES           DECIMAL(38,16) NULL,
        CURRENT_PRICE                   DECIMAL(38,16) NULL,
        ADJUSTED_PRICE                  DECIMAL(38,16) NULL,
        SPIN_ACQUIRER_COMPANY_NAME      VARCHAR(200)   NULL,
        SPIN_ACQUIRER_TICKER            VARCHAR(30)    NULL,
        SPIN_ACQUIRER_ISIN              VARCHAR(12)    NULL,
        DIVA_EX_DATE_INDEX_SHARES       DECIMAL(38,16) NULL,
        DIVA_EX_DATE_FX_RATE            DECIMAL(38,16) NULL,
        DIVA_EX_DATE_DIVISOR            DECIMAL(38,16) NULL,
        ADJUSTMENT_DIVIDEND_POINTS      DECIMAL(38,16) NULL,
        ADJUSTMENT_NET_DIVIDEND_POINTS  DECIMAL(38,16) NULL,
        CORPORATE_ACTION_NOTES          VARCHAR(4000)  NULL,
        FILE_NAME                       VARCHAR(100)   NULL,
        DATE_LOAD                       DATETIME2(0)   NOT NULL
            CONSTRAINT DF_rafs_corporate_actions_DATE_LOAD DEFAULT SYSDATETIME();
END
GO

/* 3. Rename da view */
IF OBJECT_ID('dbo.ViewReserva_Publica_NN', 'V') IS NOT NULL
   AND OBJECT_ID('dbo.vw_rafs_corporate_actions', 'V') IS NULL
    EXEC sp_rename 'dbo.ViewReserva_Publica_NN', 'vw_rafs_corporate_actions';
GO

/* 4. Definição da view (ALTER VIEW mantém os grants e atualiza o nome na definição) */
ALTER VIEW dbo.vw_rafs_corporate_actions
AS
SELECT
    [INDEX],
    DATE_REF,
    EFF_DATE,
    EVENT,
    [SEQUENCE],
    CA_DESCRIPTION,
    CURRENT_COMPANY_NAME,
    NEW_COMPANY_NAME,
    CURRENT_TICKER,
    NEW_TICKER,
    CURRENT_SEDOL,
    NEW_SEDOL,
    CURRENT_CUSIP,
    NEW_CUSIP,
    CURRENT_ISIN,
    NEW_ISIN,
    ID_BB_GLOBAL,
    STK_CURN,
    DIV_CURN,
    DIVIDEND,
    NET_DIVIDEND,
    TAX_RATE,
    FRANKED_PCT,
    SHARES_HELD,
    SHARES_RECEIVED,
    SUBSCRIPTION_OFFER_PRICE,
    SUBSCRIPTION_OFFER_CURRENCY,
    ADJ_FACTOR,
    CURRENT_SHARES_OUTSTANDING,
    NEW_SHARES_OUTSTANDING,
    CURRENT_FLOAT,
    NEW_FLOAT,
    CURRENT_WAF,
    NEW_WAF,
    CURRENT_INDEX_SHARES,
    ADJUSTED_INDEX_SHARES,
    CURRENT_PRICE,
    ADJUSTED_PRICE,
    SPIN_ACQUIRER_COMPANY_NAME,
    SPIN_ACQUIRER_TICKER,
    SPIN_ACQUIRER_ISIN,
    DIVA_EX_DATE_INDEX_SHARES,
    DIVA_EX_DATE_FX_RATE,
    DIVA_EX_DATE_DIVISOR,
    ADJUSTMENT_DIVIDEND_POINTS,
    ADJUSTMENT_NET_DIVIDEND_POINTS,
    CORPORATE_ACTION_NOTES,
    FILE_NAME,
    DATE_LOAD
FROM dbo.rafs_corporate_actions;
GO

/* 5. Remove a coluna placeholder da tabela reserva */
IF COL_LENGTH('dbo.rafs_corporate_actions', 'n') IS NOT NULL
    ALTER TABLE dbo.rafs_corporate_actions DROP COLUMN n;
GO

/* 6. Chave primária: um evento por ação, data efetiva e sequência em cada arquivo */
IF OBJECT_ID('dbo.PK_rafs_corporate_actions', 'PK') IS NULL
    ALTER TABLE dbo.rafs_corporate_actions
        ADD CONSTRAINT PK_rafs_corporate_actions
        PRIMARY KEY CLUSTERED (DATE_REF, [INDEX], EFF_DATE, ID_BB_GLOBAL, EVENT, [SEQUENCE]);
GO
