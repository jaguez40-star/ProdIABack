-- 005: extiende core.fact_comentarios_produccion con los 2 campos de comentario adicionales de la hoja
-- COMENTARIOS (E = COMENTARIO PROGRAMA, G = comentario extra). Idempotente y re-ejecutable.
ALTER TABLE core.fact_comentarios_produccion
    ADD COLUMN IF NOT EXISTS comentario_programa text,
    ADD COLUMN IF NOT EXISTS comentario_extra    text;
