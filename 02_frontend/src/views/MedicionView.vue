<script setup lang="ts">
/**
 * Medición: qué funciona. Rendimiento real de los anuncios propios de Meta (gasto, leads,
 * conversaciones de WhatsApp y su costo) frente al periodo anterior, alertas calculadas sin
 * IA, informe con IA que queda guardado, la web en GA4 y el constructor de enlaces con UTM.
 * Leads y conversaciones no se suman: cada campaña cuenta el resultado que produce.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { medicion } from '@/api/radar'
import type { AlertaMedicion, CampanaMeta, EstadoMedicion, InformeGa4, KpisMeta, ResumenIa, ResumenMedicion, TipoCampana } from '@/api/tipos'
import GraficoDiario from '@/components/GraficoDiario.vue'
import ConectarGoogle from '@/components/ConectarGoogle.vue'
import Icono from '@/components/Icono.vue'
import InformesGuardados from '@/components/InformesGuardados.vue'
import { confirmar } from '@/composables/confirmar'
import { fechaHora } from '@/composables/formato'
import { agregarUtm, slug } from '@/composables/utm'
import { useAuth } from '@/stores/auth'
import { useAvisos } from '@/stores/avisos'

const avisos = useAvisos()
const auth = useAuth()

const estado = ref<EstadoMedicion | null>(null)
const datos = ref<ResumenMedicion | null>(null)
const cargando = ref(false)
const ia = ref<ResumenIa | null>(null)
const generando = ref(false)
const versionInformes = ref(0)

// ── Periodo ──
const PRESETS = [7, 30, 90]
const dias = ref<number | null>(30)
const desde = ref('')
const hasta = ref('')
const ayer = computed(() => (estado.value ? sumarDias(estado.value.hoy, -1) : ''))

function sumarDias(iso: string, n: number) {
  const d = new Date(`${iso}T12:00:00`)
  d.setDate(d.getDate() + n)
  return d.toISOString().slice(0, 10)
}
function preset(n: number) {
  dias.value = n
  hasta.value = ayer.value
  desde.value = sumarDias(ayer.value, -(n - 1))
}

async function cargarEstado() {
  try {
    estado.value = await medicion.estado()
  } catch (e) {
    avisos.error(e)
  }
}

async function cargar() {
  if (!desde.value || !hasta.value) return
  cargando.value = true
  try {
    datos.value = await medicion.resumen(desde.value, hasta.value)
  } catch (e) {
    avisos.error(e)
  } finally {
    cargando.value = false
  }
  if (estado.value?.ga4.completo) cargarGa4()
}

onMounted(async () => {
  await cargarEstado()
  if (estado.value) {
    preset(30)
    await cargar()
    if (estado.value.sincronizacion?.estado === 'EN_CURSO') vigilar()
  }
})
watch([desde, hasta], () => {
  if (dias.value !== null && (hasta.value !== ayer.value || desde.value !== sumarDias(ayer.value, -(dias.value - 1)))) dias.value = null
})

// ── Sincronización ──
let temporizador: ReturnType<typeof setInterval> | null = null
const sincronizando = computed(() => estado.value?.sincronizacion?.estado === 'EN_CURSO')

function vigilar() {
  if (temporizador) return
  temporizador = setInterval(async () => {
    await cargarEstado()
    const s = estado.value?.sincronizacion
    if (s?.estado !== 'EN_CURSO') {
      clearInterval(temporizador!)
      temporizador = null
      if (s?.estado === 'LISTA') avisos.exito(`Datos de Meta al día: ${s.filas} filas (anuncio y día) del ${s.desde} al ${s.hasta}.`)
      else if (s?.estado === 'ERROR') avisos.error(new Error(s.error ?? 'No se pudieron traer los datos de Meta.'))
      await cargar()
    }
  }, 3000)
}
onBeforeUnmount(() => temporizador && clearInterval(temporizador))

async function sincronizar(desdeFecha?: string) {
  try {
    await medicion.sincronizar(desdeFecha)
    await cargarEstado()
    vigilar()
  } catch (e) {
    avisos.error(e)
  }
}
const historial = ref('')

// ── Formatos ──
const moneda = computed(() => datos.value?.moneda ?? estado.value?.meta.detalle?.moneda ?? 'USD')
const dinero = (n: number | null | undefined) =>
  n == null ? '—' : new Intl.NumberFormat('es-PE', { style: 'currency', currency: moneda.value, maximumFractionDigits: n >= 1000 ? 0 : 2 }).format(n)
const entero = (n: number | null | undefined) => (n == null ? '—' : new Intl.NumberFormat('es-PE').format(n))
const corto = (n: number) => new Intl.NumberFormat('es-PE', { notation: 'compact', maximumFractionDigits: 1 }).format(n)
const porcentaje = (n: number | null | undefined, d = 2) => (n == null ? '—' : `${(n * 100).toFixed(d)} %`)

// ── Indicadores ──
type Clave = keyof KpisMeta
const TILES: { clave: Clave; nombre: string; formato: 'dinero' | 'entero' | 'pct'; bueno: 'sube' | 'baja' | null; ayuda: string }[] = [
  { clave: 'gasto', nombre: 'Gasto', formato: 'dinero', bueno: null, ayuda: 'Todo lo invertido en Meta en el periodo.' },
  { clave: 'leads', nombre: 'Leads', formato: 'entero', bueno: 'sube', ayuda: 'Formularios de Lead Ads enviados.' },
  { clave: 'costoLead', nombre: 'Costo por lead', formato: 'dinero', bueno: 'baja', ayuda: 'Gasto de las campañas de leads ÷ sus leads.' },
  { clave: 'conversaciones', nombre: 'Conversaciones', formato: 'entero', bueno: 'sube', ayuda: 'Chats de WhatsApp o Messenger iniciados desde un anuncio.' },
  { clave: 'costoConversacion', nombre: 'Costo por conversación', formato: 'dinero', bueno: 'baja', ayuda: 'Gasto de las campañas de WhatsApp ÷ sus conversaciones.' },
  { clave: 'ctr', nombre: 'CTR de enlace', formato: 'pct', bueno: 'sube', ayuda: 'Clics en el enlace ÷ impresiones.' },
]
function mostrar(v: unknown, f: 'dinero' | 'entero' | 'pct') {
  const n = v as number | null
  return f === 'dinero' ? dinero(n) : f === 'pct' ? porcentaje(n) : entero(n)
}
function delta(t: (typeof TILES)[number]) {
  const a = datos.value?.kpis[t.clave] as number | null
  const b = datos.value?.kpisAnterior[t.clave] as number | null
  if (a == null || b == null || b === 0) return null
  const c = (a - b) / b
  const bien = t.bueno === null ? null : (c > 0) === (t.bueno === 'sube')
  return { texto: `${c > 0 ? '+' : ''}${(c * 100).toFixed(0)} %`, sube: c > 0, clase: Math.abs(c) < 0.005 || bien === null ? '' : bien ? 'bien' : 'mal' }
}

// ── Campañas ──
const TIPO: Record<TipoCampana, string> = { LEADS: 'Leads', CONVERSACIONES: 'WhatsApp', SIN_RESULTADOS: 'Web, alcance u otro' }
const filtroTipo = ref<'' | TipoCampana>('')
const filtroTexto = ref('')
const orden = ref<'gasto' | 'resultados' | 'costoResultado' | 'cambioCosto'>('gasto')
const campanas = computed(() => {
  const t = filtroTexto.value.trim().toLowerCase()
  const lista = (datos.value?.campanas ?? []).filter((c) => (!filtroTipo.value || c.tipo === filtroTipo.value) && (!t || c.nombre.toLowerCase().includes(t)))
  const k = orden.value
  return [...lista].sort((a, b) => (Number(b[k] ?? -Infinity) - Number(a[k] ?? -Infinity)) * (k === 'costoResultado' ? -1 : 1))
})
const queResultado = (c: { tipo: TipoCampana }) => (c.tipo === 'LEADS' ? 'leads' : c.tipo === 'CONVERSACIONES' ? 'chats' : '')
function claseCambio(c: CampanaMeta) {
  if (c.cambioCosto == null || Math.abs(c.cambioCosto) < 0.05) return 'tenue'
  return c.cambioCosto > 0 ? 'mal' : 'bien'
}

// ── Alertas ──
const NIVEL: Record<AlertaMedicion['nivel'], { chip: string; texto: string; icono: string }> = {
  ALTA: { chip: 'chip-rojo', texto: 'Revisar', icono: 'alerta' },
  MEDIA: { chip: 'chip-ambar', texto: 'Atención', icono: 'alerta' },
  OPORTUNIDAD: { chip: 'chip-lima', texto: 'Oportunidad', icono: 'estrella' },
  INFO: { chip: '', texto: 'Dato', icono: 'info' },
}

const todasAlertas = ref(false)

// ── Informe con IA ──
async function generar() {
  const ok = await confirmar({
    titulo: '¿Generar el informe con IA?',
    mensaje: `Gemini resume el periodo del ${desde.value} al ${hasta.value} con las cifras de esta pantalla. Cuesta menos de un centavo de dólar.`,
    puntos: ['Queda guardado en «Informes guardados» con las cifras y las campañas de ese momento.'],
    aceptar: 'Generar',
  })
  if (!ok.ok) return
  generando.value = true
  try {
    const r = await medicion.informe(desde.value, hasta.value)
    ia.value = r.ia
    versionInformes.value++
    avisos.exito(`Informe ${r.informe.codigo} guardado.`)
  } catch (e) {
    avisos.error(e)
  } finally {
    generando.value = false
  }
}

// ── GA4 ──
const ga4 = ref<InformeGa4 | null>(null)
const ga4Error = ref('')
const propiedades = ref<{ propiedad: string; nombre: string; cuenta: string }[] | null>(null)
async function cargarGa4() {
  ga4Error.value = ''
  try {
    ga4.value = await medicion.ga4(desde.value, hasta.value)
  } catch (e) {
    ga4.value = null
    ga4Error.value = e instanceof Error ? e.message : String(e)
  }
}
const buscandoPropiedades = ref(false)
async function verPropiedades() {
  buscandoPropiedades.value = true
  try {
    propiedades.value = (await medicion.ga4Propiedades()).propiedades
  } catch (e) {
    avisos.error(e)
  } finally {
    buscandoPropiedades.value = false
  }
}
async function usarPropiedad(p: string) {
  try {
    await medicion.elegirPropiedadGa4(p)
    avisos.exito(`GA4 usará la propiedad ${p}.`)
    propiedades.value = null
    await cargarEstado()
    if (estado.value?.ga4.completo) cargarGa4()
  } catch (e) {
    avisos.error(e)
  }
}
/** Al reconectar Google, vuelve a intentar lo que dependía de la conexión. */
async function alConectarGoogle() {
  await cargarEstado()
  if (estado.value?.ga4.completo) cargarGa4()
  else verPropiedades()
}
const totalGa4 = computed(() => (ga4.value?.canales ?? []).reduce((s, c) => s + c.sessions, 0))

// ── Constructor de UTM ──
const utm = ref({ url: 'https://ilcb.edu.pe/', fuente: 'facebook', medio: 'paid_social', campana: '', contenido: '' })
const utmResultado = computed(() => {
  const u = utm.value
  if (!/^https?:\/\/\S+\.\S+/.test(u.url.trim()) || !u.fuente.trim() || !u.medio.trim() || !u.campana.trim()) return ''
  return agregarUtm(u.url.trim(), { fuente: slug(u.fuente), medio: slug(u.medio).replace(/-/g, '_'), campana: slug(u.campana), contenido: slug(u.contenido) })
})
const PARAMETROS_META = 'utm_source=facebook&utm_medium=paid_social&utm_campaign={{campaign.name}}&utm_content={{ad.name}}&utm_term={{adset.name}}'
async function copiar(texto: string, que: string) {
  try {
    await navigator.clipboard.writeText(texto)
    avisos.exito(`${que} copiado.`)
  } catch {
    avisos.error(new Error('No se pudo copiar: selecciónalo y cópialo a mano.'))
  }
}

const SERIES_RESULTADOS = [
  { clave: 'leads', nombre: 'Leads', color: 'var(--serie-leads)' },
  { clave: 'conversaciones', nombre: 'Conversaciones', color: 'var(--serie-conversaciones)' },
]
const SERIE_GASTO = [{ clave: 'gasto', nombre: 'Gasto', color: 'var(--serie-gasto)' }]
</script>

<template>
  <div class="pagina medicion">
    <div class="pagina-cabecera">
      <div>
        <h1>Medición</h1>
        <p>
          Qué funciona: el rendimiento real de los anuncios de Meta, lo que pasa en la web (GA4) y enlaces con UTM para saber de dónde
          vino cada visita.
        </p>
      </div>
    </div>

    <!-- Meta sin conectar -->
    <div v-if="estado && !estado.meta.completo" class="aviso aviso-ambar">
      <Icono nombre="alerta" />
      <div class="aviso-cuerpo">
        <strong>Meta no está conectado.</strong>
        <template v-if="estado.meta.error"> {{ estado.meta.error }}</template>
        <template v-else> Falta en <code>03_worker/.env</code>: {{ estado.meta.faltan.join(', ') }} (el token de lectura de Marketing y la cuenta act_…).</template>
      </div>
    </div>

    <template v-if="estado?.meta.completo">
      <!-- Filtros: una fila arriba de todo -->
      <div class="fila filtros">
        <div class="segmentos" role="group" aria-label="Periodo">
          <button v-for="n in PRESETS" :key="n" type="button" :class="{ activo: dias === n }" :aria-pressed="dias === n" @click="preset(n); cargar()">
            {{ n }} días
          </button>
        </div>
        <label class="chico">Del <input v-model="desde" type="date" :max="hasta" @change="cargar" /></label>
        <label class="chico">al <input v-model="hasta" type="date" :min="desde" :max="estado.hoy" @change="cargar" /></label>
        <span class="espaciador" />
        <span class="chico tenue">
          <template v-if="estado.meta.detalle">{{ estado.meta.detalle.nombre }} · {{ estado.meta.detalle.moneda }}</template>
          <template v-if="estado.datos"> · datos del {{ estado.datos.desde }} al {{ estado.datos.hasta }}</template>
        </span>
        <button class="boton boton-chico" type="button" :disabled="sincronizando" @click="sincronizar()">
          <Icono nombre="reintentar" /> {{ sincronizando ? 'Trayendo de Meta…' : 'Actualizar datos' }}
        </button>
      </div>
      <p v-if="sincronizando" class="chico suave">
        Trayendo de Meta del {{ estado.sincronizacion!.desde }} al {{ estado.sincronizacion!.hasta }} (unos 2 minutos por cada 60 días). Puedes seguir
        usando el Radar.
      </p>
      <p v-else-if="estado.sincronizacion?.estado === 'ERROR'" class="chico rojo">
        La última actualización falló: {{ estado.sincronizacion.error }}
      </p>
      <p v-else-if="estado.sincronizacion?.fin" class="chico tenue">Actualizado {{ fechaHora(estado.sincronizacion.fin) }} · se actualiza solo cada mañana a las 7:20.</p>

      <div v-if="!estado.datos && !sincronizando" class="vacio">
        <p>Aún no hay datos de Meta en el Radar.</p>
        <button class="boton boton-primario" type="button" @click="sincronizar()"><Icono nombre="bajar" /> Traer los últimos 90 días</button>
      </div>

      <div v-if="datos && estado.datos" class="pila" :class="{ recargando: cargando }">
        <!-- Indicadores -->
        <div class="tiles">
          <div v-for="t in TILES" :key="t.clave" class="tile" :title="t.ayuda">
            <span class="tile-nombre">{{ t.nombre }}</span>
            <strong class="tile-valor">{{ mostrar(datos.kpis[t.clave], t.formato) }}</strong>
            <span v-if="delta(t)" class="tile-delta" :class="delta(t)!.clase">
              {{ delta(t)!.sube ? '▲' : '▼' }} {{ delta(t)!.texto }} <span class="tenue">vs. {{ datos.periodo.dias }} días anteriores</span>
            </span>
            <span v-else class="tile-delta tenue">sin periodo anterior</span>
          </div>
        </div>
        <p class="chico tenue">
          Del {{ datos.periodo.desde }} al {{ datos.periodo.hasta }} frente al {{ datos.anterior.desde }} – {{ datos.anterior.hasta }}.
          {{ datos.kpis.campanas }} campañas y {{ datos.kpis.anuncios }} anuncios con gasto.
          <template v-if="datos.kpis.gastoSinResultados > 0">
            {{ dinero(datos.kpis.gastoSinResultados) }} fueron a campañas cuyo resultado no es un lead ni un chat (web, alcance, visualizaciones):
            su efecto se mide en GA4.
          </template>
        </p>

        <!-- Gráficos -->
        <div class="rejilla rejilla-2">
          <section class="panel">
            <GraficoDiario titulo="Gasto por día" :dias="datos.serie" :series="SERIE_GASTO" tipo="columnas" :formato="dinero" :formato-eje="corto" />
          </section>
          <section class="panel">
            <GraficoDiario titulo="Resultados por día" :dias="datos.serie" :series="SERIES_RESULTADOS" tipo="lineas" :formato="entero" :formato-eje="corto" />
          </section>
        </div>

        <!-- Alertas -->
        <section class="panel pila">
          <h2><Icono nombre="alerta" /> Alertas <span class="chico tenue">· últimos 7 días hasta el {{ datos.periodo.hasta }} frente a los 7 anteriores</span></h2>
          <p v-if="!datos.alertas.length" class="chico tenue">Nada fuera de lo normal.</p>
          <ul v-else class="alertas">
            <li v-for="(a, i) in todasAlertas ? datos.alertas : datos.alertas.slice(0, 6)" :key="i">
              <span class="chip" :class="NIVEL[a.nivel].chip"><Icono :nombre="NIVEL[a.nivel].icono" /> {{ NIVEL[a.nivel].texto }}</span>
              <div>
                <strong>{{ a.titulo }}</strong>
                <div class="chico suave">{{ a.detalle }}</div>
              </div>
            </li>
          </ul>
          <button v-if="datos.alertas.length > 6" class="boton boton-chico boton-fantasma a-la-izquierda" type="button" @click="todasAlertas = !todasAlertas">
            {{ todasAlertas ? 'Ver solo las 6 primeras' : `Ver las ${datos.alertas.length}` }}
          </button>
          <p class="chico tenue">Primero lo que más dinero mueve. Se calculan sin IA, con mínimos de volumen (10 resultados, 5000 impresiones) para no alarmar por pocas diferencias.</p>
        </section>

        <!-- Informe con IA -->
        <section class="panel pila">
          <div class="fila entre">
            <h2><Icono nombre="chispa" /> Informe con IA</h2>
            <button class="boton boton-primario boton-chico" type="button" :disabled="generando" @click="generar">
              <Icono nombre="chispa" /> {{ generando ? 'Escribiendo…' : 'Generar informe del periodo' }}
            </button>
          </div>
          <p class="chico tenue">
            Gemini cuenta en lenguaje claro lo que dicen las cifras y las alertas; no inventa números ni promete resultados. Cada informe queda
            guardado.
          </p>
          <div v-if="ia" class="ia">
            <p class="titular">{{ ia.titular }}</p>
            <ul>
              <li v-for="(p, i) in ia.puntos" :key="i">{{ p }}</li>
            </ul>
            <div v-for="(h, i) in ia.hallazgos" :key="`h${i}`" class="hallazgo">
              <strong>{{ h.titulo }}</strong>
              <div class="chico">{{ h.evidencia }}</div>
              <div class="chico suave">Para probar: {{ h.sugerencia }}</div>
            </div>
            <p v-for="(a, i) in ia.advertencias" :key="`a${i}`" class="chico ambar"><Icono nombre="info" /> {{ a }}</p>
          </div>
          <InformesGuardados modulo="MEDICION" :version="versionInformes" />
        </section>

        <!-- Campañas -->
        <section class="panel pila">
          <div class="fila entre">
            <h2>Campañas</h2>
            <div class="fila filtros-tabla">
              <input v-model="filtroTexto" type="search" placeholder="Buscar campaña" aria-label="Buscar campaña" />
              <select v-model="filtroTipo" aria-label="Tipo de resultado">
                <option value="">Todos los resultados</option>
                <option value="LEADS">Leads</option>
                <option value="CONVERSACIONES">WhatsApp</option>
                <option value="SIN_RESULTADOS">Web, alcance u otro</option>
              </select>
              <select v-model="orden" aria-label="Ordenar">
                <option value="gasto">Más gasto</option>
                <option value="resultados">Más resultados</option>
                <option value="costoResultado">Menor costo por resultado</option>
                <option value="cambioCosto">Más se encarece</option>
              </select>
            </div>
          </div>
          <div class="tabla-envoltura">
            <table class="tabla">
              <thead>
                <tr>
                  <th>Campaña</th><th class="num">Gasto</th><th class="num">Resultados</th><th class="num">Costo por resultado</th>
                  <th class="num">vs. anterior</th><th class="num">CTR</th><th class="num">Anuncios</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="c in campanas" :key="c.id">
                  <td>
                    <strong>{{ c.producto ?? c.nombre }}</strong>
                    <small class="tenue block">{{ c.nombre }}</small>
                    <span class="chip">{{ TIPO[c.tipo] }}</span>
                  </td>
                  <td class="num">{{ dinero(c.gasto) }}</td>
                  <td class="num">{{ c.tipo === 'SIN_RESULTADOS' ? '—' : `${entero(c.resultados)} ${queResultado(c)}` }}</td>
                  <td class="num">{{ dinero(c.costoResultado) }}</td>
                  <td class="num" :class="claseCambio(c)">
                    <template v-if="c.cambioCosto != null">{{ c.cambioCosto > 0 ? '▲' : '▼' }} {{ Math.abs(c.cambioCosto * 100).toFixed(0) }} %</template>
                    <template v-else>—</template>
                  </td>
                  <td class="num">{{ porcentaje(c.ctr) }}</td>
                  <td class="num">{{ c.anuncios }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="chico tenue">«vs. anterior»: cómo cambió el costo por resultado; ▲ es que se encareció.</p>
        </section>

        <!-- Anuncios -->
        <details class="panel">
          <summary><strong>Anuncios con más gasto</strong> <span class="chico tenue">· los {{ datos.anuncios.length }} primeros</span></summary>
          <div class="tabla-envoltura">
            <table class="tabla">
              <thead>
                <tr><th>Anuncio</th><th class="num">Gasto</th><th class="num">Resultados</th><th class="num">Costo por resultado</th><th class="num">CTR</th></tr>
              </thead>
              <tbody>
                <tr v-for="a in datos.anuncios" :key="a.id">
                  <td>{{ a.nombre }}<small class="tenue block">{{ a.campana }}</small></td>
                  <td class="num">{{ dinero(a.gasto) }}</td>
                  <td class="num">{{ a.tipo === 'SIN_RESULTADOS' ? '—' : `${entero(a.resultados)} ${queResultado(a)}` }}</td>
                  <td class="num" :class="{ mal: a.tipo !== 'SIN_RESULTADOS' && !a.resultados }">{{ a.tipo === 'SIN_RESULTADOS' ? '—' : dinero(a.costoResultado) }}</td>
                  <td class="num">{{ porcentaje(a.ctr) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </details>
      </div>
    </template>

    <!-- GA4 -->
    <section v-if="estado" class="panel pila">
      <h2><Icono nombre="grafico" /> La web: Google Analytics 4</h2>
      <ConectarGoogle @conectado="alConectarGoogle" />
      <template v-if="!estado.ga4.completo">
        <p class="chico">
          Muestra qué pasa después del clic: visitas, visitas con interacción y eventos clave (formularios) por canal, por campaña UTM y por
          página de entrada. Para conectarlo:
        </p>
        <ol class="chico pasos">
          <li>Conecta Google con el botón de arriba (con tu cuenta de Google del Radar) y deja marcadas todas las casillas.</li>
          <li>Marketing te agrega como <strong>Lector</strong> en la propiedad de GA4 de ilcb.edu.pe, con esa misma cuenta.</li>
          <li>
            En Google Cloud (proyecto «Radar») activa
            <a href="https://console.cloud.google.com/apis/library/analyticsdata.googleapis.com" target="_blank" rel="noopener">Google Analytics Data API</a>
            y
            <a href="https://console.cloud.google.com/apis/library/analyticsadmin.googleapis.com" target="_blank" rel="noopener">Google Analytics Admin API</a>.
          </li>
          <li>
            Elige la propiedad:
            <button class="boton boton-chico" type="button" :disabled="buscandoPropiedades" @click="verPropiedades">
              {{ buscandoPropiedades ? 'Buscando…' : 'Ver las propiedades que ve mi cuenta' }}
            </button>
          </li>
        </ol>
        <ul v-if="propiedades" class="chico propiedades">
          <li v-if="!propiedades.length">Tu cuenta no ve ninguna propiedad de GA4 todavía: falta el paso 2.</li>
          <li v-for="p in propiedades" :key="p.propiedad" class="fila">
            <span><code>{{ p.propiedad }}</code> · {{ p.nombre }} <span class="tenue">({{ p.cuenta }})</span></span>
            <button v-if="auth.esAdmin" class="boton boton-chico" type="button" @click="usarPropiedad(p.propiedad)">Usar esta</button>
          </li>
        </ul>
      </template>
      <template v-else>
        <p v-if="ga4Error" class="chico rojo">{{ ga4Error }}</p>
        <template v-else-if="ga4">
          <p class="chico tenue">Propiedad {{ ga4.propiedad }} · del {{ ga4.desde }} al {{ ga4.hasta }} · {{ entero(totalGa4) }} sesiones.</p>
          <div class="rejilla rejilla-2">
            <div class="tabla-envoltura">
              <table class="tabla">
                <thead><tr><th>Canal</th><th class="num">Sesiones</th><th class="num">Con interacción</th><th class="num">Eventos clave</th></tr></thead>
                <tbody>
                  <tr v-for="c in ga4.canales" :key="c.sessionDefaultChannelGroup">
                    <td>{{ c.sessionDefaultChannelGroup }}</td><td class="num">{{ entero(c.sessions) }}</td>
                    <td class="num">{{ entero(c.engagedSessions) }}</td><td class="num">{{ entero(c.keyEvents) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="tabla-envoltura">
              <table class="tabla">
                <thead><tr><th>Página de entrada</th><th class="num">Sesiones</th><th class="num">Eventos clave</th></tr></thead>
                <tbody>
                  <tr v-for="p in ga4.paginas.slice(0, 12)" :key="p.landingPage">
                    <td class="corta">{{ p.landingPage }}</td><td class="num">{{ entero(p.sessions) }}</td><td class="num">{{ entero(p.keyEvents) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div class="tabla-envoltura">
            <table class="tabla">
              <thead><tr><th>Fuente / medio</th><th>Campaña (UTM)</th><th class="num">Sesiones</th><th class="num">Eventos clave</th></tr></thead>
              <tbody>
                <tr v-for="(c, i) in ga4.campanas.slice(0, 20)" :key="i">
                  <td>{{ c.sessionSource }} / {{ c.sessionMedium }}</td><td>{{ c.sessionCampaignName }}</td>
                  <td class="num">{{ entero(c.sessions) }}</td><td class="num">{{ entero(c.keyEvents) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="ga4.eventos.length" class="chico tenue">Eventos clave: {{ ga4.eventos.map((e) => `${e.eventName} (${entero(e.keyEvents)})`).join(', ') }}.</p>
        </template>
        <p v-else class="chico tenue">Cargando GA4…</p>
      </template>
    </section>

    <!-- UTM -->
    <section class="panel pila">
      <h2><Icono nombre="enlace" /> Enlaces con UTM</h2>
      <p class="chico suave">
        Para que GA4 sepa de qué red, campaña y anuncio vino cada visita. Los posts de Publicaciones ya los llevan solos en los enlaces a
        ilcb.edu.pe (Facebook y LinkedIn).
      </p>
      <div class="formulario-utm">
        <label class="campo ancho"><span>Página de destino</span><input v-model="utm.url" type="url" /></label>
        <label class="campo"><span>Fuente (utm_source)</span><input v-model="utm.fuente" list="fuentes-utm" /></label>
        <label class="campo"><span>Medio (utm_medium)</span><input v-model="utm.medio" list="medios-utm" /></label>
        <label class="campo"><span>Campaña (utm_campaign)</span><input v-model="utm.campana" placeholder="admision-2027-1" /></label>
        <label class="campo"><span>Contenido (utm_content, opcional)</span><input v-model="utm.contenido" placeholder="video-chef" /></label>
        <datalist id="fuentes-utm"><option value="facebook" /><option value="instagram" /><option value="linkedin" /><option value="google" /><option value="tiktok" /><option value="email" /></datalist>
        <datalist id="medios-utm"><option value="paid_social" /><option value="social" /><option value="cpc" /><option value="email" /><option value="qr" /></datalist>
      </div>
      <div v-if="utmResultado" class="fila resultado-utm">
        <code class="crece">{{ utmResultado }}</code>
        <button class="boton boton-chico" type="button" @click="copiar(utmResultado, 'Enlace')"><Icono nombre="copiar" /> Copiar</button>
      </div>
      <p v-else class="chico tenue">Completa la página, la fuente, el medio y la campaña.</p>
      <div class="pila meta-utm">
        <strong class="chico">Para todos los anuncios de Meta a la vez</strong>
        <p class="chico suave">
          En el Administrador de anuncios → anuncio → «Parámetros de URL», pega esto: Meta pone solo el nombre de la campaña, del conjunto y
          del anuncio en cada clic.
        </p>
        <div class="fila resultado-utm">
          <code class="crece">{{ PARAMETROS_META }}</code>
          <button class="boton boton-chico" type="button" @click="copiar(PARAMETROS_META, 'Parámetros')"><Icono nombre="copiar" /> Copiar</button>
        </div>
      </div>
    </section>

    <!-- Historial más largo -->
    <details v-if="estado?.meta.completo" class="panel chico">
      <summary>Traer más historial de Meta</summary>
      <form class="fila" @submit.prevent="sincronizar(historial)">
        <label>Desde <input v-model="historial" type="date" :max="estado.hoy" required /></label>
        <button class="boton boton-chico" type="submit" :disabled="sincronizando">Traer</button>
        <span class="tenue">Hasta 400 días por vez (unos 2 minutos por cada 60 días).</span>
      </form>
    </details>
  </div>
</template>

<style scoped>
.pila {
  display: grid;
  gap: 12px;
}
h2 {
  font-size: 1.05rem;
  margin: 0;
}
h2 svg,
.chip svg,
.boton svg,
.ambar svg {
  width: 14px;
  height: 14px;
  vertical-align: -2px;
}
.filtros {
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.segmentos {
  display: inline-flex;
  border: 1px solid var(--borde-fuerte);
  border-radius: 8px;
  overflow: hidden;
}
.segmentos button {
  background: none;
  border: 0;
  padding: 6px 12px;
  font: inherit;
  font-size: 0.85rem;
  color: var(--texto-suave);
  cursor: pointer;
}
.segmentos button + button {
  border-left: 1px solid var(--borde-fuerte);
}
.segmentos button.activo {
  background: var(--panel-2);
  color: var(--texto);
  font-weight: 700;
}
.espaciador {
  flex: 1;
}
.a-la-izquierda {
  justify-self: start;
}
.recargando {
  opacity: 0.6;
  transition: opacity 0.2s;
}
.tiles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
}
.tile {
  border: 1px solid var(--borde);
  border-radius: var(--radio);
  background: var(--panel);
  padding: 10px 12px;
  display: grid;
  gap: 2px;
}
.tile-nombre {
  font-size: 0.8rem;
  color: var(--texto-suave);
}
.tile-valor {
  font-size: 1.45rem;
  font-weight: 650;
}
.tile-delta {
  font-size: 0.78rem;
}
.bien {
  color: var(--lima);
}
.mal {
  color: var(--rojo);
}
.rojo {
  color: var(--rojo);
}
.ambar {
  color: var(--ambar);
}
.alertas {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 10px;
}
.alertas li {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px;
  align-items: start;
}
.ia {
  border-left: 3px solid var(--cian);
  padding: 4px 0 4px 12px;
  display: grid;
  gap: 8px;
}
.ia ul {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 4px;
}
.titular {
  font-weight: 650;
  margin: 0;
}
.hallazgo {
  display: grid;
  gap: 2px;
}
.filtros-tabla {
  gap: 6px;
  flex-wrap: wrap;
}
.num {
  text-align: right;
  white-space: nowrap;
}
.block {
  display: block;
}
.corta {
  max-width: 320px;
  overflow-wrap: anywhere;
}
.pasos {
  margin: 0 0 0 18px;
  display: grid;
  gap: 6px;
}
.formulario-utm {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 10px;
}
.formulario-utm .ancho {
  grid-column: 1 / -1;
}
.resultado-utm {
  gap: 8px;
  align-items: center;
}
.resultado-utm code {
  overflow-wrap: anywhere;
  background: var(--panel-2);
  border: 1px solid var(--borde);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 0.8rem;
}
.meta-utm {
  border-top: 1px solid var(--borde);
  padding-top: 10px;
}
</style>
