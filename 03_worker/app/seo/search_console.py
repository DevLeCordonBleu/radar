# -*- coding: utf-8 -*-
"""
Google Search Console de la web propia: por que busquedas aparece ya en Google, con
clics, impresiones y posicion media. Es la unica fuente con cifras reales de la web
propia; no dice nada de las busquedas en las que no aparece.

Autenticacion: la misma de Google Ads (GOOGLE_ADS_CLIENT_ID/SECRET y el refresh token
de `python -m app.keywords.autorizar`, que pide los dos permisos). La cuenta de Google
que autoriza necesita acceso (basta «Restringido», solo lectura) a la propiedad.
"""
from __future__ import annotations

import os
import time
import urllib.parse
from datetime import date, timedelta
from typing import Callable

import httpx

from app.compartido.errores import ErrorExterno
from app.keywords import google_ads

API = "https://www.googleapis.com/webmasters/v3"
# Los datos de los ultimos dias aun no estan consolidados.
RETRASO_DIAS = 3
POR_PAGINA = 25_000
MAX_PAGINAS = 4

_http: Callable[[], httpx.Client] = lambda: httpx.Client(timeout=60)  # noqa: E731


def _env(clave: str) -> str:
    return os.environ.get(clave, "").strip()


def propiedad() -> str:
    return _env("GSC_PROPIEDAD")


def configurado() -> dict:
    """Que falta, sin revelar nada."""
    claves = {"client_id": "GOOGLE_ADS_CLIENT_ID", "client_secret": "GOOGLE_ADS_CLIENT_SECRET",
              "refresh_token": "GOOGLE_ADS_REFRESH_TOKEN", "propiedad": "GSC_PROPIEDAD"}
    faltan = [v for v in claves.values() if not _env(v)]
    return {"completo": not faltan, "faltan": faltan, "propiedad": propiedad() or None, "pais": _env("GSC_PAIS") or None}


def _exigir():
    c = configurado()
    if not c["completo"]:
        raise ErrorExterno("Falta conectar Search Console: completa " + ", ".join(c["faltan"]) + " en 03_worker/.env.")


def traducir_error(estado: int, texto: str) -> str:
    t = texto or ""
    if estado == 403 and ("insufficient" in t.lower() or "scope" in t.lower()):
        return ("La autorización no incluye Search Console. Vuelve a conectar en Medición → «Conectar con Google» "
                "y deja marcadas todas las casillas.")
    if estado == 403:
        return (f"Tu cuenta de Google no tiene acceso a {propiedad()} en Search Console. Pide a quien la administra "
                "que te agregue como usuario (basta permiso «Restringido»).")
    if estado == 404:
        return f"Search Console no encuentra la propiedad {propiedad()}. Revisa GSC_PROPIEDAD (p. ej. sc-domain:ilcb.edu.pe)."
    if estado == 429:
        return "Search Console está limitando las peticiones. Espera unos minutos y vuelve a intentar."
    if estado == 401:
        return "Google rechazó las credenciales. Vuelve a conectarla en Medición → «Conectar con Google»."
    return f"Search Console respondió {estado}: {t[:200]}"


def _pedir(cliente: httpx.Client, metodo: str, ruta: str, cuerpo: dict | None = None) -> dict:
    cab = {"authorization": f"Bearer {google_ads._token_acceso(cliente)}"}
    for intento in range(3):
        try:
            r = cliente.request(metodo, API + ruta, json=cuerpo, headers=cab)
        except httpx.HTTPError as e:
            raise ErrorExterno(f"No se pudo contactar con Search Console: {e}") from e
        if r.status_code in (429, 503) and intento < 2:
            time.sleep(2 * (intento + 1))
            continue
        if not r.is_success:
            raise ErrorExterno(traducir_error(r.status_code, r.text))
        return r.json()
    raise ErrorExterno("Search Console no respondió.")


def comprobar() -> dict:
    """Que propiedades ve la cuenta autorizada y si la configurada esta entre ellas."""
    _exigir()
    with _http() as c:
        sitios = _pedir(c, "GET", "/sites").get("siteEntry", [])
    vistas = [{"propiedad": s.get("siteUrl"), "permiso": s.get("permissionLevel")} for s in sitios]
    mia = next((s for s in vistas if s["propiedad"] == propiedad()), None)
    return {"ok": bool(mia and mia["permiso"] != "siteUnverifiedUser"), "propiedad": propiedad(),
            "permiso": mia["permiso"] if mia else None, "propiedades": vistas}


def rango(dias: int, hoy: date | None = None) -> tuple[str, str]:
    fin = (hoy or date.today()) - timedelta(days=RETRASO_DIAS)
    return (fin - timedelta(days=dias - 1)).isoformat(), fin.isoformat()


def consultas(dias: int = 90) -> dict:
    """
    Consultas x pagina de los ultimos `dias` (hasta hace RETRASO_DIAS). Google solo
    devuelve las filas principales: no es un censo de todas las busquedas.
    """
    _exigir()
    desde, hasta = rango(dias)
    cuerpo: dict = {"startDate": desde, "endDate": hasta, "dimensions": ["query", "page"], "rowLimit": POR_PAGINA, "dataState": "final"}
    if _env("GSC_PAIS"):
        cuerpo["dimensionFilterGroups"] = [{"filters": [{"dimension": "country", "operator": "equals", "expression": _env("GSC_PAIS").lower()}]}]
    ruta = f"/sites/{urllib.parse.quote(propiedad(), safe='')}/searchAnalytics/query"
    filas: list[dict] = []
    with _http() as c:
        for pagina in range(MAX_PAGINAS):
            r = _pedir(c, "POST", ruta, {**cuerpo, "startRow": pagina * POR_PAGINA})
            lote = r.get("rows", [])
            filas += [{"consulta": f["keys"][0], "url": f["keys"][1], "clics": int(f.get("clicks", 0)),
                       "impresiones": int(f.get("impressions", 0)), "ctr": round(float(f.get("ctr", 0)), 4),
                       "posicion": round(float(f.get("position", 0)), 1)} for f in lote]
            if len(lote) < POR_PAGINA:
                break
    return {"propiedad": propiedad(), "desde": desde, "hasta": hasta, "pais": _env("GSC_PAIS") or None, "filas": filas}
