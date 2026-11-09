/**
 * Cliente HTTP del panel.
 *
 * Una sola puerta hacia el backend (`/api`, que Vite reenvía al 8082): aquí
 * viven el manejo de errores y la subida con progreso. Las vistas no llaman
 * a `fetch` directamente.
 *
 * El backend responde siempre `{"error": "mensaje para mostrar"}` cuando algo
 * falla (409 regla de negocio, 404 no existe, 502 fallo del worker). Ese
 * mensaje viaja tal cual en `ErrorApi.message` para mostrarlo sin retocar.
 */

export class ErrorApi extends Error {
  /** Código HTTP, o 0 si la petición ni siquiera llegó. */
  readonly estado: number
  readonly ruta: string

  // Sin propiedades en el constructor: `erasableSyntaxOnly` lo exige.
  constructor(mensaje: string, estado: number, ruta: string) {
    super(mensaje)
    this.name = 'ErrorApi'
    this.estado = estado
    this.ruta = ruta
  }
}

/** Mensaje para mostrar de cualquier error (de la API o no). */
export function mensajeDe(e: unknown): string {
  if (e instanceof ErrorApi) return e.message
  if (e instanceof Error) return e.message
  return String(e)
}

async function extraerError(respuesta: Response): Promise<string> {
  try {
    const cuerpo = await respuesta.json()
    if (cuerpo && typeof cuerpo.error === 'string' && cuerpo.error) return cuerpo.error
  } catch {
    /* la respuesta no era JSON */
  }
  if (respuesta.status === 502 || respuesta.status === 503 || respuesta.status === 504) {
    return `El backend no responde (${respuesta.status}). ¿Está corriendo en el puerto 8082?`
  }
  return `El servidor respondió ${respuesta.status}.`
}

async function pedir<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  let respuesta: Response
  try {
    respuesta = await fetch(ruta, opciones)
  } catch {
    throw new ErrorApi('No se pudo contactar con el servidor.', 0, ruta)
  }
  if (!respuesta.ok) {
    // Sesión caducada o cerrada en otro sitio: el armazón lleva a la pantalla de acceso.
    if (respuesta.status === 401 && !ruta.startsWith('/api/auth/')) {
      window.dispatchEvent(new CustomEvent('radar:sin-sesion'))
    }
    throw new ErrorApi(await extraerError(respuesta), respuesta.status, ruta)
  }
  if (respuesta.status === 204) return undefined as T
  const texto = await respuesta.text()
  return (texto ? JSON.parse(texto) : undefined) as T
}

function conJson(metodo: string, cuerpo: unknown): RequestInit {
  return {
    method: metodo,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cuerpo ?? {}),
  }
}

/** Progreso de una subida, de 0 a 1. */
export type AlProgresar = (fraccion: number) => void

/**
 * Subida multipart con progreso. `fetch` no informa del avance de lo que se
 * envía, así que aquí va XMLHttpRequest (las grabaciones pueden pesar
 * cientos de MB).
 */
function subir<T>(ruta: string, datos: FormData, alProgresar?: AlProgresar): Promise<T> {
  return new Promise<T>((resolver, rechazar) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', ruta)
    xhr.responseType = 'text'
    xhr.upload.onprogress = (ev) => {
      if (ev.lengthComputable && alProgresar) alProgresar(ev.loaded / ev.total)
    }
    xhr.onerror = () => rechazar(new ErrorApi('No se pudo contactar con el servidor.', 0, ruta))
    xhr.onabort = () => rechazar(new ErrorApi('Subida cancelada.', 0, ruta))
    xhr.onload = () => {
      let cuerpo: unknown = undefined
      try {
        cuerpo = xhr.responseText ? JSON.parse(xhr.responseText) : undefined
      } catch {
        /* no era JSON */
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolver(cuerpo as T)
        return
      }
      const error = (cuerpo as { error?: string } | undefined)?.error
      rechazar(new ErrorApi(error || `El servidor respondió ${xhr.status}.`, xhr.status, ruta))
    }
    xhr.send(datos)
  })
}

export const api = {
  obtener: <T>(ruta: string) => pedir<T>(ruta),
  enviar: <T>(ruta: string, cuerpo?: unknown) => pedir<T>(ruta, conJson('POST', cuerpo)),
  poner: <T>(ruta: string, cuerpo: unknown) => pedir<T>(ruta, conJson('PUT', cuerpo)),
  borrar: <T>(ruta: string) => pedir<T>(ruta, { method: 'DELETE' }),
  subir,
}
