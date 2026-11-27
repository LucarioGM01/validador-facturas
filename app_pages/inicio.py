"""Pantalla de inicio: saludo, números del mes y una tarjeta para cada opción."""

import streamlit as st

import base_datos
import interfaz
from validador import CANCELADA

usuario = st.session_state["usuario"]
conexion = base_datos.conectar()

primer_nombre = usuario["nombre"].split()[0] if usuario["nombre"] else usuario["usuario"]
interfaz.encabezado("inicio", f"Hola, {primer_nombre}",
                    "¿Qué quieres hacer hoy? Elige una opción o revisa cómo va el mes.")

# --- Pendientes del jefe ---
canceladas = base_datos.buscar_facturas(conexion, estado=CANCELADA)
pendientes = [f for f in canceladas if not f["uuid_reemplazo"]]
if usuario["rol"] == "jefe" and pendientes:
    with st.container(border=True, key="cancelada_aviso", horizontal=True,
                      vertical_alignment="center"):
        st.markdown(f"**Tienes {len(pendientes)} factura(s) cancelada(s) sin factura nueva.** "
                    "Revisa el seguimiento para pedirla al proveedor.", width="stretch")
        st.page_link(interfaz.PAG_HISTORIAL, label="Ir al seguimiento",
                     icon=":material/arrow_forward:")

# --- Números del mes ---
mes = base_datos.ahora()[:7]
resumen = base_datos.resumen_mes(conexion, mes)
horas = resumen["validaciones"] * interfaz.MINUTOS_ANTES / 60
st.subheader(f"Así va {interfaz.nombre_mes(mes).lower()}", icon=":material/calendar_month:")
uno, dos, tres, cuatro = st.columns(4)
with uno:
    interfaz.tarjeta_dato("azul", "ini_validadas", "Validadas", resumen["validaciones"],
                          ":material/receipt_long:", "Facturas revisadas este mes")
with dos:
    interfaz.tarjeta_dato("verde", "ini_vigentes", "Vigentes", resumen["vigentes"],
                          ":material/check_circle:", "Se pueden pagar")
with tres:
    interfaz.tarjeta_dato("rojo", "ini_pendientes", "Por reponer", len(pendientes),
                          ":material/pending_actions:", "Canceladas sin factura nueva")
with cuatro:
    interfaz.tarjeta_dato("cobre", "ini_horas", "Horas ahorradas", f"{horas:.1f}",
                          ":material/savings:", "Contra el proceso manual")

# --- Opciones ---
st.subheader("¿Qué quieres hacer?", icon=":material/apps:")
opciones = st.grid(5, min_column_width=160, gap="medium")
for clave in ["cargar", "en_vivo", "resultados", "historial", "reporte"]:
    with opciones.cell():
        interfaz.tarjeta_opcion(clave)

conexion.close()
