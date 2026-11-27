"""
validador.py
------------
Decide el estado de cada factura aplicando las reglas de negocio:

  RN-01  Solo una factura Vigente puede usarse para un pago.
  RN-02  Si está Cancelada: guardar la fecha de cancelación y avisar al jefe.
  RN-03  La factura cancelada se conserva en el historial marcada como cancelada.
  RN-04  La factura nueva pasa por la misma validación y queda ligada a la cancelada.
  RN-05  El RFC del receptor debe ser TEC000101AA1 o ITM000101BB2.
  RN-06  Toda validación guarda fecha, hora y usuario.
  RN-07  Una factura ya validada como vigente no se vuelve a validar.

El estado "en el SAT" se consulta en un archivo CSV SIMULADO
(datos/estados_sat_simulado.csv): no nos conectamos al SAT real.

Este archivo NO manda el aviso a Telegram: solo dice si hay que mandarlo
(resultado["avisar_jefe"]). El envío lo hará avisos.py en el Paso 6.

Prueba rápida desde la terminal:
    python validador.py
"""

import csv
import time
from datetime import datetime
from pathlib import Path

import base_datos
from generar_facturas import generar_csv
from lector_xml import MENSAJE_INVALIDA, FacturaInvalida, leer_factura

# ---------------------------------------------------------------
# 1. Constantes
# ---------------------------------------------------------------

RUTA_CSV = Path(__file__).parent / "datos" / "estados_sat_simulado.csv"

# Estados posibles. Se escriben una sola vez para evitar errores de dedo.
VIGENTE = "Vigente"
CANCELADA = "Cancelada"
RECEPTOR_INCORRECTO = "Receptor incorrecto"
NO_ENCONTRADA = "No encontrada"
ARCHIVO_INVALIDO = "Archivo inválido"

# Texto + símbolo de cada estado, para que no dependa solo del color (la app
# los usará en el Paso 5).
ETIQUETAS = {
    VIGENTE: "✔ Vigente",
    CANCELADA: "✖ Cancelada",
    RECEPTOR_INCORRECTO: "⚠ Receptor incorrecto",
    NO_ENCONTRADA: "? No encontrada",
    ARCHIVO_INVALIDO: "⊘ Archivo inválido",
}

# RN-05: los únicos RFC (ficticios) que puede tener el receptor.
RFC_RECEPTORES_VALIDOS = ("TEC000101AA1", "ITM000101BB2")


# ---------------------------------------------------------------
# 2. Ayudantes para fechas
# ---------------------------------------------------------------

def formatear_fecha(texto_iso):
    """'2026-11-05' -> '05/11/2026'. Si viene vacío regresa ''."""
    if not texto_iso:
        return ""
    return datetime.fromisoformat(texto_iso).strftime("%d/%m/%Y")


def formatear_fecha_hora(texto_iso):
    """'2026-11-18T10:30:00' -> '18/11/2026 a las 10:30'."""
    if not texto_iso:
        return ""
    return datetime.fromisoformat(texto_iso).strftime("%d/%m/%Y a las %H:%M")


def _segundos_desde(inicio):
    """Segundos que pasaron desde `inicio`. Usamos 6 decimales porque validar
    tarda menos de un milisegundo y con menos decimales saldría 0."""
    return round(time.perf_counter() - inicio, 6)


# ---------------------------------------------------------------
# 3. SAT simulado
# ---------------------------------------------------------------

def consultar_estado(uuid, ruta_csv=RUTA_CSV):
    """Busca el folio en el CSV del SAT simulado.

    Regresa {"estado": ..., "fecha_cancelacion": ...}.
    Si el folio no está en el CSV, el estado es "No encontrada".
    """
    if not ruta_csv.exists():
        generar_csv(ruta_csv)  # si se borró el CSV, lo vuelve a crear solo

    with open(ruta_csv, newline="", encoding="utf-8") as archivo:
        # DictReader lee cada renglón como diccionario: fila["uuid"], fila["estado"]...
        for fila in csv.DictReader(archivo):
            if fila["uuid"].strip().upper() == uuid.strip().upper():
                return {
                    "estado": fila["estado"].strip().capitalize(),  # "vigente" -> "Vigente"
                    "fecha_cancelacion": fila["fecha_cancelacion"].strip(),
                }
    return {"estado": NO_ENCONTRADA, "fecha_cancelacion": ""}


# ---------------------------------------------------------------
# 4. Validación
# ---------------------------------------------------------------

def validar_factura(conexion, contenido_xml, usuario, nombre_archivo="", datos=None):
    """Valida UNA factura de principio a fin y regresa un diccionario con el resultado.

    - conexion:       la base de datos (base_datos.conectar())
    - contenido_xml:  el contenido del archivo (texto o bytes)
    - usuario:        quién está validando (RN-06)
    - nombre_archivo: solo para mostrarlo en pantalla
    - datos:          (opcional) los datos YA leídos, por ejemplo de la foto de
                      una factura con lector_imagen.py. Si vienen, no se lee XML.

    El orden es: leer el XML -> ¿ya estaba validada? (RN-07) -> consultar el SAT
    simulado -> revisar el receptor (RN-05) -> guardar el comprobante (RN-06).
    """
    inicio = time.perf_counter()  # cronómetro: para medir cuánto tarda

    # Resultado "vacío" que vamos llenando según lo que pase.
    resultado = {
        "archivo": nombre_archivo,
        "uuid": "", "rfc_emisor": "", "nombre_emisor": "",
        "rfc_receptor": "", "nombre_receptor": "", "total": 0.0, "fecha": "",
        "estado": "",
        "fecha_cancelacion": "",
        "mensaje": "",
        "puede_pagarse": False,  # RN-01
        "avisar_jefe": False,    # RN-02
        "es_repetida": False,    # RN-07
        "segundos": 0.0,
        "id_validacion": None,   # número del comprobante guardado
        "aviso_lectura": "",     # si la factura vino en imagen y su lectura es dudosa
    }

    # --- Paso 1: leer el XML (lector_xml.py), si los datos no vienen ya leídos ---
    if datos is None:
        try:
            datos = leer_factura(contenido_xml)
        except FacturaInvalida:
            resultado["estado"] = ARCHIVO_INVALIDO
            resultado["mensaje"] = (f"{MENSAJE_INVALIDA}. Revisa que sea el archivo .xml "
                                    "que mandó el proveedor (no el PDF).")
            resultado["segundos"] = _segundos_desde(inicio)
            return resultado  # no se guarda nada: ni siquiera sabemos el folio
    resultado.update(datos)  # copia uuid, RFC, nombres, total y fecha

    # --- Paso 2: RN-07, ¿ya se había validado como vigente? ---
    anterior = base_datos.obtener_factura(conexion, datos["uuid"])
    if anterior is not None and anterior["estado"] == VIGENTE:
        resultado["estado"] = VIGENTE
        resultado["es_repetida"] = True
        resultado["mensaje"] = (
            f"Ya validada el {formatear_fecha_hora(anterior['ultima_validacion'])}."
        )
        resultado["segundos"] = _segundos_desde(inicio)
        return resultado  # no se vuelve a validar ni a guardar

    # --- Paso 3: consultar el SAT simulado y aplicar las reglas ---
    sat = consultar_estado(datos["uuid"])

    if sat["estado"] == CANCELADA:
        # RN-02: guardar fecha de cancelación y avisar al jefe. Si el aviso ya le
        # llegó antes, no se repite; si no se pudo enviar (sin internet o sin
        # Telegram), se vuelve a intentar.
        resultado["estado"] = CANCELADA
        resultado["fecha_cancelacion"] = sat["fecha_cancelacion"]
        ya_se_aviso = (anterior is not None and anterior["estado"] == CANCELADA
                       and bool(anterior["aviso_enviado"]))
        resultado["avisar_jefe"] = not ya_se_aviso
        resultado["mensaje"] = (
            f"Cancelada el {formatear_fecha(sat['fecha_cancelacion'])}. No se puede pagar: "
            "hay que pedir al proveedor una factura nueva."
        )
        if ya_se_aviso:
            resultado["mensaje"] += " El jefe ya había sido avisado."

    elif sat["estado"] == VIGENTE and datos["rfc_receptor"] not in RFC_RECEPTORES_VALIDOS:
        # RN-05: está vigente, pero no está a nombre del Tecnológico.
        resultado["estado"] = RECEPTOR_INCORRECTO
        resultado["mensaje"] = (
            f"Está a nombre de {datos['rfc_receptor']}, no del Tecnológico "
            f"({' o '.join(RFC_RECEPTORES_VALIDOS)}). Pide al proveedor que la corrija."
        )

    elif sat["estado"] == VIGENTE:
        # RN-01: solo las vigentes con receptor correcto se pueden pagar.
        resultado["estado"] = VIGENTE
        resultado["puede_pagarse"] = True
        resultado["mensaje"] = "Vigente: se puede usar para el pago."

    else:
        resultado["estado"] = NO_ENCONTRADA
        resultado["mensaje"] = ("El folio no aparece en el SAT (simulado). Revisa que el "
                                "XML sea el correcto o pide al proveedor que lo verifique.")

    # --- Paso 3b: lectura dudosa de una imagen (lector_imagen.py) ---
    # Si el QR y la IA no coinciden, o solo la IA pudo leerla, no se puede
    # confiar en los datos: aunque salga vigente, no se paga hasta revisarla.
    if resultado["aviso_lectura"]:
        resultado["puede_pagarse"] = False
        if resultado["estado"] == VIGENTE:
            resultado["mensaje"] = ("Vigente en el SAT, pero NO la pagues todavía: primero "
                                    "revisa la lectura de la imagen.")

    # --- Paso 4: guardar la factura y el comprobante (RN-03 y RN-06) ---
    resultado["segundos"] = _segundos_desde(inicio)
    resultado["id_validacion"] = base_datos.guardar_validacion(
        conexion, resultado, usuario, resultado["segundos"]
    )
    return resultado


def registrar_factura_nueva(conexion, uuid_cancelada, contenido_xml, usuario, nombre_archivo=""):
    """RN-04: valida la factura nueva y, si sale Vigente, la liga a la cancelada.

    Regresa el resultado de la validación con una clave extra:
    resultado["ligada"] = True si quedó ligada, False si no.
    """
    cancelada = base_datos.obtener_factura(conexion, uuid_cancelada)
    if cancelada is None or cancelada["estado"] != CANCELADA:
        raise ValueError("Solo se puede ligar una factura nueva a una factura cancelada.")

    # La factura nueva pasa por la MISMA validación que todas.
    resultado = validar_factura(conexion, contenido_xml, usuario, nombre_archivo)
    resultado["ligada"] = False

    if resultado["uuid"] == uuid_cancelada:
        resultado["mensaje"] = ("Subiste la misma factura cancelada. Sube la factura NUEVA "
                                "que mandó el proveedor.")
    elif resultado["estado"] == VIGENTE:
        base_datos.ligar_reemplazo(conexion, uuid_cancelada, resultado["uuid"])
        resultado["ligada"] = True
        resultado["mensaje"] += f" Quedó ligada a la factura cancelada …{uuid_cancelada[-4:]}."
    else:
        resultado["mensaje"] = (f"La factura nueva salió «{resultado['estado']}», así que no "
                                f"se ligó. {resultado['mensaje']}")
    return resultado


# ---------------------------------------------------------------
# 5. Prueba rápida desde la terminal
# ---------------------------------------------------------------

if __name__ == "__main__":
    from generar_facturas import FACTURAS_PRUEBA, crear_xml, nombre_archivo

    # Base de datos en memoria: es temporal y se borra al terminar,
    # así esta demostración no ensucia la base de datos real.
    conexion = base_datos.conectar(":memory:")

    print("Validando las 10 facturas de prueba con el usuario 'auxiliar'...\n")
    for factura in FACTURAS_PRUEBA:
        archivo = nombre_archivo(factura["numero"])
        r = validar_factura(conexion, crear_xml(factura), "auxiliar", archivo)
        aviso = "  -> AVISAR AL JEFE POR TELEGRAM" if r["avisar_jefe"] else ""
        print(f"{archivo}: {r['estado']:<20} {r['mensaje']}{aviso}")

    print("\nSe carga OTRA VEZ la factura 1 (regla RN-07):")
    r = validar_factura(conexion, crear_xml(FACTURAS_PRUEBA[0]), "auxiliar", "factura_01.xml")
    print(f"factura_01.xml: {r['mensaje']}")

    resumen = base_datos.resumen_mes(conexion, base_datos.ahora()[:7])
    print(f"\nResumen: {resumen['vigentes']} vigentes, {resumen['canceladas']} canceladas, "
          f"{resumen['receptor_incorrecto']} con receptor incorrecto. "
          f"Tiempo promedio: {resumen['segundos_promedio'] * 1000:.2f} milisegundos por "
          "factura (antes: 1 a 5 minutos).")
