<script setup lang="ts">
/**
 * Un anuncio analizado: miniatura, quién lo publica, cómo abre y cuánto lleva activo.
 * Con `abrible`, toda la tarjeta abre su ficha completa (evento `abrir`).
 */
import { ref } from 'vue'
import type { AnuncioInforme } from '@/api/tipos'
import { diasActivo, duracionActivo } from '@/composables/formato'
import Icono from './Icono.vue'
import Plataformas from './Plataformas.vue'

const props = defineProps<{
  anuncio: AnuncioInforme
  /** Etiquetas legibles de las listas cerradas. */
  etiquetas?: { hooks?: Record<string, string>; ofertas?: Record<string, string>; formatos?: Record<string, string> }
  ocultarMiniatura?: boolean
  abrible?: boolean
}>()
const emit = defineEmits<{ abrir: [] }>()

// Desde 2026-10-28 la miniatura se guarda en el Radar al cerrar el informe. Los informes
// anteriores enlazan a la Biblioteca de Meta, cuyas URLs caducan a los ~4 días: hueco neutro.
const imagenRota = ref(false)

const dias = () => diasActivo(props.anuncio)
</script>

<template>
  <article class="tarjeta" :class="{ abrible }">
    <div v-if="!ocultarMiniatura" class="miniatura">
      <img
        v-if="anuncio.thumb_url && !imagenRota"
        :src="anuncio.thumb_url"
        :alt="`Anuncio de ${anuncio.anunciante}`"
        loading="lazy"
        referrerpolicy="no-referrer"
        @error="imagenRota = true"
      />
      <span v-else class="sin-imagen" :title="imagenRota ? 'Meta caduca sus enlaces de imagen a los ~4 días; los informes nuevos guardan la imagen.' : ''">
        <Icono nombre="imagen" /><small>{{ imagenRota ? 'imagen caducada' : 'sin vista previa' }}</small>
      </span>
    </div>
    <div class="cuerpo">
      <header>
        <strong>{{ anuncio.anunciante }}</strong>
        <span class="tenue chico num" v-if="dias() != null">
          {{ anuncio.activo ? 'activo desde hace' : 'estuvo activo' }} {{ duracionActivo(dias()!) }}
        </span>
      </header>
      <Plataformas :plataformas="anuncio.plataformas" />
      <p v-if="anuncio.hook_literal" class="hook">«{{ anuncio.hook_literal }}»</p>
      <p v-else class="suave chico">Sin titular claro.</p>
      <button v-if="abrible" type="button" class="abrir chico" @click="emit('abrir')">
        Ver ficha<span class="oculto-visual"> del anuncio de {{ anuncio.anunciante }}</span>
      </button>
      <div class="chips">
        <span class="chip">{{ etiquetas?.formatos?.[anuncio.formato] ?? anuncio.formato }}</span>
        <span v-if="anuncio.oferta_tipo !== 'sin_oferta'" class="chip chip-cian">
          {{ etiquetas?.ofertas?.[anuncio.oferta_tipo] ?? anuncio.oferta_tipo }}
        </span>
        <span v-for="t in anuncio.territorios_angulo" :key="t" class="chip chip-violeta">{{ t }}</span>
      </div>
      <a v-if="anuncio.snapshot_url" :href="anuncio.snapshot_url" target="_blank" rel="noopener noreferrer" class="chico ver">
        ver anuncio <Icono nombre="externo" />
      </a>
    </div>
  </article>
</template>

<style scoped>
.tarjeta {
  display: flex;
  gap: 14px;
  background: var(--panel-2);
  border: 1px solid var(--borde);
  border-radius: var(--radio);
  padding: 12px;
  min-width: 0;
}
.abrible {
  position: relative;
  cursor: pointer;
  transition: border-color 0.15s;
}
.abrible:hover,
.abrible:focus-within {
  border-color: var(--cian);
}
/* El botón se estira sobre toda la tarjeta; el enlace a Meta queda por encima. */
.abrir {
  align-self: flex-start;
  background: none;
  border: 0;
  padding: 0;
  color: var(--cian);
  font-weight: 600;
  cursor: pointer;
}
.abrir::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: var(--radio);
}
.abrir:focus-visible {
  outline: none;
}
.abrir:focus-visible::after {
  outline: 2px solid var(--cian);
  outline-offset: 2px;
}
.ver {
  position: relative;
  z-index: 1;
}
.miniatura {
  flex: 0 0 92px;
  height: 92px;
  border-radius: var(--radio-chico);
  overflow: hidden;
  background: var(--panel-3);
  display: flex;
  align-items: center;
  justify-content: center;
}
.miniatura img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.sin-imagen {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  color: var(--texto-tenue);
  text-align: center;
}
.sin-imagen svg {
  width: 22px;
  height: 22px;
}
.sin-imagen small {
  font-size: 0.66rem;
}
.cuerpo {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  flex: 1;
}
header {
  display: flex;
  flex-direction: column;
}
.hook {
  font-size: 0.92rem;
  overflow-wrap: anywhere;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
.ver {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: auto;
}
.ver svg {
  width: 13px;
  height: 13px;
}
</style>
