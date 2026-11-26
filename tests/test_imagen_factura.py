"""
Pruebas de imagen_factura.py (la factura "impresa" en imagen PNG)

Cómo correrlas (en la terminal, desde la carpeta del proyecto):
    python -m unittest discover tests -v
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generar_facturas import FACTURAS_PRUEBA, crear_xml, folio_fiscal, generar_facturas
from imagen_factura import (
    ALTO,
    ANCHO,
    BLANCO,
    crear_imagen_desde_xml,
    generar_imagenes,
    texto_qr,
)
from lector_xml import leer_factura


class TestImagenFactura(unittest.TestCase):

    def setUp(self):
        # Datos de la factura 3 (cancelada), tal como los lee el lector de XML.
        self.datos = leer_factura(crear_xml(FACTURAS_PRUEBA[2]))

    def test_el_qr_trae_folio_rfc_y_total(self):
        """El texto del QR tiene el folio, los dos RFC y el total, como en el SAT."""
        texto = texto_qr(self.datos)
        self.assertIn(f"id={folio_fiscal(3)}", texto)
        self.assertIn("re=CPR010101CD2", texto)
        self.assertIn("rr=ITM000101BB2", texto)
        self.assertIn("tt=3480.00", texto)

    def test_la_imagen_tiene_el_tamano_correcto(self):
        imagen = crear_imagen_desde_xml(crear_xml(FACTURAS_PRUEBA[2]))
        self.assertEqual(imagen.size, (ANCHO, ALTO))
        self.assertEqual(imagen.mode, "RGB")

    def test_el_qr_esta_dibujado(self):
        """En la zona del QR hay pixeles oscuros (no está en blanco)."""
        imagen = crear_imagen_desde_xml(crear_xml(FACTURAS_PRUEBA[2]))
        zona_qr = imagen.crop((40, 990, 300, 1250))
        oscuros = sum(1 for pixel in zona_qr.getdata() if pixel != BLANCO)
        self.assertGreater(oscuros, 5000)

    def test_crea_un_png_por_cada_xml(self):
        """Por cada factura XML se crea su imagen PNG con el mismo nombre."""
        with tempfile.TemporaryDirectory() as carpeta:
            generar_facturas(Path(carpeta))
            rutas = generar_imagenes([Path(carpeta)])
            self.assertEqual(len(rutas), 10)
            self.assertTrue(all(ruta.exists() for ruta in rutas))
            self.assertEqual(rutas[0].name, "factura_01.png")


if __name__ == "__main__":
    unittest.main()
