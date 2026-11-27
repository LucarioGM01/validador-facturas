# Validador de facturas — Soluciones Digitales

> «No hay trabajo tan difícil que no se pueda solucionar»

Prototipo escolar que automatiza la validación de facturas (CFDI 4.0) del
Departamento de Recursos Financieros del Instituto Tecnológico de Matehuala.

La aplicación lee los archivos XML de las facturas, consulta su estado
(Vigente o Cancelada) en una base **simulada**, guarda un comprobante digital
de cada validación y avisa al jefe por Telegram cuando una factura sale cancelada.

**¿Eres nuevo aquí?** Lee la [Guía de uso](GUIA_DE_USO.md): explica paso a paso cómo
instalarlo y usarlo.

**Importante:** todo el proyecto usa datos inventados. No contiene facturas,
RFC ni nombres reales, y no se conecta al SAT.

## Requisitos

- Python 3.11 o más reciente (marca «Add Python to PATH» al instalarlo)
- Visual Studio Code (u otro editor)
- Conexión a internet (solo para instalar librerías y mandar avisos a Telegram)

## Instalación

Abre esta carpeta en Visual Studio Code, abre la terminal
(menú *Terminal → New Terminal*) y escribe:

```bash
python -m pip install -r requirements.txt
```

## Cómo ejecutar

| Qué | Comando | Disponible desde |
|---|---|---|
| Generar las 10 facturas de prueba | `python generar_facturas.py` | Paso 2 |
| Ver qué datos lee de cada factura | `python lector_xml.py` | Paso 3 |
| Ver cómo se validan las 10 facturas | `python validador.py` | Paso 4 |
| Correr las pruebas | `python -m unittest discover tests -v` | Paso 3 |
| Abrir la aplicación | `python -m streamlit run app.py` | Paso 5 |
| Encender el bot de Telegram (en otra terminal) | `python bot_telegram.py` | Paso 7 |

## Usuarios de prueba

La app tiene dos usuarios: **auxiliar** (valida facturas) y **jefe** (da
seguimiento a las canceladas y liga la factura nueva). Sus contraseñas de
prueba están en `.streamlit/secrets.toml`, que no se sube a GitHub. Para crear
ese archivo en otra computadora, copia `.streamlit/secrets.toml.ejemplo` y
cambia las contraseñas. Si cambias `secrets.toml`, cierra y vuelve a abrir la app.

## Avisos por Telegram

Cuando una factura sale cancelada, la app avisa al jefe por Telegram (RN-02).
Si Telegram no está configurado, la app sigue funcionando y el aviso solo se ve
en pantalla.

1. En Telegram, busca a **@BotFather** (palomita azul), escríbele `/newbot` y
   sigue los pasos. Te dará un **token**.
2. Pega el token en `.streamlit/secrets.toml`: `TELEGRAM_TOKEN = "..."`.
3. Busca tu bot nuevo en Telegram y mándale «hola».
4. Corre `python avisos.py chat`: te muestra tu `TELEGRAM_CHAT_ID`. Pégalo en
   `secrets.toml`.
5. Corre `python avisos.py prueba`: te debe llegar un mensaje.
6. Reinicia la app. El jefe ve «Configurado» en la barra lateral, en
   *Avisos por Telegram*.

El token es secreto: nunca lo subas a GitHub ni lo compartas.

Al terminar **cada validación** (desde la app o desde el bot) llega además un
**registro**: dice si todas las facturas están correctas o cuántas requieren
atención, con el desglose y los datos de cada una.

### Bot de Telegram (validar desde el celular)

Con Telegram ya configurado (pasos de arriba), abre **otra** terminal y escribe:

```bash
python bot_telegram.py
```

Déjala abierta y escríbele `/menu` a tu bot. Aparecen tres botones:
**Validar facturas de prueba**, **Resumen del mes** y **Reiniciar demostración**
(este último pide confirmación). También puedes mandarle el `.xml` o la foto de
una factura para validarla. Para apagar el bot: `Ctrl + C`.

### Facturas que llegan solas y avance en vivo

Con el bot encendido, **vigila la carpeta `bandeja_entrada/`** (se crea sola):
cualquier `.xml`, `.png` o `.jpg` que caiga ahí se valida automáticamente y
pasa a `bandeja_entrada/procesadas/`. Lo que no sea una factura (por ejemplo un
PDF) pasa a `rechazadas/`.

Mientras se valida, el avance se ve **en tiempo real** en dos lugares:

- **Telegram:** un mensaje que se edita solo y dice cuántas facturas llegaron,
  cuántas van, cuántas son correctas y cuáles requieren atención, con el motivo
  de cada falla (por ejemplo «Cancelada el 05/11/2026»).
- **Página web → «En vivo»:** los mismos contadores, una barra de avance y todos
  los pasos de cada factura (leer el archivo, comprobar el folio, consultar el
  SAT, revisar el receptor). Se actualiza sola cada 2 segundos.

Para probarlo sin copiar archivos, usa el botón **Simular llegada de facturas**
(en Telegram o en la página «En vivo»). Diez facturas se validan en alrededor de
un segundo; las fotos tardan unos segundos más porque las lee la IA.

La pantalla «En vivo» lee la base de datos que escribe el bot, así que solo
funciona cuando la página y el bot corren en la misma computadora.

- El bot solo obedece al chat de `TELEGRAM_CHAT_ID`; nadie más puede usarlo.
- Corre en tu computadora y usa la misma base de datos que la app local. La
  app publicada en Streamlit Cloud tiene su propia base de datos, así que lo
  que valides con el bot no aparece allá.
- Mientras el bot está encendido, `python avisos.py chat` no funciona (los dos
  leen los mensajes del bot). Apaga el bot si necesitas buscar tu chat_id.

## Publicar en internet (Streamlit Community Cloud)

1. Subir el código a GitHub con `git` (respeta `.gitignore`, así que
   `secrets.toml` y la base de datos no se suben).
2. En [share.streamlit.io](https://share.streamlit.io) → **Create app** →
   repositorio `validador-facturas`, rama `main`, archivo `app.py`.
3. En **Advanced settings**: Python 3.12 y, en **Secrets**, pegar el contenido
   de `.streamlit/secrets.toml`.
4. **Deploy**. La app queda en `https://<nombre>.streamlit.app`.

En la nube la base de datos se borra cuando la app se reinicia o se duerme
(12 horas sin visitas); como solo tiene datos de prueba, no hay problema.

## Estructura del proyecto

```
├── app.py                     → arranca la página web y arma el menú
├── interfaz.py                → logos, encabezados y tarjetas que comparten las pantallas (solo Python)
├── app_pages/                 → una pantalla por archivo
│   ├── acceso.py              → inicio de sesión
│   ├── inicio.py              → resumen del mes y accesos rápidos
│   ├── cargar.py              → cargar facturas
│   ├── en_vivo.py             → llegada y validación de facturas en tiempo real
│   ├── resultados.py          → resultados y comprobantes
│   ├── historial.py           → búsqueda y seguimiento de canceladas (jefe)
│   └── reporte.py             → reporte del mes
├── lector_xml.py              → lee los datos de un XML de factura
├── validador.py               → consulta el estado y aplica las reglas de negocio
├── base_datos.py              → guarda y consulta en SQLite
├── comprobante.py             → dibuja el comprobante digital descargable (imagen PNG)
├── avisos.py                  → arma y manda los avisos y el registro a Telegram
├── procesar_lote.py           → valida un grupo de facturas (lo usan la app y el bot)
├── bot_telegram.py            → bot de Telegram: botones, carpeta vigilada y mensaje en vivo
├── seguimiento.py             → lleva el avance en vivo (cuántas van, cada paso, por qué falló)
├── bandeja_entrada/           → las facturas que caen aquí se validan solas (no se sube a GitHub)
├── generar_facturas.py        → crea 10 facturas XML de prueba
├── logo.png                   → logo de Soluciones Digitales (se agrega a mano)
├── logo_tec.png               → logo del Instituto Tecnológico de Matehuala
├── datos/
│   └── estados_sat_simulado.csv → estados simulados (uuid, estado, fecha_cancelacion)
├── facturas_prueba/           → aquí se guardan las 10 facturas de prueba
├── tests/
│   ├── test_lector_xml.py     → pruebas del lector de XML
│   ├── test_validador.py      → pruebas de las reglas de negocio (RN-01 a RN-07)
│   ├── test_base_datos.py     → pruebas de usuarios, historial y reporte
│   ├── test_comprobante.py    → pruebas del comprobante descargable
│   └── test_avisos.py         → pruebas del aviso por Telegram (sin conectarse)
├── validador.db               → base de datos SQLite (se crea sola, NO se sube)
├── .streamlit/
│   ├── config.toml            → colores de la marca
│   ├── secrets.toml           → contraseñas de prueba y token de Telegram (NO se sube)
│   └── secrets.toml.ejemplo   → ejemplo de cómo llenar secrets.toml
├── requirements.txt           → librerías que hay que instalar
└── .gitignore                 → archivos que git no debe subir
```

## Herramientas

Python 3, Streamlit, SQLite, pandas, requests, unittest, bot de Telegram,
GitHub y Streamlit Community Cloud. Todas son gratuitas.

## Uso de IA

El código de este prototipo se hizo con ayuda de IA (Claude) y fue revisado
y probado por el equipo.
