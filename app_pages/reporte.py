"""Pantalla 5: totales del mes y comparación con el proceso anterior."""

import pandas as pd
import streamlit as st

import base_datos
import interfaz

conexion = base_datos.conectar()

interfaz.encabezado("reporte", "Reporte del mes",
                    "Cuántas facturas se validaron, cuántas salieron canceladas y cuánto se ahorró.")

meses = base_datos.meses_disponibles(conexion)
mes_actual = base_datos.ahora()[:7]
if mes_actual not in meses:
    meses.insert(0, mes_actual)
mes = st.selectbox("Mes", meses, format_func=interfaz.nombre_mes)

r = base_datos.resumen_mes(conexion, mes)
conexion.close()
if r["validaciones"] == 0:
    with st.container(border=True, horizontal_alignment="center"):
        st.image(interfaz.svg("reporte"), width=200, alt="")
        st.markdown("**No hay validaciones en ese mes.**", text_alignment="center")
    st.stop()

# --- Tarjetas ---
datos = st.grid(3, min_column_width=200, gap="medium")
tarjetas = [
    ("azul", "rep_validadas", "Facturas validadas", r["validaciones"], ":material/receipt_long:", "En el mes"),
    ("verde", "rep_vigentes", "Vigentes", r["vigentes"], ":material/check_circle:", "Listas para pago"),
    ("rojo", "rep_canceladas", "Canceladas", r["canceladas"], ":material/cancel:", "Con aviso al jefe"),
    ("naranja", "rep_receptor", "Receptor incorrecto", r["receptor_incorrecto"], ":material/warning:",
     "Por corregir"),
    ("verde", "rep_hojas", "Hojas ahorradas", r["hojas_ahorradas"], ":material/eco:",
     "Ya no se imprimen"),
    ("violeta", "rep_tiempo", "Tiempo promedio", interfaz.tiempo_legible(r["segundos_promedio"]),
     ":material/timer:", "Por factura"),
]
for color, clave, etiqueta, valor, icono, nota in tarjetas:
    with datos.cell():
        interfaz.tarjeta_dato(color, clave, etiqueta, valor, icono, nota)

# --- Antes y después ---
st.subheader("Antes y después", icon=":material/compare_arrows:")
horas_antes = r["validaciones"] * interfaz.MINUTOS_ANTES / 60
comparacion = pd.DataFrame([
    {"Concepto": "Tiempo por factura", "Antes (manual)": "1 a 5 minutos",
     "Ahora (con la app)": interfaz.tiempo_legible(r["segundos_promedio"])},
    {"Concepto": f"Tiempo total de {r['validaciones']} facturas",
     "Antes (manual)": f"≈ {horas_antes:.1f} horas",
     "Ahora (con la app)": interfaz.tiempo_legible(r["validaciones"] * r["segundos_promedio"])},
    {"Concepto": "Hojas impresas", "Antes (manual)": str(r["validaciones"]),
     "Ahora (con la app)": "0"},
    {"Concepto": "Aviso de facturas canceladas", "Antes (manual)": "En persona, con la hoja impresa",
     "Ahora (con la app)": "Automático por Telegram"},
])
st.dataframe(comparacion, hide_index=True, alt="Comparación del proceso manual contra la app")
st.caption(f"El «antes» usa {interfaz.MINUTOS_ANTES} minutos por factura, el promedio del rango de "
           "1 a 5 minutos del proceso manual.")
