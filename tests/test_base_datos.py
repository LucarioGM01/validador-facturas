"""
Pruebas de base_datos.py (usuarios, historial y reporte del mes)

Cómo correrlas (en la terminal, desde la carpeta del proyecto):
    python -m unittest discover tests -v
"""

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import base_datos
from generar_facturas import FACTURAS_PRUEBA, crear_xml, folio_fiscal
from validador import CANCELADA, validar_factura

# Contraseña inventada SOLO para las pruebas. Las de la app irán en secrets.toml.
CLAVE_PRUEBA = "Clave-de-prueba-1"


class TestUsuarios(unittest.TestCase):
    """Inicio de sesión: solo entra quien tiene cuenta y contraseña correcta."""

    def setUp(self):
        self.conexion = base_datos.conectar(":memory:")
        base_datos.crear_usuario(self.conexion, "auxiliar", CLAVE_PRUEBA, "auxiliar", "Auxiliar")

    def tearDown(self):
        self.conexion.close()

    def test_usuario_y_contrasena_correctos(self):
        """Con usuario y contraseña correctos regresa sus datos y su rol."""
        usuario = base_datos.verificar_usuario(self.conexion, "auxiliar", CLAVE_PRUEBA)
        self.assertEqual(usuario["rol"], "auxiliar")

    def test_no_importan_mayusculas_ni_espacios_en_el_usuario(self):
        """«AUXILIAR » se reconoce igual que «auxiliar»."""
        self.assertIsNotNone(base_datos.verificar_usuario(self.conexion, "AUXILIAR ", CLAVE_PRUEBA))

    def test_contrasena_incorrecta(self):
        """Con la contraseña mal no entra."""
        self.assertIsNone(base_datos.verificar_usuario(self.conexion, "auxiliar", "otra-clave"))

    def test_usuario_sin_cuenta_no_entra(self):
        """Un usuario sin cuenta no puede entrar (criterio de aceptación)."""
        self.assertIsNone(base_datos.verificar_usuario(self.conexion, "intruso", CLAVE_PRUEBA))

    def test_no_guarda_la_contrasena_en_texto(self):
        """En la base de datos se guarda el hash, nunca la contraseña tal cual."""
        fila = self.conexion.execute("SELECT * FROM usuarios WHERE usuario = 'auxiliar'").fetchone()
        self.assertNotIn(CLAVE_PRUEBA, tuple(fila))

    def test_rol_invalido(self):
        """Solo existen los roles auxiliar y jefe."""
        with self.assertRaises(ValueError):
            base_datos.crear_usuario(self.conexion, "director", CLAVE_PRUEBA, "director")


class TestActualizarBaseVieja(unittest.TestCase):

    def test_agrega_columnas_nuevas_a_una_base_vieja(self):
        """Una base de datos creada con la versión anterior recibe la columna aviso_enviado."""
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "vieja.db"
            vieja = sqlite3.connect(ruta)
            vieja.execute("CREATE TABLE facturas (uuid TEXT PRIMARY KEY, estado TEXT)")
            vieja.commit()
            vieja.close()

            conexion = base_datos.conectar(ruta)
            columnas = {f["name"] for f in conexion.execute("PRAGMA table_info(facturas)")}
            conexion.close()
        self.assertIn("aviso_enviado", columnas)


class TestHistorialYReporte(unittest.TestCase):
    """Búsquedas del historial y totales del mes, con las 10 facturas validadas."""

    def setUp(self):
        self.conexion = base_datos.conectar(":memory:")
        for factura in FACTURAS_PRUEBA:
            validar_factura(self.conexion, crear_xml(factura), "auxiliar")
        self.mes_actual = base_datos.ahora()[:7]  # por ejemplo "2026-11"

    def tearDown(self):
        self.conexion.close()

    def test_buscar_por_proveedor(self):
        """Buscar «papelería» (con acento y minúsculas) encuentra sus 2 facturas."""
        encontradas = base_datos.buscar_facturas(self.conexion, texto="papelería")
        self.assertEqual(len(encontradas), 2)

    def test_buscar_por_folio(self):
        """Buscar por el final del folio encuentra esa factura."""
        encontradas = base_datos.buscar_facturas(self.conexion, texto="0007")
        self.assertEqual([f["uuid"] for f in encontradas], [folio_fiscal(7)])

    def test_buscar_por_estado(self):
        """Filtrar por Cancelada encuentra las facturas 3 y 6."""
        encontradas = base_datos.buscar_facturas(self.conexion, estado=CANCELADA)
        self.assertEqual(sorted(f["uuid"] for f in encontradas), [folio_fiscal(3), folio_fiscal(6)])

    def test_buscar_por_mes(self):
        """Filtrar por el mes actual da las 10; por un mes viejo, ninguna."""
        self.assertEqual(len(base_datos.buscar_facturas(self.conexion, mes=self.mes_actual)), 10)
        self.assertEqual(base_datos.buscar_facturas(self.conexion, mes="2020-01"), [])

    def test_marcar_nueva_solicitada_solo_en_canceladas(self):
        """El jefe solo puede marcar «Nueva factura solicitada» en una cancelada."""
        self.assertFalse(base_datos.marcar_nueva_solicitada(self.conexion, folio_fiscal(1)))
        self.assertTrue(base_datos.marcar_nueva_solicitada(self.conexion, folio_fiscal(3)))

    def test_meses_disponibles(self):
        """Solo aparece el mes en que se validaron las facturas."""
        self.assertEqual(base_datos.meses_disponibles(self.conexion), [self.mes_actual])

    def test_ultimo_comprobante_de_una_factura(self):
        """Si una cancelada se valida dos veces, se usa el comprobante más nuevo."""
        segunda = validar_factura(self.conexion, crear_xml(FACTURAS_PRUEBA[2]), "jefe")
        ultimo = base_datos.obtener_id_ultima_validacion(self.conexion, folio_fiscal(3))
        self.assertEqual(ultimo, segunda["id_validacion"])
        self.assertIsNone(base_datos.obtener_id_ultima_validacion(self.conexion, "NO-EXISTE"))

    def test_reiniciar_datos_no_borra_usuarios(self):
        """«Reiniciar datos» borra facturas y validaciones, pero no los usuarios."""
        base_datos.crear_usuario(self.conexion, "jefe", CLAVE_PRUEBA, "jefe")
        base_datos.borrar_facturas(self.conexion)
        self.assertEqual(base_datos.buscar_facturas(self.conexion), [])
        self.assertEqual(base_datos.resumen_mes(self.conexion, self.mes_actual)["validaciones"], 0)
        self.assertIsNotNone(base_datos.verificar_usuario(self.conexion, "jefe", CLAVE_PRUEBA))

    def test_resumen_del_mes(self):
        """El reporte del mes cuenta 10 validaciones: 7 vigentes, 2 canceladas, 1 receptor mal."""
        resumen = base_datos.resumen_mes(self.conexion, self.mes_actual)
        self.assertEqual(resumen["validaciones"], 10)
        self.assertEqual(resumen["vigentes"], 7)
        self.assertEqual(resumen["canceladas"], 2)
        self.assertEqual(resumen["receptor_incorrecto"], 1)
        self.assertEqual(resumen["hojas_ahorradas"], 10)


if __name__ == "__main__":
    unittest.main()
