"""Pantalla 3: resumen, tabla y comprobantes de la última validación."""

import pandas as pd
import streamlit as st

import base_datos
import interfaz
from comprobante import (
    NOMBRES_LOGO_MARCA,
    NOMBRES_LOGO_TEC,
    buscar_logo,
    crear_comprobante_html,
    logo_como_dato,
    nombre_archivo_comprobante,
)
from validador import (
    ARCHIVO_INVALIDO,
    CANCELADA,
    ETIQUETAS,
    NO_ENCONTRADA,
    RECEPTOR_INCORRECTO,
    VIGENTE,
    formatear_fecha,
)

interfaz.encabezado("resultados", "Resultados",
                    "Esto es lo que encontró la última validación.")

resultados = st.session_state.get("resultados", [])
if not resultados:
    with st.container(border=True, horizontal_alignment="center"):
        st.image(interfaz.svg("cargar"), width=200, alt="")
        st.markdown("**Todavía no hay resultados.** Valida algunas facturas para verlas aquí.",
                    text_alignment="center")
        st.page_link(interfaz.PAG_CARGAR, label="Ir a cargar facturas", icon=":material/upload_file:")
    st.stop()  # no hay nada más que mostrar

conexion = base_datos.conectar()
nuevas = [r for r in resultados if not r["es_repetida"]]


def contar(estado):
    return sum(1 for r in nuevas if r["estado"] == estado)


tiempos = [r["segundos"] for r in resultados if r["estado"] != ARCHIVO_INVALIDO]
promedio = sum(tiempos) / len(tiempos) if tiempos else 0.0

# --- Tarjetas del resumen ---
uno, dos, tres, cuatro = st.columns(4)
with uno:
    interfaz.tarjeta_dato("verde", "res_vigentes", "Vigentes", contar(VIGENTE),
                          ":material/check_circle:", "Se pueden pagar")
with dos:
    interfaz.tarjeta_dato("rojo", "res_canceladas", "Canceladas", contar(CANCELADA),
                          ":material/cancel:", "Hay que pedir factura nueva")
with tres:
    interfaz.tarjeta_dato("naranja", "res_receptor", "Receptor incorrecto",
                          contar(RECEPTOR_INCORRECTO), ":material/warning:",
                          "No están a nombre del Tec")
with cuatro:
    interfaz.tarjeta_dato("azul", "res_tiempo", "Tiempo promedio", interfaz.tiempo_legible(promedio),
                          ":material/timer:", "Antes: de 1 a 5 minutos por factura")

otros = []
if len(resultados) - len(nuevas):
    otros.append(f"{len(resultados) - len(nuevas)} ya validada(s) antes")
if contar(NO_ENCONTRADA):
    otros.append(f"{contar(NO_ENCONTRADA)} no encontrada(s) en el SAT")
if contar(ARCHIVO_INVALIDO):
    otros.append(f"{contar(ARCHIVO_INVALIDO)} archivo(s) inválido(s)")
if otros:
    st.caption("Además: " + ", ".join(otros) + ".")

# --- Avisos de canceladas (RN-02) ---
for r in resultados:
    if r["avisar_jefe"]:
        aviso = r.get("aviso", {})
        if aviso.get("enviado"):
            estado_aviso = "✔ Se avisó al jefe por Telegram."
        else:
            estado_aviso = f"El aviso NO se envió: {aviso.get('detalle', '')} Avísale al jefe en persona."
        st.warning(
            f"{r['nombre_emisor']} · Total {interfaz.dinero_md(r['total'])} · cancelada el "
            f"{formatear_fecha(r['fecha_cancelacion'])}.  \n{estado_aviso}",
            title=f"Factura {interfaz.folio_corto(r['uuid'])} cancelada",
            icon=":material/notifications_active:",
        )

# --- Tabla ---
st.subheader("Detalle por factura", icon=":material/table_view:")
tabla = pd.DataFrame([{
    "Folio": interfaz.folio_corto(r["uuid"]),
    "Proveedor": r["nombre_emisor"] or "—",
    "Estado": ETIQUETAS[r["estado"]] + (" (ya validada)" if r["es_repetida"] else ""),
    "Total": r["total"] if r["uuid"] else None,
    "Detalle": r["mensaje"],
    "Archivo": r["archivo"],
} for r in resultados])
st.dataframe(
    interfaz.estilo_estados(tabla), hide_index=True,
    column_config={
        "Total": st.column_config.NumberColumn(format="dollar"),
        "Detalle": st.column_config.TextColumn(width="large"),
    },
    alt="Tabla con el resultado de cada factura validada",
)

# --- Comprobantes ---
st.subheader("Comprobantes", icon=":material/receipt_long:")
st.caption("Descarga el comprobante digital de cada factura. Ábrelo en el navegador para verlo, "
           "o guárdalo como PDF con Ctrl + P.")
logo_marca = logo_como_dato(buscar_logo(NOMBRES_LOGO_MARCA))
logo_tec = logo_como_dato(buscar_logo(NOMBRES_LOGO_TEC))
for numero, r in enumerate(resultados):
    id_validacion = r["id_validacion"]
    if id_validacion is None and r["uuid"]:  # repetida: usar su comprobante anterior
        id_validacion = base_datos.obtener_id_ultima_validacion(conexion, r["uuid"])
    validacion = base_datos.obtener_validacion(conexion, id_validacion) if id_validacion else None

    with st.container(border=True, horizontal=True, vertical_alignment="center",
                      key=f"fila_{numero}"):
        st.markdown(f"**{interfaz.folio_corto(r['uuid'])}** · {r['nombre_emisor'] or r['archivo']}",
                    width="stretch")
        interfaz.insignia_estado(r["estado"], r["es_repetida"])
        if validacion is None:
            st.caption("Sin comprobante", width="content")
        else:
            st.download_button(
                "Descargar", icon=":material/download:",
                data=crear_comprobante_html(validacion, logo_marca, logo_tec),
                file_name=nombre_archivo_comprobante(validacion), mime="text/html",
                key=f"comprobante_{numero}_{id_validacion}", on_click="ignore",
            )

conexion.close()
