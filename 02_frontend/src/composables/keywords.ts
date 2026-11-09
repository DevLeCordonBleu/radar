/**
 * Lógica compartida de KeyWords Explorer: formatos, filtros, orden y CSV.
 * Todo es cliente: los resultados (hasta 2000 filas) ya están en el navegador.
 */
import type { FilaKeyword, Intencion } from '@/api/tipos'

// ── Formatos ──────────────────────────────────────────────────────────────

const entero = new Intl.NumberFormat('es-PE', { maximumFractionDigits: 0 })

export const num = (n: number | null | undefined) => (n == null ? '—' : entero.format(n))

/** 1 900 → «1,9 mil»; 1 200 000 → «1,2 M». Para tarjetas, donde el espacio es poco. */
export function compacto(n: number | null | undefined): string {
  if (n == null) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toLocaleString('es-PE', { maximumFractionDigits: 1 })} M`
  if (n >= 10_000) return `${Math.round(n / 1000).toLocaleString('es-PE')} mil`
  return entero.format(n)
}

export function dinero(n: number | null | undefined, moneda: string | null): string {
  if (n == null) return '—'
  try {
    return new Intl.NumberFormat('es-PE', { style: 'currency', currency: moneda || 'USD', currencyDisplay: 'narrowSymbol', minimumFractionDigits: 2 }).format(n)
  } catch {
    return n.toFixed(2)
  }
}

export const ETIQUETA_INTENCION: Record<Intencion, { letra: string; nombre: string; ayuda: string }> = {
  informacional: { letra: 'I', nombre: 'Informacional', ayuda: 'Quiere aprender o resolver una duda' },
  comercial: { letra: 'C', nombre: 'Comercial', ayuda: 'Compara antes de decidir' },
  transaccional: { letra: 'T', nombre: 'Transaccional', ayuda: 'Está listo para comprar o contratar' },
  navegacional: { letra: 'N', nombre: 'Navegacional', ayuda: 'Busca una marca o sitio concreto' },
}

export const ETIQUETA_COMPETENCIA = { baja: 'Baja', media: 'Media', alta: 'Alta' } as const

// ── Filtros ───────────────────────────────────────────────────────────────

export interface Filtros {
  volMin: number | null
  volMax: number | null
  cpcMax: number | null
  competencia: '' | 'baja' | 'media' | 'alta'
  intencion: Intencion[]
  palabrasMin: number | null
  palabrasMax: number | null
  incluir: string
  excluir: string
  soloConVolumen: boolean
  termino: string
}

export const filtrosVacios = (): Filtros => ({
  volMin: null, volMax: null, cpcMax: null, competencia: '', intencion: [], palabrasMin: null, palabrasMax: null,
  incluir: '', excluir: '', soloConVolumen: false, termino: '',
})

export function hayFiltros(f: Filtros): boolean {
  const v = filtrosVacios()
  return (Object.keys(v) as (keyof Filtros)[]).some((k) => JSON.stringify(f[k]) !== JSON.stringify(v[k]))
}

const plano = (t: string) => t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
const lista = (t: string) => t.split(',').map((x) => plano(x.trim())).filter(Boolean)

export function filtrar(filas: FilaKeyword[], f: Filtros): FilaKeyword[] {
  const inc = lista(f.incluir)
  const exc = lista(f.excluir)
  const term = plano(f.termino)
  return filas.filter((k) => {
    const t = plano(k.keyword)
    if (f.soloConVolumen && !k.volumen) return false
    if (f.volMin != null && (k.volumen ?? -1) < f.volMin) return false
    if (f.volMax != null && (k.volumen == null || k.volumen > f.volMax)) return false
    if (f.cpcMax != null && (k.cpc == null || k.cpc > f.cpcMax)) return false
    if (f.competencia && k.competencia !== f.competencia) return false
    if (f.intencion.length && !f.intencion.some((i) => k.intencion.includes(i))) return false
    if (f.palabrasMin != null && k.palabras < f.palabrasMin) return false
    if (f.palabrasMax != null && k.palabras > f.palabrasMax) return false
    if (inc.length && !inc.some((x) => t.includes(x))) return false
    if (exc.length && exc.some((x) => t.includes(x))) return false
    if (term && !t.split(/\s+/).some((w) => w === term || (term.length > 3 && w.startsWith(term.slice(0, -1))))) return false
    return true
  })
}

// ── Orden ─────────────────────────────────────────────────────────────────

export type ColumnaOrden = 'keyword' | 'volumen' | 'cpc' | 'competencia_idx' | 'palabras'

/** Las keywords sin dato van siempre al final, sea cual sea el sentido. */
export function ordenar(filas: FilaKeyword[], col: ColumnaOrden, desc: boolean): FilaKeyword[] {
  const dir = desc ? -1 : 1
  return [...filas].sort((a, b) => {
    const x = a[col]
    const y = b[col]
    if (x == null && y == null) return a.keyword.localeCompare(b.keyword)
    if (x == null) return 1
    if (y == null) return -1
    if (typeof x === 'string' && typeof y === 'string') return dir * x.localeCompare(y, 'es')
    return dir * ((x as number) - (y as number)) || a.keyword.localeCompare(b.keyword)
  })
}

// ── CSV ───────────────────────────────────────────────────────────────────

const celda = (v: unknown) => {
  const t = v == null ? '' : String(v)
  return /[",\n\r]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t
}

/** CSV con BOM para que Excel abra bien las tildes. */
export function aCsv(filas: FilaKeyword[], pais: string, moneda: string | null): string {
  const cab = ['Keyword', 'Volumen mensual', `CPC (${moneda ?? ''})`, 'Competencia de anuncios', 'Índice de competencia (0-100)', 'Intención (estimada)', 'Tipo', 'Es pregunta', 'Sugerencia de Google', 'Palabras', 'Tendencia 12 meses', 'País', 'Nota']
  const filasCsv = filas.map((k) => [
    k.keyword, k.volumen, k.cpc, k.competencia ? ETIQUETA_COMPETENCIA[k.competencia] : '', k.competencia_idx,
    k.intencion.map((i) => ETIQUETA_INTENCION[i].nombre).join(' / '), k.tipo === 'coincidente' ? 'Coincidente' : 'Relacionada',
    k.pregunta ? 'Sí' : 'No', k.sugerencia ? 'Sí' : 'No', k.palabras, k.tendencia.join(' '), pais, k.nota ?? '',
  ])
  return '﻿' + [cab, ...filasCsv].map((f) => f.map(celda).join(',')).join('\r\n')
}

export function descargarCsv(nombre: string, contenido: string) {
  const url = URL.createObjectURL(new Blob([contenido], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = nombre.replace(/[^\p{L}\p{N}_-]+/gu, '-').replace(/-+/g, '-') + '.csv'
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

// ── Conexión con Google Ads ───────────────────────────────────────────────

export const CAMPOS_GOOGLE_ADS: Record<string, string> = {
  developer_token: 'Developer token (GOOGLE_ADS_DEVELOPER_TOKEN)',
  client_id: 'ID de cliente OAuth (GOOGLE_ADS_CLIENT_ID)',
  client_secret: 'Secreto de cliente OAuth (GOOGLE_ADS_CLIENT_SECRET)',
  refresh_token: 'Refresh token (GOOGLE_ADS_REFRESH_TOKEN)',
  customer_id: 'ID de la cuenta de Google Ads (GOOGLE_ADS_CUSTOMER_ID)',
}
