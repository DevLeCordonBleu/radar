package pe.edu.lcb.radar.infraestructura

import org.springframework.jdbc.core.JdbcTemplate
import org.springframework.jdbc.core.RowMapper
import org.springframework.stereotype.Repository
import org.springframework.transaction.PlatformTransactionManager
import org.springframework.transaction.support.TransactionTemplate
import com.fasterxml.jackson.annotation.JsonIgnore
import pe.edu.lcb.radar.dominio.NoEncontrado
import tools.jackson.databind.ObjectMapper
import java.time.Instant

/**
 * El flyer: sus textos (los escribe la IA y se editan), de donde salio el fondo y si la imagen de la
 * publicacion es este flyer (`enUso`) o un archivo subido aparte.
 */
data class FlyerPublicacion(
    val titulo: String = "",
    val detalle: String = "",
    val cta: String = "",
    /** Que buscar en el banco de fotos. */
    val busqueda: String = "",
    /** Que pedirle a la IA si el fondo se crea a medida. */
    val descripcion: String = "",
    val fondoOrigen: String? = null,
    val fondoCredito: String? = null,
    val fondoUrl: String? = null,
    @get:JsonIgnore val fondoTipo: String? = null,
    val enUso: Boolean = false,
) {
    val tieneFondo: Boolean get() = fondoTipo != null
}

/** Ultima comprobacion de un enlace publicado. `estado`: ACTIVA | NO_DISPONIBLE | SIN_CONFIRMAR. */
data class VerificacionEnlace(val estado: String, val detalle: String, val http: Int?, val fecha: Instant)

/** Lo que le paso a una publicacion, para la biblioteca (auditoria). */
data class EventoPublicacion(val evento: String, val detalle: String, val datos: Map<String, Any?>?, val autor: String?, val fecha: Instant)

data class Publicacion(
    val codigo: String,
    val titulo: String,
    val idea: String,
    val origen: String,
    val codOrigen: String?,
    val redes: List<String>,
    val textos: Map<String, String>,
    val hashtags: List<String>,
    val media: String,
    val archivoTipo: String?,
    val enlaces: Map<String, String>,
    val modoCopy: String,
    val flyer: FlyerPublicacion,
    val archivada: Boolean,
    val verificacion: Map<String, VerificacionEnlace>,
    val estado: String,
    val aprobador: String?,
    val autor: String?,
    val creado: Instant,
    val modificado: Instant,
)

/** Lo editable de una publicacion; `null` = no cambia. */
data class CambioPublicacion(
    val titulo: String? = null,
    val idea: String? = null,
    val redes: List<String>? = null,
    val textos: Map<String, String>? = null,
    val hashtags: List<String>? = null,
    val modoCopy: String? = null,
    /** Solo se leen sus textos (titulo, detalle, cta, busqueda, descripcion). */
    val flyer: FlyerPublicacion? = null,
)

@Repository
class RepositorioPublicaciones(private val jdbc: JdbcTemplate, private val json: ObjectMapper, transacciones: PlatformTransactionManager) {
    private val tx = TransactionTemplate(transacciones)

    private fun lista(texto: String?): List<String> =
        texto?.let { json.readValue(it, List::class.java) as List<*> }.orEmpty().map { it.toString() }

    private fun mapa(texto: String?): Map<String, String> =
        texto?.let { json.readValue(it, Map::class.java) as Map<*, *> }.orEmpty().entries.associate { it.key.toString() to it.value.toString() }

    private fun ahora() = Instant.now().toString()

    private fun flyer(texto: String?): FlyerPublicacion {
        val m = texto?.let { json.readValue(it, Map::class.java) as Map<*, *> }.orEmpty()
        fun t(k: String) = m[k]?.toString()
        return FlyerPublicacion(
            t("titulo").orEmpty(), t("detalle").orEmpty(), t("cta").orEmpty(), t("busqueda").orEmpty(), t("descripcion").orEmpty(),
            t("fondoOrigen"), t("fondoCredito"), t("fondoUrl"), t("fondoTipo"), m["enUso"] == true,
        )
    }

    private fun verificacion(texto: String?): Map<String, VerificacionEnlace> =
        texto?.let { json.readValue(it, Map::class.java) as Map<*, *> }.orEmpty().entries.mapNotNull { (red, v) ->
            val m = v as? Map<*, *> ?: return@mapNotNull null
            red.toString() to VerificacionEnlace(m["estado"].toString(), m["detalle"]?.toString().orEmpty(), (m["http"] as? Number)?.toInt(),
                Instant.parse(m["fecha"].toString()))
        }.toMap()

    private val fila = RowMapper { rs, _ ->
        Publicacion(
            rs.getString("cod_publicacion"), rs.getString("titulo"), rs.getString("idea"), rs.getString("origen"), rs.getString("cod_origen"),
            lista(rs.getString("redes_json")), mapa(rs.getString("textos_json")), lista(rs.getString("hashtags_json")), rs.getString("media"),
            rs.getString("archivo_tipo"), mapa(rs.getString("enlaces_json")), rs.getString("modo_copy"), flyer(rs.getString("flyer_json")),
            rs.getInt("archivada") == 1, verificacion(rs.getString("verificacion_json")), rs.getString("estado"), rs.getString("cod_aprobador"),
            rs.getString("cod_autor"), Instant.parse(rs.getString("fec_creacion")), Instant.parse(rs.getString("fec_modif")),
        )
    }

    fun crear(
        idea: String,
        redes: List<String>,
        autor: String?,
        titulo: String = idea.take(60),
        origen: String = "MANUAL",
        codOrigen: String? = null,
        textos: Map<String, String> = emptyMap(),
        hashtags: List<String> = emptyList(),
        modoCopy: String = "POR_RED",
    ): String = tx.execute {
        val n = jdbc.queryForObject("SELECT COALESCE(MAX(id_publicacion), 0) + 1 FROM publicacion", Int::class.java) ?: 1
        val codigo = "P%04d".format(n)
        jdbc.update(
            """INSERT INTO publicacion (cod_publicacion, titulo, idea, origen, cod_origen, redes_json, textos_json, hashtags_json,
                                        modo_copy, cod_autor, fec_creacion, fec_modif)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            codigo, titulo, idea, origen, codOrigen, json.writeValueAsString(redes), json.writeValueAsString(textos),
            json.writeValueAsString(hashtags), modoCopy, autor, ahora(), ahora(),
        )
        codigo
    }!!

    /** Sin `archivadas`, las que siguen en curso; con, toda la biblioteca. */
    fun todas(archivadas: Boolean = false): List<Publicacion> =
        jdbc.query("SELECT * FROM publicacion ${if (archivadas) "" else "WHERE archivada = 0 "}ORDER BY id_publicacion DESC", fila)

    fun buscar(codigo: String): Publicacion =
        jdbc.query("SELECT * FROM publicacion WHERE cod_publicacion = ?", fila, codigo).firstOrNull()
            ?: throw NoEncontrado("No existe la publicación $codigo.")

    fun deVideo(codVideo: String): Publicacion? =
        jdbc.query("SELECT * FROM publicacion WHERE origen = 'VIDEO' AND cod_origen = ? ORDER BY id_publicacion", fila, codVideo).firstOrNull()

    fun archivo(codigo: String): String? =
        jdbc.query("SELECT archivo FROM publicacion WHERE cod_publicacion = ?", { rs, _ -> rs.getString(1) }, codigo).firstOrNull()

    fun cambiar(codigo: String, c: CambioPublicacion) {
        jdbc.update(
            """UPDATE publicacion SET titulo = COALESCE(?, titulo), idea = COALESCE(?, idea), redes_json = COALESCE(?, redes_json),
                      textos_json = COALESCE(?, textos_json), hashtags_json = COALESCE(?, hashtags_json),
                      modo_copy = COALESCE(?, modo_copy), fec_modif = ?
               WHERE cod_publicacion = ?""",
            c.titulo, c.idea, c.redes?.let { json.writeValueAsString(it) }, c.textos?.let { json.writeValueAsString(it) },
            c.hashtags?.let { json.writeValueAsString(it) }, c.modoCopy, ahora(), codigo,
        )
    }

    /** Guarda el flyer entero (textos, fondo y si esta en uso). */
    fun guardarFlyer(codigo: String, f: FlyerPublicacion) {
        val m = mapOf(
            "titulo" to f.titulo, "detalle" to f.detalle, "cta" to f.cta, "busqueda" to f.busqueda, "descripcion" to f.descripcion,
            "fondoOrigen" to f.fondoOrigen, "fondoCredito" to f.fondoCredito, "fondoUrl" to f.fondoUrl, "fondoTipo" to f.fondoTipo,
            "enUso" to f.enUso,
        )
        jdbc.update("UPDATE publicacion SET flyer_json = ?, fec_modif = ? WHERE cod_publicacion = ?", json.writeValueAsString(m), ahora(), codigo)
    }

    /** `archivo = null` quita la imagen o el video. */
    fun media(codigo: String, media: String, archivo: String?, tipo: String?) {
        jdbc.update(
            "UPDATE publicacion SET media = ?, archivo = ?, archivo_tipo = ?, fec_modif = ? WHERE cod_publicacion = ?",
            media, archivo, tipo, ahora(), codigo,
        )
    }

    fun estado(codigo: String, estado: String, aprobador: String? = null) {
        jdbc.update(
            "UPDATE publicacion SET estado = ?, cod_aprobador = ?, fec_modif = ? WHERE cod_publicacion = ?",
            estado, aprobador, ahora(), codigo,
        )
    }

    fun enlaces(codigo: String, enlaces: Map<String, String>, estado: String) {
        jdbc.update(
            "UPDATE publicacion SET enlaces_json = ?, estado = ?, fec_modif = ? WHERE cod_publicacion = ?",
            json.writeValueAsString(enlaces), estado, ahora(), codigo,
        )
    }

    fun archivar(codigo: String, archivada: Boolean) {
        jdbc.update("UPDATE publicacion SET archivada = ?, fec_modif = ? WHERE cod_publicacion = ?", if (archivada) 1 else 0, ahora(), codigo)
    }

    fun verificacion(codigo: String, v: Map<String, VerificacionEnlace>) {
        val m = v.mapValues { (_, x) -> mapOf("estado" to x.estado, "detalle" to x.detalle, "http" to x.http, "fecha" to x.fecha.toString()) }
        jdbc.update("UPDATE publicacion SET verificacion_json = ? WHERE cod_publicacion = ?", json.writeValueAsString(m), codigo)
    }

    fun evento(codigo: String, evento: String, detalle: String, datos: Map<String, Any?>?, autor: String?) {
        jdbc.update(
            "INSERT INTO publicacion_evento (cod_publicacion, evento, detalle, datos_json, cod_autor, fec_creacion) VALUES (?, ?, ?, ?, ?, ?)",
            codigo, evento, detalle, datos?.let { json.writeValueAsString(it) }, autor, ahora(),
        )
    }

    @Suppress("UNCHECKED_CAST")
    fun eventos(codigo: String): List<EventoPublicacion> = jdbc.query(
        "SELECT evento, detalle, datos_json, cod_autor, fec_creacion FROM publicacion_evento WHERE cod_publicacion = ? ORDER BY id_publicacion_evento",
        { rs, _ ->
            EventoPublicacion(rs.getString(1), rs.getString(2), rs.getString(3)?.let { json.readValue(it, Map::class.java) as Map<String, Any?> },
                rs.getString(4), Instant.parse(rs.getString(5)))
        },
        codigo,
    )
}
