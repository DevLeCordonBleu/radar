# -*- coding: utf-8 -*-
"""Genera el informe del Radar para gerencia (HTML -> PDF con Chrome) y el modelo entidad-relación aparte."""
import html
import os
import sqlite3
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
BD = 'C:/Desarrollo/Radar/01_backend/datos/radar.db'
CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
SALIDA_INFORME = 'C:/Desarrollo/Radar/06_informes/Informe_Radar_Gerencia_2026-11-06.pdf'
SALIDA_ER = 'C:/Desarrollo/Radar/04_bd/Modelo_Entidad_Relacion_Radar.pdf'
FECHA = '6 de noviembre de 2026'
e = html.escape

# ───────────────────────── estilos ─────────────────────────
CSS = r"""
@page { size: A4; margin: 16mm 15mm 16mm 15mm;
  @bottom-left { content: "Radar · Informe de estado y propuesta · 6 nov 2026"; font: 7.5pt 'Segoe UI', Arial; color: #7a8794; }
  @bottom-right { content: counter(page) " / " counter(pages); font: 7.5pt 'Segoe UI', Arial; color: #7a8794; } }
@page portada { margin: 0; @bottom-left { content: none } @bottom-right { content: none } }
@page horizontal { size: A4 landscape; margin: 12mm 12mm 14mm 12mm; }
:root { --tinta: #14212b; --suave: #4a5866; --tenue: #7a8794; --linea: #d9e0e6; --fondo: #f4f7f9;
  --azul: #12324a; --cian: #0e7c86; --cian-f: #e3f3f4; --verde: #1d7a46; --verde-f: #e4f4ea; --ambar: #9a6200;
  --ambar-f: #fdf1d8; --rojo: #a8322b; --rojo-f: #fbe5e3; --morado: #6b3fa0; --morado-f: #efe7f8; --gris-f: #eef1f4; }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { margin: 0; font-family: 'Segoe UI', Arial, sans-serif; font-size: 9.6pt; line-height: 1.45; color: var(--tinta); background: #fff; }
h1 { font-size: 20pt; margin: 0 0 6pt; color: var(--azul); line-height: 1.15; }
h2 { font-size: 14.5pt; margin: 0 0 8pt; color: var(--azul); padding-bottom: 4pt; border-bottom: 2px solid var(--cian); }
h3 { font-size: 11pt; margin: 12pt 0 5pt; color: var(--azul); }
h4 { font-size: 9.6pt; margin: 8pt 0 3pt; color: var(--cian); text-transform: uppercase; letter-spacing: .04em; }
p { margin: 0 0 6pt; }
ul { margin: 0 0 6pt; padding-left: 15pt; } li { margin: 0 0 2pt; }
a { color: var(--cian); text-decoration: none; }
.salto { break-before: page; }
.nosplit { break-inside: avoid; }
.horizontal { page: horizontal; }
.chico { font-size: 8.4pt; } .tenue { color: var(--tenue); } .suave { color: var(--suave); }
table { width: 100%; border-collapse: collapse; margin: 4pt 0 8pt; font-size: 8.5pt; }
th { text-align: left; background: var(--azul); color: #fff; font-weight: 600; padding: 4pt 5pt; }
td { padding: 3.5pt 5pt; border-bottom: 1px solid var(--linea); vertical-align: top; }
tr { break-inside: avoid; }
tbody tr:nth-child(even) td { background: #fafbfc; }
.num { text-align: right; white-space: nowrap; }
.chip { display: inline-block; padding: 1pt 6pt; border-radius: 9pt; font-size: 7.6pt; font-weight: 700; white-space: nowrap; }
.ok { background: var(--verde-f); color: var(--verde); } .parcial { background: var(--ambar-f); color: var(--ambar); }
.bloq { background: var(--rojo-f); color: var(--rojo); } .demo { background: var(--gris-f); color: var(--suave); }
.alta { background: var(--rojo-f); color: var(--rojo); } .media { background: var(--ambar-f); color: var(--ambar); } .baja { background: var(--gris-f); color: var(--suave); }
.caja { border: 1px solid var(--linea); border-radius: 6pt; padding: 7pt 9pt; margin: 0 0 8pt; background: #fff; }
.caja.destacada { border-left: 4px solid var(--cian); background: var(--cian-f); }
.caja.aviso { border-left: 4px solid var(--ambar); background: var(--ambar-f); }
.rejilla2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8pt; }
.rejilla3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8pt; }
.cifras { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6pt; margin: 4pt 0 8pt; }
.cifra { border: 1px solid var(--linea); border-radius: 6pt; padding: 6pt 8pt; }
.cifra b { display: block; font-size: 13pt; color: var(--azul); line-height: 1.2; }
.cifra span { font-size: 7.8pt; color: var(--suave); }
/* portada */
.portada { page: portada; height: 297mm; padding: 0; position: relative; background: var(--azul); color: #fff; overflow: hidden; }
.portada .franja { position: absolute; left: 0; right: 0; bottom: 0; height: 92mm; background: #0b2233; }
.portada .contenido { position: absolute; left: 22mm; right: 22mm; top: 62mm; }
.portada .marca { font-size: 10pt; letter-spacing: .3em; text-transform: uppercase; color: #8fd3d8; margin-bottom: 10pt; }
.portada h1 { color: #fff; font-size: 34pt; margin-bottom: 10pt; }
.portada .sub { font-size: 14pt; color: #d5e4ec; max-width: 150mm; }
.portada .pie { position: absolute; left: 22mm; right: 22mm; bottom: 26mm; font-size: 10pt; color: #c3d3dd; }
.portada .pie b { color: #fff; }
.radar { position: absolute; right: -40mm; top: -30mm; width: 170mm; height: 170mm; opacity: .16; }
/* pipelines */
.pipeline { margin: 4pt 0 8pt; }
.carril { display: flex; align-items: stretch; gap: 0; margin-bottom: 5pt; }
.carril .etq { writing-mode: vertical-rl; transform: rotate(180deg); font-size: 7pt; font-weight: 700; color: var(--tenue);
  text-transform: uppercase; letter-spacing: .06em; padding: 0 3pt; text-align: center; }
.paso { flex: 1 1 0; min-width: 0; border-radius: 5pt; padding: 5pt 6pt; font-size: 7.9pt; line-height: 1.3; border: 1px solid; }
.paso b { display: block; font-size: 8.2pt; margin-bottom: 1pt; }
.paso i { font-style: normal; display: block; color: var(--suave); font-size: 7.2pt; margin-top: 2pt; }
.flecha { flex: 0 0 13pt; display: flex; align-items: center; justify-content: center; color: var(--tenue); font-size: 11pt; }
.t-persona { background: var(--ambar-f); border-color: #e8c98a; }
.t-fuente { background: #e6eef8; border-color: #b5c9e3; }
.t-ia { background: var(--morado-f); border-color: #cdb6ea; }
.t-radar { background: var(--cian-f); border-color: #9fd0d4; }
.t-salida { background: var(--verde-f); border-color: #a9d8bb; }
.t-pendiente { background: #fff; border-color: #c4ccd3; border-style: dashed; color: var(--suave); }
.leyenda { display: flex; flex-wrap: wrap; gap: 10pt; font-size: 7.6pt; color: var(--suave); margin: 2pt 0 8pt; }
.leyenda span::before { content: ""; display: inline-block; width: 9pt; height: 9pt; border-radius: 2pt; margin-right: 4pt; vertical-align: -1pt; border: 1px solid; }
.leyenda .l-persona::before { background: var(--ambar-f); border-color: #e8c98a; }
.leyenda .l-fuente::before { background: #e6eef8; border-color: #b5c9e3; }
.leyenda .l-ia::before { background: var(--morado-f); border-color: #cdb6ea; }
.leyenda .l-radar::before { background: var(--cian-f); border-color: #9fd0d4; }
.leyenda .l-salida::before { background: var(--verde-f); border-color: #a9d8bb; }
.leyenda .l-pendiente::before { background: #fff; border-color: #c4ccd3; border-style: dashed; }
/* ficha de módulo */
.modulo-cab { display: flex; justify-content: space-between; align-items: baseline; gap: 10pt; }
.modulo-cab h2 { flex: 1; }
.ficha { display: grid; grid-template-columns: 1fr 1fr; gap: 6pt 12pt; }
.ficha > div { break-inside: avoid; }
/* arquitectura */
.arq { display: grid; grid-template-columns: 1.05fr 18pt 1.25fr 18pt 1.7fr; align-items: stretch; margin: 6pt 0 8pt; }
.arq .col { display: flex; flex-direction: column; gap: 6pt; }
.arq .bloque { border: 1px solid var(--linea); border-radius: 6pt; padding: 6pt 8pt; font-size: 8.2pt; }
.arq .bloque b { display: block; color: var(--azul); font-size: 8.8pt; }
.arq .med { display: flex; align-items: center; justify-content: center; font-size: 14pt; color: var(--tenue); }
.arq .ext { display: grid; grid-template-columns: 1fr 1fr; gap: 5pt; }
/* ER */
.grupo-er { border: 1px solid var(--linea); border-radius: 6pt; padding: 4pt 6pt 2pt; break-inside: avoid; }
.grupo-er h4 { margin: 2pt 0 2pt; }
.er-svg text { font-family: 'Segoe UI', Arial, sans-serif; }
.leyenda-er { display: flex; flex-wrap: wrap; gap: 12pt; font-size: 7.8pt; color: var(--suave); margin: 4pt 0 6pt; }
.rejilla-er { display: grid; grid-template-columns: 1fr 1fr; gap: 6pt 10pt; }
.rejilla-er .er-svg { max-height: 62mm; display: block; margin: 0 auto; }
.dicc { columns: 2; column-gap: 12pt; }
.dicc .tabla-er { break-inside: avoid; margin-bottom: 8pt; }
.dicc table { font-size: 7.4pt; margin: 0; }
.dicc th { padding: 2.5pt 4pt; font-size: 7.6pt; }
.dicc td { padding: 1.6pt 4pt; }
.dicc .desc { font-size: 7.4pt; color: var(--suave); margin: 1pt 0 2pt; }
.k { font-weight: 700; font-size: 6.6pt; padding: 0 3pt; border-radius: 3pt; }
.k-pk { background: #12324a; color: #fff; } .k-fk { background: #0e7c86; color: #fff; } .k-ref { background: #e3f3f4; color: #0e7c86; } .k-uq { background: #eef1f4; color: #4a5866; }
"""

RADAR_SVG = """<svg class="radar" viewBox="0 0 200 200"><g fill="none" stroke="#8fd3d8" stroke-width="1.2">
<circle cx="100" cy="100" r="95"/><circle cx="100" cy="100" r="70"/><circle cx="100" cy="100" r="45"/><circle cx="100" cy="100" r="20"/>
<line x1="100" y1="5" x2="100" y2="195"/><line x1="5" y1="100" x2="195" y2="100"/></g>
<path d="M100 100 L100 5 A95 95 0 0 1 182 52 Z" fill="#8fd3d8" opacity=".35"/><circle cx="140" cy="60" r="4" fill="#fff"/><circle cx="70" cy="140" r="3" fill="#fff"/></svg>"""


def chip(texto, clase):
    return f'<span class="chip {clase}">{e(texto)}</span>'


def pipeline(carriles):
    """carriles: [(etiqueta, [(tipo, titulo, detalle), ...]), ...]"""
    out = ['<div class="pipeline nosplit">']
    for etq, pasos in carriles:
        out.append('<div class="carril">')
        if etq:
            out.append(f'<div class="etq">{e(etq)}</div>')
        for i, (tipo, titulo, detalle) in enumerate(pasos):
            if i:
                out.append('<div class="flecha">&#10140;</div>')
            out.append(f'<div class="paso t-{tipo}"><b>{e(titulo)}</b>{e(detalle)}</div>')
        out.append('</div>')
    out.append('</div>')
    return ''.join(out)


LEYENDA = ('<div class="leyenda"><span class="l-persona">Persona / aprobación</span><span class="l-fuente">Fuente de datos externa</span>'
           '<span class="l-ia">Inteligencia artificial</span><span class="l-radar">Proceso del Radar</span>'
           '<span class="l-salida">Resultado</span><span class="l-pendiente">Pendiente (aún no conectado)</span></div>')


def tabla(cabeceras, filas, anchos=None):
    col = ''.join(f'<col style="width:{a}">' for a in anchos) if anchos else ''
    cab = ''.join(f'<th>{c}</th>' for c in cabeceras)
    cuerpo = ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in f) + '</tr>' for f in filas)
    return f'<table><colgroup>{col}</colgroup><thead><tr>{cab}</tr></thead><tbody>{cuerpo}</tbody></table>'


def ul(items):
    return '<ul>' + ''.join(f'<li>{i}</li>' for i in items) + '</ul>'


def modulo(num, nombre, estado_chip, objetivo, flujo, herramientas, estado, falta, propuesta, extra=''):
    return f"""
<section class="salto">
  <div class="modulo-cab"><h2>{num}. {e(nombre)}</h2>{estado_chip}</div>
  <div class="caja destacada"><b>Qué busca lograr.</b> {objetivo}</div>
  <h4>Cómo funciona</h4>
  {flujo}
  {extra}
  <div class="ficha">
    <div><h4>Herramientas</h4>{herramientas}</div>
    <div><h4>Estado actual (6 nov 2026)</h4>{estado}</div>
    <div><h4>Qué falta / accesos</h4>{falta}</div>
    <div><h4>Propuesta</h4>{propuesta}</div>
  </div>
</section>"""


# ───────────────────────── contenido del informe ─────────────────────────
def portada():
    return f"""<section class="portada">{RADAR_SVG}<div class="franja"></div>
<div class="contenido"><div class="marca">Le Cordon Bleu Perú · Marketing</div>
<h1>Radar de Marketing</h1>
<div class="sub">Informe de estado, flujo de cada módulo, accesos pendientes, herramientas y costos, y propuesta de siguientes pasos.</div></div>
<div class="pie"><b>Para:</b> Gerencia y área de Marketing<br><b>Preparado por:</b> Alexander Pedemonte<br><b>Fecha:</b> {FECHA}</div></section>"""


def resumen():
    filas = [
        ['Análisis de competencia', chip('Operativo', 'ok'), 'Qué anuncia la competencia en Facebook e Instagram; mensajes saturados y espacios libres.', 'Nada para operar.'],
        ['Plan SEO', chip('Operativo', 'ok'), 'Contenido para Google basado en búsquedas reales; mejora de páginas existentes.', 'Activar el flujo semanal; volumen de búsqueda real.'],
        ['Medición · anuncios Meta', chip('Operativo', 'ok'), 'Gasto, leads, conversaciones y costos por campaña, con alertas e informe con IA.', 'Nada para operar.'],
        ['Medición · web (GA4)', chip('Falta acceso', 'bloq'), 'Lo que pasa en la web después del clic: visitas, campañas UTM, formularios.', 'Rol Lector en GA4 (Marketing).'],
        ['KeyWords Explorer', chip('Demostración', 'demo'), 'Cuánto busca la gente cada palabra en Google (como Ahrefs, sin licencia).', 'Verificación de marca de Google y acceso Básico de Google Ads.'],
        ['Publicaciones', chip('Manual', 'parcial'), 'Posts para Facebook, Instagram y LinkedIn con aprobación y auditoría.', 'App de Meta, n8n y Azure para publicar solo.'],
        ['Videos', chip('Probado, sin uso', 'parcial'), 'Reels cortos generados con IA (Google Vids), con guion y aprobación.', 'Sesión en Vids, logo oficial, más cupo de clips.'],
        ['Plataforma (usuarios, seguridad)', chip('En laptop', 'parcial'), 'Acceso con usuario y roles, auditoría, informes guardados.', 'Servidor para que funcione 24/7 y para el equipo.'],
    ]
    return f"""
<section class="salto">
<h2>Resumen ejecutivo</h2>
<p><b>Radar</b> es una plataforma interna que reúne en un solo lugar lo que hoy Marketing hace con varias herramientas sueltas o a mano:
<b>vigilar a la competencia, planificar el SEO, producir contenidos (artículos, posts y videos) y medir qué funciona</b>. Usa
inteligencia artificial para clasificar, redactar y resumir, pero <b>nada se publica sin aprobación de una persona</b> y las cifras salen
de las fuentes oficiales (Meta, Google), no de la IA.</p>
<div class="cifras">
  <div class="cifra"><b>6 módulos</b><span>3 operativos, 3 en marcha parcial</span></div>
  <div class="cifra"><b>US$ 0 / mes</b><span>costo actual (planes gratuitos)</span></div>
  <div class="cifra"><b>≈ US$ 40–50</b><span>costo mensual recomendado</span></div>
  <div class="cifra"><b>14 accesos</b><span>a solicitar (6 de prioridad alta)</span></div>
</div>
{tabla(['Módulo', 'Estado', 'Para qué sirve', 'Qué lo frena'], filas, ['21%', '13%', '40%', '26%'])}
<h3>Lo que se pide a gerencia</h3>
<div class="rejilla3">
 <div class="caja"><b>1. Aprobar los accesos de Marketing</b><br><span class="chico">GA4 (Lector), Search Console (Propietario), publicar dos páginas
 en ilcb.edu.pe y acceso al Business Manager de Meta. Sin costo. Detalle en la sección «Accesos a solicitar».</span></div>
 <div class="caja"><b>2. Activar la facturación de la IA</b><br><span class="chico">Gemini de pago: ≈ US$ 5–15 al mes. Evita que Google use nuestros datos
 para mejorar sus productos (sí lo hace en el plan gratuito) y cumple la política que exige Google. Además, dos modelos que usa
 el Radar se retiran el 1 de diciembre de 2026.</span></div>
 <div class="caja"><b>3. Llevar el Radar a un servidor</b><br><span class="chico">Hoy corre en una laptop: si está apagada no se actualizan los
 anuncios ni corre el SEO semanal, y el equipo de Marketing no puede entrar. Servidor en Azure ≈ US$ 30–35 al mes.</span></div>
</div>
</section>"""


def arquitectura():
    return f"""
<section class="salto">
<h2>Cómo está construido y cómo interactúan las herramientas</h2>
<p>El Radar tiene tres piezas propias: el <b>panel web</b> que usa el equipo, el <b>servidor</b> que guarda todo en una base de datos y
controla permisos, aprobaciones y tareas programadas, y el <b>worker</b>, que es el único que habla con los servicios externos
(Google, Meta, la IA, WordPress). Las claves de acceso viven solo en el worker; nada se comparte con terceros salvo lo indicado.</p>
<div class="arq">
 <div class="col">
  <div class="bloque t-persona"><b>Equipo de Marketing</b>Administradores (aprueban) y miembros (preparan).</div>
  <div class="bloque t-radar"><b>Panel web</b>Vue 3 · menús: Análisis de competencia, Informes, KeyWords Explorer, Plan SEO, Videos, Publicaciones, Medición, Usuarios, Ajustes.</div>
 </div>
 <div class="med">&#10140;</div>
 <div class="col">
  <div class="bloque t-radar"><b>Servidor (backend)</b>Kotlin · Spring Boot. Usuarios y roles, aprobaciones, historial, tareas programadas (Meta 7:20 diario, SEO semanal).</div>
  <div class="bloque t-radar"><b>Base de datos</b>SQLite · 24 tablas (ver Anexo A). Informes, artículos, posts, cifras de Meta y Search Console.</div>
  <div class="bloque t-radar"><b>Worker</b>Python · FastAPI. Conectores, rastreador web, IA, navegador controlado (Biblioteca de anuncios, Google Vids).</div>
 </div>
 <div class="med">&#10140;</div>
 <div class="col"><div class="ext">
  <div class="bloque t-fuente"><b>Google</b>Search Console · Analytics 4 · Ads (Keyword Planner) · autocompletado</div>
  <div class="bloque t-fuente"><b>Meta</b>Marketing API (anuncios propios) · Biblioteca de anuncios (competencia)</div>
  <div class="bloque t-ia"><b>IA</b>Google Gemini (texto e imagen) · Google Vids (video)</div>
  <div class="bloque t-fuente"><b>Web y contenido</b>WordPress de ilcb.edu.pe · Pixabay (fotos libres)</div>
  <div class="bloque t-pendiente"><b>Publicación automática</b>n8n · Meta Graph API · LinkedIn API</div>
  <div class="bloque t-pendiente"><b>Infraestructura</b>Azure (servidor e imágenes públicas)</div>
 </div></div>
</div>
{LEYENDA}
<h3>Cómo se conectan los módulos entre sí</h3>
{pipeline([
    ('', [('radar', 'Análisis de competencia', 'qué anuncian y qué hueco queda'),
          ('radar', 'Plan SEO', 'temas y artículos que faltan'),
          ('radar', 'Publicaciones y Videos', 'posts y reels a partir de artículos o ideas'),
          ('salida', 'Redes y web', 'con enlaces etiquetados (UTM)'),
          ('radar', 'Medición', 'anuncios (Meta) + web (GA4) → qué funcionó')]),
])}
<p class="chico suave">Los enlaces de cada post llevan etiquetas UTM automáticas, así GA4 puede atribuir cada visita a la red, campaña y
anuncio de origen. La medición cierra el ciclo: muestra qué mensajes y canales rinden mejor y alimenta el siguiente análisis.</p>
<h3>Principios que aplica el Radar</h3>
{ul(['<b>Aprobación humana:</b> artículos, posts y videos llegan como borrador; solo un administrador aprueba y nada se publica solo.',
     '<b>Cifras de fuente oficial:</b> los totales de Medición coinciden con los de Meta; la IA solo redacta con cifras ya calculadas.',
     '<b>Términos protegidos:</b> ninguna propuesta cambia los nombres oficiales de carreras ni de sistemas (p. ej. Matrix).',
     '<b>Trazabilidad:</b> nada se borra (se archiva); cada post guarda su historial y cada informe queda guardado para comparar periodos.',
     '<b>Solo lectura en cuentas de la institución:</b> el Radar lee Meta, Search Console y GA4; no cambia campañas ni configuraciones.'])}
</section>"""


def modulos():
    m = []
    m.append(modulo(1, 'Análisis de competencia (e Informes)', chip('Operativo', 'ok'),
        'Saber qué anuncian las instituciones de la competencia en Facebook e Instagram, qué mensajes están saturados y qué espacios '
        'quedan libres para diferenciar a ILCB. Reemplaza la revisión manual, anuncio por anuncio, de la Biblioteca de anuncios de Meta.',
        pipeline([('', [('persona', 'Elegir competidores', 'páginas de Facebook, fechas y fecha mínima'),
                         ('fuente', 'Biblioteca de anuncios de Meta', 'lectura pública con navegador'),
                         ('radar', 'Normalizar y guardar', 'texto, formato, fechas y miniaturas'),
                         ('ia', 'Clasificar cada anuncio', 'oferta, mensaje, formato (Gemini)'),
                         ('radar', 'Calcular saturado / hueco', 'por territorio de mensaje'),
                         ('salida', 'Informe', 'saturados, huecos y ejemplos')])]) + LEYENDA,
        ul(['Biblioteca de anuncios de Meta (gratis, lectura pública).', 'Google Gemini 2.5 Flash-Lite (clasificación).',
            'Respaldo: Apify (≈ US$ 29/mes) si Meta bloquea la lectura.']),
        ul(['7 análisis: 4 terminados, 1 pausado, 2 cancelados.', '4 informes generados (2 archivados).',
            'Costo de IA acumulado: US$ 0,41 (equivalente; hoy en plan gratuito).']),
        ul(['Nada para operar.', 'Riesgo: si Meta cambia su página hay que ajustar el lector; sus condiciones restringen la recolección '
            'automática, por eso se usa de forma moderada e interna.']),
        ul(['Repetir el análisis cada mes de forma automática y mostrar <b>qué cambió</b>: anuncios nuevos, retirados, ofertas y precios.',
            'Aviso por correo cuando un competidor lance una campaña nueva.'])))
    m.append(modulo(2, 'KeyWords Explorer', chip('Demostración', 'demo'),
        'Investigar qué y cuánto busca la gente en Google (volumen mensual, tendencia, temporada, competencia) para decidir sobre qué '
        'escribir y en qué invertir, sin pagar licencias como Ahrefs (US$ 129/mes) o Semrush (US$ 139,95/mes).',
        pipeline([('', [('persona', 'Palabras semilla o URL', 'país e idioma'),
                         ('pendiente', 'Google Ads · Keyword Planner', 'volumen, tendencia 12 meses, CPC'),
                         ('fuente', 'Autocompletado de Google', 'sugerencias y preguntas'),
                         ('radar', 'Agrupar y filtrar', 'intención, nº de palabras, caché 7 días'),
                         ('salida', 'Listas y CSV', 'con notas para el equipo')])]) + LEYENDA,
        ul(['Google Ads API – Keyword Planner (gratis, exige acceso «Básico»).', 'Autocompletado de Google (gratis).']),
        ul(['Funciona en <b>modo demostración</b> (cifras inventadas y marcadas como tales).',
            'Google Ads configurado: cuenta administradora «Radar ILCB» (798-743-8860) y cuenta 684-578-3537.',
            'El nivel «Explorador» no permite Keyword Planner; el «Básico» fue rechazado por falta de verificación de marca.']),
        ul(['Publicar las páginas /radar/ y /radar/privacidad/ (ya están como borrador).', 'Rol Propietario en Search Console.',
            'Verificar la marca en Google Cloud y volver a pedir el acceso Básico.']),
        ul(['Si la verificación se demora: <b>DataForSEO</b>, pago por uso (≈ US$ 0,05–0,09 por consulta de hasta 1 000 palabras; depósito mínimo US$ 50).',
            'Opcional: vincular la cuenta de Google Ads de ILCB (solo lectura) para obtener volúmenes exactos en lugar de rangos.'])))
    m.append(modulo(3, 'Plan SEO', chip('Operativo', 'ok'),
        'Atraer postulantes desde Google con contenido sobre lo que la gente realmente busca, priorizando los temas donde la competencia '
        'tiene páginas e ILCB no, y subir las páginas que ya aparecen en las posiciones 4 a 20, sin cambiar nunca los nombres oficiales.',
        pipeline([('Contenido nuevo', [('fuente', 'Sitios', 'ILCB, D\'Gallia, CENFOTUR'),
                                       ('radar', 'Inventario', 'rastreo de sitemaps; fecha mínima'),
                                       ('ia', 'Temas por página', 'Gemini'),
                                       ('radar', 'Keywords y cobertura', '¿ILCB ya lo tiene?'),
                                       ('fuente', '¿La gente lo busca?', 'autocompletado de Google'),
                                       ('ia', 'Redactar artículo', 'Gemini + imagen Pixabay/IA'),
                                       ('salida', 'Borrador en WordPress', 'una persona revisa y publica')]),
                  ('Mejorar lo existente', [('fuente', 'Search Console', '90 días de búsquedas reales'),
                                            ('radar', 'Páginas para mejorar', 'posición 4–20, sin marca'),
                                            ('ia', 'Propuesta', '«dice ahora / debe decir»; términos protegidos'),
                                            ('persona', 'Aplicar en WordPress', 'el Radar no toca páginas publicadas'),
                                            ('salida', 'Informes guardados', 'corte por fecha para comparar')])]) + LEYENDA,
        ul(['Rastreador propio (sitemaps).', 'Google Gemini (temas, agrupación, redacción, mejoras).', 'Autocompletado de Google.',
            'Google Search Console API.', 'WordPress REST API (solo borradores).', 'Pixabay (gratis) o imagen con IA (≈ US$ 0,034 c/u).']),
        ul(['3 sitios y 643 páginas inventariadas; 30 keywords; 6 artículos (5 ya como borrador en WordPress); 4 propuestas de mejora.',
            'Search Console conectado: del 6/08 al 3/11, 54 811 clics y 1 092 992 impresiones.',
            'Términos protegidos: carreras y sistemas (incl. Matrix).', 'Flujo automático semanal: <b>desactivado</b>.']),
        ul(['Activar el flujo automático (2 artículos por semana como borrador).', 'Volumen real de búsqueda: depende de KeyWords Explorer.',
            'Hoy solo corre con la laptop encendida.']),
        ul(['Seguimiento de cada artículo publicado: posición e impresiones a las 2, 4 y 8 semanas.',
            'Sugerir enlaces internos entre artículos y páginas de carreras.', 'Aplicar los términos protegidos también a artículos y posts.'])))
    m.append(modulo(4, 'Publicaciones', chip('Manual', 'parcial'),
        'Producir los posts de Facebook, Instagram y LinkedIn con un flujo ordenado y con <b>auditoría completa</b> de lo que se generó, '
        'quién lo aprobó y si sigue publicado. Cada enlace a la web lleva UTM para medir su resultado.',
        pipeline([('Hoy', [('persona', 'Idea, artículo o video', 'tema y redes'),
                           ('ia', 'Texto y hashtags', 'uno o por red (Gemini)'),
                           ('radar', 'Flyer', 'plantilla + fondo Pixabay, IA o foto'),
                           ('persona', 'Aprobación', 'administrador'),
                           ('persona', 'Publicar a mano', 'y registrar el enlace'),
                           ('salida', 'Biblioteca', 'historial, UTM, ¿sigue activo?')]),
                  ('Fase 2', [('radar', 'Post aprobado', ''),
                              ('pendiente', 'n8n', 'orquesta la publicación'),
                              ('pendiente', 'Azure Blob', 'imagen pública para Instagram'),
                              ('pendiente', 'Meta Graph API / LinkedIn API', 'publica en la página oficial'),
                              ('pendiente', 'Métricas orgánicas', 'alcance e interacción por post')])]) + LEYENDA,
        ul(['Google Gemini (texto, hashtags).', 'Plantilla de flyer propia + Pixabay / Gemini imagen.', 'UTM automáticos.',
            'Fase 2: n8n, Meta Graph API, LinkedIn Community Management API, Azure Blob Storage.']),
        ul(['Flujo completo en modo manual, con aprobación.', '1 post aprobado pendiente de publicar.',
            'Biblioteca: nada se borra (se archiva), historial por post y verificación pública de enlaces.']),
        ul(['App de Meta propia con revisión de Meta y acceso al Business Manager de ILCB.', 'URL de la instancia de n8n (TI).',
            'Contenedor de Azure para imágenes (TI).', 'LinkedIn: administrador de la página y revisión de la API.', '<b>Logo oficial en PNG.</b>']),
        ul(['Calendario editorial con las fechas de publicación.', 'Métricas de cada post orgánico al conectar la app de Meta.',
            'Pruebas primero en una página propia y luego en las oficiales.'])))
    m.append(modulo(5, 'Videos', chip('Probado, sin uso', 'parcial'),
        'Producir reels cortos para redes sin rodaje: guion por escenas, generación con IA de video y aprobación antes de publicar.',
        pipeline([('', [('persona', 'Idea o keyword', 'protagonista, lugar, voz, pronunciación'),
                         ('ia', 'Guion por partes de 10 s', 'diálogo, escena y copys (Gemini)'),
                         ('fuente', 'Google Vids (Veo)', 'clip + extensiones, mismo personaje'),
                         ('radar', 'MP4', 'descarga y guarda'),
                         ('persona', 'Aprobación', 'administrador'),
                         ('salida', 'Publicaciones', 'pasa con sus textos')])]) + LEYENDA,
        ul(['Google Gemini (guion).', 'Google Vids con Veo, manejado por un Chrome propio del Radar a ritmo humano.']),
        ul(['Probado en vivo el 30/10: clip de 10 s en ≈ 45 s; extensión en ≈ 2 min.', 'Sin videos en curso.',
            'Plan gratuito de Vids: ≈ 10 clips al mes.']),
        ul(['Iniciar sesión en Vids en el Chrome del Radar.', 'Logo oficial en PNG para el montaje.',
            'Más cupo: Google AI Pro ≈ US$ 19,99/mes (≈ 50 clips).']),
        ul(['Montaje automático con logo, subtítulos y cierre con llamada a la acción.']))
    )
    m.append(modulo(6, 'Medición', chip('Meta operativo · GA4 pendiente', 'parcial'),
        'Saber <b>qué funciona</b> con cifras reales: cuánto cuesta cada lead y cada conversación de WhatsApp por campaña, qué campañas se '
        'encarecen y qué pasa en la web después del clic. Detectar a tiempo, sin revisar Ads Manager a diario.',
        pipeline([('Anuncios', [('fuente', 'Meta Marketing API', 'cada día 7:20, por anuncio y día'),
                                ('radar', 'Cifras y tipo de campaña', 'leads vs WhatsApp, sin mezclarlos'),
                                ('radar', 'Alertas', 'se encarece, cae el CTR, gasto sin resultados'),
                                ('ia', 'Informe redactado', 'Gemini, solo con cifras calculadas'),
                                ('salida', 'Informes guardados', 'por periodo')]),
                  ('Web', [('radar', 'UTM en posts y anuncios', 'red, campaña y anuncio'),
                           ('pendiente', 'GA4 Data API', 'requiere rol Lector'),
                           ('pendiente', 'Canales, campañas, páginas', 'y eventos clave (formularios)'),
                           ('pendiente', 'Costo por matrícula', 'propuesta: cruce con admisión')])]) + LEYENDA
        + """<div class="cifras"><div class="cifra"><b>US$ 23 925</b><span>gasto, 7/10–5/11 (+44 %)</span></div>
<div class="cifra"><b>9 857 · US$ 1,68</b><span>leads y costo por lead</span></div>
<div class="cifra"><b>3 522 · US$ 1,38</b><span>conversaciones WhatsApp y costo</span></div>
<div class="cifra"><b>0,85 %</b><span>CTR de enlace (+8 %)</span></div></div>""",
        ul(['Meta Marketing API (token de lectura de Marketing, solo «ads_read»).', 'Google Analytics 4 Data y Admin API.',
            'Google Gemini (redacción).', 'UTM y constructor de enlaces.']),
        ul(['Anuncios de Meta: 12 255 filas diarias por anuncio; totales verificados idénticos a Meta.',
            'GA4: APIs activas y conexión con Google válida; <b>falta el rol Lector</b> en la propiedad real (ID de medición G-JBVGFPM4EZ, conectada por Site Kit).',
            'Por error se creó hoy una propiedad nueva vacía («Radar», G-KWFC3LJN1B): no usarla.']),
        ul(['Rol Lector en GA4 para alexander.pedemonte10@gmail.com.', 'Métricas orgánicas de posts: requieren la app de Meta.']),
        ul(['<b>Costo por matrícula</b> por campaña, cruzando leads con la lista de admisión o el CRM.',
            'Informe semanal automático por correo o Teams.', 'Microsoft Clarity (ya instalado en la web) para ver dónde abandonan los formularios.']))
    )
    m.append(modulo(7, 'Plataforma: usuarios, seguridad e informes guardados', chip('En laptop', 'parcial'),
        'Que el equipo de Marketing use el Radar con su propio usuario, con permisos según su rol, y que todo quede registrado.',
        pipeline([('', [('persona', 'Usuario y contraseña', 'rol administrador o miembro'),
                         ('radar', 'Sesión y permisos', 'bloqueo por intentos fallidos'),
                         ('radar', 'Auditoría', 'altas, cambios de rol, aprobaciones'),
                         ('salida', 'Informes guardados', 'Search Console, keywords, medición')])]) + LEYENDA,
        ul(['Servidor propio (Kotlin), base de datos SQLite.', 'Contraseñas con hash y sal; cookie de sesión.']),
        ul(['1 usuario (administrador).', 'Corre en una laptop (localhost): sin ella encendida no hay tareas programadas ni acceso del equipo.',
            'Copias de seguridad manuales antes de cada cambio de datos.']),
        ul(['Servidor en Azure (TI) con HTTPS.', 'Lista del equipo de Marketing que usará el Radar y su rol.']),
        ul(['Servidor Azure B2s (≈ US$ 30–35/mes) con copia de seguridad diaria.', 'Vista única de todos los informes guardados en el menú «Informes».']))
    )
    return ''.join(m)


ACCESOS = [
    ('Alta', 'GA4', 'Rol <b>Lector</b> en la propiedad de ilcb.edu.pe conectada por Site Kit (ID de medición <b>G-JBVGFPM4EZ</b>) para alexander.pedemonte10@gmail.com', 'Marketing', 'Medición (web)'),
    ('Alta', 'Search Console', 'Rol <b>Propietario</b> de sc-domain:ilcb.edu.pe (hoy tiene «Completo»)', 'Marketing', 'Verificación de marca → KeyWords Explorer'),
    ('Alta', 'WordPress', 'Completar el correo de contacto y <b>publicar</b> las páginas borrador 3173 (/radar/) y 3174 (/radar/privacidad/)', 'Marketing / Web', 'Verificación de marca de Google'),
    ('Alta', 'Correo de contacto', 'Un correo institucional de Marketing para las páginas y la pantalla de permisos de Google', 'Marketing', 'Verificación de marca'),
    ('Alta', 'Facturación Gemini', 'Activar facturación en el proyecto de Google Cloud «Radar» (tarjeta corporativa)', 'Gerencia / TI', 'Toda la IA; política de «uso limitado»'),
    ('Alta', 'Modelos de IA', 'Cambiar los modelos gemini-2.5-flash / flash-lite, que Google retira el 1/12/2026', 'Desarrollo', 'Toda la IA'),
    ('Media', 'Meta Business Manager', 'Acceso al Business Manager de ILCB para crear una app propia; Página de Facebook e Instagram profesional; verificación de empresa y revisión de permisos (pages_show_list, pages_read_engagement, pages_manage_posts, instagram_business_basic, instagram_business_content_publish, read_insights)', 'Marketing', 'Publicaciones automáticas y métricas orgánicas'),
    ('Media', 'LinkedIn', 'Rol administrador de la página de empresa de ILCB y alta de una app con Community Management API (revisión de LinkedIn; usa la misma política de privacidad)', 'Marketing', 'Publicaciones en LinkedIn'),
    ('Media', 'Logo oficial', 'PNG con fondo transparente (versión clara y oscura) y manual de marca', 'Marketing', 'Flyers y videos'),
    ('Media', 'n8n', 'URL de la instancia, usuario y forma de acceso desde el servidor del Radar', 'TI', 'Publicación automática'),
    ('Media', 'Azure', 'Contenedor Blob para imágenes públicas y servidor para alojar el Radar', 'TI / Gerencia', 'Instagram; Radar 24/7'),
    ('Media', 'Admisión / CRM', 'Exportación periódica de leads y matriculados (o acceso de lectura al CRM)', 'Admisión / Marketing', 'Costo por matrícula'),
    ('Baja', 'Google Ads ILCB', 'Vincular la cuenta de Google Ads de ILCB al MCC «Radar ILCB» (798-743-8860) con acceso de lectura', 'Marketing', 'Volúmenes exactos de búsqueda'),
    ('Baja', 'Microsoft Clarity', 'Acceso de lectura al proyecto de Clarity de la web', 'Marketing', 'Comportamiento en formularios'),
]


def accesos():
    filas = [[chip(p, p.lower()), f'<b>{e(q)}</b>', d, e(r), e(u)] for p, q, d, r, u in ACCESOS]
    return f"""
<section class="salto">
<h2>Accesos a solicitar</h2>
<p>Esto es lo que hoy no se tiene y frena algún módulo. Ninguno tiene costo salvo la facturación de la IA y Azure. La cuenta de Google
del Radar es <b>alexander.pedemonte10@gmail.com</b> (no es Google Workspace), por eso los accesos de Google van a ese correo.</p>
{tabla(['Prioridad', 'Qué', 'Detalle', 'Lo da', 'Destraba'], filas, ['9%', '14%', '47%', '12%', '18%'])}
<div class="caja aviso chico"><b>Ya resuelto en esta etapa:</b> conexión con Google renovada y sin vencimiento (app en producción), Search Console
operativo, APIs de Analytics activadas, token de lectura de anuncios de Meta (entregado por Marketing), WordPress y Pixabay conectados.</div>
</section>"""


HERR_ACTUALES = [
    ('Google Gemini API', 'IA: clasificar, redactar, resumir, imágenes', 'Todos', chip('En uso', 'ok'), 'Gratis (plan actual). Pago: US$ 0,10–0,50 por millón de tokens de entrada y US$ 0,40–3,00 de salida; imagen ≈ US$ 0,034', 'Facturación en Google Cloud'),
    ('Biblioteca de anuncios de Meta', 'Anuncios de la competencia', 'Competencia', chip('En uso', 'ok'), 'Gratis', 'Ninguno'),
    ('Meta Marketing API', 'Rendimiento de anuncios propios', 'Medición', chip('En uso', 'ok'), 'Gratis', 'Token de lectura (entregado)'),
    ('Google Search Console API', 'Búsquedas donde aparece la web', 'Plan SEO', chip('En uso', 'ok'), 'Gratis', 'Usuario en Search Console (tiene)'),
    ('Google Analytics 4 API', 'Visitas y conversiones de la web', 'Medición', chip('Falta acceso', 'bloq'), 'Gratis', 'Rol Lector'),
    ('Google Ads API (Keyword Planner)', 'Volumen de búsqueda', 'KeyWords, SEO', chip('Bloqueado', 'bloq'), 'Gratis', 'Acceso Básico (verificación de marca)'),
    ('Autocompletado de Google', 'Señal de demanda', 'SEO, KeyWords', chip('En uso', 'ok'), 'Gratis', 'Ninguno'),
    ('WordPress REST API', 'Borradores de artículos', 'Plan SEO', chip('En uso', 'ok'), 'Gratis', 'Contraseña de aplicación (tiene)'),
    ('Pixabay API', 'Fotos libres de uso', 'SEO, Publicaciones', chip('En uso', 'ok'), 'Gratis', 'Clave (tiene)'),
    ('Google Vids (Veo)', 'Clips de video', 'Videos', chip('Probado', 'parcial'), 'Gratis ≈ 10 clips/mes', 'Cuenta de Google'),
    ('Radar (Kotlin, Python, Vue, SQLite)', 'La plataforma', 'Todos', chip('En laptop', 'parcial'), 'US$ 0 (desarrollo propio)', '—'),
]
HERR_PROPUESTAS = [
    ('Servidor Azure B2s (Linux)', 'Radar 24/7 y acceso del equipo', 'Plataforma', 'Recomendado', '≈ US$ 30/mes + disco ≈ US$ 5', 'TI'),
    ('Gemini de pago', 'Privacidad de datos y continuidad', 'Todos', 'Recomendado', '≈ US$ 5–15/mes con el uso actual', 'Facturación'),
    ('Azure Blob Storage', 'Imágenes públicas para Instagram', 'Publicaciones', 'Recomendado', '≈ US$ 0,02 por GB/mes (< US$ 1)', 'TI'),
    ('n8n', 'Publicar en redes', 'Publicaciones', 'Recomendado', 'Community (en el servidor): gratis · Cloud Starter ≈ € 24/mes', 'TI'),
    ('Meta Graph API (app propia)', 'Publicar y métricas orgánicas', 'Publicaciones, Medición', 'Recomendado', 'Gratis', 'Business Manager + revisión de Meta'),
    ('LinkedIn Community Management API', 'Publicar como página', 'Publicaciones', 'Recomendado', 'Gratis', 'Revisión de LinkedIn'),
    ('Google AI Pro', '≈ 50 clips de video al mes', 'Videos', 'Opcional', '≈ US$ 19,99/mes', 'Cuenta de Google'),
    ('DataForSEO', 'Volumen si no llega Google Ads', 'KeyWords, SEO', 'Opcional', '≈ US$ 0,05–0,09 por consulta (depósito mín. US$ 50)', 'Tarjeta'),
    ('SerpApi', 'Google Trends y resultados de Google', 'SEO', 'Opcional', 'Gratis 250 búsquedas/mes · Starter US$ 25/mes', '—'),
    ('Microsoft Clarity', 'Mapas de calor y grabaciones', 'Medición', 'Opcional', 'Gratis (ya instalado en la web)', 'Acceso al proyecto'),
    ('Apify', 'Respaldo para anuncios de competencia', 'Competencia', 'Respaldo', '≈ US$ 29/mes (Starter)', '—'),
    ('Ahrefs Lite / Semrush Pro', 'Referencia de lo que reemplaza el Radar', 'SEO', 'No recomendado', 'US$ 129 / US$ 139,95 al mes', '—'),
]


def herramientas():
    a = [[f'<b>{e(n)}</b>', e(p), e(mo), ch, c, e(ac)] for n, p, mo, ch, c, ac in HERR_ACTUALES]
    b = [[f'<b>{e(n)}</b>', e(p), e(mo), chip(t, {'Recomendado': 'ok', 'Opcional': 'demo', 'Respaldo': 'demo'}.get(t, 'bloq')), e(c), e(ac)]
         for n, p, mo, t, c, ac in HERR_PROPUESTAS]
    costos = [['Hoy', 'US$ 0', 'IA en plan gratuito (consumo equivalente acumulado: US$ 0,68 en 78 llamadas, 20/10–3/11); laptop; APIs gratuitas.'],
              ['Recomendado', '≈ US$ 40–50', 'Gemini de pago (5–15) + servidor Azure (30–35) + Blob (&lt; 1) + n8n en el mismo servidor (0).'],
              ['Con opcionales', '≈ US$ 60–95', 'Más Google AI Pro (19,99) y SerpApi Starter (25). DataForSEO: depósito único de US$ 50 que dura meses.'],
              ['Referencia', 'US$ 129–140', 'Solo una licencia de Ahrefs o Semrush, que cubre parte del Plan SEO y KeyWords Explorer.']]
    return f"""
<section class="salto">
<h2>Herramientas: las que se usan y las que conviene sumar</h2>
<h3>En uso hoy</h3>
{tabla(['Herramienta', 'Para qué', 'Módulo', 'Estado', 'Costo', 'Acceso'], a, ['20%', '19%', '12%', '10%', '24%', '15%'])}
<h3>Propuestas</h3>
{tabla(['Herramienta', 'Para qué', 'Módulo', 'Tipo', 'Costo', 'Acceso'], b, ['20%', '20%', '13%', '11%', '23%', '13%'])}
<h3>Costo mensual estimado</h3>
{tabla(['Escenario', 'Por mes', 'Qué incluye'], costos, ['16%', '14%', '70%'])}
<p class="chico tenue">Precios en dólares, consultados el 6/11/2026 en las páginas de cada proveedor o en comparadores (ver Anexo B). Pueden
variar por región e impuestos; confirmar antes de contratar. El costo de la IA depende del volumen: se estimó a partir del consumo real medido.</p>
</section>"""


def hoja_ruta():
    filas = [
        ['<b>0 · Esta semana</b>', 'Accesos de prioridad alta (GA4, Search Console Propietario, publicar páginas, correo de contacto); activar facturación de Gemini y actualizar los modelos antes del 1/12.', 'GA4 en Medición; verificación de marca enviada.'],
        ['<b>1 · Noviembre–diciembre</b>', 'Servidor en Azure con HTTPS y usuarios del equipo de Marketing; flujo SEO semanal activo; informe semanal por correo.', 'Radar disponible 24/7 para el equipo; 2 artículos por semana en borrador.'],
        ['<b>2 · Diciembre–enero</b>', 'App de Meta + n8n + Azure Blob; LinkedIn; logo y montaje de videos; acceso Básico de Google Ads.', 'Publicación con un clic tras la aprobación; métricas orgánicas; volúmenes reales.'],
        ['<b>3 · Enero–febrero</b>', 'Costo por matrícula (cruce con admisión); seguimiento mensual de competencia; seguimiento de posiciones de cada artículo.', 'Decisiones de inversión por costo de matrícula, no solo por lead.'],
    ]
    return f"""
<section class="salto">
<h2>Propuesta y hoja de ruta</h2>
<p>La base ya está construida y probada con datos reales. Lo que falta es, sobre todo, <b>accesos</b> y <b>dónde corre</b>. La propuesta
ordena los pasos por impacto y por dependencia:</p>
{tabla(['Fase', 'Qué se hace', 'Resultado'], filas, ['18%', '52%', '30%'])}
<h3>Mejoras propuestas por módulo</h3>
{tabla(['Módulo', 'Mejora', 'Valor para Marketing'], [
    ['Medición', 'Costo por matrícula por campaña', 'Saber qué campaña trae alumnos, no solo contactos.'],
    ['Medición', 'Informe semanal automático (correo / Teams)', 'Cifras y alertas sin entrar al Radar.'],
    ['Competencia', 'Análisis mensual con «qué cambió»', 'Reaccionar a nuevas ofertas de la competencia.'],
    ['Plan SEO', 'Seguimiento de posiciones por artículo', 'Saber si cada artículo publicado atrae búsquedas.'],
    ['Plan SEO / Publicaciones', 'Términos protegidos en todos los textos', 'Nombres oficiales siempre correctos.'],
    ['Publicaciones', 'Calendario editorial y publicación automática', 'Menos trabajo manual, mismo control.'],
    ['Videos', 'Montaje con logo y subtítulos', 'Reels listos para publicar.'],
    ['Plataforma', 'Vista única de informes guardados', 'Un solo lugar para el historial de todo.'],
], ['18%', '42%', '40%'])}
<div class="caja destacada"><b>Riesgos a tener presentes.</b> La lectura de la Biblioteca de anuncios depende de la página de Meta; las
revisiones de Meta y LinkedIn pueden tardar semanas; mientras el Radar corra en una laptop no hay continuidad del servicio.</div>
</section>"""


# ───────────────────────── modelo entidad-relación ─────────────────────────
DESCRIPCION = {
    'ajuste': 'Configuración clave-valor: rubro, flujo SEO, cuenta de Meta, términos protegidos, sincronizaciones.',
    'analisis': 'Cada análisis de competencia y su avance.', 'auditoria': 'Registro de acciones de seguridad.',
    'consumo_ia': 'Cada llamada a la IA con tokens y costo (por análisis, tarea o módulo).',
    'informe': 'Informe de competencia resultado de un análisis.',
    'informe_guardado': 'Copia fija y comprimida de informes: Search Console, keywords, medición.',
    'kw_busqueda': 'Búsquedas de KeyWords Explorer (caché de 7 días).', 'kw_lista': 'Listas de keywords del equipo.',
    'kw_lista_item': 'Keywords de cada lista, con nota.', 'meta_insight': 'Rendimiento diario de cada anuncio propio de Meta.',
    'miniatura_anuncio': 'Imagen de cada anuncio de la competencia.', 'publicacion': 'Posts para redes: textos, flyer, estado y enlaces.',
    'publicacion_evento': 'Historial de cada post (creado, aprobado, publicado, archivado…).',
    'seo_articulo': 'Artículos SEO y su borrador en WordPress.', 'seo_gsc': 'Búsquedas de Search Console vigentes (consulta y página).',
    'seo_imagen': 'Imagen destacada de cada artículo.', 'seo_keyword': 'Keywords candidatas, su grupo y cobertura.',
    'seo_mejora': 'Propuestas de mejora de páginas existentes.', 'seo_pagina': 'Páginas inventariadas de cada sitio.',
    'seo_sitio': 'Sitios del Plan SEO (propio y competidores).', 'seo_tarea': 'Tareas del Plan SEO (inventario, temas, keywords, artículos, flujo).',
    'sesion': 'Sesiones abiertas.', 'usuario': 'Usuarios del Radar y su rol.', 'video': 'Videos cortos: guion, estado y archivo.',
}

# (tabla, x, y, [(marca, campo, nota)])   marca: PK, FK (física), REF (lógica), UQ, ''
GRUPOS_ER = [
    ('Acceso y configuración', 470, 230, [
        ('usuario', 10, 26, [('PK', 'id_usuario', ''), ('UQ', 'cod_usuario', ''), ('UQ', 'usuario_email', ''), ('', 'usuario_nombre', ''), ('', 'rol', 'admin | miembro'), ('', 'ultimo_acceso', '')]),
        ('sesion', 250, 26, [('PK', 'id_sesion', ''), ('FK', 'id_usuario', ''), ('', 'creado', ''), ('', 'visto', '')]),
        ('auditoria', 250, 128, [('PK', 'id_auditoria', ''), ('REF', 'actor', '→ usuario'), ('', 'accion', ''), ('', 'fecha', '')]),
        ('ajuste', 10, 160, [('PK', 'id_ajuste', ''), ('UQ', 'cod_ajuste', ''), ('', 'ajuste_valor', 'JSON')]),
    ], [('usuario', 'sesion', '1', 'N', False), ('usuario', 'auditoria', '1', 'N', True)]),
    ('Análisis de competencia', 470, 230, [
        ('analisis', 10, 26, [('PK', 'id_analisis', ''), ('UQ', 'cod_analisis', ''), ('', 'peticion_json', ''), ('', 'estado / fase', ''), ('REF', 'cod_informe', '→ informe')]),
        ('informe', 250, 26, [('PK', 'id_informe', ''), ('UQ', 'cod_informe', ''), ('REF', 'cod_analisis', '→ analisis'), ('', 'marca', ''), ('', 'datos_json', 'anuncios')]),
        ('consumo_ia', 10, 140, [('PK', 'id_consumo_ia', ''), ('REF', 'cod_analisis', 'origen'), ('', 'operacion / modelo', ''), ('', 'tokens', ''), ('', 'costo_usd', '')]),
        ('miniatura_anuncio', 250, 140, [('PK', 'id_miniatura', ''), ('UQ', 'ad_id', 'anuncio'), ('', 'datos', 'imagen'), ('', 'mime', '')]),
    ], [('analisis', 'informe', '1', '1', True), ('analisis', 'consumo_ia', '1', 'N', True), ('informe', 'miniatura_anuncio', '1', 'N', True)]),
    ('KeyWords Explorer', 470, 200, [
        ('kw_busqueda', 10, 26, [('PK', 'id_kw_busqueda', ''), ('UQ', 'cod_kw_busqueda', ''), ('', 'clave', 'caché'), ('', 'semillas / país', ''), ('', 'resultado_json', ''), ('REF', 'cod_autor', '→ usuario')]),
        ('kw_lista', 250, 26, [('PK', 'id_kw_lista', ''), ('UQ', 'cod_kw_lista', ''), ('', 'nombre', ''), ('REF', 'cod_autor', '→ usuario')]),
        ('kw_lista_item', 250, 120, [('PK', 'id_kw_lista_item', ''), ('FK', 'id_kw_lista', ''), ('UQ', 'keyword', 'por lista'), ('', 'nota', '')]),
    ], [('kw_lista', 'kw_lista_item', '1', 'N', False)]),
    ('Contenidos: videos y publicaciones', 470, 230, [
        ('video', 10, 26, [('PK', 'id_video', ''), ('UQ', 'cod_video', ''), ('', 'idea / keyword', ''), ('', 'partes_json', 'guion'), ('', 'estado', ''), ('', 'archivo', 'MP4'), ('REF', 'cod_autor', '→ usuario')]),
        ('publicacion', 250, 26, [('PK', 'id_publicacion', ''), ('UQ', 'cod_publicacion', ''), ('', 'origen', 'MANUAL | VIDEO …'), ('REF', 'cod_origen', '→ video'), ('', 'textos / redes', ''), ('', 'estado', ''), ('REF', 'cod_aprobador', '→ usuario'), ('', 'archivada', '')]),
        ('publicacion_evento', 10, 160, [('PK', 'id_evento', ''), ('REF', 'cod_publicacion', ''), ('', 'evento / detalle', ''), ('REF', 'cod_autor', '→ usuario')]),
    ], [('video', 'publicacion', '1', 'N', True), ('publicacion', 'publicacion_evento', '1', 'N', True)]),
    ('Medición e informes guardados', 470, 200, [
        ('meta_insight', 10, 26, [('PK', 'fecha + anuncio_id', ''), ('', 'campana_id / campana', ''), ('', 'conjunto', ''), ('', 'gasto', ''), ('', 'impresiones / clics', ''), ('', 'leads', ''), ('', 'conversaciones', '')]),
        ('informe_guardado', 250, 26, [('PK', 'id_informe_guardado', ''), ('UQ', 'cod_informe_guardado', ''), ('', 'modulo', 'SEARCH_CONSOLE …'), ('', 'resumen_json', ''), ('', 'datos_gz', 'comprimido'), ('REF', 'cod_origen', '→ seo_tarea'), ('REF', 'cod_autor', '→ usuario')]),
    ], []),
]
GRUPO_SEO = ('Plan SEO', 960, 470, [
    ('seo_sitio', 10, 26, [('PK', 'id_seo_sitio', ''), ('UQ', 'cod_seo_sitio', ''), ('', 'nombre', ''), ('', 'rol', 'PROPIO | COMPETIDOR'), ('', 'hosts_json', '')]),
    ('seo_pagina', 10, 170, [('PK', 'id_seo_pagina', ''), ('FK', 'id_seo_sitio', ''), ('UQ', 'url', ''), ('', 'estado', ''), ('', 'lastmod', ''), ('', 'temas_json', '')]),
    ('seo_gsc', 10, 330, [('PK', 'id_seo_gsc', ''), ('', 'consulta', ''), ('REF', 'url', '→ seo_pagina'), ('', 'clics / impresiones', ''), ('', 'ctr / posicion', '')]),
    ('seo_tarea', 255, 26, [('PK', 'id_seo_tarea', ''), ('UQ', 'cod_seo_tarea', ''), ('', 'tipo', 'INVENTARIO | TEMAS …'), ('REF', 'cod_seo_sitio', '→ seo_sitio'), ('', 'estado', ''), ('', 'resumen_json', '')]),
    ('seo_mejora', 290, 250, [('PK', 'id_seo_mejora', ''), ('UQ', 'url', '→ seo_pagina'), ('', 'consultas_json', ''), ('', 'titulo / meta', 'propuestos'), ('', 'ideas_json', 'dice / debe decir'), ('', 'estado', '')]),
    ('seo_keyword', 540, 26, [('PK', 'id_seo_keyword', ''), ('UQ', 'clave', ''), ('', 'keyword', ''), ('', 'grupo', ''), ('', 'cobertura', ''), ('REF', 'cod_seo_tarea', '→ seo_tarea')]),
    ('seo_articulo', 540, 210, [('PK', 'id_seo_articulo', ''), ('UQ', 'cod_seo_articulo', ''), ('UQ', 'grupo', '→ seo_keyword'), ('', 'titulo / slug', ''), ('', 'contenido', ''), ('REF', 'cod_seo_tarea', '→ seo_tarea'), ('', 'wp_id / wp_estado', 'WordPress')]),
    ('seo_imagen', 800, 210, [('PK', 'id_seo_imagen', ''), ('UQ', 'cod_seo_articulo', '→ articulo'), ('', 'fuente', 'PIXABAY | IA …'), ('', 'datos', 'imagen'), ('', 'wp_media_id', '')]),
], [('seo_sitio', 'seo_pagina', '1', 'N', False), ('seo_sitio', 'seo_tarea', '1', 'N', True), ('seo_pagina', 'seo_gsc', '1', 'N', True),
    ('seo_pagina', 'seo_mejora', '1', '0..1', True), ('seo_tarea', 'seo_keyword', '1', 'N', True), ('seo_keyword', 'seo_articulo', 'N', '1', True),
    ('seo_articulo', 'seo_imagen', '1', '0..1', True)])

ANCHO_E, CAB_E, FILA_E = 215, 20, 13.5


def svg_grupo(grupo):
    titulo, w, h, entidades, rels = grupo
    pos = {}
    partes = []
    for nombre, x, y, campos in entidades:
        alto = CAB_E + FILA_E * len(campos) + 6
        pos[nombre] = (x, y, ANCHO_E, alto)
        partes.append(f'<rect x="{x}" y="{y}" width="{ANCHO_E}" height="{alto}" rx="5" fill="#fff" stroke="#9fb3c2"/>')
        partes.append(f'<path d="M{x} {y + CAB_E} V{y + 5} Q{x} {y} {x + 5} {y} H{x + ANCHO_E - 5} Q{x + ANCHO_E} {y} {x + ANCHO_E} {y + 5} V{y + CAB_E} Z" fill="#12324a"/>')
        partes.append(f'<text x="{x + 8}" y="{y + 14}" font-size="10.5" font-weight="700" fill="#fff">{e(nombre)}</text>')
        for i, (marca, campo, nota) in enumerate(campos):
            cy = y + CAB_E + 11 + i * FILA_E
            colores = {'PK': ('#12324a', '#fff'), 'FK': ('#0e7c86', '#fff'), 'REF': ('#e3f3f4', '#0e7c86'), 'UQ': ('#eef1f4', '#4a5866')}
            if marca:
                fondo, tinta = colores[marca]
                partes.append(f'<rect x="{x + 6}" y="{cy - 8.5}" width="24" height="11" rx="2.5" fill="{fondo}"/>'
                              f'<text x="{x + 18}" y="{cy}" font-size="7" font-weight="700" fill="{tinta}" text-anchor="middle">{marca}</text>')
            partes.append(f'<text x="{x + 35}" y="{cy}" font-size="9" fill="#14212b">{e(campo)}</text>')
            if nota:
                partes.append(f'<text x="{x + ANCHO_E - 6}" y="{cy}" font-size="7.6" fill="#7a8794" text-anchor="end">{e(nota)}</text>')
    lineas = []
    for a, b, ca, cb, logica in rels:
        ax, ay, aw, ah = pos[a]
        bx, by, bw, bh = pos[b]
        estilo = 'stroke-dasharray="4 3"' if logica else ''
        if bx >= ax + aw - 1 or ax >= bx + bw - 1:   # en columnas distintas: de lado a lado
            if bx > ax:
                x1, x2 = ax + aw, bx
            else:
                x1, x2 = ax, bx + bw
            y1 = ay + min(ah / 2, 34)
            y2 = by + min(bh / 2, 34)
            xm = (x1 + x2) / 2
            d = f'M{x1} {y1} H{xm} V{y2} H{x2}'
            et1 = (x1 + (6 if x2 > x1 else -6), y1 - 3, 'start' if x2 > x1 else 'end')
            et2 = (x2 + (-6 if x2 > x1 else 6), y2 - 3, 'end' if x2 > x1 else 'start')
        else:   # misma columna: de abajo hacia arriba
            if by > ay:
                y1, y2 = ay + ah, by
            else:
                y1, y2 = ay, by + bh
            x1 = x2 = max(ax, bx) + 40
            d = f'M{x1} {y1} V{y2}'
            et1 = (x1 + 5, y1 + (11 if y2 > y1 else -4), 'start')
            et2 = (x2 + 5, y2 + (-4 if y2 > y1 else 11), 'start')
        lineas.append(f'<path d="{d}" fill="none" stroke="#0e7c86" stroke-width="1.4" {estilo}/>')
        for (tx, ty, anc), txt in ((et1, ca), (et2, cb)):
            lineas.append(f'<text x="{tx}" y="{ty}" font-size="8.5" font-weight="700" fill="#0e7c86" text-anchor="{anc}">{e(txt)}</text>')
    w = max(x + aw for x, y, aw, ah in pos.values()) + 12
    h = max(y + ah for x, y, aw, ah in pos.values()) + 10
    svg = f'<svg class="er-svg" viewBox="0 0 {w} {h}" width="100%">{"".join(lineas)}{"".join(partes)}</svg>'
    return f'<div class="grupo-er"><h4>{e(titulo)}</h4>{svg}</div>'


def leyenda_er():
    return ('<div class="leyenda-er"><span><span class="k k-pk">PK</span> clave primaria</span>'
            '<span><span class="k k-fk">FK</span> clave foránea física</span><span><span class="k k-ref">REF</span> referencia lógica por código</span>'
            '<span><span class="k k-uq">UQ</span> valor único</span><span>── relación física · - - - relación lógica · 1, N, 0..1 cardinalidad</span></div>')


def diccionario():
    c = sqlite3.connect(f'file:{BD}?mode=ro', uri=True)
    tablas = [r[0] for r in c.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name")]
    bloques = []
    for t in tablas:
        fks = {r[3]: f'{r[2]}.{r[4]}' for r in c.execute(f'pragma foreign_key_list("{t}")')}
        unicos = set()
        for idx in c.execute(f'pragma index_list("{t}")'):
            if idx[2]:
                cols = [r[2] for r in c.execute(f'pragma index_info("{idx[1]}")')]
                if len(cols) == 1:
                    unicos.add(cols[0])
        filas = []
        for cid, nombre, tipo, notnull, defecto, pk in c.execute(f'pragma table_info("{t}")'):
            k = []
            if pk:
                k.append('<span class="k k-pk">PK</span>')
            if nombre in fks:
                k.append(f'<span class="k k-fk">FK</span> {e(fks[nombre])}')
            if nombre in unicos:
                k.append('<span class="k k-uq">UQ</span>')
            r = ('NOT NULL' if notnull else '') + (f' · def. {e(str(defecto))}' if defecto is not None else '')
            filas.append(f'<tr><td>{e(nombre)}</td><td>{e(tipo)}</td><td>{" ".join(k)}</td><td class="tenue">{r}</td></tr>')
        bloques.append(f'<div class="tabla-er"><b>{e(t)}</b><div class="desc">{e(DESCRIPCION.get(t, ""))}</div>'
                       f'<table><thead><tr><th>Campo</th><th>Tipo</th><th>Clave</th><th>Restricción</th></tr></thead><tbody>{"".join(filas)}</tbody></table></div>')
    return len(tablas), ''.join(bloques)


RELACIONES = [
    ('usuario', 'sesion', '1 : N', 'Física (FK id_usuario)'), ('usuario', 'auditoria', '1 : N', 'Lógica (actor)'),
    ('usuario', '10 tablas', '1 : N', 'Lógica (cod_autor / cod_aprobador)'), ('analisis', 'informe', '1 : 1', 'Lógica (cod_informe / cod_analisis)'),
    ('analisis', 'consumo_ia', '1 : N', 'Lógica (cod_analisis)'), ('informe', 'miniatura_anuncio', '1 : N', 'Lógica (ad_id en datos_json)'),
    ('kw_lista', 'kw_lista_item', '1 : N', 'Física (FK id_kw_lista)'), ('seo_sitio', 'seo_pagina', '1 : N', 'Física (FK id_seo_sitio)'),
    ('seo_sitio', 'seo_tarea', '1 : N', 'Lógica (cod_seo_sitio)'), ('seo_tarea', 'seo_keyword', '1 : N', 'Lógica (cod_seo_tarea)'),
    ('seo_tarea', 'seo_articulo', '1 : N', 'Lógica (cod_seo_tarea)'), ('seo_keyword', 'seo_articulo', 'N : 1', 'Lógica (grupo)'),
    ('seo_articulo', 'seo_imagen', '1 : 0..1', 'Lógica (cod_seo_articulo, único)'), ('seo_pagina', 'seo_mejora', '1 : 0..1', 'Lógica (url, único)'),
    ('seo_pagina', 'seo_gsc', '1 : N', 'Lógica (url)'), ('seo_tarea', 'informe_guardado', '1 : N', 'Lógica (cod_origen)'),
    ('video', 'publicacion', '1 : N', 'Lógica (cod_origen, origen VIDEO)'), ('publicacion', 'publicacion_evento', '1 : N', 'Lógica (cod_publicacion)'),
]


def anexo_er(prefijo='Anexo A · '):
    n, dicc = diccionario()
    grupos = ''.join(svg_grupo(g) for g in GRUPOS_ER[:4])
    rel = tabla(['Entidad', 'Relacionada con', 'Cardinalidad', 'Tipo'], [[f'<b>{a}</b>', b, c, d] for a, b, c, d in RELACIONES], ['22%', '22%', '14%', '42%'])
    return f"""
<section class="salto horizontal">
<h2>{prefijo}Modelo entidad-relación (1/3)</h2>
<p class="chico" style="margin-bottom:4pt">Base de datos SQLite del Radar: <b>{n} tablas</b>. Las relaciones físicas tienen clave foránea en la base; las lógicas se
resuelven por código (p. ej. <i>cod_seo_tarea</i>). <b>usuario</b> se relaciona además con 10 tablas por <i>cod_autor</i> /
<i>cod_aprobador</i> (no se dibujan para no saturar el diagrama). Se muestran los campos clave; el detalle completo está en el diccionario.</p>
{leyenda_er()}
<div class="rejilla-er">{grupos}</div>
</section>
<section class="salto horizontal">
<h2>{prefijo}Modelo entidad-relación (2/3): Plan SEO</h2>
{svg_grupo(GRUPO_SEO)}
{leyenda_er()}
</section>
<section class="salto horizontal">
<h2>{prefijo}Modelo entidad-relación (3/3): Medición y relaciones</h2>
<div class="rejilla-er"><div>{svg_grupo(GRUPOS_ER[4])}{leyenda_er()}</div><div>{rel}</div></div>
</section>
<section class="salto">
<h2>{prefijo}Diccionario de datos</h2>
<div class="dicc">{dicc}</div>
</section>"""


FUENTES = [
    ('Precios de la API de Gemini (incluye uso de datos en plan gratuito y retiro de modelos)', 'https://aistudio.google.com/docs/pricing'),
    ('DataForSEO – Keyword Planner API', 'https://dataforseo.com/keyword-planner-api'),
    ('DataForSEO – precios Google Ads', 'https://dataforseo.com/pricing/keywords-data/google-ads'),
    ('Apify – precios 2026 (comparador)', 'https://automationatlas.io/answers/apify-pricing-explained-2026/'),
    ('n8n – precios 2026', 'https://sliplane.io/blog/n8n-pricing'),
    ('Azure B2s – precio por hora (Linux)', 'https://www.azurespeed.com/AzureVmPricing/Standard_B2s'),
    ('Azure Blob Storage – precios 2026', 'https://www.eon.io/blog/azure-blob-storage-pricing'),
    ('SerpApi – precios', 'https://serpapi.com/pricing'),
    ('Google Vids – clips de Veo gratis y planes', 'https://winbuzzer.com/2026/04/03/google-vids-adds-free-ai-video-music-and-avatars-xcxwbn/'),
    ('Planes Google AI (Veo)', 'https://aitoolsatlas.ai/tools/veo-3-1/pricing'),
    ('Ahrefs vs Semrush – precios 2026', 'https://omidsaffari.com/blog/ahrefs-vs-semrush-verified-july-2026'),
    ('Meta – Instagram Platform (permisos y revisión)', 'https://developers.facebook.com/documentation/instagram-platform/overview'),
    ('LinkedIn – revisión de Community Management API', 'https://learn.microsoft.com/en-us/linkedin/marketing/community-management-app-review'),
    ('Política de datos de usuario de las API de Google', 'https://developers.google.com/terms/api-services-user-data-policy'),
]


def anexo_fuentes():
    return ('<section class="salto"><h2>Anexo B · Fuentes de precios y requisitos</h2><p class="chico">Consultadas el 6/11/2026.</p>'
            + tabla(['Fuente', 'Enlace'], [[e(t), f'<a href="{u}">{e(u)}</a>'] for t, u in FUENTES], ['45%', '55%']) + '</section>')


def documento(titulo, cuerpo):
    return f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{e(titulo)}</title><style>{CSS}</style></head><body>{cuerpo}</body></html>'


def portada_er():
    return f"""<section class="portada">{RADAR_SVG}<div class="franja"></div>
<div class="contenido"><div class="marca">Le Cordon Bleu Perú · Marketing</div><h1>Radar de Marketing</h1>
<div class="sub">Modelo entidad-relación y diccionario de datos de la base del Radar.</div></div>
<div class="pie"><b>Preparado por:</b> Alexander Pedemonte<br><b>Fecha:</b> {FECHA}</div></section>"""


def imprimir(html_txt, nombre_html, pdf):
    ruta = os.path.join(AQUI, nombre_html)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(html_txt)
    os.makedirs(os.path.dirname(pdf), exist_ok=True)
    r = subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--no-pdf-header-footer', f'--print-to-pdf={pdf}',
                        'file:///' + ruta.replace('\\', '/')], capture_output=True, text=True, timeout=180)
    print(nombre_html, '->', pdf, os.path.getsize(pdf) if os.path.exists(pdf) else 'NO GENERADO', r.stderr[-300:] if r.returncode else '')


if __name__ == '__main__':
    informe = documento('Radar · Informe para gerencia', portada() + resumen() + arquitectura() + modulos() + accesos()
                        + herramientas() + hoja_ruta() + anexo_er() + anexo_fuentes())
    imprimir(informe, 'informe.html', SALIDA_INFORME)
    er = documento('Radar · Modelo entidad-relación', portada_er() + anexo_er(prefijo='')).replace(
        'Radar · Informe de estado y propuesta · 6 nov 2026', 'Radar · Modelo entidad-relación · 6 nov 2026')
    imprimir(er, 'modelo_er.html', SALIDA_ER)
