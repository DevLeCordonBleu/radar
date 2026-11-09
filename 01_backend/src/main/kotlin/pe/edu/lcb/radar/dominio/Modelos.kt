package pe.edu.lcb.radar.dominio

import java.time.Instant

typealias Json = Map<String, Any?>

/** Estado de un analisis. Un analisis pausado conserva todo lo hecho y se puede continuar. */
enum class Estado(val clave: String) {
    EN_COLA("en_cola"),
    CORRIENDO("corriendo"),
    PAUSADO("pausado"),
    TERMINADO("terminado"),
    CANCELADO("cancelado");

    val activo: Boolean get() = this == EN_COLA || this == CORRIENDO

    companion object {
        fun de(clave: String) = entries.firstOrNull { it.clave == clave }
            ?: throw ReglaIncumplida("Estado desconocido: $clave")
    }
}

enum class Fase(val clave: String) {
    BUSCANDO("buscando"),
    CLASIFICANDO("clasificando"),
    TERRITORIOS("territorios"),
    INFORME("informe");

    companion object {
        fun de(clave: String) = entries.firstOrNull { it.clave == clave } ?: BUSCANDO
    }
}

/**
 * Un competidor a vigilar. `nivel` (1-4) dice cuanto pesa: 1 es directo, 4 nacional.
 * `paginas`: sus paginas de Facebook elegidas al configurarlo (sugerencias de Meta);
 * con ellas se busca por pagina y no hace falta adivinar cual es.
 */
data class Competidor(val nombre: String, val nivel: Int = 3, val paginas: List<PaginaMeta> = emptyList())

/**
 * Tu marca, con sus paginas de Facebook elegidas al configurarla. Es opcional: si
 * se indica, sus anuncios se buscan y el informe reconoce los tuyos por esas paginas.
 */
data class Marca(val nombre: String, val paginas: List<PaginaMeta> = emptyList())

/** Una pagina de Facebook elegida para un competidor. Lo que no sea `pageId` es solo para mostrarla. */
data class PaginaMeta(
    val pageId: String,
    val nombre: String,
    val avatar: String? = null,
    val categoria: String? = null,
    val seguidores: Long? = null,
)

data class Peticion(
    /** Nombres de tus marcas (lo que muestra el informe). Las peticiones antiguas solo traen esto. */
    val misMarcas: List<String> = emptyList(),
    val marcas: List<Marca> = emptyList(),
    val competidores: List<Competidor> = emptyList(),
    /** Busquedas por palabras para ver el mercado mas alla de los competidores nombrados. */
    val keywords: List<String> = emptyList(),
    /** Negocios del sector: Gemini decide con ellos si un anuncio es relevante. */
    val referencia: List<String> = emptyList(),
    val pais: String = "PE",
    val maximo: Int = 100,
    val soloActivos: Boolean = true,
    /** false = clasificar solo por texto (mas barato y rapido, menos preciso). */
    val conMedios: Boolean = true,
    /**
     * AAAA-MM-DD: los anuncios que empezaron antes y ya no estan activos no se cargan. Los que
     * siguen activos se quedan aunque sean anteriores: son de hoy (y los veteranos son la senal).
     */
    val fechaMinima: String? = null,
)

/**
 * Una pagina de Meta que podria ser el competidor buscado, con lo necesario para
 * reconocerla: foto de perfil, hasta 3 imagenes de sus anuncios y un texto.
 */
data class Candidato(
    val pageId: String,
    val nombre: String,
    val anuncios: Int,
    val muestra: String? = null,
    val avatar: String? = null,
    val ejemplos: List<String> = emptyList(),
    val texto: String? = null,
)

/** Decision que el analisis espera de la persona antes de seguir. */
data class Pendiente(
    val tipo: String,
    val competidor: String,
    val candidatos: List<Candidato>,
)

/**
 * Checkpoint reanudable. Se guarda tras cada lote: si algo se corta, "continuar"
 * retoma exactamente aqui sin repetir la busqueda ni volver a pagar lo clasificado.
 */
data class Avance(
    /** Anuncios tal como salieron de Apify, antes de saber a que competidor pertenecen. */
    val brutos: List<Json> = emptyList(),
    val buscado: Boolean = false,
    /** competidor -> page_id elegido; "" = descartado por la persona. */
    val paginas: Map<String, String> = emptyMap(),
    /** Anuncios unicos ya con su nivel: lo que se clasifica. */
    val anuncios: List<Json> = emptyList(),
    val identificados: Boolean = false,
    val identificadas: List<Json> = emptyList(),
    val sinAnuncios: List<String> = emptyList(),
    val clasificadas: Map<String, Json> = emptyMap(),
    val territorios: List<Json>? = null,
)

data class Analisis(
    val codigo: String,
    val peticion: Peticion,
    val estado: Estado,
    val fase: Fase,
    val mensaje: String,
    val hechos: Int,
    val total: Int,
    val error: String?,
    val pendiente: Pendiente?,
    val codInforme: String?,
    val creado: Instant,
    val modificado: Instant,
)

data class InformeFila(
    val codigo: String,
    val marca: String,
    val anuncios: Int,
    val anunciantes: Int,
    val portada: Json?,
    val esEjemplo: Boolean,
    val archivado: Boolean,
    val creado: Instant,
)

class ReglaIncumplida(mensaje: String) : RuntimeException(mensaje)

class NoEncontrado(mensaje: String) : RuntimeException(mensaje)

/** Una cuenta del equipo. `hash`, `sal` y `iteraciones` nunca salen del backend. */
data class Usuario(
    val id: Long,
    val codigo: String,
    val email: String,
    val nombre: String,
    /** "admin" gestiona usuarios y ajustes; "miembro" analiza y lee informes. */
    val rol: String,
    val activo: Boolean,
    val debeCambiar: Boolean,
    val tieneRecuperacion: Boolean,
    val ultimoAcceso: Instant?,
    val creado: Instant,
    val hash: String,
    val sal: String,
    val iteraciones: Int,
    val fallos: Int,
    val bloqueadoHasta: Long,
) {
    val esAdmin: Boolean get() = rol == "admin"
}

/** Falta iniciar sesion, o la sesion caduco. */
class NoAutenticado(mensaje: String = "Inicia sesión para continuar.") : RuntimeException(mensaje)

/** Hay sesion, pero este usuario no puede hacer esto. */
class Prohibido(mensaje: String) : RuntimeException(mensaje)
