# -*- coding: utf-8 -*-
"""Normalizacion de texto compartida por el informe y la identificacion de marcas."""
import re
import unicodedata

PARADA = frozenset(
    "de del la el los las y e o u en para con por al a un una unos unas que tu tus su sus mi mis "
    "mas muy sin sobre desde hasta entre como lo le les se es son ser the and of for to with your our".split()
)


def sin_acentos(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def normalizar(t: str) -> str:
    """Minusculas, sin acentos ni signos, espacios simples."""
    t = sin_acentos(t.lower())
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def raiz(palabra: str) -> str:
    return palabra[:4] if len(palabra) > 4 else re.sub(r"(es|s)$", "", palabra)


def palabras_clave(t: str) -> set[str]:
    return {raiz(p) for p in normalizar(t).split() if len(p) > 2 and p not in PARADA}


def limpiar(t: str) -> str:
    """Quita saltos y espacios repetidos de un texto de anuncio."""
    return re.sub(r"\s+", " ", t or "").strip()
