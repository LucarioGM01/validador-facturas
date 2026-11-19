"""
comprobante.py
--------------
Arma el comprobante digital de una validación como una página HTML que se
puede descargar, abrir en el navegador e imprimir o guardar como PDF (Ctrl+P).

Reemplaza la hoja que antes se imprimía del portal del SAT y se engrapaba.
"""

import base64
import html
from pathlib import Path
from string import Template

from validador import ETIQUETAS, formatear_fecha, formatear_fecha_hora

CARPETA = Path(__file__).parent

# Logos: el de la marca (Soluciones Digitales) y el del cliente (el Tecnológico).
# Se aceptan en PNG o JPG; si todavía no existen, se muestra el nombre en texto.
NOMBRES_LOGO_MARCA = ("logo.png", "logo.jpg", "logo.jpeg")
NOMBRES_LOGO_TEC = ("logo_tec.png", "logo_tec.jpg", "logo_tec.jpeg")

NOMBRE_CLIENTE = "Instituto Tecnológico de Matehuala"
AREA_CLIENTE = "Departamento de Recursos Financieros"

# Colores del estado sobre fondo CLARO (el comprobante es blanco para imprimirse).
COLORES_ESTADO = {
    "Vigente": ("#1E6B34", "#E3F3E7"),
    "Cancelada": ("#9B2318", "#FBE6E3"),
    "Receptor incorrecto": ("#7A5000", "#FFF1CC"),
}
COLOR_ESTADO_OTRO = ("#444444", "#EEEEEE")


def buscar_logo(nombres):
    """Regresa la ruta del primer archivo que exista de la lista, o None."""
    for nombre in nombres:
        ruta = CARPETA / nombre
        if ruta.exists():
            return ruta
    return None


def logo_como_dato(ruta):
    """Convierte una imagen en texto "data:image/...;base64,..." para meterla
    DENTRO del HTML. Así el comprobante se ve completo aunque se abra en otra
    computadora. Regresa "" si no hay imagen."""
    if ruta is None:
        return ""
    tipo = "image/png" if ruta.suffix.lower() == ".png" else "image/jpeg"
    texto = base64.b64encode(ruta.read_bytes()).decode("ascii")
    return f"data:{tipo};base64,{texto}"


def nombre_archivo_comprobante(validacion):
    """Ejemplo: 'comprobante_0003_12.html' (folio ...0003, comprobante número 12)."""
    return f"comprobante_{validacion['uuid'][-4:]}_{validacion['id']}.html"


# Plantilla del comprobante. Usamos string.Template ($variable) en lugar de
# f-strings porque el CSS lleva muchas llaves { } que confundirían a Python.
PLANTILLA = Template("""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Comprobante de validación $folio_corto</title>
<style>
  body { margin: 0; background: #F5F1EC; color: #2B2E33;
         font-family: "Open Sans", Arial, sans-serif; }
  .hoja { max-width: 760px; margin: 24px auto; background: #FFFFFF;
          border: 1px solid #E3B08F; border-radius: 12px; padding: 32px; }
  .encabezado { display: flex; justify-content: space-between; align-items: center;
                gap: 16px; border-bottom: 2px solid #CD9472; padding-bottom: 16px; }
  .encabezado img { max-height: 70px; max-width: 220px; }
  .marca { font-family: Georgia, serif; font-size: 24px; color: #8A5434; }
  .lema { font-size: 12px; color: #6B6259; font-style: italic; }
  .cliente { text-align: right; font-size: 13px; color: #6B6259; }
  h1 { font-family: Georgia, serif; color: #8A5434; font-size: 26px; margin: 24px 0 4px; }
  .numero { color: #6B6259; margin: 0 0 20px; }
  .estado { display: inline-block; padding: 8px 16px; border-radius: 999px;
            font-weight: 700; font-size: 18px; color: $color_estado;
            background: $fondo_estado; border: 1px solid $color_estado; }
  table { width: 100%; border-collapse: collapse; margin-top: 20px; }
  th, td { text-align: left; padding: 9px 8px; border-bottom: 1px solid #EFE6DD;
           vertical-align: top; }
  th { width: 38%; color: #8A5434; font-weight: 600; }
  .pie { margin-top: 28px; font-size: 12px; color: #6B6259; border-top: 1px solid #EFE6DD;
         padding-top: 12px; }
  .imprimir { text-align: center; font-size: 13px; color: #6B6259; }
  @media print { body { background: #FFFFFF; } .hoja { border: none; margin: 0; }
                 .imprimir { display: none; } }
</style>
</head>
<body>
<p class="imprimir">Para guardarlo como PDF: Ctrl + P y elige «Guardar como PDF».</p>
<div class="hoja">
  <div class="encabezado">
    <div>$bloque_marca</div>
    <div class="cliente">$bloque_cliente</div>
  </div>

  <h1>Comprobante de validación</h1>
  <p class="numero">Comprobante núm. $id · $fecha_hora</p>

  <span class="estado">$etiqueta</span>

  <table>
    <tr><th>Folio fiscal (UUID)</th><td>$uuid</td></tr>
    <tr><th>Proveedor</th><td>$nombre_emisor<br>RFC $rfc_emisor</td></tr>
    <tr><th>Receptor</th><td>$nombre_receptor<br>RFC $rfc_receptor</td></tr>
    <tr><th>Total</th><td>$total</td></tr>
    <tr><th>Fecha de la factura</th><td>$fecha_emision</td></tr>
    $fila_cancelacion
    <tr><th>Validó</th><td>$usuario</td></tr>
    <tr><th>Fecha y hora de validación</th><td>$fecha_hora</td></tr>
    <tr><th>Tiempo de validación</th><td>$milisegundos milisegundos</td></tr>
  </table>

  <div class="pie">
    Prototipo escolar con datos de prueba. La validación es SIMULADA: no consulta
    al SAT y este comprobante no tiene validez fiscal ni es un documento oficial
    del Tecnológico.
  </div>
</div>
</body>
</html>
""")


def crear_comprobante_html(validacion, logo_marca="", logo_tec=""):
    """Regresa el HTML del comprobante de una validación.

    - validacion: diccionario de base_datos.obtener_validacion()
    - logo_marca, logo_tec: imágenes en formato "data:..." (de logo_como_dato)
    """
    e = html.escape  # cambia < > & " por códigos seguros, para que ningún dato rompa el HTML

    if logo_marca:
        bloque_marca = f'<img src="{logo_marca}" alt="Soluciones Digitales">'
    else:
        bloque_marca = ('<div class="marca">Soluciones Digitales</div>'
                        '<div class="lema">«No hay trabajo tan difícil que no se pueda solucionar»</div>')

    bloque_cliente = f"{e(NOMBRE_CLIENTE)}<br>{e(AREA_CLIENTE)}"
    if logo_tec:
        bloque_cliente = f'<img src="{logo_tec}" alt="{e(NOMBRE_CLIENTE)}"><br>' + bloque_cliente

    fila_cancelacion = ""
    if validacion["fecha_cancelacion"]:
        fila_cancelacion = (f"<tr><th>Fecha de cancelación</th>"
                            f"<td>{e(formatear_fecha(validacion['fecha_cancelacion']))}</td></tr>")

    color, fondo = COLORES_ESTADO.get(validacion["estado"], COLOR_ESTADO_OTRO)

    return PLANTILLA.substitute(
        folio_corto=e(validacion["uuid"][-4:]),
        bloque_marca=bloque_marca,
        bloque_cliente=bloque_cliente,
        id=validacion["id"],
        fecha_hora=e(formatear_fecha_hora(validacion["fecha_hora"])),
        etiqueta=e(ETIQUETAS.get(validacion["estado"], validacion["estado"])),
        color_estado=color,
        fondo_estado=fondo,
        uuid=e(validacion["uuid"]),
        nombre_emisor=e(validacion["nombre_emisor"]),
        rfc_emisor=e(validacion["rfc_emisor"]),
        nombre_receptor=e(validacion["nombre_receptor"] or "—"),
        rfc_receptor=e(validacion["rfc_receptor"]),
        total=f"${validacion['total']:,.2f} MXN",
        fecha_emision=e(formatear_fecha(validacion["fecha_emision"])),
        fila_cancelacion=fila_cancelacion,
        usuario=e(validacion["usuario"]),
        milisegundos=f"{validacion['segundos'] * 1000:.2f}",
    )
