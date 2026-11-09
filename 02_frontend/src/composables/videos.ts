import type { EstadoVideo } from '@/api/tipos'

/** Texto y color de cada estado de un video (lista y ficha). */
export const ESTADO_VIDEO: Record<EstadoVideo, { texto: string; chip: string }> = {
  IDEA: { texto: 'Idea', chip: '' },
  GUION: { texto: 'Guion listo', chip: 'chip-cian' },
  GENERANDO: { texto: 'Generando en Vids', chip: 'chip-violeta' },
  GENERADO: { texto: 'Por aprobar', chip: 'chip-ambar' },
  APROBADO: { texto: 'Aprobado', chip: 'chip-lima' },
  ERROR: { texto: 'Con error', chip: 'chip-rojo' },
}

/** Palabras que caben en ~10 s de voz. */
export const MAX_PALABRAS_CLIP = 22

export const palabras = (t: string) => t.trim().split(/\s+/).filter(Boolean).length

/** «[FALTA: fecha de inicio]» → «fecha de inicio». */
export const faltas = (t: string) => [...t.matchAll(/\[FALTA:?\s*([^\]]*)]/gi)].map((m) => m[1].trim())
