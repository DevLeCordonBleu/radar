package pe.edu.lcb.radar.aplicacion

import java.net.URI
import java.text.Normalizer

/**
 * Parametros UTM en los enlaces a la web propia de un post, para que GA4 sepa de que red y de
 * que publicacion vino cada visita. Solo en Facebook y LinkedIn (en Instagram el texto no tiene
 * enlaces que se puedan pulsar). Un enlace que ya trae utm_* no se toca.
 * El frontend hace lo mismo (`composables/utm.ts`): si cambia uno, cambiar el otro.
 */
object Utm {
    private val URL = Regex("""https?://[^\s<>"'()\[\]]+""")
    private val FUENTES = mapOf("FACEBOOK" to "facebook", "LINKEDIN" to "linkedin")
    const val MEDIO = "social"

    /** «Ven y conoce el Campus!» -> «ven-y-conoce-el-campus». */
    fun slug(t: String): String =
        Normalizer.normalize(t.lowercase(), Normalizer.Form.NFD).replace(Regex("\\p{M}"), "")
            .replace(Regex("[^a-z0-9]+"), "-").trim('-').take(40).trimEnd('-')

    fun agregar(url: String, fuente: String, medio: String, campana: String, contenido: String?): String {
        if (Regex("[?&]utm_", RegexOption.IGNORE_CASE).containsMatchIn(url)) return url
        val base = url.substringBefore('#')
        val ancla = url.substring(base.length)
        val params = listOfNotNull("utm_source" to fuente, "utm_medium" to medio, "utm_campaign" to campana, contenido?.let { "utm_content" to it })
            .filter { it.second.isNotBlank() }
        return base + (if ('?' in base) "&" else "?") + params.joinToString("&") { "${it.first}=${it.second}" } + ancla
    }

    private fun propio(url: String, dominios: List<String>): Boolean {
        val host = runCatching { URI(url).host }.getOrNull()?.lowercase()?.removePrefix("www.") ?: return false
        return dominios.any { d -> host == d || host.endsWith(".$d") }
    }

    /** El texto con UTM en los enlaces a `dominios`. La puntuacion final («…/admision/.») queda fuera del enlace. */
    fun enTexto(texto: String, red: String, codigo: String, titulo: String, dominios: List<String>): String {
        val fuente = FUENTES[red] ?: return texto
        return URL.replace(texto) { m ->
            val crudo = m.value
            val url = crudo.trimEnd('.', ',', ';', ':', '!', '?')
            if (!propio(url, dominios)) crudo
            else agregar(url, fuente, MEDIO, slug(titulo).ifEmpty { "publicacion" }, codigo.lowercase()) + crudo.substring(url.length)
        }
    }
}
