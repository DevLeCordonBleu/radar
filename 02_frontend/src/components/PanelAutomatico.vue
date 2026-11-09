<script setup lang="ts">
/**
 * Flujo automático del Plan SEO: cada semana, inventario → temas → keywords → artículos de
 * lo que falta → imagen del banco → borrador en WordPress. Publicar sigue siendo de la
 * persona. Solo un admin lo programa o lo lanza; el backend lo revisa cada 5 minutos, así
 * que solo corre con el Radar abierto (si a la hora estaba cerrado, corre al abrirlo).
 * «Qué redactaría ahora» enseña los candidatos y por qué van en ese orden.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { seo } from '@/api/radar'
import type { ArticuloSeo, AutomaticoSeo, CandidatoArticulo } from '@/api/tipos'
import Icono from '@/components/Icono.vue'
import { confirmar } from '@/composables/confirmar'
import { fechaHora } from '@/composables/formato'
import { useAuth } from '@/stores/auth'
import { useAvisos } from '@/stores/avisos'

const props = defineProps<{ hayTarea: boolean; articulos: ArticuloSeo[] }>()
const emit = defineEmits<{ lanzada: [] }>()
const auth = useAuth()
const avisos = useAvisos()

const estado = ref<AutomaticoSeo | null>(null)
const f = ref({ activo: false, dia: 1, hora: '09:00', articulos: 2 })
const ocupado = ref(false)
const cambiado = computed(() => {
  const e = estado.value
  return !!e && (f.value.activo !== e.activo || f.value.dia !== e.dia || f.value.hora !== e.hora || f.value.articulos !== e.articulos)
})

const GOOGLE: Record<string, { texto: string; chip: string; ayuda: string }> = {
  EXACTA: { texto: 'Google la sugiere', chip: 'chip-lima', ayuda: 'El autocompletado de Google propone esta misma búsqueda: la gente la escribe así.' },
  VARIANTES: { texto: 'Google sugiere variantes', chip: 'chip-violeta', ayuda: 'Google propone búsquedas más largas que la contienen.' },
}
function motivo(c: CandidatoArticulo): string {
  const pos = c.gsc ? c.gsc.posicion.toFixed(1) : ''
  if (c.motivo === 'YA_POSICIONA') return `tu web ya aparece en la posición ${pos} (Search Console)`
  if (c.motivo === 'MEJORAR_PAGINA') return `tu web aparece en la posición ${pos}: mejor mejorar esa página que escribir otra`
  return 'Google no la sugiere: casi nadie la escribe así'
}
const DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
const PASOS = ['Inventario', 'Temas', 'Keywords', 'Search Console', 'Elige qué falta', 'Redacta + foto', 'Borrador en WordPress', 'Propone mejoras de páginas']

async function cargar() {
  try {
    const e = await seo.automatico()
    estado.value = e
    f.value = { activo: e.activo, dia: e.dia, hora: e.hora, articulos: e.articulos }
  } catch (e) {
    avisos.error(e)
  }
}

onMounted(cargar)
// Al terminar una tarea (la del automático u otra), su resumen y los candidatos pueden haber cambiado.
watch(() => props.hayTarea, (ahora, antes) => antes && !ahora && cargar())

const resumen = computed(() => {
  const e = estado.value
  if (!e) return ''
  if (!e.activo) return 'Desactivado: actívalo para que corra solo cada semana.'
  return `Cada ${DIAS[e.dia - 1]} a las ${e.hora} (hora de Lima) · ${e.articulos} ${e.articulos === 1 ? 'artículo' : 'artículos'} por vez`
})

async function guardar() {
  ocupado.value = true
  try {
    const e = await seo.guardarAutomatico(f.value)
    estado.value = e
    f.value = { activo: e.activo, dia: e.dia, hora: e.hora, articulos: e.articulos }
    avisos.exito(e.activo ? 'Flujo automático programado.' : 'Flujo automático desactivado.')
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

async function ejecutarAhora() {
  const n = f.value.articulos
  const r = await confirmar({
    titulo: '¿Ejecutar el flujo automático ahora?',
    mensaje: `Hace todo el recorrido y redacta hasta ${n} ${n === 1 ? 'artículo' : 'artículos'} de lo que le falta a tu web.`,
    puntos: [
      'Inventario de todos los sitios: puede tardar varios minutos (una página por segundo).',
      'Usa Gemini para temas, keywords y redacción (plan gratuito; si se agota la cuota, queda en pausa y «Continuar» sigue donde quedó).',
      'Los artículos sin «[COMPLETAR]» van a WordPress como borrador; nada se publica.',
    ],
    aceptar: 'Ejecutar',
  })
  if (!r.ok) return
  ocupado.value = true
  try {
    await seo.ejecutarAutomatico()
    emit('lanzada')
    await cargar()
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

// ── Lo que hizo la última ejecución ──
const ultima = computed(() => estado.value?.tarea ?? null)
const lista = (clave: string) => {
  const v = ultima.value?.resumen?.[clave]
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : []
}
const titulo = (codigo: string) => {
  const a = props.articulos.find((x) => x.codigo === codigo)
  return a ? a.titulo || a.keyword : codigo
}
const ESTADO: Record<string, { texto: string; chip: string }> = {
  EN_COLA: { texto: 'en cola', chip: 'chip-cian' },
  CORRIENDO: { texto: 'en marcha', chip: 'chip-cian' },
  PAUSADA: { texto: 'en pausa', chip: 'chip-ambar' },
  TERMINADA: { texto: 'terminada', chip: 'chip-lima' },
  CANCELADA: { texto: 'cancelada', chip: '' },
}
</script>

<template>
  <section class="panel automatico" aria-labelledby="titulo-automatico">
    <header class="cabeza">
      <div>
        <h2 id="titulo-automatico">
          <Icono nombre="reloj" /> Flujo automático
          <span v-if="estado" class="chip" :class="estado.activo ? 'chip-lima' : ''">{{ estado.activo ? 'Programado' : 'Desactivado' }}</span>
        </h2>
        <p class="chico suave">{{ resumen }}</p>
        <p v-if="estado?.activo && estado.proxima" class="chico">
          <Icono nombre="calendario" /> Próxima ejecución: <strong>{{ fechaHora(estado.proxima) }}</strong>
        </p>
      </div>
      <button
        v-if="auth.esAdmin"
        class="boton"
        type="button"
        :disabled="ocupado || hayTarea"
        :title="hayTarea ? 'Hay una tarea en marcha' : 'Hace todo el recorrido ahora, sin esperar a la fecha'"
        @click="ejecutarAhora"
      >
        <Icono nombre="chispa" /> Ejecutar ahora
      </button>
    </header>

    <!-- Lo que hace, en orden; el último paso es de la persona -->
    <ol class="pasos" aria-label="Qué hace cada ejecución">
      <li v-for="(p, i) in PASOS" :key="p"><span class="num">{{ i + 1 }}</span>{{ p }}</li>
      <li class="tuyo"><Icono nombre="ok" />Tú revisas, publicas y aplicas las mejoras</li>
    </ol>

    <div class="columnas">
      <!-- Programación -->
      <div class="bloque">
        <h3>Programación</h3>
        <form v-if="auth.esAdmin" class="programa" @submit.prevent="guardar">
          <label class="interruptor">
            <input v-model="f.activo" type="checkbox" role="switch" :disabled="ocupado" />
            <span class="pista" aria-hidden="true"></span>
            <span>Ejecutar cada semana</span>
          </label>
          <div class="campos" :class="{ apagado: !f.activo }">
            <div class="campo">
              <label for="auto-dia">Día</label>
              <select id="auto-dia" v-model.number="f.dia" :disabled="ocupado">
                <option v-for="(d, i) in DIAS" :key="d" :value="i + 1">{{ d }}</option>
              </select>
            </div>
            <div class="campo">
              <label for="auto-hora">Hora (Lima)</label>
              <input id="auto-hora" v-model="f.hora" type="time" required :disabled="ocupado" />
            </div>
            <div class="campo">
              <label for="auto-articulos">Artículos por vez</label>
              <select id="auto-articulos" v-model.number="f.articulos" :disabled="ocupado">
                <option v-for="n in 5" :key="n" :value="n">{{ n }}</option>
              </select>
            </div>
          </div>
          <div class="fila">
            <button class="boton boton-primario" type="submit" :disabled="ocupado || !cambiado"><Icono nombre="guardar" /> Guardar</button>
            <span v-if="cambiado" class="chico tenue">Cambios sin guardar</span>
          </div>
        </form>
        <p v-else class="chico">Solo un administrador cambia la programación.</p>
        <p class="chico tenue nota">
          Solo corre con el Radar abierto: si a esa hora está cerrado, corre al abrirlo. Los artículos con «[COMPLETAR]» esperan aquí tus datos.
        </p>
      </div>

      <!-- Qué elegiría -->
      <div class="bloque">
        <h3>Qué redactaría ahora</h3>
        <p class="chico suave">
          Búsquedas <strong>informativas</strong> que tu web <strong>no cubre</strong> (ni posiciona, si Search Console está
          conectado), aún sin artículo, y que la gente <strong>escribe en Google</strong> (lo dice su autocompletado). Van primero
          las que Google sugiere tal cual; luego, las que tratan <strong>más páginas de competidores</strong>.
        </p>
        <p v-if="estado && !estado.google" class="chico ambar">
          <Icono nombre="alerta" /> No se pudo consultar a Google: este orden es solo por competidores.
        </p>
        <ol v-if="estado?.candidatos.length" class="candidatos">
          <li v-for="(c, i) in estado.candidatos" :key="c.grupo" :class="{ fuera: i >= f.articulos }">
            <div class="fila">
              <strong>{{ c.keyword }}</strong>
              <span v-if="i < f.articulos" class="chip chip-cian">siguiente</span>
              <span v-if="c.google && GOOGLE[c.google]" class="chip" :class="GOOGLE[c.google].chip" :title="GOOGLE[c.google].ayuda">
                {{ GOOGLE[c.google].texto }}
              </span>
            </div>
            <small class="tenue">
              {{ c.paginas }} {{ c.paginas === 1 ? 'página' : 'páginas' }} de {{ c.sitios.join(', ') || 'competidores' }} · relevancia
              {{ c.relevancia }}<template v-if="c.busquedas > 1"> · {{ c.busquedas }} formas de buscarla</template>
            </small>
            <small v-if="c.gsc" class="tenue gsc">
              Search Console: {{ c.gsc.impresiones }} impresiones, posición {{ c.gsc.posicion.toFixed(1) }} (no basta para cubrirla)
            </small>
            <small v-if="c.sugerencias.length" class="tenue sugeridas">También buscan: {{ c.sugerencias.join(' · ') }}</small>
          </li>
        </ol>
        <p v-else-if="estado" class="chico">
          Ahora no queda ninguna búsqueda informativa sin cobertura y sin artículo<template v-if="estado.descartados.length">
            que la gente escriba en Google</template>.
        </p>
        <details v-if="estado?.descartados.length" class="chico descartadas">
          <summary>{{ estado.descartados.length }} {{ estado.descartados.length === 1 ? 'descartada' : 'descartadas' }}</summary>
          <p class="tenue">Si alguna te interesa igual, redáctala a mano desde «Keywords».</p>
          <ul class="lista">
            <li v-for="c in estado.descartados" :key="c.grupo">
              <strong>{{ c.keyword }}</strong> — {{ motivo(c) }}
              <a v-if="c.gsc && c.motivo !== 'GOOGLE_NO_SUGIERE'" :href="c.gsc.url" target="_blank" rel="noopener">ver página</a>
            </li>
          </ul>
        </details>
        <p class="chico tenue nota">Cada ejecución actualiza inventario y keywords antes de elegir: la lista puede cambiar.</p>
      </div>
    </div>

    <!-- Última ejecución -->
    <div v-if="ultima" class="ultima">
      <p class="chico fila">
        <strong>Última ejecución</strong>
        <span>{{ fechaHora(ultima.creado) }}</span>
        <span class="chip" :class="ESTADO[ultima.estado]?.chip">{{ ESTADO[ultima.estado]?.texto ?? ultima.estado }}</span>
      </p>
      <p v-if="ultima.estado === 'PAUSADA' && ultima.error" class="chico ambar">{{ ultima.error }}</p>
      <p v-else-if="ultima.activa" class="chico">{{ ultima.mensaje || 'Trabajando…' }}</p>
      <p v-else-if="ultima.mensaje" class="chico">{{ ultima.mensaje }}</p>
      <ul v-if="lista('articulos').length" class="chico lista">
        <li v-for="c in lista('articulos')" :key="c">
          <RouterLink :to="`/seo/articulos/${c}`">{{ titulo(c) }}</RouterLink>
          <span v-if="lista('enviados').includes(c)" class="chip chip-violeta">borrador en WordPress</span>
          <span v-else-if="lista('esperanDatos').includes(c)" class="chip chip-ambar">espera tus datos</span>
        </li>
      </ul>
      <p v-if="lista('mejoras').length" class="chico">
        {{ lista('mejoras').length }} {{ lista('mejoras').length === 1 ? 'propuesta' : 'propuestas' }} de mejora de páginas: revísalas en
        Keywords → «Páginas para mejorar».
      </p>
      <p v-if="lista('descartados').length" class="chico tenue">
        Descartadas (ya las posicionas o Google no las sugiere): {{ lista('descartados').join(' · ') }}
      </p>
      <details v-if="lista('avisos').length" class="chico">
        <summary>{{ lista('avisos').length }} {{ lista('avisos').length === 1 ? 'aviso' : 'avisos' }}</summary>
        <ul class="lista">
          <li v-for="a in lista('avisos')" :key="a">{{ a }}</li>
        </ul>
      </details>
    </div>
  </section>
</template>

<style scoped>
.automatico svg {
  width: 15px;
  height: 15px;
  vertical-align: -2px;
}
.cabeza {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}
.cabeza h2 {
  font-size: 1.05rem;
  margin: 0 0 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.cabeza p {
  margin: 2px 0 0;
}

/* Pasos */
.pasos {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 14px 0;
  padding: 0;
}
.pasos li {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px 4px 4px;
  border: 1px solid var(--borde);
  border-radius: 999px;
  font-size: 0.8rem;
  color: var(--texto-suave);
  white-space: nowrap;
}
.pasos .num {
  display: inline-grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--cian-fondo);
  color: var(--cian);
  font-weight: 700;
  font-size: 0.72rem;
}
.pasos .tuyo {
  padding-left: 10px;
  border-color: var(--cian);
  color: var(--cian);
  font-weight: 600;
}

/* Dos columnas que pasan a una cuando no caben */
.columnas {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr));
  gap: 16px;
}
.bloque {
  border: 1px solid var(--borde);
  border-radius: var(--radio);
  padding: 14px 16px;
  min-width: 0;
}
.bloque h3 {
  font-size: 0.95rem;
  margin: 0 0 10px;
}
.nota {
  margin: 10px 0 0;
}

/* Programación */
.programa {
  display: grid;
  gap: 12px;
}
.campos {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
  transition: opacity 0.15s;
}
.campos.apagado {
  opacity: 0.55;
}
.campos .campo {
  min-width: 0;
}
.interruptor {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  cursor: pointer;
  width: fit-content;
}
.interruptor input {
  position: absolute;
  opacity: 0;
  width: 1px;
  height: 1px;
}
.pista {
  position: relative;
  width: 38px;
  height: 22px;
  border-radius: 999px;
  background: var(--borde-fuerte);
  transition: background 0.15s;
  flex: none;
}
.pista::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 3px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #fff;
  transition: transform 0.15s;
}
.interruptor input:checked + .pista {
  background: var(--cian);
}
.interruptor input:checked + .pista::after {
  transform: translateX(16px);
}
.interruptor input:focus-visible + .pista {
  outline: 2px solid var(--cian);
  outline-offset: 2px;
}
.interruptor input:disabled + .pista {
  opacity: 0.5;
}

/* Candidatos */
.candidatos {
  margin: 10px 0 0;
  padding-left: 20px;
  display: grid;
  gap: 8px;
}
.candidatos li {
  overflow-wrap: anywhere;
}
.candidatos li.fuera {
  opacity: 0.6;
}
.candidatos .fila {
  gap: 6px;
  flex-wrap: wrap;
}
.sugeridas {
  display: block;
  font-style: italic;
}
.gsc {
  display: block;
}
.descartadas {
  margin-top: 10px;
}
.descartadas p {
  margin: 4px 0 0;
}

/* Última ejecución */
.ultima {
  border-top: 1px solid var(--borde);
  margin-top: 16px;
  padding-top: 10px;
}
.lista {
  margin: 4px 0 0 18px;
  display: grid;
  gap: 4px;
  overflow-wrap: anywhere;
}
.lista .chip {
  margin-left: 6px;
}
.ambar {
  color: var(--ambar);
}
@media (prefers-reduced-motion: reduce) {
  .pista,
  .pista::after,
  .campos {
    transition: none;
  }
}
</style>
