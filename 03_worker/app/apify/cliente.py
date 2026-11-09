# -*- coding: utf-8 -*-
"""
Cliente de Apify para la Biblioteca de Anuncios de Meta.

Lanzar una busqueda es asincrono: se crea una ejecucion ("run"), se consulta
hasta que termine y entonces se descargan los items. Con varios tokens, si uno
no tiene credito se prueba el siguiente (`agotados` dice cuales fallaron).
"""
from __future__ import annotations

import os
from urllib.parse import urlencode

import httpx

from app.compartido.errores import ErrorExterno

API = "https://api.apify.com/v2"
ACTOR = "curious_coder~facebook-ads-library-scraper"
TOPE_EJECUCION_S = 900
MAX_ANUNCIOS = 500


def tokens() -> list[str]:
    vistos = []
    for k in ("APIFY_TOKEN", "APIFY_TOKEN_2"):
        v = os.environ.get(k, "").strip()
        if v and v not in vistos:
            vistos.append(v)
    return vistos


def _cab(token: str) -> dict:
    return {"authorization": f"Bearer {token}"}


def url_biblioteca(valor: str, modo: str, pais: str, solo_activos: bool = True) -> str:
    """
    URL de busqueda en la Biblioteca de Anuncios.
    modo: "pagina" (id de pagina: exacto), "marca" (frase exacta) o "palabras" (sin orden).
    """
    p = {"active_status": "active" if solo_activos else "all", "ad_type": "all", "country": pais, "media_type": "all"}
    if modo == "pagina":
        p |= {"view_all_page_id": valor, "search_type": "page"}
    else:
        p |= {"q": valor, "search_type": "keyword_exact_phrase" if modo == "marca" else "keyword_unordered"}
    return "https://www.facebook.com/ads/library/?" + urlencode(p)


def lanzar(terminos: list[dict], pais: str = "PE", maximo: int = 100, solo_activos: bool = True) -> dict:
    """terminos = [{valor, modo}]. Devuelve {run, t, agotados} o lanza ErrorExterno."""
    if not terminos:
        raise ErrorExterno("No hay nada que buscar.")
    if not 1 <= maximo <= MAX_ANUNCIOS:
        raise ErrorExterno(f"El máximo de anuncios va de 1 a {MAX_ANUNCIOS}.")
    toks = tokens()
    if not toks:
        raise ErrorExterno("Falta el token de Apify. Ponlo en 03_worker/.env (APIFY_TOKEN).")
    cuerpo = {
        "urls": [{"url": url_biblioteca(t["valor"], t.get("modo", "marca"), pais, solo_activos), "method": "GET"}
                 for t in terminos],
        "count": max(10, maximo),
        "limitPerSource": max(5, -(-max(10, maximo) // len(terminos))),
        "scrapeAdDetails": True,
        "scrapePageAds.countryCode": pais,
        "scrapePageAds.activeStatus": "active" if solo_activos else "all",
    }
    agotados: list[int] = []
    for i, tok in enumerate(toks):
        r = httpx.post(f"{API}/acts/{ACTOR}/runs", params={"timeout": TOPE_EJECUCION_S}, json=cuerpo,
                       headers=_cab(tok), timeout=45)
        if r.status_code in (402, 429):
            agotados.append(i)
            continue
        if r.status_code in (401, 403):
            raise ErrorExterno("Apify ha rechazado el token. Revisa que esté bien copiado en 03_worker/.env.")
        if not r.is_success:
            raise ErrorExterno(f"El buscador de anuncios ha fallado (Apify {r.status_code}). Prueba en unos minutos.")
        run = (r.json().get("data") or {}).get("id")
        if not run:
            raise ErrorExterno("El buscador de anuncios no ha devuelto la ejecución. Prueba en unos minutos.")
        return {"run": run, "t": i, "agotados": agotados}
    raise ErrorExterno("Todos los tokens de Apify están sin crédito o con demasiadas ejecuciones simultáneas. "
                       "Espera unos minutos o añade otro token.")


def consultar(run: str, t: int) -> dict:
    """{estado: "corriendo", anuncios?} o {estado: "listo", items: [...]}."""
    toks = tokens()
    if not 0 <= t < len(toks):
        raise ErrorExterno("Petición no válida: token de Apify desconocido.")
    cab = _cab(toks[t])
    r = httpx.get(f"{API}/actor-runs/{run}", headers=cab, timeout=30)
    if r.status_code in (401, 403):
        raise ErrorExterno("Apify ha rechazado el token.")
    if r.status_code == 404:
        raise ErrorExterno("La búsqueda de anuncios ya no existe en Apify. Vuelve a lanzarla.")
    if not r.is_success:
        raise ErrorExterno(f"No se pudo consultar el buscador de anuncios (Apify {r.status_code}).")
    d = r.json().get("data") or {}
    estado = d.get("status", "")
    if estado == "SUCCEEDED" and d.get("defaultDatasetId"):
        it = httpx.get(f"{API}/datasets/{d['defaultDatasetId']}/items",
                       params={"clean": "true", "format": "json", "limit": MAX_ANUNCIOS}, headers=cab, timeout=120)
        if not it.is_success:
            raise ErrorExterno(f"No se pudieron descargar los anuncios (Apify {it.status_code}).")
        return {"estado": "listo", "items": it.json()}
    if estado in ("READY", "RUNNING", "TIMING-OUT", "ABORTING"):
        n = None
        if d.get("defaultDatasetId"):
            try:
                ds = httpx.get(f"{API}/datasets/{d['defaultDatasetId']}", headers=cab, timeout=15)
                n = (ds.json().get("data") or {}).get("itemCount") if ds.is_success else None
            except httpx.HTTPError:
                pass
        return {"estado": "corriendo", "anuncios": n}
    if estado == "TIMED-OUT":
        raise ErrorExterno("El buscador de anuncios ha tardado demasiado y se ha cancelado. "
                           "Prueba con menos competidores o vuelve a intentarlo.")
    raise ErrorExterno(f"El buscador de anuncios no ha podido terminar ({estado or 'estado desconocido'}). "
                       "Prueba de nuevo en unos minutos.")


def abortar(run: str, t: int) -> None:
    toks = tokens()
    if 0 <= t < len(toks):
        try:
            httpx.post(f"{API}/actor-runs/{run}/abort", headers=_cab(toks[t]), timeout=15)
        except httpx.HTTPError:
            pass


def comprobar(token: str) -> dict:
    """{ok, detalle}: valida el token y dice cuanto credito queda."""
    try:
        r = httpx.get(f"{API}/users/me/limits", headers=_cab(token), timeout=10)
    except httpx.HTTPError:
        return {"ok": False, "detalle": "No se ha podido contactar con Apify. Prueba en un minuto."}
    if r.status_code in (401, 403):
        return {"ok": False, "detalle": "Apify no reconoce ese token. Cópialo otra vez desde Settings → API & Integrations."}
    if not r.is_success:
        return {"ok": False, "detalle": f"Apify no responde ahora mismo ({r.status_code}). Prueba en un minuto."}
    d = r.json().get("data") or {}
    tope = (d.get("limits") or {}).get("maxMonthlyUsageUsd")
    usado = (d.get("current") or {}).get("monthlyUsageUsd")
    if isinstance(tope, (int, float)) and isinstance(usado, (int, float)):
        resta = max(0.0, tope - usado)
        return {"ok": True, "detalle": f"Token válido · te quedan {resta:.2f} US$ este mes (unos {int(resta * 100 // 7)} informes)"}
    return {"ok": True, "detalle": "Token válido"}
