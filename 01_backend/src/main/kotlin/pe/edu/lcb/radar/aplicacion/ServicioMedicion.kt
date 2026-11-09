package pe.edu.lcb.radar.aplicacion

import org.slf4j.LoggerFactory
import org.springframework.scheduling.annotation.Scheduled
import org.springframework.stereotype.Service
import pe.edu.lcb.radar.dominio.Json
import pe.edu.lcb.radar.dominio.ReglaIncumplida
import pe.edu.lcb.radar.dominio.Usuario
import pe.edu.lcb.radar.infraestructura.ClienteWorker
import pe.edu.lcb.radar.infraestructura.ErrorDelWorker
import pe.edu.lcb.radar.infraestructura.FilaMeta
import pe.edu.lcb.radar.infraestructura.InformeGuardado
import pe.edu.lcb.radar.infraestructura.RepositorioAjustes
import pe.edu.lcb.radar.infraestructura.RepositorioConsumo
import pe.edu.lcb.radar.infraestructura.RepositorioInformesGuardados
import pe.edu.lcb.radar.infraestructura.RepositorioMedicion
import tools.jackson.databind.ObjectMapper
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.temporal.ChronoUnit
import java.util.concurrent.Executors

/**
 * Medicion: que funciona. El rendimiento diario de los anuncios propios de Meta (solo lectura,
 * con el token de Marketing) se guarda en `meta_insight`; de ahi salen las cifras del periodo
 * frente al anterior, por campana y por anuncio, y alertas calculadas sin IA. La IA solo
 * redacta el resumen con esas cifras, y cada resumen queda como informe guardado (MEDICION).
 * GA4 (lo que pasa en la web despues del clic) se consulta al momento.
 *
 * Leads (formularios) y conversaciones (WhatsApp) son resultados distintos: cada campana se
 * clasifica por el que produce y su costo por resultado se calcula con su propio gasto.
 */
@Service
class ServicioMedicion(
    private val repo: RepositorioMedicion,
    private val worker: ClienteWorker,
    private val ajustes: RepositorioAjustes,
    private val informes: RepositorioInformesGuardados,
    private val consumo: RepositorioConsumo,
    private val seo: ServicioSeo,
    private val json: ObjectMapper,
) {
    private val log = LoggerFactory.getLogger(javaClass)
    private val cola = Executors.newSingleThreadExecutor { r -> Thread(r, "cola-medicion").apply { isDaemon = true } }

    /** La sincronizacion en marcha o la ultima (en memoria; la ultima buena tambien en ajustes). */
    @Volatile private var tarea: Map<String, Any?>? = null

    // ── Estado ──

    fun estado(): Map<String, Any?> {
        val meta = runCatching { worker.get("/medicion/meta") }.getOrElse { mapOf("completo" to false, "faltan" to emptyList<String>(), "error" to it.message) }
        val ga4 = runCatching { worker.get("/medicion/ga4") }.getOrElse { mapOf("completo" to false, "faltan" to emptyList<String>(), "error" to it.message) }
        val rango = repo.rango()
        return mapOf(
            "meta" to meta, "ga4" to ga4, "sincronizacion" to (tarea ?: ultimaSincronizacion()),
            "datos" to rango?.let { mapOf("desde" to it.first, "hasta" to it.second, "filas" to it.third) },
            "hoy" to hoy().toString(),
        )
    }

    private fun ultimaSincronizacion(): Map<*, *>? = ajustes.leer(CLAVE_SYNC)?.let { runCatching { json.readValue(it, Map::class.java) }.getOrNull() }

    // ── Sincronizacion (en segundo plano: 90 dias tardan unos 3 minutos) ──

    /**
     * Trae de Meta desde `desde` (o, si no se pide: 90 dias la primera vez y luego desde 7 dias
     * antes de lo ultimo guardado, porque Meta corrige la atribucion) hasta hoy.
     */
    @Synchronized
    fun sincronizar(actor: Usuario?, desde: String? = null): Map<String, Any?> {
        if (tarea?.get("estado") == EN_CURSO) throw ReglaIncumplida("Ya se están trayendo los datos de Meta: espera a que termine.")
        val hasta = hoy()
        val inicio = desde?.let {
            runCatching { LocalDate.parse(it) }.getOrNull() ?: throw ReglaIncumplida("La fecha va como AAAA-MM-DD.")
        } ?: repo.rango()?.second?.let { LocalDate.parse(it).minusDays(DIAS_REVISAR) } ?: hasta.minusDays(DIAS_INICIALES - 1)
        if (inicio.isAfter(hasta)) throw ReglaIncumplida("La fecha inicial no puede ser futura.")
        if (ChronoUnit.DAYS.between(inicio, hasta) > MAX_DIAS) throw ReglaIncumplida("Como mucho $MAX_DIAS días de historial por vez.")
        val t = mapOf("estado" to EN_CURSO, "desde" to inicio.toString(), "hasta" to hasta.toString(), "inicio" to Instant.now().toString(),
            "autor" to actor?.codigo)
        tarea = t
        cola.submit {
            tarea = try {
                val r = worker.post("/medicion/meta/insights", mapOf("desde" to inicio.toString(), "hasta" to hasta.toString()))
                val filas = (r["filas"] as? List<*>).orEmpty().filterIsInstance<Map<*, *>>().mapNotNull(::fila)
                repo.reemplazar(inicio.toString(), hasta.toString(), filas)
                val hecha = t + mapOf("estado" to LISTA, "fin" to Instant.now().toString(), "filas" to filas.size)
                ajustes.guardar(CLAVE_SYNC, json.writeValueAsString(hecha))
                hecha
            } catch (e: Exception) {
                log.warn("Medicion: no se pudo sincronizar Meta: {}", e.message)
                t + mapOf("estado" to ERROR, "fin" to Instant.now().toString(), "error" to (e.message ?: e.javaClass.simpleName))
            }
        }
        return t
    }

    /** Cada manana, si Meta esta conectado: los ultimos dias. */
    @Scheduled(cron = "0 20 7 * * *", zone = "America/Lima")
    fun diaria() {
        runCatching {
            if (worker.get("/medicion/meta")["completo"] == true) sincronizar(null)
        }.onFailure { log.info("Medicion: sin sincronizacion diaria ({})", it.message) }
    }

    private fun fila(m: Map<*, *>): FilaMeta? {
        val fecha = m["fecha"] as? String ?: return null
        val anuncio = m["anuncio_id"]?.toString() ?: return null
        fun n(k: String) = (m[k] as? Number)?.toLong() ?: 0L
        return FilaMeta(
            fecha, anuncio, m["anuncio"]?.toString().orEmpty(), m["conjunto_id"]?.toString(), m["conjunto"]?.toString(),
            m["campana_id"]?.toString().orEmpty(), m["campana"]?.toString().orEmpty(), m["objetivo"]?.toString(),
            (m["gasto"] as? Number)?.toDouble() ?: 0.0, n("impresiones"), n("alcance"), n("clics"), n("clics_enlace"), n("leads"),
            n("conversaciones"), n("visitas"),
        )
    }

    // ── Cifras del periodo ──

    private data class Suma(
        var gasto: Double = 0.0, var impresiones: Long = 0, var clicsEnlace: Long = 0, var leads: Long = 0, var conversaciones: Long = 0,
        var visitas: Long = 0,
    ) {
        fun mas(f: FilaMeta) {
            gasto += f.gasto; impresiones += f.impresiones; clicsEnlace += f.clicsEnlace; leads += f.leads
            conversaciones += f.conversaciones; visitas += f.visitas
        }
        val ctr get() = if (impresiones > 0) clicsEnlace.toDouble() / impresiones else null
        val cpc get() = if (clicsEnlace > 0) gasto / clicsEnlace else null
    }

    private fun suma(filas: List<FilaMeta>) = Suma().also { s -> filas.forEach(s::mas) }

    /**
     * Que resultado produce una campana: LEADS, CONVERSACIONES o SIN_RESULTADOS (web, alcance...).
     * Una de WhatsApp tiene chats en el 10-30 % de sus clics; las de web o visualizaciones traen
     * alguno suelto (<= 2 %) y no deben contarse como de WhatsApp a USD 400 por chat.
     */
    private fun tipo(s: Suma) = when {
        s.leads > 0 && s.leads >= s.conversaciones -> LEADS
        s.conversaciones > 0 && s.conversaciones >= MIN_CHATS_POR_CLIC * s.clicsEnlace -> CONVERSACIONES
        else -> SIN_RESULTADOS
    }

    private fun resultados(s: Suma, tipo: String) = when (tipo) {
        LEADS -> s.leads
        CONVERSACIONES -> s.conversaciones
        else -> 0L
    }

    private fun costo(gasto: Double, n: Long) = if (n > 0) redondear(gasto / n) else null

    private fun redondear(x: Double, d: Int = 2): Double = Math.round(x * Math.pow(10.0, d.toDouble())) / Math.pow(10.0, d.toDouble())

    private fun cambio(actual: Double?, anterior: Double?) =
        if (actual == null || anterior == null || anterior == 0.0) null else redondear((actual - anterior) / anterior, 4)

    /**
     * Totales de la cuenta. Leads y conversaciones cuentan todos (una campana de leads tambien
     * trae algun chat); su costo se calcula solo con las campanas de ese tipo y sus resultados.
     */
    private fun kpis(filas: List<FilaMeta>, tipos: Map<String, String>): Map<String, Any?> {
        val total = suma(filas)
        val porTipo = filas.groupBy { tipos[it.campanaId] ?: SIN_RESULTADOS }.mapValues { suma(it.value) }
        val l = porTipo[LEADS] ?: Suma()
        val c = porTipo[CONVERSACIONES] ?: Suma()
        return mapOf(
            "gasto" to redondear(total.gasto), "impresiones" to total.impresiones, "clicsEnlace" to total.clicsEnlace,
            "ctr" to total.ctr?.let { redondear(it, 4) }, "cpc" to total.cpc?.let { redondear(it) }, "visitas" to total.visitas,
            "leads" to total.leads, "costoLead" to costo(l.gasto, l.leads), "gastoLeads" to redondear(l.gasto),
            "conversaciones" to total.conversaciones, "costoConversacion" to costo(c.gasto, c.conversaciones), "gastoConversaciones" to redondear(c.gasto),
            "gastoSinResultados" to redondear(porTipo[SIN_RESULTADOS]?.gasto ?: 0.0),
            "campanas" to filas.filter { it.gasto > 0 }.map { it.campanaId }.distinct().size,
            "anuncios" to filas.filter { it.gasto > 0 }.map { it.anuncioId }.distinct().size,
        )
    }

    private fun periodo(desde: String?, hasta: String?): Pair<LocalDate, LocalDate> {
        val h = hasta?.let { runCatching { LocalDate.parse(it) }.getOrNull() ?: throw ReglaIncumplida("La fecha va como AAAA-MM-DD.") } ?: hoy().minusDays(1)
        val d = desde?.let { runCatching { LocalDate.parse(it) }.getOrNull() ?: throw ReglaIncumplida("La fecha va como AAAA-MM-DD.") } ?: h.minusDays(29)
        if (d.isAfter(h)) throw ReglaIncumplida("La fecha inicial es posterior a la final.")
        if (ChronoUnit.DAYS.between(d, h) > MAX_DIAS) throw ReglaIncumplida("Como mucho $MAX_DIAS días por periodo.")
        return d to h
    }

    /** Las partes del nombre: «ILCB - Lead Ads - Pastelería - Pregrado 2027I» -> linea, canal, producto. */
    private fun partes(nombre: String): Map<String, String?> {
        val p = nombre.split(" - ").map { it.trim() }.filter { it.isNotEmpty() }
        return if (p.size >= 3) mapOf("linea" to p[0], "canal" to p[1], "producto" to p[2]) else mapOf("linea" to null, "canal" to null, "producto" to null)
    }

    /**
     * El periodo (por defecto, los 30 dias hasta ayer) frente al anterior de la misma duracion:
     * totales, serie diaria, campanas, anuncios con mas gasto y alertas.
     */
    fun resumen(desde: String?, hasta: String?): Map<String, Any?> {
        val (d, h) = periodo(desde, hasta)
        val dias = ChronoUnit.DAYS.between(d, h) + 1
        val (ad, ah) = d.minusDays(dias) to d.minusDays(1)
        val actual = repo.filas(d.toString(), h.toString())
        val anterior = repo.filas(ad.toString(), ah.toString())
        // El tipo de cada campana sale de los dos periodos: asi el anterior se compara con la misma regla.
        val tipos = (actual + anterior).groupBy { it.campanaId }.mapValues { tipo(suma(it.value)) }
        val antPorCampana = anterior.groupBy { it.campanaId }.mapValues { suma(it.value) }
        val campanas = actual.groupBy { it.campanaId }.map { (id, fs) ->
            val s = suma(fs)
            val t = tipos.getValue(id)
            val a = antPorCampana[id]
            val n = resultados(s, t)
            val costoAhora = costo(s.gasto, n)
            val costoAntes = a?.let { costo(it.gasto, resultados(it, t)) }
            mapOf(
                "id" to id, "nombre" to fs.last().campana, "objetivo" to fs.last().objetivo, "tipo" to t, "gasto" to redondear(s.gasto),
                "impresiones" to s.impresiones, "clicsEnlace" to s.clicsEnlace, "ctr" to s.ctr?.let { redondear(it, 4) },
                "leads" to s.leads, "conversaciones" to s.conversaciones, "resultados" to n, "costoResultado" to costoAhora,
                "gastoAnterior" to a?.let { redondear(it.gasto) }, "costoAnterior" to costoAntes, "cambioCosto" to cambio(costoAhora, costoAntes),
                "anuncios" to fs.filter { it.gasto > 0 }.map { it.anuncioId }.distinct().size,
            ) + partes(fs.last().campana)
        }.filter { (it["gasto"] as Double) > 0 || (it["resultados"] as Long) > 0 }.sortedByDescending { it["gasto"] as Double }
        val anuncios = actual.groupBy { it.anuncioId }.map { (id, fs) ->
            val s = suma(fs)
            val t = tipos[fs.last().campanaId] ?: SIN_RESULTADOS
            val n = resultados(s, t)
            mapOf("id" to id, "nombre" to fs.last().anuncio, "campana" to fs.last().campana, "conjunto" to fs.last().conjunto, "tipo" to t,
                "gasto" to redondear(s.gasto), "impresiones" to s.impresiones, "ctr" to s.ctr?.let { redondear(it, 4) }, "resultados" to n,
                "costoResultado" to costo(s.gasto, n))
        }.filter { (it["gasto"] as Double) > 0 }.sortedByDescending { it["gasto"] as Double }.take(MAX_ANUNCIOS)
        val serie = actual.groupBy { it.fecha }.toSortedMap().map { (f, fs) ->
            val s = suma(fs)
            mapOf("fecha" to f, "gasto" to redondear(s.gasto), "leads" to s.leads, "conversaciones" to s.conversaciones,
                "clicsEnlace" to s.clicsEnlace, "impresiones" to s.impresiones)
        }
        return mapOf(
            "periodo" to mapOf("desde" to d.toString(), "hasta" to h.toString(), "dias" to dias),
            "anterior" to mapOf("desde" to ad.toString(), "hasta" to ah.toString()),
            "moneda" to moneda(), "kpis" to kpis(actual, tipos), "kpisAnterior" to kpis(anterior, tipos),
            "serie" to serie, "campanas" to campanas, "anuncios" to anuncios, "alertas" to alertas(h),
            "datos" to repo.rango()?.let { mapOf("desde" to it.first, "hasta" to it.second) },
        )
    }

    /**
     * Alertas sin IA: los ultimos 7 dias hasta `hasta` frente a los 7 anteriores. Umbrales con
     * minimos de volumen para no alarmar por dos leads de diferencia.
     */
    fun alertas(hasta: LocalDate): List<Map<String, Any?>> {
        val (d1, d0) = hasta.minusDays(6) to hasta.minusDays(13)
        val filas = repo.filas(d0.toString(), hasta.toString())
        val (ahora, antes) = filas.partition { it.fecha >= d1.toString() }
        val tipos = filas.groupBy { it.campanaId }.mapValues { tipo(suma(it.value)) }
        val salida = mutableListOf<Map<String, Any?>>()
        val mon = moneda()
        fun dinero(x: Double) = "$mon ${"%,.2f".format(java.util.Locale.US, x)}"
        fun pct(x: Double) = "${Math.round(x * 100)} %"

        val gAhora = ahora.sumOf { it.gasto }
        val gAntes = antes.sumOf { it.gasto }
        if (gAntes >= MIN_GASTO_CUENTA && kotlin.math.abs(gAhora - gAntes) / gAntes >= UMBRAL_GASTO) {
            salida += alerta("GASTO", "INFO", "El gasto de la cuenta ${if (gAhora > gAntes) "subió" else "bajó"} ${pct(kotlin.math.abs(gAhora - gAntes) / gAntes)}",
                "${dinero(gAhora)} en los últimos 7 días frente a ${dinero(gAntes)} en los 7 anteriores.", null)
        }
        val antesPor = antes.groupBy { it.campanaId }.mapValues { suma(it.value) }
        for ((id, fs) in ahora.groupBy { it.campanaId }) {
            val t = tipos.getValue(id)
            val s = suma(fs)
            val a = antesPor[id] ?: continue
            val nombre = fs.last().campana
            val (n, na) = resultados(s, t) to resultados(a, t)
            val que = if (t == LEADS) "lead" else "conversación"
            if (t != SIN_RESULTADOS && n >= MIN_RESULTADOS && na >= MIN_RESULTADOS) {
                val (c, ca) = s.gasto / n to a.gasto / na
                if ((c - ca) / ca >= UMBRAL_COSTO) {
                    salida += alerta("COSTO_SUBE", "ALTA", "Se encarece «$nombre»",
                        "Costo por $que: ${dinero(c)} en los últimos 7 días frente a ${dinero(ca)} (+${pct((c - ca) / ca)}); $n resultados frente a $na.", id, s.gasto)
                }
            }
            val (ctr, ctra) = s.ctr to a.ctr
            if (ctr != null && ctra != null && ctra > 0 && s.impresiones >= MIN_IMPRESIONES && a.impresiones >= MIN_IMPRESIONES &&
                (ctra - ctr) / ctra >= UMBRAL_CTR) {
                salida += alerta("CTR_BAJA", "MEDIA", "Cae el CTR de «$nombre»",
                    "CTR de enlace ${"%.2f".format(java.util.Locale.US, ctr * 100)} % frente a ${"%.2f".format(java.util.Locale.US, ctra * 100)} % " +
                        "(−${pct((ctra - ctr) / ctra)}). Puede ser cansancio de la creatividad o del público.", id, s.gasto)
            }
        }
        // Anuncios que gastan sin traer su resultado: mas del doble del costo medio por resultado de su campana.
        val porCampana = ahora.groupBy { it.campanaId }.mapValues { suma(it.value) }
        for ((id, fs) in ahora.groupBy { it.anuncioId }) {
            val campana = fs.last().campanaId
            val t = tipos.getValue(campana)
            if (t == SIN_RESULTADOS) continue
            val s = suma(fs)
            val c = porCampana.getValue(campana)
            val nc = resultados(c, t)
            if (nc < MIN_RESULTADOS || resultados(s, t) > 0) continue
            val umbral = maxOf(2 * c.gasto / nc, MIN_GASTO_ANUNCIO)
            if (s.gasto >= umbral) {
                salida += alerta("SIN_RESULTADOS", "ALTA", "«${fs.last().anuncio}» gasta sin resultados",
                    "${dinero(s.gasto)} en los últimos 7 días y ningún ${if (t == LEADS) "lead" else "chat"}; su campaña «${fs.last().campana}» " +
                        "consigue cada uno por ${dinero(c.gasto / nc)}.", id, s.gasto)
            }
        }
        // Lo que rinde mucho mejor que el promedio de su tipo: candidato a recibir mas presupuesto.
        for (t in listOf(LEADS, CONVERSACIONES)) {
            val delTipo = ahora.filter { tipos[it.campanaId] == t }
            val total = suma(delTipo)
            val nt = resultados(total, t)
            if (nt < MIN_RESULTADOS) continue
            val medio = total.gasto / nt
            for ((id, fs) in delTipo.groupBy { it.campanaId }) {
                val s = suma(fs)
                val n = resultados(s, t)
                if (n >= MIN_RESULTADOS_MEJOR && s.gasto / n <= medio * UMBRAL_MEJOR) {
                    salida += alerta("RINDE_MEJOR", "OPORTUNIDAD", "«${fs.last().campana}» rinde mejor que el resto",
                        "Costo por ${if (t == LEADS) "lead" else "conversación"}: ${dinero(s.gasto / n)} frente a ${dinero(medio)} de promedio " +
                            "($n resultados en 7 días).", id, s.gasto)
                }
            }
        }
        val ultima = repo.rango()?.second?.let { LocalDate.parse(it) }
        if (ultima == null || ultima.isBefore(hoy().minusDays(2))) {
            salida += alerta("DATOS_VIEJOS", "INFO", "Los datos de Meta no están al día",
                if (ultima == null) "Aún no se trajo nada: pulsa «Actualizar datos»." else "Lo último guardado es del $ultima: pulsa «Actualizar datos».", null)
        }
        val orden = listOf("ALTA", "MEDIA", "OPORTUNIDAD", "INFO")
        return salida.sortedWith(compareBy<Map<String, Any?>> { orden.indexOf(it["nivel"]) }.thenByDescending { it["gasto"] as Double })
    }

    private fun alerta(tipo: String, nivel: String, titulo: String, detalle: String, id: String?, gasto: Double = 0.0) =
        mapOf("tipo" to tipo, "nivel" to nivel, "titulo" to titulo, "detalle" to detalle, "id" to id, "gasto" to redondear(gasto))

    private fun moneda(): String =
        ajustes.leer(CLAVE_CUENTA)?.let { runCatching { json.readValue(it, Map::class.java)["moneda"] as? String }.getOrNull() }
            ?: runCatching { (worker.get("/medicion/meta")["detalle"] as? Map<*, *>)?.let { d ->
                ajustes.guardar(CLAVE_CUENTA, json.writeValueAsString(d)); d["moneda"] as? String } }.getOrNull()
            ?: "USD"

    // ── GA4 ──

    fun ga4Propiedades(): Json = worker.get("/medicion/ga4/propiedades")

    fun elegirPropiedadGa4(propiedad: String): Json = worker.post("/medicion/ga4/propiedad", mapOf("propiedad" to propiedad))

    // ── Conexion con Google (Ads, Search Console y GA4 comparten un refresh token) ──

    /** Estado de la conexion; `comprobar` la prueba contra Google. */
    fun google(comprobar: Boolean): Json = worker.get("/google/conexion?comprobar=$comprobar")

    /** Direccion de Google para dar permiso; la vuelta la recibe el worker en 127.0.0.1. */
    fun conectarGoogle(): Json = worker.post("/google/conexion", emptyMap<String, Any>())

    fun ga4(desde: String?, hasta: String?): Json {
        val (d, h) = periodo(desde, hasta)
        return worker.post("/medicion/ga4/informe", mapOf("desde" to d.toString(), "hasta" to h.toString()))
    }

    // ── Informe con IA (queda guardado) ──

    /** Resume el periodo con IA y lo guarda como informe (MEDICION) con las cifras y las campanas. */
    fun informe(actor: Usuario?, desde: String?, hasta: String?): Map<String, Any?> {
        val r = resumen(desde, hasta)
        val kpis = r["kpis"] as Map<*, *>
        if ((kpis["gasto"] as Double) == 0.0) throw ReglaIncumplida("No hay datos de Meta en ese periodo: pulsa «Actualizar datos» o elige otro periodo.")
        val p = r["periodo"] as Map<*, *>
        @Suppress("UNCHECKED_CAST")
        val campanas = r["campanas"] as List<Map<String, Any?>>
        val ga4 = runCatching { ga4(desde, hasta) }.getOrNull()?.let { mapOf("canales" to it["canales"], "eventos" to it["eventos"]) }
        val datosIa = mapOf(
            "periodo" to p, "anterior" to r["anterior"], "moneda" to r["moneda"], "kpis" to paraIa(kpis), "kpisAnterior" to paraIa(r["kpisAnterior"] as Map<*, *>),
            "campanas" to campanas.take(15).map { c -> campanaParaIa(c) }, "alertas" to (r["alertas"] as List<*>).map { (it as Map<*, *>) - "gasto" - "id" },
            "ga4" to ga4,
        )
        val ia = worker.post("/medicion/resumen", mapOf("datos" to datosIa, "negocio" to seo.negocio(), "rubro" to seo.rubro().descripcion))
        val codigoUso = "MEDICION"
        (ia["uso"] as? Map<*, *>)?.let { consumo.registrar(codigoUso, "medicion_resumen", it) }
        val guardado: InformeGuardado = informes.guardar(
            MEDICION, "Medición · del ${p["desde"]} al ${p["hasta"]}",
            mapOf("periodo" to p, "anterior" to r["anterior"], "moneda" to r["moneda"], "kpis" to kpis, "kpisAnterior" to r["kpisAnterior"],
                "alertas" to r["alertas"], "ia" to ia - "uso", "ga4" to ga4),
            campanas, null, actor?.codigo,
        )
        return mapOf("informe" to guardado, "ia" to ia - "uso")
    }

    /** El CTR como porcentaje (la IA escribia «0.0079»). */
    private fun paraIa(m: Map<*, *>): Map<String, Any?> {
        val x = m.entries.associate { it.key.toString() to it.value }
        return (x - "ctr") + ("ctrPorcentaje" to (x["ctr"] as? Double)?.let { redondear(it * 100) })
    }

    /** Con pocos resultados el costo no dice nada: no se le pasa a la IA, para que no saque conclusiones de el. */
    private fun campanaParaIa(c: Map<String, Any?>): Map<String, Any?> {
        val base = paraIa(c.filterKeys { it in CAMPOS_IA })
        val pocos = c["tipo"] != SIN_RESULTADOS && (c["resultados"] as Long) < MIN_RESULTADOS
        return if (!pocos) base else base + mapOf("costoResultado" to null, "costoAnterior" to null, "cambioCosto" to null, "pocosResultados" to true)
    }

    private fun hoy(): LocalDate = LocalDate.now(LIMA)

    companion object {
        const val EN_CURSO = "EN_CURSO"
        const val LISTA = "LISTA"
        const val ERROR = "ERROR"
        const val LEADS = "LEADS"
        const val CONVERSACIONES = "CONVERSACIONES"
        const val SIN_RESULTADOS = "SIN_RESULTADOS"
        const val MEDICION = "MEDICION"
        const val CLAVE_SYNC = "medicion_meta_sync"
        const val CLAVE_CUENTA = "medicion_meta_cuenta"
        const val DIAS_INICIALES = 90L
        const val DIAS_REVISAR = 7L
        const val MAX_DIAS = 400L
        const val MAX_ANUNCIOS = 50
        const val MIN_RESULTADOS = 10L
        const val MIN_RESULTADOS_MEJOR = 20L
        const val MIN_IMPRESIONES = 5000L
        const val MIN_GASTO_CUENTA = 50.0
        const val MIN_GASTO_ANUNCIO = 20.0
        const val UMBRAL_COSTO = 0.30
        const val UMBRAL_CTR = 0.30
        const val UMBRAL_GASTO = 0.40
        const val UMBRAL_MEJOR = 0.60
        const val MIN_CHATS_POR_CLIC = 0.05
        val CAMPOS_IA = setOf("nombre", "tipo", "gasto", "resultados", "costoResultado", "costoAnterior", "cambioCosto", "ctr", "leads", "conversaciones")
        val LIMA: ZoneId = ZoneId.of("America/Lima")
    }
}
