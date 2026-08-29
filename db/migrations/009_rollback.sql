-- 009_rollback.sql -- revierte los 5 huecos agregados por la 009.
BEGIN;
DELETE FROM core.map_campo_activo
 WHERE campo_norm IN ('AULLADOR','ORIPAYA','BUFALO','GALA','GALAN');
COMMIT;
