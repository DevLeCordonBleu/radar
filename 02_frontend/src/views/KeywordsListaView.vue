<script setup lang="ts">
/** KeyWords Explorer · una lista: sus keywords con métricas, notas, actualización y exportación. */
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { keywords } from '@/api/radar'
import type { FilaKeyword, ListaKeywords } from '@/api/tipos'
import Icono from '@/components/Icono.vue'
import TablaKeywords from '@/components/TablaKeywords.vue'
import { confirmar } from '@/composables/confirmar'
import { useEstadoKeywords } from '@/composables/estadoKeywords'
import { fechaHora } from '@/composables/formato'
import { aCsv, descargarCsv, num } from '@/composables/keywords'
import { useAvisos } from '@/stores/avisos'

const props = defineProps<{ codigo: string }>()
const avisos = useAvisos()
const router = useRouter()
const { estado, cargar } = useEstadoKeywords()

const lista = ref<ListaKeywords | null>(null)
const items = ref<FilaKeyword[]>([])
const seleccion = ref<Set<string>>(new Set())
const cargando = ref(true)
const error = ref('')
const actualizando = ref(false)
const editando = ref(false)
const nombre = ref('')
const descripcion = ref('')

const pais = computed(() => estado.value?.paises[lista.value?.pais ?? ''] ?? lista.value?.pais ?? '')
const moneda = computed(() => (lista.value?.demo ? 'USD' : null))
const seleccionadas = computed(() => items.value.filter((f) => seleccion.value.has(f.keyword.toLowerCase())))

async function recargar() {
  try {
    const d = await keywords.lista(props.codigo)
    lista.value = d.lista
    items.value = d.items
    nombre.value = d.lista.nombre
    descripcion.value = d.lista.descripcion
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    cargando.value = false
  }
}
onMounted(async () => {
  await cargar()
  await recargar()
})

async function guardarNombre() {
  try {
    lista.value = await keywords.renombrarLista(props.codigo, nombre.value, descripcion.value)
    editando.value = false
  } catch (e) {
    avisos.error(e)
  }
}

async function guardarNota(keyword: string, texto: string) {
  try {
    await keywords.nota(props.codigo, keyword, texto)
    const f = items.value.find((x) => x.keyword === keyword)
    if (f) f.nota = texto.trim()
  } catch (e) {
    avisos.error(e, 'No se pudo guardar la nota')
  }
}

async function actualizar() {
  actualizando.value = true
  try {
    const r = await keywords.actualizarLista(props.codigo)
    avisos.exito(`${r.actualizadas} keywords actualizadas con las métricas de hoy.`)
    await recargar()
  } catch (e) {
    avisos.error(e, 'No se pudo actualizar')
  } finally {
    actualizando.value = false
  }
}

async function quitar() {
  const r = await confirmar({ titulo: `¿Quitar ${seleccionadas.value.length} keywords de la lista?`, aceptar: 'Quitar', tono: 'peligro' })
  if (!r.ok) return
  try {
    await keywords.quitar(props.codigo, seleccionadas.value.map((f) => f.keyword))
    seleccion.value = new Set()
    await recargar()
  } catch (e) {
    avisos.error(e)
  }
}

function exportar() {
  if (!lista.value) return
  const filas = seleccionadas.value.length ? seleccionadas.value : items.value
  descargarCsv(`lista-${lista.value.nombre}`, aCsv(filas, pais.value, moneda.value))
}

async function borrar() {
  const r = await confirmar({ titulo: '¿Borrar esta lista?', mensaje: 'Se eliminan sus keywords y sus notas.', aceptar: 'Borrar', tono: 'peligro' })
  if (!r.ok) return
  try {
    await keywords.borrarLista(props.codigo)
    await router.push('/keywords/listas')
  } catch (e) {
    avisos.error(e)
  }
}

function abrir(k: string) {
  void router.push({ name: 'keywords-resultados', query: { q: [k], pais: lista.value?.pais, idioma: lista.value?.idioma, demo: lista.value?.demo ? '1' : undefined } })
}
</script>

<template>
  <div class="pagina">
    <p v-if="cargando" class="cargando suave">Cargando…</p>
    <div v-else-if="error" class="aviso aviso-error" role="alert"><Icono nombre="error" /><div class="aviso-cuerpo">{{ error }}</div></div>

    <template v-else-if="lista">
      <div class="pagina-cabecera">
        <div>
          <RouterLink to="/keywords/listas" class="chico volver"><Icono nombre="volver" /> Mis listas</RouterLink>
          <h1>{{ lista.nombre }}</h1>
          <p class="fila">
            <span class="chip">{{ pais }}</span>
            <span v-if="lista.demo" class="chip chip-ambar">datos de demostración</span>
            <span class="tenue chico num">{{ num(lista.keywords) }} keywords · {{ num(lista.volumenTotal) }} búsquedas/mes · actualizada {{ fechaHora(lista.modificado) }}</span>
          </p>
          <p v-if="lista.descripcion" class="suave">{{ lista.descripcion }}</p>
        </div>
        <div class="fila">
          <button class="boton" type="button" :disabled="actualizando || !items.length" title="Vuelve a pedir las métricas a Google" @click="actualizar"><Icono nombre="reintentar" /> {{ actualizando ? 'Actualizando…' : 'Actualizar métricas' }}</button>
          <button class="boton" type="button" :disabled="!items.length" @click="exportar"><Icono nombre="bajar" /> Exportar CSV{{ seleccionadas.length ? ` (${seleccionadas.length})` : '' }}</button>
          <button class="boton" type="button" @click="editando = !editando"><Icono nombre="lapiz" /> Renombrar</button>
          <button class="boton boton-peligro" type="button" @click="borrar"><Icono nombre="basura" /> Borrar</button>
        </div>
      </div>

      <form v-if="editando" class="panel pila" @submit.prevent="guardarNombre">
        <div class="campo"><label for="le-n">Nombre</label><input id="le-n" v-model="nombre" type="text" maxlength="80" required /></div>
        <div class="campo"><label for="le-d">Descripción</label><input id="le-d" v-model="descripcion" type="text" maxlength="500" /></div>
        <div class="fila"><button class="boton boton-primario" type="submit">Guardar</button><button class="boton boton-fantasma" type="button" @click="editando = false">Cancelar</button></div>
      </form>

      <p v-if="lista.demo" class="tenue chico">Las métricas guardadas son de demostración.</p>
      <div v-if="seleccionadas.length" class="fila herramientas">
        <span class="chico">{{ seleccionadas.length }} seleccionadas</span>
        <button class="boton boton-chico boton-peligro" type="button" @click="quitar"><Icono nombre="basura" /> Quitar de la lista</button>
      </div>

      <section class="panel">
        <TablaKeywords v-model:seleccion="seleccion" :filas="items" :moneda="moneda" con-nota vacio="La lista está vacía. Añade keywords desde los resultados de una búsqueda." @nota="guardarNota" @abrir="abrir" />
      </section>
      <p v-if="items.length" class="tenue chico">Las métricas son las del momento en que se guardó cada keyword; «Actualizar métricas» las renueva.</p>
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
.herramientas {
  margin: 8px 0;
}
.panel + .panel,
form.panel {
  margin-bottom: 16px;
}
</style>
