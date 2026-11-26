"""
Pruebas de comprobante.py (el comprobante digital en imagen PNG)

Cómo correrlas (en la terminal, desde la carpeta del proyecto):
    python -m unittest discover tests -v
"""

import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

import base_datos
from comprobante import (
    ALTO,
    ANCHO,
    AVISO,
    comprobante_png,
    dibujar_comprobante,
    nombre_archivo_comprobante,
    renglones_comprobante,
)
from generar_facturas import FACTURAS_PRUEBA, crear_xml, folio_fiscal
from validador import validar_factura


def comprobante_de(conexion, numero):
    """Ayudante: valida la factura de prueba con ese número y regresa su comprobante."""
    resultado = validar_factura(conexion, crear_xml(FACTURAS_PRUEBA[numero - 1]), "auxiliar")
    return base_datos.obtener_validacion(conexion, resultado["id_validacion"])


class TestComprobante(unittest.TestCase):

    def setUp(self):
        self.conexion = base_datos.conectar(":memory:")
        self.validacion = comprobante_de(self.conexion, 3)  # la 3 sale cancelada

    def tearDown(self):
        self.conexion.close()

    def test_trae_los_datos_de_la_validacion(self):
        """El comprobante trae folio, proveedor, total, fechas y usuario (RN-06)."""
        texto = " ".join(valor for _, valor in renglones_comprobante(self.validacion))
        for dato in [folio_fiscal(3), "COMPUTO PRUEBA SA DE CV", "CPR010101CD2",
                     "$3,480.00", "05/11/2026", "auxiliar"]:
            with self.subTest(dato=dato):
                self.assertIn(dato, texto)

    def test_avisa_que_es_simulado(self):
        """El comprobante aclara que es un prototipo sin validez fiscal."""
        self.assertIn("no tiene validez fiscal", AVISO)

    def test_es_una_imagen_png(self):
        """comprobante_png regresa un archivo PNG del tamaño correcto."""
        contenido = comprobante_png(self.validacion)
        self.assertTrue(contenido.startswith(b"\x89PNG"))
        self.assertEqual(Image.open(io.BytesIO(contenido)).size, (ANCHO, ALTO))

    def test_el_color_cambia_segun_el_estado(self):
        """El recuadro del estado es rojizo si está cancelada y verdoso si está vigente."""
        cancelada = dibujar_comprobante(self.validacion).getpixel((60, 350))
        vigente = dibujar_comprobante(comprobante_de(self.conexion, 1)).getpixel((60, 350))
        self.assertGreater(cancelada[0], cancelada[1])  # más rojo que verde
        self.assertGreater(vigente[1], vigente[0])      # más verde que rojo

    def test_nombre_del_archivo(self):
        """El archivo se llama comprobante_<folio>_<número>.png."""
        nombre = nombre_archivo_comprobante(self.validacion)
        self.assertEqual(nombre, f"comprobante_0003_{self.validacion['id']}.png")


if __name__ == "__main__":
    unittest.main()
