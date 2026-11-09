<script setup lang="ts">
/**
 * Plan SEO: qué publican el sitio propio y sus competidores y qué búsquedas informacionales
 * tocan, para proponer artículos que el sitio propio aún no cubre, redactarlos y enviarlos a WordPress.
 *
 * Cuatro pasos, cada uno una tarea en segundo plano (una a la vez):
 *   1. Inventario de cada sitio (robots.txt, sitemaps, páginas). Sin IA.
 *   2. Temas de cada página (IA).
 *   3. Keywords candidatas: intención, grupos y cobertura en el sitio propio (IA).
 *   4. Artículos: borrador de la IA, revisión y envío a WordPress (IA + WordPress).
 *
 * Las keywords son hipótesis: salen del contenido público de un competidor, no de
 * su posición en Google. Esa comprobación es la fase siguiente del plan.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { seo } from '@/api/radar'
import type {
  ArticuloSeo,
  Cobertura,
  EstadoPaginaSeo,
  EstadoTareaSeo,
  IntencionSeo,
  KeywordSeo,
  PaginaSeo,
  FechaMinimaSeo,
  RubroSeo,
  SitioSeo,
  TareaSeo,
  WordpressEstado,
  WordpressPrueba,
} from '@/api/tipos'
import Icono from '@/components/Icono.vue'
import PanelAutomatico from '@/components/PanelAutomatico.vue'
import InformesGuardados from '@/components/InformesGuardados.vue'
import PanelSearchConsole from '@/components/PanelSearchConsole.vue'
import { confirmar } from '@/composables/confirmar'
import { fechaHora, usd } from '@/composables/formato'
import { descargarCsv } from '@/composables/keywords'
import { SETS_RUBRO, type SetRubro, alternarSet, elegidasDelSet, normalizarPalabra, palabrasPropias, setsCompletos } from '@/composables/rubro'
import { useSondeo } from '@/composables/sondeo'
import { useAuth } from '@/stores/auth'
import { useAvisos } from '@/stores/avisos'

const auth = useAuth()
const avisos = useAvisos()

const route = useRoute()
const router = useRouter()

type Pestana = 'sitios' | 'paginas' | 'keywords' | 'articulos'
const PESTANAS: Pestana[] = ['sitios', 'paginas', 'keywords', 'articulos']
// La pestaña viaja en la URL: volver desde un artículo deja en «Artículos».
const pestana = ref<Pestana>(PESTANAS.includes(route.query.pestana as Pestana) ? (route.query.pestana as Pestana) : 'sitios')
watch(pestana, (p) => router.replace({ query: p === 'sitios' ? {} : { pestana: p } }))

const sitios = ref<SitioSeo[]>([])
const tareas = ref<TareaSeo[]>([])
const rubro = ref<RubroSeo | null>(null)
const minima = ref<FechaMinimaSeo | null>(null)
const minimaNueva = ref('')
const articulos = ref<ArticuloSeo[]>([])
const cargando = ref(true)
const error = ref('')

async function cargar() {
  const [s, t, r, a, fm] = await Promise.all([seo.sitios(), seo.tareas(), seo.rubro(), seo.articulos(), seo.fechaMinima()])
  minima.value = fm
  minimaNueva.value = fm.fecha ?? ''
  sitios.value = s
  tareas.value = t
  rubro.value = r
  articulos.value = a
}

const miSitio = computed(() => sitios.value.find((s) => s.rol === 'PROPIO')?.nombre ?? 'tu sitio')
/** El artículo que redacta una tarea ARTICULO. */
const articuloDe = (t: TareaSeo) => (t.tipo === 'ARTICULO' && typeof t.resumen?.articulo === 'string' ? t.resumen.articulo : null)

onMounted(async () => {
  try {
    await cargar()
    alAbrir(pestana.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    cargando.value = false
  }
})

const activa = computed(() => tareas.value.find((t) => t.activa) ?? null)
/** La pausa más reciente, si es la última tarea que se lanzó de su tipo y sitio. */
const enPausa = computed(() => tareas.value.find((t) => t.estado === 'PAUSADA') ?? null)
const ultimaKeywords = computed(() => tareas.value.find((t) => t.tipo === 'KEYWORDS' && t.estado === 'TERMINADA') ?? null)

useSondeo(cargar, () => !!activa.value, 2500)

// Al terminar una tarea se avisa y se refresca lo que esté abierto.
watch(activa, (ahora, antes) => {
  if (!antes || ahora) return
  const fin = tareas.value.find((t) => t.codigo === antes.codigo)
  if (fin?.estado === 'TERMINADA') avisos.exito(fin.mensaje || 'Tarea terminada.')
  else if (fin?.estado === 'PAUSADA') avisos.error(fin.error || 'La tarea quedó en pausa.')
  if (pestana.value === 'paginas') cargarPaginas()
  if (pestana.value === 'keywords' || fin?.tipo === 'KEYWORDS') cargarKeywords()
})

const nombreSitio = (codigo: string | null) => sitios.value.find((s) => s.codigo === codigo)?.nombre ?? codigo ?? ''

const TIPO_TAREA: Record<TareaSeo['tipo'], string> = {
  INVENTARIO: 'Inventario',
  TEMAS: 'Temas (IA)',
  KEYWORDS: 'Keywords (IA)',
  ARTICULO: 'Artículo (IA)',
  AUTOMATICO: 'Flujo automático',
}
const ESTADO_TAREA: Record<EstadoTareaSeo, { texto: string; chip: string }> = {
  EN_COLA: { texto: 'En cola', chip: '' },
  CORRIENDO: { texto: 'En marcha', chip: 'chip-cian' },
  TERMINADA: { texto: 'Terminada', chip: 'chip-lima' },
  PAUSADA: { texto: 'En pausa', chip: 'chip-ambar' },
  CANCELADA: { texto: 'Cancelada', chip: '' },
}

// ── Acciones ──────────────────────────────────────────────────────────────

const ocupado = ref(false)

async function lanzar(accion: () => Promise<TareaSeo>) {
  ocupado.value = true
  try {
    await accion()
    await cargar()
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

async function inventariar(s: SitioSeo) {
  const minutos = Math.max(1, Math.ceil((s.maxPaginas * 1.6) / 60))
  const r = await confirmar({
    titulo: `¿Inventariar ${s.nombre}?`,
    mensaje: `Lee su robots.txt y sus sitemaps y descarga sus páginas públicas, una por segundo para no cargar el sitio.`,
    puntos: [
      `Como mucho ${s.maxPaginas} páginas por vez (unos ${minutos} minutos en el peor caso).`,
      'Las que ya tiene y no cambiaron no se vuelven a descargar.',
      'Se respeta lo que su robots.txt no permite leer. No usa IA.',
    ],
    aceptar: 'Inventariar',
  })
  if (r.ok) lanzar(() => seo.inventariar(s.codigo))
}

async function extraerTemas(s: SitioSeo) {
  const aIa = s.sinTemasDelSector ?? s.sinTemas
  const fuera = s.sinTemas - aIa
  const llamadas = Math.ceil(aIa / 12)
  const r = await confirmar({
    titulo: `¿Extraer los temas de ${s.nombre}?`,
    mensaje: `Gemini lee ${aIa} ${aIa === 1 ? 'página' : 'páginas'} y dice de qué trata cada una y qué búsquedas informacionales toca.`,
    puntos: [
      ...(fuera
        ? [`${fuera} de ${s.sinTemas} no mencionan ninguna palabra de tu rubro (en su URL, título, encabezados o inicio del texto): se marcan «fuera del sector» sin IA y no cuestan nada.`]
        : []),
      llamadas
        ? `Unas ${llamadas} ${llamadas === 1 ? 'llamada' : 'llamadas'} a Gemini, de la cuota de la clave configurada.`
        : 'No hace falta ninguna llamada a Gemini.',
      'Si la cuota se acaba, la tarea queda en pausa y «Continuar» sigue donde se quedó.',
    ],
    aceptar: 'Extraer temas',
  })
  if (r.ok) lanzar(() => seo.extraerTemas(s.codigo))
}

async function generarKeywords() {
  const r = await confirmar({
    titulo: '¿Generar las keywords candidatas?',
    mensaje: `Junta las búsquedas que tocan las páginas de los competidores, clasifica su intención, las agrupa y compara cada grupo con las páginas de ${miSitio.value}.`,
    puntos: [
      'Sustituye la lista anterior de keywords.',
      'Usa Gemini: unas pocas llamadas (depende de cuántas búsquedas salgan).',
      'Son hipótesis: todavía no se comprueba quién posiciona en Google.',
    ],
    aceptar: 'Generar',
  })
  if (r.ok) lanzar(() => seo.generarKeywords())
}

const continuar = (t: TareaSeo) => lanzar(() => seo.continuar(t.codigo))

async function cancelar(t: TareaSeo) {
  const r = await confirmar({ titulo: '¿Cancelar la tarea?', mensaje: 'Lo hecho hasta ahora queda guardado.', aceptar: 'Cancelar tarea', cancelar: 'Seguir', tono: 'peligro' })
  if (r.ok) lanzar(() => seo.cancelar(t.codigo))
}

// ── Agregar, ajustar y quitar sitios ──────────────────────────────────────

interface Borrador {
  nombre: string
  hosts: string
  maxPaginas: number
}

/** Dominios escritos uno por línea (o separados por comas); el backend se queda con el host de un enlace. */
const separarHosts = (t: string) => t.split(/[\s,;]+/).filter(Boolean)

const nuevo = ref<Borrador | null>(null)

async function agregarSitio() {
  if (!nuevo.value) return
  ocupado.value = true
  try {
    const s = await seo.crearSitio(nuevo.value.nombre, separarHosts(nuevo.value.hosts))
    sitios.value = [...sitios.value, s]
    nuevo.value = null
    avisos.exito(`${s.nombre} agregado. Pulsa «Inventariar» en su tarjeta para leer sus páginas.`)
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

const borradores = ref<Record<string, Borrador>>({})

function alternarAjustes(s: SitioSeo) {
  if (borradores.value[s.codigo]) delete borradores.value[s.codigo]
  else borradores.value[s.codigo] = { nombre: s.nombre, hosts: s.hosts.join('\n'), maxPaginas: s.maxPaginas }
}

async function guardarSitio(s: SitioSeo) {
  const b = borradores.value[s.codigo]
  if (!b) return
  const hosts = separarHosts(b.hosts)
  if (s.descubierto && hosts.join() !== s.hosts.join()) {
    const r = await confirmar({
      titulo: `¿Cambiar los dominios de ${s.nombre}?`,
      mensaje: 'Las páginas ya leídas y sus temas se conservan hasta el próximo inventario.',
      puntos: [
        'Al volver a inventariar se leen las páginas que declare el nuevo dominio.',
        'Las que el sitio ya no declare quedan como «Retirada» y dejan de contar para las keywords.',
      ],
      aceptar: 'Cambiar dominios',
    })
    if (!r.ok) return
  }
  ocupado.value = true
  try {
    const nuevo = await seo.ajustarSitio(s.codigo, { nombre: b.nombre, hosts, maxPaginas: Number(b.maxPaginas) })
    sitios.value = sitios.value.map((x) => (x.codigo === s.codigo ? nuevo : x))
    borradores.value[s.codigo] = { nombre: nuevo.nombre, hosts: nuevo.hosts.join('\n'), maxPaginas: nuevo.maxPaginas }
    avisos.exito(`${nuevo.nombre}: cambios guardados.`)
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

async function quitarSitio(s: SitioSeo) {
  const n = total(s)
  const r = await confirmar({
    titulo: `¿Quitar ${s.nombre}?`,
    mensaje: n ? `Se borran sus ${n} páginas inventariadas y sus temas. No se puede deshacer.` : 'Deja de aparecer en el Plan SEO.',
    puntos: [
      'Las keywords ya generadas con sus páginas siguen en la lista hasta que vuelvas a generarlas.',
      'Sus tareas pasadas quedan en el historial.',
    ],
    aceptar: 'Quitar',
    tono: 'peligro',
  })
  if (!r.ok) return
  ocupado.value = true
  try {
    await seo.borrarSitio(s.codigo)
    sitios.value = sitios.value.filter((x) => x.codigo !== s.codigo)
    if (pSitio.value === s.codigo) pSitio.value = ''
    avisos.exito(`${s.nombre} ya no está en el Plan SEO.`)
    await cargar()
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

async function borrarArticulo(a: ArticuloSeo) {
  const r = await confirmar({
    titulo: `¿Borrar «${a.titulo || a.keyword}»?`,
    mensaje: a.wpId ? 'Se borra del Radar. La entrada que ya está en WordPress no se toca: bórrala allí si no la quieres.' : 'Se borra del Radar. No se puede deshacer.',
    puntos: ['Su búsqueda vuelve a quedar libre: el flujo automático podría proponerla otra vez.'],
    aceptar: 'Borrar',
    tono: 'peligro',
  })
  if (!r.ok) return
  ocupado.value = true
  try {
    await seo.borrarArticulo(a.codigo)
    articulos.value = articulos.value.filter((x) => x.codigo !== a.codigo)
    avisos.exito('Artículo borrado.')
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

const ERRORES: EstadoPaginaSeo[] =['HTTP_ERROR', 'ERROR', 'BLOQUEADA', 'NO_HTML']
const cuenta = (s: SitioSeo, ...estados: EstadoPaginaSeo[]) => estados.reduce((n, e) => n + (s.paginas[e] ?? 0), 0)
const total = (s: SitioSeo) => Object.values(s.paginas).reduce((n, v) => n + (v ?? 0), 0)
const competidoresConTemas = computed(() => sitios.value.filter((s) => s.rol === 'COMPETIDOR' && s.conTemas > 0).length)
const propioListo = computed(() => sitios.value.some((s) => s.rol === 'PROPIO' && (s.paginas.OK ?? 0) > 0))

// ── Páginas ───────────────────────────────────────────────────────────────

const ESTADO_PAGINA: Record<EstadoPaginaSeo, { texto: string; chip: string }> = {
  PENDIENTE: { texto: 'Pendiente', chip: '' },
  OK: { texto: 'Leída', chip: 'chip-lima' },
  EXCLUIDA: { texto: 'Excluida', chip: '' },
  NO_HTML: { texto: 'No es página', chip: '' },
  HTTP_ERROR: { texto: 'Error HTTP', chip: 'chip-rojo' },
  BLOQUEADA: { texto: 'Bloqueada', chip: 'chip-ambar' },
  ERROR: { texto: 'Error', chip: 'chip-rojo' },
  RETIRADA: { texto: 'Retirada', chip: '' },
  ANTIGUA: { texto: 'Antigua', chip: '' },
}

const paginas = ref<PaginaSeo[]>([])
const pSitio = ref('')
const pEstado = ref<'' | 'OK' | 'EXCLUIDA' | 'ERRORES' | 'PENDIENTE' | 'RETIRADA' | 'ANTIGUA'>('OK')
const pTipo = ref('')
const pTexto = ref('')
const pVisibles = ref(100)
const abierta = ref<string | null>(null)
const cargandoPaginas = ref(false)

async function cargarPaginas() {
  if (!pSitio.value) pSitio.value = sitios.value.find((s) => total(s) > 0)?.codigo ?? sitios.value[0]?.codigo ?? ''
  if (!pSitio.value) return
  cargandoPaginas.value = true
  try {
    paginas.value = await seo.paginas(pSitio.value)
  } catch (e) {
    avisos.error(e)
  } finally {
    cargandoPaginas.value = false
  }
}

watch(pSitio, () => {
  pVisibles.value = 100
  if (pestana.value === 'paginas') cargarPaginas()
})

const tiposPagina = computed(() =>
  [...new Set(paginas.value.filter((p) => !p.temas?.fuera_del_sector).map((p) => p.temas?.tipo_pagina).filter((t): t is string => !!t))].sort(),
)
/** Valor del filtro «Tipo» para las páginas descartadas sin IA. */
const FUERA = '__fuera'
const hayFuera = computed(() => paginas.value.some((p) => p.temas?.fuera_del_sector))

const paginasFiltradas = computed(() => {
  const t = pTexto.value.trim().toLowerCase()
  return paginas.value.filter((p) => {
    if (pEstado.value === 'ERRORES' ? !ERRORES.includes(p.estado) : pEstado.value && p.estado !== pEstado.value) return false
    if (pTipo.value === FUERA ? !p.temas?.fuera_del_sector : pTipo.value && (p.temas?.fuera_del_sector || p.temas?.tipo_pagina !== pTipo.value)) return false
    if (!t) return true
    return `${p.url} ${p.datos?.title ?? ''} ${p.datos?.h1 ?? ''} ${p.temas?.tema ?? ''}`.toLowerCase().includes(t)
  })
})

const ruta = (url: string) => {
  try {
    const u = new URL(url)
    return u.host.replace(/^www\./, '') + decodeURI(u.pathname)
  } catch {
    return url
  }
}

// ── Keywords ──────────────────────────────────────────────────────────────

const INTENCION: Record<IntencionSeo, string> = {
  INFORMATIONAL: 'Informacional',
  COMMERCIAL: 'Comercial',
  TRANSACTIONAL: 'Transaccional',
  NAVIGATIONAL: 'De marca',
  NEEDS_REVIEW: 'Por revisar',
}
const COBERTURA: Record<Cobertura, { texto: string; chip: string; ayuda: string }> = {
  SIN_COBERTURA: { texto: 'Sin cobertura', chip: 'chip-cian', ayuda: 'Tu sitio no tiene una página que responda esta búsqueda: candidata a artículo.' },
  PARCIAL: { texto: 'Parcial', chip: 'chip-ambar', ayuda: 'Tu sitio toca el tema pero no responde la pregunta completa.' },
  YA_CUBIERTA: { texto: 'Ya cubierta', chip: 'chip-lima', ayuda: 'Tu sitio ya responde esta búsqueda en una página.' },
  INCIERTO: { texto: 'Incierto', chip: '', ayuda: 'Los datos no alcanzan para decidir.' },
}
const ORDEN_COBERTURA: Record<string, number> = { SIN_COBERTURA: 0, PARCIAL: 1, INCIERTO: 2, YA_CUBIERTA: 3 }

const keywords = ref<KeywordSeo[]>([])
const kIntencion = ref<'' | IntencionSeo>('INFORMATIONAL')
const kCobertura = ref<'' | Cobertura>('')
const kSitio = ref('')
const kTexto = ref('')
const cargandoKeywords = ref(false)

async function cargarKeywords() {
  cargandoKeywords.value = true
  try {
    keywords.value = await seo.keywords()
  } catch (e) {
    avisos.error(e)
  } finally {
    cargandoKeywords.value = false
  }
}

const sitiosOrigen = computed(() => [...new Set(keywords.value.flatMap((k) => k.origenes.map((o) => o.sitio)))].sort())

const keywordsFiltradas = computed(() => {
  const t = kTexto.value.trim().toLowerCase()
  return keywords.value
    .filter(
      (k) =>
        (!kIntencion.value || k.intencion === kIntencion.value) &&
        (!kCobertura.value || k.cobertura === kCobertura.value) &&
        (!kSitio.value || k.origenes.some((o) => o.sitio === kSitio.value)) &&
        (!t || `${k.keyword} ${k.grupo ?? ''}`.toLowerCase().includes(t)),
    )
    .sort(
      (a, b) =>
        (ORDEN_COBERTURA[a.cobertura ?? ''] ?? 4) - (ORDEN_COBERTURA[b.cobertura ?? ''] ?? 4) ||
        b.origenes.length - a.origenes.length ||
        (a.grupo ?? '').localeCompare(b.grupo ?? ''),
    )
})

const gruposVisibles = computed(() => new Set(keywordsFiltradas.value.map((k) => k.grupo)).size)

function exportar() {
  const celda = (v: unknown) => {
    const s = v == null ? '' : String(v)
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const cab = ['Keyword', 'Grupo', 'Keyword principal del grupo', 'Intención', 'Relevancia (0-100)', `Cobertura en ${miSitio.value}`, `URL de ${miSitio.value}`, 'Motivo de la cobertura',
    'Sitios de origen', 'URLs de origen', 'Evidencia', 'Motivo de la intención']
  const filas = keywordsFiltradas.value.map((k) => [
    k.keyword, k.grupo, k.canonica, k.intencion ? INTENCION[k.intencion] : '', k.relevancia, k.cobertura ? COBERTURA[k.cobertura].texto : 'No evaluada',
    k.urlPropia, k.motivoCobertura, [...new Set(k.origenes.map((o) => o.sitio))].join(' / '), k.origenes.map((o) => o.url).join(' '), k.evidencia, k.motivo,
  ])
  descargarCsv('plan-seo-keywords', '﻿' + [cab, ...filas].map((f) => f.map(celda).join(',')).join('\r\n'))
}

// ── Rubro del negocio ─────────────────────────────────────────────────────

const borradorRubro = ref<{ descripcion: string; palabras: string[] } | null>(null)
const palabraNueva = ref('')

function editarRubro() {
  if (rubro.value) borradorRubro.value = { descripcion: rubro.value.descripcion, palabras: [...rubro.value.palabras] }
  palabraNueva.value = ''
}

function cambiarSet(s: SetRubro) {
  if (borradorRubro.value) borradorRubro.value.palabras = alternarSet(s, borradorRubro.value.palabras)
}

/** Agrega lo escrito (una o varias, separadas por comas). Devuelve false si algo no es una sola palabra. */
function agregarPalabras(): boolean {
  const b = borradorRubro.value
  if (!b) return false
  const nuevas = palabraNueva.value.split(/[,;\n]+/).map(normalizarPalabra).filter(Boolean)
  const malas = nuevas.filter((p) => !/^[a-z0-9]+$/.test(p))
  if (malas.length) {
    avisos.error(`«${malas[0]}»: escribe una palabra por término, sin espacios ni signos (el filtro compara palabra por palabra).`)
    return false
  }
  b.palabras = [...b.palabras, ...nuevas.filter((p, i) => !b.palabras.includes(p) && nuevas.indexOf(p) === i)]
  palabraNueva.value = ''
  return true
}

function quitarPalabra(p: string) {
  if (borradorRubro.value) borradorRubro.value.palabras = borradorRubro.value.palabras.filter((x) => x !== p)
}

async function sugerirRubro() {
  if (!borradorRubro.value) return
  ocupado.value = true
  try {
    const r = await seo.sugerirRubro()
    borradorRubro.value = { descripcion: r.descripcion, palabras: r.palabras.map(normalizarPalabra) }
    avisos.exito('Propuesta lista: revísala y pulsa «Guardar» si te sirve.')
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

async function guardarRubro() {
  const b = borradorRubro.value
  const r = rubro.value
  if (!b || !r) return
  // Lo que quedó escrito sin pulsar «Agregar» también cuenta.
  if (palabraNueva.value.trim() && !agregarPalabras()) return
  const palabras = b.palabras
  const cambiaDescripcion = b.descripcion.trim() !== r.descripcion
  const cambianPalabras = [...palabras].sort().join() !== [...r.palabras].sort().join()
  if (!cambiaDescripcion && !cambianPalabras) {
    borradorRubro.value = null
    return
  }
  const afectadas = cambiaDescripcion ? r.conTemas : r.fueraDelSector
  if (afectadas) {
    const ok = await confirmar({
      titulo: '¿Cambiar el rubro?',
      mensaje: cambiaDescripcion
        ? `La relevancia de las ${afectadas} páginas que ya tienen temas se midió contra el rubro anterior.`
        : `Con otras palabras, las ${afectadas} páginas que el filtro dejó «fuera del sector» pueden pasar ahora.`,
      puntos: [
        `Esas ${afectadas} páginas vuelven a quedar sin temas: pulsa «Extraer temas» en cada sitio para evaluarlas de nuevo con Gemini.`,
        'Las keywords y los artículos que ya tienes no cambian hasta que los vuelvas a generar.',
      ],
      aceptar: 'Cambiar el rubro',
    })
    if (!ok.ok) return
  }
  ocupado.value = true
  try {
    rubro.value = await seo.guardarRubro(b.descripcion, palabras)
    borradorRubro.value = null
    avisos.exito(rubro.value.reevaluar ? `Rubro guardado. ${rubro.value.reevaluar} páginas esperan «Extraer temas».` : 'Rubro guardado.')
    sitios.value = await seo.sitios()
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

// ── Fecha mínima de publicación ───────────────────────────────────────────

const hoy = new Date().toISOString().slice(0, 10)

async function guardarMinima(fecha: string | null) {
  ocupado.value = true
  try {
    const r = await seo.guardarFechaMinima(fecha)
    minima.value = r
    minimaNueva.value = r.fecha ?? ''
    const partes = [
      r.marcadas ? `${r.marcadas} páginas quedan como antiguas` : '',
      r.devueltas ? `${r.devueltas} vuelven al inventario` : '',
    ].filter(Boolean)
    avisos.exito(`${r.fecha ? 'Fecha mínima guardada' : 'Sin fecha mínima'}${partes.length ? `: ${partes.join(' y ')}.` : '.'}`)
    sitios.value = await seo.sitios()
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

// ── Artículos ─────────────────────────────────────────────────────────────

const articuloPorGrupo = computed(() => new Map(articulos.value.map((a) => [a.grupo, a])))

async function redactarArticulo(k: KeywordSeo) {
  if (!k.grupo) return
  const r = await confirmar({
    titulo: `¿Redactar un artículo sobre «${k.canonica ?? k.keyword}»?`,
    mensaje: `Gemini escribe un borrador para ${miSitio.value} que responde esa búsqueda y sus variantes, con lo que publican los competidores como contexto (sin copiarlos).`,
    puntos: [
      'Una llamada a Gemini. Tarda alrededor de un minuto.',
      'No inventa datos de tu negocio (precios, fechas, duraciones…): los deja como «[COMPLETAR: …]» para que los escribas tú.',
      'Nada se envía a WordPress hasta que lo revises y lo pidas.',
    ],
    aceptar: 'Redactar',
    campo: { etiqueta: 'Indicaciones (opcional)', marcador: 'Ej.: enfocado en principiantes, menciona nuestro curso de pastelería, unas 900 palabras' },
  })
  if (!r.ok) return
  ocupado.value = true
  try {
    const a = await seo.crearArticulo(k.grupo, r.texto)
    router.push(`/seo/articulos/${a.codigo}`)
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

function estadoArticulo(a: ArticuloSeo): { texto: string; chip: string } {
  if (a.tareaEstado === 'EN_COLA' || a.tareaEstado === 'CORRIENDO') return { texto: 'Redactando…', chip: 'chip-cian' }
  if (!a.contenido) return a.tareaEstado === 'PAUSADA' ? { texto: 'En pausa', chip: 'chip-ambar' } : { texto: 'Sin redactar', chip: '' }
  if (a.wpId) {
    const publicado = a.wpEstado === 'publish'
    return a.cambiosSinEnviar
      ? { texto: 'Cambios sin enviar', chip: 'chip-ambar' }
      : { texto: publicado ? 'Publicado' : 'En WordPress (borrador)', chip: publicado ? 'chip-lima' : 'chip-violeta' }
  }
  return { texto: 'Borrador', chip: '' }
}

const PENDIENTE = /\[COMPLETAR:[^\]\n]*\]/gi
const faltan = (a: ArticuloSeo) => (a.contenido?.match(PENDIENTE) ?? []).length

const wp = ref<WordpressEstado | null>(null)
const wpPrueba = ref<WordpressPrueba | null>(null)

async function cargarWordpress() {
  try {
    wp.value = await seo.wordpress()
  } catch (e) {
    avisos.error(e)
  }
}

async function probarWordpress() {
  ocupado.value = true
  wpPrueba.value = null
  try {
    wpPrueba.value = await seo.probarWordpress()
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

function alAbrir(p: Pestana) {
  if (p === 'paginas' && !paginas.value.length) cargarPaginas()
  if (p === 'keywords' && !keywords.value.length) cargarKeywords()
  if (p === 'articulos' && !wp.value) cargarWordpress()
}

watch(pestana, (p) => {
  if (p === 'sitios' || p === 'articulos') cargar().catch(() => {})
  alAbrir(p)
})
</script>

<template>
  <div class="pagina">
    <div class="pagina-cabecera">
      <div>
        <h1>Plan SEO</h1>
        <p>
          Qué publican {{ miSitio }} y sus competidores, qué búsquedas informacionales tocan sus páginas y qué artículos le faltan a
          {{ miSitio }}: se redactan aquí y se envían a WordPress.
        </p>
      </div>
    </div>

    <p v-if="cargando" class="cargando suave">Cargando…</p>
    <div v-else-if="error" class="aviso aviso-error" role="alert"><Icono nombre="error" /><div class="aviso-cuerpo">{{ error }}</div></div>

    <template v-else>
      <!-- Tarea en marcha o en pausa -->
      <section v-if="activa" class="panel tarea" aria-live="polite">
        <div class="fila tarea-cabeza">
          <strong>{{ TIPO_TAREA[activa.tipo] }}<template v-if="activa.sitio"> · {{ nombreSitio(activa.sitio) }}</template></strong>
          <RouterLink v-if="articuloDe(activa)" :to="`/seo/articulos/${articuloDe(activa)}`" class="chico">Ver artículo</RouterLink>
          <span class="chip" :class="ESTADO_TAREA[activa.estado].chip">{{ ESTADO_TAREA[activa.estado].texto }}</span>
          <button class="boton boton-chico" type="button" :disabled="ocupado" @click="cancelar(activa)">Cancelar</button>
        </div>
        <p class="suave">{{ activa.mensaje || 'Trabajando…' }}</p>
        <div v-if="activa.total" class="barra" role="progressbar" :aria-valuenow="activa.hechos" aria-valuemin="0" :aria-valuemax="activa.total">
          <div class="barra-relleno" :style="{ width: `${Math.round((activa.hechos / activa.total) * 100)}%` }"></div>
        </div>
      </section>
      <div v-else-if="enPausa" class="aviso aviso-ambar" role="status">
        <Icono nombre="pausa" />
        <div class="aviso-cuerpo">
          <strong>{{ TIPO_TAREA[enPausa.tipo] }}<template v-if="enPausa.sitio"> de {{ nombreSitio(enPausa.sitio) }}</template> en pausa.</strong>
          {{ enPausa.error }}
          <div class="fila acciones-pausa">
            <button class="boton boton-chico boton-primario" type="button" :disabled="ocupado" @click="continuar(enPausa)">Continuar</button>
            <button class="boton boton-chico" type="button" :disabled="ocupado" @click="cancelar(enPausa)">Cancelar</button>
          </div>
        </div>
      </div>

      <div class="pestanas" role="tablist" aria-label="Plan SEO">
        <button role="tab" type="button" :aria-selected="pestana === 'sitios'" :class="{ activa: pestana === 'sitios' }" @click="pestana = 'sitios'">Sitios</button>
        <button role="tab" type="button" :aria-selected="pestana === 'paginas'" :class="{ activa: pestana === 'paginas' }" @click="pestana = 'paginas'">Páginas</button>
        <button role="tab" type="button" :aria-selected="pestana === 'keywords'" :class="{ activa: pestana === 'keywords' }" @click="pestana = 'keywords'">Keywords</button>
        <button role="tab" type="button" :aria-selected="pestana === 'articulos'" :class="{ activa: pestana === 'articulos' }" @click="pestana = 'articulos'">
          Artículos<template v-if="articulos.length"> ({{ articulos.length }})</template>
        </button>
      </div>

      <!-- ── Sitios ── -->
      <template v-if="pestana === 'sitios'">
        <ol class="pasos suave chico">
          <li><strong>Inventario</strong> de cada sitio: qué páginas publica y de qué hablan sus títulos. Sin IA.</li>
          <li><strong>Temas</strong> de las páginas de los competidores con IA: qué búsquedas informacionales tocan.</li>
          <li><strong>Keywords</strong>: se agrupan y se comparan con lo que {{ miSitio }} ya tiene (hace falta su inventario).</li>
          <li><strong>Artículos</strong>: eliges una keyword sin cobertura, la IA redacta un borrador, lo revisas y lo envías a WordPress.</li>
        </ol>

        <section class="panel rubro">
          <div class="fila rubro-cabeza">
            <h2>Rubro de tu negocio</h2>
            <span v-if="rubro?.porDefecto" class="chip">Por defecto</span>
            <button v-if="rubro && !borradorRubro" class="boton boton-chico boton-ajustes" type="button" @click="editarRubro">
              <Icono nombre="lapiz" /> Cambiar
            </button>
          </div>
          <template v-if="rubro && !borradorRubro">
            <p>{{ rubro.descripcion }}</p>
            <p class="chico tenue">
              La IA mide la relevancia de cada página contra este rubro. Antes, un filtro gratuito descarta las páginas de los
              competidores que no mencionan ninguna de estas {{ rubro.palabras.length }} palabras:
            </p>
            <p class="palabras">
              <span v-for="s in setsCompletos(rubro.palabras)" :key="s.nombre" class="chip chip-cian">{{ s.nombre }}</span>
              <span v-if="palabrasPropias(rubro.palabras).length" class="chip">
                + {{ palabrasPropias(rubro.palabras).length }} {{ palabrasPropias(rubro.palabras).length === 1 ? 'palabra propia' : 'palabras propias' }}
              </span>
            </p>
            <details class="detalle chico">
              <summary>Ver palabras</summary>
              <p class="palabras">
                <span v-for="p in rubro.palabras" :key="p" class="chip">{{ p }}</span>
              </p>
            </details>
          </template>
          <form v-else-if="borradorRubro" class="ajustes" @submit.prevent="guardarRubro">
            <label class="campo">
              <span>¿A qué se dedica {{ miSitio }}? (una frase)</span>
              <textarea v-model="borradorRubro.descripcion" rows="2" maxlength="300" required></textarea>
            </label>
            <div class="campo">
              <span>Sets de palabras (pulsa para activar o quitar uno entero)</span>
              <div class="sets">
                <button
                  v-for="s in SETS_RUBRO"
                  :key="s.nombre"
                  type="button"
                  class="set"
                  :class="{
                    activo: elegidasDelSet(s, borradorRubro.palabras) === s.palabras.length,
                    parcial: elegidasDelSet(s, borradorRubro.palabras) > 0 && elegidasDelSet(s, borradorRubro.palabras) < s.palabras.length,
                  }"
                  :aria-pressed="elegidasDelSet(s, borradorRubro.palabras) === s.palabras.length"
                  :title="s.palabras.join(', ')"
                  @click="cambiarSet(s)"
                >
                  <strong>{{ s.nombre }}</strong>
                  <span class="chico tenue">
                    {{ elegidasDelSet(s, borradorRubro.palabras) === s.palabras.length || !elegidasDelSet(s, borradorRubro.palabras)
                      ? `${s.palabras.length} palabras`
                      : `${elegidasDelSet(s, borradorRubro.palabras)} de ${s.palabras.length}` }}
                  </span>
                  <span class="chico tenue muestra">{{ s.palabras.slice(0, 5).join(', ') }}…</span>
                </button>
              </div>
            </div>
            <div class="campo">
              <span>Palabras elegidas ({{ borradorRubro.palabras.length }})</span>
              <p v-if="borradorRubro.palabras.length" class="palabras">
                <span v-for="p in borradorRubro.palabras" :key="p" class="chip mono">
                  {{ p }}
                  <button class="quitar" type="button" :aria-label="`Quitar ${p}`" @click="quitarPalabra(p)">×</button>
                </span>
              </p>
              <p v-else class="chico tenue">Ninguna: activa un set o escribe las tuyas.</p>
              <div class="fila">
                <input
                  v-model="palabraNueva"
                  class="mono"
                  spellcheck="false"
                  placeholder="Agregar palabras propias, separadas por comas"
                  aria-label="Agregar palabras propias"
                  @keydown.enter.prevent="agregarPalabras"
                />
                <button class="boton boton-chico" type="button" :disabled="!palabraNueva.trim()" @click="agregarPalabras">Agregar</button>
              </div>
            </div>
            <p class="chico tenue">
              Una palabra de 4 letras o más cuenta como comienzo: «cocin» cubre cocina, cocinero y cocinar. Las de 3 o menos cuentan
              solo enteras («bar» no cuenta en «barranco»). Sin tildes ni mayúsculas, da igual cómo las escribas.
            </p>
            <div class="fila">
              <button class="boton boton-chico boton-primario" type="submit" :disabled="ocupado"><Icono nombre="guardar" /> Guardar</button>
              <button
                class="boton boton-chico"
                type="button"
                :disabled="ocupado || !propioListo"
                :title="propioListo ? 'Una llamada a Gemini' : `Primero el inventario de ${miSitio}`"
                @click="sugerirRubro"
              >
                <Icono nombre="chispa" /> Sugerir desde mi web
              </button>
              <button class="boton boton-chico" type="button" @click="borradorRubro = null">Cancelar</button>
            </div>
          </form>
        </section>

        <section class="panel rubro">
          <div class="fila rubro-cabeza">
            <h2>Fecha mínima de publicación</h2>
            <span v-if="minima?.fecha" class="chip chip-cian">Desde el {{ minima.fecha }}</span>
            <span v-else class="chip">Sin límite</span>
          </div>
          <p class="chico tenue">
            Las páginas publicadas antes no se descargan ni pasan a temas ni keywords (por ejemplo, noticias de 2018). La fecha es la
            que declara la página o, si aún no se leyó, la última modificación de su sitemap. Las que no dicen fecha se leen igual.
            <template v-if="minima?.antiguas"> Ahora hay {{ minima.antiguas }} páginas antiguas.</template>
          </p>
          <form class="fila" @submit.prevent="guardarMinima(minimaNueva || null)">
            <input v-model="minimaNueva" type="date" :max="hoy" aria-label="Fecha mínima de publicación" :disabled="ocupado || !!activa" />
            <button class="boton boton-chico boton-primario" type="submit" :disabled="ocupado || !!activa || (minimaNueva || null) === (minima?.fecha ?? null)">
              <Icono nombre="guardar" /> Guardar
            </button>
            <button v-if="minima?.fecha" class="boton boton-chico" type="button" :disabled="ocupado || !!activa" @click="guardarMinima(null)">Quitar el límite</button>
          </form>
        </section>

        <div class="rejilla rejilla-2 sitios">
          <article v-for="s in sitios" :key="s.codigo" class="panel sitio">
            <header class="fila sitio-cabeza">
              <h2>{{ s.nombre }}</h2>
              <span class="chip" :class="s.rol === 'PROPIO' ? 'chip-violeta' : ''">{{ s.rol === 'PROPIO' ? 'Sitio propio' : 'Competidor' }}</span>
            </header>
            <p class="tenue chico hosts">{{ s.hosts.join(' · ') }}</p>

            <dl class="cifras">
              <div><dt>Leídas</dt><dd class="num">{{ s.paginas.OK ?? 0 }}</dd></div>
              <div><dt>Excluidas</dt><dd class="num">{{ cuenta(s, 'EXCLUIDA') }}</dd></div>
              <div><dt>Con error</dt><dd class="num">{{ cuenta(s, ...ERRORES) }}</dd></div>
              <div><dt>Con temas</dt><dd class="num">{{ s.conTemas }}<small v-if="s.paginas.OK" class="tenue"> de {{ s.paginas.OK }}</small></dd></div>
            </dl>
            <p v-if="cuenta(s, 'PENDIENTE')" class="chico suave">{{ cuenta(s, 'PENDIENTE') }} páginas pendientes de leer.</p>
            <p v-if="cuenta(s, 'RETIRADA')" class="chico tenue">{{ cuenta(s, 'RETIRADA') }} ya no están en su sitemap.</p>
            <p v-if="cuenta(s, 'ANTIGUA')" class="chico tenue">{{ cuenta(s, 'ANTIGUA') }} anteriores a la fecha mínima: no se leen ni se analizan.</p>
            <p class="chico tenue">
              <template v-if="s.descubierto">Último inventario: {{ fechaHora(s.descubierto) }}</template>
              <template v-else>Sin inventario todavía.</template>
            </p>
            <ul v-if="s.descubrimiento?.avisos?.length" class="avisos-sitio chico">
              <li v-for="a in s.descubrimiento.avisos" :key="a"><Icono nombre="info" /> {{ a }}</li>
            </ul>

            <details v-if="s.descubrimiento?.sitemaps?.length" class="detalle chico">
              <summary>Sitemaps leídos ({{ s.descubrimiento.sitemaps.length }})</summary>
              <ul>
                <li v-for="m in s.descubrimiento.sitemaps" :key="m.url">
                  <span class="mono">{{ ruta(m.url) }}</span>
                  <span v-if="m.excluido" class="tenue"> — no se recorre: {{ m.excluido }}</span>
                  <span v-else-if="m.estado !== 'OK'" class="rojo"> — {{ m.estado }}</span>
                  <span v-else class="tenue"> — {{ m.tipo === 'indice' ? `índice de ${m.urls} sitemaps` : `${m.urls} URLs` }}</span>
                </li>
              </ul>
            </details>
            <div class="fila acciones">
              <button class="boton boton-chico" type="button" :disabled="!!activa || ocupado" @click="inventariar(s)">
                <Icono nombre="reintentar" /> {{ s.descubierto ? 'Actualizar inventario' : 'Inventariar' }}
              </button>
              <button
                class="boton boton-chico"
                type="button"
                :disabled="!!activa || ocupado || !s.sinTemas"
                :title="!s.paginas.OK ? 'Primero el inventario' : !s.sinTemas ? 'Todas sus páginas ya tienen temas' : ''"
                @click="extraerTemas(s)"
              >
                <Icono nombre="chispa" /> Extraer temas<template v-if="s.sinTemas"> ({{ s.sinTemasDelSector ?? s.sinTemas }})</template>
              </button>
              <button
                class="boton boton-chico boton-ajustes"
                type="button"
                :aria-expanded="!!borradores[s.codigo]"
                :aria-controls="`ajustes-${s.codigo}`"
                @click="alternarAjustes(s)"
              >
                <Icono nombre="ajustes" /> Ajustes
              </button>
            </div>

            <form v-if="borradores[s.codigo]" :id="`ajustes-${s.codigo}`" class="ajustes chico" @submit.prevent="guardarSitio(s)">
                <label class="campo">
                  <span>Nombre</span>
                  <input v-model="borradores[s.codigo].nombre" maxlength="80" required />
                </label>
                <label class="campo">
                  <span>Dominios (uno por línea)</span>
                  <textarea v-model="borradores[s.codigo].hosts" rows="2" spellcheck="false" placeholder="usil.edu.pe"></textarea>
                </label>
                <label class="campo maximo">
                  <span>Máximo de páginas por inventario</span>
                  <input v-model.number="borradores[s.codigo].maxPaginas" type="number" min="10" max="3000" step="10" />
                </label>
                <div class="fila">
                  <button class="boton boton-chico boton-primario" type="submit" :disabled="ocupado"><Icono nombre="guardar" /> Guardar</button>
                  <button
                    v-if="s.rol === 'COMPETIDOR' && auth.esAdmin"
                    class="boton boton-chico boton-peligro"
                    type="button"
                    :disabled="!!activa || ocupado"
                    @click="quitarSitio(s)"
                  >
                    <Icono nombre="basura" /> Quitar competidor
                  </button>
                  <button class="boton boton-chico" type="button" @click="alternarAjustes(s)">Cerrar</button>
                </div>
              </form>
          </article>

          <article class="panel sitio sitio-nuevo">
            <form v-if="nuevo" class="ajustes" @submit.prevent="agregarSitio">
              <h2>Nuevo competidor</h2>
              <label class="campo">
                <span>Nombre</span>
                <input v-model="nuevo.nombre" maxlength="80" required placeholder="Ej.: Cumbre" />
              </label>
              <label class="campo">
                <span>Dominios (uno por línea)</span>
                <textarea v-model="nuevo.hosts" rows="2" required spellcheck="false" placeholder="cumbre.edu.pe"></textarea>
              </label>
              <p class="chico tenue">Puedes pegar el enlace de su web: se guarda solo el dominio. Si publica en dos (como CENFOTUR), escribe ambos.</p>
              <div class="fila">
                <button class="boton boton-chico boton-primario" type="submit" :disabled="ocupado"><Icono nombre="mas" /> Agregar</button>
                <button class="boton boton-chico" type="button" @click="nuevo = null">Cancelar</button>
              </div>
            </form>
            <template v-else>
              <button class="boton" type="button" @click="nuevo = { nombre: '', hosts: '', maxPaginas: 400 }"><Icono nombre="mas" /> Agregar competidor</button>
              <p class="chico tenue">Otra escuela o web cuyos artículos quieras comparar con los de {{ miSitio }}.</p>
            </template>
          </article>
        </div>

        <section class="panel generar">
          <div class="panel-titulo"><h2>Keywords candidatas</h2></div>
          <p class="suave chico">
            Junta las búsquedas que tocan las páginas de los competidores, clasifica su intención, las agrupa y mira si {{ miSitio }} ya
            tiene una página que las responda.
          </p>
          <ul class="requisitos chico">
            <li :class="competidoresConTemas ? 'listo' : ''"><Icono :nombre="competidoresConTemas ? 'ok' : 'x'" /> Al menos un competidor con temas ({{ competidoresConTemas }})</li>
            <li :class="propioListo ? 'listo' : ''"><Icono :nombre="propioListo ? 'ok' : 'x'" /> Inventario de {{ miSitio }}</li>
          </ul>
          <p v-if="ultimaKeywords" class="chico tenue">Última generación: {{ fechaHora(ultimaKeywords.modificado) }} · {{ ultimaKeywords.mensaje }}</p>
          <div class="fila">
            <button class="boton boton-primario" type="button" :disabled="!!activa || ocupado || !competidoresConTemas || !propioListo" @click="generarKeywords">
              <Icono nombre="chispa" /> Generar keywords
            </button>
            <button v-if="ultimaKeywords" class="boton" type="button" @click="pestana = 'keywords'">Ver keywords</button>
          </div>
        </section>

        <section v-if="tareas.length" class="panel">
          <div class="panel-titulo"><h2>Tareas recientes</h2></div>
          <div class="tabla-envoltura">
            <table class="tabla">
              <thead><tr><th>Tarea</th><th>Sitio</th><th>Estado</th><th>Resultado</th><th class="num">IA</th><th>Fecha</th></tr></thead>
              <tbody>
                <tr v-for="t in tareas" :key="t.codigo">
                  <td>{{ TIPO_TAREA[t.tipo] }}</td>
                  <td>
                    <RouterLink v-if="articuloDe(t)" :to="`/seo/articulos/${articuloDe(t)}`">{{ articuloDe(t) }}</RouterLink>
                    <template v-else>{{ t.sitio ? nombreSitio(t.sitio) : 'Todos' }}</template>
                  </td>
                  <td><span class="chip" :class="ESTADO_TAREA[t.estado].chip">{{ ESTADO_TAREA[t.estado].texto }}</span></td>
                  <td class="chico">{{ t.estado === 'PAUSADA' ? t.error : t.mensaje }}</td>
                  <td class="num chico">{{ t.llamadasIa ? `${t.llamadasIa} · ${usd(t.costoUsd)}` : '—' }}</td>
                  <td class="chico tenue">{{ fechaHora(t.modificado) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>

      <!-- ── Páginas ── -->
      <template v-else-if="pestana === 'paginas'">
        <div class="fila filtros">
          <div class="campo">
            <label for="p-sitio">Sitio</label>
            <select id="p-sitio" v-model="pSitio">
              <option v-for="s in sitios" :key="s.codigo" :value="s.codigo">{{ s.nombre }} ({{ total(s) }})</option>
            </select>
          </div>
          <div class="campo">
            <label for="p-estado">Estado</label>
            <select id="p-estado" v-model="pEstado" @change="pVisibles = 100">
              <option value="">Todas</option>
              <option value="OK">Leídas</option>
              <option value="EXCLUIDA">Excluidas</option>
              <option value="ERRORES">Con error</option>
              <option value="PENDIENTE">Pendientes</option>
              <option value="RETIRADA">Retiradas</option>
              <option value="ANTIGUA">Antiguas (antes de la fecha mínima)</option>
            </select>
          </div>
          <div class="campo">
            <label for="p-tipo">Tipo (según la IA)</label>
            <select id="p-tipo" v-model="pTipo" @change="pVisibles = 100">
              <option value="">Todos</option>
              <option v-for="t in tiposPagina" :key="t" :value="t">{{ t.charAt(0) + t.slice(1).toLowerCase() }}</option>
              <option v-if="hayFuera" :value="FUERA">Fuera del sector (sin IA)</option>
            </select>
          </div>
          <div class="campo crece">
            <label for="p-texto">Buscar</label>
            <input id="p-texto" v-model="pTexto" type="search" placeholder="URL, título o tema" @input="pVisibles = 100" />
          </div>
        </div>

        <p v-if="cargandoPaginas" class="cargando suave">Cargando páginas…</p>
        <p v-else-if="!paginas.length" class="vacio">Este sitio aún no tiene inventario. Lánzalo desde la pestaña «Sitios».</p>
        <template v-else>
          <p class="tenue chico">{{ paginasFiltradas.length }} de {{ paginas.length }} páginas</p>
          <div class="tabla-envoltura envoltura-paginas">
            <table class="tabla paginas">
              <thead>
                <tr>
                  <th>Página</th><th class="col-h1">H1</th><th class="num">H2</th><th class="num">Palabras</th><th>Meta</th><th>Tema (IA)</th>
                  <th class="estado">Estado</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="p in paginasFiltradas.slice(0, pVisibles)" :key="p.url">
                  <tr>
                    <td class="celda-url">
                      <button type="button" class="enlace-fila" :aria-expanded="abierta === p.url" @click="abierta = abierta === p.url ? null : p.url">
                        <Icono :nombre="abierta === p.url ? 'arriba' : 'abajo'" /> {{ ruta(p.url) }}
                      </button>
                      <small v-if="p.datos?.title" class="tenue">{{ p.datos.title }}</small>
                    </td>
                    <td class="chico col-h1">{{ p.datos?.h1 ?? '—' }}</td>
                    <td class="num dato" data-etiqueta="H2">{{ p.datos ? p.datos.h2.length : '—' }}</td>
                    <td class="num dato" data-etiqueta="Palabras">{{ p.datos?.palabras ?? '—' }}</td>
                    <td class="chico dato" data-etiqueta="Meta">{{ p.datos ? (p.datos.meta_description ? 'Sí' : 'Falta') : '—' }}</td>
                    <td class="chico dato tema" data-etiqueta="Tema">
                      <span v-if="p.temas?.fuera_del_sector" class="chip" title="No menciona ninguna palabra de tu rubro (Ajustes del rubro, en «Sitios»): no se mandó a la IA">Fuera del sector</span>
                      <template v-else-if="p.temas">
                        <span class="chip">{{ p.temas.tipo_pagina.charAt(0) + p.temas.tipo_pagina.slice(1).toLowerCase() }}</span> {{ p.temas.tema }}
                      </template>
                      <span v-else class="tenue">—</span>
                    </td>
                    <td class="estado">
                      <span class="chip" :class="ESTADO_PAGINA[p.estado].chip" :title="p.motivo ?? ''">{{ ESTADO_PAGINA[p.estado].texto }}</span>
                    </td>
                  </tr>
                  <tr v-if="abierta === p.url" class="fila-detalle">
                    <td colspan="7">
                      <dl class="ficha">
                        <div><dt>URL</dt><dd><a :href="p.url" target="_blank" rel="noopener noreferrer">{{ p.url }} <Icono nombre="externo" /></a></dd></div>
                        <div v-if="p.motivo"><dt>Motivo</dt><dd>{{ p.motivo }}</dd></div>
                        <div v-if="p.datos?.meta_description"><dt>Meta description</dt><dd>{{ p.datos.meta_description }}</dd></div>
                        <div v-if="p.datos?.h2.length"><dt>H2</dt><dd><ul><li v-for="h in p.datos.h2" :key="h">{{ h }}</li></ul></dd></div>
                        <div v-if="p.temas?.consultas.length"><dt>Búsquedas que toca (IA)</dt><dd><span v-for="c in p.temas.consultas" :key="c" class="chip chip-cian">{{ c }}</span></dd></div>
                        <div v-if="p.temas"><dt>Relevancia para {{ miSitio }}</dt><dd>{{ p.temas.relevancia }} / 100 · confianza {{ p.temas.confianza.toLowerCase() }}</dd></div>
                        <div v-if="p.temas?.evidencia.length"><dt>Evidencia</dt><dd><q v-for="e in p.temas.evidencia" :key="e">{{ e }}</q></dd></div>
                        <div v-if="p.sitemap"><dt>Sale de</dt><dd class="tenue">{{ p.sitemap }}<template v-if="p.lastmod"> · modificada {{ p.lastmod.slice(0, 10) }}</template></dd></div>
                      </dl>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
          <div v-if="paginasFiltradas.length > pVisibles" class="fila mas">
            <button class="boton" type="button" @click="pVisibles += 100">Ver {{ Math.min(100, paginasFiltradas.length - pVisibles) }} más</button>
          </div>
        </template>
      </template>

      <!-- ── Keywords ── -->
      <template v-else-if="pestana === 'keywords'">
        <div class="aviso aviso-info" role="note">
          <Icono nombre="info" />
          <div class="aviso-cuerpo">
            <strong>Son hipótesis.</strong> Cada keyword sale del contenido público de un competidor (evidencia «tema observado»).
            Todavía no se comprueba si ese competidor aparece en Google por ella, ni su volumen de búsqueda: es la siguiente fase del plan.
          </div>
        </div>

        <PanelSearchConsole />

        <InformesGuardados modulo="PLAN_SEO_KEYWORDS" :version="keywords.length" />

        <p v-if="cargandoKeywords" class="cargando suave">Cargando keywords…</p>
        <div v-else-if="!keywords.length" class="vacio">
          <template v-if="competidoresConTemas && propioListo">
            <p>Los temas ya están: falta juntarlos en keywords. «Extraer temas» y «Generar keywords» son pasos distintos.</p>
            <button class="boton boton-primario" type="button" :disabled="!!activa || ocupado" @click="generarKeywords">
              <Icono nombre="chispa" /> Generar keywords
            </button>
          </template>
          <p v-else>Aún no hay keywords. En «Sitios»: inventario de {{ miSitio }} y de al menos un competidor, sus temas y «Generar keywords».</p>
        </div>
        <template v-else>
          <div class="fila filtros">
            <div class="campo">
              <label for="k-intencion">Intención</label>
              <select id="k-intencion" v-model="kIntencion">
                <option value="">Todas</option>
                <option v-for="(t, k) in INTENCION" :key="k" :value="k">{{ t }}</option>
              </select>
            </div>
            <div class="campo">
              <label for="k-cobertura">Cobertura en {{ miSitio }}</label>
              <select id="k-cobertura" v-model="kCobertura">
                <option value="">Todas</option>
                <option v-for="(c, k) in COBERTURA" :key="k" :value="k">{{ c.texto }}</option>
              </select>
            </div>
            <div class="campo">
              <label for="k-sitio">Competidor</label>
              <select id="k-sitio" v-model="kSitio">
                <option value="">Todos</option>
                <option v-for="s in sitiosOrigen" :key="s" :value="s">{{ s }}</option>
              </select>
            </div>
            <div class="campo crece">
              <label for="k-texto">Buscar</label>
              <input id="k-texto" v-model="kTexto" type="search" placeholder="Keyword o grupo" />
            </div>
            <button class="boton" type="button" :disabled="!keywordsFiltradas.length" @click="exportar"><Icono nombre="bajar" /> CSV</button>
          </div>
          <p class="tenue chico">{{ keywordsFiltradas.length }} keywords en {{ gruposVisibles }} grupos · primero las que {{ miSitio }} no cubre</p>

          <div class="tabla-envoltura">
            <table class="tabla">
              <thead>
                <tr><th>Keyword</th><th>Grupo</th><th>Intención</th><th class="num">Relevancia</th><th>Cobertura en {{ miSitio }}</th><th>De dónde sale</th><th>Artículo</th></tr>
              </thead>
              <tbody>
                <tr v-for="k in keywordsFiltradas" :key="k.keyword">
                  <td><strong>{{ k.keyword }}</strong></td>
                  <td class="chico">{{ k.grupo }}<small v-if="k.canonica && k.canonica !== k.keyword" class="tenue block">principal: {{ k.canonica }}</small></td>
                  <td><span class="chip" :title="k.motivo ?? ''">{{ k.intencion ? INTENCION[k.intencion] : '—' }}</span></td>
                  <td class="num">{{ k.relevancia ?? '—' }}</td>
                  <td class="chico">
                    <template v-if="k.cobertura">
                      <span class="chip" :class="COBERTURA[k.cobertura].chip" :title="COBERTURA[k.cobertura].ayuda">{{ COBERTURA[k.cobertura].texto }}</span>
                      <a v-if="k.urlPropia" :href="k.urlPropia" target="_blank" rel="noopener noreferrer" class="block">{{ ruta(k.urlPropia) }}</a>
                      <small v-if="k.motivoCobertura" class="tenue block">{{ k.motivoCobertura }}</small>
                    </template>
                    <span v-else class="tenue" title="Solo se evalúa en las informacionales">No evaluada</span>
                  </td>
                  <td class="chico">
                    <details>
                      <summary>{{ [...new Set(k.origenes.map((o) => o.sitio))].join(', ') }} · {{ k.origenes.length }} {{ k.origenes.length === 1 ? 'página' : 'páginas' }}</summary>
                      <ul>
                        <li v-for="o in k.origenes" :key="o.url"><a :href="o.url" target="_blank" rel="noopener noreferrer">{{ ruta(o.url) }}</a></li>
                      </ul>
                    </details>
                  </td>
                  <td class="chico">
                    <RouterLink v-if="k.grupo && articuloPorGrupo.get(k.grupo)" :to="`/seo/articulos/${articuloPorGrupo.get(k.grupo)!.codigo}`" class="sin-salto">
                      Ver artículo
                    </RouterLink>
                    <button
                      v-else-if="k.grupo"
                      class="boton boton-chico sin-salto"
                      type="button"
                      :disabled="!!activa || ocupado"
                      :title="k.cobertura === 'YA_CUBIERTA' ? `${miSitio} ya responde esta búsqueda` : 'Un borrador para tu web'"
                      @click="redactarArticulo(k)"
                    >
                      <Icono nombre="lapiz" /> Redactar
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </template>

      <!-- ── Artículos ── -->
      <template v-else>
        <section class="panel wp">
          <div class="fila rubro-cabeza">
            <h2>Conexión con WordPress</h2>
            <span v-if="wp" class="chip" :class="wp.completo ? 'chip-lima' : 'chip-ambar'">{{ wp.completo ? 'Configurada' : 'Sin configurar' }}</span>
            <button v-if="wp?.completo" class="boton boton-chico boton-ajustes" type="button" :disabled="ocupado" @click="probarWordpress">
              <Icono nombre="servidor" /> Probar conexión
            </button>
          </div>
          <template v-if="wp?.completo">
            <p class="chico">Los artículos se envían a <strong>{{ wp.sitio }}</strong> como el usuario <strong>{{ wp.usuario }}</strong>.</p>
            <p v-if="wpPrueba" class="chico" :class="wpPrueba.puede_crear ? '' : 'rojo'">
              <Icono :nombre="wpPrueba.puede_crear ? 'ok' : 'x'" /> Conectado como {{ wpPrueba.usuario }}:
              {{ wpPrueba.puede_crear ? 'puede crear entradas' : 'no puede crear entradas (necesita rol Autor, Editor o Administrador)' }}
              <template v-if="wpPrueba.puede_crear"> y {{ wpPrueba.puede_publicar ? 'publicarlas' : 'no publicarlas (solo borradores)' }}</template>.
              <template v-if="wpPrueba.puede_crear && !wpPrueba.puede_subir"> No puede subir imágenes: los artículos irían sin imagen destacada.</template>
            </p>
          </template>
          <template v-else-if="wp">
            <p class="chico">Para enviar los artículos a tu web hace falta una «contraseña de aplicación» de WordPress (no es tu contraseña de acceso):</p>
            <ol class="pasos chico">
              <li>En el escritorio de WordPress: <strong>Usuarios → Perfil</strong>, sección <strong>Contraseñas de aplicación</strong>.</li>
              <li>Escribe un nombre («Radar») y pulsa <strong>Añadir nueva contraseña de aplicación</strong>. Cópiala: solo se muestra una vez.</li>
              <li>
                En <span class="mono">03_worker/.env</span> completa <span class="mono">WP_URL</span> (la dirección de tu web, con https),
                <span class="mono">WP_USUARIO</span> y <span class="mono">WP_CLAVE_APLICACION</span>. No la pegues en ningún chat.
              </li>
              <li>Reinicia el Radar con <span class="mono">iniciar.bat</span> y pulsa «Probar conexión».</li>
            </ol>
            <p class="chico tenue">Si la sección no aparece en tu perfil, la web no usa https o un plugin de seguridad la desactivó.</p>
          </template>
        </section>

        <PanelAutomatico :hay-tarea="!!activa" :articulos="articulos" @lanzada="cargar().catch(() => {})" />

        <p v-if="!articulos.length" class="vacio">
          Aún no hay artículos. En «Keywords», pulsa «Redactar» en una búsqueda que {{ miSitio }} no cubre.
        </p>
        <div v-else class="tabla-envoltura">
          <table class="tabla">
            <thead>
              <tr>
                <th>Artículo</th><th>Estado</th><th>Por completar</th><th>WordPress</th><th>Modificado</th>
                <th v-if="auth.esAdmin"><span class="oculto-visual">Acciones</span></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="a in articulos" :key="a.codigo">
                <td>
                  <RouterLink :to="`/seo/articulos/${a.codigo}`"><strong>{{ a.titulo || a.keyword }}</strong></RouterLink>
                  <small class="tenue block">{{ a.keyword }}</small>
                </td>
                <td><span class="chip" :class="estadoArticulo(a).chip">{{ estadoArticulo(a).texto }}</span></td>
                <td class="num">{{ a.contenido ? faltan(a) || '—' : '' }}</td>
                <td class="chico">
                  <a v-if="a.wpEnlace" :href="a.wpEnlace" target="_blank" rel="noopener noreferrer">{{ a.wpEstado === 'publish' ? 'Ver en la web' : 'Vista previa' }}</a>
                  <span v-else class="tenue">—</span>
                </td>
                <td class="chico tenue">{{ fechaHora(a.modificado) }}</td>
                <td v-if="auth.esAdmin">
                  <button
                    class="boton boton-chico boton-fantasma"
                    type="button"
                    :disabled="ocupado"
                    :aria-label="`Borrar «${a.titulo || a.keyword}»`"
                    title="Borrar artículo"
                    @click="borrarArticulo(a)"
                  ><Icono nombre="basura" /></button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </template>
  </div>
</template>

<style scoped>
.tarea {
  margin-bottom: 16px;
}
.tarea-cabeza {
  align-items: center;
  margin-bottom: 6px;
}
.tarea-cabeza button {
  margin-left: auto;
}
.tarea .barra {
  margin-top: 10px;
}
.acciones-pausa {
  margin-top: 8px;
}
/* Mismas pestañas que KeyWords Explorer (su estilo es local a esa vista). */
.pestanas {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--borde);
  margin: 16px 0;
}
.pestanas button {
  background: none;
  border: 0;
  border-bottom: 2px solid transparent;
  padding: 9px 14px;
  color: var(--texto-suave);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
  margin-bottom: -1px;
}
.pestanas button:hover {
  color: var(--texto);
}
.pestanas button.activa {
  color: var(--cian);
  border-bottom-color: var(--cian);
}
.pasos {
  margin: 0 0 16px 20px;
  display: grid;
  gap: 4px;
}
.sitios {
  margin-bottom: 16px;
}
.sitio {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sitio-cabeza {
  align-items: center;
  justify-content: space-between;
}
.sitio-cabeza h2 {
  font-size: 1.1rem;
}
.hosts {
  overflow-wrap: anywhere;
}
.cifras {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.cifras div {
  display: flex;
  flex-direction: column;
}
.cifras dt {
  font-size: 0.75rem;
  color: var(--texto-tenue);
}
.cifras dd {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 600;
}
.cifras small {
  font-size: 0.75rem;
  font-weight: 400;
}
.avisos-sitio {
  list-style: none;
  display: grid;
  gap: 4px;
  color: var(--texto-suave);
}
.avisos-sitio svg,
.requisitos svg {
  width: 13px;
  height: 13px;
  vertical-align: -2px;
}
.detalle summary {
  cursor: pointer;
  color: var(--texto-suave);
}
.detalle ul {
  margin: 6px 0 0 16px;
  display: grid;
  gap: 3px;
}
.mono {
  font-family: var(--mono);
  font-size: 0.8rem;
  overflow-wrap: anywhere;
}
.rojo {
  color: var(--rojo);
}
.maximo {
  max-width: 260px;
}
.boton-ajustes {
  margin-left: auto;
}
.rubro,
.wp {
  margin-bottom: 16px;
  display: grid;
  gap: 8px;
}
.rubro-cabeza {
  align-items: center;
}
.rubro-cabeza h2 {
  font-size: 1.1rem;
}
.rubro-cabeza svg,
.wp svg {
  width: 14px;
  height: 14px;
  vertical-align: -2px;
}
.palabras {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}
.sets {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 8px;
}
.set {
  display: grid;
  gap: 2px;
  text-align: left;
  padding: 8px 10px;
  border: 1px solid var(--borde-fuerte);
  border-radius: 10px;
  background: var(--panel-2);
  color: var(--texto);
  font: inherit;
  cursor: pointer;
}
.set.activo {
  border-color: rgba(34, 211, 238, 0.6);
  background: var(--cian-fondo);
}
.set.parcial {
  border-style: dashed;
  border-color: rgba(34, 211, 238, 0.6);
}
.set .muestra {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.campo .fila input {
  flex: 1;
  min-width: 200px;
}
.palabras .quitar {
  border: 0;
  background: none;
  padding: 0 0 0 2px;
  color: inherit;
  font: inherit;
  cursor: pointer;
}
.palabras .quitar:hover {
  color: var(--rojo);
}
.sin-salto {
  white-space: nowrap;
}
.sin-salto svg {
  width: 13px;
  height: 13px;
}
.boton-ajustes[aria-expanded='true'] {
  background: var(--panel-3);
  border-color: var(--borde-fuerte);
}
.ajustes {
  display: grid;
  gap: 10px;
  margin-top: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--borde);
}
.ajustes h2 {
  font-size: 1.1rem;
}
.ajustes textarea {
  font-family: var(--mono);
  font-size: 0.85rem;
  resize: vertical;
}
.ajustes svg {
  width: 14px;
  height: 14px;
}
.sitio-nuevo {
  border-style: dashed;
  justify-content: center;
  align-items: center;
  text-align: center;
  min-height: 160px;
}
.sitio-nuevo .ajustes {
  width: 100%;
  margin-top: 0;
  text-align: left;
}
.sitio-nuevo > .boton svg {
  width: 15px;
  height: 15px;
}
.acciones {
  margin-top: auto;
  padding-top: 6px;
}
.acciones svg,
.generar svg {
  width: 15px;
  height: 15px;
}
.generar {
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.requisitos {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 18px;
  color: var(--texto-tenue);
}
.requisitos .listo {
  color: var(--lima);
}
.filtros {
  align-items: flex-end;
  margin-bottom: 10px;
}
.filtros .campo {
  min-width: 170px;
}
.filtros .crece {
  flex: 1;
}
.celda-url {
  max-width: 380px;
}
.celda-url small,
.block {
  display: block;
}
.enlace-fila {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: 0;
  padding: 0;
  font: inherit;
  color: var(--cian);
  cursor: pointer;
  text-align: left;
  overflow-wrap: anywhere;
}
.enlace-fila svg {
  flex: none;
  width: 13px;
  height: 13px;
}
.fila-detalle td {
  background: var(--panel-2);
}
.ficha {
  display: grid;
  gap: 8px;
}
.ficha > div {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr);
  gap: 12px;
}
.ficha dt {
  color: var(--texto-tenue);
  font-size: 0.8rem;
}
.ficha dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.ficha dd ul {
  margin-left: 16px;
}
.ficha .chip {
  margin: 0 4px 4px 0;
}
.ficha q {
  display: block;
}
.ficha a svg {
  width: 12px;
  height: 12px;
}
.mas {
  justify-content: center;
  margin-top: 12px;
}
details ul {
  margin: 4px 0 0 16px;
}
/* Páginas: la columna de estado se ajusta a su etiqueta. Según el hueco real (no la
   ventana): primero sale el H1 (casi siempre repite el título, que va bajo la URL) y, en
   estrecho, cada página es una ficha: URL y estado arriba, sus datos debajo. */
.envoltura-paginas {
  container-type: inline-size;
}
.paginas .estado {
  width: 1%;
  white-space: nowrap;
}
@container (max-width: 1000px) {
  .paginas .col-h1 {
    display: none;
  }
}
@container (max-width: 640px) {
  .paginas thead {
    display: none;
  }
  .paginas,
  .paginas tbody,
  .paginas .fila-detalle,
  .paginas .fila-detalle td {
    display: block;
  }
  .paginas tbody tr:not(.fila-detalle) {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 4px 14px;
    padding: 12px;
    border-bottom: 1px solid var(--borde);
  }
  .paginas tbody tr:not(.fila-detalle) td {
    padding: 0;
    border: 0;
  }
  .paginas .celda-url {
    flex: 1 1 60%;
    min-width: 0;
    max-width: none;
  }
  .paginas .estado {
    width: auto;
    order: 1; /* al lado de la URL, aunque en la tabla vaya al final */
  }
  /* Corte de línea: los datos siempre debajo de la URL y el estado. */
  .paginas tbody tr:not(.fila-detalle)::after {
    content: '';
    order: 2;
    flex-basis: 100%;
  }
  .paginas .dato {
    order: 3;
    font-size: 0.8rem;
    text-align: left;
  }
  .paginas .dato::before {
    content: attr(data-etiqueta) ': ';
    color: var(--texto-tenue);
  }
  .paginas .tema {
    flex-basis: 100%;
  }
}
@media (max-width: 700px) {
  .cifras {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .ficha > div {
    grid-template-columns: minmax(0, 1fr);
    gap: 2px;
  }
}
</style>
