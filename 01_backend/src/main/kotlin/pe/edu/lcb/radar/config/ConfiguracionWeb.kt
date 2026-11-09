package pe.edu.lcb.radar.config

import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration
import org.springframework.web.servlet.config.annotation.CorsRegistry
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

/**
 * CORS para Vite en desarrollo y la cola de analisis.
 *
 * La cola tiene un solo hilo a proposito: dos analisis a la vez se disputarian
 * la cuota de Gemini (que es por minuto y por dia) y los creditos de Apify, y
 * los dos terminarian pausados. En cola, uno acaba antes que dos a medias.
 */
@Configuration
class ConfiguracionWeb(private val ajustes: Ajustes) : WebMvcConfigurer {

    override fun addCorsMappings(registro: CorsRegistry) {
        if (ajustes.origenesPermitidos.isEmpty()) return
        registro.addMapping("/api/**")
            .allowedOrigins(*ajustes.origenesPermitidos.toTypedArray())
            .allowedMethods("GET", "POST", "PUT", "DELETE")
            .allowedHeaders("*")
    }

    @Bean(destroyMethod = "shutdownNow")
    fun colaAnalisis(): ExecutorService = Executors.newSingleThreadExecutor { r -> Thread(r, "cola-analisis") }

    /** Plan SEO: su propia cola, para que un inventario largo no retrase un analisis de anuncios. */
    @Bean(destroyMethod = "shutdownNow")
    fun colaSeo(): ExecutorService = Executors.newSingleThreadExecutor { r -> Thread(r, "cola-seo") }
}
