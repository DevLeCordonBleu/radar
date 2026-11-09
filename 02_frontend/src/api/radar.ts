/** Llamadas al backend, una funcion por endpoint. Las vistas no usan `fetch`. */
import { api } from './cliente'
import type {
  ConexionGoogle,
  ContextoVideo,
  FlyerPublicacion,
  MarcaPublicacion,
  ModoCopy,
  Publicacion,
  RedSocial,
  NavegadorVids,
  ParteVideo,
  Video,
  ArticuloSeo,
  AutomaticoSeo,
  ComprobacionGsc,
  MejoraSeo,
  SearchConsoleSeo,
  BusquedaFotos,
  FuentesImagen,
  RubroSeo,
  TerminoProtegido,
  EstadoMedicion,
  InformeGa4,
  ResumenIa,
  ResumenMedicion,
  SincronizacionMeta,
  EstadoEnlace,
  EventoPublicacion,
  FechaMinimaSeo,
  InformeGuardado,
  ModuloInforme,
  WordpressEstado,
  WordpressPrueba,
  SugerenciaPagina,
  KeywordSeo,
  PaginaSeo,
  SitioSeo,
  TareaSeo,
  Analisis,
  AnalisisSemanal,
  BusquedaKeywords,
  Comprobacion,
  EstadoKeywords,
  FilaKeyword,
  ListaKeywords,
  PeticionExplorar,
  RespuestaBusqueda,
  ResumenKeyword,
  EstadoAuth,
  EventoAuditoria,
  Estimacion,
  InformeCompleto,
  InformeFila,
  Peticion,
  RespuestaAcceso,
  RespuestaClaveTemporal,
  Rol,
  Sistema,
  Taxonomia,
  Usuario,
} from './tipos'

export const analisis = {
  listar: () => api.obtener<Analisis[]>('/api/analisis'),
  obtener: (codigo: string) => api.obtener<Analisis>(`/api/analisis/${codigo}`),
  estimar: (p: Peticion) => api.enviar<Estimacion>('/api/analisis/estimar', p),
  /** Páginas de Facebook que coinciden con lo escrito (autocompletado de la Biblioteca de Meta). */
  paginas: (texto: string, pais: string) => api.enviar<{ paginas: SugerenciaPagina[] }>('/api/analisis/paginas', { texto, pais }),
  /** Abre por adelantado el Chrome de las sugerencias para que la primera no tarde. */
  prepararPaginas: (pais: string) => api.enviar<void>('/api/analisis/paginas/preparar', { pais }),
  crear: (p: Peticion) => api.enviar<Analisis>('/api/analisis', p),
  continuar: (codigo: string) => api.enviar<Analisis>(`/api/analisis/${codigo}/continuar`),
  terminar: (codigo: string) => api.enviar<Analisis>(`/api/analisis/${codigo}/terminar`),
  cancelar: (codigo: string) => api.enviar<Analisis>(`/api/analisis/${codigo}/cancelar`),
  /** Una o varias páginas del mismo competidor; [] = ninguna (queda fuera). */
  elegirPagina: (codigo: string, competidor: string, pageIds: string[]) =>
    api.enviar<Analisis>(`/api/analisis/${codigo}/pagina`, { competidor, pageIds }),
  borrar: (codigo: string) => api.borrar<void>(`/api/analisis/${codigo}`),
  semanal: () => api.obtener<AnalisisSemanal>('/api/analisis/semanal'),
  /** Sin `peticion` conserva la programada (solo cambia día, hora o si está activo). */
  programarSemanal: (s: { activo?: boolean; dia?: number; hora?: string; peticion?: Peticion }) =>
    api.poner<AnalisisSemanal>('/api/analisis/semanal', s),
  ejecutarSemanal: () => api.enviar<Analisis>('/api/analisis/semanal/ejecutar'),
}

export const informes = {
  listar: (archivados = false) =>
    api.obtener<InformeFila[]>(`/api/informes${archivados ? '?archivados=true' : ''}`),
  obtener: (codigo: string) => api.obtener<InformeCompleto>(`/api/informes/${codigo}`),
  crearEjemplo: () => api.enviar<InformeFila>('/api/informes/ejemplo'),
  archivar: (codigo: string, archivado: boolean) =>
    api.poner<void>(`/api/informes/${codigo}/archivo`, { archivado }),
  borrar: (codigo: string) => api.borrar<void>(`/api/informes/${codigo}`),
}

export const sistema = {
  estado: () => api.obtener<Sistema>('/api/sistema'),
  comprobar: () => api.enviar<Comprobacion>('/api/sistema/comprobar'),
  taxonomia: () => api.obtener<Taxonomia>('/api/taxonomia'),
  mercado: () => api.obtener<Peticion>('/api/mercado'),
  guardarMercado: (p: Peticion) => api.poner<Peticion>('/api/mercado', p),
}

export const auth = {
  estado: () => api.obtener<EstadoAuth>('/api/auth/estado'),
  alta: (nombre: string, email: string, clave: string) => api.enviar<RespuestaAcceso>('/api/auth/alta', { nombre, email, clave }),
  entrar: (email: string, clave: string) => api.enviar<RespuestaAcceso>('/api/auth/entrar', { email, clave }),
  recuperar: (email: string, codigo: string, claveNueva: string) =>
    api.enviar<RespuestaAcceso>('/api/auth/recuperar', { email, codigo, claveNueva }),
  salir: () => api.enviar<void>('/api/auth/salir'),
  cuenta: (c: { nombre?: string; claveActual?: string; claveNueva?: string; nuevoCodigo?: boolean }) =>
    api.poner<RespuestaAcceso>('/api/auth/cuenta', c),
}

export const usuarios = {
  listar: () => api.obtener<Usuario[]>('/api/usuarios'),
  crear: (nombre: string, email: string, rol: Rol) => api.enviar<RespuestaClaveTemporal>('/api/usuarios', { nombre, email, rol }),
  cambiar: (codigo: string, c: { rol?: Rol; activo?: boolean; nombre?: string }) => api.poner<Usuario>(`/api/usuarios/${codigo}`, c),
  reiniciarClave: (codigo: string) => api.enviar<RespuestaClaveTemporal>(`/api/usuarios/${codigo}/reiniciar-clave`),
  borrar: (codigo: string) => api.borrar<void>(`/api/usuarios/${codigo}`),
  auditoria: () => api.obtener<EventoAuditoria[]>('/api/usuarios/auditoria'),
}

export const keywords = {
  estado: () => api.obtener<EstadoKeywords>('/api/keywords/estado'),
  comprobar: () => api.enviar<{ ok: boolean; detalle: string }>('/api/keywords/comprobar'),
  explorar: (p: PeticionExplorar) => api.enviar<RespuestaBusqueda>('/api/keywords/explorar', p),
  busquedas: () => api.obtener<BusquedaKeywords[]>('/api/keywords/busquedas'),
  busqueda: (codigo: string) => api.obtener<RespuestaBusqueda>(`/api/keywords/busquedas/${codigo}`),
  borrarBusqueda: (codigo: string) => api.borrar<void>(`/api/keywords/busquedas/${codigo}`),
  resumen: (keyword: string, pais: string, idioma: string, porPais = false, demo = false) =>
    api.enviar<ResumenKeyword>('/api/keywords/resumen', { keyword, pais, idioma, porPais, demo }),
  listas: () => api.obtener<ListaKeywords[]>('/api/keywords/listas'),
  crearLista: (nombre: string, pais: string, idioma: string, demo: boolean, descripcion = '') =>
    api.enviar<ListaKeywords>('/api/keywords/listas', { nombre, pais, idioma, demo, descripcion }),
  lista: (codigo: string) => api.obtener<{ lista: ListaKeywords; items: FilaKeyword[] }>(`/api/keywords/listas/${codigo}`),
  renombrarLista: (codigo: string, nombre: string, descripcion: string) =>
    api.poner<ListaKeywords>(`/api/keywords/listas/${codigo}`, { nombre, descripcion }),
  borrarLista: (codigo: string) => api.borrar<void>(`/api/keywords/listas/${codigo}`),
  agregar: (codigo: string, items: FilaKeyword[], demo: boolean) =>
    api.enviar<{ agregadas: number; repetidas: number }>(`/api/keywords/listas/${codigo}/items`, { items, demo }),
  quitar: (codigo: string, claves: string[]) => api.enviar<void>(`/api/keywords/listas/${codigo}/quitar`, { keywords: claves }),
  nota: (codigo: string, keyword: string, nota: string) => api.poner<void>(`/api/keywords/listas/${codigo}/nota`, { keyword, nota }),
  actualizarLista: (codigo: string) => api.enviar<{ actualizadas: number }>(`/api/keywords/listas/${codigo}/actualizar`),
}

export const seo = {
  sitios: () => api.obtener<SitioSeo[]>('/api/seo/sitios'),
  crearSitio: (nombre: string, hosts: string[]) => api.enviar<SitioSeo>('/api/seo/sitios', { nombre, hosts }),
  ajustarSitio: (codigo: string, cambios: { nombre?: string; hosts?: string[]; maxPaginas?: number; activo?: boolean }) =>
    api.poner<SitioSeo>(`/api/seo/sitios/${codigo}`, cambios),
  borrarSitio: (codigo: string) => api.borrar<void>(`/api/seo/sitios/${codigo}`),
  inventariar: (codigo: string) => api.enviar<TareaSeo>(`/api/seo/sitios/${codigo}/inventario`),
  extraerTemas: (codigo: string) => api.enviar<TareaSeo>(`/api/seo/sitios/${codigo}/temas`),
  generarKeywords: () => api.enviar<TareaSeo>('/api/seo/keywords/generar'),
  paginas: (sitio?: string) => api.obtener<PaginaSeo[]>(`/api/seo/paginas${sitio ? `?sitio=${encodeURIComponent(sitio)}` : ''}`),
  keywords: () => api.obtener<KeywordSeo[]>('/api/seo/keywords'),
  tareas: () => api.obtener<TareaSeo[]>('/api/seo/tareas'),
  continuar: (codigo: string) => api.enviar<TareaSeo>(`/api/seo/tareas/${codigo}/continuar`),
  cancelar: (codigo: string) => api.enviar<TareaSeo>(`/api/seo/tareas/${codigo}/cancelar`),
  rubro: () => api.obtener<RubroSeo>('/api/seo/rubro'),
  fechaMinima: () => api.obtener<FechaMinimaSeo>('/api/seo/fecha-minima'),
  guardarFechaMinima: (fecha: string | null) => api.poner<FechaMinimaSeo>('/api/seo/fecha-minima', { fecha }),
  guardarRubro: (descripcion: string, palabras: string[]) => api.poner<RubroSeo>('/api/seo/rubro', { descripcion, palabras }),
  sugerirRubro: () => api.enviar<{ descripcion: string; palabras: string[] }>('/api/seo/rubro/sugerir'),
  articulos: () => api.obtener<ArticuloSeo[]>('/api/seo/articulos'),
  articulo: (codigo: string) => api.obtener<ArticuloSeo>(`/api/seo/articulos/${codigo}`),
  crearArticulo: (grupo: string, indicaciones: string) => api.enviar<ArticuloSeo>('/api/seo/articulos', { grupo, indicaciones }),
  editarArticulo: (codigo: string, a: { titulo: string; slug: string; metaDescription: string; contenido: string }) =>
    api.poner<ArticuloSeo>(`/api/seo/articulos/${codigo}`, a),
  borrarArticulo: (codigo: string) => api.borrar<void>(`/api/seo/articulos/${codigo}`),
  redactar: (codigo: string, indicaciones: string) => api.enviar<ArticuloSeo>(`/api/seo/articulos/${codigo}/redactar`, { indicaciones }),
  enviarWordpress: (codigo: string, publicar: boolean) => api.enviar<ArticuloSeo>(`/api/seo/articulos/${codigo}/wordpress`, { publicar }),
  desvincular: (codigo: string) => api.enviar<ArticuloSeo>(`/api/seo/articulos/${codigo}/desvincular`),
  vistaPrevia: (contenido: string) => api.enviar<{ html: string; pendientes: string[] }>('/api/seo/vista-previa', { contenido }),
  wordpress: () => api.obtener<WordpressEstado>('/api/seo/wordpress'),
  probarWordpress: () => api.enviar<WordpressPrueba>('/api/seo/wordpress/probar'),
  automatico: () => api.obtener<AutomaticoSeo>('/api/seo/automatico'),
  guardarAutomatico: (a: Pick<AutomaticoSeo, 'activo' | 'dia' | 'hora' | 'articulos'>) => api.poner<AutomaticoSeo>('/api/seo/automatico', a),
  ejecutarAutomatico: () => api.enviar<TareaSeo>('/api/seo/automatico/ejecutar'),
  searchConsole: () => api.obtener<SearchConsoleSeo>('/api/seo/search-console'),
  comprobarSearchConsole: () => api.enviar<ComprobacionGsc>('/api/seo/search-console/comprobar'),
  sincronizarSearchConsole: () => api.enviar<SearchConsoleSeo>('/api/seo/search-console/sincronizar'),
  guardarMarca: (palabras: string[]) => api.poner<SearchConsoleSeo>('/api/seo/search-console/marca', { palabras }),
  informes: (modulo: ModuloInforme) => api.obtener<InformeGuardado[]>(`/api/seo/informes?modulo=${modulo}`),
  informe: (codigo: string) =>
    api.obtener<{ informe: InformeGuardado; filas: Record<string, unknown>[] }>(`/api/seo/informes/${encodeURIComponent(codigo)}`),
  csvInforme: (codigo: string) => `/api/seo/informes/${encodeURIComponent(codigo)}/csv`,
  restaurarInforme: (codigo: string) => api.enviar<SearchConsoleSeo>(`/api/seo/informes/${encodeURIComponent(codigo)}/restaurar`),
  guardarTerminos: (terminos: TerminoProtegido[]) => api.poner<SearchConsoleSeo>('/api/seo/search-console/terminos', { terminos }),
  proponerMejora: (url: string) => api.enviar<MejoraSeo>('/api/seo/mejoras', { url }),
  estadoMejora: (url: string, estado: MejoraSeo['estado']) => api.poner<MejoraSeo>('/api/seo/mejoras/estado', { url, estado }),
  fuentesImagen: () => api.obtener<FuentesImagen>('/api/seo/imagenes'),
  buscarFotos: (consulta: string, pagina = 1) => api.enviar<BusquedaFotos>('/api/seo/imagenes/buscar', { consulta, pagina }),
  /** Para <img>: la versión evita que el navegador muestre la imagen anterior. */
  urlImagen: (codigo: string, version: string) => `/api/seo/articulos/${codigo}/imagen?v=${encodeURIComponent(version)}`,
  imagenDelBanco: (codigo: string, id: number, alt: string) =>
    api.enviar<ArticuloSeo>(`/api/seo/articulos/${codigo}/imagen/foto`, { id, alt }),
  generarImagen: (codigo: string, descripcion: string, alt: string) =>
    api.enviar<ArticuloSeo>(`/api/seo/articulos/${codigo}/imagen/generar`, { descripcion, alt }),
  textosImagen: (codigo: string, alt: string, leyenda: string) =>
    api.poner<ArticuloSeo>(`/api/seo/articulos/${codigo}/imagen`, { alt, leyenda }),
  quitarImagen: (codigo: string) => api.borrar<ArticuloSeo>(`/api/seo/articulos/${codigo}/imagen`),
}

export const videos = {
  listar: () => api.obtener<Video[]>('/api/videos'),
  obtener: (codigo: string) => api.obtener<Video>(`/api/videos/${codigo}`),
  crear: (v: { idea: string; keyword?: string; segundos: number; formato: string }) => api.enviar<Video>('/api/videos', v),
  /** Lo que no viene no cambia. */
  guardar: (
    codigo: string,
    c: Partial<Pick<Video, 'titulo' | 'idea' | 'keyword' | 'segundos' | 'formato' | 'copyFacebook' | 'copyInstagram' | 'hashtags'>> & { partes?: ParteVideo[] },
  ) => api.poner<Video>(`/api/videos/${codigo}`, c),
  borrar: (codigo: string) => api.borrar<void>(`/api/videos/${codigo}`),
  redactar: (codigo: string) => api.enviar<Video>(`/api/videos/${codigo}/guion`),
  prompts: (codigo: string) => api.obtener<{ prompts: string[] }>(`/api/videos/${codigo}/prompts`),
  generar: (codigo: string) => api.enviar<Video>(`/api/videos/${codigo}/generar`),
  cancelar: (codigo: string) => api.enviar<Video>(`/api/videos/${codigo}/cancelar`),
  aprobar: (codigo: string, aprobado: boolean) => api.poner<Video>(`/api/videos/${codigo}/aprobacion`, { aprobado }),
  archivo: (codigo: string, descargar = false) => `/api/videos/${codigo}/archivo${descargar ? '?descargar=true' : ''}`,
  contexto: () => api.obtener<ContextoVideo>('/api/videos/contexto'),
  guardarContexto: (c: ContextoVideo) => api.poner<ContextoVideo>('/api/videos/contexto', c),
  navegador: () => api.obtener<NavegadorVids>('/api/videos/navegador'),
  abrirNavegador: () => api.enviar<NavegadorVids>('/api/videos/navegador/abrir'),
}

export const publicaciones = {
  /** Con `archivadas`, toda la biblioteca. */
  listar: (archivadas = false) => api.obtener<Publicacion[]>(`/api/publicaciones${archivadas ? '?archivadas=true' : ''}`),
  obtener: (codigo: string) => api.obtener<Publicacion>(`/api/publicaciones/${codigo}`),
  crear: (idea: string, redes: RedSocial[], modoCopy: ModoCopy) => api.enviar<Publicacion>('/api/publicaciones', { idea, redes, modoCopy }),
  desdeVideo: (codVideo: string) => api.enviar<Publicacion>(`/api/publicaciones/desde-video/${codVideo}`),
  /** Lo que no viene no cambia. */
  guardar: (
    codigo: string,
    c: Partial<Pick<Publicacion, 'titulo' | 'idea' | 'redes' | 'textos' | 'hashtags' | 'modoCopy'>> & {
      flyer?: Pick<FlyerPublicacion, 'titulo' | 'detalle' | 'cta' | 'busqueda' | 'descripcion'>
    },
  ) => api.poner<Publicacion>(`/api/publicaciones/${codigo}`, c),
  /** No borra: archiva. */
  archivar: (codigo: string) => api.borrar<Publicacion>(`/api/publicaciones/${codigo}`),
  restaurar: (codigo: string) => api.enviar<Publicacion>(`/api/publicaciones/${codigo}/restaurar`),
  historial: (codigo: string) => api.obtener<EventoPublicacion[]>(`/api/publicaciones/${codigo}/historial`),
  verificar: (codigo: string) => api.enviar<Publicacion>(`/api/publicaciones/${codigo}/verificar`),
  verificarTodas: () =>
    api.enviar<{ publicaciones: number; enlaces: number } & Partial<Record<EstadoEnlace | 'ERROR', number>>>('/api/publicaciones/verificar'),
  redactar: (codigo: string) => api.enviar<Publicacion>(`/api/publicaciones/${codigo}/textos`),
  aprobar: (codigo: string, aprobada: boolean) => api.poner<Publicacion>(`/api/publicaciones/${codigo}/aprobacion`, { aprobada }),
  enlace: (codigo: string, red: RedSocial, url: string) => api.poner<Publicacion>(`/api/publicaciones/${codigo}/enlaces`, { red, url }),
  subir: (codigo: string, archivo: File, alProgresar?: (f: number) => void) => {
    const f = new FormData()
    f.append('archivo', archivo)
    return api.subir<Publicacion>(`/api/publicaciones/${codigo}/archivo`, f, alProgresar)
  },
  quitarArchivo: (codigo: string) => api.borrar<Publicacion>(`/api/publicaciones/${codigo}/archivo`),
  /** Flyer: fotos verticales del banco gratuito, elegir fondo (lo arma al momento) y volver a armarlo. */
  fotos: (consulta: string, pagina = 1) =>
    api.obtener<BusquedaFotos>(`/api/publicaciones/fotos?${new URLSearchParams({ consulta, pagina: String(pagina) })}`),
  fondoFoto: (codigo: string, id: number) => api.enviar<Publicacion>(`/api/publicaciones/${codigo}/fondo/foto`, { id }),
  fondoIa: (codigo: string, descripcion: string) => api.enviar<Publicacion>(`/api/publicaciones/${codigo}/fondo/ia`, { descripcion }),
  fondoPropio: (codigo: string, archivo: File) => {
    const f = new FormData()
    f.append('archivo', archivo)
    return api.subir<Publicacion>(`/api/publicaciones/${codigo}/fondo`, f)
  },
  componer: (codigo: string) => api.enviar<Publicacion>(`/api/publicaciones/${codigo}/flyer`),
  marca: () => api.obtener<MarcaPublicacion>('/api/publicaciones/marca'),
  guardarMarca: (m: MarcaPublicacion) => api.poner<MarcaPublicacion>('/api/publicaciones/marca', m),
  subirLogo: (archivo: File) => {
    const f = new FormData()
    f.append('archivo', archivo)
    return api.subir<MarcaPublicacion>('/api/publicaciones/marca/logo', f)
  },
  quitarLogo: () => api.borrar<MarcaPublicacion>('/api/publicaciones/marca/logo'),
  logo: '/api/publicaciones/marca/logo',
  archivo: (codigo: string, descargar = false) => `/api/publicaciones/${codigo}/archivo${descargar ? '?descargar=true' : ''}`,
}

export const medicion = {
  estado: () => api.obtener<EstadoMedicion>('/api/medicion/estado'),
  sincronizar: (desde?: string) => api.enviar<SincronizacionMeta>('/api/medicion/meta/sincronizar', desde ? { desde } : {}),
  resumen: (desde: string, hasta: string) => api.obtener<ResumenMedicion>(`/api/medicion/resumen?${new URLSearchParams({ desde, hasta })}`),
  informe: (desde: string, hasta: string) => api.enviar<{ informe: InformeGuardado; ia: ResumenIa }>('/api/medicion/informe', { desde, hasta }),
  ga4: (desde: string, hasta: string) => api.obtener<InformeGa4>(`/api/medicion/ga4?${new URLSearchParams({ desde, hasta })}`),
  ga4Propiedades: () =>
    api.obtener<{ propiedades: { propiedad: string; nombre: string; cuenta: string }[]; configurada: string | null; ok: boolean }>(
      '/api/medicion/ga4/propiedades',
    ),
  elegirPropiedadGa4: (propiedad: string) => api.poner<{ propiedad: string }>('/api/medicion/ga4/propiedad', { propiedad }),
  google: (comprobar = false) => api.obtener<ConexionGoogle>(`/api/medicion/google?comprobar=${comprobar}`),
  conectarGoogle: () => api.enviar<{ url: string }>('/api/medicion/google/conectar'),
}
