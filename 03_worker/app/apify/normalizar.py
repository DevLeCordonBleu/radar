# -*- coding: utf-8 -*-
"""
Convierte lo que devuelve el actor de Apify a un anuncio con nuestros nombres.

El actor ha cambiado de formato mas de una vez, asi que cada campo se busca en
varias rutas (de la mas probable a la menos). Si un dia el proveedor cambia
sus nombres, se arregla anadiendo la ruta nueva a CAMPOS y nada mas.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from html import unescape

CAMPOS = {
    "ad_id": ["ad_archive_id", "adArchiveID", "adArchiveId", "ad_id", "adId", "id"],
    "anunciante": ["page_name", "pageName", "advertiser_name", "advertiserName", "page.name"],
    "page_id": ["page_id", "pageId", "page.id"],
    "fecha_inicio": ["start_date", "startDate", "ad_delivery_start_time", "startDateFormatted"],
    "activo": ["is_active", "isActive", "active"],
    "formato": ["display_format", "displayFormat", "media_type", "mediaType", "snapshot.display_format"],
    "copy": ["ad_creative_body", "body", "bodyText", "adCreativeBody", "snapshot.body.text", "caption"],
    "cta": ["cta_text", "ctaText", "call_to_action_type", "snapshot.cta_text"],
    "enlace": ["link_url", "linkUrl", "snapshot.link_url", "snapshot.cards.0.link_url"],
    "imagen": ["image_url", "imageUrl", "original_image_url", "snapshot.images.0.original_image_url",
               "snapshot.images.0.resized_image_url", "snapshot.cards.0.original_image_url",
               "snapshot.cards.0.resized_image_url"],
    "video": ["video_hd_url", "videoHdUrl", "video_sd_url", "snapshot.videos.0.video_hd_url",
              "snapshot.videos.0.video_sd_url", "snapshot.cards.0.video_hd_url", "snapshot.cards.0.video_sd_url"],
    "portada": ["video_preview_image_url", "videoPreviewImageUrl", "snapshot.videos.0.video_preview_image_url",
                "snapshot.cards.0.video_preview_image_url"],
    "snapshot": ["ad_library_url", "ad_snapshot_url", "adSnapshotUrl"],
    "avatar": ["snapshot.page_profile_picture_url", "page_profile_picture_url"],
    "plataformas": ["publisher_platform", "publisherPlatform", "publisher_platforms", "publisherPlatforms"],
    "copy_reserva": ["snapshot.cards.0.body", "snapshot.title", "snapshot.link_description", "snapshot.cards.0.title"],
}

# Redes de Meta donde sale el anuncio, en el orden en que se muestran.
PLATAFORMAS = ("facebook", "instagram", "messenger", "whatsapp", "threads", "audience_network")

_CATALOGO = re.compile(r"^(DPA|CATALOG)", re.I)
_VARIAS_VERSIONES = re.compile(r"^(DCO|MULTI_IMAGES)", re.I)
# Texto con plantillas de catalogo: {{product.name}}
_PLANTILLA = re.compile(r"\{\{[^}]+\}\}")


class FormatoInesperado(Exception):
    """El actor devolvio datos que no se reconocen: hay que revisar CAMPOS."""


def _ruta(obj, ruta: str):
    for parte in ruta.split("."):
        if obj is None:
            return None
        if isinstance(obj, list):
            try:
                obj = obj[int(parte)]
            except (ValueError, IndexError):
                return None
        elif isinstance(obj, dict):
            obj = obj.get(parte)
        else:
            return None
    return obj


def _campo(item: dict, clave: str):
    for ruta in CAMPOS[clave]:
        v = _ruta(item, ruta)
        if v is not None and v != "":
            return v
    return None


def _texto(v) -> str:
    """Texto plano: sin HTML ni entidades."""
    t = re.sub(r"<[^>]+>", " ", unescape(str(v)))
    return re.sub(r"[ \t]+", " ", re.sub(r"[ \t]+\n", "\n", t)).strip()


def _url(v) -> str | None:
    return v if isinstance(v, str) and v.startswith("http") else None


def _fecha(v) -> str:
    if isinstance(v, (int, float)):
        seg = v / 1000 if v > 0xE8D4A51000 else v
        return datetime.fromtimestamp(seg, timezone.utc).date().isoformat()
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            pass
    return datetime.now(timezone.utc).date().isoformat()


def _plataformas(v) -> list[str] | None:
    """["FACEBOOK", "INSTAGRAM"] -> ["facebook", "instagram"]; None si no viene (no se sabe)."""
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, list):
        return None
    vistas = {str(p).strip().lower().replace(" ", "_") for p in v if p}
    return [p for p in PLATAFORMAS if p in vistas] + sorted(vistas - set(PLATAFORMAS))


def _tarjetas(item: dict) -> list[dict] | None:
    cards = _ruta(item, "snapshot.cards")
    if not isinstance(cards, list) or len(cards) < 2:
        return None
    salida = []
    for c in cards[:10]:
        t = {
            "imagen_url": _url(next((c.get(k) for k in ("original_image_url", "resized_image_url") if c.get(k)), None)),
            "video_url": _url(next((c.get(k) for k in ("video_hd_url", "video_sd_url") if c.get(k)), None)),
            "portada_url": _url(c.get("video_preview_image_url")),
            "titulo": _texto(c["title"])[:300] if c.get("title") else None,
            "texto": _texto(c["body"])[:300] if c.get("body") else None,
        }
        if t["imagen_url"] or t["video_url"] or t["portada_url"]:
            salida.append(t)
    return salida or None


def anuncio(item: dict) -> dict | None:
    """Un item del actor -> anuncio nuestro, o None si no trae id o anunciante."""
    ad_id, anunciante = _campo(item, "ad_id"), _campo(item, "anunciante")
    if not ad_id or not anunciante:
        return None
    formato = _campo(item, "formato")
    formato = None if formato is None else str(formato)
    copia = str(_campo(item, "copy") or "")
    es_plantilla = bool(_PLANTILLA.search(copia))
    copia = "" if es_plantilla else _texto(copia)
    if not copia.strip():
        reserva = _campo(item, "copy_reserva")
        copia = _texto(reserva) if isinstance(reserva, str) and not _PLANTILLA.search(reserva) else ""
    ad_id = str(ad_id)
    cta = _campo(item, "cta")
    return {
        "ad_id": ad_id,
        "anunciante": str(anunciante),
        "page_id": None if _campo(item, "page_id") is None else str(_campo(item, "page_id")),
        "fecha_inicio": _fecha(_campo(item, "fecha_inicio")),
        "activo": _campo(item, "activo") is not False,
        "formato_origen": formato,
        "copy": copia,
        "cta_texto": None if cta is None else str(cta),
        "enlace": _url(_campo(item, "enlace")),
        "imagen_url": _url(_campo(item, "imagen")),
        "video_url": _url(_campo(item, "video")),
        "video_portada_url": _url(_campo(item, "portada")),
        "snapshot_url": f"https://www.facebook.com/ads/library/?id={ad_id}",
        "avatar_url": _url(_campo(item, "avatar")),
        "plataformas": _plataformas(_campo(item, "plataformas")),
        "es_catalogo": es_plantilla or bool(formato and _CATALOGO.match(formato)) or None,
        "varias_versiones": (not es_plantilla and bool(formato and _VARIAS_VERSIONES.match(formato))) or None,
        "tarjetas": _tarjetas(item),
    }


_SIN_RESULTADOS = re.compile(r"ads not found|no ads found|no results", re.I)


def lote(items: list[dict]) -> tuple[list[dict], str | None]:
    """
    Normaliza los items de un dataset. Devuelve (anuncios, error).
    Un actor que no encuentra nada devuelve items con solo `error`: eso es "vacio",
    no un fallo. Si TODOS traen otro error, se propaga el mensaje.
    """
    con_error = [i for i in items if isinstance(i.get("error"), str)]
    buenos = [i for i in items if not isinstance(i.get("error"), str)]
    if con_error and not buenos:
        real = next((i["error"] for i in con_error if not _SIN_RESULTADOS.search(i["error"])), None)
        return [], real
    anuncios = [a for a in (anuncio(i) for i in buenos) if a]
    if buenos and not anuncios:
        raise FormatoInesperado(
            "El buscador de anuncios ha devuelto datos en un formato inesperado. Si sigue pasando, "
            "el proveedor ha cambiado su formato: revisar CAMPOS en app/apify/normalizar.py.")
    return anuncios, None


def unicos(anuncios: list[dict]) -> list[dict]:
    """Un anuncio puede salir en varias busquedas: se queda con la de menor nivel (mas directa)."""
    mejor: dict[str, dict] = {}
    for a in anuncios:
        previo = mejor.get(a["ad_id"])
        if not previo or a.get("nivel", 9) < previo.get("nivel", 9):
            mejor[a["ad_id"]] = a
    # Todos los anuncios de un anunciante heredan su mejor nivel.
    nivel: dict[str, int] = {}
    for a in mejor.values():
        n = a.get("nivel", 3)
        if a["anunciante"] not in nivel or n < nivel[a["anunciante"]]:
            nivel[a["anunciante"]] = n
    return [{**a, "nivel": nivel[a["anunciante"]]} for a in mejor.values()]
