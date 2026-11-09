<script setup lang="ts">
/** Usuarios (solo administradores): dar acceso al equipo, cambiar roles, desactivar y revisar la actividad. */
import { onMounted, ref } from 'vue'
import { usuarios } from '@/api/radar'
import type { EventoAuditoria, Rol, Usuario } from '@/api/tipos'
import Icono from '@/components/Icono.vue'
import SecretoUnaVez from '@/components/SecretoUnaVez.vue'
import { confirmar } from '@/composables/confirmar'
import { fechaHora } from '@/composables/formato'
import { useAvisos } from '@/stores/avisos'
import { useAuth } from '@/stores/auth'

const avisos = useAvisos()
const auth = useAuth()

const lista = ref<Usuario[]>([])
const eventos = ref<EventoAuditoria[]>([])
const cargando = ref(true)
const nuevo = ref({ nombre: '', email: '', rol: 'miembro' as Rol })
const creando = ref(false)
const temporal = ref<{ para: string; clave: string } | null>(null)

const ACCIONES: Record<string, string> = {
  alta_inicial: 'creó la cuenta inicial',
  entrar: 'entró',
  entrar_fallido: 'intento fallido de entrar',
  cuenta_bloqueada: 'cuenta bloqueada por intentos fallidos',
  cambiar_clave: 'cambió su contraseña',
  nuevo_codigo: 'generó un código de recuperación',
  recuperar: 'restableció su contraseña con el código',
  crear_usuario: 'creó a',
  cambiar_rol: 'cambió el rol de',
  activar_usuario: 'activó a',
  desactivar_usuario: 'desactivó a',
  reiniciar_clave: 'reinició la contraseña de',
  borrar_usuario: 'borró a',
}

async function cargar() {
  try {
    ;[lista.value, eventos.value] = await Promise.all([usuarios.listar(), usuarios.auditoria()])
  } catch (e) {
    avisos.error(e)
  } finally {
    cargando.value = false
  }
}
onMounted(cargar)

async function crear() {
  creando.value = true
  try {
    const r = await usuarios.crear(nuevo.value.nombre, nuevo.value.email, nuevo.value.rol)
    temporal.value = { para: r.usuario.nombre, clave: r.claveTemporal }
    nuevo.value = { nombre: '', email: '', rol: 'miembro' }
    await cargar()
  } catch (e) {
    avisos.error(e, 'No se pudo crear el usuario')
  } finally {
    creando.value = false
  }
}

async function cambiar(u: Usuario, c: { rol?: Rol; activo?: boolean }) {
  try {
    await usuarios.cambiar(u.codigo, c)
    await cargar()
  } catch (e) {
    avisos.error(e)
    await cargar()
  }
}

async function desactivar(u: Usuario) {
  const r = await confirmar({
    titulo: `¿Desactivar a ${u.nombre}?`,
    mensaje: 'Se le cierra la sesión y no podrá entrar hasta que lo reactives. Sus informes se conservan.',
    aceptar: 'Desactivar',
    tono: 'aviso',
  })
  if (r.ok) await cambiar(u, { activo: false })
}

async function reiniciar(u: Usuario) {
  const r = await confirmar({
    titulo: `¿Reiniciar la contraseña de ${u.nombre}?`,
    mensaje: 'Se genera una contraseña temporal y se cierran sus sesiones. La cambiará al entrar.',
    aceptar: 'Reiniciar',
    tono: 'aviso',
  })
  if (!r.ok) return
  try {
    const x = await usuarios.reiniciarClave(u.codigo)
    temporal.value = { para: x.usuario.nombre, clave: x.claveTemporal }
    await cargar()
  } catch (e) {
    avisos.error(e)
  }
}

async function borrar(u: Usuario) {
  const r = await confirmar({ titulo: `¿Borrar a ${u.nombre}?`, mensaje: 'Se elimina la cuenta. Esto no se puede deshacer.', aceptar: 'Borrar', tono: 'peligro' })
  if (!r.ok) return
  try {
    await usuarios.borrar(u.codigo)
    await cargar()
  } catch (e) {
    avisos.error(e)
  }
}

const frase = (e: EventoAuditoria) =>
  `${e.actor ?? 'Alguien'} ${ACCIONES[e.accion] ?? e.accion}${e.objetivo_nombre && e.objetivo !== undefined && !['entrar', 'cambiar_clave', 'nuevo_codigo', 'recuperar', 'alta_inicial'].includes(e.accion) ? ' ' + e.objetivo_nombre : ''}`
</script>

<template>
  <div class="pagina">
    <div class="pagina-cabecera">
      <div>
        <h1>Usuarios</h1>
        <p>Quién tiene acceso. Los administradores gestionan usuarios y claves; los miembros analizan y leen informes.</p>
      </div>
    </div>

    <p v-if="cargando" class="cargando suave">Cargando…</p>

    <template v-else>
      <section class="panel">
        <div class="panel-titulo"><h2>Equipo</h2><span class="tenue chico num">{{ lista.length }} {{ lista.length === 1 ? "cuenta" : "cuentas" }}</span></div>
        <div class="tabla-envoltura">
          <table class="tabla">
            <thead>
              <tr><th>Nombre</th><th>Rol</th><th>Último acceso</th><th>Estado</th><th><span class="oculto-visual">Acciones</span></th></tr>
            </thead>
            <tbody>
              <tr v-for="u in lista" :key="u.codigo" :class="{ inactivo: !u.activo }">
                <td>
                  <strong>{{ u.nombre }}</strong> <span v-if="u.codigo === auth.usuario?.codigo" class="chip chip-cian">tú</span><br />
                  <span class="tenue chico">{{ u.email }}</span>
                </td>
                <td>
                  <select
                    :value="u.rol"
                    :aria-label="`Rol de ${u.nombre}`"
                    :disabled="u.codigo === auth.usuario?.codigo"
                    @change="cambiar(u, { rol: ($event.target as HTMLSelectElement).value as Rol })"
                  >
                    <option value="admin">Administrador</option>
                    <option value="miembro">Miembro</option>
                  </select>
                </td>
                <td class="num suave chico">{{ u.ultimoAcceso ? fechaHora(u.ultimoAcceso) : 'nunca' }}</td>
                <td>
                  <span v-if="!u.activo" class="chip chip-rojo">desactivado</span>
                  <span v-else-if="u.debeCambiar" class="chip chip-ambar">clave temporal</span>
                  <span v-else class="chip chip-lima">activo</span>
                </td>
                <td class="acciones">
                  <button class="boton boton-chico boton-fantasma" type="button" @click="reiniciar(u)">Reiniciar clave</button>
                  <button v-if="u.activo && u.codigo !== auth.usuario?.codigo" class="boton boton-chico boton-fantasma" type="button" @click="desactivar(u)">Desactivar</button>
                  <button v-if="!u.activo" class="boton boton-chico boton-fantasma" type="button" @click="cambiar(u, { activo: true })">Activar</button>
                  <button
                    v-if="u.codigo !== auth.usuario?.codigo"
                    class="boton boton-chico boton-fantasma"
                    type="button"
                    :aria-label="`Borrar a ${u.nombre}`"
                    @click="borrar(u)"
                  ><Icono nombre="basura" /></button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <form class="panel pila nuevo" @submit.prevent="crear">
        <h2>Nuevo usuario</h2>
        <p class="suave chico">Se crea con una contraseña temporal, que verás una sola vez para pasársela. La cambiará la primera vez que entre.</p>
        <div class="formulario-2">
          <div class="campo"><label for="u-nombre">Nombre</label><input id="u-nombre" v-model="nuevo.nombre" type="text" required maxlength="80" /></div>
          <div class="campo"><label for="u-email">Correo</label><input id="u-email" v-model="nuevo.email" type="email" required /></div>
        </div>
        <div class="campo">
          <label for="u-rol">Rol</label>
          <select id="u-rol" v-model="nuevo.rol">
            <option value="miembro">Miembro: analiza y lee informes</option>
            <option value="admin">Administrador: además gestiona usuarios y claves</option>
          </select>
        </div>
        <div class="fila"><button class="boton boton-primario" type="submit" :disabled="creando"><Icono nombre="mas" /> Crear usuario</button></div>
      </form>

      <section class="panel">
        <div class="panel-titulo"><h2>Actividad reciente</h2></div>
        <p v-if="!eventos.length" class="suave chico">Todavía no hay actividad.</p>
        <ul v-else class="lista-plana actividad">
          <li v-for="(e, i) in eventos.slice(0, 30)" :key="i">
            <span class="tenue chico num">{{ fechaHora(e.fecha) }}</span>
            <span>{{ frase(e) }}</span>
          </li>
        </ul>
      </section>
    </template>

    <SecretoUnaVez
      :abierto="!!temporal"
      :titulo="`Contraseña temporal de ${temporal?.para ?? ''}`"
      texto="Pásasela por un canal seguro. No se muestra otra vez: si la pierdes, reinicia su clave."
      :valor="temporal?.clave ?? ''"
      aceptar="Listo"
      @cerrar="temporal = null"
    />
  </div>
</template>

<style scoped>
.panel + .panel,
.panel + form {
  margin-top: 16px;
}
tr.inactivo {
  opacity: 0.6;
}
.acciones {
  text-align: right;
  white-space: nowrap;
}
.nuevo {
  max-width: 760px;
}
.actividad {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.actividad li {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.actividad .num {
  flex: 0 0 120px;
}
</style>
