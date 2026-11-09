<script setup lang="ts">
/**
 * Videos cortos: idea o keyword → guion por partes de 10 s y copys (IA) → video en Google Vids
 * con tu Chrome → aprobación. Aquí: el Chrome de Vids, un video nuevo, la lista y el contexto
 * que se repite en todos (datos confirmados, protagonista, lugar, voz y pronunciaciones).
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { videos } from '@/api/radar'
import type { ContextoVideo, NavegadorVids, Video } from '@/api/tipos'
import Icono from '@/components/Icono.vue'
import { fechaHora } from '@/composables/formato'
import { useSondeo } from '@/composables/sondeo'
import { useAuth } from '@/stores/auth'
import { useAvisos } from '@/stores/avisos'
import { ESTADO_VIDEO } from '@/composables/videos'

const router = useRouter()
const auth = useAuth()
const avisos = useAvisos()

const lista = ref<Video[]>([])
const navegador = ref<NavegadorVids | null>(null)
const ctx = ref<ContextoVideo | null>(null)
const ocupado = ref(false)
const f = ref({ idea: '', keyword: '', segundos: 45, formato: 'VERTICAL' })

const clips = computed(() => Math.ceil(f.value.segundos / 10))
const DURACIONES = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]

async function cargar() {
  lista.value = await videos.listar()
}
async function revisarNavegador() {
  try {
    navegador.value = await videos.navegador()
  } catch {
    navegador.value = null
  }
}
onMounted(() => {
  cargar().catch((e) => avisos.error(e))
  revisarNavegador()
  videos.contexto().then((c) => (ctx.value = c)).catch((e) => avisos.error(e))
})
// Mientras uno se genera, la lista muestra su avance.
useSondeo(cargar, () => lista.value.some((v) => v.estado === 'GENERANDO'), 5000)

async function abrirNavegador() {
  ocupado.value = true
  try {
    navegador.value = await videos.abrirNavegador()
    avisos.exito('Chrome de Vids abierto. Si es la primera vez, inicia sesión en esa ventana.')
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

async function crear(conGuion: boolean) {
  ocupado.value = true
  try {
    const v = await videos.crear({ ...f.value, keyword: f.value.keyword.trim() || undefined })
    if (conGuion) {
      try {
        await videos.redactar(v.codigo)
      } catch (e) {
        avisos.error(e, 'El video se creó, pero la IA no pudo escribir el guion')
      }
    }
    router.push(`/videos/${v.codigo}`)
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

const agregarPronunciacion = () => ctx.value?.pronunciaciones.push({ texto: '', dice: '' })
async function guardarContexto() {
  if (!ctx.value) return
  ocupado.value = true
  try {
    ctx.value = await videos.guardarContexto(ctx.value)
    avisos.exito('Contexto de los videos guardado.')
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}
</script>

<template>
  <div class="pagina">
    <div class="pagina-cabecera">
      <div>
        <h1>Videos</h1>
        <p>De una idea o una palabra clave a un video corto con IA: guion por partes de 10 s, generación en Google Vids y aprobación.</p>
      </div>
    </div>

    <section class="panel pila navegador">
      <div class="fila entre">
        <h2><Icono nombre="videos" /> Chrome de Vids</h2>
        <span v-if="navegador" class="chip" :class="navegador.abierto ? 'chip-lima' : 'chip-ambar'">
          {{ navegador.abierto ? 'Abierto' : 'Cerrado' }}
        </span>
      </div>
      <p class="chico">
        El Radar genera los videos en Google Vids usando una ventana de Chrome propia, donde inicias sesión una sola vez. Va a
        ritmo de persona y se detiene si Google pide una verificación. Vids da unas <strong>10 generaciones al mes</strong> en
        el plan gratuito, y cada 10 s de video usan una.
      </p>
      <p v-if="navegador?.sesion === false" class="chico ambar"><Icono nombre="alerta" /> Esa ventana pide iniciar sesión.</p>
      <div class="fila">
        <button class="boton" type="button" :disabled="ocupado" @click="abrirNavegador">
          <Icono nombre="externo" /> {{ navegador?.abierto ? 'Mostrar Chrome de Vids' : 'Abrir Chrome de Vids' }}
        </button>
        <button class="boton boton-fantasma" type="button" @click="revisarNavegador"><Icono nombre="reintentar" /> Comprobar</button>
      </div>
    </section>

    <section class="panel pila">
      <h2>Nuevo video</h2>
      <div class="campo">
        <label for="v-idea">Idea</label>
        <textarea id="v-idea" v-model="f.idea" rows="2" placeholder="Por qué estudiar cocina en Lima abre puertas en todo el mundo" />
      </div>
      <div class="formulario-2">
        <div class="campo">
          <label for="v-kw">Palabra clave o pregunta de la audiencia (opcional)</label>
          <input id="v-kw" v-model="f.keyword" type="text" placeholder="cuánto gana un chef en perú" />
        </div>
        <div class="fila campos">
          <div class="campo">
            <label for="v-seg">Duración</label>
            <select id="v-seg" v-model.number="f.segundos">
              <option v-for="s in DURACIONES" :key="s" :value="s">{{ s }} s</option>
            </select>
          </div>
          <div class="campo">
            <span class="etiqueta">Formato</span>
            <div class="fila">
              <label class="casilla"><input v-model="f.formato" type="radio" value="VERTICAL" /> Vertical (Reels)</label>
              <label class="casilla"><input v-model="f.formato" type="radio" value="HORIZONTAL" /> Horizontal</label>
            </div>
          </div>
        </div>
      </div>
      <p class="chico suave">
        {{ clips }} {{ clips === 1 ? 'clip' : 'clips' }} de 10 s: el primero con «Crear» y el resto con «Extender», para que el
        personaje y la voz no cambien. Usará {{ clips }} {{ clips === 1 ? 'generación' : 'generaciones' }} de Vids.
      </p>
      <div class="fila">
        <button class="boton boton-primario" type="button" :disabled="ocupado || f.idea.trim().length < 3" @click="crear(true)">
          <Icono nombre="chispa" /> {{ ocupado ? 'Escribiendo el guion…' : 'Crear y escribir el guion con IA' }}
        </button>
        <button class="boton" type="button" :disabled="ocupado || f.idea.trim().length < 3" @click="crear(false)">Solo crear</button>
      </div>
    </section>

    <p v-if="!lista.length" class="vacio">Aún no hay videos.</p>
    <div v-else class="tabla-envoltura">
      <table class="tabla">
        <thead>
          <tr><th>Video</th><th>Estado</th><th>Duración</th><th>Modificado</th></tr>
        </thead>
        <tbody>
          <tr v-for="v in lista" :key="v.codigo">
            <td>
              <RouterLink :to="`/videos/${v.codigo}`"><strong>{{ v.titulo }}</strong></RouterLink>
              <small class="tenue block">{{ v.keyword || v.idea }}</small>
            </td>
            <td>
              <span class="chip" :class="ESTADO_VIDEO[v.estado].chip">{{ ESTADO_VIDEO[v.estado].texto }}</span>
              <small v-if="v.estado === 'GENERANDO' && v.avance" class="tenue block">{{ v.avance }}</small>
            </td>
            <td class="chico">{{ v.segundos }} s · {{ v.formato === 'VERTICAL' ? 'vertical' : 'horizontal' }}</td>
            <td class="chico tenue">{{ fechaHora(v.modificado) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <details v-if="ctx" class="panel contexto">
      <summary><strong>Contexto de todos los videos</strong> <span class="chico tenue">· datos confirmados, protagonista, lugar, voz y pronunciación</span></summary>
      <div class="pila">
        <div class="campo">
          <label for="c-datos">Datos confirmados</label>
          <textarea id="c-datos" v-model="ctx.datos" rows="7" :disabled="!auth.esAdmin" />
          <span class="campo-ayuda">Lo único que el guion puede afirmar. Lo que falte (fechas, precios, sedes) sale como «[FALTA: …]» y bloquea la generación.</span>
        </div>
        <div class="formulario-2">
          <div class="campo">
            <label for="c-pers">Protagonista</label>
            <textarea id="c-pers" v-model="ctx.personaje" rows="3" :disabled="!auth.esAdmin" />
            <span class="campo-ayuda">Se repite igual en cada clip. Una persona real solo con su autorización escrita.</span>
          </div>
          <div class="campo">
            <label for="c-lugar">Lugar y estilo</label>
            <textarea id="c-lugar" v-model="ctx.estilo" rows="3" :disabled="!auth.esAdmin" />
          </div>
        </div>
        <div class="campo">
          <label for="c-voz">Voz</label>
          <input id="c-voz" v-model="ctx.voz" type="text" :disabled="!auth.esAdmin" />
        </div>
        <div class="campo">
          <span class="etiqueta">Pronunciación</span>
          <div v-for="(p, i) in ctx.pronunciaciones" :key="i" class="fila">
            <input v-model="p.texto" type="text" placeholder="Se escribe" :aria-label="`Se escribe ${i + 1}`" :disabled="!auth.esAdmin" />
            <span class="tenue">se dice</span>
            <input v-model="p.dice" type="text" placeholder="Se pronuncia" :aria-label="`Se pronuncia ${i + 1}`" :disabled="!auth.esAdmin" />
            <button v-if="auth.esAdmin" class="boton boton-chico boton-fantasma" type="button" :aria-label="`Quitar ${p.texto}`" @click="ctx.pronunciaciones.splice(i, 1)">
              <Icono nombre="x" />
            </button>
          </div>
          <span class="campo-ayuda">Solo cambia lo que dice la voz. El guion, los subtítulos y los copys mantienen la ortografía correcta.</span>
        </div>
        <div v-if="auth.esAdmin" class="fila">
          <button class="boton boton-chico" type="button" @click="agregarPronunciacion"><Icono nombre="mas" /> Añadir pronunciación</button>
          <button class="boton boton-primario" type="button" :disabled="ocupado" @click="guardarContexto"><Icono nombre="guardar" /> Guardar contexto</button>
        </div>
        <p v-else class="chico">Solo un administrador cambia el contexto.</p>
      </div>
    </details>
  </div>
</template>

<style scoped>
.navegador h2,
.contexto summary {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.navegador h2 {
  margin: 0;
  font-size: 1.05rem;
}
.navegador svg,
.contexto svg {
  width: 15px;
  height: 15px;
}
.entre {
  justify-content: space-between;
}
.campos {
  align-items: flex-start;
  gap: 16px;
}
.ambar {
  color: var(--ambar);
}
.contexto summary {
  cursor: pointer;
}
.contexto .pila {
  margin-top: 12px;
}
</style>
