"""Pantalla «En vivo»: cuántas facturas llegaron, cuántas van y cada paso de la validación."""

from datetime import datetime

import streamlit as st

import base_datos
import interfaz
import procesar_lote
from validador import formatear_fecha_hora

SEGUNDOS_REFRESCO = 2      # la pantalla se actualiza sola cada 2 segundos
SEGUNDOS_BOT_VIVO = 60     # si el bot no ha dado señales en 1 minuto, se considera apagado

interfaz.encabezado("en_vivo", "En vivo",
                    "Las facturas que llegan a la carpeta «bandeja_entrada» se validan solas. "
                    "Aquí ves cuántas llegaron, cuántas van y qué se comprueba en cada una.")


def segundos_desde(texto_iso):
    """Cuántos segundos pasaron desde una hora guardada ("2026-11-27T15:30:00")."""
    ahora = datetime.fromisoformat(base_datos.ahora())
    return (ahora - datetime.fromisoformat(texto_iso)).total_seconds()


def dejar_facturas():
    """Botón de demostración: deja las facturas de prueba en la bandeja."""
    cantidad = procesar_lote.dejar_facturas_de_prueba()
    st.toast(f"Se dejaron {cantidad} facturas en la bandeja. El bot las valida en unos segundos.",
             icon=":material/move_to_inbox:")


def mostrar_estado_del_bot(conexion, lotes):
    """Dice si el bot está encendido (por su «latido» o porque está validando)."""
    ultimo = base_datos.leer_latido(conexion)
    if lotes and not lotes[0]["terminado"]:
        ultimo = max(ultimo or "", lotes[0]["actualizado"])  # validando = está vivo
    if ultimo and segundos_desde(ultimo) < SEGUNDOS_BOT_VIVO:
        st.badge("Bot encendido: vigilando la bandeja", icon=":material/check_circle:", color="green")
    else:
        st.badge("Bot apagado", icon=":material/error:", color="red")
        st.caption("Para encenderlo, en OTRA terminal: `python bot_telegram.py`")


def mostrar_lote(lote, actual):
    """Contadores, barra de avance y lista de pasos de un grupo de facturas."""
    if lote["terminado"]:
        st.badge("Validación terminada", icon=":material/task_alt:", color="green")
    elif segundos_desde(lote["actualizado"]) > SEGUNDOS_BOT_VIVO:
        st.badge("Se detuvo antes de terminar", icon=":material/error:", color="red")
    else:
        st.badge("Validando…", icon=":material/hourglass_top:", color="orange")
    st.caption(f"Origen: {lote['origen']} · Llegaron el {formatear_fecha_hora(lote['inicio'])}")

    tarjetas = st.grid(4, min_column_width=140, gap="medium")
    with tarjetas.cell():
        interfaz.tarjeta_dato("azul", f"vivo_llegaron_{actual}", "Llegaron", lote["total"],
                              ":material/move_to_inbox:", "Facturas en este grupo")
    with tarjetas.cell():
        interfaz.tarjeta_dato("cobre", f"vivo_validadas_{actual}", "Validadas",
                              f"{lote['hechas']} de {lote['total']}", ":material/fact_check:",
                              "Ya revisadas")
    with tarjetas.cell():
        interfaz.tarjeta_dato("verde", f"vivo_correctas_{actual}", "Correctas",
                              lote["correctas"], ":material/check_circle:", "Se pueden pagar")
    with tarjetas.cell():
        interfaz.tarjeta_dato("rojo", f"vivo_problema_{actual}", "Requieren atención",
                              lote["con_problema"], ":material/warning:", "No se pueden pagar")

    avance = lote["hechas"] / lote["total"] if lote["total"] else 1.0
    st.progress(avance, text=f"{lote['hechas']} de {lote['total']} facturas validadas")
    st.markdown("**Qué se hizo con cada factura** (y por qué no se validó, si falló):")
    st.code(lote["texto"], language=None, height=420)


@st.fragment(run_every=SEGUNDOS_REFRESCO)
def pantalla_en_vivo():
    """Esta parte se vuelve a dibujar sola cada 2 segundos, sin recargar toda la página."""
    conexion = base_datos.conectar()
    lotes = base_datos.ultimos_seguimientos(conexion, limite=6)
    mostrar_estado_del_bot(conexion, lotes)
    conexion.close()

    if not lotes:
        st.info("Todavía no ha llegado ninguna factura. Deja un .xml, .png o .jpg en la carpeta "
                "«bandeja_entrada», o usa el botón de abajo para simular la llegada.",
                icon=":material/inbox:")
        return

    st.subheader("Grupo más reciente", icon=":material/bolt:")
    mostrar_lote(lotes[0], actual=lotes[0]["id"])

    if len(lotes) > 1:
        st.subheader("Grupos anteriores", icon=":material/history:")
        for lote in lotes[1:]:
            titulo = (f"{formatear_fecha_hora(lote['inicio'])} · {lote['total']} factura(s) · "
                      f"{lote['correctas']} correctas, {lote['con_problema']} con problema")
            with st.expander(titulo):
                st.code(lote["texto"], language=None, height=300)


with st.container(horizontal=True, vertical_alignment="center"):
    st.button("Simular llegada de facturas", icon=":material/move_to_inbox:", type="primary",
              on_click=dejar_facturas, key="simular_llegada")
    st.caption(f"Carpeta vigilada: `{procesar_lote.CARPETA_BANDEJA}`")

pantalla_en_vivo()
