import socket
import sys
from kafka import KafkaConsumer, KafkaProducer
import time
from tabulate import tabulate
from colorama import Fore, Back, Style, init
import threading
import signal
import tkinter as tk
import requests
import uuid
import os
import requests
import uuid
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.serialization import load_pem_private_key
import mysql.connector
from mysql.connector import Error

FORMAT = "utf-8"
EXIT = "exit"
MAX_CONEXIONES = 10
TIME_OUT = 600000
taxis_autenticados = []
tokenTaxis = [] #lista para almacenar temporalmente los tokens de cada taxi, formato: [(taxi_id,token),...]
clientes = []
running = True


# Variables globales
PORT_BROKER = None
IP_KAFKA = None
PORT = None
IP_CENTRAL = None
PORT_API_CENTRAL = None
IP_API_CENTRAL = None
HOST_BDD = None
USER_BDD = None
PASSWORD_BDD = None
DATABASE_BDD = None
IP_CTC = None
PORT_CTC = None


def procesar_parametros():
    """Procesa los parámetros de entrada y los asigna a las variables globales."""
    global PORT_BROKER, IP_KAFKA, PORT, IP_CENTRAL, PORT_API_CENTRAL
    global IP_API_CENTRAL, HOST_BDD, USER_BDD, PASSWORD_BDD, DATABASE_BDD
    global IP_CTC, PORT_CTC

    if len(sys.argv) != 13:
        print("Error en los argumentos.")
        print("Uso: python EC_Central.py <PORT_BROKER> <IP_KAFKA> <PORT> <IP_CENTRAL> <PORT_API_CENTRAL> "
              "<IP_API_CENTRAL> <HOST_BDD> <user> <password> <database> <IP_CTC> <PORT_CTC>")
        sys.exit(1)

    # Asignación de parámetros
    PORT_BROKER = int(sys.argv[1])
    IP_KAFKA = sys.argv[2]
    PORT = int(sys.argv[3])
    IP_CENTRAL = sys.argv[4]
    PORT_API_CENTRAL = int(sys.argv[5])
    IP_API_CENTRAL = sys.argv[6]
    HOST_BDD = sys.argv[7]
    USER_BDD = sys.argv[8]
    PASSWORD_BDD = sys.argv[9]
    DATABASE_BDD = sys.argv[10]
    IP_CTC = sys.argv[11]
    PORT_CTC = int(sys.argv[12])


# Función de conexión a la base de datos usando las variables globales
def conectar_db():
    """Crea una conexión a la base de datos usando los valores globales."""
    try:
        conexion = mysql.connector.connect(
            host=HOST_BDD,
            user=USER_BDD,
            password=PASSWORD_BDD,
            database=DATABASE_BDD
        )
        return conexion
    except Error as e:
        print(f"Error al conectar con la base de datos: {e}")
        sys.exit(1)


class MapaGUI:
    def __init__(self, root, size=20):
        self.size = size
        # Reduced canvas size to 800x800 pixels
        self.canvas = tk.Canvas(root, width=800, height=800)
        self.canvas.pack(padx=10, pady=10)  # Slightly reduced padding
        
        # Create a frame to hold the grid
        self.frame = tk.Frame(self.canvas)
        self.frame.pack(expand=True, fill='both')
        
        # Adjusted cell size to be more compact but still readable
        self.cells = [[tk.Label(self.frame, 
                              width=3,          # Reduced width from 4 to 3
                              height=1,         # Reduced height from 2 to 1
                              font=("Arial", 12, "bold"),  # Slightly reduced font size
                              relief="solid",
                              borderwidth=1)    
                       for _ in range(self.size)] for _ in range(self.size)]
        
        # Configure grid with minimal padding
        for i in range(self.size):
            self.frame.grid_rowconfigure(i, pad=1)  # Reduced padding
            self.frame.grid_columnconfigure(i, pad=1)
            for j in range(self.size):
                self.cells[i][j].grid(row=i, column=j, sticky="nsew")

    def actualizar_celda(self, x, y, color, text=""):
        self.cells[x][y].config(bg=color, text=text)

    def limpiar_mapa(self):
        for i in range(self.size):
            for j in range(self.size):
                self.actualizar_celda(i, j, "white")

def iniciarMapaGUI(root):
    return MapaGUI(root)

def actualizarMapaGUI(gui, mapa, taxis):
    colores = {
        'cliente': "yellow",
        'localizacion': "blue",
        'taxi_moviendose': "green",
        'taxi_parado': "red",
        'taxi_averiado': "orange",
        'empty': "white"
    }

    # Clear the map first
    gui.limpiar_mapa()

    # Create a set to track clients being serviced
    clientes_en_servicio = set()
    for taxi in taxis:
        if taxi['cliente']['estado'] in ["OK.", "finalizado"]:
            clientes_en_servicio.add(taxi['cliente']['ID'])
    for cliente in clientes:
        x,y = get_coordenadasCliente(cliente["ID"])
        gui.actualizar_celda(x, y, colores['cliente'], cliente["ID"])

    # First pass: Draw locations and only unserviced clients
    elementosMapa(mapa, "localizaciones.txt")
    for i in range(len(mapa)):
        for j in range(len(mapa[i])):
            if mapa[i][j].isupper():  # Location
                gui.actualizar_celda(i, j, colores['localizacion'], mapa[i][j])

    # Second pass: Draw taxis
    for taxi in taxis:
        id_taxi = taxi['ID']
        pos_actual = taxi['pos_actual']
        estado = taxi['estado']
        estado_cliente = taxi['cliente']['estado']
        id_cliente = taxi['cliente']['ID']

        # Skip invalid positions
        if not (0 <= pos_actual[0] < len(mapa) and 0 <= pos_actual[1] < len(mapa[0])):
            continue

        # Build taxi label
        taxi_label = f"{id_taxi}"
        
        # Add client to label if picked up
        if estado_cliente == "OK." and id_cliente:
            taxi_label += id_cliente

        # Determine taxi color based on state
        if estado == "OK.Parado":
            taxi_color = colores['taxi_parado']
        elif "OK.Servicio" in estado:
            taxi_color = colores['taxi_moviendose']
        elif estado == "KO.Parado":
            taxi_color = colores['taxi_averiado']
            taxi_label += "!"

        # Update taxi position on GUI
        gui.actualizar_celda(pos_actual[0], pos_actual[1], taxi_color, taxi_label)

#enviar datos a api-central
import requests

def enviar_datos_actualizados(taxis_autenticados, clientes, tokens):
    url_taxis = f'http://{IP_API_CENTRAL}:{PORT_API_CENTRAL}/api/taxis'
    url_clientes = f'http://{IP_API_CENTRAL}:{PORT_API_CENTRAL}/api/clientes'
    url_tokens = f'http://{IP_API_CENTRAL}:{PORT_API_CENTRAL}/api/tokens'

    try:
        # Enviar datos de taxis
        response_taxis = requests.post(url_taxis, json=taxis_autenticados)
        # if response_taxis.status_code == 200:
        #     print("")
        # else:
        #     print(f"Error al actualizar taxis: {response_taxis.status_code} - {response_taxis.text}")

        # Enviar datos de clientes
        response_clientes = requests.post(url_clientes, json=clientes)
        # if response_clientes.status_code == 200:
        #     print("")
        # else:
        #     print(f"Error al actualizar clientes: {response_clientes.status_code} - {response_clientes.text}")

        response_tokens = requests.post(url_tokens, json=tokens)
        # if response_tokens.status_code == 200:
        #     print("")
        # else:
        #     print(f"Error al actualizar clientes: {response_tokens.status_code} - {response_tokens.text}")

    except requests.RequestException as e:
        print(f"Error al enviar datos a la API central: {e}")

def enviar_datos_api(url, taxis, clientes):
    datos = {
        "taxis": taxis,
        "clientes": clientes
    }
    try:
        response = requests.post(url, json=datos)
        if response.status_code == 200:
            print("Datos enviados al API Rest exitosamente")
        else:
            print(f"Error al enviar datos: {response.status_code}")
    except requests.RequestException as e:
        print(f"Error en la conexión con el API Rest: {e}")

# Función para actualizar el mapa periódicamente en la interfaz de Tkinter
def actualizar_mapa_gui_periodicamente(gui):
    mapa = iniciarMapa()
    while running:
        moverTaxiaCliente(taxis_autenticados)
        actualizarMapaGUI(gui, mapa, taxis_autenticados)
        enviar_datos_actualizados(taxis_autenticados,clientes,tokenTaxis)
        # enviar_datos_api("http://localhost:8080",taxis_autenticados,clientes)
        time.sleep(1)

def signal_handler(sig, frame):
    global running
    print("\nCerrando Central...")
    running = False

signal.signal(signal.SIGINT, signal_handler)

def get_coordenadasCliente(id_cliente):
    for cliente in clientes:
        if cliente['ID']==id_cliente:
            return cliente['coordenadas']

# Devuelve las coordenadas de un cliente o una localización con el ID
def coordenadasID(ID):
    coor_x, coor_y = -1, -1
    filename = "clientes.txt" if ID.islower() else "localizaciones.txt"
    with open(filename, 'r') as archivo:
        for linea in archivo:
            id, x, y = linea.split()
            if id == ID:
                coor_x, coor_y = int(x), int(y)
    return coor_x, coor_y

def servicioFinalizado(taxi, id_cliente, id_localizacion):
    set_estado_cliente_taxi(taxis_autenticados, taxi, "OK.finalizado")
    mensaje = f"CLIENTE {id_cliente} SERVICIO FINALIZADO {id_localizacion}"
    print(mensaje)
    producer = KafkaProducer(bootstrap_servers=f"{IP_KAFKA}:{PORT_BROKER}", linger_ms=1,acks='all',request_timeout_ms=TIME_OUT)
    producer.send(f'central-cliente-{id_cliente}', mensaje.encode(FORMAT))
    # Asegurarse de que todos los mensajes han sido enviados
    producer.flush()

# Mover taxis de acuerdo a su posición actual y destino
def moverTaxiaCliente(taxis):
    for taxi in taxis:
        id_taxi = taxi['ID']
        pos_actual = taxi['pos_actual']
        destinoCliente = taxi['destino']['coordenadas']
        coor_cliente = taxi['cliente']['coordenadas']
        estadoTaxi = taxi['estado']
        #print(f"estado del Taxi{id_taxi} : {estadoTaxi}")
        if "Servicio" in estadoTaxi:
            movimientoTaxi(pos_actual, coor_cliente, destinoCliente, id_taxi, taxis)

def get_estado_cliente_taxi(taxis_autenticados, idTaxi):
    for taxi in taxis_autenticados:
        if taxi['ID'] == idTaxi:
            estado = taxi['cliente']['estado']
    return estado

def set_estado_cliente_taxi(taxis_autenticados, idTaxi, estado):
    #print(idTaxi)
    for taxi in taxis_autenticados:
        if taxi['ID'] == idTaxi:
            taxi['cliente']['estado'] = estado
    # query = "UPDATE taxis SET cliente_estado = %s WHERE ID = %s"
    # parametros = (estado, "TAXI"+idTaxi)
    # print(parametros)
    # filas_afectadas = ejecutar_query(query, parametros)
    # if filas_afectadas > 0:
    #     print(f"Consulta ejecutada con éxito. Filas afectadas: {filas_afectadas}")
    # else:
    #     print("No se realizó ningún cambio o ocurrió un error.")

# Verificar taxis disponibles en estado OK.Parado
def taxi_libre():
    URL = f"http://{IP_CTC}:{PORT_CTC}/clima"
    for taxi in taxis_autenticados:
        #print("taxi libre: ", taxi["ID"],taxi['estado'])
        if taxi['estado'] == "OK.Parado" and consumir_api(URL)=="OK":
            return taxi['ID']
    return 0

def get_estado(taxis_autenticados, id):
    for taxi in taxis_autenticados:
        if taxi['ID'] == id:
            return taxi['estado']
    return None

def get_estado_cliente_taxi(taxis_autenticados, idTaxi):
    for taxi in taxis_autenticados:
        if taxi['ID'] == idTaxi:
            estado = taxi['cliente']['estado']
    return estado
    
def set_estadoTaxi(taxis_autenticados, id, estado):
    for taxi in taxis_autenticados:
        if taxi['ID'] == id:
            taxi['estado'] = estado

def set_idCliente(taxis_autenticados, idTaxi, idCliente):
    for taxi in taxis_autenticados:
        if taxi['ID'] == idTaxi:
            taxi['cliente']['ID'] = idCliente
def get_idCliente(taxis_autenticados, idTaxi):
    for taxi in taxis_autenticados:
        if taxi['ID'] == idTaxi:
            idClientetaxi = taxi['cliente']['ID'] 
    return idClientetaxi

def set_Destino(taxis_autenticados, idTaxi, destino):
    for taxi in taxis_autenticados:
        if taxi['ID'] == idTaxi:
            taxi['destino']['ID'] = destino

def set_CoordenadaDestino(taxis_autenticados, idTaxi, coordenada):
    for taxi in taxis_autenticados:
        if taxi['ID'] == idTaxi:
            taxi['destino']['coordenadas'] = coordenada

def set_CoordenadaCliente(taxis_autenticados, idTaxi, coordenada):
    for taxi in taxis_autenticados:
        if taxi['ID'] == idTaxi:
            taxi['cliente']['coordenadas'] = coordenada
            id_cliente = taxi['cliente']['ID']
            for cliente in clientes:
                if cliente['ID'] == id_cliente:
                    cliente['coordenadas'] = coordenada

def get_idDestino(taxis_autenticados, idTaxi):
    for taxi in taxis_autenticados:
        if taxi['ID'] == idTaxi:
            id_destino = taxi['destino']['ID']
    return id_destino

def movimientoTaxi(pos_actual,cliente, destino,id_taxi, taxis):
    servFinalizado = None
    # Mover por filas primero
    #print(get_estado_cliente_taxi(taxis, id_taxi))
    id_cliente = get_idCliente(taxis, id_taxi)
    id_destino = get_idDestino(taxis, id_taxi)
    if pos_actual[0] < cliente[0] and get_estado_cliente_taxi(taxis, id_taxi) != "OK."  :
        servFinalizado = False
        pos_actual[0] += 1
    elif pos_actual[0] > cliente[0] and get_estado_cliente_taxi(taxis, id_taxi) != "OK." :
        servFinalizado = False
        pos_actual[0] -= 1
    # Luego moverse por columnas
    elif pos_actual[1] < cliente[1] and get_estado_cliente_taxi(taxis, id_taxi) != "OK.":
        servFinalizado = False
        pos_actual[1] += 1
    elif pos_actual[1] > cliente[1] and get_estado_cliente_taxi(taxis, id_taxi) != "OK.":
        servFinalizado = False
        pos_actual[1] -= 1
    elif pos_actual[0] < destino[0]:
        servFinalizado = False
        set_estado_cliente_taxi(taxis, id_taxi, "OK.")
        pos_actual[0] += 1
        coor = pos_actual[0],pos_actual[1]
        set_CoordenadaCliente(taxis,id_taxi,coor)
    elif pos_actual[0] > destino[0]:
        servFinalizado = False
        set_estado_cliente_taxi(taxis, id_taxi, "OK.")
        pos_actual[0] -= 1
        coor = pos_actual[0],pos_actual[1]
        set_CoordenadaCliente(taxis,id_taxi,coor)
    # Luego moverse por columnas
    elif pos_actual[1] < destino[1]:
        servFinalizado = False
        pos_actual[1] += 1
        coor = pos_actual[0],pos_actual[1]
        set_CoordenadaCliente(taxis,id_taxi,coor)
    elif pos_actual[1] > destino[1]:
        servFinalizado = False
        pos_actual[1] -= 1
        coor = pos_actual[0],pos_actual[1]
        set_CoordenadaCliente(taxis,id_taxi,coor)
    else:
        #print("porqueeee")
        coor = pos_actual[0],pos_actual[1]
        set_CoordenadaCliente(taxis, id_taxi, coor)
        if get_estado_cliente_taxi(taxis, id_taxi) != "finalizado":
            set_estado_cliente_taxi(taxis, id_taxi, "finalizado")
            set_estadoTaxi(taxis, id_taxi,"OK.Parado")
            servicioFinalizado(id_taxi, id_cliente, id_destino)
            if coor == (0,0):
                eliminar_taxi_por_id(taxis_autenticados,id_taxi)

# Cargar elementos en el mapa desde archivo
def elementosMapa(mapa, filename):
    with open(filename, 'r') as archivo:
        for linea in archivo:
            id_loc, x, y = linea.split()
            coor_x, coor_y = int(x), int(y)
            mapa[coor_x][coor_y] = id_loc
            
def iniciarClientes(mapa):
    with open("clientes.txt", 'r') as archivo:
        for linea in archivo:
            id_cliente, x, y = linea.split()
            coor_x, coor_y = int(x), int(y)
            cliente = {
                "ID":id_cliente,
                "coordenadas":(coor_x, coor_y)
            }
            clientes.append(cliente)

def elementosMapaCliente(mapa):
    for cliente in clientes:
        coor_x, coor_y  = cliente['coordenadas'] 
        mapa[coor_x][coor_y] = cliente['ID']
            
# Iniciar el mapa
def iniciarMapa():
    mapa = [['' for _ in range(20)] for _ in range(20)]
    elementosMapa(mapa, "localizaciones.txt")
    iniciarClientes(mapa)
    elementosMapaCliente(mapa)
    return mapa

def solicitudesClientes():
    time.sleep(1.5)
    print("Esperando mensajes...")
    
    consumer = KafkaConsumer(
        'cliente-central',
        bootstrap_servers=f'{IP_KAFKA}:{PORT_BROKER}',
        consumer_timeout_ms=TIME_OUT
    )
    
    for mensaje in consumer:
        solicitud = mensaje.value.decode(FORMAT)
        id_localizacion = solicitud.split()[0]  # Primer valor es la localización
        id_cliente = solicitud.split()[1]       # Segundo valor es el ID del cliente

        coor_cliente = get_coordenadasCliente(id_cliente)
        coor_localizacion = coordenadasID(id_localizacion)
        print("--------------------------------")

        if coor_cliente == (-1, -1):
            print("Este cliente no está registrado.")
        elif coor_localizacion == (-1, -1):
            print("Esta localización no está registrada.")
        else:
            print(f"Cliente {id_cliente} solicita servicio para el destino: {id_localizacion}")
            print(f"Cliente se encuentra en {coor_cliente} y su destino en {coor_localizacion}")
            taxi_disponible = taxi_libre()

            if taxi_disponible:
                disponibilidadTaxi = "OK"
                print(f"Taxi disponible: {taxi_disponible}")
                set_estadoTaxi(taxis_autenticados, taxi_disponible, "OK.Servicio " + id_cliente)
                set_estado_cliente_taxi(taxis_autenticados, taxi_disponible, "OK.Taxi" + taxi_disponible)
                set_idCliente(taxis_autenticados, taxi_disponible, id_cliente)
                set_Destino(taxis_autenticados, taxi_disponible, id_localizacion)
                set_CoordenadaCliente(taxis_autenticados, taxi_disponible, coor_cliente)
                set_CoordenadaDestino(taxis_autenticados, taxi_disponible, coor_localizacion)
                #print(taxis_autenticados)
            else:
                disponibilidadTaxi = "KO"
                print("No hay taxis disponibles.")

            # Enviar mensaje de disponibilidad a un tema específico para el cliente
            tema_cliente = f'central-cliente-{id_cliente}'
            producer = KafkaProducer(bootstrap_servers=f"{IP_KAFKA}:{PORT_BROKER}")
            producer.send(tema_cliente, disponibilidadTaxi.encode(FORMAT))
            producer.flush()
            producer.close()
            
        print("--------------------------------")

    consumer.close()
    print("Kafka consumer cerrado")

#CREAR TOKEN AUTENIFICACION
def generar_token():
    return str(uuid.uuid4())  # Genera un UUID de 36 caracteres

def validar_token(token, id_taxi):
    print(f"Validando token del taxi {id_taxi}")
    print(f"token: {token}")
    return (id_taxi,token) in tokenTaxis

# Función para verificar si un taxi está autenticado
def esta_autenticado(id_taxi):
    conexion = conectar_db()
    cursor = conexion.cursor()
    
    query = "SELECT autenticado FROM taxis WHERE ID = %s"
    cursor.execute(query, (id_taxi,))
    
    resultado = cursor.fetchone()
    
    conexion.close()
    
    if resultado is None:
        print(f"El taxi con ID {id_taxi} no está registrado.")
        return False
    else:
        autenticado = resultado[0]
        if autenticado:
            print(f"El taxi con ID {id_taxi} está autenticado.")
            return True
        else:
            print(f"El taxi con ID {id_taxi} no está autenticado.")
            return False

def esta_registrado(id_taxi):
    conexion = conectar_db()
    cursor = conexion.cursor()
    
    query = "SELECT * FROM taxis WHERE ID = %s"
    cursor.execute(query, (id_taxi,))
    
    resultado = cursor.fetchone()
    
    conexion.close()
    
    return not(resultado is None)


def manejar_taxi(conexion, addr):
    print(f"Conexión aceptada desde {addr}")
    data = conexion.recv(1024).decode('utf-8')

    # Extraer el número del ID del taxi (TAXI01 -> 1)
    id_taxi = data.upper()
    print(f"Autenticando taxi con ID: {id_taxi}")
    
    if not(esta_registrado(id_taxi)):
        print(f"El taxi con ID {id_taxi} no está registrado.")
        conexion.send(f"El taxi con ID {id_taxi} no está registrado.".encode(FORMAT))
    elif not(esta_autenticado(id_taxi)):
        conexion_bbdd = conectar_db()
        cursor = conexion_bbdd.cursor()
        
        query = "UPDATE taxis SET autenticado = 1 WHERE ID = %s"
        cursor.execute(query, (id_taxi,))
        conexion_bbdd.commit()
        conexion_bbdd.close()
        id_taxi_acortado = id_taxi.replace("TAXI", "")  # Extraer el número del taxi
        # Taxi autenticado con éxito
        taxi = {
            'ID': id_taxi_acortado,  # Guardar solo el número
            'pos_actual': [0, 0],
            'destino': {'ID': None, 'coordenadas': (0, 0)},
            'cliente': {'ID': None, 'coordenadas': (0, 0), 'estado': "OK. Sin Taxi"},
            'estado': "OK.Parado"
        }
        token = generar_token()
        tokenTaxis.append((id_taxi_acortado, token))
        taxis_autenticados.append(taxi)
        print(f"{id_taxi} ha sido autenticado con token: {token}")
        conexion.send(f"Taxi {id_taxi} ha sido autenticado con éxito, token: {token}".encode(FORMAT))
        # Activar la comunicación del Digital Engine
        digitalEngineEstadoTaxi(id_taxi_acortado)
    else:
        print(f"{id_taxi} ya está autenticado")
        conexion.send(f"Taxi {id_taxi} ya estaba autenticado.".encode(FORMAT))

    conexion.close()




    # Continuar con la autenticación si está registrado
    # with open("taxisDisponibles.txt", 'r') as bdd_taxis:
    #     id_taxi = id_taxi.replace("TAXI", "")  # Extraer el número del taxi
    #     for line in bdd_taxis:
    #         taxi_id_bdd = line.split()[0].replace("TAXI", "")  # Extraer el número del taxi
    #         if any(taxi['ID'] == id_taxi for taxi in taxis_autenticados):
    #             print(f"Este taxi ya está en la lista de autenticados")
    #             conexion.send(f"Taxi {id_taxi} ya está autenticado.".encode(FORMAT))
    #             break

    #         elif taxi_id_bdd == id_taxi:
    #             # Taxi autenticado con éxito
    #             taxi = {
    #                 'ID': id_taxi,  # Guardar solo el número
    #                 'pos_actual': [0, 0],
    #                 'destino': {'ID': None, 'coordenadas': (0, 0)},
    #                 'cliente': {'ID': None, 'coordenadas': (0, 0), 'estado': "OK. Sin Taxi"},
    #                 'estado': "OK.Parado"
    #             }
    #             token = generar_token()
    #             tokenTaxis.append((id_taxi, token))
    #             taxis_autenticados.append(taxi)
    #             print(f"{id_taxi} ha sido autenticado con token: {token}")
    #             conexion.send(f"Taxi {id_taxi} ha sido autenticado con éxito, token: {token}".encode(FORMAT))
    #             # Activar la comunicación del Digital Engine
    #             digitalEngineEstadoTaxi(IP_KAFKA, PORT_BROKER, id_taxi)
    #             break
    #     else:
    #         print(f"{id_taxi} no ha podido ser autenticado")
    #         conexion.send(f"Taxi {id_taxi} no ha podido ser autenticado.".encode(FORMAT))

    conexion.close()

def autenticacion():
    global running
    socket1 = socket.socket()
    socket1.bind((IP_CENTRAL, PORT))
    socket1.listen(5)
    socket1.settimeout(5)
    print("Central ON in", PORT)

    try:
        while running:
            try:
                conexion, addr = socket1.accept()
                hilo = threading.Thread(target=manejar_taxi, args=(conexion, addr))
                hilo.start()
            except socket.timeout:
                continue
    finally:
        # Cerrar el socket cuando se sale del bucle
        socket1.close()
        print("Socket cerrado correctamente.")

def eliminar_taxi_por_id(taxis_autenticados, id_taxi):
    taxis_autenticados[:] = [taxi for taxi in taxis_autenticados if taxi['ID'] != id_taxi]
    tokenTaxis[:] = [taxi for taxi in tokenTaxis if taxi[0] != id_taxi]
    query = "UPDATE taxis SET autenticado = %s WHERE ID = %s"
    parametros = (0, "TAXI"+id_taxi)
    filas_afectadas = ejecutar_query(query, parametros)
    print("consulta ejecutada: ",filas_afectadas)
    print(tokenTaxis)
    print(f"Taxi {id_taxi} eliminado de la lista de taxis autenticados. Se requiere re-autenticación.")
    #cerrar socket


def digitalEngineEstadoTaxi(id_taxi):
    # Cargar la clave privada del Taxi
    with open("clave_privada_taxi.pem", "rb") as archivo:
        clave_privada_taxi = load_pem_private_key(archivo.read(), password=None)
    print(f'taxi-central{id_taxi}')
    consumer = KafkaConsumer(
        f'taxi-central{id_taxi}', 
        bootstrap_servers=f'{IP_KAFKA}:{PORT_BROKER}',
        consumer_timeout_ms=TIME_OUT,
        auto_offset_reset='latest',  # Leer desde el principio (o latest si prefieres solo nuevos)
        group_id='mi-grupo-seguro',
        enable_auto_commit=False,
        value_deserializer=lambda v: v  # Leer datos binarios directamente
    )

    print("Esperando clave simétrica...")

    # Leer mensajes y procesarlos
    clave_simetrica = None
    cipher = None

    for mensaje in consumer:
        #print("degub1")
        try:
            if mensaje.value.startswith(b"KEY:"):
                clave_simetrica_cifrada = mensaje.value[4:]
                clave_simetrica = clave_privada_taxi.decrypt(
                    clave_simetrica_cifrada,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=SHA256()),
                        algorithm=SHA256(),
                        label=None
                    )
                )
                cipher = Fernet(clave_simetrica)
                print("Clave simétrica recibida y descifrada")

            # Procesar mensaje con prefijo "MSG:"
            elif mensaje.value.startswith(b"MSG:") and cipher:
                #desciframos mensjae
                mensaje_cifrado = mensaje.value[4:]
                mensaje_descifrado = cipher.decrypt(mensaje_cifrado).decode('utf-8')
                print(f"Mensaje recibido y descifrado: {mensaje_descifrado}")


                #Curso normal de los sensores
                mensaje = mensaje_descifrado
                estadoTaxi = mensaje.split(",")[0].strip()
                token = mensaje.split(",")[1].strip()

                if not(validar_token(token, id_taxi)):
                    print ("Token expirado")
                    break
                print(f"Estado recibido: {estadoTaxi}")

                answer = "continuar"
                result = get_estado(taxis_autenticados, id_taxi)

                if estadoTaxi == "OK":
                    result = f"OK.Servicio {get_idCliente(taxis_autenticados, id_taxi)}"
                elif estadoTaxi == "SR":
                    result = "OK.Parado"
                    answer = "Frenar coche"
                elif estadoTaxi == "SV":
                    result = f"OK.Servicio {get_idCliente(taxis_autenticados, id_taxi)}"
                    answer = "Continuar"
                elif estadoTaxi == "PC":
                    result = "OK.Parado"
                    answer = "Frenar coche"
                elif estadoTaxi == "A":  # KO Parado state
                    result = "KO.Parado"
                    answer = "Llamar Policía"
                    # Remove the taxi from the authenticated list and close its consumer
                    eliminar_taxi_por_id(taxis_autenticados, id_taxi)
                    consumer.close()
                    break  # Exit the loop since the taxi has been removed
                else:
                    answer = "Obstaculo no encontrado"

                # Update the state if not removed
                set_estadoTaxi(taxis_autenticados, id_taxi, result)
                print(f"{result}, Acción: {answer}, Taxi ID: {id_taxi}")
                time.sleep(2)
            else:
                print("Mensaje no procesado (formato desconocido)")

        except Exception as e:
            print("EXCEPTION: ",e)
            continue
    
    print("Kafka consumer cerrado para Taxi:", id_taxi)

def procesarComandoShell(comando, taxis_autenticados):
    """
    Procesa comandos de control para los taxis desde la shell
    """
    try:
        # Stop command (S01, S02, etc)
        if comando.startswith('S'):
            id_taxi = comando[1:]
            return stopTaxi(taxis_autenticados, id_taxi)
            
        # Resume command (R01, R02, etc)
        elif comando.startswith('R'):
            id_taxi = comando[1:]
            return resumeTaxi(taxis_autenticados, id_taxi)
            
        # Base return command (B01, B02, etc)
        elif comando.startswith('B'):
            id_taxi = comando[1:]
            return returnToBase(taxis_autenticados, id_taxi)
            
        # Change destination command (01-5-15, 02-7-12, etc)
        elif '-' in comando:
            parts = comando.split('-')
            if len(parts) == 3:
                id_taxi = parts[0]
                new_x = int(parts[1])
                new_y = int(parts[2])
                return changeDestination(taxis_autenticados, id_taxi, new_x, new_y)
        
        return "Comando no válido"
    
    except Exception as e:
        return f"Error procesando comando: {str(e)}"

def stopTaxi(taxis_autenticados, id_taxi):
    """
    Para el taxi y cambia su estado a OK.Parado
    """
    for taxi in taxis_autenticados:
        if taxi['ID'] == id_taxi:
            if "Servicio" in taxi['estado']:
                taxi['estado'] = "OK.Parado"
                return f"Taxi {id_taxi} detenido correctamente"
            else:
                return f"Taxi {id_taxi} ya está detenido o no está en servicio"
    return f"Taxi {id_taxi} no encontrado"

def resumeTaxi(taxis_autenticados, id_taxi):
    """
    Reanuda el taxi y cambia su estado a OK.Servicio
    """
    for taxi in taxis_autenticados:
        if taxi['ID'] == id_taxi:
            if taxi['estado'] == "OK.Parado" and taxi['cliente']['ID'] is not None:
                taxi['estado'] = f"OK.Servicio {taxi['cliente']['ID']}"
                return f"Taxi {id_taxi} reanudado correctamente"
            else:
                return f"Taxi {id_taxi} no puede reanudar servicio (no está parado o no tiene cliente asignado)"
    return f"Taxi {id_taxi} no encontrado"

def changeDestination(taxis_autenticados, id_taxi, new_x, new_y):
    """
    Cambia el destino del taxi a las nuevas coordenadas
    """
    if not (0 <= new_x < 20 and 0 <= new_y < 20):
        return f"Coordenadas ({new_x}, {new_y}) fuera de rango"
    
    for taxi in taxis_autenticados:
        if taxi['ID'] == id_taxi:
            if "Servicio" in taxi['estado'] or taxi['estado'] == "OK.Parado":
                taxi['destino']['coordenadas'] = (new_x, new_y)
                taxi['estado'] = f"OK.Servicio {taxi['cliente']['ID']}" if taxi['cliente']['ID'] else "OK.Servicio"
                return f"Destino del taxi {id_taxi} actualizado a ({new_x}, {new_y})"
            else:
                return f"Taxi {id_taxi} no puede cambiar destino en su estado actual"
    return f"Taxi {id_taxi} no encontrado"

def returnToBase(taxis_autenticados, id_taxi):
    """
    Envía el taxi de vuelta a la base (0,0)
    """
    for taxi in taxis_autenticados:
        if taxi['ID'] == id_taxi:
            if "Servicio" in taxi['estado'] or taxi['estado'] == "OK.Parado":
                id_cliente = taxi['cliente']['ID']
                id_destino = taxi['destino']['ID']
                coor = taxi['pos_actual']
                taxi['destino']['coordenadas'] = (0, 0)
                taxi['estado'] = "OK.Servicio"
                taxi['cliente']['ID'] = None
                taxi['cliente']['estado'] = "OK. Sin Taxi"
                set_CoordenadaCliente(taxis_autenticados,id_taxi,coor)
                servicioFinalizado(id_taxi, id_cliente, id_destino)
                return f"Taxi {id_taxi} retornando a base"
            else:
                return f"Taxi {id_taxi} no puede retornar a base en su estado actual"
    return f"Taxi {id_taxi} no encontrado"

def returnToBaseAll(taxis_autenticados):
    """
    Envía los taxis de vuelta a la base (0,0)
    """
    
    for taxi in taxis_autenticados:
        id_taxi = taxi["ID"]
        id_cliente = taxi['cliente']['ID']
        id_destino = taxi['destino']['ID']
        coor = taxi['pos_actual']
        taxi['destino']['coordenadas'] = (0, 0)
        taxi['estado'] = "OK.Servicio"
        taxi['cliente']['ID'] = None
        taxi['cliente']['estado'] = "OK. Sin Taxi"
        servicioFinalizado(id_taxi, id_cliente, id_destino)
        set_CoordenadaCliente(taxis_autenticados,id_taxi,coor)
    #servicioFinalizado(id_taxi, id_cliente, id_destino)
    return f"Taxis retornando a base"

def shellInputHandler():
    """
    Manejador de entrada de comandos desde la shell
    """
    while True:
        try:
            comando = input("Introduzca comando (S/R/B[ID] o ID-X-Y): ")
            if comando.lower() == 'exit':
                break
            resultado = procesarComandoShell(comando, taxis_autenticados)
            print(resultado)
        except Exception as e:
            print(f"Error en el comando: {str(e)}")

#API REST 
def consumir_api(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Lanza una excepción si el status no es 2xx
        data = response.json()

        # Obtener el estado
        estado = data.get("status", "KO")  # Por defecto "KO" si no está presente

        print(f"Estado obtenido: {estado}")
        return estado
    except requests.RequestException as e:
        print(f"Error al consumir la API: {e}")
    
def api_rest_ctc():
    while running:
        URL = f"http://{IP_CTC}:{PORT_CTC}/clima"  # Cambia la IP y el puerto si es necesario
        print(URL)
        estado = consumir_api(URL)
        if estado == 'OK':
            viable="La temperatura es correcta"
        elif estado=="KO":
            viable="La temperatura no es correcta"
            returnToBaseAll(taxis_autenticados)
        else:
            viable="error API"
        print(viable)
        time.sleep(10)

def vaciar_bdd():
    import mysql.connector

    # Conectar a la base de datos
    conn = conectar_db()

    cursor = conn.cursor()

    # Vaciar la tabla 'taxis'
    cursor.execute("TRUNCATE TABLE taxis")

    # Confirmar la transacción
    conn.commit()

    # Cerrar la conexión
    cursor.close()
    conn.close()

    print("La tabla 'taxis' ha sido vaciada.")



def ejecutar_query(query, parametros=None):
    """Ejecuta una consulta SQL en la base de datos.

    Args:
        query (str): La consulta SQL a ejecutar.
        parametros (tuple): Parámetros para la consulta SQL (opcional).

    Returns:
        int: Número de filas afectadas por la consulta.
    """
    try:
        conexion = conectar_db()
        cursor = conexion.cursor()
        cursor.execute(query, parametros)
        conexion.commit()
        filas_afectadas = cursor.rowcount
        cursor.close()
        conexion.close()
        return filas_afectadas
    except Error as e:
        print(f"Error al ejecutar la consulta: {e}")
        return 0



# # Configuración y ejecución de la interfaz Tkinter
# def main():
#     global running

#     vaciar_bdd()

#     # Validar el número de argumentos
#     if len(sys.argv) != 13:
#         print("Error en los argumentos.")
#         print("Uso: python EC_Central.py <PORT_BROKER> <IP_KAFKA> <PORT> <CENTRAL_IP> <PORT_API_CENTRAL> "
#               "<IP_API_CENTRAL> <HOST_BDD> <user> <password> <database> <IP_CTC> <PORT_CTC>")
#         sys.exit(1)

#     PORT_BROKER = int(sys.argv[1])
#     IP_KAFKA = sys.argv[2]
#     PORT = int(sys.argv[3])
#     CENTRAL_IP = sys.argv[4]
#     PORT_API_CENTRAL = int(sys.argv[5])
#     IP_API_CENTRAL = sys.argv[6]
#     HOST_BDD = sys.argv[7]
#     USER_BDD = sys.argv[8]
#     PASSWORD_BDD = sys.argv[9]
#     DATABASE_BDD = sys.argv[10]
#     IP_CTC = sys.argv[11]
#     PORT_CTC = int(sys.argv[12])

#     # Crear ventana de Tkinter
#     root = tk.Tk()
#     root.title("Mapa de Taxis y Clientes")
#     gui = iniciarMapaGUI(root)

#     # Hilos para la lógica y actualización del mapa
#     thread_autenticacion = threading.Thread(target=autenticacion, args=(PORT, IP_KAFKA, PORT_BROKER, IP_CENTRAL))
#     thread_solicitudes = threading.Thread(target=solicitudesClientes, args=(PORT_BROKER, IP_KAFKA, PORT_API, IP_API))
#     thread_mapa_gui = threading.Thread(target=actualizar_mapa_gui_periodicamente, args=(gui, PORT_BROKER, IP_KAFKA))
#     thread_api_weather = threading.Thread(target=api_rest_ctc, args=(PORT_API, IP_API,IP_KAFKA, PORT_BROKER))
#     thread_shell = threading.Thread(target=shellInputHandler, args = (IP_KAFKA, PORT_BROKER))  # Nuevo thread para la shell

#     thread_autenticacion.start()
#     thread_solicitudes.start()
#     thread_mapa_gui.start()
#     thread_api_weather.start()
#     thread_shell.start()  # Iniciando el thread de la shell

#     # Mantener la ventana de Tkinter en ejecución
#     root.protocol("WM_DELETE_WINDOW", lambda: setattr(running, False))
#     root.mainloop()

#     # Cierre de hilos
#     thread_autenticacion.join()
#     thread_solicitudes.join()
#     thread_mapa_gui.join()
#     thread_api_weather.join()
#     thread_shell.join()  # Esperando que termine el thread de la shell
#     print("Central cerrada con éxito")

# if __name__ == "__main__":
#     main()

# Función principal
def main():
    global running

    # Procesar parámetros
    vaciar_bdd()

    # Crear ventana de Tkinter
    root = tk.Tk()
    root.title("Mapa de Taxis y Clientes")
    gui = iniciarMapaGUI(root)

    # Hilos para la lógica y actualización del mapa
    thread_autenticacion = threading.Thread(target=autenticacion)
    thread_solicitudes = threading.Thread(target=solicitudesClientes)
    thread_mapa_gui = threading.Thread(target=actualizar_mapa_gui_periodicamente, args=(gui,))
    thread_api_weather = threading.Thread(target=api_rest_ctc)
    thread_shell = threading.Thread(target=shellInputHandler)

    # Iniciar hilos
    thread_autenticacion.start()
    thread_solicitudes.start()
    thread_mapa_gui.start()
    thread_api_weather.start()
    thread_shell.start()

    # Mantener la ventana de Tkinter en ejecución
    root.protocol("WM_DELETE_WINDOW", lambda: setattr(running, False))
    root.mainloop()

    # Cerrar hilos al salir
    thread_autenticacion.join()
    thread_solicitudes.join()
    thread_mapa_gui.join()
    thread_api_weather.join()
    thread_shell.join()
    print("Central cerrada con éxito")


# Iniciar el script
if __name__ == "__main__":
    procesar_parametros()  # Procesar parámetros antes de ejecutar el main
    main()