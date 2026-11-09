# -*- coding: utf-8 -*-
"""
Clasificacion de anuncios con Gemini (multimodal) y agrupacion de etiquetas en
territorios. Es la unica parte del analisis que gasta IA.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from app.analisis import taxonomia as tx
from app.analisis.texto import limpiar, normalizar
from . import gemini, medios

PROMPTS = Path(__file__).parent / "prompts"
DESCARGAS_PARALELAS = 4


def _lista(d: dict[str, str]) -> str:
    return "\n".join(f"  {k}: {v}" for k, v in d.items())


def prompt_clasificar() -> str:
    t = (PROMPTS / "CLASIFICAR.md").read_text(encoding="utf-8")
    return (t.replace("{HOOKS}", _lista(tx.HOOKS)).replace("{OFERTAS}", _lista(tx.OFERTAS))
             .replace("{CTAS}", _lista(tx.CTAS)).replace("{FORMATOS}", _lista(tx.FORMATOS))
             .replace("{PATRONES}", _lista(tx.PATRONES_VISUALES)))


def esquema_clasificar() -> dict:
    cadenas = {"type": "array", "items": {"type": "string"}}
    props = {
        "ad_id": {"type": "string"},
        "hook_estructura": {"type": "string", "enum": list(tx.HOOKS)},
        "hook_literal": {"type": "string"},
        "oferta_tipo": {"type": "string", "enum": list(tx.OFERTAS)},
        "cta_tipo": {"type": "string", "enum": list(tx.CTAS)},
        "formato": {"type": "string", "enum": list(tx.FORMATOS)},
        "patron_visual": {"type": "array", "items": {"type": "string", "enum": list(tx.PATRONES_VISUALES)}},
        "angulos_libres": cadenas,
        "beneficios_libres": cadenas,
        "precio_visible": {"type": "boolean"},
        "marca_en_3s": {"type": "boolean"},
        "subtitulos": {"type": "boolean"},
        "duracion_seg": {"type": "number", "nullable": True},
        "relevante": {"type": "boolean"},
    }
    obligatorios = [k for k in props if k != "duracion_seg"]
    return {"type": "object", "required": ["clasificaciones"], "properties": {
        "clasificaciones": {"type": "array", "items": {"type": "object", "properties": props, "required": obligatorios}}}}


def contexto_sector(referencia: list[str], terminos: list[str]) -> str:
    """
    El sector lo definen los negocios de referencia (los indicados y los competidores).
    Las palabras clave solo sirvieron para buscar: con «gastronomia, cocina» la
    busqueda trae tiendas de menaje y restaurantes, y no por eso son del sector.
    """
    if not referencia and not terminos:
        return "No se ha indicado sector: marca todos los anuncios como relevantes."
    if not referencia:
        # Solo palabras clave: son lo unico que dice de que va el mercado.
        return "\n".join(["SECTOR ANALIZADO", f"Términos del sector: {', '.join(terminos[:8])}.",
                          "Un anuncio es relevante si lo publica un negocio de este tipo."])
    partes = ["SECTOR ANALIZADO", f"Negocios de referencia (definen el tipo de negocio que se compara): {', '.join(referencia[:12])}."]
    if terminos:
        partes.append(f"Palabras con las que además se buscó: {', '.join(terminos[:8])}. Solo sirvieron para buscar: NO definen el sector.")
    partes.append(
        "Un anuncio es relevante solo si lo publica un negocio del MISMO TIPO que los de referencia (si son escuelas o "
        "institutos, otra escuela, instituto o quien venda cursos o formación de ese tema). No lo es una tienda, un "
        "fabricante, una marca de productos ni un restaurante u otro servicio, aunque use las mismas palabras."
    )
    return "\n".join(partes)


# ── Reglas deterministas que corrigen al modelo ───────────────────────────

_CTA = [
    ("reservar", r"reserv|book|cita|appointment"),
    ("inscribirse", r"inscr|registr|sign ?up|apply|ap[uú]ntate|suscr|subscribe|join|solicit|matric"),
    ("comprar", r"compr|shop|buy|order|pedido"),
    ("descargar", r"descarg|download|instal"),
    ("contactar", r"contact|mensaje|message|whatsapp|llam|call|escr[ií]b"),
    ("probar", r"pru[eé]ba|try|probar"),
    ("mas_info", r"m[aá]s inform|learn more|saber m[aá]s|ver m[aá]s|see more|watch more|m[aá]s detalles"),
]


def cta_por_boton(texto: str | None) -> str | None:
    if texto and texto.strip():
        return next((k for k, rx in _CTA if re.search(rx, texto, re.I)), None)
    return None


def formato_por_origen(a: dict) -> str | None:
    """El formato que declara Meta manda sobre lo que crea ver el modelo."""
    if a.get("video_url"):
        return "video"
    origen = a.get("formato_origen") or ""
    if re.search(r"CAROUSEL", origen, re.I):
        return "carrusel"
    if re.match(r"^(IMAGE|DCO|DPA|MULTI_IMAGES)", origen, re.I):
        return "estatica"
    return None


def hook_corregido(literal: str, estructura: str) -> str:
    """Una primera frase con signos de pregunta es pregunta_directa, diga lo que diga el modelo."""
    limpio = re.sub(r"[^\w¿?¡!.,:;'\"%€$ -]", " ", literal or "").strip()
    primera = re.match(r"^[^.!?]*[.!?]?", limpio)
    p = (primera.group(0) if primera else "").strip()
    return "pregunta_directa" if p.startswith("¿") or p.endswith("?") else estructura


def _corregir(c: dict, a: dict) -> dict:
    cta = cta_por_boton(a.get("cta_texto")) or c.get("cta_tipo", "otro")
    return {
        **c,
        "hook_estructura": hook_corregido(c.get("hook_literal", ""), c.get("hook_estructura", "otro")),
        "cta_tipo": cta if cta in tx.CTAS else "otro",
        "formato": formato_por_origen(a) or c.get("formato", "estatica"),
        "hook_literal": limpiar(c.get("hook_literal", "")),
    }


# ── Llamadas ──────────────────────────────────────────────────────────────

def clasificar(anuncios: list[dict], *, referencia: list[str], terminos: list[str], con_medios: bool = True,
               modelo: str | None = None, parar=None) -> dict:
    """
    Clasifica un lote (el backend lo trocea). Devuelve
    {clasificaciones: [..por ad_id..], uso, medios_fallidos, sin_medio: [ad_id]}.
    """
    partes: list[dict] = [{"text": contexto_sector(referencia, terminos)}]
    medios_ok: list[dict | None] = [None] * len(anuncios)

    if con_medios:
        def medio(a: dict) -> dict | None:
            urls = list(dict.fromkeys(u for u in (a.get("video_url"), a.get("imagen_url"), a.get("video_portada_url")) if u))
            for u in urls:
                m = medios.descargar(u, cliente)
                if m:
                    return m
            return None if urls else False  # type: ignore[return-value]

        with httpx.Client(follow_redirects=True, timeout=25) as cliente, \
                ThreadPoolExecutor(DESCARGAS_PARALELAS) as pool:
            medios_ok = list(pool.map(medio, anuncios))

    sin_medio = []
    for a, m in zip(anuncios, medios_ok):
        partes.append({"text": "\n".join(filter(None, [
            f"--- ANUNCIO {a['ad_id']} ---",
            f"Anunciante: {a['anunciante']}",
            f"Texto del anuncio: {a.get('copy') or '(sin texto)'}",
            f"Botón: {a['cta_texto']}" if a.get("cta_texto") else "",
            f"Formato declarado: {a.get('formato_origen') or 'desconocido'}",
        ]))})
        if m:
            partes.append(m)
        elif m is None:
            sin_medio.append(a["ad_id"])
            partes.append({"text": "(el medio de este anuncio no se pudo descargar)"})
    partes.append({"text": f"Clasifica los {len(anuncios)} anuncios anteriores. Devuelve una entrada por cada ad_id."})

    peso = sum(len(p.get("inline_data", {}).get("data", "")) for p in partes)
    if peso > 45 * 1024 * 1024 and len(anuncios) > 1:
        raise LoteDemasiadoGrande(f"El bloque pesa {peso // 1_000_000} MB: se parte en dos.")

    datos, uso = gemini.generar(prompt_clasificar(), partes, esquema_clasificar(), modelo=modelo, parar=parar)
    por_id = {a["ad_id"]: a for a in anuncios}
    salida = [_corregir(c, por_id[c["ad_id"]]) for c in datos.get("clasificaciones", []) if c.get("ad_id") in por_id]
    return {"clasificaciones": salida, "uso": uso, "medios_fallidos": len(sin_medio), "sin_medio": sin_medio}


class LoteDemasiadoGrande(Exception):
    """El lote supera el limite de Gemini: quien llama debe partirlo."""


def territorios(etiquetas: list[str], *, modelo: str | None = None) -> dict:
    """Agrupa etiquetas libres en 8-15 territorios. {territorios: [{nombre, tipo, etiquetas}], uso}."""
    cuenta: dict[str, int] = {}
    for e in etiquetas:
        k = re.sub(r"\s+", " ", e.strip().lower())
        if k:
            cuenta[k] = cuenta.get(k, 0) + 1
    lista = "\n".join(f"{k} ({n})" for k, n in sorted(cuenta.items(), key=lambda kv: -kv[1])[:200])
    esquema = {"type": "object", "required": ["territorios"], "properties": {"territorios": {
        "type": "array", "items": {"type": "object", "required": ["nombre", "tipo", "etiquetas"], "properties": {
            "nombre": {"type": "string"}, "tipo": {"type": "string", "enum": list(tx.TIPOS_TERRITORIO)},
            "etiquetas": {"type": "array", "items": {"type": "string"}}}}}}}
    datos, uso = gemini.generar((PROMPTS / "TERRITORIOS.md").read_text(encoding="utf-8"),
                                [{"text": f"Etiquetas extraídas de los anuncios, con su frecuencia:\n\n{lista}"}],
                                esquema, modelo=modelo)
    return {"territorios": _sin_colisiones(datos.get("territorios", [])), "uso": uso}


def _sin_colisiones(territorios: list[dict]) -> list[dict]:
    """Si una etiqueta aparece en dos territorios, se queda en el primero."""
    vistas: set[str] = set()
    for t in territorios:
        t["etiquetas"] = [e for e in t.get("etiquetas", []) if (k := normalizar(e)) and not (k in vistas or vistas.add(k))]
    return territorios
