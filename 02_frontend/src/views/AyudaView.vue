<script setup lang="ts">
/** Preguntas frecuentes y, para cada mensaje de error, qué lo causa y qué hacer. Con buscador. */
import { computed, ref } from 'vue'

interface Entrada {
  grupo: 'Empezar' | 'Entender el informe' | 'KeyWords Explorer' | 'Plan SEO' | 'Publicaciones' | 'Medición' | 'Si algo falla'
  q: string
  a: string
}

const ENTRADAS: Entrada[] = [
  {
    grupo: 'Empezar',
    q: '¿Qué necesito para hacer un informe?',
    a: 'Solo una clave gratuita y sin tarjeta: Gemini, que analiza los anuncios (aistudio.google.com → Get API key; va en 03_worker/.env y se comprueba en Ajustes). Los anuncios se leen gratis de la Biblioteca de Meta con el Chrome del equipo. Apify es opcional. Sin claves puedes abrir el informe de ejemplo.',
  },
  {
    grupo: 'Empezar',
    q: '¿Cuánto cuesta?',
    a: 'Nada dentro de los planes gratuitos. Los anuncios se descargan gratis de la Biblioteca de Meta (Apify es opcional: su plan gratuito da 5 US$ al mes). Gemini gratuito permite unas 20 peticiones al día por modelo; un análisis de 100 anuncios gasta 10-12, así que salen unos 5 informes al día repartidos entre los modelos. Con la facturación activada de Gemini, un informe de 100 anuncios cuesta unos 0,20 US$. Antes de lanzar, la pantalla Análisis de competencia te dice el costo estimado.',
  },
  {
    grupo: 'Empezar',
    q: '¿Qué es el nivel de un competidor?',
    a: 'Cuánto pesa su anuncio en los porcentajes. 1 · Directo: compite por tu mismo cliente en tu zona (pesa 2). 2 · Proximidad (1,5). 3 · Categoría (1). 4 · Nacional (0,75). Así un competidor de al lado cuenta más que una gran marca de otro país.',
  },
  {
    grupo: 'Empezar',
    q: '¿Por qué me pregunta cuál es la página de un competidor?',
    a: 'Porque el nombre coincide con varios negocios (por ejemplo, una academia en Lima y otra en Cusco). Elige la correcta antes de gastar IA. Para evitar la pregunta, elige sus páginas en las sugerencias al escribir su nombre, o pega el enlace de su página de Facebook o el id numérico: Radar usa esa página exacta.',
  },
  {
    grupo: 'Empezar',
    q: '¿Cómo elijo la página exacta de un competidor?',
    a: 'Escribe su nombre en «Competidores»: desde la tercera letra aparecen sus páginas de Facebook con foto, categoría y seguidores. Marca todas las que sean suyas (sedes, talleres…) y el análisis buscará solo sus anuncios. La primera sugerencia puede tardar unos segundos; las siguientes salen al momento. Si no aparece, pega el enlace de su página.',
  },
  {
    grupo: 'Entender el informe',
    q: '¿Por qué salen anuncios de empresas que no puse como competidor?',
    a: 'Porque pusiste «Palabras clave del mercado»: con ellas se buscan también otros anunciantes que usan esas palabras, y salen como «mercado». La IA descarta los que no son del mismo tipo que tus competidores y tus negocios de referencia (tiendas, fabricantes, restaurantes…). Si quieres un informe solo de tus competidores, deja ese campo vacío.',
  },
  {
    grupo: 'Entender el informe',
    q: '¿Qué mide el informe y qué no?',
    a: 'Mide QUÉ anuncia cada negocio, no QUÉ le funciona: la Biblioteca de Anuncios de Meta no publica resultados. Lo único que deja deducir es cuánto tiempo lleva activo un anuncio; por eso se destacan los que llevan meses. El informe te dice dónde está el mercado; qué hacer con eso lo decides tú.',
  },
  {
    grupo: 'Entender el informe',
    q: '¿Qué es un territorio?',
    a: 'Una promesa que repite el mercado («salida laboral», «probar sin comprometerte»). La IA lee las etiquetas libres de cada anuncio y las agrupa de 8 a 15 territorios con las palabras del propio sector. Un territorio muy repetido está saturado; uno casi sin usar es un hueco: que esté libre no significa que funcione, significa que nadie lo ocupa.',
  },
  {
    grupo: 'Entender el informe',
    q: '¿Qué significan Muy repetido, Repetido, Habitual, Poco usado y Casi libre?',
    a: 'Es el porcentaje (ponderado por nivel) de anuncios que usa algo. Desde 40 %: muy repetido. 25-40 %: repetido. 10-25 %: habitual. 3-10 %: poco usado. Menos de 3 %: casi libre. Un anuncio puede tener varios ángulos, por eso una dimensión puede sumar más de 100 %.',
  },
  {
    grupo: 'Entender el informe',
    q: '¿Por qué hay anuncios que no aparecen en el informe?',
    a: 'La búsqueda por nombre arrastra anuncios de negocios ajenos. La IA decide si cada anuncio es del sector indicado (los negocios de referencia) y descarta los demás para no falsear los porcentajes. El informe indica cuántos se descartaron.',
  },
  {
    grupo: 'Entender el informe',
    q: '¿Por qué el informe me avisa de que la muestra es pequeña?',
    a: 'Con menos de 30 anuncios los porcentajes bailan mucho con un solo anuncio: trátalos como indicios. Sube el máximo de anuncios, añade competidores o palabras clave del sector.',
  },
  {
    grupo: 'Publicaciones',
    q: '¿Cómo publico en Facebook, Instagram y LinkedIn?',
    a: 'Publicaciones → escribe el tema, elige las redes y si quieres un texto para cada red o el mismo para todas. La IA escribe el texto y los títulos del flyer usando solo los datos confirmados. Elige el fondo del flyer (foto gratuita, IA o una foto propia) y el Radar lo arma con tu logo. Revisa los hashtags y la vista previa, y pide que un administrador la apruebe. Ya aprobada, en «Publicar» copias el texto, bajas el flyer, lo publicas en la red y pegas el enlace: así queda el registro de qué se publicó y dónde.',
  },
  {
    grupo: 'Publicaciones',
    q: '¿Dónde quedan los posts? ¿Se pueden borrar?',
    a: 'En Publicaciones → Biblioteca están todos, también los archivados: nada se borra, solo se archiva (y se puede restaurar). Cada uno tiene su historial: quién lo creó, editó y aprobó, y el texto exacto que se publicó en cada red. «Comprobar» abre cada enlace publicado como alguien sin sesión y dice si sigue: «Activa», «Ya no está» o «Sin confirmar». Facebook e Instagram suelen pedir sesión, así que muchas veces será «Sin confirmar»; lo confirmará la API de Meta cuando conectemos n8n.',
  },
  {
    grupo: 'Publicaciones',
    q: '¿Por qué el texto del flyer no lo escribe la IA dentro de la imagen?',
    a: 'Porque los generadores de imágenes escriben mal las palabras y deforman los logos (en las pruebas con Google Vids, «Le Cordon Bleu» salió como «Le Cordin Cuiz»). Por eso la IA o el banco de fotos dan solo el fondo, y el Radar pone encima el título, el detalle, el botón y el logo oficial: siempre bien escritos y con los colores de la marca (Publicaciones → Marca).',
  },
  {
    grupo: 'Publicaciones',
    q: '¿Los hashtags son los más usados?',
    a: 'Ninguna API gratuita dice cuántas veces se usa un hashtag. Por eso van primero los del rubro, que Marketing mantiene en Publicaciones → Marca según lo que ve en las redes, y después los que la IA propone para el tema de cada publicación.',
  },
  {
    grupo: 'Publicaciones',
    q: '¿Por qué no publica solo?',
    a: 'Porque publicar en nombre de la institución exige permisos de Meta y LinkedIn. El siguiente paso es enviarlo a n8n, que publicará lo aprobado; nunca lo que esté en borrador. Mientras tanto, el Radar prepara todo y tú lo publicas a mano.',
  },
  {
    grupo: 'Publicaciones',
    q: '¿Por qué no me deja editar una publicación?',
    a: 'Porque ya se publicó en alguna red (tiene un enlace registrado). Así lo guardado coincide con lo publicado. Si hay que cambiar algo, crea otra publicación.',
  },
  {
    grupo: 'Plan SEO',
    q: '¿Qué hace el Plan SEO?',
    a: 'Propone artículos informacionales para ilcb.edu.pe a partir de lo que publican D’Gallia, CENFOTUR y USIL. En tres pasos: 1) inventario de cada sitio (sus páginas, títulos y encabezados, sin IA); 2) temas: Gemini lee las páginas de los competidores y dice qué búsquedas informacionales tocan; 3) keywords: se agrupan, se clasifica su intención y se mira si ILCB ya tiene una página que las responda.',
  },
  {
    grupo: 'Medición',
    q: '¿De dónde salen las cifras de Medición?',
    a: 'De la cuenta publicitaria de ILCB en Meta, con el token de solo lectura que entregó Marketing: gasto, impresiones, clics, leads (formularios de Lead Ads) y conversaciones (chats de WhatsApp iniciados desde un anuncio), por anuncio y por día. Se actualizan cada mañana a las 7:20 o con «Actualizar datos». Leads y conversaciones no se suman: cada campaña cuenta el resultado que produce y su costo se calcula con su propio gasto. Una campaña es de WhatsApp si sus chats llegan al 5 % de sus clics (las de WhatsApp de ILCB andan entre el 10 y el 30 %); las de web o visualizaciones que traen algún chat suelto quedan como «Web, alcance u otro», y su efecto se ve en GA4.',
  },
  {
    grupo: 'Medición',
    q: '¿Cómo se calculan las alertas?',
    a: 'Sin IA: los últimos 7 días frente a los 7 anteriores. Avisan cuando el costo por resultado de una campaña sube un 30 % o más, cuando el CTR cae un 30 % o más (posible cansancio de la creatividad), cuando un anuncio gasta más del doble del costo medio por resultado de su campaña sin traer ninguno, cuando una campaña rinde mucho mejor que el promedio y cuando el gasto total cambia un 40 % o más. Piden un mínimo de 10 resultados y 5000 impresiones para no alarmar por pocas diferencias.',
  },
  {
    grupo: 'Medición',
    q: '¿Qué son los UTM y por qué los posts ya los llevan?',
    a: 'Son parámetros al final de un enlace (utm_source, utm_medium, utm_campaign) que le dicen a Google Analytics de dónde vino la visita. Las publicaciones los añaden solas a los enlaces a ilcb.edu.pe en Facebook y LinkedIn (en Instagram los enlaces del texto no se pueden pulsar). Para los anuncios de Meta, en Medición está el texto para «Parámetros de URL», que Meta completa con el nombre de la campaña, el conjunto y el anuncio.',
  },
  {
    grupo: 'Plan SEO',
    q: '¿Para qué sirve la fecha mínima de publicación?',
    a: 'Para no cargar ni analizar información muy antigua (por ejemplo, noticias de 2018). En «Sitios» → «Fecha mínima de publicación»: las páginas anteriores quedan como «Antigua» y no se leen ni pasan a temas ni keywords. La fecha es la que declara la página o, si aún no se leyó, la última modificación de su sitemap; las que no dicen fecha se leen igual. Quitar el límite las devuelve. En Análisis de competencia hay otra fecha mínima: deja fuera los anuncios que empezaron antes y ya terminaron.',
  },
  {
    grupo: 'Plan SEO',
    q: '¿Se guardan los informes de Search Console y de keywords?',
    a: 'Sí. Cada «Traer últimos 90 días» y cada «Generar keywords» queda guardado con su fecha en «Informes guardados»: se puede volver a abrir, bajar en CSV y, si es de Search Console, volver a cargar como los datos actuales. No se borran.',
  },
  {
    grupo: 'Plan SEO',
    q: '¿La IA puede cambiar el nombre de una carrera o de un sistema?',
    a: 'No. En «Páginas para mejorar» → «Términos protegidos» están las carreras, los programas y los sistemas con su nombre oficial (y, para los sistemas, su descripción oficial). Las propuestas los escriben exactamente así; si la IA los alarga o los cambia (por ejemplo «Gastronomía y Arte Culinario»), el Radar le pide otra propuesta y, si insiste, no la guarda. Cada cambio se muestra como «Dice ahora» y «Debe decir» para que lo compares antes de aplicarlo.',
  },
  {
    grupo: 'Plan SEO',
    q: '¿Las keywords son seguras? ¿El competidor posiciona por ellas?',
    a: 'Todavía no se sabe. Son hipótesis («tema observado»): salen del contenido público del competidor, no de Google. Que un sitio tenga una página sobre un tema no demuestra que aparezca en Google por esa búsqueda, ni dice cuánta gente la busca. Comprobar la posición en Google y el volumen es la fase siguiente del plan.',
  },
  {
    grupo: 'Plan SEO',
    q: '¿Por qué hay páginas «Excluidas»?',
    a: 'Son páginas de servicio que no dicen nada del contenido del sitio (carrito, pago, mi cuenta, contacto, portal de transparencia, archivos PDF o listados paginados). Se registran con su motivo pero no se descargan. Tampoco se recorren los sitemaps de categorías, etiquetas o autores.',
  },
  {
    grupo: 'Plan SEO',
    q: '¿Cuánto tarda un inventario? ¿Molesta a los sitios?',
    a: 'Se lee una página por segundo como mínimo (más lento si su robots.txt lo pide) y se respeta lo que robots.txt no permite leer: unas 290 páginas de ILCB tardan unos 12 minutos. Si un sitio responde 403 o 429 se deja de leer y la tarea queda en pausa. Repetir el inventario solo descarga las páginas nuevas, las que cambiaron y las que fallaron.',
  },
  {
    grupo: 'Plan SEO',
    q: 'D’Gallia apenas da keywords',
    a: 'Su web casi no tiene contenido informativo: en octubre de 2026 su sitemap declaraba 19 páginas (carreras, sedes, tienda) y su blog estaba vacío. No se fuerzan keywords donde no hay evidencia. Las oportunidades frente a D’Gallia tendrán que salir de la comprobación en Google (fase siguiente), no de su web.',
  },
  {
    grupo: 'KeyWords Explorer',
    q: '¿De dónde salen los datos y por qué no coinciden con Ahrefs?',
    a: 'Del Planificador de palabras clave de Google Ads (Keyword Planner): volumen mensual, tendencia de 12 meses, puja (CPC) y competencia entre anunciantes. Ahrefs usa su propio índice y modelos, así que las cifras no serán idénticas. Además, Keyword Planner no entrega dificultad orgánica (KD), clics, resultados de la SERP ni potencial de tráfico: esos datos no se muestran ni se inventan.',
  },
  {
    grupo: 'KeyWords Explorer',
    q: 'Los volúmenes salen como 10, 100, 1.000…',
    a: 'Google agrupa los volúmenes cuando la cuenta de Google Ads no tiene inversión reciente en anuncios. Sirven para comparar órdenes de magnitud. Para cifras exactas hace falta una cuenta con campañas activas.',
  },
  {
    grupo: 'KeyWords Explorer',
    q: '¿Qué significan I, C, T, N, ? y G en la tabla?',
    a: 'La intención de búsqueda se estima con reglas sobre el texto de la keyword: I informacional (quiere aprender), C comercial (compara), T transaccional (quiere comprar), N navegacional (busca una marca). «?» marca preguntas y «G» las keywords que aparecen en el autocompletado de Google. Son orientativas, no una clasificación de Google.',
  },
  {
    grupo: 'KeyWords Explorer',
    q: '«Competencia ads» no es la dificultad para posicionarme',
    a: 'Mide cuántos anunciantes pujan por esa keyword (0 a 100), no lo difícil que es salir en los resultados orgánicos. Una keyword puede tener poca competencia de anuncios y ser muy difícil de posicionar, y al revés.',
  },
  {
    grupo: 'KeyWords Explorer',
    q: 'Usé «datos de demostración»: ¿son reales?',
    a: 'No. Son números inventados, siempre iguales para la misma búsqueda, para que puedas probar el módulo sin conectar Google Ads. Se marcan en amarillo en todas partes y no se pueden mezclar en una lista con datos reales.',
  },
  {
    grupo: 'Si algo falla',
    q: '«El developer token solo tiene acceso de prueba»',
    a: 'Un token en modo «prueba» solo funciona con cuentas de prueba de Google Ads. Solicita acceso Básico en el Centro de API de tu cuenta administradora (Herramientas → Configuración → Centro de API); Google suele responder en pocos días.',
  },
  {
    grupo: 'Si algo falla',
    q: '«Google respondió 404: la versión de la API ya no existe»',
    a: 'Google retira cada versión de su API pasado un año. Sube GOOGLE_ADS_API_VERSION en 03_worker/.env (por ejemplo v25) y reinicia el worker.',
  },
  {
    grupo: 'Si algo falla',
    q: '«Se agotó la cuota diaria gratuita de Gemini»',
    a: 'El análisis se pausa y lo hecho queda guardado. Tienes tres salidas: esperar a que se renueve (hacia las 3:00 hora de Perú) y pulsar Continuar; poner una clave de reserva de otra cuenta de Google (GEMINI_API_KEY_2); o pulsar «Terminar con lo analizado» para hacer el informe con lo que ya hay.',
  },
  {
    grupo: 'Si algo falla',
    q: '«El worker no responde»',
    a: 'El programa que lee la Biblioteca de Meta y habla con Gemini no está en marcha. Abre iniciar.bat (levanta worker, backend y panel). Si ya lo abriste, mira la ventana «Radar - Worker» por si muestra un error.',
  },
  {
    grupo: 'Si algo falla',
    q: '«Meta pidió iniciar sesión» o la búsqueda de anuncios no avanza',
    a: 'Radar lee la Biblioteca de Anuncios de Meta con Chrome, igual que una persona. Si se hacen muchas búsquedas seguidas, Meta puede frenarlas un rato: espera una hora y pulsa «Continuar». Si pasa a menudo, reduce el máximo de anuncios o usa Apify (APIFY_TOKEN en 03_worker/.env).',
  },
  {
    grupo: 'Si algo falla',
    q: '«No se pudo abrir Chrome para leer la Biblioteca de Meta»',
    a: 'El worker necesita Google Chrome instalado (o el Chromium de Playwright: en una terminal, cd 03_worker y python -m playwright install chromium).',
  },
  {
    grupo: 'Si algo falla',
    q: '«Apify ha rechazado el token» o «Todos los tokens están sin crédito»',
    a: 'El token está mal copiado o se agotaron los 5 US$ del mes. Compruébalo en Ajustes → Comprobar ahora, que dice cuánto crédito queda. Puedes añadir un segundo token (APIFY_TOKEN_2) de otra cuenta.',
  },
  {
    grupo: 'Si algo falla',
    q: '«Meta no devolvió ningún anuncio para esta búsqueda»',
    a: 'Ese nombre no tiene anuncios activos en ese país. Revisa la ortografía, prueba con el enlace de su página de Facebook, cambia el país o desmarca «Solo anuncios activos».',
  },
  {
    grupo: 'Si algo falla',
    q: 'Cerré la pestaña a mitad de un análisis',
    a: 'No se pierde: el análisis sigue en el backend. Vuelve a Informes y verás «En curso». Si cerraste el programa entero, queda pausado y «Continuar» retoma exactamente donde se quedó, sin volver a pagar lo ya analizado.',
  },
  {
    grupo: 'Si algo falla',
    q: 'Las imágenes de los anuncios no se ven',
    a: 'Meta caduca las direcciones de las imágenes pasados unos días. El texto y el análisis siguen ahí; el enlace «ver anuncio» abre el original en la Biblioteca de Meta mientras siga activo.',
  },
]

const busqueda = ref('')
const GRUPOS = ['Empezar', 'Entender el informe', 'KeyWords Explorer', 'Plan SEO', 'Publicaciones', 'Medición', 'Si algo falla'] as const

const visibles = computed(() => {
  const t = busqueda.value.trim().toLowerCase()
  return ENTRADAS.filter((e) => !t || `${e.q} ${e.a}`.toLowerCase().includes(t))
})
</script>

<template>
  <div class="pagina estrecha">
    <div class="pagina-cabecera">
      <div>
        <h1>Ayuda</h1>
        <p>Preguntas frecuentes y, para cada mensaje de error, qué lo causa y qué hacer.</p>
      </div>
    </div>

    <div class="campo buscador">
      <label for="buscar" class="oculto-visual">Buscar en la ayuda</label>
      <input id="buscar" v-model="busqueda" type="search" placeholder="Buscar: cuota, token, territorio…" />
    </div>

    <p v-if="!visibles.length" class="vacio">Nada coincide con «{{ busqueda }}».</p>

    <template v-for="g in GRUPOS" :key="g">
      <section v-if="visibles.some((e) => e.grupo === g)" class="panel">
        <h2>{{ g }}</h2>
        <details v-for="e in visibles.filter((x) => x.grupo === g)" :key="e.q" :open="!!busqueda.trim()">
          <summary>{{ e.q }}</summary>
          <p>{{ e.a }}</p>
        </details>
      </section>
    </template>

    <section class="panel aviso-legal">
      <h2>Aviso</h2>
      <p class="suave chico">
        Radar analiza anuncios que Meta publica en su Biblioteca de Anuncios, que es pública. Se ofrece tal cual, sin
        garantías: la clasificación la hace una IA y puede equivocarse. Úsalo para orientarte, no como única base de una
        decisión.
      </p>
    </section>
  </div>
</template>

<style scoped>
.estrecha {
  max-width: 860px;
}
.buscador {
  margin-bottom: 16px;
}
.panel + .panel {
  margin-top: 16px;
}
details {
  border-top: 1px solid var(--borde);
  padding: 10px 0;
}
details:first-of-type {
  margin-top: 10px;
}
summary {
  cursor: pointer;
  font-weight: 600;
}
summary:hover {
  color: var(--cian);
}
details p {
  margin-top: 8px;
  color: var(--texto-suave);
}
</style>
