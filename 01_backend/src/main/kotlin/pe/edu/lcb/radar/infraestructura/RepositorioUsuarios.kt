package pe.edu.lcb.radar.infraestructura

import org.springframework.jdbc.core.JdbcTemplate
import org.springframework.stereotype.Repository
import pe.edu.lcb.radar.dominio.NoEncontrado
import pe.edu.lcb.radar.dominio.Usuario
import java.sql.ResultSet
import java.time.Instant

/** Cuentas, sesiones y auditoria. El unico lugar que conoce el SQL de la seguridad. */
@Repository
class RepositorioUsuarios(private val jdbc: JdbcTemplate) {

    private val mapeo = { rs: ResultSet, _: Int ->
        Usuario(
            id = rs.getLong("id_usuario"),
            codigo = rs.getString("cod_usuario"),
            email = rs.getString("usuario_email"),
            nombre = rs.getString("usuario_nombre"),
            rol = rs.getString("rol"),
            activo = rs.getInt("estado_reg") == 1,
            debeCambiar = rs.getInt("debe_cambiar") == 1,
            tieneRecuperacion = rs.getString("recuperacion") != null,
            ultimoAcceso = rs.getString("ultimo_acceso")?.let { Instant.parse(it) },
            creado = Instant.parse(rs.getString("fec_creacion")),
            hash = rs.getString("clave_hash"),
            sal = rs.getString("clave_sal"),
            iteraciones = rs.getInt("clave_iteraciones"),
            fallos = rs.getInt("fallos"),
            bloqueadoHasta = rs.getLong("bloqueado_hasta"),
        )
    }

    fun hayUsuarios(): Boolean = (jdbc.queryForObject("SELECT COUNT(*) FROM usuario", Int::class.java) ?: 0) > 0

    fun todos(): List<Usuario> = jdbc.query("SELECT * FROM usuario ORDER BY id_usuario", mapeo)

    fun porEmail(email: String): Usuario? = jdbc.query("SELECT * FROM usuario WHERE usuario_email = ?", mapeo, email.trim()).firstOrNull()

    fun porCodigo(codigo: String): Usuario =
        jdbc.query("SELECT * FROM usuario WHERE cod_usuario = ?", mapeo, codigo).firstOrNull() ?: throw NoEncontrado("No existe el usuario $codigo.")

    fun adminsActivos(): Int =
        jdbc.queryForObject("SELECT COUNT(*) FROM usuario WHERE rol = 'admin' AND estado_reg = 1", Int::class.java) ?: 0

    /**
     * Crea el usuario. `soloSiVacio` lo hace atomico para el alta inicial: dos
     * peticiones simultaneas no pueden crear dos administradores.
     */
    fun crear(email: String, nombre: String, rol: String, hash: String, sal: String, iteraciones: Int, debeCambiar: Boolean,
              recuperacion: String?, soloSiVacio: Boolean = false): String? {
        val ahora = Instant.now().toString()
        val n = (jdbc.queryForObject("SELECT COALESCE(MAX(id_usuario), 0) + 1 FROM usuario", Int::class.java) ?: 1)
        val codigo = "U%04d".format(n)
        val cond = if (soloSiVacio) "WHERE NOT EXISTS (SELECT 1 FROM usuario)" else ""
        val filas = jdbc.update(
            """INSERT INTO usuario (cod_usuario, usuario_email, usuario_nombre, rol, clave_hash, clave_sal, clave_iteraciones,
                                    debe_cambiar, recuperacion, ultimo_acceso, fec_creacion, fec_modif)
               SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? $cond""",
            codigo, email.trim().lowercase(), nombre.trim(), rol, hash, sal, iteraciones, if (debeCambiar) 1 else 0,
            recuperacion, if (soloSiVacio) ahora else null, ahora, ahora,
        )
        return if (filas == 1) codigo else null
    }

    fun cambiarClave(codigo: String, hash: String, sal: String, iteraciones: Int, debeCambiar: Boolean) {
        jdbc.update(
            "UPDATE usuario SET clave_hash = ?, clave_sal = ?, clave_iteraciones = ?, debe_cambiar = ?, fallos = 0, bloqueado_hasta = 0, fec_modif = ? WHERE cod_usuario = ?",
            hash, sal, iteraciones, if (debeCambiar) 1 else 0, Instant.now().toString(), codigo,
        )
    }

    fun recuperacion(codigo: String): String? =
        jdbc.query("SELECT recuperacion FROM usuario WHERE cod_usuario = ?", { rs, _ -> rs.getString(1) }, codigo).firstOrNull()

    fun guardarRecuperacion(codigo: String, huella: String) {
        jdbc.update("UPDATE usuario SET recuperacion = ?, fec_modif = ? WHERE cod_usuario = ?", huella, Instant.now().toString(), codigo)
    }

    fun nombre(codigo: String, nombre: String) {
        jdbc.update("UPDATE usuario SET usuario_nombre = ?, fec_modif = ? WHERE cod_usuario = ?", nombre.trim(), Instant.now().toString(), codigo)
    }

    fun rol(codigo: String, rol: String) {
        jdbc.update("UPDATE usuario SET rol = ?, fec_modif = ? WHERE cod_usuario = ?", rol, Instant.now().toString(), codigo)
    }

    fun activo(codigo: String, activo: Boolean) {
        jdbc.update("UPDATE usuario SET estado_reg = ?, fec_modif = ? WHERE cod_usuario = ?", if (activo) 1 else 0, Instant.now().toString(), codigo)
    }

    fun fallo(codigo: String): Int {
        jdbc.update("UPDATE usuario SET fallos = fallos + 1 WHERE cod_usuario = ?", codigo)
        return jdbc.queryForObject("SELECT fallos FROM usuario WHERE cod_usuario = ?", Int::class.java, codigo) ?: 0
    }

    fun bloquear(codigo: String, hasta: Long) {
        jdbc.update("UPDATE usuario SET bloqueado_hasta = ? WHERE cod_usuario = ?", hasta, codigo)
    }

    fun acceso(codigo: String) {
        jdbc.update("UPDATE usuario SET fallos = 0, bloqueado_hasta = 0, ultimo_acceso = ? WHERE cod_usuario = ?", Instant.now().toString(), codigo)
    }

    fun borrar(codigo: String) {
        val u = porCodigo(codigo)
        jdbc.update("DELETE FROM sesion WHERE id_usuario = ?", u.id)
        jdbc.update("DELETE FROM usuario WHERE cod_usuario = ?", codigo)
    }

    // ── Sesiones ──────────────────────────────────────────────────────────

    fun crearSesion(huella: String, usuario: Long, ahora: Long) {
        jdbc.update("INSERT INTO sesion (id_sesion, id_usuario, creado, visto) VALUES (?, ?, ?, ?)", huella, usuario, ahora, ahora)
    }

    /** (usuario, creado, visto) de la sesion, o null. */
    fun sesion(huella: String): Triple<Usuario, Long, Long>? = jdbc.query(
        """SELECT u.*, s.creado AS s_creado, s.visto AS s_visto FROM sesion s JOIN usuario u ON u.id_usuario = s.id_usuario WHERE s.id_sesion = ?""",
        { rs, i -> Triple(mapeo(rs, i), rs.getLong("s_creado"), rs.getLong("s_visto")) }, huella,
    ).firstOrNull()

    fun verSesion(huella: String, ahora: Long) {
        jdbc.update("UPDATE sesion SET visto = ? WHERE id_sesion = ?", ahora, huella)
    }

    fun cerrarSesion(huella: String) {
        jdbc.update("DELETE FROM sesion WHERE id_sesion = ?", huella)
    }

    /** Cierra todas las sesiones del usuario, menos (si se da) la actual. */
    fun cerrarSesiones(usuario: Long, salvo: String? = null) {
        jdbc.update("DELETE FROM sesion WHERE id_usuario = ? AND id_sesion != ?", usuario, salvo ?: "")
    }

    fun limpiarSesiones(inactivasAntes: Long, creadasAntes: Long) {
        jdbc.update("DELETE FROM sesion WHERE visto < ? OR creado < ?", inactivasAntes, creadasAntes)
    }

    // ── Auditoria ─────────────────────────────────────────────────────────

    fun auditar(actor: String?, accion: String, objetivo: String?) {
        jdbc.update("INSERT INTO auditoria (fecha, actor, accion, objetivo) VALUES (?, ?, ?, ?)", Instant.now().toString(), actor, accion, objetivo)
    }

    fun auditoria(limite: Int = 100): List<Map<String, Any?>> = jdbc.queryForList(
        """SELECT a.fecha, a.accion, a.objetivo, ua.usuario_nombre AS actor, uo.usuario_nombre AS objetivo_nombre
           FROM auditoria a LEFT JOIN usuario ua ON ua.cod_usuario = a.actor LEFT JOIN usuario uo ON uo.cod_usuario = a.objetivo
           ORDER BY a.id_auditoria DESC LIMIT ?""",
        limite,
    )
}
