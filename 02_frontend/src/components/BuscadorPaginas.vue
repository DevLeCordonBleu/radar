<script setup lang="ts">
/**
 * Nombre de un competidor (o de tu marca) con sugerencias de sus páginas de Facebook.
 *
 * Al escribir 3 letras o más (y parar un cuarto de segundo) pide a la Biblioteca de Meta
 * las páginas que coinciden y las muestra con foto, categoría y seguidores. Se
 * pueden marcar varias (sedes, talleres…): el análisis buscará por ellas y no
 * tendrá que adivinar cuál es. Escribir el nombre o pegar un enlace sigue valiendo.
 *
 * Para que no se note la espera: lo ya consultado se recuerda (en todo el panel) y,
 * mientras llega la respuesta, se muestran las páginas de la búsqueda anterior que
 * siguen encajando con lo escrito.
 *
 * Con páginas marcadas, el nombre es el de la primera: lo que se escribe en la caja es
 * solo para buscar y, al salir de ella, vuelve a mostrar ese nombre.
 *
 * Teclado: ↓ ↑ para moverse, Enter para marcar/desmarcar, Escape para cerrar.
 */
import { computed, onBeforeUnmount, ref, useId, watch } from 'vue'
import { analisis } from '@/api/radar'
import type { PaginaMeta, SugerenciaPagina } from '@/api/tipos'
import Icono from './Icono.vue'

/** Sugerencias ya pedidas, compartidas por todos los buscadores del panel (país|texto). */
const recordadas = new Map<string, SugerenciaPagina[]>()
function recordar(clave: string, paginas: SugerenciaPagina[]) {
  if (recordadas.size >= 200) recordadas.delete(recordadas.keys().next().value!)
  recordadas.set(clave, paginas)
}

const props = withDefaults(defineProps<{ pais: string; etiqueta: string; placeholder?: string; pie?: string }>(), {
  placeholder: 'Escribe su nombre (3 letras) o pega el enlace de su página',
  pie: 'Marca todas las que sean de este competidor (sedes, talleres…).',
})
const nombre = defineModel<string>('nombre', { required: true })
const paginas = defineModel<PaginaMeta[]>('paginas', { default: () => [] })

const id = useId()
const caja = ref<HTMLInputElement | null>(null)
const abierto = ref(false)
const cargando = ref(false)
const error = ref('')
const sugerencias = ref<SugerenciaPagina[]>([])
const activa = ref(-1)
let espera: ReturnType<typeof setTimeout> | null = null
let pedido = 0

/** Sin tildes ni mayúsculas, para comparar lo escrito con los nombres. */
const plano = (t: string) => t.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/\s+/g, ' ').trim()
/** Lo que se escribe mientras llega la respuesta: lo anterior que siga encajando. */
const provisional = (t: string) => {
  const palabras = plano(t).split(' ')
  return sugerencias.value.filter((s) => palabras.every((p) => plano(s.nombre).includes(p)))
}

const elegidas = computed(() => new Set(paginas.value.map((p) => p.pageId)))
/** Un enlace o un id ya apuntan a una página: no hace falta sugerir. */
const esEnlace = (t: string) => /^(https?:\/\/|www\.|\d{6,}$)/i.test(t.trim()) || /facebook\.com|instagram\.com|fb\.com/i.test(t)

function alEscribir() {
  if (espera) clearTimeout(espera)
  const t = nombre.value.trim()
  error.value = ''
  if (t.length < 3 || esEnlace(t)) {
    sugerencias.value = []
    abierto.value = false
    cargando.value = false
    return
  }
  const ya = recordadas.get(`${props.pais}|${plano(t)}`)
  if (ya) {
    pedido++ // lo que estuviera en camino ya no vale
    mostrar(ya)
    cargando.value = false
    return
  }
  if (sugerencias.value.length) {
    const quedan = provisional(t)
    sugerencias.value = quedan
    activa.value = quedan.length ? 0 : -1
  }
  espera = setTimeout(() => buscar(t), 250)
}

/** Si el Chrome de las sugerencias se cerró por inactividad, se abre ya, antes de escribir. */
function alEnfocar() {
  if (sugerencias.value.length) abierto.value = true
  analisis.prepararPaginas(props.pais).catch(() => {})
}

function mostrar(paginas: SugerenciaPagina[]) {
  sugerencias.value = paginas
  activa.value = paginas.length ? 0 : -1
  abierto.value = true
}

async function buscar(t: string) {
  const mio = ++pedido
  cargando.value = true
  abierto.value = true
  try {
    const r = await analisis.paginas(t, props.pais)
    recordar(`${props.pais}|${plano(t)}`, r.paginas)
    if (mio !== pedido) return // llegó tarde: ya se escribió otra cosa
    sugerencias.value = r.paginas
    activa.value = r.paginas.length ? 0 : -1
  } catch (e) {
    if (mio !== pedido) return
    sugerencias.value = []
    error.value = e instanceof Error ? e.message : 'No se pudieron pedir sugerencias.'
  } finally {
    if (mio === pedido) cargando.value = false
  }
}

function alternar(s: SugerenciaPagina) {
  if (elegidas.value.has(s.page_id)) {
    quitar(s.page_id)
    return
  }
  paginas.value = [...paginas.value, { pageId: s.page_id, nombre: s.nombre, avatar: s.avatar, categoria: s.categoria, seguidores: s.seguidores }]
  nombrar()
}

function quitar(pageId: string) {
  paginas.value = paginas.value.filter((p) => p.pageId !== pageId)
  nombrar()
}

/** El nombre es el de la primera página marcada (sin lanzar otra búsqueda por el cambio). */
let sinBuscar = false
function nombrar() {
  const primera = paginas.value[0]?.nombre
  if (!primera || nombre.value === primera) return
  sinBuscar = true
  nombre.value = primera
}

function tecla(e: KeyboardEvent) {
  if (!abierto.value || !sugerencias.value.length) {
    if (e.key === 'ArrowDown' && sugerencias.value.length) abierto.value = true
    return
  }
  if (e.key === 'ArrowDown') activa.value = (activa.value + 1) % sugerencias.value.length
  else if (e.key === 'ArrowUp') activa.value = (activa.value - 1 + sugerencias.value.length) % sugerencias.value.length
  else if (e.key === 'Enter' && activa.value >= 0) alternar(sugerencias.value[activa.value])
  else if (e.key === 'Escape') abierto.value = false
  else return
  e.preventDefault()
}

// Cerrar al salir del componente (con un respiro para que el clic en una opción cuente).
let cierre: ReturnType<typeof setTimeout> | null = null
const alSalir = () =>
  (cierre = setTimeout(() => {
    abierto.value = false
    nombrar() // lo que quedó a medio escribir era una búsqueda, no el nombre
  }, 150))
const alEntrar = () => {
  if (cierre) clearTimeout(cierre)
}

// Se busca cuando la persona escribe (la caja tiene el foco), no cuando el texto llega de «mi mercado».
watch(nombre, () => {
  if (sinBuscar) sinBuscar = false
  else if (document.activeElement === caja.value) alEscribir()
})
watch(() => props.pais, () => (sugerencias.value = []))
onBeforeUnmount(() => {
  if (espera) clearTimeout(espera)
  if (cierre) clearTimeout(cierre)
})

/** Las fotos de Facebook caducan a los pocos días: si ya no cargan, no se deja un hueco roto. */
const ocultar = (e: Event) => ((e.target as HTMLImageElement).style.display = 'none')

const decimal = new Intl.NumberFormat('es-PE', { maximumFractionDigits: 1 })
/** «193,5 mil seguidores», «2,6 mil», «1,2 M»: como lo muestra Facebook. */
function seguidores(n: number | null | undefined): string {
  if (n == null) return ''
  const t = n >= 1e6 ? `${decimal.format(n / 1e6)} M` : n >= 1000 ? `${decimal.format(n / 1000)} mil` : String(n)
  return `${t} seguidores`
}
</script>

<template>
  <div class="buscador" @focusout="alSalir" @focusin="alEntrar">
    <div class="caja">
      <input
        ref="caja"
        v-model="nombre"
        type="text"
        role="combobox"
        :aria-label="etiqueta"
        :aria-expanded="abierto"
        :aria-controls="`${id}-lista`"
        aria-autocomplete="list"
        :aria-activedescendant="abierto && activa >= 0 ? `${id}-op-${activa}` : undefined"
        :placeholder="placeholder"
        autocomplete="off"
        @keydown="tecla"
        @focus="alEnfocar"
      />
      <span v-if="cargando" class="girando" aria-hidden="true"></span>
      <div v-if="abierto" class="desplegable" @mousedown.prevent>
        <p v-if="cargando && !sugerencias.length" class="estado">Buscando sus páginas en Meta…</p>
        <p v-else-if="error" class="estado error">{{ error }}</p>
        <p v-else-if="!sugerencias.length" class="estado">Meta no sugiere ninguna página con ese nombre. Prueba otra forma de escribirlo o pega el enlace.</p>
        <ul v-if="sugerencias.length" :id="`${id}-lista`" role="listbox" aria-multiselectable="true" :aria-label="`Páginas para ${etiqueta}`">
          <li
            v-for="(s, i) in sugerencias"
            :id="`${id}-op-${i}`"
            :key="s.page_id"
            role="option"
            :aria-selected="elegidas.has(s.page_id)"
            :class="{ activa: i === activa, elegida: elegidas.has(s.page_id) }"
            @click="alternar(s)"
            @mouseenter="activa = i"
          >
            <span class="marca" aria-hidden="true"><Icono v-if="elegidas.has(s.page_id)" nombre="ok" /></span>
            <img v-if="s.avatar" :src="s.avatar" alt="" referrerpolicy="no-referrer" loading="lazy" @error="ocultar" />
            <span v-else class="sin-foto" aria-hidden="true">{{ s.nombre.charAt(0) }}</span>
            <span class="datos">
              <strong>{{ s.nombre }}<Icono v-if="s.verificada" nombre="aprobar" class="verificada" /></strong>
              <small>{{ [s.categoria, seguidores(s.seguidores), s.ig_usuario ? `@${s.ig_usuario}` : ''].filter(Boolean).join(' · ') }}</small>
            </span>
          </li>
        </ul>
        <p v-if="sugerencias.length" class="pie">{{ pie }}</p>
      </div>
    </div>

    <ul v-if="paginas.length" class="elegidas" aria-label="Páginas elegidas">
      <li v-for="p in paginas" :key="p.pageId">
        <img v-if="p.avatar" :src="p.avatar" alt="" referrerpolicy="no-referrer" @error="ocultar" />
        <span>{{ p.nombre }}</span>
        <button type="button" :aria-label="`Quitar la página ${p.nombre}`" @click="quitar(p.pageId)"><Icono nombre="x" /></button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.buscador {
  position: relative;
  flex: 1;
  min-width: 0;
}
.caja {
  position: relative;
}
.caja input {
  width: 100%;
  padding-right: 34px;
}
.girando {
  position: absolute;
  right: 12px;
  top: 50%;
  width: 16px;
  height: 16px;
  margin-top: -8px;
  border: 2px solid var(--borde-fuerte);
  border-top-color: var(--cian);
  border-radius: 50%;
  animation: girar 0.8s linear infinite;
}
@keyframes girar {
  to {
    transform: rotate(360deg);
  }
}
@media (prefers-reduced-motion: reduce) {
  .girando {
    animation-duration: 3s;
  }
}
.desplegable {
  position: absolute;
  z-index: 20;
  left: 0;
  right: 0;
  top: calc(100% + 4px);
  background: var(--panel);
  border: 1px solid var(--borde-fuerte);
  border-radius: var(--radio);
  box-shadow: var(--sombra);
  max-height: 360px;
  overflow-y: auto;
  padding: 4px;
}
.estado,
.pie {
  padding: 10px 12px;
  font-size: 0.85rem;
  color: var(--texto-suave);
}
.estado.error {
  color: var(--rojo);
}
.pie {
  border-top: 1px solid var(--borde);
  padding-block: 8px;
  font-size: 0.78rem;
  color: var(--texto-tenue);
}
ul[role='listbox'] {
  list-style: none;
}
li[role='option'] {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: var(--radio-chico);
  cursor: pointer;
}
li[role='option'].activa {
  background: var(--panel-2);
}
li[role='option'].elegida {
  background: var(--cian-fondo);
}
.marca {
  flex: none;
  width: 18px;
  height: 18px;
  border: 1.5px solid var(--borde-fuerte);
  border-radius: 4px;
  display: grid;
  place-items: center;
  color: var(--cian);
}
.elegida .marca {
  border-color: var(--cian);
}
.marca svg {
  width: 13px;
  height: 13px;
}
li[role='option'] img,
.sin-foto {
  flex: none;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  object-fit: cover;
  background: var(--panel-3);
}
.sin-foto {
  display: grid;
  place-items: center;
  font-weight: 700;
  color: var(--texto-suave);
}
.datos {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.datos strong {
  font-size: 0.92rem;
  overflow-wrap: anywhere;
}
.datos small {
  color: var(--texto-tenue);
  font-size: 0.78rem;
  overflow-wrap: anywhere;
}
.verificada {
  width: 13px;
  height: 13px;
  margin-left: 4px;
  vertical-align: -1px;
  color: var(--cian);
}
.elegidas {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.elegidas li {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  padding: 3px 4px 3px 4px;
  border: 1px solid var(--borde-fuerte);
  border-radius: 999px;
  background: var(--panel-2);
  font-size: 0.82rem;
}
.elegidas img {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  object-fit: cover;
}
.elegidas span {
  overflow-wrap: anywhere;
  padding-left: 2px;
}
.elegidas button {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border: 0;
  border-radius: 50%;
  background: none;
  color: var(--texto-suave);
  cursor: pointer;
}
.elegidas button:hover {
  background: var(--panel-3);
  color: var(--texto);
}
.elegidas button svg {
  width: 13px;
  height: 13px;
}
</style>
