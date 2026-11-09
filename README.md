# Radar de Anuncios

Analiza los anuncios que tu competencia tiene activos en Facebook e Instagram
y te dice **qué repite todo el mercado y dónde está el hueco**.

Es la versión propia, con el stack de la casa, del *Radar de Anuncios* de BIG
school (licencia MIT, original en Cloudflare/React). Se estudió su build
compilado: de ahí salen el método (niveles de competidor, territorios,
"meses funcionando"), las listas cerradas y las reglas de clasificación. El
código es nuevo.

## Acceso y usuarios

La primera vez, el panel pide crear la cuenta de **administrador** y muestra
una sola vez su **código de recuperación**. Después el administrador da acceso
al equipo desde **Usuarios** (rol *administrador* o *miembro*): cada persona
recibe una contraseña temporal y la cambia al entrar. Los miembros analizan y
leen informes; solo los administradores gestionan usuarios y comprueban las
claves. Contraseñas con PBKDF2, sesión por cookie HttpOnly, bloqueo tras 5
fallos y registro de actividad. Siempre queda al menos un administrador.

## KeyWords Explorer

Módulo de investigación de palabras clave inspirado en el Keywords Explorer de
Ahrefs, con datos de **Google Ads Keyword Planner** (gratis, requiere una cuenta
de Google Ads y un developer token con acceso Básico).

- **Buscar** por palabras (hasta 20) o desde una URL, en un país e idioma.
- **Resumen** de una keyword: volumen mensual, CPC (rango de puja), competencia de
  anuncios, tendencia de 12 meses con gráfico y mes pico, variaciones que Google
  agrupa, volumen en 8 países, ideas y preguntas principales.
- **Ideas**: todas · términos coincidentes · relacionados · preguntas · sugerencias
  del autocompletado de Google; agrupación **por término**, filtros (volumen, CPC,
  competencia, intención, nº de palabras, incluir/excluir), orden por columna.
- **Listas** de keywords con notas, actualización de métricas y **exportación CSV**.
- Historial y caché de 7 días (no gasta cuota de Google al repetir una búsqueda).
- **Modo demostración** con datos inventados (marcados en todas partes) para usarlo
  sin conectar Google Ads.

**Lo que no puede igualar a Ahrefs:** Keyword Planner no entrega dificultad orgánica
(KD), clics, SERP ni potencial de tráfico; no se muestran ni se inventan. La
intención de búsqueda es una estimación por reglas. Las cifras no coincidirán con
las de Ahrefs (índices distintos). Sin inversión en anuncios, Google devuelve
volúmenes agrupados (10, 100, 1 000…) y el panel lo avisa.

Conexión: `03_worker/.env` (`GOOGLE_ADS_*`, ver `.env.example`) y
`python -m app.keywords.autorizar` para el refresh token. La guía paso a paso está
en el propio módulo.

## Plan SEO

Primera parte del plan maestro de automatización SEO de ILCB (`ILCB - SEO Research`),
hecha en Radar en vez de en Make: sin coste por operación y con caché de páginas.

- **Inventario** de ilcb.edu.pe y de los competidores aprobados (D'Gallia, CENFOTUR
  con sus dos sitios, USIL): robots.txt, sitemaps (índices, WordPress y Yoast; si no
  hay, los enlaces de la portada) y, de cada página, title, meta description, H1,
  H2, canonical, idioma y un extracto. Una fila por URL; repetir solo descarga lo
  nuevo, lo cambiado y lo que falló. Rastreo lento (≥ 1 s por página) y respetando
  robots.txt. Páginas de servicio (carrito, cuenta, contacto…) y taxonomías excluidas
  con su motivo.
- **Temas** (Gemini): de qué trata cada página y qué búsquedas informacionales toca,
  con citas de la propia página como evidencia.
- **Keywords candidatas** (Gemini): intención (informacional, comercial,
  transaccional, de marca), grupos de búsquedas equivalentes y **cobertura en ILCB**
  (ya cubierta, parcial, sin cobertura, incierta) con la página propia más cercana.
  Exportación CSV.
- **Rubro de tu negocio**: una frase que la IA usa para medir la relevancia y las
  palabras del filtro gratuito que descarta, sin IA, las páginas de competidores que no
  son del rubro. Por defecto, el de ILCB; se puede cambiar (o pedir una sugerencia que
  lee la web propia) para usar el módulo con otro negocio.
- **Artículos** (Gemini + WordPress): desde una keyword, la IA redacta un borrador en
  Markdown que responde esa búsqueda, con lo que publican los competidores como contexto
  y enlaces solo a páginas propias que existen. Los datos del negocio que no puede saber
  quedan como «[COMPLETAR: …]» y bloquean el envío. Se edita con vista previa y se envía
  a WordPress (API REST + contraseña de aplicación en `03_worker/.env`) como borrador;
  publicar directamente, solo un admin.
- **Imagen destacada** de cada artículo: una foto de Pixabay (gratis; clave en
  `PIXABAY_API_KEY`) o una imagen generada con Gemini (de pago: la API no tiene plan
  gratuito de imágenes, hace falta la facturación activa; ~US$ 0.034 por imagen). Lleva
  texto alternativo y leyenda (crédito del fotógrafo o «Imagen generada con IA») y va a
  WordPress como imagen destacada.

- **Flujo automático** (pestaña Artículos, solo admin): una vez por semana (día y hora a
  elegir) hace todo lo anterior y deja hasta N artículos (1-5) como **borrador** en
  WordPress, con foto del banco. Solo redacta lo que la gente escribe en Google (lo dice su
  autocompletado), con la frase tal como la escriben. Los que tienen «[COMPLETAR]» esperan en el Radar.
  **No publica**: eso lo hace la persona. Solo corre con el Radar abierto (si a la hora
  estaba cerrado, corre al abrirlo).

Sitios, rubro y artículos se gestionan desde el panel. Los sitios se agregan, editan y
quitan desde sus tarjetas.

Las keywords son **hipótesis** (evidencia «tema observado»): todavía no se comprueba la
posición en Google ni el volumen. Pendiente según el plan: validación SERP, volumen
(Keyword Planner, ya integrado en KeyWords Explorer) y calendario de artículos.

**Search Console** (pestaña Keywords) trae por qué búsquedas ya aparece la web propia,
con cifras reales: el flujo automático no escribe lo que ya posiciona y el panel lista
las páginas para mejorar (posición 11-20). Usa la misma autorización de Google que
Google Ads; la cuenta que autoriza necesita acceso «Restringido» a la propiedad.

## Videos

Videos cortos para Reels a partir de una idea o una palabra clave:

1. **Guion por partes de 10 s** (Gemini): diálogo y escena de cada clip, y los copys de Facebook e
   Instagram. Solo usa los datos confirmados; lo que falta queda como «[FALTA: …]» y bloquea la
   generación.
2. **Google Vids**: el Radar maneja un Chrome propio donde la persona inició sesión. Crea el primer
   clip y **extiende** los siguientes, para que el personaje y la voz no cambien. Después descarga el
   MP4. Cada 10 s gastan una generación: el plan gratuito da unas 10 al mes.
3. **Aprobación** de un administrador. Aprobado, «Crear publicación» lo pasa a Publicaciones con sus copys.

El contexto común está en la misma pantalla: protagonista, lugar, voz y pronunciaciones (por ejemplo,
«Le Cordon Bleu» se dice «Le Cordón Blé»).

## Publicaciones

Posts para **Facebook, Instagram y LinkedIn**. El flujo:

```text
 1. Tema           ─► 2. Texto (IA)          ─► 3. Flyer                 ─► 4. Hashtags      ─► 5. Aprobación ─► 6. Publicar
    redes elegidas      uno por red o el         fondo: foto gratuita,       los del rubro       un admin,       hoy a mano y se registra
                        mismo para todas         IA o propia; el Radar       + los del tema      1 clic          el enlace; después, n8n
                                                 pone título, detalle,
                                                 botón y logo
```

1. **Texto.** Gemini escribe uno distinto para cada red (Facebook cercano, Instagram corto, LinkedIn
   profesional) o uno solo para todas, según se elija. Usa los mismos datos confirmados que los videos:
   lo que falta queda como «[FALTA: …]» y bloquea la aprobación. Escribe también los textos del flyer.
2. **Flyer** (1080×1350, 4:5, sirve para las tres redes). El fondo sale de Pixabay (gratis), de Gemini
   (de pago, ~US$ 0,03) o de una foto propia; el **texto y el logo los pone el Radar** con una plantilla
   (`app/publicaciones/flyer.py`), porque la IA escribe mal palabras y logos. En vez del flyer se puede
   subir un archivo propio: JPG o PNG hasta 8 MB o MP4 hasta 100 MB (el tipo sale del contenido). Un
   video aprobado llega desde Videos.
3. **Hashtags**: primero los del rubro (Publicaciones → Marca, los mantiene Marketing) y luego los que
   la IA propone para el tema. Ninguna API gratuita dice cuáles se usan más.
4. **Aprobación** de un administrador: cada red con su texto dentro del límite, Instagram con imagen o
   video y nada por completar (tampoco en el flyer).
5. **Publicar.** Por ahora a mano: copiar el texto, bajar el flyer, publicarlo y pegar el enlace de
   cada red. Con todas las redes registradas queda «Publicada», y desde la primera ya no se edita.

**Biblioteca** (pestaña en Publicaciones): todas las publicaciones, también las archivadas; nada se
borra. Cada una guarda su historial (quién hizo qué, y el texto exacto que se publicó en cada red) y
se puede comprobar si cada enlace sigue en su red: el Radar lo abre como alguien sin sesión y dice
«Activa», «Ya no está» o «Sin confirmar» (Facebook e Instagram suelen pedir sesión; lo confirmará
la API de Meta cuando se conecte n8n).

La marca de los flyers (logo, color principal y de acento, hashtags del rubro) está al pie de la
pantalla Publicaciones; la cambia un administrador.

El siguiente paso es enviar lo aprobado a **n8n** (instalado en la red de la oficina), que publicará
con una app de Meta propia en modo desarrollo. LinkedIn como página de empresa necesita que LinkedIn
apruebe la app (*Community Management API*).

## Medición

Qué funciona, con cifras reales:

- **Anuncios de Meta** (solo lectura, con el token de Marketing: usuario de sistema con `ads_read`). Cada día
  por anuncio en `meta_insight`: gasto, impresiones, clics, **leads** (formularios) y **conversaciones**
  (chats de WhatsApp). Se actualiza cada mañana a las 7:20 y con «Actualizar datos» (90 días ≈ 2,5 min).
  - Cifras del periodo frente al anterior: costo por lead (con el gasto de las campañas de leads) y por
    conversación (con el de las de WhatsApp). Una campaña es de WhatsApp si sus chats llegan al 5 % de sus
    clics (las reales andan en el 10-30 %; las de web traen alguno suelto).
  - Gráficos por día, campañas (línea, canal y producto salen del nombre), anuncios con más gasto.
  - **Alertas sin IA** (7 días frente a los 7 anteriores, con mínimos de volumen): se encarece, cae el CTR,
    anuncio que gasta sin resultados, rinde mejor que el promedio, cambio fuerte de gasto, datos viejos.
  - **Informe con IA** (Gemini, < 1 centavo): cuenta las cifras ya calculadas, sin inventar ni prometer; a
    las campañas con menos de 10 resultados no se les pasa el costo. Queda en Informes guardados (MEDICION).
- **GA4** (lo que pasa después del clic): canales, campañas UTM, páginas de entrada y eventos clave. Usa
  el mismo OAuth de Google y `GA4_PROPIEDAD`, que se elige en la lista de propiedades de Medición.
- **Conectar con Google** (Medición y Search Console, solo administradores): renueva el permiso de Google
  sin terminal. El worker recibe la vuelta en 127.0.0.1 y guarda el token en el `.env` sin reiniciar.
  Mientras el proyecto «Radar» de Google Cloud esté en modo Prueba, Google lo corta cada 7 días; el aviso
  dice cuándo vence (`GOOGLE_AUTORIZADO`). Desde el 2026-11-06 la app está en producción
  (`GOOGLE_APP_PRUEBA=false`): el permiso conseguido después de esa fecha no vence.
- **UTM**: los posts de Publicaciones los llevan solos en los enlaces a la web propia (Facebook y
  LinkedIn; `Utm.kt` y `composables/utm.ts` hacen lo mismo). En Medición hay un constructor de enlaces y
  los «Parámetros de URL» para todos los anuncios de Meta.

Verificado con la cuenta real el 2026-11-05: 30 días = US$ 23 725,51, 12 161 975 impresiones, 102 890 clics,
9887 leads y 3530 conversaciones, idénticos a lo que da Meta por cuenta.

## Cómo funciona

```text
 1. Buscar        Chrome lee la Biblioteca de Anuncios de Meta (gratis) o, si hay token, Apify
 2. Identificar   Si un nombre encaja con varias páginas, se le pregunta a la persona cuál es
 3. Analizar      Gemini clasifica cada anuncio (viendo imagen o video): hook, oferta, CTA,
                  formato, ángulos y beneficios libres, y si es del sector
 4. Territorios   Gemini agrupa las etiquetas libres en 8-15 territorios con palabras del sector
 5. Informe       Aritmética pura (sin IA): % ponderado por nivel, saturado / hueco, meses activos
```

El informe tiene mapa del mercado, anuncios que llevan meses funcionando,
cómo abren, galería filtrable y nueve secciones (ángulos, hooks, ofertas,
beneficios, visual, CTA, saturado, territorios libres, resumen).

**Lo que mide y lo que no:** la Biblioteca de Meta enseña *qué* anuncia cada
negocio, no *qué le funciona*. Lo único que insinúa resultados es cuánto lleva
activo un anuncio. El informe describe; no recomienda.

**Informe semanal** (Análisis de competencia, solo admin): repite el análisis del formulario cada semana, el
día y la hora elegidos, y deja un informe nuevo en «Informes». Recuerda la página que la persona
eligió cuando un nombre era ambiguo (no vuelve a preguntar) y reintenta sola una pausa por cuota de
Gemini cada 3 horas, hasta 4 veces. Solo corre con el Radar abierto.

**Es reanudable.** Cada lote clasificado se guarda. Si Gemini agota su cuota,
se cae la red o se cierra el programa, el análisis queda **pausado** y
«Continuar» retoma sin repetir la búsqueda ni volver a pagar lo ya analizado;
«Terminar con lo analizado» hace el informe con lo que hay.

## Stack

| Capa | Tecnología | Qué hace |
|---|---|---|
| Frontend | Vue 3 · TypeScript · Vite | Menú lateral con los módulos: Análisis de competencia, Informes, KeyWords Explorer, Plan SEO, Videos, Publicaciones, Usuarios, Ajustes, Ayuda; tema claro/oscuro |
| Backend | Kotlin · Spring Boot 4 · JDK 21 | Dueño del estado: ciclo del análisis, pausa/reanudar, checkpoint, informes, costos, cuentas y sesiones |
| Worker | Python · FastAPI | Apify, Gemini, normalización, identificación de competidores, cálculo del informe |
| Base de datos | SQLite (`01_backend/datos`) | Esquema en `04_bd` (DAT-01) |
| IA | Gemini 2.5 Flash → Flash-Lite → 3 Flash | Cambia de modelo cuando uno agota su cuota diaria |

## Estructura

```text
Radar/
├─ 01_backend/    Kotlin + Spring Boot · API y orquestación (contrato en LEEME.md)
├─ 02_frontend/   Vue 3 · panel
├─ 03_worker/     Python + FastAPI · analisis/ (puro), apify/, ia/, api/
├─ 04_bd/         esquema SQLite (única fuente; Gradle lo empaqueta)
├─ 05_pruebas/    flujo completo por la API, sin gastar nada
└─ 99_legado/     material archival
```

## Cómo arrancarlo

**Requisitos:** Python 3.14, Node 24, JDK 21.

**Atajo en Windows:** doble clic en `iniciar.bat` (levanta o reinicia los tres
procesos y abre <http://localhost:5175>); `detener.bat` los apaga. La primera
vez instala dependencias y crea `03_worker/.env`.

Puertos (no chocan con los otros módulos): worker 8102, backend 8082, panel 5175.

## Configuración (`03_worker/.env`)

| Clave | Para qué | Sin ella |
|---|---|---|
| `GEMINI_API_KEY` (+ `_2` de reserva) | Analizar los anuncios. aistudio.google.com → Get API key | No se puede analizar |
| `ANUNCIOS_FUENTE` | `auto` (por defecto: Apify si hay token, si no el navegador), `navegador` o `apify` | — |
| `APIFY_TOKEN` (+ `_2`) | Opcional: descargar los anuncios con Apify | Se usa el navegador, gratis |
| `GEMINI_PAGO=true` | Solo cambia el aviso de costo | — |
| `META_ACCESS_TOKEN`, `META_AD_ACCOUNT` | Medición: token de lectura de la cuenta publicitaria (lo da Marketing) y su `act_…` | Medición no muestra los anuncios |
| `GA4_PROPIEDAD` | Medición: id numérico de la propiedad de GA4 (más el OAuth de Google con Analytics) | Medición no muestra la web |

Sin claves se puede abrir el **informe de ejemplo** (anuncios inventados) desde
la pantalla de inicio. Ajustes → «Comprobar ahora» valida las claves.

**Costos:** descargar anuncios es gratis con la fuente «navegador» (el Chrome del equipo lee la Biblioteca de Meta, que es pública; ~20 s por búsqueda). Apify es opcional. Gemini gratuito ≈ 20
peticiones/día **por modelo**; un informe de 100 anuncios usa 10-12 (≈ 5
informes al día). Con facturación, ≈ 0,20 US$ por informe. La pantalla Nuevo
análisis muestra la estimación antes de lanzar.

## Cómo se verifica

| Prueba | Qué comprueba | Costo |
|---|---|---|
| `cd 03_worker && python -m pruebas.test_analisis` | Cálculo del informe, normalizador de Apify, identificación de competidores, reglas que corrigen al modelo | gratis |
| `python 05_pruebas/flujo_completo.py` | El ciclo por la API con un backend aislado (8092) y Apify/Gemini simulados: página ambigua, pausa por cuota, continuar sin repetir lo pagado, terminar con lo hecho, cancelar, archivar | gratis |

La segunda necesita el jar: `01_backend\arrancar.bat` lo compila.

## Pendiente / límites conocidos

- **No se ha probado contra Apify ni Gemini reales** (no se gastó crédito). El
  normalizador lee varias rutas por campo (`app/apify/normalizar.py`, `CAMPOS`)
  precisamente porque el actor cambia de formato; si falla con datos reales,
  es el primer sitio donde mirar.
- La cookie de sesión no lleva `Secure` (el panel corre en http://localhost): si
  algún día se publica por https hay que añadirlo.
- La fuente «navegador» lee la web pública de la Biblioteca de Meta: si Meta cambia
  la página habrá que ajustar `app/fuentes/navegador.py`, y muchas búsquedas seguidas
  pueden frenarse un rato. Las condiciones de Meta restringen la recogida automática
  (Apify hace lo mismo desde sus servidores). La API oficial de Meta no sirve aquí:
  fuera de la UE solo da anuncios políticos.
- El actor de Apify es de un tercero (`curious_coder~facebook-ads-library-scraper`):
  puede cambiar o dejar de existir.
- Se usa la clave de Gemini del entorno si `GEMINI_API_KEY` ya está definida en
  Windows; el `.env` solo completa lo que falte.
