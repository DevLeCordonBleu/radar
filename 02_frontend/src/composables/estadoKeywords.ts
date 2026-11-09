/** Estado de la conexión con Google Ads y paises/idiomas disponibles: se pide una vez y se comparte. */
import { computed, ref } from 'vue'
import { keywords } from '@/api/radar'
import type { EstadoKeywords } from '@/api/tipos'

const estado = ref<EstadoKeywords | null>(null)
const error = ref('')

export function useEstadoKeywords() {
  async function cargar(forzar = false) {
    if (estado.value && !forzar) return
    try {
      estado.value = await keywords.estado()
      error.value = ''
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    }
  }
  /** Sin Google Ads conectado solo se pueden ver datos de demostración. */
  const conectado = computed(() => estado.value?.google_ads.completo === true)
  return { estado, error, cargar, conectado }
}
