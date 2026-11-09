<script setup lang="ts">
/** Elegir (o crear) la lista a la que se añaden las keywords seleccionadas. */
import { nextTick, ref, watch } from 'vue'
import { keywords } from '@/api/radar'
import type { ListaKeywords } from '@/api/tipos'
import { mensajeDe } from '@/api/cliente'
import { num } from '@/composables/keywords'

const props = defineProps<{ abierto: boolean; cantidad: number; pais: string; idioma: string; demo: boolean }>()
const emit = defineEmits<{ cerrar: []; elegida: [lista: ListaKeywords] }>()

const dialogo = ref<HTMLDialogElement | null>(null)
const listas = ref<ListaKeywords[]>([])
const elegida = ref('')
const nombre = ref('')
const error = ref('')
const ocupado = ref(false)

watch(
  () => props.abierto,
  async (si) => {
    if (si) {
      error.value = ''
      nombre.value = ''
      try {
        // Una lista de demostración no se mezcla con datos reales (ni al revés).
        listas.value = (await keywords.listas()).filter((l) => l.demo === props.demo)
      } catch (e) {
        listas.value = []
        error.value = mensajeDe(e)
      }
      elegida.value = listas.value[0]?.codigo ?? ''
      await nextTick()
      if (dialogo.value && !dialogo.value.open) dialogo.value.showModal()
    } else if (dialogo.value?.open) {
      dialogo.value.close()
    }
  },
)

async function aceptar() {
  error.value = ''
  ocupado.value = true
  try {
    const lista = nombre.value.trim()
      ? await keywords.crearLista(nombre.value.trim(), props.pais, props.idioma, props.demo)
      : listas.value.find((l) => l.codigo === elegida.value)
    if (!lista) {
      error.value = 'Elige una lista o escribe el nombre de una nueva.'
      return
    }
    emit('elegida', lista)
  } catch (e) {
    error.value = mensajeDe(e)
  } finally {
    ocupado.value = false
  }
}
</script>

<template>
  <dialog ref="dialogo" class="dialogo-lista" aria-labelledby="dl-titulo" @cancel.prevent="emit('cerrar')">
    <form class="pila" @submit.prevent="aceptar">
      <h2 id="dl-titulo">Añadir {{ num(cantidad) }} {{ cantidad === 1 ? 'keyword' : 'keywords' }} a una lista</h2>
      <div v-if="listas.length" class="campo">
        <label for="dl-lista">Lista existente</label>
        <select id="dl-lista" v-model="elegida" :disabled="!!nombre.trim()">
          <option v-for="l in listas" :key="l.codigo" :value="l.codigo">{{ l.nombre }} ({{ l.keywords }})</option>
        </select>
      </div>
      <div class="campo">
        <label for="dl-nueva">{{ listas.length ? 'o crear una nueva' : 'Nombre de la lista nueva' }}</label>
        <input id="dl-nueva" v-model="nombre" type="text" maxlength="80" placeholder="Ej.: Cursos de cocina 2026" />
        <span class="campo-ayuda">Una lista guarda las métricas del momento y se puede actualizar después.</span>
      </div>
      <p v-if="error" class="aviso aviso-error" role="alert">{{ error }}</p>
      <div class="fila fila-fin">
        <button class="boton boton-fantasma" type="button" @click="emit('cerrar')">Cancelar</button>
        <button class="boton boton-primario" type="submit" :disabled="ocupado">{{ ocupado ? 'Guardando…' : 'Añadir' }}</button>
      </div>
    </form>
  </dialog>
</template>

<style scoped>
.dialogo-lista {
  margin: auto;
  width: min(460px, calc(100vw - 32px));
  padding: 22px;
  background: var(--panel);
  color: var(--texto);
  border: 1px solid var(--borde-fuerte);
  border-radius: var(--radio);
  box-shadow: var(--sombra);
}
.dialogo-lista::backdrop {
  background: rgba(3, 7, 18, 0.7);
}
</style>
