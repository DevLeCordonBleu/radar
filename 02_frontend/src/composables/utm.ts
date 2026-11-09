/**
 * UTM en los enlaces a la web propia de un post (Facebook y LinkedIn), igual que el backend
 * (`aplicacion/Utm.kt`): si cambia uno, cambiar el otro. Y el constructor de enlaces de la
 * página Medición.
 */
import type { RedSocial } from '@/api/tipos'

const URL_RE = /https?:\/\/[^\s<>"'()[\]]+/g
const FUENTES: Partial<Record<RedSocial, string>> = { FACEBOOK: 'facebook', LINKEDIN: 'linkedin' }

/** «Ven y conoce el Campus!» → «ven-y-conoce-el-campus». */
export function slug(t: string): string {
  return t
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40)
    .replace(/-+$/g, '')
}

export function agregarUtm(url: string, p: { fuente: string; medio: string; campana: string; contenido?: string; termino?: string }): string {
  if (/[?&]utm_/i.test(url)) return url
  const corte = url.indexOf('#')
  const base = corte >= 0 ? url.slice(0, corte) : url
  const ancla = corte >= 0 ? url.slice(corte) : ''
  const params = [
    ['utm_source', p.fuente],
    ['utm_medium', p.medio],
    ['utm_campaign', p.campana],
    ['utm_content', p.contenido ?? ''],
    ['utm_term', p.termino ?? ''],
  ].filter(([, v]) => v.trim())
  // Las llaves de Meta ({{campaign.name}}) tienen que llegar tal cual: no se codifican.
  const valor = (v: string) => (/^\{\{[\w.]+\}\}$/.test(v) ? v : encodeURIComponent(v.trim()))
  return base + (base.includes('?') ? '&' : '?') + params.map(([k, v]) => `${k}=${valor(v)}`).join('&') + ancla
}

function propio(url: string, dominios: string[]): boolean {
  try {
    const host = new URL(url).hostname.toLowerCase().replace(/^www\./, '')
    return dominios.some((d) => host === d || host.endsWith(`.${d}`))
  } catch {
    return false
  }
}

/** El texto con UTM en los enlaces a `dominios`; la puntuación final queda fuera del enlace. */
export function utmEnTexto(texto: string, red: RedSocial, codigo: string, titulo: string, dominios: string[]): string {
  const fuente = FUENTES[red]
  if (!fuente || !dominios.length) return texto
  return texto.replace(URL_RE, (crudo) => {
    const url = crudo.replace(/[.,;:!?]+$/, '')
    if (!propio(url, dominios)) return crudo
    return agregarUtm(url, { fuente, medio: 'social', campana: slug(titulo) || 'publicacion', contenido: codigo.toLowerCase() }) + crudo.slice(url.length)
  })
}
