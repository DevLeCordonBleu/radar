package pe.edu.lcb.radar.aplicacion

import pe.edu.lcb.radar.dominio.Json
import java.text.Normalizer

/** El rubro del negocio propio: lo que describe a la IA y las palabras del filtro gratuito. */
data class RubroSeo(val descripcion: String, val palabras: List<String>)

/** Un nombre que ninguna propuesta de la IA cambia ni redefine. `tipo`: CARRERA | SISTEMA | OTRO. */
data class TerminoProtegido(val nombre: String, val tipo: String, val descripcion: String)

/**
 * Filtro gratuito (sin IA) del Plan SEO: si una pagina de un competidor habla del rubro
 * del negocio propio, segun las palabras de su ajuste («Rubro de tu negocio»).
 *
 * Una palabra de 4 letras o mas cuenta como comienzo («cocin» -> cocina, cocinero); una
 * de 3 o menos, solo entera («bar» si, «barranco» no).
 *
 * Pasa si lo dice lo que anuncia de que trata (URL, title, H1, H2, meta description) o si
 * el inicio de su texto lo menciona al menos dos veces: una sola mencion suele ser un menu
 * («Turismo · Gastronomia · Hoteleria»), y sin el texto se perdian paginas de un competidor
 * que es todo cocina pero no lo dice en el titulo («Vacaciones», «Vive D'Gallia»). Ante la
 * duda deja pasar: lo que pasa lo juzga despues la IA con su relevancia; lo que no pasa no
 * se le manda y no cuesta nada. Probado con el inventario real y el rubro por defecto:
 * CENFOTUR 72 de 331, D'Gallia 10 de 14 (fuera: Shop, Blog vacio, La Pre y Talleres con
 * texto de relleno).
 */
object SectorSeo {
    /** El rubro de ILCB, el que se usa mientras nadie lo cambie. */
    val POR_DEFECTO = RubroSeo(
        "Escuela de cocina peruana e internacional, panadería, pastelería, bar y coctelería",
        listOf(
            "gastronom", "cocin", "culinar", "chef", "pastel", "reposter", "panader", "panific", "bolleri", "postre",
            "chocolat", "receta", "coctel", "mixolog", "bartender", "barman", "sommelier", "somelier", "enolog", "vinic",
            "barista", "cevich", "pisco", "cervez", "bebida", "aliment", "comida", "gourmet", "parrill", "sushi",
            "bar", "bares", "pan", "panes", "vino", "cafe", "plato", "torta", "cocktail", "food",
        ),
    )

    fun delSector(url: String, datos: Json, palabras: List<String>): Boolean {
        val (enteras, raices) = palabras.partition { it.length <= 3 }
        val esDelSector = { p: String -> p in enteras || raices.any { p.startsWith(it) } }
        val partes = listOf(url, datos["title"], datos["h1"], datos["meta_description"]) + (datos["h2"] as? List<*>).orEmpty()
        if (palabras(partes.joinToString(" ") { it?.toString().orEmpty() }).any(esDelSector)) return true
        return palabras(datos["extracto"]?.toString().orEmpty()).count(esDelSector) >= 2
    }

    /** Minusculas y sin tildes, partido en palabras: igual para el texto y para las palabras del ajuste. */
    fun palabras(t: String): List<String> =
        Normalizer.normalize(t.lowercase(), Normalizer.Form.NFD).replace(Regex("\\p{M}"), "")
            .split(Regex("[^a-z0-9]+")).filter { it.isNotEmpty() }

    /** Lo que se guarda como «temas» de una pagina descartada: relevancia 0, sin consultas. */
    val FUERA: Json = mapOf(
        "tipo_pagina" to "OTRA", "tema" to "fuera del sector", "consultas" to emptyList<String>(), "relevancia" to 0,
        "confianza" to "ALTA", "evidencia" to emptyList<String>(), "fuera_del_sector" to true,
    )
}
