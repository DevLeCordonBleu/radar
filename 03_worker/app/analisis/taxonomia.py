# -*- coding: utf-8 -*-
"""
Listas cerradas con las que se clasifica cada anuncio, y los pesos de los
niveles de competidor. Son la unica fuente: el prompt, el esquema de Gemini y
el informe las leen de aqui, y el panel recibe las etiquetas ya traducidas.
"""

HOOKS = {
    "pregunta_directa": "Pregunta directa al espectador",
    "beneficio_directo": "Afirmación de beneficio",
    "problema_cliente": "Parte del problema del cliente",
    "disponibilidad": "Anuncia disponibilidad o apertura",
    "urgencia": "Urgencia o escasez",
    "prueba_social": "Cifras, cantidad de clientes, reconocimiento",
    "testimonio": "Alguien cuenta su experiencia",
    "dato": "Dato o cifra concreta",
    "antes_despues": "Contraste antes / después",
    "historia": "Empieza contando una historia o anécdota",
    "persona_camara": "Persona hablando directamente a cámara",
    "demostracion": "Demostración del servicio o producto en uso",
    "otro": "Otra estructura",
}

OFERTAS = {
    "prueba_gratuita": "Prueba o sesión de prueba gratuita",
    "primera_gratis": "Primera unidad, clase o sesión gratis",
    "disponibilidad_abierta": "Inscripción, matrícula o reservas abiertas",
    "reserva": "Reserva de plaza o cita",
    "descuento": "Descuento o promoción sobre precio",
    "pack_intensivo": "Pack, bono o intensivo",
    "producto_curso": "Producto, curso o programa concreto",
    "recurso_gratuito": "Contenido gratis: guía, webinar, evento o descarga",
    "sin_oferta": "Sin oferta explícita",
}

CTAS = {
    "reservar": "Reservar",
    "probar": "Probar",
    "mas_info": "Más información",
    "inscribirse": "Inscribirse",
    "contactar": "Escribir o contactar",
    "comprar": "Comprar",
    "descargar": "Descargar",
    "otro": "Otro",
}

FORMATOS = {"video": "Vídeo", "estatica": "Imagen estática", "carrusel": "Carrusel"}

PATRONES_VISUALES = {
    "persona_camara": "Una persona hablando a cámara",
    "grupo_personas": "Grupo de personas",
    "servicio_en_uso": "El producto o servicio en uso",
    "instalaciones": "Instalaciones o local",
    "resultado_final": "El resultado final logrado",
    "texto_sobre_imagen": "Texto grande sobre la imagen",
    "ugc": "Aspecto casero / UGC",
    "produccion_profesional": "Producción profesional",
    "vertical": "Formato vertical",
    "montaje_momentos": "Montaje de varios momentos",
    "grafico_dato": "Gráfico o dato en pantalla",
}

TIPOS_TERRITORIO = ("funcional", "emocional", "valores")

# Cuanto pesa un anunciante segun lo cerca que compite contigo.
NIVELES = {
    1: {"nombre": "Directo", "desc": "Compite por el mismo cliente en la misma zona", "peso": 2.0},
    2: {"nombre": "Proximidad", "desc": "Zona cercana con oferta comparable", "peso": 1.5},
    3: {"nombre": "Categoría", "desc": "Mismo tipo de producto en la región", "peso": 1.0},
    4: {"nombre": "Nacional", "desc": "Mismo tipo de producto en todo el país", "peso": 0.75},
}

# (clave, porcentaje minimo) de mayor a menor.
FRECUENCIAS = (("muy_alta", 40), ("alta", 25), ("media", 10), ("baja", 3), ("hueco", 0))

# Por debajo de esta muestra los porcentajes son solo orientativos.
MUESTRA_MINIMA = 30
# Un anuncio activo desde hace tantos dias se considera "veterano".
DIAS_VETERANO = 90
