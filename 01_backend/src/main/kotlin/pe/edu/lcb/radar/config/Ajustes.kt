package pe.edu.lcb.radar.config

import org.springframework.boot.context.properties.ConfigurationProperties

/**
 * Ajustes tecnicos del modulo (application.properties). Las preferencias del
 * equipo (mis marcas, pais, sector) viven en la base y se editan en el panel:
 * ver ServicioPreferencias. Las claves de Gemini y Apify viven en el .env del
 * worker y nunca pasan por aqui.
 */
@ConfigurationProperties(prefix = "radar")
data class Ajustes(
    val datos: String = "./datos",
    val worker: String = "http://localhost:8102",
    val origenesPermitidos: List<String> = emptyList(),
)
