# -*- coding: utf-8 -*-
"""
Flyer de una publicacion: una foto de fondo con el titulo, el detalle, la llamada a la accion y
el logo encima, en 1080x1350 (4:5, sirve para Facebook, Instagram y LinkedIn).

El texto y el logo los pone este modulo y no la IA: los generadores de imagenes escriben mal las
palabras y deforman los logos (paso en Vids con «Le Cordon Bleu»). El fondo puede ser una foto
del banco gratuito, una imagen creada con IA o una foto propia.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.compartido.errores import ErrorExterno

ANCHO, ALTO = 1080, 1350
MARGEN = 80
_FUENTES = [Path(__file__).parent / "fuentes", Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/dejavu")]
_NEGRITA = ["Montserrat-Bold.ttf", "segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"]
_NORMAL = ["Montserrat-Regular.ttf", "segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"]


def _fuente(nombres: list[str], tamano: int) -> ImageFont.FreeTypeFont:
    for carpeta in _FUENTES:
        for n in nombres:
            if (carpeta / n).exists():
                return ImageFont.truetype(str(carpeta / n), tamano)
    return ImageFont.load_default(tamano)


def _rgb(hexa: str) -> tuple[int, int, int]:
    h = hexa.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _partir(texto: str, fuente, ancho: int) -> list[str]:
    """Reparte el texto en lineas que caben en `ancho` (una palabra mas larga va sola)."""
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = f"{actual} {palabra}".strip()
        if fuente.getlength(prueba) <= ancho or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def _titulo(texto: str, ancho: int) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """El tamano mas grande en el que el titulo cabe en 3 lineas (de 104 a 56 px)."""
    for tamano in range(104, 54, -6):
        f = _fuente(_NEGRITA, tamano)
        lineas = _partir(texto, f, ancho)
        if len(lineas) <= 3 and all(f.getlength(x) <= ancho for x in lineas):
            return f, lineas
    f = _fuente(_NEGRITA, 56)
    return f, _partir(texto, f, ancho)[:4]


def _alto_linea(fuente) -> int:
    a, d = fuente.getmetrics()
    return a + d


def componer(fondo: bytes, titulo: str, detalle: str = "", cta: str = "", *, logo: bytes | None = None,
             color: str = "#0B1F3F", acento: str = "#C9A55A") -> bytes:
    """-> JPEG 1080x1350."""
    try:
        base = Image.open(BytesIO(fondo))
        base = ImageOps.exif_transpose(base).convert("RGB")
    except Exception as e:  # Pillow lanza varios tipos segun el formato roto
        raise ErrorExterno("El fondo no es una imagen válida.") from e
    base = ImageOps.fit(base, (ANCHO, ALTO), Image.Resampling.LANCZOS, centering=(0.5, 0.35)).convert("RGBA")

    # Degradado del color de la marca, de transparente (un tercio de la altura) a casi opaco abajo:
    # el texto se lee sobre cualquier foto.
    r, g, b = _rgb(color)
    capa = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    pincel = ImageDraw.Draw(capa)
    inicio = int(ALTO * 0.33)
    for y in range(inicio, ALTO):
        t = (y - inicio) / (ALTO - inicio)
        pincel.line([(0, y), (ANCHO, y)], fill=(r, g, b, int(240 * min(1.0, t * 1.5))))
    base = Image.alpha_composite(base, capa)
    d = ImageDraw.Draw(base)
    util = ANCHO - 2 * MARGEN
    claro = (255, 255, 255, 255)

    # De abajo hacia arriba: llamada a la accion, detalle, titulo y la raya de acento.
    y = ALTO - MARGEN
    if cta.strip():
        f = _fuente(_NEGRITA, 40)
        texto = cta.strip()
        while f.getlength(texto) > util - 80 and len(texto) > 4:
            texto = texto[:-2].rstrip() + "…"
        alto = _alto_linea(f) + 36
        largo = int(f.getlength(texto)) + 80
        y -= alto
        d.rounded_rectangle([MARGEN, y, MARGEN + largo, y + alto], radius=alto // 2, fill=(*_rgb(acento), 255))
        d.text((MARGEN + 40, y + 18), texto, font=f, fill=(r, g, b, 255))
        y -= 40
    if detalle.strip():
        f = _fuente(_NORMAL, 44)
        lineas = _partir(detalle.strip(), f, util)[:2]
        paso = _alto_linea(f) + 4
        y -= paso * len(lineas)
        for i, linea in enumerate(lineas):
            d.text((MARGEN, y + i * paso), linea, font=f, fill=(235, 235, 235, 255))
        y -= 28
    f, lineas = _titulo(titulo.strip(), util)
    paso = int(_alto_linea(f) * 0.98)
    y -= paso * len(lineas)
    for i, linea in enumerate(lineas):
        # Sombra suave: el titulo se lee aunque caiga sobre algo claro.
        d.text((MARGEN + 3, y + i * paso + 4), linea, font=f, fill=(0, 0, 0, 120))
        d.text((MARGEN, y + i * paso), linea, font=f, fill=claro)
    d.rectangle([MARGEN, y - 36, MARGEN + 120, y - 28], fill=(*_rgb(acento), 255))

    # El logo arriba a la izquierda, sobre una placa blanca: se ve igual sobre cualquier foto.
    if logo:
        try:
            marca = ImageOps.exif_transpose(Image.open(BytesIO(logo))).convert("RGBA")
        except Exception as e:
            raise ErrorExterno("El logo no es una imagen válida.") from e
        marca.thumbnail((260, 130), Image.Resampling.LANCZOS)
        relleno = 22
        placa = [MARGEN - relleno, MARGEN - relleno, MARGEN + marca.width + relleno, MARGEN + marca.height + relleno]
        d.rounded_rectangle(placa, radius=18, fill=(255, 255, 255, 240))
        base.alpha_composite(marca, (MARGEN, MARGEN))

    salida = BytesIO()
    base.convert("RGB").save(salida, "JPEG", quality=90, optimize=True)
    return salida.getvalue()
