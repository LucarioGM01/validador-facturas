"""
Pruebas de comprobante.py (el comprobante digital descargable)

Cómo correrlas (en la terminal, desde la carpeta del proyecto):
    python -m unittest discover tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import base_datos
from comprobante import crear_comprobante_html, nombre_archivo_comprobante
from generar_facturas import FACTURAS_PRUEBA, crear_xml, folio_fiscal
from validador import validar_factura


class TestComprobante(unittest.TestCase):

    def setUp(self):
        self.conexion = base_datos.conectar(":memory:")
        resultado = validar_factura(self.conexion, crear_xml(FACTURAS_PRUEBA[2]), "auxiliar")
        self.validacion = base_datos.obtener_validacion(self.conexion, resultado["id_validacion"])

    def tearDown(self):
        self.conexion.close()

    def test_trae_los_datos_de_la_validacion(self):
        """El comprobante muestra folio, proveedor, total, estado, fechas y usuario (RN-06)."""
        pagina = crear_comprobante_html(self.validacion)
        for dato in [folio_fiscal(3), "COMPUTO PRUEBA SA DE CV", "CPR010101CD2",
                     "$3,480.00", "✖ Cancelada", "05/11/2026", "auxiliar",
                     "Instituto Tecnológico de Matehuala"]:
            with self.subTest(dato=dato):
                self.assertIn(dato, pagina)

    def test_avisa_que_es_simulado(self):
        """El comprobante aclara que es un prototipo sin validez fiscal."""
        self.assertIn("no tiene validez fiscal", crear_comprobante_html(self.validacion))

    def test_no_se_rompe_con_datos_raros(self):
        """Si un XML trae código HTML en el nombre, se muestra como texto y no se ejecuta."""
        validacion = {**self.validacion, "nombre_emisor": "<script>alert(1)</script>"}
        pagina = crear_comprobante_html(validacion)
        self.assertNotIn("<script>", pagina)
        self.assertIn("&lt;script&gt;", pagina)

    def test_nombre_del_archivo(self):
        """El archivo se llama comprobante_<folio>_<número>.html."""
        nombre = nombre_archivo_comprobante(self.validacion)
        self.assertEqual(nombre, f"comprobante_0003_{self.validacion['id']}.html")


if __name__ == "__main__":
    unittest.main()
