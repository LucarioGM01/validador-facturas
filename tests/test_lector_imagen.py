"""
Pruebas de lector_imagen.py (leer facturas que llegan como imagen)

El código QR se lee de verdad (con OpenCV). Gemini NO se usa de verdad: con
unittest.mock se finge su respuesta, así las pruebas no necesitan internet
ni la clave.

Cómo correrlas (en la terminal, desde la carpeta del proyecto):
    python -m unittest discover tests -v
"""

import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

import base_datos
from generar_facturas import FACTURAS_PRUEBA, crear_xml, folio_fiscal
from imagen_factura import crear_imagen_desde_xml
from lector_imagen import leer_con_gemini, leer_factura_imagen, leer_qr
from lector_xml import FacturaInvalida
from validador import validar_factura

CLAVE_FALSA = "clave-de-prueba"  # inventada: nunca llega a Google porque se finge


def png_de(numero):
    """Ayudante: la imagen PNG (en bytes) de la factura de prueba con ese número."""
    imagen = crear_imagen_desde_xml(crear_xml(FACTURAS_PRUEBA[numero - 1]))
    memoria = io.BytesIO()
    imagen.save(memoria, "PNG")
    return memoria.getvalue()


def respuesta_gemini(datos, codigo=200):
    """Ayudante: una respuesta inventada de Gemini con esos datos en JSON."""
    respuesta = mock.Mock()
    respuesta.status_code = codigo
    respuesta.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": json.dumps(datos)}]}}]
    }
    return respuesta


# Lo que Gemini "leería" en la factura 3.
LECTURA_FACTURA_3 = {
    "uuid": folio_fiscal(3), "rfc_emisor": "CPR010101CD2",
    "nombre_emisor": "COMPUTO PRUEBA SA DE CV", "rfc_receptor": "ITM000101BB2",
    "nombre_receptor": "INSTITUTO TECNOLOGICO MODELO", "total": 3480.0,
    "subtotal": 3000.0, "fecha": "2026-11-04T09:30:00",
    "descripcion": "Teclado y mouse inalámbrico",
}


class TestCodigoQR(unittest.TestCase):

    def test_lee_folio_rfc_y_total_del_qr(self):
        """OpenCV encuentra el QR de la imagen y saca folio, RFC y total."""
        datos = leer_qr(png_de(3))
        self.assertEqual(datos["uuid"], folio_fiscal(3))
        self.assertEqual(datos["rfc_emisor"], "CPR010101CD2")
        self.assertEqual(datos["rfc_receptor"], "ITM000101BB2")
        self.assertEqual(datos["total"], 3480.0)

    def test_imagen_sin_qr(self):
        """Una imagen en blanco no tiene QR."""
        memoria = io.BytesIO()
        Image.new("RGB", (300, 300), (255, 255, 255)).save(memoria, "PNG")
        self.assertIsNone(leer_qr(memoria.getvalue()))

    def test_archivo_que_no_es_imagen(self):
        self.assertIsNone(leer_qr(b"esto no es una imagen"))


class TestGemini(unittest.TestCase):

    @mock.patch("lector_imagen.requests.post")
    def test_si_un_modelo_esta_saturado_prueba_el_siguiente(self, post):
        """Si Google responde 503 (saturado), se intenta con el siguiente modelo."""
        post.side_effect = [respuesta_gemini({}, 503), respuesta_gemini(LECTURA_FACTURA_3)]
        datos, motivo = leer_con_gemini(png_de(3), CLAVE_FALSA)
        self.assertEqual(datos["uuid"], folio_fiscal(3))
        self.assertEqual(motivo, "")
        self.assertEqual(post.call_count, 2)

    @mock.patch("lector_imagen.requests.post")
    def test_clave_equivocada(self, post):
        post.return_value = respuesta_gemini({}, 403)
        datos, motivo = leer_con_gemini(png_de(3), CLAVE_FALSA)
        self.assertIsNone(datos)
        self.assertIn("clave", motivo)

    def test_sin_clave_no_se_conecta(self):
        datos, motivo = leer_con_gemini(png_de(3), "")
        self.assertIsNone(datos)
        self.assertIn("GEMINI_API_KEY", motivo)


class TestLeerFacturaImagen(unittest.TestCase):

    @mock.patch("lector_imagen.requests.post")
    def test_qr_y_gemini_coinciden(self, post):
        """Cuando el QR y Gemini leen lo mismo, la lectura es confiable."""
        post.return_value = respuesta_gemini(LECTURA_FACTURA_3)
        datos = leer_factura_imagen(png_de(3), CLAVE_FALSA)
        self.assertEqual(datos["fuente"], "QR + Gemini")
        self.assertTrue(datos["coinciden"])
        self.assertEqual(datos["nombre_emisor"], "COMPUTO PRUEBA SA DE CV")

    @mock.patch("lector_imagen.requests.post")
    def test_detecta_cuando_no_coinciden(self, post):
        """Si Gemini lee mal el total, se avisa y se usa el total del QR (que es exacto)."""
        post.return_value = respuesta_gemini({**LECTURA_FACTURA_3, "total": 8480.0})
        datos = leer_factura_imagen(png_de(3), CLAVE_FALSA)
        self.assertFalse(datos["coinciden"])
        self.assertEqual(datos["diferencias"], ["total"])
        self.assertEqual(datos["total"], 3480.0)

    def test_sin_clave_usa_solo_el_qr(self):
        """Sin Gemini (sin clave o sin internet) se lee solo el QR."""
        datos = leer_factura_imagen(png_de(3), "")
        self.assertEqual(datos["fuente"], "solo QR")
        self.assertEqual(datos["uuid"], folio_fiscal(3))

    def test_imagen_que_no_se_puede_leer(self):
        """Sin QR y sin IA no hay forma de leerla: sale el mensaje de factura inválida."""
        memoria = io.BytesIO()
        Image.new("RGB", (300, 300), (255, 255, 255)).save(memoria, "PNG")
        with self.assertRaises(FacturaInvalida):
            leer_factura_imagen(memoria.getvalue(), "")


class TestValidarDesdeImagen(unittest.TestCase):

    def test_las_10_imagenes_dan_el_resultado_esperado(self):
        """Una factura leída desde su imagen pasa por las mismas reglas que un XML."""
        conexion = base_datos.conectar(":memory:")
        for factura in FACTURAS_PRUEBA:
            with self.subTest(factura=factura["numero"]):
                datos = leer_factura_imagen(png_de(factura["numero"]), "")
                resultado = validar_factura(conexion, None, "auxiliar", datos=datos)
                self.assertEqual(resultado["estado"], factura["esperado"])
        conexion.close()


if __name__ == "__main__":
    unittest.main()
