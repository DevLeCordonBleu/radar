# -*- coding: utf-8 -*-
"""
Google Analytics 4 de la web propia (Data API, solo lectura): lo que pasa despues del clic,
por canal, por campana (UTM) y por pagina de entrada, con los eventos clave (conversiones).

Autenticacion: la misma de Google Ads y Search Console (un refresh token con los tres
permisos de `python -m app.keywords.autorizar`). La cuenta de Google que autoriza necesita
acceso de Lector a la propiedad; GA4_PROPIEDAD es su id numerico (p. ej. 123456789).
"""
from __future__ import annotations

import os
import time
from typing import Callable

import httpx

from app.compartido.errores import ErrorExterno
from app.keywords import google_ads

DATOS = "https://analyticsdata.googleapis.com/v1beta"
ADMIN = "https://analyticsadmin.googleapis.com/v1beta"

_http: Callable[[], httpx.Client] = lambda: httpx.Client(timeout=60)  # noqa: E731


def _env(clave: str) -> str:
    return os.environ.get(clave, "").strip()


def propiedad() -> str:
    return _env("GA4_PROPIEDAD").removeprefix("properties/")


def configurado() -> dict:
    """Que falta, sin revelar nada."""
    claves = ["GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_REFRESH_TOKEN", "GA4_PROPIEDAD"]
    faltan = [c for c in claves if not _env(c)]
    return {"completo": not faltan, "faltan": faltan, "propiedad": propiedad() or None}


def traducir_error(estado: int, texto: str) -> str:
    t = (texto or "").lower()
    if "service_disabled" in t or "has not been used in project" in t:
        return ("La API de Google Analytics no está activada en el proyecto de Google Cloud «Radar». Actívala en "
                "console.cloud.google.com → APIs y servicios → Biblioteca: «Google Analytics Data API» y «Google Analytics Admin API».")
    if estado == 403 and ("insufficient" in t or "scope" in t):
        return ("La conexión con Google no incluye Analytics. Vuelve a conectarla en Medición → «Conectar con Google» "
                "y deja marcadas todas las casillas.")
    if estado == 403:
        return (f"Tu cuenta de Google no tiene acceso a la propiedad {propiedad()} de GA4. Pide a quien la administra "
                "(Marketing) que te agregue con el rol «Lector».")
    if estado == 404:
        return f"GA4 no encuentra la propiedad {propiedad()}. Revisa GA4_PROPIEDAD (el id numérico de la propiedad)."
    if estado == 429:
        return "Google Analytics está limitando las consultas. Espera unos minutos y vuelve a intentar."
    if estado == 401:
        return "Google rechazó las credenciales. Vuelve a conectarla en Medición → «Conectar con Google»."
    return f"Google Analytics respondió {estado}: {texto[:200]}"


def _pedir(c: httpx.Client, metodo: str, url: str, cuerpo: dict | None = None) -> dict:
    cab = {"authorization": f"Bearer {google_ads._token_acceso(c)}"}
    for intento in range(3):
        try:
            r = c.request(metodo, url, json=cuerpo, headers=cab)
        except httpx.HTTPError as e:
            raise ErrorExterno(f"No se pudo contactar con Google Analytics: {type(e).__name__}") from e
        if r.status_code in (429, 503) and intento < 2:
            time.sleep(2 * (intento + 1))
            continue
        if not r.is_success:
            raise ErrorExterno(traducir_error(r.status_code, r.text))
        return r.json()
    raise ErrorExterno("Google Analytics no respondió.")


def propiedades() -> dict:
    """Las propiedades de GA4 que ve la cuenta autorizada (para elegir GA4_PROPIEDAD)."""
    for c in ("GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_REFRESH_TOKEN"):
        if not _env(c):
            raise ErrorExterno(f"Falta {c} en 03_worker/.env.")
    with _http() as c:
        d = _pedir(c, "GET", f"{ADMIN}/accountSummaries?pageSize=200")
    vistas = [{"propiedad": p.get("property", "").removeprefix("properties/"), "nombre": p.get("displayName"), "cuenta": a.get("displayName")}
              for a in d.get("accountSummaries", []) for p in a.get("propertySummaries", [])]
    return {"propiedades": vistas, "configurada": propiedad() or None, "ok": any(v["propiedad"] == propiedad() for v in vistas)}


def _filas(d: dict, dimensiones: list[str], metricas: list[str]) -> list[dict]:
    salida = []
    for f in d.get("rows", []):
        fila = {k: v.get("value") for k, v in zip(dimensiones, f.get("dimensionValues", []))}
        for k, v in zip(metricas, f.get("metricValues", [])):
            try:
                n = float(v.get("value") or 0)
            except ValueError:
                n = 0.0
            fila[k] = int(n) if n.is_integer() and k != "engagementRate" else round(n, 4)
        salida.append(fila)
    return salida


# (nombre, dimensiones, metricas, limite)
INFORMES = [
    ("canales", ["sessionDefaultChannelGroup"], ["sessions", "engagedSessions", "keyEvents", "totalUsers"], 20),
    ("campanas", ["sessionSource", "sessionMedium", "sessionCampaignName"], ["sessions", "engagedSessions", "keyEvents"], 50),
    ("paginas", ["landingPage"], ["sessions", "engagedSessions", "keyEvents"], 30),
    ("dias", ["date"], ["sessions", "keyEvents"], 400),
    ("eventos", ["eventName"], ["keyEvents"], 20),
]


def informe(desde: str, hasta: str) -> dict:
    """Sesiones, sesiones con interaccion y eventos clave por canal, campana, pagina de entrada y dia."""
    c = configurado()
    if not c["completo"]:
        raise ErrorExterno("Falta conectar GA4: completa " + ", ".join(c["faltan"]) + " en 03_worker/.env.")
    salida: dict = {"propiedad": propiedad(), "desde": desde, "hasta": hasta}
    with _http() as cli:
        for nombre, dims, mets, limite in INFORMES:
            cuerpo = {"dateRanges": [{"startDate": desde, "endDate": hasta}], "dimensions": [{"name": d} for d in dims],
                      "metrics": [{"name": m} for m in mets], "limit": limite,
                      "orderBys": [{"dimension": {"dimensionName": "date"}}] if nombre == "dias"
                      else [{"metric": {"metricName": mets[0]}, "desc": True}]}
            d = _pedir(cli, "POST", f"{DATOS}/properties/{propiedad()}:runReport", cuerpo)
            filas = _filas(d, dims, mets)
            if nombre == "eventos":
                filas = [f for f in filas if f.get("keyEvents")]
            salida[nombre] = filas
    return salida
