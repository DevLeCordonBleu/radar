<script setup lang="ts">
/**
 * Ficha completa de un anuncio, con flechas para recorrer los de un mismo grupo
 * (un punto del mapa, la galería filtrada, los veteranos). Es lo que la IA dijo de
 * ese anuncio, no una nota: la Biblioteca de Meta no publica resultados.
 *
 * La lista llega ya ordenada; quien la abre dice cómo en `orden`.
 * Teclado: ← → para cambiar de anuncio, Escape para cerrar.
 */
import { computed, nextTick, ref, watch } from 'vue'
import type { AnuncioInforme, Taxonomia } from '@/api/tipos'
import { diasActivo, duracionActivo, fecha } from '@/composables/formato'
import Icono from './Icono.vue'
import Plataformas from './Plataformas.vue'

const props = defineProps<{
  anuncios: AnuncioInforme[]
  /** Posición abierta; `null` = cerrado. */
  indice: number | null
  /** Qué grupo se recorre, p. ej. «Ángulo: Dominar la técnica». */
  contexto?: string
  orden?: string
  tax?: Taxonomia | null
  /** Texto del botón que lleva a la galería con el mismo filtro (sin él, no hay botón). */
  verTodos?: string
}>()
const emit = defineEmits<{ 'update:indice': [i: number | null]; galeria: [] }>()

const dialogo = ref<HTMLDialogElement | null>(null)
const detalle = ref<HTMLElement | null>(null)
const a = computed(() => (props.indice == null ? null : props.anuncios[props.indice] ?? null))
const total = computed(() => props.anuncios.length)

// Las URLs de Meta caducan a los pocos días: si el vídeo o la imagen no cargan, se dice.
const videoRoto = ref(false)
const imagenRota = ref(false)

watch(
  () => props.indice,
  async (i) => {
    videoRoto.value = false
    imagenRota.value = false
    if (i != null) {
      await nextTick()
      if (dialogo.value && !dialogo.value.open) dialogo.value.showModal()
      detalle.value?.scrollTo({ top: 0 })
    } else if (dialogo.value?.open) {
      dialogo.value.close()
    }
  },
)

const cerrar = () => emit('update:indice', null)
const ir = (paso: number) => {
  if (props.indice == null || !total.value) return
  emit('update:indice', (props.indice + paso + total.value) % total.value)
}

function tecla(e: KeyboardEvent) {
  if ((e.target as HTMLElement).closest('video, input, textarea')) return
  if (e.key === 'ArrowRight') ir(1)
  else if (e.key === 'ArrowLeft') ir(-1)
  else return
  e.preventDefault()
}

// Pulsar fuera de la ventana (en el fondo) la cierra.
function fuera(e: MouseEvent) {
  if (e.target === dialogo.value) cerrar()
}

const nombre = (lista: Record<string, string> | undefined, clave: string) => lista?.[clave] ?? clave.replace(/_/g, ' ')
const dias = computed(() => (a.value ? diasActivo(a.value) : null))
const nivel = computed(() => (a.value ? props.tax?.niveles?.[String(a.value.nivel)]?.nombre : undefined))

const clasificacion = computed(() => {
  const x = a.value
  if (!x) return []
  const t = props.tax
  return [
    { etiqueta: 'Estructura del hook', valor: nombre(t?.hooks, x.hook_estructura) },
    { etiqueta: 'Oferta', valor: x.oferta_tipo === 'sin_oferta' ? 'Sin oferta' : nombre(t?.ofertas, x.oferta_tipo) },
    { etiqueta: 'Llamada a la acción', valor: nombre(t?.ctas, x.cta_tipo) + (x.cta_texto ? ` (botón «${x.cta_texto}»)` : '') },
    { etiqueta: 'Formato', valor: nombre(t?.formatos, x.formato) + (x.duracion_seg ? ` · ${Math.round(x.duracion_seg)} s` : '') },
  ]
})

const detalles = computed(() => {
  const x = a.value
  if (!x) return []
  const sn = (b: boolean) => (b ? 'Sí' : 'No')
  return [
    { etiqueta: 'Precio a la vista', valor: sn(x.precio_visible) },
    { etiqueta: 'Marca en los 3 primeros segundos', valor: sn(x.marca_en_3s) },
    ...(x.formato === 'video' ? [{ etiqueta: 'Subtítulos', valor: sn(x.subtitulos) }] : []),
  ]
})
</script>

<template>
  <dialog ref="dialogo" class="visor" aria-labelledby="visor-titulo" @cancel.prevent="cerrar" @click="fuera" @keydown="tecla">
    <template v-if="a">
      <header class="cabeza">
        <div class="quien">
          <h2 id="visor-titulo">{{ a.anunciante }}</h2>
          <p v-if="contexto" class="contexto">{{ contexto }}</p>
          <p class="tenue chico num">
            <template v-if="nivel">{{ nivel }} · </template>
            <template v-if="a.activo">activo desde el {{ fecha(a.fecha_inicio) }}</template>
            <template v-else>empezó el {{ fecha(a.fecha_inicio) }}, ya no está activo</template>
            <template v-if="dias != null"> · {{ a.activo ? 'lleva' : 'duró' }} {{ duracionActivo(dias) }}</template>
          </p>
          <Plataformas :plataformas="a.plataformas" class="redes" />
        </div>
        <div class="mando">
          <div class="pasos">
            <button type="button" class="boton boton-chico icono" aria-label="Anuncio anterior" :disabled="total < 2" @click="ir(-1)">
              <Icono nombre="anterior" />
            </button>
            <span class="num chico" aria-live="polite">{{ (indice ?? 0) + 1 }} de {{ total }}</span>
            <button type="button" class="boton boton-chico icono" aria-label="Anuncio siguiente" :disabled="total < 2" @click="ir(1)">
              <Icono nombre="siguiente" />
            </button>
          </div>
          <small v-if="orden" class="tenue orden">{{ orden }}</small>
        </div>
        <button type="button" class="boton boton-chico icono cerrar" aria-label="Cerrar" @click="cerrar"><Icono nombre="x" /></button>
      </header>

      <div class="contenido">
        <div class="medio">
          <span class="chip-medio">{{ nombre(tax?.formatos, a.formato) }}</span>
          <video
            v-if="a.video_url && !videoRoto"
            :key="a.ad_id + 'v'"
            :src="a.video_url"
            :poster="a.thumb_url ?? undefined"
            controls
            playsinline
            preload="metadata"
            @error="videoRoto = true"
          ></video>
          <img
            v-else-if="a.thumb_url && !imagenRota"
            :key="a.ad_id + 'i'"
            :src="a.thumb_url"
            :alt="`Creatividad del anuncio de ${a.anunciante}`"
            referrerpolicy="no-referrer"
            @error="imagenRota = true"
          />
          <div v-else class="sin-medio">
            <Icono nombre="imagen" />
            <p v-if="a.thumb_url || a.video_url">
              Meta ya no sirve la creatividad de este anuncio: sus enlaces caducan a los pocos días.
              <a v-if="a.snapshot_url" :href="a.snapshot_url" target="_blank" rel="noopener noreferrer">Verlo en Meta</a>
            </p>
            <p v-else>Este anuncio no trae la creatividad en la descarga.</p>
          </div>
          <p v-if="videoRoto && a.thumb_url && !imagenRota" class="aviso-medio">
            El vídeo ya no está disponible en Meta (sus enlaces caducan): esta es su portada.
          </p>
        </div>

        <div ref="detalle" class="detalle">
          <section>
            <h3>Cómo abre</h3>
            <blockquote v-if="a.hook_literal">«{{ a.hook_literal }}»</blockquote>
            <p v-else class="suave">Sin titular claro.</p>
          </section>

          <section v-if="a.copy">
            <h3>Texto del anuncio</h3>
            <p class="copy">{{ a.copy }}</p>
          </section>

          <section>
            <h3>Cómo lo clasificó la herramienta</h3>
            <dl class="clasif">
              <div v-for="c in clasificacion" :key="c.etiqueta">
                <dt class="tenue chico">{{ c.etiqueta }}</dt>
                <dd>{{ c.valor }}</dd>
              </div>
            </dl>
          </section>

          <section v-if="a.territorios_angulo.length">
            <h3>Territorio</h3>
            <div class="chips"><span v-for="t in a.territorios_angulo" :key="t" class="chip chip-violeta">{{ t }}</span></div>
          </section>

          <section v-if="a.angulos_libres.length">
            <h3>Qué promete</h3>
            <div class="chips"><span v-for="t in a.angulos_libres" :key="t" class="chip chip-cian">{{ t }}</span></div>
          </section>

          <section v-if="a.beneficios_libres.length">
            <h3>Qué gana el cliente</h3>
            <div class="chips"><span v-for="t in a.beneficios_libres" :key="t" class="chip">{{ t }}</span></div>
          </section>

          <section v-if="a.patron_visual.length">
            <h3>Qué se ve</h3>
            <div class="chips"><span v-for="t in a.patron_visual" :key="t" class="chip">{{ nombre(tax?.patrones, t) }}</span></div>
          </section>

          <section>
            <h3>Detalles</h3>
            <dl class="clasif">
              <div v-for="c in detalles" :key="c.etiqueta">
                <dt class="tenue chico">{{ c.etiqueta }}</dt>
                <dd>{{ c.valor }}</dd>
              </div>
            </dl>
          </section>
        </div>
      </div>

      <footer class="pie">
        <a v-if="a.snapshot_url" :href="a.snapshot_url" target="_blank" rel="noopener noreferrer" class="boton boton-chico">
          Ver en la Biblioteca de Meta <Icono nombre="externo" />
        </a>
        <a v-if="a.enlace" :href="a.enlace" target="_blank" rel="noopener noreferrer" class="boton boton-chico">
          Su página de destino <Icono nombre="externo" />
        </a>
        <button v-if="verTodos" type="button" class="boton boton-chico boton-primario todos" @click="emit('galeria')">
          {{ verTodos }}
        </button>
      </footer>
    </template>
  </dialog>
</template>

<style scoped>
.visor {
  margin: auto;
  width: min(1100px, calc(100vw - 32px));
  height: min(800px, calc(100dvh - 48px));
  padding: 0;
  background: var(--panel);
  color: var(--texto);
  border: 1px solid var(--borde-fuerte);
  border-radius: var(--radio);
  box-shadow: var(--sombra);
  overflow: hidden;
}
.visor[open] {
  display: flex;
  flex-direction: column;
}
.visor::backdrop {
  background: rgba(3, 7, 18, 0.72);
}
.cabeza {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--borde);
}
.quien {
  flex: 1;
  min-width: 0;
}
.quien h2 {
  font-size: 1.05rem;
  overflow-wrap: anywhere;
}
.contexto {
  color: var(--cian);
  font-size: 0.74rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  margin: 2px 0;
}
.mando {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.pasos {
  display: flex;
  align-items: center;
  gap: 8px;
}
.pasos span {
  min-width: 64px;
  text-align: center;
}
.orden {
  font-size: 0.7rem;
}
.icono {
  padding: 6px;
  line-height: 0;
}
.icono svg {
  width: 16px;
  height: 16px;
}
.contenido {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
}
.medio {
  position: relative;
  background: #0b1220;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 0;
}
.medio video,
.medio img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.redes {
  margin-top: 6px;
}
.chip-medio {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 1;
  background: rgba(0, 0, 0, 0.65);
  color: #fff;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 3px 9px;
  border-radius: 999px;
}
.sin-medio {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  max-width: 280px;
  padding: 24px;
  text-align: center;
  color: rgba(255, 255, 255, 0.72);
  font-size: 0.88rem;
}
.sin-medio a {
  color: #fff;
  text-decoration: underline;
}
.sin-medio svg {
  width: 40px;
  height: 40px;
}
.aviso-medio {
  position: absolute;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  width: max-content;
  max-width: 90%;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  font-size: 0.78rem;
  padding: 6px 12px;
  border-radius: var(--radio-chico);
  text-align: center;
}
.detalle {
  overflow-y: auto;
  padding: 18px 22px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.detalle h3 {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--texto-tenue);
  margin-bottom: 8px;
}
blockquote {
  border-left: 3px solid var(--cian);
  padding-left: 14px;
  font-size: 1.12rem;
  line-height: 1.4;
  overflow-wrap: anywhere;
}
.copy {
  white-space: pre-line;
  color: var(--texto-suave);
  overflow-wrap: anywhere;
}
.clasif {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 18px;
}
.clasif dd {
  margin: 0;
  font-weight: 500;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.pie {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 18px;
  border-top: 1px solid var(--borde);
}
.pie a {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.pie svg {
  width: 13px;
  height: 13px;
}
.todos {
  margin-left: auto;
}
@media (max-width: 760px) {
  .visor {
    width: 100vw;
    height: 100dvh;
    max-width: none;
    max-height: none;
    border-radius: 0;
  }
  .cabeza {
    flex-wrap: wrap;
  }
  .mando {
    order: 3;
    width: 100%;
  }
  .contenido {
    display: block;
    overflow-y: auto;
  }
  .medio {
    height: 45dvh;
  }
  .detalle {
    overflow: visible;
  }
}
@media print {
  .visor {
    display: none !important;
  }
}
</style>
