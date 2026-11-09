# -*- coding: utf-8 -*-
"""Resumen en lenguaje claro del rendimiento de un periodo (Gemini). Las cifras las calcula el backend."""
from __future__ import annotations

import json
from pathlib import Path

from app.compartido.errores import ErrorExterno
from app.ia import gemini

PROMPT = Path(__file__).parent / "prompts" / "RESUMEN.md"
_CADENAS = {"type": "array", "items": {"type": "string"}}
ESQUEMA = {"type": "object", "required": ["titular", "puntos", "hallazgos", "advertencias"], "properties": {
    "titular": {"type": "string"}, "puntos": _CADENAS, "advertencias": _CADENAS,
    "hallazgos": {"type": "array", "items": {"type": "object", "required": ["titulo", "evidencia", "sugerencia"], "properties": {
        "titulo": {"type": "string"}, "evidencia": {"type": "string"}, "sugerencia": {"type": "string"}}}}}}


def resumir(datos: dict, *, negocio: str = "", rubro: str = "", modelo: str | None = None) -> dict:
    """datos: {periodo, anterior, moneda, kpis, campanas, alertas, ga4?} -> {titular, puntos, hallazgos, advertencias, uso}"""
    sistema = (PROMPT.read_text(encoding="utf-8").replace("{{NEGOCIO}}", negocio.strip() or "la institución")
               .replace("{{RUBRO}}", rubro.strip() or "educación"))
    texto = json.dumps(datos, ensure_ascii=False, default=str)[:60_000]
    r, uso = gemini.generar(sistema, [{"text": texto}], ESQUEMA, modelo=modelo, temperatura=0.3)
    titular = (r.get("titular") or "").strip()
    if not titular:
        raise ErrorExterno("Gemini no devolvió el resumen. Suele arreglarse volviendo a intentarlo.")
    limpiar = lambda xs, n, largo=400: [x.strip()[:largo] for x in xs or [] if isinstance(x, str) and x.strip()][:n]  # noqa: E731
    hallazgos = [{k: (h.get(k) or "").strip()[:400] for k in ("titulo", "evidencia", "sugerencia")}
                 for h in r.get("hallazgos") or [] if isinstance(h, dict) and (h.get("titulo") or "").strip()][:4]
    return {"titular": titular[:300], "puntos": limpiar(r.get("puntos"), 5), "hallazgos": hallazgos,
            "advertencias": limpiar(r.get("advertencias"), 4), "uso": uso}
