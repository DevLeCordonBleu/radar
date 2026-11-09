<script setup lang="ts">
/**
 * Una medida por día (columnas) o varias que se leen juntas (líneas), sin segundo eje.
 * Hover y teclado (flechas) muestran todas las series de ese día; «Ver tabla» da los
 * mismos números sin pasar el puntero. Los colores de las series son variables CSS
 * validadas para tema claro y oscuro (ver MedicionView).
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

interface Serie {
  clave: string
  nombre: string
  /** Variable CSS del color, p. ej. 'var(--serie-leads)'. */
  color: string
}

const props = defineProps<{
  titulo: string
  dias: Record<string, number | string>[]
  series: Serie[]
  tipo: 'columnas' | 'lineas'
  formato: (n: number) => string
  /** Para los números del eje, que tienen poco sitio; por defecto, `formato`. */
  formatoEje?: (n: number) => string
}>()

const caja = ref<HTMLElement | null>(null)
const ancho = ref(640)
const ALTO = 220
const M = { arriba: 12, derecha: 16, abajo: 26, izquierda: 52 }
let observador: ResizeObserver | null = null
onMounted(() => {
  observador = new ResizeObserver(([e]) => (ancho.value = Math.max(280, Math.round(e.contentRect.width))))
  if (caja.value) observador.observe(caja.value)
})
onBeforeUnmount(() => observador?.disconnect())

const tabla = ref(false)
const activo = ref<number | null>(null)

const valor = (d: Record<string, number | string>, k: string) => Number(d[k] ?? 0)
const maximo = computed(() => Math.max(1, ...props.dias.flatMap((d) => props.series.map((s) => valor(d, s.clave)))))

/** Ticks redondos: 0, paso, 2·paso… hasta cubrir el máximo. */
const ticks = computed(() => {
  const crudo = maximo.value / 4
  const mag = 10 ** Math.floor(Math.log10(crudo))
  const paso = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((p) => p >= crudo) ?? crudo
  const n = Math.ceil(maximo.value / paso)
  return Array.from({ length: n + 1 }, (_, i) => i * paso)
})
const tope = computed(() => ticks.value[ticks.value.length - 1] || 1)
const interior = computed(() => ({ w: ancho.value - M.izquierda - M.derecha, h: ALTO - M.arriba - M.abajo }))
const banda = computed(() => interior.value.w / Math.max(1, props.dias.length))
const x = (i: number) => M.izquierda + banda.value * (i + 0.5)
const y = (v: number) => M.arriba + interior.value.h * (1 - v / tope.value)
const anchoBarra = computed(() => Math.max(2, Math.min(24, banda.value - 2)))

const etiquetaDia = (f: string) => {
  const [, m, d] = f.split('-')
  return `${Number(d)}/${Number(m)}`
}
/** Unas pocas fechas en el eje: la primera, la última y algunas entre medio. */
const fechasEje = computed(() => {
  const n = props.dias.length
  if (!n) return []
  const cada = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(interior.value.w / 70))))
  return props.dias.map((d, i) => ({ i, f: String(d.fecha) })).filter(({ i }) => i % cada === 0 || i === n - 1)
})

function camino(clave: string) {
  return props.dias.map((d, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(valor(d, clave)).toFixed(1)}`).join(' ')
}

/** Columna con 4px redondeados arriba y recta en la base. */
function columna(i: number, v: number) {
  const w = anchoBarra.value
  const x0 = x(i) - w / 2
  const y0 = y(v)
  const base = y(0)
  const r = Math.min(4, w / 2, Math.max(0, base - y0))
  if (base - y0 < 0.5) return ''
  return `M${x0},${base} V${y0 + r} Q${x0},${y0} ${x0 + r},${y0} H${x0 + w - r} Q${x0 + w},${y0} ${x0 + w},${y0 + r} V${base} Z`
}

function mover(ev: PointerEvent) {
  const svg = ev.currentTarget as SVGSVGElement
  const r = svg.getBoundingClientRect()
  const px = ((ev.clientX - r.left) / r.width) * ancho.value
  const i = Math.floor((px - M.izquierda) / banda.value)
  activo.value = i >= 0 && i < props.dias.length ? i : null
}
function tecla(ev: KeyboardEvent) {
  if (!props.dias.length) return
  if (ev.key === 'ArrowRight') activo.value = Math.min(props.dias.length - 1, (activo.value ?? -1) + 1)
  else if (ev.key === 'ArrowLeft') activo.value = Math.max(0, (activo.value ?? props.dias.length) - 1)
  else if (ev.key === 'Escape') activo.value = null
  else return
  ev.preventDefault()
}
const tip = computed(() => {
  if (activo.value === null) return null
  const d = props.dias[activo.value]
  const izquierda = (x(activo.value) / ancho.value) * 100
  return { d, izquierda, derecha: izquierda > 60 }
})
const ultimo = computed(() => props.dias[props.dias.length - 1])
</script>

<template>
  <figure class="grafico">
    <figcaption class="fila entre">
      <strong>{{ titulo }}</strong>
      <span class="fila leyenda">
        <template v-if="series.length > 1">
          <span v-for="s in series" :key="s.clave" class="clave">
            <svg width="16" height="8" aria-hidden="true"><line x1="0" y1="4" x2="16" y2="4" :style="{ stroke: s.color }" stroke-width="2" stroke-linecap="round" /></svg>
            {{ s.nombre }}
          </span>
        </template>
        <button class="boton-texto chico" type="button" :aria-pressed="tabla" @click="tabla = !tabla">{{ tabla ? 'Ver gráfico' : 'Ver tabla' }}</button>
      </span>
    </figcaption>

    <div v-if="!tabla" ref="caja" class="lienzo">
      <svg
        :viewBox="`0 0 ${ancho} ${ALTO}`"
        :width="ancho"
        :height="ALTO"
        role="img"
        tabindex="0"
        :aria-label="`${titulo}: ${dias.length} días. Usa las flechas para recorrerlos.`"
        @pointermove="mover"
        @pointerleave="activo = null"
        @keydown="tecla"
        @blur="activo = null"
      >
        <g class="rejilla">
          <g v-for="t in ticks" :key="t">
            <line :x1="M.izquierda" :x2="ancho - M.derecha" :y1="y(t)" :y2="y(t)" />
            <text :x="M.izquierda - 6" :y="y(t) + 4" text-anchor="end">{{ (formatoEje ?? formato)(t) }}</text>
          </g>
          <text v-for="e in fechasEje" :key="e.i" :x="x(e.i)" :y="ALTO - 8" text-anchor="middle">{{ etiquetaDia(e.f) }}</text>
        </g>
        <template v-if="tipo === 'columnas'">
          <path
            v-for="(d, i) in dias"
            :key="String(d.fecha)"
            :d="columna(i, valor(d, series[0].clave))"
            :style="{ fill: series[0].color }"
            :opacity="activo === null || activo === i ? 1 : 0.55"
          />
        </template>
        <template v-else>
          <line v-if="activo !== null" class="cruz" :x1="x(activo)" :x2="x(activo)" :y1="M.arriba" :y2="y(0)" />
          <path v-for="s in series" :key="s.clave" :d="camino(s.clave)" fill="none" :style="{ stroke: s.color }" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
          <template v-if="activo !== null">
            <circle v-for="s in series" :key="s.clave" :cx="x(activo)" :cy="y(valor(dias[activo], s.clave))" r="4" :style="{ fill: s.color }" class="punto" />
          </template>
          <template v-else-if="ultimo">
            <circle v-for="s in series" :key="s.clave" :cx="x(dias.length - 1)" :cy="y(valor(ultimo, s.clave))" r="4" :style="{ fill: s.color }" class="punto" />
          </template>
        </template>
      </svg>
      <div v-if="tip" class="tip" :style="tip.derecha ? { right: `${100 - tip.izquierda}%` } : { left: `${tip.izquierda}%` }" role="status">
        <div class="tenue">{{ etiquetaDia(String(tip.d.fecha)) }}</div>
        <div v-for="s in series" :key="s.clave" class="tip-fila">
          <svg width="12" height="8" aria-hidden="true"><line x1="0" y1="4" x2="12" y2="4" :style="{ stroke: s.color }" stroke-width="2" stroke-linecap="round" /></svg>
          <strong>{{ formato(valor(tip.d, s.clave)) }}</strong> <span class="tenue">{{ s.nombre }}</span>
        </div>
      </div>
    </div>

    <div v-else class="tabla-envoltura alto">
      <table class="tabla">
        <thead>
          <tr><th>Día</th><th v-for="s in series" :key="s.clave" class="num">{{ s.nombre }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="d in dias" :key="String(d.fecha)">
            <td>{{ d.fecha }}</td>
            <td v-for="s in series" :key="s.clave" class="num">{{ formato(valor(d, s.clave)) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </figure>
</template>

<style scoped>
.grafico {
  margin: 0;
  display: grid;
  gap: 6px;
  min-width: 0;
}
.leyenda {
  gap: 12px;
  font-size: 0.8rem;
  color: var(--texto-suave);
}
.clave {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.lienzo {
  position: relative;
  min-width: 0;
}
.lienzo > svg {
  display: block;
  width: 100%;
  height: auto;
  touch-action: pan-y;
}
.lienzo > svg:focus-visible {
  outline: 2px solid var(--cian);
  outline-offset: 2px;
  border-radius: 6px;
}
.rejilla line {
  stroke: var(--borde);
  stroke-width: 1;
}
.rejilla text {
  fill: var(--texto-suave);
  font-size: 11px;
}
.cruz {
  stroke: var(--texto-suave);
  stroke-width: 1;
}
.punto {
  stroke: var(--panel);
  stroke-width: 2;
}
.tip {
  position: absolute;
  top: 0;
  pointer-events: none;
  background: var(--panel);
  border: 1px solid var(--borde-fuerte);
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 0.8rem;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.18);
  white-space: nowrap;
  z-index: 2;
}
.tip-fila {
  display: flex;
  align-items: center;
  gap: 6px;
}
.boton-texto {
  background: none;
  border: 0;
  color: var(--cian);
  cursor: pointer;
  font: inherit;
  padding: 0;
}
.alto {
  max-height: 260px;
  overflow: auto;
}
.num {
  text-align: right;
}
</style>
