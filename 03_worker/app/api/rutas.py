# -*- coding: utf-8 -*-
"""Endpoints del worker. Sin estado: el backend decide el orden y guarda el avance."""
from __future__ import annotations

import os

from fastapi import APIRouter

from app.analisis import competidores, informe, taxonomia as tx
from app import fuentes
from app.apify import cliente as apify, normalizar
from app.ia import clasificar, gemini
from . import modelos as m

router = APIRouter()


@router.get("/salud")
def salud():
    """Que esta configurado (nunca las claves, solo su final)."""
    def final(k: str):
        v = os.environ.get(k, "").strip()
        return v[-4:] if v else None
    return {
        "ok": True,
        "gemini": {"claves": len(gemini.claves()), "pago": gemini.con_pago(),
                   "modelos": gemini.modelos_disponibles(), "finales": [final("GEMINI_API_KEY"), final("GEMINI_API_KEY_2")]},
        "apify": {"tokens": len(apify.tokens()), "finales": [final("APIFY_TOKEN"), final("APIFY_TOKEN_2")]},
        # De donde saldran los anuncios del proximo analisis: «navegador» es gratis.
        "anuncios": {"fuente": fuentes.elegida(), "pedida": os.environ.get("ANUNCIOS_FUENTE", "auto").strip().lower() or "auto"},
    }


@router.get("/taxonomia")
def taxonomia():
    return {"hooks": tx.HOOKS, "ofertas": tx.OFERTAS, "ctas": tx.CTAS, "formatos": tx.FORMATOS,
            "patrones": tx.PATRONES_VISUALES, "niveles": tx.NIVELES, "muestra_minima": tx.MUESTRA_MINIMA}


@router.post("/claves/comprobar")
def comprobar_claves():
    return {"gemini": [gemini.comprobar(k) for k in gemini.claves()],
            "apify": [apify.comprobar(t) for t in apify.tokens()]}


# ── Anuncios (Biblioteca de Meta: navegador gratuito o Apify) ──────────────

@router.post("/anuncios/lanzar")
def lanzar(p: m.PeticionLanzar):
    return fuentes.lanzar([t.model_dump() for t in p.terminos], p.pais, p.maximo, p.solo_activos)


@router.post("/anuncios/consultar")
def consultar(p: m.PeticionRun):
    return fuentes.consultar(p.run, p.t)


@router.post("/anuncios/abortar")
def abortar(p: m.PeticionRun):
    fuentes.abortar(p.run, p.t)
    return {"ok": True}


@router.post("/anuncios/normalizar")
def normalizar_items(p: m.PeticionNormalizar):
    anuncios, error = normalizar.lote(p.items)
    return {"anuncios": [{**a, "nivel": p.nivel} for a in anuncios], "error": error}


@router.post("/anuncios/paginas")
def paginas_meta(p: m.PeticionPaginasMeta):
    """Sugerencias de paginas de Facebook para el nombre que se esta escribiendo."""
    from app.fuentes import paginas_meta as pm
    return {"paginas": pm.sugerir(p.texto, p.pais)}


@router.post("/anuncios/paginas/preparar")
def paginas_meta_preparar(p: m.PeticionPaginasMeta | None = None):
    from app.fuentes import paginas_meta as pm
    return {"abriendo": pm.preparar(p.pais if p else "PE")}


@router.post("/competidores/resolver")
def resolver(p: m.PeticionResolver):
    return competidores.resolver(p.buscado, p.anuncios)


# ── IA ────────────────────────────────────────────────────────────────────

@router.post("/ia/clasificar")
def clasificar_lote(p: m.PeticionClasificar):
    return clasificar.clasificar(p.anuncios, referencia=p.referencia, terminos=p.terminos,
                                 con_medios=p.con_medios, modelo=p.modelo)


@router.post("/ia/territorios")
def territorios(p: m.PeticionTerritorios):
    return clasificar.territorios(p.etiquetas, modelo=p.modelo)


@router.post("/ia/territorios-sin-ia")
def territorios_sin_ia(p: m.PeticionTerritorios):
    """Plan B cuando Gemini no responde: agrupa por palabras compartidas."""
    return {"territorios": informe.agrupar_sin_ia([(e, "funcional") for e in p.etiquetas])}


# ── Informe ───────────────────────────────────────────────────────────────

@router.post("/informe/construir")
def construir(p: m.PeticionInforme):
    return informe.construir(p.anuncios, p.territorios, mis_marcas=p.mis_marcas, mis_paginas=p.mis_paginas,
                             sin_anuncios=p.sin_anuncios, identificadas=p.identificadas)


@router.post("/informe/miniaturas")
def miniaturas(p: m.PeticionMiniaturas):
    from app.fuentes import miniaturas as mini
    return mini.descargar([i.model_dump() for i in p.items])


@router.get("/informe/ejemplo")
def ejemplo():
    """Informe de muestra con anuncios inventados: para ver el panel sin claves ni gasto."""
    from app.analisis import ejemplo as datos
    return datos.informe()


# ── KeyWords Explorer ─────────────────────────────────────────────────────

@router.get("/keywords/estado")
def keywords_estado():
    from app.keywords import servicio
    return servicio.estado()


@router.post("/keywords/comprobar")
def keywords_comprobar():
    from app.keywords import google_ads
    return google_ads.comprobar()


@router.post("/keywords/explorar")
def keywords_explorar(p: m.PeticionExplorar):
    from app.keywords import servicio
    return servicio.explorar(p.semillas, p.url, p.pais, p.idioma, p.maximo, p.sugerencias, p.demo)


@router.post("/keywords/resumen")
def keywords_resumen(p: m.PeticionResumenKw):
    from app.keywords import servicio
    return servicio.resumen(p.keyword, p.pais, p.idioma, p.por_pais, p.demo)


@router.post("/keywords/metricas")
def keywords_metricas(p: m.PeticionMetricasKw):
    from app.keywords import servicio
    return {"filas": servicio.metricas_de_lista(p.keywords, p.pais, p.idioma, p.demo)}


# ── Plan SEO ──────────────────────────────────────────────────────────────

@router.post("/seo/descubrir")
def seo_descubrir(p: m.PeticionDescubrir):
    from app.seo import rastreo
    return rastreo.descubrir(p.hosts, p.maximo)


@router.post("/seo/paginas")
def seo_paginas(p: m.PeticionPaginasSeo):
    from app.seo import rastreo
    return rastreo.paginas(p.urls, p.pausa_s)


@router.post("/seo/temas")
def seo_temas(p: m.PeticionTemasSeo):
    from app.seo import ia
    return ia.temas(p.paginas, negocio=p.negocio, rubro=p.rubro, modelo=p.modelo)


@router.post("/seo/agrupar")
def seo_agrupar(p: m.PeticionAgruparSeo):
    from app.seo import ia
    return ia.agrupar(p.keywords, p.grupos, negocio=p.negocio, rubro=p.rubro, modelo=p.modelo)


@router.post("/seo/cobertura")
def seo_cobertura(p: m.PeticionCoberturaSeo):
    from app.seo import ia
    return ia.cobertura(p.grupos, p.propias, modelo=p.modelo)


@router.post("/seo/articulo")
def seo_articulo(p: m.PeticionArticuloSeo):
    from app.seo import ia
    return ia.articulo(p.keyword, p.variantes, p.competidores, p.propias, negocio=p.negocio, rubro=p.rubro,
                       indicaciones=p.indicaciones, modelo=p.modelo)


@router.post("/seo/mejora")
def seo_mejora(p: m.PeticionMejoraSeo):
    from app.seo import ia
    return ia.mejora(p.url, p.actual, [c.model_dump() for c in p.consultas], negocio=p.negocio, rubro=p.rubro,
                    terminos=[t.model_dump() for t in p.terminos], modelo=p.modelo)


@router.post("/seo/rubro")
def seo_rubro(p: m.PeticionRubroSeo):
    from app.seo import ia
    return ia.rubro(p.negocio, p.paginas, modelo=p.modelo)


@router.post("/seo/demanda")
def seo_demanda(p: m.PeticionDemanda):
    """¿La gente lo busca? Lo que Google autocompleta para las keywords de cada grupo."""
    from app.seo import demanda
    return demanda.comprobar([g.model_dump() for g in p.grupos], p.pais, p.idioma)


@router.post("/seo/html")
def seo_html(p: m.PeticionHtml):
    from app.seo import markdown
    return {"html": markdown.a_html(p.contenido), "pendientes": markdown.pendientes(p.contenido)}


@router.get("/gsc")
def gsc_estado():
    from app.seo import search_console
    return search_console.configurado()


@router.post("/gsc/comprobar")
def gsc_comprobar():
    from app.seo import search_console
    return search_console.comprobar()


@router.post("/gsc/consultas")
def gsc_consultas(p: m.PeticionConsultasGsc):
    from app.seo import search_console
    return search_console.consultas(p.dias)


@router.get("/wordpress")
def wordpress_estado():
    from app.seo import wordpress
    return wordpress.configurado()


@router.post("/wordpress/comprobar")
def wordpress_comprobar():
    from app.seo import wordpress
    return wordpress.comprobar()


@router.post("/wordpress/enviar")
def wordpress_enviar(p: m.PeticionWordpress):
    import base64
    from app.seo import markdown, wordpress
    imagen = None
    if p.imagen:
        imagen = {"datos": base64.b64decode(p.imagen.datos_b64), "mime": p.imagen.mime, "alt": p.imagen.alt,
                  "leyenda": p.imagen.leyenda, "id_media": p.imagen.id_media}
    return wordpress.enviar(p.titulo, p.slug, markdown.a_html(p.contenido), p.extracto, p.publicar, p.id_wp, imagen)


# ── Imagen destacada de los articulos ─────────────────────────────────────

@router.get("/imagenes")
def imagenes_estado():
    from app.seo import imagenes
    return imagenes.estado()


@router.post("/imagenes/buscar")
def imagenes_buscar(p: m.PeticionBuscarImagen):
    from app.seo import imagenes
    return imagenes.buscar(p.consulta, p.pagina, p.orientacion)


@router.post("/imagenes/foto")
def imagenes_foto(p: m.PeticionFoto):
    from app.seo import imagenes
    return imagenes.descargar(p.id)


@router.post("/imagenes/generar")
def imagenes_generar(p: m.PeticionGenerarImagen):
    from app.seo import imagenes
    return imagenes.generar(p.descripcion, negocio=p.negocio, rubro=p.rubro, formato=p.formato)


# ── Videos ────────────────────────────────────────────────────────────────

@router.post("/videos/guion")
def videos_guion(p: m.PeticionGuionVideo):
    """Guion por partes de 10 s + copys de Facebook e Instagram (Gemini)."""
    from app.videos import guion
    return guion.guion(p.idea, p.segundos, keyword=p.keyword, contexto=p.contexto.model_dump(), modelo=p.modelo)


@router.post("/videos/prompts")
def videos_prompts(p: m.PeticionPromptsVideo):
    """Los prompts que se escribirán en Vids, clip por clip (sin IA)."""
    from app.videos import guion
    return {"prompts": guion.prompts([x.model_dump() for x in p.partes], p.formato, p.contexto.model_dump())}


@router.get("/videos/vids/navegador")
def videos_navegador():
    from app.videos import vids
    return vids.navegador()


@router.post("/videos/vids/abrir")
def videos_abrir():
    from app.videos import vids
    return vids.abrir_navegador()


@router.post("/videos/vids/lanzar")
def videos_lanzar(p: m.PeticionVidsLanzar):
    from app.videos import guion, vids
    prompts = guion.prompts([x.model_dump() for x in p.partes], p.formato, p.contexto.model_dump())
    return vids.lanzar(p.titulo, prompts, p.formato, p.segundos)


@router.post("/videos/vids/consultar")
def videos_consultar(p: m.PeticionTrabajoVids):
    from app.videos import vids
    return vids.consultar(p.id)


@router.post("/videos/vids/abortar")
def videos_abortar(p: m.PeticionTrabajoVids):
    from app.videos import vids
    return vids.abortar(p.id)


@router.post("/videos/vids/archivo")
def videos_archivo(p: m.PeticionTrabajoVids):
    """El MP4 terminado en base64 (se entrega una sola vez)."""
    from app.videos import vids
    return vids.archivo(p.id)


# ── Publicaciones ─────────────────────────────────────────────────────────

@router.post("/publicaciones/textos")
def publicaciones_textos(p: m.PeticionTextosPublicacion):
    """Un texto para cada red pedida (Facebook, Instagram, LinkedIn) y los hashtags (Gemini)."""
    from app.publicaciones import textos
    return textos.textos(p.idea, p.redes, media=p.media, modo=p.modo, hashtags_base=p.hashtags_base,
                         contexto=p.contexto.model_dump(), modelo=p.modelo)


@router.post("/publicaciones/verificar")
def publicaciones_verificar(p: m.PeticionVerificarPublicacion):
    """Si cada enlace publicado sigue en su red (ACTIVA, NO_DISPONIBLE o SIN_CONFIRMAR)."""
    from app.publicaciones import verificar
    return verificar.verificar(p.enlaces, p.textos)


@router.post("/publicaciones/flyer")
def publicaciones_flyer(p: m.PeticionFlyer):
    """El flyer (JPEG 1080x1350): el fondo con el titulo, el detalle, la llamada a la accion y el logo encima."""
    import base64
    from app.publicaciones import flyer
    datos = flyer.componer(base64.b64decode(p.fondo_b64), p.titulo, p.detalle, p.cta,
                           logo=base64.b64decode(p.logo_b64) if p.logo_b64 else None, color=p.color, acento=p.acento)
    return {"datos_b64": base64.b64encode(datos).decode(), "mime": "image/jpeg"}


# ── Medicion: anuncios de Meta, GA4 y resumen con IA ──

@router.get("/medicion/meta")
def medicion_meta_estado():
    """Si Meta esta configurado y, si lo esta, la cuenta publicitaria."""
    from app.medicion import meta
    c = meta.configurado()
    return {**c, "detalle": meta.cuenta() if c["completo"] else None}


@router.post("/medicion/meta/insights")
def medicion_meta_insights(p: m.PeticionPeriodo):
    from app.medicion import meta
    return meta.insights(p.desde, p.hasta)


@router.get("/medicion/ga4")
def medicion_ga4_estado():
    from app.medicion import ga4
    return ga4.configurado()


@router.get("/medicion/ga4/propiedades")
def medicion_ga4_propiedades():
    from app.medicion import ga4
    return ga4.propiedades()


@router.post("/medicion/ga4/informe")
def medicion_ga4_informe(p: m.PeticionPeriodo):
    from app.medicion import ga4
    return ga4.informe(p.desde, p.hasta)


@router.get("/google/conexion")
def google_conexion(comprobar: bool = False):
    """Si Google (Ads, Search Console, GA4) esta conectado, desde cuando y si el token sigue valido."""
    from app.keywords import conexion
    return conexion.estado(comprobar)


@router.post("/google/conexion")
def google_conectar():
    """Abre la vuelta en 127.0.0.1 y devuelve la direccion de Google para dar permiso."""
    from app.keywords import conexion
    return conexion.iniciar()


@router.post("/medicion/ga4/propiedad")
def medicion_ga4_propiedad(p: m.PeticionPropiedadGa4):
    from app.keywords import conexion
    return conexion.elegir_propiedad(p.propiedad)


@router.post("/medicion/resumen")
def medicion_resumen(p: m.PeticionResumenMedicion):
    from app.medicion import resumen
    return resumen.resumir(p.datos, negocio=p.negocio, rubro=p.rubro, modelo=p.modelo)
