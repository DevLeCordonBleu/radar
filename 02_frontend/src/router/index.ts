/**
 * Rutas del panel.
 *
 * La raíz es «Análisis de competencia» (como en el menú); el informe abierto es la vista
 * principal de lectura. Todo menos /acceso exige sesión: ver el guardia abajo.
 */
import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'nuevo', component: () => import('@/views/NuevoView.vue'), meta: { titulo: 'Análisis de competencia' } },
    { path: '/nuevo', redirect: '/' },
    { path: '/informes', name: 'informes', component: () => import('@/views/InformesView.vue'), meta: { titulo: 'Informes' } },
    { path: '/keywords', name: 'keywords', component: () => import('@/views/KeywordsHomeView.vue'), meta: { titulo: 'KeyWords Explorer' } },
    { path: '/keywords/explorar', name: 'keywords-resultados', component: () => import('@/views/KeywordsResultadosView.vue'), meta: { titulo: 'KeyWords Explorer' } },
    { path: '/keywords/listas', name: 'keywords-listas', component: () => import('@/views/KeywordsListasView.vue'), meta: { titulo: 'Listas de keywords' } },
    {
      path: '/keywords/listas/:codigo',
      name: 'keywords-lista',
      component: () => import('@/views/KeywordsListaView.vue'),
      props: true,
      meta: { titulo: 'Lista de keywords' },
    },
    { path: '/seo', name: 'seo', component: () => import('@/views/SeoView.vue'), meta: { titulo: 'Plan SEO' } },
    { path: '/videos', name: 'videos', component: () => import('@/views/VideosView.vue'), meta: { titulo: 'Videos' } },
    { path: '/videos/:codigo', name: 'video', component: () => import('@/views/VideoView.vue'), meta: { titulo: 'Video' } },
    { path: '/medicion', name: 'medicion', component: () => import('@/views/MedicionView.vue'), meta: { titulo: 'Medición' } },
    { path: '/publicaciones', name: 'publicaciones', component: () => import('@/views/PublicacionesView.vue'), meta: { titulo: 'Publicaciones' } },
    { path: '/publicaciones/:codigo', name: 'publicacion', component: () => import('@/views/PublicacionView.vue'), meta: { titulo: 'Publicación' } },
    { path: '/seo/articulos/:codigo', name: 'seo-articulo', component: () => import('@/views/SeoArticuloView.vue'), meta: { titulo: 'Artículo' } },
    { path: '/acceso', name: 'acceso', component: () => import('@/views/AccesoView.vue'), meta: { titulo: 'Acceso', publica: true } },
    { path: '/cuenta', name: 'cuenta', component: () => import('@/views/CuentaView.vue'), meta: { titulo: 'Mi cuenta' } },
    {
      path: '/usuarios',
      name: 'usuarios',
      component: () => import('@/views/UsuariosView.vue'),
      meta: { titulo: 'Usuarios', admin: true },
    },
    {
      path: '/analisis/:codigo',
      name: 'analisis',
      component: () => import('@/views/AnalisisView.vue'),
      props: true,
      meta: { titulo: 'Análisis' },
    },
    {
      path: '/informes/:codigo',
      name: 'informe',
      component: () => import('@/views/InformeView.vue'),
      props: true,
      meta: { titulo: 'Informe' },
    },
    { path: '/ajustes', name: 'ajustes', component: () => import('@/views/AjustesView.vue'), meta: { titulo: 'Ajustes' } },
    { path: '/ayuda', name: 'ayuda', component: () => import('@/views/AyudaView.vue'), meta: { titulo: 'Ayuda' } },
    {
      path: '/:pathMatch(.*)*',
      name: 'no-encontrado',
      component: () => import('@/views/NoEncontradoView.vue'),
      meta: { titulo: 'No encontrado' },
    },
  ],
  scrollBehavior: (a, b, guardada) => {
    if (guardada) return guardada
    // Saltar a una sección del informe (#s3) no debe volver arriba.
    if (a.hash) return { el: a.hash, behavior: 'smooth', top: 70 }
    if (a.name === b.name && a.params.codigo === b.params.codigo) return false
    return { top: 0 }
  },
})

/**
 * Sin sesión todo lleva a /acceso; con sesión, /acceso lleva al inicio. Quien
 * entra con una clave temporal solo puede ir a cambiarla. /usuarios es de admins.
 */
router.beforeEach(async (to) => {
  const auth = useAuth()
  try {
    await auth.cargar()
  } catch {
    return true // el backend no responde: cada vista lo avisa
  }
  if (!auth.usuario) return to.meta.publica ? true : { name: 'acceso', query: to.fullPath !== '/' ? { vuelta: to.fullPath } : {} }
  if (to.meta.publica) return { name: 'nuevo' }
  if (auth.usuario.debeCambiar && to.name !== 'cuenta') return { name: 'cuenta' }
  if (to.meta.admin && !auth.esAdmin) return { name: 'nuevo' }
  return true
})

router.afterEach((to) => {
  const titulo = (to.params.codigo as string) || (to.meta.titulo as string) || 'Panel'
  document.title = `${titulo} · Radar de Anuncios`
})

export default router
