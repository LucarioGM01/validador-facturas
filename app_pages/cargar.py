"""Pantalla 2: cargar facturas."""

import streamlit as st

import interfaz

interfaz.encabezado(
    "cargar",
    "Cargar facturas",
    "Sube los archivos XML o imágenes (PNG, JPG) de las facturas. Puedes subir varios a la vez.",
)

subir, prueba = st.columns([3, 2], gap="medium")

with subir:
    with st.container(border=True, key="tarjeta_cargar", height="stretch"):
        st.subheader("Sube tus facturas", icon=":material/upload_file:")
        st.caption(
            "Arrastra aquí los archivos .xml o imágenes (.png, .jpg, .jpeg) o haz clic para buscarlos."
        )
        # La clave cambia después de validar; así el cargador queda vacío.
        clave = f"archivos_{st.session_state['id_cargador']}"
        archivos = st.file_uploader(
            "Facturas XML o imágenes",
            type=["xml", "png", "jpg", "jpeg"],
            accept_multiple_files=True,
            key=clave,
            label_visibility="collapsed",
            help="Sube el archivo .xml o una foto/captura en PNG o JPG de cada factura (no el PDF).",
        )
        if st.button(
            "Validar todas",
            type="primary",
            icon=":material/task_alt:",
            disabled=not archivos,
            width="stretch",
        ):
            with st.spinner("Validando facturas..."):
                interfaz.validar_archivos([(archivo.name, archivo.getvalue()) for archivo in archivos])
            st.session_state["id_cargador"] += 1
            st.switch_page(interfaz.PAG_RESULTADOS)

with prueba:
    with st.container(border=True, key="tarjeta_prueba", height="stretch"):
        st.subheader("Facturas de prueba", icon=":material/science:")
        st.caption(
            "10 facturas inventadas para la demostración: 7 vigentes, 2 canceladas "
            "y 1 con receptor incorrecto."
        )
        st.space("stretch")
        if st.button("Usar facturas de prueba", icon=":material/play_arrow:", width="stretch"):
            interfaz.validar_de_prueba()
            st.switch_page(interfaz.PAG_RESULTADOS)

st.subheader("Antes de empezar", icon=":material/lightbulb:")
with st.container(horizontal=True, gap="small"):
    st.badge("XML o imágenes PNG/JPG (no PDF)", icon=":material/image:", color="blue")
    st.badge("Varias facturas a la vez", icon=":material/library_add:", color="violet")
    st.badge("XML en <1s · Imágenes con QR/IA", icon=":material/bolt:", color="green")
    st.badge(
        "Si hay canceladas, se avisa al jefe",
        icon=":material/notifications_active:",
        color="orange",
    )