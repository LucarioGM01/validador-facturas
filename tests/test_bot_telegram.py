"""
Pruebas del bot de Telegram (bot_telegram.py).

NO se conectan a Telegram: unittest.mock reemplaza las llamadas a internet.

Cómo correrlas:
    python -m unittest discover tests -v
"""

import os
import sys
import tempfile
import time
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


@mock.patch("bot_telegram.INTERVALO_EDICION", 0)  # editar en cada cambio, para contarlos
@mock.patch("bot_telegram.avisos.editar_telegram")  # no editar mensajes de verdad
@mock.patch("bot_telegram.enviar")
@mock.patch("bot_telegram.llamar")
class TestBot(unittest.TestCase):

    def test_boton_validar_prueba_manda_registro_con_menu(self, llamar, enviar, editar):
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

    def test_reiniciar_pide_confirmacion(self, llamar, enviar, editar):
        bot_telegram.atender_update(boton("reiniciar"), CONFIG)
        self.assertEqual(enviar.call_args.args[2], bot_telegram.CONFIRMAR_REINICIO)

    def test_resumen_del_mes(self, llamar, enviar, editar):
        bot_telegram.atender_update(boton("resumen_mes"), CONFIG)
        self.assertIn("📊 Resumen de", enviar.call_args.args[1])

    def test_chat_desconocido_no_puede_usar_botones(self, llamar, enviar, editar):
        with mock.patch("bot_telegram.atender_boton") as atender_boton:
            bot_telegram.atender_update(boton("reiniciar_si", chat_id=111), CONFIG)
        atender_boton.assert_not_called()
        self.assertEqual(llamar.call_args.args[2]["text"], "Este bot es privado.")

    def test_chat_desconocido_no_puede_mandar_facturas(self, llamar, enviar, editar):
        with mock.patch("bot_telegram.validar_y_registrar") as validar:
            bot_telegram.atender_update(
                mensaje(chat_id=111, document={"file_id": "x", "file_name": "f.xml"}), CONFIG)
        validar.assert_not_called()
        enviar.assert_not_called()

    def test_texto_muestra_el_menu(self, llamar, enviar, editar):
        bot_telegram.atender_update(mensaje(text="/start"), CONFIG)
        self.assertEqual(enviar.call_args.args[2], bot_telegram.MENU)

    def test_archivo_xml_se_valida(self, llamar, enviar, editar):
        xml = crear_xml(FACTURAS_PRUEBA[0]).encode("utf-8")
        with mock.patch("bot_telegram.descargar_archivo", return_value=xml), \
             mock.patch("bot_telegram.validar_y_registrar") as validar:
            bot_telegram.atender_update(
                mensaje(document={"file_id": "x", "file_name": "factura_01.xml",
                                  "file_size": 900}), CONFIG)
        validar.assert_called_once_with(CONFIG, [("factura_01.xml", xml)])

    def test_pdf_se_rechaza(self, llamar, enviar, editar):
        with mock.patch("bot_telegram.validar_y_registrar") as validar:
            bot_telegram.atender_update(
                mensaje(document={"file_id": "x", "file_name": "factura.pdf"}), CONFIG)
        validar.assert_not_called()
        self.assertIn("no es una factura que pueda leer", enviar.call_args.args[1])


    def test_validar_edita_un_mensaje_en_vivo(self, llamar, enviar, editar):
        """Se manda UN mensaje y después se edita con cada paso (no llena el chat)."""
        enviar.return_value = {"enviado": True, "detalle": "", "mensaje_id": 77}
        archivos = [("f1.xml", crear_xml(FACTURAS_PRUEBA[0]).encode()),
                    ("f3.xml", crear_xml(FACTURAS_PRUEBA[2]).encode())]
        with mock.patch("procesar_lote.avisos.enviar_telegram") as enviar_telegram:
            enviar_telegram.return_value = {"enviado": True, "detalle": ""}
            bot_telegram.validar_y_registrar(CONFIG, archivos)
        self.assertEqual(enviar.call_count, 1)  # el mensaje en vivo se manda una sola vez
        self.assertIn("Llegaron 2 facturas", enviar.call_args.args[1])
        self.assertGreater(editar.call_count, 5)  # y luego se edita con cada paso
        ultimo_texto, mensaje_id = editar.call_args.args[:2]
        self.assertEqual(mensaje_id, 77)
        self.assertIn("Validadas: 2 de 2", ultimo_texto)
        self.assertIn("Por qué: Cancelada", ultimo_texto)

    def test_boton_simular_llegada_deja_facturas_en_la_bandeja(self, llamar, enviar, editar):
        with tempfile.TemporaryDirectory() as carpeta, \
             mock.patch("bot_telegram.CARPETA_BANDEJA", Path(carpeta)):
            bot_telegram.atender_update(boton("simular_llegada"), CONFIG)
            self.assertEqual(len(list(Path(carpeta).glob("*.xml"))), 10)


@mock.patch("bot_telegram.avisos.editar_telegram")
@mock.patch("bot_telegram.enviar")
class TestMensajeEnVivo(unittest.TestCase):
    """El mensaje en vivo no espera ni se edita más de una vez por segundo."""

    def preparar(self):
        progreso = bot_telegram.Progreso("prueba", 1)
        en_vivo = bot_telegram.MensajeEnVivo(CONFIG)
        en_vivo.mensaje_id = 5  # ya se mandó el primer mensaje
        progreso.empezar_factura("a.png")
        return progreso, en_vivo

    def test_cambios_muy_seguidos_se_juntan_en_una_edicion(self, enviar, editar):
        progreso, en_vivo = self.preparar()
        en_vivo.mostrar(progreso)  # primera edición
        progreso.paso("✔ XML leído")
        en_vivo.mostrar(progreso)  # muy seguido: se salta
        progreso.paso("✔ Folio nuevo")
        en_vivo.mostrar(progreso)  # también
        self.assertEqual(editar.call_count, 1)

    def test_el_paso_lento_de_la_ia_y_el_final_siempre_se_muestran(self, enviar, editar):
        progreso, en_vivo = self.preparar()
        en_vivo.mostrar(progreso)
        progreso.paso("⏳ Leyendo el texto de la factura con la IA (Gemini)…")
        en_vivo.mostrar(progreso)
        self.assertEqual(editar.call_count, 2)
        progreso.terminar()
        en_vivo.mostrar(progreso)
        self.assertEqual(editar.call_count, 3)


@mock.patch("bot_telegram.INTERVALO_EDICION", 0)
@mock.patch("bot_telegram.avisos.editar_telegram")
@mock.patch("bot_telegram.enviar")
class TestBandeja(unittest.TestCase):
    """El bot vigila la carpeta bandeja_entrada y valida solo lo que llegue."""

    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.carpeta = Path(self.temporal.name)
        self.addCleanup(self.temporal.cleanup)

    def dejar(self, nombre, contenido, hace_segundos=10):
        """Deja un archivo en la bandeja, con la antigüedad que se pida."""
        ruta = self.carpeta / nombre
        ruta.write_bytes(contenido)
        antes = time.time() - hace_segundos
        os.utime(ruta, (antes, antes))
        return ruta

    def test_factura_que_llega_se_valida_y_pasa_a_procesadas(self, enviar, editar):
        self.dejar("factura_01.xml", crear_xml(FACTURAS_PRUEBA[0]).encode())
        with mock.patch("procesar_lote.avisos.enviar_telegram") as enviar_telegram:
            enviar_telegram.return_value = {"enviado": True, "detalle": ""}
            llegaron = bot_telegram.revisar_bandeja(CONFIG, self.carpeta)
        self.assertEqual(llegaron, 1)
        self.assertFalse((self.carpeta / "factura_01.xml").exists())
        self.assertTrue((self.carpeta / "procesadas" / "factura_01.xml").exists())
        self.assertIn("Origen: carpeta bandeja_entrada", enviar_telegram.call_args.args[0])

    def test_archivo_que_todavia_se_copia_se_deja_para_despues(self, enviar, editar):
        self.dejar("factura_01.xml", crear_xml(FACTURAS_PRUEBA[0]).encode(), hace_segundos=0)
        self.assertEqual(bot_telegram.revisar_bandeja(CONFIG, self.carpeta), 0)
        self.assertTrue((self.carpeta / "factura_01.xml").exists())

    def test_pdf_se_rechaza_y_se_avisa(self, enviar, editar):
        self.dejar("factura.pdf", b"%PDF-1.4")
        self.assertEqual(bot_telegram.revisar_bandeja(CONFIG, self.carpeta), 0)
        self.assertTrue((self.carpeta / "rechazadas" / "factura.pdf").exists())
        self.assertIn("no es una factura que pueda leer", enviar.call_args.args[1])

    def test_bandeja_vacia_o_que_no_existe_no_hace_nada(self, enviar, editar):
        self.assertEqual(bot_telegram.revisar_bandeja(CONFIG, self.carpeta), 0)
        self.assertEqual(bot_telegram.revisar_bandeja(CONFIG, self.carpeta / "no_existe"), 0)
        enviar.assert_not_called()

    def test_un_error_no_repite_las_facturas_sin_fin(self, enviar, editar):
        self.dejar("factura_01.xml", crear_xml(FACTURAS_PRUEBA[0]).encode())
        with mock.patch("bot_telegram.validar_y_registrar", side_effect=RuntimeError("falla")):
            bot_telegram.revisar_bandeja(CONFIG, self.carpeta)
        self.assertTrue((self.carpeta / "con_error" / "factura_01.xml").exists())

    def test_archivos_ocultos_se_ignoran(self, enviar, editar):
        self.dejar(".~lock.factura.xml", b"x")
        self.assertEqual(bot_telegram.archivos_nuevos_en_bandeja(self.carpeta), [])


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
