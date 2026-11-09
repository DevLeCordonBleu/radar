/**
 * Avisos flotantes del panel.
 *
 * Los errores de la API se muestran tal cual llegan (`{"error": "..."}`) y
 * se quedan hasta que alguien los cierra: suelen explicar qué hacer. Los de
 * éxito se van solos.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { mensajeDe } from '@/api/cliente'

export type TipoAviso = 'exito' | 'error' | 'info' | 'ambar'

export interface Aviso {
  id: number
  tipo: TipoAviso
  titulo: string
  texto: string
}

let siguiente = 1

export const useAvisos = defineStore('avisos', () => {
  const lista = ref<Aviso[]>([])

  function quitar(id: number) {
    lista.value = lista.value.filter((a) => a.id !== id)
  }

  function mostrar(tipo: TipoAviso, texto: string, titulo = '', duracionMs = 0) {
    const id = siguiente++
    // Un mismo error repetido (p. ej. al sondear) no se apila.
    lista.value = lista.value.filter((a) => !(a.tipo === tipo && a.texto === texto))
    lista.value.push({ id, tipo, titulo, texto })
    if (lista.value.length > 5) lista.value.shift()
    if (duracionMs > 0) setTimeout(() => quitar(id), duracionMs)
    return id
  }

  return {
    lista,
    quitar,
    exito: (texto: string, titulo = '') => mostrar('exito', texto, titulo, 4500),
    info: (texto: string, titulo = '') => mostrar('info', texto, titulo, 6000),
    ambar: (texto: string, titulo = '') => mostrar('ambar', texto, titulo),
    error: (e: unknown, titulo = 'No se pudo completar') => mostrar('error', mensajeDe(e), titulo),
  }
})
