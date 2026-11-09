<script setup lang="ts">
/**
 * Un video: el guion por partes (una por clip de 10 s), los copys de Facebook e Instagram,
 * la generación en Google Vids (con su avance) y la aprobación. Un diálogo con «[FALTA: …]»
 * no se genera: gastaría generaciones en algo que no se puede publicar.
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { publicaciones, videos } from '@/api/radar'
import type { FormatoVideo, ParteVideo, Video } from '@/api/tipos'
import Icono from '@/components/Icono.vue'
import { confirmar } from '@/composables/confirmar'
import { fechaHora } from '@/composables/formato'
import { useSondeo } from '@/composables/sondeo'
import { ESTADO_VIDEO, MAX_PALABRAS_CLIP, faltas, palabras } from '@/composables/videos'
import { useAuth } from '@/stores/auth'
import { useAvisos } from '@/stores/avisos'

const route = useRoute()
const router = useRouter()
const auth = useAuth()
const avisos = useAvisos()
const codigo = computed(() => String(route.params.codigo))

const v = ref<Video | null>(null)
const f = ref({ titulo: '', segundos: 45, formato: 'VERTICAL' as FormatoVideo, partes: [] as ParteVideo[], copyFacebook: '', copyInstagram: '', hashtags: '' })
const original = ref('')
const prompts = ref<string[] | null>(null)
const ocupado = ref(false)
const version = ref(0)

function rellenar(x: Video) {
  v.value = x
  f.value = {
    titulo: x.titulo, segundos: x.segundos, formato: x.formato, partes: x.partes.map((p) => ({ ...p })),
    copyFacebook: x.copyFacebook ?? '', copyInstagram: x.copyInstagram ?? '', hashtags: x.hashtags.join(' '),
  }
  original.value = JSON.stringify(f.value)
  prompts.value = null
}
async function cargar() {
  const x = await videos.obtener(codigo.value)
  const antes = v.value?.estado
  if (antes === 'GENERANDO' && x.estado !== 'GENERANDO') {
    rellenar(x)
    version.value++
    if (x.estado === 'GENERADO') avisos.exito('Video listo: revísalo con sonido antes de aprobarlo.')
    else if (x.error) avisos.error(x.error)
  } else if (!cambiado.value) rellenar(x)
  else v.value = x
}
onMounted(() => cargar().catch((e) => avisos.error(e)))
useSondeo(cargar, () => v.value?.estado === 'GENERANDO', 4000)

const cambiado = computed(() => !!v.value && JSON.stringify(f.value) !== original.value)
const generando = computed(() => v.value?.estado === 'GENERANDO')
const clips = computed(() => Math.ceil(f.value.segundos / 10))
const pendientes = computed(() => [...new Set(f.value.partes.flatMap((p) => faltas(p.dialogo)))])
const desajuste = computed(() => f.value.partes.length > 0 && f.value.partes.length !== clips.value)
const DURACIONES = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]
const tramo = (i: number) => `${i * 10}–${Math.min((i + 1) * 10, f.value.segundos)} s`

async function guardar(silencioso = false) {
  if (!v.value) return
  ocupado.value = true
  try {
    rellenar(await videos.guardar(codigo.value, {
      titulo: f.value.titulo, segundos: f.value.segundos, formato: f.value.formato, partes: f.value.partes,
      copyFacebook: f.value.copyFacebook, copyInstagram: f.value.copyInstagram,
      hashtags: f.value.hashtags.split(/[\s,]+/).filter(Boolean),
    }))
    if (!silencioso) avisos.exito('Cambios guardados.')
    return true
  } catch (e) {
    avisos.error(e)
    return false
  } finally {
    ocupado.value = false
  }
}

async function redactar() {
  if (v.value?.partes.length) {
    const r = await confirmar({
      titulo: '¿Volver a escribir el guion?',
      mensaje: 'La IA reemplaza las partes y los copys actuales. Lo que editaste a mano se pierde.',
      aceptar: 'Volver a escribir',
      tono: 'peligro',
    })
    if (!r.ok) return
  }
  if (cambiado.value && !(await guardar(true))) return
  ocupado.value = true
  try {
    rellenar(await videos.redactar(codigo.value))
    avisos.exito('Guion escrito. Revísalo y ajústalo antes de generar.')
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

const agregarParte = () => f.value.partes.push({ dialogo: '', escena: '' })
const quitarParte = (i: number) => f.value.partes.splice(i, 1)

async function verPrompts() {
  if (cambiado.value && !(await guardar(true))) return
  try {
    prompts.value = (await videos.prompts(codigo.value)).prompts
  } catch (e) {
    avisos.error(e)
  }
}

async function generar() {
  if (cambiado.value && !(await guardar(true))) return
  const n = clips.value
  const r = await confirmar({
    titulo: `¿Generar el video en Vids (${n} ${n === 1 ? 'generación' : 'generaciones'})?`,
    mensaje: `El robot abre Vids en tu Chrome y genera ${n} ${n === 1 ? 'clip' : 'clips'} de 10 s: el primero con «Crear» y el resto con «Extender».`,
    puntos: [
      'El Chrome de Vids tiene que estar abierto y con tu sesión iniciada.',
      `Tarda unos ${Math.max(1, n * 2)} minutos. No uses esa ventana mientras tanto.`,
      'Si Google pide una verificación, se detiene y te avisa.',
    ],
    aceptar: 'Generar',
  })
  if (!r.ok) return
  ocupado.value = true
  try {
    v.value = await videos.generar(codigo.value)
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

async function cancelar() {
  try {
    rellenar(await videos.cancelar(codigo.value))
  } catch (e) {
    avisos.error(e)
  }
}

async function aprobar(si: boolean) {
  try {
    rellenar(await videos.aprobar(codigo.value, si))
    avisos.exito(si ? 'Video aprobado.' : 'Aprobación retirada.')
  } catch (e) {
    avisos.error(e)
  }
}

/** Lleva el video aprobado a Publicaciones (si ya tiene una, abre esa). */
async function publicar() {
  if (cambiado.value && !(await guardar(true))) return
  ocupado.value = true
  try {
    const pub = await publicaciones.desdeVideo(codigo.value)
    router.push(`/publicaciones/${pub.codigo}`)
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

async function borrar() {
  const r = await confirmar({ titulo: '¿Borrar el video?', mensaje: 'Se borran el guion y el archivo del Radar. Lo generado sigue en tu Vids.', aceptar: 'Borrar', tono: 'peligro' })
  if (!r.ok) return
  try {
    await videos.borrar(codigo.value)
    original.value = JSON.stringify(f.value)
    router.push('/videos')
  } catch (e) {
    avisos.error(e)
  }
}

async function copiar(texto: string, que: string) {
  try {
    await navigator.clipboard.writeText(texto)
    avisos.exito(`${que} copiado.`)
  } catch {
    avisos.error('No se pudo copiar: selecciona el texto y cópialo a mano.')
  }
}
const conHashtags = (t: string) => [t.trim(), f.value.hashtags.trim()].filter(Boolean).join('\n\n')
</script>

<template>
  <div v-if="v" class="pagina estrecha">
    <RouterLink to="/videos" class="volver chico"><Icono nombre="volver" /> Videos</RouterLink>
    <div class="pagina-cabecera">
      <div class="titulo">
        <input v-model="f.titulo" class="input-titulo" type="text" aria-label="Título del video" :disabled="generando" />
        <p class="chico suave">
          <span class="chip" :class="ESTADO_VIDEO[v.estado].chip">{{ ESTADO_VIDEO[v.estado].texto }}</span>
          {{ v.codigo }} · {{ v.idea }}<template v-if="v.keyword"> · «{{ v.keyword }}»</template> · {{ fechaHora(v.modificado) }}
        </p>
      </div>
    </div>

    <div v-if="v.error && !generando" class="aviso aviso-ambar" role="status">
      <Icono nombre="alerta" />
      <div class="aviso-cuerpo">{{ v.error }}</div>
    </div>

    <!-- Video -->
    <section v-if="generando" class="panel pila generando" aria-live="polite">
      <h2><Icono nombre="videos" /> Generando en Vids…</h2>
      <p>{{ v.avance || 'Abriendo Vids…' }}</p>
      <p class="chico tenue">No uses la ventana de Chrome de Vids mientras tanto. Puedes salir de esta página: sigue en segundo plano.</p>
      <div class="fila"><button class="boton" type="button" @click="cancelar">Cancelar</button></div>
    </section>
    <section v-else-if="v.tieneArchivo" class="panel pila">
      <h2><Icono nombre="videos" /> Video</h2>
      <div class="reproductor" :class="v.formato === 'VERTICAL' ? 'vertical' : 'horizontal'">
        <video :key="version" :src="`${videos.archivo(v.codigo)}?v=${v.modificado}`" controls preload="metadata" />
      </div>
      <p class="chico tenue">
        {{ v.segundosReales ? `${v.segundosReales.toFixed(1)} s` : '' }} · Revísalo con sonido: voz, pronunciación, personaje y que no
        aparezcan textos ni logos inventados.
      </p>
      <div class="fila">
        <a class="boton" :href="videos.archivo(v.codigo, true)"><Icono nombre="bajar" /> Descargar MP4</a>
        <a v-if="v.vidsUrl" class="boton boton-fantasma" :href="v.vidsUrl" target="_blank" rel="noopener noreferrer"><Icono nombre="externo" /> Abrir en Vids</a>
        <template v-if="auth.esAdmin">
          <button v-if="v.estado === 'GENERADO'" class="boton boton-primario" type="button" @click="aprobar(true)"><Icono nombre="aprobar" /> Aprobar</button>
          <button v-if="v.estado === 'APROBADO'" class="boton boton-fantasma" type="button" @click="aprobar(false)">Quitar aprobación</button>
        </template>
        <button v-if="v.estado === 'APROBADO'" class="boton boton-primario" type="button" :disabled="ocupado" @click="publicar">
          <Icono nombre="compartir" /> Crear publicación
        </button>
      </div>
    </section>

    <!-- Guion -->
    <section class="panel pila">
      <div class="fila entre">
        <h2>Guion</h2>
        <button class="boton boton-chico" type="button" :disabled="ocupado || generando" @click="redactar">
          <Icono nombre="chispa" /> {{ v.partes.length ? 'Volver a escribir con IA' : 'Escribir con IA' }}
        </button>
      </div>
      <div class="fila campos">
        <div class="campo">
          <label for="d-seg">Duración</label>
          <select id="d-seg" v-model.number="f.segundos" :disabled="generando">
            <option v-for="s in DURACIONES" :key="s" :value="s">{{ s }} s</option>
          </select>
        </div>
        <div class="campo">
          <label for="d-formato">Formato</label>
          <select id="d-formato" v-model="f.formato" :disabled="generando">
            <option value="VERTICAL">Vertical (Reels)</option>
            <option value="HORIZONTAL">Horizontal</option>
          </select>
        </div>
      </div>
      <p v-if="desajuste" class="chico ambar">
        <Icono nombre="alerta" /> {{ f.segundos }} s son {{ clips }} {{ clips === 1 ? 'parte' : 'partes' }} y el guion tiene {{ f.partes.length }}:
        ajusta las partes o vuelve a escribirlo.
      </p>
      <p v-if="!f.partes.length" class="chico">Aún no hay guion. Pulsa «Escribir con IA» o añade las partes a mano.</p>

      <ol class="partes">
        <li v-for="(p, i) in f.partes" :key="i" class="parte">
          <div class="fila entre">
            <strong>Parte {{ i + 1 }} <span class="tenue chico">· {{ tramo(i) }} · {{ i === 0 ? 'Crear' : 'Extender' }}</span></strong>
            <button class="boton boton-chico boton-fantasma" type="button" :disabled="generando" :aria-label="`Quitar la parte ${i + 1}`" @click="quitarParte(i)">
              <Icono nombre="x" />
            </button>
          </div>
          <label class="oculto-visual" :for="`dialogo-${i}`">Diálogo de la parte {{ i + 1 }}</label>
          <textarea :id="`dialogo-${i}`" v-model="p.dialogo" rows="2" :disabled="generando" placeholder="Lo que dice el protagonista" />
          <small :class="palabras(p.dialogo) > MAX_PALABRAS_CLIP ? 'ambar' : 'tenue'">
            {{ palabras(p.dialogo) }} palabras<template v-if="palabras(p.dialogo) > MAX_PALABRAS_CLIP"> · más de {{ MAX_PALABRAS_CLIP }}: puede no caber en 10 s</template>
          </small>
          <label class="oculto-visual" :for="`escena-${i}`">Escena de la parte {{ i + 1 }}</label>
          <input :id="`escena-${i}`" v-model="p.escena" type="text" :disabled="generando" placeholder="Qué se ve: gesto, acción o encuadre" />
        </li>
      </ol>
      <div class="fila">
        <button class="boton boton-chico" type="button" :disabled="generando || f.partes.length >= 6" @click="agregarParte"><Icono nombre="mas" /> Añadir parte</button>
      </div>
      <p v-if="pendientes.length" class="chico ambar">
        <Icono nombre="alerta" /> Falta: {{ pendientes.join(', ') }}. Complétalo (o añádelo a los datos confirmados) antes de generar.
      </p>

      <details class="chico" @toggle="($event.target as HTMLDetailsElement).open && !prompts && verPrompts()">
        <summary>Ver lo que se escribirá en Vids</summary>
        <ol v-if="prompts" class="prompts">
          <li v-for="(p, i) in prompts" :key="i"><span class="mono">{{ p }}</span></li>
        </ol>
      </details>
    </section>

    <!-- Copys -->
    <section class="panel pila">
      <h2>Publicación</h2>
      <div class="campo">
        <div class="fila entre">
          <label for="copy-fb">Copy de Facebook</label>
          <button class="boton boton-chico boton-fantasma" type="button" @click="copiar(conHashtags(f.copyFacebook), 'Copy de Facebook')"><Icono nombre="copiar" /> Copiar</button>
        </div>
        <textarea id="copy-fb" v-model="f.copyFacebook" rows="4" />
      </div>
      <div class="campo">
        <div class="fila entre">
          <label for="copy-ig">Copy de Instagram</label>
          <button class="boton boton-chico boton-fantasma" type="button" @click="copiar(conHashtags(f.copyInstagram), 'Copy de Instagram')"><Icono nombre="copiar" /> Copiar</button>
        </div>
        <textarea id="copy-ig" v-model="f.copyInstagram" rows="4" />
      </div>
      <div class="campo">
        <label for="hashtags">Hashtags</label>
        <input id="hashtags" v-model="f.hashtags" type="text" placeholder="#LeCordonBleuPeru #Gastronomia" />
      </div>
      <p class="chico tenue">Aprobado el video, «Crear publicación» lo lleva a Publicaciones con estos textos, para añadir LinkedIn y publicarlo.</p>
    </section>

    <div class="fila acciones">
      <button class="boton boton-primario" type="button" :disabled="ocupado || generando || !cambiado" @click="guardar()"><Icono nombre="guardar" /> Guardar cambios</button>
      <button
        class="boton boton-primario"
        type="button"
        :disabled="ocupado || generando || !f.partes.length || pendientes.length > 0 || desajuste"
        @click="generar"
      >
        <Icono nombre="videos" /> {{ v.tieneArchivo ? 'Volver a generar en Vids' : 'Generar en Vids' }}
      </button>
      <span v-if="cambiado" class="chico tenue">Cambios sin guardar</span>
      <button v-if="auth.esAdmin" class="boton boton-fantasma derecha" type="button" :disabled="generando" @click="borrar"><Icono nombre="basura" /> Borrar</button>
    </div>
  </div>
</template>

<style scoped>
.estrecha {
  max-width: 900px;
}
.volver {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 8px;
}
svg {
  width: 15px;
  height: 15px;
  vertical-align: -2px;
}
h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 1.05rem;
}
.titulo {
  flex: 1;
  min-width: 0;
}
.input-titulo {
  width: 100%;
  font-size: 1.4rem;
  font-weight: 600;
  border-color: transparent;
  background: transparent;
  padding: 2px 4px;
}
.input-titulo:hover:not(:disabled),
.input-titulo:focus {
  border-color: var(--borde);
}
.entre {
  justify-content: space-between;
}
.campos {
  gap: 16px;
}
.partes {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 12px;
}
.parte {
  display: grid;
  gap: 6px;
  padding: 12px;
  border: 1px solid var(--borde);
  border-radius: 8px;
}
.prompts {
  display: grid;
  gap: 8px;
  margin-top: 8px;
}
.prompts .mono {
  white-space: pre-wrap;
  word-break: break-word;
}
.reproductor video {
  display: block;
  max-width: 100%;
  border-radius: 8px;
  background: #000;
}
.reproductor.vertical video {
  max-height: 560px;
  margin: 0 auto;
}
.acciones {
  margin-top: 8px;
}
.derecha {
  margin-left: auto;
}
.ambar {
  color: var(--ambar);
}
.generando {
  background: var(--panel-2);
}
</style>
