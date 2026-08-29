-- 001_ingesta_job.sql — tabla de jobs de ingesta (orquestación para UI).
-- Idempotente: CREATE TABLE IF NOT EXISTS. Esquema core, convenciones del DDL v2.
CREATE TABLE IF NOT EXISTS core.ingesta_job (
    job_id          BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    estado          VARCHAR(12)  NOT NULL DEFAULT 'PENDIENTE'
                                 CHECK (estado IN ('PENDIENTE','EN_PROCESO','COMPLETADO','ERROR')),
    total           INT          NOT NULL DEFAULT 0,
    procesados      INT          NOT NULL DEFAULT 0,
    errores         INT          NOT NULL DEFAULT 0,
    archivos        JSONB        NOT NULL DEFAULT '[]'::jsonb,   -- nombres solicitados
    resultado       JSONB        NOT NULL DEFAULT '[]'::jsonb,   -- [{archivo, reporte_id?, tipo?, error?}]
    mensaje         TEXT,
    creado_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    actualizado_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
