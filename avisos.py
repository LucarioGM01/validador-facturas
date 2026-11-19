"""
avisos.py
---------
Manda el aviso al jefe por Telegram cuando una factura sale cancelada (RN-02).

Usa la API de bots de Telegram: un simple POST a
    https://api.telegram.org/bot<TOKEN>/sendMessage
con el chat_id (a quién se le manda) y el texto.

Si todavía no hay token configurado, NO falla: regresa enviado=False y la app
solo muestra el aviso en pantalla.

El token y el chat_id se guardan en .streamlit/secrets.toml (que NUNCA se sube
a GitHub). Este archivo nunca muestra el token en pantalla ni en mensajes.

Ayudas desde la terminal (leen .streamlit/secrets.toml):
    python avisos.py chat     -> muestra tu chat_id (antes mándale "hola" a tu bot)
    python avisos.py prueba   -> manda un mensaje de prueba a tu Telegram
"""

import re
import sys
import tomllib
from pathlib import Path

import requests

from validador import formatear_fecha, formatear_fecha_hora

RUTA_SECRETOS = Path(__file__).parent / ".streamlit" / "secrets.toml"
URL_API = "https://api.telegram.org/bot{token}/{metodo}"

# (segundos para conectar, segundos para esperar la respuesta). Así, si no hay
# internet, la app no se queda "colgada" mucho tiempo.
TIEMPO_ESPERA = (3, 7)


# ---------------------------------------------------------------
# 1. Revisar la configuración
# ---------------------------------------------------------------

def revisar_configuracion(token, chat_id):
    """Revisa que el token y el chat_id tengan buena pinta (sin conectarse).

    Regresa (True, "") si se ven bien, o (False, "qué falta") si no.
    """
    token = str(token or "").strip()
    chat_id = str(chat_id or "").strip()
    if not token or token.startswith("pega_aqui"):
        return False, "Falta TELEGRAM_TOKEN en secrets.toml (te lo da @BotFather)."
    # Un token se ve así: 123456789:ABCdefGhIJKlmNoPQRsTUvwxYZ (número, dos puntos, letras)
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token):
        return False, "El TELEGRAM_TOKEN no tiene el formato correcto (número:letras). Cópialo otra vez."
    if not chat_id or chat_id.startswith("pega_aqui"):
        return False, "Falta TELEGRAM_CHAT_ID en secrets.toml (corre: python avisos.py chat)."
    if not re.fullmatch(r"-?\d+", chat_id):
        return False, "El TELEGRAM_CHAT_ID debe ser solo un número (por ejemplo 123456789)."
    return True, ""


# ---------------------------------------------------------------
# 2. Armar el mensaje
# ---------------------------------------------------------------

def crear_mensaje_cancelada(resultado, usuario, fecha_hora):
    """Texto del aviso de una factura cancelada.

    - resultado:  el diccionario de validador.validar_factura()
    - usuario:    quién la validó
    - fecha_hora: cuándo se validó, por ejemplo "2026-11-18T21:30:00"
    """
    return (
        "⚠️ Factura CANCELADA\n"
        "\n"
        f"Folio: …{resultado['uuid'][-4:]} ({resultado['uuid']})\n"
        f"Proveedor: {resultado['nombre_emisor']} ({resultado['rfc_emisor']})\n"
        f"Total: ${resultado['total']:,.2f}\n"
        f"Cancelada el: {formatear_fecha(resultado['fecha_cancelacion'])}\n"
        f"Validó: {usuario}, el {formatear_fecha_hora(fecha_hora)}\n"
        "\n"
        "👉 Contactar al proveedor para solicitar una nueva factura.\n"
        "\n"
        "Validador de facturas · Soluciones Digitales (prototipo con datos de prueba)"
    )


MENSAJE_PRUEBA = ("✅ Prueba del Validador de facturas (Soluciones Digitales).\n"
                  "Si lees esto, los avisos por Telegram ya funcionan.")


# ---------------------------------------------------------------
# 3. Enviar
# ---------------------------------------------------------------

def _explicar_error(codigo, descripcion):
    """Convierte la respuesta de error de Telegram en una explicación clara."""
    descripcion = descripcion.lower()
    if codigo == 401:
        return "Telegram no reconoce el token. Revisa TELEGRAM_TOKEN en secrets.toml."
    if codigo == 400 and "chat not found" in descripcion:
        return ("No se encontró el chat. Revisa TELEGRAM_CHAT_ID y que le hayas mandado "
                "un mensaje a tu bot primero.")
    if codigo == 403:
        return "El bot no puede escribirte: mándale un mensaje o desbloquéalo en Telegram."
    return f"Telegram respondió con un error (código {codigo})."


def enviar_telegram(mensaje, token, chat_id):
    """Manda `mensaje` al chat por Telegram.

    Regresa un diccionario:
        {"enviado": True,  "detalle": "Aviso enviado al jefe por Telegram."}
        {"enviado": False, "detalle": "por qué no se pudo"}
    Nunca lanza errores: si algo falla, la app sigue funcionando.
    """
    listo, motivo = revisar_configuracion(token, chat_id)
    if not listo:
        return {"enviado": False, "detalle": f"Telegram no está configurado todavía. {motivo}"}

    url = URL_API.format(token=str(token).strip(), metodo="sendMessage")
    try:
        respuesta = requests.post(
            url, json={"chat_id": str(chat_id).strip(), "text": mensaje}, timeout=TIEMPO_ESPERA
        )
    except requests.RequestException:
        # OJO: no mostramos el error original porque trae la dirección con el token.
        return {"enviado": False,
                "detalle": "No se pudo conectar con Telegram. Revisa tu conexión a internet."}

    try:
        datos = respuesta.json()
    except ValueError:
        datos = {}
    if respuesta.status_code == 200 and datos.get("ok"):
        return {"enviado": True, "detalle": "Aviso enviado al jefe por Telegram."}
    return {"enviado": False,
            "detalle": _explicar_error(respuesta.status_code, str(datos.get("description", "")))}


# ---------------------------------------------------------------
# 4. Ayudas desde la terminal
# ---------------------------------------------------------------

def _leer_secretos_archivo():
    """Lee TELEGRAM_TOKEN y TELEGRAM_CHAT_ID de .streamlit/secrets.toml."""
    if not RUTA_SECRETOS.exists():
        return "", ""
    with open(RUTA_SECRETOS, "rb") as archivo:
        secretos = tomllib.load(archivo)
    return str(secretos.get("TELEGRAM_TOKEN", "")), str(secretos.get("TELEGRAM_CHAT_ID", ""))


def _buscar_chat(token):
    """Muestra los chats que le han escrito al bot (para encontrar tu chat_id)."""
    try:
        respuesta = requests.get(URL_API.format(token=token.strip(), metodo="getUpdates"),
                                 timeout=TIEMPO_ESPERA)
        datos = respuesta.json()
    except (requests.RequestException, ValueError):
        print("No se pudo conectar con Telegram. Revisa tu conexión a internet.")
        return
    if not datos.get("ok"):
        print(_explicar_error(respuesta.status_code, str(datos.get("description", ""))))
        return

    chats = {}
    for actualizacion in datos.get("result", []):
        mensaje = actualizacion.get("message") or actualizacion.get("my_chat_member") or {}
        chat = mensaje.get("chat", {})
        if "id" in chat:
            chats[chat["id"]] = chat.get("first_name") or chat.get("title") or "(sin nombre)"
    if not chats:
        print("Tu bot todavía no tiene mensajes. Búscalo en Telegram, mándale «hola» "
              "y vuelve a correr: python avisos.py chat")
        return
    print("Chats que le escribieron a tu bot:")
    for numero, nombre in chats.items():
        print(f"  {nombre}: TELEGRAM_CHAT_ID = \"{numero}\"")
    print("Copia la línea que es tuya en .streamlit/secrets.toml")


if __name__ == "__main__":
    token_archivo, chat_archivo = _leer_secretos_archivo()
    accion = sys.argv[1] if len(sys.argv) > 1 else ""

    if accion == "chat":
        if not token_archivo.strip() or token_archivo.startswith("pega_aqui"):
            print("Primero pega tu TELEGRAM_TOKEN en .streamlit/secrets.toml (te lo da @BotFather).")
        else:
            _buscar_chat(token_archivo)
    elif accion == "prueba":
        resultado_envio = enviar_telegram(MENSAJE_PRUEBA, token_archivo, chat_archivo)
        if resultado_envio["enviado"]:
            print("Listo: revisa tu Telegram, te llegó el mensaje de prueba.")
        else:
            print("No se envió:", resultado_envio["detalle"])
    else:
        print("Uso:\n"
              "  python avisos.py chat     -> muestra tu chat_id\n"
              "  python avisos.py prueba   -> manda un mensaje de prueba")
