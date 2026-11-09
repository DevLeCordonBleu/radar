package pe.edu.lcb.radar.aplicacion

import org.slf4j.LoggerFactory
import org.springframework.scheduling.annotation.Scheduled
import org.springframework.stereotype.Service
import pe.edu.lcb.radar.dominio.Analisis
import pe.edu.lcb.radar.dominio.Estado
import pe.edu.lcb.radar.dominio.PaginaMeta
import pe.edu.lcb.radar.dominio.Peticion
import pe.edu.lcb.radar.dominio.Prohibido
import pe.edu.lcb.radar.dominio.ReglaIncumplida
import pe.edu.lcb.radar.dominio.Usuario
import pe.edu.lcb.radar.infraestructura.RepositorioAjustes
import pe.edu.lcb.radar.infraestructura.RepositorioAnalisis
import tools.jackson.databind.ObjectMapper
import java.time.Duration
import java.time.Instant
import java.time.LocalTime
import java.time.ZoneId

/**
 * Informe semanal: repite el analisis con el mercado guardado al programarlo, el dia y la hora
 * elegidos (hora de Lima). Como el flujo del Plan SEO, se revisa cada 5 minutos: solo corre con
 * el Radar abierto (si a la hora estaba cerrado, corre al abrirlo).
 *
 * Las paginas que la persona elige cuando un nombre es ambiguo se recuerdan para la semana
 * siguiente: no vuelve a preguntar. Una pausa sin pregunta (cuota de Gemini, red) se reintenta
 * sola cada pocas horas; la que pregunta espera a la persona.
 */
@Service
class ServicioAnalisisSemanal(
    private val analisis: ServicioAnalisis,
    private val repo: RepositorioAnalisis,
    private val ajustes: RepositorioAjustes,
    private val json: ObjectMapper,
) {
    private val log = LoggerFactory.getLogger(javaClass)

    data class AjusteSemanal(
        val activo: Boolean = false,
        /** 1 = lunes ... 7 = domingo. */
        val dia: Int = 1,
        val hora: String = "08:00",
        /** El formulario tal como se programo (validado), con las paginas aprendidas. */
        val peticion: Peticion? = null,
        /** Cuando se activo: la primera ejecucion es la siguiente cita despues de esto. */
        val desde: String? = null,
        val ultima: String? = null,
        /** El analisis de la ultima ejecucion: de el salen las paginas elegidas y los reintentos. */
        val analisis: String? = null,
        val reintentos: Int = 0,
    )

    data class EstadoSemanal(
        val activo: Boolean,
        val dia: Int,
        val hora: String,
        val peticion: Peticion?,
        val ultima: String?,
        val proxima: String?,
        val analisis: Analisis?,
    )

    private fun ajuste(): AjusteSemanal =
        ajustes.leer(CLAVE)?.let { runCatching { json.readValue(it, AjusteSemanal::class.java) }.getOrNull() } ?: AjusteSemanal()

    private fun guardar(a: AjusteSemanal) = ajustes.guardar(CLAVE, json.writeValueAsString(a))

    private fun ultimo(a: AjusteSemanal): Analisis? = a.analisis?.let { runCatching { repo.buscar(it) }.getOrNull() }

    /** El primer `dia` a la `hora` (hora de Lima) despues de la ultima ejecucion o de cuando se activo. */
    private fun proxima(a: AjusteSemanal): Instant? {
        if (!a.activo || a.peticion == null) return null
        val base = (a.ultima ?: a.desde)?.let(Instant::parse) ?: Instant.now()
        val hora = LocalTime.parse(a.hora)
        var d = base.atZone(LIMA).toLocalDate()
        while (true) {
            val cita = d.atTime(hora).atZone(LIMA).toInstant()
            if (d.dayOfWeek.value == a.dia && cita.isAfter(base)) return cita
            d = d.plusDays(1)
        }
    }

    fun estado(): EstadoSemanal {
        val a = ajuste()
        return EstadoSemanal(a.activo, a.dia, a.hora, a.peticion, a.ultima, proxima(a)?.toString(), ultimo(a))
    }

    /** `peticion` = el formulario de «Análisis de competencia»; sin ella se conserva la ya programada. */
    fun programar(actor: Usuario, activo: Boolean?, dia: Int?, hora: String?, peticion: Peticion?): EstadoSemanal {
        if (!actor.esAdmin) throw Prohibido("Solo un administrador puede programar el informe semanal.")
        val antes = ajuste()
        val nuevoActivo = activo ?: antes.activo
        val nuevoDia = dia ?: antes.dia
        val nuevaHora = hora?.trim() ?: antes.hora
        if (nuevoDia !in 1..7) throw ReglaIncumplida("Elige un día de la semana.")
        if (!HORA.matches(nuevaHora)) throw ReglaIncumplida("La hora va como HH:MM, de 00:00 a 23:59.")
        val nuevaPeticion = peticion?.let(analisis::validar) ?: antes.peticion
        if (nuevoActivo && nuevaPeticion == null) throw ReglaIncumplida("Indica primero tus competidores en el formulario.")
        guardar(
            antes.copy(
                activo = nuevoActivo, dia = nuevoDia, hora = nuevaHora, peticion = nuevaPeticion,
                desde = if (nuevoActivo && !antes.activo) Instant.now().toString() else antes.desde,
                reintentos = if (peticion != null) 0 else antes.reintentos,
            ),
        )
        return estado()
    }

    fun ejecutar(actor: Usuario): Analisis {
        if (!actor.esAdmin) throw Prohibido("Solo un administrador puede lanzar el informe semanal.")
        return lanzar()
    }

    private fun lanzar(): Analisis {
        val a = ajuste()
        val base = a.peticion ?: throw ReglaIncumplida("Aún no hay un informe semanal programado.")
        // La ultima se anota antes de crear: si falla, no se reintenta cada 5 minutos.
        guardar(a.copy(ultima = Instant.now().toString()))
        val nuevo = analisis.crear(conPaginasAprendidas(base, a.analisis))
        guardar(ajuste().copy(peticion = nuevo.peticion, analisis = nuevo.codigo, reintentos = 0))
        return nuevo
    }

    /**
     * Lo que la persona eligio la ultima vez (o lo que se identifico sin dudas) pasa a ser la pagina
     * del competidor: la busqueda va directa y no vuelve a preguntar. Un competidor descartado
     * ("" en el avance) sigue sin pagina.
     */
    internal fun conPaginasAprendidas(p: Peticion, codigo: String?): Peticion {
        val previo = codigo?.let { runCatching { repo.avance(it) }.getOrNull() } ?: return p
        val nombres = previo.identificadas.associate { it["page_id"].toString() to it["anunciante"]?.toString().orEmpty() }
        fun aprender(nombre: String, paginas: List<PaginaMeta>): List<PaginaMeta> {
            if (paginas.isNotEmpty()) return paginas
            return previo.paginas[nombre].orEmpty().split(",").map { it.trim() }.filter { ID_PAGINA.matches(it) }
                .map { PaginaMeta(it, nombres[it]?.ifBlank { null } ?: nombre) }
        }
        return p.copy(
            competidores = p.competidores.map { it.copy(paginas = aprender(it.nombre, it.paginas)) },
            marcas = p.marcas.map { it.copy(paginas = aprender(it.nombre, it.paginas)) },
        )
    }

    @Scheduled(fixedDelayString = "PT5M", initialDelayString = "PT3M")
    fun revisar() {
        val a = ajuste()
        if (!a.activo) return
        val previo = ultimo(a)
        if (previo != null && previo.estado == Estado.PAUSADO && previo.pendiente == null && a.reintentos < MAX_REINTENTOS &&
            previo.modificado.isBefore(Instant.now().minus(REINTENTO))
        ) {
            log.info("Informe semanal: reintento {} de {} ({})", a.reintentos + 1, MAX_REINTENTOS, previo.codigo)
            guardar(a.copy(reintentos = a.reintentos + 1))
            runCatching { analisis.continuar(previo.codigo) }.onFailure { log.warn("Informe semanal: {}", it.message) }
            return
        }
        val cita = proxima(a) ?: return
        // Si la de la semana pasada sigue corriendo, espera a que acabe.
        if (Instant.now().isBefore(cita) || previo?.estado?.activo == true) return
        log.info("Informe semanal: toca (cita {})", cita)
        runCatching { lanzar() }.onFailure { log.warn("Informe semanal: {}", it.message) }
    }

    private companion object {
        const val CLAVE = "analisis_semanal"
        const val MAX_REINTENTOS = 4
        val REINTENTO: Duration = Duration.ofHours(3)
        val HORA = Regex("""^([01]\d|2[0-3]):[0-5]\d$""")
        val ID_PAGINA = Regex("\\d{5,25}")
        val LIMA: ZoneId = ZoneId.of("America/Lima")
    }
}
