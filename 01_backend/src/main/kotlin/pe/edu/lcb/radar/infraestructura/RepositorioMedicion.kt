package pe.edu.lcb.radar.infraestructura

import org.springframework.jdbc.core.JdbcTemplate
import org.springframework.stereotype.Repository
import org.springframework.transaction.PlatformTransactionManager
import org.springframework.transaction.support.TransactionTemplate

/** Un anuncio en un dia (o la suma de varios dias, segun la consulta). */
data class FilaMeta(
    val fecha: String,
    val anuncioId: String,
    val anuncio: String,
    val conjuntoId: String?,
    val conjunto: String?,
    val campanaId: String,
    val campana: String,
    val objetivo: String?,
    val gasto: Double,
    val impresiones: Long,
    val alcance: Long,
    val clics: Long,
    val clicsEnlace: Long,
    val leads: Long,
    val conversaciones: Long,
    val visitas: Long,
)

@Repository
class RepositorioMedicion(private val jdbc: JdbcTemplate, transacciones: PlatformTransactionManager) {
    private val tx = TransactionTemplate(transacciones)

    /** Reemplaza el tramo [desde, hasta] con lo que trajo Meta. */
    fun reemplazar(desde: String, hasta: String, filas: List<FilaMeta>) = tx.executeWithoutResult {
        jdbc.update("DELETE FROM meta_insight WHERE fecha >= ? AND fecha <= ?", desde, hasta)
        jdbc.batchUpdate(
            """INSERT OR REPLACE INTO meta_insight (fecha, anuncio_id, anuncio, conjunto_id, conjunto, campana_id, campana, objetivo, gasto,
                      impresiones, alcance, clics, clics_enlace, leads, conversaciones, visitas)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            filas.map {
                arrayOf<Any?>(it.fecha, it.anuncioId, it.anuncio, it.conjuntoId, it.conjunto, it.campanaId, it.campana, it.objetivo, it.gasto,
                    it.impresiones, it.alcance, it.clics, it.clicsEnlace, it.leads, it.conversaciones, it.visitas)
            },
        )
    }

    /** (primera, ultima, filas) de lo guardado; null si no hay nada. */
    fun rango(): Triple<String, String, Int>? = jdbc.query("SELECT MIN(fecha), MAX(fecha), COUNT(*) FROM meta_insight") { rs, _ ->
        rs.getString(1)?.let { Triple(it, rs.getString(2), rs.getInt(3)) }
    }.firstOrNull()

    /** Las filas diarias del periodo. */
    fun filas(desde: String, hasta: String): List<FilaMeta> = jdbc.query(
        """SELECT fecha, anuncio_id, anuncio, conjunto_id, conjunto, campana_id, campana, objetivo, gasto, impresiones, alcance, clics,
                  clics_enlace, leads, conversaciones, visitas
           FROM meta_insight WHERE fecha >= ? AND fecha <= ? ORDER BY fecha""",
        { rs, _ ->
            FilaMeta(
                rs.getString(1), rs.getString(2), rs.getString(3), rs.getString(4), rs.getString(5), rs.getString(6), rs.getString(7),
                rs.getString(8), rs.getDouble(9), rs.getLong(10), rs.getLong(11), rs.getLong(12), rs.getLong(13), rs.getLong(14),
                rs.getLong(15), rs.getLong(16),
            )
        },
        desde, hasta,
    )
}
