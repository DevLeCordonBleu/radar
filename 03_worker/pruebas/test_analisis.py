# -*- coding: utf-8 -*-
"""
Pruebas del motor sin red ni IA (gratis): `python -m pruebas.test_analisis`

Comprueban el calculo del informe con datos conocidos, el normalizador de
Apify, la identificacion de competidores y las reglas que corrigen al modelo.
"""
import sys

from app.analisis import competidores, ejemplo, informe, taxonomia as tx
from app.apify import cliente as apify, normalizar
from app.ia import clasificar, medios

fallos = 0


def comprobar(nombre: str, ok: bool, detalle: str = ""):
    global fallos
    print(("  ok   " if ok else "  FALLA ") + nombre + (f"  [{detalle}]" if detalle and not ok else ""))
    fallos += 0 if ok else 1


def pruebas_informe():
    print("informe")
    base = {"hook_estructura": "otro", "hook_literal": "", "oferta_tipo": "sin_oferta", "cta_tipo": "otro",
            "formato": "video", "patron_visual": [], "beneficios_libres": [], "fecha_inicio": "2026-10-01", "activo": True}
    a = [
        {**base, "ad_id": "1", "anunciante": "A", "nivel": 1, "angulos_libres": ["precio"]},
        {**base, "ad_id": "2", "anunciante": "B", "nivel": 4, "angulos_libres": ["calidad"]},
    ]
    t = [{"nombre": "Precio", "tipo": "funcional", "etiquetas": ["precio"]},
         {"nombre": "Calidad", "tipo": "emocional", "etiquetas": ["calidad"]}]
    r = informe.construir(a, t)
    por = {f["clave"]: f for f in r["angulos"]}
    # Pesos 2 y 0,75: 2/2,75 = 72,7 % y 0,75/2,75 = 27,3 %
    comprobar("el nivel pondera: directo pesa 72,7 %", por["Precio"]["pct"] == 72.7, str(por))
    comprobar("el nacional pesa 27,3 %", por["Calidad"]["pct"] == 27.3)
    comprobar("72,7 % es muy_alta", por["Precio"]["frecuencia"] == "muy_alta")
    comprobar("27,3 % es alta", por["Calidad"]["frecuencia"] == "alta")
    comprobar("avisa de muestra pequeña", r["meta"]["aviso_muestra"] is not None)
    comprobar("formato sale al 100 %", r["visuales"]["formatos"][0]["pct"] == 100.0)

    r = ejemplo.informe()
    comprobar("el ejemplo tiene anuncios", r["meta"]["anuncios"] >= 60, str(r["meta"]["anuncios"]))
    comprobar("sin aviso de muestra con 60+", r["meta"]["aviso_muestra"] is None)
    comprobar("reconoce mi marca", r["mis_anuncios"] == 4 and r["mi_marca"] == "Mi Escuela")
    comprobar("mis territorios no vacíos", len(r["mis_territorios"]) > 0)
    mi_pagina = r["mis_paginas"]
    comprobar("dice las páginas de mi marca", len(mi_pagina) == 1, str(mi_pagina))
    anuncios = ejemplo.anuncios()
    por_pagina = informe.construir(anuncios, ejemplo.TERRITORIOS, mis_marcas=["Escuela"], mis_paginas=mi_pagina, hoy=ejemplo.HOY)
    comprobar("con páginas no confunde marcas de nombre parecido", por_pagina["mis_anuncios"] == 4, str(por_pagina["mis_anuncios"]))
    por_nombre = informe.construir(anuncios, ejemplo.TERRITORIOS, mis_marcas=["Escuela"], hoy=ejemplo.HOY)
    comprobar("sin páginas se reconoce por el nombre", por_nombre["mis_anuncios"] > 4, str(por_nombre["mis_anuncios"]))
    sin_pagina = informe.construir(anuncios, ejemplo.TERRITORIOS, mis_marcas=["Mi Escuela"], mis_paginas=[], hoy=ejemplo.HOY)
    comprobar("marca sin página identificada: ningún anuncio es mío", sin_pagina["mis_anuncios"] == 0)
    comprobar("hay algo dominante", len(r["saturado"]["dominantes"]) > 0)
    comprobar("veteranos ordenados por días", [v["dias_activo"] for v in r["veteranos"]] ==
              sorted((v["dias_activo"] for v in r["veteranos"]), reverse=True) and len(r["veteranos"]) > 0)
    comprobar("determinista", ejemplo.informe() == r)
    comprobar("cada clave de hooks está traducida", all(f["clave"] in tx.HOOKS.values() for f in r["hooks"]["patrones"]))
    comprobar("beneficios agrupados por tipo", set(r["beneficios"]) == set(tx.TIPOS_TERRITORIO))
    comprobar("4 titulares", len(r["titulares"]) == 4)


def pruebas_territorios():
    print("territorios")
    ind = informe.indice_etiquetas([{"nombre": "X", "tipo": "funcional", "etiquetas": ["Salida laboral"]}])
    comprobar("normaliza acentos y mayúsculas", informe.asignar(["salida LABORAL"], ind) == (["X"], []))
    comprobar("por contención", informe.asignar(["buena salida laboral garantizada"], ind)[0] == ["X"])
    comprobar("huérfana si no encaja", informe.asignar(["otra cosa"], ind) == ([], ["otra cosa"]))
    g = informe.agrupar_sin_ia([("aprender con chefs", "emocional"), ("aprende con chefs", "emocional"),
                                ("precio accesible", "funcional")])
    comprobar("plan B agrupa las parecidas", len(g) == 2, str(g))


def pruebas_apify():
    print("apify")
    item = {"ad_archive_id": 123, "page_name": "Escuela X", "page_id": 9, "start_date": 1760000000, "is_active": True,
            "snapshot": {"display_format": "VIDEO", "body": {"text": "<b>Hola</b> mundo"},
                         "videos": [{"video_hd_url": "https://v/1.mp4", "video_preview_image_url": "https://v/1.jpg"}]}}
    a = normalizar.anuncio(item)
    comprobar("lee rutas anidadas", a and a["anunciante"] == "Escuela X" and a["video_url"] == "https://v/1.mp4")
    comprobar("limpia el HTML", a["copy"] == "Hola mundo", a["copy"])
    comprobar("fecha desde epoch", a["fecha_inicio"].startswith("2025-"), a["fecha_inicio"])
    comprobar("sin id no es anuncio", normalizar.anuncio({"page_name": "x"}) is None)
    comprobar("sin plataformas no se inventan", a["plataformas"] is None)
    # Formato real de la Biblioteca (leído el 2026-10-23).
    pr = normalizar.anuncio({**item, "publisher_platform": ["INSTAGRAM", "WHATSAPP", "FACEBOOK", "AUDIENCE_NETWORK"]})
    comprobar("plataformas en minúsculas y en orden fijo",
              pr["plataformas"] == ["facebook", "instagram", "whatsapp", "audience_network"], str(pr["plataformas"]))
    comprobar("una red nueva de Meta no se pierde",
              normalizar.anuncio({**item, "publisher_platform": ["FACEBOOK", "OCULUS"]})["plataformas"] == ["facebook", "oculus"])
    pl = normalizar.anuncio({**item, "snapshot": {"display_format": "DPA", "body": {"text": "{{product.name}}"}}})
    comprobar("catálogo detectado y texto vacío", pl["es_catalogo"] and pl["copy"] == "")
    comprobar("vacío no es fallo", normalizar.lote([{"error": "No ads found"}]) == ([], None))
    comprobar("otro error se propaga", normalizar.lote([{"error": "Rate limited"}])[1] == "Rate limited")
    try:
        normalizar.lote([{"cosa": 1}])
        comprobar("formato inesperado se detecta", False)
    except normalizar.FormatoInesperado:
        comprobar("formato inesperado se detecta", True)
    u = normalizar.unicos([{"ad_id": "1", "anunciante": "A", "nivel": 3}, {"ad_id": "1", "anunciante": "A", "nivel": 1},
                           {"ad_id": "2", "anunciante": "A", "nivel": 4}])
    comprobar("dedup y nivel heredado", len(u) == 2 and all(x["nivel"] == 1 for x in u), str(u))
    url = apify.url_biblioteca("Escuela X", "marca", "PE")
    comprobar("url de biblioteca", "country=PE" in url and "keyword_exact_phrase" in url and "active_status=active" in url)
    comprobar("url por página", "view_all_page_id=55" in apify.url_biblioteca("55", "pagina", "PE"))


def pruebas_competidores():
    print("competidores")
    ads = [{"page_id": "1", "anunciante": "Sabor Andino"}, {"page_id": "1", "anunciante": "Sabor Andino"},
           {"page_id": "2", "anunciante": "Gimnasio Sabor Andino Fit"}]
    r = competidores.resolver("Escuela Sabor Andino", ads)
    comprobar("la genérica 'escuela' no estorba", r["estado"] == "unica" and r["page_id"] == "1", str(r))
    ads2 = [{"page_id": "1", "anunciante": "Mesa Abierta Lima"}, {"page_id": "2", "anunciante": "Mesa Abierta Cusco"}]
    r = competidores.resolver("Mesa Abierta", ads2)
    comprobar("dos candidatas: pregunta", r["estado"] == "ambigua" and len(r["candidatos"]) == 2, str(r))
    comprobar("ninguna", competidores.resolver("Zzz", ads)["estado"] == "ninguna")
    ads3 = [{"page_id": "a", "anunciante": "Instituto Superior Tecnológico Privado Alta Cocina DGallia"},
            {"page_id": "b", "anunciante": "Instituto D’Gallia Piura"}, {"page_id": "c", "anunciante": "Talleres Culinarios D'Gallia"},
            {"page_id": "d", "anunciante": "Gallina Feliz"}]
    r = competidores.resolver("D'Gallia", ads3)
    ads4 = [{"page_id": "1", "anunciante": "Mesa Lima", "avatar_url": None, "imagen_url": "https://i/1.jpg", "copy": "Hola   mundo"},
            {"page_id": "1", "anunciante": "Mesa Lima", "avatar_url": "https://a/1.jpg", "imagen_url": "https://i/1.jpg"},
            {"page_id": "1", "anunciante": "Mesa Lima", "video_portada_url": "https://i/2.jpg"},
            {"page_id": "2", "anunciante": "Mesa Cusco", "imagen_url": "https://i/3.jpg"}]
    c = competidores.resolver("Mesa", ads4)["candidatos"][0]
    comprobar("candidata con foto de perfil, ejemplos sin repetir y texto", c["avatar"] == "https://a/1.jpg" and c["ejemplos"] == ["https://i/1.jpg", "https://i/2.jpg"]
              and c["texto"] == "Hola mundo" and c["muestra"] == "https://a/1.jpg", str(c))
    comprobar("marca pegada o con apóstrofo curvo cuenta (DGallia = D’Gallia)", r["estado"] == "ambigua" and {c["page_id"] for c in r["candidatos"]} == {"a", "b", "c"}, str(r))


def pruebas_ia_sin_red():
    print("reglas deterministas de la IA")
    comprobar("botón manda sobre el modelo", clasificar.cta_por_boton("Reservar ahora") == "reservar")
    comprobar("botón desconocido deja al modelo", clasificar.cta_por_boton("Xyz") is None)
    comprobar("pregunta con ¿ es pregunta_directa", clasificar.hook_corregido("¿Quieres aprender?", "beneficio_directo") == "pregunta_directa")
    comprobar("sin pregunta respeta al modelo", clasificar.hook_corregido("Aprende ya", "urgencia") == "urgencia")
    comprobar("video declarado manda", clasificar.formato_por_origen({"video_url": "x"}) == "video")
    comprobar("carrusel por origen", clasificar.formato_por_origen({"formato_origen": "CAROUSEL"}) == "carrusel")
    esquema = clasificar.esquema_clasificar()
    props = esquema["properties"]["clasificaciones"]["items"]["properties"]
    comprobar("el esquema fija las listas cerradas", props["hook_estructura"]["enum"] == list(tx.HOOKS))
    comprobar("duracion_seg es opcional", "duracion_seg" not in esquema["properties"]["clasificaciones"]["items"]["required"])
    p = clasificar.prompt_clasificar()
    comprobar("el prompt no deja huecos sin rellenar", "{HOOKS}" not in p and "pregunta_directa:" in p)
    comprobar("tipo MIME por cabecera", medios.tipo(b"\xff\xd8\xff" + b"0" * 20) == "image/jpeg")
    comprobar("contexto sin sector", "todos los anuncios como relevantes" in clasificar.contexto_sector([], []))
    ctx = clasificar.contexto_sector(["D'Gallia", "Instituto de gastronomía"], ["gastronomia", "cocina"])
    comprobar("las palabras clave no definen el sector cuando hay referencia", "NO definen el sector" in ctx and "MISMO TIPO" in ctx and "D'Gallia" in ctx, ctx)
    comprobar("sin referencia, las palabras clave sí describen el sector", "Términos del sector: gastronomia" in clasificar.contexto_sector([], ["gastronomia"]))


def pruebas_miniaturas():
    """Descarga simulada: no sale a Meta."""
    import base64
    import io

    import httpx
    from PIL import Image

    from app.fuentes import miniaturas

    print("Miniaturas")
    grande = io.BytesIO()
    Image.new("RGBA", (1600, 900), (200, 50, 50, 128)).save(grande, "PNG")
    pedidas = []

    def meta(req: httpx.Request) -> httpx.Response:
        pedidas.append(str(req.url))
        if "rota" in req.url.path:
            return httpx.Response(403)
        if "texto" in req.url.path:
            return httpx.Response(200, content=b"<html>no es imagen</html>")
        return httpx.Response(200, content=grande.getvalue())

    original = miniaturas._http
    miniaturas._http = lambda: httpx.Client(transport=httpx.MockTransport(meta))
    try:
        r = miniaturas.descargar([
            {"id": "1", "url": "https://scontent.xx.fbcdn.net/v/t39/a.png?oe=1"},
            {"id": "2", "url": "https://scontent.xx.fbcdn.net/v/t39/rota.jpg"},
            {"id": "3", "url": "https://scontent.xx.fbcdn.net/v/t39/texto.jpg"},
            {"id": "4", "url": "https://evil.example.com/fbcdn.net/x.jpg"},
            {"id": "5", "url": "http://scontent.xx.fbcdn.net/x.jpg"},
        ])
        ok = r["miniaturas"]
        comprobar("solo guarda las que bajaron bien", [m["id"] for m in ok] == ["1"] and r["fallidas"] == 4, str([m["id"] for m in ok]))
        comprobar("no pide nada fuera de los CDN de Meta ni sin https", not any("evil" in u or u.startswith("http:") for u in pedidas), str(pedidas))
        with Image.open(io.BytesIO(base64.b64decode(ok[0]["datos_b64"]))) as im:
            comprobar("la reduce a 720 px y la pasa a JPEG", im.format == "JPEG" and max(im.size) == miniaturas.LADO and ok[0]["mime"] == "image/jpeg", str(im.size))
    finally:
        miniaturas._http = original


if __name__ == "__main__":
    for f in (pruebas_informe, pruebas_territorios, pruebas_apify, pruebas_competidores, pruebas_ia_sin_red, pruebas_miniaturas):
        f()
    print("\n" + ("TODO OK" if not fallos else f"{fallos} FALLOS"))
    sys.exit(1 if fallos else 0)
