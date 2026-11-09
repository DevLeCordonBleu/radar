<script setup lang="ts">
/**
 * La tabla de keywords (resultados del explorador y listas guardadas): orden por
 * columna, selección, paginación de 50 y, opcionalmente, una nota editable por fila.
 * Recibe las filas ya filtradas.
 */
import { computed, ref, watch } from 'vue'
import type { FilaKeyword } from '@/api/tipos'
import { ETIQUETA_COMPETENCIA, ETIQUETA_INTENCION, dinero, num, ordenar, type ColumnaOrden } from '@/composables/keywords'
import Icono from './Icono.vue'
import KwGraficos from './KwGraficos.vue'

const props = withDefaults(
  defineProps<{ filas: FilaKeyword[]; moneda: string | null; conNota?: boolean; vacio?: string; porPagina?: number }>(),
  { conNota: false, vacio: 'Ninguna keyword coincide con los filtros.', porPagina: 50 },
)
const seleccion = defineModel<Set<string>>('seleccion', { required: true })
const emit = defineEmits<{ nota: [keyword: string, texto: string]; abrir: [keyword: string] }>()

const columna = ref<ColumnaOrden>('volumen')
const desc = ref(true)
const pagina = ref(0)

const ordenadas = computed(() => ordenar(props.filas, columna.value, desc.value))
const paginas = computed(() => Math.max(1, Math.ceil(ordenadas.value.length / props.porPagina)))
const visibles = computed(() => ordenadas.value.slice(pagina.value * props.porPagina, (pagina.value + 1) * props.porPagina))
const clave = (k: FilaKeyword) => k.keyword.toLowerCase()

// Al filtrar u ordenar se vuelve a la primera página.
watch([() => props.filas, columna, desc], () => (pagina.value = 0))

function ordenarPor(c: ColumnaOrden) {
  if (columna.value === c) desc.value = !desc.value
  else {
    columna.value = c
    desc.value = c !== 'keyword'
  }
}
const sentido = (c: ColumnaOrden) => (columna.value === c ? (desc.value ? 'descending' : 'ascending') : 'none')

const todasLaPagina = computed(() => visibles.value.length > 0 && visibles.value.every((k) => seleccion.value.has(clave(k))))

function alternar(k: FilaKeyword) {
  const s = new Set(seleccion.value)
  if (!s.delete(clave(k))) s.add(clave(k))
  seleccion.value = s
}
function alternarPagina() {
  const s = new Set(seleccion.value)
  if (todasLaPagina.value) visibles.value.forEach((k) => s.delete(clave(k)))
  else visibles.value.forEach((k) => s.add(clave(k)))
  seleccion.value = s
}

const nivelBarra = (n: number | null) => (n == null ? '' : n < 34 ? 'baja' : n < 67 ? 'media' : 'alta')
</script>

<template>
  <p v-if="!filas.length" class="vacio">{{ vacio }}</p>
  <template v-else>
    <div class="tabla-envoltura">
      <table class="tabla kw">
        <thead>
          <tr>
            <th class="col-sel">
              <input type="checkbox" :checked="todasLaPagina" aria-label="Seleccionar las de esta página" @change="alternarPagina" />
            </th>
            <th :aria-sort="sentido('keyword')"><button type="button" @click="ordenarPor('keyword')">Keyword <Icono v-if="columna === 'keyword'" :nombre="desc ? 'abajo' : 'arriba'" /></button></th>
            <th title="Intención de búsqueda estimada">Int.</th>
            <th class="der" :aria-sort="sentido('volumen')"><button type="button" title="Búsquedas mensuales promedio" @click="ordenarPor('volumen')">Volumen <Icono v-if="columna === 'volumen'" :nombre="desc ? 'abajo' : 'arriba'" /></button></th>
            <th class="der">12 meses</th>
            <th class="der" :aria-sort="sentido('cpc')"><button type="button" title="Puja media por clic en Google Ads" @click="ordenarPor('cpc')">CPC <Icono v-if="columna === 'cpc'" :nombre="desc ? 'abajo' : 'arriba'" /></button></th>
            <th :aria-sort="sentido('competencia_idx')"><button type="button" title="Competencia entre anunciantes (no es dificultad orgánica)" @click="ordenarPor('competencia_idx')">Comp. ads <Icono v-if="columna === 'competencia_idx'" :nombre="desc ? 'abajo' : 'arriba'" /></button></th>
            <th v-if="conNota">Nota</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="k in visibles" :key="k.keyword" :class="{ marcada: seleccion.has(clave(k)) }">
            <td class="col-sel"><input type="checkbox" :checked="seleccion.has(clave(k))" :aria-label="`Seleccionar ${k.keyword}`" @change="alternar(k)" /></td>
            <td class="kw-texto">
              <button type="button" class="enlace-kw" @click="emit('abrir', k.keyword)">{{ k.keyword }}</button>
              <span v-if="k.pregunta" class="marca" title="Es una pregunta">?</span>
              <span v-if="k.sugerencia" class="marca g" title="Aparece en el autocompletado de Google">G</span>
            </td>
            <td>
              <span class="intenciones">
                <span v-for="i in k.intencion" :key="i" class="int" :class="i" :title="`${ETIQUETA_INTENCION[i].nombre}: ${ETIQUETA_INTENCION[i].ayuda} (estimada)`">{{ ETIQUETA_INTENCION[i].letra }}</span>
                <span v-if="!k.intencion.length" class="tenue">—</span>
              </span>
            </td>
            <td class="der num"><strong>{{ num(k.volumen) }}</strong></td>
            <td class="der"><KwGraficos :serie="k.tendencia" /></td>
            <td class="der num">{{ dinero(k.cpc, moneda) }}</td>
            <td>
              <span v-if="k.competencia" class="comp" :title="`Índice ${k.competencia_idx ?? '?'} de 100`">
                <span class="pista"><span class="relleno" :class="nivelBarra(k.competencia_idx)" :style="{ width: (k.competencia_idx ?? 0) + '%' }" /></span>
                <span class="chico">{{ ETIQUETA_COMPETENCIA[k.competencia] }}</span>
              </span>
              <span v-else class="tenue">—</span>
            </td>
            <td v-if="conNota">
              <input
                type="text"
                class="nota"
                :value="k.nota ?? ''"
                maxlength="500"
                :aria-label="`Nota de ${k.keyword}`"
                placeholder="Añadir nota"
                @change="emit('nota', k.keyword, ($event.target as HTMLInputElement).value)"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="fila paginacion">
      <span class="tenue chico num">{{ pagina * porPagina + 1 }}–{{ Math.min((pagina + 1) * porPagina, ordenadas.length) }} de {{ num(ordenadas.length) }}</span>
      <span class="espaciador" />
      <button class="boton boton-chico" type="button" :disabled="pagina === 0" @click="pagina--"><Icono nombre="volver" /> Anterior</button>
      <span class="chico num">{{ pagina + 1 }} / {{ paginas }}</span>
      <button class="boton boton-chico" type="button" :disabled="pagina >= paginas - 1" @click="pagina++">Siguiente</button>
    </div>
  </template>
</template>

<style scoped>
.kw th button {
  background: none;
  border: 0;
  color: inherit;
  font: inherit;
  font-weight: 700;
  text-transform: inherit;
  letter-spacing: inherit;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0;
}
.kw th button svg {
  width: 12px;
  height: 12px;
}
.der {
  text-align: right;
}
.kw :is(th, td) {
  padding-inline: 10px;
}
.col-sel {
  width: 34px;
}
tr.marcada {
  background: var(--cian-fondo);
}
.kw-texto {
  min-width: 170px;
}
.enlace-kw {
  background: none;
  border: 0;
  padding: 0;
  font: inherit;
  color: var(--texto);
  text-align: left;
  cursor: pointer;
}
.enlace-kw:hover {
  color: var(--cian);
  text-decoration: underline;
}
.marca {
  display: inline-block;
  margin-left: 6px;
  min-width: 16px;
  padding: 0 4px;
  text-align: center;
  border-radius: 4px;
  font-size: 0.68rem;
  font-weight: 700;
  background: var(--panel-3);
  color: var(--texto-suave);
}
.marca.g {
  background: var(--ambar-fondo);
  color: var(--ambar);
}
.intenciones {
  display: inline-flex;
  gap: 3px;
}
.int {
  display: inline-grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 700;
}
.int.informacional {
  background: var(--cian-fondo);
  color: var(--cian);
}
.int.comercial {
  background: var(--violeta-fondo);
  color: var(--violeta);
}
.int.transaccional {
  background: var(--lima-fondo);
  color: var(--lima);
}
.int.navegacional {
  background: var(--ambar-fondo);
  color: var(--ambar);
}
.comp {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.pista {
  width: 54px;
  height: 6px;
  background: var(--panel-3);
  border-radius: 3px;
  overflow: hidden;
}
.relleno {
  display: block;
  height: 100%;
  background: var(--cian);
}
.relleno.baja {
  background: var(--lima);
}
.relleno.media {
  background: var(--ambar);
}
.relleno.alta {
  background: var(--rojo);
}
.nota {
  min-width: 180px;
}
.paginacion {
  margin-top: 12px;
}
</style>
