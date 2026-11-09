# -*- coding: utf-8 -*-
"""
Rastreo responsable de sitios publicos: robots.txt, sitemaps y una pagina a la vez.

- Se respeta robots.txt (Disallow y Crawl-delay) y se va despacio: una peticion
  por segundo como minimo por sitio. Si el sitio responde 403/429 se frena.
- Los sitemaps salen de robots.txt; si no anuncia ninguno se prueban las tres
  rutas habituales y, si tampoco, los enlaces de la portada.
- Los sitemaps de taxonomias (categorias, etiquetas, autores...) y las paginas de
  servicio (carrito, mi cuenta, contacto...) se registran como excluidos, con el
  motivo, en vez de descargarse.
- De cada pagina se guarda lo que sirve para saber de que trata: title, meta
  description, H1, H2, canonical, idioma y un extracto del texto. Lo que no
  existe queda vacio; nunca se rellena.
"""
from __future__ import annotations

import gzip
import hashlib
import re
import time
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx

AGENTE = "Mozilla/5.0 (compatible; RadarSEO/0.1; investigacion de contenidos de Le Cordon Bleu Peru)"
NOMBRE_ROBOTS = "RadarSEO"
TIMEOUT_S = 25
MAX_BYTES = 4_000_000
PAUSA_MINIMA_S = 1.0
RUTAS_SITEMAP = ("/sitemap_index.xml", "/sitemap.xml", "/wp-sitemap.xml")
PROFUNDIDAD_SITEMAPS = 3

# Sitemaps de listados, no de contenidos: se cuentan pero no se recorren.
_TAXONOMIAS = frozenset(
    "category categories categoria categorias tag tags post_tag author authors user users taxonomies taxonomy "
    "attachment attachments product_cat product_tag floating tipo eje format formato".split()
)
# Paginas de servicio: no dicen nada del contenido del sitio.
_SERVICIO = frozenset(
    "cart carrito checkout finalizar-compra my-account mi-cuenta login wp-login.php wp-admin wp-json feed "
    "portal-de-transparencia transparencia politica-de-privacidad politicas-de-privacidad privacidad "
    "terminos-y-condiciones terminos-condiciones libro-de-reclamaciones contacto contactanos gracias "
    "search buscar xmlrpc.php".split()
)
_NO_HTML = re.compile(r"\.(pdf|jpe?g|png|gif|webp|svg|zip|rar|docx?|xlsx?|pptx?|mp4|mp3|ico|css|js|xml)$", re.I)


def _cliente() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": AGENTE, "Accept-Language": "es-PE,es;q=0.9"},
        follow_redirects=True, timeout=TIMEOUT_S,
    )


# ── URLs ──────────────────────────────────────────────────────────────────

def normalizar_url(url: str) -> str:
    """Esquema y host en minusculas, sin fragmento ni parametros de seguimiento; la ruta se respeta."""
    url, _ = urldefrag(url.strip())
    p = urlsplit(url)
    consulta = "&".join(q for q in p.query.split("&") if q and not re.match(r"(utm_|gclid|fbclid)", q, re.I))
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/", consulta, ""))


def host(url: str) -> str:
    return urlsplit(url).netloc.lower()


def base(h: str) -> str:
    return h if h.startswith("http") else f"https://{h}"


def motivo_exclusion_url(url: str) -> str | None:
    p = urlsplit(url)
    if _NO_HTML.search(p.path):
        return "No es una página (archivo)"
    if any(s.lower() in _SERVICIO for s in p.path.split("/") if s):
        return "Página de servicio (carrito, cuenta, contacto…)"
    if re.search(r"/(page|pagina)/\d+/?$", p.path):
        return "Paginación de un listado"
    return None


def motivo_exclusion_sitemap(url: str) -> str | None:
    nombre = urlsplit(url).path.rsplit("/", 1)[-1].lower()
    trozos = set(re.split(r"[-_.]", nombre))
    if trozos & _TAXONOMIAS:
        return "Sitemap de categorías, etiquetas o autores (listados, no contenidos)"
    return None


# ── robots.txt ────────────────────────────────────────────────────────────

class Robots:
    def __init__(self, texto: str | None):
        self.existe = texto is not None
        self._p = RobotFileParser()
        self._p.parse((texto or "").splitlines())

    def permite(self, url: str) -> bool:
        return self._p.can_fetch(NOMBRE_ROBOTS, url)

    @property
    def sitemaps(self) -> list[str]:
        return list(dict.fromkeys(self._p.site_maps() or []))

    @property
    def pausa(self) -> float:
        d = self._p.crawl_delay(NOMBRE_ROBOTS)
        return max(PAUSA_MINIMA_S, float(d or 0))


def leer_robots(c: httpx.Client, h: str) -> Robots:
    try:
        r = c.get(base(h) + "/robots.txt")
        return Robots(r.text if r.status_code == 200 else None)
    except httpx.HTTPError:
        return Robots(None)


# ── Sitemaps ──────────────────────────────────────────────────────────────

def _local(etiqueta: str) -> str:
    return etiqueta.rsplit("}", 1)[-1]


def leer_sitemap(contenido: bytes) -> tuple[str, list[tuple[str, str | None]]]:
    """('indice' | 'urls', [(loc, lastmod)]). Admite namespaces y gzip."""
    if contenido[:2] == b"\x1f\x8b":
        contenido = gzip.decompress(contenido)
    raiz = ET.fromstring(contenido)
    tipo = "indice" if _local(raiz.tag) == "sitemapindex" else "urls"
    hijo = "sitemap" if tipo == "indice" else "url"
    salida = []
    for el in raiz:
        if _local(el.tag) != hijo:
            continue
        loc = lastmod = None
        for c in el:
            n = _local(c.tag)
            if n == "loc" and c.text:
                loc = c.text.strip()
            elif n == "lastmod" and c.text:
                lastmod = c.text.strip()
        if loc:
            salida.append((loc, lastmod))
    return tipo, salida


def descubrir(hosts: list[str], maximo: int = 3000) -> dict:
    """
    Todas las URLs que el sitio declara, con su sitemap de origen.
    {urls: [{url, sitemap, lastmod, excluida}], sitemaps: [{url, tipo, urls, excluido, estado}], avisos: []}
    """
    urls: dict[str, dict] = {}
    sitemaps: list[dict] = []
    avisos: list[str] = []
    with _cliente() as c:
        for h in hosts:
            robots = leer_robots(c, h)
            if not robots.existe:
                avisos.append(f"{host(base(h))}: no publica robots.txt.")
            iniciales = robots.sitemaps
            if not iniciales:
                iniciales = [base(h) + r for r in RUTAS_SITEMAP]
            vistos: set[str] = set()
            antes = len(urls)
            pendientes = [(s, 0, not robots.sitemaps) for s in iniciales]
            while pendientes and len(urls) < maximo:
                s, nivel, tanteo = pendientes.pop(0)
                if s in vistos:
                    continue
                vistos.add(s)
                excl = motivo_exclusion_sitemap(s)
                if excl:
                    sitemaps.append({"url": s, "tipo": None, "urls": 0, "excluido": excl, "estado": "OK"})
                    continue
                try:
                    r = c.get(s)
                    time.sleep(robots.pausa)
                    if r.status_code != 200:
                        if not tanteo:
                            sitemaps.append({"url": s, "tipo": None, "urls": 0, "excluido": None, "estado": f"HTTP {r.status_code}"})
                        continue
                    tipo, locs = leer_sitemap(r.content)
                except (httpx.HTTPError, ET.ParseError, OSError) as e:
                    if not tanteo:
                        sitemaps.append({"url": s, "tipo": None, "urls": 0, "excluido": None, "estado": f"Ilegible: {type(e).__name__}"})
                    continue
                sitemaps.append({"url": s, "tipo": tipo, "urls": len(locs), "excluido": None, "estado": "OK"})
                if tipo == "indice":
                    if nivel < PROFUNDIDAD_SITEMAPS:
                        pendientes.extend((loc, nivel + 1, False) for loc, _ in locs)
                    continue
                for loc, lastmod in locs:
                    u = normalizar_url(loc)
                    if u not in urls and len(urls) < maximo:
                        urls[u] = {"url": u, "sitemap": s, "lastmod": lastmod, "excluida": motivo_exclusion_url(u)}
                if tanteo:
                    break  # con la primera ruta habitual que responde basta
            if len(urls) == antes:
                avisos.append(f"{host(base(h))}: sin sitemap útil; se toman los enlaces de su portada.")
                for u in enlaces_portada(c, h, robots):
                    if u not in urls and len(urls) < maximo:
                        urls[u] = {"url": u, "sitemap": "enlaces de la portada", "lastmod": None, "excluida": motivo_exclusion_url(u)}
            if len(urls) >= maximo:
                avisos.append(f"Se alcanzó el máximo de {maximo} URLs: el resto no se registró.")
                break
    return {"urls": list(urls.values()), "sitemaps": sitemaps, "avisos": avisos}


def enlaces_portada(c: httpx.Client, h: str, robots: Robots) -> list[str]:
    inicio = base(h) + "/"
    if not robots.permite(inicio):
        return []
    try:
        r = c.get(inicio)
    except httpx.HTTPError:
        return []
    if r.status_code != 200:
        return []
    p = _Extractor()
    p.feed(r.text)
    propio = host(str(r.url))
    salida = []
    for e in p.enlaces:
        u = normalizar_url(urljoin(str(r.url), e))
        if host(u) == propio and u.startswith("http") and u not in salida:
            salida.append(u)
    return salida


# ── Extraccion de una pagina ──────────────────────────────────────────────

_VACIOS = frozenset("area base br col embed hr img input link meta param source track wbr".split())
_SIN_TEXTO = frozenset("script style noscript template svg iframe canvas".split())
_PLANTILLA = frozenset("header nav footer aside form".split())
_PISTAS_PLANTILLA = re.compile(r"(^|[\s_-])(search|buscar|buscador|menu|modal|popup|cookie|breadcrumb|offcanvas)([\s_-]|$)", re.I)
# Bloques que listan OTRAS entradas (relacionadas, recientes, rejilla del blog): sus H2 no son de esta pagina.
_PISTAS_LISTADO = re.compile(r"blog_grid|blog-grid|related|relacionad|recent-?posts|entradas-recientes|posts?[_-]nav|post-navigation|sidebar|comments|comentarios|share|compartir", re.I)
# Encabezados que pone la plantilla, no el contenido (el «BUSCAR» de ilcb.edu.pe).
_ENCABEZADOS_RUIDO = frozenset(
    "buscar search menu menú navegación navegacion carrito cart cerrar categorías categorias categories etiquetas tags archivo archivos".split()
)


class _Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pila: list[tuple[str, bool]] = []  # (etiqueta, ignorar)
        self.ignorados = 0
        self.title: str | None = None
        self.meta_description: str | None = None
        self.canonical: str | None = None
        self.lang: str | None = None
        self.h1: list[str] = []
        self.h2: list[str] = []
        self.h3 = 0
        self.texto: list[str] = []
        self.enlaces: list[str] = []
        self._captura: tuple[str, list[str]] | None = None
        self._en_title = False
        self._titulo: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html" and a.get("lang"):
            self.lang = a["lang"].strip()[:10]
        if tag == "meta" and a.get("name", "").lower() == "description" and self.meta_description is None:
            self.meta_description = _limpio(a.get("content", "")) or None
        if tag == "link" and "canonical" in a.get("rel", "").lower().split() and self.canonical is None:
            self.canonical = a.get("href", "").strip() or None
        if tag == "a" and a.get("href"):
            self.enlaces.append(a["href"])
        if tag in _VACIOS:
            return
        # Un <header> dentro de <article>/<main> es la cabecera del contenido (suele llevar el H1), no de la plantilla.
        plantilla = tag in _PLANTILLA and not (tag == "header" and (self.pila_tiene("article") or self.pila_tiene("main")))
        ignorar = (
            tag in _SIN_TEXTO or plantilla
            or bool(_PISTAS_PLANTILLA.search(a.get("class", "") + " " + a.get("id", "")))
            or bool(_PISTAS_LISTADO.search(a.get("class", "") + " " + a.get("id", "")))
            or a.get("aria-hidden") == "true" or "hidden" in a
        )
        if tag == "title" and self.title is None and not self.pila_tiene("svg"):
            self._en_title = True
        self.pila.append((tag, ignorar))
        self.ignorados += ignorar
        if tag in ("h1", "h2") and not self.ignorados and self._captura is None:
            self._captura = (tag, [])
        if tag == "h3" and not self.ignorados:
            self.h3 += 1

    def pila_tiene(self, tag: str) -> bool:
        return any(t == tag for t, _ in self.pila)

    def handle_endtag(self, tag):
        if tag == "title" and self._en_title:
            self._en_title = False
            self.title = _limpio("".join(self._titulo)) or None
        if self._captura and self._captura[0] == tag:
            t = _limpio("".join(self._captura[1]))
            self._captura = None
            if t and t.lower() not in _ENCABEZADOS_RUIDO:
                (self.h1 if tag == "h1" else self.h2).append(t)
        if not any(t == tag for t, _ in self.pila):
            return
        while self.pila:
            t, ign = self.pila.pop()
            self.ignorados -= ign
            if t == tag:
                break

    def handle_data(self, data):
        if self._en_title:
            self._titulo.append(data)
            return
        if self.ignorados:
            return
        if self._captura:
            self._captura[1].append(data)
        if data.strip():
            self.texto.append(data)


def _limpio(t: str) -> str:
    return re.sub(r"\s+", " ", t or "").strip()


# Fecha de publicacion que declara la pagina (WordPress/Yoast la ponen en las dos formas).
_PUBLICADO = [
    re.compile(r"""<meta[^>]+property=["']article:published_time["'][^>]*content=["']([^"']+)""", re.I),
    re.compile(r"""<meta[^>]+content=["']([^"']+)["'][^>]*property=["']article:published_time["']""", re.I),
    re.compile(r'"datePublished"\s*:\s*"([^"]+)"'),
    re.compile(r"""<meta[^>]+itemprop=["']datePublished["'][^>]*content=["']([^"']+)""", re.I),
]


def fecha_publicacion(html: str) -> str | None:
    """AAAA-MM-DD de la primera fecha de publicacion declarada, o None si no dice."""
    for r in _PUBLICADO:
        m = r.search(html)
        if m and re.match(r"\d{4}-\d{2}-\d{2}", m.group(1).strip()):
            return m.group(1).strip()[:10]
    return None


def extraer_html(html: str) -> dict:
    p = _Extractor()
    p.feed(html)
    p.close()
    texto = _limpio(" ".join(p.texto))
    h2 = list(dict.fromkeys(p.h2))[:40]
    datos = {
        "title": p.title,
        "meta_description": p.meta_description,
        "h1": p.h1[0] if p.h1 else None,
        "h1_total": len(p.h1),
        "h2": h2,
        "h3_total": p.h3,
        "canonical": p.canonical,
        "lang": p.lang,
        "palabras": len(texto.split()),
        "extracto": texto[:1500],
        "publicado": fecha_publicacion(html),
    }
    huella = "|".join([datos["title"] or "", datos["meta_description"] or "", datos["h1"] or "", "/".join(h2), texto[:1500]])
    datos["hash"] = hashlib.sha1(huella.encode("utf-8")).hexdigest()
    return datos


def paginas(urls: list[str], pausa_s: float = PAUSA_MINIMA_S) -> dict:
    """
    Descarga y extrae cada URL, en orden y despacio.
    {paginas: [{url, estado, http, url_final, motivo, datos}], frenar}
    estado: OK | NO_HTML | HTTP_ERROR | BLOQUEADA | ERROR. `frenar` = el sitio pidio parar (403/429).
    """
    salida = []
    robots_por_host: dict[str, Robots] = {}
    frenar = False
    with _cliente() as c:
        for i, url in enumerate(urls):
            partes = urlsplit(url)
            origen = f"{partes.scheme}://{partes.netloc.lower()}"  # el robots.txt del mismo esquema y host
            if origen not in robots_por_host:
                robots_por_host[origen] = leer_robots(c, origen)
            robots = robots_por_host[origen]
            if frenar:
                break
            if not robots.permite(url):
                salida.append({"url": url, "estado": "BLOQUEADA", "http": None, "url_final": None,
                               "motivo": "robots.txt no permite leerla", "datos": None})
                continue
            if i:
                time.sleep(max(pausa_s, robots.pausa))
            salida.append(_una(c, url))
            if salida[-1]["http"] in (403, 429):
                frenar = True
    return {"paginas": salida, "frenar": frenar}


def _una(c: httpx.Client, url: str) -> dict:
    fila = {"url": url, "estado": "ERROR", "http": None, "url_final": None, "motivo": None, "datos": None}
    try:
        r = c.get(url)
    except httpx.HTTPError as e:
        fila["motivo"] = f"Sin respuesta: {type(e).__name__}"
        return fila
    fila["http"] = r.status_code
    fila["url_final"] = normalizar_url(str(r.url))
    if r.status_code >= 400:
        fila["estado"] = "BLOQUEADA" if r.status_code in (401, 403, 429) else "HTTP_ERROR"
        fila["motivo"] = f"El sitio respondió {r.status_code}"
        return fila
    tipo = r.headers.get("content-type", "").lower()
    if "html" not in tipo:
        fila["estado"] = "NO_HTML"
        fila["motivo"] = f"Contenido {tipo.split(';')[0] or 'desconocido'}"
        return fila
    if len(r.content) > MAX_BYTES:
        fila["motivo"] = "Página demasiado grande"
        return fila
    fila["estado"] = "OK"
    fila["datos"] = extraer_html(r.text)
    return fila
