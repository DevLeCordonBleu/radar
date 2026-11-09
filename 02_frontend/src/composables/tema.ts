/**
 * Tema claro / oscuro. Se guarda en este navegador (es una preferencia de quien
 * mira, no un dato del equipo) y, sin elección previa, sigue al sistema.
 */
import { ref } from 'vue'

export type Tema = 'oscuro' | 'claro'

const CLAVE = 'radar.tema'

function inicial(): Tema {
  try {
    const guardado = localStorage.getItem(CLAVE)
    if (guardado === 'claro' || guardado === 'oscuro') return guardado
  } catch {
    /* localStorage bloqueado: se sigue al sistema */
  }
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'claro' : 'oscuro'
}

export const tema = ref<Tema>(inicial())

function aplicar(t: Tema) {
  document.documentElement.dataset.tema = t
  document.querySelector('meta[name="color-scheme"]')?.setAttribute('content', t === 'claro' ? 'light' : 'dark')
}

aplicar(tema.value)

export function alternarTema() {
  tema.value = tema.value === 'claro' ? 'oscuro' : 'claro'
  aplicar(tema.value)
  try {
    localStorage.setItem(CLAVE, tema.value)
  } catch {
    /* no se pudo recordar: vale para esta visita */
  }
}
