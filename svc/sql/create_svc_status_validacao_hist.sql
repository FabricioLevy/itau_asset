/*
    Status de validação das cotas (portal OC3 > SVC > Consulta Status Validação): histórico.

    Uma linha cada vez que o src/carga_sql.py vê um fundo/dia novo em dbo.svc_status_validacao
    (CHANGE_TYPE = 'INSERT', colunas OLD_* nulas) ou vê mudar Status, Status Banda, Carga
    Cockpit ou Valor de um fundo/dia que já existia (CHANGE_TYPE = 'UPDATE', com o valor
    anterior em OLD_* e o novo em NEW_*). Mudanças só em outras colunas (mesa, Id Cota, Data
    Processamento, ...) atualizam a foto atual mas não geram linha aqui.

    DATE_LOAD é a hora da execução em que a mudança foi vista (o portal não informa quando
    o status mudou); é o mesmo valor gravado em DATE_UPDATE na svc_status_validacao.
    Rodando o relatório várias vezes ao dia, o histórico mostra a evolução de cada cota.

    Renomeia os objetos reservados (os renames mantêm os grants de cada objeto):
        dbo.TabelaReserva_GrantsApenasParaPrivado_NN  ->  dbo.svc_status_validacao_hist
        dbo.ViewReserva_Publica_NN                    ->  dbo.vw_svc_status_validacao_hist

    >>> ANTES DE RODAR: troque os NN pelos números dos objetos reservados para esta tabela
        (aparecem nos passos 1 e 3), um par diferente do usado no script da foto atual.
        Para listar os objetos reservados:
            SELECT name, type_desc FROM sys.objects WHERE name LIKE '%Reserva%' ORDER BY name;

    Ordem: tabela recebe as colunas novas -> view passa a ler as colunas novas
    -> coluna placeholder [n] é removida (evita erro se a view reserva depender dela).
    O script pode ser executado mais de uma vez.
*/
USE [DBSX337];
GO

/* 1. Rename da tabela */
IF OBJECT_ID('dbo.TabelaReserva_GrantsApenasParaPrivado_NN', 'U') IS NOT NULL
   AND OBJECT_ID('dbo.svc_status_validacao_hist', 'U') IS NULL
    EXEC sp_rename 'dbo.TabelaReserva_GrantsApenasParaPrivado_NN', 'svc_status_validacao_hist';
GO

/* 2. Colunas da tabela (a tabela reserva é esvaziada para permitir colunas NOT NULL) */
IF COL_LENGTH('dbo.svc_status_validacao_hist', 'CHANGE_TYPE') IS NULL
BEGIN
    TRUNCATE TABLE dbo.svc_status_validacao_hist;

    ALTER TABLE dbo.svc_status_validacao_hist ADD
        DATE_REF            DATE           NOT NULL,
        SYSTEM_CODE         VARCHAR(10)    NOT NULL,
        FUND                VARCHAR(100)   NOT NULL,
        CHANGE_TYPE         VARCHAR(10)    NOT NULL,  -- INSERT (fundo/dia novo) ou UPDATE
        OLD_QUOTE_STATUS    VARCHAR(100)   NULL,
        NEW_QUOTE_STATUS    VARCHAR(100)   NULL,
        OLD_BAND_STATUS     VARCHAR(100)   NULL,
        NEW_BAND_STATUS     VARCHAR(100)   NULL,
        OLD_COCKPIT_LOAD    VARCHAR(20)    NULL,
        NEW_COCKPIT_LOAD    VARCHAR(20)    NULL,
        OLD_QUOTE_VALUE     DECIMAL(38,16) NULL,
        NEW_QUOTE_VALUE     DECIMAL(38,16) NULL,
        QUOTE_ID            BIGINT         NULL,
        PROCESSING_DATE     DATETIME2(0)   NULL,
        DATE_LOAD           DATETIME2(0)   NOT NULL
            CONSTRAINT DF_svc_status_validacao_hist_DATE_LOAD DEFAULT SYSDATETIME();
END
GO

/* 3. Rename da view */
IF OBJECT_ID('dbo.ViewReserva_Publica_NN', 'V') IS NOT NULL
   AND OBJECT_ID('dbo.vw_svc_status_validacao_hist', 'V') IS NULL
    EXEC sp_rename 'dbo.ViewReserva_Publica_NN', 'vw_svc_status_validacao_hist';
GO

/* 4. Definição da view (ALTER VIEW mantém os grants e atualiza o nome na definição) */
ALTER VIEW dbo.vw_svc_status_validacao_hist
AS
SELECT
    DATE_REF,
    SYSTEM_CODE,
    FUND,
    CHANGE_TYPE,
    OLD_QUOTE_STATUS,
    NEW_QUOTE_STATUS,
    OLD_BAND_STATUS,
    NEW_BAND_STATUS,
    OLD_COCKPIT_LOAD,
    NEW_COCKPIT_LOAD,
    OLD_QUOTE_VALUE,
    NEW_QUOTE_VALUE,
    QUOTE_ID,
    PROCESSING_DATE,
    DATE_LOAD
FROM dbo.svc_status_validacao_hist;
GO

/* 5. Remove a coluna placeholder da tabela reserva */
IF COL_LENGTH('dbo.svc_status_validacao_hist', 'n') IS NOT NULL
    ALTER TABLE dbo.svc_status_validacao_hist DROP COLUMN n;
GO

/* 6. Chave primária: uma mudança por fundo/dia em cada execução (DATE_LOAD) */
IF OBJECT_ID('dbo.PK_svc_status_validacao_hist', 'PK') IS NULL
    ALTER TABLE dbo.svc_status_validacao_hist
        ADD CONSTRAINT PK_svc_status_validacao_hist
        PRIMARY KEY CLUSTERED (DATE_REF, SYSTEM_CODE, FUND, DATE_LOAD);
GO
