package pe.edu.lcb.radar.api

import jakarta.servlet.FilterChain
import jakarta.servlet.http.HttpServletRequest
import jakarta.servlet.http.HttpServletResponse
import org.springframework.http.HttpHeaders
import org.springframework.http.HttpStatus
import org.springframework.http.ResponseEntity
import org.springframework.stereotype.Component
import org.springframework.web.bind.annotation.DeleteMapping
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PathVariable
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.PutMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController
import org.springframework.web.filter.OncePerRequestFilter
import pe.edu.lcb.radar.aplicacion.ServicioAuth
import pe.edu.lcb.radar.dominio.NoAutenticado
import pe.edu.lcb.radar.dominio.Usuario
import java.time.Instant

// ── Contrato ──────────────────────────────────────────────────────────────

data class UsuarioDto(
    val codigo: String,
    val email: String,
    val nombre: String,
    val rol: String,
    val activo: Boolean,
    val debeCambiar: Boolean,
    val tieneRecuperacion: Boolean,
    val ultimoAcceso: Instant?,
    val creado: Instant,
)

fun Usuario.dto() = UsuarioDto(codigo, email, nombre, rol, activo, debeCambiar, tieneRecuperacion, ultimoAcceso, creado)

data class EstadoAuthDto(val necesitaAlta: Boolean, val usuario: UsuarioDto?)
data class PeticionAlta(val nombre: String, val email: String, val clave: String)
data class PeticionEntrar(val email: String, val clave: String)
data class PeticionRecuperar(val email: String, val codigo: String, val claveNueva: String)
data class PeticionCuenta(val nombre: String? = null, val claveActual: String? = null, val claveNueva: String? = null, val nuevoCodigo: Boolean = false)
data class PeticionNuevoUsuario(val nombre: String, val email: String, val rol: String = "miembro")
data class PeticionCambioUsuario(val rol: String? = null, val activo: Boolean? = null, val nombre: String? = null)
data class RespuestaAcceso(val usuario: UsuarioDto, val codigoRecuperacion: String? = null)
data class RespuestaClaveTemporal(val usuario: UsuarioDto, val claveTemporal: String)

// ── Filtro de sesion ──────────────────────────────────────────────────────

private const val ATRIBUTO = "radar.sesion"

/** La sesion de esta peticion (el filtro ya la valido). */
fun HttpServletRequest.sesion(): ServicioAuth.Sesion =
    getAttribute(ATRIBUTO) as? ServicioAuth.Sesion ?: throw NoAutenticado()

fun cookieSesion(token: String, segundos: Long) =
    "${ServicioAuth.COOKIE}=$token; Path=/; HttpOnly; SameSite=Strict; Max-Age=$segundos"

/**
 * Todo /api exige sesion salvo lo necesario para entrar. La cookie es HttpOnly
 * y SameSite=Strict (sin `Secure` porque el panel corre en http://localhost;
 * si algun dia se publica por https hay que anadirlo).
 */
@Component
class FiltroSesion(private val auth: ServicioAuth) : OncePerRequestFilter() {

    private val publicas = setOf("/api/auth/estado", "/api/auth/alta", "/api/auth/entrar", "/api/auth/recuperar", "/api/auth/salir")

    override fun shouldNotFilter(request: HttpServletRequest): Boolean =
        !request.requestURI.startsWith("/api/") || request.method == "OPTIONS"

    override fun doFilterInternal(request: HttpServletRequest, response: HttpServletResponse, cadena: FilterChain) {
        val token = request.cookies?.firstOrNull { it.name == ServicioAuth.COOKIE }?.value
        try {
            val s = auth.sesion(token)
            request.setAttribute(ATRIBUTO, s)
            if (s.renovar) response.addHeader(HttpHeaders.SET_COOKIE, cookieSesion(token!!, ServicioAuth.INACTIVIDAD_MS / 1000))
        } catch (e: NoAutenticado) {
            if (request.requestURI !in publicas) {
                response.status = HttpStatus.UNAUTHORIZED.value()
                response.contentType = "application/json;charset=UTF-8"
                response.writer.write("""{"error":"${e.message}","sesion":false}""")
                return
            }
        }
        cadena.doFilter(request, response)
    }
}

// ── Controladores ─────────────────────────────────────────────────────────

@RestController
@RequestMapping("/api/auth")
class AuthController(private val auth: ServicioAuth) {

    private fun conCookie(token: String, cuerpo: Any) = ResponseEntity.ok()
        .header(HttpHeaders.SET_COOKIE, cookieSesion(token, ServicioAuth.INACTIVIDAD_MS / 1000)).body(cuerpo)

    /** Siempre responde: dice si hay que crear la primera cuenta y quien es el usuario, si hay sesion. */
    @GetMapping("/estado")
    fun estado(request: HttpServletRequest): EstadoAuthDto {
        val usuario = runCatching { request.sesion().usuario.dto() }.getOrNull()
        return EstadoAuthDto(auth.necesitaAlta(), usuario)
    }

    @PostMapping("/alta")
    fun alta(@RequestBody p: PeticionAlta) = auth.alta(p.nombre, p.email, p.clave)
        .let { conCookie(it.token, RespuestaAcceso(it.usuario.dto(), it.codigoRecuperacion)) }

    @PostMapping("/entrar")
    fun entrar(@RequestBody p: PeticionEntrar) = auth.entrar(p.email, p.clave).let { conCookie(it.token, RespuestaAcceso(it.usuario.dto())) }

    @PostMapping("/recuperar")
    fun recuperar(@RequestBody p: PeticionRecuperar) =
        auth.recuperar(p.email, p.codigo, p.claveNueva).let { conCookie(it.token, RespuestaAcceso(it.usuario.dto(), it.codigoRecuperacion)) }

    @PostMapping("/salir")
    fun salir(request: HttpServletRequest): ResponseEntity<Void> {
        runCatching { auth.salir(request.sesion().huella) }
        return ResponseEntity.noContent().header(HttpHeaders.SET_COOKIE, cookieSesion("", 0)).build()
    }

    @PutMapping("/cuenta")
    fun cuenta(request: HttpServletRequest, @RequestBody p: PeticionCuenta): RespuestaAcceso {
        val s = request.sesion()
        val c = auth.actualizarCuenta(s.usuario, s.huella, p.nombre, p.claveActual, p.claveNueva, p.nuevoCodigo)
        return RespuestaAcceso(c.usuario.dto(), c.codigoRecuperacion)
    }
}

/** Gestion de cuentas: solo administradores. */
@RestController
@RequestMapping("/api/usuarios")
class UsuariosController(private val auth: ServicioAuth) {

    @GetMapping
    fun listar(request: HttpServletRequest): List<UsuarioDto> {
        auth.exigirAdmin(request.sesion().usuario)
        return auth.listar().map { it.dto() }
    }

    @PostMapping
    @org.springframework.web.bind.annotation.ResponseStatus(HttpStatus.CREATED)
    fun crear(request: HttpServletRequest, @RequestBody p: PeticionNuevoUsuario): RespuestaClaveTemporal =
        auth.crearUsuario(request.sesion().usuario, p.nombre, p.email, p.rol).let { RespuestaClaveTemporal(it.first.dto(), it.second) }

    @PutMapping("/{codigo}")
    fun cambiar(request: HttpServletRequest, @PathVariable codigo: String, @RequestBody p: PeticionCambioUsuario) =
        auth.cambiarUsuario(request.sesion().usuario, codigo, p.rol, p.activo, p.nombre).dto()

    @PostMapping("/{codigo}/reiniciar-clave")
    fun reiniciar(request: HttpServletRequest, @PathVariable codigo: String): RespuestaClaveTemporal =
        auth.reiniciarClave(request.sesion().usuario, codigo).let { RespuestaClaveTemporal(it.first.dto(), it.second) }

    @DeleteMapping("/{codigo}")
    @org.springframework.web.bind.annotation.ResponseStatus(HttpStatus.NO_CONTENT)
    fun borrar(request: HttpServletRequest, @PathVariable codigo: String) = auth.borrarUsuario(request.sesion().usuario, codigo)

    @GetMapping("/auditoria")
    fun auditoria(request: HttpServletRequest) = auth.auditoria(request.sesion().usuario)
}
