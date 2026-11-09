<script setup lang="ts">
/**
 * Informe semanal: repite el análisis del formulario cada semana, el día y la hora elegidos
 * (hora de Lima). Solo un admin lo programa. El backend lo revisa cada 5 minutos, así que solo
 * corre con el Radar abierto. Recuerda las páginas que la persona elige cuando un nombre es
 * ambiguo y reintenta solo una pausa por cuota de Gemini.
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { analisis } from '@/api/radar'
import type { AnalisisSemanal, Peticion } from '@/api/tipos'
import Icono from '@/components/Icono.vue'
import { confirmar } from '@/composables/confirmar'
import { PAISES, fechaHora } from '@/composables/formato'
import { useAuth } from '@/stores/auth'
import { useAvisos } from '@/stores/avisos'

const props = defineProps<{ peticion: () => Peticion; hayAlgo: boolean }>()
const auth = useAuth()
const avisos = useAvisos()

const estado = ref<AnalisisSemanal | null>(null)
const f = ref({ dia: 1, hora: '08:00' })
const ocupado = ref(false)

const DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
const ESTADO: Record<string, { texto: string; chip: string }> = {
  en_cola: { texto: 'en cola', chip: 'chip-cian' },
  corriendo: { texto: 'en marcha', chip: 'chip-cian' },
  pausado: { texto: 'en pausa', chip: 'chip-ambar' },
  terminado: { texto: 'terminado', chip: 'chip-lima' },
  cancelado: { texto: 'cancelado', chip: '' },
}

async function cargar() {
  try {
    const e = await analisis.semanal()
    estado.value = e
    f.value = { dia: e.dia, hora: e.hora }
  } catch (e) {
    avisos.error(e)
  }
}
onMounted(cargar)

const programado = computed(() => {
  const p = estado.value?.peticion
  if (!p) return ''
  const nombres = p.competidores.map((c) => c.nombre)
  const pais = PAISES.find((x) => x.codigo === p.pais)?.nombre ?? p.pais
  const lista = nombres.length > 4 ? `${nombres.slice(0, 4).join(', ')} y ${nombres.length - 4} más` : nombres.join(', ')
  return `${lista || 'palabras clave del sector'} · ${pais} · hasta ${p.maximo} anuncios`
})
const horario = computed(() => `cada ${DIAS[f.value.dia - 1]} a las ${f.value.hora} (hora de Lima)`)
const cambioHorario = computed(() => !!estado.value && (f.value.dia !== estado.value.dia || f.value.hora !== estado.value.hora))
const ultimo = computed(() => estado.value?.analisis ?? null)

async function enviar(cuerpo: Parameters<typeof analisis.programarSemanal>[0], exito: string) {
  ocupado.value = true
  try {
    estado.value = await analisis.programarSemanal(cuerpo)
    f.value = { dia: estado.value.dia, hora: estado.value.hora }
    avisos.exito(exito)
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

async function programar() {
  const r = await confirmar({
    titulo: '¿Programar el informe semanal?',
    mensaje: `Repetirá este análisis ${horario.value} y dejará un informe nuevo en «Informes».`,
    puntos: [
      'Usa los competidores, el sector y la búsqueda que hay ahora en este formulario.',
      'Gasta lo mismo que lanzarlo a mano cada semana (Gemini, gratis dentro de la cuota diaria).',
      'Si Gemini se queda sin cuota, lo reintenta solo cada 3 horas, hasta 4 veces.',
    ],
    aceptar: 'Programar',
  })
  if (r.ok) await enviar({ activo: true, ...f.value, peticion: props.peticion() }, 'Informe semanal programado.')
}
</script>

<template>
  <section class="panel pila semanal" aria-labelledby="titulo-semanal">
    <header>
      <h2 id="titulo-semanal">
        <Icono nombre="reloj" /> Informe semanal
        <span v-if="estado" class="chip" :class="estado.activo ? 'chip-lima' : ''">{{ estado.activo ? 'Programado' : 'Desactivado' }}</span>
      </h2>
      <p v-if="estado?.activo" class="chico">
        Analiza <strong>{{ programado }}</strong>, cada {{ DIAS[estado.dia - 1] }} a las {{ estado.hora }} (hora de Lima).
      </p>
      <p v-else class="chico suave">Repite este análisis cada semana y deja un informe nuevo, sin lanzarlo a mano.</p>
      <p v-if="estado?.activo && estado.proxima" class="chico">
        <Icono nombre="calendario" /> Próximo: <strong>{{ fechaHora(estado.proxima) }}</strong>
      </p>
      <p v-if="ultimo" class="chico">
        Último:
        <RouterLink :to="`/analisis/${ultimo.codigo}`">{{ fechaHora(ultimo.creado) }}</RouterLink>
        <span class="chip" :class="ESTADO[ultimo.estado]?.chip">{{ ESTADO[ultimo.estado]?.texto ?? ultimo.estado }}</span>
        <template v-if="ultimo.pendiente"> · espera que elijas la página de «{{ ultimo.pendiente.competidor }}»</template>
        <RouterLink v-if="ultimo.codInforme" :to="`/informes/${ultimo.codInforme}`"> · Ver informe</RouterLink>
      </p>
    </header>

    <div v-if="auth.esAdmin" class="programa">
      <div class="campo">
        <label for="semanal-dia">Día</label>
        <select id="semanal-dia" v-model.number="f.dia" :disabled="ocupado">
          <option v-for="(d, i) in DIAS" :key="d" :value="i + 1">{{ d }}</option>
        </select>
      </div>
      <div class="campo">
        <label for="semanal-hora">Hora (Lima)</label>
        <input id="semanal-hora" v-model="f.hora" type="time" required :disabled="ocupado" />
      </div>
      <div class="fila acciones">
        <button
          class="boton boton-primario"
          type="button"
          :disabled="ocupado || !hayAlgo"
          :title="hayAlgo ? '' : 'Indica primero tus competidores o palabras clave'"
          @click="programar"
        >
          <Icono nombre="calendario" /> {{ estado?.activo ? 'Reprogramar con este formulario' : 'Programar con este formulario' }}
        </button>
        <button
          v-if="estado?.activo && cambioHorario"
          class="boton"
          type="button"
          :disabled="ocupado"
          @click="enviar({ ...f }, 'Día y hora guardados.')"
        >
          <Icono nombre="guardar" /> Guardar solo día y hora
        </button>
        <button v-if="estado?.activo" class="boton boton-fantasma" type="button" :disabled="ocupado" @click="enviar({ activo: false }, 'Informe semanal desactivado.')">
          Desactivar
        </button>
      </div>
    </div>
    <p v-else class="chico">Solo un administrador cambia la programación.</p>

    <p class="chico tenue">
      Solo corre con el Radar abierto: si a esa hora está cerrado, corre al abrirlo. Si el nombre de un competidor encaja con
      varias páginas, la primera vez te pregunta; desde entonces recuerda la que elegiste. Evita el mismo día que el flujo del
      Plan SEO: los dos usan la cuota diaria de Gemini.
    </p>
  </section>
</template>

<style scoped>
/* Icono no trae tamaño propio: sin esto, dentro de un flex ocupa todo el ancho. */
.semanal svg {
  width: 15px;
  height: 15px;
  vertical-align: -2px;
}
.semanal h2 {
  font-size: 1.05rem;
  margin: 0 0 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.semanal header p {
  margin: 2px 0 0;
}
.programa {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px;
}
.programa .campo {
  flex: 0 0 160px;
}
.acciones {
  flex: 1 1 auto;
}
@media (max-width: 600px) {
  .programa .campo {
    flex: 1 1 140px;
  }
}
</style>
