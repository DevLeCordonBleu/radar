# -*- coding: utf-8 -*-
"""
Paises e idiomas que acepta Keyword Planner, con los identificadores de Google
(`geoTargetConstants/<id>` y `languageConstants/<id>`). Son ids estables
publicados por Google; la lista cubre Latinoamerica, Espana y los mercados
habituales. Para anadir uno, basta una linea aqui.
"""

PAISES: dict[str, dict] = {
    "PE": {"nombre": "Perú", "geo": 2604},
    "MX": {"nombre": "México", "geo": 2484},
    "CO": {"nombre": "Colombia", "geo": 2170},
    "CL": {"nombre": "Chile", "geo": 2152},
    "AR": {"nombre": "Argentina", "geo": 2032},
    "EC": {"nombre": "Ecuador", "geo": 2218},
    "BO": {"nombre": "Bolivia", "geo": 2068},
    "UY": {"nombre": "Uruguay", "geo": 2858},
    "PY": {"nombre": "Paraguay", "geo": 2600},
    "VE": {"nombre": "Venezuela", "geo": 2862},
    "CR": {"nombre": "Costa Rica", "geo": 2188},
    "PA": {"nombre": "Panamá", "geo": 2591},
    "DO": {"nombre": "República Dominicana", "geo": 2214},
    "GT": {"nombre": "Guatemala", "geo": 2320},
    "ES": {"nombre": "España", "geo": 2724},
    "US": {"nombre": "Estados Unidos", "geo": 2840},
    "BR": {"nombre": "Brasil", "geo": 2076},
    "GB": {"nombre": "Reino Unido", "geo": 2826},
    "FR": {"nombre": "Francia", "geo": 2250},
}

IDIOMAS: dict[str, dict] = {
    "es": {"nombre": "Español", "id": 1003},
    "en": {"nombre": "Inglés", "id": 1000},
    "pt": {"nombre": "Portugués", "id": 1014},
    "fr": {"nombre": "Francés", "id": 1002},
}

# Paises que se consultan en «Volumen por pais» del resumen.
PAISES_RESUMEN = ["PE", "MX", "CO", "CL", "AR", "EC", "ES", "US"]


from app.compartido.errores import ErrorExterno  # noqa: E402


class PaisNoSoportado(ErrorExterno):
    """País o idioma que Keyword Planner no tiene en esta lista."""


def geo(codigo: str) -> str:
    p = PAISES.get(codigo.upper())
    if not p:
        raise PaisNoSoportado(f"País no soportado: {codigo}. Disponibles: {', '.join(PAISES)}.")
    return f"geoTargetConstants/{p['geo']}"


def idioma(codigo: str) -> str:
    i = IDIOMAS.get(codigo.lower())
    if not i:
        raise PaisNoSoportado(f"Idioma no soportado: {codigo}. Disponibles: {', '.join(IDIOMAS)}.")
    return f"languageConstants/{i['id']}"
