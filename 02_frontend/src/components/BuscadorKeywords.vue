<script setup lang="ts">
/**
 * El buscador de KeyWords Explorer: palabras (hasta 20, separadas por comas o en
 * líneas) o una URL, con país e idioma. Es el mismo en el inicio y en la cabecera
 * de los resultados. Recuerda el último país e idioma en este navegador.
 */
import { onMounted, ref, watch } from 'vue'
import { useEstadoKeywords } from '@/composables/estadoKeywords'
import Icono from './Icono.vue'

export interface BusquedaForm {
  semillas: string[]
  url: string | null
  pais: string
  idioma: string
  demo: boolean
}

const props = defineProps<{ inicial?: Partial<BusquedaForm>; compacto?: boolean; ocupado?: boolean }>()
const emit = defineEmits<{ buscar: [b: BusquedaForm] }>()

const { estado, cargar, conectado } = useEstadoKeywords()

const modo = ref<'palabras' | 'url'>(props.inicial?.url ? 'url' : 'palabras')
const texto = ref((props.inicial?.semillas ?? []).join(', '))
const url = ref(props.inicial?.url ?? '')
const pais = ref(props.inicial?.pais ?? leer('radar.kw.pais', 'PE'))
const idioma = ref(props.inicial?.idioma ?? leer('radar.kw.idioma', 'es'))
const demo = ref(props.inicial?.demo ?? false)

function leer(clave: string, defecto: string): string {
  try {
    return localStorage.getItem(clave) || defecto
  } catch {
    return defecto
  }
}
function guardar(clave: string, valor: string) {
  try {
    localStorage.setItem(clave, valor)
  } catch {
    /* sin almacenamiento: no se recuerda */
  }
}

onMounted(async () => {
  await cargar()
  // Sin Google Ads conectado, lo único posible es la demostración: se marca sola.
  if (!conectado.value) demo.value = true
})
watch(conectado, (c) => {
  if (!c) demo.value = true
})
watch(pais, (v) => guardar('radar.kw.pais', v))
watch(idioma, (v) => guardar('radar.kw.idioma', v))

function enviar() {
  const semillas =
    modo.value === 'palabras' ? [...new Set(texto.value.split(/[\n,;]+/).map((s) => s.trim()).filter(Boolean))].slice(0, 20) : []
  const u = modo.value === 'url' ? url.value.trim() : ''
  if (!semillas.length && !u) return
  emit('buscar', { semillas, url: u || null, pais: pais.value, idioma: idioma.value, demo: demo.value })
}
</script>

<template>
  <form class="buscador" :class="{ compacto }" role="search" @submit.prevent="enviar">
    <div class="modos" role="group" aria-label="Qué buscar">
      <button type="button" :class="{ activo: modo === 'palabras' }" @click="modo = 'palabras'">Palabras</button>
      <button type="button" :class="{ activo: modo === 'url' }" @click="modo = 'url'">Desde una URL</button>
    </div>
    <div class="fila entrada">
      <div class="campo grande">
        <label for="kw-q" class="oculto-visual">{{ modo === 'palabras' ? 'Palabras clave' : 'URL de una página' }}</label>
        <input v-if="modo === 'palabras'" id="kw-q" v-model="texto" type="text" autocomplete="off" placeholder="Una o varias palabras, separadas por comas (máx. 20): curso de cocina, pastelería" />
        <input v-else id="kw-q" v-model="url" type="url" autocomplete="off" placeholder="https://tu-sitio.pe/pagina  ·  Google propone keywords a partir de su contenido" />
      </div>
      <div class="campo">
        <label for="kw-pais" class="oculto-visual">País</label>
        <select id="kw-pais" v-model="pais">
          <option v-for="(n, c) in estado?.paises ?? { PE: 'Perú' }" :key="c" :value="c">{{ n }}</option>
        </select>
      </div>
      <div class="campo">
        <label for="kw-idioma" class="oculto-visual">Idioma</label>
        <select id="kw-idioma" v-model="idioma">
          <option v-for="(n, c) in estado?.idiomas ?? { es: 'Español' }" :key="c" :value="c">{{ n }}</option>
        </select>
      </div>
      <button class="boton boton-primario" type="submit" :disabled="ocupado"><Icono nombre="buscar" /> {{ ocupado ? 'Buscando…' : 'Buscar' }}</button>
    </div>
    <label class="casilla chico demo">
      <input v-model="demo" type="checkbox" :disabled="!conectado" />
      Usar datos de demostración
      <span class="tenue">{{ conectado ? '(inventados, para probar sin gastar consultas)' : '(Google Ads no está conectado: solo puedes ver demostración)' }}</span>
    </label>
  </form>
</template>

<style scoped>
.buscador {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.modos {
  display: inline-flex;
  align-self: flex-start;
  gap: 2px;
  padding: 3px;
  background: var(--panel-2);
  border: 1px solid var(--borde);
  border-radius: var(--radio-chico);
}
.modos button {
  background: transparent;
  border: 0;
  padding: 5px 12px;
  border-radius: 5px;
  color: var(--texto-suave);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}
.modos button.activo {
  background: var(--panel);
  color: var(--cian);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
}
.entrada {
  flex-wrap: nowrap;
  align-items: stretch;
}
.entrada .grande {
  flex: 1;
}
.entrada select {
  min-width: 150px;
}
.entrada input,
.entrada select,
.entrada .boton {
  min-height: 44px;
}
.compacto .entrada input,
.compacto .entrada select,
.compacto .entrada .boton {
  min-height: 38px;
}
@media (max-width: 860px) {
  .entrada {
    flex-wrap: wrap;
  }
  .entrada .grande {
    flex-basis: 100%;
  }
}
</style>
