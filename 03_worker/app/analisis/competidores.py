# -*- coding: utf-8 -*-
"""
Identifica a que pagina de Meta se refiere el nombre de un competidor.

Buscar "Sabor Andino" en la Biblioteca devuelve anuncios de todo lo que lo
menciona. Antes de analizar nada hay que saber cual es SU pagina; si hay mas de
una candidata razonable se le pregunta a la persona (y se guarda su eleccion).
"""
from __future__ import annotations

from .texto import normalizar

# Palabras que no distinguen a un negocio de otro del mismo rubro. Las ciudades
# NO estan: "Mesa Abierta Lima" y "Mesa Abierta Cusco" son negocios distintos.
GENERICAS = frozenset(
    "de del la el los las y e en con para por the and of a al sl sa ltd llc inc srl sac eirl "
    "escuela academia studio estudio centro instituto colegio school institute universidad "
    "cocina gastronomia gastronomica pasteleria reposteria panaderia restaurante cafe bar hotel "
    "cursos curso formacion online oficial official web grupo group servicios".split()
)


def distintivas(nombre: str) -> list[str]:
    return [p for p in normalizar(nombre).split() if p not in GENERICAS]


def encaje(buscado: str, anunciante: str) -> int:
    """3 = nombre identico, 2 = identico sin palabras genericas, 1 = comparten lo distintivo, 0 = no."""
    if normalizar(buscado) == normalizar(anunciante):
        return 3
    a, b = distintivas(buscado), distintivas(anunciante)
    if not a or not b:
        return 0
    if a == b:
        return 2
    if set(a) <= set(b) or set(b) <= set(a):
        return 1
    if len({p for p in a if len(p) > 2} & {p for p in b if len(p) > 2}) >= 2:
        return 1
    # Marcas escritas pegadas o con apostrofe: «D'Gallia» = «DGallia» = «D’Gallia».
    junto = "".join(a)
    if len(junto) >= 5 and (junto in "".join(b) or "".join(b) in junto):
        return 1
    return 0


def resolver(buscado: str, anuncios: list[dict]) -> dict:
    """
    {estado: "unica", page_id, anunciante}
    {estado: "ambigua", candidatos: [{page_id, nombre, anuncios, muestra, avatar, ejemplos, texto}]}
    {estado: "ninguna"}

    De cada candidata se dan la foto de perfil (`avatar`), hasta 3 imagenes de sus
    anuncios (`ejemplos`) y el inicio de un texto: con eso la persona reconoce la pagina.
    """
    paginas: dict[str, dict] = {}
    for a in anuncios:
        pid = a.get("page_id")
        if not pid:
            continue
        e = encaje(buscado, a["anunciante"])
        if not e:
            continue
        p = paginas.setdefault(pid, {"page_id": pid, "nombre": a["anunciante"], "anuncios": 0, "encaje": e,
                                     "avatar": None, "ejemplos": [], "texto": None})
        p["anuncios"] += 1
        p["avatar"] = p["avatar"] or a.get("avatar_url")
        img = a.get("imagen_url") or a.get("video_portada_url")
        if img and img not in p["ejemplos"] and len(p["ejemplos"]) < 3:
            p["ejemplos"].append(img)
        if not p["texto"] and (a.get("copy") or "").strip():
            t = " ".join(a["copy"].split())
            p["texto"] = t[:140] + ("…" if len(t) > 140 else "")
    if not paginas:
        return {"estado": "ninguna"}
    orden = sorted(paginas.values(), key=lambda p: (-p["encaje"], -p["anuncios"]))
    mejores = [p for p in orden if p["encaje"] == orden[0]["encaje"]]
    if len(mejores) == 1 and orden[0]["encaje"] >= 2:
        return {"estado": "unica", "page_id": orden[0]["page_id"], "anunciante": orden[0]["nombre"]}
    return {"estado": "ambigua", "candidatos": [
        {"page_id": p["page_id"], "nombre": p["nombre"], "anuncios": p["anuncios"], "avatar": p["avatar"], "ejemplos": p["ejemplos"],
         "texto": p["texto"], "muestra": p["avatar"] or (p["ejemplos"][0] if p["ejemplos"] else None)} for p in orden[:8]]}
