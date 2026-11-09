# -*- coding: utf-8 -*-
"""
envfile.py — Lee las claves del archivo .env y las publica como variables de
entorno. Sin dependencias: así no hay que configurar variables en Windows,
basta con editar el archivo .env que está del worker (03_worker/.env).

Formato del .env (una por línea, se ignoran comentarios con #):

    ANTHROPIC_API_KEY=sk-ant-...
    PEXELS_API_KEY=...

Una variable definida de verdad en el sistema siempre manda sobre el .env.
"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))
_CARGADO = False


def load(path=None, force=False):
    """Carga el .env una sola vez. Devuelve cuántas claves publicó."""
    global _CARGADO
    if _CARGADO and not force:
        return 0
    _CARGADO = True
    try:
        with open(path or os.path.join(BASE, '.env'), encoding='utf-8-sig') as f:
            lineas = f.readlines()
    except OSError:
        return 0                      # no existe: es opcional
    n = 0
    for ln in lineas:
        ln = ln.strip()
        if not ln or ln.startswith('#') or '=' not in ln:
            continue
        k, v = ln.split('=', 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and not os.environ.get(k):
            os.environ[k] = v
            n += 1
    return n
