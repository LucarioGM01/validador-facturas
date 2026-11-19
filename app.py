"""
app.py
------
Página web del Validador de facturas de Soluciones Digitales, hecha con
Streamlit, para el Departamento de Recursos Financieros del Instituto
Tecnológico de Matehuala.

Cómo abrirla (en la terminal, desde la carpeta del proyecto):
    python -m streamlit run app.py

Este archivo solo prepara todo y arma el menú. Cada pantalla está en su
propio archivo dentro de app_pages/:
    acceso.py      -> inicio de sesión
    inicio.py      -> resumen y accesos rápidos
    cargar.py      -> cargar facturas
    resultados.py  -> resultados de la última validación
    historial.py   -> búsqueda y seguimiento de canceladas (jefe)
    reporte.py     -> reporte del mes

Cómo piensa Streamlit: cada vez que alguien hace clic o escribe algo, vuelve
a ejecutar el programa de arriba a abajo. Lo que hay que "recordar" entre
clics (quién inició sesión, los últimos resultados...) se guarda en
st.session_state, que funciona como un diccionario.
"""

import streamlit as st

import base_datos
import interfaz

st.set_page_config(
    page_title="Validador de facturas · Soluciones Digitales",
    page_icon=":material/receipt_long:",
    layout="wide",
)
interfaz.aplicar_estilos()


@st.cache_resource
def preparar_usuarios():
    """Crea en la base de datos los usuarios que están en secrets.toml.

    @st.cache_resource hace que esta función corra UNA sola vez mientras la
    app esté abierta (no en cada clic). Si cambias secrets.toml, reinicia la app.
    Regresa (cuántos usuarios se crearon, lista de errores).
    """
    try:
        usuarios = dict(st.secrets.get("usuarios", {}))
    except Exception:  # no existe secrets.toml
        usuarios = {}

    conexion = base_datos.conectar()
    errores = []
    for usuario, datos in usuarios.items():
        try:
            base_datos.crear_usuario(conexion, usuario, datos["contrasena"], datos["rol"],
                                     datos.get("nombre", usuario))
        except (KeyError, ValueError) as error:
            errores.append(f"El usuario «{usuario}» de secrets.toml está mal escrito: {error}")
    conexion.close()
    return len(usuarios) - len(errores), errores


cantidad_usuarios, errores = preparar_usuarios()
for error in errores:
    st.error(error, icon=":material/error:")

# Valores iniciales de lo que se recuerda entre clics.
st.session_state.setdefault("id_cargador", 0)
st.session_state.setdefault("resultados", [])
st.session_state["hay_usuarios"] = cantidad_usuarios > 0

usuario = st.session_state.get("usuario")

if usuario is None:
    # Sin sesión iniciada solo existe la pantalla de acceso: un usuario sin
    # cuenta no puede abrir ninguna otra (aunque escriba su dirección).
    menu = st.navigation(
        [st.Page(interfaz.PAG_ACCESO, title="Iniciar sesión", icon=":material/login:")],
        position="hidden",
    )
else:
    interfaz.barra_lateral(usuario)
    menu = st.navigation(
        [
            st.Page(opcion["pagina"], title=opcion["titulo"], icon=opcion["icono"],
                    default=(clave == "inicio"))
            for clave, opcion in interfaz.OPCIONES.items()
        ],
        position="top",  # menú arriba, con un ícono para cada opción
    )

menu.run()
