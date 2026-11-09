# -*- coding: utf-8 -*-
"""
Markdown -> HTML para los articulos del Plan SEO. Un solo conversor para la vista
previa del panel y para lo que se manda a WordPress: lo que se ve es lo que se envia.

Solo el subconjunto que escribe la IA y que una persona edita a mano: ## y ###,
parrafos, listas (- y 1.), citas (>), **negrita**, *cursiva* y [enlaces](https://...).
Todo el texto se escapa: no pasa HTML crudo. Los «[COMPLETAR: ...]» se resaltan para
que no lleguen a publicarse sin verlos.
"""
from __future__ import annotations

import html
import re

ENLACE = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)")
PENDIENTE = re.compile(r"\[COMPLETAR:[^\]\n]*\]", re.I)
_TITULO = re.compile(r"^(#{1,4})\s+(.+?)\s*#*\s*$")
_VINETA = re.compile(r"^\s*[-*+]\s+(.+)$")
_NUMERO = re.compile(r"^\s*\d+[.)]\s+(.+)$")
_CITA = re.compile(r"^\s*>\s?(.*)$")


def _enlinea(texto: str) -> str:
    t = html.escape(texto, quote=True)
    t = PENDIENTE.sub(lambda m: f'<mark class="completar">{m.group(0)}</mark>', t)
    t = ENLACE.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', t)
    t = re.sub(r"\*\*(?!\s)(.+?)(?<!\s)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![*\w])\*(?![\s*])(.+?)(?<![\s*])\*(?![*\w])", r"<em>\1</em>", t)
    return t


def a_html(md: str) -> str:
    salida: list[str] = []
    parrafo: list[str] = []
    lista: tuple[str, list[str]] | None = None  # (ul|ol, items)
    cita: list[str] = []

    def cerrar():
        nonlocal lista
        if parrafo:
            salida.append(f"<p>{_enlinea(' '.join(parrafo))}</p>")
            parrafo.clear()
        if lista:
            etiqueta, items = lista
            salida.append(f"<{etiqueta}>" + "".join(f"<li>{_enlinea(i)}</li>" for i in items) + f"</{etiqueta}>")
            lista = None
        if cita:
            salida.append(f"<blockquote><p>{_enlinea(' '.join(cita))}</p></blockquote>")
            cita.clear()

    for linea in (md or "").replace("\r\n", "\n").split("\n"):
        if not linea.strip():
            cerrar()
            continue
        if m := _TITULO.match(linea):
            cerrar()
            # El titulo del articulo va aparte: un «#» dentro del contenido baja a h2.
            nivel = max(2, len(m.group(1)))
            salida.append(f"<h{nivel}>{_enlinea(m.group(2))}</h{nivel}>")
            continue
        vineta, numero = _VINETA.match(linea), _NUMERO.match(linea)
        if vineta or numero:
            etiqueta = "ul" if vineta else "ol"
            if parrafo or cita or (lista and lista[0] != etiqueta):
                cerrar()
            if not lista:
                lista = (etiqueta, [])
            lista[1].append((vineta or numero).group(1).strip())
            continue
        if m := _CITA.match(linea):
            if parrafo or lista:
                cerrar()
            cita.append(m.group(1).strip())
            continue
        if lista:
            lista[1][-1] += " " + linea.strip()  # continuacion del ultimo punto
            continue
        if cita:
            cerrar()
        parrafo.append(linea.strip())
    cerrar()
    return "\n".join(salida)


def enlaces(md: str) -> list[str]:
    return [m.group(2) for m in ENLACE.finditer(md or "")]


def solo_enlaces_permitidos(md: str, permitidas: set[str]) -> tuple[str, list[str]]:
    """Un enlace a una URL que no estaba en la entrada se queda en su texto. Devuelve (md, quitadas)."""
    quitadas: list[str] = []

    def cambiar(m: re.Match) -> str:
        if m.group(2) in permitidas:
            return m.group(0)
        quitadas.append(m.group(2))
        return m.group(1)

    return ENLACE.sub(cambiar, md or ""), quitadas


def pendientes(md: str) -> list[str]:
    return [m.group(0) for m in PENDIENTE.finditer(md or "")]
