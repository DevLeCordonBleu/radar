# -*- coding: utf-8 -*-
"""
Si un post publicado sigue en su red: se abre su enlace como un navegador sin sesion y se
mira la respuesta. Tres resultados:

- ACTIVA: responde y muestra el texto publicado.
- NO_DISPONIBLE: la red dice que ya no existe (404/410 o «contenido no disponible»).
- SIN_CONFIRMAR: no se puede saber sin iniciar sesion (Facebook e Instagram suelen pedirla)
  o la red no respondio. No es una baja: lo confirmara la API de Meta cuando se conecte n8n.

Solo lee paginas publicas: no inicia sesion ni esquiva bloqueos.
"""
from __future__ import annotations

import html
import re
import unicodedata

import httpx

NAVEGADOR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
             "Chrome/124.0 Safari/537.36")
# La red redirige aqui cuando hace falta iniciar sesion para ver el post.
_LOGIN = ("/login", "login.php", "accounts/login", "authwall", "/checkpoint", "uas/login")
_NO_DISPONIBLE = (
    "this content isn't available", "this content isn't available right now", "este contenido no esta disponible",
    "sorry, this page isn't available", "esta pagina no esta disponible", "this page isn't available",
    "this post is unavailable", "this post has been removed", "esta publicacion no esta disponible", "page not found",
)
_OG_DESCRIPCION = re.compile(r"""<meta[^>]+(?:property|name)=["'](?:og:description|description)["'][^>]*content=["']([^"']*)""", re.I)


def _plano(t: str) -> str:
    t = unicodedata.normalize("NFD", html.unescape(t or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _muestra(texto: str) -> str:
    """Las primeras palabras del texto publicado, para reconocerlo en la pagina."""
    return " ".join(_plano(texto).split()[:8])


def verificar(enlaces: dict[str, str], textos: dict[str, str] | None = None, *, cliente: httpx.Client | None = None) -> dict:
    """enlaces: {red: url}; textos: {red: lo publicado} -> {resultados: {red: {estado, detalle, http}}}"""
    textos = textos or {}
    c = cliente or httpx.Client(headers={"User-Agent": NAVEGADOR, "Accept-Language": "es-PE,es;q=0.9"},
                                follow_redirects=True, timeout=20)
    try:
        return {"resultados": {red: _una(c, url, textos.get(red, "")) for red, url in enlaces.items()}}
    finally:
        if cliente is None:
            c.close()


def _una(c: httpx.Client, url: str, texto: str) -> dict:
    try:
        r = c.get(url)
    except httpx.HTTPError as e:
        return {"estado": "SIN_CONFIRMAR", "detalle": f"No se pudo abrir el enlace ({type(e).__name__}).", "http": None}
    final = str(r.url).lower()
    if r.status_code in (404, 410):
        return {"estado": "NO_DISPONIBLE", "detalle": f"La red responde que ya no existe (HTTP {r.status_code}).", "http": r.status_code}
    if any(m in final for m in _LOGIN):
        return {"estado": "SIN_CONFIRMAR", "detalle": "La red pide iniciar sesión para verla: no se puede saber desde fuera.", "http": r.status_code}
    cuerpo = _plano(r.text[:500_000])
    if any(_plano(m) in cuerpo for m in _NO_DISPONIBLE):
        return {"estado": "NO_DISPONIBLE", "detalle": "La red muestra «contenido no disponible».", "http": r.status_code}
    if r.status_code >= 400:
        return {"estado": "SIN_CONFIRMAR", "detalle": f"La red respondió HTTP {r.status_code}.", "http": r.status_code}
    muestra = _muestra(texto)
    descripciones = " ".join(_plano(d) for d in _OG_DESCRIPCION.findall(r.text[:500_000]))
    if muestra and (muestra in descripciones or muestra in cuerpo):
        return {"estado": "ACTIVA", "detalle": "Responde y muestra el texto publicado.", "http": r.status_code}
    return {"estado": "SIN_CONFIRMAR", "detalle": "Responde, pero sin iniciar sesión no muestra el texto: no se puede confirmar.",
            "http": r.status_code}
