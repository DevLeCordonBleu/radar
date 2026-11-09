<script setup lang="ts">
/**
 * Publicaciones en Facebook, Instagram y LinkedIn: tema → texto (uno por red o el mismo para
 * todas, IA) → flyer → hashtags → aprobación → publicar. Aquí: una publicación nueva, la lista y
 * la marca de los flyers (logo, colores y hashtags del rubro). Los videos aprobados llegan desde
 * su ficha («Crear publicación»).
 */
import { onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { publicaciones } from '@/api/radar'
import type { MarcaPublicacion, ModoCopy, Publicacion, RedSocial } from '@/api/tipos'
import BibliotecaPosts from '@/components/BibliotecaPosts.vue'
import Icono from '@/components/Icono.vue'
import { fechaHora } from '@/composables/formato'
import { ESTADO_PUBLICACION, ORDEN_REDES, REDES, leerHashtags } from '@/composables/publicaciones'
import { useAuth } from '@/stores/auth'
import { useAvisos } from '@/stores/avisos'

const router = useRouter()
const auth = useAuth()
const avisos = useAvisos()

const lista = ref<Publicacion[]>([])
const ocupado = ref(false)
const f = ref({ idea: '', redes: ['FACEBOOK', 'INSTAGRAM'] as RedSocial[], modoCopy: 'POR_RED' as ModoCopy })
const marca = ref<MarcaPublicacion | null>(null)
const hashtagsBase = ref('')
const versionLogo = ref(0)
const pestana = ref<'curso' | 'biblioteca'>('curso')

async function cargar() {
  lista.value = await publicaciones.listar()
}
function ponerMarca(m: MarcaPublicacion) {
  marca.value = m
  hashtagsBase.value = m.hashtags.join(' ')
}
onMounted(() => {
  cargar().catch((e) => avisos.error(e))
  publicaciones.marca().then(ponerMarca).catch((e) => avisos.error(e))
})

async function crear(conTextos: boolean) {
  ocupado.value = true
  try {
    const p = await publicaciones.crear(f.value.idea, f.value.redes, f.value.modoCopy)
    if (conTextos) {
      try {
        await publicaciones.redactar(p.codigo)
      } catch (e) {
        avisos.error(e, 'La publicación se creó, pero la IA no pudo escribir los textos')
      }
    }
    router.push(`/publicaciones/${p.codigo}`)
  } catch (e) {
    avisos.error(e)
  } finally {
    ocupado.value = false
  }
}

async function guardarMarca() {
  if (!marca.value) return
  try {
    ponerMarca(await publicaciones.guardarMarca({ ...marca.value, hashtags: leerHashtags(hashtagsBase.value) }))
    avisos.exito('Marca guardada. Los flyers nuevos la usan; los ya hechos se actualizan al volver a armarlos.')
  } catch (e) {
    avisos.error(e)
  }
}

async function subirLogo(ev: Event) {
  const entrada = ev.target as HTMLInputElement
  const archivo = entrada.files?.[0]
  entrada.value = ''
  if (!archivo) return
  try {
    ponerMarca(await publicaciones.subirLogo(archivo))
    versionLogo.value++
    avisos.exito('Logo guardado.')
  } catch (e) {
    avisos.error(e)
  }
}

async function quitarLogo() {
  try {
    ponerMarca(await publicaciones.quitarLogo())
  } catch (e) {
    avisos.error(e)
  }
}
</script>

<template>
  <div class="pagina">
    <div class="pagina-cabecera">
      <div>
        <h1>Publicaciones</h1>
        <p>
          Posts para Facebook, Instagram y LinkedIn: la IA escribe el texto, el Radar arma el flyer con tu logo y un administrador lo
          aprueba antes de publicarlo.
        </p>
      </div>
    </div>

    <section class="panel pila">
      <h2>Nueva publicación</h2>
      <div class="campo">
        <label for="p-idea">Tema</label>
        <textarea id="p-idea" v-model="f.idea" rows="3" placeholder="Evento «Ven y conoce nuestro Campus»: recorrido por las cocinas y charla con los chefs" />
      </div>
      <div class="formulario-2">
        <div class="campo">
          <span class="etiqueta">Redes</span>
          <div class="fila">
            <label v-for="r in ORDEN_REDES" :key="r" class="casilla">
              <input v-model="f.redes" type="checkbox" :value="r" /> {{ REDES[r].nombre }}
            </label>
          </div>
        </div>
        <div class="campo">
          <span class="etiqueta">Texto</span>
          <div class="fila">
            <label class="casilla"><input v-model="f.modoCopy" type="radio" value="POR_RED" /> Uno para cada red</label>
            <label class="casilla"><input v-model="f.modoCopy" type="radio" value="MISMO" /> El mismo para todas</label>
          </div>
        </div>
      </div>
      <p class="chico suave">
        La IA escribe también el título del flyer y propone los hashtags. Para publicar un video del Radar, ábrelo en
        <RouterLink to="/videos">Videos</RouterLink> y, ya aprobado, pulsa «Crear publicación».
      </p>
      <div class="fila">
        <button class="boton boton-primario" type="button" :disabled="ocupado || f.idea.trim().length < 3 || !f.redes.length" @click="crear(true)">
          <Icono nombre="chispa" /> {{ ocupado ? 'Escribiendo los textos…' : 'Crear y escribir con IA' }}
        </button>
        <button class="boton" type="button" :disabled="ocupado || f.idea.trim().length < 3 || !f.redes.length" @click="crear(false)">Solo crear</button>
      </div>
    </section>

    <div class="pestanas" role="tablist" aria-label="Publicaciones">
      <button role="tab" type="button" :aria-selected="pestana === 'curso'" :class="{ activa: pestana === 'curso' }" @click="pestana = 'curso'">En curso</button>
      <button role="tab" type="button" :aria-selected="pestana === 'biblioteca'" :class="{ activa: pestana === 'biblioteca' }" @click="pestana = 'biblioteca'">
        Biblioteca
      </button>
    </div>

    <BibliotecaPosts v-if="pestana === 'biblioteca'" />
    <p v-else-if="!lista.length" class="vacio">Aún no hay publicaciones.</p>
    <div v-else class="tabla-envoltura">
      <table class="tabla">
        <thead>
          <tr><th>Publicación</th><th>Redes</th><th>Estado</th><th>Modificada</th></tr>
        </thead>
        <tbody>
          <tr v-for="p in lista" :key="p.codigo">
            <td>
              <RouterLink :to="`/publicaciones/${p.codigo}`"><strong>{{ p.titulo }}</strong></RouterLink>
              <small class="tenue block">
                {{ p.media === 'VIDEO' ? 'Video' : p.flyer.enUso ? 'Flyer' : p.media === 'IMAGEN' ? 'Imagen' : 'Solo texto' }}<template v-if="p.codOrigen"> · del video {{ p.codOrigen }}</template>
              </small>
            </td>
            <td class="chico">
              <span v-for="r in p.redes" :key="r" class="red" :class="{ hecha: p.enlaces[r] }">
                <Icono v-if="p.enlaces[r]" nombre="ok" /> {{ REDES[r].nombre }}
              </span>
            </td>
            <td><span class="chip" :class="ESTADO_PUBLICACION[p.estado].chip">{{ ESTADO_PUBLICACION[p.estado].texto }}</span></td>
            <td class="chico tenue">{{ fechaHora(p.modificado) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <details v-if="marca" class="panel marca">
      <summary><strong>Marca de los flyers</strong> <span class="chico tenue">· logo, colores y hashtags del rubro</span></summary>
      <div class="pila">
        <div class="campo">
          <span class="etiqueta">Logo</span>
          <div class="fila">
            <img v-if="marca.tieneLogo" :key="versionLogo" class="logo" :src="`${publicaciones.logo}?v=${versionLogo}`" alt="Logo de los flyers" />
            <span v-else class="chico ambar"><Icono nombre="alerta" /> Sin logo: los flyers salen sin él.</span>
            <template v-if="auth.esAdmin">
              <label class="boton boton-chico">
                <Icono nombre="subir" /> {{ marca.tieneLogo ? 'Cambiar' : 'Subir logo' }}
                <input class="oculto-visual" type="file" accept="image/png,image/jpeg" @change="subirLogo" />
              </label>
              <button v-if="marca.tieneLogo" class="boton boton-chico boton-fantasma" type="button" @click="quitarLogo"><Icono nombre="x" /> Quitar</button>
            </template>
          </div>
          <span class="campo-ayuda">El logo oficial en PNG (mejor con fondo transparente). Va arriba a la izquierda, sobre una placa blanca.</span>
        </div>
        <div class="fila campos">
          <div class="campo">
            <label for="m-color">Color principal</label>
            <input id="m-color" v-model="marca.color" type="color" :disabled="!auth.esAdmin" />
          </div>
          <div class="campo">
            <label for="m-acento">Color de acento</label>
            <input id="m-acento" v-model="marca.acento" type="color" :disabled="!auth.esAdmin" />
          </div>
        </div>
        <div class="campo">
          <label for="m-hashtags">Hashtags del rubro</label>
          <input id="m-hashtags" v-model="hashtagsBase" type="text" :disabled="!auth.esAdmin" placeholder="#LeCordonBleuPeru #Gastronomía" />
          <span class="campo-ayuda">
            Van en todas las publicaciones, delante de los que la IA propone para cada tema. Ninguna API gratuita dice cuáles se usan
            más: mantenlos según lo que ve Marketing en las redes.
          </span>
        </div>
        <div v-if="auth.esAdmin" class="fila">
          <button class="boton boton-primario" type="button" @click="guardarMarca"><Icono nombre="guardar" /> Guardar marca</button>
        </div>
        <p v-else class="chico">Solo un administrador cambia la marca.</p>
      </div>
    </details>
  </div>
</template>

<style scoped>
.pestanas {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--borde);
  margin: 16px 0;
}
.pestanas button {
  background: none;
  border: 0;
  border-bottom: 2px solid transparent;
  padding: 9px 14px;
  color: var(--texto-suave);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
  margin-bottom: -1px;
}
.pestanas button:hover {
  color: var(--texto);
}
.pestanas button.activa {
  color: var(--cian);
  border-bottom-color: var(--cian);
}
h2 {
  margin: 0;
  font-size: 1.05rem;
}
svg {
  width: 15px;
  height: 15px;
  vertical-align: -2px;
}
.red {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  margin-right: 10px;
  white-space: nowrap;
}
.red.hecha {
  color: var(--lima);
}
.red svg {
  width: 12px;
  height: 12px;
}
.marca summary {
  cursor: pointer;
}
.marca .pila {
  margin-top: 12px;
}
.logo {
  max-height: 56px;
  max-width: 200px;
  padding: 6px 10px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid var(--borde);
}
.campos {
  gap: 24px;
}
input[type='color'] {
  width: 64px;
  height: 36px;
  padding: 2px;
}
.ambar {
  color: var(--ambar);
}
</style>
