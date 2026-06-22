-- ============================================================
-- DI PREMIA REPORT - Criação de Schemas e Tabelas
-- Banco: db  |  Servidor: levydb.database.windows.net
-- ============================================================


-- ------------------------------------------------------------
-- SCHEMAS
-- ------------------------------------------------------------
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'risk')
    EXEC('CREATE SCHEMA [risk]');
GO
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'middle')
    EXEC('CREATE SCHEMA [middle]');
GO
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'quant')
    EXEC('CREATE SCHEMA [quant]');
GO
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'bcb')
    EXEC('CREATE SCHEMA [bcb]');
GO
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'research')
    EXEC('CREATE SCHEMA [research]');
GO


-- ============================================================
-- SCHEMA: risk
-- Curvas de juros (DI Fut, DAP BEI)
-- ============================================================

CREATE TABLE [risk].[interest_rate_curve] (
    [id]              INT           IDENTITY(1,1) NOT NULL,
    [date_reference]  DATE          NOT NULL,
    [curve_name]      VARCHAR(50)   NOT NULL,    -- 'DI Fut', 'DAP Fut', 'DAP BEI'
    [tenor]           INT           NULL,        -- NULL para nós brutos de contrato; inteiro para buckets interpolados (180, 360, ...)
    [tenor_date]      DATE          NULL,        -- data real do vencimento / ponto da curva
    [curve_rate]      FLOAT         NOT NULL,    -- taxa anual em decimal (ex: 0.1025 = 10.25%)
    [discount_factor] FLOAT         NULL,        -- fator de desconto no ponto
    [code_maturity]   VARCHAR(20)   NULL,        -- código do contrato futuro (ex: 'F23'), NULL para buckets
    [business_day]    INT           NULL,        -- dias úteis entre date_reference e tenor_date
    CONSTRAINT PK_interest_rate_curve PRIMARY KEY ([id])
);
GO
CREATE INDEX IX_interest_rate_curve_lookup
    ON [risk].[interest_rate_curve] ([curve_name], [date_reference], [tenor]);
GO


-- ============================================================
-- SCHEMA: middle
-- Preços de produtos (SELIC TARGET)
-- ============================================================

CREATE TABLE [middle].[product_price] (
    [id]             INT           IDENTITY(1,1) NOT NULL,
    [date_reference] DATE          NOT NULL,
    [product_id]     VARCHAR(100)  NOT NULL,   -- ex: 'SELIC TARGET'
    [rate]           FLOAT         NOT NULL,
    CONSTRAINT PK_product_price PRIMARY KEY ([id])
);
GO
CREATE INDEX IX_product_price_lookup
    ON [middle].[product_price] ([product_id], [date_reference]);
GO


-- ============================================================
-- SCHEMA: quant
-- Séries temporais genéricas (CDI, prêmios exportados pelo stage 9)
-- ============================================================

CREATE TABLE [quant].[time_series_entity] (
    [id]               VARCHAR(200)  NOT NULL,   -- ex: 'CDI', 'DAPBEI1Y', 'Implicit inflation premium 1y'
    [refinitiv_symbol] VARCHAR(100)  NULL,
    [bloomberg_symbol] VARCHAR(100)  NULL,
    CONSTRAINT PK_time_series_entity PRIMARY KEY ([id])
);
GO

CREATE TABLE [quant].[time_series] (
    [id]               INT           IDENTITY(1,1) NOT NULL,
    [entity_id]        VARCHAR(200)  NOT NULL,
    [name]             VARCHAR(200)  NOT NULL,
    [source]           VARCHAR(100)  NOT NULL,   -- ex: 'di premia'
    [field]            VARCHAR(100)  NOT NULL,
    [update_frequency] VARCHAR(50)   NOT NULL,   -- ex: 'manual', 'daily'
    CONSTRAINT PK_time_series PRIMARY KEY ([id]),
    CONSTRAINT FK_time_series_entity FOREIGN KEY ([entity_id])
        REFERENCES [quant].[time_series_entity] ([id])
);
GO
CREATE INDEX IX_time_series_entity_source
    ON [quant].[time_series] ([entity_id], [source]);
GO

CREATE TABLE [quant].[time_series_value] (
    [id]             INT           IDENTITY(1,1) NOT NULL,
    [series_id]      INT           NOT NULL,
    [date_reference] DATE          NOT NULL,
    [value]          FLOAT         NOT NULL,
    CONSTRAINT PK_time_series_value PRIMARY KEY ([id]),
    CONSTRAINT FK_time_series_value_series FOREIGN KEY ([series_id])
        REFERENCES [quant].[time_series] ([id])
);
GO
CREATE UNIQUE INDEX IX_time_series_value_lookup
    ON [quant].[time_series_value] ([series_id], [date_reference]);
GO


-- ============================================================
-- SCHEMA: bcb
-- Focus BCB — expectativas de IPCA e SELIC
-- ============================================================

CREATE TABLE [bcb].[modulo_focus_series] (
    [id]        INT           IDENTITY(1,1) NOT NULL,
    [indicator] VARCHAR(50)   NOT NULL,   -- 'IPCA', 'SELIC'
    [type]      VARCHAR(20)   NOT NULL,   -- '126DU', '252DU', '378DU', '504DU', '1260DU'
    CONSTRAINT PK_modulo_focus_series PRIMARY KEY ([id])
);
GO
CREATE UNIQUE INDEX IX_modulo_focus_series_lookup
    ON [bcb].[modulo_focus_series] ([indicator], [type]);
GO

CREATE TABLE [bcb].[modulo_focus_value] (
    [id]        INT           IDENTITY(1,1) NOT NULL,
    [series_id] INT           NOT NULL,
    [date]      DATE          NOT NULL,
    [value]     FLOAT         NOT NULL,
    CONSTRAINT PK_modulo_focus_value PRIMARY KEY ([id]),
    CONSTRAINT FK_modulo_focus_value_series FOREIGN KEY ([series_id])
        REFERENCES [bcb].[modulo_focus_series] ([id])
);
GO
CREATE UNIQUE INDEX IX_modulo_focus_value_lookup
    ON [bcb].[modulo_focus_value] ([series_id], [date]);
GO


-- ============================================================
-- SCHEMA: research
-- Metas de inflação e reuniões do COPOM
-- ============================================================

CREATE TABLE [research].[inflation_target_rate] (
    [id]             INT           IDENTITY(1,1) NOT NULL,
    [country]        NVARCHAR(10)  NOT NULL,   -- 'BRL'
    [date_reference] DATE          NOT NULL,   -- ano-referência da meta (ex: 2024-12-31)
    [date_publish]   DATE          NOT NULL,   -- data de publicação da meta
    [rate_target]    FLOAT         NOT NULL,   -- meta central (ex: 3.0)
    [rate_tolerance] FLOAT         NOT NULL,   -- banda de tolerância (ex: 1.5)
    [rate_realized]  FLOAT         NULL,       -- IPCA realizado (preenchido após encerramento do ano)
    [obs]            NVARCHAR(500) NULL,
    CONSTRAINT PK_inflation_target_rate PRIMARY KEY ([id])
);
GO
CREATE INDEX IX_inflation_target_rate_lookup
    ON [research].[inflation_target_rate] ([country], [date_reference]);
GO

CREATE TABLE [research].[monetary_policy_meeting] (
    [id]               INT           IDENTITY(1,1) NOT NULL,
    [country]          VARCHAR(10)   NOT NULL,   -- 'BRL'
    [date_effective]   DATE          NOT NULL,   -- data da decisão
    [decision]         FLOAT         NULL,       -- variação da taxa (ex: 0.25, -0.50, 0.0)
    [rate_target]      FLOAT         NULL,       -- taxa SELIC resultante
    [official_schedule] BIT          NOT NULL DEFAULT 1,   -- 1 = reunião ordinária
    CONSTRAINT PK_monetary_policy_meeting PRIMARY KEY ([id])
);
GO
CREATE INDEX IX_monetary_policy_meeting_lookup
    ON [research].[monetary_policy_meeting] ([country], [date_effective]);
GO
