# -*- coding: utf-8 -*-
"""
Del conjunto de anuncios clasificados al informe.

Todo es aritmetica sobre lo que ya clasifico la IA: sin red, sin costo y
determinista, asi que se prueba con datos de ejemplo (pruebas/ejemplo.py).

Idea central: cada anuncio pesa segun el nivel de su anunciante (un competidor
directo pesa mas que uno nacional) y una dimension (angulo, oferta...) se
llama "saturada" o "hueco" segun el porcentaje de peso que acumula.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from . import taxonomia as tx
from .texto import limpiar, normalizar, palabras_clave

Anuncio = dict


def frecuencia(pct: float) -> str:
    for clave, minimo in tx.FRECUENCIAS:
        if pct >= minimo:
            return clave
    return "hueco"


def peso_nivel(nivel: int) -> float:
    return tx.NIVELES.get(nivel, tx.NIVELES[3])["peso"]


def distribucion(anuncios: list[Anuncio], claves) -> list[dict]:
    """
    Porcentaje (ponderado por nivel) de anuncios que usa cada clave.
    `claves(anuncio)` devuelve las claves de ese anuncio; un anuncio puede
    tener varias, asi que los porcentajes de una dimension pueden sumar mas de 100.
    """
    total = sum(peso_nivel(a["nivel"]) for a in anuncios)
    if total == 0:
        return []
    acum: dict[str, dict] = {}
    for a in anuncios:
        p = peso_nivel(a["nivel"])
        for k in set(claves(a)):
            f = acum.setdefault(k, {"peso": 0.0, "n": 0, "quien": set()})
            f["peso"] += p
            f["n"] += 1
            f["quien"].add(a["anunciante"])
    filas = []
    for k, f in acum.items():
        pct = f["peso"] / total * 100
        filas.append({
            "clave": k, "pct": round(pct, 1), "anuncios": f["n"],
            "anunciantes": len(f["quien"]), "frecuencia": frecuencia(pct),
        })
    return sorted(filas, key=lambda f: -f["pct"])


def etiquetar(filas: list[dict], nombres: dict[str, str]) -> list[dict]:
    return [{**f, "clave": nombres.get(f["clave"], f["clave"])} for f in filas]


def veteranos(anuncios: list[Anuncio], dias_min: int, hoy: datetime) -> list[Anuncio]:
    """Anuncios activos hace mucho: la unica senal de que algo le funciona al anunciante."""
    vistos, salida = set(), []
    for a in anuncios:
        if not a.get("activo"):
            continue
        try:
            inicio = datetime.fromisoformat(a["fecha_inicio"]).replace(tzinfo=timezone.utc)
        except (ValueError, KeyError):
            continue
        dias = (hoy - inicio).days
        if dias < dias_min:
            continue
        huella = (a["anunciante"], normalizar(a.get("copy") or a.get("hook_literal") or a["ad_id"])[:140])
        if huella in vistos:
            continue
        vistos.add(huella)
        salida.append({**a, "dias_activo": dias})
    return sorted(salida, key=lambda a: -a["dias_activo"])


def aviso_muestra(n: int) -> str | None:
    if n >= tx.MUESTRA_MINIMA:
        return None
    return (f"Solo se han encontrado {n} anuncios. Por debajo de {tx.MUESTRA_MINIMA} los porcentajes "
            "son orientativos: trátalos como indicios, no como conclusiones.")


# ── Territorios ───────────────────────────────────────────────────────────

def indice_etiquetas(territorios: list[dict]) -> dict[str, str]:
    """etiqueta normalizada -> nombre del territorio (la primera que la reclama)."""
    indice: dict[str, str] = {}
    for t in territorios:
        for e in t.get("etiquetas", []):
            k = normalizar(e)
            if k and k not in indice:
                indice[k] = t["nombre"]
    return indice


def asignar(etiquetas: list[str], indice: dict[str, str]) -> tuple[list[str], list[str]]:
    """(territorios, huerfanas): cada etiqueta a su territorio; si no esta exacta, por contencion."""
    destino, huerfanas = set(), []
    for e in etiquetas:
        k = normalizar(e)
        if not k:
            continue
        if k in indice:
            destino.add(indice[k])
            continue
        mejor, largo = None, 0
        for clave, nombre in indice.items():
            if (k in clave or clave in k) and len(clave) > largo:
                mejor, largo = nombre, len(clave)
        if mejor:
            destino.add(mejor)
        else:
            huerfanas.append(k)
    return sorted(destino), huerfanas


def agrupar_sin_ia(etiquetas: list[tuple[str, str]], maximo: int = 15) -> list[dict]:
    """
    Plan B si Gemini no puede agrupar: junta etiquetas que comparten la mitad
    de sus palabras. `etiquetas` = [(texto, tipo)] con repeticiones.
    """
    cuenta: dict[str, dict] = {}
    for texto, tipo in etiquetas:
        k = normalizar(texto)
        if not k:
            continue
        f = cuenta.setdefault(k, {"n": 0, "tipo": tipo, "pal": palabras_clave(texto)})
        f["n"] += 1

    def solape(a: set, b: set) -> float:
        return sum(1 for x in a if x in b) / max(1, min(len(a), len(b)))

    grupos: list[dict] = []
    for k, f in sorted(cuenta.items(), key=lambda kv: -kv[1]["n"]):
        mejor, s = None, 0.0
        for g in grupos:
            v = solape(f["pal"], g["pal"])
            if v > s:
                mejor, s = g, v
        if mejor and s >= 0.5:
            mejor["etiquetas"].append(k)
            mejor["n"] += f["n"]
            mejor["tipos"][f["tipo"]] += f["n"]
            mejor["pal"] |= f["pal"]
        else:
            tipos = {t: 0 for t in tx.TIPOS_TERRITORIO}
            tipos[f["tipo"]] += f["n"]
            grupos.append({"etiquetas": [k], "pal": set(f["pal"]), "n": f["n"], "tipos": tipos})
    grupos.sort(key=lambda g: -g["n"])
    principales = grupos[:maximo]
    for g in grupos[maximo:]:
        mejor, s = None, 0.0
        for p in principales:
            v = solape(g["pal"], p["pal"])
            if v > s:
                mejor, s = p, v
        if mejor:
            mejor["etiquetas"].extend(g["etiquetas"])
            mejor["n"] += g["n"]
    return [{
        "nombre": g["etiquetas"][0][:1].upper() + g["etiquetas"][0][1:],
        "tipo": max(g["tipos"].items(), key=lambda kv: kv[1])[0],
        "etiquetas": g["etiquetas"],
    } for g in principales]


# ── Informe ───────────────────────────────────────────────────────────────

def _es_mia(anuncio: dict, marcas: list[str], paginas: set[str] | None) -> bool:
    """Por sus paginas si se conocen; si no (informes antiguos, ejemplo), por el nombre."""
    if paginas is not None:
        return anuncio.get("page_id") in paginas
    a = anuncio["anunciante"].lower()
    return any(m.lower() in a or a in m.lower() for m in marcas)


def construir(anuncios: list[Anuncio], territorios: list[dict], *, mis_marcas: list[str] | None = None,
              mis_paginas: list[str] | None = None, sin_anuncios: list[str] | None = None, identificadas: list[dict] | None = None,
              hoy: datetime | None = None) -> dict:
    """
    `anuncios`: ya clasificados y filtrados por relevancia, con `nivel` por anunciante.
    `mis_paginas`: las paginas de Facebook de tus marcas; con ellas tus anuncios se
    reconocen por pagina y no por parecido del nombre.
    """
    hoy = hoy or datetime.now(timezone.utc)
    marcas = [m.strip() for m in (mis_marcas or []) if m and m.strip()]
    indice = indice_etiquetas(territorios)
    tipo_de = {t["nombre"]: t["tipo"] for t in territorios}

    n_huerfanas = n_etiquetas = 0
    enriquecidos = []
    for a in anuncios:
        a = {**a, "hook_literal": limpiar(a.get("hook_literal", "")),
             "angulos_libres": a.get("angulos_libres") or [], "beneficios_libres": a.get("beneficios_libres") or []}
        t_ang, h1 = asignar(a["angulos_libres"], indice)
        t_ben, h2 = asignar(a["beneficios_libres"], indice)
        n_huerfanas += len(h1) + len(h2)
        n_etiquetas += len(a["angulos_libres"]) + len(a["beneficios_libres"])
        enriquecidos.append({**a, "territorios_angulo": t_ang, "territorios_beneficio": t_ben})

    anunciantes = {a["anunciante"] for a in anuncios}
    angulos = distribucion(enriquecidos, lambda a: a["territorios_angulo"])
    hooks = etiquetar(distribucion(anuncios, lambda a: [a["hook_estructura"]]), tx.HOOKS)
    ofertas = etiquetar(distribucion(anuncios, lambda a: [a["oferta_tipo"]]), tx.OFERTAS)
    beneficios: dict[str, list] = {t: [] for t in tx.TIPOS_TERRITORIO}
    for b in distribucion(enriquecidos, lambda a: a["territorios_beneficio"]):
        t = tipo_de.get(b["clave"])
        if t:
            beneficios[t].append(b)
    visuales = {
        "patrones": etiquetar(distribucion(anuncios, lambda a: a.get("patron_visual") or []), tx.PATRONES_VISUALES),
        "formatos": etiquetar(distribucion(anuncios, lambda a: [a["formato"]]), tx.FORMATOS),
    }
    ctas = etiquetar(distribucion(anuncios, lambda a: [a["cta_tipo"]]), tx.CTAS)

    # Angulos y ofertas juntos: es lo que el cliente ve como "lo que se dice".
    resumen = sorted(
        [{**f, "dimension": "Ángulo"} for f in angulos]
        + [{**f, "dimension": "Oferta"} for f in ofertas if f["clave"] != tx.OFERTAS["sin_oferta"]],
        key=lambda f: -f["pct"],
    )
    dominantes = [f for f in resumen if f["frecuencia"] in ("muy_alta", "alta")]
    tope = max(1, len(anunciantes) // 4)
    poco_usados = sorted(
        (f for f in resumen if f["frecuencia"] in ("baja", "hueco") and f["anunciantes"] <= tope),
        key=lambda f: f["pct"])[:6]
    huecos = sorted((f for f in resumen if f["frecuencia"] in ("hueco", "baja")), key=lambda f: f["pct"])[:6]

    por_nivel: dict[str, int] = defaultdict(int)
    for a in anuncios:
        por_nivel[tx.NIVELES.get(a["nivel"], tx.NIVELES[3])["nombre"]] += 1

    paginas = set(mis_paginas) if mis_paginas is not None else None
    mios = [a for a in enriquecidos if _es_mia(a, marcas, paginas)] if marcas else []
    mis_territorios = sorted({t for a in mios for t in a["territorios_angulo"]})
    formato_top = visuales["formatos"][0] if visuales["formatos"] else None
    prop_huerfanas = n_huerfanas / n_etiquetas if n_etiquetas else 0.0

    titulares = [{"valor": str(len(anuncios)), "etiqueta": "anuncios analizados",
                  "detalle": f"de {len(anunciantes)} anunciantes"}]
    if resumen:
        titulares.append({"valor": f"{resumen[0]['pct']:.0f} %", "etiqueta": "lo más repetido",
                          "detalle": resumen[0]["clave"]})
    if formato_top:
        titulares.append({"valor": f"{formato_top['pct']:.0f} %", "etiqueta": "formato dominante",
                          "detalle": formato_top["clave"]})
    titulares.append({"valor": str(len(huecos)), "etiqueta": "territorios poco ocupados",
                      "detalle": "ver sección 8" if huecos else "todos bastante ocupados"})

    return {
        "meta": {
            "generado": hoy.isoformat(),
            "anuncios": len(anuncios),
            "anunciantes": len(anunciantes),
            "sin_anuncios": sin_anuncios or [],
            "por_nivel": dict(por_nivel),
            "identificadas": identificadas or [],
            "aviso_muestra": aviso_muestra(len(anuncios)),
            "aviso_huerfanas": (
                f"Un {round(prop_huerfanas * 100)} % de las etiquetas no encajó en ningún territorio. "
                "El vocabulario del sector puede estar incompleto." if prop_huerfanas > 0.25 else None),
        },
        "titulares": titulares,
        "angulos": angulos,
        "hooks": {"patrones": hooks, "ejemplos": [
            {"texto": a["hook_literal"], "anunciante": a["anunciante"]}
            for a in enriquecidos if len(a["hook_literal"]) > 3]},
        "ofertas": {"patrones": ofertas,
                    "mas_usada": next((f for f in ofertas if f["clave"] != tx.OFERTAS["sin_oferta"]), None)},
        "beneficios": beneficios,
        "visuales": visuales,
        "ctas": ctas,
        "saturado": {"dominantes": dominantes, "poco_usados": poco_usados},
        "huecos": huecos,
        "resumen": resumen,
        "veteranos": veteranos(enriquecidos, tx.DIAS_VETERANO, hoy),
        "anuncios": enriquecidos,
        "territorios": territorios,
        "mi_marca": " y ".join(marcas) or None,
        "mis_anuncios": len(mios),
        "mis_paginas": sorted({a["page_id"] for a in mios if a.get("page_id")}),
        "mis_territorios": mis_territorios,
    }
