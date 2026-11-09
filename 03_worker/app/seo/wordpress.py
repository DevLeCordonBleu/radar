# -*- coding: utf-8 -*-
"""
Envio de articulos a WordPress por su API REST (wp-json/wp/v2/posts).

Autenticacion: usuario + «contraseña de aplicación» de WordPress (Usuarios > Perfil >
Contraseñas de aplicación), que viven solo en 03_worker/.env. Es distinta de la
contraseña con la que la persona entra al escritorio y se puede revocar sola.

Una entrada nueva llega como borrador salvo que se pida publicar. Al actualizar una
que ya existe no se toca su estado si no se pide publicar: un «enviar borrador» no
despublica lo que alguien ya publico desde WordPress.
"""
from __future__ import annotations

import os
from typing import Callable
from urllib.parse import urlsplit

import httpx

from app.compartido.errores import ErrorExterno

# Los tests sustituyen esto por un cliente con transporte simulado.
_http: Callable[[], httpx.Client] = lambda: httpx.Client(timeout=40, follow_redirects=True)

CLAVES = {"url": "WP_URL", "usuario": "WP_USUARIO", "clave": "WP_CLAVE_APLICACION"}


def _env(clave: str) -> str:
    return os.environ.get(clave, "").strip()


def _base() -> str:
    return _env("WP_URL").rstrip("/")


def configurado() -> dict:
    """Que falta, sin revelar la clave."""
    faltan = [CLAVES[k] for k in CLAVES if not _env(CLAVES[k])]
    return {"completo": not faltan, "faltan": faltan, "sitio": _base() or None, "usuario": _env("WP_USUARIO") or None}


def _exigir() -> tuple[str, tuple[str, str]]:
    c = configurado()
    if not c["completo"]:
        raise ErrorExterno("Falta conectar WordPress: completa " + ", ".join(c["faltan"]) + " en 03_worker/.env y reinicia el Radar "
                           "(guía en Plan SEO → Artículos).")
    base = _base()
    p = urlsplit(base)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise ErrorExterno(f"WP_URL tiene que ser la dirección de tu web, como https://tusitio.com (ahora: {base}).")
    if p.scheme == "http" and p.hostname not in ("localhost", "127.0.0.1"):
        raise ErrorExterno("WP_URL usa http: la contraseña viajaría sin cifrar. Usa la dirección con https://.")
    # Las contraseñas de aplicacion se muestran con espacios; WordPress las acepta con o sin ellos.
    return base, (_env("WP_USUARIO"), _env("WP_CLAVE_APLICACION").replace(" ", ""))


class ErrorWordpress(ErrorExterno):
    """Respuesta de error de WordPress; `codigo` es su campo `code` (rest_post_invalid_id...)."""

    def __init__(self, mensaje: str, estado: int = 0, codigo: str = ""):
        super().__init__(mensaje)
        self.estado, self.codigo = estado, codigo


def _error(r: httpx.Response, base: str) -> ErrorWordpress:
    try:
        d = r.json()
        codigo, mensaje = d.get("code", ""), d.get("message", "")
    except ValueError:
        codigo, mensaje = "", r.text[:200]
    e = lambda texto: ErrorWordpress(texto, r.status_code, codigo)
    if r.status_code == 401 or codigo in ("invalid_username", "incorrect_password", "rest_not_logged_in"):
        return e("WordPress no acepta el usuario o la contraseña de aplicación de 03_worker/.env. "
                 "Revisa WP_USUARIO y crea una contraseña de aplicación nueva en tu perfil de WordPress.")
    if r.status_code == 403:
        return e(f"WordPress no deja a {_env('WP_USUARIO')} hacer esto: su rol no puede crear o publicar entradas ni subir imágenes ({mensaje}).")
    if codigo == "rest_post_invalid_id":
        return e("La entrada que se envió antes ya no existe en WordPress (¿la borraron?). "
                 "Pulsa «Desvincular de WordPress» y vuelve a enviarla.")
    if r.status_code == 404:
        return e(f"No se encontró la API de WordPress en {base}/wp-json/. Revisa WP_URL o si un plugin de seguridad la bloquea.")
    if r.status_code == 413:
        return e("WordPress rechazó la imagen por su tamaño (límite de subida del servidor).")
    return e(f"WordPress respondió {r.status_code}: {mensaje or codigo}"[:300])


def _pedir(metodo: str, ruta: str, cuerpo: dict | None = None, *, datos: bytes | None = None,
           cabeceras: dict | None = None) -> dict:
    base, auth = _exigir()
    try:
        with _http() as c:
            if datos is None:
                r = c.request(metodo, f"{base}/wp-json/wp/v2/{ruta}", json=cuerpo, auth=auth)
            else:
                r = c.request(metodo, f"{base}/wp-json/wp/v2/{ruta}", content=datos, headers=cabeceras, auth=auth)
    except httpx.HTTPError as e:
        raise ErrorExterno(f"No se pudo conectar con {base}: {type(e).__name__}. Revisa WP_URL y que la web esté en línea.") from e
    if not 200 <= r.status_code < 300:
        raise _error(r, base)
    try:
        return r.json()
    except ValueError as e:
        raise ErrorExterno(f"{base} no respondió como WordPress (¿WP_URL apunta a la web correcta?).") from e


def comprobar() -> dict:
    """Entra con las credenciales y dice si ese usuario puede crear y publicar entradas."""
    u = _pedir("GET", "users/me?context=edit")
    capacidades = u.get("capabilities") or {}
    return {"ok": True, "sitio": _base(), "usuario": u.get("name") or u.get("slug"),
            "puede_crear": bool(capacidades.get("edit_posts")), "puede_publicar": bool(capacidades.get("publish_posts")),
            "puede_subir": bool(capacidades.get("upload_files"))}


_EXTENSION = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
# Bloque dinamico de WordPress: se pinta con la imagen destacada de la entrada.
BLOQUE_DESTACADA = "<!-- wp:post-featured-image /-->\n\n"


def _media(imagen: dict, nombre: str) -> dict:
    """
    Sube la imagen a la biblioteca de medios (o reutiliza la ya subida) y le pone alt y leyenda.
    imagen = {datos, mime, alt, leyenda, id_media}. -> {id, url}
    """
    textos = {"alt_text": imagen.get("alt") or "", "caption": imagen.get("leyenda") or ""}
    if imagen.get("id_media"):
        try:
            r = _pedir("POST", f"media/{imagen['id_media']}", textos)
            return {"id": r.get("id"), "url": r.get("source_url")}
        except ErrorWordpress as e:
            # La borraron de la biblioteca: se sube otra vez.
            if not (e.estado == 404 or e.codigo == "rest_post_invalid_id"):
                raise
    archivo = f"{nombre or 'imagen'}.{_EXTENSION.get(imagen['mime'], 'jpg')}"
    r = _pedir("POST", "media", datos=imagen["datos"],
               cabeceras={"Content-Type": imagen["mime"], "Content-Disposition": f'attachment; filename="{archivo}"'})
    r = _pedir("POST", f"media/{r.get('id')}", textos)
    return {"id": r.get("id"), "url": r.get("source_url")}


def enviar(titulo: str, slug: str, html: str, extracto: str, publicar: bool, id_wp: int | None = None,
           imagen: dict | None = None) -> dict:
    """
    Crea la entrada (o actualiza la que ya se envio). Con `imagen`, la deja como imagen destacada.
    -> {id, estado, enlace, editar, media: {id, url} | None}
    """
    cuerpo = {"title": titulo, "slug": slug, "content": html, "excerpt": extracto}
    if publicar:
        cuerpo["status"] = "publish"
    elif id_wp is None:
        cuerpo["status"] = "draft"
    media = _media(imagen, slug) if imagen else None
    if media:
        cuerpo["featured_media"] = media["id"]
        if _env("WP_DESTACADA_EN_TEXTO").lower() not in ("no", "false", "0"):
            # La plantilla de entradas de ilcb.edu.pe no pinta la destacada: el equipo pone este
            # bloque al inicio del texto (como en sus noticias). Con un tema que si la pinta, se
            # desactiva con WP_DESTACADA_EN_TEXTO=no para no verla dos veces.
            cuerpo["content"] = BLOQUE_DESTACADA + html
    r = _pedir("POST", f"posts/{id_wp}" if id_wp else "posts", cuerpo)
    return {"id": r.get("id"), "estado": r.get("status"), "enlace": r.get("link"),
            "editar": f"{_base()}/wp-admin/post.php?post={r.get('id')}&action=edit", "media": media}
