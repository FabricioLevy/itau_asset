/*
    Status de validação das cotas (portal OC3 > SVC > Consulta Status Validação): foto atual.

    Uma linha por Dt Posição (DATE_REF) + Sistema (SYSTEM_CODE) + Fundo (FUND). A cada execução
    do relatorio_svc com --salvar-sql, o src/carga_sql.py faz um MERGE com o grid baixado:
    fundo/dia que ainda não existe é inserido, o que mudou é atualizado (DATE_UPDATE) e o que
    não veio no grid fica como estava. Cada mudança de status/valor também vai para
    dbo.svc_status_validacao_hist (create_svc_status_validacao_hist.sql).

    Colunas x relatório StatusValidacao_MesaGestao_*.xlsx:
        DATE_REF          Dt Posição (rodando sem --dias/--data-posicao: Data efetiva)
        SYSTEM_CODE       Sistema (LZ, XZ)
        FUND              Fundo (sigla SAC, como aparece no portal)
        FUND_IAM_CODE     Código IAM (codigo_IAM_fundo da VW_FUNDOS_COTAS_PL; NULL se não achou)
        QUOTE_TYPE        Tipo (Abertura, ...)
        LIABILITY_CODE    Passivo
        QUOTE_VALUE       Valor (cota)
        QUOTE_STATUS      Status (Pendente, Enviada FY, ...)
        BAND_STATUS       Status Banda (Liberada, ...)
        COCKPIT_LOAD      Carga Cockpit (Sim/Não)
        DESK              Mesa Gestão (NULL se não achou)
        QUOTE_ID          Id Cota
        PORTFOLIO_ID      Id Carteira
        PROCESSING_DATE   Data Processamento
        DATE_LOAD         primeira vez que o fundo/dia foi gravado
        DATE_UPDATE       última vez que alguma coluna do fundo/dia mudou

    Renomeia os objetos reservados (os renames mantêm os grants de cada objeto):
        dbo.TabelaReserva_GrantsApenasParaPrivado_NN  ->  dbo.svc_status_validacao
        dbo.ViewReserva_Publica_NN                    ->  dbo.vw_svc_status_validacao

    >>> ANTES DE RODAR: troque os NN pelos números dos objetos reservados para esta tabela
        (aparecem nos passos 1 e 3), um par diferente do usado no script do _hist.
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
   AND OBJECT_ID('dbo.svc_status_validacao', 'U') IS NULL
    EXEC sp_rename 'dbo.TabelaReserva_GrantsApenasParaPrivado_NN', 'svc_status_validacao';
GO

/* 2. Colunas da tabela (a tabela reserva é esvaziada para permitir colunas NOT NULL) */
IF COL_LENGTH('dbo.svc_status_validacao', 'QUOTE_STATUS') IS NULL
BEGIN
    TRUNCATE TABLE dbo.svc_status_validacao;

    ALTER TABLE dbo.svc_status_validacao ADD
        DATE_REF            DATE           NOT NULL,
        SYSTEM_CODE         VARCHAR(10)    NOT NULL,
        FUND                VARCHAR(100)   NOT NULL,
        FUND_IAM_CODE       VARCHAR(100)   NULL,
        QUOTE_TYPE          VARCHAR(50)    NULL,
        LIABILITY_CODE      VARCHAR(20)    NULL,
        QUOTE_VALUE         DECIMAL(38,16) NULL,
        QUOTE_STATUS        VARCHAR(100)   NULL,
        BAND_STATUS         VARCHAR(100)   NULL,
        COCKPIT_LOAD        VARCHAR(20)    NULL,
        DESK                VARCHAR(100)   NULL,
        QUOTE_ID            BIGINT         NULL,
        PORTFOLIO_ID        BIGINT         NULL,
        PROCESSING_DATE     DATETIME2(0)   NULL,
        DATE_LOAD           DATETIME2(0)   NOT NULL
            CONSTRAINT DF_svc_status_validacao_DATE_LOAD DEFAULT SYSDATETIME(),
        DATE_UPDATE         DATETIME2(0)   NOT NULL
            CONSTRAINT DF_svc_status_validacao_DATE_UPDATE DEFAULT SYSDATETIME();
END
GO

/* 3. Rename da view */
IF OBJECT_ID('dbo.ViewReserva_Publica_NN', 'V') IS NOT NULL
   AND OBJECT_ID('dbo.vw_svc_status_validacao', 'V') IS NULL
    EXEC sp_rename 'dbo.ViewReserva_Publica_NN', 'vw_svc_status_validacao';
GO

/* 4. Definição da view (ALTER VIEW mantém os grants e atualiza o nome na definição) */
ALTER VIEW dbo.vw_svc_status_validacao
AS
SELECT
    DATE_REF,
    SYSTEM_CODE,
    FUND,
    FUND_IAM_CODE,
    QUOTE_TYPE,
    LIABILITY_CODE,
    QUOTE_VALUE,
    QUOTE_STATUS,
    BAND_STATUS,
    COCKPIT_LOAD,
    DESK,
    QUOTE_ID,
    PORTFOLIO_ID,
    PROCESSING_DATE,
    DATE_LOAD,
    DATE_UPDATE
FROM dbo.svc_status_validacao;
GO

/* 5. Remove a coluna placeholder da tabela reserva */
IF COL_LENGTH('dbo.svc_status_validacao', 'n') IS NOT NULL
    ALTER TABLE dbo.svc_status_validacao DROP COLUMN n;
GO

/* 6. Chave primária: um status por fundo, sistema e Dt Posição */
IF OBJECT_ID('dbo.PK_svc_status_validacao', 'PK') IS NULL
    ALTER TABLE dbo.svc_status_validacao
        ADD CONSTRAINT PK_svc_status_validacao
        PRIMARY KEY CLUSTERED (DATE_REF, SYSTEM_CODE, FUND);
GO
