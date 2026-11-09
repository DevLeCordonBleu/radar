# -*- coding: utf-8 -*-
"""
Anuncios INVENTADOS de escuelas de cocina ficticias, ya clasificados.

Sirven para ver el informe sin claves ni gasto y para probar el calculo con
datos conocidos. Ningun nombre ni texto corresponde a una empresa real.
La semilla es fija: el informe de ejemplo sale siempre igual.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from . import informe as calculo, taxonomia as tx

HOY = datetime(2026, 10, 13, tzinfo=timezone.utc)

# (nombre, nivel, cuantos anuncios, perfil)
ANUNCIANTES = [
    ("Escuela Sabor Andino", 1, 14, "titulo"),
    ("Instituto Mesa Abierta", 1, 11, "prueba"),
    ("Casa del Chef Lima", 2, 9, "carrera"),
    ("Taller Fuego y Masa", 2, 8, "practica"),
    ("Academia Aroma Sur", 3, 7, "precio"),
    ("Cocina Nativa Perú", 4, 6, "carrera"),
    ("Pastelería Dulce Escuela", 3, 5, "practica"),
    ("Mi Escuela", 1, 4, "practica"),
]

PERFILES = {
    "titulo": dict(angulos=["titulación internacional", "aprender con chefs"], beneficios=["prestigio", "reconocimiento profesional"],
                   oferta="disponibilidad_abierta", cta="inscribirse", hook="beneficio_directo", visual=["produccion_profesional", "instalaciones"]),
    "prueba": dict(angulos=["probar antes de decidir", "clases prácticas"], beneficios=["perder el miedo", "disfrutar cocinando"],
                   oferta="primera_gratis", cta="reservar", hook="pregunta_directa", visual=["servicio_en_uso", "grupo_personas"]),
    "carrera": dict(angulos=["salida laboral", "aprender con chefs"], beneficios=["empleo", "emprender tu negocio"],
                    oferta="producto_curso", cta="mas_info", hook="problema_cliente", visual=["persona_camara", "texto_sobre_imagen"]),
    "practica": dict(angulos=["clases prácticas", "grupos reducidos"], beneficios=["aprender haciendo", "disfrutar cocinando"],
                     oferta="pack_intensivo", cta="inscribirse", hook="demostracion", visual=["servicio_en_uso", "montaje_momentos"]),
    "precio": dict(angulos=["precio accesible", "facilidades de pago"], beneficios=["ahorrar", "empezar ya"],
                   oferta="descuento", cta="contactar", hook="urgencia", visual=["texto_sobre_imagen", "ugc"]),
}

TITULARES = {
    "beneficio_directo": "Conviértete en chef con titulación internacional",
    "pregunta_directa": "¿Y si pruebas una clase antes de decidir?",
    "problema_cliente": "¿Cansado de un trabajo sin futuro?",
    "demostracion": "Mira cómo se hace una masa madre en 5 minutos",
    "urgencia": "Últimas vacantes: matrícula con descuento hasta el viernes",
}

TERRITORIOS = [
    {"nombre": "Una titulación que abre puertas", "tipo": "funcional", "etiquetas": ["titulación internacional", "prestigio", "reconocimiento profesional"]},
    {"nombre": "Aprender de los mejores", "tipo": "emocional", "etiquetas": ["aprender con chefs"]},
    {"nombre": "Probar sin comprometerte", "tipo": "funcional", "etiquetas": ["probar antes de decidir", "perder el miedo"]},
    {"nombre": "Cocinar con las manos", "tipo": "funcional", "etiquetas": ["clases prácticas", "grupos reducidos", "aprender haciendo"]},
    {"nombre": "Vivir de lo que te gusta", "tipo": "funcional", "etiquetas": ["salida laboral", "empleo", "emprender tu negocio"]},
    {"nombre": "Disfrutar el proceso", "tipo": "emocional", "etiquetas": ["disfrutar cocinando"]},
    {"nombre": "Pagar lo justo", "tipo": "funcional", "etiquetas": ["precio accesible", "facilidades de pago", "ahorrar", "empezar ya"]},
]


PLATAFORMAS_EJEMPLO = (["facebook", "instagram"], ["facebook", "instagram", "audience_network"], ["instagram"],
                       ["facebook", "instagram"], ["facebook"], ["facebook", "instagram", "whatsapp"])


def anuncios(semilla: int = 7) -> list[dict]:
    r = random.Random(semilla)
    salida = []
    n = 0
    for idx, (nombre, nivel, cuantos, perfil) in enumerate(ANUNCIANTES):
        p = PERFILES[perfil]
        for i in range(cuantos):
            n += 1
            # Algunos anuncios se salen del perfil: asi no todo es 100 % o 0 %.
            varia = r.random() < 0.25
            angulos = p["angulos"] if not varia else [r.choice(list(PERFILES.values()))["angulos"][0]]
            hook = p["hook"] if not varia else "beneficio_directo"
            dias = r.choice([5, 12, 30, 45, 75, 95, 140, 210]) if i < 3 else r.randint(2, 80)
            inicio = (HOY - timedelta(days=dias)).date().isoformat()
            texto = TITULARES.get(hook, TITULARES["beneficio_directo"])
            salida.append({
                "ad_id": f"{900000 + n}", "anunciante": nombre, "page_id": f"p{idx}",
                "nivel": nivel, "fecha_inicio": inicio, "activo": True,
                "copy": f"{texto}. Más información por mensaje directo.", "cta_texto": None,
                "formato": r.choices(list(tx.FORMATOS), weights=[5, 4, 1])[0],
                "hook_estructura": hook, "hook_literal": texto,
                "oferta_tipo": p["oferta"] if not varia else "sin_oferta",
                "cta_tipo": p["cta"], "patron_visual": p["visual"],
                "angulos_libres": angulos, "beneficios_libres": p["beneficios"],
                "precio_visible": perfil == "precio", "marca_en_3s": True, "subtitulos": False,
                "duracion_seg": None, "relevante": True,
                # Sin tocar el azar: el resto del ejemplo no cambia.
                "plataformas": PLATAFORMAS_EJEMPLO[n % len(PLATAFORMAS_EJEMPLO)],
            })
    return salida


def informe() -> dict:
    return calculo.construir(anuncios(), TERRITORIOS, mis_marcas=["Mi Escuela"], hoy=HOY)
