"""
lector_xml.py
-------------
Lee una factura electrónica (CFDI 4.0) en formato XML y saca sus datos
principales, para que nadie tenga que teclearlos.

Uso desde otro archivo (así lo usarán la app y las pruebas):
    from lector_xml import leer_factura, FacturaInvalida
    datos = leer_factura(contenido)   # contenido = texto o bytes del XML

Uso desde la terminal, para ver qué lee:
    python lector_xml.py                                 -> lee las 10 facturas de prueba
    python lector_xml.py facturas_prueba/factura_03.xml  -> lee solo esa
"""

import math
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------
# 1. Constantes
# ---------------------------------------------------------------

# Los "namespaces" (espacios de nombres) son como el apellido de las etiquetas.
# En el XML se ven como cfdi:Emisor o tfd:TimbreFiscalDigital, pero por dentro
# cada prefijo (cfdi, tfd) corresponde a una dirección. ElementTree necesita
# este diccionario para saber qué dirección va con cada prefijo.
NS = {
    "cfdi": "http://www.sat.gob.mx/cfd/4",
    "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
}

# Así ve ElementTree la etiqueta principal de una factura CFDI 4.0:
# la dirección del namespace entre llaves y luego el nombre.
ETIQUETA_COMPROBANTE = "{http://www.sat.gob.mx/cfd/4}Comprobante"

# Mensaje exacto que pide el criterio de aceptación.
MENSAJE_INVALIDA = "El archivo no es una factura XML válida"


# ---------------------------------------------------------------
# 2. Error propio
# ---------------------------------------------------------------

class FacturaInvalida(Exception):
    """Error que lanzamos cuando el archivo no es una factura CFDI 4.0 válida.

    - str(error)    -> el mensaje para el usuario (siempre el mismo)
    - error.detalle -> la razón técnica (te sirve a ti para encontrar fallas)

    Hereda de Exception, así que se puede atrapar con try / except.
    """

    def __init__(self, detalle=""):
        super().__init__(MENSAJE_INVALIDA)
        self.detalle = detalle


# ---------------------------------------------------------------
# 3. Funciones
# ---------------------------------------------------------------

def _atributo(elemento, nombre):
    """Regresa el valor de un atributo obligatorio, o lanza FacturaInvalida si falta.

    Ejemplo: en <cfdi:Emisor Rfc="PAP010101AB1" .../>, _atributo(emisor, "Rfc")
    regresa "PAP010101AB1".
    El guion bajo al inicio del nombre indica que es una función "interna",
    pensada para usarse solo dentro de este archivo.
    """
    valor = elemento.get(nombre, "").strip()
    if not valor:
        etiqueta = elemento.tag.split("}")[-1]  # "{http://...}Emisor" -> "Emisor"
        raise FacturaInvalida(f"Falta el dato {nombre} en {etiqueta}")
    return valor


def leer_factura(contenido_xml):
    """Lee el XML de una factura y regresa un diccionario con sus datos.

    Recibe el contenido del archivo, ya sea como texto (str) o como bytes
    (así lo entrega Streamlit cuando subes un archivo).

    Regresa, por ejemplo:
        {"uuid": "00000000-0000-4000-8000-000000000001",
         "rfc_emisor": "PAP010101AB1",
         "nombre_emisor": "PAPELERIA EJEMPLO SA DE CV",
         "rfc_receptor": "TEC000101AA1",
         "nombre_receptor": "INSTITUTO TECNOLOGICO DE PRUEBA",
         "total": 1450.0,
         "fecha": "2026-11-03T10:15:00"}

    Si el archivo no es una factura válida, lanza FacturaInvalida.
    """
    # Paso 1: convertir el texto en un "árbol" de etiquetas.
    # Algunos programas ponen al inicio un carácter invisible (BOM); lo quitamos.
    if isinstance(contenido_xml, str):
        contenido_xml = contenido_xml.lstrip("﻿")
    try:
        raiz = ET.fromstring(contenido_xml)
    except ET.ParseError as error:
        # Pasa con archivos vacíos, cortados, PDF o texto normal.
        raise FacturaInvalida(f"No es un XML bien formado: {error}") from error

    # Paso 2: revisar que la etiqueta principal sea la de una factura CFDI 4.0.
    if raiz.tag != ETIQUETA_COMPROBANTE:
        raise FacturaInvalida("La etiqueta principal no es cfdi:Comprobante de CFDI 4.0")

    # Paso 3: buscar las partes que necesitamos.
    # find() regresa None si no encuentra la etiqueta.
    emisor = raiz.find("cfdi:Emisor", NS)
    receptor = raiz.find("cfdi:Receptor", NS)
    timbre = raiz.find("cfdi:Complemento/tfd:TimbreFiscalDigital", NS)
    if emisor is None:
        raise FacturaInvalida("Falta el Emisor")
    if receptor is None:
        raise FacturaInvalida("Falta el Receptor")
    if timbre is None:
        raise FacturaInvalida("Falta el TimbreFiscalDigital (la factura no está timbrada)")

    # Paso 4: convertir el total a número y revisar que tenga sentido.
    try:
        total = float(_atributo(raiz, "Total"))
    except ValueError as error:
        raise FacturaInvalida("El Total no es un número") from error
    if not math.isfinite(total) or total < 0:  # descarta "inf", "nan" y negativos
        raise FacturaInvalida("El Total no es un importe válido")

    # Paso 5: revisar que la fecha tenga el formato correcto (2026-11-03T10:15:00).
    fecha = _atributo(raiz, "Fecha")
    try:
        datetime.fromisoformat(fecha)
    except ValueError as error:
        raise FacturaInvalida("La Fecha no tiene un formato válido") from error

    # Datos extra (no obligatorios) que se usan para dibujar la factura en imagen.
    concepto = raiz.find("cfdi:Conceptos/cfdi:Concepto", NS)
    descripcion = ""
    if concepto is not None:
        descripcion = concepto.get("Descripcion", "").strip()
    try:
        subtotal = float(raiz.get("SubTotal", total))
    except ValueError:
        subtotal = total

    # Paso 6: armar el diccionario. .upper() pasa los RFC y el UUID a mayúsculas
    # para que siempre se comparen igual.
    return {
        "uuid": _atributo(timbre, "UUID").upper(),
        "rfc_emisor": _atributo(emisor, "Rfc").upper(),
        "nombre_emisor": _atributo(emisor, "Nombre"),
        "rfc_receptor": _atributo(receptor, "Rfc").upper(),
        "nombre_receptor": receptor.get("Nombre", "").strip(),  # opcional
        "total": total,
        "fecha": fecha,
        "subtotal": subtotal,
        "descripcion": descripcion,
    }


# ---------------------------------------------------------------
# 4. Prueba rápida desde la terminal
# ---------------------------------------------------------------

def _mostrar(ruta):
    """Lee un archivo y escribe en la terminal lo que encontró."""
    if not ruta.exists():
        print(f"{ruta}: no existe ese archivo")
        return
    try:
        datos = leer_factura(ruta.read_bytes())
    except FacturaInvalida as error:
        print(f"{ruta.name}: {error}  (motivo: {error.detalle})")
        return
    fecha = datetime.fromisoformat(datos["fecha"]).strftime("%d/%m/%Y")
    print(f"{ruta.name}: folio ...{datos['uuid'][-4:]} | "
          f"{datos['nombre_emisor']} ({datos['rfc_emisor']}) | "
          f"receptor {datos['rfc_receptor']} | ${datos['total']:,.2f} | {fecha}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Se escribieron archivos después del comando: leer esos.
        rutas = [Path(texto) for texto in sys.argv[1:]]
    else:
        # No se escribió nada: leer todas las facturas de prueba.
        rutas = sorted((Path(__file__).parent / "facturas_prueba").glob("*.xml"))
    for ruta in rutas:
        _mostrar(ruta)
