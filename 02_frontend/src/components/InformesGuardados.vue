<script setup lang="ts">
/**
 * Historial de informes de un módulo del Plan SEO (cortes de Search Console o listas de
 * keywords), guardados tal como estaban el día que se hicieron. Se vuelven a abrir, se bajan
 * en CSV y, los de Search Console, se pueden volver a cargar como los datos actuales.
 */
import { computed, ref, watch } from 'vue'
import { seo } from '@/api/radar'
import type { InformeGuardado, ModuloInforme, SearchConsoleSeo } from '@/api/tipos'
import Icono from '@/components/Icono.vue'
import { confirmar } from '@/composables/confirmar'
import { fechaHora } from '@/composables/formato'
import { useAvisos } from '@/stores/avisos'

const props = defineProps<{
  modulo: ModuloInforme
  /** Cambia cuando hay un informe nuevo (otra sincronización o generación): recarga la lista. */
  version?: unknown
  /** El informe que está cargado ahora como datos actuales (Search Console). */
  enUso?: string | null
}>()
const emit = defineEmits<{ restaurado: [estado: SearchConsoleSeo] }>()
const avisos = useAvisos()
const entero = new Intl.NumberFormat('es-PE')

const abierto = ref(false)
const lista = ref<InformeGuardado[] | null>(null)
const ocupado = ref(false)
const visto = ref<{ informe: InformeGuardado; filas: Record<string, unknown>[] } | null>(null)
const filtro = ref('')

const esGsc = computed(() => props.modulo === 'SEARCH_CONSOLE')
const esMedicion = computed(() => props.modulo === 'MEDICION')
const COLUMNAS = computed(() =>
  esMedicion.value
    ? [
        { clave: 'nombre', nombre: 'Campaña' },
        { clave: 'tipo', nombre: 'Resultado' },
        { clave: 'gasto', nombre: 'Gasto', numero: true },
        { clave: 'resultados', nombre: 'Resultados', numero: true },
        { clave: 'costoResultado', nombre: 'Costo por resultado', numero: true },
      ]
    : esGsc.value
    ? [
        { clave: 'consulta', nombre: 'Búsqueda' },
        { clave: 'url', nombre: 'Página' },
        { clave: 'clics', nombre: 'Clics', numero: true },
        { clave: 'impresiones', nombre: 'Impresiones', numero: true },
        { clave: 'posicion', nombre: 'Posición', numero: true },
      ]
    : [
        { clave: 'keyword', nombre: 'Keyword' },
        { clave: 'grupo', nombre: 'Grupo' },
        { clave: 'intencion', nombre: 'Intención' },
        { clave: 'relevancia', nombre: 'Relevancia', numero: true },
        { clave: 'cobertura', nombre: 'Cobertura' },
      ],
)
const MAX_FILAS = 200

/** El resumen con IA guardado en un informe de Medición. */
function iaDe(i: InformeGuardado) {
  return (i.resumen as { ia?: { titular: string; puntos: string[]; hallazgos: { titulo: string; evidencia: string; sugerencia: string }[] } }).ia ?? null
}

async function cargar() {
  try {
    lista.value = await seo.informes(props.modulo)
  } catch (e) {
    avisos.error(e)
  }
}
watch(abierto, (a) => a && !lista.value && cargar())
watch(
  () => props.version,
  () => abierto.value && cargar(),
)

async function ver(i: InformeGuardado) {
  if (visto.value?.informe.codigo === i.codigo) {
    visto.value = null
    return
  }
  ocupado.value = true
  try {
    visto.value = await seo.informe(i.codigo)
    filtro.value = ''
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

const filasVistas = computed(() => {
  const v = visto.value
  if (!v) return { filas: [], total: 0 }
  const f = filtro.value.trim().toLowerCase()
  const todas = f ? v.filas.filter((x) => COLUMNAS.value.some((c) => String(x[c.clave] ?? '').toLowerCase().includes(f))) : v.filas
  const orden = esGsc.value ? 'impresiones' : esMedicion.value ? 'gasto' : 'relevancia'
  const ordenadas = [...todas].sort((a, b) => Number(b[orden] ?? 0) - Number(a[orden] ?? 0))
  return { filas: ordenadas.slice(0, MAX_FILAS), total: todas.length }
})

function valor(x: Record<string, unknown>, c: { clave: string; numero?: boolean }) {
  const v = x[c.clave]
  if (v == null) return ''
  if (c.clave === 'posicion' && typeof v === 'number') return v.toFixed(1)
  if ((c.clave === 'gasto' || c.clave === 'costoResultado') && typeof v === 'number') return v.toFixed(2)
  return c.numero && typeof v === 'number' ? entero.format(v) : String(v)
}

function resumen(i: InformeGuardado) {
  const r = i.resumen as Record<string, number | string | null>
  if (esMedicion.value) {
    const k = (r.kpis ?? {}) as Record<string, number | null>
    return `${r.moneda ?? ''} ${Number(k.gasto ?? 0).toFixed(2)} · ${entero.format(Number(k.leads ?? 0))} leads · ${entero.format(Number(k.conversaciones ?? 0))} conversaciones`
  }
  return esGsc.value
    ? `${entero.format(Number(r.consultas ?? 0))} búsquedas · ${entero.format(Number(r.clics ?? 0))} clics · ${entero.format(Number(r.impresiones ?? 0))} impresiones`
    : `${entero.format(i.filas)} keywords${r.grupos != null ? ` · ${r.grupos} grupos` : ''}${r.informacionales != null ? ` · ${r.informacionales} informacionales` : ''}`
}

async function restaurar(i: InformeGuardado) {
  const ok = await confirmar({
    titulo: '¿Volver a cargar este corte?',
    mensaje: `${i.titulo}, guardado el ${fechaHora(i.creado)}.`,
    puntos: [
      'Pasa a ser lo que usan «Páginas para mejorar» y el flujo automático.',
      'Los datos actuales no se pierden: también están guardados en esta lista.',
    ],
    aceptar: 'Volver a cargar',
  })
  if (!ok.ok) return
  ocupado.value = true
  try {
    emit('restaurado', await seo.restaurarInforme(i.codigo))
    avisos.exito(`Cargado el corte ${i.codigo}.`)
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}
</script>

<template>
  <details class="chico guardados" @toggle="abierto = ($event.target as HTMLDetailsElement).open">
    <summary>
      <Icono nombre="historial" /> Informes guardados
      <span class="tenue">· {{ esMedicion ? 'cada informe con IA, con sus cifras' : esGsc ? 'cada corte de Search Console' : 'cada lista de keywords generada' }}</span>
    </summary>
    <p v-if="!lista" class="tenue">Cargando…</p>
    <p v-else-if="!lista.length" class="tenue">Aún no hay informes guardados.</p>
    <ul v-else class="lista">
      <li v-for="i in lista" :key="i.codigo" class="informe">
        <div class="fila cabeza">
          <div class="texto">
            <strong>{{ i.titulo }}</strong>
            <span v-if="enUso === i.codigo" class="chip chip-lima">En uso</span>
            <p class="tenue">{{ i.codigo }} · {{ fechaHora(i.creado) }}<template v-if="i.origen"> · tarea {{ i.origen }}</template> · {{ resumen(i) }}</p>
          </div>
          <div class="fila acciones">
            <button class="boton boton-chico" type="button" :disabled="ocupado" :aria-expanded="visto?.informe.codigo === i.codigo" @click="ver(i)">
              <Icono nombre="lista" /> {{ visto?.informe.codigo === i.codigo ? 'Cerrar' : 'Ver' }}
            </button>
            <a class="boton boton-chico" :href="seo.csvInforme(i.codigo)"><Icono nombre="bajar" /> CSV</a>
            <button v-if="esGsc && enUso !== i.codigo" class="boton boton-chico" type="button" :disabled="ocupado" @click="restaurar(i)">
              <Icono nombre="reintentar" /> Volver a cargar
            </button>
          </div>
        </div>
        <div v-if="visto?.informe.codigo === i.codigo" class="visor">
          <div v-if="esMedicion && iaDe(visto.informe)" class="ia-guardada">
            <strong>{{ iaDe(visto.informe)!.titular }}</strong>
            <ul>
              <li v-for="(p, n) in iaDe(visto.informe)!.puntos" :key="n">{{ p }}</li>
              <li v-for="(h, n) in iaDe(visto.informe)!.hallazgos" :key="`h${n}`"><strong>{{ h.titulo }}:</strong> {{ h.evidencia }} — {{ h.sugerencia }}</li>
            </ul>
          </div>
          <input v-model="filtro" type="search" placeholder="Filtrar…" aria-label="Filtrar las filas del informe" />
          <p class="tenue">
            {{ filasVistas.total > MAX_FILAS ? `Las ${MAX_FILAS} primeras de ${entero.format(filasVistas.total)}` : `${entero.format(filasVistas.total)} filas` }},
            de más a menos {{ esGsc ? 'impresiones' : 'relevancia' }}. Todas, en el CSV.
          </p>
          <div class="tabla-envoltura">
            <table class="tabla">
              <thead>
                <tr>
                  <th v-for="c in COLUMNAS" :key="c.clave" :class="{ num: c.numero }">{{ c.nombre }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(x, n) in filasVistas.filas" :key="n">
                  <td v-for="c in COLUMNAS" :key="c.clave" :class="{ num: c.numero }">{{ valor(x, c) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </li>
    </ul>
  </details>
</template>

<style scoped>
.guardados {
  margin: 12px 0;
}
.guardados svg {
  width: 14px;
  height: 14px;
  vertical-align: -2px;
}
.lista {
  list-style: none;
  margin: 8px 0 0;
  padding: 0;
  display: grid;
  gap: 8px;
}
.informe {
  border: 1px solid var(--borde);
  border-radius: var(--radio);
  padding: 8px 10px;
  display: grid;
  gap: 8px;
}
.cabeza {
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}
.texto {
  min-width: 0;
}
.texto p {
  margin: 2px 0 0;
  overflow-wrap: anywhere;
}
.acciones {
  gap: 6px;
  flex-wrap: wrap;
}
.visor {
  display: grid;
  gap: 6px;
}
.visor p {
  margin: 0;
}
.ia-guardada ul {
  margin: 4px 0 0 18px;
  display: grid;
  gap: 2px;
}
.tabla-envoltura {
  max-height: 420px;
  overflow: auto;
}
.tabla td {
  overflow-wrap: anywhere;
}
.num {
  text-align: right;
  white-space: nowrap;
}
</style>
