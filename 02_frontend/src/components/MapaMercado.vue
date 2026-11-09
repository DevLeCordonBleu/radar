<script setup lang="ts">
/**
 * El mapa del mercado: cada punto es un ángulo (círculo) o una oferta (rombo).
 *  - eje X: cuántos anunciantes lo usan;
 *  - eje Y: con qué frecuencia aparece (% ponderado por cercanía del competidor).
 * Arriba a la derecha está lo que hace todo el mundo; abajo a la izquierda, lo que
 * casi nadie usa (zona sombreada = «territorio poco ocupado», mismo criterio que la
 * sección 8). Un anillo marca dónde está tu marca. Pulsar un punto filtra la
 * galería por sus anuncios.
 *
 * Colores validados con el validador de dataviz (claro sobre #ffffff, oscuro sobre
 * #121c33): ángulo azul y oferta ámbar; la forma repite la identidad, así que el
 * color nunca va solo.
 */
import { computed, ref } from 'vue'
import type { FilaFrecuencia } from '@/api/tipos'
import { ETIQUETA_FRECUENCIA, pct } from '@/composables/formato'

const props = defineProps<{
  filas: FilaFrecuencia[]          // `resumen` del informe: ángulos y ofertas
  totalAnunciantes: number
  mios: string[]                   // claves (ángulos u ofertas) que usa tu marca
  miMarca: string | null
}>()
const emit = defineEmits<{ elegir: [fila: FilaFrecuencia] }>()

// Geometría (unidades del viewBox; el SVG escala al ancho disponible).
const W = 760
const H = 420
const M = { izq: 56, der: 24, arr: 16, aba: 48 }
const ancho = W - M.izq - M.der
const alto = H - M.arr - M.aba

// Mismos umbrales que el informe: «alta» desde 25 %, «poco usado» por debajo de 10 %
// y usado por como mucho una cuarta parte de los anunciantes.
const SATURADO = 25
const POCO = 10

const maxX = computed(() => Math.max(2, ...props.filas.map((f) => f.anunciantes)) + 1)
const maxY = computed(() => Math.max(40, Math.ceil(Math.max(0, ...props.filas.map((f) => f.pct)) / 10) * 10 + 5))
const topeZona = computed(() => Math.max(1, Math.floor(props.totalAnunciantes / 4)))

const x = (v: number) => M.izq + (v / maxX.value) * ancho
const y = (v: number) => M.arr + alto - (v / maxY.value) * alto

const ticksX = computed(() => Array.from({ length: maxX.value + 1 }, (_, i) => i).filter((i) => maxX.value <= 12 || i % Math.ceil(maxX.value / 10) === 0))
const ticksY = computed(() => {
  const paso = maxY.value > 60 ? 20 : 10
  return Array.from({ length: Math.floor(maxY.value / paso) + 1 }, (_, i) => i * paso)
})

interface Punto {
  f: FilaFrecuencia
  cx: number
  cy: number
  mio: boolean
  oferta: boolean
  etiqueta: boolean
}

/** Puntos con un pequeño desplazamiento lateral cuando caen casi encima de otro. */
const puntos = computed<Punto[]>(() => {
  const base = props.filas.map((f) => ({ f, cx: x(f.anunciantes), cy: y(f.pct), mio: props.mios.includes(f.clave), oferta: f.dimension === 'Oferta', etiqueta: false }))
  const porX = new Map<number, Punto[]>()
  base.forEach((p) => porX.set(p.f.anunciantes, [...(porX.get(p.f.anunciantes) ?? []), p]))
  for (const grupo of porX.values()) {
    grupo.sort((a, b) => a.cy - b.cy)
    let pila = 0
    for (let i = 1; i < grupo.length; i++) {
      pila = Math.abs(grupo[i].cy - grupo[i - 1].cy) < 13 ? pila + 1 : 0
      grupo[i].cx += pila === 0 ? 0 : (pila % 2 ? 1 : -1) * Math.ceil(pila / 2) * 13
    }
  }
  // Etiquetas directas solo para los 4 más frecuentes, sin pisarse.
  const usadas: number[] = []
  ;[...base].sort((a, b) => b.f.pct - a.f.pct).slice(0, 4).forEach((p) => {
    if (usadas.every((yy) => Math.abs(yy - p.cy) > 16)) {
      p.etiqueta = true
      usadas.push(p.cy)
    }
  })
  return base
})

const enZona = computed(() => props.filas.filter((f) => f.pct < POCO && f.anunciantes <= topeZona.value).length)
const corto = (t: string) => (t.length > 30 ? t.slice(0, 29) + '…' : t)

// Tooltip
const sobre = ref<Punto | null>(null)
const caja = ref<HTMLElement | null>(null)
const tip = ref({ izq: 0, arr: 0 })
function mostrar(p: Punto) {
  sobre.value = p
  const r = caja.value?.getBoundingClientRect()
  if (!r) return
  const k = r.width / W
  tip.value = { izq: p.cx * k, arr: p.cy * k }
}
</script>

<template>
  <div ref="caja" class="mapa">
    <p class="tenue chico ayuda">Pulsa un punto para ver sus anuncios, empezando por el que más tiempo lleva activo. <a href="#s9">Ver como tabla</a></p>
    <svg :viewBox="`0 0 ${W} ${H}`" role="img" :aria-label="`Mapa del mercado: ${filas.length} ángulos y ofertas según cuántos anunciantes los usan y con qué frecuencia. ${enZona} en la zona poco ocupada.`">
      <!-- zona poco ocupada -->
      <rect class="zona" :x="x(0)" :y="y(POCO)" :width="x(topeZona + 0.5) - x(0)" :height="y(0) - y(POCO)" />
      <!-- El rótulo va justo encima de la zona, no dentro: dentro taparía sus puntos. -->
      <text class="zona-texto" :x="x(0) + 6" :y="y(POCO) - 7">
        TERRITORIO POCO OCUPADO <tspan class="fino">· {{ enZona }} {{ enZona === 1 ? 'territorio' : 'territorios' }}</tspan>
      </text>

      <!-- rejilla y ejes -->
      <g class="rejilla">
        <line v-for="t in ticksY" :key="'y' + t" :x1="M.izq" :x2="W - M.der" :y1="y(t)" :y2="y(t)" />
      </g>
      <line class="umbral" :x1="M.izq" :x2="W - M.der" :y1="y(SATURADO)" :y2="y(SATURADO)" />
      <text class="umbral-texto" :x="M.izq + 6" :y="y(SATURADO) - 6">muy repetido ↑</text>
      <g class="ejes">
        <text v-for="t in ticksY" :key="'ty' + t" :x="M.izq - 10" :y="y(t) + 4" text-anchor="end">{{ t }} %</text>
        <text v-for="t in ticksX" :key="'tx' + t" :x="x(t)" :y="H - M.aba + 20" text-anchor="middle">{{ t }}</text>
        <text class="titulo-eje" :x="M.izq + ancho / 2" :y="H - 6" text-anchor="middle">Anunciantes que lo usan</text>
        <text class="titulo-eje" :transform="`translate(14 ${M.arr + alto / 2}) rotate(-90)`" text-anchor="middle">Frecuencia de uso</text>
      </g>

      <!-- puntos -->
      <g
        v-for="p in puntos"
        :key="p.f.dimension + p.f.clave"
        class="punto"
        :class="{ oferta: p.oferta, activo: sobre === p }"
        tabindex="0"
        role="button"
        :aria-label="`${p.f.dimension} «${p.f.clave}»: ${pct(p.f.pct)}, ${p.f.anunciantes} anunciantes${p.mio ? ', tu marca lo usa' : ''}. Ver sus anuncios.`"
        @mouseenter="mostrar(p)"
        @mouseleave="sobre = null"
        @focus="mostrar(p)"
        @blur="sobre = null"
        @click="emit('elegir', p.f)"
        @keydown.enter.prevent="emit('elegir', p.f)"
      >
        <circle class="objetivo" :cx="p.cx" :cy="p.cy" r="14" />
        <circle v-if="p.mio" class="anillo" :cx="p.cx" :cy="p.cy" r="11" />
        <rect v-if="p.oferta" class="marca" :x="p.cx - 5.5" :y="p.cy - 5.5" width="11" height="11" :transform="`rotate(45 ${p.cx} ${p.cy})`" />
        <circle v-else class="marca" :cx="p.cx" :cy="p.cy" r="6" />
        <!-- Cerca del borde derecho la etiqueta va a la izquierda del punto para no salirse. -->
        <text v-if="p.etiqueta" class="etiqueta" :x="p.cx > W * 0.7 ? p.cx - 16 : p.cx + 16" :y="p.cy + 4" :text-anchor="p.cx > W * 0.7 ? 'end' : 'start'">{{ corto(p.f.clave) }}</text>
      </g>
    </svg>

    <div v-if="sobre" class="tooltip" :style="{ left: tip.izq + 'px', top: tip.arr + 'px' }" role="status">
      <strong>{{ sobre.f.clave }}</strong>
      <span class="fila-tip"><span class="muestra" :class="{ oferta: sobre.oferta }" />{{ sobre.f.dimension }} · {{ ETIQUETA_FRECUENCIA[sobre.f.frecuencia] }}</span>
      <span class="num">{{ pct(sobre.f.pct) }} · {{ sobre.f.anuncios }} {{ sobre.f.anuncios === 1 ? 'anuncio' : 'anuncios' }} · {{ sobre.f.anunciantes }} {{ sobre.f.anunciantes === 1 ? 'anunciante' : 'anunciantes' }}</span>
      <span v-if="sobre.mio" class="tu">Tu marca lo usa</span>
    </div>

    <ul class="leyenda" aria-label="Leyenda">
      <li><span class="muestra" /> Ángulo</li>
      <li><span class="muestra oferta" /> Oferta</li>
      <li v-if="miMarca"><span class="muestra-anillo" /> Dónde estás tú ({{ miMarca }})</li>
    </ul>
  </div>
</template>

<style scoped>
.mapa {
  --angulo: #3b82f6;
  --oferta: #d97706;
  --tu: #c084fc;
  position: relative;
}
:global(:root[data-tema='claro']) .mapa {
  --angulo: #2563eb;
  --oferta: #b45309;
  --tu: #a21caf;
}
.ayuda {
  margin-bottom: 6px;
}
svg {
  width: 100%;
  height: auto;
  display: block;
  overflow: visible;
}
.zona {
  fill: var(--lima-fondo);
}
.zona-texto {
  fill: var(--lima);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
}
.zona-texto .fino {
  font-weight: 400;
  letter-spacing: 0;
  fill: var(--texto-suave);
}
.rejilla line {
  stroke: var(--borde);
  stroke-width: 1;
}
.umbral {
  stroke: var(--texto-tenue);
  stroke-width: 1;
  stroke-dasharray: 4 4;
}
.umbral-texto {
  fill: var(--texto-tenue);
  font-size: 11px;
}
.ejes text {
  fill: var(--texto-tenue);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.ejes .titulo-eje {
  fill: var(--texto-suave);
  font-size: 12px;
}
.punto {
  cursor: pointer;
  outline: none;
}
.objetivo {
  fill: transparent;
}
.marca {
  fill: var(--angulo);
  stroke: var(--panel);
  stroke-width: 2;
}
.oferta .marca {
  fill: var(--oferta);
}
.anillo {
  fill: none;
  stroke: var(--tu);
  stroke-width: 2;
}
.punto.activo .marca,
.punto:focus-visible .marca {
  stroke: var(--texto);
}
.etiqueta {
  fill: var(--texto);
  font-size: 12px;
  pointer-events: none;
}
.tooltip {
  position: absolute;
  transform: translate(-50%, calc(-100% - 14px));
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-width: 260px;
  padding: 8px 10px;
  background: var(--panel);
  border: 1px solid var(--borde-fuerte);
  border-radius: var(--radio-chico);
  box-shadow: var(--sombra);
  font-size: 0.82rem;
  pointer-events: none;
  z-index: 5;
}
.fila-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--texto-suave);
}
.tu {
  color: var(--texto);
  font-weight: 600;
}
.leyenda {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 18px;
  margin-top: 8px;
  font-size: 0.85rem;
  color: var(--texto-suave);
}
.leyenda li {
  display: flex;
  align-items: center;
  gap: 6px;
}
.muestra {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--angulo);
}
.muestra.oferta {
  border-radius: 1px;
  transform: rotate(45deg) scale(0.85);
  background: var(--oferta);
}
.muestra-anillo {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid var(--tu);
}
</style>
