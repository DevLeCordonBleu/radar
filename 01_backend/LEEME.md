# Backend de Radar · contrato

Spring Boot (Kotlin) en el puerto 8082. Todo cuelga de `/api`. Los errores
salen como `{"error": "mensaje para mostrar tal cual"}`: 409 regla de negocio,
404 no existe, 502 fallo del worker.

## Acceso

Todo `/api` exige la cookie `radar_sesion`, salvo los endpoints de `/api/auth`
marcados abajo. Sin sesión: 401 `{"error":..., "sesion":false}`; sin permiso: 403.

| Método y ruta | Qué hace |
|---|---|
| `GET /api/auth/estado` (pública) | `{necesitaAlta, usuario}` |
| `POST /api/auth/alta` (pública) | Primer administrador; solo si no hay cuentas. Devuelve `codigoRecuperacion` (una vez) |
| `POST /api/auth/entrar` (pública) | `{email, clave}` |
| `POST /api/auth/recuperar` (pública) | `{email, codigo, claveNueva}`; el código es de un solo uso, devuelve uno nuevo |
| `POST /api/auth/salir` | Cierra la sesión |
| `PUT /api/auth/cuenta` | `{nombre?, claveActual?, claveNueva?, nuevoCodigo?}` |
| `GET/POST /api/usuarios` · `PUT/DELETE /api/usuarios/{cod}` · `POST /api/usuarios/{cod}/reiniciar-clave` · `GET /api/usuarios/auditoria` | Gestión (solo admin). Crear y reiniciar devuelven `claveTemporal` una sola vez |

## KeyWords Explorer

Con sesión. Cuerpos como mapas JSON (las filas traen `null` legítimos).

| Método y ruta | Qué hace |
|---|---|
| `GET /api/keywords/estado` | `{google_ads: {completo, faltan[], version, cuenta, con_manager}, paises{}, idiomas{}}` |
| `POST /api/keywords/comprobar` | Prueba la conexión con Google Ads (solo admin) |
| `POST /api/keywords/explorar` | `{semillas[≤20], url?, pais, idioma, maximo(10-2000)?, sugerencias?, demo?, refrescar?}` → `{busqueda, desdeCache, resultado: {filas[], terminos[], totales, demo, moneda, volumen_agrupado…}}`. Caché de 7 días por parámetros |
| `GET /api/keywords/busquedas` · `GET/DELETE /api/keywords/busquedas/{cod}` | Historial (40 últimas), reabrir, quitar |
| `POST /api/keywords/resumen` | `{keyword, pais, idioma, porPais?, demo?}` → ficha con tendencia, meses, variaciones y `por_pais` |
| `GET/POST /api/keywords/listas` · `GET/PUT/DELETE /api/keywords/listas/{cod}` | Listas (`{nombre, descripcion, pais, idioma, demo}`) |
| `POST /api/keywords/listas/{cod}/items` | `{items: fila[], demo}` → `{agregadas, repetidas}`; no mezcla demo y real (409) |
| `POST …/quitar` · `PUT …/nota` · `POST …/actualizar` | `{keywords[]}` · `{keyword, nota}` · vuelve a pedir métricas (≤500) conservando notas |

Una fila: `{keyword, volumen, tendencia[12], competencia, competencia_idx, cpc, cpc_bajo, cpc_alto, palabras, intencion[], pregunta, tipo: coincidente|relacionado, sugerencia, concepto}`.

## Plan SEO

Tareas en segundo plano, una a la vez (cola `colaSeo`, aparte de la de análisis).
Lanzar responde `202` con la tarea `EN_COLA`; el panel consulta `/tareas/{cod}`.

| Endpoint | Qué hace |
|---|---|
| `GET /api/seo/sitios` | Sitios del plan (ILCB propio + D'Gallia, CENFOTUR, USIL) con páginas por estado, `conTemas`, `sinTemas`, sitemaps y avisos del último inventario |
| `POST /api/seo/sitios` | `{nombre, hosts[]}` → 201, competidor nuevo. Un enlace vale como host (se queda el dominio); hasta 5, ninguno de otro sitio (409) |
| `PUT /api/seo/sitios/{cod}` | `{nombre?, hosts?, maxPaginas? (10-3000), activo?}`; lo que no venga se conserva. Cambiar hosts no toca las páginas: el siguiente inventario retira las no declaradas |
| `DELETE /api/seo/sitios/{cod}` | 204. Solo admin (403); el sitio propio no (409). Borra sus páginas y cancela sus tareas pausadas |
| `POST /api/seo/sitios/{cod}/inventario` | robots.txt + sitemaps + páginas pendientes (nuevas, con `lastmod` cambiado o que fallaron), hasta `maxPaginas` |
| `POST /api/seo/sitios/{cod}/temas` | IA: tipo, tema, consultas informacionales, relevancia y evidencia de las páginas cuyo contenido cambió |
| `POST /api/seo/keywords/generar` | IA: intención y grupos de las consultas de los competidores (relevancia ≥ 40) y cobertura de cada grupo informacional en el sitio propio. Sustituye la lista anterior |
| `GET /api/seo/paginas?sitio=` | Una fila por URL: estado, motivo, `datos` (title, meta_description, h1, h2[], palabras, extracto…) y `temas` |
| `GET /api/seo/keywords` | `{keyword, origenes[{sitio,url}], intencion, grupo, canonica, relevancia, cobertura, urlPropia, evidencia: TOPIC_OBSERVED}` |
| `GET /api/seo/tareas` · `GET /api/seo/tareas/{cod}` | Últimas 20 · una (con `costoUsd` y `llamadasIa`) |
| `POST /api/seo/tareas/{cod}/continuar` · `…/cancelar` | Reanudar una pausada (sin repetir lo hecho) · cancelar |

| `GET /api/seo/fecha-minima` · `PUT` | `{fecha (AAAA-MM-DD o null), antiguas}`. PUT `{fecha}` → además `marcadas` y `devueltas`: las páginas anteriores pasan a `ANTIGUA` (no se leen ni van a temas ni keywords) y las que dejan de serlo vuelven. La fecha de una página es la de publicación que declara (`datos.publicado`) o el `lastmod` de su sitemap. 409 si es futura o con una tarea en marcha |
| `GET /api/seo/informes?modulo=SEARCH_CONSOLE\|PLAN_SEO_KEYWORDS` | Informes guardados (más nuevo primero): `{codigo IG0001, modulo, titulo, resumen, filas, origen, autor, creado}`. Cada sincronización de Search Console y cada «Generar keywords» guarda uno; nunca se borran |
| `GET /api/seo/informes/{cod}` · `…/csv` | `{informe, filas[]}` tal como estaba · el CSV completo (con BOM) |
| `POST /api/seo/informes/{cod}/restaurar` | Solo Search Console: vuelve a cargar ese corte como los datos actuales (mejoras y flujo). 409 si es de keywords o con el flujo en marcha |
| `GET /api/seo/rubro` · `PUT` | `{descripcion, palabras[], porDefecto, negocio, conTemas, fueraDelSector}`. PUT `{descripcion (10-300), palabras[] (3-80, una palabra cada una)}` → además `reevaluar`: si cambia la descripción se olvidan los temas de todas las páginas; si solo las palabras, los de las «fuera del sector». 409 con una tarea en marcha |
| `POST /api/seo/rubro/sugerir` | IA (1 llamada): `{descripcion, palabras}` leyendo el inventario propio. No guarda |
| `GET /api/seo/articulos` · `GET …/{cod}` | Artículos (`AR0001`): grupo, keyword, variantes, origenes, titulo, slug, metaDescription, contenido (Markdown), pendientes, tarea y su estado, `wpId/wpEstado/wpEnlace/wpEditar`, `cambiosSinEnviar` |
| `POST /api/seo/articulos` | `{grupo, indicaciones?}` → 202: crea el artículo del grupo (uno por grupo, 409) y encarga la redacción (tarea `ARTICULO`) |
| `POST /api/seo/articulos/{cod}/redactar` | `{indicaciones?}` → 202: vuelve a redactar (sustituye título y texto) |
| `PUT /api/seo/articulos/{cod}` | `{titulo, slug, metaDescription, contenido}`; el slug se normaliza. 409 mientras se redacta |
| `POST /api/seo/articulos/{cod}/wordpress` | `{publicar?}`: crea la entrada (draft) o actualiza la ya enviada sin tocar su estado; `publicar: true` solo admin (403). 409 si quedan «[COMPLETAR: …]». Con imagen, la sube a Medios (una vez; luego solo actualiza alt y leyenda) y la pone como `featured_media` |
| `GET /api/seo/imagenes` · `POST …/buscar` | Fuentes de imagen `{fotos: PIXABAY\|PEXELS\|null, gemini, modelo, precio_usd}` · `{consulta, pagina?}` → `{fotos[], total, pagina, hay_mas, fuente}` |
| `POST /api/seo/articulos/{cod}/imagen/foto` · `…/imagen/generar` | `{id, alt?}` descarga esa foto del banco · `{descripcion, alt?}` la genera con Gemini (de pago; registra consumo `seo_imagen`). Sustituye la anterior; → artículo con `imagen` |
| `GET /api/seo/articulos/{cod}/imagen` · `PUT` · `DELETE` | Los bytes (404 sin imagen) · `{alt, leyenda}` (alt obligatorio) · quitarla (no toca WordPress) |
| `POST /api/seo/articulos/{cod}/desvincular` · `DELETE …/{cod}` | Olvidar la entrada de WordPress · borrar (solo admin; no toca WordPress) |
| `POST /api/seo/vista-previa` | `{contenido}` → `{html, pendientes}` con el mismo conversor que el envío |
| `GET /api/seo/search-console` | `{configuracion: {completo, faltan[], propiedad, pais}, sincronizacion: {propiedad, desde, hasta, pais, filas, fecha} \| null, resumen: {consultas, clics, impresiones}, oportunidades: [{url, impresiones, clics, ctr, posicion, consultas[], mejora \| null}], marca: [palabras]}` (`oportunidades`: páginas con búsquedas sin marca en la posición 4-20, ≥ 30 impresiones) |
| `PUT /api/seo/search-console/marca` | `{palabras[]}` (solo admin, 1-60) → lo mismo que el GET |
| `PUT /api/seo/search-console/terminos` | `{terminos[{nombre (2-120), tipo: CARRERA \| SISTEMA \| OTRO, descripcion (≤ 500)}]}` (solo admin, ≤ 100, sin repetidos) → lo mismo que el GET, que trae `terminos`. Por defecto, las 5 carreras y 2 programas Master de ilcb.edu.pe |
| `POST /api/seo/mejoras` | `{url}` de una oportunidad → `{url, consultas[], tituloActual, metaActual, titulo, metaDescription, ideas[{donde, diceAhora (null si es nuevo), debeDecir}], motivo, estado, creado, modificado}` (Gemini; sustituye la anterior). Los términos protegidos salen como están definidos; si la IA los alarga se reintenta una vez y luego 502. 404 si la URL no está en la lista |
| `PUT /api/seo/mejoras/estado` | `{url, estado: PROPUESTA \| APLICADA \| DESCARTADA}` → la mejora |
| `POST /api/seo/search-console/comprobar` | `{ok, propiedad, permiso, propiedades[]}`: qué propiedades ve la cuenta autorizada |
| `POST /api/seo/search-console/sincronizar` | Trae los últimos 90 días y reemplaza los anteriores → lo mismo que el GET. 409 si el flujo automático está en marcha |
| `GET /api/seo/automatico` · `PUT` | Flujo automático `{activo, dia (1 = lunes), hora (HH:MM, Lima), articulos (1-5), ultima, proxima, tarea, candidatos, descartados, google}` (`candidatos`: lo que redactaría hoy, en orden: `{grupo, keyword, busquedas, paginas, sitios, relevancia, google (EXACTA·VARIANTES·NINGUNA·null), sugerencias, gsc {impresiones, clics, posicion, url} \| null, motivo}`; `descartados`: los que la web ya posiciona (`motivo` YA_POSICIONA · MEJORAR_PAGINA) o Google no sugiere (GOOGLE_NO_SUGIERE); `google`: false si no respondió y el orden es solo por competidores) · cambiarlo (solo admin) |
| `POST /api/seo/automatico/ejecutar` | → 202: tarea `AUTOMATICO` ahora (solo admin). Encadena INVENTARIO de cada sitio activo, TEMAS de los que tienen pendientes, KEYWORDS, ARTICULO de hasta `articulos` grupos informacionales SIN_COBERTURA sin artículo, foto del banco y borrador en WordPress (no con «[COMPLETAR]»). Su `resumen`: `pasos`, `articulos`, `enviados`, `esperanDatos`, `avisos`. En pausa, `…/tareas/{cod}/continuar` retoma donde quedó |
| `GET /api/seo/wordpress` · `POST …/probar` | Qué falta en `.env` (sin la clave) · entrar y decir si el usuario puede crear, publicar y subir imágenes |

Una tarea queda `PAUSADA` si Gemini agota la cuota, si un sitio responde 403/429 o
si el backend se cierra a mitad. 409 si ya hay otra en marcha o faltan pasos previos.

## Videos

Solo admin: contexto, aprobar y borrar. El MP4 vive en `<radar.datos>/videos/<cod>.mp4`.

| Endpoint | Qué hace |
|---|---|
| `GET /api/videos` | Lista (más recientes primero) |
| `POST /api/videos` | `{idea, keyword?, segundos (10-60), formato (VERTICAL\|HORIZONTAL)}` → 201, estado `IDEA` |
| `GET /api/videos/{cod}` | El video: `partes [{dialogo, escena}]`, copys, `hashtags`, `estado`, `avance`, `error`, `tieneArchivo`, `vidsUrl` |
| `PUT /api/videos/{cod}` | Edita lo que venga (`titulo`, `segundos`, `formato`, `partes`, copys, `hashtags`). Un guion cambiado en un video `GENERADO`/`APROBADO` vuelve a `GUION`. 409 mientras `GENERANDO` |
| `POST /api/videos/{cod}/guion` | Gemini escribe una parte por cada 10 s, copys y hashtags → `GUION` |
| `GET /api/videos/{cod}/prompts` | `{prompts: []}`: lo que el robot escribirá en Vids, clip por clip |
| `POST /api/videos/{cod}/generar` | 202 → `GENERANDO`. 409 si hay «[FALTA: …]», si las partes no cuadran con la duración o si ya hay otro generándose. El backend consulta al worker cada 10 s; al terminar guarda el MP4 → `GENERADO` (o `ERROR` con el motivo) |
| `POST /api/videos/{cod}/cancelar` | Detiene el robot → `GUION` |
| `PUT /api/videos/{cod}/aprobacion` | `{aprobado}`: `GENERADO` ↔ `APROBADO` |
| `GET /api/videos/{cod}/archivo` | El MP4 (admite `Range`); `?descargar=true` lo baja |
| `DELETE /api/videos/{cod}` | Borra el video y su archivo (no mientras `GENERANDO`) |
| `GET/PUT /api/videos/contexto` | `{datos, personaje, estilo, voz, pronunciaciones [{texto, dice}]}` |
| `GET /api/videos/navegador` · `POST /api/videos/navegador/abrir` | Estado del Chrome de Vids (`{abierto, vids, sesion}`) · lo abre con su perfil |

## Publicaciones

Con sesión. Aprobar y borrar: solo admin. El archivo vive en `<radar.datos>/publicaciones/<cod>.<ext>`.
Estados: `BORRADOR` → `APROBADA` (admin) → `PUBLICADA` (cuando todas sus redes tienen enlace). Redes:
`FACEBOOK`, `INSTAGRAM`, `LINKEDIN`. Con algún enlace registrado ya no se edita (409).

| Endpoint | Qué hace |
|---|---|
| `GET /api/publicaciones` | Lista (más recientes primero), sin las archivadas; `?archivadas=true` = toda la biblioteca. Cada una trae `archivada` y `verificacion{red: {estado: ACTIVA \| NO_DISPONIBLE \| SIN_CONFIRMAR, detalle, http, fecha}}` |
| `GET /api/publicaciones/{cod}/historial` | `[{evento, detalle, datos, autor, fecha}]`: CREADA, TEXTOS, EDITADA, FONDO, FLYER, ARCHIVO, APROBADA, APROBACION_QUITADA, PUBLICADA (con el texto exacto publicado), ENLACE_QUITADO, VERIFICADA, ARCHIVADA, RESTAURADA |
| `POST /api/publicaciones/{cod}/verificar` · `POST /api/publicaciones/verificar` | Abre cada enlace publicado (sin sesión) y guarda si sigue: de una · de todas las que tienen enlaces, archivadas incluidas (→ `{publicaciones, enlaces, ACTIVA, NO_DISPONIBLE, SIN_CONFIRMAR}`). 409 sin enlaces |
| `POST /api/publicaciones` | `{idea (3-1000), redes[], modoCopy (POR_RED\|MISMO)}` → 201, `BORRADOR` |
| `POST /api/publicaciones/desde-video/{codVideo}` | Desde un video `APROBADO`: sus copys de Facebook e Instagram y una copia del MP4. Si ya existe, devuelve esa |
| `GET /api/publicaciones/{cod}` | `{codigo, titulo, idea, origen, codOrigen, redes, textos{red: texto}, hashtags, media (NINGUNA\|IMAGEN\|VIDEO), archivoTipo, enlaces{red: url}, modoCopy, flyer{titulo, detalle, cta, busqueda, descripcion, fondoOrigen, fondoCredito, fondoUrl, tieneFondo, enUso}, estado, aprobador}` |
| `PUT /api/publicaciones/{cod}` | Edita lo que venga (`titulo`, `idea`, `redes`, `textos`, `hashtags`, `modoCopy`, `flyer{titulo, detalle, cta, busqueda, descripcion}`). Si el flyer está en uso y cambian sus textos, se vuelve a armar. Un cambio en una `APROBADA` la devuelve a `BORRADOR` |
| `POST /api/publicaciones/{cod}/textos` | Gemini escribe el texto (por red o el mismo, según `modoCopy`), los hashtags del tema (detrás de los del rubro) y los textos del flyer |
| `GET /api/publicaciones/fotos?consulta=&pagina=` | Fotos verticales del banco gratuito para el fondo |
| `POST /api/publicaciones/{cod}/fondo/foto` · `/fondo/ia` · `/fondo` | Fondo del flyer: `{id}` del banco · `{descripcion?}` con Gemini (de pago, 4:5) · `multipart` `archivo` (JPG/PNG ≤ 8 MB). Con título, el flyer se arma al momento y pasa a ser la imagen |
| `POST /api/publicaciones/{cod}/flyer` | Vuelve a armar el flyer con el fondo guardado (por ejemplo, tras subir otro archivo) |
| `GET/PUT /api/publicaciones/marca` | `{color, acento (#RRGGBB), hashtags[], tieneLogo}`; cambiarla, solo admin |
| `POST/DELETE/GET /api/publicaciones/marca/logo` | El logo de los flyers: `multipart` `archivo` PNG/JPG ≤ 2 MB (solo admin) · quitarlo · servirlo |
| `POST /api/publicaciones/{cod}/archivo` | `multipart` `archivo`: JPG/PNG (≤ 8 MB) o MP4 (≤ 100 MB), según su contenido. Reemplaza el anterior |
| `DELETE /api/publicaciones/{cod}/archivo` · `GET …/archivo` | Quita el archivo · lo sirve (admite `Range`; `?descargar=true` lo baja) |
| `PUT /api/publicaciones/{cod}/aprobacion` | `{aprobada}`. Para aprobar: cada red con texto dentro de su límite (Facebook 5000, Instagram 2200 con hashtags, LinkedIn 3000), imagen o video si va a Instagram y sin «[FALTA: …]» (tampoco en el flyer en uso) |
| `PUT /api/publicaciones/{cod}/enlaces` | `{red, url}`: se publicó a mano. El enlace tiene que ser https y del dominio de esa red; `url` vacía lo quita |
| `DELETE /api/publicaciones/{cod}` · `POST …/restaurar` | No borra: **archiva** (solo admin) → la publicación; sale de la lista, sigue en la biblioteca con su archivo e historial, y no se edita · la devuelve |

## Medición

| Ruta | Qué hace |
|---|---|
| `GET /api/medicion/estado` | `{meta: {completo, faltan, detalle{nombre, moneda, activa, zona}}, ga4: {completo, faltan, propiedad}, sincronizacion, datos{desde, hasta, filas}, hoy}` |
| `POST /api/medicion/meta/sincronizar` | `{desde?}` → 202 y trae de Meta en segundo plano hasta hoy (por defecto: 90 días la primera vez; luego desde 7 días antes de lo último guardado). Reemplaza ese tramo. 409 si ya hay una en marcha |
| `GET /api/medicion/resumen?desde=&hasta=` | Por defecto los 30 días hasta ayer: `{periodo, anterior, moneda, kpis, kpisAnterior, serie[], campanas[], anuncios[] (50), alertas[]}`. `kpis`: gasto, impresiones, clicsEnlace, ctr, cpc, leads, costoLead, conversaciones, costoConversacion, gastoSinResultados… Cada campaña: `tipo` LEADS \| CONVERSACIONES \| SIN_RESULTADOS, `linea/canal/producto`, costo por resultado y su cambio |
| `POST /api/medicion/informe` | `{desde, hasta}` → Gemini resume y se guarda como informe MEDICION (`/api/seo/informes?modulo=MEDICION`). 409 sin datos en el periodo |
| `GET /api/medicion/google?comprobar=` · `POST /api/medicion/google/conectar` | Estado de la conexión con Google (`valida`, `autorizado`, `vence`) · abre la vuelta en el worker y da `{url}` de Google (admin) |
| `PUT /api/medicion/ga4/propiedad` | `{propiedad}` → guarda `GA4_PROPIEDAD` (admin) |
| `GET /api/medicion/ga4?desde=&hasta=` · `GET /api/medicion/ga4/propiedades` | Canales, campañas UTM, páginas de entrada, días y eventos clave · las propiedades de GA4 que ve la cuenta |

## Análisis

| Método y ruta | Qué hace |
|---|---|
| `GET /api/analisis` | Lista (más recientes primero) |
| `GET /api/analisis/{cod}` | Estado, fase, mensaje, `hechos/total`, `error`, `pendiente`, `codInforme` |
| `POST /api/analisis/estimar` | `{anuncios, llamadas, costoGeminiUsd, costoApifyUsd, minutos}` |
| `POST /api/analisis` | Crea y encola (201). Cuerpo = `Peticion` |
| `POST /api/analisis/{cod}/continuar` | Retoma un análisis `pausado` |
| `POST /api/analisis/{cod}/terminar` | Informe con lo ya clasificado (solo `pausado`, con ≥1 anuncio relevante) |
| `POST /api/analisis/{cod}/pagina` | `{competidor, pageIds: []}` resuelve una `pendiente` con una o varias páginas del competidor; `[]` = dejarlo fuera (`pageId` suelto se sigue aceptando) |
| `POST /api/analisis/{cod}/cancelar` | Cancela (aborta la búsqueda de Apify si está en curso) |
| `DELETE /api/analisis/{cod}` | Borrado lógico (no si está activo) |
| `GET /api/analisis/semanal` | Informe semanal: `{activo, dia (1=lunes), hora (Lima), peticion, ultima, proxima, analisis}` (`analisis` = el de la última ejecución) |
| `PUT /api/analisis/semanal` | Solo admin. `{activo?, dia?, hora?, peticion?}`; lo que no viene se conserva. `peticion` se valida como la de `POST /api/analisis` |
| `POST /api/analisis/semanal/ejecutar` | Solo admin. Lanza ya la ejecución semanal (201, el análisis creado) |

`Peticion`: `misMarcas[]`, `competidores[{nombre, nivel 1-4}]`, `keywords[]`,
`referencia[]`, `pais` (2 letras), `maximo` (10-500), `soloActivos`, `conMedios`.
Un `nombre` puede ser un enlace de Facebook o un id numérico: se usa esa página.
Tus marcas son opcionales: `marcas[{nombre, paginas[]}]` (las páginas, como en un
competidor) y `misMarcas[]` (solo nombres; lo único que traen las peticiones antiguas).
Cada marca que no esté ya entre los competidores se añade como competidor de nivel 3
con sus páginas (sus anuncios se buscan y entran al informe). El informe reconoce tus
anuncios por las páginas identificadas de tus marcas (`mis_paginas`), no por el nombre.
Sin marcas, el análisis es solo de los competidores.

Estados: `en_cola → corriendo → terminado`; cualquier fallo → `pausado`
(con `error`); `cancelado`. Fases: `buscando → clasificando → territorios → informe`.
Al reiniciar el backend, lo que estaba en marcha queda `pausado`.

| `POST /api/analisis/paginas` | `{texto, pais}` → `{paginas: [{page_id, nombre, categoria, avatar, seguidores, ig_usuario, ig_seguidores, alias, verificada}]}`. Menos de 3 letras: lista vacía sin consultar a Meta |
| `POST /api/analisis/paginas/preparar` | `{pais}` → 204. Abre por adelantado el Chrome de las sugerencias |

`Competidor.paginas[{pageId, nombre, avatar?, categoria?, seguidores?}]`: si trae
páginas, la búsqueda va por ellas y no se pregunta cuál es. Ids no numéricos se
descartan; máximo 10 por competidor. El filtro del sector recibe como referencia
los negocios de referencia + los nombres de competidores y páginas.

## Informes

| Método y ruta | Qué hace |
|---|---|
| `GET /api/informes?archivados=` | Lista con portada (lo que más satura, lo que más falta) |
| `GET /api/informes/{cod}` | `{resumen, datos}`; `datos` = informe completo del worker |
| `GET /api/informes/miniaturas/{adId}` | Miniatura guardada del anuncio (JPEG ≤ 720 px; 404 si no hay). Los informes nuevos llevan esta ruta en `thumb_url`: los enlaces de Meta caducan a los ~4 días |
| `POST /api/informes/ejemplo` | Crea el informe de muestra (anuncios inventados), una sola vez |
| `PUT /api/informes/{cod}/archivo` | `{archivado}` |
| `DELETE /api/informes/{cod}` | Borrado lógico |

## Sistema

`GET/PUT /api/mercado` (preferencias para rellenar el formulario) ·
`GET /api/sistema` (salud del worker + gasto de IA del mes) ·
`POST /api/sistema/comprobar` (valida claves) · `GET /api/taxonomia`.
