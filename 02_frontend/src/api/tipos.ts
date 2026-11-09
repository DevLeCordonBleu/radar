/**
 * Tipos del contrato con el backend (`01_backend/LEEME.md`) y del informe que
 * calcula el worker (`03_worker/app/analisis/informe.py`).
 */

// ── Mercado y peticion ────────────────────────────────────────────────────

export interface Competidor {
  nombre: string
  /** 1 directo · 2 proximidad · 3 categoría · 4 nacional */
  nivel: number
  /** Sus páginas de Facebook elegidas de las sugerencias: el análisis busca por ellas. */
  paginas?: PaginaMeta[]
}

/** Una página de Facebook elegida para un competidor (lo que no es pageId es para mostrarla). */
export interface PaginaMeta {
  pageId: string
  nombre: string
  avatar?: string | null
  categoria?: string | null
  seguidores?: number | null
}

/** Sugerencia del autocompletado de la Biblioteca de Meta. */
export interface SugerenciaPagina {
  page_id: string
  nombre: string
  categoria: string | null
  avatar: string | null
  seguidores: number | null
  ig_usuario: string | null
  ig_seguidores: number | null
  alias: string | null
  verificada: boolean
}

/** Tu marca y sus páginas de Facebook. */
export interface Marca {
  nombre: string
  paginas?: PaginaMeta[]
}

export interface Peticion {
  misMarcas: string[]
  marcas?: Marca[]
  competidores: Competidor[]
  keywords: string[]
  referencia: string[]
  pais: string
  maximo: number
  soloActivos: boolean
  conMedios: boolean
  /** AAAA-MM-DD: sin los anuncios que empezaron antes y ya no están activos. */
  fechaMinima?: string | null
}

export interface Estimacion {
  anuncios: number
  llamadas: number
  costoGeminiUsd: number
  costoApifyUsd: number
  minutos: number
}

// ── Analisis ──────────────────────────────────────────────────────────────

export type EstadoAnalisis = 'en_cola' | 'corriendo' | 'pausado' | 'terminado' | 'cancelado'
export type FaseAnalisis = 'buscando' | 'clasificando' | 'territorios' | 'informe'

export interface Candidato {
  pageId: string
  nombre: string
  anuncios: number
  muestra: string | null
  /** Foto de perfil de la página. */
  avatar?: string | null
  /** Hasta 3 imágenes de sus anuncios, para reconocerla. */
  ejemplos?: string[]
  texto?: string | null
}

export interface Pendiente {
  tipo: 'elegir_pagina'
  competidor: string
  candidatos: Candidato[]
}

export interface Analisis {
  codigo: string
  peticion: Peticion
  estado: EstadoAnalisis
  fase: FaseAnalisis
  mensaje: string
  hechos: number
  total: number
  error: string | null
  pendiente: Pendiente | null
  codInforme: string | null
  creado: string
  modificado: string
}

/** Informe semanal: el mismo análisis cada semana, a la hora de Lima elegida. */
export interface AnalisisSemanal {
  activo: boolean
  /** 1 = lunes … 7 = domingo. */
  dia: number
  hora: string
  /** El formulario programado, con las páginas que ya aprendió. */
  peticion: Peticion | null
  ultima: string | null
  proxima: string | null
  /** El análisis de la última ejecución. */
  analisis: Analisis | null
}

// ── Informes ──────────────────────────────────────────────────────────────

export interface Portada {
  territorio: string | null
  pct: number | null
  hueco: string | null
}

export interface InformeFila {
  codigo: string
  marca: string
  anuncios: number
  anunciantes: number
  portada: Portada | null
  esEjemplo: boolean
  archivado: boolean
  creado: string
}

export type Frecuencia = 'muy_alta' | 'alta' | 'media' | 'baja' | 'hueco'

export interface FilaFrecuencia {
  clave: string
  pct: number
  anuncios: number
  anunciantes: number
  frecuencia: Frecuencia
  dimension?: string
}

export interface Territorio {
  nombre: string
  tipo: 'funcional' | 'emocional' | 'valores'
  etiquetas: string[]
}

export interface AnuncioInforme {
  ad_id: string
  anunciante: string
  page_id?: string | null
  nivel: number
  fecha_inicio: string
  activo: boolean
  copy?: string
  cta_texto?: string | null
  enlace?: string | null
  snapshot_url?: string | null
  thumb_url?: string | null
  video_url?: string | null
  /** Redes de Meta donde sale: facebook, instagram… (los informes antiguos no lo traen). */
  plataformas?: string[] | null
  hook_estructura: string
  hook_literal: string
  oferta_tipo: string
  cta_tipo: string
  formato: string
  patron_visual: string[]
  angulos_libres: string[]
  beneficios_libres: string[]
  precio_visible: boolean
  marca_en_3s: boolean
  subtitulos: boolean
  duracion_seg?: number | null
  territorios_angulo: string[]
  territorios_beneficio: string[]
  dias_activo?: number
}

export interface Titular {
  valor: string
  etiqueta: string
  detalle: string
}

export interface Informe {
  meta: {
    generado: string
    anuncios: number
    anunciantes: number
    sin_anuncios: string[]
    por_nivel: Record<string, number>
    identificadas: { buscado: string; page_id: string; anunciante: string; anuncios: number }[]
    aviso_muestra: string | null
    aviso_huerfanas: string | null
    cod_analisis?: string
    costo_ia_usd?: number
    llamadas_ia?: number
    descartados?: number
  }
  titulares: Titular[]
  angulos: FilaFrecuencia[]
  hooks: { patrones: FilaFrecuencia[]; ejemplos: { texto: string; anunciante: string }[] }
  ofertas: { patrones: FilaFrecuencia[]; mas_usada: FilaFrecuencia | null }
  beneficios: Record<'funcional' | 'emocional' | 'valores', FilaFrecuencia[]>
  visuales: { patrones: FilaFrecuencia[]; formatos: FilaFrecuencia[] }
  ctas: FilaFrecuencia[]
  saturado: { dominantes: FilaFrecuencia[]; poco_usados: FilaFrecuencia[] }
  huecos: FilaFrecuencia[]
  resumen: FilaFrecuencia[]
  veteranos: AnuncioInforme[]
  anuncios: AnuncioInforme[]
  territorios: Territorio[]
  mi_marca: string | null
  mis_anuncios: number
  /** Páginas de tus marcas con anuncios en el informe (los informes antiguos no lo traen). */
  mis_paginas?: string[]
  mis_territorios: string[]
}

export interface InformeCompleto {
  resumen: InformeFila
  datos: Informe
}

// ── Sistema ───────────────────────────────────────────────────────────────

export interface Salud {
  ok: boolean
  gemini: { claves: number; pago: boolean; modelos: string[]; finales: (string | null)[] }
  apify: { tokens: number; finales: (string | null)[] }
  /** De dónde salen los anuncios: «navegador» (gratis, Chrome del equipo) o «apify». */
  anuncios?: { fuente: 'navegador' | 'apify'; pedida: string }
}

export interface Sistema {
  worker: Salud | null
  costoMesUsd: number
}

export interface ResultadoClave {
  ok: boolean
  detalle: string
}

export interface Comprobacion {
  gemini: ResultadoClave[]
  apify: ResultadoClave[]
}

export interface Taxonomia {
  hooks: Record<string, string>
  ofertas: Record<string, string>
  ctas: Record<string, string>
  formatos: Record<string, string>
  patrones: Record<string, string>
  niveles: Record<string, { nombre: string; desc: string; peso: number }>
  muestra_minima: number
}

// ── Cuentas ───────────────────────────────────────────────────────────────

export type Rol = 'admin' | 'miembro'

export interface Usuario {
  codigo: string
  email: string
  nombre: string
  rol: Rol
  activo: boolean
  debeCambiar: boolean
  tieneRecuperacion: boolean
  ultimoAcceso: string | null
  creado: string
}

export interface EstadoAuth {
  necesitaAlta: boolean
  usuario: Usuario | null
}

export interface RespuestaAcceso {
  usuario: Usuario
  codigoRecuperacion?: string | null
}

export interface RespuestaClaveTemporal {
  usuario: Usuario
  claveTemporal: string
}

export interface EventoAuditoria {
  fecha: string
  accion: string
  actor: string | null
  objetivo: string | null
  objetivo_nombre: string | null
}

// ── KeyWords Explorer ─────────────────────────────────────────────────────

export type Intencion = 'informacional' | 'comercial' | 'transaccional' | 'navegacional'
export type NivelCompetencia = 'baja' | 'media' | 'alta'

/** Una keyword con sus métricas de Keyword Planner. Todo puede faltar: no se inventa. */
export interface FilaKeyword {
  keyword: string
  volumen: number | null
  tendencia: number[]
  competencia: NivelCompetencia | null
  competencia_idx: number | null
  cpc: number | null
  cpc_bajo: number | null
  cpc_alto: number | null
  palabras: number
  intencion: Intencion[]
  pregunta: boolean
  tipo: 'coincidente' | 'relacionado'
  sugerencia: boolean
  concepto: string | null
  nota?: string
}

export interface TerminoKeyword {
  termino: string
  keywords: number
  volumen: number
}

export interface ResultadoKeywords {
  filas: FilaKeyword[]
  terminos: TerminoKeyword[]
  totales: { keywords: number; volumen: number; coincidentes: number; relacionadas: number; preguntas: number; sugerencias: number; sin_volumen: number }
  demo: boolean
  semillas: string[]
  url: string | null
  pais: string
  idioma: string
  moneda: string | null
  volumen_agrupado: boolean
}

export interface BusquedaKeywords {
  codigo: string
  semillas: string[]
  url: string | null
  pais: string
  idioma: string
  demo: boolean
  totalKeywords: number
  volumenTotal: number
  fecha: string
}

export interface RespuestaBusqueda {
  busqueda: BusquedaKeywords
  desdeCache: boolean
  resultado: ResultadoKeywords
}

export interface ResumenKeyword extends FilaKeyword {
  variaciones: string[]
  meses: string[]
  tendencia_pct: number | null
  mes_pico?: string
  demo: boolean
  pais: string
  idioma: string
  moneda: string | null
  encontrada: boolean
  por_pais?: { pais: string; nombre: string; volumen: number | null }[]
}

export interface EstadoKeywords {
  google_ads: { completo: boolean; faltan: string[]; version: string; cuenta: string | null; con_manager: boolean }
  paises: Record<string, string>
  idiomas: Record<string, string>
}

export interface ListaKeywords {
  codigo: string
  nombre: string
  descripcion: string
  pais: string
  idioma: string
  demo: boolean
  keywords: number
  volumenTotal: number
  modificado: string
}

export interface PeticionExplorar {
  semillas: string[]
  url?: string | null
  pais: string
  idioma: string
  maximo?: number
  sugerencias?: boolean
  demo?: boolean
  refrescar?: boolean
}

// ── Plan SEO ──────────────────────────────────────────────────────────────

export type EstadoPaginaSeo = 'PENDIENTE' | 'OK' | 'EXCLUIDA' | 'NO_HTML' | 'HTTP_ERROR' | 'BLOQUEADA' | 'ERROR' | 'RETIRADA' | 'ANTIGUA'

/** Fecha mínima de publicación del Plan SEO (AAAA-MM-DD o null) y cuántas páginas quedan fuera. */
export interface FechaMinimaSeo {
  fecha: string | null
  antiguas: number
  /** Solo al guardar. */
  marcadas?: number
  devueltas?: number
}
export type EstadoTareaSeo = 'EN_COLA' | 'CORRIENDO' | 'TERMINADA' | 'PAUSADA' | 'CANCELADA'
export type IntencionSeo = 'INFORMATIONAL' | 'COMMERCIAL' | 'TRANSACTIONAL' | 'NAVIGATIONAL' | 'NEEDS_REVIEW'
export type Cobertura = 'YA_CUBIERTA' | 'PARCIAL' | 'SIN_COBERTURA' | 'INCIERTO'

export interface SitemapSeo {
  url: string
  tipo: 'indice' | 'urls' | null
  urls: number
  excluido: string | null
  estado: string
}

export interface SitioSeo {
  codigo: string
  nombre: string
  rol: 'PROPIO' | 'COMPETIDOR'
  hosts: string[]
  maxPaginas: number
  activo: boolean
  descubrimiento: { sitemaps?: SitemapSeo[]; avisos?: string[] } | null
  descubierto: string | null
  paginas: Partial<Record<EstadoPaginaSeo, number>>
  conTemas: number
  sinTemas: number
  /** De las que faltan, las que hablan del sector y van a la IA; las demás se marcan gratis. */
  sinTemasDelSector: number
}

export interface TareaSeo {
  codigo: string
  tipo: 'INVENTARIO' | 'TEMAS' | 'KEYWORDS' | 'ARTICULO' | 'AUTOMATICO'
  sitio: string | null
  estado: EstadoTareaSeo
  hechos: number
  total: number
  mensaje: string | null
  error: string | null
  /** Contadores al terminar; en ARTICULO, `articulo` es su código; en AUTOMATICO, listas de artículos y avisos. */
  resumen: Record<string, unknown> | null
  costoUsd: number
  llamadasIa: number
  activa: boolean
  creado: string
  modificado: string
}

export interface TemasPagina {
  tipo_pagina: string
  tema: string
  consultas: string[]
  relevancia: number
  confianza: string
  evidencia: string[]
  /** Descartada sin IA: no habla del sector (cocina, pastelería, panadería, bar…). */
  fuera_del_sector?: boolean
}

export interface PaginaSeo {
  url: string
  sitio: string
  sitemap: string | null
  lastmod: string | null
  estado: EstadoPaginaSeo
  motivo: string | null
  http: number | null
  datos: {
    title: string | null
    meta_description: string | null
    h1: string | null
    h1_total: number
    h2: string[]
    h3_total: number
    canonical: string | null
    lang: string | null
    palabras: number
    extracto: string
  } | null
  temas: TemasPagina | null
  extraida: string | null
}

export interface KeywordSeo {
  keyword: string
  origenes: { sitio: string; url: string }[]
  intencion: IntencionSeo | null
  grupo: string | null
  canonica: string | null
  relevancia: number | null
  motivo: string | null
  cobertura: Cobertura | null
  urlPropia: string | null
  motivoCobertura: string | null
  evidencia: string
}

/** El rubro del negocio propio: lo que se le describe a la IA y las palabras del filtro gratuito. */
export interface RubroSeo {
  descripcion: string
  palabras: string[]
  porDefecto: boolean
  negocio: string
  /** Páginas que ya tienen temas y, de ellas, las marcadas «fuera del sector». */
  conTemas: number
  fueraDelSector: number
  /** Solo al guardar: cuántas páginas volverán a «Extraer temas». */
  reevaluar?: number
}

export interface ArticuloSeo {
  codigo: string
  grupo: string
  keyword: string
  variantes: string[]
  origenes: { sitio: string; url: string }[]
  indicaciones: string | null
  titulo: string | null
  slug: string | null
  metaDescription: string | null
  /** Markdown. */
  contenido: string | null
  pendientes: string[]
  tarea: string | null
  tareaEstado: EstadoTareaSeo | null
  tareaError: string | null
  wpId: number | null
  wpEstado: string | null
  wpEnlace: string | null
  wpEditar: string | null
  enviado: string | null
  redactado: string | null
  autor: string | null
  creado: string
  modificado: string
  cambiosSinEnviar: boolean
  imagen: ImagenSeo | null
}

/** Imagen destacada de un artículo (los bytes van por /api/seo/articulos/{codigo}/imagen). */
export interface ImagenSeo {
  fuente: 'PIXABAY' | 'PEXELS' | 'GEMINI'
  mime: string
  bytes: number
  alt: string | null
  leyenda: string | null
  autor: string | null
  autorUrl: string | null
  origenUrl: string | null
  /** Gemini: lo que se pidió. */
  prompt: string | null
  modelo: string | null
  wpMediaId: number | null
  modificada: string
}

export interface FuentesImagen {
  /** Banco de fotos en uso (según la clave del worker); null = sin clave. */
  fotos: 'PIXABAY' | 'PEXELS' | null
  gemini: boolean
  modelo: string
  precio_usd: number
}

export interface FotoBanco {
  id: number
  ancho: number
  alto: number
  autor: string
  autor_url: string
  pagina_url: string
  alt: string
  miniatura: string
  previa: string
}

export interface BusquedaFotos {
  fotos: FotoBanco[]
  total: number
  pagina: number
  hay_mas: boolean
  fuente: 'PIXABAY' | 'PEXELS'
}

export interface WordpressEstado {
  completo: boolean
  faltan: string[]
  sitio: string | null
  usuario: string | null
}

export interface WordpressPrueba {
  ok: boolean
  sitio: string
  usuario: string
  puede_crear: boolean
  puede_publicar: boolean
  puede_subir: boolean
}

/** Flujo automático del Plan SEO (inventario → temas → keywords → artículos → borrador en WordPress). */
export interface AutomaticoSeo {
  activo: boolean
  /** 1 = lunes … 7 = domingo. */
  dia: number
  /** HH:MM, hora de Lima. */
  hora: string
  articulos: number
  ultima: string | null
  proxima: string | null
  tarea: TareaSeo | null
  /** Lo que redactaría con las keywords de hoy, en orden (la ejecución las regenera antes de elegir). */
  candidatos: CandidatoArticulo[]
  /** Las que Google no sugiere: no se redactan. */
  descartados: CandidatoArticulo[]
  /** false si no se pudo consultar a Google: el orden es solo por competidores. */
  google: boolean
}

export interface CandidatoArticulo {
  grupo: string
  keyword: string
  /** Búsquedas del grupo (variantes de la misma pregunta). */
  busquedas: number
  /** Páginas de competidores que la tratan: decide el orden. */
  paginas: number
  sitios: string[]
  relevancia: number
  /** Autocompletado de Google: la sugiere tal cual, sugiere búsquedas que la contienen, nada; null = sin consultar. */
  google: 'EXACTA' | 'VARIANTES' | 'NINGUNA' | null
  /** Otras búsquedas que la gente escribe sobre lo mismo. */
  sugerencias: string[]
  /** Search Console de la web propia para estas búsquedas; null si no aparece o no está conectado. */
  gsc: DatoGsc | null
  /** Solo en los descartados. */
  motivo: 'YA_POSICIONA' | 'MEJORAR_PAGINA' | 'GOOGLE_NO_SUGIERE' | null
}

export interface DatoGsc {
  impresiones: number
  clics: number
  /** Posición media en Google, ponderada por impresiones. */
  posicion: number
  url: string
}

export interface FilaGsc {
  consulta: string
  url: string
  clics: number
  impresiones: number
  ctr: number
  posicion: number
}

export interface SearchConsoleSeo {
  configuracion: { completo: boolean; faltan: string[]; propiedad: string | null; pais: string | null; error?: string }
  /** `informe`: el corte guardado que está cargado ahora. */
  sincronizacion: { propiedad: string; desde: string; hasta: string; pais: string | null; filas: number; fecha: string; informe?: string } | null
  resumen: { consultas: number; clics: number; impresiones: number }
  /** Páginas propias con búsquedas sin marca en la posición 4-20, de más a menos impresiones. */
  oportunidades: OportunidadPagina[]
  /** Palabras de marca o navegación: las búsquedas que las contienen no cuentan. */
  marca: string[]
  /** Nombres que ninguna propuesta cambia ni redefine. */
  terminos: TerminoProtegido[]
}

export type ModuloInforme = 'SEARCH_CONSOLE' | 'PLAN_SEO_KEYWORDS' | 'MEDICION'

/** Un informe guardado tal como estaba el día que se hizo (auditoría). */
export interface InformeGuardado {
  codigo: string
  modulo: ModuloInforme
  titulo: string
  resumen: Record<string, unknown>
  filas: number
  origen: string | null
  autor: string | null
  creado: string
}

export type TipoTermino = 'CARRERA' | 'SISTEMA' | 'OTRO'

export interface TerminoProtegido {
  nombre: string
  tipo: TipoTermino
  /** La oficial: la IA solo describe el término con ella. */
  descripcion: string
}

/** Un cambio en el contenido de la página. `diceAhora` es null si es algo nuevo. */
export interface IdeaMejora {
  donde: string
  diceAhora: string | null
  debeDecir: string
}

export interface OportunidadPagina {
  url: string
  impresiones: number
  clics: number
  /** Clics / impresiones, de 0 a 1. */
  ctr: number
  /** Posición media, ponderada por impresiones. */
  posicion: number
  consultas: FilaGsc[]
  mejora: MejoraSeo | null
}

export interface MejoraSeo {
  url: string
  consultas: { consulta: string; impresiones: number; clics: number; posicion: number }[]
  tituloActual: string | null
  metaActual: string | null
  titulo: string
  metaDescription: string
  ideas: IdeaMejora[]
  motivo: string | null
  estado: 'PROPUESTA' | 'APLICADA' | 'DESCARTADA'
  creado: string
  modificado: string
}

export interface ComprobacionGsc {
  ok: boolean
  propiedad: string
  permiso: string | null
  propiedades: { propiedad: string; permiso: string }[]
}

// ── Videos (guion por partes y Google Vids) ───────────────────────────────

export type EstadoVideo = 'IDEA' | 'GUION' | 'GENERANDO' | 'GENERADO' | 'APROBADO' | 'ERROR'
export type FormatoVideo = 'VERTICAL' | 'HORIZONTAL'

/** Una parte del guion = un clip de 10 s en Vids. */
export interface ParteVideo {
  dialogo: string
  escena: string
}

export interface Video {
  codigo: string
  titulo: string
  idea: string
  keyword: string | null
  segundos: number
  formato: FormatoVideo
  partes: ParteVideo[]
  copyFacebook: string | null
  copyInstagram: string | null
  hashtags: string[]
  estado: EstadoVideo
  avance: string | null
  error: string | null
  tieneArchivo: boolean
  segundosReales: number | null
  vidsUrl: string | null
  creado: string
  modificado: string
}

export interface Pronunciacion {
  texto: string
  dice: string
}

/** Lo que se repite en todos los videos: datos que se pueden afirmar, protagonista, lugar, voz. */
export interface ContextoVideo {
  datos: string
  personaje: string
  estilo: string
  voz: string
  pronunciaciones: Pronunciacion[]
}

export interface NavegadorVids {
  abierto: boolean
  vids: boolean
  sesion: boolean | null
  version?: string
}

// ── Publicaciones ─────────────────────────────────────────────────────────

export type RedSocial = 'FACEBOOK' | 'INSTAGRAM' | 'LINKEDIN'
export type EstadoPublicacion = 'BORRADOR' | 'APROBADA' | 'PUBLICADA'
export type MediaPublicacion = 'NINGUNA' | 'IMAGEN' | 'VIDEO'
/** Un texto para cada red o el mismo para todas. */
export type ModoCopy = 'POR_RED' | 'MISMO'

/** Textos del flyer, de dónde salió el fondo y si la imagen de la publicación es este flyer. */
export interface FlyerPublicacion {
  titulo: string
  detalle: string
  cta: string
  /** Qué buscar en el banco de fotos. */
  busqueda: string
  /** Qué pedirle a la IA si el fondo se crea a medida. */
  descripcion: string
  fondoOrigen: 'PIXABAY' | 'PEXELS' | 'IA' | 'PROPIA' | null
  fondoCredito: string | null
  fondoUrl: string | null
  tieneFondo: boolean
  enUso: boolean
}

/** Lo común a todos los flyers y posts. */
export interface MarcaPublicacion {
  color: string
  acento: string
  /** La web propia: sus enlaces llevan UTM en Facebook y LinkedIn. */
  dominios?: string[]
  /** Hashtags del rubro: van en todas las publicaciones, delante de los del tema. */
  hashtags: string[]
  tieneLogo: boolean
}

export type EstadoEnlace = 'ACTIVA' | 'NO_DISPONIBLE' | 'SIN_CONFIRMAR'

/** Última comprobación de un enlace publicado. */
export interface VerificacionEnlace {
  estado: EstadoEnlace
  detalle: string
  http: number | null
  fecha: string
}

/** Lo que le pasó a una publicación (biblioteca). */
export interface EventoPublicacion {
  evento: string
  detalle: string
  datos: Record<string, unknown> | null
  autor: string | null
  fecha: string
}

export interface Publicacion {
  codigo: string
  titulo: string
  idea: string
  origen: 'MANUAL' | 'VIDEO'
  codOrigen: string | null
  redes: RedSocial[]
  textos: Partial<Record<RedSocial, string>>
  hashtags: string[]
  media: MediaPublicacion
  archivoTipo: string | null
  /** Enlace de lo ya publicado en cada red. */
  enlaces: Partial<Record<RedSocial, string>>
  modoCopy: ModoCopy
  flyer: FlyerPublicacion
  /** No se borra: se archiva y sigue en la biblioteca. */
  archivada: boolean
  verificacion: Partial<Record<RedSocial, VerificacionEnlace>>
  estado: EstadoPublicacion
  aprobador: string | null
  autor: string | null
  creado: string
  modificado: string
}

// ── Medición (anuncios de Meta, GA4 y resumen con IA) ─────────────────────

export interface ConfiguracionMedicion {
  completo: boolean
  faltan: string[]
  error?: string
}

export interface CuentaMeta {
  id: string
  nombre: string | null
  moneda: string | null
  activa: boolean
  zona: string | null
}

export interface SincronizacionMeta {
  estado: 'EN_CURSO' | 'LISTA' | 'ERROR'
  desde: string
  hasta: string
  inicio: string
  fin?: string
  filas?: number
  error?: string
}

export interface EstadoMedicion {
  meta: ConfiguracionMedicion & { cuenta?: string | null; detalle?: CuentaMeta | null }
  ga4: ConfiguracionMedicion & { propiedad?: string | null }
  sincronizacion: SincronizacionMeta | null
  datos: { desde: string; hasta: string; filas: number } | null
  hoy: string
}

/** Conexión con Google (Search Console, GA4 y Google Ads comparten un permiso). */
export interface ConexionGoogle {
  estado: 'INACTIVA' | 'ESPERANDO' | 'LISTA' | 'ERROR'
  mensaje: string | null
  configurada: boolean
  /** Fecha (AAAA-MM-DD) del último permiso y cuándo lo corta Google en modo Prueba. */
  autorizado: string | null
  vence: string | null
  /** null si no se comprobó contra Google. */
  valida: boolean | null
  /** La app de Google Cloud sigue en modo Prueba (el permiso dura 7 días). */
  prueba?: boolean
  error?: string
}

export type TipoCampana = 'LEADS' | 'CONVERSACIONES' | 'SIN_RESULTADOS'

export interface KpisMeta {
  gasto: number
  impresiones: number
  clicsEnlace: number
  ctr: number | null
  cpc: number | null
  visitas: number
  leads: number
  costoLead: number | null
  gastoLeads: number
  conversaciones: number
  costoConversacion: number | null
  gastoConversaciones: number
  gastoSinResultados: number
  campanas: number
  anuncios: number
}

export interface CampanaMeta {
  id: string
  nombre: string
  objetivo: string | null
  tipo: TipoCampana
  linea: string | null
  canal: string | null
  producto: string | null
  gasto: number
  impresiones: number
  clicsEnlace: number
  ctr: number | null
  leads: number
  conversaciones: number
  resultados: number
  costoResultado: number | null
  gastoAnterior: number | null
  costoAnterior: number | null
  cambioCosto: number | null
  anuncios: number
}

export interface AnuncioMeta {
  id: string
  nombre: string
  campana: string
  conjunto: string | null
  tipo: TipoCampana
  gasto: number
  impresiones: number
  ctr: number | null
  resultados: number
  costoResultado: number | null
}

export interface AlertaMedicion {
  tipo: 'COSTO_SUBE' | 'CTR_BAJA' | 'SIN_RESULTADOS' | 'RINDE_MEJOR' | 'GASTO' | 'DATOS_VIEJOS'
  nivel: 'ALTA' | 'MEDIA' | 'OPORTUNIDAD' | 'INFO'
  titulo: string
  detalle: string
  id: string | null
  /** Gasto de los 7 días de lo que señala: ordena las alertas por el dinero en juego. */
  gasto: number
}

export interface DiaMeta {
  fecha: string
  gasto: number
  leads: number
  conversaciones: number
  clicsEnlace: number
  impresiones: number
}

export interface ResumenMedicion {
  periodo: { desde: string; hasta: string; dias: number }
  anterior: { desde: string; hasta: string }
  moneda: string
  kpis: KpisMeta
  kpisAnterior: KpisMeta
  serie: DiaMeta[]
  campanas: CampanaMeta[]
  anuncios: AnuncioMeta[]
  alertas: AlertaMedicion[]
  datos: { desde: string; hasta: string } | null
}

export interface ResumenIa {
  titular: string
  puntos: string[]
  hallazgos: { titulo: string; evidencia: string; sugerencia: string }[]
  advertencias: string[]
}

export interface InformeGa4 {
  propiedad: string
  desde: string
  hasta: string
  canales: { sessionDefaultChannelGroup: string; sessions: number; engagedSessions: number; keyEvents: number; totalUsers: number }[]
  campanas: { sessionSource: string; sessionMedium: string; sessionCampaignName: string; sessions: number; engagedSessions: number; keyEvents: number }[]
  paginas: { landingPage: string; sessions: number; engagedSessions: number; keyEvents: number }[]
  dias: { date: string; sessions: number; keyEvents: number }[]
  eventos: { eventName: string; keyEvents: number }[]
}
