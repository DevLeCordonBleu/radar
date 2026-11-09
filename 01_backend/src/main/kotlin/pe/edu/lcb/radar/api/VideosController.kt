package pe.edu.lcb.radar.api

import jakarta.servlet.http.HttpServletRequest
import org.springframework.core.io.FileSystemResource
import org.springframework.core.io.Resource
import org.springframework.http.CacheControl
import org.springframework.http.ContentDisposition
import org.springframework.http.HttpHeaders
import org.springframework.http.HttpStatus
import org.springframework.http.MediaType
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.DeleteMapping
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PathVariable
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.PutMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RequestParam
import org.springframework.web.bind.annotation.ResponseStatus
import org.springframework.web.bind.annotation.RestController
import pe.edu.lcb.radar.aplicacion.ServicioVideos
import pe.edu.lcb.radar.infraestructura.CambioVideo

data class PeticionVideo(val idea: String = "", val keyword: String? = null, val segundos: Int = 45, val formato: String = "VERTICAL")

data class PeticionAprobarVideo(val aprobado: Boolean = true)

/** Videos cortos: guion por partes, generacion en Google Vids y aprobacion. */
@RestController
@RequestMapping("/api/videos")
class VideosController(private val servicio: ServicioVideos) {

    @GetMapping
    fun listar() = servicio.listar()

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    fun crear(request: HttpServletRequest, @RequestBody p: PeticionVideo) =
        servicio.crear(request.sesion().usuario, p.idea, p.keyword, p.segundos, p.formato)

    @GetMapping("/contexto")
    fun contexto() = servicio.contexto()

    @PutMapping("/contexto")
    fun guardarContexto(request: HttpServletRequest, @RequestBody c: ServicioVideos.ContextoVideo) =
        servicio.guardarContexto(request.sesion().usuario, c)

    @GetMapping("/navegador")
    fun navegador() = servicio.navegador()

    @PostMapping("/navegador/abrir")
    fun abrirNavegador() = servicio.abrirNavegador()

    @GetMapping("/{codigo}")
    fun obtener(@PathVariable codigo: String) = servicio.obtener(codigo)

    @PutMapping("/{codigo}")
    fun guardar(@PathVariable codigo: String, @RequestBody c: CambioVideo) = servicio.guardar(codigo, c)

    @DeleteMapping("/{codigo}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    fun borrar(request: HttpServletRequest, @PathVariable codigo: String) = servicio.borrar(request.sesion().usuario, codigo)

    /** Gemini escribe (o reescribe) el guion por partes y los copys. */
    @PostMapping("/{codigo}/guion")
    fun redactar(@PathVariable codigo: String) = servicio.redactar(codigo)

    @GetMapping("/{codigo}/prompts")
    fun prompts(@PathVariable codigo: String) = servicio.prompts(codigo)

    @PostMapping("/{codigo}/generar")
    @ResponseStatus(HttpStatus.ACCEPTED)
    fun generar(@PathVariable codigo: String) = servicio.generar(codigo)

    @PostMapping("/{codigo}/cancelar")
    fun cancelar(@PathVariable codigo: String) = servicio.cancelar(codigo)

    @PutMapping("/{codigo}/aprobacion")
    fun aprobar(request: HttpServletRequest, @PathVariable codigo: String, @RequestBody p: PeticionAprobarVideo) =
        servicio.aprobar(request.sesion().usuario, codigo, p.aprobado)

    /** El MP4: como recurso, para que el reproductor pueda saltar (peticiones Range). `descargar=true` lo baja. */
    @GetMapping("/{codigo}/archivo")
    fun archivo(@PathVariable codigo: String, @RequestParam(defaultValue = "false") descargar: Boolean): ResponseEntity<Resource> {
        val ruta = servicio.archivo(codigo)
        val r = ResponseEntity.ok().contentType(MediaType.parseMediaType("video/mp4")).cacheControl(CacheControl.noCache())
        if (descargar) r.header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.attachment().filename("$codigo.mp4").build().toString())
        return r.body(FileSystemResource(ruta))
    }
}
