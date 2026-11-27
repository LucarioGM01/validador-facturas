"""
seguimiento.py
--------------
Lleva la cuenta de lo que pasa mientras se validan facturas, para poder
mostrarlo EN VIVO:

  - cuántas facturas llegaron y cuántas ya se validaron,
  - cada paso que se hace con la factura actual (leer, comprobar el folio,
    consultar el SAT, revisar el receptor...),
  - y, al terminar cada una, su resultado y POR QUÉ no se validó si falló.

Este archivo NO manda nada a ningún lado. Solo arma los textos. Quien lo usa le
pasa una función "al_cambiar" que se llama cada vez que algo cambia:
  - el bot de Telegram edita su mensaje con progreso.texto_telegram()
  - la página web guarda progreso.texto_completo() para mostrarlo

Prueba rápida desde la terminal:
    python seguimiento.py
"""

import avisos
import base_datos
from validador import ETIQUETAS

# Un paso que empieza con esto está "en curso": el siguiente lo reemplaza.
EN_CURSO = "⏳"


class Progreso:
    """El seguimiento de UN grupo de facturas que llegaron juntas."""

    def __init__(self, origen, total, al_cambiar=None):
        self.origen = origen            # "carpeta bandeja_entrada", "bot de Telegram"...
        self.total = total              # cuántas facturas llegaron
        # Una función (o una lista de funciones) que reciben este mismo objeto
        # cada vez que algo cambia. Por ejemplo: guardar en la base de datos y
        # editar el mensaje de Telegram.
        self.al_cambiar = al_cambiar
        self.facturas = []              # una por factura: {"nombre", "pasos", "resultado"}
        self.terminado = False

    # --- Lo que se va avisando mientras se valida ---

    def empezar_factura(self, nombre):
        self.facturas.append({"nombre": nombre, "pasos": [], "resultado": None})
        self._avisar()

    def paso(self, texto):
        """Anota un paso de la factura actual. Un «⏳ …» se reemplaza por el
        resultado que viene después, así no se llena de líneas repetidas."""
        pasos = self.facturas[-1]["pasos"]
        if pasos and pasos[-1].startswith(EN_CURSO):
            pasos[-1] = texto
        else:
            pasos.append(texto)
        self._avisar()

    def paso_en_curso(self):
        """Texto del paso «⏳ …» que se está haciendo ahora, o "" si no hay."""
        if not self.facturas or self.facturas[-1]["resultado"] is not None:
            return ""
        pasos = self.facturas[-1]["pasos"]
        return pasos[-1] if pasos and pasos[-1].startswith(EN_CURSO) else ""

    def terminar_factura(self, resultado):
        self.facturas[-1]["resultado"] = resultado
        self._avisar()

    def terminar(self):
        self.terminado = True
        self._avisar()

    def _avisar(self):
        if self.al_cambiar is None:
            return
        destinos = self.al_cambiar if isinstance(self.al_cambiar, (list, tuple)) else [self.al_cambiar]
        for destino in destinos:  # en orden: primero la base de datos, luego Telegram
            destino(self)

    # --- Conteos ---

    @property
    def hechas(self):
        """Cuántas facturas ya tienen resultado."""
        return sum(1 for f in self.facturas if f["resultado"] is not None)

    @property
    def con_problema(self):
        """Cuántas de las ya hechas requieren atención (no se pueden pagar tal cual)."""
        return sum(1 for f in self.facturas
                   if f["resultado"] is not None and avisos.requiere_atencion(f["resultado"]))

    @property
    def correctas(self):
        return self.hechas - self.con_problema

    # --- Armar los textos ---

    def encabezado(self):
        """Primeras líneas: cuántas llegaron y cuántas van."""
        plural = "factura" if self.total == 1 else "facturas"
        if self.terminado:
            situacion = "✅ Validación terminada"
        else:
            situacion = "⏳ Validando…"
        return [
            f"📥 Llegaron {self.total} {plural} · Origen: {self.origen}",
            f"{situacion} · Validadas: {self.hechas} de {self.total}",
            f"✔ Correctas: {self.correctas} · ⚠ Requieren atención: {self.con_problema}",
        ]

    @staticmethod
    def _linea_resultado(numero, resultado):
        """Un renglón con el resultado final de una factura (y el porqué si falló)."""
        if resultado["uuid"]:
            datos = (f"…{resultado['uuid'][-4:]} · {resultado['nombre_emisor']} "
                     f"· ${resultado['total']:,.2f}")
        else:
            datos = f"archivo {resultado['archivo']}"
        repetida = " (ya validada antes)" if resultado["es_repetida"] else ""
        renglones = [f"{numero}. {ETIQUETAS[resultado['estado']]}{repetida} · {datos}"]
        if avisos.requiere_atencion(resultado):
            renglones.append(f"   ↳ Por qué: {resultado['mensaje']}")
            if resultado.get("aviso_lectura"):
                renglones.append(f"   ↳ 🔍 {resultado['aviso_lectura']}")
        return renglones

    def texto_telegram(self):
        """Texto corto para el mensaje de Telegram (solo la factura actual muestra
        sus pasos; las ya terminadas se resumen en un renglón)."""
        renglones = self.encabezado() + [""]
        for numero, factura in enumerate(self.facturas, start=1):
            if factura["resultado"] is not None:
                renglones += self._linea_resultado(numero, factura["resultado"])
            else:
                renglones.append(f"{numero}. {factura['nombre']} · validando:")
                renglones += [f"   {paso}" for paso in factura["pasos"]]
        return self._recortar("\n".join(renglones))

    def texto_completo(self):
        """Texto largo para la página web: TODOS los pasos de TODAS las facturas."""
        renglones = self.encabezado()
        for numero, factura in enumerate(self.facturas, start=1):
            renglones += ["", f"━━ Factura {numero} de {self.total}: {factura['nombre']}"]
            renglones += [f"   {paso}" for paso in factura["pasos"]]
            if factura["resultado"] is not None:
                renglones += self._linea_resultado(numero, factura["resultado"])
        return "\n".join(renglones)

    @staticmethod
    def _recortar(texto):
        """Telegram no acepta mensajes de más de 4096 letras."""
        if len(texto) <= avisos.LARGO_MAXIMO:
            return texto
        return "…" + texto[-(avisos.LARGO_MAXIMO - 1):]  # se conserva lo más reciente


class GuardarEnBD:
    """Destino para Progreso: guarda el avance en la base de datos, y de ahí lo
    lee la pantalla «En vivo» de la página web.

        progreso = Progreso("app web", 3, al_cambiar=GuardarEnBD(conexion))
    """

    def __init__(self, conexion):
        self.conexion = conexion
        self.id_seguimiento = None  # se crea con el primer aviso

    def __call__(self, progreso):
        if self.id_seguimiento is None:
            self.id_seguimiento = base_datos.crear_seguimiento(
                self.conexion, progreso.origen, progreso.total)
        base_datos.actualizar_seguimiento(
            self.conexion, self.id_seguimiento, progreso.hechas, progreso.correctas,
            progreso.con_problema, progreso.terminado, progreso.texto_completo())


if __name__ == "__main__":
    # Demostración sin Telegram: imprime cada cambio.
    import base_datos
    from procesar_lote import archivos_de_prueba, validar_lote

    conexion = base_datos.conectar(":memory:")
    archivos = archivos_de_prueba()[:3]
    progreso = Progreso("demostración", len(archivos),
                        al_cambiar=lambda p: print("\n" + "=" * 50 + "\n" + p.texto_telegram()))
    validar_lote(conexion, archivos, "demo", progreso=progreso)
