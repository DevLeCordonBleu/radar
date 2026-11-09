package pe.edu.lcb.radar.infraestructura

import org.springframework.jdbc.core.JdbcTemplate
import org.springframework.jdbc.core.RowMapper
import org.springframework.stereotype.Repository
import org.springframework.transaction.PlatformTransactionManager
import org.springframework.transaction.support.TransactionTemplate
import pe.edu.lcb.radar.dominio.Json
import pe.edu.lcb.radar.dominio.NoEncontrado
import tools.jackson.databind.ObjectMapper
import java.time.Instant

data class SitioSeo(
    val codigo: String,
    val nombre: String,
    val rol: String,
    val hosts: List<String>,
    val maxPaginas: Int,
    val activo: Boolean,
    /** Sitemaps leidos y avisos del ultimo inventario. */
    val descubrimiento: Json?,
    val descubierto: Instant?,
    /** Paginas por estado (OK, EXCLUIDA, PENDIENTE...). */
    val paginas: Map<String, Int>,
    val conTemas: Int,
    val sinTemas: Int,
    /** De las que faltan, las que hablan del sector y van a la IA (las demas se marcan gratis). */
    val sinTemasDelSector: Int = sinTemas,
) {
    val esPropio: Boolean get() = rol == "PROPIO"
}

data class TareaSeo(
    val codigo: String,
    val tipo: String,
    val sitio: String?,
    val estado: String,
    val hechos: Int,
    val total: Int,
    val mensaje: String?,
    val error: String?,
    val resumen: Json?,
    val costoUsd: Double,
    val llamadasIa: Int,
    val creado: Instant,
    val modificado: Instant,
) {
    val activa: Boolean get() = estado == "EN_COLA" || estado == "CORRIENDO"
}

data class PaginaSeo(
    val url: String,
    val sitio: String,
    val sitemap: String?,
    val lastmod: String?,
    val estado: String,
    val motivo: String?,
    val http: Int?,
    val datos: Json?,
    val temas: Json?,
    val extraida: Instant?,
)

data class KeywordSeo(
    val keyword: String,
    val origenes: List<Json>,
    val intencion: String?,
    val grupo: String?,
    val canonica: String?,
    val relevancia: Int?,
    val motivo: String?,
    val cobertura: String?,
    val urlPropia: String?,
    val motivoCobertura: String?,
    val evidencia: String,
)

data class ArticuloSeo(
    val codigo: String,
    val grupo: String,
    val keyword: String,
    val variantes: List<String>,
    val origenes: List<Json>,
    val indicaciones: String?,
    val titulo: String?,
    val slug: String?,
    val metaDescription: String?,
    /** Markdown. */
    val contenido: String?,
    val pendientes: List<String>,
    /** La ultima redaccion y como va. */
    val tarea: String?,
    val tareaEstado: String?,
    val tareaError: String?,
    val wpId: Long?,
    val wpEstado: String?,
    val wpEnlace: String?,
    val wpEditar: String?,
    val enviado: Instant?,
    val redactado: Instant?,
    val autor: String?,
    val creado: Instant,
    val modificado: Instant,
    /** Imagen destacada (sin los bytes: van por /imagen). */
    val imagen: ImagenSeo? = null,
) {
    /** Se edito despues de mandarlo a WordPress (cambiar la imagen tambien cuenta). */
    val cambiosSinEnviar: Boolean get() = wpId != null && enviado != null && modificado.isAfter(enviado)
}

/** Una consulta x pagina de Search Console. `orden`: la consulta normalizada con las palabras ordenadas. */
data class FilaGsc(
    val consulta: String, val orden: String, val url: String, val clics: Int, val impresiones: Int, val ctr: Double, val posicion: Double,
)

/** Propuesta de la IA para una pagina propia que ya aparece en Google. `estado`: PROPUESTA | APLICADA | DESCARTADA. */
data class MejoraSeo(
    val url: String, val consultas: List<Json>, val tituloActual: String?, val metaActual: String?, val titulo: String,
    val metaDescription: String, val ideas: List<IdeaMejora>, val motivo: String?, val estado: String, val creado: Instant, val modificado: Instant,
)

/** Un cambio en el contenido: donde va, el texto de hoy (null si es nuevo) y el que debe ir. */
data class IdeaMejora(val donde: String, val diceAhora: String?, val debeDecir: String)

data class ImagenSeo(
    val fuente: String,
    val mime: String,
    val bytes: Int,
    val alt: String?,
    val leyenda: String?,
    val autor: String?,
    val autorUrl: String?,
    val origenUrl: String?,
    val prompt: String?,
    val modelo: String?,
    val wpMediaId: Long?,
    val modificada: Instant,
)

/** Persistencia del Plan SEO: una fila por URL, tareas y keywords de la ultima generacion. */
@Repository
class RepositorioSeo(private val jdbc: JdbcTemplate, private val json: ObjectMapper, transacciones: PlatformTransactionManager) {

    private val tx = TransactionTemplate(transacciones)

    @Suppress("UNCHECKED_CAST")
    private fun mapa(texto: String?): Json? = texto?.let { json.readValue(it, Map::class.java) as Json }

    @Suppress("UNCHECKED_CAST")
    private fun lista(texto: String?): List<Any?> = texto?.let { json.readValue(it, List::class.java) as List<Any?> } ?: emptyList()

    private fun texto(v: Any?): String? = v?.let { json.writeValueAsString(it) }

    private fun ahora() = Instant.now().toString()

    // ── Sitios ──

    /** Siembra los sitios del plan solo con la tabla vacia: un competidor quitado no vuelve al reiniciar. */
    fun sembrar(sitios: List<Triple<String, String, Pair<String, List<String>>>>) {
        if ((jdbc.queryForObject("SELECT COUNT(*) FROM seo_sitio", Int::class.java) ?: 0) > 0) return
        for ((codigo, nombre, rolHosts) in sitios) crearSitio(codigo, nombre, rolHosts.first, rolHosts.second)
    }

    fun crearSitio(codigo: String, nombre: String, rol: String, hosts: List<String>) {
        jdbc.update(
            "INSERT INTO seo_sitio (cod_seo_sitio, nombre, rol, hosts_json, fec_creacion, fec_modif) VALUES (?, ?, ?, ?, ?, ?)",
            codigo, nombre, rol, texto(hosts), ahora(), ahora(),
        )
    }

    /** Quita el sitio con sus paginas; sus tareas quedan en el historial (las pausadas, canceladas). */
    fun borrarSitio(codigo: String) = tx.executeWithoutResult {
        val sitio = id(codigo)
        jdbc.update("DELETE FROM seo_pagina WHERE id_seo_sitio = ?", sitio)
        jdbc.update("DELETE FROM seo_sitio WHERE id_seo_sitio = ?", sitio)
        jdbc.update(
            "UPDATE seo_tarea SET estado = 'CANCELADA', mensaje = 'Cancelada: se quitó el sitio', fec_modif = ? WHERE cod_seo_sitio = ? AND estado = 'PAUSADA'",
            ahora(), codigo,
        )
    }

    private fun id(codigo: String): Long =
        jdbc.query("SELECT id_seo_sitio FROM seo_sitio WHERE cod_seo_sitio = ?", { rs, _ -> rs.getLong(1) }, codigo).firstOrNull()
            ?: throw NoEncontrado("No existe el sitio $codigo.")

    fun sitios(): List<SitioSeo> {
        val conteos = mutableMapOf<String, MutableMap<String, Int>>()
        jdbc.query(
            "SELECT s.cod_seo_sitio, p.estado, COUNT(*) FROM seo_pagina p JOIN seo_sitio s ON s.id_seo_sitio = p.id_seo_sitio GROUP BY 1, 2",
        ) { rs -> conteos.getOrPut(rs.getString(1)) { mutableMapOf() }[rs.getString(2)] = rs.getInt(3) }
        val temas = mutableMapOf<String, Pair<Int, Int>>()
        jdbc.query(
            """SELECT s.cod_seo_sitio,
                      SUM(CASE WHEN p.hash_temas = p.hash THEN 1 ELSE 0 END),
                      SUM(CASE WHEN p.hash_temas IS NULL OR p.hash_temas <> p.hash THEN 1 ELSE 0 END)
               FROM seo_pagina p JOIN seo_sitio s ON s.id_seo_sitio = p.id_seo_sitio WHERE p.estado = 'OK' GROUP BY 1""",
        ) { rs -> temas[rs.getString(1)] = rs.getInt(2) to rs.getInt(3) }
        @Suppress("UNCHECKED_CAST")
        return jdbc.query(
            "SELECT cod_seo_sitio, nombre, rol, hosts_json, max_paginas, activo, descubrimiento_json, fec_descubierto FROM seo_sitio ORDER BY id_seo_sitio",
        ) { rs, _ ->
            val c = rs.getString(1)
            SitioSeo(
                c, rs.getString(2), rs.getString(3), lista(rs.getString(4)).map { it.toString() }, rs.getInt(5), rs.getInt(6) == 1,
                mapa(rs.getString(7)), rs.getString(8)?.let(Instant::parse), conteos[c].orEmpty(),
                temas[c]?.first ?: 0, temas[c]?.second ?: 0,
            )
        }
    }

    fun sitio(codigo: String): SitioSeo = sitios().firstOrNull { it.codigo == codigo } ?: throw NoEncontrado("No existe el sitio $codigo.")

    fun ajustarSitio(codigo: String, nombre: String, hosts: List<String>, maxPaginas: Int, activo: Boolean) {
        jdbc.update(
            "UPDATE seo_sitio SET nombre = ?, hosts_json = ?, max_paginas = ?, activo = ?, fec_modif = ? WHERE cod_seo_sitio = ?",
            nombre, texto(hosts), maxPaginas, if (activo) 1 else 0, ahora(), codigo,
        )
    }

    data class Registro(val nuevas: Int, val reactivadas: Int, val excluidas: Int, val retiradas: Int, val total: Int)

    /**
     * Guarda lo que declara el sitio. Nueva -> PENDIENTE (o EXCLUIDA con su motivo).
     * Ya conocida: vuelve a PENDIENTE si cambio su lastmod o si fallo la vez anterior.
     * Las que el sitio ya no declara quedan RETIRADA (sus datos se conservan).
     */
    @Suppress("UNCHECKED_CAST")
    fun registrarDescubrimiento(codigo: String, urls: List<Json>, descubrimiento: Json): Registro = tx.execute {
        val sitio = id(codigo)
        val ahora = ahora()
        val previas = mutableMapOf<String, Triple<String, String?, String?>>() // url -> (estado, lastmod_leido, motivo)
        jdbc.query("SELECT url, estado, lastmod_leido, motivo FROM seo_pagina WHERE id_seo_sitio = ?", { rs ->
            previas[rs.getString(1)] = Triple(rs.getString(2), rs.getString(3), rs.getString(4))
        }, sitio)
        var nuevas = 0
        var reactivadas = 0
        var excluidas = 0
        val vistas = HashSet<String>()
        for (u in urls) {
            val url = u["url"] as? String ?: continue
            vistas += url
            val excluida = u["excluida"] as? String
            val lastmod = u["lastmod"] as? String
            val previa = previas[url]
            if (excluida != null) excluidas++
            if (previa == null) {
                jdbc.update(
                    """INSERT INTO seo_pagina (id_seo_sitio, url, sitemap, lastmod, estado, motivo, fec_descubierta, fec_modif)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    sitio, url, u["sitemap"], lastmod, if (excluida != null) "EXCLUIDA" else "PENDIENTE", excluida, ahora, ahora,
                )
                nuevas++
                continue
            }
            val (estado, leido) = previa
            val nuevoEstado = when {
                excluida != null -> "EXCLUIDA"
                estado in REINTENTAR || estado == "RETIRADA" || estado == "EXCLUIDA" -> "PENDIENTE"
                estado == "OK" && lastmod != null && lastmod != leido -> "PENDIENTE"
                else -> estado
            }
            if (nuevoEstado == "PENDIENTE" && estado != "PENDIENTE") reactivadas++
            jdbc.update(
                "UPDATE seo_pagina SET sitemap = ?, lastmod = ?, estado = ?, motivo = ?, fec_modif = ? WHERE url = ?",
                u["sitemap"], lastmod, nuevoEstado, if (nuevoEstado == "EXCLUIDA") excluida else previa.third.takeIf { nuevoEstado == estado }, ahora, url,
            )
        }
        val retiradas = previas.keys.filter { it !in vistas && previas[it]!!.first != "RETIRADA" }
        retiradas.forEach {
            jdbc.update("UPDATE seo_pagina SET estado = 'RETIRADA', motivo = 'El sitio ya no la declara en su sitemap', fec_modif = ? WHERE url = ?", ahora, it)
        }
        jdbc.update("UPDATE seo_sitio SET descubrimiento_json = ?, fec_descubierto = ?, fec_modif = ? WHERE id_seo_sitio = ?", texto(descubrimiento), ahora, ahora, sitio)
        Registro(nuevas, reactivadas, excluidas, retiradas.size, urls.size)
    }!!

    /**
     * Fecha minima de publicacion: las paginas anteriores pasan a ANTIGUA (no se leen ni van a
     * temas ni keywords; sus datos se conservan) y las ANTIGUA que ya no lo son vuelven. La fecha
     * de una pagina es la de publicacion que declara o, si aun no se leyo, el lastmod de su
     * sitemap (si no cambia desde antes, tampoco se publico despues). Sin fecha, no se toca.
     * Devuelve (marcadas, devueltas).
     */
    fun aplicarFechaMinima(fecha: String?, codigo: String? = null): Pair<Int, Int> = tx.execute {
        val sitio = codigo?.let { " AND id_seo_sitio = ${id(it)}" }.orEmpty()
        val ahora = ahora()
        val marcadas = if (fecha == null) 0 else jdbc.update(
            """UPDATE seo_pagina SET estado = 'ANTIGUA', fec_modif = ?,
                      motivo = 'Anterior a la fecha mínima (' || substr($FECHA_PAGINA, 1, 10) || ')'
               WHERE estado IN ('PENDIENTE', 'OK') AND substr($FECHA_PAGINA, 1, 10) < ?$sitio""",
            ahora, fecha,
        )
        val devueltas = jdbc.update(
            """UPDATE seo_pagina SET estado = CASE WHEN datos_json IS NULL THEN 'PENDIENTE' ELSE 'OK' END, motivo = NULL, fec_modif = ?
               WHERE estado = 'ANTIGUA' AND (? IS NULL OR $FECHA_PAGINA IS NULL OR substr($FECHA_PAGINA, 1, 10) >= ?)$sitio""",
            ahora, fecha, fecha,
        )
        marcadas to devueltas
    }!!

    fun pendientes(codigo: String, limite: Int): List<String> =
        jdbc.query("SELECT url FROM seo_pagina WHERE id_seo_sitio = ? AND estado = 'PENDIENTE' ORDER BY id_seo_pagina LIMIT ?", { rs, _ -> rs.getString(1) }, id(codigo), limite)

    fun contarAntiguas(): Int = jdbc.queryForObject("SELECT COUNT(*) FROM seo_pagina WHERE estado = 'ANTIGUA'", Int::class.java) ?: 0

    fun contarPendientes(codigo: String): Int =
        jdbc.queryForObject("SELECT COUNT(*) FROM seo_pagina WHERE id_seo_sitio = ? AND estado = 'PENDIENTE'", Int::class.java, id(codigo)) ?: 0

    @Suppress("UNCHECKED_CAST")
    fun guardarExtraccion(fila: Json) {
        val url = fila["url"] as? String ?: return
        val datos = fila["datos"] as? Map<String, Any?>
        val ahora = ahora()
        jdbc.update(
            """UPDATE seo_pagina SET estado = ?, motivo = ?, http = ?, url_final = ?, datos_json = COALESCE(?, datos_json),
                      hash = COALESCE(?, hash), lastmod_leido = lastmod, fec_extraida = ?, fec_modif = ? WHERE url = ?""",
            fila["estado"] ?: "ERROR", fila["motivo"], (fila["http"] as? Number)?.toInt(), fila["url_final"],
            datos?.let { texto(it - "hash") }, datos?.get("hash"), ahora, ahora, url,
        )
    }

    // ── Temas ──

    /** Paginas OK cuyo contenido cambio desde la ultima vez que se pidieron sus temas (o nunca se pidieron). */
    fun paginasSinTemas(codigo: String): List<Pair<String, Json>> = jdbc.query(
        "SELECT url, datos_json FROM seo_pagina WHERE id_seo_sitio = ? AND estado = 'OK' AND (hash_temas IS NULL OR hash_temas <> hash) ORDER BY id_seo_pagina",
        { rs, _ -> rs.getString(1) to mapa(rs.getString(2)).orEmpty() }, id(codigo),
    )

    fun guardarTemas(url: String, temas: Json) {
        val ahora = ahora()
        jdbc.update("UPDATE seo_pagina SET temas_json = ?, hash_temas = hash, fec_temas = ?, fec_modif = ? WHERE url = ?", texto(temas), ahora, ahora, url)
    }

    private val FUERA_DEL_SECTOR = "temas_json LIKE '%\"fuera_del_sector\":true%'"

    /** Paginas con temas: todas y las marcadas «fuera del sector» por el filtro gratuito. */
    fun contarTemas(): Pair<Int, Int> = jdbc.query(
        "SELECT COUNT(*), COALESCE(SUM(CASE WHEN $FUERA_DEL_SECTOR THEN 1 ELSE 0 END), 0) FROM seo_pagina WHERE estado = 'OK' AND hash_temas IS NOT NULL",
    ) { rs, _ -> rs.getInt(1) to rs.getInt(2) }.first()

    /**
     * Hace que «Extraer temas» vuelva a pedirlas (cambio de rubro). `soloFuera`: solo las que
     * el filtro gratuito dejo fuera (cambiaron las palabras, no la descripcion). Devuelve cuantas.
     */
    fun olvidarTemas(soloFuera: Boolean): Int = jdbc.update(
        "UPDATE seo_pagina SET hash_temas = NULL, fec_modif = ? WHERE estado = 'OK' AND hash_temas IS NOT NULL" + if (soloFuera) " AND $FUERA_DEL_SECTOR" else "",
        ahora(),
    )

    fun datosPagina(url: String): Json? =
        jdbc.query("SELECT datos_json FROM seo_pagina WHERE url = ? AND estado = 'OK'", { rs, _ -> mapa(rs.getString(1)) }, url).firstOrNull()

    // ── Paginas ──

    fun paginas(codigo: String?): List<PaginaSeo> = jdbc.query(
        """SELECT p.url, s.cod_seo_sitio, p.sitemap, p.lastmod, p.estado, p.motivo, p.http, p.datos_json, p.temas_json, p.fec_extraida
           FROM seo_pagina p JOIN seo_sitio s ON s.id_seo_sitio = p.id_seo_sitio
           WHERE (? IS NULL OR s.cod_seo_sitio = ?) ORDER BY s.id_seo_sitio, p.id_seo_pagina""",
        { rs, _ ->
            PaginaSeo(
                rs.getString(1), rs.getString(2), rs.getString(3), rs.getString(4), rs.getString(5), rs.getString(6),
                rs.getObject(7)?.let { (it as Number).toInt() }, mapa(rs.getString(8)), mapa(rs.getString(9)), rs.getString(10)?.let(Instant::parse),
            )
        },
        codigo, codigo,
    )

    /** Paginas OK de un rol (PROPIO / COMPETIDOR) que no estan retiradas. */
    fun paginasOk(rol: String): List<PaginaSeo> = paginas(null).filter { it.estado == "OK" }.let { todas ->
        val deRol = sitios().filter { it.rol == rol }.map { it.codigo }.toSet()
        todas.filter { it.sitio in deRol }
    }

    // ── Tareas ──

    private val tarea = { rs: java.sql.ResultSet, _: Int ->
        val codigo = rs.getString("cod_seo_tarea")
        TareaSeo(
            codigo, rs.getString("tipo"), rs.getString("cod_seo_sitio"), rs.getString("estado"), rs.getInt("hechos"), rs.getInt("total"),
            rs.getString("mensaje"), rs.getString("error"), mapa(rs.getString("resumen_json")),
            rs.getDouble("costo"), rs.getInt("llamadas"), Instant.parse(rs.getString("fec_creacion")), Instant.parse(rs.getString("fec_modif")),
        )
    }

    private val columnasTarea = """t.cod_seo_tarea, t.tipo, t.cod_seo_sitio, t.estado, t.hechos, t.total, t.mensaje, t.error, t.resumen_json,
        t.fec_creacion, t.fec_modif,
        (SELECT COALESCE(SUM(costo_usd), 0) FROM consumo_ia c WHERE c.cod_analisis = t.cod_seo_tarea) AS costo,
        (SELECT COUNT(*) FROM consumo_ia c WHERE c.cod_analisis = t.cod_seo_tarea) AS llamadas"""

    fun crearTarea(tipo: String, sitio: String?, autor: String?): String = tx.execute {
        val n = (jdbc.queryForObject("SELECT COALESCE(MAX(id_seo_tarea), 0) + 1 FROM seo_tarea", Int::class.java) ?: 1)
        val codigo = "S%04d".format(n)
        jdbc.update(
            "INSERT INTO seo_tarea (cod_seo_tarea, tipo, cod_seo_sitio, estado, mensaje, cod_autor, fec_creacion, fec_modif) VALUES (?, ?, ?, 'EN_COLA', 'En cola…', ?, ?, ?)",
            codigo, tipo, sitio, autor, ahora(), ahora(),
        )
        codigo
    }!!

    fun tarea(codigo: String): TareaSeo =
        jdbc.query("SELECT $columnasTarea FROM seo_tarea t WHERE t.cod_seo_tarea = ?", tarea, codigo).firstOrNull()
            ?: throw NoEncontrado("No existe la tarea $codigo.")

    fun tareas(limite: Int): List<TareaSeo> = jdbc.query("SELECT $columnasTarea FROM seo_tarea t ORDER BY t.id_seo_tarea DESC LIMIT ?", tarea, limite)

    fun ultimaTarea(tipo: String): TareaSeo? =
        jdbc.query("SELECT $columnasTarea FROM seo_tarea t WHERE t.tipo = ? ORDER BY t.id_seo_tarea DESC LIMIT 1", tarea, tipo).firstOrNull()

    fun tareasActivas(): List<TareaSeo> = jdbc.query("SELECT $columnasTarea FROM seo_tarea t WHERE t.estado IN ('EN_COLA', 'CORRIENDO')", tarea)

    fun estadoTarea(codigo: String, estado: String, mensaje: String? = null, error: String? = null, limpiarError: Boolean = false) {
        jdbc.update(
            "UPDATE seo_tarea SET estado = ?, mensaje = COALESCE(?, mensaje), error = CASE WHEN ? THEN NULL ELSE COALESCE(?, error) END, fec_modif = ? WHERE cod_seo_tarea = ?",
            estado, mensaje, limpiarError, error, ahora(), codigo,
        )
    }

    fun avance(codigo: String, hechos: Int, total: Int, mensaje: String) {
        jdbc.update("UPDATE seo_tarea SET hechos = ?, total = ?, mensaje = ?, fec_modif = ? WHERE cod_seo_tarea = ?", hechos, total, mensaje, ahora(), codigo)
    }

    fun resumen(codigo: String, resumen: Json) {
        jdbc.update("UPDATE seo_tarea SET resumen_json = ?, fec_modif = ? WHERE cod_seo_tarea = ?", texto(resumen), ahora(), codigo)
    }

    // ── Keywords ──

    fun reemplazarKeywords(filas: List<Json>, tarea: String) = tx.executeWithoutResult {
        jdbc.update("DELETE FROM seo_keyword")
        val ahora = ahora()
        for (f in filas) {
            jdbc.update(
                """INSERT INTO seo_keyword (clave, keyword, origenes_json, intencion, grupo, canonica, relevancia, motivo,
                                            cobertura, url_propia, motivo_cobertura, cod_seo_tarea, fec_creacion)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                f["clave"], f["keyword"], texto(f["origenes"]), f["intencion"], f["grupo"], f["canonica"], f["relevancia"], f["motivo"],
                f["cobertura"], f["url_propia"], f["motivo_cobertura"], tarea, ahora,
            )
        }
    }

    @Suppress("UNCHECKED_CAST")
    fun keywords(): List<KeywordSeo> = jdbc.query(
        """SELECT keyword, origenes_json, intencion, grupo, canonica, relevancia, motivo, cobertura, url_propia, motivo_cobertura, evidencia
           FROM seo_keyword ORDER BY grupo, keyword""",
    ) { rs, _ ->
        KeywordSeo(
            rs.getString(1), lista(rs.getString(2)).map { it as Json }, rs.getString(3), rs.getString(4), rs.getString(5),
            rs.getObject(6)?.let { (it as Number).toInt() }, rs.getString(7), rs.getString(8), rs.getString(9), rs.getString(10), rs.getString(11),
        )
    }

    // ── Articulos ──

    private val columnasArticulo = """a.cod_seo_articulo, a.grupo, a.keyword, a.variantes_json, a.origenes_json, a.indicaciones, a.titulo, a.slug,
        a.meta_description, a.contenido, a.pendientes_json, a.cod_seo_tarea, t.estado AS tarea_estado, t.error AS tarea_error,
        a.wp_id, a.wp_estado, a.wp_enlace, a.wp_editar, a.fec_enviado, a.fec_redactado, a.cod_autor, a.fec_creacion, a.fec_modif,
        i.fuente AS i_fuente, i.mime AS i_mime, LENGTH(i.datos) AS i_bytes, i.alt_text AS i_alt, i.leyenda AS i_leyenda, i.autor AS i_autor,
        i.autor_url AS i_autor_url, i.origen_url AS i_origen_url, i.prompt AS i_prompt, i.modelo AS i_modelo, i.wp_media_id AS i_media,
        i.fec_modif AS i_modif
        FROM seo_articulo a LEFT JOIN seo_tarea t ON t.cod_seo_tarea = a.cod_seo_tarea
        LEFT JOIN seo_imagen i ON i.cod_seo_articulo = a.cod_seo_articulo"""

    @Suppress("UNCHECKED_CAST")
    private val articulo = { rs: java.sql.ResultSet, _: Int ->
        ArticuloSeo(
            rs.getString("cod_seo_articulo"), rs.getString("grupo"), rs.getString("keyword"), lista(rs.getString("variantes_json")).map { it.toString() },
            lista(rs.getString("origenes_json")).map { it as Json }, rs.getString("indicaciones"), rs.getString("titulo"), rs.getString("slug"),
            rs.getString("meta_description"), rs.getString("contenido"), lista(rs.getString("pendientes_json")).map { it.toString() },
            rs.getString("cod_seo_tarea"), rs.getString("tarea_estado"), rs.getString("tarea_error"),
            rs.getObject("wp_id")?.let { (it as Number).toLong() }, rs.getString("wp_estado"), rs.getString("wp_enlace"), rs.getString("wp_editar"),
            rs.getString("fec_enviado")?.let(Instant::parse), rs.getString("fec_redactado")?.let(Instant::parse), rs.getString("cod_autor"),
            Instant.parse(rs.getString("fec_creacion")), Instant.parse(rs.getString("fec_modif")),
            rs.getString("i_fuente")?.let { fuente ->
                ImagenSeo(
                    fuente, rs.getString("i_mime"), rs.getInt("i_bytes"), rs.getString("i_alt"), rs.getString("i_leyenda"), rs.getString("i_autor"),
                    rs.getString("i_autor_url"), rs.getString("i_origen_url"), rs.getString("i_prompt"), rs.getString("i_modelo"),
                    rs.getObject("i_media")?.let { (it as Number).toLong() }, Instant.parse(rs.getString("i_modif")),
                )
            },
        )
    }

    fun articulos(): List<ArticuloSeo> = jdbc.query("SELECT $columnasArticulo ORDER BY a.id_seo_articulo DESC", articulo)

    fun articulo(codigo: String): ArticuloSeo =
        jdbc.query("SELECT $columnasArticulo WHERE a.cod_seo_articulo = ?", articulo, codigo).firstOrNull()
            ?: throw NoEncontrado("No existe el artículo $codigo.")

    fun articuloDeGrupo(grupo: String): ArticuloSeo? = jdbc.query("SELECT $columnasArticulo WHERE a.grupo = ?", articulo, grupo).firstOrNull()

    fun articuloDeTarea(tarea: String): ArticuloSeo? = jdbc.query("SELECT $columnasArticulo WHERE a.cod_seo_tarea = ?", articulo, tarea).firstOrNull()

    fun crearArticulo(grupo: String, keyword: String, variantes: List<String>, origenes: List<Json>, autor: String?): String = tx.execute {
        val n = (jdbc.queryForObject("SELECT COALESCE(MAX(id_seo_articulo), 0) + 1 FROM seo_articulo", Int::class.java) ?: 1)
        val codigo = "AR%04d".format(n)
        jdbc.update(
            """INSERT INTO seo_articulo (cod_seo_articulo, grupo, keyword, variantes_json, origenes_json, cod_autor, fec_creacion, fec_modif)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            codigo, grupo, keyword, texto(variantes), texto(origenes), autor, ahora(), ahora(),
        )
        codigo
    }!!

    fun redaccionEncargada(codigo: String, tarea: String, indicaciones: String?) {
        jdbc.update("UPDATE seo_articulo SET cod_seo_tarea = ?, indicaciones = ? WHERE cod_seo_articulo = ?", tarea, indicaciones, codigo)
    }

    fun guardarRedaccion(codigo: String, r: Json) {
        val ahora = ahora()
        jdbc.update(
            """UPDATE seo_articulo SET titulo = ?, slug = ?, meta_description = ?, contenido = ?, pendientes_json = ?, fec_redactado = ?, fec_modif = ?
               WHERE cod_seo_articulo = ?""",
            r["titulo"], r["slug"], r["meta_description"], r["contenido"], texto(r["pendientes"] ?: emptyList<String>()), ahora, ahora, codigo,
        )
    }

    fun editarArticulo(codigo: String, titulo: String, slug: String, metaDescription: String, contenido: String) {
        jdbc.update(
            "UPDATE seo_articulo SET titulo = ?, slug = ?, meta_description = ?, contenido = ?, fec_modif = ? WHERE cod_seo_articulo = ?",
            titulo, slug, metaDescription, contenido, ahora(), codigo,
        )
    }

    /** Envio a WordPress: modificado = enviado, asi «cambios sin enviar» arranca en falso. */
    fun marcarEnviado(codigo: String, wp: Json) {
        val ahora = ahora()
        jdbc.update(
            "UPDATE seo_articulo SET wp_id = ?, wp_estado = ?, wp_enlace = ?, wp_editar = ?, fec_enviado = ?, fec_modif = ? WHERE cod_seo_articulo = ?",
            (wp["id"] as? Number)?.toLong(), wp["estado"], wp["enlace"], wp["editar"], ahora, ahora, codigo,
        )
    }

    fun desvincular(codigo: String) {
        jdbc.update(
            "UPDATE seo_articulo SET wp_id = NULL, wp_estado = NULL, wp_enlace = NULL, wp_editar = NULL, fec_enviado = NULL, fec_modif = ? WHERE cod_seo_articulo = ?",
            ahora(), codigo,
        )
    }

    fun borrarArticulo(codigo: String) {
        tx.executeWithoutResult {
            jdbc.update("DELETE FROM seo_imagen WHERE cod_seo_articulo = ?", codigo)
            jdbc.update("DELETE FROM seo_articulo WHERE cod_seo_articulo = ?", codigo)
        }
    }

    // ── Imagen destacada ──

    /** Pone (o sustituye) la imagen. Cuenta como cambio del articulo: «cambios sin enviar». */
    fun guardarImagen(codigo: String, fuente: String, datos: ByteArray, mime: String, alt: String?, leyenda: String?, autor: String?,
                      autorUrl: String?, origenUrl: String?, prompt: String?, modelo: String?, codAutor: String?) {
        tx.executeWithoutResult {
            val ahora = ahora()
            jdbc.update("DELETE FROM seo_imagen WHERE cod_seo_articulo = ?", codigo)
            jdbc.update(
                """INSERT INTO seo_imagen (cod_seo_articulo, fuente, datos, mime, alt_text, leyenda, autor, autor_url, origen_url, prompt, modelo,
                   cod_autor, fec_creacion, fec_modif) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                codigo, fuente, datos, mime, alt, leyenda, autor, autorUrl, origenUrl, prompt, modelo, codAutor, ahora, ahora,
            )
            jdbc.update("UPDATE seo_articulo SET fec_modif = ? WHERE cod_seo_articulo = ?", ahora, codigo)
        }
    }

    fun archivoImagen(codigo: String): Pair<ByteArray, String>? =
        jdbc.query("SELECT datos, mime FROM seo_imagen WHERE cod_seo_articulo = ?", { rs, _ -> rs.getBytes(1) to rs.getString(2) }, codigo).firstOrNull()

    fun textosImagen(codigo: String, alt: String, leyenda: String) {
        tx.executeWithoutResult {
            val ahora = ahora()
            jdbc.update("UPDATE seo_imagen SET alt_text = ?, leyenda = ?, fec_modif = ? WHERE cod_seo_articulo = ?", alt, leyenda, ahora, codigo)
            jdbc.update("UPDATE seo_articulo SET fec_modif = ? WHERE cod_seo_articulo = ?", ahora, codigo)
        }
    }

    fun quitarImagen(codigo: String) {
        tx.executeWithoutResult {
            jdbc.update("DELETE FROM seo_imagen WHERE cod_seo_articulo = ?", codigo)
            jdbc.update("UPDATE seo_articulo SET fec_modif = ? WHERE cod_seo_articulo = ?", ahora(), codigo)
        }
    }

    /** Ya esta en la biblioteca de WordPress: el proximo envio la reutiliza en vez de subirla otra vez. */
    fun imagenSubida(codigo: String, mediaId: Long?) {
        jdbc.update("UPDATE seo_imagen SET wp_media_id = ? WHERE cod_seo_articulo = ?", mediaId, codigo)
    }

    // ── Search Console ──

    fun reemplazarGsc(filas: List<FilaGsc>) = tx.executeWithoutResult {
        jdbc.update("DELETE FROM seo_gsc")
        jdbc.batchUpdate(
            "INSERT INTO seo_gsc (consulta, orden, url, clics, impresiones, ctr, posicion) VALUES (?, ?, ?, ?, ?, ?, ?)",
            filas.map { arrayOf<Any?>(it.consulta, it.orden, it.url, it.clics, it.impresiones, it.ctr, it.posicion) },
        )
    }

    fun gscDe(ordenes: Collection<String>): List<FilaGsc> = ordenes.distinct().chunked(500).flatMap { lote ->
        jdbc.query(
            "SELECT consulta, orden, url, clics, impresiones, ctr, posicion FROM seo_gsc WHERE orden IN (${lote.joinToString(",") { "?" }})",
            filaGsc, *lote.toTypedArray(),
        )
    }

    fun resumenGsc(): Map<String, Long> = jdbc.queryForObject(
        "SELECT COUNT(DISTINCT orden), COALESCE(SUM(clics), 0), COALESCE(SUM(impresiones), 0) FROM seo_gsc",
    ) { rs, _ -> mapOf("consultas" to rs.getLong(1), "clics" to rs.getLong(2), "impresiones" to rs.getLong(3)) }!!

    /** Filas con la posicion media en [desde, hasta] y al menos `minImpresiones`, de mas a menos impresiones. */
    fun gscEntre(desde: Double, hasta: Double, minImpresiones: Int): List<FilaGsc> = jdbc.query(
        """SELECT consulta, orden, url, clics, impresiones, ctr, posicion FROM seo_gsc
           WHERE posicion >= ? AND posicion <= ? AND impresiones >= ? ORDER BY impresiones DESC""",
        filaGsc, desde, hasta, minImpresiones,
    )

    // ── Mejoras de paginas propias ──

    fun guardarMejora(url: String, consultas: List<Json>, actual: Json, propuesta: Json, autor: String?) {
        val ahora = ahora()
        jdbc.update(
            """INSERT INTO seo_mejora (url, consultas_json, titulo_actual, meta_actual, titulo, meta_description, ideas_json, motivo, estado,
                                       cod_autor, fec_creacion, fec_modif)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PROPUESTA', ?, ?, ?)
               ON CONFLICT(url) DO UPDATE SET consultas_json = excluded.consultas_json, titulo_actual = excluded.titulo_actual,
                 meta_actual = excluded.meta_actual, titulo = excluded.titulo, meta_description = excluded.meta_description,
                 ideas_json = excluded.ideas_json, motivo = excluded.motivo, estado = 'PROPUESTA', cod_autor = excluded.cod_autor,
                 fec_creacion = excluded.fec_creacion, fec_modif = excluded.fec_modif""",
            url, texto(consultas), actual["title"] as? String, actual["meta_description"] as? String, propuesta["titulo"] as? String ?: "",
            propuesta["meta_description"] as? String ?: "", texto(propuesta["ideas"] ?: emptyList<String>()), propuesta["motivo"] as? String,
            autor, ahora, ahora,
        )
    }

    fun mejoras(): List<MejoraSeo> = jdbc.query(
        """SELECT url, consultas_json, titulo_actual, meta_actual, titulo, meta_description, ideas_json, motivo, estado, fec_creacion, fec_modif
           FROM seo_mejora ORDER BY id_seo_mejora DESC""",
    ) { rs, _ ->
        MejoraSeo(
            rs.getString(1), lista(rs.getString(2)).filterIsInstance<Map<*, *>>().map { m -> m.entries.associate { it.key.toString() to it.value } },
            rs.getString(3), rs.getString(4), rs.getString(5), rs.getString(6), lista(rs.getString(7)).mapNotNull(::idea), rs.getString(8),
            rs.getString(9), Instant.parse(rs.getString(10)), Instant.parse(rs.getString(11)),
        )
    }

    /** Las propuestas de antes del 2026-11-03 eran frases sueltas: quedan como «debe decir» sin lugar ni texto actual. */
    private fun idea(v: Any?): IdeaMejora? = when (v) {
        is String -> IdeaMejora("", null, v)
        is Map<*, *> -> (v["debe_decir"] as? String)?.let { IdeaMejora(v["donde"] as? String ?: "", v["dice_ahora"] as? String, it) }
        else -> null
    }

    fun estadoMejora(url: String, estado: String): Boolean =
        jdbc.update("UPDATE seo_mejora SET estado = ?, fec_modif = ? WHERE url = ?", estado, ahora(), url) > 0

    private val filaGsc = RowMapper { rs, _ ->
        FilaGsc(rs.getString(1), rs.getString(2), rs.getString(3), rs.getInt(4), rs.getInt(5), rs.getDouble(6), rs.getDouble(7))
    }

    private companion object {
        /** Estados que se vuelven a intentar en el siguiente inventario. */
        val REINTENTAR = setOf("HTTP_ERROR", "ERROR", "BLOQUEADA")
        const val FECHA_PAGINA = "COALESCE(json_extract(datos_json, '$.publicado'), lastmod)"
    }
}
