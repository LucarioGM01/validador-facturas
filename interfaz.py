"""
interfaz.py
-----------
Piezas de la interfaz que comparten todas las pantallas: logos, encabezados,
tarjetas y las acciones de los botones.

Todo está hecho con Python y los componentes nativos de Streamlit (sin HTML,
CSS ni imágenes SVG). Los colores del programa salen del tema de
.streamlit/config.toml.

Las pantallas están en la carpeta app_pages/ y app.py arma el menú.
"""

from pathlib import Path

import streamlit as st

import avisos
import base_datos
import procesar_lote
from comprobante import NOMBRE_CLIENTE, NOMBRES_LOGO_MARCA, NOMBRES_LOGO_TEC, buscar_logo
from seguimiento import GuardarEnBD, Progreso
from validador import (
    ARCHIVO_INVALIDO,
    CANCELADA,
    ETIQUETAS,
    NO_ENCONTRADA,
    RECEPTOR_INCORRECTO,
    VIGENTE,
    registrar_factura_nueva,
)

# ---------------------------------------------------------------
# 1. Pantallas, colores e íconos
# ---------------------------------------------------------------

CARPETA = Path(__file__).parent
CARPETA_PRUEBA = CARPETA / "facturas_prueba"

PAG_ACCESO = "app_pages/acceso.py"
PAG_INICIO = "app_pages/inicio.py"
PAG_CARGAR = "app_pages/cargar.py"
PAG_EN_VIVO = "app_pages/en_vivo.py"
PAG_RESULTADOS = "app_pages/resultados.py"
PAG_HISTORIAL = "app_pages/historial.py"
PAG_REPORTE = "app_pages/reporte.py"

# Cada opción tiene su ícono, para reconocerla de un vistazo. Los íconos son
# "Material Symbols": :material/nombre_del_icono:
OPCIONES = {
    "inicio": {
        "titulo": "Inicio", "icono": ":material/home:", "pagina": PAG_INICIO,
        "descripcion": "Resumen del mes y accesos rápidos.",
    },
    "cargar": {
        "titulo": "Cargar facturas", "icono": ":material/upload_file:", "pagina": PAG_CARGAR,
        "descripcion": "Sube los XML de los proveedores o usa las facturas de prueba.",
    },
    "en_vivo": {
        "titulo": "En vivo", "icono": ":material/sensors:", "pagina": PAG_EN_VIVO,
        "descripcion": "Mira en tiempo real cómo llegan y se validan las facturas.",
    },
    "resultados": {
        "titulo": "Resultados", "icono": ":material/fact_check:", "pagina": PAG_RESULTADOS,
        "descripcion": "Mira cuáles están vigentes, canceladas o con receptor incorrecto.",
    },
    "historial": {
        "titulo": "Historial", "icono": ":material/folder_open:", "pagina": PAG_HISTORIAL,
        "descripcion": "Busca facturas validadas y da seguimiento a las canceladas.",
    },
    "reporte": {
        "titulo": "Reporte del mes", "icono": ":material/monitoring:", "pagina": PAG_REPORTE,
        "descripcion": "Totales, hojas ahorradas y comparación con el proceso anterior.",
    },
}

# Colores de las tarjetas de datos: nombre en español -> color de texto de
# Streamlit (se escribe :color[texto] en Markdown). "primary" es el cobre del tema.
COLORES = {
    "azul": "blue",
    "verde": "green",
    "rojo": "red",
    "naranja": "orange",
    "violeta": "violet",
    "cobre": "primary",
}

# Cómo se ve cada estado: color de la insignia (st.badge) e ícono.
# El estado siempre lleva texto + ícono + color, nunca solo color.
ESTADOS_VISUAL = {
    VIGENTE: ("green", ":material/check_circle:"),
    CANCELADA: ("red", ":material/cancel:"),
    RECEPTOR_INCORRECTO: ("orange", ":material/warning:"),
    NO_ENCONTRADA: ("gray", ":material/help:"),
    ARCHIVO_INVALIDO: ("gray", ":material/block:"),
}

MINUTOS_ANTES = 3  # promedio del proceso manual (de 1 a 5 minutos por factura)

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


# ---------------------------------------------------------------
# 2. Logos, encabezados y tarjetas
# ---------------------------------------------------------------

def mostrar_logos(tamano=60):
    """Logo de Soluciones Digitales y logo del Tecnológico, uno junto al otro.

    Usa una fila horizontal (no columnas) para que en pantallas angostas los
    logos no se estiren: cada uno conserva su tamaño.
    """
    with st.container(horizontal=True, vertical_alignment="center",
                      horizontal_alignment="distribute"):
        ruta_marca = buscar_logo(NOMBRES_LOGO_MARCA)
        if ruta_marca:
            st.image(str(ruta_marca), width=tamano * 2, alt="Logo de Soluciones Digitales")
        else:
            # Mientras no exista logo.png, se escribe el nombre de la marca.
            st.markdown("**Soluciones Digitales**  \n"
                        "*«No hay trabajo tan difícil que no se pueda solucionar»*", width="content")
        ruta_tec = buscar_logo(NOMBRES_LOGO_TEC)
        if ruta_tec:
            st.image(str(ruta_tec), width=tamano, alt=f"Logo del {NOMBRE_CLIENTE}")


def encabezado(clave, titulo, descripcion):
    """Encabezado de cada pantalla: título con su ícono y una descripción."""
    with st.container(border=True):
        st.title(titulo, icon=OPCIONES[clave]["icono"])
        st.markdown(descripcion)


def tarjeta_dato(color, clave, etiqueta, valor, icono, nota=None):
    """Tarjeta con un número importante (por ejemplo: «Vigentes: 7»).

    `color` es uno de los nombres de COLORES y pinta la nota de abajo;
    `clave` solo sirve para que Streamlit distinga una tarjeta de otra.
    """
    with st.container(border=True, key=f"dato_{clave}", height="stretch"):
        st.metric(etiqueta, valor, icon=icono)
        if nota:
            st.caption(f":{COLORES[color]}[{nota}]")


def tarjeta_opcion(clave):
    """Tarjeta de una opción del menú: título, descripción y botón."""
    opcion = OPCIONES[clave]
    with st.container(border=True, key=f"tarjeta_{clave}", height="stretch"):
        st.markdown(f"#### {opcion['icono']} {opcion['titulo']}")
        st.caption(opcion["descripcion"])
        st.space("stretch")  # empuja el botón hasta abajo de la tarjeta
        st.page_link(opcion["pagina"], label="Abrir", icon=":material/arrow_forward:")


def insignia_estado(estado, repetida=False):
    """Insignia de color con ícono y texto del estado de una factura."""
    color, icono = ESTADOS_VISUAL.get(estado, ("gray", ":material/help:"))
    texto = estado + (" · ya validada" if repetida else "")
    st.badge(texto, icon=icono, color=color)


def mostrar_mensaje():
    """Muestra (una sola vez) el mensaje que dejó algún botón en session_state."""
    if "mensaje" in st.session_state:
        tipo, texto = st.session_state.pop("mensaje")
        if tipo == "success":
            st.success(texto, icon=":material/check_circle:")
        else:
            st.error(texto, icon=":material/error:")


# ---------------------------------------------------------------
# 3. Ayudantes de formato
# ---------------------------------------------------------------

def dinero(cantidad):
    """1450.0 -> '$1,450.00'"""
    return f"${cantidad:,.2f}"


def dinero_md(cantidad):
    """Igual que dinero(), pero para st.markdown: ahí el signo $ se usa para
    fórmulas matemáticas, así que hay que escribirlo como \\$."""
    return dinero(cantidad).replace("$", "\\$")


def folio_corto(uuid):
    """'00000000-0000-4000-8000-000000000003' -> '…0003'"""
    return f"…{uuid[-4:]}" if uuid else "—"


def tiempo_legible(segundos):
    """0.00042 -> '0.4 ms' ; 2.5 -> '2.5 s'"""
    if segundos < 1:
        return f"{segundos * 1000:.1f} ms"
    return f"{segundos:.1f} s"


def nombre_mes(mes):
    """'2026-11' -> 'Noviembre 2026'"""
    if mes == "Todos":
        return mes
    anio, numero = mes.split("-")
    return f"{MESES[int(numero) - 1]} {anio}"


# ---------------------------------------------------------------
# 4. Barra lateral
# ---------------------------------------------------------------

def barra_lateral(usuario):
    """Logos, quién inició sesión, cerrar sesión y opciones del jefe."""
    with st.sidebar:
        mostrar_logos()
        st.caption(f"Sistema para el {NOMBRE_CLIENTE} · Recursos Financieros")
        st.space("small")
        st.markdown(f"**{usuario['nombre']}**")
        if usuario["rol"] == "jefe":
            st.badge("Jefe", icon=":material/supervisor_account:", color="orange")
        else:
            st.badge("Auxiliar", icon=":material/person:", color="blue")
        st.button("Cerrar sesión", icon=":material/logout:", on_click=cerrar_sesion, width="stretch")

        if usuario["rol"] == "jefe":
            with st.expander("Avisos por Telegram", icon=":material/send:"):
                listo, motivo = avisos.revisar_configuracion(*credenciales_telegram())
                if listo:
                    st.badge("Configurado", icon=":material/check_circle:", color="green")
                else:
                    st.badge("Sin configurar", icon=":material/info:", color="gray")
                    st.caption(f"{motivo} Mientras tanto, los avisos solo se ven en la app.")
                st.button("Enviar mensaje de prueba", icon=":material/send:", disabled=not listo,
                          on_click=probar_telegram, width="stretch")

            with st.expander("Opciones de demostración", icon=":material/restart_alt:"):
                st.caption("Borra las facturas y validaciones para repetir la demostración "
                           "desde cero. Los usuarios no se borran.")
                confirmar = st.checkbox("Sí, quiero borrar los datos", key="confirmar_borrado")
                st.button("Reiniciar datos", icon=":material/delete_sweep:", disabled=not confirmar,
                          on_click=reiniciar_datos, width="stretch")


# ---------------------------------------------------------------
# 5. Validar facturas
# ---------------------------------------------------------------

def credenciales_telegram():
    """Token y chat_id de Telegram guardados en los secretos (secrets.toml en tu
    computadora, o «Secrets» en Streamlit Cloud). Si no hay, regresa vacíos."""
    try:
        return (str(st.secrets.get("TELEGRAM_TOKEN", "")),
                str(st.secrets.get("TELEGRAM_CHAT_ID", "")))
    except Exception:  # no existe secrets.toml
        return "", ""


def clave_gemini():
    """GEMINI_API_KEY de los secretos (secrets.toml en tu computadora, o
    «Secrets» en Streamlit Cloud). Si no hay, regresa "" y las imágenes se leen
    solo con el código QR."""
    try:
        return str(st.secrets.get("GEMINI_API_KEY", "")).strip()
    except Exception:  # no existe secrets.toml
        return ""


def validar_archivos(archivos):
    """archivos = [(nombre, contenido_en_bytes), ...]. Valida todos, manda los
    avisos y el registro a Telegram, y guarda los resultados en session_state
    para la pantalla de Resultados.

    El trabajo lo hace procesar_lote.py, el mismo que usa el bot de Telegram.
    """
    conexion = base_datos.conectar()
    token, chat_id = credenciales_telegram()
    # El avance se guarda en la base de datos: la pantalla «En vivo» lo muestra.
    progreso = Progreso("app web", len(archivos), al_cambiar=GuardarEnBD(conexion))
    resultados, registro = procesar_lote.validar_lote(
        conexion, archivos, st.session_state["usuario"]["usuario"],
        clave_gemini=clave_gemini(), token=token, chat_id=chat_id, origen="app web",
        progreso=progreso,
    )
    conexion.close()
    st.session_state["resultados"] = resultados
    st.session_state["registro"] = registro  # para decir en Resultados si llegó a Telegram
    return resultados


def validar_de_prueba():
    """Valida las 10 facturas inventadas de la carpeta facturas_prueba/."""
    return validar_archivos(procesar_lote.archivos_de_prueba())


# ---------------------------------------------------------------
# 6. Acciones de los botones (callbacks)
# ---------------------------------------------------------------
# Un "callback" es una función que Streamlit ejecuta al hacer clic en un
# botón, ANTES de volver a dibujar la página.

def cerrar_sesion():
    st.session_state.clear()  # olvida al usuario y todo lo demás


def probar_telegram():
    """Botón del jefe: manda un mensaje de prueba a Telegram."""
    respuesta = avisos.enviar_telegram(avisos.MENSAJE_PRUEBA, *credenciales_telegram())
    if respuesta["enviado"]:
        st.toast("Mensaje de prueba enviado. Revisa tu Telegram.", icon=":material/check_circle:")
    else:
        st.toast(f"No se envió: {respuesta['detalle']}", icon=":material/error:")


def reiniciar_datos():
    """Opción del jefe para repetir la demostración desde cero."""
    conexion = base_datos.conectar()
    base_datos.borrar_facturas(conexion)
    conexion.close()
    st.session_state["resultados"] = []
    st.session_state["confirmar_borrado"] = False
    st.toast("Se borraron las facturas y validaciones de prueba.", icon=":material/delete_sweep:")


def marcar_solicitada(uuid):
    """Botón del jefe: «Nueva factura solicitada»."""
    conexion = base_datos.conectar()
    base_datos.marcar_nueva_solicitada(conexion, uuid)
    conexion.close()
    st.session_state["mensaje"] = (
        "success", f"Factura {folio_corto(uuid)} marcada como «Nueva factura solicitada». "
                   "Cuando llegue la nueva, súbela aquí mismo para validarla y ligarla.")


def ligar_nueva(uuid_cancelada, clave):
    """Botón del jefe: valida la factura nueva y la liga a la cancelada (RN-04)."""
    archivo = st.session_state.get(clave)
    if archivo is None:
        return
    usuario = st.session_state["usuario"]["usuario"]
    conexion = base_datos.conectar()
    resultado = registrar_factura_nueva(conexion, uuid_cancelada, archivo.getvalue(),
                                        usuario, archivo.name)
    conexion.close()
    # También es una validación: se manda su registro a Telegram.
    procesar_lote.enviar_registro([resultado], usuario, *credenciales_telegram(),
                                  origen="app web (factura nueva para ligar)")
    st.session_state["mensaje"] = ("success" if resultado["ligada"] else "error", resultado["mensaje"])
