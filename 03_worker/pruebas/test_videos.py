# -*- coding: utf-8 -*-
"""
Pruebas de los videos sin IA ni Vids (gratis):
    python -m pruebas.test_videos

Gemini se sustituye por respuestas preparadas; Vids no se toca (el navegador se busca en un
puerto donde no hay nada). El recorte se prueba con un video de colores hecho con ffmpeg.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.compartido.errores import ErrorExterno
from app.videos import guion, vids

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


CONTEXTO = {
    "negocio": "Instituto Le Cordon Bleu Perú", "datos": "Lema: Tu estándar es el mundo",
    "personaje": "Un chef peruano de unos 40 años, chaqueta blanca lisa.",
    "estilo": "Cocina profesional moderna con alumnos al fondo.",
    "voz": "en español con acento peruano, con tono cercano",
    "pronunciaciones": [{"texto": "Le Cordon Bleu", "dice": "Le Cordón Blé"}],
}


def probar_partes_y_pronunciacion():
    print("partes y pronunciación")
    comprobar("45 s son 5 clips de 10 s", guion.numero_partes(45) == 5)
    comprobar("10 s es 1 clip y 60 s son 6", guion.numero_partes(10) == 1 and guion.numero_partes(60) == 6)
    comprobar("fuera de rango se acota (de 10 a 60 s)", guion.numero_partes(5) == 1 and guion.numero_partes(200) == 6)
    texto = guion.pronunciar("Estudia en LE CORDON BLEU. Le Cordon Bleus no.", CONTEXTO["pronunciaciones"])
    comprobar("la voz dice «Le Cordón Blé», sin distinguir mayúsculas", texto.startswith("Estudia en Le Cordón Blé."), texto)
    comprobar("no toca una palabra que solo la contiene", "Le Cordon Bleus" in texto, texto)


def probar_prompts():
    print("prompts de cada clip")
    partes = [{"dialogo": "¿Quieres ser chef? Estudia en Le Cordon Bleu.", "escena": "Sonríe a la cámara."},
              {"dialogo": "Te esperamos.", "escena": "Señala la cocina."}]
    p = guion.prompts(partes, "VERTICAL", CONTEXTO)
    comprobar("un prompt por parte", len(p) == 2)
    comprobar("el primero describe formato, lugar, personaje y voz",
              "formato vertical" in p[0] and "alumnos al fondo" in p[0] and "chaqueta blanca lisa" in p[0] and "acento peruano" in p[0], p[0])
    comprobar("el diálogo va entre comillas y con la pronunciación", '"¿Quieres ser chef? Estudia en Le Cordón Blé."' in p[0], p[0])
    comprobar("los siguientes piden el mismo personaje y la misma voz", p[1].startswith("El mismo personaje") and "misma voz" in p[1], p[1])
    comprobar("todos piden sin texto ni logos", all("Sin texto en pantalla" in x and "sin logos" in x for x in p))
    comprobar("horizontal también se configura", "formato horizontal" in guion.prompts(partes[:1], "HORIZONTAL", CONTEXTO)[0])
    comprobar("sin puntos dobles", all(".." not in x for x in p), p[0])


def probar_guion():
    print("guion con Gemini simulado")
    original = guion.gemini.generar
    respuesta = {"titulo": "Chef profesional", "copy_facebook": "Texto FB", "copy_instagram": "Texto IG",
                 "hashtags": ["LeCordonBleuPeru", "#Gastronomía", "#gastronomía!", "#Gastronomía"],
                 "partes": [{"dialogo": f"Frase {i}", "escena": f"Escena {i}"} for i in range(6)]}
    vistos = {}

    def falso(sistema, partes, esquema, **k):
        vistos["sistema"], vistos["texto"] = sistema, partes[0]["text"]
        return respuesta, {"llamadas": 1, "costo_usd": 0.001}
    guion.gemini.generar = falso
    try:
        g = guion.guion("Por qué estudiar cocina", 45, keyword="estudiar cocina en lima", contexto=CONTEXTO)
        comprobar("pide 5 partes y dice cuánto dura la última", "PARTES: 5 (la última dura 5 segundos)" in vistos["texto"], vistos["texto"])
        comprobar("le pasa los datos confirmados y el negocio", "Tu estándar es el mundo" in vistos["texto"] and "Instituto Le Cordon Bleu Perú" in vistos["sistema"])
        comprobar("se queda con 5 partes aunque traiga 6", len(g["partes"]) == 5)
        comprobar("hashtags con # y sin repetidos ni símbolos", g["hashtags"] == ["#LeCordonBleuPeru", "#Gastronomía", "#gastronomía"], str(g["hashtags"]))
        comprobar("devuelve copys y uso", g["copy_facebook"] == "Texto FB" and g["copy_instagram"] == "Texto IG" and g["uso"]["llamadas"] == 1)
        respuesta["partes"] = respuesta["partes"][:2]
        e = lanza(lambda: guion.guion("Idea", 45, contexto=CONTEXTO))
        comprobar("si trae menos partes, error claro", e is not None and "2 partes de 5" in e, str(e))
    finally:
        guion.gemini.generar = original


def probar_vids_sin_navegador():
    print("Vids sin navegador")
    puerto = vids.PUERTO
    vids.PUERTO = 9   # nada escucha aqui
    try:
        comprobar("detecta que el Chrome de Vids no está abierto", vids.navegador() == {"abierto": False, "vids": False, "sesion": None})
        e = lanza(lambda: vids.lanzar("t", ["p"], "VERTICAL", 10))
        comprobar("no lanza sin el navegador y explica qué hacer", e is not None and "Abrir Chrome de Vids" in e, str(e))
        comprobar("un trabajo desconocido lo dice", vids.consultar("nope")["estado"] == "desconocido")
        comprobar("no entrega un archivo que no existe", lanza(lambda: vids.archivo("nope")) is not None)
    finally:
        vids.PUERTO = puerto


def probar_recorte():
    print("recorte a la duración pedida")
    if not shutil.which("ffmpeg"):
        print("  (sin ffmpeg: se omite)")
        return
    ruta = Path(tempfile.mkdtemp()) / "prueba.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=180x320:d=20", "-f", "lavfi",
                    "-i", "sine=f=440:d=20", "-shortest", "-c:v", "libx264", "-c:a", "aac", str(ruta)], check=True)
    duracion = vids._recortar(ruta, 15)
    comprobar("un video de 20 s pedido de 15 queda en 15", duracion is not None and abs(duracion - 15) < 0.3, str(duracion))
    comprobar("si ya mide lo pedido no lo toca", abs(vids._recortar(ruta, 15) - duracion) < 0.01)


if __name__ == "__main__":
    probar_partes_y_pronunciacion()
    probar_prompts()
    probar_guion()
    probar_vids_sin_navegador()
    probar_recorte()
    print("\nTODO OK" if not fallos else f"\n{fallos} FALLOS")
