# -*- coding: utf-8 -*-
"""
Fuente gratuita de anuncios (lectura de la Biblioteca de Meta con Chrome).

    python -m pruebas.test_navegador            # sin red: extraccion y contrato
    python -m pruebas.test_navegador --en-vivo  # ademas abre Chrome y busca de verdad (gratis, ~1 min)

Las muestras imitan lo que Meta devuelve: bloques JSON dentro del HTML y
respuestas de /api/graphql con prefijo «for (;;);» y varias lineas.
"""
import json
import os
import sys
import time

from app import fuentes
from app.analisis import competidores
from app.apify import normalizar
from app.compartido.errores import ErrorExterno
from app.fuentes import navegador

fallos = 0


def comprobar(nombre: str, ok: bool, detalle: str = ""):
    global fallos
    print(("  ok   " if ok else "  FALLA ") + nombre + (f"  [{detalle}]" if detalle and not ok else ""))
    fallos += 0 if ok else 1


def anuncio(i, pagina="Escuela X", pid="1"):
    return {"ad_archive_id": str(i), "page_id": pid, "page_name": pagina, "is_active": True, "start_date": 1760000000,
            "snapshot": {"display_format": "IMAGE", "body": {"text": f"Texto {i}"}, "cta_text": "Más información",
                         "images": [{"original_image_url": f"https://x/{i}.jpg"}], "page_profile_picture_url": "https://x/p.jpg"}}


def pruebas_extraccion():
    print("extracción")
    destino = {}
    html = ('<html><script type="application/json" data-sjs>' + json.dumps({"require": [[{"__bbox": {"result": {"data": {"ad_library_main": {
        "search_results_connection": {"edges": [{"node": {"collated_results": [anuncio(1), anuncio(2)]}}]}}}}}}]]}) + '</script>'
            '<script type="application/json">{"otro": 1}</script></html>')
    comprobar("encuentra los anuncios anidados en el HTML", navegador.de_html(html, destino) == 2 and set(destino) == {"1", "2"})
    resp = "for (;;);" + json.dumps({"data": {"x": [anuncio(2), anuncio(3)]}}) + "\n" + json.dumps({"extensions": {}}) + "\n{roto"
    comprobar("respuesta graphql: prefijo, varias líneas y una rota", navegador.de_respuesta(resp, destino) == 1 and len(destino) == 3)
    comprobar("no duplica", navegador.recoger([anuncio(1), anuncio(1)], destino) == 0)
    comprobar("ignora dicts con ad_archive_id pero sin snapshot", navegador.recoger({"ad_archive_id": "9"}, destino) == 0)
    anuncios, error = normalizar.lote(list(destino.values()))
    comprobar("el normalizador los entiende igual que los de Apify", error is None and len(anuncios) == 3 and anuncios[0]["copy"].startswith("Texto")
              and anuncios[0]["cta_texto"] == "Más información" and anuncios[0]["imagen_url"].startswith("https://"), str(anuncios[:1]))


def pruebas_contrato():
    print("contrato lanzar / consultar")
    original = navegador._ejecutar

    def falso(t):
        time.sleep(0.2)
        for i in range(5):
            t.items[str(i)] = anuncio(i)
        t.estado = "listo"

    navegador._ejecutar = falso
    try:
        r = navegador.lanzar([{"valor": "x", "modo": "marca"}], "PE", 50, True)
        comprobar("lanza en segundo plano con un id propio", r["run"].startswith("nav") and r["fuente"] == "navegador")
        try:
            navegador.lanzar([{"valor": "y"}], "PE", 50, True)
            comprobar("no lanza dos a la vez", False)
        except ErrorExterno:
            comprobar("no lanza dos a la vez", True)
        primera = navegador.consultar(r["run"])
        time.sleep(0.4)
        final = navegador.consultar(r["run"])
        comprobar("mientras corre dice cuántos lleva y al final los entrega", primera["estado"] == "corriendo" and final["estado"] == "listo" and len(final["items"]) == 5)
        comprobar("un run desconocido se explica", "ya no existe" in str(_error(lambda: navegador.consultar("navnoexiste"))))
    finally:
        navegador._ejecutar = original

    def con_error(t):
        t.estado, t.error = "error", "Meta pidió iniciar sesión"
    navegador._ejecutar = con_error
    try:
        r = navegador.lanzar([{"valor": "z"}], "PE", 10, True)
        time.sleep(0.1)
        comprobar("un error de la búsqueda llega como mensaje", "iniciar sesión" in str(_error(lambda: navegador.consultar(r["run"]))))
    finally:
        navegador._ejecutar = original

    print("elección de fuente")
    previo = {k: os.environ.pop(k, None) for k in ("ANUNCIOS_FUENTE", "APIFY_TOKEN", "APIFY_TOKEN_2")}
    try:
        comprobar("sin token de Apify usa el navegador", fuentes.elegida() == "navegador")
        os.environ["APIFY_TOKEN"] = "apify_api_x"
        comprobar("con token, auto usa Apify", fuentes.elegida() == "apify")
        os.environ["ANUNCIOS_FUENTE"] = "navegador"
        comprobar("se puede forzar el navegador aunque haya token", fuentes.elegida() == "navegador")
    finally:
        for k, v in previo.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _error(f):
    try:
        f()
    except ErrorExterno as e:
        return e
    return None


def pruebas_sugerencias():
    """Lector de la respuesta de autocompletado de Meta (formato real, recortado)."""
    from app.fuentes import paginas_meta as pm
    print("sugerencias de páginas")
    cuerpo = json.dumps({"data": {"ad_library_main": {"typeahead_suggestions": {
        "keyword_results": [], "exact_phrase_results": '"dgallia"', "location_results": [],
        "page_results": [
            {"page_id": "129085860471390", "category": "Negocio local", "image_uri": "https://x/a.jpg", "likes": 193457,
             "verification": "NOT_VERIFIED", "name": "Instituto Superior Tecnológico Privado Alta Cocina DGallia",
             "ig_username": "dgallia", "ig_followers": 120000, "page_alias": "dgalliaoficial", "page_is_deleted": False},
            {"page_id": "1", "name": "Borrada", "page_is_deleted": True},
            {"page_id": "803475712853255", "name": "Instituto D’Gallia Piura", "category": "Escuela de cocina", "likes": 2559,
             "verification": "BLUE_VERIFIED"},
        ]}}}, "extensions": {"is_final": True}})
    r = pm.de_respuesta(cuerpo + "\n")
    comprobar("reconoce la respuesta y la búsqueda que contesta", r is not None and r[0] == "dgallia", str(r)[:120])
    paginas = r[1] if r else []
    comprobar("descarta páginas borradas", [p["page_id"] for p in paginas] == ["129085860471390", "803475712853255"])
    comprobar("nombre, categoría, foto, seguidores e Instagram", paginas and paginas[0]["categoria"] == "Negocio local" and paginas[0]["avatar"]
              and paginas[0]["seguidores"] == 193457 and paginas[0]["ig_usuario"] == "dgallia")
    comprobar("marca la verificada", paginas[1]["verificada"] is True and paginas[0]["verificada"] is False)
    comprobar("ignora otras respuestas de graphql", pm.de_respuesta('{"data": {"ad_library_main": {"search_results_connection": {}}}}') is None)
    comprobar("menos de 3 letras no consulta a Meta", pm.sugerir("dg") == [])

    # Mientras se atiende una consulta se sigue escribiendo: solo se atiende la última.
    from concurrent.futures import Future
    atendidas = []

    class Falso(pm._Buscador):
        def _consultar(self, texto, pais):
            atendidas.append(texto)
            time.sleep(0.3)
            return [{"page_id": "1", "nombre": texto}]

    b = Falso()
    futuros = [Future() for _ in range(4)]
    b.pendientes.put(("afro", "PE", futuros[0]))
    b.start()
    time.sleep(0.1)
    for texto, f in zip(("afro l", "afro la", "afro latina"), futuros[1:]):
        b.pendientes.put((texto, "PE", f))
    ultima = futuros[-1].result(timeout=5)
    comprobar("descarta las consultas que quedaron viejas", atendidas == ["afro", "afro latina"] and ultima[0]["nombre"] == "afro latina",
              str(atendidas))
    comprobar("las descartadas quedan canceladas", all(f.cancelled() for f in futuros[1:3]))


def prueba_en_vivo():
    print("en vivo: Biblioteca de Meta con Chrome (gratis)")
    r = navegador.lanzar([{"valor": "D'Gallia", "modo": "marca"}, {"valor": "gastronomia", "modo": "palabras"}], "PE", 40, True)
    inicio = time.time()
    while True:
        c = navegador.consultar(r["run"])
        if c["estado"] == "listo":
            break
        if time.time() - inicio > 300:
            comprobar("termina en menos de 5 minutos", False)
            return
        time.sleep(3)
    anuncios, error = normalizar.lote(c["items"])
    comprobar(f"trae anuncios reales ({len(anuncios)} en {time.time() - inicio:.0f} s)", error is None and len(anuncios) >= 10, str(error))
    con_texto = sum(1 for a in anuncios if a["copy"])
    comprobar("con texto, anunciante y fecha", con_texto >= len(anuncios) * 0.6 and all(a["anunciante"] and a["fecha_inicio"] for a in anuncios), f"{con_texto}/{len(anuncios)}")
    comprobar("respeta el máximo", len(anuncios) <= 40)
    r = competidores.resolver("D'Gallia", anuncios)
    comprobar("identifica la(s) página(s) de D'Gallia", r["estado"] in ("unica", "ambigua"), str(r)[:200])
    print("   ", r["estado"], [c["nombre"] for c in r.get("candidatos", [])] or r.get("anunciante"))


if __name__ == "__main__":
    pruebas_extraccion()
    pruebas_contrato()
    pruebas_sugerencias()
    if "--en-vivo" in sys.argv:
        prueba_en_vivo()
    print("\n" + ("TODO OK" if not fallos else f"{fallos} FALLOS"))
    sys.exit(1 if fallos else 0)
