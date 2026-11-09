/**
 * Sondeo mientras haya trabajo en curso.
 *
 * La producción corre en el backend (voz, visuales, montaje, publicación) y
 * no hay notificaciones: la vista abierta pregunta cada pocos segundos
 * mientras `activo()` sea verdadero, y se detiene sola al salir de la vista.
 * Un sondeo no se solapa con el anterior: el siguiente se programa cuando
 * termina la petición en curso.
 */
import { onBeforeUnmount, watch } from 'vue'

export function useSondeo(
  refrescar: () => Promise<unknown>,
  activo: () => boolean,
  intervaloMs = 3500,
) {
  let temporizador: ReturnType<typeof setTimeout> | null = null
  let vivo = true

  function detener() {
    if (temporizador) clearTimeout(temporizador)
    temporizador = null
  }

  function programar() {
    detener()
    if (!vivo || !activo()) return
    temporizador = setTimeout(async () => {
      temporizador = null
      try {
        await refrescar()
      } catch {
        /* el error ya lo muestra quien refresca; se sigue intentando */
      }
      programar()
    }, intervaloMs)
  }

  watch(activo, (si) => (si ? programar() : detener()), { immediate: true })

  onBeforeUnmount(() => {
    vivo = false
    detener()
  })

  return { detener, programar }
}
