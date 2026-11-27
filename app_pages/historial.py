"""Pantalla 4: buscar facturas validadas y (el jefe) dar seguimiento a canceladas."""

import pandas as pd
import streamlit as st

import base_datos
import interfaz
from comprobante import comprobante_png, nombre_archivo_comprobante
from validador import (
    CANCELADA,
    ETIQUETAS,
    NO_ENCONTRADA,
    RECEPTOR_INCORRECTO,
    VIGENTE,
    formatear_fecha,
    formatear_fecha_hora,
)

usuario = st.session_state["usuario"]
conexion = base_datos.conectar()

interfaz.encabezado("historial", "Historial",
                    "Busca cualquier factura validada y descarga su comprobante.")
interfaz.mostrar_mensaje()

# --- Seguimiento de canceladas (solo el jefe) ---
if usuario["rol"] == "jefe":
    st.subheader("Seguimiento de canceladas", icon=":material/assignment_late:")
    st.caption("Marca cuándo pediste la factura nueva al proveedor y, cuando llegue, súbela "
               "aquí: pasa por la misma validación y queda ligada a la cancelada (RN-04).")
    canceladas = base_datos.buscar_facturas(conexion, estado=CANCELADA)
    if not canceladas:
        st.success("No hay facturas canceladas.", icon=":material/celebration:")

    for numero, factura in enumerate(canceladas):
        uuid = factura["uuid"]
        with st.container(border=True):
            with st.container(horizontal=True, vertical_alignment="center"):
                st.markdown(f"**{interfaz.folio_corto(uuid)} · {factura['nombre_emisor']}**",
                            width="stretch")
                # Cada cancelada pasa por 3 etapas: pendiente -> solicitada -> reemplazada.
                if factura["uuid_reemplazo"]:
                    st.badge("Reemplazada", icon=":material/task_alt:", color="green")
                elif factura["nueva_solicitada"]:
                    st.badge("Factura nueva solicitada", icon=":material/forward_to_inbox:",
                             color="blue")
                else:
                    st.badge("Pendiente", icon=":material/pending_actions:", color="orange")
            st.caption(f"RFC {factura['rfc_emisor']} · Total {interfaz.dinero_md(factura['total'])} "
                       f"· Cancelada el {formatear_fecha(factura['fecha_cancelacion'])}")

            if factura["uuid_reemplazo"]:
                st.markdown(f":green[:material/link: Ligada a la factura nueva "
                            f"**{interfaz.folio_corto(factura['uuid_reemplazo'])}**]")
            elif not factura["nueva_solicitada"]:
                st.button("Marcar «Nueva factura solicitada»", icon=":material/forward_to_inbox:",
                          key=f"solicitar_{uuid}", on_click=interfaz.marcar_solicitada,
                          args=(uuid,), type="primary")
            else:
                st.caption(f"Solicitada el {formatear_fecha_hora(factura['fecha_solicitud'])}. "
                           "Sube aquí la factura nueva:")
                clave = f"nueva_{uuid}"
                archivo = st.file_uploader("Factura nueva (XML)", key=clave,
                                           label_visibility="collapsed")
                st.button("Validar y ligar", icon=":material/link:", key=f"ligar_{uuid}",
                          disabled=archivo is None, on_click=interfaz.ligar_nueva,
                          args=(uuid, clave), type="primary")

# --- Búsqueda ---
st.subheader("Buscar facturas", icon=":material/search:")
columna_texto, columna_estado, columna_mes = st.columns([2, 1, 1])
texto = columna_texto.text_input("Proveedor o folio", placeholder="Ej. papelería o 0003",
                                 icon=":material/search:")
estado = columna_estado.selectbox(
    "Estado", ["Todos", VIGENTE, CANCELADA, RECEPTOR_INCORRECTO, NO_ENCONTRADA])
mes = columna_mes.selectbox("Mes", ["Todos"] + base_datos.meses_disponibles(conexion),
                            format_func=interfaz.nombre_mes)

facturas = base_datos.buscar_facturas(
    conexion, texto=texto,
    estado="" if estado == "Todos" else estado,
    mes="" if mes == "Todos" else mes,
)
if not facturas:
    st.info("No se encontraron facturas con esos filtros. Prueba quitando alguno.",
            icon=":material/search_off:")
    st.stop()

st.caption(f"{len(facturas)} factura(s) encontrada(s).")
tabla = pd.DataFrame([{
    "Folio": interfaz.folio_corto(f["uuid"]),
    "Proveedor": f["nombre_emisor"],
    "Estado": ETIQUETAS.get(f["estado"], f["estado"]),
    "Total": f["total"],
    "Última validación": formatear_fecha_hora(f["ultima_validacion"]),
    "Nueva solicitada": "Sí" if f["nueva_solicitada"] else ("No" if f["estado"] == CANCELADA else "—"),
    "Reemplazada por": interfaz.folio_corto(f["uuid_reemplazo"]) if f["uuid_reemplazo"] else "—",
    "RFC proveedor": f["rfc_emisor"],
    "Folio fiscal completo": f["uuid"],
} for f in facturas])
st.dataframe(tabla, hide_index=True,
             column_config={"Total": st.column_config.NumberColumn(format="dollar")},
             alt="Tabla del historial de facturas validadas")

# --- Descargar un comprobante ---
nombres = {f["uuid"]: f"{interfaz.folio_corto(f['uuid'])} · {f['nombre_emisor']}" for f in facturas}
with st.container(horizontal=True, vertical_alignment="bottom"):
    elegida = st.selectbox("Comprobante de la factura", list(nombres), format_func=nombres.get)
    validacion = base_datos.obtener_validacion(
        conexion, base_datos.obtener_id_ultima_validacion(conexion, elegida))
    st.download_button(
        "Descargar comprobante", icon=":material/download:",
        data=comprobante_png(validacion),
        file_name=nombre_archivo_comprobante(validacion), mime="image/png", on_click="ignore",
    )

conexion.close()
