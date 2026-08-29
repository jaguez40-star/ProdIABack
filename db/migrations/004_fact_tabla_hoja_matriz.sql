-- 004_fact_tabla_hoja_matriz.sql — soporte de tablas MATRICIALES en fact_tabla_hoja.
-- Las tablas cuyas columnas son categorías (no fechas) se guardan con fecha = NULL y
-- dims = {"fila": <etiqueta de fila>, "columna": <etiqueta de columna>}.
-- Por eso 'fecha' deja de ser NOT NULL.
ALTER TABLE core.fact_tabla_hoja ALTER COLUMN fecha DROP NOT NULL;
