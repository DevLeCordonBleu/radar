package pe.edu.lcb.radar.api

import jakarta.servlet.http.HttpServletRequest
import org.springframework.http.CacheControl
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
import pe.edu.lcb.radar.aplicacion.ServicioSeo
import pe.edu.lcb.radar.infraestructura.ArticuloSeo
import pe.edu.lcb.radar.infraestructura.KeywordSeo
import pe.edu.lcb.radar.infraestructura.MejoraSeo
import pe.edu.lcb.radar.infraestructura.PaginaSeo
import pe.edu.lcb.radar.infraestructura.SitioSeo
import pe.edu.lcb.radar.infraestructura.TareaSeo

/**
 * Plan SEO. Lanzar una tarea responde enseguida con la tarea EN_COLA; el panel
 * consulta /tareas/{codigo} hasta que termina.
 */
@RestController
@RequestMapping("/api/seo")
class SeoController(private val servicio: ServicioSeo) {

    @GetMapping("/sitios")
    fun sitios(): List<SitioSeo> = servicio.sitios()

    @PostMapping("/sitios")
    @ResponseStatus(HttpStatus.CREATED)
    fun crear(@RequestBody cuerpo: Map<*, *>): SitioSeo = servicio.crearSitio(cuerpo)

    @PutMapping("/sitios/{codigo}")
    fun ajustar(@PathVariable codigo: String, @RequestBody cuerpo: Map<*, *>): SitioSeo = servicio.ajustarSitio(codigo, cuerpo)

    @DeleteMapping("/sitios/{codigo}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    fun borrar(request: HttpServletRequest, @PathVariable codigo: String) = servicio.borrarSitio(request.sesion().usuario, codigo)

    @PostMapping("/sitios/{codigo}/inventario")
    @ResponseStatus(HttpStatus.ACCEPTED)
    fun inventario(request: HttpServletRequest, @PathVariable codigo: String): TareaSeo = servicio.lanzar(request.sesion().usuario, "INVENTARIO", codigo)

    @PostMapping("/sitios/{codigo}/temas")
    @ResponseStatus(HttpStatus.ACCEPTED)
    fun temas(request: HttpServletRequest, @PathVariable codigo: String): TareaSeo = servicio.lanzar(request.sesion().usuario, "TEMAS", codigo)

    @PostMapping("/keywords/generar")
    @ResponseStatus(HttpStatus.ACCEPTED)
    fun generar(request: HttpServletRequest): TareaSeo = servicio.lanzar(request.sesion().usuario, "KEYWORDS", null)

    @GetMapping("/paginas")
    fun paginas(@RequestParam(required = false) sitio: String?): List<PaginaSeo> = servicio.paginas(sitio)

    @GetMapping("/keywords")
    fun keywords(): List<KeywordSeo> = servicio.keywords()

    @GetMapping("/tareas")
    fun tareas(): List<TareaSeo> = servicio.tareas()

    @GetMapping("/tareas/{codigo}")
    fun tarea(@PathVariable codigo: String): TareaSeo = servicio.tarea(codigo)

    @PostMapping("/tareas/{codigo}/continuar")
    fun continuar(@PathVariable codigo: String): TareaSeo = servicio.continuar(codigo)

    @PostMapping("/tareas/{codigo}/cancelar")
    fun cancelar(@PathVariable codigo: String): TareaSeo = servicio.cancelar(codigo)

    // ── Rubro del negocio propio ──

    @GetMapping("/rubro")
    fun rubro() = servicio.estadoRubro()

    @GetMapping("/fecha-minima")
    fun fechaMinima() = servicio.estadoFechaMinima()

    @PutMapping("/fecha-minima")
    fun guardarFechaMinima(@RequestBody cuerpo: Map<*, *>) = servicio.guardarFechaMinima(cuerpo)

    @PutMapping("/rubro")
    fun guardarRubro(@RequestBody cuerpo: Map<*, *>) = servicio.guardarRubro(cuerpo)

    @PostMapping("/rubro/sugerir")
    fun sugerirRubro() = servicio.sugerirRubro()

    // ── Articulos ──

    @GetMapping("/articulos")
    fun articulos(): List<ArticuloSeo> = servicio.articulos()

    @PostMapping("/articulos")
    @ResponseStatus(HttpStatus.ACCEPTED)
    fun crearArticulo(request: HttpServletRequest, @RequestBody cuerpo: Map<*, *>): ArticuloSeo = servicio.crearArticulo(request.sesion().usuario, cuerpo)

    @GetMapping("/articulos/{codigo}")
    fun articulo(@PathVariable codigo: String): ArticuloSeo = servicio.articulo(codigo)

    @PutMapping("/articulos/{codigo}")
    fun editarArticulo(@PathVariable codigo: String, @RequestBody cuerpo: Map<*, *>): ArticuloSeo = servicio.editarArticulo(codigo, cuerpo)

    @DeleteMapping("/articulos/{codigo}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    fun borrarArticulo(request: HttpServletRequest, @PathVariable codigo: String) = servicio.borrarArticulo(request.sesion().usuario, codigo)

    @PostMapping("/articulos/{codigo}/redactar")
    @ResponseStatus(HttpStatus.ACCEPTED)
    fun redactar(request: HttpServletRequest, @PathVariable codigo: String, @RequestBody(required = false) cuerpo: Map<*, *>?): ArticuloSeo =
        servicio.redactarDeNuevo(request.sesion().usuario, codigo, cuerpo.orEmpty())

    @PostMapping("/articulos/{codigo}/wordpress")
    fun enviar(request: HttpServletRequest, @PathVariable codigo: String, @RequestBody(required = false) cuerpo: Map<*, *>?): ArticuloSeo =
        servicio.enviarAWordpress(request.sesion().usuario, codigo, cuerpo.orEmpty())

    @PostMapping("/articulos/{codigo}/desvincular")
    fun desvincular(@PathVariable codigo: String): ArticuloSeo = servicio.desvincular(codigo)

    @PostMapping("/vista-previa")
    fun vistaPrevia(@RequestBody cuerpo: Map<*, *>) = servicio.vistaPrevia(cuerpo)

    // ── Imagen destacada ──

    @GetMapping("/imagenes")
    fun imagenes() = servicio.imagenes()

    @PostMapping("/imagenes/buscar")
    fun buscarImagenes(@RequestBody cuerpo: Map<*, *>) = servicio.buscarImagenes(cuerpo)

    @GetMapping("/articulos/{codigo}/imagen")
    fun archivoImagen(@PathVariable codigo: String): ResponseEntity<ByteArray> {
        val (datos, mime) = servicio.archivoImagen(codigo)
        return ResponseEntity.ok().contentType(MediaType.parseMediaType(mime)).cacheControl(CacheControl.noCache()).body(datos)
    }

    @PostMapping("/articulos/{codigo}/imagen/foto")
    fun imagenDelBanco(request: HttpServletRequest, @PathVariable codigo: String, @RequestBody cuerpo: Map<*, *>): ArticuloSeo =
        servicio.imagenDelBanco(request.sesion().usuario, codigo, cuerpo)

    @PostMapping("/articulos/{codigo}/imagen/generar")
    fun generarImagen(request: HttpServletRequest, @PathVariable codigo: String, @RequestBody cuerpo: Map<*, *>): ArticuloSeo =
        servicio.generarImagen(request.sesion().usuario, codigo, cuerpo)

    @PutMapping("/articulos/{codigo}/imagen")
    fun textosImagen(@PathVariable codigo: String, @RequestBody cuerpo: Map<*, *>): ArticuloSeo = servicio.textosImagen(codigo, cuerpo)

    @DeleteMapping("/articulos/{codigo}/imagen")
    fun quitarImagen(@PathVariable codigo: String): ArticuloSeo = servicio.quitarImagen(codigo)

    // ── Automatico ──

    @GetMapping("/automatico")
    fun automatico() = servicio.estadoAutomatico()

    @PutMapping("/automatico")
    fun guardarAutomatico(request: HttpServletRequest, @RequestBody cuerpo: Map<*, *>) = servicio.guardarAutomatico(request.sesion().usuario, cuerpo)

    @PostMapping("/automatico/ejecutar")
    @ResponseStatus(HttpStatus.ACCEPTED)
    fun ejecutarAutomatico(request: HttpServletRequest): TareaSeo = servicio.ejecutarAutomatico(request.sesion().usuario)

    // ── Search Console ──

    @GetMapping("/search-console")
    fun searchConsole() = servicio.searchConsole()

    @PostMapping("/search-console/comprobar")
    fun comprobarSearchConsole() = servicio.comprobarSearchConsole()

    @PostMapping("/search-console/sincronizar")
    fun sincronizarSearchConsole() = servicio.sincronizarSearchConsole()

    @PutMapping("/search-console/marca")
    fun guardarMarca(request: HttpServletRequest, @RequestBody cuerpo: Map<*, *>) = servicio.guardarMarca(request.sesion().usuario, cuerpo)

    // ── Informes guardados (cortes de Search Console y keywords) ──

    @GetMapping("/informes")
    fun informes(@RequestParam(required = false) modulo: String?) = servicio.informesGuardados(modulo)

    @GetMapping("/informes/{codigo}")
    fun informe(@PathVariable codigo: String) = servicio.informeGuardado(codigo)

    @GetMapping("/informes/{codigo}/csv")
    fun csvInforme(@PathVariable codigo: String): ResponseEntity<String> {
        val (nombre, csv) = servicio.csvInforme(codigo)
        return ResponseEntity.ok()
            .header("Content-Disposition", "attachment; filename=\"$nombre\"")
            .contentType(MediaType("text", "csv", Charsets.UTF_8))
            .body(csv)
    }

    @PostMapping("/informes/{codigo}/restaurar")
    fun restaurarCorte(@PathVariable codigo: String) = servicio.restaurarCorte(codigo)

    @PutMapping("/search-console/terminos")
    fun guardarTerminos(request: HttpServletRequest, @RequestBody cuerpo: Map<*, *>) = servicio.guardarTerminos(request.sesion().usuario, cuerpo)

    @PostMapping("/mejoras")
    fun proponerMejora(request: HttpServletRequest, @RequestBody cuerpo: Map<*, *>): MejoraSeo = servicio.proponerMejora(request.sesion().usuario, cuerpo)

    @PutMapping("/mejoras/estado")
    fun estadoMejora(@RequestBody cuerpo: Map<*, *>): MejoraSeo = servicio.estadoMejora(cuerpo)

    // ── WordPress ──

    @GetMapping("/wordpress")
    fun wordpress() = servicio.wordpress()

    @PostMapping("/wordpress/probar")
    fun probarWordpress() = servicio.probarWordpress()
}
