# Guía de uso — Validador de facturas

Esta guía es para **cualquier persona** que quiera instalar y usar el Validador
de facturas de Soluciones Digitales. No necesitas saber programar: solo seguir
los pasos en orden.

> **Importante:** el programa es un prototipo escolar. Todas las facturas, RFC y
> nombres son **inventados** y el estado «en el SAT» se **simula** con un archivo.
> No se conecta al SAT real. No lo uses con facturas reales.

---

## 1. ¿Qué hace?

Revisa facturas electrónicas (CFDI) del Departamento de Recursos Financieros y
dice, en segundos, si se pueden pagar:

| Resultado | Qué significa | Qué hacer |
|---|---|---|
| ✔ **Vigente** | Es válida y está a nombre del Tec | Se puede pagar |
| ✖ **Cancelada** | El proveedor la canceló | No se paga. Se avisa al jefe por Telegram y se pide una factura nueva |
| ⚠ **Receptor incorrecto** | Está vigente, pero no está a nombre del Tec | Pedir al proveedor que la corrija |
| ? **No encontrada** | El folio no aparece en el SAT simulado | Revisar que sea el archivo correcto |
| ⊘ **Archivo inválido** | No es un XML de factura o la imagen no se pudo leer | Mandar el `.xml` o una foto clara (no el PDF) |
| 🔍 **Lectura por revisar** | (Solo fotos) la lectura es dudosa | No pagar hasta revisarla a mano |

Puedes mandarle las facturas de **tres formas**:

1. **Subiéndolas en la página web.**
2. **Mandándolas por Telegram** al bot (por ejemplo, desde el celular).
3. **Dejándolas en la carpeta `bandeja_entrada`**: se validan solas.

Los archivos pueden ser **XML** o **imágenes** (PNG o JPG). Los PDF no se leen.

---

## 2. Dos formas de usarlo

**A) Con la página ya publicada (sin instalar nada).** Pídele al autor el enlace
y un usuario de prueba. Así puedes subir facturas y ver resultados. El bot de
Telegram y la carpeta vigilada **no** funcionan en esta forma.

**B) En tu computadora (todo completo).** Sigue la sección 3.

---

## 3. Instalación en tu computadora (Windows)

### Paso 1. Instala Python
1. Descarga **Python 3.11 o más reciente** desde <https://www.python.org/downloads/>.
2. Al instalar, **marca la casilla «Add Python to PATH»** (si no, nada funcionará).
3. Comprueba que quedó bien: abre la terminal (en Visual Studio Code: menú
   *Terminal → New Terminal*, o busca «PowerShell» en el menú Inicio) y escribe:

```bash
python --version
```
Debe decir `Python 3.11` o más.

### Paso 2. Descarga el proyecto
Opción fácil: entra a <https://github.com/LucarioGM01/validador-facturas>,
botón verde **Code → Download ZIP**, y descomprime la carpeta.

Opción con Git:
```bash
git clone https://github.com/LucarioGM01/validador-facturas.git
```

Abre la carpeta en Visual Studio Code (o abre la terminal dentro de ella).

### Paso 3. Instala las librerías
```bash
python -m pip install -r requirements.txt
```
Tarda un par de minutos la primera vez.

### Paso 4. Crea tu archivo de secretos
El programa necesita un archivo con las contraseñas de los usuarios. Se llama
`.streamlit/secrets.toml` y **no viene incluido** (por seguridad).

1. Dentro de la carpeta `.streamlit/`, copia el archivo `secrets.toml.ejemplo`
   y llama a la copia **`secrets.toml`**.
2. Ábrelo y cambia las contraseñas por las que quieras:

```toml
[usuarios.auxiliar]
contrasena = "pon-aqui-una-contrasena"
rol = "auxiliar"
nombre = "Auxiliar de Recursos Financieros"

[usuarios.jefe]
contrasena = "pon-aqui-otra-contrasena"
rol = "jefe"
nombre = "Jefe de Recursos Financieros"
```

Las líneas de `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` y `GEMINI_API_KEY` que están
arriba son **opcionales** (secciones 7 y 8). Sin ellas el programa funciona igual,
solo que sin avisos por Telegram y leyendo las fotos únicamente con el código QR.

> Si cambias `secrets.toml` más adelante, cierra la página y ábrela otra vez.

### Paso 5. Abre la página
```bash
python -m streamlit run app.py
```
Se abre sola en tu navegador (si no, entra a <http://localhost:8501>). Si la
terminal te pregunta un correo electrónico, solo presiona **Enter**.

Para **cerrar** la página: en la terminal, `Ctrl + C`.

---

## 4. Usar la página web

Entra con tu usuario (**auxiliar** o **jefe**) y tu contraseña. El menú está
arriba:

| Pantalla | Para qué sirve |
|---|---|
| **Inicio** | Resumen del mes y accesos rápidos |
| **Cargar facturas** | Subir facturas para validarlas |
| **En vivo** | Ver en tiempo real cómo llegan y se validan |
| **Resultados** | Ver lo que encontró la última validación y descargar comprobantes |
| **Historial** | Buscar cualquier factura validada y dar seguimiento a las canceladas |
| **Reporte del mes** | Totales, hojas ahorradas y tiempo ahorrado |

### Validar facturas (la primera vez, para probar)
1. Ve a **Cargar facturas**.
2. Toca **Usar facturas de prueba**: valida 10 facturas inventadas.
3. Te lleva a **Resultados**: verás cuántas salieron vigentes, canceladas y con
   receptor incorrecto, y una tabla con el motivo de cada una.

### Validar tus propias facturas
1. En **Cargar facturas**, arrastra uno o varios archivos `.xml`, `.png` o `.jpg`
   (o haz clic para buscarlos).
2. Toca **Validar todas**.
3. En **Resultados** revisa cada una. Con el botón **Descargar** de cada fila
   guardas su **comprobante** (una imagen PNG con fecha, hora y usuario).

Si subes una factura que ya estaba vigente, el programa no la repite: dice
«ya validada».

### Seguimiento de facturas canceladas (solo el jefe)
1. Ve a **Historial**. Arriba aparecen las canceladas, cada una «Pendiente».
2. Cuando pidas la factura nueva al proveedor, toca
   **Marcar «Nueva factura solicitada»**.
3. Cuando llegue la factura nueva, súbela en el recuadro y toca
   **Validar y ligar**. Si sale vigente, queda ligada a la cancelada.

   *(Para probarlo con datos de ejemplo: en la carpeta `facturas_reemplazo/` está
   `factura_11_reemplazo_de_03.xml`, que reemplaza a la factura 3.)*

### Pantalla «En vivo»
Muestra cuántas facturas llegaron, cuántas van, una barra de avance y **cada paso**
que se hace con cada factura (leer el archivo, comprobar el folio, consultar el
SAT, revisar el receptor), con el **motivo** si alguna falla. Se actualiza sola
cada 2 segundos. Arriba dice si el **bot está encendido**.

El botón **Simular llegada de facturas** deja las 10 facturas de prueba en la
carpeta `bandeja_entrada` para que el bot las valide solo (sección 6).

### Barra lateral (solo el jefe)
- **Avisos por Telegram → Enviar mensaje de prueba**: comprueba que Telegram sirve.
- **Opciones de demostración → Reiniciar datos**: marca la casilla y toca el botón
  para **borrar todas las facturas y validaciones** y repetir la demostración.
  Los usuarios no se borran.

---

## 5. Usar el bot de Telegram (opcional)

Con el bot puedes validar facturas desde el celular y recibir los avisos.

### Configurarlo (una sola vez)
1. En Telegram busca **@BotFather**, escríbele `/newbot` y sigue los pasos. Te da
   un **token** (un texto largo con dos puntos).
2. Pégalo en `.streamlit/secrets.toml`, arriba del todo:
   ```toml
   TELEGRAM_TOKEN = "el-token-que-te-dio-BotFather"
   ```
3. Busca tu bot nuevo en Telegram y mándale «hola».
4. En la terminal corre:
   ```bash
   python avisos.py chat
   ```
   Te muestra tu **chat_id** (un número). Pégalo en `secrets.toml`:
   ```toml
   TELEGRAM_CHAT_ID = "tu-numero"
   ```
5. Comprueba que funciona:
   ```bash
   python avisos.py prueba
   ```
   Te debe llegar un mensaje a Telegram.

> **El token es secreto.** No lo compartas, no lo captures en pantalla y nunca lo
> subas a GitHub. El archivo `secrets.toml` ya está excluido para que no se suba.

### Encenderlo
En **otra** terminal (deja la de la página abierta):
```bash
python bot_telegram.py
```
Déjala abierta. Para apagar el bot: `Ctrl + C`.

### Usarlo
Escríbele `/menu` a tu bot. Aparecen cuatro botones:

| Botón | Qué hace |
|---|---|
| ✅ **Validar facturas de prueba** | Valida las 10 facturas de prueba |
| 📥 **Simular llegada de facturas** | Las deja en la carpeta `bandeja_entrada` y el bot las valida solo |
| 📊 **Resumen del mes** | Manda los totales del mes |
| 🔄 **Reiniciar demostración** | Borra las facturas y validaciones (pide confirmación) |

También puedes **mandarle un archivo `.xml` o una foto** de una factura: la valida
y te contesta. Mientras valida, ves **un mensaje que se va actualizando** con
cuántas llegaron, cuántas van y el motivo de cada falla. Al final llega un
**registro** que dice si todas están correctas o cuáles requieren atención.

- **Solo tú puedes usar tu bot:** obedece únicamente al chat guardado en
  `TELEGRAM_CHAT_ID`.
- Mientras el bot está encendido, `python avisos.py chat` no funciona (los dos leen
  los mensajes del bot). Apágalo si necesitas buscar tu chat_id otra vez.

---

## 6. Facturas que llegan solas (carpeta `bandeja_entrada`)

Con el bot encendido, vigila la carpeta **`bandeja_entrada`** (se crea sola dentro
del proyecto):

1. **Copia** un `.xml`, `.png` o `.jpg` a esa carpeta (o usa «Simular llegada»).
2. En unos segundos el bot lo valida. Lo ves en Telegram y en la pantalla **En vivo**.
3. El archivo pasa a la subcarpeta `procesadas/`. Si no era una factura (por
   ejemplo un PDF) pasa a `rechazadas/`, y si hubo un error, a `con_error/`.

Diez facturas XML se validan en alrededor de **un segundo**. Las fotos tardan unos
segundos más.

> La página y el bot comparten la misma base de datos (`validador.db`), por eso
> deben estar en **la misma computadora** para que «En vivo» muestre lo que valida
> el bot.

---

## 7. Leer fotos de facturas con IA (opcional)

Las fotos se leen con **dos métodos** y se comparan: el **código QR** de la factura
y la **IA de Google (Gemini)**. Si no configuras Gemini, igual se lee el QR.

Para activar la IA:
1. Pide una clave gratuita en **Google AI Studio** (<https://aistudio.google.com/apikey>).
2. Pégala en `secrets.toml`:
   ```toml
   GEMINI_API_KEY = "tu-clave"
   ```

Si el QR y la IA **no coinciden**, la factura sale con **🔍 lectura por revisar** y
no debe pagarse hasta revisarla: puede ser un error de lectura o una factura alterada.

---

## 8. Datos de prueba incluidos

| Factura | Proveedor ficticio | Resultado esperado |
|---|---|---|
| 1, 2, 4, 5, 7, 9 y 10 | Varios | ✔ Vigente |
| 3 y 6 | Cómputo Prueba y Papelería Ejemplo | ✖ Cancelada (con aviso) |
| 8 | Imprenta Prueba | ⚠ Receptor incorrecto |
| 11 (reemplazo) | Cómputo Prueba | ✔ Vigente, se liga a la 3 |

Cada una existe como **XML** y como **imagen PNG** (con código QR) en las carpetas
`facturas_prueba/` y `facturas_reemplazo/`.

---

## 9. Problemas comunes

| Problema | Solución |
|---|---|
| `python` no se reconoce como comando | Reinstala Python y marca **«Add Python to PATH»**; cierra y abre la terminal |
| `No module named …` | Corre otra vez `python -m pip install -r requirements.txt` |
| La página dice «Todavía no hay usuarios configurados» | Falta crear `.streamlit/secrets.toml` (Paso 4) y volver a abrir la página |
| «Usuario o contraseña incorrectos» | Usa exactamente `auxiliar` o `jefe` y la contraseña de tu `secrets.toml` (distingue mayúsculas) |
| No llegan los avisos a Telegram | Revisa `TELEGRAM_TOKEN` y `TELEGRAM_CHAT_ID`, y que le hayas mandado «hola» a tu bot. Prueba con `python avisos.py prueba` |
| El bot contesta «Este bot es privado» | Tu `TELEGRAM_CHAT_ID` no es el de ese chat: corre `python avisos.py chat` (con el bot apagado) |
| En «En vivo» dice **Bot apagado** | Enciende el bot en otra terminal: `python bot_telegram.py` |
| Las fotos dicen «lectura por revisar» o no se leen | Usa una foto nítida y recta, con el QR completo; configura `GEMINI_API_KEY` (sección 7) |
| «El archivo no es una factura XML válida» | Sube el `.xml` que mandó el proveedor (no el PDF) |
| Cambié `secrets.toml` y no pasa nada | Cierra la página (`Ctrl + C`) y ábrela otra vez |
| Quiero empezar de cero | Jefe: barra lateral → *Opciones de demostración → Reiniciar datos*, o botón **Reiniciar demostración** del bot |

---

## 10. Para quien quiera revisar el código

- Pruebas automáticas (135, no necesitan internet):
  ```bash
  python -m unittest discover tests
  ```
- Ver cómo se validan las 10 facturas de prueba desde la terminal:
  ```bash
  python validador.py
  ```
- Más detalles técnicos: archivo `README.md` y el documento
  «Documentación del Validador de facturas».
