-- 003_fact_tabla_hoja.sql — tabla GENÉRICA para tablas modeladas de cualquier hoja (formato largo).
-- dims JSONB guarda las dimensiones variables por hoja/tabla (p.ej. {"area":"BORANDA","vice":"VFS",...}).
CREATE TABLE IF NOT EXISTS core.fact_tabla_hoja (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reporte_id  INTEGER NOT NULL REFERENCES core.config_reporte(reporte_id),
    hoja        TEXT    NOT NULL,
    tabla_idx   INTEGER NOT NULL,
    tabla_label TEXT    NOT NULL,
    dims        JSONB   NOT NULL DEFAULT '{}'::jsonb,
    fecha       DATE    NOT NULL,
    valor       NUMERIC
);
CREATE INDEX IF NOT EXISTS ix_tabla_hoja ON core.fact_tabla_hoja (reporte_id, hoja, tabla_idx);
-- Retirar la tabla específica anterior (su loader se reemplaza por el genérico).
DROP TABLE IF EXISTS core.fact_p50_quemado;
