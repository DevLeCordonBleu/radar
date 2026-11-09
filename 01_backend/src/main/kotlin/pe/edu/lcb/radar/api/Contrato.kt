package pe.edu.lcb.radar.api

import pe.edu.lcb.radar.aplicacion.ServicioAnalisisSemanal
import pe.edu.lcb.radar.dominio.Analisis
import pe.edu.lcb.radar.dominio.Json
import pe.edu.lcb.radar.dominio.Pendiente
import pe.edu.lcb.radar.dominio.Peticion
import java.time.Instant

/**
 * Contrato HTTP con el panel. Todo cuelga de /api. Los errores salen como
 * { "error": "mensaje para mostrar tal cual" }.
 */
data class RespuestaError(val error: String)

/** `pageIds` (varias paginas del mismo competidor); `pageId` se acepta por compatibilidad. "" o [] = ninguna. */
data class PeticionEleccion(val competidor: String, val pageId: String? = null, val pageIds: List<String>? = null)

data class PeticionArchivar(val archivado: Boolean)

data class AnalisisDto(
    val codigo: String,
    val peticion: Peticion,
    val estado: String,
    val fase: String,
    val mensaje: String,
    val hechos: Int,
    val total: Int,
    val error: String?,
    val pendiente: Pendiente?,
    val codInforme: String?,
    val creado: Instant,
    val modificado: Instant,
)

fun Analisis.dto() = AnalisisDto(
    codigo, peticion, estado.clave, fase.clave, mensaje, hechos, total, error, pendiente, codInforme, creado, modificado,
)

/** Programar el informe semanal. Lo que no viene se conserva; `peticion` = el formulario de «Análisis de competencia». */
data class PeticionSemanal(val activo: Boolean? = null, val dia: Int? = null, val hora: String? = null, val peticion: Peticion? = null)

data class SemanalDto(
    val activo: Boolean,
    val dia: Int,
    val hora: String,
    val peticion: Peticion?,
    val ultima: String?,
    val proxima: String?,
    /** El analisis de la ultima ejecucion (su estado y su informe). */
    val analisis: AnalisisDto?,
)

fun ServicioAnalisisSemanal.EstadoSemanal.dto() = SemanalDto(activo, dia, hora, peticion, ultima, proxima, analisis?.dto())

data class SistemaDto(val worker: Json?, val costoMesUsd: Double)
