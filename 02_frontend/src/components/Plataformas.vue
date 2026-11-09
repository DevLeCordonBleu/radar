<script setup lang="ts">
/**
 * En qué redes de Meta sale un anuncio (Facebook, Instagram…), tal como lo dice la
 * Biblioteca. Los anuncios de informes anteriores no lo traen: entonces no se muestra nada.
 */
import { NOMBRE_PLATAFORMA } from '@/composables/formato'

defineProps<{ plataformas?: string[] | null }>()
</script>

<template>
  <ul v-if="plataformas?.length" class="plataformas" aria-label="Sale en">
    <li v-for="p in plataformas" :key="p" class="chip" :class="`red-${p}`">
      <span class="punto" aria-hidden="true"></span>{{ NOMBRE_PLATAFORMA[p] ?? p }}
    </li>
  </ul>
</template>

<style scoped>
.plataformas {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.punto {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--texto-tenue);
  flex: none;
}
.red-facebook .punto {
  background: #1877f2;
}
.red-instagram .punto {
  background: linear-gradient(45deg, #f58529, #dd2a7b 50%, #8134af);
}
.red-messenger .punto {
  background: #0a7cff;
}
.red-whatsapp .punto {
  background: #25d366;
}
.red-threads .punto {
  background: var(--texto);
}
</style>
