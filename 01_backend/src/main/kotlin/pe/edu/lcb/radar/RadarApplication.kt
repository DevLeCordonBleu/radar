package pe.edu.lcb.radar

import org.springframework.boot.autoconfigure.SpringBootApplication
import org.springframework.boot.context.properties.ConfigurationPropertiesScan
import org.springframework.boot.runApplication
import org.springframework.scheduling.annotation.EnableScheduling
import java.nio.file.Files
import java.nio.file.Path

@SpringBootApplication
@ConfigurationPropertiesScan
@EnableScheduling
class RadarApplication

fun main(args: Array<String>) {
	// SQLite crea el archivo de la base, pero no la carpeta que lo contiene.
	val datos = args.firstOrNull { it.startsWith("--radar.datos=") }
		?.substringAfter("=") ?: System.getProperty("radar.datos", "./datos")
	Files.createDirectories(Path.of(datos))
	runApplication<RadarApplication>(*args)
}
