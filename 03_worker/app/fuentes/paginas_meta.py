# -*- coding: utf-8 -*-
"""
Sugerencias de paginas de Facebook mientras se escribe el nombre de un competidor.

Usa el autocompletado de la Biblioteca de Anuncios de Meta (publico, sin sesion):
al escribir en su buscador, la pagina pide a /api/graphql `typeahead_suggestions`
con las paginas que coinciden (id, nombre, categoria, foto, seguidores, @usuario).
La primera vez se escribe en ese buscador y se guarda la peticion que hace la pagina
(`plantilla`); las siguientes repiten esa peticion desde la propia pagina cambiando
solo el texto: una sola llamada (~0,5 s) en vez de teclear letra a letra, que dispara
una llamada por letra. Si repetirla falla, se vuelve a teclear.

Un Chrome queda abierto en su propio hilo (Playwright no se comparte entre hilos):
la primera consulta tarda lo que tarda en abrirse (~3-10 s). Solo se atiende la
consulta mas reciente: las que se quedaron en cola mientras se escribia se descartan.
Se cierra solo tras un rato sin uso. Si Meta cambia la pagina, esto deja de
sugerir y el panel sigue aceptando el nombre o el enlace escritos a mano.
"""
from __future__ import annotations

import json
import queue
import threading
import time
from concurrent.futures import CancelledError, Future
from urllib.parse import parse_qs, quote, urlencode

from app.analisis.texto import normalizar
from app.compartido.errores import ErrorExterno

CIERRE_INACTIVO_S = 20 * 60
RENOVAR_PAGINA_S = 30 * 60
ESPERA_RESPUESTA_S = 7.0
ESPERA_REPETIR_MS = 5000
CACHE_S = 3600
MAXIMO = 8

_cache: dict[tuple[str, str], tuple[float, list[dict]]] = {}

# Repite la peticion del autocompletado desde la pagina (con sus cookies y su token).
_REPETIR_JS = """async ([url, cuerpo, cabeceras, espera]) => {
  const corte = new AbortController();
  const reloj = setTimeout(() => corte.abort(), espera);
  try {
    const r = await fetch(url, {method: 'POST', body: cuerpo, headers: cabeceras, credentials: 'include', signal: corte.signal});
    return r.ok ? await r.text() : null;
  } catch (e) {
    return null;
  } finally {
    clearTimeout(reloj);
  }
}"""


# ── Respuesta de Meta ─────────────────────────────────────────────────────

def _sugerencias(objeto) -> dict | None:
    """Busca `typeahead_suggestions` dentro de una respuesta de /api/graphql."""
    try:
        return objeto["data"]["ad_library_main"]["typeahead_suggestions"]
    except (KeyError, TypeError):
        return None


def de_respuesta(texto: str) -> tuple[str | None, list[dict]] | None:
    """(texto consultado, paginas) de una respuesta de graphql, o None si no es de sugerencias."""
    for linea in texto.splitlines() or [texto]:
        linea = linea.strip()
        if not linea.startswith("{") or "typeahead_suggestions" not in linea:
            continue
        try:
            s = _sugerencias(json.loads(linea))
        except ValueError:
            continue
        if s is None:
            continue
        # Meta devuelve la frase consultada entre comillas: dice a que tecleo corresponde.
        consultado = (s.get("exact_phrase_results") or "").strip().strip('"') or None
        return consultado, [p for p in (normalizar_pagina(x) for x in s.get("page_results") or []) if p]
    return None


def normalizar_pagina(p: dict) -> dict | None:
    if not isinstance(p, dict) or not p.get("page_id") or p.get("page_is_deleted"):
        return None
    return {
        "page_id": str(p["page_id"]),
        "nombre": p.get("name") or "",
        "categoria": p.get("category"),
        "avatar": p.get("image_uri"),
        "seguidores": p.get("likes"),
        "ig_usuario": p.get("ig_username"),
        "ig_seguidores": p.get("ig_followers"),
        "alias": p.get("page_alias"),
        "verificada": p.get("verification") == "BLUE_VERIFIED",
    }


# ── Chrome en su hilo ─────────────────────────────────────────────────────

class _Buscador(threading.Thread):
    def __init__(self):
        super().__init__(name="sugerencias-meta", daemon=True)
        self.pendientes: queue.Queue[tuple[str, str, Future]] = queue.Queue()
        self._pw = self._nav = self._pagina = None
        self._pais = None
        self._abierta = 0.0
        self._recibidas: dict[str, list[dict]] = {}
        self._plantilla: dict | None = None

    def run(self):
        while True:
            try:
                texto, pais, futuro = self.pendientes.get(timeout=CIERRE_INACTIVO_S)
            except queue.Empty:
                self._cerrar()
                continue
            # Mientras se atendia otra, se siguio escribiendo: solo vale la ultima.
            while True:
                try:
                    siguiente = self.pendientes.get_nowait()
                except queue.Empty:
                    break
                futuro.cancel()
                texto, pais, futuro = siguiente
            if futuro.set_running_or_notify_cancel():
                try:
                    futuro.set_result(self._consultar(texto, pais))
                except Exception as e:  # noqa: BLE001
                    self._cerrar()  # la proxima consulta abre un Chrome limpio
                    futuro.set_exception(e)

    def _cerrar(self):
        try:
            if self._nav is not None:
                self._nav.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception:  # noqa: BLE001
            pass
        self._pw = self._nav = self._pagina = None
        self._plantilla = None

    def _al_pedir(self, r):
        """Guarda la peticion del autocompletado que hace la pagina, para repetirla."""
        try:
            if "graphql" in r.url and "TypeaheadSuggestion" in (r.headers.get("x-fb-friendly-name") or ""):
                self._plantilla = {"url": r.url, "cuerpo": r.post_data,
                                   "cabeceras": {k: v for k, v in r.headers.items() if k.startswith("x-") or k == "content-type"}}
        except Exception:  # noqa: BLE001 - sin plantilla se teclea, como antes
            pass

    def _repetir(self, texto: str, pais: str) -> list[dict] | None:
        """Una sola peticion con el texto entero; None si no hay plantilla o algo no cuadra."""
        p = self._plantilla
        if not p or not p["cuerpo"]:
            return None
        campos = parse_qs(p["cuerpo"], keep_blank_values=True)
        try:
            variables = json.loads(campos["variables"][0])
        except (KeyError, ValueError):
            return None
        variables.update(queryString=texto, country=pais)
        campos["variables"] = [json.dumps(variables, ensure_ascii=False)]
        cuerpo = urlencode({k: v[0] for k, v in campos.items()})
        respuesta = self._pagina.evaluate(_REPETIR_JS, [p["url"], cuerpo, p["cabeceras"], ESPERA_REPETIR_MS])
        hallado = de_respuesta(respuesta) if respuesta else None
        if not hallado:
            return None
        consultado, paginas = hallado
        return paginas if consultado is None or normalizar(consultado) == normalizar(texto) else None

    def _al_responder(self, r):
        if "graphql" not in r.url:
            return
        try:
            cuerpo = r.text()
        except Exception:  # noqa: BLE001
            return
        hallado = de_respuesta(cuerpo)
        if hallado and hallado[0]:
            self._recibidas[normalizar(hallado[0])] = hallado[1]

    def _abrir(self, texto: str, pais: str):
        from playwright.sync_api import sync_playwright

        from .navegador import _abrir, _aceptar_cookies

        self._cerrar()
        self._pw = sync_playwright().start()
        self._nav = _abrir(self._pw)
        ctx = self._nav.new_context(locale="es-PE", viewport={"width": 1366, "height": 900})
        self._pagina = ctx.new_page()
        self._pagina.on("response", self._al_responder)
        self._pagina.on("request", self._al_pedir)
        # El buscador solo aparece con una busqueda ya hecha.
        self._pagina.goto(
            "https://www.facebook.com/ads/library/?active_status=active&ad_type=all"
            f"&country={pais}&media_type=all&search_type=keyword_unordered&q={quote(texto)}",
            wait_until="domcontentloaded",
        )
        _aceptar_cookies(self._pagina)
        self._pagina.wait_for_selector('input[type="search"]', timeout=20000)
        self._pais, self._abierta = pais, time.time()

    def _consultar(self, texto: str, pais: str) -> list[dict]:
        if self._pagina is None or pais != self._pais or time.time() - self._abierta > RENOVAR_PAGINA_S:
            self._abrir(texto, pais)
        try:
            rapidas = self._repetir(texto, pais)
        except Exception:  # noqa: BLE001 - se prueba tecleando
            rapidas = None
        if rapidas is not None:
            return rapidas
        clave = normalizar(texto)
        self._recibidas.pop(clave, None)
        caja = self._pagina.locator('input[type="search"]').first
        caja.click()
        caja.fill("")
        caja.type(texto, delay=40)
        limite = time.time() + ESPERA_RESPUESTA_S
        while time.time() < limite:
            self._pagina.wait_for_timeout(150)
            if clave in self._recibidas:
                return self._recibidas.pop(clave)
        # Sin respuesta para el texto exacto: vale la ultima que llego si es de un prefijo suyo.
        prefijos = [k for k in self._recibidas if clave.startswith(k)]
        if prefijos:
            return self._recibidas[max(prefijos, key=len)]
        raise ErrorExterno("Meta no devolvió sugerencias a tiempo. Escribe el nombre o pega el enlace de su página.")


_buscador: _Buscador | None = None
_candado = threading.Lock()


def _hilo() -> _Buscador:
    global _buscador
    with _candado:
        if _buscador is None or not _buscador.is_alive():
            _buscador = _Buscador()
            _buscador.start()
        return _buscador


def preparar(pais: str = "PE") -> bool:
    """Abre Chrome por adelantado (al entrar en «Análisis de competencia») para que la primera sugerencia no tarde."""
    b = _hilo()
    if b._pagina is not None or not b.pendientes.empty():
        return False
    b.pendientes.put(("cocina", (pais or "PE").upper(), Future()))
    return True


def sugerir(texto: str, pais: str = "PE") -> list[dict]:
    """Paginas de Facebook cuyo nombre coincide con `texto` (las de la Biblioteca de Anuncios)."""
    texto = " ".join(texto.split())[:60]
    pais = (pais or "PE").upper()
    clave = (pais, normalizar(texto))
    if len(clave[1]) < 3:
        return []
    guardado = _cache.get(clave)
    if guardado and time.time() - guardado[0] < CACHE_S:
        return guardado[1]
    futuro: Future = Future()
    _hilo().pendientes.put((texto, pais, futuro))
    try:
        paginas = futuro.result(timeout=45)[:MAXIMO]
    except ErrorExterno:
        raise
    except CancelledError:
        raise ErrorExterno("Se pidió otra búsqueda más reciente.") from None
    except Exception as e:  # noqa: BLE001
        raise ErrorExterno(f"No se pudieron pedir sugerencias a Meta ({type(e).__name__}). Escribe el nombre o pega el enlace de su página.") from e
    _cache[clave] = (time.time(), paginas)
    return paginas
