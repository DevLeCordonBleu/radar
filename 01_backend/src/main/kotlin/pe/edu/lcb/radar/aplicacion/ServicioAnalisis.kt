package pe.edu.lcb.radar.aplicacion

import org.slf4j.LoggerFactory
import org.springframework.beans.factory.annotation.Qualifier
import org.springframework.boot.context.event.ApplicationReadyEvent
import org.springframework.context.event.EventListener
import org.springframework.stereotype.Service
import pe.edu.lcb.radar.dominio.Analisis
import pe.edu.lcb.radar.dominio.Avance
import pe.edu.lcb.radar.dominio.Candidato
import pe.edu.lcb.radar.dominio.Competidor
import pe.edu.lcb.radar.dominio.Estado
import pe.edu.lcb.radar.dominio.Fase
import pe.edu.lcb.radar.dominio.Json
import pe.edu.lcb.radar.dominio.Marca
import pe.edu.lcb.radar.dominio.PaginaMeta
import pe.edu.lcb.radar.dominio.Pendiente
import pe.edu.lcb.radar.dominio.Peticion
import pe.edu.lcb.radar.dominio.ReglaIncumplida
import pe.edu.lcb.radar.infraestructura.ClienteWorker
import pe.edu.lcb.radar.infraestructura.ErrorDelWorker
import pe.edu.lcb.radar.infraestructura.RepositorioAnalisis
import pe.edu.lcb.radar.infraestructura.RepositorioConsumo
import pe.edu.lcb.radar.infraestructura.RepositorioInformes
import java.util.Base64
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.ExecutorService
import kotlin.math.ceil

/**
 * El ciclo de un analisis: buscar -> identificar competidores -> clasificar
 * -> agrupar en territorios -> informe.
 *
 * Todo lo que cuesta (Apify, Gemini) deja un checkpoint antes de seguir, y
 * cualquier fallo PAUSA en vez de dar por perdido: "continuar" retoma donde se
 * quedo, sin repetir la busqueda ni pagar de nuevo lo ya clasificado. Es la
 * misma promesa del Radar original ("lo analizado esta guardado").
 */
@Service
class ServicioAnalisis(
    private val repo: RepositorioAnalisis,
    private val informes: RepositorioInformes,
    private val consumo: RepositorioConsumo,
    private val worker: ClienteWorker,
    @Qualifier("colaAnalisis") private val cola: ExecutorService,
) {
    private val log = LoggerFactory.getLogger(javaClass)

    /** Se pidio cancelar este analisis: el hilo lo comprueba entre pasos. */
    private val cancelados = ConcurrentHashMap.newKeySet<String>()

    /** Busqueda de Apify en curso (run, token) por analisis, para abortarla al cancelar. */
    private val busquedas = ConcurrentHashMap<String, Pair<String, Int>>()

    private class Cancelado : RuntimeException()

    // ── Casos de uso ──────────────────────────────────────────────────────

    data class Estimacion(val anuncios: Int, val llamadas: Int, val costoGeminiUsd: Double, val costoApifyUsd: Double, val minutos: Int)

    fun estimar(p: Peticion): Estimacion {
        val n = p.maximo
        val llamadas = ceil(n / LOTE.toDouble()).toInt() + 1
        return Estimacion(
            anuncios = n,
            llamadas = llamadas,
            costoGeminiUsd = n * (TOKENS_ENTRADA * PRECIO_ENTRADA + TOKENS_SALIDA * PRECIO_SALIDA) / 1e6,
            costoApifyUsd = APIFY_POR_INFORME * n / 100.0,
            minutos = 2 + ceil(llamadas * 0.6).toInt(),
        )
    }

    fun crear(p: Peticion): Analisis {
        val limpia = validar(p)
        val a = repo.crear(limpia)
        encolar(a.codigo, cerrar = false)
        return a
    }

    fun listar(): List<Analisis> = repo.todos()

    fun obtener(codigo: String): Analisis = repo.buscar(codigo)

    /** Retoma un analisis pausado desde su checkpoint. */
    fun continuar(codigo: String): Analisis {
        val a = repo.buscar(codigo)
        if (a.estado != Estado.PAUSADO) throw ReglaIncumplida("Solo se puede continuar un analisis pausado.")
        if (a.pendiente != null) throw ReglaIncumplida("Antes de continuar hay que elegir la pagina de ${a.pendiente.competidor}.")
        encolar(codigo, cerrar = false)
        return repo.buscar(codigo)
    }

    /** Termina con lo ya clasificado en vez de esperar a que Gemini recupere su cuota. */
    fun terminarYa(codigo: String): Analisis {
        val a = repo.buscar(codigo)
        if (a.estado != Estado.PAUSADO) throw ReglaIncumplida("Solo se puede terminar un analisis pausado.")
        val av = repo.avance(codigo)
        if (av.clasificadas.values.none { it["relevante"] == true }) {
            throw ReglaIncumplida("Todavia no hay ningun anuncio clasificado: no hay nada con que hacer un informe.")
        }
        encolar(codigo, cerrar = true)
        return repo.buscar(codigo)
    }

    /**
     * La persona elige cual(es) de las paginas candidatas son el competidor: una marca
     * suele tener varias (sedes, talleres...). Vacio = ninguna. Se guardan separadas por comas.
     */
    fun elegirPagina(codigo: String, competidor: String, pageIds: List<String>): Analisis {
        val a = repo.buscar(codigo)
        val pend = a.pendiente ?: throw ReglaIncumplida("Este analisis no espera ninguna eleccion.")
        if (pend.competidor != competidor) throw ReglaIncumplida("Se esperaba la eleccion de ${pend.competidor}.")
        val ids = pageIds.map { it.trim() }.filter { it.isNotEmpty() }.distinct()
        if (ids.any { id -> pend.candidatos.none { it.pageId == id } }) {
            throw ReglaIncumplida("Esa pagina no esta entre las candidatas.")
        }
        val av = repo.avance(codigo)
        repo.guardarAvance(codigo, av.copy(paginas = av.paginas + (competidor to ids.joinToString(","))))
        repo.pendiente(codigo, null)
        encolar(codigo, cerrar = false)
        return repo.buscar(codigo)
    }

    fun cancelar(codigo: String): Analisis {
        val a = repo.buscar(codigo)
        when (a.estado) {
            Estado.TERMINADO, Estado.CANCELADO -> throw ReglaIncumplida("Este analisis ya ha terminado.")
            Estado.PAUSADO -> repo.estado(codigo, Estado.CANCELADO, mensaje = "Cancelado")
            else -> {
                cancelados += codigo
                busquedas[codigo]?.let { (run, t) -> runCatching { worker.post("/anuncios/abortar", mapOf("run" to run, "t" to t)) } }
            }
        }
        return repo.buscar(codigo)
    }

    fun borrar(codigo: String) {
        val a = repo.buscar(codigo)
        if (a.estado.activo) throw ReglaIncumplida("Cancela el analisis antes de borrarlo.")
        repo.borrar(codigo)
    }

    /** Un cierre del backend a mitad de analisis lo deja pausado y reanudable, no perdido. */
    @EventListener(ApplicationReadyEvent::class)
    fun recuperarInterrumpidos() {
        for (a in repo.enEstado(Estado.EN_COLA, Estado.CORRIENDO)) {
            repo.estado(a.codigo, Estado.PAUSADO, error = "El programa se cerró durante el análisis. Lo hecho está guardado: pulsa «Continuar».")
        }
    }

    // ── Ejecucion ─────────────────────────────────────────────────────────

    private fun encolar(codigo: String, cerrar: Boolean) {
        cancelados -= codigo
        repo.estado(codigo, Estado.EN_COLA, mensaje = "En cola…", limpiarError = true)
        cola.submit { ejecutar(codigo, cerrar) }
    }

    private fun ejecutar(codigo: String, cerrar: Boolean) {
        try {
            if (codigo in cancelados) throw Cancelado()
            val a = repo.buscar(codigo)
            val p = a.peticion
            repo.estado(codigo, Estado.CORRIENDO, limpiarError = true)
            var av = repo.avance(codigo)
            if (!cerrar) {
                if (!av.buscado) av = buscar(codigo, p, av)
                if (!av.identificados) av = identificar(codigo, p, av) ?: return
            }
            av = clasificar(codigo, p, av, cerrar)
            av = territorios(codigo, av, cerrar)
            cerrarInforme(codigo, p, av)
        } catch (e: Cancelado) {
            repo.estado(codigo, Estado.CANCELADO, mensaje = "Cancelado")
        } catch (e: ErrorDelWorker) {
            repo.estado(codigo, Estado.PAUSADO, error = e.message)
        } catch (e: ReglaIncumplida) {
            repo.estado(codigo, Estado.PAUSADO, error = e.message)
        } catch (e: Exception) {
            log.error("Fallo inesperado en el analisis {}", codigo, e)
            repo.estado(codigo, Estado.PAUSADO, error = "Error inesperado: ${e.message ?: e.javaClass.simpleName}. Lo hecho está guardado.")
        } finally {
            busquedas.remove(codigo)
            cancelados -= codigo
        }
    }

    private fun comprobarCancelado(codigo: String) {
        if (codigo in cancelados) throw Cancelado()
    }

    /** Duerme en tramos cortos para reaccionar rapido a una cancelacion. */
    private fun esperar(codigo: String, ms: Long) {
        var resta = ms
        while (resta > 0) {
            comprobarCancelado(codigo)
            Thread.sleep(minOf(resta, 500))
            resta -= 500
        }
    }

    // 1 · Buscar en la Biblioteca de Anuncios (Apify)

    @Suppress("UNCHECKED_CAST")
    private fun buscar(codigo: String, p: Peticion, av: Avance): Avance {
        repo.progreso(codigo, Fase.BUSCANDO, "Buscando anuncios en la Biblioteca de Meta…")
        val terminos = p.competidores.flatMap { c ->
            // Con paginas elegidas se busca por cada una; si no, por el nombre (o enlace) escrito.
            if (c.paginas.isNotEmpty()) c.paginas.map { mapOf("valor" to it.pageId, "modo" to "pagina") }
            else listOf(termino(c.nombre).let { (valor, modo) -> mapOf("valor" to valor, "modo" to modo) })
        } +
            p.keywords.map { mapOf("valor" to it, "modo" to "palabras") }
        val lanzada = worker.post(
            "/anuncios/lanzar",
            mapOf("terminos" to terminos, "pais" to p.pais, "maximo" to p.maximo, "solo_activos" to p.soloActivos),
        )
        val run = lanzada["run"] as String
        val t = (lanzada["t"] as Number).toInt()
        busquedas[codigo] = run to t

        val limite = System.currentTimeMillis() + BUSQUEDA_MAX_MS
        var items: List<Json>
        while (true) {
            esperar(codigo, SONDEO_MS)
            if (System.currentTimeMillis() > limite) {
                runCatching { worker.post("/anuncios/abortar", mapOf("run" to run, "t" to t)) }
                throw ErrorDelWorker("La búsqueda en la Biblioteca de Meta no ha terminado en 12 minutos y se ha cancelado para no gastar crédito. Suele ser saturación momentánea: continúa en unos minutos, o prueba con menos competidores.")
            }
            val r = worker.post("/anuncios/consultar", mapOf("run" to run, "t" to t))
            if (r["estado"] == "listo") {
                items = r["items"] as? List<Json> ?: emptyList()
                break
            }
            val n = (r["anuncios"] as? Number)?.toInt()
            repo.progreso(codigo, Fase.BUSCANDO, if (n != null) "Buscando anuncios… $n encontrados" else "Buscando anuncios…")
        }
        busquedas.remove(codigo)

        val norm = worker.post("/anuncios/normalizar", mapOf("items" to items, "nivel" to 3))
        (norm["error"] as? String)?.let { throw ErrorDelWorker("El buscador de anuncios ha fallado: $it") }
        val todos = norm["anuncios"] as? List<Json> ?: emptyList()
        if (todos.isEmpty()) {
            throw ReglaIncumplida("Meta no devolvió ningún anuncio para esta búsqueda. Revisa los nombres, el país y si hay anuncios activos.")
        }
        val brutos = recientes(todos, p.fechaMinima)
        if (brutos.isEmpty()) {
            throw ReglaIncumplida("Los ${todos.size} anuncios que devolvió Meta empezaron antes de la fecha mínima (${p.fechaMinima}) y ya no están activos. Usa una fecha más antigua.")
        }
        return av.copy(brutos = brutos, buscado = true).also { repo.guardarAvance(codigo, it) }
    }

    /** Sin los anuncios que empezaron antes de la fecha minima y ya terminaron. Sin fecha de inicio, se quedan. */
    internal fun recientes(anuncios: List<Json>, minima: String?): List<Json> =
        if (minima == null) anuncios
        else anuncios.filter { a -> a["activo"] == true || (a["fecha_inicio"] as? String).let { it.isNullOrBlank() || it.take(10) >= minima } }

    /** Un enlace de Facebook/Instagram o un id numerico apunta a una pagina concreta: no hay que adivinar. */
    internal fun termino(texto: String): Pair<String, String> {
        val t = texto.trim()
        Regex("view_all_page_id=(\\d+)").find(t)?.let { return it.groupValues[1] to "pagina" }
        Regex("^(?:https?://)?(?:[\\w-]+\\.)?(?:facebook|fb|instagram)\\.com/(?:pg/)?([^/?#]+)", RegexOption.IGNORE_CASE).find(t)?.let {
            val slug = it.groupValues[1]
            if (slug.all(Char::isDigit) && slug.length >= 8) return slug to "pagina"
            return slug.replace(Regex("[.\\-_]+"), " ") to "marca"
        }
        if (Regex("^\\d{8,}$").matches(t)) return t to "pagina"
        return t to "marca"
    }

    // 2 · Saber cual es la pagina de cada competidor

    @Suppress("UNCHECKED_CAST")
    private fun identificar(codigo: String, p: Peticion, av: Avance): Avance? {
        repo.progreso(codigo, Fase.BUSCANDO, "Identificando a los competidores…")
        val paginas = av.paginas.toMutableMap()
        for (c in p.competidores) {
            comprobarCancelado(codigo)
            if (c.nombre in paginas) continue
            if (c.paginas.isNotEmpty()) {
                paginas[c.nombre] = c.paginas.joinToString(",") { it.pageId }
                continue
            }
            val (valor, modo) = termino(c.nombre)
            if (modo == "pagina") {
                paginas[c.nombre] = valor
                continue
            }
            val r = worker.post("/competidores/resolver", mapOf("buscado" to c.nombre, "anuncios" to av.brutos))
            when (r["estado"]) {
                "unica" -> paginas[c.nombre] = r["page_id"] as String
                "ambigua" -> {
                    repo.guardarAvance(codigo, av.copy(paginas = paginas))
                    val candidatos = (r["candidatos"] as List<Json>).map {
                        Candidato(
                            it["page_id"].toString(), it["nombre"].toString(), (it["anuncios"] as? Number)?.toInt() ?: 0, it["muestra"] as? String,
                            it["avatar"] as? String, (it["ejemplos"] as? List<*>).orEmpty().filterIsInstance<String>(), it["texto"] as? String,
                        )
                    }
                    repo.pendiente(codigo, Pendiente("elegir_pagina", c.nombre, candidatos))
                    repo.estado(codigo, Estado.PAUSADO, mensaje = "Falta elegir la página de ${c.nombre}", limpiarError = true)
                    return null
                }
                else -> paginas[c.nombre] = ""
            }
        }

        val nivelPagina = HashMap<String, Int>()
        val identificadas = mutableListOf<Json>()
        val sin = mutableListOf<String>()
        for (c in p.competidores) {
            val ids = paginas[c.nombre].orEmpty().split(",").map { it.trim() }.filter { it.isNotEmpty() }
            var alguno = false
            for (pageId in ids) {
                val suyos = av.brutos.filter { it["page_id"] == pageId }
                if (suyos.isEmpty()) continue
                alguno = true
                nivelPagina.merge(pageId, c.nivel, ::minOf)
                identificadas += mapOf("buscado" to c.nombre, "page_id" to pageId, "anunciante" to suyos.first()["anunciante"], "anuncios" to suyos.size)
            }
            if (!alguno) sin += c.nombre
        }

        // Con palabras clave, el resto de lo que salio es "mercado" (nivel 3); sin ellas solo importan los competidores.
        val conNivel = av.brutos.mapNotNull { a ->
            val nivel = nivelPagina[a["page_id"]] ?: if (p.keywords.isNotEmpty()) 3 else return@mapNotNull null
            a + ("nivel" to nivel)
        }
        val unicos = unicosConNivel(conNivel).take(MAX_ANUNCIOS)
        if (unicos.isEmpty()) {
            throw ReglaIncumplida("No se encontró ningún anuncio de los competidores indicados. Prueba con el enlace de su página de Facebook o añade palabras clave del sector.")
        }
        repo.progreso(codigo, Fase.CLASIFICANDO, "${unicos.size} anuncios por analizar", hechos = av.clasificadas.size, total = unicos.size)
        return av.copy(paginas = paginas, anuncios = unicos, identificados = true, identificadas = identificadas, sinAnuncios = sin)
            .also { repo.guardarAvance(codigo, it) }
    }

    /** Un anuncio sale en varias busquedas: se queda con el de menor nivel, y cada anunciante hereda su mejor nivel. */
    internal fun unicosConNivel(anuncios: List<Json>): List<Json> {
        val mejor = LinkedHashMap<String, Json>()
        for (a in anuncios) {
            val id = a["ad_id"].toString()
            val previo = mejor[id]
            if (previo == null || nivelDe(a) < nivelDe(previo)) mejor[id] = a
        }
        val porAnunciante = HashMap<String, Int>()
        mejor.values.forEach { porAnunciante.merge(it["anunciante"].toString(), nivelDe(it), ::minOf) }
        return mejor.values.map { it + ("nivel" to porAnunciante.getValue(it["anunciante"].toString())) }
    }

    private fun nivelDe(a: Json) = (a["nivel"] as? Number)?.toInt() ?: 3

    // 3 · Clasificar con Gemini

    @Suppress("UNCHECKED_CAST")
    private fun clasificar(codigo: String, p: Peticion, inicial: Avance, cerrar: Boolean): Avance {
        var av = inicial
        if (cerrar) return av
        val pendientes = av.anuncios.filter { it["ad_id"].toString() !in av.clasificadas }
        val total = av.anuncios.size
        repo.progreso(codigo, Fase.CLASIFICANDO, "Analizando anuncios…", hechos = av.clasificadas.size, total = total)
        for (lote in pendientes.chunked(LOTE)) {
            comprobarCancelado(codigo)
            repo.progreso(codigo, Fase.CLASIFICANDO, "Analizando anuncios ${av.clasificadas.size + 1}-${av.clasificadas.size + lote.size} de $total…")
            val nuevas = clasificarLote(codigo, p, lote)
            av = av.copy(clasificadas = av.clasificadas + nuevas).also { repo.guardarAvance(codigo, it) }
            repo.progreso(codigo, Fase.CLASIFICANDO, "Analizando anuncios…", hechos = av.clasificadas.size, total = total)
        }
        return av
    }

    /**
     * Quien define el sector para el filtro de relevancia: los negocios de referencia
     * y tambien los competidores (y sus paginas). Las palabras clave no: solo buscan.
     */
    internal fun referenciaSector(p: Peticion): List<String> =
        (p.referencia + p.competidores.flatMap { c -> listOf(c.nombre) + c.paginas.map { it.nombre } })
            .map { it.trim() }.filter { it.isNotEmpty() && !it.startsWith("http") && !it.all(Char::isDigit) }
            .distinctBy { it.lowercase() }

    /** Si el lote pesa demasiado para Gemini se parte por la mitad hasta que cabe. */
    @Suppress("UNCHECKED_CAST")
    private fun clasificarLote(codigo: String, p: Peticion, lote: List<Json>): Map<String, Json> {
        val r = try {
            worker.post(
                "/ia/clasificar",
                mapOf("anuncios" to lote, "referencia" to referenciaSector(p), "terminos" to p.keywords, "con_medios" to p.conMedios),
            )
        } catch (e: ErrorDelWorker) {
            if (e.loteGrande && lote.size > 1) {
                val mitad = lote.size / 2
                return clasificarLote(codigo, p, lote.take(mitad)) + clasificarLote(codigo, p, lote.drop(mitad))
            }
            throw e
        }
        (r["uso"] as? Map<*, *>)?.let { consumo.registrar(codigo, "clasificar", it) }
        val hechas = (r["clasificaciones"] as? List<Json> ?: emptyList()).associateBy { it["ad_id"].toString() }
        // Si el modelo se salta un anuncio no se reintenta (podria no devolverlo nunca): queda fuera del informe.
        return lote.associate { a ->
            val id = a["ad_id"].toString()
            id to (hechas[id] ?: mapOf("ad_id" to id, "omitida" to true, "relevante" to false))
        }
    }

    // 4 · Territorios

    @Suppress("UNCHECKED_CAST")
    private fun territorios(codigo: String, av: Avance, cerrar: Boolean): Avance {
        if (av.territorios != null) return av
        comprobarCancelado(codigo)
        repo.progreso(codigo, Fase.TERRITORIOS, "Detectando los territorios de este sector…")
        val etiquetas = av.clasificadas.values.filter { it["relevante"] == true }.flatMap {
            (it["angulos_libres"] as? List<String> ?: emptyList()) + (it["beneficios_libres"] as? List<String> ?: emptyList())
        }
        val lista: List<Json> = if (etiquetas.isEmpty()) {
            emptyList()
        } else {
            try {
                val r = worker.post("/ia/territorios", mapOf("etiquetas" to etiquetas))
                (r["uso"] as? Map<*, *>)?.let { consumo.registrar(codigo, "territorios", it) }
                r["territorios"] as? List<Json> ?: emptyList()
            } catch (e: ErrorDelWorker) {
                if (!cerrar) throw e
                // "Terminar ya": agrupar por palabras compartidas, sin IA.
                worker.post("/ia/territorios-sin-ia", mapOf("etiquetas" to etiquetas))["territorios"] as? List<Json> ?: emptyList()
            }
        }
        return av.copy(territorios = lista).also { repo.guardarAvance(codigo, it) }
    }

    // 5 · Informe

    @Suppress("UNCHECKED_CAST")
    private fun cerrarInforme(codigo: String, p: Peticion, av: Avance) {
        comprobarCancelado(codigo)
        repo.progreso(codigo, Fase.INFORME, "Calculando el informe…")
        val conEnlace = av.anuncios.mapNotNull { a ->
            val c = av.clasificadas[a["ad_id"].toString()] ?: return@mapNotNull null
            if (c["relevante"] != true) return@mapNotNull null
            a + c + ("thumb_url" to (a["imagen_url"] ?: a["video_portada_url"] ?: a["avatar_url"]))
        }
        if (conEnlace.isEmpty()) {
            throw ReglaIncumplida("Ningún anuncio resultó ser del sector indicado. Revisa los negocios de referencia o los competidores.")
        }
        // La miniatura guardada sustituye al enlace de Meta, que caduca; la que no se pudo bajar conserva el enlace.
        val guardadas = guardarMiniaturas(codigo, conEnlace)
        val relevantes = conEnlace.map { a ->
            val id = a["ad_id"].toString()
            if (id in guardadas) a + ("thumb_url" to "$RUTA_MINIATURAS/$id") else a
        }
        val datos = worker.post(
            "/informe/construir",
            mapOf(
                "anuncios" to relevantes, "territorios" to (av.territorios ?: emptyList<Json>()), "mis_marcas" to p.misMarcas,
                "mis_paginas" to misPaginas(p, av),
                "sin_anuncios" to av.sinAnuncios, "identificadas" to av.identificadas,
            ),
        )
        val meta = (datos["meta"] as? Json).orEmpty() + mapOf(
            "cod_analisis" to codigo, "costo_ia_usd" to consumo.costo(codigo), "llamadas_ia" to consumo.llamadas(codigo),
            "descartados" to (av.anuncios.size - relevantes.size),
        )
        val completo = datos + ("meta" to meta)
        val marca = p.misMarcas.joinToString(" y ").ifBlank { p.competidores.take(3).joinToString(", ") { it.nombre } }
        val codInforme = informes.guardar(codigo, marca, completo, ServicioInformes.portada(completo), esEjemplo = false)
        repo.terminar(codigo, codInforme)
    }

    /**
     * Baja y guarda las miniaturas (gratis, sin IA). Devuelve los anuncios que ya tienen la suya.
     * Un fallo no para el informe: esos anuncios se quedan con el enlace de Meta.
     */
    private fun guardarMiniaturas(codigo: String, anuncios: List<Json>): Set<String> {
        val items = anuncios.mapNotNull { a ->
            val url = a["thumb_url"] as? String ?: return@mapNotNull null
            mapOf("id" to a["ad_id"].toString(), "url" to url)
        }.distinctBy { it["id"] }
        val ids = items.map { it["id"]!! }
        val ya = informes.conMiniatura(ids)
        val faltan = items.filter { it["id"] !in ya }
        for ((i, lote) in faltan.chunked(LOTE_MINIATURAS).withIndex()) {
            comprobarCancelado(codigo)
            repo.progreso(codigo, Fase.INFORME, "Guardando las imágenes de los anuncios (${i * LOTE_MINIATURAS} de ${faltan.size})…")
            try {
                val r = worker.post("/informe/miniaturas", mapOf("items" to lote))
                (r["miniaturas"] as? List<*>).orEmpty().mapNotNull { it as? Json }.forEach { m ->
                    val datos = (m["datos_b64"] as? String)?.let { Base64.getDecoder().decode(it) } ?: return@forEach
                    informes.guardarMiniatura(m["id"].toString(), datos, m["mime"] as? String ?: "image/jpeg")
                }
            } catch (e: ErrorDelWorker) {
                log.warn("Miniaturas de {}: {}", codigo, e.message)
            }
        }
        repo.progreso(codigo, Fase.INFORME, "Calculando el informe…")
        return informes.conMiniatura(ids)
    }

    /**
     * Las paginas de tus marcas tal como quedaron identificadas (elegidas al configurarlas,
     * o al resolver una ambigua): el informe reconoce tus anuncios por ellas, no por el nombre.
     */
    private fun misPaginas(p: Peticion, av: Avance): List<String> =
        p.competidores.filter { c -> p.misMarcas.any { it.equals(c.nombre, ignoreCase = true) } }
            .flatMap { c -> av.paginas[c.nombre].orEmpty().split(",") }.map { it.trim() }.filter { it.isNotEmpty() }.distinct()

    // ── Sugerencias de paginas (autocompletado de la Biblioteca de Meta) ──

    fun sugerirPaginas(texto: String, pais: String): Json {
        val t = texto.trim()
        if (t.length < 3) return mapOf("paginas" to emptyList<Json>())
        if (t.length > 60) throw ReglaIncumplida("Escribe como mucho 60 caracteres.")
        return worker.post("/anuncios/paginas", mapOf("texto" to t, "pais" to pais.uppercase().take(2)))
    }

    /** Abre el Chrome de las sugerencias por adelantado; si el worker no responde, no pasa nada. */
    fun prepararSugerencias(pais: String) {
        runCatching { worker.post("/anuncios/paginas/preparar", mapOf("texto" to "-", "pais" to pais.uppercase().take(2))) }
    }

    // ── Validacion ────────────────────────────────────────────────────────

    internal fun validar(p: Peticion): Peticion {
        val competidores = p.competidores.map { c ->
            val (nombre, paginas) = nombreYPaginas(c.nombre, c.paginas, "competidor")
            Competidor(nombre, c.nivel, paginas)
        }.filter { it.nombre.isNotEmpty() }.distinctBy { it.nombre.lowercase() }
        // Tu marca es opcional; si la indicas, sus anuncios tambien se buscan y entran al informe.
        // Va con nivel 3 (peso 1) para no inflar los porcentajes con tus propios anuncios.
        val marcas = (p.marcas + p.misMarcas.map { Marca(it) }).map { m ->
            val (nombre, paginas) = nombreYPaginas(m.nombre, m.paginas, "marca")
            Marca(nombre, paginas)
        }.filter { it.nombre.isNotEmpty() }.distinctBy { it.nombre.lowercase() }
        val comp = competidores + marcas.filter { m -> competidores.none { it.nombre.equals(m.nombre, ignoreCase = true) } }
            .map { Competidor(it.nombre, 3, it.paginas) }
        val kw = p.keywords.map { it.trim() }.filter { it.isNotEmpty() }.distinct()
        if (comp.isEmpty() && kw.isEmpty()) throw ReglaIncumplida("Indica al menos un competidor o una palabra clave del sector.")
        if (comp.size > 20) throw ReglaIncumplida("Máximo 20 competidores por análisis (tus marcas cuentan).")
        if (comp.any { it.nivel !in 1..4 }) throw ReglaIncumplida("El nivel de un competidor va de 1 (directo) a 4 (nacional).")
        if (p.maximo !in 10..MAX_ANUNCIOS) throw ReglaIncumplida("El máximo de anuncios va de 10 a $MAX_ANUNCIOS.")
        if (!Regex("[A-Za-z]{2}").matches(p.pais)) throw ReglaIncumplida("El país va como código de dos letras (PE, ES, MX...).")
        val fechaMinima = p.fechaMinima?.trim()?.ifEmpty { null }?.also { f ->
            val d = runCatching { java.time.LocalDate.parse(f) }.getOrNull() ?: throw ReglaIncumplida("La fecha mínima va como AAAA-MM-DD.")
            if (d.isAfter(java.time.LocalDate.now())) throw ReglaIncumplida("La fecha mínima no puede ser futura.")
        }
        return p.copy(
            fechaMinima = fechaMinima,
            misMarcas = marcas.map { it.nombre }, marcas = marcas,
            competidores = comp, keywords = kw, referencia = p.referencia.map { it.trim() }.filter { it.isNotEmpty() }.distinct(),
            pais = p.pais.uppercase(),
        )
    }

    /**
     * Solo paginas con id valido, sin repetir. Con paginas elegidas, el nombre es el de la
     * primera: lo escrito en la caja es solo lo que se busco (una «c» acabo titulando un informe).
     */
    private fun nombreYPaginas(nombre: String, paginas: List<PaginaMeta>, que: String): Pair<String, List<PaginaMeta>> {
        val validas = paginas.filter { Regex("\\d{5,25}").matches(it.pageId) }.distinctBy { it.pageId }
        if (validas.size > 10) throw ReglaIncumplida("Máximo 10 páginas por $que.")
        return (validas.firstOrNull()?.nombre?.trim()?.ifEmpty { null } ?: nombre.trim()) to validas
    }

    private companion object {
        const val LOTE = 10
        const val LOTE_MINIATURAS = 40
        const val RUTA_MINIATURAS = "/api/informes/miniaturas"
        const val MAX_ANUNCIOS = 500
        const val SONDEO_MS = 4_000L
        const val BUSQUEDA_MAX_MS = 12 * 60_000L

        // Estimacion de costo por anuncio (referencia: gemini-2.5-flash, US$ por millon de tokens).
        const val TOKENS_ENTRADA = 3_000
        const val TOKENS_SALIDA = 400
        const val PRECIO_ENTRADA = 0.30
        const val PRECIO_SALIDA = 2.50
        const val APIFY_POR_INFORME = 0.07
    }
}
