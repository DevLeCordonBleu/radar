# -*- coding: utf-8 -*-
"""
Guion de un video corto por partes de 10 s (Gemini) y los prompts de cada clip para Vids.

El guion lo escribe Gemini; los prompts los arma este modulo de forma fija, para que el
personaje, el lugar, la voz y las reglas (sin texto ni logos inventados) se repitan igual en
cada clip. La pronunciacion se ajusta solo en el prompt: el guion, los subtitulos y los copys
conservan la ortografia correcta.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

from app.compartido.errores import ErrorExterno
from app.ia import gemini

PROMPTS = Path(__file__).parent / "prompts"
SEGUNDOS_CLIP = 10
MIN_SEGUNDOS, MAX_SEGUNDOS = 10, 60
MAX_PALABRAS_CLIP = 22
NEGOCIO_POR_DEFECTO = "Instituto Le Cordon Bleu Perú"
RUBRO_POR_DEFECTO = "Escuela de cocina peruana e internacional, panadería, pastelería, bar y coctelería"
# Lo que el modelo tiende a inventar mal: rotulos y logos (escribio mal el de la marca en las pruebas).
REGLAS_FIJAS = "Cámara estable. Sin texto en pantalla ni subtítulos. Ropa lisa, sin logos, letras ni escudos."

_CADENAS = {"type": "array", "items": {"type": "string"}}


def numero_partes(segundos: int) -> int:
    return math.ceil(max(MIN_SEGUNDOS, min(MAX_SEGUNDOS, segundos)) / SEGUNDOS_CLIP)


def guion(idea: str, segundos: int, *, keyword: str = "", contexto: dict | None = None, modelo: str | None = None) -> dict:
    """-> {titulo, partes: [{dialogo, escena}], copy_facebook, copy_instagram, hashtags, uso}"""
    c = contexto or {}
    n = numero_partes(segundos)
    ultima = segundos - SEGUNDOS_CLIP * (n - 1)
    sistema = ((PROMPTS / "GUION.md").read_text(encoding="utf-8")
               .replace("{{NEGOCIO}}", (c.get("negocio") or "").strip() or NEGOCIO_POR_DEFECTO)
               .replace("{{RUBRO}}", (c.get("rubro") or "").strip() or RUBRO_POR_DEFECTO))
    texto = (f"Idea: {idea.strip()}\n"
             f"Palabra clave o pregunta de la audiencia: {keyword.strip() or '(ninguna)'}\n"
             f"Duración: {segundos} segundos. PARTES: {n} (la última dura {ultima} segundos).\n"
             f"Protagonista: {(c.get('personaje') or '').strip() or '(el sistema lo describe)'}\n\n"
             f"Datos confirmados (lo único que puedes afirmar):\n{(c.get('datos') or '').strip() or '(ninguno)'}")
    esquema = {"type": "object", "required": ["titulo", "partes", "copy_facebook", "copy_instagram", "hashtags"], "properties": {
        "titulo": {"type": "string"},
        "partes": {"type": "array", "items": {"type": "object", "required": ["dialogo", "escena"],
                                              "properties": {"dialogo": {"type": "string"}, "escena": {"type": "string"}}}},
        "copy_facebook": {"type": "string"}, "copy_instagram": {"type": "string"}, "hashtags": _CADENAS}}
    datos, uso = gemini.generar(sistema, [{"text": texto}], esquema, modelo=modelo, temperatura=0.6)
    partes = [{"dialogo": (p.get("dialogo") or "").strip()[:400], "escena": (p.get("escena") or "").strip()[:300]}
              for p in datos.get("partes") or [] if (p.get("dialogo") or "").strip()]
    if len(partes) < n:
        raise ErrorExterno(f"Gemini escribió {len(partes)} partes de {n}. Suele arreglarse volviendo a intentarlo.")
    return {
        "titulo": (datos.get("titulo") or idea).strip()[:60],
        "partes": partes[:n],
        "copy_facebook": (datos.get("copy_facebook") or "").strip()[:1500],
        "copy_instagram": (datos.get("copy_instagram") or "").strip()[:1500],
        "hashtags": limpiar_hashtags(datos.get("hashtags"), 6),
        "uso": uso,
    }


def limpiar_hashtags(lista: list | None, maximo: int) -> list[str]:
    """Con #, sin simbolos ni repetidos (distingue mayusculas: #Chef y #chef se leen distinto)."""
    salida = []
    for h in lista or []:
        h = "#" + re.sub(r"[^\wáéíóúñü]", "", str(h).strip().lstrip("#"), flags=re.IGNORECASE)
        if len(h) > 1 and h not in salida:
            salida.append(h)
    return salida[:maximo]


def pronunciar(texto: str, pronunciaciones: list[dict] | None) -> str:
    """«Le Cordon Bleu» -> «Le Cordón Blé» solo para la voz; sin distinguir mayusculas."""
    for p in pronunciaciones or []:
        escrito, dice = (p.get("texto") or "").strip(), (p.get("dice") or "").strip()
        if escrito and dice:
            texto = re.sub(rf"(?<!\w){re.escape(escrito)}(?!\w)", dice, texto, flags=re.IGNORECASE)
    return texto


def prompts(partes: list[dict], formato: str, contexto: dict | None = None) -> list[str]:
    """Un prompt por clip: el primero describe todo; los demas piden continuar con lo mismo."""
    c = contexto or {}
    orientacion = "vertical" if formato.upper() == "VERTICAL" else "horizontal"
    personaje = (c.get("personaje") or "").strip().rstrip(".")
    lugar = (c.get("estilo") or "").strip().rstrip(".")
    voz = (c.get("voz") or "en español con acento peruano, con tono cercano").strip().rstrip(".")
    salida = []
    for i, p in enumerate(partes):
        dialogo = pronunciar(p["dialogo"], c.get("pronunciaciones"))
        escena = (p.get("escena") or "").strip().rstrip(".")
        if i == 0:
            piezas = [f"Video realista en formato {orientacion}", lugar, personaje, escena,
                      f"Mira a la cámara y dice {voz}: \"{dialogo}\"", REGLAS_FIJAS]
        else:
            piezas = ["El mismo personaje, en el mismo lugar y con la misma voz, continúa", escena,
                      f"Sigue hablando a la cámara y dice {voz}: \"{dialogo}\"", REGLAS_FIJAS]
        salida.append(". ".join(x for x in piezas if x).replace("..", "."))
    return salida
