"""
generar_facturas.py
-------------------
Crea las 10 facturas XML de prueba (CFDI 4.0 simplificado) en la carpeta
facturas_prueba/ y el archivo datos/estados_sat_simulado.csv con el estado
que "diría" el SAT para cada una.

TODOS los datos son INVENTADOS: los RFC, nombres, folios y montos no existen.

Cómo usarlo (en la terminal, dentro de la carpeta del proyecto):
    python generar_facturas.py

Puedes correrlo las veces que quieras: siempre vuelve a crear los mismos
archivos con los mismos datos.
"""

import csv
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------
# 1. Rutas de las carpetas
# ---------------------------------------------------------------

# Path(__file__).parent es la carpeta donde está ESTE archivo.
# Así el programa funciona sin importar desde qué carpeta lo ejecutes.
CARPETA_PROYECTO = Path(__file__).parent
CARPETA_FACTURAS = CARPETA_PROYECTO / "facturas_prueba"
RUTA_CSV = CARPETA_PROYECTO / "datos" / "estados_sat_simulado.csv"

TASA_IVA = 0.16  # 16 % de IVA

# ---------------------------------------------------------------
# 2. Datos inventados
# ---------------------------------------------------------------

# Proveedores (los que EMITEN la factura).
# La clave corta ("papeleria", "limpieza"...) evita repetir el RFC y el
# nombre en cada factura y así no hay errores de dedo.
# Los nombres van en mayúsculas y sin acentos, como los escribe el SAT.
PROVEEDORES = {
    "papeleria":   {"rfc": "PAP010101AB1", "nombre": "PAPELERIA EJEMPLO SA DE CV"},
    "limpieza":    {"rfc": "LDE010101EF3", "nombre": "LIMPIEZA DEMO SA DE CV"},
    "computo":     {"rfc": "CPR010101CD2", "nombre": "COMPUTO PRUEBA SA DE CV"},
    "ferreteria":  {"rfc": "FFI010101GH4", "nombre": "FERRETERIA FICTICIA SA DE CV"},
    "cafeteria":   {"rfc": "CMU010101JK5", "nombre": "CAFETERIA MUESTRA SA DE CV"},
    "transportes": {"rfc": "TDE010101LM6", "nombre": "TRANSPORTES DEMO SA DE CV"},
    "imprenta":    {"rfc": "IPR010101NP7", "nombre": "IMPRENTA PRUEBA SA DE CV"},
}

# Receptores (los que RECIBEN la factura): RFC -> nombre.
# Los dos primeros son los únicos RFC válidos del Tecnológico (regla RN-05).
# El tercero es una empresa ajena: sirve para probar «Receptor incorrecto».
RECEPTORES = {
    "TEC000101AA1": "INSTITUTO TECNOLOGICO DE PRUEBA",
    "ITM000101BB2": "INSTITUTO TECNOLOGICO MODELO",
    "XYZ000101ZZ9": "EMPRESA AJENA DE PRUEBA SA DE CV",
}

# Las 10 facturas de prueba (es la tabla de la sección 4 del documento).
#   estado_sat        -> lo que responde el "SAT simulado" (se guarda en el CSV)
#   fecha_cancelacion -> solo para las canceladas; vacía si está vigente
#   esperado          -> lo que la app DEBE mostrar al validarla (para las pruebas)
FACTURAS_PRUEBA = [
    {"numero": 1, "proveedor": "papeleria", "rfc_receptor": "TEC000101AA1",
     "fecha": "2026-11-03T10:15:00", "descripcion": "Resma de papel carta",
     "cantidad": 10, "valor_unitario": 125.00,
     "estado_sat": "Vigente", "fecha_cancelacion": "", "esperado": "Vigente"},

    {"numero": 2, "proveedor": "limpieza", "rfc_receptor": "TEC000101AA1",
     "fecha": "2026-11-03T12:40:00", "descripcion": "Servicio de limpieza de oficinas",
     "cantidad": 1, "valor_unitario": 2800.00,
     "estado_sat": "Vigente", "fecha_cancelacion": "", "esperado": "Vigente"},

    {"numero": 3, "proveedor": "computo", "rfc_receptor": "ITM000101BB2",
     "fecha": "2026-11-04T09:30:00", "descripcion": "Teclado y mouse inalámbrico",
     "cantidad": 4, "valor_unitario": 750.00,
     "estado_sat": "Cancelada", "fecha_cancelacion": "2026-11-05", "esperado": "Cancelada"},

    {"numero": 4, "proveedor": "ferreteria", "rfc_receptor": "TEC000101AA1",
     "fecha": "2026-11-05T11:00:00", "descripcion": "Juego de desarmadores",
     "cantidad": 5, "valor_unitario": 180.00,
     "estado_sat": "Vigente", "fecha_cancelacion": "", "esperado": "Vigente"},

    {"numero": 5, "proveedor": "cafeteria", "rfc_receptor": "ITM000101BB2",
     "fecha": "2026-11-06T13:20:00", "descripcion": "Servicio de café para reunión",
     "cantidad": 1, "valor_unitario": 1500.00,
     "estado_sat": "Vigente", "fecha_cancelacion": "", "esperado": "Vigente"},

    {"numero": 6, "proveedor": "papeleria", "rfc_receptor": "TEC000101AA1",
     "fecha": "2026-11-06T16:45:00", "descripcion": "Caja de folders tamaño carta",
     "cantidad": 8, "valor_unitario": 95.00,
     "estado_sat": "Cancelada", "fecha_cancelacion": "2026-11-10", "esperado": "Cancelada"},

    {"numero": 7, "proveedor": "transportes", "rfc_receptor": "TEC000101AA1",
     "fecha": "2026-11-09T08:50:00", "descripcion": "Flete de mobiliario",
     "cantidad": 1, "valor_unitario": 4200.00,
     "estado_sat": "Vigente", "fecha_cancelacion": "", "esperado": "Vigente"},

    # Ojo: el SAT dice "Vigente", pero el receptor NO es el Tecnológico,
    # así que la app debe marcarla como «Receptor incorrecto» (RN-05).
    {"numero": 8, "proveedor": "imprenta", "rfc_receptor": "XYZ000101ZZ9",
     "fecha": "2026-11-10T10:05:00", "descripcion": "Impresión de lona publicitaria",
     "cantidad": 3, "valor_unitario": 650.00,
     "estado_sat": "Vigente", "fecha_cancelacion": "", "esperado": "Receptor incorrecto"},

    {"numero": 9, "proveedor": "limpieza", "rfc_receptor": "ITM000101BB2",
     "fecha": "2026-11-11T12:00:00", "descripcion": "Paquete de productos de limpieza",
     "cantidad": 12, "valor_unitario": 85.00,
     "estado_sat": "Vigente", "fecha_cancelacion": "", "esperado": "Vigente"},

    {"numero": 10, "proveedor": "computo", "rfc_receptor": "TEC000101AA1",
     "fecha": "2026-11-12T15:30:00", "descripcion": "Memoria USB 64 GB",
     "cantidad": 20, "valor_unitario": 140.00,
     "estado_sat": "Vigente", "fecha_cancelacion": "", "esperado": "Vigente"},
]

# ---------------------------------------------------------------
# 3. Plantilla del XML
# ---------------------------------------------------------------
# Es el "molde" de una factura CFDI 4.0, simplificado para el prototipo.
# Lo que está entre llaves {asi} se reemplaza con los datos de cada factura.
#   - RegimenFiscal 601 = General de Ley Personas Morales
#   - UsoCFDI G03       = Gastos en general
#   - Impuesto 002      = IVA
# Una factura real también trae sellos digitales y certificados; aquí no
# los ponemos porque no nos conectamos al SAT.
PLANTILLA_XML = """<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0" Fecha="{fecha}" Moneda="MXN"
    SubTotal="{subtotal}" Total="{total}" TipoDeComprobante="I">
  <cfdi:Emisor Rfc="{rfc_emisor}" Nombre="{nombre_emisor}" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="{rfc_receptor}" Nombre="{nombre_receptor}" UsoCFDI="G03"/>
  <cfdi:Conceptos>
    <cfdi:Concepto Descripcion="{descripcion}" Cantidad="{cantidad}" ValorUnitario="{valor_unitario}" Importe="{subtotal}"/>
  </cfdi:Conceptos>
  <cfdi:Impuestos TotalImpuestosTrasladados="{iva}">
    <cfdi:Traslados>
      <cfdi:Traslado Base="{subtotal}" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="{iva}"/>
    </cfdi:Traslados>
  </cfdi:Impuestos>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital Version="1.1" UUID="{uuid}" FechaTimbrado="{fecha_timbrado}"/>
  </cfdi:Complemento>
</cfdi:Comprobante>
"""

# ---------------------------------------------------------------
# 4. Funciones
# ---------------------------------------------------------------


def folio_fiscal(numero):
    """Arma un folio fiscal (UUID) inventado que termina en el número de factura.

    Ejemplo: folio_fiscal(3) -> "00000000-0000-4000-8000-000000000003"
    El :012d rellena el número con ceros hasta tener 12 dígitos.
    """
    return f"00000000-0000-4000-8000-{numero:012d}"


def nombre_archivo(numero):
    """Nombre del archivo XML. Ejemplo: nombre_archivo(3) -> "factura_03.xml"."""
    return f"factura_{numero:02d}.xml"


def calcular_importes(factura):
    """Regresa (subtotal, iva, total) de una factura.

    subtotal = cantidad x precio unitario
    iva      = 16 % del subtotal
    total    = subtotal + iva
    round(..., 2) deja solo 2 decimales (centavos).
    """
    subtotal = factura["cantidad"] * factura["valor_unitario"]
    iva = round(subtotal * TASA_IVA, 2)
    total = round(subtotal + iva, 2)
    return subtotal, iva, total


def crear_xml(factura):
    """Regresa el TEXTO del XML de una factura, listo para guardarse en un archivo."""
    proveedor = PROVEEDORES[factura["proveedor"]]
    subtotal, iva, total = calcular_importes(factura)

    # El SAT "timbra" (sella) la factura un minuto después de que se crea.
    fecha_timbrado = datetime.fromisoformat(factura["fecha"]) + timedelta(minutes=1)

    # .format() cambia cada {campo} de la plantilla por su valor.
    # :.2f escribe el número con 2 decimales, por ejemplo 1450.0 -> "1450.00".
    return PLANTILLA_XML.format(
        fecha=factura["fecha"],
        subtotal=f"{subtotal:.2f}",
        iva=f"{iva:.2f}",
        total=f"{total:.2f}",
        rfc_emisor=proveedor["rfc"],
        nombre_emisor=proveedor["nombre"],
        rfc_receptor=factura["rfc_receptor"],
        nombre_receptor=RECEPTORES[factura["rfc_receptor"]],
        descripcion=factura["descripcion"],
        cantidad=factura["cantidad"],
        valor_unitario=f"{factura['valor_unitario']:.2f}",
        uuid=folio_fiscal(factura["numero"]),
        fecha_timbrado=fecha_timbrado.isoformat(),
    )


def generar_facturas(carpeta=CARPETA_FACTURAS):
    """Guarda las 10 facturas XML en la carpeta y regresa la lista de rutas."""
    carpeta.mkdir(parents=True, exist_ok=True)  # crea la carpeta si no existe
    rutas = []
    for factura in FACTURAS_PRUEBA:
        ruta = carpeta / nombre_archivo(factura["numero"])
        ruta.write_text(crear_xml(factura), encoding="utf-8")
        rutas.append(ruta)
    return rutas


def generar_csv(ruta=RUTA_CSV):
    """Guarda el CSV del "SAT simulado": uuid, estado, fecha_cancelacion."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    # newline="" evita que en Windows aparezcan renglones vacíos de más.
    with open(ruta, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["uuid", "estado", "fecha_cancelacion"])  # encabezados
        for factura in FACTURAS_PRUEBA:
            escritor.writerow([
                folio_fiscal(factura["numero"]),
                factura["estado_sat"],
                factura["fecha_cancelacion"],
            ])
    return ruta


def main():
    """Crea todo y muestra en la terminal una tabla para revisar."""
    rutas = generar_facturas()
    generar_csv()

    print(f"Listo: se crearon {len(rutas)} facturas en la carpeta {CARPETA_FACTURAS.name}/")
    print(f"       y el archivo datos/{RUTA_CSV.name}")
    print()
    print(f"{'#':>2}  {'Archivo':<15} {'Proveedor':<29} {'Receptor':<13} "
          f"{'Total':>11}  {'Estado SAT':<10}  Resultado esperado")
    print("-" * 108)
    for factura in FACTURAS_PRUEBA:
        _, _, total = calcular_importes(factura)
        proveedor = PROVEEDORES[factura["proveedor"]]["nombre"]
        total_texto = f"${total:,.2f}"  # :, separa los miles con coma
        print(f"{factura['numero']:>2}  {nombre_archivo(factura['numero']):<15} "
              f"{proveedor:<29} {factura['rfc_receptor']:<13} {total_texto:>11}  "
              f"{factura['estado_sat']:<10}  {factura['esperado']}")


# Esto hace que main() solo se ejecute cuando corres el archivo directamente
# (python generar_facturas.py), y NO cuando otro archivo lo importa.
# Más adelante la app y las pruebas van a importar FACTURAS_PRUEBA y crear_xml.
if __name__ == "__main__":
    main()
