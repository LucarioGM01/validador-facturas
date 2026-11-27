"""
lector_imagen.py
----------------
Lee una factura que llega como IMAGEN (foto del celular, captura o PNG) y saca
sus datos: folio fiscal, RFC, nombres y total.

Usa dos "ojos" y compara lo que ve cada uno:
  1. El CÓDIGO QR de la factura (librería OpenCV). Es exacto y no necesita
     internet: trae el folio, los dos RFC y el total.
  2. La inteligencia artificial GEMINI de Google, que "ve" la imagen y lee los
     caracteres impresos (también los nombres, la fecha y el concepto).

Si los dos coinciden, la lectura es confiable. Si la foto no deja ver el QR,
se usa solo lo que leyó Gemini; si no hay internet, solo el QR.

Regresa un diccionario con las mismas claves que lector_xml.leer_factura(),
así validador.py lo valida igual que un XML.

Prueba desde la terminal:
    python lector_imagen.py                                 -> lee las 11 imágenes de prueba
    python lector_imagen.py facturas_prueba/factura_03.png  -> lee solo esa
"""

import base64
import json
import re
import sys
import tomllib
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import cv2
import numpy
import requests

from lector_xml import FacturaInvalida

# ---------------------------------------------------------------
# 1. Constantes
# ---------------------------------------------------------------

CARPETA = Path(__file__).parent
RUTA_SECRETOS = CARPETA / ".streamlit" / "secrets.toml"

# Modelos de Gemini que se prueban EN ORDEN. A veces Google responde que un
# modelo está saturado; entonces se intenta con el siguiente.
MODELOS_GEMINI = [
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-3.5-flash-lite",
    "gemini-4-hydrogen",
]
URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"

# Instrucciones que se le dan a Gemini junto con la imagen.
INSTRUCCIONES = (
    "Eres un lector de facturas mexicanas (CFDI). Lee la imagen y responde SOLO "
    "un objeto JSON con estas claves: uuid (folio fiscal), rfc_emisor, nombre_emisor, "
    "rfc_receptor, nombre_receptor, total (número), subtotal (número), "
    "fecha (formato AAAA-MM-DDTHH:MM:SS) y descripcion (el concepto). "
    "Copia los caracteres exactamente como aparecen. Si un dato no se ve, pon \"\"."
)

# Formas que deben tener un folio fiscal y un RFC (expresiones regulares).
FORMA_UUID = r"[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}"
FORMA_RFC = r"[A-ZÑ&]{3,4}[0-9]{6}[A-Z0-9]{3}"


# ---------------------------------------------------------------
# 2. Ayudantes
# ---------------------------------------------------------------

def tipo_de_imagen(contenido):
    """Dice si los bytes son PNG o JPG mirando sus primeros bytes."""
    if contenido.startswith(b"\x89PNG"):
        return "image/png"
    if contenido.startswith(b"\xff\xd8"):
        return "image/jpeg"
    return ""


def a_numero(texto):
    """'$3,480.00' -> 3480.0. Regresa None si no es un número."""
    try:
        return float(str(texto).replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


def leer_clave_gemini():
    """Lee GEMINI_API_KEY de .streamlit/secrets.toml (o "" si no hay)."""
    if not RUTA_SECRETOS.exists():
        return ""
    with open(RUTA_SECRETOS, "rb") as archivo:
        return str(tomllib.load(archivo).get("GEMINI_API_KEY", "")).strip()


# ---------------------------------------------------------------
# 3. Ojo 1: el código QR
# ---------------------------------------------------------------

def leer_qr(contenido):
    """Busca el código QR en la imagen y regresa sus datos, o None si no lo encuentra.

    El QR de una factura trae una dirección como:
    https://verificacfdi...?id=FOLIO&re=RFC_EMISOR&rr=RFC_RECEPTOR&tt=TOTAL
    """
    if not contenido or not tipo_de_imagen(contenido):
        return None  # vacío o no es PNG/JPG
    # Convertir los bytes en una imagen que OpenCV entienda.
    arreglo = numpy.frombuffer(contenido, dtype=numpy.uint8)
    imagen = cv2.imdecode(arreglo, cv2.IMREAD_COLOR)
    if imagen is None:
        return None  # no es una imagen

    texto, _, _ = cv2.QRCodeDetector().detectAndDecode(imagen)
    if not texto:
        return None  # no se encontró un QR (o no se pudo leer)

    # parse_qs separa la parte después del "?" en un diccionario.
    partes = parse_qs(urlparse(texto).query)
    if "id" not in partes:
        return None  # es un QR, pero no de una factura
    return {
        "uuid": partes["id"][0].strip().upper(),
        "rfc_emisor": partes.get("re", [""])[0].strip().upper(),
        "rfc_receptor": partes.get("rr", [""])[0].strip().upper(),
        "total": a_numero(partes.get("tt", ["0"])[0]) or 0.0,
    }


# ---------------------------------------------------------------
# 4. Ojo 2: la inteligencia artificial Gemini
# ---------------------------------------------------------------

def leer_con_gemini(contenido, clave):
    """Le manda la imagen a Gemini y regresa (datos, motivo).

    - datos:  diccionario con lo que leyó, o None si no se pudo
    - motivo: si falló, por qué (para explicarlo en pantalla)
    """
    if not clave:
        return None, "No hay GEMINI_API_KEY en secrets.toml."
    tipo = tipo_de_imagen(contenido)
    if not tipo:
        return None, "El archivo no es una imagen PNG o JPG."

    # Así se le manda una imagen a Gemini: convertida a texto base64.
    cuerpo = {
        "contents": [{"parts": [
            {"inline_data": {"mime_type": tipo, "data": base64.b64encode(contenido).decode()}},
            {"text": INSTRUCCIONES},
        ]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }

    motivo = "Gemini no respondió."
    for modelo in MODELOS_GEMINI:
        try:
            respuesta = requests.post(URL_GEMINI.format(modelo=modelo), json=cuerpo,
                                      headers={"x-goog-api-key": clave}, timeout=30)
        except requests.RequestException:
            return None, "No se pudo conectar con Gemini. Revisa tu conexión a internet."

        if respuesta.status_code in (400, 401, 403):
            return None, "Google no aceptó la clave. Revisa GEMINI_API_KEY en secrets.toml."
        if respuesta.status_code != 200:
            # 503 = saturado, 429 = límite gratis, 404 = modelo no disponible: probar otro.
            motivo = f"Gemini está ocupado (error {respuesta.status_code}). Intenta en un momento."
            continue

        try:
            partes = respuesta.json()["candidates"][0]["content"]["parts"]
            datos = json.loads(partes[-1]["text"])
        except (KeyError, IndexError, ValueError):
            motivo = "Gemini respondió algo que no se pudo entender."
            continue
        return datos, ""
    return None, motivo


# ---------------------------------------------------------------
# 5. Juntar las dos lecturas
# ---------------------------------------------------------------

# Nombres para mostrar de cada dato que se compara.
NOMBRES_DATOS = {
    "uuid": "folio fiscal",
    "rfc_emisor": "RFC del emisor",
    "rfc_receptor": "RFC del receptor",
    "total": "total",
}


def crear_aviso_lectura(fuente, detalle):
    """Texto de aviso cuando la lectura de la imagen NO es confiable, o "" si lo es.

    - fuente:  "QR + Gemini", "solo QR" o "solo Gemini"
    - detalle: lista de (dato, valor del QR, valor leído por la IA) que no coinciden

    Casos:
      * QR y Gemini no coinciden -> puede ser un error de la IA... o una factura
        impresa ALTERADA (el texto dice una cosa y el QR otra). Hay que revisarla.
      * Solo Gemini (no se pudo leer el QR) -> nada confirma lo que leyó la IA.
      * Solo QR, o QR y Gemini coinciden -> confiable: no hay aviso.
    """
    if fuente == "solo Gemini":
        return ("No se pudo leer el código QR: los datos los leyó solo la IA y nada los "
                "confirma. Compara el folio, los RFC y el total con la factura antes de pagar.")
    if not detalle:
        return ""

    partes = []
    for clave, valor_qr, valor_ia in detalle:
        if clave == "total":
            valor_qr, valor_ia = f"${valor_qr:,.2f}", f"${valor_ia:,.2f}"
        partes.append(f"{NOMBRES_DATOS[clave]} (QR: {valor_qr or 'vacío'}; "
                      f"impreso según la IA: {valor_ia or 'vacío'})")
    return ("El código QR y lo impreso en la factura NO coinciden en: " + "; ".join(partes)
            + ". Se usaron los datos del QR. Revisa la factura antes de pagar: puede ser "
              "un error de lectura o una factura alterada.")

def leer_factura_imagen(contenido, clave_gemini="", al_paso=None):
    """Lee la imagen de una factura y regresa sus datos.

    El diccionario trae las claves de leer_factura() y además:
      fuente      -> "QR + Gemini", "solo QR" o "solo Gemini"
      coinciden   -> True si el QR y Gemini leyeron lo mismo
      diferencias -> lista de los datos que no coincidieron
      aviso_lectura -> texto si hay que revisar la lectura a mano, o "" si es confiable
    al_paso (opcional): función que recibe un texto por cada paso, para verlo en vivo.
    Si no se pudo leer nada, lanza FacturaInvalida.
    """
    def avisar(texto):
        if al_paso is not None:
            al_paso(texto)

    avisar("⏳ Buscando el código QR en la imagen…")
    del_qr = leer_qr(contenido)
    if del_qr is None:
        avisar("✖ No se encontró un código QR legible")
    else:
        avisar(f"✔ QR leído: folio …{del_qr['uuid'][-4:]} · ${del_qr['total']:,.2f}")

    if clave_gemini:
        avisar("⏳ Leyendo el texto de la factura con la IA (Gemini)…")
    de_ia, motivo_ia = leer_con_gemini(contenido, clave_gemini)
    if clave_gemini:
        avisar("✔ La IA leyó la factura" if de_ia is not None else f"✖ La IA no pudo leerla: {motivo_ia}")

    if del_qr is None and de_ia is None:
        raise FacturaInvalida(f"No se encontró el código QR y la IA no pudo leerla. {motivo_ia}")

    # Empezamos con valores vacíos y los vamos llenando.
    datos = {
        "uuid": "", "rfc_emisor": "", "nombre_emisor": "(nombre no leído)",
        "rfc_receptor": "", "nombre_receptor": "", "total": 0.0, "fecha": "",
        "subtotal": 0.0, "descripcion": "",
    }

    if de_ia is not None:
        datos["uuid"] = str(de_ia.get("uuid", "")).strip().upper()
        datos["rfc_emisor"] = str(de_ia.get("rfc_emisor", "")).strip().upper()
        datos["rfc_receptor"] = str(de_ia.get("rfc_receptor", "")).strip().upper()
        datos["nombre_emisor"] = str(de_ia.get("nombre_emisor", "")).strip() or "(nombre no leído)"
        datos["nombre_receptor"] = str(de_ia.get("nombre_receptor", "")).strip()
        datos["descripcion"] = str(de_ia.get("descripcion", "")).strip()
        datos["total"] = a_numero(de_ia.get("total", "")) or 0.0
        datos["subtotal"] = a_numero(de_ia.get("subtotal", "")) or datos["total"]
        fecha = str(de_ia.get("fecha", "")).strip()
        try:
            datetime.fromisoformat(fecha)
            datos["fecha"] = fecha
        except ValueError:
            datos["fecha"] = ""  # la fecha no se leyó bien: se deja vacía

    # Comparar lo que leyó cada "ojo" (solo si los dos leyeron algo).
    # detalle guarda (dato, lo que dice el QR, lo que leyó la IA) para el aviso.
    diferencias = []
    detalle = []
    if del_qr is not None and de_ia is not None:
        for clave in ["uuid", "rfc_emisor", "rfc_receptor"]:
            if del_qr[clave] != datos[clave]:
                diferencias.append(clave)
                detalle.append((clave, del_qr[clave], datos[clave]))
        if abs(del_qr["total"] - datos["total"]) > 0.01:
            diferencias.append("total")
            detalle.append(("total", del_qr["total"], datos["total"]))

    # El QR manda en folio, RFC y total porque es exacto.
    if del_qr is not None:
        datos.update(del_qr)
        if not datos["subtotal"]:
            datos["subtotal"] = datos["total"]

    if del_qr is not None and de_ia is not None:
        datos["fuente"] = "QR + Gemini"
    elif del_qr is not None:
        datos["fuente"] = "solo QR"
    else:
        datos["fuente"] = "solo Gemini"
    datos["coinciden"] = (datos["fuente"] == "QR + Gemini" and not diferencias)
    datos["diferencias"] = diferencias
    datos["aviso_lectura"] = crear_aviso_lectura(datos["fuente"], detalle)
    if datos["fuente"] == "QR + Gemini":
        avisar("✔ El QR y la IA coinciden" if datos["coinciden"]
               else "⚠ El QR y la IA NO coinciden en: " + ", ".join(diferencias))

    # Revisar que el folio y los RFC tengan la forma correcta.
    if not re.fullmatch(FORMA_UUID, datos["uuid"]):
        raise FacturaInvalida("No se pudo leer un folio fiscal (UUID) válido en la imagen.")
    if not re.fullmatch(FORMA_RFC, datos["rfc_emisor"]) or not re.fullmatch(FORMA_RFC, datos["rfc_receptor"]):
        raise FacturaInvalida("No se pudieron leer bien los RFC en la imagen.")
    return datos


# ---------------------------------------------------------------
# 6. Prueba rápida desde la terminal
# ---------------------------------------------------------------

if __name__ == "__main__":
    clave = leer_clave_gemini()
    if len(sys.argv) > 1:
        rutas = [Path(texto) for texto in sys.argv[1:]]
    else:
        rutas = (sorted((CARPETA / "facturas_prueba").glob("*.png"))
                 + sorted((CARPETA / "facturas_reemplazo").glob("*.png")))
    if not clave:
        print("(No hay GEMINI_API_KEY: solo se leerá el código QR)\n")

    for ruta in rutas:
        try:
            datos = leer_factura_imagen(ruta.read_bytes(), clave)
        except FacturaInvalida as error:
            print(f"{ruta.name}: NO SE PUDO LEER ({error.detalle})")
            continue
        revision = "coinciden" if datos["coinciden"] else (
            "NO coinciden: " + ", ".join(datos["diferencias"]) if datos["diferencias"] else "")
        print(f"{ruta.name}: folio ...{datos['uuid'][-4:]} | {datos['nombre_emisor']} "
              f"({datos['rfc_emisor']}) -> {datos['rfc_receptor']} | ${datos['total']:,.2f} "
              f"| leído con {datos['fuente']} {revision}")
