-- 009_map_campo_activo_huecos.sql · Idempotente.
-- Completa 5 huecos del mapeo CAMPO -> ACTIVO usando la BD de DIFERIDAS como fuente.
--
-- DE DONDE SALE (2026-07-23)
--   Al comparar los activos de core.map_campo_activo (52) contra AVM_DATADIF.AREA de la BD
--   ECP_DIFERIDAS (41) se verificó que DIFERIDAS ⊂ Postgres: sus 41 áreas existen todas en el
--   catálogo, 0 huérfanos. Pero DIFERIDAS asigna a un activo 5 campos que aquí no tenían ninguno.
--   DIFERIDAS trae explícito (columna AREA) el dato que a dim_fuente le faltaba.
--
-- EL CASO QUE IMPORTA
--   AULLADOR quedó SIN activo en la 008 por ambigüedad (LISAMA vs LISAMA UNIFICADO), a la espera
--   de veredicto. DIFERIDAS lo asigna a LISAMA de forma consistente -> se cierra esa deuda.
--
-- ⚠ ALCANCE REAL (verificado contra dim_fuente antes de aplicar)
--   Solo 2 de los 5 existen como campo en esta BD y por tanto cambian cifras:
--     · AULLADOR -> LISAMA          (1 fuente, vol_estimado acum. 94.600)
--     · ORIPAYA  -> POB CATATUMBO   (1 fuente, vol_estimado acum. 848.660)
--   Los otros 3 NO existen en core.dim_fuente (búsqueda difusa: no hay variante de grafía):
--     · BUFALO -> CASABE, GALA -> GAL-LLANITO, GALAN -> GAL-LLANITO
--   Se insertan igual, a propósito, como CATÁLOGO: no alteran ningún rollup (un campo sin
--   fuentes aporta 0), y dejan la relación documentada por si esos campos entran más adelante.
--   Si se prefiere un mapeo estrictamente ceñido a dim_fuente, basta borrar esas 3 filas.
--
-- NO SE TOCA: LORITO sigue en AKACIAS (veredicto del usuario, 008). DIFERIDAS lo pone en CPO-09
--   -> discrepancia CONOCIDA y pendiente de decisión, deliberadamente NO resuelta aquí.
--
-- ⚠ Tras aplicar hay que REINICIAR los backends: el resolver cachea _INDEX/_FUENTE_SETS al arranque.

BEGIN;

INSERT INTO core.map_campo_activo (campo_norm, campo, activo) VALUES
    ('AULLADOR', 'AULLADOR', 'LISAMA'),          -- real: cierra la ambigüedad de la 008
    ('ORIPAYA',  'ORIPAYA',  'POB CATATUMBO'),   -- real
    ('BUFALO',   'BUFALO',   'CASABE'),          -- catálogo: no existe hoy en dim_fuente
    ('GALA',     'GALA',     'GAL-LLANITO'),     -- catálogo: no existe hoy en dim_fuente
    ('GALAN',    'GALAN',    'GAL-LLANITO')      -- catálogo: no existe hoy en dim_fuente
ON CONFLICT (campo_norm) DO NOTHING;

COMMIT;
