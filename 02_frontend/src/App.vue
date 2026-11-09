<script setup lang="ts">
/**
 * Armazón: menú lateral con los módulos, el usuario y el tema abajo, y el
 * contenido a la derecha. La pantalla de acceso va sola, sin menú.
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import CentroAvisos from '@/components/CentroAvisos.vue'
import DialogoConfirmar from '@/components/DialogoConfirmar.vue'
import Icono from '@/components/Icono.vue'
import { alternarTema, tema } from '@/composables/tema'
import { useAuth } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuth()

const conMenu = computed(() => !route.meta.publica)
const menuUsuario = ref(false)

interface Enlace {
  a: string
  texto: string
  icono: string
  admin?: boolean
}

const ENLACES: Enlace[] = [
  { a: '/', texto: 'Análisis de competencia', icono: 'radar' },
  { a: '/informes', texto: 'Informes', icono: 'lista' },
  { a: '/keywords', texto: 'KeyWords Explorer', icono: 'buscar' },
  { a: '/seo', texto: 'Plan SEO', icono: 'grafico' },
  { a: '/videos', texto: 'Videos', icono: 'videos' },
  { a: '/publicaciones', texto: 'Publicaciones', icono: 'compartir' },
  { a: '/medicion', texto: 'Medición', icono: 'tablero' },
  { a: '/usuarios', texto: 'Usuarios', icono: 'usuarios', admin: true },
  { a: '/ajustes', texto: 'Ajustes', icono: 'ajustes' },
]
const visibles = computed(() => ENLACES.filter((e) => !e.admin || auth.esAdmin))

/** «/» solo es «Análisis de competencia» en exacto; el resto, por prefijo (un informe abierto sigue en Informes). */
function activo(e: Enlace): boolean {
  if (e.a === '/') return route.path === '/'
  return route.path === e.a || route.path.startsWith(e.a + '/') || (e.a === '/informes' && route.path.startsWith('/analisis'))
}

const inicial = computed(() => (auth.usuario?.nombre.trim()[0] ?? '?').toUpperCase())

async function salir() {
  menuUsuario.value = false
  await auth.salir()
  router.push('/acceso')
}

function alCaducar() {
  auth.sesionCaducada()
  if (!route.meta.publica) router.push('/acceso')
}

function cerrarMenuFuera(ev: MouseEvent) {
  if (!(ev.target as HTMLElement).closest('.usuario-caja')) menuUsuario.value = false
}

onMounted(() => {
  window.addEventListener('radar:sin-sesion', alCaducar)
  document.addEventListener('click', cerrarMenuFuera)
})
onBeforeUnmount(() => {
  window.removeEventListener('radar:sin-sesion', alCaducar)
  document.removeEventListener('click', cerrarMenuFuera)
})
</script>

<template>
  <div class="armazon" :class="{ 'con-menu': conMenu }">
    <a href="#contenido" class="saltar">Saltar al contenido</a>

    <aside v-if="conMenu" class="menu" aria-label="Menú principal">
      <RouterLink to="/" class="marca" aria-label="Radar de Anuncios: inicio">
        <span class="logo" aria-hidden="true"><Icono nombre="radar" /></span>
        <strong>RADAR</strong>
      </RouterLink>

      <nav aria-label="Módulos">
        <RouterLink v-for="e in visibles" :key="e.a" :to="e.a" class="enlace" :class="{ activo: activo(e) }" :aria-current="activo(e) ? 'page' : undefined">
          <Icono :nombre="e.icono" />
          <span>{{ e.texto }}</span>
          <i v-if="activo(e)" class="punto" aria-hidden="true" />
        </RouterLink>
      </nav>

      <div class="abajo">
        <RouterLink to="/ayuda" class="enlace" :class="{ activo: route.path === '/ayuda' }">
          <Icono nombre="ayuda" />
          <span>Ayuda</span>
        </RouterLink>

        <div v-if="auth.usuario" class="usuario-caja">
          <button class="usuario" type="button" :aria-expanded="menuUsuario" aria-haspopup="menu" @click.stop="menuUsuario = !menuUsuario">
            <span class="avatar" aria-hidden="true">{{ inicial }}</span>
            <span class="quien">
              <strong>{{ auth.usuario.nombre }}</strong>
              <small>{{ auth.usuario.rol === 'admin' ? 'Administrador' : 'Miembro' }}</small>
            </span>
            <Icono nombre="abajo" class="flecha" />
          </button>
          <button
            class="tema"
            type="button"
            :aria-label="tema === 'claro' ? 'Cambiar al tema oscuro' : 'Cambiar al tema claro'"
            :title="tema === 'claro' ? 'Tema oscuro' : 'Tema claro'"
            @click="alternarTema"
          >
            <Icono :nombre="tema === 'claro' ? 'luna' : 'sol'" />
          </button>

          <div v-if="menuUsuario" class="desplegable" role="menu">
            <p class="chico tenue correo">{{ auth.usuario.email }}</p>
            <RouterLink to="/cuenta" role="menuitem" class="opcion" @click="menuUsuario = false"><Icono nombre="llave" /> Mi cuenta</RouterLink>
            <button type="button" role="menuitem" class="opcion" @click="salir"><Icono nombre="salir" /> Cerrar sesión</button>
          </div>
        </div>

        <p class="pie tenue">Radar de Anuncios · v0.1</p>
      </div>
    </aside>

    <main id="contenido" class="contenido">
      <RouterView />
    </main>

    <CentroAvisos />
    <DialogoConfirmar />
  </div>
</template>

<style scoped>
.armazon {
  min-height: 100vh;
}
.saltar {
  position: absolute;
  left: -9999px;
  top: 8px;
  z-index: 2000;
  background: var(--cian);
  color: #fff;
  padding: 6px 12px;
  border-radius: 6px;
}
.saltar:focus {
  left: 8px;
}

/* ── Menú lateral ── */
.con-menu {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
}
.menu {
  position: sticky;
  top: 0;
  height: 100vh;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 20px 14px 14px;
  background: var(--panel);
  border-right: 1px solid var(--borde);
}
.marca {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 10px;
  color: var(--texto);
  text-decoration: none;
  letter-spacing: 0.04em;
}
.marca:hover {
  text-decoration: none;
}
.logo {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 9px;
  background: var(--cian);
  color: #fff;
}
.logo svg {
  width: 22px;
  height: 22px;
}
nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.enlace {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  color: var(--texto-suave);
  font-weight: 500;
  text-decoration: none;
}
.enlace svg {
  width: 19px;
  height: 19px;
  flex-shrink: 0;
}
.enlace:hover {
  background: var(--panel-2);
  color: var(--texto);
  text-decoration: none;
}
.enlace.activo {
  background: var(--cian-fondo);
  color: var(--cian);
}
.punto {
  margin-left: auto;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}
.abajo {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.usuario-caja {
  position: relative;
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 6px;
}
.usuario {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: transparent;
  border: 0;
  border-radius: 10px;
  color: var(--texto);
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.usuario:hover {
  background: var(--panel-2);
}
.avatar {
  display: grid;
  place-items: center;
  flex: 0 0 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--cian-fondo);
  color: var(--cian);
  font-weight: 700;
}
.quien {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.2;
}
.quien strong,
.quien small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.quien small {
  color: var(--texto-suave);
}
.flecha {
  width: 16px;
  height: 16px;
  margin-left: auto;
  color: var(--texto-tenue);
}
.tema {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: transparent;
  border: 1px solid var(--borde);
  color: var(--texto-suave);
  cursor: pointer;
}
.tema:hover {
  background: var(--panel-2);
  color: var(--texto);
}
.tema svg {
  width: 18px;
  height: 18px;
}
.desplegable {
  position: absolute;
  left: 0;
  right: 0;
  bottom: calc(100% + 6px);
  display: flex;
  flex-direction: column;
  padding: 6px;
  background: var(--panel);
  border: 1px solid var(--borde-fuerte);
  border-radius: 10px;
  box-shadow: var(--sombra);
  z-index: 50;
}
.correo {
  padding: 6px 10px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.opcion {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: transparent;
  border: 0;
  border-radius: 8px;
  color: var(--texto);
  font: inherit;
  text-align: left;
  text-decoration: none;
  cursor: pointer;
}
.opcion:hover {
  background: var(--panel-2);
  text-decoration: none;
}
.opcion svg {
  width: 16px;
  height: 16px;
}
.pie {
  padding: 4px 10px 0;
  font-size: 0.72rem;
}

/* En pantallas estrechas el menú pasa arriba y solo muestra iconos. */
@media (max-width: 860px) {
  .con-menu {
    grid-template-columns: minmax(0, 1fr);
  }
  .menu {
    position: sticky;
    z-index: 100;
    height: auto;
    flex-direction: row;
    align-items: center;
    gap: 6px;
    padding: 8px 10px;
    border-right: 0;
    border-bottom: 1px solid var(--borde);
  }
  .marca strong,
  .enlace span,
  .quien,
  .flecha,
  .pie,
  .punto {
    display: none;
  }
  .marca {
    padding: 0;
  }
  /* Con muchos módulos los iconos se desplazan en horizontal en vez de desbordar la barra. */
  nav {
    flex-direction: row;
    flex: 1;
    min-width: 0;
    overflow-x: auto;
    scrollbar-width: none;
  }
  .abajo {
    flex: none;
    margin: 0 0 0 auto;
    flex-direction: row;
    align-items: center;
  }
  .usuario-caja {
    margin: 0;
  }
  .desplegable {
    left: auto;
    right: 0;
    bottom: auto;
    top: calc(100% + 6px);
    min-width: 220px;
  }
}
@media print {
  .menu {
    display: none;
  }
  .con-menu {
    display: block;
  }
}
</style>
