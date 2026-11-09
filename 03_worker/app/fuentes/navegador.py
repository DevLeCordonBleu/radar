# -*- coding: utf-8 -*-
"""
Fuente GRATUITA de anuncios: lee la Biblioteca de Anuncios de Meta con el Chrome
del equipo, sin cuenta ni token.

La Biblioteca es publica (no pide iniciar sesion). La pagina carga sus anuncios
como JSON —los primeros dentro del HTML y el resto en las peticiones /api/graphql
que hace al desplazarse—, con la misma estructura que devuelve el actor de Apify
(`ad_archive_id`, `page_name`, `snapshot.body.text`…). Aqui solo se recogen esos
JSON mientras se desplaza la pagina, asi que `normalizar.py` los entiende tal cual.

Funciona como Apify: `lanzar` arranca la busqueda en segundo plano y `consultar`
dice cuantos lleva o los devuelve al terminar. Asi el backend no distingue fuentes.

Limites honestos: Meta puede cambiar la pagina o frenar las lecturas automaticas
si se abusa (pocas busquedas al dia no deberian notarse). Sus condiciones de uso
restringen la recogida automatica; Apify hace lo mismo desde sus servidores.
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid
from dataclasses import dataclass, field

from app.apify.cliente import url_biblioteca
from app.compartido.errores import ErrorExterno

ESPERA_CARGA_MS = 4000
ESPERA_SCROLL_MS = 1800
SIN_CRECER_MAX = 4               # scrolls seguidos sin anuncios nuevos = se acabo la lista
TOPE_POR_URL_S = 180
TOPE_TOTAL_S = 12 * 60
BOTONES_COOKIES = ["Permitir todas las cookies", "Allow all cookies", "Aceptar todo", "Permitir cookies"]
_SCRIPT_JSON = re.compile(r'<script type="application/json"[^>]*>(.*?)</script>', re.S)


@dataclass
class Trabajo:
    id: str
    terminos: list[dict]
    pais: str
    maximo: int
    solo_activos: bool
    estado: str = "corriendo"      # corriendo | listo | error
    items: dict = field(default_factory=dict)
    error: str | None = None
    parar: threading.Event = field(default_factory=threading.Event)
    creado: float = field(default_factory=time.time)


_trabajos: dict[str, Trabajo] = {}
_cerrojo = threading.Lock()


# ── Extraccion (pura, se prueba sin navegador) ────────────────────────────

def recoger(objeto, destino: dict) -> int:
    """Mete en `destino` cada anuncio (dict con ad_archive_id y snapshot) que haya dentro de `objeto`."""
    nuevos = 0
    pila = [objeto]
    while pila:
        o = pila.pop()
        if isinstance(o, dict):
            if "ad_archive_id" in o and isinstance(o.get("snapshot"), dict):
                clave = str(o["ad_archive_id"])
                if clave not in destino:
                    destino[clave] = o
                    nuevos += 1
                continue                       # un anuncio no contiene otros anuncios
            pila.extend(o.values())
        elif isinstance(o, list):
            pila.extend(o)
    return nuevos


def de_respuesta(texto: str, destino: dict) -> int:
    """Una respuesta de /api/graphql: puede traer el prefijo «for (;;);» y varios JSON, uno por linea."""
    nuevos = 0
    for linea in texto.removeprefix("for (;;);").splitlines():
        linea = linea.strip()
        if linea[:1] in "{[":
            try:
                nuevos += recoger(json.loads(linea), destino)
            except ValueError:
                pass
    return nuevos


def de_html(html: str, destino: dict) -> int:
    """Los primeros anuncios vienen dentro del HTML, en bloques <script type="application/json">."""
    nuevos = 0
    for bloque in _SCRIPT_JSON.findall(html):
        if "ad_archive_id" not in bloque:
            continue
        try:
            nuevos += recoger(json.loads(bloque), destino)
        except ValueError:
            pass
    return nuevos


# ── Navegador ─────────────────────────────────────────────────────────────

def _abrir(p):
    """El Chrome instalado; si no esta, el Chromium de Playwright."""
    try:
        return p.chromium.launch(channel="chrome", headless=True)
    except Exception:  # noqa: BLE001
        try:
            return p.chromium.launch(headless=True)
        except Exception as e:  # noqa: BLE001
            raise ErrorExterno("No se pudo abrir Chrome para leer la Biblioteca de Meta. Instala Google Chrome o ejecuta "
                               "`python -m playwright install chromium` en 03_worker.") from e


def _aceptar_cookies(pagina) -> None:
    for texto in BOTONES_COOKIES:
        try:
            b = pagina.get_by_role("button", name=texto)
            if b.count():
                b.first.click(timeout=2000)
                return
        except Exception:  # noqa: BLE001
            pass


def _ejecutar(t: Trabajo) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        t.estado, t.error = "error", "Falta Playwright en el worker: `pip install playwright` en 03_worker."
        return
    inicio = time.time()
    try:
        with sync_playwright() as p:
            nav = _abrir(p)
            try:
                ctx = nav.new_context(locale="es-PE", viewport={"width": 1366, "height": 900})
                pagina = ctx.new_page()
                actual: dict = {}

                def al_responder(r):
                    if "/api/graphql" in r.url:
                        try:
                            de_respuesta(r.text(), actual)
                        except Exception:  # noqa: BLE001 - una respuesta rara no rompe la busqueda
                            pass

                pagina.on("response", al_responder)
                por_url = max(10, -(-t.maximo // max(1, len(t.terminos))))
                for termino in t.terminos:
                    if t.parar.is_set() or len(t.items) >= t.maximo:
                        break
                    actual.clear()
                    url = url_biblioteca(termino["valor"], termino.get("modo", "marca"), t.pais, t.solo_activos)
                    pagina.goto(url, wait_until="domcontentloaded", timeout=60000)
                    if re.search(r"/(login|checkpoint)", pagina.url):
                        raise ErrorExterno("Meta pidió iniciar sesión para ver la Biblioteca (suele ser un freno temporal por "
                                           "muchas búsquedas seguidas). Espera una hora y continúa.")
                    _aceptar_cookies(pagina)
                    pagina.wait_for_timeout(ESPERA_CARGA_MS)
                    de_html(pagina.content(), actual)
                    sin_crecer, desde = 0, time.time()
                    while (len(actual) < por_url and sin_crecer < SIN_CRECER_MAX and not t.parar.is_set()
                           and time.time() - desde < TOPE_POR_URL_S and time.time() - inicio < TOPE_TOTAL_S):
                        antes = len(actual)
                        pagina.mouse.wheel(0, 5000)
                        pagina.wait_for_timeout(ESPERA_SCROLL_MS)
                        sin_crecer = sin_crecer + 1 if len(actual) == antes else 0
                    for clave, item in list(actual.items())[:por_url]:
                        t.items.setdefault(clave, item)
            finally:
                nav.close()
        t.estado = "listo"
    except ErrorExterno as e:
        t.estado, t.error = "error", str(e)
    except Exception as e:  # noqa: BLE001
        t.estado, t.error = "error", f"No se pudo leer la Biblioteca de Meta: {str(e)[:200]}"


# ── Contrato (igual que Apify) ────────────────────────────────────────────

def lanzar(terminos: list[dict], pais: str = "PE", maximo: int = 100, solo_activos: bool = True) -> dict:
    if not terminos:
        raise ErrorExterno("No hay nada que buscar.")
    with _cerrojo:
        for k in [k for k, v in _trabajos.items() if time.time() - v.creado > 3600]:
            del _trabajos[k]
        if any(v.estado == "corriendo" for v in _trabajos.values()):
            raise ErrorExterno("Ya hay una búsqueda en la Biblioteca de Meta en curso. Espera a que termine.")
        t = Trabajo(id=f"nav{uuid.uuid4().hex[:16]}", terminos=terminos, pais=pais, maximo=maximo, solo_activos=solo_activos)
        _trabajos[t.id] = t
    threading.Thread(target=_ejecutar, args=(t,), daemon=True, name=f"meta-{t.id}").start()
    return {"run": t.id, "t": 0, "agotados": [], "fuente": "navegador"}


def _trabajo(run: str) -> Trabajo:
    t = _trabajos.get(run)
    if not t:
        raise ErrorExterno("La búsqueda ya no existe (se reinició el worker). Vuelve a lanzarla.")
    return t


def consultar(run: str) -> dict:
    t = _trabajo(run)
    if t.estado == "corriendo":
        return {"estado": "corriendo", "anuncios": len(t.items)}
    if t.estado == "error":
        raise ErrorExterno(t.error or "La búsqueda en la Biblioteca de Meta falló.")
    return {"estado": "listo", "items": list(t.items.values())}


def abortar(run: str) -> None:
    t = _trabajos.get(run)
    if t:
        t.parar.set()
