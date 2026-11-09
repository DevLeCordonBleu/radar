package pe.edu.lcb.radar.infraestructura

import org.springframework.jdbc.core.JdbcTemplate
import org.springframework.stereotype.Repository
import pe.edu.lcb.radar.dominio.Analisis
import pe.edu.lcb.radar.dominio.Avance
import pe.edu.lcb.radar.dominio.Estado
import pe.edu.lcb.radar.dominio.Fase
import pe.edu.lcb.radar.dominio.InformeFila
import pe.edu.lcb.radar.dominio.Json
import pe.edu.lcb.radar.dominio.NoEncontrado
import pe.edu.lcb.radar.dominio.Pendiente
import pe.edu.lcb.radar.dominio.Peticion
import tools.jackson.databind.ObjectMapper
import java.sql.ResultSet
import java.time.Instant

/** Persistencia en SQLite. El unico lugar del backend que conoce SQL. */
@Repository
class RepositorioAnalisis(private val jdbc: JdbcTemplate, private val json: ObjectMapper) {

    private val mapeo = { rs: ResultSet, _: Int ->
        Analisis(
            codigo = rs.getString("cod_analisis"),
            peticion = json.readValue(rs.getString("peticion_json"), Peticion::class.java),
            estado = Estado.de(rs.getString("estado")),
            fase = Fase.de(rs.getString("fase")),
            mensaje = rs.getString("mensaje"),
            hechos = rs.getInt("hechos"),
            total = rs.getInt("total"),
            error = rs.getString("error"),
            pendiente = rs.getString("pendiente_json")?.let { json.readValue(it, Pendiente::class.java) },
            codInforme = rs.getString("cod_informe"),
            creado = Instant.parse(rs.getString("fec_creacion")),
            modificado = Instant.parse(rs.getString("fec_modif")),
        )
    }

    fun crear(p: Peticion): Analisis {
        val ahora = Instant.now().toString()
        val n = (jdbc.queryForObject("SELECT COALESCE(MAX(id_analisis), 0) + 1 FROM analisis", Int::class.java) ?: 1)
        val codigo = "A%04d".format(n)
        jdbc.update(
            "INSERT INTO analisis (cod_analisis, peticion_json, fec_creacion, fec_modif) VALUES (?, ?, ?, ?)",
            codigo, json.writeValueAsString(p), ahora, ahora,
        )
        return buscar(codigo)
    }

    fun todos(): List<Analisis> =
        jdbc.query("SELECT * FROM analisis WHERE estado_reg = 1 ORDER BY id_analisis DESC", mapeo)

    fun buscar(codigo: String): Analisis =
        jdbc.query("SELECT * FROM analisis WHERE cod_analisis = ? AND estado_reg = 1", mapeo, codigo)
            .firstOrNull() ?: throw NoEncontrado("No existe el analisis $codigo.")

    fun enEstado(vararg estados: Estado): List<Analisis> {
        val marcas = estados.joinToString(",") { "?" }
        return jdbc.query("SELECT * FROM analisis WHERE estado_reg = 1 AND estado IN ($marcas)", mapeo, *estados.map { it.clave }.toTypedArray())
    }

    /** Cambia el estado, y con el la fase/mensaje/error visibles en el panel. */
    fun estado(codigo: String, estado: Estado, fase: Fase? = null, mensaje: String? = null, error: String? = null, limpiarError: Boolean = false) {
        jdbc.update(
            """UPDATE analisis SET estado = ?, fase = COALESCE(?, fase), mensaje = COALESCE(?, mensaje),
                      error = CASE WHEN ? THEN NULL ELSE COALESCE(?, error) END, fec_modif = ?
               WHERE cod_analisis = ?""",
            estado.clave, fase?.clave, mensaje, limpiarError, error, Instant.now().toString(), codigo,
        )
    }

    fun progreso(codigo: String, fase: Fase, mensaje: String, hechos: Int? = null, total: Int? = null) {
        jdbc.update(
            "UPDATE analisis SET fase = ?, mensaje = ?, hechos = COALESCE(?, hechos), total = COALESCE(?, total), fec_modif = ? WHERE cod_analisis = ?",
            fase.clave, mensaje, hechos, total, Instant.now().toString(), codigo,
        )
    }

    fun pendiente(codigo: String, p: Pendiente?) {
        jdbc.update(
            "UPDATE analisis SET pendiente_json = ?, fec_modif = ? WHERE cod_analisis = ?",
            p?.let { json.writeValueAsString(it) }, Instant.now().toString(), codigo,
        )
    }

    /**
     * Se lee como mapa sin tipar y se arma a mano: los anuncios traen muchos null
     * legitimos (cta_texto, page_id...) y Jackson rechaza un null dentro de un
     * Map<String, Any?> de un data class de Kotlin.
     */
    @Suppress("UNCHECKED_CAST")
    fun avance(codigo: String): Avance {
        val texto = jdbc.query("SELECT avance_json FROM analisis WHERE cod_analisis = ?", { rs, _ -> rs.getString(1) }, codigo)
            .firstOrNull() ?: return Avance()
        val m = json.readValue(texto, Map::class.java) as Map<String, Any?>
        return Avance(
            brutos = m["brutos"] as? List<Json> ?: emptyList(),
            buscado = m["buscado"] == true,
            paginas = m["paginas"] as? Map<String, String> ?: emptyMap(),
            anuncios = m["anuncios"] as? List<Json> ?: emptyList(),
            identificados = m["identificados"] == true,
            identificadas = m["identificadas"] as? List<Json> ?: emptyList(),
            sinAnuncios = m["sinAnuncios"] as? List<String> ?: emptyList(),
            clasificadas = m["clasificadas"] as? Map<String, Json> ?: emptyMap(),
            territorios = m["territorios"] as? List<Json>,
        )
    }

    fun guardarAvance(codigo: String, a: Avance) {
        jdbc.update(
            "UPDATE analisis SET avance_json = ?, fec_modif = ? WHERE cod_analisis = ?",
            json.writeValueAsString(a), Instant.now().toString(), codigo,
        )
    }

    fun terminar(codigo: String, codInforme: String) {
        jdbc.update(
            "UPDATE analisis SET estado = 'terminado', cod_informe = ?, mensaje = 'Informe listo', error = NULL, pendiente_json = NULL, fec_modif = ? WHERE cod_analisis = ?",
            codInforme, Instant.now().toString(), codigo,
        )
    }

    fun borrar(codigo: String) {
        jdbc.update("UPDATE analisis SET estado_reg = 0, fec_modif = ? WHERE cod_analisis = ?", Instant.now().toString(), codigo)
    }
}

@Repository
class RepositorioInformes(private val jdbc: JdbcTemplate, private val json: ObjectMapper) {

    @Suppress("UNCHECKED_CAST")
    private fun mapa(texto: String?): Json? = texto?.let { json.readValue(it, Map::class.java) as Json }

    private val fila = { rs: ResultSet, _: Int ->
        InformeFila(
            codigo = rs.getString("cod_informe"),
            marca = rs.getString("marca"),
            anuncios = rs.getInt("anuncios"),
            anunciantes = rs.getInt("anunciantes"),
            portada = mapa(rs.getString("portada_json")),
            esEjemplo = rs.getInt("es_ejemplo") == 1,
            archivado = rs.getInt("archivado") == 1,
            creado = Instant.parse(rs.getString("fec_creacion")),
        )
    }

    fun guardar(codAnalisis: String?, marca: String, datos: Json, portada: Json?, esEjemplo: Boolean): String {
        val ahora = Instant.now().toString()
        val n = (jdbc.queryForObject("SELECT COALESCE(MAX(id_informe), 0) + 1 FROM informe", Int::class.java) ?: 1)
        val codigo = "I%04d".format(n)
        val meta = datos["meta"] as? Map<*, *>
        jdbc.update(
            """INSERT INTO informe (cod_informe, cod_analisis, marca, anuncios, anunciantes, portada_json, datos_json, es_ejemplo, fec_creacion, fec_modif)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            codigo, codAnalisis, marca, (meta?.get("anuncios") as? Number)?.toInt() ?: 0,
            (meta?.get("anunciantes") as? Number)?.toInt() ?: 0,
            portada?.let { json.writeValueAsString(it) }, json.writeValueAsString(datos),
            if (esEjemplo) 1 else 0, ahora, ahora,
        )
        return codigo
    }

    fun todos(incluirArchivados: Boolean): List<InformeFila> = jdbc.query(
        """SELECT cod_informe, marca, anuncios, anunciantes, portada_json, es_ejemplo, archivado, fec_creacion
           FROM informe WHERE estado_reg = 1 ${if (incluirArchivados) "" else "AND archivado = 0"} ORDER BY id_informe DESC""",
        fila,
    )

    fun fila(codigo: String): InformeFila = jdbc.query(
        """SELECT cod_informe, marca, anuncios, anunciantes, portada_json, es_ejemplo, archivado, fec_creacion
           FROM informe WHERE cod_informe = ? AND estado_reg = 1""",
        fila, codigo,
    ).firstOrNull() ?: throw NoEncontrado("No existe el informe $codigo.")

    fun datos(codigo: String): Json =
        jdbc.query("SELECT datos_json FROM informe WHERE cod_informe = ? AND estado_reg = 1", { rs, _ -> rs.getString(1) }, codigo)
            .firstOrNull()?.let { mapa(it) } ?: throw NoEncontrado("No existe el informe $codigo.")

    fun archivar(codigo: String, archivado: Boolean) {
        fila(codigo)
        jdbc.update("UPDATE informe SET archivado = ?, fec_modif = ? WHERE cod_informe = ?", if (archivado) 1 else 0, Instant.now().toString(), codigo)
    }

    fun borrar(codigo: String) {
        fila(codigo)
        jdbc.update("UPDATE informe SET estado_reg = 0, fec_modif = ? WHERE cod_informe = ?", Instant.now().toString(), codigo)
    }

    // Miniaturas de anuncios (las de Meta caducan)

    fun guardarMiniatura(adId: String, datos: ByteArray, mime: String) {
        jdbc.update(
            "INSERT OR REPLACE INTO miniatura_anuncio (ad_id, datos, mime, fec_creacion) VALUES (?, ?, ?, ?)",
            adId, datos, mime, Instant.now().toString(),
        )
    }

    fun miniatura(adId: String): Pair<ByteArray, String>? =
        jdbc.query("SELECT datos, mime FROM miniatura_anuncio WHERE ad_id = ?", { rs, _ -> rs.getBytes(1) to rs.getString(2) }, adId).firstOrNull()

    /** De estos anuncios, los que ya tienen su miniatura guardada. */
    fun conMiniatura(adIds: Collection<String>): Set<String> = adIds.distinct().chunked(500).flatMap { lote ->
        jdbc.query(
            "SELECT ad_id FROM miniatura_anuncio WHERE ad_id IN (${lote.joinToString(",") { "?" }})",
            { rs, _ -> rs.getString(1) }, *lote.toTypedArray(),
        )
    }.toSet()
}

@Repository
class RepositorioConsumo(private val jdbc: JdbcTemplate) {

    fun registrar(codAnalisis: String, operacion: String, uso: Map<*, *>) {
        jdbc.update(
            """INSERT INTO consumo_ia (cod_analisis, operacion, modelo, tokens_entrada, tokens_salida, costo_usd, fec_creacion)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            codAnalisis, operacion, uso["modelo"]?.toString() ?: "?",
            (uso["tokens_entrada"] as? Number)?.toInt() ?: 0, (uso["tokens_salida"] as? Number)?.toInt() ?: 0,
            (uso["costo_usd"] as? Number)?.toDouble() ?: 0.0, Instant.now().toString(),
        )
    }

    fun costo(codAnalisis: String): Double =
        jdbc.queryForObject("SELECT COALESCE(SUM(costo_usd), 0) FROM consumo_ia WHERE cod_analisis = ?", Double::class.java, codAnalisis) ?: 0.0

    fun llamadas(codAnalisis: String): Int =
        jdbc.queryForObject("SELECT COUNT(*) FROM consumo_ia WHERE cod_analisis = ?", Int::class.java, codAnalisis) ?: 0

    fun costoMes(): Double = jdbc.queryForObject(
        "SELECT COALESCE(SUM(costo_usd), 0) FROM consumo_ia WHERE fec_creacion >= ?", Double::class.java,
        Instant.now().toString().substring(0, 7),
    ) ?: 0.0
}

@Repository
class RepositorioAjustes(private val jdbc: JdbcTemplate) {

    fun leer(codigo: String): String? =
        jdbc.query("SELECT ajuste_valor FROM ajuste WHERE cod_ajuste = ?", { rs, _ -> rs.getString(1) }, codigo).firstOrNull()

    fun guardar(codigo: String, valor: String) {
        jdbc.update(
            """INSERT INTO ajuste (cod_ajuste, ajuste_valor, fec_modif) VALUES (?, ?, ?)
               ON CONFLICT (cod_ajuste) DO UPDATE SET ajuste_valor = excluded.ajuste_valor, fec_modif = excluded.fec_modif""",
            codigo, valor, Instant.now().toString(),
        )
    }
}
