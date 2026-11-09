# -*- coding: utf-8 -*-
"""
Prueba de extremo a extremo del ciclo de un analisis, GRATIS.

Levanta un worker real pero con las tres cosas que cuestan dinero reemplazadas
por datos de ejemplo (busqueda en Apify, clasificacion y territorios de Gemini),
y un backend aislado (puerto 8092, base temporal). Comprueba por la API:
informe de ejemplo, estimacion, eleccion de una pagina ambigua, pausa por cuota
de Gemini, continuar SIN repetir lo ya pagado, terminar con lo hecho y cancelar.

    python 05_pruebas/flujo_completo.py

Requiere el jar del backend compilado (01_backend\\arrancar.bat lo compila).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "03_worker"))

PUERTO_BACKEND, PUERTO_WORKER = 8092, 8112
BASE = f"http://localhost:{PUERTO_BACKEND}/api"
fallos = 0


def comprobar(nombre: str, ok: bool, detalle: str = ""):
    global fallos
    print(("  ok    " if ok else "  FALLA ") + nombre + (f"  [{detalle}]" if detalle and not ok else ""))
    fallos += 0 if ok else 1


# ── Worker con lo caro simulado ───────────────────────────────────────────

def worker_simulado():
    import uvicorn
    from app.analisis import ejemplo
    from app.compartido.errores import CuotaAgotada
    from app.ia import clasificar
    from app import fuentes
    from app.main import app

    # app.main carga el .env real: la prueba no usa ni gasta las credenciales de Google Ads.
    for clave in [k for k in os.environ if k.startswith("GOOGLE_ADS_")]:
        os.environ.pop(clave)

    # Videos: ni Gemini ni Google Vids. El trabajo de Vids pasa por «corriendo» y luego queda listo.
    from app.videos import guion as vguion, vids
    import base64
    video_trabajos: dict = {}

    def guion_video(idea, segundos, keyword="", contexto=None, modelo=None):
        estado["video_contexto"] = contexto
        partes = [{"dialogo": f"Estudia en Le Cordon Bleu: {idea}, parte {i + 1}.", "escena": "Sonríe a la cámara."}
                  for i in range(vguion.numero_partes(segundos))]
        return {"titulo": idea[:60], "partes": partes, "copy_facebook": "Copy de Facebook", "copy_instagram": "Copy de Instagram",
                "hashtags": ["#LeCordonBleuPeru"], "uso": {"tokens_entrada": 500, "tokens_salida": 200, "llamadas": 1, "modelo": "simulado", "costo_usd": 0.001}}

    def lanzar_video(titulo, prompts, formato, segundos):
        estado["video_lanzado"] = {"titulo": titulo, "prompts": prompts, "formato": formato, "segundos": segundos}
        id_ = f"trabajo{len(video_trabajos) + 1}"
        video_trabajos[id_] = 0
        return {"id": id_}

    def consultar_video(id_):
        if id_ not in video_trabajos:
            return {"estado": "desconocido"}
        video_trabajos[id_] += 1
        return {"estado": "corriendo", "mensaje": "Generando el clip 1 de 2…"} if video_trabajos[id_] < 2 else {"estado": "listo"}

    vguion.guion = guion_video
    vids.navegador = lambda: {"abierto": True, "vids": True, "sesion": None}
    vids.abrir_navegador = vids.navegador
    vids.lanzar = lanzar_video
    vids.consultar = consultar_video
    vids.archivo = lambda id_: {"datos_b64": base64.b64encode(MP4_PRUEBA).decode(), "segundos": 20.0, "url": "https://docs.google.com/videos/d/prueba/edit"}

    # Publicaciones: un texto por red sin Gemini; LinkedIn trae un dato por completar.
    from app.publicaciones import textos as ptextos

    def textos_publicacion(idea, redes, media="NINGUNA", modo="POR_RED", hashtags_base=None, contexto=None, modelo=None):
        estado["pub_pedido"] = {"redes": redes, "media": media, "modo": modo, "hashtags_base": hashtags_base, "contexto": contexto}
        if modo == "MISMO":
            t = {r: f"Texto común: {idea}" for r in redes}
        else:
            t = {r: f"Texto de {r.capitalize()}: {idea}" for r in redes}
            if "LINKEDIN" in t:
                t["LINKEDIN"] += " Empieza [FALTA: fecha de inicio]."
        return {"titulo": idea[:60], "textos": t, "hashtags": list(dict.fromkeys((hashtags_base or []) + ["#Chef"])),
                "flyer": {"titulo": "Ven y conoce el campus", "detalle": "[FALTA: fecha]", "cta": "Inscríbete", "busqueda": "chef cocina",
                          "fondo": "Una cocina luminosa"},
                "uso": {"tokens_entrada": 300, "tokens_salida": 150, "llamadas": 1, "modelo": "simulado", "costo_usd": 0.001}}
    ptextos.textos = textos_publicacion

    # Si el post sigue en su red: la de LinkedIn «ya no está»; el resto, segun estado["enlaces_activos"].
    from app.publicaciones import verificar as pverificar

    def verificar_enlaces(enlaces, textos=None, **k):
        estado["verificados"] = {"enlaces": enlaces, "textos": textos}
        return {"resultados": {r: {"estado": "NO_DISPONIBLE" if r == "LINKEDIN" else "ACTIVA", "detalle": "simulado", "http": 200} for r in enlaces}}
    pverificar.verificar = verificar_enlaces

    # El flyer se arma con Pillow en test_publicaciones; aqui se comprueba que le llega lo correcto.
    from app.publicaciones import flyer as pflyer

    def componer_flyer(fondo, titulo, detalle="", cta="", logo=None, color="#0B1F3F", acento="#C9A55A"):
        estado["flyer_llamadas"] = estado.get("flyer_llamadas", 0) + 1
        estado["flyer"] = {"fondo": fondo, "titulo": titulo, "detalle": detalle, "cta": cta, "logo": logo, "color": color, "acento": acento}
        return FLYER_PRUEBA
    pflyer.componer = componer_flyer

    reales = ejemplo.anuncios()
    items = [{
        "ad_archive_id": a["ad_id"], "page_name": a["anunciante"], "page_id": a["page_id"],
        "start_date": a["fecha_inicio"], "is_active": True, "publisher_platform": [p.upper() for p in a["plataformas"]],
        "snapshot": {"display_format": "VIDEO" if a["formato"] == "video" else "IMAGE", "body": {"text": a["copy"]},
                     "videos": [{"video_hd_url": f"https://ejemplo.invalid/{a['ad_id']}.mp4"}] if a["formato"] == "video" else [],
                     "images": [{"original_image_url": f"https://ejemplo.invalid/{a['ad_id']}.jpg"}]},
    } for a in reales]
    # Dos paginas con casi el mismo nombre: obliga a preguntar cual es.
    for i, ciudad in enumerate(("Lima", "Cusco")):
        for j in range(3):
            items.append({"ad_archive_id": f"8{i}{j}", "page_name": f"Fogón {ciudad}", "page_id": f"880000001{i}",
                          "start_date": "2026-09-01", "is_active": True,
                          "snapshot": {"display_format": "IMAGE", "body": {"text": "Clases de cocina"}}})

    estado = {"llamadas_clasificar": 0, "ids_clasificados": [], "cuota_en": None}
    por_id = {a["ad_id"]: a for a in reales}

    def lanzar(terminos, pais="PE", maximo=100, solo_activos=True):
        estado["terminos"] = terminos
        return {"run": "RUNSIMULADO1", "t": 0, "agotados": []}

    def consultar(run, t):
        if estado.get("anuncios_terminados"):
            # Todos ya terminados y de 2019: para la fecha minima del analisis.
            return {"estado": "listo", "items": [{**i, "is_active": False, "start_date": "2019-01-01"} for i in items]}
        return {"estado": "listo", "items": items}

    def clasificar_falso(anuncios, **extra):
        estado["referencia"] = extra.get("referencia")
        estado["llamadas_clasificar"] += 1
        if estado["cuota_en"] and estado["llamadas_clasificar"] == estado["cuota_en"]:
            estado["cuota_en"] = None
            raise CuotaAgotada("Se agotó la cuota diaria gratuita de Gemini en todos los modelos.")
        salida = []
        for a in anuncios:
            estado["ids_clasificados"].append(a["ad_id"])
            c = por_id.get(a["ad_id"])
            if c:
                salida.append({k: c[k] for k in ("ad_id", "hook_estructura", "hook_literal", "oferta_tipo", "cta_tipo", "formato",
                                                "patron_visual", "angulos_libres", "beneficios_libres", "precio_visible",
                                                "marca_en_3s", "subtitulos", "duracion_seg", "relevante")})
            else:
                salida.append({"ad_id": a["ad_id"], "hook_estructura": "otro", "hook_literal": "", "oferta_tipo": "sin_oferta",
                               "cta_tipo": "otro", "formato": "estatica", "patron_visual": [], "angulos_libres": ["clases prácticas"],
                               "beneficios_libres": [], "precio_visible": False, "marca_en_3s": False, "subtitulos": False,
                               "duracion_seg": None, "relevante": True})
        uso = {"tokens_entrada": 1000, "tokens_salida": 100, "llamadas": 1, "modelo": "simulado", "costo_usd": 0.002}
        return {"clasificaciones": salida, "uso": uso, "medios_fallidos": 0, "sin_medio": []}

    def territorios_falso(etiquetas, **_):
        return {"territorios": ejemplo.TERRITORIOS, "uso": {"tokens_entrada": 100, "tokens_salida": 50, "llamadas": 1,
                                                            "modelo": "simulado", "costo_usd": 0.0005}}

    # ── Plan SEO: sitio y IA simulados ──
    from app.seo import ia as seo_ia, rastreo

    estado.update({"seo_leidas": [], "seo_temas": [], "seo_temas_llamadas": 0, "seo_cuota_en": None,
                   "seo_lastmod_a1": "2026-09-01", "seo_retirar": False})

    def descubrir(hosts, maximo=3000):
        urls = []
        if "dgallia.edu.pe" in hosts:
            for i in range(1, 16):
                if i == 15 and estado["seo_retirar"]:
                    continue
                urls.append({"url": f"https://dgallia.edu.pe/a{i}/", "sitemap": "https://dgallia.edu.pe/wp-sitemap-posts-page-1.xml",
                             "lastmod": estado["seo_lastmod_a1"] if i == 1 else "2026-01-01", "excluida": None})
            urls.append({"url": "https://dgallia.edu.pe/cart/", "sitemap": "x", "lastmod": None, "excluida": "Página de servicio (carrito, cuenta, contacto…)"})
        if "ilcb.edu.pe" in hosts:
            urls += [{"url": f"https://ilcb.edu.pe/p{i}/", "sitemap": "https://ilcb.edu.pe/post-sitemap1.xml", "lastmod": None, "excluida": None} for i in (1, 2)]
        return {"urls": urls, "sitemaps": [{"url": "x", "tipo": "urls", "urls": len(urls), "excluido": None, "estado": "OK"}], "avisos": []}

    def paginas_seo(urls, pausa_s=1.0):
        estado["seo_leidas"] += urls
        return {"paginas": [{"url": u, "estado": "OK", "http": 200, "url_final": u, "motivo": None,
                             # Todas de cocina salvo /a14/, un trámite: el filtro del sector la marca sin IA.
                             "datos": {"title": f"Cronograma de pagos {u}" if u.endswith("/a14/") else f"Curso de cocina {u}",
                                       "meta_description": None, "h1": f"H1 {u}", "h2": ["Uno"], "canonical": u,
                                       "lang": "es", "palabras": 300, "extracto": "texto",
                                       "hash": f"h-{u}-{estado['seo_lastmod_a1'] if u.endswith('/a1/') else 0}"}}
                            for u in urls], "frenar": False}

    def temas_seo(paginas, **k):
        estado["seo_temas_kw"] = k
        estado["seo_temas_llamadas"] += 1
        estado["seo_temas"].append([p["url"] for p in paginas])
        if estado["seo_cuota_en"] == estado["seo_temas_llamadas"]:
            estado["seo_cuota_en"] = None
            raise CuotaAgotada("Se agotó la cuota diaria gratuita de Gemini en todos los modelos.")
        salida = []
        for p in paginas:
            n = int(p["url"].rstrip("/").rsplit("/a", 1)[-1]) if "/a" in p["url"] else 0
            consultas = (["qué es la mise en place", "Qué es la mise en place?"] if n % 2 else ["cuánto dura la carrera de cocina", "precio carrera de cocina"]) if n else []
            salida.append({"url": p["url"], "tipo_pagina": "ARTICULO", "tema": f"tema {n}", "consultas": consultas,
                           "relevancia": 10 if n == 14 else 80, "confianza": "ALTA", "evidencia": []})
        return {"temas": salida, "uso": {"tokens_entrada": 500, "tokens_salida": 80, "llamadas": 1, "modelo": "simulado", "costo_usd": 0.001}}

    def agrupar_seo(keywords, grupos=None, **_):
        return {"keywords": [{"keyword": k, "intencion": "TRANSACTIONAL" if "precio" in k else "INFORMATIONAL", "grupo": k.lower().strip("?"),
                              "canonica": k.lower().strip("?"), "relevancia": 80, "motivo": "simulado"} for k in keywords],
                "uso": {"tokens_entrada": 300, "tokens_salida": 60, "llamadas": 1, "modelo": "simulado", "costo_usd": 0.001}}

    def cobertura_seo(grupos, propias, **_):
        estado["seo_grupos_cobertura"] = [g["grupo"] for g in grupos]
        return {"cobertura": [{"grupo": g["grupo"], "estado": "PARCIAL" if i == 0 else "SIN_COBERTURA",
                               "url": propias[0]["url"] if i == 0 else None, "motivo": "simulado"} for i, g in enumerate(grupos)],
                "uso": {"tokens_entrada": 300, "tokens_salida": 60, "llamadas": 1, "modelo": "simulado", "costo_usd": 0.001}}

    def articulo_seo(keyword, variantes, competidores, propias, **k):
        estado["seo_articulo"] = {"keyword": keyword, "variantes": variantes, "competidores": [c["url"] for c in competidores],
                                  "propias": [p["url"] for p in propias], **k}
        # estado["articulos_limpios"] = n: los n siguientes salen sin «[COMPLETAR]» (se pueden enviar).
        limpio = estado.get("articulos_limpios", 0) > 0
        if limpio:
            estado["articulos_limpios"] -= 1
        return {"titulo": f"Guía: {keyword}", "slug": "guia", "meta_description": "Todo sobre el tema.",
                "contenido": "## Qué es\nTexto completo." if limpio else "## Qué es\nTexto.\n\nDura [COMPLETAR: duración del curso].",
                "pendientes": [] if limpio else ["[COMPLETAR: duración del curso]"],
                "enlaces_quitados": [], "uso": {"tokens_entrada": 900, "tokens_salida": 1500, "llamadas": 1, "modelo": "simulado", "costo_usd": 0.004}}

    def rubro_seo(negocio, paginas, **_):
        return {"descripcion": "Escuela de cocina sugerida", "palabras": ["cocin", "chef"],
                "uso": {"tokens_entrada": 400, "tokens_salida": 60, "llamadas": 1, "modelo": "simulado", "costo_usd": 0.001}}

    rastreo.descubrir, rastreo.paginas = descubrir, paginas_seo

    # WordPress simulado: el cliente real contra un transporte falso.
    import httpx
    from app.seo import wordpress

    os.environ.update(WP_URL="https://blog.prueba", WP_USUARIO="editor", WP_CLAVE_APLICACION="abcd efgh")
    estado.update(wp=[], wp_estado="draft")

    def wp_responder(req):
        if "/media" in req.url.path:
            subida = req.url.path.endswith("/media")
            estado["wp"].append((req.method, req.url.path, {"bytes": len(req.content), "tipo": req.headers.get("content-type")}
                                 if subida else json.loads(req.content)))
            return httpx.Response(201 if subida else 200, json={"id": 501, "source_url": "https://blog.prueba/up/guia.jpg"})
        cuerpo = json.loads(req.content) if req.content else None
        estado["wp"].append((req.method, req.url.path, cuerpo))
        if req.url.path.endswith("/users/me"):
            return httpx.Response(200, json={"name": "Editora", "capabilities": {"edit_posts": True, "publish_posts": True}})
        estado["wp_estado"] = cuerpo.get("status", estado["wp_estado"])
        return httpx.Response(200, json={"id": 77, "status": estado["wp_estado"], "link": "https://blog.prueba/?p=77"})

    wordpress._http = lambda: httpx.Client(transport=httpx.MockTransport(wp_responder))

    # Imagen destacada: banco de fotos y Gemini simulados.
    import base64
    from app.seo import imagenes

    b64 = lambda b: base64.b64encode(b).decode()
    imagenes.estado = lambda: {"fotos": "PIXABAY", "gemini": True, "modelo": "gemini-3.1-flash-lite-image", "precio_usd": 0.0336}
    imagenes.buscar = lambda consulta, pagina=1, orientacion="horizontal": estado.update(foto_consulta=consulta, foto_orientacion=orientacion) or {
        "fotos": [{"id": 9, "ancho": 4000, "alto": 3000, "autor": "Ana", "autor_url": "https://www.pexels.com/@ana",
                   "pagina_url": "https://www.pexels.com/photo/9/", "alt": "Pan", "miniatura": "", "previa": ""}],
        "total": 1, "pagina": pagina, "hay_mas": False, "fuente": "PIXABAY"}
    imagenes.descargar = lambda id_foto: {"id": id_foto, "autor": "Ana", "autor_url": "https://www.pexels.com/@ana",
                                          "pagina_url": "https://www.pexels.com/photo/9/", "alt": "Pan", "miniatura": "", "previa": "",
                                          "datos_b64": b64(JPG_PRUEBA), "mime": "image/jpeg", "fuente": "PIXABAY"}

    def generar_imagen(descripcion, negocio="", rubro="", formato="HORIZONTAL"):
        estado["imagen_pedida"] = {"descripcion": descripcion, "negocio": negocio, "rubro": rubro, "formato": formato}
        return {"datos_b64": b64(PNG_PRUEBA), "mime": "image/png", "modelo": "gemini-3.1-flash-lite-image", "prompt": descripcion,
                "uso": {"tokens_entrada": 80, "tokens_salida": 1290, "llamadas": 1, "modelo": "gemini-3.1-flash-lite-image", "costo_usd": 0.0336}}

    imagenes.generar = generar_imagen

    # Autocompletado de Google: estado["google"] = "ok" (la sugiere en otro orden), "ninguna" o "caido".
    from app.seo import demanda
    estado["google"] = "ok"

    def demanda_falsa(grupos, pais="PE", idioma="es"):
        estado["demanda_pedida"] = {"grupos": grupos, "pais": pais}
        modo = estado["google"]
        if modo == "caido":
            return {"disponible": False, "grupos": [{"grupo": g["grupo"], "senal": None, "forma": None, "sugerencias": []} for g in grupos]}
        return {"disponible": True, "grupos": [
            {"grupo": g["grupo"], "senal": "NINGUNA", "forma": None, "sugerencias": []} if modo == "ninguna" else
            {"grupo": g["grupo"], "senal": "EXACTA", "forma": " ".join(reversed(g["keywords"][0].split())), "sugerencias": ["otra búsqueda"]}
            for g in grupos]}

    demanda.comprobar = demanda_falsa

    # Search Console: estado["gsc"] = None (sin conectar) o las filas que «devuelve Google».
    from app.compartido.errores import ErrorExterno
    from app.seo import search_console
    estado["gsc"] = None
    search_console.configurado = lambda: {"completo": estado["gsc"] is not None, "faltan": [] if estado["gsc"] is not None else ["GSC_PROPIEDAD"],
                                          "propiedad": "sc-domain:ilcb.edu.pe", "pais": "per"}
    search_console.comprobar = lambda: {"ok": True, "propiedad": "sc-domain:ilcb.edu.pe", "permiso": "siteRestrictedUser",
                                        "propiedades": [{"propiedad": "sc-domain:ilcb.edu.pe", "permiso": "siteRestrictedUser"}]}

    def gsc_consultas(dias=90):
        if estado["gsc"] is None:
            raise ErrorExterno("Falta conectar Search Console: completa GSC_PROPIEDAD en 03_worker/.env.")
        return {"propiedad": "sc-domain:ilcb.edu.pe", "desde": "2026-07-29", "hasta": "2026-10-26", "pais": "per", "filas": estado["gsc"]}

    search_console.consultas = gsc_consultas

    # ── Medicion: Meta, GA4 y resumen simulados ──
    # Cinco anuncios con un cambio de regimen en los ultimos 7 dias hasta ayer (FIN), pensado para que
    # cada alerta salte una vez: c1 se encarece y a2 gasta sin leads; c2 pierde CTR; c4 rinde mejor;
    # c3 (trafico) no tiene leads ni chats.
    from datetime import date as _fecha, timedelta as _dias
    from app.medicion import meta as mmeta, ga4 as mga4, resumen as mresumen
    fin_meta = _fecha.today() - _dias(days=1)
    estado.update(meta_conectado=True, meta_pedidas=[])
    mmeta.configurado = lambda: {"completo": estado["meta_conectado"], "faltan": [] if estado["meta_conectado"] else ["META_ACCESS_TOKEN"], "cuenta": "act_1"}
    mmeta.cuenta = lambda: {"id": "act_1", "nombre": "ILCB Prueba", "moneda": "USD", "activa": True, "zona": "America/Lima"}

    def insights_meta(desde, hasta):
        if not estado["meta_conectado"]:
            raise ErrorExterno("Falta conectar Meta: completa META_ACCESS_TOKEN en 03_worker/.env.")
        estado["meta_pedidas"].append((desde, hasta))
        filas = []
        d = _fecha.fromisoformat(desde)
        while d <= _fecha.fromisoformat(hasta):
            nuevo = d > fin_meta - _dias(days=7)

            def fila(ad, camp, nombre, objetivo, gasto, imp, clics, leads=0, conv=0):
                filas.append({"fecha": d.isoformat(), "anuncio_id": ad, "anuncio": f"Anuncio {ad}", "conjunto_id": "s", "conjunto": "Conjunto",
                              "campana_id": camp, "campana": nombre, "objetivo": objetivo, "gasto": gasto, "impresiones": imp, "alcance": imp // 2,
                              "clics": clics, "clics_enlace": clics, "leads": leads, "conversaciones": conv, "visitas": 0})
            fila("a1", "c1", "ILCB - Lead Ads - Pastelería - 2027I", "OUTCOME_LEADS", 10.0, 2000, 40, leads=3 if nuevo else 5)
            if nuevo:
                fila("a2", "c1", "ILCB - Lead Ads - Pastelería - 2027I", "OUTCOME_LEADS", 15.0, 3000, 45)
            fila("b1", "c2", "ILCB - WSP - Gastronomía - 2027I", "OUTCOME_SALES", 20.0, 5000, 50 if nuevo else 100, conv=10)
            fila("b2", "c4", "ILCB - WSP - Pastelería - 2027I", "OUTCOME_SALES", 6.0, 1000, 20, conv=8)
            fila("t1", "c3", "Tráfico web", "OUTCOME_TRAFFIC", 5.0, 4000, 60)
            d += _dias(days=1)
        return {"cuenta": "act_1", "desde": desde, "hasta": hasta, "filas": filas}
    mmeta.insights = insights_meta

    mga4.configurado = lambda: {"completo": True, "faltan": [], "propiedad": "123"}
    mga4.propiedades = lambda: {"propiedades": [{"propiedad": "123", "nombre": "ilcb.edu.pe", "cuenta": "ILCB"}], "configurada": "123", "ok": True}
    mga4.informe = lambda desde, hasta: {"propiedad": "123", "desde": desde, "hasta": hasta,
                                         "canales": [{"sessionDefaultChannelGroup": "Paid Social", "sessions": 100, "engagedSessions": 60, "keyEvents": 7, "totalUsers": 90}],
                                         "campanas": [], "paginas": [], "dias": [], "eventos": [{"eventName": "generate_lead", "keyEvents": 7}]}

    def resumir_medicion(datos, **k):
        estado["medicion_ia"] = datos
        return {"titular": "Pastelería se encarece", "puntos": ["El costo por lead subió."], "hallazgos": [], "advertencias": [],
                "uso": {"tokens_entrada": 900, "tokens_salida": 200, "llamadas": 1, "modelo": "simulado", "costo_usd": 0.001}}
    mresumen.resumir = resumir_medicion

    # Miniaturas de los anuncios: las de ad_id acabado en 7 «no bajan» (el informe conserva su enlace).
    from app.fuentes import miniaturas

    def miniaturas_falsas(items):
        estado.setdefault("miniaturas_pedidas", []).append([i["id"] for i in items])
        hechas = [{"id": i["id"], "datos_b64": b64(JPG_PRUEBA), "mime": "image/jpeg"} for i in items if not i["id"].endswith("7")]
        return {"miniaturas": hechas, "fallidas": len(items) - len(hechas)}

    miniaturas.descargar = miniaturas_falsas

    # Sugerencias de paginas de Meta (sin Chrome).
    from app.fuentes import paginas_meta

    def sugerir(texto, pais="PE"):
        estado["sugerencias"] = estado.get("sugerencias", 0) + 1
        return [{"page_id": "8800000010", "nombre": "Fogón Lima", "categoria": "Escuela de cocina", "avatar": None, "seguidores": 1200,
                 "ig_usuario": "fogonlima", "ig_seguidores": 800, "alias": None, "verificada": False}]

    paginas_meta.sugerir = sugerir
    paginas_meta.preparar = lambda pais="PE": estado.update(preparado=pais) or True
    seo_ia.temas, seo_ia.agrupar, seo_ia.cobertura = temas_seo, agrupar_seo, cobertura_seo

    def mejora_seo(url, actual, consultas, **k):
        estado.setdefault("mejoras_pedidas", []).append({"url": url, "actual": actual, "consultas": consultas, **k})
        return {"titulo": f"Mejor título para {url[-4:]}", "meta_description": "Descripción propuesta.",
                "ideas": [{"donde": "H2", "dice_ahora": "Origen", "debe_decir": "Origen del curso"}],
                "motivo": "La búsqueda no está en el título.",
                "uso": {"tokens_entrada": 400, "tokens_salida": 80, "llamadas": 1, "modelo": "simulado", "costo_usd": 0.001}}

    seo_ia.mejora = mejora_seo
    seo_ia.articulo, seo_ia.rubro = articulo_seo, rubro_seo

    fuentes.lanzar, fuentes.consultar = lanzar, lambda run, t: consultar(run, t)
    clasificar.clasificar, clasificar.territorios = clasificar_falso, territorios_falso
    # rutas.py importo los modulos, no las funciones: el parche llega.
    servidor = uvicorn.Server(uvicorn.Config(app, port=PUERTO_WORKER, log_level="error"))
    threading.Thread(target=servidor.run, daemon=True).start()
    return servidor, estado


# ── Cliente HTTP minimo ───────────────────────────────────────────────────

PRINCIPAL: dict = {"c": ""}      # cookie de la sesion del administrador
JPG_PRUEBA = b"\xff\xd8\xff\xe0" + b"1" * 200
PNG_PRUEBA = b"\x89PNG\r\n\x1a\n" + b"2" * 300
MP4_PRUEBA = b"\x00\x00\x00\x18ftypmp42" + b"3" * 5000
FLYER_PRUEBA = b"\xff\xd8\xff\xe0" + b"F" * 500


def subir_archivo(ruta: str, nombre: str, datos: bytes, jar: dict | None = None):
    """POST multipart con un campo `archivo`: (estado, json)."""
    jar = PRINCIPAL if jar is None else jar
    borde = f"radarprueba{int(time.time() * 1000)}"
    cuerpo = (f'--{borde}\r\nContent-Disposition: form-data; name="archivo"; filename="{nombre}"\r\n'
              f"Content-Type: application/octet-stream\r\n\r\n").encode() + datos + f"\r\n--{borde}--\r\n".encode()
    r = urllib.request.Request(BASE + ruta, data=cuerpo, method="POST",
                               headers={"content-type": f"multipart/form-data; boundary={borde}", "cookie": jar["c"]})
    try:
        resp = urllib.request.urlopen(r, timeout=60)
        estado = resp.status
    except urllib.error.HTTPError as e:
        resp, estado = e, e.code
    t = resp.read().decode()
    return estado, (json.loads(t) if t else None)


def bajar(ruta: str, jar: dict | None = None) -> tuple[int, bytes, str]:
    """GET de un archivo (no JSON): (estado, bytes, content-type)."""
    jar = PRINCIPAL if jar is None else jar
    r = urllib.request.Request(BASE + ruta, headers={"cookie": jar["c"]})
    try:
        resp = urllib.request.urlopen(r, timeout=60)
        return resp.status, resp.read(), resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers.get("Content-Type", "")


def http(metodo: str, ruta: str, cuerpo=None, jar: dict | None = None):
    jar = PRINCIPAL if jar is None else jar
    datos = None if cuerpo is None else json.dumps(cuerpo).encode()
    cab = {"content-type": "application/json"}
    if jar["c"]:
        cab["cookie"] = jar["c"]
    r = urllib.request.Request(BASE + ruta, data=datos, method=metodo, headers=cab)
    try:
        resp = urllib.request.urlopen(r, timeout=60)
        estado = resp.status
    except urllib.error.HTTPError as e:
        resp, estado = e, e.code
    nueva = resp.headers.get("Set-Cookie")
    if nueva:
        valor = nueva.split(";")[0]
        jar["c"] = "" if valor.endswith("=") else valor
    t = resp.read().decode()
    return estado, (json.loads(t) if t else None)


def esperar(codigo: str, hasta: tuple[str, ...], segundos: int = 90) -> dict:
    fin = time.time() + segundos
    a = {}
    while time.time() < fin:
        st, a = http("GET", f"/analisis/{codigo}")
        if st != 200:
            raise RuntimeError(f"GET /analisis/{codigo} -> {st} {a}")
        if a["estado"] in hasta:
            return a
        time.sleep(0.5)
    return a


def esperar_seo(codigo: str, hasta: tuple[str, ...] = ("TERMINADA", "PAUSADA", "CANCELADA"), segundos: int = 60) -> dict:
    fin = time.time() + segundos
    t = {}
    while time.time() < fin:
        t = http("GET", f"/seo/tareas/{codigo}")[1]
        if t and t["estado"] in hasta:
            return t
        time.sleep(0.3)
    return t


def peticion(**extra) -> dict:
    return {"misMarcas": [], "keywords": [], "referencia": ["escuela de cocina"], "pais": "PE", "maximo": 100,
            "soloActivos": True, "conMedios": False, **extra}


# ── Prueba ────────────────────────────────────────────────────────────────

def main() -> int:
    datos = tempfile.mkdtemp(prefix="radar-prueba-")
    os.makedirs(os.path.join(RAIZ, "05_pruebas", "salida"), exist_ok=True)
    registro = os.path.join(RAIZ, "05_pruebas", "salida", "backend.log")   # para ver por que fallo algo
    servidor, estado = worker_simulado()
    jar = os.path.join(RAIZ, "01_backend", "build", "libs", "radar-0.0.1-SNAPSHOT.jar")
    if not os.path.exists(jar):
        print("Falta compilar el backend: 01_backend\\gradlew.bat bootJar")
        return 2
    backend = subprocess.Popen(
        ["java", "-jar", jar, f"--server.port={PUERTO_BACKEND}", f"--radar.datos={datos}", f"--radar.worker=http://localhost:{PUERTO_WORKER}",
         "--radar.origenes-permitidos="],
        stdout=open(registro, "w", encoding="utf-8"), stderr=subprocess.STDOUT)
    try:
        for _ in range(120):
            try:
                if urllib.request.urlopen(f"http://localhost:{PUERTO_BACKEND}/actuator/health", timeout=2).status == 200:
                    break
            except OSError:
                time.sleep(1)
        else:
            print("El backend no arranco")
            return 2

        print("cuentas")
        s, e = http("GET", "/auth/estado")
        comprobar("pide crear la primera cuenta", s == 200 and e["necesitaAlta"] and e["usuario"] is None)
        comprobar("sin sesion no se ve nada", http("GET", "/analisis")[0] == 401 and http("GET", "/informes")[0] == 401)
        comprobar("rechaza una contraseña débil", http("POST", "/auth/alta", {"nombre": "Ana", "email": "ana@ejemplo.pe", "clave": "12345"})[0] == 409)
        comprobar("rechaza la que contiene el correo", http("POST", "/auth/alta", {"nombre": "Ana", "email": "anamaria@ejemplo.pe", "clave": "Mi-anamaria-2026"})[0] == 409)
        s, r = http("POST", "/auth/alta", {"nombre": "Ana Admin", "email": "ana@ejemplo.pe", "clave": "Frase larga y segura 2026"})
        comprobar("crea al administrador con código de recuperación", s == 200 and r["usuario"]["rol"] == "admin" and len(r["codigoRecuperacion"]) == 24, str(r))
        codigo_rec = r["codigoRecuperacion"]
        comprobar("no hay una segunda alta", http("POST", "/auth/alta", {"nombre": "X", "email": "x@ejemplo.pe", "clave": "Otra frase larga 2026"})[0] == 409)
        comprobar("con sesión ya se ve", http("GET", "/analisis")[0] == 200 and http("GET", "/auth/estado")[1]["usuario"]["nombre"] == "Ana Admin")

        miembro: dict = {"c": ""}
        s, r = http("POST", "/usuarios", {"nombre": "Luis", "email": "luis@ejemplo.pe", "rol": "miembro"})
        comprobar("el admin crea un miembro con clave temporal", s == 201 and r["usuario"]["debeCambiar"] and r["claveTemporal"], str(r))
        temporal, cod_luis = r["claveTemporal"], r["usuario"]["codigo"]
        comprobar("no se repite un correo", http("POST", "/usuarios", {"nombre": "L2", "email": "LUIS@ejemplo.pe", "rol": "miembro"})[0] == 409)
        s, r = http("POST", "/auth/entrar", {"email": "luis@ejemplo.pe", "clave": temporal}, miembro)
        comprobar("el miembro entra con la temporal y debe cambiarla", s == 200 and r["usuario"]["debeCambiar"] and r["usuario"]["rol"] == "miembro", str(r))
        comprobar("un miembro no gestiona usuarios", http("GET", "/usuarios", None, miembro)[0] == 403 and http("POST", "/usuarios", {"nombre": "Z", "email": "z@ejemplo.pe", "rol": "admin"}, miembro)[0] == 403)
        comprobar("ni comprueba claves de IA", http("POST", "/sistema/comprobar", None, miembro)[0] == 403)
        comprobar("pero sí ve los análisis", http("GET", "/analisis", None, miembro)[0] == 200)
        comprobar("cambiar clave exige la actual", http("PUT", "/auth/cuenta", {"claveActual": "mala", "claveNueva": "Mi clave nueva segura 1"}, miembro)[0] == 409)
        s, r = http("PUT", "/auth/cuenta", {"claveActual": temporal, "claveNueva": "Mi clave nueva segura 1"}, miembro)
        comprobar("cambia la clave y ya no es temporal", s == 200 and not r["usuario"]["debeCambiar"] and r["codigoRecuperacion"], str(r))

        malo: dict = {"c": ""}
        msgs = {http("POST", "/auth/entrar", {"email": "luis@ejemplo.pe", "clave": "incorrecta-1"}, malo)[1]["error"] for _ in range(5)}
        comprobar("mismo mensaje para clave mala y correo inexistente",
                  msgs == {"Correo o contraseña incorrectos."} and http("POST", "/auth/entrar", {"email": "nadie@ejemplo.pe", "clave": "incorrecta-1"}, malo)[1]["error"] in msgs)
        s, r = http("POST", "/auth/entrar", {"email": "luis@ejemplo.pe", "clave": "Mi clave nueva segura 1"}, malo)
        comprobar("tras 5 fallos la cuenta se bloquea (incluso con la clave buena)", s == 409 and "intentos" in r["error"], str(r))

        comprobar("no se puede degradar al último admin", http("PUT", f"/usuarios/{http('GET', '/usuarios')[1][0]['codigo']}", {"rol": "miembro"})[0] == 409)
        comprobar("no se puede borrar a uno mismo", http("DELETE", f"/usuarios/{http('GET', '/usuarios')[1][0]['codigo']}")[0] == 409)
        comprobar("el admin desactiva al miembro", http("PUT", f"/usuarios/{cod_luis}", {"activo": False})[0] == 200)
        comprobar("su sesión deja de valer", http("GET", "/analisis", None, miembro)[0] == 401)
        s, r = http("POST", f"/usuarios/{cod_luis}/reiniciar-clave")
        comprobar("reiniciar clave da una temporal", s == 200 and r["claveTemporal"])
        comprobar("la auditoría registra lo hecho", any(a["accion"] == "desactivar_usuario" for a in http("GET", "/usuarios/auditoria")[1]))

        otro: dict = {"c": ""}
        s, r = http("POST", "/auth/recuperar", {"email": "ana@ejemplo.pe", "codigo": "AAAA-AAAA-AAAA-AAAA-AAAA", "claveNueva": "Frase nueva de Ana 2026"}, otro)
        comprobar("un código de recuperación falso no sirve", s == 409)
        s, r = http("POST", "/auth/recuperar", {"email": "ana@ejemplo.pe", "codigo": codigo_rec.lower(), "claveNueva": "Frase nueva de Ana 2026"}, otro)
        comprobar("el código correcto restablece la clave y entra", s == 200 and r["codigoRecuperacion"] and r["codigoRecuperacion"] != codigo_rec, str(r))
        comprobar("el código es de un solo uso", http("POST", "/auth/recuperar", {"email": "ana@ejemplo.pe", "codigo": codigo_rec, "claveNueva": "Frase nueva de Ana 2027"}, {"c": ""})[0] == 409)
        comprobar("la sesión anterior del admin se cerró", http("GET", "/analisis")[0] == 401)
        s, r = http("POST", "/auth/entrar", {"email": "ana@ejemplo.pe", "clave": "Frase nueva de Ana 2026"})
        comprobar("entra con la clave nueva", s == 200)
        comprobar("sale", http("POST", "/auth/salir")[0] == 204 and http("GET", "/analisis")[0] == 401)
        http("POST", "/auth/entrar", {"email": "ana@ejemplo.pe", "clave": "Frase nueva de Ana 2026"})

        print("sistema e informe de ejemplo")
        s, sis = http("GET", "/sistema")
        comprobar("el backend ve al worker", s == 200 and sis["worker"] and sis["worker"]["ok"])
        s, fila = http("POST", "/informes/ejemplo")
        comprobar("crea el informe de ejemplo", s == 201 and fila["esEjemplo"], str(fila))
        comprobar("no lo crea dos veces", http("POST", "/informes/ejemplo")[0] == 409)
        s, inf = http("GET", f"/informes/{fila['codigo']}")
        comprobar("lee el informe completo", s == 200 and inf["datos"]["meta"]["anuncios"] >= 60)
        comprobar("la lista lo incluye con portada", any(f["portada"] for f in http("GET", "/informes")[1]))

        print("validacion y estimacion")
        s, e = http("POST", "/analisis/estimar", peticion(maximo=100))
        comprobar("estima 11 llamadas y un costo", s == 200 and e["llamadas"] == 11 and 0.1 < e["costoGeminiUsd"] < 0.5, str(e))
        comprobar("rechaza sin competidores", http("POST", "/analisis", peticion(competidores=[]))[0] == 409)
        comprobar("rechaza nivel 9", http("POST", "/analisis", peticion(competidores=[{"nombre": "X", "nivel": 9}]))[0] == 409)
        comprobar("fecha mínima mal escrita o futura: rechazada",
                  http("POST", "/analisis", peticion(competidores=[{"nombre": "X", "nivel": 1}], fechaMinima="15/01/2026"))[0] == 409
                  and http("POST", "/analisis", peticion(competidores=[{"nombre": "X", "nivel": 1}], fechaMinima="2099-01-01"))[0] == 409)

        print("analisis con pagina ambigua")
        comp = [{"nombre": "Escuela Sabor Andino", "nivel": 1}, {"nombre": "Instituto Mesa Abierta", "nivel": 1},
                {"nombre": "Fogón", "nivel": 2}, {"nombre": "Academia Inexistente Zzz", "nivel": 3}]
        # Mi Escuela solo como marca propia: se busca igual, como competidor de nivel 3.
        s, a = http("POST", "/analisis", peticion(competidores=comp, misMarcas=["Mi Escuela"]))
        codigo = a["codigo"]
        comprobar("lo crea en cola", s == 201 and codigo == "A0001")
        comprobar("tu marca se busca como competidor de nivel 3",
                  {"nombre": "Mi Escuela", "nivel": 3, "paginas": []} in a["peticion"]["competidores"], str(a["peticion"]["competidores"]))
        a = esperar(codigo, ("pausado", "terminado"))
        comprobar("se pausa pidiendo elegir pagina", a["estado"] == "pausado" and a["pendiente"] and a["pendiente"]["competidor"] == "Fogón", str(a))
        comprobar("ofrece las dos candidatas", a["pendiente"] and len(a["pendiente"]["candidatos"]) == 2)
        comprobar("no se puede continuar sin elegir", http("POST", f"/analisis/{codigo}/continuar")[0] == 409)
        comprobar("rechaza una pagina que no es candidata", http("POST", f"/analisis/{codigo}/pagina", {"competidor": "Fogón", "pageId": "nope"})[0] == 409)
        s, a = http("POST", f"/analisis/{codigo}/pagina", {"competidor": "Fogón", "pageId": "8800000010"})
        comprobar("acepta la eleccion", s == 200, f"{s} {a}")
        a = esperar(codigo, ("terminado", "pausado"))
        comprobar("termina tras elegir", a["estado"] == "terminado" and a["codInforme"], str(a))
        s, inf = http("GET", f"/informes/{a['codInforme']}")
        meta = inf["datos"]["meta"]
        comprobar("informe con anuncios y mi marca", meta["anuncios"] == 29 + 3 and inf["datos"]["mis_anuncios"] == 4, str(meta["anuncios"]))
        comprobar("anota al competidor sin anuncios", "Academia Inexistente Zzz" in meta["sin_anuncios"], str(meta["sin_anuncios"]))
        comprobar("anota las paginas identificadas", len(meta["identificadas"]) >= 3)
        comprobar("registra el costo de la IA", meta["costo_ia_usd"] > 0 and meta["llamadas_ia"] >= 2, str(meta))
        from app.analisis import ejemplo
        redes = {x["ad_id"]: x["plataformas"] for x in ejemplo.anuncios()}
        comprobar("cada anuncio dice en qué redes sale", all(x["plataformas"] == redes[x["ad_id"]]
                  for x in inf["datos"]["anuncios"] if x["ad_id"] in redes), str(inf["datos"]["anuncios"][0].get("plataformas")))
        comprobar("la otra pagina ambigua (Cusco) no entra", all(x["anunciante"] != "Fogón Cusco" for x in inf["datos"]["anuncios"]))
        anuncios = inf["datos"]["anuncios"]
        locales = [x for x in anuncios if (x.get("thumb_url") or "").startswith("/api/informes/miniaturas/")]
        comprobar("guarda las miniaturas en el Radar (las de Meta caducan)", locales and all(
            x in locales for x in anuncios if not x["ad_id"].endswith("7") and x.get("thumb_url")), f"{len(locales)} de {len(anuncios)}")
        comprobar("la que no bajó conserva el enlace de Meta", all(x["thumb_url"].startswith("https://") for x in anuncios if x["ad_id"].endswith("7") and x.get("thumb_url")))
        s, archivo, tipo = bajar(locales[0]["thumb_url"].removeprefix("/api"))
        comprobar("sirve la miniatura guardada", s == 200 and archivo == JPG_PRUEBA and tipo.startswith("image/jpeg"), f"{s} {tipo}")
        comprobar("miniatura que no existe: 404", bajar("/informes/miniaturas/000")[0] == 404)
        pedidas_antes = {i for lote in estado["miniaturas_pedidas"] for i in lote if not i.endswith("7")}

        print("fecha mínima de los anuncios")
        estado["anuncios_terminados"] = True
        s, a = http("POST", "/analisis", peticion(competidores=[{"nombre": "Fogón", "nivel": 1}], soloActivos=False, fechaMinima="2020-01-01"))
        comprobar("guarda la fecha mínima en la petición", s == 201 and a["peticion"]["fechaMinima"] == "2020-01-01", str(a.get("peticion")))
        a = esperar(a["codigo"], ("pausado", "terminado", "error", "cancelado"))
        comprobar("los anuncios terminados y anteriores no se cargan: lo dice", a["estado"] != "terminado"
                  and "fecha mínima" in json.dumps(a, ensure_ascii=False), str(a)[:300])
        estado["anuncios_terminados"] = False
        http("POST", f"/analisis/{a['codigo']}/cancelar")

        print("varias páginas del mismo competidor")
        n_lotes = len(estado["miniaturas_pedidas"])
        s, a = http("POST", "/analisis", peticion(competidores=[{"nombre": "Fogón", "nivel": 1}]))
        cod_multi = a["codigo"]
        a = esperar(cod_multi, ("pausado", "terminado"))
        comprobar("pregunta por las páginas de Fogón", a["estado"] == "pausado" and a["pendiente"] and len(a["pendiente"]["candidatos"]) == 2, str(a)[:200])
        s, a = http("POST", f"/analisis/{cod_multi}/pagina", {"competidor": "Fogón", "pageIds": ["8800000010", "8800000011"]})
        comprobar("acepta varias páginas a la vez", s == 200, str(a)[:200])
        a = esperar(cod_multi, ("terminado", "pausado"))
        inf = http("GET", f"/informes/{a['codInforme']}")[1] if a.get("codInforme") else {}
        nuevas = {i for lote in estado["miniaturas_pedidas"][n_lotes:] for i in lote}
        comprobar("no vuelve a bajar las miniaturas ya guardadas", not (nuevas & pedidas_antes), str(nuevas & pedidas_antes))
        ids = {i["page_id"] for i in inf.get("datos", {}).get("meta", {}).get("identificadas", [])}
        comprobar("el informe incluye los anuncios de ambas páginas", a["estado"] == "terminado" and ids == {"8800000010", "8800000011"}
                  and {x["anunciante"] for x in inf["datos"]["anuncios"]} == {"Fogón Lima", "Fogón Cusco"}, str(ids))
        comprobar("sin marca propia el informe no marca ninguna", inf["datos"]["mi_marca"] is None and inf["datos"]["mis_anuncios"] == 0)

        print("competidor con páginas elegidas al configurarlo")
        s, r = http("POST", "/analisis/paginas", {"texto": "fo", "pais": "PE"})
        comprobar("con menos de 3 letras no consulta a Meta", s == 200 and r["paginas"] == [] and not estado.get("sugerencias"), str(r))
        s, r = http("POST", "/analisis/paginas", {"texto": "fogón", "pais": "pe"})
        comprobar("sugiere páginas con foto, categoría y seguidores", s == 200 and r["paginas"][0]["page_id"] == "8800000010" and r["paginas"][0]["categoria"], str(r))
        comprobar("abre Chrome por adelantado", http("POST", "/analisis/paginas/preparar", {"pais": "PE"})[0] == 204 and estado.get("preparado") == "PE")
        s, a = http("POST", "/analisis", peticion(competidores=[{"nombre": "Fogón", "nivel": 1, "paginas": [
            {"pageId": "8800000010", "nombre": "Fogón Lima", "avatar": None, "categoria": "Escuela de cocina", "seguidores": 1200},
            {"pageId": "no-es-un-id", "nombre": "Mala"}]}], referencia=["Escuela de cocina"]))
        cod_pag = a["codigo"]
        comprobar("guarda solo las páginas con id válido", [x["pageId"] for x in a["peticion"]["competidores"][0]["paginas"]] == ["8800000010"], str(a["peticion"]))
        comprobar("con páginas, el nombre es el de la primera y no lo escrito para buscar",
                  a["peticion"]["competidores"][0]["nombre"] == "Fogón Lima", a["peticion"]["competidores"][0]["nombre"])
        a = esperar(cod_pag, ("terminado", "pausado"))
        comprobar("no pregunta cuál es su página", a["estado"] == "terminado" and not a["pendiente"], str(a)[:200])
        comprobar("busca por la página elegida, no por el nombre", {"valor": "8800000010", "modo": "pagina"} in estado["terminos"]
                  and not any(t["modo"] == "marca" and t["valor"] == "Fogón" for t in estado["terminos"]), str(estado["terminos"]))
        inf = http("GET", f"/informes/{a['codInforme']}")[1]
        comprobar("el informe es solo de esa página", {x["anunciante"] for x in inf["datos"]["anuncios"]} == {"Fogón Lima"}, str({x["anunciante"] for x in inf["datos"]["anuncios"]}))
        comprobar("el filtro del sector recibe los competidores y sus páginas como referencia",
                  estado["referencia"] == ["Escuela de cocina", "Fogón Lima"], str(estado["referencia"]))

        print("tu marca con su página elegida")
        s, a = http("POST", "/analisis", peticion(competidores=[{"nombre": "Escuela Sabor Andino", "nivel": 1}],
                                                  marcas=[{"nombre": "c", "paginas": [{"pageId": "8800000010", "nombre": "Fogón Lima"}]}]))
        comprobar("la marca entra como competidor con su página",
                  s == 201 and {"nombre": "Fogón Lima", "nivel": 3, "paginas": [{"pageId": "8800000010", "nombre": "Fogón Lima", "avatar": None,
                                                                            "categoria": None, "seguidores": None}]} in a["peticion"]["competidores"]
                  and a["peticion"]["misMarcas"] == ["Fogón Lima"], str(a)[:300])
        a = esperar(a["codigo"], ("terminado", "pausado"))
        comprobar("no pregunta cuál es la página de tu marca", a["estado"] == "terminado" and not a["pendiente"], str(a)[:200])
        inf = http("GET", f"/informes/{a['codInforme']}")[1]["datos"]
        comprobar("reconoce tus anuncios por la página, no por el nombre",
                  inf["mis_paginas"] == ["8800000010"] and inf["mis_anuncios"] == sum(x["page_id"] == "8800000010" for x in inf["anuncios"]) > 0,
                  f"{inf['mis_paginas']} {inf['mis_anuncios']}")

        print("pausa por cuota y continuar sin repetir")
        estado["ids_clasificados"].clear()
        estado["llamadas_clasificar"] = 0
        estado["cuota_en"] = 2          # la 2a llamada (anuncios 11-20) agota la cuota
        s, a = http("POST", "/analisis", peticion(competidores=[c for c in comp if c["nombre"] not in ("Fogón", "Instituto Mesa Abierta")]))
        codigo2 = a["codigo"]
        a = esperar(codigo2, ("pausado", "terminado"))
        comprobar("se pausa por la cuota", a["estado"] == "pausado" and "cuota" in (a["error"] or ""), str(a))
        comprobar("conserva lo clasificado", a["hechos"] == 10 and a["total"] > 10, f"hechos={a['hechos']} total={a['total']}")
        hechos_antes = list(estado["ids_clasificados"])
        s, a = http("POST", f"/analisis/{codigo2}/continuar")
        a = esperar(codigo2, ("terminado", "pausado"))
        comprobar("continuar termina", a["estado"] == "terminado" and a["codInforme"], str(a))
        nuevos = estado["ids_clasificados"][len(hechos_antes):]
        comprobar("no reclasifica lo ya pagado", not (set(nuevos) & set(hechos_antes)) and len(nuevos) == a["total"] - 10,
                  f"repetidos={len(set(nuevos) & set(hechos_antes))}")

        print("terminar con lo hecho")
        estado["llamadas_clasificar"] = 0
        estado["cuota_en"] = 2
        s, a = http("POST", "/analisis", peticion(competidores=[c for c in comp if c["nombre"] == "Escuela Sabor Andino"], misMarcas=["Mi Escuela"]))
        codigo3 = a["codigo"]
        a = esperar(codigo3, ("pausado", "terminado"))
        comprobar("pausa de nuevo", a["estado"] == "pausado" and a["hechos"] == 10, str(a))
        s, a = http("POST", f"/analisis/{codigo3}/terminar")
        comprobar("acepta terminar", s == 200, f"{s} {a}")
        a = esperar(codigo3, ("terminado", "pausado"))
        comprobar("termina con lo clasificado", a["estado"] == "terminado" and a["codInforme"], str(a))
        comprobar("el informe parcial tiene 10 anuncios", http("GET", f"/informes/{a['codInforme']}")[1]["datos"]["meta"]["anuncios"] == 10)

        print("cancelar, borrar, archivar")
        estado["cuota_en"] = 2
        estado["llamadas_clasificar"] = 0
        s, a = http("POST", "/analisis", peticion(competidores=comp[:1]))
        codigo4 = a["codigo"]
        a = esperar(codigo4, ("pausado", "terminado"))
        comprobar("pausado para poder cancelar", a["estado"] == "pausado")
        comprobar("cancela", http("POST", f"/analisis/{codigo4}/cancelar")[1]["estado"] == "cancelado")
        comprobar("no se cancela dos veces", http("POST", f"/analisis/{codigo4}/cancelar")[0] == 409)
        comprobar("borra", http("DELETE", f"/analisis/{codigo4}")[0] == 204 and http("GET", f"/analisis/{codigo4}")[0] == 404)
        inf_cod = a["codInforme"] or http("GET", "/informes")[1][0]["codigo"]
        comprobar("archiva", http("PUT", f"/informes/{inf_cod}/archivo", {"archivado": True})[0] == 200
                  and all(f["codigo"] != inf_cod for f in http("GET", "/informes")[1]))
        comprobar("archivados aparecen si se piden", any(f["codigo"] == inf_cod for f in http("GET", "/informes?archivados=true")[1]))
        comprobar("borra un informe", http("DELETE", f"/informes/{inf_cod}")[0] == 204 and http("GET", f"/informes/{inf_cod}")[0] == 404)

        print("análisis: informe semanal")
        eva: dict = {"c": ""}
        s, r = http("POST", "/usuarios", {"nombre": "Eva", "email": "eva@ejemplo.pe", "rol": "miembro"})
        http("POST", "/auth/entrar", {"email": "eva@ejemplo.pe", "clave": r["claveTemporal"]}, eva)
        s, sem = http("GET", "/analisis/semanal")
        comprobar("empieza sin programar", s == 200 and not sem["activo"] and sem["peticion"] is None and sem["proxima"] is None, str(sem))
        comprobar("activarlo sin competidores: rechazado", http("PUT", "/analisis/semanal", {"activo": True})[0] == 409)
        semanal_p = peticion(competidores=[{"nombre": "Fogón", "nivel": 1}])
        comprobar("un miembro no lo programa ni lo lanza", http("PUT", "/analisis/semanal", {"activo": True, "peticion": semanal_p}, eva)[0] == 403
                  and http("POST", "/analisis/semanal/ejecutar", None, eva)[0] == 403)
        comprobar("pero sí lo ve", http("GET", "/analisis/semanal", None, eva)[0] == 200)
        comprobar("hora no válida: rechazada", http("PUT", "/analisis/semanal", {"activo": True, "hora": "7:00", "peticion": semanal_p})[0] == 409)
        s, sem = http("PUT", "/analisis/semanal", {"activo": True, "dia": 1, "hora": "08:00", "peticion": semanal_p})
        comprobar("lo programa con el formulario validado", s == 200 and sem["activo"] and sem["peticion"]["competidores"][0]["nombre"] == "Fogón", str(sem)[:300])
        lima = datetime.fromisoformat(sem["proxima"].replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=-5)))
        comprobar("la próxima es un lunes a las 08:00 de Lima", lima.strftime("%w %H:%M") == "1 08:00", sem["proxima"])
        s, a = http("POST", "/analisis/semanal/ejecutar")
        comprobar("ejecutar ahora crea el análisis", s == 201 and a["codigo"], str(a)[:200])
        a = esperar(a["codigo"], ("pausado", "terminado"))
        comprobar("la primera vez pregunta la página de Fogón", a["estado"] == "pausado" and a["pendiente"] and a["pendiente"]["competidor"] == "Fogón", str(a)[:200])
        http("POST", f"/analisis/{a['codigo']}/pagina", {"competidor": "Fogón", "pageIds": ["8800000010"]})
        a = esperar(a["codigo"], ("terminado", "pausado"))
        comprobar("termina con su informe", a["estado"] == "terminado" and a["codInforme"], str(a)[:200])
        sem = http("GET", "/analisis/semanal")[1]
        comprobar("muestra el último análisis y su informe", sem["analisis"]["codigo"] == a["codigo"] and sem["analisis"]["codInforme"] and sem["ultima"])
        b = esperar(http("POST", "/analisis/semanal/ejecutar")[1]["codigo"], ("pausado", "terminado"))
        comprobar("la siguiente vez recuerda la página y no pregunta", b["estado"] == "terminado" and not b["pendiente"]
                  and b["peticion"]["competidores"][0]["paginas"][0]["pageId"] == "8800000010", str(b)[:300])
        comprobar("busca directo por esa página", {"valor": "8800000010", "modo": "pagina"} in estado["terminos"], str(estado["terminos"]))
        comprobar("y queda guardada en lo programado", http("GET", "/analisis/semanal")[1]["peticion"]["competidores"][0]["paginas"][0]["pageId"] == "8800000010")
        s, sem = http("PUT", "/analisis/semanal", {"activo": False})
        comprobar("se desactiva conservando lo programado", s == 200 and not sem["activo"] and sem["proxima"] is None and sem["peticion"], str(sem)[:200])

        print("videos: guion, Vids y aprobación")
        s, ctx = http("GET", "/videos/contexto")
        comprobar("el contexto trae los datos confirmados y la pronunciación de la marca",
                  s == 200 and "Tu estándar es el mundo" in ctx["datos"] and {"texto": "Le Cordon Bleu", "dice": "Le Cordón Blé"} in ctx["pronunciaciones"], str(ctx)[:200])
        comprobar("un miembro no cambia el contexto", http("PUT", "/videos/contexto", ctx, eva)[0] == 403)
        comprobar("idea demasiado corta: rechazada", http("POST", "/videos", {"idea": "x"})[0] == 409)
        comprobar("más de 60 s: rechazado", http("POST", "/videos", {"idea": "Por qué estudiar cocina", "segundos": 70})[0] == 409)
        s, v = http("POST", "/videos", {"idea": "Por qué estudiar cocina", "keyword": "estudiar cocina en lima", "segundos": 20, "formato": "vertical"})
        cod_v = v["codigo"]
        comprobar("crea la idea", s == 201 and cod_v == "V0001" and v["estado"] == "IDEA" and v["formato"] == "VERTICAL", str(v)[:200])
        comprobar("sin guion no se genera", http("POST", f"/videos/{cod_v}/generar")[0] == 409)
        s, v = http("POST", f"/videos/{cod_v}/guion")
        comprobar("Gemini escribe 2 partes de 10 s y los copys", s == 200 and v["estado"] == "GUION" and len(v["partes"]) == 2
                  and v["copyFacebook"] and v["copyInstagram"] and v["hashtags"] == ["#LeCordonBleuPeru"], str(v)[:300])
        comprobar("le pasa el negocio y el contexto", estado["video_contexto"]["pronunciaciones"][0]["dice"] == "Le Cordón Blé" and estado["video_contexto"]["negocio"])
        s, pr = http("GET", f"/videos/{cod_v}/prompts")
        comprobar("los prompts dicen la marca como se pronuncia; el guion la escribe bien",
                  s == 200 and len(pr["prompts"]) == 2 and "Le Cordón Blé" in pr["prompts"][0] and "Le Cordon Bleu" in v["partes"][0]["dialogo"], str(pr)[:300])
        http("PUT", f"/videos/{cod_v}", {"segundos": 40})
        e = http("POST", f"/videos/{cod_v}/generar")
        comprobar("40 s con 2 partes: no genera y explica", e[0] == 409 and "4 partes" in e[1]["error"], str(e))
        partes = [{"dialogo": "Empieza el [FALTA: fecha de inicio].", "escena": ""}, {"dialogo": "Te esperamos.", "escena": ""}]
        http("PUT", f"/videos/{cod_v}", {"segundos": 20, "partes": partes})
        e = http("POST", f"/videos/{cod_v}/generar")
        comprobar("con [FALTA] no gasta generaciones", e[0] == 409 and "fecha de inicio" in e[1]["error"], str(e))
        partes[0]["dialogo"] = "Estudia en Le Cordon Bleu."
        http("PUT", f"/videos/{cod_v}", {"partes": partes})
        s, v = http("POST", f"/videos/{cod_v}/generar")
        comprobar("lanza la generación en Vids", s == 202 and v["estado"] == "GENERANDO", str(v)[:200])
        comprobar("al robot le llegan los prompts, el formato y la duración",
                  estado["video_lanzado"]["formato"] == "VERTICAL" and estado["video_lanzado"]["segundos"] == 20
                  and len(estado["video_lanzado"]["prompts"]) == 2 and "Radar V0001" in estado["video_lanzado"]["titulo"], str(estado["video_lanzado"])[:200])
        comprobar("no se edita mientras se genera", http("PUT", f"/videos/{cod_v}", {"titulo": "Otro"})[0] == 409)
        s, v2 = http("POST", "/videos", {"idea": "Otra idea de video", "segundos": 10})
        http("PUT", f"/videos/{v2['codigo']}", {"partes": [{"dialogo": "Hola.", "escena": ""}]})
        comprobar("un video a la vez en Vids", http("POST", f"/videos/{v2['codigo']}/generar")[0] == 409)
        for _ in range(30):
            v = http("GET", f"/videos/{cod_v}")[1]
            if v["estado"] != "GENERANDO":
                break
            time.sleep(2)
        comprobar("al terminar guarda el video", v["estado"] == "GENERADO" and v["tieneArchivo"] and v["segundosReales"] == 20.0 and v["vidsUrl"], str(v)[:300])
        s, archivo, tipo = bajar(f"/videos/{cod_v}/archivo")
        comprobar("sirve el MP4", s == 200 and archivo == MP4_PRUEBA and tipo.startswith("video/mp4"), f"{s} {tipo}")
        r = urllib.request.Request(BASE + f"/videos/{cod_v}/archivo", headers={"cookie": PRINCIPAL["c"], "Range": "bytes=0-99"})
        resp = urllib.request.urlopen(r, timeout=30)
        comprobar("admite saltar en el reproductor (Range)", resp.status == 206 and len(resp.read()) == 100, str(resp.status))
        comprobar("un miembro no aprueba", http("PUT", f"/videos/{cod_v}/aprobacion", {"aprobado": True}, eva)[0] == 403)
        s, v = http("PUT", f"/videos/{cod_v}/aprobacion", {"aprobado": True})
        comprobar("el admin aprueba", s == 200 and v["estado"] == "APROBADO")
        comprobar("un video sin aprobar no pasa a publicaciones", http("POST", f"/publicaciones/desde-video/{v2['codigo']}")[0] == 409)
        s, pv = http("POST", f"/publicaciones/desde-video/{cod_v}")
        comprobar("el video aprobado pasa a publicaciones con sus copys y su MP4",
                  s == 200 and pv["origen"] == "VIDEO" and pv["codOrigen"] == cod_v and pv["media"] == "VIDEO" and pv["redes"] == ["FACEBOOK", "INSTAGRAM"]
                  and pv["textos"] == {"FACEBOOK": "Copy de Facebook", "INSTAGRAM": "Copy de Instagram"} and pv["hashtags"] == ["#LeCordonBleuPeru"], str(pv)[:300])
        comprobar("pedirlo otra vez abre la misma", http("POST", f"/publicaciones/desde-video/{cod_v}")[1]["codigo"] == pv["codigo"])
        s, v = http("PUT", f"/videos/{cod_v}", {"partes": [{"dialogo": "Otro texto.", "escena": ""}, {"dialogo": "Te esperamos.", "escena": ""}]})
        comprobar("cambiar el guion de un video aprobado lo devuelve a guion", s == 200 and v["estado"] == "GUION", v["estado"])
        comprobar("un miembro no borra", http("DELETE", f"/videos/{cod_v}", None, eva)[0] == 403)
        comprobar("el admin borra el video y su archivo", http("DELETE", f"/videos/{cod_v}")[0] == 204 and http("GET", f"/videos/{cod_v}")[0] == 404)
        comprobar("la publicación conserva su copia del video", bajar(f"/publicaciones/{pv['codigo']}/archivo")[1] == MP4_PRUEBA)
        comprobar("el navegador de Vids se consulta", http("GET", "/videos/navegador")[1]["abierto"] is True)

        print("publicaciones: textos, archivo, aprobación y enlaces")
        comprobar("sin redes: rechazada", http("POST", "/publicaciones", {"idea": "Admisión 2027", "redes": []})[0] == 409)
        comprobar("red desconocida: rechazada", http("POST", "/publicaciones", {"idea": "Admisión 2027", "redes": ["tiktok"]})[0] == 409)
        s, pu = http("POST", "/publicaciones", {"idea": "Abrimos la admisión 2027-1", "redes": ["linkedin", "facebook", "instagram"]})
        cod_p = pu["codigo"]
        comprobar("crea un borrador con las redes en orden fijo", s == 201 and pu["estado"] == "BORRADOR" and pu["redes"] == ["FACEBOOK", "INSTAGRAM", "LINKEDIN"]
                  and pu["media"] == "NINGUNA", str(pu)[:200])
        s, pu = http("POST", f"/publicaciones/{cod_p}/textos")
        comprobar("la IA escribe un texto por red con los datos confirmados",
                  s == 200 and set(pu["textos"]) == {"FACEBOOK", "INSTAGRAM", "LINKEDIN"} and pu["hashtags"] == ["#LeCordonBleuPeru", "#Gastronomía", "#Chef"]
                  and estado["pub_pedido"]["modo"] == "POR_RED" and estado["pub_pedido"]["hashtags_base"] == ["#LeCordonBleuPeru", "#Gastronomía"]
                  and estado["pub_pedido"]["contexto"]["datos"] and estado["pub_pedido"]["media"] == "NINGUNA", str(pu)[:300])
        s, e = http("PUT", f"/publicaciones/{cod_p}/aprobacion", {"aprobada": True})
        comprobar("no se aprueba sin imagen para Instagram ni con datos por completar",
                  s == 409 and "Instagram necesita" in e["error"] and "fecha de inicio" in e["error"], str(e))
        comprobar("en borrador no se registran enlaces", http("PUT", f"/publicaciones/{cod_p}/enlaces", {"red": "FACEBOOK", "url": "https://www.facebook.com/x/posts/1"})[0] == 409)
        s, e = subir_archivo(f"/publicaciones/{cod_p}/archivo", "falsa.jpg", b"no soy una imagen")
        comprobar("rechaza lo que no es imagen ni video aunque diga .jpg", s == 409 and "JPG o PNG" in e["error"], str(e))
        s, pu = subir_archivo(f"/publicaciones/{cod_p}/archivo", "foto.png", PNG_PRUEBA)
        comprobar("sube una imagen PNG", s == 200 and pu["media"] == "IMAGEN" and pu["archivoTipo"] == "image/png", str(pu)[:200])
        s, contenido, tipo = bajar(f"/publicaciones/{cod_p}/archivo")
        comprobar("la sirve tal cual", s == 200 and contenido == PNG_PRUEBA and tipo.startswith("image/png"), f"{s} {tipo}")
        s, pu = subir_archivo(f"/publicaciones/{cod_p}/archivo", "reel.mp4", MP4_PRUEBA)
        comprobar("cambiarla por un video reemplaza la imagen", s == 200 and pu["media"] == "VIDEO" and bajar(f"/publicaciones/{cod_p}/archivo")[1] == MP4_PRUEBA)
        subir_archivo(f"/publicaciones/{cod_p}/archivo", "foto.png", PNG_PRUEBA)
        texto_li = pu["textos"]["LINKEDIN"].replace("[FALTA: fecha de inicio]", "el 15 de marzo")
        s, pu = http("PUT", f"/publicaciones/{cod_p}", {"textos": {**pu["textos"], "LINKEDIN": texto_li}, "hashtags": ["LeCordonBleuPeru", "#Chef", "#Chef", "mal hashtag"]})
        comprobar("guarda los textos y limpia los hashtags", s == 200 and pu["textos"]["LINKEDIN"] == texto_li and pu["hashtags"] == ["#LeCordonBleuPeru", "#Chef"], str(pu)[:300])
        comprobar("un miembro no aprueba", http("PUT", f"/publicaciones/{cod_p}/aprobacion", {"aprobada": True}, eva)[0] == 403)
        s, pu = http("PUT", f"/publicaciones/{cod_p}/aprobacion", {"aprobada": True})
        comprobar("el admin aprueba", s == 200 and pu["estado"] == "APROBADA" and pu["aprobador"], str(pu)[:200])
        s, pu = http("PUT", f"/publicaciones/{cod_p}", {"titulo": "Admisión 2027-1"})
        comprobar("cambiarla ya aprobada la devuelve a borrador", s == 200 and pu["estado"] == "BORRADOR")
        http("PUT", f"/publicaciones/{cod_p}/aprobacion", {"aprobada": True})
        comprobar("un enlace de otra red se rechaza", http("PUT", f"/publicaciones/{cod_p}/enlaces", {"red": "FACEBOOK", "url": "https://www.instagram.com/p/abc/"})[0] == 409)
        comprobar("un enlace sin https se rechaza", http("PUT", f"/publicaciones/{cod_p}/enlaces", {"red": "FACEBOOK", "url": "facebook.com/x"})[0] == 409)
        s, pu = http("PUT", f"/publicaciones/{cod_p}/enlaces", {"red": "facebook", "url": "https://www.facebook.com/ilcb/posts/123"})
        comprobar("registra el enlace de una red y sigue por publicar en las demás",
                  s == 200 and pu["enlaces"] == {"FACEBOOK": "https://www.facebook.com/ilcb/posts/123"} and pu["estado"] == "APROBADA", str(pu)[:200])
        comprobar("publicada en una red ya no se edita ni se cambia el archivo",
                  http("PUT", f"/publicaciones/{cod_p}", {"titulo": "Otro"})[0] == 409 and subir_archivo(f"/publicaciones/{cod_p}/archivo", "foto.png", PNG_PRUEBA)[0] == 409)
        comprobar("ni se le quita la aprobación", http("PUT", f"/publicaciones/{cod_p}/aprobacion", {"aprobada": False})[0] == 409)
        http("PUT", f"/publicaciones/{cod_p}/enlaces", {"red": "INSTAGRAM", "url": "https://www.instagram.com/p/abc/"})
        s, pu = http("PUT", f"/publicaciones/{cod_p}/enlaces", {"red": "LINKEDIN", "url": "https://www.linkedin.com/feed/update/urn:li:activity:1/"})
        comprobar("con todas las redes queda publicada", s == 200 and pu["estado"] == "PUBLICADA")
        s, pu = http("PUT", f"/publicaciones/{cod_p}/enlaces", {"red": "LINKEDIN", "url": ""})
        comprobar("quitar un enlace la devuelve a por publicar", s == 200 and pu["estado"] == "APROBADA" and "LINKEDIN" not in pu["enlaces"])
        s, p2 = http("POST", "/publicaciones", {"idea": "Taller abierto de panadería", "redes": ["FACEBOOK", "LINKEDIN"]})
        http("PUT", f"/publicaciones/{p2['codigo']}", {"textos": {"FACEBOOK": "Hola", "LINKEDIN": "Hola"}})
        comprobar("solo texto para Facebook y LinkedIn se aprueba sin imagen", http("PUT", f"/publicaciones/{p2['codigo']}/aprobacion", {"aprobada": True})[1]["estado"] == "APROBADA")
        comprobar("la lista trae todas, la más nueva primero", [x["codigo"] for x in http("GET", "/publicaciones")[1]][:2] == [p2["codigo"], cod_p])
        print("publicaciones: biblioteca (historial, comprobación y archivo)")
        hist = http("GET", f"/publicaciones/{cod_p}/historial")[1]
        tipos = [e["evento"] for e in hist]
        comprobar("el historial guarda cada paso con su autor", tipos[0] == "CREADA" and "TEXTOS" in tipos and "APROBADA" in tipos
                  and "EDITADA" in tipos and "ENLACE_QUITADO" in tipos and all(e["autor"] for e in hist if e["evento"] != "FLYER"), str(tipos))
        fb = next(e for e in hist if e["evento"] == "PUBLICADA" and e["datos"]["red"] == "FACEBOOK")
        comprobar("y el texto exacto que se publicó en cada red, con sus hashtags", fb["datos"]["url"] == "https://www.facebook.com/ilcb/posts/123"
                  and fb["datos"]["texto"].startswith("Texto de Facebook") and "#LeCordonBleuPeru" in fb["datos"]["texto"], str(fb))
        comprobar("sin enlaces no hay nada que comprobar", http("POST", f"/publicaciones/{p2['codigo']}/verificar")[0] == 409)
        http("PUT", f"/publicaciones/{cod_p}/enlaces", {"red": "LINKEDIN", "url": "https://www.linkedin.com/feed/update/urn:li:activity:1/"})
        s, pu = http("POST", f"/publicaciones/{cod_p}/verificar", None, eva)
        comprobar("comprueba cada enlace publicado y guarda el resultado", s == 200 and pu["verificacion"]["FACEBOOK"]["estado"] == "ACTIVA"
                  and pu["verificacion"]["LINKEDIN"]["estado"] == "NO_DISPONIBLE" and set(estado["verificados"]["enlaces"]) == {"FACEBOOK", "INSTAGRAM", "LINKEDIN"}
                  and estado["verificados"]["textos"]["FACEBOOK"].startswith("Texto de Facebook"), str(pu.get("verificacion"))[:300])
        comprobar("y lo anota en el historial", sum(e["evento"] == "VERIFICADA" for e in http("GET", f"/publicaciones/{cod_p}/historial")[1]) == 3)
        comprobar("un miembro no archiva", http("DELETE", f"/publicaciones/{cod_p}", None, eva)[0] == 403)
        s, pu = http("DELETE", f"/publicaciones/{cod_p}")
        comprobar("archivar no borra: sale de la lista, sigue en la biblioteca con su archivo",
                  s == 200 and pu["archivada"] and http("GET", f"/publicaciones/{cod_p}")[0] == 200
                  and cod_p not in [x["codigo"] for x in http("GET", "/publicaciones")[1]]
                  and cod_p in [x["codigo"] for x in http("GET", "/publicaciones?archivadas=true")[1]]
                  and bajar(f"/publicaciones/{cod_p}/archivo")[0] == 200, str(pu)[:200])
        comprobar("archivada no se edita", http("PUT", f"/publicaciones/{p2['codigo']}", {"titulo": "x"})[0] == 200
                  and http("DELETE", f"/publicaciones/{p2['codigo']}")[0] == 200 and http("PUT", f"/publicaciones/{p2['codigo']}", {"titulo": "y"})[0] == 409)
        r = http("POST", "/publicaciones/verificar")[1]
        comprobar("comprobar todas: también las archivadas con enlaces", r["publicaciones"] == 1 and r["enlaces"] == 3
                  and r.get("ACTIVA") == 2 and r.get("NO_DISPONIBLE") == 1, str(r))
        print("publicaciones: UTM en los enlaces a la web propia")
        comprobar("la marca dice qué dominios llevan UTM", http("GET", "/publicaciones/marca")[1]["dominios"] == ["ilcb.edu.pe"])
        s, p3 = http("POST", "/publicaciones", {"idea": "Admisión abierta", "redes": ["FACEBOOK", "LINKEDIN"]})
        http("PUT", f"/publicaciones/{p3['codigo']}", {"titulo": "¡Admisión 2027-1 ya!", "textos": {
            "FACEBOOK": "Inscríbete en https://ilcb.edu.pe/admision/. Más en https://otra.com/x",
            "LINKEDIN": "Ver https://www.ilcb.edu.pe/carreras/?ref=1#top y https://ilcb.edu.pe/x?utm_source=yo"}})
        http("PUT", f"/publicaciones/{p3['codigo']}/aprobacion", {"aprobada": True})
        http("PUT", f"/publicaciones/{p3['codigo']}/enlaces", {"red": "FACEBOOK", "url": "https://www.facebook.com/ilcb/posts/9"})
        http("PUT", f"/publicaciones/{p3['codigo']}/enlaces", {"red": "LINKEDIN", "url": "https://www.linkedin.com/feed/update/9"})
        pub = {e["datos"]["red"]: e["datos"]["texto"] for e in http("GET", f"/publicaciones/{p3['codigo']}/historial")[1] if e["evento"] == "PUBLICADA"}
        cod3 = p3["codigo"].lower()
        comprobar("Facebook: UTM en el enlace propio, la puntuación fuera y el ajeno intacto",
                  f"https://ilcb.edu.pe/admision/?utm_source=facebook&utm_medium=social&utm_campaign=admision-2027-1-ya&utm_content={cod3}. Más en https://otra.com/x"
                  in pub["FACEBOOK"], pub["FACEBOOK"])
        comprobar("LinkedIn: respeta la consulta y el ancla, y no toca un enlace que ya trae UTM",
                  f"https://www.ilcb.edu.pe/carreras/?ref=1&utm_source=linkedin&utm_medium=social&utm_campaign=admision-2027-1-ya&utm_content={cod3}#top" in pub["LINKEDIN"]
                  and "https://ilcb.edu.pe/x?utm_source=yo" in pub["LINKEDIN"] and pub["LINKEDIN"].count("utm_source") == 2, pub["LINKEDIN"])
        s, pu = http("POST", f"/publicaciones/{p2['codigo']}/restaurar")
        comprobar("restaurar la devuelve a la lista", s == 200 and not pu["archivada"]
                  and p2["codigo"] in [x["codigo"] for x in http("GET", "/publicaciones")[1]]
                  and [e["evento"] for e in http("GET", f"/publicaciones/{p2['codigo']}/historial")[1]][-2:] == ["ARCHIVADA", "RESTAURADA"])

        print("publicaciones: el mismo texto, flyer y marca")
        s, m = http("GET", "/publicaciones/marca")
        comprobar("marca por defecto: azul y dorado, hashtags del rubro y sin logo",
                  s == 200 and m["color"] == "#0B1F3F" and m["hashtags"] == ["#LeCordonBleuPeru", "#Gastronomía"] and not m["tieneLogo"], str(m))
        comprobar("un miembro no cambia la marca", http("PUT", "/publicaciones/marca", {**m, "color": "#000000"}, eva)[0] == 403)
        comprobar("un color mal escrito se rechaza", http("PUT", "/publicaciones/marca", {**m, "color": "azul"})[0] == 409)
        s, m = http("PUT", "/publicaciones/marca", {"color": "#5a1020", "acento": "#F2C14E", "hashtags": ["LeCordonBleuPeru", "#Pastelería"]})
        comprobar("el admin la guarda", s == 200 and m["color"] == "#5A1020" and m["hashtags"] == ["#LeCordonBleuPeru", "#Pastelería"], str(m))
        comprobar("un logo que no es imagen se rechaza", subir_archivo("/publicaciones/marca/logo", "logo.txt", b"hola")[0] == 409)
        comprobar("un miembro no sube el logo", subir_archivo("/publicaciones/marca/logo", "logo.png", PNG_PRUEBA, eva)[0] == 403)
        s, m = subir_archivo("/publicaciones/marca/logo", "logo.png", PNG_PRUEBA)
        comprobar("sube el logo", s == 200 and m["tieneLogo"] and bajar("/publicaciones/marca/logo")[1] == PNG_PRUEBA)
        comprobar("modo de texto desconocido: rechazado", http("POST", "/publicaciones", {"idea": "Taller", "redes": ["FACEBOOK"], "modoCopy": "OTRO"})[0] == 409)
        s, pf = http("POST", "/publicaciones", {"idea": "Ven y conoce nuestro Campus", "redes": ["FACEBOOK", "INSTAGRAM", "LINKEDIN"], "modoCopy": "MISMO"})
        cod_f = pf["codigo"]
        s, pf = http("POST", f"/publicaciones/{cod_f}/textos")
        comprobar("el mismo texto en las tres redes, con los hashtags del rubro delante",
                  s == 200 and pf["modoCopy"] == "MISMO" and len(pf["textos"]) == 3 and len(set(pf["textos"].values())) == 1
                  and estado["pub_pedido"]["modo"] == "MISMO" and pf["hashtags"] == ["#LeCordonBleuPeru", "#Pastelería", "#Chef"], str(pf)[:300])
        comprobar("la IA propone los textos del flyer", pf["flyer"]["titulo"] == "Ven y conoce el campus" and pf["flyer"]["busqueda"] == "chef cocina"
                  and not pf["flyer"]["tieneFondo"] and not pf["flyer"]["enUso"], str(pf["flyer"]))
        comprobar("sin fondo no se arma el flyer", http("POST", f"/publicaciones/{cod_f}/flyer")[0] == 409)
        s, fb = http("GET", "/publicaciones/fotos?consulta=chef%20cocina")
        comprobar("busca fotos verticales para el fondo", s == 200 and fb["fotos"][0]["id"] == 9 and estado["foto_orientacion"] == "vertical", str(fb)[:200])
        s, pf = http("POST", f"/publicaciones/{cod_f}/fondo/foto", {"id": 9})
        comprobar("al elegir la foto arma el flyer con sus textos, el logo y los colores de la marca",
                  s == 200 and pf["media"] == "IMAGEN" and pf["archivoTipo"] == "image/jpeg" and pf["flyer"]["enUso"]
                  and pf["flyer"]["fondoCredito"] == "Foto: Ana en Pixabay" and estado["flyer"]["titulo"] == "Ven y conoce el campus"
                  and estado["flyer"]["logo"] == PNG_PRUEBA and estado["flyer"]["color"] == "#5A1020" and estado["flyer"]["fondo"] == JPG_PRUEBA, str(pf)[:300])
        comprobar("sirve el flyer", bajar(f"/publicaciones/{cod_f}/archivo")[1] == FLYER_PRUEBA)
        s, e = http("PUT", f"/publicaciones/{cod_f}/aprobacion", {"aprobada": True})
        comprobar("con «[FALTA]» en el flyer no se aprueba", s == 409 and "fecha" in e["error"], str(e))
        n = estado["flyer_llamadas"]
        s, pf = http("PUT", f"/publicaciones/{cod_f}", {"flyer": {**pf["flyer"], "detalle": "Sábado 15 de noviembre"}})
        comprobar("cambiar los textos del flyer lo vuelve a armar",
                  s == 200 and pf["flyer"]["detalle"] == "Sábado 15 de noviembre" and estado["flyer_llamadas"] == n + 1 and estado["flyer"]["detalle"] == "Sábado 15 de noviembre")
        s, pf = http("POST", f"/publicaciones/{cod_f}/fondo/ia", {"descripcion": "Una cocina luminosa"})
        comprobar("fondo con IA: pide formato vertical y rearma el flyer",
                  s == 200 and estado["imagen_pedida"]["formato"] == "VERTICAL" and pf["flyer"]["fondoOrigen"] == "IA" and pf["flyer"]["enUso"], str(pf)[:200])
        estado.pop("imagen_pedida")   # el Plan SEO comprueba despues que no se pidio ninguna
        s, pf = subir_archivo(f"/publicaciones/{cod_f}/fondo", "campus.png", PNG_PRUEBA)
        comprobar("foto propia de fondo", s == 200 and pf["flyer"]["fondoOrigen"] == "PROPIA" and pf["flyer"]["enUso"] and estado["flyer"]["fondo"] == PNG_PRUEBA)
        s, pf = subir_archivo(f"/publicaciones/{cod_f}/archivo", "reel.mp4", MP4_PRUEBA)
        comprobar("un archivo propio reemplaza al flyer, que queda guardado", s == 200 and pf["media"] == "VIDEO" and not pf["flyer"]["enUso"] and pf["flyer"]["tieneFondo"])
        s, pf = http("POST", f"/publicaciones/{cod_f}/flyer")
        comprobar("y se puede volver al flyer", s == 200 and pf["media"] == "IMAGEN" and pf["flyer"]["enUso"] and bajar(f"/publicaciones/{cod_f}/archivo")[1] == FLYER_PRUEBA)
        s, pf = http("PUT", f"/publicaciones/{cod_f}/aprobacion", {"aprobada": True})
        comprobar("completa, se aprueba", s == 200 and pf["estado"] == "APROBADA", str(pf)[:200])
        s, m = http("DELETE", "/publicaciones/marca/logo")
        comprobar("quita el logo", s == 200 and not m["tieneLogo"] and bajar("/publicaciones/marca/logo")[0] == 404)
        hist = [e["evento"] for e in http("GET", f"/publicaciones/{cod_f}/historial")[1]]
        comprobar("el historial anota fondos, flyers y archivos", {"FONDO", "FLYER", "ARCHIVO"} <= set(hist), str(hist))
        comprobar("archiva la publicación y conserva su flyer", http("DELETE", f"/publicaciones/{cod_f}")[0] == 200
                  and bajar(f"/publicaciones/{cod_f}/archivo")[1] == FLYER_PRUEBA)

        print("medición: Meta, alertas, informe con IA y GA4")
        hoy_m, fin_m = (_fecha_hoy := __import__("datetime").date.today()), __import__("datetime").date.today() - __import__("datetime").timedelta(days=1)
        td = __import__("datetime").timedelta

        def esperar_meta(segundos=30):
            fin_t = time.time() + segundos
            while time.time() < fin_t:
                e = http("GET", "/medicion/estado")[1]
                if (e.get("sincronizacion") or {}).get("estado") != "EN_CURSO":
                    return e
                time.sleep(0.3)
            return e
        s, e = http("GET", "/medicion/estado")
        comprobar("estado: Meta y GA4 conectados, aún sin datos", s == 200 and e["meta"]["completo"] and e["meta"]["detalle"]["moneda"] == "USD"
                  and e["ga4"]["completo"] and e["datos"] is None and e["sincronizacion"] is None, str(e))
        s, t = http("POST", "/medicion/meta/sincronizar", {}, eva)
        comprobar("la primera vez trae 90 días en segundo plano", s == 202 and t["estado"] == "EN_CURSO"
                  and t["desde"] == (hoy_m - td(days=89)).isoformat() and t["hasta"] == hoy_m.isoformat(), str(t))
        e = esperar_meta()
        comprobar("y guarda una fila por anuncio y día", e["sincronizacion"]["estado"] == "LISTA" and e["datos"]["filas"] == 4 * 90 + 8
                  and e["datos"]["hasta"] == hoy_m.isoformat(), str(e.get("sincronizacion")))
        http("POST", "/medicion/meta/sincronizar", {})
        e = esperar_meta()
        comprobar("después vuelve a traer desde 7 días antes de lo último (Meta corrige la atribución)",
                  estado["meta_pedidas"][-1] == ((hoy_m - td(days=7)).isoformat(), hoy_m.isoformat()) and e["datos"]["filas"] == 4 * 90 + 8, str(estado["meta_pedidas"]))
        comprobar("fecha mal escrita: 409", http("POST", "/medicion/meta/sincronizar", {"desde": "ayer"})[0] == 409)

        desde_m, hasta_m = (fin_m - td(days=13)).isoformat(), fin_m.isoformat()
        s, r = http("GET", f"/medicion/resumen?desde={desde_m}&hasta={hasta_m}")
        k, ka = r["kpis"], r["kpisAnterior"]
        comprobar("totales del periodo", s == 200 and k["gasto"] == 679.0 and k["impresiones"] == 189000 and k["campanas"] == 4 and k["anuncios"] == 5, str(k))
        comprobar("leads y conversaciones aparte, cada costo con el gasto de su tipo de campaña",
                  k["leads"] == 56 and k["costoLead"] == 4.38 and k["gastoLeads"] == 245.0 and k["conversaciones"] == 252
                  and k["costoConversacion"] == 1.44 and k["gastoSinResultados"] == 70.0, str(k))
        comprobar("y el periodo anterior de la misma duración", r["anterior"] == {"desde": (fin_m - td(days=27)).isoformat(), "hasta": (fin_m - td(days=14)).isoformat()}
                  and ka["leads"] == 70 and ka["costoLead"] == 2.0, str(ka))
        c = {x["id"]: x for x in r["campanas"]}
        comprobar("cada campaña con su tipo, partes del nombre y cambio del costo", c["c1"]["tipo"] == "LEADS" and c["c1"]["producto"] == "Pastelería"
                  and c["c1"]["canal"] == "Lead Ads" and c["c2"]["tipo"] == "CONVERSACIONES" and c["c3"]["tipo"] == "SIN_RESULTADOS"
                  and c["c3"]["linea"] is None and c["c1"]["costoAnterior"] == 2.0 and c["c1"]["cambioCosto"] > 1
                  and r["campanas"][0]["id"] == "c2", str(r["campanas"][:2]))
        comprobar("serie diaria y anuncios ordenados por gasto", len(r["serie"]) == 14 and r["serie"][-1]["fecha"] == hasta_m
                  and r["serie"][-1]["leads"] == 3 and r["anuncios"][0]["id"] == "b1" and next(a for a in r["anuncios"] if a["id"] == "a2")["costoResultado"] is None)
        tipos_alerta = sorted(a["tipo"] for a in r["alertas"])
        comprobar("alertas: se encarece c1, a2 gasta sin leads, c2 pierde CTR y c4 rinde mejor (nada más)",
                  tipos_alerta == ["COSTO_SUBE", "CTR_BAJA", "RINDE_MEJOR", "SIN_RESULTADOS"]
                  and {a["tipo"]: a["id"] for a in r["alertas"]} == {"COSTO_SUBE": "c1", "CTR_BAJA": "c2", "RINDE_MEJOR": "c4", "SIN_RESULTADOS": "a2"}
                  and r["alertas"][0]["nivel"] == "ALTA" and "USD" in r["alertas"][0]["detalle"], str(r["alertas"]))
        comprobar("periodo al revés o fechas raras: 409", http("GET", f"/medicion/resumen?desde={hasta_m}&hasta={desde_m}")[0] == 409
                  and http("GET", "/medicion/resumen?desde=x&hasta=y")[0] == 409)
        comprobar("sin datos en el periodo no hay informe que hacer", http("POST", "/medicion/informe", {"desde": "2020-01-01", "hasta": "2020-01-07"})[0] == 409)
        s, inf = http("POST", "/medicion/informe", {"desde": desde_m, "hasta": hasta_m}, eva)
        ia = estado.get("medicion_ia") or {}
        comprobar("informe con IA: le pasa las cifras ya calculadas, las alertas y GA4",
                  s == 200 and inf["ia"]["titular"] == "Pastelería se encarece" and ia["kpis"]["gasto"] == 679.0 and len(ia["alertas"]) == 4
                  and ia["ga4"]["canales"][0]["sessions"] == 100 and set(ia["campanas"][0]) <= {"nombre", "tipo", "gasto", "resultados", "costoResultado",
                  "costoAnterior", "cambioCosto", "ctrPorcentaje", "leads", "conversaciones", "pocosResultados"}
                  and ia["kpis"]["ctrPorcentaje"] is not None and "ctr" not in ia["kpis"], str(inf)[:300])
        comprobar("a la IA no le llega el costo de una campaña con pocos resultados", all(
            c.get("pocosResultados") and c["costoResultado"] is None for c in ia["campanas"] if c["tipo"] != "SIN_RESULTADOS" and c["resultados"] < 10)
            and any(c["resultados"] >= 10 and c["costoResultado"] for c in ia["campanas"]), str(ia["campanas"]))
        lista = http("GET", "/seo/informes?modulo=MEDICION")[1]
        comprobar("y queda guardado con sus cifras, el resumen y las campañas", len(lista) == 1 and lista[0]["codigo"] == inf["informe"]["codigo"]
                  and lista[0]["resumen"]["kpis"]["leads"] == 56 and lista[0]["resumen"]["ia"]["titular"] == "Pastelería se encarece"
                  and lista[0]["filas"] == 4 and lista[0]["autor"], str(lista)[:300])
        s, csv, tipo = bajar(f"/seo/informes/{lista[0]['codigo']}/csv")
        comprobar("en CSV, una fila por campaña", s == 200 and csv.decode("utf-8").startswith("\ufeffnombre,tipo,linea") and len(csv.decode("utf-8").strip().splitlines()) == 5)
        s, g = http("GET", f"/medicion/ga4?desde={desde_m}&hasta={hasta_m}")
        comprobar("GA4: canales y eventos clave del periodo", s == 200 and g["canales"][0]["sessionDefaultChannelGroup"] == "Paid Social"
                  and g["desde"] == desde_m, str(g)[:200])
        comprobar("GA4: las propiedades que ve la cuenta", http("GET", "/medicion/ga4/propiedades")[1]["propiedades"][0]["propiedad"] == "123")
        estado["meta_conectado"] = False
        e = http("GET", "/medicion/estado")[1]
        comprobar("Meta sin conectar: dice qué falta", not e["meta"]["completo"] and e["meta"]["faltan"] == ["META_ACCESS_TOKEN"], str(e["meta"]))
        http("POST", "/medicion/meta/sincronizar", {})
        e = esperar_meta()
        comprobar("y si se intenta, la sincronización queda en error con el motivo, sin borrar lo guardado",
                  e["sincronizacion"]["estado"] == "ERROR" and "META_ACCESS_TOKEN" in e["sincronizacion"]["error"] and e["datos"]["filas"] == 4 * 90 + 8,
                  str(e["sincronizacion"]))
        estado["meta_conectado"] = True

        print("keywords: estado, búsqueda y caché")
        s, e = http("GET", "/keywords/estado")
        comprobar("estado: Google Ads sin conectar dice qué falta", s == 200 and not e["google_ads"]["completo"] and "developer_token" in e["google_ads"]["faltan"] and e["paises"]["PE"] == "Perú", str(e)[:200])
        comprobar("sin sesión no se puede explorar", http("POST", "/keywords/explorar", {"semillas": ["a"], "demo": True}, {"c": ""})[0] == 401)
        s, k1 = http("POST", "/keywords/explorar", {"semillas": ["curso de cocina"], "pais": "PE", "idioma": "es", "demo": True})
        res = k1["resultado"]
        comprobar("explora en demo: filas, términos y totales", s == 200 and k1["desdeCache"] is False and res["demo"] and len(res["filas"]) > 40 and res["terminos"] and res["totales"]["keywords"] == len(res["filas"]), str(k1)[:200])
        comprobar("las filas traen sus métricas y marcas", all(f["tendencia"] and f["competencia"] and f["tipo"] in ("coincidente", "relacionado") for f in res["filas"][:20]))
        s, k2 = http("POST", "/keywords/explorar", {"semillas": ["Curso de Cocina"], "pais": "pe", "idioma": "ES", "demo": True})
        comprobar("repetir la búsqueda sale de la caché (mayúsculas no cuentan)", k2["desdeCache"] is True and k2["busqueda"]["codigo"] == k1["busqueda"]["codigo"])
        s, k3 = http("POST", "/keywords/explorar", {"semillas": ["curso de cocina"], "demo": True, "refrescar": True})
        comprobar("refrescar vuelve a consultar y reutiliza la misma entrada", k3["desdeCache"] is False and k3["busqueda"]["codigo"] == k1["busqueda"]["codigo"])
        s, k4 = http("POST", "/keywords/explorar", {"semillas": ["curso de cocina"], "pais": "MX", "demo": True})
        comprobar("otro país es otra búsqueda", k4["busqueda"]["codigo"] != k1["busqueda"]["codigo"] and k4["resultado"]["pais"] == "MX")
        s, k5 = http("POST", "/keywords/explorar", {"semillas": [], "url": "https://www.escuela.pe/cursos", "demo": True})
        comprobar("explora desde una URL", s == 200 and k5["resultado"]["url"] == "https://www.escuela.pe/cursos" and len(k5["resultado"]["filas"]) > 20)
        s, r = http("POST", "/keywords/explorar", {"semillas": ["curso de cocina"]})
        comprobar("sin demo y sin Google Ads conectado: error claro", s == 502 and "Falta conectar Google Ads" in r["error"], str(r))
        comprobar("valida lo que se pide", http("POST", "/keywords/explorar", {"semillas": []})[0] == 409
                  and http("POST", "/keywords/explorar", {"semillas": [str(i) for i in range(21)], "demo": True})[0] == 409
                  and http("POST", "/keywords/explorar", {"url": "ftp://x", "demo": True})[0] == 409
                  and http("POST", "/keywords/explorar", {"semillas": ["a"], "maximo": 5, "demo": True})[0] == 409)
        s, r = http("POST", "/keywords/explorar", {"semillas": ["a"], "pais": "ZZ", "demo": True})
        comprobar("un país que Google no tiene se explica", s == 502 and "no soportado" in r["error"], str(r))
        busquedas = http("GET", "/keywords/busquedas")[1]
        comprobar("historial de búsquedas", len(busquedas) >= 3 and busquedas[0]["totalKeywords"] > 0 and busquedas[0]["demo"] is True)
        s, ab = http("GET", f"/keywords/busquedas/{k1['busqueda']['codigo']}")
        comprobar("reabrir una búsqueda del historial", s == 200 and len(ab["resultado"]["filas"]) == len(res["filas"]))
        comprobar("borrar una búsqueda", http("DELETE", f"/keywords/busquedas/{k4['busqueda']['codigo']}")[0] == 204 and http("GET", f"/keywords/busquedas/{k4['busqueda']['codigo']}")[0] == 404)

        print("keywords: resumen y conexión")
        s, rs = http("POST", "/keywords/resumen", {"keyword": "curso de cocina", "pais": "PE", "porPais": True, "demo": True})
        comprobar("resumen de una keyword con volumen por país", s == 200 and rs["volumen"] and len(rs["tendencia"]) == 12 and len(rs["por_pais"]) == 8 and rs["demo"], str(rs)[:200])
        comprobar("el resumen pide una keyword", http("POST", "/keywords/resumen", {"keyword": " "})[0] == 409)
        s, c = http("POST", "/keywords/comprobar")
        comprobar("el admin comprueba la conexión", s == 200 and c["ok"] is False and "Falta" in c["detalle"], str(c))
        comprobar("un miembro no la comprueba", http("POST", "/keywords/comprobar", None, eva)[0] == 403)
        comprobar("pero sí explora", http("POST", "/keywords/explorar", {"semillas": ["pan"], "demo": True}, eva)[0] == 200)

        print("keywords: listas")
        filas = res["filas"][:6] + [{**res["filas"][6], "volumen": None, "cpc": None}]
        s, li = http("POST", "/keywords/listas", {"nombre": "Cursos de cocina", "descripcion": "Para el blog", "pais": "PE", "idioma": "es", "demo": True})
        comprobar("crea una lista", s == 201 and li["codigo"] == "L0001" and li["keywords"] == 0 and li["demo"], str(li))
        comprobar("el nombre es obligatorio", http("POST", "/keywords/listas", {"nombre": " "})[0] == 409)
        s, r = http("POST", f"/keywords/listas/{li['codigo']}/items", {"items": filas, "demo": True})
        comprobar("añade keywords (incluida una sin volumen)", s == 200 and r["agregadas"] == 7 and r["repetidas"] == 0, str(r))
        s, r = http("POST", f"/keywords/listas/{li['codigo']}/items", {"items": [{**filas[0], "keyword": filas[0]["keyword"].upper()}, res["filas"][8]], "demo": True})
        comprobar("no repite (ignora mayúsculas) y suma las nuevas", r["agregadas"] == 1 and r["repetidas"] == 1, str(r))
        comprobar("no mezcla demostración con datos reales", http("POST", f"/keywords/listas/{li['codigo']}/items", {"items": filas, "demo": False})[0] == 409)
        s, det = http("GET", f"/keywords/listas/{li['codigo']}")
        comprobar("la lista trae sus keywords con métricas", s == 200 and len(det["items"]) == 8 and det["lista"]["keywords"] == 8 and det["lista"]["volumenTotal"] > 0
                  and all("nota" in i for i in det["items"]), str(det["lista"]))
        kw0 = det["items"][-1]["keyword"]
        comprobar("guarda una nota", http("PUT", f"/keywords/listas/{li['codigo']}/nota", {"keyword": kw0, "nota": "Para el artículo del lunes"})[0] == 204
                  and next(i for i in http("GET", f"/keywords/listas/{li['codigo']}")[1]["items"] if i["keyword"] == kw0)["nota"] == "Para el artículo del lunes")
        s, r = http("POST", f"/keywords/listas/{li['codigo']}/actualizar")
        det = http("GET", f"/keywords/listas/{li['codigo']}")[1]
        comprobar("actualiza las métricas y conserva las notas", s == 200 and r["actualizadas"] == 8 and all(i["volumen"] for i in det["items"])
                  and next(i for i in det["items"] if i["keyword"] == kw0)["nota"] == "Para el artículo del lunes", str(r))
        comprobar("renombra la lista", http("PUT", f"/keywords/listas/{li['codigo']}", {"nombre": "Cocina 2026", "descripcion": ""})[1]["nombre"] == "Cocina 2026")
        http("POST", f"/keywords/listas/{li['codigo']}/quitar", {"keywords": [kw0]})
        comprobar("quita keywords", len(http("GET", f"/keywords/listas/{li['codigo']}")[1]["items"]) == 7 and http("GET", "/keywords/listas")[1][0]["keywords"] == 7)
        comprobar("borra la lista con sus keywords", http("DELETE", f"/keywords/listas/{li['codigo']}")[0] == 204 and http("GET", f"/keywords/listas/{li['codigo']}")[0] == 404 and http("GET", "/keywords/listas")[1] == [])

        print("plan seo: inventario")
        s, sitios = http("GET", "/seo/sitios")
        por = {x["codigo"]: x for x in sitios or []}
        comprobar("siembra los cuatro sitios del plan", s == 200 and list(por) == ["ILCB", "DGALLIA", "CENFOTUR", "USIL"], str(sitios))
        comprobar("ILCB es el propio y CENFOTUR tiene dos hosts", por["ILCB"]["rol"] == "PROPIO" and len(por["CENFOTUR"]["hosts"]) == 2)
        comprobar("sin temas no se generan keywords", http("POST", "/seo/keywords/generar")[0] == 409)
        comprobar("sin inventario no se extraen temas", http("POST", "/seo/sitios/DGALLIA/temas")[0] == 409)
        comprobar("el máximo de páginas tiene límites", http("PUT", "/seo/sitios/DGALLIA", {"maxPaginas": 5})[0] == 409)
        s, cu = http("POST", "/seo/sitios", {"nombre": "Cumbre Perú", "hosts": ["https://www.cumbre.edu.pe/carreras/", "cumbre.edu.pe", "CUMBRE.edu.pe"]})
        comprobar("agrega un competidor y se queda con el dominio del enlace", s == 201 and cu["codigo"] == "CUMBREPERU" and cu["rol"] == "COMPETIDOR"
                  and cu["hosts"] == ["www.cumbre.edu.pe", "cumbre.edu.pe"], str(cu))
        comprobar("un dominio no puede ser de dos sitios", http("POST", "/seo/sitios", {"nombre": "Otra", "hosts": ["dgallia.edu.pe"]})[0] == 409)
        comprobar("rechaza lo que no es un dominio", http("POST", "/seo/sitios", {"nombre": "Otra", "hosts": ["no es web"]})[0] == 409
                  and http("POST", "/seo/sitios", {"nombre": "Otra", "hosts": []})[0] == 409)
        s, cu = http("PUT", "/seo/sitios/CUMBREPERU", {"nombre": "Cumbre", "hosts": ["cumbre.edu.pe"]})
        comprobar("cambia nombre y dominios y conserva el máximo", s == 200 and cu["nombre"] == "Cumbre" and cu["hosts"] == ["cumbre.edu.pe"]
                  and cu["maxPaginas"] == 400, str(cu))
        comprobar("solo un admin quita un sitio", http("DELETE", "/seo/sitios/CUMBREPERU", None, eva)[0] == 403)
        comprobar("el sitio propio no se quita", http("DELETE", "/seo/sitios/ILCB")[0] == 409)
        comprobar("quita el competidor", http("DELETE", "/seo/sitios/CUMBREPERU")[0] == 204
                  and [x["codigo"] for x in http("GET", "/seo/sitios")[1]] == ["ILCB", "DGALLIA", "CENFOTUR", "USIL"])
        s, t = http("POST", "/seo/sitios/DGALLIA/inventario")
        comprobar("lanza el inventario en segundo plano", s == 202 and t["estado"] == "EN_COLA" and t["codigo"] == "S0001", str(t))
        t = esperar_seo(t["codigo"])
        comprobar("inventario terminado", t["estado"] == "TERMINADA" and t["resumen"]["nuevas"] == 16 and t["resumen"]["ok"] == 15, str(t))
        pags = http("GET", "/seo/paginas?sitio=DGALLIA")[1]
        comprobar("una fila por URL; el carrito queda excluido con su motivo",
                  len(pags) == 16 and any(p["estado"] == "EXCLUIDA" and "servicio" in p["motivo"] for p in pags), str([p["estado"] for p in pags]))
        comprobar("guarda title, H1 y H2", next(p for p in pags if p["url"].endswith("/a1/"))["datos"]["h2"] == ["Uno"])
        n = len(estado["seo_leidas"])
        t = esperar_seo(http("POST", "/seo/sitios/DGALLIA/inventario")[1]["codigo"])
        comprobar("repetir el inventario no vuelve a descargar nada", len(estado["seo_leidas"]) == n and t["resumen"]["leidas"] == 0, str(t["resumen"]))
        estado["seo_lastmod_a1"], estado["seo_retirar"] = "2026-10-15", True
        t = esperar_seo(http("POST", "/seo/sitios/DGALLIA/inventario")[1]["codigo"])
        comprobar("solo relee la página cuyo lastmod cambió", estado["seo_leidas"][n:] == ["https://dgallia.edu.pe/a1/"], str(estado["seo_leidas"][n:]))
        comprobar("la que ya no está en el sitemap queda RETIRADA", t["resumen"]["retiradas"] == 1
                  and next(p for p in http("GET", "/seo/paginas?sitio=DGALLIA")[1] if p["url"].endswith("/a15/"))["estado"] == "RETIRADA")

        print("plan seo: fecha mínima de publicación")
        comprobar("sin fecha mínima por defecto", http("GET", "/seo/fecha-minima")[1] == {"fecha": None, "antiguas": 0})
        comprobar("fecha mal escrita o futura: 409", http("PUT", "/seo/fecha-minima", {"fecha": "2026-02-30"})[0] == 409
                  and http("PUT", "/seo/fecha-minima", {"fecha": "2099-01-01"})[0] == 409)
        s, fm = http("PUT", "/seo/fecha-minima", {"fecha": "2026-06-01"})
        pags = http("GET", "/seo/paginas?sitio=DGALLIA")[1]
        antiguas = sorted(p["url"] for p in pags if p["estado"] == "ANTIGUA")
        comprobar("las páginas anteriores quedan ANTIGUA (la de octubre no; las retiradas y excluidas no se tocan)",
                  s == 200 and fm["marcadas"] == 13 and fm["antiguas"] == 13 and len(antiguas) == 13
                  and "https://dgallia.edu.pe/a1/" not in antiguas and "2026-01-01" in next(p for p in pags if p["estado"] == "ANTIGUA")["motivo"], str(fm))
        s, fm = http("PUT", "/seo/fecha-minima", {"fecha": None})
        comprobar("sin fecha mínima vuelven todas, con sus datos", s == 200 and fm["devueltas"] == 13 and fm["antiguas"] == 0
                  and sum(p["estado"] == "OK" for p in http("GET", "/seo/paginas?sitio=DGALLIA")[1]) == 14, str(fm))

        print("plan seo: temas")
        dg = next(x for x in http("GET", "/seo/sitios")[1] if x["codigo"] == "DGALLIA")
        comprobar("antes de lanzar dice cuántas van a la IA", dg["sinTemas"] == 14 and dg["sinTemasDelSector"] == 13, str(dg))
        estado["seo_cuota_en"] = 2
        t = esperar_seo(http("POST", "/seo/sitios/DGALLIA/temas")[1]["codigo"])
        comprobar("sin cuota de Gemini la tarea queda en pausa", t["estado"] == "PAUSADA" and "cuota" in (t["error"] or ""), str(t))
        s, i = http("POST", "/seo/sitios/ILCB/inventario")
        comprobar("con la tarea en pausa se puede lanzar otra", s == 202 and esperar_seo(i["codigo"])["estado"] == "TERMINADA", str(i))
        http("POST", "/seo/tareas/S0004/continuar")
        t = esperar_seo("S0004")
        comprobar("continuar solo pide los temas que faltaban", t["estado"] == "TERMINADA" and len(estado["seo_temas"][0]) == 12
                  and estado["seo_temas"][-1] == estado["seo_temas"][1] and len(estado["seo_temas"][-1]) == 1, str([len(x) for x in estado["seo_temas"]]))
        comprobar("la página fuera del sector no va a la IA", all("/a14/" not in u for lote in estado["seo_temas"] for u in lote)
, str(estado["seo_temas"]))
        a14 = next(p for p in http("GET", "/seo/paginas?sitio=DGALLIA")[1] if p["url"].endswith("/a14/"))
        comprobar("queda marcada «fuera del sector» con relevancia 0", a14["temas"]["fuera_del_sector"] is True and a14["temas"]["relevancia"] == 0, str(a14["temas"]))
        comprobar("la tarea suma su costo de IA", t["llamadasIa"] == 2 and t["costoUsd"] > 0, str(t))
        dg = next(x for x in http("GET", "/seo/sitios")[1] if x["codigo"] == "DGALLIA")
        comprobar("el sitio cuenta sus páginas con temas", dg["conTemas"] == 14 and dg["sinTemas"] == 0, str(dg))
        comprobar("sin cambios no hay temas que pedir", http("POST", "/seo/sitios/DGALLIA/temas")[0] == 409)

        print("plan seo: keywords")
        t = esperar_seo(http("POST", "/seo/keywords/generar")[1]["codigo"])
        kws = http("GET", "/seo/keywords")[1]
        k = {x["keyword"].lower().strip("?"): x for x in kws}
        comprobar("keywords terminadas", t["estado"] == "TERMINADA" and t["resumen"]["informacionales"] == 2, str(t))
        comprobar("une variantes con la misma forma normalizada", len(kws) == 3 and len(k["qué es la mise en place"]["origenes"]) == 7, str(kws))
        comprobar("descarta páginas poco relevantes (relevancia < 40)", len(k["cuánto dura la carrera de cocina"]["origenes"]) == 6)
        comprobar("cada keyword dice de qué página salió", k["qué es la mise en place"]["origenes"][0]["sitio"] == "D'Gallia"
                  and k["qué es la mise en place"]["evidencia"] == "TOPIC_OBSERVED")
        comprobar("la cobertura solo se pide para grupos informacionales",
                  sorted(estado["seo_grupos_cobertura"]) == ["cuánto dura la carrera de cocina", "qué es la mise en place"], str(estado.get("seo_grupos_cobertura")))
        comprobar("guarda la página propia que ya la cubre en parte", any(x["cobertura"] == "PARCIAL" and x["urlPropia"].startswith("https://ilcb.edu.pe/") for x in kws))
        comprobar("la transaccional queda sin evaluar cobertura", k["precio carrera de cocina"]["intencion"] == "TRANSACTIONAL" and k["precio carrera de cocina"]["cobertura"] is None)
        comprobar("un miembro también ve el plan", http("GET", "/seo/keywords", None, eva)[0] == 200)
        s, ig = http("GET", "/seo/informes?modulo=PLAN_SEO_KEYWORDS")
        comprobar("la lista de keywords queda guardada como informe, con su tarea y su resumen", s == 200 and len(ig) == 1
                  and ig[0]["filas"] == 3 and ig[0]["origen"] == t["codigo"] and ig[0]["resumen"]["informacionales"] == 2, str(ig))
        s, d = http("GET", f"/seo/informes/{ig[0]['codigo']}")
        comprobar("se vuelve a abrir con sus filas", s == 200 and {f["keyword"] for f in d["filas"]} == {x["keyword"] for x in kws}, str(d)[:200])
        s, csv, tipo = bajar(f"/seo/informes/{ig[0]['codigo']}/csv")
        texto_csv = csv.decode("utf-8")
        comprobar("y se baja en CSV (con BOM, cabecera y una fila por keyword)", s == 200 and "text/csv" in tipo and texto_csv.startswith("\ufeffkeyword,grupo")
                  and len(texto_csv.strip().splitlines()) == 4, texto_csv[:200])
        comprobar("un informe de keywords no se «vuelve a cargar»", http("POST", f"/seo/informes/{ig[0]['codigo']}/restaurar")[0] == 409)
        comprobar("módulo desconocido: 409", http("GET", "/seo/informes?modulo=OTRO")[0] == 409)
        comprobar("informe que no existe: 404", http("GET", "/seo/informes/IG9999")[0] == 404)
        comprobar("lista de tareas", [x["codigo"] for x in http("GET", "/seo/tareas")[1]][:2] == ["S0006", "S0005"])

        print("plan seo: rubro")
        s, defecto = http("GET", "/seo/rubro")
        comprobar("rubro por defecto: el de ILCB", s == 200 and defecto["porDefecto"] and "cocina" in defecto["descripcion"] and "cocin" in defecto["palabras"]
                  and defecto["negocio"] == "Instituto Le Cordon Bleu Perú", str(defecto))
        comprobar("sugiere el rubro leyendo la web propia (sin guardarlo)",
                  http("POST", "/seo/rubro/sugerir")[1] == {"descripcion": "Escuela de cocina sugerida", "palabras": ["cocin", "chef"]}
                  and http("GET", "/seo/rubro")[1]["porDefecto"])
        comprobar("una palabra con espacios se rechaza", http("PUT", "/seo/rubro", {"descripcion": "Academia de baile", "palabras": ["salsa", "bachata", "masa madre"]})[0] == 409)
        s, r = http("PUT", "/seo/rubro", {"descripcion": defecto["descripcion"], "palabras": defecto["palabras"] + ["Cronograma"]})
        comprobar("cambiar solo las palabras reevalúa las «fuera del sector»", s == 200 and r["reevaluar"] == 1 and not r["porDefecto"]
                  and r["palabras"][-1] == "cronograma", str(r))
        dg = next(x for x in http("GET", "/seo/sitios")[1] if x["codigo"] == "DGALLIA")
        comprobar("y con la palabra nueva esa página ya pasa el filtro", dg["sinTemas"] == 1 and dg["sinTemasDelSector"] == 1, str(dg))
        con_temas = http("GET", "/seo/rubro")[1]["conTemas"]
        s, r = http("PUT", "/seo/rubro", {"descripcion": "Academia de baile: salsa y bachata", "palabras": ["salsa", "bachata", "Baile"]})
        comprobar("cambiar la descripción reevalúa todas", s == 200 and r["reevaluar"] == con_temas and r["palabras"] == ["salsa", "bachata", "baile"], str(r))
        dg = next(x for x in http("GET", "/seo/sitios")[1] if x["codigo"] == "DGALLIA")
        comprobar("con otro rubro, las páginas de cocina quedan fuera del filtro", dg["sinTemas"] == 14 and dg["sinTemasDelSector"] == 0, str(dg))
        llamadas = estado["seo_temas_llamadas"]
        t = esperar_seo(http("POST", "/seo/sitios/DGALLIA/temas")[1]["codigo"])
        comprobar("y se marcan sin llamar a la IA", t["estado"] == "TERMINADA" and estado["seo_temas_llamadas"] == llamadas and "14 fuera del sector" in t["mensaje"], str(t))
        http("PUT", "/seo/rubro", {"descripcion": defecto["descripcion"], "palabras": defecto["palabras"]})
        t = esperar_seo(http("POST", "/seo/sitios/DGALLIA/temas")[1]["codigo"])
        comprobar("la IA recibe el negocio y el rubro configurados", estado["seo_temas_kw"].get("negocio") == "Instituto Le Cordon Bleu Perú"
                  and estado["seo_temas_kw"].get("rubro") == defecto["descripcion"], str(estado["seo_temas_kw"]))

        print("plan seo: artículos")
        kws = http("GET", "/seo/keywords")[1]
        grupo = next(k["grupo"] for k in kws if k["cobertura"] == "SIN_COBERTURA")
        s, a = http("POST", "/seo/articulos", {"grupo": grupo, "indicaciones": "  para principiantes "})
        comprobar("encarga la redacción en segundo plano", s == 202 and a["codigo"] == "AR0001" and a["tarea"], str(a))
        t = esperar_seo(a["tarea"])
        a = http("GET", "/seo/articulos/AR0001")[1]
        comprobar("redactado: título, contenido y pendientes", t["estado"] == "TERMINADA" and t["resumen"]["articulo"] == "AR0001"
                  and a["titulo"] == f"Guía: {a['keyword']}" and a["contenido"].startswith("## Qué es") and a["pendientes"] == ["[COMPLETAR: duración del curso]"]
                  and a["redactado"] and a["indicaciones"] == "para principiantes", str(a))
        e = estado["seo_articulo"]
        comprobar("la IA recibe rubro, indicaciones, competidores y páginas propias para enlazar",
                  e["indicaciones"] == "para principiantes" and e["rubro"] == defecto["descripcion"] and e["competidores"]
                  and all(u.startswith("https://dgallia.edu.pe/") for u in e["competidores"]) and e["propias"]
                  and all(u.startswith("https://ilcb.edu.pe/") for u in e["propias"]), str(e))
        comprobar("un artículo por grupo", http("POST", "/seo/articulos", {"grupo": grupo})[0] == 409)
        comprobar("aparece en la lista", [x["codigo"] for x in http("GET", "/seo/articulos")[1]] == ["AR0001"])
        comprobar("con [COMPLETAR] no se envía a WordPress", http("POST", "/seo/articulos/AR0001/wordpress", {})[0] == 409 and not estado["wp"])
        s, v = http("POST", "/seo/vista-previa", {"contenido": "## Hola\n[COMPLETAR: x]"})
        comprobar("vista previa en HTML con el pendiente resaltado", s == 200 and v["html"].startswith("<h2>Hola</h2>") and v["pendientes"] == ["[COMPLETAR: x]"], str(v))
        s, a = http("PUT", "/seo/articulos/AR0001", {"titulo": "Guía editada", "slug": "Guía Editada!", "metaDescription": "Resumen", "contenido": "## Qué es\nDura tres años."})
        comprobar("edita y limpia el slug", s == 200 and a["slug"] == "guia-editada" and a["titulo"] == "Guía editada", str(a))

        print("plan seo: imagen destacada")
        comprobar("sin imagen al principio", a["imagen"] is None and bajar("/seo/articulos/AR0001/imagen")[0] == 404)
        comprobar("fuentes de imagen", http("GET", "/seo/imagenes")[1]["fotos"] == "PIXABAY")
        s, b = http("POST", "/seo/imagenes/buscar", {"consulta": " pan de masa madre "})
        comprobar("busca fotos en el banco", s == 200 and b["fotos"][0]["id"] == 9 and estado["foto_consulta"] == "pan de masa madre", str(b))
        comprobar("búsqueda vacía: rechazada", http("POST", "/seo/imagenes/buscar", {"consulta": " "})[0] == 409)
        s, a = http("POST", "/seo/articulos/AR0001/imagen/foto", {"id": 9}, eva)
        i = a.get("imagen") or {}
        comprobar("elige la foto: crédito y alt por defecto (el título)", s == 200 and i.get("fuente") == "PIXABAY" and i.get("leyenda") == "Foto: Ana en Pixabay"
                  and i.get("alt") == "Guía editada" and i.get("bytes") == len(JPG_PRUEBA) and i.get("origenUrl") == "https://www.pexels.com/photo/9/", str(a))
        s, archivo, tipo = bajar("/seo/articulos/AR0001/imagen")
        comprobar("sirve la imagen guardada", s == 200 and archivo == JPG_PRUEBA and tipo.startswith("image/jpeg"), f"{s} {tipo}")
        comprobar("sin sesión no se ve la imagen", bajar("/seo/articulos/AR0001/imagen", {"c": ""})[0] == 401)
        comprobar("el alt no puede quedar vacío", http("PUT", "/seo/articulos/AR0001/imagen", {"alt": " ", "leyenda": ""})[0] == 409)
        s, a = http("PUT", "/seo/articulos/AR0001/imagen", {"alt": "Pan de masa madre recién horneado", "leyenda": "Foto: Ana en Pixabay"})
        comprobar("edita el alt", s == 200 and a["imagen"]["alt"] == "Pan de masa madre recién horneado", str(a))

        comprobar("WordPress configurado y probado", http("GET", "/seo/wordpress")[1]["completo"] and http("POST", "/seo/wordpress/probar")[1]["usuario"] == "Editora")
        comprobar("un miembro no puede publicar en la web", http("POST", "/seo/articulos/AR0001/wordpress", {"publicar": True}, eva)[0] == 403)
        s, a = http("POST", "/seo/articulos/AR0001/wordpress", {}, eva)
        _, ruta, cuerpo = estado["wp"][-1]
        comprobar("un miembro envía el borrador: entrada nueva en draft y en HTML", s == 200 and ruta == "/wp-json/wp/v2/posts" and cuerpo["status"] == "draft"
                  and cuerpo["content"] == "<!-- wp:post-featured-image /-->\n\n<h2>Qué es</h2>\n<p>Dura tres años.</p>" and cuerpo["slug"] == "guia-editada" and cuerpo["excerpt"] == "Resumen"
                  and a["wpId"] == 77 and a["wpEstado"] == "draft" and not a["cambiosSinEnviar"], f"{s} {cuerpo} {a}")
        subidas = [x for x in estado["wp"] if x[1].endswith("/media")]
        textos = [x[2] for x in estado["wp"] if x[1].endswith("/media/501")]
        comprobar("la imagen va como destacada, con su alt", len(subidas) == 1 and subidas[0][2] == {"bytes": len(JPG_PRUEBA), "tipo": "image/jpeg"}
                  and textos[-1]["alt_text"] == "Pan de masa madre recién horneado" and cuerpo["featured_media"] == 501
                  and a["imagen"]["wpMediaId"] == 501, f"{subidas} {textos} {cuerpo}")
        time.sleep(0.01)
        a = http("PUT", "/seo/articulos/AR0001", {"titulo": "Guía editada", "slug": "guia-editada", "metaDescription": "Resumen", "contenido": "## Qué es\nDura dos años."})[1]
        comprobar("editar después de enviar: cambios sin enviar", a["cambiosSinEnviar"], str(a))
        s, a = http("POST", "/seo/articulos/AR0001/wordpress", {})
        _, ruta, cuerpo = estado["wp"][-1]
        comprobar("reenviar actualiza la misma entrada sin tocar su estado", s == 200 and ruta == "/wp-json/wp/v2/posts/77" and "status" not in cuerpo
                  and not a["cambiosSinEnviar"], str(cuerpo))
        comprobar("reenviar no vuelve a subir la imagen", len([x for x in estado["wp"] if x[1].endswith("/media")]) == 1 and cuerpo["featured_media"] == 501)
        time.sleep(0.01)
        comprobar("descripción demasiado corta: no genera", http("POST", "/seo/articulos/AR0001/imagen/generar", {"descripcion": "pan"})[0] == 409
                  and "imagen_pedida" not in estado)
        s, a = http("POST", "/seo/articulos/AR0001/imagen/generar", {"descripcion": "manos amasando pan de masa madre"})
        i = a.get("imagen") or {}
        comprobar("genera con IA y sustituye la foto", s == 200 and i.get("fuente") == "GEMINI" and i.get("leyenda") == "Imagen generada con IA"
                  and i.get("prompt") == "manos amasando pan de masa madre" and i.get("wpMediaId") is None and a["cambiosSinEnviar"], str(a))
        comprobar("la IA recibe el negocio y el rubro", estado["imagen_pedida"]["rubro"] == defecto["descripcion"]
                  and estado["imagen_pedida"]["negocio"] == "Instituto Le Cordon Bleu Perú", str(estado["imagen_pedida"]))
        comprobar("sirve la imagen nueva", bajar("/seo/articulos/AR0001/imagen")[1] == PNG_PRUEBA)
        http("POST", "/seo/articulos/AR0001/wordpress", {})
        comprobar("la imagen nueva se sube en el siguiente envío", len([x for x in estado["wp"] if x[1].endswith("/media")]) == 2)
        s, a = http("DELETE", "/seo/articulos/AR0001/imagen")
        comprobar("quita la imagen", s == 200 and a["imagen"] is None and bajar("/seo/articulos/AR0001/imagen")[0] == 404, str(a))
        s, a = http("POST", "/seo/articulos/AR0001/wordpress", {"publicar": True})
        comprobar("un admin publica", s == 200 and estado["wp"][-1][2]["status"] == "publish" and a["wpEstado"] == "publish", str(a))
        comprobar("desvincular olvida la entrada", http("POST", "/seo/articulos/AR0001/desvincular")[1]["wpId"] is None)
        comprobar("solo un admin borra artículos", http("DELETE", "/seo/articulos/AR0001", None, eva)[0] == 403)
        comprobar("borra el artículo", http("DELETE", "/seo/articulos/AR0001")[0] == 204 and http("GET", "/seo/articulos/AR0001")[0] == 404)

        print("plan seo: flujo automático")
        s, auto = http("GET", "/seo/automatico")
        comprobar("desactivado por defecto", s == 200 and auto["activo"] is False and auto["proxima"] is None and auto["articulos"] == 2, str(auto))
        cand = auto.get("candidatos") or []
        comprobar("enseña qué redactaría: la informativa sin cobertura, con sus páginas de competidores",
                  len(cand) == 1 and cand[0]["paginas"] > 0 and cand[0]["sitios"] and cand[0]["relevancia"] == 80, str(cand))
        pedida = estado.get("demanda_pedida") or {}
        forma_google = " ".join(reversed(pedida["grupos"][0]["keywords"][0].split())) if pedida.get("grupos") else None
        comprobar("pregunta a Google (Perú) y usa la forma en que la gente la escribe", pedida.get("pais") == "PE" and auto["google"] is True
                  and cand[0]["google"] == "EXACTA" and cand[0]["keyword"] == forma_google and cand[0]["sugerencias"] == ["otra búsqueda"]
                  and auto["descartados"] == [], str(cand))
        comprobar("un miembro no lo programa ni lo lanza", http("PUT", "/seo/automatico", {"activo": True}, eva)[0] == 403
                  and http("POST", "/seo/automatico/ejecutar", None, eva)[0] == 403)
        comprobar("hora no válida: rechazada", http("PUT", "/seo/automatico", {"activo": True, "hora": "25:00"})[0] == 409)
        s, auto = http("PUT", "/seo/automatico", {"activo": True, "dia": 1, "hora": "09:00", "articulos": 2})
        prox =datetime.fromisoformat(auto["proxima"].replace("Z", "+00:00")) if auto.get("proxima") else None
        comprobar("programado: próxima el lunes a las 09:00 de Lima (14:00 UTC)", s == 200 and auto["activo"] and prox is not None
                  and prox.weekday() == 0 and (prox.hour, prox.minute) == (14, 0) and prox > datetime.now(timezone.utc), str(auto))
        antes_tareas = {t["codigo"] for t in http("GET", "/seo/tareas")[1]}
        antes_wp = len(estado["wp"])
        estado["articulos_limpios"] = 1
        s, t = http("POST", "/seo/automatico/ejecutar")
        comprobar("lanza el flujo como tarea", s == 202 and t["tipo"] == "AUTOMATICO", str(t))
        t = esperar_seo(t["codigo"], segundos=120)
        r = t.get("resumen") or {}
        comprobar("termina", t.get("estado") == "TERMINADA", f"{t.get('estado')} {t.get('error')} {t.get('mensaje')}")
        nuevas = [x for x in http("GET", "/seo/tareas")[1] if x["codigo"] not in antes_tareas and x["codigo"] != t["codigo"]]
        sitios_activos = {x["codigo"] for x in http("GET", "/seo/sitios")[1] if x["activo"]}
        comprobar("encadena inventario de cada sitio, keywords y redacción", {x["sitio"] for x in nuevas if x["tipo"] == "INVENTARIO"} == sitios_activos
                  and any(x["tipo"] == "KEYWORDS" for x in nuevas) and any(x["tipo"] == "ARTICULO" for x in nuevas)
                  and all(x["estado"] == "TERMINADA" for x in nuevas), str([(x["tipo"], x["sitio"], x["estado"]) for x in nuevas]))
        arts = r.get("articulos") or []
        a = http("GET", f"/seo/articulos/{arts[0]}")[1] if arts else {}
        comprobar("redacta el grupo sin cobertura y le pone foto", len(arts) == 1 and a.get("contenido") and (a.get("imagen") or {}).get("fuente") == "PIXABAY", str(r))
        comprobar("redacta con la forma de Google como keyword principal", a.get("keyword") == forma_google
                  and estado["seo_articulo"]["keyword"] == forma_google, str(a.get("keyword")))
        comprobar("lo envía a WordPress como borrador", r.get("enviados") == arts and a.get("wpId") == 77 and a.get("wpEstado") == "draft"
                  and len(estado["wp"]) > antes_wp and estado["wp"][-1][2].get("status") == "draft", str(a.get("wpEstado")))
        auto = http("GET", "/seo/automatico")[1]
        comprobar("anota la ejecución y la próxima es otra semana", auto["tarea"]["codigo"] == t["codigo"] and auto["ultima"]
                  and auto["proxima"] > auto["ultima"], str(auto))

        t2 = esperar_seo(http("POST", "/seo/automatico/ejecutar")[1]["codigo"], segundos=120)
        comprobar("otra vez: no repite un artículo ya redactado", t2.get("estado") == "TERMINADA" and not (t2.get("resumen") or {}).get("articulos")
                  and "ningún artículo nuevo" in (t2.get("mensaje") or ""), str(t2.get("mensaje")))
        http("DELETE", f"/seo/articulos/{arts[0]}")
        t3 = esperar_seo(http("POST", "/seo/automatico/ejecutar")[1]["codigo"], segundos=120)
        r3 = t3.get("resumen") or {}
        comprobar("con «[COMPLETAR]» no lo envía: espera tus datos", t3.get("estado") == "TERMINADA" and r3.get("esperanDatos") == r3.get("articulos")
                  and len(r3.get("articulos") or []) == 1 and not r3.get("enviados") and "espera tus datos" in (t3.get("mensaje") or ""), str(r3))

        # Una página cambia y Gemini se queda sin cuota al extraer sus temas: pausa y «Continuar» retoma.
        estado["seo_lastmod_a1"] = "2026-10-27"
        estado["seo_cuota_en"] = estado["seo_temas_llamadas"] + 1
        t4 = esperar_seo(http("POST", "/seo/automatico/ejecutar")[1]["codigo"], segundos=120)
        sub_temas = next((v for k, v in ((t4.get("resumen") or {}).get("pasos") or {}).items() if k.startswith("temas:")), None)
        comprobar("sin cuota de Gemini: el flujo queda en pausa y dice dónde", t4.get("estado") == "PAUSADA" and "Temas de" in (t4.get("error") or "")
                  and sub_temas and http("GET", f"/seo/tareas/{sub_temas}")[1]["estado"] == "PAUSADA", f"{t4.get('estado')} {t4.get('error')}")
        n_inv = len([x for x in http("GET", "/seo/tareas")[1] if x["tipo"] == "INVENTARIO"])
        http("POST", f"/seo/tareas/{t4['codigo']}/continuar")
        t4 = esperar_seo(t4["codigo"], segundos=120)
        comprobar("«Continuar» retoma la misma sub-tarea sin repetir el inventario", t4.get("estado") == "TERMINADA"
                  and http("GET", f"/seo/tareas/{sub_temas}")[1]["estado"] == "TERMINADA"
                  and len([x for x in http("GET", "/seo/tareas")[1] if x["tipo"] == "INVENTARIO"]) == n_inv, f"{t4.get('estado')} {t4.get('error')}")

        # Google no sugiere la búsqueda que falta: se descarta y no se redacta.
        for x in (r3.get("articulos") or []):
            http("DELETE", f"/seo/articulos/{x}")
        estado["google"] = "ninguna"
        auto = http("GET", "/seo/automatico")[1]
        comprobar("lo que Google no sugiere sale de los candidatos y se enseña como descartado", auto["candidatos"] == []
                  and len(auto["descartados"]) == 1 and auto["descartados"][0]["google"] == "NINGUNA", str(auto.get("descartados")))
        t5 = esperar_seo(http("POST", "/seo/automatico/ejecutar")[1]["codigo"], segundos=120)
        r5 = t5.get("resumen") or {}
        comprobar("no redacta lo descartado y lo explica", t5.get("estado") == "TERMINADA" and not r5.get("articulos")
                  and len(r5.get("descartados") or []) == 1 and any("Google" in x for x in r5.get("avisos") or []), str(r5))
        estado["google"] = "caido"
        auto = http("GET", "/seo/automatico")[1]
        comprobar("Google caído: elige solo por competidores y lo avisa", auto["google"] is False and len(auto["candidatos"]) == 1
                  and auto["candidatos"][0]["google"] is None and auto["descartados"] == [], str(auto.get("candidatos")))
        estado["google"] = "ok"

        print("plan seo: search console")
        s, g = http("GET", "/seo/search-console")
        comprobar("sin conectar: dice qué falta", s == 200 and g["configuracion"]["completo"] is False
                  and "GSC_PROPIEDAD" in g["configuracion"]["faltan"] and g["sincronizacion"] is None, str(g))
        comprobar("sin conectar no sincroniza", http("POST", "/seo/search-console/sincronizar")[0] >= 400)
        comprobar("el flujo automático lo salta si no está conectado", ((r5.get("pasos") or {}).get("gsc")) == "sin conectar", str(r5.get("pasos")))
        kw = auto["candidatos"][0]["keyword"]
        import unicodedata
        al_reves = "".join(c for c in unicodedata.normalize("NFD", " ".join(reversed(kw.split()))) if not unicodedata.combining(c))
        estado["gsc"] = [
            {"consulta": al_reves, "url": "https://ilcb.edu.pe/p1/", "clics": 4, "impresiones": 40, "ctr": 0.1, "posicion": 6.0},
            {"consulta": kw, "url": "https://ilcb.edu.pe/p2/", "clics": 1, "impresiones": 10, "ctr": 0.1, "posicion": 11.0},
            {"consulta": "escuela de cocina lima", "url": "https://ilcb.edu.pe/", "clics": 0, "impresiones": 300, "ctr": 0.0, "posicion": 14.2},
        ]
        s, g = http("POST", "/seo/search-console/sincronizar")
        comprobar("sincroniza y resume (búsquedas distintas, clics, impresiones)", s == 200 and g["sincronizacion"]["filas"] == 3
                  and g["sincronizacion"]["desde"] == "2026-07-29" and g["resumen"] == {"consultas": 2, "clics": 5, "impresiones": 350}, str(g))
        cortes = http("GET", "/seo/informes?modulo=SEARCH_CONSOLE")[1]
        comprobar("cada sincronización queda guardada como un corte, y es el que está en uso", len(cortes) == 1
                  and cortes[0]["filas"] == 3 and cortes[0]["resumen"]["impresiones"] == 350 and "2026-07-29" in cortes[0]["titulo"]
                  and g["sincronizacion"]["informe"] == cortes[0]["codigo"], str(cortes))
        primer_corte = cortes[0]["codigo"]
        ops = g["oportunidades"]
        comprobar("páginas para mejorar: por página, posición 4-20, ≥ 30 impresiones, de más a menos", [o["url"] for o in ops]
                  == ["https://ilcb.edu.pe/", "https://ilcb.edu.pe/p1/"] and ops[0]["impresiones"] == 300 and ops[0]["mejora"] is None
                  and ops[0]["consultas"][0]["consulta"] == "escuela de cocina lima", str(ops))
        comprobar("marca por defecto: el nombre del sitio sin palabras genéricas, su dominio y la intranet",
                  g["marca"][:2] == ["cordon bleu", "ilcb"] and "intranet" in g["marca"], str(g["marca"]))
        comprobar("solo un admin cambia la marca", http("PUT", "/seo/search-console/marca", {"palabras": ["x"]}, eva)[0] == 403
                  and http("PUT", "/seo/search-console/marca", {"palabras": [" "]})[0] == 409)
        s, g = http("PUT", "/seo/search-console/marca", {"palabras": ["Cordon Bleu", "ilcb", "Escuela"]})
        comprobar("con «escuela» como marca, esa búsqueda deja de contar", s == 200 and g["marca"] == ["cordon bleu", "ilcb", "escuela"]
                  and [o["url"] for o in g["oportunidades"]] == ["https://ilcb.edu.pe/p1/"], str(g.get("oportunidades")))
        http("PUT", "/seo/search-console/marca", {"palabras": ["cordon bleu", "ilcb"]})
        g = http("GET", "/seo/search-console")[1]
        comprobar("términos protegidos por defecto: las carreras y programas de la web", len(g["terminos"]) == 7
                  and g["terminos"][0] == {"nombre": "Gastronomía", "tipo": "CARRERA", "descripcion": ""}, str(g.get("terminos")))
        comprobar("un miembro no cambia los términos", http("PUT", "/seo/search-console/terminos", {"terminos": []}, eva)[0] == 403)
        comprobar("un término repetido se rechaza", http("PUT", "/seo/search-console/terminos",
                  {"terminos": [{"nombre": "Cocina", "tipo": "CARRERA"}, {"nombre": "cocina ", "tipo": "OTRO"}]})[0] == 409)
        s, g = http("PUT", "/seo/search-console/terminos", {"terminos": g["terminos"] + [
            {"nombre": " Matrix ", "tipo": "SISTEMA", "descripcion": "La intranet de alumnos."}, {"nombre": "   ", "tipo": "OTRO"}, {"nombre": "PEC", "tipo": "RARO"}]})
        comprobar("el admin agrega un sistema con su descripción (sin vacíos; tipo desconocido = OTRO)", s == 200 and len(g["terminos"]) == 9
                  and g["terminos"][7] == {"nombre": "Matrix", "tipo": "SISTEMA", "descripcion": "La intranet de alumnos."}
                  and g["terminos"][8]["tipo"] == "OTRO", str(g.get("terminos")))
        comprobar("proponer mejora de una página que no está en la lista: 404", http("POST", "/seo/mejoras", {"url": "https://ilcb.edu.pe/otra/"})[0] == 404)
        s, m = http("POST", "/seo/mejoras", {"url": "https://ilcb.edu.pe/p1/"}, eva)
        pedida = (estado.get("mejoras_pedidas") or [{}])[-1]
        comprobar("propone título, descripción e ideas con el título actual del inventario y las búsquedas reales", s == 200
                  and m["estado"] == "PROPUESTA" and m["titulo"] == "Mejor título para /p1/"
                  and m["ideas"] == [{"donde": "H2", "diceAhora": "Origen", "debeDecir": "Origen del curso"}]
                  and [t["nombre"] for t in pedida.get("terminos", [])][:2] == ["Gastronomía", "Administración de Servicios de Hostelería y Restaurantes"]
                  and m["tituloActual"] == "Curso de cocina https://ilcb.edu.pe/p1/" and pedida.get("actual", {}).get("title") == m["tituloActual"]
                  and pedida["consultas"][0]["impresiones"] == 40 and pedida.get("rubro"), str(m))
        comprobar("estado no válido: 409", http("PUT", "/seo/mejoras/estado", {"url": "https://ilcb.edu.pe/p1/", "estado": "PUBLICADA"})[0] == 409)
        filas_antes = list(estado["gsc"])
        estado["gsc"] = filas_antes[:1]
        s, g2 = http("POST", "/seo/search-console/sincronizar")
        cortes = http("GET", "/seo/informes?modulo=SEARCH_CONSOLE")[1]
        comprobar("un corte nuevo no borra el anterior", s == 200 and g2["resumen"]["impresiones"] == 40 and len(cortes) == 2
                  and cortes[1]["codigo"] == primer_corte and g2["sincronizacion"]["informe"] == cortes[0]["codigo"], str(cortes))
        s, g2 = http("POST", f"/seo/informes/{primer_corte}/restaurar", None, eva)
        comprobar("volver a cargar el primer corte: vuelven sus datos, su periodo y sus oportunidades",
                  s == 200 and g2["resumen"] == {"consultas": 2, "clics": 5, "impresiones": 350} and g2["sincronizacion"]["informe"] == primer_corte
                  and g2["sincronizacion"]["desde"] == "2026-07-29" and len(g2["oportunidades"]) == 2
                  and len(http("GET", "/seo/informes?modulo=SEARCH_CONSOLE")[1]) == 2, str(g2)[:300])
        estado["gsc"] = filas_antes
        s, m = http("PUT", "/seo/mejoras/estado", {"url": "https://ilcb.edu.pe/p1/", "estado": "APLICADA"})
        g = http("GET", "/seo/search-console")[1]
        comprobar("marcada como aplicada, y se ve en la lista", s == 200 and m["estado"] == "APLICADA"
                  and next(o for o in g["oportunidades"] if o["url"].endswith("/p1/"))["mejora"]["estado"] == "APLICADA", str(m))
        comprobar("comprobar acceso", http("POST", "/seo/search-console/comprobar")[1]["ok"] is True)
        auto = http("GET", "/seo/automatico")[1]
        d = (auto["descartados"] or [{}])[0]
        comprobar("ya posiciona (sin importar orden ni tildes): descartada, con su posición media y página", auto["candidatos"] == []
                  and d.get("motivo") == "YA_POSICIONA" and d["gsc"] == {"impresiones": 50, "clics": 5, "posicion": 7.0, "url": "https://ilcb.edu.pe/p1/"},
                  str(auto["descartados"]))
        for f in estado["gsc"][:2]:
            f["posicion"] = 16.0
        http("POST", "/seo/search-console/sincronizar")
        auto = http("GET", "/seo/automatico")[1]
        comprobar("en la segunda página: mejor mejorar la página", auto["candidatos"] == []
                  and (auto["descartados"] or [{}])[0].get("motivo") == "MEJORAR_PAGINA", str(auto["descartados"]))
        for f in estado["gsc"][:2]:
            f["posicion"] = 40.0
        http("POST", "/seo/search-console/sincronizar")
        auto = http("GET", "/seo/automatico")[1]
        comprobar("lejos (posición 40): sigue siendo candidata, con su dato de Search Console", len(auto["candidatos"]) == 1
                  and auto["candidatos"][0]["gsc"]["impresiones"] == 50 and auto["descartados"] == [], str(auto["candidatos"]))
        t6 = esperar_seo(http("POST", "/seo/automatico/ejecutar")[1]["codigo"], segundos=120)
        r6 = t6.get("resumen") or {}
        comprobar("conectado: el flujo sincroniza Search Console antes de elegir", t6.get("estado") == "TERMINADA"
                  and (r6.get("pasos") or {}).get("gsc") == "ok" and len(r6.get("articulos") or []) == 1, str(r6.get("pasos")))
        comprobar("y propone mejoras para las páginas que aún no tienen (la que no está en el inventario la lee)", r6.get("mejoras") == ["https://ilcb.edu.pe/"]
                  and "propuesta de mejora" in (t6.get("mensaje") or "") and estado["mejoras_pedidas"][-1]["actual"].get("title"), str(r6.get("mejoras")))
        http("PUT", "/seo/automatico", {"activo": False})

        print("mercado guardado")
        http("PUT", "/mercado", peticion(competidores=comp[:2]))
        comprobar("recuerda el mercado", len(http("GET", "/mercado")[1]["competidores"]) == 2)
    finally:
        backend.terminate()
        try:
            backend.wait(timeout=15)
        except subprocess.TimeoutExpired:
            backend.kill()
        servidor.should_exit = True
        shutil.rmtree(datos, ignore_errors=True)

    print("\n" + ("TODO OK" if not fallos else f"{fallos} FALLOS"))
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
