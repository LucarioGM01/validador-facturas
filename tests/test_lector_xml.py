"""
Pruebas de lector_xml.py

Cómo correrlas (en la terminal, desde la carpeta del proyecto):
    python -m unittest discover tests -v

El -v ("verbose") muestra el nombre de cada prueba y si pasó (ok) o falló.
"""

import sys
import tempfile
import time
import unittest
from pathlib import Path

# Agrega la carpeta del proyecto a los lugares donde Python busca módulos,
# para poder importar lector_xml y generar_facturas desde la carpeta tests/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generar_facturas import (
    FACTURAS_PRUEBA,
    calcular_importes,
    crear_xml,
    folio_fiscal,
    generar_facturas,
)
from lector_xml import MENSAJE_INVALIDA, FacturaInvalida, leer_factura


class TestLeerFacturaValida(unittest.TestCase):
    """Casos donde el archivo SÍ es una factura: debe leer bien los datos."""

    def test_lee_los_datos_principales(self):
        """Lee folio, RFC emisor, RFC receptor y total de la factura 1 sin teclearlos."""
        datos = leer_factura(crear_xml(FACTURAS_PRUEBA[0]))

        # Los 4 datos que pide el portal del SAT para verificar una factura:
        self.assertEqual(datos["uuid"], "00000000-0000-4000-8000-000000000001")
        self.assertEqual(datos["rfc_emisor"], "PAP010101AB1")
        self.assertEqual(datos["rfc_receptor"], "TEC000101AA1")
        self.assertEqual(datos["total"], 1450.00)
        # Datos extra que también usa la app:
        self.assertEqual(datos["nombre_emisor"], "PAPELERIA EJEMPLO SA DE CV")
        self.assertEqual(datos["fecha"], "2026-11-03T10:15:00")

    def test_lee_las_10_facturas_de_prueba(self):
        """Las 10 facturas de prueba se leen con su folio, receptor y total correctos."""
        for factura in FACTURAS_PRUEBA:
            # subTest hace que, si falla una, te diga cuál número fue.
            with self.subTest(factura=factura["numero"]):
                datos = leer_factura(crear_xml(factura))
                _, _, total_esperado = calcular_importes(factura)
                self.assertEqual(datos["uuid"], folio_fiscal(factura["numero"]))
                self.assertEqual(datos["rfc_receptor"], factura["rfc_receptor"])
                self.assertAlmostEqual(datos["total"], total_esperado, places=2)

    def test_lee_archivos_guardados_en_disco(self):
        """Lee un archivo .xml como bytes, igual que lo recibe la app al subirlo."""
        # Carpeta temporal: se borra sola al terminar el "with".
        with tempfile.TemporaryDirectory() as carpeta:
            rutas = generar_facturas(Path(carpeta))
            datos = leer_factura(rutas[2].read_bytes())  # rutas[2] es la factura 3
        self.assertEqual(datos["uuid"], folio_fiscal(3))
        self.assertEqual(datos["nombre_emisor"], "COMPUTO PRUEBA SA DE CV")
        self.assertEqual(datos["total"], 3480.00)

    def test_acepta_texto_y_bytes(self):
        """Da el mismo resultado si recibe el XML como texto o como bytes."""
        texto = crear_xml(FACTURAS_PRUEBA[4])
        self.assertEqual(leer_factura(texto), leer_factura(texto.encode("utf-8")))

    def test_lectura_rapida(self):
        """Leer las 10 facturas tarda menos de 1 segundo (la meta es 10 s por factura)."""
        inicio = time.perf_counter()
        for factura in FACTURAS_PRUEBA:
            leer_factura(crear_xml(factura))
        segundos = time.perf_counter() - inicio
        self.assertLess(segundos, 1.0)


class TestArchivoInvalido(unittest.TestCase):
    """Casos donde el archivo NO es una factura: debe salir el mensaje claro."""

    def comprobar_que_es_invalido(self, contenido):
        """Ayudante: revisa que leer_factura lance FacturaInvalida con el mensaje exacto.

        Regresa el error para que la prueba pueda revisar también el detalle.
        """
        with self.assertRaises(FacturaInvalida) as contexto:
            leer_factura(contenido)
        self.assertEqual(str(contexto.exception), MENSAJE_INVALIDA)
        return contexto.exception

    def test_texto_que_no_es_xml(self):
        """Un archivo de texto normal no es una factura."""
        self.comprobar_que_es_invalido(b"Hola, esto es un archivo de texto")

    def test_archivo_vacio(self):
        """Un archivo vacío no es una factura."""
        self.comprobar_que_es_invalido(b"")

    def test_xml_cortado(self):
        """Un XML incompleto (archivo dañado) no es una factura."""
        self.comprobar_que_es_invalido(crear_xml(FACTURAS_PRUEBA[0])[:200])

    def test_xml_que_no_es_factura(self):
        """Un XML bien escrito pero de otra cosa (una lista de alumnos) no es una factura."""
        error = self.comprobar_que_es_invalido(
            "<?xml version='1.0'?><lista><alumno>Ana</alumno></lista>"
        )
        self.assertIn("Comprobante", error.detalle)

    def test_factura_sin_timbre(self):
        """Una factura sin TimbreFiscalDigital (sin folio fiscal) no es válida."""
        xml = crear_xml(FACTURAS_PRUEBA[0])
        inicio = xml.index("<cfdi:Complemento>")
        fin = xml.index("</cfdi:Complemento>") + len("</cfdi:Complemento>")
        error = self.comprobar_que_es_invalido(xml[:inicio] + xml[fin:])
        self.assertIn("TimbreFiscalDigital", error.detalle)

    def test_factura_sin_uuid(self):
        """Una factura con timbre pero sin UUID no es válida."""
        xml = crear_xml(FACTURAS_PRUEBA[0]).replace(
            'UUID="00000000-0000-4000-8000-000000000001" ', ""
        )
        error = self.comprobar_que_es_invalido(xml)
        self.assertIn("UUID", error.detalle)

    def test_total_que_no_es_numero(self):
        """Una factura cuyo Total no es un número no es válida."""
        xml = crear_xml(FACTURAS_PRUEBA[0]).replace(
            'Total="1450.00"', 'Total="mil cuatrocientos"'
        )
        self.comprobar_que_es_invalido(xml)


if __name__ == "__main__":
    unittest.main()
