<script setup lang="ts">
/**
 * Una página propia que Google ya muestra en la posición 4-20 para búsquedas sin marca.
 * La IA propone título, descripción y cambios en el texto, cada uno con lo que dice ahora y lo
 * que debe decir; la persona los aplica en WordPress y la marca como aplicada (el Radar no
 * cambia páginas publicadas). Los términos protegidos (carreras, sistemas) no se cambian.
 */
import { computed, ref } from 'vue'
import { seo } from '@/api/radar'
import type { MejoraSeo, OportunidadPagina } from '@/api/tipos'
import Icono from '@/components/Icono.vue'
import { fechaHora } from '@/composables/formato'
import { useAvisos } from '@/stores/avisos'

const props = defineProps<{ oportunidad: OportunidadPagina }>()
const emit = defineEmits<{ cambio: [mejora: MejoraSeo] }>()
const avisos = useAvisos()
const ocupado = ref(false)
const entero = new Intl.NumberFormat('es-PE')

const o = computed(() => props.oportunidad)
const m = computed(() => o.value.mejora)
const ruta = computed(() => {
  try {
    const u = new URL(o.value.url)
    return u.hostname.replace(/^www\./, '') === 'ilcb.edu.pe' ? u.pathname : `${u.hostname}${u.pathname}`
  } catch {
    return o.value.url
  }
})
/** Título, descripción e ideas con la misma forma: dónde, qué dice ahora y qué debe decir. */
const cambios = computed(() => {
  const x = m.value
  if (!x) return []
  return [
    { clave: 'titulo', donde: 'Título SEO', ahora: x.tituloActual, vacio: '(sin título)', nuevo: x.titulo, limite: 60 },
    { clave: 'meta', donde: 'Meta descripción', ahora: x.metaActual, vacio: '(sin descripción)', nuevo: x.metaDescription, limite: 155 },
    ...x.ideas.map((i, n) => ({
      clave: `idea-${n}`,
      donde: i.donde || 'Contenido',
      ahora: i.diceAhora,
      // Las propuestas antiguas no traían el lugar ni el texto actual.
      vacio: i.donde ? '(no existe: es nuevo)' : '(propuesta antigua: sin el texto actual)',
      nuevo: i.debeDecir,
      limite: 0,
    })),
  ]
})

const ESTADO: Record<MejoraSeo['estado'], { texto: string; chip: string }> = {
  PROPUESTA: { texto: 'propuesta', chip: 'chip-cian' },
  APLICADA: { texto: 'aplicada', chip: 'chip-lima' },
  DESCARTADA: { texto: 'descartada', chip: '' },
}

async function proponer() {
  ocupado.value = true
  try {
    emit('cambio', await seo.proponerMejora(o.value.url))
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

async function marcar(estado: MejoraSeo['estado']) {
  ocupado.value = true
  try {
    emit('cambio', await seo.estadoMejora(o.value.url, estado))
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

async function copiar(texto: string, que: string) {
  try {
    await navigator.clipboard.writeText(texto)
    avisos.exito(`${que} copiado.`)
  } catch {
    avisos.error(new Error('No se pudo copiar: selecciónalo y cópialo a mano.'))
  }
}
</script>

<template>
  <article class="mejora" :class="{ apagada: m?.estado === 'DESCARTADA' }">
    <header class="fila cabeza">
      <a :href="o.url" target="_blank" rel="noopener" class="ruta">{{ ruta }}</a>
      <span v-if="m" class="chip" :class="ESTADO[m.estado].chip">{{ ESTADO[m.estado].texto }}</span>
    </header>
    <p class="chico suave cifras">
      Posición media <strong>{{ o.posicion.toFixed(1) }}</strong> · {{ entero.format(o.impresiones) }} impresiones ·
      {{ entero.format(o.clics) }} clics · {{ (o.ctr * 100).toFixed(1) }} % de clics
    </p>
    <ul class="busquedas chico">
      <li v-for="c in o.consultas" :key="c.consulta">
        {{ c.consulta }} <span class="tenue">· pos {{ c.posicion.toFixed(1) }} · {{ entero.format(c.impresiones) }}</span>
      </li>
    </ul>

    <template v-if="m">
      <p v-if="m.motivo" class="chico"><strong>Por qué:</strong> {{ m.motivo }}</p>
      <div class="cambios">
        <div v-for="c in cambios" :key="c.clave" class="cambio">
          <p class="etiqueta">{{ c.donde }}</p>
          <div class="par">
            <div>
              <p class="rotulo">Dice ahora</p>
              <p class="actual" :class="{ tenue: !c.ahora }">{{ c.ahora || c.vacio }}</p>
            </div>
            <div>
              <p class="rotulo">Debe decir</p>
              <p class="nuevo">
                {{ c.nuevo }} <span v-if="c.limite" class="tenue cuenta">{{ c.nuevo.length }}/{{ c.limite }}</span>
                <button class="boton-texto" type="button" :title="`Copiar: ${c.donde}`" @click="copiar(c.nuevo, c.donde)"><Icono nombre="copiar" /></button>
              </p>
            </div>
          </div>
        </div>
      </div>
      <p class="chico tenue">Propuesta del {{ fechaHora(m.creado) }}. Aplícala en WordPress y márcala aquí.</p>
      <div class="fila acciones">
        <button v-if="m.estado !== 'APLICADA'" class="boton boton-primario" type="button" :disabled="ocupado" @click="marcar('APLICADA')">
          <Icono nombre="ok" /> Ya la apliqué
        </button>
        <button v-if="m.estado === 'PROPUESTA'" class="boton" type="button" :disabled="ocupado" @click="marcar('DESCARTADA')">
          <Icono nombre="x" /> Descartar
        </button>
        <button class="boton" type="button" :disabled="ocupado" @click="proponer"><Icono nombre="chispa" /> Proponer otra</button>
      </div>
    </template>
    <div v-else class="fila acciones">
      <button class="boton" type="button" :disabled="ocupado" @click="proponer">
        <Icono nombre="chispa" /> {{ ocupado ? 'Pensando…' : 'Proponer mejora con IA' }}
      </button>
    </div>
  </article>
</template>

<style scoped>
.mejora {
  border: 1px solid var(--borde);
  border-radius: var(--radio);
  padding: 12px 14px;
  display: grid;
  gap: 8px;
  min-width: 0;
}
.mejora.apagada {
  opacity: 0.6;
}
.mejora svg {
  width: 14px;
  height: 14px;
  vertical-align: -2px;
}
.cabeza {
  justify-content: space-between;
  gap: 8px;
}
.ruta {
  font-weight: 600;
  overflow-wrap: anywhere;
}
.cifras,
.mejora p {
  margin: 0;
}
.busquedas {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
}
.cambios {
  display: grid;
  gap: 10px;
  border-top: 1px solid var(--borde);
  padding-top: 8px;
}
.cambio {
  display: grid;
  gap: 4px;
}
.par {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr));
  gap: 6px 12px;
}
.par > div {
  border: 1px solid var(--borde);
  border-radius: 8px;
  padding: 6px 10px;
  min-width: 0;
}
.par > div:last-child {
  border-color: rgba(34, 211, 238, 0.45);
  background: var(--cian-fondo);
}
.rotulo {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--texto-suave);
}
.etiqueta {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--texto-suave);
}
.actual {
  font-size: 0.85rem;
  overflow-wrap: anywhere;
  white-space: pre-line;
}
.nuevo {
  font-weight: 600;
  overflow-wrap: anywhere;
  white-space: pre-line;
}
.cuenta {
  font-weight: 400;
  font-size: 0.75rem;
}
.boton-texto {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--cian);
  padding: 0 2px;
}
.acciones {
  gap: 8px;
  flex-wrap: wrap;
}
</style>
