<script setup lang="ts">
/**
 * Muestra UNA vez un dato que el backend no vuelve a dar (código de
 * recuperación o contraseña temporal). No se cierra hasta que la persona
 * confirma que lo ha guardado, y deja copiarlo.
 */
import { nextTick, ref, watch } from 'vue'
import Icono from './Icono.vue'

const props = defineProps<{ abierto: boolean; titulo: string; texto: string; valor: string; aceptar?: string }>()
const emit = defineEmits<{ cerrar: [] }>()

const dialogo = ref<HTMLDialogElement | null>(null)
const guardado = ref(false)
const copiado = ref(false)

watch(
  () => props.abierto,
  async (si) => {
    if (si) {
      guardado.value = false
      copiado.value = false
      await nextTick()
      if (dialogo.value && !dialogo.value.open) dialogo.value.showModal()
    } else if (dialogo.value?.open) {
      dialogo.value.close()
    }
  },
)

async function copiar() {
  try {
    await navigator.clipboard.writeText(props.valor)
    copiado.value = true
  } catch {
    /* sin permiso de portapapeles: se puede seleccionar a mano */
  }
}
</script>

<template>
  <dialog ref="dialogo" class="secreto" aria-labelledby="secreto-titulo" @cancel.prevent>
    <h2 id="secreto-titulo"><Icono nombre="llave" /> {{ titulo }}</h2>
    <p class="suave">{{ texto }}</p>
    <p class="valor mono" tabindex="0">{{ valor }}</p>
    <div class="fila">
      <button class="boton" type="button" @click="copiar"><Icono nombre="copiar" /> {{ copiado ? 'Copiado' : 'Copiar' }}</button>
    </div>
    <label class="casilla"><input v-model="guardado" type="checkbox" /> Lo he guardado en un lugar seguro</label>
    <div class="fila fila-fin">
      <button class="boton boton-primario" type="button" :disabled="!guardado" @click="emit('cerrar')">{{ aceptar ?? 'Continuar' }}</button>
    </div>
  </dialog>
</template>

<style scoped>
.secreto {
  margin: auto;
  width: min(480px, calc(100vw - 32px));
  padding: 22px;
  background: var(--panel);
  color: var(--texto);
  border: 1px solid var(--borde-fuerte);
  border-radius: var(--radio);
  box-shadow: var(--sombra);
}
.secreto::backdrop {
  background: rgba(3, 7, 18, 0.7);
}
.secreto > * + * {
  margin-top: 14px;
}
h2 {
  display: flex;
  align-items: center;
  gap: 8px;
}
h2 svg {
  width: 20px;
  height: 20px;
  color: var(--ambar);
}
.valor {
  padding: 14px;
  text-align: center;
  font-size: 1.12rem;
  letter-spacing: 0.06em;
  background: var(--panel-2);
  border: 1px dashed var(--borde-fuerte);
  border-radius: var(--radio-chico);
  user-select: all;
  overflow-wrap: anywhere;
}
</style>
