# Registro de cambios

Formato: fecha, qué cambió y por qué. Lo relevante, no cada commit.

## 2026-11-06 · Conectar con Google desde el Radar

### Corregido
- Medición, Search Console y GA4 se caían con «Google rechazó el refresh token» cada 7 días (el proyecto «Radar»
  de Google Cloud está en modo Prueba) y había que renovarlo por terminal.

### Añadido
- **Conectar con Google** en Medición y en Search Console: dice si la conexión sigue viva y cuándo vence, y la
  renueva en una pestaña de Google sin terminal ni reinicio. Avisa si se desmarcó algún permiso.
- La propiedad de GA4 se elige con «Usar esta» en la lista de propiedades (antes, a mano en el `.env`).
- La app de Google Cloud pasó a producción: con `GOOGLE_APP_PRUEBA=false` el Radar ya no anuncia vencimiento.
- Borradores en WordPress (páginas 3173 y 3174) de la página principal de la app y su política de privacidad,
  para la verificación de marca de Google. Los revisa y publica Marketing.

## 2026-11-05 · Medición: anuncios de Meta, alertas, informe con IA, GA4 y UTM

### Añadido
- **Medición** (menú nuevo):
  - Rendimiento diario de los anuncios de Meta con el token de lectura de Marketing.
  - Cifras del periodo frente al anterior, gráficos por día, campañas y anuncios con más gasto.
  - Alertas calculadas sin IA, ordenadas por el dinero en juego.
  - Informe con IA que queda guardado.
  - Sincronización en segundo plano y cada mañana a las 7:20.
- **GA4** (canales, campañas UTM, páginas de entrada, eventos clave):
  - `autorizar.py` pide ahora también Analytics.
  - Falta que Marketing dé acceso a la propiedad y poner `GA4_PROPIEDAD`.
- **UTM automáticos** en los enlaces a la web propia de los posts de Facebook y LinkedIn.
- En Medición, un constructor de enlaces y los «Parámetros de URL» para todos los anuncios de Meta.

### Verificado con datos reales
- 30 días de la cuenta «ILCB Instituto Backup»: gasto, impresiones, clics, leads y conversaciones idénticos a
  los totales de Meta.
- Dos informes con Gemini real. El primero sacó conclusiones de una campaña con 3 resultados y escribió el CTR
  como proporción. Ahora a la IA no le llega el costo de las campañas con menos de 10 resultados, y el CTR va
  en porcentaje.
- Las campañas «Web» y «Visualizaciones» contaban como de WhatsApp por algún chat suelto: hasta US$ 462 por
  chat. Ahora una campaña es de WhatsApp si sus chats llegan al 5 % de sus clics. Con eso, el costo por
  conversación real es US$ 1,39, no US$ 1,88.

## 2026-11-03 · Biblioteca de posts, informes guardados y fecha mínima

### Añadido
- **Biblioteca de posts** (Publicaciones → Biblioteca): todas, también las archivadas, con filtros y CSV.
  - Nada se borra: «Archivar» (antes «Borrar») la saca de la lista y conserva textos, flyer e historial; se restaura.
  - **Historial** de cada post (`publicacion_evento`): quién la creó, editó, aprobó y publicó, con el texto
    exacto publicado en cada red.
  - **¿Sigue activa?** (`app/publicaciones/verificar.py`): abre cada enlace sin sesión y dice Activa, Ya no
    está o Sin confirmar. De una o de todas. Facebook e Instagram suelen pedir sesión: lo confirmará la API
    de Meta cuando se conecte n8n.
- **Informes guardados** (`informe_guardado`): cada corte de Search Console y cada lista de keywords del Plan
  SEO, con su fecha. Se abren de nuevo, se bajan en CSV y un corte de Search Console se puede volver a cargar.
  Al arrancar, los datos que ya había quedan como el primer informe de cada uno.
- **Fecha mínima de publicación**:
  - Plan SEO: las páginas anteriores pasan a «Antigua» y no se leen ni se analizan. El inventario lee ahora
    la fecha de publicación que declara cada página (`article:published_time` o `datePublished`).
  - Análisis de competencia: fuera los anuncios que empezaron antes y ya terminaron (los activos se quedan).

## 2026-11-03 · Plan SEO: términos protegidos, «dice ahora / debe decir» y sets del rubro

### Añadido
- **Términos protegidos** (Páginas para mejorar): carreras, programas y sistemas con su nombre oficial y,
  si hace falta, su descripción oficial. Por defecto, las 5 carreras y los 2 programas Master tal como los
  escribe ilcb.edu.pe. La IA los recibe con la regla de no renombrarlos ni redefinirlos, y el worker
  (`ia.nombres_oficiales`) los escribe como están definidos y rechaza la propuesta que los alarga
  («Gastronomía y Arte Culinario», «Cocina Profesional»): un reintento con el error a la vista y, si
  insiste, error sin guardar nada.
- **Rubro del negocio por sets**: Cocina, Pastelería y panadería, Bar y coctelería, Vinos y café
  (los cuatro = el rubro por defecto), Restaurantes y servicio, Hotelería y turismo, y Nutrición e
  inocuidad. Se activan o quitan enteros, y se pueden agregar o quitar palabras sueltas.

### Cambiado
- Las propuestas de mejora muestran cada cambio como **«Dice ahora» / «Debe decir»**: título, meta
  descripción y cada cambio del contenido (dónde va, el texto actual copiado de la página o «no existe»,
  y el texto listo para pegar). Las propuestas anteriores se siguen viendo, sin el texto actual.
- A la IA se le manda más texto de la página (2500 caracteres) para que pueda citar lo que dice hoy.

## 2026-11-03 · Publicaciones: texto único o por red, flyer y hashtags del rubro

### Añadido
- Al crear una publicación se elige el texto: **uno para cada red** o **el mismo para todas** (`modoCopy`).
- **Flyer** de 1080×1350 (`app/publicaciones/flyer.py`, Pillow):
  - El fondo es una foto vertical de Pixabay (gratis), una imagen de Gemini (de pago, 4:5) o una foto propia.
  - El Radar pone encima el título, el detalle, el botón y el logo, sobre un degradado del color de la marca.
  - La IA escribe esos textos junto con los del post. Al elegir el fondo, el flyer se arma solo, y se
    rehace al cambiar sus textos.
  - Un «[FALTA: …]» en el flyer bloquea la aprobación.
- **Marca** (al pie de Publicaciones; la cambia un admin): logo, color principal y de acento, y los
  hashtags del rubro, que van delante de los que la IA propone para cada tema.
- Ficha de la publicación ordenada por pasos (texto → flyer → hashtags → vista previa → aprobación →
  publicar), con vista previa por red.
- `MigracionesBd.kt`: añade las columnas nuevas (`modo_copy`, `flyer_json`) a una base que ya tenía la tabla.

### Cambiado
- El panel «Publicar» explica que la publicación automática aún no está conectada (n8n) y qué hacer
  mientras tanto.
- `imagenes.buscar` acepta orientación vertical, e `imagenes.generar` acepta formato vertical (4:5).

## 2026-11-03 · Publicaciones en Facebook, Instagram y LinkedIn

### Añadido
- Módulo **Publicaciones** (menú lateral):
  - **Textos por red:** Gemini escribe uno para cada red elegida y los hashtags, con los datos
    confirmados de los videos (`app/publicaciones/textos.py`, prompt `PUBLICACION.md`).
  - **Imagen o video:** JPG o PNG hasta 8 MB o MP4 hasta 100 MB; el tipo sale del contenido del archivo.
  - **Aprobación** de un administrador, que revisa límites, «[FALTA: …]» y que Instagram lleve imagen o video.
  - **Publicar a mano** y registrar el enlace de cada red. Con todas, queda «Publicada»; desde la
    primera ya no se edita.
- En Videos, un video aprobado tiene «Crear publicación»: pasa con sus copys y una copia del MP4.
- Tabla `publicacion`; consumo de IA `publicacion_textos`.
- Pruebas: `pruebas/test_publicaciones.py` (worker) y una sección nueva en `flujo_completo.py`.

### Cambiado
- Subidas hasta 100 MB (antes 20 MB); un archivo mayor responde 409 con un mensaje claro.
- `guion.limpiar_hashtags` se comparte entre videos y publicaciones.

## 2026-11-03 · «Nuevo análisis» pasa a llamarse «Análisis de competencia»

### Cambiado
- El módulo se renombra en el menú, el título de la página y la Ayuda, para que diga lo que
  hace: analizar los anuncios de la competencia. La ruta (`/`) y la API no cambian. El botón
  «Nuevo análisis» de Informes se queda: es la acción de lanzar uno.

## 2026-11-03 · Se retira la Biblioteca de skills y prompts

### Quitado
- Módulo **Biblioteca** (menú, vistas, API `/api/biblioteca`, importador y exportador):
  no se usaba y no hacía falta. Estaba vacío, así que no se pierde nada.
- El esquema borra `biblioteca_item` y `biblioteca_version` al arrancar
  (`DROP TABLE IF EXISTS`). Respaldo previo: `radar.antes-quitar-biblioteca.2026-11-03.db`.
- `flujo_completo.py` ya no prueba la biblioteca; la usuaria «Eva» se crea ahora en la
  sección del informe semanal, que la usa.

## 2026-10-30 · Videos cortos con Google Vids

### Añadido
- Módulo **Videos** (menú lateral), en cuatro pasos:
  - **Idea o keyword:** se elige la duración (10-60 s) y el formato (vertical u horizontal).
  - **Guion:** Gemini escribe una parte de ~10 s por clip, con diálogo y escena, más los copys de
    Facebook e Instagram y los hashtags (`app/videos/guion.py`, prompt `GUION.md`).
  - **Generación:** el robot de Google Vids crea el primer clip y extiende los demás.
  - **Aprobación:** la da un administrador.
- **Robot de Vids** (`app/videos/vids.py`):
  - Usa Playwright conectado por CDP a un Chrome con perfil propio (`03_worker/datos/chrome-vids`,
    fuera de git). La persona inicia sesión a mano una sola vez.
  - Va a ritmo humano, hace una generación cada vez y se detiene si Google pide verificación.
    No se disfraza el navegador ni se resuelven CAPTCHAs.
  - Descarga el MP4 de la última extensión: Vids ya lo devuelve unido. Si sobra, lo recorta a la
    duración pedida con ffmpeg.
  - Probado en vivo el 2026-10-30: modelo Omni, 720p, 10 s; clip en ~45 s, extensión en ~2 min,
    mismo personaje en los 20 s.
- **Prompts fijos por clip**, sin IA:
  - El protagonista, el lugar, la voz y «sin texto ni logos» se repiten igual en cada clip.
    En la prueba, el modelo había inventado un logo con la marca mal escrita.
  - Las **pronunciaciones** (por defecto «Le Cordon Bleu» → «Le Cordón Blé») solo cambian el
    prompt. Guion, subtítulos y copys conservan la ortografía.
- **Contexto de los videos** (ajuste `video_contexto`, solo admin):
  - Datos confirmados, protagonista, lugar, voz y pronunciaciones.
  - Por defecto, los datos confirmados del plan de contenido de Marketing (`contenido.xlsx`).
- **Reglas:**
  - Un diálogo con «[FALTA: …]» no se genera, porque gastaría generaciones.
  - El número de partes tiene que cuadrar con la duración.
  - Un solo video a la vez en Vids.
  - Si cambia el guion de un video aprobado, vuelve a «Guion listo».
- **Pruebas:** `pruebas/test_videos.py` (worker) y `flujo_completo.py`, con Gemini y Vids simulados.
- Pendiente:
  - montaje con el logo real y subtítulos (falta el PNG del logo);
  - publicación en Facebook e Instagram (falta el acceso de Marketing).

## 2026-10-30 · Borrar artículos desde la lista; Google Ads: niveles de acceso

### Añadido
- **Informe semanal** del análisis de anuncios (`ServicioAnalisisSemanal`, ajuste
  `analisis_semanal`, panel al pie de «Nuevo análisis», solo admin).
  - Guarda el formulario validado, el día y la hora (Lima). Se revisa cada 5 minutos, como el
    flujo del Plan SEO, y crea un análisis normal: mismo coste, misma pausa y «Continuar».
  - Las páginas elegidas a mano en una ejecución pasan a la petición programada, así la
    siguiente busca directo por la página y no vuelve a preguntar.
  - Una pausa sin pregunta (cuota, red) se reintenta sola tras 3 horas, hasta 4 veces.
  - Si la ejecución anterior sigue corriendo, espera a que termine.
  - `flujo_completo.py` cubre permisos, hora, la primera pregunta y que la segunda vez no
    pregunta.
  - El simulador del worker de esa prueba quita ahora las `GOOGLE_ADS_*` del `.env` real: con
    la configuración completa, las pruebas de KeyWords llamaban a Google.
- Plan SEO → Artículos: botón de papelera en cada fila (solo admin) con confirmación. Usa el
  mismo `DELETE /api/seo/articulos/{codigo}` que la ficha. El borrador de WordPress no se
  toca, y la búsqueda vuelve a quedar libre para el flujo automático.

### Cambiado
- Mensajes de Google Ads: el nivel de acceso es del proyecto de Google Cloud, no del Centro
  de API.
  - «Proyecto solo para cuentas de prueba» (`ACTION_NOT_PERMITTED`) y «Explorer no permite
    Keyword Planner» tienen ahora su propio texto, y los dos dicen dónde pedir el Básico.
  - Comprobado contra Google real: Explorer aprobado; Keyword Planner devuelve
    `DEVELOPER_TOKEN_NOT_APPROVED` (*not allowed for use with explorer access*).
  - El Básico fue rechazado porque exige la verificación de marca del OAuth.
- `.env`: `GOOGLE_ADS_LOGIN_CUSTOMER_ID` = MCC 798-743-8860 y `GOOGLE_ADS_CUSTOMER_ID` =
  684-578-3537 (cuenta cliente aún sin activar).

## 2026-10-29 · Plan SEO: mejorar páginas que ya aparecen en Google

### Añadido
- **«Páginas para mejorar»** (panel de Search Console): páginas propias con búsquedas **sin
  marca** entre la posición 4 y 20 (≥ 30 impresiones), agrupadas por página, de más a menos
  impresiones. Con los datos reales de ILCB, el 87 % de las impresiones eran de marca o
  navegación («intranet ilcb», «le cordon bleu») y casi no había búsquedas sin marca lejos
  (posición > 20): Search Console sirve para pulir lo que ya aparece, no para descubrir
  temas nuevos (eso sigue siendo Google Ads).
- **Palabras de marca** (`ajuste` `seo_marca`, las edita un admin): por defecto, el nombre del
  sitio propio sin palabras genéricas («cordon bleu»), sus dominios («ilcb») y lo típico de
  una intranet.
- **Propuesta de mejora con IA** (`POST /seo/mejora` del worker, prompt `MEJORA.md`): título
  (≤ 60), descripción (120-155), hasta 4 ideas de contenido y el motivo, a partir del título,
  meta y encabezados del inventario (o leyendo la página si no está) y de las búsquedas con
  sus cifras. Sin datos inventados («[COMPLETAR]») ni promesas. Se guarda en `seo_mejora`
  (una por página); la persona la aplica en WordPress y la marca «aplicada» o «descartada».
  El Radar no cambia páginas publicadas.
- Flujo automático, paso 7: si Search Console se sincronizó, propone mejoras para las 2
  primeras páginas que aún no tienen propuesta.
- `autorizar.py`: espera 15 minutos (la verificación de identidad de Google tarda) y solo
  acepta la vuelta de Google (antes un favicon o una extensión cortaban la espera).
- Search Console probado contra Google real (sc-domain:ilcb.edu.pe, 90 días).

## 2026-10-29 · Plan SEO: Search Console de la web propia

### Añadido
- **Google Search Console** (estaba en el plan maestro y en el escenario de Make «ILCB -
  SEO Research»; en Radar había quedado pendiente). Worker `app/seo/search_console.py`:
  consultas × página de los últimos 90 días (hasta hace 3, datos consolidados), filtradas
  por país (`GSC_PAIS`, por defecto Perú), paginadas de 25.000 en 25.000. Usa la **misma
  autorización** que Google Ads: `autorizar.py` ahora pide los dos permisos (Ads y
  Search Console de solo lectura), así basta con dar acceso a la cuenta de Google de la
  persona; no hace falta cuenta de servicio. Se guarda entera en `seo_gsc` (cada
  sincronización la reemplaza) y el resumen en `ajuste` `seo_gsc`.
- Elección del flujo automático: una búsqueda que la web ya posiciona según Search Console
  (≥ 10 impresiones; comparada sin tildes y sin importar el orden de las palabras) sale de
  los candidatos: posición ≤ 10, «ya posiciona»; 11-20, «mejorar la página» en vez de
  escribir otra. Las que quedan se ordenan también por impresiones. El flujo sincroniza
  Search Console antes de elegir si está conectado; si no, lo salta; si falla, aviso.
- Panel «Search Console de tu web» en la pestaña Keywords: estado (qué falta), «Comprobar
  acceso», «Traer últimos 90 días», totales y «Páginas para mejorar» (posición 11-20).
- Sin probar contra Google real: no hay credenciales todavía.

## 2026-10-29 · Plan SEO: el flujo automático elige lo que la gente busca en Google

### Cambiado
- **La elección del flujo automático consulta el autocompletado de Google** (pedido por la
  persona: priorizar lo que se busca, no solo lo que publican los competidores). El worker
  (`app/seo/demanda.py`, `POST /seo/demanda`) pregunta a Google (Perú, español) por hasta 3
  keywords de cada grupo candidato (los 20 primeros por competidores) y da una señal:
  EXACTA (sugiere esa búsqueda, o las mismas palabras en otro orden), VARIANTES (sugiere
  búsquedas que la contienen) o NINGUNA. Lo que Google no sugiere se descarta; primero van
  las EXACTA y después rige el orden de siempre (páginas de competidores, relevancia). El
  artículo se redacta con la frase **como la escribe la gente** (p. ej. «curso barista
  duración» en vez de «duración curso barista», respuesta real de Google). Respuestas en
  caché 24 h. Es una señal sin números (no un volumen): el volumen llegará al conectar
  Google Ads. Si Google no responde, se elige solo por competidores y queda un aviso.
- Panel «Qué redactaría ahora»: chip «Google la sugiere» / «Google sugiere variantes», lo que
  también busca la gente, y las descartadas aparte; la última ejecución dice cuáles descartó.

## 2026-10-28 · Plan SEO: imagen destacada de los artículos; miniaturas de anuncios guardadas

### Añadido
- **Flujo automático del Plan SEO** (decidido por la persona: semanal, 2 artículos por vez,
  hasta borrador en WordPress; publicar no se automatiza). Tarea `AUTOMATICO` que encadena,
  en el mismo hilo de la cola SEO, las tareas de siempre: inventario de cada sitio activo
  (uno que frena no para el resto: queda como aviso), temas de lo pendiente, keywords, y
  los artículos de los grupos informacionales SIN_COBERTURA que no tienen artículo (ni uno
  de otro grupo con la misma búsqueda: los grupos cambian de nombre al regenerar), primero
  los que tocan más páginas de competidores. A cada uno, la primera foto del banco para su
  búsqueda; los que no tienen «[COMPLETAR]» van a WordPress como borrador. Cada paso queda
  en el `resumen`: si Gemini se queda sin cuota se pausa y «Continuar» retoma la misma
  sub-tarea. Programación en `ajuste` `seo_automatico` (día, hora de Lima, artículos);
  `@Scheduled` revisa cada 5 min, así que corre al abrir el Radar si a la hora estaba
  cerrado. Panel «Flujo automático» en la pestaña Artículos (solo admin lo cambia o lo
  lanza con «Ejecutar ahora»), con los pasos a la vista y «Qué redactaría ahora»: los
  candidatos en orden y por qué (páginas de competidores, sitios, relevancia).
- **Imagen destacada** en el editor del artículo (`ImagenArticulo.vue`), con dos fuentes
  a elegir (decidido por la persona):
  - **Banco de fotos** (gratis, uso comercial libre): se busca, se elige y se guarda.
    **Pixabay** (`PIXABAY_API_KEY`; hasta 1280 px; búsquedas en caché 24 h como pide su
    API). Pexels (`PEXELS_API_KEY`, 1200×627) queda solo si no hay clave de Pixabay: en
    octubre de 2026 Pexels tenía suspendidas las claves nuevas. El worker solo descarga
    por id de foto y desde el dominio del banco. La leyenda lleva el crédito del fotógrafo.
    Probado con la clave real de Pixabay (una búsqueda y una descarga).
  - **Gemini** (de pago): `gemini-3.1-flash-lite-image` por defecto (~US$ 0.034 por imagen,
    `GEMINI_MODELO_IMAGEN` para cambiarlo). La API no tiene plan gratuito para imágenes
    (comprobado en julio con esta clave: límite 0); sin facturación Google responde 429 y
    el panel lo explica. Se confirma antes de generar y queda en el consumo (`seo_imagen`).
    Usa `generateContent` con `responseModalities: ["IMAGE"]`: **no probado contra Google
    real** (sin facturación no se puede); ante un error se conserva el mensaje de Google.
- Tabla `seo_imagen` (una por artículo, bytes en la base). Cambiar o quitar la imagen
  cuenta como «cambios sin enviar».
- WordPress: al enviar, la imagen se sube a Medios con su alt y leyenda y queda como
  `featured_media`. Ya subida, los reenvíos solo actualizan alt y leyenda; si la borraron
  de la biblioteca, se sube otra vez. «Probar conexión» dice si el usuario puede subir imágenes.

- **Miniaturas de los anuncios guardadas en el Radar.** Los enlaces de imagen de la
  Biblioteca de Meta (`fbcdn.net`) caducan a los ~4 días: los tres informes que había
  (I0001-I0003) ya mostraban todas sus tarjetas sin imagen. Al cerrar el informe, el
  worker (`app/fuentes/miniaturas.py`) baja cada miniatura —solo de los CDN de Meta— y la
  reduce a JPEG de 720 px; el backend la guarda en `miniatura_anuncio` (una por anuncio,
  compartida entre informes; no se vuelve a bajar) y pone `thumb_url` =
  `/api/informes/miniaturas/{adId}`. Gratis, sin IA. La que no baja conserva el enlace de
  Meta. Los informes anteriores no se pueden recuperar (sus enlaces ya caducaron); su
  tarjeta dice ahora «imagen caducada». Los videos siguen siendo enlaces de Meta.

### Corregido
- La etiqueta «Fuera del sector» de la pestaña Páginas seguía diciendo «no habla de
  cocina…» (resto del rubro fijo).
- La imagen destacada llegaba a WordPress (`featured_media`) pero no se veía en la entrada:
  la plantilla de ilcb.edu.pe no la pinta sola; el equipo pone el bloque
  `<!-- wp:post-featured-image /-->` al inicio del texto (entradas 3000 y 2723). El envío
  ahora lo antepone cuando hay imagen (`WP_DESTACADA_EN_TEXTO=no` lo desactiva).
- «Actualizar en WordPress» se quedaba cargando: se recompiló el backend mientras estaba en
  marcha y la petición murió al cargar clases del jar cambiado (sin respuesta al panel).
  `arrancar.bat` ejecuta ahora una copia del jar (`build/run/radar.jar`). La subida a
  WordPress en sí funciona (comprobada con la imagen real: 5 s, y borrada después).

## 2026-10-27 · Plan SEO: rubro configurable, artículos y WordPress

### Añadido
- **Rubro de tu negocio** (pestaña Sitios): descripción + palabras del filtro gratuito,
  guardados en `ajuste` (`seo_rubro`). Antes estaban fijos para gastronomía en
  `SectorSeo.kt`, `TEMAS.md` y `KEYWORDS.md`; ahora los prompts reciben `{{NEGOCIO}}` y
  `{{RUBRO}}`. Por defecto, el de ILCB (mismo resultado que antes: CENFOTUR 72 de 331,
  D'Gallia 10 de 14). Cambiar la descripción olvida los temas de todas las páginas;
  cambiar solo las palabras, los de las «fuera del sector». «Sugerir desde mi web»
  propone ambos con una llamada a Gemini (`RUBRO.md`) sin guardarlos.
- **Artículos**: en Keywords, «Redactar» en una búsqueda crea el artículo de su grupo
  (uno por grupo) y encarga la redacción a Gemini como tarea `ARTICULO` (cola SEO,
  pausa por cuota). `ARTICULO.md`: responde la búsqueda y sus variantes, usa las páginas
  de competidores como contexto sin copiarlas, enlaza solo a páginas propias de la
  entrada (el worker quita las demás) y no inventa datos del negocio: los deja como
  «[COMPLETAR: …]». Vista `/seo/articulos/:codigo`: editor Markdown con vista previa,
  pendientes, volver a redactar con indicaciones.
- **WordPress** (`app/seo/wordpress.py`): API REST con contraseña de aplicación
  (`WP_URL`, `WP_USUARIO`, `WP_CLAVE_APLICACION` en `03_worker/.env`; exige https). La
  primera vez crea la entrada en borrador; después actualiza la misma sin tocar su
  estado. Publicar directamente, solo admin. Con «[COMPLETAR: …]» no se envía. La meta
  description va como extracto. Pestaña «Artículos» con los pasos para conectar y
  «Probar conexión».
- Markdown → HTML propio (`app/seo/markdown.py`, sin dependencias): un solo conversor
  para la vista previa y el envío; escapa todo el texto y solo enlaza http(s).
- `gemini.generar` acepta `temperatura` (0 por defecto; 0,6 para redactar).
- El panel dice el nombre del sitio propio donde decía «ILCB».

## 2026-10-27 · Plan SEO: agregar, editar y quitar sitios

### Añadido
- Los sitios ya no están fijos en el código. En «Sitios», la tarjeta «Agregar competidor»
  pide nombre y dominios (se puede pegar un enlace: se queda el host). El botón «Ajustes»
  (tuerca, a la derecha de las acciones de cada tarjeta) abre debajo el formulario para
  cambiar nombre, dominios y máximo de páginas, con «Guardar».
  «Quitar competidor» (solo admin) borra sus páginas y temas; las pausadas de ese sitio se
  cancelan y sus tareas pasadas quedan en el historial. El sitio propio no se quita.
- Validación: dominios con forma de dominio, hasta 5 por sitio, y ninguno repetido entre
  sitios (la URL de una página es única en toda la base). Con una tarea del sitio en marcha
  no se cambian sus dominios ni se quita.
- `POST /api/seo/sitios`, `PUT /api/seo/sitios/{cod}` acepta `nombre` y `hosts`,
  `DELETE /api/seo/sitios/{cod}`.

### Cambiado
- La siembra de los cuatro sitios del plan solo ocurre con la tabla vacía: un competidor
  quitado no vuelve al reiniciar.
- Cambiar dominios no toca las páginas ya leídas: el siguiente inventario lee las del
  dominio nuevo y deja «Retirada» las que el sitio ya no declare.

### Corregido
- «Extraer temas ()» salía vacío con un backend anterior al filtro del sector: el panel
  usa el total sin temas si el backend no manda `sinTemasDelSector`.

## 2026-10-27 · Plan SEO: filtro del sector antes de la IA

### Añadido
- **«Extraer temas» ya no manda a Gemini lo que no es del sector.** El inventario de
  CENFOTUR trajo 331 páginas, casi todas de turismo. Ahora un filtro gratuito
  (`SectorSeo.kt`) mira URL, title, H1, H2 y meta description (o ≥ 2 menciones en el
  inicio del texto) buscando cocina, panadería, pastelería, bar, coctelería, vino, café…
  Lo que no pasa se marca «fuera del sector» con relevancia 0 y sin IA; lo que pasa lo
  juzga la IA como antes. Solo en competidores: del sitio propio va todo. Con el
  inventario real: CENFOTUR 72 de 331 a la IA (de ~28 llamadas a ~6), D'Gallia 10 de 14.
- El botón y la confirmación dicen cuántas van a la IA y cuántas se marcan gratis
  (`SitioSeo.sinTemasDelSector`). En «Páginas», el filtro «Tipo» tiene «Fuera del sector
  (sin IA)» y la columna Tema lo muestra.
- `TEMAS.md`: la relevancia se mide contra cocina peruana e internacional, panadería,
  pastelería, bar y coctelería; turismo y hotelería sin cocina ni bebidas puntúan bajo.

## 2026-10-27 · Plan SEO: estados legibles en cualquier ancho

### Corregido
- En «Páginas» el estado se partía («Leíd / a») porque el H1 se comía la tabla. Ahora
  un chip dentro de una celda de tabla no parte nunca (`base.css`, todas las tablas) y la
  columna «Estado» se ajusta a su etiqueta. Según el hueco real de la tabla (container
  query): con menos de 1000 px se oculta el H1 (casi siempre repite el título que va bajo
  la URL); con menos de 640 px cada página es una ficha, con URL y estado arriba y H2,
  palabras, meta y tema debajo. Revisado en una maqueta a 1300, 900 y 400 px.

## 2026-10-23 · El nombre de un competidor es el de su página

### Corregido
- Un informe salió titulado «c»: en una fila de competidor se marcaron tres páginas
  (TIMBA SCHOOL, Conteo Sabroso, Combinación Latina) y en la caja quedó escrita la «c»
  de la última búsqueda, que se usaba como nombre. Ahora, con páginas marcadas, el
  competidor (o la marca) **se llama como su primera página**: lo hace el backend al
  validar y el panel lo muestra (al marcar la primera y al salir de la caja).
- Una fila con varias páginas avisa de que **cuentan como un solo competidor** (pensado
  para sedes) y ofrece **«Separar en N competidores»**, uno por página con el mismo nivel.

## 2026-10-23 · «Todos los anuncios» por origen

### Cambiado
- La galería del informe muestra **primero los anuncios de tus competidores**, luego los
  de tu marca y **al final los del mercado** (los que trajeron las palabras clave del
  sector), con un título por grupo cuando el informe mezcla orígenes. Dentro de cada
  grupo, los que más tiempo llevan activos. El origen sale de las páginas identificadas
  (`meta.identificadas`) y de `mis_paginas`: vale también para los informes ya hechos.

## 2026-10-23 · Sugerencias de páginas más rápidas

### Cambiado
- **El worker ya no teclea letra a letra** en el buscador de Meta (cada letra era una
  petición: 60 para 6 búsquedas). La primera vez guarda la petición del autocompletado
  (`useAdLibraryTypeaheadSuggestionDataSourceQuery`) y luego la repite desde la propia
  página cambiando solo el texto: **0,4–0,7 s** por búsqueda medidos en vivo (antes
  0,7–1,9 s, más la cola). Si repetirla falla, se teclea como antes.
- **Solo se atiende la búsqueda más reciente**: las que se quedaron en cola mientras
  se escribía se cancelan en vez de hacer esperar a la buena.
- Chrome de sugerencias: se cierra tras 20 min sin uso (antes 5) y se reabre al entrar
  en una caja de nombre, antes de escribir.
- Panel: espera 250 ms tras la última tecla (antes 450), recuerda lo ya consultado
  (respuesta inmediata al repetir o borrar letras) y, mientras llega la respuesta,
  muestra las páginas anteriores que siguen encajando con lo escrito.

## 2026-10-23 · «Nuevo análisis» empieza vacío

### Cambiado
- El formulario de «Nuevo análisis» **empieza siempre vacío**, también al recargar la
  página: antes se rellenaba solo con el último mercado, y lanzar un análisis lo
  sobrescribía sin avisar. Ahora el mercado se guarda solo con «Guardar mi mercado» y se
  carga solo con el botón «Usar mi mercado guardado» (aparece si hay uno guardado).

## 2026-10-23 · En qué red sale cada anuncio

### Añadido
- **Etiqueta de red** en cada anuncio del informe (tarjeta y ficha): Facebook, Instagram,
  Messenger, WhatsApp, Threads o Audience Network (`Plataformas.vue`). Sale del campo
  `publisher_platform` de la Biblioteca de Meta, comprobado en vivo con 10 anuncios de
  Le Cordon Bleu (casi todos van a la vez en Facebook e Instagram). `normalizar.py` lo
  guarda como `plataformas` en minúsculas y orden fijo; sin el campo queda `null` (no se
  inventa). Los informes anteriores no lo tienen y no muestran etiqueta. El de ejemplo
  trae redes de muestra.

### Cambiado
- «Mis marcas» pasa a ser **opcional** y su texto de ejemplo es «Ingrese su marca» (antes
  «Le Cordon Bleu Perú», que parecía un valor puesto por defecto). Vacía, el análisis es
  solo de los competidores, para cualquier negocio.
- **Las marcas se eligen con sus páginas de Facebook**, con el mismo buscador que los
  competidores (`BuscadorPaginas`, ahora con `placeholder` y `pie`): así no se adivina
  cuál es tu página. Nuevo `Peticion.marcas[{nombre, paginas}]`; `misMarcas` sigue con
  los nombres y un mercado guardado antes se carga igual.
- El informe **reconoce tus anuncios por página** (`mis_paginas`), no por parecido del
  nombre: antes «LCB» no reconocía «Le Cordon Bleu Perú» y «Cordon Bleu» se llevaba otras
  sedes. Los informes antiguos y el de ejemplo siguen por nombre.
- Si se indica una marca, **sus anuncios también se buscan** (antes había que repetirla
  como competidor): el backend la añade como competidor de nivel 3 (peso 1, para no
  inflar los porcentajes) si no estaba ya entre ellos, y el informe marca dónde está.
  Con solo la marca ya se puede lanzar. El tope de 20 competidores incluye las marcas.

### Verificado
- `flujo_completo.py`: marca solo en «Mis marcas» → se busca y el informe cuenta sus
  anuncios; con su página elegida → no pregunta y la reconoce por página; sin marca →
  `mi_marca` vacío. `test_analisis`: por página no confunde nombres parecidos.

## 2026-10-22 · Páginas de Facebook al configurar competidores y filtro del sector

### Añadido
- **Sugerencias de páginas** en «Competidores» (`BuscadorPaginas.vue`): desde 3 letras
  aparecen las páginas de Facebook que coinciden, con foto, categoría, seguidores e
  Instagram, y se marcan varias por competidor (sedes, talleres). Salen del
  autocompletado público de la Biblioteca de Meta (`app/fuentes/paginas_meta.py`):
  un Chrome en su propio hilo, abierto por adelantado al entrar en «Nuevo análisis»
  (~10 s la primera vez, ~1 s después, caché de 1 h; se cierra a los 5 min sin uso).
  Escribir el nombre o pegar el enlace sigue valiendo.
- `Competidor.paginas` (`PaginaMeta`): con páginas elegidas, la búsqueda va por
  cada página y no hay paso de «elegir la página». Se guardan con «mi mercado».
- «Meses funcionando» avisa del competidor sin anuncios de 90 días o más («D'Gallia
  no tiene ninguno: su anuncio más antiguo lleva 9 días») y dice que la sección es
  de todo el informe.

### Corregido
- El filtro del sector dejaba pasar a Promart, Electrolux, Elinox, Enkasa, Ajinomoto
  y restaurantes en un informe de escuelas de cocina: las palabras clave («gastronomia,
  cocina») se le daban a la IA como definición del sector y la regla era «ante la
  duda, relevante». Ahora el sector lo definen los negocios de referencia **y los
  competidores** (y sus páginas); las palabras clave solo buscan; la duda solo
  favorece a negocios del mismo tipo, no a quien vende productos o comidas.

### Verificado
- `test_navegador` (lector del autocompletado con el formato real), `test_analisis`
  (contexto del sector) y `flujo_completo.py` (sugerencias, preparar, competidor con
  páginas: no pregunta, busca por página, referencia del filtro): todo OK.
- En vivo: «dgallia» → sus 4 páginas (más un blog ajeno); «cordon bleu» → 8 páginas.
  Panel: elegir con ratón y teclado, guardar y recargar «mi mercado», móvil.
- **No probado** un análisis completo con Gemini real tras el cambio del filtro.

## 2026-10-22 · Pantallas que se adaptan al ancho

### Corregido
- Las etiquetas (`.chip`) no partían línea (`white-space: nowrap`): una larga como
  «Producto, curso o programa concreto» se salía de la tarjeta al estrechar la
  ventana. Ahora parten línea y nunca pasan del ancho de su caja.
- `.rejilla-2` / `.rejilla-3` pasaban a una columna según el ancho de la ventana, no
  del hueco real (menú lateral + índice del informe): las tarjetas quedaban
  apretadas. Ahora cada columna mide al menos 20rem (15rem en la de 3) y la rejilla
  reduce columnas sola.
- En móvil, el texto oculto para lectores de pantalla de la columna «Acciones» de
  Usuarios ensanchaba la página 37 px: `.tabla-envoltura` es ahora `position: relative`.
- En móvil, los iconos del menú superior se desplazan en horizontal en vez de
  desbordar la barra.

### Verificado
- Detector de desbordes (cajas y texto) en las 13 pantallas a 1440, 1100, 900, 768
  y 390 px: sin desbordes.

## 2026-10-20 · Plan SEO (inventario y keywords candidatas)

Primera parte del *Plan maestro de automatización SEO* de ILCB, hecha en Radar en
vez de en Make (decisión de la persona: sin coste por operación).

### Añadido
- Módulo **Plan SEO** (menú lateral): sitios (ILCB propio; D'Gallia, CENFOTUR con
  sus dos hosts y USIL como competidores), páginas y keywords. Tablas `seo_sitio`,
  `seo_pagina` (una fila por URL), `seo_tarea`, `seo_keyword`.
- Worker `app/seo/rastreo.py`: robots.txt (Disallow, Crawl-delay, Sitemap), índices
  de sitemaps anidados con y sin namespace, rutas habituales y enlaces de la portada
  si no hay sitemap; exclusión de taxonomías y páginas de servicio con motivo;
  extractor HTML sin dependencias que ignora cabecera, menú, buscador, barras
  laterales y bloques de «relacionadas» (el «BUSCAR» de ILCB y los H2 de otras
  noticias de CENFOTUR); una página por segundo como mínimo, frena ante 403/429.
- Worker `app/seo/ia.py` + prompts `TEMAS`, `KEYWORDS`, `COBERTURA`: lo que Gemini
  devuelve se contrasta con la entrada (URLs, keywords y citas inventadas se descartan;
  una cobertura con URL inventada pasa a INCIERTO).
- Backend: cola `colaSeo` con tareas reanudables (pausa por cuota, por 403/429 o por
  cierre), inventario incremental por `lastmod`, temas solo de páginas cambiadas,
  costo de IA por tarea en `consumo_ia`.
- Panel: pestañas Sitios (avance, pausa, sitemaps leídos, máximo de páginas),
  Páginas (filtros y ficha con H2, búsquedas que toca y evidencia) y Keywords
  (intención, grupo, cobertura en ILCB con su página, origen; CSV). Ayuda.

### Verificado
- `pruebas.test_seo` (sitio falso en local + IA simulada con errores a propósito):
  todo OK. `flujo_completo.py` con el Plan SEO (inventario, repetir sin descargar,
  lastmod, retiradas, pausa por cuota y continuar sin repetir, keywords): todo OK.
- En vivo y sin IA: inventario de D'Gallia (19 URLs declaradas, 5 excluidas, 14
  leídas en 33 s) y de 30 páginas de ILCB (289 declaradas) desde el panel.
- **No probado con Gemini real** (temas, keywords y cobertura): falta autorización.

## 2026-10-20 · Ficha de anuncio con flechas

### Añadido
- **Ficha de anuncio** (`VisorAnuncio.vue`), como la del Radar original: creatividad
  (vídeo o imagen; si Meta ya no la sirve, se dice), cómo abre, texto, cómo lo
  clasificó la herramienta (hook, oferta, CTA, formato), territorio, qué promete,
  qué gana el cliente, qué se ve, detalles y enlaces a Meta y a la página de destino.
  Flechas ‹ › (y ← → del teclado) para recorrer el grupo; Escape o el fondo la cierran.
- Se abre al pulsar un punto del mapa, una tarjeta de la galería o un anuncio de
  «Meses funcionando». Desde el mapa, «Ver los N en la galería» deja la galería
  filtrada por ese punto.

### Cambiado
- **Orden por días activo** en la ficha y en la galería: primero el que más tiempo
  lleva activo (`porDiasActivo` en `composables/formato.ts`). El original abría el
  primer anuncio que llegó de Meta, sin criterio; el tiempo activo es la única pista
  de rendimiento que da la Biblioteca.
- Pulsar un punto del mapa ya no filtra la galería directamente: abre la ficha.

## 2026-10-20 · Mapa del mercado como gráfico de dispersión

### Cambiado
- «El mapa del mercado» repetía las barras de la sección 1. Ahora es un gráfico de
  dispersión (`MapaMercado.vue`, SVG sin librerías): X = anunciantes que lo usan,
  Y = frecuencia ponderada; ángulos (círculo azul) y ofertas (rombo ámbar); anillo
  en lo que usa tu marca; zona sombreada «territorio poco ocupado» con el mismo
  criterio que la sección 8; línea de «muy repetido» (25 %); etiquetas directas
  solo en los 4 más frecuentes; ficha al pasar el ratón o con el teclado; pulsar
  un punto filtra la galería (nuevo filtro por oferta). Colores validados con el
  validador de dataviz en claro y oscuro; la forma repite la identidad.
- El índice «En este informe» pasa a ser una columna vertical fija que marca la
  sección que se está leyendo.
- Los cuatro titulares del informe cuentan desde 0 hasta su valor al abrir o
  recargar (`NumeroAnimado.vue`, ~0,9 s). Con «reducir movimiento» se muestran
  directamente; el lector de pantalla oye solo el valor final.

## 2026-10-20 · Fuente gratuita de anuncios (sin Apify)

### Añadido
- **Fuente «navegador»** (`03_worker/app/fuentes/`): el Chrome del equipo abre la
  Biblioteca de Anuncios de Meta (pública, sin cuenta) y recoge los JSON que la
  propia página carga (HTML inicial + `/api/graphql` al desplazarse). Misma forma
  que Apify, así que el normalizador no cambia. Mismo contrato lanzar/consultar/
  abortar: el backend solo cambió de ruta (`/apify/*` → `/anuncios/*`).
- `ANUNCIOS_FUENTE=auto|navegador|apify`. Por defecto, sin token de Apify se usa
  el navegador. Ajustes y «Nuevo análisis» muestran la fuente y que es gratis.
- Una marca puede tener **varias páginas** (sedes, talleres): la elección de página
  ahora admite marcar varias (`pageIds`).

### Corregido
- En la elección de páginas, el icono «ver en Meta» no tenía tamaño y se estiraba
  hasta tapar la tarjeta. Ahora cada página muestra su **foto de perfil**, cuántos
  anuncios activos tiene, el inicio de un texto y **3 imágenes de sus anuncios**
  (`avatar`, `ejemplos`, `texto` en `Candidato`), y la tarjeta entera se puede pulsar.
- «D'Gallia» no reconocía la página «… Alta Cocina DGallia» (marca pegada / apóstrofo
  curvo): `competidores.encaje` compara también sin espacios.

### Verificado
- `pruebas.test_navegador`: extracción y contrato sin red; `--en-vivo`: 40 anuncios
  reales de «D'Gallia» y «gastronomia» en Perú en 15 s. Búsqueda real por el backend
  (aislado) hasta la elección de páginas: 21 s, 3 páginas de D'Gallia, sin gastar IA.
  `flujo_completo.py` (con el caso de varias páginas) y demás pruebas: todo OK.

## 2026-10-14 · KeyWords Explorer

### Añadido
- Módulo **KeyWords Explorer** (menú lateral), al estilo del Keywords Explorer de
  Ahrefs, con datos de **Google Ads Keyword Planner** (decisión de la persona: la
  fuente gratuita; Ahrefs y DataForSEO quedaron descartados por costo).
- Worker (`app/keywords/`): cliente REST de Google Ads sin SDK (ideas por palabras
  y/o URL con paginación, métricas históricas en lotes de 700, moneda de la cuenta,
  errores de Google traducidos), autocompletado de Google, intención estimada por
  reglas, preguntas, coincidentes/relacionados, agrupación por término, volumen por
  país, datos de demostración deterministas y `autorizar.py` para el refresh token.
- Backend: búsquedas con historial y caché de 7 días (`kw_busqueda`), listas con
  notas y actualización de métricas (`kw_lista`, `kw_lista_item`). Las listas de
  demostración y las reales no se mezclan. Comprobar la conexión es solo para admin.
- Panel: inicio (buscador, historial, listas, estado y guía de conexión), resultados
  (Resumen con tarjetas, gráfico mensual y país; Ideas con subpestañas, términos,
  filtros, orden, paginación, añadir a lista, CSV), listas y entradas de Ayuda.

### Verificado
- `pruebas.test_keywords`: reglas, normalización con el formato real de Google y el
  cliente contra un transporte HTTP simulado (cuerpos, cabeceras, páginas, lotes,
  errores). `flujo_completo.py`: búsqueda, caché, historial, resumen, listas,
  permisos (en demostración). Todo OK. Recorrido en el navegador.
- **No probado contra Google Ads real**: no hay credenciales. La versión de la API
  (v24 por defecto, v25 la más nueva en octubre de 2026) es configurable.

### Corregido durante la verificación
- La clase `.barra` de los estilos base (barra de progreso) ocultaba la barra de
  herramientas de la tabla: renombrada a `.herramientas`.
- En la demo, la ficha de una keyword y su fila no coincidían, y había frases como
  «curso de curso de cocina»: el volumen inventado depende ahora solo de la keyword.
- Pedir métricas de «Curso» y «curso» las consultaba dos veces.

## 2026-10-14 · Biblioteca de skills y prompts

### Añadido
- Módulo **Biblioteca** (menú lateral): alta y edición de skills y prompts con
  categoría, etiquetas, origen, favoritos, archivo, búsqueda y filtros; detección
  de variables (`{{x}}` y `[X]`) con asistente para rellenar y copiar; skills con
  archivos de apoyo; **historial de versiones** y restauración. Tablas
  `biblioteca_item` y `biblioteca_version`.
- **Importar** con tres vías (archivos / texto pegado / «desde mi herramienta de
  IA» con un mensaje de exportación que devuelve un JSON `radar-biblioteca`) y
  **vista previa** antes de guardar. Entiende SKILL.md (cabecera YAML, incluida la
  descripción multilínea), `.md`/`.txt`, varios prompts con `## Título`, JSON con
  nombres en español o inglés y ZIP con carpetas de skills. Modos para lo que ya
  existe: omitir, actualizar (versión nueva) o copia.
- **Exportar** a ZIP (`skills/<id>/SKILL.md`, `prompts/<id>.md`, `radar.json`) o
  JSON; ambos se reimportan sin pérdida. Una skill sale como SKILL.md estándar.
- Cualquier usuario crea y edita; solo un administrador borra de verdad.

### Verificado
- `flujo_completo.py` cubre la biblioteca: variables, versiones, restaurar,
  filtros, los cinco formatos de entrada, los tres modos, ida y vuelta por ZIP y
  JSON, permisos. Todo OK. Importación recorrida en el navegador.

### Corregido durante la verificación
- Escribir `{{ '{{variable}}' }}` en una plantilla rompe el compilador de Vue y
  `vue-tsc` no lo detecta: ahora va en una constante. Conviene correr
  `npx vite build` además de `vue-tsc -b`.

## 2026-10-13 · Menú lateral y módulo de usuarios

### Añadido
- Armazón con **menú lateral** (Nuevo análisis, Informes, Usuarios, Ajustes,
  Ayuda), usuario con menú (Mi cuenta, Cerrar sesión) y **tema claro/oscuro**
  recordado en el navegador. En pantallas estrechas el menú pasa arriba con iconos.
- **Cuentas**: alta del primer administrador, entrar, salir, «¿Olvidaste la
  clave?» con código de recuperación de un solo uso, cambio de contraseña, roles
  admin/miembro, contraseñas temporales, desactivar/reactivar/borrar, bloqueo
  por intentos fallidos y registro de actividad. Tablas `usuario`, `sesion`,
  `auditoria`.
- «Nuevo análisis» pasa a ser la portada (`/`); los informes viven en `/informes`.

### Verificado
- `05_pruebas/flujo_completo.py` cubre las cuentas (alta, roles, 401/403,
  bloqueo, desactivación, recuperación de un solo uso, salir): todo OK.
- Panel visto en el navegador: alta con código de recuperación, menú, Usuarios,
  tema claro y oscuro.

## 2026-10-13 · Primera versión

Origen: análisis del build compilado del *Radar de Anuncios* de BIG school
(`Downloads\radar-de-anuncios`, MIT), con el stack de Monetización-YouTube.

### Añadido · worker (`03_worker`)
- `analisis/`: niveles de competidor con peso (2 / 1,5 / 1 / 0,75), frecuencias
  (≥40 muy alta … <3 hueco), informe determinista, anuncios "veteranos"
  (≥90 días activos), identificación de la página de un competidor, plan B de
  territorios sin IA, datos de ejemplo inventados.
- `apify/`: lanzar / consultar / abortar con varios tokens, URLs de la
  Biblioteca (por página, marca exacta o palabras), normalizador tolerante con
  rutas alternativas por campo.
- `ia/`: Gemini con salida JSON estructurada, rotación de claves y de modelos,
  reintentos con espera sugerida; descarga y reducción de imágenes/videos;
  prompts de clasificación y de territorios (`ia/prompts/`); reglas
  deterministas que corrigen al modelo (botón del CTA, formato declarado,
  pregunta directa).

### Añadido · backend (`01_backend`)
- Ciclo del análisis reanudable con checkpoint, pausa por cuota, elección de
  página ambigua, "terminar con lo analizado", cancelar, estimación de costo
  y costo real por informe. Recuperación al reiniciar (queda pausado).

### Añadido · panel (`02_frontend`)
- Informes, nuevo análisis (con estimación), seguimiento, informe de 9
  secciones con mapa del mercado y galería filtrable, ajustes con comprobación
  de claves, ayuda con buscador. Impresión a PDF.

### Corregido durante la verificación
- El checkpoint no se podía releer (Jackson rechaza `null` en los mapas de los
  anuncios): se lee sin tipar. Lo detectó `flujo_completo.py`.
- Las candidatas pendientes tampoco se leían: clase `Candidato`.
- «Lima» y «Perú» no son palabras genéricas: con ellas dos páginas de ciudades
  distintas parecían una sola.
- El HTML de un anuncio dejaba espacios dobles.

### Verificado
- `pruebas.test_analisis`: todo OK. `05_pruebas/flujo_completo.py`: todo OK.
- Panel: informe de ejemplo renderizado en el navegador sin errores de consola.
- **No probado con Apify ni Gemini reales** (sin gasto).
