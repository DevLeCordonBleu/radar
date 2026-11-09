package pe.edu.lcb.radar.aplicacion

import org.springframework.scheduling.annotation.Scheduled
import org.springframework.stereotype.Service
import pe.edu.lcb.radar.dominio.NoAutenticado
import pe.edu.lcb.radar.dominio.Prohibido
import pe.edu.lcb.radar.dominio.ReglaIncumplida
import pe.edu.lcb.radar.dominio.Usuario
import pe.edu.lcb.radar.infraestructura.RepositorioUsuarios
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.Base64
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.PBEKeySpec

/**
 * Cuentas y sesiones.
 *
 *  - Contraseñas con PBKDF2-SHA256 (100 000 iteraciones, sal propia).
 *  - La cookie lleva un token aleatorio; en la base solo esta su huella SHA-256,
 *    asi que robar la base no da sesiones.
 *  - 5 fallos seguidos bloquean la cuenta 15 min (se duplica cada 5 fallos, hasta 24 h).
 *  - "Correo o contraseña incorrectos" es el unico mensaje, exista o no el correo.
 *  - Siempre queda al menos un administrador activo.
 */
@Service
class ServicioAuth(private val repo: RepositorioUsuarios) {

    data class Sesion(val usuario: Usuario, val huella: String, val renovar: Boolean)
    data class Entrada(val usuario: Usuario, val token: String, val codigoRecuperacion: String? = null)

    private val azar = SecureRandom()

    // ── Estado y alta ─────────────────────────────────────────────────────

    fun necesitaAlta(): Boolean = !repo.hayUsuarios()

    /** El primer usuario es administrador. Solo funciona mientras no haya ninguno. */
    fun alta(nombre: String, email: String, clave: String): Entrada {
        validarNombre(nombre)
        validarEmail(email)
        validarClave(clave, email)
        val codigo = generarCodigo()
        val h = hashear(clave)
        val cod = repo.crear(email, nombre, "admin", h.hash, h.sal, ITERACIONES, false, huella("recuperacion:" + normalizarCodigo(codigo)), soloSiVacio = true)
            ?: throw ReglaIncumplida("La aplicación ya tiene cuentas. Entra con la tuya o pide acceso a un administrador.")
        repo.auditar(cod, "alta_inicial", cod)
        return Entrada(repo.porCodigo(cod), abrirSesion(repo.porCodigo(cod)), codigo)
    }

    // ── Entrar, salir, sesion ─────────────────────────────────────────────

    fun entrar(email: String, clave: String): Entrada {
        val u = repo.porEmail(email)
        if (u == null) {
            verificar(clave, FANTASMA_HASH, FANTASMA_SAL, ITERACIONES)   // mismo tiempo que un usuario real
            throw ReglaIncumplida(MAL)
        }
        val ahora = System.currentTimeMillis()
        val correcta = verificar(clave, u.hash, u.sal, u.iteraciones)
        if (u.bloqueadoHasta > ahora) {
            throw ReglaIncumplida("$MAL Hay demasiados intentos seguidos: prueba dentro de ${espera((u.bloqueadoHasta - ahora) / 1000)}, o entra con tu código de recuperación.")
        }
        if (!correcta) {
            val fallos = repo.fallo(u.codigo)
            val bloqueo = bloqueoTras(fallos)
            if (bloqueo > 0) {
                repo.bloquear(u.codigo, ahora + bloqueo)
                repo.auditar(null, "cuenta_bloqueada", u.codigo)
            } else {
                repo.auditar(null, "entrar_fallido", u.codigo)
            }
            throw ReglaIncumplida(MAL)
        }
        if (!u.activo) throw ReglaIncumplida("Tu cuenta está desactivada. Habla con un administrador.")
        repo.acceso(u.codigo)
        repo.auditar(u.codigo, "entrar", null)
        return Entrada(u, abrirSesion(u))
    }

    fun salir(huella: String?) {
        if (huella != null) repo.cerrarSesion(huella)
    }

    /** Valida la cookie. Lanza NoAutenticado si no hay sesion valida. */
    fun sesion(token: String?): Sesion {
        if (token.isNullOrBlank() || token.length > 100) throw NoAutenticado()
        val h = huella(token)
        val (u, creado, visto) = repo.sesion(h) ?: throw NoAutenticado()
        val ahora = System.currentTimeMillis()
        if (!u.activo || ahora - visto > INACTIVIDAD_MS || ahora - creado > VIDA_MAXIMA_MS) {
            repo.cerrarSesion(h)
            throw NoAutenticado("Tu sesión ha caducado. Vuelve a entrar.")
        }
        val renovar = ahora - visto > RENOVAR_CADA_MS
        if (renovar) repo.verSesion(h, ahora)
        return Sesion(u, h, renovar)
    }

    // ── Cuenta propia ─────────────────────────────────────────────────────

    data class Cambio(val usuario: Usuario, val codigoRecuperacion: String?)

    fun actualizarCuenta(u: Usuario, huellaSesion: String, nombre: String?, claveActual: String?, claveNueva: String?, nuevoCodigo: Boolean): Cambio {
        var codigo: String? = null
        if (nombre != null) {
            validarNombre(nombre)
            repo.nombre(u.codigo, nombre)
        }
        if (claveNueva != null || nuevoCodigo) {
            if (claveActual == null || !verificar(claveActual, u.hash, u.sal, u.iteraciones)) throw ReglaIncumplida("La contraseña actual no es correcta.")
        }
        if (claveNueva != null) {
            validarClave(claveNueva, u.email)
            if (claveNueva == claveActual) throw ReglaIncumplida("La contraseña nueva tiene que ser distinta de la actual.")
            val h = hashear(claveNueva)
            repo.cambiarClave(u.codigo, h.hash, h.sal, ITERACIONES, false)
            repo.cerrarSesiones(u.id, huellaSesion)
            repo.auditar(u.codigo, "cambiar_clave", u.codigo)
            if (!u.tieneRecuperacion) codigo = nuevoCodigoRecuperacion(u.codigo)
        }
        if (nuevoCodigo && codigo == null) {
            codigo = nuevoCodigoRecuperacion(u.codigo)
            repo.auditar(u.codigo, "nuevo_codigo", u.codigo)
        }
        return Cambio(repo.porCodigo(u.codigo), codigo)
    }

    /** Olvidaste la contraseña: el correo + el codigo de recuperacion la restablecen. */
    fun recuperar(email: String, codigo: String, claveNueva: String): Entrada {
        val u = repo.porEmail(email)
        val ahora = System.currentTimeMillis()
        val esperada = u?.let { repo.recuperacion(it.codigo) }
        val ok = u != null && esperada != null && u.bloqueadoHasta <= ahora &&
            MessageDigest.isEqual(esperada.toByteArray(), huella("recuperacion:" + normalizarCodigo(codigo)).toByteArray())
        if (!ok || u == null) {
            u?.let {
                val f = repo.fallo(it.codigo)
                bloqueoTras(f).takeIf { b -> b > 0 }?.let { b -> repo.bloquear(it.codigo, ahora + b) }
            }
            throw ReglaIncumplida("El correo o el código de recuperación no son correctos.")
        }
        if (!u.activo) throw ReglaIncumplida("Tu cuenta está desactivada. Habla con un administrador.")
        validarClave(claveNueva, u.email)
        val h = hashear(claveNueva)
        repo.cambiarClave(u.codigo, h.hash, h.sal, ITERACIONES, false)
        repo.cerrarSesiones(u.id)
        val nuevo = nuevoCodigoRecuperacion(u.codigo)       // el codigo es de un solo uso
        repo.auditar(u.codigo, "recuperar", u.codigo)
        return Entrada(repo.porCodigo(u.codigo), abrirSesion(u), nuevo)
    }

    // ── Gestion de usuarios (solo administradores) ────────────────────────

    fun exigirAdmin(u: Usuario) {
        if (!u.esAdmin) throw Prohibido("Solo un administrador puede gestionar usuarios.")
    }

    fun listar(): List<Usuario> = repo.todos()

    /** Crea un miembro o administrador con una contraseña temporal que se devuelve UNA vez. */
    fun crearUsuario(actor: Usuario, nombre: String, email: String, rol: String): Pair<Usuario, String> {
        exigirAdmin(actor)
        validarNombre(nombre)
        validarEmail(email)
        if (rol !in ROLES) throw ReglaIncumplida("El rol es admin o miembro.")
        if (repo.porEmail(email) != null) throw ReglaIncumplida("Ya existe una cuenta con ese correo.")
        val temporal = claveTemporal()
        val h = hashear(temporal)
        val cod = repo.crear(email, nombre, rol, h.hash, h.sal, ITERACIONES, true, null)!!
        repo.auditar(actor.codigo, "crear_usuario", cod)
        return repo.porCodigo(cod) to temporal
    }

    fun cambiarUsuario(actor: Usuario, codigo: String, rol: String?, activo: Boolean?, nombre: String?): Usuario {
        exigirAdmin(actor)
        val u = repo.porCodigo(codigo)
        val dejaDeSerAdmin = u.esAdmin && u.activo && ((rol != null && rol != "admin") || activo == false)
        if (dejaDeSerAdmin && repo.adminsActivos() <= 1) throw ReglaIncumplida("Tiene que quedar al menos un administrador activo.")
        if (rol != null) {
            if (rol !in ROLES) throw ReglaIncumplida("El rol es admin o miembro.")
            repo.rol(codigo, rol)
            repo.auditar(actor.codigo, "cambiar_rol", codigo)
        }
        if (nombre != null) {
            validarNombre(nombre)
            repo.nombre(codigo, nombre)
        }
        if (activo != null) {
            repo.activo(codigo, activo)
            if (!activo) repo.cerrarSesiones(u.id)
            repo.auditar(actor.codigo, if (activo) "activar_usuario" else "desactivar_usuario", codigo)
        }
        return repo.porCodigo(codigo)
    }

    fun reiniciarClave(actor: Usuario, codigo: String): Pair<Usuario, String> {
        exigirAdmin(actor)
        val u = repo.porCodigo(codigo)
        val temporal = claveTemporal()
        val h = hashear(temporal)
        repo.cambiarClave(codigo, h.hash, h.sal, ITERACIONES, true)
        repo.cerrarSesiones(u.id)
        repo.auditar(actor.codigo, "reiniciar_clave", codigo)
        return repo.porCodigo(codigo) to temporal
    }

    fun borrarUsuario(actor: Usuario, codigo: String) {
        exigirAdmin(actor)
        val u = repo.porCodigo(codigo)
        if (u.codigo == actor.codigo) throw ReglaIncumplida("No puedes borrar tu propia cuenta.")
        if (u.esAdmin && u.activo && repo.adminsActivos() <= 1) throw ReglaIncumplida("Tiene que quedar al menos un administrador activo.")
        repo.borrar(codigo)
        repo.auditar(actor.codigo, "borrar_usuario", codigo)
    }

    fun auditoria(actor: Usuario): List<Map<String, Any?>> {
        exigirAdmin(actor)
        return repo.auditoria()
    }

    @Scheduled(fixedDelayString = "PT6H", initialDelayString = "PT1M")
    fun limpiar() {
        val ahora = System.currentTimeMillis()
        repo.limpiarSesiones(ahora - INACTIVIDAD_MS, ahora - VIDA_MAXIMA_MS)
    }

    // ── Internos ──────────────────────────────────────────────────────────

    private fun abrirSesion(u: Usuario): String {
        val token = Base64.getUrlEncoder().withoutPadding().encodeToString(ByteArray(32).also(azar::nextBytes))
        repo.crearSesion(huella(token), u.id, System.currentTimeMillis())
        return token
    }

    private fun nuevoCodigoRecuperacion(codigoUsuario: String): String {
        val c = generarCodigo()
        repo.guardarRecuperacion(codigoUsuario, huella("recuperacion:" + normalizarCodigo(c)))
        return c
    }

    private data class Hash(val hash: String, val sal: String)

    private fun derivar(clave: String, sal: ByteArray, iteraciones: Int): ByteArray =
        SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256")
            .generateSecret(PBEKeySpec(java.text.Normalizer.normalize(clave, java.text.Normalizer.Form.NFKC).toCharArray(), sal, iteraciones, 256)).encoded

    private fun hashear(clave: String): Hash {
        val sal = ByteArray(16).also(azar::nextBytes)
        return Hash(Base64.getEncoder().encodeToString(derivar(clave, sal, ITERACIONES)), Base64.getEncoder().encodeToString(sal))
    }

    private fun verificar(clave: String, hash: String, sal: String, iteraciones: Int): Boolean =
        MessageDigest.isEqual(derivar(clave, Base64.getDecoder().decode(sal), iteraciones), Base64.getDecoder().decode(hash))

    private fun huella(texto: String): String =
        Base64.getEncoder().encodeToString(MessageDigest.getInstance("SHA-256").digest(texto.toByteArray()))

    /** 20 simbolos sin caracteres ambiguos, en grupos de 4: XXXX-XXXX-XXXX-XXXX-XXXX. */
    private fun generarCodigo(): String =
        (1..20).map { ALFABETO[azar.nextInt(ALFABETO.length)] }.joinToString("").chunked(4).joinToString("-")

    private fun normalizarCodigo(c: String) = c.uppercase().filter { it.isLetterOrDigit() }

    private fun claveTemporal(): String =
        (1..4).joinToString("-") { (1..4).map { ALFABETO[azar.nextInt(ALFABETO.length)] }.joinToString("") } + "-x7"

    private fun bloqueoTras(fallos: Int): Long {
        if (fallos < 5 || fallos % 5 != 0) return 0
        val tanda = fallos / 5 - 1
        return minOf(15 * 60_000L * (1L shl minOf(tanda, 10)), 24 * 3_600_000L)
    }

    private fun espera(s: Long) = if (s < 60) "$s segundos" else if (s < 3600) "${(s + 59) / 60} minutos" else "${(s + 3599) / 3600} horas"

    private fun validarNombre(n: String) {
        if (n.trim().isEmpty() || n.trim().length > 80) throw ReglaIncumplida("Escribe un nombre (hasta 80 caracteres).")
    }

    private fun validarEmail(e: String) {
        if (e.length > 254 || !Regex("^[^@\\s]+@[^@\\s.]+(\\.[^@\\s.]+)+$").matches(e.trim())) throw ReglaIncumplida("Ese correo no parece válido.")
    }

    internal fun validarClave(clave: String, email: String?) {
        if (clave.length < CLAVE_MIN) throw ReglaIncumplida("La contraseña necesita al menos $CLAVE_MIN caracteres.")
        if (clave.length > 128) throw ReglaIncumplida("La contraseña no puede pasar de 128 caracteres.")
        val baja = clave.lowercase()
        val local = email?.substringBefore("@")?.lowercase().orEmpty()
        if (local.length >= 4 && baja.contains(local)) throw ReglaIncumplida("La contraseña no puede contener tu correo.")
        if (clave.toSet().size < 4 || COMUNES.any { baja.contains(it) }) {
            throw ReglaIncumplida("Esa contraseña es demasiado fácil de adivinar. Prueba con una frase.")
        }
    }

    companion object {
        const val COOKIE = "radar_sesion"
        const val INACTIVIDAD_MS = 7 * 24 * 3_600_000L
        const val VIDA_MAXIMA_MS = 30 * 24 * 3_600_000L
        private const val RENOVAR_CADA_MS = 3_600_000L
        private const val ITERACIONES = 100_000
        private const val CLAVE_MIN = 10
        private const val ALFABETO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
        private val ROLES = setOf("admin", "miembro")
        private val COMUNES = listOf("1234567890", "contraseña", "contrasena", "password", "qwertyuiop", "radaranuncios", "cordonbleu")
        private const val MAL = "Correo o contraseña incorrectos."
        private const val FANTASMA_HASH = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
        private const val FANTASMA_SAL = "AAAAAAAAAAAAAAAAAAAAAA=="
    }
}
