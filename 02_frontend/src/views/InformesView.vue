<script setup lang="ts">
/** Inicio: los análisis en curso o pausados y los informes terminados. */
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { analisis, informes } from '@/api/radar'
import type { Analisis, InformeFila } from '@/api/tipos'
import Icono from '@/components/Icono.vue'
import { confirmar } from '@/composables/confirmar'
import { CLASE_ESTADO, ETIQUETA_ESTADO, fecha, pct } from '@/composables/formato'
import { useSondeo } from '@/composables/sondeo'
import { useAvisos } from '@/stores/avisos'

const avisos = useAvisos()
const lista = ref<InformeFila[]>([])
const trabajos = ref<Analisis[]>([])
const archivados = ref(false)
const cargando = ref(true)

/** Lo que sigue vivo: en marcha, en cola o pausado esperando a la persona. */
const abiertos = computed(() => trabajos.value.filter((a) => a.estado !== 'terminado' && a.estado !== 'cancelado'))
const enMarcha = computed(() => abiertos.value.some((a) => a.estado === 'corriendo' || a.estado === 'en_cola'))
const sinNada = computed(() => !cargando.value && !lista.value.length && !abiertos.value.length)

async function cargar() {
  try {
    ;[lista.value, trabajos.value] = await Promise.all([informes.listar(archivados.value), analisis.listar()])
  } catch (e) {
    avisos.error(e, 'No se pudo cargar la lista')
  } finally {
    cargando.value = false
  }
}

onMounted(cargar)
useSondeo(
  async () => {
    trabajos.value = await analisis.listar()
    if (!enMarcha.value) lista.value = await informes.listar(archivados.value)
  },
  () => enMarcha.value,
  4000,
)

async function ejemplo() {
  try {
    await informes.crearEjemplo()
    avisos.exito('Informe de ejemplo creado: son anuncios inventados para que veas cómo se lee.')
    await cargar()
  } catch (e) {
    avisos.error(e)
  }
}

async function borrar(f: InformeFila) {
  const r = await confirmar({
    titulo: `¿Borrar el informe de ${f.marca || f.codigo}?`,
    mensaje: 'Desaparece de la lista.',
    aceptar: 'Borrar',
    tono: 'peligro',
  })
  if (!r.ok) return
  try {
    await informes.borrar(f.codigo)
    await cargar()
  } catch (e) {
    avisos.error(e)
  }
}

async function archivar(f: InformeFila) {
  try {
    await informes.archivar(f.codigo, !f.archivado)
    await cargar()
  } catch (e) {
    avisos.error(e)
  }
}

const progreso = (a: Analisis) => (a.total > 0 ? Math.round((a.hechos / a.total) * 100) : 0)
</script>

<template>
  <div class="pagina">
    <div class="pagina-cabecera">
      <div>
        <h1>Informes</h1>
        <p>Qué anuncia tu competencia en Facebook e Instagram, qué repite todo el mundo y dónde está el hueco.</p>
      </div>
      <div class="fila">
        <label class="casilla chico">
          <input v-model="archivados" type="checkbox" @change="cargar" /> ver archivados
        </label>
        <RouterLink to="/" class="boton boton-primario"><Icono nombre="mas" /> Nuevo análisis</RouterLink>
      </div>
    </div>

    <p v-if="cargando" class="cargando suave">Cargando…</p>

    <section v-if="abiertos.length" class="panel" aria-label="Análisis en curso">
      <div class="panel-titulo"><h2>En curso</h2></div>
      <ul class="lista-plana trabajos">
        <li v-for="a in abiertos" :key="a.codigo">
          <RouterLink :to="`/analisis/${a.codigo}`" class="trabajo">
            <span class="chip" :class="CLASE_ESTADO[a.estado]">{{ ETIQUETA_ESTADO[a.estado] }}</span>
            <span class="titulo">
              {{ a.peticion.misMarcas.join(' y ') || a.peticion.competidores.map((c) => c.nombre).slice(0, 3).join(', ') }}
            </span>
            <span class="suave chico mensaje">{{ a.pendiente ? `Falta elegir la página de ${a.pendiente.competidor}` : a.error || a.mensaje }}</span>
            <span v-if="a.total" class="tenue chico num">{{ a.hechos }}/{{ a.total }} · {{ progreso(a) }} %</span>
          </RouterLink>
        </li>
      </ul>
    </section>

    <div v-if="sinNada" class="panel vacio-inicio">
      <Icono nombre="radar" class="grande" />
      <h2>Aún no hay ningún informe</h2>
      <p class="suave">
        Un informe tarda unos minutos: indicas tus competidores, la herramienta descarga sus anuncios activos y los
        analiza con IA. Si solo quieres ver cómo se lee, abre uno de ejemplo.
      </p>
      <div class="fila" style="justify-content: center">
        <RouterLink to="/" class="boton boton-primario"><Icono nombre="mas" /> Hacer mi primer análisis</RouterLink>
        <button class="boton" type="button" @click="ejemplo"><Icono nombre="chispa" /> Ver un informe de ejemplo</button>
      </div>
    </div>

    <section v-if="lista.length" class="rejilla rejilla-3 informes" aria-label="Informes">
      <article v-for="f in lista" :key="f.codigo" class="panel informe" :class="{ archivado: f.archivado }">
        <header>
          <RouterLink :to="`/informes/${f.codigo}`" class="nombre">{{ f.marca || 'Informe ' + f.codigo }}</RouterLink>
          <span v-if="f.esEjemplo" class="chip chip-ambar">ejemplo</span>
          <span v-if="f.archivado" class="chip">archivado</span>
        </header>
        <p class="tenue chico num">{{ fecha(f.creado) }} · {{ f.anuncios }} anuncios · {{ f.anunciantes }} anunciantes</p>
        <dl v-if="f.portada" class="portada">
          <template v-if="f.portada.territorio">
            <dt>Satura</dt>
            <dd>{{ f.portada.territorio }} <span class="tenue num" v-if="f.portada.pct != null">({{ pct(f.portada.pct) }})</span></dd>
          </template>
          <template v-if="f.portada.hueco">
            <dt>Casi libre</dt>
            <dd>{{ f.portada.hueco }}</dd>
          </template>
        </dl>
        <div class="fila acciones">
          <RouterLink :to="`/informes/${f.codigo}`" class="boton boton-chico boton-primario">Abrir</RouterLink>
          <button class="boton boton-chico boton-fantasma" type="button" @click="archivar(f)">
            {{ f.archivado ? 'Recuperar' : 'Archivar' }}
          </button>
          <button class="boton boton-chico boton-fantasma" type="button" aria-label="Borrar informe" @click="borrar(f)">
            <Icono nombre="basura" />
          </button>
        </div>
      </article>
    </section>
  </div>
</template>

<style scoped>
.trabajos {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.trabajo {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 12px;
  border: 1px solid var(--borde);
  border-radius: var(--radio-chico);
  color: var(--texto);
  background: var(--panel-2);
}
.trabajo:hover {
  text-decoration: none;
  border-color: var(--borde-fuerte);
}
.trabajo .titulo {
  font-weight: 600;
}
.trabajo .mensaje {
  flex: 1;
  min-width: 160px;
}
.vacio-inicio {
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
  padding: 40px 24px;
  max-width: 640px;
  margin: 24px auto;
}
.grande {
  width: 48px;
  height: 48px;
  color: var(--cian);
}
.informes {
  margin-top: 16px;
}
.informe {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.informe + .informe {
  margin-top: 0;
}
.informe.archivado {
  opacity: 0.7;
}
.informe header {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.nombre {
  font-weight: 700;
  font-size: 1.05rem;
}
.portada {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 2px 12px;
  font-size: 0.9rem;
}
.portada dt {
  color: var(--texto-suave);
}
.acciones {
  margin-top: auto;
  padding-top: 6px;
}
</style>
