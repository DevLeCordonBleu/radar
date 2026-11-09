# -*- coding: utf-8 -*-
"""
Las consultas a Gemini del Plan SEO. El modelo clasifica e interpreta; no es
fuente de volumen, posiciones ni URLs. Lo que devuelve se comprueba contra la
entrada: URLs, keywords y citas que no estaban en ella se descartan.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from app.analisis.texto import normalizar
from app.compartido.errores import ErrorExterno
from app.ia import gemini

PROMPTS = Path(__file__).parent / "prompts"

TIPOS_PAGINA = ["ARTICULO", "PROGRAMA", "NOTICIA", "INSTITUCIONAL", "LISTADO", "OTRA", "DESCONOCIDA"]
CONFIANZAS = ["ALTA", "MEDIA", "BAJA"]
INTENCIONES = ["INFORMATIONAL", "COMMERCIAL", "TRANSACTIONAL", "NAVIGATIONAL", "NEEDS_REVIEW"]
COBERTURAS = ["YA_CUBIERTA", "PARCIAL", "SIN_COBERTURA", "INCIERTO"]

_CADENAS = {"type": "array", "items": {"type": "string"}}


# Lo que se usaba antes de que el rubro fuera un ajuste: si el backend no lo manda, se sigue igual.
NEGOCIO_POR_DEFECTO = "Instituto Le Cordon Bleu Perú"
RUBRO_POR_DEFECTO = "Escuela de cocina peruana e internacional, panadería, pastelería, bar y coctelería"


def _prompt(nombre: str, negocio: str = "", rubro: str = "") -> str:
    texto = (PROMPTS / nombre).read_text(encoding="utf-8")
    return (texto.replace("{{NEGOCIO}}", negocio.strip() or NEGOCIO_POR_DEFECTO)
            .replace("{{RUBRO}}", rubro.strip() or RUBRO_POR_DEFECTO))


def _rango(v, minimo=0, maximo=100) -> int:
    try:
        return max(minimo, min(maximo, int(v)))
    except (TypeError, ValueError):
        return minimo


# ── 1 · Temas de cada pagina ──────────────────────────────────────────────

def temas(paginas: list[dict], *, negocio: str = "", rubro: str = "", modelo: str | None = None) -> dict:
    """paginas: [{url, title, meta_description, h1, h2, extracto}] -> {temas: [...], uso}"""
    bloques = []
    for p in paginas:
        h2 = " | ".join(p.get("h2") or [])
        bloques.append(
            f"url: {p['url']}\ntitle: {p.get('title') or ''}\nmeta description: {p.get('meta_description') or ''}\n"
            f"H1: {p.get('h1') or ''}\nH2: {h2}\ntexto: {(p.get('extracto') or '')[:900]}"
        )
    esquema = {"type": "object", "required": ["paginas"], "properties": {"paginas": {"type": "array", "items": {
        "type": "object", "required": ["url", "tipo_pagina", "tema", "consultas", "relevancia", "confianza", "evidencia"],
        "properties": {
            "url": {"type": "string"}, "tipo_pagina": {"type": "string", "enum": TIPOS_PAGINA}, "tema": {"type": "string"},
            "consultas": _CADENAS, "relevancia": {"type": "integer"}, "confianza": {"type": "string", "enum": CONFIANZAS},
            "evidencia": _CADENAS}}}}}
    datos, uso = gemini.generar(_prompt("TEMAS.md", negocio, rubro), [{"text": "Páginas:\n\n" + "\n\n---\n\n".join(bloques)}], esquema, modelo=modelo)
    por_url = {p["url"]: p for p in paginas}
    salida = []
    for t in datos.get("paginas", []):
        p = por_url.get(t.get("url"))
        if not p:
            continue
        fuente = normalizar(" ".join([p.get("title") or "", p.get("meta_description") or "", p.get("h1") or "",
                                      " ".join(p.get("h2") or []), p.get("extracto") or ""]))
        consultas = list(dict.fromkeys(c.strip().lower() for c in t.get("consultas", []) if 3 <= len(c.strip()) <= 90))[:5]
        salida.append({
            "url": p["url"],
            "tipo_pagina": t.get("tipo_pagina", "DESCONOCIDA"),
            "tema": (t.get("tema") or "").strip()[:120],
            "consultas": consultas,
            "relevancia": _rango(t.get("relevancia")),
            "confianza": t.get("confianza", "BAJA"),
            # Solo citas que de verdad estan en la pagina.
            "evidencia": [e.strip() for e in t.get("evidencia", []) if e.strip() and normalizar(e) in fuente][:3],
        })
    return {"temas": salida, "uso": uso}


# ── 2 · Intencion y grupos de las keywords candidatas ─────────────────────

def agrupar(keywords: list[str], grupos_existentes: list[str] | None = None, *, negocio: str = "", rubro: str = "",
            modelo: str | None = None) -> dict:
    """keywords: textos ya sin duplicados -> {keywords: [{keyword, intencion, grupo, canonica, relevancia, motivo}], uso}"""
    texto = "Búsquedas:\n" + "\n".join(f"- {k}" for k in keywords)
    if grupos_existentes:
        texto += "\n\nGrupos ya creados (reutiliza el nombre exacto si corresponde):\n" + "\n".join(f"- {g}" for g in grupos_existentes)
    esquema = {"type": "object", "required": ["keywords"], "properties": {"keywords": {"type": "array", "items": {
        "type": "object", "required": ["keyword", "intencion", "grupo", "canonica", "relevancia", "motivo"],
        "properties": {
            "keyword": {"type": "string"}, "intencion": {"type": "string", "enum": INTENCIONES}, "grupo": {"type": "string"},
            "canonica": {"type": "string"}, "relevancia": {"type": "integer"}, "motivo": {"type": "string"}}}}}}
    datos, uso = gemini.generar(_prompt("KEYWORDS.md", negocio, rubro), [{"text": texto}], esquema, modelo=modelo)
    recibidas = {normalizar(k): k for k in keywords}
    salida, vistas = [], set()
    for k in datos.get("keywords", []):
        n = normalizar(k.get("keyword", ""))
        if n not in recibidas or n in vistas:
            continue  # el modelo no puede añadir keywords
        vistas.add(n)
        salida.append({
            "keyword": recibidas[n],
            "intencion": k.get("intencion", "NEEDS_REVIEW"),
            "grupo": (k.get("grupo") or recibidas[n]).strip().lower()[:100],
            "canonica": (k.get("canonica") or recibidas[n]).strip().lower()[:100],
            "relevancia": _rango(k.get("relevancia")),
            "motivo": (k.get("motivo") or "").strip()[:300],
        })
    return {"keywords": salida, "uso": uso}


# ── 3 · Cobertura en el sitio propio ──────────────────────────────────────

def cobertura(grupos: list[dict], propias: list[dict], *, modelo: str | None = None) -> dict:
    """
    grupos: [{grupo, canonica, keywords}]; propias: [{url, title, h1, tema, h2}]
    -> {cobertura: [{grupo, estado, url, motivo}], uso}
    """
    inventario = "\n".join(
        f"- {p['url']} | {p.get('title') or ''} | H1: {p.get('h1') or ''}"
        + (f" | tema: {p['tema']}" if p.get("tema") else "")
        + (f" | H2: {' / '.join((p.get('h2') or [])[:6])}" if p.get("h2") else "")
        for p in propias
    )
    lista = "\n".join(f"- grupo: {g['grupo']} | principal: {g['canonica']} | variantes: {', '.join(g.get('keywords', [])[:8])}" for g in grupos)
    esquema = {"type": "object", "required": ["cobertura"], "properties": {"cobertura": {"type": "array", "items": {
        "type": "object", "required": ["grupo", "estado", "url", "motivo"],
        "properties": {"grupo": {"type": "string"}, "estado": {"type": "string", "enum": COBERTURAS},
                       "url": {"type": "string"}, "motivo": {"type": "string"}}}}}}
    datos, uso = gemini.generar(
        _prompt("COBERTURA.md"),
        [{"text": f"Grupos de búsquedas:\n{lista}\n\nInventario del sitio propio ({len(propias)} páginas):\n{inventario}"}],
        esquema, modelo=modelo,
    )
    nombres = {g["grupo"] for g in grupos}
    urls = {p["url"] for p in propias}
    salida, vistos = [], set()
    for c in datos.get("cobertura", []):
        g = c.get("grupo")
        if g not in nombres or g in vistos:
            continue
        vistos.add(g)
        url = (c.get("url") or "").strip()
        estado = c.get("estado", "INCIERTO")
        if url not in urls:
            url = None  # el modelo no puede citar una pagina que no existe
            if estado in ("YA_CUBIERTA", "PARCIAL"):
                estado = "INCIERTO"
        salida.append({"grupo": g, "estado": estado, "url": url, "motivo": (c.get("motivo") or "").strip()[:300]})
    return {"cobertura": salida, "uso": uso}


# ── 4 · Articulo para el sitio propio ─────────────────────────────────────

def articulo(keyword: str, variantes: list[str], competidores: list[dict], propias: list[dict], *, negocio: str = "",
             rubro: str = "", indicaciones: str = "", modelo: str | None = None) -> dict:
    """
    competidores: [{url, title, h2, extracto}]; propias: [{url, title}] (las unicas a las que puede enlazar)
    -> {titulo, slug, meta_description, contenido (Markdown), pendientes, enlaces_quitados, uso}
    """
    from . import markdown

    ajenas = "\n\n".join(
        f"url: {p['url']}\ntitle: {p.get('title') or ''}\nH2: {' | '.join((p.get('h2') or [])[:12])}\n"
        f"texto: {(p.get('extracto') or '')[:1500]}"
        for p in competidores
    ) or "(ninguna)"
    enlazables = "\n".join(f"- {p['url']} | {p.get('title') or ''}" for p in propias) or "(ninguna)"
    texto = (f"Búsqueda principal: {keyword}\nVariantes: {', '.join(variantes) or '(ninguna)'}\n\n"
             f"Páginas de competidores:\n{ajenas}\n\n"
             f"Páginas del sitio de {negocio or NEGOCIO_POR_DEFECTO} para enlazar:\n{enlazables}")
    if indicaciones.strip():
        texto += f"\n\nIndicaciones de la persona:\n{indicaciones.strip()[:1500]}"
    esquema = {"type": "object", "required": ["titulo", "slug", "meta_description", "contenido", "pendientes"], "properties": {
        "titulo": {"type": "string"}, "slug": {"type": "string"}, "meta_description": {"type": "string"},
        "contenido": {"type": "string"}, "pendientes": _CADENAS}}
    datos, uso = gemini.generar(_prompt("ARTICULO.md", negocio, rubro), [{"text": texto}], esquema, modelo=modelo, temperatura=0.6)
    contenido, quitados = markdown.solo_enlaces_permitidos((datos.get("contenido") or "").strip(), {p["url"] for p in propias})
    if not contenido:
        raise ErrorExterno("Gemini devolvió el artículo vacío. Suele arreglarse volviendo a intentarlo.")
    titulo = (datos.get("titulo") or keyword).strip()[:200]
    pendientes = [p.strip()[:200] for p in datos.get("pendientes") or [] if p and p.strip()][:20]
    # Lo que quedo marcado en el texto tambien es un pendiente, aunque el modelo no lo listara.
    for marca in markdown.pendientes(contenido):
        if marca not in pendientes:
            pendientes.append(marca)
    return {"titulo": titulo, "slug": slug(datos.get("slug") or titulo), "meta_description": (datos.get("meta_description") or "").strip()[:300],
            "contenido": contenido, "pendientes": pendientes, "enlaces_quitados": quitados, "uso": uso}


# ── 4b · Mejorar una pagina que ya aparece en Google (Search Console) ─────

MAX_TITULO = 70
MAX_META = 200
MAX_IDEA = 600
TIPOS_TERMINO = {"CARRERA": "carrera o programa", "SISTEMA": "sistema", "OTRO": "término"}
# Lo que puede seguir a un término protegido sin cambiarlo («Gastronomía Le Cordon Bleu», «Cocina en Lima»).
_TRAS_NOMBRE = {"le", "lcb", "ilcb", "instituto", "lima", "peru", "en", "de", "del", "con", "para"}
_PEGADO = re.compile(r"(\s+(?:y|e|&)\s+|[ \t]+)([A-ZÁÉÍÓÚÑ][\wáéíóúñü]*)")


def _plegar(t: str) -> str:
    """Minúsculas y sin tildes, letra por letra: cada posición coincide con la del original."""
    return "".join(unicodedata.normalize("NFD", c.lower()[:1] or c)[0] for c in t)


def nombres_oficiales(texto: str, nombres: list[str]) -> tuple[str, list[str]]:
    """
    Escribe cada término protegido tal como está definido (tildes y mayúsculas) y devuelve
    los que la IA alargó: «Gastronomía y Arte Culinario» o «Cocina Profesional». Lo que
    sigue a un término con mayúscula solo vale si empieza otro término o es de la
    institución o el lugar («Cocina en Lima», «Gastronomía Le Cordon Bleu»).
    """
    plegado = _plegar(texto)
    primeras = {_plegar(n).split()[0] for n in nombres if n.split()}
    ocupado: list[tuple[int, int]] = []
    cambiados: list[str] = []
    # Los largos primero: «Cocina Peruana», si está en la lista, gana a «Cocina».
    for n in sorted({n.strip() for n in nombres if n.strip()}, key=len, reverse=True):
        for m in re.finditer(rf"(?<!\w){re.escape(_plegar(n))}(?!\w)", plegado):
            a, b = m.span()
            if any(a < y and x < b for x, y in ocupado):
                continue
            ocupado.append((a, b))
            texto = texto[:a] + n + texto[b:]
            sigue = _PEGADO.match(texto, b)
            if sigue and _plegar(sigue.group(2)) not in primeras | _TRAS_NOMBRE:
                cambiados.append(texto[a:sigue.end()])
    return texto, cambiados


def _lista_terminos(terminos: list[dict]) -> str:
    lineas = []
    for t in terminos:
        linea = f"- {t['nombre']} ({TIPOS_TERMINO.get(t.get('tipo') or 'OTRO', 'término')})"
        if (t.get("descripcion") or "").strip():
            linea += f": {t['descripcion'].strip()}"
        lineas.append(linea)
    return "\n".join(lineas) or "(ninguno)"


def mejora(url: str, actual: dict, consultas: list[dict], *, negocio: str = "", rubro: str = "", terminos: list[dict] | None = None,
           modelo: str | None = None) -> dict:
    """
    actual: {title, meta_description, h1, h2[], extracto}; consultas: [{consulta, impresiones, clics, posicion}];
    terminos: [{nombre, tipo, descripcion}] que no cambian de nombre ni de significado (carreras, sistemas...).
    -> {titulo, meta_description, ideas: [{donde, dice_ahora, debe_decir}], motivo, uso}
    """
    terminos = [t for t in terminos or [] if (t.get("nombre") or "").strip()]
    nombres = [t["nombre"].strip() for t in terminos]
    busquedas = "\n".join(
        f"- {c['consulta']}: {c.get('impresiones', 0)} impresiones, {c.get('clics', 0)} clics, posición {c.get('posicion', 0)}"
        for c in consultas
    ) or "(ninguna)"
    texto = (f"Página: {url}\nTítulo actual: {actual.get('title') or '(sin título)'}\n"
             f"Meta descripción actual: {actual.get('meta_description') or '(sin descripción)'}\n"
             f"H1: {actual.get('h1') or ''}\nH2: {' | '.join((actual.get('h2') or [])[:12])}\n"
             f"Texto: {(actual.get('extracto') or '')[:2500]}\n\n"
             f"Búsquedas de los últimos 90 días (Search Console):\n{busquedas}\n\n"
             f"Términos protegidos:\n{_lista_terminos(terminos)}")
    esquema = {"type": "object", "required": ["titulo", "meta_description", "ideas", "motivo"], "properties": {
        "titulo": {"type": "string"}, "meta_description": {"type": "string"}, "motivo": {"type": "string"},
        "ideas": {"type": "array", "items": {"type": "object", "required": ["donde", "dice_ahora", "debe_decir"], "properties": {
            "donde": {"type": "string"}, "dice_ahora": {"type": "string"}, "debe_decir": {"type": "string"}}}}}}
    uso_total: dict = {}
    for intento in range(2):
        datos, uso = gemini.generar(_prompt("MEJORA.md", negocio, rubro), [{"text": texto}], esquema, modelo=modelo, temperatura=0.4)
        uso_total = _sumar_uso(uso_total, uso)
        r = _propuesta(datos, nombres)
        cambiados = list(dict.fromkeys(r.pop("cambiados")))
        if not cambiados:
            return {**r, "uso": uso_total}
        if intento == 0:
            # Un segundo intento con el error a la vista suele bastar.
            texto += ("\n\nCorrección: tu propuesta anterior cambió un término protegido ("
                      + ", ".join(f"«{c}»" for c in cambiados) + "). Escríbelos exactamente como en la lista.")
    raise ErrorExterno("La IA cambió un término protegido (" + ", ".join(f"«{c}»" for c in cambiados)
                       + "). Vuelve a pedir la propuesta; si ese nombre también es oficial, agrégalo a «Términos protegidos».")


def _propuesta(datos: dict, nombres: list[str]) -> dict:
    """Limpia la respuesta y pone los nombres oficiales como están definidos. «cambiados»: los que la IA alargó."""
    cambiados: list[str] = []

    def fijar(t: str) -> str:
        t, c = nombres_oficiales(t, nombres)
        cambiados.extend(c)
        return t

    titulo = fijar((datos.get("titulo") or "").strip())
    if not titulo:
        raise ErrorExterno("Gemini no propuso un título. Suele arreglarse volviendo a intentarlo.")
    ideas = []
    for i in datos.get("ideas") or []:
        if not isinstance(i, dict) or not (i.get("debe_decir") or "").strip():
            continue
        ahora = (i.get("dice_ahora") or "").strip()
        # «dice_ahora» es el texto de la página tal cual: no se toca.
        ideas.append({"donde": (i.get("donde") or "").strip()[:120],
                      "dice_ahora": None if _plegar(ahora).strip("() .") in ("", "no existe") else ahora[:MAX_IDEA],
                      "debe_decir": fijar(i["debe_decir"].strip())[:MAX_IDEA]})
    return {"titulo": titulo[:MAX_TITULO], "meta_description": fijar((datos.get("meta_description") or "").strip())[:MAX_META],
            "ideas": ideas[:4], "motivo": fijar((datos.get("motivo") or "").strip())[:300], "cambiados": cambiados}


def _sumar_uso(a: dict, b: dict) -> dict:
    if not a:
        return dict(b or {})
    r = dict(a)
    for k, v in (b or {}).items():
        r[k] = r.get(k, 0) + v if isinstance(v, (int, float)) and not isinstance(v, bool) else v
    return r


def slug(texto: str) -> str:
    t = normalizar(texto)
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:90].strip("-") or "articulo"


# ── 5 · Rubro del sitio propio (para sugerir el ajuste) ───────────────────

def rubro(negocio: str, paginas: list[dict], *, modelo: str | None = None) -> dict:
    """paginas: [{title, h1, h2}] del sitio propio -> {descripcion, palabras, uso}"""
    lineas = "\n".join(
        f"- {p.get('title') or ''} | H1: {p.get('h1') or ''} | H2: {' / '.join((p.get('h2') or [])[:5])}" for p in paginas
    )
    esquema = {"type": "object", "required": ["descripcion", "palabras"],
               "properties": {"descripcion": {"type": "string"}, "palabras": _CADENAS}}
    datos, uso = gemini.generar(_prompt("RUBRO.md"), [{"text": f"Negocio: {negocio}\n\nPáginas:\n{lineas}"}], esquema, modelo=modelo)
    palabras = []
    for p in datos.get("palabras") or []:
        n = normalizar(p).strip()
        if re.fullmatch(r"[a-zñ0-9]{2,30}", n) and n not in palabras:
            palabras.append(n)
    return {"descripcion": (datos.get("descripcion") or "").strip()[:300], "palabras": palabras[:60], "uso": uso}
