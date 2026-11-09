package pe.edu.lcb.radar.aplicacion

import org.springframework.stereotype.Service
import pe.edu.lcb.radar.dominio.InformeFila
import pe.edu.lcb.radar.dominio.Json
import pe.edu.lcb.radar.dominio.NoEncontrado
import pe.edu.lcb.radar.dominio.ReglaIncumplida
import pe.edu.lcb.radar.infraestructura.ClienteWorker
import pe.edu.lcb.radar.infraestructura.RepositorioInformes

/** Informes terminados: lista, lectura, archivo y borrado. */
@Service
class ServicioInformes(private val repo: RepositorioInformes, private val worker: ClienteWorker) {

    fun listar(incluirArchivados: Boolean): List<InformeFila> = repo.todos(incluirArchivados)

    fun obtener(codigo: String): Json = repo.datos(codigo)

    fun resumen(codigo: String): InformeFila = repo.fila(codigo)

    fun miniatura(adId: String): Pair<ByteArray, String> = repo.miniatura(adId) ?: throw NoEncontrado("No hay imagen guardada de ese anuncio.")

    fun archivar(codigo: String, archivado: Boolean) = repo.archivar(codigo, archivado)

    fun borrar(codigo: String) = repo.borrar(codigo)

    /** Informe de muestra con anuncios inventados: para ver el panel sin claves ni gasto. */
    fun crearEjemplo(): InformeFila {
        if (repo.todos(true).any { it.esEjemplo }) throw ReglaIncumplida("El informe de ejemplo ya existe.")
        val datos = worker.get("/informe/ejemplo")
        val codigo = repo.guardar(null, "Escuelas de cocina (ejemplo)", datos, portada(datos), esEjemplo = true)
        return repo.fila(codigo)
    }

    companion object {
        /** Lo que se ve en la lista de informes: lo que mas se repite y lo que mas falta. */
        @Suppress("UNCHECKED_CAST")
        fun portada(datos: Json): Json? {
            val resumen = datos["resumen"] as? List<Json> ?: emptyList()
            val huecos = datos["huecos"] as? List<Json> ?: emptyList()
            val top = resumen.firstOrNull()
            val hueco = huecos.firstOrNull()
            if (top == null && hueco == null) return null
            return mapOf(
                "territorio" to top?.get("clave"), "pct" to top?.get("pct"),
                "hueco" to hueco?.get("clave"),
            )
        }
    }
}
