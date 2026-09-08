-- 012_p50_2026_desglose.sql · Idempotente.
-- Desglose REAL de la lamina: Ecopetrol + Filiales por mes, en kboepd.
--
-- POR QUE (2026-09-08)
--   El panel P50 pinta las tres tarjetas de producto (Crudo/Gas/Blancos) pero NO el corte por
--   empresa, que es justo la lectura de la lamina gerencial: la barra apilada separa REAL
--   NACIONAL (verde oscuro = Ecopetrol) de REAL FILIALES (verde claro).
--
--   El dato de Filiales SI existe en REPORTE_PRESIDENT, pero solo para los meses con reporte
--   ingerido -- en el 139 hay marzo, julio, agosto y septiembre. Y cuando el reporte se tomo
--   antes del cierre, la cifra queda por debajo de la definitiva (medido: julio 706,65 vs 708,2
--   de la lamina; agosto, con reporte del 31, da 714,32 vs 714,5 y si cuadra).
--
--   DECISION DEL USUARIO (2026-09-08): enero-agosto se leen de ESTA tabla (historico cerrado,
--   transcrito de la lamina); septiembre en adelante se siguen leyendo de REPORTE_PRESIDENT,
--   que es la fuente viva. Asi los meses cerrados no dependen de que reporte se ingirio.
--
-- ORIGEN: lamina gerencial "Produccion Equivalente G.E. 2026", transcrita A MANO desde la
--   barra apilada. NO proviene de la ingesta. La columna `fuente` de la tabla ya lo declara.
--
-- ESCALA: kboepd, la misma de la columna `p50`. Verificado: agosto real_nacional 714,5 =
--   ecopetrol 593,1 + filiales 121,4 (la suma cierra en los 9 meses con dato).
--
-- OCT-DIC quedan en NULL: la lamina no desglosa esos meses (solo el POP total 733,6/731,8/729,9).

ALTER TABLE core.p50_2026 ADD COLUMN IF NOT EXISTS real_ecopetrol NUMERIC(8,2);
ALTER TABLE core.p50_2026 ADD COLUMN IF NOT EXISTS real_filiales  NUMERIC(8,2);
ALTER TABLE core.p50_2026 ADD COLUMN IF NOT EXISTS real_nacional  NUMERIC(8,2);

COMMENT ON COLUMN core.p50_2026.real_ecopetrol IS
    'REAL NACIONAL de la lamina (barra verde oscuro), kboepd. Transcrito a mano. NULL = la lamina no lo desglosa.';
COMMENT ON COLUMN core.p50_2026.real_filiales IS
    'REAL FILIALES de la lamina (barra verde claro), kboepd. Transcrito a mano.';
COMMENT ON COLUMN core.p50_2026.real_nacional IS
    'Total apilado = ecopetrol + filiales, kboepd. Se guarda transcrito, no calculado, para poder verificar la suma.';

-- Los 12 meses del P50 (por si la tabla esta vacia) + el desglose ene-ago.
-- Idempotente: ON CONFLICT actualiza, asi que reejecutarla no duplica ni pierde.
INSERT INTO core.p50_2026 (mes, mes_nombre, p50, real_ecopetrol, real_filiales, real_nacional) VALUES
    ( 1, 'Enero',      744.20, 588.20, 134.20, 722.50),
    ( 2, 'Febrero',    741.20, 591.00, 134.20, 725.20),
    ( 3, 'Marzo',      732.80, 593.40, 134.60, 728.00),
    ( 4, 'Abril',      714.90, 582.90, 128.30, 711.20),
    ( 5, 'Mayo',       726.70, 592.20, 119.90, 712.20),
    ( 6, 'Junio',      728.00, 572.30, 121.30, 693.60),
    ( 7, 'Julio',      747.00, 590.40, 117.80, 708.20),
    ( 8, 'Agosto',     740.40, 593.10, 121.40, 714.50),
    ( 9, 'Septiembre', 735.00, NULL,   NULL,   NULL),
    (10, 'Octubre',    741.80, NULL,   NULL,   NULL),
    (11, 'Noviembre',  738.30, NULL,   NULL,   NULL),
    (12, 'Diciembre',  733.30, NULL,   NULL,   NULL)
ON CONFLICT (mes) DO UPDATE SET
    p50            = EXCLUDED.p50,
    real_ecopetrol = EXCLUDED.real_ecopetrol,
    real_filiales  = EXCLUDED.real_filiales,
    real_nacional  = EXCLUDED.real_nacional;

-- Guarda: la suma tiene que cerrar. Si una transcripcion quedo mal, esto lo canta al aplicar.
DO $$
DECLARE malos INT;
BEGIN
    SELECT COUNT(*) INTO malos FROM core.p50_2026
    WHERE real_nacional IS NOT NULL
      AND ABS(real_nacional - (real_ecopetrol + real_filiales)) > 0.15;
    IF malos > 0 THEN
        RAISE EXCEPTION 'p50_2026: % mes(es) donde ecopetrol+filiales no suma el nacional', malos;
    END IF;
END $$;
