package pe.edu.lcb.radar.infraestructura

import org.springframework.jdbc.core.JdbcTemplate
import org.springframework.stereotype.Repository
import pe.edu.lcb.radar.dominio.Json
import pe.edu.lcb.radar.dominio.NoEncontrado
import tools.jackson.databind.ObjectMapper
import java.time.Instant

/** Resumen de una busqueda guardada (sin sus miles de filas). */
data class BusquedaFila(
    val codigo: String,
    val semillas: List<String>,
    val url: String?,
    val pais: String,
    val idioma: String,
    val demo: Boolean,
    val totalKeywords: Int,
    val volumenTotal: Long,
    val fecha: Instant,
)

data class ListaFila(
    val codigo: String,
    val nombre: String,
    val descripcion: String,
    val pais: String,
    val idioma: String,
    val demo: Boolean,
    val keywords: Int,
    val volumenTotal: Long,
    val modificado: Instant,
)

/** Persistencia de busquedas (historial + cache) y listas de KeyWords Explorer. */
@Repository
class RepositorioKeywords(private val jdbc: JdbcTemplate, private val json: ObjectMapper) {

    @Suppress("UNCHECKED_CAST")
    private fun mapa(texto: String): Json = json.readValue(texto, Map::class.java) as Json

    @Suppress("UNCHECKED_CAST")
    private fun textos(texto: String): List<String> = json.readValue(texto, List::class.java) as List<String>

    // ── Busquedas ──

    private val busqueda = { rs: java.sql.ResultSet, _: Int ->
        BusquedaFila(
            rs.getString("cod_kw_busqueda"), textos(rs.getString("semillas_json")), rs.getString("url"), rs.getString("pais"),
            rs.getString("idioma"), rs.getInt("demo") == 1, rs.getInt("total_keywords"), rs.getLong("volumen_total"),
            Instant.parse(rs.getString("fec_modif")),
        )
    }

    private val columnasBusqueda = "cod_kw_busqueda, semillas_json, url, pais, idioma, demo, total_keywords, volumen_total, fec_modif"

    fun busquedaPorClave(clave: String): BusquedaFila? =
        jdbc.query("SELECT $columnasBusqueda FROM kw_busqueda WHERE clave = ? AND estado_reg = 1 ORDER BY id_kw_busqueda DESC LIMIT 1", busqueda, clave).firstOrNull()

    fun guardarBusqueda(clave: String, semillas: List<String>, url: String?, pais: String, idioma: String, demo: Boolean, resultado: Json, autor: String?): BusquedaFila {
        val totales = (resultado["totales"] as? Map<*, *>)
        val total = (totales?.get("keywords") as? Number)?.toInt() ?: 0
        val volumen = (totales?.get("volumen") as? Number)?.toLong() ?: 0L
        val ahora = Instant.now().toString()
        val existente = jdbc.query("SELECT cod_kw_busqueda FROM kw_busqueda WHERE clave = ? AND estado_reg = 1 ORDER BY id_kw_busqueda DESC LIMIT 1", { rs, _ -> rs.getString(1) }, clave).firstOrNull()
        val codigo = if (existente != null) {
            jdbc.update(
                "UPDATE kw_busqueda SET resultado_json = ?, total_keywords = ?, volumen_total = ?, fec_modif = ? WHERE cod_kw_busqueda = ?",
                json.writeValueAsString(resultado), total, volumen, ahora, existente,
            )
            existente
        } else {
            val n = (jdbc.queryForObject("SELECT COALESCE(MAX(id_kw_busqueda), 0) + 1 FROM kw_busqueda", Int::class.java) ?: 1)
            val nuevo = "K%04d".format(n)
            jdbc.update(
                """INSERT INTO kw_busqueda (cod_kw_busqueda, clave, semillas_json, url, pais, idioma, demo, total_keywords, volumen_total,
                                            resultado_json, cod_autor, fec_creacion, fec_modif) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                nuevo, clave, json.writeValueAsString(semillas), url, pais, idioma, if (demo) 1 else 0, total, volumen,
                json.writeValueAsString(resultado), autor, ahora, ahora,
            )
            nuevo
        }
        return jdbc.query("SELECT $columnasBusqueda FROM kw_busqueda WHERE cod_kw_busqueda = ?", busqueda, codigo).first()
    }

    fun busquedas(limite: Int): List<BusquedaFila> =
        jdbc.query("SELECT $columnasBusqueda FROM kw_busqueda WHERE estado_reg = 1 ORDER BY fec_modif DESC LIMIT ?", busqueda, limite)

    fun resultado(codigo: String): Pair<BusquedaFila, Json> {
        val fila = jdbc.query("SELECT $columnasBusqueda FROM kw_busqueda WHERE cod_kw_busqueda = ? AND estado_reg = 1", busqueda, codigo).firstOrNull()
            ?: throw NoEncontrado("No existe la búsqueda $codigo.")
        val texto = jdbc.queryForObject("SELECT resultado_json FROM kw_busqueda WHERE cod_kw_busqueda = ?", String::class.java, codigo)!!
        return fila to mapa(texto)
    }

    fun borrarBusqueda(codigo: String) {
        if (jdbc.update("UPDATE kw_busqueda SET estado_reg = 0 WHERE cod_kw_busqueda = ?", codigo) == 0) throw NoEncontrado("No existe la búsqueda $codigo.")
    }

    // ── Listas ──

    private val lista = { rs: java.sql.ResultSet, _: Int ->
        ListaFila(
            rs.getString("cod_kw_lista"), rs.getString("nombre"), rs.getString("descripcion"), rs.getString("pais"), rs.getString("idioma"),
            rs.getInt("demo") == 1, rs.getInt("n"), rs.getLong("vol"), Instant.parse(rs.getString("fec_modif")),
        )
    }

    private val consultaLista = """SELECT l.cod_kw_lista, l.nombre, l.descripcion, l.pais, l.idioma, l.demo, l.fec_modif,
        (SELECT COUNT(*) FROM kw_lista_item i WHERE i.id_kw_lista = l.id_kw_lista) AS n,
        COALESCE((SELECT SUM(COALESCE(json_extract(i.datos_json, '$.volumen'), 0)) FROM kw_lista_item i WHERE i.id_kw_lista = l.id_kw_lista), 0) AS vol
        FROM kw_lista l WHERE l.estado_reg = 1"""

    fun listas(): List<ListaFila> = jdbc.query("$consultaLista ORDER BY l.fec_modif DESC", lista)

    fun lista(codigo: String): ListaFila =
        jdbc.query("$consultaLista AND l.cod_kw_lista = ?", lista, codigo).firstOrNull() ?: throw NoEncontrado("No existe la lista $codigo.")

    fun crearLista(nombre: String, descripcion: String, pais: String, idioma: String, demo: Boolean, autor: String?): String {
        val ahora = Instant.now().toString()
        val n = (jdbc.queryForObject("SELECT COALESCE(MAX(id_kw_lista), 0) + 1 FROM kw_lista", Int::class.java) ?: 1)
        val codigo = "L%04d".format(n)
        jdbc.update(
            "INSERT INTO kw_lista (cod_kw_lista, nombre, descripcion, pais, idioma, demo, cod_autor, fec_creacion, fec_modif) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            codigo, nombre, descripcion, pais, idioma, if (demo) 1 else 0, autor, ahora, ahora,
        )
        return codigo
    }

    fun actualizarLista(codigo: String, nombre: String, descripcion: String) {
        lista(codigo)
        jdbc.update("UPDATE kw_lista SET nombre = ?, descripcion = ?, fec_modif = ? WHERE cod_kw_lista = ?", nombre, descripcion, Instant.now().toString(), codigo)
    }

    fun borrarLista(codigo: String) {
        lista(codigo)
        jdbc.update("DELETE FROM kw_lista_item WHERE id_kw_lista = (SELECT id_kw_lista FROM kw_lista WHERE cod_kw_lista = ?)", codigo)
        jdbc.update("DELETE FROM kw_lista WHERE cod_kw_lista = ?", codigo)
    }

    private fun idLista(codigo: String): Long =
        jdbc.query("SELECT id_kw_lista FROM kw_lista WHERE cod_kw_lista = ? AND estado_reg = 1", { rs, _ -> rs.getLong(1) }, codigo).firstOrNull()
            ?: throw NoEncontrado("No existe la lista $codigo.")

    /** (fila, nota) de cada keyword de la lista, la mas reciente primero. */
    fun items(codigo: String): List<Pair<Json, String>> = jdbc.query(
        "SELECT datos_json, nota FROM kw_lista_item WHERE id_kw_lista = ? ORDER BY id_kw_lista_item DESC",
        { rs, _ -> mapa(rs.getString("datos_json")) to rs.getString("nota") }, idLista(codigo),
    )

    /** Anade las filas que no estan ya (sin distinguir mayusculas). Devuelve cuantas entraron. */
    fun agregar(codigo: String, filas: List<Json>): Int {
        val id = idLista(codigo)
        val ahora = Instant.now().toString()
        var n = 0
        for (f in filas) {
            val k = (f["keyword"] as? String)?.trim().orEmpty()
            if (k.isEmpty()) continue
            n += jdbc.update(
                "INSERT OR IGNORE INTO kw_lista_item (id_kw_lista, keyword, datos_json, fec_creacion, fec_modif) VALUES (?, ?, ?, ?, ?)",
                id, k, json.writeValueAsString(f), ahora, ahora,
            )
        }
        jdbc.update("UPDATE kw_lista SET fec_modif = ? WHERE id_kw_lista = ?", ahora, id)
        return n
    }

    fun quitar(codigo: String, keywords: List<String>) {
        val id = idLista(codigo)
        keywords.forEach { jdbc.update("DELETE FROM kw_lista_item WHERE id_kw_lista = ? AND keyword = ?", id, it) }
        jdbc.update("UPDATE kw_lista SET fec_modif = ? WHERE id_kw_lista = ?", Instant.now().toString(), id)
    }

    fun nota(codigo: String, keyword: String, nota: String) {
        jdbc.update("UPDATE kw_lista_item SET nota = ?, fec_modif = ? WHERE id_kw_lista = ? AND keyword = ?", nota, Instant.now().toString(), idLista(codigo), keyword)
    }

    fun actualizarFila(codigo: String, keyword: String, fila: Json) {
        jdbc.update("UPDATE kw_lista_item SET datos_json = ?, fec_modif = ? WHERE id_kw_lista = ? AND keyword = ?", json.writeValueAsString(fila), Instant.now().toString(), idLista(codigo), keyword)
        jdbc.update("UPDATE kw_lista SET fec_modif = ? WHERE cod_kw_lista = ?", Instant.now().toString(), codigo)
    }
}
