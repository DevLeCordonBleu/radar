<script setup lang="ts">
/** KeyWords Explorer · inicio: buscar, retomar búsquedas anteriores, listas y conexión con Google Ads. */
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { keywords } from '@/api/radar'
import type { BusquedaKeywords, ListaKeywords } from '@/api/tipos'
import BuscadorKeywords, { type BusquedaForm } from '@/components/BuscadorKeywords.vue'
import Icono from '@/components/Icono.vue'
import { useEstadoKeywords } from '@/composables/estadoKeywords'
import { fecha } from '@/composables/formato'
import { CAMPOS_GOOGLE_ADS, num } from '@/composables/keywords'
import { useAvisos } from '@/stores/avisos'
import { useAuth } from '@/stores/auth'

const router = useRouter()
const avisos = useAvisos()
const auth = useAuth()
const { estado, cargar, conectado } = useEstadoKeywords()

const busquedas = ref<BusquedaKeywords[]>([])
const listas = ref<ListaKeywords[]>([])
const comprobando = ref(false)
const resultadoConexion = ref<{ ok: boolean; detalle: string } | null>(null)
const guiaAbierta = ref(false)

const ga = computed(() => estado.value?.google_ads)
const paises = computed(() => estado.value?.paises ?? {})

onMounted(async () => {
  await cargar(true)
  guiaAbierta.value = !conectado.value
  try {
    ;[busquedas.value, listas.value] = await Promise.all([keywords.busquedas(), keywords.listas()])
  } catch (e) {
    avisos.error(e, 'No se pudo cargar el historial')
  }
})

function buscar(b: BusquedaForm) {
  router.push({
    name: 'keywords-resultados',
    query: { q: b.semillas, url: b.url ?? undefined, pais: b.pais, idioma: b.idioma, demo: b.demo ? '1' : undefined },
  })
}

async function comprobar() {
  comprobando.value = true
  try {
    resultadoConexion.value = await keywords.comprobar()
  } catch (e) {
    avisos.error(e)
  } finally {
    comprobando.value = false
  }
}

async function borrar(b: BusquedaKeywords) {
  try {
    await keywords.borrarBusqueda(b.codigo)
    busquedas.value = busquedas.value.filter((x) => x.codigo !== b.codigo)
  } catch (e) {
    avisos.error(e)
  }
}

const titulo = (b: BusquedaKeywords) => (b.semillas.length ? b.semillas.join(', ') : (b.url ?? '(sin palabras)'))
</script>

<template>
  <div class="pagina">
    <div class="pagina-cabecera">
      <div>
        <h1>KeyWords Explorer</h1>
        <p>Descubre qué busca la gente en Google: volumen mensual, tendencia, costo por clic, competencia y miles de ideas relacionadas.</p>
      </div>
      <RouterLink to="/keywords/listas" class="boton"><Icono nombre="lista" /> Mis listas</RouterLink>
    </div>

    <section class="panel hero">
      <BuscadorKeywords @buscar="buscar" />
    </section>

    <div v-if="estado && !conectado" class="aviso aviso-ambar" role="status">
      <Icono nombre="alerta" />
      <div class="aviso-cuerpo">
        <strong>Google Ads no está conectado.</strong> Puedes explorar con datos de demostración (inventados, para ver cómo funciona), pero para volúmenes
        reales hay que conectar una cuenta. Es gratis. <button class="enlace-boton" type="button" @click="guiaAbierta = true">Ver cómo conectarlo</button>
      </div>
    </div>

    <div class="rejilla rejilla-2 dos">
      <section class="panel">
        <div class="panel-titulo"><h2>Búsquedas recientes</h2></div>
        <p v-if="!busquedas.length" class="suave chico">Todavía no has buscado nada. Escribe una palabra arriba para empezar.</p>
        <ul v-else class="lista-plana historial">
          <li v-for="b in busquedas.slice(0, 12)" :key="b.codigo">
            <RouterLink :to="{ name: 'keywords-resultados', query: { cod: b.codigo } }" class="item">
              <strong>{{ titulo(b) }}</strong>
              <span class="tenue chico num">
                {{ paises[b.pais] ?? b.pais }} · {{ num(b.totalKeywords) }} keywords · {{ fecha(b.fecha) }}
                <span v-if="b.demo" class="chip chip-ambar">demo</span>
              </span>
            </RouterLink>
            <button class="boton boton-fantasma boton-chico" type="button" :aria-label="`Quitar «${titulo(b)}» del historial`" @click="borrar(b)"><Icono nombre="x" /></button>
          </li>
        </ul>
      </section>

      <section class="panel">
        <div class="panel-titulo"><h2>Mis listas</h2><RouterLink to="/keywords/listas" class="chico">ver todas</RouterLink></div>
        <p v-if="!listas.length" class="suave chico">Selecciona keywords en los resultados y guárdalas en una lista para volver a ellas, ponerles notas o exportarlas.</p>
        <ul v-else class="lista-plana historial">
          <li v-for="l in listas.slice(0, 8)" :key="l.codigo">
            <RouterLink :to="`/keywords/listas/${l.codigo}`" class="item">
              <strong>{{ l.nombre }}</strong>
              <span class="tenue chico num">{{ l.keywords }} keywords · {{ num(l.volumenTotal) }} búsquedas/mes <span v-if="l.demo" class="chip chip-ambar">demo</span></span>
            </RouterLink>
          </li>
        </ul>
      </section>
    </div>

    <section class="panel conexion">
      <div class="panel-titulo">
        <h2><Icono nombre="servidor" /> Conexión con Google Ads</h2>
        <span class="chip" :class="conectado ? 'chip-lima' : 'chip-ambar'">{{ conectado ? 'conectado' : 'sin conectar' }}</span>
      </div>
      <p v-if="conectado" class="suave">
        Cuenta …{{ ga?.cuenta }} · API {{ ga?.version }}{{ ga?.con_manager ? ' · vía cuenta administradora' : '' }}.
        Los datos son los de Google Keyword Planner.
      </p>
      <template v-else>
        <p class="suave">Faltan estos datos en <span class="mono">03_worker/.env</span>:</p>
        <ul class="lista-plana faltan">
          <li v-for="f in ga?.faltan ?? []" :key="f"><Icono nombre="x" /> {{ CAMPOS_GOOGLE_ADS[f] ?? f }}</li>
        </ul>
      </template>

      <div v-if="auth.esAdmin" class="fila">
        <button class="boton" type="button" :disabled="comprobando" @click="comprobar"><Icono nombre="aprobar" /> {{ comprobando ? 'Comprobando…' : 'Comprobar conexión' }}</button>
        <span v-if="resultadoConexion" class="chico" :class="resultadoConexion.ok ? 'bien' : 'mal'">{{ resultadoConexion.detalle }}</span>
      </div>

      <details :open="guiaAbierta" class="guia" @toggle="guiaAbierta = ($event.target as HTMLDetailsElement).open">
        <summary>Cómo conectar Google Ads, paso a paso (gratis, unos 20 minutos)</summary>
        <ol>
          <li>
            <strong>Una cuenta de Google Ads.</strong> Si no tienes, créala en ads.google.com y completa la configuración inicial (puedes saltarte crear
            una campaña). <em>No hace falta invertir</em>, pero sin anuncios activos Google puede devolver volúmenes agrupados (10, 100, 1.000…).
          </li>
          <li>
            <strong>Developer token.</strong> En una cuenta administradora (MCC): Herramientas → Configuración → Centro de API. Solicita acceso
            <em>Básico</em>. Un token en modo «prueba» solo funciona con cuentas de prueba. Cópialo en <span class="mono">GOOGLE_ADS_DEVELOPER_TOKEN</span>.
          </li>
          <li>
            <strong>Credenciales OAuth.</strong> En console.cloud.google.com crea un proyecto, habilita la <em>Google Ads API</em> y crea un
            <em>ID de cliente de OAuth</em> de tipo «Aplicación de escritorio». En la pantalla de consentimiento añade tu correo como usuario de prueba.
            Copia el ID y el secreto en <span class="mono">GOOGLE_ADS_CLIENT_ID</span> y <span class="mono">GOOGLE_ADS_CLIENT_SECRET</span>.
          </li>
          <li>
            <strong>La cuenta.</strong> Pon el número de tu cuenta de Google Ads (10 dígitos) en <span class="mono">GOOGLE_ADS_CUSTOMER_ID</span>. Si entras
            a ella a través de una cuenta administradora, pon el número de esa en <span class="mono">GOOGLE_ADS_LOGIN_CUSTOMER_ID</span>.
          </li>
          <li>
            <strong>Autoriza.</strong> En una terminal: <span class="mono">cd 03_worker</span> y <span class="mono">python -m app.keywords.autorizar</span>.
            Se abre el navegador, das permiso y el refresh token se guarda solo en el .env.
          </li>
          <li><strong>Reinicia el worker</strong> (iniciar.bat) y pulsa «Comprobar conexión».</li>
        </ol>
      </details>
    </section>

    <section class="panel limites">
      <h2>Qué mide este módulo y qué no</h2>
      <p class="suave chico">
        Los datos vienen de <strong>Google Keyword Planner</strong>: volumen mensual y tendencia de 12 meses, puja (CPC) y competencia entre anunciantes.
        <strong>No incluye</strong> la dificultad orgánica (KD), los clics, la SERP ni el potencial de tráfico: eso es de Ahrefs y requiere su propio
        índice. La <em>intención</em> de búsqueda y los términos «coincidentes / relacionados» se calculan aquí con reglas, y sirven para filtrar, no son una verdad.
      </p>
    </section>
  </div>
</template>

<style scoped>
.hero {
  margin-bottom: 16px;
  padding: 22px;
}
.dos {
  margin: 16px 0;
}
.panel + .panel {
  margin-top: 0;
}
.conexion,
.limites {
  margin-top: 16px;
}
.historial {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.historial li {
  display: flex;
  align-items: center;
  gap: 6px;
}
.item {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 8px 10px;
  border-radius: var(--radio-chico);
  color: var(--texto);
}
.item:hover {
  background: var(--panel-2);
  text-decoration: none;
}
.item strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.faltan li {
  display: flex;
  gap: 8px;
  align-items: center;
  color: var(--ambar);
  font-size: 0.9rem;
}
.faltan svg {
  width: 14px;
  height: 14px;
}
.conexion .fila {
  margin: 12px 0;
}
.bien {
  color: var(--lima);
}
.mal {
  color: var(--rojo);
}
.guia {
  margin-top: 8px;
  border-top: 1px solid var(--borde);
  padding-top: 10px;
}
.guia summary {
  cursor: pointer;
  font-weight: 600;
}
.guia ol {
  margin: 12px 0 0 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  color: var(--texto-suave);
}
.enlace-boton {
  background: none;
  border: 0;
  color: var(--cian);
  font: inherit;
  text-decoration: underline;
  cursor: pointer;
  padding: 0;
}
h2 svg {
  width: 18px;
  height: 18px;
  vertical-align: -3px;
}
</style>
