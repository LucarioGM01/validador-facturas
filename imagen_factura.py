"""
imagen_factura.py
-----------------
Dibuja la "representación impresa" de una factura: una imagen PNG parecida a
la factura en papel o en PDF que mandan los proveedores. Trae el folio fiscal,
los RFC, el total y un código QR con esos mismos datos.

Sirve para probar el bot de Telegram: se le manda la foto de la factura y el
programa la lee con el código QR y con la inteligencia artificial.

Todo se dibuja con Python (librerías Pillow y qrcode), sin HTML.
TODOS los datos son INVENTADOS.

Cómo usarlo (en la terminal, desde la carpeta del proyecto):
    python imagen_factura.py   -> crea la imagen de cada factura de prueba
"""

import textwrap
from datetime import datetime
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont

from lector_xml import leer_factura

# ---------------------------------------------------------------
# 1. Constantes
# ---------------------------------------------------------------

CARPETA = Path(__file__).parent
CARPETAS_CON_FACTURAS = [CARPETA / "facturas_prueba", CARPETA / "facturas_reemplazo"]

ANCHO = 1000   # pixeles
ALTO = 1300

# Colores en formato (rojo, verde, azul), cada uno de 0 a 255.
BLANCO = (255, 255, 255)
NEGRO = (30, 30, 30)
GRIS = (110, 110, 110)
GRIS_CLARO = (236, 236, 236)
ROJO = (190, 40, 30)
COBRE = (138, 84, 52)

# Las facturas reales traen un QR con la dirección de verificación del SAT y
# estos datos: id (folio fiscal), re (RFC emisor), rr (RFC receptor),
# tt (total) y fe (últimos 8 caracteres del sello digital).
URL_VERIFICACION = "https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx"


# ---------------------------------------------------------------
# 2. Funciones
# ---------------------------------------------------------------

def letra(tamano, negrita=False):
    """Tipo de letra del tamaño indicado.

    Busca Arial (viene en Windows) o DejaVu Sans (viene en Linux, como en
    Streamlit Cloud), que sí tienen acentos. Si no encuentra ninguna, usa la
    letra que trae Pillow (esa no tiene acentos).
    """
    if negrita:
        nombres = ["arialbd.ttf", "DejaVuSans-Bold.ttf"]
    else:
        nombres = ["arial.ttf", "DejaVuSans.ttf"]
    for nombre in nombres:
        try:
            return ImageFont.truetype(nombre, tamano)
        except OSError:  # esa letra no está instalada: probar la siguiente
            pass
    return ImageFont.load_default(size=tamano)


def dinero(cantidad):
    """1450.0 -> '$1,450.00'"""
    return f"${cantidad:,.2f}"


def texto_qr(datos):
    """Texto que va dentro del código QR, con el mismo formato que usa el SAT."""
    return (f"{URL_VERIFICACION}?id={datos['uuid']}&re={datos['rfc_emisor']}"
            f"&rr={datos['rfc_receptor']}&tt={datos['total']:.2f}&fe=PRUEBA00")


def dibujar_factura(datos):
    """Dibuja la factura y regresa la imagen (un objeto Image de Pillow).

    `datos` es el diccionario que regresa lector_xml.leer_factura().
    En una imagen, (x, y) es la posición: x crece hacia la derecha y y hacia abajo.
    """
    imagen = Image.new("RGB", (ANCHO, ALTO), BLANCO)
    dibujo = ImageDraw.Draw(imagen)

    # --- Encabezado gris ---
    dibujo.rectangle([0, 0, ANCHO, 150], fill=GRIS_CLARO)
    dibujo.text((40, 30), "FACTURA", font=letra(58, negrita=True), fill=NEGRO)
    dibujo.text((40, 102), "Representación impresa de un CFDI 4.0", font=letra(22), fill=GRIS)
    dibujo.text((960, 48), "DOCUMENTO DE PRUEBA", font=letra(30, negrita=True), fill=ROJO, anchor="ra")
    dibujo.text((960, 90), "Datos ficticios, sin validez fiscal", font=letra(22),
                fill=ROJO, anchor="ra")

    # --- Emisor (proveedor) y receptor ---
    dibujo.text((40, 190), "EMISOR (PROVEEDOR)", font=letra(20), fill=COBRE)
    dibujo.text((40, 218), datos["nombre_emisor"], font=letra(30), fill=NEGRO)
    dibujo.text((40, 258), f"RFC: {datos['rfc_emisor']}", font=letra(28), fill=NEGRO)

    dibujo.text((40, 320), "RECEPTOR (CLIENTE)", font=letra(20), fill=COBRE)
    dibujo.text((40, 348), datos["nombre_receptor"] or "—", font=letra(30), fill=NEGRO)
    dibujo.text((40, 388), f"RFC: {datos['rfc_receptor']}", font=letra(28), fill=NEGRO)

    # --- Folio fiscal (lo más importante para validar) ---
    dibujo.rectangle([30, 450, 970, 560], outline=COBRE, width=3)
    dibujo.text((50, 465), "FOLIO FISCAL (UUID)", font=letra(20), fill=COBRE)
    dibujo.text((50, 497), datos["uuid"], font=letra(38, negrita=True), fill=NEGRO)

    fecha = datetime.fromisoformat(datos["fecha"]).strftime("%d/%m/%Y %H:%M")
    dibujo.text((40, 585), f"Fecha de emisión: {fecha}", font=letra(24), fill=NEGRO)

    # --- Concepto ---
    dibujo.rectangle([30, 640, 970, 685], fill=GRIS_CLARO)
    dibujo.text((50, 650), "Concepto", font=letra(22), fill=NEGRO)
    dibujo.text((950, 650), "Importe", font=letra(22), fill=NEGRO, anchor="ra")
    y = 705
    # textwrap.wrap parte una descripción larga en renglones de 45 letras.
    for renglon in textwrap.wrap(datos["descripcion"] or "—", 45):
        dibujo.text((50, y), renglon, font=letra(24), fill=NEGRO)
        y += 34
    dibujo.text((950, 705), dinero(datos["subtotal"]), font=letra(24), fill=NEGRO, anchor="ra")

    # --- Totales ---
    iva = datos["total"] - datos["subtotal"]
    dibujo.text((700, 820), "Subtotal:", font=letra(24), fill=NEGRO, anchor="ra")
    dibujo.text((950, 820), dinero(datos["subtotal"]), font=letra(24), fill=NEGRO, anchor="ra")
    dibujo.text((700, 858), "IVA 16 %:", font=letra(24), fill=NEGRO, anchor="ra")
    dibujo.text((950, 858), dinero(iva), font=letra(24), fill=NEGRO, anchor="ra")
    dibujo.line([560, 900, 960, 900], fill=NEGRO, width=2)
    dibujo.text((700, 915), "TOTAL:", font=letra(34, negrita=True), fill=NEGRO, anchor="ra")
    dibujo.text((950, 915), dinero(datos["total"]), font=letra(34, negrita=True), fill=NEGRO, anchor="ra")

    # --- Código QR ---
    codigo = qrcode.make(texto_qr(datos), box_size=6, border=2).get_image().convert("RGB")
    codigo = codigo.resize((260, 260))
    imagen.paste(codigo, (40, 990))
    dibujo.text((330, 1010), "Este código QR trae el folio, los RFC", font=letra(22), fill=GRIS)
    dibujo.text((330, 1040), "y el total de la factura.", font=letra(22), fill=GRIS)
    dibujo.text((330, 1100), "Sello digital del SAT: FICTICIO", font=letra(22), fill=GRIS)
    dibujo.text((330, 1130), "Generada para probar el Validador de facturas", font=letra(22),
                fill=GRIS)
    dibujo.text((330, 1160), "de Soluciones Digitales (prototipo escolar).", font=letra(22),
                fill=GRIS)

    return imagen


def crear_imagen_desde_xml(contenido_xml):
    """Lee el XML de una factura y regresa su imagen."""
    return dibujar_factura(leer_factura(contenido_xml))


def generar_imagenes(carpetas=None):
    """Crea un PNG junto a cada XML de las carpetas. Regresa la lista de rutas."""
    if carpetas is None:
        carpetas = CARPETAS_CON_FACTURAS
    rutas = []
    for carpeta in carpetas:
        for ruta_xml in sorted(carpeta.glob("*.xml")):
            ruta_png = ruta_xml.with_suffix(".png")  # factura_01.xml -> factura_01.png
            crear_imagen_desde_xml(ruta_xml.read_bytes()).save(ruta_png)
            rutas.append(ruta_png)
    return rutas


if __name__ == "__main__":
    for ruta in generar_imagenes():
        print("Imagen creada:", ruta.relative_to(CARPETA))
