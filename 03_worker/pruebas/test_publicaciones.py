# -*- coding: utf-8 -*-
"""
Pruebas de las publicaciones sin IA (gratis):
    python -m pruebas.test_publicaciones

Gemini se sustituye por respuestas preparadas; el flyer se arma con un fondo hecho con Pillow.
"""
from io import BytesIO

from PIL import Image

from app.compartido.errores import ErrorExterno
from app.publicaciones import flyer, textos

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


CONTEXTO = {"negocio": "Instituto Le Cordon Bleu Perú", "datos": "Admisión abierta: Inscripciones abiertas 2027-1"}
FLYER = {"titulo": "Ven y conoce el campus", "detalle": "[FALTA: fecha]", "cta": "Inscríbete", "busqueda": "chef cocina", "fondo": "Una cocina"}


def probar_textos():
    print("textos por red con Gemini simulado")
    original = textos.gemini.generar
    respuesta = {"titulo": "Admisión 2027", "facebook": "Texto FB", "instagram": "Texto IG", "linkedin": "Texto LI", "texto": "Texto común",
                 "hashtags": ["LeCordonBleuPeru", "#Gastronomía", "#Gastronomía", "#chef!"], "flyer": dict(FLYER)}
    vistos = {}

    def falso(sistema, partes, esquema, **k):
        vistos["sistema"], vistos["texto"], vistos["esquema"] = sistema, partes[0]["text"], esquema
        return respuesta, {"llamadas": 1, "costo_usd": 0.001}
    textos.gemini.generar = falso
    try:
        t = textos.textos("Abrimos la admisión", ["instagram", "FACEBOOK"], media="IMAGEN", contexto=CONTEXTO)
        comprobar("solo las redes pedidas, en orden fijo", list(t["textos"]) == ["FACEBOOK", "INSTAGRAM"], str(t["textos"]))
        comprobar("un texto por red: el esquema pide esas redes y el flyer",
                  set(vistos["esquema"]["required"]) == {"titulo", "hashtags", "flyer", "facebook", "instagram"}, str(vistos["esquema"]["required"]))
        comprobar("le pasa el modo, el formato, los datos confirmados y el negocio",
                  "un texto por red" in vistos["texto"] and "con una imagen" in vistos["texto"] and "2027-1" in vistos["texto"]
                  and "Instituto Le Cordon Bleu Perú" in vistos["sistema"])
        comprobar("hashtags con # y sin repetidos ni símbolos", t["hashtags"] == ["#LeCordonBleuPeru", "#Gastronomía", "#chef"], str(t["hashtags"]))
        comprobar("devuelve título, textos del flyer y uso", t["titulo"] == "Admisión 2027" and t["flyer"] == FLYER and t["uso"]["llamadas"] == 1, str(t["flyer"]))

        t = textos.textos("Abrimos la admisión", ["FACEBOOK", "INSTAGRAM", "LINKEDIN"], modo="MISMO", hashtags_base=["#LeCordonBleuPeru", "Gastronomia"],
                          contexto=CONTEXTO)
        comprobar("el mismo texto: un solo campo en el esquema y el mismo texto en las tres redes",
                  "texto" in vistos["esquema"]["required"] and "facebook" not in vistos["esquema"]["required"]
                  and set(t["textos"].values()) == {"Texto común"} and len(t["textos"]) == 3, str(t["textos"]))
        comprobar("los hashtags base van primero y no se repiten",
                  t["hashtags"] == ["#LeCordonBleuPeru", "#Gastronomia", "#Gastronomía", "#chef"] and "#LeCordonBleuPeru #Gastronomia" in vistos["texto"], str(t["hashtags"]))

        respuesta["linkedin"] = "x" * 4000
        t = textos.textos("Idea", ["LINKEDIN"], contexto=CONTEXTO)
        comprobar("recorta al límite de la red", len(t["textos"]["LINKEDIN"]) == textos.LIMITES["LINKEDIN"])
        respuesta["flyer"] = {"titulo": "y" * 90}
        t = textos.textos("Idea", ["LINKEDIN"], contexto=CONTEXTO)
        comprobar("el flyer: recorta el título y completa lo que falte", len(t["flyer"]["titulo"]) == 45 and t["flyer"]["cta"] == "", str(t["flyer"]))
        respuesta["instagram"] = "  "
        e = lanza(lambda: textos.textos("Idea", ["INSTAGRAM"], contexto=CONTEXTO))
        comprobar("si falta el texto de una red, error claro", e is not None and "Instagram" in e, str(e))
        e = lanza(lambda: textos.textos("Idea", ["TIKTOK"], contexto=CONTEXTO))
        comprobar("una red desconocida no cuenta", e is not None and "al menos una red" in e, str(e))
    finally:
        textos.gemini.generar = original


def _imagen(ancho: int, alto: int, modo: str = "RGB", formato: str = "JPEG") -> bytes:
    b = BytesIO()
    Image.new(modo, (ancho, alto), (200, 120, 40) if modo == "RGB" else (10, 30, 60, 255)).save(b, formato)
    return b.getvalue()


def probar_flyer():
    print("flyer")
    datos = flyer.componer(_imagen(1600, 900), "Ven y conoce nuestro Campus Le Cordon Bleu", "Sábado 15 de noviembre", "Inscríbete",
                           logo=_imagen(400, 150, "RGBA", "PNG"))
    img = Image.open(BytesIO(datos))
    comprobar("JPEG de 1080x1350 aunque el fondo sea horizontal", img.format == "JPEG" and img.size == (1080, 1350), f"{img.format} {img.size}")
    comprobar("arriba queda la foto; abajo, el color de la marca", img.getpixel((900, 300))[0] > 150 and img.getpixel((900, 1330))[2] > img.getpixel((900, 1330))[0],
              f"{img.getpixel((900, 300))} {img.getpixel((900, 1330))}")
    comprobar("la placa del logo es blanca", min(img.getpixel((120, 64))) > 220, str(img.getpixel((120, 64))))
    largo = flyer.componer(_imagen(800, 1000), "Un título larguísimo " * 6)
    comprobar("un título muy largo no rompe nada", Image.open(BytesIO(largo)).size == (1080, 1350))
    comprobar("un fondo roto da un error claro", "no es una imagen" in (lanza(lambda: flyer.componer(b"nada", "Hola")) or ""))


def probar_verificar():
    """Si el post sigue en su red, con respuestas simuladas (no sale a internet)."""
    import httpx
    from app.publicaciones import verificar

    print("Verificar enlaces")
    texto = "¡Ven y conoce nuestro Campus! Este sábado abrimos las puertas de Le Cordon Bleu."
    paginas = {
        "/activa": (200, '<meta property="og:description" content="&iexcl;Ven y conoce nuestro Campus! Este s&aacute;bado abrimos las puertas de Le Cordon Bleu...">'),
        "/borrada": (404, "Not found"),
        "/no-disponible": (200, "<h2>This content isn't available right now</h2>"),
        "/login": (302, ""),
        "/otra": (200, "<title>Facebook</title><p>Inicia sesión o regístrate</p>"),
        "/caida": (503, "error"),
    }

    def responder(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/login":
            return httpx.Response(302, headers={"location": "https://www.facebook.com/login/?next=x"})
        if req.url.path.startswith("/login/"):
            return httpx.Response(200, text="Inicia sesión")
        if req.url.path == "/sin-red":
            raise httpx.ConnectError("sin red")
        estado, cuerpo = paginas[req.url.path]
        return httpx.Response(estado, text=cuerpo)

    with httpx.Client(transport=httpx.MockTransport(responder), follow_redirects=True) as c:
        def una(ruta):
            return verificar.verificar({"FACEBOOK": f"https://www.facebook.com{ruta}"}, {"FACEBOOK": texto}, cliente=c)["resultados"]["FACEBOOK"]
        comprobar("muestra el texto publicado (con entidades y tildes): ACTIVA", una("/activa")["estado"] == "ACTIVA", str(una("/activa")))
        comprobar("404: NO_DISPONIBLE", una("/borrada")["estado"] == "NO_DISPONIBLE" and una("/borrada")["http"] == 404)
        comprobar("«contenido no disponible»: NO_DISPONIBLE", una("/no-disponible")["estado"] == "NO_DISPONIBLE")
        comprobar("pide iniciar sesión: SIN_CONFIRMAR, no se da por borrada", una("/login")["estado"] == "SIN_CONFIRMAR"
                  and "sesión" in una("/login")["detalle"])
        comprobar("responde sin el texto: SIN_CONFIRMAR", una("/otra")["estado"] == "SIN_CONFIRMAR")
        comprobar("error del servidor: SIN_CONFIRMAR", una("/caida")["estado"] == "SIN_CONFIRMAR" and una("/caida")["http"] == 503)
        comprobar("sin red: SIN_CONFIRMAR con el motivo", una("/sin-red")["estado"] == "SIN_CONFIRMAR" and una("/sin-red")["http"] is None)


if __name__ == "__main__":
    probar_textos()
    probar_flyer()
    probar_verificar()
    print("\nTODO OK" if not fallos else f"\n{fallos} FALLOS")
