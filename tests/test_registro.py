"""
Pruebas del REGISTRO de validación (avisos.crear_mensaje_registro), de los
botones en enviar_telegram y de procesar_lote.validar_lote.

NO se conectan a Telegram: unittest.mock "finge" las respuestas de internet.

Cómo correrlas:
    python -m unittest discover tests -v
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import avisos
import base_datos
import procesar_lote
from generar_facturas import FACTURAS_PRUEBA, crear_xml
from validador import ARCHIVO_INVALIDO, validar_factura

TOKEN_FALSO = "123456789:ABCdef_token-de-prueba"
CHAT_FALSO = "987654321"
FECHA = "2026-11-27T10:30:00"


def respuesta_ok():
    respuesta = mock.Mock()
    respuesta.status_code = 200
    respuesta.json.return_value = {"ok": True}
    return respuesta


def validar(numeros):
    """Valida las facturas de prueba indicadas (1 a 10) en una base temporal."""
    conexion = base_datos.conectar(":memory:")
    resultados = [validar_factura(conexion, crear_xml(FACTURAS_PRUEBA[n - 1]), "auxiliar",
                                  f"factura_{n:02d}.xml") for n in numeros]
    conexion.close()
    return resultados


class TestMensajeRegistro(unittest.TestCase):

    def test_todas_correctas(self):
        """Si todas son vigentes, el registro lo dice en la primera línea."""
        mensaje = avisos.crear_mensaje_registro(validar([1, 2]), "auxiliar", FECHA)
        primera_linea = mensaje.splitlines()[0]
        self.assertIn("✅", primera_linea)
        self.assertIn("las 2 facturas están CORRECTAS", primera_linea)
        self.assertNotIn("Requieren atención", mensaje)
        self.assertIn("✔ Vigente: 2", mensaje)

    def test_alguna_requiere_atencion(self):
        """Con una cancelada y una de receptor incorrecto: desglose y datos de cada una."""
        mensaje = avisos.crear_mensaje_registro(validar([1, 3, 8]), "auxiliar", FECHA,
                                                origen="bot de Telegram")
        self.assertIn("⚠️ Registro de validación: 2 de 3 REQUIEREN ATENCIÓN",
                      mensaje.splitlines()[0])
        for dato in ["✖ Cancelada: 1", "⚠ Receptor incorrecto: 1", "✔ Vigente: 1",
                     "…0003", "COMPUTO PRUEBA SA DE CV", "CPR010101CD2", "$3,480.00",
                     "…0008", "XYZ000101ZZ9", "Origen: bot de Telegram", "auxiliar",
                     "27/11/2026 a las 10:30", "Correctas (se pueden pagar):"]:
            with self.subTest(dato=dato):
                self.assertIn(dato, mensaje)

    def test_archivo_invalido_requiere_atencion(self):
        invalida = procesar_lote.resultado_imagen_invalida("foto.jpg", "sin QR")
        mensaje = avisos.crear_mensaje_registro([invalida], "auxiliar", FECHA)
        self.assertIn("1 de 1 REQUIEREN ATENCIÓN", mensaje)
        self.assertIn("Archivo foto.jpg", mensaje)

    def test_repetidas_cuentan_como_correctas(self):
        """RN-07: una factura ya validada antes no es una incidencia."""
        conexion = base_datos.conectar(":memory:")
        validar_factura(conexion, crear_xml(FACTURAS_PRUEBA[0]), "auxiliar")
        repetida = validar_factura(conexion, crear_xml(FACTURAS_PRUEBA[0]), "auxiliar")
        conexion.close()
        mensaje = avisos.crear_mensaje_registro([repetida], "auxiliar", FECHA)
        self.assertIn("CORRECTAS", mensaje)
        self.assertIn("1 ya validada(s) antes", mensaje)

    def test_mensaje_largo_se_recorta(self):
        """Telegram no acepta más de 4096 letras."""
        muchas = validar(range(1, 11)) * 10
        mensaje = avisos.crear_mensaje_registro(muchas, "auxiliar", FECHA)
        self.assertLessEqual(len(mensaje), 4096)
        self.assertIn("mensaje recortado", mensaje)


class TestBotones(unittest.TestCase):

    @mock.patch("avisos.requests.post")
    def test_manda_teclado_inline(self, post):
        post.return_value = respuesta_ok()
        botones = [[{"text": "Validar", "callback_data": "validar_prueba"}]]
        avisos.enviar_telegram("hola", TOKEN_FALSO, CHAT_FALSO, botones)
        cuerpo = post.call_args.kwargs["json"]
        self.assertEqual(cuerpo["reply_markup"], {"inline_keyboard": botones})

    @mock.patch("avisos.requests.post")
    def test_sin_botones_no_manda_teclado(self, post):
        post.return_value = respuesta_ok()
        avisos.enviar_telegram("hola", TOKEN_FALSO, CHAT_FALSO)
        self.assertNotIn("reply_markup", post.call_args.kwargs["json"])


class TestValidarLote(unittest.TestCase):

    @mock.patch("avisos.requests.post")
    def test_manda_aviso_de_cancelada_y_registro_al_final(self, post):
        post.return_value = respuesta_ok()
        conexion = base_datos.conectar(":memory:")
        archivos = [(f"factura_{n:02d}.xml", crear_xml(FACTURAS_PRUEBA[n - 1])) for n in (1, 3)]
        resultados, registro = procesar_lote.validar_lote(
            conexion, archivos, "auxiliar", token=TOKEN_FALSO, chat_id=CHAT_FALSO)

        self.assertEqual([r["estado"] for r in resultados], ["Vigente", "Cancelada"])
        self.assertTrue(registro["enviado"])
        textos = [llamada.kwargs["json"]["text"] for llamada in post.call_args_list]
        self.assertEqual(len(textos), 2)                      # aviso RN-02 + registro
        self.assertIn("Factura CANCELADA", textos[0])
        self.assertIn("REQUIEREN ATENCIÓN", textos[1])
        self.assertEqual(base_datos.obtener_factura(conexion, resultados[1]["uuid"])["aviso_enviado"], 1)
        conexion.close()

    @mock.patch("avisos.requests.post")
    def test_sin_telegram_valida_igual(self, post):
        conexion = base_datos.conectar(":memory:")
        resultados, registro = procesar_lote.validar_lote(
            conexion, [("factura_01.xml", crear_xml(FACTURAS_PRUEBA[0]))], "auxiliar")
        conexion.close()
        self.assertEqual(resultados[0]["estado"], "Vigente")
        self.assertFalse(registro["enviado"])
        post.assert_not_called()

    @mock.patch("avisos.requests.post")
    def test_imagen_ilegible_es_archivo_invalido(self, post):
        conexion = base_datos.conectar(":memory:")
        resultados, _ = procesar_lote.validar_lote(conexion, [("foto.png", b"no es imagen")],
                                                   "auxiliar")
        conexion.close()
        self.assertEqual(resultados[0]["estado"], ARCHIVO_INVALIDO)


if __name__ == "__main__":
    unittest.main()
