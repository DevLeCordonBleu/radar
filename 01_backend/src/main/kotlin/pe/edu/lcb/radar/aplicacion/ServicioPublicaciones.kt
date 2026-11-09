package pe.edu.lcb.radar.aplicacion

import org.springframework.stereotype.Service
import pe.edu.lcb.radar.config.Ajustes
import pe.edu.lcb.radar.dominio.Json
import pe.edu.lcb.radar.dominio.NoEncontrado
import pe.edu.lcb.radar.dominio.Prohibido
import pe.edu.lcb.radar.dominio.ReglaIncumplida
import pe.edu.lcb.radar.dominio.Usuario
import pe.edu.lcb.radar.infraestructura.CambioPublicacion
import pe.edu.lcb.radar.infraestructura.ClienteWorker
import pe.edu.lcb.radar.infraestructura.ErrorDelWorker
import pe.edu.lcb.radar.infraestructura.EventoPublicacion
import pe.edu.lcb.radar.infraestructura.VerificacionEnlace
import pe.edu.lcb.radar.infraestructura.FlyerPublicacion
import pe.edu.lcb.radar.infraestructura.Publicacion
import pe.edu.lcb.radar.infraestructura.RepositorioAjustes
import pe.edu.lcb.radar.infraestructura.RepositorioConsumo
import pe.edu.lcb.radar.infraestructura.RepositorioPublicaciones
import tools.jackson.databind.ObjectMapper
import java.io.InputStream
import java.net.URI
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths
import java.nio.file.StandardCopyOption
import java.time.Instant
import java.util.Base64

/**
 * Publicaciones en Facebook, Instagram y LinkedIn: tema -> texto (uno por red o el mismo para
 * todas, Gemini) -> flyer (fondo de foto gratuita, IA o propia + titulo, detalle, llamada a la
 * accion y logo puestos por el Radar) -> hashtags (los del rubro + los del tema) -> aprobacion de
 * un administrador -> publicar.
 *
 * Por ahora se publica a mano (copiar el texto y bajar el archivo) y aqui se registra el enlace
 * de cada red; el envio automatico por n8n llegara despues, y solo para lo aprobado. Una vez
 * publicada en alguna red ya no se edita: lo publicado y lo guardado no deben diferir.
 *
 * Biblioteca: nada se borra (se archiva) y cada paso queda en `publicacion_evento` con su autor,
 * incluido el texto exacto publicado en cada red y cada comprobacion de si el post sigue activo.
 */
@Service
class ServicioPublicaciones(
    private val repo: RepositorioPublicaciones,
    private val worker: ClienteWorker,
    private val consumo: RepositorioConsumo,
    private val videos: ServicioVideos,
    private val seo: ServicioSeo,
    private val ajustes: RepositorioAjustes,
    private val config: Ajustes,
    private val json: ObjectMapper,
) {
    /** Lo comun a todos los flyers y posts: colores, hashtags del rubro y si hay logo. */
    data class Marca(
        val color: String = COLOR,
        val acento: String = ACENTO,
        val hashtags: List<String> = HASHTAGS_BASE,
        val tieneLogo: Boolean = false,
        /** La web propia: sus enlaces llevan UTM en Facebook y LinkedIn (solo se lee). */
        val dominios: List<String> = emptyList(),
    )

    fun listar(archivadas: Boolean = false): List<Publicacion> = repo.todas(archivadas)

    fun historial(codigo: String): List<EventoPublicacion> {
        repo.buscar(codigo)
        return repo.eventos(codigo)
    }

    private fun evento(codigo: String, actor: Usuario?, evento: String, detalle: String, datos: Map<String, Any?>? = null) =
        repo.evento(codigo, evento, detalle, datos, actor?.codigo)

    fun obtener(codigo: String): Publicacion = repo.buscar(codigo)

    fun crear(actor: Usuario, idea: String, redes: List<String>, modoCopy: String = POR_RED): Publicacion {
        val i = idea.trim()
        if (i.length !in 3..1000) throw ReglaIncumplida("Describe la idea en 3 a 1000 caracteres.")
        val codigo = repo.crear(i, validarRedes(redes), actor.codigo, modoCopy = validarModo(modoCopy))
        evento(codigo, actor, "CREADA", "Creada con el tema «${i.take(120)}».", mapOf("redes" to redes, "modoCopy" to modoCopy))
        return repo.buscar(codigo)
    }

    fun guardar(actor: Usuario?, codigo: String, c: CambioPublicacion): Publicacion {
        val p = editable(codigo)
        val idea = c.idea?.trim()
        if (idea != null && idea.length !in 3..1000) throw ReglaIncumplida("Describe la idea en 3 a 1000 caracteres.")
        val limpio = CambioPublicacion(
            titulo = c.titulo?.trim()?.take(60)?.ifEmpty { null },
            idea = idea,
            redes = c.redes?.let { validarRedes(it) },
            textos = c.textos?.filterKeys { it in REDES }?.mapValues { (red, t) -> t.trim().take(LIMITES.getValue(red)) },
            hashtags = c.hashtags?.let { limpiarHashtags(it) },
            modoCopy = c.modoCopy?.let { validarModo(it) },
        )
        repo.cambiar(codigo, limpio)
        c.flyer?.let { nf ->
            val f = p.flyer.copy(
                titulo = nf.titulo.trim().take(80), detalle = nf.detalle.trim().take(120), cta = nf.cta.trim().take(30),
                busqueda = nf.busqueda.trim().take(60), descripcion = nf.descripcion.trim().take(1000),
            )
            if (f != p.flyer) {
                repo.guardarFlyer(codigo, f)
                // El flyer en uso se rehace con los textos nuevos: la imagen y lo guardado no deben diferir.
                if (f.enUso && f.tieneFondo && f.titulo.isNotBlank()) componer(codigo)
            }
        }
        val nueva = repo.buscar(codigo)
        if (contenido(nueva) != contenido(p)) {
            val que = listOfNotNull(
                "el título".takeIf { nueva.titulo != p.titulo }, "el tema".takeIf { nueva.idea != p.idea }, "las redes".takeIf { nueva.redes != p.redes },
                "los textos".takeIf { nueva.textos != p.textos }, "los hashtags".takeIf { nueva.hashtags != p.hashtags },
                "el flyer".takeIf { nueva.flyer.titulo != p.flyer.titulo || nueva.flyer.detalle != p.flyer.detalle || nueva.flyer.cta != p.flyer.cta },
            )
            evento(codigo, actor, "EDITADA", "Cambió ${que.joinToString(", ")}." + if (p.estado == APROBADA) " Vuelve a borrador." else "",
                mapOf("textos" to nueva.textos, "hashtags" to nueva.hashtags))
            if (p.estado == APROBADA) repo.estado(codigo, BORRADOR)
        }
        return repo.buscar(codigo)
    }

    /** Gemini escribe (o reescribe) los textos de las redes, los hashtags y los textos del flyer. */
    @Suppress("UNCHECKED_CAST")
    fun redactar(actor: Usuario?, codigo: String): Publicacion {
        val p = editable(codigo)
        val r = worker.post(
            "/publicaciones/textos",
            mapOf(
                "idea" to p.idea, "redes" to p.redes, "media" to p.media, "modo" to p.modoCopy, "hashtags_base" to marca().hashtags,
                "contexto" to mapOf("negocio" to seo.negocio(), "rubro" to seo.rubro().descripcion, "datos" to videos.contexto().datos),
            ),
        )
        (r["uso"] as? Map<*, *>)?.let { consumo.registrar(codigo, "publicacion_textos", it) }
        val nuevos = (r["textos"] as? Map<String, Any?>).orEmpty().mapValues { it.value?.toString().orEmpty() }
        repo.cambiar(
            codigo,
            CambioPublicacion(
                titulo = (r["titulo"] as? String)?.ifBlank { null }, textos = p.textos + nuevos,
                hashtags = limpiarHashtags((r["hashtags"] as? List<*>).orEmpty().map { it.toString() }),
            ),
        )
        (r["flyer"] as? Map<*, *>)?.let { m ->
            fun t(k: String) = m[k]?.toString().orEmpty()
            val f = p.flyer.copy(titulo = t("titulo"), detalle = t("detalle"), cta = t("cta"), busqueda = t("busqueda"), descripcion = t("fondo"))
            repo.guardarFlyer(codigo, f)
            if (f.enUso && f.tieneFondo && f.titulo.isNotBlank()) componer(codigo)
        }
        if (p.estado == APROBADA) repo.estado(codigo, BORRADOR)
        val n = repo.buscar(codigo)
        evento(codigo, actor, "TEXTOS", "La IA escribió ${if (n.modoCopy == MISMO) "el texto para todas las redes" else "un texto para cada red"}, los hashtags y los textos del flyer.",
            mapOf("textos" to n.textos, "hashtags" to n.hashtags))
        return n
    }

    // ── Imagen o video propios ──

    /** Imagen JPG o PNG (hasta 8 MB, el limite de Instagram) o video MP4 (hasta 100 MB). Reemplaza la anterior. */
    fun subir(actor: Usuario?, codigo: String, datos: InputStream): Publicacion {
        val p = editable(codigo)
        val carpeta = carpeta()
        val temporal = Files.createTempFile(carpeta, "subida-", ".tmp")
        try {
            Files.copy(datos, temporal, StandardCopyOption.REPLACE_EXISTING)
            val (media, tipo, extension) = detectar(Files.newInputStream(temporal).use { it.readNBytes(12) })
                ?: throw ReglaIncumplida("Sube una imagen JPG o PNG, o un video MP4.")
            val tamano = Files.size(temporal)
            if (media == IMAGEN && tamano > MAX_IMAGEN) throw ReglaIncumplida("La imagen pasa de 8 MB, el máximo de Instagram. Redúcela y vuelve a subirla.")
            val destino = carpeta.resolve("$codigo.$extension")
            repo.archivo(codigo)?.let { anterior -> if (Paths.get(anterior) != destino) runCatching { Files.deleteIfExists(Paths.get(anterior)) } }
            Files.move(temporal, destino, StandardCopyOption.REPLACE_EXISTING)
            repo.media(codigo, media, destino.toAbsolutePath().toString(), tipo)
        } finally {
            Files.deleteIfExists(temporal)
        }
        if (p.flyer.enUso) repo.guardarFlyer(codigo, p.flyer.copy(enUso = false))
        if (p.estado == APROBADA) repo.estado(codigo, BORRADOR)
        val n = repo.buscar(codigo)
        evento(codigo, actor, "ARCHIVO", "Subió ${if (n.media == VIDEO) "un video propio" else "una imagen propia"} (${n.archivoTipo}).")
        return n
    }

    fun quitarArchivo(actor: Usuario?, codigo: String): Publicacion {
        val p = editable(codigo)
        repo.archivo(codigo)?.let { runCatching { Files.deleteIfExists(Paths.get(it)) } }
        repo.media(codigo, NINGUNA, null, null)
        if (p.flyer.enUso) repo.guardarFlyer(codigo, p.flyer.copy(enUso = false))
        if (p.estado == APROBADA) repo.estado(codigo, BORRADOR)
        evento(codigo, actor, "ARCHIVO", "Quitó la imagen o el video.")
        return repo.buscar(codigo)
    }

    /** La ruta y su tipo (image/jpeg, image/png, video/mp4). */
    fun archivo(codigo: String): Pair<Path, String> {
        val p = repo.buscar(codigo)
        val ruta = repo.archivo(codigo)?.let { Paths.get(it) }
        if (ruta == null || p.archivoTipo == null || !Files.exists(ruta)) throw NoEncontrado("Esta publicación no tiene imagen ni video.")
        return ruta to p.archivoTipo
    }

    // ── Flyer ──

    /** Fotos verticales del banco gratuito (Pixabay o Pexels) para el fondo. */
    fun buscarFotos(consulta: String, pagina: Int): Json {
        val c = consulta.trim()
        if (c.length < 2) throw ReglaIncumplida("Escribe qué foto buscar (al menos 2 letras).")
        return worker.post("/imagenes/buscar", mapOf("consulta" to c.take(100), "pagina" to pagina.coerceIn(1, 50), "orientacion" to "vertical"))
    }

    fun fondoFoto(actor: Usuario?, codigo: String, id: Long): Publicacion {
        val p = editable(codigo).also { evento(codigo, actor, "FONDO", "Eligió una foto gratuita (id $id) de fondo.") }
        val f = worker.post("/imagenes/foto", mapOf("id" to id))
        val banco = (f["fuente"] as? String ?: "PIXABAY").lowercase().replaceFirstChar { it.uppercase() }
        val autor = (f["autor"] as? String)?.ifBlank { null }
        return guardarFondo(p, base64(f), banco.uppercase(), autor?.let { "Foto: $it en $banco" } ?: "Foto de $banco", f["pagina_url"] as? String)
    }

    /** Gemini no tiene plan gratuito de imagenes: sin facturacion el worker lo explica y no se guarda nada. */
    fun fondoIa(actor: Usuario?, codigo: String, descripcion: String?): Publicacion {
        val p = editable(codigo)
        val d = (descripcion?.trim()?.ifEmpty { null } ?: p.flyer.descripcion.ifBlank { p.idea }).take(1000)
        if (d.length < 5) throw ReglaIncumplida("Describe el fondo en al menos 5 caracteres.")
        val r = worker.post(
            "/imagenes/generar",
            mapOf("descripcion" to d, "negocio" to seo.negocio(), "rubro" to seo.rubro().descripcion, "formato" to "VERTICAL"),
        )
        (r["uso"] as? Map<*, *>)?.let { consumo.registrar(codigo, "publicacion_fondo", it) }
        evento(codigo, actor, "FONDO", "Creó el fondo con IA (de pago).", mapOf("descripcion" to d))
        return guardarFondo(p.copy(flyer = p.flyer.copy(descripcion = d)), base64(r), "IA", "Imagen creada con IA", null)
    }

    /** Una foto propia (JPG o PNG, hasta 8 MB) como fondo: por ejemplo, del campus real. */
    fun fondoPropio(actor: Usuario?, codigo: String, datos: InputStream): Publicacion {
        val p = editable(codigo).also { evento(codigo, actor, "FONDO", "Subió una foto propia de fondo.") }
        val bytes = datos.readNBytes(MAX_IMAGEN.toInt() + 1)
        if (bytes.size > MAX_IMAGEN) throw ReglaIncumplida("La foto pasa de 8 MB. Redúcela y vuelve a subirla.")
        return guardarFondo(p, bytes, "PROPIA", null, null)
    }

    /** Arma el flyer con el fondo, sus textos y la marca, y lo pone como imagen de la publicacion. */
    fun componer(codigo: String): Publicacion {
        val p = editable(codigo)
        val f = p.flyer
        if (!f.tieneFondo) throw ReglaIncumplida("Elige primero un fondo: una foto gratuita, una imagen con IA o una foto propia.")
        if (f.titulo.isBlank()) throw ReglaIncumplida("Escribe el título del flyer.")
        val m = marca()
        val logo = logoRuta().takeIf { Files.exists(it) }?.let { Base64.getEncoder().encodeToString(Files.readAllBytes(it)) }
        val r = worker.post(
            "/publicaciones/flyer",
            mapOf(
                "fondo_b64" to Base64.getEncoder().encodeToString(Files.readAllBytes(fondoRuta(codigo))), "titulo" to f.titulo,
                "detalle" to f.detalle, "cta" to f.cta, "logo_b64" to logo, "color" to m.color, "acento" to m.acento,
            ),
        )
        val destino = carpeta().resolve("$codigo.jpg")
        repo.archivo(codigo)?.let { anterior -> if (Paths.get(anterior) != destino) runCatching { Files.deleteIfExists(Paths.get(anterior)) } }
        Files.write(destino, base64(r))
        repo.media(codigo, IMAGEN, destino.toAbsolutePath().toString(), "image/jpeg")
        repo.guardarFlyer(codigo, f.copy(enUso = true))
        if (p.estado == APROBADA) repo.estado(codigo, BORRADOR)
        evento(codigo, null, "FLYER", "Se armó el flyer «${f.titulo}».", mapOf("titulo" to f.titulo, "detalle" to f.detalle, "cta" to f.cta, "fondo" to f.fondoOrigen))
        return repo.buscar(codigo)
    }

    private fun guardarFondo(p: Publicacion, datos: ByteArray, origen: String, credito: String?, url: String?): Publicacion {
        val tipo = detectar(datos.copyOf(minOf(12, datos.size)))?.takeIf { it.first == IMAGEN }?.second
            ?: tipoWebp(datos) ?: throw ReglaIncumplida("El fondo tiene que ser una imagen JPG o PNG.")
        Files.write(fondoRuta(p.codigo), datos)
        repo.guardarFlyer(p.codigo, p.flyer.copy(fondoOrigen = origen, fondoCredito = credito, fondoUrl = url, fondoTipo = tipo))
        // Con titulo, el flyer se arma al momento; sin el, queda el fondo esperando los textos.
        return if (p.flyer.titulo.isNotBlank()) componer(p.codigo) else repo.buscar(p.codigo)
    }

    // ── Marca ──

    fun marca(): Marca {
        val guardada = ajustes.leer(CLAVE_MARCA)?.let { runCatching { json.readValue(it, Marca::class.java) }.getOrNull() } ?: Marca()
        return guardada.copy(tieneLogo = Files.exists(logoRuta()), dominios = seo.dominiosPropios())
    }

    fun guardarMarca(actor: Usuario, m: Marca): Marca {
        if (!actor.esAdmin) throw Prohibido("Solo un administrador cambia la marca.")
        if (!HEX.matches(m.color) || !HEX.matches(m.acento)) throw ReglaIncumplida("Los colores van en formato #RRGGBB.")
        val limpia = Marca(m.color.uppercase(), m.acento.uppercase(), limpiarHashtags(m.hashtags).take(15))
        // Los dominios no se guardan: salen del sitio propio del Plan SEO.
        ajustes.guardar(CLAVE_MARCA, json.writeValueAsString(limpia))
        return marca()
    }

    /** El logo (PNG con transparencia, mejor; o JPG), hasta 2 MB. */
    fun subirLogo(actor: Usuario, datos: InputStream): Marca {
        if (!actor.esAdmin) throw Prohibido("Solo un administrador cambia el logo.")
        val bytes = datos.readNBytes(MAX_LOGO + 1)
        if (bytes.size > MAX_LOGO) throw ReglaIncumplida("El logo pasa de 2 MB.")
        if (detectar(bytes.copyOf(minOf(12, bytes.size)))?.first != IMAGEN) throw ReglaIncumplida("El logo tiene que ser PNG o JPG.")
        Files.write(logoRuta(), bytes)
        return marca()
    }

    fun quitarLogo(actor: Usuario): Marca {
        if (!actor.esAdmin) throw Prohibido("Solo un administrador cambia el logo.")
        Files.deleteIfExists(logoRuta())
        return marca()
    }

    fun logo(): Pair<Path, String> {
        val ruta = logoRuta()
        if (!Files.exists(ruta)) throw NoEncontrado("Aún no hay logo.")
        val tipo = detectar(Files.newInputStream(ruta).use { it.readNBytes(12) })?.second ?: "image/png"
        return ruta to tipo
    }

    // ── Aprobacion, enlaces y borrado ──

    fun aprobar(actor: Usuario, codigo: String, aprobada: Boolean): Publicacion {
        if (!actor.esAdmin) throw Prohibido("Solo un administrador aprueba una publicación.")
        val p = repo.buscar(codigo)
        if (aprobada) {
            if (p.estado != BORRADOR) throw ReglaIncumplida("Esta publicación ya está aprobada.")
            val faltan = problemas(p)
            if (faltan.isNotEmpty()) throw ReglaIncumplida("Antes de aprobarla: ${faltan.joinToString(" ")}")
            repo.estado(codigo, APROBADA, actor.codigo)
            evento(codigo, actor, "APROBADA", "Aprobada para publicar.", mapOf("textos" to p.textos, "hashtags" to p.hashtags))
        } else {
            if (p.estado != APROBADA) throw ReglaIncumplida("Esta publicación no está aprobada.")
            if (p.enlaces.isNotEmpty()) throw ReglaIncumplida("Ya se publicó en alguna red: no se le quita la aprobación.")
            repo.estado(codigo, BORRADOR)
            evento(codigo, actor, "APROBACION_QUITADA", "Le quitó la aprobación: vuelve a borrador.")
        }
        return repo.buscar(codigo)
    }

    /** Se publico a mano: guarda el enlace de esa red (vacio lo quita). Con todas las redes, queda PUBLICADA. */
    fun registrarEnlace(actor: Usuario?, codigo: String, red: String, url: String): Publicacion {
        val p = repo.buscar(codigo)
        val r = red.uppercase()
        if (p.estado == BORRADOR) throw ReglaIncumplida("Primero tiene que aprobarla un administrador.")
        if (r !in p.redes) throw ReglaIncumplida("Esta publicación no va a ${nombre(r)}.")
        val u = url.trim()
        val enlaces = if (u.isEmpty()) p.enlaces - r else p.enlaces + (r to validarEnlace(r, u))
        repo.enlaces(codigo, enlaces, if (p.redes.all { it in enlaces }) PUBLICADA else APROBADA)
        if (u.isEmpty()) {
            evento(codigo, actor, "ENLACE_QUITADO", "Quitó el enlace de ${nombre(r)}.", mapOf("red" to r, "url" to p.enlaces[r]))
            repo.verificacion(codigo, p.verificacion - r)
        } else {
            // El texto exacto que se publico, para comparar despues con lo que hay en la red.
            evento(codigo, actor, "PUBLICADA", "Publicada en ${nombre(r)}.",
                mapOf("red" to r, "url" to enlaces[r], "texto" to publicado(p, r), "media" to p.media))
        }
        return repo.buscar(codigo)
    }

    /** No se borra nada: queda en la biblioteca, con su imagen o video y su historial. */
    fun archivar(actor: Usuario, codigo: String, archivada: Boolean = true): Publicacion {
        if (!actor.esAdmin) throw Prohibido("Solo un administrador archiva una publicación.")
        val p = repo.buscar(codigo)
        if (p.archivada == archivada) return p
        repo.archivar(codigo, archivada)
        evento(codigo, actor, if (archivada) "ARCHIVADA" else "RESTAURADA", if (archivada) "Archivada: sale de la lista, sigue en la biblioteca." else "Vuelve a la lista.")
        return repo.buscar(codigo)
    }

    /** Abre cada enlace publicado y guarda si sigue en su red (ACTIVA, NO_DISPONIBLE o SIN_CONFIRMAR). */
    @Suppress("UNCHECKED_CAST")
    fun verificar(actor: Usuario?, codigo: String): Publicacion {
        val p = repo.buscar(codigo)
        if (p.enlaces.isEmpty()) throw ReglaIncumplida("Aún no tiene enlaces publicados que comprobar.")
        val textos = p.enlaces.keys.associateWith { p.textos[it].orEmpty() }
        val r = worker.post("/publicaciones/verificar", mapOf("enlaces" to p.enlaces, "textos" to textos))
        val ahora = Instant.now()
        val nuevos = (r["resultados"] as? Map<String, Any?>).orEmpty().mapNotNull { (red, v) ->
            val m = v as? Map<*, *> ?: return@mapNotNull null
            red to VerificacionEnlace(m["estado"]?.toString() ?: SIN_CONFIRMAR, m["detalle"]?.toString().orEmpty(), (m["http"] as? Number)?.toInt(), ahora)
        }.toMap()
        repo.verificacion(codigo, p.verificacion + nuevos)
        nuevos.forEach { (red, v) ->
            evento(codigo, actor, "VERIFICADA", "${nombre(red)}: ${ESTADO_ENLACE[v.estado] ?: v.estado}. ${v.detalle}",
                mapOf("red" to red, "url" to p.enlaces[red], "estado" to v.estado, "http" to v.http))
        }
        return repo.buscar(codigo)
    }

    /** Todas las que tienen algun enlace publicado, archivadas incluidas. -> cuantas por estado. */
    fun verificarTodas(actor: Usuario?): Map<String, Any?> {
        val conEnlaces = repo.todas(archivadas = true).filter { it.enlaces.isNotEmpty() }
        val resultados = conEnlaces.flatMap { p -> runCatching { verificar(actor, p.codigo).verificacion.values.map { it.estado } }.getOrDefault(listOf("ERROR")) }
        return mapOf("publicaciones" to conEnlaces.size, "enlaces" to resultados.size) + resultados.groupingBy { it }.eachCount()
    }

    /** Publicacion de un video aprobado, con sus copys y una copia del MP4. Si ya existe, devuelve esa. */
    fun desdeVideo(actor: Usuario, codVideo: String): Publicacion {
        val v = videos.obtener(codVideo)
        if (v.estado != ServicioVideos.APROBADO) throw ReglaIncumplida("Solo se publica un video aprobado.")
        repo.deVideo(codVideo)?.let { return it }
        val origen = videos.archivo(codVideo)
        val textos = mapOf(FACEBOOK to v.copyFacebook.orEmpty(), INSTAGRAM to v.copyInstagram.orEmpty()).filterValues { it.isNotBlank() }
        val codigo = repo.crear(v.idea, listOf(FACEBOOK, INSTAGRAM), actor.codigo, v.titulo, "VIDEO", codVideo, textos, limpiarHashtags(v.hashtags))
        evento(codigo, actor, "CREADA", "Creada desde el video $codVideo, con sus textos y el MP4.", mapOf("video" to codVideo))
        val destino = carpeta().resolve("$codigo.mp4")
        Files.copy(origen, destino, StandardCopyOption.REPLACE_EXISTING)
        repo.media(codigo, VIDEO, destino.toAbsolutePath().toString(), "video/mp4")
        return repo.buscar(codigo)
    }

    // ── Reglas ──

    /** Lo que impide aprobarla, en frases para mostrar. */
    private fun problemas(p: Publicacion): List<String> {
        val salida = mutableListOf<String>()
        if (p.redes.isEmpty()) salida += "Elige al menos una red."
        for (red in p.redes) {
            val texto = p.textos[red].orEmpty()
            if (texto.isBlank()) salida += "Falta el texto de ${nombre(red)}."
            else if (publicado(p, red).length > LIMITES.getValue(red)) {
                salida += "El texto de ${nombre(red)} con sus hashtags pasa de ${LIMITES.getValue(red)} caracteres."
            }
        }
        if (INSTAGRAM in p.redes && p.media == NINGUNA) salida += "Instagram necesita una imagen o un video."
        val revisar = p.redes.map { p.textos[it].orEmpty() } + if (p.flyer.enUso) listOf(p.flyer.titulo, p.flyer.detalle, p.flyer.cta) else emptyList()
        val faltan = revisar.flatMap { t -> FALTA.findAll(t).map { it.groupValues[1].trim() } }.distinct()
        if (faltan.isNotEmpty()) salida += "Hay datos por completar: ${faltan.joinToString(", ")}."
        return salida
    }

    /** Lo que se pega en la red: texto, hashtags y UTM en los enlaces a la web propia (Facebook y LinkedIn). */
    fun publicado(p: Publicacion, red: String): String =
        Utm.enTexto(textoFinal(p.textos[red].orEmpty(), p.hashtags), red, p.codigo, p.titulo, seo.dominiosPropios())

    private fun editable(codigo: String): Publicacion {
        val p = repo.buscar(codigo)
        if (p.archivada) throw ReglaIncumplida("Está archivada: restáurala para cambiarla.")
        if (p.enlaces.isNotEmpty()) {
            throw ReglaIncumplida("Ya se publicó en ${p.enlaces.keys.joinToString(", ") { nombre(it) }}: no se cambia. Crea otra publicación.")
        }
        return p
    }

    private fun contenido(p: Publicacion) =
        listOf(p.titulo, p.idea, p.redes, p.textos, p.hashtags, p.flyer.titulo, p.flyer.detalle, p.flyer.cta)

    private fun validarRedes(redes: List<String>): List<String> {
        val pedidas = redes.map { it.trim().uppercase() }.toSet()
        val desconocidas = pedidas - REDES.toSet()
        if (desconocidas.isNotEmpty()) throw ReglaIncumplida("Red desconocida: ${desconocidas.joinToString(", ")}. Son Facebook, Instagram y LinkedIn.")
        if (pedidas.isEmpty()) throw ReglaIncumplida("Elige al menos una red.")
        return REDES.filter { it in pedidas }
    }

    private fun validarModo(modo: String): String {
        val m = modo.trim().uppercase()
        if (m !in setOf(POR_RED, MISMO)) throw ReglaIncumplida("El texto es uno por red (POR_RED) o el mismo para todas (MISMO).")
        return m
    }

    private fun validarEnlace(red: String, url: String): String {
        val host = runCatching { URI(url) }.getOrNull()?.takeIf { it.scheme in setOf("http", "https") }?.host?.lowercase()
            ?: throw ReglaIncumplida("Pega el enlace completo de la publicación (empieza con https://).")
        if (DOMINIOS.getValue(red).none { host == it || host.endsWith(".$it") }) {
            throw ReglaIncumplida("Ese enlace no es de ${nombre(red)}.")
        }
        return url
    }

    /** Por el inicio del archivo: no se fia de la extension ni del tipo que manda el navegador. -> (media, tipo, extension) */
    private fun detectar(cabecera: ByteArray): Triple<String, String, String>? {
        fun empieza(vararg b: Int) = cabecera.size >= b.size && b.indices.all { cabecera[it] == b[it].toByte() }
        return when {
            empieza(0xFF, 0xD8, 0xFF) -> Triple(IMAGEN, "image/jpeg", "jpg")
            empieza(0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A) -> Triple(IMAGEN, "image/png", "png")
            cabecera.size >= 8 && String(cabecera, 4, 4, Charsets.US_ASCII) == "ftyp" -> Triple(VIDEO, "video/mp4", "mp4")
            else -> null
        }
    }

    /** Gemini puede devolver WebP: sirve de fondo (el flyer final siempre es JPEG). */
    private fun tipoWebp(d: ByteArray) =
        if (d.size >= 12 && String(d, 0, 4, Charsets.US_ASCII) == "RIFF" && String(d, 8, 4, Charsets.US_ASCII) == "WEBP") "image/webp" else null

    private fun base64(r: Json): ByteArray =
        Base64.getDecoder().decode(r["datos_b64"] as? String ?: throw ErrorDelWorker("El worker no devolvió la imagen."))

    private fun carpeta(): Path = Paths.get(config.datos, "publicaciones").also { Files.createDirectories(it) }

    private fun fondoRuta(codigo: String): Path = carpeta().resolve("$codigo-fondo")

    private fun logoRuta(): Path = carpeta().resolve("marca-logo")

    companion object {
        const val BORRADOR = "BORRADOR"
        const val APROBADA = "APROBADA"
        const val PUBLICADA = "PUBLICADA"
        const val NINGUNA = "NINGUNA"
        const val IMAGEN = "IMAGEN"
        const val VIDEO = "VIDEO"
        const val FACEBOOK = "FACEBOOK"
        const val INSTAGRAM = "INSTAGRAM"
        const val LINKEDIN = "LINKEDIN"
        const val POR_RED = "POR_RED"
        const val SIN_CONFIRMAR = "SIN_CONFIRMAR"
        val ESTADO_ENLACE = mapOf("ACTIVA" to "activa", "NO_DISPONIBLE" to "ya no está disponible", SIN_CONFIRMAR to "sin confirmar")
        const val MISMO = "MISMO"
        val REDES = listOf(FACEBOOK, INSTAGRAM, LINKEDIN)
        /** Lo que admite cada red; Instagram cuenta tambien los hashtags (y como mucho 30). */
        val LIMITES = mapOf(FACEBOOK to 5000, INSTAGRAM to 2200, LINKEDIN to 3000)
        private const val MAX_HASHTAGS = 30
        private const val MAX_IMAGEN = 8L * 1024 * 1024
        private const val MAX_LOGO = 2 * 1024 * 1024
        private const val CLAVE_MARCA = "publicacion_marca"
        // Azul marino y dorado; se cambian en Publicaciones -> Marca.
        const val COLOR = "#0B1F3F"
        const val ACENTO = "#C9A55A"
        val HASHTAGS_BASE = listOf("#LeCordonBleuPeru", "#Gastronomía")
        private val HEX = Regex("^#[0-9A-Fa-f]{6}$")
        private val DOMINIOS = mapOf(
            FACEBOOK to listOf("facebook.com", "fb.com", "fb.watch"),
            INSTAGRAM to listOf("instagram.com"),
            LINKEDIN to listOf("linkedin.com", "lnkd.in"),
        )
        private val FALTA = Regex("""\[FALTA:?\s*([^\]]*)]""", RegexOption.IGNORE_CASE)

        fun nombre(red: String) = when (red) {
            FACEBOOK -> "Facebook"
            INSTAGRAM -> "Instagram"
            LINKEDIN -> "LinkedIn"
            else -> red
        }

        /** Lo que se pega en la red: el texto y, debajo, los hashtags. */
        fun textoFinal(texto: String, hashtags: List<String>) = listOf(texto.trim(), hashtags.joinToString(" ")).filter { it.isNotEmpty() }.joinToString("\n\n")

        fun limpiarHashtags(lista: List<String>) =
            lista.map { "#" + it.trim().trimStart('#') }.filter { it.length > 1 && !it.contains(' ') }.distinct().take(MAX_HASHTAGS)
    }
}
