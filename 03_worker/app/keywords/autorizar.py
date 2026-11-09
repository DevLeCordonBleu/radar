# -*- coding: utf-8 -*-
"""
Obtiene el refresh token de Google Ads y Search Console (el mismo sirve para los dos), una sola vez:

    cd 03_worker
    python -m app.keywords.autorizar

Antes hacen falta GOOGLE_ADS_CLIENT_ID y GOOGLE_ADS_CLIENT_SECRET en el .env
(credenciales OAuth de tipo «Aplicación de escritorio» creadas en Google Cloud,
con la API de Google Ads habilitada). Abre el navegador, tu cuenta de Google da
permiso y el token se guarda en el .env. Nada sale de tu equipo salvo hacia Google.
"""
from __future__ import annotations

import http.server
import os
import re
import socketserver
import sys
import threading
import urllib.parse
import webbrowser

import httpx

from app.compartido import envfile

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV = os.path.join(RAIZ, ".env")
# Un solo permiso para los tres: Google Ads (Keyword Planner), Search Console y Google Analytics (solo lectura).
ALCANCE = ("https://www.googleapis.com/auth/adwords https://www.googleapis.com/auth/webmasters.readonly "
           "https://www.googleapis.com/auth/analytics.readonly")


def escribir_env(clave: str, valor: str, ruta: str = ENV) -> None:
    """Pone o reemplaza `CLAVE=valor` en el .env sin tocar el resto del archivo."""
    try:
        with open(ruta, encoding="utf-8-sig") as f:
            lineas = f.read().splitlines()
    except OSError:
        lineas = []
    nueva = f"{clave}={valor}"
    for i, ln in enumerate(lineas):
        if re.match(rf"^\s*{re.escape(clave)}\s*=", ln):
            lineas[i] = nueva
            break
    else:
        lineas.append(nueva)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")


def url_autorizacion(client_id: str, redirect: str) -> str:
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": redirect, "response_type": "code", "scope": ALCANCE,
        "access_type": "offline", "prompt": "consent"})


def main() -> int:
    envfile.load(ENV)
    cid, secreto = os.environ.get("GOOGLE_ADS_CLIENT_ID", "").strip(), os.environ.get("GOOGLE_ADS_CLIENT_SECRET", "").strip()
    if not cid or not secreto:
        print("Faltan GOOGLE_ADS_CLIENT_ID y GOOGLE_ADS_CLIENT_SECRET en 03_worker/.env.\n"
              "Créalos en Google Cloud → APIs y servicios → Credenciales → ID de cliente de OAuth → «Aplicación de escritorio».")
        return 1

    recibido: dict = {}
    listo = threading.Event()

    class Manejador(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            # El navegador o una extension piden otras cosas (favicon, sondeos): solo cuenta la vuelta de Google.
            if "code" not in q and "error" not in q:
                self.send_response(404)
                self.end_headers()
                return
            if listo.is_set():
                self.send_response(204)
                self.end_headers()
                return
            recibido["code"] = (q.get("code") or [None])[0]
            recibido["error"] = (q.get("error") or [None])[0]
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h2>Listo. Ya puedes cerrar esta pestaña y volver a la terminal.</h2>".encode("utf-8"))
            listo.set()

        def log_message(self, *a):  # silencio
            pass

    with socketserver.TCPServer(("127.0.0.1", 0), Manejador) as servidor:
        redirect = f"http://127.0.0.1:{servidor.server_address[1]}"
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        url = url_autorizacion(cid, redirect)
        print("Se abrirá el navegador para que autorices el acceso a Google Ads, Search Console y Google Analytics (solo lectura).\n"
              "Si no se abre, copia esta dirección:\n\n" + url + "\n")
        webbrowser.open(url)
        if not listo.wait(timeout=900):
            print("Pasaron 15 minutos sin respuesta. Vuelve a ejecutar el comando.")
            return 1
        servidor.shutdown()

    if recibido.get("error") or not recibido.get("code"):
        print(f"Google no dio permiso: {recibido.get('error') or 'sin código'}.")
        return 1
    r = httpx.post("https://oauth2.googleapis.com/token", data={
        "code": recibido["code"], "client_id": cid, "client_secret": secreto, "redirect_uri": redirect, "grant_type": "authorization_code"}, timeout=30)
    if not r.is_success or not r.json().get("refresh_token"):
        print(f"No se obtuvo el refresh token ({r.status_code}): {r.text[:300]}\n"
              "Si ya habías autorizado antes, revoca el acceso en myaccount.google.com/permissions y repite.")
        return 1
    escribir_env("GOOGLE_ADS_REFRESH_TOKEN", r.json()["refresh_token"])
    import datetime
    escribir_env("GOOGLE_AUTORIZADO", datetime.date.today().isoformat())
    print("Listo: GOOGLE_ADS_REFRESH_TOKEN guardado en 03_worker/.env. Reinicia el worker.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
