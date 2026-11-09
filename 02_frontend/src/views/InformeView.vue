<script setup lang="ts">
/**
 * El informe: lo que anuncia el mercado, qué está saturado y dónde hay hueco.
 *
 * Todo viene calculado del worker; aquí solo se pinta. Importante para quien lo
 * lea: la Biblioteca de Meta enseña QUÉ anuncia cada negocio, no QUÉ le funciona.
 * Lo único que insinúa resultados es cuánto tiempo lleva activo un anuncio
 * ("meses funcionando"). El informe dice dónde está el mercado; qué hacer con
 * eso lo decide quien lo lee.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { informes, sistema } from '@/api/radar'
import type { AnuncioInforme, FilaFrecuencia, Informe, InformeFila, Taxonomia } from '@/api/tipos'
import Icono from '@/components/Icono.vue'
import MapaMercado from '@/components/MapaMercado.vue'
import NumeroAnimado from '@/components/NumeroAnimado.vue'
import TablaFrecuencias from '@/components/TablaFrecuencias.vue'
import TarjetaAnuncio from '@/components/TarjetaAnuncio.vue'
import VisorAnuncio from '@/components/VisorAnuncio.vue'
import { confirmar } from '@/composables/confirmar'
import { duracionActivo, fecha, porDiasActivo, pct, usd } from '@/composables/formato'
import { useAvisos } from '@/stores/avisos'

const props = defineProps<{ codigo: string }>()
const avisos = useAvisos()
const router = useRouter()

const resumen = ref<InformeFila | null>(null)
const d = ref<Informe | null>(null)
const tax = ref<Taxonomia | null>(null)
const cargando = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const r = await informes.obtener(props.codigo)
    resumen.value = r.resumen
    d.value = r.datos
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    cargando.value = false
  }
  sistema.taxonomia().then((t) => (tax.value = t)).catch(() => {})
})

const SECCIONES = [
  { id: 'mapa', titulo: 'Mapa del mercado' },
  { id: 'meses', titulo: 'Meses funcionando' },
  { id: 'aperturas', titulo: 'Cómo abren' },
  { id: 'galeria', titulo: 'Todos los anuncios' },
  { id: 's1', titulo: '1 · Ángulos' },
  { id: 's2', titulo: '2 · Hooks' },
  { id: 's3', titulo: '3 · Ofertas' },
  { id: 's4', titulo: '4 · Beneficios' },
  { id: 's5', titulo: '5 · Visual y formatos' },
  { id: 's6', titulo: '6 · Llamadas a la acción' },
  { id: 's7', titulo: '7 · Saturado' },
  { id: 's8', titulo: '8 · Territorios libres' },
  { id: 's9', titulo: '9 · Resumen' },
]

const TIPOS_BENEFICIO = [
  { clave: 'funcional', titulo: 'Funcionales', ayuda: 'Lo que el servicio hace' },
  { clave: 'emocional', titulo: 'Emocionales', ayuda: 'Cómo se siente el cliente' },
  { clave: 'valores', titulo: 'De valores', ayuda: 'Lo que representa' },
] as const

const etiquetas = computed(() => ({ hooks: tax.value?.hooks, ofertas: tax.value?.ofertas, formatos: tax.value?.formatos }))
const hayVeteranos = computed(() => (d.value?.veteranos.length ?? 0) > 0)
const seccionesVisibles = computed(() =>
  SECCIONES.filter((x) => (x.id !== 'meses' || hayVeteranos.value) && (x.id !== 'aperturas' || aperturas.value.length)),
)

// Índice lateral: marca la sección que se está leyendo.
const activa = ref('mapa')
let observador: IntersectionObserver | null = null
watch(d, async (v) => {
  if (!v) return
  await nextTick()
  observador?.disconnect()
  observador = new IntersectionObserver(
    (entradas) => {
      const visible = entradas.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0]
      if (visible) activa.value = visible.target.id
    },
    { rootMargin: '-15% 0px -70% 0px' },
  )
  seccionesVisibles.value.forEach((x) => {
    const el = document.getElementById(x.id)
    if (el) observador!.observe(el)
  })
})
onBeforeUnmount(() => observador?.disconnect())
const aperturas = computed(() => (d.value?.hooks.ejemplos ?? []).slice(0, 12))

/**
 * Competidores sin ningún anuncio de 90 días o más. «Meses funcionando» es de todo el
 * informe (competidores y mercado): sin este aviso parece que al competidor se le olvidó.
 */
const sinVeteranos = computed(() => {
  const dd = d.value
  if (!dd) return []
  const generado = new Date(dd.meta.generado).getTime()
  const paginas = new Map<string, Set<string>>()
  for (const i of dd.meta.identificadas ?? []) {
    if (!paginas.has(i.buscado)) paginas.set(i.buscado, new Set())
    paginas.get(i.buscado)!.add(i.page_id)
  }
  const salida: { competidor: string; dias: number }[] = []
  for (const [competidor, ids] of paginas) {
    const dias = dd.anuncios
      .filter((a) => a.page_id && ids.has(a.page_id))
      .map((a) => Math.max(0, Math.floor((generado - new Date(a.fecha_inicio).getTime()) / 864e5)))
      .filter((n) => Number.isFinite(n))
    if (dias.length && Math.max(...dias) < 90) salida.push({ competidor, dias: Math.max(...dias) })
  }
  return salida
})

// ── Galería filtrable ─────────────────────────────────────────────────────

const fTerritorio = ref('')
const fOferta = ref('')
const fAnunciante = ref('')
const fTexto = ref('')
const visibles = ref(24)

const anunciantes = computed(() => [...new Set((d.value?.anuncios ?? []).map((a) => a.anunciante))].sort())

/**
 * De dónde sale cada anuncio: de los competidores que pusiste (sus páginas identificadas),
 * de tu marca, o del mercado (lo que trajeron las palabras clave del sector).
 */
const GRUPOS = ['Tus competidores', 'Tu marca', 'Del sector y las palabras clave'] as const
const grupoDe = computed(() => {
  const suyas = new Set((d.value?.meta.identificadas ?? []).map((i) => i.page_id))
  return (a: AnuncioInforme) => (esMio.value(a) ? 1 : a.page_id && suyas.has(a.page_id) ? 0 : 2)
})

const filtrados = computed<AnuncioInforme[]>(() => {
  const t = fTexto.value.trim().toLowerCase()
  // Primero tus competidores, luego tu marca y al final el mercado; dentro de cada grupo,
  // los que más tiempo llevan activos (sort es estable).
  const grupo = grupoDe.value
  return porDiasActivo(d.value?.anuncios ?? []).sort((a, b) => grupo(a) - grupo(b)).filter(
    (a) =>
      (!fTerritorio.value || a.territorios_angulo.includes(fTerritorio.value)) &&
      (!fOferta.value || nombreOferta(a.oferta_tipo) === fOferta.value) &&
      (!fAnunciante.value || a.anunciante === fAnunciante.value) &&
      (!t || `${a.hook_literal} ${a.copy ?? ''} ${a.anunciante}`.toLowerCase().includes(t)),
  )
})
/** Los títulos de grupo solo tienen sentido si el informe mezcla más de un origen. */
const hayGrupos = computed(() => new Set((d.value?.anuncios ?? []).map(grupoDe.value)).size > 1)

const nombreOferta = (clave: string) => tax.value?.ofertas?.[clave] ?? clave
const ofertasUsadas = computed(() => [...new Set((d.value?.anuncios ?? []).map((a) => nombreOferta(a.oferta_tipo)))].sort())

/** Si un anuncio es de tu marca: por sus páginas; los informes antiguos no las traen y se reconocen por el nombre. */
const esMio = computed(() => {
  const marcas = (d.value?.mi_marca ?? '').split(' y ').map((m) => m.trim().toLowerCase()).filter(Boolean)
  if (!marcas.length) return () => false
  const paginas = d.value?.mis_paginas ? new Set(d.value.mis_paginas) : null
  return (a: AnuncioInforme) =>
    paginas
      ? !!a.page_id && paginas.has(a.page_id)
      : marcas.some((m) => a.anunciante.toLowerCase().includes(m) || m.includes(a.anunciante.toLowerCase()))
})

/** Ofertas que usa tu marca (el informe solo trae sus territorios; las ofertas se deducen de sus anuncios). */
const misOfertas = computed(() => [
  ...new Set((d.value?.anuncios ?? []).filter(esMio.value).map((a) => nombreOferta(a.oferta_tipo))),
])

// ── Ficha de anuncio (visor con flechas) ───────────────────────────────────

const ORDEN_DIAS = 'ordenados por días activo'

const visor = ref<{ lista: AnuncioInforme[]; contexto: string; orden: string; punto?: FilaFrecuencia }>({
  lista: [],
  contexto: '',
  orden: '',
})
const visorIndice = ref<number | null>(null)

function abrirVisor(lista: AnuncioInforme[], indice: number, contexto: string, orden = ORDEN_DIAS, punto?: FilaFrecuencia) {
  if (!lista.length) return
  visor.value = { lista, contexto, orden, punto }
  visorIndice.value = indice
}

const deFila = (f: FilaFrecuencia) =>
  (d.value?.anuncios ?? []).filter((a) =>
    f.dimension === 'Oferta' ? nombreOferta(a.oferta_tipo) === f.clave : a.territorios_angulo.includes(f.clave),
  )

/**
 * Un punto del mapa abre sus anuncios, empezando por el que más tiempo lleva
 * activo. (El Radar original abría el primero que llegó de Meta, sin criterio.)
 */
function elegirEnMapa(f: FilaFrecuencia) {
  abrirVisor(porDiasActivo(deFila(f)), 0, `${f.dimension}: ${f.clave}`, ORDEN_DIAS, f)
}

/** Desde el visor: deja la galería filtrada por el mismo punto y baja hasta ella. */
function verPuntoEnGaleria() {
  const f = visor.value.punto
  if (!f) return
  fTexto.value = ''
  fAnunciante.value = ''
  fTerritorio.value = f.dimension === 'Oferta' ? '' : f.clave
  fOferta.value = f.dimension === 'Oferta' ? f.clave : ''
  visibles.value = 24
  visorIndice.value = null
  nextTick(() => document.getElementById('galeria')?.scrollIntoView({ behavior: 'smooth' }))
}

const contextoGaleria = computed(() => {
  const partes = [fTerritorio.value && `Territorio: ${fTerritorio.value}`, fOferta.value && `Oferta: ${fOferta.value}`, fAnunciante.value]
  return partes.filter(Boolean).join(' · ') || 'Todos los anuncios'
})

// ── Acciones ──────────────────────────────────────────────────────────────

const imprimir = () => globalThis.print()

async function archivar() {
  if (!resumen.value) return
  try {
    await informes.archivar(resumen.value.codigo, !resumen.value.archivado)
    resumen.value = { ...resumen.value, archivado: !resumen.value.archivado }
    avisos.exito(resumen.value.archivado ? 'Informe archivado.' : 'Informe recuperado.')
  } catch (e) {
    avisos.error(e)
  }
}

async function borrar() {
  if (!resumen.value) return
  const r = await confirmar({
    titulo: '¿Borrar este informe?',
    mensaje: 'Desaparece de la lista. El análisis que lo generó no se vuelve a ejecutar.',
    aceptar: 'Borrar',
    tono: 'peligro',
  })
  if (!r.ok) return
  try {
    await informes.borrar(resumen.value.codigo)
    avisos.exito('Informe borrado.')
    router.push('/informes')
  } catch (e) {
    avisos.error(e)
  }
}
</script>

<template>
  <div class="pagina">
    <p v-if="cargando" class="cargando suave">Abriendo el informe…</p>
    <div v-else-if="error" class="aviso aviso-error" role="alert">
      <Icono nombre="error" /><div class="aviso-cuerpo">{{ error }}</div>
    </div>

    <template v-else-if="d && resumen">
      <div class="pagina-cabecera">
        <div>
          <RouterLink to="/informes" class="chico volver"><Icono nombre="volver" /> Informes</RouterLink>
          <h1>Informe de patrones en Meta Ads</h1>
          <p>
            <strong>{{ resumen.marca || 'Mercado' }}</strong> · {{ fecha(d.meta.generado) }} ·
            {{ d.meta.anuncios }} anuncios de {{ d.meta.anunciantes }} anunciantes
            <span v-if="resumen.esEjemplo" class="chip chip-ambar">ejemplo con datos inventados</span>
          </p>
        </div>
        <div class="fila sin-imprimir">
          <button class="boton" type="button" @click="archivar">
            {{ resumen.archivado ? 'Recuperar' : 'Archivar' }}
          </button>
          <button class="boton" type="button" @click="imprimir"><Icono nombre="imprimir" /> Imprimir / PDF</button>
          <button class="boton boton-peligro" type="button" @click="borrar"><Icono nombre="basura" /> Borrar</button>
        </div>
      </div>

      <div v-if="d.meta.aviso_muestra" class="aviso aviso-ambar" role="status">
        <Icono nombre="alerta" /><div class="aviso-cuerpo">{{ d.meta.aviso_muestra }}</div>
      </div>
      <div v-if="d.meta.aviso_huerfanas" class="aviso aviso-ambar" role="status">
        <Icono nombre="alerta" /><div class="aviso-cuerpo">{{ d.meta.aviso_huerfanas }}</div>
      </div>
      <div v-if="d.meta.sin_anuncios.length" class="aviso aviso-info" role="status">
        <Icono nombre="info" />
        <div class="aviso-cuerpo">
          Sin anuncios activos en Meta ahora mismo: <strong>{{ d.meta.sin_anuncios.join(', ') }}</strong>.
        </div>
      </div>

      <section class="titulares" aria-label="Titulares">
        <div v-for="t in d.titulares" :key="t.etiqueta" class="titular panel">
          <strong><NumeroAnimado :valor="t.valor" /></strong>
          <span>{{ t.etiqueta }}</span>
          <small class="tenue">{{ t.detalle }}</small>
        </div>
      </section>

      <div class="cuerpo">
      <nav class="indice sin-imprimir panel" aria-label="En este informe">
        <strong>En este informe</strong>
        <ol>
          <li v-for="s in seccionesVisibles" :key="s.id">
            <a :href="`#${s.id}`" :class="{ activa: activa === s.id }" :aria-current="activa === s.id ? 'location' : undefined">{{ s.titulo }}</a>
          </li>
        </ol>
      </nav>

      <div class="secciones">

      <!-- Mapa -->
      <section id="mapa" class="panel">
        <div class="panel-titulo"><h2>El mapa del mercado</h2></div>
        <p class="suave chico bajada">
          Arriba a la derecha, lo que hace casi todo el mundo. Abajo a la izquierda, lo que apenas aparece: ahí está el hueco.
          Cada punto es un ángulo (lo que se promete) o una oferta (lo que se da).
        </p>
        <MapaMercado :filas="d.resumen" :total-anunciantes="d.meta.anunciantes" :mios="[...d.mis_territorios, ...misOfertas]" :mi-marca="d.mi_marca" @elegir="elegirEnMapa" />
        <div v-if="d.mi_marca" class="aviso aviso-info donde">
          <Icono nombre="info" />
          <div class="aviso-cuerpo">
            <strong>Dónde estás tú.</strong>
            <template v-if="d.mis_anuncios">
              Se han analizado {{ d.mis_anuncios }} anuncios de {{ d.mi_marca }}, que ocupan
              {{ d.mis_territorios.length }} de {{ d.angulos.length }} territorios<template v-if="d.mis_territorios.length">:
              {{ d.mis_territorios.join(', ') }}</template>.
            </template>
            <template v-else>No se encontraron anuncios activos de {{ d.mi_marca }} entre los analizados.</template>
          </div>
        </div>
      </section>

      <!-- Meses funcionando -->
      <section v-if="hayVeteranos" id="meses" class="panel">
        <div class="panel-titulo"><h2>Anuncios que llevan meses funcionando</h2></div>
        <p class="suave chico bajada">
          Nadie mantiene meses un anuncio que no le sirve: es la única señal de rendimiento que deja ver la Biblioteca.
          Estos llevan 90 días o más activos, de cualquier anunciante del informe (competidores y mercado).
        </p>
        <div v-if="sinVeteranos.length" class="aviso aviso-info sin-veteranos" role="note">
          <Icono nombre="info" />
          <div class="aviso-cuerpo">
            <template v-for="(x, i) in sinVeteranos" :key="x.competidor">
              <template v-if="i">; </template><strong>{{ x.competidor }}</strong> no tiene ninguno: su anuncio más antiguo lleva
              {{ duracionActivo(x.dias) }}</template>.
          </div>
        </div>
        <div class="rejilla rejilla-2">
          <TarjetaAnuncio
            v-for="(a, i) in d.veteranos.slice(0, 8)"
            :key="a.ad_id"
            :anuncio="a"
            :etiquetas="etiquetas"
            abrible
            @abrir="abrirVisor(d.veteranos.slice(0, 8), i, 'Llevan meses funcionando')"
          />
        </div>
      </section>

      <!-- Cómo abren -->
      <section v-if="aperturas.length" id="aperturas" class="panel">
        <div class="panel-titulo"><h2>Cómo abren sus anuncios</h2></div>
        <p class="suave chico bajada">Lo primero que dice o muestra cada anuncio, tal cual.</p>
        <ul class="citas">
          <li v-for="(e, i) in aperturas" :key="i">
            <q>{{ e.texto }}</q>
            <small class="tenue">{{ e.anunciante }}</small>
          </li>
        </ul>
      </section>

      <!-- Galería -->
      <section id="galeria" class="panel">
        <div class="panel-titulo">
          <h2>Todos los anuncios analizados</h2>
          <span class="tenue chico num">
            {{ filtrados.length }} de {{ d.anuncios.length }} · primero tus competidores, al final el mercado; en cada grupo, los
            que más tiempo llevan activos
          </span>
        </div>
        <div class="fila filtros sin-imprimir">
          <div class="campo">
            <label for="f-texto">Buscar</label>
            <input id="f-texto" v-model="fTexto" type="text" placeholder="Texto, titular o marca" @input="visibles = 24" />
          </div>
          <div class="campo">
            <label for="f-anunciante">Anunciante</label>
            <select id="f-anunciante" v-model="fAnunciante" @change="visibles = 24">
              <option value="">Todos</option>
              <option v-for="a in anunciantes" :key="a" :value="a">{{ a }}</option>
            </select>
          </div>
          <div class="campo">
            <label for="f-territorio">Territorio</label>
            <select id="f-territorio" v-model="fTerritorio" @change="visibles = 24">
              <option value="">Todos</option>
              <option v-for="t in d.territorios" :key="t.nombre" :value="t.nombre">{{ t.nombre }}</option>
            </select>
          </div>
          <div class="campo">
            <label for="f-oferta">Oferta</label>
            <select id="f-oferta" v-model="fOferta" @change="visibles = 24">
              <option value="">Todas</option>
              <option v-for="o in ofertasUsadas" :key="o" :value="o">{{ o }}</option>
            </select>
          </div>
        </div>
        <p v-if="!filtrados.length" class="vacio">Ningún anuncio coincide con esos filtros.</p>
        <div class="rejilla rejilla-2">
          <template v-for="(a, i) in filtrados.slice(0, visibles)" :key="a.ad_id">
            <h3 v-if="hayGrupos && (i === 0 || grupoDe(filtrados[i - 1]) !== grupoDe(a))" class="grupo">
              {{ GRUPOS[grupoDe(a)] }}
            </h3>
            <TarjetaAnuncio :anuncio="a" :etiquetas="etiquetas" abrible @abrir="abrirVisor(filtrados, i, contextoGaleria)" />
          </template>
        </div>
        <div v-if="filtrados.length > visibles" class="fila" style="justify-content: center; margin-top: 14px">
          <button class="boton sin-imprimir" type="button" @click="visibles += 24">
            Ver {{ Math.min(24, filtrados.length - visibles) }} más
          </button>
        </div>
      </section>

      <!-- 1 Ángulos -->
      <section id="s1" class="panel">
        <div class="panel-titulo"><h2>1 · Qué ángulos se repiten más</h2></div>
        <p class="suave chico bajada">Lo que prometen los anuncios, agrupado en territorios.</p>
        <TablaFrecuencias :filas="d.angulos" :mios="d.mis_territorios" />
      </section>

      <!-- 2 Hooks -->
      <section id="s2" class="panel">
        <div class="panel-titulo"><h2>2 · Qué estructuras de hook se repiten</h2></div>
        <p class="suave chico bajada">Cómo abre cada anuncio, según la primera frase.</p>
        <TablaFrecuencias :filas="d.hooks.patrones" />
      </section>

      <!-- 3 Ofertas -->
      <section id="s3" class="panel">
        <div class="panel-titulo"><h2>3 · Qué ofertas se utilizan</h2></div>
        <p v-if="d.ofertas.mas_usada" class="suave chico bajada">
          La más usada: <strong>{{ d.ofertas.mas_usada.clave }}</strong> ({{ pct(d.ofertas.mas_usada.pct) }}).
        </p>
        <TablaFrecuencias :filas="d.ofertas.patrones" />
      </section>

      <!-- 4 Beneficios -->
      <section id="s4" class="panel">
        <div class="panel-titulo"><h2>4 · Qué beneficios comunica la competencia</h2></div>
        <div class="rejilla rejilla-3">
          <div v-for="t in TIPOS_BENEFICIO" :key="t.clave">
            <h3>{{ t.titulo }}</h3>
            <p class="tenue chico bajada">{{ t.ayuda }}</p>
            <TablaFrecuencias :filas="d.beneficios[t.clave]" vacio="Ningún anuncio comunica beneficios de este tipo." :detalle="false" />
          </div>
        </div>
      </section>

      <!-- 5 Visual -->
      <section id="s5" class="panel">
        <div class="panel-titulo"><h2>5 · Patrones visuales y formatos</h2></div>
        <div class="rejilla rejilla-2">
          <div>
            <h3>Formatos</h3>
            <TablaFrecuencias :filas="d.visuales.formatos" :detalle="false" />
          </div>
          <div>
            <h3>Lo que se ve</h3>
            <TablaFrecuencias :filas="d.visuales.patrones" :detalle="false" />
          </div>
        </div>
      </section>

      <!-- 6 CTA -->
      <section id="s6" class="panel">
        <div class="panel-titulo"><h2>6 · Llamadas a la acción más utilizadas</h2></div>
        <TablaFrecuencias :filas="d.ctas" :detalle="false" />
      </section>

      <!-- 7 Saturado -->
      <section id="s7" class="panel">
        <div class="panel-titulo"><h2>7 · Qué está saturado</h2></div>
        <div class="rejilla rejilla-2">
          <div>
            <h3>Muy repetido</h3>
            <TablaFrecuencias :filas="d.saturado.dominantes" vacio="Nada destaca por encima del resto en este mercado." />
          </div>
          <div>
            <h3>Menos utilizado</h3>
            <TablaFrecuencias
              :filas="d.saturado.poco_usados"
              vacio="Nada aparece muy por debajo del resto: todos los ángulos están bastante ocupados."
            />
          </div>
        </div>
      </section>

      <!-- 8 Huecos -->
      <section id="s8" class="panel">
        <div class="panel-titulo"><h2>8 · Territorios que aparecen poco</h2></div>
        <p v-if="d.huecos.length" class="suave chico bajada">
          Estos aparecen con menor frecuencia entre los anuncios analizados. Que estén libres no significa que funcionen:
          significa que nadie los está ocupando. La decisión de probarlos es tuya.
        </p>
        <TablaFrecuencias
          :filas="d.huecos"
          vacio="Ningún territorio ni oferta aparece por debajo del 10 % de los anuncios: en este mercado todos los ángulos están bastante ocupados. Para diferenciarte, mira en la sección 7 lo menos utilizado."
        />
      </section>

      <!-- 9 Resumen -->
      <section id="s9" class="panel">
        <div class="panel-titulo"><h2>9 · Resumen</h2></div>
        <div class="tabla-envoltura">
          <table class="tabla">
            <thead>
              <tr><th>Dimensión</th><th>Qué</th><th class="num">%</th><th>Frecuencia</th></tr>
            </thead>
            <tbody>
              <tr v-for="f in d.resumen" :key="f.dimension + f.clave">
                <td class="suave">{{ f.dimension }}</td>
                <td>{{ f.clave }}</td>
                <td class="num">{{ pct(f.pct) }}</td>
                <td>{{ f.frecuencia.replace('_', ' ') }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="aviso aviso-info leer">
          <Icono nombre="info" />
          <div class="aviso-cuerpo">
            <strong>Cómo leer este informe.</strong>
            Mide qué anuncia el mercado, no qué le funciona: la Biblioteca de Meta no publica resultados. Los porcentajes
            pesan más a los competidores directos que a los nacionales. Describe, no recomienda.
            <span v-if="d.meta.costo_ia_usd" class="tenue">
              Costo de IA de este informe: {{ usd(d.meta.costo_ia_usd) }} en {{ d.meta.llamadas_ia }} llamadas.
            </span>
            <span v-if="d.meta.descartados" class="tenue">
              {{ d.meta.descartados }} anuncios se descartaron por no ser del sector.
            </span>
            <span v-if="d.veteranos.length" class="tenue">
              El anuncio más veterano lleva {{ duracionActivo(d.veteranos[0].dias_activo ?? 0) }}.
            </span>
          </div>
        </div>
      </section>
      </div>
      </div>

      <VisorAnuncio
        v-model:indice="visorIndice"
        :anuncios="visor.lista"
        :contexto="visor.contexto"
        :orden="visor.orden"
        :tax="tax"
        :ver-todos="visor.punto ? `Ver los ${visor.lista.length} en la galería` : undefined"
        @galeria="verPuntoEnGaleria"
      />
    </template>
  </div>
</template>

<style scoped>
.grupo {
  grid-column: 1 / -1;
  font-size: 0.95rem;
  color: var(--texto-suave);
  margin-top: 6px;
}
.grupo:first-child {
  margin-top: 0;
}
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
.titulares {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}
.titular {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.titular strong {
  font-size: 1.9rem;
  color: var(--cian);
  line-height: 1.1;
}
.titular + .titular {
  margin-top: 0;
}
@media (max-width: 860px) {
  .titulares {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
.cuerpo {
  display: grid;
  grid-template-columns: 230px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
.indice {
  position: sticky;
  top: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: calc(100vh - 32px);
  overflow: auto;
}
.indice ol {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.indice a {
  display: block;
  padding: 6px 10px;
  border-left: 2px solid transparent;
  border-radius: 0 var(--radio-chico) var(--radio-chico) 0;
  color: var(--texto-suave);
  font-size: 0.92rem;
}
.indice a:hover {
  color: var(--texto);
  background: var(--panel-2);
  text-decoration: none;
}
.indice a.activa {
  color: var(--cian);
  border-left-color: var(--cian);
  background: var(--cian-fondo);
  font-weight: 600;
}
.secciones > .panel + .panel {
  margin-top: 16px;
}
@media (max-width: 1000px) {
  .cuerpo {
    grid-template-columns: minmax(0, 1fr);
  }
  .indice {
    position: static;
    max-height: none;
  }
}
@media print {
  .cuerpo {
    display: block;
  }
}
.bajada {
  margin-bottom: 14px;
}
.donde {
  margin-top: 16px;
}
.sin-veteranos {
  margin-bottom: 14px;
}
.leer {
  margin-top: 16px;
}
.filtros {
  margin-bottom: 14px;
  align-items: flex-end;
}
.filtros .campo {
  min-width: 180px;
  flex: 1;
}
.citas {
  list-style: none;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 20px;
}
.citas li {
  display: flex;
  flex-direction: column;
  border-left: 3px solid var(--cian);
  padding-left: 12px;
}
@media (max-width: 760px) {
  .citas {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media print {
  .sin-imprimir {
    display: none !important;
  }
  .panel {
    break-inside: avoid;
  }
}
</style>
