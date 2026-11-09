package pe.edu.lcb.radar.infraestructura

import org.slf4j.LoggerFactory
import org.springframework.beans.factory.InitializingBean
import org.springframework.jdbc.core.JdbcTemplate
import org.springframework.stereotype.Component

/**
 * Columnas nuevas en tablas que ya existian. El esquema (04_bd) solo crea lo que falta con
 * `CREATE TABLE IF NOT EXISTS`, asi que una columna anadida despues no llega a una base vieja:
 * se anade aqui. El esquema tambien la declara, para las bases nuevas.
 *
 * Corre despues del esquema: Spring Boot inicializa la base antes de crear el JdbcTemplate.
 */
@Component
class MigracionesBd(private val jdbc: JdbcTemplate) : InitializingBean {
    private val log = LoggerFactory.getLogger(javaClass)

    override fun afterPropertiesSet() {
        columna("publicacion", "modo_copy", "TEXT NOT NULL DEFAULT 'POR_RED'")
        columna("publicacion", "flyer_json", "TEXT")
        columna("publicacion", "archivada", "INTEGER NOT NULL DEFAULT 0")
        columna("publicacion", "verificacion_json", "TEXT")
    }

    private fun columna(tabla: String, nombre: String, definicion: String) {
        val hay = jdbc.query("PRAGMA table_info($tabla)") { rs, _ -> rs.getString("name") }
        if (hay.isNotEmpty() && nombre !in hay) {
            jdbc.execute("ALTER TABLE $tabla ADD COLUMN $nombre $definicion")
            log.info("Base: añadida la columna {}.{}", tabla, nombre)
        }
    }
}
