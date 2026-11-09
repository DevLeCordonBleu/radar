# -*- coding: utf-8 -*-
"""Medicion: Meta (insights por tramos y paginas), GA4 y el resumen con IA, sin salir a internet."""
from __future__ import annotations

import json
import os
import sys

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.compartido.errores import ErrorExterno  # noqa: E402
from app.keywords import autorizar, conexion, google_ads  # noqa: E402
from app.medicion import ga4, meta, resumen  # noqa: E402

fallos = 0


def comprobar(nombre: str, ok: bool, detalle: str = ""):
    global fallos
    print(("  ok   " if ok else "  FALLA ") + nombre + ("" if ok else f"  [{detalle}]"))
    fallos += 0 if ok else 1


def lanza(f) -> str | None:
    try:
        f()
    except ErrorExterno as e:
        return str(e)
    return None


def probar_meta():
    print("Meta: insights")
    os.environ.update(META_ACCESS_TOKEN="EAAprueba", META_AD_ACCOUNT="act_1")
    pedidas = []

    def responder(req: httpx.Request) -> httpx.Response:
        pedidas.append(req)
        assert req.headers["authorization"] == "Bearer EAAprueba"
        if req.url.path.endswith("/act_1"):
            return httpx.Response(200, json={"name": "Cuenta", "currency": "USD", "account_status": 1, "timezone_name": "America/Lima"})
        q = dict(req.url.params)
        if q.get("after") == "p2":
            return httpx.Response(200, json={"data": [{"date_start": "2026-10-02", "ad_id": "2", "campaign_id": "c2", "spend": "5",
                                                       "actions": [{"action_type": "onsite_conversion.messaging_conversation_started_7d", "value": "3"}]}]})
        rango = json.loads(q["time_range"])
        fila = {"date_start": rango["since"], "campaign_id": "c1", "campaign_name": "ILCB - Lead Ads - Pastelería - 2027I", "adset_id": "s1",
                "adset_name": "Conjunto", "ad_id": "1", "ad_name": "Video chef", "objective": "OUTCOME_LEADS", "spend": "12.345",
                "impressions": "1000", "reach": "800", "frequency": "1.25", "clicks": "40", "inline_link_clicks": "30",
                "actions": [{"action_type": "lead", "value": "4"}, {"action_type": "landing_page_view", "value": "7"},
                            {"action_type": "offsite_complete_registration_add_meta_leads", "value": "4"}]}
        cuerpo = {"data": [fila]}
        if rango["since"] == "2026-10-01":
            cuerpo["paging"] = {"next": "https://graph.facebook.com/v23.0/act_1/insights?after=p2"}
        return httpx.Response(200, json=cuerpo)

    meta._http = lambda: httpx.Client(transport=httpx.MockTransport(responder))
    c = meta.cuenta()
    comprobar("la cuenta: nombre, moneda, activa", c == {"id": "act_1", "nombre": "Cuenta", "moneda": "USD", "activa": True, "zona": "America/Lima"}, str(c))
    r = meta.insights("2026-10-01", "2026-10-15")
    f = r["filas"]
    comprobar("por tramos de 10 días y siguiendo las páginas", len(pedidas) == 1 + 3 and len(f) == 3, f"{len(pedidas)} pedidas, {len(f)} filas")
    comprobar("normaliza: gasto, leads (sin contar dos veces el registro), visitas", f[0]["gasto"] == 12.35 and f[0]["leads"] == 4
              and f[0]["conversaciones"] == 0 and f[0]["visitas"] == 7 and f[0]["clics_enlace"] == 30 and f[0]["campana"].startswith("ILCB"), str(f[0]))
    comprobar("las conversaciones de WhatsApp van aparte", f[1]["conversaciones"] == 3 and f[1]["leads"] == 0, str(f[1]))
    comprobar("tramos cubren el periodo sin huecos", [(a.isoformat(), b.isoformat()) for a, b in meta.tramos(*map(meta.date.fromisoformat, ("2026-10-01", "2026-10-25")))]
              == [("2026-10-01", "2026-10-10"), ("2026-10-11", "2026-10-20"), ("2026-10-21", "2026-10-25")])
    comprobar("fechas al revés: error claro", "anterior" in (lanza(lambda: meta.insights("2026-10-05", "2026-10-01")) or ""))

    def error(codigo: int, estado: int = 400):
        meta._http = lambda: httpx.Client(transport=httpx.MockTransport(
            lambda req: httpx.Response(estado, json={"error": {"code": codigo, "message": "x"}})))
        return lanza(meta.cuenta) or ""
    comprobar("token vencido: pedir otro a Marketing", "token" in error(190, 401) and "Marketing" in error(190, 401))
    comprobar("sin permiso sobre la cuenta: lo dice", "permiso" in error(200, 403))
    meta.time.sleep = lambda s: None
    comprobar("limitado por Meta: reintenta y luego explica", "limitando" in error(17))
    os.environ["META_ACCESS_TOKEN"] = ""
    comprobar("sin token: qué falta", meta.configurado()["faltan"] == ["META_ACCESS_TOKEN"] and "META_ACCESS_TOKEN" in (lanza(meta.cuenta) or ""))


def probar_ga4():
    print("GA4")
    for k in ("GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_REFRESH_TOKEN"):
        os.environ[k] = "x"
    os.environ["GA4_PROPIEDAD"] = "properties/123"
    from app.keywords import google_ads
    google_ads._token_acceso = lambda c: "tok"
    cuerpos = []

    def responder(req: httpx.Request) -> httpx.Response:
        if "accountSummaries" in str(req.url):
            return httpx.Response(200, json={"accountSummaries": [{"displayName": "ILCB", "propertySummaries": [
                {"property": "properties/123", "displayName": "ilcb.edu.pe"}]}]})
        c = json.loads(req.content)
        cuerpos.append((str(req.url), c))
        dims = [d["name"] for d in c["dimensions"]]
        mets = [m["name"] for m in c["metrics"]]
        fila = {"dimensionValues": [{"value": "Paid Social" if d == "sessionDefaultChannelGroup" else "generate_lead" if d == "eventName" else "v"} for d in dims],
                "metricValues": [{"value": "12" if m != "engagementRate" else "0.5"} for m in mets]}
        return httpx.Response(200, json={"rows": [fila]})

    ga4._http = lambda: httpx.Client(transport=httpx.MockTransport(responder))
    comprobar("propiedad sin el prefijo", ga4.propiedad() == "123")
    p = ga4.propiedades()
    comprobar("lista las propiedades que ve la cuenta", p["ok"] and p["propiedades"][0]["nombre"] == "ilcb.edu.pe", str(p))
    r = ga4.informe("2026-10-01", "2026-10-31")
    comprobar("cinco consultas a la propiedad, con el periodo", len(cuerpos) == 5 and all("/properties/123:runReport" in u for u, _ in cuerpos)
              and cuerpos[0][1]["dateRanges"] == [{"startDate": "2026-10-01", "endDate": "2026-10-31"}])
    comprobar("filas con dimensiones y métricas como números", r["canales"] == [{"sessionDefaultChannelGroup": "Paid Social", "sessions": 12,
              "engagedSessions": 12, "keyEvents": 12, "totalUsers": 12}] and r["eventos"][0]["eventName"] == "generate_lead", str(r["canales"]))

    def error(estado: int, texto: str):
        ga4._http = lambda: httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(estado, text=texto)))
        return lanza(lambda: ga4.informe("2026-10-01", "2026-10-31")) or ""
    comprobar("API sin activar en Google Cloud: dice cuáles activar", "Google Analytics Data API" in error(403, "SERVICE_DISABLED"))
    comprobar("autorización sin Analytics: volver a conectar", "Conectar con Google" in error(403, "ACCESS_TOKEN_SCOPE_INSUFFICIENT insufficient"))
    comprobar("sin acceso a la propiedad: pedir rol Lector", "Lector" in error(403, "User does not have sufficient permissions"))
    os.environ["GA4_PROPIEDAD"] = ""
    comprobar("sin propiedad: qué falta", ga4.configurado()["faltan"] == ["GA4_PROPIEDAD"])


def probar_resumen():
    print("Resumen con IA")
    pedido = {}

    def falso(sistema, partes, esquema, **k):
        pedido.update(sistema=sistema, texto=partes[0]["text"])
        return ({"titular": "  Más leads y más baratos  ", "puntos": ["a", " ", "b", "c", "d", "e", "f"],
                 "hallazgos": [{"titulo": "Pastelería se encarece", "evidencia": "USD 3.10 frente a USD 2.20", "sugerencia": "revisar el público"},
                               {"titulo": " "}], "advertencias": []}, {"llamadas": 1, "costo_usd": 0.001})

    original = resumen.gemini.generar
    try:
        resumen.gemini.generar = falso
        r = resumen.resumir({"moneda": "USD", "kpis": {"gasto": 100}}, negocio="ILCB", rubro="Escuela de cocina")
        comprobar("manda las cifras y el negocio; limpia la respuesta", '"gasto": 100' in pedido["texto"] and "ILCB" in pedido["sistema"]
                  and "{{" not in pedido["sistema"] and r["titular"] == "Más leads y más baratos" and r["puntos"] == ["a", "b", "c", "d", "e"]
                  and len(r["hallazgos"]) == 1 and r["uso"]["llamadas"] == 1, str(r))
        comprobar("el prompt prohíbe inventar cifras y sumar leads con conversaciones", "No inventes" in pedido["sistema"] and "no los sumes" in pedido["sistema"])
        resumen.gemini.generar = lambda *a, **k: ({"titular": "", "puntos": [], "hallazgos": [], "advertencias": []}, {})
        comprobar("sin titular: error claro", "resumen" in (lanza(lambda: resumen.resumir({})) or ""))
    finally:
        resumen.gemini.generar = original


def probar_conexion():
    print("Conectar Google desde el Radar")
    import tempfile
    import threading
    import time
    import urllib.request

    dir_ = tempfile.mkdtemp()
    env_original, post_original = autorizar.ENV, conexion.httpx.post
    autorizar.ENV = os.path.join(dir_, ".env")
    with open(autorizar.ENV, "w", encoding="utf-8") as f:
        f.write("OTRA=1\nGOOGLE_ADS_REFRESH_TOKEN=viejo\n")
    os.environ.update(GOOGLE_ADS_CLIENT_ID="cid", GOOGLE_ADS_CLIENT_SECRET="secreto", GOOGLE_ADS_REFRESH_TOKEN="viejo")
    canjes = []

    def post(url, data=None, timeout=None):
        canjes.append(data)
        return httpx.Response(200, json={"refresh_token": "nuevo", "access_token": "a", "scope":
                                         "https://www.googleapis.com/auth/adwords https://www.googleapis.com/auth/webmasters.readonly"},
                              request=httpx.Request("POST", url))

    def volver(url: str, consulta: str) -> str:
        redirect = dict(x.split("=", 1) for x in url.split("?", 1)[1].split("&"))["redirect_uri"]
        from urllib.parse import unquote
        with urllib.request.urlopen(unquote(redirect) + "/?" + consulta, timeout=10) as r:
            return r.read().decode("utf-8")

    try:
        conexion.httpx.post = post
        u = conexion.iniciar()["url"]
        comprobar("da la dirección de Google con vuelta a 127.0.0.1", "accounts.google.com" in u and "127.0.0.1" in u and conexion.estado()["estado"] == "ESPERANDO")
        pagina = volver(u, "error=access_denied")
        comprobar("si no da permiso: error claro", "No diste permiso" in pagina and conexion.estado()["estado"] == "ERROR")

        u = conexion.iniciar()["url"]
        pagina = volver(u, "code=abc")
        with open(autorizar.ENV, encoding="utf-8") as f:
            env = f.read()
        e = conexion.estado()
        comprobar("canjea el código y guarda el token en el .env y en el proceso", "Listo" in pagina and canjes[-1]["code"] == "abc"
                  and "GOOGLE_ADS_REFRESH_TOKEN=nuevo" in env and "OTRA=1" in env and os.environ["GOOGLE_ADS_REFRESH_TOKEN"] == "nuevo", env)
        comprobar("anota la fecha y cuándo vence (7 días)", e["autorizado"] == time.strftime("%Y-%m-%d") and e["vence"] and e["estado"] == "LISTA", str(e))
        os.environ["GOOGLE_APP_PRUEBA"] = "false"
        comprobar("app en producción: sin fecha de vencimiento", conexion.estado()["vence"] is None and not conexion.estado()["prueba"])
        del os.environ["GOOGLE_APP_PRUEBA"]
        comprobar("avisa si se desmarcó Analytics", "Google Analytics" in (e["mensaje"] or ""), str(e))
        comprobar("la vuelta no se reutiliza", lanza_url(lambda: volver(u, "code=otro")) and len(canjes) == 1)

        comprobar("propiedad GA4: solo números", "número" in (lanza(lambda: conexion.elegir_propiedad("ilcb")) or ""))
        conexion.elegir_propiedad("properties/123456")
        with open(autorizar.ENV, encoding="utf-8") as f:
            comprobar("propiedad GA4 guardada", "GA4_PROPIEDAD=123456" in f.read() and ga4.propiedad() == "123456")
    finally:
        conexion.httpx.post = post_original
        autorizar.ENV = env_original
        conexion._cerrar()
        threading.Event().wait(0.1)


def lanza_url(f) -> bool:
    try:
        f()
    except Exception:  # noqa: BLE001
        return True
    return False


if __name__ == "__main__":
    probar_meta()
    probar_ga4()
    probar_resumen()
    probar_conexion()
    print("\nTODO OK" if not fallos else f"\n{fallos} FALLOS")
