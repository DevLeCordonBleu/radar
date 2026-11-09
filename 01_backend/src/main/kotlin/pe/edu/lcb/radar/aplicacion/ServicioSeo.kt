package pe.edu.lcb.radar.aplicacion

import org.slf4j.LoggerFactory
import org.springframework.beans.factory.annotation.Qualifier
import org.springframework.boot.context.event.ApplicationReadyEvent
import org.springframework.context.event.EventListener
import org.springframework.scheduling.annotation.Scheduled
import org.springframework.stereotype.Service
import pe.edu.lcb.radar.dominio.Json
import pe.edu.lcb.radar.dominio.NoEncontrado
import pe.edu.lcb.radar.dominio.Prohibido
import pe.edu.lcb.radar.dominio.ReglaIncumplida
import pe.edu.lcb.radar.dominio.Usuario
import pe.edu.lcb.radar.infraestructura.ArticuloSeo
import pe.edu.lcb.radar.infraestructura.ClienteWorker
import pe.edu.lcb.radar.infraestructura.ErrorDelWorker
import pe.edu.lcb.radar.infraestructura.FilaGsc
import pe.edu.lcb.radar.infraestructura.InformeGuardado
import pe.edu.lcb.radar.infraestructura.RepositorioInformesGuardados
import pe.edu.lcb.radar.infraestructura.MejoraSeo
import pe.edu.lcb.radar.infraestructura.KeywordSeo
import pe.edu.lcb.radar.infraestructura.PaginaSeo
import pe.edu.lcb.radar.infraestructura.RepositorioAjustes
import pe.edu.lcb.radar.infraestructura.RepositorioConsumo
import pe.edu.lcb.radar.infraestructura.RepositorioSeo
import pe.edu.lcb.radar.infraestructura.SitioSeo
import pe.edu.lcb.radar.infraestructura.TareaSeo
import tools.jackson.databind.ObjectMapper
import java.text.Normalizer
import java.time.Instant
import java.time.LocalTime
import java.time.ZoneId
import java.util.Base64
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.ExecutorService

/**
 * Plan SEO: inventario de paginas publicas, temas por pagina y keywords
 * informacionales candidatas con su cobertura en el sitio propio.
 *
 * Tres tareas en segundo plano, una a la vez (cola propia, aparte de la de
 * analisis). Todas son repetibles sin rehacer trabajo: el inventario solo
 * descarga paginas nuevas, cambiadas o que fallaron; los temas solo se piden de
 * paginas cuyo contenido cambio. Si Gemini agota la cuota, la tarea queda en
 * pausa y «Continuar» sigue donde se quedo.
 *
 * Las keywords son hipotesis (evidencia TOPIC_OBSERVED): salen del contenido
 * publico de un competidor, no de su posicion en Google.
 */
@Service
class ServicioSeo(
    private val repo: RepositorioSeo,
    private val worker: ClienteWorker,
    private val consumo: RepositorioConsumo,
    private val ajustes: RepositorioAjustes,
    private val informes: RepositorioInformesGuardados,
    private val json: ObjectMapper,
    @Qualifier("colaSeo") private val cola: ExecutorService,
) {
    private val log = LoggerFactory.getLogger(javaClass)
    private val cancelados = ConcurrentHashMap.newKeySet<String>()

    private class Cancelada : RuntimeException()

    @EventListener(ApplicationReadyEvent::class)
    fun preparar() {
        repo.sembrar(SITIOS)
        for (t in repo.tareasActivas()) {
            repo.estadoTarea(t.codigo, "PAUSADA", error = "El programa se cerró durante la tarea. Lo hecho está guardado: pulsa «Continuar».")
        }
        // Lo que ya habia antes del historial queda como su primer informe.
        if (!informes.hay(SEARCH_CONSOLE) && repo.resumenGsc()["consultas"] != 0L) guardarCorteGsc()
        if (!informes.hay(PLAN_SEO_KEYWORDS) && repo.keywords().isNotEmpty()) guardarKeywords(null, null)
    }

    // ── Informes guardados (Search Console y keywords) ────────────────────

    fun informesGuardados(modulo: String?): List<InformeGuardado> {
        if (modulo != null && modulo !in MODULOS_INFORME) throw ReglaIncumplida("Módulo no válido: usa ${MODULOS_INFORME.joinToString(", ")}.")
        return informes.todos(modulo)
    }

    fun informeGuardado(codigo: String): Map<String, Any?> = mapOf("informe" to informes.buscar(codigo), "filas" to informes.datos(codigo))

    /** El informe en CSV, con las columnas de su modulo y BOM para que Excel lea las tildes. */
    fun csvInforme(codigo: String): Pair<String, String> {
        val i = informes.buscar(codigo)
        val columnas = when (i.modulo) {
            SEARCH_CONSOLE -> COLUMNAS_GSC
            PLAN_SEO_KEYWORDS -> COLUMNAS_KEYWORDS
            else -> COLUMNAS_MEDICION
        }
        val celda = { v: Any? ->
            val t = when (v) {
                null -> ""
                is List<*> -> v.joinToString(" / ") { (it as? Map<*, *>)?.get("url")?.toString() ?: it.toString() }
                else -> v.toString()
            }
            if (t.any { it == ',' || it == '"' || it == '\n' }) "\"" + t.replace("\"", "\"\"") + "\"" else t
        }
        val lineas = listOf(columnas.joinToString(",")) + informes.datos(codigo).map { f -> columnas.joinToString(",") { celda(f[it]) } }
        return "${i.codigo}-${i.modulo.lowercase()}.csv" to "\uFEFF" + lineas.joinToString("\r\n")
    }

    /** Vuelve a poner un corte guardado de Search Console como los datos actuales (lo que usan las mejoras y el flujo). */
    fun restaurarCorte(codigo: String): Map<String, Any?> {
        val i = informes.buscar(codigo)
        if (i.modulo != SEARCH_CONSOLE) throw ReglaIncumplida("Solo un corte de Search Console se puede volver a cargar.")
        if (repo.tareasActivas().any { it.tipo == "AUTOMATICO" }) throw ReglaIncumplida("El flujo automático está en marcha: espera a que termine.")
        val filas = informes.datos(codigo).mapNotNull { f ->
            val consulta = (f["consulta"] as? String)?.ifBlank { null } ?: return@mapNotNull null
            FilaGsc(consulta, orden(consulta), f["url"] as? String ?: "", (f["clics"] as? Number)?.toInt() ?: 0,
                (f["impresiones"] as? Number)?.toInt() ?: 0, (f["ctr"] as? Number)?.toDouble() ?: 0.0, (f["posicion"] as? Number)?.toDouble() ?: 0.0)
        }
        repo.reemplazarGsc(filas)
        ajustes.guardar(CLAVE_GSC, json.writeValueAsString(
            i.resumen.filterKeys { it in CAMPOS_SINC } + mapOf("filas" to filas.size, "informe" to i.codigo)))
        return searchConsole()
    }

    /** Guarda los datos actuales de Search Console como un informe y lo anota en el ajuste de la sincronizacion. */
    private fun guardarCorteGsc(): InformeGuardado {
        val sinc = ajustes.leer(CLAVE_GSC)?.let { runCatching { json.readValue(it, Map::class.java) }.getOrNull() }.orEmpty()
        val filas = repo.gscEntre(-1.0, Double.MAX_VALUE, 0)
        val resumen = CAMPOS_SINC.associateWith { sinc[it] } + repo.resumenGsc() + ("filas" to filas.size)
        val periodo = if (sinc["desde"] != null) "del ${sinc["desde"]} al ${sinc["hasta"]}" else "periodo sin registrar"
        val corte = informes.guardar(SEARCH_CONSOLE, "Search Console · $periodo", resumen,
            filas.map { mapOf("consulta" to it.consulta, "url" to it.url, "clics" to it.clics, "impresiones" to it.impresiones, "ctr" to it.ctr, "posicion" to it.posicion) },
            null, null)
        if (sinc.isNotEmpty()) ajustes.guardar(CLAVE_GSC, json.writeValueAsString(sinc + ("informe" to corte.codigo)))
        return corte
    }

    private fun guardarKeywords(tarea: String?, resumen: Map<String, Any?>?): InformeGuardado {
        val ks = repo.keywords()
        val datos = ks.map {
            mapOf("keyword" to it.keyword, "grupo" to it.grupo, "canonica" to it.canonica, "intencion" to it.intencion, "relevancia" to it.relevancia,
                "cobertura" to it.cobertura, "urlPropia" to it.urlPropia, "motivoCobertura" to it.motivoCobertura, "origenes" to it.origenes,
                "evidencia" to it.evidencia, "motivo" to it.motivo)
        }
        val r = resumen ?: mapOf("evaluadas" to ks.size, "grupos" to ks.mapNotNull { it.grupo }.distinct().size,
            "informacionales" to ks.count { it.intencion == "INFORMATIONAL" })
        return informes.guardar(PLAN_SEO_KEYWORDS, "Keywords del Plan SEO · ${ks.size} keywords", r, datos, tarea, null)
    }

    // ── Consultas ─────────────────────────────────────────────────────────

    fun sitios(): List<SitioSeo> {
        val palabras = rubro().palabras
        return repo.sitios().map { s ->
            if (s.esPropio || s.sinTemas == 0) s
            else s.copy(sinTemasDelSector = repo.paginasSinTemas(s.codigo).count { (url, d) -> SectorSeo.delSector(url, d, palabras) })
        }
    }

    /** Un competidor nuevo: nombre y los dominios donde publica (se aceptan enlaces completos). */
    fun crearSitio(cuerpo: Map<*, *>): SitioSeo {
        val nombre = nombreValido(cuerpo["nombre"])
        val hosts = hostsValidos(cuerpo["hosts"], null)
        val existentes = repo.sitios().map { it.codigo }.toSet()
        val raiz = Normalizer.normalize(nombre.uppercase(), Normalizer.Form.NFD).replace(Regex("[^A-Z0-9]"), "").take(12).ifEmpty { "SITIO" }
        val codigo = (sequenceOf(raiz) + generateSequence(2) { it + 1 }.map { "$raiz$it" }).first { it !in existentes }
        repo.crearSitio(codigo, nombre, "COMPETIDOR", hosts)
        return repo.sitio(codigo)
    }

    /**
     * Cambia nombre, dominios, maximo o activo (lo que no venga se conserva). Si cambian los
     * dominios, las paginas ya leidas se quedan: el siguiente inventario retira las que el sitio
     * ya no declare y lee las nuevas.
     */
    fun ajustarSitio(codigo: String, cuerpo: Map<*, *>): SitioSeo {
        val s = repo.sitio(codigo)
        val max = (cuerpo["maxPaginas"] as? Number)?.toInt() ?: s.maxPaginas
        if (max !in 10..3000) throw ReglaIncumplida("El máximo de páginas por inventario va de 10 a 3000.")
        val nombre = if (cuerpo.containsKey("nombre")) nombreValido(cuerpo["nombre"]) else s.nombre
        val hosts = if (cuerpo.containsKey("hosts")) hostsValidos(cuerpo["hosts"], codigo) else s.hosts
        if (hosts != s.hosts && repo.tareasActivas().any { it.sitio == codigo }) {
            throw ReglaIncumplida("Hay una tarea de ${s.nombre} en marcha: espera a que termine para cambiar sus dominios.")
        }
        repo.ajustarSitio(codigo, nombre, hosts, max, cuerpo["activo"] as? Boolean ?: s.activo)
        return repo.sitio(codigo)
    }

    /** Quita un competidor y sus paginas leidas. Solo admin; el sitio propio no se quita. */
    fun borrarSitio(actor: Usuario, codigo: String) {
        if (!actor.esAdmin) throw Prohibido("Solo un administrador puede quitar un sitio.")
        val s = repo.sitio(codigo)
        if (s.esPropio) throw ReglaIncumplida("El sitio propio no se puede quitar: sin él no se sabe qué ya está cubierto. Puedes cambiar sus dominios.")
        if (repo.tareasActivas().any { it.sitio == codigo }) throw ReglaIncumplida("Hay una tarea de ${s.nombre} en marcha: cancélala antes de quitarlo.")
        repo.borrarSitio(codigo)
    }

    private fun nombreValido(v: Any?): String {
        val nombre = (v as? String)?.trim().orEmpty()
        if (nombre.isEmpty()) throw ReglaIncumplida("Falta el nombre del sitio.")
        if (nombre.length > 80) throw ReglaIncumplida("El nombre del sitio admite hasta 80 caracteres.")
        return nombre
    }

    /** «https://www.usil.edu.pe/carreras/» -> «www.usil.edu.pe». Sin repetidos ni dominios de otro sitio. */
    private fun hostsValidos(v: Any?, codigo: String?): List<String> {
        val hosts = (v as? List<*>).orEmpty().mapNotNull { (it as? String)?.trim()?.takeIf(String::isNotEmpty) }.map { t ->
            val sinEsquema = t.lowercase().replace(Regex("^[a-z]+://"), "")
            val h = sinEsquema.substringBefore('/').substringBefore('?').substringBefore('#').substringBefore(':').trimEnd('.')
            if (!HOST.matches(h)) throw ReglaIncumplida("«$t» no parece un dominio. Escríbelo como usil.edu.pe o pega el enlace de su web.")
            h
        }.distinct()
        if (hosts.isEmpty()) throw ReglaIncumplida("Falta al menos un dominio (por ejemplo, usil.edu.pe).")
        if (hosts.size > MAX_HOSTS) throw ReglaIncumplida("Como mucho $MAX_HOSTS dominios por sitio.")
        for (otro in repo.sitios().filter { it.codigo != codigo }) {
            hosts.firstOrNull { it in otro.hosts }?.let { throw ReglaIncumplida("$it ya es de ${otro.nombre}.") }
        }
        return hosts
    }

    fun paginas(sitio: String?): List<PaginaSeo> = repo.paginas(sitio)

    fun keywords(): List<KeywordSeo> = repo.keywords()

    fun tareas(): List<TareaSeo> = repo.tareas(20)

    fun tarea(codigo: String): TareaSeo = repo.tarea(codigo)

    // ── Rubro del negocio propio ──────────────────────────────────────────

    fun rubro(): RubroSeo = ajustes.leer(CLAVE_RUBRO)?.let { texto ->
        val m = json.readValue(texto, Map::class.java)
        RubroSeo(m["descripcion"] as? String ?: "", (m["palabras"] as? List<*>).orEmpty().map { it.toString() })
    } ?: SectorSeo.POR_DEFECTO

    /** El rubro y lo que costaria cambiarlo: paginas con temas (todas y las marcadas fuera del sector). */
    fun estadoRubro(): Map<String, Any?> {
        val (conTemas, fuera) = repo.contarTemas()
        val r = rubro()
        return mapOf("descripcion" to r.descripcion, "palabras" to r.palabras, "porDefecto" to (r == SectorSeo.POR_DEFECTO),
            "negocio" to negocio(), "conTemas" to conTemas, "fueraDelSector" to fuera)
    }

    /**
     * Guarda el rubro. Si cambia la descripcion, la relevancia de todas las paginas se midio
     * contra otra cosa: se olvidan sus temas para que «Extraer temas» las vuelva a evaluar. Si
     * solo cambian las palabras, se olvidan solo las que el filtro dejo fuera (ahora pueden pasar).
     */
    fun guardarRubro(cuerpo: Map<*, *>): Map<String, Any?> {
        val descripcion = (cuerpo["descripcion"] as? String)?.trim().orEmpty()
        if (descripcion.length !in 10..300) throw ReglaIncumplida("Describe el rubro en una frase (de 10 a 300 caracteres).")
        val palabras = (cuerpo["palabras"] as? List<*>).orEmpty().mapNotNull { (it as? String)?.trim()?.takeIf(String::isNotEmpty) }.map { p ->
            SectorSeo.palabras(p).singleOrNull()
                ?: throw ReglaIncumplida("«$p»: escribe una palabra por término, sin espacios ni signos (el filtro compara palabra por palabra).")
        }.distinct()
        if (palabras.size < 3) throw ReglaIncumplida("Hacen falta al menos 3 palabras del rubro para el filtro gratuito.")
        if (palabras.size > MAX_PALABRAS) throw ReglaIncumplida("Como mucho $MAX_PALABRAS palabras.")
        palabras.firstOrNull { it.length < 2 }?.let { throw ReglaIncumplida("«$it» es demasiado corta: filtraría casi cualquier página.") }
        if (repo.tareasActivas().isNotEmpty()) throw ReglaIncumplida("Hay una tarea del Plan SEO en marcha: espera a que termine para cambiar el rubro.")
        val antes = rubro()
        val nuevo = RubroSeo(descripcion, palabras)
        val reevaluar = when {
            nuevo == antes -> 0
            nuevo.descripcion != antes.descripcion -> repo.olvidarTemas(soloFuera = false)
            nuevo.palabras.toSet() != antes.palabras.toSet() -> repo.olvidarTemas(soloFuera = true)
            else -> 0
        }
        ajustes.guardar(CLAVE_RUBRO, json.writeValueAsString(mapOf("descripcion" to descripcion, "palabras" to palabras)))
        return estadoRubro() + ("reevaluar" to reevaluar)
    }

    // ── Fecha minima de publicacion ───────────────────────────────────────

    /** AAAA-MM-DD o null (sin limite). Lo anterior no se lee ni se analiza. */
    fun fechaMinima(): String? = ajustes.leer(CLAVE_FECHA_MINIMA)?.ifBlank { null }

    fun estadoFechaMinima(): Map<String, Any?> = mapOf("fecha" to fechaMinima(), "antiguas" to repo.contarAntiguas())

    fun guardarFechaMinima(cuerpo: Map<*, *>): Map<String, Any?> {
        val fecha = (cuerpo["fecha"] as? String)?.trim()?.ifEmpty { null }
        if (fecha != null) {
            val d = runCatching { java.time.LocalDate.parse(fecha) }.getOrNull() ?: throw ReglaIncumplida("La fecha mínima va como AAAA-MM-DD.")
            if (d.isAfter(java.time.LocalDate.now(LIMA))) throw ReglaIncumplida("La fecha mínima no puede ser futura.")
        }
        if (repo.tareasActivas().isNotEmpty()) throw ReglaIncumplida("Hay una tarea del Plan SEO en marcha: espera a que termine para cambiar la fecha mínima.")
        ajustes.guardar(CLAVE_FECHA_MINIMA, fecha.orEmpty())
        val (marcadas, devueltas) = repo.aplicarFechaMinima(fecha)
        return estadoFechaMinima() + mapOf("marcadas" to marcadas, "devueltas" to devueltas)
    }

    /** Propuesta de rubro leyendo el inventario del sitio propio (una llamada a Gemini). No se guarda. */
    fun sugerirRubro(): Map<String, Any?> {
        val propias = repo.paginasOk("PROPIO")
        if (propias.isEmpty()) throw ReglaIncumplida("Primero haz el inventario de tu sitio propio: la sugerencia sale de sus páginas.")
        val paginas = propias.take(250).map { p ->
            val d = p.datos.orEmpty()
            mapOf("title" to d["title"], "h1" to d["h1"], "h2" to (d["h2"] as? List<*>).orEmpty().take(5))
        }
        val r = worker.post("/seo/rubro", mapOf("negocio" to negocio(), "paginas" to paginas))
        (r["uso"] as? Map<*, *>)?.let { consumo.registrar("SEO-RUBRO", "seo_rubro", it) }
        return mapOf("descripcion" to r["descripcion"], "palabras" to r["palabras"])
    }

    /** Los dominios del sitio propio, sin www (para los UTM de las publicaciones). */
    fun dominiosPropios(): List<String> =
        repo.sitios().filter { it.esPropio }.flatMap { it.hosts }.map { it.lowercase().removePrefix("www.") }.distinct().ifEmpty { listOf("ilcb.edu.pe") }

    internal fun negocio(): String = repo.sitios().firstOrNull { it.esPropio }?.nombre ?: "el sitio propio"

    // ── Articulos ─────────────────────────────────────────────────────────

    fun articulos(): List<ArticuloSeo> = repo.articulos()

    fun articulo(codigo: String): ArticuloSeo = repo.articulo(codigo)

    /** Un articulo por grupo de keywords: lo crea y encarga su redaccion. */
    fun crearArticulo(actor: Usuario, cuerpo: Map<*, *>): ArticuloSeo {
        val grupo = (cuerpo["grupo"] as? String)?.trim().orEmpty()
        repo.articuloDeGrupo(grupo)?.let { throw ReglaIncumplida("Ya hay un artículo para «$grupo» (${it.codigo}): ábrelo desde «Artículos».") }
        if (repo.tareasActivas().isNotEmpty()) throw ReglaIncumplida("Ya hay una tarea del Plan SEO en marcha. Espera a que termine o cancélala.")
        val codigo = nuevoArticulo(grupo, actor.codigo)
        return encargar(actor, codigo, cuerpo["indicaciones"] as? String)
    }

    /** Crea el articulo de un grupo de keywords (sin redactar). `forma`: como la escribe la gente, si Google lo dijo. */
    private fun nuevoArticulo(grupo: String, autor: String?, forma: String? = null): String {
        val kws = repo.keywords().filter { it.grupo == grupo }
        if (kws.isEmpty()) throw NoEncontrado("No hay keywords del grupo «$grupo». Vuelve a cargar la lista.")
        val principal = forma ?: kws.firstNotNullOfOrNull { it.canonica } ?: kws.first().keyword
        val variantes = kws.map { it.keyword }.filter { clave(it) != clave(principal) }.distinct()
        val origenes = kws.flatMap { it.origenes }.distinctBy { it["url"] }
        return repo.crearArticulo(grupo, principal, variantes, origenes, autor)
    }

    /** Vuelve a redactar (sustituye titulo y contenido), con nuevas indicaciones si las hay. */
    fun redactarDeNuevo(actor: Usuario, codigo: String, cuerpo: Map<*, *>): ArticuloSeo {
        val a = repo.articulo(codigo)
        if (repo.tareasActivas().isNotEmpty()) throw ReglaIncumplida("Ya hay una tarea del Plan SEO en marcha. Espera a que termine o cancélala.")
        return encargar(actor, a.codigo, if (cuerpo.containsKey("indicaciones")) cuerpo["indicaciones"] as? String else a.indicaciones)
    }

    private fun encargar(actor: Usuario, codigo: String, indicaciones: String?): ArticuloSeo {
        val ind = indicaciones?.trim()?.take(MAX_INDICACIONES)?.ifEmpty { null }
        val tarea = repo.crearTarea("ARTICULO", null, actor.codigo)
        repo.resumen(tarea, mapOf("articulo" to codigo))
        repo.redaccionEncargada(codigo, tarea, ind)
        encolar(tarea)
        return repo.articulo(codigo)
    }

    fun editarArticulo(codigo: String, cuerpo: Map<*, *>): ArticuloSeo {
        val a = repo.articulo(codigo)
        if (repo.tareasActivas().any { it.codigo == a.tarea }) throw ReglaIncumplida("La IA está redactando este artículo: espera a que termine.")
        val titulo = (cuerpo["titulo"] as? String)?.trim().orEmpty()
        val contenido = (cuerpo["contenido"] as? String)?.trim().orEmpty()
        if (titulo.isEmpty() || titulo.length > 200) throw ReglaIncumplida("El título va de 1 a 200 caracteres.")
        if (contenido.isEmpty()) throw ReglaIncumplida("El artículo no tiene contenido.")
        if (contenido.length > 200_000) throw ReglaIncumplida("El artículo es demasiado largo.")
        val slug = SectorSeo.palabras((cuerpo["slug"] as? String)?.ifBlank { null } ?: titulo).joinToString("-").take(90).trim('-')
        repo.editarArticulo(codigo, titulo, slug, (cuerpo["metaDescription"] as? String)?.trim().orEmpty().take(300), contenido)
        return repo.articulo(codigo)
    }

    fun borrarArticulo(actor: Usuario, codigo: String) {
        if (!actor.esAdmin) throw Prohibido("Solo un administrador puede borrar un artículo.")
        val a = repo.articulo(codigo)
        if (repo.tareasActivas().any { it.codigo == a.tarea }) throw ReglaIncumplida("La IA está redactando este artículo: cancela la tarea antes de borrarlo.")
        repo.borrarArticulo(codigo)
    }

    /** Markdown -> HTML con el mismo conversor que se usa al enviar a WordPress. */
    fun vistaPrevia(cuerpo: Map<*, *>): Json = worker.post("/seo/html", mapOf("contenido" to (cuerpo["contenido"] as? String).orEmpty()))

    // ── WordPress ─────────────────────────────────────────────────────────

    fun wordpress(): Json = worker.get("/wordpress")

    fun probarWordpress(): Json = worker.post("/wordpress/comprobar", emptyMap<String, Any>())

    /**
     * Envia el articulo a WordPress: la primera vez crea la entrada (borrador salvo que se
     * pida publicar); despues actualiza esa misma. Publicar en la web solo un admin.
     */
    fun enviarAWordpress(actor: Usuario, codigo: String, cuerpo: Map<*, *>): ArticuloSeo {
        val publicar = cuerpo["publicar"] == true
        if (publicar && !actor.esAdmin) throw Prohibido("Solo un administrador puede publicar en la web. Envíalo como borrador.")
        return enviar(codigo, publicar)
    }

    private fun enviar(codigo: String, publicar: Boolean): ArticuloSeo {
        val a = repo.articulo(codigo)
        val contenido = a.contenido ?: throw ReglaIncumplida("El artículo todavía no está redactado.")
        if (repo.tareasActivas().any { it.codigo == a.tarea }) throw ReglaIncumplida("La IA está redactando este artículo: espera a que termine.")
        val faltan = PENDIENTE.findAll(contenido).count()
        if (faltan > 0) {
            throw ReglaIncumplida("Quedan $faltan ${if (faltan == 1) "dato" else "datos"} por completar («[COMPLETAR: …]»). Escríbelos o quita esas frases antes de enviarlo.")
        }
        // La imagen viaja entera en cada envio: si ya se subio, el worker reutiliza la de WordPress y solo le pone alt y leyenda.
        val imagen = a.imagen?.let { i ->
            repo.archivoImagen(a.codigo)?.let { (datos, mime) ->
                mapOf("datos_b64" to Base64.getEncoder().encodeToString(datos), "mime" to mime, "alt" to i.alt.orEmpty(),
                    "leyenda" to i.leyenda.orEmpty(), "id_media" to i.wpMediaId)
            }
        }
        val wp = worker.post(
            "/wordpress/enviar",
            mapOf("titulo" to a.titulo, "slug" to a.slug.orEmpty(), "contenido" to contenido, "extracto" to a.metaDescription.orEmpty(),
                "publicar" to publicar, "id_wp" to a.wpId, "imagen" to imagen),
        )
        repo.marcarEnviado(codigo, wp)
        (wp["media"] as? Map<*, *>)?.let { repo.imagenSubida(codigo, (it["id"] as? Number)?.toLong()) }
        return repo.articulo(codigo)
    }

    // ── Imagen destacada ──────────────────────────────────────────────────

    /** Que fuentes hay: el banco de fotos (Pixabay o Pexels, clave gratuita) y Gemini (modelo y precio por imagen). */
    fun imagenes(): Json = worker.get("/imagenes")

    fun buscarImagenes(cuerpo: Map<*, *>): Json {
        val consulta = (cuerpo["consulta"] as? String)?.trim().orEmpty()
        if (consulta.length < 2) throw ReglaIncumplida("Escribe qué buscar (al menos 2 letras).")
        val pagina = ((cuerpo["pagina"] as? Number)?.toInt() ?: 1).coerceIn(1, 50)
        return worker.post("/imagenes/buscar", mapOf("consulta" to consulta.take(100), "pagina" to pagina))
    }

    fun imagenDelBanco(actor: Usuario, codigo: String, cuerpo: Map<*, *>): ArticuloSeo {
        val a = repo.articulo(codigo)
        val id = (cuerpo["id"] as? Number)?.toLong() ?: throw ReglaIncumplida("Elige una foto.")
        fotoDelBanco(a, id, cuerpo, actor.codigo)
        return repo.articulo(codigo)
    }

    private fun fotoDelBanco(a: ArticuloSeo, id: Long, cuerpo: Map<*, *>, codAutor: String?) {
        val f = worker.post("/imagenes/foto", mapOf("id" to id))
        val fuente = f["fuente"] as? String ?: "PIXABAY"
        val banco = fuente.lowercase().replaceFirstChar { it.uppercase() }
        val autor = (f["autor"] as? String)?.ifBlank { null }
        guardarImagen(
            codAutor, a, fuente, f, cuerpo, leyenda = autor?.let { "Foto: $it en $banco" } ?: "Foto de $banco",
            autor = autor, autorUrl = f["autor_url"] as? String, origenUrl = f["pagina_url"] as? String,
        )
    }

    /** Gemini no tiene plan gratuito de imagenes: sin facturacion el worker lo explica y no se guarda nada. */
    fun generarImagen(actor: Usuario, codigo: String, cuerpo: Map<*, *>): ArticuloSeo {
        val a = repo.articulo(codigo)
        val descripcion = (cuerpo["descripcion"] as? String)?.trim().orEmpty()
        if (descripcion.length !in 5..1000) throw ReglaIncumplida("Describe la imagen en 5 a 1000 caracteres.")
        val r = worker.post("/imagenes/generar", mapOf("descripcion" to descripcion, "negocio" to negocio(), "rubro" to rubro().descripcion))
        (r["uso"] as? Map<*, *>)?.let { consumo.registrar(a.codigo, "seo_imagen", it) }
        guardarImagen(actor.codigo, a, "GEMINI", r, cuerpo, leyenda = "Imagen generada con IA", prompt = descripcion, modelo = r["modelo"] as? String)
        return repo.articulo(codigo)
    }

    private fun guardarImagen(codAutor: String?, a: ArticuloSeo, fuente: String, r: Json, cuerpo: Map<*, *>, leyenda: String,
                              autor: String? = null, autorUrl: String? = null, origenUrl: String? = null, prompt: String? = null, modelo: String? = null) {
        val datos = Base64.getDecoder().decode(r["datos_b64"] as? String ?: throw ErrorDelWorker("El worker no devolvió la imagen."))
        val alt = (cuerpo["alt"] as? String)?.trim()?.ifEmpty { null } ?: a.titulo ?: a.keyword
        repo.guardarImagen(a.codigo, fuente, datos, r["mime"] as? String ?: "image/jpeg", alt.take(MAX_TEXTO_IMAGEN), leyenda.take(MAX_TEXTO_IMAGEN),
            autor, autorUrl, origenUrl, prompt, modelo, codAutor)
    }

    fun textosImagen(codigo: String, cuerpo: Map<*, *>): ArticuloSeo {
        val a = repo.articulo(codigo)
        if (a.imagen == null) throw NoEncontrado("El artículo no tiene imagen.")
        val alt = (cuerpo["alt"] as? String)?.trim().orEmpty()
        if (alt.isEmpty()) throw ReglaIncumplida("El texto alternativo describe la imagen para quien no la ve y para Google: no lo dejes vacío.")
        repo.textosImagen(codigo, alt.take(MAX_TEXTO_IMAGEN), (cuerpo["leyenda"] as? String)?.trim().orEmpty().take(MAX_TEXTO_IMAGEN))
        return repo.articulo(codigo)
    }

    fun quitarImagen(codigo: String): ArticuloSeo {
        repo.articulo(codigo)
        repo.quitarImagen(codigo)
        return repo.articulo(codigo)
    }

    fun archivoImagen(codigo: String): Pair<ByteArray, String> = repo.archivoImagen(codigo) ?: throw NoEncontrado("El artículo no tiene imagen.")

    /** Olvida la entrada de WordPress (si la borraron alla): el siguiente envio crea otra. */
    fun desvincular(codigo: String): ArticuloSeo {
        repo.articulo(codigo)
        repo.desvincular(codigo)
        return repo.articulo(codigo)
    }

    // ── Automatico: el flujo entero cada semana, hasta borrador en WordPress ──
    //
    // Decidido por la persona (2026-10-28): semanal, 2 articulos por vez, hasta borrador.
    // Publicar no se automatiza. Solo corre con el Radar abierto: si a la hora no lo estaba,
    // corre al abrirlo (la revision es cada 5 minutos).

    data class AjusteAutomatico(
        val activo: Boolean = false,
        /** 1 = lunes ... 7 = domingo. */
        val dia: Int = 1,
        val hora: String = "09:00",
        val articulos: Int = 2,
        /** Cuando se activo: la primera ejecucion es la siguiente cita despues de esto. */
        val desde: String? = null,
        val ultima: String? = null,
    )

    private fun ajusteAutomatico(): AjusteAutomatico =
        ajustes.leer(CLAVE_AUTOMATICO)?.let { runCatching { json.readValue(it, AjusteAutomatico::class.java) }.getOrNull() } ?: AjusteAutomatico()

    /** El primer `dia` a la `hora` (hora de Lima) despues de la ultima ejecucion o de cuando se activo. */
    private fun proxima(a: AjusteAutomatico): Instant? {
        if (!a.activo) return null
        val base = (a.ultima ?: a.desde)?.let(Instant::parse) ?: Instant.now()
        val hora = LocalTime.parse(a.hora)
        var d = base.atZone(LIMA).toLocalDate()
        while (true) {
            val cita = d.atTime(hora).atZone(LIMA).toInstant()
            if (d.dayOfWeek.value == a.dia && cita.isAfter(base)) return cita
            d = d.plusDays(1)
        }
    }

    fun estadoAutomatico(): Map<String, Any?> {
        val a = ajusteAutomatico()
        // Con las keywords de hoy; la ejecucion las regenera antes de elegir, asi que puede cambiar.
        val e = eleccion()
        return mapOf(
            "activo" to a.activo, "dia" to a.dia, "hora" to a.hora, "articulos" to a.articulos, "ultima" to a.ultima,
            "proxima" to proxima(a)?.toString(), "tarea" to repo.ultimaTarea("AUTOMATICO"),
            "candidatos" to e.candidatos.take(MAX_ARTICULOS_AUTO), "descartados" to e.descartados, "google" to e.google,
        )
    }

    fun guardarAutomatico(actor: Usuario, cuerpo: Map<*, *>): Map<String, Any?> {
        if (!actor.esAdmin) throw Prohibido("Solo un administrador puede programar el flujo automático.")
        val antes = ajusteAutomatico()
        val activo = cuerpo["activo"] as? Boolean ?: antes.activo
        val dia = (cuerpo["dia"] as? Number)?.toInt() ?: antes.dia
        val hora = (cuerpo["hora"] as? String)?.trim() ?: antes.hora
        val articulos = (cuerpo["articulos"] as? Number)?.toInt() ?: antes.articulos
        if (dia !in 1..7) throw ReglaIncumplida("Elige un día de la semana.")
        if (!HORA.matches(hora)) throw ReglaIncumplida("La hora va como HH:MM, de 00:00 a 23:59.")
        if (articulos !in 1..MAX_ARTICULOS_AUTO) throw ReglaIncumplida("De 1 a $MAX_ARTICULOS_AUTO artículos por ejecución.")
        val desde = if (activo && !antes.activo) Instant.now().toString() else antes.desde
        ajustes.guardar(CLAVE_AUTOMATICO, json.writeValueAsString(antes.copy(activo = activo, dia = dia, hora = hora, articulos = articulos, desde = desde)))
        return estadoAutomatico()
    }

    fun ejecutarAutomatico(actor: Usuario): TareaSeo {
        if (!actor.esAdmin) throw Prohibido("Solo un administrador puede lanzar el flujo automático.")
        return lanzarAutomatico(actor.codigo)
    }

    private fun lanzarAutomatico(autor: String): TareaSeo {
        if (repo.tareasActivas().isNotEmpty()) throw ReglaIncumplida("Ya hay una tarea del Plan SEO en marcha. Espera a que termine o cancélala.")
        val a = ajusteAutomatico()
        // La ultima se anota al lanzar: si luego se pausa, no se relanza cada 5 minutos.
        ajustes.guardar(CLAVE_AUTOMATICO, json.writeValueAsString(a.copy(ultima = Instant.now().toString())))
        val codigo = repo.crearTarea("AUTOMATICO", null, autor)
        repo.resumen(codigo, mapOf("articulosMax" to a.articulos))
        encolar(codigo)
        return repo.tarea(codigo)
    }

    @Scheduled(fixedDelayString = "PT5M", initialDelayString = "PT2M")
    fun revisarAutomatico() {
        val cita = proxima(ajusteAutomatico()) ?: return
        if (Instant.now().isBefore(cita) || repo.tareasActivas().isNotEmpty()) return
        log.info("Flujo automático del Plan SEO: toca (cita {})", cita)
        runCatching { lanzarAutomatico(AUTOR_AUTOMATICO) }.onFailure { log.warn("Flujo automático: {}", it.message) }
    }

    /** La sub-tarea que corre ahora dentro del automatico: cancelar el automatico la cancela tambien. */
    @Volatile
    private var subActual: String? = null

    /**
     * Encadena las tareas de siempre en este mismo hilo. Cada paso queda anotado en el resumen:
     * «Continuar» salta lo terminado y retoma lo que quedo en pausa.
     */
    @Suppress("UNCHECKED_CAST")
    private fun automatico(t: TareaSeo) {
        val r = (t.resumen ?: emptyMap()).toMutableMap()
        val pasos = (r["pasos"] as? Map<String, Any?>).orEmpty().toMutableMap()
        val avisos = (r["avisos"] as? List<String>).orEmpty().toMutableList()
        val articulos = (r["articulos"] as? List<String>).orEmpty().toMutableList()
        val enviados = (r["enviados"] as? List<String>).orEmpty().toMutableList()
        val esperan = (r["esperanDatos"] as? List<String>).orEmpty().toMutableList()
        val maximo = (r["articulosMax"] as? Number)?.toInt() ?: ajusteAutomatico().articulos
        fun guardar() {
            r += mapOf("pasos" to pasos, "avisos" to avisos.distinct(), "articulos" to articulos, "enviados" to enviados, "esperanDatos" to esperan)
            repo.resumen(t.codigo, r)
        }
        var n = 0

        /** Corre (o retoma) una sub-tarea. Devuelve la sub-tarea al acabar; CANCELADA cancela todo. */
        fun paso(clave: String, tipo: String, sitio: String?, mensaje: String, preparar: (String) -> Unit = {}): TareaSeo {
            comprobar(t.codigo)
            val previa = (pasos[clave] as? String)?.let { runCatching { repo.tarea(it) }.getOrNull() }
            if (previa?.estado == "TERMINADA") return previa
            val sub = previa?.takeIf { it.estado == "PAUSADA" }?.codigo ?: repo.crearTarea(tipo, sitio, AUTOR_AUTOMATICO).also(preparar)
            pasos[clave] = sub
            guardar()
            repo.avance(t.codigo, ++n, 0, mensaje)
            subActual = sub
            try {
                ejecutar(sub)
            } finally {
                subActual = null
            }
            val fin = repo.tarea(sub)
            if (fin.estado == "CANCELADA") throw Cancelada()
            return fin
        }

        fun parar(que: String, sub: TareaSeo): Nothing {
            guardar()
            throw ReglaIncumplida("Se detuvo en «$que»: ${sub.error ?: "en pausa"} Pulsa «Continuar» para seguir donde se quedó.")
        }

        // 1 · Inventario de cada sitio. Un sitio que frena (403/429) no para el resto.
        for (s in repo.sitios().filter { it.activo }) {
            val sub = paso("inventario:${s.codigo}", "INVENTARIO", s.codigo, "Inventario de ${s.nombre}…")
            if (sub.estado != "TERMINADA") avisos += "Inventario de ${s.nombre}: ${sub.error ?: "en pausa"}"
        }
        // 2 · Temas de lo nuevo o cambiado. Sin Gemini no hay nada que hacer despues: se para.
        for (s in repo.sitios().filter { it.activo && it.sinTemas > 0 }) {
            val sub = paso("temas:${s.codigo}", "TEMAS", s.codigo, "Temas de ${s.nombre}…")
            if (sub.estado != "TERMINADA") parar("Temas de ${s.nombre}", sub)
        }
        // 3 · Keywords y cobertura.
        paso("keywords", "KEYWORDS", null, "Generando keywords…").let { if (it.estado != "TERMINADA") parar("Generar keywords", it) }
        // 3b · Search Console, si esta conectado: lo que la web ya posiciona no se vuelve a escribir. Si falla, sigue sin el.
        if (pasos["gsc"] == null) {
            comprobar(t.codigo)
            val conectado = runCatching { worker.get("/gsc")["completo"] == true }.getOrDefault(false)
            pasos["gsc"] = if (!conectado) "sin conectar" else {
                repo.avance(t.codigo, ++n, 0, "Datos de Search Console…")
                runCatching { sincronizarGsc(); "ok" }.getOrElse { e -> avisos += "Search Console: ${e.message}"; "fallo" }
            }
            guardar()
        }

        // 4 · Articulos de los grupos que faltan en la web propia.
        if (r["elegidos"] != true) {
            val e = eleccion()
            for (c in e.candidatos.take(maximo)) articulos += nuevoArticulo(c.grupo, AUTOR_AUTOMATICO, c.keyword)
            r["elegidos"] = true
            r["descartados"] = e.descartados.map { it.keyword }
            if (!e.google) avisos += "No se pudo consultar a Google: se eligió solo por las páginas de competidores."
            if (articulos.isEmpty()) {
                avisos += if (e.descartados.isEmpty()) "No hay búsquedas informacionales sin cobertura que no tengan ya su artículo."
                else "Las búsquedas que faltan ya las posiciona tu web o no aparecen en las sugerencias de Google: no se redactó ninguna."
            }
            guardar()
        }
        val wpListo = runCatching { wordpress()["completo"] == true }.getOrDefault(false)
        if (!wpListo && articulos.isNotEmpty()) avisos += "WordPress no está conectado: los artículos se quedan en el Radar."
        for (cod in articulos) {
            val a = runCatching { repo.articulo(cod) }.getOrNull() ?: continue // lo borraron mientras tanto
            val sub = paso("articulo:$cod", "ARTICULO", null, "Redactando «${a.keyword}»…") { s ->
                repo.resumen(s, mapOf("articulo" to cod))
                repo.redaccionEncargada(cod, s, null)
            }
            if (sub.estado != "TERMINADA") parar("Redactar «${a.keyword}»", sub)

            // 5 · Imagen: la primera foto del banco para su busqueda. Si falla, va sin imagen.
            if (pasos["imagen:$cod"] == null) {
                comprobar(t.codigo)
                repo.avance(t.codigo, ++n, 0, "Imagen para «${a.keyword}»…")
                pasos["imagen:$cod"] = runCatching {
                    val foto = (buscarImagenes(mapOf("consulta" to a.keyword))["fotos"] as? List<*>)?.firstOrNull() as? Map<*, *>
                    val id = (foto?.get("id") as? Number)?.toLong() ?: return@runCatching "sin fotos"
                    fotoDelBanco(repo.articulo(cod), id, emptyMap<String, Any>(), AUTOR_AUTOMATICO)
                    "ok"
                }.getOrElse { e -> avisos += "Imagen de «${a.keyword}»: ${e.message}"; "fallo" }
                guardar()
            }
            // 6 · Borrador en WordPress, salvo que falten datos que solo sabe la persona.
            if (pasos["wordpress:$cod"] == null && wpListo) {
                comprobar(t.codigo)
                val redactado = repo.articulo(cod)
                pasos["wordpress:$cod"] = if (PENDIENTE.containsMatchIn(redactado.contenido.orEmpty())) {
                    esperan += cod
                    "espera datos"
                } else {
                    repo.avance(t.codigo, ++n, 0, "Enviando «${a.keyword}» a WordPress como borrador…")
                    runCatching { enviar(cod, publicar = false); enviados += cod; "borrador" }
                        .getOrElse { e -> avisos += "WordPress, «${a.keyword}»: ${e.message}"; "fallo" }
                }
                guardar()
            }
        }
        // 7 · Propuestas para mejorar paginas que ya aparecen en Google (Search Console). Las aplica la persona.
        val propuestas = (r["mejoras"] as? List<String>).orEmpty().toMutableList()
        if (pasos["mejoras"] == null && pasos["gsc"] == "ok") {
            for (o in oportunidades().filter { it.mejora == null }.take(MAX_MEJORAS_AUTO)) {
                comprobar(t.codigo)
                repo.avance(t.codigo, ++n, 0, "Propuesta de mejora para ${o.url}…")
                runCatching { mejorar(o, AUTOR_AUTOMATICO); propuestas += o.url }.onFailure { e -> avisos += "Mejora de ${o.url}: ${e.message}" }
            }
            r["mejoras"] = propuestas
            pasos["mejoras"] = "ok"
        }
        guardar()
        repo.avance(t.codigo, n, n, "")
        val partes = buildList {
            add(if (articulos.isEmpty()) "ningún artículo nuevo" else "${articulos.size} ${if (articulos.size == 1) "artículo redactado" else "artículos redactados"}")
            if (propuestas.isNotEmpty()) add("${propuestas.size} ${if (propuestas.size == 1) "propuesta" else "propuestas"} de mejora de páginas")
            if (enviados.isNotEmpty()) add("${enviados.size} en WordPress como borrador")
            if (esperan.isNotEmpty()) add("${esperan.size} ${if (esperan.size == 1) "espera" else "esperan"} tus datos («[COMPLETAR]»)")
            if (avisos.isNotEmpty()) add("${avisos.size} ${if (avisos.size == 1) "aviso" else "avisos"}")
        }
        repo.estadoTarea(t.codigo, "TERMINADA", mensaje = "Flujo automático: ${partes.joinToString(", ")}.")
    }

    /**
     * Un grupo que el automatico redactaria, con lo que decide su orden (se muestra en el panel).
     * `keyword`: como la escribe la gente si Google lo dijo; si no, la canonica del grupo.
     * `google`: EXACTA (Google sugiere esa busqueda), VARIANTES (sugiere busquedas que la contienen),
     * NINGUNA, o null si no se pudo consultar.
     */
    data class CandidatoArticulo(
        val grupo: String, val keyword: String, val busquedas: Int, val paginas: Int, val sitios: List<String>, val relevancia: Int,
        val google: String? = null, val sugerencias: List<String> = emptyList(),
        /** Lo que dice Search Console de la web propia para estas busquedas (null: no aparece o no esta conectado). */
        val gsc: DatoGsc? = null,
        /** Solo en los descartados: YA_POSICIONA, MEJORAR_PAGINA (Search Console) o GOOGLE_NO_SUGIERE. */
        val motivo: String? = null,
    )

    /** Search Console de un grupo: totales del periodo; `posicion`, media ponderada por impresiones; `url`, la que mas sale. */
    data class DatoGsc(val impresiones: Int, val clics: Int, val posicion: Double, val url: String)

    /** `google` = false si Google no respondio: entonces el orden es solo por competidores. */
    data class Eleccion(val candidatos: List<CandidatoArticulo>, val descartados: List<CandidatoArticulo>, val google: Boolean)

    /**
     * Los grupos a redactar: informacionales, sin cobertura en la web propia y sin articulo (ni
     * uno de otro grupo que responda la misma busqueda: los grupos cambian de nombre al regenerar).
     * Se descartan los que la web ya posiciona segun Search Console (top 10: ya esta; 11-20: mejor
     * mejorar esa pagina) y los que Google no sugiere (nadie los escribe). Orden: primero los que
     * Google sugiere tal cual, luego mas impresiones en Search Console, mas paginas de
     * competidores y, a igualdad, mas relevancia.
     */
    private fun eleccion(): Eleccion {
        val existentes = repo.articulos()
        val yaRedactadas = existentes.flatMap { listOf(it.keyword) + it.variantes }.map(::clave).toSet()
        val conArticulo = existentes.map { it.grupo }.toSet()
        val grupos = repo.keywords()
            .filter { it.intencion == "INFORMATIONAL" && it.cobertura == "SIN_COBERTURA" && it.grupo != null }
            .groupBy { it.grupo!! }
            .filter { (grupo, ks) -> grupo !in conArticulo && ks.none { k -> clave(k.keyword) in yaRedactadas || clave(k.canonica.orEmpty()) in yaRedactadas } }
        val formas = grupos.mapValues { (_, ks) -> (listOfNotNull(ks.firstNotNullOfOrNull { it.canonica }) + ks.map { it.keyword }).distinctBy(::clave) }
        val gsc = datosGsc(formas)
        val todos = grupos.map { (grupo, ks) ->
            val origenes = ks.flatMap { it.origenes }.distinctBy { it["url"] }
            CandidatoArticulo(
                grupo, formas[grupo]!!.first(), ks.size, origenes.size,
                origenes.mapNotNull { it["sitio"] as? String }.distinct(), ks.maxOf { it.relevancia ?: 0 }, gsc = gsc[grupo],
            )
        }.sortedWith(compareByDescending<CandidatoArticulo> { it.paginas }.thenByDescending { it.relevancia })
        val porGsc = todos.mapNotNull { c ->
            val g = c.gsc?.takeIf { it.impresiones >= MIN_IMPRESIONES_GSC } ?: return@mapNotNull null
            when {
                g.posicion <= 10.0 -> c.copy(motivo = "YA_POSICIONA")
                g.posicion <= 20.0 -> c.copy(motivo = "MEJORAR_PAGINA")
                else -> null
            }
        }
        val fuera = porGsc.map { it.grupo }.toSet()
        val base = todos.filter { it.grupo !in fuera }.take(MAX_REVISAR_GOOGLE)
        val orden = compareByDescending<CandidatoArticulo> { RANGO_GOOGLE[it.google] ?: 0 }
            .thenByDescending { it.gsc?.impresiones ?: 0 }.thenByDescending { it.paginas }.thenByDescending { it.relevancia }
        if (base.isEmpty()) return Eleccion(emptyList(), porGsc, google = true)

        val consulta = base.map { c -> mapOf("grupo" to c.grupo, "keywords" to formas[c.grupo]!!.take(10)) }
        val r = runCatching { worker.post("/seo/demanda", mapOf("grupos" to consulta, "pais" to PAIS_GOOGLE, "idioma" to "es")) }
            .onFailure { log.warn("Autocompletado de Google: {}", it.message) }.getOrNull()
        if (r?.get("disponible") != true) return Eleccion(base.sortedWith(orden), porGsc, google = false)
        val porGrupo = (r["grupos"] as? List<*>).orEmpty().filterIsInstance<Map<*, *>>().associateBy { it["grupo"] as? String }
        val revisados = base.map { c ->
            val g = porGrupo[c.grupo] ?: return@map c
            c.copy(keyword = (g["forma"] as? String)?.ifBlank { null } ?: c.keyword, google = g["senal"] as? String,
                sugerencias = (g["sugerencias"] as? List<*>).orEmpty().filterIsInstance<String>())
        }
        val (sinDemanda, validos) = revisados.partition { it.google == "NINGUNA" }
        return Eleccion(validos.sortedWith(orden), porGsc + sinDemanda.map { it.copy(motivo = "GOOGLE_NO_SUGIERE") }, google = true)
    }

    /** Por grupo, lo que Search Console dice de sus busquedas (mismas palabras, sin importar orden ni tildes). */
    private fun datosGsc(formas: Map<String, List<String>>): Map<String, DatoGsc> {
        val porOrden = repo.gscDe(formas.values.flatten().map(::orden)).groupBy { it.orden }
        return formas.mapNotNull { (grupo, ks) ->
            val filas = ks.map(::orden).distinct().flatMap { porOrden[it].orEmpty() }.distinctBy { it.consulta to it.url }
            val impresiones = filas.sumOf { it.impresiones }
            if (impresiones == 0) return@mapNotNull null
            val posicion = filas.sumOf { it.posicion * it.impresiones } / impresiones
            val url = filas.groupBy { it.url }.maxBy { (_, f) -> f.sumOf { it.impresiones } }.key
            grupo to DatoGsc(impresiones, filas.sumOf { it.clics }, Math.round(posicion * 10) / 10.0, url)
        }.toMap()
    }

    // ── Search Console de la web propia ───────────────────────────────────

    /** Configuracion (del worker), ultima sincronizacion, totales y lo que conviene mejorar. */
    fun searchConsole(): Map<String, Any?> {
        val conf = runCatching { worker.get("/gsc") }.getOrElse { mapOf("completo" to false, "faltan" to emptyList<String>(), "error" to it.message) }
        val sinc = ajustes.leer(CLAVE_GSC)?.let { runCatching { json.readValue(it, Map::class.java) }.getOrNull() }
        return mapOf("configuracion" to conf, "sincronizacion" to sinc, "resumen" to repo.resumenGsc(),
            "oportunidades" to oportunidades(), "marca" to marca(), "terminos" to terminos())
    }

    // ── Mejorar paginas propias que ya aparecen en Google ─────────────────
    //
    // Las busquedas sin marca en la posicion 4-20 dicen que pagina conviene pulir: subir de la 9
    // a la 3 suele traer mas visitas que un articulo nuevo. La IA propone titulo, descripcion e
    // ideas; la persona las aplica en WordPress (nada se cambia solo en una pagina publicada).

    /** Una pagina propia con busquedas sin marca en la posicion 4-20, con lo que se propuso para ella. */
    data class OportunidadPagina(
        val url: String, val impresiones: Int, val clics: Int, val ctr: Double, val posicion: Double, val consultas: List<FilaGsc>, val mejora: MejoraSeo?,
    )

    /**
     * Palabras de marca o de navegacion: una busqueda que las contiene la hace quien ya conoce la
     * marca, asi que no dice nada del contenido. Por defecto, el nombre del sitio propio sin las
     * palabras genericas, sus dominios y lo tipico de una intranet.
     */
    fun marca(): List<String> = ajustes.leer(CLAVE_MARCA)?.let { t -> runCatching { json.readValue(t, List::class.java).filterIsInstance<String>() }.getOrNull() }
        ?: marcaPorDefecto()

    private fun marcaPorDefecto(): List<String> {
        val propio = repo.sitios().firstOrNull { it.esPropio } ?: return NAVEGACION
        val nombre = clave(propio.nombre).split(" ").filter { it.length > 1 && it !in GENERICAS }.joinToString(" ")
        val dominios = propio.hosts.map { it.removePrefix("www.").substringBefore('.') }
        return (listOf(nombre) + dominios + NAVEGACION).filter { it.isNotBlank() }.distinct()
    }

    fun guardarMarca(actor: Usuario, cuerpo: Map<*, *>): Map<String, Any?> {
        if (!actor.esAdmin) throw Prohibido("Solo un administrador cambia las palabras de marca.")
        val palabras = (cuerpo["palabras"] as? List<*>).orEmpty().filterIsInstance<String>().map(::clave).filter { it.length >= 2 }.distinct()
        if (palabras.isEmpty()) throw ReglaIncumplida("Escribe al menos una palabra de marca (p. ej. el nombre de tu institución).")
        if (palabras.size > MAX_MARCA) throw ReglaIncumplida("Como máximo $MAX_MARCA palabras de marca.")
        ajustes.guardar(CLAVE_MARCA, json.writeValueAsString(palabras))
        return searchConsole()
    }

    /**
     * Terminos protegidos: carreras, sistemas y demas que ninguna propuesta puede renombrar ni
     * redefinir. El worker los escribe tal como estan aqui y rechaza la propuesta que los alarga.
     */
    fun terminos(): List<TerminoProtegido> = ajustes.leer(CLAVE_TERMINOS)?.let { t ->
        runCatching { json.readValue(t, List::class.java).filterIsInstance<Map<*, *>>().mapNotNull(::termino) }.getOrNull()
    } ?: TERMINOS_POR_DEFECTO

    private fun termino(m: Map<*, *>): TerminoProtegido? {
        val nombre = (m["nombre"] as? String)?.split(" ")?.filter { it.isNotBlank() }?.joinToString(" ").orEmpty()
        if (nombre.isEmpty()) return null
        val tipo = (m["tipo"] as? String)?.takeIf { it in TIPOS_TERMINO } ?: "OTRO"
        return TerminoProtegido(nombre, tipo, (m["descripcion"] as? String)?.trim().orEmpty())
    }

    fun guardarTerminos(actor: Usuario, cuerpo: Map<*, *>): Map<String, Any?> {
        if (!actor.esAdmin) throw Prohibido("Solo un administrador cambia los términos protegidos.")
        val terminos = (cuerpo["terminos"] as? List<*>).orEmpty().filterIsInstance<Map<*, *>>().mapNotNull(::termino)
        if (terminos.size > MAX_TERMINOS) throw ReglaIncumplida("Como máximo $MAX_TERMINOS términos protegidos.")
        terminos.firstOrNull { it.nombre.length !in 2..120 }?.let { throw ReglaIncumplida("«${it.nombre}»: el nombre va de 2 a 120 caracteres.") }
        terminos.firstOrNull { it.descripcion.length > 500 }?.let { throw ReglaIncumplida("La descripción de «${it.nombre}» pasa de 500 caracteres.") }
        terminos.groupBy { clave(it.nombre) }.values.firstOrNull { it.size > 1 }
            ?.let { throw ReglaIncumplida("«${it.first().nombre}» está repetido.") }
        ajustes.guardar(CLAVE_TERMINOS, json.writeValueAsString(terminos))
        return searchConsole()
    }

    private fun esMarca(consulta: String, marca: List<String>): Boolean {
        val c = " ${clave(consulta)} "
        return marca.any { c.contains(" ${clave(it)} ") }
    }

    fun oportunidades(maximo: Int = MAX_OPORTUNIDADES): List<OportunidadPagina> {
        val marca = marca()
        val mejoras = repo.mejoras().associateBy { it.url }
        return repo.gscEntre(POS_MEJORA_DESDE, POS_MEJORA_HASTA, MIN_IMPRESIONES_MEJORA)
            .filter { !esMarca(it.consulta, marca) }
            .groupBy { it.url }
            .map { (url, fs) ->
                val impresiones = fs.sumOf { it.impresiones }
                val clics = fs.sumOf { it.clics }
                OportunidadPagina(
                    url, impresiones, clics, Math.round(clics * 10000.0 / impresiones) / 10000.0,
                    Math.round(fs.sumOf { it.posicion * it.impresiones } / impresiones * 10) / 10.0,
                    fs.sortedByDescending { it.impresiones }.take(MAX_CONSULTAS_MEJORA), mejoras[url],
                )
            }
            .sortedByDescending { it.impresiones }
            .take(maximo)
    }

    /** Pide a la IA la propuesta para una pagina de la lista (sustituye la anterior, si la habia). */
    fun proponerMejora(actor: Usuario, cuerpo: Map<*, *>): MejoraSeo {
        val url = (cuerpo["url"] as? String)?.trim().orEmpty()
        val o = oportunidades(Int.MAX_VALUE).find { it.url == url }
            ?: throw NoEncontrado("Esa página no está entre las que conviene mejorar (Search Console, posición 4-20). Trae los datos de nuevo.")
        mejorar(o, actor.codigo)
        return repo.mejoras().first { it.url == url }
    }

    private fun mejorar(o: OportunidadPagina, autor: String?) {
        // Del inventario si se leyo; si no (otro subdominio, pagina nueva), se lee ahora.
        val actual = repo.datosPagina(o.url) ?: runCatching {
            val r = worker.post("/seo/paginas", mapOf("urls" to listOf(o.url), "pausa_s" to PAUSA_S))
            @Suppress("UNCHECKED_CAST")
            ((r["paginas"] as? List<*>)?.firstOrNull() as? Map<*, *>)?.get("datos") as? Json
        }.getOrNull() ?: emptyMap()
        val consultas = o.consultas.map { mapOf("consulta" to it.consulta, "impresiones" to it.impresiones, "clics" to it.clics, "posicion" to it.posicion) }
        val r = worker.post("/seo/mejora", mapOf("url" to o.url, "actual" to actual.filterKeys { it in CAMPOS_PAGINA }, "consultas" to consultas,
            "negocio" to negocio(), "rubro" to rubro().descripcion, "terminos" to terminos()))
        (r["uso"] as? Map<*, *>)?.let { consumo.registrar("MEJORA", "seo_mejora", it) }
        repo.guardarMejora(o.url, consultas, actual, r, autor)
    }

    fun estadoMejora(cuerpo: Map<*, *>): MejoraSeo {
        val url = (cuerpo["url"] as? String)?.trim().orEmpty()
        val estado = cuerpo["estado"] as? String
        if (estado !in ESTADOS_MEJORA) throw ReglaIncumplida("Estado no válido: usa ${ESTADOS_MEJORA.joinToString(", ")}.")
        if (!repo.estadoMejora(url, estado!!)) throw NoEncontrado("No hay propuesta para esa página.")
        return repo.mejoras().first { it.url == url }
    }

    fun comprobarSearchConsole(): Json = worker.post("/gsc/comprobar", emptyMap<String, Any>())

    fun sincronizarSearchConsole(): Map<String, Any?> {
        if (repo.tareasActivas().any { it.tipo == "AUTOMATICO" }) throw ReglaIncumplida("El flujo automático está en marcha y ya sincroniza Search Console.")
        sincronizarGsc()
        return searchConsole()
    }

    /** Trae los ultimos DIAS_GSC dias y reemplaza los anteriores. */
    private fun sincronizarGsc(): Int {
        val r = worker.post("/gsc/consultas", mapOf("dias" to DIAS_GSC))
        val filas = (r["filas"] as? List<*>).orEmpty().filterIsInstance<Map<*, *>>().mapNotNull { f ->
            val consulta = (f["consulta"] as? String)?.trim()?.ifEmpty { null } ?: return@mapNotNull null
            FilaGsc(consulta, orden(consulta), f["url"] as? String ?: "", (f["clics"] as? Number)?.toInt() ?: 0,
                (f["impresiones"] as? Number)?.toInt() ?: 0, (f["ctr"] as? Number)?.toDouble() ?: 0.0, (f["posicion"] as? Number)?.toDouble() ?: 0.0)
        }
        repo.reemplazarGsc(filas)
        ajustes.guardar(CLAVE_GSC, json.writeValueAsString(mapOf(
            "propiedad" to r["propiedad"], "desde" to r["desde"], "hasta" to r["hasta"], "pais" to r["pais"],
            "filas" to filas.size, "fecha" to Instant.now().toString(),
        )))
        // Cada corte queda guardado: el siguiente reemplaza los datos actuales, no el historial.
        guardarCorteGsc()
        return filas.size
    }

    /** Clave de comparacion con Search Console: normalizada y con las palabras ordenadas. */
    private fun orden(t: String): String = clave(t).split(" ").filter { it.isNotEmpty() }.sorted().joinToString(" ")

    // ── Lanzar, continuar, cancelar ───────────────────────────────────────

    fun lanzar(actor: Usuario, tipo: String, sitio: String?): TareaSeo {
        if (repo.tareasActivas().isNotEmpty()) throw ReglaIncumplida("Ya hay una tarea del Plan SEO en marcha. Espera a que termine o cancélala.")
        when (tipo) {
            "INVENTARIO" -> {
                val s = repo.sitio(sitio ?: throw ReglaIncumplida("Falta el sitio."))
                if (!s.activo) throw ReglaIncumplida("El sitio ${s.nombre} está desactivado.")
            }
            "TEMAS" -> {
                val s = repo.sitio(sitio ?: throw ReglaIncumplida("Falta el sitio."))
                if ((s.paginas["OK"] ?: 0) == 0) throw ReglaIncumplida("Primero haz el inventario de ${s.nombre}.")
                if (s.sinTemas == 0) throw ReglaIncumplida("Todas las páginas de ${s.nombre} ya tienen sus temas.")
            }
            "KEYWORDS" -> {
                val sitios = repo.sitios()
                if (sitios.none { !it.esPropio && it.conTemas > 0 }) {
                    throw ReglaIncumplida("Ningún competidor tiene temas todavía: haz su inventario y luego «Extraer temas».")
                }
                if (sitios.none { it.esPropio && (it.paginas["OK"] ?: 0) > 0 }) {
                    throw ReglaIncumplida("Falta el inventario del sitio propio: sin él no se puede saber qué ya está cubierto.")
                }
            }
            else -> throw ReglaIncumplida("Tarea desconocida: $tipo.")
        }
        val codigo = repo.crearTarea(tipo, sitio.takeIf { tipo != "KEYWORDS" }, actor.codigo)
        encolar(codigo)
        return repo.tarea(codigo)
    }

    fun continuar(codigo: String): TareaSeo {
        val t = repo.tarea(codigo)
        if (t.estado != "PAUSADA") throw ReglaIncumplida("Solo se puede continuar una tarea en pausa.")
        if (repo.tareasActivas().isNotEmpty()) throw ReglaIncumplida("Ya hay una tarea del Plan SEO en marcha.")
        encolar(codigo)
        return repo.tarea(codigo)
    }

    fun cancelar(codigo: String): TareaSeo {
        val t = repo.tarea(codigo)
        when {
            t.activa -> {
                cancelados += codigo
                if (t.tipo == "AUTOMATICO") subActual?.let { cancelados += it }
            }
            t.estado == "PAUSADA" -> repo.estadoTarea(codigo, "CANCELADA", mensaje = "Cancelada")
            else -> throw ReglaIncumplida("La tarea ya terminó.")
        }
        return repo.tarea(codigo)
    }

    // ── Ejecucion ─────────────────────────────────────────────────────────

    private fun encolar(codigo: String) {
        cancelados -= codigo
        repo.estadoTarea(codigo, "EN_COLA", mensaje = "En cola…", limpiarError = true)
        cola.submit { ejecutar(codigo) }
    }

    private fun ejecutar(codigo: String) {
        try {
            comprobar(codigo)
            val t = repo.tarea(codigo)
            repo.estadoTarea(codigo, "CORRIENDO", limpiarError = true)
            when (t.tipo) {
                "INVENTARIO" -> inventario(t)
                "TEMAS" -> temas(t)
                "KEYWORDS" -> keywords(t)
                "ARTICULO" -> redactar(t)
                "AUTOMATICO" -> automatico(t)
            }
        } catch (e: Cancelada) {
            repo.estadoTarea(codigo, "CANCELADA", mensaje = "Cancelada. Lo hecho hasta aquí está guardado.")
        } catch (e: ErrorDelWorker) {
            repo.estadoTarea(codigo, "PAUSADA", error = e.message)
        } catch (e: ReglaIncumplida) {
            repo.estadoTarea(codigo, "PAUSADA", error = e.message)
        } catch (e: Exception) {
            log.error("Fallo inesperado en la tarea SEO {}", codigo, e)
            repo.estadoTarea(codigo, "PAUSADA", error = "Error inesperado: ${e.message ?: e.javaClass.simpleName}. Lo hecho está guardado.")
        } finally {
            cancelados -= codigo
        }
    }

    private fun comprobar(codigo: String) {
        if (codigo in cancelados) throw Cancelada()
    }

    // 1 · Inventario: robots.txt + sitemaps + una pagina a la vez

    @Suppress("UNCHECKED_CAST")
    private fun inventario(t: TareaSeo) {
        val sitio = repo.sitio(t.sitio!!)
        repo.avance(t.codigo, 0, 0, "Leyendo robots.txt y sitemaps de ${sitio.nombre}…")
        val d = worker.post("/seo/descubrir", mapOf("hosts" to sitio.hosts, "maximo" to MAX_URLS))
        val urls = (d["urls"] as? List<*>).orEmpty().mapNotNull { it as? Json }
        val registro = repo.registrarDescubrimiento(sitio.codigo, urls, mapOf("sitemaps" to d["sitemaps"], "avisos" to d["avisos"]))
        // Lo anterior a la fecha minima no se descarga (segun el lastmod del sitemap).
        val minima = fechaMinima()
        var antiguas = repo.aplicarFechaMinima(minima, sitio.codigo).first
        comprobar(t.codigo)

        val pendientes = repo.pendientes(sitio.codigo, sitio.maxPaginas)
        var hechas = 0
        var frenado = false
        for (lote in pendientes.chunked(LOTE_PAGINAS)) {
            comprobar(t.codigo)
            repo.avance(t.codigo, hechas, pendientes.size, "Leyendo páginas de ${sitio.nombre} ($hechas de ${pendientes.size})…")
            val r = worker.post("/seo/paginas", mapOf("urls" to lote, "pausa_s" to PAUSA_S))
            (r["paginas"] as? List<*>).orEmpty().mapNotNull { it as? Json }.forEach(repo::guardarExtraccion)
            hechas += lote.size
            if (r["frenar"] == true) {
                frenado = true
                break
            }
        }
        // Y lo que al leerlo dice que se publico antes, tampoco pasa a temas ni keywords.
        antiguas += repo.aplicarFechaMinima(minima, sitio.codigo).first
        val despues = repo.sitio(sitio.codigo)
        val quedan = repo.contarPendientes(sitio.codigo)
        repo.resumen(
            t.codigo,
            mapOf(
                "declaradas" to registro.total, "nuevas" to registro.nuevas, "aRevisar" to registro.reactivadas,
                "excluidas" to registro.excluidas, "retiradas" to registro.retiradas, "leidas" to hechas, "antiguas" to antiguas,
                "ok" to (despues.paginas["OK"] ?: 0), "quedan" to quedan,
            ),
        )
        repo.avance(t.codigo, hechas, pendientes.size, "")
        when {
            frenado -> repo.estadoTarea(
                t.codigo, "PAUSADA",
                error = "${sitio.nombre} respondió que paremos (403 o 429). Se dejó de leer para no insistir; prueba más tarde con «Continuar».",
            )
            quedan > 0 -> repo.estadoTarea(
                t.codigo, "TERMINADA",
                mensaje = "Leídas $hechas páginas. Quedan $quedan por el máximo de ${sitio.maxPaginas} por inventario: vuelve a inventariar para seguir.",
            )
            else -> repo.estadoTarea(t.codigo, "TERMINADA", mensaje = "Inventario completo: ${despues.paginas["OK"] ?: 0} páginas leídas de ${sitio.nombre}.")
        }
    }

    // 2 · Temas por pagina (IA)

    @Suppress("UNCHECKED_CAST")
    private fun temas(t: TareaSeo) {
        val sitio = repo.sitio(t.sitio!!)
        // De un competidor, lo que no habla del sector se marca sin IA (gratis); del sitio propio va todo.
        val rubro = rubro()
        val (paginas, fuera) = repo.paginasSinTemas(sitio.codigo).partition { (url, d) -> sitio.esPropio || SectorSeo.delSector(url, d, rubro.palabras) }
        fuera.forEach { (url, _) -> repo.guardarTemas(url, SectorSeo.FUERA) }
        var hechas = 0
        for (lote in paginas.chunked(LOTE_TEMAS)) {
            comprobar(t.codigo)
            repo.avance(t.codigo, hechas, paginas.size, "Leyendo de qué trata cada página ($hechas de ${paginas.size})…")
            val entrada = lote.map { (url, d) ->
                mapOf("url" to url, "title" to d["title"], "meta_description" to d["meta_description"], "h1" to d["h1"], "h2" to d["h2"], "extracto" to d["extracto"])
            }
            val r = worker.post("/seo/temas", mapOf("paginas" to entrada, "negocio" to negocio(), "rubro" to rubro.descripcion))
            (r["uso"] as? Map<*, *>)?.let { consumo.registrar(t.codigo, "seo_temas", it) }
            (r["temas"] as? List<*>).orEmpty().mapNotNull { it as? Json }.forEach { tema ->
                (tema["url"] as? String)?.let { repo.guardarTemas(it, tema - "url") }
            }
            hechas += lote.size
        }
        repo.avance(t.codigo, hechas, paginas.size, "")
        val s = repo.sitio(sitio.codigo)
        repo.resumen(t.codigo, mapOf("paginas" to hechas, "fueraDelSector" to fuera.size, "conTemas" to s.conTemas))
        val sinIa = if (fuera.isEmpty()) "" else "; ${fuera.size} fuera del sector, marcadas sin IA"
        repo.estadoTarea(t.codigo, "TERMINADA", mensaje = "Temas extraídos de $hechas páginas de ${sitio.nombre}$sinIa.")
    }

    // 3 · Keywords candidatas: intencion, grupos y cobertura en el sitio propio (IA)

    private data class Candidata(val keyword: String, val origenes: MutableList<Map<String, String>>)

    @Suppress("UNCHECKED_CAST")
    private fun keywords(t: TareaSeo) {
        val nombres = repo.sitios().associate { it.codigo to it.nombre }
        val candidatas = LinkedHashMap<String, Candidata>()
        for (p in repo.paginasOk("COMPETIDOR")) {
            val temas = p.temas ?: continue
            if (((temas["relevancia"] as? Number)?.toInt() ?: 0) < RELEVANCIA_MINIMA) continue
            for (c in (temas["consultas"] as? List<*>).orEmpty().mapNotNull { it as? String }) {
                val clave = clave(c).takeIf { it.length >= 3 } ?: continue
                val cand = candidatas.getOrPut(clave) { Candidata(c, mutableListOf()) }
                if (cand.origenes.none { it["url"] == p.url }) cand.origenes += mapOf("sitio" to (nombres[p.sitio] ?: p.sitio), "url" to p.url)
            }
        }
        if (candidatas.isEmpty()) {
            throw ReglaIncumplida("Las páginas de los competidores no tocan ninguna búsqueda informacional relevante. No hay keywords que proponer con esta evidencia.")
        }
        val elegidas = candidatas.entries.sortedByDescending { it.value.origenes.size }.take(MAX_CANDIDATAS)
        val propias = repo.paginasOk("PROPIO").map { p ->
            val d = p.datos.orEmpty()
            mapOf("url" to p.url, "title" to d["title"], "h1" to d["h1"], "h2" to (d["h2"] as? List<*>).orEmpty().take(6), "tema" to p.temas?.get("tema"))
        }
        val lotesAgrupar = elegidas.chunked(LOTE_AGRUPAR)
        var total = lotesAgrupar.size
        var hechos = 0

        // Intencion y grupos. Los grupos ya creados pasan al lote siguiente para que no se dupliquen.
        val clasificadas = LinkedHashMap<String, Json>()
        val grupos = LinkedHashSet<String>()
        for (lote in lotesAgrupar) {
            comprobar(t.codigo)
            repo.avance(t.codigo, hechos, total, "Clasificando la intención de ${elegidas.size} búsquedas…")
            val r = worker.post(
                "/seo/agrupar",
                mapOf("keywords" to lote.map { it.value.keyword }, "grupos" to grupos.toList().takeLast(300), "negocio" to negocio(), "rubro" to rubro().descripcion),
            )
            (r["uso"] as? Map<*, *>)?.let { consumo.registrar(t.codigo, "seo_agrupar", it) }
            (r["keywords"] as? List<*>).orEmpty().mapNotNull { it as? Json }.forEach { k ->
                val c = clave(k["keyword"] as? String ?: return@forEach)
                clasificadas[c] = k
                (k["grupo"] as? String)?.let(grupos::add)
            }
            hechos++
        }

        // Cobertura: solo de los grupos informacionales (o dudosos), que son los candidatos a artículo.
        val porGrupo = clasificadas.values.filter { it["intencion"] in setOf("INFORMATIONAL", "NEEDS_REVIEW") }.groupBy { it["grupo"] as String }
        val gruposEntrada = porGrupo.map { (g, ks) -> mapOf("grupo" to g, "canonica" to (ks.first()["canonica"] ?: g), "keywords" to ks.map { it["keyword"] }) }
        val lotesCobertura = gruposEntrada.chunked(LOTE_COBERTURA)
        total += lotesCobertura.size
        val cobertura = HashMap<String, Json>()
        for (lote in lotesCobertura) {
            comprobar(t.codigo)
            repo.avance(t.codigo, hechos, total, "Comparando ${gruposEntrada.size} grupos con las ${propias.size} páginas propias…")
            val r = worker.post("/seo/cobertura", mapOf("grupos" to lote, "propias" to propias))
            (r["uso"] as? Map<*, *>)?.let { consumo.registrar(t.codigo, "seo_cobertura", it) }
            (r["cobertura"] as? List<*>).orEmpty().mapNotNull { it as? Json }.forEach { c -> (c["grupo"] as? String)?.let { cobertura[it] = c } }
            hechos++
        }

        val filas = elegidas.mapNotNull { (clave, cand) ->
            val k = clasificadas[clave] ?: return@mapNotNull null
            val c = cobertura[k["grupo"] as? String]
            mapOf(
                "clave" to clave, "keyword" to cand.keyword, "origenes" to cand.origenes, "intencion" to k["intencion"], "grupo" to k["grupo"],
                "canonica" to k["canonica"], "relevancia" to k["relevancia"], "motivo" to k["motivo"],
                "cobertura" to c?.get("estado"), "url_propia" to c?.get("url"), "motivo_cobertura" to c?.get("motivo"),
            )
        }
        repo.reemplazarKeywords(filas, t.codigo)
        val informacionales = filas.count { it["intencion"] == "INFORMATIONAL" }
        val estados = cobertura.values.groupingBy { it["estado"] as? String ?: "INCIERTO" }.eachCount()
        repo.resumen(
            t.codigo,
            mapOf(
                "candidatas" to candidatas.size, "evaluadas" to filas.size, "informacionales" to informacionales, "grupos" to porGrupo.size,
                "sinCobertura" to (estados["SIN_COBERTURA"] ?: 0), "parcial" to (estados["PARCIAL"] ?: 0),
                "cubierta" to (estados["YA_CUBIERTA"] ?: 0), "incierto" to (estados["INCIERTO"] ?: 0),
            ),
        )
        repo.avance(t.codigo, hechos, total, "")
        guardarKeywords(t.codigo, repo.tarea(t.codigo).resumen)
        repo.estadoTarea(
            t.codigo, "TERMINADA",
            mensaje = "${filas.size} keywords candidatas: $informacionales informacionales en ${porGrupo.size} grupos; ${estados["SIN_COBERTURA"] ?: 0} grupos sin cobertura en el sitio propio.",
        )
    }

    // 4 · Articulo para el sitio propio (IA)

    private fun redactar(t: TareaSeo) {
        val a = repo.articuloDeTarea(t.codigo) ?: throw ReglaIncumplida("El artículo de esta tarea ya no existe.")
        repo.avance(t.codigo, 0, 1, "Redactando «${a.keyword}»…")
        // Paginas de competidores que tocan el tema: una por sitio primero, hasta cinco.
        val competidores = a.origenes.sortedBy { o -> a.origenes.filter { it["sitio"] == o["sitio"] }.indexOf(o) }
            .mapNotNull { o ->
                val url = o["url"] as? String ?: return@mapNotNull null
                repo.datosPagina(url)?.let { d -> mapOf("url" to url, "title" to d["title"], "h2" to d["h2"], "extracto" to d["extracto"]) }
            }.take(5)
        // Paginas propias para enlazar: las que comparten mas palabras con las busquedas.
        val buscadas = (listOf(a.keyword) + a.variantes).flatMap { SectorSeo.palabras(it) }.filter { it.length >= 4 }.toSet()
        val propias = repo.paginasOk("PROPIO").map { p ->
            val d = p.datos.orEmpty()
            val texto = SectorSeo.palabras("${d["title"] ?: ""} ${d["h1"] ?: ""} ${p.url}").toSet()
            Triple(p, d, buscadas.count { it in texto })
        }.filter { it.third > 0 }.sortedByDescending { it.third }.take(MAX_ENLAZABLES)
            .map { (p, d, _) -> mapOf("url" to p.url, "title" to (d["title"] ?: d["h1"])) }
        comprobar(t.codigo)
        val r = worker.post(
            "/seo/articulo",
            mapOf("keyword" to a.keyword, "variantes" to a.variantes.take(15), "competidores" to competidores, "propias" to propias,
                "negocio" to negocio(), "rubro" to rubro().descripcion, "indicaciones" to a.indicaciones.orEmpty()),
        )
        (r["uso"] as? Map<*, *>)?.let { consumo.registrar(t.codigo, "seo_articulo", it) }
        comprobar(t.codigo)
        repo.guardarRedaccion(a.codigo, r)
        val quitados = (r["enlaces_quitados"] as? List<*>).orEmpty().size
        repo.resumen(t.codigo, mapOf("articulo" to a.codigo, "pendientes" to (r["pendientes"] as? List<*>).orEmpty().size, "enlacesQuitados" to quitados))
        repo.avance(t.codigo, 1, 1, "")
        repo.estadoTarea(t.codigo, "TERMINADA", mensaje = "Artículo redactado: «${r["titulo"]}». Revísalo antes de enviarlo a WordPress.")
    }

    private fun clave(t: String): String =
        Normalizer.normalize(t.lowercase(), Normalizer.Form.NFD).replace(Regex("\\p{M}"), "")
            .replace(Regex("[^a-z0-9ñ ]"), " ").replace(Regex("\\s+"), " ").trim()

    private companion object {
        /** Sitios del plan maestro (§4). CENFOTUR son dos hosts de una misma entidad. */
        val SITIOS = listOf(
            Triple("ILCB", "Instituto Le Cordon Bleu Perú", "PROPIO" to listOf("ilcb.edu.pe")),
            Triple("DGALLIA", "D'Gallia", "COMPETIDOR" to listOf("dgallia.edu.pe")),
            Triple("CENFOTUR", "CENFOTUR", "COMPETIDOR" to listOf("www.cenfotur.edu.pe", "aprendeturismo.cenfotur.edu.pe")),
            Triple("USIL", "USIL", "COMPETIDOR" to listOf("usil.edu.pe")),
        )
        const val CLAVE_RUBRO = "seo_rubro"
        const val CLAVE_AUTOMATICO = "seo_automatico"
        const val AUTOR_AUTOMATICO = "AUTOMATICO"
        const val MAX_ARTICULOS_AUTO = 5
        /** Cuantos grupos se pasan por el autocompletado de Google antes de elegir (los primeros por competidores). */
        const val MAX_REVISAR_GOOGLE = 20
        const val PAIS_GOOGLE = "PE"
        const val CLAVE_GSC = "seo_gsc"
        const val CLAVE_FECHA_MINIMA = "seo_fecha_minima"
        const val SEARCH_CONSOLE = "SEARCH_CONSOLE"
        const val PLAN_SEO_KEYWORDS = "PLAN_SEO_KEYWORDS"
        val MODULOS_INFORME = setOf(SEARCH_CONSOLE, PLAN_SEO_KEYWORDS, "MEDICION")
        val CAMPOS_SINC = listOf("propiedad", "desde", "hasta", "pais", "fecha")
        val COLUMNAS_MEDICION = listOf("nombre", "tipo", "linea", "canal", "producto", "gasto", "impresiones", "clicsEnlace", "ctr", "leads",
            "conversaciones", "resultados", "costoResultado", "gastoAnterior", "costoAnterior", "cambioCosto")
        val COLUMNAS_GSC = listOf("consulta", "url", "clics", "impresiones", "ctr", "posicion")
        val COLUMNAS_KEYWORDS = listOf("keyword", "grupo", "canonica", "intencion", "relevancia", "cobertura", "urlPropia", "motivoCobertura",
            "origenes", "evidencia", "motivo")
        const val DIAS_GSC = 90
        /** Menos impresiones que esto no basta para decidir nada. */
        const val MIN_IMPRESIONES_GSC = 10
        const val CLAVE_MARCA = "seo_marca"
        const val CLAVE_TERMINOS = "seo_terminos"
        const val MAX_TERMINOS = 100
        val TIPOS_TERMINO = setOf("CARRERA", "SISTEMA", "OTRO")
        /** Las carreras y programas como los escribe ilcb.edu.pe (/carreras/ y /programas-master/, noviembre de 2026). */
        val TERMINOS_POR_DEFECTO = listOf(
            "Gastronomía", "Administración de Servicios de Hostelería y Restaurantes", "Pastelería", "Bar y Coctelería", "Cocina",
            "Master Cuisine", "Master Patisserie",
        ).map { TerminoProtegido(it, "CARRERA", "") }
        const val MAX_MARCA = 60
        /** Palabras que no identifican a nadie en el nombre de un sitio («Instituto Le Cordon Bleu Perú» → «cordon bleu»). */
        val GENERICAS = setOf("instituto", "escuela", "universidad", "academia", "colegio", "centro", "peru", "lima", "de", "del", "la", "las",
            "el", "los", "le", "y", "en", "sac", "eirl")
        val NAVEGACION = listOf("intranet", "campus", "aula virtual", "login", "matricula", "pension")
        const val POS_MEJORA_DESDE = 4.0
        const val POS_MEJORA_HASTA = 20.0
        const val MIN_IMPRESIONES_MEJORA = 30
        const val MAX_OPORTUNIDADES = 15
        const val MAX_CONSULTAS_MEJORA = 8
        const val MAX_MEJORAS_AUTO = 2
        val ESTADOS_MEJORA = setOf("PROPUESTA", "APLICADA", "DESCARTADA")
        val CAMPOS_PAGINA = setOf("title", "meta_description", "h1", "h2", "extracto")
        private val RANGO_GOOGLE = mapOf("EXACTA" to 2, "VARIANTES" to 1)
        val HORA = Regex("""^([01]\d|2[0-3]):[0-5]\d$""")
        val LIMA: ZoneId = ZoneId.of("America/Lima")
        const val MAX_PALABRAS = 80
        const val MAX_INDICACIONES = 1500
        const val MAX_ENLAZABLES = 15
        const val MAX_TEXTO_IMAGEN = 300
        val PENDIENTE = Regex("\\[COMPLETAR:[^\\]\\n]*\\]", RegexOption.IGNORE_CASE)
        val HOST = Regex("^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")
        const val MAX_HOSTS = 5
        const val MAX_URLS = 5000
        const val LOTE_PAGINAS = 8
        const val PAUSA_S = 1.0
        const val LOTE_TEMAS = 12
        const val LOTE_AGRUPAR = 150
        const val LOTE_COBERTURA = 40
        const val MAX_CANDIDATAS = 600
        /** Por debajo, la pagina no tiene que ver con lo que ensena una escuela de cocina (p. ej. ingenieria en USIL). */
        const val RELEVANCIA_MINIMA = 40
    }
}
