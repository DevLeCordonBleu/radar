# -*- coding: utf-8 -*-
"""
Pruebas de KeyWords Explorer sin red ni cuenta de Google (gratis):
    python -m pruebas.test_keywords

El cliente de Google Ads y el autocompletado se prueban con un transporte HTTP
simulado que responde con el formato real de la API (enteros como texto, enums
en mayusculas, camelCase).
"""
import json
import os
import sys
import tempfile

import httpx

from app.compartido.errores import ErrorExterno
from app.keywords import analisis, autorizar, demo, geo, google_ads, servicio, sugerencias

fallos = 0


def comprobar(nombre: str, ok: bool, detalle: str = ""):
    global fallos
    print(("  ok   " if ok else "  FALLA ") + nombre + (f"  [{detalle}]" if detalle and not ok else ""))
    fallos += 0 if ok else 1


def lanza(f) -> str | None:
    try:
        f()
    except ErrorExterno as e:
        return str(e)
    return None


MESES = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]


def metricas_google(vol=1900, comp="MEDIUM", idx="48", bajo="800000", alto="2400000"):
    """keywordIdeaMetrics con el formato real, y los meses en desorden a proposito."""
    serie = [{"month": MESES[i], "year": "2026" if i < 9 else "2025", "monthlySearches": str(100 + i * 10)} for i in range(12)]
    return {"avgMonthlySearches": str(vol), "monthlySearchVolumes": list(reversed(serie)), "competition": comp,
            "competitionIndex": idx, "lowTopOfPageBidMicros": bajo, "highTopOfPageBidMicros": alto}


def pruebas_texto():
    print("intención y preguntas")
    comprobar("comprar precio = transaccional", "transaccional" in analisis.intencion("comprar laptop precio"))
    comprobar("mejores + opiniones = comercial", "comercial" in analisis.intencion("mejores cursos opiniones"))
    comprobar("cómo hacer = informacional (con tilde)", analisis.intencion("¿Cómo hacer una receta?") == ["informacional"])
    comprobar("login = navegacional", "navegacional" in analisis.intencion("campus virtual login"))
    comprobar("puede tener varias", set(analisis.intencion("mejor curso precio")) >= {"comercial", "transaccional"})
    comprobar("no confunde palabras parecidas (tope ≠ top)", "comercial" not in analisis.intencion("tope de gama"))
    comprobar("sin pistas queda vacía", analisis.intencion("zapatillas rojas") == [])
    comprobar("pregunta por inicio", analisis.es_pregunta("cómo hacer pan") and analisis.es_pregunta("qué es seo"))
    comprobar("pregunta de dos palabras", analisis.es_pregunta("por qué sube el dólar") and analisis.es_pregunta("para qué sirve el seo"))
    comprobar("no toda keyword es pregunta", not analisis.es_pregunta("curso de cocina") and not analisis.es_pregunta("cuarzo rosa"))


def pruebas_filas():
    print("filas y métricas")
    f = analisis.fila("Curso de Cocina", metricas_google(), concepto=None)
    comprobar("volumen entero desde texto", f["volumen"] == 1900)
    comprobar("serie cronológica de 12 meses (antiguo→reciente)", len(f["tendencia"]) == 12 and f["tendencia"][0] == 190 and f["tendencia"][-1] == 180, str(f["tendencia"]))
    comprobar("competencia traducida", f["competencia"] == "media" and f["competencia_idx"] == 48)
    comprobar("CPC = promedio de la puja baja y alta, en moneda", f["cpc_bajo"] == 0.8 and f["cpc_alto"] == 2.4 and f["cpc"] == 1.6, str(f))
    comprobar("cuenta palabras", f["palabras"] == 3)
    s = analisis.fila("sin datos", None)
    comprobar("sin métricas no inventa", s["volumen"] is None and s["cpc"] is None and s["competencia"] is None and s["tendencia"] == [])
    comprobar("usa averageCpc si no hay pujas", analisis.fila("x", {"averageCpcMicros": "500000"})["cpc"] == 0.5)

    filas = [analisis.fila("curso de cocina", metricas_google()), analisis.fila("cursos cocina online", metricas_google()),
             analisis.fila("cocina peruana", metricas_google()), analisis.fila("receta de pan", metricas_google())]
    analisis.marcar_tipos(filas, ["curso cocina"])
    comprobar("coincidente = contiene todas las palabras, sin importar orden ni plural", [x["tipo"] for x in filas] == ["coincidente", "coincidente", "relacionado", "relacionado"], str([x["tipo"] for x in filas]))
    t = analisis.por_terminos(filas)
    cocina = next(x for x in t if x["termino"].startswith("cocin"))
    comprobar("por término: cuenta keywords y suma volumen", cocina["keywords"] == 3 and cocina["volumen"] == 5700, str(cocina))
    comprobar("ignora palabras vacías (de)", not any(x["termino"] == "de" for x in t))
    comprobar("curso/cursos cuentan como una", sum(1 for x in t if x["termino"].startswith("curso")) == 1)

    r = analisis.construir(["curso cocina"], [
        {"text": "curso de cocina", "keywordIdeaMetrics": metricas_google(vol=5000), "keywordAnnotations": {"concepts": [{"name": "curso"}]}},
        {"text": "receta de pan", "keywordIdeaMetrics": metricas_google(vol=900)},
        {"text": "sin volumen", "keywordIdeaMetrics": {}}],
        sugerencias=["Curso de cocina", "curso de cocina gratis"], metricas_sugerencias={"curso de cocina gratis": metricas_google(vol=70)})
    ks = [x["keyword"] for x in r["filas"]]
    comprobar("ordena por volumen y deja los sin dato al final", ks == ["curso de cocina", "receta de pan", "curso de cocina gratis", "sin volumen"], str(ks))
    comprobar("marca las sugerencias (también las que ya eran ideas)", [x["sugerencia"] for x in r["filas"]] == [True, False, True, False])
    comprobar("la sugerencia nueva trae sus métricas", next(x for x in r["filas"] if x["keyword"] == "curso de cocina gratis")["volumen"] == 70)
    comprobar("concepto de Google", r["filas"][0]["concepto"] == "curso")
    comprobar("totales", r["totales"]["keywords"] == 4 and r["totales"]["volumen"] == 5970 and r["totales"]["sin_volumen"] == 1 and r["totales"]["sugerencias"] == 2, str(r["totales"]))
    comprobar("volumen agrupado se detecta", analisis.volumen_agrupado([{"volumen": v} for v in (10, 100, 100, 1000, 10, 100)]) and not analisis.volumen_agrupado([{"volumen": v} for v in (10, 130, 210, 1900, 70, 320)]))

    rs = analisis.resumen("curso de cocina", metricas_google())
    comprobar("resumen: tendencia y mes pico", rs["tendencia_pct"] == 0 and rs["mes_pico"] == "diciembre", str((rs["tendencia_pct"], rs.get("mes_pico"))))


def pruebas_demo():
    print("datos de demostración")
    a, b = demo.ideas(["curso de cocina"], None, "PE"), demo.ideas(["curso de cocina"], None, "PE")
    comprobar("determinista", json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))
    comprobar("trae la semilla y variaciones", len(a) > 40 and a[0]["text"] == "curso de cocina")
    r = analisis.construir(["curso de cocina"], a)
    comprobar("mismo formato que Google: todo se interpreta", all(x["volumen"] and len(x["tendencia"]) == 12 and x["competencia"] for x in r["filas"]))
    comprobar("hay preguntas y coincidentes y relacionadas", r["totales"]["preguntas"] > 3 and r["totales"]["coincidentes"] > 10 and r["totales"]["relacionadas"] > 3, str(r["totales"]))
    comprobar("semillas distintas dan volúmenes distintos", demo.ideas(["otra cosa"], None, "PE")[0]["keywordIdeaMetrics"]["avgMonthlySearches"] != a[0]["keywordIdeaMetrics"]["avgMonthlySearches"])
    ficha = demo.metricas(["curso de cocina"], "PE")["curso de cocina"]["avgMonthlySearches"]
    fila_ = next(x for x in a if x["text"] == "curso de cocina")["keywordIdeaMetrics"]["avgMonthlySearches"]
    comprobar("la ficha de una keyword coincide con su fila en la tabla", ficha == fila_, f"{ficha} vs {fila_}")
    comprobar("no repite la primera palabra de la semilla", not any(x["text"].startswith("curso de curso") for x in a))
    comprobar("desde una URL deduce el tema", demo.ideas([], "https://www.academia.pe/cursos", "PE")[0]["text"] == "academia")


class Simulador:
    """Transporte HTTP que imita a Google y apunta lo que recibe."""

    def __init__(self, ideas_paginas=None, error=None, error_token=None):
        self.llamadas, self.paginas, self.error, self.error_token = [], list(ideas_paginas or []), error, error_token

    def __call__(self, req: httpx.Request) -> httpx.Response:
        if "oauth2.googleapis.com" in str(req.url):
            self.llamadas.append(("token", None, dict(req.headers)))
            if self.error_token:
                return httpx.Response(400, json={"error": self.error_token})
            return httpx.Response(200, json={"access_token": "AT-1", "expires_in": 3600})
        cuerpo = json.loads(req.content) if req.content else {}
        self.llamadas.append((str(req.url), cuerpo, dict(req.headers)))
        if self.error:
            return httpx.Response(self.error[0], text=self.error[1])
        if str(req.url).endswith(":generateKeywordIdeas"):
            pagina = self.paginas.pop(0) if self.paginas else {"results": []}
            return httpx.Response(200, json=pagina)
        if str(req.url).endswith(":generateKeywordHistoricalMetrics"):
            return httpx.Response(200, json={"results": [{"text": k, "closeVariants": [k + "s"], "keywordMetrics": metricas_google(vol=300)} for k in cuerpo["keywords"]]})
        if str(req.url).endswith("/googleAds:search"):
            return httpx.Response(200, json={"results": [{"customer": {"currencyCode": "PEN"}}]})
        return httpx.Response(404, text="{}")


def con_simulador(sim: Simulador):
    google_ads._http = lambda: httpx.Client(transport=httpx.MockTransport(sim))
    google_ads._acceso.update(token=None, expira=0.0)
    google_ads._moneda.clear()


ENTORNO = {"GOOGLE_ADS_DEVELOPER_TOKEN": "DEV", "GOOGLE_ADS_CLIENT_ID": "cid", "GOOGLE_ADS_CLIENT_SECRET": "sec",
           "GOOGLE_ADS_REFRESH_TOKEN": "rt", "GOOGLE_ADS_CUSTOMER_ID": "123-456-7890", "GOOGLE_ADS_LOGIN_CUSTOMER_ID": "",
           "GOOGLE_ADS_API_VERSION": "v24"}


def pruebas_google():
    print("cliente de Google Ads (transporte simulado)")
    for k in ENTORNO:
        os.environ.pop(k, None)
    comprobar("sin credenciales dice qué falta", "GOOGLE_ADS_DEVELOPER_TOKEN" in (lanza(lambda: google_ads.ideas(["a"], None, "PE", "es")) or "")
              and not google_ads.configurado()["completo"] and "refresh_token" in google_ads.configurado()["faltan"])
    os.environ.update(ENTORNO)
    comprobar("configurado sin revelar claves", google_ads.configurado() == {"completo": True, "faltan": [], "version": "v24", "cuenta": "7890", "con_manager": False})

    sim = Simulador(ideas_paginas=[
        {"results": [{"text": "curso de cocina", "keywordIdeaMetrics": metricas_google()}], "nextPageToken": "P2"},
        {"results": [{"text": "cocina peruana", "keywordIdeaMetrics": metricas_google()}]}])
    con_simulador(sim)
    r = google_ads.ideas(["curso de cocina", "cocina"], None, "PE", "es", 1000)
    url, cuerpo, cab = next(c for c in sim.llamadas if c[0].endswith(":generateKeywordIdeas"))
    comprobar("URL con versión y cuenta sin guiones", url == "https://googleads.googleapis.com/v24/customers/1234567890:generateKeywordIdeas", url)
    comprobar("cabeceras de autenticación", cab["authorization"] == "Bearer AT-1" and cab["developer-token"] == "DEV" and "login-customer-id" not in cab)
    comprobar("cuerpo: país, idioma, red y semillas", cuerpo["geoTargetConstants"] == ["geoTargetConstants/2604"] and cuerpo["language"] == "languageConstants/1003"
              and cuerpo["keywordPlanNetwork"] == "GOOGLE_SEARCH" and cuerpo["keywordSeed"]["keywords"] == ["curso de cocina", "cocina"], str(cuerpo))
    comprobar("sigue las páginas", [x["text"] for x in r] == ["curso de cocina", "cocina peruana"] and any(c[1] and c[1].get("pageToken") == "P2" for c in sim.llamadas))
    comprobar("reutiliza el token de acceso", sum(1 for c in sim.llamadas if c[0] == "token") == 1)

    con_simulador(Simulador([{"results": []}]))
    google_ads.ideas([], "https://x.pe", "ES", "en")
    cuerpo_url = google_ads.cuerpo_ideas([], "https://x.pe", "ES", "en", 10)
    cuerpo_ambos = google_ads.cuerpo_ideas(["a"], "https://x.pe", "ES", "en", 10)
    comprobar("semilla solo URL / palabras + URL", cuerpo_url["urlSeed"] == {"url": "https://x.pe"} and cuerpo_ambos["keywordAndUrlSeed"] == {"url": "https://x.pe", "keywords": ["a"]})
    comprobar("sin semillas ni URL falla claro", "al menos una palabra" in (lanza(lambda: google_ads.cuerpo_ideas([], None, "PE", "es", 10)) or ""))
    comprobar("más de 20 semillas se rechaza", "Máximo 20" in (lanza(lambda: google_ads.ideas([str(i) for i in range(21)], None, "PE", "es")) or ""))
    comprobar("país desconocido se explica", "no soportado" in (lanza(lambda: geo.geo("ZZ")) or ""))

    os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"] = "999-888-7777"
    sim = Simulador()
    con_simulador(sim)
    m = google_ads.metricas(["Curso", "curso", "otro"] + [f"k{i}" for i in range(750)], "PE", "es")
    lotes = [c for c in sim.llamadas if c[0].endswith(":generateKeywordHistoricalMetrics")]
    comprobar("métricas: lotes de 700 y sin repetidas", len(lotes) == 2 and len(lotes[0][1]["keywords"]) == 700 and len(m) == 752, f"{len(lotes)} {len(m)}")
    comprobar("login-customer-id cuando hay cuenta administradora", lotes[0][2]["login-customer-id"] == "9998887777")
    comprobar("claves de métricas en minúscula", "curso" in m and m["curso"]["avgMonthlySearches"] == "300" and m["curso"]["closeVariants"] == ["cursos"])
    comprobar("sin país = todos los países", "geoTargetConstants" not in google_ads.metricas(["a"], None, "es") and "geoTargetConstants" not in next(c for c in sim.llamadas[::-1] if c[1] and "keywords" in c[1])[1])
    comprobar("moneda de la cuenta", google_ads.moneda() == "PEN")
    os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"] = ""

    print("errores de Google traducidos")
    def con_error(estado, texto):
        con_simulador(Simulador(error=(estado, texto)))
        return lanza(lambda: google_ads.ideas(["a"], None, "PE", "es")) or ""
    comprobar("token de prueba", "acceso de prueba" in con_error(403, json.dumps({"error": {"details": [{"errors": [{"errorCode": {"authorizationError": "DEVELOPER_TOKEN_NOT_APPROVED"}, "message": "x"}]}]}})))
    comprobar("acceso Explorador sin Keyword Planner", "acceso Básico" in con_error(403, json.dumps({"error": {"details": [{"errors": [{"errorCode": {"authorizationError": "DEVELOPER_TOKEN_NOT_APPROVED"}, "message": "This method is not allowed for use with explorer access."}]}]}})))
    comprobar("proyecto solo para cuentas de prueba", "acceso de prueba" in con_error(403, json.dumps({"error": {"details": [{"errors": [{"errorCode": {"authorizationError": "ACTION_NOT_PERMITTED"}, "message": "The Google Cloud project is only approved for use with test accounts."}]}]}})))
    comprobar("permiso de cuenta", "no tiene acceso a esa cuenta" in con_error(403, "USER_PERMISSION_DENIED"))
    comprobar("versión retirada (404)", "GOOGLE_ADS_API_VERSION" in con_error(404, "<html>Not found</html>"))
    comprobar("límite de peticiones (reintenta y explica)", "limitando" in con_error(429, "RESOURCE_EXHAUSTED"))
    comprobar("otro error conserva el mensaje de Google", "cuota rara" in con_error(400, json.dumps({"error": {"message": "cuota rara"}})))
    con_simulador(Simulador(error_token="invalid_grant"))
    comprobar("conexión vencida: reconectar desde el Radar", "Conectar con Google" in (lanza(lambda: google_ads.ideas(["a"], None, "PE", "es")) or ""))

    con_simulador(Simulador())
    c = google_ads.comprobar()
    comprobar("comprobar conecta y prueba una keyword", c["ok"] and "…7890" in c["detalle"] and "v24" in c["detalle"], str(c))
    con_simulador(Simulador(error=(403, "DEVELOPER_TOKEN_NOT_APPROVED")))
    comprobar("comprobar explica el fallo", not google_ads.comprobar()["ok"])


def pruebas_sugerencias():
    print("autocompletado")
    def handler(req):
        q = req.url.params["q"]
        return httpx.Response(200, content=json.dumps([q, [f"{q} online", "curso de cocina", "Curso de cocina gratis"]]).encode())
    sugerencias._http = lambda: httpx.Client(transport=httpx.MockTransport(handler))
    s = sugerencias.buscar(["curso de cocina"], "PE", "es")
    comprobar("junta sugerencias únicas y quita la semilla", "curso de cocina" not in [x.lower() for x in s] and "Curso de cocina gratis" in s and len(s) == len({x.lower() for x in s}), str(s[:4]))
    comprobar("consulta letras y preguntas", len(sugerencias.consultas_de("x")) == 1 + 26 + len(sugerencias.PREGUNTAS))
    sugerencias._http = lambda: httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    comprobar("si Google falla, devuelve vacío sin romper", sugerencias.buscar(["a"], "PE", "es") == [])


def pruebas_servicio():
    print("servicio y autorización")
    r = servicio.explorar(["curso de cocina"], None, "PE", "es", 500, True, demo=True)
    comprobar("explorar en demo", r["demo"] and r["totales"]["keywords"] > 40 and r["moneda"] == "USD" and r["totales"]["sugerencias"] >= 1)
    comprobar("avisa que no es volumen agrupado en la demo", r["volumen_agrupado"] is False)
    comprobar("explorar sin nada falla claro", "al menos una palabra" in (lanza(lambda: servicio.explorar([], None, "PE", "es", demo=True)) or ""))
    comprobar("explorar con país inválido falla claro", "no soportado" in (lanza(lambda: servicio.explorar(["a"], None, "ZZ", "es", demo=True)) or ""))
    rs = servicio.resumen("curso de cocina", "PE", "es", por_pais=True, demo=True)
    comprobar("resumen con volumen por país ordenado", rs["por_pais"] and [p["volumen"] for p in rs["por_pais"]] == sorted((p["volumen"] for p in rs["por_pais"]), reverse=True) and len(rs["por_pais"]) == 8)
    comprobar("refrescar una lista", [f["keyword"] for f in servicio.metricas_de_lista(["a b", "c"], "PE", "es", True)] == ["a b", "c"])
    comprobar("estado lista países e idiomas", servicio.estado()["paises"]["PE"] == "Perú" and "es" in servicio.estado()["idiomas"])

    with tempfile.TemporaryDirectory() as d:
        ruta = os.path.join(d, ".env")
        open(ruta, "w", encoding="utf-8").write("A=1\n# nota\nGOOGLE_ADS_REFRESH_TOKEN=viejo\nB=2\n")
        autorizar.escribir_env("GOOGLE_ADS_REFRESH_TOKEN", "nuevo", ruta)
        autorizar.escribir_env("OTRA", "x", ruta)
        txt = open(ruta, encoding="utf-8").read()
        comprobar("escribe el .env sin tocar lo demás", "GOOGLE_ADS_REFRESH_TOKEN=nuevo" in txt and "viejo" not in txt and "A=1" in txt and "# nota" in txt and "OTRA=x" in txt and txt.count("REFRESH") == 1, txt)
    u = autorizar.url_autorizacion("cid", "http://127.0.0.1:5555")
    comprobar("URL de autorización pide acceso offline y el alcance de Ads", "access_type=offline" in u and "auth%2Fadwords" in u and "prompt=consent" in u)


if __name__ == "__main__":
    for f in (pruebas_texto, pruebas_filas, pruebas_demo, pruebas_google, pruebas_sugerencias, pruebas_servicio):
        f()
    print("\n" + ("TODO OK" if not fallos else f"{fallos} FALLOS"))
    sys.exit(1 if fallos else 0)
