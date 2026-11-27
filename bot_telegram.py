"""
bot_telegram.py
---------------
Bot de Telegram del Validador de facturas. Con él, el jefe puede validar y ver
reportes desde el celular, sin abrir la página web.

Qué sabe hacer:
  - Muestra un MENÚ con botones debajo del mensaje (teclado inline):
        ✅ Validar facturas de prueba
        📊 Resumen del mes
        🔄 Reiniciar demostración
  - Si le mandas el archivo .xml o la foto (PNG/JPG) de una factura, la valida.
  - Al terminar cada validación manda el REGISTRO: si todas salieron
    correctas o cuáles requieren atención (lo arma avisos.py).
  - VIGILA la carpeta «bandeja_entrada»: cualquier factura (.xml, .png, .jpg)
    que caiga ahí se valida sola. Mientras tanto, un mensaje se va EDITANDO en
    vivo: cuántas facturas llegaron, cuántas van, cada paso (leer, comprobar el
    folio, consultar el SAT, revisar el receptor) y el porqué si alguna falla.

Cómo funciona: "long polling". El programa le pregunta a Telegram, una y otra
vez, «¿hay mensajes nuevos?». Telegram espera hasta 25 segundos a que llegue
algo y responde. No hace falta servidor ni dirección pública: basta con dejar
este programa abierto en la computadora.

Seguridad: el bot SOLO obedece al chat de TELEGRAM_CHAT_ID (el del jefe). Si
alguien más lo encuentra en Telegram, no puede validar ni borrar nada.

Cómo usarlo (en OTRA terminal, desde la carpeta del proyecto):
    python bot_telegram.py
Déjalo abierto y, en Telegram, escríbele /menu a tu bot. Ctrl + C lo detiene.

Usa la misma base de datos (validador.db) que la página web cuando los dos
corren en la misma computadora, así que lo validado aquí sale en el Historial.
"""

import shutil
import sys
import time
from pathlib import Path

import requests

import avisos
import base_datos
import procesar_lote
from lector_imagen import leer_clave_gemini
from seguimiento import GuardarEnBD, Progreso

# ---------------------------------------------------------------
# 1. Constantes
# ---------------------------------------------------------------

USUARIO_BOT = "bot_telegram"   # se guarda como "quién validó" (RN-06)
ORIGEN = "bot de Telegram"

ESPERA_LARGA = 1               # segundos que Telegram espera mensajes nuevos (corto,
                               # para revisar la carpeta bandeja_entrada seguido)
TAMANO_MAXIMO = 5 * 1024 * 1024  # 5 MB, igual que en la página web
INTERVALO_EDICION = 1.0        # el mensaje en vivo se edita como máximo 1 vez por segundo
                               # (Telegram limita las ediciones). NO se hacen pausas: la
                               # validación va a toda velocidad y el mensaje se actualiza
                               # cuando toca.

# Carpeta que el bot vigila: lo que caiga aquí se valida solo.
CARPETA_BANDEJA = procesar_lote.CARPETA_BANDEJA
SEGUNDOS_ESTABLE = 1           # un archivo se lee hasta que lleva 1 s sin cambiar
                               # (así no se lee a medias mientras se copia)
URL_ARCHIVO = "https://api.telegram.org/file/bot{token}/{ruta}"

# Teclado inline: lista de filas, cada fila es una lista de botones. Al tocar
# uno, Telegram le manda al bot el texto de "callback_data".
MENU = [
    [{"text": "✅ Validar facturas de prueba", "callback_data": "validar_prueba"}],
    [{"text": "📥 Simular llegada de facturas", "callback_data": "simular_llegada"}],
    [{"text": "📊 Resumen del mes", "callback_data": "resumen_mes"}],
    [{"text": "🔄 Reiniciar demostración", "callback_data": "reiniciar"}],
]

CONFIRMAR_REINICIO = [[
    {"text": "Sí, borrar", "callback_data": "reiniciar_si"},
    {"text": "No, cancelar", "callback_data": "menu"},
]]

# Texto cortito que aparece arriba en Telegram al tocar cada botón.
TEXTOS_ESPERA = {
    "validar_prueba": "Validando las facturas de prueba…",
    "simular_llegada": "Dejando facturas en la bandeja…",
    "resumen_mes": "Armando el resumen…",
    "reiniciar_si": "Borrando los datos de prueba…",
}

TEXTO_MENU = (
    "🧾 Validador de facturas · Soluciones Digitales\n"
    "\n"
    "Elige una opción, o mándame el archivo .xml o la foto (PNG/JPG) de una "
    "factura para validarla."
)

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")


# ---------------------------------------------------------------
# 2. Hablar con Telegram
# ---------------------------------------------------------------

def llamar(token, metodo, datos=None, tiempo=avisos.TIEMPO_ESPERA):
    """Llama a un método de la API de Telegram (getUpdates, getFile...).

    Regresa el "result" de la respuesta, o None si algo falló.
    OJO: nunca mostramos la dirección completa porque trae el token.
    """
    try:
        respuesta = requests.post(avisos.URL_API.format(token=token, metodo=metodo),
                                  json=datos or {}, timeout=tiempo)
        contenido = respuesta.json()
    except (requests.RequestException, ValueError):
        return None
    if not contenido.get("ok"):
        print(f"Telegram no aceptó «{metodo}»: {contenido.get('description', '')}")
        return None
    return contenido.get("result")


def enviar(config, texto, botones=None):
    """Manda un mensaje al chat del jefe (con botones si se indican)."""
    return avisos.enviar_telegram(texto, config["token"], config["chat_id"], botones)


def descargar_archivo(token, file_id):
    """Descarga un archivo que mandaron al bot. Regresa sus bytes, o None."""
    info = llamar(token, "getFile", {"file_id": file_id})
    if not info or "file_path" not in info:
        return None
    try:
        respuesta = requests.get(URL_ARCHIVO.format(token=token, ruta=info["file_path"]),
                                 timeout=(3, 30))
    except requests.RequestException:
        return None
    return respuesta.content if respuesta.status_code == 200 else None


# ---------------------------------------------------------------
# 3. Lo que hace cada botón
# ---------------------------------------------------------------

class MensajeEnVivo:
    """UN mensaje de Telegram que se va EDITANDO mientras se validan las facturas.

    La primera vez se manda; las siguientes veces se cambia su texto. Así el jefe
    ve en el celular cuántas facturas llegaron, cuántas van y cada paso, sin que
    el chat se llene de mensajes.
    """

    def __init__(self, config):
        self.config = config
        self.mensaje_id = None
        self.ultimo_texto = ""
        self.ultima_vez = 0.0  # cuándo se editó por última vez

    def mostrar(self, progreso):
        """Es la función "al_cambiar" del Progreso: se llama con cada cambio.

        No se espera nada: si el último cambio fue hace menos de INTERVALO_EDICION
        segundos, este se salta (el siguiente mostrará todo). Siempre se muestra el
        primer mensaje, el final y los pasos lentos de la IA.
        """
        urgente = progreso.terminado or "IA" in progreso.paso_en_curso()
        if (self.mensaje_id is not None and not urgente
                and time.monotonic() - self.ultima_vez < INTERVALO_EDICION):
            return
        texto = progreso.texto_telegram()
        if texto == self.ultimo_texto:
            return  # Telegram rechaza editar con el mismo texto
        self.ultimo_texto = texto
        if self.mensaje_id is None:
            respuesta = enviar(self.config, texto)
            self.mensaje_id = respuesta.get("mensaje_id")
        else:
            avisos.editar_telegram(texto, self.mensaje_id,
                                   self.config["token"], self.config["chat_id"])
        self.ultima_vez = time.monotonic()


def validar_y_registrar(config, archivos, origen=ORIGEN):
    """Valida los archivos con procesar_lote.py, igual que la página web.

    Mientras valida, un mensaje de Telegram se edita EN VIVO (MensajeEnVivo).
    procesar_lote manda los avisos de canceladas y el REGISTRO; aquí solo le
    pedimos que el registro lleve el menú abajo, para seguir usando el bot.
    """
    en_vivo = MensajeEnVivo(config)
    conexion = base_datos.conectar(config["ruta_bd"])
    # Cada cambio se guarda en la base de datos (lo lee la pantalla «En vivo» de
    # la página web) y se edita el mensaje de Telegram.
    progreso = Progreso(origen, len(archivos), al_cambiar=[GuardarEnBD(conexion), en_vivo.mostrar])
    try:
        resultados, registro = procesar_lote.validar_lote(
            conexion, archivos, USUARIO_BOT, clave_gemini=config["clave_gemini"],
            token=config["token"], chat_id=config["chat_id"], origen=origen, botones=MENU,
            progreso=progreso,
        )
    finally:
        conexion.close()  # se cierra aunque algo falle
    return resultados, registro


# ---------------------------------------------------------------
# 2b. La carpeta vigilada: «bandeja_entrada»
# ---------------------------------------------------------------

def archivos_nuevos_en_bandeja(carpeta=None):
    """Archivos que están en la bandeja listos para validarse.

    Se ignoran las carpetas, los archivos ocultos o temporales (empiezan con
    «.» o «~») y los que cambiaron hace menos de SEGUNDOS_ESTABLE segundos
    (todavía se están copiando).
    """
    carpeta = carpeta or CARPETA_BANDEJA
    if not carpeta.exists():
        return []
    listos = []
    for ruta in sorted(carpeta.iterdir()):
        if not ruta.is_file() or ruta.name.startswith((".", "~")):
            continue
        if time.time() - ruta.stat().st_mtime < SEGUNDOS_ESTABLE:
            continue
        listos.append(ruta)
    return listos


def mover_a(ruta, subcarpeta):
    """Mueve un archivo a bandeja_entrada/<subcarpeta>/ para no validarlo dos veces.
    Si ya hay uno con ese nombre, le agrega la hora para no pisarlo."""
    destino_carpeta = ruta.parent / subcarpeta
    destino_carpeta.mkdir(exist_ok=True)
    destino = destino_carpeta / ruta.name
    if destino.exists():
        destino = destino_carpeta / f"{ruta.stem}_{time.strftime('%H%M%S')}{ruta.suffix}"
    shutil.move(str(ruta), str(destino))


def revisar_bandeja(config, carpeta=None):
    """Valida lo que haya llegado a la bandeja. Regresa cuántas facturas llegaron.

    - .xml / .png / .jpg  -> se validan (con el mensaje en vivo) y pasan a «procesadas»
    - cualquier otra cosa o más de 5 MB -> se avisa por Telegram y pasa a «rechazadas»
    """
    rutas = archivos_nuevos_en_bandeja(carpeta)
    if not rutas:
        return 0

    aceptadas, rechazadas = [], []
    for ruta in rutas:
        bien = (ruta.suffix.lower() in procesar_lote.EXTENSIONES_ACEPTADAS
                and ruta.stat().st_size <= TAMANO_MAXIMO)
        (aceptadas if bien else rechazadas).append(ruta)

    for ruta in rechazadas:
        enviar(config, f"📂 En la bandeja llegó «{ruta.name}», pero no es una factura que pueda "
                       "leer (solo .xml, .png o .jpg de hasta 5 MB). Lo moví a «rechazadas».", MENU)
        mover_a(ruta, "rechazadas")

    if aceptadas:
        try:
            archivos = [(ruta.name, ruta.read_bytes()) for ruta in aceptadas]
            validar_y_registrar(config, archivos, origen="carpeta bandeja_entrada")
            destino = "procesadas"
        except Exception as error:  # un error no debe apagar el bot ni repetirse sin fin
            print(f"Error al validar la bandeja: {type(error).__name__}: {error}")
            enviar(config, "Ocurrió un error al validar las facturas de la bandeja. "
                           "Las moví a «con_error».", MENU)
            destino = "con_error"
        for ruta in aceptadas:
            mover_a(ruta, destino)
    return len(aceptadas)


def simular_llegada(config):
    """Botón de demostración: copia las facturas de prueba a la bandeja, como si
    los proveedores las hubieran mandado. El bot las detecta y las valida solo."""
    procesar_lote.dejar_facturas_de_prueba(CARPETA_BANDEJA)
    enviar(config, "📥 Dejé las facturas de prueba en la carpeta «bandeja_entrada». "
                   "En unos segundos el bot las detecta y las valida solo.")


def texto_resumen_mes(resumen, mes):
    """Texto del resumen del mes ("2026-11") a partir de base_datos.resumen_mes()."""
    anio, numero_mes = mes.split("-")
    renglones = [
        f"📊 Resumen de {MESES[int(numero_mes) - 1]} de {anio}",
        "",
        f"Validaciones: {resumen['validaciones']}",
        f"  ✔ Vigentes: {resumen['vigentes']}",
        f"  ✖ Canceladas: {resumen['canceladas']}",
        f"  ⚠ Receptor incorrecto: {resumen['receptor_incorrecto']}",
        f"  ? No encontradas: {resumen['no_encontradas']}",
        "",
        f"Hojas ahorradas: {resumen['hojas_ahorradas']}",
        f"Tiempo promedio: {resumen['segundos_promedio'] * 1000:.2f} milisegundos por factura",
    ]
    if not resumen["validaciones"]:
        renglones.append("\nTodavía no hay validaciones este mes.")
    return "\n".join(renglones)


def mandar_resumen(config):
    conexion = base_datos.conectar(config["ruta_bd"])
    mes = base_datos.ahora()[:7]  # "2026-11-27T10:30:00" -> "2026-11"
    resumen = base_datos.resumen_mes(conexion, mes)
    conexion.close()
    enviar(config, texto_resumen_mes(resumen, mes), MENU)


def reiniciar(config):
    conexion = base_datos.conectar(config["ruta_bd"])
    base_datos.borrar_facturas(conexion)
    conexion.close()
    enviar(config, "🔄 Listo: se borraron las facturas y validaciones de prueba. "
                   "Ya puedes repetir la demostración.", MENU)


def atender_boton(accion, config):
    """Hace lo que corresponde al botón tocado (su callback_data)."""
    if accion == "validar_prueba":
        validar_y_registrar(config, procesar_lote.archivos_de_prueba())
    elif accion == "simular_llegada":
        simular_llegada(config)
    elif accion == "resumen_mes":
        mandar_resumen(config)
    elif accion == "reiniciar":
        # Borrar es delicado: primero se pide confirmación con otros dos botones.
        enviar(config, "¿Seguro que quieres borrar TODAS las facturas y validaciones de "
                       "prueba? Los usuarios no se borran.", CONFIRMAR_REINICIO)
    elif accion == "reiniciar_si":
        reiniciar(config)
    else:  # "menu" o un botón viejo que ya no existe
        enviar(config, TEXTO_MENU, MENU)


# ---------------------------------------------------------------
# 4. Atender cada mensaje que llega
# ---------------------------------------------------------------

def es_chat_autorizado(chat_id, config):
    """Solo el chat configurado en TELEGRAM_CHAT_ID puede usar el bot."""
    return str(chat_id) == config["chat_id"]


def atender_archivo(config, nombre, file_id, tamano):
    """Un archivo o foto que mandaron al bot: lo descarga y lo valida."""
    if Path(nombre).suffix.lower() not in procesar_lote.EXTENSIONES_ACEPTADAS:
        enviar(config, f"«{nombre}» no es una factura que pueda leer. Mándame el archivo "
                       ".xml o una foto PNG/JPG (no el PDF).", MENU)
        return
    if tamano > TAMANO_MAXIMO:
        enviar(config, f"«{nombre}» pesa más de 5 MB. Mándalo más ligero.", MENU)
        return
    contenido = descargar_archivo(config["token"], file_id)
    if contenido is None:
        enviar(config, "No pude descargar el archivo de Telegram. Inténtalo otra vez.", MENU)
        return
    validar_y_registrar(config, [(nombre, contenido)])


def atender_update(update, config):
    """Decide qué hacer con una "actualización" de Telegram: un botón tocado
    (callback_query) o un mensaje (texto, archivo o foto)."""
    token = config["token"]

    # --- Tocaron un botón del teclado inline ---
    if "callback_query" in update:
        consulta = update["callback_query"]
        chat_id = consulta.get("message", {}).get("chat", {}).get("id")
        if not es_chat_autorizado(chat_id, config):
            llamar(token, "answerCallbackQuery", {"callback_query_id": consulta["id"],
                                                  "text": "Este bot es privado.",
                                                  "show_alert": True})
            return
        accion = consulta.get("data", "")
        # Hay que contestar SIEMPRE el callback: si no, el botón se queda "cargando".
        llamar(token, "answerCallbackQuery", {"callback_query_id": consulta["id"],
                                              "text": TEXTOS_ESPERA.get(accion, "")})
        atender_boton(accion, config)
        return

    # --- Llegó un mensaje ---
    mensaje = update.get("message")
    if not mensaje:
        return  # otro tipo de actualización que no usamos
    chat_id = mensaje.get("chat", {}).get("id")
    if not es_chat_autorizado(chat_id, config):
        llamar(token, "sendMessage", {"chat_id": chat_id,
                                      "text": "Este bot es privado del Validador de facturas."})
        return

    if "document" in mensaje:  # archivo .xml, o imagen mandada "como archivo"
        documento = mensaje["document"]
        atender_archivo(config, documento.get("file_name", "archivo"),
                        documento["file_id"], documento.get("file_size", 0))
    elif "photo" in mensaje:  # foto: Telegram manda varios tamaños, el último es el más grande
        foto = mensaje["photo"][-1]
        atender_archivo(config, "foto_telegram.jpg", foto["file_id"], foto.get("file_size", 0))
    else:  # /start, /menu o cualquier texto: mostrar el menú
        enviar(config, TEXTO_MENU, MENU)


# ---------------------------------------------------------------
# 5. Programa principal
# ---------------------------------------------------------------

def preparar_configuracion():
    """Lee las credenciales de .streamlit/secrets.toml. Si faltan, explica y termina."""
    token, chat_id = avisos.leer_secretos_archivo()
    listo, motivo = avisos.revisar_configuracion(token, chat_id)
    if not listo:
        print(f"No se puede iniciar el bot: {motivo}")
        sys.exit(1)
    return {
        "token": token.strip(),
        "chat_id": chat_id.strip(),
        "clave_gemini": leer_clave_gemini(),  # si no hay, las fotos se leen solo con el QR
        "ruta_bd": base_datos.RUTA_BD,
    }


def escuchar(config):
    """Ciclo infinito: pide mensajes nuevos a Telegram y los atiende."""
    token = config["token"]
    llamar(token, "deleteWebhook")  # el polling no funciona si hay un webhook puesto
    yo = llamar(token, "getMe")
    if yo is None:
        print("No se pudo conectar con Telegram. Revisa tu internet y TELEGRAM_TOKEN.")
        sys.exit(1)

    # Se ignora lo que llegó mientras el bot estaba apagado, para no repetir
    # validaciones de botones viejos.
    pendientes = llamar(token, "getUpdates", {"timeout": 0}) or []
    desplazamiento = pendientes[-1]["update_id"] + 1 if pendientes else None

    CARPETA_BANDEJA.mkdir(exist_ok=True)
    print(f"Bot @{yo['username']} escuchando. Escríbele /menu en Telegram. (Ctrl + C para detener)")
    print(f"Vigilando la carpeta: {CARPETA_BANDEJA}", flush=True)
    enviar(config, "🟢 El bot está encendido y vigila la carpeta «bandeja_entrada»: las "
                   "facturas que lleguen ahí se validan solas.\n\n" + TEXTO_MENU, MENU)

    latido = base_datos.conectar(config["ruta_bd"])  # para decirle a la página «sigo vivo»

    while True:
        base_datos.guardar_latido(latido)
        # Primero se revisa la carpeta: si llegó algo, se valida (con mensaje en vivo).
        try:
            revisar_bandeja(config)
        except Exception as error:  # la carpeta no debe apagar el bot
            print(f"Error al revisar la bandeja: {type(error).__name__}: {error}")

        datos = {"timeout": ESPERA_LARGA, "allowed_updates": ["message", "callback_query"]}
        if desplazamiento is not None:
            datos["offset"] = desplazamiento  # "ya leí hasta aquí"
        actualizaciones = llamar(token, "getUpdates", datos, tiempo=(3, ESPERA_LARGA + 10))
        if actualizaciones is None:
            print("Sin respuesta de Telegram; se reintenta en 5 segundos...")
            time.sleep(5)
            continue

        for actualizacion in actualizaciones:
            # Se avanza ANTES de atender: si algo falla, no se repite en bucle.
            desplazamiento = actualizacion["update_id"] + 1
            try:
                atender_update(actualizacion, config)
            except Exception as error:  # un error en un mensaje no debe apagar el bot
                print(f"Error al atender un mensaje: {type(error).__name__}: {error}")
                enviar(config, "Ocurrió un error al atender tu mensaje. Inténtalo otra vez.", MENU)


if __name__ == "__main__":
    try:
        escuchar(preparar_configuracion())
    except KeyboardInterrupt:
        print("\nBot detenido.")
