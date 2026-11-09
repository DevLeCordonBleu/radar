# -*- coding: utf-8 -*-
"""
¿La gente lo busca? Lo comprueba con el autocompletado de Google, el mismo de las
«Sugerencias» del KeyWords Explorer (endpoint publico, sin clave ni garantias).

Es una señal, no un volumen: Google sugiere lo que mucha gente escribe, pero no dice
cuanta. El volumen mensual sale de Google Ads (Keyword Planner), que pide claves.

Señal de una keyword:
- EXACTA: Google sugiere esa misma busqueda (o las mismas palabras en otro orden; entonces
  la «forma» es la de Google, que es como la escribe la gente).
- VARIANTES: sugiere busquedas mas largas que la contienen.
- NINGUNA: no sugiere nada que la contenga.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor

import httpx

from app.keywords import sugerencias as autocompletado

CACHE_S = 24 * 3600
MAX_POR_GRUPO = 3
MAX_SUGERENCIAS = 4
RANGO = {"EXACTA": 2, "VARIANTES": 1, "NINGUNA": 0}

_http = lambda: httpx.Client(timeout=8, headers={"user-agent": "Mozilla/5.0"})  # noqa: E731
_cache: dict[tuple[str, str, str], tuple[float, list[str]]] = {}


def normal(texto: str) -> str:
    """Minusculas, sin tildes ni signos: «¿Cómo se hace?» == «como se hace»."""
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s]", " ", t).split())


def _palabras(texto: str) -> list[str]:
    return sorted(normal(texto).split())


def _consultar(cliente: httpx.Client, keyword: str, pais: str, idioma: str) -> list[str] | None:
    """Lo que Google sugiere para `keyword`, o None si no respondio (no es lo mismo que no sugerir nada)."""
    clave = (normal(keyword), pais.upper(), idioma)
    previo = _cache.get(clave)
    if previo and time.time() - previo[0] < CACHE_S:
        return previo[1]
    try:
        r = cliente.get(autocompletado.URL, params={"client": "firefox", "q": keyword, "hl": idioma, "gl": pais.lower()})
        if not r.is_success:
            return None
        datos = json.loads(r.content.decode(r.encoding or "utf-8", errors="replace"))
        lista = [s.strip() for s in datos[1] if isinstance(s, str) and s.strip()]
    except (httpx.HTTPError, ValueError, IndexError, TypeError):
        return None
    _cache[clave] = (time.time(), lista)
    return lista


def senal(keyword: str, sugeridas: list[str]) -> dict:
    """{senal, forma, sugerencias}: `forma` es como la escribe la gente; `sugerencias`, otras que escribe."""
    k, palabras = normal(keyword), _palabras(keyword)
    exacta = next((s for s in sugeridas if normal(s) == k), None) or next((s for s in sugeridas if _palabras(s) == palabras), None)
    if exacta is not None:
        # Si solo cambian tildes o signos se queda la nuestra (Google las quita); si cambia el orden, la de Google.
        forma = keyword if normal(exacta) == k else exacta
        otras = [s for s in sugeridas if _palabras(s) != palabras]
        return {"senal": "EXACTA", "forma": forma, "sugerencias": otras[:MAX_SUGERENCIAS]}
    contienen = [s for s in sugeridas if set(palabras) <= set(normal(s).split())]
    if contienen:
        return {"senal": "VARIANTES", "forma": keyword, "sugerencias": contienen[:MAX_SUGERENCIAS]}
    return {"senal": "NINGUNA", "forma": None, "sugerencias": []}


def comprobar(grupos: list[dict], pais: str = "PE", idioma: str = "es") -> dict:
    """
    Por grupo, la mejor señal de sus keywords (hasta MAX_POR_GRUPO; en empate gana la primera).
    `disponible` es False si Google no respondio a ninguna: quien llama decide sin esta señal.
    """
    pares: list[tuple[int, str]] = []
    for i, g in enumerate(grupos):
        unicas: dict[str, str] = {}
        for k in g["keywords"]:
            unicas.setdefault(normal(k), k.strip())
        unicas.pop("", None)
        pares += [(i, k) for k in list(unicas.values())[:MAX_POR_GRUPO]]
    if not pares:
        return {"disponible": True, "grupos": [{"grupo": g["grupo"], "senal": None, "forma": None, "sugerencias": []} for g in grupos]}
    with _http() as c, ThreadPoolExecutor(autocompletado.PARALELO) as pool:
        respuestas = list(pool.map(lambda p: _consultar(c, p[1], pais, idioma), pares))
    salida = []
    for i, g in enumerate(grupos):
        mejor = None
        for (j, k), sug in zip(pares, respuestas):
            if j != i or sug is None:
                continue
            s = senal(k, sug)
            if mejor is None or RANGO[s["senal"]] > RANGO[mejor["senal"]]:
                mejor = s
        salida.append({"grupo": g["grupo"], **(mejor or {"senal": None, "forma": None, "sugerencias": []})})
    return {"disponible": any(r is not None for r in respuestas), "grupos": salida}
