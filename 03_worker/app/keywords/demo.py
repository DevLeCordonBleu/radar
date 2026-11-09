# -*- coding: utf-8 -*-
"""
Datos de DEMOSTRACION para KeyWords Explorer.

Generan keywords y metricas inventadas, deterministas (la misma busqueda sale
siempre igual), con la MISMA forma que devuelve Google Ads. Sirven para ver el
modulo y probarlo sin conectar ninguna cuenta. El panel los marca siempre como
demostracion: ningun numero de aqui es real.
"""
from __future__ import annotations

import hashlib
import math
from datetime import date

SUFIJOS = ["precio", "curso", "online", "gratis", "para principiantes", "paso a paso", "ejemplos", "mejores", "opiniones", "guía",
           "tutorial", "cerca de mi", "barato", "certificado", "2026", "pdf", "ideas", "tipos", "diferencia", "costo", "comprar",
           "alternativas", "herramientas", "plantilla", "para empresas", "profesional", "desde cero", "con certificado"]
PREFIJOS = ["mejor", "como", "que es", "curso de", "cual es el mejor", "donde comprar", "para que sirve", "tipos de", "precio de",
            "ideas de", "como aprender", "por que usar", "cuando usar"]
RELACIONADOS = ["escuela", "academia", "instituto", "taller", "clases", "recetas", "libro", "canal de youtube", "blog", "certificación"]
COMPETENCIA = ["LOW", "MEDIUM", "HIGH"]


def _h(*partes: str) -> float:
    """Numero estable entre 0 y 1 a partir de un texto."""
    return int(hashlib.sha256("|".join(partes).encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def _redondear(n: float) -> int:
    """Dos cifras significativas, como los agrupa Keyword Planner."""
    if n < 100:
        return max(10, int(round(n, -1)))
    cifras = int(math.log10(n)) - 1
    return int(round(n, -cifras))


def _meses(hasta: date | None = None) -> list[tuple[int, int]]:
    hoy = hasta or date.today()
    a, m = hoy.year, hoy.month - 1 or 12
    if hoy.month == 1:
        a -= 1
    salida = []
    for _ in range(12):
        salida.append((a, m))
        m -= 1
        if m == 0:
            a, m = a - 1, 12
    return salida[::-1]


NOMBRES = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]


def metricas_de(texto: str, base: float, pais: str = "PE") -> dict:
    """keywordMetrics inventadas, en el formato de Google (enteros como texto)."""
    vol = _redondear(max(10, base))
    fase = _h(texto, "fase") * 2 * math.pi
    amplitud = 0.1 + _h(texto, "amp") * 0.5
    serie = []
    for i, (a, m) in enumerate(_meses()):
        factor = 1 + amplitud * math.sin(fase + i * math.pi / 6) + (_h(texto, str(i)) - 0.5) * 0.2
        serie.append({"year": str(a), "month": NOMBRES[m - 1], "monthlySearches": str(_redondear(max(10, vol * factor)))})
    comp = COMPETENCIA[int(_h(texto, "comp") * 3)]
    bajo = round(0.1 + _h(texto, "bajo") * 1.5, 2)
    return {
        "avgMonthlySearches": str(vol), "monthlySearchVolumes": serie, "competition": comp,
        "competitionIndex": str(int({"LOW": 8, "MEDIUM": 45, "HIGH": 78}[comp] + _h(texto, "idx") * 18)),
        "lowTopOfPageBidMicros": str(int(bajo * 1_000_000)),
        "highTopOfPageBidMicros": str(int((bajo * (1.8 + _h(texto, "alto"))) * 1_000_000)),
    }


def _volumen(kw: str) -> float:
    """
    Volumen inventado que depende SOLO de la keyword: asi la fila de la tabla y su ficha
    coinciden siempre. Cuantas mas palabras, menos busquedas (la cola larga es mas pequena).
    """
    palabras = max(1, len(kw.split()))
    return max(10.0, 24000 * (_h(kw, "vol") ** 2.5) * (0.5 ** (palabras - 1)))


def ideas(semillas: list[str], url: str | None, pais: str, maximo: int = 1000) -> list[dict]:
    """results[] de generateKeywordIdeas, inventados."""
    base = list(semillas) or ([url.split("//")[-1].split("/")[0].replace("www.", "").split(".")[0]] if url else [])
    vistos: dict[str, dict] = {}
    for s in base:
        s = s.strip().lower()
        # Sin prefijos que repitan la primera palabra de la semilla («curso de curso de cocina»).
        candidatas = [s] + [f"{s} {x}" for x in SUFIJOS] + [f"{p} {s}" for p in PREFIJOS if p.split()[0] != s.split()[0]]
        primera = s.split()[0] if s.split() else s
        candidatas += [f"{primera} {r}" for r in RELACIONADOS] + [f"{r} de {s.split()[-1]}" for r in RELACIONADOS]
        for kw in candidatas:
            if kw not in vistos:
                vistos[kw] = {"text": kw, "keywordIdeaMetrics": metricas_de(kw, _volumen(kw), pais),
                              "keywordAnnotations": {"concepts": [{"name": s}]}}
    return list(vistos.values())[:maximo]


def metricas(keywords: list[str], pais: str | None) -> dict[str, dict]:
    salida = {}
    for k in keywords:
        k = k.strip().lower()
        if k:
            m = metricas_de(k, _volumen(k), pais or "")
            m["closeVariants"] = [k + "s", k.replace(" de ", " ")][:2]
            salida[k] = m
    return salida


def sugerencias(semillas: list[str]) -> list[str]:
    """Algunas sugerencias de autocompletado inventadas."""
    plantillas = ["{} en lima", "{} para negocios", "{} 2026", "como {} paso a paso", "{} que es", "{} vs {}"]
    salida = []
    for s in semillas[:3]:
        salida += [p.format(s, s + " pro") for p in plantillas]
    return salida
