<script setup lang="ts">
/**
 * Muestra un valor como «31», «69 %» o «1.900 mil» contando desde 0 hasta él al
 * aparecer, como si se estuviera calculando. Solo anima el número del principio;
 * el resto (« %», « mil») se queda fijo. Con «reducir movimiento» activado en el
 * sistema, o si el texto no empieza por un número, se muestra directamente.
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = withDefaults(defineProps<{ valor: string; duracion?: number }>(), { duracion: 900 })

const texto = ref(props.valor)
let marco = 0

function animar() {
  cancelAnimationFrame(marco)
  const m = /^(-?\d+(?:[.,]\d+)?)(.*)$/s.exec(props.valor.trim())
  const quieto = globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  if (!m || quieto) {
    texto.value = props.valor
    return
  }
  const [, numero, resto] = m
  const separador = numero.includes(',') ? ',' : '.'
  const decimales = numero.split(/[.,]/)[1]?.length ?? 0
  const final = Number(numero.replace(',', '.'))
  const inicio = performance.now()
  const paso = (ahora: number) => {
    const t = Math.min(1, (ahora - inicio) / props.duracion)
    const suave = 1 - Math.pow(1 - t, 3) // arranca rápido y frena al llegar
    texto.value = (final * suave).toFixed(decimales).replace('.', separador) + resto
    if (t < 1) marco = requestAnimationFrame(paso)
    else texto.value = props.valor // termina exactamente en el valor original
  }
  texto.value = (0).toFixed(decimales).replace('.', separador) + resto
  marco = requestAnimationFrame(paso)
}

onMounted(animar)
watch(() => props.valor, animar)
onBeforeUnmount(() => cancelAnimationFrame(marco))
</script>

<template>
  <!-- El lector de pantalla oye el valor final, no el conteo. -->
  <span class="num" aria-hidden="true">{{ texto }}</span><span class="oculto-visual">{{ valor }}</span>
</template>
