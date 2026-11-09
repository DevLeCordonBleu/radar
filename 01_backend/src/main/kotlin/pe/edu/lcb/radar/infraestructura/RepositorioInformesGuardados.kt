package pe.edu.lcb.radar.infraestructura

import org.springframework.jdbc.core.JdbcTemplate
import org.springframework.jdbc.core.RowMapper
import org.springframework.stereotype.Repository
import pe.edu.lcb.radar.dominio.NoEncontrado
import tools.jackson.databind.ObjectMapper
import java.io.ByteArrayOutputStream
import java.time.Instant
import java.util.zip.GZIPInputStream
import java.util.zip.GZIPOutputStream

/**
 * Un informe guardado tal como estaba el dia que se hizo: cada corte de Search Console y cada
 * lista de keywords del Plan SEO. Nunca se borra ni se cambia (es la auditoria); los datos van
 * comprimidos porque un corte de Search Console son ~20 000 filas.
 * `modulo`: SEARCH_CONSOLE | PLAN_SEO_KEYWORDS.
 */
data class InformeGuardado(
    val codigo: String,
    val modulo: String,
    val titulo: String,
    val resumen: Map<String, Any?>,
    val filas: Int,
    /** La tarea o la accion que lo genero (p. ej. la tarea de keywords). */
    val origen: String?,
    val autor: String?,
    val creado: Instant,
)

@Repository
class RepositorioInformesGuardados(private val jdbc: JdbcTemplate, private val json: ObjectMapper) {

    fun guardar(modulo: String, titulo: String, resumen: Map<String, Any?>, datos: List<Map<String, Any?>>, origen: String?, autor: String?): InformeGuardado {
        val n = jdbc.queryForObject("SELECT COALESCE(MAX(id_informe_guardado), 0) + 1 FROM informe_guardado", Int::class.java) ?: 1
        val codigo = "IG%04d".format(n)
        jdbc.update(
            """INSERT INTO informe_guardado (cod_informe_guardado, modulo, titulo, resumen_json, datos_gz, filas, cod_origen, cod_autor, fec_creacion)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            codigo, modulo, titulo, json.writeValueAsString(resumen), comprimir(json.writeValueAsBytes(datos)), datos.size, origen, autor,
            Instant.now().toString(),
        )
        return buscar(codigo)
    }

    fun todos(modulo: String?): List<InformeGuardado> =
        if (modulo == null) jdbc.query("SELECT $COLUMNAS FROM informe_guardado ORDER BY id_informe_guardado DESC", fila)
        else jdbc.query("SELECT $COLUMNAS FROM informe_guardado WHERE modulo = ? ORDER BY id_informe_guardado DESC", fila, modulo)

    fun hay(modulo: String): Boolean =
        (jdbc.queryForObject("SELECT COUNT(*) FROM informe_guardado WHERE modulo = ?", Int::class.java, modulo) ?: 0) > 0

    fun buscar(codigo: String): InformeGuardado =
        jdbc.query("SELECT $COLUMNAS FROM informe_guardado WHERE cod_informe_guardado = ?", fila, codigo).firstOrNull()
            ?: throw NoEncontrado("No existe el informe guardado $codigo.")

    @Suppress("UNCHECKED_CAST")
    fun datos(codigo: String): List<Map<String, Any?>> {
        val gz = jdbc.query("SELECT datos_gz FROM informe_guardado WHERE cod_informe_guardado = ?", { rs, _ -> rs.getBytes(1) }, codigo).firstOrNull()
            ?: throw NoEncontrado("No existe el informe guardado $codigo.")
        return json.readValue(GZIPInputStream(gz.inputStream()).use { it.readBytes() }, List::class.java) as List<Map<String, Any?>>
    }

    private fun comprimir(b: ByteArray): ByteArray = ByteArrayOutputStream().also { o -> GZIPOutputStream(o).use { it.write(b) } }.toByteArray()

    @Suppress("UNCHECKED_CAST")
    private val fila = RowMapper { rs, _ ->
        InformeGuardado(
            rs.getString(1), rs.getString(2), rs.getString(3), json.readValue(rs.getString(4), Map::class.java) as Map<String, Any?>,
            rs.getInt(5), rs.getString(6), rs.getString(7), Instant.parse(rs.getString(8)),
        )
    }

    private companion object {
        const val COLUMNAS = "cod_informe_guardado, modulo, titulo, resumen_json, filas, cod_origen, cod_autor, fec_creacion"
    }
}
