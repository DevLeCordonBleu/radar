<script setup lang="ts">
/**
 * Search Console de la web propia: por qué búsquedas ya aparece en Google, con cifras
 * reales. Sirve para no escribir lo que ya posiciona y para ver qué páginas conviene
 * mejorar (posición 4-20, sin búsquedas de marca). Solo ve búsquedas donde la web ya aparece.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { seo } from '@/api/radar'
import type { ComprobacionGsc, SearchConsoleSeo } from '@/api/tipos'
import ConectarGoogle from '@/components/ConectarGoogle.vue'
import Icono from '@/components/Icono.vue'
import MejoraPagina from '@/components/MejoraPagina.vue'
import InformesGuardados from '@/components/InformesGuardados.vue'
import TerminosProtegidos from '@/components/TerminosProtegidos.vue'
import { fecha, fechaHora } from '@/composables/formato'
import { useAuth } from '@/stores/auth'
import { useAvisos } from '@/stores/avisos'

const auth = useAuth()
const avisos = useAvisos()
const estado = ref<SearchConsoleSeo | null>(null)
const prueba = ref<ComprobacionGsc | null>(null)
const ocupado = ref(false)
const entero = new Intl.NumberFormat('es-PE')

const conectado = computed(() => !!estado.value?.configuracion.completo)
const sinc = computed(() => estado.value?.sincronizacion ?? null)

async function cargar() {
  try {
    estado.value = await seo.searchConsole()
  } catch (e) {
    avisos.error(e)
  }
}
onMounted(cargar)

async function comprobar() {
  ocupado.value = true
  try {
    prueba.value = await seo.comprobarSearchConsole()
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

async function sincronizar() {
  ocupado.value = true
  try {
    estado.value = await seo.sincronizarSearchConsole()
    avisos.exito(`Search Console: ${entero.format(estado.value.sincronizacion?.filas ?? 0)} filas de consultas.`)
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

/** Fechas sin hora (AAAA-MM-DD): a mediodía, para que la zona horaria no las mueva de día. */
const dia = (iso: string) => fecha(`${iso}T12:00:00`)

// Palabras de marca: se editan como texto separado por comas.
const marcaTexto = ref('')
watch(
  () => estado.value?.marca,
  (m) => (marcaTexto.value = (m ?? []).join(', ')),
)
const marcaNueva = computed(() =>
  marcaTexto.value
    .split(',')
    .map((p) => p.trim())
    .filter(Boolean),
)
const marcaCambiada = computed(() => marcaNueva.value.join('|') !== (estado.value?.marca ?? []).join('|'))

async function guardarMarca() {
  ocupado.value = true
  try {
    estado.value = await seo.guardarMarca(marcaNueva.value)
    avisos.exito('Palabras de marca guardadas.')
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}
</script>

<template>
  <section class="panel gsc" aria-labelledby="titulo-gsc">
    <header class="cabeza">
      <div>
        <h2 id="titulo-gsc">
          <Icono nombre="buscar" /> Search Console de tu web
          <span v-if="estado" class="chip" :class="conectado ? 'chip-lima' : ''">{{ conectado ? 'Conectado' : 'Sin conectar' }}</span>
        </h2>
        <p class="chico suave">
          Por qué búsquedas ya apareces en Google, con clics, impresiones y posición reales. El flujo automático lo usa para no
          escribir lo que ya posicionas.
        </p>
        <p v-if="sinc" class="chico">
          {{ sinc.propiedad }} · del {{ dia(sinc.desde) }} al {{ dia(sinc.hasta) }}<template v-if="sinc.pais">
            · búsquedas desde {{ sinc.pais.toUpperCase() }}</template> · actualizado {{ fechaHora(sinc.fecha) }}
        </p>
      </div>
      <div v-if="conectado" class="fila">
        <button class="boton" type="button" :disabled="ocupado" @click="comprobar"><Icono nombre="ok" /> Comprobar acceso</button>
        <button class="boton boton-primario" type="button" :disabled="ocupado" @click="sincronizar">
          <Icono nombre="reintentar" /> {{ ocupado ? 'Trayendo…' : 'Traer últimos 90 días' }}
        </button>
      </div>
    </header>

    <!-- Sin conectar: qué falta -->
    <div v-if="estado && !conectado" class="pasos-gsc chico">
      <p v-if="estado.configuracion.error" class="ambar">{{ estado.configuracion.error }}</p>
      <ol>
        <li>Quien administra Search Console de tu web te agrega como usuario con permiso <strong>Restringido</strong> (solo lectura).</li>
        <li>
          En <code>03_worker/.env</code>: <code>GSC_PROPIEDAD</code> (p. ej. <code>sc-domain:ilcb.edu.pe</code>) y las credenciales de
          Google (<code>GOOGLE_ADS_CLIENT_ID</code> y <code>GOOGLE_ADS_CLIENT_SECRET</code>, las mismas de Google Ads).
        </li>
        <li>Conectar Google con el botón de abajo (pide Google Ads, Search Console y Analytics).</li>
      </ol>
      <p v-if="estado.configuracion.faltan.length" class="tenue">Falta: {{ estado.configuracion.faltan.join(', ') }}</p>
    </div>

    <ConectarGoogle @conectado="cargar" />

    <!-- Comprobación -->
    <p v-if="prueba" class="chico" :class="prueba.ok ? '' : 'ambar'">
      <template v-if="prueba.ok">Acceso correcto a {{ prueba.propiedad }} (permiso {{ prueba.permiso }}).</template>
      <template v-else>
        Tu cuenta no tiene acceso a {{ prueba.propiedad }}.
        <template v-if="prueba.propiedades.length">Ve: {{ prueba.propiedades.map((p) => p.propiedad).join(', ') }}.</template>
      </template>
    </p>

    <!-- Datos -->
    <template v-if="sinc">
      <dl class="cifras">
        <div><dt>Búsquedas</dt><dd>{{ entero.format(estado!.resumen.consultas) }}</dd></div>
        <div><dt>Clics</dt><dd>{{ entero.format(estado!.resumen.clics) }}</dd></div>
        <div><dt>Impresiones</dt><dd>{{ entero.format(estado!.resumen.impresiones) }}</dd></div>
      </dl>
      <h3>Páginas para mejorar</h3>
      <p class="chico suave">
        Páginas que Google ya muestra entre la <strong>posición 4 y 20</strong> para búsquedas sin marca (al menos 30 impresiones),
        de más a menos impresiones. Subir de la 9 a la 3 suele traer más visitas que un artículo nuevo. La IA propone título,
        descripción y cambios en el texto (lo que dice ahora y lo que debe decir); tú los aplicas en WordPress.
      </p>
      <details class="chico marca">
        <summary>Búsquedas de marca excluidas ({{ estado!.marca.length }} palabras)</summary>
        <p class="tenue">Una búsqueda que contiene alguna de estas palabras la hace quien ya conoce la marca: no dice nada del contenido.</p>
        <form v-if="auth.esAdmin" class="fila" @submit.prevent="guardarMarca">
          <input v-model="marcaTexto" type="text" aria-label="Palabras de marca, separadas por comas" :disabled="ocupado" />
          <button class="boton" type="submit" :disabled="ocupado || !marcaCambiada"><Icono nombre="guardar" /> Guardar</button>
        </form>
        <p v-else>{{ estado!.marca.join(', ') }}</p>
      </details>
      <TerminosProtegidos :terminos="estado!.terminos" @guardado="(e) => (estado = e)" />
      <div v-if="estado!.oportunidades.length" class="oportunidades">
        <MejoraPagina v-for="o in estado!.oportunidades" :key="o.url" :oportunidad="o" @cambio="(m) => (o.mejora = m)" />
      </div>
      <p v-else class="chico">Ninguna búsqueda sin marca con al menos 30 impresiones entre la posición 4 y 20.</p>
    </template>
    <p v-else-if="conectado" class="chico">Conectado, pero aún sin datos: pulsa «Traer últimos 90 días».</p>
    <InformesGuardados
      v-if="estado"
      modulo="SEARCH_CONSOLE"
      :version="sinc?.fecha"
      :en-uso="sinc?.informe ?? null"
      @restaurado="(e) => (estado = e)"
    />
  </section>
</template>

<style scoped>
.gsc svg {
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
.cabeza .fila {
  gap: 8px;
  flex-wrap: wrap;
}
h3 {
  font-size: 0.95rem;
  margin: 16px 0 4px;
}
.pasos-gsc ol {
  margin: 10px 0 0 18px;
  display: grid;
  gap: 4px;
}
.pasos-gsc code {
  overflow-wrap: anywhere;
}
.cifras {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
  margin: 14px 0 0;
}
.cifras div {
  border: 1px solid var(--borde);
  border-radius: var(--radio);
  padding: 8px 12px;
}
.cifras dt {
  font-size: 0.78rem;
  color: var(--texto-suave);
}
.cifras dd {
  margin: 2px 0 0;
  font-size: 1.15rem;
  font-weight: 700;
}
.marca {
  margin: 8px 0 12px;
}
.marca p {
  margin: 4px 0;
}
.marca form {
  gap: 8px;
  margin-top: 6px;
}
.marca input {
  flex: 1;
  min-width: 0;
}
.oportunidades {
  display: grid;
  gap: 12px;
}
.ambar {
  color: var(--ambar);
}
</style>
