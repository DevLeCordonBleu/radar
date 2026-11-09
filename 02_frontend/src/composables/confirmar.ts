/**
 * Confirmaciones con un diálogo propio (no `window.confirm`): dejan explicar
 * qué pasa al aceptar —por ejemplo, que aprobar el guion arranca la
 * producción— y, si hace falta, pedir un texto (el motivo de un rechazo).
 *
 *   const r = await confirmar({ titulo: '¿Descartar?', aceptar: 'Descartar', tono: 'peligro' })
 *   if (r.ok) ...
 */
import { ref } from 'vue'

export interface PeticionConfirmar {
  titulo: string
  mensaje?: string
  puntos?: string[]
  aceptar: string
  cancelar?: string
  tono?: 'primario' | 'exito' | 'peligro' | 'aviso'
  /** Pide un texto antes de aceptar. */
  campo?: { etiqueta: string; marcador?: string; obligatorio?: boolean }
}

export interface RespuestaConfirmar {
  ok: boolean
  texto: string
}

interface Pendiente extends PeticionConfirmar {
  resolver: (r: RespuestaConfirmar) => void
}

export const confirmacionActual = ref<Pendiente | null>(null)

export function confirmar(p: PeticionConfirmar): Promise<RespuestaConfirmar> {
  // Si había otra abierta, se da por cancelada.
  confirmacionActual.value?.resolver({ ok: false, texto: '' })
  return new Promise((resolver) => {
    confirmacionActual.value = { ...p, resolver }
  })
}

export function responder(r: RespuestaConfirmar) {
  const actual = confirmacionActual.value
  confirmacionActual.value = null
  actual?.resolver(r)
}
