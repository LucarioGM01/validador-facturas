"""
Pruebas de validador.py (reglas de negocio RN-01 a RN-07)

Cómo correrlas (en la terminal, desde la carpeta del proyecto):
    python -m unittest discover tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import base_datos
from generar_facturas import FACTURAS_PRUEBA, crear_xml, folio_fiscal
from lector_xml import MENSAJE_INVALIDA
from validador import (
    ARCHIVO_INVALIDO,
    CANCELADA,
    NO_ENCONTRADA,
    RECEPTOR_INCORRECTO,
    VIGENTE,
    consultar_estado,
    registrar_factura_nueva,
    validar_factura,
)


def xml_de(numero):
    """Ayudante: el XML de la factura de prueba con ese número (1 a 10)."""
    return crear_xml(FACTURAS_PRUEBA[numero - 1])


def contar_validaciones(conexion):
    """Ayudante: cuántos comprobantes hay guardados en la base de datos."""
    return conexion.execute("SELECT COUNT(*) FROM validaciones").fetchone()[0]


class TestConsultarEstado(unittest.TestCase):
    """El SAT simulado (CSV) responde el estado correcto."""

    def test_vigente(self):
        """Un folio vigente regresa Vigente y sin fecha de cancelación."""
        sat = consultar_estado(folio_fiscal(1))
        self.assertEqual(sat["estado"], VIGENTE)
        self.assertEqual(sat["fecha_cancelacion"], "")

    def test_cancelada_con_fecha(self):
        """Un folio cancelado regresa Cancelada y su fecha de cancelación."""
        sat = consultar_estado(folio_fiscal(3))
        self.assertEqual(sat["estado"], CANCELADA)
        self.assertEqual(sat["fecha_cancelacion"], "2026-11-05")

    def test_folio_que_no_existe(self):
        """Un folio que no está en el CSV regresa No encontrada."""
        sat = consultar_estado("AAAAAAAA-0000-4000-8000-000000000099")
        self.assertEqual(sat["estado"], NO_ENCONTRADA)


class TestValidarFactura(unittest.TestCase):
    """Validación completa de una factura, con base de datos en memoria."""

    def setUp(self):
        # setUp corre ANTES de cada prueba: base nueva y vacía cada vez,
        # y en memoria, para no tocar el archivo validador.db real.
        self.conexion = base_datos.conectar(":memory:")

    def tearDown(self):
        # tearDown corre DESPUÉS de cada prueba.
        self.conexion.close()

    def validar(self, numero, usuario="auxiliar"):
        """Ayudante: valida la factura de prueba con ese número."""
        return validar_factura(self.conexion, xml_de(numero), usuario, f"factura_{numero:02d}.xml")

    def test_estado_correcto_de_las_10_facturas(self):
        """Las 10 facturas de prueba dan el resultado esperado de la tabla."""
        for factura in FACTURAS_PRUEBA:
            with self.subTest(factura=factura["numero"]):
                resultado = self.validar(factura["numero"])
                self.assertEqual(resultado["estado"], factura["esperado"])

    def test_solo_vigente_se_puede_pagar(self):
        """RN-01: solo la vigente con receptor correcto se puede pagar."""
        self.assertTrue(self.validar(1)["puede_pagarse"])   # vigente
        self.assertFalse(self.validar(3)["puede_pagarse"])  # cancelada
        self.assertFalse(self.validar(8)["puede_pagarse"])  # receptor incorrecto

    def test_cancelada_avisa_al_jefe(self):
        """RN-02: la cancelada guarda su fecha y pide avisar al jefe; la vigente no."""
        cancelada = self.validar(3)
        self.assertTrue(cancelada["avisar_jefe"])
        self.assertEqual(cancelada["fecha_cancelacion"], "2026-11-05")
        self.assertIn("05/11/2026", cancelada["mensaje"])
        self.assertFalse(self.validar(1)["avisar_jefe"])

    def test_cancelada_se_conserva_en_historial(self):
        """RN-03: la cancelada queda en el historial marcada como cancelada."""
        self.validar(3)
        canceladas = base_datos.buscar_facturas(self.conexion, estado=CANCELADA)
        self.assertEqual([f["uuid"] for f in canceladas], [folio_fiscal(3)])

    def test_receptor_incorrecto(self):
        """RN-05: la factura 8 no está a nombre del Tecnológico."""
        resultado = self.validar(8)
        self.assertEqual(resultado["estado"], RECEPTOR_INCORRECTO)
        self.assertIn("XYZ000101ZZ9", resultado["mensaje"])

    def test_guarda_fecha_hora_y_usuario(self):
        """RN-06: el comprobante guarda fecha, hora, usuario y tiempo."""
        resultado = self.validar(1, usuario="auxiliar")
        comprobante = base_datos.obtener_validacion(self.conexion, resultado["id_validacion"])
        self.assertEqual(comprobante["usuario"], "auxiliar")
        self.assertEqual(comprobante["estado"], VIGENTE)
        self.assertEqual(comprobante["fecha_hora"][:10], base_datos.ahora()[:10])  # hoy
        self.assertGreaterEqual(comprobante["segundos"], 0)

    def test_factura_repetida(self):
        """RN-07: una vigente cargada otra vez avisa «Ya validada el...» y no se guarda doble."""
        primera = self.validar(1)
        segunda = self.validar(1)
        self.assertFalse(primera["es_repetida"])
        self.assertTrue(segunda["es_repetida"])
        self.assertIn("Ya validada el", segunda["mensaje"])
        self.assertIsNone(segunda["id_validacion"])
        self.assertEqual(contar_validaciones(self.conexion), 1)

    def test_cancelada_repetida_no_avisa_dos_veces(self):
        """Si el aviso ya le llegó al jefe, cargar otra vez la cancelada no lo repite."""
        self.assertTrue(self.validar(3)["avisar_jefe"])
        base_datos.marcar_aviso_enviado(self.conexion, folio_fiscal(3))
        self.assertFalse(self.validar(3)["avisar_jefe"])

    def test_reintenta_el_aviso_si_no_se_envio(self):
        """Si el aviso NO se pudo enviar (sin internet o sin Telegram), se reintenta."""
        self.assertTrue(self.validar(3)["avisar_jefe"])
        self.assertTrue(self.validar(3)["avisar_jefe"])

    def test_archivo_invalido(self):
        """Un archivo que no es factura muestra el mensaje claro y no guarda nada."""
        resultado = validar_factura(self.conexion, b"no soy una factura", "auxiliar", "foto.xml")
        self.assertEqual(resultado["estado"], ARCHIVO_INVALIDO)
        self.assertIn(MENSAJE_INVALIDA, resultado["mensaje"])
        self.assertEqual(contar_validaciones(self.conexion), 0)

    def test_folio_no_encontrado(self):
        """Una factura bien hecha cuyo folio no está en el SAT simulado."""
        xml = xml_de(1).replace(folio_fiscal(1), "AAAAAAAA-0000-4000-8000-000000000099")
        resultado = validar_factura(self.conexion, xml, "auxiliar")
        self.assertEqual(resultado["estado"], NO_ENCONTRADA)
        self.assertFalse(resultado["puede_pagarse"])

    def test_validacion_rapida(self):
        """Validar una factura tarda 10 segundos o menos (criterio de aceptación)."""
        self.assertLessEqual(self.validar(1)["segundos"], 10)


class TestFacturaNueva(unittest.TestCase):
    """RN-04: la factura nueva se valida igual y queda ligada a la cancelada."""

    def setUp(self):
        self.conexion = base_datos.conectar(":memory:")
        validar_factura(self.conexion, xml_de(3), "auxiliar")  # la 3 sale cancelada
        self.uuid_cancelada = folio_fiscal(3)

    def tearDown(self):
        self.conexion.close()

    def test_liga_la_factura_nueva_vigente(self):
        """Si la nueva sale vigente, queda ligada a la cancelada."""
        self.assertTrue(base_datos.marcar_nueva_solicitada(self.conexion, self.uuid_cancelada))
        resultado = registrar_factura_nueva(self.conexion, self.uuid_cancelada, xml_de(10), "jefe")
        self.assertTrue(resultado["ligada"])
        cancelada = base_datos.obtener_factura(self.conexion, self.uuid_cancelada)
        self.assertEqual(cancelada["uuid_reemplazo"], folio_fiscal(10))
        self.assertEqual(cancelada["nueva_solicitada"], 1)

    def test_no_liga_si_la_nueva_no_es_vigente(self):
        """Si la nueva también sale cancelada, no se liga."""
        resultado = registrar_factura_nueva(self.conexion, self.uuid_cancelada, xml_de(6), "jefe")
        self.assertFalse(resultado["ligada"])
        self.assertIn("no se ligó", resultado["mensaje"])
        cancelada = base_datos.obtener_factura(self.conexion, self.uuid_cancelada)
        self.assertIsNone(cancelada["uuid_reemplazo"])

    def test_no_liga_la_misma_factura(self):
        """Subir la misma factura cancelada como "nueva" no se liga."""
        resultado = registrar_factura_nueva(self.conexion, self.uuid_cancelada, xml_de(3), "jefe")
        self.assertFalse(resultado["ligada"])

    def test_solo_se_liga_a_canceladas(self):
        """No se puede ligar una factura nueva a una que está vigente."""
        validar_factura(self.conexion, xml_de(1), "auxiliar")
        with self.assertRaises(ValueError):
            registrar_factura_nueva(self.conexion, folio_fiscal(1), xml_de(10), "jefe")


if __name__ == "__main__":
    unittest.main()
