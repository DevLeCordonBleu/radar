# -*- coding: utf-8 -*-
"""
Descarga la imagen o el video de un anuncio y lo prepara para Gemini.

Las URLs de la Biblioteca de Meta caducan y pesan, asi que: se valida que el
archivo llego entero (una imagen cortada confunde al modelo), se reduce lo que
pasa de ~1,5 MB y se descarta lo que no cabe. Un medio que falla no rompe el
analisis: ese anuncio se clasifica solo por su texto.
"""
from __future__ import annotations

import base64
import io

import httpx

MAX_VIDEO = 18 * 1024 * 1024
MAX_IMAGEN_BYTES = 1_500_000
LADO_MAXIMO = 1536
ACEPTADOS = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif", "video/mp4", "video/webm", "video/quicktime"}


def tipo(b: bytes) -> str | None:
    """Tipo MIME por los primeros bytes (la cabecera HTTP de un CDN no es de fiar)."""
    if len(b) < 12:
        return None
    if b[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp"
    if b[:3] == b"GIF":
        return "image/gif"
    if b[4:8] == b"ftyp":
        marca = b[8:12]
        if marca[:4] in (b"avif", b"avis"):
            return "image/avif"
        if marca in (b"heic", b"heix", b"hevc", b"mif1", b"msf1", b"heif"):
            return "image/heic"
        return "video/quicktime" if marca == b"qt  " else "video/mp4"
    if b[:4] == b"\x1a\x45\xdf\xa3":
        return "video/webm"
    return None


def _reducir(b: bytes) -> bytes | None:
    """A JPEG de hasta 1536 px por el lado largo. None si no se puede decodificar."""
    try:
        from PIL import Image
        with Image.open(io.BytesIO(b)) as im:
            im = im.convert("RGB")
            im.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
            salida = io.BytesIO()
            im.save(salida, "JPEG", quality=85)
            return salida.getvalue()
    except Exception:  # noqa: BLE001 - cualquier fallo de decodificacion es "no se pudo"
        return None


def preparar(b: bytes) -> dict | None:
    t = tipo(b)
    if not t:
        return None
    if t.startswith("image/") and (t not in ACEPTADOS or len(b) > MAX_IMAGEN_BYTES):
        r = _reducir(b)
        return {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(r).decode()}} if r else None
    if t not in ACEPTADOS:
        return None
    return {"inline_data": {"mime_type": t, "data": base64.b64encode(b).decode()}}


def descargar(url: str, cliente: httpx.Client | None = None) -> dict | None:
    """Parte `inline_data` lista para Gemini, o None si no se pudo."""
    c = cliente or httpx.Client(follow_redirects=True, timeout=25)
    try:
        for _ in range(2):
            try:
                r = c.get(url)
            except httpx.HTTPError:
                continue
            if r.status_code != 200 or not r.content or len(r.content) > MAX_VIDEO:
                return None
            esperado = r.headers.get("content-length")
            if esperado and esperado.isdigit() and int(esperado) != len(r.content) and r.headers.get("content-encoding") is None:
                continue  # llego cortado: un reintento
            return preparar(r.content)
        return None
    finally:
        if cliente is None:
            c.close()
