/*
    Consultas de exemplo nas views do status de validação das cotas
    (create_svc_status_validacao.sql e create_svc_status_validacao_hist.sql).
    As views têm grant público; as tabelas, só para o usuário da carga.
*/
USE [DBSX337];
GO

/* 1. Foto da última Dt Posição carregada, por mesa */
SELECT s.DATE_REF, s.DESK, s.SYSTEM_CODE, s.FUND, s.FUND_IAM_CODE, s.QUOTE_TYPE,
       s.QUOTE_VALUE, s.QUOTE_STATUS, s.BAND_STATUS, s.COCKPIT_LOAD,
       s.PROCESSING_DATE, s.DATE_UPDATE
FROM   dbo.vw_svc_status_validacao AS s WITH (NOLOCK)
WHERE  s.DATE_REF = (SELECT MAX(DATE_REF) FROM dbo.vw_svc_status_validacao WITH (NOLOCK))
ORDER  BY s.DESK, s.SYSTEM_CODE, s.FUND;

/* 2. Quantos fundos em cada status na última Dt Posição */
SELECT s.DATE_REF, s.SYSTEM_CODE, s.QUOTE_STATUS, s.BAND_STATUS, COUNT(*) AS FUNDS
FROM   dbo.vw_svc_status_validacao AS s WITH (NOLOCK)
WHERE  s.DATE_REF = (SELECT MAX(DATE_REF) FROM dbo.vw_svc_status_validacao WITH (NOLOCK))
GROUP  BY s.DATE_REF, s.SYSTEM_CODE, s.QUOTE_STATUS, s.BAND_STATUS
ORDER  BY s.SYSTEM_CODE, FUNDS DESC;

/* 3. Fundos que ainda não chegaram em 'Enviada FY' / 'Liberada' na última Dt Posição */
SELECT s.DATE_REF, s.DESK, s.SYSTEM_CODE, s.FUND, s.QUOTE_STATUS, s.BAND_STATUS,
       s.PROCESSING_DATE, s.DATE_UPDATE
FROM   dbo.vw_svc_status_validacao AS s WITH (NOLOCK)
WHERE  s.DATE_REF = (SELECT MAX(DATE_REF) FROM dbo.vw_svc_status_validacao WITH (NOLOCK))
  AND  (ISNULL(s.QUOTE_STATUS, '') <> 'Enviada FY' OR ISNULL(s.BAND_STATUS, '') <> 'Liberada')
ORDER  BY s.DESK, s.FUND;

/* 4. Histórico de um fundo (todas as mudanças vistas, mais recentes primeiro) */
SELECT h.DATE_REF, h.SYSTEM_CODE, h.FUND, h.DATE_LOAD, h.CHANGE_TYPE,
       h.OLD_QUOTE_STATUS, h.NEW_QUOTE_STATUS, h.OLD_BAND_STATUS, h.NEW_BAND_STATUS,
       h.OLD_COCKPIT_LOAD, h.NEW_COCKPIT_LOAD, h.OLD_QUOTE_VALUE, h.NEW_QUOTE_VALUE,
       h.PROCESSING_DATE
FROM   dbo.vw_svc_status_validacao_hist AS h WITH (NOLOCK)
WHERE  h.FUND = 'FAC 001'
ORDER  BY h.DATE_REF DESC, h.DATE_LOAD DESC;

/* 5. Mudanças vistas hoje (exceto a primeira aparição de cada fundo/dia) */
SELECT h.DATE_LOAD, h.DATE_REF, h.SYSTEM_CODE, h.FUND,
       h.OLD_QUOTE_STATUS, h.NEW_QUOTE_STATUS, h.OLD_BAND_STATUS, h.NEW_BAND_STATUS,
       h.OLD_QUOTE_VALUE, h.NEW_QUOTE_VALUE
FROM   dbo.vw_svc_status_validacao_hist AS h WITH (NOLOCK)
WHERE  h.DATE_LOAD >= CAST(GETDATE() AS DATE)
  AND  h.CHANGE_TYPE = 'UPDATE'
ORDER  BY h.DATE_LOAD DESC, h.FUND;

/* 6. Primeira vez que cada cota da última Dt Posição foi vista como 'Enviada FY' */
SELECT h.DATE_REF, h.SYSTEM_CODE, h.FUND, MIN(h.DATE_LOAD) AS FIRST_SEEN_SENT
FROM   dbo.vw_svc_status_validacao_hist AS h WITH (NOLOCK)
WHERE  h.DATE_REF = (SELECT MAX(DATE_REF) FROM dbo.vw_svc_status_validacao WITH (NOLOCK))
  AND  h.NEW_QUOTE_STATUS = 'Enviada FY'
GROUP  BY h.DATE_REF, h.SYSTEM_CODE, h.FUND
ORDER  BY FIRST_SEEN_SENT DESC;
