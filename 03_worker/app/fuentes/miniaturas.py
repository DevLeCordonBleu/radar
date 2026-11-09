# -*- coding: utf-8 -*-
"""
Miniaturas de los anuncios para el informe.

Los enlaces de imagen de la Biblioteca de Meta (fbcdn.net) llevan fecha de caducidad
(unos 4 dias): pasado ese plazo el informe se quedaba sin imagenes. Al cerrar el
informe el backend pide aqui cada miniatura, la reduce a un tamaño de tarjeta y la
guarda en su base. Gratis (no hay IA) y sin romper nada: lo que falla se cuenta y
el informe sigue con el enlace original.

Solo se descarga de los CDN de Meta: el worker no baja URLs arbitrarias.
"""
from __future__ import annotations

import base64
import io
from concurrent.futures import ThreadPoolExecutor
from typing import Callable
from urllib.parse import urlsplit

import httpx

from app.ia.medios import tipo

# Los tests sustituyen esto por un cliente con transporte simulado.
_http: Callable[[], httpx.Client] = lambda: httpx.Client(timeout=30, follow_redirects=True)

DOMINIOS = ("fbcdn.net", "facebook.com", "fbsbx.com", "cdninstagram.com")
MAX_BYTES = 15 * 1024 * 1024
LADO = 720
HILOS = 6


def permitida(url: str) -> bool:
    p = urlsplit(url or "")
    host = p.hostname or ""
    return p.scheme == "https" and any(host == d or host.endswith("." + d) for d in DOMINIOS)


def _reducir(datos: bytes) -> bytes:
    """JPEG de como mucho LADO px por lado: una tarjeta no necesita el original."""
    from PIL import Image

    with Image.open(io.BytesIO(datos)) as im:
        im.thumbnail((LADO, LADO))
        if im.mode != "RGB":
            fondo = Image.new("RGB", im.size, "white")
            fondo.paste(im.convert("RGBA"), mask=im.convert("RGBA").split()[-1])
            im = fondo
        salida = io.BytesIO()
        im.save(salida, "JPEG", quality=82, optimize=True, progressive=True)
        return salida.getvalue()


def _una(c: httpx.Client, url: str) -> bytes | None:
    try:
        r = c.get(url)
    except httpx.HTTPError:
        return None
    if not r.is_success or len(r.content) > MAX_BYTES or not (tipo(r.content) or "").startswith("image/"):
        return None
    try:
        return _reducir(r.content)
    except Exception:  # noqa: BLE001 - una imagen corrupta no debe parar las demas
        return None


def descargar(items: list[dict]) -> dict:
    """items = [{id, url}] -> {miniaturas: [{id, datos_b64, mime}], fallidas, caducadas}"""
    validos = [i for i in items if i.get("id") and permitida(i.get("url") or "")]
    with _http() as c, ThreadPoolExecutor(HILOS) as pool:
        datos = list(pool.map(lambda i: _una(c, i["url"]), validos))
    hechas = [{"id": i["id"], "datos_b64": base64.b64encode(d).decode(), "mime": "image/jpeg"} for i, d in zip(validos, datos) if d]
    return {"miniaturas": hechas, "fallidas": len(items) - len(hechas)}
