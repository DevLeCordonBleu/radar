# Instrucciones para asistentes de IA

## Qué es esto

Radar de Anuncios: analiza los anuncios activos de la competencia en Meta
(Biblioteca de Anuncios) y produce un informe de qué está saturado y qué está
libre. Versión propia del Radar de BIG school (MIT) con el stack de
`C:\Desarrollo\Monetizacion-YouTube` y `manuales-modulo`, que sirven de modelo
para cualquier duda de convenciones.

## Regla rectora

El informe **describe, no recomienda**, y no afirma qué "funciona": la
Biblioteca de Meta no publica resultados. Lo único que insinúa rendimiento es
cuánto lleva activo un anuncio. No añadir textos, prompts ni UI que prometan
efectividad. Los prompts de clasificación dicen "describes lo que ves, no lo
que opinas": mantenerlo.

## Arquitectura

- `01_backend` Kotlin + Spring Boot. Capas CODE-01 en español: `dominio`,
  `aplicacion` (`ServicioAnalisis` es el corazón), `infraestructura` (SQLite,
  `ClienteWorker`), `api`, `config`. Dueño del estado. Contrato en `LEEME.md`:
  actualizarlo con cada cambio.
- `02_frontend` Vue 3 + TS + Vite. Solo habla con el backend (`/api`).
- `03_worker` Python + FastAPI, sin estado. `analisis/informe.py` es aritmética
  pura y determinista (se prueba sin red); lo que gasta dinero es solo
  `apify/` y `ia/`. El worker no se expone al navegador.
- Esquema: única fuente `04_bd/01_ESQUEMA.sql` (Gradle lo copia).

## Decisiones que no hay que reabrir

- **Todo fallo pausa, nada se pierde.** Checkpoint (`Avance`) tras cada lote;
  `continuar` retoma sin repetir lo pagado. Gemini sin cuota → worker responde
  429 → `ErrorDelWorker.cuota` → análisis PAUSADO, no fallido.
- Una sola cola de análisis (un hilo): dos análisis se disputarían la cuota.
- Gemini en este orden de modelos: 2.5-flash → 2.5-flash-lite → 3-flash-preview
  (la cuota diaria es por modelo). Claves múltiples: si una agota, la siguiente.
- Competidor ambiguo → se pregunta a la persona (`Pendiente`), nunca se adivina
  entre candidatas igual de buenas. Las ciudades NO son palabras genéricas.
- Las claves viven solo en `03_worker/.env`; no hay endpoint que las devuelva.
- Cuentas propias (admin / miembro): `ServicioAuth` + `FiltroSesion` exigen sesión
  en todo `/api` salvo `/api/auth/{estado,alta,entrar,recuperar,salir}`. Cookie
  HttpOnly + SameSite=Strict; en la base solo la huella del token. Nada de
  endpoints que devuelvan contraseñas ni códigos: se muestran una sola vez.

## Trampas ya encontradas

- Jackson 3 + Kotlin: un `null` dentro de `Map<String, Any?>` de un data class
  falla al leer (`InvalidNullException`). Por eso `RepositorioAnalisis.avance()`
  lee como mapa sin tipar y `Pendiente` usa la clase `Candidato`. No volver a
  tipar `Avance` con `readValue(..., Avance::class.java)`.
- Vue: llaves dobles literales en una plantilla (`{{ '{{x}}' }}`) rompen el
  compilador y `vue-tsc -b` no lo ve: usar una constante y, tras tocar vistas,
  correr también `npx vite build`.
- Anuncios: fuente por defecto «navegador» (gratis, Playwright + Chrome leyendo la
  Biblioteca pública de Meta), elegida porque la persona no tiene Apify de pago
  (2026-10-20). Apify queda como opción. Si Meta cambia la página, el arreglo va en
  `app/fuentes/navegador.py` (`recoger` busca dicts con `ad_archive_id` + `snapshot`).
  La API oficial de Meta (ads_archive) no sirve: fuera de la UE solo trae anuncios políticos.
- KeyWords Explorer: la fuente es Google Ads Keyword Planner (decidido por la
  persona). No mostrar ni inventar KD, clics, SERP ni potencial de tráfico. Los
  datos de demostración van SIEMPRE marcados y no se mezclan con reales en listas.
  El cliente REST no está probado contra Google real: ante un error, el mensaje de
  Google se conserva. `GOOGLE_ADS_API_VERSION` caduca al año (sube el número).
  El nivel de acceso es del proyecto de Google Cloud del OAuth (no del Centro de API).
  Explorer no permite Keyword Planner, así que hace falta Básico, y el Básico exige la
  verificación de marca del OAuth: app en producción, página principal y política de
  privacidad en un dominio verificado. Estado (2026-10-30): Explorer aprobado y Básico
  rechazado por falta de esa verificación.
  Los cuerpos de `/api/keywords` se reciben como `Map<*, *>` sin tipar por los
  `null` de las filas (misma trampa de Jackson que el checkpoint).
- Plan SEO: decidido (2026-10-20) hacerlo en Radar y no en Make (el plan maestro
  lo diseñó en Make; aquí no hay coste por operación). Las keywords son hipótesis
  TOPIC_OBSERVED: no presentar posición en Google, volumen ni KD sin una fuente
  que los mida. La IA no puede añadir URLs, keywords ni citas que no estaban en la
  entrada (`app/seo/ia.py` las descarta). El rastreo va a ≥ 1 s por página, respeta
  robots.txt y se frena ante 403/429: no acelerarlo. Antes de «Extraer temas», las páginas
  de un competidor pasan por `SectorSeo` (gratis, sin IA) con las palabras del rubro
  configurado (`ajuste` `seo_rubro`; por defecto el de ILCB): las que no las mencionan
  quedan «fuera del sector» (relevancia 0) sin gastar Gemini. No volver a escribir el
  rubro fijo en prompts ni en Kotlin: los prompts usan `{{NEGOCIO}}`/`{{RUBRO}}`.
  Artículos: la IA no inventa datos del negocio («[COMPLETAR: …]», que bloquea el envío)
  ni enlaza fuera de las páginas propias recibidas. WordPress recibe borradores; publicar
  es solo de admin y una actualización no cambia el estado de la entrada. El Markdown se
  convierte solo en el worker (`app/seo/markdown.py`): no añadir un segundo conversor en
  el panel. Imagen destacada: Pixabay (gratis; Pexels solo si no hay clave de Pixabay: en
  2026-10 Pexels no daba claves nuevas) o Gemini (de pago, sin plan gratuito de imágenes;
  confirmar antes de generar y no generar en pruebas reales sin que la persona lo pida). El
  cliente de imagen de Gemini no está probado contra Google real. La plantilla de entradas de
  ilcb.edu.pe no muestra la destacada: el envío antepone `<!-- wp:post-featured-image /-->`
  (como hace el equipo en sus noticias); `WP_DESTACADA_EN_TEXTO=no` para otro tema.
  Flujo automático (2026-10-28): llega hasta **borrador**; no añadir publicación automática
  sin que la persona lo pida (errores de la IA, «[COMPLETAR]», política de Google sobre
  contenido masivo). Sus sub-tareas corren con `ejecutar()` en el hilo de la cola: nunca
  `encolar()` desde dentro (la cola es de un hilo y se bloquearía). Elige con el
  autocompletado de Google (`app/seo/demanda.py`, sin clave): es una señal sin números, no
  mostrarla como volumen; si Google no responde, elige por competidores y lo avisa. El
  volumen real llegará cuando se conecte Google Ads (Keyword Planner). Search Console
  (`app/seo/search_console.py`) comparte la autorización OAuth de Google Ads (un refresh
  token con los dos permisos); no está probado contra Google real. Solo ve búsquedas donde
  la web propia ya aparece: no usarlo como volumen de lo que falta. Su uso real es pulir
  páginas en la posición 4-20 (`seo_mejora`): la IA propone, la persona aplica en WordPress;
  cada cambio va como «dice ahora / debe decir». Los **términos protegidos** (ajuste
  `seo_terminos`: carreras, sistemas y su descripción oficial) nunca se renombran ni se
  redefinen: `ia.nombres_oficiales` los escribe como están definidos y rechaza la propuesta
  que los alarga («Gastronomía y Arte Culinario»);
  no cambiar páginas publicadas desde el Radar sin que la persona lo pida. La app OAuth está
  en modo Prueba (cuenta personal, sin Workspace): el refresh token caduca cada 7 días. La web de D'Gallia casi no
  tiene contenido (19 URLs en su sitemap, blog vacío): pocas keywords es lo esperado.
  Los sitios se gestionan desde el panel; `ServicioSeo.SITIOS` solo siembra una base vacía
  (no reintroducir la siembra por sitio: devolvería los competidores quitados). `url` de
  `seo_pagina` es única en toda la base: por eso un host no puede estar en dos sitios.
- Desbordes al estrechar: un texto que no debe partir línea necesita `max-width` o
  ellipsis; un `.oculto-visual` (absoluto) se escapa de un contenedor con scroll
  que no sea `position: relative`. Las rejillas de base.css reducen columnas según
  el hueco real (`--min-col`), no la ventana.
- Los enlaces de imagen y video de Meta (`fbcdn.net`, parámetro `oe`) caducan a los ~4 días.
  Por eso las miniaturas se guardan al cerrar el informe (`miniatura_anuncio`); no volver a
  guardar solo el enlace. Los videos siguen siendo enlaces (pesan demasiado para la base).
- Sugerencias de páginas: salen del autocompletado interno de la Biblioteca de Meta
  (`typeahead_suggestions` en /api/graphql; `exact_phrase_results` dice a qué texto
  responde). Si Meta lo cambia, el arreglo va en `app/fuentes/paginas_meta.py`; el
  panel sigue aceptando nombre o enlace. Playwright es por hilo: ese Chrome vive en
  su propio hilo, no lo llames desde otro. No volver a teclear letra a letra como vía
  principal (una petición por letra, lento): se repite la petición capturada
  (`_plantilla`) con `fetch` desde la página; teclear queda solo de respaldo.
- Filtro del sector: lo definen referencia + competidores; las palabras clave NO
  (ver `contexto_sector`). No volver a «ante la duda, relevante» sin matices: dejó
  entrar tiendas y restaurantes en un informe de escuelas.
- Videos (2026-10-30): no hay API de Google Vids. El robot (`app/videos/vids.py`) maneja el Chrome
  de la persona por CDP (puerto 9222, perfil `03_worker/datos/chrome-vids`, sesión iniciada a mano).
  Decidido: ritmo humano, una generación cada vez, y se para ante una verificación. **No** añadir
  anti-detección, resolución de CAPTCHAs ni rotación de cuentas para saltarse el cupo (unas 10
  generaciones al mes). Si Vids cambia la pantalla, los nombres de los botones están en las constantes
  `B_*` de `vids.py`. Vids usa Gemini Omni, como la API de pago: el plan B es `gemini-omni-1.1-flash`.
  Los prompts se arman fijos en `guion.prompts` (no los escribe la IA) para que el personaje y la voz
  se repitan. Las pronunciaciones solo cambian el prompt, nunca el texto mostrado.
- Publicaciones (2026-11-03): el Radar redacta, guarda el archivo y aprueba; publicar es aparte. Hoy
  a mano (se registra el enlace de cada red); después, n8n (en la red de la oficina) publicará solo lo
  `APROBADA`. Decidido así porque Meta y LinkedIn exigen una app propia para publicar: Meta en modo
  desarrollo basta para las cuentas propias; LinkedIn como página de empresa necesita la revisión de
  *Community Management API*. Las pruebas van primero en una página y un Instagram propios de
  Alexander, no en las cuentas de ILCB. Publicada en alguna red no se edita. El tipo de archivo se
  decide por su contenido (`detectar`), no por la extensión.
- Medición: el token de Meta (META_ACCESS_TOKEN) es de Marketing, solo `ads_read`, y nunca se escribe
  en la cuenta. Leads y conversaciones no se suman: el tipo de campaña sale de sus resultados (WhatsApp
  si los chats llegan al 5 % de los clics) y cada costo usa el gasto de su tipo. Las alertas son
  deterministas; la IA solo redacta con las cifras ya calculadas (sin costo para < 10 resultados).
  Para probar la UI contra otra copia: `RADAR_BACKEND=http://localhost:8093 npx vite --port 5176`.
- Publicaciones: nada se borra (DELETE archiva) y cada paso va a `publicacion_evento` con su autor;
  el texto publicado se guarda en el evento PUBLICADA. «Comprobar» (`app/publicaciones/verificar.py`)
  solo abre enlaces públicos sin sesión: SIN_CONFIRMAR no es una baja. No iniciar sesión ni esquivar
  bloqueos de las redes para comprobarlos.
- Informes guardados (`informe_guardado`): cada corte de Search Console y cada lista de keywords, con
  gzip; no se borran. Un corte de Search Console se puede volver a cargar como datos actuales.
- Fecha mínima: Plan SEO (ajuste `seo_fecha_minima`, páginas en estado ANTIGUA) y Análisis de
  competencia (`Peticion.fechaMinima`: fuera los anuncios que empezaron antes y ya terminaron; los
  activos se quedan, son de hoy).
- Flyers: la IA (o el banco de fotos) da solo el FONDO; el título, el detalle, el botón y el logo los
  dibuja `app/publicaciones/flyer.py` con Pillow. No pedirle a un modelo de imagen que escriba el texto
  o el logo: los deforma («Le Cordin Cuiz» en las pruebas de Vids). Gemini imagen es de pago.
- Columnas nuevas en tablas existentes: el esquema solo hace `CREATE TABLE IF NOT EXISTS`, así que
  también van en `infraestructura/MigracionesBd.kt` (`ALTER TABLE ADD COLUMN` si falta).
- Las pestañas (`.pestanas`) no están en base.css: cada vista las define (KeyWords
  Explorer y Plan SEO).
- Clases genéricas de base.css (`.barra`, `.panel`, `.fila`…) chocan con nombres
  locales: no reutilizar esos nombres en estilos scoped.
- Un backend viejo puede quedar ocupando el 8082 de una sesión anterior y el
  nuevo no arranca (y los endpoints nuevos «cuelgan»): matar los listeners de
  8102/8082/5175 antes de levantar. `iniciar.bat` ya lo hace.
- Recompilar (`gradlew bootJar`) con el backend en marcha cambiaba el jar en uso: Java carga
  clases a demanda y la primera petición que tocaba código nuevo moría sin respuesta (el panel
  se quedaba cargando; pasó el 2026-10-28 con «Actualizar en WordPress»). `arrancar.bat` ahora
  ejecuta una copia (`build/run/radar.jar`). Aun así, tras compilar, avisar de reiniciar.
- En el shell de Bash de esta máquina los heredocs largos fallan: escribir
  archivos con la herramienta Write.
- Editar la base a mano: las fechas (`fec_creacion`, `fec_modif`) son ISO de `Instant`
  (`2026-10-23T20:39:19.000000000Z`). `datetime('now')` de SQLite deja
  `2026-10-23 20:39:19`, `Instant.parse` falla y toda la lista da 500 (pasó el
  2026-10-23). Copia de la base antes de tocarla.

## Convenciones

- META-01 (carpetas `NN_`), PROC-05 (README, este archivo, CHANGELOG al día).
- Puertos: worker 8102, backend 8082, Vite 5175.
- Las pruebas no tocan datos reales: `05_pruebas/flujo_completo.py` usa su
  backend (8092), datos temporales y Apify/Gemini simulados. Una prueba que
  gaste IA o Apify debe decirlo en su nombre y docstring.
- Hay una `GEMINI_API_KEY` ya definida en las variables de entorno de Windows
  de este equipo: no hacer llamadas reales a Gemini/Apify sin que la persona lo
  pida.

## Herramientas en este equipo

Python 3.14, Node 24, JDK 21 (`%LOCALAPPDATA%\Programs\jdk-21`; exportar
`JAVA_HOME` antes de `gradlew`). Gradle llega con el wrapper de `01_backend`.
