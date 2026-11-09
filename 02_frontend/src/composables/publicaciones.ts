import type { EstadoEnlace, EstadoPublicacion, RedSocial } from '@/api/tipos'

/** Texto y color de cada estado de una publicación (lista y ficha). */
export const ESTADO_PUBLICACION: Record<EstadoPublicacion, { texto: string; chip: string }> = {
  BORRADOR: { texto: 'Borrador', chip: '' },
  APROBADA: { texto: 'Aprobada, por publicar', chip: 'chip-ambar' },
  PUBLICADA: { texto: 'Publicada', chip: 'chip-lima' },
}

/**
 * Cada red: nombre, límite de caracteres (Instagram cuenta también los hashtags) y dónde
 * publicar a mano mientras el envío automático no esté conectado.
 */
export const REDES: Record<RedSocial, { nombre: string; limite: number; publicar: string; ayuda: string }> = {
  FACEBOOK: {
    nombre: 'Facebook',
    limite: 5000,
    publicar: 'https://www.facebook.com/',
    ayuda: 'Entra a tu página, crea la publicación y pega el texto.',
  },
  INSTAGRAM: {
    nombre: 'Instagram',
    limite: 2200,
    publicar: 'https://www.instagram.com/',
    ayuda: 'Necesita imagen o video. Proporción de la imagen entre 4:5 (vertical) y 1,91:1 (horizontal).',
  },
  LINKEDIN: {
    nombre: 'LinkedIn',
    limite: 3000,
    publicar: 'https://www.linkedin.com/feed/',
    ayuda: 'Publica desde la página de la institución, no desde tu perfil.',
  },
}

export const ORDEN_REDES: RedSocial[] = ['FACEBOOK', 'INSTAGRAM', 'LINKEDIN']

/** Si el post sigue en su red, según la última comprobación. */
export const ESTADO_ENLACE: Record<EstadoEnlace, { texto: string; chip: string }> = {
  ACTIVA: { texto: 'Activa', chip: 'chip-lima' },
  NO_DISPONIBLE: { texto: 'Ya no está', chip: 'chip-rojo' },
  SIN_CONFIRMAR: { texto: 'Sin confirmar', chip: 'chip-ambar' },
}

/** Lo que se pega en la red: el texto y, debajo, los hashtags (igual que el backend). */
export const textoFinal = (texto: string, hashtags: string[]) =>
  [texto.trim(), hashtags.join(' ')].filter(Boolean).join('\n\n')

/** «#a, b  #c» → ['#a', '#b', '#c'], sin repetidos. */
export const leerHashtags = (t: string) => [
  ...new Set(t.split(/[\s,]+/).map((h) => h.replace(/^#+/, '')).filter(Boolean).map((h) => `#${h}`)),
]
