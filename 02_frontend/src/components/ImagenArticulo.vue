<script setup lang="ts">
/**
 * Imagen destacada de un artículo del Plan SEO. Dos fuentes:
 *  - Banco de fotos (Pixabay, o Pexels si esa es la clave del worker): fotos reales de
 *    uso libre; se busca, se elige y el Radar la guarda.
 *  - Gemini: imagen generada a partir de una descripción. Es de pago (la API no tiene
 *    plan gratuito de imágenes): se confirma antes y Google la rechaza sin facturación.
 * La imagen viaja a WordPress con el artículo, como imagen destacada.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { seo } from '@/api/radar'
import type { ArticuloSeo, BusquedaFotos, FotoBanco, FuentesImagen } from '@/api/tipos'
import Icono from '@/components/Icono.vue'
import { confirmar } from '@/composables/confirmar'
import { useAvisos } from '@/stores/avisos'

const props = defineProps<{ articulo: ArticuloSeo; bloqueado?: boolean }>()
const emit = defineEmits<{ actualizado: [ArticuloSeo] }>()
const avisos = useAvisos()

const fuentes = ref<FuentesImagen | null>(null)
const imagen = computed(() => props.articulo.imagen)
const eligiendo = ref(false)
const pestana = ref<'fotos' | 'gemini'>('fotos')
const ocupado = ref<'' | 'buscar' | 'elegir' | 'generar' | 'textos'>('')

onMounted(async () => {
  fuentes.value = await seo.fuentesImagen().catch(() => null)
})

const NOMBRES: Record<string, string> = { PIXABAY: 'Pixabay', PEXELS: 'Pexels', GEMINI: 'IA' }
const WEBS: Record<string, string> = { PIXABAY: 'https://pixabay.com', PEXELS: 'https://www.pexels.com' }
const banco = computed(() => fuentes.value?.fotos ?? 'PIXABAY')

// ── Textos de la imagen ──
const alt = ref('')
const leyenda = ref('')
watch(
  imagen,
  (i) => {
    alt.value = i?.alt ?? ''
    leyenda.value = i?.leyenda ?? ''
  },
  { immediate: true },
)
const textosCambiados = computed(() => !!imagen.value && (alt.value !== (imagen.value.alt ?? '') || leyenda.value !== (imagen.value.leyenda ?? '')))

async function guardarTextos() {
  ocupado.value = 'textos'
  try {
    emit('actualizado', await seo.textosImagen(props.articulo.codigo, alt.value, leyenda.value))
    avisos.exito('Textos de la imagen guardados.')
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = ''
  }
}

async function quitar() {
  const r = await confirmar({
    titulo: '¿Quitar la imagen?',
    mensaje: 'El artículo se queda sin imagen destacada en el Radar.',
    puntos: props.articulo.wpId ? ['Si ya está en WordPress, allí no se borra: quítala desde la entrada si no la quieres.'] : [],
    aceptar: 'Quitar',
    tono: 'peligro',
  })
  if (!r.ok) return
  try {
    emit('actualizado', await seo.quitarImagen(props.articulo.codigo))
  } catch (e) {
    avisos.error(e)
  }
}

// ── Banco de fotos ──
const consulta = ref(props.articulo.keyword)
const resultado = ref<BusquedaFotos | null>(null)
const elegida = ref<FotoBanco | null>(null)

async function buscar(pagina = 1) {
  if (consulta.value.trim().length < 2) return
  ocupado.value = 'buscar'
  try {
    const r = await seo.buscarFotos(consulta.value.trim(), pagina)
    resultado.value = pagina === 1 || !resultado.value ? r : { ...r, fotos: [...resultado.value.fotos, ...r.fotos] }
    if (pagina === 1) elegida.value = null
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = ''
  }
}

async function usarFoto() {
  if (!elegida.value) return
  ocupado.value = 'elegir'
  try {
    emit('actualizado', await seo.imagenDelBanco(props.articulo.codigo, elegida.value.id, ''))
    eligiendo.value = false
    resultado.value = null
    elegida.value = null
    avisos.exito('Foto guardada como imagen destacada.')
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = ''
  }
}

// ── Gemini ──
const descripcion = ref('')
watch(
  () => [props.articulo.titulo, imagen.value?.prompt] as const,
  ([titulo, prompt]) => {
    if (!descripcion.value) descripcion.value = prompt || titulo || props.articulo.keyword
  },
  { immediate: true },
)
const precio = computed(() => (fuentes.value ? `${fuentes.value.precio_usd.toFixed(3)} US$` : ''))

async function generar() {
  if (descripcion.value.trim().length < 5 || !fuentes.value) return
  const r = await confirmar({
    titulo: '¿Generar la imagen con Gemini?',
    mensaje: `Una imagen con ${fuentes.value.modelo}: unos ${precio.value}, que Google cobra en tu proyecto.`,
    puntos: [
      'La API de Gemini no tiene plan gratuito para imágenes: hace falta la facturación activa en el proyecto de tu clave. Si no lo está, Google la rechaza y no cobra nada.',
      'Suele tardar entre 10 y 30 segundos.',
      imagen.value ? 'Sustituye la imagen actual.' : 'Se guarda como imagen destacada del artículo.',
    ],
    aceptar: 'Generar',
    tono: 'aviso',
  })
  if (!r.ok) return
  ocupado.value = 'generar'
  try {
    emit('actualizado', await seo.generarImagen(props.articulo.codigo, descripcion.value.trim(), ''))
    eligiendo.value = false
    avisos.exito('Imagen generada. Revísala antes de enviarla.')
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = ''
  }
}

const kb = (n: number) => (n >= 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.round(n / 1024)} KB`)
</script>

<template>
  <section class="panel imagen-articulo" aria-labelledby="titulo-imagen">
    <div class="cabecera">
      <h2 id="titulo-imagen"><Icono nombre="imagen" /> Imagen destacada</h2>
      <div v-if="imagen && !eligiendo" class="fila">
        <button class="boton boton-chico" type="button" :disabled="bloqueado || !!ocupado" @click="eligiendo = true">Cambiar</button>
        <button class="boton boton-chico boton-fantasma" type="button" :disabled="bloqueado || !!ocupado" @click="quitar"><Icono nombre="basura" /> Quitar</button>
      </div>
      <button v-else-if="imagen" class="boton boton-chico boton-fantasma" type="button" @click="eligiendo = false">Cancelar</button>
    </div>

    <!-- La imagen actual -->
    <div v-if="imagen && !eligiendo" class="actual">
      <img :src="seo.urlImagen(articulo.codigo, imagen.modificada)" :alt="imagen.alt ?? ''" class="previa" />
      <div class="pila">
        <p class="fila chico">
          <span v-if="imagen.fuente !== 'GEMINI'" class="chip chip-cian">{{ NOMBRES[imagen.fuente] }}</span>
          <span v-else class="chip chip-violeta" :title="imagen.modelo ?? ''">Generada con IA</span>
          <span class="tenue">{{ kb(imagen.bytes) }}</span>
          <span v-if="imagen.wpMediaId" class="chip chip-lima">en WordPress</span>
          <span v-else-if="articulo.wpId" class="chip chip-ambar">se sube en el próximo envío</span>
        </p>
        <p v-if="imagen.fuente !== 'GEMINI' && imagen.autor" class="chico tenue">
          Foto de <a :href="imagen.autorUrl ?? undefined" target="_blank" rel="noopener noreferrer">{{ imagen.autor }}</a> en
          <a :href="imagen.origenUrl ?? WEBS[imagen.fuente]" target="_blank" rel="noopener noreferrer">{{ NOMBRES[imagen.fuente] }}</a>
        </p>
        <p v-else-if="imagen.prompt" class="chico tenue">Pedido: «{{ imagen.prompt }}»</p>
        <form class="pila" @submit.prevent="guardarTextos">
          <div class="campo">
            <label for="img-alt">Texto alternativo <span class="tenue">(describe la imagen; lo leen Google y los lectores de pantalla)</span></label>
            <input id="img-alt" v-model="alt" type="text" maxlength="300" required :disabled="bloqueado" />
          </div>
          <div class="campo">
            <label for="img-leyenda">Leyenda o crédito</label>
            <input id="img-leyenda" v-model="leyenda" type="text" maxlength="300" :disabled="bloqueado" />
          </div>
          <div v-if="textosCambiados" class="fila">
            <button class="boton boton-chico boton-primario" type="submit" :disabled="!!ocupado || !alt.trim()"><Icono nombre="guardar" /> Guardar textos</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Elegir una -->
    <div v-else class="pila">
      <p v-if="!imagen" class="chico tenue">
        Va a WordPress con el artículo, como imagen destacada. Elige una foto gratis de {{ NOMBRES[banco] }} o genérala con IA (de pago).
      </p>
      <div class="pestanas chicas" role="tablist" aria-label="Fuente de la imagen">
        <button role="tab" type="button" :aria-selected="pestana === 'fotos'" :class="{ activa: pestana === 'fotos' }" @click="pestana = 'fotos'">
          Foto de {{ NOMBRES[banco] }} <span class="tenue">· gratis</span>
        </button>
        <button role="tab" type="button" :aria-selected="pestana === 'gemini'" :class="{ activa: pestana === 'gemini' }" @click="pestana = 'gemini'">
          Generar con IA <span class="tenue">· de pago</span>
        </button>
      </div>

      <template v-if="pestana === 'fotos'">
        <p v-if="fuentes && !fuentes.fotos" class="chico">
          Falta la clave del banco de fotos. Crea una cuenta gratis en Pixabay, copia tu clave de
          <a href="https://pixabay.com/api/docs/" target="_blank" rel="noopener noreferrer">pixabay.com/api/docs</a>, ponla en
          <span class="mono">03_worker/.env</span> como <span class="mono">PIXABAY_API_KEY=</span> y reinicia el Radar.
        </p>
        <template v-else>
          <form class="fila buscador" role="search" @submit.prevent="buscar()">
            <label for="img-consulta" class="oculto-visual">Buscar fotos</label>
            <input id="img-consulta" v-model="consulta" type="search" maxlength="100" placeholder="Ej.: masa madre, pan artesanal" :disabled="bloqueado" />
            <button class="boton" type="submit" :disabled="bloqueado || !!ocupado || consulta.trim().length < 2">
              <Icono nombre="buscar" /> {{ ocupado === 'buscar' ? 'Buscando…' : 'Buscar' }}
            </button>
          </form>
          <p v-if="resultado && !resultado.fotos.length" class="chico">
            {{ NOMBRES[banco] }} no tiene fotos para «{{ consulta }}». Prueba con menos palabras o en inglés («sourdough bread»).
          </p>
          <div v-if="resultado?.fotos.length" class="galeria" role="listbox" aria-label="Fotos encontradas">
            <button
              v-for="foto in resultado.fotos"
              :key="foto.id"
              type="button"
              role="option"
              class="foto"
              :class="{ elegida: elegida?.id === foto.id }"
              :aria-selected="elegida?.id === foto.id"
              :title="`${foto.alt || 'Foto'} · ${foto.autor}`"
              @click="elegida = foto"
            >
              <img :src="foto.miniatura" :alt="foto.alt || `Foto de ${foto.autor}`" loading="lazy" />
            </button>
          </div>
          <div v-if="resultado?.fotos.length" class="fila">
            <button class="boton boton-primario" type="button" :disabled="!elegida || !!ocupado" @click="usarFoto">
              <Icono nombre="ok" /> {{ ocupado === 'elegir' ? 'Guardando…' : 'Usar esta foto' }}
            </button>
            <button v-if="resultado.hay_mas" class="boton boton-fantasma" type="button" :disabled="!!ocupado" @click="buscar(resultado.pagina + 1)">Más fotos</button>
            <span v-if="elegida" class="chico tenue">Foto de {{ elegida.autor }}</span>
          </div>
          <p v-if="resultado" class="chico tenue">
            Fotos de <a :href="WEBS[resultado.fuente]" target="_blank" rel="noopener noreferrer">{{ NOMBRES[resultado.fuente] }}</a>: uso libre, también
            comercial. El crédito al fotógrafo va como leyenda.
          </p>
        </template>
      </template>

      <template v-else>
        <p v-if="fuentes && !fuentes.gemini" class="chico">Falta la clave de Gemini en <span class="mono">03_worker/.env</span>.</p>
        <form v-else class="pila" @submit.prevent="generar">
          <div class="campo">
            <label for="img-descripcion">Qué debe mostrar la imagen</label>
            <textarea id="img-descripcion" v-model="descripcion" rows="3" maxlength="1000" :disabled="bloqueado"></textarea>
            <span class="campo-ayuda">Se pide como fotografía realista y horizontal, sin texto ni logotipos. Sé concreto: «manos amasando pan de masa madre sobre mesa de madera».</span>
          </div>
          <div class="aviso aviso-ambar" role="note">
            <Icono nombre="alerta" />
            <div class="aviso-cuerpo chico">
              <strong>De pago:</strong> unos {{ precio }} por imagen ({{ fuentes?.modelo }}). La API de Gemini no tiene plan gratuito para
              imágenes: necesitas activar la facturación en el proyecto de Google de tu clave.
            </div>
          </div>
          <div class="fila">
            <button class="boton boton-primario" type="submit" :disabled="bloqueado || !!ocupado || descripcion.trim().length < 5">
              <Icono nombre="chispa" /> {{ ocupado === 'generar' ? 'Generando… (10-30 s)' : 'Generar imagen' }}
            </button>
          </div>
        </form>
      </template>
    </div>
  </section>
</template>

<style scoped>
.cabecera {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.cabecera h2 {
  font-size: 1rem;
  margin: 0;
}
.imagen-articulo svg {
  width: 15px;
  height: 15px;
  vertical-align: -2px;
}
.actual {
  display: grid;
  grid-template-columns: minmax(0, 340px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
@media (max-width: 760px) {
  .actual {
    grid-template-columns: minmax(0, 1fr);
  }
}
.previa {
  width: 100%;
  aspect-ratio: 1200 / 627;
  object-fit: cover;
  border-radius: var(--radio);
  border: 1px solid var(--borde);
  background: var(--borde);
}
.buscador input {
  flex: 1;
  min-width: 0;
}
.galeria {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 8px;
}
.foto {
  padding: 0;
  border: 2px solid transparent;
  border-radius: var(--radio);
  overflow: hidden;
  background: var(--borde);
  cursor: pointer;
  aspect-ratio: 4 / 3;
}
.foto img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.foto:hover {
  border-color: var(--borde-fuerte);
}
.foto.elegida {
  border-color: var(--cian);
  box-shadow: 0 0 0 2px var(--cian-fondo);
}
.pestanas.chicas {
  display: flex;
  gap: 4px;
  align-items: center;
  border-bottom: 1px solid var(--borde);
  flex-wrap: wrap;
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
</style>
