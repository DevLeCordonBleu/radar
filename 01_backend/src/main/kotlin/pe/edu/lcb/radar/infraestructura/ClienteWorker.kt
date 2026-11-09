package pe.edu.lcb.radar.infraestructura

import org.springframework.http.client.SimpleClientHttpRequestFactory
import org.springframework.stereotype.Component
import org.springframework.web.client.ResourceAccessException
import org.springframework.web.client.RestClient
import pe.edu.lcb.radar.config.Ajustes
import pe.edu.lcb.radar.dominio.Json
import tools.jackson.databind.ObjectMapper
import java.time.Duration

/**
 * Fallo de un paso en el worker, con un mensaje apto para el panel.
 * `cuota` = Gemini agoto su cuota: el analisis se pausa en vez de darse por fallado.
 */
class ErrorDelWorker(mensaje: String, val estado: Int = 0) : RuntimeException(mensaje) {
    val cuota: Boolean get() = estado == 429
    val loteGrande: Boolean get() = estado == 413
}

/**
 * Llamadas al worker.
 *
 * Espera larga a proposito: un lote de 10 anuncios con video puede tardar un
 * par de minutos en Gemini. El backend llama siempre desde su cola de analisis,
 * nunca desde el hilo de una peticion del navegador (salvo las consultas
 * rapidas: salud, comprobar claves, informe de ejemplo).
 */
@Component
class ClienteWorker(private val ajustes: Ajustes, private val json: ObjectMapper) {

    private val http = RestClient.builder()
        .baseUrl(ajustes.worker)
        .requestFactory(
            SimpleClientHttpRequestFactory().apply {
                setConnectTimeout(Duration.ofSeconds(5))
                setReadTimeout(Duration.ofMinutes(12))
            },
        )
        .build()

    private fun leer(texto: String?): Any? = if (texto.isNullOrBlank()) null else json.readValue(texto, Any::class.java)

    private fun llamar(metodo: String, ruta: String, cuerpo: Any?): Any? = try {
        val peticion = if (metodo == "GET") http.get().uri(ruta) else http.post().uri(ruta).body(cuerpo ?: emptyMap<String, Any>())
        peticion.exchange { _, resp ->
            val texto = resp.bodyTo(String::class.java)
            if (resp.statusCode.isError) {
                val detalle = (leer(texto) as? Map<*, *>)?.get("detail")
                throw ErrorDelWorker(
                    when (detalle) {
                        is String -> detalle
                        null -> "El worker respondio ${resp.statusCode.value()}."
                        else -> "Datos rechazados por el worker: $detalle"
                    },
                    resp.statusCode.value(),
                )
            }
            leer(texto)
        }
    } catch (e: ResourceAccessException) {
        throw ErrorDelWorker("El worker no responde en ${ajustes.worker}. Arrancalo con iniciar.bat.")
    }

    @Suppress("UNCHECKED_CAST")
    fun post(ruta: String, cuerpo: Any): Json = (llamar("POST", ruta, cuerpo) as? Json).orEmpty()

    @Suppress("UNCHECKED_CAST")
    fun get(ruta: String): Json = (llamar("GET", ruta, null) as? Json).orEmpty()

    fun salud(): Json? = try {
        get("/salud")
    } catch (e: ErrorDelWorker) {
        null
    }
}
