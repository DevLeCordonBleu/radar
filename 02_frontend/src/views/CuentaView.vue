<script setup lang="ts">
/** Mi cuenta: nombre, contraseña y código de recuperación. Aquí cae quien entra con una clave temporal. */
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { auth as api } from '@/api/radar'
import Icono from '@/components/Icono.vue'
import SecretoUnaVez from '@/components/SecretoUnaVez.vue'
import { fechaHora } from '@/composables/formato'
import { useAvisos } from '@/stores/avisos'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const avisos = useAvisos()
const router = useRouter()

const nombre = ref(auth.usuario?.nombre ?? '')
const actual = ref('')
const nueva = ref('')
const repetida = ref('')
const secreto = ref('')
const ocupado = ref(false)

async function guardarNombre() {
  ocupado.value = true
  try {
    auth.fijar(await api.cuenta({ nombre: nombre.value }))
    avisos.exito('Nombre actualizado.')
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

async function cambiarClave() {
  if (nueva.value !== repetida.value) {
    avisos.error(new Error('Las dos contraseñas nuevas no coinciden.'), 'Revisa la contraseña')
    return
  }
  const eraTemporal = auth.usuario?.debeCambiar
  ocupado.value = true
  try {
    const r = await api.cuenta({ claveActual: actual.value, claveNueva: nueva.value })
    auth.fijar(r)
    actual.value = nueva.value = repetida.value = ''
    avisos.exito('Contraseña cambiada. Las demás sesiones se han cerrado.')
    if (r.codigoRecuperacion) secreto.value = r.codigoRecuperacion
    else if (eraTemporal) await router.push('/')
  } catch (e) {
    avisos.error(e, 'No se pudo cambiar la contraseña')
  } finally {
    ocupado.value = false
  }
}

async function nuevoCodigo() {
  if (!actual.value) {
    avisos.error(new Error('Escribe tu contraseña actual para generar un código nuevo.'), 'Falta la contraseña')
    return
  }
  ocupado.value = true
  try {
    const r = await api.cuenta({ claveActual: actual.value, nuevoCodigo: true })
    auth.fijar(r)
    actual.value = ''
    secreto.value = r.codigoRecuperacion ?? ''
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

async function cerrarSecreto() {
  secreto.value = ''
  if (!auth.usuario?.debeCambiar) await router.push('/')
}
</script>

<template>
  <div class="pagina estrecha">
    <div class="pagina-cabecera">
      <div>
        <h1>Mi cuenta</h1>
        <p>{{ auth.usuario?.email }} · {{ auth.usuario?.rol === 'admin' ? 'Administrador' : 'Miembro' }}
          <span v-if="auth.usuario?.ultimoAcceso" class="tenue"> · último acceso {{ fechaHora(auth.usuario.ultimoAcceso) }}</span></p>
      </div>
    </div>

    <div v-if="auth.usuario?.debeCambiar" class="aviso aviso-ambar" role="alert">
      <Icono nombre="alerta" />
      <div class="aviso-cuerpo"><strong>Entraste con una contraseña temporal.</strong> Elige la tuya para seguir usando el panel.</div>
    </div>

    <form class="panel pila" @submit.prevent="guardarNombre">
      <h2>Tu nombre</h2>
      <div class="campo">
        <label for="nombre">Nombre</label>
        <input id="nombre" v-model="nombre" type="text" maxlength="80" required />
      </div>
      <div class="fila"><button class="boton" type="submit" :disabled="ocupado || nombre.trim() === auth.usuario?.nombre">Guardar nombre</button></div>
    </form>

    <form class="panel pila" @submit.prevent="cambiarClave">
      <h2>Contraseña</h2>
      <div class="campo">
        <label for="actual">Contraseña actual</label>
        <input id="actual" v-model="actual" type="password" autocomplete="current-password" required />
      </div>
      <div class="formulario-2">
        <div class="campo">
          <label for="nueva">Contraseña nueva</label>
          <input id="nueva" v-model="nueva" type="password" autocomplete="new-password" required />
          <span class="campo-ayuda">Al menos 10 caracteres, sin tu correo dentro.</span>
        </div>
        <div class="campo">
          <label for="repetida">Repítela</label>
          <input id="repetida" v-model="repetida" type="password" autocomplete="new-password" required />
        </div>
      </div>
      <div class="fila"><button class="boton boton-primario" type="submit" :disabled="ocupado">Cambiar contraseña</button></div>
    </form>

    <section v-if="!auth.usuario?.debeCambiar" class="panel pila">
      <h2>Código de recuperación</h2>
      <p class="suave chico">
        {{ auth.usuario?.tieneRecuperacion ? 'Tienes un código guardado.' : 'Aún no tienes código.' }}
        Si lo perdiste, genera uno nuevo (el anterior deja de valer). Pide tu contraseña actual, escrita arriba.
      </p>
      <div class="fila"><button class="boton" type="button" :disabled="ocupado" @click="nuevoCodigo"><Icono nombre="llave" /> Generar código nuevo</button></div>
    </section>

    <SecretoUnaVez
      :abierto="!!secreto"
      titulo="Tu código de recuperación"
      texto="Guárdalo ahora: no se muestra otra vez. Sirve una sola vez para restablecer la contraseña."
      :valor="secreto"
      @cerrar="cerrarSecreto"
    />
  </div>
</template>

<style scoped>
.estrecha {
  max-width: 720px;
}
.panel + .panel {
  margin-top: 16px;
}
.aviso {
  margin-bottom: 16px;
}
</style>
