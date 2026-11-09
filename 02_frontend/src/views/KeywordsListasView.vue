<script setup lang="ts">
/** KeyWords Explorer · mis listas de keywords guardadas. */
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { keywords } from '@/api/radar'
import type { ListaKeywords } from '@/api/tipos'
import { mensajeDe } from '@/api/cliente'
import Icono from '@/components/Icono.vue'
import { confirmar } from '@/composables/confirmar'
import { useEstadoKeywords } from '@/composables/estadoKeywords'
import { fecha } from '@/composables/formato'
import { num } from '@/composables/keywords'
import { useAvisos } from '@/stores/avisos'

const avisos = useAvisos()
const { estado, cargar, conectado } = useEstadoKeywords()

const listas = ref<ListaKeywords[]>([])
const cargando = ref(true)
const nombre = ref('')
const pais = ref('PE')
const creando = ref(false)
const error = ref('')

async function refrescar() {
  try {
    listas.value = await keywords.listas()
  } catch (e) {
    avisos.error(e)
  } finally {
    cargando.value = false
  }
}
onMounted(async () => {
  await cargar()
  await refrescar()
})

async function crear() {
  error.value = ''
  creando.value = true
  try {
    await keywords.crearLista(nombre.value.trim(), pais.value, 'es', !conectado.value)
    nombre.value = ''
    avisos.exito('Lista creada.')
    await refrescar()
  } catch (e) {
    error.value = mensajeDe(e)
  } finally {
    creando.value = false
  }
}

async function borrar(l: ListaKeywords) {
  const r = await confirmar({ titulo: `¿Borrar la lista «${l.nombre}»?`, mensaje: `Se eliminan sus ${l.keywords} keywords y sus notas.`, aceptar: 'Borrar', tono: 'peligro' })
  if (!r.ok) return
  try {
    await keywords.borrarLista(l.codigo)
    await refrescar()
  } catch (e) {
    avisos.error(e)
  }
}
</script>

<template>
  <div class="pagina">
    <div class="pagina-cabecera">
      <div>
        <RouterLink to="/keywords" class="chico volver"><Icono nombre="volver" /> KeyWords Explorer</RouterLink>
        <h1>Mis listas de keywords</h1>
        <p>Guarda keywords con sus métricas, ponles notas, actualízalas y exporta.</p>
      </div>
    </div>

    <form class="panel fila nueva" @submit.prevent="crear">
      <div class="campo grande">
        <label for="ln">Nueva lista</label>
        <input id="ln" v-model="nombre" type="text" maxlength="80" placeholder="Ej.: Cursos de cocina 2026" required />
      </div>
      <div class="campo">
        <label for="lp">País</label>
        <select id="lp" v-model="pais"><option v-for="(n, c) in estado?.paises ?? { PE: 'Perú' }" :key="c" :value="c">{{ n }}</option></select>
      </div>
      <button class="boton boton-primario" type="submit" :disabled="creando || !nombre.trim()"><Icono nombre="mas" /> Crear</button>
    </form>
    <p v-if="error" class="aviso aviso-error" role="alert">{{ error }}</p>

    <p v-if="cargando" class="cargando suave">Cargando…</p>
    <p v-else-if="!listas.length" class="vacio">Aún no tienes listas. Crea una aquí o desde los resultados de una búsqueda.</p>
    <section class="rejilla rejilla-3 tarjetas" aria-label="Listas">
      <article v-for="l in listas" :key="l.codigo" class="panel tarjeta">
        <header>
          <RouterLink :to="`/keywords/listas/${l.codigo}`" class="nombre">{{ l.nombre }}</RouterLink>
          <span v-if="l.demo" class="chip chip-ambar">demo</span>
        </header>
        <p v-if="l.descripcion" class="suave chico">{{ l.descripcion }}</p>
        <p class="num chico"><strong>{{ num(l.keywords) }}</strong> keywords · <strong>{{ num(l.volumenTotal) }}</strong> búsquedas/mes</p>
        <p class="tenue chico">{{ estado?.paises[l.pais] ?? l.pais }} · actualizada {{ fecha(l.modificado) }}</p>
        <div class="fila">
          <RouterLink :to="`/keywords/listas/${l.codigo}`" class="boton boton-chico boton-primario">Abrir</RouterLink>
          <button class="boton boton-chico boton-fantasma" type="button" :aria-label="`Borrar ${l.nombre}`" @click="borrar(l)"><Icono nombre="basura" /></button>
        </div>
      </article>
    </section>
  </div>
</template>

<style scoped>
.volver {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 6px;
}
.volver svg {
  width: 14px;
  height: 14px;
}
.nueva {
  align-items: flex-end;
  margin-bottom: 16px;
}
.nueva .grande {
  flex: 1;
  min-width: 220px;
}
.tarjeta {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.tarjeta + .tarjeta {
  margin-top: 0;
}
.tarjeta header {
  display: flex;
  gap: 8px;
  align-items: center;
}
.nombre {
  font-weight: 700;
  font-size: 1.05rem;
}
</style>
