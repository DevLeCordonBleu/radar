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
import org.springframework.web.bind.annotation.RequestPart
import org.springframework.web.bind.annotation.ResponseStatus
import org.springframework.web.bind.annotation.RestController
import org.springframework.web.multipart.MultipartFile
import pe.edu.lcb.radar.aplicacion.ServicioPublicaciones
import pe.edu.lcb.radar.infraestructura.CambioPublicacion

data class PeticionPublicacion(val idea: String = "", val redes: List<String> = emptyList(), val modoCopy: String = "POR_RED")

data class PeticionFotoFondo(val id: Long = 0)

data class PeticionFondoIa(val descripcion: String? = null)

data class PeticionAprobarPublicacion(val aprobada: Boolean = true)

data class PeticionEnlace(val red: String = "", val url: String = "")

/** Publicaciones en Facebook, Instagram y LinkedIn: textos, flyer o archivo propio, aprobacion y enlaces. */
@RestController
@RequestMapping("/api/publicaciones")
class PublicacionesController(private val servicio: ServicioPublicaciones) {

    /** Sin `archivadas`, las que siguen en curso; con `archivadas=true`, toda la biblioteca. */
    @GetMapping
    fun listar(@RequestParam(defaultValue = "false") archivadas: Boolean) = servicio.listar(archivadas)

    /** Comprueba los enlaces de todas las publicadas (biblioteca). */
    @PostMapping("/verificar")
    fun verificarTodas(request: HttpServletRequest) = servicio.verificarTodas(request.sesion().usuario)

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    fun crear(request: HttpServletRequest, @RequestBody p: PeticionPublicacion) =
        servicio.crear(request.sesion().usuario, p.idea, p.redes, p.modoCopy)

    // ── Marca (colores, hashtags del rubro y logo de los flyers) ──

    @GetMapping("/marca")
    fun marca() = servicio.marca()

    @PutMapping("/marca")
    fun guardarMarca(request: HttpServletRequest, @RequestBody m: ServicioPublicaciones.Marca) = servicio.guardarMarca(request.sesion().usuario, m)

    @PostMapping("/marca/logo")
    fun subirLogo(request: HttpServletRequest, @RequestPart("archivo") archivo: MultipartFile) =
        archivo.inputStream.use { servicio.subirLogo(request.sesion().usuario, it) }

    @DeleteMapping("/marca/logo")
    fun quitarLogo(request: HttpServletRequest) = servicio.quitarLogo(request.sesion().usuario)

    @GetMapping("/marca/logo")
    fun logo(): ResponseEntity<Resource> {
        val (ruta, tipo) = servicio.logo()
        return ResponseEntity.ok().contentType(MediaType.parseMediaType(tipo)).cacheControl(CacheControl.noCache()).body(FileSystemResource(ruta))
    }

    /** Fotos verticales del banco gratuito para el fondo del flyer. */
    @GetMapping("/fotos")
    fun fotos(@RequestParam consulta: String, @RequestParam(defaultValue = "1") pagina: Int) = servicio.buscarFotos(consulta, pagina)

    /** Desde un video aprobado: sus copys y una copia del MP4 (si ya existe, la misma). */
    @PostMapping("/desde-video/{codVideo}")
    fun desdeVideo(request: HttpServletRequest, @PathVariable codVideo: String) = servicio.desdeVideo(request.sesion().usuario, codVideo)

    @GetMapping("/{codigo}")
    fun obtener(@PathVariable codigo: String) = servicio.obtener(codigo)

    @PutMapping("/{codigo}")
    fun guardar(request: HttpServletRequest, @PathVariable codigo: String, @RequestBody c: CambioPublicacion) =
        servicio.guardar(request.sesion().usuario, codigo, c)

    /** No borra: archiva (sigue en la biblioteca con su historial). */
    @DeleteMapping("/{codigo}")
    fun archivar(request: HttpServletRequest, @PathVariable codigo: String) = servicio.archivar(request.sesion().usuario, codigo)

    @PostMapping("/{codigo}/restaurar")
    fun restaurar(request: HttpServletRequest, @PathVariable codigo: String) = servicio.archivar(request.sesion().usuario, codigo, false)

    @GetMapping("/{codigo}/historial")
    fun historial(@PathVariable codigo: String) = servicio.historial(codigo)

    @PostMapping("/{codigo}/verificar")
    fun verificar(request: HttpServletRequest, @PathVariable codigo: String) = servicio.verificar(request.sesion().usuario, codigo)

    /** Gemini escribe (o reescribe) el texto de cada red y los hashtags. */
    @PostMapping("/{codigo}/textos")
    fun redactar(request: HttpServletRequest, @PathVariable codigo: String) = servicio.redactar(request.sesion().usuario, codigo)

    @PutMapping("/{codigo}/aprobacion")
    fun aprobar(request: HttpServletRequest, @PathVariable codigo: String, @RequestBody p: PeticionAprobarPublicacion) =
        servicio.aprobar(request.sesion().usuario, codigo, p.aprobada)

    @PutMapping("/{codigo}/enlaces")
    fun enlace(request: HttpServletRequest, @PathVariable codigo: String, @RequestBody p: PeticionEnlace) =
        servicio.registrarEnlace(request.sesion().usuario, codigo, p.red, p.url)

    // ── Flyer: el fondo (al elegirlo se arma el flyer) y volver a armarlo ──

    @PostMapping("/{codigo}/fondo/foto")
    fun fondoFoto(request: HttpServletRequest, @PathVariable codigo: String, @RequestBody p: PeticionFotoFondo) =
        servicio.fondoFoto(request.sesion().usuario, codigo, p.id)

    /** Gemini (de pago) crea el fondo; sin `descripcion`, usa la que propuso la IA al escribir los textos. */
    @PostMapping("/{codigo}/fondo/ia")
    fun fondoIa(request: HttpServletRequest, @PathVariable codigo: String, @RequestBody p: PeticionFondoIa) =
        servicio.fondoIa(request.sesion().usuario, codigo, p.descripcion)

    @PostMapping("/{codigo}/fondo")
    fun fondoPropio(request: HttpServletRequest, @PathVariable codigo: String, @RequestPart("archivo") archivo: MultipartFile) =
        archivo.inputStream.use { servicio.fondoPropio(request.sesion().usuario, codigo, it) }

    @PostMapping("/{codigo}/flyer")
    fun componer(@PathVariable codigo: String) = servicio.componer(codigo)

    /** `multipart`: `archivo` = imagen JPG/PNG o video MP4. */
    @PostMapping("/{codigo}/archivo")
    fun subir(request: HttpServletRequest, @PathVariable codigo: String, @RequestPart("archivo") archivo: MultipartFile) =
        archivo.inputStream.use { servicio.subir(request.sesion().usuario, codigo, it) }

    @DeleteMapping("/{codigo}/archivo")
    fun quitarArchivo(request: HttpServletRequest, @PathVariable codigo: String) = servicio.quitarArchivo(request.sesion().usuario, codigo)

    /** La imagen o el video, como recurso (el reproductor pide trozos con Range). `descargar=true` lo baja. */
    @GetMapping("/{codigo}/archivo")
    fun archivo(@PathVariable codigo: String, @RequestParam(defaultValue = "false") descargar: Boolean): ResponseEntity<Resource> {
        val (ruta, tipo) = servicio.archivo(codigo)
        val r = ResponseEntity.ok().contentType(MediaType.parseMediaType(tipo)).cacheControl(CacheControl.noCache())
        if (descargar) {
            r.header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.attachment().filename(ruta.fileName.toString()).build().toString())
        }
        return r.body(FileSystemResource(ruta))
    }
}
