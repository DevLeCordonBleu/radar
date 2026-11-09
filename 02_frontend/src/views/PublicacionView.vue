<script setup lang="ts">
/**
 * Una publicación, en el orden del flujo: texto (uno por red o el mismo para todas) → flyer
 * (fondo de foto gratuita, IA o propia; el Radar pone título, detalle, llamada a la acción y
 * logo) → hashtags → vista previa → aprobación → publicar.
 *
 * Publicar aún es a mano (copiar, bajar, pegar el enlace): el envío automático por n8n llegará
 * después. Publicada en alguna red ya no se edita: lo publicado y lo guardado no deben diferir.
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { publicaciones, seo } from '@/api/radar'
import type { BusquedaFotos, EventoPublicacion, FuentesImagen, ModoCopy, Publicacion, RedSocial } from '@/api/tipos'
import Icono from '@/components/Icono.vue'
import { confirmar } from '@/composables/confirmar'
import { fechaHora } from '@/composables/formato'
import { ESTADO_ENLACE, ESTADO_PUBLICACION, ORDEN_REDES, REDES, leerHashtags, textoFinal } from '@/composables/publicaciones'
import { utmEnTexto } from '@/composables/utm'
import { faltas } from '@/composables/videos'
import { useAuth } from '@/stores/auth'
import { useAvisos } from '@/stores/avisos'

const route = useRoute()
const router = useRouter()
const auth = useAuth()
const avisos = useAvisos()
const codigo = computed(() => String(route.params.codigo))

const p = ref<Publicacion | null>(null)
const f = ref({
  titulo: '', idea: '', redes: [] as RedSocial[], modoCopy: 'POR_RED' as ModoCopy, comun: '',
  textos: { FACEBOOK: '', INSTAGRAM: '', LINKEDIN: '' } as Record<RedSocial, string>, hashtags: '',
  flyer: { titulo: '', detalle: '', cta: '', busqueda: '', descripcion: '' },
})
const original = ref('')
const ocupado = ref(false)
const subiendo = ref<number | null>(null)
const enlaces = ref<Record<RedSocial, string>>({ FACEBOOK: '', INSTAGRAM: '', LINKEDIN: '' })
const proporcion = ref<number | null>(null)
const pestana = ref<'foto' | 'ia' | 'propia'>('foto')
const consulta = ref('')
const fotos = ref<BusquedaFotos | null>(null)
const fuentes = ref<FuentesImagen | null>(null)
const vista = ref<RedSocial>('FACEBOOK')
const historial = ref<EventoPublicacion[] | null>(null)
const comprobando = ref(false)

function rellenar(x: Publicacion) {
  p.value = x
  const textos = { FACEBOOK: x.textos.FACEBOOK ?? '', INSTAGRAM: x.textos.INSTAGRAM ?? '', LINKEDIN: x.textos.LINKEDIN ?? '' }
  f.value = {
    titulo: x.titulo, idea: x.idea, redes: [...x.redes], modoCopy: x.modoCopy, textos,
    comun: x.redes.map((r) => textos[r]).find(Boolean) ?? '',
    hashtags: x.hashtags.join(' '),
    flyer: { titulo: x.flyer.titulo, detalle: x.flyer.detalle, cta: x.flyer.cta, busqueda: x.flyer.busqueda, descripcion: x.flyer.descripcion },
  }
  original.value = JSON.stringify(f.value)
  if (!consulta.value) consulta.value = x.flyer.busqueda
  // El historial abierto se pone al día con cada cambio.
  if (historial.value) cargarHistorial()
  if (!x.redes.includes(vista.value) && x.redes.length) vista.value = x.redes[0]
}
onMounted(() => {
  publicaciones.obtener(codigo.value).then(rellenar).catch((e) => avisos.error(e))
  seo.fuentesImagen().then((x) => (fuentes.value = x)).catch(() => {})
  publicaciones.marca().then((m) => (dominios.value = m.dominios ?? [])).catch(() => {})
})

const cambiado = computed(() => !!p.value && JSON.stringify(f.value) !== original.value)
const flyerCambiado = computed(() => !!p.value && JSON.stringify(f.value.flyer) !== JSON.stringify(JSON.parse(original.value || '{}').flyer))
const bloqueada = computed(() => !!p.value && (Object.keys(p.value.enlaces).length > 0 || p.value.archivada))
const hashtags = computed(() => leerHashtags(f.value.hashtags))
const redes = computed(() => ORDEN_REDES.filter((r) => f.value.redes.includes(r)))
const mismo = computed(() => f.value.modoCopy === 'MISMO')
/** El texto que irá en cada red, según el modo. */
const texto = (r: RedSocial) => (mismo.value ? f.value.comun : f.value.textos[r])
/** Lo que se pega en la red: texto, hashtags y UTM en los enlaces a la web propia (como el backend). */
const dominios = ref<string[]>([])
const final = (r: RedSocial) => (p.value ? utmEnTexto(textoFinal(texto(r), hashtags.value), r, p.value.codigo, f.value.titulo, dominios.value) : '')
const largo = (r: RedSocial) => final(r).length
const nombresRedes = computed(() => redes.value.map((r) => REDES[r].nombre).join(', '))
const limiteComun = computed(() => Math.min(...redes.value.map((r) => REDES[r].limite), 5000))
const archivoUrl = computed(() => (p.value ? `${publicaciones.archivo(p.value.codigo)}?v=${p.value.modificado}` : ''))

/** Lo mismo que revisa el backend al aprobar, para avisar antes. */
const problemas = computed(() => {
  const salida: string[] = []
  if (!redes.value.length) salida.push('Elige al menos una red.')
  for (const r of redes.value) {
    if (!texto(r).trim()) salida.push(`Falta el texto de ${REDES[r].nombre}.`)
    else if (largo(r) > REDES[r].limite) salida.push(`El texto de ${REDES[r].nombre} con sus hashtags pasa de ${REDES[r].limite} caracteres.`)
  }
  if (redes.value.includes('INSTAGRAM') && p.value?.media === 'NINGUNA') salida.push('Instagram necesita una imagen o un video.')
  const revisar = [...redes.value.map(texto), ...(p.value?.flyer.enUso ? [f.value.flyer.titulo, f.value.flyer.detalle, f.value.flyer.cta] : [])]
  const pendientes = [...new Set(revisar.flatMap(faltas))]
  if (pendientes.length) salida.push(`Hay datos por completar: ${pendientes.join(', ')}.`)
  return salida
})
const fueraDeInstagram = computed(
  () => p.value?.media === 'IMAGEN' && !p.value.flyer.enUso && redes.value.includes('INSTAGRAM') && proporcion.value !== null && (proporcion.value < 0.8 || proporcion.value > 1.91),
)

async function guardar(silencioso = false) {
  if (!p.value) return false
  ocupado.value = true
  try {
    const textos = { ...f.value.textos }
    if (mismo.value) for (const r of redes.value) textos[r] = f.value.comun
    rellenar(await publicaciones.guardar(codigo.value, {
      titulo: f.value.titulo, idea: f.value.idea, redes: f.value.redes, modoCopy: f.value.modoCopy, textos, hashtags: hashtags.value,
      flyer: f.value.flyer,
    }))
    if (!silencioso) avisos.exito(p.value?.flyer.enUso && flyerCambiado.value ? 'Cambios guardados y flyer actualizado.' : 'Cambios guardados.')
    return true
  } catch (e) {
    avisos.error(e)
    return false
  } finally {
    ocupado.value = false
  }
}

async function redactar() {
  if (redes.value.some((r) => p.value?.textos[r])) {
    const r = await confirmar({
      titulo: '¿Volver a escribir los textos?',
      mensaje: 'La IA reemplaza los textos de las redes, los hashtags y los textos del flyer. Lo que editaste a mano se pierde.',
      aceptar: 'Volver a escribir',
      tono: 'peligro',
    })
    if (!r.ok) return
  }
  if (cambiado.value && !(await guardar(true))) return
  ocupado.value = true
  try {
    rellenar(await publicaciones.redactar(codigo.value))
    consulta.value = p.value?.flyer.busqueda ?? consulta.value
    avisos.exito('Textos escritos. Revísalos antes de aprobar.')
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

/** Antes de cambiar la imagen: guarda lo pendiente y, si había un video, pregunta. */
async function prepararFondo() {
  if (p.value?.media === 'VIDEO') {
    const r = await confirmar({
      titulo: '¿Cambiar el video por un flyer?',
      mensaje: 'La publicación lleva un video. El flyer lo reemplaza (el video sigue en el módulo Videos).',
      aceptar: 'Usar flyer',
    })
    if (!r.ok) return false
  }
  return !cambiado.value || (await guardar(true))
}

async function buscarFotos(pagina = 1) {
  if (consulta.value.trim().length < 2) return
  ocupado.value = true
  try {
    fotos.value = await publicaciones.fotos(consulta.value.trim(), pagina)
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

async function con(accion: () => Promise<Publicacion>, exito: string) {
  if (!(await prepararFondo())) return
  ocupado.value = true
  try {
    rellenar(await accion())
    avisos.exito(p.value?.flyer.enUso ? exito : 'Fondo guardado. Escribe el título del flyer para armarlo.')
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}
const elegirFoto = (id: number) => con(() => publicaciones.fondoFoto(codigo.value, id), 'Flyer armado con la foto.')

async function crearConIa() {
  const precio = fuentes.value?.precio_usd
  const r = await confirmar({
    titulo: '¿Crear el fondo con IA?',
    mensaje: `Gemini crea una imagen a medida${precio ? ` (unos US$ ${precio.toFixed(2)})` : ''}. Necesita la facturación activada en el proyecto de Google de tu clave.`,
    aceptar: 'Crear fondo',
  })
  if (!r.ok) return
  await con(() => publicaciones.fondoIa(codigo.value, f.value.flyer.descripcion), 'Flyer armado con el fondo creado con IA.')
}

async function fondoPropio(ev: Event) {
  const entrada = ev.target as HTMLInputElement
  const archivo = entrada.files?.[0]
  entrada.value = ''
  if (archivo) await con(() => publicaciones.fondoPropio(codigo.value, archivo), 'Flyer armado con tu foto.')
}

const armar = () => con(() => publicaciones.componer(codigo.value), 'Flyer armado.')

async function subir(ev: Event) {
  const entrada = ev.target as HTMLInputElement
  const archivo = entrada.files?.[0]
  entrada.value = ''
  if (!archivo) return
  if (cambiado.value && !(await guardar(true))) return
  subiendo.value = 0
  try {
    const x = await publicaciones.subir(codigo.value, archivo, (fr) => (subiendo.value = fr))
    proporcion.value = null
    rellenar(x)
    avisos.exito(x.media === 'VIDEO' ? 'Video subido.' : 'Imagen subida.')
  } catch (e) {
    avisos.error(e)
  } finally {
    subiendo.value = null
  }
}

async function quitarArchivo() {
  try {
    rellenar(await publicaciones.quitarArchivo(codigo.value))
  } catch (e) {
    avisos.error(e)
  }
}

async function aprobar(si: boolean) {
  if (cambiado.value && !(await guardar(true))) return
  try {
    rellenar(await publicaciones.aprobar(codigo.value, si))
    avisos.exito(si ? 'Publicación aprobada: ya se puede publicar.' : 'Aprobación retirada.')
  } catch (e) {
    avisos.error(e)
  }
}

async function registrar(r: RedSocial, url: string) {
  try {
    rellenar(await publicaciones.enlace(codigo.value, r, url))
    enlaces.value[r] = ''
    if (url) avisos.exito(`Enlace de ${REDES[r].nombre} guardado.`)
  } catch (e) {
    avisos.error(e)
  }
}

async function archivar() {
  const r = await confirmar({
    titulo: '¿Archivar la publicación?',
    mensaje: 'Sale de la lista «En curso», pero sigue en la Biblioteca con sus textos, su flyer y su historial. Se puede restaurar.',
    puntos: Object.keys(p.value?.enlaces ?? {}).length ? ['Lo ya publicado sigue en las redes: bórralo allí si hace falta.'] : [],
    aceptar: 'Archivar',
  })
  if (!r.ok) return
  try {
    await publicaciones.archivar(codigo.value)
    original.value = JSON.stringify(f.value)
    router.push('/publicaciones')
  } catch (e) {
    avisos.error(e)
  }
}

async function restaurar() {
  try {
    rellenar(await publicaciones.restaurar(codigo.value))
    avisos.exito('Vuelve a la lista.')
  } catch (e) {
    avisos.error(e)
  }
}

async function cargarHistorial() {
  try {
    historial.value = await publicaciones.historial(codigo.value)
  } catch (e) {
    avisos.error(e)
  }
}

async function comprobar() {
  comprobando.value = true
  try {
    rellenar(await publicaciones.verificar(codigo.value))
    avisos.exito('Enlaces comprobados.')
  } catch (e) {
    avisos.error(e)
  } finally {
    comprobando.value = false
  }
}

async function copiar(r: RedSocial) {
  try {
    await navigator.clipboard.writeText(final(r))
    avisos.exito(`Texto de ${REDES[r].nombre} copiado, con los hashtags.`)
  } catch {
    avisos.error('No se pudo copiar: selecciona el texto y cópialo a mano.')
  }
}

function cambiarModo(m: ModoCopy) {
  // Al pasar a «el mismo», parte del primer texto que haya; al volver, cada red conserva el común.
  if (m === 'MISMO') f.value.comun = f.value.comun || redes.value.map((r) => f.value.textos[r]).find(Boolean) || ''
  else for (const r of redes.value) f.value.textos[r] = f.value.textos[r] || f.value.comun
  f.value.modoCopy = m
}

function medirImagen(ev: Event) {
  const img = ev.target as HTMLImageElement
  proporcion.value = img.naturalHeight ? img.naturalWidth / img.naturalHeight : null
}
</script>

<template>
  <div v-if="p" class="pagina estrecha">
    <RouterLink to="/publicaciones" class="volver chico"><Icono nombre="volver" /> Publicaciones</RouterLink>
    <div class="pagina-cabecera">
      <div class="titulo">
        <input v-model="f.titulo" class="input-titulo" type="text" aria-label="Título de la publicación" :disabled="bloqueada" />
        <p class="chico suave">
          <span class="chip" :class="ESTADO_PUBLICACION[p.estado].chip">{{ ESTADO_PUBLICACION[p.estado].texto }}</span>
          {{ p.codigo }}<template v-if="p.codOrigen"> · del video <RouterLink :to="`/videos/${p.codOrigen}`">{{ p.codOrigen }}</RouterLink></template>
          · {{ fechaHora(p.modificado) }}
        </p>
      </div>
    </div>

    <ol class="pasos chico" aria-label="Pasos">
      <li :class="{ hecho: redes.some((r) => texto(r)) }">1 · Texto</li>
      <li :class="{ hecho: p.media !== 'NINGUNA' }">2 · Flyer</li>
      <li :class="{ hecho: hashtags.length > 0 }">3 · Hashtags</li>
      <li :class="{ hecho: p.estado !== 'BORRADOR' }">4 · Aprobación</li>
      <li :class="{ hecho: p.estado === 'PUBLICADA' }">5 · Publicación</li>
    </ol>

    <div v-if="p.archivada" class="aviso aviso-ambar" role="status">
      <Icono nombre="alerta" />
      <div class="aviso-cuerpo">
        Archivada: está en la Biblioteca y no se edita.
        <button v-if="auth.esAdmin" class="boton boton-chico" type="button" @click="restaurar">Restaurar</button>
      </div>
    </div>
    <div v-else-if="bloqueada" class="aviso aviso-ambar" role="status">
      <Icono nombre="alerta" />
      <div class="aviso-cuerpo">Ya se publicó en alguna red: no se edita. Si hay que cambiar algo, crea otra publicación.</div>
    </div>

    <!-- 5 · Publicar -->
    <section v-if="p.estado !== 'BORRADOR'" class="panel pila publicar">
      <div class="fila entre">
        <h2><Icono nombre="compartir" /> Publicar</h2>
        <button v-if="Object.keys(p.enlaces).length" class="boton boton-chico" type="button" :disabled="comprobando" @click="comprobar">
          <Icono nombre="reintentar" /> {{ comprobando ? 'Comprobando…' : 'Comprobar si sigue activa' }}
        </button>
      </div>
      <div class="aviso aviso-info">
        <Icono nombre="info" />
        <div class="aviso-cuerpo chico">
          <strong>La publicación automática aún no está conectada.</strong> Cuando conectemos n8n con tu página de Facebook, tu
          Instagram y LinkedIn, aquí habrá un solo botón «Publicar ahora». Mientras tanto, en cada red: copia el texto, baja el
          flyer, publícalo y pega el enlace para que quede registrado. Los enlaces a la web propia ya llevan UTM (Facebook y LinkedIn) para
          medir las visitas en GA4.
        </div>
      </div>
      <div v-for="r in p.redes" :key="r" class="red-fila">
        <div class="fila entre">
          <strong>{{ REDES[r].nombre }}</strong>
          <span v-if="p.enlaces[r]" class="chip chip-lima"><Icono nombre="ok" /> Publicada</span>
          <span v-else class="chip chip-ambar">Pendiente</span>
        </div>
        <p v-if="p.enlaces[r] && p.verificacion[r]" class="chico">
          <span class="chip" :class="ESTADO_ENLACE[p.verificacion[r]!.estado].chip">{{ ESTADO_ENLACE[p.verificacion[r]!.estado].texto }}</span>
          {{ p.verificacion[r]!.detalle }} <span class="tenue">· {{ fechaHora(p.verificacion[r]!.fecha) }}</span>
        </p>
        <template v-if="p.enlaces[r]">
          <div class="fila">
            <a class="chico enlace" :href="p.enlaces[r]" target="_blank" rel="noopener noreferrer"><Icono nombre="externo" /> {{ p.enlaces[r] }}</a>
            <button class="boton boton-chico boton-fantasma" type="button" @click="registrar(r, '')">Quitar enlace</button>
          </div>
        </template>
        <template v-else>
          <div class="fila">
            <button class="boton boton-chico" type="button" @click="copiar(r)"><Icono nombre="copiar" /> Copiar texto</button>
            <a v-if="p.media !== 'NINGUNA'" class="boton boton-chico" :href="publicaciones.archivo(p.codigo, true)">
              <Icono nombre="bajar" /> {{ p.media === 'VIDEO' ? 'Bajar video' : p.flyer.enUso ? 'Bajar flyer' : 'Bajar imagen' }}
            </a>
            <a class="boton boton-chico boton-fantasma" :href="REDES[r].publicar" target="_blank" rel="noopener noreferrer">
              <Icono nombre="externo" /> Abrir {{ REDES[r].nombre }}
            </a>
          </div>
          <form class="fila" @submit.prevent="registrar(r, enlaces[r])">
            <label class="oculto-visual" :for="`enlace-${r}`">Enlace de la publicación en {{ REDES[r].nombre }}</label>
            <input :id="`enlace-${r}`" v-model="enlaces[r]" class="crece" type="url" :placeholder="`Pega el enlace de la publicación en ${REDES[r].nombre}`" />
            <button class="boton boton-chico boton-primario" type="submit" :disabled="!enlaces[r].trim()">Registrar</button>
          </form>
        </template>
      </div>
    </section>

    <!-- 1 · Texto -->
    <section class="panel pila">
      <div class="fila entre">
        <h2>1 · Texto</h2>
        <button class="boton boton-chico" type="button" :disabled="ocupado || bloqueada || !redes.length" @click="redactar">
          <Icono nombre="chispa" /> {{ redes.some((r) => p?.textos[r]) ? 'Volver a escribir con IA' : 'Escribir con IA' }}
        </button>
      </div>
      <div class="campo">
        <label for="p-idea">Tema</label>
        <textarea id="p-idea" v-model="f.idea" rows="2" :disabled="bloqueada" />
        <span class="campo-ayuda">Lo que la IA usa para escribir. Solo afirma lo que está en los datos confirmados (Videos → Contexto); lo demás sale como «[FALTA: …]».</span>
      </div>
      <div class="formulario-2">
        <div class="campo">
          <span class="etiqueta">Redes</span>
          <div class="fila">
            <label v-for="r in ORDEN_REDES" :key="r" class="casilla">
              <input v-model="f.redes" type="checkbox" :value="r" :disabled="bloqueada" /> {{ REDES[r].nombre }}
            </label>
          </div>
        </div>
        <div class="campo">
          <span class="etiqueta">Texto</span>
          <div class="fila">
            <label class="casilla"><input type="radio" :checked="!mismo" :disabled="bloqueada" @change="cambiarModo('POR_RED')" /> Uno para cada red</label>
            <label class="casilla"><input type="radio" :checked="mismo" :disabled="bloqueada" @change="cambiarModo('MISMO')" /> El mismo para todas</label>
          </div>
        </div>
      </div>
      <div v-if="mismo" class="campo">
        <div class="fila entre">
          <label for="texto-comun">Texto para {{ nombresRedes || 'las redes' }}</label>
          <span class="chico" :class="textoFinal(f.comun, hashtags).length > limiteComun ? 'ambar' : 'tenue'">{{ textoFinal(f.comun, hashtags).length }} / {{ limiteComun }}</span>
        </div>
        <textarea id="texto-comun" v-model="f.comun" rows="6" :disabled="bloqueada" />
        <small v-if="faltas(f.comun).length" class="ambar">Falta: {{ faltas(f.comun).join(', ') }}</small>
      </div>
      <template v-else>
        <div v-for="r in redes" :key="r" class="campo">
          <div class="fila entre">
            <label :for="`texto-${r}`">{{ REDES[r].nombre }}</label>
            <span class="chico" :class="largo(r) > REDES[r].limite ? 'ambar' : 'tenue'">{{ largo(r) }} / {{ REDES[r].limite }}</span>
          </div>
          <textarea :id="`texto-${r}`" v-model="f.textos[r]" :rows="r === 'LINKEDIN' ? 8 : 5" :disabled="bloqueada" />
          <small v-if="faltas(f.textos[r]).length" class="ambar">Falta: {{ faltas(f.textos[r]).join(', ') }}</small>
        </div>
      </template>
    </section>

    <!-- 2 · Flyer -->
    <section class="panel pila">
      <div class="fila entre">
        <h2><Icono :nombre="p.media === 'VIDEO' ? 'videos' : 'imagen'" /> 2 · {{ p.media === 'VIDEO' ? 'Video' : 'Flyer' }}</h2>
        <span v-if="p.flyer.fondoCredito" class="chico tenue">
          <a v-if="p.flyer.fondoUrl" :href="p.flyer.fondoUrl" target="_blank" rel="noopener noreferrer">{{ p.flyer.fondoCredito }}</a>
          <template v-else>{{ p.flyer.fondoCredito }}</template>
        </span>
      </div>
      <div class="flyer">
        <div class="medio">
          <video v-if="p.media === 'VIDEO'" :src="archivoUrl" controls preload="metadata" />
          <img v-else-if="p.media === 'IMAGEN'" :src="archivoUrl" alt="Imagen de la publicación" @load="medirImagen" />
          <div v-else class="vacio-medio chico">Elige un fondo y el Radar arma el flyer con el título y tu logo.</div>
        </div>
        <div class="pila">
          <div class="campo">
            <label for="fl-titulo">Título del flyer</label>
            <input id="fl-titulo" v-model="f.flyer.titulo" type="text" maxlength="80" :disabled="bloqueada" placeholder="Ven y conoce nuestro Campus" />
          </div>
          <div class="campo">
            <label for="fl-detalle">Detalle</label>
            <input id="fl-detalle" v-model="f.flyer.detalle" type="text" maxlength="120" :disabled="bloqueada" placeholder="Sábado 15 de noviembre · 10:00 a. m." />
            <small v-if="faltas(f.flyer.detalle).length" class="ambar">Falta: {{ faltas(f.flyer.detalle).join(', ') }}</small>
          </div>
          <div class="campo">
            <label for="fl-cta">Botón (llamada a la acción)</label>
            <input id="fl-cta" v-model="f.flyer.cta" type="text" maxlength="30" :disabled="bloqueada" placeholder="Inscríbete" />
          </div>
          <p v-if="p.flyer.enUso && flyerCambiado" class="chico ambar">Guarda los cambios para actualizar el flyer.</p>
          <div v-if="p.flyer.tieneFondo && !p.flyer.enUso && !bloqueada" class="fila">
            <button class="boton boton-chico boton-primario" type="button" :disabled="ocupado || !f.flyer.titulo.trim()" @click="armar">
              <Icono nombre="imagen" /> Armar flyer con el fondo elegido
            </button>
          </div>
        </div>
      </div>

      <div v-if="!bloqueada" class="fondo">
        <div class="pestanas-fondo" role="tablist" aria-label="Fondo del flyer">
          <button role="tab" type="button" :aria-selected="pestana === 'foto'" :class="{ activa: pestana === 'foto' }" @click="pestana = 'foto'">Foto gratuita</button>
          <button role="tab" type="button" :aria-selected="pestana === 'ia'" :class="{ activa: pestana === 'ia' }" @click="pestana = 'ia'">Crear con IA</button>
          <button role="tab" type="button" :aria-selected="pestana === 'propia'" :class="{ activa: pestana === 'propia' }" @click="pestana = 'propia'">Foto propia</button>
        </div>
        <div v-if="pestana === 'foto'" class="pila">
          <form class="fila" @submit.prevent="buscarFotos(1)">
            <label class="oculto-visual" for="fl-buscar">Buscar foto de fondo</label>
            <input id="fl-buscar" v-model="consulta" class="crece" type="search" placeholder="chef cocina profesional" />
            <button class="boton boton-chico" type="submit" :disabled="ocupado || consulta.trim().length < 2"><Icono nombre="buscar" /> Buscar</button>
          </form>
          <p v-if="fuentes && !fuentes.fotos" class="chico ambar">Falta la clave del banco de fotos (PIXABAY_API_KEY en 03_worker/.env).</p>
          <div v-if="fotos" class="rejilla">
            <button v-for="x in fotos.fotos" :key="x.id" type="button" class="foto" :disabled="ocupado" :title="`Usar esta foto · ${x.autor}`" @click="elegirFoto(x.id)">
              <img :src="x.miniatura" :alt="x.alt || 'Foto del banco'" loading="lazy" />
            </button>
          </div>
          <p v-if="fotos && !fotos.fotos.length" class="chico">Sin resultados: prueba con otras palabras.</p>
          <div v-if="fotos && (fotos.pagina > 1 || fotos.hay_mas)" class="fila">
            <button class="boton boton-chico boton-fantasma" type="button" :disabled="ocupado || fotos.pagina <= 1" @click="buscarFotos(fotos.pagina - 1)"><Icono nombre="anterior" /> Anteriores</button>
            <button class="boton boton-chico boton-fantasma" type="button" :disabled="ocupado || !fotos.hay_mas" @click="buscarFotos(fotos.pagina + 1)">Más <Icono nombre="siguiente" /></button>
          </div>
          <p class="chico tenue">Fotos de {{ fotos?.fuente === 'PEXELS' ? 'Pexels' : 'Pixabay' }}, de uso libre también comercial. Son genéricas: para el campus real, usa «Foto propia».</p>
        </div>
        <div v-else-if="pestana === 'ia'" class="pila">
          <div class="campo">
            <label for="fl-ia">Qué debe mostrar el fondo</label>
            <textarea id="fl-ia" v-model="f.flyer.descripcion" rows="2" placeholder="Una cocina profesional luminosa con alumnos de gorro blanco trabajando" />
            <span class="campo-ayuda">Sin texto ni logos: el Radar los pone encima, bien escritos.</span>
          </div>
          <div class="fila">
            <button class="boton boton-chico" type="button" :disabled="ocupado || f.flyer.descripcion.trim().length < 5" @click="crearConIa">
              <Icono nombre="chispa" /> Crear fondo con IA<template v-if="fuentes"> (≈ US$ {{ fuentes.precio_usd.toFixed(2) }})</template>
            </button>
          </div>
          <p v-if="fuentes && !fuentes.gemini" class="chico ambar">Falta la clave de Gemini en el worker.</p>
        </div>
        <div v-else class="pila">
          <p class="chico">Una foto real (del campus, de un evento): JPG o PNG hasta 8 MB. El Radar la recorta a 4:5 y pone encima el título y el logo.</p>
          <div class="fila">
            <label class="boton boton-chico" :class="{ deshabilitado: ocupado }">
              <Icono nombre="subir" /> Elegir foto
              <input class="oculto-visual" type="file" accept="image/jpeg,image/png" :disabled="ocupado" @change="fondoPropio" />
            </label>
          </div>
        </div>
      </div>

      <details v-if="!bloqueada" class="chico">
        <summary>Usar un archivo propio en vez del flyer (imagen ya diseñada o video)</summary>
        <div class="pila propio">
          <p v-if="fueraDeInstagram" class="ambar">
            <Icono nombre="alerta" /> Instagram acepta imágenes entre 4:5 (vertical) y 1,91:1 (horizontal): esta la recortará.
          </p>
          <p v-if="subiendo !== null" aria-live="polite">Subiendo… {{ Math.round(subiendo * 100) }} %</p>
          <div class="fila">
            <label class="boton boton-chico" :class="{ deshabilitado: subiendo !== null }">
              <Icono nombre="subir" /> Subir imagen o video
              <input class="oculto-visual" type="file" accept="image/jpeg,image/png,video/mp4" :disabled="subiendo !== null" @change="subir" />
            </label>
            <button v-if="p.media !== 'NINGUNA'" class="boton boton-chico boton-fantasma" type="button" @click="quitarArchivo"><Icono nombre="x" /> Quitar imagen</button>
          </div>
          <span class="tenue">JPG o PNG hasta 8 MB · MP4 hasta 100 MB.</span>
        </div>
      </details>
    </section>

    <!-- 3 · Hashtags -->
    <section class="panel pila">
      <h2>3 · Hashtags</h2>
      <div class="campo">
        <label class="oculto-visual" for="p-hashtags">Hashtags</label>
        <input id="p-hashtags" v-model="f.hashtags" type="text" placeholder="#LeCordonBleuPeru #Gastronomia" :disabled="bloqueada" />
        <span class="campo-ayuda">
          Primero los del rubro (Publicaciones → Marca) y después los que la IA propone para este tema. Van debajo del texto en todas las
          redes; Instagram admite hasta 30.
        </span>
      </div>
    </section>

    <!-- Vista previa -->
    <section v-if="redes.length" class="panel pila">
      <div class="fila entre">
        <h2>Vista previa</h2>
        <div class="pestanas-fondo" role="tablist" aria-label="Red">
          <button v-for="r in redes" :key="r" role="tab" type="button" :aria-selected="vista === r" :class="{ activa: vista === r }" @click="vista = r">{{ REDES[r].nombre }}</button>
        </div>
      </div>
      <article class="post" :class="vista.toLowerCase()">
        <header class="chico"><strong>Tu página</strong> · {{ REDES[vista].nombre }}</header>
        <p v-if="vista !== 'INSTAGRAM'" class="post-texto">{{ final(vista) || 'Aún sin texto.' }}</p>
        <img v-if="p.media === 'IMAGEN'" :src="archivoUrl" alt="" />
        <video v-else-if="p.media === 'VIDEO'" :src="archivoUrl" controls preload="metadata" />
        <p v-if="vista === 'INSTAGRAM'" class="post-texto">{{ final(vista) || 'Aún sin texto.' }}</p>
      </article>
      <p class="chico tenue">Aproximada: cada red corta el texto largo con «Ver más».</p>
    </section>

    <div v-if="p.estado === 'BORRADOR' && problemas.length" class="aviso aviso-ambar" role="status">
      <Icono nombre="alerta" />
      <div class="aviso-cuerpo">
        <strong>Antes de aprobarla</strong>
        <ul>
          <li v-for="x in problemas" :key="x">{{ x }}</li>
        </ul>
      </div>
    </div>

    <div class="fila acciones">
      <button class="boton boton-primario" type="button" :disabled="ocupado || bloqueada || !cambiado" @click="guardar()"><Icono nombre="guardar" /> Guardar cambios</button>
      <template v-if="auth.esAdmin">
        <button v-if="p.estado === 'BORRADOR'" class="boton boton-primario" type="button" :disabled="ocupado || problemas.length > 0" @click="aprobar(true)">
          <Icono nombre="aprobar" /> 4 · Aprobar
        </button>
        <button v-if="p.estado === 'APROBADA' && !bloqueada" class="boton boton-fantasma" type="button" @click="aprobar(false)">Quitar aprobación</button>
      </template>
      <span v-else-if="p.estado === 'BORRADOR'" class="chico tenue">Un administrador tiene que aprobarla antes de publicarla.</span>
      <span v-if="cambiado" class="chico tenue">Cambios sin guardar</span>
      <button v-if="auth.esAdmin && !p.archivada" class="boton boton-fantasma derecha" type="button" @click="archivar">
        <Icono nombre="paquete" /> Archivar
      </button>
    </div>

    <details class="panel historial" @toggle="($event.target as HTMLDetailsElement).open && !historial && cargarHistorial()">
      <summary><strong>Historial</strong> <span class="chico tenue">· quién hizo qué y el texto exacto que se publicó</span></summary>
      <p v-if="!historial" class="chico tenue">Cargando…</p>
      <p v-else-if="!historial.length" class="chico tenue">Sin eventos (es anterior a la biblioteca).</p>
      <ol v-else class="eventos">
        <li v-for="(e, i) in historial" :key="i">
          <span class="tenue chico">{{ fechaHora(e.fecha) }}<template v-if="e.autor"> · {{ e.autor }}</template></span>
          <div>{{ e.detalle }}</div>
          <details v-if="e.evento === 'PUBLICADA' && e.datos?.texto" class="chico">
            <summary>Texto publicado</summary>
            <pre class="publicado">{{ e.datos.texto }}</pre>
          </details>
        </li>
      </ol>
    </details>
  </div>
</template>

<style scoped>
.estrecha {
  max-width: 960px;
}
.historial {
  margin-top: 16px;
}
.eventos {
  margin: 10px 0 0 18px;
  display: grid;
  gap: 8px;
}
.publicado {
  white-space: pre-wrap;
  font: inherit;
  background: var(--panel-2);
  border: 1px solid var(--borde);
  border-radius: 8px;
  padding: 8px 10px;
  margin: 4px 0 0;
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
.pasos {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  list-style: none;
  padding: 0;
  margin: 0 0 12px;
}
.pasos li {
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid var(--borde);
  color: var(--texto-suave, inherit);
}
.pasos li.hecho {
  border-color: var(--lima);
  background: var(--lima-fondo);
}
.flyer {
  display: grid;
  grid-template-columns: minmax(0, 320px) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}
@media (max-width: 720px) {
  .flyer {
    grid-template-columns: 1fr;
  }
}
.medio img,
.medio video {
  display: block;
  width: 100%;
  max-height: 480px;
  object-fit: contain;
  border-radius: 8px;
  background: #000;
}
.vacio-medio {
  display: grid;
  place-items: center;
  aspect-ratio: 4 / 5;
  padding: 16px;
  text-align: center;
  border: 2px dashed var(--borde);
  border-radius: 8px;
}
.fondo {
  display: grid;
  gap: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--borde);
}
.pestanas-fondo {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.pestanas-fondo button {
  padding: 6px 12px;
  border: 1px solid var(--borde);
  border-radius: 999px;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font: inherit;
  font-size: 0.9rem;
}
.pestanas-fondo button.activa {
  background: var(--panel-2);
  border-color: currentColor;
  font-weight: 600;
}
.rejilla {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 8px;
}
.foto {
  padding: 0;
  border: 2px solid transparent;
  border-radius: 8px;
  overflow: hidden;
  background: none;
  cursor: pointer;
  aspect-ratio: 4 / 5;
}
.foto:hover,
.foto:focus-visible {
  border-color: var(--ambar);
}
.foto img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.propio {
  margin-top: 8px;
}
.post {
  max-width: 420px;
  border: 1px solid var(--borde);
  border-radius: 10px;
  overflow: hidden;
  background: var(--panel-2);
}
.post header {
  padding: 10px 12px;
}
.post img,
.post video {
  display: block;
  width: 100%;
}
.post-texto {
  margin: 0;
  padding: 10px 12px;
  white-space: pre-wrap;
  max-height: 260px;
  overflow: auto;
}
.publicar {
  background: var(--panel-2);
}
.red-fila {
  display: grid;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--borde);
  border-radius: 8px;
}
.enlace {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  word-break: break-all;
}
.crece {
  flex: 1;
  min-width: 0;
}
.deshabilitado {
  opacity: 0.6;
  pointer-events: none;
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
.aviso ul {
  margin: 4px 0 0;
  padding-left: 18px;
}
</style>
