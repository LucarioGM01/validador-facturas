"""
procesar_lote.py
----------------
Valida un GRUPO de facturas (XML o imágenes) de principio a fin:

  1. Lee cada archivo (lector_xml.py o lector_imagen.py) y lo valida (validador.py).
  2. Si alguna sale cancelada, avisa al jefe por Telegram (RN-02).
  3. Al terminar, manda el REGISTRO de la validación a Telegram: si todas
     salieron correctas o cuáles requieren atención.

No usa Streamlit, así que lo pueden usar las dos "puertas" del programa:
  - la página web (interfaz.py), y
  - el bot de Telegram (bot_telegram.py).
Así las dos validan exactamente igual.
"""

from pathlib import Path

import avisos
import base_datos
from generar_facturas import CARPETA_FACTURAS, generar_facturas
from lector_imagen import leer_factura_imagen
from lector_xml import FacturaInvalida
from validador import ARCHIVO_INVALIDO, avisar_paso, validar_factura

# Carpeta que vigila el bot: lo que caiga aquí se valida solo.
CARPETA_BANDEJA = Path(__file__).parent / "bandeja_entrada"

EXTENSIONES_IMAGEN = {".png", ".jpg", ".jpeg"}
EXTENSIONES_ACEPTADAS = EXTENSIONES_IMAGEN | {".xml"}


def resultado_imagen_invalida(nombre, error):
    """Resultado de una imagen que no se pudo leer (mismas claves que validar_factura)."""
    motivo = getattr(error, "detalle", "") or error  # FacturaInvalida trae el porqué en .detalle
    return {
        "archivo": nombre,
        "uuid": "", "rfc_emisor": "", "nombre_emisor": "",
        "rfc_receptor": "", "nombre_receptor": "", "total": 0.0, "fecha": "",
        "estado": ARCHIVO_INVALIDO,
        "fecha_cancelacion": "",
        "mensaje": f"No se pudo leer la imagen: {motivo}",
        "puede_pagarse": False,
        "avisar_jefe": False,
        "es_repetida": False,
        "segundos": 0.0,
        "id_validacion": None,
        "aviso_lectura": "",
    }


def validar_un_archivo(conexion, nombre, contenido, usuario, clave_gemini="", al_paso=None):
    """Valida un archivo: si es imagen la lee con QR/Gemini, si no, como XML.

    al_paso (opcional): función que recibe un texto por cada paso, para ver la
    validación en vivo (la usan seguimiento.py y el bot de Telegram).
    """
    if Path(nombre).suffix.lower() in EXTENSIONES_IMAGEN:
        try:
            datos_imagen = leer_factura_imagen(contenido, clave_gemini, al_paso)
        except FacturaInvalida as error:
            avisar_paso(al_paso, f"✖ No se pudo leer la imagen: {error.detalle or error}")
            return resultado_imagen_invalida(nombre, error)
        return validar_factura(conexion, contenido, usuario, nombre, datos=datos_imagen,
                               al_paso=al_paso)
    return validar_factura(conexion, contenido, usuario, nombre, al_paso=al_paso)


def validar_lote(conexion, archivos, usuario, clave_gemini="", token="", chat_id="",
                 origen="app web", botones=None, progreso=None):
    """Valida todos los archivos y manda los mensajes de Telegram.

    - archivos: [(nombre, contenido_en_bytes), ...]
    - token, chat_id: credenciales de Telegram. Si faltan, todo funciona igual
      y los mensajes simplemente no se mandan.
    - origen:  "app web" o "bot de Telegram" (se escribe en el registro)
    - botones: (opcional) teclado inline que va debajo del registro
    - progreso: (opcional) un seguimiento.Progreso: se le va avisando cada paso
      de cada factura para mostrarlo en vivo (Telegram y página web)

    Regresa (resultados, registro):
      resultados -> lista de diccionarios, uno por archivo
      registro   -> {"enviado": True/False, "detalle": "..."} del mensaje de registro
    """
    resultados = []
    for nombre, contenido in archivos:
        if progreso is not None:
            progreso.empezar_factura(nombre)
        al_paso = progreso.paso if progreso is not None else None
        resultado = validar_un_archivo(conexion, nombre, contenido, usuario, clave_gemini,
                                       al_paso)

        if resultado["avisar_jefe"]:  # RN-02: aviso inmediato de cada cancelada
            mensaje = avisos.crear_mensaje_cancelada(resultado, usuario, base_datos.ahora())
            resultado["aviso"] = avisos.enviar_telegram(mensaje, token, chat_id)
            if resultado["aviso"]["enviado"]:
                base_datos.marcar_aviso_enviado(conexion, resultado["uuid"])
        resultados.append(resultado)
        if progreso is not None:
            progreso.terminar_factura(resultado)

    if progreso is not None:
        progreso.terminar()
    registro = enviar_registro(resultados, usuario, token, chat_id, origen, botones)
    return resultados, registro


def enviar_registro(resultados, usuario, token, chat_id, origen="app web", botones=None):
    """Manda a Telegram el registro de una validación ya hecha."""
    mensaje = avisos.crear_mensaje_registro(resultados, usuario, base_datos.ahora(), origen)
    return avisos.enviar_telegram(mensaje, token, chat_id, botones)


def archivos_de_prueba():
    """Las 10 facturas inventadas como [(nombre, bytes), ...]. Si no existen
    (por ejemplo en la nube), las crea primero."""
    if not any(CARPETA_FACTURAS.glob("*.xml")):
        generar_facturas()
    return [(ruta.name, ruta.read_bytes()) for ruta in sorted(CARPETA_FACTURAS.glob("*.xml"))]


def dejar_facturas_de_prueba(carpeta=CARPETA_BANDEJA):
    """Copia las 10 facturas de prueba a la bandeja, como si los proveedores las
    hubieran mandado. Regresa cuántas dejó. El bot las detecta y las valida solo."""
    carpeta.mkdir(exist_ok=True)
    archivos = archivos_de_prueba()
    for nombre, contenido in archivos:
        (carpeta / nombre).write_bytes(contenido)
    return len(archivos)
