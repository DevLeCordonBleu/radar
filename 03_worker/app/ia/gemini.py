# -*- coding: utf-8 -*-
"""
Cliente de Gemini (Google AI Studio) con salida JSON estructurada.

Tres redes de seguridad, porque el plan gratuito es justo:
  1. varias claves: si una agota su cuota o no tiene saldo, se prueba la siguiente;
  2. varios modelos: la cuota diaria es POR MODELO, asi que al agotarse uno se
     pasa al siguiente (quedan anotados hasta que se renueva);
  3. reintentos con espera para los limites por minuto y los 5xx.
Si todo se agota lanza CuotaAgotada y el backend deja el analisis en pausa con
lo hecho guardado.
"""
from __future__ import annotations

import os
import re
import time
from datetime import datetime, timedelta, timezone

import httpx

from app.compartido.errores import CuotaAgotada, ErrorExterno

API = "https://generativelanguage.googleapis.com/v1beta"
MODELOS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3-flash-preview"]
# Modelos que acepta comprobar(): evita que una peticion elija un modelo caro.
_PERMITIDOS = re.compile(r"^gemini-(2\.5|3)(\.\d)?-flash(-lite)?(-preview)?(-\d{2}-\d{4})?$")
REINTENTOS = 5
TIMEOUT_S = 300
# Precio por millon de tokens (US$) de gemini-2.5-flash, la referencia del plan de pago.
PRECIO_ENTRADA = 0.30
PRECIO_SALIDA = 2.50

# Modelos sin cuota hasta que se renueva (medianoche de California ~ 08:00 UTC).
_agotados: dict[str, datetime] = {}


def claves() -> list[str]:
    vistas = []
    for k in ("GEMINI_API_KEY", "GEMINI_API_KEY_2"):
        v = os.environ.get(k, "").strip()
        if v and v not in vistas:
            vistas.append(v)
    return vistas


def con_pago() -> bool:
    return os.environ.get("GEMINI_PAGO", "").strip().lower() in ("1", "true", "si", "sí")


def costo_usd(tokens_entrada: int, tokens_salida: int) -> float:
    return tokens_entrada / 1e6 * PRECIO_ENTRADA + tokens_salida / 1e6 * PRECIO_SALIDA


def _renovacion() -> datetime:
    ahora = datetime.now(timezone.utc)
    r = ahora.replace(hour=8, minute=0, second=0, microsecond=0)
    return r if r > ahora else r + timedelta(days=1)


def modelos_disponibles(preferido: str | None = None) -> list[str]:
    ahora = datetime.now(timezone.utc)
    for m in [m for m, hasta in _agotados.items() if hasta <= ahora]:
        del _agotados[m]
    orden = ([preferido] if preferido else []) + [m for m in MODELOS if m != preferido]
    return [m for m in orden if m not in _agotados]


def _detalle(texto: str) -> dict:
    return {
        "gratuito": bool(re.search(r"FreeTier|free_tier", texto, re.I)),
        "por_dia": bool(re.search(r"PerDay|per day", texto, re.I)),
        "por_minuto": bool(re.search(r"PerMinute|per minute", texto, re.I)),
        "cero": bool(re.search(r'"quotaValue"\s*:\s*"0"|limit:\s*0\b', texto)),
        "saldo": bool(re.search(r"prepay|credits are depleted|spending cap|spend cap", texto, re.I)),
        "facturacion": bool(re.search(r"FAILED_PRECONDITION|billing", texto, re.I)),
    }


def _espera_sugerida(texto: str) -> float | None:
    m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', texto) or re.search(r"retry in (\d+(?:\.\d+)?)s", texto, re.I)
    return min(70.0, float(m.group(1)) + 1) if m else None


class _SinCuota(Exception):
    """Un modelo agoto su cuota diaria con todas las claves."""

    def __init__(self, modelo: str, detalle: dict):
        self.modelo, self.detalle = modelo, detalle


def _una_peticion(modelo: str, cuerpo: dict) -> tuple[int, str]:
    """Prueba cada clave hasta que una responde. Devuelve (status, texto) del mejor intento."""
    ks = claves()
    if not ks:
        raise ErrorExterno("Falta la clave de Gemini. Ponla en 03_worker/.env (GEMINI_API_KEY).")
    ultimo = (500, "")
    for i, k in enumerate(ks):
        try:
            r = httpx.post(f"{API}/models/{modelo}:generateContent", json=cuerpo,
                           headers={"x-goog-api-key": k}, timeout=TIMEOUT_S)
        except httpx.TimeoutException:
            return 504, '{"error":{"message":"tiempo de espera agotado"}}'
        except httpx.HTTPError as e:
            raise ErrorExterno(f"Se ha perdido la conexión con Google: {e}") from e
        if r.is_success:
            return r.status_code, r.text
        ultimo = (r.status_code, r.text)
        ayuda_otra = r.status_code in (401, 402, 403, 429) or (
            r.status_code == 400 and re.search(r"API key|API_KEY_INVALID|FAILED_PRECONDITION|billing", r.text, re.I))
        # Un 429 por minuto no se arregla cambiando de clave de la misma cuenta, pero cuesta poco probarlo.
        if not ayuda_otra:
            break
    return ultimo


def generar(sistema: str, partes: list[dict], esquema: dict, *, modelo: str | None = None,
            parar=None, temperatura: float = 0) -> tuple[dict, dict]:
    """
    Devuelve (json, uso). `uso` = {tokens_entrada, tokens_salida, llamadas, modelo, costo_usd}.
    `parar()` -> True aborta entre reintentos. `temperatura` 0 para clasificar; algo mas para redactar.
    """
    probados = []
    for m in modelos_disponibles(modelo):
        try:
            return _con_reintentos(m, sistema, partes, esquema, parar, temperatura)
        except _SinCuota as e:
            probados.append(e)
            _agotados[m] = _renovacion()
    if not probados:
        raise CuotaAgotada("Todos los modelos de Gemini ya agotaron su cuota de hoy. Se renueva hacia las 3:00 (hora de Perú).")
    raise _mensaje_cuota(probados)


def _mensaje_cuota(fallos: list[_SinCuota]) -> CuotaAgotada:
    if all(f.detalle["cero"] for f in fallos):
        return CuotaAgotada("Google dice que tu clave de Gemini no tiene cuota en ningún modelo (límite 0). "
                            "Pasa en el plan gratuito de algunos proyectos y regiones; activar la facturación lo resuelve.")
    if any(f.detalle["gratuito"] for f in fallos):
        return CuotaAgotada("Se agotó la cuota diaria gratuita de Gemini en todos los modelos. Vuelve mañana, usa la "
                            "clave de otro proyecto de Google o activa la facturación en aistudio.google.com. Lo analizado está guardado.")
    return CuotaAgotada("Gemini llegó a su límite diario en todos los modelos. Se renueva hacia las 3:00 (hora de Perú). "
                        "Lo analizado está guardado.")


def _con_reintentos(modelo: str, sistema: str, partes: list[dict], esquema: dict, parar, temperatura: float = 0) -> tuple[dict, dict]:
    cuerpo = {
        "system_instruction": {"parts": [{"text": sistema}]},
        "contents": [{"role": "user", "parts": partes}],
        "generationConfig": {
            "response_mime_type": "application/json", "response_schema": esquema,
            "temperature": temperatura, "max_output_tokens": 32768,
            **({"thinking_config": {"thinking_budget": 0}} if modelo.startswith("gemini-2.5") else {}),
        },
    }
    estado, texto = 0, ""
    for intento in range(REINTENTOS + 1):
        if parar and parar():
            raise ErrorExterno("Análisis parado.")
        estado, texto = _una_peticion(modelo, cuerpo)
        if 200 <= estado < 300:
            return _leer(modelo, texto)
        d = _detalle(texto)
        if d["saldo"]:
            raise CuotaAgotada("La cuenta de Google de tu clave de Gemini se ha quedado sin saldo o llegó a su tope de gasto. "
                               "Recárgala en aistudio.google.com y continúa: lo analizado está guardado.")
        if estado == 429 and (d["por_dia"] or d["cero"]):
            raise _SinCuota(modelo, d)
        if estado == 404:
            raise _SinCuota(modelo, {**d, "cero": False})
        if estado not in (429, 500, 502, 503, 504):
            break
        if intento < REINTENTOS:
            time.sleep(_espera_sugerida(texto) or 2 * 2 ** intento)
    raise _error_final(estado, texto)


def _error_final(estado: int, texto: str) -> ErrorExterno:
    if estado in (401, 403) or (estado == 400 and re.search(r"API key|API_KEY_INVALID", texto, re.I)):
        if re.search(r"leaked", texto, re.I):
            return ErrorExterno("Google ha bloqueado la clave de Gemini porque la detectó publicada en internet. Crea una nueva en aistudio.google.com.")
        return ErrorExterno("Google no acepta la clave de Gemini: ya no es válida o está restringida. Revísala en aistudio.google.com.")
    if estado == 400 and _detalle(texto)["facturacion"]:
        return ErrorExterno("Google no deja usar la clave: la facturación de su proyecto no está activa o el plan gratuito no está disponible en tu región.")
    if estado == 429:
        return ErrorExterno("Gemini está limitando las peticiones. Espera unos minutos y continúa: lo analizado está guardado.")
    if estado == 504:
        return ErrorExterno("Gemini no responde: se agotó el tiempo de espera. Lo analizado hasta aquí está guardado.")
    return ErrorExterno(f"Gemini respondió {estado}: {texto[:200]}")


def _leer(modelo: str, texto: str) -> tuple[dict, dict]:
    import json
    try:
        d = json.loads(texto)
        salida = d["candidates"][0]["content"]["parts"][0]["text"]
        datos = json.loads(salida)
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise ErrorExterno("Gemini devolvió una respuesta incompleta. Suele arreglarse volviendo a intentarlo.") from e
    u = d.get("usageMetadata") or {}
    ent, sal = u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0)
    return datos, {"tokens_entrada": ent, "tokens_salida": sal, "llamadas": 1, "modelo": modelo,
                   "costo_usd": costo_usd(ent, sal)}


def comprobar(clave: str) -> dict:
    """{ok, detalle}: valida la clave y avisa si el proyecto no tiene cuota."""
    try:
        r = httpx.get(f"{API}/models", params={"pageSize": 100}, headers={"x-goog-api-key": clave}, timeout=10)
    except httpx.HTTPError:
        return {"ok": False, "detalle": "No se ha podido contactar con Google. Prueba en un minuto."}
    if r.status_code == 403 and re.search(r"leaked", r.text, re.I):
        return {"ok": False, "detalle": "Google ha bloqueado esta clave porque la detectó publicada en internet. Crea una nueva en aistudio.google.com."}
    if r.status_code in (400, 401, 403):
        return {"ok": False, "detalle": "Google no reconoce esa clave. Cópiala otra vez desde aistudio.google.com."}
    if not r.is_success:
        return {"ok": False, "detalle": f"Google no responde ahora mismo ({r.status_code}). Prueba en un minuto."}
    flash = sum(1 for m in r.json().get("models", []) if re.search(r"gemini-.*flash", m.get("name", "")))
    base = f"Clave válida · {flash} modelos Flash disponibles" if flash else "Clave válida"
    try:
        g = httpx.post(f"{API}/models/gemini-2.5-flash-lite:generateContent", headers={"x-goog-api-key": clave}, timeout=15,
                       json={"contents": [{"parts": [{"text": "ok"}]}], "generationConfig": {"max_output_tokens": 1}})
    except httpx.HTTPError:
        return {"ok": True, "detalle": base}
    if g.is_success:
        return {"ok": True, "detalle": base}
    d = _detalle(g.text)
    if g.status_code == 402 or d["saldo"]:
        return {"ok": False, "detalle": "La clave es válida, pero su cuenta de Google no tiene saldo o llegó a su tope de gasto."}
    if g.status_code == 429 and d["cero"]:
        return {"ok": True, "detalle": f"{base} · Aviso: Google no le da cuota a este proyecto (límite 0). Activa la facturación para usarla."}
    if g.status_code == 429 and d["por_dia"]:
        return {"ok": True, "detalle": f"{base} · Hoy ya agotó su cuota en el modelo más ligero; se renueva a medianoche de California."}
    return {"ok": True, "detalle": base}
