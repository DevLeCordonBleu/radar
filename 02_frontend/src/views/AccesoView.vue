<script setup lang="ts">
/**
 * Pantalla de acceso. Tres caras según el momento:
 *  - primera vez (no hay cuentas): crear la cuenta de administrador;
 *  - entrar con correo y contraseña;
 *  - «¿Olvidaste la clave?»: correo + código de recuperación + clave nueva.
 */
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { auth as api } from '@/api/radar'
import { mensajeDe } from '@/api/cliente'
import Icono from '@/components/Icono.vue'
import SecretoUnaVez from '@/components/SecretoUnaVez.vue'
import { alternarTema, tema } from '@/composables/tema'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const router = useRouter()
const route = useRoute()

const modo = ref<'entrar' | 'recuperar'>('entrar')
const nombre = ref('')
const email = ref('')
const clave = ref('')
const codigo = ref('')
const error = ref('')
const trabajando = ref(false)
const secreto = ref('')

const alta = computed(() => auth.necesitaAlta)

/** Tras ver el código de recuperación se entra al panel. */
let respuestaPendiente: Parameters<typeof auth.fijar>[0] | null = null

function destino() {
  const v = route.query.vuelta
  return typeof v === 'string' && v.startsWith('/') && !v.startsWith('//') ? v : '/'
}

async function enviar() {
  error.value = ''
  trabajando.value = true
  try {
    if (alta.value) {
      const r = await api.alta(nombre.value, email.value, clave.value)
      respuestaPendiente = r
      secreto.value = r.codigoRecuperacion ?? ''
      if (!secreto.value) await entrarYa()
    } else if (modo.value === 'recuperar') {
      const r = await api.recuperar(email.value, codigo.value, clave.value)
      respuestaPendiente = r
      secreto.value = r.codigoRecuperacion ?? ''
      if (!secreto.value) await entrarYa()
    } else {
      auth.fijar(await api.entrar(email.value, clave.value))
      await router.push(destino())
    }
  } catch (e) {
    error.value = mensajeDe(e)
  } finally {
    trabajando.value = false
  }
}

async function entrarYa() {
  if (respuestaPendiente) auth.fijar(respuestaPendiente)
  secreto.value = ''
  await router.push(destino())
}
</script>

<template>
  <div class="acceso">
    <button class="boton boton-fantasma tema" type="button" :aria-label="tema === 'claro' ? 'Tema oscuro' : 'Tema claro'" @click="alternarTema">
      <Icono :nombre="tema === 'claro' ? 'luna' : 'sol'" />
    </button>

    <form class="tarjeta panel" @submit.prevent="enviar">
      <div class="cabeza">
        <span class="logo" aria-hidden="true"><Icono nombre="radar" /></span>
        <h1>Radar de Anuncios</h1>
        <p class="suave">
          <template v-if="alta">Bienvenida o bienvenido. Crea la cuenta de administrador: será quien dé acceso al equipo.</template>
          <template v-else-if="modo === 'recuperar'">Restablece tu contraseña con el código de recuperación que guardaste al crear tu cuenta.</template>
          <template v-else>Qué anuncia tu competencia, qué repite todo el mundo y dónde está el hueco.</template>
        </p>
      </div>

      <div v-if="alta" class="campo">
        <label for="nombre">Tu nombre</label>
        <input id="nombre" v-model="nombre" type="text" autocomplete="name" required maxlength="80" />
      </div>
      <div class="campo">
        <label for="email">Correo</label>
        <input id="email" v-model="email" type="email" autocomplete="username" required />
      </div>
      <div v-if="modo === 'recuperar' && !alta" class="campo">
        <label for="codigo">Código de recuperación</label>
        <input id="codigo" v-model="codigo" type="text" class="mono" autocomplete="off" placeholder="XXXX-XXXX-XXXX-XXXX-XXXX" required />
      </div>
      <div class="campo">
        <label for="clave">{{ modo === 'recuperar' && !alta ? 'Contraseña nueva' : 'Contraseña' }}</label>
        <input
          id="clave"
          v-model="clave"
          type="password"
          :autocomplete="alta || modo === 'recuperar' ? 'new-password' : 'current-password'"
          required
          maxlength="128"
        />
        <span v-if="alta || modo === 'recuperar'" class="campo-ayuda">Al menos 10 caracteres. Mejor una frase que una palabra.</span>
      </div>

      <div v-if="error" class="aviso aviso-error" role="alert">
        <Icono nombre="error" /><div class="aviso-cuerpo">{{ error }}</div>
      </div>

      <button class="boton boton-primario" type="submit" :disabled="trabajando">
        {{ trabajando ? 'Un momento…' : alta ? 'Crear cuenta y entrar' : modo === 'recuperar' ? 'Restablecer y entrar' : 'Entrar' }}
      </button>

      <button
        v-if="!alta"
        class="boton boton-fantasma"
        type="button"
        @click="((modo = modo === 'entrar' ? 'recuperar' : 'entrar'), (error = ''), (clave = ''))"
      >
        {{ modo === 'entrar' ? '¿Olvidaste la clave?' : 'Volver a entrar' }}
      </button>
    </form>

    <SecretoUnaVez
      :abierto="!!secreto"
      titulo="Guarda tu código de recuperación"
      texto="Es la única forma de volver a entrar si olvidas la contraseña. No se muestra otra vez: guárdalo en un gestor de contraseñas o impreso. Sirve una sola vez."
      :valor="secreto"
      aceptar="Entrar al panel"
      @cerrar="entrarYa"
    />
  </div>
</template>

<style scoped>
.acceso {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px 16px;
  position: relative;
}
.tema {
  position: absolute;
  top: 16px;
  right: 16px;
}
.tarjeta {
  width: min(420px, 100%);
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 28px;
}
.panel + .panel {
  margin-top: 0;
}
.cabeza {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  text-align: center;
  margin-bottom: 6px;
}
.logo {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  border-radius: 12px;
  background: var(--cian);
  color: #fff;
}
.logo svg {
  width: 28px;
  height: 28px;
}
</style>
