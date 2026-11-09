# -*- coding: utf-8 -*-
"""
Texto de una publicacion (Gemini): uno por red (Facebook, Instagram y LinkedIn) o el mismo para
todas, mas los hashtags y los textos del flyer (titulo, detalle, llamada a la accion y que foto
buscar de fondo).

Los hashtags del tema los propone la IA; los generales del rubro (lista que mantiene Marketing)
se ponen delante y no se repiten. Las reglas son las de los guiones de video: solo datos
confirmados y «[FALTA: …]» en lo que no se sabe, sin precios ni promesas.
"""
from __future__ import annotations

from pathlib import Path

from app.compartido.errores import ErrorExterno
from app.ia import gemini
from app.videos.guion import NEGOCIO_POR_DEFECTO, RUBRO_POR_DEFECTO, limpiar_hashtags

PROMPTS = Path(__file__).parent / "prompts"
REDES = ("FACEBOOK", "INSTAGRAM", "LINKEDIN")
# Lo que admite cada red (Instagram cuenta tambien los hashtags).
LIMITES = {"FACEBOOK": 5000, "INSTAGRAM": 2200, "LINKEDIN": 3000}
MAX_HASHTAGS = 12
_MEDIA = {"NINGUNA": "solo texto", "IMAGEN": "con una imagen", "VIDEO": "con un video corto (Reel)"}
_MODO = {"POR_RED": "un texto por red", "MISMO": "el mismo texto para todas"}
_FLYER = {"titulo": 45, "detalle": 60, "cta": 25, "busqueda": 60, "fondo": 300}


def textos(idea: str, redes: list[str], *, media: str = "NINGUNA", modo: str = "POR_RED", hashtags_base: list[str] | None = None,
           contexto: dict | None = None, modelo: str | None = None) -> dict:
    """-> {titulo, textos: {RED: texto}, hashtags, flyer: {titulo, detalle, cta, busqueda, fondo}, uso}. Solo las redes pedidas."""
    pedidas = [r for r in REDES if r in {x.upper() for x in redes}]
    if not pedidas:
        raise ErrorExterno("Elige al menos una red: Facebook, Instagram o LinkedIn.")
    mismo = modo.upper() == "MISMO"
    base = limpiar_hashtags(hashtags_base, 30)
    c = contexto or {}
    sistema = ((PROMPTS / "PUBLICACION.md").read_text(encoding="utf-8")
               .replace("{{NEGOCIO}}", (c.get("negocio") or "").strip() or NEGOCIO_POR_DEFECTO)
               .replace("{{RUBRO}}", (c.get("rubro") or "").strip() or RUBRO_POR_DEFECTO))
    texto = (f"Idea: {idea.strip()}\n"
             f"Redes: {', '.join(pedidas)}\n"
             f"Modo: {_MODO['MISMO' if mismo else 'POR_RED']}\n"
             f"Formato: {_MEDIA.get(media.upper(), _MEDIA['NINGUNA'])}\n"
             f"Hashtags base del rubro (no los repitas): {' '.join(base) or '(ninguno)'}\n\n"
             f"Datos confirmados (lo único que puedes afirmar):\n{(c.get('datos') or '').strip() or '(ninguno)'}")
    propiedades = {
        "titulo": {"type": "string"}, "hashtags": {"type": "array", "items": {"type": "string"}},
        "flyer": {"type": "object", "required": list(_FLYER), "properties": {k: {"type": "string"} for k in _FLYER}},
    }
    propiedades |= {"texto": {"type": "string"}} if mismo else {r.lower(): {"type": "string"} for r in pedidas}
    esquema = {"type": "object", "required": list(propiedades), "properties": propiedades}
    datos, uso = gemini.generar(sistema, [{"text": texto}], esquema, modelo=modelo, temperatura=0.7)
    if mismo:
        comun = (datos.get("texto") or "").strip()
        salida = {r: comun[:LIMITES[r]] for r in pedidas}
    else:
        salida = {r: (datos.get(r.lower()) or "").strip()[:LIMITES[r]] for r in pedidas}
    vacias = [r for r, t in salida.items() if not t]
    if vacias:
        raise ErrorExterno(f"Gemini no escribió el texto de {', '.join(r.capitalize() for r in vacias)}. "
                           "Suele arreglarse volviendo a intentarlo.")
    f = datos.get("flyer") or {}
    return {
        "titulo": (datos.get("titulo") or idea).strip()[:60],
        "textos": salida,
        "hashtags": limpiar_hashtags(base + limpiar_hashtags(datos.get("hashtags"), 6), MAX_HASHTAGS),
        "flyer": {k: str(f.get(k) or "").strip()[:n] for k, n in _FLYER.items()},
        "uso": uso,
    }
