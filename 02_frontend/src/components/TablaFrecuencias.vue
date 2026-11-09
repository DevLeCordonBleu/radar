<script setup lang="ts">
/**
 * Una dimensión del informe (ángulos, hooks, ofertas...) como barras: cuánto
 * se repite cada cosa entre los anuncios analizados, ponderado por lo cerca
 * que compite cada anunciante. Un porcentaje alto = saturado; bajo = hueco.
 */
import type { FilaFrecuencia } from '@/api/tipos'
import { ETIQUETA_FRECUENCIA, pct } from '@/composables/formato'

withDefaults(
  defineProps<{
    filas: FilaFrecuencia[]
    vacio?: string
    /** Muestra la columna "N anuncios · M anunciantes". */
    detalle?: boolean
    max?: number
    /** Marca con "tú" los territorios en los que ya estás. */
    mios?: string[]
    /** Si se da, cada fila es un botón que filtra por esa clave. */
    seleccionable?: boolean
  }>(),
  { vacio: 'Sin datos en esta dimensión.', detalle: true, max: 0, mios: () => [], seleccionable: false },
)

defineEmits<{ elegir: [clave: string] }>()
</script>

<template>
  <p v-if="!filas.length" class="suave chico">{{ vacio }}</p>
  <ul v-else class="tabla-frec">
    <li v-for="f in max ? filas.slice(0, max) : filas" :key="f.clave" class="fila-frec">
      <component
        :is="seleccionable ? 'button' : 'div'"
        class="cabeza"
        :type="seleccionable ? 'button' : undefined"
        @click="seleccionable && $emit('elegir', f.clave)"
      >
        <span class="nombre">
          {{ f.clave }}
          <span v-if="mios.includes(f.clave)" class="chip chip-violeta yo">tú estás aquí</span>
        </span>
        <span class="valor num">{{ pct(f.pct) }}</span>
      </component>
      <div
        class="pista"
        role="img"
        :aria-label="`${f.clave}: ${pct(f.pct)}, ${ETIQUETA_FRECUENCIA[f.frecuencia]}`"
      >
        <div class="relleno" :class="f.frecuencia" :style="{ width: Math.min(100, Math.max(f.pct, 1.5)) + '%' }" />
      </div>
      <div class="pie">
        <span class="etiqueta-frec" :class="f.frecuencia">{{ ETIQUETA_FRECUENCIA[f.frecuencia] }}</span>
        <span v-if="detalle" class="tenue num">
          {{ f.anuncios }} {{ f.anuncios === 1 ? 'anuncio' : 'anuncios' }} ·
          {{ f.anunciantes }} {{ f.anunciantes === 1 ? 'anunciante' : 'anunciantes' }}
        </span>
      </div>
    </li>
  </ul>
</template>

<style scoped>
.tabla-frec {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.cabeza {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  width: 100%;
  background: none;
  border: 0;
  color: inherit;
  font: inherit;
  text-align: left;
  padding: 0;
}
button.cabeza {
  cursor: pointer;
}
button.cabeza:hover .nombre {
  color: var(--cian);
}
.nombre {
  font-weight: 600;
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.yo {
  font-size: 0.7rem;
}
.valor {
  font-weight: 700;
  font-size: 1.02rem;
}
.pista {
  height: 9px;
  background: var(--panel-3);
  border-radius: 5px;
  overflow: hidden;
  margin: 5px 0 4px;
}
.relleno {
  height: 100%;
  border-radius: 5px;
  background: var(--cian);
}
.relleno.muy_alta {
  background: var(--rojo);
}
.relleno.alta {
  background: var(--ambar);
}
.relleno.media {
  background: var(--cian);
}
.relleno.baja,
.relleno.hueco {
  background: var(--lima);
}
.pie {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 0.78rem;
  flex-wrap: wrap;
}
.etiqueta-frec {
  font-weight: 600;
}
.etiqueta-frec.muy_alta {
  color: var(--rojo);
}
.etiqueta-frec.alta {
  color: var(--ambar);
}
.etiqueta-frec.media {
  color: var(--cian);
}
.etiqueta-frec.baja,
.etiqueta-frec.hueco {
  color: var(--lima);
}
</style>
