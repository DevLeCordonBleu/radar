package pe.edu.lcb.radar.api

import jakarta.servlet.http.HttpServletRequest
import org.springframework.http.CacheControl
import org.springframework.http.HttpStatus
import org.springframework.http.MediaType
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.DeleteMapping
import org.springframework.web.bind.annotation.ExceptionHandler
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PathVariable
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.PutMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RequestParam
import org.springframework.web.bind.annotation.ResponseStatus
import org.springframework.web.bind.annotation.RestController
import org.springframework.web.bind.annotation.RestControllerAdvice
import org.springframework.web.multipart.MaxUploadSizeExceededException
import pe.edu.lcb.radar.aplicacion.ServicioAnalisis
import pe.edu.lcb.radar.aplicacion.ServicioAnalisisSemanal
import pe.edu.lcb.radar.aplicacion.ServicioInformes
import pe.edu.lcb.radar.aplicacion.ServicioPreferencias
import pe.edu.lcb.radar.dominio.Json
import pe.edu.lcb.radar.dominio.NoAutenticado
import pe.edu.lcb.radar.dominio.NoEncontrado
import pe.edu.lcb.radar.dominio.Prohibido
import pe.edu.lcb.radar.dominio.Peticion
import pe.edu.lcb.radar.dominio.ReglaIncumplida
import pe.edu.lcb.radar.infraestructura.ClienteWorker
import pe.edu.lcb.radar.infraestructura.ErrorDelWorker
import pe.edu.lcb.radar.infraestructura.RepositorioConsumo
import java.util.concurrent.TimeUnit

/** Analisis: crear, seguir su avance, pausar/continuar. */
@RestController
@RequestMapping("/api/analisis")
class AnalisisController(private val servicio: ServicioAnalisis, private val semanal: ServicioAnalisisSemanal) {

    @GetMapping
    fun listar() = servicio.listar().map { it.dto() }

    /** Informe semanal: el mismo analisis cada semana, el dia y la hora elegidos (solo admin lo cambia). */
    @GetMapping("/semanal")
    fun semanal() = semanal.estado().dto()

    @PutMapping("/semanal")
    fun programarSemanal(request: HttpServletRequest, @RequestBody p: PeticionSemanal) =
        semanal.programar(request.sesion().usuario, p.activo, p.dia, p.hora, p.peticion).dto()

    @PostMapping("/semanal/ejecutar")
    @ResponseStatus(HttpStatus.CREATED)
    fun ejecutarSemanal(request: HttpServletRequest) = semanal.ejecutar(request.sesion().usuario).dto()

    @GetMapping("/{codigo}")
    fun obtener(@PathVariable codigo: String) = servicio.obtener(codigo).dto()

    /** Cuanto costara y cuanto tardara, antes de lanzarlo. */
    /** Paginas de Facebook que coinciden con lo que se escribe en «Competidores». */
    @PostMapping("/paginas")
    fun paginas(@RequestBody cuerpo: Map<*, *>) =
        servicio.sugerirPaginas(cuerpo["texto"]?.toString().orEmpty(), cuerpo["pais"]?.toString() ?: "PE")

    @PostMapping("/paginas/preparar")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    fun prepararPaginas(@RequestBody(required = false) cuerpo: Map<*, *>?) = servicio.prepararSugerencias(cuerpo?.get("pais")?.toString() ?: "PE")

    @PostMapping("/estimar")
    fun estimar(@RequestBody p: Peticion) = servicio.estimar(p)

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    fun crear(@RequestBody p: Peticion) = servicio.crear(p).dto()

    @PostMapping("/{codigo}/continuar")
    fun continuar(@PathVariable codigo: String) = servicio.continuar(codigo).dto()

    @PostMapping("/{codigo}/terminar")
    fun terminar(@PathVariable codigo: String) = servicio.terminarYa(codigo).dto()

    @PostMapping("/{codigo}/pagina")
    fun elegirPagina(@PathVariable codigo: String, @RequestBody e: PeticionEleccion) =
        servicio.elegirPagina(codigo, e.competidor, e.pageIds ?: listOfNotNull(e.pageId)).dto()

    @PostMapping("/{codigo}/cancelar")
    fun cancelar(@PathVariable codigo: String) = servicio.cancelar(codigo).dto()

    @DeleteMapping("/{codigo}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    fun borrar(@PathVariable codigo: String) = servicio.borrar(codigo)
}

/** Informes terminados. */
@RestController
@RequestMapping("/api/informes")
class InformesController(private val servicio: ServicioInformes) {

    @GetMapping
    fun listar(@RequestParam(defaultValue = "false") archivados: Boolean) = servicio.listar(archivados)

    @GetMapping("/{codigo}")
    fun obtener(@PathVariable codigo: String) = mapOf("resumen" to servicio.resumen(codigo), "datos" to servicio.obtener(codigo))

    /** La miniatura guardada de un anuncio: no cambia, el navegador la guarda en caché. */
    @GetMapping("/miniaturas/{adId}")
    fun miniatura(@PathVariable adId: String): ResponseEntity<ByteArray> {
        val (datos, mime) = servicio.miniatura(adId)
        return ResponseEntity.ok().contentType(MediaType.parseMediaType(mime))
            .cacheControl(CacheControl.maxAge(30, TimeUnit.DAYS).cachePrivate()).body(datos)
    }

    @PostMapping("/ejemplo")
    @ResponseStatus(HttpStatus.CREATED)
    fun ejemplo() = servicio.crearEjemplo()

    @PutMapping("/{codigo}/archivo")
    fun archivar(@PathVariable codigo: String, @RequestBody p: PeticionArchivar) = servicio.archivar(codigo, p.archivado)

    @DeleteMapping("/{codigo}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    fun borrar(@PathVariable codigo: String) = servicio.borrar(codigo)
}

/** Lo que no es de un analisis ni de un informe: mercado guardado, sistema, claves. */
@RestController
@RequestMapping("/api")
class SistemaController(
    private val preferencias: ServicioPreferencias,
    private val worker: ClienteWorker,
    private val consumo: RepositorioConsumo,
    private val auth: pe.edu.lcb.radar.aplicacion.ServicioAuth,
) {

    @GetMapping("/mercado")
    fun mercado() = preferencias.leer()

    @PutMapping("/mercado")
    fun guardarMercado(@RequestBody p: Peticion) = preferencias.guardar(p)

    /** Que esta configurado en el worker (Gemini, Apify) y cuanto se ha gastado este mes. */
    @GetMapping("/sistema")
    fun sistema() = SistemaDto(worker.salud(), consumo.costoMes())

    /** Valida las claves contra Google y Apify (tarda unos segundos; no gasta cuota de analisis). */
    @PostMapping("/sistema/comprobar")
    fun comprobar(request: jakarta.servlet.http.HttpServletRequest): Json {
        auth.exigirAdmin(request.sesion().usuario)
        return worker.post("/claves/comprobar", emptyMap<String, Any>())
    }

    /** Listas cerradas con sus etiquetas, para que el panel no las duplique. */
    @GetMapping("/taxonomia")
    fun taxonomia() = worker.get("/taxonomia")
}

/** Errores con mensaje para el panel: { "error": "..." }. */
@RestControllerAdvice
class ManejadorErrores {

    @ExceptionHandler(ReglaIncumplida::class)
    fun regla(e: ReglaIncumplida) = ResponseEntity.status(HttpStatus.CONFLICT).body(RespuestaError(e.message ?: "Accion no permitida."))

    @ExceptionHandler(NoEncontrado::class)
    fun noEncontrado(e: NoEncontrado) = ResponseEntity.status(HttpStatus.NOT_FOUND).body(RespuestaError(e.message ?: "No encontrado."))

    @ExceptionHandler(NoAutenticado::class)
    fun sinSesion(e: NoAutenticado) = ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(RespuestaError(e.message ?: "Inicia sesión."))

    @ExceptionHandler(Prohibido::class)
    fun prohibido(e: Prohibido) = ResponseEntity.status(HttpStatus.FORBIDDEN).body(RespuestaError(e.message ?: "No permitido."))

    @ExceptionHandler(ErrorDelWorker::class)
    fun worker(e: ErrorDelWorker) = ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(RespuestaError(e.message ?: "Fallo del worker."))

    @ExceptionHandler(MaxUploadSizeExceededException::class)
    fun archivoGrande(e: MaxUploadSizeExceededException) =
        ResponseEntity.status(HttpStatus.CONFLICT).body(RespuestaError("El archivo pasa de 100 MB."))
}
