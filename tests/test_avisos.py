"""
Pruebas de avisos.py (aviso al jefe por Telegram, RN-02)

Estas pruebas NO se conectan a Telegram: usan unittest.mock para "fingir" la
respuesta de internet. Así se pueden correr sin token y sin conexión.

Cómo correrlas (en la terminal, desde la carpeta del proyecto):
    python -m unittest discover tests -v
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

import avisos
import base_datos
from generar_facturas import FACTURAS_PRUEBA, crear_xml
from validador import validar_factura

# Datos INVENTADOS con el formato correcto (no son de ningún bot real).
TOKEN_FALSO = "123456789:ABCdef_token-de-prueba"
CHAT_FALSO = "987654321"


def respuesta_falsa(codigo, datos):
    """Ayudante: una respuesta de internet inventada, como la que daría Telegram."""
    respuesta = mock.Mock()
    respuesta.status_code = codigo
    respuesta.json.return_value = datos
    return respuesta


class TestMensaje(unittest.TestCase):

    def test_mensaje_de_cancelada_trae_los_datos_del_proveedor(self):
        """El aviso trae folio, RFC y nombre del proveedor, total y fecha de cancelación (RN-02)."""
        conexion = base_datos.conectar(":memory:")
        resultado = validar_factura(conexion, crear_xml(FACTURAS_PRUEBA[2]), "auxiliar")
        conexion.close()
        mensaje = avisos.crear_mensaje_cancelada(resultado, "auxiliar", "2026-11-18T21:30:00")
        for dato in ["CANCELADA", "…0003", "COMPUTO PRUEBA SA DE CV", "CPR010101CD2",
                     "$3,480.00", "05/11/2026", "auxiliar", "18/11/2026 a las 21:30",
                     "nueva factura"]:
            with self.subTest(dato=dato):
                self.assertIn(dato, mensaje)


class TestConfiguracion(unittest.TestCase):

    def test_sin_token(self):
        listo, motivo = avisos.revisar_configuracion("", CHAT_FALSO)
        self.assertFalse(listo)
        self.assertIn("TELEGRAM_TOKEN", motivo)

    def test_token_de_ejemplo_cuenta_como_vacio(self):
        listo, _ = avisos.revisar_configuracion("pega_aqui_tu_token", CHAT_FALSO)
        self.assertFalse(listo)

    def test_chat_id_que_no_es_numero(self):
        listo, motivo = avisos.revisar_configuracion(TOKEN_FALSO, "mi chat")
        self.assertFalse(listo)
        self.assertIn("número", motivo)

    def test_configuracion_correcta(self):
        self.assertEqual(avisos.revisar_configuracion(TOKEN_FALSO, CHAT_FALSO), (True, ""))


class TestEnviar(unittest.TestCase):

    @mock.patch("avisos.requests.post")
    def test_sin_token_no_falla_ni_se_conecta(self, post):
        """Sin token configurado: no truena, no se conecta y explica qué falta."""
        respuesta = avisos.enviar_telegram("hola", "", "")
        self.assertFalse(respuesta["enviado"])
        self.assertIn("no está configurado", respuesta["detalle"])
        post.assert_not_called()

    @mock.patch("avisos.requests.post")
    def test_envio_correcto(self, post):
        """Con token y chat_id, manda el texto al método sendMessage de Telegram."""
        post.return_value = respuesta_falsa(200, {"ok": True})
        respuesta = avisos.enviar_telegram("Factura cancelada", TOKEN_FALSO, CHAT_FALSO)
        self.assertTrue(respuesta["enviado"])
        url = post.call_args.args[0]
        self.assertTrue(url.endswith("/sendMessage"))
        self.assertEqual(post.call_args.kwargs["json"],
                         {"chat_id": CHAT_FALSO, "text": "Factura cancelada"})

    @mock.patch("avisos.requests.post")
    def test_token_equivocado(self, post):
        post.return_value = respuesta_falsa(401, {"ok": False, "description": "Unauthorized"})
        respuesta = avisos.enviar_telegram("hola", TOKEN_FALSO, CHAT_FALSO)
        self.assertFalse(respuesta["enviado"])
        self.assertIn("token", respuesta["detalle"])

    @mock.patch("avisos.requests.post")
    def test_chat_que_no_existe(self, post):
        post.return_value = respuesta_falsa(400, {"ok": False,
                                                  "description": "Bad Request: chat not found"})
        respuesta = avisos.enviar_telegram("hola", TOKEN_FALSO, CHAT_FALSO)
        self.assertFalse(respuesta["enviado"])
        self.assertIn("TELEGRAM_CHAT_ID", respuesta["detalle"])

    @mock.patch("avisos.requests.post")
    def test_sin_internet_no_muestra_el_token(self, post):
        """Sin conexión: no truena y el mensaje de error nunca incluye el token."""
        post.side_effect = requests.ConnectionError(f"fallo al abrir /bot{TOKEN_FALSO}/sendMessage")
        respuesta = avisos.enviar_telegram("hola", TOKEN_FALSO, CHAT_FALSO)
        self.assertFalse(respuesta["enviado"])
        self.assertIn("conexión", respuesta["detalle"])
        self.assertNotIn(TOKEN_FALSO, respuesta["detalle"])


if __name__ == "__main__":
    unittest.main()
