# -*- coding: utf-8 -*-
"""
Imagen destacada de un articulo: foto de un banco gratuito o imagen generada con Gemini (de pago).

Fotos: Pixabay (PIXABAY_API_KEY) y, si no hay esa clave, Pexels (PEXELS_API_KEY; en
2026-10 Pexels no da claves nuevas). Ambas de uso libre, tambien comercial. Solo se
descargan fotos por su id y desde el dominio del banco: el worker no baja URLs que
lleguen de fuera. Pixabay exige descargar la imagen (no enlazarla desde su web) y
guardar en cache las busquedas 24 h: por eso `_cache`.

Gemini: la API no tiene plan gratuito para imagenes (ningun modelo). Sin facturacion en el
proyecto de Google responde 429 con limite 0 y aqui se explica asi. Una imagen por llamada,
sin reintentos largos: es una peticion del panel y la persona espera mirando.
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
from typing import Callable
from urllib.parse import urlsplit

import httpx

from app.compartido.errores import ErrorExterno
from app.ia import gemini

# Los tests sustituyen esto por un cliente con transporte simulado.
_http: Callable[[], httpx.Client] = lambda: httpx.Client(timeout=40, follow_redirects=True)

PEXELS = "https://api.pexels.com/v1"
PIXABAY = "https://pixabay.com/api/"
POR_PAGINA = 15
MAX_BYTES = 12 * 1024 * 1024
CACHE_S = 24 * 3600
_cache: dict[tuple, tuple[float, dict]] = {}

# US$ por imagen de 1K (ai.google.dev/gemini-api/docs/pricing, consultado 2026-10-28).
PRECIOS = {"gemini-3.1-flash-lite-image": 0.0336, "gemini-3.1-flash-image": 0.067, "gemini-nano-banana-2.1": 0.0336}
MODELO_POR_DEFECTO = "gemini-3.1-flash-lite-image"

ESTILO = """Fotografía editorial realista para la imagen destacada de un artículo del blog de {negocio} ({rubro}).
Qué debe mostrar: {descripcion}
Requisitos: formato horizontal; luz natural; composición limpia y profesional. Sin texto, letras, números,
logotipos, marcas de agua ni rótulos. Si aparecen personas, que no haya rostros en primer plano."""

# Fondo de un flyer: el Radar escribe encima el titulo y pone el logo, asi que la parte de abajo
# tiene que quedar despejada y la imagen no lleva texto (los modelos lo escriben mal).
ESTILO_FLYER = """Fotografía realista para el fondo de un flyer de redes sociales de {negocio} ({rubro}).
Qué debe mostrar: {descripcion}
Requisitos: formato vertical; luz cálida y atractiva; el motivo principal en la mitad superior y la mitad inferior
más simple y despejada, porque encima irá texto. Sin texto, letras, números, logotipos, marcas de agua ni rótulos.
Si aparecen personas, que no haya rostros en primer plano."""


def _clave_pexels() -> str:
    return os.environ.get("PEXELS_API_KEY", "").strip()


def _clave_pixabay() -> str:
    return os.environ.get("PIXABAY_API_KEY", "").strip()


def banco() -> str | None:
    """El banco de fotos en uso: Pixabay si tiene clave; si no, Pexels."""
    return "PIXABAY" if _clave_pixabay() else "PEXELS" if _clave_pexels() else None


def modelo_imagen() -> str:
    m = os.environ.get("GEMINI_MODELO_IMAGEN", "").strip()
    return m if m in PRECIOS else MODELO_POR_DEFECTO


def estado() -> dict:
    """Que fuentes hay configuradas, sin revelar claves."""
    m = modelo_imagen()
    return {"fotos": banco(), "gemini": bool(gemini.claves()), "modelo": m, "precio_usd": PRECIOS[m]}


def tipo_de(datos: bytes) -> str | None:
    if datos.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if datos.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "image/webp"
    return None


# ── Bancos de fotos ──────────────────────────────────────────────────────

def _exigir_banco() -> str:
    fuente = banco()
    if not fuente:
        raise ErrorExterno("Falta la clave del banco de fotos: crea una gratis en pixabay.com (la ves en "
                           "pixabay.com/api/docs con la sesión iniciada), ponla en 03_worker/.env como "
                           "PIXABAY_API_KEY y reinicia el Radar.")
    return fuente


def buscar(consulta: str, pagina: int = 1, orientacion: str = "horizontal") -> dict:
    """-> {fotos, total, pagina, hay_mas, fuente}. Cada foto: id, autor, miniatura, pagina_url...
    `orientacion` horizontal (imagen destacada) o vertical (fondo de flyer)."""
    fuente = _exigir_banco()
    vertical = orientacion == "vertical"
    clave = (fuente, consulta.strip().lower(), pagina, vertical)
    guardada = _cache.get(clave)
    if guardada and time.time() - guardada[0] < CACHE_S:
        return guardada[1]
    r = {**(_buscar_pixabay if fuente == "PIXABAY" else _buscar_pexels)(consulta, pagina, vertical), "fuente": fuente}
    _cache[clave] = (time.time(), r)
    return r


def descargar(id_foto: int) -> dict:
    """La foto elegida, en el tamaño de una imagen destacada, con sus créditos y `datos_b64`."""
    fuente = _exigir_banco()
    f, url, dominio = (_foto_pixabay_por_id if fuente == "PIXABAY" else _foto_pexels_por_id)(id_foto)
    host = urlsplit(url).hostname or ""
    if host != dominio and not host.endswith("." + dominio):
        raise ErrorExterno("El banco de fotos devolvió una dirección de imagen inesperada; no se descargó.")
    try:
        with _http() as c:
            r = c.get(url)
    except httpx.HTTPError as e:
        raise ErrorExterno(f"No se pudo descargar la foto: {type(e).__name__}.") from e
    if not r.is_success:
        raise ErrorExterno(f"El banco de fotos respondió {r.status_code} al descargar la foto.")
    datos = r.content
    mime = tipo_de(datos)
    if not mime or len(datos) > MAX_BYTES:
        raise ErrorExterno("Lo que se descargó no es una imagen válida.")
    return {**f, "fuente": fuente, "datos_b64": base64.b64encode(datos).decode(), "mime": mime}


# Pixabay: la clave va en la URL (?key=); los mensajes de error no la repiten.

def _pixabay(params: dict) -> dict:
    try:
        with _http() as c:
            r = c.get(PIXABAY, params={"key": _clave_pixabay(), **params})
    except httpx.HTTPError as e:
        raise ErrorExterno(f"No se pudo conectar con Pixabay: {type(e).__name__}.") from e
    if r.status_code == 400 and re.search(r"key", r.text, re.I):
        raise ErrorExterno("Pixabay no acepta la clave de 03_worker/.env (PIXABAY_API_KEY). Cópiala otra vez de pixabay.com/api/docs.")
    if r.status_code == 429:
        raise ErrorExterno("Pixabay limita las búsquedas (100 por minuto): espera un momento y vuelve a buscar.")
    if not r.is_success:
        raise ErrorExterno(f"Pixabay respondió {r.status_code}.")
    try:
        return r.json()
    except ValueError as e:
        raise ErrorExterno("Pixabay devolvió una respuesta inesperada.") from e


def _foto_pixabay(h: dict) -> dict:
    usuario, id_usuario = h.get("user") or "", h.get("user_id")
    return {"id": h.get("id"), "ancho": h.get("imageWidth"), "alto": h.get("imageHeight"), "autor": usuario,
            "autor_url": f"https://pixabay.com/users/{usuario}-{id_usuario}/" if usuario and id_usuario else "",
            "pagina_url": h.get("pageURL") or "", "alt": h.get("tags") or "",
            "miniatura": h.get("webformatURL") or h.get("previewURL") or "", "previa": h.get("largeImageURL") or ""}


def _buscar_pixabay(consulta: str, pagina: int, vertical: bool = False) -> dict:
    d = _pixabay({"q": consulta[:100], "lang": "es", "image_type": "photo", "orientation": "vertical" if vertical else "horizontal",
                  "safesearch": "true", "per_page": POR_PAGINA, "page": pagina})
    total = d.get("totalHits") or 0
    return {"fotos": [_foto_pixabay(h) for h in d.get("hits") or []], "total": total, "pagina": pagina,
            "hay_mas": pagina * POR_PAGINA < total}


def _foto_pixabay_por_id(id_foto: int) -> tuple[dict, str, str]:
    hits = _pixabay({"id": id_foto}).get("hits") or []
    if not hits:
        raise ErrorExterno("Esa foto ya no está en Pixabay. Busca otra.")
    f = _foto_pixabay(hits[0])
    return f, f["previa"], "pixabay.com"


# Pexels

def _pexels(ruta: str, params: dict | None = None) -> dict:
    clave = _clave_pexels()
    try:
        with _http() as c:
            r = c.get(f"{PEXELS}/{ruta}", params=params, headers={"Authorization": clave})
    except httpx.HTTPError as e:
        raise ErrorExterno(f"No se pudo conectar con Pexels: {type(e).__name__}.") from e
    if r.status_code in (401, 403):
        raise ErrorExterno("Pexels no acepta la clave de 03_worker/.env (PEXELS_API_KEY). Revísala en pexels.com/api.")
    if r.status_code == 404:
        raise ErrorExterno("Esa foto ya no está en Pexels. Busca otra.")
    if r.status_code == 429:
        raise ErrorExterno("Pexels limita las búsquedas por hora: espera un rato y vuelve a buscar.")
    if not r.is_success:
        raise ErrorExterno(f"Pexels respondió {r.status_code}.")
    return r.json()


def _foto(f: dict) -> dict:
    src = f.get("src") or {}
    return {"id": f.get("id"), "ancho": f.get("width"), "alto": f.get("height"), "autor": f.get("photographer") or "",
            "autor_url": f.get("photographer_url") or "", "pagina_url": f.get("url") or "", "alt": f.get("alt") or "",
            "miniatura": src.get("medium") or src.get("small") or "", "previa": src.get("landscape") or src.get("large") or ""}


def _buscar_pexels(consulta: str, pagina: int, vertical: bool = False) -> dict:
    d = _pexels("search", {"query": consulta, "per_page": POR_PAGINA, "page": pagina,
                           "orientation": "portrait" if vertical else "landscape", "locale": "es-ES"})
    return {"fotos": [_foto(f) for f in d.get("photos") or []], "total": d.get("total_results") or 0, "pagina": pagina,
            "hay_mas": bool(d.get("next_page"))}


def _foto_pexels_por_id(id_foto: int) -> tuple[dict, str, str]:
    """En 1200x627 (src.landscape, el tamaño de una imagen destacada)."""
    f = _foto(_pexels(f"photos/{id_foto}"))
    return f, f["previa"], "images.pexels.com"


# ── Gemini ───────────────────────────────────────────────────────────────

def _cuerpo(prompt: str, con_tamano: bool, proporcion: str = "16:9") -> dict:
    config = {"aspectRatio": proporcion, **({"imageSize": "1K"} if con_tamano else {})}
    return {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": config}}


def _error_gemini(estado: int, texto: str) -> ErrorExterno:
    d = gemini._detalle(texto)
    if estado == 429 and (d["cero"] or d["gratuito"]):
        return ErrorExterno("Gemini no genera imágenes en el plan gratuito: activa la facturación en el proyecto de Google de "
                            "tu clave (aistudio.google.com) o usa una foto del banco gratuito.")
    if d["saldo"]:
        return ErrorExterno("La cuenta de Google de tu clave de Gemini se quedó sin saldo o llegó a su tope de gasto.")
    if estado == 429:
        return ErrorExterno("Gemini está limitando las peticiones de imagen. Espera un minuto y vuelve a intentarlo.")
    if estado == 404:
        return ErrorExterno(f"Tu clave no tiene acceso al modelo {modelo_imagen()}. Cambia GEMINI_MODELO_IMAGEN en 03_worker/.env.")
    return gemini._error_final(estado, texto)


def generar(descripcion: str, *, negocio: str = "", rubro: str = "", formato: str = "HORIZONTAL") -> dict:
    """`formato` HORIZONTAL (imagen destacada, 16:9) o VERTICAL (fondo de flyer, 4:5)."""
    modelo = modelo_imagen()
    vertical = formato.upper() == "VERTICAL"
    prompt = (ESTILO_FLYER if vertical else ESTILO).format(negocio=negocio or "el negocio", rubro=rubro or "su rubro",
                                                           descripcion=descripcion.strip())
    proporcion = "4:5" if vertical else "16:9"
    estado_http, texto = gemini._una_peticion(modelo, _cuerpo(prompt, True, proporcion))
    if estado_http == 400 and re.search(r"image_?size", texto, re.I):
        # Hay modelos que no aceptan elegir el tamaño: se pide sin él.
        estado_http, texto = gemini._una_peticion(modelo, _cuerpo(prompt, False, proporcion))
    if not 200 <= estado_http < 300:
        raise _error_gemini(estado_http, texto)
    try:
        d = json.loads(texto)
        candidato = (d.get("candidates") or [{}])[0]
        partes = (candidato.get("content") or {}).get("parts") or []
    except (ValueError, AttributeError) as e:
        raise ErrorExterno("Gemini devolvió una respuesta incompleta. Vuelve a intentarlo.") from e
    for p in partes:
        bloque = p.get("inlineData") or p.get("inline_data")
        if bloque and bloque.get("data"):
            datos = base64.b64decode(bloque["data"])
            mime = tipo_de(datos)
            if not mime:
                raise ErrorExterno("Gemini devolvió algo que no es una imagen.")
            u = d.get("usageMetadata") or {}
            uso = {"tokens_entrada": u.get("promptTokenCount", 0), "tokens_salida": u.get("candidatesTokenCount", 0),
                   "llamadas": 1, "modelo": modelo, "costo_usd": PRECIOS[modelo]}
            return {"datos_b64": base64.b64encode(datos).decode(), "mime": mime, "modelo": modelo, "prompt": prompt, "uso": uso}
    motivo = candidato.get("finishReason") or (d.get("promptFeedback") or {}).get("blockReason") or "sin motivo"
    raise ErrorExterno(f"Gemini no devolvió ninguna imagen ({motivo}). Cambia la descripción y vuelve a intentarlo.")
