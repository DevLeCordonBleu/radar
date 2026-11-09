package pe.edu.lcb.radar.aplicacion

import org.slf4j.LoggerFactory
import org.springframework.scheduling.annotation.Scheduled
import org.springframework.stereotype.Service
import pe.edu.lcb.radar.config.Ajustes
import pe.edu.lcb.radar.dominio.Json
import pe.edu.lcb.radar.dominio.NoEncontrado
import pe.edu.lcb.radar.dominio.Prohibido
import pe.edu.lcb.radar.dominio.ReglaIncumplida
import pe.edu.lcb.radar.dominio.Usuario
import pe.edu.lcb.radar.infraestructura.CambioVideo
import pe.edu.lcb.radar.infraestructura.ClienteWorker
import pe.edu.lcb.radar.infraestructura.ErrorDelWorker
import pe.edu.lcb.radar.infraestructura.ParteVideo
import pe.edu.lcb.radar.infraestructura.RepositorioAjustes
import pe.edu.lcb.radar.infraestructura.RepositorioConsumo
import pe.edu.lcb.radar.infraestructura.RepositorioVideos
import pe.edu.lcb.radar.infraestructura.Video
import tools.jackson.databind.ObjectMapper
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths
import java.util.Base64
import kotlin.math.ceil

/**
 * Videos cortos: idea o keyword -> guion por partes de 10 s y copys (Gemini) -> video en Google
 * Vids (un clip y extensiones, para que el personaje y la voz no cambien) -> aprobacion.
 *
 * Vids lo maneja el worker con el Chrome de la persona; aqui solo se lanza, se sigue cada 10 s
 * y se guarda el MP4 en `<datos>/videos`. Un video a la vez: Vids genera de uno en uno y su
 * cupo mensual es corto. Un dialogo con «[FALTA: …]» no se genera (gastaria una generacion en
 * algo que no se puede publicar). Publicar en Facebook e Instagram aun no esta conectado.
 */
@Service
class ServicioVideos(
    private val repo: RepositorioVideos,
    private val worker: ClienteWorker,
    private val consumo: RepositorioConsumo,
    private val ajustes: RepositorioAjustes,
    private val seo: ServicioSeo,
    private val config: Ajustes,
    private val json: ObjectMapper,
) {
    private val log = LoggerFactory.getLogger(javaClass)

    data class Pronunciacion(val texto: String = "", val dice: String = "")

    /** Lo que se repite en todos los videos: lo que se puede afirmar, el protagonista, el lugar y la voz. */
    data class ContextoVideo(
        val datos: String = DATOS,
        val personaje: String = PERSONAJE,
        val estilo: String = ESTILO,
        val voz: String = VOZ,
        val pronunciaciones: List<Pronunciacion> = listOf(Pronunciacion("Le Cordon Bleu", "Le Cordón Blé")),
    )

    fun contexto(): ContextoVideo =
        ajustes.leer(CLAVE_CONTEXTO)?.let { runCatching { json.readValue(it, ContextoVideo::class.java) }.getOrNull() } ?: ContextoVideo()

    fun guardarContexto(actor: Usuario, c: ContextoVideo): ContextoVideo {
        if (!actor.esAdmin) throw Prohibido("Solo un administrador cambia el contexto de los videos.")
        if (c.datos.length > 6000) throw ReglaIncumplida("Los datos confirmados pasan de 6000 caracteres.")
        if (listOf(c.personaje, c.estilo).any { it.length > 600 } || c.voz.length > 200) throw ReglaIncumplida("Personaje y lugar van en 600 caracteres; la voz, en 200.")
        val pron = c.pronunciaciones.map { Pronunciacion(it.texto.trim(), it.dice.trim()) }.filter { it.texto.isNotEmpty() && it.dice.isNotEmpty() }
        if (pron.size > 20 || pron.any { it.texto.length > 80 || it.dice.length > 80 }) throw ReglaIncumplida("Hasta 20 pronunciaciones de 80 caracteres.")
        val limpio = c.copy(datos = c.datos.trim(), personaje = c.personaje.trim(), estilo = c.estilo.trim(), voz = c.voz.trim(), pronunciaciones = pron)
        ajustes.guardar(CLAVE_CONTEXTO, json.writeValueAsString(limpio))
        return limpio
    }

    private fun contextoWorker(): Json {
        val c = contexto()
        return mapOf(
            "negocio" to seo.negocio(), "rubro" to seo.rubro().descripcion, "datos" to c.datos, "personaje" to c.personaje,
            "estilo" to c.estilo, "voz" to c.voz, "pronunciaciones" to c.pronunciaciones,
        )
    }

    // ── Videos ──

    fun listar(): List<Video> = repo.todos()

    fun obtener(codigo: String): Video = repo.buscar(codigo)

    fun crear(actor: Usuario, idea: String, keyword: String?, segundos: Int, formato: String): Video {
        val i = idea.trim()
        if (i.length !in 3..500) throw ReglaIncumplida("Describe la idea en 3 a 500 caracteres.")
        validarFormato(segundos, formato)
        return repo.buscar(repo.crear(i, keyword?.trim()?.take(200)?.ifEmpty { null }, segundos, formato.uppercase(), actor.codigo))
    }

    fun guardar(codigo: String, c: CambioVideo): Video {
        val v = repo.buscar(codigo)
        if (v.estado == GENERANDO) throw ReglaIncumplida("El video se está generando: espera a que termine o cancélalo.")
        c.segundos?.let { validarFormato(it, c.formato ?: v.formato) }
        c.formato?.let { validarFormato(c.segundos ?: v.segundos, it) }
        val partes = c.partes?.map { ParteVideo(it.dialogo.trim().take(400), it.escena.trim().take(300)) }?.filter { it.dialogo.isNotEmpty() }
        if (partes != null && partes.size > MAX_PARTES) throw ReglaIncumplida("Como mucho $MAX_PARTES partes (60 segundos).")
        repo.cambiar(
            codigo,
            c.copy(
                titulo = c.titulo?.trim()?.take(60)?.ifEmpty { null }, formato = c.formato?.uppercase(), partes = partes,
                hashtags = c.hashtags?.map { "#" + it.trim().trimStart('#') }?.filter { it.length > 1 }?.distinct()?.take(10),
            ),
        )
        // Un guion cambiado deja viejo el video: hay que volver a generarlo.
        if (partes != null && partes != v.partes && v.estado in setOf(GENERADO, APROBADO)) repo.estado(codigo, GUION)
        if (v.estado in setOf(IDEA, ERROR) && (partes ?: v.partes).isNotEmpty()) repo.estado(codigo, GUION)
        return repo.buscar(codigo)
    }

    @Suppress("UNCHECKED_CAST")
    fun redactar(codigo: String): Video {
        val v = repo.buscar(codigo)
        if (v.estado == GENERANDO) throw ReglaIncumplida("El video se está generando: espera a que termine o cancélalo.")
        val r = worker.post(
            "/videos/guion",
            mapOf("idea" to v.idea, "keyword" to v.keyword.orEmpty(), "segundos" to v.segundos, "contexto" to contextoWorker()),
        )
        (r["uso"] as? Map<*, *>)?.let { consumo.registrar(codigo, "video_guion", it) }
        val partes = (r["partes"] as? List<Map<*, *>>).orEmpty().map { ParteVideo(it["dialogo"]?.toString().orEmpty(), it["escena"]?.toString().orEmpty()) }
        repo.cambiar(
            codigo,
            CambioVideo(
                titulo = (r["titulo"] as? String)?.ifBlank { null }, partes = partes, copyFacebook = r["copy_facebook"] as? String,
                copyInstagram = r["copy_instagram"] as? String, hashtags = (r["hashtags"] as? List<*>).orEmpty().map { it.toString() },
            ),
        )
        repo.estado(codigo, GUION)
        return repo.buscar(codigo)
    }

    /** Los prompts que el robot escribira en Vids, clip por clip. */
    fun prompts(codigo: String): Json {
        val v = repo.buscar(codigo)
        if (v.partes.isEmpty()) return mapOf("prompts" to emptyList<String>())
        return worker.post("/videos/prompts", mapOf("partes" to v.partes, "formato" to v.formato, "contexto" to contextoWorker()))
    }

    fun generar(codigo: String): Video {
        val v = repo.buscar(codigo)
        if (v.estado == GENERANDO) throw ReglaIncumplida("Este video ya se está generando.")
        if (v.partes.isEmpty()) throw ReglaIncumplida("Primero escribe el guion.")
        val faltan = v.partes.flatMap { FALTA.findAll(it.dialogo).map { m -> m.groupValues[1].trim() } }.distinct()
        if (faltan.isNotEmpty()) throw ReglaIncumplida("El guion tiene datos por completar: ${faltan.joinToString(", ")}. Complétalos antes de gastar generaciones de Vids.")
        if (v.partes.size != partesPara(v.segundos)) {
            throw ReglaIncumplida("Un video de ${v.segundos} s lleva ${partesPara(v.segundos)} partes y el guion tiene ${v.partes.size}: ajústalo o vuelve a escribirlo.")
        }
        if (repo.enEstado(GENERANDO).isNotEmpty()) throw ReglaIncumplida("Ya hay un video generándose en Vids: espera a que termine.")
        val r = worker.post(
            "/videos/vids/lanzar",
            mapOf("titulo" to "Radar ${v.codigo} - ${v.titulo}", "partes" to v.partes, "formato" to v.formato, "segundos" to v.segundos,
                "contexto" to contextoWorker()),
        )
        val trabajo = r["id"]?.toString() ?: throw ErrorDelWorker("El worker no devolvió el trabajo de Vids.")
        repo.estado(codigo, GENERANDO, avance = "Abriendo Vids…", trabajo = trabajo)
        return repo.buscar(codigo)
    }

    fun cancelar(codigo: String): Video {
        val v = repo.buscar(codigo)
        if (v.estado != GENERANDO) throw ReglaIncumplida("Este video no se está generando.")
        v.trabajo?.let { runCatching { worker.post("/videos/vids/abortar", mapOf("id" to it)) } }
        repo.estado(codigo, GUION, error = "Cancelado. Lo ya generado queda en tu Vids, pero no en el Radar.")
        return repo.buscar(codigo)
    }

    fun aprobar(actor: Usuario, codigo: String, aprobado: Boolean): Video {
        if (!actor.esAdmin) throw Prohibido("Solo un administrador aprueba un video.")
        val v = repo.buscar(codigo)
        if (aprobado && v.estado != GENERADO) throw ReglaIncumplida("Solo se aprueba un video ya generado.")
        if (!aprobado && v.estado != APROBADO) throw ReglaIncumplida("Este video no está aprobado.")
        repo.estado(codigo, if (aprobado) APROBADO else GENERADO)
        return repo.buscar(codigo)
    }

    fun borrar(actor: Usuario, codigo: String) {
        if (!actor.esAdmin) throw Prohibido("Solo un administrador borra un video.")
        val v = repo.buscar(codigo)
        if (v.estado == GENERANDO) throw ReglaIncumplida("Cancela la generación antes de borrarlo.")
        repo.archivo(codigo)?.let { runCatching { Files.deleteIfExists(Paths.get(it)) } }
        repo.borrar(codigo)
    }

    fun archivo(codigo: String): Path {
        val ruta = repo.archivo(codigo)?.let { Paths.get(it) }
        if (ruta == null || !Files.exists(ruta)) throw NoEncontrado("Este video aún no tiene archivo.")
        return ruta
    }

    fun navegador(): Json = worker.get("/videos/vids/navegador")

    fun abrirNavegador(): Json = worker.post("/videos/vids/abrir", emptyMap<String, Any>())

    /** Sigue el trabajo de Vids: avance, archivo al terminar, o el error tal cual. */
    @Scheduled(fixedDelayString = "PT10S", initialDelayString = "PT20S")
    fun revisar() {
        for (v in repo.enEstado(GENERANDO)) {
            val trabajo = v.trabajo ?: continue
            val r = try {
                worker.post("/videos/vids/consultar", mapOf("id" to trabajo))
            } catch (e: ErrorDelWorker) {
                log.warn("Videos: no se pudo consultar {}: {}", v.codigo, e.message)
                continue
            }
            when (r["estado"]) {
                "corriendo" -> repo.avance(v.codigo, r["mensaje"]?.toString() ?: "Generando…")
                "listo" -> runCatching { guardarArchivo(v, trabajo) }.onFailure { e ->
                    repo.estado(v.codigo, ERROR, error = "Vids terminó, pero no se pudo guardar el video: ${e.message}")
                }
                "cancelado" -> repo.estado(v.codigo, GUION, error = "Cancelado.")
                "desconocido" -> repo.estado(v.codigo, ERROR, error = "El worker se reinició durante la generación. Revisa tu Vids: lo ya generado está allí.")
                else -> repo.estado(v.codigo, ERROR, error = r["error"]?.toString() ?: "Vids no pudo generar el video.")
            }
        }
    }

    private fun guardarArchivo(v: Video, trabajo: String) {
        val r = worker.post("/videos/vids/archivo", mapOf("id" to trabajo))
        val datos = Base64.getDecoder().decode(r["datos_b64"] as? String ?: throw ErrorDelWorker("El worker no devolvió el video."))
        val carpeta = Paths.get(config.datos, "videos").also { Files.createDirectories(it) }
        val ruta = carpeta.resolve("${v.codigo}.mp4")
        Files.write(ruta, datos)
        repo.terminado(v.codigo, ruta.toAbsolutePath().toString(), (r["segundos"] as? Number)?.toDouble(), r["url"] as? String)
        log.info("Video {} listo ({} bytes)", v.codigo, datos.size)
    }

    private fun validarFormato(segundos: Int, formato: String) {
        if (segundos !in 10..60) throw ReglaIncumplida("La duración va de 10 a 60 segundos.")
        if (formato.uppercase() !in setOf("VERTICAL", "HORIZONTAL")) throw ReglaIncumplida("El formato es vertical u horizontal.")
    }

    private fun partesPara(segundos: Int) = ceil(segundos / 10.0).toInt()

    companion object {
        const val IDEA = "IDEA"
        const val GUION = "GUION"
        const val GENERANDO = "GENERANDO"
        const val GENERADO = "GENERADO"
        const val APROBADO = "APROBADO"
        const val ERROR = "ERROR"
        const val MAX_PARTES = 6
        private const val CLAVE_CONTEXTO = "video_contexto"
        private val FALTA = Regex("""\[FALTA:?\s*([^\]]*)]""", RegexOption.IGNORE_CASE)

        // Por defecto, lo de la hoja «Datos confirmados» del plan de contenido de Marketing (oct. 2026).
        val DATOS = """
            Lema: Tu estándar es el mundo
            Frase de propuesta: Estudia en Lima, trabaja en cualquier parte del mundo
            Admisión abierta: Inscripciones abiertas 2027-1
            Programas: Gastronomía, Cocina, Pastelería, Panadería (carrera nueva), Bar y Coctelería, Hostelería y Restaurantes
            Posgrado y especialización: Master Cuisine, Master Patisserie, Diploma en Gastronomía Peruana
            Duración de Cocina: 2 años
        """.trimIndent()
        const val PERSONAJE = "Un chef peruano de unos 40 años, cabello negro corto, sonrisa cálida y chaqueta blanca de chef impecable, en plano medio"
        const val ESTILO = "Cocina profesional moderna y bien iluminada de una escuela de gastronomía en Lima, con alumnos con gorro de chef trabajando al fondo. Luz cálida"
        const val VOZ = "en español con acento peruano, con tono cercano y entusiasta"
    }
}
