/**
 * Sets de palabras para el filtro gratuito del Plan SEO («Rubro de tu negocio»). Se eligen
 * enteros en vez de escribir las palabras una por una. Las cuatro primeras juntas son el
 * rubro por defecto de ILCB (`SectorSeo.POR_DEFECTO` en el backend); las demás sirven para
 * competidores que también enseñan turismo, hotelería o nutrición.
 *
 * Mismas reglas que el filtro: minúsculas, sin tildes, una palabra por término; con 4 letras
 * o más cuenta como comienzo («cocin» → cocina, cocinero), con 3 o menos solo entera.
 */
export interface SetRubro {
  nombre: string
  palabras: string[]
}

export const SETS_RUBRO: SetRubro[] = [
  {
    nombre: 'Cocina',
    palabras: ['gastronom', 'cocin', 'culinar', 'chef', 'receta', 'plato', 'comida', 'gourmet', 'parrill', 'cevich', 'sushi', 'aliment', 'food'],
  },
  {
    nombre: 'Pastelería y panadería',
    palabras: ['pastel', 'reposter', 'panader', 'panific', 'bolleri', 'postre', 'chocolat', 'torta', 'pan', 'panes'],
  },
  {
    nombre: 'Bar y coctelería',
    palabras: ['coctel', 'cocktail', 'mixolog', 'bartender', 'barman', 'bar', 'bares', 'pisco', 'cervez', 'bebida'],
  },
  {
    nombre: 'Vinos y café',
    palabras: ['sommelier', 'somelier', 'enolog', 'vinic', 'vino', 'barista', 'cafe'],
  },
  {
    nombre: 'Restaurantes y servicio',
    palabras: ['restaurant', 'catering', 'mesero', 'mozo', 'maitre', 'menu', 'delivery'],
  },
  {
    nombre: 'Hotelería y turismo',
    palabras: ['hotel', 'turism', 'turist', 'ecoturism', 'hospedaj', 'hospitalid', 'housekeep', 'resort'],
  },
  {
    nombre: 'Nutrición e inocuidad',
    palabras: ['nutric', 'dietet', 'dieta', 'inocu', 'haccp', 'bromatolog', 'saludabl'],
  },
]

/** Como la normaliza el backend: minúsculas y sin tildes. */
export const normalizarPalabra = (p: string) =>
  p.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().trim()

/** Cuántas palabras del set están elegidas. */
export const elegidasDelSet = (s: SetRubro, palabras: string[]) => s.palabras.filter((p) => palabras.includes(p)).length

/** Los sets que están completos en la lista. */
export const setsCompletos = (palabras: string[]) =>
  SETS_RUBRO.filter((s) => elegidasDelSet(s, palabras) === s.palabras.length)

/** Las palabras que no son de ningún set: las que escribió la persona. */
export const palabrasPropias = (palabras: string[]) => {
  const deSets = new Set(SETS_RUBRO.flatMap((s) => s.palabras))
  return palabras.filter((p) => !deSets.has(p))
}

/**
 * Activa el set si le falta alguna palabra; si ya estaba completo, lo quita (sin tocar las
 * palabras que también son de otro set completo).
 */
export function alternarSet(s: SetRubro, palabras: string[]): string[] {
  if (elegidasDelSet(s, palabras) < s.palabras.length) return [...palabras, ...s.palabras.filter((p) => !palabras.includes(p))]
  const otras = new Set(setsCompletos(palabras).filter((o) => o !== s).flatMap((o) => o.palabras))
  return palabras.filter((p) => !s.palabras.includes(p) || otras.has(p))
}
