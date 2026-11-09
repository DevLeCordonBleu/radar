# -*- coding: utf-8 -*-
"""
De lo que devuelve Google Ads a las filas y vistas del explorador.

Todo es puro y determinista (se prueba sin red): normalizar metricas, estimar la
intencion de busqueda, separar «terminos coincidentes» de «relacionados»,
detectar preguntas y agrupar por termino.

La intencion se ESTIMA con reglas sobre el texto de la keyword: Ahrefs usa
aprendizaje automatico, aqui son reglas en espanol (y algo de ingles). Sirve
para filtrar, no es una verdad.
"""
from __future__ import annotations

import re
from collections import defaultdict

from app.analisis.texto import normalizar

MESES = {m: i for i, m in enumerate(
    ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"], 1)}
NOMBRE_MES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
COMPETENCIA = {"LOW": "baja", "MEDIUM": "media", "HIGH": "alta"}

STOP = frozenset(
    "de del la el los las y e o u en para con por al a un una unos unas que se su sus mi tu lo le les es son the and of for to in on".split())

PREGUNTA_INICIO = frozenset("que como cual cuales cuando donde quien quienes cuanto cuanta cuantos cuantas porque".split())
PREGUNTA_DOS = {("por", "que"), ("para", "que"), ("a", "que"), ("de", "que"), ("en", "que"), ("hasta", "cuando"), ("desde", "cuando")}

# Intencion: cada lista son palabras o frases que la delatan (sobre texto sin acentos).
INTENCIONES: dict[str, list[str]] = {
    "transaccional": ["comprar", "compra", "precio", "precios", "barato", "baratos", "oferta", "ofertas", "descuento", "cotizar",
                      "cotizacion", "contratar", "alquiler", "alquilar", "delivery", "pedir", "tienda", "inscripcion", "matricula",
                      "reservar", "reserva", "cerca de mi", "costo", "costos", "cuanto cuesta", "buy", "price", "cheap", "order", "pagar"],
    "comercial": ["mejor", "mejores", "top", "vs", "comparar", "comparativa", "opiniones", "resenas", "review", "reviews", "alternativa",
                  "alternativas", "ranking", "recomendado", "recomendados", "conviene", "vale la pena", "best", "versus"],
    "navegacional": ["login", "iniciar sesion", "ingresar", "campus virtual", "intranet", "web oficial", "sitio oficial", "portal", "acceso",
                     "www", ".com", ".pe", ".mx", ".es", "app", "descargar app"],
    "informacional": ["como", "que es", "que son", "cual", "cuales", "por que", "porque", "cuando", "donde", "para que", "quien", "tutorial",
                      "guia", "ejemplos", "ejemplo", "significado", "definicion", "receta", "recetas", "ideas", "tipos", "diferencia",
                      "pdf", "curso gratis", "aprender", "how", "what", "why", "paso a paso", "consejos", "trucos"],
}


def tokens(texto: str) -> list[str]:
    return normalizar(texto).split()


def _raiz(p: str) -> str:
    """Plural simple: «cursos» y «curso» cuentan como la misma palabra."""
    return p[:-1] if len(p) > 3 and p.endswith("s") else p


def intencion(keyword: str) -> list[str]:
    """Una o varias de: informacional, comercial, transaccional, navegacional. Puede quedar vacia."""
    n = f" {normalizar(keyword)} "
    salida = []
    for nombre, claves in INTENCIONES.items():
        for c in claves:
            if (f" {c} " in n) if " " in c or c.isalnum() else (c in n):
                salida.append(nombre)
                break
    return salida


def es_pregunta(keyword: str) -> bool:
    t = tokens(keyword)
    if "?" in keyword or "¿" in keyword:
        return True
    if not t:
        return False
    if t[0] in PREGUNTA_INICIO:
        return True
    return len(t) > 1 and (t[0], t[1]) in PREGUNTA_DOS


# ── Metricas ──────────────────────────────────────────────────────────────

def _entero(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _micros(v) -> float | None:
    n = _entero(v)
    return None if n is None else round(n / 1_000_000, 2)


def serie(volumenes: list[dict] | None) -> list[int]:
    """Los ultimos 12 meses en orden cronologico: [mes mas antiguo ... mes mas reciente]."""
    if not volumenes:
        return []
    puntos = sorted(((_entero(v.get("year")) or 0, MESES.get(str(v.get("month")).upper(), 0), _entero(v.get("monthlySearches")) or 0)
                     for v in volumenes))
    return [p[2] for p in puntos][-12:]


def meses_de(volumenes: list[dict] | None) -> list[tuple[int, int]]:
    """(año, mes) de cada punto de la serie, en el mismo orden que `serie`."""
    if not volumenes:
        return []
    return sorted(((_entero(v.get("year")) or 0, MESES.get(str(v.get("month")).upper(), 0)) for v in volumenes))[-12:]


def fila(texto: str, m: dict | None, *, sugerencia: bool = False, concepto: str | None = None) -> dict:
    """Una keyword con sus metricas ya normalizadas. `m` = keywordIdeaMetrics o keywordMetrics de Google."""
    m = m or {}
    bajo, alto = _micros(m.get("lowTopOfPageBidMicros")), _micros(m.get("highTopOfPageBidMicros"))
    medios = [x for x in (bajo, alto) if x is not None]
    cpc = round(sum(medios) / len(medios), 2) if medios else _micros(m.get("averageCpcMicros"))
    vols = m.get("monthlySearchVolumes")
    return {
        "keyword": texto.strip(),
        "volumen": _entero(m.get("avgMonthlySearches")),
        "tendencia": serie(vols),
        "competencia": COMPETENCIA.get(str(m.get("competition") or "")),
        "competencia_idx": _entero(m.get("competitionIndex")),
        "cpc": cpc, "cpc_bajo": bajo, "cpc_alto": alto,
        "palabras": len(texto.split()),
        "intencion": intencion(texto),
        "pregunta": es_pregunta(texto),
        "tipo": "relacionado",
        "sugerencia": sugerencia,
        "concepto": concepto,
    }


def _concepto(raw: dict) -> str | None:
    cs = (raw.get("keywordAnnotations") or {}).get("concepts") or []
    return (cs[0].get("name") or None) if cs else None


def marcar_tipos(filas: list[dict], semillas: list[str]) -> None:
    """«Coincidente» = contiene todas las palabras de alguna semilla (en cualquier orden y en plural o singular)."""
    objetivos = [{_raiz(t) for t in tokens(s) if t not in STOP} for s in semillas if s.strip()]
    objetivos = [o for o in objetivos if o]
    for f in filas:
        palabras = {_raiz(t) for t in tokens(f["keyword"])}
        f["tipo"] = "coincidente" if any(o <= palabras for o in objetivos) else "relacionado"


def por_terminos(filas: list[dict], maximo: int = 80) -> list[dict]:
    """Agrupa por cada palabra que aparece: cuantas keywords la usan y cuanto volumen suman."""
    cuenta: dict[str, dict] = defaultdict(lambda: {"keywords": 0, "volumen": 0, "formas": defaultdict(int)})
    for f in filas:
        vistas = set()
        for t in tokens(f["keyword"]):
            if t in STOP or len(t) < 2:
                continue
            r = _raiz(t)
            if r in vistas:
                continue
            vistas.add(r)
            c = cuenta[r]
            c["keywords"] += 1
            c["volumen"] += f["volumen"] or 0
            c["formas"][t] += 1
    salida = [{"termino": max(c["formas"].items(), key=lambda kv: kv[1])[0], "keywords": c["keywords"], "volumen": c["volumen"]}
              for c in cuenta.values()]
    return sorted(salida, key=lambda x: (-x["keywords"], -x["volumen"]))[:maximo]


def volumen_agrupado(filas: list[dict]) -> bool:
    """
    Google devuelve volumenes agrupados (10, 100, 1 000, 10 000…) a las cuentas que no
    invierten en anuncios. Si casi todos son potencias de diez, el panel avisa.
    """
    vols = [f["volumen"] for f in filas if f["volumen"]]
    if len(vols) < 5:
        return False
    potencias = sum(1 for v in vols if re.fullmatch(r"10+", str(v)))
    return potencias / len(vols) >= 0.8


def totales(filas: list[dict]) -> dict:
    con_vol = [f for f in filas if f["volumen"] is not None]
    return {
        "keywords": len(filas), "volumen": sum(f["volumen"] for f in con_vol),
        "coincidentes": sum(1 for f in filas if f["tipo"] == "coincidente"),
        "relacionadas": sum(1 for f in filas if f["tipo"] == "relacionado"),
        "preguntas": sum(1 for f in filas if f["pregunta"]),
        "sugerencias": sum(1 for f in filas if f["sugerencia"]),
        "sin_volumen": len(filas) - len(con_vol),
    }


def construir(semillas: list[str], ideas: list[dict], sugerencias: list[str] | None = None,
              metricas_sugerencias: dict[str, dict] | None = None) -> dict:
    """
    Resultado del explorador: filas + clusters por termino + totales.
    `ideas` = results[] de generateKeywordIdeas; `sugerencias` = textos del autocompletado de Google;
    `metricas_sugerencias` = metricas exactas de las sugerencias que Google no devolvio como idea.
    """
    filas: dict[str, dict] = {}
    for r in ideas:
        t = (r.get("text") or "").strip()
        if t:
            filas.setdefault(t.lower(), fila(t, r.get("keywordIdeaMetrics"), concepto=_concepto(r)))
    sug = {s.strip().lower(): s.strip() for s in (sugerencias or []) if s.strip()}
    for k, original in sug.items():
        if k in filas:
            filas[k]["sugerencia"] = True
        else:
            filas[k] = fila(original, (metricas_sugerencias or {}).get(k), sugerencia=True)
    lista = sorted(filas.values(), key=lambda f: (f["volumen"] is None, -(f["volumen"] or 0), f["keyword"]))
    marcar_tipos(lista, semillas)
    return {"filas": lista, "terminos": por_terminos(lista), "totales": totales(lista)}


# ── Resumen de una keyword ────────────────────────────────────────────────

def resumen(texto: str, m: dict | None, volumenes: list[dict] | None = None) -> dict:
    """La ficha de una keyword: sus metricas, estacionalidad y variaciones que Google agrupa con ella."""
    f = fila(texto, m)
    f["tipo"] = "coincidente"
    s = f["tendencia"]
    f["variaciones"] = list((m or {}).get("closeVariants") or [])[:20]
    f["meses"] = [f"{a}-{mes:02d}" for a, mes in meses_de(volumenes or (m or {}).get("monthlySearchVolumes"))]
    if len(s) >= 6:
        mitad = len(s) // 2
        antes, despues = sum(s[:mitad]) / mitad, sum(s[mitad:]) / (len(s) - mitad)
        f["tendencia_pct"] = round((despues / antes - 1) * 100) if antes else None
        meses = meses_de(volumenes or (m or {}).get("monthlySearchVolumes"))
        if meses and max(s) > 0:
            f["mes_pico"] = NOMBRE_MES[meses[s.index(max(s))][1]]
    else:
        f["tendencia_pct"] = None
    return f
