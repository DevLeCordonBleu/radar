# -*- coding: utf-8 -*-
"""
«Sugerencias de búsqueda»: lo que Google autocompleta mientras se escribe.

Usa el endpoint publico del autocompletado de Google (el mismo que alimenta la
barra de busqueda). No es una API oficial ni tiene garantias: si falla o cambia,
el explorador sigue funcionando sin esta pestana.
"""
from __future__ import annotations

import json
import string
from concurrent.futures import ThreadPoolExecutor

import httpx

URL = "https://suggestqueries.google.com/complete/search"
PREGUNTAS = ["como", "que", "cual", "por que", "donde", "cuando", "para que", "quien", "cuanto"]
PARALELO = 6
MAX_CONSULTAS = 40

_http = lambda: httpx.Client(timeout=8, headers={"user-agent": "Mozilla/5.0"})  # noqa: E731


def _una(cliente: httpx.Client, consulta: str, pais: str, idioma: str) -> list[str]:
    try:
        r = cliente.get(URL, params={"client": "firefox", "q": consulta, "hl": idioma, "gl": pais.lower()})
        if not r.is_success:
            return []
        datos = json.loads(r.content.decode(r.encoding or "utf-8", errors="replace"))
        return [s for s in datos[1] if isinstance(s, str)]
    except (httpx.HTTPError, ValueError, IndexError, TypeError):
        return []


def consultas_de(semilla: str) -> list[str]:
    """La semilla sola, la semilla + cada letra, y las preguntas + la semilla."""
    s = semilla.strip()
    return [s, *(f"{s} {c}" for c in string.ascii_lowercase), *(f"{p} {s}" for p in PREGUNTAS)]


def buscar(semillas: list[str], pais: str, idioma: str) -> list[str]:
    """Sugerencias unicas (sin las propias semillas) para todas las semillas, o [] si Google no responde."""
    consultas = [c for s in semillas[:3] for c in consultas_de(s)][:MAX_CONSULTAS]
    with _http() as c, ThreadPoolExecutor(PARALELO) as pool:
        resultados = list(pool.map(lambda q: _una(c, q, pais, idioma), consultas))
    propias = {s.strip().lower() for s in semillas}
    vistas: dict[str, str] = {}
    for lista in resultados:
        for s in lista:
            k = s.strip().lower()
            if k and k not in propias and k not in vistas:
                vistas[k] = s.strip()
    return list(vistas.values())
