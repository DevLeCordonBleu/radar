<script setup lang="ts">
/**
 * Diálogo modal de confirmación (uno solo para todo el panel). Usa <dialog>
 * nativo: atrapa el foco y se cierra con Escape.
 */
import { computed, nextTick, ref, watch } from 'vue'
import { confirmacionActual, responder } from '@/composables/confirmar'

const dialogo = ref<HTMLDialogElement | null>(null)
const texto = ref('')
const actual = computed(() => confirmacionActual.value)

const puedeAceptar = computed(
  () => !actual.value?.campo?.obligatorio || texto.value.trim().length > 0,
)

const claseBoton = computed(() => {
  switch (actual.value?.tono) {
    case 'peligro':
      return 'boton-peligro'
    case 'exito':
      return 'boton-exito'
    case 'aviso':
      return 'boton-aviso'
    default:
      return 'boton-primario'
  }
})

watch(actual, async (p) => {
  if (p) {
    texto.value = ''
    await nextTick()
    if (dialogo.value && !dialogo.value.open) dialogo.value.showModal()
  } else if (dialogo.value?.open) {
    dialogo.value.close()
  }
})

function aceptar() {
  if (!puedeAceptar.value) return
  responder({ ok: true, texto: texto.value.trim() })
}

function cancelar() {
  responder({ ok: false, texto: '' })
}
</script>

<template>
  <dialog
    ref="dialogo"
    class="dialogo"
    aria-labelledby="dialogo-titulo"
    @cancel.prevent="cancelar"
  >
    <form v-if="actual" method="dialog" @submit.prevent="aceptar">
      <h2 id="dialogo-titulo">{{ actual.titulo }}</h2>
      <p v-if="actual.mensaje" class="mensaje">{{ actual.mensaje }}</p>
      <ul v-if="actual.puntos?.length" class="puntos">
        <li v-for="(p, i) in actual.puntos" :key="i">{{ p }}</li>
      </ul>
      <div v-if="actual.campo" class="campo">
        <label for="dialogo-campo">{{ actual.campo.etiqueta }}</label>
        <textarea
          id="dialogo-campo"
          v-model="texto"
          rows="3"
          :placeholder="actual.campo.marcador"
          autofocus
        ></textarea>
      </div>
      <div class="fila fila-fin acciones">
        <button class="boton" type="button" @click="cancelar">
          {{ actual.cancelar || 'Cancelar' }}
        </button>
        <button class="boton" :class="claseBoton" type="submit" :disabled="!puedeAceptar" :autofocus="!actual.campo">
          {{ actual.aceptar }}
        </button>
      </div>
    </form>
  </dialog>
</template>

<style scoped>
.dialogo {
  margin: auto;
  width: min(540px, calc(100vw - 32px));
  background: var(--panel);
  color: var(--texto);
  border: 1px solid var(--borde-fuerte);
  border-radius: var(--radio);
  padding: 22px 24px;
  box-shadow: var(--sombra);
}
.dialogo::backdrop {
  background: rgba(3, 7, 18, 0.7);
}
h2 {
  margin-bottom: 10px;
}
.mensaje {
  color: var(--texto-suave);
  white-space: pre-line;
}
.puntos {
  margin: 12px 0 0 18px;
  color: var(--texto-suave);
  display: grid;
  gap: 4px;
}
.campo {
  margin-top: 14px;
}
.acciones {
  margin-top: 20px;
}
</style>
