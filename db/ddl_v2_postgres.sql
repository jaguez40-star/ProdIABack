-- ============================================================================
-- MODELO ER v9 → DDL v2 — PostgreSQL — Reporte Diario de Producción (Robustez V2.0)
-- ============================================================================
-- Objetivo: ingerir y PRESERVAR la información de TODOS los .xlsm (decisión D3,
-- "degradación elegante"), no solo los archivos "New" con capa raw.
--
-- Arquitectura Medallion en 2 esquemas:
--   bronze.*  → staging crudo, tal cual viene cada hoja (preserva todo).
--   core.*    → modelo estrella dimensional (Silver/Gold) + metadatos de ingesta.
--
-- Cambios clave vs DDL v9 (MySQL):
--   1. Sintaxis PostgreSQL (IDENTITY, NUMERIC, índices/constraints separados,
--      EXTRACT en lugar de YEAR()/MONTH()).
--   2. Capa Bronze nueva (bdp_dia/mes/programa + landing JSONB genérico).
--   3. config_reporte extendido con linaje/cobertura (archivo, tipo, tiene_raw, nivel_detalle).
--   4. ingesta_log nuevo (data_version / freshness).
--   5. Claves únicas naturales en los 3 facts ECP → idempotencia vía ON CONFLICT ("última gana").
--      VALIDADAS contra el archivo de 125 MB (uk_dia/uk_mes/uk_prog → 0 colisiones).
--   6. fact_programa_ecp gana columnas area/campo (el raw las trae; IDBDP puede venir vacío);
--      uk_prog incluye fuente_id (IDBDP) con NULLS NOT DISTINCT (validado).
--   7. fact_dia/fact_mes ganan columna `producto` (PRODUCTO específico ≠ TIPOPRODUCTO): una
--      misma fuente produce varios PRODUCTOs el mismo día → es grano del fact, no atributo de dim_fuente.
--   8. BPDAC_5 y atributos extra de BDP_datos_mes se PRESERVAN en bronze, no entran al fact.
--   Motor objetivo: PostgreSQL 15+ (por UNIQUE NULLS NOT DISTINCT y MERGE opcional).
--
--   Base de datos destino: daily_report_prod
--   Crear (desde una conexión a 'postgres') y luego ejecutar este script conectado a ella:
--       CREATE DATABASE daily_report_prod;
--       \c daily_report_prod
--       \i db/ddl_v2_postgres.sql
--   o vía CLI:
--       createdb -U postgres daily_report_prod
--       psql -U postgres -d daily_report_prod -f db/ddl_v2_postgres.sql
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS core;

-- ============================================================================
-- 0. BRONZE — staging crudo (todo como TEXT; preserva lo que cada archivo trae)
-- ============================================================================
-- Lineaje común a todas las tablas bronze: reporte_id, archivo, fila de origen.

-- 0.1 BDP_datos_dia  (solo archivos "New"; 30 columnas, grano completo, ESCENARIO=REAL)
CREATE TABLE bronze.bdp_datos_dia (
    bronze_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reporte_id    INT,
    archivo       TEXT,
    fila_origen   INT,
    concepto      TEXT, socio TEXT, operador TEXT, tipocontrato TEXT, contrato TEXT,
    fuente        TEXT, idbdp TEXT, fuentecontrato TEXT, fecha TEXT, mes TEXT, anio TEXT,
    escenario     TEXT, propietario TEXT, grupoprod TEXT, producto TEXT, tipoproducto TEXT,
    gerencia      TEXT, modalidad TEXT, operacion TEXT, nacionalidad TEXT,
    grupo1        TEXT, grupo2 TEXT, grupo3 TEXT,
    volumen       TEXT, porcentaje TEXT, vice TEXT, activos TEXT,
    voldismez     TEXT, vol_estimado TEXT, promedio TEXT,
    cargado_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 0.2 BDP_datos_mes  (solo "New"; 59 columnas; incluye BPDAC_5 y atributos extra preservados)
CREATE TABLE bronze.bdp_datos_mes (
    bronze_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reporte_id    INT,
    archivo       TEXT,
    fila_origen   INT,
    concepto TEXT, socio TEXT, ba_id TEXT, operador TEXT, grupooperador TEXT,
    tipocontrato TEXT, contrato TEXT, fuente TEXT, idbdp TEXT, fuentecontratoplot TEXT,
    fuentecontrato TEXT, fecha TEXT, mes TEXT, anio TEXT, escenario TEXT, proceso TEXT,
    row_changed_by TEXT, propietario TEXT, grupoprod TEXT, producto TEXT, tipoproducto TEXT,
    negocio TEXT, nuevagerencia TEXT, superintendencia TEXT, tag TEXT, tipofuente TEXT,
    tagdescripcion TEXT, fechaefprop TEXT, fechaexprop TEXT, fechaefpden TEXT, fechaexpden TEXT,
    negociovpr TEXT, gerencia TEXT, modalidad TEXT, operacion TEXT, tipocrudo TEXT,
    nacionalidad TEXT, grupo1 TEXT, grupo2 TEXT, grupo3 TEXT,
    volumen TEXT, porcentaje TEXT, voldismez TEXT, bpd_m TEXT, bpda_ac TEXT, bpdac_5 TEXT,
    bpd_a TEXT, bpdeq_m TEXT, blseq TEXT, bpdeq_a TEXT,
    nodo TEXT, diluyente TEXT, linea_estrategica TEXT, mezcla_siv_gas TEXT,
    producto_yacimiento TEXT, proyeccion TEXT, esc_proy TEXT, vice TEXT, activos TEXT,
    cargado_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 0.3 BDP_Programa  (solo "New"; 14 columnas; 1 versión semanal por archivo)
CREATE TABLE bronze.bdp_programa (
    bronze_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reporte_id    INT,
    archivo       TEXT,
    fila_origen   INT,
    fecha TEXT, vice TEXT, gerencia TEXT, version TEXT, fecha_version TEXT, estado TEXT,
    volumen TEXT, campo TEXT, producto TEXT, area TEXT, idbdp TEXT, contrato TEXT,
    produccion_total TEXT, part_ecp TEXT,
    cargado_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 0.4 Landing genérico (JSONB) — para CUALQUIER otra hoja (filiales, POP, comentarios,
--     INICIO, pivots de los archivos ~30 MB...). Garantiza que NADA de un archivo se pierde,
--     aunque su grano no llegue al star schema.
CREATE TABLE bronze.hoja_landing (
    bronze_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reporte_id  INT,
    archivo     TEXT,
    hoja        TEXT NOT NULL,
    fila_origen INT,
    payload     JSONB NOT NULL,          -- fila completa como {columna: valor}
    cargado_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_landing_reporte ON bronze.hoja_landing (reporte_id);
CREATE INDEX idx_landing_hoja    ON bronze.hoja_landing (hoja);
CREATE INDEX idx_landing_payload ON bronze.hoja_landing USING GIN (payload);

CREATE INDEX idx_bz_dia_reporte ON bronze.bdp_datos_dia (reporte_id);
CREATE INDEX idx_bz_mes_reporte ON bronze.bdp_datos_mes (reporte_id);
CREATE INDEX idx_bz_prg_reporte ON bronze.bdp_programa (reporte_id);

-- ============================================================================
-- 1. CORE — DIMENSIONES COMPARTIDAS
-- ============================================================================

CREATE TABLE core.dim_fecha (
    fecha        DATE        PRIMARY KEY,
    anio         INT         NOT NULL,
    mes          INT         NOT NULL,
    dia          INT         NOT NULL,
    trimestre    INT         NOT NULL,
    dia_semana   INT         NOT NULL,   -- 1=Lun .. 7=Dom (ISODOW)
    semana_mes   INT         NOT NULL    -- 1-5
);

CREATE TABLE core.dim_tipo_producto (
    tipo_producto_id  INT          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre            VARCHAR(50)  NOT NULL UNIQUE      -- CRUDO | GAS | BLANCOS
);

CREATE TABLE core.dim_tipo_registro (
    tipo_id   INT          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre    VARCHAR(20)  NOT NULL UNIQUE              -- Real | Programa
);

CREATE TABLE core.dim_empresa (
    empresa_id  INT          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre      VARCHAR(50)  NOT NULL UNIQUE            -- Hocol | America | Permian
);

-- config_reporte EXTENDIDO con linaje/cobertura (D3). 1 fila por archivo ingerido.
CREATE TABLE core.config_reporte (
    reporte_id      INT          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fecha_reporte   DATE         NOT NULL UNIQUE,
    fecha_corte     DATE,
    mes_inicio      DATE,
    mes_fin         DATE,
    version_semana  INT,
    anio_inicio     INT,
    dias_anio       INT,
    -- linaje / cobertura -----------------------------------------------------
    archivo_nombre  TEXT,
    tipo_archivo    VARCHAR(10)  CHECK (tipo_archivo IN ('NEW','STD')),
    tiene_raw       BOOLEAN      NOT NULL DEFAULT FALSE,
    nivel_detalle   VARCHAR(12)  NOT NULL DEFAULT 'SIN_ECP'
                                 CHECK (nivel_detalle IN ('FULL','AGREGADO','SIN_ECP')),
    hash_archivo    TEXT,        -- para evitar reprocesar el mismo archivo
    ingested_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ============================================================================
-- 2. CORE — DIMENSIONES BDP (compartidas día + mes + programa)
-- ============================================================================

-- dim_fuente: PK natural = IDBDP. SCD "última gana" (updated_at + reporte_id de origen).
CREATE TABLE core.dim_fuente (
    fuente_id            INT           PRIMARY KEY,        -- = IDBDP (entero)
    nombre               VARCHAR(150),                     -- FUENTE
    campo                VARCHAR(150),                     -- Campo (BDP_Programa)
    contrato             VARCHAR(150),
    tipo_contrato        VARCHAR(50),
    operador             VARCHAR(100),
    modalidad            VARCHAR(50),
    operacion            VARCHAR(50),
    nacionalidad         VARCHAR(50),
    gerencia             VARCHAR(20),
    grupo1               VARCHAR(100),                     -- = AREA
    grupo2               VARCHAR(50),
    grupo3               VARCHAR(50),
    activos              VARCHAR(80),
    -- OJO: PRODUCTO (mezcla específica) NO es atributo 1:1 de la fuente — una misma fuente
    -- produce varios PRODUCTOs el mismo día. Por eso vive en los facts, no aquí (validado).
    fuente_contrato      VARCHAR(200),
    reporte_id_origen    INT,                              -- último archivo que lo actualizó
    updated_at           TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE TABLE core.dim_vicepresidencia (
    vice_id          INT          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo           VARCHAR(5)   NOT NULL UNIQUE,          -- VRC|VRO|VAO|VFS|VPI|VEX|VAS
    nombre_completo  VARCHAR(100)
);

CREATE TABLE core.dim_socio (
    socio_id  INT          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre    VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE core.dim_concepto (
    concepto_id  INT          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre       VARCHAR(30)  NOT NULL UNIQUE              -- DERECO|PROPIEDAD|REGALIADISP
);

CREATE TABLE core.dim_escenario (
    escenario_id  INT          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre        VARCHAR(20)  NOT NULL UNIQUE             -- REAL|OPERATIVO|PPTO|CONTABLE
);

CREATE TABLE core.dim_proceso (
    proceso_id  INT          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre      VARCHAR(30)  NOT NULL UNIQUE               -- PROD_TOTAL|VENTA-GRAVABLE|...
);

-- ============================================================================
-- 3. CORE — HECHOS ECOPETROL (solo se llenan desde archivos con raw)
-- ============================================================================

CREATE TABLE core.fact_produccion_dia_ecp (
    id                BIGINT         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fecha             DATE           NOT NULL,
    fuente_id         INT            NOT NULL,
    vice_id           INT            NOT NULL,
    socio_id          INT            NOT NULL,
    concepto_id       INT            NOT NULL,
    tipo_producto_id  INT            NOT NULL,
    producto          VARCHAR(60)    NOT NULL DEFAULT '',   -- PRODUCTO específico (GLP, GASOLINA, mezcla...)
    grupo_prod        VARCHAR(20)    NOT NULL DEFAULT '',   -- ECOPETROL|SOCIOS
    propietario       VARCHAR(20)    NOT NULL DEFAULT '',
    volumen           NUMERIC(16,4),
    porcentaje        NUMERIC(10,6),
    voldismez         NUMERIC(16,4),
    vol_estimado      NUMERIC(16,4),
    promedio          NUMERIC(16,4),
    reporte_id        INT            NOT NULL,
    FOREIGN KEY (fecha)            REFERENCES core.dim_fecha(fecha),
    FOREIGN KEY (fuente_id)        REFERENCES core.dim_fuente(fuente_id),
    FOREIGN KEY (vice_id)          REFERENCES core.dim_vicepresidencia(vice_id),
    FOREIGN KEY (socio_id)         REFERENCES core.dim_socio(socio_id),
    FOREIGN KEY (concepto_id)      REFERENCES core.dim_concepto(concepto_id),
    FOREIGN KEY (tipo_producto_id) REFERENCES core.dim_tipo_producto(tipo_producto_id),
    FOREIGN KEY (reporte_id)       REFERENCES core.config_reporte(reporte_id),
    -- clave natural para idempotencia (ON CONFLICT → "última gana"). NO incluye reporte_id:
    -- los cortes que se solapan entre archivos se deduplican (gana el último cargado).
    CONSTRAINT uk_dia UNIQUE (fecha, fuente_id, concepto_id, socio_id,
                              tipo_producto_id, producto, grupo_prod, propietario)
);
CREATE INDEX idx_dia_fecha     ON core.fact_produccion_dia_ecp (fecha);
CREATE INDEX idx_dia_fuente    ON core.fact_produccion_dia_ecp (fuente_id);
CREATE INDEX idx_dia_vice      ON core.fact_produccion_dia_ecp (vice_id);
CREATE INDEX idx_dia_tipoprod  ON core.fact_produccion_dia_ecp (tipo_producto_id);
CREATE INDEX idx_dia_reporte   ON core.fact_produccion_dia_ecp (reporte_id);

CREATE TABLE core.fact_produccion_mes_ecp (
    id                BIGINT         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fecha             DATE           NOT NULL,               -- fin de mes
    fuente_id         INT            NOT NULL,
    vice_id           INT            NOT NULL,
    socio_id          INT            NOT NULL,
    concepto_id       INT            NOT NULL,
    tipo_producto_id  INT            NOT NULL,
    producto          VARCHAR(60)    NOT NULL DEFAULT '',   -- PRODUCTO específico
    escenario_id      INT            NOT NULL,
    proceso_id        INT            NOT NULL,
    grupo_prod        VARCHAR(20)    NOT NULL DEFAULT '',
    negocio           VARCHAR(30),
    volumen           NUMERIC(16,4),
    porcentaje        NUMERIC(10,6),
    voldismez         NUMERIC(16,4),
    bpd_m             NUMERIC(16,4),
    bpda_ac           NUMERIC(16,4),
    bpd_a             NUMERIC(16,4),
    bpdeq_m           NUMERIC(16,4),
    blseq             NUMERIC(16,4),
    bpdeq_a           NUMERIC(16,4),
    -- NOTA: BPDAC_5 y demás atributos extra del raw quedan en bronze.bdp_datos_mes, no aquí.
    reporte_id        INT            NOT NULL,
    FOREIGN KEY (fecha)            REFERENCES core.dim_fecha(fecha),
    FOREIGN KEY (fuente_id)        REFERENCES core.dim_fuente(fuente_id),
    FOREIGN KEY (vice_id)          REFERENCES core.dim_vicepresidencia(vice_id),
    FOREIGN KEY (socio_id)         REFERENCES core.dim_socio(socio_id),
    FOREIGN KEY (concepto_id)      REFERENCES core.dim_concepto(concepto_id),
    FOREIGN KEY (tipo_producto_id) REFERENCES core.dim_tipo_producto(tipo_producto_id),
    FOREIGN KEY (escenario_id)     REFERENCES core.dim_escenario(escenario_id),
    FOREIGN KEY (proceso_id)       REFERENCES core.dim_proceso(proceso_id),
    FOREIGN KEY (reporte_id)       REFERENCES core.config_reporte(reporte_id),
    CONSTRAINT uk_mes UNIQUE (fecha, fuente_id, concepto_id, socio_id, tipo_producto_id,
                              producto, escenario_id, proceso_id)
);
CREATE INDEX idx_mes_fecha     ON core.fact_produccion_mes_ecp (fecha);
CREATE INDEX idx_mes_fuente    ON core.fact_produccion_mes_ecp (fuente_id);
CREATE INDEX idx_mes_escenario ON core.fact_produccion_mes_ecp (escenario_id);
CREATE INDEX idx_mes_proceso   ON core.fact_produccion_mes_ecp (proceso_id);
CREATE INDEX idx_mes_vice      ON core.fact_produccion_mes_ecp (vice_id);
CREATE INDEX idx_mes_tipoprod  ON core.fact_produccion_mes_ecp (tipo_producto_id);
CREATE INDEX idx_mes_reporte   ON core.fact_produccion_mes_ecp (reporte_id);

CREATE TABLE core.fact_programa_ecp (
    id                BIGINT         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fecha             DATE           NOT NULL,
    vice_id           INT            NOT NULL,
    tipo_producto_id  INT            NOT NULL,
    fuente_id         INT,                                   -- IDBDP puede venir vacío
    area              VARCHAR(100)   NOT NULL DEFAULT '',    -- AREA (raw)
    campo             VARCHAR(100)   NOT NULL DEFAULT '',    -- Campo (raw)
    version           VARCHAR(10)    NOT NULL DEFAULT '',    -- V39, ...
    fecha_version     DATE,
    volumen           NUMERIC(16,4),                         -- porción ECP
    produccion_total  NUMERIC(16,4),
    part_ecp          NUMERIC(10,4),
    reporte_id        INT            NOT NULL,
    FOREIGN KEY (fecha)            REFERENCES core.dim_fecha(fecha),
    FOREIGN KEY (vice_id)          REFERENCES core.dim_vicepresidencia(vice_id),
    FOREIGN KEY (tipo_producto_id) REFERENCES core.dim_tipo_producto(tipo_producto_id),
    FOREIGN KEY (fuente_id)        REFERENCES core.dim_fuente(fuente_id),
    FOREIGN KEY (reporte_id)       REFERENCES core.config_reporte(reporte_id),
    -- la VERSION sí entra en la clave (cada versión semanal es una fila legítima).
    -- fuente_id (IDBDP) es necesario para unicidad (validado); NULLS NOT DISTINCT por si viene vacío.
    CONSTRAINT uk_prog UNIQUE NULLS NOT DISTINCT
        (fecha, vice_id, tipo_producto_id, area, campo, version, fuente_id)
);
CREATE INDEX idx_prog_fecha   ON core.fact_programa_ecp (fecha);
CREATE INDEX idx_prog_vice    ON core.fact_programa_ecp (vice_id);
CREATE INDEX idx_prog_version ON core.fact_programa_ecp (version);
CREATE INDEX idx_prog_reporte ON core.fact_programa_ecp (reporte_id);

-- ============================================================================
-- 4. CORE — HECHOS FILIALES (se llenan de TODOS los archivos: New y ~30 MB)
-- ============================================================================

CREATE TABLE core.fact_produccion_diaria (
    id                BIGINT         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    empresa_id        INT            NOT NULL,
    producto_id       INT            NOT NULL,
    tipo_id           INT            NOT NULL,               -- Real | Programa
    fecha             DATE           NOT NULL,
    valor_produccion  NUMERIC(14,2),
    reporte_id        INT            NOT NULL,
    FOREIGN KEY (empresa_id)  REFERENCES core.dim_empresa(empresa_id),
    FOREIGN KEY (producto_id) REFERENCES core.dim_tipo_producto(tipo_producto_id),
    FOREIGN KEY (tipo_id)     REFERENCES core.dim_tipo_registro(tipo_id),
    FOREIGN KEY (fecha)       REFERENCES core.dim_fecha(fecha),
    FOREIGN KEY (reporte_id)  REFERENCES core.config_reporte(reporte_id),
    CONSTRAINT uk_fil UNIQUE (empresa_id, producto_id, tipo_id, fecha)  -- última gana
);
CREATE INDEX idx_fil_fecha   ON core.fact_produccion_diaria (fecha);
CREATE INDEX idx_fil_empresa ON core.fact_produccion_diaria (empresa_id);
CREATE INDEX idx_fil_reporte ON core.fact_produccion_diaria (reporte_id);

CREATE TABLE core.fact_plan_mensual (
    id           BIGINT         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    empresa_id   INT            NOT NULL,
    anio         INT            NOT NULL,
    mes          INT            NOT NULL,
    ppto_kbd     NUMERIC(12,3),
    pop_kbd      NUMERIC(12,3),
    segmento     VARCHAR(20)    NOT NULL DEFAULT 'Filiales',  -- Filiales | Exploración
    reporte_id   INT            NOT NULL,
    FOREIGN KEY (empresa_id) REFERENCES core.dim_empresa(empresa_id),
    FOREIGN KEY (reporte_id) REFERENCES core.config_reporte(reporte_id),
    CONSTRAINT uk_plan UNIQUE (empresa_id, anio, mes, segmento)
);

CREATE TABLE core.fact_promedio_validado (
    id                  BIGINT         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    empresa_id          INT            NOT NULL,
    producto_id         INT            NOT NULL,
    anio                INT            NOT NULL,
    mes                 INT            NOT NULL,
    promedio_validado   NUMERIC(14,2),
    reporte_id          INT            NOT NULL,
    FOREIGN KEY (empresa_id)  REFERENCES core.dim_empresa(empresa_id),
    FOREIGN KEY (producto_id) REFERENCES core.dim_tipo_producto(tipo_producto_id),
    FOREIGN KEY (reporte_id)  REFERENCES core.config_reporte(reporte_id),
    CONSTRAINT uk_prom UNIQUE (empresa_id, producto_id, anio, mes)
);

-- ============================================================================
-- 5. CORE — COMENTARIOS (texto libre; de TODOS los archivos)
-- ============================================================================
CREATE TABLE core.fact_comentarios_produccion (
    id                BIGINT         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tipo_producto_id  INT,
    activos           VARCHAR(80),
    area              VARCHAR(100),
    comentario        TEXT           NOT NULL,
    reporte_id        INT            NOT NULL,
    comentario_programa TEXT,
    comentario_extra    TEXT,
    FOREIGN KEY (tipo_producto_id) REFERENCES core.dim_tipo_producto(tipo_producto_id),
    FOREIGN KEY (reporte_id)       REFERENCES core.config_reporte(reporte_id)
);
CREATE INDEX idx_com_activos ON core.fact_comentarios_produccion (activos);
CREATE INDEX idx_com_reporte ON core.fact_comentarios_produccion (reporte_id);

-- ============================================================================
-- 6. CORE — OPERACIÓN / FRESHNESS (data_version) y KPIs precalculados (Silver)
-- ============================================================================
CREATE TABLE core.ingesta_log (
    id              BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reporte_id      INT          REFERENCES core.config_reporte(reporte_id),
    archivo_nombre  TEXT,
    hoja            TEXT,
    tabla_destino   TEXT,
    filas_leidas    INT,
    filas_insertadas INT,
    filas_actualizadas INT,
    filas_descartadas  INT,
    estado          VARCHAR(10)  CHECK (estado IN ('OK','PARCIAL','ERROR')),
    mensaje         TEXT,
    fecha_proceso   TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_ingesta_reporte ON core.ingesta_log (reporte_id);

CREATE TABLE core.kpis_precalculados (
    id            BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kpi           VARCHAR(60)  NOT NULL,
    dimension     JSONB        NOT NULL DEFAULT '{}',   -- {vice, activo, producto, ...}
    fecha         DATE,
    valor         NUMERIC(18,6),
    unidad        VARCHAR(20),
    reporte_id    INT          REFERENCES core.config_reporte(reporte_id),
    calculado_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uk_kpi UNIQUE (kpi, dimension, fecha)
);
CREATE INDEX idx_kpi_fecha ON core.kpis_precalculados (fecha);

-- ============================================================================
-- 7. VISTAS FILIALES
-- ============================================================================
CREATE VIEW core.vw_proyeccion_diaria AS
SELECT
    f.fecha,
    e.nombre  AS empresa,
    p.nombre  AS producto,
    r.valor_produccion     AS valor_real,
    prog.valor_produccion  AS valor_programa,
    COALESCE(r.valor_produccion, prog.valor_produccion) AS valor_proyeccion,
    AVG(COALESCE(r.valor_produccion, prog.valor_produccion))
      OVER (PARTITION BY e.empresa_id, p.tipo_producto_id,
            EXTRACT(YEAR FROM f.fecha), EXTRACT(MONTH FROM f.fecha)) AS promedio_mes
FROM core.dim_fecha f
CROSS JOIN core.dim_empresa e
CROSS JOIN core.dim_tipo_producto p
LEFT JOIN core.fact_produccion_diaria r
    ON r.fecha = f.fecha AND r.empresa_id = e.empresa_id
   AND r.producto_id = p.tipo_producto_id AND r.tipo_id = 1
LEFT JOIN core.fact_produccion_diaria prog
    ON prog.fecha = f.fecha AND prog.empresa_id = e.empresa_id
   AND prog.producto_id = p.tipo_producto_id AND prog.tipo_id = 2;

CREATE VIEW core.vw_resumen_mensual_filiales AS
SELECT
    e.nombre                       AS empresa,
    EXTRACT(YEAR  FROM f.fecha)::int AS anio,
    EXTRACT(MONTH FROM f.fecha)::int AS mes,
    pm.ppto_kbd,
    pm.pop_kbd,
    AVG(COALESCE(r.valor_produccion, prog.valor_produccion)) / 1000 AS proy_kbd,
    AVG(r.valor_produccion) / 1000                                   AS real_kbd,
    (AVG(COALESCE(r.valor_produccion, prog.valor_produccion)) / 1000) - pm.ppto_kbd AS proy_vs_ppto,
    (AVG(COALESCE(r.valor_produccion, prog.valor_produccion)) / 1000) - pm.pop_kbd  AS proy_vs_pop
FROM core.dim_empresa e
JOIN core.fact_produccion_diaria r ON r.empresa_id = e.empresa_id AND r.tipo_id = 1
JOIN core.dim_fecha f ON f.fecha = r.fecha
LEFT JOIN core.fact_produccion_diaria prog
    ON prog.empresa_id = e.empresa_id AND prog.tipo_id = 2
   AND prog.fecha = r.fecha AND prog.producto_id = r.producto_id
LEFT JOIN core.fact_plan_mensual pm
    ON pm.empresa_id = e.empresa_id
   AND pm.anio = EXTRACT(YEAR FROM f.fecha)::int
   AND pm.mes  = EXTRACT(MONTH FROM f.fecha)::int
   AND pm.segmento = 'Filiales'
GROUP BY e.nombre, EXTRACT(YEAR FROM f.fecha), EXTRACT(MONTH FROM f.fecha),
         pm.ppto_kbd, pm.pop_kbd;

CREATE VIEW core.vw_seguimiento_semanal AS
SELECT
    e.nombre                       AS empresa,
    EXTRACT(YEAR  FROM f.fecha)::int AS anio,
    EXTRACT(MONTH FROM f.fecha)::int AS mes,
    f.semana_mes,
    AVG(CASE WHEN fp.tipo_id = 2 THEN fp.valor_produccion END) / 1000 AS prog_kbd,
    AVG(CASE WHEN fp.tipo_id = 1 THEN fp.valor_produccion END) / 1000 AS real_kbd,
    (AVG(CASE WHEN fp.tipo_id = 1 THEN fp.valor_produccion END)
   - AVG(CASE WHEN fp.tipo_id = 2 THEN fp.valor_produccion END)) / 1000 AS diferencia_kbd
FROM core.fact_produccion_diaria fp
JOIN core.dim_empresa e ON e.empresa_id = fp.empresa_id
JOIN core.dim_fecha f   ON f.fecha = fp.fecha
GROUP BY e.nombre, EXTRACT(YEAR FROM f.fecha), EXTRACT(MONTH FROM f.fecha), f.semana_mes;

-- ============================================================================
-- 8. VISTAS REPORTE WHATSAPP
-- ============================================================================
CREATE VIEW core.vw_wa_resumen_corporativo AS
SELECT 'ECOPETROL' AS segmento, tp.nombre AS tipo_producto, f.fecha,
       SUM(e.vol_estimado) / 1000 AS real_dia_kbd
FROM core.fact_produccion_dia_ecp e
JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = e.tipo_producto_id
JOIN core.dim_fecha f ON f.fecha = e.fecha
WHERE e.grupo_prod = 'ECOPETROL'
GROUP BY tp.nombre, f.fecha
UNION ALL
SELECT 'FILIALES' AS segmento, p.nombre AS tipo_producto, f.fecha,
       SUM(fp.valor_produccion) / 1000 AS real_dia_kbd
FROM core.fact_produccion_diaria fp
JOIN core.dim_tipo_producto p ON p.tipo_producto_id = fp.producto_id
JOIN core.dim_fecha f ON f.fecha = fp.fecha
WHERE fp.tipo_id = 1
GROUP BY p.nombre, f.fecha;

CREATE VIEW core.vw_wa_produccion_por_activo AS
SELECT
    fu.grupo1  AS activo,
    fu.activos AS clasificacion,
    v.codigo   AS vice,
    f.fecha,
    SUM(CASE WHEN e.grupo_prod = 'ECOPETROL' THEN e.vol_estimado END) AS real_dia_bpd,
    AVG(SUM(CASE WHEN e.grupo_prod = 'ECOPETROL' THEN e.vol_estimado END))
      OVER (PARTITION BY fu.grupo1, EXTRACT(YEAR FROM f.fecha), EXTRACT(MONTH FROM f.fecha)
            ORDER BY f.fecha ROWS UNBOUNDED PRECEDING) AS real_acum_mes_bpd
FROM core.fact_produccion_dia_ecp e
JOIN core.dim_fuente fu ON fu.fuente_id = e.fuente_id
JOIN core.dim_vicepresidencia v ON v.vice_id = e.vice_id
JOIN core.dim_fecha f ON f.fecha = e.fecha
GROUP BY fu.grupo1, fu.activos, v.codigo, f.fecha, EXTRACT(YEAR FROM f.fecha), EXTRACT(MONTH FROM f.fecha);

CREATE VIEW core.vw_wa_filiales_equivalente AS
SELECT
    em.nombre AS empresa,
    f.fecha,
    SUM(fp.valor_produccion) AS real_dia_bpd,
    AVG(SUM(fp.valor_produccion))
      OVER (PARTITION BY em.empresa_id, EXTRACT(YEAR FROM f.fecha), EXTRACT(MONTH FROM f.fecha)
            ORDER BY f.fecha ROWS UNBOUNDED PRECEDING) AS real_acum_mes_bpd,
    pm.pop_kbd * 1000 AS pop_mes_bpd
FROM core.fact_produccion_diaria fp
JOIN core.dim_empresa em ON em.empresa_id = fp.empresa_id
JOIN core.dim_fecha f ON f.fecha = fp.fecha
LEFT JOIN core.fact_plan_mensual pm
    ON pm.empresa_id = em.empresa_id
   AND pm.anio = EXTRACT(YEAR FROM f.fecha)::int
   AND pm.mes  = EXTRACT(MONTH FROM f.fecha)::int
   AND pm.segmento = 'Filiales'
WHERE fp.tipo_id = 1
GROUP BY em.nombre, em.empresa_id, f.fecha,
         EXTRACT(YEAR FROM f.fecha), EXTRACT(MONTH FROM f.fecha), pm.pop_kbd;

-- ============================================================================
-- 9. VISTA P50 QUEMADO
-- ============================================================================
CREATE VIEW core.vw_p50_quemado AS
SELECT
    tp.nombre AS producto,
    v.codigo  AS vice,
    fu.activos,
    fu.grupo1 AS area,
    f.fecha,
    EXTRACT(YEAR  FROM f.fecha)::int AS anio,
    EXTRACT(MONTH FROM f.fecha)::int AS mes,
    SUM(m.volumen) AS p50_volumen,
    SUM(m.bpdeq_m) AS p50_bpdeq,
    AVG(SUM(m.volumen))
      OVER (PARTITION BY tp.nombre, v.codigo, fu.activos, fu.grupo1,
            EXTRACT(YEAR FROM f.fecha)) AS promedio_anual
FROM core.fact_produccion_mes_ecp m
JOIN core.dim_escenario es ON es.escenario_id = m.escenario_id
JOIN core.dim_tipo_producto tp ON tp.tipo_producto_id = m.tipo_producto_id
JOIN core.dim_vicepresidencia v ON v.vice_id = m.vice_id
JOIN core.dim_fuente fu ON fu.fuente_id = m.fuente_id
JOIN core.dim_fecha f ON f.fecha = m.fecha
WHERE es.nombre = 'PPTO' AND m.grupo_prod = 'ECOPETROL'
GROUP BY tp.nombre, v.codigo, fu.activos, fu.grupo1, f.fecha,
         EXTRACT(YEAR FROM f.fecha), EXTRACT(MONTH FROM f.fecha)
ORDER BY v.codigo, fu.activos, fu.grupo1, f.fecha;

-- ============================================================================
-- 10. SEMILLAS — dimensiones pequeñas
-- ============================================================================
INSERT INTO core.dim_tipo_producto (nombre) VALUES ('CRUDO'), ('GAS'), ('BLANCOS');
INSERT INTO core.dim_tipo_registro (nombre) VALUES ('Real'), ('Programa');
INSERT INTO core.dim_empresa (nombre) VALUES ('Hocol'), ('America'), ('Permian');
INSERT INTO core.dim_concepto (nombre) VALUES ('DERECO'), ('PROPIEDAD'), ('REGALIADISP');
INSERT INTO core.dim_escenario (nombre) VALUES ('REAL'), ('OPERATIVO'), ('PPTO'), ('CONTABLE');
INSERT INTO core.dim_proceso (nombre) VALUES
    ('PROD_TOTAL'), ('VENTA-GRAVABLE'), ('CONSUMO'), ('GAS CONVERTIDO MME');
INSERT INTO core.dim_vicepresidencia (codigo, nombre_completo) VALUES
    ('VRC', 'Vicepresidencia Regional Central'),
    ('VRO', 'Vicepresidencia Regional Orinoquía'),
    ('VAO', 'Vicepresidencia Asociadas y Operaciones'),
    ('VFS', 'Vicepresidencia Frontera Sur'),
    ('VPI', 'Vicepresidencia Piedemonte'),
    ('VEX', 'Vicepresidencia Exploración'),
    ('VAS', 'Vicepresidencia Aguas y Servicios');

-- ============================================================================
-- 11. PREPOBLADO dim_fecha (2019-01-01 .. 2030-12-31; cubre histórico + PPTO a 2028)
-- ============================================================================
INSERT INTO core.dim_fecha (fecha, anio, mes, dia, trimestre, dia_semana, semana_mes)
SELECT d::date,
       EXTRACT(YEAR  FROM d)::int,
       EXTRACT(MONTH FROM d)::int,
       EXTRACT(DAY   FROM d)::int,
       EXTRACT(QUARTER FROM d)::int,
       EXTRACT(ISODOW FROM d)::int,
       FLOOR((EXTRACT(DAY FROM d)::int - 1) / 7) + 1
FROM generate_series('2019-01-01'::date, '2030-12-31'::date, interval '1 day') AS g(d);

-- ============================================================================
-- FIN — Notas de ingesta (idempotencia "última gana"):
--   INSERT INTO core.fact_produccion_dia_ecp (...) VALUES (...)
--   ON CONFLICT ON CONSTRAINT uk_dia DO UPDATE SET
--       volumen = EXCLUDED.volumen, ..., reporte_id = EXCLUDED.reporte_id;
--   (igual para uk_mes, uk_prog, uk_fil, uk_plan, uk_prom).
-- ============================================================================

-- ============================================================================
-- INGESTA_JOB — orquestación de ingesta por demanda (añadido 2026-06-18)
-- ============================================================================
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

-- ============================================================================
-- FACT TABLA HOJA (genérico, añadido 2026-06-23)
-- ============================================================================
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
