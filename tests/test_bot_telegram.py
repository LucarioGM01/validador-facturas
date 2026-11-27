"""
Pruebas del bot de Telegram (bot_telegram.py).

NO se conectan a Telegram: unittest.mock reemplaza las llamadas a internet.

Cómo correrlas:
    python -m unittest discover tests -v
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bot_telegram
from generar_facturas import FACTURAS_PRUEBA, crear_xml

CONFIG = {
    "token": "123456789:ABCdef_token-de-prueba",
    "chat_id": "987654321",
    "clave_gemini": "",
    "ruta_bd": ":memory:",  # base temporal: no toca validador.db
}


def boton(data, chat_id=987654321):
    """Actualización de Telegram de alguien que tocó un botón."""
    return {"update_id": 1, "callback_query": {
        "id": "abc", "data": data, "message": {"chat": {"id": chat_id}}}}


def mensaje(chat_id=987654321, **extra):
    """Actualización de Telegram con un mensaje."""
    return {"update_id": 1, "message": {"chat": {"id": chat_id}, **extra}}


@mock.patch("bot_telegram.enviar")
@mock.patch("bot_telegram.llamar")
class TestBot(unittest.TestCase):

    def test_boton_validar_prueba_manda_registro_con_menu(self, llamar, enviar):
        with mock.patch("procesar_lote.avisos.enviar_telegram") as enviar_telegram:
            enviar_telegram.return_value = {"enviado": True, "detalle": ""}
            bot_telegram.atender_update(boton("validar_prueba"), CONFIG)

        # Se contestó el callback para que el botón deje de "cargar".
        self.assertEqual(llamar.call_args_list[0].args[1], "answerCallbackQuery")
        # El último mensaje es el registro, con el menú abajo.
        texto, _, _, botones = enviar_telegram.call_args_list[-1].args
        self.assertIn("REQUIEREN ATENCIÓN", texto)  # las de prueba traen 2 canceladas
        self.assertIn("Origen: bot de Telegram", texto)
        self.assertEqual(botones, bot_telegram.MENU)

    def test_reiniciar_pide_confirmacion(self, llamar, enviar):
        bot_telegram.atender_update(boton("reiniciar"), CONFIG)
        self.assertEqual(enviar.call_args.args[2], bot_telegram.CONFIRMAR_REINICIO)

    def test_resumen_del_mes(self, llamar, enviar):
        bot_telegram.atender_update(boton("resumen_mes"), CONFIG)
        self.assertIn("📊 Resumen de", enviar.call_args.args[1])

    def test_chat_desconocido_no_puede_usar_botones(self, llamar, enviar):
        with mock.patch("bot_telegram.atender_boton") as atender_boton:
            bot_telegram.atender_update(boton("reiniciar_si", chat_id=111), CONFIG)
        atender_boton.assert_not_called()
        self.assertEqual(llamar.call_args.args[2]["text"], "Este bot es privado.")

    def test_chat_desconocido_no_puede_mandar_facturas(self, llamar, enviar):
        with mock.patch("bot_telegram.validar_y_registrar") as validar:
            bot_telegram.atender_update(
                mensaje(chat_id=111, document={"file_id": "x", "file_name": "f.xml"}), CONFIG)
        validar.assert_not_called()
        enviar.assert_not_called()

    def test_texto_muestra_el_menu(self, llamar, enviar):
        bot_telegram.atender_update(mensaje(text="/start"), CONFIG)
        self.assertEqual(enviar.call_args.args[2], bot_telegram.MENU)

    def test_archivo_xml_se_valida(self, llamar, enviar):
        xml = crear_xml(FACTURAS_PRUEBA[0]).encode("utf-8")
        with mock.patch("bot_telegram.descargar_archivo", return_value=xml), \
             mock.patch("bot_telegram.validar_y_registrar") as validar:
            bot_telegram.atender_update(
                mensaje(document={"file_id": "x", "file_name": "factura_01.xml",
                                  "file_size": 900}), CONFIG)
        validar.assert_called_once_with(CONFIG, [("factura_01.xml", xml)])

    def test_pdf_se_rechaza(self, llamar, enviar):
        with mock.patch("bot_telegram.validar_y_registrar") as validar:
            bot_telegram.atender_update(
                mensaje(document={"file_id": "x", "file_name": "factura.pdf"}), CONFIG)
        validar.assert_not_called()
        self.assertIn("no es una factura que pueda leer", enviar.call_args.args[1])


class TestResumen(unittest.TestCase):

    def test_texto_resumen_mes(self):
        resumen = {"validaciones": 10, "vigentes": 7, "canceladas": 2, "receptor_incorrecto": 1,
                   "no_encontradas": 0, "hojas_ahorradas": 10, "segundos_promedio": 0.0004}
        texto = bot_telegram.texto_resumen_mes(resumen, "2026-11")
        for dato in ["noviembre de 2026", "Validaciones: 10", "Vigentes: 7", "Canceladas: 2",
                     "0.40 milisegundos"]:
            with self.subTest(dato=dato):
                self.assertIn(dato, texto)


if __name__ == "__main__":
    unittest.main()
