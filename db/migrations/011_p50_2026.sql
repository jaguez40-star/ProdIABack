-- 011_p50_2026.sql · Idempotente.
-- Serie P50 mensual 2026 (nivel Upstream global), en kboepd.
--
-- DE DONDE SALE (2026-09-07)
--   El P50 solo entra al sistema dentro de la hoja REPORTE_PRESIDENT de cada reporte diario.
--   Un mes sin reporte ingerido no tiene P50, y el panorama corporativo se queda sin la cifra
--   de referencia ("Compromiso P50 no disponible"). Esta tabla guarda los 12 meses del
--   compromiso 2026 para servir de RESPALDO cuando la ingesta no cubre ese mes.
--
--   ORIGEN DEL DATO: lamina gerencial "Produccion Equivalente G.E. 2026", transcrita A MANO.
--   NO proviene de la ingesta y NO tiene reporte_id que lo respalde. La columna `fuente` lo
--   deja explicito para que nadie lo confunda con un dato medido.
--
-- ESCALA: kboepd. Verificado el 2026-09-07 contra REPORTE_PRESIDENT (reporte 18, 2026-05-18):
--   Upstream base_p50 = 726.73 y esta tabla para mayo = 726.7. Es la MISMA magnitud que el
--   endpoint /president rotula como "kbpe" -- distinto rotulo, misma escala. No hay conversion.
--
-- GRANO: Upstream global. NO hay desglose por producto, vicepresidencia, activo ni campo,
--   porque el P50 no se pacta a esos niveles (ver p50_referencia.py, cabecera del modulo).

CREATE TABLE IF NOT EXISTS core.p50_2026 (
    mes        SMALLINT     PRIMARY KEY CHECK (mes BETWEEN 1 AND 12),
    mes_nombre VARCHAR(12)  NOT NULL,
    p50        NUMERIC(8,2) NOT NULL,
    unidad     VARCHAR(10)  NOT NULL DEFAULT 'kboepd',
    fuente     VARCHAR(60)  NOT NULL DEFAULT 'lamina Produccion Equivalente G.E. 2026'
);

COMMENT ON TABLE core.p50_2026 IS
    'Serie P50 mensual 2026 (Upstream) en kboepd. Origen: lamina gerencial, transcrito a mano - NO proviene de ingesta.';

-- ON CONFLICT: reejecutar la migracion deja los mismos 12 valores, no duplica ni acumula.
INSERT INTO core.p50_2026 (mes, mes_nombre, p50) VALUES
    ( 1, 'Enero',      744.20),
    ( 2, 'Febrero',    741.20),
    ( 3, 'Marzo',      732.80),
    ( 4, 'Abril',      714.90),
    ( 5, 'Mayo',       726.70),
    ( 6, 'Junio',      728.00),
    ( 7, 'Julio',      747.00),
    ( 8, 'Agosto',     740.40),
    ( 9, 'Septiembre', 735.00),
    (10, 'Octubre',    741.80),
    (11, 'Noviembre',  738.30),
    (12, 'Diciembre',  733.30)
ON CONFLICT (mes) DO UPDATE
    SET mes_nombre = EXCLUDED.mes_nombre,
        p50        = EXCLUDED.p50;
