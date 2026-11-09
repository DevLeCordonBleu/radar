/**
 * Quién está dentro. El estado viene del backend (`/api/auth/estado`): la
 * cookie de sesión es HttpOnly, así que el panel no la ve ni la guarda.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { auth } from '@/api/radar'
import type { RespuestaAcceso, Usuario } from '@/api/tipos'

export const useAuth = defineStore('auth', () => {
  const cargado = ref(false)
  const necesitaAlta = ref(false)
  const usuario = ref<Usuario | null>(null)

  const esAdmin = computed(() => usuario.value?.rol === 'admin')

  async function cargar(forzar = false) {
    if (cargado.value && !forzar) return
    const e = await auth.estado()
    necesitaAlta.value = e.necesitaAlta
    usuario.value = e.usuario
    cargado.value = true
  }

  /** Aplica la respuesta de entrar / alta / recuperar / cuenta. */
  function fijar(r: RespuestaAcceso) {
    usuario.value = r.usuario
    necesitaAlta.value = false
    cargado.value = true
  }

  async function salir() {
    try {
      await auth.salir()
    } finally {
      usuario.value = null
    }
  }

  function sesionCaducada() {
    usuario.value = null
  }

  return { cargado, necesitaAlta, usuario, esAdmin, cargar, fijar, salir, sesionCaducada }
})
