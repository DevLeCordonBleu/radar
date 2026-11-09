package pe.edu.lcb.radar.api

import jakarta.servlet.http.HttpServletRequest
import org.springframework.http.HttpStatus
import org.springframework.web.bind.annotation.DeleteMapping
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PathVariable
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.PutMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.ResponseStatus
import org.springframework.web.bind.annotation.RestController
import pe.edu.lcb.radar.aplicacion.ServicioAuth
import pe.edu.lcb.radar.aplicacion.ServicioKeywords
import pe.edu.lcb.radar.infraestructura.BusquedaFila
import pe.edu.lcb.radar.infraestructura.ClienteWorker
import pe.edu.lcb.radar.infraestructura.ListaFila

/** Respuesta de una busqueda: el resultado completo mas de donde viene (cache o Google). */
data class BusquedaDto(val busqueda: BusquedaFila, val desdeCache: Boolean, val resultado: Map<String, Any?>)

/**
 * KeyWords Explorer. Los cuerpos se reciben como mapas sin tipar a proposito: las filas
 * de keywords traen `null` legitimos (sin volumen, sin CPC) que Jackson rechaza en
 * un data class de Kotlin (ver CLAUDE.md).
 */
@RestController
@RequestMapping("/api/keywords")
class KeywordsController(
    private val servicio: ServicioKeywords,
    private val worker: ClienteWorker,
    private val auth: ServicioAuth,
) {

    /** Si Google Ads esta conectado (y que falta), mas los paises e idiomas disponibles. */
    @GetMapping("/estado")
    fun estado() = worker.get("/keywords/estado")

    /** Prueba la conexion con Google Ads. Solo administradores: usa las credenciales del equipo. */
    @PostMapping("/comprobar")
    fun comprobar(request: HttpServletRequest): Map<String, Any?> {
        auth.exigirAdmin(request.sesion().usuario)
        return worker.post("/keywords/comprobar", emptyMap<String, Any>())
    }

    @PostMapping("/explorar")
    fun explorar(request: HttpServletRequest, @RequestBody cuerpo: Map<*, *>): BusquedaDto =
        servicio.explorar(request.sesion().usuario, cuerpo).let { BusquedaDto(it.busqueda, it.desdeCache, it.resultado) }

    @GetMapping("/busquedas")
    fun busquedas(): List<BusquedaFila> = servicio.busquedas()

    @GetMapping("/busquedas/{codigo}")
    fun busqueda(@PathVariable codigo: String): BusquedaDto = servicio.busqueda(codigo).let { BusquedaDto(it.busqueda, it.desdeCache, it.resultado) }

    @DeleteMapping("/busquedas/{codigo}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    fun borrarBusqueda(@PathVariable codigo: String) = servicio.borrarBusqueda(codigo)

    @PostMapping("/resumen")
    fun resumen(@RequestBody cuerpo: Map<*, *>) = servicio.resumen(cuerpo)

    // ── Listas ──

    @GetMapping("/listas")
    fun listas(): List<ListaFila> = servicio.listas()

    @PostMapping("/listas")
    @ResponseStatus(HttpStatus.CREATED)
    fun crearLista(request: HttpServletRequest, @RequestBody cuerpo: Map<*, *>): ListaFila = servicio.crearLista(request.sesion().usuario, cuerpo)

    @GetMapping("/listas/{codigo}")
    fun lista(@PathVariable codigo: String): Map<String, Any?> = servicio.lista(codigo).let { mapOf("lista" to it.first, "items" to it.second) }

    @PutMapping("/listas/{codigo}")
    fun actualizarLista(@PathVariable codigo: String, @RequestBody cuerpo: Map<*, *>): ListaFila = servicio.actualizarLista(codigo, cuerpo)

    @DeleteMapping("/listas/{codigo}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    fun borrarLista(@PathVariable codigo: String) = servicio.borrarLista(codigo)

    @PostMapping("/listas/{codigo}/items")
    fun agregar(@PathVariable codigo: String, @RequestBody cuerpo: Map<*, *>) = servicio.agregar(codigo, cuerpo)

    @PostMapping("/listas/{codigo}/quitar")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    fun quitar(@PathVariable codigo: String, @RequestBody cuerpo: Map<*, *>) = servicio.quitar(codigo, cuerpo)

    @PutMapping("/listas/{codigo}/nota")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    fun nota(@PathVariable codigo: String, @RequestBody cuerpo: Map<*, *>) = servicio.nota(codigo, cuerpo)

    @PostMapping("/listas/{codigo}/actualizar")
    fun actualizar(@PathVariable codigo: String): Map<String, Int> = mapOf("actualizadas" to servicio.actualizarMetricas(codigo))
}
