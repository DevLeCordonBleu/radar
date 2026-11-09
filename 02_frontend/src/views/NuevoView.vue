<script setup lang="ts">
/**
 * Análisis de competencia: tu mercado (marcas, competidores, sector) y los límites de la
 * búsqueda. Muestra el costo estimado ANTES de lanzar y recuerda el mercado
 * para el siguiente análisis.
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { analisis, sistema } from '@/api/radar'
import type { Estimacion, Marca, Peticion, Taxonomia } from '@/api/tipos'
import BuscadorPaginas from '@/components/BuscadorPaginas.vue'
import Icono from '@/components/Icono.vue'
import PanelSemanal from '@/components/PanelSemanal.vue'
import { PAISES, usd } from '@/composables/formato'
import { useAvisos } from '@/stores/avisos'

const router = useRouter()
const avisos = useAvisos()

const f = reactive<Peticion & { marcas: Marca[] }>({
  misMarcas: [],
  marcas: [{ nombre: '', paginas: [] }],
  competidores: [{ nombre: '', nivel: 1 }],
  keywords: [],
  referencia: [],
  pais: 'PE',
  maximo: 100,
  soloActivos: true,
  conMedios: true,
  fechaMinima: null,
})
const hoy = new Date().toISOString().slice(0, 10)
// Los campos de lista se editan como texto separado por comas.
const keywordsTxt = ref('')
const referenciaTxt = ref('')

const tax = ref<Taxonomia | null>(null)
const est = ref<Estimacion | null>(null)
const enviando = ref(false)
const faltaWorker = ref(false)
/** Con la fuente «navegador» descargar los anuncios no cuesta nada. */
const conApify = ref(false)
/** El formulario siempre empieza vacío; el mercado guardado se carga solo si se pide. */
const guardado = ref<Peticion | null>(null)

const lista = (t: string) => t.split(',').map((x) => x.trim()).filter(Boolean)

const NIVELES_FIJOS: Record<string, { nombre: string; desc: string }> = {
  '1': { nombre: 'Directo', desc: 'Compite por el mismo cliente en la misma zona' },
  '2': { nombre: 'Proximidad', desc: 'Zona cercana con oferta comparable' },
  '3': { nombre: 'Categoría', desc: 'Mismo tipo de producto en la región' },
  '4': { nombre: 'Nacional', desc: 'Mismo tipo de producto en todo el país' },
}
const niveles = computed(() => tax.value?.niveles ?? NIVELES_FIJOS)

const conAlgo = <T extends { nombre: string; paginas?: unknown[] }>(x: T) => !!(x.nombre.trim() || x.paginas?.length)

function peticion(): Peticion {
  const marcas = f.marcas.filter(conAlgo)
  return {
    ...f,
    marcas,
    misMarcas: marcas.map((m) => m.nombre.trim() || m.paginas?.[0]?.nombre || ''),
    keywords: lista(keywordsTxt.value),
    referencia: lista(referenciaTxt.value),
    competidores: f.competidores.filter(conAlgo),
  }
}

onMounted(async () => {
  sistema.taxonomia().then((t) => (tax.value = t)).catch(() => (faltaWorker.value = true))
  sistema.estado().then((s) => (conApify.value = s.worker?.anuncios?.fuente === 'apify')).catch(() => {})
  // Abre ya el Chrome de las sugerencias de páginas: así la primera no tarda.
  analisis.prepararPaginas(f.pais).catch(() => {})
  sistema
    .mercado()
    .then((m) => (guardado.value = m.competidores.length || m.misMarcas.length || m.keywords.length ? m : null))
    .catch(() => {})
  estimar()
})

function usarGuardado() {
  const m = guardado.value
  if (!m) return
  // Un mercado guardado antes de poder elegir páginas solo trae los nombres de las marcas.
  const marcas = m.marcas?.length ? m.marcas : m.misMarcas.map((nombre) => ({ nombre, paginas: [] }))
  // Copia: editar el formulario no debe tocar lo guardado.
  const copia: Peticion = JSON.parse(JSON.stringify({ ...m, marcas }))
  Object.assign(f, copia, {
    competidores: copia.competidores.length ? copia.competidores : [{ nombre: '', nivel: 1 }],
    marcas: copia.marcas?.length ? copia.marcas : [{ nombre: '', paginas: [] }],
  })
  keywordsTxt.value = m.keywords.join(', ')
  referenciaTxt.value = m.referencia.join(', ')
  estimar()
}

let espera: ReturnType<typeof setTimeout> | null = null
function estimar() {
  if (espera) clearTimeout(espera)
  espera = setTimeout(async () => {
    try {
      est.value = await analisis.estimar(peticion())
    } catch {
      est.value = null
    }
  }, 300)
}
watch(() => [f.maximo, f.conMedios], estimar)

const agregar = () => f.competidores.push({ nombre: '', nivel: 2 })
const quitar = (i: number) => f.competidores.splice(i, 1)
/** Una fila con páginas de negocios distintos pasa a ser un competidor por página, con el mismo nivel. */
function separar(i: number) {
  const c = f.competidores[i]
  f.competidores.splice(i, 1, ...(c.paginas ?? []).map((p) => ({ nombre: p.nombre, nivel: c.nivel, paginas: [p] })))
}
const agregarMarca = () => f.marcas.push({ nombre: '', paginas: [] })
/** La última fila no se quita: se vacía, para poder escribir otra marca. */
const quitarMarca = (i: number) => (f.marcas.length > 1 ? f.marcas.splice(i, 1) : (f.marcas[0] = { nombre: '', paginas: [] }))

const hayAlgo = computed(
  () =>
    f.competidores.some(conAlgo) || lista(keywordsTxt.value).length > 0 || f.marcas.some(conAlgo),
)

async function guardarMercado() {
  try {
    guardado.value = await sistema.guardarMercado(peticion())
    avisos.exito('Mercado guardado: recupéralo cuando quieras con «Usar mi mercado guardado».')
  } catch (e) {
    avisos.error(e)
  }
}

async function lanzar() {
  enviando.value = true
  try {
    const a = await analisis.crear(peticion())
    router.push(`/analisis/${a.codigo}`)
  } catch (e) {
    avisos.error(e, 'No se pudo lanzar el análisis')
  } finally {
    enviando.value = false
  }
}
</script>

<template>
  <div class="pagina estrecha">
    <div class="pagina-cabecera">
      <div>
        <h1>Análisis de competencia</h1>
        <p>Dinos a quién vigilar. Tarda unos minutos y puedes cerrar la pestaña: el avance queda guardado.</p>
      </div>
      <button v-if="guardado" class="boton" type="button" @click="usarGuardado">
        <Icono nombre="historial" /> Usar mi mercado guardado
      </button>
    </div>

    <div v-if="faltaWorker" class="aviso aviso-ambar" role="status">
      <Icono nombre="alerta" />
      <div class="aviso-cuerpo">
        No se pudo hablar con el worker. Ábrelo con <span class="mono">iniciar.bat</span>; sin él no se puede analizar.
      </div>
    </div>

    <form class="pila" @submit.prevent="lanzar">
      <section class="panel pila">
        <h2>Tu mercado</h2>
        <div class="campo">
          <span class="etiqueta">Mis marcas (opcional)</span>
          <div v-for="(m, i) in f.marcas" :key="i" class="fila competidor fila-marca">
            <BuscadorPaginas
              v-model:nombre="m.nombre"
              v-model:paginas="m.paginas"
              :pais="f.pais"
              :etiqueta="`Marca ${i + 1}`"
              placeholder="Ingrese su marca"
              pie="Marca todas las páginas que sean tuyas (sedes, escuelas…)."
            />
            <button class="boton boton-fantasma boton-chico" type="button" :aria-label="`Quitar marca ${i + 1}`" @click="quitarMarca(i)">
              <Icono nombre="x" />
            </button>
          </div>
          <div class="fila">
            <button class="boton boton-chico" type="button" :disabled="f.marcas.length >= 5" @click="agregarMarca">
              <Icono nombre="mas" /> Añadir marca
            </button>
          </div>
          <span class="campo-ayuda">
            Al escribir su nombre aparecen sus páginas de Facebook: marca las tuyas y el informe reconocerá tus anuncios
            por esas páginas, sin adivinar. Si la pones, sus anuncios también se analizan y el informe marca en qué
            territorios ya estás, para compararte. Si no, el análisis es solo de tus competidores.
          </span>
        </div>

        <div class="campo">
          <span class="etiqueta">Competidores</span>
          <template v-for="(c, i) in f.competidores" :key="i">
            <div class="fila competidor">
              <BuscadorPaginas v-model:nombre="c.nombre" v-model:paginas="c.paginas" :pais="f.pais" :etiqueta="`Competidor ${i + 1}`" />
              <select v-model.number="c.nivel" :aria-label="`Nivel de ${c.nombre || 'competidor ' + (i + 1)}`">
                <option v-for="(n, k) in niveles" :key="k" :value="Number(k)" :title="n.desc">{{ k }} · {{ n.nombre }}</option>
              </select>
              <button class="boton boton-fantasma boton-chico" type="button" :aria-label="`Quitar competidor ${i + 1}`" @click="quitar(i)">
                <Icono nombre="x" />
              </button>
            </div>
            <p v-if="(c.paginas?.length ?? 0) > 1" class="una-fila">
              Estas {{ c.paginas!.length }} páginas cuentan como <strong>un solo competidor</strong> («{{ c.nombre }}»), como
              las sedes de un mismo negocio. ¿Son negocios distintos?
              <button class="boton boton-chico" type="button" :disabled="f.competidores.length - 1 + c.paginas!.length > 20" @click="separar(i)">
                Separar en {{ c.paginas!.length }} competidores
              </button>
            </p>
          </template>
          <div class="fila">
            <button class="boton boton-chico" type="button" :disabled="f.competidores.length >= 20" @click="agregar">
              <Icono nombre="mas" /> Añadir competidor
            </button>
          </div>
          <span class="campo-ayuda">
            Al escribir su nombre aparecen sus páginas de Facebook: marca las suyas (sedes, talleres…) y el análisis
            buscará solo sus anuncios, sin adivinar cuál es. También puedes pegar el enlace de su página. El nivel
            decide cuánto pesa en los porcentajes: 1 es el que compite por tu mismo cliente (pesa el doble), 4 el
            nacional (pesa menos de la mitad).
          </span>
        </div>
      </section>

      <section class="panel pila">
        <h2>El sector</h2>
        <div class="campo">
          <label for="referencia">Negocios de referencia</label>
          <input id="referencia" v-model="referenciaTxt" type="text" placeholder="escuela de cocina, instituto de gastronomía" />
          <span class="campo-ayuda">
            El tipo de negocio con el que compites. Junto con tus competidores define el sector: la IA descarta
            tiendas, fabricantes, restaurantes y demás negocios que solo usan las mismas palabras. Separados por comas.
          </span>
        </div>
        <div class="campo">
          <label for="keywords">Palabras clave del mercado (opcional)</label>
          <input id="keywords" v-model="keywordsTxt" type="text" placeholder="curso de cocina lima, estudiar gastronomía" @input="estimar" />
          <span class="campo-ayuda">
            Amplían el análisis a anunciantes que no nombraste (salen como «mercado»). Solo sirven para buscar: de lo
            que traigan, cuentan los negocios del mismo tipo que tus competidores. Cuestan más tiempo y más anuncios por clasificar.
          </span>
        </div>
      </section>

      <section class="panel pila">
        <h2>La búsqueda</h2>
        <div class="formulario-2">
          <div class="campo">
            <label for="pais">País de los anuncios</label>
            <select id="pais" v-model="f.pais">
              <option v-for="p in PAISES" :key="p.codigo" :value="p.codigo">{{ p.nombre }}</option>
            </select>
          </div>
          <div class="campo">
            <label for="maximo">Máximo de anuncios</label>
            <input id="maximo" v-model.number="f.maximo" type="number" min="10" max="500" step="10" />
            <span class="campo-ayuda">Entre 10 y 500. Con menos de 30 los porcentajes son solo orientativos.</span>
          </div>
        </div>
        <label class="casilla"><input v-model="f.soloActivos" type="checkbox" /> Solo anuncios activos ahora</label>
        <div class="campo">
          <label for="fecha-minima">Fecha mínima de inicio (opcional)</label>
          <input id="fecha-minima" v-model="f.fechaMinima" type="date" :max="hoy" :disabled="f.soloActivos" />
          <span class="campo-ayuda">
            Sin los anuncios que empezaron antes y ya terminaron. Los que siguen activos se quedan aunque sean anteriores: son de hoy.
            Con «Solo anuncios activos ahora» no hace falta.
          </span>
        </div>
        <label class="casilla">
          <input v-model="f.conMedios" type="checkbox" />
          La IA mira las imágenes y vídeos
          <span class="tenue chico">(más preciso; sin esto clasifica solo por el texto: más rápido y barato)</span>
        </label>
      </section>

      <section v-if="est" class="panel estimacion" aria-live="polite">
        <h2>Antes de lanzar</h2>
        <p>
          Hasta <strong class="num">{{ est.anuncios }}</strong> anuncios en unas <strong class="num">{{ est.llamadas }}</strong> llamadas a
          la IA, unos <strong class="num">{{ est.minutos }} min</strong>.
        </p>
        <p class="suave chico">
          Costo aproximado: Gemini <strong class="num">{{ usd(est.costoGeminiUsd) }}</strong> (gratis dentro de la cuota
          del plan gratuito)
          <template v-if="conApify"> + Apify <strong class="num">{{ usd(est.costoApifyUsd) }}</strong></template>
          <template v-else>. Los anuncios se leen gratis de la Biblioteca de Meta</template>. El costo real se muestra en el informe.
        </p>
      </section>

      <div class="fila">
        <button class="boton boton-primario" type="submit" :disabled="enviando || !hayAlgo">
          <Icono nombre="radar" /> {{ enviando ? 'Lanzando…' : 'Analizar' }}
        </button>
        <button class="boton" type="button" :disabled="!hayAlgo" @click="guardarMercado">
          <Icono nombre="guardar" /> Guardar mi mercado
        </button>
        <RouterLink to="/informes" class="boton boton-fantasma">Cancelar</RouterLink>
      </div>
    </form>

    <PanelSemanal :peticion="peticion" :hay-algo="hayAlgo" />
  </div>
</template>

<style scoped>
.estrecha {
  max-width: 860px;
}
.competidor {
  flex-wrap: nowrap;
  align-items: flex-start;
}
.competidor select {
  flex: 0 0 160px;
}
.una-fila {
  font-size: 0.82rem;
  color: var(--texto-suave);
  margin: -4px 0 4px;
}
.una-fila .boton {
  margin-left: 6px;
}
.estimacion {
  background: var(--panel-2);
}
@media (max-width: 600px) {
  .competidor {
    flex-wrap: wrap;
  }
  /* El buscador va en su propia línea; el nivel y quitar, debajo. */
  .competidor > .buscador {
    flex-basis: 100%;
  }
  .competidor select {
    flex: 1;
  }
  /* Sin nivel que mostrar, quitar cabe al lado del buscador. */
  .fila-marca {
    flex-wrap: nowrap;
  }
  .fila-marca > .buscador {
    flex-basis: auto;
  }
}
</style>
