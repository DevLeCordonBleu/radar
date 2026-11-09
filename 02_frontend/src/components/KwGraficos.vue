<script setup lang="ts">
/**
 * Gráficos de KeyWords Explorer, en SVG sin librerías:
 *  - modo «barras»: los 12 meses con su etiqueta y valor (resumen de una keyword);
 *  - modo «linea»: una línea mínima para las tablas (sparkline).
 */
import { computed } from 'vue'
import { num } from '@/composables/keywords'

const props = withDefaults(
  defineProps<{ serie: number[]; modo?: 'barras' | 'linea'; meses?: string[]; ancho?: number; alto?: number }>(),
  { modo: 'linea', meses: () => [], ancho: 90, alto: 26 },
)

const max = computed(() => Math.max(1, ...props.serie))
const NOMBRES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
const etiqueta = (i: number) => {
  const m = props.meses[i]
  if (!m) return ''
  const [a, mes] = m.split('-')
  return `${NOMBRES[Number(mes) - 1] ?? ''} ${a.slice(2)}`
}

const puntos = computed(() => {
  const n = props.serie.length
  if (n < 2) return ''
  return props.serie.map((v, i) => `${((i / (n - 1)) * (props.ancho - 2) + 1).toFixed(1)},${(props.alto - 2 - (v / max.value) * (props.alto - 4)).toFixed(1)}`).join(' ')
})

const resumen = computed(() =>
  props.serie.length ? `Tendencia de ${props.serie.length} meses: de ${num(props.serie[0])} a ${num(props.serie[props.serie.length - 1])}, máximo ${num(max.value)}.` : 'Sin datos de tendencia.',
)
</script>

<template>
  <span v-if="!serie.length" class="tenue chico">—</span>

  <svg v-else-if="modo === 'linea'" :width="ancho" :height="alto" :viewBox="`0 0 ${ancho} ${alto}`" role="img" :aria-label="resumen" class="linea">
    <polyline :points="puntos" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" />
  </svg>

  <figure v-else class="barras" role="img" :aria-label="resumen">
    <div class="columnas">
      <div v-for="(v, i) in serie" :key="i" class="columna" :title="`${etiqueta(i)}: ${num(v)}`">
        <span class="valor num">{{ num(v) }}</span>
        <span class="barra" :style="{ height: Math.max(3, (v / max) * 100) + '%' }" />
        <span class="mes">{{ etiqueta(i) }}</span>
      </div>
    </div>
  </figure>
</template>

<style scoped>
.linea {
  color: var(--cian);
  vertical-align: middle;
}
.barras {
  margin: 0;
}
.columnas {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  height: 190px;
}
.columna {
  flex: 1;
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  align-items: center;
  gap: 4px;
}
.barra {
  width: 100%;
  background: var(--cian);
  border-radius: 4px 4px 0 0;
  opacity: 0.85;
}
.columna:hover .barra {
  opacity: 1;
}
.valor {
  font-size: 0.68rem;
  color: var(--texto-suave);
}
.mes {
  font-size: 0.68rem;
  color: var(--texto-tenue);
  white-space: nowrap;
}
@media (max-width: 700px) {
  .valor {
    display: none;
  }
}
</style>
