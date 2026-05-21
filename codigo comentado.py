# Importa el modulo recolector de basura.
# Se usa para liberar memoria RAM manualmente en MicroPython.
import gc

# Importa funciones relacionadas con tiempo.
# Permite usar delays, timestamps y control temporal.
import time

# Libreria para manejar datos JSON en MicroPython.
# Se usa para enviar informacion en formato JSON al servidor web.
import ujson

# Libreria para manejar sensores DHT11 y DHT22.
import dht

# Importa asyncio adaptado para MicroPython.
# Permite ejecutar varias tareas "simultaneamente".
import uasyncio as asyncio

# Libreria para manejo de red WiFi.
import network

# Libreria para realizar solicitudes HTTP.
# Se usa para comunicarse con Telegram.
import urequests


# Importa clases de hardware desde machine.
# Pin -> manejo de GPIO
# I2C -> comunicacion I2C
# PWM -> generar señales PWM para buzzer
from machine import Pin, I2C, PWM

# Importa la clase MPU6050 desde el archivo mpu6050.py
from mpu6050 import MPU6050


# ======================================================
# CONFIGURACION GENERAL
# ======================================================

# Comentario importante sobre el tipo de sensor DHT usado.

# Define el tipo de sensor DHT.
# Puede ser "DHT11" o "DHT22".
TIPO_DHT = "DHT11"

# Configuracion de Telegram.
# BOT_TOKEN es el token del bot creado con BotFather.
BOT_TOKEN = "8714231259:AAFgi3bfxKQXWop5iThKQC0tMV80P_EPDMM"

# CHAT_ID es el ID del chat donde se enviaran mensajes.
CHAT_ID = "8889804535"

# ==========================
# CONFIGURACION DE PINES
# ==========================

# GPIO donde esta conectado el DHT.
PIN_DHT = 4

# GPIO SDA del bus I2C.
PIN_SDA = 21

# GPIO SCL del bus I2C.
PIN_SCL = 22

# GPIO del buzzer.
PIN_BUZZER = 27

# GPIO del pulsador de panico.
PIN_PULSADOR = 18


# ==========================
# UMBRALES AMBIENTALES
# ==========================

# Temperatura minima permitida.
TEMP_MIN = 18.0

# Temperatura maxima permitida.
TEMP_MAX = 35.0

# Humedad minima permitida.
HUM_MIN = 40.0

# Humedad maxima permitida.
HUM_MAX = 70.0


# ==========================
# UMBRALES DE MOVIMIENTO
# ==========================

# Magnitud considerada movimiento normal.
MOV_NORMAL_G = 1.15

# Magnitud considerada movimiento brusco.
MOV_BRUSCO_G = 1.80


# ==========================
# INTERVALOS DE OPERACION
# ==========================

# Tiempo entre lecturas de sensores.
INTERVALO_SENSORES = 2

# Tiempo entre revisiones del bot Telegram.
INTERVALO_TELEGRAM = 5

# Tiempo minimo entre alertas repetidas.
ANTI_SPAM_ALERTA = 60


# ======================================================
# INICIALIZACION DE HARDWARE
# ======================================================

# Verifica si el tipo de DHT es DHT11.
if TIPO_DHT.upper() == "DHT11":

    # Crea objeto sensor DHT11 en el pin definido.
    sensor_dht = dht.DHT11(Pin(PIN_DHT))

# Si no es DHT11 entonces usa DHT22.
else:

    # Crea objeto sensor DHT22.
    sensor_dht = dht.DHT22(Pin(PIN_DHT))


# Inicializa el bus I2C.
# I2C(0) -> canal I2C numero 0
# sda -> pin SDA
# scl -> pin SCL
# freq -> frecuencia de comunicacion
i2c = I2C(0, sda=Pin(PIN_SDA), scl=Pin(PIN_SCL), freq=400000)

# Inicializa el sensor MPU6050 usando I2C.
mpu = MPU6050(i2c)


# Configura el buzzer usando PWM.
buzzer = PWM(Pin(PIN_BUZZER))

# Apaga inicialmente el buzzer.
buzzer.duty(0)


# Configura el pulsador como entrada con resistencia pull-up.
# Cuando se presiona el boton el valor sera 0.
pulsador = Pin(PIN_PULSADOR, Pin.IN, Pin.PULL_UP)


# ======================================================
# ESTADO GLOBAL
# ======================================================

# Diccionario que almacena el estado general del sistema.
estado = {

    # Temperatura actual.
    "temperatura": None,

    # Humedad actual.
    "humedad": None,

    # Aceleracion en eje X.
    "ax": 0.0,

    # Aceleracion en eje Y.
    "ay": 0.0,

    # Aceleracion en eje Z.
    "az": 0.0,

    # Magnitud total de aceleracion.
    "magnitud_g": 1.0,

    # Estado del movimiento.
    "movimiento": "SIN DATO",

    # Estado de alarmas.
    "alarma": "INICIANDO",

    # Estado del boton panico.
    "panico": "INACTIVO",

    # Direccion IP.
    "ip": "SIN IP",

    # Estado de lectura del DHT.
    "dht_ok": False,

    # Ultima actualizacion.
    "ultima_actualizacion": "SIN DATO"
}

# Diccionario para controlar spam de alertas.
ultimo_envio_alerta = {}

# Offset para Telegram.
telegram_offset = 0


# ======================================================
# FUNCIONES AUXILIARES
# ======================================================

# Funcion para obtener la IP del ESP32.
def obtener_ip():

    # Obtiene la interfaz WiFi en modo estacion.
    wlan = network.WLAN(network.STA_IF)

    # Verifica si esta conectado.
    if wlan.isconnected():

        # Devuelve la IP.
        return wlan.ifconfig()[0]

    # Si no hay conexion retorna mensaje.
    return "SIN CONEXION WIFI"


# Funcion para codificar caracteres especiales en URL.
def url_encode(texto):

    """
    Convierte caracteres especiales para que Telegram
    pueda recibir el mensaje correctamente.
    """

    # Convierte a string.
    texto = str(texto)

    # Diccionario de reemplazos.
    reemplazos = {

        # Reemplazos URL.
        "%": "%25",
        " ": "%20",
        "\n": "%0A",
        ":": "%3A",
        "/": "%2F",
        "#": "%23",
        "&": "%26",
        "?": "%3F",
        "=": "%3D",
        "+": "%2B",

        # Simbolo grados.
        "°": "%C2%B0",

        # Elimina signo de admiracion invertido.
        "¡": "",

        # Signo admiracion normal.
        "!": "%21",

        # Reemplaza vocales acentuadas.
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",

        # Mayusculas acentuadas.
        "Á": "A",
        "É": "E",
        "Í": "I",
        "Ó": "O",
        "Ú": "U",

        # Letra ñ.
        "ñ": "n",
        "Ñ": "N"
    }

    # Recorre todos los reemplazos.
    for original, codificado in reemplazos.items():

        # Reemplaza caracteres.
        texto = texto.replace(original, codificado)

    # Devuelve texto codificado.
    return texto
# ======================================================
# FUNCION PARA VERIFICAR TELEGRAM
# ======================================================

# Verifica si BOT_TOKEN y CHAT_ID estan configurados.
def telegram_configurado():

    # Retorna True si los datos son validos.
    return (
        BOT_TOKEN != "TU_TOKEN_DE_TELEGRAM"
        and CHAT_ID != "TU_CHAT_ID"
        and len(BOT_TOKEN) > 10
        and len(CHAT_ID) > 0
    )


# ======================================================
# FUNCION MENSAJE DE ESTADO
# ======================================================

# Genera un mensaje con el estado completo del sistema.
def mensaje_estado():

    # Si no hay lectura de temperatura muestra SIN LECTURA.
    temp = "SIN LECTURA" if estado["temperatura"] is None else "{:.1f} C".format(estado["temperatura"])

    # Si no hay lectura de humedad muestra SIN LECTURA.
    hum = "SIN LECTURA" if estado["humedad"] is None else "{:.1f} %".format(estado["humedad"])

    # Retorna mensaje formateado.
    return (
        "ESTADO DEL SISTEMA\n"
        "Temperatura: {}\n"
        "Humedad: {}\n"
        "DHT: {}\n"
        "Movimiento: {}\n"
        "Magnitud: {:.2f} g\n"
        "Alarma: {}\n"
        "Boton panico: {}\n"
        "IP: {}"
    ).format(
        temp,
        hum,

        # Muestra estado del sensor DHT.
        "OK" if estado["dht_ok"] else "SIN LECTURA",

        estado["movimiento"],
        estado["magnitud_g"],
        estado["alarma"],
        estado["panico"],
        estado["ip"]
    )


# ======================================================
# FUNCION MENSAJE DE UMBRALES
# ======================================================

# Genera un mensaje con los limites configurados.
def mensaje_umbrales():

    return (
        "UMBRALES CONFIGURADOS\n"
        "Temperatura minima: {:.1f} C\n"
        "Temperatura maxima: {:.1f} C\n"
        "Humedad minima: {:.1f} %\n"
        "Humedad maxima: {:.1f} %\n"
        "Movimiento normal: > {:.2f} g\n"
        "Movimiento brusco: > {:.2f} g"
    ).format(
        TEMP_MIN,
        TEMP_MAX,
        HUM_MIN,
        HUM_MAX,
        MOV_NORMAL_G,
        MOV_BRUSCO_G
    )


# ======================================================
# FUNCION ENVIAR TELEGRAM
# ======================================================

# Funcion asincrona para enviar mensajes Telegram.
async def enviar_telegram(mensaje):

    """
    Envia mensajes al bot Telegram.
    """

    # Si Telegram no esta configurado.
    if not telegram_configurado():

        # Imprime mensaje localmente.
        print("Telegram no configurado. Mensaje local:", mensaje)

        return False

    try:

        # Construye URL de Telegram.
        url = (
            "https://api.telegram.org/bot{}/sendMessage?chat_id={}&text={}"
            .format(BOT_TOKEN, CHAT_ID, url_encode(mensaje))
        )

        # Realiza peticion HTTP GET.
        respuesta = urequests.get(url)

        # Guarda codigo HTTP.
        codigo = respuesta.status_code

        # Cierra conexion.
        respuesta.close()

        # Si la respuesta fue exitosa.
        if codigo == 200:

            print("Mensaje enviado a Telegram.")

            return True

        else:

            print("Telegram respondio con codigo:", codigo)

            return False

    except Exception as e:

        # Captura errores de conexion.
        print("Error enviando Telegram:", e)

        return False


# ======================================================
# FUNCION ALERTA SONORA
# ======================================================

# Genera sonidos diferentes segun el tipo de alarma.
async def alerta_sonora(tipo):

    """
    Patrones sonoros diferenciados.
    """

    # Alarma de temperatura.
    if tipo == "TEMPERATURA":

        frecuencia = 1000
        repeticiones = 2

    # Alarma de humedad.
    elif tipo == "HUMEDAD":

        frecuencia = 1300
        repeticiones = 3

    # Alarma de movimiento.
    elif tipo == "MOVIMIENTO":

        frecuencia = 2000
        repeticiones = 4

    # Alarma de panico.
    elif tipo == "PANICO":

        frecuencia = 2500
        repeticiones = 5

    # Error DHT.
    elif tipo == "DHT":

        frecuencia = 700
        repeticiones = 1

    # Caso por defecto.
    else:

        frecuencia = 900
        repeticiones = 1


    # Ejecuta los pitidos.
    for _ in range(repeticiones):

        # Configura frecuencia del buzzer.
        buzzer.freq(frecuencia)

        # Activa PWM.
        buzzer.duty(512)

        # Espera.
        await asyncio.sleep(0.16)

        # Apaga buzzer.
        buzzer.duty(0)

        # Espera entre pitidos.
        await asyncio.sleep(0.12)

    # Garantiza apagado final.
    buzzer.duty(0)


# ======================================================
# FUNCION DISPARAR ALERTA
# ======================================================

# Activa sonido y envia mensaje evitando spam.
async def disparar_alerta(tipo, mensaje):

    """
    Activa alerta sonora y remota.
    """

    # Obtiene tiempo actual.
    ahora = time.time()

    # Obtiene ultimo envio.
    ultimo = ultimo_envio_alerta.get(tipo, 0)

    # Ejecuta sonido.
    await alerta_sonora(tipo)

    # Verifica tiempo anti spam.
    if ahora - ultimo >= ANTI_SPAM_ALERTA:

        # Guarda nuevo tiempo.
        ultimo_envio_alerta[tipo] = ahora

        # Envia mensaje Telegram.
        await enviar_telegram("ALERTA {}:\n{}".format(tipo, mensaje))

    # Imprime alerta en consola.
    print("ALERTA", tipo, mensaje)


# ======================================================
# FUNCION LEER DHT DE FORMA SEGURA
# ======================================================

# Lee el DHT evitando que el programa se detenga.
def leer_dht_seguro():

    """
    Lee temperatura y humedad de forma segura.
    """

    try:

        # Realiza medicion.
        sensor_dht.measure()

        # Obtiene temperatura.
        temperatura = float(sensor_dht.temperature())

        # Obtiene humedad.
        humedad = float(sensor_dht.humidity())

        # Guarda temperatura en estado global.
        estado["temperatura"] = temperatura

        # Guarda humedad en estado global.
        estado["humedad"] = humedad

        # Marca lectura valida.
        estado["dht_ok"] = True

        # Retorna datos.
        return temperatura, humedad, True

    except Exception as e:

        # Captura errores.
        print("Error leyendo DHT:", e)

        # Marca error DHT.
        estado["dht_ok"] = False

        # Retorna ultimos valores validos.
        return estado["temperatura"], estado["humedad"], False
    # ======================================================
# TAREA 1: MONITOREO DE SENSORES
# ======================================================

# Tarea asincrona principal de monitoreo.
async def tarea_sensores():

    # Guarda IP inicial del ESP32.
    estado["ip"] = obtener_ip()

    # Envia mensaje inicial Telegram.
    await enviar_telegram(
        "ESP32 iniciado correctamente.\nIP del servidor web: http://{}".format(estado["ip"])
    )

    # Bucle infinito.
    while True:

        # Lista donde se almacenan alarmas activas.
        alarmas = []

        try:

            # ==================================================
            # LECTURA DEL SENSOR DHT
            # ==================================================

            # Lee temperatura y humedad de forma segura.
            temperatura, humedad, dht_ok = leer_dht_seguro()


            # ==================================================
            # LECTURA MPU6050
            # ==================================================

            try:

                # Lee aceleracion en ejes X,Y,Z.
                ax, ay, az = mpu.leer_aceleracion_g()

                # Calcula magnitud total.
                magnitud = mpu.leer_magnitud_g()

                # Clasifica movimiento.
                movimiento = mpu.clasificar_movimiento(magnitud)

                # Guarda valores en estado global.
                estado["ax"] = ax
                estado["ay"] = ay
                estado["az"] = az

                estado["magnitud_g"] = magnitud
                estado["movimiento"] = movimiento

            except Exception as e:

                # Captura errores MPU6050.
                print("Error leyendo MPU6050:", e)

                # Marca error.
                estado["movimiento"] = "ERROR MPU6050"

                # Conserva ultimo valor valido.
                magnitud = estado["magnitud_g"]
                movimiento = estado["movimiento"]


            # ==================================================
            # ESTADO DEL BOTON DE PANICO
            # ==================================================

            # Si el pulsador esta presionado.
            estado["panico"] = "ACTIVO" if pulsador.value() == 0 else "INACTIVO"

            # Guarda timestamp de actualizacion.
            estado["ultima_actualizacion"] = str(time.time())

            # Actualiza direccion IP.
            estado["ip"] = obtener_ip()


            # ==================================================
            # VALIDACION DE TEMPERATURA Y HUMEDAD
            # ==================================================

            # Solo verifica si DHT tiene lectura valida.
            if dht_ok:

                # Temperatura baja.
                if temperatura < TEMP_MIN:

                    # Agrega alarma.
                    alarmas.append("TEMPERATURA BAJA")

                    # Dispara alerta.
                    await disparar_alerta(
                        "TEMPERATURA",
                        "Temperatura baja: {:.1f} C. Limite minimo: {:.1f} C"
                        .format(temperatura, TEMP_MIN)
                    )

                # Temperatura alta.
                if temperatura > TEMP_MAX:

                    alarmas.append("TEMPERATURA ALTA")

                    await disparar_alerta(
                        "TEMPERATURA",
                        "Temperatura alta: {:.1f} C. Limite maximo: {:.1f} C"
                        .format(temperatura, TEMP_MAX)
                    )

                # Humedad baja.
                if humedad < HUM_MIN:

                    alarmas.append("HUMEDAD BAJA")

                    await disparar_alerta(
                        "HUMEDAD",
                        "Humedad baja: {:.1f} %. Limite minimo: {:.1f} %"
                        .format(humedad, HUM_MIN)
                    )

                # Humedad alta.
                if humedad > HUM_MAX:

                    alarmas.append("HUMEDAD ALTA")

                    await disparar_alerta(
                        "HUMEDAD",
                        "Humedad alta: {:.1f} %. Limite maximo: {:.1f} %"
                        .format(humedad, HUM_MAX)
                    )

            # Si no hubo lectura DHT.
            else:

                # Agrega alarma.
                alarmas.append("DHT SIN LECTURA")

                # Dispara alerta.
                await disparar_alerta(
                    "DHT",
                    "No se pudo leer el sensor DHT. Revise tipo de sensor, DATA GPIO 4, VCC 3V3 y GND."
                )


            # ==================================================
            # VALIDACION DE MOVIMIENTO
            # ==================================================

            # Si hubo movimiento brusco.
            if estado["movimiento"] == "MOVIMIENTO BRUSCO":

                # Agrega alarma.
                alarmas.append("MOVIMIENTO BRUSCO")

                # Dispara alerta.
                await disparar_alerta(
                    "MOVIMIENTO",
                    "Movimiento brusco detectado. Magnitud: {:.2f} g"
                    .format(estado["magnitud_g"])
                )


            # ==================================================
            # VALIDACION BOTON PANICO
            # ==================================================

            # Si boton esta presionado.
            if pulsador.value() == 0:

                # Agrega alarma.
                alarmas.append("BOTON DE PANICO")

                # Dispara alerta.
                await disparar_alerta(
                    "PANICO",
                    "Boton de panico activado manualmente."
                )


            # ==================================================
            # ESTADO GENERAL DE ALARMAS
            # ==================================================

            # Si no hay alarmas.
            if len(alarmas) == 0:

                # Estado normal.
                estado["alarma"] = "NORMAL"

                # Apaga buzzer.
                buzzer.duty(0)

            else:

                # Une todas las alarmas activas.
                estado["alarma"] = " / ".join(alarmas)

        except Exception as e:

            # Captura errores generales.
            estado["alarma"] = "ERROR GENERAL"

            # Apaga buzzer.
            buzzer.duty(0)

            # Imprime error.
            print("Error general en tarea_sensores:", e)


        # Libera memoria RAM.
        gc.collect()

        # Espera antes de siguiente lectura.
        await asyncio.sleep(INTERVALO_SENSORES)
        # ======================================================
# TAREA 2: SERVIDOR WEB
# ======================================================

# Funcion que genera la pagina HTML.
def pagina_web():

    # Define color dependiendo del estado.
    color_alarma = "#0f9d58" if estado["alarma"] == "NORMAL" else "#d93025"

    # Si no hay temperatura valida.
    temp_web = "SIN LECTURA" if estado["temperatura"] is None else "{:.1f}".format(estado["temperatura"])

    # Si no hay humedad valida.
    hum_web = "SIN LECTURA" if estado["humedad"] is None else "{:.1f}".format(estado["humedad"])


    # Contenido HTML de la pagina.
    html = """<!DOCTYPE html>
<html>

<head>

    <!-- Configuracion de caracteres -->
    <meta charset="UTF-8">

    <!-- Recarga automatica cada 3 segundos -->
    <meta http-equiv="refresh" content="3">

    <!-- Titulo pestaña navegador -->
    <title>Seguimiento V - ESP32</title>

    <style>

        /* Estilo general */
        body {{
            font-family: Arial, sans-serif;
            background: #f3f6fb;
            margin: 0;
            padding: 24px;
            color: #1f2933;
        }}

        /* Tarjeta principal */
        .card {{
            max-width: 760px;
            margin: auto;
            background: white;
            border-radius: 14px;
            padding: 24px;
            box-shadow: 0 4px 18px rgba(0,0,0,0.12);
        }}

        /* Titulo principal */
        h1 {{
            margin-top: 0;
            color: #0b5394;
        }}

        /* Grid de informacion */
        .grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 14px;
        }}

        /* Caja individual */
        .box {{
            background: #eef3f8;
            border-radius: 10px;
            padding: 14px;
        }}

        /* Valores grandes */
        .value {{
            font-size: 28px;
            font-weight: bold;
        }}

        /* Barra de alarma */
        .alarm {{
            background: {color_alarma};
            color: white;
            border-radius: 10px;
            padding: 14px;
            font-size: 20px;
            font-weight: bold;
            margin: 16px 0;
        }}

        /* Texto pequeño */
        .small {{
            font-size: 13px;
            color: #5f6b7a;
        }}

        /* Tabla */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 12px;
        }}

        /* Celdas */
        td, th {{
            padding: 8px;
            border-bottom: 1px solid #d8dee9;
            text-align: left;
        }}

    </style>

</head>

<body>

    <!-- Contenedor principal -->
    <div class="card">

        <!-- Titulo -->
        <h1>Monitoreo IoT Biomedico - ESP32</h1>

        <!-- Descripcion -->
        <p class="small">
            Servidor web embebido con actualizacion automatica cada 3 segundos.
        </p>

        <!-- Estado alarma -->
        <div class="alarm">
            Estado de alarma: {alarma}
        </div>

        <!-- Grid principal -->
        <div class="grid">

            <!-- Temperatura -->
            <div class="box">
                <div>Temperatura</div>
                <div class="value">{temperatura} C</div>
            </div>

            <!-- Humedad -->
            <div class="box">
                <div>Humedad relativa</div>
                <div class="value">{humedad} %</div>
            </div>

            <!-- Movimiento -->
            <div class="box">
                <div>Estado de movimiento</div>
                <div class="value">{movimiento}</div>
            </div>

            <!-- Magnitud -->
            <div class="box">
                <div>Magnitud aceleracion</div>
                <div class="value">{magnitud:.2f} g</div>
            </div>

        </div>


        <!-- Tabla estado sistema -->
        <h2>Estado del sistema</h2>

        <table>

            <tr>
                <th>Variable</th>
                <th>Valor</th>
            </tr>

            <tr>
                <td>Sensor DHT</td>
                <td>{dht_estado}</td>
            </tr>

            <tr>
                <td>Boton de panico</td>
                <td>{panico}</td>
            </tr>

            <tr>
                <td>Aceleracion X</td>
                <td>{ax:.2f} g</td>
            </tr>

            <tr>
                <td>Aceleracion Y</td>
                <td>{ay:.2f} g</td>
            </tr>

            <tr>
                <td>Aceleracion Z</td>
                <td>{az:.2f} g</td>
            </tr>

            <tr>
                <td>IP ESP32</td>
                <td>{ip}</td>
            </tr>

        </table>


        <!-- Tabla de umbrales -->
        <h2>Umbrales configurados</h2>

        <table>

            <tr>
                <th>Parametro</th>
                <th>Rango / limite</th>
            </tr>

            <tr>
                <td>Temperatura</td>
                <td>{tmin:.1f} C a {tmax:.1f} C</td>
            </tr>

            <tr>
                <td>Humedad</td>
                <td>{hmin:.1f} % a {hmax:.1f} %</td>
            </tr>

            <tr>
                <td>Movimiento</td>
                <td>Normal &gt; {mov:.2f} g</td>
            </tr>

            <tr>
                <td>Movimiento brusco</td>
                <td>&gt; {brusco:.2f} g</td>
            </tr>

        </table>

    </div>

</body>
</html>

""".format(

        # Variables insertadas en HTML.
        color_alarma=color_alarma,
        alarma=estado["alarma"],
        temperatura=temp_web,
        humedad=hum_web,
        movimiento=estado["movimiento"],
        magnitud=estado["magnitud_g"],

        # Estado DHT.
        dht_estado="OK" if estado["dht_ok"] else "SIN LECTURA",

        panico=estado["panico"],

        ax=estado["ax"],
        ay=estado["ay"],
        az=estado["az"],

        ip=estado["ip"],

        tmin=TEMP_MIN,
        tmax=TEMP_MAX,

        hmin=HUM_MIN,
        hmax=HUM_MAX,

        mov=MOV_NORMAL_G,
        brusco=MOV_BRUSCO_G
    )

    # Retorna pagina HTML.
    return html


# ======================================================
# SERVIDOR WEB
# ======================================================

# Tarea asincrona del servidor web.
async def servidor_web():

    # Funcion que atiende clientes HTTP.
    async def atender_cliente(reader, writer):

        try:

            # Lee peticion HTTP.
            request = await reader.read(1024)

            # Convierte bytes a texto.
            request = request.decode()


            # ==================================================
            # RESPUESTA JSON
            # ==================================================

            # Si la URL contiene /json.
            if "GET /json" in request:

                # Convierte estado a JSON.
                contenido = ujson.dumps(estado)

                # Encabezado HTTP.
                writer.write("HTTP/1.1 200 OK\r\n")

                # Tipo JSON.
                writer.write("Content-Type: application/json\r\n")

                # Cierra conexion.
                writer.write("Connection: close\r\n\r\n")

                # Envia contenido.
                writer.write(contenido)

            else:

                # Genera pagina web HTML.
                contenido = pagina_web()

                # Encabezado HTTP.
                writer.write("HTTP/1.1 200 OK\r\n")

                # Tipo HTML.
                writer.write("Content-Type: text/html\r\n")

                # Cierra conexion.
                writer.write("Connection: close\r\n\r\n")

                # Envia HTML.
                writer.write(contenido)


            # Fuerza envio de datos.
            await writer.drain()

            # Cierra conexion.
            await writer.wait_closed()

        except Exception as e:

            # Captura errores cliente.
            print("Error cliente web:", e)


    # Inicia servidor HTTP puerto 80.
    await asyncio.start_server(atender_cliente, "0.0.0.0", 80)

    # Mensaje en consola.
    print("Servidor web iniciado en http://{}".format(obtener_ip()))


    # Mantiene servidor vivo.
    while True:

        # Espera larga.
        await asyncio.sleep(3600)
        # ======================================================
# TAREA 3: BOT DE TELEGRAM
# ======================================================

# Tarea asincrona que revisa mensajes del bot.
async def tarea_telegram():

    # Permite modificar variable global.
    global telegram_offset

    # Verifica si Telegram esta configurado.
    if not telegram_configurado():

        # Mensaje en consola.
        print("Telegram no configurado. Configure BOT_TOKEN y CHAT_ID para activar el bot.")

        return


    # Bucle infinito.
    while True:

        try:

            # ==================================================
            # CONSULTA A TELEGRAM
            # ==================================================

            # Construye URL para obtener mensajes nuevos.
            url = (
                "https://api.telegram.org/bot{}/getUpdates?offset={}"
                .format(BOT_TOKEN, telegram_offset)
            )

            # Realiza solicitud HTTP.
            respuesta = urequests.get(url)

            # Convierte respuesta a JSON.
            datos = respuesta.json()

            # Cierra conexion HTTP.
            respuesta.close()


            # ==================================================
            # PROCESAMIENTO DE MENSAJES
            # ==================================================

            # Verifica si Telegram respondio correctamente.
            if datos.get("ok"):

                # Recorre mensajes recibidos.
                for item in datos.get("result", []):

                    # Guarda nuevo offset.
                    telegram_offset = item["update_id"] + 1

                    # Obtiene mensaje.
                    mensaje = item.get("message", {})

                    # Obtiene texto del mensaje.
                    texto = mensaje.get("text", "").strip().lower()


                    # ==========================================
                    # COMANDO /estado
                    # ==========================================

                    if texto == "/estado":

                        # Envia estado completo.
                        await enviar_telegram(mensaje_estado())


                    # ==========================================
                    # COMANDO /temp
                    # ==========================================

                    elif texto == "/temp":

                        # Si no hay lectura.
                        if estado["temperatura"] is None:

                            await enviar_telegram("Temperatura: SIN LECTURA")

                        else:

                            # Envia temperatura actual.
                            await enviar_telegram(
                                "Temperatura actual: {:.1f} C".format(estado["temperatura"])
                            )


                    # ==========================================
                    # COMANDO /humedad
                    # ==========================================

                    elif texto == "/humedad":

                        # Si no hay lectura.
                        if estado["humedad"] is None:

                            await enviar_telegram("Humedad: SIN LECTURA")

                        else:

                            # Envia humedad actual.
                            await enviar_telegram(
                                "Humedad actual: {:.1f} %".format(estado["humedad"])
                            )


                    # ==========================================
                    # COMANDO /movimiento
                    # ==========================================

                    elif texto == "/movimiento":

                        # Envia estado movimiento.
                        await enviar_telegram(
                            "Movimiento: {}\nMagnitud: {:.2f} g"
                            .format(estado["movimiento"], estado["magnitud_g"])
                        )


                    # ==========================================
                    # COMANDO /umbrales
                    # ==========================================

                    elif texto == "/umbrales":

                        # Envia umbrales configurados.
                        await enviar_telegram(mensaje_umbrales())


                    # ==========================================
                    # COMANDO /ayuda
                    # ==========================================

                    elif texto == "/ayuda":

                        # Envia lista comandos.
                        await enviar_telegram(
                            "Comandos disponibles:\n"
                            "/estado\n"
                            "/temp\n"
                            "/humedad\n"
                            "/movimiento\n"
                            "/umbrales\n"
                            "/ayuda"
                        )


                    # ==========================================
                    # COMANDO DESCONOCIDO
                    # ==========================================

                    elif texto:

                        # Mensaje comando invalido.
                        await enviar_telegram("Comando no reconocido. Use /ayuda")

        except Exception as e:

            # Captura errores Telegram.
            print("Error revisando Telegram:", e)


        # Libera memoria RAM.
        gc.collect()

        # Espera antes de siguiente consulta.
        await asyncio.sleep(INTERVALO_TELEGRAM)


# ======================================================
# PROGRAMA PRINCIPAL
# ======================================================

# Funcion principal del sistema.
async def main():

    # Mensaje inicial en consola.
    print("Iniciando sistema Seguimiento V...")

    # Guarda IP inicial.
    estado["ip"] = obtener_ip()


    # ==================================================
    # CREACION DE TAREAS ASINCRONAS
    # ==================================================

    # Inicia monitoreo sensores.
    asyncio.create_task(tarea_sensores())

    # Inicia servidor web.
    asyncio.create_task(servidor_web())

    # Inicia bot Telegram.
    asyncio.create_task(tarea_telegram())


    # ==================================================
    # BUCLE PRINCIPAL
    # ==================================================

    # Mantiene programa vivo.
    while True:

        # Espera.
        await asyncio.sleep(10)


# ======================================================
# EJECUCION PRINCIPAL
# ======================================================

try:

    # Ejecuta programa principal.
    asyncio.run(main())

finally:

    # Garantiza apagado del buzzer.
    buzzer.duty(0)

    # Reinicia loop asyncio.
    asyncio.new_event_loop()
