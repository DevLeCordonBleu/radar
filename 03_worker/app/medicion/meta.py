# -*- coding: utf-8 -*-
"""
Rendimiento de los anuncios propios (Meta Marketing API, solo lectura).

Token: el de la integracion de Marketing (usuario de sistema con `ads_read`), en
META_ACCESS_TOKEN; la cuenta publicitaria en META_AD_ACCOUNT (act_...). Nunca se escribe
en la cuenta: solo se leen la cuenta y sus insights.

Resultados: la cuenta tiene dos tipos y no se suman sin decirlo:
- leads: formularios de Lead Ads (accion `lead`);
- conversaciones: chats de WhatsApp/Messenger iniciados (`onsite_conversion.messaging_conversation_started_7d`).
"""
from __future__ import annotations

import os
import time
from datetime import date, timedelta
from typing import Callable

import httpx

from app.compartido.errores import ErrorExterno

API = "https://graph.facebook.com/v23.0"
CAMPOS = ("date_start,campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name,objective,spend,impressions,reach,"
          "frequency,clicks,inline_link_clicks,actions")
LEAD = "lead"
CONVERSACION = "onsite_conversion.messaging_conversation_started_7d"
VISITA = "landing_page_view"
# Ventanas cortas: una peticion por tramo, sin trabajos asincronos.
DIAS_POR_TRAMO = 10
MAX_DIAS = 400

_http: Callable[[], httpx.Client] = lambda: httpx.Client(timeout=90)  # noqa: E731


def _env(clave: str) -> str:
    return os.environ.get(clave, "").strip()


def configurado() -> dict:
    """Que falta, sin revelar nada."""
    faltan = [c for c in ("META_ACCESS_TOKEN", "META_AD_ACCOUNT") if not _env(c)]
    return {"completo": not faltan, "faltan": faltan, "cuenta": _env("META_AD_ACCOUNT") or None}


def _exigir():
    c = configurado()
    if not c["completo"]:
        raise ErrorExterno("Falta conectar Meta: completa " + ", ".join(c["faltan"]) + " en 03_worker/.env.")


def traducir_error(estado: int, cuerpo: dict | str) -> str:
    e = cuerpo.get("error", {}) if isinstance(cuerpo, dict) else {}
    codigo, mensaje = e.get("code"), e.get("message") or str(cuerpo)[:200]
    if codigo == 190 or estado == 401:
        return "Meta rechazó el token (vencido o revocado). Pide a Marketing uno nuevo y ponlo en META_ACCESS_TOKEN."
    if codigo in (10, 200) or estado == 403:
        return f"El token no tiene permiso sobre {_env('META_AD_ACCOUNT')} (hace falta ads_read). Detalle: {mensaje}"
    if codigo in (4, 17, 32, 613, 80000, 80004):
        return "Meta está limitando las consultas de la cuenta. Espera unos minutos y vuelve a intentar."
    if codigo == 100:
        return f"Meta no reconoce la consulta o la cuenta {_env('META_AD_ACCOUNT')}: {mensaje}"
    return f"Meta respondió {estado}: {mensaje}"


def _pedir(c: httpx.Client, url: str, params: dict | None = None) -> dict:
    cab = {"Authorization": f"Bearer {_env('META_ACCESS_TOKEN')}"}
    for intento in range(3):
        try:
            r = c.get(url, params=params, headers=cab)
        except httpx.HTTPError as e:
            raise ErrorExterno(f"No se pudo contactar con Meta: {type(e).__name__}") from e
        try:
            cuerpo = r.json()
        except ValueError:
            cuerpo = r.text
        if r.is_success and isinstance(cuerpo, dict):
            return cuerpo
        limitado = isinstance(cuerpo, dict) and cuerpo.get("error", {}).get("code") in (4, 17, 32, 613, 80000, 80004)
        if (limitado or r.status_code >= 500) and intento < 2:
            time.sleep(3 * (intento + 1))
            continue
        raise ErrorExterno(traducir_error(r.status_code, cuerpo))
    raise ErrorExterno("Meta no respondió.")


def cuenta() -> dict:
    """Nombre, moneda, estado y zona horaria de la cuenta publicitaria."""
    _exigir()
    with _http() as c:
        d = _pedir(c, f"{API}/{_env('META_AD_ACCOUNT')}", {"fields": "name,currency,account_status,timezone_name"})
    return {"id": _env("META_AD_ACCOUNT"), "nombre": d.get("name"), "moneda": d.get("currency"),
            "activa": d.get("account_status") == 1, "zona": d.get("timezone_name")}


def _accion(acciones: list[dict] | None, tipo: str) -> int:
    for a in acciones or []:
        if a.get("action_type") == tipo:
            try:
                return int(float(a.get("value") or 0))
            except (TypeError, ValueError):
                return 0
    return 0


def _num(v, tipo=float):
    try:
        return tipo(float(v))
    except (TypeError, ValueError):
        return tipo(0)


def normalizar(fila: dict) -> dict:
    """Una fila diaria de un anuncio, con nombres en espanol y los resultados separados."""
    acciones = fila.get("actions")
    return {
        "fecha": fila.get("date_start"), "campana_id": fila.get("campaign_id"), "campana": fila.get("campaign_name") or "",
        "conjunto_id": fila.get("adset_id"), "conjunto": fila.get("adset_name") or "", "anuncio_id": fila.get("ad_id"),
        "anuncio": fila.get("ad_name") or "", "objetivo": fila.get("objective") or "",
        "gasto": round(_num(fila.get("spend")), 2), "impresiones": _num(fila.get("impressions"), int),
        "alcance": _num(fila.get("reach"), int), "clics": _num(fila.get("clicks"), int),
        "clics_enlace": _num(fila.get("inline_link_clicks"), int), "leads": _accion(acciones, LEAD),
        "conversaciones": _accion(acciones, CONVERSACION), "visitas": _accion(acciones, VISITA),
    }


def tramos(desde: date, hasta: date, dias: int = DIAS_POR_TRAMO) -> list[tuple[date, date]]:
    salida, d = [], desde
    while d <= hasta:
        fin = min(hasta, d + timedelta(days=dias - 1))
        salida.append((d, fin))
        d = fin + timedelta(days=1)
    return salida


def insights(desde: str, hasta: str) -> dict:
    """Rendimiento diario por anuncio entre dos fechas (AAAA-MM-DD, incluidas). -> {cuenta, filas, desde, hasta}"""
    _exigir()
    d0, d1 = date.fromisoformat(desde), date.fromisoformat(hasta)
    if d1 < d0:
        raise ErrorExterno("La fecha final es anterior a la inicial.")
    if (d1 - d0).days > MAX_DIAS:
        raise ErrorExterno(f"Como mucho {MAX_DIAS} días por consulta.")
    filas: list[dict] = []
    with _http() as c:
        for a, b in tramos(d0, d1):
            params = {"level": "ad", "time_increment": 1, "fields": CAMPOS, "limit": 500,
                      "time_range": f'{{"since":"{a.isoformat()}","until":"{b.isoformat()}"}}'}
            url: str | None = f"{API}/{_env('META_AD_ACCOUNT')}/insights"
            while url:
                d = _pedir(c, url, params)
                filas += [normalizar(f) for f in d.get("data", [])]
                # La siguiente pagina ya trae todos los parametros.
                url, params = d.get("paging", {}).get("next"), None
    return {"cuenta": _env("META_AD_ACCOUNT"), "desde": desde, "hasta": hasta, "filas": filas}
