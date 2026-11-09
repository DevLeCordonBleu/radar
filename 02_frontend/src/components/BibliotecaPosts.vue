<script setup lang="ts">
/**
 * Biblioteca de posts: todas las publicaciones, archivadas incluidas (nada se borra), con su
 * historial en la ficha y la comprobación de si cada enlace publicado sigue en su red.
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { publicaciones } from '@/api/radar'
import type { EstadoEnlace, Publicacion, RedSocial } from '@/api/tipos'
import Icono from '@/components/Icono.vue'
import { fecha, fechaHora } from '@/composables/formato'
import { descargarCsv } from '@/composables/keywords'
import { ESTADO_ENLACE, ESTADO_PUBLICACION, ORDEN_REDES, REDES, textoFinal } from '@/composables/publicaciones'
import { useAuth } from '@/stores/auth'
import { useAvisos } from '@/stores/avisos'

const auth = useAuth()
const avisos = useAvisos()
const lista = ref<Publicacion[]>([])
const cargando = ref(true)
const ocupado = ref<string | null>(null)

const filtro = ref({ texto: '', estado: '', red: '' as '' | RedSocial, enlace: '' as '' | EstadoEnlace | 'SIN_COMPROBAR', desde: '', hasta: '' })

async function cargar() {
  try {
    lista.value = await publicaciones.listar(true)
  } catch (e) {
    avisos.error(e)
  } finally {
    cargando.value = false
  }
}
onMounted(cargar)

const visibles = computed(() => {
  const f = filtro.value
  const t = f.texto.trim().toLowerCase()
  return lista.value.filter((p) => {
    if (t && ![p.codigo, p.titulo, p.idea, ...Object.values(p.textos)].some((x) => (x ?? '').toLowerCase().includes(t))) return false
    if (f.estado === 'ARCHIVADA' ? !p.archivada : f.estado && (p.archivada || p.estado !== f.estado)) return false
    if (f.red && !p.redes.includes(f.red)) return false
    if (f.enlace) {
      const conEnlace = Object.keys(p.enlaces) as RedSocial[]
      if (!conEnlace.length) return false
      if (f.enlace === 'SIN_COMPROBAR' ? conEnlace.every((r) => p.verificacion[r]) : !conEnlace.some((r) => p.verificacion[r]?.estado === f.enlace)) return false
    }
    const dia = p.creado.slice(0, 10)
    if (f.desde && dia < f.desde) return false
    if (f.hasta && dia > f.hasta) return false
    return true
  })
})
const conEnlaces = computed(() => lista.value.filter((p) => Object.keys(p.enlaces).length).length)

async function comprobar(p: Publicacion) {
  ocupado.value = p.codigo
  try {
    const n = await publicaciones.verificar(p.codigo)
    lista.value = lista.value.map((x) => (x.codigo === n.codigo ? n : x))
    const malas = Object.values(n.verificacion).filter((v) => v.estado === 'NO_DISPONIBLE').length
    if (malas) avisos.error(`${n.codigo}: ${malas} ${malas === 1 ? 'enlace ya no está disponible' : 'enlaces ya no están disponibles'}.`)
    else avisos.exito(`${n.codigo} comprobada.`)
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = null
  }
}

async function comprobarTodas() {
  ocupado.value = 'todas'
  try {
    const r = await publicaciones.verificarTodas()
    await cargar()
    avisos.exito(
      `${r.enlaces} enlaces de ${r.publicaciones} publicaciones: ${r.ACTIVA ?? 0} activos, ${r.NO_DISPONIBLE ?? 0} ya no disponibles, ${r.SIN_CONFIRMAR ?? 0} sin confirmar.`,
    )
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = null
  }
}

async function restaurar(p: Publicacion) {
  try {
    const n = await publicaciones.restaurar(p.codigo)
    lista.value = lista.value.map((x) => (x.codigo === n.codigo ? n : x))
    avisos.exito(`${p.codigo} vuelve a la lista.`)
  } catch (e) {
    avisos.error(e)
  }
}

function exportar() {
  const celda = (v: unknown) => {
    const t = String(v ?? '')
    return /[",\r\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t
  }
  const cab = ['codigo', 'titulo', 'estado', 'archivada', 'creada', 'autor', 'aprobador', 'red', 'enlace', 'comprobacion', 'comprobada', 'texto']
  const filas = visibles.value.flatMap((p) =>
    p.redes.map((r) => [
      p.codigo, p.titulo, p.estado, p.archivada ? 'sí' : 'no', p.creado, p.autor ?? '', p.aprobador ?? '', REDES[r].nombre, p.enlaces[r] ?? '',
      p.verificacion[r] ? ESTADO_ENLACE[p.verificacion[r]!.estado].texto : '', p.verificacion[r]?.fecha ?? '', textoFinal(p.textos[r] ?? '', p.hashtags),
    ]),
  )
  descargarCsv('biblioteca-posts', '﻿' + [cab, ...filas].map((f) => f.map(celda).join(',')).join('\r\n'))
}
</script>

<template>
  <section class="pila">
    <p class="chico suave">
      Todas las publicaciones, también las archivadas: nada se borra. En la ficha de cada una está su historial (quién hizo qué y el
      texto exacto que se publicó). «Comprobar» abre cada enlace como alguien sin sesión y dice si el post sigue en su red.
    </p>
    <div class="fila filtros">
      <input v-model="filtro.texto" type="search" placeholder="Buscar en título, tema o textos" aria-label="Buscar" class="crece" />
      <select v-model="filtro.estado" aria-label="Estado">
        <option value="">Todos los estados</option>
        <option value="BORRADOR">Borrador</option>
        <option value="APROBADA">Aprobada</option>
        <option value="PUBLICADA">Publicada</option>
        <option value="ARCHIVADA">Archivada</option>
      </select>
      <select v-model="filtro.red" aria-label="Red">
        <option value="">Todas las redes</option>
        <option v-for="r in ORDEN_REDES" :key="r" :value="r">{{ REDES[r].nombre }}</option>
      </select>
      <select v-model="filtro.enlace" aria-label="Comprobación">
        <option value="">Cualquier comprobación</option>
        <option value="ACTIVA">Activas</option>
        <option value="NO_DISPONIBLE">Ya no disponibles</option>
        <option value="SIN_CONFIRMAR">Sin confirmar</option>
        <option value="SIN_COMPROBAR">Sin comprobar</option>
      </select>
      <label class="chico">Desde <input v-model="filtro.desde" type="date" /></label>
      <label class="chico">Hasta <input v-model="filtro.hasta" type="date" /></label>
    </div>
    <div class="fila">
      <button class="boton boton-chico" type="button" :disabled="!!ocupado || !conEnlaces" @click="comprobarTodas">
        <Icono nombre="reintentar" /> {{ ocupado === 'todas' ? 'Comprobando…' : `Comprobar todas las publicadas (${conEnlaces})` }}
      </button>
      <button class="boton boton-chico" type="button" :disabled="!visibles.length" @click="exportar"><Icono nombre="bajar" /> CSV</button>
      <span class="chico tenue">{{ visibles.length }} de {{ lista.length }}</span>
    </div>

    <p v-if="cargando" class="cargando suave">Cargando…</p>
    <p v-else-if="!visibles.length" class="vacio">Nada con esos filtros.</p>
    <div v-else class="tabla-envoltura">
      <table class="tabla">
        <thead>
          <tr><th>Publicación</th><th>Enlaces y comprobación</th><th>Estado</th><th>Creada</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="p in visibles" :key="p.codigo" :class="{ archivada: p.archivada }">
            <td>
              <RouterLink :to="`/publicaciones/${p.codigo}`"><strong>{{ p.titulo }}</strong></RouterLink>
              <small class="tenue block">{{ p.codigo }}<template v-if="p.autor"> · {{ p.autor }}</template><template v-if="p.aprobador"> · aprobó {{ p.aprobador }}</template></small>
            </td>
            <td class="chico">
              <div v-for="r in p.redes" :key="r" class="enlace-red">
                <strong>{{ REDES[r].nombre }}</strong>
                <template v-if="p.enlaces[r]">
                  <a :href="p.enlaces[r]" target="_blank" rel="noopener noreferrer" :title="p.enlaces[r]"><Icono nombre="externo" /></a>
                  <span
                    v-if="p.verificacion[r]"
                    class="chip"
                    :class="ESTADO_ENLACE[p.verificacion[r]!.estado].chip"
                    :title="`${p.verificacion[r]!.detalle} (${fechaHora(p.verificacion[r]!.fecha)})`"
                  >{{ ESTADO_ENLACE[p.verificacion[r]!.estado].texto }}</span>
                  <span v-else class="tenue">sin comprobar</span>
                </template>
                <span v-else class="tenue">sin publicar</span>
              </div>
            </td>
            <td>
              <span v-if="p.archivada" class="chip">Archivada</span>
              <span v-else class="chip" :class="ESTADO_PUBLICACION[p.estado].chip">{{ ESTADO_PUBLICACION[p.estado].texto }}</span>
            </td>
            <td class="chico tenue">{{ fecha(p.creado) }}</td>
            <td>
              <div class="fila acciones">
                <button v-if="Object.keys(p.enlaces).length" class="boton boton-chico" type="button" :disabled="!!ocupado" @click="comprobar(p)">
                  {{ ocupado === p.codigo ? 'Comprobando…' : 'Comprobar' }}
                </button>
                <button v-if="p.archivada && auth.esAdmin" class="boton boton-chico boton-fantasma" type="button" @click="restaurar(p)">Restaurar</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.filtros {
  gap: 8px;
  flex-wrap: wrap;
}
.filtros .crece {
  min-width: 200px;
}
.enlace-red {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.enlace-red svg,
.fila svg {
  width: 14px;
  height: 14px;
  vertical-align: -2px;
}
.acciones {
  gap: 6px;
  flex-wrap: nowrap;
}
tr.archivada td {
  opacity: 0.7;
}
.block {
  display: block;
}
</style>
