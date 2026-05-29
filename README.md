# 🤖 Automatización SIRE y Descarga de Comprobantes SUNAT

Este proyecto contiene un conjunto de robots (scripts) que automatizan la extracción de información del portal de SUNAT. El flujo principal se divide en dos grandes pasos:

## ⚙️ Paso 0: Configurar tus Clientes (Credenciales)

Antes de ejecutar cualquier comando, el robot necesita saber a qué empresa conectarse. Toda la configuración de tus clientes vive en un archivo CSV muy simple:

**Archivo:** `clients/sunat_clients.csv`

**Formato:**
```csv
NombreEmpresa,RUC,UsuarioSOL,ClaveSOL,Client_ID_API,Client_Secret_API
MiEmpresa_SAC,20123456789,USUARIO1,ClaveSecreta,6016db33-dd...,9WVkFC4P...
```
*(Nota: El `Client_ID` y `Client_Secret` los obtienes desde el portal de SUNAT para usar su API del SIRE).*

---

## 🔑 Paso 1: Iniciar Sesión en SUNAT (Robot Navegador)

El robot encargado de descargar los PDFs y XMLs físicos trabaja en modo "invisible" (headless), por lo que necesita que tú le "pases" una sesión válida de SUNAT primero.

**¿Cómo ejecutarlo?**
```powershell
python brain/automation_scraper.py
```
**Instrucciones:**
1. Se abrirá una ventana de Chrome visible.
2. Inicia sesión manualmente con tu RUC, Usuario y Clave.
3. Una vez adentro, navega hasta `Empresas -> Comprobantes de Pago -> SEE - SOL -> Nueva Consulta de comprobantes de pago`.
4. El robot detectará automáticamente que llegaste a esa pantalla, guardará las "cookies" (sesión) en un archivo interno (`sunat_session.json`) y cerrará la ventana.

*(¡Listo! Ya tienes permiso para que el robot trabaje invisiblemente).*

---

## 📊 Paso 2: Obtención y Transformación de la Propuesta SIRE

Este paso se conecta a las APIs internas de SUNAT para solicitar el archivo ZIP oficial con la propuesta de compras o ventas del SIRE. 

1. Se genera un "Ticket" de solicitud a SUNAT.
2. El sistema espera a que SUNAT termine de procesar el archivo.
3. Se descarga el ZIP, se extrae el archivo `.txt` nativo.
4. (Opcional pero automático) Se transforma ese TXT inentendible en un archivo **Excel (`.xlsx`)** perfectamente tabulado y con cabeceras claras.

**¿Cómo ejecutarlo?**
```powershell
# Descarga el SIRE de Compras del periodo Enero 2025
python brain/sire_download_cli.py --period 202501 --books purchases
```
*Los archivos se guardarán en: `downloads/sire/<RUC>/<PERIODO>/<LIBRO>/`*

---

## 🧾 Paso 3: Descarga de Comprobantes Físicos (XML y PDF)

Una vez que tenemos el archivo `.txt` del SIRE (el cual contiene la lista exacta de todas las facturas del mes), este segundo paso utiliza un robot de navegador invisible (Playwright) para entrar a SUNAT y descargar los archivos físicos de cada factura.

1. Lee el archivo `.txt` del SIRE para saber qué facturas buscar.
2. Navega automáticamente a la opción **"Mis Comprobantes"** en el portal SOL.
3. Busca una por una cada factura de la lista.
4. Identifica los botones de descarga de **XML** y **PDF**.
5. Descarga ambos archivos, renombrándolos ordenadamente (ej. `20611897953-01-E001-256.pdf`).

**¿Cómo ejecutarlo?**
```powershell
# Puedes pasarle la ruta exacta del archivo TXT, O puedes pasarle simplemente la CARPETA
# y el robot procesará todos los archivos .txt que encuentre ahí adentro automáticamente:
python brain/sire_xml_scrape_cli.py --sire-txt "downloads/sire/20600373065/202501/purchases" --book purchases
```
*Los archivos se guardarán en: `downloads/xml/<PERIODO>/<LIBRO>/`*

> **Opciones útiles para el Paso 2:**
> * `--limit 5`: Limita la descarga a las 5 primeras facturas (útil para pruebas).
> * `--no-skip-existing`: Fuerza al robot a descargar facturas que ya habías descargado antes (por defecto las salta para ahorrar tiempo).

---

## 🚀 ¡Todo en Uno! (Modo Automático Total)

Si quieres hacer todo el trabajo de una sola vez, el script principal tiene la capacidad de **encadenar ambos pasos automáticamente**. Primero descargará la propuesta SIRE, luego abrirá el robot navegador, descargará todos los PDFs/XMLs, y finalmente armará tu archivo Excel inyectando la información extraída de los XMLs.

**El Comando Maestro:**
```powershell
python brain/sire_download_cli.py --period 202501 --books purchases --scrape-xml
```
*Puedes añadirle `--scrape-limit 5` si solo quieres descargar 5 comprobantes.*
