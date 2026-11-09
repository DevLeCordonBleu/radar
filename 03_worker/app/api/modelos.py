# -*- coding: utf-8 -*-
from typing import Literal

from pydantic import BaseModel, Field


class Termino(BaseModel):
    valor: str
    modo: str = "marca"          # pagina | marca | palabras


class PeticionLanzar(BaseModel):
    terminos: list[Termino]
    pais: str = "PE"
    maximo: int = Field(100, ge=1, le=500)
    solo_activos: bool = True


class PeticionRun(BaseModel):
    run: str
    t: int = 0


class PeticionNormalizar(BaseModel):
    items: list[dict]
    nivel: int = 3


class PeticionResolver(BaseModel):
    buscado: str
    anuncios: list[dict]


class PeticionClasificar(BaseModel):
    anuncios: list[dict]
    referencia: list[str] = []
    terminos: list[str] = []
    con_medios: bool = True
    modelo: str | None = None


class PeticionTerritorios(BaseModel):
    etiquetas: list[str]
    modelo: str | None = None


class PeticionInforme(BaseModel):
    anuncios: list[dict]
    territorios: list[dict]
    mis_marcas: list[str] = []
    mis_paginas: list[str] | None = None   # None: reconocer tus anuncios por el nombre
    sin_anuncios: list[str] = []
    identificadas: list[dict] = []


class Miniatura(BaseModel):
    id: str = Field(..., min_length=1, max_length=40)  # ad_id
    url: str = Field(..., max_length=4000)


class PeticionMiniaturas(BaseModel):
    items: list[Miniatura] = Field(..., max_length=60)


class PeticionExplorar(BaseModel):
    semillas: list[str] = []
    url: str | None = None
    pais: str = "PE"
    idioma: str = "es"
    maximo: int = Field(1000, ge=10, le=2000)
    sugerencias: bool = True
    demo: bool = False


class PeticionResumenKw(BaseModel):
    keyword: str
    pais: str = "PE"
    idioma: str = "es"
    por_pais: bool = False
    demo: bool = False


class PeticionMetricasKw(BaseModel):
    keywords: list[str] = Field(..., max_length=500)
    pais: str = "PE"
    idioma: str = "es"
    demo: bool = False


# ── Plan SEO ──

class PeticionDescubrir(BaseModel):
    hosts: list[str] = Field(..., min_length=1, max_length=5)
    maximo: int = Field(3000, ge=1, le=10000)


class PeticionPaginasSeo(BaseModel):
    urls: list[str] = Field(..., min_length=1, max_length=30)
    pausa_s: float = Field(1.0, ge=1.0, le=30.0)


class PeticionTemasSeo(BaseModel):
    paginas: list[dict] = Field(..., min_length=1, max_length=30)
    negocio: str = ""
    rubro: str = ""
    modelo: str | None = None


class PeticionAgruparSeo(BaseModel):
    keywords: list[str] = Field(..., min_length=1, max_length=300)
    grupos: list[str] = []
    negocio: str = ""
    rubro: str = ""
    modelo: str | None = None


class PeticionCoberturaSeo(BaseModel):
    grupos: list[dict] = Field(..., min_length=1, max_length=60)
    propias: list[dict] = Field(..., max_length=1500)
    modelo: str | None = None


class PeticionArticuloSeo(BaseModel):
    keyword: str = Field(..., min_length=2, max_length=200)
    variantes: list[str] = Field([], max_length=40)
    competidores: list[dict] = Field([], max_length=8)
    propias: list[dict] = Field([], max_length=40)
    negocio: str = ""
    rubro: str = ""
    indicaciones: str = Field("", max_length=2000)
    modelo: str | None = None


class PeticionRubroSeo(BaseModel):
    negocio: str = Field(..., min_length=1, max_length=120)
    paginas: list[dict] = Field(..., min_length=1, max_length=300)
    modelo: str | None = None


class PeticionHtml(BaseModel):
    contenido: str = Field(..., max_length=200_000)


class GrupoDemanda(BaseModel):
    grupo: str
    # La primera es la principal: gana si empata con otra.
    keywords: list[str] = Field(..., min_length=1, max_length=10)


class ConsultaMejora(BaseModel):
    consulta: str
    impresiones: int = 0
    clics: int = 0
    posicion: float = 0


class TerminoProtegido(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=120)
    tipo: Literal["CARRERA", "SISTEMA", "OTRO"] = "OTRO"
    descripcion: str = Field("", max_length=500)


class PeticionMejoraSeo(BaseModel):
    url: str = Field(..., max_length=2000)
    actual: dict = Field(default_factory=dict)
    consultas: list[ConsultaMejora] = Field(..., min_length=1, max_length=20)
    negocio: str = ""
    rubro: str = ""
    # Carreras, sistemas y demás que no cambian de nombre ni de significado.
    terminos: list[TerminoProtegido] = Field(default_factory=list, max_length=100)
    modelo: str | None = None


class PeticionConsultasGsc(BaseModel):
    # Search Console guarda 16 meses.
    dias: int = Field(90, ge=7, le=480)


class PeticionDemanda(BaseModel):
    grupos: list[GrupoDemanda] = Field(..., max_length=40)
    pais: str = Field("PE", min_length=2, max_length=2)
    idioma: str = Field("es", min_length=2, max_length=5)


class ImagenWordpress(BaseModel):
    datos_b64: str = Field(..., min_length=1, max_length=17_000_000)  # ~12 MB en base64
    mime: str = Field(..., pattern=r"^image/(jpeg|png|webp)$")
    alt: str = Field("", max_length=300)
    leyenda: str = Field("", max_length=300)
    id_media: int | None = None  # ya subida antes: se reutiliza si sigue en WordPress


class PeticionWordpress(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=300)
    slug: str = Field("", max_length=200)
    contenido: str = Field(..., min_length=1, max_length=200_000)  # Markdown: aqui se pasa a HTML
    extracto: str = Field("", max_length=1000)
    publicar: bool = False
    id_wp: int | None = None
    imagen: ImagenWordpress | None = None


class PeticionBuscarImagen(BaseModel):
    consulta: str = Field(..., min_length=2, max_length=100)
    pagina: int = Field(1, ge=1, le=50)
    orientacion: str = Field("horizontal", pattern="^(horizontal|vertical)$")


class PeticionFoto(BaseModel):
    id: int = Field(..., ge=1)


class PeticionGenerarImagen(BaseModel):
    descripcion: str = Field(..., min_length=5, max_length=1000)
    negocio: str = Field("", max_length=200)
    rubro: str = Field("", max_length=400)
    formato: str = Field("HORIZONTAL", pattern="^(HORIZONTAL|VERTICAL)$")


class PeticionPaginasMeta(BaseModel):
    texto: str = Field(..., min_length=1, max_length=80)
    pais: str = "PE"


# ── Videos (guion por partes y Google Vids) ───────────────────────────────

class Pronunciacion(BaseModel):
    texto: str = Field(..., max_length=80)
    dice: str = Field(..., max_length=80)


class ContextoVideo(BaseModel):
    negocio: str = ""
    rubro: str = ""
    datos: str = Field("", max_length=6000)
    personaje: str = Field("", max_length=600)
    estilo: str = Field("", max_length=600)
    voz: str = Field("", max_length=200)
    pronunciaciones: list[Pronunciacion] = Field(default_factory=list, max_length=20)


class ParteVideo(BaseModel):
    dialogo: str = Field(..., min_length=1, max_length=400)
    escena: str = Field("", max_length=300)


class PeticionGuionVideo(BaseModel):
    idea: str = Field(..., min_length=3, max_length=500)
    keyword: str = Field("", max_length=200)
    segundos: int = Field(45, ge=10, le=60)
    contexto: ContextoVideo = Field(default_factory=ContextoVideo)
    modelo: str | None = None


class PeticionPromptsVideo(BaseModel):
    partes: list[ParteVideo] = Field(..., min_length=1, max_length=6)
    formato: str = Field("VERTICAL", pattern="^(VERTICAL|HORIZONTAL)$")
    contexto: ContextoVideo = Field(default_factory=ContextoVideo)


class PeticionVidsLanzar(PeticionPromptsVideo):
    titulo: str = Field(..., min_length=1, max_length=120)
    segundos: int = Field(45, ge=10, le=60)


class PeticionTrabajoVids(BaseModel):
    id: str = Field(..., min_length=6, max_length=40)


# ── Publicaciones ──────────────────────────────────────────────────────────

class PeticionTextosPublicacion(BaseModel):
    idea: str = Field(..., min_length=3, max_length=1000)
    redes: list[str] = Field(..., min_length=1, max_length=3)
    media: str = Field("NINGUNA", pattern="^(NINGUNA|IMAGEN|VIDEO)$")
    modo: str = Field("POR_RED", pattern="^(POR_RED|MISMO)$")
    hashtags_base: list[str] = Field(default_factory=list, max_length=30)
    contexto: ContextoVideo = Field(default_factory=ContextoVideo)
    modelo: str | None = None


class PeticionFlyer(BaseModel):
    fondo_b64: str = Field(..., min_length=10)
    titulo: str = Field(..., min_length=1, max_length=120)
    detalle: str = Field("", max_length=160)
    cta: str = Field("", max_length=60)
    logo_b64: str | None = None
    color: str = Field("#0B1F3F", pattern="^#[0-9A-Fa-f]{6}$")
    acento: str = Field("#C9A55A", pattern="^#[0-9A-Fa-f]{6}$")


class PeticionVerificarPublicacion(BaseModel):
    # {red: url} de lo publicado y {red: texto publicado} para reconocerlo.
    enlaces: dict[str, str] = Field(..., min_length=1, max_length=3)
    textos: dict[str, str] = Field(default_factory=dict)


class PeticionPropiedadGa4(BaseModel):
    propiedad: str = Field(min_length=1, max_length=40)


class PeticionPeriodo(BaseModel):
    desde: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    hasta: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")


class PeticionResumenMedicion(BaseModel):
    # Las cifras ya calculadas por el backend: la IA solo las cuenta.
    datos: dict
    negocio: str = ""
    rubro: str = ""
    modelo: str | None = None
