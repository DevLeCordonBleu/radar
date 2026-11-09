<script setup lang="ts">
/**
 * La conexión con Google (Search Console, GA4 y Google Ads comparten un permiso). Dice si
 * sigue viva y, mientras el proyecto «Radar» de Google Cloud esté en modo Prueba, cuándo
 * vence (Google la corta cada 7 días; en producción no vence). «Conectar con Google» abre el permiso en otra
 * pestaña; la vuelta la recibe el worker y el Radar la usa sin reiniciar.
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { medicion } from '@/api/radar'
import type { ConexionGoogle } from '@/api/tipos'
import Icono from '@/components/Icono.vue'
import { fecha } from '@/composables/formato'
import { useAuth } from '@/stores/auth'
import { useAvisos } from '@/stores/avisos'

const emit = defineEmits<{ conectado: [] }>()
const auth = useAuth()
const avisos = useAvisos()
const estado = ref<ConexionGoogle | null>(null)
const esperando = ref(false)
let reloj: ReturnType<typeof setInterval> | null = null
let limite = 0

const dia = (iso: string) => fecha(`${iso}T12:00:00`)
/** Días que le quedan (0 = vence hoy); null si no se sabe. */
const quedan = computed(() => {
  const v = estado.value?.vence
  if (!v) return null
  const hoy = new Date()
  hoy.setHours(12, 0, 0, 0)
  return Math.round((new Date(`${v}T12:00:00`).getTime() - hoy.getTime()) / 86_400_000)
})
const viva = computed(() => estado.value?.valida === true)

const fallo = ref('')
async function cargar(comprobar = true) {
  try {
    estado.value = await medicion.google(comprobar)
    fallo.value = ''
  } catch (e) {
    const texto = e instanceof Error ? e.message : String(e)
    // Pantalla nueva con backend o worker viejos: la ruta todavía no existe.
    fallo.value = /not found|404/i.test(texto)
      ? 'El Radar sigue con la versión anterior: reinícialo con detener.bat e iniciar.bat para ver la conexión con Google.'
      : `No se pudo consultar la conexión con Google: ${texto}`
  }
}
onMounted(() => cargar())
onBeforeUnmount(parar)

function parar() {
  if (reloj) clearInterval(reloj)
  reloj = null
  esperando.value = false
}

async function conectar() {
  // La pestaña se abre en el clic (si no, el navegador la bloquea) y luego se le pone la dirección.
  const pestana = window.open('', '_blank')
  try {
    const { url } = await medicion.conectarGoogle()
    if (pestana) pestana.location.href = url
    else window.location.assign(url)
  } catch (e) {
    pestana?.close()
    avisos.error(e)
    return
  }
  esperando.value = true
  limite = Date.now() + 15 * 60_000
  if (reloj) clearInterval(reloj)
  reloj = setInterval(async () => {
    let e: ConexionGoogle
    try {
      e = await medicion.google(false)
    } catch {
      return
    }
    if (e.estado === 'ESPERANDO' && Date.now() < limite) return
    parar()
    if (e.estado === 'LISTA') {
      await cargar()
      if (viva.value) {
        avisos.exito(estado.value?.mensaje ?? 'Google quedó conectado.')
        emit('conectado')
      }
    } else {
      estado.value = e
      if (e.mensaje) avisos.error(new Error(e.mensaje))
    }
  }, 2000)
}
</script>

<template>
  <p v-if="fallo && !estado" class="conexion por-vencer chico" role="status"><Icono nombre="alerta" /> {{ fallo }}</p>
  <div v-else-if="estado" class="conexion chico" :class="viva ? (quedan !== null && quedan <= 1 ? 'por-vencer' : 'ok') : 'caida'" role="status">
    <Icono :nombre="viva ? 'ok' : 'alerta'" />
    <span class="texto">
      <template v-if="esperando">Da el permiso en la pestaña de Google que se abrió (con tu cuenta de Google del Radar). Esto se actualiza solo.</template>
      <template v-else-if="viva">
        Google conectado<template v-if="estado.autorizado"> desde el {{ dia(estado.autorizado) }}</template>.
        <template v-if="estado.vence && quedan !== null">
          {{ quedan <= 0 ? 'Vence hoy' : quedan === 1 ? 'Vence mañana' : `Vence el ${dia(estado.vence)}` }}: Google la corta cada 7 días
          mientras el proyecto «Radar» de Google Cloud esté en modo Prueba.
        </template>
      </template>
      <template v-else-if="!estado.configurada">Google no está conectado: Search Console y GA4 lo necesitan.</template>
      <template v-else>
        La conexión con Google venció o fue revocada<template v-if="estado.vence"> (duraba hasta el {{ dia(estado.vence) }})</template>.
        Search Console y GA4 no se actualizan hasta reconectarla.
      </template>
      <template v-if="estado.mensaje && !esperando"><br />{{ estado.mensaje }}</template>
    </span>
    <template v-if="auth.esAdmin">
      <button v-if="esperando" class="boton boton-chico" type="button" @click="parar">Cancelar</button>
      <button v-else class="boton boton-chico" :class="viva ? '' : 'boton-primario'" type="button" @click="conectar">
        <Icono nombre="reintentar" /> {{ viva ? 'Renovar' : 'Conectar con Google' }}
      </button>
    </template>
    <span v-else-if="!viva" class="tenue">Pídele a un administrador que la reconecte.</span>
  </div>
</template>

<style scoped>
.conexion {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 10px;
  padding: 8px 12px;
  border: 1px solid var(--borde);
  border-radius: 8px;
}
.conexion > svg {
  flex: none;
  width: 18px;
  height: 18px;
}
.texto {
  flex: 1 1 260px;
}
.caida {
  background: var(--rojo-fondo);
  border-color: var(--rojo);
}
.por-vencer {
  background: var(--ambar-fondo);
  border-color: var(--ambar);
}
</style>
