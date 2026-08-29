-- 010_clasificacion_log.sql · Idempotente.
-- Libreta de clasificación del Motor Q v2 (Fase 1: clasificador de grupo).
--
-- DE DONDE SALE (2026-07-30)
--   El clasificador de grupo (features/consulta_v2/) etiqueta cada pregunta libre como
--   jerarquizar | cuantificar | analizar | desconocido (Capa 1 regex, Capa 2 LLM fallback).
--   Principio del audit_motor_clas.md: "anotación sin veredicto = ruido, no aprendizaje" —
--   toda pregunta real queda registrada AQUÍ con su clasificación y un VEREDICTO que le
--   ponen tres jueces: botones ✓/✗ del usuario (confirmado_usuario/corregido_usuario),
--   señales indirectas (sospecha — bandera de prioridad, NO veredicto) y la revisión por
--   lotes del dueño del dominio (confirmado_revision/corregido_revision).
--   Solo los casos VERIFICADOS alimentan el crecimiento de patrones y del golden set.
--
-- POR QUÉ POSTGRES (P1 del plan): los controles 2 y 3 consultan con filtros y ventanas de
--   tiempo; JSONL no da queries y una SQLite nueva no existe en 139. get_engine() ya existe.
--
-- llm_diag (H5): sin él, un timeout por arranque en frío de gemma@139 (load ~342s medido el
--   29-jul) parecería un error del clasificador al revisar el lote. Valores típicos:
--   timeout | conexion | json_invalido | grupo_invalido | NULL (regex o LLM OK).
--
-- NOTA: esta migración NO toca caches del resolver → no exige el reinicio especial de la
--   008/009 (desplegar_version.bat reinicia backends de todos modos).

BEGIN;

CREATE TABLE IF NOT EXISTS core.clasificacion_log (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    usuario TEXT,
    conversation_id TEXT,
    texto_pregunta TEXT NOT NULL,
    grupo_asignado TEXT NOT NULL,          -- jerarquizar|cuantificar|analizar|desconocido
    capa_resolutora TEXT NOT NULL,         -- regex|llm
    patrones_atrapados JSONB,              -- solo si capa=regex
    entidad_cruda TEXT,
    llm_diag TEXT,                         -- H5: timeout|conexion|json_invalido|grupo_invalido|NULL
    veredicto TEXT NOT NULL DEFAULT 'pendiente',
        -- pendiente | sospecha | confirmado_usuario | corregido_usuario
        -- | confirmado_revision | corregido_revision
    grupo_correcto TEXT,                   -- null salvo en correcciones
    fuente_veredicto TEXT,                 -- usuario|indirecta|revision|null
    ts_veredicto TIMESTAMPTZ,
    nota_revision TEXT
);

CREATE INDEX IF NOT EXISTS idx_clas_log_veredicto ON core.clasificacion_log(veredicto, ts);

COMMIT;
