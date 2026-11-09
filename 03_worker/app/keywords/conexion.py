# -*- coding: utf-8 -*-
"""
Conectar Google desde el Radar, sin terminal: el mismo flujo de `autorizar.py`.

El worker abre un servidor de vuelta en 127.0.0.1 (puerto libre), el Radar abre la
direccion de Google en una pestaña, la persona da permiso y Google vuelve a ese
servidor. El refresh token se guarda en el .env y en el proceso, sin reiniciar.

Mientras el proyecto de Google Cloud este en modo Prueba, Google corta el token a
los 7 dias: GOOGLE_AUTORIZADO guarda la fecha para avisar antes. Con la app en
produccion (GOOGLE_APP_PRUEBA=false) el token no vence y no hay aviso.
"""
from __future__ import annotations

import datetime as dt
import http.server
import os
import socketserver
import threading
import urllib.parse

import httpx

from app.compartido.errores import ErrorExterno
from . import autorizar, google_ads

DIAS_PRUEBA = 7
ESPERA = 900  # 15 minutos para dar permiso

_cerrojo = threading.Lock()
_estado: dict = {"estado": "INACTIVA", "mensaje": None}
_servidor: socketserver.TCPServer | None = None

PAGINA = """<!doctype html><meta charset="utf-8"><title>Radar · Google</title>
<body style="font-family:system-ui,sans-serif;max-width:520px;margin:15vh auto;padding:0 16px;color:#1f2937">
<h2>{titulo}</h2><p>{texto}</p><script>setTimeout(function(){{window.close()}},1500)</script></body>"""


def _env(clave: str) -> str:
    return os.environ.get(clave, "").strip()


def en_prueba() -> bool:
    """La app de Google Cloud sigue en modo Prueba (por defecto, si no se dice lo contrario)."""
    return _env("GOOGLE_APP_PRUEBA").lower() not in ("false", "0", "no")


def _guardar(clave: str, valor: str) -> None:
    autorizar.escribir_env(clave, valor, autorizar.ENV)
    os.environ[clave] = valor


def _apagar(s: socketserver.TCPServer) -> None:
    def hilo():
        s.shutdown()
        s.server_close()
    threading.Thread(target=hilo, daemon=True).start()


def _cerrar() -> None:
    global _servidor
    if _servidor:
        _apagar(_servidor)
        _servidor = None


def _canjear(code: str, redirect: str) -> None:
    r = httpx.post(google_ads.TOKEN_URL, data={
        "code": code, "client_id": _env("GOOGLE_ADS_CLIENT_ID"), "client_secret": _env("GOOGLE_ADS_CLIENT_SECRET"),
        "redirect_uri": redirect, "grant_type": "authorization_code"}, timeout=30)
    datos = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if not r.is_success or not datos.get("refresh_token"):
        raise ErrorExterno(f"Google no entregó el permiso ({r.status_code}): {(datos.get('error_description') or r.text)[:200]}")
    _guardar("GOOGLE_ADS_REFRESH_TOKEN", datos["refresh_token"])
    _guardar("GOOGLE_AUTORIZADO", dt.date.today().isoformat())
    google_ads._acceso.update(token=datos.get("access_token"), expira=0.0)
    # Google deja desmarcar permisos en la pantalla: avisar si falta alguno.
    dados = set((datos.get("scope") or "").split())
    faltan = [n for n, s in (("Search Console", "webmasters.readonly"), ("Google Analytics", "analytics.readonly"))
              if not any(x.endswith(s) for x in dados)]
    _estado.update(estado="LISTA", mensaje=("Conectado, pero sin permiso para " + " ni ".join(faltan)
                                            + ": vuelve a conectar y deja marcadas todas las casillas.") if faltan else None)


def iniciar() -> dict:
    """Abre el servidor de vuelta y devuelve la direccion de Google para abrir en el navegador."""
    global _servidor
    if not _env("GOOGLE_ADS_CLIENT_ID") or not _env("GOOGLE_ADS_CLIENT_SECRET"):
        raise ErrorExterno("Faltan GOOGLE_ADS_CLIENT_ID y GOOGLE_ADS_CLIENT_SECRET en 03_worker/.env.")
    with _cerrojo:
        _cerrar()
        hecho = threading.Event()

        class Manejador(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                # Solo cuenta la vuelta de Google (el navegador pide tambien favicon y otras cosas).
                if ("code" not in q and "error" not in q) or hecho.is_set():
                    self.send_response(404)
                    self.end_headers()
                    return
                hecho.set()
                try:
                    if q.get("error"):
                        raise ErrorExterno("No diste permiso en Google." if q["error"][0] == "access_denied"
                                           else f"Google respondió: {q['error'][0]}")
                    _canjear(q["code"][0], redirect)
                    titulo, texto = "Listo", "Google quedó conectado. Puedes cerrar esta pestaña y volver al Radar."
                except Exception as e:  # noqa: BLE001
                    _estado.update(estado="ERROR", mensaje=str(e))
                    titulo, texto = "No se pudo conectar", f"{e} Vuelve al Radar e inténtalo de nuevo."
                self.send_response(200)
                self.send_header("content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(PAGINA.format(titulo=titulo, texto=texto).encode("utf-8"))
                _apagar(self.server)

            def log_message(self, *a):  # silencio
                pass

        servidor = socketserver.TCPServer(("127.0.0.1", 0), Manejador)
        redirect = f"http://127.0.0.1:{servidor.server_address[1]}"
        _servidor = servidor
        threading.Thread(target=servidor.serve_forever, kwargs={"poll_interval": 0.5}, daemon=True).start()

        def vencer():
            if not hecho.wait(ESPERA) and _servidor is servidor:
                _estado.update(estado="ERROR", mensaje="Pasaron 15 minutos sin respuesta de Google. Vuelve a intentarlo.")
                with _cerrojo:
                    _cerrar()
        threading.Thread(target=vencer, daemon=True).start()
        _estado.update(estado="ESPERANDO", mensaje=None)
        return {"url": autorizar.url_autorizacion(_env("GOOGLE_ADS_CLIENT_ID"), redirect)}


def estado(comprobar: bool = False) -> dict:
    """Si hay conexion, desde cuando y hasta cuando dura (modo Prueba); `comprobar` la prueba contra Google."""
    autorizado = _env("GOOGLE_AUTORIZADO") or None
    vence = None
    if autorizado and en_prueba():
        try:
            vence = (dt.date.fromisoformat(autorizado) + dt.timedelta(days=DIAS_PRUEBA)).isoformat()
        except ValueError:
            autorizado = None
    salida = {**_estado, "configurada": bool(_env("GOOGLE_ADS_REFRESH_TOKEN")), "autorizado": autorizado, "vence": vence,
              "valida": None, "prueba": en_prueba()}
    if comprobar and salida["configurada"] and _estado["estado"] != "ESPERANDO":
        google_ads._acceso.update(token=None, expira=0.0)
        try:
            with google_ads._http() as c:
                google_ads._token_acceso(c)
            salida["valida"] = True
        except ErrorExterno as e:
            salida.update(valida=False, error=str(e))
    return salida


def elegir_propiedad(propiedad: str) -> dict:
    """Guarda GA4_PROPIEDAD (el id numerico) en el .env y en el proceso."""
    p = (propiedad or "").strip().removeprefix("properties/")
    if not p.isdigit():
        raise ErrorExterno("La propiedad de GA4 es un número (p. ej. 123456789).")
    _guardar("GA4_PROPIEDAD", p)
    return {"propiedad": p}
