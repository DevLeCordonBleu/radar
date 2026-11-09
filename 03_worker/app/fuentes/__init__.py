# -*- coding: utf-8 -*-
"""
De donde salen los anuncios. Dos fuentes con el mismo contrato (lanzar /
consultar / abortar):

  - navegador: lee la Biblioteca de Meta con el Chrome del equipo. Gratis.
  - apify: el actor de Apify. Necesita APIFY_TOKEN (y credito).

ANUNCIOS_FUENTE en el .env: auto (Apify si hay token, si no el navegador),
navegador o apify. El `run` de cada busqueda lleva la fuente: los del
navegador empiezan por «nav».
"""
from __future__ import annotations

import os

from app.apify import cliente as apify
from . import navegador


def elegida() -> str:
    pedida = os.environ.get("ANUNCIOS_FUENTE", "auto").strip().lower()
    if pedida in ("navegador", "apify"):
        return pedida
    return "apify" if apify.tokens() else "navegador"


def lanzar(terminos: list[dict], pais: str, maximo: int, solo_activos: bool) -> dict:
    if elegida() == "apify":
        return {**apify.lanzar(terminos, pais, maximo, solo_activos), "fuente": "apify"}
    return navegador.lanzar(terminos, pais, maximo, solo_activos)


def consultar(run: str, t: int) -> dict:
    return navegador.consultar(run) if run.startswith("nav") else apify.consultar(run, t)


def abortar(run: str, t: int) -> None:
    if run.startswith("nav"):
        navegador.abortar(run)
    else:
        apify.abortar(run, t)
