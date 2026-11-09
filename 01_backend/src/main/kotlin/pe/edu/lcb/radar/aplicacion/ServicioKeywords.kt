package pe.edu.lcb.radar.aplicacion

import org.springframework.stereotype.Service
import pe.edu.lcb.radar.dominio.Json
import pe.edu.lcb.radar.dominio.ReglaIncumplida
import pe.edu.lcb.radar.dominio.Usuario
import pe.edu.lcb.radar.infraestructura.BusquedaFila
import pe.edu.lcb.radar.infraestructura.ClienteWorker
import pe.edu.lcb.radar.infraestructura.ListaFila
import pe.edu.lcb.radar.infraestructura.RepositorioKeywords
import java.security.MessageDigest
import java.time.Duration
import java.time.Instant

/**
 * KeyWords Explorer: busquedas con cache, historial y listas de keywords.
 *
 * Los datos los pone el worker (Google Ads Keyword Planner, o los de demostracion);
 * aqui solo se valida, se guarda y se reutiliza. Un resultado de hasta 7 dias se
 * sirve del historial: los volumenes de Keyword Planner son mensuales y repetir la
 * consulta solo gastaria cuota de Google.
 */
@Service
class ServicioKeywords(private val repo: RepositorioKeywords, private val worker: ClienteWorker) {

    data class Busqueda(val busqueda: BusquedaFila, val resultado: Json, val desdeCache: Boolean)
    data class Parametros(
        val semillas: List<String>, val url: String?, val pais: String, val idioma: String,
        val maximo: Int, val sugerencias: Boolean, val demo: Boolean, val refrescar: Boolean,
    )

    // ── Busquedas ─────────────────────────────────────────────────────────

    fun parametros(c: Map<*, *>): Parametros {
        val semillas = (c["semillas"] as? List<*>).orEmpty().mapNotNull { it?.toString()?.trim()?.takeIf { s -> s.isNotEmpty() } }
            .distinctBy { it.lowercase() }
        val url = (c["url"] as? String)?.trim()?.takeIf { it.isNotEmpty() }
        if (semillas.isEmpty() && url == null) throw ReglaIncumplida("Escribe al menos una palabra o una URL.")
        if (semillas.size > 20) throw ReglaIncumplida("Máximo 20 palabras por búsqueda.")
        if (semillas.any { it.length > 80 }) throw ReglaIncumplida("Una palabra no puede pasar de 80 caracteres.")
        if (url != null && (!Regex("^https?://\\S+$").matches(url) || url.length > 300)) throw ReglaIncumplida("La URL tiene que empezar por http:// o https://.")
        val pais = (c["pais"] as? String ?: "PE").uppercase()
        val idioma = (c["idioma"] as? String ?: "es").lowercase()
        if (!Regex("[A-Z]{2}").matches(pais) || !Regex("[a-z]{2}").matches(idioma)) throw ReglaIncumplida("País e idioma van como código de dos letras (PE, es).")
        val maximo = (c["maximo"] as? Number)?.toInt() ?: 1000
        if (maximo !in 10..2000) throw ReglaIncumplida("El máximo de ideas va de 10 a 2000.")
        return Parametros(semillas, url, pais, idioma, maximo, c["sugerencias"] as? Boolean ?: true, c["demo"] as? Boolean ?: false, c["refrescar"] as? Boolean ?: false)
    }

    private fun clave(p: Parametros): String {
        val texto = "v1|${p.demo}|${p.pais}|${p.idioma}|${p.maximo}|${p.sugerencias}|${p.url.orEmpty().lowercase()}|${p.semillas.map { it.lowercase() }.sorted().joinToString(",")}"
        return MessageDigest.getInstance("SHA-256").digest(texto.toByteArray()).joinToString("") { "%02x".format(it) }
    }

    fun explorar(actor: Usuario, cuerpo: Map<*, *>): Busqueda {
        val p = parametros(cuerpo)
        val k = clave(p)
        if (!p.refrescar) {
            repo.busquedaPorClave(k)?.takeIf { Duration.between(it.fecha, Instant.now()) < VIGENCIA }?.let { fila ->
                return Busqueda(fila, repo.resultado(fila.codigo).second, desdeCache = true)
            }
        }
        val resultado = worker.post(
            "/keywords/explorar",
            mapOf("semillas" to p.semillas, "url" to p.url, "pais" to p.pais, "idioma" to p.idioma, "maximo" to p.maximo, "sugerencias" to p.sugerencias, "demo" to p.demo),
        )
        val fila = repo.guardarBusqueda(k, p.semillas, p.url, p.pais, p.idioma, p.demo, resultado, actor.codigo)
        return Busqueda(fila, resultado, desdeCache = false)
    }

    fun busquedas(): List<BusquedaFila> = repo.busquedas(40)

    fun busqueda(codigo: String): Busqueda = repo.resultado(codigo).let { Busqueda(it.first, it.second, desdeCache = true) }

    fun borrarBusqueda(codigo: String) = repo.borrarBusqueda(codigo)

    /** Ficha de una keyword (y su volumen por pais si se pide). No se guarda: es una consulta suelta. */
    fun resumen(cuerpo: Map<*, *>): Json {
        val keyword = (cuerpo["keyword"] as? String)?.trim().orEmpty()
        if (keyword.isEmpty() || keyword.length > 80) throw ReglaIncumplida("Escribe una keyword de hasta 80 caracteres.")
        return worker.post(
            "/keywords/resumen",
            mapOf("keyword" to keyword, "pais" to (cuerpo["pais"] as? String ?: "PE").uppercase(), "idioma" to (cuerpo["idioma"] as? String ?: "es").lowercase(),
                "por_pais" to (cuerpo["porPais"] as? Boolean ?: false), "demo" to (cuerpo["demo"] as? Boolean ?: false)),
        )
    }

    // ── Listas ────────────────────────────────────────────────────────────

    fun listas(): List<ListaFila> = repo.listas()

    fun crearLista(actor: Usuario, cuerpo: Map<*, *>): ListaFila {
        val nombre = (cuerpo["nombre"] as? String)?.trim().orEmpty()
        if (nombre.isEmpty() || nombre.length > 80) throw ReglaIncumplida("El nombre de la lista va de 1 a 80 caracteres.")
        val pais = (cuerpo["pais"] as? String ?: "PE").uppercase()
        val idioma = (cuerpo["idioma"] as? String ?: "es").lowercase()
        if (!Regex("[A-Z]{2}").matches(pais) || !Regex("[a-z]{2}").matches(idioma)) throw ReglaIncumplida("País e idioma van como código de dos letras.")
        val codigo = repo.crearLista(nombre, (cuerpo["descripcion"] as? String)?.trim()?.take(500).orEmpty(), pais, idioma, cuerpo["demo"] as? Boolean ?: false, actor.codigo)
        return repo.lista(codigo)
    }

    fun lista(codigo: String): Pair<ListaFila, List<Json>> =
        repo.lista(codigo) to repo.items(codigo).map { (fila, nota) -> fila + ("nota" to nota) }

    fun actualizarLista(codigo: String, cuerpo: Map<*, *>): ListaFila {
        val nombre = (cuerpo["nombre"] as? String)?.trim().orEmpty()
        if (nombre.isEmpty() || nombre.length > 80) throw ReglaIncumplida("El nombre de la lista va de 1 a 80 caracteres.")
        repo.actualizarLista(codigo, nombre, (cuerpo["descripcion"] as? String)?.trim()?.take(500).orEmpty())
        return repo.lista(codigo)
    }

    fun borrarLista(codigo: String) = repo.borrarLista(codigo)

    /** Las filas se guardan tal como llegaron del explorador (con sus metricas de ese momento). */
    @Suppress("UNCHECKED_CAST")
    fun agregar(codigo: String, cuerpo: Map<*, *>): Map<String, Int> {
        val lista = repo.lista(codigo)
        val demo = cuerpo["demo"] as? Boolean ?: false
        if (demo != lista.demo) {
            throw ReglaIncumplida(if (lista.demo) "Esta lista es de demostración: no se pueden mezclar datos reales." else "Esta lista es de datos reales: no se pueden mezclar datos de demostración.")
        }
        val filas = (cuerpo["items"] as? List<*>).orEmpty().mapNotNull { it as? Map<String, Any?> }
        if (filas.isEmpty()) throw ReglaIncumplida("No hay keywords que añadir.")
        if (filas.size > 2000) throw ReglaIncumplida("Máximo 2000 keywords por vez.")
        val nuevas = repo.agregar(codigo, filas)
        return mapOf("agregadas" to nuevas, "repetidas" to filas.size - nuevas)
    }

    fun quitar(codigo: String, cuerpo: Map<*, *>) {
        val ks = (cuerpo["keywords"] as? List<*>).orEmpty().mapNotNull { it?.toString() }
        repo.quitar(codigo, ks)
    }

    fun nota(codigo: String, cuerpo: Map<*, *>) {
        val k = (cuerpo["keyword"] as? String).orEmpty()
        val nota = (cuerpo["nota"] as? String)?.trim()?.take(500).orEmpty()
        if (k.isEmpty()) throw ReglaIncumplida("Falta la keyword.")
        repo.nota(codigo, k, nota)
    }

    /** Vuelve a pedir las metricas de todas las keywords de la lista. Las notas se conservan. */
    @Suppress("UNCHECKED_CAST")
    fun actualizarMetricas(codigo: String): Int {
        val lista = repo.lista(codigo)
        val keywords = repo.items(codigo).mapNotNull { it.first["keyword"] as? String }
        if (keywords.isEmpty()) return 0
        if (keywords.size > 500) throw ReglaIncumplida("Para actualizar, la lista no puede pasar de 500 keywords. Divídela en dos.")
        val r = worker.post("/keywords/metricas", mapOf("keywords" to keywords, "pais" to lista.pais, "idioma" to lista.idioma, "demo" to lista.demo))
        val filas = r["filas"] as? List<Map<String, Any?>> ?: emptyList()
        filas.forEach { f -> (f["keyword"] as? String)?.let { repo.actualizarFila(codigo, it, f) } }
        return filas.size
    }

    private companion object {
        val VIGENCIA: Duration = Duration.ofDays(7)
    }
}
