-- 006_ix_tabla_hoja_covering.sql
-- Indice para el desglose de hojas/tablas por reporte (endpoint GET /tablas/arbol/<reporte_id>,
-- pestana Control "Reportes Ingeridos"). Sin el, esa consulta hacia un seq scan sobre
-- core.fact_tabla_hoja (50M+ filas con el corpus real) -> ~16s por reporte y la vista colgaba.
-- Con el indice el desglose por reporte baja a ~0.2s.
--
-- Idempotente (IF NOT EXISTS): si la BD se restauro desde un backup que YA trae el indice,
-- esto es un no-op instantaneo. Si se reconstruye desde el DDL (BD vacia), el indice se crea
-- al instante (tabla sin filas). NO se usa CONCURRENTLY a proposito: solo hace falta cuando se
-- crea en caliente sobre la tabla llena (caso dev, ya hecho); en un deploy/restore no aplica.
CREATE INDEX IF NOT EXISTS ix_tabla_hoja_covering
    ON core.fact_tabla_hoja USING btree (reporte_id, hoja, tabla_idx, tabla_label);
