<script setup lang="ts">
/**
 * Ajustes = estado del sistema. Las claves (Gemini, Apify) viven en el .env del
 * worker y nunca llegan al navegador: aquí solo se ve si están y si funcionan.
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { sistema } from '@/api/radar'
import type { Comprobacion, Sistema } from '@/api/tipos'
import Icono from '@/components/Icono.vue'
import { usd } from '@/composables/formato'
import { useAvisos } from '@/stores/avisos'

const avisos = useAvisos()
const s = ref<Sistema | null>(null)
const cargando = ref(true)
const comprobando = ref(false)
const resultado = ref<Comprobacion | null>(null)

const w = computed(() => s.value?.worker ?? null)

async function cargar() {
  try {
    s.value = await sistema.estado()
  } catch (e) {
    avisos.error(e)
  } finally {
    cargando.value = false
  }
}
onMounted(cargar)

async function comprobar() {
  comprobando.value = true
  try {
    resultado.value = await sistema.comprobar()
  } catch (e) {
    avisos.error(e)
  } finally {
    comprobando.value = false
  }
}
</script>

<template>
  <div class="pagina estrecha">
    <div class="pagina-cabecera">
      <div>
        <h1>Ajustes</h1>
        <p>Qué está conectado. Las claves se ponen en <span class="mono">03_worker/.env</span> y no salen de tu equipo.</p>
      </div>
    </div>

    <p v-if="cargando" class="cargando suave">Cargando…</p>

    <template v-else>
      <div v-if="!w" class="aviso aviso-error" role="alert">
        <Icono nombre="error" />
        <div class="aviso-cuerpo">
          <strong>El worker no responde.</strong> Sin él no se puede analizar ni abrir el informe de ejemplo. Arráncalo con
          <span class="mono">iniciar.bat</span> (puerto 8102).
        </div>
      </div>

      <section class="panel pila">
        <div class="panel-titulo">
          <h2>Gemini <span class="suave chico">· analiza los anuncios</span></h2>
          <span v-if="w" class="chip" :class="w.gemini.claves ? 'chip-lima' : 'chip-rojo'">
            {{ w.gemini.claves ? `${w.gemini.claves} ${w.gemini.claves === 1 ? 'clave' : 'claves'}` : 'sin clave' }}
          </span>
        </div>
        <template v-if="w">
          <p v-if="!w.gemini.claves" class="suave">
            Falta <span class="mono">GEMINI_API_KEY</span>. Consíguela gratis en
            <a href="https://aistudio.google.com" target="_blank" rel="noopener noreferrer">aistudio.google.com</a>
            → Get API key.
          </p>
          <ul v-else class="lista-plana chico">
            <li v-for="(f, i) in w.gemini.finales.filter(Boolean)" :key="i">
              {{ i === 0 ? 'Principal' : 'De reserva' }}: <span class="mono">…{{ f }}</span>
            </li>
            <li class="suave">Modelos en este orden: {{ w.gemini.modelos.join(' → ') }}</li>
            <li class="suave">
              {{ w.gemini.pago ? 'Facturación activada: sin límite diario.' : 'Plan gratuito: unas 20 peticiones al día por modelo (≈ 5 informes de 100 anuncios al día).' }}
            </li>
          </ul>
        </template>
      </section>

      <section class="panel pila">
        <div class="panel-titulo">
          <h2>Anuncios de Meta <span class="suave chico">· de dónde se descargan</span></h2>
          <span v-if="w?.anuncios" class="chip chip-lima">{{ w.anuncios.fuente === 'navegador' ? 'navegador · gratis' : 'Apify' }}</span>
        </div>
        <template v-if="w">
          <p v-if="w.anuncios?.fuente !== 'apify'" class="suave">
            Radar abre la Biblioteca de Anuncios de Meta con el Chrome de este equipo y lee los anuncios, sin cuenta ni costo.
            Tarda unos segundos por competidor. Si haces muchas búsquedas seguidas, Meta puede frenarlas un rato.
          </p>
          <p v-else class="suave">Se usa el actor de Apify (cuesta crédito de tu cuenta de Apify).</p>
          <p class="tenue chico">
            Opcional: con un <span class="mono">APIFY_TOKEN</span> en <span class="mono">03_worker/.env</span> se usa Apify. Para forzar el
            navegador aunque haya token: <span class="mono">ANUNCIOS_FUENTE=navegador</span>.
          </p>
          <ul v-if="w.apify.tokens" class="lista-plana chico">
            <li v-for="(f, i) in w.apify.finales.filter(Boolean)" :key="i">
              Apify {{ i === 0 ? 'principal' : 'segundo' }}: <span class="mono">…{{ f }}</span>
            </li>
          </ul>
        </template>
      </section>

      <section class="panel pila">
        <div class="panel-titulo">
          <h2>Comprobar las claves</h2>
          <button class="boton" type="button" :disabled="comprobando || !w" @click="comprobar">
            <Icono nombre="aprobar" /> {{ comprobando ? 'Comprobando…' : 'Comprobar ahora' }}
          </button>
        </div>
        <p class="suave chico">Pregunta a Google (y a Apify, si lo usas) si cada clave sigue siendo válida y cuánto crédito queda. No gasta cuota de análisis.</p>
        <template v-if="resultado">
          <ul class="lista-plana resultados">
            <li v-for="(r, i) in resultado.gemini" :key="'g' + i" :class="r.ok ? 'bien' : 'mal'">
              <Icono :nombre="r.ok ? 'ok' : 'error'" /> <span><strong>Gemini {{ i + 1 }}:</strong> {{ r.detalle }}</span>
            </li>
            <li v-for="(r, i) in resultado.apify" :key="'a' + i" :class="r.ok ? 'bien' : 'mal'">
              <Icono :nombre="r.ok ? 'ok' : 'error'" /> <span><strong>Apify {{ i + 1 }}:</strong> {{ r.detalle }}</span>
            </li>
            <li v-if="!resultado.gemini.length && !resultado.apify.length" class="suave">No hay ninguna clave que comprobar.</li>
          </ul>
        </template>
      </section>

      <section class="panel">
        <h2>Gasto de IA este mes</h2>
        <p class="grande num">{{ usd(s?.costoMesUsd ?? 0) }}</p>
        <p class="suave chico">
          Suma el costo medido de cada llamada a Gemini. Con el plan gratuito no se cobra, pero así ves lo que costaría.
          <RouterLink to="/ayuda">Más en Ayuda</RouterLink>.
        </p>
      </section>
    </template>
  </div>
</template>

<style scoped>
.estrecha {
  max-width: 860px;
}
.panel + .panel {
  margin-top: 16px;
}
.resultados {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.resultados li {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.resultados svg {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  margin-top: 3px;
}
.bien svg {
  color: var(--lima);
}
.mal svg {
  color: var(--rojo);
}
.grande {
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--cian);
}
</style>
