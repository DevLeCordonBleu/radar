package pe.edu.lcb.radar.api

import jakarta.servlet.http.HttpServletRequest
import org.springframework.http.HttpStatus
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.PutMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RequestParam
import org.springframework.web.bind.annotation.ResponseStatus
import org.springframework.web.bind.annotation.RestController
import pe.edu.lcb.radar.aplicacion.ServicioAuth
import pe.edu.lcb.radar.aplicacion.ServicioMedicion

data class PeticionPeriodo(val desde: String? = null, val hasta: String? = null)
data class PeticionPropiedad(val propiedad: String = "")

/** Medicion: anuncios propios de Meta (cifras, alertas, informe con IA) y GA4. */
@RestController
@RequestMapping("/api/medicion")
class MedicionController(private val servicio: ServicioMedicion, private val auth: ServicioAuth) {

    @GetMapping("/estado")
    fun estado() = servicio.estado()

    /** Trae de Meta en segundo plano; `desde` opcional (por defecto, lo que falta). */
    @PostMapping("/meta/sincronizar")
    @ResponseStatus(HttpStatus.ACCEPTED)
    fun sincronizar(request: HttpServletRequest, @RequestBody(required = false) p: PeticionPeriodo?) =
        servicio.sincronizar(request.sesion().usuario, p?.desde)

    @GetMapping("/resumen")
    fun resumen(@RequestParam(required = false) desde: String?, @RequestParam(required = false) hasta: String?) = servicio.resumen(desde, hasta)

    @PostMapping("/informe")
    fun informe(request: HttpServletRequest, @RequestBody(required = false) p: PeticionPeriodo?) =
        servicio.informe(request.sesion().usuario, p?.desde, p?.hasta)

    @GetMapping("/ga4/propiedades")
    fun ga4Propiedades() = servicio.ga4Propiedades()

    /** Elige la propiedad de GA4 (queda en GA4_PROPIEDAD del worker). Solo administradores. */
    @PutMapping("/ga4/propiedad")
    fun ga4Propiedad(request: HttpServletRequest, @RequestBody p: PeticionPropiedad): Map<String, Any?> {
        auth.exigirAdmin(request.sesion().usuario)
        return servicio.elegirPropiedadGa4(p.propiedad)
    }

    @GetMapping("/google")
    fun google(@RequestParam(required = false, defaultValue = "false") comprobar: Boolean) = servicio.google(comprobar)

    /** Abre la conexion con Google: devuelve la direccion para dar permiso. Solo administradores. */
    @PostMapping("/google/conectar")
    fun conectarGoogle(request: HttpServletRequest): Map<String, Any?> {
        auth.exigirAdmin(request.sesion().usuario)
        return servicio.conectarGoogle()
    }

    @GetMapping("/ga4")
    fun ga4(@RequestParam(required = false) desde: String?, @RequestParam(required = false) hasta: String?) = servicio.ga4(desde, hasta)
}
