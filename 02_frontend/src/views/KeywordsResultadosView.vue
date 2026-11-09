<script setup lang="ts">
/**
 * KeyWords Explorer · resultados. Dos pestañas, como en Ahrefs:
 *  - Resumen: la ficha de una keyword (volumen, CPC, competencia, tendencia, país).
 *  - Ideas de keywords: miles de keywords con subpestañas (coincidentes, relacionadas,
 *    preguntas, sugerencias de Google), filtros, términos agrupados, listas y CSV.
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { keywords } from '@/api/radar'
import type { FilaKeyword, Intencion, ListaKeywords, PeticionExplorar, ResumenKeyword, RespuestaBusqueda } from '@/api/tipos'
import { mensajeDe } from '@/api/cliente'
import BuscadorKeywords, { type BusquedaForm } from '@/components/BuscadorKeywords.vue'
import DialogoLista from '@/components/DialogoLista.vue'
import Icono from '@/components/Icono.vue'
import KwGraficos from '@/components/KwGraficos.vue'
import TablaKeywords from '@/components/TablaKeywords.vue'
import { useEstadoKeywords } from '@/composables/estadoKeywords'
import { fechaHora } from '@/composables/formato'
import {
  ETIQUETA_COMPETENCIA, ETIQUETA_INTENCION, aCsv, compacto, descargarCsv, dinero, filtrar, filtrosVacios, hayFiltros, num,
} from '@/composables/keywords'
import { useAvisos } from '@/stores/avisos'

const route = useRoute()
const router = useRouter()
const avisos = useAvisos()
const { estado, cargar } = useEstadoKeywords()

type Subpestana = 'todas' | 'coincidentes' | 'relacionadas' | 'preguntas' | 'sugerencias'

const respuesta = ref<RespuestaBusqueda | null>(null)
const cargando = ref(true)
const error = ref('')
const pestana = ref<'resumen' | 'ideas'>('ideas')
const sub = ref<Subpestana>('todas')
const filtros = reactive(filtrosVacios())
const seleccion = ref<Set<string>>(new Set())
const dialogoLista = ref(false)

const resumen = ref<ResumenKeyword | null>(null)
const resumenCargando = ref(false)
const resumenError = ref('')
const keywordResumen = ref('')

const r = computed(() => respuesta.value?.resultado ?? null)
const moneda = computed(() => r.value?.moneda ?? null)
const nombrePais = computed(() => (r.value ? (estado.value?.paises[r.value.pais] ?? r.value.pais) : ''))

// ── Carga ─────────────────────────────────────────────────────────────────

function peticion(refrescar = false): PeticionExplorar {
  const q = route.query
  const lista = (v: unknown) => (Array.isArray(v) ? v : v ? [v] : []).map(String)
  return {
    semillas: lista(q.q), url: typeof q.url === 'string' ? q.url : null, pais: typeof q.pais === 'string' ? q.pais : 'PE',
    idioma: typeof q.idioma === 'string' ? q.idioma : 'es', demo: q.demo === '1', refrescar,
  }
}

async function cargarResultados(refrescar = false) {
  cargando.value = true
  error.value = ''
  seleccion.value = new Set()
  try {
    const cod = typeof route.query.cod === 'string' ? route.query.cod : ''
    respuesta.value = cod ? await keywords.busqueda(cod) : await keywords.explorar(peticion(refrescar))
    if (refrescar) avisos.exito('Resultados actualizados con datos de Google.')
    const primera = respuesta.value.resultado.semillas[0]
    keywordResumen.value = primera ?? ''
    pestana.value = primera ? 'resumen' : 'ideas'
    sub.value = 'todas'
    Object.assign(filtros, filtrosVacios())
    if (primera) void cargarResumen(primera)
  } catch (e) {
    respuesta.value = null
    error.value = mensajeDe(e)
  } finally {
    cargando.value = false
  }
}

async function cargarResumen(keyword: string, porPais = false) {
  const rr = r.value
  if (!rr) return
  resumenCargando.value = true
  resumenError.value = ''
  try {
    resumen.value = await keywords.resumen(keyword, rr.pais, rr.idioma, porPais, rr.demo)
  } catch (e) {
    resumen.value = null
    resumenError.value = mensajeDe(e)
  } finally {
    resumenCargando.value = false
  }
}

onMounted(async () => {
  await cargar()
  await cargarResultados()
})
watch(() => route.fullPath, (_n, o) => {
  if (o) void cargarResultados()
})

function nuevaBusqueda(b: BusquedaForm) {
  void router.push({ name: 'keywords-resultados', query: { q: b.semillas, url: b.url ?? undefined, pais: b.pais, idioma: b.idioma, demo: b.demo ? '1' : undefined } })
}

function abrirKeyword(k: string) {
  keywordResumen.value = k
  pestana.value = 'resumen'
  void cargarResumen(k)
  globalThis.scrollTo({ top: 0, behavior: 'smooth' })
}

// ── Ideas ─────────────────────────────────────────────────────────────────

const SUBS: { clave: Subpestana; texto: string; ayuda: string; cumple: (f: FilaKeyword) => boolean }[] = [
  { clave: 'todas', texto: 'Todas', ayuda: 'Todas las ideas que propone Google más sus sugerencias', cumple: () => true },
  { clave: 'coincidentes', texto: 'Términos coincidentes', ayuda: 'Contienen todas las palabras de tu búsqueda', cumple: (f) => f.tipo === 'coincidente' },
  { clave: 'relacionadas', texto: 'Términos relacionados', ayuda: 'Temas cercanos que no contienen tus palabras', cumple: (f) => f.tipo === 'relacionado' },
  { clave: 'preguntas', texto: 'Preguntas', ayuda: 'Qué, cómo, cuál, por qué…', cumple: (f) => f.pregunta },
  { clave: 'sugerencias', texto: 'Sugerencias de búsqueda', ayuda: 'Lo que Google autocompleta al escribir', cumple: (f) => f.sugerencia },
]
const cuenta = (c: Subpestana) => (r.value ? r.value.filas.filter(SUBS.find((s) => s.clave === c)!.cumple).length : 0)
const base = computed(() => (r.value ? r.value.filas.filter(SUBS.find((s) => s.clave === sub.value)!.cumple) : []))
const filtradas = computed(() => filtrar(base.value, filtros))
const volumenFiltrado = computed(() => filtradas.value.reduce((t, f) => t + (f.volumen ?? 0), 0))
const activos = computed(() => hayFiltros(filtros))
const INTENCIONES = Object.keys(ETIQUETA_INTENCION) as Intencion[]

const terminosVisibles = ref(14)
const busquedaTermino = ref('')
const terminos = computed(() => {
  const t = busquedaTermino.value.trim().toLowerCase()
  const todos = r.value?.terminos ?? []
  return t ? todos.filter((x) => x.termino.includes(t)) : todos
})

function alternarIntencion(i: Intencion) {
  const k = filtros.intencion.indexOf(i)
  if (k >= 0) filtros.intencion.splice(k, 1)
  else filtros.intencion.push(i)
}

function elegirTermino(t: string) {
  filtros.termino = filtros.termino === t ? '' : t
}

// ── Selección, listas y exportación ───────────────────────────────────────

const seleccionadas = computed(() => (r.value ? r.value.filas.filter((f) => seleccion.value.has(f.keyword.toLowerCase())) : []))

function seleccionarFiltradas() {
  seleccion.value = new Set(filtradas.value.map((f) => f.keyword.toLowerCase()))
}

async function agregarALista(lista: ListaKeywords) {
  dialogoLista.value = false
  try {
    const x = await keywords.agregar(lista.codigo, seleccionadas.value, r.value?.demo ?? false)
    avisos.exito(`${x.agregadas} ${x.agregadas === 1 ? 'keyword añadida' : 'keywords añadidas'} a «${lista.nombre}»${x.repetidas ? ` (${x.repetidas} ya estaban)` : ''}.`)
    seleccion.value = new Set()
  } catch (e) {
    avisos.error(e, 'No se pudo añadir')
  }
}

function exportar() {
  if (!r.value) return
  const filas = seleccionadas.value.length ? seleccionadas.value : filtradas.value
  const nombre = `keywords-${(r.value.semillas[0] ?? 'url').slice(0, 30)}-${r.value.pais}`
  descargarCsv(nombre, aCsv(filas, nombrePais.value, moneda.value))
  avisos.exito(`${num(filas.length)} keywords exportadas.`)
}

// ── Resumen ───────────────────────────────────────────────────────────────

const ideasPrincipales = computed(() => (r.value ? r.value.filas.filter((f) => f.tipo === 'coincidente' && f.keyword.toLowerCase() !== keywordResumen.value.toLowerCase()).slice(0, 8) : []))
const preguntasPrincipales = computed(() => (r.value ? r.value.filas.filter((f) => f.pregunta).slice(0, 8) : []))
const maxPais = computed(() => Math.max(1, ...(resumen.value?.por_pais ?? []).map((p) => p.volumen ?? 0)))
const titulo = computed(() => r.value?.semillas.join(', ') || r.value?.url || '')

function recomendacion(rs: ResumenKeyword): string {
  if (!rs.volumen) return 'Google no tiene datos de volumen para esta keyword en este país.'
  const partes: string[] = []
  if (rs.tendencia_pct != null && Math.abs(rs.tendencia_pct) >= 10) partes.push(rs.tendencia_pct > 0 ? `viene creciendo (${rs.tendencia_pct} %)` : `viene cayendo (${rs.tendencia_pct} %)`)
  if (rs.mes_pico) partes.push(`su pico es en ${rs.mes_pico}`)
  return partes.length ? `Esta keyword ${partes.join(' y ')}.` : 'Su volumen se mantiene estable durante el año.'
}
</script>

<template>
  <div class="pagina">
    <div class="pagina-cabecera">
      <div>
        <RouterLink to="/keywords" class="chico volver"><Icono nombre="volver" /> KeyWords Explorer</RouterLink>
        <h1 v-if="r">{{ titulo }}</h1>
        <h1 v-else>KeyWords Explorer</h1>
        <p v-if="r" class="fila">
          <span class="chip">{{ nombrePais }}</span>
          <span class="chip">{{ estado?.idiomas[r.idioma] ?? r.idioma }}</span>
          <span v-if="r.demo" class="chip chip-ambar">datos de demostración</span>
          <span class="tenue chico num">{{ num(r.totales.keywords) }} keywords · {{ num(r.totales.volumen) }} búsquedas/mes en total</span>
        </p>
      </div>
      <div v-if="r" class="fila">
        <button class="boton" type="button" :disabled="cargando" title="Vuelve a pedir los datos a Google" @click="cargarResultados(true)"><Icono nombre="reintentar" /> Actualizar</button>
      </div>
    </div>

    <section class="panel buscar"><BuscadorKeywords compacto :ocupado="cargando" :inicial="r ? { semillas: r.semillas, url: r.url, pais: r.pais, idioma: r.idioma, demo: r.demo } : undefined" @buscar="nuevaBusqueda" /></section>

    <p v-if="cargando" class="cargando suave" role="status">Consultando… la primera vez puede tardar unos segundos mientras se piden las ideas a Google.</p>
    <div v-else-if="error" class="aviso aviso-error" role="alert"><Icono nombre="error" /><div class="aviso-cuerpo">{{ error }}</div></div>

    <template v-else-if="r && respuesta">
      <div v-if="r.demo" class="aviso aviso-ambar" role="status">
        <Icono nombre="alerta" />
        <div class="aviso-cuerpo"><strong>Datos de demostración.</strong> Los números son inventados para que veas cómo funciona. Conecta Google Ads (en el inicio de KeyWords Explorer) para volúmenes reales.</div>
      </div>
      <div v-if="r.volumen_agrupado" class="aviso aviso-info" role="status">
        <Icono nombre="info" />
        <div class="aviso-cuerpo">Google está devolviendo volúmenes <strong>agrupados</strong> (10, 100, 1.000…). Pasa en cuentas sin inversión reciente en anuncios: sirven para comparar órdenes de magnitud, no para cifras exactas.</div>
      </div>
      <p v-if="respuesta.desdeCache" class="tenue chico">Resultado guardado el {{ fechaHora(respuesta.busqueda.fecha) }} (los volúmenes de Google son mensuales). Pulsa «Actualizar» para volver a consultarlo.</p>

      <div class="pestanas" role="tablist" aria-label="Vista">
        <button role="tab" :aria-selected="pestana === 'resumen'" :class="{ activa: pestana === 'resumen' }" type="button" :disabled="!r.semillas.length && !keywordResumen" @click="pestana = 'resumen'; if (!resumen && keywordResumen) cargarResumen(keywordResumen)">Resumen</button>
        <button role="tab" :aria-selected="pestana === 'ideas'" :class="{ activa: pestana === 'ideas' }" type="button" @click="pestana = 'ideas'">Ideas de keywords <span class="tenue num">{{ num(r.totales.keywords) }}</span></button>
      </div>

      <!-- ───────── Resumen ───────── -->
      <section v-if="pestana === 'resumen'" class="pila" role="tabpanel">
        <p v-if="!keywordResumen" class="vacio">Esta búsqueda fue por URL: elige una keyword de la tabla para ver su resumen.</p>
        <p v-else-if="resumenCargando" class="cargando suave">Cargando el resumen de «{{ keywordResumen }}»…</p>
        <div v-else-if="resumenError" class="aviso aviso-error" role="alert"><Icono nombre="error" /><div class="aviso-cuerpo">{{ resumenError }}</div></div>

        <template v-else-if="resumen">
          <h2 class="kw-titulo">{{ resumen.keyword }}</h2>
          <div class="tarjetas">
            <div class="panel tarjeta">
              <span class="etiqueta">Volumen mensual</span>
              <strong class="gran num">{{ compacto(resumen.volumen) }}</strong>
              <span class="tenue chico">búsquedas en {{ nombrePais }}</span>
            </div>
            <div class="panel tarjeta">
              <span class="etiqueta">CPC</span>
              <strong class="gran num">{{ dinero(resumen.cpc, resumen.moneda) }}</strong>
              <span class="tenue chico num">de {{ dinero(resumen.cpc_bajo, resumen.moneda) }} a {{ dinero(resumen.cpc_alto, resumen.moneda) }}</span>
            </div>
            <div class="panel tarjeta">
              <span class="etiqueta" title="Cuánta competencia hay entre anunciantes por esta keyword. No es dificultad orgánica (KD).">Competencia de anuncios</span>
              <strong class="gran">{{ resumen.competencia ? ETIQUETA_COMPETENCIA[resumen.competencia] : '—' }}</strong>
              <span class="tenue chico num">índice {{ resumen.competencia_idx ?? '—' }} de 100</span>
            </div>
            <div class="panel tarjeta">
              <span class="etiqueta">Tendencia</span>
              <strong class="gran num" :class="{ sube: (resumen.tendencia_pct ?? 0) > 0, baja: (resumen.tendencia_pct ?? 0) < 0 }">{{ resumen.tendencia_pct == null ? '—' : `${resumen.tendencia_pct > 0 ? '+' : ''}${resumen.tendencia_pct} %` }}</strong>
              <span class="tenue chico">últimos 6 meses vs. 6 anteriores</span>
            </div>
          </div>

          <p class="suave">{{ recomendacion(resumen) }}</p>

          <section class="panel">
            <div class="panel-titulo"><h3>Búsquedas por mes</h3><span v-if="resumen.mes_pico" class="tenue chico">pico en {{ resumen.mes_pico }}</span></div>
            <KwGraficos modo="barras" :serie="resumen.tendencia" :meses="resumen.meses" />
          </section>

          <div class="rejilla rejilla-2">
            <section class="panel">
              <h3>Intención de búsqueda <span class="tenue chico">(estimada)</span></h3>
              <div class="fila chips-int">
                <span v-for="i in resumen.intencion" :key="i" class="chip chip-cian" :title="ETIQUETA_INTENCION[i].ayuda">{{ ETIQUETA_INTENCION[i].nombre }}</span>
                <span v-if="!resumen.intencion.length" class="tenue chico">Sin pistas claras en el texto de la keyword.</span>
                <span v-if="resumen.pregunta" class="chip">Es una pregunta</span>
              </div>
              <template v-if="resumen.variaciones.length">
                <h3 style="margin-top: 14px">Variaciones que Google agrupa</h3>
                <div class="fila"><span v-for="v in resumen.variaciones" :key="v" class="chip">{{ v }}</span></div>
              </template>
            </section>

            <section class="panel">
              <div class="panel-titulo">
                <h3>Volumen por país</h3>
                <button v-if="!resumen.por_pais" class="boton boton-chico" type="button" @click="cargarResumen(resumen.keyword, true)">Calcular</button>
              </div>
              <p v-if="!resumen.por_pais" class="tenue chico">Pide el volumen en 8 países (una consulta por país).</p>
              <ul v-else class="lista-plana paises">
                <li v-for="p in resumen.por_pais" :key="p.pais">
                  <span class="nombre">{{ p.nombre }}</span>
                  <span class="pista"><span class="relleno" :style="{ width: ((p.volumen ?? 0) / maxPais) * 100 + '%' }" /></span>
                  <span class="num">{{ num(p.volumen) }}</span>
                </li>
              </ul>
            </section>
          </div>

          <div v-if="ideasPrincipales.length || preguntasPrincipales.length" class="rejilla rejilla-2">
            <section v-if="ideasPrincipales.length" class="panel">
              <div class="panel-titulo"><h3>Ideas con esta keyword</h3><button class="boton boton-chico boton-fantasma" type="button" @click="pestana = 'ideas'; sub = 'coincidentes'">Ver todas</button></div>
              <ul class="lista-plana top"><li v-for="f in ideasPrincipales" :key="f.keyword"><button type="button" class="enlace-kw" @click="abrirKeyword(f.keyword)">{{ f.keyword }}</button><span class="num tenue">{{ num(f.volumen) }}</span></li></ul>
            </section>
            <section v-if="preguntasPrincipales.length" class="panel">
              <div class="panel-titulo"><h3>Preguntas</h3><button class="boton boton-chico boton-fantasma" type="button" @click="pestana = 'ideas'; sub = 'preguntas'">Ver todas</button></div>
              <ul class="lista-plana top"><li v-for="f in preguntasPrincipales" :key="f.keyword"><button type="button" class="enlace-kw" @click="abrirKeyword(f.keyword)">{{ f.keyword }}</button><span class="num tenue">{{ num(f.volumen) }}</span></li></ul>
            </section>
          </div>

          <p class="tenue chico nota-limites">
            Keyword Planner no entrega la dificultad orgánica (KD), los clics, la SERP ni el potencial de tráfico, así que no se muestran.
          </p>
        </template>
      </section>

      <!-- ───────── Ideas ───────── -->
      <section v-else class="pila" role="tabpanel">
        <div class="subpestanas" role="tablist" aria-label="Tipo de idea">
          <button v-for="s in SUBS" :key="s.clave" role="tab" :aria-selected="sub === s.clave" :class="{ activa: sub === s.clave }" type="button" :title="s.ayuda" @click="sub = s.clave; seleccion = new Set()">
            {{ s.texto }} <span class="num tenue">{{ num(cuenta(s.clave)) }}</span>
          </button>
        </div>

        <div class="ideas">
          <aside class="panel terminos" aria-label="Por término">
            <h3>Por término</h3>
            <p class="tenue chico">Palabras más repetidas entre las ideas. Haz clic para filtrar.</p>
            <input v-model="busquedaTermino" type="search" placeholder="Buscar término" aria-label="Buscar término" />
            <ul class="lista-plana">
              <li v-for="t in terminos.slice(0, busquedaTermino ? 60 : terminosVisibles)" :key="t.termino">
                <button type="button" :class="{ activo: filtros.termino === t.termino }" @click="elegirTermino(t.termino)">
                  <span>{{ t.termino }}</span><span class="num tenue">{{ num(t.keywords) }}</span>
                </button>
              </li>
            </ul>
            <button v-if="!busquedaTermino && terminos.length > terminosVisibles" class="boton boton-chico boton-fantasma" type="button" @click="terminosVisibles += 20">Ver más</button>
          </aside>

          <div class="pila principal">
            <details class="panel filtros" :open="activos">
              <summary>Filtros <span v-if="activos" class="chip chip-cian">activos</span></summary>
              <div class="rejilla-filtros">
                <div class="campo"><label for="f-vmin">Volumen mín.</label><input id="f-vmin" v-model.number="filtros.volMin" type="number" min="0" /></div>
                <div class="campo"><label for="f-vmax">Volumen máx.</label><input id="f-vmax" v-model.number="filtros.volMax" type="number" min="0" /></div>
                <div class="campo"><label for="f-cpc">CPC máx.</label><input id="f-cpc" v-model.number="filtros.cpcMax" type="number" min="0" step="0.1" /></div>
                <div class="campo">
                  <label for="f-comp">Competencia ads</label>
                  <select id="f-comp" v-model="filtros.competencia"><option value="">Cualquiera</option><option value="baja">Baja</option><option value="media">Media</option><option value="alta">Alta</option></select>
                </div>
                <div class="campo"><label for="f-pmin">Palabras mín.</label><input id="f-pmin" v-model.number="filtros.palabrasMin" type="number" min="1" /></div>
                <div class="campo"><label for="f-pmax">Palabras máx.</label><input id="f-pmax" v-model.number="filtros.palabrasMax" type="number" min="1" /></div>
                <div class="campo ancho"><label for="f-inc">Incluir (cualquiera de)</label><input id="f-inc" v-model="filtros.incluir" type="text" placeholder="precio, gratis" /></div>
                <div class="campo ancho"><label for="f-exc">Excluir</label><input id="f-exc" v-model="filtros.excluir" type="text" placeholder="pdf, usado" /></div>
              </div>
              <div class="fila">
                <span class="chico suave">Intención:</span>
                <button v-for="i in INTENCIONES" :key="i" type="button" class="chip chip-boton" :class="{ 'chip-cian': filtros.intencion.includes(i) }" :aria-pressed="filtros.intencion.includes(i)" :title="ETIQUETA_INTENCION[i].ayuda" @click="alternarIntencion(i)">{{ ETIQUETA_INTENCION[i].nombre }}</button>
                <label class="casilla chico"><input v-model="filtros.soloConVolumen" type="checkbox" /> solo con volumen</label>
                <button v-if="activos" class="boton boton-chico boton-fantasma" type="button" @click="Object.assign(filtros, filtrosVacios())">Limpiar filtros</button>
              </div>
            </details>

            <div class="fila herramientas">
              <span class="chico num"><strong>{{ num(filtradas.length) }}</strong> keywords · <strong>{{ num(volumenFiltrado) }}</strong> búsquedas/mes<template v-if="filtros.termino"> · término «{{ filtros.termino }}»</template></span>
              <span class="espaciador" />
              <button v-if="filtradas.length > 1" class="boton boton-chico boton-fantasma" type="button" @click="seleccionarFiltradas">Seleccionar las {{ num(filtradas.length) }}</button>
              <button class="boton boton-chico" type="button" :disabled="!seleccionadas.length" @click="dialogoLista = true"><Icono nombre="mas" /> Añadir a lista{{ seleccionadas.length ? ` (${seleccionadas.length})` : '' }}</button>
              <button class="boton boton-chico" type="button" :disabled="!filtradas.length" @click="exportar"><Icono nombre="bajar" /> Exportar CSV{{ seleccionadas.length ? ` (${seleccionadas.length})` : '' }}</button>
            </div>

            <section class="panel"><TablaKeywords v-model:seleccion="seleccion" :filas="filtradas" :moneda="moneda" @abrir="abrirKeyword" /></section>
            <p class="tenue chico">I/C/T/N = intención estimada (informacional, comercial, transaccional, navegacional) · ? = pregunta · G = aparece en el autocompletado de Google.</p>
          </div>
        </div>
      </section>

      <DialogoLista :abierto="dialogoLista" :cantidad="seleccionadas.length" :pais="r.pais" :idioma="r.idioma" :demo="r.demo" @cerrar="dialogoLista = false" @elegida="agregarALista" />
    </template>
  </div>
</template>

<style scoped>
.volver {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 6px;
}
.volver svg {
  width: 14px;
  height: 14px;
}
.buscar {
  margin-bottom: 16px;
}
.panel + .panel {
  margin-top: 0;
}
.pestanas,
.subpestanas {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--borde);
  margin: 16px 0;
}
.subpestanas {
  margin-top: 0;
}
.pestanas button,
.subpestanas button {
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
.pestanas button:hover:not(:disabled),
.subpestanas button:hover {
  color: var(--texto);
}
.pestanas button.activa,
.subpestanas button.activa {
  color: var(--cian);
  border-bottom-color: var(--cian);
}
.pestanas button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.kw-titulo {
  font-size: 1.4rem;
}
.tarjetas {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}
@media (max-width: 900px) {
  .tarjetas {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
.tarjeta {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.tarjeta .etiqueta {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--texto-suave);
}
.gran {
  font-size: 1.9rem;
  line-height: 1.15;
  color: var(--cian);
}
.gran.sube {
  color: var(--lima);
}
.gran.baja {
  color: var(--rojo);
}
.chips-int {
  margin-top: 8px;
}
.paises {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.paises li {
  display: grid;
  grid-template-columns: 130px 1fr 70px;
  gap: 10px;
  align-items: center;
  font-size: 0.9rem;
}
.paises .num {
  text-align: right;
}
.pista {
  height: 8px;
  background: var(--panel-3);
  border-radius: 4px;
  overflow: hidden;
}
.relleno {
  display: block;
  height: 100%;
  background: var(--cian);
}
.top {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.top li {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}
.enlace-kw {
  background: none;
  border: 0;
  padding: 0;
  font: inherit;
  color: var(--texto);
  text-align: left;
  cursor: pointer;
}
.enlace-kw:hover {
  color: var(--cian);
  text-decoration: underline;
}
.nota-limites {
  margin-top: 4px;
}
.ideas {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
@media (max-width: 960px) {
  .ideas {
    grid-template-columns: minmax(0, 1fr);
  }
}
.terminos {
  display: flex;
  flex-direction: column;
  gap: 8px;
  position: sticky;
  top: 16px;
  max-height: calc(100vh - 32px);
  overflow: auto;
}
@media (max-width: 960px) {
  .terminos {
    position: static;
    max-height: 320px;
  }
}
.terminos li button {
  width: 100%;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  background: none;
  border: 0;
  border-radius: var(--radio-chico);
  padding: 5px 8px;
  color: var(--texto);
  font: inherit;
  cursor: pointer;
  text-align: left;
}
.terminos li button:hover {
  background: var(--panel-2);
}
.terminos li button.activo {
  background: var(--cian-fondo);
  color: var(--cian);
}
.filtros summary {
  cursor: pointer;
  font-weight: 600;
  display: flex;
  gap: 8px;
  align-items: center;
}
.rejilla-filtros {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
  margin: 14px 0;
}
.rejilla-filtros .ancho {
  grid-column: span 2;
}
.chip-boton {
  cursor: pointer;
  border: 1px solid transparent;
  font: inherit;
  font-size: 0.8rem;
}
.herramientas {
  gap: 8px;
}
</style>
