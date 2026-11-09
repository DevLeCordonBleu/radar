# -*- coding: utf-8 -*-
"""
Cliente REST de Google Ads para Keyword Planner (sin el SDK, que pesa mucho).

Dos metodos de KeywordPlanIdeaService:
  - generateKeywordIdeas: a partir de palabras semilla y/o una URL, devuelve ideas
    con volumen mensual, tendencia de 12 meses, competencia de anuncios y puja.
  - generateKeywordHistoricalMetrics: las mismas metricas para una lista exacta.

Lo que Keyword Planner NO da (a diferencia de Ahrefs): dificultad organica (KD),
clics, resultados de la SERP, tema principal. El modulo no los inventa.

Autenticacion: OAuth2 con refresh token (ver autorizar.py) + developer token.
Los enteros de 64 bits llegan como texto en el JSON de Google.
"""
from __future__ import annotations

import os
import time
from typing import Callable

import httpx

from app.compartido.errores import ErrorExterno
from . import geo

TOKEN_URL = "https://oauth2.googleapis.com/token"
MESES = {m: i for i, m in enumerate(
    ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"], 1)}
MAX_SEMILLAS = 20
LOTE_METRICAS = 700
MAX_PAGINAS = 5

# Los tests sustituyen esto por un cliente con transporte simulado.
_http: Callable[[], httpx.Client] = lambda: httpx.Client(timeout=60)

_acceso: dict = {"token": None, "expira": 0.0}
_moneda: dict = {}


def _env(clave: str) -> str:
    return os.environ.get(clave, "").strip()


def configurado() -> dict:
    """Que falta, sin revelar nada."""
    claves = {
        "developer_token": "GOOGLE_ADS_DEVELOPER_TOKEN", "client_id": "GOOGLE_ADS_CLIENT_ID",
        "client_secret": "GOOGLE_ADS_CLIENT_SECRET", "refresh_token": "GOOGLE_ADS_REFRESH_TOKEN",
        "customer_id": "GOOGLE_ADS_CUSTOMER_ID",
    }
    faltan = [k for k, v in claves.items() if not _env(v)]
    return {"completo": not faltan, "faltan": faltan, "version": version(),
            "cuenta": _cuenta()[-4:] if _env("GOOGLE_ADS_CUSTOMER_ID") else None,
            "con_manager": bool(_env("GOOGLE_ADS_LOGIN_CUSTOMER_ID"))}


def version() -> str:
    v = _env("GOOGLE_ADS_API_VERSION") or "v24"
    return v if v.startswith("v") else f"v{v}"


def _cuenta() -> str:
    return _env("GOOGLE_ADS_CUSTOMER_ID").replace("-", "")


def _exigir():
    c = configurado()
    if not c["completo"]:
        nombres = {"developer_token": "GOOGLE_ADS_DEVELOPER_TOKEN", "client_id": "GOOGLE_ADS_CLIENT_ID",
                   "client_secret": "GOOGLE_ADS_CLIENT_SECRET", "refresh_token": "GOOGLE_ADS_REFRESH_TOKEN",
                   "customer_id": "GOOGLE_ADS_CUSTOMER_ID"}
        raise ErrorExterno("Falta conectar Google Ads: completa " + ", ".join(nombres[f] for f in c["faltan"])
                           + " en 03_worker/.env (guía en KeyWords Explorer → Conectar Google Ads).")


def _token_acceso(cliente: httpx.Client) -> str:
    if _acceso["token"] and _acceso["expira"] > time.time() + 60:
        return _acceso["token"]
    try:
        r = cliente.post(TOKEN_URL, data={
            "client_id": _env("GOOGLE_ADS_CLIENT_ID"), "client_secret": _env("GOOGLE_ADS_CLIENT_SECRET"),
            "refresh_token": _env("GOOGLE_ADS_REFRESH_TOKEN"), "grant_type": "refresh_token"})
    except httpx.HTTPError as e:
        raise ErrorExterno(f"No se pudo contactar con Google para autorizar: {e}") from e
    if not r.is_success:
        d = r.text
        if "invalid_grant" in d:
            prueba = os.environ.get("GOOGLE_APP_PRUEBA", "").strip().lower() not in ("false", "0", "no")
            raise ErrorExterno("La conexión con Google venció o fue revocada"
                               + (" (mientras el proyecto «Radar» de Google Cloud esté en modo Prueba, Google la corta cada 7 días)"
                                  if prueba else "")
                               + ". Vuelve a conectarla en Medición → «Conectar con Google».")
        if "invalid_client" in d:
            raise ErrorExterno("Google no reconoce el GOOGLE_ADS_CLIENT_ID / CLIENT_SECRET. Revísalos en Google Cloud → Credenciales.")
        raise ErrorExterno(f"Google no dio acceso ({r.status_code}): {d[:200]}")
    datos = r.json()
    _acceso["token"] = datos["access_token"]
    _acceso["expira"] = time.time() + int(datos.get("expires_in", 3600))
    return _acceso["token"]


def traducir_error(estado: int, texto: str) -> str:
    """Mensaje para la persona; el detalle de Google se conserva al final."""
    t = texto or ""
    resto = ""
    try:
        import json
        e = json.loads(t).get("error", {})
        detalles = [x for d in e.get("details", []) for x in d.get("errors", [])]
        resto = (detalles[0].get("message") if detalles else e.get("message")) or ""
    except Exception:  # noqa: BLE001
        resto = t[:200]
    # Desde 2026 el nivel de acceso es del proyecto de Google Cloud, no del Centro de API.
    if "DEVELOPER_TOKEN_NOT_APPROVED" in t and "explorer access" in t:
        return ("El acceso Explorador de la API de Google Ads no permite Keyword Planner. Pide acceso Básico en "
                "Google Cloud → APIs y servicios → Google Ads API (proyecto del OAuth).")
    if "DEVELOPER_TOKEN_NOT_APPROVED" in t or ("ACTION_NOT_PERMITTED" in t and "test accounts" in t):
        return ("La API de Google Ads solo tiene acceso de prueba, que únicamente funciona con cuentas de prueba. "
                "Pide acceso Explorer o Básico en Google Cloud → APIs y servicios → Google Ads API (proyecto del OAuth).")
    if "DEVELOPER_TOKEN_INVALID" in t or "DEVELOPER_TOKEN_PROHIBITED" in t:
        return "Google no acepta el GOOGLE_ADS_DEVELOPER_TOKEN. Cópialo de nuevo desde el Centro de API de la cuenta administradora."
    if "USER_PERMISSION_DENIED" in t or "CUSTOMER_NOT_FOUND" in t:
        return ("El usuario que autorizó no tiene acceso a esa cuenta. Revisa GOOGLE_ADS_CUSTOMER_ID y, si entras por una cuenta "
                "administradora, GOOGLE_ADS_LOGIN_CUSTOMER_ID.")
    if "CUSTOMER_NOT_ENABLED" in t:
        return "La cuenta de Google Ads no está activa (hace falta haber completado su configuración inicial)."
    if "RESOURCE_EXHAUSTED" in t or "RATE_EXCEEDED" in t or estado == 429:
        return "Google Ads está limitando las peticiones. Espera un minuto y vuelve a intentar."
    if estado == 401:
        return "Google rechazó las credenciales. Vuelve a conectarla en Medición → «Conectar con Google»."
    if estado == 404:
        return (f"Google respondió 404: la versión {version()} de la API ya no existe o la ruta cambió. "
                "Sube GOOGLE_ADS_API_VERSION (p. ej. v25) y reinicia el worker.")
    return f"Google Ads respondió {estado}: {resto or t[:200]}"


def _llamar(metodo: str, cuerpo: dict, cliente: httpx.Client) -> dict:
    _exigir()
    cab = {"authorization": f"Bearer {_token_acceso(cliente)}", "developer-token": _env("GOOGLE_ADS_DEVELOPER_TOKEN"),
           "content-type": "application/json"}
    if _env("GOOGLE_ADS_LOGIN_CUSTOMER_ID"):
        cab["login-customer-id"] = _env("GOOGLE_ADS_LOGIN_CUSTOMER_ID").replace("-", "")
    url = f"https://googleads.googleapis.com/{version()}/customers/{_cuenta()}{metodo}"
    for intento in range(3):
        try:
            r = cliente.post(url, json=cuerpo, headers=cab)
        except httpx.HTTPError as e:
            raise ErrorExterno(f"No se pudo contactar con Google Ads: {e}") from e
        if r.status_code in (429, 503) and intento < 2:
            time.sleep(2 * (intento + 1))
            continue
        if not r.is_success:
            raise ErrorExterno(traducir_error(r.status_code, r.text))
        return r.json()
    raise ErrorExterno("Google Ads no respondió.")


# ── Metodos ───────────────────────────────────────────────────────────────

def cuerpo_ideas(semillas: list[str], url: str | None, pais: str, idioma: str, tamano: int) -> dict:
    cuerpo: dict = {
        "language": geo.idioma(idioma), "geoTargetConstants": [geo.geo(pais)], "keywordPlanNetwork": "GOOGLE_SEARCH",
        "includeAdultKeywords": False, "pageSize": tamano, "keywordAnnotation": ["KEYWORD_CONCEPT"],
    }
    if semillas and url:
        cuerpo["keywordAndUrlSeed"] = {"url": url, "keywords": semillas}
    elif semillas:
        cuerpo["keywordSeed"] = {"keywords": semillas}
    elif url:
        cuerpo["urlSeed"] = {"url": url}
    else:
        raise ErrorExterno("Indica al menos una palabra o una URL.")
    return cuerpo


def ideas(semillas: list[str], url: str | None, pais: str, idioma: str, maximo: int = 1000) -> list[dict]:
    """Ideas crudas de Google, hasta `maximo`."""
    if len(semillas) > MAX_SEMILLAS:
        raise ErrorExterno(f"Máximo {MAX_SEMILLAS} palabras semilla por búsqueda.")
    cuerpo = cuerpo_ideas(semillas, url, pais, idioma, min(maximo, 1000))
    salida: list[dict] = []
    with _http() as c:
        for _ in range(MAX_PAGINAS):
            d = _llamar(":generateKeywordIdeas", cuerpo, c)
            salida += d.get("results", [])
            token = d.get("nextPageToken")
            if not token or len(salida) >= maximo:
                break
            cuerpo = {**cuerpo, "pageToken": token}
    return salida[:maximo]


def metricas(keywords: list[str], pais: str | None, idioma: str) -> dict[str, dict]:
    """Metricas exactas de una lista. `pais=None` = todos los paises. Devuelve {texto: keywordMetrics + closeVariants}."""
    salida: dict[str, dict] = {}
    unicas = list(dict.fromkeys(k.strip().lower() for k in keywords if k.strip()))   # Google no distingue mayusculas
    with _http() as c:
        for i in range(0, len(unicas), LOTE_METRICAS):
            cuerpo: dict = {"keywords": unicas[i:i + LOTE_METRICAS], "language": geo.idioma(idioma),
                            "keywordPlanNetwork": "GOOGLE_SEARCH", "includeAdultKeywords": False}
            if pais:
                cuerpo["geoTargetConstants"] = [geo.geo(pais)]
            d = _llamar(":generateKeywordHistoricalMetrics", cuerpo, c)
            for r in d.get("results", []):
                m = dict(r.get("keywordMetrics") or {})
                m["closeVariants"] = r.get("closeVariants", [])
                salida[(r.get("text") or "").strip().lower()] = m
    return salida


def moneda() -> str | None:
    """Codigo de moneda de la cuenta (las pujas vienen en ella)."""
    cuenta = _cuenta()
    if cuenta in _moneda:
        return _moneda[cuenta]
    try:
        with _http() as c:
            d = _llamar("/googleAds:search", {"query": "SELECT customer.currency_code FROM customer LIMIT 1"}, c)
        _moneda[cuenta] = d["results"][0]["customer"]["currencyCode"]
    except (ErrorExterno, KeyError, IndexError):
        return None
    return _moneda[cuenta]


def comprobar() -> dict:
    """{ok, detalle}: autoriza y pide las metricas de una palabra de prueba."""
    c = configurado()
    if not c["completo"]:
        return {"ok": False, "detalle": "Falta: " + ", ".join(c["faltan"]) + "."}
    try:
        m = metricas(["marketing digital"], "ES", "es")
    except ErrorExterno as e:
        return {"ok": False, "detalle": str(e)}
    v = next(iter(m.values()), {}).get("avgMonthlySearches")
    return {"ok": True, "detalle": f"Conectado a la cuenta …{c['cuenta']} · API {c['version']}"
            + (f" · prueba: «marketing digital» en España = {int(v):,} búsquedas/mes".replace(",", ".") if v else "")}
