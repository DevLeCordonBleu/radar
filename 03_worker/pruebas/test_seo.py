# -*- coding: utf-8 -*-
"""
Pruebas del Plan SEO sin red externa ni IA (gratis):
    python -m pruebas.test_seo

El rastreo se prueba contra un sitio falso servido en 127.0.0.1 (robots.txt,
indice de sitemaps, taxonomias, paginas con ruido de plantilla). Gemini se
sustituye por respuestas preparadas que traen errores a proposito: URLs, keywords
y citas inventadas que el codigo debe descartar.
"""
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.seo import ia, rastreo

fallos = 0


def comprobar(nombre: str, ok: bool, detalle: str = ""):
    global fallos
    print(("  ok   " if ok else "  FALLA ") + nombre + (f"  [{detalle}]" if detalle and not ok else ""))
    fallos += 0 if ok else 1


# ── Sitio falso ───────────────────────────────────────────────────────────

ARTICULO = """<!doctype html><html lang="es-PE"><head>
<title>Qué es la mise en place - Escuela</title>
<meta content="Guía de la mise en place en cocina profesional" name="description">
<link rel="canonical" href="{base}/que-es-mise-en-place/">
</head><body>
<header class="sitio"><nav><a href="/">Inicio</a></nav><h1>Menú</h1></header>
<div class="popup-buscar"><h1>BUSCAR</h1></div>
<main><article><header class="entry-header"><h1>Qué es la <strong>mise en place</strong></h1></header>
<p>La mise en place es&nbsp;preparar todo antes de cocinar.</p>
<h2>Origen del término</h2><p>Viene del francés.</p>
<h2>Cómo organizarla</h2><p>Por estaciones.</p>
<script>var h2 = "<h2>no</h2>";</script>
</article>
<div class="related-posts"><h2>Otra noticia que no es de esta página</h2></div>
</main>
<aside><h2>Categorías</h2></aside>
<footer><h2>Contacto</h2></footer>
</body></html>"""

SIN_H2 = """<html><head><title>Carrera de cocina</title></head><body><main><h1>Carrera de cocina</h1><p>Tres años.</p></main></body></html>"""

INDICE = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>{base}/post-sitemap.xml</loc></sitemap>
<sitemap><loc>{base}/category-sitemap.xml</loc></sitemap>
<sitemap><loc>{base}/wp-sitemap-taxonomies-course_language-1.xml</loc></sitemap>
</sitemapindex>"""

POSTS = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>{base}/que-es-mise-en-place/</loc><lastmod>2026-09-01</lastmod></url>
<url><loc>{base}/carrera-de-cocina/?utm_source=x#arriba</loc></url>
<url><loc>{base}/cart/</loc></url>
<url><loc>{base}/privado/secreto/</loc></url>
<url><loc>{base}/folleto.pdf</loc></url>
<url><loc>{base}/no-existe/</loc></url>
</urlset>"""

PORTADA_B = """<html><body><a href="/curso-de-barista/">Barista</a><a href="https://otro.example/x">Fuera</a>
<a href="/mi-cuenta/">Cuenta</a><a href="#top">Arriba</a></body></html>"""


class Sitio(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _enviar(self, codigo: int, cuerpo: str, tipo: str = "text/html; charset=UTF-8"):
        datos = cuerpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self):
        h = self.headers.get("Host", "")
        b = f"http://{h}"
        segundo = h.startswith("localhost")  # el «sitio B»: sin sitemap
        ruta = self.path.split("?")[0]
        if ruta == "/robots.txt":
            if segundo:
                return self._enviar(200, "User-agent: *\nDisallow:\n", "text/plain")
            return self._enviar(200, f"User-agent: *\nDisallow: /privado/\n\nSitemap: {b}/sitemap_index.xml\n", "text/plain")
        if segundo:
            return self._enviar(200, PORTADA_B) if ruta == "/" else self._enviar(404, "no")
        rutas = {
            "/sitemap_index.xml": (INDICE, "text/xml"),
            "/post-sitemap.xml": (POSTS, "application/xml"),
            "/que-es-mise-en-place/": (ARTICULO, "text/html; charset=UTF-8"),
            "/carrera-de-cocina/": (SIN_H2, "text/html"),
        }
        if ruta in rutas:
            cuerpo, tipo = rutas[ruta]
            return self._enviar(200, cuerpo.format(base=b), tipo)
        if ruta == "/category-sitemap.xml":
            raise AssertionError("no debía pedirse el sitemap de categorías")
        if ruta == "/folleto.pdf":
            return self._enviar(200, "%PDF", "application/pdf")
        return self._enviar(404, "no")


def probar_rastreo():
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Sitio)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    puerto = servidor.server_address[1]
    a, b = f"http://127.0.0.1:{puerto}", f"http://localhost:{puerto}"
    rastreo.PAUSA_MINIMA_S = 0
    try:
        print("Descubrir")
        d = rastreo.descubrir([a])
        urls = {u["url"]: u for u in d["urls"]}
        comprobar("lee el índice desde robots.txt y entra al sitemap de entradas", f"{a}/que-es-mise-en-place/" in urls, str(list(urls)))
        comprobar("guarda lastmod", urls.get(f"{a}/que-es-mise-en-place/", {}).get("lastmod") == "2026-09-01")
        comprobar("quita utm y fragmento", f"{a}/carrera-de-cocina/" in urls, str(list(urls)))
        comprobar("carrito excluido con motivo", "servicio" in (urls.get(f"{a}/cart/", {}).get("excluida") or ""))
        comprobar("pdf excluido", bool(urls.get(f"{a}/folleto.pdf", {}).get("excluida")))
        excl = [s for s in d["sitemaps"] if s["excluido"]]
        comprobar("sitemaps de taxonomías no se descargan", len(excl) == 2, str(d["sitemaps"]))
        comprobar("el índice queda registrado como índice", any(s["tipo"] == "indice" for s in d["sitemaps"]))

        print("Sitio sin sitemap")
        d2 = rastreo.descubrir([b])
        u2 = [u["url"] for u in d2["urls"]]
        comprobar("usa los enlaces de la portada", f"{b}/curso-de-barista/" in u2, str(u2))
        comprobar("no sale del dominio", not any("otro.example" in u for u in u2))
        comprobar("avisa de que no hay sitemap", any("sin sitemap" in x for x in d2["avisos"]), str(d2["avisos"]))
        comprobar("mi cuenta excluida", any(u["excluida"] for u in d2["urls"] if u["url"].endswith("/mi-cuenta/")))

        print("Extraer páginas")
        r = rastreo.paginas([f"{a}/que-es-mise-en-place/", f"{a}/carrera-de-cocina/", f"{a}/privado/secreto/",
                             f"{a}/folleto.pdf", f"{a}/no-existe/"], pausa_s=0)
        p = {x["url"]: x for x in r["paginas"]}
        art = p[f"{a}/que-es-mise-en-place/"]
        dd = art["datos"] or {}
        comprobar("artículo OK", art["estado"] == "OK", str(art))
        comprobar("title", dd.get("title") == "Qué es la mise en place - Escuela", str(dd.get("title")))
        comprobar("meta description aunque content vaya antes de name", dd.get("meta_description") == "Guía de la mise en place en cocina profesional")
        comprobar("H1 del contenido, no «BUSCAR» ni el de la cabecera del sitio", dd.get("h1") == "Qué es la mise en place", str(dd.get("h1")))
        comprobar("H2 sin aside, footer, relacionadas ni scripts", dd.get("h2") == ["Origen del término", "Cómo organizarla"], str(dd.get("h2")))
        comprobar("entidades HTML limpias", "\xa0" not in dd.get("extracto", "") and "es preparar" in dd.get("extracto", ""), dd.get("extracto", "")[:80])
        comprobar("canonical e idioma", dd.get("canonical", "").endswith("/que-es-mise-en-place/") and dd.get("lang") == "es-PE")
        comprobar("hash estable", dd.get("hash") == rastreo.extraer_html(ARTICULO.format(base=a))["hash"])
        fp = rastreo.fecha_publicacion
        comprobar("fecha de publicación: meta de WordPress, JSON-LD o ninguna",
                  fp('<meta property="article:published_time" content="2018-05-02T10:00:00+00:00" />') == "2018-05-02"
                  and fp('<meta content="2019-03-01" property="article:published_time">') == "2019-03-01"
                  and fp('{"@type":"Article","datePublished":"2021-01-09T08:00:00-05:00"}') == "2021-01-09"
                  and fp('<p>Publicado: ayer</p>') is None and fp('"datePublished": "pronto"') is None)
        sin = p[f"{a}/carrera-de-cocina/"]["datos"]
        comprobar("sin meta ni H2: vacíos, no inventados", sin["meta_description"] is None and sin["h2"] == [])
        comprobar("robots.txt prohíbe /privado/", p[f"{a}/privado/secreto/"]["estado"] == "BLOQUEADA")
        comprobar("pdf = NO_HTML", p[f"{a}/folleto.pdf"]["estado"] == "NO_HTML")
        comprobar("404 = HTTP_ERROR", p[f"{a}/no-existe/"]["estado"] == "HTTP_ERROR" and p[f"{a}/no-existe/"]["http"] == 404)
        comprobar("no frena sin 403/429", r["frenar"] is False)
    finally:
        servidor.shutdown()


# ── IA con respuestas preparadas ──────────────────────────────────────────

def probar_ia():
    original = ia.gemini.generar
    uso = {"tokens_entrada": 10, "tokens_salida": 5, "llamadas": 1, "modelo": "x", "costo_usd": 0.0}
    try:
        print("Temas")
        ia.gemini.generar = lambda *a, **k: ({"paginas": [
            {"url": "https://a.pe/1", "tipo_pagina": "ARTICULO", "tema": "mise en place", "consultas": ["Qué es la mise en place", "qué es la mise en place", "x"],
             "relevancia": 140, "confianza": "ALTA", "evidencia": ["Origen del término", "frase que no está en la página"]},
            {"url": "https://inventada.pe/", "tipo_pagina": "OTRA", "tema": "x", "consultas": [], "relevancia": 1, "confianza": "BAJA", "evidencia": []},
        ]}, uso)
        r = ia.temas([{"url": "https://a.pe/1", "title": "Mise en place", "h1": "Qué es", "h2": ["Origen del término"], "extracto": "texto"}])
        comprobar("descarta páginas que no se enviaron", [t["url"] for t in r["temas"]] == ["https://a.pe/1"])
        t = r["temas"][0]
        comprobar("consultas sin duplicados ni demasiado cortas", t["consultas"] == ["qué es la mise en place"], str(t["consultas"]))
        comprobar("relevancia acotada a 100", t["relevancia"] == 100)
        comprobar("solo citas que están en la página", t["evidencia"] == ["Origen del término"], str(t["evidencia"]))

        print("Agrupar")
        ia.gemini.generar = lambda *a, **k: ({"keywords": [
            {"keyword": "Que es la mise en place", "intencion": "INFORMATIONAL", "grupo": "Mise en place", "canonica": "qué es la mise en place", "relevancia": 90, "motivo": "aprender"},
            {"keyword": "keyword inventada", "intencion": "INFORMATIONAL", "grupo": "x", "canonica": "x", "relevancia": 50, "motivo": ""},
        ]}, uso)
        r = ia.agrupar(["qué es la mise en place", "precio curso"])
        comprobar("no acepta keywords que no estaban", [k["keyword"] for k in r["keywords"]] == ["qué es la mise en place"], str(r["keywords"]))
        comprobar("conserva la grafía original", r["keywords"][0]["keyword"] == "qué es la mise en place")
        comprobar("grupo en minúsculas", r["keywords"][0]["grupo"] == "mise en place")

        print("Cobertura")
        ia.gemini.generar = lambda *a, **k: ({"cobertura": [
            {"grupo": "mise en place", "estado": "YA_CUBIERTA", "url": "https://ilcb.pe/no-existe/", "motivo": "x"},
            {"grupo": "masa madre", "estado": "PARCIAL", "url": "https://ilcb.pe/pan/", "motivo": "toca el tema"},
            {"grupo": "grupo inventado", "estado": "SIN_COBERTURA", "url": "", "motivo": ""},
        ]}, uso)
        r = ia.cobertura([{"grupo": "mise en place", "canonica": "qué es la mise en place", "keywords": []},
                          {"grupo": "masa madre", "canonica": "cómo hacer masa madre", "keywords": []}],
                         [{"url": "https://ilcb.pe/pan/", "title": "Pan", "h1": "Pan"}])
        c = {x["grupo"]: x for x in r["cobertura"]}
        comprobar("URL inventada: se quita y la cobertura pasa a INCIERTO", c["mise en place"]["url"] is None and c["mise en place"]["estado"] == "INCIERTO")
        comprobar("URL real del inventario se conserva", c["masa madre"]["url"] == "https://ilcb.pe/pan/" and c["masa madre"]["estado"] == "PARCIAL")
        comprobar("no acepta grupos que no se enviaron", "grupo inventado" not in c)
    finally:
        ia.gemini.generar = original


def probar_articulo():
    from app.seo import markdown

    print("Markdown a HTML")
    h = markdown.a_html("# Título dentro\n\nUn párrafo\nque sigue con **negrita** y *cursiva*.\n\n## Sección\n- uno\n- dos\n  que sigue\n\n1. paso\n2. otro\n\n"
                        "> una cita\n\nVer [la guía](https://ilcb.edu.pe/guia/) y [COMPLETAR: precio del curso].\n\n<script>alert(1)</script>")
    comprobar("un # dentro del contenido baja a h2 (el título va aparte)", h.startswith("<h2>Título dentro</h2>"), h)
    comprobar("párrafo con líneas unidas, negrita y cursiva", "<p>Un párrafo que sigue con <strong>negrita</strong> y <em>cursiva</em>.</p>" in h, h)
    comprobar("listas con continuación de línea", "<ul><li>uno</li><li>dos que sigue</li></ul>" in h and "<ol><li>paso</li><li>otro</li></ol>" in h, h)
    comprobar("cita", "<blockquote><p>una cita</p></blockquote>" in h, h)
    comprobar("enlace y pendiente resaltado", '<a href="https://ilcb.edu.pe/guia/">la guía</a>' in h and '<mark class="completar">[COMPLETAR: precio del curso]</mark>' in h, h)
    comprobar("el HTML crudo se escapa", "<script>" not in h and "&lt;script&gt;" in h, h)
    comprobar("un enlace javascript: no es enlace", "<a" not in markdown.a_html("[x](javascript:alert(1))"))
    md, quitadas = markdown.solo_enlaces_permitidos("[a](https://ilcb.edu.pe/a/) y [b](https://otro.com/b/)", {"https://ilcb.edu.pe/a/"})
    comprobar("enlace a una URL que no estaba: queda su texto", md == "[a](https://ilcb.edu.pe/a/) y b" and quitadas == ["https://otro.com/b/"], md)

    print("Artículo")
    original = ia.gemini.generar
    uso = {"tokens_entrada": 1, "tokens_salida": 1, "llamadas": 1, "modelo": "x", "costo_usd": 0}
    vistos = {}
    try:
        def falso(sistema, partes, esquema, **k):
            vistos.update(sistema=sistema, texto=partes[0]["text"], temperatura=k.get("temperatura"))
            return ({"titulo": " Qué es la mise en place ", "slug": "Qué es la Mise en Place!", "meta_description": "Guía.",
                     "contenido": "## Qué es\nTexto con [enlace propio](https://ilcb.edu.pe/pan/) y [inventado](https://ilcb.edu.pe/no-existe/).\n\n"
                                  "Dura [COMPLETAR: duración del curso].",
                     "pendientes": ["Verificar la duración"]}, uso)
        ia.gemini.generar = falso
        r = ia.articulo("qué es la mise en place", ["mise en place significado"], [{"url": "https://dgallia.edu.pe/x/", "title": "X"}],
                        [{"url": "https://ilcb.edu.pe/pan/", "title": "Pan"}], negocio="Academia Ritmo", rubro="Academia de baile")
        comprobar("el prompt lleva el negocio y el rubro configurados", "Academia Ritmo" in vistos["sistema"] and "Academia de baile" in vistos["sistema"]
                  and "{{" not in vistos["sistema"])
        comprobar("redacta con algo de temperatura", vistos["temperatura"] == 0.6)
        comprobar("quita el enlace a una página que no existe", "[enlace propio](https://ilcb.edu.pe/pan/)" in r["contenido"]
                  and "no-existe" not in r["contenido"] and r["enlaces_quitados"] == ["https://ilcb.edu.pe/no-existe/"], r["contenido"])
        comprobar("slug limpio", r["slug"] == "que-es-la-mise-en-place", r["slug"])
        comprobar("los [COMPLETAR] del texto son pendientes", r["pendientes"] == ["Verificar la duración", "[COMPLETAR: duración del curso]"], str(r["pendientes"]))

        ia.gemini.generar = lambda *a, **k: ({"descripcion": "Academia de baile", "palabras": ["Bailé", "salsa", "dos palabras", "salsa", "x"]}, uso)
        r = ia.rubro("Academia Ritmo", [{"title": "Clases de salsa"}])
        comprobar("rubro sugerido: palabras normalizadas, sin repetidas ni frases", r["palabras"] == ["baile", "salsa"], str(r["palabras"]))
        ia.gemini.generar = lambda s, *a, **k: (vistos.update(sistema=s) or {"paginas": []}, uso)
        ia.temas([{"url": "https://x.pe/"}])
        comprobar("sin rubro configurado se usa el de siempre", "Le Cordon Bleu" in vistos["sistema"] and "cocina peruana" in vistos["sistema"])
    finally:
        ia.gemini.generar = original


def probar_wordpress():
    import json
    import os

    import httpx

    from app.compartido.errores import ErrorExterno
    from app.seo import wordpress

    print("WordPress")
    pedidas = []

    def responder(req: httpx.Request) -> httpx.Response:
        pedidas.append(req)
        if req.headers.get("authorization") != "Basic " + __import__("base64").b64encode(b"editor:abcd efgh".replace(b" ", b"")).decode():
            return httpx.Response(401, json={"code": "incorrect_password", "message": "x"})
        if req.url.path.endswith("/users/me"):
            return httpx.Response(200, json={"name": "Editora", "capabilities": {"edit_posts": True, "publish_posts": False}})
        if req.url.path.endswith("/posts/999"):
            return httpx.Response(404, json={"code": "rest_post_invalid_id", "message": "ID no válido"})
        cuerpo = json.loads(req.content)
        return httpx.Response(201, json={"id": 42, "status": cuerpo.get("status", "publish"), "link": "https://blog.pe/?p=42"})

    antes = {k: os.environ.get(k) for k in wordpress.CLAVES.values()}
    original = wordpress._http
    try:
        for k in wordpress.CLAVES.values():
            os.environ.pop(k, None)
        try:
            wordpress.enviar("t", "t", "<p>x</p>", "", False)
            comprobar("sin configurar avisa qué falta", False)
        except ErrorExterno as e:
            comprobar("sin configurar avisa qué falta", "WP_URL" in str(e) and "WP_CLAVE_APLICACION" in str(e), str(e))
        os.environ.update(WP_URL="http://blog.pe/", WP_USUARIO="editor", WP_CLAVE_APLICACION="abcd efgh")
        try:
            wordpress.comprobar()
            comprobar("rechaza http fuera de localhost", False)
        except ErrorExterno as e:
            comprobar("rechaza http fuera de localhost", "https" in str(e), str(e))
        os.environ["WP_URL"] = "https://blog.pe/"
        wordpress._http = lambda: httpx.Client(transport=httpx.MockTransport(responder))
        c = wordpress.comprobar()
        comprobar("comprueba usuario y permisos", c["usuario"] == "Editora" and c["puede_crear"] and not c["puede_publicar"], str(c))
        r = wordpress.enviar("Título", "titulo", "<p>x</p>", "Resumen", False)
        cuerpo = json.loads(pedidas[-1].content)
        comprobar("una entrada nueva llega como borrador", str(pedidas[-1].url) == "https://blog.pe/wp-json/wp/v2/posts" and cuerpo["status"] == "draft"
                  and cuerpo["excerpt"] == "Resumen" and r["id"] == 42 and r["editar"].endswith("post.php?post=42&action=edit"), str(cuerpo))
        wordpress.enviar("Título", "titulo", "<p>y</p>", "", False, 42)
        comprobar("actualizar sin publicar no toca su estado", pedidas[-1].url.path.endswith("/posts/42") and "status" not in json.loads(pedidas[-1].content))
        wordpress.enviar("Título", "titulo", "<p>y</p>", "", True, 42)
        comprobar("publicar manda status publish", json.loads(pedidas[-1].content)["status"] == "publish")
        try:
            wordpress.enviar("Título", "titulo", "<p>y</p>", "", False, 999)
            comprobar("entrada borrada en WordPress: lo explica", False)
        except ErrorExterno as e:
            comprobar("entrada borrada en WordPress: lo explica", "ya no existe" in str(e), str(e))
        os.environ["WP_CLAVE_APLICACION"] = "mala"
        try:
            wordpress.comprobar()
            comprobar("clave incorrecta: mensaje claro", False)
        except ErrorExterno as e:
            comprobar("clave incorrecta: mensaje claro", "no acepta el usuario" in str(e) and "mala" not in str(e), str(e))
    finally:
        wordpress._http = original
        for k, v in antes.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


JPG = b"\xff\xd8\xff\xe0" + b"0" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def probar_imagenes():
    """Pixabay, Pexels, Gemini y la subida a WordPress, todo simulado (no gasta nada)."""
    import base64
    import json
    import os

    import httpx

    from app.compartido.errores import ErrorExterno
    from app.seo import imagenes, wordpress

    print("Imagen destacada")
    foto = {"id": 7, "width": 4000, "height": 3000, "photographer": "Ana", "photographer_url": "https://www.pexels.com/@ana",
            "url": "https://www.pexels.com/photo/pan-7/", "alt": "Pan",
            "src": {"medium": "https://images.pexels.com/7-m.jpg", "landscape": "https://images.pexels.com/7-l.jpg"}}
    pedidas = []

    def pexels(req: httpx.Request) -> httpx.Response:
        pedidas.append(req)
        if req.url.host == "images.pexels.com":
            return httpx.Response(200, content=JPG)
        if req.headers.get("authorization") != "clave-pexels":
            return httpx.Response(401)
        if req.url.path == "/v1/search":
            return httpx.Response(200, json={"photos": [foto], "total_results": 1, "next_page": None})
        if req.url.path == "/v1/photos/7":
            return httpx.Response(200, json=foto)
        if req.url.path == "/v1/photos/8":
            return httpx.Response(200, json={**foto, "id": 8, "src": {"landscape": "https://otro.sitio/x.jpg"}})
        return httpx.Response(404)

    antes = {k: os.environ.get(k) for k in ("PIXABAY_API_KEY", "PEXELS_API_KEY", "GEMINI_MODELO_IMAGEN", "WP_DESTACADA_EN_TEXTO",
                                            *wordpress.CLAVES.values())}
    os.environ.pop("WP_DESTACADA_EN_TEXTO", None)
    originales = (imagenes._http, wordpress._http, imagenes.gemini._una_peticion)
    try:
        os.environ.pop("PEXELS_API_KEY", None)
        os.environ.pop("PIXABAY_API_KEY", None)
        imagenes._cache.clear()
        try:
            imagenes.buscar("pan")
            comprobar("sin clave del banco de fotos lo explica", False)
        except ErrorExterno as e:
            comprobar("sin clave del banco de fotos lo explica", "PIXABAY_API_KEY" in str(e) and imagenes.estado()["fotos"] is None, str(e))

        # Pixabay (el banco por defecto).
        hit = {"id": 5, "imageWidth": 5000, "imageHeight": 3000, "user": "Luis", "user_id": 12, "pageURL": "https://pixabay.com/photos/pan-5/",
               "tags": "pan, horno", "webformatURL": "https://pixabay.com/get/5_640.jpg", "largeImageURL": "https://pixabay.com/get/5_1280.jpg"}

        def pixabay(req: httpx.Request) -> httpx.Response:
            pedidas.append(req)
            if req.url.path.startswith("/get/"):
                return httpx.Response(200, content=JPG)
            if req.url.params.get("key") != "clave-pixabay":
                return httpx.Response(400, text="[ERROR 400] Invalid or missing API key")
            if req.url.params.get("id") == "6":
                return httpx.Response(200, json={"hits": [{**hit, "id": 6, "largeImageURL": "https://otro.sitio/6.jpg"}]})
            if req.url.params.get("id"):
                return httpx.Response(200, json={"hits": [hit]})
            return httpx.Response(200, json={"totalHits": 40, "hits": [hit]})

        os.environ["PIXABAY_API_KEY"] = "clave-pixabay"
        imagenes._http = lambda: httpx.Client(transport=httpx.MockTransport(pixabay))
        r = imagenes.buscar("pan de masa madre")
        p = pedidas[-1].url.params
        comprobar("Pixabay: busca fotos horizontales en español", r["fuente"] == "PIXABAY" and r["fotos"][0]["autor"] == "Luis"
                  and r["fotos"][0]["autor_url"] == "https://pixabay.com/users/Luis-12/" and r["hay_mas"]
                  and p["orientation"] == "horizontal" and p["lang"] == "es" and p["image_type"] == "photo", str(r))
        n = len(pedidas)
        imagenes.buscar("Pan de masa madre ")
        comprobar("Pixabay: la misma búsqueda sale de la caché (24 h)", len(pedidas) == n)
        d = imagenes.descargar(5)
        comprobar("Pixabay: descarga la foto grande con su crédito", d["fuente"] == "PIXABAY" and base64.b64decode(d["datos_b64"]) == JPG
                  and pedidas[-1].url.path == "/get/5_1280.jpg" and d["pagina_url"].endswith("pan-5/"),
                  str({k: v for k, v in d.items() if k != "datos_b64"}))
        try:
            imagenes.descargar(6)
            comprobar("Pixabay: no baja imágenes de otro dominio", False)
        except ErrorExterno as e:
            comprobar("Pixabay: no baja imágenes de otro dominio", "inesperada" in str(e), str(e))
        os.environ["PIXABAY_API_KEY"] = "mala"
        imagenes._cache.clear()
        try:
            imagenes.buscar("pan")
            comprobar("Pixabay: clave mala, mensaje sin la clave", False)
        except ErrorExterno as e:
            comprobar("Pixabay: clave mala, mensaje sin la clave", "PIXABAY_API_KEY" in str(e) and "mala" not in str(e), str(e))

        # Pexels: solo si no hay clave de Pixabay.
        os.environ.pop("PIXABAY_API_KEY", None)
        os.environ["PEXELS_API_KEY"] = "clave-pexels"
        imagenes._http = lambda: httpx.Client(transport=httpx.MockTransport(pexels))
        r = imagenes.buscar("pan de masa madre")
        comprobar("Pexels: busca fotos horizontales", r["fuente"] == "PEXELS" and r["fotos"][0]["autor"] == "Ana" and r["fotos"][0]["miniatura"].endswith("7-m.jpg")
                  and pedidas[-1].url.params["orientation"] == "landscape" and not r["hay_mas"], str(r))
        d = imagenes.descargar(7)
        comprobar("Pexels: descarga la foto 1200x627 con su crédito", d["fuente"] == "PEXELS" and d["mime"] == "image/jpeg" and base64.b64decode(d["datos_b64"]) == JPG
                  and d["autor"] == "Ana" and d["pagina_url"].endswith("pan-7/"), str({k: v for k, v in d.items() if k != "datos_b64"}))
        try:
            imagenes.descargar(8)
            comprobar("Pexels: no baja imágenes fuera de images.pexels.com", False)
        except ErrorExterno as e:
            comprobar("Pexels: no baja imágenes fuera de images.pexels.com", "inesperada" in str(e), str(e))

        # Gemini: sin facturacion (limite 0) y con imagen.
        cuerpos = []
        imagenes.gemini._una_peticion = lambda m, c: (cuerpos.append((m, c)) or (
            429, '{"error":{"status":"RESOURCE_EXHAUSTED","details":[{"quotaId":"GenerateRequestsPerDayPerProjectPerModel-FreeTier","quotaValue":"0"}]}}'))
        try:
            imagenes.generar("pan artesanal", negocio="ILCB", rubro="cocina")
            comprobar("sin facturación: explica que no hay plan gratuito", False)
        except ErrorExterno as e:
            comprobar("sin facturación: explica que no hay plan gratuito", "plan gratuito" in str(e) and "banco gratuito" in str(e), str(e))
        os.environ.pop("GEMINI_MODELO_IMAGEN", None)
        respuesta = {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": base64.b64encode(PNG).decode()}}]}}],
                     "usageMetadata": {"promptTokenCount": 80, "candidatesTokenCount": 1290}}
        imagenes.gemini._una_peticion = lambda m, c: (cuerpos.append((m, c)) or (200, json.dumps(respuesta)))
        g = imagenes.generar("pan artesanal", negocio="ILCB", rubro="cocina")
        modelo, cuerpo = cuerpos[-1]
        texto = cuerpo["contents"][0]["parts"][0]["text"]
        comprobar("genera horizontal, sin texto, con el rubro", modelo == "gemini-3.1-flash-lite-image" and g["mime"] == "image/png"
                  and cuerpo["generationConfig"]["imageConfig"]["aspectRatio"] == "16:9" and "pan artesanal" in texto and "ILCB" in texto
                  and "Sin texto" in texto and g["uso"]["costo_usd"] == imagenes.PRECIOS[modelo], str(g["uso"]))
        imagenes.gemini._una_peticion = lambda m, c: (200, json.dumps({"candidates": [{"finishReason": "IMAGE_SAFETY", "content": {"parts": []}}]}))
        try:
            imagenes.generar("pan artesanal")
            comprobar("sin imagen: dice el motivo", False)
        except ErrorExterno as e:
            comprobar("sin imagen: dice el motivo", "IMAGE_SAFETY" in str(e), str(e))

        # WordPress: sube la imagen, le pone alt y leyenda y la deja como destacada.
        wp = []

        def responder(req: httpx.Request) -> httpx.Response:
            wp.append(req)
            if req.url.path.endswith("/media/555"):
                return httpx.Response(404, json={"code": "rest_post_invalid_id", "message": "ID no válido"})
            if req.url.path.endswith("/media"):
                return httpx.Response(201, json={"id": 77, "source_url": "https://blog.pe/up/x.jpg"})
            if "/media/" in req.url.path:
                return httpx.Response(200, json={"id": int(req.url.path.rsplit("/", 1)[1]), "source_url": "https://blog.pe/up/x.jpg"})
            return httpx.Response(201, json={"id": 42, "status": "draft", "link": "https://blog.pe/?p=42"})

        os.environ.update(WP_URL="https://blog.pe", WP_USUARIO="editor", WP_CLAVE_APLICACION="x")
        wordpress._http = lambda: httpx.Client(transport=httpx.MockTransport(responder))
        img = {"datos": JPG, "mime": "image/jpeg", "alt": "Pan de masa madre", "leyenda": "Foto: Ana en Pexels", "id_media": None}
        r = wordpress.enviar("Título", "pan-masa-madre", "<p>x</p>", "", False, None, img)
        subida, textos, entrada = wp[-3], wp[-2], wp[-1]
        comprobar("sube la imagen con su nombre", subida.url.path.endswith("/media") and subida.content == JPG
                  and 'filename="pan-masa-madre.jpg"' in subida.headers["content-disposition"], str(subida.headers))
        comprobar("le pone alt y leyenda", json.loads(textos.content) == {"alt_text": "Pan de masa madre", "caption": "Foto: Ana en Pexels"})
        comprobar("la entrada la lleva como destacada", json.loads(entrada.content)["featured_media"] == 77 and r["media"]["id"] == 77, str(r))
        comprobar("y la muestra al inicio del texto (bloque Imagen destacada)",
                  json.loads(entrada.content)["content"] == "<!-- wp:post-featured-image /-->\n\n<p>x</p>", json.loads(entrada.content)["content"])
        os.environ["WP_DESTACADA_EN_TEXTO"] = "no"
        wordpress.enviar("Título", "pan-masa-madre", "<p>x</p>", "", False, 42, {**img, "id_media": 77})
        comprobar("WP_DESTACADA_EN_TEXTO=no: no la pone en el texto", json.loads(wp[-1].content)["content"] == "<p>x</p>")
        os.environ.pop("WP_DESTACADA_EN_TEXTO")
        wordpress.enviar("Título", "pan-masa-madre", "<p>x</p>", "", False, None)
        comprobar("sin imagen, el texto va tal cual", json.loads(wp[-1].content)["content"] == "<p>x</p>")
        n = len(wp)
        wordpress.enviar("Título", "pan-masa-madre", "<p>x</p>", "", False, 42, {**img, "id_media": 77})
        comprobar("ya subida: no la vuelve a subir", len(wp) - n == 2 and wp[-2].url.path.endswith("/media/77"))
        n = len(wp)
        r = wordpress.enviar("Título", "pan-masa-madre", "<p>x</p>", "", False, 42, {**img, "id_media": 555})
        comprobar("borrada de la biblioteca: la sube otra vez", len(wp) - n == 4 and r["media"]["id"] == 77)
    finally:
        imagenes._http, wordpress._http, imagenes.gemini._una_peticion = originales
        for k, v in antes.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def probar_demanda():
    """El autocompletado de Google, simulado con lo que respondio de verdad (2026-10-29)."""
    import json
    import httpx
    from app.seo import demanda

    print("demanda (autocompletado de Google)")
    respuestas = {
        "duración curso barista": ["curso barista duración"],
        "cómo se hace el stollen": ["como se hace el stollen", "como se hace el stollen aleman"],
        "galletas linzer": ["galletas linzer receta", "galletas linzer de almendra"],
        "duración programa sommelier": [],
    }
    pedidas = []

    def google(req):
        q = req.url.params["q"]
        pedidas.append(q)
        if q == "falla":
            return httpx.Response(503)
        return httpx.Response(200, content=json.dumps([q, respuestas.get(q, [])]).encode())

    demanda._http = lambda: httpx.Client(transport=httpx.MockTransport(google))
    demanda._cache.clear()
    s = demanda.senal("cómo se hace el stollen", respuestas["cómo se hace el stollen"])
    comprobar("misma búsqueda sin tilde: EXACTA y conserva la nuestra", s["senal"] == "EXACTA" and s["forma"] == "cómo se hace el stollen"
              and s["sugerencias"] == ["como se hace el stollen aleman"], str(s))
    s = demanda.senal("duración curso barista", respuestas["duración curso barista"])
    comprobar("mismas palabras en otro orden: EXACTA con la forma de Google", s["senal"] == "EXACTA" and s["forma"] == "curso barista duración", str(s))
    s = demanda.senal("galletas linzer", respuestas["galletas linzer"])
    comprobar("solo búsquedas más largas: VARIANTES", s["senal"] == "VARIANTES" and s["forma"] == "galletas linzer" and len(s["sugerencias"]) == 2, str(s))
    comprobar("nada que la contenga: NINGUNA", demanda.senal("duración programa sommelier", ["sommelier sueldo"])["senal"] == "NINGUNA")

    r = demanda.comprobar([
        {"grupo": "barista", "keywords": ["duracion curso barista", "duración curso barista", "Duración curso barista?"]},
        {"grupo": "sommelier", "keywords": ["duración programa sommelier"]},
        {"grupo": "navidad", "keywords": ["galletas linzer", "cómo se hace el stollen"]},
        {"grupo": "caido", "keywords": ["falla"]},
    ])
    g = {x["grupo"]: x for x in r["grupos"]}
    comprobar("disponible si Google respondió a alguna", r["disponible"] is True)
    comprobar("consulta una vez cada forma distinta (sin tildes ni signos)", pedidas.count("duracion curso barista") == 1
              and "duración curso barista" not in pedidas and "Duración curso barista?" not in pedidas, str(pedidas))
    comprobar("por grupo, la mejor señal de sus keywords", g["navidad"]["senal"] == "EXACTA" and g["navidad"]["forma"] == "cómo se hace el stollen"
              and g["sommelier"]["senal"] == "NINGUNA", str(r))
    comprobar("si Google no responde a un grupo, su señal queda vacía (no NINGUNA)", g["caido"]["senal"] is None)
    n = len(pedidas)
    demanda.comprobar([{"grupo": "navidad", "keywords": ["galletas linzer"]}])
    comprobar("guarda las respuestas 24 h", len(pedidas) == n)
    demanda._cache.clear()
    demanda._http = lambda: httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(503)))
    r = demanda.comprobar([{"grupo": "x", "keywords": ["galletas linzer"]}])
    comprobar("Google caído: no disponible", r["disponible"] is False and r["grupos"][0]["senal"] is None, str(r))
    demanda._cache.clear()


def probar_mejora():
    """Propuesta para una página que ya aparece en Google (Gemini simulado): dice ahora / debe decir y términos protegidos."""
    from app.compartido.errores import ErrorExterno
    from app.seo import ia

    print("Mejora de página")
    original = ia.gemini.generar
    pedidos = []
    terminos = [{"nombre": "Gastronomía", "tipo": "CARRERA", "descripcion": ""},
                {"nombre": "Bar y Coctelería", "tipo": "CARRERA", "descripcion": ""},
                {"nombre": "Matrix", "tipo": "SISTEMA", "descripcion": "La intranet de alumnos y docentes."}]

    def falso(prompt, partes, esquema, **k):
        pedidos.append({"prompt": prompt, "texto": partes[0]["text"]})
        return ({"titulo": "Gin tonic: historia, receta y cómo prepararlo en casa" + "x" * 40,
                 "meta_description": "Aprende de dónde viene el gin tonic y cómo prepararlo, en la carrera de bar y cocteleria.",
                 "ideas": [{"donde": "H2", "dice_ahora": "Origen", "debe_decir": "Origen del gin tonic"},
                           {"donde": "Nueva sección", "dice_ahora": "(no existe)", "debe_decir": "Cómo se prepara\nPaso a paso [COMPLETAR: medidas]"},
                           {"donde": "x", "dice_ahora": "y", "debe_decir": " "}, "texto suelto", {}, {"debe_decir": "c"}, {"debe_decir": "d"}],
                 "motivo": "La receta no aparece."}, {"llamadas": 1, "costo_usd": 0.001})

    try:
        ia.gemini.generar = falso
        r = ia.mejora("https://ilcb.edu.pe/gin-tonic/", {"title": "Gin tonic: conoce más", "meta_description": "", "h1": "Gin tonic", "h2": ["Origen"]},
                      [{"consulta": "gin tonic", "impresiones": 2607, "clics": 3, "posicion": 9.0}], negocio="ILCB", rubro="Escuela de cocina",
                      terminos=terminos)
        t = pedidos[0]["texto"]
        comprobar("manda la página, sus búsquedas con cifras, el rubro y los términos protegidos con su descripción",
                  "gin tonic: 2607 impresiones, 3 clics, posición 9.0" in t and "Gin tonic: conoce más" in t
                  and "- Gastronomía (carrera o programa)" in t and "- Matrix (sistema): La intranet de alumnos y docentes." in t
                  and "Escuela de cocina" in pedidos[0]["prompt"] and "{{" not in pedidos[0]["prompt"])
        comprobar("recorta el título; ideas con dónde, qué dice ahora y qué debe decir (máximo 4, sin vacías)", len(r["titulo"]) == ia.MAX_TITULO
                  and r["ideas"][0] == {"donde": "H2", "dice_ahora": "Origen", "debe_decir": "Origen del gin tonic"}
                  and r["ideas"][1]["dice_ahora"] is None and len(r["ideas"]) == 4 and r["motivo"] == "La receta no aparece.", str(r["ideas"]))
        comprobar("un término protegido mal escrito queda como está definido", "carrera de Bar y Coctelería" in r["meta_description"], r["meta_description"])
        comprobar("una sola llamada si no cambia ningún término", len(pedidos) == 1 and r["uso"]["llamadas"] == 1)

        # La IA alarga el nombre de la carrera: se le vuelve a pedir con el error a la vista.
        respuestas = [{"titulo": "Gastronomía y Arte Culinario en Lima", "meta_description": "", "ideas": [], "motivo": ""},
                      {"titulo": "Carrera de Gastronomía en Lima", "meta_description": "", "ideas": [], "motivo": ""}]
        pedidos.clear()
        ia.gemini.generar = lambda p, partes, e, **k: (pedidos.append(partes[0]["text"]), (respuestas[len(pedidos) - 1], {"llamadas": 1}))[1]
        r = ia.mejora("https://x/", {}, [{"consulta": "x"}], terminos=terminos)
        comprobar("nombre de carrera cambiado: reintenta una vez avisando cuál", len(pedidos) == 2 and "«Gastronomía y Arte»" in pedidos[1]
                  and r["titulo"] == "Carrera de Gastronomía en Lima" and r["uso"]["llamadas"] == 2, str(r))
        comprobar("lo que sigue con «en», «Le» o el inicio de otro término no es un cambio",
                  ia.nombres_oficiales("Gastronomía Le Cordon Bleu, Gastronomía y Bar y Coctelería, Gastronomía en Lima", [x["nombre"] for x in terminos])[1] == [])
        comprobar("«Cocina Profesional» sí es un cambio", ia.nombres_oficiales("Cocina Profesional", ["Cocina"])[1] == ["Cocina Profesional"])
        comprobar("si el término alargado también está en la lista, vale", ia.nombres_oficiales("Cocina Peruana", ["Cocina", "Cocina Peruana"])[1] == [])
        ia.gemini.generar = lambda *a, **k: ({"titulo": "Matrix Pro: la intranet", "meta_description": "", "ideas": [], "motivo": ""}, {"llamadas": 1})
        try:
            ia.mejora("https://x/", {}, [{"consulta": "x"}], terminos=terminos)
            comprobar("si insiste en cambiarlo: error claro", False)
        except ErrorExterno as e:
            comprobar("si insiste en cambiarlo: error claro", "«Matrix Pro»" in str(e) and "Términos protegidos" in str(e), str(e))
        ia.gemini.generar = lambda *a, **k: ({"titulo": " ", "meta_description": "", "ideas": [], "motivo": ""}, {})
        try:
            ia.mejora("https://x/", {}, [{"consulta": "x"}])
            comprobar("sin título: error claro", False)
        except ErrorExterno as e:
            comprobar("sin título: error claro", "título" in str(e))
    finally:
        ia.gemini.generar = original


def probar_search_console():
    """Search Console simulado: token, propiedades, consultas paginadas y errores."""
    import json
    import os
    import httpx
    from datetime import date
    from app.compartido.errores import ErrorExterno
    from app.keywords import google_ads
    from app.seo import search_console as gsc

    print("Search Console")
    antes = {k: os.environ.get(k) for k in ("GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_REFRESH_TOKEN", "GSC_PROPIEDAD", "GSC_PAIS")}
    for k in antes:
        os.environ.pop(k, None)
    google_ads._acceso.update(token=None, expira=0.0)
    try:
        c = gsc.configurado()
        comprobar("sin claves dice qué falta", not c["completo"] and "GSC_PROPIEDAD" in c["faltan"] and "GOOGLE_ADS_REFRESH_TOKEN" in c["faltan"], str(c))
        try:
            gsc.consultas()
            comprobar("sin claves no consulta", False)
        except ErrorExterno as e:
            comprobar("sin claves no consulta", "GSC_PROPIEDAD" in str(e))
        os.environ.update(GOOGLE_ADS_CLIENT_ID="cid", GOOGLE_ADS_CLIENT_SECRET="sec", GOOGLE_ADS_REFRESH_TOKEN="rt",
                          GSC_PROPIEDAD="sc-domain:ilcb.edu.pe", GSC_PAIS="per")
        pedidos = []
        modo = {"permiso": "siteRestrictedUser", "error": None}

        def google(req):
            if req.url.host == "oauth2.googleapis.com":
                return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
            pedidos.append((req.method, req.url.raw_path.decode(), json.loads(req.content) if req.content else None, req.headers.get("authorization")))
            if modo["error"]:
                return httpx.Response(modo["error"][0], text=modo["error"][1])
            if req.url.path.endswith("/sites"):
                return httpx.Response(200, json={"siteEntry": [{"siteUrl": "sc-domain:ilcb.edu.pe", "permissionLevel": modo["permiso"]},
                                                               {"siteUrl": "https://otra.pe/", "permissionLevel": "siteOwner"}]})
            cuerpo = json.loads(req.content)
            n = gsc.POR_PAGINA if cuerpo["startRow"] == 0 else 1
            return httpx.Response(200, json={"rows": [{"keys": ["curso barista duración", "https://ilcb.edu.pe/barista/"], "clicks": 3,
                                                       "impressions": 120, "ctr": 0.025, "position": 14.37}] * n})

        gsc._http = google_ads._http = lambda: httpx.Client(transport=httpx.MockTransport(google))
        r = gsc.comprobar()
        comprobar("ve la propiedad con permiso de lectura", r["ok"] and r["permiso"] == "siteRestrictedUser" and len(r["propiedades"]) == 2, str(r))
        comprobar("usa el token de la autorización compartida con Google Ads", pedidos[-1][3] == "Bearer tok")
        modo["permiso"] = "siteUnverifiedUser"
        comprobar("sin verificar: no vale", gsc.comprobar()["ok"] is False)
        pedidos.clear()
        r = gsc.consultas(90)
        comprobar("pagina hasta que una página viene incompleta", len(pedidos) == 2 and pedidos[1][2]["startRow"] == gsc.POR_PAGINA
                  and len(r["filas"]) == gsc.POR_PAGINA + 1, str(len(pedidos)))
        q = pedidos[0]
        comprobar("pide consulta × página, filtrado por país", q[2]["dimensions"] == ["query", "page"]
                  and q[2]["dimensionFilterGroups"][0]["filters"][0]["expression"] == "per" and "sc-domain%3Ailcb.edu.pe" in q[1], str(q[1]))
        f = r["filas"][0]
        comprobar("normaliza la fila", f == {"consulta": "curso barista duración", "url": "https://ilcb.edu.pe/barista/", "clics": 3,
                                              "impresiones": 120, "ctr": 0.025, "posicion": 14.4}, str(f))
        comprobar("rango: 90 días hasta hace 3", gsc.rango(90, date(2026, 10, 29)) == ("2026-07-29", "2026-10-26"))
        for estado, texto, esperado in ((403, '{"error":{"message":"Request had insufficient authentication scopes."}}', "Conectar con Google"),
                                        (403, '{"error":{"message":"User does not have sufficient permission"}}', "Restringido"),
                                        (404, "not found", "GSC_PROPIEDAD")):
            modo["error"] = (estado, texto)
            try:
                gsc.comprobar()
                comprobar(f"error {estado}: mensaje claro", False)
            except ErrorExterno as e:
                comprobar(f"error {estado}: mensaje claro ({esperado})", esperado in str(e), str(e))
    finally:
        for k, v in antes.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        google_ads._acceso.update(token=None, expira=0.0)


if __name__ == "__main__":
    probar_search_console()
    probar_mejora()
    probar_demanda()
    probar_rastreo()
    probar_ia()
    probar_articulo()
    probar_wordpress()
    probar_imagenes()
    print("\nTODO OK" if not fallos else f"\n{fallos} FALLOS")
    raise SystemExit(1 if fallos else 0)
