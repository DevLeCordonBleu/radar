<script setup lang="ts">
/**
 * Un artículo del Plan SEO: la IA lo redacta (tarea en segundo plano), la persona
 * lo revisa y lo edita en Markdown, y lo envía a WordPress.
 *
 * Los «[COMPLETAR: …]» son datos del negocio que la IA no puede saber (precios,
 * fechas, duraciones): mientras quede alguno no se puede enviar. La vista previa
 * sale del mismo conversor que el envío, así que se ve lo que llegará a la web.
 * La imagen destacada (banco de fotos o Gemini) se elige en `ImagenArticulo` y viaja con el envío.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { seo } from '@/api/radar'
import type { ArticuloSeo, WordpressEstado } from '@/api/tipos'
import Icono from '@/components/Icono.vue'
import ImagenArticulo from '@/components/ImagenArticulo.vue'
import { confirmar } from '@/composables/confirmar'
import { fechaHora } from '@/composables/formato'
import { useSondeo } from '@/composables/sondeo'
import { useAuth } from '@/stores/auth'
import { useAvisos } from '@/stores/avisos'

const route = useRoute()
const router = useRouter()
const auth = useAuth()
const avisos = useAvisos()
const codigo = computed(() => String(route.params.codigo))

const a = ref<ArticuloSeo | null>(null)
const wp = ref<WordpressEstado | null>(null)
const cargando = ref(true)
const error = ref('')
const ocupado = ref(false)

interface Formulario {
  titulo: string
  slug: string
  metaDescription: string
  contenido: string
}
const f = ref<Formulario>({ titulo: '', slug: '', metaDescription: '', contenido: '' })
const original = ref('')
const sucio = computed(() => JSON.stringify(f.value) !== original.value)

function rellenar(x: ArticuloSeo) {
  f.value = { titulo: x.titulo ?? '', slug: x.slug ?? '', metaDescription: x.metaDescription ?? '', contenido: x.contenido ?? '' }
  original.value = JSON.stringify(f.value)
}

const redactando = computed(() => a.value?.tareaEstado === 'EN_COLA' || a.value?.tareaEstado === 'CORRIENDO')

async function cargar() {
  const antes = a.value
  const x = await seo.articulo(codigo.value)
  a.value = x
  // Lo que acaba de redactar la IA entra en el formulario; lo que escribe la persona no se pisa.
  if (!antes || !sucio.value || (antes.redactado !== x.redactado && x.contenido)) rellenar(x)
}

onMounted(async () => {
  try {
    await cargar()
    wp.value = await seo.wordpress().catch(() => null)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    cargando.value = false
  }
})

useSondeo(cargar, () => redactando.value, 3000)

watch(redactando, (ahora, antes) => {
  if (antes && !ahora && a.value) {
    if (a.value.tareaEstado === 'TERMINADA') avisos.exito('Artículo redactado. Revísalo antes de enviarlo.')
    else if (a.value.tareaEstado === 'PAUSADA') avisos.error(a.value.tareaError || 'La redacción quedó en pausa.')
  }
})

// ── Lo que falta ──────────────────────────────────────────────────────────

const PENDIENTE = /\[COMPLETAR:[^\]\n]*\]/gi
const marcas = computed(() => f.value.contenido.match(PENDIENTE) ?? [])
const palabras = computed(() => f.value.contenido.split(/\s+/).filter((p) => /\w/.test(p)).length)

// ── Editar y vista previa ─────────────────────────────────────────────────

const modo = ref<'editar' | 'vista'>('editar')
const html = ref('')

watch(modo, async (m) => {
  if (m !== 'vista') return
  try {
    html.value = (await seo.vistaPrevia(f.value.contenido)).html
  } catch (e) {
    avisos.error(e)
  }
})

async function guardar(silencioso = false) {
  if (!a.value) return false
  ocupado.value = true
  try {
    const x = await seo.editarArticulo(a.value.codigo, f.value)
    a.value = x
    rellenar(x)
    if (!silencioso) avisos.exito('Cambios guardados.')
    return true
  } catch (e) {
    avisos.error(e)
    return false
  } finally {
    ocupado.value = false
  }
}

async function redactarDeNuevo() {
  if (!a.value) return
  const r = await confirmar({
    titulo: a.value.contenido ? '¿Volver a redactar el artículo?' : '¿Redactar el artículo?',
    mensaje: a.value.contenido
      ? 'Gemini escribe una versión nueva y sustituye el título, la descripción y el texto actuales, también lo que hayas editado.'
      : 'Gemini escribe el borrador. Tarda alrededor de un minuto.',
    puntos: [
      'Una llamada a Gemini.',
      a.value.indicaciones ? `Indicaciones anteriores: «${a.value.indicaciones}». Escribe otras abajo o déjalo vacío para quitarlas.` : 'Puedes darle indicaciones abajo.',
    ],
    aceptar: 'Redactar',
    tono: a.value.contenido ? 'aviso' : 'primario',
    campo: { etiqueta: 'Indicaciones (opcional)', marcador: 'Ej.: más corto, enfocado en principiantes, menciona nuestro taller de panadería' },
  })
  if (!r.ok) return
  ocupado.value = true
  try {
    a.value = await seo.redactar(a.value.codigo, r.texto)
    original.value = JSON.stringify(f.value) // lo escrito se va a sustituir: no avisar al salir
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

// ── WordPress ─────────────────────────────────────────────────────────────

async function enviar(publicar: boolean) {
  if (!a.value || !wp.value?.completo) return
  const yaEnviado = !!a.value.wpId
  const r = await confirmar({
    titulo: publicar ? '¿Publicar en la web?' : yaEnviado ? '¿Actualizar la entrada en WordPress?' : '¿Enviar a WordPress como borrador?',
    mensaje: publicar
      ? `Queda publicado en ${wp.value.sitio} y visible para cualquiera.`
      : yaEnviado
        ? 'Se sustituyen el título, el texto y el extracto de la entrada que ya está en WordPress. Su estado (borrador o publicada) no cambia.'
        : `Se crea una entrada en borrador en ${wp.value.sitio}: nadie la ve hasta que alguien la publique desde WordPress.`,
    puntos: [
      'La descripción para Google va como «extracto» de la entrada. Si usas Yoast o Rank Math, cópiala también en su campo.',
      a.value.imagen
        ? 'La imagen va como imagen destacada, con su texto alternativo y su leyenda.'
        : 'Sin imagen destacada: puedes elegirla arriba o ponerla después en WordPress.',
      'Categorías y etiquetas se ponen en WordPress.',
    ],
    aceptar: publicar ? 'Publicar' : yaEnviado ? 'Actualizar' : 'Enviar borrador',
    tono: publicar ? 'aviso' : 'primario',
  })
  if (!r.ok) return
  if (sucio.value && !(await guardar(true))) return
  ocupado.value = true
  try {
    a.value = await seo.enviarWordpress(a.value.codigo, publicar)
    rellenar(a.value)
    avisos.exito(publicar ? 'Publicado en la web.' : yaEnviado ? 'Entrada actualizada en WordPress.' : 'Enviado a WordPress como borrador.')
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

async function desvincular() {
  if (!a.value) return
  const r = await confirmar({
    titulo: '¿Desvincular de WordPress?',
    mensaje: 'El Radar olvida la entrada de WordPress (no la borra allí). El siguiente envío creará una entrada nueva.',
    puntos: ['Úsalo si borraron la entrada en WordPress o quieres enviarla de nuevo desde cero.'],
    aceptar: 'Desvincular',
  })
  if (!r.ok) return
  try {
    a.value = await seo.desvincular(a.value.codigo)
  } catch (e) {
    avisos.error(e)
  }
}

async function borrar() {
  if (!a.value) return
  const r = await confirmar({
    titulo: '¿Borrar el artículo?',
    mensaje: a.value.wpId ? 'Se borra del Radar. La entrada que ya está en WordPress no se toca.' : 'Se borra del Radar. No se puede deshacer.',
    aceptar: 'Borrar',
    tono: 'peligro',
  })
  if (!r.ok) return
  try {
    await seo.borrarArticulo(a.value.codigo)
    original.value = JSON.stringify(f.value)
    avisos.exito('Artículo borrado.')
    router.push({ path: '/seo', query: { pestana: 'articulos' } })
  } catch (e) {
    avisos.error(e)
  }
}

onBeforeRouteLeave(async () => {
  if (!sucio.value) return true
  const r = await confirmar({ titulo: '¿Salir sin guardar?', mensaje: 'Tienes cambios sin guardar en el artículo.', aceptar: 'Salir', cancelar: 'Seguir editando', tono: 'peligro' })
  return r.ok
})

const ESTADO_WP: Record<string, string> = { draft: 'borrador', publish: 'publicada', pending: 'pendiente de revisión', future: 'programada', private: 'privada' }
const ruta = (u: string) => u.replace(/^https?:\/\/[^/]+/, '') || '/'
</script>

<template>
  <div class="pagina">
    <p v-if="cargando" class="cargando suave">Cargando…</p>
    <div v-else-if="error" class="aviso aviso-error" role="alert"><Icono nombre="error" /><div class="aviso-cuerpo">{{ error }}</div></div>

    <template v-else-if="a">
      <div class="pagina-cabecera">
        <div>
          <RouterLink :to="{ path: '/seo', query: { pestana: 'articulos' } }" class="chico volver"><Icono nombre="volver" /> Artículos</RouterLink>
          <h1>{{ f.titulo || a.keyword }}</h1>
          <p class="fila chico">
            <span class="tenue">Responde a «{{ a.keyword }}»</span>
            <span v-if="a.redactado" class="tenue">· redactado {{ fechaHora(a.redactado) }}</span>
            <span v-if="a.wpId" class="chip" :class="a.wpEstado === 'publish' ? 'chip-lima' : 'chip-violeta'">
              WordPress: {{ ESTADO_WP[a.wpEstado ?? ''] ?? a.wpEstado }}
            </span>
            <span v-if="a.cambiosSinEnviar" class="chip chip-ambar">cambios sin enviar</span>
          </p>
        </div>
        <div class="fila">
          <button class="boton" type="button" :disabled="ocupado || redactando" @click="redactarDeNuevo">
            <Icono nombre="chispa" /> {{ a.contenido ? 'Volver a redactar' : 'Redactar' }}
          </button>
          <button v-if="auth.esAdmin" class="boton boton-peligro" type="button" :disabled="ocupado || redactando" @click="borrar"><Icono nombre="basura" /> Borrar</button>
        </div>
      </div>

      <section v-if="redactando" class="panel" aria-live="polite">
        <p><strong>Gemini está redactando el artículo…</strong> Suele tardar alrededor de un minuto; esta página se actualiza sola.</p>
        <div class="barra"><div class="barra-relleno indeterminada"></div></div>
      </section>
      <div v-else-if="!a.contenido" class="aviso aviso-ambar" role="status">
        <Icono nombre="pausa" />
        <div class="aviso-cuerpo">
          <strong>{{ a.tareaEstado === 'PAUSADA' ? 'La redacción quedó en pausa.' : 'Este artículo aún no está redactado.' }}</strong>
          {{ a.tareaEstado === 'PAUSADA' ? a.tareaError : '' }}
          <template v-if="a.tareaEstado === 'PAUSADA'"> Puedes continuarla desde Plan SEO o pulsar «Redactar».</template>
        </div>
      </div>

      <div v-if="a.contenido" class="disposicion">
        <div class="pila principal">
          <!-- Cambiar la imagen no toca el texto: solo se actualiza el artículo, no el formulario. -->
          <ImagenArticulo :articulo="a" :bloqueado="ocupado || redactando" @actualizado="(x) => (a = x)" />
          <form class="panel pila editor" @submit.prevent="guardar()">
            <div class="campo">
              <label for="titulo">Título <span class="tenue">({{ f.titulo.length }}; mejor menos de 65)</span></label>
              <input id="titulo" v-model="f.titulo" type="text" required maxlength="200" :disabled="redactando" />
            </div>
            <div class="formulario-2">
              <div class="campo">
                <label for="slug">URL (slug)</label>
                <input id="slug" v-model="f.slug" type="text" maxlength="90" spellcheck="false" :disabled="redactando" />
              </div>
              <div class="campo">
                <label for="meta">Descripción para Google <span class="tenue">({{ f.metaDescription.length }}; de 120 a 155)</span></label>
                <input id="meta" v-model="f.metaDescription" type="text" maxlength="300" :disabled="redactando" />
              </div>
            </div>

            <div class="pestanas chicas" role="tablist" aria-label="Contenido">
              <button role="tab" type="button" :aria-selected="modo === 'editar'" :class="{ activa: modo === 'editar' }" @click="modo = 'editar'">Texto</button>
              <button role="tab" type="button" :aria-selected="modo === 'vista'" :class="{ activa: modo === 'vista' }" @click="modo = 'vista'">Vista previa</button>
              <span class="tenue chico contador">{{ palabras }} palabras</span>
            </div>
            <div v-if="modo === 'editar'" class="campo">
              <label for="contenido" class="oculto-visual">Contenido</label>
              <textarea id="contenido" v-model="f.contenido" rows="26" spellcheck="true" :disabled="redactando"></textarea>
              <span class="campo-ayuda">
                Markdown: <span class="mono">## Sección</span>, <span class="mono">### Subsección</span>, <span class="mono">- punto</span>,
                <span class="mono">**negrita**</span>, <span class="mono">[texto](https://…)</span>. Deja una línea en blanco entre párrafos.
              </span>
            </div>
            <!-- El HTML sale del conversor del worker, que escapa todo el texto. -->
            <!-- eslint-disable-next-line vue/no-v-html -->
            <div v-else class="vista-previa" v-html="html"></div>

            <div class="fila">
              <button class="boton boton-primario" type="submit" :disabled="ocupado || redactando || !sucio"><Icono nombre="guardar" /> Guardar</button>
              <span v-if="sucio" class="chico tenue">Cambios sin guardar</span>
            </div>
          </form>
        </div>

        <aside class="pila lateral">
          <section class="panel">
            <h2>Antes de enviar</h2>
            <p v-if="marcas.length" class="chico rojo">
              <Icono nombre="alerta" /> Quedan {{ marcas.length }} {{ marcas.length === 1 ? 'dato' : 'datos' }} por completar en el texto:
            </p>
            <ul v-if="marcas.length" class="chico lista-pendientes">
              <li v-for="(m, i) in marcas" :key="i">{{ m }}</li>
            </ul>
            <p v-else class="chico"><Icono nombre="ok" /> No queda ningún «[COMPLETAR: …]».</p>
            <template v-if="a.pendientes.filter((p) => !p.startsWith('[COMPLETAR')).length">
              <p class="chico">La IA pide verificar:</p>
              <ul class="chico lista-pendientes">
                <li v-for="p in a.pendientes.filter((x) => !x.startsWith('[COMPLETAR'))" :key="p">{{ p }}</li>
              </ul>
            </template>
            <p class="chico tenue">Lee el texto entero: la IA puede equivocarse en datos generales. Nada sale a la web sin que lo envíes.</p>
          </section>

          <section class="panel">
            <h2>WordPress</h2>
            <template v-if="wp?.completo">
              <p v-if="a.wpId" class="chico">
                Entrada {{ ESTADO_WP[a.wpEstado ?? ''] ?? a.wpEstado }} en {{ wp.sitio }}, enviada {{ fechaHora(a.enviado!) }}.
                <a v-if="a.wpEditar" :href="a.wpEditar" target="_blank" rel="noopener noreferrer" class="block">Abrir en WordPress</a>
                <a v-if="a.wpEnlace" :href="a.wpEnlace" target="_blank" rel="noopener noreferrer" class="block">{{ a.wpEstado === 'publish' ? 'Ver en la web' : 'Vista previa' }}</a>
              </p>
              <p v-else class="chico">Se envía a {{ wp.sitio }} como borrador: lo publicas tú desde WordPress cuando quieras.</p>
              <div class="pila">
                <button
                  class="boton boton-primario"
                  type="button"
                  :disabled="ocupado || redactando || marcas.length > 0"
                  :title="marcas.length ? 'Completa los datos marcados antes de enviar' : ''"
                  @click="enviar(false)"
                >
                  <Icono nombre="subir" /> {{ a.wpId ? 'Actualizar en WordPress' : 'Enviar como borrador' }}
                </button>
                <button
                  v-if="auth.esAdmin && a.wpEstado !== 'publish'"
                  class="boton"
                  type="button"
                  :disabled="ocupado || redactando || marcas.length > 0"
                  @click="enviar(true)"
                >
                  Publicar directamente
                </button>
                <button v-if="a.wpId" class="boton boton-chico boton-fantasma" type="button" :disabled="ocupado" @click="desvincular">Desvincular de WordPress</button>
              </div>
            </template>
            <p v-else class="chico">
              WordPress no está conectado. Los pasos están en
              <RouterLink :to="{ path: '/seo', query: { pestana: 'articulos' } }">Plan SEO → Artículos</RouterLink>. Mientras tanto puedes copiar el texto.
            </p>
          </section>

          <section class="panel">
            <h2>De dónde sale</h2>
            <p class="chico">Búsqueda principal: <strong>{{ a.keyword }}</strong></p>
            <p v-if="a.variantes.length" class="chico tenue">Variantes: {{ a.variantes.join(' · ') }}</p>
            <p class="chico">Páginas de competidores que tocan el tema:</p>
            <ul class="chico lista-pendientes">
              <li v-for="o in a.origenes" :key="o.url">
                {{ o.sitio }}: <a :href="o.url" target="_blank" rel="noopener noreferrer">{{ ruta(o.url) }}</a>
              </li>
            </ul>
            <p v-if="a.indicaciones" class="chico tenue">Indicaciones: «{{ a.indicaciones }}»</p>
          </section>
        </aside>
      </div>
    </template>
  </div>
</template>

<style scoped>
.volver svg {
  width: 14px;
  height: 14px;
  vertical-align: -2px;
}
.disposicion {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 16px;
  align-items: start;
}
@media (max-width: 1000px) {
  .disposicion {
    grid-template-columns: minmax(0, 1fr);
  }
}
.lateral h2 {
  font-size: 1rem;
  margin-bottom: 6px;
}
.lateral svg,
.editor .fila svg,
.pagina-cabecera svg {
  width: 15px;
  height: 15px;
  vertical-align: -2px;
}
.lista-pendientes {
  margin: 4px 0 8px 18px;
  display: grid;
  gap: 3px;
  overflow-wrap: anywhere;
}
.editor textarea {
  font-family: var(--mono);
  font-size: 0.88rem;
  line-height: 1.55;
  resize: vertical;
}
.pestanas.chicas {
  display: flex;
  gap: 4px;
  align-items: center;
  border-bottom: 1px solid var(--borde);
}
.pestanas.chicas button {
  background: none;
  border: 0;
  border-bottom: 2px solid transparent;
  padding: 7px 12px;
  color: var(--texto-suave);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
  margin-bottom: -1px;
}
.pestanas.chicas button.activa {
  color: var(--cian);
  border-bottom-color: var(--cian);
}
.contador {
  margin-left: auto;
}
.vista-previa {
  border: 1px solid var(--borde);
  border-radius: var(--radio);
  padding: 20px 24px;
  line-height: 1.65;
  max-width: 75ch;
  overflow-wrap: anywhere;
}
.vista-previa :deep(h2) {
  font-size: 1.3rem;
  margin: 1.4em 0 0.5em;
}
.vista-previa :deep(h3) {
  font-size: 1.1rem;
  margin: 1.2em 0 0.4em;
}
.vista-previa :deep(p),
.vista-previa :deep(ul),
.vista-previa :deep(ol),
.vista-previa :deep(blockquote) {
  margin: 0 0 0.9em;
}
.vista-previa :deep(ul),
.vista-previa :deep(ol) {
  padding-left: 1.4em;
}
.vista-previa :deep(blockquote) {
  border-left: 3px solid var(--borde-fuerte);
  padding-left: 12px;
  color: var(--texto-suave);
}
.vista-previa :deep(mark.completar) {
  background: var(--ambar-fondo);
  color: var(--ambar);
  border-radius: 3px;
  padding: 0 3px;
}
.barra-relleno.indeterminada {
  width: 35%;
  animation: vaiven 1.6s ease-in-out infinite;
}
@keyframes vaiven {
  0% {
    margin-left: 0;
  }
  50% {
    margin-left: 65%;
  }
  100% {
    margin-left: 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  .barra-relleno.indeterminada {
    animation: none;
    width: 100%;
    opacity: 0.4;
  }
}
</style>
