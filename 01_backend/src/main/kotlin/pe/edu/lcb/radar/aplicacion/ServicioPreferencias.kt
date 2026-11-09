package pe.edu.lcb.radar.aplicacion

import org.springframework.stereotype.Service
import pe.edu.lcb.radar.dominio.Peticion
import pe.edu.lcb.radar.dominio.ReglaIncumplida
import pe.edu.lcb.radar.infraestructura.RepositorioAjustes
import tools.jackson.databind.ObjectMapper

/**
 * "Tu mercado": mis marcas, competidores, sector y pais, guardados para que el
 * siguiente analisis salga con el formulario ya relleno. No son claves.
 */
@Service
class ServicioPreferencias(private val repo: RepositorioAjustes, private val json: ObjectMapper) {

    fun leer(): Peticion = repo.leer(CLAVE)?.let { json.readValue(it, Peticion::class.java) } ?: Peticion()

    fun guardar(p: Peticion): Peticion {
        if (p.competidores.size > 20) throw ReglaIncumplida("Máximo 20 competidores.")
        repo.guardar(CLAVE, json.writeValueAsString(p))
        return leer()
    }

    private companion object {
        const val CLAVE = "mercado"
    }
}
