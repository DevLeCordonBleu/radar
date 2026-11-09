# -*- coding: utf-8 -*-
"""
Worker de Radar.

Hace el trabajo sin estado del analisis: buscar anuncios en Apify, clasificarlos
con Gemini, agrupar etiquetas en territorios y calcular el informe. El orden de
los pasos, el avance y la pausa/reanudacion viven en el backend.

    uvicorn app.main:app --port 8102

Lo consume unicamente el backend; no se expone al navegador.
"""
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.compartido import envfile

envfile.load(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from app.api import rutas  # noqa: E402
from app.apify.normalizar import FormatoInesperado  # noqa: E402
from app.compartido.errores import CuotaAgotada, ErrorExterno  # noqa: E402
from app.ia.clasificar import LoteDemasiadoGrande  # noqa: E402

app = FastAPI(title="Radar - Worker", version="0.1.0")


@app.exception_handler(CuotaAgotada)
async def cuota(_: Request, exc: CuotaAgotada):
    # 429 aparte: el backend pausa el analisis en vez de darlo por fallado.
    return JSONResponse(status_code=429, content={"detail": str(exc)})


@app.exception_handler(LoteDemasiadoGrande)
async def grande(_: Request, exc: LoteDemasiadoGrande):
    return JSONResponse(status_code=413, content={"detail": str(exc)})


@app.exception_handler(ErrorExterno)
@app.exception_handler(FormatoInesperado)
async def error_conocido(_: Request, exc: Exception):
    # 422: la peticion era valida pero el paso no pudo completarse. El mensaje
    # esta pensado para mostrarse tal cual en el panel.
    return JSONResponse(status_code=422, content={"detail": str(exc)})


app.include_router(rutas.router)
