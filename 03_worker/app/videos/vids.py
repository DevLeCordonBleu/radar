# -*- coding: utf-8 -*-
"""
Genera un video en Google Vids con el Chrome de la persona: un clip con «Crear» y el resto con
«Extender», que mantiene personaje y voz. Vids devuelve cada extension ya unida a lo anterior,
asi que basta con descargar la ultima.

Se conecta por CDP a un Chrome con su propio perfil (`datos/chrome-vids`), donde la persona
inicio sesion a mano. Va a ritmo de persona, una generacion cada vez, y se detiene si Google
pide una verificacion: no se disfraza el navegador ni se resuelven CAPTCHAs. Comprobado con Vids
el 2026-10-30 (modelo Omni, 720p, clip de 10 s en ~45 s, extension en ~2 min). Si Google cambia la
pantalla, el arreglo va aqui: los nombres de los botones estan en las constantes.

Playwright es por hilo: cada trabajo abre su conexion en su propio hilo.
"""
from __future__ import annotations

import base64
import json
import os
import random
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import uuid
from pathlib import Path

from app.compartido.errores import ErrorExterno

PUERTO = int(os.environ.get("VIDS_PUERTO", "9222"))
PERFIL = Path(__file__).resolve().parents[2] / "datos" / "chrome-vids"
INICIO = "https://docs.google.com/videos/u/0/"
CHROME = [r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
          os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")]

# Lo que se lee en la pantalla de Vids (en espanol).
B_VIDEO_NUEVO = "Video sin contenido"
B_NOMBRE = "Cambiar el nombre"
B_PANEL_CLIP = "Generar un clip de video con IA"
B_EXPANDIR = "Expandir"
B_AJUSTES = "Generation settings"
B_GENERAR = "Generar"
B_EXTENDER = "Extender"
CAJA_CREAR = "Describe tu video"
CAJA_EXTENDER = "Crea un video y describe lo que debería suceder a continuación"
VERIFICACION = ("captcha", "verifica que eres", "actividad inusual", "unusual traffic")

ESPERA_CLIP_S = 8 * 60

_trabajos: dict[str, dict] = {}
_cerrojo = threading.Lock()


# ── Navegador ─────────────────────────────────────────────────────────────

def _cdp(ruta: str):
    with urllib.request.urlopen(f"http://127.0.0.1:{PUERTO}{ruta}", timeout=3) as r:
        return json.loads(r.read())


def navegador() -> dict:
    """Si el Chrome de Vids esta abierto y si tiene una pestana de Vids (o de inicio de sesion)."""
    try:
        version = _cdp("/json/version").get("Browser")
        pestanas = [p.get("url", "") for p in _cdp("/json/list") if p.get("type") == "page"]
    except OSError:
        return {"abierto": False, "vids": False, "sesion": None}
    return {"abierto": True, "version": version, "vids": any("docs.google.com/videos" in u for u in pestanas),
            "sesion": False if any("accounts.google.com" in u for u in pestanas) else None}


def abrir_navegador() -> dict:
    """Abre (si no lo esta) un Chrome aparte con el perfil del Radar, en la pagina de Vids."""
    if navegador()["abierto"]:
        return navegador()
    exe = next((c for c in CHROME if os.path.exists(c)), None)
    if not exe:
        raise ErrorExterno("No encontré Google Chrome instalado en este equipo.")
    PERFIL.mkdir(parents=True, exist_ok=True)
    subprocess.Popen([exe, f"--remote-debugging-port={PUERTO}", f"--user-data-dir={PERFIL}", "--no-first-run", INICIO],
                     creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
    for _ in range(20):
        time.sleep(0.5)
        if navegador()["abierto"]:
            break
    return navegador()


# ── Trabajos ──────────────────────────────────────────────────────────────

def lanzar(titulo: str, prompts: list[str], formato: str, segundos: int) -> dict:
    if not navegador()["abierto"]:
        raise ErrorExterno("El Chrome de Vids no está abierto: pulsa «Abrir Chrome de Vids» e inicia sesión en él.")
    with _cerrojo:
        if any(t["estado"] == "corriendo" for t in _trabajos.values()):
            raise ErrorExterno("Ya hay un video generándose en Vids: espera a que termine.")
        id_ = uuid.uuid4().hex[:12]
        _trabajos[id_] = {"estado": "corriendo", "hecho": 0, "total": len(prompts), "mensaje": "Abriendo Vids…",
                          "error": None, "url": None, "archivo": None, "segundos": None, "abortar": False}
    threading.Thread(target=_correr, args=(id_, titulo, prompts, formato, segundos), daemon=True).start()
    return {"id": id_}


def consultar(id_: str) -> dict:
    t = _trabajos.get(id_)
    if not t:
        return {"estado": "desconocido", "error": "El worker no conoce este trabajo (¿se reinició?)."}
    return {k: v for k, v in t.items() if k not in ("archivo", "abortar")}


def abortar(id_: str) -> dict:
    if id_ in _trabajos:
        _trabajos[id_]["abortar"] = True
    return consultar(id_)


def archivo(id_: str) -> dict:
    """El MP4 terminado, en base64. Se entrega una vez: luego se borra."""
    t = _trabajos.get(id_)
    if not t or t["estado"] != "listo" or not t.get("archivo"):
        raise ErrorExterno("Ese video no está listo o ya se entregó.")
    ruta = Path(t["archivo"])
    datos = base64.b64encode(ruta.read_bytes()).decode()
    ruta.unlink(missing_ok=True)
    _trabajos.pop(id_, None)
    return {"datos_b64": datos, "segundos": t.get("segundos"), "url": t.get("url")}


class _Abortado(Exception):
    pass


def _correr(id_: str, titulo: str, prompts: list[str], formato: str, segundos: int):
    t = _trabajos[id_]
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            pg = _pestana(p.chromium.connect_over_cdp(f"http://127.0.0.1:{PUERTO}"))
            _nuevo_video(pg, titulo, t)
            t["url"] = pg.url
            fuente = None
            for i, prompt in enumerate(prompts):
                _comprobar(pg, t)
                t["mensaje"] = f"Generando el clip {i + 1} de {len(prompts)}…"
                fuente = _crear(pg, prompt, formato) if i == 0 else _extender(pg, fuente, prompt)
                t["hecho"] = i + 1
            t["mensaje"] = "Descargando el video…"
            r = pg.context.request.get(fuente, timeout=180_000)
            if not r.ok:
                raise ErrorExterno(f"Vids no entregó el video (HTTP {r.status}).")
            ruta = Path(tempfile.gettempdir()) / f"radar-vids-{id_}.mp4"
            ruta.write_bytes(r.body())
        t["segundos"] = _recortar(ruta, segundos)
        t.update(estado="listo", archivo=str(ruta), mensaje="Listo")
    except _Abortado:
        t.update(estado="cancelado", mensaje="Cancelado")
    except ErrorExterno as e:
        t.update(estado="error", error=str(e), mensaje="Detenido")
    except Exception as e:  # noqa: BLE001
        t.update(estado="error", error=f"Fallo inesperado en Vids: {e}", mensaje="Detenido")


def _pausa(a=0.8, b=1.8):
    time.sleep(random.uniform(a, b))


def _comprobar(pg, t):
    if t["abortar"]:
        raise _Abortado()
    if "accounts.google.com" in pg.url:
        raise ErrorExterno("El Chrome de Vids no tiene la sesión iniciada: entra a tu cuenta en esa ventana y vuelve a intentarlo.")
    cuerpo = pg.inner_text("body")[:20000].lower()
    if any(v in cuerpo for v in VERIFICACION):
        raise ErrorExterno("Google pidió una verificación en Vids: resuélvela en esa ventana y vuelve a intentarlo.")


def _pestana(navegador_cdp):
    ctx = navegador_cdp.contexts[0]
    pg = next((x for x in ctx.pages if "docs.google.com/videos" in x.url), None) or ctx.new_page()
    pg.bring_to_front()
    return pg


def _nuevo_video(pg, titulo, t):
    pg.goto(INICIO)
    pg.wait_for_load_state("domcontentloaded")
    _pausa(2, 3)
    _comprobar(pg, t)
    pg.get_by_role("button", name=B_VIDEO_NUEVO).first.click()
    pg.wait_for_url("**/videos/d/**", timeout=60_000)
    _pausa(5, 7)
    pg.get_by_role("textbox", name=B_NOMBRE).fill(titulo[:80])
    pg.keyboard.press("Enter")
    _pausa()


def _fuentes(pg) -> list[str]:
    return pg.evaluate("() => [...document.querySelectorAll('video')].map(v => v.currentSrc || v.src).filter(s => s && s.startsWith('http'))")


def _escribir(pg, caja, texto):
    caja.focus()
    pg.keyboard.type(texto, delay=random.randint(25, 45))
    _pausa(1.5, 2.5)


def _esperar_nuevo(pg, previas: list[str]) -> str:
    limite = time.time() + ESPERA_CLIP_S
    while time.time() < limite:
        time.sleep(10)
        cuerpo = pg.inner_text("body")[:20000].lower()
        if any(v in cuerpo for v in VERIFICACION):
            raise ErrorExterno("Google pidió una verificación en Vids: resuélvela en esa ventana y vuelve a intentarlo.")
        nuevas = [s for s in _fuentes(pg) if s not in previas]
        if nuevas:
            time.sleep(3)
            return nuevas[0]
    raise ErrorExterno("Vids no terminó el clip en 8 minutos. Revisa la ventana de Vids (¿se agotaron las generaciones del mes?).")


def _crear(pg, prompt, formato) -> str:
    pg.get_by_role("button", name=B_PANEL_CLIP).first.click()
    _pausa(2, 3)
    pg.get_by_role("textbox", name=CAJA_CREAR).last.focus()
    expandir = pg.get_by_role("button", name=B_EXPANDIR)
    if expandir.count():
        expandir.first.click()
        _pausa()
    ajustes = pg.get_by_role("button", name=B_AJUSTES).first
    quiero = "Vertical" if formato.upper() == "VERTICAL" else "Horizontal"
    if quiero not in (ajustes.get_attribute("aria-label") or ""):
        ajustes.click()
        _pausa()
        pg.get_by_role("radio", name=quiero).click()
        _pausa()
        pg.keyboard.press("Escape")
        _pausa()
    estado = ajustes.get_attribute("aria-label") or ""
    if quiero not in estado or "10 segundos" not in estado:
        raise ErrorExterno(f"Vids no quedó en {quiero.lower()} y 10 segundos ({estado}). La pantalla pudo cambiar.")
    previas = _fuentes(pg)
    _escribir(pg, pg.get_by_role("textbox", name=CAJA_CREAR).last, prompt)
    pg.get_by_role("button", name=B_GENERAR, exact=True).last.click()
    return _esperar_nuevo(pg, previas)


def _extender(pg, fuente, prompt) -> str:
    # El boton «Extender» de la tarjeta del ultimo clip (no la pestana): se busca desde su <video>.
    marcado = pg.evaluate("""(src) => {
        const v = [...document.querySelectorAll('video')].find(v => (v.currentSrc || v.src) === src);
        const es = b => (b.innerText || '').trim() === 'Extender' && b.getAttribute('role') !== 'tab';
        for (let n = v; n; n = n.parentElement) {
            const b = [...n.querySelectorAll('button, [role=button]')].find(es);
            if (b) { b.setAttribute('data-radar', 'extender'); return true; }
        }
        return false; }""", fuente)
    if not marcado:
        raise ErrorExterno("No encontré el botón «Extender» del último clip en Vids. La pantalla pudo cambiar.")
    pg.locator("[data-radar=extender]").first.click()
    pg.evaluate("() => document.querySelectorAll('[data-radar]').forEach(b => b.removeAttribute('data-radar'))")
    _pausa(2, 3)
    caja = pg.get_by_role("textbox", name=CAJA_EXTENDER)
    if not caja.count():
        raise ErrorExterno("Vids no mostró el cuadro de «Extender». La pantalla pudo cambiar.")
    previas = _fuentes(pg)
    _escribir(pg, caja.last, prompt)
    pg.get_by_role("button", name=B_GENERAR, exact=True).last.click()
    return _esperar_nuevo(pg, previas)


def _duracion(ruta: Path) -> float | None:
    if not shutil.which("ffprobe"):
        return None
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ruta)],
                       capture_output=True, text=True, timeout=60)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def _recortar(ruta: Path, segundos: int) -> float | None:
    """Los clips son de 10 s: un video de 45 s sale de 50 y se recorta (con un fundido corto al final)."""
    total = _duracion(ruta)
    if total is None or total <= segundos + 0.5 or not shutil.which("ffmpeg"):
        return total
    corto = ruta.with_suffix(".corto.mp4")
    fundido = max(0.0, segundos - 0.6)
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(ruta), "-t", str(segundos),
                        "-vf", f"fade=t=out:st={fundido}:d=0.6", "-af", f"afade=t=out:st={fundido}:d=0.6",
                        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "aac", "-b:a", "160k", str(corto)],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        return total
    corto.replace(ruta)
    return _duracion(ruta)
