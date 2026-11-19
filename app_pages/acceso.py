"""Pantalla 1: inicio de sesión."""

import streamlit as st

import base_datos
import interfaz

_, centro, _ = st.columns([1, 1.3, 1])
with centro:
    with st.container(border=True, key="acceso"):
        interfaz.mostrar_logos(clave="logos_acceso", tamano=96)
        with st.container(horizontal_alignment="center"):
            st.image(interfaz.svg("bienvenida"), width=210, alt="")
        st.title("Validador de facturas", text_alignment="center")
        st.markdown("Valida en segundos las facturas de los proveedores, sin teclear ni imprimir.",
                    text_alignment="center")

        if not st.session_state.get("hay_usuarios", True):
            st.error("Todavía no hay usuarios configurados. Copia .streamlit/secrets.toml.ejemplo "
                     "como secrets.toml, pon las contraseñas de prueba y vuelve a abrir la app.",
                     icon=":material/error:")

        with st.form("inicio_sesion", border=False):
            usuario = st.text_input("Usuario", placeholder="auxiliar o jefe", icon=":material/person:")
            contrasena = st.text_input("Contraseña", type="password", icon=":material/lock:")
            entrar = st.form_submit_button("Entrar", type="primary", icon=":material/login:",
                                           width="stretch")

        if entrar:
            conexion = base_datos.conectar()
            datos = base_datos.verificar_usuario(conexion, usuario, contrasena)
            conexion.close()
            if datos is None:
                st.error("Usuario o contraseña incorrectos. Revisa que estén bien escritos "
                         "(la contraseña distingue mayúsculas) y vuelve a intentarlo.",
                         icon=":material/error:")
            else:
                st.session_state["usuario"] = datos
                st.rerun()  # vuelve a cargar la app, ahora con el menú completo

        st.caption("¿No tienes cuenta? Pídela al jefe de Recursos Financieros.",
                   text_alignment="center")
