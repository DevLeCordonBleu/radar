<script setup lang="ts">
/** Avisos flotantes (esquina inferior derecha). Los errores se quedan hasta cerrarlos. */
import { useAvisos } from '@/stores/avisos'
import Icono from './Icono.vue'

const avisos = useAvisos()

const ICONO = { exito: 'ok', error: 'error', info: 'info', ambar: 'alerta' } as const
const CLASE = { exito: 'aviso-exito', error: 'aviso-error', info: 'aviso-info', ambar: 'aviso-ambar' } as const
</script>

<template>
  <div class="centro" aria-live="polite">
    <div
      v-for="a in avisos.lista"
      :key="a.id"
      class="aviso flotante"
      :class="CLASE[a.tipo]"
      :role="a.tipo === 'error' ? 'alert' : 'status'"
    >
      <Icono :nombre="ICONO[a.tipo]" />
      <div class="aviso-cuerpo">
        <strong v-if="a.titulo">{{ a.titulo }}</strong>
        <span class="texto">{{ a.texto }}</span>
      </div>
      <button class="boton boton-fantasma boton-chico" type="button" @click="avisos.quitar(a.id)">
        Cerrar
      </button>
    </div>
  </div>
</template>

<style scoped>
.centro {
  position: fixed;
  right: 18px;
  bottom: 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: min(440px, calc(100vw - 36px));
  z-index: 1000;
}
.flotante {
  background-color: var(--panel);
  box-shadow: var(--sombra);
  align-items: center;
}
.flotante.aviso-error {
  background: color-mix(in srgb, var(--rojo) 14%, var(--panel));
}
.flotante.aviso-exito {
  background: color-mix(in srgb, var(--lima) 14%, var(--panel));
}
.flotante.aviso-ambar {
  background: color-mix(in srgb, var(--ambar) 14%, var(--panel));
}
.flotante.aviso-info {
  background: color-mix(in srgb, var(--cian) 14%, var(--panel));
}
.texto {
  white-space: pre-line;
  word-break: break-word;
}
</style>
