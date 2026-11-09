<script setup lang="ts">
/**
 * Términos protegidos del Plan SEO: carreras, sistemas y demás nombres que ninguna propuesta
 * de la IA puede renombrar ni redefinir. El worker los escribe tal como están aquí y rechaza
 * la propuesta que los alarga («Gastronomía y Arte Culinario»). Los cambia un administrador.
 */
import { computed, ref, watch } from 'vue'
import { seo } from '@/api/radar'
import type { SearchConsoleSeo, TerminoProtegido, TipoTermino } from '@/api/tipos'
import Icono from '@/components/Icono.vue'
import { useAuth } from '@/stores/auth'
import { useAvisos } from '@/stores/avisos'

const props = defineProps<{ terminos: TerminoProtegido[] }>()
const emit = defineEmits<{ guardado: [estado: SearchConsoleSeo] }>()
const auth = useAuth()
const avisos = useAvisos()
const ocupado = ref(false)

const TIPOS: Record<TipoTermino, string> = { CARRERA: 'Carrera o programa', SISTEMA: 'Sistema', OTRO: 'Otro' }

const borrador = ref<TerminoProtegido[]>([])
watch(
  () => props.terminos,
  (t) => (borrador.value = t.map((x) => ({ ...x }))),
  { immediate: true },
)
const limpio = computed(() =>
  borrador.value.map((t) => ({ ...t, nombre: t.nombre.trim(), descripcion: t.descripcion.trim() })).filter((t) => t.nombre),
)
const cambiado = computed(() => JSON.stringify(limpio.value) !== JSON.stringify(props.terminos))

function agregar(tipo: TipoTermino) {
  borrador.value.push({ nombre: '', tipo, descripcion: '' })
}

async function guardar() {
  ocupado.value = true
  try {
    emit('guardado', await seo.guardarTerminos(limpio.value))
    avisos.exito('Términos protegidos guardados.')
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}
</script>

<template>
  <details class="chico terminos">
    <summary>Términos protegidos ({{ terminos.length }}): no cambian de nombre ni de significado</summary>
    <p class="tenue">
      Las propuestas los escriben exactamente así, y si la IA los alarga o cambia («Gastronomía y Arte Culinario»), el Radar le pide
      otra propuesta. A un sistema ponle su descripción oficial: la IA solo lo describe con ella.
    </p>
    <form v-if="auth.esAdmin" @submit.prevent="guardar">
      <div v-for="(t, i) in borrador" :key="i" class="termino">
        <input v-model="t.nombre" type="text" maxlength="120" placeholder="Nombre exacto" :aria-label="`Nombre del término ${i + 1}`" />
        <select v-model="t.tipo" :aria-label="`Tipo del término ${i + 1}`">
          <option v-for="(n, k) in TIPOS" :key="k" :value="k">{{ n }}</option>
        </select>
        <input
          v-model="t.descripcion"
          type="text"
          maxlength="500"
          :placeholder="t.tipo === 'SISTEMA' ? 'Qué es (descripción oficial)' : 'Descripción (opcional)'"
          :aria-label="`Descripción del término ${i + 1}`"
        />
        <button class="boton-texto" type="button" :aria-label="`Quitar ${t.nombre || 'término'}`" @click="borrador.splice(i, 1)">
          <Icono nombre="x" />
        </button>
      </div>
      <div class="fila">
        <button class="boton boton-chico" type="button" @click="agregar('CARRERA')"><Icono nombre="mas" /> Carrera</button>
        <button class="boton boton-chico" type="button" @click="agregar('SISTEMA')"><Icono nombre="mas" /> Sistema</button>
        <button class="boton boton-chico" type="button" @click="agregar('OTRO')"><Icono nombre="mas" /> Otro</button>
        <button class="boton boton-chico boton-primario" type="submit" :disabled="ocupado || !cambiado"><Icono nombre="guardar" /> Guardar</button>
      </div>
    </form>
    <ul v-else class="lista">
      <li v-for="t in terminos" :key="t.nombre">
        <strong>{{ t.nombre }}</strong> <span class="tenue">· {{ TIPOS[t.tipo] }}</span><template v-if="t.descripcion">: {{ t.descripcion }}</template>
      </li>
    </ul>
  </details>
</template>

<style scoped>
.terminos {
  margin: 0 0 12px;
}
.terminos p {
  margin: 4px 0;
}
form {
  display: grid;
  gap: 6px;
  margin-top: 6px;
}
.termino {
  display: grid;
  grid-template-columns: minmax(140px, 1.2fr) minmax(120px, 0.7fr) minmax(160px, 2fr) auto;
  gap: 6px;
  align-items: center;
}
@media (max-width: 640px) {
  .termino {
    grid-template-columns: 1fr auto;
  }
  .termino select,
  .termino input:nth-of-type(2) {
    grid-column: 1;
  }
}
.termino input,
.termino select {
  min-width: 0;
}
.fila {
  gap: 6px;
  flex-wrap: wrap;
}
.boton-texto {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--texto-suave);
  padding: 0 4px;
}
.boton-texto:hover {
  color: var(--rojo);
}
svg {
  width: 14px;
  height: 14px;
  vertical-align: -2px;
}
.lista {
  margin: 4px 0 0 18px;
  display: grid;
  gap: 2px;
}
</style>
