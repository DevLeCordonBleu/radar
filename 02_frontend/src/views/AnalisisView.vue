<script setup lang="ts">
/**
 * Seguimiento de un análisis: en qué fase va, cuánto lleva, y qué hacer si se
 * pausa (cuota de Gemini, red, una página ambigua). Lo hecho nunca se pierde.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { analisis } from '@/api/radar'
import type { Analisis, FaseAnalisis } from '@/api/tipos'
import Icono from '@/components/Icono.vue'
import { confirmar } from '@/composables/confirmar'
import { CLASE_ESTADO, ETIQUETA_ESTADO, enMeta, fechaHora } from '@/composables/formato'
import { useSondeo } from '@/composables/sondeo'
import { useAvisos } from '@/stores/avisos'

const props = defineProps<{ codigo: string }>()
const avisos = useAvisos()
const router = useRouter()

const a = ref<Analisis | null>(null)
const error = ref('')
const ocupado = ref(false)

const FASES: { clave: FaseAnalisis; texto: string }[] = [
  { clave: 'buscando', texto: 'Buscar anuncios' },
  { clave: 'clasificando', texto: 'Analizarlos' },
  { clave: 'territorios', texto: 'Agrupar territorios' },
  { clave: 'informe', texto: 'Informe' },
]

const activo = computed(() => a.value?.estado === 'en_cola' || a.value?.estado === 'corriendo')
const indiceFase = computed(() => FASES.findIndex((x) => x.clave === a.value?.fase))
const porcentaje = computed(() => (a.value && a.value.total > 0 ? Math.round((a.value.hechos / a.value.total) * 100) : 0))
const puedeTerminar = computed(() => (a.value?.hechos ?? 0) > 0 && a.value?.estado === 'pausado' && !a.value.pendiente)
const nombre = computed(
  () => a.value?.peticion.misMarcas.join(' y ') || a.value?.peticion.competidores.map((c) => c.nombre).slice(0, 3).join(', ') || props.codigo,
)

async function cargar() {
  try {
    a.value = await analisis.obtener(props.codigo)
    error.value = ''
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
    throw e
  }
}

onMounted(() => cargar().catch(() => {}))
useSondeo(cargar, () => activo.value || !a.value, 2500)

async function accion(f: () => Promise<Analisis>, ok?: string) {
  ocupado.value = true
  try {
    a.value = await f()
    if (ok) avisos.exito(ok)
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

const continuar = () => accion(() => analisis.continuar(props.codigo))

async function terminar() {
  const r = await confirmar({
    titulo: '¿Terminar con lo analizado?',
    mensaje: `Se hace el informe con los ${a.value?.hechos} anuncios ya clasificados, sin esperar a Gemini.`,
    puntos: ['Los porcentajes serán menos fiables cuanto menos anuncios haya.', 'Los territorios se agrupan por palabras compartidas si Gemini no responde.'],
    aceptar: 'Terminar ya',
    tono: 'aviso',
  })
  if (r.ok) await accion(() => analisis.terminar(props.codigo))
}

async function cancelar() {
  const r = await confirmar({
    titulo: '¿Cancelar el análisis?',
    mensaje: 'Se detiene la búsqueda para no gastar crédito. Lo hecho se descarta.',
    aceptar: 'Cancelar análisis',
    tono: 'peligro',
    cancelar: 'Seguir',
  })
  if (r.ok) await accion(() => analisis.cancelar(props.codigo))
}

async function borrar() {
  const r = await confirmar({ titulo: '¿Borrar este análisis?', aceptar: 'Borrar', tono: 'peligro' })
  if (!r.ok) return
  try {
    await analisis.borrar(props.codigo)
    router.push('/informes')
  } catch (e) {
    avisos.error(e)
  }
}

/** Páginas marcadas en la elección: una marca suele tener varias (sedes, talleres...). */
const marcadas = ref<string[]>([])
watch(() => a.value?.pendiente?.competidor, () => (marcadas.value = []))

const elegir = (competidor: string, pageIds: string[]) =>
  accion(() => analisis.elegirPagina(props.codigo, competidor, pageIds))
</script>

<template>
  <div class="pagina estrecha">
    <p v-if="!a && !error" class="cargando suave">Cargando…</p>
    <div v-else-if="error && !a" class="aviso aviso-error" role="alert">
      <Icono nombre="error" /><div class="aviso-cuerpo">{{ error }}</div>
    </div>

    <template v-else-if="a">
      <div class="pagina-cabecera">
        <div>
          <RouterLink to="/informes" class="chico volver"><Icono nombre="volver" /> Informes</RouterLink>
          <h1>{{ nombre }}</h1>
          <p class="num">
            Análisis {{ a.codigo }} · {{ fechaHora(a.creado) }} · {{ a.peticion.competidores.length }} competidores · {{ a.peticion.pais }}
          </p>
        </div>
        <span class="chip" :class="CLASE_ESTADO[a.estado]">{{ ETIQUETA_ESTADO[a.estado] }}</span>
      </div>

      <section class="panel" aria-live="polite">
        <ol class="fases" aria-label="Fases">
          <li
            v-for="(x, i) in FASES"
            :key="x.clave"
            :class="{ hecha: a.estado === 'terminado' || i < indiceFase, actual: i === indiceFase && a.estado !== 'terminado' }"
          >
            <!-- El ✓ solo ocupa sitio cuando la fase está hecha: si no, el texto quedaría descentrado. -->
            <span v-if="a.estado === 'terminado' || i < indiceFase" class="punto"><Icono nombre="ok" /></span>
            {{ x.texto }}
          </li>
        </ol>

        <div v-if="a.estado !== 'terminado' && a.estado !== 'cancelado'" class="avance">
          <p>
            <Icono v-if="activo" nombre="reintentar" class="giratorio" /> {{ a.mensaje }}
          </p>
          <div v-if="a.total > 0" class="pista" role="progressbar" :aria-valuenow="porcentaje" aria-valuemin="0" aria-valuemax="100">
            <div class="relleno" :style="{ width: porcentaje + '%' }" />
          </div>
          <p v-if="a.total > 0" class="tenue chico num">{{ a.hechos }} de {{ a.total }} anuncios · {{ porcentaje }} %</p>
        </div>
      </section>

      <!-- Eleccion de pagina -->
      <section v-if="a.pendiente" class="panel pila" aria-label="Elegir página">
        <h2>¿Cuáles son las páginas de «{{ a.pendiente.competidor }}»?</h2>
        <p class="suave">
          Hay varias páginas con un nombre parecido. Marca las que son de este competidor (puede tener más de una: sedes,
          talleres…); así no se mezclan anuncios ajenos en el informe.
        </p>
        <ul class="lista-plana candidatas">
          <li v-for="c in a.pendiente.candidatos" :key="c.pageId">
            <label class="candidata" :class="{ marcada: marcadas.includes(c.pageId) }">
              <input v-model="marcadas" type="checkbox" :value="c.pageId" :aria-label="`${c.nombre} es de ${a.pendiente.competidor}`" />
              <span class="avatar">
                <img v-if="c.avatar ?? c.muestra" :src="(c.avatar ?? c.muestra)!" :alt="`Foto de perfil de ${c.nombre}`" loading="lazy" referrerpolicy="no-referrer" />
                <Icono v-else nombre="imagen" />
              </span>
              <span class="datos">
                <strong>{{ c.nombre }}</strong>
                <span class="tenue chico num">{{ c.anuncios }} {{ c.anuncios === 1 ? 'anuncio activo' : 'anuncios activos' }} · id {{ c.pageId }}</span>
                <span v-if="c.texto" class="suave chico texto">«{{ c.texto }}»</span>
                <a :href="enMeta(c.pageId, a.peticion.pais)" target="_blank" rel="noopener noreferrer" class="chico enlace-meta" @click.stop>
                  Ver sus anuncios en Meta <Icono nombre="externo" />
                </a>
              </span>
              <span v-if="c.ejemplos?.length" class="ejemplos" aria-label="Ejemplos de sus anuncios">
                <img v-for="(e, i) in c.ejemplos" :key="i" :src="e" alt="" loading="lazy" referrerpolicy="no-referrer" @error="($event.target as HTMLImageElement).style.display = 'none'" />
              </span>
            </label>
          </li>
        </ul>
        <div class="fila">
          <button class="boton boton-primario" type="button" :disabled="ocupado || !marcadas.length" @click="elegir(a.pendiente!.competidor, marcadas)">
            {{ marcadas.length > 1 ? `Usar estas ${marcadas.length} páginas` : 'Usar esta página' }}
          </button>
          <button class="boton boton-fantasma" type="button" :disabled="ocupado" @click="elegir(a.pendiente!.competidor, [])">
            Ninguna: dejar fuera a {{ a.pendiente.competidor }}
          </button>
        </div>
      </section>

      <!-- Pausa con error -->
      <div v-if="a.estado === 'pausado' && a.error && !a.pendiente" class="aviso aviso-ambar" role="alert">
        <Icono nombre="pausa" />
        <div class="aviso-cuerpo">
          <strong>El análisis se ha pausado.</strong> {{ a.error }}
          <span v-if="a.hechos" class="tenue"> Lo analizado ({{ a.hechos }} anuncios) está guardado.</span>
        </div>
      </div>

      <div class="fila acciones">
        <RouterLink v-if="a.estado === 'terminado' && a.codInforme" :to="`/informes/${a.codInforme}`" class="boton boton-exito">
          <Icono nombre="lista" /> Abrir el informe
        </RouterLink>
        <button v-if="a.estado === 'pausado' && !a.pendiente" class="boton boton-primario" type="button" :disabled="ocupado" @click="continuar">
          <Icono nombre="reintentar" /> Continuar donde se quedó
        </button>
        <button v-if="puedeTerminar" class="boton boton-aviso" type="button" :disabled="ocupado" @click="terminar">
          Terminar con lo analizado
        </button>
        <button v-if="a.estado !== 'terminado' && a.estado !== 'cancelado'" class="boton boton-peligro" type="button" :disabled="ocupado" @click="cancelar">
          Cancelar
        </button>
        <button v-if="!activo" class="boton boton-fantasma" type="button" @click="borrar"><Icono nombre="basura" /> Borrar análisis</button>
      </div>

      <section class="panel resumen-peticion">
        <h3>Qué se está analizando</h3>
        <ul class="lista-plana chico">
          <li v-for="c in a.peticion.competidores" :key="c.nombre"><span class="chip">nivel {{ c.nivel }}</span> {{ c.nombre }}</li>
          <li v-for="k in a.peticion.keywords" :key="k" class="suave">palabra clave: {{ k }}</li>
        </ul>
      </section>
    </template>
  </div>
</template>

<style scoped>
.estrecha {
  max-width: 860px;
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
.fases {
  list-style: none;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.fases li {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid var(--borde);
  color: var(--texto-tenue);
  font-size: 0.88rem;
}
.fases li.actual {
  border-color: var(--cian);
  color: var(--cian);
  background: var(--cian-fondo);
}
.fases li.hecha {
  color: var(--lima);
  border-color: rgba(163, 230, 53, 0.4);
}
.punto {
  width: 14px;
  height: 14px;
  display: inline-flex;
}
.punto svg {
  width: 14px;
  height: 14px;
}
.avance p {
  display: flex;
  gap: 8px;
  align-items: center;
}
.avance svg {
  width: 16px;
  height: 16px;
}
.pista {
  height: 10px;
  border-radius: 5px;
  background: var(--panel-3);
  overflow: hidden;
  margin: 10px 0 6px;
}
.relleno {
  height: 100%;
  background: var(--cian);
  transition: width 0.4s;
}
.acciones {
  margin: 16px 0;
}
.panel + .panel,
.aviso + .fila {
  margin-top: 16px;
}
.candidatas {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.candidata {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 14px;
  border: 1px solid var(--borde);
  border-radius: var(--radio);
  background: var(--panel-2);
  cursor: pointer;
}
.candidata:hover {
  border-color: var(--borde-fuerte);
}
.candidata.marcada {
  border-color: var(--cian);
  background: var(--cian-fondo);
}
.candidata input {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}
.avatar {
  flex: 0 0 56px;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  overflow: hidden;
  background: var(--panel-3);
  display: grid;
  place-items: center;
  color: var(--texto-tenue);
}
.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.avatar svg {
  width: 22px;
  height: 22px;
}
.datos {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.datos .texto {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.enlace-meta {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  align-self: flex-start;
}
.enlace-meta svg {
  width: 13px;
  height: 13px;
}
.ejemplos {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
.ejemplos img {
  width: 64px;
  height: 64px;
  object-fit: cover;
  border-radius: var(--radio-chico);
  background: var(--panel-3);
}
@media (max-width: 700px) {
  .candidata {
    flex-wrap: wrap;
  }
  .ejemplos {
    width: 100%;
    padding-left: 32px;
  }
}
.resumen-peticion li {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 3px 0;
}
</style>
