<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<template>
  <div class="pagina">
    <div class="vacio">
      <h1>No encontrado</h1>
      <p class="suave">Esa página no existe.</p>
      <RouterLink to="/" class="boton boton-primario">Ir a los informes</RouterLink>
    </div>
  </div>
</template>
