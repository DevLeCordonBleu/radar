package pe.edu.lcb.radar.infraestructura

import org.springframework.jdbc.core.JdbcTemplate
import org.springframework.jdbc.core.RowMapper
import org.springframework.stereotype.Repository
import org.springframework.transaction.PlatformTransactionManager
import org.springframework.transaction.support.TransactionTemplate
import pe.edu.lcb.radar.dominio.NoEncontrado
import tools.jackson.databind.ObjectMapper
import java.time.Instant

data class ParteVideo(val dialogo: String, val escena: String = "")

data class Video(
    val codigo: String,
    val titulo: String,
    val idea: String,
    val keyword: String?,
    val segundos: Int,
    val formato: String,
    val partes: List<ParteVideo>,
    val copyFacebook: String?,
    val copyInstagram: String?,
    val hashtags: List<String>,
    val estado: String,
    val trabajo: String?,
    val avance: String?,
    val error: String?,
    val tieneArchivo: Boolean,
    val segundosReales: Double?,
    val vidsUrl: String?,
    val autor: String?,
    val creado: Instant,
    val modificado: Instant,
)

/** Lo editable de un video; `null` = no cambia. */
data class CambioVideo(
    val titulo: String? = null,
    val idea: String? = null,
    val keyword: String? = null,
    val segundos: Int? = null,
    val formato: String? = null,
    val partes: List<ParteVideo>? = null,
    val copyFacebook: String? = null,
    val copyInstagram: String? = null,
    val hashtags: List<String>? = null,
)

@Repository
class RepositorioVideos(private val jdbc: JdbcTemplate, private val json: ObjectMapper, transacciones: PlatformTransactionManager) {
    private val tx = TransactionTemplate(transacciones)

    private fun lista(texto: String?): List<Any?> = texto?.let { json.readValue(it, List::class.java) as List<Any?> } ?: emptyList()

    private fun ahora() = Instant.now().toString()

    private val fila = RowMapper { rs, _ ->
        Video(
            rs.getString("cod_video"), rs.getString("titulo"), rs.getString("idea"), rs.getString("keyword"), rs.getInt("segundos"),
            rs.getString("formato"),
            lista(rs.getString("partes_json")).filterIsInstance<Map<*, *>>().map { ParteVideo(it["dialogo"]?.toString().orEmpty(), it["escena"]?.toString().orEmpty()) },
            rs.getString("copy_facebook"), rs.getString("copy_instagram"), lista(rs.getString("hashtags_json")).map { it.toString() },
            rs.getString("estado"), rs.getString("trabajo"), rs.getString("avance"), rs.getString("error"), rs.getString("archivo") != null,
            rs.getDouble("segundos_reales").takeIf { !rs.wasNull() }, rs.getString("vids_url"), rs.getString("cod_autor"),
            Instant.parse(rs.getString("fec_creacion")), Instant.parse(rs.getString("fec_modif")),
        )
    }

    fun crear(idea: String, keyword: String?, segundos: Int, formato: String, autor: String?): String = tx.execute {
        val n = jdbc.queryForObject("SELECT COALESCE(MAX(id_video), 0) + 1 FROM video", Int::class.java) ?: 1
        val codigo = "V%04d".format(n)
        jdbc.update(
            """INSERT INTO video (cod_video, titulo, idea, keyword, segundos, formato, cod_autor, fec_creacion, fec_modif)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            codigo, idea.take(60), idea, keyword, segundos, formato, autor, ahora(), ahora(),
        )
        codigo
    }!!

    fun todos(): List<Video> = jdbc.query("SELECT * FROM video ORDER BY id_video DESC", fila)

    fun buscar(codigo: String): Video =
        jdbc.query("SELECT * FROM video WHERE cod_video = ?", fila, codigo).firstOrNull() ?: throw NoEncontrado("No existe el video $codigo.")

    fun enEstado(estado: String): List<Video> = jdbc.query("SELECT * FROM video WHERE estado = ?", fila, estado)

    fun archivo(codigo: String): String? =
        jdbc.query("SELECT archivo FROM video WHERE cod_video = ?", { rs, _ -> rs.getString(1) }, codigo).firstOrNull()

    fun cambiar(codigo: String, c: CambioVideo) {
        jdbc.update(
            """UPDATE video SET titulo = COALESCE(?, titulo), idea = COALESCE(?, idea), keyword = COALESCE(?, keyword),
                      segundos = COALESCE(?, segundos), formato = COALESCE(?, formato), partes_json = COALESCE(?, partes_json),
                      copy_facebook = COALESCE(?, copy_facebook), copy_instagram = COALESCE(?, copy_instagram),
                      hashtags_json = COALESCE(?, hashtags_json), fec_modif = ?
               WHERE cod_video = ?""",
            c.titulo, c.idea, c.keyword, c.segundos, c.formato, c.partes?.let { json.writeValueAsString(it) }, c.copyFacebook,
            c.copyInstagram, c.hashtags?.let { json.writeValueAsString(it) }, ahora(), codigo,
        )
    }

    fun estado(codigo: String, estado: String, avance: String? = null, error: String? = null, trabajo: String? = null) {
        jdbc.update(
            "UPDATE video SET estado = ?, avance = ?, error = ?, trabajo = ?, fec_modif = ? WHERE cod_video = ?",
            estado, avance, error, trabajo, ahora(), codigo,
        )
    }

    fun avance(codigo: String, avance: String) {
        jdbc.update("UPDATE video SET avance = ? WHERE cod_video = ?", avance, codigo)
    }

    fun terminado(codigo: String, archivo: String, segundos: Double?, vidsUrl: String?) {
        jdbc.update(
            """UPDATE video SET estado = 'GENERADO', archivo = ?, segundos_reales = ?, vids_url = ?, trabajo = NULL, avance = NULL,
                      error = NULL, fec_modif = ? WHERE cod_video = ?""",
            archivo, segundos, vidsUrl, ahora(), codigo,
        )
    }

    fun borrar(codigo: String) {
        jdbc.update("DELETE FROM video WHERE cod_video = ?", codigo)
    }
}
