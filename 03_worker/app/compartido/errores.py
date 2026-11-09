# -*- coding: utf-8 -*-
"""Errores con mensaje apto para mostrarse tal cual en el panel."""


class ErrorExterno(Exception):
    """Un servicio externo (Apify, Gemini) no pudo completar la peticion."""


class CuotaAgotada(ErrorExterno):
    """Gemini agoto la cuota de todos los modelos y claves. Lo hecho hasta aqui esta guardado."""
