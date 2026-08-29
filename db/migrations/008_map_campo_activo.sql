-- 008_map_campo_activo.sql · Idempotente.
-- Mapeo CAMPO -> ACTIVO. FUENTE DE VERDAD del nivel 'activo'.
--
-- POR QUÉ EXISTE ESTA TABLA (auditoría 2026-07-16, verificada contra la BD):
--   NINGUNA columna de core.dim_fuente es el Activo:
--     · dim_fuente.activos  -> NO es el activo: es un bucket de portafolio
--       (OPERADOS/NO OPERADOS/MENORES + agrupaciones regionales). 18 valores.
--       Para APIAY agrupa 13 campos; el activo real tiene 4.
--     · dim_fuente.grupo1   -> parecido pero distinto (62 valores, taxonomía previa).
--       Discrepa del catálogo real: KIMERA->CPO-09, GIGANTE->NEIVA, PAUTO SUR->RECETOR.
--   El catálogo real son 52 activos (coincide con el maestro corporativo).
--   Origen: data/Activo_campo.csv (export de la BD de otro proyecto; estable a 2026-07-16).
--
-- ALCANCE (decisiones del usuario, 2026-07-16):
--   · Solo cubre operación directa Ecopetrol (~80 de 139 campos de dim_fuente).
--     Los campos operados por terceros (SierraCol, Cepcolsa, Parex, Gran Tierra, Hocol,
--     PetroSantander, Emerald, Frontera, Cedco) NO tienen activo -> se responden como Campo.
--   · Un campo NO puede estar en 2 activos (doble conteo al sumar). El CSV trae 2 casos:
--       - LORITO (AKACIAS vs CPO-09) -> resuelto a AKACIAS (veredicto del usuario).
--       - OMITIDOS por seguir ambiguos: AULLADOR
--         -> quedan SIN activo: se responden como Campo y no suman en ningún rollup.
--   · campo_norm = norm() de app.features.consulta.normaliza (NFKD sin acentos + upper + trim).
--     El join contra dim_fuente lo hace Python con el MISMO norm(), no SQL.

CREATE TABLE IF NOT EXISTS core.map_campo_activo (
    campo_norm  text PRIMARY KEY,
    campo       text NOT NULL,
    activo      text NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_map_campo_activo_activo ON core.map_campo_activo (activo);

INSERT INTO core.map_campo_activo (campo_norm, campo, activo) VALUES
    ('ABANICO', 'ABANICO', 'ABANICO'),
    ('ABARCO', 'ABARCO', 'NARE'),
    ('ABARCO BUFFER', 'ABARCO BUFFER', 'NARE'),
    ('ACAE-SAN MIGUEL', 'ACAE-SAN MIGUEL', 'SUR'),
    ('AKACIAS', 'AKACIAS', 'CPO-09'),
    ('ALQAMARI', 'ALQAMARI', 'OCCIDENTE'),
    ('APIAY', 'APIAY', 'APIAY'),
    ('APIAY ESTE', 'APIAY ESTE', 'APIAY'),
    ('AREA TECA-COCORNA', 'AREA TECA-COCORNA', 'AREA TECA-COCORNA'),
    ('ARRAYAN', 'ARRAYAN', 'ARRAYAN-BALCON'),
    ('AUSTRAL', 'AUSTRAL', 'SURIA'),
    ('BAJO RIO', 'BAJO RIO', 'CASABE'),
    ('BALCON', 'BALCON', 'ARRAYAN-BALCON'),
    ('BONANZA', 'BONANZA', 'BONANZA'),
    ('BRISAS', 'BRISAS', 'DINA CRETACEO'),
    ('CAIPAL', 'CAIPAL', 'PALAGUA'),
    ('CAMPO EXPLORATORIO MORITO-1', 'CAMPO EXPLORATORIO MORITO-1', 'MORITO'),
    ('CANO SUR ESTE', 'CAÑO SUR ESTE', 'CAÑO SUR'),
    ('CARIBE', 'CARIBE', 'OCCIDENTE'),
    ('CASABE', 'CASABE', 'CASABE'),
    ('CASABE SUR', 'CASABE SUR', 'CASABE'),
    ('CASTILLA', 'CASTILLA', 'CASTILLA'),
    ('CASTILLA ESTE', 'CASTILLA ESTE', 'CASTILLA'),
    ('CASTILLA NORTE', 'CASTILLA NORTE', 'CASTILLA'),
    ('CEDRAL', 'CEDRAL', 'NORORIENTE'),
    ('CENCELLA', 'CENCELLA', 'NORORIENTE'),
    ('CHICHIMENE', 'CHICHIMENE', 'CHICHIMENE'),
    ('CHICHIMENE SW', 'CHICHIMENE SW', 'CHICHIMENE'),
    ('CHURUYACO', 'CHURUYACO', 'OCCIDENTE'),
    ('COLORADO', 'COLORADO', 'COMERCIAL'),
    ('CRISTALINA', 'CRISTALINA', 'CR-GR-SG'),
    ('CUPIAGUA', 'CUPIAGUA', 'CUPIAGUA'),
    ('CUSIANA', 'CUSIANA', 'CUSIANA'),
    ('DELE', 'DELE', 'CUPIAGUA'),
    ('DINA CRETACEO', 'DINA CRETACEO', 'DINA CRETACEO'),
    ('DINA NORTE', 'DINA NORTE', 'DINA CRETACEO'),
    ('DINA TERCIARIO', 'DINA TERCIARIO', 'DINA CRETACEO'),
    ('ESPINO', 'ESPINO', 'UNIFICADO RIO CEIBAS'),
    ('FLAMENCOS', 'FLAMENCOS', 'FLAMENCOS'),
    ('FLORENA', 'FLOREÑA', 'PIEDEMONTE'),
    ('FLORENA MIRADOR', 'FLOREÑA MIRADOR', 'PIEDEMONTE'),
    ('GARZAS', 'GARZAS', 'CR-GR-SG'),
    ('GAVAN', 'GAVAN', 'APIAY'),
    ('GIBRALTAR', 'GIBRALTAR', 'SIRIRI'),
    ('GIGANTE', 'GIGANTE', 'NEIVA'),
    ('GIRASOL', 'GIRASOL', 'NARE'),
    ('GUARIQUIES', 'GUARIQUIES', 'GUARIQUIES'),
    ('GUATIQUIA', 'GUATIQUIA', 'APIAY'),
    ('GUAYURIBA', 'GUAYURIBA', 'SURIA'),
    ('HORMIGA', 'HORMIGA', 'SUR'),
    ('INFANTAS', 'INFANTAS', 'LA CIRA'),
    ('JAZMIN', 'JAZMIN', 'NARE'),
    ('KIMERA', 'KIMERA', 'KIMERA'),
    ('LA CIRA', 'LA CIRA', 'LA CIRA'),
    ('LA JAGUA', 'LA JAGUA', 'TELLO'),
    ('LA REFORMA', 'LA REFORMA', 'LA REFORMA'),
    ('LIBERTAD', 'LIBERTAD', 'LA REFORMA'),
    ('LIBERTAD NORTE', 'LIBERTAD NORTE', 'LA REFORMA'),
    ('LIEBRE', 'LIEBRE', 'PROVINCIA'),
    ('LISAMA', 'LISAMA', 'LISAMA'),
    ('LISAMA PROFUNDO', 'LISAMA PROFUNDO', 'LISAMA'),
    ('LISAMA UNIFICADO', 'LISAMA UNIFICADO', 'LISAMA UNIFICADO'),
    ('LLANITO UNIFICADO', 'LLANITO UNIFICADO', 'GAL-LLANITO'),
    ('LOMA LARGA', 'LOMA LARGA', 'LOMA LARGA'),
    ('LORITO', 'LORITO', 'AKACIAS'),
    ('LORO', 'LORO', 'SUR'),
    ('MANSOYA', 'MANSOYA', 'NORORIENTE'),
    ('MEREY', 'MEREY', 'SURIA'),
    ('MITO', 'MITO', 'CAÑO SUR'),
    ('MORICHE', 'MORICHE', 'NARE'),
    ('MORICHE BUFFER II', 'MORICHE BUFFER II', 'NARE'),
    ('NARE', 'NARE', 'NARE'),
    ('NARE UNIFICADO', 'NARE UNIFICADO', 'NARE - UNIFICADO'),
    ('NUTRIA', 'NUTRIA', 'LISAMA'),
    ('OCOA', 'OCOA', 'SURIA'),
    ('ORITO', 'ORITO', 'ORITO'),
    ('PACHAQUIARO', 'PACHAQUIARO', 'PACHAQUIARO'),
    ('PALAGUA', 'PALAGUA', 'PALAGUA'),
    ('PALERMO-SANTA CLARA UNIFICADO', 'PALERMO-SANTA CLARA UNIFICADO', 'PALERMO - SANTA CLARA UNIFICADO'),
    ('PALOGRANDE UNIFICADO', 'PALOGRANDE UNIFICADO', 'DINA CRETACEO'),
    ('PAUTO SUR', 'PAUTO SUR', 'PIEDEMONTE'),
    ('PENAS BLANCAS', 'PEÑAS BLANCAS', 'CASABE'),
    ('PEROLES', 'PEROLES', 'LISAMA'),
    ('PINOCHO', 'PINOCHO', 'CAÑO SUR'),
    ('POMPEYA', 'POMPEYA', 'SURIA'),
    ('PROVINCIA', 'PROVINCIA', 'PROVINCIA'),
    ('QUENANE', 'QUENANE', 'SURIA'),
    ('QUILILI', 'QUILILI', 'NORORIENTE'),
    ('QURIYANA', 'QURIYANA', 'OCCIDENTE'),
    ('RECETOR WEST', 'RECETOR WEST', 'RECETOR WEST'),
    ('RUBIALES', 'RUBIALES', 'RUBIALES'),
    ('SAN ANTONIO', 'SAN ANTONIO', 'OCCIDENTE'),
    ('SAN FRANCISCO', 'SAN FRANCISCO', 'SAN FRANCISCO'),
    ('SAN LUIS', 'SAN LUIS', 'ALEDAÑOS'),
    ('SAN ROQUE', 'SAN ROQUE', 'TISQUIRAMA'),
    ('SARDINATA', 'SARDINATA', 'POB CATATUMBO'),
    ('SAURIO', 'SAURIO', 'SURIA'),
    ('SUCIO', 'SUCIO', 'OCCIDENTE'),
    ('SUCUMBIOS', 'SUCUMBIOS', 'OCCIDENTE'),
    ('SURIA', 'SURIA', 'SURIA'),
    ('SURIA SUR', 'SURIA SUR', 'SURIA'),
    ('TANANE', 'TANANE', 'SURIA'),
    ('TELLO', 'TELLO', 'TELLO'),
    ('TEMPRANILLO UNIFICADO', 'TEMPRANILLO UNIFICADO', 'DINA CRETACEO'),
    ('TENAY', 'TENAY', 'DINA CRETACEO'),
    ('TENAY VILLETA', 'TENAY VILLETA', 'HUILA'),
    ('TENERIFE', 'TENERIFE', 'ALEDAÑOS'),
    ('TESORO', 'TESORO', 'LISAMA'),
    ('TIBU', 'TIBU', 'SOT'),
    ('TINAMU', 'TINAMU', 'AKACIAS'),
    ('TISQUIRAMA', 'TISQUIRAMA', 'TISQUIRAMA'),
    ('UNDERRIVER', 'UNDERRIVER', 'NARE'),
    ('UNIFICADO LORO - ACAE', 'UNIFICADO LORO - ACAE', 'SUR'),
    ('UNIFICADO RIO CEIBAS', 'UNIFICADO RIO CEIBAS', 'UNIFICADO RIO CEIBAS'),
    ('YAGUARA', 'YAGUARA', 'YAGUARA'),
    ('YARIGUI-CANTAGALLO', 'YARIGUI-CANTAGALLO', 'YARIGUI'),
    ('YURILLA', 'YURILLA', 'NORORIENTE')
ON CONFLICT (campo_norm) DO UPDATE SET campo = EXCLUDED.campo, activo = EXCLUDED.activo;
