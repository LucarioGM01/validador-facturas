"""
comprobante.py
--------------
Arma el comprobante digital de una validación como una IMAGEN PNG.

Reemplaza la hoja que antes se imprimía del portal del SAT y se engrapaba.
El bot de Telegram la manda directo al chat y la página permite descargarla.

Todo se dibuja con Python (librería Pillow), sin HTML.
"""

import io
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw

from imagen_factura import dinero, letra
from validador import formatear_fecha, formatear_fecha_hora

# ---------------------------------------------------------------
# 1. Constantes
# ---------------------------------------------------------------

CARPETA = Path(__file__).parent

# Logos: el de la marca (Soluciones Digitales) y el del cliente (el Tecnológico).
# Se aceptan en PNG o JPG; si no existen, se escribe el nombre en texto.
NOMBRES_LOGO_MARCA = ("logo.png", "logo.jpg", "logo.jpeg")
NOMBRES_LOGO_TEC = ("logo_tec.png", "logo_tec.jpg", "logo_tec.jpeg")

NOMBRE_CLIENTE = "Instituto Tecnológico de Matehuala"
AREA_CLIENTE = "Departamento de Recursos Financieros"

ANCHO = 900
ALTO = 1150

BLANCO = (255, 255, 255)
NEGRO = (30, 30, 30)
GRIS = (110, 110, 110)
GRIS_CLARO = (236, 236, 236)
COBRE = (138, 84, 52)

# Color de cada estado: (texto, fondo). El estado SIEMPRE se escribe con
# palabras; el color solo ayuda a reconocerlo más rápido.
COLORES_ESTADO = {
    "Vigente": ((30, 107, 52), (227, 243, 231)),
    "Cancelada": ((155, 35, 24), (251, 230, 227)),
    "Receptor incorrecto": ((122, 74, 0), (255, 241, 204)),
}
COLOR_OTRO = ((70, 70, 70), (238, 238, 238))

AVISO = ("Prototipo escolar con datos de prueba. La validación es SIMULADA: no consulta al "
         "SAT y este comprobante no tiene validez fiscal ni es un documento oficial del "
         "Tecnológico.")


# ---------------------------------------------------------------
# 2. Funciones
# ---------------------------------------------------------------

def buscar_logo(nombres):
    """Regresa la ruta del primer archivo que exista de la lista, o None."""
    for nombre in nombres:
        ruta = CARPETA / nombre
        if ruta.exists():
            return ruta
    return None


def nombre_archivo_comprobante(validacion):
    """Ejemplo: 'comprobante_0003_12.png' (folio ...0003, comprobante número 12)."""
    return f"comprobante_{validacion['uuid'][-4:]}_{validacion['id']}.png"


def renglones_comprobante(validacion):
    """Lista de (etiqueta, valor) que se escriben en el comprobante.

    Está separada del dibujo para poder probar fácilmente qué datos trae.
    """
    renglones = [
        ("Folio fiscal", validacion["uuid"]),
        ("Proveedor", f"{validacion['nombre_emisor']}\nRFC {validacion['rfc_emisor']}"),
        ("Receptor", f"{validacion['nombre_receptor'] or '—'}\nRFC {validacion['rfc_receptor']}"),
        ("Total", f"{dinero(validacion['total'])} MXN"),
        ("Fecha de la factura", formatear_fecha(validacion["fecha_emision"]) or "—"),
    ]
    if validacion["fecha_cancelacion"]:
        renglones.append(("Fecha de cancelación", formatear_fecha(validacion["fecha_cancelacion"])))
    renglones += [
        ("Validó", validacion["usuario"]),
        ("Fecha y hora", formatear_fecha_hora(validacion["fecha_hora"])),
        ("Tiempo", f"{validacion['segundos'] * 1000:.2f} milisegundos"),
    ]
    return renglones


def dibujar_comprobante(validacion):
    """Dibuja el comprobante y regresa la imagen (objeto Image de Pillow).

    `validacion` es el diccionario de base_datos.obtener_validacion().
    """
    imagen = Image.new("RGB", (ANCHO, ALTO), BLANCO)
    dibujo = ImageDraw.Draw(imagen)

    # --- Encabezado: marca a la izquierda, Tecnológico a la derecha ---
    ruta_marca = buscar_logo(NOMBRES_LOGO_MARCA)
    if ruta_marca:
        logo = Image.open(ruta_marca).convert("RGB")
        logo.thumbnail((260, 110))  # lo hace más chico sin deformarlo
        imagen.paste(logo, (40, 30))
    else:
        dibujo.text((40, 40), "Soluciones Digitales", font=letra(34, negrita=True), fill=COBRE)
        dibujo.text((40, 88), "«No hay trabajo tan difícil que no se pueda solucionar»",
                    font=letra(17), fill=GRIS)

    ruta_tec = buscar_logo(NOMBRES_LOGO_TEC)
    if ruta_tec:
        logo_tec = Image.open(ruta_tec).convert("RGB")
        logo_tec.thumbnail((100, 100))
        imagen.paste(logo_tec, (ANCHO - 40 - logo_tec.width, 25))
    dibujo.text((ANCHO - 40, 132), NOMBRE_CLIENTE, font=letra(17), fill=GRIS, anchor="ra")
    dibujo.text((ANCHO - 40, 154), AREA_CLIENTE, font=letra(17), fill=GRIS, anchor="ra")
    dibujo.line([40, 190, ANCHO - 40, 190], fill=COBRE, width=3)

    # --- Título ---
    dibujo.text((40, 215), "Comprobante de validación", font=letra(40, negrita=True), fill=COBRE)
    dibujo.text((40, 268), f"Comprobante núm. {validacion['id']}", font=letra(22), fill=GRIS)

    # --- Estado en un recuadro de color ---
    texto_color, fondo = COLORES_ESTADO.get(validacion["estado"], COLOR_OTRO)
    dibujo.rounded_rectangle([40, 315, ANCHO - 40, 385], radius=18, fill=fondo,
                             outline=texto_color, width=3)
    dibujo.text((ANCHO // 2, 350), f"ESTADO: {validacion['estado'].upper()}",
                font=letra(32, negrita=True), fill=texto_color, anchor="mm")

    # --- Datos, renglón por renglón ---
    y = 420
    for etiqueta, valor in renglones_comprobante(validacion):
        dibujo.text((40, y), etiqueta, font=letra(22, negrita=True), fill=COBRE)
        renglones_valor = []
        for parte in valor.split("\n"):
            renglones_valor += textwrap.wrap(parte, 38) or [""]
        for renglon in renglones_valor:
            dibujo.text((300, y), renglon, font=letra(22), fill=NEGRO)
            y += 30
        y += 14
        dibujo.line([40, y - 8, ANCHO - 40, y - 8], fill=GRIS_CLARO, width=1)

    # --- Aviso al pie ---
    y = max(y + 10, ALTO - 120)
    for renglon in textwrap.wrap(AVISO, 80):
        dibujo.text((40, y), renglon, font=letra(17), fill=GRIS)
        y += 24

    return imagen


def comprobante_png(validacion):
    """Regresa el comprobante como bytes de un archivo PNG (para descargarlo o mandarlo)."""
    memoria = io.BytesIO()   # un "archivo" que vive en la memoria, no en el disco
    dibujar_comprobante(validacion).save(memoria, "PNG")
    return memoria.getvalue()
