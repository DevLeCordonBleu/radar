/** Formatos de numeros, fechas y etiquetas que comparten varias vistas. */
import type { EstadoAnalisis, Frecuencia } from '@/api/tipos'

const decimal = new Intl.NumberFormat('es-PE', { maximumFractionDigits: 1 })
const dinero = new Intl.NumberFormat('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

export const pct = (n: number) => `${decimal.format(n)} %`
export const usd = (n: number) => `${dinero.format(n)} US$`

export function fecha(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString('es-PE', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function fechaHora(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString('es-PE', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

/** "3 meses" / "12 días": como lo diría una persona, no un contador. */
export function duracionActivo(dias: number): string {
  if (dias >= 60) return `${Math.round(dias / 30)} meses`
  if (dias >= 30) return '1 mes'
  return `${dias} ${dias === 1 ? 'día' : 'días'}`
}

/** Días que lleva (o llevó) activo un anuncio; `null` si la fecha no se entiende. */
export function diasActivo(a: { dias_activo?: number; fecha_inicio: string }): number | null {
  if (a.dias_activo != null) return a.dias_activo
  const d = Math.floor((Date.now() - new Date(a.fecha_inicio).getTime()) / 864e5)
  return Number.isFinite(d) && d >= 0 ? d : null
}

/**
 * Primero los que más tiempo llevan activos: es la única pista de rendimiento
 * que da la Biblioteca de Meta. A igualdad, se respeta el orden de llegada.
 */
export const porDiasActivo = <T extends { dias_activo?: number; fecha_inicio: string }>(lista: T[]): T[] =>
  [...lista].sort((a, b) => (diasActivo(b) ?? -1) - (diasActivo(a) ?? -1))

export const ETIQUETA_FRECUENCIA: Record<Frecuencia, string> = {
  muy_alta: 'Muy repetido',
  alta: 'Repetido',
  media: 'Habitual',
  baja: 'Poco usado',
  hueco: 'Casi libre',
}

export const ETIQUETA_ESTADO: Record<EstadoAnalisis, string> = {
  en_cola: 'En cola',
  corriendo: 'En marcha',
  pausado: 'Pausado',
  terminado: 'Terminado',
  cancelado: 'Cancelado',
}

export const CLASE_ESTADO: Record<EstadoAnalisis, string> = {
  en_cola: 'chip-violeta',
  corriendo: 'chip-cian',
  pausado: 'chip-ambar',
  terminado: 'chip-lima',
  cancelado: 'chip-rojo',
}

export const PAISES: { codigo: string; nombre: string }[] = [
  { codigo: 'PE', nombre: 'Perú' },
  { codigo: 'MX', nombre: 'México' },
  { codigo: 'CO', nombre: 'Colombia' },
  { codigo: 'CL', nombre: 'Chile' },
  { codigo: 'AR', nombre: 'Argentina' },
  { codigo: 'EC', nombre: 'Ecuador' },
  { codigo: 'ES', nombre: 'España' },
  { codigo: 'US', nombre: 'Estados Unidos' },
]

/** Redes de Meta donde puede salir un anuncio (`publisher_platform` de la Biblioteca). */
export const NOMBRE_PLATAFORMA: Record<string, string> = {
  facebook: 'Facebook',
  instagram: 'Instagram',
  messenger: 'Messenger',
  whatsapp: 'WhatsApp',
  threads: 'Threads',
  audience_network: 'Audience Network',
}

export const enMeta = (pageId: string, pais = 'PE') =>
  `https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=${pais}&view_all_page_id=${pageId}&search_type=page`
