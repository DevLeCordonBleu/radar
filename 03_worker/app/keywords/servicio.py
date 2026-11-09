# -*- coding: utf-8 -*-
"""
Une las piezas del explorador: elige entre Google Ads y los datos de demostracion
y arma el resultado. Sin estado: el backend guarda las busquedas y las listas.
"""
from __future__ import annotations

from app.compartido.errores import ErrorExterno
from . import analisis, demo as datos_demo, geo, google_ads, sugerencias as autocompletado


def explorar(semillas: list[str], url: str | None, pais: str, idioma: str, maximo: int = 1000,
             con_sugerencias: bool = True, demo: bool = False) -> dict:
    semillas = [s.strip() for s in semillas if s.strip()]
    if not semillas and not url:
        raise ErrorExterno("Escribe al menos una palabra o una URL.")
    geo.geo(pais)
    geo.idioma(idioma)

    if demo:
        ideas = datos_demo.ideas(semillas, url, pais, maximo)
        sugeridas = datos_demo.sugerencias(semillas) if con_sugerencias else []
        conocidas = {(i.get("text") or "").lower() for i in ideas}
        met = datos_demo.metricas([s for s in sugeridas if s.lower() not in conocidas], pais)
        moneda = "USD"
    else:
        ideas = google_ads.ideas(semillas, url, pais, idioma, maximo)
        sugeridas = autocompletado.buscar(semillas, pais, idioma) if con_sugerencias and semillas else []
        conocidas = {(i.get("text") or "").lower() for i in ideas}
        faltan = [s for s in sugeridas if s.lower() not in conocidas]
        try:
            met = google_ads.metricas(faltan, pais, idioma) if faltan else {}
        except ErrorExterno:
            met = {}        # las sugerencias quedan sin volumen, pero las ideas siguen valiendo
        moneda = google_ads.moneda()

    resultado = analisis.construir(semillas, ideas, sugeridas, met)
    resultado.update({
        "demo": demo, "semillas": semillas, "url": url, "pais": pais.upper(), "idioma": idioma.lower(), "moneda": moneda,
        "volumen_agrupado": analisis.volumen_agrupado(resultado["filas"]),
    })
    if not resultado["filas"]:
        raise ErrorExterno("Google no devolvió ideas para esa búsqueda. Prueba con otra palabra, otro país o desactiva el filtro de idioma.")
    return resultado


def resumen(keyword: str, pais: str, idioma: str, por_pais: bool = False, demo: bool = False) -> dict:
    keyword = keyword.strip()
    if not keyword:
        raise ErrorExterno("Escribe una keyword.")
    geo.geo(pais)
    geo.idioma(idioma)
    fuente = (lambda ks, p: datos_demo.metricas(ks, p)) if demo else (lambda ks, p: google_ads.metricas(ks, p, idioma))
    m = fuente([keyword], pais).get(keyword.lower())
    r = analisis.resumen(keyword, m)
    r.update({"demo": demo, "pais": pais.upper(), "idioma": idioma.lower(), "moneda": "USD" if demo else google_ads.moneda(),
              "encontrada": m is not None})
    if por_pais:
        filas = []
        for codigo in geo.PAISES_RESUMEN:
            try:
                mp = fuente([keyword], codigo).get(keyword.lower()) or {}
            except ErrorExterno:
                continue
            filas.append({"pais": codigo, "nombre": geo.PAISES[codigo]["nombre"], "volumen": analisis._entero(mp.get("avgMonthlySearches"))})
        r["por_pais"] = sorted(filas, key=lambda x: -(x["volumen"] or 0))
    return r


def metricas_de_lista(keywords: list[str], pais: str, idioma: str, demo: bool = False) -> list[dict]:
    """Filas actualizadas para refrescar una lista guardada."""
    geo.geo(pais)
    geo.idioma(idioma)
    m = datos_demo.metricas(keywords, pais) if demo else google_ads.metricas(keywords, pais, idioma)
    salida = [analisis.fila(k, m.get(k.strip().lower())) for k in keywords]
    return salida


def estado() -> dict:
    c = google_ads.configurado()
    return {"google_ads": c, "paises": {k: v["nombre"] for k, v in geo.PAISES.items()}, "idiomas": {k: v["nombre"] for k, v in geo.IDIOMAS.items()}}
