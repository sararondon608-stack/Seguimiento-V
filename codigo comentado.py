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