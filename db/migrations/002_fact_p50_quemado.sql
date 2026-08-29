-- 002_fact_p50_quemado.sql
-- P50 Quemado: 2 tablas de la hoja "P50 Quemado <año> ECP y Filiales", formato largo (unpivot 12 meses).
--   tabla='quemado'  -> dims: escenario, producto, vice, activos, area
--   tabla='filiales' -> dims: producto, empresa  (vice/activos/area NULL)
-- Subtotales y "Promedio Año" NO se ingieren (decisión del proyecto).
CREATE TABLE IF NOT EXISTS core.fact_p50_quemado (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reporte_id  INTEGER NOT NULL REFERENCES core.config_reporte(reporte_id),
    tabla       TEXT    NOT NULL,           -- 'quemado' | 'filiales'
    escenario   TEXT,
    producto    TEXT,
    vice        TEXT,
    activos     TEXT,
    area        TEXT,
    empresa     TEXT,
    fecha       DATE    NOT NULL,
    valor       NUMERIC,
    CONSTRAINT uk_p50 UNIQUE NULLS NOT DISTINCT
        (reporte_id, tabla, escenario, producto, vice, activos, area, empresa, fecha)
);
CREATE INDEX IF NOT EXISTS ix_p50_reporte ON core.fact_p50_quemado (reporte_id);
