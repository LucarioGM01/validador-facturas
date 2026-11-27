"""
Pruebas del avance en vivo: los pasos que avisa validador.py y el texto que arma
seguimiento.py (cuántas llegaron, cuántas van y por qué falló cada una).

Cómo correrlas:
    python -m unittest discover tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import base_datos
from generar_facturas import FACTURAS_PRUEBA, crear_xml
from procesar_lote import validar_lote
from seguimiento import GuardarEnBD, Progreso
from validador import validar_factura


def xml_de(numero):
    return crear_xml(FACTURAS_PRUEBA[numero - 1])


def pasos_de(numero_factura=None, contenido=None):
    """Valida una factura y regresa la lista de pasos que fue avisando."""
    pasos = []
    conexion = base_datos.conectar(":memory:")
    validar_factura(conexion, contenido or xml_de(numero_factura), "prueba", "f.xml",
                    al_paso=pasos.append)
    conexion.close()
    return pasos


class TestPasosDelValidador(unittest.TestCase):

    def test_factura_vigente_pasa_por_todos_los_pasos(self):
        texto = "\n".join(pasos_de(1))
        self.assertIn("XML leído", texto)
        self.assertIn("Folio nuevo", texto)
        self.assertIn("El SAT lo marca como Vigente", texto)
        self.assertIn("Receptor TEC000101AA1 correcto", texto)
        self.assertIn("Comprobante No.", texto)

    def test_cancelada_dice_por_que(self):
        texto = "\n".join(pasos_de(3))
        self.assertIn("CANCELADA el 05/11/2026", texto)

    def test_receptor_incorrecto_dice_cual_era(self):
        texto = "\n".join(pasos_de(8))
        self.assertIn("✖ El receptor es XYZ000101ZZ9", texto)

    def test_archivo_que_no_es_xml_dice_el_motivo(self):
        pasos = pasos_de(contenido=b"esto no es un xml")
        self.assertTrue(pasos[-1].startswith("✖ No se pudo leer el XML"))

    def test_sin_al_paso_sigue_funcionando(self):
        conexion = base_datos.conectar(":memory:")
        resultado = validar_factura(conexion, xml_de(1), "prueba", "f.xml")
        self.assertEqual(resultado["estado"], "Vigente")

    def test_cada_paso_en_curso_va_seguido_de_su_resultado(self):
        """Un «⏳» siempre se reemplaza: nunca queda un paso colgado al final."""
        for numero in (1, 3, 8):
            self.assertFalse(pasos_de(numero)[-1].startswith("⏳"))


class TestProgreso(unittest.TestCase):

    def validar_tres(self, cambios=None):
        """Valida las facturas 1, 3 (cancelada) y 8 (receptor incorrecto)."""
        archivos = [(f"factura_{n:02d}.xml", xml_de(n).encode("utf-8")) for n in (1, 3, 8)]
        progreso = Progreso("prueba", len(archivos),
                            al_cambiar=cambios.append if cambios is not None else None)
        conexion = base_datos.conectar(":memory:")
        validar_lote(conexion, archivos, "prueba", progreso=progreso)
        conexion.close()
        return progreso

    def test_cuenta_cuantas_llegaron_y_cuantas_van(self):
        progreso = self.validar_tres()
        self.assertEqual((progreso.total, progreso.hechas), (3, 3))
        self.assertEqual((progreso.correctas, progreso.con_problema), (1, 2))
        self.assertTrue(progreso.terminado)

    def test_el_texto_dice_cuantas_llegaron(self):
        texto = self.validar_tres().texto_telegram()
        self.assertIn("Llegaron 3 facturas", texto)
        self.assertIn("Validadas: 3 de 3", texto)
        self.assertIn("Validación terminada", texto)

    def test_el_texto_explica_por_que_fallaron(self):
        texto = self.validar_tres().texto_telegram()
        self.assertIn("Por qué: Cancelada el 05/11/2026", texto)
        self.assertIn("Por qué: Está a nombre de XYZ000101ZZ9", texto)

    def test_el_texto_completo_trae_todos_los_pasos(self):
        texto = self.validar_tres().texto_completo()
        self.assertEqual(texto.count("━━ Factura"), 3)
        self.assertEqual(texto.count("Consultando el folio en el SAT") + texto.count("SAT lo marca")
                         + texto.count("NO aparece"), 3)

    def test_avisa_en_cada_cambio_y_el_conteo_sube_poco_a_poco(self):
        van = []
        archivos = [(f"factura_{n:02d}.xml", xml_de(n).encode("utf-8")) for n in (1, 3)]
        progreso = Progreso("prueba", 2, al_cambiar=lambda p: van.append(p.hechas))
        conexion = base_datos.conectar(":memory:")
        validar_lote(conexion, archivos, "prueba", progreso=progreso)
        self.assertEqual(van[0], 0)
        self.assertEqual(van[-1], 2)
        self.assertEqual(van, sorted(van))  # nunca baja

    def test_una_factura_a_medias_muestra_sus_pasos(self):
        progreso = Progreso("prueba", 2)
        progreso.empezar_factura("a.xml")
        progreso.paso("⏳ Leyendo…")
        progreso.paso("✔ Leído")
        texto = progreso.texto_telegram()
        self.assertIn("a.xml · validando:", texto)
        self.assertIn("✔ Leído", texto)
        self.assertNotIn("⏳ Leyendo", texto)  # el paso en curso se reemplazó

    def test_mensaje_muy_largo_se_recorta_para_telegram(self):
        progreso = Progreso("prueba", 1)
        progreso.empezar_factura("a.xml")
        for numero in range(500):
            progreso.paso(f"✔ paso {numero}")
        self.assertLessEqual(len(progreso.texto_telegram()), 4096)


class TestGuardarEnBD(unittest.TestCase):
    """El avance se guarda en la base de datos para la pantalla «En vivo»."""

    def test_el_avance_queda_guardado(self):
        conexion = base_datos.conectar(":memory:")
        archivos = [(f"factura_{n:02d}.xml", xml_de(n).encode("utf-8")) for n in (1, 3, 8)]
        progreso = Progreso("prueba", 3, al_cambiar=GuardarEnBD(conexion))
        validar_lote(conexion, archivos, "prueba", progreso=progreso)

        lotes = base_datos.ultimos_seguimientos(conexion)
        self.assertEqual(len(lotes), 1)  # un solo grupo, aunque hubo muchos cambios
        lote = lotes[0]
        self.assertEqual((lote["total"], lote["hechas"]), (3, 3))
        self.assertEqual((lote["correctas"], lote["con_problema"]), (1, 2))
        self.assertEqual(lote["terminado"], 1)
        self.assertIn("Por qué: Cancelada el 05/11/2026", lote["texto"])

    def test_varios_destinos_reciben_cada_cambio(self):
        a, b = [], []
        progreso = Progreso("prueba", 1, al_cambiar=[a.append, b.append])
        progreso.empezar_factura("a.xml")
        progreso.paso("✔ listo")
        self.assertEqual((len(a), len(b)), (2, 2))

    def test_los_grupos_salen_del_mas_nuevo_al_mas_viejo(self):
        conexion = base_datos.conectar(":memory:")
        primero = base_datos.crear_seguimiento(conexion, "uno", 1)
        segundo = base_datos.crear_seguimiento(conexion, "dos", 2)
        ids = [lote["id"] for lote in base_datos.ultimos_seguimientos(conexion)]
        self.assertEqual(ids, [segundo, primero])

    def test_reiniciar_la_demostracion_borra_el_avance(self):
        conexion = base_datos.conectar(":memory:")
        base_datos.crear_seguimiento(conexion, "uno", 1)
        base_datos.borrar_facturas(conexion)
        self.assertEqual(base_datos.ultimos_seguimientos(conexion), [])

    def test_latido_del_bot(self):
        conexion = base_datos.conectar(":memory:")
        self.assertIsNone(base_datos.leer_latido(conexion))
        base_datos.guardar_latido(conexion)
        base_datos.guardar_latido(conexion)  # una segunda vez actualiza, no duplica
        self.assertEqual(base_datos.leer_latido(conexion)[:10], base_datos.ahora()[:10])


if __name__ == "__main__":
    unittest.main()
