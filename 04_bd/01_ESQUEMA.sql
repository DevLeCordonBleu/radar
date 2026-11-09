-- Esquema de Radar (SQLite, prototipo local).
--
-- Unica fuente del esquema: Gradle lo copia a los recursos del backend al
-- compilar y Spring lo aplica al arrancar (CREATE ... IF NOT EXISTS, asi que
-- es idempotente).
--
-- Sigue las convenciones de DAT-01 (id_<tabla> primero, cod_<tabla> despues,
-- auditoria y estado_reg al final) aunque DAT-01 solo obliga en SQL Server:
-- asi el paso al motor del anfitrion es una traduccion, no un rediseno.
-- Las columnas *_json guardan estructuras que define el worker (peticion,
-- avance, informe); se normalizaran al migrar.

-- Un analisis es una ejecucion: busca anuncios, los clasifica y genera un informe.
-- Es reanudable: `avance_json` guarda lo hecho tras cada lote, asi que una pausa
-- (cuota de Gemini, cierre del backend, error de red) no pierde nada.
CREATE TABLE IF NOT EXISTS analisis (
    id_analisis    INTEGER PRIMARY KEY AUTOINCREMENT,
    cod_analisis   TEXT    NOT NULL UNIQUE,                 -- A0001
    peticion_json  TEXT    NOT NULL,                        -- marcas, competidores, pais, maximo...
    estado         TEXT    NOT NULL DEFAULT 'en_cola',      -- en_cola | corriendo | pausado | terminado | cancelado
    fase           TEXT    NOT NULL DEFAULT 'buscando',     -- buscando | clasificando | territorios | informe
    mensaje        TEXT    NOT NULL DEFAULT '',             -- lo que esta haciendo, para el panel
    hechos         INTEGER NOT NULL DEFAULT 0,              -- anuncios clasificados
    total          INTEGER NOT NULL DEFAULT 0,              -- anuncios a clasificar
    error          TEXT,                                    -- motivo de la pausa
    pendiente_json TEXT,                                    -- decision que espera de la persona
    avance_json    TEXT,                                    -- checkpoint reanudable
    cod_informe    TEXT,                                    -- informe resultante
    fec_creacion   TEXT    NOT NULL,
    fec_modif      TEXT    NOT NULL,
    estado_reg     INTEGER NOT NULL DEFAULT 1               -- 0 = borrado logico
);

CREATE INDEX IF NOT EXISTS IX_analisis_estado ON analisis (estado);

-- El informe terminado. Los porcentajes ya estan calculados; el panel solo pinta.
CREATE TABLE IF NOT EXISTS informe (
    id_informe   INTEGER PRIMARY KEY AUTOINCREMENT,
    cod_informe  TEXT    NOT NULL UNIQUE,                   -- I0001
    cod_analisis TEXT,                                      -- NULL: informe de ejemplo
    marca        TEXT    NOT NULL DEFAULT '',
    anuncios     INTEGER NOT NULL,
    anunciantes  INTEGER NOT NULL,
    portada_json TEXT,                                      -- lo que se ve en la lista: que satura, que falta
    datos_json   TEXT    NOT NULL,
    es_ejemplo   INTEGER NOT NULL DEFAULT 0,
    archivado    INTEGER NOT NULL DEFAULT 0,
    fec_creacion TEXT    NOT NULL,
    fec_modif    TEXT    NOT NULL,
    estado_reg   INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS IX_informe_fec_creacion ON informe (fec_creacion DESC);

-- Miniatura de cada anuncio, descargada al cerrar el informe: los enlaces de imagen de
-- la Biblioteca de Meta caducan a los ~4 dias. Una por anuncio, compartida entre informes.
CREATE TABLE IF NOT EXISTS miniatura_anuncio (
    id_miniatura INTEGER PRIMARY KEY AUTOINCREMENT,
    ad_id        TEXT    NOT NULL UNIQUE,
    datos        BLOB    NOT NULL,                          -- JPEG de 720 px como mucho
    mime         TEXT    NOT NULL,
    fec_creacion TEXT    NOT NULL
);

-- Cada llamada a Gemini con su costo: alimenta el costo real de cada informe.
CREATE TABLE IF NOT EXISTS consumo_ia (
    id_consumo_ia  INTEGER PRIMARY KEY AUTOINCREMENT,
    cod_analisis   TEXT    NOT NULL,
    operacion      TEXT    NOT NULL,                        -- clasificar | territorios
    modelo         TEXT    NOT NULL,
    tokens_entrada INTEGER NOT NULL DEFAULT 0,
    tokens_salida  INTEGER NOT NULL DEFAULT 0,
    costo_usd      REAL    NOT NULL DEFAULT 0,
    fec_creacion   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS IX_consumo_ia_cod_analisis ON consumo_ia (cod_analisis);

-- Preferencias del equipo (mis marcas, pais, sector...). Las claves NO van aqui:
-- viven en 03_worker/.env.
CREATE TABLE IF NOT EXISTS ajuste (
    id_ajuste    INTEGER PRIMARY KEY AUTOINCREMENT,
    cod_ajuste   TEXT    NOT NULL UNIQUE,
    ajuste_valor TEXT    NOT NULL,
    fec_modif    TEXT    NOT NULL
);

-- ── Cuentas del equipo ─────────────────────────────────────────────────
-- El primer usuario que se registra es administrador. Las contraseñas se
-- guardan con PBKDF2-SHA256 y sal propia; nunca en claro. El codigo de
-- recuperacion (solo su huella) permite entrar si se olvida la contraseña.
CREATE TABLE IF NOT EXISTS usuario (
    id_usuario        INTEGER PRIMARY KEY AUTOINCREMENT,
    cod_usuario       TEXT    NOT NULL UNIQUE,              -- U0001
    usuario_email     TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    usuario_nombre    TEXT    NOT NULL,
    rol               TEXT    NOT NULL CHECK (rol IN ('admin', 'miembro')),
    clave_hash        TEXT    NOT NULL,
    clave_sal         TEXT    NOT NULL,
    clave_iteraciones INTEGER NOT NULL,
    debe_cambiar      INTEGER NOT NULL DEFAULT 0,           -- clave temporal: cambiarla al entrar
    fallos            INTEGER NOT NULL DEFAULT 0,
    bloqueado_hasta   INTEGER NOT NULL DEFAULT 0,           -- epoch ms
    recuperacion      TEXT,                                 -- huella del codigo de recuperacion
    ultimo_acceso     TEXT,
    fec_creacion      TEXT    NOT NULL,
    fec_modif         TEXT    NOT NULL,
    estado_reg        INTEGER NOT NULL DEFAULT 1            -- 0 = desactivado
);

CREATE TABLE IF NOT EXISTS sesion (
    id_sesion    TEXT    PRIMARY KEY,                       -- huella del token (el token solo vive en la cookie)
    id_usuario   INTEGER NOT NULL REFERENCES usuario (id_usuario),
    creado       INTEGER NOT NULL,                          -- epoch ms
    visto        INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS IX_sesion_id_usuario ON sesion (id_usuario);

CREATE TABLE IF NOT EXISTS auditoria (
    id_auditoria INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha        TEXT    NOT NULL,
    actor        TEXT,                                      -- cod_usuario de quien lo hizo
    accion       TEXT    NOT NULL,
    objetivo     TEXT
);

-- ── Biblioteca de skills y prompts (retirada el 2026-11-03) ───────────────
-- El modulo se quito por innecesario; esto limpia las bases que aun la tienen.
DROP TABLE IF EXISTS biblioteca_version;
DROP TABLE IF EXISTS biblioteca_item;

-- ── KeyWords Explorer ──────────────────────────────────────────────────
-- Cada busqueda guarda su resultado completo: sirve de historial y de cache
-- (los volumenes de Keyword Planner son mensuales, asi que repetir una busqueda
-- dentro de 7 dias no vuelve a gastar cuota de Google).
CREATE TABLE IF NOT EXISTS kw_busqueda (
    id_kw_busqueda  INTEGER PRIMARY KEY AUTOINCREMENT,
    cod_kw_busqueda TEXT    NOT NULL UNIQUE,                -- K0001
    clave           TEXT    NOT NULL,                       -- huella de los parametros (cache)
    semillas_json   TEXT    NOT NULL,
    url             TEXT,
    pais            TEXT    NOT NULL,
    idioma          TEXT    NOT NULL,
    demo            INTEGER NOT NULL DEFAULT 0,             -- 1 = datos de demostracion, no reales
    total_keywords  INTEGER NOT NULL DEFAULT 0,
    volumen_total   INTEGER NOT NULL DEFAULT 0,
    resultado_json  TEXT    NOT NULL,
    cod_autor       TEXT,
    fec_creacion    TEXT    NOT NULL,
    fec_modif       TEXT    NOT NULL,
    estado_reg      INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS IX_kw_busqueda_clave ON kw_busqueda (clave);

-- Listas de keywords guardadas (como las «Keyword lists» de Ahrefs).
CREATE TABLE IF NOT EXISTS kw_lista (
    id_kw_lista  INTEGER PRIMARY KEY AUTOINCREMENT,
    cod_kw_lista TEXT    NOT NULL UNIQUE,                   -- L0001
    nombre       TEXT    NOT NULL,
    descripcion  TEXT    NOT NULL DEFAULT '',
    pais         TEXT    NOT NULL,
    idioma       TEXT    NOT NULL,
    demo         INTEGER NOT NULL DEFAULT 0,
    cod_autor    TEXT,
    fec_creacion TEXT    NOT NULL,
    fec_modif    TEXT    NOT NULL,
    estado_reg   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS kw_lista_item (
    id_kw_lista_item INTEGER PRIMARY KEY AUTOINCREMENT,
    id_kw_lista      INTEGER NOT NULL REFERENCES kw_lista (id_kw_lista),
    keyword          TEXT    NOT NULL COLLATE NOCASE,
    datos_json       TEXT    NOT NULL,                      -- la fila con sus metricas al guardarla
    nota             TEXT    NOT NULL DEFAULT '',
    fec_creacion     TEXT    NOT NULL,
    fec_modif        TEXT    NOT NULL,
    UNIQUE (id_kw_lista, keyword)
);

-- ── Plan SEO ──────────────────────────────────────────────────────────────

-- Sitios que se inventarían: el propio (ILCB) y los competidores aprobados.
CREATE TABLE IF NOT EXISTS seo_sitio (
    id_seo_sitio        INTEGER PRIMARY KEY AUTOINCREMENT,
    cod_seo_sitio       TEXT    NOT NULL UNIQUE,            -- ILCB, DGALLIA, CENFOTUR, USIL
    nombre              TEXT    NOT NULL,
    rol                 TEXT    NOT NULL,                   -- PROPIO | COMPETIDOR
    hosts_json          TEXT    NOT NULL,                   -- ["www.cenfotur.edu.pe", "aprendeturismo.cenfotur.edu.pe"]
    max_paginas         INTEGER NOT NULL DEFAULT 400,       -- paginas que se descargan como mucho por inventario
    activo              INTEGER NOT NULL DEFAULT 1,
    descubrimiento_json TEXT,                               -- sitemaps leidos y avisos del ultimo inventario
    fec_descubierto     TEXT,
    fec_creacion        TEXT    NOT NULL,
    fec_modif           TEXT    NOT NULL
);

-- Una fila por URL (la clave es la URL): repetir el inventario actualiza, no duplica.
CREATE TABLE IF NOT EXISTS seo_pagina (
    id_seo_pagina   INTEGER PRIMARY KEY AUTOINCREMENT,
    id_seo_sitio    INTEGER NOT NULL REFERENCES seo_sitio (id_seo_sitio),
    url             TEXT    NOT NULL UNIQUE,
    sitemap         TEXT,                                   -- de donde salio la URL
    lastmod         TEXT,                                   -- lo que declara el sitemap
    lastmod_leido   TEXT,                                   -- lastmod cuando se descargo por ultima vez
    estado          TEXT    NOT NULL DEFAULT 'PENDIENTE',   -- PENDIENTE | OK | EXCLUIDA | NO_HTML | HTTP_ERROR | BLOQUEADA | ERROR | RETIRADA
    motivo          TEXT,
    http            INTEGER,
    url_final       TEXT,
    datos_json      TEXT,                                   -- title, meta_description, h1, h2[], canonical, lang, palabras, extracto
    hash            TEXT,                                   -- huella del contenido extraido
    temas_json      TEXT,                                   -- lo que dijo la IA: tipo, tema, consultas, relevancia, evidencia
    hash_temas      TEXT,                                   -- hash del contenido cuando se pidieron los temas
    fec_descubierta TEXT    NOT NULL,
    fec_extraida    TEXT,
    fec_temas       TEXT,
    fec_modif       TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS IX_seo_pagina_sitio ON seo_pagina (id_seo_sitio, estado);

-- Trabajos en segundo plano (inventario, temas, keywords), uno a la vez.
CREATE TABLE IF NOT EXISTS seo_tarea (
    id_seo_tarea  INTEGER PRIMARY KEY AUTOINCREMENT,
    cod_seo_tarea TEXT    NOT NULL UNIQUE,                  -- S0001
    tipo          TEXT    NOT NULL,                         -- INVENTARIO | TEMAS | KEYWORDS | ARTICULO
    cod_seo_sitio TEXT,                                     -- null en KEYWORDS (usa todos)
    estado        TEXT    NOT NULL,                         -- EN_COLA | CORRIENDO | TERMINADA | PAUSADA | CANCELADA
    hechos        INTEGER NOT NULL DEFAULT 0,
    total         INTEGER NOT NULL DEFAULT 0,
    mensaje       TEXT,
    error         TEXT,
    resumen_json  TEXT,                                     -- contadores al terminar
    cod_autor     TEXT,
    fec_creacion  TEXT    NOT NULL,
    fec_modif     TEXT    NOT NULL
);

-- Keywords candidatas de la ultima generacion. Evidencia TOPIC_OBSERVED: salen del
-- contenido publico de un competidor, no de su posicion en Google.
CREATE TABLE IF NOT EXISTS seo_keyword (
    id_seo_keyword   INTEGER PRIMARY KEY AUTOINCREMENT,
    clave            TEXT    NOT NULL UNIQUE,               -- keyword normalizada
    keyword          TEXT    NOT NULL,
    origenes_json    TEXT    NOT NULL,                      -- [{sitio, url}]
    intencion        TEXT,                                  -- INFORMATIONAL | COMMERCIAL | TRANSACTIONAL | NAVIGATIONAL | NEEDS_REVIEW
    grupo            TEXT,
    canonica         TEXT,
    relevancia       INTEGER,
    motivo           TEXT,
    cobertura        TEXT,                                  -- YA_CUBIERTA | PARCIAL | SIN_COBERTURA | INCIERTO (null = no evaluada)
    url_propia       TEXT,
    motivo_cobertura TEXT,
    evidencia        TEXT    NOT NULL DEFAULT 'TOPIC_OBSERVED',
    cod_seo_tarea    TEXT,
    fec_creacion     TEXT    NOT NULL
);

-- Articulos para el sitio propio: la IA redacta un borrador a partir de un grupo de
-- keywords, la persona lo revisa y lo envia a WordPress (como borrador o publicado).
CREATE TABLE IF NOT EXISTS seo_articulo (
    id_seo_articulo  INTEGER PRIMARY KEY AUTOINCREMENT,
    cod_seo_articulo TEXT    NOT NULL UNIQUE,               -- AR0001
    grupo            TEXT    NOT NULL UNIQUE,               -- un articulo por grupo de keywords
    keyword          TEXT    NOT NULL,                      -- busqueda principal
    variantes_json   TEXT    NOT NULL,
    origenes_json    TEXT    NOT NULL,                      -- [{sitio, url}] paginas de competidores que la tocan
    indicaciones     TEXT,                                  -- lo que pidio la persona al redactar
    titulo           TEXT,
    slug             TEXT,
    meta_description TEXT,
    contenido        TEXT,                                  -- Markdown; el worker lo pasa a HTML
    pendientes_json  TEXT,                                  -- datos a completar o verificar segun la IA
    cod_seo_tarea    TEXT,                                  -- la ultima redaccion
    wp_id            INTEGER,                               -- entrada en WordPress (null = no enviado)
    wp_estado        TEXT,                                  -- draft | publish | ...
    wp_enlace        TEXT,
    wp_editar        TEXT,
    fec_enviado      TEXT,
    fec_redactado    TEXT,
    cod_autor        TEXT,
    fec_creacion     TEXT    NOT NULL,
    fec_modif        TEXT    NOT NULL
);

-- Imagen destacada de un articulo (una por articulo; elegir otra la sustituye). Los bytes
-- viven aqui para que una copia de radar.db lo lleve todo.
CREATE TABLE IF NOT EXISTS seo_imagen (
    id_seo_imagen    INTEGER PRIMARY KEY AUTOINCREMENT,
    cod_seo_articulo TEXT    NOT NULL UNIQUE,
    fuente           TEXT    NOT NULL,                      -- PIXABAY | PEXELS | GEMINI
    datos            BLOB    NOT NULL,
    mime             TEXT    NOT NULL,                      -- image/jpeg | image/png | image/webp
    alt_text         TEXT,                                  -- texto alternativo (accesibilidad y SEO)
    leyenda          TEXT,                                  -- credito: «Foto: X en Pixabay» o «Imagen generada con IA»
    autor            TEXT,                                  -- banco de fotos: fotografo
    autor_url        TEXT,
    origen_url       TEXT,                                  -- banco de fotos: pagina de la foto
    prompt           TEXT,                                  -- Gemini: lo que se pidio
    modelo           TEXT,
    wp_media_id      INTEGER,                               -- ya subida a la biblioteca de WordPress
    cod_autor        TEXT,
    fec_creacion     TEXT    NOT NULL,
    fec_modif        TEXT    NOT NULL
);

-- Search Console de la web propia: consultas x pagina de la ultima sincronizacion (se
-- reemplaza entera). Cifras reales de Google, solo de busquedas donde la web ya aparece.
CREATE TABLE IF NOT EXISTS seo_gsc (
    id_seo_gsc   INTEGER PRIMARY KEY AUTOINCREMENT,
    consulta     TEXT    NOT NULL,
    orden        TEXT    NOT NULL,                          -- consulta normalizada con las palabras ordenadas
    url          TEXT    NOT NULL,
    clics        INTEGER NOT NULL,
    impresiones  INTEGER NOT NULL,
    ctr          REAL    NOT NULL,
    posicion     REAL    NOT NULL                           -- media del periodo
);
CREATE INDEX IF NOT EXISTS ix_seo_gsc_orden ON seo_gsc(orden);

-- Propuesta de mejora de una pagina propia que Google ya muestra en la posicion 4-20
-- (Search Console). La IA propone; la persona la aplica en WordPress y la marca.
CREATE TABLE IF NOT EXISTS seo_mejora (
    id_seo_mejora    INTEGER PRIMARY KEY AUTOINCREMENT,
    url              TEXT    NOT NULL UNIQUE,               -- una por pagina: proponer otra la sustituye
    consultas_json   TEXT    NOT NULL,                      -- las busquedas con sus cifras cuando se propuso
    titulo_actual    TEXT,
    meta_actual      TEXT,
    titulo           TEXT    NOT NULL,                      -- propuesto
    meta_description TEXT    NOT NULL,                      -- propuesta
    ideas_json       TEXT    NOT NULL,                      -- cambios de contenido sugeridos
    motivo           TEXT,
    estado           TEXT    NOT NULL DEFAULT 'PROPUESTA',  -- PROPUESTA | APLICADA | DESCARTADA
    cod_autor        TEXT,
    fec_creacion     TEXT    NOT NULL,
    fec_modif        TEXT    NOT NULL
);

-- Informes guardados tal como estaban el dia que se hicieron: cada corte de Search Console y
-- cada lista de keywords del Plan SEO. No se borran ni se cambian (auditoria); se pueden
-- volver a abrir, bajar en CSV y, los de Search Console, volver a cargar como datos actuales.
CREATE TABLE IF NOT EXISTS informe_guardado (
    id_informe_guardado  INTEGER PRIMARY KEY AUTOINCREMENT,
    cod_informe_guardado TEXT    NOT NULL UNIQUE,           -- IG0001
    modulo               TEXT    NOT NULL,                  -- SEARCH_CONSOLE | PLAN_SEO_KEYWORDS
    titulo               TEXT    NOT NULL,
    resumen_json         TEXT    NOT NULL,                  -- cifras para la lista (periodo, totales)
    datos_gz             BLOB    NOT NULL,                  -- las filas en JSON, comprimidas con gzip
    filas                INTEGER NOT NULL,
    cod_origen           TEXT,                              -- la tarea que lo genero, si la hubo
    cod_autor            TEXT,
    fec_creacion         TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_informe_guardado_modulo ON informe_guardado(modulo);

-- Biblioteca de posts: todo lo que le paso a cada publicacion (quien y cuando), incluido el
-- texto exacto que se publico en cada red y cada comprobacion de si sigue activa.
CREATE TABLE IF NOT EXISTS publicacion_evento (
    id_publicacion_evento INTEGER PRIMARY KEY AUTOINCREMENT,
    cod_publicacion       TEXT    NOT NULL,
    evento                TEXT    NOT NULL,                 -- CREADA | TEXTOS | EDITADA | FLYER | ARCHIVO | APROBADA | ...
    detalle               TEXT    NOT NULL,                 -- frase para mostrar
    datos_json            TEXT,                             -- lo necesario para auditar (p. ej. el texto publicado)
    cod_autor             TEXT,
    fec_creacion          TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_publicacion_evento ON publicacion_evento(cod_publicacion);

-- ── Medicion: rendimiento diario de los anuncios propios de Meta (solo lectura) ──
-- Una fila por anuncio y dia. Cada sincronizacion vuelve a traer los ultimos dias (Meta
-- corrige la atribucion) y reemplaza ese tramo.
CREATE TABLE IF NOT EXISTS meta_insight (
    fecha          TEXT    NOT NULL,                        -- AAAA-MM-DD (zona de la cuenta)
    anuncio_id     TEXT    NOT NULL,
    anuncio        TEXT    NOT NULL,
    conjunto_id    TEXT,
    conjunto       TEXT,
    campana_id     TEXT    NOT NULL,
    campana        TEXT    NOT NULL,
    objetivo       TEXT,                                    -- OUTCOME_LEADS | OUTCOME_SALES | ...
    gasto          REAL    NOT NULL DEFAULT 0,
    impresiones    INTEGER NOT NULL DEFAULT 0,
    alcance        INTEGER NOT NULL DEFAULT 0,              -- del dia: no se suma entre dias
    clics          INTEGER NOT NULL DEFAULT 0,
    clics_enlace   INTEGER NOT NULL DEFAULT 0,
    leads          INTEGER NOT NULL DEFAULT 0,              -- formularios (accion lead)
    conversaciones INTEGER NOT NULL DEFAULT 0,              -- chats iniciados (WhatsApp/Messenger)
    visitas        INTEGER NOT NULL DEFAULT 0,              -- landing_page_view
    PRIMARY KEY (fecha, anuncio_id)
);
CREATE INDEX IF NOT EXISTS ix_meta_insight_campana ON meta_insight(campana_id, fecha);

-- ── Videos cortos (guion por partes de 10 s, generados en Google Vids) ──
CREATE TABLE IF NOT EXISTS video (
    id_video         INTEGER PRIMARY KEY AUTOINCREMENT,
    cod_video        TEXT    NOT NULL UNIQUE,               -- V0001
    titulo           TEXT    NOT NULL,
    idea             TEXT    NOT NULL,
    keyword          TEXT,
    segundos         INTEGER NOT NULL DEFAULT 45,           -- 10 a 60; un clip de Vids por cada 10 s
    formato          TEXT    NOT NULL DEFAULT 'VERTICAL',   -- VERTICAL | HORIZONTAL
    partes_json      TEXT    NOT NULL DEFAULT '[]',         -- [{dialogo, escena}], una por clip
    copy_facebook    TEXT,
    copy_instagram   TEXT,
    hashtags_json    TEXT    NOT NULL DEFAULT '[]',
    estado           TEXT    NOT NULL DEFAULT 'IDEA',       -- IDEA | GUION | GENERANDO | GENERADO | APROBADO | ERROR
    trabajo          TEXT,                                  -- id del trabajo en el worker mientras GENERANDO
    avance           TEXT,
    error            TEXT,
    archivo          TEXT,                                  -- MP4 en <datos>/videos
    segundos_reales  REAL,
    vids_url         TEXT,                                  -- el proyecto en Google Vids
    cod_autor        TEXT,
    fec_creacion     TEXT    NOT NULL,
    fec_modif        TEXT    NOT NULL
);

-- ── Publicaciones en redes (Facebook, Instagram, LinkedIn) ─────────────
-- Se redactan y se aprueban en el Radar; por ahora se publican a mano y se
-- registra el enlace de cada red. El envio automatico (n8n) llegara despues.
-- Columnas anadidas despues de crear la tabla: tambien en MigracionesBd.kt.
CREATE TABLE IF NOT EXISTS publicacion (
    id_publicacion  INTEGER PRIMARY KEY AUTOINCREMENT,
    cod_publicacion TEXT    NOT NULL UNIQUE,                -- P0001
    titulo          TEXT    NOT NULL,
    idea            TEXT    NOT NULL,
    origen          TEXT    NOT NULL DEFAULT 'MANUAL',      -- MANUAL | VIDEO
    cod_origen      TEXT,                                   -- el video del que sale (V0001)
    redes_json      TEXT    NOT NULL DEFAULT '[]',          -- ["FACEBOOK", "INSTAGRAM", "LINKEDIN"]
    textos_json     TEXT    NOT NULL DEFAULT '{}',          -- {red: texto}
    hashtags_json   TEXT    NOT NULL DEFAULT '[]',
    media           TEXT    NOT NULL DEFAULT 'NINGUNA',     -- NINGUNA | IMAGEN | VIDEO
    archivo         TEXT,                                   -- en <datos>/publicaciones
    archivo_tipo    TEXT,                                   -- image/jpeg | image/png | video/mp4
    enlaces_json    TEXT    NOT NULL DEFAULT '{}',          -- {red: url} de lo ya publicado
    modo_copy       TEXT    NOT NULL DEFAULT 'POR_RED',     -- POR_RED | MISMO (un texto para todas las redes)
    flyer_json      TEXT,                                   -- textos del flyer y de donde salio el fondo
    archivada       INTEGER NOT NULL DEFAULT 0,             -- no se borra: se archiva (auditoria)
    verificacion_json TEXT,                                 -- {red: {estado, detalle, http, fecha}} ultima comprobacion
    estado          TEXT    NOT NULL DEFAULT 'BORRADOR',    -- BORRADOR | APROBADA | PUBLICADA
    cod_aprobador   TEXT,
    cod_autor       TEXT,
    fec_creacion    TEXT    NOT NULL,
    fec_modif       TEXT    NOT NULL
);
