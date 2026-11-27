"""
base_datos.py
-------------
Guarda y consulta la información en SQLite: una base de datos que vive dentro
de un solo archivo (validador.db) y que ya viene incluida con Python.

Tablas:
  usuarios      -> quién puede entrar y con qué rol (auxiliar o jefe)
  facturas      -> una fila por factura, con su estado más reciente
  validaciones  -> una fila por cada validación: es el "comprobante digital"
                   con fecha, hora, usuario y cuánto tardó (RN-06)

El archivo validador.db se crea solo la primera vez y NO se sube a GitHub
(está en .gitignore).
"""

import hashlib
import hmac
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------
# 1. Constantes
# ---------------------------------------------------------------

RUTA_BD = Path(__file__).parent / "validador.db"

# Hora de México. Es importante porque los servidores de Streamlit Cloud usan
# otra zona horaria y, sin esto, las horas saldrían adelantadas 6 horas.
ZONA_HORARIA = ZoneInfo("America/Mexico_City")

ROLES_VALIDOS = ("auxiliar", "jefe")

# Cuántas veces se repite el cálculo del hash de la contraseña. Lo hace lento
# a propósito, para que adivinar contraseñas a la fuerza tarde muchísimo.
ITERACIONES_HASH = 200_000

# Instrucciones SQL para crear las tablas. "IF NOT EXISTS" hace que no pase
# nada si la tabla ya existe, así que se puede ejecutar cada vez que abre la app.
TABLAS_SQL = """
CREATE TABLE IF NOT EXISTS usuarios (
    usuario  TEXT PRIMARY KEY,                 -- nombre para iniciar sesión
    nombre   TEXT NOT NULL DEFAULT '',         -- nombre para mostrar
    rol      TEXT NOT NULL CHECK (rol IN ('auxiliar', 'jefe')),
    sal      TEXT NOT NULL,                    -- dato al azar para el hash
    hash     TEXT NOT NULL                     -- contraseña "revuelta" (nunca en texto)
);

CREATE TABLE IF NOT EXISTS facturas (
    uuid              TEXT PRIMARY KEY,        -- folio fiscal
    rfc_emisor        TEXT NOT NULL,
    nombre_emisor     TEXT NOT NULL,
    rfc_receptor      TEXT NOT NULL,
    nombre_receptor   TEXT NOT NULL DEFAULT '',
    total             REAL NOT NULL,
    fecha_emision     TEXT NOT NULL,
    estado            TEXT NOT NULL,           -- Vigente, Cancelada, Receptor incorrecto...
    fecha_cancelacion TEXT NOT NULL DEFAULT '',
    ultima_validacion TEXT NOT NULL,           -- fecha y hora de la última validación
    aviso_enviado     INTEGER NOT NULL DEFAULT 0,  -- 1 = el aviso de Telegram sí llegó (RN-02)
    nueva_solicitada  INTEGER NOT NULL DEFAULT 0,  -- 1 = el jefe ya pidió factura nueva
    fecha_solicitud   TEXT NOT NULL DEFAULT '',
    uuid_reemplazo    TEXT REFERENCES facturas(uuid)  -- RN-04: factura nueva ligada
);

CREATE TABLE IF NOT EXISTS validaciones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,  -- número de comprobante
    uuid        TEXT NOT NULL REFERENCES facturas(uuid),
    estado      TEXT NOT NULL,
    fecha_hora  TEXT NOT NULL,
    usuario     TEXT NOT NULL,
    segundos    REAL NOT NULL                       -- cuánto tardó la validación
);

-- Avance EN VIVO de cada grupo de facturas que llega (lo escribe el bot o la
-- página y lo lee la pantalla «En vivo»).
CREATE TABLE IF NOT EXISTS seguimientos (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    origen         TEXT NOT NULL,                   -- «carpeta bandeja_entrada», «app web»...
    total          INTEGER NOT NULL,                -- cuántas facturas llegaron
    hechas         INTEGER NOT NULL DEFAULT 0,      -- cuántas ya se validaron
    correctas      INTEGER NOT NULL DEFAULT 0,
    con_problema   INTEGER NOT NULL DEFAULT 0,
    terminado      INTEGER NOT NULL DEFAULT 0,      -- 1 = ya terminó
    inicio         TEXT NOT NULL,
    actualizado    TEXT NOT NULL,                   -- última vez que cambió
    texto          TEXT NOT NULL DEFAULT ''         -- todos los pasos, ya escritos
);

-- «Latido» del bot: cada pocos segundos escribe aquí la hora, para que la
-- página pueda decir si el bot está encendido.
CREATE TABLE IF NOT EXISTS latido (
    id    INTEGER PRIMARY KEY CHECK (id = 1),       -- una sola fila
    hora  TEXT NOT NULL
);
"""


# ---------------------------------------------------------------
# 2. Conexión
# ---------------------------------------------------------------

def ahora():
    """Fecha y hora actual de México como texto. Ejemplo: '2026-11-18T10:30:00'."""
    return datetime.now(ZONA_HORARIA).strftime("%Y-%m-%dT%H:%M:%S")


def conectar(ruta=RUTA_BD):
    """Abre la base de datos (la crea si no existe) y regresa la conexión.

    - ruta=":memory:" crea una base temporal en memoria (la usan las pruebas).
    - check_same_thread=False deja que Streamlit use la misma conexión
      aunque cada clic se atienda en un "hilo" distinto.
    - row_factory = sqlite3.Row permite leer columnas por nombre: fila["estado"].
    """
    conexion = sqlite3.connect(ruta, check_same_thread=False)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")  # que se respeten los REFERENCES
    conexion.executescript(TABLAS_SQL)
    _agregar_columnas_nuevas(conexion)
    return conexion


def _agregar_columnas_nuevas(conexion):
    """Si la base de datos se creó con una versión anterior del programa, le
    agrega las columnas nuevas. Así no hay que borrarla para actualizarla."""
    columnas = {fila["name"] for fila in conexion.execute("PRAGMA table_info(facturas)")}
    if "aviso_enviado" not in columnas:
        with conexion:
            conexion.execute(
                "ALTER TABLE facturas ADD COLUMN aviso_enviado INTEGER NOT NULL DEFAULT 0")


# ---------------------------------------------------------------
# 3. Usuarios y contraseñas
# ---------------------------------------------------------------

def _hash_contrasena(contrasena, sal):
    """Convierte la contraseña en un "hash": un texto revuelto que no se puede
    regresar a la contraseña original. La "sal" es un dato al azar distinto
    para cada usuario, así dos contraseñas iguales dan hashes diferentes."""
    resultado = hashlib.pbkdf2_hmac(
        "sha256", contrasena.encode("utf-8"), sal, ITERACIONES_HASH
    )
    return resultado.hex()


def crear_usuario(conexion, usuario, contrasena, rol, nombre=""):
    """Crea un usuario, o lo actualiza si ya existe. Nunca guarda la contraseña tal cual."""
    if rol not in ROLES_VALIDOS:
        raise ValueError(f"Rol no válido: {rol}. Usa 'auxiliar' o 'jefe'.")
    if not contrasena:
        raise ValueError("La contraseña no puede estar vacía.")
    sal = os.urandom(16)  # 16 bytes al azar
    with conexion:  # guarda los cambios al terminar el bloque
        conexion.execute(
            """
            INSERT INTO usuarios (usuario, nombre, rol, sal, hash)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(usuario) DO UPDATE SET
                nombre = excluded.nombre, rol = excluded.rol,
                sal = excluded.sal, hash = excluded.hash
            """,
            (usuario.strip().lower(), nombre, rol, sal.hex(), _hash_contrasena(contrasena, sal)),
        )


def verificar_usuario(conexion, usuario, contrasena):
    """Revisa usuario y contraseña.

    Regresa {"usuario", "nombre", "rol"} si son correctos, o None si el usuario
    no existe o la contraseña está mal (no decimos cuál de los dos falló, para
    no darle pistas a un intruso).
    """
    fila = conexion.execute(
        "SELECT * FROM usuarios WHERE usuario = ?", (usuario.strip().lower(),)
    ).fetchone()
    if fila is None:
        return None
    hash_calculado = _hash_contrasena(contrasena, bytes.fromhex(fila["sal"]))
    # compare_digest compara sin dar pistas por el tiempo que tarda.
    if not hmac.compare_digest(hash_calculado, fila["hash"]):
        return None
    return {"usuario": fila["usuario"], "nombre": fila["nombre"], "rol": fila["rol"]}


# ---------------------------------------------------------------
# 4. Facturas y validaciones
# ---------------------------------------------------------------

def guardar_validacion(conexion, factura, usuario, segundos):
    """Guarda (o actualiza) la factura y agrega un comprobante de validación.

    `factura` es el diccionario que arma validador.py. Regresa el número (id)
    del comprobante nuevo.

    Las instrucciones usan :nombre para tomar cada valor del diccionario por
    su clave. Así nunca pegamos texto directo en el SQL, lo que evita errores
    y ataques de "inyección SQL".
    """
    fecha_hora = ahora()
    datos = {**factura, "ultima_validacion": fecha_hora, "usuario": usuario, "segundos": segundos}
    with conexion:  # todo o nada: si algo falla, no se guarda nada a medias
        conexion.execute(
            """
            INSERT INTO facturas (uuid, rfc_emisor, nombre_emisor, rfc_receptor,
                nombre_receptor, total, fecha_emision, estado, fecha_cancelacion,
                ultima_validacion)
            VALUES (:uuid, :rfc_emisor, :nombre_emisor, :rfc_receptor,
                :nombre_receptor, :total, :fecha, :estado, :fecha_cancelacion,
                :ultima_validacion)
            ON CONFLICT(uuid) DO UPDATE SET
                estado = excluded.estado,
                fecha_cancelacion = excluded.fecha_cancelacion,
                ultima_validacion = excluded.ultima_validacion
            """,
            datos,
        )
        cursor = conexion.execute(
            """
            INSERT INTO validaciones (uuid, estado, fecha_hora, usuario, segundos)
            VALUES (:uuid, :estado, :ultima_validacion, :usuario, :segundos)
            """,
            datos,
        )
    return cursor.lastrowid


def obtener_factura(conexion, uuid):
    """Regresa la factura como diccionario, o None si nunca se ha validado."""
    fila = conexion.execute("SELECT * FROM facturas WHERE uuid = ?", (uuid,)).fetchone()
    return dict(fila) if fila else None


def obtener_validacion(conexion, id_validacion):
    """Regresa un comprobante (validación + datos de su factura), o None si no existe."""
    fila = conexion.execute(
        """
        SELECT v.id, v.fecha_hora, v.usuario, v.estado, v.segundos,
               f.uuid, f.rfc_emisor, f.nombre_emisor, f.rfc_receptor,
               f.nombre_receptor, f.total, f.fecha_emision, f.fecha_cancelacion
        FROM validaciones AS v
        JOIN facturas AS f ON f.uuid = v.uuid
        WHERE v.id = ?
        """,
        (id_validacion,),
    ).fetchone()
    return dict(fila) if fila else None


def obtener_id_ultima_validacion(conexion, uuid):
    """Número del comprobante más reciente de una factura, o None si no tiene."""
    return conexion.execute(
        "SELECT MAX(id) FROM validaciones WHERE uuid = ?", (uuid,)
    ).fetchone()[0]


def meses_disponibles(conexion):
    """Meses con validaciones ("2026-11", "2026-10"...), del más reciente al más antiguo."""
    filas = conexion.execute(
        "SELECT DISTINCT substr(fecha_hora, 1, 7) AS mes FROM validaciones ORDER BY mes DESC"
    )
    return [fila["mes"] for fila in filas]


def borrar_facturas(conexion):
    """Borra TODAS las facturas y validaciones (los usuarios se quedan).

    Solo sirve para reiniciar la demostración con las facturas de prueba.
    """
    with conexion:
        conexion.execute("DELETE FROM validaciones")
        conexion.execute("UPDATE facturas SET uuid_reemplazo = NULL")  # quita las ligas primero
        conexion.execute("DELETE FROM facturas")
        conexion.execute("DELETE FROM seguimientos")  # también el avance en vivo de la demo


def _sin_acentos(texto):
    """'Papelería' -> 'Papeleria'. Los nombres del SAT vienen sin acentos."""
    return texto.translate(str.maketrans("áéíóúüÁÉÍÓÚÜ", "aeiouuAEIOUU"))


def buscar_facturas(conexion, texto="", estado="", mes=""):
    """Busca facturas para el Historial. Todos los filtros son opcionales.

    - texto:  parte del nombre o RFC del proveedor, o del folio
    - estado: "Vigente", "Cancelada", "Receptor incorrecto"...
    - mes:    "2026-11" (mes de la última validación)

    Regresa una lista de diccionarios, de la más reciente a la más antigua.
    """
    consulta = "SELECT * FROM facturas WHERE 1 = 1"  # 1 = 1 permite ir sumando "AND ..."
    parametros = []
    if texto.strip():
        patron = f"%{_sin_acentos(texto.strip())}%"  # % = "cualquier cosa"
        consulta += " AND (nombre_emisor LIKE ? OR rfc_emisor LIKE ? OR uuid LIKE ?)"
        parametros += [patron, patron, patron]
    if estado:
        consulta += " AND estado = ?"
        parametros.append(estado)
    if mes:
        consulta += " AND ultima_validacion LIKE ?"
        parametros.append(f"{mes}%")
    consulta += " ORDER BY ultima_validacion DESC"
    return [dict(fila) for fila in conexion.execute(consulta, parametros)]


def marcar_aviso_enviado(conexion, uuid):
    """RN-02: anota que el aviso de esta factura cancelada SÍ le llegó al jefe."""
    with conexion:
        conexion.execute("UPDATE facturas SET aviso_enviado = 1 WHERE uuid = ?", (uuid,))


def marcar_nueva_solicitada(conexion, uuid):
    """El jefe marca «Nueva factura solicitada». Solo funciona con canceladas.

    Regresa True si se marcó, False si la factura no existe o no está cancelada.
    """
    with conexion:
        cursor = conexion.execute(
            """
            UPDATE facturas SET nueva_solicitada = 1, fecha_solicitud = ?
            WHERE uuid = ? AND estado = 'Cancelada'
            """,
            (ahora(), uuid),
        )
    return cursor.rowcount == 1  # rowcount = cuántas filas cambiaron


def ligar_reemplazo(conexion, uuid_cancelada, uuid_nueva):
    """RN-04: liga la factura nueva a la cancelada. Regresa True si se ligó."""
    with conexion:
        cursor = conexion.execute(
            """
            UPDATE facturas SET uuid_reemplazo = ?, nueva_solicitada = 1
            WHERE uuid = ? AND estado = 'Cancelada'
            """,
            (uuid_nueva, uuid_cancelada),
        )
    return cursor.rowcount == 1


def resumen_mes(conexion, mes):
    """Totales de un mes ("2026-11") para el Reporte del mes.

    Las hojas ahorradas son una por validación: antes cada factura se
    imprimía en una hoja de validación del portal del SAT.
    """
    patron = f"{mes}%"
    conteo = {
        fila["estado"]: fila["cantidad"]
        for fila in conexion.execute(
            """
            SELECT estado, COUNT(*) AS cantidad FROM validaciones
            WHERE fecha_hora LIKE ? GROUP BY estado
            """,
            (patron,),
        )
    }
    total, promedio = conexion.execute(
        "SELECT COUNT(*), AVG(segundos) FROM validaciones WHERE fecha_hora LIKE ?",
        (patron,),
    ).fetchone()
    # Los textos de los estados son los mismos que en validador.py.
    return {
        "validaciones": total,
        "vigentes": conteo.get("Vigente", 0),
        "canceladas": conteo.get("Cancelada", 0),
        "receptor_incorrecto": conteo.get("Receptor incorrecto", 0),
        "no_encontradas": conteo.get("No encontrada", 0),
        "hojas_ahorradas": total,
        "segundos_promedio": promedio or 0.0,  # AVG da None si no hay filas
    }


# ---------------------------------------------------------------
# 5. Avance en vivo y latido del bot
# ---------------------------------------------------------------

def crear_seguimiento(conexion, origen, total):
    """Anota que llegó un grupo de facturas. Regresa su número (id)."""
    ahora_texto = ahora()
    with conexion:
        cursor = conexion.execute(
            "INSERT INTO seguimientos (origen, total, inicio, actualizado) VALUES (?, ?, ?, ?)",
            (origen, total, ahora_texto, ahora_texto),
        )
    return cursor.lastrowid


def actualizar_seguimiento(conexion, id_seguimiento, hechas, correctas, con_problema,
                           terminado, texto):
    """Guarda cómo va un grupo de facturas (cuántas van y todos sus pasos)."""
    with conexion:
        conexion.execute(
            """
            UPDATE seguimientos
            SET hechas = ?, correctas = ?, con_problema = ?, terminado = ?,
                actualizado = ?, texto = ?
            WHERE id = ?
            """,
            (hechas, correctas, con_problema, int(terminado), ahora(), texto, id_seguimiento),
        )


def ultimos_seguimientos(conexion, limite=6):
    """Los últimos grupos de facturas, del más reciente al más antiguo."""
    filas = conexion.execute(
        "SELECT * FROM seguimientos ORDER BY id DESC LIMIT ?", (limite,)
    )
    return [dict(fila) for fila in filas]


def guardar_latido(conexion):
    """El bot avisa «sigo encendido»."""
    with conexion:
        conexion.execute(
            "INSERT INTO latido (id, hora) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET hora = excluded.hora",
            (ahora(),),
        )


def leer_latido(conexion):
    """Hora del último latido del bot ("2026-11-27T15:30:00"), o None si nunca avisó."""
    fila = conexion.execute("SELECT hora FROM latido WHERE id = 1").fetchone()
    return fila["hora"] if fila else None
